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
import json
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
    """(a) Le PER normalise est RETIRE et doit le rester. (b) Operations sur titre.

    (a) POURQUOI CETTE MOITIE A CHANGE DE SENS (chantier C23, 02/10/2026). Elle
        verifiait que le PER normalise restait calcule et que le drapeau
        BENEFICE_NON_REPRESENTATIF restait discriminant. Claudia a signale le
        01/10 que ce nombre etait faux sur le tableau de bord publie, et la
        mesure lui a donne raison : PER x (dernier benefice / moyenne des quatre
        derniers) mesure la CROISSANCE, pas un pic. Sur une serie geometrique de
        taux g, le dernier terme depasse la moyenne de quatre termes d'environ
        1,5 g sans qu'il y ait de pic ; les huit titres a serie strictement
        croissante voyaient leur PER gonfle de 12 a 119 % (BOAC 12,9 -> 16,2 sur
        20069-26075-32044-35540, CABC 14,0 -> 16,9, SHEC 24,7 -> 31,4).

        Trois lectures ont ete mesurees -- la moyenne, la tendance par regression
        log-lineaire, et le retrait. Claudia a tranche le 02/10 : RETRAIT
        DEFINITIF. Le drapeau est parti avec la mesure : il se declenchait sur le
        MEME rapport, et retenait donc BICC et SLBC, qui croissent sans pic.

        Les controles ci-dessous gardent le retrait, des deux cotes : le code ne
        porte plus la mesure, et le fichier publie ne porte plus ses champs. Un
        seul des deux ne suffirait pas -- une fonction rebranchee sans champ
        expose, ou un champ reintroduit depuis ailleurs, passeraient l'autre.

    (b) Operations sur titre : SOLIBRA a divise son nominal le 27/09/2024 (cours
        de ~95 000 a 10 215 en une seance) sans que l'operation soit enregistree.
        Toutes ses performances sur deux ans en etaient faussees. Une chute de
        plus de 60 % en une seule seance est presque toujours une division de
        nominal, pas un krach : on la signale.
    """
    print("\n=== 7. Retrait du PER normalise et operations sur titre (bloquant) ===")
    import json
    f = RACINE / "collecte" / "profils.json"
    if not f.exists():
        verifie(False, "profils.json absent", bloquant=False)
        return
    profils = json.loads(f.read_text(encoding="utf-8"))

    # --- (a) Le PER normalise est retire, et des deux cotes -------------------
    moteur_src = (ICI / "profils.py").read_text(encoding="utf-8")
    verifie("def per_normalise(" not in moteur_src,
            "moteur/profils.py ne definit plus per_normalise() (C23, retrait "
            "definitif tranche par Claudia le 02/10/2026)")
    verifie('drapeaux + ["BENEFICE_NON_REPRESENTATIF"]' not in moteur_src,
            "moteur/profils.py n'emet plus le drapeau BENEFICE_NON_REPRESENTATIF, "
            "qui se declenchait sur le meme rapport et portait le meme defaut")

    # Cote fichier publie : aucun titre ne doit plus porter ces champs ni ce
    # drapeau. Le controle sur le code ne suffit pas -- profils.json pourrait
    # garder d'anciennes valeurs si personne ne le regenerait.
    restes = sorted(t for t, v in profils.items()
                    if any(v.get(c) is not None for c in
                           ("per_normalise", "ecart_benefice", "n_ex_normalise"))
                    or "BENEFICE_NON_REPRESENTATIF" in (v.get("drapeaux") or []))
    verifie(not restes,
            f"aucun des {len(profils)} titres de collecte/profils.json ne porte "
            f"encore per_normalise, ecart_benefice, n_ex_normalise ni le drapeau"
            + ("" if not restes else f" — RESTES : {restes}"))

    # Et l'affichage, qui etait le premier symptome vu par Claudia.
    rendu = []
    for chemin in [APP] + sorted((RACINE / "dashboard").glob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        for motif in ("r.per_norm", "per_normalise", "ecart_ben",
                      "BENEFICE_NON_REPRESENTATIF"):
            if motif in texte:
                rendu.append(f"{chemin.name} : {motif}")
    verifie(not rendu,
            "ni app.py ni dashboard/*.py ne nomment plus la mesure retiree"
            + ("" if not rendu else " — RESTES : " + ", ".join(rendu)))

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
        # SEUIL BAS RETIRE le 03/10/2026 (C18, cycle 17). Ce controle triait sur
        # `var < -0.60 ET var > -0.995`, en commentant « on ignore les erreurs de
        # saisie manifestes (facteur ~1000) ». Les deux seules chutes que cette
        # borne ecartait etaient SLBC 2022-01-12 et 2023-06-02 : elles n'etaient
        # enregistrees NULLE PART, ni ici, ni dans operations_sur_titre.csv, et
        # restaient dans le CSV commite et dans la base. Un controle qui ecarte
        # en silence ne surveille pas, il rassure. Les deux sont corrigees par
        # outils/correction_collisions_echelle.py ; la borne disparait, et ce qui
        # reste a ecarter doit l'etre nommement, par le registre COLLISIONS_ECHELLE.
        suspects = c[c["var"] < -0.60]
        connues = set()
        if ops.exists():
            o = pd.read_csv(ops)
            connues = {(r.ticker, str(r.date)[:7]) for r in o.itertuples()}
        # Volontairement SANS exclure le registre COLLISIONS_ECHELLE : ses deux
        # entrees restantes sont une division de nominal REELLE (SAFC 2018-12-21)
        # et son artefact, c'est-a-dire exactement ce que cette alerte doit
        # continuer de reclamer a C4. Filtrer sur le registre reviendrait a
        # masquer la seule date que C4 doit documenter.
        non_tracees = [(r.ticker, str(r.date_bulletin)[:10])
                       for r in suspects.itertuples()
                       if (r.ticker, str(r.date_bulletin)[:7]) not in connues]
        verifie(len(non_tracees) == 0,
                "aucune division de nominal non enregistree"
                + ("" if not non_tracees
                   else f" — a documenter dans operations_sur_titre.csv : {non_tracees}"),
                bloquant=False)

        # Ce que l'ancienne borne basse cachait : une chute de plus de 99,5 % en
        # une seance n'est pas un fait de marche. Elle est maintenant NOMMEE,
        # qu'elle soit au registre des collisions ou non.
        enormes = [(r.ticker, str(r.date_bulletin)[:10], round(r.var, 5))
                   for r in c[c["var"] <= -0.995].itertuples()]
        hors_registre = [e for e in enormes if (e[0], e[1]) not in COLLISIONS_ECHELLE]
        verifie(not hors_registre,
                f"aucune chute de plus de 99,5 % dans la serie ({len(enormes)} vue(s))"
                + ("" if not hors_registre else
                   " — : " + ", ".join(f"{t} {d} ({v})" for t, d, v in hors_registre)
                   + " — un cours ne perd pas 99,5 % en une seance : mesurer, puis "
                     "corriger la serie par un script de migration dans outils/ ou "
                     "inscrire au registre COLLISIONS_ECHELLE avec son motif ; ce "
                     "controle ne les ecarte plus en silence, comme le faisait le "
                     "seuil bas retire ci-dessus"))


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

    # Les quatre cadrans du plan sortent en TABLEAUX (02/10/2026, demande de
    # Claudia). Ils sortaient en listes a puces, une phrase par titre, ou le PER,
    # le rendement et la croissance se suivaient separes par des points mediums :
    # illisible des cinq titres, et surtout incomparable d'une ligne a l'autre.
    #
    # Les deux controles ci-dessous gardent la propriete qui compte, et ce n'est
    # pas la forme du tableau : c'est que les colonnes chiffrees restent
    # NUMERIQUES, le formatage etant delegue a column_config. Mises en forme en
    # chaines, elles se trieraient alphabetiquement a la premiere colonne cliquee
    # et "9.3" passerait apres "14.0" -- le defaut que C10 a corrige dans la table
    # des dividendes, reintroduit cette fois a l'ecran.
    verifie("COLONNES_ZONE" in code and "st.dataframe(_table_zone(" in code,
            "les cadrans du plan sortent en tableaux (st.dataframe + column_config)")
    for colonne in ("PER", "Rendement", "Croissance", "Decote"):
        motif = f'"{colonne}": st.column_config.NumberColumn'
        verifie(motif in code,
                f"la colonne {colonne} des cadrans reste NUMERIQUE (NumberColumn) : "
                f"formatee en chaine, le tri de l'en-tete redeviendrait alphabetique")



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

    # Jusqu'au 04/10/2026, un alias traduisait BBGC (chaine pipeline/) vers
    # BBGCI (moteur), parce que la base portait un mnemonique provisoire. C27 a
    # tranche sur l'avis BRVM de premiere cotation : le mnemonique officiel est
    # BBGC, la base a ete renommee, l'alias est vide. Le controle est retourne —
    # il verifie maintenant que Bridge Bank arrive sous son vrai nom et que
    # l'ancien code provisoire a bien disparu des deux cotes.
    verifie("BBGC" in agr and "BBGCI" not in agr,
            "Bridge Bank est lu sous le mnemonique officiel BBGC, sans alias")

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

    Les controles ci-dessous. Le premier bloque le jour ou app.py lit une
    table que sa chaine ne remplit pas. Le second bloque le jour ou un chargeur
    nouveau est ajoute a collecte/ sans etre branche dans pages.yml — c'est la
    meme divergence, prise a l'autre bout. Le TROISIEME (ajoute le 01/10/2026,
    cycle 11) porte le meme invariant sur tout workflow qui recalcule ET commite
    collecte/profils.json : le 30/09 a 22h37, P13 a commite un profils.json
    recalcule sur une chaine amputee, qui avait perdu les six drapeaux de C1.
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

    # --- Controle C : TOUT workflow qui recalcule ET commite profils.json -----
    #
    # POURQUOI CE CONTROLE EXISTE (chasse du cycle 11, 01/10/2026). Le controle B
    # ci-dessus ne regardait que pages.yml, qu'il appelle "la chaine de
    # reference". Or pages.yml PUBLIE le tableau de bord : il ne commite rien.
    # Deux autres workflows, eux, reconstruisent collecte/profils.json et le
    # COMMITENT — avis_brvm.yml (P13, quotidien) et notations.yml (P12) — et
    # aucun controle ne les regardait.
    #
    # Mesure, et ce n'est pas un defaut latent. Le 30/09/2026 a 22h37, P13 a
    # commite profils.json (548639e, 1 025 lignes changees) apres l'avoir
    # recalcule sur une chaine de QUATRE scripts qui omettait
    # charger_dividendes_exercice.py. Reproduit a l'identique le 01/10 : la table
    # dividendes passe de 311 lignes a 15, et les SIX drapeaux
    # DISTRIBUTION_NON_RECURRENTE de C1 disparaissent — FTSC retrouvait une prime
    # de rendement de +80,35 points et SIVC de +19,74, les valeurs exactes du
    # fichier commite. Le fichier publie contredisait donc le code depuis
    # huit heures, et la section 21 l'aurait vu si tests.yml avait tourne entre
    # temps : aucun workflow de collecte ne lance les barrieres.
    #
    # C'est la regression n°2 de l'en-tete de ce fichier pour la troisieme fois,
    # par une troisieme porte : app.py (C13, section 18), puis les workflows ici.
    # L'invariant est donc celui du controle A, applique aux workflows : qui
    # reconstruit un fichier de reference l'a reconstruit sur la base COMPLETE.
    # Ce controle cherche les scripts REELLEMENT LANCES, pas les noms cites.
    # Premiere version ecrite ce cycle : elle testait `nom not in texte`, et elle
    # passait a vide — le commentaire que je venais d'ajouter dans avis_brvm.yml
    # NOMMAIT charger_dividendes_exercice.py, ce qui suffisait a la satisfaire.
    # Verifie par injection : la chaine amputee doit faire ECHOUER ce controle.
    def _scripts_lances(texte):
        return {Path(m).name for m in re.findall(
            r"^\s*python3?\s+(?:-\S+\s+)*(\S+\.py)", texte, re.M)}

    wf = sorted((RACINE / ".github" / "workflows").glob("*.yml"))
    verifie(bool(wf), ".github/workflows/ contient des workflows a controler")
    manquants = []
    recalculeurs = []
    for f in wf:
        texte = f.read_text(encoding="utf-8")
        lances = _scripts_lances(texte)
        commite = re.search(r"git add[^\n]*(\n[^\n]*)?collecte/profils\.json", texte)
        if not ("profils.py" in lances and commite):
            continue
        recalculeurs.append(f.name)
        absents_wf = [ch.name for ch in chargeurs if ch.name not in lances]
        if absents_wf:
            manquants.append("%s omet %s" % (f.name, ", ".join(absents_wf)))
    verifie(not manquants,
            f"les {len(recalculeurs)} workflow(s) qui recalculent ET commitent "
            f"profils.json enchainent les {len(chargeurs)} chargeurs "
            f"({', '.join(recalculeurs) or 'aucun'})"
            + ("" if not manquants else " — CHAINE AMPUTEE : " + " ; ".join(manquants)))

    # Et le corollaire : un recalcul en echec ne doit pas committer le fichier.
    # Sans cette garde, la chaine complete ne suffit pas — il reste la panne.
    #
    # Le controle porte sur l'ETAPE qui ajoute profils.json, pas sur le fichier
    # entier. Premiere version ecrite ce cycle : elle cherchait
    # "steps.profils.outcome" n'importe ou dans le YAML, et elle passait a vide —
    # les deux workflows nomment deja cette sortie dans leur etape "Resume",
    # pour afficher un avertissement. Verifie par injection.
    import yaml
    sans_garde = []
    for nom in recalculeurs:
        texte = (RACINE / ".github" / "workflows" / nom).read_text(encoding="utf-8")
        etapes = [e for j in (yaml.safe_load(texte).get("jobs") or {}).values()
                  for e in (j.get("steps") or []) if isinstance(e, dict)]
        ajouts = [e for e in etapes
                  if "collecte/profils.json" in (e.get("run") or "")
                  and "git add" in (e.get("run") or "")]
        if not ajouts:
            sans_garde.append("%s : aucune etape n'ajoute profils.json" % nom)
            continue
        for e in ajouts:
            cond_etape = str(e.get("if") or "")
            env = " ".join(str(v) for v in (e.get("env") or {}).values())
            vu = ("steps.profils.outcome" in cond_etape
                  or ("steps.profils.outcome" in env
                      and re.search(r"^\s*if \[", e.get("run") or "", re.M)))
            if not vu:
                sans_garde.append("%s : l'etape « %s » ajoute profils.json sans "
                                  "conditionner au succes du recalcul"
                                  % (nom, e.get("name") or "sans nom"))
    verifie(not sans_garde,
            f"les {len(recalculeurs)} workflow(s) subordonnent l'ajout de profils.json "
            f"au succes du recalcul, dans l'etape qui l'ajoute"
            + ("" if not sans_garde else " — SANS GARDE : " + " ; ".join(sans_garde)))

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
# nominal ne revient jamais sur ses pas : un tel cas est une valeur d'une AUTRE
# echelle deposee dans la serie, pas une operation sur titre. Voir C18.
#
# DE CINQ A DEUX le 03/10/2026 (C18, cycle 17). Trois entrees sont parties parce
# que la serie est corrigee ; les deux qui restent sont la pour une tout autre
# raison, et il faut la lire avant d'y toucher.
#
#   * SLBC 2022-01-12 (154 -> 154 000) et 2023-06-02 (67,6 -> 67 600) : facteur
#     1 000 exact des deux cotes, confirme par le PER publie sur la ligne meme.
#     Le facteur 1 080,99 qui etait inscrit ici pour la seconde etait mesure
#     contre la seance d'avant, alors que le cours de SLBC BAISSAIT dans cette
#     fenetre : la seance n'avait aucune raison de revenir a 73 075.
#   * STBC 2018-07-12 (11 315 -> 44 995) : pas une erreur d'echelle (facteur 3,98,
#     aucun facteur rond) mais une valeur fausse, le rendement 9,17 % publie sur
#     la ligne imposant un cours entre 44 948 et 45 001 avec le dividende de
#     4 124 FCFA alors en vigueur.
#
# LES DEUX QUI RESTENT NE SONT PAS DES COLLISIONS, et le detecteur ne peut pas le
# voir : il signale la seance de CHUTE, jamais celle du RETOUR. SAFC a subi une
# DIVISION DE NOMINAL AU VINGT-CINQUIEME fin decembre 2018 -- le dividende que le
# BOC publie passe de 576,00 a 23,04 entre les bulletins de novembre et de
# decembre (576 / 23,04 = 25,0 exact) et la serie reste a 215, 210, 200 pendant
# toute l'annee 2019. La chute est donc l'evenement reel ; ce sont les retours a
# 5 300 des 2018-12-31 et 2019-01-04 qui sont fautifs.
#
# Ces deux lignes fautives ne sont PAS corrigees : le 31/12 est une copie de la
# ligne mensuelle versee par C15, et la corriger ferait tomber la section 19, qui
# exige l'egalite au franc entre les deux series. Arbitrage inscrit en C30.
# Les deux entrees ci-dessous disparaitront d'elles-memes quand il sera tranche.
#
# Proces-verbal : outils/correction_collisions_echelle.py (idempotent).
# Une entree nouvelle ici doit porter son facteur mesure et son motif ecrit.
COLLISIONS_ECHELLE = {
    ("SAFC", "2018-12-21"): 24.65,
    ("SAFC", "2019-01-02"): 24.65,
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

    # --- C16, option (b) : l'axe de decote ne lit plus le rendement facial ----
    #
    # POURQUOI CES CONTROLES EXISTENT (chantier C16, 01/10/2026, cycle 11).
    # C1 avait retire le rendement facial de la prime et des classements, mais
    # l'avait laisse dans l'axe de DECOTE, parce que le retirer deplace des
    # verdicts. Les trois options ont ete mesurees au cycle 9 ; Claudia a
    # tranche l'option (b) -- case vide -- le 30/09/2026. Rien ne surveillait
    # cette regle : la decision ne vivait que dans un commentaire.
    #
    # Le controle tourne sur un bassin JETABLE de quatre titres, donc il ne
    # depend d'aucune donnee du jour, et il porte son CONTRE-EXEMPLE : les
    # memes quatre titres avec le rendement facial remis dans l'axe -- ce que
    # serait l'option (a) -- doivent donner d'autres rangs. Sans ce
    # contre-exemple, le controle passerait aussi sur l'option refusee.
    from profils import bassins_et_axes

    def _titre(per, dy, dy_axe):
        return {"per": per, "dy": dy, "dy_axe": dy_axe, "g": None, "secteur": "S"}

    # Secteur de 4 titres : sous n_secteur_min=8, la reference est le MARCHE.
    # A, B, C sont sains (dy_axe = dy) ; D est drapeaute : son rendement facial
    # de 1,00 % est faux (dividende perime) et son PER est celui de A.
    sains = {"A": _titre(10.0, 6.0, 6.0), "B": _titre(12.0, 5.0, 5.0),
             "C": _titre(14.0, 4.0, 4.0)}
    sp_axes = {"n_secteur_min": 8}
    pool_b = dict(sains, D=_titre(10.0, 1.0, None))    # option (b), appliquee
    pool_a = dict(sains, D=_titre(10.0, 1.0, 1.0))     # option (a), refusee
    _, _, axes_b = bassins_et_axes(pool_b, sp_axes)
    _, _, axes_a = bassins_et_axes(pool_a, sp_axes)
    dec_b = {t: axes_b(t, v)[0] for t, v in pool_b.items()}
    dec_a = {t: axes_a(t, v)[0] for t, v in pool_a.items()}

    verifie(dec_b["D"] == 100 and dec_a["D"] == 62,
            "un titre drapeaute n'a plus de rang de rendement : sa decote vient du "
            f"seul axe benefice/prix (P{dec_b['D']}) au lieu d'etre tiree vers le bas "
            f"par un rendement facial faux (P{dec_a['D']} sous l'option refusee)")
    verifie(dec_b["B"] == 58 and dec_b["C"] == 29,
            f"les titres sains gardent leurs DEUX axes (B P{dec_b['B']}, C P{dec_b['C']})")
    verifie(dec_b["B"] < dec_a["B"] and dec_b["C"] < dec_a["C"],
            "effet de bassin assume et surveille : retirer un rendement BAS du bassin "
            f"deplace les titres sains vers le cher (B P{dec_a['B']} -> P{dec_b['B']}, "
            f"C P{dec_a['C']} -> P{dec_b['C']}) sans qu'aucune de leurs donnees change")
    verifie(dec_b["A"] == dec_a["A"] == 100,
            "le titre le moins cher et le mieux remunerateur reste a P100 dans les deux "
            "lectures : l'effet de bassin ne touche que les rangs intermediaires")

    # Le meme dy_axe est bien ce que profils.json publie sous "dy_recurrent",
    # donc la case vide de l'axe et celle de la fiche sont la MEME case.
    incoherents = sorted(t for t, v in pj.items()
                         if porte(t) and (v.get("dy_recurrent") is not None
                                          or v.get("prime_rendement") is not None))
    verifie(not incoherents,
            "tous les titres drapeautes ont la case vide sur l'axe de decote, la prime "
            "et le rendement recurrent"
            + ("" if not incoherents else " — INCOHERENTS : " + ", ".join(incoherents)))


# Plancher de la section 23 : nombre de dates de paiement ISO en base. Il ne peut
# que monter — la collecte ajoute des dividendes, elle n'en retire pas. Mesure du
# 30/09/2026 (cycle 10), apres migration : 308 ISO et 3 nulles sur 311 lignes.
DATES_ISO_MIN = 308


def _extraire_fonction(chemin, nom, besoins=()):
    """Compile UNE fonction d'un module, sans importer le module.

    Sert a tester une fonction qui vit dans un fichier dont les imports de tete
    tirent une dependance absente de requirements.txt (ici pdfplumber, via
    collecte_boc_quotidien -> extracteur_boc). Seuls le corps de la fonction et
    les affectations de tete nommees dans `besoins` sont compiles ; tout le reste
    du fichier, imports compris, est ignore. `re` est fourni parce que les
    normaliseurs de date s'en servent.
    """
    import ast as _ast
    import re as _re
    arbre = _ast.parse(chemin.read_text(encoding="utf-8"))
    retenus = []
    for noeud in arbre.body:
        if isinstance(noeud, _ast.FunctionDef) and noeud.name == nom:
            retenus.append(noeud)
        elif isinstance(noeud, _ast.Assign) and any(
                isinstance(c, _ast.Name) and c.id in besoins for c in noeud.targets):
            retenus.append(noeud)
    if not any(isinstance(n, _ast.FunctionDef) for n in retenus):
        raise AssertionError("fonction %s absente de %s" % (nom, chemin))
    espace = {"re": _re}
    exec(compile(_ast.Module(body=retenus, type_ignores=[]), str(chemin), "exec"),
         espace)
    return espace[nom]


def test_dates_dividendes_iso():
    """La colonne date_paiement est ISO, et le tri chronologique redevient vrai.

    POURQUOI CETTE SECTION EXISTE (chantier C10, 30/09/2026). La colonne
    melangeait 296 dates en francais abrege ('24-juil.-17') et 12 en ISO, parce
    que charger_dividendes_exercice.py inserait la chaine brute du CSV. Ce
    melange n'etait pas cosmetique, et deux de ses trois effets etaient ACTIFS,
    mesures sur la base du jour avant correction :

      1. moteur/scoring.py::dividendes() fait ORDER BY date_paiement DESC. Sur du
         francais abrege l'ordre est ALPHABETIQUE : sur les 49 tickers portant au
         moins un dividende date, le premier rendu n'etait PAS le versement le
         plus recent pour 34 d'entre eux ;
      2. le meme fichier fait int(dernier_div["date_paiement"][:4]), soit
         int("24-j") sur du francais : ValueError, avalee par un except. Tout le
         bloc « regularite du dividende » (bonus 20, malus 20, alerte
         « dernier dividende verse il y a N ans ») etait silencieusement saute
         sur 45 des 49 tickers ;
      3. collecte_boc_quotidien.py normalise en ISO puis deduplique par egalite
         de chaine : une date ISO ne s'egalera jamais a la forme francaise du
         meme jour, donc le BOC aurait un jour reinsere en double un dividende
         deja charge par la Piste D. Celui-la etait LATENT (0 paire (ticker,
         jour) portant les deux formats), et c'est pour qu'il le reste que le
         quatrieme controle ci-dessous existe.

    Ce que la section verrouille : la conversion elle-meme (liste blanche de
    mois, refus des formes approchantes), l'absence de toute date non ISO en
    base, la verite du tri, la faisabilite de l'extraction d'annee, et la
    reconnaissance par le dedoublonneur du BOC.
    """
    print("\n=== 23. Dates de paiement des dividendes en ISO (bloquant) ===")
    sys.path.insert(0, str(RACINE / "collecte"))
    from dates_dividendes import CAS, est_iso, vers_iso

    # --- 1. La conversion : refuser plutot que deviner ----------------------
    echecs = [(e, a, vers_iso(e)) for e, a in CAS if vers_iso(e) != a]
    verifie(not echecs,
            "les %d cas de collecte/dates_dividendes.py passent (formes reelles du "
            "depot, et refus des pieges)" % len(CAS)
            + ("" if not echecs else " — ECHECS : %r" % echecs[:5]))
    # Le piege fondateur : un prefixe de trois lettres aurait accepte celui-ci.
    verifie(vers_iso("24-jullet-17") is None,
            "un mois francais mal orthographie ('jullet') echoue au lieu d'etre "
            "devine par prefixe")
    verifie(vers_iso("31-fevr.-20") is None and vers_iso("2025-02-31") is None,
            "un jour qui n'existe pas echoue, en francais comme en ISO")
    verifie(vers_iso("30-sept.-97") is None,
            "l'annee sur deux chiffres est levee en 20AA, et 2097 est refusee "
            "comme hors fenetre de plausibilite")

    if not DB.exists():
        verifie(False, "base absente", bloquant=False)
        return
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- 2. Aucune date non ISO en base ------------------------------------
    lignes = cur.execute(
        "SELECT ticker, montant_net, date_paiement FROM dividendes").fetchall()
    fautives = sorted({(r["ticker"], r["date_paiement"]) for r in lignes
                       if r["date_paiement"] and not est_iso(r["date_paiement"])})
    verifie(not fautives,
            "les %d lignes de dividendes portent une date ISO ou une case vide, "
            "aucune autre forme" % len(lignes)
            + ("" if not fautives else " — FAUTIVES : %r" % fautives[:8]))
    n_iso = sum(1 for r in lignes if est_iso(r["date_paiement"]))
    verifie(n_iso >= DATES_ISO_MIN,
            "%d date(s) ISO en base (plancher %d, qui ne peut que monter)"
            % (n_iso, DATES_ISO_MIN))

    # --- 3. Le tri SQL redit la verite, et l'annee s'extrait ---------------
    tickers = [r[0] for r in cur.execute(
        "SELECT DISTINCT ticker FROM dividendes ORDER BY 1")]
    mal_triees, annee_illisible = [], []
    for t in tickers:
        rs = cur.execute("SELECT date_paiement FROM dividendes WHERE ticker=? "
                         "ORDER BY date_paiement DESC", (t,)).fetchall()
        premier = rs[0]["date_paiement"]
        dates = [r["date_paiement"] for r in rs if r["date_paiement"]]
        if dates:
            vrai = max(dates, key=lambda d: vers_iso(d) or "")
            if premier != vrai:
                mal_triees.append("%s : %s au lieu de %s" % (t, premier, vrai))
            try:
                int(str(premier)[:4])
            except (ValueError, TypeError):
                annee_illisible.append("%s : %r" % (t, premier))
    verifie(not mal_triees,
            "ORDER BY date_paiement DESC rend le versement le plus recent sur les "
            "%d tickers a dividende (34 etaient faux avant C10)" % len(tickers)
            + ("" if not mal_triees else " — FAUX : " + " ; ".join(mal_triees[:6])))
    verifie(not annee_illisible,
            "int(date_paiement[:4]) reussit sur les %d tickers, donc le bloc "
            "« regularite du dividende » de scoring.py s'execute reellement "
            "(il etait saute sur 45 d'entre eux)" % len(tickers)
            + ("" if not annee_illisible else " — ILLISIBLES : " + ", ".join(annee_illisible[:6])))

    # --- 4. Le dedoublonneur du BOC retrouve bien les lignes existantes ----
    # C'etait le defaut LATENT de C10. On rejoue exactement sa requete, avec la
    # date telle que le BOC l'ecrit (francais abrege), sur des dividendes
    # reellement en base. Sans la migration, aucune de ces recherches n'aboutit.
    #
    # La fonction du BOC est extraite par AST, PAS importee. Pourquoi : un
    # `from collecte_boc_quotidien import date_dividende_vers_iso` tire
    # extracteur_boc, donc `import pdfplumber`, qui n'est PAS dans
    # requirements.txt. La premiere version de cette section l'importait et a
    # fait tomber P4 le 30/09/2026 (ModuleNotFoundError), alors qu'elle passait
    # dans le bac a sable ou pdfplumber se trouve preinstalle -- une barriere
    # verte par accident d'environnement. Les tests de donnees ne doivent
    # dependre que de ce que requirements.txt installe.
    date_dividende_vers_iso = _extraire_fonction(
        RACINE / "collecte" / "collecte_boc_quotidien.py",
        "date_dividende_vers_iso", besoins=("MOIS_FR",))
    MOIS_INV = {1: "janv.", 2: "fevr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
                7: "juil.", 8: "aout", 9: "sept.", 10: "oct.", 11: "nov.", 12: "dec."}
    temoins = [r for r in lignes if est_iso(r["date_paiement"])
               and r["montant_net"] is not None][:40]
    introuvables = []
    for r in temoins:
        a, m, j = (int(x) for x in r["date_paiement"].split("-"))
        forme_boc = "%d-%s-%02d" % (j, MOIS_INV[m], a % 100)
        iso_boc = date_dividende_vers_iso(forme_boc)
        trouve = cur.execute(
            "SELECT 1 FROM dividendes WHERE ticker=? AND montant_net=? "
            "AND date_paiement=?", (r["ticker"], r["montant_net"], iso_boc)).fetchone()
        if iso_boc != r["date_paiement"] or not trouve:
            introuvables.append("%s %s -> %r (BOC : %r)"
                                % (r["ticker"], r["date_paiement"], iso_boc, forme_boc))
    verifie(temoins and not introuvables,
            "la deduplication de collecte_boc_quotidien.py retrouve les %d "
            "dividendes temoins quand le BOC les reobserve en francais abrege "
            "(elle ne les retrouvait sur aucun avant C10)" % len(temoins)
            + ("" if not introuvables else " — INTROUVABLES : " + " ; ".join(introuvables[:5])))
    conn.close()

    # --- 5. Les chargeurs normalisent bien a l'entree ----------------------
    for chemin, quoi in (("collecte/charger_dividendes_exercice.py", "Piste D"),
                         ("moteur/peupler.py", "donnees/base"),
                         ("collecte/historiser_dividendes_exercice.py", "la sortie de l'historisation")):
        code = (RACINE / chemin).read_text(encoding="utf-8")
        verifie("dates_dividendes" in code and "vers_iso" in code,
                "%s normalise les dates a l'entree (%s)" % (chemin, quoi))
    mig = RACINE / "outils" / "migration_dates_dividendes_iso.py"
    verifie(mig.exists(), "le proces-verbal executable de la migration est dans outils/")

    # --- 6. Le dedoublonneur du BOC n'a pas change de forme ----------------
    boc = (RACINE / "collecte" / "collecte_boc_quotidien.py").read_text(encoding="utf-8")
    verifie("date_paiement = date_dividende_vers_iso(date_brute)" in boc,
            "collecte_boc_quotidien.py convertit toujours en ISO avant de chercher "
            "le doublon (le controle 4 ne prouve rien s'il cesse de le faire)")
    verifie("WHERE ticker=? AND montant_net=? AND date_paiement=?" in boc,
            "sa recherche de doublon est toujours l'egalite sur (ticker, montant, date)")
    # Cette section ne doit dependre que de ce que requirements.txt installe :
    # P4 est tombe le 30/09/2026 parce qu'elle importait collecte_boc_quotidien,
    # donc pdfplumber, absent de requirements.txt et present par hasard dans le
    # bac a sable. La fonction est desormais extraite par AST.
    # Le controle porte sur les INSTRUCTIONS, pas sur le texte du fichier : la
    # premiere version cherchait la sous-chaine et se declenchait sur le
    # commentaire ci-dessus, qui la contient.
    ici = (ICI / "tester_donnees.py").read_text(encoding="utf-8")
    importe = [l.strip() for l in ici.splitlines()
               if l.strip().startswith(("from collecte_boc_quotidien import",
                                        "import collecte_boc_quotidien"))]
    verifie(not importe,
            "tester_donnees.py n'importe pas collecte_boc_quotidien : sa chaine "
            "d'imports tire pdfplumber, qui n'est pas dans requirements.txt"
            + ("" if not importe else " — TROUVE : %r" % importe))


# Plancher releve le 01/10/2026 (cycle 12) : 44 titres sur 44 portant un
# rendement BOC ont leur dividende de reference identifie en base. Il etait de
# 31 avant le chargement de collecte/dividendes_boc.csv. Il ne doit que monter :
# une baisse signifie que le pont a ete debranche ou que la collecte recule.
# ----------------------------------------------------------------------
# 28. LE PER GLISSANT (TTM) — sa regle, et ses refus (bloquant)
# ----------------------------------------------------------------------
# Plancher pose le 03/10/2026 (cycle 16, C26) : nombre de titres dont le PER
# glissant se calcule. Il vaut 1 — BOAC, seul titre dont les publications
# intermediaires, les deux exercices annuels encadrants et les paliers du BPA
# implicite soient tous les trois en base. Il ne doit que MONTER : une baisse
# signifie qu'une collecte intermediaire a disparu ou qu'un refus s'est elargi.
# Le cycle qui versera des lignes dans resultats_intermediaires l'eleve ici.
TITRES_PER_GLISSANT_MIN = 1


def test_per_glissant():
    """Le PER sur douze mois glissants ne se calcule que sur une reference verifiee.

    POURQUOI CETTE SECTION EXISTE (02/10/2026, demande de Claudia : afficher un
    PER glissant pour refleter la situation financiere la plus actuelle).

    LA FORMULE EST UN RAPPORT : PER_TTM = PER_affiche x (RN_annuel / RN_TTM), ou
    RN_TTM = RN du dernier exercice clos + cumul des periodes intermediaires de
    l'exercice en cours - cumul des MEMES periodes un an plus tot. Le nombre
    d'actions s'annule, donc on n'a pas a l'estimer.

    MAIS L'EGALITE N'EST VRAIE QUE SI LE BULLETIN DIVISE PAR LE MEME RN_annuel.
    C'est precisement l'erreur qui a coute le PER normalise (C23) : une formule
    juste posee sur un denominateur non verifie. La verification se fait sans
    estimer le nombre d'actions : le BPA implicite du bulletin (cours / PER)
    forme des PALIERS, et le rapport des deux derniers paliers doit egaler le
    rapport de nos deux derniers resultats annuels. Mesure du 02/10/2026 sur
    BOAC : paliers 801,08 -> 888,52 soit x1,1091, contre RN 2025/2024 =
    35540/32044 = x1,1091. Ecart 0,00 %.

    CE QUE LA REGLE REFUSE, et c'est le coeur de ces controles : une periode sans
    comparatif N-1, deux familles de periodes sur le meme exercice (S1 recouvre
    T1+T2), un cumul qui ne part pas du debut de l'exercice, un exercice
    intermediaire qui ne suit pas l'exercice clos, un resultat glissant negatif,
    et une reference que les paliers ne confirment pas. Chaque refus porte son
    motif, expose dans profils.json et sur la fiche : une case vide sans
    explication ne vaut rien.

    CE QUE LA BASE PERMET AUJOURD'HUI, dit franchement : resultats_intermediaires
    porte 3 lignes pour 2 titres. BOAC donne 12,93 -> 12,89 (+0,3 % de resultat
    glissant). SGBC est refuse parce que nos exercices 2022 a 2024 manquent, donc
    le rapport des paliers n'a rien a confronter. Le PER glissant vaut donc pour
    1 titre sur 47, et ce qui le limite est la COLLECTE des publications
    intermediaires, pas le calcul.

    LE PLANCHER, pose le 03/10/2026 (cycle 16, C26). Le critere de terminaison de
    C26 demande que le nombre de titres a PER glissant calculable soit fige par un
    test qui ne peut que MONTER. Sans cela, une collecte intermediaire qui
    disparait ou un refus qui s'elargit se verrait a l'oeil ou pas du tout : la
    mesure a 1 titre n'etait ecrite nulle part qu'en prose. Quand le plancher
    monte, c'est au cycle qui verse les lignes de l'elever ici.

    NUMERO : cette section etait la DEUXIEME a porter le 27 -- la confrontation
    du bulletin a la page Volumes / Valeurs (C25) portait le meme numero le meme
    jour. CHANTIERS.md designe la section 27 pour le registre TICKERS_HORS_BASE,
    qui appartient a celle de C25 ; c'est donc celle-ci qui est renumerotee 28.
    """
    print("\n=== 28. PER glissant sur douze mois (bloquant) ===")
    import json
    sys.path.insert(0, str(ICI))
    from profils import benefice_glissant, per_glissant

    # --- La regle, sur une base jetable, avec ses contre-exemples -------------
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE etats_financiers (ticker TEXT, exercice INT, "
                 "resultat_net REAL)")
    conn.execute("CREATE TABLE resultats_intermediaires (ticker TEXT, exercice INT, "
                 "periode TEXT, resultat_net REAL, resultat_net_n1 REAL)")

    def _cas(t, annuels, inters):
        conn.executemany("INSERT INTO etats_financiers VALUES (?,?,?)",
                         [(t, e, rn) for e, rn in annuels])
        conn.executemany("INSERT INTO resultats_intermediaires VALUES (?,?,?,?,?)",
                         [(t, e, p, rn, n1) for e, p, rn, n1 in inters])

    # A. deux trimestres consecutifs : 1000 + (300-200) + (350-250) = 1200
    _cas("A", [(2025, 1000.0)], [(2026, "T1", 300.0, 200.0), (2026, "T2", 350.0, 250.0)])
    # B. T2 sans T1 : le cumul sauterait un trimestre
    _cas("B", [(2025, 1000.0)], [(2026, "T2", 350.0, 250.0)])
    # C. T1 et S1 ensemble : S1 recouvre T1, le cumul doublerait des mois
    _cas("C", [(2025, 1000.0)], [(2026, "T1", 300.0, 200.0), (2026, "S1", 650.0, 450.0)])
    # D. comparatif N-1 absent : la soustraction serait inventee
    _cas("D", [(2025, 1000.0)], [(2026, "T1", 300.0, None)])
    # E. l'intermediaire ne suit pas l'exercice clos (2024 puis 2026)
    _cas("E", [(2024, 1000.0)], [(2026, "T1", 300.0, 200.0)])
    # F. resultat glissant negatif
    _cas("F", [(2025, 100.0)], [(2026, "T1", 10.0, 500.0)])
    cur_j = conn.cursor()

    rn, rn_an, ex, per, motif = benefice_glissant(cur_j, "A")
    verifie(motif is None and rn == 1200.0 and rn_an == 1000.0 and ex == 2025
            and per == "T1+T2 2026",
            "deux trimestres consecutifs se cumulent : 1000 + (300-200) + (350-250) "
            f"= 1200 (obtenu : {rn}, periodes {per!r})")
    for nom, attendu in (("B", "ne part pas du debut"), ("C", "deux familles"),
                         ("D", "sans comparatif N-1"), ("E", "ne se suivent pas"),
                         ("F", "negatif ou nul")):
        rn_x, _a, _b, _c, motif_x = benefice_glissant(cur_j, nom)
        verifie(rn_x is None and motif_x is not None and attendu in motif_x,
                f"cas {nom} refuse avec son motif ({attendu})"
                + ("" if rn_x is None else f" — CALCULE QUAND MEME : {rn_x}")
                + ("" if motif_x and attendu in (motif_x or "") else
                   f" — motif obtenu : {motif_x!r}"))

    # Sans serie de cours, la reference du bulletin ne peut pas etre verifiee :
    # le PER glissant doit etre refuse meme quand le cumul, lui, est bon.
    conn.execute("CREATE TABLE cours_quotidien_boc (ticker TEXT, date_bulletin TEXT, "
                 "cours REAL, per REAL, rendement REAL)")
    conn.execute("CREATE TABLE cours_mensuels (ticker TEXT, fin_mois TEXT, cours REAL, "
                 "per REAL, rendement REAL)")
    valeur, _d, motif_v = per_glissant(cur_j, "A", 10.0)
    verifie(valeur is None and motif_v is not None,
            "sans paliers de BPA implicite, le PER glissant est refuse meme quand le "
            f"cumul est bon — c'est la garde que C23 avait manquee (motif : {motif_v!r})")
    conn.close()

    # --- La propriete sur la base du jour -------------------------------------
    f = RACINE / "collecte" / "profils.json"
    if not f.exists() or not DB.exists():
        verifie(False, "profils.json ou brvm.db absent", bloquant=False)
        return
    profils = json.loads(f.read_text(encoding="utf-8"))
    calcules = {t: v for t, v in profils.items() if v.get("per_ttm") is not None}
    verifie(len(calcules) >= TITRES_PER_GLISSANT_MIN,
            "au moins %d titre(s) portent un PER glissant calculable — plancher qui "
            "ne peut que monter (obtenu : %d%s)"
            % (TITRES_PER_GLISSANT_MIN, len(calcules),
               ", " + ", ".join(sorted(calcules)) if calcules else ""))
    sans_detail = sorted(t for t, v in calcules.items() if not v.get("ttm_detail"))
    verifie(not sans_detail,
            f"les {len(calcules)} PER glissants publies portent leur detail de calcul"
            + ("" if not sans_detail else f" — MUETS : {sans_detail}"))
    sans_motif = sorted(t for t, v in profils.items()
                        if v.get("per_ttm") is None and not v.get("ttm_motif"))
    verifie(not sans_motif,
            "chaque titre SANS PER glissant porte le motif du refus"
            + ("" if not sans_motif else f" — MUETS : {sans_motif}"))

    # Un PER glissant qui s'eloignerait enormement du PER publie signalerait que
    # la reference a change sans que la verification l'ait vu. Alerte, pas blocage :
    # un resultat intermediaire peut legitimement s'effondrer.
    aberrants = sorted(f"{t} {v['per']:.1f} -> {v['per_ttm']:.1f}"
                       for t, v in calcules.items()
                       if v.get("per") and not 0.2 <= v["per_ttm"] / v["per"] <= 5)
    verifie(not aberrants,
            "aucun PER glissant ne s'ecarte du PER publie d'un facteur superieur a 5"
            + ("" if not aberrants else f" — A VERIFIER : {aberrants}"),
            bloquant=False)

    code = APP.read_text(encoding="utf-8")
    verifie("per_ttm" in code and "PER glissant" in code,
            "app.py affiche le PER glissant (fiche titre et onglet Explorer)")

    # --- PER D'ANALYSE (02/10/2026, decision de Claudia) -----------------------
    # Les analyses lisent le glissant quand il existe, le BOC a defaut ; "per"
    # reste le PER PUBLIE. Une inversion des deux passerait inapercue a l'oeil :
    # le glissant est aujourd'hui a 0,3 % du BOC sur le seul titre qui en a un.
    mal_choisis = sorted(
        t for t, v in profils.items()
        if v.get("per_analyse") != (v.get("per_ttm") if v.get("per_ttm") is not None
                                    else (round(v["per"], 2) if v.get("per") is not None
                                          else None)))
    verifie(not mal_choisis,
            "per_analyse vaut le PER glissant quand il existe, le PER du BOC sinon"
            + ("" if not mal_choisis else f" — ECART : {mal_choisis}"))
    sources_fausses = sorted(
        t for t, v in profils.items()
        if v.get("per_source") != ("GLISSANT" if v.get("per_ttm") is not None
                                   else ("BOC" if v.get("per") else None)))
    verifie(not sources_fausses,
            "per_source dit lequel des deux a ete lu"
            + ("" if not sources_fausses else f" — ECART : {sources_fausses}"))
    # Le payout IMPLICITE reste une identite sur un exercice : rendement x PER du
    # BOC, jamais x PER glissant. Contre-exemple pose : s'il lisait le glissant,
    # l'egalite ci-dessous tomberait sur tout titre dont le glissant differe.
    payout_glisse = sorted(
        t for t, v in profils.items()
        if str(v.get("payout_source", "")).startswith("IMPLICITE")
        and v.get("per") and v.get("dy") is not None and v.get("payout") is not None
        and abs(v["payout"] - v["dy"] / 100 * v["per"]) > 1e-6)
    verifie(not payout_glisse,
            "le payout implicite est calcule sur le PER du BOC, pas sur le glissant"
            + ("" if not payout_glisse else f" — ECART : {payout_glisse}"))
    src = (RACINE / "moteur" / "profils.py").read_text(encoding="utf-8")
    verifie("dy * per_boc" in src and "dy * per," not in src,
            "profils.py : le payout implicite multiplie par per_boc (ancrage du source)")


REFERENCES_IDENTIFIEES_MIN = 44


# ----------------------------------------------------------------------
# 24. LE DIVIDENDE DE REFERENCE DU BOC EST EN BASE (bloquant)
# ----------------------------------------------------------------------
def test_reference_dividende_boc():
    """Le dividende par lequel le BOC divise doit etre dans la table dividendes.

    POURQUOI CETTE SECTION EXISTE (chantier C17, 01/10/2026). Le rendement publie
    par le bulletin est un rapport : dernier dividende par action sur cours. En le
    reconstruisant (rendement x cours) et en le confrontant au versement le plus
    recent de la table, 13 titres sur 44 ne concordaient pas. C17 appelait cela
    une « lacune de collecte ». Mesure de ce cycle : il n'y en avait aucune.

    Les 13 references etaient dans collecte/dividendes_boc.csv -- fichier
    COMMITE, ecrit par collecte_boc_quotidien.py depuis la colonne « Dernier
    dividende paye » du bulletin, collectees entre le 28/07 et le 30/09/2026 --
    et AUCUN chargeur de la chaine ne lisait ce fichier. collecte_boc_quotidien.py
    les inserait dans une base jetee a chaque reconstruction. La donnee etait
    collectee, commitee, et perdue a l'entree.

    CE QUE CELA RENDAIT INERTE, et c'est le vrai cout. La regle 1 de
    diagnostic_distribution() (chantier C1, drapeau DISTRIBUTION_NON_RECURRENTE)
    n'identifie son dividende de reference que par coincidence entre l'implicite
    du BOC et le versement le plus RECENT de la table. Sans coincidence, elle ne
    conclut pas -- a juste titre. Elle etait donc silencieusement inapplicable sur
    13 des 44 titres, soit 30 % du marche, sans qu'aucun controle ne le dise.
    Apres chargement : 44 / 44, et les 16 lignes chargees concordent avec
    l'implicite entre 0,01 % et 0,16 %.

    AUCUN VERDICT DU JOUR N'EN DEPEND, et il faut le dire ainsi : collecte/
    profils.json est identique au champ pres avant et apres, 0 titre d'ecart sur
    47 -- les 16 versements charges sont tous recents (2026-07 a 2026-09), donc
    aucun n'est perime, et aucun ne depasse le plus fort des versements
    precedents. Le defaut etait LATENT, comme C10 et C19 : arme, en attente.

    SEVERITES. Bloquant : que le pont tourne, et que la regle de completion d'un
    montant NULL n'ait pas ete relachee -- ce sont des proprietes du CODE. En
    alerte : le plancher de references identifiees, parce qu'une baisse peut venir
    du BOC, et que ce fichier ne bloque pas un commit pour un defaut de source.
    """
    print("\n=== 24. Le dividende de reference du BOC est en base (bloquant) ===")
    code = (RACINE / "collecte" / "charger_dividendes_boc.py")
    verifie(code.exists(),
            "collecte/charger_dividendes_boc.py existe (la section 17 verrouille, "
            "elle, sa presence dans app.py, pages.yml et les workflows qui "
            "recalculent profils.json)")
    if not code.exists():
        return
    src = code.read_text(encoding="utf-8")

    # Le pont doit lire LE fichier, pas un autre.
    verifie('"dividendes_boc.csv"' in src,
            "charger_dividendes_boc.py lit collecte/dividendes_boc.csv")

    # Les deux gardes qui font la difference entre completer et ecraser. Sans la
    # premiere, un montant valide est remplace ; sans la seconde, un montant NULL
    # est rempli par un versement d'une AUTRE date -- NSBC 2025 porte 2026-06-30
    # quand le BOC dit 2026-08-04, et doit rester vide.
    verifie("montant_base is None and date_base == date_p" in src,
            "un montant NULL n'est complete que si la date_paiement est identique "
            "des deux cotes (la seconde moitie de la preuve a deux cotes)")
    verifie("UPDATE dividendes SET montant_net" in src
            and src.count("UPDATE dividendes SET montant_net") == 1,
            "le pont ne porte qu'UN seul UPDATE de montant, celui de la completion")

    if not DB.exists():
        verifie(False, "brvm.db absent : le reste de la section ne prouverait rien",
                bloquant=False)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Le pont a-t-il REELLEMENT tourne sur cette base ? Un controle qui se
    # contente de lire le source passerait sur une base construite sans lui :
    # c'est le faux vert que la chasse du cycle 11 a trouve deux fois.
    charges = cur.execute(
        "SELECT COUNT(*) FROM dividendes WHERE source LIKE '%dividendes_boc.csv%'"
    ).fetchone()[0]
    verifie(charges > 0,
            f"{charges} ligne(s) de dividendes portent collecte/dividendes_boc.csv "
            f"pour source : le pont a tourne sur cette base"
            + ("" if charges else " — CHAINE AMPUTEE : la base a ete construite "
                                  "sans charger_dividendes_boc.py"))

    # Un montant NULL que le BOC renseigne pour le MEME exercice et le MEME jour
    # ne doit plus exister : c'est exactement ce que la completion traite.
    import csv as _csv
    chemin_csv = RACINE / "collecte" / "dividendes_boc.csv"
    boc = {}
    if chemin_csv.exists():
        with chemin_csv.open(encoding="utf-8", newline="") as f:
            for r in _csv.DictReader(f):
                if r.get("ticker") and r.get("date_paiement") and r.get("montant_net"):
                    boc[(r["ticker"], r["date_paiement"])] = r["montant_net"]
    # peupler.py doit refuser de REINSERER le marqueur vide a cote de la ligne
    # completee : sa clef naturelle inclut montant_net, donc une ligne vide et sa
    # version completee sont deux lignes differentes pour elle. Sans cette garde,
    # le controle suivant tombait des que la section 16 relancait peupler.py --
    # c'est ainsi que le defaut a ete trouve, le 01/10/2026.
    peup = (ICI / "peupler.py").read_text(encoding="utf-8")
    verifie("AND exercice_couvert IS ? AND montant_net IS NOT NULL" in peup,
            "peupler.py ne reinsere pas un marqueur a montant vide quand le montant "
            "est deja en base pour le meme (ticker, exercice, jour)")

    masques = [f"{t} ex.{e} le {d}" for t, e, d in cur.execute(
        "SELECT ticker, exercice_couvert, date_paiement FROM dividendes "
        "WHERE montant_net IS NULL AND date_paiement IS NOT NULL")
        if (t, d) in boc]
    verifie(not masques,
            "aucun montant NULL ne masque un montant que le BOC donne pour le meme "
            "jour"
            + ("" if not masques else " — MASQUES : " + ", ".join(masques)))

    # --- Le plancher de C17 : combien de references sont identifiees ? --------
    # La tolerance est lue dans config/seuils.yaml, pas recopiee ici : ce controle
    # doit mesurer ce que le moteur applique, et suivre Claudia si elle la change.
    import yaml as _yaml
    _cfg = _yaml.safe_load((RACINE / "config" / "seuils.yaml").read_text(
        encoding="utf-8")) or {}
    tol = (_cfg.get("profils") or {}).get("distribution_tolerance_implicite", 0.10)
    derniers = cur.execute(
        "SELECT q.ticker, q.cours, q.rendement FROM cours_quotidien_boc q JOIN "
        "(SELECT ticker, MAX(date_bulletin) d FROM cours_quotidien_boc "
        " WHERE rendement IS NOT NULL AND rendement > 0 AND cours IS NOT NULL "
        " GROUP BY ticker) m ON m.ticker = q.ticker AND m.d = q.date_bulletin"
    ).fetchall()
    identifiees, echappent = 0, []
    for ticker, cours, rendement in derniers:
        implicite = cours * rendement
        derniere = cur.execute(
            "SELECT montant_net FROM dividendes WHERE ticker=? AND montant_net > 0 "
            "AND date_paiement IS NOT NULL ORDER BY date_paiement DESC LIMIT 1",
            (ticker,)).fetchone()
        if not derniere:
            echappent.append(f"{ticker} (aucun versement date)")
            continue
        ecart = abs(derniere[0] - implicite) / implicite
        if ecart <= tol:
            identifiees += 1
        else:
            echappent.append(f"{ticker} ({ecart * 100:.0f} %)")

    verifie(len(derniers) >= 40,
            f"la mesure porte sur une population reelle ({len(derniers)} titres a "
            f"rendement BOC publie)")
    verifie(identifiees >= REFERENCES_IDENTIFIEES_MIN,
            f"{identifiees} / {len(derniers)} titres ont leur dividende de reference "
            f"identifie (plancher {REFERENCES_IDENTIFIEES_MIN}, tolerance "
            f"{tol * 100:.0f} %) — la regle 1 de C1 ne s'applique qu'a ceux-la"
            + ("" if identifiees >= REFERENCES_IDENTIFIEES_MIN
               else " — EN BAISSE, la reference echappe sur : "
                    + ", ".join(sorted(echappent))),
            bloquant=False)

    # --- Le registre des refus du pont (chantier C22, 05/10/2026) -----------
    # C22 exige qu'aucun refus du pont ne reste sans motif ecrit, et qu'aucun
    # refus NOUVEAU n'apparaisse sans etre inscrit. Le controle ne fait pas
    # confiance a la sortie du pont : il RECALCULE l'ensemble des refus depuis
    # collecte/dividendes_boc.csv et la base, avec la meme logique que le pont,
    # puis le compare au registre dans les DEUX sens.
    _controle_registre_refus(cur, boc_brut=chemin_csv)
    conn.close()


# Le registre est un fichier de donnees, pas du code : il vit dans collecte/
# et la section le relit. Une ligne y porte sa decision, son motif, sa preuve
# et le chantier dont elle releve.
REGISTRE_REFUS = "collecte/arbitrages_pont_boc.csv"

# Decisions admises. Une decision inconnue est un ECHEC : elle signifie qu'un
# cycle a invente une categorie sans le dire.
DECISIONS_REFUS = {
    "REFUS_DEFINITIF",   # la base fait foi, definitivement (marqueur humain)
    "REFUS_SIGNALE",     # la base n'est pas ecrasee, mais le cas part a Claudia
    "REFUS_MOTIVE",      # la base fait foi, motif ecrit, renvoi a un chantier
    "TRANCHE_RENVOI",    # valeur tranchee, application renvoyee a un chantier
    "TRANCHE_APPLIQUE",  # valeur tranchee ET appliquee : le refus doit disparaitre
}


def _refus_recalcules(cur, boc_brut):
    """Les refus que le pont emet, recalcules independamment de sa sortie.

    Meme logique que charger_dividendes_boc.py : triplet exact deja present ->
    rien ; couple (ticker, exercice) absent -> insertion ; montant NULL a date
    identique -> completion ; sinon REFUS.
    """
    import csv as _csv
    sys.path.insert(0, str(RACINE / "collecte"))
    from dates_dividendes import est_iso  # noqa: E402
    from historiser_dividendes_exercice import deduire_exercice  # noqa: E402

    refus = set()
    if not Path(boc_brut).exists():
        return refus
    with Path(boc_brut).open(encoding="utf-8", newline="") as f:
        for r in _csv.DictReader(f):
            ticker = (r.get("ticker") or "").strip()
            brut = (r.get("montant_net") or "").strip()
            date_p = (r.get("date_paiement") or "").strip()
            if not ticker or not brut or not date_p or not est_iso(date_p):
                continue
            try:
                montant = float(brut)
            except ValueError:
                continue
            exercice, _c, _n = deduire_exercice(int(date_p[:4]), int(date_p[5:7]))
            if exercice is None:
                continue
            if cur.execute("SELECT 1 FROM dividendes WHERE ticker=? AND "
                           "montant_net=? AND date_paiement=?",
                           (ticker, montant, date_p)).fetchone():
                continue
            presentes = cur.execute(
                "SELECT montant_net, date_paiement FROM dividendes "
                "WHERE ticker=? AND exercice_couvert=?",
                (ticker, exercice)).fetchall()
            if not presentes:
                continue
            if any(m is None and d == date_p for m, d in presentes):
                continue
            refus.add((ticker, exercice))
    return refus


def _controle_registre_refus(cur, boc_brut):
    """Le registre de C22 couvre exactement les refus que le pont emet."""
    import csv as _csv
    chemin = RACINE / REGISTRE_REFUS
    if not verifie(chemin.exists(),
                   f"{REGISTRE_REFUS} existe : les refus du pont ont un registre "
                   f"motive (chantier C22)"):
        return
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = list(_csv.DictReader(f))

    # Forme : chaque ligne porte une decision connue, un motif, un chantier.
    inconnues = sorted({l["decision"] for l in lignes} - DECISIONS_REFUS)
    verifie(not inconnues,
            "chaque ligne du registre porte une decision d'une categorie connue"
            + ("" if not inconnues else f" — INCONNUES : {inconnues}"))
    muettes = [f"{l['ticker']} ex.{l['exercice']}" for l in lignes
               if not l["motif"].strip() or not l["chantier"].strip()
               or not l["valeur_retenue"].strip()]
    verifie(not muettes,
            f"les {len(lignes)} lignes du registre portent toutes une valeur "
            f"retenue, un motif et un chantier de renvoi"
            + ("" if not muettes else " — MUETTES : " + ", ".join(muettes)))

    doublons = len(lignes) - len({(l["ticker"], l["exercice"]) for l in lignes})
    verifie(not doublons,
            f"le registre ne porte aucun couple (ticker, exercice) en double "
            f"({doublons} doublon(s))")

    # Les deux sens. Un refus non inscrit est le defaut que C22 ferme ; une
    # ligne 'subsiste' que le pont n'emet plus est un registre qui a derive.
    recalcules = _refus_recalcules(cur, boc_brut)
    inscrits = {(l["ticker"], int(l["exercice"])) for l in lignes}
    subsistent = {(l["ticker"], int(l["exercice"])) for l in lignes
                  if l["refus_subsiste"].strip().lower() == "oui"}

    non_inscrits = sorted(f"{t} ex.{e}" for t, e in recalcules - inscrits)
    verifie(not non_inscrits,
            f"les {len(recalcules)} refus que le pont emet sont tous inscrits au "
            f"registre"
            + ("" if not non_inscrits
               else " — REFUS NOUVEAU SANS MOTIF ECRIT : " + ", ".join(non_inscrits)
                    + f" ; l'inscrire dans {REGISTRE_REFUS} avec sa valeur "
                      f"retenue, son motif et son chantier"))

    fantomes = sorted(f"{t} ex.{e}" for t, e in subsistent - recalcules)
    verifie(not fantomes,
            f"les {len(subsistent)} refus marques 'subsiste : oui' sont tous "
            f"emis par le pont"
            + ("" if not fantomes else " — FANTOMES, le pont ne les emet plus : "
                                       + ", ".join(fantomes)))

    # Un TRANCHE_APPLIQUE dont le refus subsiste est un arbitrage qui n'a pas
    # pris : c'est exactement le faux vert que la chasse du cycle 11 cherchait.
    rates = sorted(f"{l['ticker']} ex.{l['exercice']}" for l in lignes
                   if l["decision"] == "TRANCHE_APPLIQUE"
                   and (l["ticker"], int(l["exercice"])) in recalcules)
    verifie(not rates,
            "aucun arbitrage marque TRANCHE_APPLIQUE ne voit son refus subsister"
            + ("" if not rates else " — NON APPLIQUE EN FAIT : " + ", ".join(rates)))

    # Et la consequence concrete de l'arbitrage NSBC : la table n'a plus de
    # montant vide. C'etait le seul, et il tenait a une date d'AGO.
    vides = [f"{t} ex.{e}" for t, e in cur.execute(
        "SELECT ticker, exercice_couvert FROM dividendes WHERE montant_net IS NULL "
        "AND ticker NOT LIKE 'TEST_%'")]
    verifie(not vides,
            "aucun montant de dividende n'est vide dans la table"
            + ("" if not vides else " — VIDES : " + ", ".join(vides)),
            bloquant=False)


# ----------------------------------------------------------------------
# 25. LECTURE DES BASSINS DE PERCENTILE (bloquant + alerte)
# ----------------------------------------------------------------------
def test_lecture_des_bassins():
    """L'effet de bassin est assume : option (a), tranchee par Claudia (C20).

    POURQUOI CETTE SECTION EXISTE (chantier C20, 02/10/2026, cycle 13).
    En appliquant C16 le 01/10, retirer deux rendements BAS du bassin a fait
    perdre 1 a 3 points de decote a 28 titres sur 47 sans qu'aucune de leurs
    donnees ait change, et SMBC a perdu son secondaire VALUE pour cette seule
    raison. Trois lectures etaient defendables ; Claudia a ecrit
    "validation : OK option (a)" : le rang est relatif, un bassin qui change EST
    une information. Cette section fige ce choix, et porte son CONTRE-EXEMPLE —
    sans quoi elle passerait aussi sur les options refusees.

    Les deux proprietes de l'option (a), et ce que les autres lectures auraient
    rendu sur le MEME bassin jetable (donc independant des donnees du jour) :

      1. un titre est dans son propre bassin — pctl() compte "val <= x" en
         incluant la valeur du titre. T2 rend donc une decote de 46 ; l'option
         (b) laisser-un-dehors aurait rendu 32. Et le titre le moins cher du
         bassin ne peut pas descendre a P0 : T1 rend 22, contre 0 en (b).
      2. la bascule secteur/marche se decide sur le SEUL bassin benefice/prix,
         pour les trois axes a la fois. Le secteur jetable porte 8 valeurs de
         benefice/prix et 3 seulement de rendement : l'option (a) lit le
         rendement sur ces 3 valeurs (33 points par cran) ; l'option (c)
         plancher-par-axe serait basculee sur le marche et aurait rendu 41.

    L'alerte en fin de section surveille la seule chose que l'option (a) laisse
    ouverte : le jour ou un secteur lu en sectoriel portera un axe sous le
    plancher, le cran de ce percentile depassera la marge des seuils. Mesure du
    02/10/2026 : 0 cas (SERVICES_FINANCIERS, seul secteur lu en sectoriel, porte
    14 valeurs en benefice/prix et 13 en rendement comme en croissance).
    """
    print("\n=== 25. Lecture des bassins de percentile (bloquant) ===")
    import json
    sys.path.insert(0, str(ICI))
    from profils import bassins_et_axes, pctl

    # --- Bassin jetable, independant des donnees du jour ----------------------
    # BANQUE : 8 titres en benefice/prix (le plancher est a 8), 3 seulement en
    # rendement. AUTRE : 4 titres, qui grossissent le bassin MARCHE.
    sp = {"n_secteur_min": 8}
    per = dict(T1=100.0, T2=50.0, T3=40.0, T4=25.0, T5=20.0, T6=10.0, T7=8.0,
               T8=5.0, U1=200.0, U2=25.0, U3=12.5, U4=4.0)
    dy = dict(T1=0.01, T2=0.05, T3=0.09, U1=0.02, U2=0.04, U3=0.06, U4=0.08)
    jetable = {t: {"per": per[t], "dy_axe": dy.get(t), "g": None,
                   "secteur": "BANQUE" if t.startswith("T") else "AUTRE"}
               for t in per}
    _ep, par_secteur, axes = bassins_et_axes(jetable, sp)

    verifie(len(par_secteur["BANQUE"]["ep"]) == 8
            and len(par_secteur["BANQUE"]["dy"]) == 3,
            "bassin jetable conforme : BANQUE porte 8 valeurs en benefice/prix "
            "et 3 en rendement, donc la bascule et l'axe divergent")

    d2, _g2, ref2 = axes("T2", jetable["T2"])
    verifie(ref2 == "secteur (n=8)" and d2 == 46,
            f"T2 est classe dans son propre bassin : decote {d2} (attendu 46, "
            f"reference '{ref2}')")
    # CONTRE-EXEMPLE 1 : laisser-un-dehors, option (b), refusee.
    ep_banque = sorted(par_secteur["BANQUE"]["ep"])
    dy_banque = sorted(par_secteur["BANQUE"]["dy"])
    sans_t2_ep = [v for v in ep_banque if v != 100.0 / 50.0]
    sans_t2_dy = [v for v in dy_banque if v != 0.05]
    d2_b = round((pctl(sans_t2_ep, 100.0 / 50.0) + pctl(sans_t2_dy, 0.05)) / 2)
    verifie(d2_b == 32 and d2 != d2_b,
            f"contre-exemple (b) : laisser-un-dehors aurait rendu {d2_b} pour T2 "
            f"(soit {d2 - d2_b:+d} point(s)), l'option (a) rend {d2}")

    d1, _g1, _r1 = axes("T1", jetable["T1"])
    d1_b = round((pctl([v for v in ep_banque if v != 1.0], 1.0)
                  + pctl([v for v in dy_banque if v != 0.01], 0.01)) / 2)
    verifie(d1 == 22 and d1_b == 0,
            f"le moins cher du bassin ne descend pas a P0 sous (a) : T1 rend {d1}, "
            f"contre {d1_b} en laisser-un-dehors — le rang mesure en partie la "
            f"presence du titre lui-meme, et c'est assume")

    # CONTRE-EXEMPLE 2 : plancher-par-axe, option (c), refusee. Le rendement de
    # T2 est lu sur les 3 valeurs du secteur, pas sur les 7 du marche.
    marche_dy = sorted(v for v in dy.values())
    d2_c = round((pctl(ep_banque, 100.0 / 50.0) + pctl(marche_dy, 0.05)) / 2)
    verifie(len(marche_dy) == 7 and d2_c == 41 and d2 != d2_c,
            f"contre-exemple (c) : un plancher par axe aurait bascule le rendement "
            f"de T2 sur le marche (n=7) et rendu {d2_c} ; l'option (a) le lit sur "
            f"les 3 valeurs du secteur et rend {d2}")
    verifie(pctl(dy_banque, 0.05) == 67 and round(100 / 3) == 33,
            "le cran du percentile de rendement de BANQUE vaut 33 points : "
            "l'option (a) accepte un bassin plus petit que le plancher sur un axe "
            "que la bascule ne regarde pas")

    # --- Veille sur les donnees du jour : le defaut latent est-il reste latent ?
    chemin = RACINE / "collecte" / "profils.json"
    if not chemin.exists() or not DB.exists():
        return
    pj = json.loads(chemin.read_text(encoding="utf-8"))
    secteurs = {}
    for t, v in pj.items():
        if v.get("decote_pctl") is None and v.get("croissance_pctl") is None:
            continue
        d = secteurs.setdefault(v.get("secteur") or "", {"dy": 0, "g": 0, "n": 0})
        d["n"] += 1
        if v.get("dy_recurrent") is not None:
            d["dy"] += 1
        if v.get("croissance_pctl") is not None:
            d["g"] += 1
    sectoriels = {t: v for t, v in pj.items()
                  if (v.get("reference_axes") or "").startswith("secteur")}
    etroits = sorted({
        "%s (benefice/prix %d, rendement %d, croissance %d)"
        % (v["secteur"], v.get("n_secteur") or 0,
           secteurs.get(v["secteur"], {}).get("dy", 0),
           secteurs.get(v["secteur"], {}).get("g", 0))
        for v in sectoriels.values()
        if min(secteurs.get(v["secteur"], {}).get("dy", 0),
               secteurs.get(v["secteur"], {}).get("g", 0)) < 8})
    verifie(not etroits,
            "aucun secteur lu en sectoriel ne porte un axe sous le plancher de 8 "
            "(C20 : le defaut reste latent)"
            + ("" if not etroits else " — DEVENU ACTIF sur " + " ; ".join(etroits)),
            bloquant=False)


# ----------------------------------------------------------------------
# 26. RATTACHEMENT D'UN DIVIDENDE A SON EXERCICE (bloquant + alertes)
# ----------------------------------------------------------------------
# Chaque divergence connue entre l'avis BRVM et la base, avec le chantier dont
# elle releve. Un cas NON inscrit ici fait tomber ou alerter la section.
#
# VIDE DEPUIS LE 05/10/2026 (cycle 20, chantier C22), et c'est le resultat, pas
# un relachement. Le seul cas inscrit etait NSBC 2025 : la base portait la date
# de l'AGO (2026-06-30) a la place de la date de paiement, et l'exemption
# existait pour que la section ne tombe pas dessus a chaque passage. C22 a
# tranche le cas -- date corrigee en 2026-08-04 par
# outils/arbitrage_refus_pont_boc.py, montant 675,98 complete par le pont --
# donc l'exemption n'a plus d'objet et elle part. Un registre d'exceptions qui
# ne se vide jamais finit par couvrir le defaut au lieu de le signaler.
RATTACHEMENTS_CONNUS = {}
# Avis de dividende que le collecteur n'a pas su rattacher a un ticker. Plafond
# qui ne peut que DESCENDRE : 19 sur 47 mesures le 02/10/2026.
AVIS_DIVIDENDE_SANS_TICKER_MAX = 19


def test_rattachement_exercice():
    """L'exercice d'un dividende est DEDUIT d'une regle ; la source qui le dit est ignoree.

    POURQUOI CETTE SECTION EXISTE (chasse du cycle 13, 02/10/2026). C10 avait
    laisse cette mesure explicitement non faite : `substr(date_paiement,1,4)`
    rendait `24-j` et l'annee de paiement etait inextractible. La colonne est ISO
    depuis le cycle 10, donc la confrontation est devenue possible — et elle
    montre que RIEN ne surveillait cette famille.

    Mesure du 02/10/2026, sur la base du jour : sur les 321 lignes datees et
    rattachees, 314 portent un exercice **deduit** par la seule regle
    `deduire_exercice()` (annee de paiement moins un, avril a decembre), que les
    DEUX chargeurs de dividendes appellent ; 7 seulement viennent de
    `donnees/base/dividendes.csv`, ou l'exercice est ecrit a la main. Le "+1 an
    sur 324 lignes sur 324" est donc une TAUTOLOGIE pour 97 % de la table : il
    mesure la regle, pas la realite. Trois cotes independants existent, et
    aucun n'etait lu :

      - les 9 rattachements ecrits a la main dans `donnees/base/dividendes.csv`
        (le TEST_ exclu) : la regle les reproduit 9 fois sur 9 ;
      - aucun titre ne verse deux fois dans la meme annee civile (0 cas sur
        324) : c'est ce qui ferme la faille principale de la regle, un acompte
        de l'exercice N verse en decembre N qu'elle rattacherait a N-1 ;
      - 18 avis BRVM NOMMENT l'exercice en clair dans leur titre
        ("paiement de dividendes exercice 2025 smb ci"). Aucun script du depot
        ne les lit. Confrontes ici : 14 concordants, 1 divergent (NSBC, deja
        inscrit en C22), 0 absent, sur les 15 qui portent un ticker.

    Le divergent est le meme defaut que C22 avait vu d'un autre cote : la base
    date NSBC ex.2025 du 30/06/2026, soit AVANT l'avis de paiement du
    21/07/2026. Un paiement ne precede pas son avis : c'est la date d'AGO.
    """
    print("\n=== 26. Rattachement d'un dividende a son exercice (bloquant) ===")
    import csv as _csv
    import re as _re
    sys.path.insert(0, str(RACINE / "collecte"))
    from historiser_dividendes_exercice import deduire_exercice

    # --- 1. La regle, bornes figees, et une seule definition dans le depot ----
    verifie(deduire_exercice(2025, 4) == (2024, "ELEVEE", deduire_exercice(2025, 4)[2])
            and deduire_exercice(2025, 12)[0] == 2024
            and deduire_exercice(2025, 7)[0] == 2024,
            "avril a decembre : exercice = annee de paiement - 1, confiance ELEVEE")
    for mois in (1, 2, 3):
        e, conf, _n = deduire_exercice(2025, mois)
        verifie(e is None and conf == "MANQUANT",
                f"mois {mois} : aucun exercice devine (MANQUANT), pas de regle -2 "
                f"inventee — l'avis BRVM N 072-2017 contredit le cas FTSC de janvier")

    definitions = sorted(
        p.relative_to(RACINE).as_posix()
        for p in RACINE.rglob("*.py")
        if p.name != "tester_donnees.py"  # ce fichier-ci porte la chaine cherchee
        and "def deduire_exercice" in p.read_text(encoding="utf-8", errors="ignore"))
    verifie(definitions == ["collecte/historiser_dividendes_exercice.py"],
            f"une seule definition de deduire_exercice dans le depot ({definitions})")
    appels = sorted(
        p.relative_to(RACINE).as_posix()
        for p in RACINE.rglob("*.py")
        if "deduire_exercice" in p.read_text(encoding="utf-8", errors="ignore")
        and p.name not in ("tester_donnees.py", "historiser_dividendes_exercice.py"))
    verifie(appels == ["collecte/charger_dividendes_boc.py"],
            f"les chargeurs passent par cette definition, aucun ne rededuit ({appels})")

    # --- 2. Le cote INDEPENDANT : les rattachements ecrits a la main ----------
    chemin_main = RACINE / "donnees" / "base" / "dividendes.csv"
    if chemin_main.exists():
        mains, desaccords = 0, []
        with chemin_main.open(encoding="utf-8") as f:
            for r in _csv.DictReader(f):
                if r["ticker"].startswith("TEST") or not r["date_paiement"] \
                        or not r["exercice_couvert"]:
                    continue
                mains += 1
                an, mois = int(r["date_paiement"][:4]), int(r["date_paiement"][5:7])
                if deduire_exercice(an, mois)[0] != int(r["exercice_couvert"]):
                    desaccords.append("%s ex.%s paye %s"
                                      % (r["ticker"], r["exercice_couvert"],
                                         r["date_paiement"]))
        verifie(mains >= 9 and not desaccords,
                f"la regle reproduit les {mains} rattachements ecrits a la main "
                f"(corroboration independante)"
                + ("" if not desaccords else " — desaccords : " + ", ".join(desaccords)))

    if not DB.exists():
        verifie(False, "moteur/brvm.db absent — confrontation en base non faite",
                bloquant=False)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # --- 3. En base : le rattachement est coherent avec sa date ---------------
    lignes = cur.execute(
        "SELECT ticker, date_paiement, exercice_couvert FROM dividendes "
        "WHERE date_paiement IS NOT NULL AND exercice_couvert IS NOT NULL "
        "AND ticker NOT LIKE 'TEST%'").fetchall()
    faux = ["%s ex.%d paye %s" % (t, e, d) for t, d, e in lignes
            if int(d[:4]) != e + 1]
    verifie(lignes and not faux,
            f"les {len(lignes)} rattachements dates valent exercice + 1 an"
            + ("" if not faux else " — hors regle : " + ", ".join(faux[:6])))

    # La propriete sur laquelle la regle -1 REPOSE : un titre ne verse qu'une
    # fois par annee civile. Un acompte de l'exercice N verse en decembre N
    # serait rattache a N-1 par la regle, sans qu'aucun controle ne le dise.
    doubles = cur.execute(
        "SELECT ticker, substr(date_paiement,1,4) a, COUNT(*) n FROM dividendes "
        "WHERE date_paiement IS NOT NULL AND ticker NOT LIKE 'TEST%' "
        "GROUP BY 1,2 HAVING n > 1").fetchall()
    verifie(not doubles,
            "aucun titre ne verse deux fois dans la meme annee civile — la regle "
            "-1 ne peut donc pas confondre un acompte avec un solde"
            + ("" if not doubles else " — a trancher : " + str(doubles[:6])))

    # --- 4. Le cote independant que personne ne lisait : les avis BRVM -------
    chemin_avis = RACINE / "collecte" / "avis_brvm.csv"
    if not chemin_avis.exists():
        conn.close()
        return
    with chemin_avis.open(encoding="utf-8") as f:
        avis = list(_csv.DictReader(f))
    divid = [r for r in avis
             if r.get("type") in ("DIVIDENDE", "DIVIDENDE_EXCEPTIONNEL")]
    nommes = []
    for r in divid:
        m = _re.search(r"exercice\s*(20\d\d)", r.get("titre") or "", _re.I)
        if m and (r.get("ticker") or "").strip():
            nommes.append((r["ticker"].strip(), int(m.group(1)), r["date_avis"]))

    absents, mal_dates, anterieurs, connus = [], [], [], []
    for tk, ex, da in sorted(set(nommes)):
        rs = cur.execute("SELECT date_paiement FROM dividendes "
                         "WHERE ticker=? AND exercice_couvert=?", (tk, ex)).fetchall()
        if (tk, ex) in RATTACHEMENTS_CONNUS:
            connus.append("%s ex.%d" % (tk, ex))
            continue
        if not rs:
            absents.append("%s ex.%d (avis %s)" % (tk, ex, da))
            continue
        for (d,) in rs:
            if d is None or int(d[:4]) != ex + 1:
                mal_dates.append("%s ex.%d : avis %s, base %s" % (tk, ex, da, d))
            elif d < da:
                anterieurs.append("%s ex.%d : paye %s, avis %s" % (tk, ex, d, da))
    verifie(len(nommes) >= 15,
            f"{len(set(nommes))} avis BRVM nomment leur exercice et portent un "
            f"ticker — c'est le seul cote independant du rattachement")
    verifie(not mal_dates,
            "aucun avis BRVM ne contredit l'exercice que la base porte"
            + ("" if not mal_dates else " — " + " ; ".join(mal_dates)))
    for cle in sorted(RATTACHEMENTS_CONNUS):
        if "%s ex.%d" % cle in connus:
            print("  [CONNU] %s ex.%d — %s" % (cle[0], cle[1], RATTACHEMENTS_CONNUS[cle]))
    verifie(not anterieurs,
            "aucun dividende n'est paye AVANT l'avis qui l'annonce (signature "
            "d'une date d'AGO prise pour une date de paiement)"
            + ("" if not anterieurs else " — " + " ; ".join(anterieurs)),
            bloquant=False)
    verifie(not absents,
            "tout exercice nomme par un avis est rattache en base"
            + ("" if not absents else " — manquants : " + ", ".join(absents)),
            bloquant=False)

    sans_ticker = len([r for r in divid if not (r.get("ticker") or "").strip()])
    verifie(sans_ticker <= AVIS_DIVIDENDE_SANS_TICKER_MAX,
            f"{sans_ticker} avis de dividende sur {len(divid)} ne sont rattaches a "
            f"aucun ticker (plafond {AVIS_DIVIDENDE_SANS_TICKER_MAX}, il ne peut "
            f"que descendre) — un avis sans ticker ne peut corroborer aucun "
            f"rattachement",
            bloquant=False)
    conn.close()


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


# ----------------------------------------------------------------------
# 27. LE BULLETIN PDF CONTRE LA PAGE « VOLUMES / VALEURS » (bloquant + alertes)
# ----------------------------------------------------------------------
# Tout ce que le depot sait du PER vient d'un seul document lu par un seul
# analyseur. La page brvm.org/fr/volumes/0, relevee par pipeline/collecte_volumes.py,
# publie le PER des 48 titres par une AUTRE chaine. Chantier C25.
#
# Plancher de titres releves. Mesure le 02/10/2026 (cycle 14) sur le premier
# releve reel : 48 lignes, dont 44 portent un PER. Le plancher ne peut que monter.
TITRES_RELEVES_MINIMUM = 40
PER_RELEVES_MINIMUM = 40

# Granularite publiee, MESUREE des deux cotes avant de fixer le moindre seuil,
# parce que deux sources qui arrondissent differemment divergent sans qu'aucune
# ait tort. Page : 43 valeurs a 2 decimales, 1 a 1 decimale. Bulletin : 71 020 a
# 2 decimales, 8 186 a 1 decimale sur 79 206. Les deux cotes publient donc deux
# decimales, et la tolerance est la moitie du dernier rang publie.
TOLERANCE_PER = 0.005
# Les indices sont publies a deux decimales des deux cotes.
TOLERANCE_INDICE = 0.005

# CONTRE-EXEMPLE FIGE, et c'est le controle qui donne son sens a l'ancrage.
# Confronter le releve du 02/10/2026 au bulletin de la seance VOISINE du
# 01/10/2026 donne 21 divergences sur 43 paires au-dela de TOLERANCE_PER ; au
# bulletin du 30/09, 35 sur 43. Confronter « le dernier des deux » plutot que la
# meme seance ne produirait donc pas du bruit : il nommerait 21 fausses
# divergences. C'est l'erreur exacte que C15 a du defaire, et la section refuse
# de confronter tant que la seance n'est pas ETABLIE.
DIVERGENCES_SEANCE_VOISINE_MINIMUM = 15

# Registre ADOSSE A LA VALEUR OBSERVEE : un ticker hors base de plus est signale,
# jamais silencieux.
#
# Pourquoi BBGC y reste apres le renommage du 04/10/2026 (cycle 19, C27). La
# colonne connu_en_base du releve est une OBSERVATION DATEE : le 02/10/2026,
# BBGC n'etait effectivement pas en base, puisqu'elle portait encore le
# mnemonique provisoire BBGCI. Le renommage ne change pas ce qui a ete observe
# ce jour-la, et reecrire la ligne du releve pour qu'elle dise « oui » serait
# falsifier un releve. Le prochain releve, lui, dira « oui » de lui-meme : BBGC
# sortira alors de l'ensemble hors-base sans que personne y touche, et ce
# registre pourra se vider.
TICKERS_HORS_BASE = {"BBGC"}

# Libelles des indices, de chaque cote.
INDICES_PAGE = {"composite": "BRVM-C", "brvm30": "BRVM-30", "prestige": "BRVM-PRES"}


def test_confrontation_per_page():
    """Le PER du bulletin PDF contre le PER de la page HTML, meme seance.

    POURQUOI CETTE SECTION EXISTE (02/10/2026, cycle 14, chantier C25). Les cours,
    le PER et le rendement viennent tous d'extracteur_boc.py, qui lit un PDF. Une
    erreur d'extraction est invisible tant qu'elle ne produit pas une valeur
    absurde. La page Volumes / Valeurs publie le PER par une autre chaine : une
    divergence ne peut venir que de l'une des deux, et une divergence est un
    SIGNALEMENT, jamais une correction automatique.

    CE QUE LA MESURE A APPRIS, ET QUI N'ETAIT PAS PREVU PAR C25. La page ne publie
    NI le cours de la cote (seuls le Top 5 et le Flop 5 en portent un) NI le
    rendement : la confrontation des 90 469 cours et l'arbitrage de C21 ne passent
    donc pas par elle. Elle publie le PER des 48 titres, et c'est tout.

    ET ELLE NE PUBLIE AUCUNE DATE — verifie dans le texte rendu comme dans le HTML
    brut. Le releveur laisse donc date_seance VIDE : stamper la date du jour serait
    une estimation pour combler un trou. La garantie « ne jamais confronter deux
    jours differents » est donc ICI, et elle tient a un ANCRAGE A DEUX COTES : les
    trois indices. Mesure du 02/10/2026 a 22h16 UTC — page BRVM-C 546,78 avec une
    variation veille de -0,41 %, bulletin de la seance du 01/10 composite 549,02.
    La veille implicite de la page vaut 549,031, soit 0,0020 % du composite du
    bulletin : la page montre donc la seance SUIVANTE, et elle le prouve sans
    passer par le PER qu'on veut confronter.

    Six controles. A : le releve porte au moins TITRES_RELEVES_MINIMUM titres
    (plancher, il ne peut que monter) — sans quoi le vider suffirait a rendre la
    section verte. B : la colonne PER reste renseignee, sinon la page a change de
    structure. C : aucun releve ne porte une date de seance SUPPOSEE — un futur
    cycle ne peut pas contourner l'ancrage en stampant la date du jour. D :
    l'ancrage, qui dit si la seance est etablie. E : la confrontation du PER, sur
    la seule seance etablie, divergences nommees. F : le registre des tickers que
    la base ignore.
    """
    print("\n=== 27. Bulletin PDF contre page Volumes / Valeurs (bloquant) ===")
    import csv as _csv
    rel_f = RACINE / "collecte" / "releve_volumes.csv"
    mar_f = RACINE / "collecte" / "releve_volumes_marche.csv"
    boc_f = RACINE / "donnees" / "boc.json"
    quot_f = RACINE / "collecte" / "cours_quotidien_boc.csv"
    if not rel_f.exists():
        verifie(False, "collecte/releve_volumes.csv absent : le releveur de la page "
                       "n'a jamais tourne (workflow volumes_quotidien.yml)",
                bloquant=False)
        return

    releves = list(_csv.DictReader(open(rel_f, encoding="utf-8")))
    if not releves:
        verifie(False, "collecte/releve_volumes.csv est vide : le releveur doit "
                       "echouer bruyamment, jamais rendre une table vide")
        return
    dernier_jour = max(r["date_releve"] for r in releves)
    dujour = [r for r in releves if r["date_releve"] == dernier_jour]

    # A — le releve est PLEIN. Plancher adosse a la mesure du 02/10/2026 (48).
    verifie(len(dujour) >= TITRES_RELEVES_MINIMUM,
            f"{len(dujour)} titre(s) releve(s) le {dernier_jour} "
            f"(plancher {TITRES_RELEVES_MINIMUM}, il ne peut que monter)"
            + ("" if len(dujour) >= TITRES_RELEVES_MINIMUM else
               " — LE RELEVE S'EST VIDE : vert sans rien confronter, l'etat que "
               "la section 19 portait avant C15"))

    # B — la structure de la page tient encore.
    per_page = {}
    for r in dujour:
        if r.get("per"):
            try:
                per_page[r["ticker"]] = float(r["per"])
            except ValueError:
                pass
    verifie(len(per_page) >= PER_RELEVES_MINIMUM,
            f"{len(per_page)} PER releve(s) sur la page (plancher {PER_RELEVES_MINIMUM})"
            + ("" if len(per_page) >= PER_RELEVES_MINIMUM else
               " — la colonne PER a disparu ou change de nom : la page a ete "
               "refondue, relire le diagnostic de pipeline/collecte_volumes.py"))

    # C — aucune date de seance supposee. C'est ce controle qui empeche un futur
    # cycle de contourner l'ancrage en stampant la date du jour.
    suppposees = [r["ticker"] for r in dujour
                  if (r.get("date_seance") or "")
                  and (r.get("date_seance_source") or "") != "page"]
    verifie(not suppposees,
            f"aucune date de seance supposee dans le releve ({len(dujour)} lignes verifiees)"
            + ("" if not suppposees else
               f" — {len(suppposees)} ligne(s) portent une date_seance sans que la "
               f"page la publie : une case vide vaut mieux qu'une valeur approchee "
               f"(" + ", ".join(suppposees[:5]) + ")"))

    # D — l'ancrage a deux cotes : les indices disent si la seance est etablie.
    if not (mar_f.exists() and boc_f.exists()):
        verifie(False, "releve_volumes_marche.csv ou donnees/boc.json absent : "
                       "la seance du releve ne peut pas etre ancree, aucune "
                       "confrontation n'est faite", bloquant=False)
        return
    marche = {r["libelle"]: r["valeur"] for r in _csv.DictReader(
        open(mar_f, encoding="utf-8")) if r["date_releve"] == dernier_jour}
    boc = json.loads(boc_f.read_text(encoding="utf-8"))
    seance_boc = boc.get("seance")
    indices_boc = boc.get("indices") or {}

    def num(t):
        if t is None:
            return None
        s = (str(t).replace("\xa0", "").replace(" ", "").replace(" ", "")
             .replace("FCFA", "").replace("%", "").replace(",", "."))
        try:
            return float(s)
        except ValueError:
            return None

    ecarts, lus = {}, 0
    for cle_boc, libelle in INDICES_PAGE.items():
        a = num(marche.get(libelle))
        b = (indices_boc.get(cle_boc) or {}).get("niveau")
        if a is None or b is None:
            continue
        lus += 1
        ecarts[libelle] = a - b
    verifie(lus == len(INDICES_PAGE),
            f"les {len(INDICES_PAGE)} indices sont lisibles des deux cotes ({lus} lus)"
            + ("" if lus == len(INDICES_PAGE) else
               " — sans eux la seance du releve ne peut pas etre ancree"),
            bloquant=False)

    concordent = lus == len(INDICES_PAGE) and all(
        abs(e) <= TOLERANCE_INDICE for e in ecarts.values())
    detail = ", ".join(f"{k} {v:+.2f}" for k, v in sorted(ecarts.items()))

    if concordent:
        # E — la seance est ETABLIE : le releve et le bulletin montrent le meme
        # jour. La confrontation du PER est legitime, et elle est bloquante.
        print(f"    ancrage : les indices concordent, seance etablie {seance_boc} ({detail})")
        per_boc = {}
        for r in _csv.DictReader(open(quot_f, encoding="utf-8")):
            if r["date_bulletin"] == seance_boc and r["per"]:
                try:
                    per_boc[r["ticker"]] = float(r["per"])
                except ValueError:
                    pass
        communs = sorted(set(per_page) & set(per_boc))
        verifie(len(communs) >= PER_RELEVES_MINIMUM,
                f"{len(communs)} PER confrontables sur la seance etablie {seance_boc} "
                f"(plancher {PER_RELEVES_MINIMUM})"
                + ("" if len(communs) >= PER_RELEVES_MINIMUM else
                   " — la confrontation s'est videe : verte sans rien confronter"))
        diverg = [(t, per_page[t], per_boc[t]) for t in communs
                  if abs(per_page[t] - per_boc[t]) > TOLERANCE_PER]
        verifie(not diverg,
                f"{len(communs)} PER confrontes sur la seance {seance_boc}, "
                f"{len(diverg)} divergent(s) au-dela de {TOLERANCE_PER} "
                f"— deux chaines independantes sur le meme jour"
                + ("" if not diverg else
                   " — SIGNALEMENT, pas une correction : l'inspection dit laquelle "
                   "des deux sources a tort : " + " ; ".join(
                       f"{t} page {a:g} contre bulletin {b:g}" for t, a, b in diverg[:8])))
    else:
        # La page montre une AUTRE seance que le bulletin. On verifie que c'est
        # bien la seance SUIVANTE, par la variation veille, et on ne confronte
        # RIEN. Alerte, jamais un faux vert.
        comp = num(marche.get(INDICES_PAGE["composite"]))
        var = num(marche.get("Variation veille (%)"))
        ref = (indices_boc.get("composite") or {}).get("niveau")
        veille = comp / (1 + var / 100) if (comp is not None and var not in (None, -100)) else None
        if veille is not None and ref:
            rel = abs(veille - ref) / ref
            if rel <= 0.001:
                verifie(False,
                        f"le releve du {dernier_jour} porte la seance SUIVANTE celle du "
                        f"bulletin ({seance_boc}) : la veille implicite de la page vaut "
                        f"{veille:.3f} contre {ref:.2f} au bulletin, soit {100 * rel:.4f} % "
                        f"— ancrage ferme des deux cotes, mais le bulletin de cette "
                        f"seance n'est pas encore collecte : AUCUNE confrontation faite, "
                        f"elle se fera au prochain passage de boc_quotidien.yml ({detail})",
                        bloquant=False)
            else:
                verifie(False,
                        f"la seance du releve du {dernier_jour} n'est pas identifiable : "
                        f"les indices diffèrent du bulletin {seance_boc} ({detail}) et la "
                        f"veille implicite de la page ({veille:.3f}) ne recouvre pas son "
                        f"composite ({ref:.2f}) a {100 * rel:.4f} % — ne rien confronter "
                        f"tant que la seance n'est pas etablie", bloquant=False)
        else:
            verifie(False,
                    f"la seance du releve du {dernier_jour} n'est pas ancrable : indices "
                    f"({detail}) et variation veille illisibles — aucune confrontation",
                    bloquant=False)

    # F — le contre-exemple qui donne son sens a l'ancrage. Confronter le releve a
    # une seance VOISINE doit produire beaucoup de divergences : sans l'ancrage, la
    # section nommerait ces fausses divergences comme des erreurs d'extraction.
    if not concordent and seance_boc:
        per_voisin = {}
        for r in _csv.DictReader(open(quot_f, encoding="utf-8")):
            if r["date_bulletin"] == seance_boc and r["per"]:
                try:
                    per_voisin[r["ticker"]] = float(r["per"])
                except ValueError:
                    pass
        com = sorted(set(per_page) & set(per_voisin))
        faux = [t for t in com if abs(per_page[t] - per_voisin[t]) > TOLERANCE_PER]
        if com:
            verifie(len(faux) >= DIVERGENCES_SEANCE_VOISINE_MINIMUM,
                    f"contre-exemple : confronter ce releve au bulletin voisin "
                    f"{seance_boc} donne {len(faux)} divergence(s) sur {len(com)} paires "
                    f"(plancher {DIVERGENCES_SEANCE_VOISINE_MINIMUM}) — c'est ce que "
                    f"confronter « le dernier des deux » nommerait a tort, et c'est "
                    f"pourquoi l'ancrage porte quelque chose"
                    + ("" if len(faux) >= DIVERGENCES_SEANCE_VOISINE_MINIMUM else
                       " — SI CE NOMBRE S'EFFONDRE, verifier que l'ancrage n'est pas "
                       "devenu inutile avant de baisser le plancher"))

    # G — registre des tickers que la page porte et que la base ignore.
    hors = {r["ticker"] for r in dujour if (r.get("connu_en_base") or "") == "non"}
    nouveaux = sorted(hors - TICKERS_HORS_BASE)
    verifie(not nouveaux,
            f"{len(hors)} ticker(s) de la page hors de societes.csv, registre "
            f"{sorted(TICKERS_HORS_BASE)}"
            + ("" if not nouveaux else
               f" — TICKER(S) NOUVEAU(X) SUR LA COTE : {nouveaux} ; les inscrire en "
               f"base est un arbitrage, pas une passe pre-autorisee"),
            bloquant=False)

# ---------------------------------------------------------------------------
# SECTION 29 — l'echelle de la colonne rendement du BOC quotidien (chantier C21)
# ---------------------------------------------------------------------------

# Plafonds mesures le 04/10/2026 (cycle 18), APRES la normalisation livree par
# outils/normalisation_rendement_boc.py. Ils ne peuvent que BAISSER.
POURCENTAGE_RESIDUEL_MAX = 1        # STBC 2018-08-01, 206,2 % : hors plafond du chargeur
MAL_ECHELONNEES_MAX = 0             # le defaut lui-meme : zero, et il y reste

# NON TRANCHEES : plafond change d'UNITE le 07/10/2026 (cycle 21), et ce n'est
# pas un relevement.
#
# Il valait 1756, « lignes qu'aucun des deux cotes ne tranche », pose le
# 04/10/2026 et annonce comme « ne pouvant que baisser ». Il a rougi le
# 07/10/2026 a 1786, SANS LA MOINDRE REGRESSION. La mesure du cycle 21 le dit a
# la ligne pres : 1756 jusqu'au 2026-10-01 inclus — le plafond exact de l'epoque
# — plus 15 pour le 2026-10-05 et 15 pour le 2026-10-06. Le taux par seance est
# de 15 depuis le 24/09, invariant.
#
# Le defaut n'est donc pas dans la donnee, il est dans l'UNITE du plafond : un
# compte ABSOLU pose sur une serie qui s'allonge de 47 lignes a chaque seance
# etait arithmetiquement condamne a tourner au rouge tout seul, et il l'a fait
# apres deux seances. Un tel plafond ne surveille rien : il ne sait pas
# distinguer la croissance normale d'une regression, et il crie pour la
# premiere.
#
# Le remplacant est un TAUX PAR SEANCE, en deux plafonds, et il ne derive pas.
#
# PREMIERE MESURE, CORRIGEE PAR LE TEST LUI-MEME. J'ai d'abord pose 15, releve
# sur les seules huit seances depuis le 24/09/2026 — et la section 34, ecrite le
# meme cycle, l'a fait tomber aussitot : sur les 2 031 seances de la serie, le
# maximum par seance est 34 (le 2025-01-02), puis 31 (2022-01-12) et 30
# (2023-06-02). La fenetre de huit seances n'etait pas representative. Les deux
# plafonds ci-dessous sont mesures sur la serie ENTIERE le 07/10/2026 :
#
#   - 34 par seance sur toute la serie, c'est le residu historique, borne ;
#   - 15 par seance sur les 91 seances de 2026, c'est le regime COURANT, et
#     c'est ce plafond-la qui garde la collecte d'aujourd'hui. Il est deux fois
#     plus severe que le precedent, et une seule seance qui deraille le fait
#     tomber — la ou le compte absolu avait besoin de 1 757 lignes cumulees.
#
# Le compte absolu reste publie en observation, pour que la grandeur reste
# lisible. Les deux taux, eux, ne peuvent que BAISSER.
NON_TRANCHEES_PAR_SEANCE_MAX = 34        # serie entiere, 2 031 seances
NON_TRANCHEES_PAR_SEANCE_2026_MAX = 15   # regime courant, 91 seances de 2026
RUPTURES_VOISINES_MAX = 291         # frontieres de changement de dividende, alerte seule
FTSC_RENDEMENT_REEL_MIN = 0.50      # C1 : la distribution 2025 de FTSC est exacte


def test_echelle_rendement_boc():
    """La colonne `rendement` du BOC porte-t-elle UNE seule unite ?

    POURQUOI CETTE SECTION EXISTE (04/10/2026, cycle 18, chantier C21). C21
    annoncait « 29 seances sur 7 titres » portant un facteur 100, et un defaut
    LATENT. La mesure ligne a ligne dit autre chose : le fichier
    `collecte/cours_quotidien_boc.csv` melangeait DEUX unites depuis l'origine
    — 68 426 lignes en POURCENTAGE contre 5 370 en FRACTION — et le pont
    `charger_cours_quotidien.py` tranchait entre elles **par la grandeur**
    (au-dessus de 1,5 on divise par cent). C'est une estimation, que la
    premiere regle du depot interdit, et elle etait fausse sur **1 683**
    lignes : un rendement publie SOUS 1,5 % restait non divise et entrait en
    base cent fois trop grand.

    Le defaut etait bien latent au sens de C21 — aucune de ces lignes n'est la
    derniere seance d'un titre, et `collecte/profils.json` n'a pas bouge d'un
    champ — mais il ne l'etait pas pour les trois backtests du depot, qui
    lisent la serie entiere.

    Cinq controles. A : plus aucune ligne prouvee en pourcentage, sauf le
    residu nomme. B : zero ligne mal echelonnee par le chargeur — c'est le
    defaut lui-meme. C : le residu non tranche ne grossit pas. D : aucune
    valeur superieure a 1,5 en base. E : FTSC n'est pas balaye — son rendement
    de 86,5 % est REEL (C1), et toute regle qui l'effacerait effacerait un
    fait. Plus une alerte : les ruptures d'echelle restantes entre deux seances
    voisines, qui sont des changements de dividende, pas des defauts.
    """
    print("\n=== 29. Echelle de la colonne rendement du BOC (bloquant) ===")
    sys.path.insert(0, str(RACINE / "outils"))
    import normalisation_rendement_boc as nrb

    sha, entete, _corps, lignes = nrb.lire()
    verdict = nrb.classer(lignes, nrb.dividendes_mensuels())

    pourcentage, fraction, non_tranchees, mal = 0, 0, 0, []
    import collections as _col
    nt_par_seance = _col.Counter()
    for i, r in enumerate(lignes):
        v = nrb._flot(r["rendement"])
        if v is None:
            continue
        g = verdict.get(i)
        if g == "P":
            pourcentage += 1
            if v <= nrb.SEUIL_CHARGEUR:
                mal.append((r["ticker"], r["date_bulletin"], v))
        elif g == "F":
            fraction += 1
        else:
            non_tranchees += 1
            nt_par_seance[(r.get("date_bulletin") or "").strip()] += 1

    # --- A : le fichier ne porte plus qu'un residu nomme en pourcentage
    verifie(pourcentage <= POURCENTAGE_RESIDUEL_MAX,
            f"{pourcentage} ligne(s) prouvee(s) en pourcentage, plafond "
            f"{POURCENTAGE_RESIDUEL_MAX} (STBC 2018-08-01, 206,2 % : au-dela du "
            f"plafond du chargeur, laissee telle quelle pour que la case reste "
            f"VIDE plutot que fausse) ; {fraction} en fraction")

    # --- B : le defaut lui-meme
    verifie(len(mal) <= MAL_ECHELONNEES_MAX,
            f"{len(mal)} ligne(s) en pourcentage sous le seuil {nrb.SEUIL_CHARGEUR} du "
            f"chargeur — elles entreraient en base CENT FOIS trop grandes (plafond "
            f"{MAL_ECHELONNEES_MAX})"
            + ("" if not mal else f" : {mal[:8]}"))

    # --- C : le residu non tranche ne grossit pas, SEANCE PAR SEANCE
    # (unite corrigee le 07/10/2026, cycle 21 : voir le commentaire de
    # NON_TRANCHEES_PAR_SEANCE_MAX. Un compte absolu sur une serie qui croit de
    # 47 lignes par seance tournait au rouge sans regression.)
    pires = sorted(nt_par_seance.items(), key=lambda kv: -kv[1])[:5]
    pire = pires[0][1] if pires else 0
    verifie(pire <= NON_TRANCHEES_PAR_SEANCE_MAX,
            f"au plus {pire} ligne(s) non tranchee(s) sur une MEME seance, plafond "
            f"{NON_TRANCHEES_PAR_SEANCE_MAX} par seance — un plafond qui ne peut que baisser"
            + ("" if pire <= NON_TRANCHEES_PAR_SEANCE_MAX
               else f" — seances en cause : {pires}"))
    pires_2026 = sorted(((d, n) for d, n in nt_par_seance.items() if d >= "2026-01-01"),
                        key=lambda kv: -kv[1])[:5]
    pire_2026 = pires_2026[0][1] if pires_2026 else 0
    verifie(pire_2026 <= NON_TRANCHEES_PAR_SEANCE_2026_MAX,
            f"au plus {pire_2026} ligne(s) non tranchee(s) sur une meme seance de 2026, "
            f"plafond {NON_TRANCHEES_PAR_SEANCE_2026_MAX} — c'est le regime courant, "
            f"celui qui garde la collecte d'aujourd'hui"
            + ("" if pire_2026 <= NON_TRANCHEES_PAR_SEANCE_2026_MAX
               else f" — seances en cause : {pires_2026}"))
    print(f"  [obs]  {non_tranchees} ligne(s) non tranchees au total sur "
          f"{len(nt_par_seance)} seance(s) concernee(s) — grandeur publiee pour "
          f"rester lisible ; le controle bloquant est le taux par seance ci-dessus")

    # --- D : la base ne porte aucune valeur hors echelle
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    hors = cur.execute(
        "SELECT ticker, date_bulletin, rendement FROM cours_quotidien_boc "
        "WHERE rendement IS NOT NULL AND rendement > ? ORDER BY rendement DESC LIMIT 5",
        (nrb.SEUIL_CHARGEUR,)).fetchall()
    verifie(not hors,
            f"aucun rendement superieur a {nrb.SEUIL_CHARGEUR} en base"
            + ("" if not hors else f" — {hors}"))

    # --- E : FTSC n'est pas balaye par une regle de niveau (C1)
    ftsc = cur.execute(
        "SELECT rendement FROM cours_quotidien_boc WHERE ticker='FTSC' "
        "AND rendement IS NOT NULL ORDER BY date_bulletin DESC LIMIT 1").fetchone()
    verifie(ftsc is not None and FTSC_RENDEMENT_REEL_MIN <= ftsc[0] <= nrb.SEUIL_CHARGEUR,
            f"FTSC garde son rendement REEL (C1) : {ftsc[0] if ftsc else None} — "
            f"entre {FTSC_RENDEMENT_REEL_MIN} et {nrb.SEUIL_CHARGEUR}, donc ni efface "
            f"par un seuil de niveau ni divise une seconde fois")
    conn.close()

    # --- alerte : les ruptures residuelles sont des changements de dividende
    par = {}
    for i, r in enumerate(lignes):
        par.setdefault(r["ticker"], []).append(i)
    ruptures = 0
    for ind in par.values():
        ind.sort(key=lambda i: lignes[i]["date_bulletin"])
        for a, b in zip(ind, ind[1:]):
            ra, rb = nrb._flot(lignes[a]["rendement"]), nrb._flot(lignes[b]["rendement"])
            ca, cb = nrb._flot(lignes[a]["cours"]), nrb._flot(lignes[b]["cours"])
            if not ra or not rb or not ca or not cb:
                continue
            if 50 <= max(ra / rb, rb / ra) <= 200 and abs(cb / ca - 1) < 0.20:
                ruptures += 1
    verifie(ruptures <= RUPTURES_VOISINES_MAX,
            f"{ruptures} rupture(s) d'echelle entre deux seances voisines, plafond "
            f"{RUPTURES_VOISINES_MAX} — ce sont les seances ou le dividende de "
            f"reference CHANGE, et le residu non tranche les borde ; un plafond qui "
            f"ne peut que baisser",
            bloquant=False)

# ---------------------------------------------------------------------------
# SECTION 30 — le PER du BOC bascule entre deux branches (chasse du cycle 18)
# ---------------------------------------------------------------------------

# UNITE CORRIGEE LE 07/10/2026 (cycle 21, chasse de la section 34).
#
# Ce plafond valait `BASCULES_PER_MAX = 23`, un compte ABSOLU et BLOQUANT sur
# une serie que la collecte allonge, pose le 04/10/2026 — et il etait deja a
# MARGE NULLE : 23 observees sur 23 autorisees. La seance suivante portant une
# bascule cassait la barriere. C'est exactement ce qui est arrive a
# NON_TRANCHEES_MAX, dont la panne a ouvert la chasse de ce cycle, et la
# section 34 interdit desormais cette forme.
#
# Le remplacant est un REGISTRE PAR TICKER, mesure le 07/10/2026 sur les
# 90 754 lignes : 23 bascules, reparties sur exactement les 12 titres deja
# nommes, 4 au plus pour un meme titre. Il est AUSSI severe que le compte total
# — une bascule de plus, sur n'importe quel titre, le fait tomber — et il ne
# derive pas, parce qu'il est indexe par titre et non par le temps. Chaque
# nombre ne peut que BAISSER, et la liste des titres ne peut que se reduire.
BASCULES_PAR_TICKER = {
    "SLBC": 4, "BNBC": 3, "FTSC": 3, "SICC": 3, "CABC": 2, "SMBC": 2,
    "BOAN": 1, "CIEC": 1, "PALC": 1, "SDSC": 1, "SPHC": 1, "UNXC": 1,
}
TICKERS_A_BASCULE_PER = set(BASCULES_PAR_TICKER)
# Titres dont le PER DU JOUR est plus de cinq fois leur propre mediane. FTSC est
# explique (C1 : resultat 2025 de 466 M contre 18 595 M en 2024) ; les quatre
# autres ne le sont pas, et c'est l'objet du chantier propose.
PER_DU_JOUR_HORS_BRANCHE = {"BNBC", "BOAN", "SDSC", "SICC", "FTSC"}
FACTEUR_BASCULE = 5.0


def test_bascule_per_boc():
    """Le PER du BOC saute d'une branche a l'autre sans que le cours bouge.

    POURQUOI CETTE SECTION EXISTE (chasse du cycle 18, 04/10/2026). Trois
    choses lisent le PER du BOC : l'axe de decote, le PEG/PEGY, et le payout
    implicite (`rendement x PER`). Une seule le confronte a quoi que ce soit —
    la section 27, et seulement sur UNE seance, contre la page Volumes /
    Valeurs. Les 75 000 autres valeurs ne sont confrontees a rien.

    L'identite disponible sans rien ouvrir : le BPA implicite d'une ligne vaut
    `cours / PER`, et il ne change qu'a la publication d'un resultat. Le cours
    et le rendement de la MEME ligne servent de temoins : s'ils sont continus
    et que le PER saute d'un facteur cinq, ce n'est pas le marche qui a bouge,
    c'est la definition du PER.

    Mesure du 04/10/2026 : **23 bascules** sur **12 titres**, toutes entre mars
    et juillet, et plusieurs ALTERNENT d'une annee sur l'autre — SLBC passe de
    4,60 a 29,82 en 2018, de 78,20 a 5,83 en 2021, de 6,43 a 116,29 en 2023, de
    112,57 a 9,09 en 2024. Un benefice n'alterne pas d'un facteur douze tous
    les ans ; deux definitions du BPA, si.

    **Le defaut n'est pas latent.** Le moteur ne lit que la DERNIERE valeur, et
    quatre titres portent aujourd'hui celle de la branche haute :
    BNBC 563,92 (51 fois sa propre mediane), BOAN 254,11 (34 fois),
    SDSC 202,15 (28 fois), SICC 139,98 (12 fois). Ces quatre PER sont le `per`
    publie dans `collecte/profils.json`. FTSC, cinquieme, est explique : C1 a
    etabli que son resultat 2025 s'est effondre.

    Trancher QUELLE branche fait foi demande une source exterieure (le nombre
    d'actions, que la base ne porte pas) : c'est un arbitrage, donc un chantier.
    Ce test fige ce qui est mesure et empeche la famille de grossir en silence.
    """
    print("\n=== 30. Bascule d'echelle du PER du BOC (bloquant) ===")
    import csv as _csv
    import statistics as _st

    chemin = RACINE / "collecte" / "cours_quotidien_boc.csv"
    par = {}
    with open(chemin, newline="", encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            par.setdefault(r["ticker"], []).append(r)

    def nombre(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    bascules, derniers = {}, {}
    for t, serie in par.items():
        serie.sort(key=lambda r: r["date_bulletin"])
        n = 0
        for a, b in zip(serie, serie[1:]):
            pa, pb = nombre(a["per"]), nombre(b["per"])
            ca, cb = nombre(a["cours"]), nombre(b["cours"])
            ra, rb = nombre(a["rendement"]), nombre(b["rendement"])
            if not pa or not pb or not ca or not cb or pa <= 0 or pb <= 0:
                continue
            if max(pa / pb, pb / pa) < FACTEUR_BASCULE:
                continue
            if abs(cb / ca - 1) >= 0.20:          # temoin 1 : le cours
                continue
            if ra and rb and abs(rb / ra - 1) >= 0.20:   # temoin 2 : le rendement
                continue
            n += 1
        if n:
            bascules[t] = n
        pers = [nombre(r["per"]) for r in serie if nombre(r["per"])]
        if pers:
            derniers[t] = (pers[-1], _st.median(pers))

    total = sum(bascules.values())
    # Registre par titre (unite corrigee le 07/10/2026) : chaque titre est
    # compare a SON nombre mesure, pas la serie entiere a un cumul.
    en_hausse = sorted(
        (t, n, BASCULES_PAR_TICKER.get(t, 0))
        for t, n in bascules.items() if n > BASCULES_PAR_TICKER.get(t, 0))
    verifie(not en_hausse,
            f"{total} bascule(s) d'echelle du PER a cours ET rendement continus, "
            f"chaque titre a ou sous son nombre mesure le 07/10/2026 — chaque nombre "
            f"ne peut que baisser"
            + ("" if not en_hausse else " — EN HAUSSE : " + ", ".join(
                f"{t} {n} contre {ref} au registre" for t, n, ref in en_hausse)))
    print(f"  [obs]  {total} bascule(s) au total sur {len(bascules)} titre(s) — "
          f"grandeur publiee pour rester lisible ; le controle bloquant est le "
          f"registre par titre ci-dessus")

    nouveaux = sorted(set(bascules) - TICKERS_A_BASCULE_PER)
    verifie(not nouveaux,
            f"{len(bascules)} titre(s) a bascule, registre {sorted(TICKERS_A_BASCULE_PER)}"
            + ("" if not nouveaux else
               f" — TITRE(S) NOUVEAU(X) : {nouveaux} ; trancher la branche demande "
               f"le nombre d'actions, que la base ne porte pas : c'est un arbitrage"))

    hors = sorted(t for t, (d, m) in derniers.items()
                  if t in bascules and m > 0 and max(d / m, m / d) > FACTEUR_BASCULE)
    verifie(set(hors) <= PER_DU_JOUR_HORS_BRANCHE,
            f"PER du jour a plus de {FACTEUR_BASCULE:.0f} fois la mediane du titre : "
            f"{hors} — registre {sorted(PER_DU_JOUR_HORS_BRANCHE)} (FTSC explique par C1)"
            + ("" if set(hors) <= PER_DU_JOUR_HORS_BRANCHE else
               f" ; NOUVEAU(X) : {sorted(set(hors) - PER_DU_JOUR_HORS_BRANCHE)}"),
            bloquant=False)





# ---------------------------------------------------------------------------
# SECTION 31 — un releve de collecte commite cesse d'avancer en silence
#              (chasse du cycle 20, 05/10/2026)
# ---------------------------------------------------------------------------
# Retard mesure le 05/10/2026, en SEANCES du quotidien (derniere seance en base
# 2026-10-01, 2 029 seances). Registre adosse aux valeurs OBSERVEES : une hausse
# est signalee, jamais silencieuse. Un plafond ne peut que DESCENDRE.
#
#   fichier -> (colonne de date lue, retard observe en seances, plafond, motif)
#
# Les deux premiers sont les cas qui ont ouvert la chasse : ils se sont arretes
# le MEME jour, le 2026-07-24, alors que le quotidien a continue 44 seances.
RETARD_RELEVES_MAX = {
    "collecte/dividendes_historique.csv": (
        "derniere_observation", 44, 60,
        "releve des fenetres d'observation du BOC ; dividendes_par_exercice.csv "
        "en est GENERE, donc son retard se propage a toute regeneration"),
    "collecte/liquidite_quotidienne_historique.csv": (
        "date_bulletin", 44, 60,
        "releve de la liquidite quotidienne (table de C14)"),
    "collecte/dividendes_boc.csv": (
        "date_paiement", 1, 30,
        "colonne Dernier dividende paye du bulletin ; une date de PAIEMENT, donc "
        "un retard apparent est normal entre deux saisons d'AGM"),
    "collecte/cours_quotidien_boc.csv": (
        "date_bulletin", 0, 10,
        "la serie de reference : c'est elle qui donne la derniere seance"),
}

# Lignes de collecte/dividendes_boc.csv absentes de dividendes_historique.csv.
# Consequence DIRECTE du retard du premier releve, et elle est chiffree : une
# regeneration de dividendes_par_exercice.csv perdrait ces valeurs. 17 mesurees
# le 05/10/2026, toutes collectees entre le 2026-07-28 et le 2026-09-28.
# Plafond qui ne peut que DESCENDRE.
OBSERVATIONS_NON_RELEVEES_MAX = 17


def _derniere_date_iso(chemin, colonne):
    """La plus grande date ISO portee par `colonne`, ou None."""
    import csv as _csv
    chemin_abs = RACINE / chemin
    if not chemin_abs.exists():
        return None
    maxi = None
    with chemin_abs.open(encoding="utf-8", newline="") as f:
        lecteur = _csv.DictReader(f)
        if colonne not in (lecteur.fieldnames or []):
            return None
        for r in lecteur:
            v = (r.get(colonne) or "").strip()
            if len(v) == 10 and v[4] == "-" and v[7] == "-" and (maxi is None or v > maxi):
                maxi = v
    return maxi


def test_fraicheur_releves_collecte():
    """Un releve commite qui cesse d'avancer doit le DIRE, pas attendre d'etre lu.

    POURQUOI CETTE SECTION EXISTE (chasse du cycle 20, 05/10/2026). Le depot
    surveille la fraicheur de ce qu'il LIT -- cours_mensuels contre le quotidien
    (section 2), profils.json contre la base (section 23). Il ne surveillait pas
    la fraicheur de ce qu'il ECRIT : les releves commites de collecte/, qui sont
    la memoire longue des collecteurs.

    Deux d'entre eux se sont arretes le MEME jour, le 2026-07-24, et rien ne le
    disait. Mesure de ce cycle : le quotidien a publie 44 seances de plus
    (jusqu'au 2026-10-01) pendant que ni collecte/dividendes_historique.csv ni
    collecte/liquidite_quotidienne_historique.csv n'avancaient d'une ligne.

    CE QUE CELA COUTE, ET C'EST MESURE, pas suppose.
    collecte/dividendes_par_exercice.csv n'est pas un fichier saisi : il est
    GENERE par historiser_dividendes_exercice.py depuis
    collecte/dividendes_historique.csv. Or 17 des 64 lignes de
    collecte/dividendes_boc.csv -- toutes collectees entre le 2026-07-28 et le
    2026-09-28 -- sont absentes du releve. Une regeneration du fichier genere
    les perdrait toutes les 17, dont NSBC 675,98 du 04/08/2026 : la valeur meme
    que C22 vient de faire entrer en base ce cycle. Le defaut est LATENT tant que
    personne ne regenere, et ARME des que quelqu'un le fait.
    Cote liquidite, les 44 seances postericures au 2026-07-24 sont exactement 44
    des 195 seances du quotidien sans aucune ligne de liquidite.

    SEVERITES. Bloquant : que le registre COUVRE chaque fichier mesure, et que
    chaque fichier du registre existe et porte bien sa colonne de date -- ce sont
    des proprietes du registre et du depot. En alerte : le retard lui-meme et le
    nombre d'observations non relevees, parce qu'ils viennent des workflows de
    collecte et que ce fichier ne bloque pas un commit de code pour un defaut de
    source. C'est la meme separation que la section 24.
    """
    print("\n=== 31. Fraicheur des releves de collecte commites "
          "(bloquant + alertes) ===")
    import csv as _csv

    reference = _derniere_date_iso("collecte/cours_quotidien_boc.csv", "date_bulletin")
    if not verifie(reference is not None,
                   "collecte/cours_quotidien_boc.csv donne la derniere seance de "
                   "reference"):
        return
    seances = set()
    with (RACINE / "collecte" / "cours_quotidien_boc.csv").open(
            encoding="utf-8", newline="") as f:
        for r in _csv.DictReader(f):
            v = (r.get("date_bulletin") or "").strip()
            if len(v) == 10:
                seances.add(v)
    ordonnees = sorted(seances)
    verifie(len(ordonnees) >= 2000,
            f"la mesure porte sur une population reelle ({len(ordonnees)} seances, "
            f"derniere {reference})")

    for chemin, (colonne, observe, plafond, motif) in sorted(
            RETARD_RELEVES_MAX.items()):
        chemin_abs = RACINE / chemin
        if not verifie(chemin_abs.exists(), f"{chemin} existe"):
            continue
        derniere = _derniere_date_iso(chemin, colonne)
        if not verifie(derniere is not None,
                       f"{chemin} porte bien une colonne {colonne} datee en ISO"):
            continue
        retard = sum(1 for s in ordonnees if s > derniere)
        verifie(retard <= plafond,
                f"{chemin} : derniere date {derniere}, {retard} seance(s) de "
                f"retard sur {reference} (plafond {plafond}, observe {observe} le "
                f"05/10/2026) — {motif}"
                + ("" if retard <= plafond
                   else " — EN HAUSSE : le releve a cesse d'avancer et rien "
                        "d'autre ne le dit"),
                bloquant=False)

    # Le registre doit couvrir ce qui est reellement commite : un releve nouveau
    # qui porterait une date de seance sans etre inscrit ici serait exactement le
    # defaut que cette section ferme, vu une fois de plus.
    attendus = {"collecte/dividendes_historique.csv",
                "collecte/liquidite_quotidienne_historique.csv",
                "collecte/dividendes_boc.csv",
                "collecte/cours_quotidien_boc.csv"}
    verifie(attendus <= set(RETARD_RELEVES_MAX),
            f"le registre couvre les {len(attendus)} releves commites qui portent "
            f"une date de seance ou d'observation"
            + ("" if attendus <= set(RETARD_RELEVES_MAX)
               else " — NON COUVERTS : " + ", ".join(sorted(attendus - set(RETARD_RELEVES_MAX)))))

    # --- La consequence chiffree : ce qu'une regeneration perdrait -----------
    sys.path.insert(0, str(RACINE / "collecte"))
    from dates_dividendes import vers_iso  # noqa: E402
    releve = set()
    with (RACINE / "collecte" / "dividendes_historique.csv").open(
            encoding="utf-8", newline="") as f:
        for r in _csv.DictReader(f):
            brut = (r.get("montant") or "").strip()
            try:
                d = vers_iso((r.get("date_paiement") or "").strip())
            except Exception:
                d = (r.get("date_paiement") or "").strip()
            releve.add((r.get("ticker"), brut and float(brut), d))
    absents = []
    with (RACINE / "collecte" / "dividendes_boc.csv").open(
            encoding="utf-8", newline="") as f:
        for r in _csv.DictReader(f):
            brut = (r.get("montant_net") or "").strip()
            cle = (r.get("ticker"), brut and float(brut),
                   (r.get("date_paiement") or "").strip())
            if cle not in releve:
                absents.append(f"{cle[0]} {cle[1]} le {cle[2]}")
    verifie(len(absents) <= OBSERVATIONS_NON_RELEVEES_MAX,
            f"{len(absents)} observation(s) de collecte/dividendes_boc.csv absente(s) "
            f"du releve dividendes_historique.csv (plafond "
            f"{OBSERVATIONS_NON_RELEVEES_MAX}) — une regeneration de "
            f"dividendes_par_exercice.csv les perdrait"
            + ("" if len(absents) <= OBSERVATIONS_NON_RELEVEES_MAX
               else " — EN HAUSSE : " + ", ".join(sorted(absents))),
            bloquant=False)

    # Et le cas nominatif qui donne la mesure son sens : la valeur que C22 vient
    # de faire entrer en base est parmi les absentes. Non bloquant, mais nomme :
    # si elle en sort, c'est que le releve a ete rattrape.
    nsbc = [a for a in absents if a.startswith("NSBC")]
    verifie(not nsbc,
            "NSBC 675.98 du 2026-08-04, entre en base par C22, est aussi dans le "
            "releve dividendes_historique.csv"
            + ("" if not nsbc else " — ABSENTE du releve : " + ", ".join(nsbc)
                                   + " ; une regeneration de "
                                     "dividendes_par_exercice.csv la perdrait"),
            bloquant=False)



# ----------------------------------------------------------------------
# 32. L'HISTORIQUE DU QUOTIDIEN NE PEUT QUE CROITRE (bloquant)
# ----------------------------------------------------------------------
def test_historique_quotidien_protege():
    """Le 05/10/2026 a 15h11, le run de collecte_boc_quotidien.yml a commite
    cours_quotidien_boc.csv VIDE (90 660 lignes supprimees, restaurees par le
    revert 8fbdc5f). Cause : le collecteur, corrige le meme jour pour rattraper
    les seances manquees, sortait AVANT de recharger l'historique commite quand
    aucun BOC n'etait chargeable ; l'export du workflow a ecrit la table vide.

    Deux protections, chacune suffisante, et toutes deux figees ici :
      (1) main() recharge l'historique commite AVANT toute sortie ;
      (2) l'export du workflow refuse d'ecrire moins de lignes qu'il n'y en a."""
    print("\n=== 32. L'historique du quotidien ne peut que croitre (bloquant) ===")
    src = (RACINE / "collecte" / "collecte_boc_quotidien.py").read_text(encoding="utf-8")
    corps = src[src.index("def main():"):]
    i_recharge = corps.find("recharger_historique_committe(cur)")
    i_return = corps.find("return")
    verifie(i_recharge != -1 and (i_return == -1 or i_recharge < i_return),
            "collecte_boc_quotidien.main() recharge l'historique commite avant toute sortie")
    wf = (RACINE / ".github" / "workflows" / "collecte_boc_quotidien.yml").read_text(encoding="utf-8")
    verifie("REFUS" in wf and "len(rows) < avant" in wf,
            "l'export de collecte_boc_quotidien.yml refuse de reduire l'historique commite")
    f = RACINE / "collecte" / "cours_quotidien_boc.csv"
    n = max(sum(1 for _ in open(f, encoding="utf-8")) - 1, 0) if f.exists() else 0
    verifie(n >= 90660,
            f"cours_quotidien_boc.csv porte {n} lignes (plancher 90 660, releve du "
            "05/10/2026 ; il ne peut que monter)")


# ----------------------------------------------------------------------
# 33. AUCUNE LIGNE DE BULLETIN N'EST ECARTEE EN SILENCE (chantier C32)
# ----------------------------------------------------------------------
# Nombre de seances du quotidien, depuis la premiere cotation de BBGC le
# 2026-09-24 (BOC n(deg) 181), qui ne portent PAS BBGC. Mesure du 07/10/2026
# (cycle 21) : 8 seances sur 8 -- 24/09, 25/09, 28/09, 29/09, 30/09, 01/10,
# 05/10, 06/10, toutes a exactement 47 lignes. Ces huit-la sont deja ecrites et
# le collecteur ne les retentera pas (il saute toute seance deja en base) : leur
# rattrapage demande une reextraction ciblee, et c'est un chantier a part.
#
# ET ELLES SONT NOMMEES, PAS COMPTEES. Un plafond « au plus 8 seances sans
# BBGC » serait exactement le defaut que la chasse de ce cycle a trouve dans la
# section 29 : un compte absolu sur une serie que la collecte allonge, donc un
# plafond qui rougit tout seul a la seance suivante. La liste ci-dessous fige
# les huit seances CONNUES ; le controle exige ZERO seance manquante en dehors
# d'elles. Une neuvieme seance sans BBGC tombe donc immediatement, et chacune de
# ces huit qui sera rattrapee pourra sortir de la liste.
SEANCES_SANS_BBGC_CONNUES = {
    "2026-09-24", "2026-09-25", "2026-09-28", "2026-09-29",
    "2026-09-30", "2026-10-01", "2026-10-05", "2026-10-06",
}
PREMIERE_COTATION_BBGC = "2026-09-24"


def test_univers_bulletin_sans_silence():
    """POURQUOI CETTE SECTION EXISTE (chantier C32, 07/10/2026, cycle 21).
    collecte/extracteur_boc.py filtrait chaque bulletin par un ensemble de 47
    tickers ECRIT EN DUR. Bridge Bank Group CI est cotee depuis le 24/09/2026 ;
    de cette seance au 06/10 incluse, cours_quotidien_boc.csv a porte
    exactement 47 lignes a chaque fois, et jamais BBGC. La 48e ligne du
    bulletin etait jetee SANS AUCUNE TRACE -- ni alerte, ni journal, ni
    compteur : c'est le silence, plus que la liste, qui a laisse passer dix
    seances.

    Ce que cette section fige, et pourquoi chaque controle plutot qu'un autre :
      - l'univers est DERIVE de donnees/base/societes.csv, donc une prochaine
        introduction suit le referentiel au lieu d'attendre qu'on se souvienne
        d'un script de collecte ;
      - il COUVRE la cote observee (donnees/cote_reference.json, 48 titres lus
        du bulletin lui-meme) : c'est le controle qui tombera le jour ou une
        49e societe sera cotee sans etre inscrite, et il la nommera ;
      - un mnemonique de cotation que l'univers ecarte quand meme est NOMME,
        pas jete -- parce qu'aucune liste blanche, derivee ou non, n'est a
        l'abri d'avoir tort ;
      - et un entete ou un total ne declenche pas de fausse alerte, sans quoi
        le signalement serait aussitot ignore.
    La liste blanche est conservee a dessein : des OPCVM et des obligations du
    meme document partagent le motif de ticker (FGI, SBIF, cas reels)."""
    print("\n=== 33. Aucune ligne de bulletin n'est ecartee en silence (C32) ===")
    import csv as _csv
    sys.path.insert(0, str(RACINE / "collecte"))
    from univers_actions import univers_actions, UniversIndisponible  # noqa: E402
    import extracteur_boc as eb  # noqa: E402

    src = (RACINE / "collecte" / "extracteur_boc.py").read_text(encoding="utf-8")
    verifie("UNIVERS_ACTIONS = {" not in src,
            "extracteur_boc.py ne porte plus d'univers ecrit en dur")
    verifie("from univers_actions import univers_actions" in src,
            "extracteur_boc.py derive son univers de univers_actions.py")

    univers = univers_actions(forcer=True)
    cote = json.loads((RACINE / "donnees" / "cote_reference.json").read_text(
        encoding="utf-8"))
    absents = sorted(t for t in cote if t not in univers)
    verifie(not absents,
            f"les {len(cote)} titres de la cote observee (donnees/cote_reference.json) "
            f"sont tous dans l'univers"
            + ("" if not absents else " — ECARTES DU BULLETIN, donc PERDUS a chaque "
                                      "seance : " + ", ".join(absents)))
    verifie("BBGC" in univers,
            "BBGC est dans l'univers (la 48e ligne du bulletin est acceptee)")

    # Le signalement, eprouve sur des lignes fabriquees : un mnemonique de
    # cotation inconnu est nomme, un entete ne l'est pas.
    inconnu = ["ZZZC", "UN TITRE INCONNU", "CD"] + [""] * 4 + [
        "10", "1000", "5000", "0,0", "5100", "", "0,0", "9,9"]
    vus = set()
    verifie(eb.parser_ligne(inconnu, ecartes=vus) is None and vus == {"ZZZC"},
            f"un mnemonique de cotation hors univers est NOMME, pas jete "
            f"(obtenu : {sorted(vus)})")
    entete = ["SECTEUR", "TOTAL"] + [""] * 12
    vus2 = set()
    eb.parser_ligne(entete, ecartes=vus2)
    texte = ["XXXX", "une ligne de texte"] + [""] * 12
    eb.parser_ligne(texte, ecartes=vus2)
    verifie(not vus2,
            f"un entete, un total ou une ligne sans valeur ne declenche aucune "
            f"fausse alerte (obtenu : {sorted(vus2)})")

    # Le refus plutot que la devinette : un referentiel tronque doit arreter la
    # collecte, pas la laisser tourner sur un univers de deux tickers.
    import tempfile as _tmp
    with _tmp.TemporaryDirectory() as d:
        tronque = Path(d) / "societes.csv"
        tronque.write_text("ticker,nom\nABJC,Servair\n", encoding="utf-8")
        refuse = False
        try:
            univers_actions(tronque)
        except UniversIndisponible:
            refuse = True
        verifie(refuse,
                "un referentiel des societes tronque fait REFUSER l'univers, "
                "il ne rend jamais un ensemble degrade")

    # Et le compte de ce que la correction du code ne repare pas : les seances
    # deja ecrites a 47 lignes. Alerte de fraicheur, pas blocage -- le defaut
    # est dans le passe, et son rattrapage est un chantier a part.
    f = RACINE / "collecte" / "cours_quotidien_boc.csv"
    seances, avec_bbgc = set(), set()
    with f.open(encoding="utf-8", newline="") as fh:
        for r in _csv.DictReader(fh):
            d = (r.get("date_bulletin") or "").strip()
            if d >= PREMIERE_COTATION_BBGC:
                seances.add(d)
                if r.get("ticker") == "BBGC":
                    avec_bbgc.add(d)
    manquantes = sorted(seances - avec_bbgc)
    nouvelles = sorted(set(manquantes) - SEANCES_SANS_BBGC_CONNUES)
    verifie(not nouvelles,
            f"aucune seance NOUVELLE sans BBGC : {len(manquantes)} manquante(s) sur "
            f"{len(seances)} depuis le {PREMIERE_COTATION_BBGC}, toutes dans les "
            f"{len(SEANCES_SANS_BBGC_CONNUES)} seances connues et nommees"
            + ("" if not nouvelles
               else " — SEANCE(S) NOUVELLE(S), la correction de C32 n'a pas pris : "
                    + ", ".join(nouvelles)),
            bloquant=False)
    rattrapees = sorted(SEANCES_SANS_BBGC_CONNUES - set(manquantes))
    if rattrapees:
        print(f"  [obs]  {len(rattrapees)} seance(s) connue(s) desormais RATTRAPEE(S) : "
              + ", ".join(rattrapees) + " — a retirer de SEANCES_SANS_BBGC_CONNUES")


# ----------------------------------------------------------------------
# 34. UN PLAFOND BLOQUANT NE PEUT PAS ETRE UN CUMUL (chasse du cycle 21)
# ----------------------------------------------------------------------
# D'OU VIENT CETTE SECTION. Le 07/10/2026, la barriere etait DEJA ROUGE sur
# `main` avant tout travail du cycle, et aucune regression ne l'expliquait :
# NON_TRANCHEES_MAX valait 1756, pose le 04/10/2026, et la mesure du cycle 21
# l'a retrouve A LA LIGNE PRES — 1756 jusqu'au 2026-10-01 inclus, plus 15 pour
# le 05/10 et 15 pour le 06/10. Le plafond etait un COMPTE ABSOLU sur une serie
# que la collecte allonge de 47 lignes par seance : il etait condamne a rougir
# tout seul, et il l'a fait apres deux seances.
#
# LA FAMILLE, MESUREE LE 07/10/2026. Treize plafonds de ce fichier portent un
# compte ; quatre etaient DEJA A MARGE NULLE, c'est-a-dire qu'une seule seance
# de plus les faisait tomber : RUPTURES_VOISINES_MAX (291 observees sur 291),
# BASCULES_PER_MAX (23 sur 23), OBSERVATIONS_NON_RELEVEES_MAX (17 sur 17) et le
# plafond de seances sans BBGC pose par C32 le meme jour (8 sur 8, corrige en
# liste nommee dans la section 33 des que la chasse l'a vu). Les quatre sont des
# ALERTES, pas des blocages : ils auraient crie sans arreter personne. Le
# cinquieme, NON_TRANCHEES_MAX, etait le seul BLOQUANT de la famille, et c'est
# le seul qui a casse la barriere.
#
# LE CONTRE-EXEMPLE EST DANS LE MEME FICHIER, et c'est lui qui donne la regle.
# Les plafonds de la section 31 (fraicheur des releves) sont exprimes en
# SEANCES DE RETARD : 46 contre 60, 3 contre 30, 0 contre 10. Ils ne derivent
# pas, parce qu'un retard ne cumule pas — il monte quand la collecte s'arrete et
# redescend quand elle reprend. C'est la bonne unite.
#
# LA REGLE QUE CETTE SECTION FIGE : un plafond BLOQUANT doit etre un taux, un
# retard, ou un compte de cas nommes — jamais un cumul sur une serie qui croit.
# Un plafond non bloquant peut rester un cumul : il informe, il n'arrete rien.
# Et tout plafond nouveau doit etre CLASSE ici, sans quoi cette section tombe :
# c'est la seule facon qu'un plafond ne naisse plus sans que son unite ait ete
# pensee.
#
#   cumul    — compte absolu sur une serie que la collecte allonge : DERIVE
#   taux     — par seance, par titre, par ligne : ne derive pas
#   retard   — en seances d'ecart a la derniere seance connue : ne derive pas
#   ponctuel — un ensemble ferme de cas nommes, ou un zero : ne derive pas
UNITE_PLAFONDS = {
    "PAIRES_CONFRONTABLES_MINIMUM": "ponctuel",   # plancher, pas un plafond
    "FIGEMENTS_PER_MAX": "cumul",
    "FIGEMENTS_RENDEMENT_MAX": "cumul",
    "DATES_ISO_MIN": "ponctuel",
    "TITRES_PER_GLISSANT_MIN": "ponctuel",
    "REFERENCES_IDENTIFIEES_MIN": "ponctuel",
    "AVIS_DIVIDENDE_SANS_TICKER_MAX": "cumul",
    "TITRES_RELEVES_MINIMUM": "ponctuel",
    "PER_RELEVES_MINIMUM": "ponctuel",
    "DIVERGENCES_SEANCE_VOISINE_MINIMUM": "ponctuel",
    "POURCENTAGE_RESIDUEL_MAX": "ponctuel",       # un cas nomme : STBC 2018-08-01
    "MAL_ECHELONNEES_MAX": "ponctuel",            # zero, et il y reste
    "NON_TRANCHEES_PAR_SEANCE_MAX": "taux",       # corrige le 07/10/2026
    "NON_TRANCHEES_PAR_SEANCE_2026_MAX": "taux",  # regime courant
    "RUPTURES_VOISINES_MAX": "cumul",             # alerte seule
    "FTSC_RENDEMENT_REEL_MIN": "ponctuel",
    "OBSERVATIONS_NON_RELEVEES_MAX": "cumul",     # alerte seule
}
# Les registres en forme de dictionnaire ou d'ensemble nomme ne figurent pas
# ci-dessus et n'ont pas a y figurer : etre indexe par titre, par fichier ou par
# seance nommee est precisement ce qui les empeche de deriver. Ce sont
# BASCULES_PAR_TICKER (section 30), RETARD_RELEVES_MAX (section 31) et
# SEANCES_SANS_BBGC_CONNUES (section 33), tous trois issus de la conversion d'un
# cumul ou ecrits d'emblee sous cette forme.


def test_unite_des_plafonds():
    """Deux controles, et le premier est celui qui aurait sauve la barriere.

    A — aucun plafond BLOQUANT n'est un cumul. C'est la regle que la panne du
        07/10/2026 a ecrite : un cumul qui bloque arrete le depot sans qu'aucune
        regression ne se soit produite.
    B — tout plafond du fichier est classe dans UNITE_PLAFONDS. Sans ce
        controle, la regle A ne couvrirait que les plafonds d'aujourd'hui, et le
        prochain plafond ecrit a la main echapperait a la question.

    Le caractere bloquant est lu dans le code lui-meme : l'appel verifie() qui
    nomme la constante porte `bloquant=False` ou ne le porte pas. On ne demande
    pas aux sections de se declarer, on regarde ce qu'elles font."""
    print("\n=== 34. Un plafond bloquant ne peut pas etre un cumul (chasse C21/C32) ===")
    import re as _re
    src = (RACINE / "moteur" / "tester_donnees.py").read_text(encoding="utf-8")

    # B — l'inventaire : toute constante de seuil declaree au niveau module.
    declares = set(_re.findall(
        r"^([A-Z][A-Z0-9_]*(?:_MAX|_MIN|_MINIMUM))\s*=\s*-?[0-9]", src, _re.M))
    non_classes = sorted(declares - set(UNITE_PLAFONDS))
    verifie(not non_classes,
            f"les {len(declares)} plafonds du fichier sont tous classes dans "
            f"UNITE_PLAFONDS"
            + ("" if not non_classes
               else " — NON CLASSE(S), leur unite n'a pas ete pensee : "
                    + ", ".join(non_classes)))
    disparus = sorted(set(UNITE_PLAFONDS) - declares)
    verifie(not disparus,
            "UNITE_PLAFONDS ne classe aucun plafond disparu du fichier"
            + ("" if not disparus else " — A RETIRER : " + ", ".join(disparus)))

    # A — la regle. Pour chaque constante, l'appel verifie() qui la nomme.
    fautifs = []
    for nom, unite in sorted(UNITE_PLAFONDS.items()):
        if unite != "cumul":
            continue
        for m in _re.finditer(r"verifie\(", src):
            debut = m.start()
            # Fin de l'appel : la ligne vide qui suit, ou 1200 caracteres.
            fin = src.find("\n\n", debut)
            appel = src[debut:fin if 0 < fin - debut < 1600 else debut + 1600]
            if nom in appel and "bloquant=False" not in appel:
                fautifs.append(nom)
                break
    verifie(not fautifs,
            f"aucun des {sum(1 for u in UNITE_PLAFONDS.values() if u == 'cumul')} "
            f"plafonds de type `cumul` n'est bloquant"
            + ("" if not fautifs
               else " — BLOQUANT ET CUMULATIF, donc condamne a rougir sans "
                    "regression : " + ", ".join(sorted(set(fautifs)))))


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
    test_dates_dividendes_iso()
    test_per_glissant()
    test_reference_dividende_boc()
    test_lecture_des_bassins()
    test_rattachement_exercice()
    test_confrontation_per_page()
    test_echelle_rendement_boc()
    test_bascule_per_boc()
    test_fraicheur_releves_collecte()
    test_historique_quotidien_protege()
    test_univers_bulletin_sans_silence()
    test_unite_des_plafonds()
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
