"""Lecture de contrôle d'un fichier MusicXML : que contient-il vraiment ?

Un export peut « réussir » et produire un fichier vide ou tronqué (Finale
interrompu, partie oubliée). On relit donc chaque fichier produit et on
compte ce qui compte pour un musicien : parties, mesures, notes, silences,
paroles, nuances, indications de texte. Le rapport final s'en sert pour
signaler ce qui mérite un coup d'œil.

Formats lus : .musicxml / .xml (texte) et .mxl (archive compressée).
La lecture se fait au fil de l'eau (iterparse) : une partition d'orchestre de
plusieurs dizaines de Mo ne charge pas la mémoire.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class Contenu:
    titre: str = ""
    compositeur: str = ""
    parties: list[str] = field(default_factory=list)
    mesures: int = 0            # mesures de la partie la plus longue
    notes: int = 0              # notes jouées (accords compris, silences exclus)
    silences: int = 0
    paroles: int = 0
    nuances: int = 0
    textes: int = 0             # indications (directions) autres que nuances
    logiciel: str = ""          # qui a écrit le fichier (Finale + Dolet, MuseScore…)
    version_xml: str = ""
    erreur: str = ""

    @property
    def lisible(self) -> bool:
        return not self.erreur

    @property
    def suspect(self) -> str:
        """Code d'alerte, vide si rien d'anormal."""
        if self.erreur:
            return "illisible"
        if not self.parties:
            return "sans_partie"
        if self.mesures == 0:
            return "sans_mesure"
        if self.notes == 0:
            return "sans_note"
        return ""

    def en_dict(self) -> dict:
        d = asdict(self)
        d["suspect"] = self.suspect
        return d


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ouvrir(chemin: Path):
    """Flux XML du fichier ; pour un .mxl, le fichier racine désigné par
    META-INF/container.xml (à défaut, le premier .xml/.musicxml hors META-INF)."""
    if chemin.suffix.lower() == ".mxl" or zipfile.is_zipfile(chemin):
        with zipfile.ZipFile(chemin) as z:
            noms = z.namelist()
            racine = None
            if "META-INF/container.xml" in noms:
                arbre = ET.fromstring(z.read("META-INF/container.xml"))
                for el in arbre.iter():
                    if _local(el.tag) == "rootfile" and el.get("full-path"):
                        racine = el.get("full-path")
                        break
            if not racine:
                racine = next((n for n in noms if not n.startswith("META-INF/")
                               and n.lower().endswith((".xml", ".musicxml"))), None)
            if not racine:
                raise ValueError("archive .mxl sans partition")
            return io.BytesIO(z.read(racine))
    return open(chemin, "rb")


def lire(chemin: str | Path) -> Contenu:
    """Ne lève jamais : un fichier illisible donne `Contenu.erreur`."""
    c = Contenu()
    chemin = Path(chemin)
    mesures_par_partie: dict[str, int] = {}
    noms_parties: dict[str, str] = {}
    ordre: list[str] = []
    partie = None
    try:
        flux = _ouvrir(chemin)
    except (OSError, zipfile.BadZipFile, ValueError, ET.ParseError) as e:
        c.erreur = type(e).__name__
        return c
    try:
        with flux:
            for evenement, el in ET.iterparse(flux, events=("start", "end")):
                nom = _local(el.tag)
                if evenement == "start":
                    if nom in ("score-partwise", "score-timewise"):
                        c.version_xml = el.get("version", "")
                    elif nom == "part" and el.get("id"):
                        partie = el.get("id")
                        mesures_par_partie.setdefault(partie, 0)
                    continue
                # fin d'élément
                if nom == "score-part":
                    ident = el.get("id", "")
                    pn = next((x for x in el if _local(x.tag) == "part-name"), None)
                    noms_parties[ident] = (pn.text or "").strip() if pn is not None else ""
                    ordre.append(ident)
                elif nom in ("work-title", "movement-title") and not c.titre:
                    c.titre = (el.text or "").strip()
                elif nom == "creator" and el.get("type") == "composer" and not c.compositeur:
                    c.compositeur = (el.text or "").strip()
                elif nom == "software" and not c.logiciel:
                    c.logiciel = (el.text or "").strip()
                elif nom == "measure" and partie is not None:
                    mesures_par_partie[partie] += 1
                    el.clear()                # mémoire : on jette la mesure lue
                elif nom == "note":
                    if any(_local(x.tag) == "rest" for x in el):
                        c.silences += 1
                    else:
                        c.notes += 1
                elif nom == "lyric":
                    c.paroles += 1
                elif nom == "dynamics":
                    c.nuances += 1
                elif nom == "words":
                    c.textes += 1
                elif nom == "part":
                    partie = None
    except ET.ParseError as e:
        c.erreur = f"ParseError ligne {getattr(e, 'position', ('?',))[0]}"
    except OSError as e:
        c.erreur = type(e).__name__
    c.parties = [noms_parties.get(i, "") or i for i in ordre] or list(mesures_par_partie)
    c.mesures = max(mesures_par_partie.values(), default=0)
    return c
