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
import json
import statistics
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "moteur"))
from glossaire_signaux import badge_html
from scoring import charger_seuils
from calendrier import cycle_le_plus_recent, deja_satisfait

CALENDRIER_PATH = Path(__file__).resolve().parent.parent / "collecte" / "calendrier.json"

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


def _ligne_signal(ty, de):
    """Une ligne compacte : badge (libelle clair, code en info-bulle) + detail."""
    return f'<div class="sig-ligne-signal">{badge_html(ty)}<span class="sig-detail">{de}</span></div>'


def _prochaines_echeances(aujourd_hui):
    """Pour chaque titre couvert par le calendrier, l'echeance REGLEMENTAIRE
    CREPMF (config: delais_reglementaires) du cycle en cours -- revise le
    15/07/2026 : n'utilise plus l'intervalle historique pour PROJETER une
    date, seulement pour (1) confirmer que le titre publie reellement cette
    categorie, (2) verifier si le cycle en cours est deja satisfait.
    N'affiche QUE les echeances dont le cycle concerne l'ANNEE EN COURS
    (demande explicite du 15/07/2026) -- le passe sert a calibrer/confirmer,
    jamais a s'afficher pour lui-meme."""
    if not CALENDRIER_PATH.exists():
        return []
    cal = json.loads(CALENDRIER_PATH.read_text())
    cfg = charger_seuils().get("calendrier", {})
    delais_cfg = charger_seuils().get("delais_reglementaires", {})
    min_occ = cfg.get("min_occurrences", 3)
    exclues = set(cfg.get("categories_exclues", ["autre", "rapport_cac"]))

    echeances = []
    for t, categories in cal.items():
        meilleure = None
        for categorie, v in categories.items():
            if categorie in exclues or categorie not in delais_cfg:
                continue
            hist = sorted(date(*map(int, d.split("-"))) for d in v["historique"])
            if len(hist) < min_occ:
                continue
            annee_ref, echeance = cycle_le_plus_recent(categorie, aujourd_hui, delais_cfg)
            if echeance.year != aujourd_hui.year:
                continue  # hors annee en cours -- filtre demande le 15/07/2026
            if deja_satisfait(categorie, hist, annee_ref, delais_cfg):
                continue  # obligation deja remplie pour ce cycle
            jours_restants = (echeance - aujourd_hui).days
            if meilleure is None or jours_restants < meilleure[2]:
                meilleure = (categorie, hist[-1], jours_restants, echeance)
        if meilleure:
            echeances.append((t, *meilleure))
    return sorted(echeances, key=lambda x: x[3])  # la plus proche d'abord


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
    # ---- Bloc 3 : introductions et cotations a venir (14/07/2026) ----
    # Principe identique a celui applique au Sizing "Prudence" : ne JAMAIS
    # confondre "pas de donnee" avec "probleme" -- un titre nouvellement
    # introduit (BBGCI, rejoint la BRVM en 2026) n'a ni cours ni historique,
    # ce n'est pas une exclusion pour cause, ce n'est pas un signal --
    # affichage separe, jamais dans "Exclus".
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
  <h2>Introductions et cotations a venir <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      ({len(intro)} titre{'s' if len(intro)>1 else ''} — pas encore de cours, distinct d'une exclusion)</span></h2>
  <table class="sig-table">
    <thead><tr><th>Titre</th><th>Nom</th><th>Secteur</th><th>Statut</th><th>Note</th></tr></thead>
    <tbody>{''.join(lignes3)}</tbody>
  </table>
  <div class="sig-note">Absence de cours = pas encore cote, pas un probleme de donnee ni un risque --
  ce titre rejoindra les autres tableaux des que ses premieres cotations seront collectees.</div>
</div>"""

    # ---- Bloc 4 : calendrier des publications (14/07/2026) ----
    # Reponse au constat : le calendrier existait en coulisses (D4 automatique)
    # sans jamais etre visible. Ici : une vue directe, triee par echeance la
    # plus proche, plutot qu'un fichier json invisible.
    ech = _prochaines_echeances(date.today())
    bloc4 = ""
    if ech:
        lignes4 = []
        for t, categorie, dernier, jours_restants, prochaine in ech[:15]:
            if jours_restants < 0:
                statut = f"<span class='sig-def' style='padding:1px 8px;border-radius:99px'>en retard de {-jours_restants}j</span>"
            elif jours_restants <= 14:
                statut = f"<span class='sig-info' style='padding:1px 8px;border-radius:99px'>dans {jours_restants}j</span>"
            else:
                statut = f"attendue vers le {prochaine.isoformat()}"
            lignes4.append(f"<tr><td><b>{t}</b></td><td>{categorie}</td>"
                          f"<td>{dernier.isoformat()}</td><td>{statut}</td></tr>")
        bloc4 = f"""
<div class="sig-carte">
  <h2>Calendrier des publications <span style="font-weight:400;color:var(--muted,#94a3b8);font-size:0.78em">
      (echeance estimee la plus proche par titre, {len(ech)} titres couverts)</span></h2>
  <table class="sig-table">
    <thead><tr><th>Titre</th><th>Categorie</th><th>Dernier depot</th><th>Echeance estimee</th></tr></thead>
    <tbody>{''.join(lignes4)}</tbody>
  </table>
  <div class="sig-note">Estimation = dernier depot + intervalle historique typique de ce titre pour cette
  categorie de document (pas une date reglementaire officielle). Les 15 echeances les plus proches sont affichees.</div>
</div>"""

    return STYLE + bloc1 + bloc2 + bloc3 + bloc4


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
