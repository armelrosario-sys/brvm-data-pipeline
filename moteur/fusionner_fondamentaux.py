#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/fusionner_fondamentaux.py — (27/07/2026).

Fusionne collecte/fondamentaux_extraits.csv (260 lignes auto-extraites,
Piste A) dans la table ETATS de moteur/peupler.py.

Regle absolue : n'AJOUTE que des couples (ticker, exercice) absents de
ETATS. Ne modifie, ne supprime, ne recalcule JAMAIS une ligne deja
presente -- meme si le meme couple existe en PROBABLE dans le CSV, une
entree manuelle existante (meme moins bonne) reste prioritaire, parce
qu'elle a ete relue par un humain. Champs absents de l'extraction
automatique (dettes financieres, payout, solvabilite bancaire) : None,
jamais devine.

Usage : python3 moteur/fusionner_fondamentaux.py
"""
import csv
import re

PEUPLER = "moteur/peupler.py"
SOURCE = "collecte/fondamentaux_extraits.csv"


def couples_existants(contenu):
    start = contenu.index("ETATS = [")
    end = contenu.index("\n]", start)
    bloc = contenu[start:end]
    paires = set()
    for m in re.finditer(r'\("([A-Z0-9_]+)",\s*(\d{4}),', bloc):
        paires.add((m.group(1), int(m.group(2))))
    return paires, end


def date_pub_depuis_nom_fichier(url):
    """Le nom des rapports BRVM commence par la date de depot (AAAAMMJJ) --
    c'est la meilleure approximation disponible de la date de publication,
    faute de l'avoir extraite explicitement du texte du PDF."""
    m = re.search(r"/(\d{8})[_-]", url)
    if not m:
        return None
    s = m.group(1)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def to_num(s):
    return float(s) if s not in (None, "") else None


def main():
    contenu = open(PEUPLER, encoding="utf-8").read()
    existants, pos_fin_etats = couples_existants(contenu)

    ajouts = []
    with open(SOURCE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("exercice"):
                continue  # rien d'exploitable comme cle sans exercice
            cle = (row["ticker"], int(row["exercice"]))
            if cle in existants:
                continue  # ne remplace jamais une entree deja presente
            rn = to_num(row["resultat_net"])
            rn1 = to_num(row["resultat_net_n1"])
            actif = to_num(row["total_actif"])
            passif = to_num(row["total_passif"])
            cp = to_num(row["capitaux_propres"])
            date_pub = date_pub_depuis_nom_fichier(row["source_url"])
            ligne = (f'    ("{row["ticker"]}", {row["exercice"]}, {rn}, {rn1}, {actif}, {passif}, '
                     f'{cp}, None, None, None,\n'
                     f'     "{row["source_type"]}", "{row["statut_donnee"]}", '
                     f'{repr(date_pub)}),  '
                     f'# Fusion auto 27/07/2026 (Piste A, strategie={row["strategie"] or "?"}) '
                     f'-- {row["note"] or ""}')
            ajouts.append(ligne)
            existants.add(cle)  # evite un doublon si le CSV contient 2 fois le meme couple

    if not ajouts:
        print("Rien a fusionner : tous les couples (ticker, exercice) existent deja.")
        return

    entete = ("\n    # --- Fusion automatique Piste A (27/07/2026) : dettes financieres, \n"
              "    # payout et solvabilite bancaire absents de l'extraction automatique -> \n"
              "    # None (jamais devine). A relire au meme titre que le reste. ---\n")
    nouveau_bloc = entete + "\n".join(ajouts) + "\n"
    contenu_final = contenu[:pos_fin_etats] + nouveau_bloc + contenu[pos_fin_etats:]

    with open(PEUPLER, "w", encoding="utf-8") as f:
        f.write(contenu_final)

    print(f"{len(ajouts)} nouvelle(s) ligne(s) ajoutee(s) a ETATS "
          f"(sur {sum(1 for _ in csv.DictReader(open(SOURCE, encoding='utf-8')))} lignes source, "
          f"le reste existait deja).")


if __name__ == "__main__":
    main()
