"""Inventaire, copie de sécurité et journal des partitions Finale.

Règle d'or : les fichiers d'origine ne sont JAMAIS ouverts par Finale ni
modifiés. Da Capo en fait d'abord une copie (vérifiée par empreinte SHA-256)
dans le dossier de travail, et c'est cette copie que Finale ouvre.

Organisation du dossier de travail :

    <travail>/originaux/<source>/<sous-dossiers>/Partition.mus   copies intactes
    <travail>/musicxml/…/Partition.musicxml                       export Finale
    <travail>/pdf-finale/…/Partition.pdf                          PDF de référence
    <travail>/musescore/…/Partition.mscz (+ .pdf)                 prêt pour MuseScore
    <travail>/rapport.html                                        bilan à relire
    <travail>/_dacapo/journal.json                                reprise après arrêt

Le journal permet de reprendre là où on s'était arrêté (coupure, plantage de
Finale, ordinateur éteint) sans refaire ce qui est fait.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

#: Extensions des fichiers Finale. .mus : Finale jusqu'à 2011 ; .musx : 2012
#: et après ; .ftm : modèles (gabarits), utiles à garder mais pas à exporter.
EXT_FINALE = {".mus", ".musx"}
EXT_GARDER = EXT_FINALE | {".ftm", ".ftmx"}

#: Fichiers que Finale écrit lui-même et qu'il ne faut pas prendre pour des
#: partitions : sauvegardes automatiques et copies de secours.
PREFIXES_IGNORES = ("~", "._")
DOSSIERS_IGNORES = {"$recycle.bin", "system volume information", "windows", "program files",
                    "program files (x86)", "programdata", "appdata", "_dacapo"}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte)
                   if not unicodedata.combining(c)).casefold()


def est_partition(chemin: Path) -> bool:
    nom = chemin.name
    if nom.startswith(PREFIXES_IGNORES):
        return False
    bas = _sans_accents(nom)
    # « Sauvegarde de X.mus », « Backup of X.mus », « X.bak.mus » : copies de
    # secours de Finale, déjà représentées par le fichier principal.
    if bas.startswith(("sauvegarde de ", "backup of ")) or ".bak." in bas:
        return False
    return chemin.suffix.lower() in EXT_FINALE


def chercher(racines: Iterable[str | Path], *, annule: Callable[[], bool] | None = None,
             rappel: Callable[[int], None] | None = None) -> list[tuple[Path, Path]]:
    """Toutes les partitions sous `racines`, en couples (racine, fichier).

    Les sous-dossiers sont parcourus ; les dossiers système et ceux de Da Capo
    sont sautés, les liens symboliques ne sont pas suivis (pas de boucle). Un
    même fichier atteint par deux racines n'est compté qu'une fois.
    """
    vus: set[str] = set()
    trouves: list[tuple[Path, Path]] = []
    for racine in racines:
        racine = Path(racine)
        if racine.is_file():
            if est_partition(racine):
                cle = os.path.normcase(str(racine.resolve()))
                if cle not in vus:
                    vus.add(cle)
                    trouves.append((racine.parent, racine))
            continue
        for dossier, sous, fichiers in os.walk(racine, followlinks=False):
            if annule and annule():
                return trouves
            sous[:] = sorted(d for d in sous if _sans_accents(d) not in DOSSIERS_IGNORES
                             and not d.startswith("."))
            for nom in sorted(fichiers, key=_sans_accents):
                p = Path(dossier) / nom
                if est_partition(p):
                    cle = os.path.normcase(str(p.resolve()))
                    if cle not in vus:
                        vus.add(cle)
                        trouves.append((racine, p))
            if rappel:
                rappel(len(trouves))
    return trouves


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def relatif(racine: Path, fichier: Path) -> Path:
    """Chemin de rangement : nom de la racine + chemin sous la racine.

    Deux dossiers « Partitions » sur deux disques ne se mélangent pas : la
    racine est préfixée par sa lettre de lecteur si besoin."""
    nom_racine = racine.name or racine.drive.replace(":", "").replace("\\", "") or "racine"
    return Path(nom_racine) / fichier.relative_to(racine)


# ----------------------------------------------------------------- journal

ETAPES = ("copie", "musicxml", "pdf", "musescore")


@dataclass
class Fiche:
    """Ce que Da Capo sait d'une partition, d'une séance à l'autre."""
    rel: str                         # chemin de rangement (avec « / »)
    source: str                      # fichier d'origine
    sha256: str = ""
    taille: int = 0
    etats: dict = field(default_factory=dict)     # étape -> "ok" | "echec" | "saute"
    details: dict = field(default_factory=dict)   # étape -> message
    mesure: dict = field(default_factory=dict)    # contenu du MusicXML (parties, mesures…)
    duree: float = 0.0                            # secondes passées dans Finale

    def fait(self, etape: str) -> bool:
        return self.etats.get(etape) == "ok"


class Journal:
    """journal.json du dossier de travail, réécrit à chaque changement (de
    façon atomique : une coupure ne laisse jamais un journal à moitié écrit)."""

    def __init__(self, travail: Path):
        self.travail = Path(travail)
        self.chemin = self.travail / "_dacapo" / "journal.json"
        self.fiches: dict[str, Fiche] = {}
        if self.chemin.exists():
            try:
                brut = json.loads(self.chemin.read_text(encoding="utf-8"))
                for d in brut.get("fiches", []):
                    self.fiches[d["rel"]] = Fiche(**d)
            except (OSError, ValueError, TypeError, KeyError):
                # Journal illisible : on le met de côté, rien n'est perdu
                # (les fichiers produits restent, ils seront revérifiés).
                try:
                    self.chemin.replace(self.chemin.with_suffix(f".illisible-{int(time.time())}"))
                except OSError:
                    pass

    def fiche(self, rel: str, source: str) -> Fiche:
        if rel not in self.fiches:
            self.fiches[rel] = Fiche(rel=rel, source=source)
        else:
            self.fiches[rel].source = source
        return self.fiches[rel]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        donnees = {"version": 1, "fiches": [asdict(f) for f in self.fiches.values()]}
        fd, tmp = tempfile.mkstemp(prefix=".journal-", suffix=".tmp", dir=self.chemin.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(donnees, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.chemin)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


# ----------------------------------------------------------------- chemins

def chemin_sortie(travail: Path, rel: str, dossier: str, extension: str) -> Path:
    r = Path(rel)
    return Path(travail) / dossier / r.parent / (r.stem + extension)


def copie(travail: Path, rel: str) -> Path:
    return Path(travail) / "originaux" / Path(rel)


def copier(source: Path, travail: Path, rel: str, fiche: Fiche) -> Path:
    """Copie de sécurité vérifiée. Une copie déjà présente et identique (même
    empreinte) n'est pas refaite ; une copie différente est remplacée, jamais
    l'original."""
    cible = copie(travail, rel)
    sha = empreinte(source)
    fiche.sha256, fiche.taille = sha, source.stat().st_size
    if cible.exists() and empreinte(cible) == sha:
        return cible
    cible.parent.mkdir(parents=True, exist_ok=True)
    tmp = cible.with_name(cible.name + ".copie")
    shutil.copy2(source, tmp)
    if empreinte(tmp) != sha:
        tmp.unlink(missing_ok=True)
        raise OSError("copie différente de l'original")
    os.replace(tmp, cible)
    # La copie est en lecture seule : Finale ne pourra pas l'écraser par
    # mégarde (une question « Enregistrer ? » validée trop vite).
    try:
        os.chmod(cible, 0o444)
    except OSError:
        pass
    return cible


def fichier_stable(chemin: Path, delai: float = 1.0) -> bool:
    """Le fichier existe, n'est pas vide, et sa taille ne bouge plus."""
    try:
        t1 = chemin.stat().st_size
        if t1 <= 0:
            return False
        time.sleep(delai)
        return chemin.stat().st_size == t1
    except OSError:
        return False
