#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecteur de nouveaux documents (11/07/2026).

Compare MANIFESTE.csv (documents collectes automatiquement) a ce qui est deja
en base (etats_financiers) et signale les documents "etats_financiers" qui
n'ont PAS encore ete extraits — sans jamais extraire lui-meme.

Pourquoi ce script n'extrait rien : la session a montre a plusieurs reprises
(3 inversions de colonnes, unites ambigues, echecs OCR) qu'une extraction
automatique sans verification croisee produit des erreurs silencieuses.
Ce script accelere uniquement le DEMARRAGE d'une session de mise a jour —
il dit "voici ce qui est nouveau", jamais "voici les chiffres".

Usage : python3 detecter_nouveaux_documents.py
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "moteur"))
from scoring import DB

MANIFESTE_URL = "https://raw.githubusercontent.com/armelrosario-sys/brvm-data-pipeline/main/MANIFESTE.csv"

# Mots-cles de nom de societe par ticker, tels qu'etablis au fil du projet
# (meme mapping que celui utilise pour reconstruire source_url, etape B)
MOTS_CLES = {
    'SNTS': 'sonatel', 'STBC': 'sitab', 'NSBC': 'nsia_banque', 'SMBC': 'smb_ci',
    'SAFC': 'safca', 'ORGT': 'oragroup', 'BOABF': 'boa_bf', 'CBIBF': 'coris',
    'SICC': 'sicor', 'CABC': 'sicable', 'FTSC': 'filtisac', 'STAC': 'setao',
    'SDCC': 'sode', 'SIVC': 'erium', 'NTLC': 'nestle', 'PALC': 'palm',
    'SPHC': 'saph', 'SCRC': 'sucrivoire', 'SLBC': 'solibra', 'SOGC': 'sogb',
    'UNLC': 'unilever', 'TTLC': 'totalenergies_marketing_ci',
    'TTLS': 'totalenergies_marketing_sn', 'SHEC': 'vivo_energy', 'BICB': 'biic',
    'BICC': 'bici', 'ECOC': 'ecobank_ci', 'SGBC': 'societe_generale',
    'SIBC': 'sib_ci', 'ORAC': 'orange_ci', 'ONTBF': 'onatel', 'ABJC': 'servair',
    'BNBC': 'bernabe', 'CFAC': 'cfao', 'LNBB': 'loterie', 'NEIC': 'nei-ceda',
    'PRSC': 'tractafric', 'UNXC': 'uniwax', 'BOAB': 'boa_bn', 'BOAC': 'boa_ci',
    'BOAM': 'boa_ml', 'BOAN': 'boa_ng', 'BOAS': 'boa_sn', 'CIEC': 'cie_ci',
}


def exercices_deja_en_base():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT ticker, exercice FROM etats_financiers WHERE ticker NOT LIKE 'TEST_%'"
    ).fetchall()
    conn.close()
    connu = {}
    for t, e in rows:
        connu.setdefault(t, set()).add(e)
    return connu


def documents_disponibles():
    import urllib.request
    with urllib.request.urlopen(MANIFESTE_URL) as resp:
        contenu = resp.read().decode("utf-8")
    lignes = list(csv.DictReader(contenu.splitlines()))
    return [r for r in lignes if r["type"] == "rapport"]


def main():
    connu = exercices_deja_en_base()
    rapports = documents_disponibles()

    nouveaux = []
    for r in rapports:
        nom = r["nom_fichier"].lower()
        sans_hash = re.sub(r"^[0-9a-f]{8}_", "", nom)
        if "etats_financiers" not in sans_hash and "etats financiers" not in sans_hash:
            continue
        m_exercice = re.search(r"exercice[_ ](20\d\d)", sans_hash)
        if not m_exercice:
            continue
        exercice = int(m_exercice.group(1))

        for ticker, mot in MOTS_CLES.items():
            if mot in sans_hash:
                if exercice not in connu.get(ticker, set()):
                    nouveaux.append((ticker, exercice, r["nom_fichier"], r["release_tag"]))
                break

    nouveaux = sorted(set(nouveaux))
    print(f"Documents 'etats_financiers' scannes : {sum(1 for r in rapports if 'etats_financiers' in r['nom_fichier'].lower())}")
    print(f"Nouveaux (ticker+exercice absent de la base) : {len(nouveaux)}\n")
    if not nouveaux:
        print("Aucun nouveau document detecte — base a jour par rapport au manifeste.")
        return

    print(f"{'Titre':<8}{'Exercice':<10}{'Tag':<16}Fichier")
    for ticker, exercice, fichier, tag in nouveaux:
        print(f"{ticker:<8}{exercice:<10}{tag:<16}{fichier}")
    print("\nCes documents n'ont PAS ete extraits automatiquement — a traiter manuellement,")
    print("avec la meme discipline de verification croisee que le reste du projet.")


if __name__ == "__main__":
    main()
