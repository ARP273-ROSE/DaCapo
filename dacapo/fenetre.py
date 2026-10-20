"""Fenêtre de Da Capo : quatre étapes, un bouton.

Règle d'or (comme Tutti) : le fil graphique ne touche jamais un fichier ni
Finale. Recherche des partitions, export et diagnostic tournent dans des fils
de fond qui ne parlent à Qt que par signaux : la fenêtre reste vivante
pendant des heures d'export.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from . import __version__, finale, inventaire, musescore, travail, win32
from .i18n import langue, tr


class Signaux(QtCore.QObject):
    trouves = QtCore.pyqtSignal(int, object)          # (génération, couples)
    evenement = QtCore.pyqtSignal(object)             # travail.Evenement
    fini = QtCore.pyqtSignal(object)                  # message d'erreur ou None
    diagnostic = QtCore.pyqtSignal(str, bool)         # (relevé, tout reconnu)


class ListeDossiers(QtWidgets.QListWidget):
    """Liste de dossiers qui accepte un glisser-déposer depuis l'Explorateur."""
    deposes = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setMinimumHeight(64)
        self.setMaximumHeight(104)          # 1 à 3 dossiers en général

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        chemins = [u.toLocalFile() for u in ev.mimeData().urls() if u.isLocalFile()]
        ev.acceptProposedAction()
        if chemins:
            self.deposes.emit(chemins)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if self.count() == 0:
            p = QtGui.QPainter(self.viewport())
            p.setPen(self.palette().color(QtGui.QPalette.ColorRole.PlaceholderText))
            p.drawText(self.viewport().rect().adjusted(12, 6, -12, -6),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), tr("sources.vide"))
            p.end()


class FenetrePrincipale(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("fenetre.titre", version=__version__))
        self.resize(820, 900)
        self.reglages = QtCore.QSettings("ARP273-ROSE", "DaCapo")
        self.signaux = Signaux()
        self.signaux.trouves.connect(self._recevoir_partitions)
        self.signaux.evenement.connect(self._evenement)
        self.signaux.fini.connect(self._fin)
        self.signaux.diagnostic.connect(self._fin_diagnostic)
        self.couples: list = []
        self._generation = 0
        self.en_cours = False
        self._arret = threading.Event()
        self.finales = finale.detecter() if win32.DISPONIBLE else []
        self.mscore = musescore.trouver()
        self._construire()
        self._construire_menus()
        for d in self.reglages.value("sources", [], type=list) or []:
            if Path(d).is_dir():
                self._ajouter_item(d)
        self._chercher()
        self._majeur()

    # ------------------------------------------------------------ interface
    def _construire(self):
        # Contenu dans une zone défilante : sur un petit écran ou en mise à
        # l'échelle 150 %, rien ne se chevauche, on fait défiler.
        # La barre du bas (avertissement, progression, boutons) reste toujours
        # visible, hors de la zone qui défile.
        fond = QtWidgets.QWidget()
        fond.setObjectName("central")
        self.setCentralWidget(fond)
        principal = QtWidgets.QVBoxLayout(fond)
        principal.setContentsMargins(0, 0, 0, 0)
        principal.setSpacing(0)
        defile = QtWidgets.QScrollArea()
        defile.setWidgetResizable(True)
        defile.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        central = QtWidgets.QWidget()
        central.setObjectName("central")
        defile.setWidget(central)
        principal.addWidget(defile, 1)
        g = QtWidgets.QVBoxLayout(central)

        entete = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        chemin_logo = Path(__file__).resolve().parent.parent / "logo_64.png"
        if chemin_logo.exists():
            logo.setPixmap(QtGui.QPixmap(str(chemin_logo)).scaled(
                52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        entete.addWidget(logo)
        textes = QtWidgets.QVBoxLayout()
        titre = QtWidgets.QLabel("Da Capo")
        titre.setObjectName("titre")
        textes.addWidget(titre)
        sous = QtWidgets.QLabel(tr("entete.sous_titre"))
        sous.setObjectName("sous_titre")
        sous.setWordWrap(True)
        textes.addWidget(sous)
        entete.addLayout(textes, 1)
        g.addLayout(entete)

        # 1. sources
        b1 = QtWidgets.QGroupBox(tr("etape.sources"))
        l1 = QtWidgets.QVBoxLayout(b1)
        ligne = QtWidgets.QHBoxLayout()
        self.liste = ListeDossiers()
        self.liste.deposes.connect(self.ajouter_sources)
        self.liste.itemSelectionChanged.connect(self._majeur)
        ligne.addWidget(self.liste, 1)
        colonne = QtWidgets.QVBoxLayout()
        self.b_ajouter = QtWidgets.QPushButton(tr("sources.ajouter"))
        self.b_ajouter.clicked.connect(self._choisir_source)
        self.b_retirer = QtWidgets.QPushButton(tr("sources.retirer"))
        self.b_retirer.clicked.connect(self._retirer_source)
        colonne.addWidget(self.b_ajouter)
        colonne.addWidget(self.b_retirer)
        colonne.addStretch(1)
        ligne.addLayout(colonne)
        l1.addLayout(ligne, 1)
        self.l_trouves = QtWidgets.QLabel("")
        self.l_trouves.setObjectName("resume")
        l1.addWidget(self.l_trouves)
        g.addWidget(b1)

        # 2. dossier de travail
        b2 = QtWidgets.QGroupBox(tr("etape.travail"))
        l2 = QtWidgets.QGridLayout(b2)
        self.e_travail = QtWidgets.QLineEdit()
        self.e_travail.setReadOnly(True)
        defaut = Path.home() / "Documents" / tr("travail.defaut")
        self.e_travail.setText(self.reglages.value("travail", str(defaut), type=str))
        b = QtWidgets.QPushButton(tr("travail.choisir"))
        b.clicked.connect(self._choisir_travail)
        note = QtWidgets.QLabel(tr("travail.note"))
        note.setWordWrap(True)
        note.setObjectName("note")
        l2.addWidget(self.e_travail, 0, 0)
        l2.addWidget(b, 0, 1)
        l2.addWidget(note, 1, 0, 1, 2)
        l2.setColumnStretch(0, 1)
        g.addWidget(b2)

        # 3. Finale
        b3 = QtWidgets.QGroupBox(tr("etape.finale"))
        l3 = QtWidgets.QGridLayout(b3)
        self.cb_finale = QtWidgets.QComboBox()
        for i, f in enumerate(self.finales):
            cle = "finale.recommande" if i == 0 else "finale.option"
            self.cb_finale.addItem(tr(cle, nom=f.nom, xml=tr(f.musicxml)), i)
        self.b_diag = QtWidgets.QPushButton(tr("finale.diagnostic"))
        self.b_diag.setToolTip(tr("finale.diagnostic.astuce"))
        self.b_diag.clicked.connect(self._diagnostic)
        self.l_finale = QtWidgets.QLabel("")
        self.l_finale.setWordWrap(True)
        self.l_finale.setObjectName("note")
        if not win32.DISPONIBLE:
            self.l_finale.setText(tr("finale.pas_windows"))
        elif not self.finales:
            self.l_finale.setText(tr("finale.aucun"))
        l3.addWidget(self.cb_finale, 0, 0)
        l3.addWidget(self.b_diag, 0, 1)
        l3.addWidget(self.l_finale, 1, 0, 1, 2)
        l3.setColumnStretch(0, 1)
        self.cb_finale.setVisible(bool(self.finales))
        self.b_diag.setVisible(bool(self.finales))
        self.l_finale.setVisible(bool(self.l_finale.text()))
        g.addWidget(b3)

        # 4. options
        b4 = QtWidgets.QGroupBox(tr("etape.options"))
        l4 = QtWidgets.QVBoxLayout(b4)
        self.c_xml = QtWidgets.QCheckBox(tr("options.musicxml"))
        self.c_xml.setChecked(True)
        self.c_xml.setEnabled(False)
        self.c_pdf = QtWidgets.QCheckBox(tr("options.pdf"))
        self.c_pdf.setToolTip(tr("options.pdf.astuce"))
        self.c_pdf.setChecked(self.reglages.value("pdf", True, type=bool))
        self.c_ms = QtWidgets.QCheckBox(tr("options.musescore"))
        self.c_ms.setChecked(bool(self.mscore) and self.reglages.value("musescore", True, type=bool))
        self.c_ms.setEnabled(bool(self.mscore))
        for c in (self.c_xml, self.c_pdf, self.c_ms):
            l4.addWidget(c)
        if not self.mscore:
            absent = QtWidgets.QLabel(tr("options.musescore_absent"))
            absent.setWordWrap(True)
            absent.setObjectName("note")
            l4.addWidget(absent)
        g.addWidget(b4)

        g.addStretch(1)
        # bas : avertissement, progression, boutons (hors défilement)
        pied = QtWidgets.QWidget()
        g = QtWidgets.QVBoxLayout(pied)
        g.setContentsMargins(9, 4, 9, 9)
        principal.addWidget(pied)
        self.l_avert = QtWidgets.QLabel(tr("avertissement"))
        self.l_avert.setWordWrap(True)
        self.l_avert.setObjectName("avertissement")
        g.addWidget(self.l_avert)
        self.barre = QtWidgets.QProgressBar()
        self.barre.hide()
        g.addWidget(self.barre)
        self.l_etat = QtWidgets.QLabel("")
        self.l_etat.setObjectName("resume")
        self.l_etat.setWordWrap(True)
        g.addWidget(self.l_etat)
        bas = QtWidgets.QHBoxLayout()
        self.b_rapport = QtWidgets.QPushButton(tr("bouton.rapport"))
        self.b_rapport.clicked.connect(lambda: self._ouvrir(self._travail() / "rapport.html"))
        self.b_dossier = QtWidgets.QPushButton(tr("bouton.dossier"))
        self.b_dossier.clicked.connect(lambda: self._ouvrir(self._travail()))
        bas.addWidget(self.b_rapport)
        bas.addWidget(self.b_dossier)
        bas.addStretch(1)
        self.b_go = QtWidgets.QPushButton(tr("bouton.commencer"))
        self.b_go.setObjectName("principal")
        self.b_go.setMinimumHeight(46)
        self.b_go.setMinimumWidth(210)
        f = self.b_go.font()
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        f.setPointSizeF(f.pointSizeF() * 1.25)
        self.b_go.setFont(f)
        self.b_go.clicked.connect(self._commencer_ou_arreter)
        bas.addWidget(self.b_go)
        g.addLayout(bas)
        self.statusBar()

    # ------------------------------------------------------------ sources
    def _ajouter_item(self, d: str):
        if any(self.liste.item(i).text() == d for i in range(self.liste.count())):
            return
        it = QtWidgets.QListWidgetItem(self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_DirIcon), d)
        self.liste.addItem(it)

    def sources(self) -> list[str]:
        return [self.liste.item(i).text() for i in range(self.liste.count())]

    def ajouter_sources(self, chemins):
        for c in chemins:
            p = Path(c)
            if p.is_file():
                p = p.parent
            if p.is_dir():
                self._ajouter_item(str(p))
        self._chercher()

    def _choisir_source(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, tr("dlg.choisir_sources"), self.sources()[-1] if self.sources() else str(Path.home()))
        if d:
            self.ajouter_sources([d])

    def _retirer_source(self):
        for it in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(it))
        self._chercher()

    def _chercher(self):
        """Recherche des partitions en fond ; seule la dernière demande compte."""
        self.reglages.setValue("sources", self.sources())
        self._generation += 1
        gen, racines = self._generation, self.sources()
        self.couples = []
        self.l_trouves.setText(tr("sources.recherche") if racines else "")
        self._majeur()
        if not racines:
            return

        def fond():
            trouves = inventaire.chercher(racines, annule=lambda: gen != self._generation)
            self.signaux.trouves.emit(gen, trouves)
        threading.Thread(target=fond, daemon=True, name="dacapo-recherche").start()

    def _recevoir_partitions(self, gen, couples):
        if gen != self._generation:
            return
        self.couples = couples
        if couples:
            mus = sum(1 for _, f in couples if f.suffix.lower() == ".mus")
            self.l_trouves.setText(tr("sources.trouvees", n=len(couples), mus=mus, musx=len(couples) - mus))
        else:
            self.l_trouves.setText(tr("sources.aucune"))
        self._majeur()

    # ------------------------------------------------------------ travail
    def _travail(self) -> Path:
        return Path(self.e_travail.text())

    def _choisir_travail(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, tr("dlg.choisir_travail"),
                                                       str(self._travail().parent))
        if d:
            self.e_travail.setText(d)
            self.reglages.setValue("travail", d)
            self._majeur()

    def finale_choisi(self):
        i = self.cb_finale.currentData()
        return self.finales[i] if i is not None and self.finales else None

    def _majeur(self):
        libre = not self.en_cours
        for w in (self.liste, self.b_ajouter, self.cb_finale, self.c_pdf):
            w.setEnabled(libre)
        self.c_ms.setEnabled(libre and bool(self.mscore))
        self.b_retirer.setEnabled(libre and bool(self.liste.selectedItems()))
        self.b_diag.setEnabled(libre and bool(self.couples))
        deja = (self._travail() / "_dacapo" / "journal.json").exists()
        self.b_go.setText(tr("bouton.arreter") if self.en_cours else
                          tr("bouton.reprendre" if deja else "bouton.commencer"))
        self.b_go.setEnabled(self.en_cours or bool(self.couples))
        self.b_rapport.setEnabled((self._travail() / "rapport.html").exists())
        self.b_dossier.setEnabled(self._travail().exists())

    def _ouvrir(self, chemin: Path):
        if chemin.exists():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(chemin)))

    def _commencer_ou_arreter(self):
        if self.en_cours:
            self._arret.set()
            self.b_go.setEnabled(False)
            self.b_go.setText(tr("bouton.arret"))
            return
        cible = self._travail()
        try:
            cible.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, "Da Capo", tr("phase.dossier_ecriture",
                                                              detail=e.strerror or str(e)))
            return
        self.reglages.setValue("travail", str(cible))
        self.reglages.setValue("pdf", self.c_pdf.isChecked())
        self.reglages.setValue("musescore", self.c_ms.isChecked())
        options = travail.Options(musicxml=True, pdf=self.c_pdf.isChecked(),
                                  musescore=self.c_ms.isChecked())
        f = self.finale_choisi()
        fabrique = None
        if f is not None:
            from .pilote import PiloteFinale
            fabrique = lambda: PiloteFinale(f)          # noqa: E731
        couples = list(self.couples)
        mscore = self.mscore if options.musescore else None
        self.en_cours = True
        self._arret.clear()
        self.barre.setRange(0, 0)
        self.barre.show()
        self._majeur()

        def fond():
            win32.empecher_veille(True)
            try:
                travail.executer(cible, couples, options, pilote=fabrique, mscore=mscore,
                                 rappel=self.signaux.evenement.emit, annule=self._arret.is_set)
                self.signaux.fini.emit(None)
            except RuntimeError as e:
                self.signaux.fini.emit(tr("phase.demarrage_finale") if "finale_demarrage" in str(e)
                                       else str(e))
            except OSError as e:
                self.signaux.fini.emit(tr("phase.dossier_ecriture", detail=e.strerror or str(e)))
            except Exception as e:
                self.signaux.fini.emit(f"{type(e).__name__}: {e}")
                raise
            finally:
                win32.empecher_veille(False)
        threading.Thread(target=fond, daemon=True, name="dacapo-export").start()

    def _evenement(self, e):
        if e.total:
            self.barre.setRange(0, e.total)
            self.barre.setValue(e.fait)
        cle = {"copie": "phase.copie", "finale": "phase.finale", "musescore": "phase.musescore",
               "rapport": "phase.rapport"}.get(e.phase)
        if cle:
            self.l_etat.setText(tr(cle, nom=e.nom or "…") + (f"  ({e.fait}/{e.total})" if e.total else ""))

    def _fin(self, erreur):
        self.en_cours = False
        self.barre.hide()
        j = inventaire.Journal(self._travail())
        rels = {travail.rel_posix(r, f) for r, f in self.couples}
        fiches = [x for k, x in j.fiches.items() if k in rels]
        ok = sum(1 for x in fiches if x.fait("musicxml"))
        echecs = sum(1 for x in fiches if x.etats.get("musicxml") == "echec")
        if erreur:
            self.l_etat.setText(erreur)
            QtWidgets.QMessageBox.warning(self, "Da Capo", erreur)
        elif self._arret.is_set():
            self.l_etat.setText(tr("phase.arrete"))
        else:
            self.l_etat.setText(tr("phase.fini", ok=ok, n=len(fiches), echecs=echecs))
        self._majeur()

    # ------------------------------------------------------------ diagnostic
    def _diagnostic(self):
        f = self.finale_choisi()
        if f is None or not self.couples:
            QtWidgets.QMessageBox.information(self, tr("diag.titre"), tr("diag.sans_partition"))
            return
        racine, premiere = self.couples[0]
        QtWidgets.QMessageBox.information(self, tr("diag.titre"), tr("diag.encours", nom=premiere.name))
        cible = self._travail()
        self.en_cours = True
        self._majeur()

        def fond():
            texte, complet = "", False
            try:
                rel = "_diagnostic/" + premiere.name
                fiche = inventaire.Fiche(rel=rel, source=str(premiere))
                copie = inventaire.copier(premiere, cible / "_dacapo", rel, fiche)
                from .pilote import PiloteFinale
                texte = PiloteFinale(f).diagnostic(copie)
                complet = "NON TROUVÉ" not in texte and "ÉCHEC" not in texte
            except Exception as e:
                texte = f"{type(e).__name__}: {e}"
            self.signaux.diagnostic.emit(texte, complet)
        threading.Thread(target=fond, daemon=True, name="dacapo-diagnostic").start()

    def _fin_diagnostic(self, texte, complet):
        self.en_cours = False
        self._majeur()
        chemin = self._travail() / "_dacapo" / "diagnostic-finale.txt"
        try:
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(texte, encoding="utf-8")
        except OSError:
            pass
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(tr("diag.titre"))
        dlg.resize(760, 520)
        lo = QtWidgets.QVBoxLayout(dlg)
        conclusion = QtWidgets.QLabel(tr("diag.resultat_ok" if complet else "diag.resultat_ko"))
        conclusion.setWordWrap(True)
        lo.addWidget(conclusion)
        zone = QtWidgets.QPlainTextEdit(texte)
        zone.setReadOnly(True)
        zone.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lo.addWidget(zone, 1)
        lo.addWidget(QtWidgets.QLabel(tr("diag.enregistre", chemin=chemin)))
        btns = QtWidgets.QDialogButtonBox()
        envoyer = btns.addButton(tr("diag.envoyer"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        btns.addButton(tr("dlg.fermer"), QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        btns.rejected.connect(dlg.reject)

        def envoi():
            try:
                import reporting
                accord = reporting.consentement()
                if accord is not True:
                    reporting.definir_consentement(True)
                morceaux = {f"releve_{i + 1}": texte[i * 7000:(i + 1) * 7000]
                            for i in range(min(8, (len(texte) + 6999) // 7000))}
                reporting.envoyer("diagnostic_finale", version=__version__, **morceaux)
                if accord is not True:
                    reporting.definir_consentement(bool(accord))
                QtWidgets.QMessageBox.information(dlg, tr("diag.titre"), tr("diag.envoye"))
            except Exception:
                pass
        envoyer.clicked.connect(envoi)
        lo.addWidget(btns)
        dlg.exec()

    # ------------------------------------------------------------ menus
    def _construire_menus(self):
        m = self.menuBar().addMenu(tr("menu.fichier"))
        m.addAction(tr("sources.ajouter"), self._choisir_source).setShortcut("Ctrl+O")
        m.addSeparator()
        m.addAction(tr("menu.quitter"), self.close).setShortcut("Ctrl+Q")

        lg = self.menuBar().addMenu(tr("menu.langue"))
        groupe = QtGui.QActionGroup(self)
        choisie = self.reglages.value("langue", "auto", type=str)
        for code, libelle in (("auto", tr("menu.langue.auto")), ("fr", "Français"), ("en", "English")):
            act = lg.addAction(libelle)
            act.setCheckable(True)
            act.setChecked(code == choisie)
            act.triggered.connect(lambda _=False, c=code: self._changer_langue(c))
            groupe.addAction(act)

        aide = self.menuBar().addMenu(tr("menu.aide"))
        aide.addAction(tr("menu.manuel"), self._ouvrir_manuel).setShortcut("F1")
        aide.addAction(tr("menu.mode_emploi"), self._afficher_aide)
        aide.addSeparator()
        aide.addAction(tr("menu.maj"), lambda: self._check_update(manual=True))
        aide.addAction(tr("menu.signaler"), self._signaler_probleme)
        self.act_autoreport = aide.addAction(tr("menu.rapports_auto"))
        self.act_autoreport.setCheckable(True)
        try:
            import reporting
            self.act_autoreport.setChecked(reporting.consentement() is True)
        except Exception:
            self.act_autoreport.setEnabled(False)
        self.act_autoreport.toggled.connect(self._basculer_rapports)
        aide.addSeparator()
        aide.addAction(tr("menu.a_propos"), self._a_propos)

    def closeEvent(self, ev):
        if self.en_cours:
            r = QtWidgets.QMessageBox.question(self, "Da Capo", tr("quitter.en_cours"))
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                ev.ignore()
                return
            self._arret.set()
        super().closeEvent(ev)

    # ------------------------------------------------------------ aide
    def _afficher_aide(self):
        QtWidgets.QMessageBox.information(self, tr("aide.titre"), tr("aide.texte"))

    def _ouvrir_manuel(self):
        """Manuel PDF dans la langue de l'interface (docs/manuel-fr.pdf, -en.pdf)."""
        docs = Path(__file__).resolve().parent.parent / "docs"
        for nom in (f"manuel-{langue()}.pdf", "manuel-en.pdf", "manuel-fr.pdf"):
            if (docs / nom).exists():
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(docs / nom)))
                return
        QtWidgets.QMessageBox.information(self, "Da Capo", tr("manuel.absent"))

    def _changer_langue(self, code: str):
        self.reglages.setValue("langue", code)
        QtWidgets.QMessageBox.information(self, "Da Capo", tr("menu.langue.redemarrer"))

    def _a_propos(self):
        # le logo est le même fichier que l'icône (une seule source : logo.svg)
        boite = QtWidgets.QMessageBox(self)
        boite.setWindowTitle(tr("menu.a_propos"))
        logo = Path(__file__).resolve().parent.parent / "logo_128.png"
        if logo.exists():
            boite.setIconPixmap(QtGui.QPixmap(str(logo)))
        boite.setText(tr("a_propos.texte", version=__version__))
        boite.exec()

    def _basculer_rapports(self, coche: bool):
        try:
            import reporting
            reporting.definir_consentement(bool(coche))
        except Exception:
            pass

    # ------------------------------------------------------------ mise à jour
    # Dispositif du kit Windows (identique à MusicOthèque, Anticythere3D…) :
    # archive ZIP déballée par le programme, jamais d'exécutable téléchargé.
    _maj_signal = QtCore.pyqtSignal(object, bool)

    def _check_update(self, manual: bool = False):
        if not hasattr(self, "_maj_branche"):
            self._maj_signal.connect(self._update_result)
            self._maj_branche = True
        if manual:
            self.statusBar().showMessage(tr("maj.recherche"))

        def worker():
            try:
                import updater
                info = updater.check(__version__)
            except Exception:
                info = None
            self._maj_signal.emit(info, manual)

        threading.Thread(target=worker, daemon=True, name="dacapo-maj").start()

    def _update_result(self, info, manual: bool):
        self.statusBar().clearMessage()
        if not info:
            if manual:
                QtWidgets.QMessageBox.information(
                    self, tr("maj.titre"), tr("maj.a_jour", version=__version__))
            return
        try:
            import updater
            installe = bool(updater.is_packaged())
            page = f"https://github.com/{updater.REPO}/releases/latest"
        except Exception:
            installe, page = False, ""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(tr("maj.titre"))
        box.setText(tr("maj.dispo", nouvelle=info["version"], version=__version__))
        notes = (info.get("notes") or "").strip()
        try:
            import updater
            notes = updater.notes_dans_la_langue(notes, langue())
        except Exception:
            pass
        if notes:
            box.setDetailedText(notes[:4000])
        oui = box.addButton(tr("maj.installer") if installe else tr("maj.page"),
                            QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("maj.plus_tard"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not oui:
            return
        if not installe:
            if page:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(page))
            return
        self._telecharger_maj(info)

    def _telecharger_maj(self, info: dict):
        import updater
        dlg = QtWidgets.QProgressDialog(tr("maj.telechargement"), None, 0, 100, self)
        dlg.setWindowTitle(tr("maj.titre"))
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        etat = {"fait": 0, "total": 0, "fini": False, "erreur": None, "pose": False}

        def _prog(done, total):
            etat["fait"], etat["total"] = done, total

        def worker():
            try:
                etat["pose"] = bool(updater.download_and_apply(info, progress=_prog))
            except Exception as exc:
                etat["erreur"] = exc
            finally:
                etat["fini"] = True

        threading.Thread(target=worker, daemon=True, name="dacapo-maj-pose").start()
        poll = QtCore.QTimer(self)
        poll.setInterval(100)

        def tick():
            if not etat["fini"]:
                if etat["total"] > 0:
                    dlg.setValue(min(99, etat["fait"] * 100 // etat["total"]))
                return
            poll.stop()
            dlg.close()
            if etat["erreur"] is not None or not etat["pose"]:
                texte = str(etat["erreur"] or "archive invalide")
                verrou = ("WinError 32" in texte or "used by another process" in texte
                          or isinstance(etat["erreur"], PermissionError))
                QtWidgets.QMessageBox.warning(
                    self, tr("maj.titre"),
                    tr("maj.verrou") if verrou else tr("maj.echec", erreur=texte))
                return
            QtWidgets.QMessageBox.information(self, tr("maj.titre"), tr("maj.redemarre"))
            try:
                updater.restart()
            finally:
                QtWidgets.QApplication.quit()

        poll.timeout.connect(tick)
        poll.start()
        self._maj_poll = poll

    # ------------------------------------------------------------ rapports
    def _signaler_probleme(self):
        try:
            import reporting
        except Exception:
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(tr("signal.titre"))
        dlg.resize(560, 360)
        lo = QtWidgets.QVBoxLayout(dlg)
        lo.addWidget(QtWidgets.QLabel(tr("signal.invite")))
        texte = QtWidgets.QPlainTextEdit()
        texte.setPlaceholderText(tr("signal.exemple"))
        lo.addWidget(texte)
        note = QtWidgets.QLabel(tr("signal.note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        lo.addWidget(note)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                          | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(tr("signal.envoyer"))
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lo.addWidget(btns)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        description = texte.toPlainText().strip()
        if not description:
            return
        accord = reporting.consentement()
        if accord is not True:
            reporting.definir_consentement(True)
        rapport = reporting.envoyer("manuel", description=description, version=__version__,
                                    partitions=len(self.couples))
        if accord is not True:
            reporting.definir_consentement(bool(accord))
        chemin = None
        try:
            chemin = reporting.paquet_local(rapport, None)
        except Exception:
            pass
        msg = (tr("signal.parti") if rapport.get("transmis", True) and not chemin
               else tr("signal.local", chemin=chemin))
        QtWidgets.QMessageBox.information(self, tr("signal.merci"), msg)
