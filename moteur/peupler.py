#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Peuplement de la base BRVM depuis les CSV de reference de donnees/base/.

MIGRATION DU 27/09/2026. Jusqu'a cette date, les 449 lignes de donnees de
reference du projet vivaient en dur dans ce fichier, sous forme de tuples
Python : 184 etats financiers, 50 societes, 167 URL sources, et le reste.
Le fichier faisait 83 Ko pour 975 lignes. Trois consequences mesurees :

  - Corriger une valeur exigeait d'editer du code. La permutation des colonnes
    resultat_net / resultat_net_n1 d'ECOC et de BOAS, trouvee le 26/09 par
    moteur/arbitrage.py, a demande un remplacement de chaine dans un fichier
    source -- alors qu'il s'agissait de corriger deux nombres.
  - Aucun outil de donnees ne pouvait les lire : ni tableur, ni requete, ni
    diff lisible. Un changement de valeur apparaissait dans l'historique Git
    comme une modification de code.
  - Completer un exercice manquant (CFAC 2025, NEIC 2025, SICC 2024 sont
    toujours en attente) supposait de respecter l'arite d'un tuple de 13
    elements positionnels, sans en-tete pour se reperer.

Les donnees sont desormais dans donnees/base/, un CSV par table, avec une
colonne "note" qui porte les commentaires de provenance de l'ancienne saisie
-- document source, correction datee, reserve de lecture. Ces notes etaient
l'essentiel de la valeur du fichier : elles sont reprises integralement, y
compris les commentaires qui couraient sur plusieurs lignes.

Ce module ne contient plus aucune donnee. Pour en ajouter ou en corriger, on
edite le CSV concerne ; rien ici ne change.

REGLE D'UNITE (formalisee 11/07/2026, suite audit AUDCIF/SYSCOHADA) : avant
toute extraction, LIRE la mention d'unite ecrite sur le document lui-meme
("en milliers de F CFA" ou "en millions FCFA", quasi toujours presente en
en-tete du bilan) — JAMAIS la deviner ou la supposer par habitude. Pattern
observe et confirme sur de nombreux documents : comptes individuels SYSCOHADA
-> quasi systematiquement en MILLIERS (ex. FTSC, Unilever CI) ; comptes
consolides IFRS des grands groupes cotes (article 8 AUDCIF) -> en MILLIONS
(ex. Sonatel, ETI). Ce n'est pas arbitraire, c'est correle au referentiel
comptable utilise. Toute ligne ajoutee a etats_financiers.csv doit tracer,
dans sa colonne "note", la mention d'unite trouvee dans le document source.
Le controle croise (rapport_ordre_grandeur, scoring.py) reste un FILET DE
SECURITE en second rang, jamais le mecanisme principal.

Les lignes prefixees TEST_ sont SYNTHETIQUES et clairement etiquetees : elles
valident que le gate exclut des profils degrades qu'aucun titre reel ne
presentait. moteur/profils.py les ecarte par 'ticker NOT LIKE TEST_%'.
"""
import csv
import sqlite3
from datetime import date as _date
from pathlib import Path

_BASE = Path(__file__).resolve().parent
RACINE = _BASE.parent
DB = str(_BASE / "brvm.db")
DONNEES = RACINE / "donnees" / "base"

# Colonnes attendues par fichier, dans l'ordre. Sert de controle : un CSV dont
# l'en-tete ne correspond pas est refuse, plutot que lu de travers.
SCHEMA_CSV = {
    "societes.csv": [
        "ticker", "nom", "secteur", "referentiel", "pays", "compartiment",
        "actionnariat"],
    "etats_financiers.csv": [
        "ticker", "exercice", "resultat_net", "resultat_net_n1", "total_actif",
        "total_passif", "capitaux_propres", "dettes_financieres", "payout_ratio",
        "solvabilite_bancaire", "source_type", "statut_donnee", "date_publication"],
    "resultat_activites_ordinaires.csv": [
        "ticker", "exercice", "resultat_activites_ordinaires"],
    "resultat_exploitation.csv": [
        "ticker", "exercice", "resultat_exploitation", "resultat_financier", "source"],
    "resultats_intermediaires.csv": [
        "ticker", "exercice", "periode", "resultat_net", "resultat_net_n1",
        "produit_net_bancaire", "resultat_brut_exploitation", "cout_du_risque",
        "coefficient_exploitation", "statut_donnee", "date_publication",
        "source_url", "note_source"],
    "source_urls.csv": ["ticker", "exercice", "source_url"],
    "dividendes.csv": ["ticker", "montant_net", "date_paiement", "exercice_couvert"],
    "avis_reglementaires.csv": ["ticker", "type", "date_avis", "note_avis"],
}

# Colonnes a convertir. Tout le reste reste du texte ; une cellule vide devient
# toujours None, jamais 0 ni la chaine vide -- la distinction entre "zero" et
# "non renseigne" porte du sens dans toute la chaine en aval.
ENTIERS = {"exercice", "exercice_couvert"}
REELS = {
    "resultat_net", "resultat_net_n1", "total_actif", "total_passif",
    "capitaux_propres", "dettes_financieres", "payout_ratio",
    "solvabilite_bancaire", "resultat_activites_ordinaires",
    "resultat_exploitation", "resultat_financier", "produit_net_bancaire",
    "resultat_brut_exploitation", "cout_du_risque", "coefficient_exploitation",
    "montant_net"}


def _valeur(colonne, brut):
    if brut is None or brut == "":
        return None
    if colonne in ENTIERS:
        return int(brut)
    if colonne in REELS:
        return float(brut)
    return brut


def lire(fichier):
    """Lit un CSV de donnees/base/ et rend une liste de tuples, colonne "note"
    exclue. L'en-tete est verifie : une colonne renommee, ajoutee ou deplacee
    fait echouer ici, avec un message, plutot que de decaler silencieusement
    les valeurs d'une colonne -- le mode de defaillance le plus couteux de
    tout le projet (cf. permutation ECOC/BOAS)."""
    chemin = DONNEES / fichier
    attendu = SCHEMA_CSV[fichier]
    if not chemin.exists():
        raise SystemExit("Fichier de reference absent : %s" % chemin)
    with chemin.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        entete = [c for c in (lecteur.fieldnames or []) if c != "note"]
        if entete != attendu:
            raise SystemExit(
                "En-tete inattendu dans %s\n  attendu   : %s\n  trouve    : %s"
                % (fichier, ", ".join(attendu), ", ".join(entete)))
        return [tuple(_valeur(c, ligne[c]) for c in attendu) for ligne in lecteur]


def main():
    societes = lire("societes.csv")
    etats = lire("etats_financiers.csv")
    rao = lire("resultat_activites_ordinaires.csv")
    exploitation = lire("resultat_exploitation.csv")
    intermediaires = lire("resultats_intermediaires.csv")
    source_urls = lire("source_urls.csv")
    dividendes = lire("dividendes.csv")
    avis = lire("avis_reglementaires.csv")

    conn = sqlite3.connect(DB)
    conn.executescript(open(_BASE / "schema.sql", encoding="utf-8").read())
    cur = conn.cursor()
    cur.executemany(
        "INSERT OR REPLACE INTO societes VALUES (?,?,?,?,?,?,?)", societes)
    cur.executemany(
        "INSERT OR REPLACE INTO etats_financiers "
        "(ticker,exercice,resultat_net,resultat_net_n1,total_actif,total_passif,"
        "capitaux_propres,dettes_financieres,payout_ratio,solvabilite_bancaire,"
        "source_type,statut_donnee,date_publication) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        etats)
    cur.executemany(
        "UPDATE etats_financiers SET resultat_activites_ordinaires=? "
        "WHERE ticker=? AND exercice=?",
        [(v, t, e) for t, e, v in rao])
    cur.executemany(
        "INSERT OR REPLACE INTO resultats_intermediaires "
        "(ticker,exercice,periode,resultat_net,resultat_net_n1,produit_net_bancaire,"
        "resultat_brut_exploitation,cout_du_risque,coefficient_exploitation,"
        "statut_donnee,date_publication,source_url,note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", intermediaires)
    cur.executemany(
        "UPDATE etats_financiers SET resultat_exploitation=?, resultat_financier=? "
        "WHERE ticker=? AND exercice=?",
        [(re_, rf, t, e) for t, e, re_, rf, _src in exploitation])
    cur.executemany(
        "UPDATE etats_financiers SET source_url=? WHERE ticker=? AND exercice=?",
        [(url, t, e) for t, e, url in source_urls])
    cur.executemany(
        "INSERT INTO dividendes (ticker,montant_net,date_paiement,exercice_couvert) "
        "VALUES (?,?,?,?)", dividendes)
    cur.executemany(
        "INSERT INTO avis_reglementaires (ticker,type,date_avis,note) VALUES (?,?,?,?)",
        avis)

    # Liste de suivi (15/07/2026) : lue depuis config/liste_suivi.yaml --
    # CODES SEULS, jamais de quantite ni de prix (doctrine du projet).
    import yaml as _yaml
    chemin_suivi = RACINE / "config" / "liste_suivi.yaml"
    if chemin_suivi.exists():
        cfg_suivi = _yaml.safe_load(chemin_suivi.read_text()) or {}
        tickers_suivi = cfg_suivi.get("titres", [])
        cur.execute("DELETE FROM liste_suivi")  # repart de la liste du fichier
        cur.executemany(
            "INSERT INTO liste_suivi (ticker, date_ajout, note) VALUES (?,?,NULL)",
            [(t, _date.today().isoformat()) for t in tickers_suivi])

    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM societes").fetchone()[0]
    m = cur.execute("SELECT COUNT(*) FROM etats_financiers").fetchone()[0]
    print("Base peuplee : %d societes, %d lignes d'etats financiers "
          "(source : donnees/base/)." % (n, m))
    conn.close()


if __name__ == "__main__":
    main()
