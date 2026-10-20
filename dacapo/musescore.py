"""Préparer les partitions pour MuseScore Studio (libre et gratuit).

MuseScore sait convertir en lot depuis la ligne de commande : on lui donne
une liste de tâches (fichier JSON « -j »), il ouvre chaque MusicXML et
écrit un .mscz (sa partition, à ouvrir d'un double-clic) et un PDF (pour
comparer, page à page, avec le PDF de référence fait par Finale).

MuseScore travaille sans fenêtre ; une partition qui le fait planter
n'empêche pas les autres : on lui donne les fichiers par petits paquets et
on recommence sans la fautive.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence

PAQUET = 8            # partitions par lancement de MuseScore
DELAI_PAR_PARTITION = 120


def trouver() -> Path | None:
    """MuseScore Studio 4 (ou 3), aux emplacements d'installation usuels."""
    candidats: list[Path] = []
    if sys.platform == "win32":
        for base in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"),
                                  os.environ.get("ProgramFiles(x86)"))):
            for dossier in ("MuseScore 4", "MuseScore Studio 4", "MuseScore 3"):
                candidats += [Path(base) / dossier / "bin" / n
                              for n in ("MuseScore4.exe", "MuseScore3.exe", "MuseScore.exe")]
    elif sys.platform == "darwin":
        for app in ("MuseScore 4.app", "MuseScore Studio 4.app", "MuseScore 3.app"):
            for base in (Path("/Applications"), Path.home() / "Applications"):
                candidats += [base / app / "Contents" / "MacOS" / n for n in ("mscore", "MuseScore 4")]
    for c in candidats:
        if c.is_file():
            return c
    for nom in ("mscore4portable", "musescore4", "mscore4", "mscore", "musescore"):
        trouve = shutil.which(nom)
        if trouve:
            return Path(trouve)
    return None


def taches(paires: Sequence[tuple[Path, Path, Path | None]]) -> list[dict]:
    """[(musicxml, mscz, pdf ou None)] → tâches au format « -j » de MuseScore."""
    sortie = []
    for xml, mscz, pdf in paires:
        out = [str(mscz)] + ([str(pdf)] if pdf else [])
        sortie.append({"in": str(xml), "out": out})
    return sortie


def convertir(mscore: Path, paires: Sequence[tuple[Path, Path, Path | None]], *,
              progression: Callable[[int, int], None] | None = None,
              annule: Callable[[], bool] | None = None) -> dict[str, str]:
    """Convertit ; renvoie {musicxml: ""} si réussi, {musicxml: "raison"} sinon."""
    resultats: dict[str, str] = {}
    paires = list(paires)
    for _, mscz, pdf in paires:
        mscz.parent.mkdir(parents=True, exist_ok=True)
        if pdf:
            pdf.parent.mkdir(parents=True, exist_ok=True)
    i = 0
    while i < len(paires):
        if annule and annule():
            break
        lot = paires[i:i + PAQUET]
        _lancer(mscore, lot, resultats)
        # Un plantage de MuseScore au milieu d'un paquet : on refait un par
        # un ce qui n'a pas abouti, pour isoler la partition fautive.
        if len(lot) > 1 and any(resultats.get(str(x)) for x, _, _ in lot):
            for p in lot:
                if resultats.get(str(p[0])):
                    _lancer(mscore, [p], resultats)
        i += len(lot)
        if progression:
            progression(min(i, len(paires)), len(paires))
    return resultats


def _lancer(mscore: Path, lot, resultats: dict[str, str]) -> None:
    for _, mscz, pdf in lot:              # un reste d'essai ne doit pas passer pour réussi
        for x in (mscz, pdf):
            if x is not None:
                try:
                    x.unlink()
                except OSError:
                    pass
    with tempfile.TemporaryDirectory(prefix="dacapo-ms-") as tmp:
        travail = Path(tmp) / "taches.json"
        travail.write_text(json.dumps(taches(lot), ensure_ascii=False), encoding="utf-8")
        options = {}
        if sys.platform == "win32":
            options["creationflags"] = 0x08000000          # CREATE_NO_WINDOW
        # Pas de QT_QPA_PLATFORM=offscreen : MuseScore charge le thème GTK et
        # s'arrête net sans écran ; sous Windows et sur un bureau Linux, il
        # travaille sans ouvrir de fenêtre.
        env = dict(os.environ)
        try:
            subprocess.run([str(mscore), "-j", str(travail)], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=DELAI_PAR_PARTITION * len(lot), check=False, env=env, **options)
            raison = ""
        except subprocess.TimeoutExpired:
            raison = "delai"
        except OSError as e:
            raison = type(e).__name__
    for xml, mscz, pdf in lot:
        ok = mscz.exists() and mscz.stat().st_size > 0 and (pdf is None or pdf.exists())
        resultats[str(xml)] = "" if ok else (raison or "echec")
