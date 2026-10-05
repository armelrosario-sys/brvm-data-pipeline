#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C22 — les deux refus du pont BOC qui se tranchent sur une DATE
=========================================================================

Ce que ce script tranche, et ce qu'il ne touche pas
---------------------------------------------------
``collecte/charger_dividendes_boc.py`` refuse d'ecrire quand le couple
(ticker, exercice) porte deja autre chose. Mesure du 05/10/2026 (cycle 20) :
il refuse **8 fois**, exactement les 8 cas inscrits dans C22. Les huit sont
tranches, avec leur motif et leur preuve, dans le registre
``collecte/arbitrages_pont_boc.csv``, que la section 24 relit.

Deux seulement sont appliques ici, et c'est ce qui les distingue : leur
arbitrage porte sur une **date de paiement saisie a la main**, dans
``donnees/base/dividendes.csv``, et le montant qu'elle commande ne change pas
de main — il est soit identique des deux cotes, soit complete par le pont
lui-meme sous sa propre garde.

1. **SNTS 2025 — la date, pas le montant.** La base portait 1 740,00 paye le
   **25/05/2026**, d'apres Sika Finance 02/2026 ; le BOC publie le meme
   1 740,00 paye le **26/05/2026**, et il le publie du 2026-05-21 au
   2026-07-24, donc **deux mois apres le versement**. Une annonce de presse de
   fevrier est anterieure a l'evenement ; la date publiee par la bourse
   elle-meme, apres coup, l'emporte. Le montant est le meme des deux cotes et
   ne bouge pas : l'implicite rendement x cours du BOC vaut 1 738,2 a 1 741,5
   sur les 8 dernieres seances, soit 0,07 a 0,10 % de 1 740. Effet second
   mesure : la clef de deduplication du pont est le triplet
   (ticker, montant, date) — elle ne protege donc **pas** d'un doublon a un
   jour pres, et aligner la date supprime ce risque au lieu de le laisser.

2. **NSBC 2025 — une date d'AGO a la place d'une date de paiement.** La base
   portait un montant **vide** date du **30/06/2026**, et sa propre note dit
   pourquoi : « AGO 30/06/2026 : 19 Mds FCFA approuves (Ecofin) ; par action a
   sourcer ». C'etait le **seul** montant vide de la table des dividendes. Le
   BOC donne 675,98 paye le **04/08/2026**. Ce script ne corrige que la
   **date** ; le montant est ensuite ecrit par
   ``collecte/charger_dividendes_boc.py``, sous la garde qui fait la moitie de
   sa preuve : un montant NULL n'est complete que si la date_paiement est
   identique des deux cotes.

Preuve a deux cotes, deux colonnes DIFFERENTES du meme bulletin
---------------------------------------------------------------
C'est le patron de preuve que C17 a etabli et que la section 24 verrouille :

1. la colonne « Dernier dividende paye » (montant **et** date), relevee dans
   ``collecte/dividendes_boc.csv`` — NSBC 675,98 / 2026-08-04, source
   ``BOC 2026-08-03`` ; SNTS 1 740,00 / 2026-05-26, source ``BOC 2026-07-17`` ;
2. le **rendement publie x le cours publie** de ``cours_quotidien_boc``, qui
   est une extraction independante de la precedente. Mesure de ce cycle sur
   les 8 dernieres seances a rendement publie :
   NSBC 675,0 a 676,8 (ecart 0,02 a 0,15 % de 675,98) ;
   SNTS 1 738,2 a 1 741,5 (ecart 0,07 a 0,10 % de 1 740,00).

Reserve explicite sur NSBC, et elle ne ferme pas
------------------------------------------------
Les « 19 Mds approuves » de la note rapportes a 675,98 impliquent **28,1 M**
d'actions. Le BNPA de reference (1 540,38, seance 2025-12-31) rapporte au
resultat net de ``etats_financiers`` en implique **24,7 M** (exercice 2024) ou
**26,4 M** (exercice 2025) — soit 16,7 a 17,9 Mds distribues contre 19
annonces. L'identite ne ferme qu'en lisant les 19 Mds en **brut**
(675,98 / 0,875 x 24,7 M = 19,1 Mds, a 0,6 %), ce qui reste un **signal** et
non une preuve. La preuve retenue est celle des deux colonnes du BOC ; cette
lecture-la est notee parce qu'elle releve de C2 (brut/net), pas parce qu'elle
tranche.

Ce que ce script NE fait PAS, et pourquoi
-----------------------------------------
* **SICC 1999 et ORGT 2019** : le 0 de la base est un marqueur d'obsolescence
  pose a la main. La premiere regle du depot interdit d'ecraser une valeur
  adossee a une note qui documente une analyse humaine. Rien ecrit. ORGT est
  **signale** au registre : l'implicite du BOC vaut 59,40 a 59,64 sur 8
  seances, donc le BOC divise bien par 59,52 et un dividende a ete verse le
  17/07/2020 pour l'exercice 2019, alors que la note (« 5e annee sans
  dividende ») porte sur 2020-2024. Le marqueur est pose sur un exercice qui a
  paye : c'est a Claudia de le trancher.
* **BOABF 2025** : refus motive, la base fait foi. Sa note dit « net apres
  IRVM 12,5 % », et 397,25 / 0,875 = **454,00 exactement**, un brut rond, quand
  397,00 / 0,875 = 453,71 ne l'est pas. L'implicite **ne separe pas** les deux
  (0,02 a 0,09 % contre 397,00 ; 0,01 a 0,15 % contre 397,25, les deux sous
  l'arrondi de publication) et il faut le dire ainsi. Ecart 0,06 % : aucun rang
  ne bouge. Renvoi C2.
* **SAFC 2010, SEMC 2020, BOAC 2025** : tranches au registre — la publication
  courante de la BRVM fait foi sur celle qu'elle a retiree, soit 23,04 / 14,00
  / 597,53 — mais **non appliques ici**. Leur valeur ne vient pas d'une saisie
  humaine : elle vient de ``collecte/dividendes_par_exercice.csv``, qui est un
  fichier **genere** par ``historiser_dividendes_exercice.py`` depuis
  ``collecte/dividendes_historique.csv``. Y ecrire serait defait a la premiere
  regeneration. Ces trois-la ne sont donc pas trois arbitrages mais **un seul**,
  qui porte sur la regle de chargement, et dont le cycle 20 a mesure la portee
  entiere : **31 valeurs** en base, 8 d'entre elles decalees d'un facteur 2 a
  64 (restatements de nominal), pour un effet sur ``collecte/profils.json``
  de **2 champs de texte** et **0 profil, 0 grade, 0 rang**. C'est le chantier
  **C34**, et c'est a Claudia de le valider.

Gardes
------
Sept, verifiees a l'execution et pas seulement ecrites ici : existence du
fichier, entete exact, nombre de lignes, empreinte SHA-256 **avant**,
assertion d'**unicite** de chaque ancre (la ligne entiere, pas un fragment),
garde ``attendu`` sur chaque champ avant ecriture (ticker, montant, date,
exercice lus par l'analyseur CSV et compares un par un), et relecture apres
ecriture — nombre de lignes, nombre de colonnes par ligne, et les champs
attendus apres. Le script refuse d'ecrire si la realite differe, et une
seconde execution ne fait rien et le dit.

Usage : ``python3 outils/arbitrage_refus_pont_boc.py``
        ``python3 outils/arbitrage_refus_pont_boc.py --test``
"""

import csv
import hashlib
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIBLE = "donnees/base/dividendes.csv"
REGISTRE = "collecte/arbitrages_pont_boc.csv"

ENTETE = "ticker,montant_net,date_paiement,exercice_couvert,note"
LIGNES = 16
SHA256_AVANT = "d2b516c725f24e757eec87818c2c408f55586a5f3db149603ffae2d96c6531f5"

# Marqueur d'idempotence : present dans le fichier, la passe est deja faite.
MARQUEUR = "cycle 20, chantier C22"

_NOTE_SNTS_AVANT = "source : Sika Finance 02/2026 (1933 brut / 1740 net)"
_NOTE_NSBC_AVANT = ("AGO 30/06/2026 : 19 Mds FCFA approuves (Ecofin) ; "
                    "par action a sourcer")

# La note d'origine est CONSERVEE mot pour mot et l'arbitrage est AJOUTE
# derriere, date et source : elle dit l'etat de la connaissance avant ce cycle.
_NOTE_SNTS_APRES = _NOTE_SNTS_AVANT + (
    " -- DATE TRANCHEE le 05/10/2026 (cycle 20, chantier C22) : le BOC publie "
    "le 26/05/2026, et il le publie du 2026-05-21 au 2026-07-24, donc deux mois "
    "apres le versement, quand la date de presse du 25/05 lui est anterieure. "
    "Le montant 1740 ne change pas et l'implicite rendement x cours du BOC le "
    "confirme : 1738,2 a 1741,5 sur les 8 dernieres seances (0,07 a 0,10 %). "
    "Registre : collecte/arbitrages_pont_boc.csv ; proces-verbal : "
    "outils/arbitrage_refus_pont_boc.py.")

_NOTE_NSBC_APRES = _NOTE_NSBC_AVANT + (
    " -- DATE TRANCHEE le 05/10/2026 (cycle 20, chantier C22) : la date portee "
    "ici etait celle de l'AGO, pas celle du paiement. Le BOC donne 675,98 paye "
    "le 04/08/2026 (collecte/dividendes_boc.csv, source BOC 2026-08-03) et "
    "l'implicite rendement x cours vaut 675,0 a 676,8 sur les 8 dernieres "
    "seances (0,02 a 0,15 %). Seule la DATE est corrigee ici ; le montant est "
    "ecrit par collecte/charger_dividendes_boc.py sous sa garde de date "
    "identique des deux cotes. La phrase qui precede est conservee : elle dit "
    "ce qu'on savait avant cette date. Reserve : les 19 Mds rapportes a 675,98 "
    "impliquent 28,1 M d'actions contre 24,7 a 26,4 M deduites du BNPA de "
    "reference -- l'identite ne ferme pas, elle n'est donc pas comptee comme "
    "preuve. Registre : collecte/arbitrages_pont_boc.csv.")

# chaque cible : la ligne ENTIERE avant, la ligne ENTIERE apres, et les champs
# attendus des deux cotes. L'ancre est la ligne complete : aucun fragment ne
# peut mordre sur une autre ligne.
CIBLES = [
    {
        "nom": "SNTS 2025",
        "avant": ["SNTS", "1740", "2026-05-25", "2025", _NOTE_SNTS_AVANT],
        "apres": ["SNTS", "1740", "2026-05-26", "2025", _NOTE_SNTS_APRES],
    },
    {
        "nom": "NSBC 2025",
        "avant": ["NSBC", "", "2026-06-30", "2025", _NOTE_NSBC_AVANT],
        "apres": ["NSBC", "", "2026-08-04", "2025", _NOTE_NSBC_APRES],
    },
]


def sha256(texte):
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def lire(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8", newline="") as f:
        return f.read()


def ecrire(chemin, texte):
    with open(os.path.join(RACINE, chemin), "w", encoding="utf-8", newline="") as f:
        f.write(texte)


def serialiser(champs):
    """Rend la ligne CSV exacte qu'ecrirait csv.writer pour ces champs."""
    tampon = io.StringIO()
    csv.writer(tampon, lineterminator="").writerow(champs)
    return tampon.getvalue()


def occurrences(texte, ligne):
    """Nombre de lignes du fichier EGALES a `ligne`. Ancre = ligne entiere."""
    return sum(1 for l in texte.split("\n") if l == ligne)


def remplacer_ligne(texte, avant, apres):
    return "\n".join(apres if l == avant else l for l in texte.split("\n"))


def champs_par_ligne(texte):
    """Nombre de champs vus par l'analyseur CSV, ligne par ligne. Prouve
    qu'aucune virgule n'a ete ajoutee ni perdue par le remplacement."""
    return [len(l) for l in csv.reader(io.StringIO(texte)) if l]


def echec(message):
    print(f"  [REFUS] {message}")
    print("\nARBITRAGE ABANDONNE — aucun fichier n'a ete ecrit.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Autotest : la mecanique, sur des chaines fabriquees.
# ---------------------------------------------------------------------------

CAS_TEST = [
    # (texte, ligne_avant, ligne_apres, occurrences attendues, resultat attendu)
    # Cas nominal : une seule ligne egale a l'ancre, et c'est elle qui bouge.
    ("a,1\nb,2\n", "a,1", "a,9", 1, "a,9\nb,2\n"),
    # Le piege du fragment : une ancre de ligne ENTIERE ne mord pas sur une
    # ligne qui la contient en prefixe.
    ("a,1\na,10\n", "a,1", "a,9", 1, "a,9\na,10\n"),
    # Idempotence : relance sur le resultat, zero occurrence, texte inchange.
    ("a,9\nb,2\n", "a,1", "a,9", 0, "a,9\nb,2\n"),
    # Une ancre absente ne change rien.
    ("b,2\n", "a,1", "a,9", 0, "b,2\n"),
    # Deux lignes identiques : l'assertion d'unicite doit voir 2, pas 1.
    ("a,1\na,1\n", "a,1", "a,9", 2, "a,9\na,9\n"),
    # Une virgule dans un champ force le guillemet, et la ligne reste une ligne.
    ('x,"p, q"\n', 'x,"p, q"', 'x,"p, r"', 1, 'x,"p, r"\n'),
]


def autotest():
    n_ok = n_ko = 0

    def controle(ok, libelle, detail=""):
        nonlocal n_ok, n_ko
        print(f"  [{'OK' if ok else 'ECHEC'}] {libelle}")
        if not ok and detail:
            print(f"        {detail}")
        if ok:
            n_ok += 1
        else:
            n_ko += 1

    for i, (txt, av, ap, n_att, attendu) in enumerate(CAS_TEST, 1):
        n = occurrences(txt, av)
        res = remplacer_ligne(txt, av, ap)
        controle(n == n_att and res == attendu,
                 f"cas {i} : {n} occurrence(s) (attendu {n_att})",
                 f"obtenu {res!r}, attendu {attendu!r}")

    # Le remplacement ne change jamais le nombre de lignes.
    for txt, av, ap, _n, _a in CAS_TEST:
        controle(remplacer_ligne(txt, av, ap).count("\n") == txt.count("\n"),
                 "le remplacement ne change pas le nombre de lignes")

    # La serialisation d'une note a virgules est relue a l'identique.
    for cible in CIBLES:
        ligne = serialiser(cible["apres"])
        relu = next(csv.reader(io.StringIO(ligne)))
        controle(relu == cible["apres"],
                 f"{cible['nom']} : la ligne serialisee se relit champ pour champ")
        controle(len(relu) == 5,
                 f"{cible['nom']} : 5 champs apres serialisation, pas plus")

    # Seule la date change ; ticker, montant et exercice sont intacts.
    for cible in CIBLES:
        av, ap = cible["avant"], cible["apres"]
        bouges = [i for i in range(4) if av[i] != ap[i]]
        controle(bouges == [2],
                 f"{cible['nom']} : seul le champ date_paiement change "
                 f"(champs modifies : {bouges})")

    # La note d'origine est conservee mot pour mot dans la note d'arrivee.
    for cible in CIBLES:
        controle(cible["apres"][4].startswith(cible["avant"][4]),
                 f"{cible['nom']} : la note d'origine est conservee en tete")
        controle(MARQUEUR in cible["apres"][4],
                 f"{cible['nom']} : le marqueur d'idempotence est dans la note")

    # Le registre des 8 est lisible, complet, et chaque ligne porte un motif.
    chemin_reg = os.path.join(RACINE, REGISTRE)
    if not os.path.exists(chemin_reg):
        controle(False, f"{REGISTRE} existe")
    else:
        with open(chemin_reg, encoding="utf-8", newline="") as f:
            reg = list(csv.DictReader(f))
        controle(len(reg) == 8, f"{REGISTRE} porte 8 arbitrages ({len(reg)} lus)")
        controle(all(r["motif"].strip() and r["decision"].strip()
                     and r["chantier"].strip() for r in reg),
                 "chaque ligne du registre porte une decision, un motif et un "
                 "chantier de renvoi")
        appliques = {r["ticker"] for r in reg if r["decision"] == "TRANCHE_APPLIQUE"}
        controle(appliques == {"SNTS", "NSBC"},
                 f"les seuls arbitrages APPLIQUES sont SNTS et NSBC ({appliques})")

    print(f"\n{n_ok} controle(s) OK, {n_ko} echec(s)")
    return 0 if n_ko == 0 else 1


# ---------------------------------------------------------------------------
# Arbitrage
# ---------------------------------------------------------------------------

def main():
    print("Chantier C22 — arbitrage des refus du pont BOC (dates SNTS et NSBC)")
    print("=" * 72)

    chemin_abs = os.path.join(RACINE, CIBLE)
    if not os.path.exists(chemin_abs):
        echec(f"{CIBLE} : fichier absent")
    if not os.path.exists(os.path.join(RACINE, REGISTRE)):
        echec(f"{REGISTRE} : le registre des 8 arbitrages est absent — il est la "
              f"moitie du travail de C22, le script ne va pas sans lui")
    txt = lire(CIBLE)

    lignes_avant = [serialiser(c["avant"]) for c in CIBLES]
    lignes_apres = [serialiser(c["apres"]) for c in CIBLES]

    etat = []
    for cible, la, lp in zip(CIBLES, lignes_avant, lignes_apres):
        n_av = occurrences(txt, la)
        n_ap = occurrences(txt, lp)
        if n_av == 1 and n_ap == 0:
            etat.append("a_faire")
            print(f"  [OK] {cible['nom']} : ancre unique, arbitrage a appliquer")
        elif n_av == 0 and n_ap == 1:
            etat.append("deja_fait")
            print(f"  [DEJA] {cible['nom']} : la ligne porte deja la date "
                  f"tranchee {cible['apres'][2]}")
        else:
            echec(f"{cible['nom']} : {n_av} occurrence(s) de la ligne d'avant et "
                  f"{n_ap} de celle d'apres — attendu 1 et 0 (a faire) ou 0 et 1 "
                  f"(deja fait). La realite ne correspond a aucun des deux etats "
                  f"connus ; la ligne a ete editee depuis la redaction de ce "
                  f"script.")

    if all(e == "deja_fait" for e in etat):
        print("\nARBITRAGE DEJA APPLIQUE — aucun fichier ecrit, rien a faire.")
        return 0

    # --- Gardes sur la forme du fichier, seulement s'il reste a ecrire -------
    nb = txt.count("\n") + (0 if txt.endswith("\n") else 1)
    if nb != LIGNES:
        echec(f"{CIBLE} : {nb} lignes, attendu {LIGNES}")
    entete = txt.split("\n", 1)[0].rstrip("\r")
    if entete != ENTETE:
        echec(f"{CIBLE} : entete inattendu\n    obtenu  : {entete}\n"
              f"    attendu : {ENTETE}")
    h = sha256(txt)
    if h != SHA256_AVANT:
        echec(f"{CIBLE} : empreinte {h[:16]}..., attendu {SHA256_AVANT[:16]}... — "
              f"le fichier a change depuis la redaction de ce script")
    print(f"  [OK] {CIBLE} : {nb} lignes, entete et empreinte conformes")

    # --- Garde `attendu` sur chaque champ, lu par l'analyseur CSV -----------
    with io.StringIO(txt) as f:
        avant_csv = list(csv.DictReader(f))
    for cible, e in zip(CIBLES, etat):
        if e == "deja_fait":
            continue
        t, m, d, ex, _n = cible["avant"]
        vues = [r for r in avant_csv
                if r["ticker"] == t and r["exercice_couvert"] == ex]
        if len(vues) != 1:
            echec(f"{cible['nom']} : {len(vues)} ligne(s) pour (ticker={t}, "
                  f"exercice={ex}) — attendu exactement 1")
        r = vues[0]
        for colonne, attendu in (("montant_net", m), ("date_paiement", d)):
            if r[colonne] != attendu:
                echec(f"{cible['nom']} : {colonne} vaut {r[colonne]!r}, attendu "
                      f"{attendu!r} — la realite differe, rien n'est ecrit")
        print(f"  [OK] {cible['nom']} : montant {m!r} et date {d!r} conformes "
              f"a l'attendu")

    # --- Ecriture -----------------------------------------------------------
    print("\nEcriture")
    print("-" * 72)
    apres = txt
    for cible, e, la, lp in zip(CIBLES, etat, lignes_avant, lignes_apres):
        if e == "deja_fait":
            continue
        apres = remplacer_ligne(apres, la, lp)
        print(f"  {cible['nom']} : date_paiement {cible['avant'][2]} -> "
              f"{cible['apres'][2]}, montant {cible['avant'][1]!r} inchange")

    if apres.count("\n") != txt.count("\n"):
        echec("le remplacement a change le nombre de lignes")
    ca, cp = champs_par_ligne(txt), champs_par_ligne(apres)
    if ca != cp:
        echec(f"le nombre de champs par ligne a change : {ca} -> {cp}")
    bougees = [i for i, (a, b) in enumerate(zip(txt.split("\n"),
                                                apres.split("\n"))) if a != b]
    attendues = sum(1 for e in etat if e == "a_faire")
    if len(bougees) != attendues:
        echec(f"{len(bougees)} ligne(s) modifiee(s), attendu {attendues}")

    ecrire(CIBLE, apres)

    # --- Relecture ----------------------------------------------------------
    print("\nRelecture")
    print("-" * 72)
    relu = lire(CIBLE)
    nb_relu = relu.count("\n") + (0 if relu.endswith("\n") else 1)
    if nb_relu != LIGNES:
        echec(f"relecture : {nb_relu} lignes, attendu {LIGNES}")
    if champs_par_ligne(relu) != ca:
        echec("relecture : le nombre de champs par ligne a change")
    with io.StringIO(relu) as f:
        apres_csv = list(csv.DictReader(f))
    for cible in CIBLES:
        t, m, d, ex, note = cible["apres"]
        vues = [r for r in apres_csv
                if r["ticker"] == t and r["exercice_couvert"] == ex]
        if len(vues) != 1:
            echec(f"relecture : {len(vues)} ligne(s) pour {t} ex.{ex}")
        r = vues[0]
        if r["date_paiement"] != d or r["montant_net"] != m or r["note"] != note:
            echec(f"relecture : {t} ex.{ex} ne porte pas les champs attendus")
        print(f"  [OK] {t} ex.{ex} : montant {m!r}, date {d}, note conservee "
              f"et completee ({len(note)} caracteres)")
    print(f"  [OK] {CIBLE} : {nb_relu} lignes, {len(bougees)} ligne(s) ecrite(s), "
          f"empreinte apres {sha256(relu)[:16]}...")

    print("\nARBITRAGE APPLIQUE. Le montant de NSBC 2025 n'est PAS ecrit ici : "
          "il est complete par collecte/charger_dividendes_boc.py a la prochaine "
          "reconstruction, sous sa garde de date identique des deux cotes.")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(autotest())
    sys.exit(main())
