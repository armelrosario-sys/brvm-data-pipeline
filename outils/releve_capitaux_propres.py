#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Releve manuel des capitaux propres des titres hors de portee des extracteurs
=============================================================================

Sept titres n'avaient pas de capitaux propres exploitables : ni etats
financiers structures dans la base, ni rapport de notation recent chez
l'agregateur. La seule voie restante etait d'ouvrir les documents publies par
la BRVM et de relever les valeurs a la main. C'est fait le 27/09/2026 ; ce
script installe les valeurs relevees.

Doctrine appliquee, celle de moteur/arbitrage.py :

  * l'unite est celle IMPRIMEE sur le document, jamais devinee. Les trois
    unites rencontrees ici (millions, milliers, FCFA) sont citees dans la note
    de chaque ligne, avec le detail de la derivation quand le bilan n'affiche
    pas de ligne « total capitaux propres » ;
  * rien n'est ecrase : le script verifie que la case visee est bien VIDE
    avant d'ecrire, et refuse de tourner si une valeur y a ete deposee entre
    temps. Seule exception declaree, BNBC 2023, dont la valeur existante est
    demontrablement fausse (voir DEFAUT_BNBC) ;
  * une valeur illisible ne devient pas une valeur approchee. UNXC reste vide.

Le script est idempotent : relance apres succes, il constate que tout est
deja en place et ne touche a rien.

Verifications de plausibilite passees avant redaction (ROE = RN / CP) :
SOGC 18,3 % · SLBC 23,5 % · SHEC 22,2 % · CFAC 24,1 % · SICC -4,3 %.
"""

import csv
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETATS = os.path.join(RACINE, "donnees", "base", "etats_financiers.csv")
SOCIETES = os.path.join(RACINE, "donnees", "base", "societes.csv")

# --------------------------------------------------------------------------
# Les valeurs relevees, une entree par ligne de etats_financiers.csv.
#
#   attendu : etat des colonnes AVANT ecriture. Le script s'arrete si la
#             realite en differe -- c'est ce qui empeche d'ecraser un travail
#             fait ailleurs depuis la redaction de ce fichier.
#   nouveau : etat des colonnes APRES ecriture.
# --------------------------------------------------------------------------

RELEVES = [
    {
        "ticker": "SOGC",
        "exercice": "2025",
        "document": "20260422 - etats financiers SYSCOHADA - exercice 2025 - SOGB CI",
        "attendu": {
            "capitaux_propres": "",
            "statut_donnee": "VALIDE",
            "note": "SOGB CI, identite exacte (unite : milliers FCFA supposee)",
        },
        "nouveau": {
            "capitaux_propres": "68430.361",
            "note": (
                "SOGB CI, identite exacte ; unite MILLIERS FCFA confirmee par "
                "l'en-tete du document (etait supposee) ; CP releves a la main le "
                "27/09/2026 : capital 21601840 + primes et reserves 34335898 + "
                "resultat 12492623 = 68430361 milliers, le bilan resume n'affichant "
                "pas de ligne \"total capitaux propres\" ; ROE 18.3% ; comptes "
                "certifies par les commissaires aux comptes"
            ),
        },
    },
    {
        "ticker": "SHEC",
        "exercice": "2025",
        "document": "20260603 - etats financiers - exercice 2025 - Vivo Energy CI",
        "attendu": {
            "capitaux_propres": "",
            "payout_ratio": "",
            "statut_donnee": "VALIDE",
            "note": ("Vivo Energy CI, identite exacte --- R6 lot 5 : Services "
                     "financiers (partiel) + Telecommunications ---"),
        },
        "nouveau": {
            "capitaux_propres": "27158.717963",
            "payout_ratio": "1.0103",
            "note": (
                "Vivo Energy CI, identite exacte ; unite FCFA (imprimee au titre) ; "
                "CP releves a la main le 27/09/2026 : capital 3150000000 + primes et "
                "reserves 8802000000 + reserves 630000000 + report a nouveau "
                "8548592005 + resultat 6028125958 = 27158717963 FCFA, pas de ligne "
                "\"total CP\" au bilan ; la somme du passif recoupe le total bilan a "
                "l'unite (193561278972), ce qui valide la derivation ; ROE 22.2% ; "
                "payout = dividendes bruts 6090000000 / RN, projet d'affectation "
                "soumis a l'AGO du 24/06/2026 ; etats financiers PROVISOIRES "
                "--- R6 lot 5 : Services financiers (partiel) + Telecommunications ---"
            ),
        },
    },
    {
        "ticker": "SLBC",
        "exercice": "2025",
        "document": "20260519 - etats financiers - exercice 2025 - Solibra CI",
        "attendu": {
            "capitaux_propres": "",
            "payout_ratio": "",
            "statut_donnee": "PROBABLE",
            "note": ("Solibra ; texte natif corrompu, OCR utilise ; +113% confirme "
                     "par presse (05/2026) TP corrige (etait 307546, la valeur "
                     "N-1, au lieu de repeter 339517 — meme bug que les lignes "
                     "ci-dessous, revele par le golden test 65 lors de son ajout)"),
        },
        "nouveau": {
            "capitaux_propres": "195142",
            "payout_ratio": "0.7648",
            "note": (
                "Solibra ; texte natif corrompu, OCR utilise ; +113% confirme par "
                "presse (05/2026) TP corrige (etait 307546, la valeur N-1, au lieu de "
                "repeter 339517 — meme bug que les lignes ci-dessous, revele par le "
                "golden test 65 lors de son ajout) ; CP releves a la main le "
                "27/09/2026 sur le bilan resume, unite MILLIONS FCFA imprimee : "
                "ligne explicite \"Capitaux propres\" 195142 (2024 : 169443), "
                "recoupee par capital-primes-reserves 149361 + resultat 45781 ; "
                "ROE 23.5% ; payout = dividendes bruts 35012206680 / RN "
                "45781024496, projet d'affectation non approuve par l'AGO ; "
                "comptes certifies par les commissaires aux comptes"
            ),
        },
    },
    {
        "ticker": "CFAC",
        "exercice": "2024",
        "document": "20250516 - etats financiers - exercice 2024 - CFAO Motors CI",
        "attendu": {
            "capitaux_propres": "",
            "total_actif": "",
            "total_passif": "",
            "statut_donnee": "PROBABLE",
            "note": ("CFAO Motors CI, exercice 2024 seul dispo, bilan non recoupe "
                     "(ecart ~4%)"),
        },
        "nouveau": {
            "capitaux_propres": "19452.985667",
            "total_actif": "85012.929523",
            "total_passif": "85012.929523",
            "statut_donnee": "VALIDE",
            "note": (
                "CFAO Mobility Cote d'Ivoire (denomination du document ; la societe "
                "etait enregistree \"CFAO Motors CI\", nom corrige dans societes.csv) ; "
                "bilan systeme normal, unite FCFA ; releve a la main le 27/09/2026 : "
                "CP ligne CP \"TOTAL CAPITAUX PROPRES ET RESSOURCES ASSIMILEES\" "
                "19452985667 (N-1 17979153259), total general actif BZ = total general "
                "passif DZ = 85012929523 ; le RN 4693479450 du compte de resultat "
                "confirme au franc la valeur deja en base ; l'ecart de bilan d'environ "
                "4% qui maintenait cette ligne en PROBABLE est leve, statut porte a "
                "VALIDE ; ROE 24.1%"
            ),
        },
    },
    {
        "ticker": "SICC",
        "exercice": "2024",
        "document": ("20260612 - rapport d'activites annuel et etats financiers - "
                     "exercice 2025 - Sicor CI (en realite exercice 2024)"),
        "attendu": {
            "resultat_net": "",
            "resultat_net_n1": "",
            "capitaux_propres": "",
            "total_actif": "",
            "total_passif": "",
            "statut_donnee": "PROBABLE",
            "note": "",
        },
        "nouveau": {
            "resultat_net": "-128.639513",
            "resultat_net_n1": "19.245083",
            "capitaux_propres": "2975.325212",
            "total_actif": "4000.527655",
            "total_passif": "4000.527655",
            "note": (
                "Sicor ; ATTENTION le document depose le 12/06/2026 sous l'intitule "
                "\"exercice 2025\" porte en realite sur l'EXERCICE 2024 (\"Exercice "
                "clos le 31/12/2024\" au cartouche du bilan, AGO statuant sur 2024) : "
                "Sicor n'a pas encore publie ses comptes 2025 ; releve a la main le "
                "27/09/2026, unite FCFA : CP ligne CP 2975325212 (N-1 3103964725), "
                "RN -128639513, RN N-1 19245083, total bilan 4000527655 recoupe par "
                "le rapport des commissaires aux comptes ; OPINION AVEC RESERVES — "
                "ajustement de stocks non justifie de +131695250 et provision pour "
                "retraite IAS non comptabilisee ; le conseil d'administration avait "
                "arrete les memes comptes a un RN de -260334763 et des CP de "
                "2843629962, soit exactement 131695250 de moins : la perte affichee "
                "est de moitie celle arretee, statut maintenu a PROBABLE pour cette "
                "raison ; ROE -4.3%"
            ),
        },
    },
]

# --------------------------------------------------------------------------
# Correction d'un defaut existant, decouvert en passant au crible les 76
# couples (resultat net, capitaux propres) de la base : un seul est
# impossible.
#
#   BNBC 2023 : capitaux_propres = 3.0 millions FCFA pour un resultat net de
#   36.0 millions, soit un ROE de 1200 %. La meme societe porte 17769.95
#   millions de capitaux propres en 2025. La valeur est un fragment
#   d'extraction, pas une grandeur. Une case vide se voit et se comble ; une
#   fausse valeur se propage en silence jusqu'au ROE et au profil. Elle est
#   donc remise a vide.
# --------------------------------------------------------------------------

DEFAUT_BNBC = {
    "ticker": "BNBC",
    "exercice": "2023",
    "attendu": {
        "capitaux_propres": "3.0",
        "note": "9e3e6104_20240507_-_etats_financiers_de_synthese_-_bernabe_ci.pdf",
    },
    "nouveau": {
        "capitaux_propres": "",
        "note": (
            "9e3e6104_20240507_-_etats_financiers_de_synthese_-_bernabe_ci.pdf ; "
            "capitaux propres 3.0 retires le 27/09/2026 : la valeur donnait un ROE "
            "de 1200% (RN 36.0) alors que la meme societe porte 17769.95 de CP en "
            "2025 — fragment d'extraction, pas une grandeur. Case laissee vide, une "
            "absence etant lisible alors qu'une fausse valeur se propage en silence."
        ),
    },
}

# Renommage d'entite constate sur le document CFAC.
SOCIETE_CFAC = {
    "ticker": "CFAC",
    "avant": "CFAO Motors CI",
    "apres": "CFAO Mobility Cote d'Ivoire",
}


def lire(chemin):
    with open(chemin, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def ecrire(chemin, lignes):
    tampon = io.StringIO()
    csv.writer(tampon, lineterminator="\n").writerows(lignes)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        f.write(tampon.getvalue())


def index_unique(lignes, entete, ticker, exercice):
    """Renvoie l'indice de LA ligne (ticker, exercice). Echoue s'il y en a
    zero ou plusieurs : un doublon signifierait que la base a change de forme
    et qu'ecrire au hasard de l'une des deux serait un coup de des."""
    it, ie = entete.index("ticker"), entete.index("exercice")
    trouves = [i for i, l in enumerate(lignes)
               if i > 0 and l[it] == ticker and l[ie] == exercice]
    if len(trouves) != 1:
        raise SystemExit(
            "ERREUR : %s %s apparait %d fois dans %s (attendu : exactement 1). "
            "La base a change de forme, le script s'arrete sans rien ecrire."
            % (ticker, exercice, len(trouves), os.path.basename(ETATS)))
    return trouves[0]


def appliquer(lignes, entete, cible, journal):
    """Applique une entree. Renvoie 'ecrit', 'deja' ou leve SystemExit."""
    i = index_unique(lignes, entete, cible["ticker"], cible["exercice"])
    ligne = lignes[i]
    etiquette = "%s %s" % (cible["ticker"], cible["exercice"])

    # Deja applique ? Toutes les colonnes visees portent deja la valeur cible.
    if all(ligne[entete.index(c)] == v for c, v in cible["nouveau"].items()):
        journal.append("  = %-12s deja a jour" % etiquette)
        return "deja"

    # Sinon l'etat de depart doit etre exactement celui prevu.
    for colonne, valeur in cible.get("attendu", {}).items():
        reel = ligne[entete.index(colonne)]
        if reel != valeur:
            raise SystemExit(
                "ERREUR : %s, colonne %s vaut %r alors que le releve a ete "
                "prepare sur %r. Refus d'ecrire : soit la valeur a ete "
                "renseignee ailleurs depuis, soit ce n'est pas la bonne ligne."
                % (etiquette, colonne, reel, valeur))

    for colonne, valeur in cible["nouveau"].items():
        ligne[entete.index(colonne)] = valeur
    journal.append("  + %-12s %s" % (
        etiquette, ", ".join("%s=%s" % (c, v or "(vide)")
                             for c, v in cible["nouveau"].items()
                             if c != "note")))
    return "ecrit"


def renommer_societe(journal):
    lignes = lire(SOCIETES)
    entete = lignes[0]
    it, inom = entete.index("ticker"), entete.index("nom")
    cibles = [i for i, l in enumerate(lignes) if i > 0
              and l[it] == SOCIETE_CFAC["ticker"]]
    if len(cibles) != 1:
        raise SystemExit("ERREUR : CFAC apparait %d fois dans societes.csv."
                         % len(cibles))
    i = cibles[0]
    actuel = lignes[i][inom]
    if actuel == SOCIETE_CFAC["apres"]:
        journal.append("  = CFAC        nom deja a jour")
        return False
    if actuel != SOCIETE_CFAC["avant"]:
        raise SystemExit(
            "ERREUR : le nom de CFAC vaut %r alors que le renommage a ete "
            "prepare sur %r. Refus d'ecrire." % (actuel, SOCIETE_CFAC["avant"]))
    lignes[i][inom] = SOCIETE_CFAC["apres"]
    ecrire(SOCIETES, lignes)
    journal.append("  + CFAC        nom %r -> %r"
                   % (SOCIETE_CFAC["avant"], SOCIETE_CFAC["apres"]))
    return True


TESTS = os.path.join(RACINE, "moteur", "tester_donnees.py")

# Ancre d'insertion dans la section 13 de tester_donnees.py : la derniere
# ligne de la boucle sur les quatre scripts qui lisaient le TEXTE de
# peupler.py. Le bloc est ajoute juste apres, a la fin de la section.
ANCRE_TESTS = '''                f"{chemin_rel} : {fonction}() lit un CSV de reference, "
                f"plus le texte de peupler.py")
'''

# Marqueur d'idempotence : si cette chaine est deja dans le fichier, le
# patch a deja ete applique et on n'y retouche pas.
MARQUEUR_TESTS = "SEUIL_ROE_ABSURDE"

BLOC_TESTS = r'''
    # Plancher de plausibilite sur le couple (resultat net, capitaux propres).
    #
    # POURQUOI (27/09/2026). En passant au crible les 76 couples renseignes,
    # un seul etait impossible : BNBC 2023 portait 3.0 millions de capitaux
    # propres pour 36.0 millions de resultat net, soit un ROE de 1200 %, alors
    # que la meme societe porte 17769.95 millions de capitaux propres en 2025.
    # C'etait un fragment d'extraction, pas une grandeur -- et il avait
    # traverse quinze sections de tests sans etre vu, parce qu'aucune ne
    # confrontait les deux colonnes entre elles. Le seuil est volontairement
    # large : le plus haut ROE legitime de la base est celui de STBC (79.9 %),
    # une societe qui distribue presque tout ce qu'elle gagne.
    SEUIL_ROE_ABSURDE = 200.0
    absurdes = []
    for r in etats:
        try:
            rn = float(r["resultat_net"])
            cp = float(r["capitaux_propres"])
        except (TypeError, ValueError):
            continue
        if cp == 0 or r["ticker"].startswith("TEST"):
            continue
        roe = 100.0 * rn / cp
        if abs(roe) > SEUIL_ROE_ABSURDE:
            absurdes.append(f"{r['ticker']} {r['exercice']} : ROE {roe:.0f} % "
                            f"(RN {rn}, CP {cp})")
    verifie(not absurdes,
            f"aucun couple (resultat net, capitaux propres) n'implique un ROE "
            f"superieur a {SEUIL_ROE_ABSURDE:.0f} % en valeur absolue"
            + ("" if not absurdes else " — " + " ; ".join(absurdes)))

    # Non-regression du releve manuel du 27/09/2026 (outils/releve_capitaux_propres.py).
    #
    # Ces cinq valeurs ne viennent d'aucun extracteur : elles ont ete lues a
    # la main dans les documents publies par la BRVM, apres que les deux
    # chaines de collecte ont echoue sur ces titres. Aucune n'est
    # reconstituable automatiquement : si une reecriture du CSV les efface,
    # rien ne les ramenera. D'ou ce test.
    RELEVE_MANUEL = {
        ("SOGC", "2025"): 68430.361,       # milliers FCFA -> millions
        ("SHEC", "2025"): 27158.717963,    # FCFA -> millions
        ("SLBC", "2025"): 195142.0,        # millions FCFA, ligne explicite
        ("CFAC", "2024"): 19452.985667,    # FCFA -> millions
        ("SICC", "2024"): 2975.325212,     # FCFA -> millions
    }
    perdus = []
    for (ticker, exercice), attendu in sorted(RELEVE_MANUEL.items()):
        ligne = next((r for r in etats if r["ticker"] == ticker
                      and r["exercice"] == exercice), None)
        if ligne is None:
            perdus.append(f"{ticker} {exercice} : ligne absente")
            continue
        try:
            reel = float(ligne["capitaux_propres"])
        except (TypeError, ValueError):
            perdus.append(f"{ticker} {exercice} : capitaux propres vides")
            continue
        if abs(reel - attendu) > 0.001:
            perdus.append(f"{ticker} {exercice} : {reel} au lieu de {attendu}")
    verifie(not perdus,
            f"les {len(RELEVE_MANUEL)} capitaux propres releves a la main le "
            f"27/09/2026 sont toujours en base"
            + ("" if not perdus else " — " + " ; ".join(perdus)))
'''


def patcher_tests(journal):
    """Ajoute deux controles a la section 13 de moteur/tester_donnees.py :
    un plancher de plausibilite sur le couple (resultat net, capitaux
    propres) -- celui qui aurait attrape BNBC 2023 -- et la non-regression
    des cinq valeurs relevees a la main, qu'aucun extracteur ne saurait
    reconstituer si une reecriture du CSV les effacait."""
    if not os.path.exists(TESTS):
        raise SystemExit("ERREUR : %s absent." % TESTS)
    code = open(TESTS, encoding="utf-8").read()
    if MARQUEUR_TESTS in code:
        journal.append("  = tester_donnees.py  deja patche")
        return False
    n = code.count(ANCRE_TESTS)
    if n != 1:
        raise SystemExit(
            "ERREUR : l'ancre d'insertion apparait %d fois dans "
            "moteur/tester_donnees.py (attendu : exactement 1). Le fichier a "
            "change, le patch s'arrete sans rien ecrire." % n)
    code = code.replace(ANCRE_TESTS, ANCRE_TESTS + BLOC_TESTS)
    # Le fichier doit rester du Python valide : on le verifie avant d'ecrire.
    import ast
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise SystemExit("ERREUR : le patch casserait tester_donnees.py "
                         "(ligne %s : %s). Rien n'est ecrit." % (e.lineno, e.msg))
    with open(TESTS, "w", encoding="utf-8") as f:
        f.write(code)
    journal.append("  + tester_donnees.py  2 controles ajoutes a la section 13 "
                   "(%d lignes)" % len(BLOC_TESTS.splitlines()))
    return True


def main():
    lignes = lire(ETATS)
    entete = lignes[0]
    manquantes = [c for c in ("ticker", "exercice", "resultat_net",
                              "resultat_net_n1", "total_actif", "total_passif",
                              "capitaux_propres", "payout_ratio",
                              "statut_donnee", "note") if c not in entete]
    if manquantes:
        raise SystemExit("ERREUR : colonnes absentes de l'en-tete : %s"
                         % ", ".join(manquantes))

    journal, ecrits = [], 0
    journal.append("Releves manuels du 27/09/2026 :")
    for cible in RELEVES:
        if appliquer(lignes, entete, cible, journal) == "ecrit":
            ecrits += 1
    journal.append("Correction du defaut BNBC 2023 :")
    if appliquer(lignes, entete, DEFAUT_BNBC, journal) == "ecrit":
        ecrits += 1

    if ecrits:
        ecrire(ETATS, lignes)

    journal.append("Renommage d'entite :")
    renomme = renommer_societe(journal)

    journal.append("Garde-fous ajoutes aux tests :")
    patche = patcher_tests(journal)

    print("\n".join(journal))
    print()
    if ecrits or renomme or patche:
        print("%d ligne(s) de etats_financiers.csv ecrite(s)%s%s."
              % (ecrits, ", nom de societe corrige" if renomme else "",
                 ", tests enrichis" if patche else ""))
    else:
        print("Rien a faire : le releve etait deja installe.")

    # UNXC est volontairement absent : la conversion du document Uniwax 2024
    # ne restitue que le capital social de l'en-tete, tout le bilan est perdu.
    # Aucune valeur approchee n'est deposee a la place.
    print("UNXC reste sans capitaux propres (document illisible), "
          "et SICC 2025 reste a publier par la societe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
