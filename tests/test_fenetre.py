"""Fenêtre de Da Capo sans écran : ajout d'un dossier, recherche en fond,
lancement (copie + rapport ; Finale n'est piloté que sous Windows), reprise."""
import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from dacapo import style  # noqa: E402
from dacapo.i18n import definir_langue  # noqa: E402

definir_langue("fr")
from dacapo import fenetre as module_fenetre  # noqa: E402


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    style.appliquer(a)
    return a


def attendre(app, condition, delai=20.0):
    fin = time.time() + delai
    while time.time() < fin:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_parcours(app, tmp_path, monkeypatch):
    QtCore.QSettings("ARP273-ROSE", "DaCapo").clear()
    monkeypatch.setattr(module_fenetre.win32, "DISPONIBLE", False)
    monkeypatch.setattr(module_fenetre.musescore, "trouver", lambda: None)
    src = tmp_path / "Partitions"
    for nom in ("Kyrie.mus", "Gloria.MUS", "Credo.musx"):
        (src / "Messe").mkdir(parents=True, exist_ok=True)
        (src / "Messe" / nom).write_bytes(b"finale")
    w = module_fenetre.FenetrePrincipale()
    w.e_travail.setText(str(tmp_path / "Export"))
    w.show()
    assert not w.b_go.isEnabled()
    w.ajouter_sources([str(src)])
    assert attendre(app, lambda: len(w.couples) == 3)
    assert "3 partition" in w.l_trouves.text() and "2 .mus, 1 .musx" in w.l_trouves.text()
    assert w.b_go.isEnabled() and w.b_go.text() == "Commencer"
    assert not w.c_ms.isEnabled() and not w.cb_finale.isVisible()
    w._commencer_ou_arreter()
    assert attendre(app, lambda: not w.en_cours)
    t = tmp_path / "Export"
    assert (t / "originaux" / "Partitions" / "Messe" / "Kyrie.mus").read_bytes() == b"finale"
    assert (t / "rapport.html").exists() and w.b_rapport.isEnabled()
    assert w.b_go.text() == "Reprendre"
    assert "0 partition(s) exportée(s) sur 3" in w.l_etat.text()
    w.close()


def test_avertissement_et_textes_tiennent(app):
    w = module_fenetre.FenetrePrincipale()
    w.resize(640, 700)
    w.show()
    app.processEvents()
    assert w.l_avert.wordWrap() and w.l_avert.width() <= w.width()
    w.close()
