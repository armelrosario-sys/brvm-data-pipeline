#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANTIER 1 — Blocs d'affichage des signaux (le "film") dans le dashboard.

Genere deux cartes injectees EN TETE du dashboard (avant les onglets) :
  1. "Ma liste de suivi" : les tickers de liste_suivi avec leurs signaux
     ACTIFS, defavorables toujours au-dessus des favorables.
  2. "Signaux actifs — marche" : tous les signaux ACTIFS, dates et sources.
Aucune donnee personnelle : la liste de suivi ne contient que des codes.

Usage : python3 bloc_signaux.py   (apres generer_dashboard_html.py)
"""
import sqlite3
from pathlib import Path

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
.sig-def { color: #f87171; font-weight: 600; }
.sig-fav { color: #34d399; font-weight: 600; }
.sig-ras { color: var(--muted, #94a3b8); }
.sig-date { color: var(--muted, #94a3b8); font-size: 0.85em; white-space: nowrap; }
.sig-note { color: var(--muted, #94a3b8); font-size: 0.82em; margin-top: 8px; }
</style>
"""


def _signaux_actifs(cur):
    return cur.execute(
        "SELECT ticker, type, direction, detail, date_detection, source_donnee "
        "FROM signaux WHERE statut='ACTIF' "
        "ORDER BY CASE direction WHEN 'DEFAVORABLE' THEN 0 ELSE 1 END, ticker, type"
    ).fetchall()


def generer_blocs():
    cur = sqlite3.connect(DB).cursor()
    suivi = [r[0] for r in cur.execute("SELECT ticker FROM liste_suivi ORDER BY ticker")]
    actifs = _signaux_actifs(cur)
    par_ticker = {}
    for t, ty, di, de, dd, so in actifs:
        par_ticker.setdefault(t, []).append((ty, di, de, dd, so))

    # ---- Bloc 1 : liste de suivi (defavorables d'abord, deja trie) ----
    lignes = []
    for t in suivi:
        sigs = par_ticker.get(t, [])
        if not sigs:
            lignes.append(f"<tr><td><b>{t}</b></td>"
                          f"<td class='sig-ras'>RAS</td><td></td><td></td></tr>")
        for ty, di, de, dd, so in sigs:
            cls = "sig-def" if di == "DEFAVORABLE" else "sig-fav"
            lignes.append(f"<tr><td><b>{t}</b></td><td class='{cls}'>{ty}</td>"
                          f"<td>{de}</td><td class='sig-date'>depuis le {dd}</td></tr>")
    bloc1 = f"""
<div class="sig-carte">
  <h2>Ma liste de suivi <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({len(suivi)} titres — codes seuls, aucune donnee personnelle)</span></h2>
  <table class="sig-table">
    <thead><tr><th>Titre</th><th>Signal</th><th>Detail</th><th>Depuis</th></tr></thead>
    <tbody>{''.join(lignes)}</tbody>
  </table>
  <div class="sig-note">Regle d'escalade : deux signaux defavorables simultanes sur un
  titre suivi = revue obligatoire sous 10 seances, decision ecrite au journal.
  Le systeme ne decide jamais seul.</div>
</div>"""

    # ---- Bloc 2 : tous les signaux actifs du marche ----
    lignes2 = []
    for t, ty, di, de, dd, so in actifs:
        cls = "sig-def" if di == "DEFAVORABLE" else "sig-fav"
        lignes2.append(f"<tr><td><b>{t}</b></td><td class='{cls}'>{ty}</td>"
                       f"<td>{de}</td><td class='sig-date'>{dd}</td>"
                       f"<td class='sig-date'>{so or ''}</td></tr>")
    nb_def = sum(1 for a in actifs if a[2] == "DEFAVORABLE")
    bloc2 = f"""
<div class="sig-carte">
  <h2>Signaux actifs — marche <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({len(actifs)} actifs, dont {nb_def} defavorables — cycle de vie date, distinct des scores)</span></h2>
  <table class="sig-table">
    <thead><tr><th>Titre</th><th>Signal</th><th>Detail</th><th>Detecte le</th><th>Source</th></tr></thead>
    <tbody>{''.join(lignes2)}</tbody>
  </table>
</div>"""
    return STYLE + bloc1 + bloc2


def injecter():
    html = HTML.read_text(encoding="utf-8")
    ancre = '<div class="onglets">'
    if ancre not in html:
        raise SystemExit("Ancre d'injection introuvable — dashboard non genere ?")
    # idempotence : retirer une injection precedente
    marque_deb, marque_fin = "<!-- BLOCS-SIGNAUX -->", "<!-- /BLOCS-SIGNAUX -->"
    if marque_deb in html:
        avant = html[:html.index(marque_deb)]
        apres = html[html.index(marque_fin) + len(marque_fin):]
        html = avant + apres
    blocs = marque_deb + generer_blocs() + marque_fin + "\n  "
    html = html.replace(ancre, blocs + ancre, 1)
    HTML.write_text(html, encoding="utf-8")
    print(f"Blocs signaux injectes dans {HTML.name} (liste de suivi en premier).")


if __name__ == "__main__":
    injecter()
