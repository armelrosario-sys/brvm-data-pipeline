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
    "D1_PREMIERE_PERTE":   {"libelle": "Premiere perte",      "classe": "def",
        "description": "Le dernier exercice publie est en perte, apres un exercice positif."},
    "D2_CHUTE_RESULTAT":   {"libelle": "Chute du resultat",   "classe": "def",
        "description": "Le resultat net recule d'au moins 30% par rapport a l'exercice precedent (les deux positifs)."},
    "D3_COUPE_DIVIDENDE":  {"libelle": "Coupe de dividende",  "classe": "def",
        "description": "Le dividende verse est inferieur a celui de l'exercice precedent."},
    "D4_RETARD_PUBLICATION": {"libelle": "Retard de publication", "classe": "def",
        "description": "Un retard de publication des comptes a ete constate et n'est pas encore resorbe."},
    "D4_RETARD_CALENDRIER": {"libelle": "Retard (calendrier)", "classe": "def",
        "description": "Ecart significatif au rythme historique de depot de ce titre (detecte automatiquement, sans avis officiel)."},
    "A_QUALITE_DECOTEE":  {"libelle": "Decote qualifiee",     "classe": "fav",
        "description": "PER inferieur a 70% de la mediane sectorielle, resultat en progression, titre eligible."},
    "B1_RECORD":          {"libelle": "Nouveau record",       "classe": "info",
        "description": "Le cours de cloture depasse son plus-haut sur 12 mois (ou sur tout l'historique)."},
    "RERATING_EN_COURS":  {"libelle": "Re-rating en cours",   "classe": "fav",
        "description": "Le titre est sorti de sa decote par hausse du cours, fondamentaux inchanges."},
}


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
    libelle clair + code technique et definition en info-bulle."""
    lib, cls, desc = libelle(code), classe(code), description(code)
    icone = _ICONES.get(cls, "")
    return (f'<span class="{css_prefix}-{cls}" title="{code} — {desc}">{icone} {lib}</span>')


# --- Sizing (moteur/scoring.py) : traduction operationnelle des recommandations ---
# Ces 4 valeurs sont l'unique vocabulaire produit par le moteur (evaluer_titre).
# Le mapping ci-dessous traduit le mot-cle en phrase actionnable, sans jamais
# inventer de pourcentage ou de montant que le moteur n'a pas calcule lui-meme.
SIZING = {
    "PLEINE":   {"libelle": "Normal",  "classe": "ok",
        "description": "Liquidite jugee suffisante pour une entree en une fois, sans precaution particuliere."},
    "REDUITE":  {"libelle": "Reduit",        "classe": "mid",
        "description": "Liquidite limitee : reduire la taille de la ligne et etaler les achats sur plusieurs seances."},
    "MINIMALE": {"libelle": "Minimal", "classe": "bad",
        "description": "Marche quasi illiquide sur ce titre : n'engager qu'une position tres reduite, sortie difficile."},
    "PRUDENCE": {"libelle": "Donnee manquante", "classe": "na",
        "description": "Aucune donnee de liquidite collectee pour ce titre (chantier de collecte en cours) : a defaut, traiter comme une taille minimale par prudence."},
}


def sizing_libelle(code):
    return SIZING.get(code, {}).get("libelle", code)


def sizing_classe(code):
    return SIZING.get(code, {}).get("classe", "na")


def sizing_description(code):
    return SIZING.get(code, {}).get("description", "")
