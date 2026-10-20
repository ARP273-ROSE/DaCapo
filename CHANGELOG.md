# Changelog / Historique

## English

### 0.1.0

- First version. Finds every Finale score (.mus, .musx) in the chosen folders, makes verified
  safety copies (the originals are never opened), drives Finale to export each copy to MusicXML
  and, optionally, a reference PDF, checks every MusicXML file (parts, bars, notes, lyrics),
  prepares MuseScore files with a PDF to compare, and writes a report. Resumes where it left off.
- Picks the most recent Finale installed (better MusicXML), recognises menus in French and English,
  records every unexpected Finale message, restarts Finale if it hangs.
- Diagnostics: records Finale's menus and windows, to adapt Da Capo to an unknown version.

## Francais

### 0.1.0

- Première version. Trouve toutes les partitions Finale (.mus, .musx) des dossiers choisis, en fait
  des copies de sécurité vérifiées (les originaux ne sont jamais ouverts), pilote Finale pour
  exporter chaque copie en MusicXML et, au choix, en PDF de référence, relit chaque MusicXML
  (parties, mesures, notes, paroles), prépare les fichiers MuseScore avec un PDF pour comparer, et
  rédige un rapport. Reprend là où il s'était arrêté.
- Choisit le Finale le plus récent installé (MusicXML plus fidèle), reconnaît les menus en français
  et en anglais, consigne chaque message imprévu de Finale, relance Finale s'il se fige.
- Diagnostic : relève les menus et les fenêtres de Finale, pour adapter Da Capo à une version inconnue.
