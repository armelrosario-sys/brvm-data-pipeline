#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_bootstrap_blocs.py — (29/07/2026).

Repond a la question : l'ecart (decote - cher) trouve par backtest_leger.py
est-il statistiquement significatif, ou pourrait-il etre du au hasard ?

Methode : bootstrap PAR TITRE (pas par observation individuelle), car les
observations d'un meme titre a des mois consecutifs se chevauchent
(fenetres de 12 mois glissantes) et ne sont donc PAS independantes -- un
bootstrap naif sur les observations individuelles sous-estimerait la vraie
incertitude. On rehantillonne les TITRES avec remise (en gardant toutes
leurs observations ensemble), on recalcule l'ecart a chaque tirage, et on
lit l'intervalle a 95% sur la distribution des ecarts obtenus.

Usage : python3 backtest_bootstrap_blocs.py [n_tirages]
"""
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

DB = Path(__file__).resolve().parent / "moteur" / "brvm.db"
N_TIRAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 3000


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

    par_mois = defaultdict(list)
    for tick, fm, cours, per in rows:
        par_mois[fm].append((tick, cours, per))
    cours_par_tick_mois = {(t, fm): c for t, fm, c, p in rows}

    # observations groupees PAR TITRE (bloc = toutes les observations d'un titre)
    obs_par_titre = defaultdict(list)  # ticker -> liste de (decote_bool, rendement_12m)
    for fm in sorted(par_mois):
        fm12 = mois_suivant(fm, 12)
        if fm12 not in par_mois:
            continue
        lignes = par_mois[fm]
        par_secteur = defaultdict(list)
        for tick, cours, per in lignes:
            sec = secteurs.get(tick)
            if sec:
                par_secteur[sec].append(per)
        for tick, cours, per in lignes:
            sec = secteurs.get(tick)
            if not sec or len(par_secteur[sec]) < 3:
                continue
            med = median(par_secteur[sec])
            cours_fut = cours_par_tick_mois.get((tick, fm12))
            if cours_fut is None or cours <= 0:
                continue
            rdt = (cours_fut - cours) / cours
            decote = (med - per) / med if med else 0
            obs_par_titre[tick].append((decote > 0, rdt))

    titres = [t for t in obs_par_titre if len(obs_par_titre[t]) >= 3]
    print(f"{len(titres)} titres avec au moins 3 observations, "
          f"{sum(len(obs_par_titre[t]) for t in titres)} observations au total")

    def ecart_sur(liste_titres):
        d, c = [], []
        for t in liste_titres:
            for est_decote, rdt in obs_par_titre[t]:
                (d if est_decote else c).append(rdt)
        if not d or not c:
            return None
        return mean(d) - mean(c)

    ecart_observe = ecart_sur(titres)
    print(f"Ecart observe (decote - cher) : {ecart_observe:+.1%}")

    random.seed(42)
    ecarts_bootstrap = []
    for _ in range(N_TIRAGES):
        echantillon = [random.choice(titres) for _ in titres]
        e = ecart_sur(echantillon)
        if e is not None:
            ecarts_bootstrap.append(e)
    ecarts_bootstrap.sort()
    n = len(ecarts_bootstrap)
    ic_bas = ecarts_bootstrap[int(0.025 * n)]
    ic_haut = ecarts_bootstrap[int(0.975 * n)]
    print(f"IC 95% (bootstrap par titre, {n} tirages) : [{ic_bas:+.1%} ; {ic_haut:+.1%}]")
    if ic_bas <= 0 <= ic_haut:
        print("-> L'intervalle inclut zero : PAS statistiquement significatif "
              "a ce seuil, meme avec les donnees actuelles.")
    else:
        print("-> L'intervalle EXCLUT zero : statistiquement significatif a 95%.")


if __name__ == "__main__":
    main()
