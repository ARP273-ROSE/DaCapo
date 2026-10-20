#!/usr/bin/env python3
"""Lanceur de Da Capo — sortir ses partitions de Finale.

    python run.py                    ouvre la fenêtre
    python run.py DOSSIER …          ouvre la fenêtre avec ces dossiers de partitions

Branchement du kit Windows, comme MusicOthèque et Anticythere3D : rapports
d'incident (plantage Python, crash natif, gel), accord au premier lancement,
verrou nommé lu par l'installeur, vérification silencieuse des mises à jour.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")

NOM = "DaCapo"
_fichier_faulthandler = None


def _dossier_donnees() -> Path:
    """Données hors du dossier d'installation : elles survivent aux mises à jour.

    Windows : %LOCALAPPDATA%\\Da Capo ; macOS : ~/Library/Application Support/Da Capo ;
    Linux : $XDG_STATE_HOME/Da Capo (~/.local/state/Da Capo). Depuis les sources :
    le dossier du dépôt.
    """
    ici = Path(__file__).resolve().parent
    python = ici.parent / "python"
    installe = (python / "python.exe").exists() or (python / "bin" / "python3").exists()
    if not installe:
        base = ici
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / NOM
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / NOM
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / NOM
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path.home()
    return base


def _demarrer_rapports() -> None:
    dossier = _dossier_donnees()
    trace_native = dossier / "_crash_natif.log"
    # La trace de la session précédente est relevée AVANT de rouvrir le
    # fichier : l'ouverture en écriture le vide.
    try:
        import reporting
        from dacapo import __version__
        reporting.init(dossier, application="dacapo", version=__version__)
        reporting.relever_crash_natif(trace_native)
        reporting.reprendre_file_en_fond()
    except Exception:
        pass
    try:
        import faulthandler
        global _fichier_faulthandler
        _fichier_faulthandler = open(trace_native, "w", encoding="utf-8")
        faulthandler.enable(file=_fichier_faulthandler, all_threads=True)
    except Exception:
        pass


def _demander_accord(win) -> None:
    try:
        import reporting
        from PyQt6 import QtWidgets
        premier = reporting.consentement() is None
        if premier:
            boite = QtWidgets.QMessageBox(win)
            boite.setWindowTitle(NOM)
            boite.setIcon(QtWidgets.QMessageBox.Icon.Question)
            from dacapo.i18n import tr
            boite.setText(tr("accord.titre"))
            boite.setInformativeText(tr("accord.texte"))
            oui = boite.addButton(tr("dlg.oui"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            boite.addButton(tr("dlg.non"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
            boite.exec()
            reporting.definir_consentement(boite.clickedButton() is oui)
            win.act_autoreport.setChecked(reporting.consentement() is True)
        reporting.signaler_demarrage(premier=premier)
    except Exception:
        pass


def _rapport_crash(exc: BaseException) -> None:
    """Une application fenêtrée n'a pas de console : sans ce filet, une erreur
    au démarrage fermerait le programme sans rien montrer."""
    import datetime
    import traceback
    texte = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    entete = f"{NOM} — erreur au démarrage — {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n"
    chemin = _dossier_donnees() / "dacapo-erreur.log"
    try:
        with open(chemin, "a", encoding="utf-8") as fh:
            fh.write(entete + texte + "\n")
    except OSError:
        chemin = "(journal impossible à écrire)"
    sys.stderr.write(entete + texte)
    try:
        import reporting
        reporting.signaler_plantage(texte)
    except Exception:
        pass
    try:
        from PyQt6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from dacapo.i18n import tr
        QtWidgets.QMessageBox.critical(
            None, NOM, tr("demarrage.echec", erreur=f"{type(exc).__name__}: {exc}", chemin=chemin))
    except Exception:
        pass


def _verifier() -> int:
    """--check : l'application et ses dépendances se chargent (lancé par la
    construction des paquets avec l'interpréteur embarqué ; aucune fenêtre)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
        import interface_kit  # noqa: F401
        import reporting  # noqa: F401
        import updater  # noqa: F401
        from dacapo import fenetre, inventaire, musicxml, pilote, style, travail  # noqa: F401
        style.appliquer(app)
        del app
    except Exception as exc:
        print(f"Da Capo : ECHEC / FAILED -- {type(exc).__name__}: {exc}")
        return 1
    print("Da Capo : OK")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return _verifier()
    from dacapo.i18n import definir_langue, tr
    ap = argparse.ArgumentParser(description=tr("cli.description"))
    ap.add_argument("dossiers", nargs="*", help="score folders / dossiers de partitions")
    ap.add_argument("--lang", choices=["fr", "en"], help="interface language / langue")
    from dacapo import __version__
    ap.add_argument("--version", action="version", version=f"Da Capo {__version__}")
    args = ap.parse_args()
    definir_langue(args.lang)

    _demarrer_rapports()
    from PyQt6 import QtCore, QtGui, QtWidgets
    from dacapo.fenetre import FenetrePrincipale

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(NOM)
    # Langue : choix du menu Langue s'il existe, sinon détection automatique.
    if not args.lang:
        choix = QtCore.QSettings("ARP273-ROSE", NOM).value("langue", "auto", type=str)
        definir_langue(choix if choix in ("fr", "en") else None)
    from dacapo import style
    style.appliquer(app)            # apparence figée, indépendante du thème Windows
    # Linux : la boîte « native » passe par le portail XDG et se réduit souvent
    # à une liste ; on impose la boîte COMPLÈTE de Qt (barre latérale avec
    # dossier personnel, Documents, Téléchargements, supports montés ;
    # arborescence, création de dossier), au style de l'application (kit
    # commun, interface_kit). Windows et macOS gardent leur boîte native.
    try:
        import interface_kit
        interface_kit.installer_dialogues_fichiers()
    except Exception:
        pass
    # Verrou nommé lu par l'installeur Inno (AppMutex = <nom_fichier>EnCours).
    if sys.platform == "win32":
        try:
            import ctypes
            app._mutex_installeur = ctypes.windll.kernel32.CreateMutexW(None, False, f"{NOM}EnCours")
        except Exception:
            pass
    icone = Path(__file__).resolve().parent / "logo.png"
    if icone.exists():
        app.setWindowIcon(QtGui.QIcon(str(icone)))

    win = FenetrePrincipale()
    win.show()
    if args.dossiers:
        win.ajouter_sources(args.dossiers)

    QtCore.QTimer.singleShot(1200, lambda: _demander_accord(win))
    try:
        import updater
        if updater.is_packaged():
            QtCore.QTimer.singleShot(3000, lambda: win._check_update(manual=False))
    except Exception:
        pass
    try:
        import reporting
        vigie = reporting.Vigie(seuil=10.0, periode=2.0)
        vigie.demarrer()
        minuteur = QtCore.QTimer(win)
        minuteur.timeout.connect(vigie.battre)
        minuteur.start(2000)
        win._vigie, win._vigie_timer = vigie, minuteur
    except Exception:
        pass
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as _exc:          # noqa: BLE001 — filet volontaire
        _rapport_crash(_exc)
        sys.exit(1)
