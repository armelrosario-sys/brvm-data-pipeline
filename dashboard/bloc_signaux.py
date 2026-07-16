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
import json
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
    tous_tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]
    actifs = _signaux_actifs(cur)
    par_ticker = {}
    for t, ty, di, de, dd, so in actifs:
        par_ticker.setdefault(t, []).append((ty, di, de, dd, so))

    en_tete_signaux = ("<thead><tr><th>Titre</th><th>Signal</th><th>Essentiel</th>"
                       "<th>Détail</th><th class=\"sig-col-optionnelle\">Depuis</th></tr></thead>")
    en_tete_marche = ("<thead><tr><th>Titre</th><th>Signal</th><th>Essentiel</th>"
                      "<th>Détail</th><th class=\"sig-col-optionnelle\">Détecté le — Source</th></tr></thead>")

    # Pre-rendu HTML par ticker (15/07/2026), pour tous les titres reels, pas
    # seulement liste_suivi -- permet au navigateur d'ajouter n'importe quel
    # titre a "Ma liste de suivi" (stockage local, cf. script d'injection
    # plus bas) et d'en afficher les VRAIS signaux, sans dupliquer en JS la
    # logique de rendu des badges/resumes (deja fiable cote Python).
    lignes_ras = "<tr><td class='sig-ticker-cell'><b>__TICKER__</b></td><td colspan='3' class='sig-ras'>RAS</td><td class='sig-col-optionnelle'></td></tr>"
    lignes_par_ticker_html = {}
    for t in tous_tickers:
        sigs = par_ticker.get(t, [])
        if sigs:
            lignes_par_ticker_html[t] = "".join(_lignes_ticker(t, sigs, avec_source=False))
        else:
            lignes_par_ticker_html[t] = lignes_ras.replace("__TICKER__", t)

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
                       """<span style="font-size:0.85em">Ajoute un titre ci-dessous, ou des codes"""
                       """ dans <code>config/liste_suivi.yaml</code> pour qu'il apparaisse"""
                       """ pour tout le monde.</span></div>""")

    # Donnees pour la gestion cote navigateur (15/07/2026) : ajouter un titre
    # depuis le dashboard, sans toucher au depot. Stockage dans le
    # navigateur de la personne (localStorage) uniquement -- jamais envoye
    # nulle part, jamais visible par quelqu'un d'autre. Un titre ajoute ici
    # se rajoute a la liste du fichier config/liste_suivi.yaml (celle-ci
    # reste la liste "pour tout le monde qui ouvre ce dashboard").
    bloc1 = f"""
<div class="sig-carte">
  <h2>Ma liste de suivi <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      (<span id="suivi-compte">{len(suivi)}</span> titres — codes seuls, aucune donnee personnelle)</span></h2>
  <div style="display:flex;gap:8px;margin-bottom:10px;align-items:center;flex-wrap:wrap">
    <input id="suivi-input" list="suivi-datalist" placeholder="Code du titre (ex. SNTS)"
           style="background:var(--bg,#0f172a);border:1px solid var(--border,#334155);color:var(--text,#e2e8f0);
           border-radius:6px;padding:5px 10px;font-size:0.85em;width:200px;text-transform:uppercase">
    <datalist id="suivi-datalist"></datalist>
    <button class="sig-toggle" onclick="suiviAjouter()">+ Ajouter un titre</button>
    <button class="sig-toggle" onclick="sigToggleColonnes('tbl-suivi', this)">Afficher les dates et sources</button>
    <span id="suivi-message" style="font-size:0.8em;color:var(--muted,#94a3b8)"></span>
  </div>
  <div id="suivi-conteneur">{corps_suivi}</div>
  <div class="sig-note">Règle d'escalade : deux signaux défavorables simultanés sur un
  titre suivi = revue obligatoire sous 10 séances, décision écrite au journal.
  Le système ne décide jamais seul. Survolez un badge pour le code technique et sa définition.
  <br>Les titres ajoutés via le champ ci-dessus sont enregistrés uniquement dans ce navigateur
  (aucune donnée envoyée nulle part) — sur un autre appareil, tu ne les verras pas, sauf à les
  ajouter aussi via <code>config/liste_suivi.yaml</code> pour qu'ils apparaissent pour tout le monde.</div>
</div>
<script>
(function() {{
  const CLE_LOCALE = 'brvm_liste_suivi_locale';
  const SUIVI_SERVEUR = {json.dumps(suivi)};
  const LIGNES_PAR_TICKER = {json.dumps(lignes_par_ticker_html)};
  const ENTETE_SUIVI = {json.dumps(en_tete_signaux)};

  function listeLocale() {{
    try {{ return JSON.parse(localStorage.getItem(CLE_LOCALE) || '[]'); }}
    catch(e) {{ return []; }}
  }}
  function sauverListeLocale(l) {{ localStorage.setItem(CLE_LOCALE, JSON.stringify(l)); }}

  window.suiviAjouter = function() {{
    const champ = document.getElementById('suivi-input');
    const code = (champ.value || '').trim().toUpperCase();
    const msg = document.getElementById('suivi-message');
    if (!code) {{ return; }}
    if (!LIGNES_PAR_TICKER.hasOwnProperty(code)) {{
      msg.textContent = `"${{code}}" ne correspond a aucun titre connu.`;
      msg.style.color = '#f87171';
      return;
    }}
    const locale = listeLocale();
    if (SUIVI_SERVEUR.includes(code) || locale.includes(code)) {{
      msg.textContent = `${{code}} est deja dans la liste.`;
      msg.style.color = 'var(--muted,#94a3b8)';
      champ.value = '';
      return;
    }}
    locale.push(code);
    sauverListeLocale(locale);
    champ.value = '';
    msg.textContent = '';
    suiviRerendre();
  }};

  window.suiviRetirer = function(code) {{
    sauverListeLocale(listeLocale().filter(t => t !== code));
    suiviRerendre();
  }};

  function suiviRerendre() {{
    const locale = listeLocale();
    const tous = SUIVI_SERVEUR.concat(locale.filter(t => !SUIVI_SERVEUR.includes(t))).sort();
    document.getElementById('suivi-compte').textContent = tous.length;
    if (tous.length === 0) {{
      document.getElementById('suivi-conteneur').innerHTML =
        '<div style="padding:16px;text-align:center;color:var(--muted,#94a3b8);border:1px dashed var(--border,#334155);border-radius:8px;">Aucun titre dans la liste de suivi pour l\\'instant.</div>';
      return;
    }}
    let lignes = '';
    for (const t of tous) {{
      const estLocal = locale.includes(t) && !SUIVI_SERVEUR.includes(t);
      let ligne = LIGNES_PAR_TICKER[t] || '';
      if (estLocal) {{
        // Ajoute un bouton de retrait uniquement sur les titres ajoutes localement
        ligne = ligne.replace(`<b>${{t}}</b>`,
          `<b>${{t}}</b> <button onclick="suiviRetirer('${{t}}')" title="Retirer de ma liste"
           style="background:none;border:none;color:var(--muted,#94a3b8);cursor:pointer;font-size:0.9em;padding:0 4px">&times;</button>`);
      }}
      lignes += ligne;
    }}
    document.getElementById('suivi-conteneur').innerHTML =
      `<table class="sig-table" id="tbl-suivi">${{ENTETE_SUIVI}}<tbody>${{lignes}}</tbody></table>`;
  }}

  document.addEventListener('DOMContentLoaded', function() {{
    const dl = document.getElementById('suivi-datalist');
    if (dl && typeof TICKERS !== 'undefined') {{
      dl.innerHTML = TICKERS.map(t => `<option value="${{t}}">`).join('');
    }}
    suiviRerendre();
  }});
  if (document.readyState !== 'loading') {{
    const dl = document.getElementById('suivi-datalist');
    if (dl && typeof TICKERS !== 'undefined') {{
      dl.innerHTML = TICKERS.map(t => `<option value="${{t}}">`).join('');
    }}
    suiviRerendre();
  }}
}})();
</script>"""

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
            statut = f"cotation prévue le {date_intro}" if date_intro else "date de cotation à préciser"
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
  <div class="sig-note">Absence de cours = pas encore côté, pas un problème de donnée ni un risque --
  ce titre rejoindra les autres tableaux dès que ses premières cotations seront collectées.</div>
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
