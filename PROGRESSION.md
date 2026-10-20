# Da Capo — progression

## État au 20/10/2026

**Version : 0.1.0** — première version, jamais essayée contre un vrai Finale.

### Fonctions
- Inventaire des `.mus` / `.musx` (sous-dossiers, copies de secours de Finale ignorées).
- Copie vérifiée SHA-256 dans `<travail>/originaux/`, en lecture seule : Finale n'ouvre QUE les copies.
- Pilote Finale (Windows, `dacapo/pilote.py` + `dacapo/win32.py`, ctypes pur) : menus lus par
  GetMenu et déclenchés par WM_COMMAND, reconnus par libellé FR/EN ; boîtes Ouvrir/Enregistrer
  remplies par WM_SETTEXT (contrôles 1148/1152) + IDOK ; boîtes imprévues lues puis refermées
  (« Enregistrer ? » → toujours Non) ; Finale relancé s'il se fige, et tous les 40 fichiers.
- PDF de référence : Fichier → Exporter → PDF (Finale 25+), sinon impression vers CutePDF Writer.
- Contrôle de chaque MusicXML (`dacapo/musicxml.py`) ; conversion MuseScore en lot (`-j`).
- Journal `_dacapo/journal.json` réécrit après chaque partition → reprise.
- Diagnostic : relevé des menus/fenêtres de Finale, envoi par le kit (`diagnostic_finale`).

### Vérifié
- Tests : moteur avec faux Finale, menus Finale 2006 FR et Finale 27 EN simulés, fenêtre hors écran ;
  `test_win32.py` pilote le vrai Bloc-notes sous Windows (CI).
- **MuseScore Studio 4.7.5 réel** (AppImage, sous Xvfb) : conversion en lot MusicXML → .mscz + PDF OK.
  🔴 Ne PAS forcer `QT_QPA_PLATFORM=offscreen` : MuseScore charge le thème GTK et s'arrête sans écran.

### Reste à vérifier
- ⏳ **Diagnostic sur un vrai Finale** (poste Windows avec Finale 2006 + Finale récent) : libellés
  exacts des menus, boîtes au démarrage, export Dolet Light vs export intégré.
- ⏳ Impression vers CutePDF (boîte d'impression propre à Finale ?).

### Fabrication
- Tests : `QT_QPA_PLATFORM=offscreen python -m pytest -q tests`
- Captures : `python docs/captures.py` ; manuels : `sh docs/src/compiler.sh` ; logo : `python make_logo.py`
- Publication : VERSION + CHANGELOG, tag `vX.Y.Z` (release unique : les anciennes sont retirées).
