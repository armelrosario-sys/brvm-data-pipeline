#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C27 — le mnemonique officiel de Bridge Bank Group CI est BBGC
========================================================================

Ce que ce script tranche
------------------------
``donnees/base/societes.csv`` porte ``BBGCI`` depuis le 10/07/2026, et sa
propre note dit pourquoi :

    Ticker "BBGCI" provisoire (non confirme par mnemonique officiel BRVM,
    ISIN CI0000010609 connu) [...] A RECONFIRMER des qu'un avis BRVM
    officiel de premiere cotation sera publie.

L'avis a ete publie. La note demandait cette passe ; ce script la fait.

La preuve, a deux cotes, et les deux cotes sont la BRVM elle-meme
------------------------------------------------------------------
1. **L'avis de premiere cotation**, collecte dans ``collecte/avis_brvm.csv``
   le 25/09/2026, s'intitule mot pour mot :
   ``Resultats de premiere cotation - BRIDGE BANK GROUP COTE D'IVOIRE (BBGC)``.
   C'est exactement le document que la note de ``societes.csv`` attendait.
2. **La page « Volumes / Valeurs »**, relevee le 02/10/2026 par C25
   (``collecte/releve_volumes.csv``), publie ``BBGC`` sur les 48 lignes de la
   cote, avec ``connu_en_base=non`` faute de correspondance en base.

Deux confirmations de plus, qui ne sont pas la preuve mais la corroborent :
le bulletin officiel de la cote n(deg) 186 du 01/10/2026
(``donnees/boc.json``) porte le symbole ``BBGC`` avec un cours de cloture de
8 800 FCFA, et ``donnees/cote_reference.json`` nomme 48 titres dont ``BBGC``.

Pourquoi ce n'est pas cosmetique
---------------------------------
Mesure du 04/10/2026 (cycle 19), avant ecriture : **Bridge Bank est la seule
societe reelle de la base sans aucun cours** — 5 exercices fondamentaux, 0
ligne dans ``cours_mensuels``, 0 dans ``cours_quotidien_boc``, et **aucune
entree dans ``collecte/profils.json``**, qui n'en compte que 47. Pendant ce
temps le depot detient deja, **sous le nom BBGC**, 7 seances de valeur
transigee dans ``collecte/historique_liquidite.json`` (24/09 -> 02/10/2026),
une ligne de bulletin complete dans ``donnees/boc.json`` et un cours de
reference dans ``donnees/cote_reference.json``. Les deux moities du titre
existent et ne se rencontrent jamais, parce qu'elles ne portent pas le meme
nom.

``moteur/arbitrage.py`` avait pose un pansement sur ce point --
``ALIAS_TICKERS = {"BBGC": "BBGCI"}`` -- qui tranchait dans le mauvais sens :
il faisait du mnemonique officiel l'alias du provisoire. Le renommage le rend
inutile ; il est vide dans le meme commit.

Ce que ce script NE renomme PAS, et pourquoi
---------------------------------------------
``collecte/fondamentaux_echecs.jsonl`` porte une ligne ``"ticker": "BBGCI"``
dont le ``nom_fichier`` est
``...rapport_dactivites_-_3eme_trimestre_2024_-_bank_of_africa_bf.pdf`` : un
document de **BOA Burkina Faso**, pas de Bridge Bank. C'est la famille de
**C29** (« quinze extractions portent le ticker d'une autre societe que celle
du document »). Renommer cette ligne reviendrait a porter plus loin une
attribution fausse. Elle reste telle quelle, et c'est C29 qui la tranchera.

Gardes
------
Six, toutes verifiees a l'execution et non pas seulement ecrites ici :
entete et nombre de lignes de chaque fichier, empreinte SHA-256 **avant**,
nombre exact d'occurrences attendu de chaque ancre (assertion d'unicite ou de
cardinalite), interdiction d'ecrire si ``BBGC`` est deja present la ou il ne
devrait pas l'etre, relecture apres ecriture, et constat d'idempotence : une
seconde execution ne fait rien et le dit.

Usage : ``python3 outils/migration_ticker_bbgci_vers_bbgc.py``
        ``python3 outils/migration_ticker_bbgci_vers_bbgc.py --test``
"""

import csv
import hashlib
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ANCIEN = "BBGCI"
NOUVEAU = "BBGC"

# Etat des fichiers AVANT migration, mesure le 04/10/2026 (cycle 19). Le script
# s'arrete si la realite en differe : c'est ce qui empeche d'ecrire dans un
# fichier qui a change de forme ou de taille depuis la redaction de celui-ci.
#
# chemin -> (entete attendu, nb de lignes avec entete, sha256 avant,
#            ancre a remplacer, remplacement, nb d'occurrences attendu)
CIBLES = [
    {
        "chemin": "donnees/base/societes.csv",
        "entete": "ticker,nom,secteur,referentiel,pays,compartiment,actionnariat,note",
        "lignes": 51,
        "sha256_avant": "8419fb6f9a49d426b8ea7614e8676e7ecae6f35a252948f6ef8e5cd9da66af3e",
        "ancre": "BBGCI,",
        "remplacement": "BBGC,",
        "occurrences": 1,
        "debut_de_ligne": True,
    },
    {
        "chemin": "donnees/base/etats_financiers.csv",
        "entete": None,  # entete long, non fige ici : le nb de colonnes suffit
        "lignes": 186,
        "sha256_avant": "1a9752eaaf38495f5fd138564c097be1eca55b7e146fb0caa546ac044b9cf537",
        "ancre": "BBGCI,",
        "remplacement": "BBGC,",
        "occurrences": 5,
        "debut_de_ligne": True,
    },
    {
        "chemin": "donnees/base/source_urls.csv",
        "entete": "ticker,exercice,source_url,note",
        "lignes": 168,
        "sha256_avant": "f24e4ea401ba41bbece2ebf1bad0861a8ef83299b0fac3b364819ece8bfe6796",
        "ancre": "BBGCI,",
        "remplacement": "BBGC,",
        "occurrences": 5,
        "debut_de_ligne": True,
    },
    {
        "chemin": "collecte/avis_brvm.csv",
        "entete": "date_avis,rubrique,type,ticker,critique,titre,url,date_collecte",
        "lignes": 141,
        "sha256_avant": "e20e221415662d5d2003ea70b498c76b3ce4191dfa45223ae3af5d98dcfb7ca5",
        # Ancre plus large que le simple ticker : la colonne 4 d'une ligne
        # PREMIERE_COTATION. Le titre de l'avis contient deja « (BBGC) », on ne
        # veut surtout pas y toucher.
        "ancre": ",PREMIERE_COTATION,BBGCI,",
        "remplacement": ",PREMIERE_COTATION,BBGC,",
        "occurrences": 2,
        "debut_de_ligne": False,
    },
]

# La note de societes.csv n'est PAS ecrasee : la regle du depot interdit
# d'effacer une note qui documente une analyse humaine. La phrase d'origine
# reste mot pour mot -- elle dit l'etat de la connaissance au 10/07/2026 -- et
# la confirmation est AJOUTEE derriere, datee et sourcee.
NOTE_ANCRE = ("AUCUNE donnee cours_mensuels (le prix d'offre 6750 FCFA n'est PAS "
              "un cours de marche, ne jamais l'utiliser comme tel).")

NOTE_AJOUT = (
    " MNEMONIQUE CONFIRME le 04/10/2026 (cycle 19, chantier C27) : le mnemonique "
    "officiel est BBGC, et non BBGCI. Preuve a deux cotes, toutes deux publiees "
    "par la BRVM -- l'avis de premiere cotation du 25/09/2026, collecte dans "
    "collecte/avis_brvm.csv, s'intitule 'Resultats de premiere cotation - BRIDGE "
    "BANK GROUP COTE D'IVOIRE (BBGC)' ; et la page Volumes / Valeurs relevee le "
    "02/10/2026 (collecte/releve_volumes.csv) publie BBGC sur les 48 lignes de la "
    "cote. Corrobore par le bulletin officiel de la cote n(deg) 186 du 01/10/2026 "
    "(donnees/boc.json, symbole BBGC, cloture 8800) et par donnees/cote_reference.json "
    "(48 titres). Renommage porte par outils/migration_ticker_bbgci_vers_bbgc.py ; "
    "la phrase qui precede est conservee telle quelle, elle dit ce qu'on savait "
    "avant cette date. Premiere cotation effective le 24/09/2026 (BOC n(deg) 181)."
)

# Marqueur d'idempotence : present dans la note, la migration est deja faite.
NOTE_MARQUEUR = "MNEMONIQUE CONFIRME le 04/10/2026"


def sha256(texte):
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def lire(chemin):
    with open(os.path.join(RACINE, chemin), encoding="utf-8", newline="") as f:
        return f.read()


def ecrire(chemin, texte):
    with open(os.path.join(RACINE, chemin), "w", encoding="utf-8", newline="") as f:
        f.write(texte)


def occurrences(texte, ancre, debut_de_ligne):
    if not debut_de_ligne:
        return texte.count(ancre)
    return sum(1 for l in texte.split("\n") if l.startswith(ancre))


def remplacer(texte, ancre, remplacement, debut_de_ligne):
    if not debut_de_ligne:
        return texte.replace(ancre, remplacement)
    lignes = texte.split("\n")
    return "\n".join(remplacement + l[len(ancre):] if l.startswith(ancre) else l
                     for l in lignes)


def nb_colonnes(texte):
    """Nombre de colonnes par ligne, vu par l'analyseur CSV. Sert a prouver
    qu'aucune virgule n'a ete ajoutee ou perdue par le remplacement."""
    lignes = list(csv.reader(io.StringIO(texte)))
    return sorted({len(l) for l in lignes if l})


def echec(message):
    print(f"  [REFUS] {message}")
    print("\nMIGRATION ABANDONNEE — aucun fichier n'a ete ecrit.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Autotest : la mecanique de remplacement, sur des chaines fabriquees.
# ---------------------------------------------------------------------------

CAS_TEST = [
    # (texte, ancre, remplacement, debut_de_ligne, occurrences, resultat)
    ("BBGCI,a\nBBGCIX,b\nxBBGCI,c\n", "BBGCI,", "BBGC,", True, 1,
     "BBGC,a\nBBGCIX,b\nxBBGCI,c\n"),
    # Le piege que le prefixe simple ne voit pas : BBGCIX commence par BBGCI
    # mais n'est pas BBGCI. La virgule de l'ancre est ce qui l'ecarte.
    ("BBGCIX,b\n", "BBGCI,", "BBGC,", True, 0, "BBGCIX,b\n"),
    # Une occurrence en milieu de ligne n'est PAS touchee en mode debut de ligne.
    ("x,BBGCI,y\n", "BBGCI,", "BBGC,", True, 0, "x,BBGCI,y\n"),
    # Mode colonne : l'ancre large ne touche que la colonne visee.
    ("2026-09-25,AVIS,PREMIERE_COTATION,BBGCI,non,titre (BBGC),u,d\n",
     ",PREMIERE_COTATION,BBGCI,", ",PREMIERE_COTATION,BBGC,", False, 1,
     "2026-09-25,AVIS,PREMIERE_COTATION,BBGC,non,titre (BBGC),u,d\n"),
    # Idempotence : relance sur le resultat, zero occurrence, texte inchange.
    ("BBGC,a\n", "BBGCI,", "BBGC,", True, 0, "BBGC,a\n"),
    # Deux occurrences, les deux remplacees.
    ("BBGCI,1\nBBGCI,2\n", "BBGCI,", "BBGC,", True, 2, "BBGC,1\nBBGC,2\n"),
]


def autotest():
    n_ok = n_ko = 0
    for i, (txt, anc, rem, dl, n_att, attendu) in enumerate(CAS_TEST, 1):
        n = occurrences(txt, anc, dl)
        res = remplacer(txt, anc, rem, dl)
        ok = (n == n_att and res == attendu)
        print(f"  [{'OK' if ok else 'ECHEC'}] cas {i} : {n} occurrence(s) "
              f"(attendu {n_att})")
        if not ok:
            print(f"        obtenu  : {res!r}")
            print(f"        attendu : {attendu!r}")
            n_ko += 1
        else:
            n_ok += 1
    # Le remplacement ne doit jamais changer le nombre de lignes.
    for txt, anc, rem, dl, _n, _a in CAS_TEST:
        if remplacer(txt, anc, rem, dl).count("\n") != txt.count("\n"):
            print("  [ECHEC] le remplacement a change le nombre de lignes")
            n_ko += 1
        else:
            n_ok += 1
    # L'ajout a la note est idempotent par son marqueur.
    note = "fin de phrase." + NOTE_AJOUT
    if NOTE_MARQUEUR in note:
        n_ok += 1
        print("  [OK] marqueur d'idempotence present dans l'ajout de note")
    else:
        n_ko += 1
        print("  [ECHEC] marqueur d'idempotence absent de l'ajout de note")
    print(f"\n{n_ok} controle(s) OK, {n_ko} echec(s)")
    return 0 if n_ko == 0 else 1


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def main():
    print("Migration C27 — mnemonique BBGCI -> BBGC")
    print("=" * 60)

    textes_avant = {}
    etat = []  # "a_faire" | "deja_fait"
    for cible in CIBLES:
        chemin = cible["chemin"]
        chemin_abs = os.path.join(RACINE, chemin)
        if not os.path.exists(chemin_abs):
            echec(f"{chemin} : fichier absent")
        txt = lire(chemin)
        textes_avant[chemin] = txt

        n = occurrences(txt, cible["ancre"], cible["debut_de_ligne"])
        n_apres = occurrences(txt, cible["remplacement"], cible["debut_de_ligne"])

        if n == cible["occurrences"] and n_apres == 0:
            etat.append("a_faire")
        elif n == 0 and n_apres == cible["occurrences"]:
            etat.append("deja_fait")
            print(f"  [DEJA] {chemin} : {n_apres} ligne(s) portent deja {NOUVEAU}")
            continue
        else:
            echec(f"{chemin} : {n} occurrence(s) de l'ancre et {n_apres} du "
                  f"remplacement — attendu {cible['occurrences']} et 0 (migration "
                  f"a faire) ou 0 et {cible['occurrences']} (deja faite). La "
                  f"realite ne correspond a aucun des deux etats connus.")

        # Gardes, seulement sur les fichiers a migrer.
        lignes = txt.count("\n") + (0 if txt.endswith("\n") else 1)
        if lignes != cible["lignes"]:
            echec(f"{chemin} : {lignes} lignes, attendu {cible['lignes']}")
        if cible["entete"] is not None:
            # collecte/avis_brvm.csv est en CRLF : on compare l'entete sans son
            # retour chariot, mais on n'y touche pas -- les fins de ligne du
            # fichier restent exactement ce qu'elles etaient.
            entete = txt.split("\n", 1)[0].rstrip("\r")
            if entete != cible["entete"]:
                echec(f"{chemin} : entete inattendu\n    obtenu  : {entete}\n"
                      f"    attendu : {cible['entete']}")
        h = sha256(txt)
        if h != cible["sha256_avant"]:
            echec(f"{chemin} : empreinte {h[:16]}..., attendu "
                  f"{cible['sha256_avant'][:16]}... — le fichier a change depuis "
                  f"la redaction de ce script")
        print(f"  [OK] {chemin} : {lignes} lignes, {n} ligne(s) a renommer, "
              f"empreinte conforme")

    note_a_faire = NOTE_MARQUEUR not in textes_avant.get(
        "donnees/base/societes.csv", lire("donnees/base/societes.csv"))

    if all(e == "deja_fait" for e in etat) and not note_a_faire:
        print("\nMigration DEJA APPLIQUEE — aucun fichier ecrit, rien a faire.")
        return 0

    # --- Ecriture -----------------------------------------------------------
    print("\nEcriture")
    print("-" * 60)
    total_lignes = 0
    for cible, e in zip(CIBLES, etat):
        if e == "deja_fait":
            continue
        chemin = cible["chemin"]
        avant = textes_avant[chemin]
        apres = remplacer(avant, cible["ancre"], cible["remplacement"],
                          cible["debut_de_ligne"])

        # Garde : seules les lignes visees changent, et rien d'autre.
        la, lb = avant.split("\n"), apres.split("\n")
        if len(la) != len(lb):
            echec(f"{chemin} : le remplacement a change le nombre de lignes")
        bougees = [i for i, (a, b) in enumerate(zip(la, lb)) if a != b]
        if len(bougees) != cible["occurrences"]:
            echec(f"{chemin} : {len(bougees)} ligne(s) modifiee(s), attendu "
                  f"{cible['occurrences']}")
        # Garde : le nombre de colonnes de chaque ligne est inchange.
        if nb_colonnes(avant) != nb_colonnes(apres):
            echec(f"{chemin} : le nombre de colonnes a change "
                  f"({nb_colonnes(avant)} -> {nb_colonnes(apres)})")
        # Garde : le seul changement est la longueur du ticker, 1 caractere.
        for i in bougees:
            if la[i].replace(ANCIEN, NOUVEAU, 1) != lb[i]:
                echec(f"{chemin} ligne {i + 1} : la modification ne se reduit "
                      f"pas au renommage du ticker")

        ecrire(chemin, apres)
        total_lignes += len(bougees)
        print(f"  [ECRIT] {chemin} : {len(bougees)} ligne(s), "
              f"{sha256(avant)[:12]} -> {sha256(apres)[:12]}")

    # --- Note de societes.csv ----------------------------------------------
    if note_a_faire:
        chemin = "donnees/base/societes.csv"
        avant = lire(chemin)
        if avant.count(NOTE_ANCRE) != 1:
            echec(f"{chemin} : l'ancre de la note apparait "
                  f"{avant.count(NOTE_ANCRE)} fois, attendu exactement 1")
        apres = avant.replace(NOTE_ANCRE, NOTE_ANCRE + NOTE_AJOUT, 1)
        la, lb = avant.split("\n"), apres.split("\n")
        if len(la) != len(lb):
            echec(f"{chemin} : l'ajout de note a change le nombre de lignes")
        bougees = [i for i, (a, b) in enumerate(zip(la, lb)) if a != b]
        if len(bougees) != 1:
            echec(f"{chemin} : {len(bougees)} ligne(s) touchee(s) par l'ajout "
                  f"de note, attendu 1")
        if nb_colonnes(avant) != nb_colonnes(apres):
            echec(f"{chemin} : l'ajout de note a change le nombre de colonnes")
        # L'ancienne phrase doit survivre mot pour mot.
        if NOTE_ANCRE not in apres:
            echec(f"{chemin} : la phrase d'origine a disparu de la note")
        ecrire(chemin, apres)
        print(f"  [ECRIT] {chemin} : note du ticker completee "
              f"({len(NOTE_AJOUT)} caracteres ajoutes, phrase d'origine conservee)")

    # --- Relecture ----------------------------------------------------------
    print("\nRelecture apres ecriture")
    print("-" * 60)
    total_bbgc = 0
    for cible in CIBLES:
        txt = lire(cible["chemin"])
        reste = occurrences(txt, cible["ancre"], cible["debut_de_ligne"])
        vu = occurrences(txt, cible["remplacement"], cible["debut_de_ligne"])
        if reste != 0 or vu != cible["occurrences"]:
            echec(f"{cible['chemin']} : apres ecriture, {reste} ancre(s) "
                  f"restante(s) et {vu} remplacement(s), attendu 0 et "
                  f"{cible['occurrences']}")
        total_bbgc += vu
        print(f"  [OK] {cible['chemin']} : {vu} ligne(s) en {NOUVEAU}, "
              f"0 reste de {ANCIEN}")
    note = lire("donnees/base/societes.csv")
    if NOTE_MARQUEUR not in note:
        echec("donnees/base/societes.csv : le marqueur de la note est absent "
              "apres ecriture")
    print(f"  [OK] donnees/base/societes.csv : marqueur de note present")

    print(f"\nMIGRATION APPLIQUEE — {total_bbgc} ligne(s) portent desormais "
          f"{NOUVEAU}, 0 reste de {ANCIEN} dans les fichiers vises.")
    print("Relancez ce script : il doit dire « DEJA APPLIQUEE » sans rien ecrire.")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(autotest())
    sys.exit(main())
