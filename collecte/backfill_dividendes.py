#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/backfill_dividendes.py — (27/07/2026).

dividendes_boc.csv n'est qu'une PHOTO (dernier dividende connu par titre a
une date donnee). Chaque BOC affiche pourtant deja le dividende declare a
CE moment-la (colonnes deja extraites par extracteur_boc.py). En relisant
tous les BOC deja archives (673, meme source que la Piste C liquidite,
AUCUNE requete brvm.org) et en detectant les changements de valeur
declaree au fil du temps, on reconstruit une vraie serie historique.

Principe : pour un ticker donne, tant que (montant, date_paiement) reste
identique d'un BOC au suivant, c'est le MEME dividende deja vu -> pas une
nouvelle ligne. Des qu'il change, c'est un nouveau dividende declare ->
une ligne. Resultat : une ligne par evenement de dividende reellement
observe, pas une ligne par jour de bourse.

Limite assumee : la reconstruction ne "voit" que les dividendes deja
declares PENDANT la fenetre couverte par nos BOC archives (2021-07 ->
aujourd'hui a ce jour) -- les dividendes plus anciens, jamais affiches
dans un BOC qu'on possede, restent invisibles par cette methode.

Sortie : collecte/dividendes_historique.csv (append-only, resumable).
Usage : python3 collecte/backfill_dividendes.py
"""
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
SORTIE = "collecte/dividendes_historique.csv"
TRAITES = "collecte/dividendes_traites.json"
REPO = "armelrosario-sys/brvm-data-pipeline"
COLONNES = ["ticker", "montant", "date_paiement", "premiere_observation", "derniere_observation"]


def charger_json(chemin, defaut):
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return defaut


def sauver_json(chemin, data):
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


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
    lignes_boc.sort(key=lambda r: r["nom_fichier"])  # ordre chronologique approx (date dans le nom)

    # observations brutes : ticker -> liste de (date, montant, date_paiement)
    observations = {}
    if os.path.exists("collecte/_dividendes_observations.json"):
        observations = charger_json("collecte/_dividendes_observations.json", {})

    echecs, traites_ce_run = 0, 0
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
        m = re.search(r"(\d{8})", row["nom_fichier"])
        date_iso = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None
        _, lignes = extraire_boc(chemin_local)
        if lignes and date_iso:
            for l in lignes:
                montant = l.get("dividende_montant")
                if montant is None:
                    continue
                date_paiement = l.get("dividende_date")
                # Garde-fou (28/07/2026) : force des types simples et hashables.
                # Si un champ est anormal (liste, dict -- cause jamais identifiee
                # avec certitude d'un crash "unhashable type: list"), on ignore
                # cette seule observation et on le signale, plutot que de
                # planter tout le run.
                try:
                    montant = float(montant)
                    date_paiement = str(date_paiement) if date_paiement is not None else None
                    hash((date_iso, montant, date_paiement))
                except (TypeError, ValueError) as e:
                    print(f"[avertissement] observation ignoree (type anormal) : "
                          f"{l.get('ticker')} {date_iso} montant={montant!r} "
                          f"date_paiement={date_paiement!r} -- {e}", file=sys.stderr)
                    continue
                observations.setdefault(l["ticker"], []).append(
                    (date_iso, montant, date_paiement))

        traites.add(sha)
        traites_ce_run += 1
        sauver_json(TRAITES, sorted(traites))
        sauver_json("collecte/_dividendes_observations.json", observations)
        try:
            os.remove(chemin_local)
        except OSError:
            pass

        checkpoint.sauvegarder(f"Backfill dividendes : {traites_ce_run} BOC traites ce run (auto)",
                                intervalle=600)

    # ---- derivation des evenements distincts a partir des observations ----
    evenements = []
    for ticker, obs in observations.items():
        obs_propres = []
        for o in obs:
            try:
                t = tuple(o)
                hash(t)
                obs_propres.append(t)
            except TypeError:
                print(f"[avertissement] observation existante ignoree (non hashable) : "
                      f"{ticker} {o!r}", file=sys.stderr)
        obs_triees = sorted(set(obs_propres), key=lambda o: o[0])  # chronologique, dedoublonne
        dernier = None
        for date_obs, montant, date_paiement in obs_triees:
            cle = (montant, date_paiement)
            if cle != dernier:
                evenements.append({
                    "ticker": ticker, "montant": montant, "date_paiement": date_paiement,
                    "premiere_observation": date_obs, "derniere_observation": date_obs,
                })
                dernier = cle
            else:
                evenements[-1]["derniere_observation"] = date_obs

    os.makedirs("collecte", exist_ok=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writeheader()
        w.writerows(sorted(evenements, key=lambda e: (e["ticker"], e["premiere_observation"])))

    checkpoint.sauvegarder(f"Backfill dividendes : run termine, {traites_ce_run} BOC traites, "
                            f"{len(evenements)} evenement(s) derive(s) (auto)", force=True)
    print(f"{len(evenements)} evenement(s) de dividende distinct(s) sur {len(observations)} titres, "
          f"{echecs} echec(s) de telechargement, {traites_ce_run} BOC traites ce run.")


if __name__ == "__main__":
    main()
