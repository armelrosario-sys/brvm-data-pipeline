#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard/glossaire_signaux.py — vocabulaire commun pour l'affichage des
signaux (table `signaux`), partage par bloc_signaux.py, generer_poste_decision.py
et generer_dashboard_html.py.

Cree le 14/07/2026 suite au retour utilisateur : les codes bruts
(SCREAMING_SNAKE_CASE) melanges a des phrases en minuscules rendaient la
lecture difficile, et les codes eux-memes etaient obscurs sans traduction.
Le code technique reste la cle stable (utilise par signaux.py, la base, les
tests) ; ce module ne fait QUE l'affichage, jamais la logique.
"""

SIGNAUX = {
    "D1_PREMIERE_PERTE": {"libelle": "Perte apres un exercice positif", "classe": "def",
        "description": "Le dernier exercice publié est en perte, après un exercice positif.",
        "recommandation": "Vérifier si la perte est exceptionnelle (charge ponctuelle, provision) ou structurelle (dégradation durable) avant toute décision."},
    "D2_CHUTE_RESULTAT": {"libelle": "Chute du resultat", "classe": "def",
        "description": "Le résultat net recule d'au moins 30% par rapport à l'exercice précédent (les deux positifs).",
        "recommandation": "Comparer au secteur : ce recul est-il propre au titre, ou une tendance qui touche tous ses pairs ?"},
    "D3_COUPE_DIVIDENDE": {"libelle": "Coupe de dividende", "classe": "def",
        "description": "Le dividende versé est inférieur à celui de l'exercice précédent.",
        "recommandation": "Distinguer une coupe subie (tension de trésorerie) d'une coupe choisie (réinvestissement stratégique) avant d'en tirer une conclusion."},
    "D4_RETARD_PUBLICATION": {"libelle": "Retard de publication", "classe": "def",
        "description": "Un retard de publication des comptes a été constaté et n'est pas encore résorbé.",
        "recommandation": "Un retard de gouvernance n'annonce pas forcément un problème financier, mais mérite une vigilance renforcée jusqu'à la prochaine publication."},
    "D4_RETARD_CALENDRIER": {"libelle": "Retard reglementaire", "classe": "def",
        "description": "Échéance réglementaire CREPMF dépassée sans nouveau dépôt (détecté automatiquement, sans avis officiel).",
        "recommandation": "Un retard de gouvernance n'annonce pas forcément un problème financier, mais mérite une vigilance renforcée jusqu'à la prochaine publication."},
    "D5_INFO_PERIMEE": {"libelle": "Information perimee", "classe": "def",
        "description": "Aucun document reçu depuis plus d'un an, toutes catégories confondues -- axe indépendant de D4, ne l'atténue jamais.",
        "recommandation": "Décider à l'aveugle sur une information de plus d'un an est risqué -- envisager de solliciter directement l'émetteur ou ta SGI pour des nouvelles récentes."},
    "A_QUALITE_DECOTEE":  {"libelle": "Decote qualifiee",     "classe": "fav",
        "description": "PER inférieur à 70% de la médiane sectorielle, résultat en progression, titre éligible.",
        "recommandation": "Correspond au profil recherché par la stratégie satellite -- une occasion à examiner, dans les limites du plafond satellite déjà fixé, jamais en dehors."},
    "B1_RECORD":          {"libelle": "Nouveau record",       "classe": "info",
        "description": "Le cours de clôture dépasse son plus-haut sur 12 mois (ou sur tout l'historique). Ni un signal d'achat, ni de vente en soi : une hausse portée par de vrais fondamentaux diffère d'une hausse spéculative.",
        "recommandation": "Pour une position détenue : bon moment pour vérifier si la thèse d'investissement initiale tient toujours, et si le poids de la ligne dans le portefeuille reste raisonnable."},
    "RERATING_EN_COURS":  {"libelle": "Re-rating en cours",   "classe": "fav",
        "description": "Le titre est sorti de sa décote par hausse du cours, fondamentaux inchangés.",
        "recommandation": "La décote qui justifiait l'entrée s'est résorbée -- vérifier si la thèse reste valable à ce niveau de prix, ou si une prise de gain partielle se justifie."},
}


import re as _re_resume


def resume_capital(code, detail):
    """Extrait l'information LA PLUS IMPORTANTE d'un detail de signal, de
    facon TOUJOURS VISIBLE et concise (15/07/2026, retour utilisateur : les
    phrases completes en texte simple, sans hierarchie, rendaient la lecture
    difficile). Le detail complet reste affiche a cote, ce resume n'efface
    rien -- il met juste le chiffre qui compte en evidence immediate."""
    if code in ("D1_PREMIERE_PERTE",):
        m = _re_resume.search(r"negatif \(([\d.\-]+) M FCFA\)", detail)
        return f"{float(m.group(1)):,.0f} M FCFA".replace(",", " ") if m else None
    if code == "D2_CHUTE_RESULTAT":
        m = _re_resume.search(r"recul de ([\d.]+)%", detail)
        return f"-{m.group(1)}% RN" if m else None
    if code == "D3_COUPE_DIVIDENDE":
        m = _re_resume.search(r"\(([\d.]+) FCFA\) < dividende \d+ \(([\d.]+) FCFA\)", detail)
        return f"{m.group(1)} < {m.group(2)} FCFA" if m else None
    if code in ("D4_RETARD_PUBLICATION", "D4_RETARD_CALENDRIER"):
        m = _re_resume.search(r"d[ée]pass[ée]e de (\d+)j", detail)
        return f"{m.group(1)}j de retard" if m else None
    if code == "D5_INFO_PERIMEE":
        m = _re_resume.search(r"depuis (\d+)j", detail)
        return f"{m.group(1)}j sans info" if m else None
    if code == "A_QUALITE_DECOTEE":
        m = _re_resume.search(r"PER ([\d.]+) < 70% de la m[ée]diane sectorielle ([\d.]+)", detail)
        return f"PER {m.group(1)} (m\u00e9d. {m.group(2)})" if m else None
    if code == "B1_RECORD":
        m = _re_resume.search(r"a ([\d\s]+) FCFA", detail)
        return f"{m.group(1).strip()} FCFA" if m else None
    if code == "RERATING_EN_COURS":
        m = _re_resume.search(r"\(([\d\s]+) -> ([\d\s]+) FCFA\)", detail)
        return f"{m.group(1).strip()} \u2192 {m.group(2).strip()} FCFA" if m else None
    return None


def libelle(code):
    """Libelle court, lisible, casse normale."""
    return SIGNAUX.get(code, {}).get("libelle", code)


def classe(code):
    """Classe CSS : def (defavorable), fav (favorable), info (neutre/attention)."""
    return SIGNAUX.get(code, {}).get("classe", "info")


def description(code):
    return SIGNAUX.get(code, {}).get("description", "")


_ICONES = {"def": "\u26a0", "fav": "\u2713", "info": "\u2139"}  # !, check, i — accessibilite (pas la seule couleur)


def badge_html(code, css_prefix="sig"):
    """Badge HTML complet : icone (accessibilite, pas seulement la couleur) +
    libelle clair + code technique, definition et recommandation en info-bulle."""
    lib, cls, desc = libelle(code), classe(code), description(code)
    icone = _ICONES.get(cls, "")
    reco = SIGNAUX.get(code, {}).get("recommandation", "")
    titre = f"{code} — {desc}" + (f" | À faire : {reco}" if reco else "")
    return (f'<span class="{css_prefix}-{cls}" title="{titre}">{icone} {lib}</span>')


def recommandation(code):
    """Recommandation associee a un type de signal -- jamais une directive
    d'achat/vente, toujours une invitation a verifier/reflechir (doctrine du
    projet : le systeme ne decide jamais seul)."""
    return SIGNAUX.get(code, {}).get("recommandation", "")


# --- Sizing (moteur/scoring.py) : traduction operationnelle des recommandations ---
# Ces 4 valeurs sont l'unique vocabulaire produit par le moteur (evaluer_titre).
# Le mapping ci-dessous traduit le mot-cle en phrase actionnable, sans jamais
# inventer de pourcentage ou de montant que le moteur n'a pas calcule lui-meme.
SIZING = {
    "PLEINE":   {"libelle": "Normal",  "classe": "ok",
        "description": "Liquidité jugée suffisante pour une entrée en une fois, sans précaution particulière."},
    "REDUITE":  {"libelle": "Reduit",        "classe": "mid",
        "description": "Liquidité limitée : réduire la taille de la ligne et étaler les achats sur plusieurs séances."},
    "MINIMALE": {"libelle": "Minimal", "classe": "bad",
        "description": "Marché quasi illiquide sur ce titre : n'engager qu'une position très réduite, sortie difficile."},
    "PRUDENCE": {"libelle": "Donnee manquante", "classe": "na",
        "description": "Aucune donnée de liquidité collectée pour ce titre (chantier de collecte en cours) : à défaut, traiter comme une taille minimale par prudence."},
}


def sizing_libelle(code):
    return SIZING.get(code, {}).get("libelle", code)


def sizing_classe(code):
    return SIZING.get(code, {}).get("classe", "na")


def sizing_description(code):
    return SIZING.get(code, {}).get("description", "")
