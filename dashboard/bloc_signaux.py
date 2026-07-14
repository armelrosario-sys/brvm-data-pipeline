#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANTIER 1 — Blocs d'affichage des signaux (le "film") dans le dashboard.

v2 (14/07/2026) — corrections suite au retour utilisateur sur la v1 :
  - regroupement par titre (une entreprise = une ligne, plusieurs signaux
    empiles dans la cellule) au lieu d'une ligne par signal (SNTS apparaissait
    deux fois, source de confusion) ;
  - colonnes "Detecte le" / "Depuis" / "Source" repliables (toggle), pas
    supprimees : disponibles en un clic, pas genantes par defaut ;
  - libelles clairs via glossaire_signaux (fini les codes SCREAMING_SNAKE_CASE
    bruts melanges a du texte en minuscules).

Genere deux cartes injectees EN TETE du dashboard (avant les onglets) :
  1. "Ma liste de suivi" : les tickers de liste_suivi avec leurs signaux ACTIFS.
  2. "Signaux actifs — marche" : tous les signaux ACTIFS, groupes par titre.
Aucune donnee personnelle : la liste de suivi ne contient que des codes.

Usage : python3 bloc_signaux.py   (apres generer_dashboard_html.py)
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glossaire_signaux import badge_html

DB = Path(__file__).resolve().parent.parent / "moteur" / "brvm.db"
HTML = Path(__file__).resolve().parent.parent / "docs_site" / "index.html"

STYLE = """
<style>
.sig-carte { background: var(--card, #1e293b); border: 1px solid var(--border, #334155);
  border-radius: 10px; padding: 16px 18px; margin-bottom: 16px; }
.sig-carte h2 { margin: 0 0 10px; font-size: 1.05em; }
.sig-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
.sig-table th { text-align: left; color: var(--muted, #94a3b8); font-weight: 500;
  padding: 6px 8px; border-bottom: 1px solid var(--border, #334155); }
.sig-table td { padding: 7px 8px; border-bottom: 1px solid rgba(148,163,184,.15); vertical-align: top; }
.sig-ligne-signal { margin: 2px 0; }
.sig-def { display:inline-block; background:#3f1d1d; color:#f87171; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; }
.sig-fav { display:inline-block; background:#173f2e; color:#34d399; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; }
.sig-info { display:inline-block; background:#1e3a5f; color:#60a5fa; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; }
.sig-detail { color: var(--text, #e2e8f0); font-size: 0.92em; margin-left: 6px; }
.sig-ras { color: var(--muted, #94a3b8); }
.sig-note { color: var(--muted, #94a3b8); font-size: 0.82em; margin-top: 8px; }
.sig-col-optionnelle { display: none; }
.sig-col-optionnelle.visible { display: table-cell; }
.sig-toggle { background: none; border: 1px solid var(--border, #334155); color: var(--muted, #94a3b8);
  border-radius: 6px; padding: 3px 10px; font-size: 0.78em; cursor: pointer; margin-bottom: 8px; }
.sig-toggle:hover { color: var(--text, #e2e8f0); border-color: var(--muted, #94a3b8); }
</style>
<script>
function sigToggleColonnes(tableId, btn) {
  const cols = document.querySelectorAll('#' + tableId + ' .sig-col-optionnelle');
  const visible = cols.length && cols[0].classList.contains('visible');
  cols.forEach(c => c.classList.toggle('visible', !visible));
  btn.textContent = visible ? 'Afficher les dates et sources' : 'Masquer les dates et sources';
}
</script>
"""


def _signaux_actifs(cur):
    return cur.execute(
        "SELECT ticker, type, direction, detail, date_detection, source_donnee "
        "FROM signaux WHERE statut='ACTIF' "
        "ORDER BY CASE direction WHEN 'DEFAVORABLE' THEN 0 ELSE 1 END, ticker, type"
    ).fetchall()


def _ligne_signal(ty, de):
    """Une ligne compacte : badge (libelle clair, code en info-bulle) + detail."""
    return f'<div class="sig-ligne-signal">{badge_html(ty)}<span class="sig-detail">{de}</span></div>'


def generer_blocs():
    cur = sqlite3.connect(DB).cursor()
    suivi = [r[0] for r in cur.execute("SELECT ticker FROM liste_suivi ORDER BY ticker")]
    actifs = _signaux_actifs(cur)
    par_ticker = {}
    for t, ty, di, de, dd, so in actifs:
        par_ticker.setdefault(t, []).append((ty, di, de, dd, so))

    # ---- Bloc 1 : liste de suivi — UNE LIGNE PAR TITRE ----
    lignes = []
    for t in suivi:
        sigs = par_ticker.get(t, [])
        if not sigs:
            lignes.append(f"<tr><td><b>{t}</b></td><td class='sig-ras'>RAS</td>"
                          f"<td class='sig-col-optionnelle'></td></tr>")
            continue
        corps_signaux = "".join(_ligne_signal(ty, de) for ty, di, de, dd, so in sigs)
        depuis_txt = "; ".join(f"depuis le {dd}" for _, _, _, dd, _ in sigs)
        lignes.append(f"<tr><td><b>{t}</b></td><td>{corps_signaux}</td>"
                      f"<td class='sig-col-optionnelle sig-date'>{depuis_txt}</td></tr>")
    if suivi:
        corps_suivi = f"""<table class="sig-table" id="tbl-suivi">
    <thead><tr><th>Titre</th><th>Signaux actifs</th><th class="sig-col-optionnelle">Depuis</th></tr></thead>
    <tbody>{''.join(lignes)}</tbody>
  </table>"""
    else:
        # Amelioration ergonomique (14/07/2026) : une table vide sans explication
        # ressemble a un bug. Etat vide explicite avec la marche a suivre.
        corps_suivi = ("""<div style="padding:16px;text-align:center;color:var(--muted,#94a3b8);"""
                       """border:1px dashed var(--border,#334155);border-radius:8px;">"""
                       """Aucun titre dans la liste de suivi pour l'instant.<br>"""
                       """<span style="font-size:0.85em">Ajoute des codes (ex. SNTS, CBIBF) dans"""
                       """ <code>config/liste_suivi.yaml</code> pour que ce tableau se peuple"""
                       """ automatiquement au prochain calcul.</span></div>""")
    bloc1 = f"""
<div class="sig-carte">
  <h2>Ma liste de suivi <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({len(suivi)} titres — codes seuls, aucune donnee personnelle)</span></h2>
  <button class="sig-toggle" onclick="sigToggleColonnes('tbl-suivi', this)">Afficher les dates et sources</button>
  {corps_suivi}
  <div class="sig-note">Regle d'escalade : deux signaux defavorables simultanes sur un
  titre suivi = revue obligatoire sous 10 seances, decision ecrite au journal.
  Le systeme ne decide jamais seul. Survolez un badge pour le code technique et sa definition.</div>
</div>"""

    # ---- Bloc 2 : tous les signaux actifs du marche — UNE LIGNE PAR TITRE ----
    lignes2 = []
    for t in sorted(par_ticker, key=lambda tk: (
            0 if any(s[1] == "DEFAVORABLE" for s in par_ticker[tk]) else 1, tk)):
        sigs = par_ticker[t]
        corps_signaux = "".join(_ligne_signal(ty, de) for ty, di, de, dd, so in sigs)
        dates_sources = "<br>".join(f"{dd} — {so or ''}" for _, _, _, dd, so in sigs)
        lignes2.append(f"<tr><td><b>{t}</b></td><td>{corps_signaux}</td>"
                       f"<td class='sig-col-optionnelle sig-date'>{dates_sources}</td></tr>")
    nb_def = sum(1 for a in actifs if a[2] == "DEFAVORABLE")
    nb_titres_actifs = len(par_ticker)
    bloc2 = f"""
<div class="sig-carte">
  <h2>Signaux actifs — marche <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({nb_titres_actifs} titres concernes, {len(actifs)} signaux dont {nb_def} defavorables
      — cycle de vie date, distinct des scores)</span></h2>
  <button class="sig-toggle" onclick="sigToggleColonnes('tbl-marche', this)">Afficher les dates et sources</button>
  <table class="sig-table" id="tbl-marche">
    <thead><tr><th>Titre</th><th>Signaux actifs</th><th class="sig-col-optionnelle">Detecte le — Source</th></tr></thead>
    <tbody>{''.join(lignes2)}</tbody>
  </table>
</div>"""
    return STYLE + bloc1 + bloc2


def injecter():
    html = HTML.read_text(encoding="utf-8")
    ancre = '<div class="onglets">'
    if ancre not in html:
        raise SystemExit("Ancre d'injection introuvable — dashboard non genere ?")
    marque_deb, marque_fin = "<!-- BLOCS-SIGNAUX -->", "<!-- /BLOCS-SIGNAUX -->"
    if marque_deb in html:
        avant = html[:html.index(marque_deb)]
        apres = html[html.index(marque_fin) + len(marque_fin):]
        html = avant + apres
    blocs = marque_deb + generer_blocs() + marque_fin + "\n  "
    html = html.replace(ancre, blocs + ancre, 1)
    HTML.write_text(html, encoding="utf-8")
    print(f"Blocs signaux injectes dans {HTML.name} (groupes par titre, colonnes repliables).")


if __name__ == "__main__":
    injecter()
