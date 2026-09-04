#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de non-regression sur les DONNEES et l'APPLICATION.

POURQUOI CE FICHIER EXISTE (04/09/2026).
tester.py couvre le moteur : signaux, gate, profils, seuils. Trois regressions
sont pourtant passees en une seule semaine sans qu'aucun de ses 28 tests ne
bronche, parce qu'aucune ne portait sur le moteur :

  1. CONFLIT DE DEPENDANCE — starlette 1.4.0 a rendu obligatoire un parametre de
     GZipResponder que Streamlit 1.61.0 n'envoie pas. L'application ne demarrait
     plus du tout (500 sur tous les health checks). Detectable par un simple
     lancement de app.py.

  2. RETARD DE DONNEES — le moteur et l'application lisaient cours_mensuels
     (bulletins de fin de mois, arretes au 07/07/2026) alors que la collecte
     quotidienne allait jusqu'au 01/09. Pres de deux mois d'ecart, invisible
     parce que rien ne surveillait la fraicheur.

  3. DECALAGE POSITIONNEL — apres la migration vers les cours quotidiens,
     piv.shift(12) ne valait plus 12 mois mais 12 SEANCES. Le tableau de bord
     affichait "+6 % sur douze mois" au lieu de +93 %, et annoncait un "marche
     calme" en pleine fin de rallye. C'est l'utilisateur qui l'a vu, pas les
     tests : "l'evolution du marche en 24 mois depasse largement les 8 %".

Ces trois defauts partagent un trait : ils ne cassent RIEN. Le code s'execute,
les chiffres s'affichent, ils sont simplement faux. Un test unitaire classique
ne les voit pas — il faut confronter le systeme a une mesure INDEPENDANTE ou a
une attente de bon sens. C'est ce que fait ce fichier.

SEPARATION DES ROLES :
  - BLOQUANT : les tests de COHERENCE (un calcul qui se contredit lui-meme est
    un bug, il ne faut pas deployer).
  - NON BLOQUANT : les tests de FRAICHEUR (un retard de collecte est une alerte
    d'exploitation, pas une raison d'empecher un commit de code).
Le code de sortie distingue les deux : 0 = tout va bien, 1 = incoherence
bloquante, 2 = alertes de fraicheur uniquement.

Usage :
    python3 moteur/tester_donnees.py            # tout
    python3 moteur/tester_donnees.py --sans-app # sans le lancement Streamlit
"""
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
DB = ICI / "brvm.db"
APP = RACINE / "app.py"

BLOQUANTS = []
ALERTES = []


def verifie(cond, message, bloquant=True):
    if cond:
        print(f"  [OK] {message}")
        return True
    etiquette = "ECHEC" if bloquant else "ALERTE"
    print(f"  [{etiquette}] {message}")
    (BLOQUANTS if bloquant else ALERTES).append(message)
    return False


def jours_ouvres(depuis, jusqua):
    """Jours ouvres entre deux dates, sans dependance a numpy."""
    n, courant = 0, depuis
    while courant < jusqua:
        courant = date.fromordinal(courant.toordinal() + 1)
        if courant.weekday() < 5:
            n += 1
    return n


# ----------------------------------------------------------------------
# 1. FRAICHEUR (non bloquant)
# ----------------------------------------------------------------------
def test_fraicheur():
    print("\n=== 1. Fraicheur des donnees (non bloquant) ===")
    if not DB.exists():
        verifie(False, "brvm.db absente — lancer peupler.py puis charger_cours*.py",
                bloquant=False)
        return
    cur = sqlite3.connect(DB).cursor()
    try:
        derniere = cur.execute(
            "SELECT MAX(date_bulletin) FROM cours_quotidien_boc").fetchone()[0]
    except Exception:
        derniere = None
    if not verifie(derniere is not None,
                   "table cours_quotidien_boc alimentee "
                   "(sinon le pont charger_cours_quotidien.py n'a pas tourne)",
                   bloquant=False):
        return

    d = datetime.strptime(str(derniere)[:10], "%Y-%m-%d").date()
    manquees = jours_ouvres(d, date.today())
    verifie(manquees <= 3,
            f"derniere seance {d} — {manquees} seance(s) manquee(s) "
            f"(au-dela de 3, verifier les workflows P11 et P9)",
            bloquant=False)

    # Trous dans l'historique recent : une collecte qui tourne un jour sur deux
    # produit des donnees "fraiches" mais incompletes — l'incident du 25-26/08.
    recentes = [r[0][:10] for r in cur.execute(
        "SELECT DISTINCT date_bulletin FROM cours_quotidien_boc "
        "ORDER BY date_bulletin DESC LIMIT 15").fetchall()]
    if len(recentes) >= 2:
        plus_ancienne = datetime.strptime(recentes[-1], "%Y-%m-%d").date()
        attendues = jours_ouvres(plus_ancienne, d) + 1
        verifie(len(recentes) >= attendues - 2,
                f"historique recent complet : {len(recentes)} seances collectees "
                f"pour {attendues} jours ouvres attendus",
                bloquant=False)


# ----------------------------------------------------------------------
# 2. COHERENCE DE FREQUENCE (bloquant)
# ----------------------------------------------------------------------
def test_coherence_frequence():
    """Recalcule la variation du marche par une methode INDEPENDANTE de celle de
    l'application, et compare. C'est le test qui aurait attrape le +6 % au lieu
    de +93 % : un decalage positionnel et un decalage temporel ne peuvent pas
    donner le meme resultat si la frequence n'est pas mensuelle."""
    print("\n=== 2. Coherence du calcul de regime (bloquant) ===")
    if not DB.exists():
        verifie(False, "brvm.db absente", bloquant=False)
        return
    try:
        import pandas as pd
    except ImportError:
        verifie(True, "pandas absent — test ignore", bloquant=False)
        return

    conn = sqlite3.connect(DB)
    try:
        cours = pd.read_sql_query(
            "SELECT ticker, date_bulletin, cours FROM cours_quotidien_boc "
            "WHERE cours IS NOT NULL", conn)
    except Exception:
        verifie(False, "cours_quotidien_boc illisible", bloquant=False)
        return
    if cours.empty:
        verifie(False, "aucun cours quotidien en base", bloquant=False)
        return

    piv = cours.pivot_table(index="date_bulletin", columns="ticker",
                            values="cours").sort_index()
    piv.index = pd.to_datetime(piv.index)
    fin = piv.index[-1]

    # mesure de reference : decalage TEMPOREL
    cible = fin - pd.DateOffset(months=12)
    anterieures = piv.index[piv.index <= cible]
    if not len(anterieures):
        verifie(True, "moins de 12 mois d'historique — test ignore", bloquant=False)
        return
    ref_temporelle = float((piv.loc[fin] / piv.loc[anterieures[-1]] - 1).median())

    # mesure que produirait un decalage POSITIONNEL de 12 lignes
    ref_positionnelle = float((piv / piv.shift(12) - 1).median(axis=1).dropna().iloc[-1])

    # frequence reelle des donnees
    ecart_median = (piv.index.to_series().diff().dt.days.median())
    verifie(ecart_median is not None and ecart_median <= 7,
            f"les cours sont bien a frequence quotidienne "
            f"(ecart median entre seances : {ecart_median:.0f} j)")

    # Le test central : sur des donnees quotidiennes, les deux methodes DOIVENT
    # diverger. Si elles convergent, c'est que la source est redevenue mensuelle
    # sans que personne ne s'en apercoive.
    divergent = abs(ref_temporelle - ref_positionnelle) > 0.05
    verifie(divergent,
            f"decalage temporel ({ref_temporelle:+.1%}) et positionnel "
            f"({ref_positionnelle:+.1%}) divergent comme attendu en quotidien")

    # L'application doit utiliser la methode TEMPORELLE.
    # On analyse l'AST et non le texte brut : au premier essai, ce test echouait
    # sur app.py CORRIGE, parce que la chaine "shift(12)" apparaissait dans le
    # COMMENTAIRE documentant le correctif. Un test qui lit des commentaires
    # comme du code produit exactement le genre de faux positif qui finit par
    # faire desactiver la suite entiere.
    if APP.exists():
        import ast
        arbre = ast.parse(APP.read_text(encoding="utf-8"))
        appels_shift = [n for n in ast.walk(arbre)
                        if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "shift"]
        noms = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
        noms |= {n.attr for n in ast.walk(arbre) if isinstance(n, ast.Attribute)}
        verifie(not appels_shift and "DateOffset" in noms,
                "app.py calcule le regime par decalage temporel (DateOffset) "
                f"et non par shift() positionnel ({len(appels_shift)} appel(s) "
                f"a .shift() dans le code executable)")

    # Ordre de grandeur : une variation annuelle mediane hors de [-60 %, +300 %]
    # sur un marche entier signale une erreur de calcul plutot qu'un marche.
    verifie(-0.60 <= ref_temporelle <= 3.00,
            f"variation 12 mois du marche plausible : {ref_temporelle:+.1%}")


# ----------------------------------------------------------------------
# 3. SOURCE DES COURS (bloquant)
# ----------------------------------------------------------------------
def test_source_cours():
    print("\n=== 3. Source de cours utilisee par le moteur (bloquant) ===")
    sys.path.insert(0, str(ICI))
    try:
        from profils import source_cours
    except ImportError:
        verifie(False, "profils.py n'expose pas source_cours() — migration "
                       "vers la source la plus fraiche non appliquee")
        return
    if not DB.exists():
        verifie(False, "brvm.db absente", bloquant=False)
        return
    cur = sqlite3.connect(DB).cursor()
    table, colonne = source_cours(cur)
    verifie(table == "cours_quotidien_boc",
            f"le moteur lit la source la plus fraiche (table retenue : {table})")

    # profils.json doit exposer la date du cours : sans elle, la fraicheur
    # redevient implicite, ce qui est exactement ce qui avait masque le retard.
    import json
    p = RACINE / "collecte" / "profils.json"
    if p.exists():
        profils = json.loads(p.read_text(encoding="utf-8"))
        avec_date = sum(1 for v in profils.values() if v.get("date_cours"))
        verifie(avec_date == len(profils),
                f"profils.json expose la date du cours pour les {len(profils)} titres "
                f"({avec_date} renseignes)")


# ----------------------------------------------------------------------
# 4. DEMARRAGE DE L'APPLICATION (bloquant)
# ----------------------------------------------------------------------
def test_application():
    """Lance reellement app.py. C'est le test qui aurait attrape le conflit
    starlette : aucune erreur de syntaxe, aucun probleme de moteur, mais un
    serveur qui refuse de demarrer."""
    print("\n=== 4. Demarrage de l'application (bloquant) ===")
    if not APP.exists():
        verifie(True, "app.py absent — test ignore", bloquant=False)
        return
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        verifie(True, "streamlit non installe — test ignore "
                      "(l'installer dans le workflow pour l'activer)", bloquant=False)
        return
    try:
        at = AppTest.from_file(str(APP), default_timeout=300).run()
    except Exception as e:
        verifie(False, f"app.py leve une exception au demarrage : {type(e).__name__} — "
                       f"{str(e)[:160]}")
        return
    verifie(len(at.exception) == 0,
            "app.py demarre sans exception"
            + ("" if not at.exception else f" — {at.exception[0].value[:160]}"))
    verifie(len(at.tabs) >= 4, f"les onglets sont rendus ({len(at.tabs)} trouves)")


# ----------------------------------------------------------------------
# 5. JURISPRUDENCE DU DRAPEAU RESULTAT_NON_OPERATIONNEL (bloquant)
# ----------------------------------------------------------------------
def test_resultat_non_operationnel():
    """Verrouille le comportement du drapeau sur les deux cas de reference.

    AGL CI (SDSC) est le cas FONDATEUR : en 2024, son resultat net de
    21 069 M provenait a 96 % du financier (resultat d'exploitation : 942 M).
    Le profilage y lisait une croissance GARP de +14,8 %/an ; l'exercice 2025 a
    fait tomber le resultat net de 96 %. Le drapeau doit se declencher.

    SAPH (SPHC) est le CONTRE-EXEMPLE, tout aussi important : son resultat
    d'exploitation (38 130 M) DEPASSE son resultat net (24 972 M). Sa croissance
    est pleinement operationnelle et le drapeau ne doit PAS se declencher. Sans
    ce second cas, rien n'empecherait de durcir le seuil jusqu'a marquer toute
    la cote — un drapeau qui se leve partout ne signale plus rien.
    """
    print("\n=== 5. Drapeau RESULTAT_NON_OPERATIONNEL (bloquant) ===")
    import json
    p = RACINE / "collecte" / "profils.json"
    if not p.exists():
        verifie(False, "profils.json absent — lancer profils.py", bloquant=False)
        return
    profils = json.loads(p.read_text(encoding="utf-8"))

    sdsc = profils.get("SDSC", {})
    verifie("RESULTAT_NON_OPERATIONNEL" in (sdsc.get("drapeaux") or []),
            "SDSC (AGL CI) porte le drapeau : resultat majoritairement non "
            f"operationnel (part mesuree : {sdsc.get('part_operationnelle')})")
    verifie(sdsc.get("grade") == "C",
            f"SDSC est plafonne en grade C (grade actuel : {sdsc.get('grade')})")

    sphc = profils.get("SPHC", {})
    verifie("RESULTAT_NON_OPERATIONNEL" not in (sphc.get("drapeaux") or []),
            "SPHC (SAPH) ne porte PAS le drapeau : croissance operationnelle "
            f"(part mesuree : {sphc.get('part_operationnelle')})")

    # Le drapeau doit rester RARE : s'il touche plus du quart des titres
    # renseignes, le seuil est mal calibre.
    renseignes = [v for v in profils.values() if v.get("part_operationnelle") is not None]
    marques = [v for v in renseignes
               if "RESULTAT_NON_OPERATIONNEL" in (v.get("drapeaux") or [])]
    if renseignes:
        verifie(len(marques) <= max(1, len(renseignes) // 4),
                f"le drapeau reste discriminant : {len(marques)} titre(s) marque(s) "
                f"sur {len(renseignes)} renseigne(s)")


def main():
    sans_app = "--sans-app" in sys.argv
    print("=" * 60)
    print("TESTS DE NON-REGRESSION — donnees et application")
    print("=" * 60)
    test_fraicheur()
    test_coherence_frequence()
    test_source_cours()
    test_resultat_non_operationnel()
    if not sans_app:
        test_application()

    print("\n" + "=" * 60)
    if BLOQUANTS:
        print(f"RESULTAT : {len(BLOQUANTS)} INCOHERENCE(S) BLOQUANTE(S)")
        for m in BLOQUANTS:
            print(f"  - {m}")
        if ALERTES:
            print(f"  (+ {len(ALERTES)} alerte(s) de fraicheur)")
        return 1
    if ALERTES:
        print(f"RESULTAT : coherence OK, {len(ALERTES)} ALERTE(S) DE FRAICHEUR")
        for m in ALERTES:
            print(f"  - {m}")
        print("  -> la collecte prend du retard ; le code, lui, est sain.")
        return 2
    print("RESULTAT : TOUS LES TESTS DE DONNEES PASSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
