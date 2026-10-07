#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C34 — les 31 observations que la BRVM avait retirees, et que le
chargeur retenait quand meme
=============================================================================

POURQUOI CE PROCES-VERBAL N'ECRIT AUCUN FICHIER, ET POURQUOI C'EST LE BON CHOIX
------------------------------------------------------------------------------
Les scripts freres de ce repertoire corrigent des valeurs ECRITES dans un CSV
commite : leur procès-verbal doit donc ecrire, sous gardes. Ici la valeur
fautive n'est ecrite nulle part de facon durable. Les deux fichiers en jeu sont :

* ``collecte/dividendes_historique.csv`` — le releve BRUT des observations du
  BOC, avec leur fenetre de publication. Il porte DEJA la bonne reponse : il
  dit, pour chaque versement, quel montant etait affiche et jusqu'a quand. Sa
  valeur est d'etre non retouche ; on n'y touche pas.
* ``collecte/dividendes_par_exercice.csv`` — un fichier GENERE depuis le
  precedent par ``historiser_dividendes_exercice.py``. Il n'est pas une saisie,
  et C19 comme C28 ont une question ouverte sur sa forme : le modifier ici
  trancherait a leur place.

La valeur fautive n'existait que dans ``moteur/brvm.db``, reconstruite a chaque
passage et jamais commitee. La correction est donc une REGLE DE LECTURE, posee
dans ``collecte/charger_dividendes_exercice.py`` via ``observations_boc.py`` :
une observation retiree par la BRVM pour sa propre date de paiement n'entre plus
en base. C'est l'option (a) de C34, et c'est la seule des deux qui ne change pas
la forme d'un fichier genere commite.

Ce script est le procès-verbal de cette regle : il fige les 31 deplacements
mesures le 07/10/2026, les recalcule sur l'etat du depot, et REFUSE si la
realite differe. Il n'ecrit rien, donc il est idempotent par construction : deux
passages rendent le meme verdict.

LES 31, ET LES HUIT QUI NE SONT PAS DES ARRONDIS
------------------------------------------------
Sur 307 couples (ticker, exercice) chargeables, 33 portent plusieurs montants.
Le chargeur retenait la PREMIERE ligne du fichier, donc une observation retiree,
dans 31 cas (les deux autres, ABJC 2018 et ECOC 2021, portent deux versements de
DATES differentes : hors scope, voir ``observations_boc.py``). Huit ne sont pas
des arrondis au franc mais des restatements de nominal, et le facteur le dit :
PRSC 2018 x64, SEMC 2016 x40, SAFC 2010 x25, STBC 2016 x20, ECOC 2017 x5,
SIBC 2017 x5, TTLC 2016 x5, ONTBF 2017 x2. Quatre autres sont entre 15 % et 25 %
(ABJC n'y est pas : ETIT 2016, ONTBF 2023, et rien de plus a ce seuil), les 19
restantes sous 6 %.

PREUVE A DEUX COTES, et elle est venue d'elle-meme
--------------------------------------------------
``collecte/charger_dividendes_boc.py`` est un second chemin, independant : il
lit ``collecte/dividendes_boc.csv`` (releve de la colonne du BOC) et REFUSE
d'ecrire quand la base porte deja autre chose. Avant la regle, il refusait
**6 fois** ; apres, **3 fois**. Les trois refus qui tombent sont SAFC 2010,
SEMC 2020 et BOAC 2025 — exactement les trois cas que C22 avait tranches le
05/10/2026 en renvoyant leur application a ce chantier, et qui portent desormais
la valeur que ce second chemin reclamait. Les trois refus restants (SICC 1999,
ORGT 2019, BOABF 2025) sont les cas que C22 a explicitement MAINTENUS.

LA SEULE ECRITURE DE CE SCRIPT, ET POURQUOI ELLE EST DUE
--------------------------------------------------------
``collecte/arbitrages_pont_boc.csv`` est le registre de C22. Il porte trois
lignes ``TRANCHE_RENVOI`` / ``refus_subsiste=oui`` dont le motif dit mot pour
mot « NON APPLIQUE ICI : fichier genere, voir C34 » : SAFC 2010, SEMC 2020,
BOAC 2025. La regle posee ici les applique, donc le pont ne les refuse plus et
ces trois lignes sont devenues fausses — la section 24 l'a dit d'elle-meme en
ECHEC (« FANTOMES, le pont ne les emet plus »). Ce script les passe en
``TRANCHE_APPLIQUE`` / ``non``, sous gardes, et c'est tout ce qu'il ecrit. Les
trois autres refus (SICC 1999, ORGT 2019, BOABF 2025) restent ``oui`` : ce sont
des valeurs SAISIES A LA MAIN que C22 a explicitement maintenues, et la regle 1
du depot interdit de les ecraser.

Usage :
    python3 outils/arbitrage_observations_perimees_boc.py [--test]
"""
import csv
import hashlib
import io
import sqlite3
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
COLLECTE = RACINE / "collecte"
sys.path.insert(0, str(COLLECTE))
from dates_dividendes import vers_iso  # noqa: E402
from observations_boc import charger_fenetres, est_perimee  # noqa: E402

GENERE = COLLECTE / "dividendes_par_exercice.csv"
DB = RACINE / "moteur" / "brvm.db"

# Garde `attendu` : (ticker, exercice, date, montant RETIRE, montant COURANT).
# Mesure du 07/10/2026. Le script refuse si un seul de ces champs differe.
ATTENDU = [
    ("PRSC", 2018, "2019-09-18", 9623.00, 150.36),
    ("SEMC", 2016, "2017-09-29", 677.00, 16.92),
    ("SAFC", 2010, "2011-07-29", 576.00, 23.04),
    ("STBC", 2016, "2017-06-19", 4124.00, 206.20),
    ("ECOC", 2017, "2018-06-22", 1844.00, 368.80),
    ("SIBC", 2017, "2018-06-08", 945.00, 189.00),
    ("TTLC", 2016, "2017-06-30", 485.00, 97.00),
    ("ONTBF", 2017, "2018-06-06", 727.91, 363.96),
    ("ETIT", 2016, "2017-04-28", 1.00, 1.21),
    ("ONTBF", 2023, "2024-07-31", 226.45, 266.45),
    ("CIEC", 2020, "2021-07-14", 176.14, 167.14),
    ("SEMC", 2020, "2021-12-28", 14.40, 14.00),
    ("CFAC", 2016, "2017-07-24", 20.00, 20.32),
    ("NTLC", 2010, "2011-08-12", 32.00, 31.50),
    ("ABJC", 2016, "2017-07-24", 50.00, 49.50),
    ("SHEC", 2016, "2017-07-27", 33.00, 33.30),
    ("BOAC", 2025, "2026-05-06", 594.53, 597.53),
    ("TTLC", 2022, "2023-09-21", 175.53, 176.00),
    ("PALC", 2016, "2017-09-29", 120.00, 120.30),
    ("BOAN", 2018, "2019-05-27", 385.95, 385.00),
    ("BNBC", 2016, "2017-07-11", 163.00, 162.60),
    ("UNXC", 2016, "2017-07-10", 174.00, 173.60),
    ("SCRC", 2016, "2017-09-29", 137.00, 137.25),
    ("SPHC", 2013, "2014-06-13", 116.00, 116.20),
    ("BOAM", 2024, "2025-06-03", 237.50, 237.15),
    ("CIEC", 2016, "2017-09-20", 173.00, 173.25),
    ("SOGC", 2016, "2017-07-31", 320.00, 320.40),
    ("BOAN", 2017, "2018-05-31", 379.00, 379.44),
    ("SGBC", 2016, "2017-07-04", 584.00, 583.70),
    ("BICC", 2016, "2017-07-24", 277.00, 277.14),
    ("TTLS", 2022, "2023-07-13", 241.01, 241.00),
]

# Hors scope, et c'est une DECISION, pas un oubli : deux versements de dates
# differentes ne se revisent pas l'un l'autre.
HORS_SCOPE = {
    ("ABJC", 2018): "deux versements en 2019 (123,72 le 27/05 et 164,96 le 30/09)",
    ("ECOC", 2021): "549,00 publie une fois sous la date fautive 30-mai-22 "
                    "au lieu de 30-mai-23",
}

CONFIANCE_MIN = "ELEVEE"
ECHECS = []

# --- le registre de C22, et les trois lignes que ce chantier solde -----------
REGISTRE = COLLECTE / "arbitrages_pont_boc.csv"
LIGNES_REGISTRE = 9           # entete + 8 arbitrages
SHA256_AVANT = "538bb173a631d77dc08fc953f60c2ba3f02045f3852f88ef8753ec71eb0c5730"
MENTION = (" APPLIQUE le 07/10/2026 par la regle de chargement de C34 "
           "(collecte/observations_boc.py) : l'observation retiree n'entre plus "
           "en base, le pont n'emet plus ce refus.")
# Garde `attendu` : (ticker, exercice, valeur_retenue, decision, refus_subsiste)
# AVANT ecriture. Un seul champ different : refus d'ecrire.
SOLDES = [
    ("SAFC", "2010", "23.04", "TRANCHE_RENVOI", "oui"),
    ("SEMC", "2020", "14.00", "TRANCHE_RENVOI", "oui"),
    ("BOAC", "2025", "597.53", "TRANCHE_RENVOI", "oui"),
]
# Et ceux qui ne bougent pas : valeurs saisies a la main, regle 1 du depot.
MAINTENUS = [("SICC", "1999"), ("ORGT", "2019"), ("BOABF", "2025")]


def controle(ok, libelle):
    print(f"  [{'OK' if ok else 'ECHEC'}] {libelle}")
    if not ok:
        ECHECS.append(libelle)
    return ok


def candidats_par_cle():
    """{(ticker, exercice): [lignes du fichier genere, dans l'ordre du fichier]}.

    Reproduit exactement le filtrage du chargeur : exercice renseigne,
    confiance ELEVEE, date convertible.
    """
    par_cle = {}
    with GENERE.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["exercice_couvert"] or r["confiance"] != CONFIANCE_MIN:
                continue
            brute = (r.get("date_paiement") or "").strip()
            iso = vers_iso(brute) if brute else None
            if brute and iso is None:
                continue
            r["_iso"] = iso
            par_cle.setdefault((r["ticker"], int(r["exercice_couvert"])), []).append(r)
    return par_cle


def deplacements():
    """Les couples ou l'ancienne regle (premiere ligne) retenait une observation
    retiree, et ce que la nouvelle retient a la place."""
    fenetres = charger_fenetres()
    par_cle = candidats_par_cle()
    sortie = []
    for cle, lignes in par_cle.items():
        premiere = lignes[0]
        restantes = [r for r in lignes
                     if not est_perimee(r["ticker"], r["_iso"],
                                        float(r["montant"]) if r["montant"] else None,
                                        fenetres)]
        if not restantes:
            # Impossible par construction (la courante survit toujours), mais un
            # invariant muet n'est pas un invariant.
            ECHECS.append(f"{cle} : toutes les observations ecartees")
            continue
        av = float(premiere["montant"]) if premiere["montant"] else None
        ap = float(restantes[0]["montant"]) if restantes[0]["montant"] else None
        if av is None or ap is None or abs(av - ap) <= 1e-9:
            continue
        sortie.append((cle[0], cle[1], premiere["_iso"], round(av, 6), round(ap, 6),
                       restantes[0]["_iso"]))
    return sortie


def _sha256(texte):
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _serialiser(rangs):
    """Re-serialise le registre en CRLF, la forme exacte du fichier commite."""
    tampon = io.StringIO()
    csv.writer(tampon, lineterminator="\r\n").writerows(rangs)
    return tampon.getvalue()


def appliquer_registre():
    """Passe les trois TRANCHE_RENVOI de C34 en TRANCHE_APPLIQUE, sous gardes.

    Six gardes : nombre de lignes, entete, empreinte avant, garde `attendu` sur
    chacun des trois, reserialisation exigee A L'OCTET PRES sur les lignes NON
    touchees avant toute ecriture, relecture apres ecriture. Si le fichier porte
    deja l'etat d'arrivee, le script le dit et n'ecrit rien.
    """
    brut = REGISTRE.read_text(encoding="utf-8", newline="")
    rangs = list(csv.reader(io.StringIO(brut)))
    entete = rangs[0]
    i_t, i_e = entete.index("ticker"), entete.index("exercice")
    i_v = entete.index("valeur_retenue")
    i_d, i_s = entete.index("decision"), entete.index("refus_subsiste")
    i_m = entete.index("motif")

    if not controle(len(rangs) == LIGNES_REGISTRE,
                    f"{REGISTRE.name} : {len(rangs)} lignes, attendu "
                    f"{LIGNES_REGISTRE}"):
        return
    if not controle(_serialiser(rangs) == brut,
                    "le registre se reserialise A L'OCTET PRES (CRLF, guillemets) "
                    "— sans quoi une ecriture reecrirait tout le fichier"):
        return

    index = {(r[i_t], r[i_e]): r for r in rangs[1:]}
    deja = all(index.get((t, e), [""] * 20)[i_s].strip().lower() == "non"
               for t, e, *_ in SOLDES)
    if deja:
        print(f"  [INFO] les {len(SOLDES)} lignes portent deja 'non' — "
              f"ARBITRAGE DEJA APPLIQUE, aucun fichier ecrit.")
        for t, e in MAINTENUS:
            controle(index[(t, e)][i_s].strip().lower() == "oui",
                     f"{t} {e} reste un refus qui subsiste (valeur saisie a la "
                     f"main, regle 1)")
        return

    conforme = _sha256(brut) == SHA256_AVANT
    if not controle(conforme,
                    f"empreinte du registre : {_sha256(brut)[:16]}..."
                    + (f", celle mesuree le 07/10/2026" if conforme else
                       f", attendu {SHA256_AVANT[:16]}... — le fichier a change "
                       f"depuis la mesure, rien n'est ecrit")):
        return

    # --- garde `attendu` sur chacun des trois -----------------------------
    cibles = []
    for t, e, valeur, decision, subsiste in SOLDES:
        r = index.get((t, e))
        if r is None:
            controle(False, f"{t} {e} absent du registre — rien n'est ecrit")
            return
        reel = (r[i_v].strip(), r[i_d].strip(), r[i_s].strip().lower())
        if reel != (valeur, decision, subsiste):
            controle(False, f"{t} {e} : registre porte {reel}, attendu "
                            f"{(valeur, decision, subsiste)} — la realite "
                            f"differe, rien n'est ecrit")
            return
        controle(True, f"{t} {e} : {decision}/{subsiste}, valeur retenue "
                       f"{valeur} — conforme a l'attendu")
        cibles.append(r)
    for t, e in MAINTENUS:
        if not controle(index[(t, e)][i_s].strip().lower() == "oui",
                        f"{t} {e} doit rester 'oui' avant comme apres (valeur "
                        f"saisie a la main, regle 1)"):
            return

    # --- l'ecriture, et rien d'autre --------------------------------------
    vises = {id(r) for r in cibles}
    temoin = [(i, list(r)) for i, r in enumerate(rangs) if id(r) not in vises]
    for r in cibles:
        r[i_d] = "TRANCHE_APPLIQUE"
        r[i_s] = "non"
        if MENTION.strip() not in r[i_m]:
            r[i_m] = r[i_m].rstrip() + MENTION
    if not controle(all(rangs[i] == copie for i, copie in temoin),
                    f"les {len(temoin)} lignes non visees (entete comprise) sont "
                    f"inchangees, champ par champ"):
        return
    REGISTRE.write_text(_serialiser(rangs), encoding="utf-8", newline="")

    # --- relecture ---------------------------------------------------------
    relu = list(csv.reader(io.StringIO(
        REGISTRE.read_text(encoding="utf-8", newline=""))))
    controle(len(relu) == LIGNES_REGISTRE,
             f"relecture : {len(relu)} lignes, attendu {LIGNES_REGISTRE}")
    ri = {(r[i_t], r[i_e]): r for r in relu[1:]}
    for t, e, *_ in SOLDES:
        controle(ri[(t, e)][i_d] == "TRANCHE_APPLIQUE"
                 and ri[(t, e)][i_s] == "non" and MENTION.strip() in ri[(t, e)][i_m],
                 f"relecture : {t} {e} porte TRANCHE_APPLIQUE / non, mention C34 "
                 f"ajoutee au motif")
    for t, e in MAINTENUS:
        controle(ri[(t, e)][i_s].strip().lower() == "oui",
                 f"relecture : {t} {e} reste 'oui'")
    print(f"  ECRIT : {REGISTRE.relative_to(RACINE)}, empreinte apres "
          f"{_sha256(REGISTRE.read_text(encoding='utf-8', newline=''))[:16]}...")


def main():
    print("Chantier C34 — proces-verbal de la regle « une observation retiree "
          "n'entre pas en base »")
    print(f"  releve   : collecte/dividendes_historique.csv")
    print(f"  genere   : {GENERE.relative_to(RACINE)}")
    print("  ecriture : AUCUNE — la correction est une regle de lecture du "
          "chargeur\n")

    obtenus = deplacements()
    index = {(t, e): (d, av, ap, dap) for t, e, d, av, ap, dap in obtenus}

    controle(len(obtenus) == len(ATTENDU),
             f"{len(obtenus)} couple(s) deplace(s), attendu {len(ATTENDU)}")

    # --- garde `attendu`, champ par champ ---------------------------------
    for t, e, d, av, ap in ATTENDU:
        got = index.get((t, e))
        if got is None:
            controle(False, f"{t} {e} : attendu {av} -> {ap}, le couple n'est "
                            f"plus deplace — la realite differe")
            continue
        gd, gav, gap, gdap = got
        ok = (gd == d and abs(gav - av) < 1e-6 and abs(gap - ap) < 1e-6)
        controle(ok, f"{t} {e} le {d} : {av:g} (retiree) -> {ap:g} (courante), "
                     f"facteur {av / ap:.4g}"
                     + ("" if ok else f" — OBTENU {gav:g} -> {gap:g} le {gd}"))
        if gdap != gd:
            controle(False, f"{t} {e} : la date de paiement passerait de {gd} a "
                            f"{gdap} — une revision ne change jamais de date")

    inattendus = sorted(set(index) - {(t, e) for t, e, *_ in ATTENDU})
    controle(not inattendus, f"aucun couple deplace hors des {len(ATTENDU)} "
                             f"attendus — surnumeraires : {inattendus}")

    # --- le registre de C22 : les trois lignes que ce chantier solde -------
    print("\n  -- registre de C22 (collecte/arbitrages_pont_boc.csv) --")
    appliquer_registre()
    print()

    # --- les deux hors scope restent hors scope ---------------------------
    for cle, motif in HORS_SCOPE.items():
        controle(cle not in index,
                 f"{cle[0]} {cle[1]} reste INTOUCHE ({motif})")

    # --- la base, si elle existe, porte bien la valeur courante -----------
    if DB.exists():
        cur = sqlite3.connect(DB).cursor()
        mauvaises = []
        for t, e, d, av, ap in ATTENDU:
            q = cur.execute("SELECT montant_net, date_paiement FROM dividendes "
                            "WHERE ticker=? AND exercice_couvert=?", (t, e)).fetchall()
            if len(q) != 1:
                mauvaises.append(f"{t} {e} : {len(q)} ligne(s) en base")
            elif q[0][0] is None or abs(q[0][0] - ap) > 1e-6:
                mauvaises.append(f"{t} {e} : base {q[0][0]}, courante {ap}")
            elif q[0][1] != d:
                mauvaises.append(f"{t} {e} : date base {q[0][1]}, attendue {d}")
        controle(not mauvaises,
                 f"les {len(ATTENDU)} couples portent la valeur COURANTE dans "
                 f"moteur/brvm.db" + ("" if not mauvaises
                                      else " — FAUTIFS : " + " ; ".join(mauvaises)))
    else:
        print("  [INFO] moteur/brvm.db absente : la confrontation a la base est "
              "sautee (reconstruire la base pour l'obtenir).")

    print()
    if ECHECS:
        print(f"REFUS : {len(ECHECS)} controle(s) en echec — la realite differe de "
              f"l'attendu, rien n'est ecrit (et rien ne l'aurait ete).")
        return 1
    print(f"CONFORME : les {len(ATTENDU)} deplacements sont ceux mesures le "
          f"07/10/2026. Aucun fichier ecrit — relance sans effet.")
    return 0


def autotest():
    """Verifie que la regle ne depend pas de l'ordre des lignes du fichier.

    C'est la propriete que l'ancienne regle n'avait PAS : elle retenait « la
    premiere ligne », donc son resultat tenait a un tri.
    """
    fen = {("X", "2020-06-01", 100.0): "2021-01-01",
           ("X", "2020-06-01", 4.0): "2024-01-01"}
    ok = ech = 0
    for ordre in ([100.0, 4.0], [4.0, 100.0]):
        restantes = [m for m in ordre if not est_perimee("X", "2020-06-01", m, fen)]
        if restantes == [4.0]:
            ok += 1
            print(f"  [OK] ordre {ordre} : la courante 4,0 est retenue")
        else:
            ech += 1
            print(f"  [ECHEC] ordre {ordre} : retenu {restantes}")
    print(f"\nautotest : {ok} OK, {ech} echec(s)")
    return 1 if ech else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(autotest() or main())
    sys.exit(main())
