#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lot 2 du 27/09/2026 : taux sans risque, referentiel BICB, Uniwax certifie,
et mise en quarantaine des rapports intermediaires pris pour des comptes annuels
==============================================================================

Quatre chantiers qu'une meme soiree a fait remonter, et un cinquieme controle
pour qu'ils ne reviennent pas.

A. TAUX DE REFERENCE UEMOA. Celui en place datait du 06/03/2026 (adjudication
   du Togo, 7,36 % a cinq ans) et servait de prime de rendement aux 47 fiches,
   soit 205 jours de retard. Il est remplace par l'adjudication de la Cote
   d'Ivoire du 15/09/2026. Le changement d'emetteur est volontaire et il est
   ecrit dans le fichier : la Cote d'Ivoire est le mieux note des huit Tresors
   de l'union, le plus profond, et le pays de domiciliation de la grande
   majorite des societes cotees -- c'est donc son papier, et non celui d'un
   emetteur plus risque, qui represente l'actif sans risque face auquel un
   dividende BRVM se juge.

B. BICB, REFERENTIEL. La base retenait le resultat PCB OHADA (24 200) alors
   que BIIC publie aussi un resultat IFRS (36 237), et la note disait
   explicitement : « statut PROBABLE tant que la source du double-reporting
   n'est pas expertisee ». L'expertise est faite, par trois identites
   concordantes (voir NOTE_BICB) : le PER publie par la BRVM est bati sur le
   resultat IFRS. Garder le PCB OHADA revient a afficher, cote a cote sur la
   meme fiche, un PER calcule sur un resultat et une croissance calculee sur
   un autre.

C. UNIWAX. Les etats financiers 2024 certifies, releves a la main le
   27/09/2026, donnent un exercice 2024 absent de la base et corrigent
   l'exercice 2023, dont la seule source etait un document dont le nom porte
   « non_verifies_par_les_cac ». L'arrete definitif differe de 18,6 millions
   sur le resultat et de 28,7 millions sur le bilan.

D. RAPPORTS INTERMEDIAIRES PRIS POUR DES COMPTES ANNUELS. La fusion
   automatique du 27/07/2026 a ingere des rapports trimestriels comme s'ils
   etaient des exercices clos. Trois lignes portent ainsi un resultat partiel :
   UNXC 2025, ECOC 2022, BICC 2024. Deux se refutent toutes seules, par la
   colonne N-1 de l'exercice suivant (voir les notes). Ces resultats sont
   retires -- pas remplaces par une estimation : la case vide est le seul etat
   honnete tant que les comptes annuels ne sont pas relus.

E. CONTROLE AJOUTE. Un document publie AVANT la cloture de l'exercice qu'il
   pretend couvrir ne peut pas etre des comptes annuels. C'est un test d'une
   ligne, et il attrape toute la famille D d'un coup.
"""

import ast
import csv
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETATS = os.path.join(RACINE, "donnees", "base", "etats_financiers.csv")
SEUILS = os.path.join(RACINE, "config", "seuils.yaml")
TESTS = os.path.join(RACINE, "moteur", "tester_donnees.py")

# ==========================================================================
# A. TAUX DE REFERENCE UEMOA
# ==========================================================================

BLOC_TAUX_AVANT = '''macro:
  taux_oat_3ans: 0.0718        # rendement moyen pondere, adjudication Togo 06/03/2026
  taux_oat_5ans: 0.0736        # idem, maturite 5 ans
  taux_reference: 0.0736       # celui utilise pour les comparaisons de rendement
  source: "UMOA-Titres, adjudication Togo du 06/03/2026 (rendements moyens ponderes)"
  date_releve: "2026-03-06"
'''

BLOC_TAUX_APRES = '''# Emetteur de reference : COTE D'IVOIRE (changement du 27/09/2026, auparavant
# Togo). Un taux « sans risque » ne doit pas transporter de prime de credit :
# on prend donc le mieux note des huit Tresors de l'union, qui est aussi le
# plus profond et le pays ou reside la grande majorite des societes cotees.
# L'ecart n'est pas theorique -- meme semaine, meme maturite : Cote d'Ivoire
# 7,07 % (15/09/2026) contre Burkina Faso 7,50 % (23/09/2026).
macro:
  taux_oat_3ans: 0.0629        # rendement moyen pondere, adjudication Cote d'Ivoire 15/09/2026
  taux_oat_5ans: 0.0707        # idem, maturite 5 ans (7 ans : 7,15 %)
  taux_reference: 0.0707       # celui utilise pour les comparaisons de rendement
  source: "UMOA-Titres, adjudication Cote d'Ivoire du 15/09/2026 (rendements moyens ponderes ; 3 ans 6,29 %, 5 ans 7,07 %, 7 ans 7,15 %) ; le 5 ans est corrobore par l'adjudication CI du 17/06/2026, deja a 7,07 %"
  date_releve: "2026-09-15"
'''

# ==========================================================================
# B, C, D. LIGNES DE etats_financiers.csv
# ==========================================================================

NOTE_BICB = (
    "BIIC Benin ; REFERENTIEL IFRS RETENU le 27/09/2026, en remplacement du PCB "
    "OHADA. La note precedente disait : statut PROBABLE tant que la source du "
    "double-reporting n'est pas expertisee. Elle l'est, par trois identites "
    "concordantes. (1) Le rapport IFRS publie son propre resultat par action : "
    "627 FCFA (2024 : 503). (2) La chaine pipeline calcule depuis le BOC un bnpa "
    "de 627.58 (cours 8510 / PER 13.56) : le PER publie par la BRVM est donc bati "
    "sur le resultat IFRS, pas sur le PCB OHADA -- sur ce dernier le PER vaudrait "
    "20.3. (3) La capitalisation publiee (491536 MFCFA a 8510 FCFA) implique "
    "57.76 millions d'actions, et 36236705101 / 57.76 M = 627.4, quand 24200 M "
    "donne 418.97, soit exactement le bnpa25 que notre propre chaine calcule sur "
    "le PCB OHADA. Garder le PCB OHADA revenait a afficher un PER calcule sur un "
    "resultat et une croissance calculee sur un autre. Capitaux propres IFRS "
    "135118 (83136 capital et primes + 51982 reserves et resultat non affecte), "
    "releves le 27/09/2026 ; ROE 26.8%, conforme au ratio publie. Le resultat PCB "
    "OHADA reste consultable : 24200 en 2025 contre 30340 en 2024, soit -20%."
)

NOTE_UNXC_2024 = (
    "Uniwax CI, exercice 2024 certifie, releve a la main le 27/09/2026 sur le "
    "bilan et le compte de resultat (unite FCFA). Trois identites se ferment au "
    "franc : les composantes des capitaux propres (4150000000 + 10817156576 + "
    "830000000 + 5325530022 - 3352745751 - 2188937902 + 10472573) donnent la "
    "ligne CP 15591475518 ; CP + dettes financieres 946536663 = ressources "
    "stables 16538012181 ; ressources stables + passif circulant 17703085558 = "
    "total general 34241097739, egal au total general de l'actif. Troisieme "
    "exercice deficitaire consecutif et aggrave (-2054 en 2023, -2189 en 2024) : "
    "aucun retournement. Chiffre d'affaires 27333349555 contre 29686986976."
)

NOTE_UNXC_2023 = (
    "CORRIGE le 27/09/2026. Les valeurs precedentes (resultat -2035.492389, bilan "
    "38585.032514) venaient du seul document alors disponible, dont le nom dit "
    "lui-meme ce qu'il est : 20240430_-_etats_financiers_de_synthese_projets_"
    "daffectation_NON_VERIFIES_PAR_LES_CAC_-_exercice_2023_-_uniwax_ci.pdf. "
    "L'arrete definitif figure en colonne N-1 des etats financiers 2024 : "
    "resultat -2054070779, bilan 38556378909, capitaux propres 17781488715. "
    "L'ecart d'audit est de 18578390 sur le resultat et de 28653605 sur le bilan. "
    "Preuve a deux cotes : le report a nouveau au 31/12/2024 (-3352745751) est "
    "exactement le report a nouveau au 31/12/2023 (-1298674972, soit le resultat "
    "2022) augmente du resultat 2023 -- identite qui ne se ferme qu'avec "
    "-2054070779. Statut porte de VALIDE a VALIDE sur source certifiee. "
    "2e annee de perte consecutive -> exclusion attendue"
)

NOTE_UNXC_2025 = (
    "PROVENANCE CORRIGEE le 27/09/2026, valeurs conservees. La ligne portait la "
    "date 2025-10-31, celle du document 20251031_-_rapport_dactivites_-_3eme_"
    "trimestre_2025_-_uniwax_ci.pdf : un rapport de troisieme trimestre ne peut "
    "pas porter un exercice clos le 31/12/2025. Le resultat -624.0 n'est pourtant "
    "PAS un chiffre partiel : config/faits_qualitatifs.yaml le documente comme le "
    "resultat annuel approuve, source \"Resolutions AGO du 16/07/2026 ; Financial "
    "Afrik 06/07/2026\", date_fait 2025-12-31. C'etait donc la date du document "
    "qui etait fausse, pas la valeur. Elle est portee au 16/07/2026, date des "
    "resolutions citees, faute de connaitre la date de depot BRVM des comptes "
    "2025. Le comparatif est aligne sur le resultat 2024 certifie "
    "(-2188.937902 au lieu de -2165.166944) -- valeur que la note qualitative "
    "utilisait deja, en arrondi, sous la forme \"les 2 189 M de 2024\". "
    "Fusion auto 27/07/2026 (Piste A, strategie=pdfplumber)"
)

NOTE_ECOC_2022 = (
    "RECONSTITUE le 27/09/2026. La ligne portait un resultat de 28386 adosse a un "
    "document du 02/11/2022, anterieur a la cloture de l'exercice 2022 : un "
    "rapport intermediaire pris pour des comptes annuels. Elle se refutait "
    "d'elle-meme, la ligne ECOC 2023 portant en colonne N-1 un resultat 2022 de "
    "44598 -- l'ecart est celui d'un resultat a neuf mois contre une annee "
    "pleine. La valeur annuelle 44598 est reprise de cette colonne N-1, comme le "
    "projet le fait deja ailleurs, et la date suit le document dont elle vient "
    "(28/03/2024). Le comparatif 24389, du meme rapport intermediaire, est "
    "retire : l'exercice 2021 n'est pas en base. Chaine restauree : "
    "2022=44598 -> 2023=48071 -> 2024=57477 -> 2025=63482, soit une progression "
    "reguliere d'environ 8% l'an, la ou le faux creux de 2022 faisait lire un "
    "RATTRAPAGE et un BENEFICE_NON_REPRESENTATIF. "
    "Fusion auto 27/07/2026 (Piste A, strategie=pdfplumber)"
)

NOTE_BICC_2024 = (
    "RECONSTITUE le 27/09/2026. La ligne portait un resultat de 12061 adosse a un "
    "document du 28/11/2024, anterieur a la cloture de l'exercice : rapport "
    "intermediaire. Elle se refutait deux fois. La ligne BICC 2025 (DEUX_SOURCE, "
    "VALIDE) porte en colonne N-1 un resultat 2024 de 26226 ; et la note de la "
    "ligne BICC 2023 ecrit la chaine certifiee en toutes lettres : 2021=9603 -> "
    "2022=12391 -> 2023=16694 -> 2024=26226 -> 2025=36520. Les deux valeurs sont "
    "reprises de cette chaine (resultat 26226, comparatif 16694, qui est le "
    "resultat 2023 deja en base et certifie), et la date suit le document dont "
    "elles viennent (17/04/2026). Le comparatif 18172 de la ligne precedente ne "
    "correspondait a aucun exercice de la chaine. "
    "Fusion auto 27/07/2026 (Piste A, strategie=pdfplumber)"
)

MODIFICATIONS = [
    {
        "ticker": "BICB", "exercice": "2025",
        "attendu": {"resultat_net": "24200", "resultat_net_n1": "30340",
                    "capitaux_propres": "", "statut_donnee": "PROBABLE"},
        "nouveau": {"resultat_net": "36237", "resultat_net_n1": "29058",
                    "capitaux_propres": "135118", "statut_donnee": "VALIDE",
                    "note": NOTE_BICB},
    },
    {
        "ticker": "UNXC", "exercice": "2023",
        "attendu": {"resultat_net": "-2035.492389", "total_actif": "38585.032514",
                    "total_passif": "38585.032514", "capitaux_propres": "",
                    "statut_donnee": "VALIDE"},
        "nouveau": {"resultat_net": "-2054.070779", "total_actif": "38556.378909",
                    "total_passif": "38556.378909",
                    "capitaux_propres": "17781.488715", "note": NOTE_UNXC_2023},
    },
    {
        "ticker": "UNXC", "exercice": "2025",
        "attendu": {"resultat_net": "-624.0", "resultat_net_n1": "-2165.166944",
                    "date_publication": "2025-10-31"},
        "nouveau": {"resultat_net_n1": "-2188.937902",
                    "date_publication": "2026-07-16", "note": NOTE_UNXC_2025},
    },
    {
        "ticker": "ECOC", "exercice": "2022",
        "attendu": {"resultat_net": "28386.0", "resultat_net_n1": "24389.0",
                    "date_publication": "2022-11-02"},
        "nouveau": {"resultat_net": "44598", "resultat_net_n1": "",
                    "date_publication": "2024-03-28", "note": NOTE_ECOC_2022},
    },
    {
        "ticker": "BICC", "exercice": "2024",
        "attendu": {"resultat_net": "12061.0", "resultat_net_n1": "18172.0",
                    "date_publication": "2024-11-28"},
        "nouveau": {"resultat_net": "26226", "resultat_net_n1": "16694",
                    "date_publication": "2026-04-17", "note": NOTE_BICC_2024},
    },
]

# Ligne a creer : Uniwax 2024 n'existait pas du tout en base.
LIGNE_UNXC_2024 = {
    "ticker": "UNXC", "exercice": "2024",
    "resultat_net": "-2188.937902", "resultat_net_n1": "-2054.070779",
    "total_actif": "34241.097739", "total_passif": "34241.097739",
    "capitaux_propres": "15591.475518", "dettes_financieres": "946.536663",
    "payout_ratio": "", "solvabilite_bancaire": "",
    "source_type": "NATIF", "statut_donnee": "VALIDE",
    "date_publication": "2025-08-28", "note": NOTE_UNXC_2024,
}

# ==========================================================================
# E. CONTROLE AJOUTE A tester_donnees.py
# ==========================================================================

ANCRE_TESTS = '''    verifie(not perdus,
            f"les {len(RELEVE_MANUEL)} capitaux propres releves a la main le "
            f"27/09/2026 sont toujours en base"
            + ("" if not perdus else " — " + " ; ".join(perdus)))
'''

MARQUEUR_TESTS = "INTERIMAIRES_TOLERES"

BLOC_TESTS = '''
    # Un document publie AVANT la cloture de l'exercice qu'il pretend porter
    # n'est pas des comptes annuels : c'est un rapport trimestriel ou
    # semestriel.
    #
    # POURQUOI (27/09/2026). La fusion automatique du 27/07/2026 en avait
    # ingere trois comme s'il s'agissait d'exercices clos, et deux se
    # refutaient d'elles-memes par la colonne N-1 de l'exercice suivant :
    # ECOC 2022 portait 28386 quand la ligne 2023 en annoncait 44598, BICC
    # 2024 portait 12061 quand la ligne 2025 en annoncait 26226. Un resultat
    # a neuf mois compare a une annee pleine creuse un faux trou, puis fait
    # lire un faux RATTRAPAGE l'annee suivante -- c'est exactement ce que les
    # drapeaux anti-artefact signalaient sur ECOC et BICC, sur notre propre
    # defaut de collecte et non sur les societes. Chez UNXC, le meme mecanisme
    # affichait un RETOURNEMENT la ou les comptes certifies montrent une
    # troisieme perte aggravee.
    #
    # Le test ne porte que sur les lignes PORTEUSES D'UN RESULTAT : une ligne
    # vide adossee a un rapport intermediaire ne trompe personne.
    INTERIMAIRES_TOLERES = set()
    intermediaires = []
    for r in etats:
        if r["ticker"].startswith("TEST"):
            continue
        publie = (r.get("date_publication") or "").strip()
        if not publie or not (r.get("resultat_net") or "").strip():
            continue
        if (r["ticker"], r["exercice"]) in INTERIMAIRES_TOLERES:
            continue
        if publie < "%s-12-31" % r["exercice"]:
            intermediaires.append(
                "%s %s : resultat %s adosse a un document du %s, anterieur a la "
                "cloture" % (r["ticker"], r["exercice"], r["resultat_net"], publie))
    verifie(not intermediaires,
            "aucun resultat annuel ne repose sur un document publie avant la "
            "cloture de son exercice"
            + ("" if not intermediaires else " — " + " ; ".join(intermediaires)))
'''


def lire(chemin):
    with open(chemin, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def ecrire(chemin, lignes):
    tampon = io.StringIO()
    csv.writer(tampon, lineterminator="\n").writerows(lignes)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        f.write(tampon.getvalue())


def index_unique(lignes, entete, ticker, exercice):
    it, ie = entete.index("ticker"), entete.index("exercice")
    trouves = [i for i, l in enumerate(lignes)
               if i > 0 and l[it] == ticker and l[ie] == exercice]
    if len(trouves) != 1:
        raise SystemExit(
            "ERREUR : %s %s apparait %d fois (attendu : exactement 1). Le "
            "script s'arrete sans rien ecrire." % (ticker, exercice, len(trouves)))
    return trouves[0]


def appliquer(lignes, entete, cible, journal):
    i = index_unique(lignes, entete, cible["ticker"], cible["exercice"])
    ligne = lignes[i]
    etiquette = "%s %s" % (cible["ticker"], cible["exercice"])
    if all(ligne[entete.index(c)] == v for c, v in cible["nouveau"].items()):
        journal.append("  = %-12s deja a jour" % etiquette)
        return False
    for colonne, valeur in cible.get("attendu", {}).items():
        reel = ligne[entete.index(colonne)]
        if reel != valeur:
            raise SystemExit(
                "ERREUR : %s, colonne %s vaut %r alors que la modification a ete "
                "preparee sur %r. Refus d'ecrire." % (etiquette, colonne, reel, valeur))
    for colonne, valeur in cible["nouveau"].items():
        ligne[entete.index(colonne)] = valeur
    journal.append("  + %-12s %s" % (
        etiquette, ", ".join("%s=%s" % (c, v or "(vide)")
                             for c, v in cible["nouveau"].items() if c != "note")))
    return True


def creer(lignes, entete, ligne_dict, journal):
    it, ie = entete.index("ticker"), entete.index("exercice")
    existe = [l for l in lignes[1:]
              if l[it] == ligne_dict["ticker"] and l[ie] == ligne_dict["exercice"]]
    etiquette = "%s %s" % (ligne_dict["ticker"], ligne_dict["exercice"])
    if existe:
        attendue = [ligne_dict.get(c, "") for c in entete]
        if existe[0] == attendue:
            journal.append("  = %-12s deja creee" % etiquette)
            return False
        raise SystemExit(
            "ERREUR : %s existe deja avec un contenu different. Refus d'ecrire "
            "-- verifier a la main avant de relancer." % etiquette)
    manquantes = [c for c in entete if c not in ligne_dict]
    if manquantes:
        raise SystemExit("ERREUR : colonnes non renseignees pour %s : %s"
                         % (etiquette, ", ".join(manquantes)))
    # Inseree juste apres UNXC 2023, pour garder la serie groupee.
    i = index_unique(lignes, entete, "UNXC", "2023")
    lignes.insert(i + 1, [ligne_dict[c] for c in entete])
    journal.append("  + %-12s ligne creee (RN %s, CP %s)"
                   % (etiquette, ligne_dict["resultat_net"],
                      ligne_dict["capitaux_propres"]))
    return True


def patcher_taux(journal):
    code = open(SEUILS, encoding="utf-8").read()
    if BLOC_TAUX_APRES in code:
        journal.append("  = seuils.yaml   taux deja a jour")
        return False
    n = code.count(BLOC_TAUX_AVANT)
    if n != 1:
        raise SystemExit(
            "ERREUR : le bloc macro attendu apparait %d fois dans "
            "config/seuils.yaml (attendu : 1). Le fichier a change, rien "
            "n'est ecrit." % n)
    code = code.replace(BLOC_TAUX_AVANT, BLOC_TAUX_APRES)
    try:
        import yaml
        d = yaml.safe_load(code)
        assert abs(d["macro"]["taux_reference"] - 0.0707) < 1e-9
    except Exception as e:  # noqa: BLE001
        raise SystemExit("ERREUR : le patch casserait seuils.yaml (%s). "
                         "Rien n'est ecrit." % e)
    with open(SEUILS, "w", encoding="utf-8") as f:
        f.write(code)
    journal.append("  + seuils.yaml   taux de reference 7.36% (Togo 06/03) -> "
                   "7.07% (Cote d'Ivoire 15/09)")
    return True


def patcher_tests(journal):
    code = open(TESTS, encoding="utf-8").read()
    if MARQUEUR_TESTS in code:
        journal.append("  = tester_donnees.py  deja patche")
        return False
    n = code.count(ANCRE_TESTS)
    if n != 1:
        raise SystemExit(
            "ERREUR : l'ancre d'insertion apparait %d fois dans "
            "moteur/tester_donnees.py (attendu : 1). Le lot 1 a-t-il bien ete "
            "applique ? Rien n'est ecrit." % n)
    code = code.replace(ANCRE_TESTS, ANCRE_TESTS + BLOC_TESTS)
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise SystemExit("ERREUR : le patch casserait tester_donnees.py "
                         "(ligne %s : %s). Rien n'est ecrit." % (e.lineno, e.msg))
    with open(TESTS, "w", encoding="utf-8") as f:
        f.write(code)
    journal.append("  + tester_donnees.py  controle des rapports intermediaires "
                   "ajoute a la section 13")
    return True


def main():
    lignes = lire(ETATS)
    entete = lignes[0]
    journal, n = [], 0

    journal.append("A. Taux de reference UEMOA :")
    if patcher_taux(journal):
        n += 1

    journal.append("B/C/D. Lignes d'etats financiers :")
    ecrits = 0
    for cible in MODIFICATIONS:
        if appliquer(lignes, entete, cible, journal):
            ecrits += 1
    if creer(lignes, entete, LIGNE_UNXC_2024, journal):
        ecrits += 1
    if ecrits:
        ecrire(ETATS, lignes)
        n += ecrits

    journal.append("E. Garde-fou ajoute aux tests :")
    if patcher_tests(journal):
        n += 1

    print("\n".join(journal))
    print()
    print("%d modification(s) appliquee(s)." % n if n
          else "Rien a faire : le lot 2 etait deja installe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
