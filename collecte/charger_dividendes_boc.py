#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/charger_dividendes_boc.py — chantier C17 (01/10/2026).

PONT MANQUANT, mesure de ce cycle. collecte/dividendes_boc.csv est ecrit par
collecte_boc_quotidien.py depuis la colonne « Dernier dividende paye » du
bulletin officiel (montant net ET date de paiement, lus directement, pas
reconstruits). Le fichier est COMMITE. Aucun chargeur de la chaine ne le
lisait : seuls collecte_boc_quotidien.py lui-meme -- qui ecrit dans une base
jetee a chaque reconstruction -- et backfill_dividendes.py le nommaient.

Ce que cela coutait, mesure le 01/10/2026 (cycle 12) sur la base du jour. En
reconstruisant le dividende implicite du BOC (rendement x cours) et en le
confrontant au versement le plus recent de la table dividendes, 13 titres sur
44 ne concordaient pas -- le constat d'origine de C17, qui l'attribuait a une
« lacune de collecte ». Il n'y en avait aucune : les 13 references etaient
dans dividendes_boc.csv, collectees entre le 28/07 et le 30/09/2026, et
jamais chargees. La donnee etait collectee, commitee, et perdue a l'entree.

PREUVE A DEUX COTES, exigee par la doctrine du depot avant d'ecrire une
donnee certifiee. Les deux cotes viennent de deux colonnes DIFFERENTES du
meme bulletin, extraites independamment :
  1. la colonne « Dernier dividende paye » (montant + date) -> ce fichier ;
  2. le rendement publie x le cours publie -> cours_quotidien_boc, qui forme
     un PALIER stable sur 5 a 41 seances a cours mouvant.
Les 13 concordent entre 0,0 % et 0,4 %. Un palier de rendement qui tient sur
des dizaines de seances a cours variable n'est pas un hasard d'arrondi.

CE QUE CE CHARGEUR NE FAIT JAMAIS :
  - remplacer un montant deja renseigne. Un couple (ticker, exercice) deja
    porteur d'un montant est laisse tel quel et COMPTE comme collision, avec
    son motif a l'ecran. SICC 1999 et ORGT 2019 portent un 0 valide a la main
    (marqueur d'obsolescence, cinq ans sans dividende) : les ecraser est
    exactement ce que la premiere regle du depot interdit ;
  - completer un montant NULL si la date ne concorde pas. Une ligne a montant
    NULL (« date BOC ; montant a re-sourcer ») n'est completee que si sa
    date_paiement est IDENTIQUE a celle du BOC -- c'est la deuxieme moitie de
    la preuve. NSBC 2025 porte 2026-06-30 quand le BOC dit 2026-08-04 : il
    reste NULL, et c'est le bon resultat ;
  - deviner un exercice. Le rattachement passe par deduire_exercice() de
    historiser_dividendes_exercice.py -- une seule definition dans le depot --
    qui rend None hors de la saison d'AGM. La ligne est alors ecartee ;
  - accepter une date non ISO. est_iso() de dates_dividendes.py tranche.

IDEMPOTENT. La deduplication porte sur le triplet (ticker, montant_net,
date_paiement), la meme clef que collecte_boc_quotidien.py. Un second
passage ne trouve que des lignes deja presentes, completions comprises.

Usage : python3 collecte/charger_dividendes_boc.py [chemin_db]
"""
import csv
import sqlite3
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))
from dates_dividendes import est_iso  # noqa: E402
from historiser_dividendes_exercice import deduire_exercice  # noqa: E402

CSV_SOURCE = str(_BASE / "dividendes_boc.csv")
DB = sys.argv[1] if len(sys.argv) > 1 else str(_BASE.parent / "moteur" / "brvm.db")


def main():
    chemin = Path(CSV_SOURCE)
    if not chemin.exists():
        print(f"{CSV_SOURCE} absent : rien a charger (collecte_boc_quotidien.py "
              f"ne l'a jamais ecrit).")
        return 0

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    n_ajoutes = n_completes = n_deja = 0
    collisions, ecartes = [], []

    with chemin.open(newline="", encoding="utf-8") as f:
        for numero, r in enumerate(csv.DictReader(f), start=2):
            ticker = (r.get("ticker") or "").strip()
            brut_m = (r.get("montant_net") or "").strip()
            date_p = (r.get("date_paiement") or "").strip()
            source = (r.get("source") or "").strip()

            if not ticker or not brut_m or not date_p:
                ecartes.append((numero, ticker, "ticker, montant ou date vide"))
                continue
            if not est_iso(date_p):
                ecartes.append((numero, ticker, f"date non ISO {date_p!r}"))
                continue
            try:
                montant = float(brut_m)
            except ValueError:
                ecartes.append((numero, ticker, f"montant illisible {brut_m!r}"))
                continue

            exercice, confiance, _note = deduire_exercice(int(date_p[:4]), int(date_p[5:7]))
            if exercice is None:
                ecartes.append((numero, ticker,
                                f"exercice non deductible du mois de paiement "
                                f"({date_p}, {confiance}) -- jamais devine"))
                continue

            # Deja la, a l'identique : rien a faire. C'est le cas idempotent.
            if cur.execute("SELECT 1 FROM dividendes WHERE ticker=? AND montant_net=? "
                           "AND date_paiement=?", (ticker, montant, date_p)).fetchone():
                n_deja += 1
                continue

            presentes = cur.execute(
                "SELECT id, montant_net, date_paiement FROM dividendes "
                "WHERE ticker=? AND exercice_couvert=?", (ticker, exercice)).fetchall()

            if not presentes:
                cur.execute(
                    "INSERT INTO dividendes (ticker, montant_net, date_paiement, "
                    "exercice_couvert, statut_donnee, source) VALUES (?,?,?,?,?,?)",
                    (ticker, montant, date_p, exercice, "VALIDE",
                     f"collecte/dividendes_boc.csv ({source})"))
                n_ajoutes += 1
                continue

            # Un couple (ticker, exercice) existe deja. Deux issues seulement :
            # completer un montant NULL dont la date concorde, ou refuser.
            traite = False
            for _id, montant_base, date_base in presentes:
                if montant_base is None and date_base == date_p:
                    cur.execute(
                        "UPDATE dividendes SET montant_net=?, source=? WHERE id=?",
                        (montant, f"collecte/dividendes_boc.csv ({source}) -- montant "
                                  f"complete, date identique des deux cotes", _id))
                    n_completes += 1
                    traite = True
            if not traite:
                collisions.append((ticker, exercice, montant, date_p, presentes))

    conn.commit()

    for numero, ticker, motif in ecartes:
        print(f"  [ECARTE] ligne {numero}, {ticker} : {motif}.", file=sys.stderr)
    for ticker, exercice, montant, date_p, presentes in collisions:
        detail = " ; ".join(f"{m} le {d}" for _i, m, d in presentes)
        print(f"  [REFUSE] {ticker} ex.{exercice} : le BOC dit {montant} le {date_p}, "
              f"la base porte deja {detail} -- rien ecrase, rien devine.",
              file=sys.stderr)

    print(f"{n_ajoutes} dividende(s) BOC ajoute(s), {n_completes} montant(s) NULL "
          f"complete(s) (date identique des deux cotes), {n_deja} deja present(s) "
          f"a l'identique, {len(collisions)} refuse(s) (exercice deja renseigne "
          f"autrement), {len(ecartes)} ecarte(s).")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
