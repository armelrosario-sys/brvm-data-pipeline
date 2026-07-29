#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/charger_cours_quotidien.py — (28/07/2026).

Pont manquant identifie le 28/07/2026 : la table cours_quotidien_boc existe
dans schema.sql depuis le 18/07/2026, concue precisement pour accumuler une
ligne par jour de cotation (contrairement a cours_mensuels qui n'en garde
qu'une par mois) -- mais rien ne l'alimentait depuis collecte/cours_quotidien_boc.csv
(1886 jours au 28/07/2026, Piste B). Ce script comble ce pont, sur le meme
modele que charger_cours.py (cours_mensuels).

INSERT OR REPLACE : idempotent, peut tourner a chaque publication sans
creer de doublons (cle primaire ticker+date_bulletin).

Usage : python3 collecte/charger_cours_quotidien.py [chemin_db]
"""
import csv
import sqlite3
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
CSV_SOURCE = str(_BASE / "cours_quotidien_boc.csv")
DB = sys.argv[1] if len(sys.argv) > 1 else str(_BASE.parent / "moteur" / "brvm.db")


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n = 0
    tickers, dates = set(), set()
    with open(CSV_SOURCE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("date_bulletin") or not r.get("ticker"):
                continue
            cur.execute(
                "INSERT OR REPLACE INTO cours_quotidien_boc "
                "(ticker, date_bulletin, cours, per, rendement) "
                "VALUES (?,?,?,?,?)",
                (r["ticker"], r["date_bulletin"],
                 float(r["cours"]) if r.get("cours") else None,
                 float(r["per"]) if r.get("per") else None,
                 float(r["rendement"]) / 100 if r.get("rendement") else None))
            n += 1
            tickers.add(r["ticker"])
            dates.add(r["date_bulletin"])
    conn.commit()
    print(f"{n} lignes inserees/mises a jour dans cours_quotidien_boc "
          f"({len(tickers)} tickers, {len(dates)} jours, "
          f"{min(dates) if dates else '?'} -> {max(dates) if dates else '?'}).")
    conn.close()


if __name__ == "__main__":
    main()
