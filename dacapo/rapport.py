"""rapport.html : le bilan à relire, partition par partition.

Une page autonome (aucun fichier externe, aucun script), lisible dans
n'importe quel navigateur, avec des liens relatifs vers les fichiers
produits : on peut déplacer ou copier tout le dossier de travail, les liens
suivent. Les partitions qui demandent un coup d'œil sont en tête.
"""
from __future__ import annotations

import html
import os
from datetime import datetime
from pathlib import Path

from . import __version__, inventaire
from .i18n import tr
from .inventaire import Journal


def _lien(travail: Path, chemin: Path, texte: str) -> str:
    if not chemin.exists():
        return ""
    rel = os.path.relpath(chemin, travail).replace(os.sep, "/")
    from urllib.parse import quote
    return f'<a href="{html.escape(quote(rel))}">{html.escape(texte)}</a>'


def _gravite(f) -> int:
    """0 = à regarder en premier, 2 = tout va bien."""
    if any(v == "echec" for v in f.etats.values()):
        return 0
    if (f.mesure or {}).get("suspect") or f.details.get("imprevus"):
        return 1
    return 2


def ecrire(travail: Path, journal: Journal, rels: list[str]) -> Path:
    travail = Path(travail)
    fiches = [journal.fiches[r] for r in rels if r in journal.fiches]
    fiches.sort(key=lambda f: (_gravite(f), f.rel.casefold()))
    compte = {k: sum(1 for f in fiches if f.fait(k)) for k in inventaire.ETAPES}
    echecs = sum(1 for f in fiches if _gravite(f) == 0)
    a_voir = sum(1 for f in fiches if _gravite(f) == 1)

    lignes = []
    for f in fiches:
        m = f.mesure or {}
        classe = ("echec", "voir", "ok")[_gravite(f)]
        if f.fait("musicxml"):
            contenu = tr("rapport.contenu", p=len(m.get("parties", [])), m=m.get("mesures", 0),
                         n=m.get("notes", 0))
            if m.get("paroles"):
                contenu += tr("rapport.paroles", n=m["paroles"])
            xml = _lien(travail, inventaire.chemin_sortie(travail, f.rel, "musicxml", ".musicxml"),
                        "MusicXML") + f"<br><small>{html.escape(contenu)}</small>"
        else:
            xml = f'<span class="non">{html.escape(tr("rapport.etat." + f.etats.get("musicxml", "absent")))}</span>'
        pdf = _lien(travail, inventaire.chemin_sortie(travail, f.rel, "pdf-finale", ".pdf"), "PDF")
        ms = " · ".join(x for x in (
            _lien(travail, inventaire.chemin_sortie(travail, f.rel, "musescore", ".mscz"), "MuseScore"),
            _lien(travail, inventaire.chemin_sortie(travail, f.rel, "musescore", ".pdf"), "PDF"))
            if x)
        remarques = []
        if m.get("suspect"):
            remarques.append(tr("rapport.suspect." + m["suspect"]))
        for etape in ("copie", "musicxml", "pdf", "musescore"):
            if f.etats.get(etape) == "echec":
                remarques.append(tr("rapport.echec", etape=tr("rapport.etape." + etape),
                                    detail=tr_code(f.details.get(etape, ""))))
        if f.details.get("imprevus"):
            remarques.append(tr("rapport.imprevus", detail=f.details["imprevus"][:400]))
        lignes.append(
            f'<tr class="{classe}"><td>{html.escape(f.rel)}<br>'
            f'{_lien(travail, inventaire.copie(travail, f.rel), tr("rapport.original"))}</td>'
            f"<td>{xml}</td><td>{pdf}</td><td>{ms}</td>"
            f"<td>{'<br>'.join(html.escape(r) for r in remarques)}</td></tr>")

    page = f"""<!doctype html>
<html lang="{tr('rapport.lang')}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(tr('rapport.titre'))}</title>
<style>
:root {{ --papier:#FBF8F1; --encre:#2A2420; --vert:#2C6E49; --rouge:#B5382B; --or:#B8860B; --bord:#D9CFBE; }}
body {{ background:var(--papier); color:var(--encre); font:15px/1.45 "Segoe UI",system-ui,sans-serif;
       margin:0 auto; max-width:1200px; padding:16px; }}
h1 {{ font-family:Georgia,serif; color:var(--vert); margin:.2em 0; }}
.bilan {{ display:flex; flex-wrap:wrap; gap:10px; margin:12px 0 18px; }}
.bilan div {{ background:#fff; border:1px solid var(--bord); border-radius:8px; padding:8px 14px; }}
.bilan b {{ font-size:20px; display:block; }}
table {{ border-collapse:collapse; width:100%; background:#fff; }}
th, td {{ border-bottom:1px solid var(--bord); padding:6px 8px; text-align:left; vertical-align:top; }}
th {{ background:#EFE8D8; position:sticky; top:0; }}
tr.echec td:first-child {{ border-left:5px solid var(--rouge); }}
tr.voir td:first-child {{ border-left:5px solid var(--or); }}
tr.ok td:first-child {{ border-left:5px solid var(--vert); }}
.non {{ color:var(--rouge); font-weight:600; }}
small {{ color:#6b625a; }}
a {{ color:var(--vert); }}
p.aide {{ max-width:70em; }}
</style></head><body>
<h1>{html.escape(tr('rapport.titre'))}</h1>
<p>{html.escape(tr('rapport.genere', date=datetime.now().strftime('%d/%m/%Y %H:%M'), version=__version__))}</p>
<div class="bilan">
<div><b>{len(fiches)}</b>{html.escape(tr('rapport.partitions'))}</div>
<div><b>{compte['musicxml']}</b>MusicXML</div>
<div><b>{compte['pdf']}</b>{html.escape(tr('rapport.pdf_ref'))}</div>
<div><b>{compte['musescore']}</b>MuseScore</div>
<div><b>{echecs}</b>{html.escape(tr('rapport.nb_echecs'))}</div>
<div><b>{a_voir}</b>{html.escape(tr('rapport.nb_voir'))}</div>
</div>
<p class="aide">{html.escape(tr('rapport.aide'))}</p>
<table><thead><tr><th>{html.escape(tr('rapport.col.partition'))}</th><th>MusicXML</th>
<th>{html.escape(tr('rapport.col.pdf'))}</th><th>MuseScore</th><th>{html.escape(tr('rapport.col.remarques'))}</th></tr></thead>
<tbody>
{chr(10).join(lignes)}
</tbody></table>
</body></html>
"""
    sortie = travail / "rapport.html"
    tmp = sortie.with_suffix(".html.tmp")
    tmp.write_text(page, encoding="utf-8")
    os.replace(tmp, sortie)
    return sortie


def tr_code(code: str) -> str:
    """Code d'échec technique (« export:musicxml », « boite_fichier »…) → phrase."""
    base = (code or "").split(":")[0]
    cle = f"code.{base}"
    texte = tr(cle)
    return code if texte == cle else texte
