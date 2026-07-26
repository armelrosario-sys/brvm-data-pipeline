#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/verifier_continuite.py — Correctif (25/07/2026).

Remplace le controle de continuite fait EN DIRECT dans
backfill_boc_quotidien.py, qui etait biaise : ce dernier traite les mois du
plus recent au plus ancien, donc le "dernier cours vu" au debut de chaque
mois plus ancien etait en realite celui d'un mois PLUS RECENT deja traite --
d'ou 87 des 88 alertes du premier run tombant exactement sur le 1er jour de
bourse de chaque mois (artefact d'ordre de traitement, pas un vrai
mouvement de marche). Constate en verifiant les resultats du run du
25/07/2026, corrige avant que le fichier ne soit utilise pour autre chose.

Ce script relit l'INTEGRALITE de cours_quotidien_boc.csv, trie chaque
ticker par date reellement croissante, et ne compare que des jours
consecutifs dans le bon ordre. Fichier de sortie recalcule en entier
(ecrase, contrairement aux fichiers d'evenements append-only du reste du
pipeline -- celui-ci est un rapport derive, jamais une source primaire).

Usage : python3 collecte/verifier_continuite.py
"""
import csv
import json
import os
from collections import defaultdict
from datetime import date

CSV_QUOTIDIEN = "collecte/cours_quotidien_boc.csv"
OPERATIONS = "collecte/operations_sur_titre.csv"
EVENEMENTS_MARCHE = "collecte/evenements_marche.csv"
SORTIE = "collecte/continuite_suspecte.jsonl"
SEUIL = 0.20


def charger_operations_connues():
    """Sauts deja expliques (dividendes, DPS, splits...) -> ne plus les
    re-signaler a chaque run. Retourne un set de (ticker, date_iso)."""
    connues = set()
    if os.path.exists(OPERATIONS):
        with open(OPERATIONS, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                connues.add((row["ticker"], row["date"]))
    return connues


def charger_evenements_marche():
    """Evenements globaux (revision d'indice, etc.) -> une date suffit,
    s'applique a TOUS les titres ce jour-la (contrairement a
    operations_sur_titre.csv qui est specifique a un titre)."""
    dates = set()
    if os.path.exists(EVENEMENTS_MARCHE):
        with open(EVENEMENTS_MARCHE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dates.add(row["date"])
    return dates


def main():
    connues = charger_operations_connues()
    dates_evenement = charger_evenements_marche()
    par_ticker = defaultdict(list)
    with open(CSV_QUOTIDIEN, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("cours"):
                continue
            try:
                d = date.fromisoformat(row["date_bulletin"])
                cours = float(row["cours"])
            except (ValueError, TypeError):
                continue
            par_ticker[row["ticker"]].append((d, cours))

    suspects, expliques = [], 0
    for ticker, points in par_ticker.items():
        points.sort(key=lambda p: p[0])  # ordre chronologique reel, garanti
        for (d_prec, c_prec), (d_actuel, c_actuel) in zip(points, points[1:]):
            if c_prec == 0:
                continue
            variation = abs(c_actuel - c_prec) / c_prec
            if variation > SEUIL:
                if (ticker, d_actuel.isoformat()) in connues or d_actuel.isoformat() in dates_evenement:
                    expliques += 1
                    continue
                suspects.append({
                    "ticker": ticker,
                    "date_precedente": d_prec.isoformat(),
                    "cours_precedent": c_prec,
                    "date": d_actuel.isoformat(),
                    "cours": c_actuel,
                    "variation": round(variation, 4),
                })

    with open(SORTIE, "w", encoding="utf-8") as f:
        for s in sorted(suspects, key=lambda x: x["date"]):
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"{len(suspects)} saut(s) a verifier, {expliques} deja explique(s) "
          f"(operations_sur_titre.csv + evenements_marche.csv), sur {len(par_ticker)} tickers.")


if __name__ == "__main__":
    main()
