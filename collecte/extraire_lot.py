#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/extraire_lot.py — Chantier "brancher l'extracteur sur le pipeline"
(15/07/2026).

Traite par LOTS BUDGETES (meme discipline que reparer_releases.py) les
documents "etats_financiers" deja identifies dans MANIFESTE.csv : telecharge
chaque PDF depuis sa release GitHub, lance extracteur_etats.py (OCR
positionnel si necessaire), et ecrit la proposition JSON dans
collecte/propositions_extraction/ POUR RELECTURE HUMAINE.

NE MODIFIE JAMAIS peupler.py NI la base directement -- l'OCR peut se
tromper, l'integrite du projet exige une verification avant toute
insertion (meme doctrine que extracteur_etats.py lui-meme).

Etat de progression suivi dans collecte/extractions_traitees.json (SHA256
deja traites), pour reprendre exactement la ou le lot precedent s'est
arrete sur plusieurs executions successives -- meme logique que
a_reteleverser.json.

Usage : python3 extraire_lot.py
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "moteur"))
from extracteur_etats import extraire_pdf
from calendrier import construire_mapping, _categoriser, PATTERN_NOM

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE = RACINE / "MANIFESTE.csv"
TRAITES_PATH = RACINE / "collecte" / "extractions_traitees.json"
SORTIE_DIR = RACINE / "collecte" / "propositions_extraction"
BUDGET_DOCUMENTS = 15  # OCR lent (plusieurs pages/document) -- marge de securite vs timeout du run
DELAI_ENTRE_TELECHARGEMENTS = 2.0
REPO = "armelrosario-sys/brvm-data-pipeline"


def charger_referentiels():
    """ticker -> referentiel_comptable, lu directement dans SOCIETES
    (peupler.py) -- evite de dependre d'une base SQLite deja construite."""
    src = (RACINE / "moteur" / "peupler.py").read_text(encoding="utf-8")
    m = re.search(r"SOCIETES = \[(.*?)\n\]", src, re.S)
    lignes = re.findall(r'\("([A-Z_]+)",\s*"[^"]*",\s*"[^"]*",\s*"([A-Z_]+)"', m.group(1))
    return dict(lignes)


def documents_a_traiter(mapping, traites_set):
    slug_vers_ticker = {v: k for k, v in mapping.items()}
    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    a_traiter = []
    total_rapports = 0
    for r in rows:
        if r["type"] != "rapport":
            continue
        total_rapports += 1
        mm = PATTERN_NOM.match(r["nom_fichier"])
        if not mm:
            continue
        _, libelle, slug = mm.groups()
        if _categoriser(libelle) != "etats_financiers":
            continue
        ticker = slug_vers_ticker.get(slug)
        if not ticker or r["sha256"] in traites_set:
            continue
        a_traiter.append((r, ticker))
    return a_traiter, total_rapports


def main():
    mapping, _ = construire_mapping(RACINE / "moteur" / "peupler.py")
    referentiels = charger_referentiels()

    traites = json.loads(TRAITES_PATH.read_text(encoding="utf-8")) if TRAITES_PATH.exists() else []
    traites_set = set(traites)
    SORTIE_DIR.mkdir(exist_ok=True)

    a_traiter, total_rapports = documents_a_traiter(mapping, traites_set)
    print(f"{len(a_traiter)} document(s) 'etats_financiers' restant(s) a traiter "
          f"(sur {total_rapports} rapports au total, {len(traites_set)} deja traites).")

    n_ok, n_echec = 0, 0
    for r, ticker in a_traiter[:BUDGET_DOCUMENTS]:
        referentiel = "bancaire_umoa" if referentiels.get(ticker) == "BANCAIRE_UMOA" else "syscohada"
        url = f"https://github.com/{REPO}/releases/download/{r['release_tag']}/{r['nom_fichier']}"
        try:
            resp = requests.get(url, timeout=60,
                                 headers={"User-Agent": "brvm-data-pipeline-extraction/1.0"})
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(resp.content)
                chemin_tmp = f.name
            m_annee = re.search(r"exercice[_\s]+(\d{4})", r["nom_fichier"], re.IGNORECASE)
            annee_connue = int(m_annee.group(1)) if m_annee else None
            proposition = extraire_pdf(chemin_tmp, ticker, referentiel, annee_connue=annee_connue)
            proposition["fichier_source"] = r["nom_fichier"]
            proposition["sha256"] = r["sha256"]
            nom_sortie = f"{ticker}_{r['sha256'][:10]}.json"
            (SORTIE_DIR / nom_sortie).write_text(
                json.dumps(proposition, ensure_ascii=False, indent=2), encoding="utf-8")
            n_champs = len(proposition.get("champs", {}))
            print(f"  OK    {ticker:8} <- {r['nom_fichier']} ({n_champs} champ(s) extrait(s))")
            n_ok += 1
        except Exception as e:
            print(f"  ECHEC {ticker:8} <- {r['nom_fichier']} : {type(e).__name__}: {e}")
            n_echec += 1
        traites_set.add(r["sha256"])
        time.sleep(DELAI_ENTRE_TELECHARGEMENTS)

    TRAITES_PATH.write_text(json.dumps(sorted(traites_set), ensure_ascii=False, indent=1), encoding="utf-8")
    restant = max(0, len(a_traiter) - BUDGET_DOCUMENTS)
    print(f"\nTermine : {n_ok} extrait(s), {n_echec} echec(s), {restant} document(s) "
          f"restant(s) pour un prochain lot (relancer le workflow pour continuer).")


if __name__ == "__main__":
    main()
