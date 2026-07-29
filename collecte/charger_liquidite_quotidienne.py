#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/charger_liquidite_quotidienne.py — (28/07/2026).

Pont manquant identifie le 28/07/2026 : collecte/liquidite_quotidienne_historique.csv
(1791 jours, Piste C) n'etait charge nulle part -- seul collecte/historique_liquidite.json
(fenetre glissante de 60 jours, volontairement purgee a chaque collecte
quotidienne pour l'usage temps reel) etait lu par le moteur. Ce script
charge l'historique COMPLET dans une table dediee (liquidite_quotidienne,
schema.sql) qui n'est jamais purgee, en plus du fichier JSON existant --
les deux coexistent, chacun pour son usage (temps reel vs analyse longue).

INSERT OR REPLACE : idempotent, peut tourner a chaque publication.

Usage : python3 collecte/charger_liquidite_quotidienne.py [chemin_db]
"""
import csv
import sqlite3
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
CSV_SOURCE = str(_BASE / "liquidite_quotidienne_historique.csv")
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
                "INSERT OR REPLACE INTO liquidite_quotidienne "
                "(ticker, date_bulletin, volume_echange, valeur_echangee) "
                "VALUES (?,?,?,?)",
                (r["ticker"], r["date_bulletin"],
                 float(r["volume_echange"]) if r.get("volume_echange") else None,
                 float(r["valeur_echangee"]) if r.get("valeur_echangee") else None))
            n += 1
            tickers.add(r["ticker"])
            dates.add(r["date_bulletin"])
    conn.commit()
    print(f"{n} lignes inserees/mises a jour dans liquidite_quotidienne "
          f"({len(tickers)} tickers, {len(dates)} jours, "
          f"{min(dates) if dates else '?'} -> {max(dates) if dates else '?'}).")
    conn.close()


if __name__ == "__main__":
    main()
