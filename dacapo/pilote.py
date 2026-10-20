"""Piloter Finale comme le ferait une personne, partition après partition.

Pour chaque fichier : Fichier → Ouvrir, puis l'export MusicXML (et, si
demandé, un PDF de référence), puis Fichier → Fermer sans enregistrer. Les
commandes sont trouvées dans la barre de menus PAR LEUR LIBELLÉ, en français
comme en anglais, quelle que soit la version :

    Finale 2003 à 2010  Fichier → MusicXML → Exporter…  (Dolet Light)
    Finale 2011 à 2014  Fichier → MusicXML → Exporter…  (Dolet 6/7)
    Finale 25 à 27      Fichier → Exporter → MusicXML…  (intégré)

Le PDF de référence passe par Fichier → Exporter → PDF quand la version le
propose (Finale 25 et après), sinon par l'impression vers CutePDF Writer.

Tout imprévu est consigné : chaque boîte de dialogue rencontrée est lue
(titre, texte, boutons) avant d'être refermée. Si Finale ne répond plus,
il est arrêté et relancé, la partition est marquée en échec, et la suite
continue : une partition rebelle n'arrête pas les quatre cents autres.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import win32
from .finale import Finale
from .win32 import Entree, normaliser

EXT_MUSICXML = (".musicxml", ".xml", ".mxl")

# ----------------------------------------------------------------- menus
# Reconnaissance des commandes à partir des libellés normalisés (sans accents,
# sans « … », en minuscules). Fonctions pures : testées sans Windows.

MOTS_DOSSIER = ("dossier", "folder", "traduire", "translate", "lot", "batch")


def _derniere(e: Entree) -> str:
    return e.chemin[-1] if e.chemin else ""


def entree_ouvrir(entrees: list[Entree]) -> Entree | None:
    return next((e for e in entrees if len(e.chemin) == 2 and _derniere(e) in ("ouvrir", "open")),
                None)


def entree_fermer(entrees: list[Entree]) -> Entree | None:
    return next((e for e in entrees if len(e.chemin) == 2 and _derniere(e) in ("fermer", "close")),
                None)


def entree_export_xml(entrees: list[Entree]) -> Entree | None:
    """« … MusicXML … Exporter » ou « … Exporter … MusicXML », jamais
    l'import ni la traduction d'un dossier entier ; la forme non compressée
    (.musicxml / .xml) est préférée à la compressée (.mxl)."""
    candidats = []
    for e in entrees:
        tout = " / ".join(e.chemin)
        if "musicxml" not in tout or "export" not in tout:
            continue
        if "import" in _derniere(e) or any(m in tout for m in MOTS_DOSSIER):
            continue
        compresse = "compress" in _derniere(e) or "mxl" in _derniere(e)
        candidats.append((compresse, len(e.chemin), e))
    candidats.sort(key=lambda t: (t[0], t[1]))
    return candidats[0][2] if candidats else None


def entree_export_pdf(entrees: list[Entree]) -> Entree | None:
    return next((e for e in entrees if "export" in " / ".join(e.chemin[:-1])
                 and _derniere(e).startswith("pdf")), None)


def entree_imprimer(entrees: list[Entree]) -> Entree | None:
    return next((e for e in entrees if len(e.chemin) == 2
                 and _derniere(e) in ("imprimer", "print")), None)


def entree_quitter(entrees: list[Entree]) -> Entree | None:
    return next((e for e in entrees if len(e.chemin) == 2
                 and _derniere(e) in ("quitter", "exit", "quit")), None)


# Boutons à presser devant une boîte imprévue, par ordre de préférence. Une
# question « Enregistrer les modifications ? » reçoit toujours NON.
BOUTONS_ENREGISTRER_NON = ("non", "no", "ne pas enregistrer", "don't save", "dont save")
BOUTONS_PREFERES = ("plus tard", "later", "continuer", "continue", "ok", "oui", "yes",
                    "ignorer", "ignore", "fermer", "close", "terminer", "finish",
                    "non", "no", "annuler", "cancel")


def question_enregistrer(message: str) -> bool:
    m = normaliser(message)
    return ("enregistr" in m or "save" in m or "sauvegard" in m) and (
        "modif" in m or "change" in m or "?" in m)


def bouton_pour(d: win32.Dialogue):
    if question_enregistrer(d.message):
        b = d.bouton(*BOUTONS_ENREGISTRER_NON)
        if b:
            return b
    return d.bouton(*BOUTONS_PREFERES)


def trouver_produit(dossier: Path, stem: str, depuis: float, extensions=EXT_MUSICXML) -> Path | None:
    """Le fichier qu'a écrit Finale, même s'il a ajouté sa propre extension
    (« X.musicxml.xml ») : le plus récent du dossier dont le nom commence
    par `stem`, écrit après `depuis`."""
    meilleurs = []
    try:
        for p in dossier.iterdir():
            if p.is_file() and p.name.lower().startswith(stem.lower()) \
                    and p.suffix.lower() in extensions and p.stat().st_mtime >= depuis - 2:
                meilleurs.append((p.stat().st_mtime, p))
    except OSError:
        return None
    return max(meilleurs)[1] if meilleurs else None


# ----------------------------------------------------------------- pilote

class FinaleBloque(Exception):
    """Finale ne répond plus ou une étape a dépassé son délai."""


@dataclass
class Delais:
    demarrage: float = 120.0
    ouverture: float = 180.0
    export: float = 600.0       # une grosse partition d'orchestre peut être longue
    fermeture: float = 60.0
    boite: float = 30.0


class PiloteFinale:
    def __init__(self, finale: Finale, journal: Callable[[str], None] | None = None,
                 delais: Delais | None = None):
        if not win32.DISPONIBLE:
            raise RuntimeError("Windows requis")
        self.finale = finale
        self.delais = delais or Delais()
        self.proc: subprocess.Popen | None = None
        self.fenetre = None
        self.entrees: list[Entree] = []
        self._journal = journal or (lambda t: None)
        self.imprevus: list[str] = []          # boîtes rencontrées pour la partition en cours

    # ------------------------------------------------------------ outils
    def noter(self, texte: str) -> None:
        self._journal(texte)

    @property
    def pid(self) -> int:
        return self.proc.pid if self.proc else -1

    def vivant(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _fenetre_principale(self):
        """La plus grande fenêtre visible de Finale qui porte une barre de menus."""
        meilleures = []
        for h in win32.fenetres(pid=self.pid):
            if win32.classe(h) == "#32770":
                continue
            if win32.user32.GetMenu(h):
                w, hgt = win32.taille(h)
                meilleures.append((w * hgt, h))
        return max(meilleures)[1] if meilleures else None

    def relire_menus(self) -> None:
        self.entrees = win32.menus(self.fenetre) if self.fenetre else []

    def _imprevus(self, sauf=lambda d: False) -> int:
        """Referme les boîtes inattendues de Finale ; renvoie leur nombre."""
        n = 0
        for d in win32.dialogues(pid=self.pid):
            if sauf(d):
                continue
            b = bouton_pour(d)
            self.imprevus.append(f"{d.titre} : {d.message}"[:300])
            self.noter(f"boîte imprévue — {d.description()}\n   → {b.texte if b else 'fermeture'}")
            if b:
                win32.cliquer(b.hwnd)
            else:
                win32.fermer(d.hwnd)
            n += 1
        return n

    def _attendre_boite_fichier(self, delai: float, pid: int | None = None):
        """Attend une boîte Ouvrir / Enregistrer (en traitant les autres)."""
        def cherche():
            for d in win32.dialogues(pid=pid if pid is not None else self.pid):
                if win32.champ_nom_fichier(d):
                    return d
            if pid is not None and pid != self.pid:
                return None
            self._imprevus(sauf=lambda d: win32.champ_nom_fichier(d) is not None)
            return None
        d = win32.attendre(cherche, delai, 0.3)
        if d is None:
            raise FinaleBloque("boite_fichier")
        return d

    def _commande(self, entree: Entree | None, nom: str) -> None:
        if entree is None:
            raise FinaleBloque(f"menu_absent:{nom}")
        if not self.vivant():
            raise FinaleBloque("finale_arrete")
        win32.commande(self.fenetre, entree.commande)

    # ------------------------------------------------------------ cycle de vie
    def demarrer(self) -> None:
        self.noter(f"démarrage de {self.finale.nom} ({self.finale.exe})")
        self.proc = subprocess.Popen([str(self.finale.exe)], cwd=str(self.finale.exe.parent))

        def prete():
            self._imprevus()
            return self._fenetre_principale()
        self.fenetre = win32.attendre(prete, self.delais.demarrage, 0.5)
        if not self.fenetre:
            raise FinaleBloque("demarrage")
        # Laisser Finale finir son initialisation (greffons, fenêtre de
        # lancement) puis refermer ce qui s'est ouvert.
        time.sleep(3)
        self._imprevus()
        self.relire_menus()
        self.noter(f"fenêtre « {win32.texte(self.fenetre)} », {len(self.entrees)} commandes de menu")

    def arreter(self) -> None:
        if not self.vivant():
            return
        try:
            win32.fermer(self.fenetre)
            if win32.attendre(lambda: (self._imprevus(), not self.vivant())[1], 30, 0.5):
                return
        except Exception:
            pass
        self.tuer()

    def tuer(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.noter("Finale ne répond plus : arrêt forcé")
            self.proc.kill()
            try:
                self.proc.wait(15)
            except subprocess.TimeoutExpired:
                pass
        self.fenetre = None

    # ------------------------------------------------------------ une partition
    def ouvrir(self, fichier: Path) -> None:
        self.imprevus = []
        self._commande(entree_ouvrir(self.entrees), "ouvrir")
        d = self._attendre_boite_fichier(self.delais.boite)
        win32.remplir_et_valider(d, str(fichier))
        cle = normaliser(fichier.stem)[:20]

        def ouvert():
            self._imprevus(sauf=lambda x: win32.champ_nom_fichier(x) is not None)
            return cle in normaliser(win32.texte(self.fenetre) or "")
        if not win32.attendre(ouvert, self.delais.ouverture, 0.5):
            raise FinaleBloque("ouverture")
        time.sleep(1.0)            # mise en page initiale
        self._imprevus()
        self.relire_menus()        # certaines entrées n'existent qu'avec un document ouvert

    def _enregistrer_sous(self, entree: Entree | None, nom: str, cible: Path,
                          extensions, delai: float, pid_boite: int | None = None) -> Path:
        cible.parent.mkdir(parents=True, exist_ok=True)
        depuis = time.time()
        if entree is not None:
            self._commande(entree, nom)
        d = self._attendre_boite_fichier(self.delais.boite, pid=pid_boite)
        win32.remplir_et_valider(d, str(cible))

        def produit():
            # « Remplacer le fichier existant ? » → Oui ; compte rendu → OK
            for b in win32.dialogues(pid=self.pid):
                if win32.champ_nom_fichier(b):
                    continue
                choix = b.bouton("oui", "yes", "remplacer", "replace", "ok")
                self.noter(f"pendant l'export — {b.description()}")
                self.imprevus.append(f"{b.titre} : {b.message}"[:300])
                if choix:
                    win32.cliquer(choix.hwnd)
                else:
                    win32.fermer(b.hwnd)
            if not self.vivant():
                raise FinaleBloque("finale_arrete")
            p = trouver_produit(cible.parent, cible.stem, depuis, extensions)
            if p is not None and win32_stable(p):
                return p
            return None
        p = win32.attendre(produit, delai, 1.0)
        if p is None:
            raise FinaleBloque(f"export:{nom}")
        if p != cible:
            try:
                os.replace(p, cible)
                p = cible
            except OSError:
                pass
        return p

    def exporter_musicxml(self, cible: Path) -> Path:
        return self._enregistrer_sous(entree_export_xml(self.entrees), "musicxml", cible,
                                      EXT_MUSICXML, self.delais.export)

    def exporter_pdf(self, cible: Path) -> Path:
        e = entree_export_pdf(self.entrees)
        if e is not None:
            return self._enregistrer_sous(e, "pdf", cible, (".pdf",), self.delais.export)
        return self._imprimer_vers_cutepdf(cible)

    def _imprimer_vers_cutepdf(self, cible: Path) -> Path:
        """Fichier → Imprimer, imprimante CutePDF Writer, puis la boîte
        « Enregistrer sous » de CutePDF (autre processus)."""
        self._commande(entree_imprimer(self.entrees), "imprimer")

        def boite_impression():
            for d in win32.dialogues(pid=self.pid):
                if any(c.classe == "ComboBox" for c in d.controles):
                    return d
            return None
        d = win32.attendre(boite_impression, self.delais.boite, 0.3)
        if d is None:
            raise FinaleBloque("boite_impression")
        self.noter(f"boîte d'impression — {d.description()}")
        if not any(win32.choisir_dans_liste(c.hwnd, "cutepdf")
                   for c in d.controles if c.classe == "ComboBox"):
            win32.fermer(d.hwnd)
            raise FinaleBloque("cutepdf_absent")
        time.sleep(0.5)
        ok = d.bouton("ok", "imprimer", "print") or d.par_ident(win32.IDOK)
        if ok is None:
            win32.fermer(d.hwnd)
            raise FinaleBloque("boite_impression")
        depuis = time.time()
        win32.cliquer(ok.hwnd)

        # La boîte « Enregistrer sous » vient de CutePDF, pas de Finale.
        def boite_cutepdf():
            for b in win32.dialogues():
                if b.pid != self.pid and win32.champ_nom_fichier(b):
                    return b
            return None
        b = win32.attendre(boite_cutepdf, 120, 0.5)
        if b is None:
            raise FinaleBloque("cutepdf_boite")
        cible.parent.mkdir(parents=True, exist_ok=True)
        win32.remplir_et_valider(b, str(cible))
        p = win32.attendre(lambda: trouver_produit(cible.parent, cible.stem, depuis, (".pdf",)),
                           self.delais.export, 1.0)
        if p is None or not win32_stable(p):
            raise FinaleBloque("export:pdf")
        return p

    def fermer_document(self) -> None:
        self._commande(entree_fermer(self.entrees), "fermer")
        avant = normaliser(win32.texte(self.fenetre) or "")

        def ferme():
            for d in win32.dialogues(pid=self.pid):
                b = d.bouton(*BOUTONS_ENREGISTRER_NON) or bouton_pour(d)
                if b:
                    win32.cliquer(b.hwnd)
                else:
                    win32.fermer(d.hwnd)
            return normaliser(win32.texte(self.fenetre) or "") != avant
        if not win32.attendre(ferme, self.delais.fermeture, 0.5):
            raise FinaleBloque("fermeture")
        time.sleep(0.5)

    # ------------------------------------------------------------ diagnostic
    def diagnostic(self, essai: Path | None = None) -> str:
        """Relevé complet, pour adapter Da Capo à un Finale inconnu : fenêtres,
        boîtes au démarrage, arbre des menus avant et après ouverture d'un
        document, commandes reconnues. Ne modifie rien."""
        lignes = [f"Finale : {self.finale.nom} — {self.finale.version} — {self.finale.exe}"]
        notes: list[str] = []
        ancien = self._journal
        self._journal = lambda t: (notes.append(t), ancien(t))
        try:
            try:
                self.demarrer()
            except FinaleBloque as e:
                lignes.append(f"ÉCHEC au démarrage : {e}")
                return "\n".join(lignes + notes)
            lignes.append(f"fenêtre principale : {win32.texte(self.fenetre)!r} "
                          f"classe {win32.classe(self.fenetre)}")
            lignes += self._resume_menus("menus sans document")
            if essai is not None:
                try:
                    self.ouvrir(essai)
                    lignes.append(f"ouverture de « {essai.name} » : réussie, titre "
                                  f"{win32.texte(self.fenetre)!r}")
                    lignes += self._resume_menus("menus avec un document ouvert")
                    self.fermer_document()
                except FinaleBloque as e:
                    lignes.append(f"ouverture de « {essai.name} » : ÉCHEC ({e})")
                    for d in win32.dialogues(pid=self.pid):
                        lignes.append(d.description())
            self.arreter()
        finally:
            self._journal = ancien
        return "\n".join(lignes + ["", "--- journal ---"] + notes)

    def _resume_menus(self, titre: str) -> list[str]:
        e = self.entrees
        lignes = ["", f"=== {titre} : {len(e)} commandes ==="]
        for nom, f in (("ouvrir", entree_ouvrir), ("fermer", entree_fermer),
                       ("export MusicXML", entree_export_xml), ("export PDF", entree_export_pdf),
                       ("imprimer", entree_imprimer)):
            x = f(e)
            lignes.append(f"  {nom:<16} → {' > '.join(x.brut) if x else 'NON TROUVÉ'}")
        lignes.append("  -- arbre complet --")
        for x in e:
            lignes.append(f"  {' > '.join(x.brut)}  [{x.commande}]{' (grisé)' if x.grisee else ''}")
        return lignes


def win32_stable(p: Path) -> bool:
    from .inventaire import fichier_stable
    return fichier_stable(p, 1.0)
