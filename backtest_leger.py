#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest leger — Hypothese : un titre au PER decote vs sa mediane
sectorielle du mois surperforme-t-il en rendement PRIX sur les 12 mois
suivants ? Utilise cours_mensuels (deja peuple, 2018-2026, 47 titres) et
societes.secteur. LIMITE ASSUMEE : rendement PRIX seul (dividendes non
inclus ici) — un backtest en rendement total est un prochain pas, pas
celui-ci. Aucune decision d'investissement sur ce resultat seul.
"""
import sqlite3
from pathlib import Path
from statistics import median, mean

DB = Path(__file__).resolve().parent / "moteur" / "brvm.db"


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
        "SELECT ticker, fin_mois, cours, per FROM cours_mensuels "
        "WHERE cours IS NOT NULL AND per IS NOT NULL").fetchall()
    conn.close()

    par_mois = {}
    for tick, fm, cours, per in rows:
        par_mois.setdefault(fm, []).append((tick, cours, per))
    cours_par_tick_mois = {(t, fm): c for t, fm, c, p in rows}

    mois_tries = sorted(par_mois)
    resultats_decotes, resultats_chers = [], []
    n_mois_testes = 0

    for fm in mois_tries:
        fm12 = mois_suivant(fm, 12)
        if fm12 not in par_mois:
            continue
        lignes = par_mois[fm]
        par_secteur = {}
        for tick, cours, per in lignes:
            sec = secteurs.get(tick)
            if sec:
                par_secteur.setdefault(sec, []).append(per)
        n_mois_testes += 1
        for tick, cours, per in lignes:
            sec = secteurs.get(tick)
            if not sec or len(par_secteur.get(sec, [])) < 3:
                continue
            med = median(par_secteur[sec])
            cours_fut = cours_par_tick_mois.get((tick, fm12))
            if cours_fut is None or cours <= 0:
                continue
            rdt_12m = (cours_fut - cours) / cours
            decote = (med - per) / med if med else 0
            (resultats_decotes if decote > 0 else resultats_chers).append(rdt_12m)

    print(f"Mois testes (avec 12m de recul disponible) : {n_mois_testes}")
    print(f"Observations 'decote vs secteur'  : n={len(resultats_decotes)}, "
          f"rendement 12m moyen = {mean(resultats_decotes):+.1%}" if resultats_decotes else "n=0")
    print(f"Observations 'cher vs secteur'     : n={len(resultats_chers)}, "
          f"rendement 12m moyen = {mean(resultats_chers):+.1%}" if resultats_chers else "n=0")
    if resultats_decotes and resultats_chers:
        ecart = mean(resultats_decotes) - mean(resultats_chers)
        print(f"\nEcart (decote - cher) : {ecart:+.1%}")
        print("\nLIMITES : rendement PRIX seul (dividendes exclus) ; pas de neutralisation "
              "du biais du survivant (titres radies absents) ; chevauchement des fenetres "
              "12 mois (observations non independantes, IC non calcule) ; resultat "
              "DIRECTIONNEL, pas une preuve statistique — cf. section 6 du document de reference.")


if __name__ == "__main__":
    main()
