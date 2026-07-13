#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3 — Charge cours_extraits.csv (sortie de l'extracteur BOC) dans cours_mensuels.
Un ticker peut apparaitre sur plusieurs BOC du meme mois (rare, doublons de
collecte) : on garde la ligne la plus tardive du mois. liquidite_ratio non
extrait a ce stade (limite documentee, cf. section 12 du document de reference)."""
import csv, sqlite3, sys
from datetime import datetime
from pathlib import Path

from pathlib import Path
_BASE = Path(__file__).resolve().parent
CSV_SOURCE = str(_BASE / "cours_extraits.csv")
DB = sys.argv[1] if len(sys.argv) > 1 else str(_BASE.parent / "moteur" / "brvm.db")


def periode(date_bulletin):
    d = datetime.strptime(date_bulletin, "%Y%m%d")
    return f"{d.year:04d}-{d.month:02d}"


def main():
    rows = list(csv.DictReader(open(CSV_SOURCE, encoding="utf-8")))
    meilleur = {}  # (ticker, periode) -> ligne la plus recente
    for r in rows:
        if not r["date_bulletin"]:
            continue
        p = periode(r["date_bulletin"])
        cle = (r["ticker"], p)
        if cle not in meilleur or r["date_bulletin"] > meilleur[cle]["date_bulletin"]:
            meilleur[cle] = r

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n = 0
    for (ticker, p), r in meilleur.items():
        cur.execute(
            "INSERT OR REPLACE INTO cours_mensuels "
            "(ticker, fin_mois, cours, per, rendement, liquidite_ratio) "
            "VALUES (?,?,?,?,?,NULL)",
            (ticker, p,
             float(r["cours"]) if r["cours"] else None,
             float(r["per"]) if r["per"] else None,
             float(r["rendement"]) / 100 if r["rendement"] else None))
        n += 1
    conn.commit()
    print(f"{n} lignes inserees dans cours_mensuels "
          f"({len(set(k[0] for k in meilleur))} tickers, "
          f"{len(set(k[1] for k in meilleur))} mois).")
    conn.close()


if __name__ == "__main__":
    main()
