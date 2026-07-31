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

Sortie : collecte/profils.json
"""
import sqlite3
import json
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "brvm.db"
RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "collecte" / "profils.json"
FAITS = RACINE / "config" / "faits_qualitatifs.yaml"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import charger_seuils, charger_marche, appliquer_gate  # noqa: E402

# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------


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


def croissance_rn(cur, ticker, fenetre, pic_max, base_min, cap):
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
        return None, None, len(chrono), drapeaux + ["SERIE_TRONQUEE"]

    # Garde 2 : base ecrasee (croissance depuis un creux non representatif)
    med = _mediane([x[1] for x in chrono])
    if med and chrono[0][1] < base_min * med:
        drapeaux.append("BASE_ECRASEE")

    n = chrono[-1][0] - chrono[0][0]
    if n <= 0:
        return None, None, len(chrono), drapeaux
    g = (chrono[-1][1] / chrono[0][1]) ** (1.0 / n) - 1

    # Garde 3 : plafond
    if g > cap:
        drapeaux.append("CAP_%d" % round(cap * 100))
        g = cap

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
    lignes = cur.execute(
        "SELECT fin_mois, cours, per FROM cours_mensuels "
        "WHERE ticker=? AND per IS NOT NULL AND per>0 AND cours IS NOT NULL "
        "ORDER BY fin_mois", (ticker,)).fetchall()
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


def ingredients(cur, ticker, seuils, sp):
    per_row = cur.execute(
        "SELECT per FROM cours_mensuels WHERE ticker=? AND per IS NOT NULL "
        "ORDER BY fin_mois DESC LIMIT 1", (ticker,)).fetchone()
    dy_row = cur.execute(
        "SELECT rendement FROM cours_mensuels WHERE ticker=? AND rendement IS NOT NULL "
        "ORDER BY fin_mois DESC LIMIT 1", (ticker,)).fetchone()
    etats = cur.execute(
        "SELECT exercice, resultat_net, capitaux_propres, payout_ratio FROM etats_financiers "
        "WHERE ticker=? ORDER BY exercice DESC", (ticker,)).fetchall()

    per = per_row[0] if per_row else None
    dy = dy_row[0] if dy_row else None  # fraction (0,056 = 5,6 %)

    roe = None
    for exercice, rn, cp, _payout in etats:
        if rn is not None and cp:
            roe = 100.0 * rn / cp
            break
    payout, payout_source = None, None
    for _e, _rn, _cp, p in etats:
        if p is not None:
            payout, payout_source = p, "ETATS_FINANCIERS"
            break
    if payout is None and per and dy is not None:
        # Identite comptable : DPA/BPA = (DPA/cours) x (cours/BPA) = rendement x PER.
        # CHANTIER OUVERT (31/07/2026) : la convention brut/net du champ rendement
        # du BOC n'est PAS tranchee. Test sur 11 titres a payout certifie :
        # 8 se comportent comme BRUT (CBIBF 0,440 vs 0,440 ; SDSC 0,237 vs 0,238 ;
        # SGBC 0,505 vs 0,513), 3 comme NET (dont ORAC : 800 F brut sur 16 000 =
        # 5,0 %, alors que le BOC affiche 4,40 % = exactement le net personnes
        # physiques). Tant que ce n'est pas tranche, le payout implicite est
        # affiche avec sa source et n'est jamais promu au rang de donnee certifiee.
        payout, payout_source = dy * per, "IMPLICITE(rendement x PER)"

    rn_dispo = [(e, rn) for e, rn, _c, _p in etats if rn is not None]
    dernier_rn = rn_dispo[0][1] if rn_dispo else None

    g, statut_g, n_ex, drapeaux = croissance_rn(
        cur, ticker, sp["fenetre_exercices_max"], sp["pic_yoy_max"],
        sp["base_ecrasee_min"], sp["croissance_cap"])
    if g is not None:
        source_g = "RN_%s(%dex)" % (statut_g, n_ex)
    else:
        g, drapeaux = croissance_bpa_implicite(
            cur, ticker, sp["bpa_implicite_annees"], sp["croissance_cap"])
        source_g = "BPA_IMPLICITE" if g is not None else "AUCUNE"

    if g is not None and g > sp["rattrapage_min"] and "RATTRAPAGE" not in drapeaux:
        drapeaux = drapeaux + ["RATTRAPAGE"]

    peg = per / (g * 100) if (per and g and g > 0) else None
    base_pegy = (g + (dy or 0)) * 100 if g is not None else None
    pegy = per / base_pegy if (per and base_pegy and base_pegy > 0) else None

    return dict(per=per, dy=100.0 * dy if dy is not None else None, payout=payout,
                payout_source=payout_source,
                roe=roe, g=100.0 * g if g is not None else None, source_croissance=source_g,
                drapeaux=drapeaux, n_exercices=len(rn_dispo), dernier_rn=dernier_rn,
                peg=round(peg, 2) if peg else None,
                pegy=round(pegy, 2) if pegy else None)


# ----------------------------------------------------------------------
# Signature -> profil
# ----------------------------------------------------------------------


def profil_par_signature(ing, cherte, croissance, sp):
    """Deduction du profil par correspondance de signature. Aucun score.
    Retourne (principal, secondaire, notes)."""
    g = ing["g"]
    dy = ing["dy"]
    payout = ing["payout"]
    pegy = ing["pegy"]
    drapeaux = ing["drapeaux"]
    notes = []

    bloc = ("BASE_ECRASEE" in drapeaux
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
    value = (cherte is not None and cherte >= sp["value_pctl_min"]
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


def motif_du_profil(profil, ing, cherte, croissance, sp):
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
        return ("decote marquee (cherte P%s) sur des benefices etablis%s — "
                "l'histoire est la revalorisation, pas l'expansion"
                % (cherte, "" if g is None else ", croissance de %.1f %%/an" % g))
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
        return "donnees insuffisantes pour etablir un profil (PER absent ou benefices residuels)"

    # --- AUCUN_PROFIL : identifier la cause reelle ---
    if g is None:
        return ("croissance non calculable (historique trop court ou series absentes) : "
                "l'axe croissance manque, ce n'est pas un diagnostic mais une lacune")
    if "BASE_ECRASEE" in dra or any(d.startswith("CAP_") for d in dra) or g > sp["rattrapage_bloquant"] * 100:
        return ("croissance de %.1f %%/an issue d'un rattrapage depuis un creux : "
                "non extrapolable, et decote insuffisante par ailleurs (cherte P%s)"
                % (g, cherte))
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
                "(cherte P%s) ni rendement distinctifs" % (g, gmin, proximite, cherte))
    return ("ni decote (cherte P%s), ni croissance dans le tercile superieur (P%s), "
            "ni rendement superieur : coeur de cote correctement paye"
            % (cherte, croissance))


def sensible_brut_net(profil, ing, sp):
    """Le profil bascule-t-il selon la convention brut/net du rendement ?
    Chantier non tranche : 8 titres se comportent comme BRUT, 3 comme NET."""
    dy = ing["dy"]
    if dy is None:
        return False
    seuil = sp["rendement_dy_min"] * 100
    return bool(dy < seuil <= dy / 0.88)


def grade_confiance(profil, ing, faits_titre):
    """A = exploitable tel quel | B = solide avec reserve nommee | C = travail requis."""
    reserves = []
    source = ing["source_croissance"]
    if source == "BPA_IMPLICITE":
        reserves.append("croissance issue du BPA implicite (source BOC circulaire, "
                        "validation croisee faite sur NSBC uniquement)")
    if source == "AUCUNE":
        reserves.append("aucune source de croissance exploitable")
    if ing["drapeaux"]:
        reserves.append("gardes anti-artefact en jeu (%s) — seuils calibres en echantillon"
                        % ", ".join(ing["drapeaux"]))
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
    if profil in ("VALUE", "RENDEMENT") and ing["payout"] is None:
        return "B", reserves
    if "VERIFIE" in source and not ing["drapeaux"]:
        return "A", reserves
    if "VERIFIE" in source or source == "RN_PROBABLE" or source.startswith("RN_"):
        return "B", reserves
    if source == "BPA_IMPLICITE":
        return "B", reserves
    return "C", reserves


# ----------------------------------------------------------------------
# Calcul principal
# ----------------------------------------------------------------------


def calculer():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    seuils, marche = charger_seuils(), charger_marche()
    faits = charger_faits()

    par_defaut = dict(
        fenetre_exercices_max=4, pic_yoy_max=3.5, base_ecrasee_min=0.30,
        croissance_cap=0.60, bpa_implicite_annees=3, rattrapage_min=0.25,
        rattrapage_bloquant=0.30, payout_max=1.0, per_max_analysable=50,
        n_secteur_min=8, value_pctl_min=67, growth_pctl_min=67,
        garp_g_min=0.08, garp_g_max=0.30, garp_pegy_max=1.5, growth_g_min=0.05,
        rendement_dy_min=0.048, contraction_seuil=0.10, alerte_pegy_max=0.25,
        confiance_haute_min_exercices=4, confiance_moyenne_min_exercices=2)
    sp = dict(par_defaut)
    sp.update({k: v for k, v in (seuils.get("profils") or {}).items() if k in par_defaut})

    secteurs = dict(cur.execute("SELECT ticker, secteur FROM societes"))
    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]

    brut = {}
    for t in tickers:
        # un titre sans aucune cotation n'est pas encore cote (ex. IPO annoncee)
        cote = cur.execute(
            "SELECT COUNT(*) FROM cours_mensuels WHERE ticker=?", (t,)).fetchone()[0]
        if not cote:
            continue
        ing = ingredients(cur, t, seuils, sp)
        statut_gate, _motifs = appliquer_gate(cur, t, secteurs.get(t, ""), seuils, marche)
        brut[t] = dict(ing, gate=statut_gate, secteur=secteurs.get(t, ""))

    # --- Perimetre analysable : PER exploitable et pas de fait qualitatif bloquant
    for t, v in brut.items():
        fait = (faits.get(t) or {}).get("profil")
        per = v["per"]
        v["analysable"] = bool(
            fait is None and per is not None and per <= sp["per_max_analysable"])
    analysables = {t: v for t, v in brut.items() if v["analysable"]}

    # --- Axes : double lecture secteur (n>=8) / marche, reference etiquetee
    ep = {t: (100.0 / v["per"]) for t, v in analysables.items() if v["per"]}
    par_secteur = {}
    for t, v in analysables.items():
        d = par_secteur.setdefault(v["secteur"], {"ep": [], "dy": [], "g": []})
        if t in ep:
            d["ep"].append(ep[t])
        if v["dy"] is not None:
            d["dy"].append(v["dy"])
        if v["g"] is not None:
            d["g"].append(v["g"])
    marche_ep = list(ep.values())
    marche_dy = [v["dy"] for v in analysables.values() if v["dy"] is not None]
    marche_g = [v["g"] for v in analysables.values() if v["g"] is not None]

    def axes(t, v):
        d = par_secteur.get(v["secteur"], {"ep": [], "dy": [], "g": []})
        assez = len(d["ep"]) >= sp["n_secteur_min"]
        if assez:
            ref = "secteur (n=%d)" % len(d["ep"])
            p_ep = pctl(d["ep"], ep.get(t))
            p_dy = pctl(d["dy"], v["dy"])
            p_g = pctl(d["g"], v["g"])
        else:
            ref = "marche (n=%d)" % len(marche_ep)
            p_ep = pctl(marche_ep, ep.get(t))
            p_dy = pctl(marche_dy, v["dy"])
            p_g = pctl(marche_g, v["g"])
        dispo = [x for x in (p_ep, p_dy) if x is not None]
        cherte = round(sum(dispo) / len(dispo)) if dispo else None
        return cherte, p_g, ref

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
            elif v["per"] is None or v["per"] > sp["per_max_analysable"]:
                principal, secondaire, notes = "NON_ANALYSABLE", None, [
                    "PER absent ou > %d : benefices nuls ou residuels" % sp["per_max_analysable"]]
            else:
                principal, secondaire, notes = "NON_ANALYSABLE", None, []
            cherte = croissance = None
            ref = "hors axes"
        else:
            cherte, croissance, ref = axes(t, v)
            principal, secondaire, notes = profil_par_signature(v, cherte, croissance, sp)

        motif = motif_du_profil(principal, v, cherte, croissance, sp)
        if sensible_brut_net(principal, v, sp):
            notes = notes + [
                "profil SENSIBLE a la convention brut/net du rendement : avec un "
                "rendement brut, le seuil du profil RENDEMENT serait franchi. "
                "Chantier de verification ouvert — aucune correction appliquee."]
        grade, reserves = grade_confiance(principal, v, fait)
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
            "secondaire": secondaire,
            "grade": grade,
            "notes": notes,
            "reserves": reserves,
            "cherte_pctl": cherte,
            "croissance_pctl": croissance,
            "reference_axes": ref,
            "g": round(v["g"], 1) if v["g"] is not None else None,
            "source_croissance": v["source_croissance"],
            "drapeaux": v["drapeaux"],
            "per": v["per"],
            "payout": v["payout"],
            "roe": round(v["roe"], 1) if v["roe"] is not None else None,
            "pegy": v["pegy"],
            "gate": v["gate"],
            "secteur": v["secteur"],
            "n_secteur": len(par_secteur.get(v["secteur"], {"ep": []})["ep"]),
            "source_fait": fait.get("source"),
        }

    SORTIE.write_text(json.dumps(profils, ensure_ascii=False, indent=1), encoding="utf-8")
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
    return profils


if __name__ == "__main__":
    calculer()
