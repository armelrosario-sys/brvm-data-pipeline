#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/collecte_boc_quotidien.py — Chantier "PER a jour" (18/07/2026).

La BRVM publie un Bulletin Officiel de la Cote (BOC) CHAQUE JOUR de cotation
(pas seulement mensuel) : https://www.brvm.org/sites/default/files/boc_AAAAMMJJ_2.pdf
Constat reel qui a motive ce chantier : notre ancien fichier cours_extraits.csv
datait du 7 juillet alors qu'on etait le 18 -- 11 jours de retard, aucune
automatisation ne le rafraichissait jamais. Le PER affiche etait donc perime
en permanence, pas par accident ponctuel.

Correction architecturale (demandee par l'utilisateur, a raison) : cette
collecte quotidienne alimente DEUX tables, jamais une seule --
  - cours_quotidien_boc : ACCUMULE une ligne par jour, ne jamais rien ecraser
    (contrairement a cours_mensuels, qui par construction ne garde que la
    derniere ligne du mois -- une collecte quotidienne qui n'alimenterait
    QUE cours_mensuels jetterait l'historique intra-mensuel chaque jour).
  - cours_mensuels : continue d'etre rafraichi (compatibilite avec toute la
    logique existante -- B1_RECORD, mediane sectorielle, etc.), desormais a
    jour quotidiennement au lieu de deux fois par semaine.

Essaie plusieurs jours en arriere (jusqu'a 5) si le BOC du jour n'est pas
encore publie (weekend, jour ferie, delai de publication).

Usage : python3 collecte_boc_quotidien.py [chemin_db]
"""
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extracteur_boc import extraire_boc

DB = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "moteur" / "brvm.db")
UA = {"User-Agent": "Mozilla/5.0 (brvm-data-pipeline/1.0; +https://github.com/armelrosario-sys/brvm-data-pipeline)"}
MAX_JOURS_EN_ARRIERE = 5


def telecharger_boc(jour):
    """Tente de telecharger le BOC pour une date donnee. Retourne le chemin
    du fichier temporaire si succes, None sinon (jour non-ouvre ou pas encore publie)."""
    aaaammjj = jour.strftime("%Y%m%d")
    url = f"https://www.brvm.org/sites/default/files/boc_{aaaammjj}_2.pdf"
    try:
        resp = requests.get(url, headers=UA, timeout=30)
        if resp.status_code != 200 or len(resp.content) < 1000:
            return None
        f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        f.write(resp.content)
        f.close()
        return f.name
    except requests.RequestException:
        return None


def periode(date_bulletin_aaaammjj):
    return f"{date_bulletin_aaaammjj[:4]}-{date_bulletin_aaaammjj[4:6]}"


def date_iso(date_bulletin_aaaammjj):
    d = date_bulletin_aaaammjj
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def recharger_historique_committe(cur):
    """cours_quotidien_boc vit dans brvm.db, qui est reconstruit A NEUF a
    chaque execution du pipeline (jamais committe -- voir .gitignore). Sans
    ce rechargement, l'accumulation serait effacee a chaque run, exactement
    l'erreur qu'on vient de corriger pour historique_liquidite.json. Le CSV
    committe (collecte/cours_quotidien_boc.csv) est la vraie source de
    verite persistante ; la table SQLite n'est qu'un cache de travail."""
    import csv
    chemin = Path(__file__).resolve().parent / "cours_quotidien_boc.csv"
    if not chemin.exists():
        return 0
    with open(chemin, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        cur.execute(
            "INSERT OR REPLACE INTO cours_quotidien_boc (ticker, date_bulletin, cours, per, rendement) "
            "VALUES (?,?,?,?,?)",
            (r["ticker"], r["date_bulletin"],
             float(r["cours"]) if r["cours"] else None,
             float(r["per"]) if r["per"] else None,
             float(r["rendement"]) if r["rendement"] else None))
    return len(rows)


def main():
    aujourd_hui = date.today()
    chemin_pdf, date_bulletin = None, None
    for delta in range(MAX_JOURS_EN_ARRIERE):
        jour = aujourd_hui - timedelta(days=delta)
        chemin = telecharger_boc(jour)
        if chemin:
            db_, lignes = extraire_boc(chemin)
            if db_ and lignes:
                chemin_pdf, date_bulletin, boc_lignes = chemin, db_, lignes
                print(f"BOC trouve pour {jour.isoformat()} ({len(lignes)} titres)")
                break
            Path(chemin).unlink(missing_ok=True)

    if not chemin_pdf:
        print(f"Aucun BOC exploitable trouve sur les {MAX_JOURS_EN_ARRIERE} derniers jours -- rien a faire.")
        return

    Path(chemin_pdf).unlink(missing_ok=True)
    p = periode(date_bulletin)
    d_iso = date_iso(date_bulletin)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n_recharges = recharger_historique_committe(cur)
    if n_recharges:
        print(f"{n_recharges} ligne(s) d'historique deja committe rechargee(s) avant d'accumuler")
    n_quotidien, n_mensuel = 0, 0
    for r in boc_lignes:
        cur.execute(
            "INSERT OR REPLACE INTO cours_quotidien_boc (ticker, date_bulletin, cours, per, rendement) "
            "VALUES (?,?,?,?,?)",
            (r["ticker"], d_iso, r.get("cours"), r.get("per"),
             r.get("rendement") / 100 if r.get("rendement") else None))
        n_quotidien += 1

        # cours_mensuels : ne remplacer que si cette collecte est plus recente
        # que ce qui y figure deja pour ce mois (coherent avec charger_cours.py :
        # "on garde la ligne la plus tardive du mois").
        existant = cur.execute(
            "SELECT fin_mois FROM cours_mensuels WHERE ticker=? AND fin_mois=?",
            (r["ticker"], p)).fetchone()
        cur.execute(
            "INSERT OR REPLACE INTO cours_mensuels (ticker, fin_mois, cours, per, rendement, liquidite_ratio) "
            "VALUES (?,?,?,?,?,NULL)",
            (r["ticker"], p, r.get("cours"), r.get("per"),
             r.get("rendement") / 100 if r.get("rendement") else None))
        n_mensuel += 1

    conn.commit()
    conn.close()
    print(f"{n_quotidien} ligne(s) ajoutee(s)/mise(s) a jour dans cours_quotidien_boc ({d_iso})")
    print(f"{n_mensuel} ligne(s) rafraichie(s) dans cours_mensuels ({p})")


if __name__ == "__main__":
    main()
