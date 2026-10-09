#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/profils.py (v2 — 31/07/2026) — PROFILAGE DESCRIPTIF par signature.

CHANGEMENT DE DOCTRINE (acte le 31/07/2026) : l'objectif du cadre est le
PROFILAGE, pas la detection de re-rating. Le score de style 0-100 par
dimension (v1) est SUPPRIME : il produisait un "dominant" par maximum, ce
qui revient a classer alors que l'objectif est de decrire. Diagnostic mesure
sur la v1 : 29 titres sur 43 ressortaient VALUE, non par economie reelle
mais parce que le score VALUE (PER+rendement) etait le seul calculable pour
la majorite des titres -- un artefact de disponibilite de donnees.

REMPLACEMENT : profil deduit par SIGNATURE, sur 7 categories, dont 4
recuperent les titres que le gate ecartait sans les nommer (l'information
etait perdue).

Sources de croissance, par ordre de priorite (ecart median mesure entre les
deux sources : 11,8 points -- la hierarchie n'est pas cosmetique) :
  1. RN transcrits en base (VALIDE > PROBABLE), >= 3 exercices consecutivement
     beneficiaires -- doctrine du projet, conservee.
  2. BPA implicite (cours/PER du BOC) en repli, statut PROBABLE.
     Validation : NSBC uniquement (1646,5 implicite vs 1646 certifie).
     Chantier de validation 8-10 titres NON CLOS -> statut PROBABLE partout.

GARDES ANTI-ARTEFACT (ajoutees v2, decouvertes par test) : la garde v1
"exercices consecutivement beneficiaires" ne protege PAS d'une base positive
mais ECRASEE. Cas mesure : SLBC ressortait a +235 %/an sur un creux 2022 a
1,2 Md contre une mediane de serie a 20 Mds. Trois gardes :
  - troncature au pic     : ratio annuel > 3,5x  -> la serie repart apres le pic
  - base ecrasee          : 1er exercice < 30 % de la mediane de serie -> drapeau
  - plafond de croissance : g plafonnee a 60 %/an
  STATUT : seuils PROVISOIRES, calibres en echantillon (SLBC, CABC, ECOC,
  NEIC). Validation reelle au premier cas NOUVEAU traite sans retouche.

AXES : lecture percentile INTRA-SECTEUR si n_secteur >= 8, sinon MARCHE, avec
la reference toujours etiquetee. Fondement : (a) correctif du 14/07/2026
(PER median Services Financiers 12,6 vs Industriels 36,0 -> toute banque
ressortait VALUE par effet de multiple sectoriel) ; (b) mesure du 31/07/2026 :
axes relatifs = 62 % d'etiquettes stables sur 7 mois contre 47 % en seuils
absolus. La borne n>=8 evite les percentiles dans un secteur de 3 titres.

INTERDITS ACTES PAR LE COMITE (a ne jamais contourner en aval) :
  1. Ce module ne sert PAS a chercher les re-ratings explosifs : il en est
     structurellement l'anti-outil (les explosions partent du compartiment
     que le profilage ecarte ou signale).
  2. Le test point-in-time (GARP +94 % vs marche +80 % sur 12 mois) NE PEUT
     PAS etre invoque comme preuve de performance : p = 0,43, IC 90 %
     [-14 % ; +89 %]. Aucune superiorite de style n'est etablie sur la BRVM,
     et elle n'est meme pas testable en l'etat (GARP calculable sur 3
     titres-annees seulement entre 2019 et 2024).
  3. Etiquette DESCRIPTIVE, jamais decisionnelle. Le systeme ne decide seul
     d'aucune position.

Compatibilite : les cles "dominant", "mixte", "alerte_peg", "peg", "dy",
"confiance" sont conservees pour le dashboard HTML existant. Les cles
"VALUE"/"GROWTH"/"GARP" sont conservees a None (depreciees) pour que les
consommateurs n'affichent plus de score sans planter.

RENOMMAGE DU 27/09/2026 : la variable s'appelait "cherte" alors qu'elle
MONTE quand le titre est bon marche. SGBC, a PER 11,94 contre une mediane de
marche a 14,79, recevait "chertee P90" ; ORAC, a PER 19,12, recevait P22. La
fiche affichait donc "decote marquee (cherte P90)", une phrase qui se
contredit elle-meme. Le calcul etait juste, le nom disait l'inverse. La cle
de sortie est desormais "decote_pctl" : P100 = le moins cher de sa reference,
P0 = le plus cher. L'ancienne cle "cherte_pctl" n'est plus emise -- aucun
consommateur ne la lisait (verifie sur tout le depot avant renommage).

Sortie : collecte/profils.json
"""
import sqlite3
import json
import sys
from datetime import date
from pathlib import Path

DB = Path(__file__).resolve().parent / "brvm.db"
RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "collecte" / "profils.json"
FAITS = RACINE / "config" / "faits_qualitatifs.yaml"
NOTATIONS = RACINE / "collecte" / "notations_financieres.csv"
AVIS = RACINE / "collecte" / "avis_brvm.csv"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import charger_seuils, charger_marche, appliquer_gate  # noqa: E402
from arbitrage import (  # noqa: E402
    charger_agregateur, arbitrer, ecrire_rapport,
    EXPLICATIONS as EXPLICATIONS_ARBITRAGE)

# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------


def source_cours(cur):
    """Choisit la table de cours la plus FRAICHE et la renvoie sous une forme
    unifiee (fin_mois, cours, per, rendement).

    Correctif du 03/09/2026, sur constat direct de l'utilisateur : le tableau de
    bord affichait des cours arretes au 07/07/2026 alors que la collecte
    quotidienne (P11) allait jusqu'au 01/09 — pres de deux mois de retard.
    Cause : cours_mensuels est alimente par cours_extraits.csv (bulletins de FIN
    DE MOIS, extraction manuelle), tandis que cours_quotidien_boc est collecte
    chaque jour. Le pont charger_cours_quotidien.py existait depuis le 28/07 mais
    ni le moteur ni l'application ne lisaient la table qu'il remplit.

    Le mensuel n'est pas abandonne : il reste le repli si la table quotidienne est
    vide (base reconstruite sans le pont). L'argument de microstructure qui avait
    justifie le mensuel — sur un titre peu liquide, un cours quotidien isole peut
    n'etre qu'une transaction non representative — reste valable ; c'est pourquoi
    la DATE de la donnee est desormais exposee dans profils.json et affichee dans
    l'application, plutot que d'etre implicite.
    """
    try:
        n = cur.execute("SELECT COUNT(*) FROM cours_quotidien_boc").fetchone()[0]
    except Exception:
        n = 0
    if n:
        return "cours_quotidien_boc", "date_bulletin"
    return "cours_mensuels", "fin_mois"


def _mediane(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def pctl(vals, x, inverse=False):
    """Rang percentile de x dans vals. inverse=True : petit = bon (PER)."""
    v = sorted(val for val in vals if val is not None)
    if x is None or not v:
        return None
    return round(100 * sum(1 for val in v if (val >= x if inverse else val <= x)) / len(v))


# Types d'avis qui changent la lecture d'un titre. Recalcules ICI plutot que lus
# dans la colonne "critique" du CSV : celle-ci reflete la version du collecteur
# au moment de la collecte. Cas mesure le 24/09/2026 — la levee de suspension de
# Sucrivoire etait enregistree avec critique="non", parce que REPRISE_COTATION
# avait rejoint la liste des types critiques APRES la collecte du fichier. La
# levee restait donc invisible dans le tableau de bord alors meme qu'elle etait
# correctement classee.
TYPES_CRITIQUES = {"SUSPENSION", "REPRISE_COTATION", "PREMIERE_COTATION",
                   "FRACTIONNEMENT", "AUGMENTATION_CAPITAL", "RADIATION",
                   "OPA_OPR", "RETARD_PUBLICATION"}


def bassins_et_axes(analysables, sp):
    """Bassins de percentiles + fonction axes(t, v). Rend (ep, par_secteur, axes).

    HISSE AU NIVEAU MODULE le 01/10/2026 (cycle 11), sans changer un seul
    calcul : le bloc vivait a l'interieur de calculer(), donc la regle de
    l'axe de decote n'etait testable que par ancrage textuel ou en refaisant
    tourner tout le moteur. Garde posee a l'extraction : collecte/profils.json
    est identique au champ pres avant et apres le hissage.

    C16, OPTION (b), tranchee par Claudia le 30/09/2026 et appliquee ici.
    L'axe de decote lit "dy_axe" -- le rendement RECURRENT -- et non plus "dy",
    le rendement facial du BOC. Un titre drapeaute DISTRIBUTION_NON_RECURRENTE
    a donc une CASE VIDE sur cet axe : il n'y entre plus, et son rendement
    facial ne pese plus sur le bassin de comparaison des autres. La prime et
    les classements etaient deja dans ce cas depuis C1 (cycle 7) ; l'axe de
    decote etait la derniere lecture du rendement facial.

    Les deux consequences mesurees avant l'application (cycle 9, confirmees au
    cycle 11) sont assumees par ce choix : retirer deux rendements BAS du bassin
    (ORGT 2,05 % et SEMC 0,94 %) deplace 28 titres sur 47 de 1 a 3 points vers
    le cher sans qu'aucune de leurs donnees ait change, et ORGT gagne un profil
    VALUE parce que son rendement facial faux ne le penalise plus. L'effet de
    bassin lui-meme, lui, n'est pas tranche : voir C20.

    "dy" (facial) reste lu par le test du profil RENDEMENT et affiche sur la
    fiche : C1 l'a laisse ainsi, et C16 ne l'a pas remis en cause.
    """
    ep = {t: (100.0 / v["per"]) for t, v in analysables.items() if v["per"]}
    par_secteur = {}
    for t, v in analysables.items():
        d = par_secteur.setdefault(v["secteur"], {"ep": [], "dy": [], "g": []})
        if t in ep:
            d["ep"].append(ep[t])
        if v["dy_axe"] is not None:
            d["dy"].append(v["dy_axe"])
        if v["g"] is not None:
            d["g"].append(v["g"])
    marche_ep = list(ep.values())
    marche_dy = [v["dy_axe"] for v in analysables.values() if v["dy_axe"] is not None]
    marche_g = [v["g"] for v in analysables.values() if v["g"] is not None]

    def axes(t, v):
        d = par_secteur.get(v["secteur"], {"ep": [], "dy": [], "g": []})
        assez = len(d["ep"]) >= sp["n_secteur_min"]
        if assez:
            ref = "secteur (n=%d)" % len(d["ep"])
            p_ep = pctl(d["ep"], ep.get(t))
            p_dy = pctl(d["dy"], v["dy_axe"])
            p_g = pctl(d["g"], v["g"])
        else:
            ref = "marche (n=%d)" % len(marche_ep)
            p_ep = pctl(marche_ep, ep.get(t))
            p_dy = pctl(marche_dy, v["dy_axe"])
            p_g = pctl(marche_g, v["g"])
        dispo = [x for x in (p_ep, p_dy) if x is not None]
        # Percentile de DECOTE : il monte quand le titre est bon marche (P100 =
        # le moins cher de sa reference). Moyenne des rangs de rendement
        # benefice/prix et de rendement du dividende, tous deux croissants avec
        # le bon marche.
        decote = round(sum(dispo) / len(dispo)) if dispo else None
        return decote, p_g, ref

    return ep, par_secteur, axes


def charger_avis():
    """Avis officiels de la BRVM, par ticker, les plus recents d'abord.

    Ajout du 18/09/2026. Trois informations changeaient la lecture d'un titre du
    jour au lendemain sans que l'outil les voie : les suspensions de cotation
    (Sucrivoire, SICOR, SONOCO depuis le 16/09/2026), les projets de
    fractionnement soumis en assemblee extraordinaire (Sonatel), et les
    paiements de dividendes. Un titre suspendu reste profile comme s'il etait
    negociable ; un fractionnement non enregistre fausse toute la serie de cours,
    comme cela s'est produit sur Solibra.
    """
    if not AVIS.exists():
        return {}
    import csv as _csv
    par_ticker = {}
    with AVIS.open(encoding="utf-8") as f:
        for ligne in _csv.DictReader(f):
            t = (ligne.get("ticker") or "").strip()
            if t:
                ligne["critique"] = ("oui" if ligne.get("type") in TYPES_CRITIQUES
                                     else "non")
                par_ticker.setdefault(t, []).append(ligne)
    for t in par_ticker:
        par_ticker[t].sort(key=lambda x: x.get("date_avis", ""), reverse=True)
    return par_ticker


def evenements_cotation(avis_titre, jours=45):
    """Suspensions ET levees des dernieres semaines, dans l'ordre chronologique.

    Ajout du 24/09/2026 (retour d'usage). Jusqu'ici, quand la BRVM levait une
    suspension, le titre cessait simplement d'etre signale : l'information
    disparaissait sans que rien n'annonce la reprise. Or une levee est un
    evenement aussi important que la suspension — elle dit qu'un titre redevient
    negociable, et pourquoi il ne l'etait plus. On conserve donc la sequence
    complete sur une fenetre glissante, pour raconter l'EVOLUTION plutot que de
    n'afficher qu'un etat instantane.
    """
    from datetime import datetime, timedelta
    limite = (datetime.today() - timedelta(days=jours)).strftime("%Y-%m-%d")
    recents = [a for a in avis_titre
               if a.get("type") in ("SUSPENSION", "REPRISE_COTATION")
               and (a.get("date_avis") or "") >= limite]
    return sorted(recents, key=lambda a: a.get("date_avis") or "")


def historique_cotation(avis_titre, jours=120):
    """Suite des suspensions et reprises, du plus recent au plus ancien.

    Ajout du 24/09/2026, sur demande de l'utilisatrice : jusqu'ici, la levee
    d'une suspension faisait simplement DISPARAITRE l'alerte. Sucrivoire,
    suspendue le 17/09 et retablie le 22/09, est repassee de "suspendue" a rien
    du tout — comme si l'episode n'avait jamais eu lieu. Or une societe qui a
    ete suspendue pour manquement a ses obligations de publication, puis
    retablie cinq jours plus tard, n'est pas dans le meme etat qu'une societe
    qui n'a jamais ete inquietee. L'evenement reste une information, meme resolu.
    On conserve donc la trace et on affiche l'EVOLUTION.
    """
    from datetime import datetime as _dt
    limite = None
    try:
        limite = _dt.now().date().toordinal() - jours
    except Exception:
        pass
    suite = []
    for a in avis_titre:
        if a.get("type") not in ("SUSPENSION", "REPRISE_COTATION"):
            continue
        d = a.get("date_avis")
        if limite and d:
            try:
                if _dt.strptime(d[:10], "%Y-%m-%d").date().toordinal() < limite:
                    continue
            except Exception:
                pass
        suite.append({"date": d, "type": a.get("type"), "titre": a.get("titre"),
                      "url": a.get("url")})
    return suite


def statut_cotation(avis_titre):
    """SUSPENDU / NEGOCIABLE, d'apres le dernier avis de suspension ou de reprise.
    Un avis de reprise posterieur annule une suspension."""
    for a in avis_titre:
        if a.get("type") == "SUSPENSION":
            return "SUSPENDU", a.get("date_avis"), a.get("titre")
        if a.get("type") == "REPRISE_COTATION":
            return "NEGOCIABLE", a.get("date_avis"), a.get("titre")
    return "NEGOCIABLE", None, None


def charger_notations():
    """Notations d'agences (GCR, WARA...) collectees depuis brvm.org.

    PREMIERE SOURCE REELLEMENT INDEPENDANTE du pipeline : jusqu'ici tout
    recoupement passait par la BRVM (BOC) ou par la presse, qui reprend les
    memes communiques. Une agence a acces aux comptes et aux entretiens de
    direction : elle peut CONTREDIRE un profil.

    RAPPEL IMPERATIF : une notation mesure le RISQUE DE CREDIT, pas
    l'attractivite actionnaire (GCR l'ecrit explicitement : ses notations ne
    couvrent ni le risque de liquidite, ni le risque de marche, et ne sont pas
    des recommandations). Une note A+ n'est JAMAIS un profil GARP. Elle sert
    ici a VERIFIER, jamais a CLASSER.
    """
    if not NOTATIONS.exists():
        return {}
    import csv as _csv
    recentes = {}
    with NOTATIONS.open(encoding="utf-8") as f:
        for ligne in _csv.DictReader(f):
            t = (ligne.get("ticker") or "").strip()
            if not t or ligne.get("statut_extraction") not in ("OK", "SANS_NOTE"):
                continue
            anc = recentes.get(t)
            if anc is None or ligne["date_annonce"] > anc["date_annonce"]:
                recentes[t] = ligne
    return recentes


def charger_faits():
    """Faits qualitatifs dates et sources (RETOURNEMENT / MUTATION / squeeze).
    Aucun fait en dur dans le moteur : tout vit dans config/, versionne."""
    if not FAITS.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(FAITS.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


# ----------------------------------------------------------------------
# Sources de croissance
# ----------------------------------------------------------------------


def croissance_rn(cur, ticker, fenetre, pic_max, base_min, cap,
                  base_gonflee_max=1.5, fenetre_max=8, correctifs=None):
    """Croissance annualisee sur les RN transcrits en base.

    Retourne (g, statut, n_exercices, drapeaux). g=None si non calculable.
    Doctrine conservee : exercices CONSECUTIVEMENT beneficiaires uniquement.
    Gardes v2 : troncature au pic, base ecrasee, plafond.
    """
    # Serie enrichie : le comparatif N-1 d'un document certifie est lui-meme
    # certifie (pratique deja appliquee dans la base, cf. SDSC colonne 2023).
    # Mesure du 31/07/2026 : 53 exercices dormaient dans resultat_net_n1 sans
    # ligne d'exercice correspondante (ORAC 2024, SNTS 2021, SGBC 2024...).
    serie_dict = {}
    for ex, rn, rn1, st in cur.execute(
            "SELECT exercice, resultat_net, resultat_net_n1, statut_donnee "
            "FROM etats_financiers WHERE ticker=? ORDER BY exercice", (ticker,)):
        if rn1 is not None and (ex - 1) not in serie_dict:
            serie_dict[ex - 1] = (rn1, st, "COMPARATIF")
        if rn is not None:
            anc = serie_dict.get(ex)
            if anc and anc[2] == "COMPARATIF" and abs(anc[0] - rn) > 0.01 * max(abs(rn), 1):
                serie_dict[ex] = (rn, st, "CONFLIT")  # ligne prioritaire, conflit signale
            else:
                serie_dict[ex] = (rn, st, "LIGNE")
    # Correctifs d'arbitrage (26/09/2026) : un resultat net repris d'une source
    # exterieure parce que la ligne en base provient d'un OCR a source unique,
    # jamais certifiable. Applique APRES la construction de la serie pour que la
    # detection de CONFLIT sur le comparatif N-1 porte sur la donnee d'origine.
    for _ex, _rn in (correctifs or {}).items():
        if _ex in serie_dict:
            serie_dict[_ex] = (_rn, serie_dict[_ex][1], "ARBITRE")
    lignes = [(ex, v[0], v[1]) for ex, v in sorted(serie_dict.items(), reverse=True)]
    origines = {ex: v[2] for ex, v in serie_dict.items()}
    serie = []
    for exercice, rn, statut in lignes:
        if rn is None or rn <= 0:
            break
        serie.append((exercice, rn, statut))
    serie = serie[:fenetre]
    drapeaux = []
    if len(serie) < 3:
        return None, None, len(serie), drapeaux

    chrono = serie[::-1]  # du plus ancien au plus recent
    # Garde 1 : troncature au pic (rupture d'echelle = changement de nature)
    for i in range(1, len(chrono)):
        if chrono[i - 1][1] > 0 and chrono[i][1] / chrono[i - 1][1] > pic_max:
            drapeaux.append("PIC_YOY")
            chrono = chrono[i:]
            break
    if len(chrono) < 3:
        # Correctif cyclique (06/08/2026) : chez un titre cyclique, un creux profond
        # est une INFORMATION economique, pas un artefact. Cas mesures SPHC (creux
        # caoutchouc 2023 a 3 635 M -> ratio 5,17) et STBC (accises 2024 -> 3,61) :
        # la troncature ramenait la serie a 2 exercices, et le moteur basculait sur
        # le BPA implicite alors que 4 exercices CERTIFIES existaient en base. Une
        # donnee certifiee tronquee ne doit jamais ceder la place a une donnee
        # probable : on restaure la serie complete, avec un drapeau explicite.
        complete = serie[::-1]
        if len(complete) >= 3:
            chrono = complete
            drapeaux.append("CYCLE_SERIE_RESTAUREE")
        else:
            return None, None, len(chrono), drapeaux + ["SERIE_TRONQUEE"]

    # Garde 2 : base ecrasee (croissance depuis un creux non representatif)
    med = _mediane([x[1] for x in chrono])
    if med and chrono[0][1] < base_min * med:
        drapeaux.append("BASE_ECRASEE")

    # Garde 2bis (v3, 31/07/2026) : base GONFLEE — symetrique de la precedente.
    # Cas mesure PRSC : fenetre 2022-2025 demarrant sur le pic 2022 -> -12,7 %/an,
    # alors que la serie complete 2018-2025 donne +2,1 %/an et que le niveau
    # 2023-2025 depasse celui de 2018-2020. Sans cette garde, un titre STABLE
    # etait classe "benefices en contraction" avec un grade A.
    # Remede : elargir la fenetre quand des exercices anterieurs existent,
    # plutot que d'invalider la mesure.
    med_suivants = _mediane([x[1] for x in chrono[1:]])
    if med_suivants and chrono[0][1] > base_gonflee_max * med_suivants:
        if len(serie) > len(chrono) or len(lignes) > fenetre:
            serie_longue = []
            for exercice, rn, statut in lignes:
                if rn is None or rn <= 0:
                    break
                serie_longue.append((exercice, rn, statut))
            serie_longue = serie_longue[:fenetre_max][::-1]
            if len(serie_longue) > len(chrono):
                chrono = serie_longue
                drapeaux.append("FENETRE_ELARGIE")
            else:
                drapeaux.append("BASE_GONFLEE")
        else:
            drapeaux.append("BASE_GONFLEE")

    # Garde 4 : serie a trous (le CAGR relie deux bornes sans les points du milieu)
    span = chrono[-1][0] - chrono[0][0] + 1
    if span > len(chrono):
        drapeaux.append("SERIE_TROUEE")

    n = chrono[-1][0] - chrono[0][0]
    if n <= 0:
        return None, None, len(chrono), drapeaux
    g = (chrono[-1][1] / chrono[0][1]) ** (1.0 / n) - 1

    # Garde 3 : plafond
    if g > cap:
        drapeaux.append("CAP_%d" % round(cap * 100))
        g = cap

    # Drapeau INFLEXION_RECENTE (06/08/2026, jurisprudence STBC) : un CAGR positif peut
    # masquer un retournement en cours. Cas mesure STBC : serie 2022-2025 restauree
    # donnant +46,9 %/an, alors que le DERNIER exercice recule de 18,5 % (accises).
    # Un profil est un diagnostic DATE : la derniere variation prime sur la moyenne.
    if len(chrono) >= 2 and chrono[-2][1] > 0:
        var_derniere = chrono[-1][1] / chrono[-2][1] - 1
        if var_derniere < -0.10 and chrono[-1][1] > 0:
            drapeaux.append("INFLEXION_RECENTE")

    statut = "VERIFIE" if all(x[2] == "VALIDE" for x in chrono) else "PROBABLE"
    if any(origines.get(x[0]) == "COMPARATIF" for x in chrono):
        drapeaux.append("SERIE_COMPLETEE_N1")
    if any(origines.get(x[0]) == "CONFLIT" for x in chrono):
        drapeaux.append("CONFLIT_N1")
    return g, statut, len(chrono), drapeaux


def croissance_bpa_implicite(cur, ticker, annees, cap):
    """Repli : CAGR du BPA implicite (cours/PER du BOC), fin d'annee.
    Statut PROBABLE par construction (source circulaire : le PER vient de la
    BRVM elle-meme ; validation croisee faite sur NSBC uniquement)."""
    table, col = source_cours(cur)
    lignes = cur.execute(
        f"SELECT {col}, cours, per FROM {table} "
        "WHERE ticker=? AND per IS NOT NULL AND per>0 AND cours IS NOT NULL "
        f"ORDER BY {col}", (ticker,)).fetchall()
    if not lignes:
        return None, []
    par_an = {}
    for fin_mois, cours, per in lignes:
        par_an[fin_mois[:4]] = cours / per  # derniere observation de l'annee
    if len(par_an) < annees + 1:
        return None, []
    cles = sorted(par_an)
    debut, fin = par_an[cles[-(annees + 1)]], par_an[cles[-1]]
    if debut is None or fin is None or debut <= 0 or fin <= 0:
        return None, []
    g = (fin / debut) ** (1.0 / annees) - 1
    drapeaux = []
    if g > cap:
        drapeaux.append("CAP_%d" % round(cap * 100))
        g = cap
    return g, drapeaux


# ----------------------------------------------------------------------
# Ingredients par titre
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Distribution non recurrente (chantier C1, 30/09/2026)
# ----------------------------------------------------------------------
# Le rendement du BOC est arithmetiquement exact et peut pourtant ne pas etre un
# rendement de REVENU. Mesure du 30/09/2026 sur les 47 titres : FTSC porte une prime
# de +79,5 points (rendement 86,54 %), SIVC +19,7 points (26,81 %) ; le troisieme,
# STBC, est a +0,7 point. FTSC a verse 1 726,56 FCFA le 30/09/2025 contre 143,10 un
# an plus tot (dividende exceptionnel sur une plus-value de cession) ; le dividende
# de reference de SIVC date de 2017.
MOIS_FR = {"janv.": 1, "janv": 1, "fevr.": 2, "fevr": 2, "f\u00e9vr.": 2, "f\u00e9vr": 2,
           "mars": 3, "avr.": 4, "avr": 4, "mai": 5, "juin": 6, "juil.": 7, "juil": 7,
           "aout": 8, "ao\u00fbt": 8, "sept.": 9, "sept": 9, "oct.": 10, "oct": 10,
           "nov.": 11, "nov": 11, "dec.": 12, "dec": 12, "d\u00e9c.": 12, "d\u00e9c": 12}


def date_dividende(texte):
    """Date d'un paiement de dividende, ISO ou francais abrege ('30-sept.-25').

    Rend None plutot que de deviner : un mois non reconnu, une forme inattendue.
    (dividendes.date_paiement melange deux formats, chantier C10.) Annee sur deux
    chiffres lue comme 20AA : la base ne remonte pas avant 2017.
    """
    if not texte:
        return None
    t = str(texte).strip().lower()
    try:
        if len(t) == 10 and t[4] == "-" and t[7] == "-":
            return date(int(t[:4]), int(t[5:7]), int(t[8:10]))
        j, m, a = t.split("-")
        if m not in MOIS_FR or len(a) != 2:
            return None
        return date(2000 + int(a), MOIS_FR[m], int(j))
    except (ValueError, TypeError):
        return None


def diagnostic_distribution(cur, ticker, date_cours, sp, cours=None, dy=None):
    """(non_recurrente, detail) pour la distribution qui porte le rendement du BOC.

    Deux regles, qui ne se lisent que sur des dates et des montants presents en
    base ; sans historique suffisant, aucun drapeau (une case vide vaut mieux
    qu'une estimation) :
      1. PERIME : le dividende qui porte le rendement du BOC date de plus de
         `distribution_age_max_ans` ans. On l'identifie par le dividende IMPLICITE
         du BOC, rendement x cours, qui doit coincider (a
         `distribution_tolerance_implicite` pres) avec le versement date le PLUS
         RECENT de la table -- celui-la seul, parce que c'est par le dernier
         dividende paye que le BOC divise. Sans coincidence, on ne conclut pas :
         aucun drapeau. C'est le cas quand la table a un trou (NEIC 2025 et
         STBC 2025 y manquent, C5) comme quand le BOC connait un versement que
         nous n'avons pas : dans les deux cas la reference nous echappe, et une
         lacune de collecte n'est pas un fait sur la societe ;
      2. EXCEPTIONNEL : le dernier versement de la table depasse
         `distribution_ratio_max` fois le PLUS FORT des versements precedents (au
         moins `distribution_historique_min`). Contre le maximum et non la
         mediane : une serie qui monte (BICC 830 -> 1157) n'est pas exceptionnelle.
    """
    lignes = cur.execute(
        "SELECT montant_net, date_paiement FROM dividendes WHERE ticker=? "
        "AND montant_net IS NOT NULL AND montant_net > 0 "
        "AND COALESCE(statut_donnee, 'VALIDE')='VALIDE'", (ticker,)).fetchall()
    par_date = {}
    for montant, d in lignes:
        dd = date_dividende(d)
        if dd is not None:
            par_date[dd] = max(par_date.get(dd, 0.0), float(montant))
    if not par_date:
        return False, None
    try:
        auj = date.fromisoformat(str(date_cours)[:10])
    except (ValueError, TypeError):
        auj = None

    # --- Regle 1 : le dividende du BOC est-il perime ? -------------------------
    # CORRECTION du 30/09/2026, meme jour, session parallele du cycle 7. La
    # premiere version cherchait le versement le plus proche EN MONTANT parmi
    # TOUTES les dates. Sur une serie de versements voisins, le plus proche en
    # montant n'est pas forcement le plus recent, et la regle concluait alors
    # "dividende perime" sur un titre dont la MEME table porte un versement
    # POSTERIEUR. Quatre titres sur les neuf drapeautes PERIME etaient dans ce
    # cas, mesure sur la base du jour :
    #   NTLC  implicite 369,60 -> retenu 2021-07-30 (363,67), table : 2025-08-18 (721,60)
    #   SDCC  implicite 462,44 -> retenu 2023-09-15 (450,00), table : 2025-09-30 (352,00)
    #   SIBC  implicite 374,24 -> retenu 2021-07-23 (360,00), table : 2025-07-31 (330,00)
    #   SMBC  implicite 704,55 -> retenu 2022-08-24 (720,00), table : 2024-09-30 (1080,00)
    # Le rapprochement etait une COINCIDENCE de montant, pas une identification.
    # Le BOC divise par le DERNIER dividende paye : la coincidence ne vaut donc
    # que sur le versement le plus recent de la table. Si c'est un autre qui
    # colle, la reference nous echappe et on ne conclut pas -- exactement le
    # traitement deja reserve a NEIC et STBC, dont la table a un trou.
    if auj is not None and cours and dy:
        implicite = cours * dy
        d_proche = max(par_date)
        ecart = abs(par_date[d_proche] - implicite) / implicite
        age = (auj - d_proche).days / 365.25
        if ecart <= sp["distribution_tolerance_implicite"] and age > sp["distribution_age_max_ans"]:
            return True, ("le rendement du BOC repose sur un dividende de %.2f FCFA verse le "
                          "%s, soit %.1f ans avant le cours (dividende implicite du BOC : "
                          "%.2f) : il ne decrit plus une distribution en cours"
                          % (par_date[d_proche], d_proche.isoformat(), age, implicite))

    # --- Regle 2 : le dernier versement est-il hors norme ? ---------------------
    ref_date = max(par_date)
    ref_montant = par_date[ref_date]
    avant = [m for d, m in par_date.items() if d < ref_date]
    if len(avant) >= sp["distribution_historique_min"]:
        plus_fort = max(avant)
        if ref_montant > sp["distribution_ratio_max"] * plus_fort:
            return True, ("dividende de %.2f FCFA le %s, soit %.1f fois le plus fort des %d "
                          "versements precedents (%.2f) : distribution exceptionnelle, "
                          "non reproductible" % (ref_montant, ref_date.isoformat(),
                                                 ref_montant / plus_fort, len(avant), plus_fort))
    return False, None


def ingredients(cur, ticker, seuils, sp, sp_part_min=0.50,
                sp_age_max_cp=3, arb=None):
    table, col = source_cours(cur)
    # C3 (09/10/2026) : `cours` est lu SUR LA MEME LIGNE que le PER, donc a la
    # seance `date_cours` que profils.json publie deja. C'est le prix auquel le
    # verdict est rendu. Le `cours_row` plus bas, lui, exige un rendement non
    # nul : il sert au diagnostic de distribution, pas au journal — BBGC, sans
    # rendement BOC, y rendrait une case vide avec un PER renseigne.
    per_row = cur.execute(
        f"SELECT per, {col}, cours FROM {table} WHERE ticker=? AND per IS NOT NULL "
        f"ORDER BY {col} DESC LIMIT 1", (ticker,)).fetchone()
    dy_row = cur.execute(
        f"SELECT rendement FROM {table} WHERE ticker=? AND rendement IS NOT NULL "
        f"ORDER BY {col} DESC LIMIT 1", (ticker,)).fetchone()
    date_cours = per_row[1] if per_row else None
    etats = cur.execute(
        "SELECT exercice, resultat_net, capitaux_propres, payout_ratio FROM etats_financiers "
        "WHERE ticker=? ORDER BY exercice DESC", (ticker,)).fetchall()

    per = per_row[0] if per_row else None
    dy = dy_row[0] if dy_row else None  # fraction (0,056 = 5,6 %)

    # PER D'ANALYSE (02/10/2026, decision de Claudia en conversation) : toute
    # analyse qui lit un PER lit le PER GLISSANT (12 mois) quand il existe, et le
    # PER du BOC a defaut. Le PER du BOC reste la valeur PUBLIEE et AFFICHEE en
    # premier ("per_boc", et "per" dans profils.json pour les consommateurs
    # existants). Le glissant porte deja ses gardes (paliers du BPA implicite
    # verifies, fenetre sans recouvrement) : quand il est refuse, rien ne change.
    # SEULE EXCEPTION, deliberee : le payout implicite ci-dessous reste calcule
    # sur le PER du BOC. C'est une identite sur UN exercice (dividende de
    # l'exercice / BPA du meme exercice) ; le BPA glissant ne correspond a aucun
    # dividende verse, et le melanger fausserait le ratio au lieu de l'actualiser.
    per_boc = per
    per_ttm, ttm_detail, ttm_motif = per_glissant(cur, ticker, per_boc)
    per = per_ttm if per_ttm is not None else per_boc
    per_source = "GLISSANT" if per_ttm is not None else ("BOC" if per_boc else None)

    roe, roe_exercice = None, None
    for exercice, rn, cp, _payout in etats:
        if rn is not None and cp:
            roe, roe_exercice = 100.0 * rn / cp, exercice
            break
    # Drapeau DONNEES_PERIMEES (18/09/2026) : un ROE se calcule sur des capitaux
    # propres. Si ceux-ci datent de plusieurs annees, le ratio n'a plus de sens
    # et induit en erreur d'autant plus qu'il s'affiche sans date. Cas mesure :
    # SGBC affichait un ROE de 22,1 % calcule sur des capitaux propres de 2021 —
    # peri me de cinq ans, alors que son resultat net a progresse de 50 % depuis.
    # On masque plutot que de publier un chiffre faux.
    annee_courante = date.today().year
    roe_perime = (roe_exercice is not None
                  and (annee_courante - roe_exercice) > sp_age_max_cp)
    roe_source = "ETATS_FINANCIERS" if roe is not None else None
    if roe_perime:
        roe = None
    # Repli du 27/09/2026 : 19 titres sur 47 n'avaient AUCUN ROE, faute de
    # capitaux propres en base. La chaine pipeline/ en tient 25, chacun avec son
    # millesime et l'URL du rapport de notation dont il est tire. On les utilise
    # quand la base n'a rien — jamais pour ECRASER une valeur certifiee — et la
    # meme regle de peremption s'applique : des fonds propres de plus de trois
    # ans ne donnent pas un ROE lisible, d'ou qu'ils viennent.
    agr_titre = (arb or {}).get("agregateur") or {}
    if roe is None and agr_titre.get("capitaux_propres"):
        ex_cp = agr_titre.get("exercice_cp")
        rn_agr = agr_titre.get("rn")
        perime = ex_cp is not None and (annee_courante - ex_cp) > sp_age_max_cp
        if rn_agr and not perime:
            roe = 100.0 * rn_agr / agr_titre["capitaux_propres"]
            roe_exercice = ex_cp
            roe_source = "AGREGATEUR"
            roe_perime = False
    payout, payout_source = None, None
    for _e, _rn, _cp, p in etats:
        if p is not None:
            payout, payout_source = p, "ETATS_FINANCIERS"
            break
    if payout is None and per_boc and dy is not None:
        # Identite comptable : DPA/BPA = (DPA/cours) x (cours/BPA) = rendement x PER.
        # CHANTIER OUVERT (31/07/2026) : la convention brut/net du champ rendement
        # du BOC n'est PAS tranchee. Test sur 11 titres a payout certifie :
        # 8 se comportent comme BRUT (CBIBF 0,440 vs 0,440 ; SDSC 0,237 vs 0,238 ;
        # SGBC 0,505 vs 0,513), 3 comme NET (dont ORAC : 800 F brut sur 16 000 =
        # 5,0 %, alors que le BOC affiche 4,40 % = exactement le net personnes
        # physiques). Tant que ce n'est pas tranche, le payout implicite est
        # affiche avec sa source et n'est jamais promu au rang de donnee certifiee.
        payout, payout_source = dy * per_boc, "IMPLICITE(rendement x PER)"

    # Drapeau RESULTAT_NON_OPERATIONNEL (06/08/2026, jurisprudence AGL CI) : quand le
    # resultat net provient majoritairement du financier ou de l'exceptionnel, une
    # croissance du RN ne mesure PAS la dynamique du metier. AGL CI 2024 : resultat
    # d'exploitation 941,675 M pour un RN de 21068,974 M (4,5 %) -> le profil GARP
    # etait construit sur des produits financiers, et s'est effondre de 96 % en 2025.
    # Contre-exemple SPHC 2025 : resultat d'exploitation 38130 M pour un RN de
    # 24972 M -> croissance pleinement operationnelle, le drapeau ne se declenche pas.
    # La colonne peut ne pas exister encore : absence = drapeau non evaluable, jamais
    # un faux negatif silencieux.
    part_operationnelle = None
    try:
        ligne = cur.execute(
            "SELECT resultat_exploitation, resultat_net FROM etats_financiers "
            "WHERE ticker=? AND resultat_exploitation IS NOT NULL AND resultat_net IS NOT NULL "
            "ORDER BY exercice DESC LIMIT 1", (ticker,)).fetchone()
        if ligne and ligne[1]:
            part_operationnelle = ligne[0] / ligne[1]
    except Exception:
        part_operationnelle = None

    rn_dispo = [(e, rn) for e, rn, _c, _p in etats if rn is not None]
    dernier_rn = rn_dispo[0][1] if rn_dispo else None

    arb = arb or {}
    g, statut_g, n_ex, drapeaux = croissance_rn(
        cur, ticker, sp["fenetre_exercices_max"], sp["pic_yoy_max"],
        sp["base_ecrasee_min"], sp["croissance_cap"],
        sp["base_gonflee_max"], sp["fenetre_exercices_etendue"],
        correctifs=arb.get("correctif") or None)
    if g is not None:
        source_g = "RN_%s(%dex)" % (statut_g, n_ex)
    else:
        g, drapeaux = croissance_bpa_implicite(
            cur, ticker, sp["bpa_implicite_annees"], sp["croissance_cap"])
        source_g = "BPA_IMPLICITE" if g is not None else "AUCUNE"
        # Controle de coherence : meme trop courte pour servir de source, une serie
        # de RN peut CONTREDIRE le BPA implicite. Cas mesure SIBC : RN 2024->2025
        # en hausse de 10,7 %, BPA implicite a -11,5 %/an. On ne peut pas trancher
        # (2 exercices < 3), mais on ne peut pas non plus se taire.
        # serie enrichie du comparatif N-1 (sinon SIBC, dont le RN 2024 vit dans le
        # comparatif de la ligne 2025, echappe au controle)
        enrichie = {}
        for ex, rn, rn1 in cur.execute(
                "SELECT exercice, resultat_net, resultat_net_n1 FROM etats_financiers "
                "WHERE ticker=? ORDER BY exercice", (ticker,)):
            if rn1 is not None and (ex - 1) not in enrichie:
                enrichie[ex - 1] = rn1
            if rn is not None:
                enrichie[ex] = rn
        rn_dispo_ord = sorted(enrichie.items())
        if g is not None and len(rn_dispo_ord) >= 2:
            recents = sorted(rn_dispo_ord)[-2:]
            if recents[0][1] > 0 and recents[1][1] > 0:
                g_rn_court = recents[1][1] / recents[0][1] - 1
                if g_rn_court * g < 0 and abs(g_rn_court) > 0.05:
                    drapeaux = drapeaux + ["CONTRADICTION_RN_BPA"]
        if g is not None and not rn_dispo_ord:
            drapeaux = drapeaux + ["AUCUN_RN_EN_BASE"]

    if g is not None and g > sp["rattrapage_min"] and "RATTRAPAGE" not in drapeaux:
        drapeaux = drapeaux + ["RATTRAPAGE"]

    # --- Arbitrage contre une source exterieure (26/09/2026, moteur/arbitrage.py).
    # Les tests existants verifient la coherence INTERNE de la base ; une base peut
    # etre coherente avec elle-meme et fausse. Cas fondateurs : ECOC et BOAS, dont
    # les colonnes resultat_net / resultat_net_n1 etaient permutees a la saisie,
    # ce qui produisait un profil GARP et un profil VALUE sur des series inversees.
    if arb.get("drapeau") and arb["drapeau"] not in drapeaux:
        drapeaux = drapeaux + [arb["drapeau"]]
    if arb.get("axe_retire"):
        # On retire l'axe plutot que de profiler sur un chiffre contested : g=None
        # exclut aussi le titre des pools de percentiles, donc il ne deplace plus
        # les medianes des autres.
        g, source_g = None, "ARBITRAGE_BLOQUANT"

    peg = per / (g * 100) if (per and g and g > 0) else None
    cours_row = cur.execute(
        f"SELECT cours FROM {table} WHERE ticker=? AND rendement IS NOT NULL "
        f"AND cours IS NOT NULL ORDER BY {col} DESC LIMIT 1", (ticker,)).fetchone()
    non_rec, detail_dist = diagnostic_distribution(
        cur, ticker, date_cours, sp, cours_row[0] if cours_row else None, dy)
    dy_axe = None if non_rec else dy   # rendement RECURRENT : celui de la prime et des classements
    base_pegy = (g + (dy or 0)) * 100 if g is not None else None
    pegy = per / base_pegy if (per and base_pegy and base_pegy > 0) else None

    if part_operationnelle is not None and part_operationnelle < sp_part_min:
        drapeaux = drapeaux + ["RESULTAT_NON_OPERATIONNEL"]

    # C23, 02/10/2026 : per_normalise() et le drapeau BENEFICE_NON_REPRESENTATIF
    # sont RETIRES. Voir le bloc « Pourquoi le PER normalise n'existe plus » en
    # bas de ce fichier.
    if roe_perime:
        drapeaux = drapeaux + ["DONNEES_PERIMEES"]
    if non_rec:
        drapeaux = drapeaux + ["DISTRIBUTION_NON_RECURRENTE"]
    if roe_source == "AGREGATEUR":
        drapeaux = drapeaux + ["ROE_SOURCE_EXTERIEURE"]

    return dict(chiffre_affaires=agr_titre.get("ca"),
                marge_nette=agr_titre.get("marge_nette"),
                croissance_ca=agr_titre.get("croissance_ca"),
                reference_31_decembre=agr_titre.get("reference_31_decembre"),
                roe_source=roe_source, source_capitaux_propres=(
                    agr_titre.get("source_roe") if roe_source == "AGREGATEUR" else None),
                arbitrage_regle=arb.get("regle", 0),
                arbitrage_drapeau=arb.get("drapeau"),
                arbitrage_detail=arb.get("detail"),
                arbitrage_corroboree=bool(arb.get("corroboree")),
                arbitrage_bloquant=bool(arb.get("bloquant")),
                per=per, per_boc=per_boc, per_source=per_source,
                per_ttm=per_ttm, ttm_detail=ttm_detail, ttm_motif=ttm_motif,
                dy=100.0 * dy if dy is not None else None,
                dy_axe=100.0 * dy_axe if dy_axe is not None else None,
                distribution_non_recurrente=non_rec, distribution_detail=detail_dist,
                payout=payout,
                payout_source=payout_source, part_operationnelle=part_operationnelle,
                # C3 (09/10/2026) : le cours de la seance `date_cours`, celle du
                # PER retenu. Un profil sans son prix n'est pas verifiable apres
                # coup. Cle INTERNE : profils.json n'en porte pas, sa forme
                # etant figee par la section 20 des tests de donnees.
                cours=per_row[2] if per_row else None,
                date_cours=date_cours, table_cours=table,
                roe_exercice=roe_exercice, roe_perime=roe_perime,
                roe=roe, g=100.0 * g if g is not None else None, source_croissance=source_g,
                drapeaux=drapeaux, n_exercices=len(rn_dispo), dernier_rn=dernier_rn,
                peg=round(peg, 2) if peg else None,
                pegy=round(pegy, 2) if pegy else None)


# ----------------------------------------------------------------------
# Signature -> profil
# ----------------------------------------------------------------------


def profil_par_signature(ing, decote, croissance, sp):
    """Deduction du profil par correspondance de signature. Aucun score.
    Retourne (principal, secondaire, notes)."""
    g = ing["g"]
    dy = ing["dy"]
    payout = ing["payout"]
    pegy = ing["pegy"]
    drapeaux = ing["drapeaux"]
    notes = []

    inflexion = "INFLEXION_RECENTE" in drapeaux
    if inflexion:
        notes.append("dernier exercice en net recul : la croissance moyenne masque "
                     "un retournement en cours — profil a reexaminer a la prochaine publication")
    # SERIE_TROUEE devient BLOQUANTE (18/09/2026). Cas mesure SGBC : croissance
    # de +15,9 %/an calculee en reliant 2021 a 2025 sans les quatre exercices
    # intermediaires, alors que son premier semestre 2026 sort a +0,6 %. Une
    # croissance qui saute des annees n'est pas une tendance, c'est une
    # interpolation : elle ne peut plus fonder un profil GARP ou GROWTH.
    if "SERIE_TROUEE" in drapeaux:
        notes.append("croissance calculee sur une serie A TROUS : des exercices "
                     "manquent entre les bornes, le taux affiche relie deux points "
                     "sans les annees intermediaires")
    bloc = (inflexion
            or "SERIE_TROUEE" in drapeaux
            or "BASE_ECRASEE" in drapeaux
            or any(d.startswith("CAP_") for d in drapeaux)
            or (g is not None and g > sp["rattrapage_bloquant"] * 100))
    if "RATTRAPAGE" in drapeaux and not bloc:
        notes.append("croissance de rattrapage — non extrapolable")
    if bloc:
        notes.append("croissance non exploitable (rattrapage extreme ou base ecrasee)")

    payout_ok = payout is None or payout <= sp["payout_max"]

    garp = (g is not None and sp["garp_g_min"] * 100 <= g <= sp["garp_g_max"] * 100
            and pegy is not None and pegy <= sp["garp_pegy_max"]
            and payout_ok and not bloc)
    growth = (croissance is not None and croissance >= sp["growth_pctl_min"]
              and g is not None and g > sp["growth_g_min"] * 100 and not bloc)
    value = (decote is not None and decote >= sp["value_pctl_min"]
             and payout_ok
             and (g is None or g > -sp["contraction_seuil"] * 100))
    rendement = (dy is not None and dy >= sp["rendement_dy_min"] * 100
                 and payout_ok
                 and g is not None and abs(g) < sp["garp_g_min"] * 100)
    if payout is None and (value or rendement):
        notes.append("soutenabilite du dividende non verifiable (payout non disponible)")

    if g is not None and g < -sp["contraction_seuil"] * 100 and not value:
        return "VIGILANCE_CONTRACTION", None, notes

    ordre = [("GARP", garp), ("GROWTH", growth), ("VALUE", value), ("RENDEMENT", rendement)]
    retenus = [nom for nom, ok in ordre if ok]
    if not retenus:
        return "AUCUN_PROFIL", None, notes
    return retenus[0], (retenus[1] if len(retenus) > 1 else None), notes


def tendance_intermediaire(cur, ticker):
    """Derniere publication trimestrielle ou semestrielle, et ce qu'elle dit de
    l'exercice EN COURS.

    Ajout du 18/09/2026, apres deux constats simultanes qui invalidaient les deux
    profils bancaires les mieux notes du tableau de bord :
      SGBC — profil a +15,9 %/an, premier semestre 2026 a +0,6 %.
      BOAC — croissance certifiee de +21 %/an sur 2022-2025, premier trimestre
             2026 a +0,91 %, avec un cout du risque multiplie par 4,2 et un
             resultat brut d'exploitation en recul de 1,1 %.
    Le profilage lisait des exercices CLOS, donc le passe, et presentait comme
    croissance ce qui avait cesse de croitre. Ces chiffres non audites ne
    calculent aucun profil : ils le CONTREDISENT quand l'ecart est net.

    Retourne (variation, periode, exercice, note, contredit) ou (None, ...).
    """
    try:
        ligne = cur.execute(
            "SELECT exercice, periode, resultat_net, resultat_net_n1, note "
            "FROM resultats_intermediaires WHERE ticker=? AND resultat_net IS NOT NULL "
            "AND resultat_net_n1 IS NOT NULL "
            "ORDER BY exercice DESC, periode DESC LIMIT 1", (ticker,)).fetchone()
    except Exception:
        return None, None, None, None
    if not ligne or not ligne[3]:
        return None, None, None, None
    exercice, periode, rn, rn1, note = ligne
    return (rn / rn1 - 1), periode, exercice, note


# Familles de periodes acceptees pour le cumul glissant. Un exercice doit etre
# couvert par UNE SEULE famille : melanger des trimestres et un semestre
# compterait deux fois les memes mois (S1 vaut T1+T2). Rang = nombre de periodes
# couvertes depuis le debut de l'exercice.
PERIODES_TTM = {"T1": ("T", 1), "T2": ("T", 2), "T3": ("T", 3), "T4": ("T", 4),
                "S1": ("S", 2), "S2": ("S", 4), "9M": ("M", 3)}


def benefice_glissant(cur, ticker):
    """Resultat net sur DOUZE MOIS GLISSANTS (TTM), ou None avec son motif.

    TTM = resultat du dernier exercice CLOS
          + cumul des periodes intermediaires de l'exercice EN COURS
          - cumul des MEMES periodes de l'exercice precedent.

    La soustraction est ce qui fait la fenetre glissante : elle retire du dernier
    exercice clos les mois que l'exercice en cours a deja remplaces. Elle est
    possible parce que resultats_intermediaires porte resultat_net_n1, la meme
    periode un an plus tot, lue dans le document lui-meme -- jamais reconstruite.

    CE QUI EST REFUSE, et pourquoi (une case vide vaut mieux qu'une valeur
    approchee) :
      - une periode sans son comparatif N-1 : la soustraction serait inventee ;
      - un exercice couvert par deux familles de periodes (T1, T2 et S1) :
        S1 vaut T1+T2, les compter ensemble double un semestre ;
      - des periodes non consecutives depuis le debut de l'exercice (T1 absent,
        T3 present) : le cumul sauterait des mois sans le dire ;
      - un exercice intermediaire qui ne suit pas immediatement l'exercice clos
        de reference ;
      - un resultat glissant negatif ou nul : aucun PER n'a de sens dessus.

    Retourne (rn_ttm, rn_annuel, exercice_annuel, libelle_periodes, motif_refus).
    """
    lignes = cur.execute(
        "SELECT exercice, periode, resultat_net, resultat_net_n1 "
        "FROM resultats_intermediaires WHERE ticker=? AND resultat_net IS NOT NULL "
        "ORDER BY exercice DESC", (ticker,)).fetchall()
    if not lignes:
        return None, None, None, None, "aucune publication intermediaire en base"
    exercice = max(x[0] for x in lignes)
    courantes = [x for x in lignes if x[0] == exercice]

    inconnues = sorted({p for _e, p, _rn, _n1 in courantes if p not in PERIODES_TTM})
    if inconnues:
        return None, None, None, None, f"periode(s) non reconnue(s) : {inconnues}"
    familles = {PERIODES_TTM[p][0] for _e, p, _rn, _n1 in courantes}
    if len(familles) > 1:
        return None, None, None, None, (
            "deux familles de periodes sur le meme exercice (%s) : un semestre "
            "recouvre deux trimestres, les cumuler les compterait deux fois"
            % ", ".join(sorted(p for _e, p, _rn, _n1 in courantes)))
    manquants = [p for _e, p, _rn, n1 in courantes if n1 is None]
    if manquants:
        return None, None, None, None, (
            "periode(s) sans comparatif N-1 : %s — la soustraction serait inventee"
            % ", ".join(sorted(manquants)))

    # Le cumul doit partir du DEBUT de l'exercice, sans trou. Les lignes
    # trimestrielles portent un trimestre chacune et doivent donc paver T1..Tk ;
    # une ligne semestrielle ou de neuf mois porte deja le cumul, donc elle doit
    # etre seule, et commencer a l'ouverture de l'exercice (S1, 9M — jamais S2).
    famille = familles.pop()
    periodes = sorted((p for _e, p, _rn, _n1 in courantes),
                      key=lambda p: PERIODES_TTM[p][1])
    if famille == "T":
        depart_ok = [PERIODES_TTM[p][1] for p in periodes] == list(
            range(1, len(periodes) + 1))
    else:
        depart_ok = len(periodes) == 1 and periodes[0] in ("S1", "9M")
    if not depart_ok:
        return None, None, None, None, (
            "le cumul ne part pas du debut de l'exercice, ou saute une periode (%s)"
            % ", ".join(periodes))

    annuel = cur.execute(
        "SELECT exercice, resultat_net FROM etats_financiers WHERE ticker=? "
        "AND resultat_net IS NOT NULL ORDER BY exercice DESC LIMIT 1", (ticker,)).fetchone()
    if not annuel:
        return None, None, None, None, "aucun exercice annuel en base"
    ex_annuel, rn_annuel = annuel
    if ex_annuel != exercice - 1:
        return None, None, None, None, (
            "le dernier exercice clos en base est %d, l'intermediaire porte sur %d : "
            "ils ne se suivent pas" % (ex_annuel, exercice))

    cumul = sum(x[2] for x in courantes)
    cumul_n1 = sum(x[3] for x in courantes)
    rn_ttm = rn_annuel + cumul - cumul_n1
    if rn_ttm <= 0:
        return None, None, None, None, (
            "resultat glissant negatif ou nul (%.0f) : aucun PER n'a de sens dessus"
            % rn_ttm)
    return rn_ttm, rn_annuel, ex_annuel, f"{'+'.join(periodes)} {exercice}", None


def boc_divise_par_notre_resultat(cur, ticker, ex_annuel, tolerance=0.02):
    """Le PER publie par le BOC repose-t-il bien sur NOTRE dernier resultat annuel ?

    POURQUOI CETTE VERIFICATION EXISTE. Le PER glissant se calcule en rapport :
    PER_TTM = PER_affiche x (RN_annuel / RN_TTM). Le nombre d'actions s'annule,
    ce qui evite de l'estimer -- mais l'egalite n'est vraie QUE si le PER du BOC
    divise par le MEME resultat annuel que celui de notre base. Si le bulletin
    est reste sur l'exercice precedent, ou s'il retient un resultat different du
    notre, le rapport est faux et le PER glissant serait un nombre invente.
    C'est exactement l'erreur que le chantier C23 a fait payer au PER normalise :
    une formule juste appliquee a un denominateur non verifie.

    METHODE, sans estimer le nombre d'actions. Le benefice par action implicite
    du bulletin, cours / PER, forme des PALIERS : il ne bouge qu'a la publication
    d'un resultat annuel. Si le BOC suit notre serie, le rapport entre les deux
    derniers paliers doit egaler le rapport de nos deux derniers resultats
    annuels. Verifie sur BOAC le 02/10/2026 : paliers 801,08 -> 888,52, soit
    1,1091, contre RN 2025/2024 = 35540/32044 = 1,1091. Ecart 0,00 %.

    Retourne (True/False, detail).
    """
    precedent = cur.execute(
        "SELECT resultat_net FROM etats_financiers WHERE ticker=? AND exercice=? "
        "AND resultat_net IS NOT NULL", (ticker, ex_annuel - 1)).fetchone()
    courant = cur.execute(
        "SELECT resultat_net FROM etats_financiers WHERE ticker=? AND exercice=? "
        "AND resultat_net IS NOT NULL", (ticker, ex_annuel)).fetchone()
    if not precedent or not courant or precedent[0] <= 0 or courant[0] <= 0:
        return False, ("les exercices %d et %d ne sont pas tous deux en base : le "
                       "rapport des paliers n'a rien a confronter"
                       % (ex_annuel - 1, ex_annuel))

    table, col = source_cours(cur)
    seances = cur.execute(
        f"SELECT {col}, cours, per FROM {table} WHERE ticker=? AND per IS NOT NULL "
        f"AND per > 0 AND cours IS NOT NULL AND cours > 0 ORDER BY {col}",
        (ticker,)).fetchall()
    paliers = []
    for _d, cours, per in seances:
        bpa = cours / per
        if paliers and abs(bpa - paliers[-1][0]) / paliers[-1][0] < tolerance:
            paliers[-1][0] = (paliers[-1][0] * paliers[-1][1] + bpa) / (paliers[-1][1] + 1)
            paliers[-1][1] += 1
        else:
            paliers.append([bpa, 1])
    paliers = [p for p in paliers if p[1] >= 5]  # un palier d'une seance est du bruit
    if len(paliers) < 2:
        return False, ("moins de deux paliers de BPA implicite dans la serie : rien "
                       "a confronter")
    observe = paliers[-1][0] / paliers[-2][0]
    attendu = courant[0] / precedent[0]
    ecart = abs(observe / attendu - 1)
    if ecart > tolerance:
        return False, ("le BOC ne suit pas notre serie : dernier saut du BPA "
                       "implicite x%.4f, rapport RN %d/%d x%.4f, ecart %.1f %%"
                       % (observe, ex_annuel, ex_annuel - 1, attendu, ecart * 100))
    return True, ("saut du BPA implicite x%.4f contre rapport RN %d/%d x%.4f, "
                  "ecart %.2f %%" % (observe, ex_annuel, ex_annuel - 1, attendu,
                                     ecart * 100))


def per_glissant(cur, ticker, per):
    """PER sur douze mois glissants. Retourne (per_ttm, detail, motif_refus).

    PER_TTM = PER_affiche x (RN_annuel / RN_TTM). Le nombre d'actions s'annule :
    inutile de l'estimer, a condition que le PER affiche repose bien sur
    RN_annuel -- ce que boc_divise_par_notre_resultat() verifie, et sans quoi on
    ne calcule rien.
    """
    if not per or per <= 0:
        return None, None, "aucun PER publie par le bulletin"
    rn_ttm, rn_annuel, ex_annuel, periodes, motif = benefice_glissant(cur, ticker)
    if rn_ttm is None:
        return None, None, motif
    ok, detail_boc = boc_divise_par_notre_resultat(cur, ticker, ex_annuel)
    if not ok:
        return None, None, detail_boc
    valeur = per * rn_annuel / rn_ttm
    detail = ("%s : resultat glissant %.0f M contre %.0f M pour l'exercice %d "
              "(%+.1f %%). Reference verifiee — %s."
              % (periodes, rn_ttm, rn_annuel, ex_annuel,
                 (rn_ttm / rn_annuel - 1) * 100, detail_boc))
    return valeur, detail, None


# ----------------------------------------------------------------------
# POURQUOI LE PER NORMALISE N'EXISTE PLUS — chantier C23, retire le 02/10/2026
# ----------------------------------------------------------------------
# Il a vecu du 12/09 au 02/10/2026. Il rendait PER x (dernier benefice / moyenne
# des quatre derniers) et se presentait comme une correction de PIC : "si ce
# benefice est un pic, le PER parait bas alors que le titre est cher".
#
# CE QU'IL MESURAIT REELLEMENT, mesure le 01/10/2026 apres un signalement de
# Claudia sur le tableau de bord publie : la CROISSANCE. Sur une serie
# geometrique de taux g, le dernier terme depasse la moyenne de quatre termes
# d'environ 1,5 g, sans qu'il y ait le moindre pic. Sur les huit titres a serie
# strictement croissante -- ou un pic est impossible par construction -- il
# gonflait le PER de 12 a 119 %, et le gonflement suivait g :
#
#     titre  serie des RN                            PER -> PERn   ratio   g %/an
#     NSBC   32382 34813 38112 40712                13,1 -> 14,6    1,12      7,9
#     SNTS   278912 331748 393662 413588            10,9 -> 12,7    1,17     14,0
#     CABC   796 1135 1375 1439                     14,0 -> 16,9    1,21     21,9
#     BOAC   20069 26075 32044 35540                12,9 -> 16,2    1,25     21,0
#     SHEC   3549 4012 5354 6028                    24,7 -> 31,4    1,27     19,3
#
# Deux defauts de SELECTION ont ete corriges le 01/10 avant de conclure, pour ne
# pas accuser la formule de ce qui venait de la fenetre : elle n'etait pas
# consecutive (6 titres sur 25 enjambaient un trou, SICC n'avait aucun exercice
# posterieur a 2021) et le filtre resultat_net > 0 ecartait 17 exercices
# deficitaires en faisant paraitre le titre MOINS cher. Corriges, le defaut de
# fond est reste entier : c'est bien la lecture du rapport qui est fausse.
#
# TROIS LECTURES ONT ETE MESUREES, et Claudia a tranche le 02/10 :
#   (a) garder la moyenne -- c'est un CAPE a quatre ans, dont penaliser la
#       croissance est une critique connue ; mais aux taux de croissance de la
#       BRVM la penalite de croissance domine le signal de pic ;
#   (b) normaliser sur la TENDANCE (regression log-lineaire) -- ramene les
#       titres monotones a 0,93-1,02, mais sur un effondrement recent la
#       regression extrapole l'ancienne pente et rendrait 327 pour SICC,
#       875 pour BNBC ;
#   (c) RETRAIT DEFINITIF. Retenu.
#
# CE QUI EST PARTI AVEC : le drapeau BENEFICE_NON_REPRESENTATIF, qui se
# declenchait sur le MEME rapport (ecart > ecart_benefice_max) et portait donc
# le meme defaut -- il retenait BICC et SLBC, qui croissent sans pic. Son texte
# avait deja ete ampute le 02/10 de sa conclusion sur la cherte, ce qui ne
# laissait qu'un constat sans portee.
#
# NE PAS LE RECONSTRUIRE SOUS UN AUTRE NOM sans resoudre d'abord ce que ni (a)
# ni (b) ne resolvent : distinguer un pic d'une croissance reguliere sur trois
# ou quatre points, quand un effondrement recent et une serie qui monte donnent
# le meme rapport a la moyenne. La section 7 de tester_donnees.py tient un
# controle qui echoue si la mesure revient.



def motif_du_profil(profil, ing, decote, croissance, sp):
    """Phrase en clair : pourquoi CE profil, ou pourquoi aucun.
    Repond au constat d'usage : 'AUCUN PROFIL' sans motif est illisible, alors
    qu'il recouvre au moins cinq causes distinctes (croissance artefactuelle,
    croissance sous la fenetre, croissance deja payee, distribution non
    couverte, croissance non calculable)."""
    g, dy, payout, pegy = ing["g"], ing["dy"], ing["payout"], ing["pegy"]
    dra = ing["drapeaux"]
    gmin, gmax = sp["garp_g_min"] * 100, sp["garp_g_max"] * 100

    if profil == "GARP":
        return ("croissance de %.1f %%/an dans la fenetre soutenable (%.0f-%.0f %%), "
                "payee PEGY %.2f — la croissance n'est pas encore dans le prix"
                % (g, gmin, gmax, pegy))
    if profil == "GROWTH":
        return "croissance de %.1f %%/an dans le tercile superieur (P%s), reguliere" % (
            g, croissance)
    if profil == "VALUE":
        return ("decote marquee (rang P%s sur l'axe decote) sur des benefices "
                "etablis%s — "
                "l'histoire est la revalorisation, pas l'expansion"
                % (decote, "" if g is None else ", croissance de %.1f %%/an" % g))
    if profil == "RENDEMENT":
        return ("rendement de %.1f %% avec une distribution couverte (payout %.0f %%) "
                "et une croissance quasi nulle (%.1f %%/an) : profil de revenu"
                % (dy, (payout or 0) * 100, g))
    if profil == "VIGILANCE_CONTRACTION":
        return ("benefices en contraction de %.1f %%/an sans decote suffisante "
                "pour la compenser" % g)
    if profil == "RETOURNEMENT":
        return "pertes ou sortie de pertes avec catalyseur documente — hors perimetre du profilage"
    if profil == "MUTATION":
        return "la nature economique de la societe a change : l'historique n'est plus predictif"
    if profil == "NON_ANALYSABLE":
        # Cas d'une INTRODUCTION RECENTE (24/09/2026, prepare pour Bridge Bank
        # Group CI) : une societe peut arriver sur la cote avec des comptes
        # certifies impeccables et n'etre pas profilable pour une seule raison —
        # la BRVM ne publie pas encore son PER, faute d'historique de cotation.
        # Dire "donnees insuffisantes" serait injuste et trompeur : ce qui manque
        # est le PRIX, pas les comptes.
        if ing.get("source_croissance", "").startswith("RN_") and g is not None:
            return ("comptes solides (croissance de %.1f %%/an sur exercices "
                    "certifies) mais PER non encore publie par la BRVM : le titre "
                    "sera profilable des que sa valorisation sera etablie" % g)
        return "donnees insuffisantes pour etablir un profil (PER absent ou benefices residuels)"

    # --- AUCUN_PROFIL : identifier la cause reelle ---
    if g is None:
        return ("croissance non calculable (historique trop court ou series absentes) : "
                "l'axe croissance manque, ce n'est pas un diagnostic mais une lacune")
    if "BASE_ECRASEE" in dra or any(d.startswith("CAP_") for d in dra) or g > sp["rattrapage_bloquant"] * 100:
        return ("croissance de %.1f %%/an issue d'un rattrapage depuis un creux : "
                "non extrapolable, et decote insuffisante par ailleurs (rang P%s)"
                % (g, decote))
    if payout is not None and payout > sp["payout_max"]:
        return ("distribution non couverte (payout %.0f %%) : le rendement de %.1f %% "
                "ne qualifie pas un profil de revenu" % (payout * 100, dy or 0))
    if gmin <= g <= gmax and pegy is not None and pegy > sp["garp_pegy_max"]:
        return ("croissance reelle de %.1f %%/an mais deja payee (PEGY %.2f, au-dela "
                "de %.1f)" % (g, pegy, sp["garp_pegy_max"]))
    if 0 < g < gmin:
        ecart = gmin - g
        proximite = (" — a %.1f point de la fenetre, a revoir a la prochaine publication"
                     % ecart) if ecart <= 1.5 else ""
        return ("croissance de %.1f %%/an sous la fenetre GARP (%.0f %%)%s, sans decote "
                "(rang de decote P%s) ni rendement distinctifs"
                % (g, gmin, proximite, decote))
    return ("ni decote (rang P%s), ni croissance dans le tercile superieur (P%s), "
            "ni rendement superieur : coeur de cote correctement paye"
            % (decote, croissance))


def sensible_brut_net(profil, ing, sp):
    """Le profil bascule-t-il selon la convention brut/net du rendement ?
    Chantier non tranche : 8 titres se comportent comme BRUT, 3 comme NET."""
    dy = ing["dy"]
    if dy is None:
        return False
    seuil = sp["rendement_dy_min"] * 100
    return bool(dy < seuil <= dy / 0.88)


def _drapeaux_de_croissance(ing):
    """Drapeaux qui pesent sur la fiabilite de la CROISSANCE, seule chose que le
    grade note. DISTRIBUTION_NON_RECURRENTE (C1) parle du rendement du dividende :
    l'y compter ferait passer NTLC et SMBC du grade A au B, un verdict deplace par
    un drapeau qui ne concerne pas l'axe note (mesure du 30/09/2026)."""
    return set(ing["drapeaux"]) - {"DISTRIBUTION_NON_RECURRENTE"}


def grade_confiance(profil, ing, faits_titre):
    """A = exploitable tel quel | B = solide avec reserve nommee | C = travail requis."""
    reserves = []
    source = ing["source_croissance"]
    if source == "BPA_IMPLICITE":
        reserves.append("croissance issue du BPA implicite (source BOC circulaire, "
                        "validation croisee faite sur NSBC uniquement)")
    if source == "AUCUNE":
        reserves.append("aucune source de croissance exploitable")
    EXPLICATIONS = {
        "CONTRADICTION_RN_BPA": "les resultats nets en base et le BPA implicite evoluent "
                                "en sens OPPOSE — la croissance affichee n'est pas fiable, "
                                "trancher avant tout usage",
        "AUCUN_RN_EN_BASE": "aucun resultat net transcrit : la croissance repose "
                            "integralement sur le BPA implicite, invérifiable en l'etat",
        "BASE_GONFLEE": "la fenetre demarre sur un exercice exceptionnellement eleve : "
                        "la contraction mesuree peut n'etre qu'un retour a la normale",
        "FENETRE_ELARGIE": "fenetre etendue au-dela de 4 exercices car elle demarrait sur "
                           "un pic — la tendance de fond remplace l'effet de base",
        "SERIE_TROUEE": "des exercices manquent entre les bornes : le taux relie deux "
                        "points sans les annees intermediaires",
        "SERIE_COMPLETEE_N1": "serie completee par le comparatif N-1 d'un document certifie",
        "CONFLIT_N1": "une ligne d'exercice contredit un comparatif N-1 — ligne retenue, "
                      "ecart a arbitrer",
        "PIC_YOY": "rupture d'echelle annuelle : serie tronquee au pic",
        "BASE_ECRASEE": "la fenetre demarre sur un creux non representatif",
        "RATTRAPAGE": "croissance de rattrapage, non extrapolable",
        "INFLEXION_RECENTE": "le dernier exercice recule de plus de 10 % : la croissance "
                             "moyenne affichee masque un retournement en cours",
        "CYCLE_SERIE_RESTAUREE": "serie certifiee restauree malgre une rupture d'echelle "
                                 "(creux de cycle) : la croissance porte sur l'ensemble du "
                                 "cycle, pas sur une phase",
        "DONNEES_PERIMEES": "les capitaux propres en base ont plus de trois ans : le ROE "
                            "n'est plus calculable de facon fiable et n'est pas affiche",
        "CONTREDIT_PAR_INTERMEDIAIRE": "la derniere publication trimestrielle ou "
                                       "semestrielle contredit la croissance annuelle "
                                       "affichee : l'exercice en cours ne suit pas la "
                                       "tendance des exercices clos",
        "ROE_SOURCE_EXTERIEURE": "les capitaux propres ne sont pas en base : le ROE est "
                                 "calcule sur ceux d'un rapport de notation, dont l'URL "
                                 "figure dans la fiche",
        "RESULTAT_NON_OPERATIONNEL": "le resultat net provient majoritairement du financier "
                                     "ou de l'exceptionnel : la croissance affichee ne mesure "
                                     "PAS la dynamique du metier (jurisprudence AGL CI)",
    }
    # Arbitrage contre une source exterieure (26/09/2026) : les libelles vivent
    # dans moteur/arbitrage.py, aux cotes des regles qui les produisent.
    EXPLICATIONS = dict(EXPLICATIONS, **EXPLICATIONS_ARBITRAGE)
    if ing.get("arbitrage_detail") and ing.get("arbitrage_regle") not in (0, 1):
        reserves.append("ARBITRAGE : %s" % ing["arbitrage_detail"])
    for d in ing["drapeaux"]:
        base = d.split("_")[0] if d.startswith("CAP_") else d
        if base in EXPLICATIONS:
            reserves.append("%s : %s" % (d, EXPLICATIONS[base]))
        elif d.startswith("CAP_"):
            reserves.append("%s : croissance plafonnee" % d)
    if ing.get("distribution_non_recurrente"):
        reserves.append("DISTRIBUTION_NON_RECURRENTE : %s" % ing["distribution_detail"])
    if ing["payout"] is None:
        reserves.append("payout non disponible — soutenabilite du dividende non verifiee")
    if ing["payout"] is not None and ing["payout"] > 1.0:
        reserves.append("payout > 100 % — distribution non couverte ou decalage de donnees")
    reserves.append("croissance du resultat net TOTAL, non ajustee des operations sur capital")

    if profil in ("RETOURNEMENT", "MUTATION"):
        reserves.insert(0, "HORS PERIMETRE du profilage — releve de l'outil de pari (a construire)")
        return ("B" if faits_titre else "C"), reserves
    if profil == "NON_ANALYSABLE":
        return "C", reserves
    critiques = {"CONTRADICTION_RN_BPA", "AUCUN_RN_EN_BASE", "BASE_GONFLEE", "CONFLIT_N1",
                 "RESULTAT_NON_OPERATIONNEL", "INFLEXION_RECENTE",
                 "DONNEES_PERIMEES", "CONTREDIT_PAR_INTERMEDIAIRE",
                 # Arbitrage (26/09/2026) : un desaccord avec une source exterieure
                 # ou un exercice manquant rendent le profil non exploitable tel quel.
                 "PERMUTATION_PROBABLE", "PERMUTATION_SUSPECTEE",
                 "CROISSANCE_CONTESTEE", "FONDAMENTAL_EN_RETARD"}
    if critiques & set(ing["drapeaux"]):
        return "C", reserves
    if profil in ("VALUE", "RENDEMENT") and ing["payout"] is None:
        return "B", reserves
    # Corroboration (regle 1, 26/09/2026) : deux lectures independantes des memes
    # comptes publies concordent. C'est la seule situation ou le grade MONTE, et
    # elle exige une ligne certifiee -- une concordance entre deux sources faibles
    # ne prouve rien de plus que leur accord. Placee APRES le controle du payout
    # pour ne jamais effacer une reserve deja etablie.
    if (ing.get("arbitrage_corroboree") and "VERIFIE" in source
            and _drapeaux_de_croissance(ing) <= {"CROISSANCE_CORROBOREE", "SERIE_COMPLETEE_N1",
                                                 "ROE_SOURCE_EXTERIEURE"}):
        return "A", reserves
    if "VERIFIE" in source and _drapeaux_de_croissance(ing) <= {"ROE_SOURCE_EXTERIEURE"}:
        return "A", reserves
    if "VERIFIE" in source or source == "RN_PROBABLE" or source.startswith("RN_"):
        return "B", reserves
    if source == "BPA_IMPLICITE":
        return "B", reserves
    return "C", reserves


# ----------------------------------------------------------------------
# Journal des predictions (chantier C3, 09/10/2026)
# ----------------------------------------------------------------------
# POURQUOI IL EXISTE. Sans lui, l'outil est un INSTANTANE : il dit ce qu'il
# pense aujourd'hui, et personne ne pourra jamais dire s'il avait raison. Le
# journal fige, a chaque passage de profils.py, ce que le moteur a conclu et le
# prix auquel il l'a conclu. C'est la seule piece qui rende le profilage
# falsifiable.
#
# CE QUI N'Y EST PAS, ET POURQUOI. Aucun jugement, aucun score agrege, aucune
# recommandation : six faits par titre, tous relus de profils.py ou de la base.
# Un journal qui interprete devient une opinion de plus a verifier.
JOURNAL = RACINE / "collecte" / "journal_profils.csv"
JOURNAL_COLONNES = ("date", "ticker", "profil", "grade", "cours",
                    "date_cours", "per", "per_analyse")


def ecrire_journal(lignes, chemin, jour, colonnes=JOURNAL_COLONNES):
    """Ajoute une ligne par titre au journal, et n'en reecrit jamais aucune.

    TROIS PROPRIETES, et la section 38 de tester_donnees.py verifie les trois
    en rejouant cette fonction, sans importer ce module.

      1. AJOUT SEUL. Le fichier s'ouvre en "a" ; l'en-tete ne s'ecrit que s'il
         est absent. Aucune ligne passee ne peut changer, meme si le moteur
         change d'avis sur un titre d'hier — c'est precisement le desaccord
         qu'on veut pouvoir lire plus tard.
      2. IDEMPOTENT PAR JOUR. profils.py tourne plusieurs fois par jour (P13,
         P12, P5b, P4, branchement). Une paire (date, ticker) deja presente
         n'est pas reecrite : relancer le meme jour n'ajoute rien.
      3. IL S'ALLONGE. Un jour neuf ajoute exactement une ligne par titre.

    `jour` est la date du PASSAGE, distincte de `date_cours`, qui est la seance
    du prix. Les deux sont inscrites : un verdict rendu le lundi sur le cours du
    vendredi n'est pas un verdict rendu le vendredi.

    Rend (ajoutees, deja_presentes).
    """
    import csv
    jour = str(jour)[:10]
    deja = set()
    non_vide = chemin.exists() and chemin.stat().st_size > 0
    if non_vide:
        with chemin.open("r", encoding="utf-8", newline="") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 2 and ligne[0] != colonnes[0]:
                    deja.add((ligne[0], ligne[1]))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ajoutees = 0
    with chemin.open("a", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f, lineterminator="\n")
        if not non_vide:
            ecrivain.writerow(colonnes)
        for ticker in sorted(lignes):
            if (jour, ticker) in deja:
                continue
            v = lignes[ticker]
            ecrivain.writerow(
                [jour, ticker]
                + ["" if v.get(c) is None else v.get(c) for c in colonnes[2:]])
            ajoutees += 1
    return ajoutees, len(lignes) - ajoutees


# ----------------------------------------------------------------------
# Calcul principal
# ----------------------------------------------------------------------


def calculer():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    seuils, marche = charger_seuils(), charger_marche()
    macro = seuils.get("macro") or {}
    taux_ref = macro.get("taux_reference")
    faits = charger_faits()
    notations = charger_notations()
    avis = charger_avis()
    agregateur = charger_agregateur()

    par_defaut = dict(
        fenetre_exercices_max=4, pic_yoy_max=3.5, base_ecrasee_min=0.30,
        croissance_cap=0.60, bpa_implicite_annees=3, rattrapage_min=0.25,
        rattrapage_bloquant=0.30, payout_max=1.0, per_max_analysable=50,
        base_gonflee_max=1.5, fenetre_exercices_etendue=8,
        part_operationnelle_min=0.50,
        age_max_capitaux_propres=3, ecart_intermediaire_max=0.08,
        n_secteur_min=8, value_pctl_min=67, growth_pctl_min=67,
        garp_g_min=0.08, garp_g_max=0.30, garp_pegy_max=1.5, growth_g_min=0.05,
        rendement_dy_min=0.048, contraction_seuil=0.10, alerte_pegy_max=0.25,
        confiance_haute_min_exercices=4, confiance_moyenne_min_exercices=2,
        distribution_ratio_max=3.0, distribution_age_max_ans=2,
        distribution_historique_min=3, distribution_tolerance_implicite=0.10)
    sp = dict(par_defaut)
    sp.update({k: v for k, v in (seuils.get("profils") or {}).items() if k in par_defaut})

    secteurs = dict(cur.execute("SELECT ticker, secteur FROM societes"))
    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]

    brut, verdicts = {}, {}
    for t in tickers:
        # un titre sans aucune cotation n'est pas encore cote (ex. IPO annoncee)
        _tbl, _c = source_cours(cur)
        cote = cur.execute(
            f"SELECT COUNT(*) FROM {_tbl} WHERE ticker=?", (t,)).fetchone()[0]
        if not cote:
            continue
        verdict = arbitrer(cur, t, agregateur) if agregateur else None
        if verdict is not None:
            # La ligne de l'agregateur voyage avec le verdict : elle porte le
            # chiffre d'affaires, la marge et les capitaux propres sources, que
            # ingredients() utilise en repli quand la base n'a rien.
            verdict["agregateur"] = (agregateur or {}).get(t) or {}
        verdicts[t] = verdict or {}
        ing = ingredients(cur, t, seuils, sp, sp["part_operationnelle_min"],
                          sp["age_max_capitaux_propres"], arb=verdict)
        statut_gate, _motifs = appliquer_gate(cur, t, secteurs.get(t, ""), seuils, marche)
        brut[t] = dict(ing, gate=statut_gate, secteur=secteurs.get(t, ""))

    # --- Perimetre analysable : PER exploitable et pas de fait qualitatif bloquant
    for t, v in brut.items():
        fait = (faits.get(t) or {}).get("profil")
        per = v["per"]
        v["analysable"] = bool(
            fait is None and per is not None and per <= sp["per_max_analysable"]
            and not v.get("arbitrage_bloquant"))
    analysables = {t: v for t, v in brut.items() if v["analysable"]}

    # --- Axes : double lecture secteur (n>=8) / marche, reference etiquetee
    ep, par_secteur, axes = bassins_et_axes(analysables, sp)

    # --- Medianes de reference (secteur et marche) pour la mise en contexte ---
    # Un PER de 14 ne dit rien seul ; "14,0 contre 13,2 en mediane bancaire et
    # 15,1 sur le marche" se lit immediatement.
    INDICS = ["per", "dy", "g", "payout", "roe"]
    med_marche = {k: _mediane([v[k] for v in analysables.values()]) for k in INDICS}
    n_marche = {k: len([1 for v in analysables.values() if v[k] is not None]) for k in INDICS}
    med_secteur, n_sect = {}, {}
    for sec in {v["secteur"] for v in analysables.values()}:
        grp = [v for v in analysables.values() if v["secteur"] == sec]
        med_secteur[sec] = {k: _mediane([v[k] for v in grp]) for k in INDICS}
        n_sect[sec] = {k: len([1 for v in grp if v[k] is not None]) for k in INDICS}

    def comparaisons(v):
        sec = v["secteur"]
        out = {}
        for k in INDICS:
            ms = (med_secteur.get(sec) or {}).get(k)
            out[k] = {
                "titre": round(v[k], 2) if v[k] is not None else None,
                "mediane_secteur": round(ms, 2) if ms is not None else None,
                "n_secteur": (n_sect.get(sec) or {}).get(k, 0),
                "mediane_marche": round(med_marche[k], 2) if med_marche[k] is not None else None,
                "n_marche": n_marche[k]}
        return out

    profils = {}
    for t, v in brut.items():
        fait = faits.get(t) or {}
        if not v["analysable"]:
            if fait.get("profil"):
                principal, secondaire, notes = fait["profil"], None, []
            elif v.get("arbitrage_bloquant"):
                principal, secondaire, notes = "NON_ANALYSABLE", None, [
                    "PROFIL SUSPENDU par arbitrage : " + (v.get("arbitrage_detail") or "")]
            elif v["per"] is None or v["per"] > sp["per_max_analysable"]:
                principal, secondaire, notes = "NON_ANALYSABLE", None, [
                    "PER absent ou > %d : benefices nuls ou residuels" % sp["per_max_analysable"]]
            else:
                principal, secondaire, notes = "NON_ANALYSABLE", None, []
            decote = croissance = None
            ref = "hors axes"
        else:
            decote, croissance, ref = axes(t, v)
            principal, secondaire, notes = profil_par_signature(v, decote, croissance, sp)

        # --- Avis officiels : suspension, fractionnement, operation sur capital ---
        avis_titre = avis.get(t, [])
        statut, date_statut, libelle_statut = statut_cotation(avis_titre)
        evenements = evenements_cotation(avis_titre)
        if statut == "NEGOCIABLE" and any(e["type"] == "SUSPENSION" for e in evenements):
            # Le titre a ete suspendu puis repris recemment : on l'annonce.
            susp = [e for e in evenements if e["type"] == "SUSPENSION"][-1]
            repr_ = [e for e in evenements if e["type"] == "REPRISE_COTATION"][-1]
            notes = notes + [
                "COTATION RETABLIE le %s, apres une suspension prononcee le %s. "
                "Le titre est de nouveau negociable. Motif de la suspension : %s"
                % (repr_["date_avis"], susp["date_avis"],
                   (susp.get("titre") or "voir l'avis BRVM"))]
        if statut == "SUSPENDU":
            # Un titre suspendu ne peut etre ni achete ni vendu : le profil
            # devient une information theorique. On le CONSERVE (l'analyse reste
            # valable pour la reprise) mais on le signale sans ambiguite.
            notes = notes + [
                "COTATION SUSPENDUE depuis le %s — le titre ne peut etre ni achete "
                "ni vendu. Le profil ci-dessous reste une lecture des comptes, pas "
                "une opportunite accessible. Motif : %s"
                % (date_statut, (libelle_statut or "voir l'avis BRVM"))]
        hist = historique_cotation(avis_titre)
        if statut == "NEGOCIABLE" and len(hist) >= 2 and hist[0]["type"] == "REPRISE_COTATION":
            susp = next((h for h in hist[1:] if h["type"] == "SUSPENSION"), None)
            if susp:
                notes = notes + [
                    "SUSPENSION LEVEE — ce titre a ete suspendu de cotation le %s puis "
                    "retabli le %s. L'episode est resolu, mais il reste une information : "
                    "une societe suspendue pour manquement a ses obligations n'est pas "
                    "dans la meme situation qu'une societe jamais inquietee. "
                    "Motif de la suspension : %s"
                    % (susp["date"], hist[0]["date"], (susp.get("titre") or "voir l'avis"))]

        alertes_avis = [a for a in avis_titre[:12]
                        if a.get("type") in ("FRACTIONNEMENT", "AUGMENTATION_CAPITAL",
                                             "RADIATION", "OPA_OPR")]
        for a in alertes_avis[:2]:
            notes = notes + [
                "AVIS BRVM du %s — %s : %s. Une operation sur le capital modifie le "
                "nombre d'actions et donc le cours de reference ; tant qu'elle n'est "
                "pas enregistree dans operations_sur_titre.csv, les series historiques "
                "de ce titre seront faussees."
                % (a.get("date_avis"), a.get("type"), (a.get("titre") or "")[:110])]

        # --- Confrontation a la derniere publication intermediaire ---
        var_int, periode_int, ex_int, note_int = tendance_intermediaire(cur, t)
        if var_int is not None and v["g"] is not None:
            ecart = (v["g"] / 100.0) - var_int
            # Un profil de croissance dement par l'exercice en cours n'est plus
            # un profil de croissance : on le signale et on plafonne le grade.
            if ecart > sp["ecart_intermediaire_max"] and v["g"] > 5:
                notes = notes + [
                    "CONTREDIT PAR L'EXERCICE EN COURS — le profil affiche une "
                    "croissance de %.1f %%/an, mais la derniere publication (%s %s) "
                    "ressort a %+.1f %%. %s"
                    % (v["g"], periode_int, ex_int, var_int * 100,
                       (note_int or "")[:220])]
                if "CONTREDIT_PAR_INTERMEDIAIRE" not in v["drapeaux"]:
                    v["drapeaux"] = v["drapeaux"] + ["CONTREDIT_PAR_INTERMEDIAIRE"]

        # PER glissant (TTM) : calcule dans ingredients() depuis le 02/10/2026,
        # parce qu'il y devient le PER d'analyse. Le PER du BOC reste la valeur
        # publiee, affichee en premier ; le motif de refus reste dans le fichier.
        per_ttm, ttm_detail, ttm_motif = v["per_ttm"], v["ttm_detail"], v["ttm_motif"]

        motif = motif_du_profil(principal, v, decote, croissance, sp)
        if v.get("arbitrage_bloquant"):
            motif = ("profil suspendu : la base est en desaccord avec une source "
                     "exterieure sur le dernier exercice (%s) — voir la note "
                     "d'arbitrage" % (v.get("arbitrage_drapeau") or "arbitrage"))
        if sensible_brut_net(principal, v, sp):
            notes = notes + [
                "profil SENSIBLE a la convention brut/net du rendement : avec un "
                "rendement brut, le seuil du profil RENDEMENT serait franchi. "
                "Chantier de verification ouvert — aucune correction appliquee."]
        # --- Confrontation a l'opinion d'une agence de notation ---
        # On ne modifie JAMAIS le profil : on signale la divergence pour que
        # l'analyste tranche. Cas fondateur ONTBF : profile
        # VIGILANCE_CONTRACTION (-13,4 %/an, BPA implicite sur 2 points) alors
        # que GCR rehaussait sa note de A(WU) a A+(WU) le 19/12/2025 en citant
        # une rentabilite solide. Les chiffres du communique (CA 142 Mds en
        # 2024 apres 139 en 2023, marge nette 15 %) donnaient un RN implicite
        # de 21,3 Mds, identique a notre base : le -13,4 % etait un artefact.
        note = notations.get(t)
        contradiction = None
        if note:
            var = note.get("variation_crans")
            var = int(var) if (var or "").lstrip("-").isdigit() else None
            # TROIS agences agreees UEMOA coexistent dans le fonds, mesure du
            # 27/09/2026 apres reprise : Bloomfield Investment Corporation
            # (243 rapports, notes nues), WARA (82, notes nues) et GCR (43,
            # notes suffixees WU). Le commentaire d'origine n'en citait que
            # deux, WARA n'etant pas encore apparue dans le fonds collecte.
            # Leurs echelles sont toutes REGIONALES et NON comparables entre
            # elles ni a une echelle internationale. On ne compare donc JAMAIS
            # deux titres notes par des agences differentes : seule la
            # VARIATION d'une revue a l'autre, chez la meme agence, est
            # exploitee — regle qui protege deja l'arrivee de WARA.
            persp = (note.get("perspective") or "").lower()
            defavorable = principal in ("VIGILANCE_CONTRACTION", "RETOURNEMENT")
            favorable = principal in ("GARP", "GROWTH")
            if defavorable and ((var is not None and var > 0) or persp == "positive"):
                contradiction = (
                    "l'agence %s %s (note %s, perspective %s, %s) alors que le "
                    "profilage conclut a une degradation — la source du profil "
                    "(%s) doit etre verifiee avant tout usage"
                    % (note.get("agence") or "de notation",
                       "a rehausse la note" if (var or 0) > 0 else "affiche une perspective positive",
                       note.get("note_lt"), persp or "n/d", note.get("date_annonce"),
                       v["source_croissance"]))
            elif favorable and ((var is not None and var < 0) or persp in ("negative", "négative")):
                contradiction = (
                    "l'agence %s %s (note %s, perspective %s, %s) alors que le "
                    "profilage conclut a une dynamique favorable"
                    % (note.get("agence") or "de notation",
                       "a abaisse la note" if (var or 0) < 0 else "affiche une perspective negative",
                       note.get("note_lt"), persp or "n/d", note.get("date_annonce")))
            if contradiction:
                notes = notes + ["CONTRADICTION_NOTATION : " + contradiction]

        grade, reserves = grade_confiance(principal, v, fait)
        if statut == "SUSPENDU" and grade == "A":
            grade = "B"
        if contradiction and grade == "A":
            grade = "B"  # une contradiction externe interdit le grade maximal
        if fait.get("note"):
            notes = notes + [fait["note"]]
        alerte_peg = bool(v["pegy"] is not None and v["pegy"] < sp["alerte_pegy_max"])
        if alerte_peg:
            notes = notes + ["PEGY < %.2f : protocole de revue obligatoire "
                             "(donnee erronee ? risque non capture ?)" % sp["alerte_pegy_max"]]

        confiance = ("HAUTE" if v["n_exercices"] >= sp["confiance_haute_min_exercices"]
                     else "MOYENNE" if v["n_exercices"] >= sp["confiance_moyenne_min_exercices"]
                     else "FAIBLE")

        profils[t] = {
            # --- compatibilite dashboard HTML existant ---
            "dominant": principal,
            "mixte": bool(secondaire),
            "VALUE": None, "GROWTH": None, "GARP": None,  # scores supprimes (v2)
            "alerte_peg": alerte_peg,
            "peg": v["peg"],
            "dy": v["dy"],
            "confiance": confiance,
            # --- v2 ---
            "profil": principal,
            "motif": motif,
            "comparaisons": comparaisons(v) if v["analysable"] else None,
            "payout_source": v["payout_source"],
            "date_cours": v["date_cours"],
            "tendance_intermediaire": (round(var_int, 4) if var_int is not None else None),
            "periode_intermediaire": (f"{periode_int} {ex_int}" if var_int is not None
                                      else None),
            "per_ttm": round(per_ttm, 2) if per_ttm is not None else None,
            "ttm_detail": ttm_detail,
            "ttm_motif": ttm_motif,
            "roe_exercice": v.get("roe_exercice"),
            # Prime du rendement sur le taux sans risque regional. Negative =
            # le titre rapporte MOINS qu'une obligation d'Etat de la zone.
            "taux_reference": taux_ref,
            "prime_rendement": (round(v["dy_axe"] / 100 - taux_ref, 4)
                                if (v["dy_axe"] is not None and taux_ref) else None),
            # C1 (30/09/2026) : "dy" reste le rendement FACIAL du BOC, exact, et la
            # fiche l'affiche. La prime, "dy_recurrent" et les classements ne lisent
            # que le rendement recurrent.
            # C16 option (b), appliquee le 01/10/2026 (cycle 11) : l'axe de decote ne
            # lit plus "dy" non plus, mais "dy_axe". Un titre drapeaute a desormais une
            # case vide sur cet axe et sort du bassin de comparaison.
            "dy_recurrent": (round(v["dy_axe"], 2) if v["dy_axe"] is not None else None),
            "distribution_non_recurrente": v["distribution_detail"],
            "table_cours": v["table_cours"],
            "part_operationnelle": (round(v["part_operationnelle"], 2)
                                    if v.get("part_operationnelle") is not None else None),
            "secondaire": secondaire,
            "grade": grade,
            "notes": notes,
            "reserves": reserves,
            "chiffre_affaires": v.get("chiffre_affaires"),
            "marge_nette": v.get("marge_nette"),
            "croissance_ca": v.get("croissance_ca"),
            "reference_31_decembre": v.get("reference_31_decembre"),
            "roe_source": v.get("roe_source"),
            "source_capitaux_propres": v.get("source_capitaux_propres"),
            "arbitrage": ({"regle": v.get("arbitrage_regle"),
                           "drapeau": v.get("arbitrage_drapeau"),
                           "detail": v.get("arbitrage_detail")}
                          if v.get("arbitrage_drapeau") else None),
            "decote_pctl": decote,
            "croissance_pctl": croissance,
            "reference_axes": ref,
            "g": round(v["g"], 1) if v["g"] is not None else None,
            "source_croissance": v["source_croissance"],
            "drapeaux": v["drapeaux"],
            # "per" reste le PER PUBLIE par le BOC (affiche en premier, lu par les
            # consommateurs existants). "per_analyse" est celui que le moteur a lu
            # pour les axes, le PEGY, le perimetre et les medianes.
            "per": v["per_boc"],
            "per_analyse": round(v["per"], 2) if v["per"] is not None else None,
            "per_source": v["per_source"],
            "payout": v["payout"],
            "roe": round(v["roe"], 1) if v["roe"] is not None else None,
            "pegy": v["pegy"],
            "gate": v["gate"],
            "secteur": v["secteur"],
            "n_secteur": len(par_secteur.get(v["secteur"], {"ep": []})["ep"]),
            "source_fait": fait.get("source"),
            "notation": ({"agence": note.get("agence"), "note": note.get("note_lt"),
                          "note_precedente": note.get("note_ancienne"),
                          "perspective": note.get("perspective"),
                          "date": note.get("date_annonce"),
                          "validite": note.get("validite"),
                          "marge_nette": note.get("marge_nette"),
                          "ca_mds": note.get("ca_mds"),
                          "url": note.get("url_pdf")} if note else None),
            "contradiction_notation": bool(contradiction),
            "statut_cotation": statut,
            "evenements_cotation": [{"date": e["date_avis"], "type": e["type"],
                                     "titre": e.get("titre"), "url": e.get("url")}
                                    for e in evenements],
            "date_statut_cotation": date_statut,
            "historique_cotation": hist,
            "avis_recents": [{"date": a.get("date_avis"), "type": a.get("type"),
                              "titre": a.get("titre"), "url": a.get("url")}
                             for a in avis_titre[:5]],
        }

    SORTIE.write_text(json.dumps(profils, ensure_ascii=False, indent=1), encoding="utf-8")

    # C3 : le journal des predictions. Ecrit APRES profils.json, pour qu'un
    # echec du calcul ne laisse pas une ligne de journal sans le fichier
    # qu'elle est censee attester.
    ajoutees, presentes = ecrire_journal(
        {t: {"profil": v["profil"], "grade": v["grade"],
             "cours": brut[t].get("cours"), "date_cours": v["date_cours"],
             "per": v["per"], "per_analyse": v["per_analyse"]}
         for t, v in profils.items()},
        JOURNAL, date.today())
    print("journal_profils.csv : %d ligne(s) ajoutee(s), %d deja presente(s) pour %s"
          % (ajoutees, presentes, date.today().isoformat()))

    if agregateur:
        ecrire_rapport(verdicts)
    repartition = {}
    for v in profils.values():
        repartition[v["profil"]] = repartition.get(v["profil"], 0) + 1
    grades = {}
    for v in profils.values():
        grades[v["grade"]] = grades.get(v["grade"], 0) + 1
    print("profils.json : %d titres profiles" % len(profils))
    print("  repartition : %s" % ", ".join(
        "%s=%d" % (k, n) for k, n in sorted(repartition.items(), key=lambda kv: -kv[1])))
    print("  grades      : %s" % ", ".join("%s=%d" % (k, grades[k]) for k in sorted(grades)))
    arbitrages = {}
    for v in profils.values():
        d = (v.get("arbitrage") or {}).get("drapeau")
        if d:
            arbitrages[d] = arbitrages.get(d, 0) + 1
    if arbitrages:
        print("  arbitrage   : %s" % ", ".join(
            "%s=%d" % (k, n) for k, n in sorted(arbitrages.items(), key=lambda kv: -kv[1])))
    elif not agregateur:
        print("  arbitrage   : docs/data_brvm.json absent — aucune confrontation")
    return profils


if __name__ == "__main__":
    calculer()
