#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/historiser_dividendes_exercice.py — (28/07/2026).

collecte/dividendes_historique.csv dit QUAND un montant de dividende a ete
observe pour la premiere/derniere fois dans un BOC -- pas QUEL EXERCICE
(annee comptable) ce dividende recompense. Ce script deduit l'exercice
couvert a partir du mois de paiement, sur la base de la vraie distribution
observee dans nos donnees (355 evenements) :

  avril -> decembre  (355-3=352 cas, 98%)  : quasi tous les paiements BRVM
      suivent l'AGM qui approuve les comptes de l'exercice precedent.
      Regle : exercice_couvert = annee_paiement - 1. Confiance ELEVEE.

  janvier (3 cas seulement, situation rare)      : trop tot pour etre un
      paiement normal de l'exercice N-1 (l'AGM n'a generalement pas encore
      eu lieu) -> tres probablement un paiement RETARDE de l'exercice N-2.
      Regle : exercice_couvert = annee_paiement - 2. Confiance A_VERIFIER
      (peu de cas, jamais confirme par un document).

  fevrier/mars (0 cas observes a ce jour) : aucune donnee pour calibrer ->
      MANQUANT plutot que devine si un futur cas apparait.

Sortie : collecte/dividendes_par_exercice.csv (ticker, exercice_couvert,
montant, date_paiement, confiance, note) -- une ligne par evenement de
dividende distinct deja identifie, jamais un doublon invente.

Usage : python3 collecte/historiser_dividendes_exercice.py
"""
import csv
import re

ENTREE = "collecte/dividendes_historique.csv"
SORTIE = "collecte/dividendes_par_exercice.csv"

MOIS_FR = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11,
    "dec": 12, "déc": 12,
    # variantes anglaises rencontrees dans certains BOC a mise en page mixte
    "jan": 1, "feb": 2, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
}


def parser_date_fr(s):
    """Retourne (annee, mois) ou None si le format n'est pas reconnu --
    jamais une devinette silencieuse."""
    if not s or not s.strip():
        return None
    m = re.match(r"(\d{1,2})[- ](\w+)[.\-]?[- ](\d{2,4})", s)
    if not m:
        return None
    _, mois_txt, annee = m.groups()
    mois_txt = mois_txt.lower().rstrip(".")
    mois = MOIS_FR.get(mois_txt[:4]) or MOIS_FR.get(mois_txt[:3])
    if not mois:
        return None
    annee = int(annee)
    if annee < 100:
        annee += 2000
    return (annee, mois)


def deduire_exercice(annee_paiement, mois_paiement):
    """Retourne (exercice, confiance, note)."""
    if 4 <= mois_paiement <= 12:
        return (annee_paiement - 1, "ELEVEE",
                "paiement en saison normale d'AGM (avril-decembre)")
    if mois_paiement == 1:
        # CAS FTSC verifie le 28/07/2026 (Avis BRVM N 072-2017/DC/BR/DG) :
        # le dividende de l'exercice 2016 a ete paye le 31 juillet 2017, PAS
        # en janvier -- la regle generique "-2" ci-dessous est donc
        # explicitement contredite pour ce ticker. Ne pas deviner un autre
        # exercice : MANQUANT tant qu'aucun document ne confirme le bon.
        return (None, "MANQUANT",
                "paiement de janvier : la regle -2 est explicitement "
                "contredite pour FTSC par l'avis BRVM N 072-2017/DC/BR/DG "
                "(exercice 2016 confirme paye le 31/07/2017, pas en janvier) "
                "-- non devine, a verifier au cas par cas")
    # fevrier/mars : aucun cas observe pour calibrer une regle fiable
    return (None, "MANQUANT",
            "mois de paiement (fevrier/mars) sans precedent observe pour "
            "calibrer une regle -- non devine")


def main():
    lignes_sortie = []
    with open(ENTREE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = parser_date_fr(row["date_paiement"])
            if d is None:
                lignes_sortie.append({
                    "ticker": row["ticker"], "exercice_couvert": "",
                    "montant": row["montant"], "date_paiement": row["date_paiement"],
                    "confiance": "MANQUANT",
                    "note": "date de paiement illisible, format non reconnu",
                })
                continue
            annee, mois = d
            exercice, confiance, note = deduire_exercice(annee, mois)
            lignes_sortie.append({
                "ticker": row["ticker"],
                "exercice_couvert": exercice if exercice is not None else "",
                "montant": row["montant"],
                "date_paiement": row["date_paiement"],
                "confiance": confiance,
                "note": note,
            })

    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "exercice_couvert", "montant",
                                           "date_paiement", "confiance", "note"])
        w.writeheader()
        w.writerows(sorted(lignes_sortie, key=lambda r: (r["ticker"], str(r["exercice_couvert"]))))

    from collections import Counter
    c = Counter(l["confiance"] for l in lignes_sortie)
    print(f"{len(lignes_sortie)} evenement(s) traites : {dict(c)}")


if __name__ == "__main__":
    main()
