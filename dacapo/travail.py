"""Le déroulé complet, du dossier de partitions au rapport final.

    1. copie     chaque partition est copiée et vérifiée (originaux intouchés) ;
    2. Finale    chaque copie est ouverte, exportée en MusicXML (et en PDF de
                 référence si demandé), puis refermée sans enregistrer ;
    3. contrôle  chaque MusicXML est relu (parties, mesures, notes…) ;
    4. MuseScore chaque MusicXML devient un .mscz (+ PDF de comparaison) ;
    5. rapport   rapport.html dans le dossier de travail.

Le journal est enregistré après chaque partition : un arrêt (bouton,
coupure, plantage) ne fait perdre que la partition en cours, et la reprise
saute tout ce qui est déjà fait. Ce module ne connaît ni Qt ni Windows : le
pilote de Finale lui est fourni, ce qui permet de le tester avec un faux.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, Sequence

from . import inventaire, musescore, musicxml, rapport
from .inventaire import Fiche, Journal

REDEMARRER_TOUS_LES = 40     # Finale relancé régulièrement : il fuit en mémoire
ESSAIS_DEMARRAGE = 3


class Pilote(Protocol):
    imprevus: list[str]
    def demarrer(self) -> None: ...
    def arreter(self) -> None: ...
    def tuer(self) -> None: ...
    def ouvrir(self, fichier: Path) -> None: ...
    def exporter_musicxml(self, cible: Path) -> Path: ...
    def exporter_pdf(self, cible: Path) -> Path: ...
    def fermer_document(self) -> None: ...


@dataclass
class Options:
    musicxml: bool = True
    pdf: bool = True
    musescore: bool = True
    refaire_echecs: bool = True       # une partition en échec est retentée à la reprise


@dataclass
class Evenement:
    phase: str          # "copie", "finale", "musescore", "rapport", "fini"
    fait: int
    total: int
    nom: str = ""
    message: str = ""


def rel_posix(racine: Path, fichier: Path) -> str:
    return inventaire.relatif(racine, fichier).as_posix()


def executer(travail: Path, couples: Sequence[tuple[Path, Path]], options: Options, *,
             pilote: Callable[[], Pilote] | None = None,
             mscore: Path | None = None,
             rappel: Callable[[Evenement], None] | None = None,
             annule: Callable[[], bool] | None = None) -> Journal:
    travail = Path(travail)
    travail.mkdir(parents=True, exist_ok=True)
    journal = Journal(travail)
    dire = rappel or (lambda e: None)
    stop = annule or (lambda: False)

    # 1. copie --------------------------------------------------------------
    fiches: list[Fiche] = []
    for n, (racine, fichier) in enumerate(couples):
        if stop():
            break
        rel = rel_posix(Path(racine), Path(fichier))
        f = journal.fiche(rel, str(fichier))
        dire(Evenement("copie", n, len(couples), Path(fichier).name))
        try:
            inventaire.copier(Path(fichier), travail, rel, f)
            f.etats["copie"] = "ok"
            f.details.pop("copie", None)
        except OSError as e:
            f.etats["copie"], f.details["copie"] = "echec", e.strerror or str(e)
        fiches.append(f)
    journal.enregistrer()
    dire(Evenement("copie", len(fiches), len(couples)))

    # 2-3. Finale + contrôle ------------------------------------------------
    def a_faire(f: Fiche) -> bool:
        if not f.fait("copie"):
            return False
        besoins = []
        if options.musicxml:
            besoins.append("musicxml")
        if options.pdf:
            besoins.append("pdf")
        return any(not f.fait(b) and (options.refaire_echecs or f.etats.get(b) != "echec")
                   for b in besoins)

    restantes = [f for f in fiches if a_faire(f)] if pilote and (options.musicxml or options.pdf) else []
    if restantes and not stop():
        _phase_finale(travail, journal, restantes, options, pilote, dire, stop)

    # contrôle des MusicXML déjà présents (reprise, ou export fait à la main)
    for f in fiches:
        xml = inventaire.chemin_sortie(travail, f.rel, "musicxml", ".musicxml")
        if xml.exists() and not f.mesure:
            f.mesure = musicxml.lire(xml).en_dict()
            f.etats.setdefault("musicxml", "ok")
    journal.enregistrer()

    # 4. MuseScore ------------------------------------------------------------
    if options.musescore and mscore and not stop():
        paires, par_xml = [], {}
        for f in fiches:
            xml = inventaire.chemin_sortie(travail, f.rel, "musicxml", ".musicxml")
            if f.fait("musicxml") and xml.exists() and not f.fait("musescore"):
                mscz = inventaire.chemin_sortie(travail, f.rel, "musescore", ".mscz")
                pdf = inventaire.chemin_sortie(travail, f.rel, "musescore", ".pdf")
                paires.append((xml, mscz, pdf))
                par_xml[str(xml)] = f
        if paires:
            res = musescore.convertir(
                mscore, paires, annule=stop,
                progression=lambda a, b: dire(Evenement("musescore", a, b)))
            for xml, raison in res.items():
                f = par_xml[xml]
                if raison:
                    f.etats["musescore"], f.details["musescore"] = "echec", raison
                else:
                    f.etats["musescore"] = "ok"
                    f.details.pop("musescore", None)
            journal.enregistrer()

    # 5. rapport --------------------------------------------------------------
    dire(Evenement("rapport", 0, 1))
    rapport.ecrire(travail, journal, [f.rel for f in fiches])
    dire(Evenement("fini", len(fiches), len(fiches)))
    return journal


def _phase_finale(travail, journal, restantes, options, fabrique, dire, stop):
    p = None
    depuis_demarrage = 0

    def lancer():
        nonlocal p, depuis_demarrage
        for essai in range(ESSAIS_DEMARRAGE):
            try:
                p = fabrique()
                p.demarrer()
                depuis_demarrage = 0
                return True
            except Exception as e:
                dire(Evenement("finale", 0, len(restantes), message=f"demarrage:{e}"))
                if p is not None:
                    try:
                        p.tuer()
                    except Exception:
                        pass
        return False

    if not lancer():
        for f in restantes:
            f.details["finale"] = "demarrage"
        raise RuntimeError("finale_demarrage")
    try:
        for n, f in enumerate(restantes):
            if stop():
                break
            nom = Path(f.rel).name
            dire(Evenement("finale", n, len(restantes), nom))
            if depuis_demarrage >= REDEMARRER_TOUS_LES:
                p.arreter()
                if not lancer():
                    raise RuntimeError("finale_demarrage")
            debut = time.monotonic()
            etape = "ouverture"
            try:
                p.ouvrir(inventaire.copie(travail, f.rel))
                if options.musicxml and not f.fait("musicxml"):
                    etape = "musicxml"
                    xml = p.exporter_musicxml(
                        inventaire.chemin_sortie(travail, f.rel, "musicxml", ".musicxml"))
                    f.mesure = musicxml.lire(xml).en_dict()
                    f.etats["musicxml"] = "ok"
                    f.details.pop("musicxml", None)
                if options.pdf and not f.fait("pdf"):
                    etape = "pdf"
                    try:
                        p.exporter_pdf(inventaire.chemin_sortie(travail, f.rel, "pdf-finale", ".pdf"))
                        f.etats["pdf"] = "ok"
                        f.details.pop("pdf", None)
                    except Exception as e:
                        # Un PDF manqué n'empêche pas le MusicXML : on note et on continue.
                        f.etats["pdf"], f.details["pdf"] = "echec", str(e)
                etape = "fermeture"
                p.fermer_document()
            except Exception as e:
                code = str(e) or type(e).__name__
                if etape in ("ouverture", "musicxml"):
                    f.etats["musicxml"] = "echec"
                    f.details["musicxml"] = code
                f.details["imprevus"] = " | ".join(getattr(p, "imprevus", [])[-4:])
                # Finale dans un état inconnu : on le relance pour la suite.
                try:
                    p.tuer()
                except Exception:
                    pass
                if not lancer():
                    raise RuntimeError("finale_demarrage")
            else:
                if getattr(p, "imprevus", None):
                    f.details["imprevus"] = " | ".join(p.imprevus[-4:])
            f.duree = round(time.monotonic() - debut, 1)
            depuis_demarrage += 1
            journal.enregistrer()
        dire(Evenement("finale", len(restantes), len(restantes)))
    finally:
        try:
            p.arreter()
        except Exception:
            pass
