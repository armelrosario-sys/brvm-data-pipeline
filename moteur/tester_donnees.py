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
        "plan cherte x croissance": "Plan cherte",
        "taux sans risque": "Taux sans risque",
        "onglet Explorer": "Telecharger (CSV)",
        "fiche titre": "Pourquoi ce profil",
        "qualite des donnees": "Limites permanentes",
    }
    manquantes = [nom for nom, motif in sections.items() if motif not in code]
    verifie(not manquantes,
            f"app.py contient toutes ses sections"
            + ("" if not manquantes else f" — MANQUANTES : {', '.join(manquantes)}"))

    lignes = code.count("\n")
    verifie(lignes >= 700,
            f"app.py fait {lignes} lignes (une chute nette signale une troncature)")


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
