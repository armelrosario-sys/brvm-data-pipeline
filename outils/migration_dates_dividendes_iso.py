#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C10 — normaliser en ISO les dates de paiement des dividendes
=======================================================================

Ce que ce script repare
-----------------------
``collecte/dividendes_par_exercice.csv`` porte les dates de paiement au format
francais abrege sur deux chiffres d'annee (``24-juil.-17``,  ``30-sept.-24``,
``24-aout-22``). ``charger_dividendes_exercice.py`` inserait la chaine brute
sans la normaliser : la colonne ``dividendes.date_paiement`` melangeait donc
**296 lignes francaises** et **12 lignes ISO** (mesure du 30/09/2026, sur une
table de 311 lignes -- les comptes de 326/296/24/6 inscrits le 28/09 etaient
faux).

Trois consequences, toutes mesurees sur la base du 30/09/2026 :

  1. ``moteur/scoring.py::dividendes()`` fait ``ORDER BY date_paiement DESC``.
     Sur du francais abrege l'ordre est ALPHABETIQUE : sur les **49** tickers
     portant au moins un dividende date, ce tri rendait un autre versement que
     le plus recent pour **34** d'entre eux.
  2. Le meme fichier fait ``int(dernier_div["date_paiement"][:4])``. Sur
     ``24-juil.-17`` cela vaut ``int("24-j")``, donc ``ValueError`` -- avalee
     par un ``except (ValueError, TypeError): pass``. Tout le bloc
     « regularite du dividende » (bonus de 20 points, malus de 20, alerte
     « dernier dividende verse il y a N ans ») etait donc **silencieusement
     saute sur 45 des 49 tickers**.
  3. ``collecte/collecte_boc_quotidien.py`` normalise en ISO puis deduplique
     par ``WHERE ticker=? AND montant_net=? AND date_paiement=?``. Une date ISO
     ne s'egalera jamais a la forme francaise du meme jour : le jour ou le BOC
     reobserve un dividende deja charge par la Piste D, il l'insere en double.
     Aucun doublon mixte n'existait encore (0 paire (ticker, jour) portant les
     deux formats) : ce defaut-la etait latent, les deux premiers etaient actifs.

Ce que ce script fait, et ne fait pas
-------------------------------------
Il reecrit la seule colonne ``date_paiement`` de
``collecte/dividendes_par_exercice.csv`` en ISO, par
``collecte/dates_dividendes.py::vers_iso``. **Aucune autre colonne, aucune
autre ligne, aucun autre fichier.** Il ne touche pas la base : ``brvm.db`` est
reconstruite a neuf a chaque passage, c'est le CSV qui est la donnee durable.

Il ne touche pas ``collecte/dividendes_historique.csv``, qui est l'**archive
des observations brutes** telles que le BOC les a ecrites : sa valeur est
justement d'etre le releve non retouche. La normalisation se fait a la sortie
de ``historiser_dividendes_exercice.py``, qui lit cette archive et ecrit le
fichier migre ici -- donc une regeneration ne defait pas cette migration.

Il ne touche pas ``donnees/base/dividendes.csv`` : verifie le 30/09/2026, ses
15 lignes sont deja ISO (12) ou vides (3). Le script le controle et s'arrete si
ce n'est plus vrai.

Garde-fous
----------
Sur le modele de ``outils/versement_mensuel_vers_quotidien.py`` :

* **ancres exactes avec assertion d'unicite** -- la cle (ticker, exercice,
  montant, date brute) de chaque ligne, et refus si deux lignes la partagent ;
* **garde ``ATTENDU`` sur chaque grandeur** -- entete, nombre de lignes, nombre
  de dates distinctes, nombre de cases vides, repartition des confiances, et
  **empreinte SHA-256 de la colonne des cles et des dates avant migration**.
  Toute divergence arrete le script sans rien ecrire ;
* **garde d'empreinte APRES** -- le resultat doit valoir exactement l'empreinte
  attendue, calculee le 30/09/2026 ;
* **garde de reserialisation** -- avant d'ecrire, le script reserialise le
  fichier d'origine et exige l'octet pres le fichier d'origine. Sans elle, rien
  ne garantirait que la reecriture ne deforme pas les 364 lignes qu'elle est
  censee laisser intactes hors la colonne de date ;
* **refus plutot que devinette** -- une date non convertible arrete tout. Zero
  cas sur les 364 lignes, verifie ;
* **relance sans effet** -- si la colonne est deja ISO, le script le constate et
  sort sans ecrire.

Usage : python3 outils/migration_dates_dividendes_iso.py [--verifier]
        --verifier : ne touche a rien, dit seulement ou en est la migration.
"""
import csv
import hashlib
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "collecte"))
from dates_dividendes import est_iso, vers_iso  # noqa: E402

CIBLE = os.path.join(RACINE, "collecte", "dividendes_par_exercice.csv")
BASE_DIVIDENDES = os.path.join(RACINE, "donnees", "base", "dividendes.csv")

# --------------------------------------------------------------------------
# ATTENDU : etat du depot AVANT ecriture, mesure le 30/09/2026 (cycle 10). Le
# script s'arrete si la realite en differe -- c'est ce qui empeche de migrer un
# fichier qui a change depuis la redaction de celui-ci.
# --------------------------------------------------------------------------
ATTENDU = {
    "entete": ["ticker", "exercice_couvert", "montant", "date_paiement",
               "confiance", "note"],
    "lignes": 364,
    "dates_distinctes": 253,
    "cases_vides": 2,
    # Doublons stricts : lignes identiques sur les six colonnes. Trouves par
    # l'assertion d'unicite de ce script (voir garde 2). Inscrits en C19.
    # Ils passent de 12 a 16 par la migration : quatre evenements etaient
    # dedoubles sous DEUX orthographes de la meme date, que l'ISO reunit.
    "doublons_stricts_avant": 12,
    "doublons_stricts_apres": 16,
    "confiances": {"ELEVEE": 359, "MANQUANT": 5},
    "fin_de_ligne": "\n",
    # SHA-256 de "ticker|exercice|montant|date" par ligne, dans l'ordre du fichier.
    "empreinte_avant": "9788fb92d2f15a5828f4d7547bbaea8d4ea97ae081692555c25a17689989b8c4",
    "empreinte_apres": "bbd3f94ef98a9539d9a7769625e5351a9ef65c8c960c6875416733343dde61c3",
    # donnees/base/dividendes.csv, deja propre : 12 ISO, 3 vides, 0 francais.
    "base_iso": 12,
    "base_vides": 3,
}


def echec(message):
    raise SystemExit("ERREUR : " + message + "\n  -> rien n'a ete ecrit.")


def lire_texte(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return f.read()


def fin_de_ligne(texte):
    """Fin de ligne reellement utilisee, jamais supposee."""
    i = texte.find("\n")
    if i <= 0:
        echec("fichier sans fin de ligne exploitable : " + CIBLE)
    return "\r\n" if texte[i - 1] == "\r" else "\n"


def serialiser(entete, lignes, fin):
    tampon = io.StringIO(newline="")
    ecrivain = csv.DictWriter(tampon, fieldnames=entete, lineterminator=fin)
    ecrivain.writeheader()
    for ligne in lignes:
        ecrivain.writerow(ligne)
    return tampon.getvalue()


def empreinte(lignes, champ="date_paiement"):
    h = hashlib.sha256()
    for r in lignes:
        h.update(("%s|%s|%s|%s\n" % (r["ticker"], r["exercice_couvert"],
                                     r["montant"], r[champ] or "")).encode("utf-8"))
    return h.hexdigest()


def compter_doublons_stricts(lignes, entete):
    """Nombre de lignes en trop parmi celles qui partagent la cle naturelle.

    Refuse si deux lignes partagent la cle (ticker, exercice, montant, date)
    SANS etre identiques partout : laquelle convertir serait alors indecidable.
    """
    groupes = {}
    for i, r in enumerate(lignes, start=2):
        cle = (r["ticker"], r["exercice_couvert"], r["montant"], r["date_paiement"])
        groupes.setdefault(cle, []).append((i, r))
    doublons = 0
    for cle, membres in groupes.items():
        if len(membres) == 1:
            continue
        premier = membres[0][1]
        for i, r in membres[1:]:
            if any(r[c] != premier[c] for c in entete):
                echec("ancre %r partagee par des lignes DIFFERENTES (ligne %d) : "
                      "impossible de savoir laquelle convertir." % (cle, i))
            doublons += 1
    return doublons


def controler_base_dividendes():
    """donnees/base/dividendes.csv n'est pas migre : verifier qu'il n'en a pas besoin."""
    lignes = list(csv.DictReader(open(BASE_DIVIDENDES, encoding="utf-8", newline="")))
    iso = sum(1 for r in lignes if est_iso(r.get("date_paiement")))
    vides = sum(1 for r in lignes if not (r.get("date_paiement") or "").strip())
    autres = len(lignes) - iso - vides
    if autres:
        echec("donnees/base/dividendes.csv porte %d date(s) ni ISO ni vide : ce "
              "fichier n'etait pas concerne le 30/09/2026, il l'est devenu. "
              "Le relire avant de migrer quoi que ce soit." % autres)
    if (iso, vides) != (ATTENDU["base_iso"], ATTENDU["base_vides"]):
        print("  [note] donnees/base/dividendes.csv : %d ISO et %d vides "
              "(attendu %d et %d) -- toujours sain, seul le compte a bouge."
              % (iso, vides, ATTENDU["base_iso"], ATTENDU["base_vides"]))


def controler_le_chargeur():
    """Le chargeur doit normaliser a l'entree, sans quoi la migration seule ne
    tient pas : le jour ou un CSV reprend une date francaise, la table la
    ravalerait telle quelle."""
    chemin = os.path.join(RACINE, "collecte", "charger_dividendes_exercice.py")
    code = lire_texte(chemin)
    if "dates_dividendes" not in code or "vers_iso" not in code:
        echec("collecte/charger_dividendes_exercice.py n'importe pas "
              "dates_dividendes.vers_iso : il inserirait encore la chaine brute. "
              "Appliquer le correctif du chargeur avant cette migration.")


def main():
    verifier_seulement = "--verifier" in sys.argv
    print("=== C10 — migration ISO de collecte/dividendes_par_exercice.csv ===")

    texte = lire_texte(CIBLE)
    fin = fin_de_ligne(texte)
    lecteur = csv.DictReader(io.StringIO(texte, newline=""))
    entete = list(lecteur.fieldnames or [])
    lignes = list(lecteur)

    # --- Garde 1 : la forme du fichier -------------------------------------
    if entete != ATTENDU["entete"]:
        echec("entete inattendue : %s" % entete)
    if fin != ATTENDU["fin_de_ligne"]:
        echec("fin de ligne %r inattendue (attendu %r)" % (fin, ATTENDU["fin_de_ligne"]))
    if len(lignes) != ATTENDU["lignes"]:
        echec("%d lignes (attendu %d)" % (len(lignes), ATTENDU["lignes"]))

    confiances = {}
    for r in lignes:
        confiances[r["confiance"]] = confiances.get(r["confiance"], 0) + 1
    if confiances != ATTENDU["confiances"]:
        echec("repartition des confiances %s (attendu %s)"
              % (confiances, ATTENDU["confiances"]))

    # --- Relance sans effet ? Teste AVANT les gardes d'etat d'avant, qui ne
    # --- decrivent que le fichier non encore migre. -------------------------
    deja = [r for r in lignes if est_iso(r["date_paiement"])]
    vides = [r for r in lignes if not (r["date_paiement"] or "").strip()]
    if len(deja) + len(vides) == len(lignes):
        print("  migration DEJA APPLIQUEE : %d dates ISO, %d cases vides, "
              "0 date francaise." % (len(deja), len(vides)))
        emp = empreinte(lignes)
        if emp != ATTENDU["empreinte_apres"]:
            echec("le fichier est bien tout ISO mais son empreinte est %s "
                  "(attendu %s) : il a change ailleurs que sur les dates."
                  % (emp, ATTENDU["empreinte_apres"]))
        dbl = compter_doublons_stricts(lignes, entete)
        if dbl != ATTENDU["doublons_stricts_apres"]:
            echec("%d doublon(s) strict(s) apres migration (attendu %d)."
                  % (dbl, ATTENDU["doublons_stricts_apres"]))
        print("  empreinte conforme, %d doublon(s) strict(s) (C19). Rien a faire." % dbl)
        return 0

    # --- Garde 2 : les ancres, et les 12 doublons trouves en les posant -----
    # La cle naturelle (ticker, exercice, montant, date) n'est PAS unique dans
    # ce fichier : 12 lignes y sont dupliquees. Mesure du 30/09/2026, faite
    # justement par l'assertion d'unicite de ce script, qui a refuse de tourner
    # au premier essai (ligne 4 et ligne 6 : ABJC 2017, 98,97, 20-juin-18).
    #
    # Les 12 doublons sont STRICTEMENT IDENTIQUES sur les six colonnes, note
    # comprise. Laquelle des deux lignes jumelles est convertie est donc sans
    # objet : elles recoivent la meme date. L'assertion est reformulee en
    # consequence -- non pas "chaque cle est unique", mais "toute cle repetee
    # ne l'est que par des lignes rigoureusement identiques", ce qui est la
    # propriete dont cette migration a reellement besoin. Le nombre de doublons
    # est fige : s'il change, le fichier a change et le script s'arrete.
    #
    # Ces doublons ne produisent aucun doublon EN BASE :
    # charger_dividendes_exercice.py deduplique par (ticker, exercice_couvert).
    # Le defaut est donc latent, et inscrit en C19.
    doublons = compter_doublons_stricts(lignes, entete)
    if doublons != ATTENDU["doublons_stricts_avant"]:
        echec("%d ligne(s) dupliquee(s) a l'identique (attendu %d) : le fichier a "
              "change depuis la mesure du 30/09/2026."
              % (doublons, ATTENDU["doublons_stricts_avant"]))
    print("  ancres : %d lignes, %d doublon(s) strict(s) avant migration (C19)."
          % (len(lignes), doublons))

    # --- Garde 3 : l'etat d'avant est bien celui qui a ete mesure ----------
    emp_avant = empreinte(lignes)
    if emp_avant != ATTENDU["empreinte_avant"]:
        echec("empreinte des cles et dates %s (attendu %s) : le fichier a change "
              "depuis la mesure du 30/09/2026." % (emp_avant, ATTENDU["empreinte_avant"]))
    if len(vides) != ATTENDU["cases_vides"]:
        echec("%d case(s) vide(s) (attendu %d)" % (len(vides), ATTENDU["cases_vides"]))
    distinctes = {r["date_paiement"] for r in lignes if (r["date_paiement"] or "").strip()}
    if len(distinctes) != ATTENDU["dates_distinctes"]:
        echec("%d dates distinctes (attendu %d)"
              % (len(distinctes), ATTENDU["dates_distinctes"]))

    controler_base_dividendes()
    controler_le_chargeur()

    # --- Garde 4 : reserialisation a l'octet pres --------------------------
    if serialiser(entete, lignes, fin) != texte:
        echec("la reserialisation du fichier d'origine n'est pas identique a "
              "l'octet pres : la reecriture deformerait des lignes qu'elle doit "
              "laisser intactes.")

    # --- Conversion, refus plutot que devinette ----------------------------
    converties, inchangees, refus = 0, 0, []
    nouvelles = []
    for i, r in enumerate(lignes, start=2):
        brute = (r["date_paiement"] or "").strip()
        neuf = dict(r)
        if not brute:
            inchangees += 1
        else:
            iso = vers_iso(brute)
            if iso is None:
                refus.append((i, r["ticker"], brute))
            elif iso == brute:
                inchangees += 1
            else:
                neuf["date_paiement"] = iso
                converties += 1
        nouvelles.append(neuf)

    if refus:
        for i, t, brute in refus[:20]:
            print("  [REFUS] ligne %d, %s : date illisible %r" % (i, t, brute))
        echec("%d date(s) non convertible(s) : un mois non reconnu ou un jour "
              "inexistant ne se devine pas. Corriger ces lignes a la main "
              "d'abord." % len(refus))

    # --- Garde 5 : le resultat vaut l'empreinte attendue -------------------
    emp_apres = empreinte(nouvelles)
    if emp_apres != ATTENDU["empreinte_apres"]:
        echec("le resultat porte l'empreinte %s (attendu %s) : la conversion ne "
              "donne pas ce qui a ete mesure le 30/09/2026."
              % (emp_apres, ATTENDU["empreinte_apres"]))

    # --- Garde 6 : rien d'autre que la colonne de date n'a bouge -----------
    for avant, apres in zip(lignes, nouvelles):
        for champ in entete:
            if champ != "date_paiement" and avant[champ] != apres[champ]:
                echec("la colonne %r a change sur %s : la migration ne doit "
                      "toucher que date_paiement." % (champ, avant["ticker"]))
    if any(not est_iso(r["date_paiement"]) and (r["date_paiement"] or "").strip()
           for r in nouvelles):
        echec("une date de sortie n'est pas ISO : garde finale.")

    print("  %d ligne(s) a convertir, %d inchangee(s) (%d deja ISO, %d vides)."
          % (converties, inchangees, len(deja), len(vides)))
    if verifier_seulement:
        print("  --verifier : rien ecrit.")
        return 0

    with open(CIBLE, "w", encoding="utf-8", newline="") as f:
        f.write(serialiser(entete, nouvelles, fin))
    print("  ECRIT : %s" % CIBLE)

    # --- Relecture : ce qui est sur le disque est bien ce qui etait prevu ---
    relu = list(csv.DictReader(io.StringIO(lire_texte(CIBLE), newline="")))
    if empreinte(relu) != ATTENDU["empreinte_apres"]:
        echec("relecture apres ecriture : empreinte %s, attendu %s."
              % (empreinte(relu), ATTENDU["empreinte_apres"]))
    print("  relecture conforme : %d lignes, toutes ISO ou vides." % len(relu))
    return 0


if __name__ == "__main__":
    sys.exit(main())
