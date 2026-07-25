#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/backfill_boc_quotidien.py — Boucle P8 (25/07/2026), Piste B.

Objectif : elargir cours_quotidien_boc au-dela des seuls BOC de fin de mois
deja archives (collecteur.py existant, volontairement mensuel), en visant
TOUS les jours de bourse d'une fenetre RECENTE et bornee -- pas l'integralite
2018-2026, qui demanderait des dizaines de milliers de requetes a 10s
d'intervalle (Crawl-delay du robots.txt, deja respecte par collecteur.py et
repris ici a l'identique -- ce script ne le contourne pas).

Fenetre par defaut : les FENETRE_MOIS derniers mois glisses, du plus recent
au plus ancien (comme collecteur.py) -- c'est la periode la plus utile pour
les tests statistiques (mediane de liquidite, puissance de detection).

Reprise automatique via collecte/etat_backfill_quotidien.json : chaque jour
deja tente (trouve ou confirme absent) est memorise, un nouveau run reprend
sans retenter ce qui est deja regle.

Usage : python3 collecte/backfill_boc_quotidien.py [--fenetre-mois N] [--budget N]
"""
import argparse
import csv
import json
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collecteur import get, charger_manifeste, ajouter_manifeste, BASE  # reprend le meme throttling
from extracteur_boc import extraire_boc

ETAT = "collecte/etat_backfill_quotidien.json"
CSV_QUOTIDIEN = "collecte/cours_quotidien_boc.csv"
COLONNES_CSV = ["ticker", "date_bulletin", "cours", "per", "rendement"]
FENETRE_MOIS_DEFAUT = 24
BUDGET_DEFAUT = 200  # sous les 220 de collecteur.py : partage prudent du meme site


def jours_ouvres_du_mois(y, m):
    d = date(y, m, 1)
    jours = []
    while d.month == m:
        if d.weekday() < 5 and d <= date.today():
            jours.append(d)
        d += timedelta(days=1)
    return jours


def mois_fenetre(n_mois):
    auj = date.today()
    y, m = auj.year, auj.month
    liste = []
    for _ in range(n_mois):
        liste.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return liste  # du plus recent au plus ancien


def charger_etat():
    if os.path.exists(ETAT):
        with open(ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {"jours_tentes": [], "jours_trouves": [], "jours_absents": []}


def sauver_etat(etat):
    os.makedirs("collecte", exist_ok=True)
    with open(ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)


def dates_deja_en_base():
    dates = set()
    if os.path.exists(CSV_QUOTIDIEN):
        with open(CSV_QUOTIDIEN, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dates.add(row["date_bulletin"])
    return dates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fenetre-mois", type=int, default=FENETRE_MOIS_DEFAUT)
    ap.add_argument("--budget", type=int, default=BUDGET_DEFAUT)
    args = ap.parse_args()

    etat = charger_etat()
    deja_tentes = set(etat["jours_tentes"])
    manifeste = charger_manifeste()
    deja_en_base = dates_deja_en_base()

    nouveaux_manifeste, nouvelles_lignes_csv = [], []
    requetes = 0

    for y, m in mois_fenetre(args.fenetre_mois):
        for d in jours_ouvres_du_mois(y, m):
            if requetes >= args.budget:
                break
            iso = d.isoformat()
            if iso in deja_tentes or iso in deja_en_base:
                continue
            trouve = False
            for suffixe in ("_2", "_1", ""):
                if requetes >= args.budget:
                    break
                url = f"{BASE}/sites/default/files/boc_{d:%Y%m%d}{suffixe}.pdf"
                if url in manifeste:
                    # LIMITE CONNUE (25/07/2026, non corrigee) : ce PDF a deja
                    # ete archive (typiquement un BOC de fin de mois deja
                    # collecte par collecteur.py) mais son contenu n'est pas
                    # retelecharge ici pour extraction quotidienne -> cette
                    # date restera absente de cours_quotidien_boc.csv meme si
                    # le PDF existe deja en Release. A traiter dans un futur
                    # passage (meme logique de lecture de Release qu'en Piste A).
                    trouve = True
                    break
                contenu = get(url, binaire=True)
                requetes += 1
                if contenu and contenu.startswith(b"%PDF"):
                    import hashlib
                    sha = hashlib.sha256(contenu).hexdigest()
                    tag = f"boc-{y}"
                    os.makedirs(f"data/{tag}", exist_ok=True)
                    chemin = f"data/{tag}/boc_{d:%Y%m%d}{suffixe}.pdf"
                    with open(chemin, "wb") as f:
                        f.write(contenu)
                    with open("a_uploader.txt", "a", encoding="utf-8") as f:
                        f.write(f"{tag}\t{chemin}\n")
                    nouveaux_manifeste.append({
                        "sha256": sha, "type": "boc", "periode": f"{y}-{m:02d}",
                        "url": url, "nom_fichier": os.path.basename(chemin),
                        "taille_octets": len(contenu),
                        "date_collecte_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "release_tag": tag,
                    })
                    date_bulletin, lignes = extraire_boc(chemin)
                    if lignes:
                        for ligne in lignes:
                            nouvelles_lignes_csv.append({
                                "ticker": ligne["ticker"],
                                "date_bulletin": iso,
                                "cours": ligne.get("cours", ""),
                                "per": ligne.get("per", ""),
                                "rendement": ligne.get("rendement", ""),
                            })
                    trouve = True
                    break
            etat["jours_tentes"].append(iso)
            (etat["jours_trouves"] if trouve else etat["jours_absents"]).append(iso)
        if requetes >= args.budget:
            break

    if nouveaux_manifeste:
        ajouter_manifeste(nouveaux_manifeste)
    if nouvelles_lignes_csv:
        existe = os.path.exists(CSV_QUOTIDIEN)
        os.makedirs("collecte", exist_ok=True)
        with open(CSV_QUOTIDIEN, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLONNES_CSV)
            if not existe:
                w.writeheader()
            w.writerows(nouvelles_lignes_csv)
    sauver_etat(etat)
    print(f"Run termine : {len(nouveaux_manifeste)} nouveau(x) BOC, "
          f"{len(nouvelles_lignes_csv)} ligne(s) de cours ajoutees, "
          f"{requetes} requetes ({args.budget} autorisees). "
          f"Lancer collecte/verifier_continuite.py pour la verification de "
          f"continuite (recalculee separement, en ordre chronologique correct).")


if __name__ == "__main__":
    main()
