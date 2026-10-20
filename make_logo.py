#!/usr/bin/env python3
"""Logo de Da Capo : UNE source SVG (logo.svg), tout le reste en est rendu.

    QT_QPA_PLATFORM=offscreen python make_logo.py      (PyQt6 + Pillow)

Une page de partition sur fond vert sapin, cadre d'or : une portée, la barre
de reprise (double barre et deux points) et l'indication « D.C. » — da capo,
« reprendre depuis le début ». Les lettres sont converties en tracés (police
EB Garamond embarquée) : le SVG ne dépend d'aucune police installée.
Sorties : logo.svg, logo_{16..1024}.png, logo.png (= 256), logo.ico, logo.icns.
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
VERT, VERT_SOMBRE, OR, PAPIER, ENCRE = "#2C6E49", "#1D4F33", "#C9A227", "#FBF8F1", "#1E1A17"


def texte_en_chemin(texte: str, taille: float, x_centre: float, y_base: float) -> str:
    """Lettres → données de tracé SVG (« d »), centrées sur x_centre."""
    from PyQt6.QtGui import QFont, QFontDatabase, QPainterPath
    famille = "serif"
    ident = QFontDatabase.addApplicationFont(str(ICI / "dacapo" / "polices" / "EBGaramond-SemiBold.otf"))
    if ident >= 0:
        famille = QFontDatabase.applicationFontFamilies(ident)[0]
    f = QFont(famille)
    f.setPixelSize(int(taille))
    f.setWeight(QFont.Weight.DemiBold)
    chemin = QPainterPath()
    chemin.addText(0, 0, f, texte)
    r = chemin.boundingRect()
    dx, dy = x_centre - (r.left() + r.width() / 2), y_base
    d, i, n = [], 0, chemin.elementCount()
    while i < n:
        e = chemin.elementAt(i)
        if e.isMoveTo():
            d.append(f"M{e.x + dx:.1f} {e.y + dy:.1f}")
        elif e.isLineTo():
            d.append(f"L{e.x + dx:.1f} {e.y + dy:.1f}")
        elif e.isCurveTo():
            c1, c2 = chemin.elementAt(i + 1), chemin.elementAt(i + 2)
            d.append(f"C{e.x + dx:.1f} {e.y + dy:.1f} {c1.x + dx:.1f} {c1.y + dy:.1f} "
                     f"{c2.x + dx:.1f} {c2.y + dy:.1f}")
            i += 2
        i += 1
    return " ".join(d) + " Z"


def construire_svg() -> str:
    n = 512
    portee = "\n".join(f'<line x1="118" y1="{y}" x2="394" y2="{y}" stroke="{ENCRE}" stroke-width="3"/>'
                        for y in range(250, 250 + 5 * 22, 22))
    lettres = texte_en_chemin("D.C.", 104, 256, 200)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{n}" height="{n}" viewBox="0 0 {n} {n}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="fond" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{VERT}"/>
      <stop offset="100%" stop-color="{VERT_SOMBRE}"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="480" height="480" rx="96" fill="url(#fond)"/>
  <rect x="40" y="40" width="432" height="432" rx="76" fill="none" stroke="{OR}" stroke-width="5"/>
  <rect x="92" y="84" width="328" height="350" rx="16" fill="{PAPIER}" stroke="#D9CFBE" stroke-width="3"/>
  <path d="{lettres}" fill="{ENCRE}"/>
  {portee}
  <line x1="118" y1="250" x2="118" y2="338" stroke="{ENCRE}" stroke-width="3"/>
  <rect x="300" y="250" width="22" height="88" fill="{ENCRE}"/>
  <line x1="336" y1="250" x2="336" y2="338" stroke="{ENCRE}" stroke-width="5"/>
  <circle cx="358" cy="283" r="9" fill="{ENCRE}"/>
  <circle cx="358" cy="305" r="9" fill="{ENCRE}"/>
  <ellipse cx="176" cy="316" rx="17" ry="12" transform="rotate(-20 176 316)" fill="{ENCRE}"/>
  <rect x="189" y="246" width="5" height="70" fill="{ENCRE}"/>
  <ellipse cx="240" cy="283" rx="17" ry="12" transform="rotate(-20 240 283)" fill="{ENCRE}"/>
  <rect x="253" y="213" width="5" height="70" fill="{ENCRE}"/>
  <rect x="112" y="372" width="288" height="30" rx="10" fill="{OR}" stroke="#8C6E12" stroke-width="2"/>
</svg>
'''


def rendre(svg: Path, sortie: Path, taille: int) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer
    img = QImage(taille, taille, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    QSvgRenderer(str(svg)).render(p, QRectF(0, 0, taille, taille))
    p.end()
    img.save(str(sortie), "PNG")


def main():
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)  # noqa: F841 — requis pour le rendu (et les polices)
    svg = ICI / "logo.svg"
    svg.write_text(construire_svg(), encoding="utf-8")
    for taille in (16, 32, 64, 128, 256, 512, 1024):
        rendre(svg, ICI / f"logo_{taille}.png", taille)
    (ICI / "logo.png").write_bytes((ICI / "logo_256.png").read_bytes())
    from PIL import Image
    img = Image.open(ICI / "logo_1024.png").convert("RGBA")
    img.save(ICI / "logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                      (64, 64), (128, 128), (256, 256)])
    img.save(ICI / "logo.icns")
    print("logo.svg -> logo_*.png, logo.png, logo.ico, logo.icns")


if __name__ == "__main__":
    main()
