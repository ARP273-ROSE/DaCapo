"""Moteur de Da Capo sans Windows ni Finale : inventaire, copie, journal,
lecture MusicXML, reconnaissance des menus, déroulé complet avec un faux
Finale et un faux MuseScore."""
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dacapo import finale, inventaire, musescore, musicxml, pilote, travail  # noqa: E402
from dacapo.i18n import definir_langue  # noqa: E402
from dacapo.win32 import Entree, normaliser  # noqa: E402

definir_langue("fr")

PARTITION = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <work><work-title>Ave verum</work-title></work>
  <identification><creator type="composer">Mozart</creator>
    <encoding><software>Finale 2006 for Windows</software></encoding></identification>
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
    <score-part id="P2"><part-name>Orgue</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1"><direction><direction-type><dynamics><p/></dynamics></direction-type></direction>
      <note><pitch><step>D</step><octave>5</octave></pitch><duration>2</duration>
        <lyric><text>A</text></lyric></note>
      <note><rest/><duration>2</duration></note></measure>
    <measure number="2"><note><pitch><step>F</step><octave>5</octave></pitch><duration>4</duration>
        <lyric><text>ve</text></lyric></note></measure>
  </part>
  <part id="P2">
    <measure number="1"><direction><direction-type><words>Adagio</words></direction-type></direction>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration></note>
      <note><chord/><pitch><step>F</step><octave>4</octave></pitch><duration>4</duration></note></measure>
    <measure number="2"><note><rest/><duration>4</duration></note></measure>
  </part>
</score-partwise>
"""


def ecrire(p: Path, contenu: bytes | str = b"finale") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode())
    return p


# ----------------------------------------------------------------- inventaire

def test_chercher_ignore_sauvegardes_et_doublons(tmp_path):
    src = tmp_path / "Partitions"
    ecrire(src / "Messe" / "Kyrie.MUS")
    ecrire(src / "Messe" / "Gloria.musx")
    ecrire(src / "Messe" / "Sauvegarde de Kyrie.mus")
    ecrire(src / "Messe" / "~Kyrie.mus")
    ecrire(src / "Messe" / "Notes.txt")
    ecrire(src / "_dacapo" / "Ancien.mus")
    trouves = inventaire.chercher([src, src / "Messe"])
    assert sorted(f.name for _, f in trouves) == ["Gloria.musx", "Kyrie.MUS"]
    assert all(r == src for r, _ in trouves)        # premier atteint : la racine large


def test_copie_verifiee_lecture_seule_et_idempotente(tmp_path):
    src = ecrire(tmp_path / "A" / "Kyrie.mus", b"\x00contenu finale")
    travail_ = tmp_path / "T"
    f = inventaire.Fiche(rel="A/Kyrie.mus", source=str(src))
    c = inventaire.copier(src, travail_, f.rel, f)
    assert c.read_bytes() == src.read_bytes() and f.sha256 == inventaire.empreinte(src)
    if os.name != "nt":
        assert not os.stat(c).st_mode & stat.S_IWUSR
    avant = c.stat().st_mtime_ns
    inventaire.copier(src, travail_, f.rel, f)                # rien à refaire
    assert c.stat().st_mtime_ns == avant
    assert src.read_bytes() == b"\x00contenu finale"         # original intact


def test_journal_reprise_et_journal_abime(tmp_path):
    j = inventaire.Journal(tmp_path)
    f = j.fiche("A/x.mus", "/src/x.mus")
    f.etats["musicxml"] = "ok"
    j.enregistrer()
    assert inventaire.Journal(tmp_path).fiches["A/x.mus"].fait("musicxml")
    j.chemin.write_text("{abîmé")
    assert inventaire.Journal(tmp_path).fiches == {}
    assert list(j.chemin.parent.glob("journal.illisible-*"))


# ----------------------------------------------------------------- MusicXML

def test_lire_musicxml(tmp_path):
    c = musicxml.lire(ecrire(tmp_path / "a.musicxml", PARTITION))
    assert (c.titre, c.compositeur, c.parties) == ("Ave verum", "Mozart", ["Soprano", "Orgue"])
    assert (c.mesures, c.notes, c.silences, c.paroles, c.nuances, c.textes) == (2, 4, 2, 2, 1, 1)
    assert c.logiciel.startswith("Finale") and c.suspect == ""


def test_lire_mxl_et_fichiers_abimes(tmp_path):
    mxl = tmp_path / "a.mxl"
    with zipfile.ZipFile(mxl, "w") as z:
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="s/a.xml"/>'
                                             '</rootfiles></container>')
        z.writestr("s/a.xml", PARTITION)
    assert musicxml.lire(mxl).notes == 4
    assert musicxml.lire(ecrire(tmp_path / "b.xml", PARTITION[:400])).suspect == "illisible"
    vide = PARTITION.split("<part id=")[0] + "</score-partwise>"
    assert musicxml.lire(ecrire(tmp_path / "c.xml", vide)).suspect == "sans_mesure"


# ----------------------------------------------------------------- Finale

def test_choisir_le_finale_le_plus_recent():
    liste = finale.trier([finale.Finale("Finale 2006", Path("a.exe"), rang=2006),
                          finale.Finale("Finale NotePad 2012", Path("b.exe"), rang=2012),
                          finale.Finale("Finale v27", Path("c.exe"), rang=2027)])
    assert [f.nom for f in liste] == ["Finale v27", "Finale 2006", "Finale NotePad 2012"]
    assert liste[0].musicxml == "finale.xml_4" and liste[1].musicxml == "finale.xml_light"


def _menus(chemins):
    return [Entree(tuple(normaliser(x) for x in c), tuple(c), i + 100, False)
            for i, c in enumerate(chemins)]


FINALE_2006_FR = _menus([
    ("&Fichier", "&Nouveau"), ("&Fichier", "&Ouvrir...\tCtrl+O"), ("&Fichier", "&Fermer"),
    ("&Fichier", "MusicXML", "&Importer..."), ("&Fichier", "MusicXML", "&Exporter..."),
    ("&Fichier", "&Imprimer...\tCtrl+P"), ("&Fichier", "&Quitter")])
FINALE_27_EN = _menus([
    ("&File", "&Open...\tCtrl+O"), ("&File", "&Close"),
    ("&File", "Export", "MusicXML..."), ("&File", "Export", "Compressed MusicXML..."),
    ("&File", "Export", "PDF..."), ("&File", "MusicXML", "Translate Folder to MusicXML..."),
    ("&File", "&Print...\tCtrl+P"), ("&File", "E&xit")])


def test_reconnaitre_les_menus_des_deux_versions():
    e = pilote.entree_export_xml(FINALE_2006_FR)
    assert e.brut[-1] == "&Exporter..."
    assert pilote.entree_ouvrir(FINALE_2006_FR).commande == 101
    assert pilote.entree_export_pdf(FINALE_2006_FR) is None
    assert pilote.entree_imprimer(FINALE_2006_FR).brut[-1].startswith("&Imprimer")
    assert pilote.entree_export_xml(FINALE_27_EN).brut[-1] == "MusicXML..."   # non compressé, pas « dossier »
    assert pilote.entree_export_pdf(FINALE_27_EN).brut[-1] == "PDF..."
    assert pilote.entree_fermer(FINALE_27_EN).brut[-1] == "&Close"


def test_question_enregistrer_toujours_non():
    assert pilote.question_enregistrer("Enregistrer les modifications apportées à « Kyrie » ?")
    assert pilote.question_enregistrer("Do you want to save changes to Kyrie.mus?")
    assert not pilote.question_enregistrer("Le fichier a été créé avec une version antérieure.")


def test_trouver_produit_extension_ajoutee(tmp_path):
    import time
    t0 = time.time()
    ecrire(tmp_path / "Kyrie.musicxml.xml", "x")
    assert pilote.trouver_produit(tmp_path, "Kyrie", t0).name == "Kyrie.musicxml.xml"
    assert pilote.trouver_produit(tmp_path, "Gloria", t0) is None


# ----------------------------------------------------------------- déroulé complet

class FauxFinale:
    """Imite PiloteFinale : écrit un MusicXML ; « Credo » fait planter Finale."""
    demarrages = 0

    def __init__(self):
        self.imprevus = []
        self.ouvert = None

    def demarrer(self):
        FauxFinale.demarrages += 1

    def arreter(self):
        pass

    def tuer(self):
        pass

    def ouvrir(self, fichier):
        assert "originaux" in str(fichier)                  # jamais l'original
        if fichier.stem == "Credo":
            self.imprevus.append("Finale : erreur interne")
            raise pilote.FinaleBloque("ouverture")
        self.ouvert = fichier

    def exporter_musicxml(self, cible):
        ecrire(cible, PARTITION)
        return cible

    def exporter_pdf(self, cible):
        ecrire(cible, b"%PDF-1.4")
        return cible

    def fermer_document(self):
        self.ouvert = None


def faux_mscore(tmp_path) -> Path:
    script = tmp_path / "mscore"
    script.write_text("#!/usr/bin/env python3\nimport json,sys\n"
                      "for t in json.load(open(sys.argv[2])):\n"
                      "    [open(o,'wb').write(b'x') for o in t['out']]\n")
    script.chmod(0o755)
    return script


@pytest.mark.skipif(os.name == "nt", reason="faux MuseScore en script Unix")
def test_deroule_complet_et_reprise(tmp_path):
    src = tmp_path / "Partitions"
    for nom in ("Kyrie", "Gloria", "Credo"):
        ecrire(src / "Messe" / f"{nom}.mus")
    t = tmp_path / "Export"
    couples = inventaire.chercher([src])
    evenements = []
    j = travail.executer(t, couples, travail.Options(), pilote=FauxFinale,
                         mscore=faux_mscore(tmp_path), rappel=evenements.append)
    f = {Path(k).stem: v for k, v in j.fiches.items()}
    assert f["Kyrie"].fait("musicxml") and f["Kyrie"].fait("pdf") and f["Kyrie"].fait("musescore")
    assert f["Kyrie"].mesure["notes"] == 4
    assert f["Credo"].etats["musicxml"] == "echec" and "erreur interne" in f["Credo"].details["imprevus"]
    assert (t / "musicxml" / "Partitions" / "Messe" / "Gloria.musicxml").exists()
    assert (t / "musescore" / "Partitions" / "Messe" / "Gloria.mscz").exists()
    page = (t / "rapport.html").read_text(encoding="utf-8")
    assert page.index("Credo") < page.index("Gloria")         # les échecs en tête
    assert evenements[-1].phase == "fini"

    # reprise : seul le Credo est retenté
    FauxFinale.demarrages = 0
    ouverts = []

    class Espion(FauxFinale):
        def ouvrir(self, fichier):
            ouverts.append(fichier.stem)
            super().ouvrir(fichier)
    travail.executer(t, couples, travail.Options(), pilote=Espion, mscore=faux_mscore(tmp_path))
    assert ouverts == ["Credo"]


def test_taches_musescore():
    t = musescore.taches([(Path("a.musicxml"), Path("a.mscz"), Path("a.pdf")),
                          (Path("b.musicxml"), Path("b.mscz"), None)])
    assert t == [{"in": "a.musicxml", "out": ["a.mscz", "a.pdf"]},
                 {"in": "b.musicxml", "out": ["b.mscz"]}]
    json.dumps(t)
