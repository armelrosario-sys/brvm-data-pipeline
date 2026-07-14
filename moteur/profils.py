#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/profils.py — Etiquettes de style par titre (VALUE/GROWTH/GARP).
Percentiles MARCHE sur donnees reelles en base — jamais de seuils absolus.
Garde anti-effet de base : croissance calculee uniquement sur exercices
consecutivement beneficiaires. Sortie : profils.json (consomme par le
poste de decision et la fiche titre). Etiquette DESCRIPTIVE, jamais decisionnelle.
Justification microstructure : tous les ingredients (PER mensuel BOC, rendement,
RN, capitaux propres) sont VERIFIES en base ; aucun indicateur court terme."""
import sqlite3, json
from pathlib import Path
DB = Path(__file__).resolve().parent / "brvm.db"
SORTIE = Path(__file__).resolve().parent.parent / "collecte" / "profils.json"
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import charger_seuils, charger_marche, appliquer_gate

def pctl(vals, x, inverse=False):
    vals = sorted(v for v in vals if v is not None)
    if x is None or not vals: return None
    return round(100 * sum(1 for v in vals if (v >= x if inverse else v <= x)) / len(vals))

def calculer():
    c = sqlite3.connect(DB).cursor()
    seuils, marche = charger_seuils(), charger_marche()
    # Correctif 14/07/2026 : ces seuils vivaient en dur, rapatries dans seuils.yaml
    sp = seuils.get("profils", {})
    fenetre_max = sp.get("fenetre_exercices_max", 4)
    seuil_mixite = sp.get("seuil_mixite_pts", 20)
    conf_haute = sp.get("confiance_haute_min_exercices", 4)
    conf_moyenne = sp.get("confiance_moyenne_min_exercices", 2)
    alerte_peg_max = sp.get("alerte_peg_plausibilite_max", 0.20)
    sect = dict(c.execute("SELECT ticker, secteur FROM societes"))
    ing = {}
    tickers = [r[0] for r in c.execute("SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%'").fetchall()]
    for t in tickers:
        per = c.execute("SELECT per FROM cours_mensuels WHERE ticker=? AND per IS NOT NULL ORDER BY fin_mois DESC LIMIT 1",(t,)).fetchone()
        rdt = c.execute("SELECT rendement FROM cours_mensuels WHERE ticker=? AND rendement IS NOT NULL ORDER BY fin_mois DESC LIMIT 1",(t,)).fetchone()
        ex = c.execute("SELECT exercice,resultat_net,capitaux_propres FROM etats_financiers WHERE ticker=? AND resultat_net IS NOT NULL ORDER BY exercice DESC",(t,)).fetchall()
        roe = 100*ex[0][1]/ex[0][2] if ex and ex[0][2] and ex[0][2] > 0 else None
        g = None  # croissance annualisee, exercices consecutivement beneficiaires uniquement
        serie = [e for e in ex if e[1] and e[1] > 0][:fenetre_max]
        if len(serie) >= 2 and serie[0][0] > serie[-1][0]:
            n = serie[0][0] - serie[-1][0]
            g = 100*((serie[0][1]/serie[-1][1])**(1/n) - 1)
        st, _ = appliquer_gate(c, t, sect.get(t, ""), seuils, marche)
        ing[t] = dict(per=per[0] if per else None, dy=100*rdt[0] if rdt else None,
                      roe=roe, g=g, gate=st, n_ex=len(ex))
    E = {t: v for t, v in ing.items() if v["gate"] == "ELIGIBLE"}

    # Correctif 14/07/2026 (retour utilisateur, evidences chiffrees a l'appui) :
    # les percentiles etaient calcules sur TOUT LE MARCHE, jamais par secteur --
    # exactement l'incoherence que le gate evite deja (mediane sectorielle).
    # Consequence mesuree : PER median Services Financiers 12.6 vs Industriels
    # 36.0 -> toute banque, meme moyenne pour son secteur, ressortait "VALUE"
    # par le seul effet du multiple structurellement plus bas des banques,
    # jamais parce qu'elle etait reellement decotee PARMI SES PAIRS. Corrige :
    # chaque titre est desormais compare a son propre secteur, comme le gate.
    par_secteur = {}
    for t, v in E.items():
        sec = sect.get(t, "")
        d = par_secteur.setdefault(sec, {"per": [], "dy": [], "roe": [], "g": [], "peg": []})
        if v["per"] is not None: d["per"].append(v["per"])
        if v["dy"] is not None: d["dy"].append(v["dy"])
        if v["roe"] is not None: d["roe"].append(v["roe"])
        if v["g"] is not None: d["g"].append(v["g"])
        peg_v = v["per"]/v["g"] if (v["per"] and v["g"] and v["g"] > 0) else None
        if peg_v is not None: d["peg"].append(peg_v)

    profils = {}
    for t, v in E.items():
        sec = sect.get(t, "")
        listes = par_secteur[sec]
        pv_per = pctl(listes["per"], v["per"], True); pv_dy = pctl(listes["dy"], v["dy"])
        pg_g = pctl(listes["g"], v["g"]); pg_roe = pctl(listes["roe"], v["roe"])
        peg = v["per"]/v["g"] if (v["per"] and v["g"] and v["g"] > 0) else None
        pg_peg = pctl(listes["peg"], peg, True) if peg is not None else None
        sc = {"VALUE": round(0.5*(pv_per or 0)+0.5*(pv_dy or 0)) if (pv_per or pv_dy) else None,
              "GROWTH": round(0.6*(pg_g or 0)+0.4*(pg_roe or 0)) if v["g"] is not None else None,
              "GARP": round(0.6*(pg_peg or 0)+0.4*(pg_g or 0)) if peg is not None else None}
        dispo = {k: x for k, x in sc.items() if x is not None}
        tri = sorted(dispo.values(), reverse=True)
        profils[t] = dict(**sc, dominant=max(dispo, key=dispo.get) if dispo else None,
            mixte=len(tri) >= 2 and (tri[0]-tri[1]) < seuil_mixite,
            peg=round(peg, 2) if peg else None,
            alerte_peg=bool(peg is not None and peg < alerte_peg_max),  # plausibilite (cas SLBC)
            n_secteur=len(listes["per"]),  # transparence : taille de l'echantillon sectoriel utilise
            confiance="HAUTE" if v["n_ex"] >= conf_haute else "MOYENNE" if v["n_ex"] >= conf_moyenne else "FAIBLE", **v)
    SORTIE.write_text(json.dumps(profils, ensure_ascii=False, indent=1))
    print(f"profils.json : {len(profils)} titres profiles")
    return profils

if __name__ == "__main__":
    calculer()
