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


def normaliser_dates_dividendes(lignes):
    """date_paiement en ISO a l'entree (chantier C10, 30/09/2026).

    donnees/base/dividendes.csv est deja ISO (12 dates) ou vide (3) : cette
    garde ne change aujourd'hui aucune valeur. Elle est la pour que la table
    ne puisse plus MELANGER deux formats, quel que soit le chargeur -- c'est
    le melange, et non le format francais en soi, qui cassait le tri
    `ORDER BY date_paiement DESC` et l'extraction d'annee de scoring.py.
    Une date illisible arrete le peuplement : elle n'est jamais devinee, et
    elle n'entre pas non plus en base telle quelle.
    """
    import sys as _sys
    _sys.path.insert(0, str(RACINE / "collecte"))
    from dates_dividendes import vers_iso
    i_date = SCHEMA_CSV["dividendes.csv"].index("date_paiement")
    sorties = []
    for ligne in lignes:
        brute = ligne[i_date]
        if brute in (None, ""):
            sorties.append(ligne)
            continue
        iso = vers_iso(brute)
        if iso is None:
            raise SystemExit(
                "Date de paiement illisible dans donnees/base/dividendes.csv : "
                "%r (ticker %s). Un mois non reconnu ou un jour inexistant ne se "
                "devine pas : corriger la ligne." % (brute, ligne[0]))
        sorties.append(ligne[:i_date] + (iso,) + ligne[i_date + 1:])
    return sorties


def main():
    societes = lire("societes.csv")
    etats = lire("etats_financiers.csv")
    rao = lire("resultat_activites_ordinaires.csv")
    exploitation = lire("resultat_exploitation.csv")
    intermediaires = lire("resultats_intermediaires.csv")
    source_urls = lire("source_urls.csv")
    dividendes = normaliser_dates_dividendes(lire("dividendes.csv"))
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
    # Idempotence (28/09/2026) : ces deux tables n'ont PAS de cle unique -- leur
    # seule clef est un id AUTOINCREMENT. Un INSERT simple y rejouait donc la
    # totalite du CSV a chaque passage, et app.py::preparer_base() relance
    # peupler.py sur une base EXISTANTE des que l'empreinte des sources change,
    # en annoncant une "reconstruction" qui n'en est pas une. Mesure du
    # 28/09/2026 : +15 dividendes et +16 avis par passage, croissance lineaire
    # non bornee (311/16 -> 326/32 -> 341/48 -> 356/64 -> 371/80).
    #
    # Ce n'etait pas cosmetique. appliquer_gate() COMPTE les avis :
    #   retards = avis(cur, ticker, "RETARD_PUBLICATION")
    #   if len(retards) >= fx["retards_publication"]["defauts_max"]  # seuil 2
    # SDSC porte UN retard de publication (2025-04-30, confirme par ses propres
    # commissaires aux comptes). Duplique, il en porte deux : le seuil tombe et
    # le titre passe de ELIGIBLE a EXCLU. Le collecte/profils.json commite
    # portait ce verdict corrompu.
    #
    # Le correctif deduplique a l'insertion plutot que de vider les tables :
    # charger_dividendes_exercice.py (296 lignes) et collecte_boc_quotidien.py
    # ecrivent dans dividendes eux aussi, et app.py ne les relance PAS -- un
    # DELETE ici les effacerait sans les rebatir. L'operateur IS est retenu
    # plutot que = parce qu'il est NULL-safe : trois dividendes SDSC ont une
    # date_paiement nulle, et "NULL = NULL" est faux en SQL, ce qui laisserait
    # passer le doublon. Clefs naturelles verifiees uniques dans les deux CSV.
    cur.executemany(
        "INSERT INTO dividendes (ticker,montant_net,date_paiement,exercice_couvert) "
        "SELECT ?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM dividendes "
        "WHERE ticker IS ? AND montant_net IS ? AND date_paiement IS ? "
        "AND exercice_couvert IS ?)",
        [d + d for d in dividendes])
    cur.executemany(
        "INSERT INTO avis_reglementaires (ticker,type,date_avis,note) "
        "SELECT ?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM avis_reglementaires "
        "WHERE ticker IS ? AND type IS ? AND date_avis IS ?)",
        [a + a[:3] for a in avis])

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
