# Da Capo — progression

## État au 25/11/2026

**Version : 0.1.4** (25/11/2026) — **essayée contre un vrai Finale 27.4** : 22/22 tutoriels + MIDI.

- 0.1.1 : boîte « Enregistrer sous » moderne (id 1001). 0.1.2 : MAJ signées Ed25519.
  0.1.3 : Python embarqué 3.14.10 vérifié par SHA-256.
- 25/11/2026 : **premier essai réel** (session du PC Windows, Finale 27.4 + MuseScore 4) : 22/22 tutoriels
  OK (~9 s/partition), menus tous reconnus. 3 bugs corrigés sur main (publiés en **0.1.4**) : boîtes de fichier validées par Da Capo comptées comme imprévues (tout en orange),
  fenêtre de progression annulée (seul bouton Cancel), boîte d'options à champ texte prise pour une boîte
  de fichier ; + « Ne pas vérifier » sur la boîte de mise à jour ; 2e essai : fenêtre de lancement
  refermée sans être consignée, boîte de fichier jamais prise pour une progression. Tests : `tests/test_boites.py`.
- (avant) **aucun relevé reçu** (pas de `rapports/dacapo` dans pwa-rapports) → le Diagnostic n'a jamais tourné.

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
- ✅ **Diagnostic sur un vrai Finale 27.4 EN** (25/11/2026, poste Windows) : menus File > Open / Close /
  Export > MusicXML… / PDF… / Print reconnus ; 22/22 tutoriels exportés (~9 s/partition) ; aller-retour
  MuseScore identique note à note 21/22 (le 22e : `<mode>` omis sur une tablature).
- ⏳ **Finale 2006** (les vrais .mus à convertir) : libellés FR, export Dolet Light vs intégré.
- ⏳ Impression vers CutePDF (boîte d'impression propre à Finale ?).

### Fabrication
- Tests : `QT_QPA_PLATFORM=offscreen python -m pytest -q tests`
- Captures : `python docs/captures.py` ; manuels : `sh docs/src/compiler.sh` ; logo : `python make_logo.py`
- Publication : VERSION + CHANGELOG, tag `vX.Y.Z` (release unique : les anciennes sont retirées).
