#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moteur de decision BRVM — module pur, teste par golden tests (voir tester.py).
Contrat d'interface : evaluer_titre(ticker) -> dict avec statut_gate, motifs,
scores par dimension, score composite, alertes. Aucune donnee metier en dur :
tout provient de seuils.yaml (registre versionne) et de brvm.db (donnees tracees).
"""
import json, sqlite3, sys
from datetime import date
import yaml

from pathlib import Path
_BASE = Path(__file__).resolve().parent          # moteur/
_RACINE = _BASE.parent                            # racine du depot
DB = str(_BASE / "brvm.db")
SEUILS_PATH = str(_RACINE / "config" / "seuils.yaml")
MARCHE_PATH = str(_RACINE / "config" / "marche.yaml")


def charger_seuils():
    return yaml.safe_load(open(SEUILS_PATH, encoding="utf-8"))


def charger_marche():
    return yaml.safe_load(open(MARCHE_PATH, encoding="utf-8"))


LIQUIDITE_JOUR_PATH = str(_RACINE / "collecte" / "liquidite_jour.json")


def charger_liquidite_jour():
    """P8 (12/07/2026) : lit le volume/valeur du jour publie directement par
    BRVM (collecte_liquidite_jour.py), une seule page, aucune reconstruction.
    Absence geree proprement (fichier pas encore produit par un premier run
    reel du robot, ou jour sans collecte) — retourne {} plutot que planter,
    modificateur_taille se rabat alors sur marche.yaml."""
    try:
        return json.load(open(LIQUIDITE_JOUR_PATH, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


LIQUIDITE_GENERALE_PATH = str(_RACINE / "collecte" / "liquidite_generale.json")


def charger_liquidite_generale():
    """P9 (12/07/2026) : reference de liquidite TYPIQUE (moyenne 12 mois
    glissants, valeur en FCFA absolue par titre) — distincte de
    charger_liquidite_jour() qui donne un INSTANTANE d'un seul jour. Repond
    a une question differente : "ce titre est-il liquide en general ?" (ici)
    vs "puis-je executer aujourd'hui ?" (liquidite_jour.json)."""
    try:
        return json.load(open(LIQUIDITE_GENERALE_PATH, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


TENDANCE_LIQUIDITE_PATH = str(_RACINE / "collecte" / "tendance_liquidite.json")


def charger_tendance_liquidite():
    """P10 (12/07/2026) : detection precoce — compare la valeur echangee des
    3 derniers mois a la moyenne 12 mois, ET verifie la coherence avec la
    variation de prix sur la meme periode (un mouvement de volume corrobore
    par le prix est plus credible qu'isole, cf. discussion methodologique).
    Seuils derives d'un test de permutation (2000 tirages/titre, 12/07/2026) :
    - >=125% d'ecart : CONFIRMEE (95e percentile du bruit pur mesure)
    - >=30% d'ecart ET coherent avec le prix : A_SURVEILLER (non confirme
      statistiquement, signale quand meme pour la detection precoce)
    - sinon : STABLE
    Limite assumee : seuils calibres sur 47 titres / 12 mois — a recalibrer
    a mesure que l'historique s'allonge, comme les seuils du score composite."""
    try:
        return json.load(open(TENDANCE_LIQUIDITE_PATH, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_conn():
    return sqlite3.connect(DB)


def dernier_et_precedent_exercice(cur, ticker):
    rows = cur.execute(
        "SELECT * FROM etats_financiers WHERE ticker=? ORDER BY exercice DESC",
        (ticker,)).fetchall()
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in rows]
    return rows  # liste triee, le plus recent en premier


def dividendes(cur, ticker):
    rows = cur.execute(
        "SELECT montant_net, date_paiement, exercice_couvert FROM dividendes "
        "WHERE ticker=? ORDER BY date_paiement DESC", (ticker,)).fetchall()
    return [{"montant_net": r[0], "date_paiement": r[1], "exercice_couvert": r[2]}
            for r in rows]


def avis(cur, ticker, type_=None):
    q = "SELECT type, date_avis, note FROM avis_reglementaires WHERE ticker=?"
    p = [ticker]
    if type_:
        q += " AND type=?"; p.append(type_)
    return cur.execute(q, p).fetchall()


# ---------------------- NIVEAU 1 : FILTRES D'EXCLUSION ----------------------
def appliquer_gate(cur, ticker, secteur, seuils, marche):
    """Retourne (statut, [motifs]). Un seul motif suffit a exclure (gate = OR)."""
    fx = seuils["filtres_exclusion"]
    motifs = []

    # Suspension/sanction/retards : evenements reglementaires independants de
    # la disponibilite des etats financiers -> verifies en premier et
    # ACCUMULES (ne court-circuitent pas les controles financiers qui suivent,
    # cf. cas TEST_EXCLU ou plusieurs motifs coexistent).
    if avis(cur, ticker, "SUSPENSION"):
        motifs.append("suspension de cotation enregistree")
    if avis(cur, ticker, "SANCTION"):
        motifs.append("sanction du regulateur enregistree")
    retards = avis(cur, ticker, "RETARD_PUBLICATION")
    if len(retards) >= fx["retards_publication"]["defauts_max"]:
        motifs.append(f"{len(retards)} retard(s) de publication constate(s)")

    etats = dernier_et_precedent_exercice(cur, ticker)

    if not etats:
        motifs.append("aucune donnee financiere disponible")
        return "EXCLU", motifs

    dernier = etats[0]

    # 5. Capitaux propres negatifs (immediat)
    if dernier["capitaux_propres"] is not None and dernier["capitaux_propres"] < 0:
        motifs.append(f"capitaux propres negatifs ({dernier['capitaux_propres']} M FCFA)")

    # 6. Resultat net negatif sur N exercices consecutifs
    n_neg = fx["resultat_net_negatif_exercices"]
    valeurs_rn = [e["resultat_net"] for e in etats]
    if len(valeurs_rn) < n_neg and dernier.get("resultat_net_n1") is not None:
        valeurs_rn.append(dernier["resultat_net_n1"])
    if len(valeurs_rn) >= n_neg:
        derniers_rn = valeurs_rn[:n_neg]
        if all(rn is not None and rn < 0 for rn in derniers_rn):
            motifs.append(f"resultat net negatif sur {n_neg} exercices consecutifs")

    # 7. Endettement anormal (hors banques : D/E ; banques : solvabilite)
    if secteur == "SERVICES_FINANCIERS":
        sv = dernier.get("solvabilite_bancaire")
        if sv is not None and sv < fx["solvabilite_bancaire_min"]:
            motifs.append(f"solvabilite bancaire {sv:.1%} < minimum "
                          f"{fx['solvabilite_bancaire_min']:.1%}")
    else:
        if dernier["dettes_financieres"] and dernier["capitaux_propres"]:
            de = dernier["dettes_financieres"] / dernier["capitaux_propres"]
            mediane = marche["de_mediane_sectorielle"].get(secteur, 1.0)
            if de > fx["de_ratio_multiple_median_sectoriel"] * mediane:
                motifs.append(f"D/E {de:.2f} > {fx['de_ratio_multiple_median_sectoriel']}x "
                              f"mediane sectorielle ({mediane})")

    # 9. Payout > seuil sur N exercices consecutifs
    n_pay = fx["payout_max_exercices"]
    if len(etats) >= n_pay:
        payouts = [e["payout_ratio"] for e in etats[:n_pay]]
        if all(p is not None and p > fx["payout_max"] for p in payouts):
            motifs.append(f"payout > {fx['payout_max']:.0%} sur {n_pay} exercices consecutifs")

    return ("EXCLU", motifs) if motifs else ("ELIGIBLE", [])


# ---------------------- NIVEAU 2 : SCORE COMPOSITE ----------------------
def score_rentabilite(etats, seuils, marche=None):
    """35% — ROE, croissance, regularite, recul maximal.
    Utilise resultat_net_n1 de la MEME ligne (comparatif republie dans le document
    source), et complete si besoin par une 2e ligne d'exercice anterieur si
    disponible dans la base. Retourne (note /100, alertes)."""
    alertes = []
    if not etats or etats[0]["resultat_net"] is None:
        return None, ["resultat net indisponible pour noter la rentabilite"]

    rn = etats[0]["resultat_net"]
    rn_n1 = etats[0].get("resultat_net_n1")
    if rn_n1 is None and len(etats) >= 2:
        rn_n1 = etats[1]["resultat_net"]
    if rn_n1 is None or rn_n1 == 0:
        return None, ["comparatif N-1 indisponible pour noter la rentabilite"]

    # CAS TURNAROUND : base de comparaison negative -> la "croissance" en %
    # n'a aucun sens economique (artefact detecte a l'audit sur ORGT/SAFC).
    if rn_n1 < 0:
        if rn >= 0:
            alertes.append("TURNAROUND (perte N-1 -> profit) : croissance non "
                           "comparable a une croissance organique — note neutre+, "
                           "durabilite du redressement a confirmer sur 2-3 exercices")
            return 55.0, alertes
        alertes.append("pertes sur les deux exercices"
                       + (" (en attenuation)" if rn > rn_n1 else " (en aggravation)"))
        return 35.0, alertes

    croissance = (rn - rn_n1) / abs(rn_n1)
    note = 50 + min(max(croissance, -1), 1) * 50  # 0-100, 0%=50, +100%=100, -100%=0

    # Comparaison RN vs RAO (Resultat des Activites Ordinaires, SYSCOHADA) —
    # JAMAIS de substitution : le RN reste la base de calcul (coherence avec
    # payout/ROE/dividende qui utilisent tous le RN ailleurs dans ce meme
    # moteur). Si un ecart important existe entre les deux croissances, on
    # MODERE la note (moyenne RN/RAO) et on l'affiche explicitement — on ne
    # bascule jamais silencieusement sur une seule des deux bases.
    rao = etats[0].get("resultat_activites_ordinaires")
    rao_n1 = etats[1].get("resultat_activites_ordinaires") if len(etats) >= 2 else None
    if rao is not None and rao_n1 is not None and rao_n1 != 0:
        croissance_rao = (rao - rao_n1) / abs(rao_n1)
        note_rao = 50 + min(max(croissance_rao, -1), 1) * 50
        ecart = abs(croissance - croissance_rao)
        if ecart > 0.50:
            alertes.append(
                f"ECART RN/RAO important : croissance resultat net {croissance:+.1%} vs "
                f"croissance activites ordinaires {croissance_rao:+.1%} — part non recurrente "
                f"probable ; note moderee (moyenne RN/RAO, jamais de substitution)")
            note = (note + note_rao) / 2
        else:
            alertes.append(f"croissance RAO {croissance_rao:+.1%} coherente avec le RN "
                           f"(ecart {ecart:.1%}, pas de moderation necessaire)")

    # R5 — ROE (premier indicateur specifie pour cette dimension, absent jusqu'ici)
    cp = etats[0].get("capitaux_propres")
    if cp and cp > 0:
        roe = rn / cp
        alertes.append(f"ROE {roe:.1%}")
        if roe > 0.15:
            note += 10
        elif roe < 0.05:
            note -= 10
            alertes.append("ROE faible (<5%) — rentabilite des capitaux propres limitee")

    rc = seuils["score"]["recul_max"]
    if croissance < 0:
        recul = abs(croissance)
        if recul >= rc["vigilance"]:
            alertes.append(f"recul du resultat net de {recul:.1%} (seuil de vigilance {rc['vigilance']:.0%})")
            note -= 20
        elif recul >= rc["malus_des"]:
            alertes.append(f"recul du resultat net de {recul:.1%} (malus leger)")
            note -= 10
    return max(0, min(100, note)), alertes


def score_solidite(ticker, etats, seuils, divs):
    """30% — payout sain, regularite dividende, recul capitaux propres."""
    alertes = []
    note = 50.0
    ps = seuils["score"]["payout_sain"]
    payout = etats[0].get("payout_ratio")
    if payout is not None:
        if ps["min"] <= payout <= ps["max"]:
            note += 20
        elif payout > ps["max"]:
            alertes.append(f"payout {payout:.0%} au-dessus de la fourchette saine "
                          f"({ps['min']:.0%}-{ps['max']:.0%})")
            note -= 15
            if payout > 1.0:
                alertes.append("payout superieur a 100% sur ce seul exercice — "
                              "a surveiller de tres pres l'exercice suivant")
        else:
            note -= 5

    # Regularite du dividende
    annees_seuil = seuils["score"]["dividende_regulier_annees"]
    if divs:
        dernier_div = divs[0]
        try:
            annee_dernier = int(dernier_div["date_paiement"][:4])
            anciennete = date.today().year - annee_dernier
            if anciennete == 0 and dernier_div["montant_net"] and dernier_div["montant_net"] > 0:
                note += 20
            elif anciennete >= 3:
                alertes.append(f"dernier dividende verse il y a {anciennete} ans "
                              "— regularite non etablie")
                note -= 20
        except (ValueError, TypeError):
            pass
    else:
        alertes.append("aucun historique de dividende disponible")

    if len(etats) >= 2 and etats[0]["capitaux_propres"] and etats[1]["capitaux_propres"]:
        cp, cp_n1 = etats[0]["capitaux_propres"], etats[1]["capitaux_propres"]
        if cp_n1 and cp < cp_n1:
            recul = (cp_n1 - cp) / abs(cp_n1)
            if recul >= seuils["score"]["recul_max"]["vigilance"]:
                alertes.append(f"recul des capitaux propres de {recul:.1%}")
                note -= 15
    return max(0, min(100, note)), alertes


SEUIL_FRAICHEUR_JOURS = 45  # au-dela, alerte ; conforme a la cadence bimensuelle de collecte (lun/jeu)


def verifier_fraicheur(fin_mois_str, aujourdhui=None):
    """R7 — garde-fou de fraicheur. fin_mois_str format 'AAAA-MM'.
    Retourne (jours_ecoules, perime:bool)."""
    from datetime import date as _date
    if aujourdhui is None:
        aujourdhui = _date.today()
    if not fin_mois_str:
        return None, True
    annee, mois = map(int, fin_mois_str.split("-"))
    ref = _date(annee, mois, 28)  # fin de mois approximative
    jours = (aujourdhui - ref).days
    return jours, jours > SEUIL_FRAICHEUR_JOURS


def per_le_plus_recent(cur, ticker):
    """Source de verite : cours_mensuels (vivante, R3). Retourne (per, fin_mois)
    ou (None, None) si aucune donnee chargee pour ce ticker."""
    row = cur.execute(
        "SELECT per, fin_mois FROM cours_mensuels WHERE ticker=? AND per IS NOT NULL "
        "ORDER BY fin_mois DESC LIMIT 1", (ticker,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def per_periode(cur, ticker, mois_cible):
    """PER a un mois precis (AAAA-MM), ou le plus proche disponible avant."""
    row = cur.execute(
        "SELECT per, fin_mois FROM cours_mensuels WHERE ticker=? AND per IS NOT NULL "
        "AND fin_mois <= ? ORDER BY fin_mois DESC LIMIT 1", (ticker, mois_cible)).fetchone()
    return (row[0], row[1]) if row else (None, None)


def rendement_le_plus_recent(cur, ticker):
    row = cur.execute(
        "SELECT rendement, fin_mois FROM cours_mensuels WHERE ticker=? "
        "AND rendement IS NOT NULL ORDER BY fin_mois DESC LIMIT 1", (ticker,)).fetchone()
    return (row[0], row[1]) if row else (None, None)


# Angle mort fiscal UEMOA (identifie a l'audit du 11/07/2026) — IRVM (Impot sur
# le Revenu des Valeurs Mobilieres), retenue a la source sur dividendes, taux
# par pays de siege de l'emetteur (pas du beneficiaire — simplification assumee,
# la fiscalite du beneficiaire depend de sa propre residence et des conventions
# bilaterales, hors scope de ce calcul indicatif). Sources : SikaFinance,
# directive UEMOA n(deg) 02/2010/CM/UEMOA (fourchette 2-7% pour societes cotees,
# taux reels observes par pays ci-dessous, verifies 11/07/2026.
IRVM_PAR_PAYS = {
    "BF": 0.125,  # Burkina Faso
    "CI": 0.10,   # Cote d'Ivoire
    "SN": 0.10,   # Senegal
    "ML": 0.07,   # Mali (depuis 2017)
    "TG": 0.07,   # Togo (personnes morales ; 3% pour personnes physiques, non modelise ici)
    "BJ": 0.05,   # Benin (depuis 2018)
    "NE": 0.10,   # Niger (taux non confirme independamment, aligne sur le taux de droit commun UEMOA)
}


def rendement_net_estime(rendement_brut, pays):
    """R6+ (11/07/2026) : rendement net indicatif apres IRVM standard du pays
    de siege. INDICATIF SEULEMENT — ne tient pas compte de la residence fiscale
    du beneficiaire, des conventions bilaterales, ni des cas particuliers
    (FTSC/STBC notes par SikaFinance comme ayant un IRVM effectif tres inferieur
    du fait de leur consolidation — non modelise, ecart possible)."""
    taux = IRVM_PAR_PAYS.get(pays)
    if rendement_brut is None or taux is None:
        return None, taux
    return rendement_brut * (1 - taux), taux


def _mediane(valeurs):
    v = sorted(valeurs)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def per_secteur_reproductible(cur, secteur, marche, min_titres=3):
    """R5 : mediane du PER individuel des titres du secteur, au dernier mois
    disponible pour chacun — reproductible depuis nos donnees, contrairement a
    un chiffre BOC dont la methodologie exacte (pondere ? moyenne ?) n'est pas
    reconstituable depuis les bulletins bruts (cf. audit R5). Repli sur
    marche.yaml si echantillon insuffisant."""
    rows = cur.execute(
        "SELECT cm.per FROM cours_mensuels cm JOIN societes s ON s.ticker = cm.ticker "
        "WHERE s.secteur = ? AND cm.per IS NOT NULL AND cm.fin_mois = "
        "(SELECT MAX(fin_mois) FROM cours_mensuels WHERE per IS NOT NULL)",
        (secteur,)).fetchall()
    pers = [r[0] for r in rows]
    if len(pers) >= min_titres:
        return _mediane(pers), f"mediane sur {len(pers)} titres (reproductible)"
    return marche["per_sectoriel"].get(secteur), "repli marche.yaml (echantillon insuffisant)"


def rendement_secteur_reproductible(cur, secteur, marche, min_titres=3):
    rows = cur.execute(
        "SELECT cm.rendement FROM cours_mensuels cm JOIN societes s ON s.ticker = cm.ticker "
        "WHERE s.secteur = ? AND cm.rendement IS NOT NULL AND cm.fin_mois = "
        "(SELECT MAX(fin_mois) FROM cours_mensuels WHERE rendement IS NOT NULL)",
        (secteur,)).fetchall()
    rdts = [r[0] for r in rows]
    if len(rdts) >= min_titres:
        return sum(rdts) / len(rdts), f"moyenne sur {len(rdts)} titres (reproductible)"
    return marche["indicateurs_marche"].get("rendement_moyen"), "repli marche.yaml (marche entier)"


def score_valorisation(cur, ticker, secteur, etats, seuils, marche):
    """35% — PER vs secteur, PEG historique, rendement vs marche ET secteur (R5)."""
    alertes = []
    per, fin_mois = per_le_plus_recent(cur, ticker)
    if per is not None:
        jours, perime = verifier_fraicheur(fin_mois)
        if perime:
            alertes.append(f"DONNEE PERIMEE : PER date du {fin_mois} ({jours} jours) — "
                           f"seuil de fraicheur {SEUIL_FRAICHEUR_JOURS}j depasse, a rafraichir")
    if per is not None:
        alertes.append(f"PER {per:.2f} au {fin_mois} (source : cours_mensuels)")
    else:
        per = marche["per_individuels"].get(ticker)
        if per is not None:
            alertes.append(f"PER {per} — repli sur marche.yaml, "
                           "aucune donnee cours_mensuels pour ce titre (a rafraichir)")
    per_secteur, methode_secteur = per_secteur_reproductible(cur, secteur, marche)
    if per is None or per_secteur is None:
        return None, ["PER indisponible pour noter la valorisation"]
    alertes.append(f"PER secteur {per_secteur:.2f} ({methode_secteur})")

    ecart = (per_secteur - per) / per_secteur  # positif = decote
    note = 50 + max(min(ecart, 1), -1) * 50

    rn = etats[0]["resultat_net"] if etats else None
    rn_n1 = etats[0].get("resultat_net_n1") if etats else None
    if rn_n1 is None and len(etats) >= 2:
        rn_n1 = etats[1]["resultat_net"]
    if rn is not None and rn_n1:
        if rn_n1 < 0:
            alertes.append("PEG non calculable : base N-1 negative (turnaround) — "
                           "le bonus de valorisation ne s'applique pas")
        elif (rn - rn_n1) / abs(rn_n1) > 0:
            croissance_pct = (rn - rn_n1) / abs(rn_n1) * 100
            peg = per / croissance_pct if croissance_pct > 0 else None
            if peg is not None:
                if peg < seuils["score"]["peg_attractif_max"]:
                    note += 15
                    alertes.append(f"PEG historique {peg:.2f} < seuil attractif "
                                  f"({seuils['score']['peg_attractif_max']})")
        elif (rn - rn_n1) / abs(rn_n1) < 0:
            alertes.append("PEG non calculable : resultat net en repli sur la periode")

    # R5 — rendement vs marche ET vs secteur (indicateur specifie, manquant jusqu'ici)
    rendement, fin_mois_rdt = rendement_le_plus_recent(cur, ticker)
    if rendement is not None:
        rdt_marche = marche["indicateurs_marche"]["rendement_moyen"]
        rdt_secteur, methode_rdt = rendement_secteur_reproductible(cur, secteur, marche)
        alertes.append(f"rendement {rendement:.2%} au {fin_mois_rdt} vs marche "
                       f"{rdt_marche:.2%} et secteur {rdt_secteur:.2%} ({methode_rdt})")
        pays_row = cur.execute("SELECT pays_immatriculation FROM societes WHERE ticker=?", (ticker,)).fetchone()
        pays = pays_row[0] if pays_row else None
        rdt_net, taux_irvm = rendement_net_estime(rendement, pays)
        if rdt_net is not None:
            alertes.append(f"rendement NET estime apres IRVM {pays} ({taux_irvm:.1%}) : "
                           f"{rdt_net:.2%} — indicatif, ne tient pas compte de la residence "
                           "fiscale du beneficiaire ni des conventions bilaterales")
        if rendement > rdt_marche and (rdt_secteur is None or rendement > rdt_secteur):
            note += 10
        elif rendement < rdt_marche * 0.5:
            alertes.append("rendement nettement sous la moyenne marche — "
                           "verifier si coherent avec le profil GARP recherche")
            note -= 5

    # R5 — part du re-rating deja consommee (PER actuel vs PER il y a 12 mois)
    if fin_mois:
        annee, mois = fin_mois.split("-")
        mois_n1 = f"{int(annee)-1}-{mois}"
        per_ancien, fin_mois_ancien = per_periode(cur, ticker, mois_n1)
        if per_ancien and per_ancien > 0:
            hausse_per = (per - per_ancien) / per_ancien
            alertes.append(f"PER {hausse_per:+.0%} vs il y a 12 mois "
                           f"({fin_mois_ancien}) — re-rating deja consomme")
            if hausse_per > 0.30:
                note -= 10
                alertes.append("re-rating deja largement consomme — "
                               "potentiel restant probablement moindre")

    if per > per_secteur * 2:
        alertes.append(f"PER {per} tres superieur au secteur ({per_secteur:.2f}) — "
                       "verifier la plausibilite du BNPA")
    return max(0, min(100, note)), alertes


# ---------------------- NIVEAU 3 : MODIFICATEURS DE TAILLE ----------------------
def modificateur_taille(ticker, marche):
    """N'affecte JAMAIS le score — affecte uniquement la taille de ligne
    recommandee. Statut explicite si la donnee manque plutot que de deviner
    (principe : integrite > couverture).

    PRIORITE (revisee 12/07/2026) : le volume/valeur DU JOUR, publie
    directement par BRVM (liquidite_jour.json, collecte_liquidite_jour.py,
    une seule page lue telle quelle) est verifie EN PREMIER — c'est la
    donnee la plus actuelle et la plus simple, sans aucune reconstruction.
    marche.yaml (flottant, mesures historiques) reste un repli pour les
    jours sans collecte (week-end, jour ferie, script pas encore execute)."""
    liquidite_jour = charger_liquidite_jour()
    donnee_jour = liquidite_jour.get(ticker)
    ref_jour = liquidite_jour.get("SNTS", {}).get("valeur_echangee_jour")

    if donnee_jour is not None and ref_jour:
        valeur = donnee_jour["valeur_echangee_jour"]
        ratio = valeur / ref_jour
        date_maj = donnee_jour.get("date_maj_brvm", "date inconnue")
        if ratio < 0.01:
            return {
                "statut": "QUASI_INTRADABLE_JOUR",
                "recommandation": "MINIMALE",
                "note": f"valeur echangee du jour a {ratio:.1%} de la reference marche "
                       f"({date_maj}) — donnee BRVM directe, pas une reconstruction",
            }
        if ratio < 0.25:
            return {
                "statut": "LIQUIDITE_FAIBLE_JOUR",
                "recommandation": "REDUITE",
                "note": f"valeur echangee du jour a {ratio:.1%} de la reference marche ({date_maj})",
            }
        return {
            "statut": "LIQUIDITE_NORMALE_JOUR",
            "recommandation": "PLEINE",
            "note": f"valeur echangee du jour a {ratio:.1%} de la reference marche ({date_maj})",
        }

    # --- Repli : marche.yaml (pas de collecte du jour disponible) ---
    liq = marche.get("liquidite_individuelle", {}).get(ticker)
    rotation_marche = marche["indicateurs_marche"]["taux_rotation_moyen"]

    if liq is None:
        return {
            "statut": "DONNEE_INDISPONIBLE",
            "recommandation": "PRUDENCE",
            "note": f"aucune donnee individuelle collectee (ni jour, ni repli marche.yaml) — "
                   f"defaut prudent justifie par le taux de rotation moyen du marche "
                   f"({rotation_marche}), structurellement bas",
        }

    liquidite_execution = liq.get("liquidite_execution")
    if liquidite_execution == "ELEVEE":
        return {
            "statut": "LIQUIDITE_ELEVEE",
            "recommandation": "PLEINE",
            "note": liq.get("note", "") + " [repli marche.yaml, pas de collecte du jour]",
        }

    flottant = liq.get("ratio_flottant")
    if flottant is not None and flottant < 0.25:
        return {
            "statut": "FLOTTANT_RESTREINT",
            "recommandation": "REDUITE",
            "note": f"flottant estime a {flottant:.0%} (source: {liq.get('source', '?')}) "
                   "— taille de ligne reduite, horizon de sortie allonge [repli marche.yaml]",
        }

    volume_relatif = liq.get("volume_relatif_marche")
    if volume_relatif is not None:
        if volume_relatif < 0.01:
            return {
                "statut": "QUASI_INTRADABLE",
                "recommandation": "MINIMALE",
                "note": f"volume mesure a {volume_relatif:.1%} de la reference marche "
                       f"(source: {liq.get('source', '?')}) — {liq.get('note', '')} "
                       "— rendement-prix observe non fiable, backtest sensible a exclure "
                       "[repli marche.yaml]",
            }
        if volume_relatif < 0.25:
            return {
                "statut": "LIQUIDITE_FAIBLE_MESUREE",
                "recommandation": "REDUITE",
                "note": f"volume mesure a {volume_relatif:.1%} de la reference marche "
                       f"(source: {liq.get('source', '?')}) [repli marche.yaml]",
            }

    return {
        "statut": "NORMAL",
        "recommandation": "PLEINE",
        "note": (f"flottant {flottant:.0%}" if flottant is not None else "") + " [repli marche.yaml]",
    }


# ---------------------- ORCHESTRATION ----------------------
def evaluer_titre(ticker):
    seuils = charger_seuils()
    marche = charger_marche()
    conn = get_conn()
    cur = conn.cursor()
    secteur = cur.execute("SELECT secteur FROM societes WHERE ticker=?",
                          (ticker,)).fetchone()
    if not secteur:
        conn.close()
        return {"ticker": ticker, "erreur": "societe inconnue"}
    secteur = secteur[0]

    statut_gate, motifs_gate = appliquer_gate(cur, ticker, secteur, seuils, marche)
    etats = dernier_et_precedent_exercice(cur, ticker)
    divs = dividendes(cur, ticker)
    sizing = modificateur_taille(ticker, marche)

    resultat = {
        "ticker": ticker, "secteur": secteur,
        "statut_gate": statut_gate, "motifs_exclusion": motifs_gate,
        "score_rentabilite": None, "score_solidite": None,
        "score_valorisation": None, "score_composite": None,
        "alertes": [], "sizing": sizing,
    }

    if statut_gate == "ELIGIBLE":
        sr, ar = score_rentabilite(etats, seuils)
        ss, as_ = score_solidite(ticker, etats, seuils, divs)
        sv, av = score_valorisation(cur, ticker, secteur, etats, seuils, marche)
        resultat["score_rentabilite"] = sr
        resultat["score_solidite"] = ss
        resultat["score_valorisation"] = sv
        resultat["alertes"] = ar + as_ + av

    # Avis contextuels non-excluants (NOTATION_DEGRADEE, GOUVERNANCE, ...) :
    # ils ne bloquent pas et ne modifient pas le score, mais DOIVENT etre
    # visibles a cote de lui (lecon de l'audit : ORGT n°2 avec un processus
    # de defaut Fitch invisible etait inacceptable). Deplace HORS du bloc
    # ELIGIBLE : un titre sans donnee financiere (gap, statut EXCLU) doit
    # aussi remonter ses avis contextuels — decouvert lors de l'etape A du
    # plan de marche (SDSC, 10/07/2026) : l'avis Financial Afrik restait
    # invisible faute de score calculable, alors qu'il est precisement
    # l'information la plus utile disponible pour ce titre.
    types_excluants = {"RETARD_PUBLICATION", "SANCTION", "SUSPENSION", "OPR"}
    for t_avis, d_avis, note_avis in avis(cur, ticker):
        if t_avis not in types_excluants:
            resultat["alertes"].append(
                f"AVIS {t_avis} ({d_avis}) : {note_avis}")

    if statut_gate == "ELIGIBLE":

        poids = seuils["score"]["poids"]
        composantes = [(sr, poids["rentabilite"]), (ss, poids["solidite"]),
                       (sv, poids["valorisation"])]
        dispo = [(v, p) for v, p in composantes if v is not None]
        if dispo:
            poids_total = sum(p for _, p in dispo)
            resultat["score_composite"] = round(
                sum(v * p for v, p in dispo) / poids_total, 1)
            if poids_total < 1.0:
                resultat["alertes"].append(
                    f"score calcule sur {poids_total:.0%} du poids seulement "
                    "(donnees manquantes sur une dimension)")

            # Etape D du plan de marche (10/07/2026) : le signal decote-vs-secteur
            # (dimension Valorisation) n'est PAS statistiquement significatif une
            # fois la structure de correlation des donnees correctement prise en
            # compte (bootstrap en blocs par titre, IC 95% incluant zero — cf.
            # document de reference section 20). Decision : le score composite
            # reste CALCULE (a titre observationnel, pour suivre son comportement
            # au fil de la collecte), mais SUSPENDU comme critere de decision
            # principal. Les 3 sous-scores (rentabilite/solidite/valorisation)
            # sont la lecture de reference tant qu'un echantillon plus large
            # (plus de titres, plus d'annees) ne permet pas de trancher les poids.
            resultat["composite_observationnel"] = True
            resultat["alertes"].append(
                "SCORE COMPOSITE SUSPENDU comme critere de decision (etape D, "
                "10/07/2026) — affiche a titre observationnel uniquement ; "
                "se referer aux 3 sous-scores individuellement")

    conn.close()
    return resultat


def evaluer_univers():
    conn = get_conn()
    tickers = [r[0] for r in conn.execute("SELECT ticker FROM societes").fetchall()]
    conn.close()
    return [evaluer_titre(t) for t in tickers]


def rapport_fraicheur():
    """R7 — bilan de fraicheur sur l'ensemble de l'univers, a consulter avant
    toute lecture de la watchlist. Ne bloque rien : informe."""
    conn = get_conn()
    tickers = [r[0] for r in conn.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%'").fetchall()]
    perimes, frais, sans_donnee = [], [], []
    for t in tickers:
        cur = conn.cursor()
        per, fin_mois = per_le_plus_recent(cur, t)
        if per is None:
            sans_donnee.append(t)
            continue
        jours, perime = verifier_fraicheur(fin_mois)
        (perimes if perime else frais).append((t, fin_mois, jours))
    conn.close()
    return {
        "seuil_jours": SEUIL_FRAICHEUR_JOURS,
        "frais": sorted(frais, key=lambda x: -x[2]),
        "perimes": sorted(perimes, key=lambda x: -x[2]),
        "sans_donnee_marche": sans_donnee,
    }


if __name__ == "__main__":
    resultats = evaluer_univers()
    resultats.sort(key=lambda r: (r["score_composite"] is None,
                                  -(r["score_composite"] or 0)))
    fr = rapport_fraicheur()
    if fr["perimes"]:
        print(f"::warning:: {len(fr['perimes'])} titre(s) avec PER perime "
              f"(>{fr['seuil_jours']}j) : "
              + ", ".join(f"{t}({j}j)" for t, _, j in fr["perimes"]))
    print(json.dumps(resultats, ensure_ascii=False, indent=2))
