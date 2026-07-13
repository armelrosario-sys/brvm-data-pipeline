#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest rendement TOTAL (prix + dividende) — approximation.
Utilise le champ 'rendement' de cours_mensuels (rendement net BOC = dernier
dividende/cours au mois de depart) comme proxy du revenu de dividende sur les
12 mois suivants. Approximation assumee : le rendement affiche au mois M est
traite comme le flux de dividende percu sur M->M+12. Limite reelle si le
dividende change en cours de route (sous-estime ou surestime localement).
"""
import sqlite3
from pathlib import Path
from statistics import median, mean

DB = Path(__file__).resolve().parent / "moteur" / "brvm.db"
EXCLUS_ILLIQUIDES = {"UNLC", "SIVC", "STBC", "CFAC", "BOAM", "BICC"}


def mois_suivant(fin_mois, offset):
    a, m = map(int, fin_mois.split("-"))
    total = a * 12 + (m - 1) + offset
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    secteurs = dict(cur.execute(
        "SELECT ticker, secteur FROM societes WHERE ticker NOT LIKE 'TEST_%'").fetchall())
    rows = cur.execute(
        "SELECT ticker, fin_mois, cours, per, rendement FROM cours_mensuels "
        "WHERE cours IS NOT NULL AND per IS NOT NULL").fetchall()
    conn.close()

    par_mois = {}
    for tick, fm, cours, per, rdt in rows:
        par_mois.setdefault(fm, []).append((tick, cours, per, rdt))
    cours_par_tick_mois = {(t, fm): c for t, fm, c, p, r in rows}

    for exclure_illiquides in (False, True):
        d_prix, c_prix, d_total, c_total = [], [], [], []
        for fm in sorted(par_mois):
            fm12 = mois_suivant(fm, 12)
            if fm12 not in par_mois:
                continue
            lignes = par_mois[fm]
            par_secteur = {}
            for tick, cours, per, rdt in lignes:
                if exclure_illiquides and tick in EXCLUS_ILLIQUIDES:
                    continue
                sec = secteurs.get(tick)
                if sec:
                    par_secteur.setdefault(sec, []).append(per)
            for tick, cours, per, rdt in lignes:
                if exclure_illiquides and tick in EXCLUS_ILLIQUIDES:
                    continue
                sec = secteurs.get(tick)
                if not sec or len(par_secteur.get(sec, [])) < 3:
                    continue
                med = median(par_secteur[sec])
                cours_fut = cours_par_tick_mois.get((tick, fm12))
                if cours_fut is None or cours <= 0:
                    continue
                rdt_prix = (cours_fut - cours) / cours
                rdt_div = rdt if rdt else 0.0
                rdt_totalT = rdt_prix + rdt_div
                decote = (med - per) / med if med else 0
                if decote > 0:
                    d_prix.append(rdt_prix); d_total.append(rdt_totalT)
                else:
                    c_prix.append(rdt_prix); c_total.append(rdt_totalT)

        label = "SANS les 6 illiquides" if exclure_illiquides else "TOUS les titres"
        print(f"\n=== {label} ===")
        print(f"{'':<12}{'Prix seul':<14}{'Prix + dividende'}")
        print(f"Decote (n={len(d_total)})  {mean(d_prix):+.1%}         {mean(d_total):+.1%}")
        print(f"Cher   (n={len(c_total)})  {mean(c_prix):+.1%}         {mean(c_total):+.1%}")
        print(f"Ecart                {mean(d_prix)-mean(c_prix):+.1%}         "
              f"{mean(d_total)-mean(c_total):+.1%}")


if __name__ == "__main__":
    main()
