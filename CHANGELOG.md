# Changelog / Historique

## English

### 0.1.3

- Security: bundled Python 3.14.10 (3.12.10 no longer received security fixes on Windows); the interpreter downloaded at build time is checked against its SHA-256. Incident reports: no more false “watchdog without heartbeat” warning at start-up.

### 0.1.2

- Signed updates: Da Capo installs an update only if its archive is listed in a manifest
  signed by the publisher's key (Ed25519, kept off GitHub); a stolen GitHub access can no longer
  push code to installed copies. The address reached after redirects is checked as well.

### 0.1.1

- Windows: the “File name” box of the modern Save As dialog is now found (it is not where the
  older dialog keeps it). Checked on Windows by driving Notepad end to end.

### 0.1.0

- First version. Finds every Finale score (.mus, .musx) in the chosen folders, makes verified
  safety copies (the originals are never opened), drives Finale to export each copy to MusicXML
  and, optionally, a reference PDF, checks every MusicXML file (parts, bars, notes, lyrics),
  prepares MuseScore files with a PDF to compare, and writes a report. Resumes where it left off.
- Picks the most recent Finale installed (better MusicXML), recognises menus in French and English,
  records every unexpected Finale message, restarts Finale if it hangs.
- Diagnostics: records Finale's menus and windows, to adapt Da Capo to an unknown version.

## Francais

### 0.1.3

- Sécurité : Python embarqué 3.14.10 (la 3.12.10 ne recevait plus de correctifs de sécurité sous Windows) ; l'interpréteur téléchargé à la construction est vérifié par son empreinte SHA-256. Rapports d'incident : plus de faux avertissement « vigie sans battement » au démarrage.

### 0.1.2

- Mises à jour signées : Da Capo n'installe plus une mise à jour que si son archive figure
  dans un manifeste signé par la clé de l'éditeur (Ed25519, hors de GitHub) ; un accès GitHub volé
  ne peut plus pousser de code sur les postes. L'adresse atteinte après les redirections est
  vérifiée elle aussi.

### 0.1.1

- Windows : le champ « Nom du fichier » de la boîte Enregistrer sous moderne est trouvé (il n'est
  pas au même endroit que dans l'ancienne). Vérifié sous Windows en pilotant le Bloc-notes de bout en bout.

### 0.1.0

- Première version. Trouve toutes les partitions Finale (.mus, .musx) des dossiers choisis, en fait
  des copies de sécurité vérifiées (les originaux ne sont jamais ouverts), pilote Finale pour
  exporter chaque copie en MusicXML et, au choix, en PDF de référence, relit chaque MusicXML
  (parties, mesures, notes, paroles), prépare les fichiers MuseScore avec un PDF pour comparer, et
  rédige un rapport. Reprend là où il s'était arrêté.
- Choisit le Finale le plus récent installé (MusicXML plus fidèle), reconnaît les menus en français
  et en anglais, consigne chaque message imprévu de Finale, relance Finale s'il se fige.
- Diagnostic : relève les menus et les fenêtres de Finale, pour adapter Da Capo à une version inconnue.
