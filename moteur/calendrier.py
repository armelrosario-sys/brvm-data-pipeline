#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/calendrier.py — CHANTIER 2 (14/07/2026) : calendrier des publications.

Derive, quasi gratuitement, un calendrier des depots par titre et par
categorie de document a partir des DATES DEJA PRESENTES dans les noms de
fichiers du MANIFESTE (audit du 14/07/2026 : 866/924 rapports, soit 94%,
ont une date AAAAMMJJ et un nom d'entreprise extractibles du nom de fichier
sans aucune collecte supplementaire).

Ce module NE modifie PAS le signal D4 (retard de publication), qui reste
pour l'instant alimente manuellement via avis_reglementaires -- l'automatiser
completement est le prolongement naturel de ce chantier, delibrement laisse
pour une etape separee et testable independamment (discipline du projet :
un chantier a la fois).

Sortie : collecte/calendrier.json
  { ticker: { categorie: { dernier_depot: "AAAA-MM-JJ", mois_habituel: int,
                           nb_occurrences: int, historique: [dates] } } }

Correspondance ticker <-> slug de fichier : derivee DYNAMIQUEMENT depuis
SOCIETES (peupler.py) a chaque execution, jamais figee en dur -- si un
ticker est ajoute/renomme, la correspondance se recalcule automatiquement.
Un seul cas non deductible automatiquement (abreviation) : LNBB -> lnb_bn.
BBGCI : aucun document trouve dans le MANIFESTE sous quelque nom que ce
soit (meme situation que SDSC avant le 14/07/2026) -- signale, pas bloquant.
"""
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE = RACINE / "MANIFESTE.csv"
SORTIE = RACINE / "collecte" / "calendrier.json"

CORRECTIFS_MANUELS = {"LNBB": "lnb_bn"}  # abreviations non deductibles par slugification

PATTERN_NOM = re.compile(r"^[0-9a-f]{8}_(\d{8})_-_(.+?)_-_([a-z0-9_]+)\.pdf$", re.I)


def _slugify(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", txt.lower()).strip("_")


def _categoriser(libelle):
    """Categorie de document, dans un vocabulaire STABLE et VERSIONNABLE.
    'autre' capte tout ce qui ne correspond a aucun motif connu -- volontairement
    peu couvrant plutot que de deviner a tort (integrite > couverture)."""
    l = libelle.lower()
    if "etats_financiers" in l or "etat_financier" in l:
        return "etats_financiers"
    if "rapport_des_cac" in l or "attestation_des_commissaires" in l or "attestation_des_cac" in l:
        return "rapport_cac"
    if "1er_trimestre" in l or "premier_trimestre" in l or "1er_trim" in l:
        return "activite_T1"
    if "2eme_trimestre" in l or "2e_trimestre" in l:
        return "activite_T2"
    if "3eme_trimestre" in l or "3e_trimestre" in l or "3t" in l:
        return "activite_T3"
    if "1er_semestre" in l or "premier_semestre" in l:
        return "activite_S1"
    if "resolution" in l or "assemblee" in l or "_ago_" in l or l.startswith("ago"):
        return "resolutions_ago"
    return "autre"


def construire_mapping(peupler_path):
    """Derive ticker -> slug de fichier depuis SOCIETES (peupler.py) et les
    slugs reellement observes dans le MANIFESTE. Jamais fige en dur."""
    src = peupler_path.read_text()
    m = re.search(r"SOCIETES = \[(.*?)\n\]", src, re.S)
    lignes = re.findall(r'\("([A-Z_]+)",\s*"([^"]+)"', m.group(1))
    noms = {t: n for t, n in lignes if not t.startswith("TEST_")}

    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    slugs_fichiers = set()
    for r in rows:
        if r["type"] != "rapport":
            continue
        mm = PATTERN_NOM.match(r["nom_fichier"])
        if mm:
            slugs_fichiers.add(mm.group(3))

    mapping = dict(CORRECTIFS_MANUELS)
    non_couverts = []
    for t, n in noms.items():
        if t in mapping:
            continue
        s_nom = _slugify(n)
        candidats = [sf for sf in slugs_fichiers if s_nom in sf or sf in s_nom]
        if not candidats:
            premier_mot = s_nom.split("_")[0]
            candidats = [sf for sf in slugs_fichiers if sf.startswith(premier_mot + "_") or sf == premier_mot]
        if candidats:
            mapping[t] = sorted(candidats, key=len)[0]
        else:
            non_couverts.append(t)
    return mapping, non_couverts


def construire_calendrier(mapping):
    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    slug_vers_ticker = {v: k for k, v in mapping.items()}
    par_ticker = {}
    for r in rows:
        if r["type"] != "rapport":
            continue
        mm = PATTERN_NOM.match(r["nom_fichier"])
        if not mm:
            continue
        date_brute, libelle, slug = mm.groups()
        ticker = slug_vers_ticker.get(slug)
        if not ticker:
            continue
        date_iso = f"{date_brute[:4]}-{date_brute[4:6]}-{date_brute[6:]}"
        cat = _categoriser(libelle)
        par_ticker.setdefault(ticker, {}).setdefault(cat, []).append(date_iso)

    calendrier = {}
    for ticker, cats in par_ticker.items():
        calendrier[ticker] = {}
        for cat, dates in cats.items():
            dates_triees = sorted(dates)
            mois = Counter(int(d[5:7]) for d in dates_triees)
            mois_habituel = mois.most_common(1)[0][0] if mois else None
            calendrier[ticker][cat] = dict(
                dernier_depot=dates_triees[-1],
                mois_habituel=mois_habituel,
                nb_occurrences=len(dates_triees),
                historique=dates_triees,
            )
    return calendrier


def calculer():
    mapping, non_couverts = construire_mapping(RACINE / "moteur" / "peupler.py")
    calendrier = construire_calendrier(mapping)
    SORTIE.write_text(json.dumps(calendrier, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"calendrier.json : {len(calendrier)} tickers couverts "
          f"({len(mapping)} mappings, {len(non_couverts)} non couverts : {non_couverts})")
    return calendrier, non_couverts


if __name__ == "__main__":
    calculer()
