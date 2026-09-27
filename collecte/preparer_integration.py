#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/preparer_integration.py — Chantier "clore les 159 propositions"
(17/07/2026).

NE MODIFIE JAMAIS peupler.py directement. Produit un fichier texte listant
les nouvelles lignes ETATS proposees, prêtes a etre relues puis collees a
la main dans moteur/peupler.py -- exactement la meme discipline que toutes
les extractions precedentes de ce projet (jamais d'insertion automatique
sans verification humaine).

Regles d'exclusion, strictes :
  - Toute proposition avec une alerte de plausibilite active -> exclue
  - Tout (ticker, exercice) deja present dans ETATS -> exclu (jamais
    d'ecrasement silencieux d'une donnee existante, VALIDE ou PROBABLE)
  - Toute proposition sans resultat_net exploitable -> exclue
  - Statut TOUJOURS "PROBABLE" (jamais VALIDE sans 2e source independante,
    doctrine du projet deja actee et testee : moteur/tester.py verifie
    justement qu'aucune ligne OCR seule n'est jamais VALIDE)

Usage : python3 collecte/preparer_integration.py
"""
import csv
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PROPOSITIONS = RACINE / "collecte" / "propositions_extraction"
PEUPLER = RACINE / "moteur" / "peupler.py"  # conserve : cite dans les messages
ETATS_CSV = RACINE / "donnees" / "base" / "etats_financiers.csv"
SORTIE = RACINE / "collecte" / "candidats_integration.txt"


def charger_exercices_existants():
    """(ticker, exercice) deja presents en base -- jamais ecrases.

    27/09/2026 : lu depuis donnees/base/etats_financiers.csv, ou les donnees
    ont ete sorties de peupler.py."""
    if not ETATS_CSV.exists():
        raise SystemExit("Referentiel des etats financiers introuvable : %s" % ETATS_CSV)
    with ETATS_CSV.open(encoding="utf-8", newline="") as f:
        out = set()
        for r in csv.DictReader(f):
            try:
                out.add((r["ticker"], int(r["exercice"])))
            except (TypeError, ValueError, KeyError):
                continue
        return out


def date_depuis_nom_fichier(nom):
    """Le nom de fichier BRVM commence par la date de publication reelle
    (AAAAMMJJ) -- plus fiable que la date d'extraction de ce script."""
    m = re.match(r"^[0-9a-f]{8}_(\d{8})_", nom)
    if not m:
        return None
    d = m.group(1)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def main():
    existants = charger_exercices_existants()
    fichiers = sorted(PROPOSITIONS.glob("*.json"))
    print(f"{len(fichiers)} proposition(s) trouvee(s), {len(existants)} "
          f"exercice(s) deja presents dans peupler.py")

    candidats = []
    exclus_alerte, exclus_existant, exclus_incomplet = 0, 0, 0

    for f in fichiers:
        d = json.loads(f.read_text(encoding="utf-8"))
        ticker = d["ticker"]
        exercice = d.get("exercice_courant")
        champs = d.get("champs", {})
        rn = champs.get("resultat_net", {})

        if d.get("alertes_plausibilite"):
            exclus_alerte += 1
            continue
        if exercice is None or (ticker, exercice) in existants:
            exclus_existant += 1
            continue
        if rn.get("valeur_courante_M_FCFA") is None:
            exclus_incomplet += 1
            continue

        def v(champ):
            return champs.get(champ, {}).get("valeur_courante_M_FCFA")

        source_type = "OCR" if "ocr" in d.get("methode_pages", []) else "NATIF"
        date_pub = date_depuis_nom_fichier(d["fichier_source"])

        ligne = (
            f'    ("{ticker}", {exercice}, {v("resultat_net")}, '
            f'{rn.get("valeur_precedente_M_FCFA")}, {v("total_actif")}, '
            f'{v("total_passif")}, {v("capitaux_propres")}, '
            f'{v("dettes_financieres")}, {v("payout_ratio")}, None, '
            f'"{source_type}", "PROBABLE", {repr(date_pub)}),'
            f'  # {d["fichier_source"]}'
        )
        candidats.append((ticker, exercice, ligne))
        existants.add((ticker, exercice))  # evite les doublons entre propositions du meme lot

    candidats.sort()
    with open(SORTIE, "w", encoding="utf-8") as out:
        out.write(f"# {len(candidats)} candidats a l'integration -- a RELIRE avant de coller\n")
        out.write("# dans moteur/peupler.py (liste ETATS). Statut PROBABLE systematique.\n\n")
        for _, _, ligne in candidats:
            out.write(ligne + "\n")

    print(f"\n{len(candidats)} candidats retenus, ecrits dans {SORTIE}")
    print(f"Exclus : {exclus_alerte} (alerte de plausibilite), "
          f"{exclus_existant} (deja present), {exclus_incomplet} (donnee incomplete)")


if __name__ == "__main__":
    main()
