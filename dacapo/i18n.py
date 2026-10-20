"""Textes de Da Capo en français et en anglais, langue détectée automatiquement.

Règles (les mêmes que MountMonitor) :
* chaque clé existe dans les deux langues — un test l'exige ;
* les champs de format ({n}, {nom}…) sont les mêmes d'une langue à l'autre,
  sinon le texte lèverait une erreur à l'exécution, chez l'utilisateur ;
* une clé manquante retombe sur l'anglais, puis sur la clé elle-même :
  un texte non traduit est un défaut cosmétique, un bouton vide est une panne.

Ce module ne dépend pas de Qt : le moteur l'utilise aussi.
"""
from __future__ import annotations

import os
import sys

LANGUES = ("fr", "en")
_langue = None


def detecter() -> str:
    """Langue d'AFFICHAGE du système (pas celle des formats de date).

    Windows : GetUserDefaultUILanguage (la locale de format peut être
    britannique chez un francophone, et inversement). macOS : la liste
    AppleLanguages des préférences globales, lue sans lancer de commande.
    Linux : variables d'environnement.
    """
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val not in ("C", "POSIX") and not val.startswith("C."):
            return "fr" if val.lower().startswith("fr") else "en"
    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "fr" if (langid & 0x3FF) == 0x0C else "en"
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            import plistlib
            from pathlib import Path
            chemin = Path.home() / "Library" / "Preferences" / ".GlobalPreferences.plist"
            with open(chemin, "rb") as f:
                langues = plistlib.load(f).get("AppleLanguages") or []
            if langues:
                return "fr" if str(langues[0]).lower().startswith("fr") else "en"
        except Exception:
            pass
    return "en"


def definir_langue(code: str | None) -> str:
    """Fixe la langue ('fr', 'en', ou None/'auto' pour la détection)."""
    global _langue
    _langue = code if code in LANGUES else detecter()
    return _langue


def langue() -> str:
    return _langue or definir_langue(None)


def tr(cle: str, **champs) -> str:
    textes = TEXTES.get(cle)
    if not textes:
        return cle
    modele = textes.get(langue()) or textes.get("en") or cle
    try:
        return modele.format(**champs) if champs else modele
    except (KeyError, IndexError, ValueError):
        return modele


def pluriel(n: int, cle_un: str, cle_plusieurs: str, **champs) -> str:
    return tr(cle_un if n == 1 else cle_plusieurs, n=n, **champs)




TEXTES: dict[str, dict[str, str]] = {
    # ---- fenêtre
    "fenetre.titre": {"fr": "Da Capo {version} — sortir ses partitions de Finale",
                      "en": "Da Capo {version} — get your scores out of Finale"},
    "entete.sous_titre": {
        "fr": "Toutes vos partitions Finale, exportées fidèlement en MusicXML pour MuseScore — "
              "les originaux ne sont jamais touchés.",
        "en": "All your Finale scores, faithfully exported to MusicXML for MuseScore — "
              "the originals are never touched."},
    "etape.sources": {"fr": "1. Où sont vos partitions Finale ?", "en": "1. Where are your Finale scores?"},
    "sources.vide": {"fr": "Glissez ici le ou les dossiers de partitions\n(les sous-dossiers sont parcourus)",
                     "en": "Drop the score folder(s) here\n(subfolders are included)"},
    "sources.ajouter": {"fr": "Ajouter un dossier…", "en": "Add a folder…"},
    "sources.retirer": {"fr": "Retirer", "en": "Remove"},
    "sources.recherche": {"fr": "Recherche des partitions…", "en": "Looking for scores…"},
    "sources.trouvees": {"fr": "{n} partition(s) Finale trouvée(s) : {mus} .mus, {musx} .musx",
                         "en": "{n} Finale score(s) found: {mus} .mus, {musx} .musx"},
    "sources.aucune": {"fr": "Aucune partition Finale (.mus, .musx) dans ces dossiers.",
                       "en": "No Finale score (.mus, .musx) in these folders."},
    "etape.travail": {"fr": "2. Où ranger le résultat ?", "en": "2. Where to put the result?"},
    "travail.choisir": {"fr": "Choisir…", "en": "Browse…"},
    "travail.note": {"fr": "Da Capo y copie vos partitions et travaille sur les copies : "
                           "les originaux ne sont jamais ouverts ni modifiés.",
                     "en": "Da Capo copies your scores there and works on the copies: "
                           "the originals are never opened or modified."},
    "travail.defaut": {"fr": "Partitions Finale - export Da Capo", "en": "Finale scores - Da Capo export"},
    "etape.finale": {"fr": "3. Avec quel Finale ?", "en": "3. With which Finale?"},
    "finale.aucun": {"fr": "Aucun Finale trouvé sur cet ordinateur.", "en": "No Finale found on this computer."},
    "finale.pas_windows": {"fr": "Finale ne peut être piloté que sous Windows. Ici, Da Capo copie, vérifie "
                                 "les MusicXML déjà exportés et prépare les fichiers MuseScore.",
                           "en": "Finale can only be driven on Windows. Here, Da Capo copies, checks the "
                                 "MusicXML files already exported and prepares the MuseScore files."},
    "finale.recommande": {"fr": "{nom} — {xml} (recommandé)", "en": "{nom} — {xml} (recommended)"},
    "finale.option": {"fr": "{nom} — {xml}", "en": "{nom} — {xml}"},
    "finale.xml_4": {"fr": "MusicXML 4.0, le plus fidèle", "en": "MusicXML 4.0, the most faithful"},
    "finale.xml_3": {"fr": "MusicXML 3, très fidèle", "en": "MusicXML 3, very faithful"},
    "finale.xml_light": {"fr": "MusicXML de base (Dolet Light)", "en": "basic MusicXML (Dolet Light)"},
    "finale.xml_aucun": {"fr": "export MusicXML incertain", "en": "MusicXML export uncertain"},
    "finale.diagnostic": {"fr": "Diagnostic…", "en": "Diagnostics…"},
    "finale.diagnostic.astuce": {
        "fr": "Ouvre Finale avec une copie d'une partition et relève ses menus et ses fenêtres, "
              "sans rien modifier. À faire une fois avant le premier export.",
        "en": "Opens Finale with a copy of one score and records its menus and windows, without "
              "changing anything. Do it once before the first export."},
    "etape.options": {"fr": "4. Que produire ?", "en": "4. What to produce?"},
    "options.musicxml": {"fr": "MusicXML (pour MuseScore, Dorico, Sibelius…) — toujours",
                         "en": "MusicXML (for MuseScore, Dorico, Sibelius…) — always"},
    "options.pdf": {"fr": "PDF de référence : la partition exactement comme Finale l'imprime",
                    "en": "Reference PDF: the score exactly as Finale prints it"},
    "options.pdf.astuce": {"fr": "Pour comparer avec MuseScore, et comme archive qui se lira toujours. "
                                 "Finale 25 et après : export PDF direct ; avant : imprimante CutePDF Writer.",
                           "en": "To compare with MuseScore, and as an archive that will always open. "
                                 "Finale 25 and later: direct PDF export; earlier: CutePDF Writer printer."},
    "options.musescore": {"fr": "Fichiers MuseScore prêts à ouvrir, avec un PDF pour comparer",
                          "en": "MuseScore files ready to open, with a PDF to compare"},
    "options.musescore_absent": {"fr": "MuseScore Studio n'est pas installé (gratuit : musescore.org) : "
                                       "cette étape est sautée.",
                                 "en": "MuseScore Studio is not installed (free: musescore.org): "
                                       "this step is skipped."},
    "avertissement": {"fr": "Pendant l'export, Finale s'ouvre et travaille seul : ne touchez ni à la "
                            "souris ni au clavier. Vous pouvez arrêter à tout moment, Da Capo "
                            "reprendra là où il s'était arrêté.",
                      "en": "During the export, Finale opens and works on its own: do not touch the "
                            "mouse or keyboard. You can stop at any time; Da Capo will resume where "
                            "it left off."},
    "bouton.commencer": {"fr": "Commencer", "en": "Start"},
    "bouton.reprendre": {"fr": "Reprendre", "en": "Resume"},
    "bouton.arreter": {"fr": "Arrêter", "en": "Stop"},
    "bouton.arret": {"fr": "Arrêt après cette partition…", "en": "Stopping after this score…"},
    "bouton.rapport": {"fr": "Ouvrir le rapport", "en": "Open the report"},
    "bouton.dossier": {"fr": "Ouvrir le dossier", "en": "Open the folder"},
    "phase.copie": {"fr": "Copie de sécurité : {nom}", "en": "Safety copy: {nom}"},
    "phase.finale": {"fr": "Finale : {nom}", "en": "Finale: {nom}"},
    "phase.musescore": {"fr": "Préparation pour MuseScore", "en": "Preparing for MuseScore"},
    "phase.rapport": {"fr": "Rédaction du rapport", "en": "Writing the report"},
    "phase.fini": {"fr": "Terminé : {ok} partition(s) exportée(s) sur {n}, {echecs} échec(s).",
                   "en": "Done: {ok} of {n} score(s) exported, {echecs} failure(s)."},
    "phase.arrete": {"fr": "Arrêté. Cliquez sur « Reprendre » pour continuer plus tard.",
                     "en": "Stopped. Click “Resume” to continue later."},
    "phase.demarrage_finale": {"fr": "Finale ne démarre pas. Ouvrez-le une fois à la main (activation, "
                                     "mises à jour), refermez-le, puis recommencez.",
                               "en": "Finale does not start. Open it once by hand (activation, updates), "
                                     "close it, then try again."},
    "phase.dossier_ecriture": {"fr": "Impossible d'écrire dans le dossier de travail : {detail}",
                               "en": "Cannot write to the working folder: {detail}"},
    "quitter.en_cours": {"fr": "Un export est en cours. L'arrêter après la partition en cours et quitter ?",
                         "en": "An export is running. Stop it after the current score and quit?"},
    # ---- diagnostic
    "diag.titre": {"fr": "Diagnostic de Finale", "en": "Finale diagnostics"},
    "diag.encours": {"fr": "Finale va s'ouvrir quelques instants avec une copie de « {nom} ». "
                           "Ne touchez à rien jusqu'à la fin.",
                     "en": "Finale will open for a moment with a copy of “{nom}”. Do not touch "
                           "anything until it is done."},
    "diag.sans_partition": {"fr": "Ajoutez d'abord un dossier de partitions (étape 1).",
                            "en": "First add a score folder (step 1)."},
    "diag.resultat_ok": {"fr": "Tout est reconnu : Da Capo sait ouvrir, exporter et fermer avec ce Finale.",
                         "en": "Everything is recognised: Da Capo can open, export and close with this Finale."},
    "diag.resultat_ko": {"fr": "Certaines commandes n'ont pas été reconnues. Envoyez ce relevé au "
                               "développeur pour qu'il adapte Da Capo à ce Finale.",
                         "en": "Some commands were not recognised. Send this record to the developer so "
                               "Da Capo can be adapted to this Finale."},
    "diag.envoyer": {"fr": "Envoyer le relevé", "en": "Send the record"},
    "diag.envoye": {"fr": "Relevé envoyé. Merci !", "en": "Record sent. Thank you!"},
    "diag.enregistre": {"fr": "Relevé enregistré ici :\n{chemin}", "en": "Record saved here:\n{chemin}"},
    # ---- rapport
    "rapport.lang": {"fr": "fr", "en": "en"},
    "rapport.titre": {"fr": "Da Capo — rapport d'export", "en": "Da Capo — export report"},
    "rapport.genere": {"fr": "Rapport du {date}, Da Capo {version}.", "en": "Report of {date}, Da Capo {version}."},
    "rapport.partitions": {"fr": "partitions", "en": "scores"},
    "rapport.pdf_ref": {"fr": "PDF de référence", "en": "reference PDFs"},
    "rapport.nb_echecs": {"fr": "en échec", "en": "failed"},
    "rapport.nb_voir": {"fr": "à vérifier", "en": "to check"},
    "rapport.aide": {
        "fr": "Rouge : l'export a échoué (voir la raison) ; orange : exporté, mais à vérifier ; vert : "
              "tout s'est bien passé. Pour contrôler une partition, ouvrez côte à côte son PDF de "
              "référence (Finale) et son PDF MuseScore.",
        "en": "Red: the export failed (see why); orange: exported, but worth checking; green: all "
              "went well. To check a score, open its reference PDF (Finale) and its MuseScore PDF "
              "side by side."},
    "rapport.col.partition": {"fr": "Partition", "en": "Score"},
    "rapport.col.pdf": {"fr": "PDF Finale", "en": "Finale PDF"},
    "rapport.col.remarques": {"fr": "Remarques", "en": "Notes"},
    "rapport.original": {"fr": "copie de l'original", "en": "copy of the original"},
    "rapport.contenu": {"fr": "{p} partie(s), {m} mesures, {n} notes",
                        "en": "{p} part(s), {m} bars, {n} notes"},
    "rapport.paroles": {"fr": ", {n} syllabes de paroles", "en": ", {n} lyric syllables"},
    "rapport.etat.echec": {"fr": "échec", "en": "failed"},
    "rapport.etat.absent": {"fr": "pas encore fait", "en": "not done yet"},
    "rapport.etat.ok": {"fr": "fait", "en": "done"},
    "rapport.etat.saute": {"fr": "sauté", "en": "skipped"},
    "rapport.etape.copie": {"fr": "copie", "en": "copy"},
    "rapport.etape.musicxml": {"fr": "export MusicXML", "en": "MusicXML export"},
    "rapport.etape.pdf": {"fr": "PDF de référence", "en": "reference PDF"},
    "rapport.etape.musescore": {"fr": "conversion MuseScore", "en": "MuseScore conversion"},
    "rapport.echec": {"fr": "{etape} : {detail}", "en": "{etape}: {detail}"},
    "rapport.imprevus": {"fr": "Messages de Finale : {detail}", "en": "Finale messages: {detail}"},
    "rapport.suspect.illisible": {"fr": "MusicXML illisible", "en": "unreadable MusicXML"},
    "rapport.suspect.sans_partie": {"fr": "aucune partie dans le MusicXML", "en": "no part in the MusicXML"},
    "rapport.suspect.sans_mesure": {"fr": "aucune mesure dans le MusicXML", "en": "no bar in the MusicXML"},
    "rapport.suspect.sans_note": {"fr": "aucune note : partition vide ou export incomplet",
                                  "en": "no note: empty score or incomplete export"},
    "code.boite_fichier": {"fr": "la boîte « Ouvrir / Enregistrer » n'est pas apparue",
                           "en": "the Open / Save dialog did not appear"},
    "code.ouverture": {"fr": "Finale n'a pas ouvert la partition à temps", "en": "Finale did not open the score in time"},
    "code.fermeture": {"fr": "Finale n'a pas refermé la partition", "en": "Finale did not close the score"},
    "code.export": {"fr": "le fichier n'a pas été écrit à temps", "en": "the file was not written in time"},
    "code.menu_absent": {"fr": "commande introuvable dans les menus de Finale (faire un diagnostic)",
                         "en": "command not found in Finale's menus (run a diagnostic)"},
    "code.finale_arrete": {"fr": "Finale s'est fermé", "en": "Finale closed"},
    "code.boite_impression": {"fr": "boîte d'impression non reconnue", "en": "print dialog not recognised"},
    "code.cutepdf_absent": {"fr": "imprimante CutePDF Writer introuvable", "en": "CutePDF Writer printer not found"},
    "code.cutepdf_boite": {"fr": "CutePDF n'a pas demandé où enregistrer", "en": "CutePDF did not ask where to save"},
    "code.delai": {"fr": "MuseScore a mis trop longtemps", "en": "MuseScore took too long"},
    "code.echec": {"fr": "MuseScore n'a rien produit", "en": "MuseScore produced nothing"},
    "code.demarrage": {"fr": "Finale ne démarre pas", "en": "Finale does not start"},
    # ---- menus, aide, kit
    "menu.fichier": {"fr": "&Fichier", "en": "&File"},
    "menu.quitter": {"fr": "Quitter", "en": "Quit"},
    "menu.langue": {"fr": "&Langue", "en": "&Language"},
    "menu.langue.auto": {"fr": "Automatique (langue du système)", "en": "Automatic (system language)"},
    "menu.langue.redemarrer": {"fr": "La nouvelle langue s'appliquera au prochain démarrage de Da Capo.",
                               "en": "The new language will apply the next time Da Capo starts."},
    "menu.aide": {"fr": "&Aide", "en": "&Help"},
    "menu.manuel": {"fr": "Manuel (PDF)", "en": "User guide (PDF)"},
    "menu.mode_emploi": {"fr": "Mode d'emploi rapide", "en": "Quick help"},
    "menu.maj": {"fr": "Rechercher une mise à jour", "en": "Check for updates"},
    "menu.signaler": {"fr": "Signaler un problème…", "en": "Report a problem…"},
    "menu.rapports_auto": {"fr": "Envoi automatique des rapports d'incident",
                           "en": "Send error reports automatically"},
    "menu.a_propos": {"fr": "À propos", "en": "About"},
    "manuel.absent": {"fr": "Le manuel est introuvable dans le dossier du programme.",
                      "en": "The user guide could not be found in the program folder."},
    "aide.titre": {"fr": "Mode d'emploi", "en": "Quick help"},
    "aide.texte": {
        "fr": "<h3>Da Capo — en quatre étapes</h3><ol>"
              "<li><b>Ajoutez</b> le ou les dossiers où sont vos partitions Finale.</li>"
              "<li>Choisissez le <b>dossier de travail</b> : tout y sera rangé (copies, MusicXML, PDF, "
              "fichiers MuseScore, rapport).</li>"
              "<li>Choisissez le <b>Finale</b> à utiliser : le plus récent est le plus fidèle. "
              "La première fois, cliquez sur <i>Diagnostic…</i>.</li>"
              "<li>Cliquez sur <b>Commencer</b>, et ne touchez plus à l'ordinateur.</li></ol>"
              "<p>À la fin, <b>Ouvrir le rapport</b> montre partition par partition ce qui a été fait, "
              "et ce qui mérite un coup d'œil. Les originaux ne sont <b>jamais modifiés</b>.</p>"
              "<p>Le manuel complet est dans le menu <i>Aide</i> (F1).</p>",
        "en": "<h3>Da Capo — in four steps</h3><ol>"
              "<li><b>Add</b> the folder(s) where your Finale scores are.</li>"
              "<li>Choose the <b>working folder</b>: everything goes there (copies, MusicXML, PDF, "
              "MuseScore files, report).</li>"
              "<li>Choose the <b>Finale</b> to use: the most recent is the most faithful. "
              "The first time, click <i>Diagnostics…</i>.</li>"
              "<li>Click <b>Start</b>, and leave the computer alone.</li></ol>"
              "<p>At the end, <b>Open the report</b> shows, score by score, what was done and what is "
              "worth a look. The originals are <b>never modified</b>.</p>"
              "<p>The full user guide is in the <i>Help</i> menu (F1).</p>"},
    "a_propos.texte": {
        "fr": "<b>Da Capo {version}</b><br>Sortir ses partitions de Finale, fidèlement et en lot.<br><br>"
              "<i>Da capo</i> : « depuis le début », en musique — reprendre ses partitions "
              "dans un nouveau logiciel.<br><br>Logiciel libre et gratuit. Finale est une marque de "
              "MakeMusic ; MuseScore, de Muse Group. Da Capo n'est lié à aucun des deux.<br><br>"
              "Polices : Source Sans 3 et EB Garamond (SIL Open Font License).",
        "en": "<b>Da Capo {version}</b><br>Get your scores out of Finale, faithfully and in bulk.<br><br>"
              "<i>Da capo</i>: “from the beginning”, in music — picking your scores up again in new "
              "software.<br><br>Free software. Finale is a trademark of MakeMusic; MuseScore, of Muse "
              "Group. Da Capo is affiliated with neither.<br><br>"
              "Fonts: Source Sans 3 and EB Garamond (SIL Open Font License)."},
    "accord.titre": {"fr": "Envoyer automatiquement un rapport si Da Capo rencontre un problème ?",
                     "en": "Send a report automatically if Da Capo runs into a problem?"},
    "accord.texte": {
        "fr": "Le rapport contient la version du programme et du système et l'erreur rencontrée. "
              "Les noms de vos fichiers et votre nom d'utilisateur sont masqués. "
              "Vous pourrez changer d'avis dans le menu Aide.",
        "en": "The report contains the program and system versions and the error. "
              "Your file names and user name are hidden. You can change your mind in the Help menu."},
    "dlg.oui": {"fr": "Oui", "en": "Yes"},
    "dlg.non": {"fr": "Non", "en": "No"},
    "dlg.fermer": {"fr": "Fermer", "en": "Close"},
    "dlg.choisir_sources": {"fr": "Choisir un dossier de partitions", "en": "Choose a score folder"},
    "dlg.choisir_travail": {"fr": "Choisir le dossier de travail", "en": "Choose the working folder"},
    "maj.titre": {"fr": "Mise à jour", "en": "Update"},
    "maj.recherche": {"fr": "Recherche d'une mise à jour…", "en": "Checking for updates…"},
    "maj.a_jour": {"fr": "Da Capo {version} est à jour.", "en": "Da Capo {version} is up to date."},
    "maj.dispo": {"fr": "La version {nouvelle} est disponible (vous avez la {version}).",
                  "en": "Version {nouvelle} is available (you have {version})."},
    "maj.installer": {"fr": "Installer maintenant", "en": "Install now"},
    "maj.page": {"fr": "Ouvrir la page", "en": "Open the page"},
    "maj.plus_tard": {"fr": "Plus tard", "en": "Later"},
    "maj.telechargement": {"fr": "Téléchargement de la mise à jour…", "en": "Downloading the update…"},
    "maj.verrou": {"fr": "Un fichier de Da Capo est en cours d'utilisation : fermez les autres fenêtres "
                         "de Da Capo et réessayez.",
                   "en": "A Da Capo file is in use: close the other Da Capo windows and try again."},
    "maj.echec": {"fr": "La mise à jour a échoué : {erreur}", "en": "The update failed: {erreur}"},
    "maj.redemarre": {"fr": "Mise à jour installée : Da Capo va redémarrer.",
                      "en": "Update installed: Da Capo will now restart."},
    "signal.titre": {"fr": "Signaler un problème", "en": "Report a problem"},
    "signal.invite": {"fr": "Décrivez ce qui s'est passé :", "en": "Describe what happened:"},
    "signal.exemple": {"fr": "Par exemple : à la partition 37, Finale a affiché un message et tout s'est arrêté…",
                       "en": "For example: at score 37, Finale showed a message and everything stopped…"},
    "signal.note": {"fr": "Le message part avec la version de Da Capo et du système. Les noms de vos "
                          "fichiers et votre nom d'utilisateur sont masqués.",
                    "en": "The message is sent with the Da Capo and system versions. Your file names "
                          "and user name are hidden."},
    "signal.envoyer": {"fr": "Envoyer", "en": "Send"},
    "signal.merci": {"fr": "Merci", "en": "Thank you"},
    "signal.parti": {"fr": "Merci, le signalement est parti.", "en": "Thank you, the report was sent."},
    "signal.local": {"fr": "Pas de réseau : le signalement a été enregistré ici :\n{chemin}",
                     "en": "No network: the report was saved here:\n{chemin}"},
    "demarrage.echec": {"fr": "Le programme n'a pas pu démarrer.\n\n{erreur}\n\nDétails enregistrés dans :\n{chemin}",
                        "en": "The program could not start.\n\n{erreur}\n\nDetails saved in:\n{chemin}"},
    "cli.description": {"fr": "Exporter des partitions Finale en MusicXML, en lot.",
                        "en": "Export Finale scores to MusicXML, in bulk."},
}
