#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/fusionner_fondamentaux.py — (27/07/2026, reecrit le 27/09/2026).

Fusionne collecte/fondamentaux_extraits.csv (lignes auto-extraites, Piste A)
dans donnees/base/etats_financiers.csv.

REECRITURE DU 27/09/2026. Jusqu'ici, ce script inserait du TEXTE PYTHON dans
moteur/peupler.py : il cherchait la chaine "ETATS = [", localisait le "\\n]"
suivant, et y injectait des tuples formates a la main. Apres la sortie des
donnees vers donnees/base/, cette chaine n'existe plus et le script levait
"ValueError: substring not found" -- en PREMIERE etape du workflow P4, qui
s'execute sous bash -e : le workflow entier serait tombe. Il ecrit desormais
des lignes de CSV, ce qui supprime la chirurgie sur le code source.

Regle absolue, inchangee : n'AJOUTE que des couples (ticker, exercice)
absents du fichier. Ne modifie, ne supprime, ne recalcule JAMAIS une ligne
deja presente -- meme si le meme couple existe en PROBABLE dans le CSV
source, une entree manuelle existante (meme moins bonne) reste prioritaire,
parce qu'elle a ete relue par un humain. Champs absents de l'extraction
automatique (dettes financieres, payout, solvabilite bancaire) : vides,
jamais devines.

Usage : python3 moteur/fusionner_fondamentaux.py
"""
import csv
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "donnees" / "base" / "etats_financiers.csv"
SOURCE = RACINE / "collecte" / "fondamentaux_extraits.csv"

# Garde-fou (28/07/2026, suite a l'incident BOABF/2026 -- document mal
# identifie, ticker et exercice tous deux faux, jamais filtre avant d'entrer
# dans la base malgre une valeur x1000 au-dela du plausible). Meme plafond que
# le golden test "plafond de plausibilite" (seuils.yaml), applique ICI, a la
# fusion, pas seulement a la verification a posteriori.
PLAFOND_RN_M_FCFA = 1_000_000

COLONNES = [
    "ticker", "exercice", "resultat_net", "resultat_net_n1", "total_actif",
    "total_passif", "capitaux_propres", "dettes_financieres", "payout_ratio",
    "solvabilite_bancaire", "source_type", "statut_donnee", "date_publication",
    "note"]


def date_pub_depuis_nom_fichier(url):
    """Le nom des rapports BRVM commence par la date de depot (AAAAMMJJ) --
    c'est la meilleure approximation disponible de la date de publication,
    faute de l'avoir extraite explicitement du texte du PDF."""
    m = re.search(r"/(\d{8})[_-]", url or "")
    if not m:
        return ""
    s = m.group(1)
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:])


def to_num(s):
    return float(s) if s not in (None, "") else None


def _texte(x):
    return "" if x is None else repr(x) if isinstance(x, float) else str(x)


def main():
    if not CIBLE.exists():
        raise SystemExit("Fichier de reference absent : %s" % CIBLE)
    with CIBLE.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        if lecteur.fieldnames != COLONNES:
            raise SystemExit(
                "En-tete inattendu dans %s\n  attendu : %s\n  trouve  : %s"
                % (CIBLE.name, ", ".join(COLONNES), ", ".join(lecteur.fieldnames or [])))
        existants = set()
        for ligne in lecteur:
            try:
                existants.add((ligne["ticker"], int(ligne["exercice"])))
            except (TypeError, ValueError):
                continue

    ajouts = []
    with SOURCE.open(newline="", encoding="utf-8") as f:
        lignes_source = list(csv.DictReader(f))
    for row in lignes_source:
        if not row.get("exercice"):
            continue  # rien d'exploitable comme cle sans exercice
        cle = (row["ticker"], int(row["exercice"]))
        if cle in existants:
            continue  # ne remplace jamais une entree deja presente
        rn = to_num(row["resultat_net"])
        rn1 = to_num(row["resultat_net_n1"])
        if (rn is not None and abs(rn) > PLAFOND_RN_M_FCFA) or \
           (rn1 is not None and abs(rn1) > PLAFOND_RN_M_FCFA):
            print("[ecarte] %s/%s : resultat net (%s) ou N-1 (%s) au-dela du plafond "
                  "de plausibilite (%d M FCFA) -- jamais fusionne, a verifier "
                  "manuellement (source : %s)"
                  % (row["ticker"], row["exercice"], rn, rn1, PLAFOND_RN_M_FCFA,
                     row.get("source_url", "")))
            existants.add(cle)  # ne plus jamais retenter cette ligne precise
            continue
        note = ("Fusion auto %s (Piste A, strategie=%s) -- %s"
                % (__import__("datetime").date.today().isoformat(),
                   row.get("strategie") or "?", row.get("note") or "")).strip()
        ajouts.append([
            row["ticker"], row["exercice"], _texte(rn), _texte(rn1),
            _texte(to_num(row["total_actif"])), _texte(to_num(row["total_passif"])),
            _texte(to_num(row["capitaux_propres"])), "", "", "",
            row["source_type"], row["statut_donnee"],
            date_pub_depuis_nom_fichier(row.get("source_url")), note])
        existants.add(cle)  # evite un doublon si le CSV source contient 2 fois le couple

    if not ajouts:
        print("Rien a fusionner : tous les couples (ticker, exercice) existent deja.")
        return

    with CIBLE.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(ajouts)

    print("%d nouvelle(s) ligne(s) ajoutee(s) a %s (sur %d lignes source, le reste "
          "existait deja). Dettes financieres, payout et solvabilite bancaire sont "
          "laisses VIDES : absents de l'extraction automatique, jamais devines."
          % (len(ajouts), CIBLE.name, len(lignes_source)))


if __name__ == "__main__":
    main()
