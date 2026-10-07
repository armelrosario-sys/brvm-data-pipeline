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
vraie. Ce script exige donc une confrontation au releve **independant** de la
page « Volumes / Valeurs » (`collecte/releve_volumes.csv`), releve le meme jour
par un autre collecteur sur une autre source.

LE TEMOIN EST LE VOLUME ET LA VALEUR ECHANGEE, PAS LE PER. PREMIERE VERSION
CORRIGEE PAR LA MESURE. Le premier jet confrontait le **PER**, et il a REFUSE le
versement du 02/10 : 26 concordants sur 44, 59,1 %. La mesure du 07/10/2026 dit
que ce refus portait sur le mauvais temoin, pas sur un defaut d'ancrage :

  - **volume + valeur echangee : 42 sur 42 identiques A L'UNITE** entre le PDF
    anglais et le releve. Ce sont des entiers bruts, non derives, et leur accord
    exact prouve que la LIGNE est bien alignee — donc que le cours et le PER sont
    pris dans les bonnes colonnes ;
  - **PER : 26 sur 44**, avec des ecarts de 0,3 a 2 % (PALC 8,32 contre 8,27 ;
    ECOC 14,83 contre 14,56 ; ORAC 18,5 contre 18,18). Un decalage de colonne
    donnerait des ecarts sauvages, pas des ecarts de 1 %. Le PER est une
    grandeur **derivee** (cours / BPA) que les deux sources ne derivent pas de
    la meme facon — c'est le sujet de C31 et de C33, pas une erreur de lecture.

Le PER reste donc CONFRONTE et son taux PUBLIE, mais il ne bloque plus : un
temoin derive ne peut pas arbitrer l'alignement d'une ligne. Les deux conditions
d'ecriture sont desormais l'accord exact des volumes (`CONCORDANCE_MIN`) et la
continuite des cours contre la seance voisine deja en base (`ECART_COURS_MAX`) :
ecart median mesure 0,53 % contre le 01/10 et 1,30 % contre le 05/10, aucun
au-dela de 15 %. Sans releve pour la date, **rien n'est ecrit**.

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
                     "volumes_concordants", "volumes_confrontes",
                     "per_concordants", "per_confrontes",
                     "seance_voisine", "ecart_cours_median", "verse_le"]

# Concordance minimale du VOLUME et de la VALEUR ECHANGEE contre le releve
# independant, en proportion des tickers confrontables, a l'unite pres. Mesure
# du 07/10/2026 sur le bulletin anglais du 02/10 : 42 sur 42, soit 100 %. Le
# plancher est pose a 95 % pour tolerer une ligne illisible, pas un desaccord.
CONCORDANCE_MIN = 0.95
# Le PER est confronte et publie, mais NE BLOQUE PAS : grandeur derivee que les
# deux sources ne calculent pas identiquement (26/44 le 02/10, ecarts de 0,3 a
# 2 %). Voir le docstring, et les chantiers C31 et C33.
TOLERANCE_PER = 0.05
# Continuite des cours contre la seance voisine deja en base. Mesure du
# 07/10/2026 : ecart median 0,53 % contre le 01/10, 1,30 % contre le 05/10,
# AUCUN titre au-dela de 15 %. Le plafond est pose a 25 % : il ne cherche pas a
# juger un mouvement de marche, il attrape une colonne decalee ou une collision
# d'echelle, qui se comptent en facteurs, pas en pourcents.
ECART_COURS_MAX = 0.25
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


def releve_du_jour(date_iso):
    """Volume, valeur et PER par ticker, releves le meme jour sur la page
    « Volumes / Valeurs ».

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
            t = (r.get("ticker") or "").strip()

            def nb(champ, entier=False):
                brut = (r.get(champ) or "").strip()
                if not brut:
                    return None
                try:
                    v = float(brut)
                except ValueError:
                    return None
                return int(v) if entier else v

            out[t] = {"volume": nb("volume", True), "valeur": nb("valeur", True),
                      "per": nb("per")}
    return out


def confronter_volumes(lignes, date_iso):
    """(concordants, confrontes, desaccords) du couple volume/valeur, A L'UNITE.

    C'est LE temoin d'alignement : deux entiers bruts, non derives, lus sur deux
    sources independantes. Leur accord exact prouve que la ligne est alignee,
    donc que le cours et le PER sont pris dans les bonnes colonnes.
    """
    ref = releve_du_jour(date_iso)
    concordants, confrontes, desaccords = 0, 0, []
    for l in lignes:
        r = ref.get(l["ticker"])
        if not r or r["volume"] is None or r["valeur"] is None:
            continue
        if l["volume_echange"] is None or l["valeur_echangee"] is None:
            continue
        confrontes += 1
        a = (int(l["volume_echange"]), int(l["valeur_echangee"]))
        b = (r["volume"], r["valeur"])
        if a == b:
            concordants += 1
        else:
            desaccords.append((l["ticker"], a, b))
    return concordants, confrontes, desaccords


def confronter_per(lignes, date_iso):
    """(concordants, confrontes, desaccords) du PER. PUBLIE, NON BLOQUANT."""
    ref = releve_du_jour(date_iso)
    concordants, confrontes, desaccords = 0, 0, []
    for l in lignes:
        r = ref.get(l["ticker"])
        attendu = r["per"] if r else None
        if attendu is None or l["per"] is None:
            continue
        confrontes += 1
        if abs(l["per"] - attendu) <= TOLERANCE_PER:
            concordants += 1
        else:
            desaccords.append((l["ticker"], l["per"], attendu))
    return concordants, confrontes, desaccords


def seance_voisine(date_iso, existantes):
    """La seance deja en base la plus proche de `date_iso`, et ses cours."""
    dates = sorted({(r.get("date_bulletin") or "").strip() for r in existantes}
                   - {""} - {date_iso})
    if not dates:
        return None, {}
    proche = min(dates, key=lambda d: abs(
        (int(d[:4]) * 10000 + int(d[5:7]) * 100 + int(d[8:10]))
        - (int(date_iso[:4]) * 10000 + int(date_iso[5:7]) * 100 + int(date_iso[8:10]))))
    cours = {}
    for r in existantes:
        if (r.get("date_bulletin") or "").strip() != proche:
            continue
        brut = (r.get("cours") or "").strip()
        if not brut:
            continue
        try:
            cours[(r.get("ticker") or "").strip()] = float(brut)
        except ValueError:
            continue
    return proche, cours


def confronter_cours(lignes, date_iso, existantes):
    """(n_confrontes, ecart_median, hors_plafond) des cours contre la voisine."""
    proche, cours = seance_voisine(date_iso, existantes)
    if not cours:
        return proche, 0, None, []
    ecarts, hors = [], []
    for l in lignes:
        ref = cours.get(l["ticker"])
        if not ref or not l["cours"]:
            continue
        e = abs(l["cours"] / ref - 1)
        ecarts.append(e)
        if e > ECART_COURS_MAX:
            hors.append((l["ticker"], l["cours"], ref, e))
    if not ecarts:
        return proche, 0, None, []
    ecarts.sort()
    return proche, len(ecarts), ecarts[len(ecarts) // 2], hors


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

    # --- Garde 5a : la preuve d'alignement, sur volume et valeur ------------
    conc, confr, desac = confronter_volumes(lignes, date_iso)
    if confr == 0:
        print(f"  REFUS (garde 5a) : aucun volume du releve Volumes / Valeurs pour "
              f"le {date_iso} — l'alignement des colonnes de l'edition anglaise ne "
              f"peut pas etre prouve, et il n'est qu'une hypothese. Rien ecrit.")
        return False
    taux = conc / confr
    print(f"  garde 5a : volume ET valeur echangee confrontes au releve independant "
          f"du {date_iso} — {conc}/{confr} identiques A L'UNITE ({taux:.1%}, plancher "
          f"{CONCORDANCE_MIN:.0%})")
    if desac:
        print("            desaccords : " + ", ".join(
            f"{t} PDF {a} contre releve {b}" for t, a, b in desac[:6]))
    if taux < CONCORDANCE_MIN:
        print(f"  REFUS (garde 5a) : concordance {taux:.1%} sous le plancher — "
              f"l'alignement des colonnes est vraisemblablement faux. Rien ecrit.")
        return False

    # --- Garde 5b : le PER, publie mais NON BLOQUANT ------------------------
    pc, pconf, pdesac = confronter_per(lignes, date_iso)
    if pconf:
        print(f"  garde 5b : PER confronte — {pc}/{pconf} concordants a "
              f"{TOLERANCE_PER} pres ({pc / pconf:.1%}), NON BLOQUANT : le PER est "
              f"derive (cours / BPA) et les deux sources ne le derivent pas de la "
              f"meme facon (chantiers C31, C33)")
        if pdesac:
            print("            ecarts : " + ", ".join(
                f"{t} {a} contre {b}" for t, a, b in pdesac[:6]))

    # --- Garde 5c : continuite des cours contre la seance voisine -----------
    proche, n_c, med, hors = confronter_cours(lignes, date_iso, existantes)
    if n_c == 0:
        print(f"  REFUS (garde 5c) : aucun cours confrontable a la seance voisine "
              f"{proche} — rien ecrit.")
        return False
    print(f"  garde 5c : cours confrontes a la seance voisine {proche} — {n_c} "
          f"commun(s), ecart median {med:.2%}, plafond individuel "
          f"{ECART_COURS_MAX:.0%}")
    if hors:
        print(f"  REFUS (garde 5c) : {len(hors)} cours au-dela du plafond — une "
              f"colonne decalee ou une collision d'echelle se compte en facteurs. "
              f"Rien ecrit : " + ", ".join(
                  f"{t} {a} contre {b} ({e:+.0%})" for t, a, b, e in hors[:6]))
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
            "volumes_concordants": conc, "volumes_confrontes": confr,
            "per_concordants": pc, "per_confrontes": pconf,
            "seance_voisine": proche,
            "ecart_cours_median": f"{med:.6f}",
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
