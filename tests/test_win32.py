"""Pilotage Win32 en vrai, sur le Bloc-notes classique (CI windows-latest) :
lecture des menus, commande « Enregistrer sous », remplissage de la boîte de
dialogue standard — les mêmes gestes que pour Finale."""
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows seulement")


def test_bloc_notes_enregistrer_sous(tmp_path):
    from dacapo import win32
    proc = subprocess.Popen(["notepad.exe"])
    try:
        def principale():
            for h in win32.fenetres(pid=proc.pid):
                if win32.user32.GetMenu(h):
                    return h
            return None
        fen = win32.attendre(principale, 20)
        if not fen:
            pytest.skip("Bloc-notes moderne (sans menus Win32) sur ce système")
        entrees = win32.menus(fen)
        save_as = next((e for e in entrees if len(e.chemin) == 2 and (
            "save as" in e.chemin[-1] or "enregistrer sous" in e.chemin[-1])), None)
        assert save_as is not None, [e.brut for e in entrees]
        zone = next(h for h in win32.enfants(fen) if win32.classe(h) in ("Edit", "RichEditD2DPT"))
        win32.ecrire(zone, "Da Capo")
        win32.commande(fen, save_as.commande)

        def boite():
            return next((d for d in win32.dialogues(pid=proc.pid) if win32.champ_nom_fichier(d)), None)
        d = win32.attendre(boite, 20)
        assert d is not None
        cible = tmp_path / "essai.txt"
        assert win32.remplir_et_valider(d, str(cible))
        assert win32.attendre(lambda: cible.exists() and cible.stat().st_size > 0, 20)
        assert cible.read_text(encoding="utf-8", errors="replace").strip().endswith("Da Capo")
    finally:
        proc.kill()
        time.sleep(0.5)
