#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/versement_boc_eng.py — verser une seance lue sur l'edition ANGLAISE.

CHANTIER C36, option (b), tranchee par Claudia le 05/10/2026 ; execute hors
cycle le 07/10/2026 a sa demande. Procès-verbal exécutable : ce script est la
seule chose qui ecrit, et tout ce qu'il fait est verifiable en le relisant.

CE QU'IL VERSE. Pour chaque seance donnee, les lignes de cotation de l'edition
anglaise du BOC, dans `collecte/cours_quotidien_boc.csv` : **ticker, date,
cours, PER**. La colonne `rendement` est laissee **VIDE** — l'anglais l'arrondit
a deux decimales de la fraction (SNTS 0.04 contre 3,87 % en francais), et une
case vide vaut mieux qu'une valeur approchee. Mais la case vide n'IDENTIFIE
rien : la serie en porte deja 15 116 sur 90 754 lignes (mesure du 07/10/2026,
sur les 2 031 seances). C'est `collecte/seances_boc_eng.csv`, inscrit plus bas,
qui dit quelles seances sont adossees a l'edition anglaise.

LA PREUVE A DEUX COTES EST UNE CONDITION D'ECRITURE, PAS UN COMMENTAIRE.
L'extracteur anglais ancre ses colonnes depuis la droite comme l'extracteur
francais. C'est vraisemblable — c'est le meme bulletin traduit — mais ce n'est
pas prouve, et se tromper de colonne versrait des valeurs fausses sous une date
vraie. Ce script exige donc, AVANT d'ecrire, que le PER extrait du PDF concorde
avec celui du releve **independant** de la page « Volumes / Valeurs »
(`collecte/releve_volumes.csv`), releve le meme jour par un autre collecteur sur
une autre source. Sans releve pour cette date, ou si la concordance tombe sous
`CONCORDANCE_MIN`, **rien n'est ecrit** et le motif est dit.

LES SEPT GARDES, dans l'ordre ou elles s'appliquent.
  1. entete et comptes du CSV conformes, sinon refus ;
  2. empreinte SHA-256 du fichier AVANT, journalisee ;
  3. la seance visee ne doit porter AUCUNE ligne prealable (sinon ce n'est plus
     un versement, c'est une reecriture : refus) ;
  4. **garde `attendu`** : aucune ligne preexistante du fichier, quelle que soit
     sa date, ne doit changer — verifiee ligne a ligne apres ecriture ;
  5. preuve a deux cotes sur le PER contre `releve_volumes.csv` ;
  6. plafond de vraisemblance : le nombre de titres verses doit etre au moins
     `TITRES_MIN`, sinon la seance serait un second trou deguise en seance
     complete ;
  7. empreinte SHA-256 APRES, et relecture du fichier ecrit.

IDEMPOTENT. Une seconde execution constate « DEJA APPLIQUE » par la garde 3 et
n'ecrit rien.

JOURNAL DES EDITIONS. Chaque seance versee est inscrite dans
`collecte/seances_boc_eng.csv` (date, edition, url, nombre de titres,
concordance mesuree). C'est ce registre qui rend decidable le remplacement promis
par l'option (b) : si l'edition francaise parait plus tard, on sait quelles
seances sont adossees a l'anglaise.

Usage :
  python3 outils/versement_boc_eng.py --rapport <pdf> [<pdf> ...]
  python3 outils/versement_boc_eng.py --verser <pdf> [<pdf> ...]
"""
import argparse
import csv
import hashlib
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "collecte"))

CSV_QUOTIDIEN = RACINE / "collecte" / "cours_quotidien_boc.csv"
RELEVE = RACINE / "collecte" / "releve_volumes.csv"
REGISTRE = RACINE / "collecte" / "seances_boc_eng.csv"
COLONNES = ["ticker", "date_bulletin", "cours", "per", "rendement"]
COLONNES_REGISTRE = ["date_bulletin", "edition", "source", "n_titres",
                     "per_concordants", "per_confrontes", "verse_le"]

# Concordance minimale du PER contre le releve independant, en proportion des
# tickers confrontables. Le PER du releve est arrondi a deux decimales comme
# celui du bulletin : on compare a TOLERANCE_PER pres.
CONCORDANCE_MIN = 0.90
TOLERANCE_PER = 0.05
# Au moins ce nombre de titres, sinon la seance versee serait incomplete sans le
# dire. La cote compte 48 titres au 07/10/2026 ; tous ne cotent pas chaque jour.
TITRES_MIN = 40


def sha256(chemin):
    if not Path(chemin).exists():
        return None
    h = hashlib.sha256()
    h.update(Path(chemin).read_bytes())
    return h.hexdigest()


def lire_quotidien():
    with CSV_QUOTIDIEN.open(newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        entete = lecteur.fieldnames
        lignes = list(lecteur)
    return entete, lignes


def per_du_releve(date_iso):
    """PER par ticker, releve le meme jour sur la page Volumes / Valeurs.

    Source INDEPENDANTE du PDF : autre collecteur, autre page. C'est ce qui
    fait de la confrontation une preuve et non une verification circulaire.
    """
    if not RELEVE.exists():
        return {}
    out = {}
    with RELEVE.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("date_releve") or "").strip() != date_iso:
                continue
            brut = (r.get("per") or "").strip()
            if not brut:
                continue
            try:
                out[(r.get("ticker") or "").strip()] = float(brut)
            except ValueError:
                continue
    return out


def confronter(lignes, date_iso):
    """(concordants, confrontes, desaccords) du PER contre le releve."""
    ref = per_du_releve(date_iso)
    concordants, confrontes, desaccords = 0, 0, []
    for l in lignes:
        attendu = ref.get(l["ticker"])
        if attendu is None or l["per"] is None:
            continue
        confrontes += 1
        if abs(l["per"] - attendu) <= TOLERANCE_PER:
            concordants += 1
        else:
            desaccords.append((l["ticker"], l["per"], attendu))
    return concordants, confrontes, desaccords


def traiter(chemin_pdf, ecrire):
    from extracteur_boc_eng import extraire_boc_eng

    nom = Path(chemin_pdf).name
    print(f"\n=== {nom} ===")
    ecartes = set()
    date_b, lignes = extraire_boc_eng(chemin_pdf, ecartes=ecartes)
    if not date_b or not lignes:
        print("  REFUS : extraction vide ou date du bulletin illisible — rien ecrit.")
        return False
    date_iso = f"{date_b[:4]}-{date_b[4:6]}-{date_b[6:]}"
    print(f"  seance lue : {date_iso} | {len(lignes)} titre(s) | "
          f"{len(ecartes)} ecarte(s){' : ' + ', '.join(sorted(ecartes)) if ecartes else ''}")

    # --- Garde 1 : entete et comptes ----------------------------------------
    entete, existantes = lire_quotidien()
    if entete != COLONNES:
        print(f"  REFUS : entete inattendue {entete}, attendu {COLONNES}.")
        return False
    avant_n = len(existantes)
    avant_sha = sha256(CSV_QUOTIDIEN)
    print(f"  garde 1 : entete conforme, {avant_n} ligne(s) en place")
    print(f"  garde 2 : SHA-256 avant = {avant_sha[:16]}…")

    # --- Garde 3 : la seance ne doit rien porter ----------------------------
    deja = [r for r in existantes if (r.get("date_bulletin") or "").strip() == date_iso]
    if deja:
        print(f"  garde 3 : la seance {date_iso} porte deja {len(deja)} ligne(s) — "
              f"versement DEJA APPLIQUE, rien ecrit. Un remplacement de valeurs "
              f"existantes n'est pas un versement et n'est pas autorise ici.")
        return True  # idempotence : ce n'est pas un echec

    # --- Garde 5 : la preuve a deux cotes -----------------------------------
    conc, confr, desac = confronter(lignes, date_iso)
    if confr == 0:
        print(f"  REFUS (garde 5) : aucun PER du releve Volumes / Valeurs pour le "
              f"{date_iso} — la disposition des colonnes de l'edition anglaise ne "
              f"peut pas etre prouvee, et elle n'est qu'une hypothese. Rien ecrit.")
        return False
    taux = conc / confr
    print(f"  garde 5 : PER confronte au releve independant du {date_iso} — "
          f"{conc}/{confr} concordants a {TOLERANCE_PER} pres ({taux:.1%}, "
          f"plancher {CONCORDANCE_MIN:.0%})")
    if desac:
        print(f"           desaccords : " + ", ".join(
            f"{t} PDF {a} contre releve {b}" for t, a, b in desac[:8]))
    if taux < CONCORDANCE_MIN:
        print(f"  REFUS (garde 5) : concordance {taux:.1%} sous le plancher — "
              f"l'ancrage des colonnes est vraisemblablement faux. Rien ecrit.")
        return False

    # --- Garde 6 : vraisemblance du nombre de titres ------------------------
    if len(lignes) < TITRES_MIN:
        print(f"  REFUS (garde 6) : {len(lignes)} titre(s) seulement, plancher "
              f"{TITRES_MIN} — une seance versee incomplete serait un second trou "
              f"deguise en seance complete. Rien ecrit.")
        return False
    print(f"  garde 6 : {len(lignes)} titre(s), au-dessus du plancher {TITRES_MIN}")

    if not ecrire:
        print("  MODE RAPPORT : toutes les gardes passent, rien n'a ete ecrit. "
              "Relancer avec --verser pour appliquer.")
        return True

    # --- Ecriture, par AJOUT seul -------------------------------------------
    nouvelles = [{
        "ticker": l["ticker"],
        "date_bulletin": date_iso,
        "cours": "" if l["cours"] is None else repr(l["cours"]),
        "per": "" if l["per"] is None else repr(l["per"]),
        "rendement": "",          # option (b) : vide, jamais l'arrondi anglais
    } for l in sorted(lignes, key=lambda x: x["ticker"])]
    with CSV_QUOTIDIEN.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writerows(nouvelles)
        f.flush()
        os.fsync(f.fileno())

    # --- Garde 4 : aucune ligne preexistante n'a change ---------------------
    _entete2, apres = lire_quotidien()
    if len(apres) != avant_n + len(nouvelles):
        print(f"  ALERTE : {len(apres)} ligne(s) apres ecriture, attendu "
              f"{avant_n + len(nouvelles)}.")
        return False
    identiques = all(apres[i] == existantes[i] for i in range(avant_n))
    print(f"  garde 4 (attendu) : les {avant_n} ligne(s) preexistantes sont "
          f"{'INCHANGEES' if identiques else 'MODIFIEES — ANOMALIE'}")
    if not identiques:
        return False

    # --- Garde 7 : empreinte apres, et relecture ----------------------------
    apres_sha = sha256(CSV_QUOTIDIEN)
    print(f"  garde 7 : SHA-256 apres = {apres_sha[:16]}… | {len(nouvelles)} ligne(s) "
          f"ajoutee(s), 0 modifiee(s)")
    relu = [r for r in apres if (r.get("date_bulletin") or "").strip() == date_iso]
    vides = sum(1 for r in relu if not (r.get("rendement") or "").strip())
    print(f"           relecture : {len(relu)} ligne(s) au {date_iso}, "
          f"{vides} rendement(s) vide(s) (attendu {len(relu)})")

    # --- Registre des editions ----------------------------------------------
    import time
    existe = REGISTRE.exists()
    with REGISTRE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES_REGISTRE)
        if not existe:
            w.writeheader()
        w.writerow({
            "date_bulletin": date_iso, "edition": "BOC_ENG",
            "source": nom, "n_titres": len(nouvelles),
            "per_concordants": conc, "per_confrontes": confr,
            "verse_le": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    print(f"  registre : {REGISTRE.name} inscrit (edition BOC_ENG)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--verser", action="store_true",
                    help="appliquer l'ecriture (par defaut : rapport seul)")
    ap.add_argument("--rapport", action="store_true", help="explicite, defaut")
    args = ap.parse_args()
    ecrire = args.verser and not args.rapport
    print("MODE :", "VERSEMENT" if ecrire else "RAPPORT (aucune ecriture)")
    ok = True
    for p in args.pdfs:
        ok = traiter(p, ecrire) and ok
    print("\n" + ("TOUT EST PASSE" if ok else "AU MOINS UN REFUS — voir ci-dessus"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
