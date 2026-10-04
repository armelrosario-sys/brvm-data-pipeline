#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C21 — la colonne ``rendement`` du BOC quotidien n'a jamais eu une
seule convention
=============================================================================

Ce que le chantier C21 disait, et ce que la mesure du 04/10/2026 corrige
------------------------------------------------------------------------
C21 annoncait **29 seances sur 7 titres** portant un rendement multiplie par
cent, et concluait : « le defaut est LATENT ». La signature qu'il employait --
une seance dont le rendement vaut 50 a 200 fois celui de la veille ET celui du
lendemain, a cours quasi constant -- rend aujourd'hui **136** seances, et elle
ne mesure pas le defaut : elle mesure les FRONTIERES entre deux conventions qui
coexistent dans le fichier depuis l'origine.

Le fichier ``collecte/cours_quotidien_boc.csv`` melange en effet deux unites,
et ce n'est pas une surprise : le docstring de ``_rendement_normalise`` dans
``collecte/charger_cours_quotidien.py`` l'ecrit noir sur blanc depuis le
12/09/2026. Ce que personne n'avait compte, c'est la proportion.

Mesure du 04/10/2026, ligne a ligne, par la preuve a deux cotes :

  * **68 426 lignes** sont en POURCENTAGE (``6.28`` pour 6,28 %) ;
  * **5 370 lignes** sont en FRACTION (``0.0628`` pour le meme 6,28 %) ;
  * **1 756 lignes** ne se tranchent par aucun des deux cotes et restent
    telles quelles, nommees dans le rapport.

Les lignes en fraction sont exactement les **101 dates mensuelles** versees par
C15 plus les **52 seances depuis le 2026-07-17**, ou la collecte quotidienne
P11 ecrit desormais la fraction. Tout le reste de la serie est en pourcentage.

Le defaut n'est pas dans la donnee, il est dans la facon de la lire
---------------------------------------------------------------------
Le moteur veut une FRACTION : ``moteur/profils.py`` l'ecrit sur la ligne meme
(``dy = dy_row[0]  # fraction (0,056 = 5,6 %)``). Le pont
``charger_cours_quotidien.py`` arbitre donc entre les deux unites, et il
arbitre **par la grandeur** : au-dessus de 1,5, c'est un pourcentage, on divise
par cent ; en dessous, c'est deja une fraction, on n'y touche pas.

C'est une estimation, et la premiere regle du depot l'interdit. Elle est de
surcroit mesurablement fausse : **1 683 lignes** sont en pourcentage avec une
valeur inferieure ou egale a 1,5 -- un rendement publie sous 1,5 % -- et
entrent donc dans la base **cent fois trop grandes**. Elles portent sur 11
tickers : ORGT 403, NSBC 291, CFAC 211, UNXC 184, BICC 174, PALC 150, SEMC 121,
SPHC 91, SCRC 33, SLBC 17, ETIT 8. Une ligne de plus, ``STBC 2018-08-01``
(206,2 %), franchit le seuil haut apres division (2,062 > 1,5) et est
**silencieusement remplacee par une case vide** -- et ce script la
laisse telle quelle, pour que la case reste vide plutot que de devenir fausse.

Ce que ce script fait
---------------------
Il ramene a la FRACTION les lignes dont la convention est PROUVEE des deux
cotes, et **ne touche a rien d'autre**. Apres son passage, toute ligne prouvee
porte la meme unite que le moteur attend, et le seuil de grandeur de
``_rendement_normalise`` n'a plus a arbitrer que le residu nomme.

La preuve a deux cotes, pour chaque ligne
------------------------------------------
Cote 1 -- **le dividende que le BOC publie lui-meme**. La colonne
``dividende_montant`` de ``collecte/cours_extraits.csv`` (bulletin mensuel)
donne le dividende en vigueur a la date de la seance. Le dividende implicite de
la ligne vaut ``rendement x cours`` en lecture fraction, ``rendement / 100 x
cours`` en lecture pourcentage. Une seule des deux retombe a moins de 5 % du
dividende publie ; c'est celle-la, et l'autre est ecartee.

Cote 2 -- **les seances qui l'encadrent**. Quand le mensuel ne tranche pas
(dividende absent, ou perime parce que la seance precede le premier bulletin
collecte), le dividende implicite des seances voisines DEJA tranchees sert de
reference : il est constant par morceaux dans la serie d'un titre, et les deux
lectures different d'un facteur cent exactement. Tolerance 10 %, mediane des
six voisines tranchees les plus proches.

Une ligne qu'aucun des deux cotes ne tranche n'est **pas** convertie. Une case
laissee en l'etat vaut mieux qu'une valeur devinee.

Les gardes
----------
1. entete exact et nombre de lignes attendu ;
2. empreinte SHA-256 du fichier AVANT, et APRES ;
3. comptes attendus sur chaque categorie (prouvees pourcentage, prouvees
   fraction, non tranchees, mal echelonnees par le chargeur) ;
4. conversion par decalage DECIMAL exact (``Decimal`` / 100), jamais par
   division flottante : ``2.61`` devient ``0.0261``, pas
   ``0.026099999999999998`` ;
5. aucune autre colonne, aucun autre caractere : le fichier est relu ligne a
   ligne en texte brut, fins de ligne CRLF conservees, et toute ligne non
   convertie doit ressortir **identique a l'octet** ;
6. relecture apres ecriture, et reclassement : apres application, plus aucune
   ligne prouvee ne doit etre en pourcentage.

Idempotent : relance sans effet, il constate « normalisation DEJA APPLIQUEE ».

Usage :
    python3 outils/normalisation_rendement_boc.py            # rapport, n'ecrit rien
    python3 outils/normalisation_rendement_boc.py --test     # autotest
    python3 outils/normalisation_rendement_boc.py --appliquer
"""

import bisect
import collections
import csv
import hashlib
import io
import os
import statistics
import sys
from decimal import Decimal, InvalidOperation

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIBLE = os.path.join(RACINE, "collecte", "cours_quotidien_boc.csv")
MENSUEL = os.path.join(RACINE, "collecte", "cours_extraits.csv")

ENTETE_ATTENDU = "ticker,date_bulletin,cours,per,rendement"
LIGNES_ATTENDUES = 90660            # hors entete
SHA_AVANT = "fc019ab4bd935cd7ae761ba11aa956f3b7eca6737d4982e8ef9b17b2ad349e59"

# Comptes mesures le 04/10/2026 (cycle 18), avant toute ecriture.
ATTENDU_RENSEIGNEES = 75552
ATTENDU_POURCENTAGE = 68426
ATTENDU_FRACTION = 5370
ATTENDU_NON_TRANCHEES = 1756
ATTENDU_MAL_ECHELONNEES = 1683      # pourcentage <= 1,5 : le chargeur ne divise pas
ATTENDU_HORS_PLAFOND = 1            # pourcentage > 150 : NON convertie, voir plus bas
ATTENDU_CONVERTIES = ATTENDU_POURCENTAGE - ATTENDU_HORS_PLAFOND

SEUIL_CHARGEUR = 1.5                # seuil de _rendement_normalise, pour le compte seul
TOL_MENSUEL = 0.05
TOL_VOISINES = 0.10
VOISINES = 3                        # de chaque cote


# --------------------------------------------------------------------------
# Lecture et classement
# --------------------------------------------------------------------------

def _flot(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v


def dividendes_mensuels(chemin=MENSUEL):
    """ticker -> [(date ISO, dividende publie)] trie. Cote 1 de la preuve."""
    table = collections.defaultdict(list)
    with open(chemin, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = (r.get("date_bulletin") or "").strip()
            m = _flot(r.get("dividende_montant"))
            if len(d) != 8 or m is None or m <= 0:
                continue
            table[r["ticker"]].append((f"{d[:4]}-{d[4:6]}-{d[6:8]}", m))
    for t in table:
        table[t].sort()
    return table


def dividende_en_vigueur(table, ticker, date):
    serie = table.get(ticker)
    if not serie:
        return None
    i = bisect.bisect_right([x[0] for x in serie], date) - 1
    return serie[i][1] if i >= 0 else None


def _depart(valeur, cours, reference, tolerance):
    """'P', 'F' ou None : laquelle des deux lectures ferme sur la reference."""
    if reference is None or reference <= 0:
        return None
    ecart_p = abs(valeur / 100.0 * cours / reference - 1)
    ecart_f = abs(valeur * cours / reference - 1)
    if ecart_p < tolerance <= ecart_f:
        return "P"
    if ecart_f < tolerance <= ecart_p:
        return "F"
    return None


def classer(lignes, table_mensuelle):
    """Rend {indice de ligne: 'P'|'F'}. Deux passes : mensuel, puis voisines."""
    verdict = {}
    # --- cote 1 : le dividende publie par le BOC
    for i, r in enumerate(lignes):
        v, c = _flot(r["rendement"]), _flot(r["cours"])
        if v is None or c is None or v <= 0 or c <= 0:
            continue
        d = dividende_en_vigueur(table_mensuelle, r["ticker"], r["date_bulletin"])
        verdict_i = _depart(v, c, d, TOL_MENSUEL)
        if verdict_i:
            verdict[i] = verdict_i

    # --- cote 2 : les seances qui l'encadrent
    par_ticker = collections.defaultdict(list)
    for i, r in enumerate(lignes):
        par_ticker[r["ticker"]].append(i)
    for ind in par_ticker.values():
        ind.sort(key=lambda i: lignes[i]["date_bulletin"])
        ancres = []
        for rang, i in enumerate(ind):
            if i not in verdict:
                continue
            v, c = _flot(lignes[i]["rendement"]), _flot(lignes[i]["cours"])
            if v is None or c is None:
                continue
            ancres.append((rang, v * c if verdict[i] == "F" else v / 100.0 * c))
        if not ancres:
            continue
        rangs = [a[0] for a in ancres]
        for rang, i in enumerate(ind):
            if i in verdict:
                continue
            v, c = _flot(lignes[i]["rendement"]), _flot(lignes[i]["cours"])
            if v is None or c is None or v <= 0 or c <= 0:
                continue
            j = bisect.bisect_left(rangs, rang)
            fenetre = [ancres[k][1]
                       for k in range(max(0, j - VOISINES), min(len(ancres), j + VOISINES))]
            if not fenetre:
                continue
            verdict_i = _depart(v, c, statistics.median(fenetre), TOL_VOISINES)
            if verdict_i:
                verdict[i] = verdict_i
    return verdict


def fraction_decimale(brut):
    """'2.61' -> '0.0261'. Decalage DECIMAL exact, jamais une division flottante."""
    try:
        d = Decimal(brut.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"valeur de rendement illisible : {brut!r}")
    return format(d / Decimal(100), "f")


# --------------------------------------------------------------------------
# Rapport et application
# --------------------------------------------------------------------------

def lire(chemin=CIBLE):
    with open(chemin, "rb") as f:
        octets = f.read()
    sha = hashlib.sha256(octets).hexdigest()
    texte = octets.decode("utf-8")
    brutes = texte.split("\r\n")
    if brutes and brutes[-1] == "":
        brutes.pop()
    entete = brutes[0]
    corps = brutes[1:]
    lignes = list(csv.DictReader(io.StringIO("\n".join([entete] + corps))))
    return sha, entete, corps, lignes


def rapport(verbeux=True):
    sha, entete, corps, lignes = lire()
    assert entete == ENTETE_ATTENDU, f"entete inattendu : {entete!r}"
    assert len(corps) == len(lignes) == LIGNES_ATTENDUES, \
        f"{len(corps)} lignes, {LIGNES_ATTENDUES} attendues"

    verdict = classer(lignes, dividendes_mensuels())
    c = collections.Counter()
    mal, perdues, non_tranchees = [], [], []
    for i, r in enumerate(lignes):
        v = _flot(r["rendement"])
        if v is None:
            c["vides"] += 1
            continue
        c["renseignees"] += 1
        g = verdict.get(i)
        if g == "P":
            c["pourcentage"] += 1
            if v / 100.0 > SEUIL_CHARGEUR:
                perdues.append((r["ticker"], r["date_bulletin"], v))
            elif v <= SEUIL_CHARGEUR:
                mal.append((r["ticker"], r["date_bulletin"], v))
        elif g == "F":
            c["fraction"] += 1
            if v > SEUIL_CHARGEUR:
                c["fraction_au_dessus_du_plafond"] += 1
        else:
            c["non_tranchees"] += 1
            non_tranchees.append((r["ticker"], r["date_bulletin"], v))

    if verbeux:
        print(f"SHA-256 du fichier       : {sha}")
        print(f"lignes                   : {len(lignes)}  "
              f"(renseignees {c['renseignees']}, vides {c['vides']})")
        print(f"  prouvees POURCENTAGE   : {c['pourcentage']}")
        print(f"  prouvees FRACTION      : {c['fraction']}")
        print(f"  non tranchees          : {c['non_tranchees']}")
        print(f"  mal echelonnees par le chargeur (pourcentage <= {SEUIL_CHARGEUR}) : {len(mal)}")
        print(f"  pourcentage au-dela du plafond du chargeur (> 150 %) : {len(perdues)}"
              " -- NON converties, le chargeur en fait une case vide des deux cotes")
        if perdues:
            print(f"      {perdues}")
        print("  fraction deja au-dela du plafond (> 1,5) : "
              f"{c['fraction_au_dessus_du_plafond']}")
        par_ticker = collections.Counter(t for t, _, _ in mal)
        if par_ticker:
            print(f"  tickers mal echelonnes : {par_ticker.most_common()}")
    return sha, entete, corps, lignes, verdict, c, mal, perdues, non_tranchees


def appliquer():
    sha, entete, corps, lignes, verdict, c, mal, perdues, _ = rapport()
    print()

    if c["pourcentage"] <= ATTENDU_HORS_PLAFOND:
        print("normalisation DEJA APPLIQUEE : aucune ligne prouvee n'est en pourcentage.")
        return 0

    # --- gardes d'etat initial
    assert sha == SHA_AVANT, (
        f"le fichier n'est pas celui mesure le 04/10/2026 (SHA {sha}) -- rien ecrit")
    for nom, obtenu, attendu in (
            ("renseignees", c["renseignees"], ATTENDU_RENSEIGNEES),
            ("pourcentage", c["pourcentage"], ATTENDU_POURCENTAGE),
            ("fraction", c["fraction"], ATTENDU_FRACTION),
            ("non tranchees", c["non_tranchees"], ATTENDU_NON_TRANCHEES),
            ("mal echelonnees", len(mal), ATTENDU_MAL_ECHELONNEES),
            ("hors plafond", len(perdues), ATTENDU_HORS_PLAFOND)):
        assert obtenu == attendu, f"{nom} : {obtenu} mesurees, {attendu} attendues -- rien ecrit"

    # --- reecriture ligne a ligne, en texte brut
    sorties, convertis = [], 0
    for i, brute in enumerate(corps):
        if verdict.get(i) != "P":
            sorties.append(brute)
            continue
        # Un rendement publie AU-DELA de 150 % ne se convertit pas : en fraction
        # il depasserait le plafond de _rendement_normalise, qui le diviserait
        # une seconde fois et ferait entrer en base une valeur FAUSSE la ou il
        # laisse aujourd'hui une CASE VIDE. Une case vide vaut mieux. Un seul
        # cas : STBC 2018-08-01, 206,2 % -- le dividende de 4 124 FCFA non
        # reajuste apres la division 1:20 du 27/07/2018 (voir C4).
        if _flot(lignes[i]["rendement"]) / 100.0 > SEUIL_CHARGEUR:
            sorties.append(brute)
            continue
        champs = brute.split(",")
        assert len(champs) == 5, f"ligne {i + 2} : {len(champs)} champs"
        assert champs[0] == lignes[i]["ticker"] and champs[1] == lignes[i]["date_bulletin"], \
            f"ligne {i + 2} : ancre (ticker, date) desalignee"
        ancien = champs[4]
        assert _flot(ancien) == _flot(lignes[i]["rendement"]), \
            f"ligne {i + 2} : valeur ATTENDUE {lignes[i]['rendement']!r}, lue {ancien!r}"
        champs[4] = fraction_decimale(ancien)
        # garde de valeur : le decalage decimal vaut exactement un centieme
        assert abs(float(champs[4]) * 100 - float(ancien)) < 1e-9 * max(1.0, abs(float(ancien))), \
            f"ligne {i + 2} : conversion non exacte {ancien!r} -> {champs[4]!r}"
        sorties.append(",".join(champs))
        convertis += 1

    assert convertis == ATTENDU_CONVERTIES, \
        f"{convertis} conversions, {ATTENDU_CONVERTIES} attendues -- rien ecrit"
    intacts = sum(1 for a, b in zip(corps, sorties) if a == b)
    assert intacts == LIGNES_ATTENDUES - convertis, \
        f"{intacts} lignes intactes, {LIGNES_ATTENDUES - convertis} attendues -- rien ecrit"

    texte = "\r\n".join([entete] + sorties) + "\r\n"
    with open(CIBLE, "wb") as f:
        f.write(texte.encode("utf-8"))

    # --- relecture apres ecriture
    sha2, entete2, corps2, lignes2 = lire()
    assert entete2 == ENTETE_ATTENDU and len(lignes2) == LIGNES_ATTENDUES
    verdict2 = classer(lignes2, dividendes_mensuels())
    reste = sum(1 for i, g in verdict2.items() if g == "P")
    assert reste == ATTENDU_HORS_PLAFOND, \
        f"apres ecriture, {reste} lignes prouvees restent en pourcentage"
    print(f"{convertis} lignes converties en fraction, "
          f"{LIGNES_ATTENDUES - convertis} intactes a l'octet.")
    print(f"SHA-256 apres : {sha2}")
    print(f"relecture : {reste} ligne prouvee encore en pourcentage (hors plafond, voulu), "
          f"{sum(1 for g in verdict2.values() if g == 'F')} en fraction.")
    return 0


# --------------------------------------------------------------------------
# Autotest
# --------------------------------------------------------------------------

def autotest():
    echecs = []

    def v(nom, obtenu, attendu):
        if obtenu != attendu:
            echecs.append(f"{nom} : {obtenu!r} au lieu de {attendu!r}")

    # decalage decimal exact, sans bruit flottant
    v("decimal 2.61", fraction_decimale("2.61"), "0.0261")
    v("decimal 6.28", fraction_decimale("6.28"), "0.0628")
    v("decimal 206.2", fraction_decimale("206.2"), "2.062")
    v("decimal 1.41", fraction_decimale("1.41"), "0.0141")
    v("decimal 0.0256999999999999997",
      fraction_decimale("0.0256999999999999997"), "0.000256999999999999997")
    try:
        fraction_decimale("abc")
        echecs.append("une valeur illisible aurait du lever")
    except ValueError:
        pass

    # depart des deux lectures
    v("depart pourcentage", _depart(6.28, 3285.0, 206.3, TOL_MENSUEL), "P")
    v("depart fraction", _depart(0.0628, 3285.0, 206.3, TOL_MENSUEL), "F")
    v("depart ambigu (les deux ferment)", _depart(1.0, 100.0, 50.0, 2.0), None)
    v("depart aucun", _depart(6.28, 3285.0, 1.0, TOL_MENSUEL), None)
    v("depart sans reference", _depart(6.28, 3285.0, None, TOL_MENSUEL), None)
    v("depart reference nulle", _depart(6.28, 3285.0, 0.0, TOL_MENSUEL), None)

    # FTSC ne doit JAMAIS etre balaye par un seuil de niveau : son 86,76 %
    # est reel (C1). En fraction il vaut 0,8676 et ferme sur son dividende.
    v("FTSC reel reste fraction", _depart(0.8676, 1985.0, 1722.2, TOL_MENSUEL), "F")
    v("FTSC publie en % reste pourcentage", _depart(86.98, 1985.0, 1726.6, TOL_MENSUEL), "P")

    # classement complet sur une serie synthetique : un titre dont la serie est
    # en pourcentage sauf une seance deja en fraction.
    lignes = [{"ticker": "XXX", "date_bulletin": f"2020-01-{j:02d}",
               "cours": "1000.0", "per": "10", "rendement": r}
              for j, r in zip(range(1, 6), ["5.0", "5.0", "0.05", "5.0", "5.0"])]
    table = {"XXX": [("2019-12-31", 50.0)]}
    g = classer(lignes, table)
    v("serie synthetique", [g.get(i) for i in range(5)], ["P", "P", "F", "P", "P"])

    # cote 2 seul : aucune reference mensuelle, les voisines tranchent
    lignes2 = [{"ticker": "YYY", "date_bulletin": f"2020-01-{j:02d}",
                "cours": "1000.0", "per": "10", "rendement": r}
               for j, r in zip(range(1, 6), ["5.0", "5.0", "5.0", "5.0", "5.0"])]
    v("sans reference, rien n'est tranche", classer(lignes2, {}), {})

    # une ligne sans cours ne se tranche pas
    v("sans cours", _depart(1.41, 0.0, 9.8, TOL_MENSUEL), None)

    print(f"autotest : {15 - len(echecs)} cas OK, {len(echecs)} echec(s)")
    for e in echecs:
        print("  [ECHEC]", e)
    return 1 if echecs else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(autotest())
    if "--appliquer" in sys.argv:
        sys.exit(appliquer())
    rapport()
    print("\n(rapport seul : rien n'a ete ecrit. --appliquer pour normaliser.)")
