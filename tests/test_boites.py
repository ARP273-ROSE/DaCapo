"""Boîtes de Finale avec de faux dialogues (relevés sur Finale 27.4) : la boîte
de fichier que Da Capo vient de valider, la fenêtre de progression à ne pas
annuler, la boîte d'options avec un champ texte qui n'est pas une boîte de
fichier, la boîte de mise à jour au démarrage."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dacapo import pilote, win32  # noqa: E402
from dacapo.win32 import Controle, Dialogue  # noqa: E402


def bouton(h, texte, ident=0):
    return Controle(h, "Button", ident, texte, True, True)


def statique(h, texte):
    return Controle(h, "Static", 0, texte, True, True)


def edit(h, ident=0):
    return Controle(h, "Edit", ident, "", True, True)


PID = 4242

MIDI_STATUS = Dialogue(10, "MIDI File Status", PID, [
    statique(11, "Transcribing MIDI Sequencer File"), statique(12, "Checking Key Signatures"),
    statique(13, "Current Measure: 12"), bouton(14, "Cancel", 2)])

OPTIONS_MIDI = Dialogue(20, "Import MIDI File Options", PID, [
    statique(21, "Quant Settings"), edit(22, 1001), bouton(23, "OK", 1), bouton(24, "Cancel", 2)])

OUVRIR = Dialogue(30, "Open", PID, [
    Controle(31, "ComboBox", 1148, "", True, True), Controle(32, "NamespaceTreeControl", 0, "", True, True),
    bouton(33, "&Open", 1), bouton(34, "Cancel", 2)])

OUVRIR_QUI_SE_FERME = Dialogue(30, "Open", PID, [])          # plus de contrôles lisibles

EXPORT_XML = Dialogue(40, "Export MusicXML File", PID, [
    Controle(41, "DirectUIHWND", 0, "", True, True), bouton(42, "&Save", 1)])

REMPLACER = Dialogue(50, "Export MusicXML File", PID, [
    statique(51, "Kyrie.musicxml already exists. Do you want to replace it?"),
    bouton(52, "&Yes", 6), bouton(53, "&No", 7)])

MISE_A_JOUR = Dialogue(60, "Mise à jour du Logiciel", PID, [
    statique(61, "Finale peut vérifier automatiquement les mises à jour."),
    bouton(62, "Vérifier automatiquement"), bouton(63, "Ne pas vérifier")])

CONVERSION = Dialogue(70, "Converting", PID, [statique(71, "Converting file…")])

ANCIENNE_VERSION = Dialogue(80, "Finale", PID, [
    statique(81, "Ce fichier a été créé avec une version antérieure. La conversion peut modifier la mise en page."),
    bouton(82, "OK", 1)])


# ----------------------------------------------------------------- bug 3

def test_boite_d_options_n_est_pas_une_boite_de_fichier():
    assert not win32.est_boite_fichier(OPTIONS_MIDI)
    assert win32.champ_nom_fichier(OPTIONS_MIDI) is None


def test_vraies_boites_de_fichier():
    assert win32.est_boite_fichier(OUVRIR)
    assert win32.est_boite_fichier(EXPORT_XML)
    assert win32.est_boite_fichier(Dialogue(1, "Save As", PID, [edit(2, 1152), bouton(3, "Save", 1)]))


# ----------------------------------------------------------------- bug 2

def test_progression_reconnue():
    assert pilote.est_progression(MIDI_STATUS)
    assert pilote.est_progression(CONVERSION)
    assert pilote.est_progression(Dialogue(1, "Progression", PID, [bouton(2, "Annuler", 2)]))


def test_vraies_questions_ne_sont_pas_des_progressions():
    for d in (OPTIONS_MIDI, REMPLACER, MISE_A_JOUR, ANCIENNE_VERSION, OUVRIR):
        assert not pilote.est_progression(d), d.titre


# ----------------------------------------------------------------- bonus

def test_mise_a_jour_ne_pas_verifier():
    assert pilote.bouton_pour(MISE_A_JOUR).texte == "Ne pas vérifier"
    d = Dialogue(1, "Software Update", PID, [bouton(2, "Check Automatically"), bouton(3, "Don't Check")])
    assert pilote.bouton_pour(d).texte == "Don't Check"


# ----------------------------------------------------------------- pilote

@pytest.fixture
def faux_windows(monkeypatch):
    """PiloteFinale sur de faux dialogues : on note ce qui est cliqué/fermé."""
    ecran = {"boites": [], "clics": [], "fermees": []}
    monkeypatch.setattr(win32, "DISPONIBLE", True)
    monkeypatch.setattr(win32, "dialogues", lambda pid=None: list(ecran["boites"]))
    monkeypatch.setattr(win32, "cliquer", lambda h: ecran["clics"].append(h))
    monkeypatch.setattr(win32, "fermer", lambda h: ecran["fermees"].append(h))
    monkeypatch.setattr(win32, "remplir_et_valider", lambda d, c: True)
    p = pilote.PiloteFinale(finale=None)
    p.proc = type("Proc", (), {"pid": PID, "poll": lambda self: None})()
    return p, ecran


def test_boite_validee_par_da_capo_n_est_pas_imprevue(faux_windows):
    p, ecran = faux_windows
    p._valider_boite(OUVRIR, r"C:\travail\originaux\Kyrie.mus")
    ecran["boites"] = [OUVRIR_QUI_SE_FERME]                  # même hwnd, en cours de fermeture
    assert p._imprevus() == 0
    p._valider_boite(EXPORT_XML, r"C:\travail\musicxml\Kyrie.musicxml")
    ecran["boites"] = [Dialogue(99, "Export MusicXML File", PID, [])]   # même titre, rien d'affiché
    assert p._imprevus() == 0
    assert p.imprevus == [] and ecran["fermees"] == [] and ecran["clics"] == []


def test_remplacer_reste_traite_apres_validation(faux_windows):
    p, ecran = faux_windows
    p._valider_boite(EXPORT_XML, r"C:\travail\musicxml\Kyrie.musicxml")
    ecran["boites"] = [REMPLACER]
    assert p._imprevus() == 1
    assert ecran["clics"] == [52]                             # Oui
    assert p.imprevus and "replace" in p.imprevus[0]


def test_progression_jamais_annulee(faux_windows):
    p, ecran = faux_windows
    ecran["boites"] = [MIDI_STATUS]
    for _ in range(3):
        assert p._imprevus() == 0
    assert ecran["clics"] == [] and ecran["fermees"] == [] and p.imprevus == []


def test_boite_d_options_traitee_pas_ignoree(faux_windows):
    p, ecran = faux_windows
    ecran["boites"] = [OPTIONS_MIDI]
    assert p._imprevus(sauf=lambda x: win32.champ_nom_fichier(x) is not None) == 1
    assert ecran["clics"] == [23]                             # OK


def test_pas_de_message_vide_dans_les_imprevus(faux_windows):
    p, ecran = faux_windows
    ecran["boites"] = [Dialogue(5, "Finale", PID, [bouton(6, "OK", 1)])]
    p._imprevus()
    assert p.imprevus == ["Finale"]
