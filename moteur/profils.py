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
    sect = dict(c.execute("SELECT ticker, secteur FROM societes"))
    ing = {}
    for (t,) in c.execute("SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%'"):
        per = c.execute("SELECT per FROM cours_mensuels WHERE ticker=? AND per IS NOT NULL ORDER BY fin_mois DESC LIMIT 1",(t,)).fetchone()
        rdt = c.execute("SELECT rendement FROM cours_mensuels WHERE ticker=? AND rendement IS NOT NULL ORDER BY fin_mois DESC LIMIT 1",(t,)).fetchone()
        ex = c.execute("SELECT exercice,resultat_net,capitaux_propres FROM etats_financiers WHERE ticker=? AND resultat_net IS NOT NULL ORDER BY exercice DESC",(t,)).fetchall()
        roe = 100*ex[0][1]/ex[0][2] if ex and ex[0][2] and ex[0][2] > 0 else None
        g = None  # croissance annualisee, exercices consecutivement beneficiaires uniquement
        serie = [e for e in ex if e[1] and e[1] > 0][:4]
        if len(serie) >= 2 and serie[0][0] > serie[-1][0]:
            n = serie[0][0] - serie[-1][0]
            g = 100*((serie[0][1]/serie[-1][1])**(1/n) - 1)
        st, _ = appliquer_gate(c, t, sect.get(t, ""), seuils, marche)
        ing[t] = dict(per=per[0] if per else None, dy=100*rdt[0] if rdt else None,
                      roe=roe, g=g, gate=st, n_ex=len(ex))
    E = {t: v for t, v in ing.items() if v["gate"] == "ELIGIBLE"}
    PERs=[v["per"] for v in E.values()]; DYs=[v["dy"] for v in E.values()]
    ROEs=[v["roe"] for v in E.values()]; Gs=[v["g"] for v in E.values()]
    pegs=[v["per"]/v["g"] for v in E.values() if v["per"] and v["g"] and v["g"] > 0]
    profils = {}
    for t, v in E.items():
        pv_per=pctl(PERs, v["per"], True); pv_dy=pctl(DYs, v["dy"])
        pg_g=pctl(Gs, v["g"]); pg_roe=pctl(ROEs, v["roe"])
        peg = v["per"]/v["g"] if (v["per"] and v["g"] and v["g"] > 0) else None
        s = {"VALUE": round(0.5*(pv_per or 0)+0.5*(pv_dy or 0)) if (pv_per or pv_dy) else None,
             "GROWTH": round(0.6*(pg_g or 0)+0.4*(pg_roe or 0)) if v["g"] is not None else None,
             "GARP": round(0.6*pctl(pegs, peg, True)+0.4*(pg_g or 0)) if peg is not None else None}
        dispo = {k: x for k, x in s.items() if x is not None}
        tri = sorted(dispo.values(), reverse=True)
        profils[t] = dict(**s, dominant=max(dispo, key=dispo.get) if dispo else None,
            mixte=len(tri) >= 2 and (tri[0]-tri[1]) < 20,
            peg=round(peg, 2) if peg else None,
            alerte_peg=bool(peg is not None and peg < 0.2),  # plausibilite (cas SLBC)
            confiance="HAUTE" if v["n_ex"] >= 4 else "MOYENNE" if v["n_ex"] >= 2 else "FAIBLE", **v)
    SORTIE.write_text(json.dumps(profils, ensure_ascii=False, indent=1))
    print(f"profils.json : {len(profils)} titres profiles")
    return profils

if __name__ == "__main__":
    calculer()
