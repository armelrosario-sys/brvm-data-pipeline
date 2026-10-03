#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BNPA de clôture d'exercice, figé une fois par an.

    python bnpa_reference.py                    # 31 décembre de l'année précédente
    python bnpa_reference.py --annee 2025       # une année précise
    python bnpa_reference.py --pdf chemin.pdf   # depuis un bulletin déjà téléchargé

Produit donnees/bnpa_reference.json : pour chaque symbole, le cours de clôture,
le PER et le BNPA qui s'en déduit, lus dans le dernier Bulletin Officiel de la
Cote de l'année.

Pourquoi ce bulletin-là. Le PER publié au 31 décembre se rapporte au dernier
exercice clos et publié à cette date, c'est-à-dire l'exercice précédent, tandis
que le PER du jour se rapporte à l'exercice en cours de publication. Le rapport
des deux BNPA donne donc la progression du bénéfice par action d'un exercice à
l'autre — par la même arithmétique, la même source et le même extracteur que le
BNPA courant, ce qui évite d'introduire une seconde méthode qu'il faudrait
réconcilier avec la première.

Ce fichier ne se recalcule pas chaque jour : une fois écrit, il vaut pour toute
l'année. Le relancer est sans effet de bord, il réécrit le même contenu.

Dépendances : les mêmes que collecte_boc.py, dont il réutilise l'extracteur.
"""
import argparse, json, os, sys, tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collecte_boc import (DOSSIER, entete, lignes_actions, pdf_si_present,
                          session_http, texte_pdf, SUFFIXES, URL)

SORTIE = os.path.join(DOSSIER, "bnpa_reference.json")
# Le 31 décembre n'est pas toujours coté : jour férié, week-end, fermeture
# exceptionnelle. On remonte alors vers le dernier jour de bourse de l'année.
RECUL_MAX = 10


def dernier_bulletin_de_lannee(annee):
    """Contenu du dernier bulletin publié en décembre de cette année-là."""
    s = session_http()
    jour = date(annee, 12, 31)
    essais = []
    for _ in range(RECUL_MAX):
        if jour.weekday() < 5:
            for n in SUFFIXES:
                u = URL.format(aaaammjj=jour.strftime("%Y%m%d"), n=n)
                contenu = pdf_si_present(s, u)
                if contenu:
                    print(f"Bulletin de clôture {annee} : {u}")
                    return contenu
                essais.append(u)
        jour -= timedelta(days=1)
    raise SystemExit(
        f"Aucun bulletin trouvé sur les {RECUL_MAX} derniers jours de {annee}.\n  "
        + "\n  ".join(essais[:6]))


def releve(txt):
    """BNPA de chaque titre coté, par la même règle que le tableau de bord."""
    table, sans_per = {}, []
    for v in lignes_actions(txt):
        if not v.get("per") or not v.get("cloture"):
            sans_per.append(v["symbole"])
            continue
        table[v["symbole"]] = dict(
            cours=v["cloture"], per=v["per"],
            bnpa=round(v["cloture"] / v["per"], 2))
    return table, sans_per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annee", type=int, default=date.today().year - 1,
                    help="année de clôture à relever ; par défaut l'année précédente")
    ap.add_argument("--pdf", help="bulletin local, sans téléchargement")
    ap.add_argument("--sortie", default=SORTIE)
    a = ap.parse_args()

    if a.pdf:
        chemin, tmp = a.pdf, None
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(dernier_bulletin_de_lannee(a.annee))
        tmp.close()
        chemin = tmp.name

    txt = texte_pdf(chemin)
    numero, jour_iso = entete(txt)
    table, sans_per = releve(txt)

    print(f"BOC n° {numero} — séance du {jour_iso} — {len(table)} BNPA relevés")
    if sans_per:
        print(f"  sans PER au bulletin, donc sans BNPA : {', '.join(sorted(sans_per))}")
    if table:
        ech = sorted(table.items())[:3]
        for s, d in ech:
            print(f"    {s:6s} cours {d['cours']:>9,} / PER {d['per']:>6} "
                  f"= BNPA {d['bnpa']:>10,.2f}".replace(",", " "))

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    json.dump(dict(numero=numero, seance=jour_iso, annee=a.annee,
                   source="brvm.org — bulletin de clôture d'exercice",
                   methode="cours de clôture / PER publié",
                   valeurs=table, sans_per=sorted(sans_per)),
              open(a.sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{a.sortie} écrit.")
    if tmp:
        os.unlink(tmp.name)


if __name__ == "__main__":
    main()
