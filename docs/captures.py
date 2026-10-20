"""Captures du manuel, sans écran : QT_QPA_PLATFORM=offscreen python docs/captures.py

Tout est fictif : dossiers et partitions d'exemple créés dans un dossier
temporaire, Finale et MuseScore simulés (le manuel ne montre aucun nom ni
chemin réel, et se fabrique sur n'importe quelle machine).
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))

from PyQt6 import QtCore, QtWidgets  # noqa: E402

from dacapo import finale, fenetre, style  # noqa: E402
from dacapo.i18n import definir_langue, tr  # noqa: E402

EXEMPLES = {
    "fr": (r"C:\Users\Musicien\Documents\Partitions",
           r"C:\Users\Musicien\Documents\Partitions Finale - export Da Capo",
           ["Messe en ut/Kyrie.mus", "Messe en ut/Gloria.mus", "Noëls/Il est né.mus",
            "Noëls/Les anges dans nos campagnes.musx", "Ave verum.mus"]),
    "en": (r"C:\Users\Musician\Documents\Scores",
           r"C:\Users\Musician\Documents\Finale scores - Da Capo export",
           ["Mass in C/Kyrie.mus", "Mass in C/Gloria.mus", "Carols/Silent night.mus",
            "Carols/Angels we have heard on high.musx", "Ave verum.mus"]),
}

DIAGNOSTIC = """Finale : Finale 27 — 27.4.1 — C:\\Program Files\\MakeMusic\\Finale\\27\\Finale.exe
fenêtre principale : 'Finale' classe Afx:00400000:8

=== menus avec un document ouvert : 412 commandes ===
  ouvrir           → &Fichier > &Ouvrir...\tCtrl+O
  fermer           → &Fichier > &Fermer\tCtrl+W
  export MusicXML  → &Fichier > &Exporter > MusicXML...
  export PDF       → &Fichier > &Exporter > PDF...
  imprimer         → &Fichier > &Imprimer...\tCtrl+P
  -- arbre complet --
  &Fichier > &Nouveau > Document avec l'assistant...\tCtrl+N  [57600]
  …"""


def attendre(app, condition, delai=20):
    fin = time.time() + delai
    while time.time() < fin and not condition():
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.01)


def main():
    app = QtWidgets.QApplication([])
    style.appliquer(app)
    # Un poste Windows fictif, avec deux Finale et MuseScore installés.
    fenetre.win32.DISPONIBLE = True
    fenetre.finale.detecter = lambda: [
        finale.Finale("Finale 27", Path("Finale.exe"), rang=2027),
        finale.Finale("Finale 2006", Path("Finale2006.exe"), rang=2006)]
    fenetre.musescore.trouver = lambda: Path("MuseScore4.exe")
    for lg, (affiche_src, affiche_travail, noms) in EXEMPLES.items():
        definir_langue(lg)
        QtCore.QSettings("ARP273-ROSE", "DaCapo").clear()
        base = Path(tempfile.mkdtemp()) / "src"
        for n in noms:
            (base / n).parent.mkdir(parents=True, exist_ok=True)
            (base / n).write_bytes(b"finale")
        w = fenetre.FenetrePrincipale()
        w.resize(820, 900)
        w.e_travail.setText(str(Path(tempfile.mkdtemp()) / "neuf"))
        w.show()
        app.processEvents()
        w.grab().save(str(ICI / f"capture_vide-{lg}.png"))

        w.ajouter_sources([str(base)])
        attendre(app, lambda: len(w.couples) == len(noms))
        w.liste.item(0).setText(affiche_src)
        w.e_travail.setText(affiche_travail)
        w.e_travail.deselect()
        w.b_go.setFocus()
        app.processEvents()
        w.grab().save(str(ICI / f"capture_prete-{lg}.png"))

        # pendant l'export
        w.en_cours = True
        w._majeur()
        w.barre.setRange(0, 412)
        w.barre.setValue(137)
        w.barre.show()
        w.l_etat.setText(tr("phase.finale", nom=noms[1].split("/")[-1]) + "  (137/412)")
        app.processEvents()
        w.grab().save(str(ICI / f"capture_export-{lg}.png"))
        w.en_cours = False
        w.close()

        # diagnostic
        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle(tr("diag.titre"))
        dlg.resize(760, 420)
        lo = QtWidgets.QVBoxLayout(dlg)
        lab = QtWidgets.QLabel(tr("diag.resultat_ok"))
        lab.setWordWrap(True)
        lo.addWidget(lab)
        zone = QtWidgets.QPlainTextEdit(DIAGNOSTIC if lg == "fr" else DIAGNOSTIC
                                        .replace("&Fichier", "&File").replace("&Ouvrir", "&Open")
                                        .replace("&Fermer", "&Close").replace("&Exporter", "&Export")
                                        .replace("&Imprimer", "&Print").replace("&Nouveau", "&New"))
        zone.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lo.addWidget(zone, 1)
        btns = QtWidgets.QDialogButtonBox()
        btns.addButton(tr("diag.envoyer"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        btns.addButton(tr("dlg.fermer"), QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        lo.addWidget(btns)
        dlg.show()
        app.processEvents()
        dlg.grab().save(str(ICI / f"capture_diagnostic-{lg}.png"))
        dlg.close()
    print("captures écrites dans", ICI)


if __name__ == "__main__":
    main()
