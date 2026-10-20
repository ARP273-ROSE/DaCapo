"""Petite boîte à outils Win32 (ctypes) pour piloter une application fenêtrée.

Aucune dépendance : pas de pywin32 ni de pywinauto, qui compliquent un
Python embarqué. On ne se sert que de messages Windows standard, que le
système transmet d'un processus à l'autre (WM_GETTEXT, WM_SETTEXT,
BM_CLICK, CB_*, WM_COMMAND) :

* les MENUS se lisent par GetMenu / GetMenuString et se déclenchent par
  WM_COMMAND, exactement comme un clic — sans dépendre de la position de la
  souris ni de la langue (on reconnaît les libellés français ET anglais) ;
* les BOÎTES DE DIALOGUE (classe « #32770 ») se lisent contrôle par
  contrôle ; un bouton se presse par BM_CLICK ;
* tout envoi passe par SendMessageTimeout : une application figée ne peut
  pas figer Da Capo.

Ce module ne s'importe que sous Windows ; ailleurs, `DISPONIBLE` vaut False.
"""
from __future__ import annotations

import sys
import time
import unicodedata
from dataclasses import dataclass, field

DISPONIBLE = sys.platform == "win32"

if DISPONIBLE:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowEnabled.argtypes = [wintypes.HWND]
    user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
    user32.GetMenu.argtypes = [wintypes.HWND]
    user32.GetMenu.restype = wintypes.HMENU
    user32.GetSubMenu.argtypes = [wintypes.HMENU, ctypes.c_int]
    user32.GetSubMenu.restype = wintypes.HMENU
    user32.GetMenuItemCount.argtypes = [wintypes.HMENU]
    user32.GetMenuItemID.argtypes = [wintypes.HMENU, ctypes.c_int]
    user32.GetMenuItemID.restype = wintypes.UINT
    user32.GetMenuStringW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR,
                                      ctypes.c_int, wintypes.UINT]
    user32.GetMenuState.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    user32.GetMenuState.restype = wintypes.UINT
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                           wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                           ctypes.POINTER(ctypes.c_size_t)]
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    kernel32.SetThreadExecutionState.restype = wintypes.DWORD

WM_SETTEXT, WM_GETTEXT, WM_GETTEXTLENGTH = 0x000C, 0x000D, 0x000E
WM_CLOSE, WM_COMMAND, WM_KEYDOWN, WM_KEYUP = 0x0010, 0x0111, 0x0100, 0x0101
BM_CLICK = 0x00F5
CB_GETCOUNT, CB_GETLBTEXT, CB_GETLBTEXTLEN, CB_SETCURSEL = 0x0146, 0x0148, 0x0149, 0x014E
CBN_SELCHANGE = 1
MF_BYPOSITION, MF_GRAYED, MF_DISABLED, MF_POPUP, MF_SEPARATOR = 0x400, 0x1, 0x2, 0x10, 0x800
SMTO_ABORTIFHUNG = 0x0002
GW_OWNER = 4
VK_RETURN, VK_ESCAPE = 0x0D, 0x1B
#: Champs « Nom du fichier » des boîtes Ouvrir / Enregistrer (cmb13, edt1)
#: et bouton par défaut (IDOK).
ID_NOM_FICHIER = (0x047C, 0x0480, 0x03E9)   # 1148, 1152, et 1001 (Enregistrer sous moderne)
IDOK, IDCANCEL = 1, 2


def normaliser(texte: str) -> str:
    """« &Ouvrir...\\tCtrl+O » → « ouvrir » : sans raccourci, sans &, sans
    points de suspension, sans accents, en minuscules."""
    texte = (texte or "").split("\t")[0].replace("&", "")
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.replace("…", "").strip().strip(".").strip().casefold()


# ----------------------------------------------------------------- fenêtres

def _envoyer(hwnd, msg, wparam=0, lparam=0, delai_ms=3000) -> int | None:
    resultat = ctypes.c_size_t(0)
    ok = user32.SendMessageTimeoutW(hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, delai_ms,
                                    ctypes.byref(resultat))
    return resultat.value if ok else None


def texte(hwnd) -> str:
    """Texte d'une fenêtre ou d'un contrôle, même d'un autre processus
    (GetWindowText ne lit pas les contrôles des autres processus)."""
    n = _envoyer(hwnd, WM_GETTEXTLENGTH) or 0
    if n <= 0:
        return ""
    tampon = ctypes.create_unicode_buffer(n + 1)
    _envoyer(hwnd, WM_GETTEXT, n + 1, ctypes.cast(tampon, ctypes.c_void_p).value)
    return tampon.value


def classe(hwnd) -> str:
    tampon = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, tampon, 256)
    return tampon.value


def pid_de(hwnd) -> int:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def visible(hwnd) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def actif(hwnd) -> bool:
    return bool(user32.IsWindowEnabled(hwnd))


def ident(hwnd) -> int:
    return user32.GetDlgCtrlID(hwnd)


def proprietaire(hwnd):
    return user32.GetWindow(hwnd, GW_OWNER)


def fenetres(pid: int | None = None, classe_voulue: str | None = None,
             visibles: bool = True) -> list[int]:
    """Fenêtres de premier niveau, filtrées par processus et par classe."""
    liste = []

    def rappel(hwnd, _):
        if visibles and not user32.IsWindowVisible(hwnd):
            return True
        if pid is not None and pid_de(hwnd) != pid:
            return True
        if classe_voulue is not None and classe(hwnd) != classe_voulue:
            return True
        liste.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(rappel), 0)
    return liste


def enfants(hwnd) -> list[int]:
    """Tous les descendants (EnumChildWindows parcourt toute la profondeur)."""
    liste = []

    def rappel(h, _):
        liste.append(h)
        return True

    user32.EnumChildWindows(hwnd, WNDENUMPROC(rappel), 0)
    return liste


def fermer(hwnd) -> None:
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def cliquer(bouton) -> None:
    # PostMessage : le clic peut ouvrir une boîte modale qui bloquerait un
    # SendMessage jusqu'à sa fermeture.
    user32.PostMessageW(bouton, BM_CLICK, 0, 0)


def touche(hwnd, vk) -> None:
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)


def ecrire(hwnd, valeur: str) -> bool:
    tampon = ctypes.create_unicode_buffer(valeur)
    return _envoyer(hwnd, WM_SETTEXT, 0, ctypes.cast(tampon, ctypes.c_void_p).value) is not None


def premier_plan(hwnd) -> None:
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def taille(hwnd) -> tuple[int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


# ----------------------------------------------------------------- dialogues

@dataclass
class Controle:
    hwnd: int
    classe: str
    ident: int
    texte: str
    visible: bool
    actif: bool


@dataclass
class Dialogue:
    hwnd: int
    titre: str
    pid: int
    controles: list[Controle] = field(default_factory=list)

    @property
    def message(self) -> str:
        """Le texte qu'affiche la boîte (contrôles statiques, sans les boutons)."""
        return " / ".join(c.texte for c in self.controles
                          if c.classe == "Static" and c.texte.strip() and c.visible)

    def boutons(self) -> list[Controle]:
        return [c for c in self.controles if c.classe == "Button" and c.visible and c.actif]

    def bouton(self, *libelles: str) -> Controle | None:
        """Premier bouton dont le libellé normalisé est l'un de `libelles`
        (dans l'ordre de préférence donné)."""
        bs = self.boutons()
        for voulu in libelles:
            for b in bs:
                if normaliser(b.texte) == voulu:
                    return b
        return None

    def par_ident(self, *idents: int) -> Controle | None:
        for i in idents:
            for c in self.controles:
                if c.ident == i and c.visible:
                    return c
        return None

    def description(self) -> str:
        lignes = [f"[{self.titre}] pid={self.pid}"]
        for c in self.controles:
            if c.visible and (c.texte.strip() or c.classe in ("Edit", "ComboBox", "ComboBoxEx32")):
                lignes.append(f"   {c.classe:<14} id={c.ident:<6} {'' if c.actif else '(grisé) '}{c.texte[:120]!r}")
        return "\n".join(lignes)


def lire_dialogue(hwnd) -> Dialogue:
    d = Dialogue(hwnd=hwnd, titre=texte(hwnd), pid=pid_de(hwnd))
    for h in enfants(hwnd):
        d.controles.append(Controle(h, classe(h), ident(h), texte(h), visible(h), actif(h)))
    return d


def dialogues(pid: int | None = None) -> list[Dialogue]:
    """Boîtes de dialogue visibles (classe #32770), d'un processus ou de tous."""
    return [lire_dialogue(h) for h in fenetres(pid=pid, classe_voulue="#32770")]


def champ_nom_fichier(d: Dialogue) -> int | None:
    """Le champ où taper le chemin dans une boîte Ouvrir / Enregistrer sous,
    ancienne (Edit id 1152) ou moderne (ComboBox id 1148 contenant un Edit)."""
    c = d.par_ident(*ID_NOM_FICHIER)
    if c is not None:
        if c.classe == "Edit":
            return c.hwnd
        for h in enfants(c.hwnd):
            if classe(h) == "Edit":
                return h
    # Repli : la boîte moderne (IFileDialog) loge le nom du fichier dans un
    # Edit enfant d'une liste déroulante ; à défaut, le premier Edit visible
    # d'une boîte qui a un bouton OK — mais jamais celui de la barre
    # d'adresse ni de la recherche (enfants de classes de l'Explorateur).
    if d.par_ident(IDOK) is None:
        return None
    edits = [c for c in d.controles if c.classe == "Edit" and c.visible and c.actif]
    for e in edits:
        if classe(user32.GetParent(e.hwnd)) in ("ComboBox", "ComboBoxEx32"):
            return e.hwnd
    for e in edits:
        if classe(user32.GetParent(e.hwnd)) not in ("Breadcrumb Parent", "SearchEditBoxWrapperClass",
                                                     "UniversalSearchBand", "ToolbarWindow32"):
            return e.hwnd
    return None


def remplir_et_valider(d: Dialogue, chemin: str) -> bool:
    champ = champ_nom_fichier(d)
    if champ is None:
        return False
    ecrire(champ, chemin)
    ok = d.par_ident(IDOK)
    if ok is not None:
        cliquer(ok.hwnd)
    else:
        touche(champ, VK_RETURN)
    return True


def choisir_dans_liste(combo: int, morceau: str) -> bool:
    """Sélectionne dans une liste déroulante le premier élément qui contient
    `morceau` (imprimante « CutePDF Writer »…), et prévient la boîte."""
    n = _envoyer(combo, CB_GETCOUNT) or 0
    voulu = normaliser(morceau)
    for i in range(n):
        lg = _envoyer(combo, CB_GETLBTEXTLEN, i) or 0
        if lg <= 0 or lg > 1024:
            continue
        tampon = ctypes.create_unicode_buffer(lg + 1)
        _envoyer(combo, CB_GETLBTEXT, i, ctypes.cast(tampon, ctypes.c_void_p).value)
        if voulu in normaliser(tampon.value):
            _envoyer(combo, CB_SETCURSEL, i)
            parent = user32.GetParent(combo)
            user32.PostMessageW(parent, WM_COMMAND, (CBN_SELCHANGE << 16) | ident(combo), combo)
            return True
    return False


# ----------------------------------------------------------------- menus

@dataclass
class Entree:
    chemin: tuple[str, ...]      # libellés normalisés, du menu principal à l'entrée
    brut: tuple[str, ...]        # libellés tels qu'affichés
    commande: int
    grisee: bool


def menus(hwnd) -> list[Entree]:
    """Toutes les entrées de la barre de menus, sous-menus compris."""
    entrees: list[Entree] = []

    def parcourir(hmenu, chemin, brut, profondeur):
        if not hmenu or profondeur > 6:
            return
        n = user32.GetMenuItemCount(hmenu)
        for i in range(max(0, n)):
            tampon = ctypes.create_unicode_buffer(512)
            user32.GetMenuStringW(hmenu, i, tampon, 512, MF_BYPOSITION)
            libelle = tampon.value
            etat = user32.GetMenuState(hmenu, i, MF_BYPOSITION)
            if etat & MF_SEPARATOR and not libelle:
                continue
            sous = user32.GetSubMenu(hmenu, i)
            if sous:
                parcourir(sous, chemin + (normaliser(libelle),), brut + (libelle,), profondeur + 1)
            elif libelle:
                entrees.append(Entree(chemin + (normaliser(libelle),), brut + (libelle,),
                                      user32.GetMenuItemID(hmenu, i),
                                      bool(etat & (MF_GRAYED | MF_DISABLED))))

    parcourir(user32.GetMenu(hwnd), (), (), 0)
    return entrees


def commande(hwnd, ident_commande: int) -> None:
    user32.PostMessageW(hwnd, WM_COMMAND, ident_commande & 0xFFFF, 0)


# ----------------------------------------------------------------- divers

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def empecher_veille(oui: bool) -> None:
    """Pendant un long export, l'ordinateur ne doit pas se mettre en veille."""
    if DISPONIBLE:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if oui else 0))


def attendre(condition, delai: float, pas: float = 0.25):
    """Appelle `condition()` jusqu'à ce qu'elle rende une valeur vraie, ou
    jusqu'au délai ; renvoie cette valeur (ou None)."""
    fin = time.monotonic() + delai
    while True:
        v = condition()
        if v:
            return v
        if time.monotonic() >= fin:
            return None
        time.sleep(pas)
