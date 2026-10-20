"""Trouver les Finale installés et choisir le meilleur pour l'export.

Un poste peut garder plusieurs Finale (2006 en usage quotidien, un plus
récent installé et jamais ouvert). Le plus récent exporte un MusicXML bien
plus fidèle : version 4.0 pour Finale 27, 3.x pour Finale 2011 à 26, alors
que le « Dolet Light » de Finale 2003 à 2010 se limite à l'essentiel. Or un
Finale récent ouvre sans difficulté les .mus des anciennes versions : on
choisit donc toujours le plus récent, sauf avis contraire de l'utilisateur.

Sources : la liste des programmes installés (registre, 32 et 64 bits) et
les dossiers usuels, pour un Finale copié sans installeur.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: Éditions qui ne sont pas « Finale » complet : elles ouvrent les fichiers
#: mais ne savent pas toutes exporter. On les garde en dernier recours.
EDITIONS_REDUITES = ("notepad", "printmusic", "songwriter", "allegro", "guitar", "reader")


@dataclass
class Finale:
    nom: str                 # « Finale 2006 », « Finale 27 »…
    exe: Path
    version: str = ""        # telle qu'affichée par l'installeur
    rang: float = 0.0        # pour trier : 2006, 2014.5, 2025 (v25)…

    @property
    def complet(self) -> bool:
        return not any(e in self.nom.lower() for e in EDITIONS_REDUITES)

    @property
    def musicxml(self) -> str:
        """Ce que cette version sait exporter, en clair (clé de traduction)."""
        if self.rang >= 2027:
            return "finale.xml_4"
        if self.rang >= 2011:
            return "finale.xml_3"
        if self.rang >= 2003:
            return "finale.xml_light"
        return "finale.xml_aucun"


def rang(texte: str) -> float:
    """« Finale 2006 » → 2006 ; « Finale v27 » / « 27.4 » → 2027 ; « 2014.5 » → 2014.5."""
    m = re.search(r"(?<!\d)(20\d\d)(?:\.(\d))?(?!\d)", texte)
    if m:
        return float(m.group(1)) + (int(m.group(2)) / 10 if m.group(2) else 0)
    m = re.search(r"(?:\bv|\s|^)(2[5-9]|3\d)(?:\.\d+)*\b", texte)
    if m:
        return 2000.0 + int(m.group(1))
    return 0.0


def _depuis_registre() -> list[Finale]:
    if sys.platform != "win32":
        return []
    import winreg
    trouves = []
    racines = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
               (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
               (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for ruche, chemin in racines:
        try:
            cle = winreg.OpenKey(ruche, chemin)
        except OSError:
            continue
        with cle:
            for i in range(winreg.QueryInfoKey(cle)[0]):
                try:
                    with winreg.OpenKey(cle, winreg.EnumKey(cle, i)) as sous:
                        nom = str(winreg.QueryValueEx(sous, "DisplayName")[0])
                        if "finale" not in nom.lower():
                            continue
                        def val(n):
                            try:
                                return str(winreg.QueryValueEx(sous, n)[0])
                            except OSError:
                                return ""
                        dossier = val("InstallLocation").strip('"')
                        icone = val("DisplayIcon").split(",")[0].strip('"')
                        exe = None
                        for candidat in ([Path(icone)] if icone.lower().endswith(".exe") else []) + (
                                [Path(dossier) / n for n in ("Finale.exe",)] if dossier else []):
                            if candidat.is_file() and "unins" not in candidat.name.lower():
                                exe = candidat
                                break
                        if exe is None and dossier:
                            exe = next(iter(sorted(Path(dossier).glob("Finale*.exe"))), None)
                        if exe:
                            trouves.append(Finale(nom=nom, exe=exe, version=val("DisplayVersion"),
                                                  rang=rang(nom) or rang(val("DisplayVersion"))))
                except OSError:
                    continue
    return trouves


def _depuis_dossiers() -> list[Finale]:
    bases = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
    trouves = []
    for base in filter(None, dict.fromkeys(bases)):
        b = Path(base)
        candidats = list(b.glob("Finale*/Finale*.exe")) + list(b.glob("MakeMusic/Finale/*/Finale*.exe"))
        for exe in candidats:
            if "unins" in exe.name.lower():
                continue
            nom = exe.parent.name if exe.parent.name.lower().startswith("finale") else \
                f"Finale {exe.parent.name}"
            trouves.append(Finale(nom=nom, exe=exe, rang=rang(nom) or rang(str(exe))))
    return trouves


def detecter() -> list[Finale]:
    """Les Finale du poste, du plus apte à l'export au moins apte."""
    vus: dict[str, Finale] = {}
    for f in _depuis_registre() + _depuis_dossiers():
        cle = os.path.normcase(str(f.exe))
        if cle not in vus or (not vus[cle].version and f.version):
            vus[cle] = f
    return trier(list(vus.values()))


def trier(liste: list[Finale]) -> list[Finale]:
    return sorted(liste, key=lambda f: (f.complet, f.rang), reverse=True)
