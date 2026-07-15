#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5b v3 — Dashboard HTML. Ajouts de cette version (consolidation dashboard,
07/2026) : recherche/tri/regroupement sectoriel sur la Synthese, glossaire au
CLIC (jamais au survol seul, accessibilite clavier/mobile), lien vers document
source (actuellement non renseigne en base, affiche honnetement), comparaison
tabulaire de 2 titres (jamais un graphique, precision > pattern - Cleveland &
McGill 1984), couleurs accessibles daltonisme (WCAG 1.4.1 : jamais rouge/vert
seul, toujours un texte redondant).
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path
from statistics import median, mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "moteur"))
from scoring import evaluer_titre, rapport_fraicheur, charger_seuils, charger_marche, charger_liquidite_jour, charger_liquidite_generale, charger_tendance_liquidite, DB
from calendrier import cycle_le_plus_recent, deja_satisfait
from glossaire_signaux import sizing_libelle, sizing_classe, sizing_description, SIZING  # 14/07/2026
import re as _re_humanise


def humaniser(texte):
    """Convertit tout token EN_MAJUSCULES_AVEC_SOULIGNES (code technique libre,
    ex. type d'avis reglementaire non couvert par un glossaire ferme) en texte
    lisible 'En majuscules avec soulignes' -> 'En majuscules avec soulignes'.
    Corrige le 14/07/2026 : ces codes bruts (ex. AVIS CYCLE_MATIERE_PREMIERE)
    echappaient au glossaire_signaux (qui ne couvre que les 7 types de la
    table `signaux`) car avis_reglementaires.type est un champ libre, pas une
    enumeration fermee — un glossaire fige est donc impossible ici ; seule
    une transformation de texte generique peut s'appliquer a toute valeur
    future sans maintenance."""
    if not texte:
        return texte
    def _conv(m):
        mot = m.group(0)
        return mot.replace("_", " ").capitalize()
    return _re_humanise.sub(r"\b[A-Z][A-Z_]{2,}\b", _conv, texte)
import sqlite3

LIBELLES_SECTEURS_COURTS = {
    "Consommation De Base": "Conso. De Base",
    "Consommation Discretionnaire": "Conso. Discretionnaire",
    "Services Financiers": "Services Fin.",
    "Services Publics": "Services Publics",
    "Telecommunications": "Telecoms",
}


def _rendre_profil_secteur(t):
    """Identique au rendu JS de la Synthese (fonction renderProfil) : meme
    mini-graphique en barres, memes classes CSS -> rendu visuellement
    identique aux deux endroits (harmonisation demandee le 14/07/2026)."""
    if not t.get("profil"):
        return "<span class='chip chip-na'>n/d</span>"
    sc = t.get("profil_scores") or {}
    dominant = t["profil"]
    titre = f"VALUE {sc.get('VALUE')} \u00b7 GROWTH {sc.get('GROWTH')} \u00b7 GARP {sc.get('GARP')}"
    def barre(nom, cls):
        v = sc.get(nom)
        if v is None:
            return ""
        dom_cls = " pm-dom" if dominant == nom else ""
        return f"<div class='pm-bar pm-{cls}{dom_cls}' style='height:{v}%'></div>"
    chip = f"<span class='chip chip-{dominant.lower()}'>{dominant}</span>"
    barres = f"<div class='profil-mini' title='{titre}'>{barre('VALUE','value')}{barre('GROWTH','growth')}{barre('GARP','garp')}</div>"
    return chip + barres


def libelle_secteur(s):
    """Point 5 (audit ergonomie, 14/07/2026) : libelles raccourcis pour gagner
    de la largeur dans les tableaux, sans perdre l'info (titre complet en attribut)."""
    titre = s.replace("_", " ").title()
    court = LIBELLES_SECTEURS_COURTS.get(titre, titre)
    return f'<span title="{titre}">{court}</span>' if court != titre else titre


GLOSSAIRE = {
    "RN": "Resultat net : ce que l'entreprise a gagne au total sur l'exercice, apres impots.",
    "CP": "Capitaux propres : la valeur nette de l'entreprise si elle remboursait toutes ses dettes.",
    "ROE": "Rentabilite des capitaux propres : combien l'entreprise gagne pour chaque FCFA que ses actionnaires ont investi.",
    "PER": "Prix rapporte au benefice : combien d'annees de benefice actuel faudrait-il pour 'rembourser' le prix de l'action.",
    "Payout": "Part du benefice reellement versee aux actionnaires sous forme de dividende.",
    "RAO": "Resultat des activites ordinaires : le benefice hors elements exceptionnels (cessions, gains ponctuels).",
    "Score": "Note composite /100 issue du moteur (rentabilite, solidite, valorisation) — seuils encore provisoires.",
}


def collecter_donnees():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%'").fetchall()]
    resultats = [evaluer_titre(t) for t in tickers]
    for r in resultats:
        r["alertes"] = [humaniser(a) for a in r.get("alertes", [])]

    series = {}
    for t in tickers:
        rows = cur.execute(
            "SELECT fin_mois, cours, per, rendement FROM cours_mensuels "
            "WHERE ticker=? ORDER BY fin_mois", (t,)).fetchall()
        series[t] = [{"mois": r["fin_mois"], "cours": r["cours"],
                     "per": r["per"], "rendement": r["rendement"]} for r in rows]

    fondamentaux = {}
    source_urls = {}
    for t in tickers:
        rows = cur.execute(
            "SELECT exercice, resultat_net, resultat_net_n1, total_actif, total_passif, "
            "capitaux_propres, payout_ratio, resultat_activites_ordinaires, statut_donnee, "
            "source_type, source_url FROM etats_financiers WHERE ticker=? ORDER BY exercice DESC",
            (t,)).fetchall()
        fondamentaux[t] = [dict(r) for r in rows]
        source_urls[t] = rows[0]["source_url"] if rows else None

    avis = {}
    for t in tickers:
        rows = cur.execute(
            "SELECT type, date_avis, note FROM avis_reglementaires WHERE ticker=?",
            (t,)).fetchall()
        avis[t] = [dict(r, type=humaniser(r["type"]), note=humaniser(r["note"])) for r in rows]

    conn.close()
    # Point 1 (audit ergonomie, 14/07/2026) : integrer le profilage de style
    # (VALUE/GROWTH/GARP), calcule par moteur/profils.py, dans le dashboard
    # principal. Auparavant consomme uniquement par le poste de decision et
    # les 2 blocs signaux — absent de la Synthese et des Secteurs, la lacune
    # que l'utilisateur avait signalee.
    profils_path = Path(__file__).resolve().parent.parent / "collecte" / "profils.json"
    profils = json.loads(profils_path.read_text()) if profils_path.exists() else {}
    return resultats, series, fondamentaux, avis, source_urls, profils


def calculer_roe(fonda_ticker):
    if not fonda_ticker:
        return None
    f = fonda_ticker[0]
    if f.get("resultat_net") and f.get("capitaux_propres") and f["capitaux_propres"] > 0:
        return f["resultat_net"] / f["capitaux_propres"]
    return None


def interpreter_roe(roe):
    if roe is None:
        return None, None
    pct = round(roe * 100, 1)
    if roe > 0.15:
        return pct, "eleve"
    if roe < 0.05:
        return pct, "faible"
    return pct, None


def interpreter_liquidite_generale(ticker, liquidite_generale):
    """P9 (12/07/2026) : repond a "ce titre est-il liquide EN GENERAL ?" —
    valeur absolue FCFA (typique, moyenne 12 mois glissants) en premier plan,
    ratio vs Sonatel en contexte secondaire SEULEMENT (jamais la base de
    calcul principale)."""
    donnee = liquidite_generale.get(ticker)
    ref = liquidite_generale.get("SNTS", {}).get("valeur_moyenne_12m")
    if donnee is None:
        return None, None, None
    valeur_abs = donnee["valeur_moyenne_12m"]
    ratio_pct = round(valeur_abs / ref * 100, 1) if ref else None
    n_mois = donnee.get("n_mois")
    return valeur_abs, ratio_pct, n_mois


def formater_fcfa(valeur):
    if valeur is None:
        return "—"
    if valeur >= 1_000_000:
        return f"{valeur/1_000_000:.1f} M FCFA"
    if valeur >= 1_000:
        return f"{valeur/1_000:.0f} K FCFA"
    return f"{valeur:.0f} FCFA"


def interpreter_liquidite(ticker, marche, liquidite_jour):
    """REVISION (12/07/2026) : priorite a la donnee DU JOUR (liquidite_jour.json,
    lue directement depuis brvm.org par collecte_liquidite_jour.py — aucune
    reconstruction), repli marche.yaml si absente. Retourne valeur echangee ET
    flottant separement — les deux affiches cote a cote, jamais l'un a la
    place de l'autre (la valeur repond a "puis-je executer aujourd'hui", le
    flottant repond a "pourquoi c'est structurel" — deux questions differentes)."""
    donnee_jour = liquidite_jour.get(ticker)
    ref_jour = liquidite_jour.get("SNTS", {}).get("valeur_echangee_jour")
    liq = marche.get("liquidite_individuelle", {}).get(ticker, {})

    valeur_pct, valeur_interp, date_maj = None, None, None
    if donnee_jour is not None and ref_jour:
        ratio = donnee_jour["valeur_echangee_jour"] / ref_jour
        valeur_pct = round(ratio * 100, 1)
        date_maj = donnee_jour.get("date_maj_brvm")
        if ratio < 0.01:
            valeur_interp = "quasi-intradable"
        elif ratio < 0.25:
            valeur_interp = "reduite"
    else:
        # Repli marche.yaml (pas de collecte du jour disponible)
        ratio = liq.get("volume_relatif_marche") or liq.get("valeur_relative_marche")
        if ratio is not None:
            valeur_pct = round(ratio * 100, 1)
            date_maj = "repli marche.yaml"
            if ratio < 0.01:
                valeur_interp = "quasi-intradable"
            elif ratio < 0.25:
                valeur_interp = "reduite"
        elif liq.get("liquidite_execution") == "ELEVEE":
            valeur_interp = "elevee"
            date_maj = "repli marche.yaml"

    flottant_pct, flottant_interp = None, None
    flottant = liq.get("ratio_flottant")
    if flottant is not None:
        flottant_pct = round(flottant * 100, 1)
        flottant_interp = "restreint" if flottant < 0.25 else None

    return valeur_pct, valeur_interp, date_maj, flottant_pct, flottant_interp


def categoriser_position(valeur, moyenne, sens_favorable_bas):
    """sens_favorable_bas=True (PER: en dessous de la moyenne = favorable/decote).
    sens_favorable_bas=False (ROE: au dessus de la moyenne = favorable)."""
    if valeur is None or moyenne is None or moyenne == 0:
        return None, None
    ecart = (valeur - moyenne) / abs(moyenne)
    if sens_favorable_bas:
        ecart = -ecart  # inverse : en dessous de la moyenne devient positif
    if ecart > 0.15:
        return "vert", "▼" if sens_favorable_bas else "▲"
    if ecart < -0.15:
        return "rouge", "▲" if sens_favorable_bas else "▼"
    return "orange", "●"


def calculer_secteurs(resultats, series, fondamentaux, marche, liquidite_jour, liquidite_generale, profils):
    secteurs = {}
    for r in resultats:
        s = r["secteur"]
        secteurs.setdefault(s, {"scores": [], "pers": [], "roes": [], "titres": []})
        roe = calculer_roe(fondamentaux.get(r["ticker"], []))
        roe_pct, roe_interp = interpreter_roe(roe)
        liq_gen_abs, liq_gen_ratio, liq_gen_nmois = interpreter_liquidite_generale(r["ticker"], liquidite_generale)
        _, _, _, liq_flot_pct, liq_flot_interp = interpreter_liquidite(r["ticker"], marche, liquidite_jour)
        sr = series.get(r["ticker"], [])
        per = sr[-1]["per"] if sr and sr[-1]["per"] else None

        p_style = profils.get(r["ticker"], {})
        # Correctif ergonomie (14/07/2026) : un survol (title=) est invisible sur
        # mobile/tactile et cache l'info au lieu de l'expliciter — corrige suite
        # au retour explicite sur ce point. Les 3 scores sont maintenant fournis
        # pour un affichage TOUJOURS VISIBLE (plus seulement en info-bulle).
        profil_scores = {"VALUE": p_style.get("VALUE"), "GROWTH": p_style.get("GROWTH"), "GARP": p_style.get("GARP")}
        profil_detail = (f"VALUE {{p_style['VALUE']}} \u00b7 GROWTH {{p_style['GROWTH']}} \u00b7 GARP {{p_style['GARP']}}"
                         if p_style.get("dominant") else "")
        secteurs[s]["titres"].append({
            "ticker": r["ticker"], "score": round(r["score_composite"], 1) if r.get("score_composite") else None,
            "profil": p_style.get("dominant"), "profil_mixte": bool(p_style.get("mixte")),
            "profil_detail": profil_detail, "profil_scores": profil_scores,
            "per": per, "roe": roe_pct, "roe_interp": roe_interp,
            "liq_gen_abs": liq_gen_abs, "liq_gen_ratio": liq_gen_ratio, "liq_gen_nmois": liq_gen_nmois,
            "liq_flottant": liq_flot_pct, "liq_flottant_interp": liq_flot_interp, "statut": r["statut_gate"],
        })
        # Agregats sectoriels (mediane, comparaison) : UNIQUEMENT les titres ELIGIBLE.
        # Un titre EXCLU (pertes, capitaux negatifs...) ne doit pas fausser la
        # reference "typique" du secteur pour juger les autres titres — decision
        # actee le 10/07/2026 apres simulation (STAC polluait Industriels a -5.8%).
        if r["statut_gate"] == "ELIGIBLE":
            if r.get("score_composite"):
                secteurs[s]["scores"].append(r["score_composite"])
            if per:
                secteurs[s]["pers"].append(per)
            if roe_pct is not None:
                secteurs[s]["roes"].append(roe_pct)

    out = {}
    for s, d in secteurs.items():
        per_median = round(median(d["pers"]), 2) if d["pers"] else None
        roe_median = round(median(d["roes"]), 1) if d["roes"] else None
        for t in d["titres"]:
            t["per_pos"], t["per_symb"] = categoriser_position(t["per"], per_median, sens_favorable_bas=True)
            t["roe_pos"], t["roe_symb"] = categoriser_position(t["roe"], roe_median, sens_favorable_bas=False)
        out[s] = {
            "nb_titres": len(d["titres"]), "nb_eligibles_ds_calcul": len(d["pers"]),
            "per_median": per_median, "roe_median": roe_median,
            "score_moyen": round(mean(d["scores"]), 1) if d["scores"] else None,
            "titres": sorted(d["titres"], key=lambda t: -(t["score"] or 0)),
        }
    return out


def terme_glossaire(mot):
    txt = GLOSSAIRE.get(mot, "")
    return (f'<span class="gloss" tabindex="0" data-def="{txt}">{mot}</span>' if txt else mot)


def _prochaines_echeances_annee_en_cours(aujourd_hui):
    """Echeance REGLEMENTAIRE CREPMF (config: delais_reglementaires) du cycle
    en cours, par titre -- deplace de dashboard/bloc_signaux.py vers ici le
    15/07/2026 (demande : afficher ce bloc en bas de la Synthese, sous
    'Donnees perimees', plutot qu'en tete de page). Logique inchangee :
    l'historique confirme seulement que le titre publie la categorie et si
    le cycle est deja satisfait ; la date elle-meme vient du texte
    reglementaire. Seules les echeances de l'ANNEE EN COURS sont retenues."""
    chemin = Path(__file__).resolve().parent.parent / "collecte" / "calendrier.json"
    if not chemin.exists():
        return []
    cal = json.loads(chemin.read_text())
    seuils_locaux = charger_seuils()
    cfg = seuils_locaux.get("calendrier", {})
    delais_cfg = seuils_locaux.get("delais_reglementaires", {})
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
                continue
            if deja_satisfait(categorie, hist, annee_ref, delais_cfg):
                continue
            jours_restants = (echeance - aujourd_hui).days
            if meilleure is None or jours_restants < meilleure[2]:
                meilleure = (categorie, hist[-1], jours_restants, echeance)
        if meilleure:
            echeances.append((t, *meilleure))
    return sorted(echeances, key=lambda x: x[3])


def generer_html(resultats, series, fondamentaux, avis, source_urls, seuils, fraicheur, marche, liquidite_jour, liquidite_generale, tendance_liquidite, profils):
    elig = [r for r in resultats if r["statut_gate"] == "ELIGIBLE" and r["score_composite"]]
    elig.sort(key=lambda r: -r["score_composite"])
    excl = [r for r in resultats if r["statut_gate"] == "EXCLU"]
    tous_tickers = sorted(r["ticker"] for r in resultats)
    secteurs = calculer_secteurs(resultats, series, fondamentaux, marche, liquidite_jour, liquidite_generale, profils)

    # Couleurs accessibles daltonisme (WCAG 1.4.1) : jamais rouge/vert pur.
    # Bleu = normal, terracotta = attention — toujours associe a un texte.
    C_OK, C_ATTN = "#2a78d6", "#c1502e"

    labels = json.dumps([r["ticker"] for r in elig])
    scores = json.dumps([round(r["score_composite"], 1) for r in elig])
    couleurs = json.dumps([
        C_ATTN if (any("PERIMEE" in a for a in r["alertes"]) or
                   r["sizing"]["recommandation"] in ("REDUITE", "MINIMALE", "PRUDENCE"))
        else C_OK for r in elig
    ])

    # Table de donnees JS (recherche/tri/regroupement cote client - site statique)
    lignes_js = []
    for r in elig:
        roe = calculer_roe(fondamentaux.get(r["ticker"], []))
        alertes_maj = [a for a in r["alertes"] if any(
            m in a for m in ("TURNAROUND", "PERIMEE", "payout", "recul", "AVIS", "ECART"))]
        attention = any("PERIMEE" in a for a in r["alertes"]) or r["sizing"]["recommandation"] in ("REDUITE", "MINIMALE", "PRUDENCE")
        p_style = profils.get(r["ticker"], {})
        # Correctif ergonomie (14/07/2026) : un survol (title=) est invisible sur
        # mobile/tactile et cache l'info au lieu de l'expliciter — corrige suite
        # au retour explicite sur ce point. Les 3 scores sont maintenant fournis
        # pour un affichage TOUJOURS VISIBLE (plus seulement en info-bulle).
        profil_scores = {"VALUE": p_style.get("VALUE"), "GROWTH": p_style.get("GROWTH"), "GARP": p_style.get("GARP")}
        profil_detail = (f"VALUE {{p_style['VALUE']}} \u00b7 GROWTH {{p_style['GROWTH']}} \u00b7 GARP {{p_style['GARP']}}"
                         if p_style.get("dominant") else "")
        lignes_js.append({
            "ticker": r["ticker"], "secteur": r["secteur"].replace("_", " ").title(),
            "profil": p_style.get("dominant"), "profil_mixte": bool(p_style.get("mixte")),
            "profil_detail": profil_detail, "profil_scores": profil_scores,
            "score": round(r["score_composite"], 1) if r["score_composite"] is not None else None,
            "rentabilite": round(r["score_rentabilite"], 1) if r["score_rentabilite"] is not None else None,
            "solidite": round(r["score_solidite"], 1) if r["score_solidite"] is not None else None,
            "valorisation": round(r["score_valorisation"], 1) if r["score_valorisation"] is not None else None,
            "roe": round(roe * 100, 1) if roe else None,
            "sizing": r["sizing"]["recommandation"],
            "sizing_libelle": sizing_libelle(r["sizing"]["recommandation"]),
            "sizing_classe": sizing_classe(r["sizing"]["recommandation"]),
            "sizing_desc": sizing_description(r["sizing"]["recommandation"]),
            "attention": attention,
            "alertes": alertes_maj,  # liste complete (14/07/2026) ; le JS affiche 1 + "et N autres" repliable
        })

    lignes_exclus = "".join(f"""
        <tr><td><b>{r['ticker']}</b></td><td>{r['secteur'].replace('_',' ').title()}</td>
        <td class="alertes">{'; '.join(r['motifs_exclusion'])}</td></tr>""" for r in excl)

    lignes_fraicheur = "".join(f'<tr><td>{t}</td><td>{fm}</td><td>{j} jours</td></tr>'
                                for t, fm, j in fraicheur["perimes"])

    echeances_calendrier = _prochaines_echeances_annee_en_cours(date.today())
    def _statut_echeance(jours_restants, prochaine):
        if jours_restants < 0:
            return f"<span style='color:#f87171;font-weight:600'>en retard de {-jours_restants}j</span>"
        if jours_restants <= 14:
            return f"<span style='color:#60a5fa;font-weight:600'>dans {jours_restants}j</span>"
        return f"attendue vers le {prochaine.isoformat()}"
    lignes_calendrier = "".join(
        f"<tr><td><b>{t}</b></td><td>{cat}</td><td>{dernier.isoformat()}</td>"
        f"<td>{_statut_echeance(jr, prochaine)}</td></tr>"
        for t, cat, dernier, jr, prochaine in echeances_calendrier)

    def fmt_valeur(val, interp, unite="%"):
        if val is None:
            return "—"
        base = f"{val}{unite}"
        return f"{base} ({interp})" if interp else base

    def cellule_couleur(val, pos, symb, unite=""):
        if val is None:
            return "—"
        if pos is None:
            return f"{val}{unite}"
        couleurs_pos = {"vert": "#2a9d5c", "orange": "#c17a2a", "rouge": "#c1502e"}
        return (f'<span style="color:{couleurs_pos[pos]}">{val}{unite} '
                f'<span aria-hidden="true">{symb}</span></span>')

    blocs_secteurs = ""
    for s, d in sorted(secteurs.items()):
        lignes_titres = ""
        for t in d["titres"]:
            statut_txt = "" if t["statut"] == "ELIGIBLE" else ' <span class="alertes">(exclu)</span>'
            lignes_titres += f"""
            <tr onclick="afficherFiche('{t['ticker']}')" style="cursor:pointer">
              <td><b>{t['ticker']}</b>{statut_txt}</td>
              <td>{_rendre_profil_secteur(t)}</td>
              <td>{t['score'] if t['score'] is not None else '—'}</td>
              <td>{cellule_couleur(t['per'], t['per_pos'], t['per_symb'])}</td>
              <td>{cellule_couleur(t['roe'], t['roe_pos'], t['roe_symb'], '%')}</td>
              <td>{formater_fcfa(t['liq_gen_abs'])}{f" <span class='alertes'>(≈{t['liq_gen_ratio']}% Sonatel, {t['liq_gen_nmois']}m)</span>" if t.get('liq_gen_ratio') else ''}</td>
              <td>{fmt_valeur(t['liq_flottant'], t['liq_flottant_interp'])}</td>
            </tr>"""
        lignes_titres += f"""
            <tr style="background:var(--surface-3, #172033);font-weight:600">
              <td>Mediane du secteur <span style="font-weight:400;color:var(--muted);font-size:0.75em">(titres eligibles seulement, n={d['nb_eligibles_ds_calcul']})</span></td><td>—</td><td>—</td>
              <td>{d['per_median'] if d['per_median'] else '—'}</td>
              <td>{d['roe_median'] if d['roe_median'] else '—'}%</td><td>—</td>
            </tr>"""
        note_couverture = (f'<div style="font-size:0.75em;color:#c1502e;margin-top:6px">'
                           f'⚠️ Couverture ROE incomplete pour ce secteur ({d["nb_eligibles_ds_calcul"]} titre(s) '
                           f'seulement avec capitaux propres connus) — classement a interpreter avec prudence</div>'
                           if d['roe_median'] is None or d['nb_eligibles_ds_calcul'] < d['nb_titres'] // 2 else '')
        blocs_secteurs += f"""
        <div class="carte">
          <h2>{libelle_secteur(s)} — {d['nb_titres']} titres
            <span style="font-weight:400;color:var(--muted);font-size:0.75em">
              (mediane PER {d['per_median'] if d['per_median'] else '—'} · score moyen {d['score_moyen'] if d['score_moyen'] else '—'})
            </span></h2>
          <div class="scroll"><table>
            <thead><tr><th>Titre</th><th>Profil</th><th>{terme_glossaire('Score')}</th><th>{terme_glossaire('PER')}</th>
              <th>{terme_glossaire('ROE')}</th><th>Liquidite generale</th><th>Flottant</th></tr></thead>
            <tbody>{lignes_titres}</tbody>
          </table></div>
          <div style="font-size:0.75em;color:var(--muted);margin-top:8px">
            ▼ vert = plus favorable que la mediane du secteur (PER bas ou ROE eleve) ·
            ● orange = proche de la mediane (±15%) · ▲ rouge = moins favorable ·
            les titres EXCLUS ne comptent pas dans le calcul de la mediane
          </div>
          {note_couverture}
        </div>"""

    # Classements inter-sectoriels (mediane, titres eligibles uniquement)
    secteurs_par_per = sorted([(libelle_secteur(s), d["per_median"]) for s, d in secteurs.items() if d["per_median"]],
                              key=lambda x: x[1])
    secteurs_par_roe = sorted([(libelle_secteur(s), d["roe_median"]) for s, d in secteurs.items() if d["roe_median"]],
                              key=lambda x: -x[1])
    rang_per = "".join(f"<tr><td>{i}</td><td>{s.replace('_',' ').title()}</td><td>{v}</td></tr>"
                        for i, (s, v) in enumerate(secteurs_par_per, 1))
    rang_roe = "".join(f"<tr><td>{i}</td><td>{s.replace('_',' ').title()}</td><td>{v}%</td></tr>"
                        for i, (s, v) in enumerate(secteurs_par_roe, 1))
    secteurs_absents_roe = [s.replace('_',' ').title() for s, d in secteurs.items() if d["roe_median"] is None]
    tables_classement = f"""
        <div class="carte">
          <h2>Classement des secteurs par {terme_glossaire('PER')} median <span style="font-weight:400;color:var(--muted);font-size:0.75em">(du moins cher au plus cher, titres exclus non comptes)</span></h2>
          <table><thead><tr><th>Rang</th><th>Secteur</th><th>PER median</th></tr></thead>
          <tbody>{rang_per}</tbody></table>
        </div>
        <div class="carte">
          <h2>Classement des secteurs par {terme_glossaire('ROE')} median <span style="font-weight:400;color:var(--muted);font-size:0.75em">(du plus au moins rentable, titres exclus non comptes)</span></h2>
          <table><thead><tr><th>Rang</th><th>Secteur</th><th>ROE median</th></tr></thead>
          <tbody>{rang_roe}</tbody></table>
          {f'<div style="font-size:0.8em;color:var(--muted);margin-top:8px">Secteurs absents (aucune donnee capitaux propres collectee) : {", ".join(secteurs_absents_roe)}</div>' if secteurs_absents_roe else ''}
        </div>"""

    maj = datetime.now().strftime("%d/%m/%Y a %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BRVM — Watchlist GARP-Quality</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{ --bg:#0f172a; --card:#1e293b; --border:#334155; --text:#e2e8f0; --muted:#94a3b8; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
  .conteneur {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.6em; margin-bottom: 4px; }}
  .maj {{ color: var(--muted); font-size: 0.85em; margin-bottom: 4px; }}
  .avertissement {{ background: #7f1d1d; color: #fecaca; padding: 10px 14px; border-radius: 8px;
                     font-size: 0.85em; margin: 12px 0 20px; }}
  .onglets {{ display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }}
  .onglet {{ background: var(--card); border: 1px solid var(--border); color: var(--muted);
             padding: 8px 16px; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 0.9em; }}
  .onglet.actif {{ background: #2563eb; color: white; border-color: #2563eb; }}
  .groupe-onglets {{ color: var(--muted); font-size: 0.72em; text-transform: uppercase;
                      letter-spacing: 0.05em; align-self: center; margin-right: 2px; }}
  .separateur-onglets {{ width: 1px; background: var(--border); margin: 4px 6px; }}
  .panneau {{ display: none; }}
  .panneau.actif {{ display: block; }}
  .carte {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
            padding: 18px; margin-bottom: 20px; }}
  h2 {{ font-size: 1.1em; margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
  .scroll {{ overflow-x: auto; }}
  .chip {{ display:inline-block; padding:1px 8px; border-radius:99px; font-size:0.78em; font-weight:600; white-space:nowrap; }}
  .chip-value {{ background:#173f2e; color:#34d399; }}
  .chip-growth {{ background:#1e3a5f; color:#60a5fa; }}
  .chip-garp {{ background:#3f2e17; color:#fbbf24; }}
  .chip-na {{ background:#334155; color:#94a3b8; }}
  .col-analytique {{ color: var(--muted, #94a3b8); font-size: 0.93em; }}
  .legende-globale {{ margin: 10px 0 16px; font-size: 0.85em; color: var(--muted, #94a3b8); }}
  .legende-globale summary {{ cursor: pointer; }}
  /* Profil : mini-graphique en barres (14/07/2026, 2e iteration ergonomie) */
  .profil-mini {{ display: inline-flex; align-items: flex-end; gap: 2px; height: 16px;
                  width: 26px; vertical-align: middle; margin-left: 6px; cursor: help; }}
  .pm-bar {{ flex: 1; min-height: 2px; border-radius: 1px; opacity: 0.5; }}
  .pm-bar.pm-dom {{ opacity: 1; }}
  .pm-value {{ background: #34d399; }}
  .pm-growth {{ background: #60a5fa; }}
  .pm-garp {{ background: #fbbf24; }}
  /* Alertes : badge compact replie par defaut (14/07/2026) */
  .alertes-compact summary {{ cursor: pointer; color: #fdba74; font-weight: 600; list-style: none; }}
  .alertes-compact summary::-webkit-details-marker {{ display: none; }}
  .alertes-compact ul {{ margin: 6px 0 0; padding-left: 18px; font-size: 0.85em; color: var(--muted, #94a3b8); }}
  .alertes-ras {{ color: var(--muted, #94a3b8); }}
  /* Tableau Synthese : largeurs fixes, colonnes numeriques alignees a droite,
     jamais de retour a la ligne dans les cellules critiques (14/07/2026) */
  #corps-synthese, .scroll table {{ table-layout: fixed; width: 100%; }}
  #corps-synthese td, #corps-synthese th {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .score-fort {{ color: #34d399; font-weight: 600; }}
  .score-moyen {{ color: #fbbf24; }}
  .score-faible {{ color: #f87171; }}
  .score-na {{ color: var(--muted, #94a3b8); }}
  .badge-na {{ background: #334155; color: #94a3b8; }}
  .legende-corps {{ display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 8px;
                     padding: 10px 14px; background: var(--card, #1e293b);
                     border: 1px solid var(--border, #334155); border-radius: 8px; }}
  .alertes details {{ cursor: pointer; }}
  .alertes summary {{ list-style: none; }}
  .alertes summary::-webkit-details-marker {{ display: none; }}
  .badge[title], .chip[title] {{ cursor: help; }}
  th {{ text-align: left; padding: 8px 10px; color: var(--muted); font-weight: 600;
        border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--card); cursor: pointer; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #27334a; vertical-align: top; }}
  tr:hover td {{ background: #24314a; }}
  .alertes {{ color: var(--muted); font-size: 0.92em; }}
  .badge {{ padding: 2px 8px; border-radius: 999px; font-size: 0.8em; font-weight: 600; }}
  .badge-pleine {{ background: #1e3a5f; color: #93c5fd; }}
  .badge-reduite, .badge-prudence {{ background: #7c2d12; color: #fdba74; }}
  .badge-minimale {{ background: #7c2d12; color: #fed7aa; }}
  .puce {{ display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:6px; }}
  .scroll {{ max-height: 480px; overflow-y: auto; }}
  canvas {{ max-height: 320px; }}
  select, input[type=text] {{ background: #0f172a; color: var(--text); border: 1px solid var(--border);
            border-radius: 6px; padding: 8px 12px; font-size: 0.95em; margin-bottom: 14px; }}
  input[type=text] {{ width: 100%; }}
  .barre-outils {{ display: flex; gap: 8px; margin-bottom: 10px; }}
  .barre-outils select {{ margin-bottom: 0; }}
  .fiche-grille {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                    gap: 10px; margin-bottom: 16px; }}
  .fiche-stat {{ background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 10px; }}
  .fiche-stat .label {{ color: var(--muted); font-size: 0.78em; }}
  .fiche-stat .valeur {{ font-size: 1.2em; font-weight: 700; }}
  .photo-unique {{ background: #78350f; color: #fdba74; padding: 8px 12px; border-radius: 8px;
                    font-size: 0.85em; margin-bottom: 12px; }}
  .gloss {{ border-bottom: 1px dotted var(--muted); cursor: help; position: relative; }}
  .gloss:focus, .gloss.ouvert {{ outline: none; }}
  .gloss .bulle {{ display: none; position: absolute; bottom: 130%; left: 0; background: #0f172a;
                   border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px;
                   font-size: 0.85em; color: var(--text); width: 220px; z-index: 10; font-weight: 400; }}
  .gloss:focus .bulle, .gloss.ouvert .bulle {{ display: block; }}
  .sourcelien {{ color: #60a5fa; font-size: 0.85em; text-decoration: underline; }}
  .sourcelien.indisponible {{ color: var(--muted); text-decoration: none; font-style: italic; }}
  .footer {{ color: var(--muted); font-size: 0.8em; text-align: center; margin-top: 24px; }}
</style>
</head>
<body>
<div class="conteneur">
  <h1>BRVM — Watchlist GARP-Quality</h1>
  <div class="maj">Généré automatiquement le {maj} · seuils v{seuils.get('version','?')}</div>
  <div class="avertissement">
    ⚠️ Cette watchlist ne sert a AUCUNE decision d'investissement seule — seuils non valides
    empiriquement (backtest en cours), voir document de reference du projet.
  </div>
  <div class="avertissement" style="background:#78350f;color:#fdba74">
    📊 SCORE COMPOSITE SUSPENDU comme critere de decision principal (10/07/2026) — le signal
    decote-vs-secteur n'est pas statistiquement significatif une fois la correlation des donnees
    prise en compte (test en blocs par titre, IC 95% incluant zero). Le score reste affiche a
    titre observationnel ; se referer aux 3 sous-scores (Rentabilite / Solidite / Valorisation)
    individuellement pour toute lecture.
  </div>

  <details class="legende-globale">
    <summary>Légende des couleurs et symboles (cliquer pour déplier)</summary>
    <div class="legende-corps">
      <span>&#9873; rouge = défavorable / à surveiller</span>
      <span>&#10003; vert = favorable / décote qualifiée</span>
      <span>&#8505; bleu = information neutre (ex. nouveau record)</span>
      <span>Profil : 3 barres = VALUE/GROWTH/GARP — la plus haute et vive domine (survol = chiffres exacts)</span>
      <span>Vert/orange/rouge sur un chiffre = niveau (fort/moyen/faible) du score ou du ROE</span>
      <span>Taille "Donnee manquante" (gris) = pas de liquidite collectee, different d'un vrai risque</span>
      <span>Alertes : badge replie par defaut, cliquez pour lire le détail</span>
      <span>&#9660; vert (secteurs) = plus favorable que la mediane</span>
      <span>&#9679; orange (secteurs) = proche de la mediane (&plusmn;15%)</span>
      <span>&#9650; rouge (secteurs) = moins favorable que la mediane</span>
    </div>
  </details>

  <div class="onglets">
    <span class="groupe-onglets">Essentiel</span>
    <div class="onglet actif" onclick="onglet('synthese')">Synthese</div>
    <div class="onglet" onclick="onglet('surveillance')">Surveillance</div>
    <span class="separateur-onglets"></span>
    <span class="groupe-onglets">Marche</span>
    <div class="onglet" onclick="onglet('secteurs')">Secteurs</div>
    <div class="onglet" onclick="onglet('comparaison')">Comparaison</div>
    <span class="separateur-onglets"></span>
    <span class="groupe-onglets">Detail</span>
    <div class="onglet" onclick="onglet('fiche')">Fiche titre</div>
  </div>

  <div id="p-synthese" class="panneau actif">
    <div class="carte">
      <h2>Synthese classee <span style="font-weight:400;color:var(--muted);font-size:0.8em">(clic sur une ligne pour la fiche titre)</span></h2>
      <div class="barre-outils">
        <input type="text" id="recherche" placeholder="Rechercher un titre ou un secteur..." onkeyup="filtrerTable()">
        <select id="tri" onchange="trierTable()">
          <option value="rentabilite_desc">Rentabilite (decroissant)</option>
          <option value="solidite_desc">Solidite (decroissant)</option>
          <option value="valorisation_desc">Valorisation (decroissant)</option>
          <option value="secteur">Secteur</option>
          <option value="ticker">Titre (A-Z)</option>
        </select>
      </div>
      <div class="scroll"><table>
        <colgroup>
          <col style="width:9%"><col style="width:15%"><col style="width:13%">
          <col style="width:10%">
          <col style="width:9%"><col style="width:9%"><col style="width:10%"><col style="width:9%">
          <col style="width:16%">
        </colgroup>
        <thead><tr><th>Titre</th><th>Secteur</th><th>Profil</th><th>Taille</th>
          <th class="col-analytique num">Rentab.</th><th class="col-analytique num">Solidite</th>
          <th class="col-analytique num">Valoris.</th><th class="col-analytique num">{terme_glossaire('ROE')}</th>
          <th>Alertes</th></tr></thead>
        <tbody id="corps-synthese"></tbody>
      </table></div>
    </div>
    <div class="carte">
      <h2>Exclus ({len(excl)})</h2>
      <table><thead><tr><th>Titre</th><th>Secteur</th><th>Motif</th></tr></thead>
      <tbody>{lignes_exclus}</tbody></table>
    </div>
    <div class="carte">
      <h2>Donnees perimees (seuil {fraicheur['seuil_jours']}j)</h2>
      <table><thead><tr><th>Titre</th><th>Dernier mois</th><th>Anciennete</th></tr></thead>
      <tbody>{lignes_fraicheur or '<tr><td colspan="3">Aucune donnee perimee</td></tr>'}</tbody></table>
    </div>
    <div class="carte">
      <h2>Calendrier des publications <span style="font-weight:400;color:var(--muted);font-size:0.75em">
          (echeance reglementaire la plus proche par titre, annee en cours uniquement)</span></h2>
      <table><thead><tr><th>Titre</th><th>Categorie</th><th>Dernier depot</th><th>Echeance</th></tr></thead>
      <tbody>{lignes_calendrier or '<tr><td colspan="4">Aucune echeance en attente pour l\'annee en cours</td></tr>'}</tbody></table>
      <div style="font-size:0.75em;color:var(--muted);margin-top:8px">Echeance = delai reglementaire CREPMF
      (etats financiers et T1 : 30 avril ; T3 et semestriel : 31 octobre) applique au cycle en cours.
      L'historique confirme seulement que le titre publie cette categorie et si le cycle est deja satisfait.</div>
    </div>
  </div>

  <div id="p-surveillance" class="panneau">
    <div class="carte">
      <h2>Surveillance court/moyen terme — 47/47 titres couverts</h2>
      <select id="select-surveillance" onchange="tracerSurveillance()"></select>
      <canvas id="graph-cours"></canvas>
      <div style="height:14px"></div>
      <canvas id="graph-per"></canvas>
    </div>
  </div>

  <div id="p-fiche" class="panneau">
    <div class="carte">
      <h2>Fiche titre detaillee</h2>
      <select id="select-fiche" onchange="afficherFicheSelect()"></select>
      <div id="contenu-fiche"></div>
    </div>
  </div>

  <div id="p-comparaison" class="panneau">
    <div class="carte">
      <h2>Comparaison à deux titres <span style="font-weight:400;color:var(--muted);font-size:0.8em">(table uniquement — la précision compte plus qu'un graphique ici)</span></h2>
      <div style="display:flex;gap:10px;margin-bottom:14px">
        <select id="select-comp-a" onchange="comparer()" style="flex:1"></select>
        <select id="select-comp-b" onchange="comparer()" style="flex:1"></select>
      </div>
      <div id="contenu-comparaison"></div>
    </div>
  </div>

  <div id="p-secteurs" class="panneau">
    {tables_classement}
    {blocs_secteurs}
  </div>

  <div class="footer">Généré depuis brvm-data-pipeline — régénéré à chaque mise à jour du moteur</div>
</div>
<script>
const SERIES = {json.dumps(series)};
const FONDAMENTAUX = {json.dumps(fondamentaux)};
const AVIS = {json.dumps(avis)};
const SOURCE_URLS = {json.dumps(source_urls)};
const RESULTATS = {json.dumps({r["ticker"]: r for r in resultats})};
const TENDANCE_LIQUIDITE = {json.dumps(tendance_liquidite)};
const PROFILS = {json.dumps(profils)};
const LIBELLES_SECTEURS = {json.dumps(LIBELLES_SECTEURS_COURTS)};
const LIBELLES_STATUT = {{"ELIGIBLE": "Eligible", "EXCLU": "Exclu"}};
// Jumelle JS de humaniser() (Python) : meme transformation, pour les valeurs
// qui arrivent brutes cote JS (Comparaison) sans etre passees par le point
// d'humanisation Python (14/07/2026).
function humaniserJs(txt) {{
  if (!txt) return txt;
  return txt.replace(/\\b[A-Z][A-Z_]{{2,}}\\b/g, m => m.replace(/_/g, ' ').toLowerCase()
    .replace(/^./, c => c.toUpperCase()));
}}
function libelleSecteurJs(s) {{
  if (!s) return '—';
  const titre = s.replace(/_/g, ' ').toLowerCase().replace(/\\b\\w/g, c => c.toUpperCase());
  return LIBELLES_SECTEURS[titre] || titre;
}}
const LIGNES_SYNTHESE = {json.dumps(lignes_js)};
const SIZING_INFO = {json.dumps(SIZING)};
// Composant partage (harmonisation demandee le 14/07/2026) : utilise en Synthese,
// Fiche titre et Comparaison — un seul rendu possible pour "sizing" dans tout le site.
function renderSizing(code) {{
  const info = SIZING_INFO[code];
  if (!info) return '—';
  return `<span class="badge badge-${{info.classe}}" title="${{info.description}}">${{info.libelle}}</span>`;
}}
// Idem pour une alerte unique ou une liste d'alertes -> badge compact "N alerte(s)"
// replie par defaut (demande du 14/07/2026 : attirer l'attention sans imposer
// la lecture ; le detail reste a un clic, jamais cache totalement).
function renderAlertes(liste) {{
  if (!liste || !liste.length) return '<span class="alertes-ras">—</span>';
  const items = liste.map(a => `<li>${{a}}</li>`).join('');
  return `<details class="alertes-compact"><summary>&#9888; ${{liste.length}} alerte${{liste.length>1?'s':''}}</summary><ul>${{items}}</ul></details>`;
}}
// Profil de style : mini-graphique en barres TOUJOURS VISIBLE (correctif ergonomie
// du 14/07/2026, 2e iteration : les chiffres bruts "V82 G75 P71" etaient exacts
// mais peu lisibles d'un coup d'oeil ; la barre dominante ressort visuellement
// sans lecture requise, les chiffres precis restent en info-bulle).
// Rend un score 0-100 immediatement parlant par la couleur (vert = solide,
// orange = moyen, rouge = faible) au lieu d'un chiffre neutre sans repere
// (demande du 14/07/2026 : chiffres "pas spontanement indicatifs").
function renderScore(v) {{
  // Score 0-100 du moteur (Rentabilite/Solidite/Valorisation) : seuils absolus.
  if (v === null || v === undefined) return '<span class="score-na">—</span>';
  const cls = v >= 60 ? 'score-fort' : v >= 35 ? 'score-moyen' : 'score-faible';
  return `<span class="${{cls}}">${{v}}</span>`;
}}
function renderROE(v) {{
  // ROE en % (pas un score 0-100) : seuils propres au marche BRVM
  // (15%+ solide, 8-15% correct, <8% faible pour ce marche).
  if (v === null || v === undefined) return '<span class="score-na">—</span>';
  const cls = v >= 15 ? 'score-fort' : v >= 8 ? 'score-moyen' : 'score-faible';
  return `<span class="${{cls}}">${{v}}%</span>`;
}}
function renderProfil(dominant, scores) {{
  if (!dominant) return '<span class="chip chip-na">n/d</span>';
  const sc = scores || {{}};
  const titre = `VALUE ${{sc.VALUE}} \u00b7 GROWTH ${{sc.GROWTH}} \u00b7 GARP ${{sc.GARP}}`;
  const barre = (nom, cls) => sc[nom] !== null && sc[nom] !== undefined
    ? `<div class="pm-bar pm-${{cls}}${{dominant===nom?' pm-dom':''}}" style="height:${{sc[nom]}}%"></div>` : '';
  return `<span class="chip chip-${{dominant.toLowerCase()}}">${{dominant}}</span>`
       + `<div class="profil-mini" title="${{titre}}">${{barre('VALUE','value')}}${{barre('GROWTH','growth')}}${{barre('GARP','garp')}}</div>`;
}}
const TICKERS = {json.dumps(tous_tickers)};
// Point 4 (audit ergonomie, 14/07/2026) : une seule liste de tickers peuple
// les 4 menus deroulants (Surveillance, Fiche, Comparaison x2), au lieu de
// 4 copies HTML identiques generees cote serveur.
for (const id of ['select-surveillance','select-fiche','select-comp-a','select-comp-b']) {{
  document.getElementById(id).innerHTML = TICKERS.map(t => `<option value="${{t}}">${{t}}</option>`).join('');
}}
const GLOSSAIRE = {json.dumps(GLOSSAIRE)};

function rendreSynthese(lignes) {{
  const corps = document.getElementById('corps-synthese');
  const v = x => x !== null ? x : '—';
  corps.innerHTML = lignes.map(l => `
    <tr onclick="afficherFiche('${{l.ticker}}')" style="cursor:pointer">
      <td><b>${{l.ticker}}</b></td><td>${{l.secteur}}</td>
      <td>${{renderProfil(l.profil, l.profil_scores)}}</td>
      <td>${{renderSizing(l.sizing)}}</td>
      <td class="col-analytique num">${{renderScore(l.rentabilite)}}</td><td class="col-analytique num">${{renderScore(l.solidite)}}</td><td class="col-analytique num">${{renderScore(l.valorisation)}}</td>
      <td class="col-analytique num">${{renderROE(l.roe)}}</td>
      <td>${{renderAlertes(l.alertes)}}</td>
    </tr>`).join('');
}}
let ligneCourantes = [...LIGNES_SYNTHESE];
function filtrerTable() {{
  const q = document.getElementById('recherche').value.toLowerCase();
  ligneCourantes = LIGNES_SYNTHESE.filter(l => l.ticker.toLowerCase().includes(q) || l.secteur.toLowerCase().includes(q));
  trierTable();
}}
function trierTable() {{
  const tri = document.getElementById('tri').value;
  const l = [...ligneCourantes];
  const parNull = (a,b,champ) => (b[champ]??-1) - (a[champ]??-1);
  if (tri === 'rentabilite_desc') l.sort((a,b) => parNull(a,b,'rentabilite'));
  if (tri === 'solidite_desc') l.sort((a,b) => parNull(a,b,'solidite'));
  if (tri === 'valorisation_desc') l.sort((a,b) => parNull(a,b,'valorisation'));
  if (tri === 'score_desc') l.sort((a,b) => parNull(a,b,'score'));
  if (tri === 'score_asc') l.sort((a,b) => (a.score??999) - (b.score??999));
  if (tri === 'secteur') l.sort((a,b) => a.secteur.localeCompare(b.secteur) || parNull(a,b,'score'));
  if (tri === 'ticker') l.sort((a,b) => a.ticker.localeCompare(b.ticker));
  rendreSynthese(l);
}}
rendreSynthese(LIGNES_SYNTHESE);

let chartCours, chartPer;
function tracerSurveillance() {{
  const t = document.getElementById('select-surveillance').value;
  const d = SERIES[t] || [];
  const mois = d.map(x => x.mois), cours = d.map(x => x.cours), per = d.map(x => x.per);
  if (chartCours) chartCours.destroy();
  if (chartPer) chartPer.destroy();
  chartCours = new Chart(document.getElementById('graph-cours'), {{ type: 'line',
    data: {{ labels: mois, datasets: [{{ label: t + ' — Cours (FCFA)', data: cours,
             borderColor: '#2563eb', backgroundColor: '#2563eb33', fill: true, tension: 0.15, pointRadius: 0 }}] }},
    options: {{ scales: {{ y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }},
                           x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', maxTicksLimit: 12 }} }} }},
                plugins: {{ legend: {{ labels: {{ color: '#e2e8f0' }} }} }} }} }});
  chartPer = new Chart(document.getElementById('graph-per'), {{ type: 'line',
    data: {{ labels: mois, datasets: [{{ label: t + ' — PER', data: per,
             borderColor: '#0891b2', backgroundColor: '#0891b233', fill: true, tension: 0.15, pointRadius: 0 }}] }},
    options: {{ scales: {{ y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }},
                           x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', maxTicksLimit: 12 }} }} }},
                plugins: {{ legend: {{ labels: {{ color: '#e2e8f0' }} }} }} }} }});
}}

function afficherFicheSelect() {{ construireFiche(document.getElementById('select-fiche').value); }}
function afficherFiche(t) {{
  document.querySelectorAll('.panneau').forEach(p => p.classList.remove('actif'));
  document.querySelectorAll('.onglet').forEach(o => o.classList.remove('actif'));
  document.getElementById('p-fiche').classList.add('actif');
  document.querySelectorAll('.onglet')[2].classList.add('actif');
  document.getElementById('select-fiche').value = t;
  construireFiche(t);
}}
function ligneSource(t) {{
  const url = SOURCE_URLS[t];
  return url ? `<a class="sourcelien" href="${{url}}" target="_blank">Voir le document source →</a>`
             : `<span class="sourcelien indisponible">Document source non renseigne (gap connu, cf. section 21)</span>`;
}}
function construireSectionTendance(t) {{
  const tend = TENDANCE_LIQUIDITE[t];
  if (!tend) return '';
  const statut = tend.statut;
  let libelle, couleur, niveau_confiance;
  if (statut === 'CONFIRMEE_HAUSSE' || statut === 'CONFIRMEE_BAISSE') {{
    const dir = statut.endsWith('HAUSSE') ? 'hausse' : 'baisse';
    libelle = `TENDANCE CONFIRMEE (${{dir}})`;
    couleur = dir === 'hausse' ? '#2a9d5c' : '#c1502e';
    niveau_confiance = 'Ecart au-dela du seuil de confiance a 95% (test de permutation, 12/07/2026).';
  }} else if (statut === 'A_SURVEILLER_HAUSSE' || statut === 'A_SURVEILLER_BAISSE') {{
    const dir = statut.endsWith('HAUSSE') ? 'hausse' : 'baisse';
    libelle = `A SURVEILLER (${{dir}})`;
    couleur = '#c17a2a';
    niveau_confiance = 'NON confirme statistiquement — corrobore par le prix, signale pour detection precoce uniquement.';
  }} else {{
    libelle = 'STABLE';
    couleur = 'var(--muted)';
    niveau_confiance = 'Aucun mouvement significatif detecte sur les 3 derniers mois.';
  }}
  const ecart = (tend.ecart_volume_3v12*100).toFixed(0);
  const varPrix = tend.variation_prix_meme_periode !== null ? (tend.variation_prix_meme_periode*100).toFixed(1) : '—';
  return `
  <div class="carte" style="padding:14px;margin-bottom:16px">
    <h2 style="font-size:1em">Signal court terme (3 derniers mois vs 12 mois)</h2>
    <div style="color:${{couleur}};font-weight:600;font-size:1.05em;margin-bottom:6px">${{libelle}}</div>
    <div style="font-size:0.85em;color:var(--text)">Ecart de volume echange : ${{ecart}}% · Variation du prix sur la meme periode : ${{varPrix}}%</div>
    <div style="font-size:0.78em;color:var(--muted);margin-top:6px">${{niveau_confiance}}</div>
  </div>`;
}}

function construireFiche(t) {{
  const fonda = FONDAMENTAUX[t] || [];
  const r = RESULTATS[t] || {{}};
  const av = AVIS[t] || [];
  let html = '';
  html += construireSectionTendance(t);
  if (fonda.length <= 1) html += '<div class="photo-unique">⚠️ Photo unique (1 seul exercice fondamental disponible) — aucune tendance historique fiable pour ce titre</div>';
  if (fonda.length > 0) {{
    const f = fonda[0];
    html += '<div class="fiche-grille">';
    html += `<div class="fiche-stat"><div class="label">Exercice</div><div class="valeur">${{f.exercice}}</div></div>`;
    html += `<div class="fiche-stat"><div class="label">Résultat net (M FCFA)</div><div class="valeur">${{f.resultat_net ?? '—'}}</div></div>`;
    html += `<div class="fiche-stat"><div class="label">Statut de la donnée</div><div class="valeur">${{f.statut_donnee ?? '—'}}</div></div>`;
    html += `<div class="fiche-stat"><div class="label">Score</div><div class="valeur">${{r.score_composite ? r.score_composite.toFixed(1) : '—'}}</div></div>`;
    html += `<div class="fiche-stat"><div class="label">PEG</div><div class="valeur">${{PROFILS[t]?.peg ?? '—'}}</div></div>`;
    html += `<div class="fiche-stat"><div class="label">Taille</div><div class="valeur">${{r.sizing ? renderSizing(r.sizing.recommandation) : '—'}}</div></div>`;
    html += '</div>';
    html += `<div style="margin-bottom:14px">${{ligneSource(t)}}</div>`;
  }}
  html += '<h2 style="font-size:1em">Historique fondamental — vue transposée (' + fonda.length + ' exercice(s))</h2>';
  const exercicesTries = [...fonda].sort((a,b) => a.exercice - b.exercice);
  const cols = exercicesTries.map(f => f.exercice);
  html += '<div class="scroll"><table><thead><tr><th>Indicateur</th>' + cols.map(c => `<th>${{c}}</th>`).join('') + '</tr></thead><tbody>';
  const ligne = (label, fn) => '<tr><td class="alertes">' + label + '</td>' + exercicesTries.map(f => `<td>${{fn(f) ?? '—'}}</td>`).join('') + '</tr>';
  html += ligne('Chiffre d\\'affaires (M FCFA)', f => null);  // non collecte — gap assume, affiche honnetement
  html += ligne('Résultat net (M FCFA)', f => f.resultat_net);
  html += ligne('Croissance RN', f => (f.resultat_net != null && f.resultat_net_n1 && f.resultat_net_n1 !== 0)
    ? ((f.resultat_net - f.resultat_net_n1) / Math.abs(f.resultat_net_n1) * 100).toFixed(1) + '%' : null);
  html += ligne('Resultat activites ordinaires (RAO)', f => f.resultat_activites_ordinaires);
  html += ligne('Capitaux propres (M FCFA)', f => f.capitaux_propres);
  html += ligne('ROE calcule', f => (f.resultat_net != null && f.capitaux_propres && f.capitaux_propres > 0)
    ? (f.resultat_net / f.capitaux_propres * 100).toFixed(1) + '%' : null);
  html += ligne('Statut de la donnée', f => f.statut_donnee);
  html += '</tbody></table></div>';
  html += '<div style="font-size:0.75em;color:var(--muted);margin:6px 0 14px">Chiffre d\\'affaires non collecté actuellement (lacune connue) — affiché pour référence, pas une omission masquée.</div>';
  if (av.length > 0) {{
    html += '<h2 style="font-size:1em">Avis réglementaires</h2><table><thead><tr><th>Type</th><th>Date</th><th>Detail</th></tr></thead><tbody>';
    av.forEach(a => {{ html += `<tr><td>${{a.type}}</td><td>${{a.date_avis}}</td><td class="alertes">${{a.note}}</td></tr>`; }});
    html += '</tbody></table>';
  }}
  if (r.alertes && r.alertes.length > 0) {{
    html += '<h2 style="font-size:1em">Toutes les alertes du moteur</h2><ul class="alertes">';
    r.alertes.forEach(a => {{ html += `<li>${{a}}</li>`; }});
    html += '</ul>';
  }}
  document.getElementById('contenu-fiche').innerHTML = html;
}}

function comparer() {{
  const a = document.getElementById('select-comp-a').value;
  const b = document.getElementById('select-comp-b').value;
  const ra = RESULTATS[a] || {{}}, rb = RESULTATS[b] || {{}};
  const fa = (FONDAMENTAUX[a] || [])[0] || {{}};
  const fb = (FONDAMENTAUX[b] || [])[0] || {{}};
  const roeA = calculerRoeJs(FONDAMENTAUX[a]), roeB = calculerRoeJs(FONDAMENTAUX[b]);
  const lignes = [
    ['Secteur', libelleSecteurJs(ra.secteur), libelleSecteurJs(rb.secteur)],
    ['Score composite', ra.score_composite?.toFixed(1) ?? '—', rb.score_composite?.toFixed(1) ?? '—'],
    ['Statut', LIBELLES_STATUT[ra.statut_gate] ?? '—', LIBELLES_STATUT[rb.statut_gate] ?? '—'],
    ['PEG', PROFILS[a]?.peg ?? '—', PROFILS[b]?.peg ?? '—'],
    ['Résultat net (M FCFA)', fa.resultat_net ?? '—', fb.resultat_net ?? '—'],
    ['ROE', roeA !== null ? (roeA*100).toFixed(1)+'%' : '—', roeB !== null ? (roeB*100).toFixed(1)+'%' : '—'],
    ['Taille de position', ra.sizing ? renderSizing(ra.sizing.recommandation) : '—', rb.sizing ? renderSizing(rb.sizing.recommandation) : '—'],
    ['Exercices disponibles', (FONDAMENTAUX[a]||[]).length, (FONDAMENTAUX[b]||[]).length],
  ];
  let html = '<table><thead><tr><th>Indicateur</th><th>' + a + '</th><th>' + b + '</th></tr></thead><tbody>';
  lignes.forEach(l => {{ html += `<tr><td class="alertes">${{l[0]}}</td><td>${{l[1]}}</td><td>${{l[2]}}</td></tr>`; }});
  html += '</tbody></table>';
  document.getElementById('contenu-comparaison').innerHTML = html;
}}
function calculerRoeJs(fonda) {{
  if (!fonda || fonda.length === 0) return null;
  const f = fonda[0];
  if (f.resultat_net && f.capitaux_propres && f.capitaux_propres > 0) return f.resultat_net / f.capitaux_propres;
  return null;
}}

document.querySelectorAll('.gloss').forEach(el => {{
  const bulle = document.createElement('span');
  bulle.className = 'bulle';
  bulle.textContent = el.dataset.def;
  el.appendChild(bulle);
  el.addEventListener('click', (e) => {{ e.stopPropagation(); el.classList.toggle('ouvert'); }});
}});
document.addEventListener('click', () => document.querySelectorAll('.gloss.ouvert').forEach(g => g.classList.remove('ouvert')));

function onglet(nom) {{
  document.querySelectorAll('.panneau').forEach(p => p.classList.remove('actif'));
  document.querySelectorAll('.onglet').forEach(o => o.classList.remove('actif'));
  document.getElementById('p-' + nom).classList.add('actif');
  event.currentTarget.classList.add('actif');
  if (nom === 'surveillance' && !chartCours) tracerSurveillance();
  if (nom === 'fiche' && !document.getElementById('contenu-fiche').innerHTML) construireFiche(document.getElementById('select-fiche').value);
  if (nom === 'comparaison' && !document.getElementById('contenu-comparaison').innerHTML) comparer();
}}
</script>
</body>
</html>"""


def main():
    resultats, series, fondamentaux, avis, source_urls, profils = collecter_donnees()
    seuils = charger_seuils()
    marche = charger_marche()
    liquidite_jour = charger_liquidite_jour()
    liquidite_generale = charger_liquidite_generale()
    tendance_liquidite = charger_tendance_liquidite()
    fraicheur = rapport_fraicheur()
    html = generer_html(resultats, series, fondamentaux, avis, source_urls, seuils, fraicheur, marche,
                        liquidite_jour, liquidite_generale, tendance_liquidite, profils)
    sortie = Path(__file__).resolve().parent.parent / "docs_site"
    sortie.mkdir(exist_ok=True)
    (sortie / "index.html").write_text(html, encoding="utf-8")
    n_sources = sum(1 for u in source_urls.values() if u)
    n_liq_jour = len(liquidite_jour)
    n_liq_gen = len(liquidite_generale)
    n_tendance = len(tendance_liquidite)
    print(f"Dashboard HTML v3 genere : {sortie / 'index.html'} ({len(resultats)} titres, "
          f"{n_sources}/{len(source_urls)} avec source_url renseignee, "
          f"{n_liq_jour} avec liquidite du jour, {n_liq_gen} avec liquidite generale, "
          f"{n_tendance} avec tendance calculee)")


if __name__ == "__main__":
    main()
