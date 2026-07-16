#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANTIER 1 — Blocs d'affichage des signaux (le "film") dans le dashboard.

v3 (15/07/2026) — colonnes distinctes, resume capital toujours visible :
  - retour utilisateur : le texte de detail (blanc, non structure, en ligne
    avec le badge) etait difficile a lire, sans intitule de colonne, sans
    mise en evidence de l'information essentielle.
  - refonte : une ligne PAR SIGNAL (pas par titre), le ticker fusionne sur
    plusieurs lignes (rowspan) quand un titre porte plusieurs signaux --
    conserve l'objectif du v2 (ne pas repeter le ticker inutilement) tout en
    donnant a chaque signal sa propre ligne, plus lisible qu'un empilement
    de divs dans une seule cellule.
  - 3 colonnes distinctes : Signal (badge) | Essentiel (gras, centre, TOUJOURS
    visible -- cf. glossaire_signaux.resume_capital) | Detail (texte justifie,
    attenue, la phrase complete).
  - nettoyage : la fonction _prochaines_echeances (calendrier) etait devenue
    du code mort ici depuis son deplacement vers generer_dashboard_html.py
    (le calendrier s'affiche desormais en bas de la Synthese) -- retiree.

Genere trois cartes injectees EN TETE du dashboard (avant les onglets) :
  1. "Ma liste de suivi" : les tickers de liste_suivi avec leurs signaux ACTIFS.
  2. "Signaux actifs — marche" : tous les signaux ACTIFS, groupes par titre.
  3. "Introductions et cotations à venir".
Aucune donnee personnelle : la liste de suivi ne contient que des codes.

Usage : python3 bloc_signaux.py   (apres generer_dashboard_html.py)
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glossaire_signaux import badge_html, resume_capital

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
.sig-table td { padding: 7px 8px; border-bottom: 1px solid rgba(148,163,184,.15); vertical-align: middle; }
.sig-table td.sig-ticker-cell { vertical-align: top; border-right: 1px solid rgba(148,163,184,.15); }
.sig-def { display:inline-block; background:#3f1d1d; color:#f87171; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; white-space:nowrap; }
.sig-fav { display:inline-block; background:#173f2e; color:#34d399; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; white-space:nowrap; }
.sig-info { display:inline-block; background:#1e3a5f; color:#60a5fa; font-weight:600;
  padding:1px 8px; border-radius:99px; font-size:0.85em; white-space:nowrap; }
.sig-essentiel { text-align: center; font-weight: 700; color: var(--text, #e2e8f0);
  font-size: 0.95em; white-space: nowrap; }
.sig-detail { color: var(--muted, #94a3b8); font-size: 0.87em; text-align: justify; line-height: 1.4; }
.sig-ras { color: var(--muted, #94a3b8); }
.sig-note { color: var(--muted, #94a3b8); font-size: 0.82em; margin-top: 8px; }
.sig-col-optionnelle { display: none; }
.sig-col-optionnelle.visible { display: table-cell; }
.sig-toggle { background: none; border: 1px solid var(--border, #334155); color: var(--muted, #94a3b8);
  border-radius: 6px; padding: 3px 10px; font-size: 0.78em; cursor: pointer; margin-bottom: 8px; }
.sig-toggle:hover { color: var(--text, #e2e8f0); border-color: var(--muted, #94a3b8); }
.sig-note-cell { color: var(--muted, #94a3b8); font-size: 0.85em; }
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


def _lignes_ticker(t, sigs, avec_source):
    """Une ligne PAR SIGNAL pour ce ticker ; le ticker n'apparait qu'une
    fois, fusionne (rowspan) sur toutes ses lignes."""
    n = len(sigs)
    lignes = []
    for i, (ty, di, de, dd, so) in enumerate(sigs):
        essentiel = resume_capital(ty, de) or ""
        col_date_source = f"{dd} — {so or ''}" if avec_source else f"depuis le {dd}"
        cell_ticker = f"<td class='sig-ticker-cell' rowspan='{n}'><b>{t}</b></td>" if i == 0 else ""
        lignes.append(
            f"<tr>{cell_ticker}"
            f"<td>{badge_html(ty)}</td>"
            f"<td class='sig-essentiel'>{essentiel}</td>"
            f"<td class='sig-detail'>{de}</td>"
            f"<td class='sig-col-optionnelle sig-date'>{col_date_source}</td></tr>"
        )
    return lignes


def generer_blocs():
    cur = sqlite3.connect(DB).cursor()
    suivi = [r[0] for r in cur.execute("SELECT ticker FROM liste_suivi ORDER BY ticker")]
    actifs = _signaux_actifs(cur)
    par_ticker = {}
    for t, ty, di, de, dd, so in actifs:
        par_ticker.setdefault(t, []).append((ty, di, de, dd, so))

    en_tete_signaux = ("<thead><tr><th>Titre</th><th>Signal</th><th>Essentiel</th>"
                       "<th>Détail</th><th class=\"sig-col-optionnelle\">Depuis</th></tr></thead>")
    en_tete_marche = ("<thead><tr><th>Titre</th><th>Signal</th><th>Essentiel</th>"
                      "<th>Détail</th><th class=\"sig-col-optionnelle\">Detecte le — Source</th></tr></thead>")

    # ---- Bloc 1 : liste de suivi ----
    lignes = []
    for t in suivi:
        sigs = par_ticker.get(t, [])
        if not sigs:
            lignes.append(f"<tr><td class='sig-ticker-cell'><b>{t}</b></td>"
                          f"<td colspan='3' class='sig-ras'>RAS</td>"
                          f"<td class='sig-col-optionnelle'></td></tr>")
            continue
        lignes.extend(_lignes_ticker(t, sigs, avec_source=False))
    if suivi:
        corps_suivi = f"""<table class="sig-table" id="tbl-suivi">
    {en_tete_signaux}
    <tbody>{''.join(lignes)}</tbody>
  </table>"""
    else:
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

    # ---- Bloc 2 : tous les signaux actifs du marche ----
    lignes2 = []
    for t in sorted(par_ticker, key=lambda tk: (
            0 if any(s[1] == "DEFAVORABLE" for s in par_ticker[tk]) else 1, tk)):
        lignes2.extend(_lignes_ticker(t, par_ticker[t], avec_source=True))
    nb_def = sum(1 for a in actifs if a[2] == "DEFAVORABLE")
    nb_titres_actifs = len(par_ticker)
    bloc2 = f"""
<div class="sig-carte">
  <h2>Signaux actifs — marche <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({nb_titres_actifs} titres concernes, {len(actifs)} signaux dont {nb_def} defavorables
      — cycle de vie date, distinct des scores)</span></h2>
  <button class="sig-toggle" onclick="sigToggleColonnes('tbl-marche', this)">Afficher les dates et sources</button>
  <table class="sig-table" id="tbl-marche">
    {en_tete_marche}
    <tbody>{''.join(lignes2)}</tbody>
  </table>
</div>"""

    # ---- Bloc 3 : introductions et cotations a venir ----
    intro = cur.execute(
        "SELECT ticker, nom, secteur, date_introduction, controle_actionnarial "
        "FROM societes WHERE ticker NOT LIKE 'TEST_%' AND ticker NOT IN "
        "(SELECT DISTINCT ticker FROM cours_mensuels)").fetchall()
    bloc3 = ""
    if intro:
        lignes3 = []
        for t, nom, sec, date_intro, note in intro:
            statut = f"cotation prevue le {date_intro}" if date_intro else "date de cotation a preciser"
            lignes3.append(f"<tr><td><b>{t}</b></td><td>{nom}</td><td>{sec.replace('_',' ').title()}</td>"
                          f"<td>{statut}</td><td class='sig-note-cell'>{note or ''}</td></tr>")
        bloc3 = f"""
<div class="sig-carte">
  <h2>Introductions et cotations à venir <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({len(intro)} titre{'s' if len(intro)>1 else ''} — pas encore de cours, distinct d'une exclusion)</span></h2>
  <table class="sig-table">
    <thead><tr><th>Titre</th><th>Nom</th><th>Secteur</th><th>Statut</th><th>Note</th></tr></thead>
    <tbody>{''.join(lignes3)}</tbody>
  </table>
  <div class="sig-note">Absence de cours = pas encore cote, pas un probleme de donnee ni un risque --
  ce titre rejoindra les autres tableaux des que ses premieres cotations seront collectees.</div>
</div>"""

    return STYLE + bloc1 + bloc2 + bloc3


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
    print(f"Blocs signaux injectes dans {HTML.name} (colonnes distinctes, essentiel toujours visible).")


if __name__ == "__main__":
    injecter()
