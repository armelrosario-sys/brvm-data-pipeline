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
import os
import sqlite3
import subprocess
import sys
import tempfile
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
        verifie(False, "brvm.db absente — lancer moteur/peupler.py puis charger_cours*.py",
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


# ----------------------------------------------------------------------
# 6. ECHELLE DES GRANDEURS (bloquant)
# ----------------------------------------------------------------------
def test_echelles():
    """Verifie qu'aucune grandeur n'a change d'ORDRE DE GRANDEUR entre deux
    sources censees dire la meme chose.

    Bug detecte le 10/09/2026 par l'utilisateur, sur le graphique et non par les
    tests : charger_cours_quotidien.py divisait le rendement par 100, alors que
    le CSV le stocke deja en fraction. Le rendement passait de 4,93 % a 0,0493 %.
    Rien ne plantait ; deux effets silencieux :
      - le profil RENDEMENT devenait inatteignable (seuil 4,8 %) ;
      - le payout implicite (rendement x PER) tombait sous 1 % pour 26 titres,
        donc la condition "payout <= 100 %" passait TOUJOURS, et les societes
        distribuant plus que leur benefice n'etaient plus ecartees.
    Une erreur d'unite ne casse rien : elle deplace des titres. D'ou ce test.
    """
    print("\n=== 6. Echelle des grandeurs (bloquant) ===")
    if not DB.exists():
        verifie(False, "brvm.db absente", bloquant=False)
        return
    cur = sqlite3.connect(DB).cursor()

    # Les rendements des deux tables doivent partager la meme unite.
    try:
        med_q = cur.execute(
            "SELECT rendement FROM cours_quotidien_boc WHERE rendement IS NOT NULL "
            "AND rendement < 0.5 ORDER BY rendement LIMIT 1 OFFSET "
            "(SELECT COUNT(*)/2 FROM cours_quotidien_boc WHERE rendement IS NOT NULL "
            "AND rendement < 0.5)").fetchone()
        med_m = cur.execute(
            "SELECT rendement FROM cours_mensuels WHERE rendement IS NOT NULL "
            "AND rendement < 0.5 ORDER BY rendement LIMIT 1 OFFSET "
            "(SELECT COUNT(*)/2 FROM cours_mensuels WHERE rendement IS NOT NULL "
            "AND rendement < 0.5)").fetchone()
    except Exception:
        med_q = med_m = None
    if med_q and med_m and med_q[0] and med_m[0]:
        rapport = med_q[0] / med_m[0]
        verifie(0.2 <= rapport <= 5.0,
                f"rendements quotidien et mensuel a la meme echelle "
                f"(medianes {med_q[0]:.4f} et {med_m[0]:.4f}, rapport {rapport:.2f})")

    # Un rendement median de marche hors de [1 %, 12 %] signale une unite fausse
    # bien avant de signaler un marche extraordinaire.
    if med_q and med_q[0]:
        verifie(0.01 <= med_q[0] <= 0.12,
                f"rendement median plausible : {med_q[0]*100:.2f} %")

    # Le profil RENDEMENT ne doit pas disparaitre entierement : sur un marche ou
    # la mediane depasse 4 %, zero titre classe signale un seuil devenu
    # inatteignable, donc une unite fausse en amont.
    import json
    f = RACINE / "collecte" / "profils.json"
    if f.exists():
        profils = json.loads(f.read_text(encoding="utf-8"))
        dys = [v["dy"] for v in profils.values() if v.get("dy") is not None]
        if dys:
            dys.sort()
            mediane = dys[len(dys) // 2]
            verifie(1.0 <= mediane <= 12.0,
                    f"rendements de profils.json en POURCENTAGE "
                    f"(mediane {mediane:.2f})")
        payouts = [v["payout"] for v in profils.values() if v.get("payout") is not None]
        if payouts:
            aberrants = [x for x in payouts if 0 < x < 0.02]
            verifie(len(aberrants) <= max(2, len(payouts) // 10),
                    f"payouts a la bonne echelle : {len(aberrants)} valeur(s) "
                    f"sous 2 % sur {len(payouts)}")


# ----------------------------------------------------------------------
# 7. PER NORMALISE ET OPERATIONS SUR TITRE (bloquant)
# ----------------------------------------------------------------------
def test_per_normalise_et_operations():
    """Deux controles issus des constats du 12/09/2026.

    (a) PER normalise : le PER affiche se calcule sur le DERNIER benefice. Quand
        celui-ci est un pic, le titre parait bon marche alors qu'il est cher.
        Ecarts mesures : SLBC 13,6 -> 29,9 ; BICC 15,1 -> 29,4. Le drapeau
        BENEFICE_NON_REPRESENTATIF doit rester actif et discriminant.

    (b) Operations sur titre : SOLIBRA a divise son nominal le 27/09/2024 (cours
        de ~95 000 a 10 215 en une seance) sans que l'operation soit enregistree.
        Toutes ses performances sur deux ans en etaient faussees. Une chute de
        plus de 60 % en une seule seance est presque toujours une division de
        nominal, pas un krach : on la signale.
    """
    print("\n=== 7. PER normalise et operations sur titre (bloquant) ===")
    import json
    f = RACINE / "collecte" / "profils.json"
    if not f.exists():
        verifie(False, "profils.json absent", bloquant=False)
        return
    profils = json.loads(f.read_text(encoding="utf-8"))

    calcules = [v for v in profils.values() if v.get("per_normalise") is not None]
    verifie(len(calcules) >= 15,
            f"PER normalise calcule pour {len(calcules)} titres "
            f"(sous 15, l'historique des resultats est trop court)")
    marques = [v for v in calcules
               if "BENEFICE_NON_REPRESENTATIF" in (v.get("drapeaux") or [])]
    verifie(1 <= len(marques) <= max(2, len(calcules) // 3),
            f"le drapeau BENEFICE_NON_REPRESENTATIF reste discriminant : "
            f"{len(marques)} titre(s) sur {len(calcules)}")

    # Le taux sans risque doit etre present et plausible pour la zone.
    taux = {v.get("taux_reference") for v in profils.values() if v.get("taux_reference")}
    verifie(len(taux) == 1 and 0.03 <= list(taux)[0] <= 0.15,
            f"taux de reference UEMOA renseigne et plausible : {taux}")

    # (b) divisions de nominal non enregistrees
    csv_cours = RACINE / "collecte" / "cours_quotidien_boc.csv"
    ops = RACINE / "collecte" / "operations_sur_titre.csv"
    if csv_cours.exists():
        try:
            import pandas as pd
        except ImportError:
            return
        c = pd.read_csv(csv_cours, parse_dates=["date_bulletin"])
        c = c.sort_values(["ticker", "date_bulletin"])
        c["var"] = c.groupby("ticker").cours.pct_change()
        # on ignore les erreurs de saisie manifestes (facteur ~1000)
        suspects = c[(c["var"] < -0.60) & (c["var"] > -0.995)]
        connues = set()
        if ops.exists():
            o = pd.read_csv(ops)
            connues = {(r.ticker, str(r.date)[:7]) for r in o.itertuples()}
        non_tracees = [(r.ticker, str(r.date_bulletin)[:10])
                       for r in suspects.itertuples()
                       if (r.ticker, str(r.date_bulletin)[:7]) not in connues]
        verifie(len(non_tracees) == 0,
                "aucune division de nominal non enregistree"
                + ("" if not non_tracees
                   else f" — a documenter dans operations_sur_titre.csv : {non_tracees}"),
                bloquant=False)


# ----------------------------------------------------------------------
# 8. VEILLE DES AVIS BRVM (bloquant)
# ----------------------------------------------------------------------
def test_avis_brvm():
    """Verifie que la veille des avis officiels alimente bien le moteur.

    Ajout du 18/09/2026. Trois faits officiels etaient invisibles dans l'outil :
    les suspensions de cotation (Sucrivoire, SICOR, SONOCO au 16/09/2026), les
    projets de fractionnement (AGE Sonatel) et les paiements de dividendes. Un
    titre suspendu ne peut etre ni achete ni vendu : le profiler sans le dire est
    trompeur. Un fractionnement non enregistre fausse toute la serie de cours —
    c'est deja arrive sur Solibra, et le controle des divisions de nominal en a
    trouve douze non documentees.
    """
    print("\n=== 8. Veille des avis BRVM (bloquant) ===")
    import json
    fichier = RACINE / "collecte" / "avis_brvm.csv"
    verifie(fichier.exists(),
            "collecte/avis_brvm.csv present (sinon la veille n'a jamais tourne)",
            bloquant=False)
    f = RACINE / "collecte" / "profils.json"
    if not f.exists():
        return
    profils = json.loads(f.read_text(encoding="utf-8"))

    avec_statut = sum(1 for v in profils.values() if v.get("statut_cotation"))
    verifie(avec_statut == len(profils),
            f"statut de cotation expose pour les {len(profils)} titres "
            f"({avec_statut} renseignes)")

    suspendus = [t for t, v in profils.items() if v.get("statut_cotation") == "SUSPENDU"]
    # Un titre suspendu ne peut pas etre presente comme exploitable tel quel.
    mal_gradues = [t for t in suspendus if profils[t].get("grade") == "A"]
    verifie(not mal_gradues,
            f"aucun titre suspendu en grade A (suspendus : {suspendus or 'aucun'})")

    # Une alerte d'operation sur capital doit remonter dans les notes du titre.
    if fichier.exists():
        import csv as _csv
        with fichier.open(encoding="utf-8") as fh:
            lignes = list(_csv.DictReader(fh))
        frac = [x for x in lignes
                if x.get("type") in ("FRACTIONNEMENT", "AUGMENTATION_CAPITAL")
                and x.get("ticker")]
        for x in frac[:3]:
            notes = " ".join(profils.get(x["ticker"], {}).get("notes") or [])
            verifie("AVIS BRVM" in notes,
                    f"l'operation sur capital de {x['ticker']} ({x['type']}, "
                    f"{x['date_avis']}) est signalee sur sa fiche")


# ----------------------------------------------------------------------
# 9. FRAICHEUR DES FONDAMENTAUX ET EXERCICE EN COURS (bloquant)
# ----------------------------------------------------------------------
def test_fondamentaux_a_jour():
    """Trois controles issus de la comparaison SGBC / BOAC du 18/09/2026.

    (a) Aucun ROE ne doit etre affiche s'il repose sur des capitaux propres de
        plus de trois ans. SGBC affichait 22,1 % calcule sur 2021.
    (b) Une croissance calculee sur une serie a trous ne peut pas fonder un
        profil GARP ou GROWTH. SGBC ressortait a +15,9 %/an en reliant 2021 a
        2025 ; son premier semestre 2026 sort a +0,6 %.
    (c) Quand la derniere publication trimestrielle contredit nettement la
        croissance annuelle, le titre doit porter le drapeau. BOAC : +21 %/an
        certifie sur 2022-2025, mais +0,91 % au premier trimestre 2026.
    """
    print("\n=== 9. Fondamentaux a jour et exercice en cours (bloquant) ===")
    import json
    f = RACINE / "collecte" / "profils.json"
    if not f.exists():
        return
    profils = json.loads(f.read_text(encoding="utf-8"))
    annee = date.today().year

    perimes = [t for t, v in profils.items()
               if v.get("roe") is not None and v.get("roe_exercice")
               and annee - v["roe_exercice"] > 3]
    verifie(not perimes,
            f"aucun ROE affiche sur des capitaux propres de plus de 3 ans "
            f"({perimes or 'aucun'})")

    troues_croissance = [t for t, v in profils.items()
                         if "SERIE_TROUEE" in (v.get("drapeaux") or [])
                         and v.get("profil") in ("GARP", "GROWTH")]
    verifie(not troues_croissance,
            f"aucun profil GARP ou GROWTH fonde sur une serie a trous "
            f"({troues_croissance or 'aucun'})")

    boac = profils.get("BOAC", {})
    if boac.get("tendance_intermediaire") is not None:
        verifie("CONTREDIT_PAR_INTERMEDIAIRE" in (boac.get("drapeaux") or []),
                f"BOAC signale : croissance annuelle {boac.get('g')} %/an contre "
                f"{boac['tendance_intermediaire']*100:+.1f} % au "
                f"{boac.get('periode_intermediaire')}")


# ----------------------------------------------------------------------
# 10. COHERENCE DES STATUTS DE COTATION (bloquant)
# ----------------------------------------------------------------------
def test_statuts_cotation():
    """Une levee de suspension ne doit jamais etre lue comme une suspension.

    Bug du 22/09/2026 : l'avis "SUCRIVOIRE S.A. : Levee de suspension de la
    cotation" etait classe SUSPENSION, parce que le motif de levee exigeait
    "levee de LA suspension" alors que la BRVM ecrit "levee DE suspension" — et
    que le libelle contient par ailleurs "suspension de la cotation". Un titre
    redevenu negociable serait reste bloque dans l'outil.
    """
    print("\n=== 10. Coherence des statuts de cotation (bloquant) ===")
    sys.path.insert(0, str(RACINE / "collecte"))
    try:
        import avis_brvm
    except ImportError:
        verifie(True, "collecteur d'avis absent — test ignore", bloquant=False)
        return
    for titre, attendu in (
            ("SUCRIVOIRE S.A. : Levée de suspension de la cotation", "REPRISE_COTATION"),
            ("SICOR S.A : Suspension de la cotation", "SUSPENSION"),
            ("X : Reprise des cotations", "REPRISE_COTATION")):
        verifie(avis_brvm.classer(titre) == attendu,
                f"'{titre[:48]}' classe {avis_brvm.classer(titre)} (attendu {attendu})")


# ----------------------------------------------------------------------
# 11. INTEGRITE DU FICHIER APPLICATION (bloquant)
# ----------------------------------------------------------------------
def test_integrite_app():
    """Verifie qu'app.py contient bien toutes ses sections.

    Ajout du 24/09/2026 apres un incident : une modification par ancrage de
    lignes n'a pas trouve son ancre, est allee jusqu'a la fin du fichier et a
    ECRASE tout ce qui suivait. Le fichier est passe de 943 a 444 lignes et a ete
    commite tel quel. L'application demarrait sans la moindre erreur — elle
    affichait seulement les trois metriques du haut et plus rien d'autre. Aucun
    test existant ne l'a vu : ils verifiaient que l'app ne PLANTE pas, pas
    qu'elle affiche quelque chose.
    Une troncature silencieuse est plus dangereuse qu'un plantage.
    """
    print("\n=== 11. Integrite du fichier application (bloquant) ===")
    app = RACINE / "app.py"
    if not app.exists():
        verifie(False, "app.py absent", bloquant=False)
        return
    code = app.read_text(encoding="utf-8")

    sections = {
        "onglets": 'st.tabs(',
        "repartition des profils": "Repartition des profils",
        "plan decote x croissance": "Plan decote",
        "taux sans risque": "Taux sans risque",
        "onglet Explorer": "Telecharger (CSV)",
        "fiche titre": "Pourquoi ce profil",
        "qualite des donnees": "Limites permanentes",
        "activite (CA, marge)": "Chiffre d'affaires",
    }
    manquantes = [nom for nom, motif in sections.items() if motif not in code]
    verifie(not manquantes,
            f"app.py contient toutes ses sections"
            + ("" if not manquantes else f" — MANQUANTES : {', '.join(manquantes)}"))

    lignes = code.count("\n")
    verifie(lignes >= 700,
            f"app.py fait {lignes} lignes (une chute nette signale une troncature)")

    # Sens de l'axe de valorisation (27/09/2026). La variable montait quand le
    # titre etait BON MARCHE mais s'appelait "cherte" : la fiche affichait
    # "decote marquee (cherte P90)" pour SGBC, a PER 11,94 contre 14,79 de
    # mediane de marche. Le calcul etait juste, le nom disait l'inverse.
    verifie("cherte_pctl" not in code,
            "app.py n'utilise plus cherte_pctl (nom qui disait l'inverse de ce "
            "que la variable mesure)")
    verifie("decote_pctl" in code,
            "app.py lit bien decote_pctl")



# ----------------------------------------------------------------------
# 12. ARBITRAGE CONTRE UNE SOURCE EXTERIEURE (bloquant)
# ----------------------------------------------------------------------
def test_arbitrage():
    """Les onze sections precedentes verifient la coherence INTERNE de la base.

    POURQUOI CETTE SECTION EXISTE (26/09/2026). Une base peut etre parfaitement
    coherente avec elle-meme et fausse. Mesure fondatrice : sur les 37 titres ou
    les deux chaines du projet donnent le glissement du MEME exercice, l'ecart
    median est de 0,0 point -- la saisie manuelle est fiable. Mais deux titres
    avaient les colonnes resultat_net et resultat_net_n1 PERMUTEES, ce qui
    produisait un profil GARP (ECOC, +26,5 %/an affiche) et un profil VALUE
    (BOAS) sur des series au dernier point inverse. Aucun des 28 golden tests ni
    des 11 sections de ce fichier ne l'avait vu, parce qu'aucun ne confronte la
    base a une source EXTERIEURE.

    Trois familles de verifications :
      (a) les regles d'arbitrage sur des cas SYNTHETIQUES, pour qu'elles restent
          vraies independamment de l'etat des donnees du jour ;
      (b) la permutation d'ECOC et de BOAS rejouee sur les chiffres reels, en
          test de non-regression : si quelqu'un re-permute les colonnes, ce test
          tombe ;
      (c) l'etat de la base du jour : aucune permutation ne doit rester ouverte,
          et aucun titre suspendu par arbitrage ne doit porter un profil de style.
    """
    print("\n=== 12. Arbitrage contre une source exterieure (bloquant) ===")
    sys.path.insert(0, str(ICI))
    try:
        import arbitrage as arb
    except ImportError as e:
        verifie(False, f"moteur/arbitrage.py introuvable ou non importable : {e}")
        return

    # --- (a) Les regles, sur des cas synthetiques -----------------------------
    # Une base en memoire : on teste les regles, pas les donnees du jour.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE etats_financiers (ticker TEXT, exercice INTEGER, "
                 "resultat_net REAL, resultat_net_n1 REAL, statut_donnee TEXT, "
                 "source_type TEXT)")
    cas = [
        # ticker, exercice, rn, rn_n1, statut, source_type
        ("CONCORDE", 2025, 110.0, 100.0, "VALIDE", "NATIF"),
        ("CERTIFIE", 2025, 150.0, 100.0, "VALIDE", "NATIF"),
        ("OCRSEUL", 2025, 150.0, 100.0, "PROBABLE", "OCR"),
        ("PERMUTE", 2025, 100.0, 110.0, "VALIDE", "NATIF"),
        ("PERMUTE1", 2025, 100.0, 110.0, "VALIDE", "NATIF"),
        ("RETARD", 2024, 110.0, 100.0, "VALIDE", "NATIF"),
        ("CONTESTE", 2025, 200.0, 100.0, "PROBABLE", "NATIF"),
    ]
    conn.executemany("INSERT INTO etats_financiers VALUES (?,?,?,?,?,?)", cas)
    agr = {
        # concordance : 10,0 % en base contre 9,5 % publie -> ecart 0,5 pt
        "CONCORDE": {"exercice": 2025, "rn": 110.0, "ca": 1000.0,
                     "croissance_rn": 9.5, "marge_nette": 11.0, "seance": None},
        # ligne certifiee en ecart de 30 pts : la base est conservee
        "CERTIFIE": {"exercice": 2025, "rn": 120.0, "ca": 1000.0,
                     "croissance_rn": 20.0, "marge_nette": 12.0, "seance": None},
        # meme ecart, mais la ligne vient d'un OCR a source unique
        "OCRSEUL": {"exercice": 2025, "rn": 120.0, "ca": 1000.0,
                    "croissance_rn": 20.0, "marge_nette": 12.0, "seance": None},
        # permutation confirmee par les DEUX identites (taux + marge)
        "PERMUTE": {"exercice": 2025, "rn": 110.0, "ca": 1100.0,
                    "croissance_rn": 10.0, "marge_nette": 10.0, "seance": None},
        # permutation confirmee par le seul taux : marge incoherente
        "PERMUTE1": {"exercice": 2025, "rn": 110.0, "ca": 1100.0,
                     "croissance_rn": 10.0, "marge_nette": 33.0, "seance": None},
        # l'agregateur a un exercice de plus que la base
        "RETARD": {"exercice": 2025, "rn": 130.0, "ca": 1000.0,
                   "croissance_rn": 18.2, "marge_nette": 13.0, "seance": None},
        # ecart de 100 pts, ligne non certifiee, pas de permutation plausible
        "CONTESTE": {"exercice": 2025, "rn": 100.0, "ca": 1000.0,
                     "croissance_rn": 0.0, "marge_nette": 10.0, "seance": None},
    }
    cur = conn.cursor()
    attendu = {
        "CONCORDE": (1, "CROISSANCE_CORROBOREE"),
        "CERTIFIE": (2, "ECART_AGREGATEUR"),
        "OCRSEUL": (3, "VALEUR_REPRISE_AGREGATEUR"),
        "RETARD": (4, "FONDAMENTAL_EN_RETARD"),
        "PERMUTE": (5, "PERMUTATION_PROBABLE"),
        "PERMUTE1": (5, "PERMUTATION_SUSPECTEE"),
        "CONTESTE": (6, "CROISSANCE_CONTESTEE"),
    }
    for ticker, (regle, drapeau) in sorted(attendu.items(), key=lambda kv: kv[1][0]):
        v = arb.arbitrer(cur, ticker, agr)
        verifie(v["regle"] == regle and v["drapeau"] == drapeau,
                f"regle {regle} ({drapeau}) : {ticker} -> regle {v['regle']} "
                f"/ {v['drapeau']}")

    # Proprietes que les regles doivent respecter, quel que soit le cas
    v_ocr = arb.arbitrer(cur, "OCRSEUL", agr)
    verifie(v_ocr["correctif"] == {2025: 120.0},
            f"regle 3 : la substitution est explicite et journalisee, "
            f"obtenu {v_ocr['correctif']}")
    v_cert = arb.arbitrer(cur, "CERTIFIE", agr)
    verifie(not v_cert["correctif"] and not v_cert["bloquant"],
            "regle 2 : une ligne certifiee n'est JAMAIS reecrite au demarrage "
            "et ne bloque pas le profil")
    for t in ("PERMUTE", "PERMUTE1"):
        v = arb.arbitrer(cur, t, agr)
        verifie(v["bloquant"] and v["axe_retire"] and not v["correctif"],
                f"regle 5 : {t} bloque le profil et retire l'axe sans reecrire "
                f"la base (bloquant={v['bloquant']}, correctif={v['correctif']})")
        verifie("etats_financiers.csv" in (v["detail"] or ""),
                f"regle 5 : le detail de {t} nomme le fichier ou porter la correction")
    verifie(arb.arbitrer(cur, "CONCORDE", {})["regle"] == 0,
            "agregateur absent : l'arbitrage se retire sans bloquer le moteur")
    verifie(arb.arbitrer(cur, "INCONNU", agr)["regle"] == 0,
            "titre absent de l'agregateur : aucun verdict, aucune erreur")
    conn.close()

    # --- (b) ECOC et BOAS, non-regression sur les chiffres reels -------------
    # Les deux identites qui ont etabli la permutation le 26/09/2026. Si ces
    # egalites cessent d'etre vraies, c'est que les colonnes ont bouge.
    for ticker, rn_2025, rn_2024, ca, croi, marge in (
            ("ECOC", 63482.0, 57477.0, 132725.0, 10.45, 47.83),
            ("BOAS", 21906.0, 19984.0, 51926.0, 9.61, 42.19)):
        glissement = 100.0 * (rn_2025 - rn_2024) / rn_2024
        verifie(abs(glissement - croi) <= 0.15,
                f"{ticker} : le glissement du bon sens ({glissement:+.2f} %) egale "
                f"celui publie ({croi:+.2f} %)")
        verifie(abs(100.0 * rn_2025 / ca - marge) <= 0.06,
                f"{ticker} : le resultat net 2025 rapporte au chiffre d'affaires donne "
                f"{100.0 * rn_2025 / ca:.2f} %, soit la marge publiee ({marge:.2f} %)")

    if not DB.exists():
        verifie(False, "brvm.db absente : impossible de verifier l'etat du jour",
                bloquant=False)
        return

    # --- (c) Etat de la base du jour ----------------------------------------
    agregateur = arb.charger_agregateur()
    if not agregateur:
        verifie(False, "docs/data_brvm.json absent : aucune confrontation possible "
                       "(verifier les workflows boc_quotidien et sikafinance)",
                bloquant=False)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]
    verdicts = {t: arb.arbitrer(cur, t, agregateur) for t in tickers}
    conn.close()

    confrontes = [t for t, v in verdicts.items() if v["regle"]]
    verifie(len(confrontes) >= 30,
            f"{len(confrontes)} titres confrontes a l'agregateur (sous 30, "
            f"la confrontation ne couvre plus le marche)")

    corrobores = [t for t, v in verdicts.items() if v["regle"] == 1]
    verifie(len(corrobores) >= 0.6 * max(len(confrontes), 1),
            f"{len(corrobores)}/{len(confrontes)} titres corrobores "
            f"({100 * len(corrobores) // max(len(confrontes), 1)} %) — une chute nette "
            f"signale une derive de saisie ou un changement de format de l'agregateur")

    permutations = sorted(t for t, v in verdicts.items()
                          if v["drapeau"] in ("PERMUTATION_PROBABLE",
                                              "PERMUTATION_SUSPECTEE"))
    verifie(not permutations,
            "aucune permutation de colonnes ouverte — a corriger dans "
            f"donnees/base/etats_financiers.csv : {permutations}" if permutations
            else "aucune permutation de colonnes ouverte dans la base")

    retards = sorted(t for t, v in verdicts.items()
                     if v["drapeau"] == "FONDAMENTAL_EN_RETARD")
    verifie(not retards,
            "aucun exercice publie manquant en base — a saisir dans "
            f"donnees/base/etats_financiers.csv : {retards}" if retards
            else "aucun exercice publie manquant en base",
            bloquant=False)

    # --- Coherence avec profils.json --------------------------------------
    # ATTENTION (27/09/2026, premier passage reel en integration continue) :
    # ces deux controles comparent des verdicts calcules a chaud au contenu de
    # profils.json. Ils n'ont de sens que si ce fichier a ete regenere APRES la
    # base. Sinon ils comparent le present au passe et echouent sur tous les
    # titres a la fois -- ce qui est exactement ce qui s'est produit, parce que
    # tests.yml ne lancait pas profils.py. Le workflow le lance desormais ; ce
    # garde-fou traite le cas ou quelqu'un execute ce fichier sans l'avoir fait.
    profils_json = RACINE / "collecte" / "profils.json"
    if not profils_json.exists():
        verifie(False, "collecte/profils.json absent : coherence non verifiable "
                       "(lancer python3 moteur/profils.py)", bloquant=False)
    elif profils_json.stat().st_mtime < DB.stat().st_mtime:
        verifie(False, "collecte/profils.json est plus ancien que la base : "
                       "coherence non verifiable, relancer python3 moteur/profils.py "
                       "avant ce test", bloquant=False)
    else:
        import json
        profils = json.loads(profils_json.read_text(encoding="utf-8"))
        # Un titre suspendu par arbitrage ne doit porter aucun profil de style :
        # c'est tout l'objet du blocage.
        STYLES = {"GARP", "VALUE", "GROWTH", "RENDEMENT"}
        fautifs = sorted(
            t for t, v in verdicts.items()
            if v["bloquant"] and (profils.get(t) or {}).get("profil") in STYLES)
        verifie(not fautifs,
                f"aucun titre suspendu par arbitrage ne porte un profil de style "
                f"(fautifs : {fautifs})")
        # Le drapeau doit etre visible, pas seulement calcule.
        muets = sorted(
            t for t, v in verdicts.items()
            if v["drapeau"] and v["drapeau"] not in (
                (profils.get(t) or {}).get("drapeaux") or []))
        verifie(not muets,
                f"tous les verdicts d'arbitrage remontent dans profils.json "
                f"(absents : {muets})")



# ----------------------------------------------------------------------
# 13. BASE DE REFERENCE EN CSV (bloquant)
# ----------------------------------------------------------------------
def test_base_reference():
    """Les donnees de reference du projet vivent dans donnees/base/.

    POURQUOI CETTE SECTION EXISTE (27/09/2026). Jusqu'a cette date, les 449
    lignes de reference etaient des tuples Python codes en dur dans
    moteur/peupler.py (83 Ko, 975 lignes). Quatre scripts en tiraient leurs
    correspondances par EXPRESSION REGULIERE sur le texte du fichier --
    dont collecte/avis_brvm.py, qui tourne tous les jours dans P13 et qui
    rendait un dictionnaire VIDE, sans rien signaler, si la structure
    changeait. La veille aurait alors tourne quotidiennement en ne
    reconnaissant aucun titre.

    Ces tests verifient que la base de reference est lisible, complete et
    coherente, et qu'aucune donnee n'est revenue se loger dans le code.
    """
    print("\n=== 13. Base de reference en CSV (bloquant) ===")
    base = RACINE / "donnees" / "base"
    if not base.exists():
        verifie(False, f"dossier {base} absent : la base de reference a disparu")
        return

    # Effectifs attendus au moment de la migration. Ces nombres NE SONT PAS
    # figes : ils doivent croitre (exercices ajoutes, societes nouvelles).
    # Le test attrape une CHUTE, qui signalerait une troncature ou un
    # ecrasement de fichier -- pas une augmentation, qui est le but.
    PLANCHERS = {
        "societes.csv": 50,
        "etats_financiers.csv": 184,
        "resultat_activites_ordinaires.csv": 11,
        "resultat_exploitation.csv": 3,
        "resultats_intermediaires.csv": 3,
        "source_urls.csv": 167,
        "dividendes.csv": 15,
        "avis_reglementaires.csv": 16,
    }
    import csv as _csv
    contenus = {}
    for fichier, plancher in sorted(PLANCHERS.items()):
        chemin = base / fichier
        if not chemin.exists():
            verifie(False, f"{fichier} absent de donnees/base/")
            continue
        with chemin.open(encoding="utf-8", newline="") as f:
            lignes = list(_csv.DictReader(f))
        contenus[fichier] = lignes
        verifie(len(lignes) >= plancher,
                f"{fichier} : {len(lignes)} lignes (plancher {plancher} — "
                f"une chute signale une troncature)")

    # L'en-tete doit correspondre a ce que peupler.py attend. Une colonne
    # renommee, ajoutee ou deplacee decalerait silencieusement toutes les
    # valeurs d'une colonne : c'est le mode de defaillance le plus couteux
    # du projet (cf. permutation ECOC/BOAS, section 12).
    sys.path.insert(0, str(ICI))
    try:
        import peupler
    except Exception as e:  # noqa: BLE001
        verifie(False, f"moteur/peupler.py non importable : {e}")
        return
    for fichier, attendu in sorted(peupler.SCHEMA_CSV.items()):
        lignes = contenus.get(fichier)
        if lignes is None:
            continue
        entete = [c for c in (lignes[0].keys() if lignes else []) if c != "note"]
        verifie(entete == attendu,
                f"{fichier} : en-tete conforme au schema attendu"
                + ("" if entete == attendu else f" — trouve {entete}"))

    # Une cle dupliquee ferait qu'INSERT OR REPLACE garde silencieusement la
    # DERNIERE ligne lue, en perdant la premiere sans rien dire.
    etats = contenus.get("etats_financiers.csv") or []
    cles = [(r["ticker"], r["exercice"]) for r in etats]
    doublons = sorted({c for c in cles if cles.count(c) > 1})
    verifie(not doublons,
            f"aucun couple (ticker, exercice) en double dans etats_financiers.csv"
            + ("" if not doublons else f" — doublons : {doublons}"))

    societes = contenus.get("societes.csv") or []
    tickers = [r["ticker"] for r in societes]
    doublons_t = sorted({t for t in tickers if tickers.count(t) > 1})
    verifie(not doublons_t,
            "aucun ticker en double dans societes.csv"
            + ("" if not doublons_t else f" — doublons : {doublons_t}"))

    # Integrite referentielle : un etat financier sans societe correspondante
    # viole la contrainte du schema et ferait echouer le peuplement.
    connus = set(tickers)
    orphelins = sorted({r["ticker"] for r in etats if r["ticker"] not in connus})
    verifie(not orphelins,
            "tout etat financier se rattache a une societe declaree"
            + ("" if not orphelins else f" — orphelins : {orphelins}"))

    # Les notes de provenance sont l'essentiel de la valeur de la saisie
    # manuelle : document source, correction datee, reserve de lecture. Une
    # chute brutale signalerait une reecriture du fichier qui les aurait
    # perdues (c'est ce qu'une extraction naive aurait fait le 27/09).
    avec_note = sum(1 for r in etats if (r.get("note") or "").strip())
    verifie(avec_note >= 120,
            f"{avec_note} lignes d'etats financiers portent une note de provenance "
            f"(plancher 120 — une chute signale une perte de tracabilite)")

    # Aucune donnee ne doit etre revenue dans le code. Le motif cherche est
    # celui d'un tuple de saisie : ("XXXX", 2025, ...
    code_peupler = (ICI / "peupler.py").read_text(encoding="utf-8")
    import re as _re
    tuples = _re.findall(r'\("[A-Z][A-Z0-9_]{2,6}",\s*(?:19|20)\d{2},', code_peupler)
    verifie(not tuples,
            f"moteur/peupler.py ne contient plus de donnees codees en dur"
            + ("" if not tuples else f" — {len(tuples)} tuple(s) retrouve(s)"))

    # Les quatre scripts qui lisaient le TEXTE de peupler.py doivent lire le CSV.
    for chemin_rel, fonction in (
            ("collecte/avis_brvm.py", "charger_tickers"),
            ("moteur/calendrier.py", "construire_mapping"),
            ("collecte/extraire_lot.py", "charger_referentiels"),
            ("collecte/preparer_integration.py", "charger_exercices_existants")):
        chemin = RACINE / chemin_rel
        if not chemin.exists():
            verifie(False, f"{chemin_rel} absent", bloquant=False)
            continue
        code = chemin.read_text(encoding="utf-8")
        bloc = code.split("def %s(" % fonction, 1)
        if len(bloc) < 2:
            verifie(False, f"{chemin_rel} : fonction {fonction}() introuvable")
            continue
        corps = bloc[1].split("\ndef ", 1)[0]
        verifie("peupler.py" not in corps.replace("peupler.py, d'ou", "")
                or "societes.csv" in corps or "etats_financiers.csv" in corps,
                f"{chemin_rel} : {fonction}() lit un CSV de reference, "
                f"plus le texte de peupler.py")

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

    # ------------------------------------------------------------------
    # Identite du bilan : total actif = total passif.
    #
    # POURQUOI (28/09/2026). Les regles du projet exigent « une identite
    # comptable qui se ferme » comme preuve avant de corriger une donnee
    # certifiee -- mais AUCUN test ne verifiait que les identites se
    # fermaient sur les donnees deja en base. En confrontant les 116 bilans
    # renseignes, un seul ne se ferme pas : SIBC 2025, total actif
    # 1881733 contre total passif 1685249, soit 196484 M d'ecart (10,44 %).
    # Un bilan qui ne se ferme pas n'est pas un retraitement : c'est une
    # impossibilite arithmetique, donc un defaut d'extraction. La ligne est
    # pourtant marquee VALIDE et avait traverse quinze sections de tests.
    #
    # Le registre ci-dessous est ADOSSE AUX VALEURS observees : si l'une des
    # deux bouge, l'exception ne s'applique plus et le test bloque. Une
    # exception ne se transmet donc pas a une valeur qu'elle n'a pas
    # examinee.
    TOLERANCE_BILAN = 0.001          # 0,1 % — couvre l'arrondi d'extraction
    BILANS_NON_FERMES_CONNUS = {
        # (ticker, exercice): (total_actif, total_passif, motif)
        ("SIBC", "2025"): (
            1881733.0, 1685249.0,
            "ecart 196484 M (10,44 %) pour des capitaux propres de 204765 M : "
            "le total passif extrait est vraisemblablement le passif exigible "
            "seul, hors capitaux propres (1685249 + 204765 = 1890014, a 8281 M "
            "du total actif). Non tranche : le document source "
            "(20260421, rapport annuel SIB) est hors de portee du bac a sable. "
            "Inscrit en C11, aucune valeur n'est corrigee a l'aveugle."),
    }
    bilans_confrontes, bilans_ouverts = 0, []
    for r in etats:
        if r["ticker"].startswith("TEST"):
            continue
        try:
            ta = float(r["total_actif"])
            tp = float(r["total_passif"])
        except (TypeError, ValueError):
            continue
        echelle = max(abs(ta), abs(tp))
        if echelle == 0:
            continue
        bilans_confrontes += 1
        if abs(ta - tp) / echelle <= TOLERANCE_BILAN:
            continue
        connu = BILANS_NON_FERMES_CONNUS.get((r["ticker"], r["exercice"]))
        if connu and abs(connu[0] - ta) < 0.001 and abs(connu[1] - tp) < 0.001:
            continue
        bilans_ouverts.append(
            "%s %s : total actif %s contre total passif %s (ecart %.2f %%)"
            % (r["ticker"], r["exercice"], ta, tp, 100.0 * abs(ta - tp) / echelle))
    verifie(not bilans_ouverts,
            "identite du bilan : les %d bilans renseignes se ferment, hors les "
            "%d ecarts inscrits au registre"
            % (bilans_confrontes, len(BILANS_NON_FERMES_CONNUS))
            + ("" if not bilans_ouverts else " — " + " ; ".join(bilans_ouverts)))

    # ------------------------------------------------------------------
    # Le comparatif N-1 republie par le document de l'exercice N doit
    # concorder avec la ligne N-1 de la base.
    #
    # POURQUOI (28/09/2026). C'est le mecanisme qui a demasque ECOC 2022 et
    # BICC 2024 le 27/09/2026 : « deux se refutaient d'elles-memes par la
    # colonne N-1 de l'exercice suivant ». Il avait ete applique A LA MAIN,
    # sur deux titres, et rien ne le rejouait. Confronte aux 96 paires
    # confrontables de la base, il revele quatre desaccords que rien ne
    # signalait, dont deux entre lignes toutes deux marquees VALIDE.
    #
    # Ce controle attrape a lui seul quatre defauts de nature differente :
    # un fragment d'extraction, un rapport intermediaire pris pour un
    # exercice clos, un retraitement du comparatif, et une RUPTURE DE
    # REFERENTIEL COMPTABLE (CIEC et TTLS ci-dessous) -- que la base ne sait
    # aujourd'hui pas exprimer, faute de colonne de referentiel. D'ou C10.
    #
    # Registre adosse aux deux valeurs, comme ci-dessus.
    TOLERANCE_COMPARATIF = 0.005     # 0,5 % — couvre l'arrondi au million
    COMPARATIFS_DIVERGENTS_CONNUS = {
        # (ticker, exercice): (resultat_net_n1 du doc N, resultat_net ligne N-1, motif)
        ("CIEC", "2023"): (
            10271.0, 9819.0,
            "RUPTURE DE REFERENTIEL : la ligne 2022 vient d'un document IFRS "
            "(20230427_..._ifrs_exercice_2022) tandis que le document 2023 est "
            "en SYSCOHADA. Ecart 4,60 %. Les deux valeurs sont justes dans "
            "leur referentiel ; c'est la serie qui est heterogene."),
        ("CIEC", "2025"): (
            10100.0, 10555.0,
            "RUPTURE DE REFERENTIEL : le document 2025 publie SYSCOHADA ET "
            "IFRS (20260520_..._syscohada_et_ifrs) ; son comparatif 2024 "
            "(10100) n'est pas celui de notre ligne 2024, en SYSCOHADA seul "
            "(10555). Ecart 4,31 %."),
        ("STBC", "2025"): (
            44173.762491, 44730.358142,
            "RETRAITEMENT DU COMPARATIF : le document 2025 s'intitule "
            "« annule et remplace le precedent » et republie 2024 a "
            "44173,762 contre 44730,358 dans le document 2024 d'origine. "
            "Ecart 556,596 M (1,24 %)."),
        ("TTLS", "2025"): (
            7140.0, 7090.811,
            "RUPTURE DE REFERENTIEL : le document 2025 est en IFRS "
            "(20260430_..._ifrs) et la ligne 2024 en SYSCOHADA. Ecart "
            "0,69 %. C'est le comparatif IFRS (7140) que le moteur utilise "
            "pour le glissement du dernier exercice, ce qui est homogene ; "
            "c'est la moyenne sur quatre exercices qui enjambe la rupture."),
    }
    par_ticker = {}
    for r in etats:
        if r["ticker"].startswith("TEST"):
            continue
        try:
            exercice = int(r["exercice"])
        except (TypeError, ValueError):
            continue
        par_ticker.setdefault(r["ticker"], {})[exercice] = r
    paires, divergences = 0, []
    for ticker, lignes in sorted(par_ticker.items()):
        for exercice, ligne in sorted(lignes.items()):
            precedente = lignes.get(exercice - 1)
            if precedente is None:
                continue
            try:
                comparatif = float(ligne["resultat_net_n1"])
                reference = float(precedente["resultat_net"])
            except (TypeError, ValueError):
                continue
            if reference == 0:
                continue
            paires += 1
            ecart = abs(comparatif - reference) / abs(reference)
            if ecart <= TOLERANCE_COMPARATIF:
                continue
            connu = COMPARATIFS_DIVERGENTS_CONNUS.get((ticker, str(exercice)))
            if (connu and abs(connu[0] - comparatif) < 0.001
                    and abs(connu[1] - reference) < 0.001):
                continue
            divergences.append(
                "%s %s : le document republie %s pour %s, la base porte %s "
                "(ecart %.2f %%)"
                % (ticker, exercice, comparatif, exercice - 1, reference,
                   100.0 * ecart))
    verifie(not divergences,
            "comparatif N-1 : les %d paires confrontables concordent, hors les "
            "%d divergences inscrites au registre"
            % (paires, len(COMPARATIFS_DIVERGENTS_CONNUS))
            + ("" if not divergences else " — " + " ; ".join(divergences)))



# ----------------------------------------------------------------------
# 16. IDEMPOTENCE DE peupler.py (bloquant)
# ----------------------------------------------------------------------
def test_idempotence_peupler():
    """Relancer peupler.py ne doit JAMAIS changer le nombre de lignes.

    POURQUOI CETTE SECTION EXISTE (28/09/2026). Rien ne surveillait cette
    famille de defauts, et elle mordait deja.

    peupler.py inserait dividendes et avis_reglementaires par un INSERT simple.
    Ces deux tables sont les SEULES de la base de reference sans clef unique --
    leur seule clef est un id AUTOINCREMENT -- donc chaque passage y rejouait
    la totalite du CSV. Les quatre autres tables (societes, etats_financiers,
    resultats_intermediaires par INSERT OR REPLACE sur une clef unique,
    liste_suivi par DELETE puis insertion) etaient, elles, idempotentes.
    L'idempotence du chargeur reposait donc entierement sur la presence d'une
    clef unique, et deux tables n'en avaient pas.

    Ce n'etait pas theorique : app.py::preparer_base() relance peupler.py sur
    une base EXISTANTE des que l'empreinte des sources change, en annoncant une
    "reconstruction" qui n'en est pas une -- et tester_donnees.py demarre app.py
    en section 4. La barriere corrompait donc la base qu'elle validait. Mesure
    du 28/09/2026 : +15 dividendes et +16 avis par passage, croissance lineaire
    non bornee (311/16 -> 326/32 -> 341/48 -> 356/64 -> 371/80).

    Consequence mesuree, et c'est la qu'est l'enjeu : appliquer_gate() COMPTE
    les avis reglementaires --
        retards = avis(cur, ticker, "RETARD_PUBLICATION")
        if len(retards) >= fx["retards_publication"]["defauts_max"]   # seuil 2
    SDSC porte UN retard de publication (2025-04-30, confirme par ses propres
    commissaires aux comptes). Duplique, il en porte deux : le seuil tombe et le
    titre passe de ELIGIBLE a EXCLU, sortant de toute l'analyse sur la base d'un
    manquement enregistre une fois et compte deux fois. Le collecte/profils.json
    commite portait ce verdict corrompu.

    Le test compte les lignes de chaque table apres un premier peuplement, puis
    apres un second, sur une base jetable -- jamais sur brvm.db.
    """
    print("\n=== 16. Idempotence de peupler.py (bloquant) ===")
    sys.path.insert(0, str(ICI))
    try:
        import peupler
    except Exception as e:  # pragma: no cover
        verifie(False, f"moteur/peupler.py non importable : {e}")
        return

    tables = ("societes", "etats_financiers", "dividendes", "avis_reglementaires",
              "liste_suivi", "resultats_intermediaires")

    def comptes(chemin):
        conn = sqlite3.connect(chemin)
        try:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in tables}
        finally:
            conn.close()

    db_origine = peupler.DB
    with tempfile.TemporaryDirectory() as tmp:
        jetable = str(Path(tmp) / "idempotence.db")
        peupler.DB = jetable
        try:
            peupler.main()
            premier = comptes(jetable)
            peupler.main()
            second = comptes(jetable)
        except Exception as e:  # pragma: no cover
            verifie(False, f"peupler.main() a echoue sur une base jetable : {e}")
            return
        finally:
            peupler.DB = db_origine

    derives = [f"{t} : {premier[t]} -> {second[t]}"
               for t in tables if premier[t] != second[t]]
    verifie(not derives,
            "relancer peupler.py ne cree aucune ligne supplementaire"
            + ("" if not derives else " — DERIVE : " + " ; ".join(derives)))

    # Garde-fou de second niveau : le test ci-dessus ne vaut que si le
    # peuplement a bien eu lieu. Une base vide serait trivialement stable.
    verifie(premier["societes"] >= 40 and premier["etats_financiers"] >= 150,
            f"la base jetable est bien peuplee ({premier['societes']} societes, "
            f"{premier['etats_financiers']} lignes d'etats) — sans quoi la "
            f"stabilite ci-dessus ne prouverait rien")

    # Le compte des avis par (ticker, type) doit rester a 1 pour les avis
    # venus du CSV de reference : c'est ce compte que lit le gate.
    conn = sqlite3.connect(DB) if Path(DB).exists() else None
    if conn is not None:
        try:
            trop = conn.execute(
                "SELECT ticker, type, COUNT(*) FROM avis_reglementaires "
                "GROUP BY ticker, type, date_avis HAVING COUNT(*) > 1").fetchall()
        finally:
            conn.close()
        verifie(not trop,
                "aucun avis reglementaire en double dans brvm.db (le gate les "
                "COMPTE : un doublon exclut un titre a tort)"
                + ("" if not trop else " — trouve : " + str(trop)))


# ----------------------------------------------------------------------
# 14. FONDAMENTAUX REPRIS DE LA CHAINE pipeline/ (bloquant)
# ----------------------------------------------------------------------
def test_fondamentaux_agregateur():
    """docs/data_brvm.json est branche comme source de fondamentaux.

    POURQUOI CETTE SECTION EXISTE (27/09/2026). L'audit du 26/09 avait etabli
    que le projet maintenait DEUX chaines de collecte, et que le tableau de
    bord lisait la moins riche. La chaine pipeline/ tient, pour 47 titres sur
    47, le chiffre d'affaires, la marge nette et la croissance du chiffre
    d'affaires -- trois grandeurs absentes du moteur -- et, pour 25 titres,
    des capitaux propres avec leur millesime et l'URL du rapport de notation
    dont ils sont tires. Onze ROE manquants en sont devenus calculables.

    Ces tests verifient que le branchement tient : les grandeurs remontent,
    le ROE d'origine exterieure est signale et n'ecrase jamais une valeur
    certifiee, et l'alias de ticker de Bridge Bank est en place.
    """
    print("\n=== 14. Fondamentaux repris de la chaine pipeline/ (bloquant) ===")
    sys.path.insert(0, str(ICI))
    try:
        import arbitrage as arb
    except ImportError as e:
        verifie(False, f"moteur/arbitrage.py non importable : {e}")
        return
    agr = arb.charger_agregateur()
    if not agr:
        verifie(False, "docs/data_brvm.json absent : les fondamentaux exterieurs ne "
                       "sont plus alimentes (verifier boc_quotidien et sikafinance)",
                bloquant=False)
        return

    # L'alias existe parce que les deux chaines ne nomment pas Bridge Bank de
    # la meme facon. Sans lui, le titre serait invisible a l'arbitrage alors
    # que les deux chaines le connaissent.
    verifie("BBGCI" in agr and "BBGC" not in agr,
            "l'alias de ticker BBGC -> BBGCI est applique a la lecture")

    for champ, plancher in (("ca", 40), ("marge_nette", 40), ("croissance_ca", 40),
                            ("capitaux_propres", 20)):
        n = sum(1 for v in agr.values() if v.get(champ) is not None)
        verifie(n >= plancher,
                f"agregateur : {champ} renseigne pour {n} titres (plancher {plancher})")

    profils_json = RACINE / "collecte" / "profils.json"
    if not profils_json.exists():
        verifie(False, "collecte/profils.json absent", bloquant=False)
        return
    if not DB.exists():
        verifie(False, "brvm.db absente : coherence non verifiable (lancer "
                       "moteur/peupler.py puis charger_cours*.py)", bloquant=False)
        return
    if profils_json.stat().st_mtime < DB.stat().st_mtime:
        verifie(False, "collecte/profils.json plus ancien que la base : relancer "
                       "python3 moteur/profils.py avant ce test", bloquant=False)
        return
    import json as _json
    profils = _json.loads(profils_json.read_text(encoding="utf-8"))

    for champ in ("chiffre_affaires", "marge_nette", "croissance_ca"):
        n = sum(1 for v in profils.values() if v.get(champ) is not None)
        verifie(n >= 0.8 * len(profils),
                f"profils.json : {champ} expose pour {n}/{len(profils)} titres "
                f"(sous 80 %, le branchement ne remonte plus)")

    # Un ROE d'origine exterieure doit TOUJOURS etre signale : sans cela, rien
    # ne distingue a l'affichage une valeur certifiee d'une valeur reprise.
    exterieurs = [t for t, v in profils.items() if v.get("roe_source") == "AGREGATEUR"]
    muets = sorted(t for t in exterieurs
                   if "ROE_SOURCE_EXTERIEURE" not in (profils[t].get("drapeaux") or []))
    verifie(not muets,
            f"les {len(exterieurs)} ROE d'origine exterieure portent tous leur drapeau"
            + ("" if not muets else f" — muets : {muets}"))
    sans_source = sorted(t for t in exterieurs if not profils[t].get("source_capitaux_propres"))
    verifie(not sans_source,
            "chaque ROE d'origine exterieure cite le rapport dont il vient"
            + ("" if not sans_source else f" — sans source : {sans_source}"))

    # Le repli ne doit JAMAIS ecraser des capitaux propres certifies ENCORE
    # LISIBLES. Il n'intervient que si la base n'a rien, ou si ce qu'elle a
    # depasse les trois ans — auquel cas le ROE n'etait de toute facon plus
    # calculable et n'etait pas affiche.
    #
    # Ce controle a d'abord ete ecrit a l'envers : il cherchait le drapeau
    # DONNEES_PERIMEES, que le repli efface justement quand il reussit. Il
    # accusait donc BOAB, CBIBF et SGBC d'ecrasement alors que leurs fonds
    # propres en base datent de 2021, 2022 et 2021. On interroge desormais
    # l'exercice, pas le drapeau.
    AGE_MAX = 3
    conn = sqlite3.connect(DB)
    dernier_cp = dict(conn.execute(
        "SELECT ticker, MAX(exercice) FROM etats_financiers "
        "WHERE capitaux_propres IS NOT NULL GROUP BY ticker"))
    conn.close()
    annee = date.today().year
    ecrases = sorted(t for t in exterieurs
                     if t in dernier_cp and (annee - dernier_cp[t]) <= AGE_MAX)
    verifie(not ecrases,
            f"le repli n'ecrase aucun capital propre certifie de moins de {AGE_MAX} ans"
            + ("" if not ecrases else
               f" — ecrases : {[(t, dernier_cp[t]) for t in ecrases]}"))
    remplaces = sorted((t, dernier_cp[t]) for t in exterieurs if t in dernier_cp)
    if remplaces:
        print("       (repli legitime sur des fonds propres perimes : %s)"
              % ", ".join("%s %d" % x for x in remplaces))



# ----------------------------------------------------------------------
# 17. COUVERTURE DE LA CHAINE DE CHARGEMENT (bloquant)
# ----------------------------------------------------------------------
# Registre des tables lues par la chaine de publication, hors app.py. Sert a
# expliquer, dans le message du controle A, pourquoi un chargeur peut legitimement
# manquer a app.py : sa table n'est lue que par la publication.
LECTEURS_HORS_APP = {
    "dividendes": "dashboard/generer_dashboard_html.py (historique des dividendes de la Fiche titre)",
    "liquidite_quotidienne": "personne — table ecrite sans lecteur (constat du 28/09/2026)",
}


def _tables_ecrites(source):
    """Tables cibles des INSERT d'un fichier Python, lues dans son source.

    Deliberement derive du source plutot que fige dans un registre : un registre
    en dur se desynchronise du code qu'il decrit, et c'est precisement le genre de
    derive que cette section surveille.
    """
    import re
    return set(m.group(1) for m in re.finditer(
        r"INSERT\s+(?:OR\s+(?:REPLACE|IGNORE)\s+)?INTO\s+([a-z_]+)", source, re.I))


def test_chaine_chargement():
    """La chaine que app.py construit doit remplir toute table que app.py lit.

    POURQUOI CETTE SECTION EXISTE (28/09/2026). Rien ne surveillait cette famille,
    et la chaine de chargement est deja ecrite DEUX FOIS, dans deux versions
    differentes :

      - .github/workflows/pages.yml enchaine les quatre chargeurs de collecte/
        apres peupler.py, puis calendrier, signaux, profils, et publie la fiche ;
      - app.py::preparer_base() n'en lance que DEUX (charger_cours.py et
        charger_cours_quotidien.py) puis profils.py. Il omet
        charger_dividendes_exercice.py et charger_liquidite_quotidienne.py.

    Mesure du 28/09/2026, base construite des deux facons depuis les memes CSV :

        table                   chaine pages.yml    chaine app.py
        dividendes                       311                 15
        liquidite_quotidienne          73141                  0

    Et sur les 47 fiches : 308 lignes de dividendes, 47/47 fiches non vides par la
    chaine complete, contre 12 lignes et 9/47 par celle de app.py.

    CE N'EST PAS UN DEFAUT ACTIF AUJOURD'HUI, et il faut le dire ainsi : app.py ne
    lit que societes, etats_financiers, cours_mensuels et cours_quotidien_boc, que
    sa propre chaine remplit entierement. profils.json est d'ailleurs identique au
    champ pres entre les deux bases — verifie sur les 47 titres, 0 ecart. Le defaut
    est LATENT, exactement comme la deduplication de C10 : arme, en attente de se
    declencher.

    Ce qui l'armera. app.py calcule sa clef de cache (empreinte()) sur une liste de
    CSV qui inclut DEJA collecte/dividendes_par_exercice.csv — la source des 296
    dividendes manquants. Modifier ce CSV invalide donc le cache et declenche une
    "reconstruction" qui, par construction, ne le relit pas. Le jour ou un onglet
    de app.py affichera un historique de dividendes, il le tirera d'une table
    remplie a 4,8 %, sans qu'aucune erreur ne s'affiche : preparer_base() lance ses
    scripts en check=False, capture_output=True, donc tout echec de chargeur est
    avale sans trace.

    Les deux controles ci-dessous. Le premier bloque le jour ou app.py lit une
    table que sa chaine ne remplit pas. Le second bloque le jour ou un chargeur
    nouveau est ajoute a collecte/ sans etre branche dans pages.yml — c'est la
    meme divergence, prise a l'autre bout.
    """
    print("\n=== 17. Couverture de la chaine de chargement (bloquant) ===")
    import re

    app = APP.read_text(encoding="utf-8")
    pages = RACINE / ".github" / "workflows" / "pages.yml"
    chargeurs = sorted((RACINE / "collecte").glob("charger_*.py"))
    verifie(bool(chargeurs), "collecte/ contient au moins un chargeur charger_*.py")
    if not chargeurs:
        return

    # Liste de scripts de preparer_base(), lue dans le source de app.py.
    bloc = re.search(r"def preparer_base\(.*?\n    return ", app, re.S)
    verifie(bloc is not None,
            "app.py::preparer_base() est reperable dans le source "
            "(sans quoi ce controle ne prouve rien)")
    if bloc is None:
        return
    chaine_app = set(re.findall(r'"([a-z_0-9]+\.py)"', bloc.group(0)))

    # Tables lues par app.py, hors faux positif de "from pathlib import".
    lues_app = set(m.group(1).lower() for m in re.finditer(
        r"FROM\s+([a-z_]+)", app)) - {"pathlib"}

    # --- Controle A : preparer_base() enchaine TOUS les chargeurs --------------
    # Invariant volontairement plus large que le defaut d'origine. Un controle
    # limite aux tables que app.py lit AUJOURD'HUI serait vrai et inutile : c'est
    # exactement parce que app.py ne lisait pas dividendes que l'omission a tenu
    # sans se voir. L'invariant qui protege est l'egalite des deux chaines.
    absents = sorted(ch.name for ch in chargeurs if ch.name not in chaine_app)
    consequences = []
    for nom in absents:
        tables = sorted(_tables_ecrites((RACINE / "collecte" / nom).read_text(encoding="utf-8")))
        lues = [t for t in tables if t in lues_app]
        consequences.append(
            f"{nom} n'alimente pas {', '.join(tables)}"
            + (f" — DEJA LUE(S) PAR app.py : {', '.join(lues)}" if lues
               else " — pas encore lue par app.py, donc defaut latent"))
    verifie(not absents,
            f"app.py::preparer_base() enchaine les {len(chargeurs)} chargeurs de "
            f"collecte/ — sa base est donc celle que pages.yml publie"
            + ("" if not absents else " — MANQUE(S) : " + " ; ".join(consequences)))

    # --- Controle B : pages.yml branche tous les chargeurs existants ----------
    verifie(pages.exists(), "pages.yml existe (c'est la chaine de reference)")
    if pages.exists():
        texte_pages = pages.read_text(encoding="utf-8")
        oublies = [ch.name for ch in chargeurs if ch.name not in texte_pages]
        verifie(not oublies,
                f"pages.yml enchaine les {len(chargeurs)} chargeurs de collecte/ "
                f"— la fiche publiee est donc construite sur la base complete"
                + ("" if not oublies else " — OUBLIE(S) : " + ", ".join(oublies)))

    # --- Garde-fou : le registre d'explication doit rester adosse au code ----
    # Une table declaree "sans lecteur" qui se met a etre lue quelque part doit
    # faire tomber son explication, sinon le message du controle A devient faux.
    sans_lecteur = [t for t, motif in LECTEURS_HORS_APP.items()
                    if motif.startswith("personne")]
    for table in sans_lecteur:
        lecteurs = [p.name for p in list(RACINE.rglob("*.py"))
                    if p.name not in {c.name for c in chargeurs}
                    and re.search(rf"FROM\s+{table}\b", p.read_text(encoding="utf-8", errors="ignore"), re.I)]
        verifie(not lecteurs,
                f"{table} est toujours sans lecteur, comme le dit le registre"
                + ("" if not lecteurs else
                   f" — DESORMAIS LUE PAR : {', '.join(sorted(lecteurs))} ; "
                   f"mettre a jour LECTEURS_HORS_APP et rebrancher son chargeur"))


# ----------------------------------------------------------------------
# 18. UN CHARGEUR EN ECHEC NE SE TAIT PLUS (bloquant)
# ----------------------------------------------------------------------
def test_panne_de_chargeur():
    """Un chargeur qui echoue doit rompre le silence, pas basculer sur le repli.

    POURQUOI CETTE SECTION EXISTE (chantier C13, 30/09/2026). preparer_base()
    lancait ses scripts en check=False, capture_output=True puis rendait
    DB.exists(). Mesure par injection d'une panne dans
    charger_cours_quotidien.py : code de retour 1 jete, preparer_base() rend True,
    cours_quotidien_boc a 0 ligne, l'application sert alors le repli
    cours_mensuels (2026-07 au lieu de 2026-09-25) et profils.py reecrit
    collecte/profils.json (854 insertions / 857 suppressions) sur la base
    degradee. C'est la regression n°2 de l'en-tete de ce fichier, rejouee.

    Quatre controles. Les trois premiers portent sur executer_chaine() : un echec
    est rendu, il arrete la chaine (donc profils.py ne tourne pas en aval), un
    script absent en est un aussi. Le quatrieme est l'INJECTION sur l'application
    elle-meme : une copie de app.py dans un arbre jetable ou la base existe mais ou
    un chargeur sort en code 1 doit afficher l'echec et ne rien rendre d'autre.
    """
    print("\n=== 18. Un chargeur en echec ne se tait plus (bloquant) ===")
    import shutil
    sys.path.insert(0, str(ICI))
    from chaine import executer_chaine

    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "ok.py").write_text("pass\n", encoding="utf-8")
        (t / "ko.py").write_text(
            "import sys\nsys.stderr.write('PANNE-DE-TEST')\nsys.exit(3)\n", encoding="utf-8")
        (t / "aval.py").write_text(
            "from pathlib import Path\nPath('aval_a_tourne').write_text('x')\n", encoding="utf-8")
        (t / "lent.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")

        verifie(executer_chaine([t / "ok.py", t / "aval.py"]) == [],
                "une chaine saine ne rend aucun echec")
        (t / "aval_a_tourne").unlink(missing_ok=True)

        echecs = executer_chaine([t / "ok.py", t / "ko.py", t / "aval.py"])
        verifie(len(echecs) == 1 and echecs[0]["script"] == "ko.py" and echecs[0]["code"] == 3
                and "PANNE-DE-TEST" in echecs[0]["motif"],
                "un chargeur en code 3 est rendu avec son code et sa sortie d'erreur"
                + ("" if echecs else " — RIEN RENDU : le silence est revenu"))
        verifie(not (t / "aval_a_tourne").exists(),
                "la chaine s'arrete au premier echec : le script en aval "
                "(profils.py, qui reecrit un fichier commite) ne tourne pas")

        absent = executer_chaine([t / "ok.py", t / "n_existe_pas.py"])
        verifie(len(absent) == 1 and absent[0]["script"] == "n_existe_pas.py",
                "un script absent est un echec, pas une omission tolerable")
        lent = executer_chaine([t / "lent.py"], timeout=1)
        verifie(len(lent) == 1 and lent[0]["code"] is None and "delai" in lent[0]["motif"],
                "un script qui depasse son delai est un echec")

    # --- Injection sur l'application elle-meme --------------------------------
    if not DB.exists():
        verifie(False, "brvm.db absente : l'injection sur app.py ne prouverait rien "
                       "(lancer peupler.py et les chargeurs d'abord)", bloquant=False)
        return
    try:
        from streamlit.testing.v1 import AppTest
        import streamlit as st
    except ImportError:
        verifie(True, "streamlit non installe — injection sur app.py ignoree", bloquant=False)
        return
    with tempfile.TemporaryDirectory() as tmp:
        arbre = Path(tmp)
        (arbre / "moteur").mkdir()
        (arbre / "collecte").mkdir()
        shutil.copy2(APP, arbre / "app.py")
        shutil.copy2(ICI / "chaine.py", arbre / "moteur" / "chaine.py")
        shutil.copy2(DB, arbre / "moteur" / "brvm.db")      # la base EXISTE : c'est le piege
        shutil.copy2(RACINE / "collecte" / "profils.json", arbre / "collecte" / "profils.json")
        temoin = arbre / "profils_a_tourne"
        noms_ok = ["moteur/peupler.py", "collecte/charger_cours.py",
                   "collecte/charger_dividendes_exercice.py",
                   "collecte/charger_liquidite_quotidienne.py"]
        for n in noms_ok:
            (arbre / n).write_text("pass\n", encoding="utf-8")
        (arbre / "collecte" / "charger_cours_quotidien.py").write_text(
            "import sys\nsys.stderr.write('PANNE-INJECTEE')\nsys.exit(1)\n", encoding="utf-8")
        (arbre / "moteur" / "profils.py").write_text(
            f"from pathlib import Path\nPath({str(temoin)!r}).write_text('x')\n", encoding="utf-8")
        st.cache_resource.clear()
        try:
            at = AppTest.from_file(str(arbre / "app.py"), default_timeout=300).run()
        except Exception as e:
            verifie(False, f"app.py copiee leve une exception sous panne : {type(e).__name__} — {str(e)[:160]}")
            return
        finally:
            st.cache_resource.clear()
        erreurs = " ".join(e.value for e in at.error)
        verifie(len(at.exception) == 0, "sous panne de chargeur, app.py ne plante pas")
        verifie("charger_cours_quotidien.py" in erreurs and "PANNE-INJECTEE" in erreurs,
                "sous panne de chargeur, l'ecran NOMME le chargeur et affiche sa sortie d'erreur"
                + ("" if erreurs else " — ECRAN MUET : la base existante a ete servie"))
        verifie(len(at.tabs) == 0,
                "sous panne de chargeur, aucun onglet n'est rendu (pas de donnee de repli servie)")
        verifie(not temoin.exists(),
                "sous panne de chargeur, profils.py ne tourne pas (profils.json n'est pas reecrit)")


# ----------------------------------------------------------------------
# 19. CONFRONTATION DES DEUX SERIES DE COURS (bloquant)
# ----------------------------------------------------------------------
# Plafond des seances du mensuel absentes du quotidien. Registre ADOSSE A LA
# VALEUR OBSERVEE : il ne peut que descendre. Il valait 101 sur 101 le
# 30/09/2026 au matin -- la cause etant la « LIMITE CONNUE 25/07/2026, non
# corrigee » de collecte/backfill_boc_quotidien.py : un BOC deja archive par le
# collecteur mensuel n'etait jamais reextrait vers cours_quotidien_boc.csv.
# Le chantier C15 a verse les 4 509 lignes du mensuel dans le quotidien
# (outils/versement_mensuel_vers_quotidien.py) : le plafond tombe a ZERO, et
# toute seance qui en disparaitrait serait desormais une regression.
SEANCES_MENSUEL_ABSENTES_DU_QUOTIDIEN = 0

# Nombre de paires (ticker, jour) que les deux series doivent pouvoir
# confronter. Mesure apres versement : 4 508 -- les 4 509 lignes du mensuel
# moins STAC au 31/12/2018, seule ligne sans cours. Registre adosse a la valeur
# observee lui aussi, mais dans l'autre sens : il ne peut que MONTER. Sans ce
# plancher, vider la confrontation la rendrait verte, ce qu'elle etait
# precisement avant C15 -- verte et vide.
PAIRES_CONFRONTABLES_MINIMUM = 4508


def test_confrontation_cours():
    """La base porte deux sources de prix ; il faut qu'elles puissent se confronter.

    POURQUOI CETTE SECTION EXISTE (30/09/2026). cours_mensuels (depuis
    collecte/cours_extraits.csv) et cours_quotidien_boc (depuis
    collecte/cours_quotidien_boc.csv) sont deux extractions INDEPENDANTES des BOC.
    Les sections 1 a 3 verifient fraicheur, frequence et source retenue, jamais
    l'accord des VALEURS. Etat mesure le 30/09/2026 au matin :

      - le mensuel portait 101 dates de bulletin, le quotidien 1926 ;
      - les deux series ne partageaient AUCUNE date : 0 sur 101 ;
      - la confrontation etait donc VIDE : pas une seule paire (ticker, jour)
        commune. Cette section passait au vert sans rien confronter. Comparer le
        dernier cours du mois quotidien au cours mensuel donnait 1561 egalites au
        franc sur 4463 paires, mais cela compare deux jours DIFFERENTS (1 a 3 jours
        d'ecart) : ce n'est pas un accord, c'est du bruit.

    CE QUE LE CHANTIER C15 A CHANGE (30/09/2026, cycle 8). Les 4 509 lignes du
    mensuel ont ete versees dans le quotidien par
    outils/versement_mensuel_vers_quotidien.py, script idempotent et sans reseau.
    La confrontation est desormais PLEINE et son resultat est le premier verdict
    que le projet possede sur la qualite de ses prix : sur **4 508 paires
    (ticker, jour)** communes, **0 divergence au franc**. Deux extractions
    independantes des memes bulletins, faites a des dates differentes par des
    codes differents, donnent exactement le meme cours partout.

    Trois controles. A : plus aucune seance du mensuel n'est absente du quotidien
    (plafond zero, il ne peut que descendre). B : la confrontation reste PLEINE --
    au moins PAIRES_CONFRONTABLES_MINIMUM paires ; sans ce plancher, la vider
    suffirait a rendre la section verte, ce qu'elle etait avant C15. C : sur toute
    paire commune, le meme ticker porte le meme cours au franc -- deux extractions
    du MEME document ne peuvent pas diverger sans qu'une soit fausse.
    """
    print("\n=== 19. Confrontation des deux series de cours (bloquant) ===")
    import csv
    mens_f = RACINE / "collecte" / "cours_extraits.csv"
    quot_f = RACINE / "collecte" / "cours_quotidien_boc.csv"
    if not (mens_f.exists() and quot_f.exists()):
        verifie(False, "cours_extraits.csv ou cours_quotidien_boc.csv absent : "
                       "rien a confronter", bloquant=False)
        return

    def iso(d):
        d = d.strip()
        return d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    mens = {}
    for r in csv.DictReader(open(mens_f, encoding="utf-8")):
        if r["cours"] and r["date_bulletin"]:
            mens[(r["ticker"], iso(r["date_bulletin"]))] = float(r["cours"])
    quot = {}
    for r in csv.DictReader(open(quot_f, encoding="utf-8")):
        if r["cours"] and r["date_bulletin"]:
            quot[(r["ticker"], iso(r["date_bulletin"]))] = float(r["cours"])
    verifie(len(mens) > 4000 and len(quot) > 80000,
            f"les deux series sont chargees ({len(mens)} cours mensuels, {len(quot)} quotidiens) "
            f"— sans quoi la confrontation ne prouverait rien")

    dates_m = {d for _, d in mens}
    dates_q = {d for _, d in quot}
    absentes = sorted(dates_m - dates_q)
    verifie(len(absentes) <= SEANCES_MENSUEL_ABSENTES_DU_QUOTIDIEN,
            f"{len(absentes)} seance(s) du mensuel sur {len(dates_m)} sont absentes du quotidien "
            f"(plafond {SEANCES_MENSUEL_ABSENTES_DU_QUOTIDIEN}, verse par C15)"
            + ("" if len(absentes) <= SEANCES_MENSUEL_ABSENTES_DU_QUOTIDIEN else
               " — LE PLAFOND EST DEPASSE : une seance a disparu du quotidien, "
               "relancer outils/versement_mensuel_vers_quotidien.py et chercher "
               "ce qui l'a retiree : " + ", ".join(absentes[:5])))

    communs = sorted(set(mens) & set(quot))
    # Plancher : la confrontation doit rester PLEINE. Avant C15 elle etait vide,
    # donc verte sans rien prouver — c'est le faux vert que ce controle interdit.
    verifie(len(communs) >= PAIRES_CONFRONTABLES_MINIMUM,
            f"{len(communs)} paire(s) (ticker, jour) confrontables "
            f"(plancher {PAIRES_CONFRONTABLES_MINIMUM}, il ne peut que monter)"
            + ("" if len(communs) >= PAIRES_CONFRONTABLES_MINIMUM else
               " — LA CONFRONTATION S'EST VIDEE : verte sans rien confronter, "
               "l'etat exact d'avant C15"))

    diverg = [(k, mens[k], quot[k]) for k in communs if mens[k] != quot[k]]
    verifie(not diverg,
            f"{len(communs)} paire(s) confrontees, {len(diverg)} divergente(s) au franc "
            f"— deux extractions independantes des memes bulletins"
            + ("" if not diverg else " — " + " ; ".join(
                f"{k[0]} {k[1]} : mensuel {a:g} contre quotidien {b:g}" for k, a, b in diverg[:5])))


# ----------------------------------------------------------------------
# 22. L'IMPLICITE DU BOC DANS LE TEMPS (bloquant + alertes)
# ----------------------------------------------------------------------
# Plafonds mesures le 30/09/2026 (cycle 8), sur 52 368 seances a cours mouvant
# pour le PER et 51 781 pour le rendement. Registres ADOSSES AUX VALEURS
# OBSERVEES : une hausse est signalee, jamais silencieuse.
FIGEMENTS_PER_MAX = 108
FIGEMENTS_RENDEMENT_MAX = 327

# Points de BPA annuel (derniere seance de l'annee, cours/per) qui reposent sur
# un PER fige. croissance_bpa_implicite() les lit pour calculer un CAGR : celui-ci
# est donc faux du meme pourcentage que le mouvement de cours non repercute.
# Un seul cas sur huit ans et demi, et il est CORROBORE par les deux extractions
# (la seance du 30/12 vient de la collecte quotidienne, celle du 31/12 du
# bulletin mensuel verse par C15) : c'est le BOC qui a publie ce PER fige, pas
# notre transcription. Effet : 0,63 % sur une borne du CAGR de BOAS.
BPA_ANNUEL_SUR_PER_FIGE = {("BOAS", "2024-12-31"): 6.66}

# Collisions d'echelle : une chute de plus de 60 % en une seance, suivie dans les
# quinze seances d'un RETOUR a moins de 5 % du niveau d'avant. Une division de
# nominal ne revient jamais sur ses pas : ces cinq cas sont donc des valeurs d'une
# AUTRE echelle deposees dans la serie, pas des operations sur titre. Registre
# adosse aux valeurs observees, avec le facteur mesure. Voir C18.
# Les deux SLBC sont des facteurs 1000 : le controle de la section 7 les ecarte
# explicitement comme « erreurs de saisie manifestes » (var > -0.995) et ne les
# enregistre nulle part. Les trois autres, lui, les compte a tort comme divisions
# de nominal non enregistrees.
COLLISIONS_ECHELLE = {
    ("SAFC", "2018-12-21"): 24.65,
    ("SAFC", "2019-01-02"): 24.65,
    ("SLBC", "2022-01-12"): 1000.0,
    ("SLBC", "2023-06-02"): 1080.99,
    ("STBC", "2018-07-12"): 3.98,
}


def _collisions_echelle(cur, chute=0.40, fenetre=15, retour=0.05):
    """Chutes de plus de 60 % qui REVIENNENT au niveau d'avant dans la fenetre."""
    lignes = cur.execute(
        "SELECT ticker, date_bulletin, cours FROM cours_quotidien_boc "
        "WHERE ticker NOT LIKE 'TEST_%' AND cours IS NOT NULL "
        "ORDER BY ticker, date_bulletin").fetchall()
    par_ticker = {}
    for ticker, date_b, cours in lignes:
        par_ticker.setdefault(ticker, []).append((date_b, cours))
    trouves = {}
    for ticker, serie in par_ticker.items():
        for i in range(1, len(serie)):
            (_d0, c0), (d1, c1) = serie[i - 1], serie[i]
            if not (c0 and c1) or c1 >= chute * c0:
                continue
            for dj, cj in serie[i + 1:i + 1 + fenetre]:
                if cj and abs(cj / c0 - 1) < retour:
                    trouves[(ticker, d1)] = round(c0 / c1, 2)
                    break
    return trouves


def _figements(cur, champ, demi_pas):
    """Seances ou `champ` est reste IDENTIQUE alors que le cours a bouge.

    L'arrondi de publication est defalque : le BOC publie le PER a deux
    decimales et le rendement a quatre (en fraction), donc une valeur peut
    legitimement ne pas bouger tant que le mouvement de cours reste sous la
    granularite de la case. La marge retenue est deux fois le demi-pas rapporte
    a la valeur, ce qui laisse passer tout ce que l'arrondi explique.
    """
    lignes = cur.execute(
        f"SELECT ticker, date_bulletin, cours, {champ} FROM cours_quotidien_boc "
        "WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker, date_bulletin").fetchall()
    cas, population, precedent = [], 0, None
    for ticker, date_b, cours, valeur in lignes:
        if precedent and precedent[0] == ticker:
            _t, _d, cours_p, valeur_p = precedent
            if (cours and cours_p and cours != cours_p
                    and valeur is not None and valeur_p is not None):
                population += 1
                if valeur == valeur_p:
                    marge = (demi_pas / abs(valeur)) if valeur else 0.0
                    variation = abs(cours / cours_p - 1.0)
                    if variation > 2 * marge:
                        cas.append((ticker, date_b, cours_p, cours, valeur, variation))
        precedent = (ticker, date_b, cours, valeur)
    return cas, population


def test_implicite_boc():
    """Le BPA et le DPA implicites du BOC doivent etre des PALIERS, pas du bruit.

    POURQUOI CETTE SECTION EXISTE (chasse du cycle 8, 30/09/2026). Le bulletin
    publie trois nombres par titre et par seance -- cours, per, rendement -- dont
    deux sont derives : le benefice par action implicite (cours / per) et le
    dividende par action implicite (cours x rendement). Ces deux-la ne peuvent
    bouger qu'a une publication de resultats ou a un detachement de dividende :
    entre deux, ce sont des paliers. Rien ne le verifiait. Les sections 1 a 3
    regardent la fraicheur, la frequence et la source retenue ; la section 19
    confronte les deux series de COURS ; et le moteur ne lit jamais que la
    DERNIERE ligne de chaque titre. Un per ou un rendement reste colle a sa
    valeur de la veille pendant que le cours bouge passait donc inapercu.

    CE QUE LA CHASSE A MESURE, et qu'il faut lire avant de toucher aux plafonds :

      - **108 figements du PER** sur 52 368 seances a cours mouvant (0,2 %), et
        **327 du rendement** sur 51 781 (0,6 %), une fois defalque tout ce que
        l'arrondi de publication explique. Les ecarts de cours non repercutes
        vont de 0,6 % a 6,8 %.
      - **Ce ne sont pas nos erreurs de transcription.** 12 de ces cas (10 PER,
        2 rendement) enjambent DEUX extractions independantes -- une seance venue
        de la collecte quotidienne, la suivante du bulletin mensuel. Deux codes
        differents ne recopient pas la meme valeur par hasard : c'est le BOC qui
        a publie la valeur figee. Cette confrontation etait IMPOSSIBLE avant le
        chantier C15, qui a verse le mensuel dans le quotidien le meme jour.
      - **L'exposition du moteur est aujourd'hui minime.** Aucun figement sur la
        derniere seance, donc aucun profil du jour n'en depend. Un seul des 108
        tombe sur un point de BPA ANNUEL lu par croissance_bpa_implicite (BOAS,
        31/12/2024), pour 0,63 % sur une borne de son CAGR.

    SEVERITES. Bloquant : un point de BPA annuel repose sur un PER fige hors du
    registre ci-dessus -- c'est un nombre que le moteur CALCULE, et le registre
    est adosse aux valeurs observees. En alerte : les plafonds de figements et la
    derniere seance, parce qu'une hausse vient du BOC et non du code, et que la
    doctrine de ce fichier ne bloque pas un commit pour un defaut de source.
    """
    print("\n=== 22. L'implicite du BOC dans le temps ===")
    if not DB.exists():
        verifie(False, "brvm.db absent : rien a mesurer", bloquant=False)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # PER a deux decimales -> demi-pas 0,005 ; rendement en FRACTION a quatre
    # decimales -> demi-pas 0,00005. Verifie sur la base avant de s'en servir.
    def decimales_max(champ):
        return max((len(("%.10f" % v).rstrip("0").split(".")[1])
                    for (v,) in cur.execute(
                        f"SELECT DISTINCT {champ} FROM cours_quotidien_boc "
                        f"WHERE {champ} IS NOT NULL")), default=0)

    d_per, d_rend = decimales_max("per"), decimales_max("rendement")
    verifie(d_per <= 2 and d_rend <= 4,
            f"granularite publiee confirmee (per {d_per} decimales, rendement {d_rend}) "
            f"— les marges d'arrondi en decoulent"
            + ("" if (d_per <= 2 and d_rend <= 4) else
               " — la granularite a change, les demi-pas de cette section sont a revoir"))

    figes_per, pop_per = _figements(cur, "per", 0.005)
    figes_rend, pop_rend = _figements(cur, "rendement", 0.00005)

    verifie(len(figes_per) <= FIGEMENTS_PER_MAX,
            f"{len(figes_per)} PER figes alors que le cours bougeait, sur {pop_per} seances "
            f"(plafond {FIGEMENTS_PER_MAX})"
            + ("" if len(figes_per) <= FIGEMENTS_PER_MAX else
               " — EN HAUSSE : " + ", ".join(f"{t} {d}" for t, d, *_ in figes_per[-3:])),
            bloquant=False)
    verifie(len(figes_rend) <= FIGEMENTS_RENDEMENT_MAX,
            f"{len(figes_rend)} rendements figes alors que le cours bougeait, sur {pop_rend} "
            f"seances (plafond {FIGEMENTS_RENDEMENT_MAX})"
            + ("" if len(figes_rend) <= FIGEMENTS_RENDEMENT_MAX else
               " — EN HAUSSE : " + ", ".join(f"{t} {d}" for t, d, *_ in figes_rend[-3:])),
            bloquant=False)

    # Garde-fou : une population vide rendrait les deux controles ci-dessus
    # trivialement verts. C'est le faux vert de la section 19 d'avant C15.
    verifie(pop_per > 40000 and pop_rend > 40000,
            f"la mesure porte sur une population reelle ({pop_per} seances pour le PER, "
            f"{pop_rend} pour le rendement)")

    derniere = cur.execute(
        "SELECT MAX(date_bulletin) FROM cours_quotidien_boc").fetchone()[0]
    du_jour = [f"{t} ({champ})"
               for champ, cas in (("per", figes_per), ("rendement", figes_rend))
               for t, d, *_ in cas if d == derniere]
    verifie(not du_jour,
            f"aucune valeur figee sur la derniere seance ({derniere}) : les profils du "
            f"jour ne reposent sur aucun champ perime"
            + ("" if not du_jour else " — ATTENTION : " + ", ".join(du_jour)
               + " ; le PER et le rendement de ces titres datent de la veille alors "
                 "que leur cours a bouge"),
            bloquant=False)

    # --- Bloquant : les points que le moteur CALCULE ------------------------
    # croissance_bpa_implicite() prend la DERNIERE seance de chaque annee.
    annuels = {}
    for ticker, date_b, cours, per in cur.execute(
            "SELECT ticker, date_bulletin, cours, per FROM cours_quotidien_boc "
            "WHERE ticker NOT LIKE 'TEST_%' AND per IS NOT NULL AND per > 0 "
            "AND cours IS NOT NULL ORDER BY ticker, date_bulletin"):
        annuels[(ticker, date_b[:4])] = date_b
    touches = {(t, d): v for t, d, _cp, _c, v, _var in figes_per
               if annuels.get((t, d[:4])) == d}
    inconnus = sorted(k for k in touches if k not in BPA_ANNUEL_SUR_PER_FIGE
                      or abs(BPA_ANNUEL_SUR_PER_FIGE[k] - touches[k]) > 0.001)
    verifie(not inconnus,
            f"{len(touches)} point(s) de BPA annuel reposent sur un PER fige, tous au "
            f"registre ({len(BPA_ANNUEL_SUR_PER_FIGE)} inscrit)"
            + ("" if not inconnus else
               " — HORS REGISTRE : " + ", ".join(f"{t} {d} (per {touches[(t, d)]})"
                                                 for t, d in inconnus)
               + " — le CAGR du BPA implicite de ce titre est faux du mouvement de "
                 "cours non repercute ; mesurer, puis inscrire au registre"))

    # --- Bloquant : les collisions d'echelle -------------------------------
    # Decouvertes en versant le mensuel dans le quotidien (C15) : la seance
    # mensuelle du 31/12/2018 de SAFC porte 5 300 quand les seances quotidiennes
    # qui l'encadrent portent 215. Un cours qui chute de 99,9 % et revient le
    # lendemain n'est pas un fait de marche, c'est une valeur d'une autre echelle.
    collisions = _collisions_echelle(cur)
    nouvelles = sorted(k for k in collisions if k not in COLLISIONS_ECHELLE)
    disparues = sorted(k for k in COLLISIONS_ECHELLE if k not in collisions)
    verifie(not nouvelles,
            f"{len(collisions)} collision(s) d'echelle, toutes au registre "
            f"({len(COLLISIONS_ECHELLE)} inscrites)"
            + ("" if not nouvelles else
               " — HORS REGISTRE : " + ", ".join(f"{t} {d} (facteur {collisions[(t, d)]})"
                                                 for t, d in nouvelles)
               + " — un cours qui chute puis revient au niveau d'avant n'est pas une "
                 "division de nominal : mesurer, puis corriger la serie ou inscrire"))
    verifie(not disparues,
            "les collisions inscrites au registre sont toujours la"
            + ("" if not disparues else
               " — DISPARUES : " + ", ".join(f"{t} {d}" for t, d in disparues)
               + " — soit la serie a ete corrigee (retirer du registre en le disant), "
                 "soit une seance a ete perdue"),
            bloquant=False)
    conn.close()


# ----------------------------------------------------------------------
# 20. profils.json COMMITE ET CODE COURANT PARLENT LA MEME LANGUE (bloquant)
# ----------------------------------------------------------------------
def test_forme_profils_json():
    """Le profils.json commite doit avoir la forme que profils.py produit aujourd'hui.

    POURQUOI CETTE SECTION EXISTE (30/09/2026, cycle 7). profils.json est un
    fichier COMMITE, regenere par profils.py. Mesure sur les 21 derniers commits qui
    modifient cours_quotidien_boc.csv : a chacun, le profils.json commite est en
    RETARD d'au moins une seance sur le CSV (21 sur 21) — retard voulu, puisque le
    workflow P13 le regenere une demi-heure plus tard, et sans consequence pour la
    fiche publiee, que pages.yml reconstruit. Comparer les VALEURS commitees aux
    valeurs regenerees serait donc un faux positif quotidien.

    Ce qui, en revanche, ne doit jamais deriver : la FORME. Un commit qui change
    profils.py (champ ajoute, renomme, retire) sans regenerer le fichier laisserait
    app.py lire un champ absent, en silence (`.get()` rend None). Le controle compare
    la liste des titres et, pour chacun, l'ensemble des champs, entre le fichier
    commite (git HEAD) et le fichier que la barriere vient de regenerer.
    """
    print("\n=== 20. Forme de profils.json : commite contre regenere (bloquant) ===")
    import json
    chemin = RACINE / "collecte" / "profils.json"
    if not chemin.exists():
        verifie(False, "collecte/profils.json absent", bloquant=False)
        return
    try:
        r = subprocess.run(["git", "show", "HEAD:collecte/profils.json"], cwd=str(RACINE),
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        verifie(True, f"git indisponible ({type(e).__name__}) — controle ignore", bloquant=False)
        return
    if r.returncode != 0:
        verifie(True, "profils.json non suivi par git (HEAD) — controle ignore", bloquant=False)
        return
    commite = json.loads(r.stdout)
    regenere = json.loads(chemin.read_text(encoding="utf-8"))
    verifie(len(regenere) >= 40, f"profils.json regenere couvre {len(regenere)} titres "
                                 f"— sans quoi la comparaison ne prouverait rien")
    titres_diff = sorted(set(commite) ^ set(regenere))
    verifie(not titres_diff,
            f"memes titres dans le fichier commite et le regenere ({len(regenere)})"
            + ("" if not titres_diff else " — DIFFERENCE : " + ", ".join(titres_diff[:8])))
    derive = []
    for t in sorted(set(commite) & set(regenere)):
        a, b = set(commite[t]), set(regenere[t])
        if a != b:
            derive.append(f"{t} (commite seul : {sorted(a - b)} ; regenere seul : {sorted(b - a)})")
    if derive and os.environ.get("GITHUB_ACTIONS") != "true":
        # En local, une difference de forme est LEGITIME tant que le changement de
        # profils.py et le profils.json regenere ne sont pas commites ensemble. Le
        # controle se durcit en CI, ou HEAD est le commit qui vient d'etre pousse.
        verifie(True, f"forme de profils.json modifiee localement sur {len(derive)} titre(s), "
                      f"non commitee — controle applique en CI (GITHUB_ACTIONS), "
                      f"a commiter avec profils.py")
        return
    verifie(not derive,
            "chaque titre porte les memes champs dans le commite et le regenere"
            + ("" if not derive else f" — DERIVE sur {len(derive)} titre(s) : " + " ; ".join(derive[:3])
               + " — regenerer et commiter collecte/profils.json"))


# ----------------------------------------------------------------------
# 21. DISTRIBUTIONS NON RECURRENTES (bloquant)
# ----------------------------------------------------------------------
PLAUSIBILITE_PRIME = 0.10   # au-dela de +10 points sur le taux sans risque, le drapeau est obligatoire


def test_distribution_non_recurrente():
    """Un rendement facial hors norme doit porter son drapeau et sortir des classements.

    POURQUOI CETTE SECTION EXISTE (chantier C1, 30/09/2026). FTSC portait une prime
    de rendement de +79,5 points (rendement 86,54 %) et SIVC de +19,7 points ; les
    45 autres titres tenaient entre -6,1 et +0,7. Aucune erreur de donnee : Filtisac
    a bien verse 1 726,56 FCFA le 30/09/2025 (7,3 fois le plus fort des cinq versements
    precedents, 235), et le dividende de reference de SIVC date de 2017. Le rendement
    est exact et n'est pas un rendement de revenu.

    Jurisprudence en trois cas, chacun avec son contre-exemple (comme la section 5) :
      - FTSC (exceptionnel) et SIVC (perime) DOIVENT porter le drapeau ;
      - BICC verse 1 157 apres 831 (serie croissante, 1,4x le plus fort precedent) :
        NE DOIT PAS le porter, sinon la regle marque toute banque qui croit ;
      - NEIC et STBC dont la table n'a pas le dernier versement (C5) : le dividende
        implicite du BOC (rendement x cours) ne coincide avec aucun versement date,
        donc AUCUN drapeau — un trou de table n'est pas un dividende perime.
    """
    print("\n=== 21. Distributions non recurrentes (bloquant) ===")
    import json
    import sqlite3
    sys.path.insert(0, str(ICI))
    from profils import date_dividende, diagnostic_distribution

    # --- Regle pure, sur une base jetable -------------------------------------
    sp = dict(distribution_ratio_max=3.0, distribution_age_max_ans=2,
              distribution_historique_min=3, distribution_tolerance_implicite=0.10)
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE dividendes (ticker TEXT, montant_net REAL, "
                 "date_paiement TEXT, statut_donnee TEXT)")

    def serie(t, montants, dates):
        for m, d in zip(montants, dates):
            conn.execute("INSERT INTO dividendes VALUES (?,?,?,'VALIDE')", (t, m, d))

    serie("X3", [100, 100, 100, 300], ["1-juil.-21", "1-juil.-22", "1-juil.-23", "1-juil.-25"])
    serie("X4", [100, 100, 100, 301], ["1-juil.-21", "1-juil.-22", "1-juil.-23", "1-juil.-25"])
    serie("X2", [100, 500], ["1-juil.-24", "1-juil.-25"])
    serie("OLD", [50], ["1-juil.-21"])
    cur = conn.cursor()
    ok3, _ = diagnostic_distribution(cur, "X3", "2026-09-29", sp)
    ok4, _ = diagnostic_distribution(cur, "X4", "2026-09-29", sp)
    ok2, _ = diagnostic_distribution(cur, "X2", "2026-09-29", sp)
    verifie(not ok3 and ok4,
            "le seuil est fige : 3,00x le plus fort des precedents ne declenche pas, 3,01x oui")
    verifie(not ok2,
            "sous 3 versements precedents, l'ampleur ne se juge pas : aucun drapeau (case vide, pas estimation)")
    perime, _ = diagnostic_distribution(cur, "OLD", "2026-09-29", sp, cours=1000, dy=0.05)
    verifie(perime, "un rendement du BOC qui repose sur un dividende de plus de deux ans est perime")
    trou, _ = diagnostic_distribution(cur, "OLD", "2026-09-29", sp, cours=1000, dy=0.14)
    verifie(not trou,
            "un dividende implicite (140) sans versement date correspondant ne conclut pas : "
            "un trou de la table n'est pas un dividende perime")

    # Correction du 30/09/2026 (journal, cycle 7). La premiere version de la regle
    # retenait le versement le plus proche EN MONTANT parmi TOUTES les dates : un
    # vieux versement dont le montant coincide par hasard faisait conclure
    # "perime" sur un titre qui a distribue depuis. Quatre titres reels etaient
    # dans ce cas (NTLC, SDCC, SIBC, SMBC). Le BOC divise par le DERNIER dividende
    # paye : la coincidence ne vaut que sur le plus recent de la table.
    serie("COINCIDENCE", [100, 180], ["1-juil.-21", "1-juil.-25"])
    faux, _ = diagnostic_distribution(cur, "COINCIDENCE", "2026-09-29", sp,
                                      cours=1000, dy=0.10)
    verifie(not faux,
            "un vieux versement dont le montant coincide (100 en 2021) ne conclut pas "
            "quand la table porte un versement POSTERIEUR (180 en 2025) : la reference "
            "du BOC nous echappe")

    verifie(date_dividende("30-sept.-25") is not None and date_dividende("3-foo.-25") is None
            and date_dividende("2025-09-30") is not None,
            "un mois francais non reconnu est refuse, pas devine")

    # --- Illisibilite des dates de la base -------------------------------------
    if DB.exists():
        c = sqlite3.connect(DB)
        illisibles = [r for r in c.execute(
            "SELECT ticker, date_paiement FROM dividendes WHERE date_paiement IS NOT NULL")
            if date_dividende(r[1]) is None]
        c.close()
        verifie(not illisibles,
                f"aucune date de dividende illisible dans brvm.db ({len(illisibles)} trouvee(s))"
                + ("" if not illisibles else " : " + str(illisibles[:4])))

        # Le meme controle que l'injection COINCIDENCE ci-dessus, mais sur le
        # fonds reel : un titre declare "dividende perime" ne doit pas porter,
        # dans la meme table, un versement POSTERIEUR a celui que le motif nomme.
        # C'est ce qui a ete mesure et corrige le 30/09/2026 sur quatre titres.
        c = sqlite3.connect(DB)
        contredits = []
        for t, v in sorted(json.loads(
                (RACINE / "collecte" / "profils.json").read_text(encoding="utf-8")).items()):
            motif = v.get("distribution_non_recurrente") or ""
            if "verse le " not in motif:
                continue
            nomme = motif.split("verse le ", 1)[1][:10]
            dates = [date_dividende(d) for (d,) in c.execute(
                "SELECT date_paiement FROM dividendes WHERE ticker=? AND montant_net > 0 "
                "AND COALESCE(statut_donnee,'VALIDE')='VALIDE' AND date_paiement IS NOT NULL",
                (t,))]
            plus_recent = max([d for d in dates if d is not None], default=None)
            if plus_recent is not None and plus_recent.isoformat() > nomme:
                contredits.append("%s : motif sur %s, table jusqu'a %s"
                                  % (t, nomme, plus_recent.isoformat()))
        c.close()
        verifie(not contredits,
                "aucun drapeau de dividende perime n'est contredit par un versement "
                "posterieur de la meme table"
                + ("" if not contredits else " — " + " ; ".join(contredits)))

    # --- Jurisprudence sur profils.json regenere --------------------------------
    chemin = RACINE / "collecte" / "profils.json"
    if not chemin.exists():
        verifie(False, "collecte/profils.json absent", bloquant=False)
        return
    pj = json.loads(chemin.read_text(encoding="utf-8"))

    def porte(t):
        return "DISTRIBUTION_NON_RECURRENTE" in ((pj.get(t) or {}).get("drapeaux") or [])

    for t in ("FTSC", "SIVC"):
        v = pj.get(t) or {}
        verifie(porte(t) and v.get("prime_rendement") is None and v.get("dy_recurrent") is None
                and v.get("distribution_non_recurrente"),
                f"{t} porte le drapeau, sa prime et son rendement recurrent sont vides, "
                f"le motif est ecrit (rendement facial {v.get('dy')} % conserve)")
    for t, pourquoi in (("BICC", "serie croissante"), ("NEIC", "trou de table"),
                        ("STBC", "trou de table")):
        verifie(t in pj and not porte(t), f"{t} ne porte PAS le drapeau ({pourquoi})")
    # Reecrit le 30/09/2026 : NTLC et SMBC ne portent plus le drapeau depuis la
    # correction de la regle 1, donc la formulation d'origine passait a vide. La
    # propriete a garder est celle du code : le drapeau ne fait pas partie de ceux
    # que le grade lit, quel que soit le titre qui le porte.
    from profils import _drapeaux_de_croissance as _dc
    verifie("DISTRIBUTION_NON_RECURRENTE" not in _dc(
                {"drapeaux": ["CROISSANCE_CORROBOREE", "DISTRIBUTION_NON_RECURRENTE"]}),
            "le drapeau est exclu des drapeaux que le grade note : il ne deplace "
            "aucun verdict de confiance")
    for t in ("NTLC", "SDCC", "SIBC", "SMBC"):
        verifie(t in pj and not porte(t),
                f"{t} ne porte PAS le drapeau (coincidence de montant sur un vieux "
                f"versement, alors que la table en porte un posterieur)")

    taux = next((v.get("taux_reference") for v in pj.values() if v.get("taux_reference")), None)
    if taux is None:
        verifie(False, "taux_reference absent de profils.json", bloquant=False)
        return
    trop_hauts = sorted(t for t, v in pj.items()
                        if v.get("dy") is not None and v["dy"] / 100 - taux > PLAUSIBILITE_PRIME
                        and not porte(t))
    verifie(not trop_hauts,
            f"aucune prime de rendement au-dela de +{PLAUSIBILITE_PRIME * 100:.0f} points sans le drapeau"
            + ("" if not trop_hauts else " — SANS DRAPEAU : " + ", ".join(trop_hauts)))
    primes = [v["prime_rendement"] for v in pj.values() if v.get("prime_rendement") is not None]
    verifie(primes and max(primes) < PLAUSIBILITE_PRIME,
            f"la plus forte prime restante est de {max(primes) * 100:+.1f} points "
            f"(plancher de plausibilite +{PLAUSIBILITE_PRIME * 100:.0f})")


# ----------------------------------------------------------------------
# 15. FONDS DES NOTATIONS FINANCIERES (bloquant)
# ----------------------------------------------------------------------
def test_fonds_notations():
    """La collecte des notations doit AVANCER, jamais reculer.

    POURQUOI CETTE SECTION EXISTE (27/09/2026). L'audit du 26/09 lisait
    "356 rapports NON_EXTRAIT sur 385" comme un echec de l'extracteur. C'en
    etait l'inverse : un seul ECHEC reel : les 355 autres n'avaient jamais ete
    TENTEES. L'extracteur etait plafonne a --pdf annonces, prenait les plus
    recentes, puis REECRIVAIT tout le fichier. Les 30 lignes portant un statut
    etaient donc exactement les 30 annonces les plus recentes, coupure au jour
    pres, et chaque passage mensuel repassait sur les memes.

    Le correctif rend la collecte cumulative. Ce test garde la propriete qui
    compte : le nombre de rapports exploites ne doit jamais DIMINUER. Si un
    jour il baisse, c'est que le fichier a ete reecrit a zero — la panne
    silencieuse d'origine.
    """
    print("\n=== 15. Fonds des notations financieres (bloquant) ===")
    chemin = RACINE / "collecte" / "notations_financieres.csv"
    if not chemin.exists():
        verifie(False, "collecte/notations_financieres.csv absent : la collecte P12 "
                       "n'a jamais tourne", bloquant=False)
        return
    import csv as _csv
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = list(_csv.DictReader(f))
    statuts = {}
    for r in lignes:
        s = r.get("statut_extraction") or "VIDE"
        statuts[s] = statuts.get(s, 0) + 1
    exploitees = statuts.get("OK", 0) + statuts.get("SANS_NOTE", 0)
    print("       statuts : %s" % ", ".join("%s=%d" % kv for kv in sorted(statuts.items())))

    # Plancher releve le 27/09/2026 apres quatre passages de reprise : le fonds
    # est passe de 29 a 378 rapports exploites. Il doit MONTER a chaque passage
    # de P12 ; on ne l'abaisse que si la BRVM retire reellement des rapports.
    #
    # Ce plancher a une raison d'etre precise : au cours de la reprise, UNE
    # ligne deja extraite (STBC du 05/05/2026, note AA+) a disparu du fichier
    # parce qu'elle etait sortie de l'index de la BRVM et que la fusion ne
    # conservait que les lignes encore indexees. Corrige dans notations.py, et
    # ce plancher est le filet.
    PLANCHER_EXPLOITEES = 370
    verifie(exploitees >= PLANCHER_EXPLOITEES,
            f"{exploitees} rapports exploites (plancher {PLANCHER_EXPLOITEES}) — "
            f"une baisse signale que le fichier a ete reecrit a zero")

    # L'acquis doit etre complet : une ligne exploitee porte son agence et sa note.
    incompletes = sorted(
        r["url_pdf"].rsplit("/", 1)[-1] for r in lignes
        if r.get("statut_extraction") == "OK" and not (r.get("agence") and r.get("note_lt")))
    verifie(not incompletes,
            "chaque rapport marque OK porte son agence et sa note"
            + ("" if not incompletes else f" — incomplets : {incompletes[:5]}"))

    # Une URL ne doit apparaitre qu'une fois : un doublon signifierait que la
    # fusion avec l'acquis a duplique au lieu de remplacer.
    urls = [r.get("url_pdf") for r in lignes if r.get("url_pdf")]
    doublons = sorted({u.rsplit("/", 1)[-1] for u in urls if urls.count(u) > 1})
    verifie(not doublons,
            "aucune URL en double dans le fonds"
            + ("" if not doublons else f" — doublons : {doublons[:5]}"))

    # Le code doit porter la reprise cumulative : sans elle, tout recommence.
    code = (RACINE / "collecte" / "notations.py").read_text(encoding="utf-8")
    verifie("lire_acquis" in code and "STATUTS_ACQUIS" in code,
            "collecte/notations.py relit l'acquis avant d'extraire")
    verifie("agence_canonique" in code,
            "collecte/notations.py normalise le nom des agences")

    # Une meme agence sous deux orthographes casserait le rapprochement des
    # variations de note, que le moteur ne fait QUE chez une meme agence.
    # Mesure du 27/09 : "Bloomfield Investment Corporation" 235 fois,
    # "Bloomfield" 7 fois, pour la meme agence.
    VARIANTES = {"Bloomfield": "Bloomfield Investment Corporation",
                 "GCR Ratings": "GCR"}
    trouvees = sorted({r["agence"] for r in lignes if r.get("agence")})
    fautives = sorted(a for a in trouvees if a in VARIANTES)
    verifie(not fautives,
            f"les agences portent un nom canonique (trouve : {trouvees})"
            + ("" if not fautives else f" — a normaliser : {fautives}"))

    restantes = statuts.get("NON_EXTRAIT", 0)
    if restantes:
        verifie(False, f"{restantes} rapports jamais tentes — relancer le workflow P12 "
                       f"(l'acquis n'est plus efface, chaque passage avance le front)",
                bloquant=False)


def main():
    sans_app = "--sans-app" in sys.argv
    print("=" * 60)
    print("TESTS DE NON-REGRESSION — donnees et application")
    print("=" * 60)
    test_fraicheur()
    test_coherence_frequence()
    test_source_cours()
    test_resultat_non_operationnel()
    test_echelles()
    test_per_normalise_et_operations()
    test_avis_brvm()
    test_fondamentaux_a_jour()
    test_statuts_cotation()
    test_integrite_app()
    test_arbitrage()
    test_base_reference()
    test_fondamentaux_agregateur()
    test_fonds_notations()
    test_idempotence_peupler()
    test_chaine_chargement()
    test_panne_de_chargeur()
    test_confrontation_cours()
    test_implicite_boc()
    test_forme_profils_json()
    test_distribution_non_recurrente()
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
