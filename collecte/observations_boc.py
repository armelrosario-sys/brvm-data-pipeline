#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/observations_boc.py — chantier C34 (07/10/2026).

QUELLE OBSERVATION DU BOC EST ENCORE PUBLIEE, ET LAQUELLE A ETE RETIREE.

`collecte/dividendes_historique.csv` est le releve BRUT des valeurs lues dans
la colonne « Dernier dividende paye » du Bulletin Officiel de la Cote : une
ligne par valeur observee, avec la FENETRE de publication de cette valeur
(`premiere_observation`, `derniere_observation`). Quand la BRVM REVISE cette
colonne — et elle le fait —, le releve porte donc plusieurs montants pour le
meme versement : l'ancien, dont la fenetre est close, et le courant.

`collecte/dividendes_par_exercice.csv`, qui en est DERIVE par
`historiser_dividendes_exercice.py`, recopie ces lignes sans la fenetre. Son
chargeur gardait « la premiere ligne du fichier », c'est-a-dire, dans 31 cas
sur 31, l'observation que la BRVM avait RETIREE — dont huit restatements de
nominal : PRSC 2018 lu 9 623,00 pour 150,36 (facteur 64), SEMC 2016 lu 677,00
pour 16,92 (facteur 40), SAFC 2010 lu 576,00 pour 23,04 (facteur 25).

LA REGLE, ET SA PORTEE EXACTE. Une revision se lit A TICKER ET DATE DE PAIEMENT
EGAUX : c'est le meme versement republie sous un autre montant. Ce module ne
dit donc rien des versements de DATES differentes, meme rattaches au meme
exercice — ce n'est pas une revision, c'est un autre evenement, et la question
de savoir lequel rattacher a l'exercice reste ouverte.

CE QUE CETTE RESTRICTION EVITE, mesure le 07/10/2026. Une regle large — « parmi
tous les candidats d'un (ticker, exercice), garder la fenetre la plus recente »
— deplacerait DEUX cles de plus, et les deux a tort :

  - ABJC 2018 : 123,72 paye le 27/05/2019 serait remplace par 164,96 paye le
    30/09/2019, un AUTRE versement de la meme annee ;
  - ECOC 2021 : 420,30 paye le 29/04/2022 serait remplace par 549,00 « paye le
    30/05/2022 » — or 549,00 est le versement du 30/05/2023, publie une seule
    fois sous une date fautive (`30-mai-22`) entre le 30/05/2023 et le
    02/01/2024, puis republie sous `30-mai-23`. La regle large ecrirait donc la
    faute de frappe du BOC dans la base.

La fenetre dit QUAND une valeur etait affichee, pas qu'elle est juste : hors
d'un couple (ticker, date) identique, elle ne departage rien.

Usage :
    python3 collecte/observations_boc.py --test
"""
import csv
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))
from dates_dividendes import vers_iso  # noqa: E402

RELEVE = _BASE / "dividendes_historique.csv"


def charger_fenetres(chemin=None):
    """{(ticker, date_iso, montant_arrondi): derniere_observation}.

    Une date brute illisible est IGNOREE, jamais devinee : la ligne du fichier
    derive qui lui correspond restera simplement non arbitrable, et le chargeur
    gardera son comportement historique dessus.
    """
    chemin = Path(chemin) if chemin else RELEVE
    fenetres = {}
    with chemin.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            brute = (r.get("date_paiement") or "").strip()
            iso = vers_iso(brute) if brute else None
            if iso is None:
                continue
            try:
                montant = round(float(r["montant"]), 6)
            except (TypeError, ValueError):
                continue
            cle = (r["ticker"], iso, montant)
            derniere = (r.get("derniere_observation") or "").strip()
            # Un meme montant peut etre reobserve apres une parenthese (BOAM
            # 2024 alterne 237,50 / 237,15 / 237,50 / 237,15) : seule compte sa
            # fenetre la PLUS RECENTE.
            if cle not in fenetres or derniere > fenetres[cle]:
                fenetres[cle] = derniere
    return fenetres


def montant_courant(ticker, date_iso, fenetres):
    """Le montant encore publie pour ce (ticker, date), ou None si inconnu.

    None veut dire « le releve ne porte aucune observation datable pour ce
    couple » : on ne tranche pas, on se tait.
    """
    candidats = [(d, m) for (t, dt, m), d in fenetres.items()
                 if t == ticker and dt == date_iso]
    if not candidats:
        return None
    return max(candidats)[1]


def est_perimee(ticker, date_iso, montant, fenetres):
    """Vrai si le BOC a RETIRE ce montant pour ce versement.

    Faux quand le releve ne sait pas : une case vide vaut mieux qu'une valeur
    approchee, et ici l'abstention est de ne rien ecarter.
    """
    if montant is None:
        return False
    courant = montant_courant(ticker, date_iso, fenetres)
    if courant is None:
        return False
    return abs(round(float(montant), 6) - courant) > 1e-9


# --------------------------------------------------------------------------
# Autotest : il ne lit PAS le depot, il fabrique ses propres fenetres, pour
# que les cas limites soient lisibles a cote de leur reponse.
# --------------------------------------------------------------------------
def _test():
    ok = ech = 0

    def v(cond, libelle):
        nonlocal ok, ech
        if cond:
            ok += 1
            print(f"  [OK] {libelle}")
        else:
            ech += 1
            print(f"  [ECHEC] {libelle}")

    f = {
        # une revision simple : 677,00 retiree, 16,92 courante
        ("SEMC", "2017-09-29", 677.0): "2018-05-31",
        ("SEMC", "2017-09-29", 676.8): "2018-12-19",
        ("SEMC", "2017-09-29", 16.92): "2021-12-22",
        # un montant reobserve apres une parenthese
        ("BOAM", "2025-06-03", 237.5): "2025-06-18",
        ("BOAM", "2025-06-03", 237.15): "2026-05-29",
        # deux versements de DATES differentes : aucun n'est perime
        ("ABJC", "2019-05-27", 123.72): "2019-09-24",
        ("ABJC", "2019-09-30", 41.24): "2019-10-01",
        ("ABJC", "2019-09-30", 164.96): "2022-08-18",
    }
    v(montant_courant("SEMC", "2017-09-29", f) == 16.92,
      "SEMC 29/09/2017 : la valeur courante est 16,92, la derniere publiee")
    v(est_perimee("SEMC", "2017-09-29", 677.0, f)
      and est_perimee("SEMC", "2017-09-29", 676.8, f)
      and not est_perimee("SEMC", "2017-09-29", 16.92, f),
      "677,00 et 676,80 sont retirees, 16,92 ne l'est pas")
    v(montant_courant("BOAM", "2025-06-03", f) == 237.15
      and not est_perimee("BOAM", "2025-06-03", 237.15, f)
      and est_perimee("BOAM", "2025-06-03", 237.5, f),
      "un montant reobserve est juge sur sa fenetre la plus recente (BOAM 237,15)")
    v(not est_perimee("ABJC", "2019-05-27", 123.72, f)
      and not est_perimee("ABJC", "2019-09-30", 164.96, f),
      "deux versements de dates differentes coexistent : aucun n'est perime")
    v(est_perimee("ABJC", "2019-09-30", 41.24, f),
      "la revision du 30/09/2019 (41,24 -> 164,96) est vue, elle, car meme date")
    v(not est_perimee("XXXX", "2020-01-01", 1.0, f),
      "un couple absent du releve n'est jamais declare perime : on se tait")
    v(not est_perimee("SEMC", "2017-09-29", None, f),
      "un montant vide n'est pas perime (une case vide reste une case vide)")

    # --- sur le releve REEL du depot : les invariants de forme ---
    reelles = charger_fenetres()
    v(len(reelles) > 300,
      f"le releve du depot rend {len(reelles)} fenetres (ticker, date, montant)")
    inversees = [k for k, d in reelles.items() if d and d < "1998-01-01"]
    v(not inversees, f"aucune fenetre a date aberrante : {inversees[:3]}")
    v(montant_courant("SAFC", "2011-07-29", reelles) == 23.04,
      "sur le releve reel, SAFC 29/07/2011 est courant a 23,04 et non 576,00 "
      "(facteur 25, le meme que la division de nominal de decembre 2018)")

    print(f"\nobservations_boc : {ok} controle(s) OK, {ech} echec(s)")
    return 1 if ech else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_test())
    fen = charger_fenetres()
    print(f"{len(fen)} fenetre(s) (ticker, date, montant) dans {RELEVE.name}")
