#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/backfill_liquidite.py — (25/07/2026).

Le volume et la valeur echangee du jour sont dans le BOC depuis toujours
(colonnes "Seance de cotation : Volume Valeur"), mais n'etaient jamais
extraits. Ce script relit tous les BOC deja archives en Release (aucune
requete vers brvm.org) et produit un historique complet, ticker par ticker,
jour par jour -- au lieu des 60 jours glissants de historique_liquidite.json
(fichier operationnel du scoring, non touche ici).

Sortie : collecte/liquidite_quotidienne_historique.csv (append-only,
resumable via collecte/liquidite_traites.json).

Usage : python3 collecte/backfill_liquidite.py
"""
import csv
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extracteur_boc import extraire_boc

MANIFESTE = "MANIFESTE.csv"
SORTIE = "collecte/liquidite_quotidienne_historique.csv"
TRAITES = "collecte/liquidite_traites.json"
REPO = "armelrosario-sys/brvm-data-pipeline"
COLONNES = ["ticker", "date_bulletin", "volume_echange", "valeur_echangee"]


def charger_json(chemin, defaut):
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return defaut


def main():
    traites = set(charger_json(TRAITES, []))
    session = requests.Session()
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)

    lignes_boc = []
    with open(MANIFESTE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] == "boc":
                lignes_boc.append(row)

    resultats, echecs = [], 0
    for row in lignes_boc:
        sha = row["sha256"]
        if sha in traites:
            continue
        rel = session.get(f"https://api.github.com/repos/{REPO}/releases/tags/{row['release_tag']}", timeout=30)
        if rel.status_code != 200:
            echecs += 1
            continue
        asset = next((a for a in rel.json().get("assets", []) if a["name"] == row["nom_fichier"]), None)
        if not asset:
            echecs += 1
            continue
        pdf = session.get(asset["url"], headers={**headers, "Accept": "application/octet-stream"}, timeout=60)
        if pdf.status_code != 200:
            echecs += 1
            continue
        chemin_local = f"/tmp/{sha[:16]}.pdf"
        with open(chemin_local, "wb") as f:
            f.write(pdf.content)
        # date reelle depuis le nom de fichier archive (contient boc_AAAAMMJJ)
        import re
        m = re.search(r"(\d{8})", row["nom_fichier"])
        date_iso = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None
        _, lignes = extraire_boc(chemin_local)
        if lignes and date_iso:
            for l in lignes:
                if l.get("volume_echange") is not None:
                    resultats.append({
                        "ticker": l["ticker"], "date_bulletin": date_iso,
                        "volume_echange": l["volume_echange"],
                        "valeur_echangee": l.get("valeur_echangee", ""),
                    })
        traites.add(sha)
        try:
            os.remove(chemin_local)
        except OSError:
            pass

    if resultats:
        existe = os.path.exists(SORTIE)
        os.makedirs("collecte", exist_ok=True)
        with open(SORTIE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLONNES)
            if not existe:
                w.writeheader()
            w.writerows(resultats)

    os.makedirs("collecte", exist_ok=True)
    with open(TRAITES, "w", encoding="utf-8") as f:
        json.dump(sorted(traites), f, ensure_ascii=False, indent=1)

    print(f"{len(resultats)} ligne(s) de liquidite ajoutees, {echecs} echec(s) de telechargement, "
          f"{len(traites)} BOC traites au total.")


if __name__ == "__main__":
    main()
