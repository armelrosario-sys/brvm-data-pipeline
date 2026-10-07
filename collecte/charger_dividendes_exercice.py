#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/charger_dividendes_exercice.py — (28/07/2026).

Pont manquant identifie le 28/07/2026 : collecte/dividendes_par_exercice.csv
(364 evenements rattaches a leur exercice, Piste D + historisation) n'etait
jamais charge dans la table dividendes -- seules les 15 lignes codees en
dur dans moteur/peupler.py (DIVIDENDES) y figuraient.

Regle (identique a fusionner_fondamentaux.py) : n'ajoute que des couples
(ticker, exercice_couvert) absents de la table -- ne remplace ni ne
supprime jamais une entree deja presente, meme moins complete. Seules les
lignes confiance=ELEVEE sont chargees par defaut (A_VERIFIER et MANQUANT
restent exclues tant qu'elles ne sont pas confirmees par un document, cf.
les 3 cas FTSC deja rencontres).

LES OBSERVATIONS RETIREES PAR LA BRVM SONT ECARTEES (chantier C34, 07/10/2026).
La regle « n'ajoute que des couples absents » ci-dessus retenait, de fait, LA
PREMIERE LIGNE DU FICHIER pour un (ticker, exercice) donne. Or le fichier source
est GENERE a raison d'une ligne par valeur OBSERVEE dans la colonne « Dernier
dividende paye » du BOC : quand la BRVM revise cette colonne, il porte l'ancienne
valeur ET la courante, et l'ancienne y precede la courante. Mesure du 07/10/2026 :
sur 307 couples (ticker, exercice) chargeables, 33 portent plusieurs montants, et
le chargeur retenait une observation RETIREE dans 31 cas -- dont huit restatements
de nominal (PRSC 2018 9 623,00 au lieu de 150,36, facteur 64 ; SEMC 2016 677,00 au
lieu de 16,92, facteur 40 ; SAFC 2010 576,00 au lieu de 23,04, facteur 25).

La fenetre de publication vit dans collecte/dividendes_historique.csv, que lit
observations_boc.py. Une ligne dont le montant a ete retire POUR SA PROPRE DATE DE
PAIEMENT est desormais ecartee, bruyamment ; la premiere ligne restante est donc
la courante. Deux garde-fous : l'ecart se juge a TICKER ET DATE EGAUX (deux
versements de dates differentes ne se revisent pas l'un l'autre -- cf. ABJC 2018 et
ECOC 2021, documentes dans observations_boc.py), et un couple absent du releve
n'est jamais ecarte -- on ne devine pas.

NORMALISATION DES DATES A L'ENTREE (chantier C10, 30/09/2026). Ce chargeur
inserait la chaine brute du CSV, donc du francais abrege ('24-juil.-17'), ce
qui melangeait deux formats dans dividendes.date_paiement et cassait a la fois
le tri (ORDER BY alphabetique) et l'extraction d'annee de scoring.py. La date
passe desormais par dates_dividendes.vers_iso, et une date illisible fait
ECARTER la ligne avec un message sur stderr -- jamais une date devinee, jamais
une chaine non ISO en base.

Usage : python3 collecte/charger_dividendes_exercice.py [chemin_db]
"""
import csv
import sqlite3
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))
from dates_dividendes import vers_iso  # noqa: E402
from observations_boc import charger_fenetres, est_perimee  # noqa: E402

CSV_SOURCE = str(_BASE / "dividendes_par_exercice.csv")
DB = sys.argv[1] if len(sys.argv) > 1 else str(_BASE.parent / "moteur" / "brvm.db")
CONFIANCE_MIN = "ELEVEE"  # A_VERIFIER/MANQUANT jamais charges automatiquement


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    existants = set(cur.execute(
        "SELECT ticker, exercice_couvert FROM dividendes WHERE exercice_couvert IS NOT NULL").fetchall())

    n_ajoutes, n_deja_presents, n_ecartes_confiance = 0, 0, 0
    n_ecartes_date, n_ecartes_perimee = 0, 0
    fenetres = charger_fenetres()
    with open(CSV_SOURCE, newline="", encoding="utf-8") as f:
        for numero, r in enumerate(csv.DictReader(f), start=2):
            if not r.get("exercice_couvert"):
                continue  # exercice inconnu (MANQUANT) : rien a rattacher
            if r["confiance"] != CONFIANCE_MIN:
                n_ecartes_confiance += 1
                continue
            cle = (r["ticker"], int(r["exercice_couvert"]))
            if cle in existants:
                n_deja_presents += 1
                continue
            # C10 : normalisation a l'entree. Une case vide reste vide (une case
            # vide vaut mieux qu'une valeur approchee) ; une date presente mais
            # illisible fait ecarter la ligne, bruyamment.
            brute = (r.get("date_paiement") or "").strip()
            date_paiement = vers_iso(brute) if brute else None
            if brute and date_paiement is None:
                n_ecartes_date += 1
                print(f"  [ECARTE] ligne {numero}, {r['ticker']} : date de paiement "
                      f"illisible {brute!r} -- ligne non chargee (jamais devinee).",
                      file=sys.stderr)
                continue
            # C34 : une observation que la BRVM a RETIREE pour cette meme date de
            # paiement n'entre pas en base. Ecartee sans etre comptee comme
            # presente : la ligne suivante du meme couple reste candidate, et
            # c'est la courante.
            montant = float(r["montant"]) if r.get("montant") else None
            if est_perimee(r["ticker"], date_paiement, montant, fenetres):
                n_ecartes_perimee += 1
                print(f"  [ECARTE] ligne {numero}, {r['ticker']} exercice "
                      f"{r['exercice_couvert']} : montant {montant} retire par la "
                      f"BRVM pour le versement du {date_paiement} -- observation "
                      f"perimee, non chargee (C34).", file=sys.stderr)
                continue
            cur.execute(
                "INSERT INTO dividendes (ticker, montant_net, date_paiement, "
                "exercice_couvert, statut_donnee, source) VALUES (?,?,?,?,?,?)",
                (r["ticker"], montant,
                 date_paiement, int(r["exercice_couvert"]), "VALIDE",
                 "collecte/dividendes_par_exercice.csv (Piste D, confiance ELEVEE)"))
            existants.add(cle)
            n_ajoutes += 1

    conn.commit()
    print(f"{n_ajoutes} dividende(s) ajoute(s), {n_deja_presents} deja present(s) "
          f"(non dupliques), {n_ecartes_confiance} ecarte(s) (confiance insuffisante), "
          f"{n_ecartes_date} ecarte(s) (date illisible), "
          f"{n_ecartes_perimee} ecarte(s) (observation retiree par la BRVM, C34).")
    conn.close()


if __name__ == "__main__":
    main()
