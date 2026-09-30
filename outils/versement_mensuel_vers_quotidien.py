#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C15 — verser les seances du mensuel dans la serie quotidienne
========================================================================

Ce que ce script repare
-----------------------
La base porte DEUX extractions independantes des memes bulletins officiels :

  * ``collecte/cours_extraits.csv``      -> table ``cours_mensuels``
  * ``collecte/cours_quotidien_boc.csv`` -> table ``cours_quotidien_boc``

Mesure du 30/09/2026 (cycles 6 puis 8, deux fois) : elles ne partagent
**aucune date de bulletin**, 0 sur 101. Il n'existe donc pas une seule paire
(ticker, jour) commune, et leurs valeurs n'ont jamais pu etre confrontees --
alors que ce sont deux lectures du MEME document, la seule corroboration
gratuite dont le projet dispose sur les prix.

La cause est ecrite dans le code : ``collecte/backfill_boc_quotidien.py`` porte
depuis le 25/07/2026 une « LIMITE CONNUE, non corrigee » -- un BOC deja archive
par le collecteur mensuel n'est jamais reextrait vers le quotidien. Les 101
seances du mensuel sont donc exactement 101 des 355 jours ouvres absents du
quotidien.

Ce que ce script fait, et ne fait pas
-------------------------------------
Il verse les 4 509 lignes de ``cours_extraits.csv`` dans
``cours_quotidien_boc.csv``. **Sans reseau** : les donnees sont deja dans le
depot, il ne s'agit que de les mettre la ou elles peuvent servir. Il ne
retouche aucune ligne existante du quotidien et n'ecrit jamais par-dessus : une
paire (ticker, jour) deja presente et IDENTIQUE est une relance (le script le
constate et passe) ; une paire deja presente et DIFFERENTE arrete tout, parce
que c'est precisement la divergence que la section 19 doit juger, pas un script
de migration.

Il ne comble pas les 254 jours ouvres absents du quotidien hors mensuel : 247
sont confirmes absents chez brvm.org par le backfill, 5 n'ont jamais ete tentes,
et 2021 en porte 107 a lui seul. C'est un trou cote source, hors de portee d'ici.

Le piege des unites, et pourquoi une case reste vide
----------------------------------------------------
Les deux fichiers n'ecrivent pas le rendement dans la meme unite :

  * ``cours_extraits.csv`` le porte en POURCENTAGE (3,13 pour 3,13 %) ;
    ``charger_cours.py`` divise par cent a la lecture.
  * ``cours_quotidien_boc.csv`` melange les deux unites selon l'origine de la
    ligne, et ``charger_cours_quotidien.py::_rendement_normalise`` les
    discrimine par un seuil : **au-dela de 1,5 c'est un pourcentage**, en
    dessous c'est deja une fraction.

Consequence mesuree sur le fichier mensuel : **105 lignes** y portent un
rendement inferieur ou egal a 1,5 % (BICC, CFAC, NSBC, ORGT, PALC, SCRC, SEMC,
SPHC, UNXC). Recopiees telles quelles, elles seraient relues comme des
fractions, donc **cent fois trop grandes**. Ce script convertit donc en
FRACTION avant d'ecrire, seule unite que le lecteur du quotidien rend
fidelement sur toute la plage.

Reste une ligne que la fraction ne sauve pas : **STBC au 31/07/2018, rendement
210,41 %**. En fraction cela vaut 2,1041, au-dessus du plafond de 1,5 du
lecteur, qui le prendrait pour un pourcentage et servirait 2,10 %. Plutot
qu'une valeur fausse, cette case part **vide** -- une case vide vaut mieux
qu'une valeur approchee. Le cours et le PER de cette ligne, eux, sont verses
normalement. Note pour C4 : ce 210 % tombe juste apres les deux chutes de cours
STBC non documentees des 12 et 27/07/2018 que C4 recense ; c'est la signature
d'un dividende non ajuste d'une division de nominal, et une corroboration de
plus de ce chantier.

Garde-fous
----------
Comme ``outils/releve_capitaux_propres.py`` : ancres exactes, assertion
d'unicite, garde ``ATTENDU`` sur chaque grandeur avant ecriture, refus d'ecrire
si la realite differe, relance sans effet si deja applique. Une garde de plus,
propre a ce cas : avant d'ajouter quoi que ce soit, le script **reserialise le
fichier quotidien existant et exige l'octet pres le fichier d'origine**. Sans
elle, rien ne garantirait que la reecriture ne deforme pas les 86 057 lignes
qu'elle est censee laisser intactes.

Usage : python3 outils/versement_mensuel_vers_quotidien.py [--verifier]
        --verifier : ne touche a rien, dit seulement ou en est le versement.
"""

import csv
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENSUEL = os.path.join(RACINE, "collecte", "cours_extraits.csv")
QUOTIDIEN = os.path.join(RACINE, "collecte", "cours_quotidien_boc.csv")

# --------------------------------------------------------------------------
# ATTENDU : etat du depot AVANT ecriture, mesure le 30/09/2026. Le script
# s'arrete si la realite en differe -- c'est ce qui empeche de verser dans un
# fichier qui a change de forme depuis la redaction de celui-ci.
# --------------------------------------------------------------------------
ATTENDU = {
    "entete_mensuel": ["ticker", "date_bulletin", "cours", "per", "rendement",
                       "variation_annee", "dividende_montant", "dividende_date"],
    "entete_quotidien": ["ticker", "date_bulletin", "cours", "per", "rendement"],
    "lignes_mensuel": 4509,
    "dates_mensuel": 101,
    "tickers_mensuel": 47,
    "lignes_quotidien_avant": 86057,
    "dates_quotidien_avant": 1926,
}

# Le lecteur du quotidien prend pour un pourcentage tout rendement superieur a
# ce seuil. Recopie de charger_cours_quotidien.py::_rendement_normalise ; le
# script verifie ci-dessous que la valeur y est toujours celle-la.
PLAFOND_FRACTION = 1.5

# Seule case volontairement laissee vide, avec sa valeur d'origine. Le script
# refuse de tourner si l'ensemble des cases inrepresentables differe de celui-ci.
RENDEMENTS_INREPRESENTABLES = {("STBC", "2018-07-31"): 210.41}


def iso(date_bulletin):
    """'20180131' -> '2018-01-31'. Refuse tout ce qui n'est pas cette forme."""
    d = date_bulletin.strip()
    if "-" in d:
        return d
    if len(d) != 8 or not d.isdigit():
        raise SystemExit("ERREUR : date de bulletin illisible : %r" % date_bulletin)
    return "%s-%s-%s" % (d[:4], d[4:6], d[6:8])


def fraction(pourcentage):
    """Pourcentage (3,13) -> fraction ('0.0313'). Rend None si inrepresentable."""
    if pourcentage in (None, ""):
        return ""
    v = float(pourcentage)
    if v / 100.0 > PLAFOND_FRACTION:
        return None
    return ("%.8f" % (v / 100.0)).rstrip("0").rstrip(".") or "0"


def lire(chemin):
    with open(chemin, newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        return lecteur.fieldnames, list(lecteur)


def fin_de_ligne(texte):
    """Fin de ligne reellement utilisee par le fichier, jamais supposee.

    cours_quotidien_boc.csv est ecrit en CRLF par les collecteurs. Reecrire en
    LF n'aurait change aucune valeur mais aurait produit un diff de 86 057
    lignes, illisible, et aurait mis ce fichier en desaccord avec le collecteur
    qui continue d'y ecrire. La garde de reserialisation ci-dessous l'a attrape
    au premier essai : c'est exactement ce pour quoi elle est la.
    """
    i = texte.find("\n")
    if i <= 0:
        raise SystemExit("ERREUR : fichier sans fin de ligne exploitable")
    return "\r\n" if texte[i - 1] == "\r" else "\n"


def serialiser(entete, lignes, fin="\n"):
    tampon = io.StringIO(newline="")
    ecrivain = csv.DictWriter(tampon, fieldnames=entete, lineterminator=fin)
    ecrivain.writeheader()
    for ligne in lignes:
        ecrivain.writerow(ligne)
    return tampon.getvalue()


def controler_le_lecteur():
    """Le seuil de 1,5 est copie ici : verifier qu'il n'a pas bouge la-bas."""
    chemin = os.path.join(RACINE, "collecte", "charger_cours_quotidien.py")
    with open(chemin, encoding="utf-8") as f:
        code = f.read()
    if "if v > 1.5:" not in code:
        raise SystemExit(
            "ERREUR : charger_cours_quotidien.py ne porte plus le seuil 'if v > 1.5:'. "
            "Le seuil de discrimination pourcentage/fraction a change : relire ce "
            "lecteur avant de verser quoi que ce soit.")


def main():
    verifier_seulement = "--verifier" in sys.argv
    controler_le_lecteur()

    entete_m, mensuel = lire(MENSUEL)
    entete_q, quotidien = lire(QUOTIDIEN)

    if entete_m != ATTENDU["entete_mensuel"]:
        raise SystemExit("ERREUR : entete de cours_extraits.csv inattendue : %s" % entete_m)
    if entete_q != ATTENDU["entete_quotidien"]:
        raise SystemExit("ERREUR : entete de cours_quotidien_boc.csv inattendue : %s" % entete_q)
    if len(mensuel) != ATTENDU["lignes_mensuel"]:
        raise SystemExit("ERREUR : %d lignes dans cours_extraits.csv (attendu %d)"
                         % (len(mensuel), ATTENDU["lignes_mensuel"]))

    # --- Unicite des ancres : une paire (ticker, jour) et une seule ---------
    paires_m = {}
    for r in mensuel:
        if not r["date_bulletin"]:
            raise SystemExit("ERREUR : ligne mensuelle sans date : %r" % r)
        cle = (r["ticker"], iso(r["date_bulletin"]))
        if cle in paires_m:
            raise SystemExit("ERREUR : %s %s apparait deux fois dans cours_extraits.csv "
                             "(attendu : exactement 1)" % cle)
        paires_m[cle] = r
    if len({d for _, d in paires_m}) != ATTENDU["dates_mensuel"]:
        raise SystemExit("ERREUR : %d dates dans cours_extraits.csv (attendu %d)"
                         % (len({d for _, d in paires_m}), ATTENDU["dates_mensuel"]))
    if len({t for t, _ in paires_m}) != ATTENDU["tickers_mensuel"]:
        raise SystemExit("ERREUR : %d tickers dans cours_extraits.csv (attendu %d)"
                         % (len({t for t, _ in paires_m}), ATTENDU["tickers_mensuel"]))

    paires_q = {}
    for r in quotidien:
        cle = (r["ticker"], r["date_bulletin"])
        if cle in paires_q:
            raise SystemExit("ERREUR : %s %s apparait deux fois dans "
                             "cours_quotidien_boc.csv" % cle)
        paires_q[cle] = r

    # --- Les cases que la fraction ne sauve pas ----------------------------
    inrepresentables = {}
    for cle, r in paires_m.items():
        if r["rendement"] and fraction(r["rendement"]) is None:
            inrepresentables[cle] = float(r["rendement"])
    if inrepresentables != RENDEMENTS_INREPRESENTABLES:
        raise SystemExit(
            "ERREUR : les rendements inrepresentables ont change.\n"
            "  attendu : %s\n  trouve  : %s\n"
            "Relire la note d'en-tete avant de toucher a la liste."
            % (RENDEMENTS_INREPRESENTABLES, inrepresentables))

    # --- Ce qui est deja la, et ce qui manque ------------------------------
    def convertie(r):
        rendement = fraction(r["rendement"])
        return {"ticker": r["ticker"],
                "date_bulletin": iso(r["date_bulletin"]),
                "cours": r["cours"],
                "per": r["per"],
                "rendement": "" if rendement is None else rendement}

    a_verser, deja, divergentes = [], 0, []
    for cle, r in sorted(paires_m.items()):
        neuve = convertie(r)
        ancienne = paires_q.get(cle)
        if ancienne is None:
            a_verser.append(neuve)
            continue
        if all(str(ancienne.get(c, "")) == str(neuve[c]) for c in entete_q):
            deja += 1
        else:
            divergentes.append((cle, ancienne, neuve))

    print("cours_extraits.csv : %d lignes, %d dates, %d tickers"
          % (len(mensuel), len({d for _, d in paires_m}), len({t for t, _ in paires_m})))
    print("cours_quotidien_boc.csv : %d lignes, %d dates"
          % (len(quotidien), len({d for _, d in paires_q})))
    print("a verser : %d | deja presentes a l'identique : %d | divergentes : %d"
          % (len(a_verser), deja, len(divergentes)))

    if divergentes:
        for cle, ancienne, neuve in divergentes[:10]:
            print("  DIVERGENTE %s %s : quotidien %s | mensuel %s"
                  % (cle[0], cle[1], ancienne, neuve))
        raise SystemExit(
            "ERREUR : %d paire(s) (ticker, jour) existent deja dans le quotidien avec "
            "des valeurs DIFFERENTES. Ce script ne tranche pas une divergence entre "
            "deux extractions du meme document : c'est le travail de la section 19 de "
            "moteur/tester_donnees.py, et d'un humain. Rien n'a ete ecrit."
            % len(divergentes))

    if not a_verser:
        print("Rien a faire : le versement est deja applique (%d paires a l'identique)." % deja)
        return 0
    if verifier_seulement:
        print("--verifier : %d ligne(s) restent a verser, rien n'a ete ecrit." % len(a_verser))
        return 0

    # --- Garde de reecriture : l'existant doit se reserialiser a l'identique
    with open(QUOTIDIEN, encoding="utf-8", newline="") as f:
        original = f.read()
    fin = fin_de_ligne(original)
    if serialiser(entete_q, quotidien, fin) != original:
        raise SystemExit(
            "ERREUR : reserialiser cours_quotidien_boc.csv sans rien changer ne rend "
            "pas le fichier d'origine a l'octet pres. Une reecriture deformerait les "
            "lignes existantes. Rien n'a ete ecrit.")

    # --- Versement ----------------------------------------------------------
    # Le fichier est trie par (date_bulletin, ticker) : on le reconstruit dans
    # le meme ordre, sans quoi chaque collecte quotidienne produirait ensuite un
    # diff illisible.
    fusion = quotidien + a_verser
    fusion.sort(key=lambda r: (r["date_bulletin"], r["ticker"]))
    with open(QUOTIDIEN, "w", encoding="utf-8", newline="") as f:
        f.write(serialiser(entete_q, fusion, fin))

    _, relu = lire(QUOTIDIEN)
    if len(relu) != len(quotidien) + len(a_verser):
        raise SystemExit("ERREUR : relecture apres ecriture : %d lignes au lieu de %d"
                         % (len(relu), len(quotidien) + len(a_verser)))
    print("Verse : %d lignes ajoutees, %d lignes au total, %d dates."
          % (len(a_verser), len(relu), len({r["date_bulletin"] for r in relu})))
    print("Rendement laisse vide (inrepresentable par le lecteur) : %s"
          % ", ".join("%s %s (%.2f %%)" % (t, d, v)
                      for (t, d), v in sorted(RENDEMENTS_INREPRESENTABLES.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
