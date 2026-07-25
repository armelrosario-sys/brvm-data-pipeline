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
import argparse
import csv
import json
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extracteur_boc import extraire_boc
import checkpoint

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


def sauver_json(chemin, data):
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def ecrire_lignes_csv(chemin, fieldnames, lignes):
    if not lignes:
        return
    existe = os.path.exists(chemin)
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not existe:
            w.writeheader()
        w.writerows(lignes)
        f.flush()
        os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint-secondes", type=int, default=600)
    args = ap.parse_args()

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

    n_resultats, echecs, traites_ce_run = 0, 0, 0
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
        m = re.search(r"(\d{8})", row["nom_fichier"])
        date_iso = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None
        _, lignes = extraire_boc(chemin_local)
        if lignes and date_iso:
            nouvelles_lignes = [{
                "ticker": l["ticker"], "date_bulletin": date_iso,
                "volume_echange": l["volume_echange"],
                "valeur_echangee": l.get("valeur_echangee", ""),
            } for l in lignes if l.get("volume_echange") is not None]
            ecrire_lignes_csv(SORTIE, COLONNES, nouvelles_lignes)
            n_resultats += len(nouvelles_lignes)

        traites.add(sha)
        traites_ce_run += 1
        sauver_json(TRAITES, sorted(traites))  # sur disque immediatement
        try:
            os.remove(chemin_local)
        except OSError:
            pass

        checkpoint.sauvegarder(f"Backfill liquidite : {traites_ce_run} BOC traites ce run (auto)",
                                intervalle=args.checkpoint_secondes)

    checkpoint.sauvegarder(f"Backfill liquidite : run termine, {traites_ce_run} BOC traites (auto)",
                            force=True)
    print(f"{n_resultats} ligne(s) de liquidite ajoutees, {echecs} echec(s) de telechargement, "
          f"{len(traites)} BOC traites au total.")


if __name__ == "__main__":
    main()
