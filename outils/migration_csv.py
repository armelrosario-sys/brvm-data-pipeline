#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""outils/migration_csv.py — sortie des donnees de reference vers donnees/base/.

MIGRATION A USAGE UNIQUE (27/09/2026), executee par le workflow
.github/workflows/migration_csv.yml. Elle est IDEMPOTENTE : relancee apres
coup, elle constate que peupler.py lit deja les CSV et ne fait rien.

CE QU'ELLE FAIT
  1. Construit la base avec le peupler.py ACTUEL et en prend une empreinte.
  2. Extrait les 449 lignes de donnees codees en dur (184 etats financiers,
     50 societes, 167 URL sources, et le reste) vers 8 CSV dans donnees/base/,
     en rapatriant les commentaires de provenance en colonne "note".
  3. Remplace peupler.py (975 -> 190 lignes, plus aucune donnee) et
     fusionner_fondamentaux.py, qui INJECTAIT des tuples Python dans le texte
     de peupler.py et levait ValueError des que cette structure changeait --
     en premiere etape du workflow P4, qui s'execute sous bash -e.
  4. Corrige les quatre scripts qui lisaient le TEXTE de peupler.py par
     expression reguliere, dont collecte/avis_brvm.py : il rendait un
     dictionnaire VIDE sans rien signaler si la structure changeait, ce qui
     aurait fait tourner la veille P13 tous les jours sans reconnaitre aucun
     titre. Il echoue desormais bruyamment. Elle etend aussi l'empreinte de
     cache d'app.py aux CSV, sans quoi corriger un resultat net ne
     reconstruirait pas la base affichee.
  5. Reconstruit la base et EXIGE qu'elle soit identique a l'originale, table
     par table, colonne par colonne. Toute divergence interrompt la migration.

Chaque remplacement de texte porte sur une ancre qui doit apparaitre
EXACTEMENT une fois. Le 24/09/2026, un remplacement par ancrage dont l'ancre
n'existait pas avait tronque app.py de 943 a 444 lignes sans lever d'erreur.

Usage : python3 outils/migration_csv.py   (depuis la racine du depot)
"""
import ast
import csv
import io
import json
import sqlite3
import subprocess
import sys
import tokenize
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MOTEUR = RACINE / "moteur"
DONNEES = RACINE / "donnees" / "base"

NOUVEAU_PEUPLER = r'''#!/usr/bin/env python3
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
'''

NOUVEAU_FUSIONNER = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/fusionner_fondamentaux.py — (27/07/2026, reecrit le 27/09/2026).

Fusionne collecte/fondamentaux_extraits.csv (lignes auto-extraites, Piste A)
dans donnees/base/etats_financiers.csv.

REECRITURE DU 27/09/2026. Jusqu'ici, ce script inserait du TEXTE PYTHON dans
moteur/peupler.py : il cherchait la chaine "ETATS = [", localisait le "\\n]"
suivant, et y injectait des tuples formates a la main. Apres la sortie des
donnees vers donnees/base/, cette chaine n'existe plus et le script levait
"ValueError: substring not found" -- en PREMIERE etape du workflow P4, qui
s'execute sous bash -e : le workflow entier serait tombe. Il ecrit desormais
des lignes de CSV, ce qui supprime la chirurgie sur le code source.

Regle absolue, inchangee : n'AJOUTE que des couples (ticker, exercice)
absents du fichier. Ne modifie, ne supprime, ne recalcule JAMAIS une ligne
deja presente -- meme si le meme couple existe en PROBABLE dans le CSV
source, une entree manuelle existante (meme moins bonne) reste prioritaire,
parce qu'elle a ete relue par un humain. Champs absents de l'extraction
automatique (dettes financieres, payout, solvabilite bancaire) : vides,
jamais devines.

Usage : python3 moteur/fusionner_fondamentaux.py
"""
import csv
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "donnees" / "base" / "etats_financiers.csv"
SOURCE = RACINE / "collecte" / "fondamentaux_extraits.csv"

# Garde-fou (28/07/2026, suite a l'incident BOABF/2026 -- document mal
# identifie, ticker et exercice tous deux faux, jamais filtre avant d'entrer
# dans la base malgre une valeur x1000 au-dela du plausible). Meme plafond que
# le golden test "plafond de plausibilite" (seuils.yaml), applique ICI, a la
# fusion, pas seulement a la verification a posteriori.
PLAFOND_RN_M_FCFA = 1_000_000

COLONNES = [
    "ticker", "exercice", "resultat_net", "resultat_net_n1", "total_actif",
    "total_passif", "capitaux_propres", "dettes_financieres", "payout_ratio",
    "solvabilite_bancaire", "source_type", "statut_donnee", "date_publication",
    "note"]


def date_pub_depuis_nom_fichier(url):
    """Le nom des rapports BRVM commence par la date de depot (AAAAMMJJ) --
    c'est la meilleure approximation disponible de la date de publication,
    faute de l'avoir extraite explicitement du texte du PDF."""
    m = re.search(r"/(\d{8})[_-]", url or "")
    if not m:
        return ""
    s = m.group(1)
    return "%s-%s-%s" % (s[:4], s[4:6], s[6:])


def to_num(s):
    return float(s) if s not in (None, "") else None


def _texte(x):
    return "" if x is None else repr(x) if isinstance(x, float) else str(x)


def main():
    if not CIBLE.exists():
        raise SystemExit("Fichier de reference absent : %s" % CIBLE)
    with CIBLE.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        if lecteur.fieldnames != COLONNES:
            raise SystemExit(
                "En-tete inattendu dans %s\n  attendu : %s\n  trouve  : %s"
                % (CIBLE.name, ", ".join(COLONNES), ", ".join(lecteur.fieldnames or [])))
        existants = set()
        for ligne in lecteur:
            try:
                existants.add((ligne["ticker"], int(ligne["exercice"])))
            except (TypeError, ValueError):
                continue

    ajouts = []
    with SOURCE.open(newline="", encoding="utf-8") as f:
        lignes_source = list(csv.DictReader(f))
    for row in lignes_source:
        if not row.get("exercice"):
            continue  # rien d'exploitable comme cle sans exercice
        cle = (row["ticker"], int(row["exercice"]))
        if cle in existants:
            continue  # ne remplace jamais une entree deja presente
        rn = to_num(row["resultat_net"])
        rn1 = to_num(row["resultat_net_n1"])
        if (rn is not None and abs(rn) > PLAFOND_RN_M_FCFA) or \
           (rn1 is not None and abs(rn1) > PLAFOND_RN_M_FCFA):
            print("[ecarte] %s/%s : resultat net (%s) ou N-1 (%s) au-dela du plafond "
                  "de plausibilite (%d M FCFA) -- jamais fusionne, a verifier "
                  "manuellement (source : %s)"
                  % (row["ticker"], row["exercice"], rn, rn1, PLAFOND_RN_M_FCFA,
                     row.get("source_url", "")))
            existants.add(cle)  # ne plus jamais retenter cette ligne precise
            continue
        note = ("Fusion auto %s (Piste A, strategie=%s) -- %s"
                % (__import__("datetime").date.today().isoformat(),
                   row.get("strategie") or "?", row.get("note") or "")).strip()
        ajouts.append([
            row["ticker"], row["exercice"], _texte(rn), _texte(rn1),
            _texte(to_num(row["total_actif"])), _texte(to_num(row["total_passif"])),
            _texte(to_num(row["capitaux_propres"])), "", "", "",
            row["source_type"], row["statut_donnee"],
            date_pub_depuis_nom_fichier(row.get("source_url")), note])
        existants.add(cle)  # evite un doublon si le CSV source contient 2 fois le couple

    if not ajouts:
        print("Rien a fusionner : tous les couples (ticker, exercice) existent deja.")
        return

    with CIBLE.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(ajouts)

    print("%d nouvelle(s) ligne(s) ajoutee(s) a %s (sur %d lignes source, le reste "
          "existait deja). Dettes financieres, payout et solvabilite bancaire sont "
          "laisses VIDES : absents de l'extraction automatique, jamais devines."
          % (len(ajouts), CIBLE.name, len(lignes_source)))


if __name__ == "__main__":
    main()
'''

# Correctifs des fichiers qui lisaient le TEXTE de peupler.py, plus
# l'empreinte de cache d'app.py. Chaque entree est [ancre, remplacement] ;
# l'ancre porte son contexte et doit etre unique dans le fichier. Les blocs
# dont les contextes se touchaient ont ete fusionnes : sans cela, le premier
# remplacement detruirait l'ancre du suivant.
PATCHES_JSON = r'''{"collecte/avis_brvm.py": [["\n\ndef charger_tickers():\n    \"\"\"Correspondance nom BRVM -> ticker, lue depuis peupler.py pour rester\n    l'unique source de verite du projet (pas de second dictionnaire a maintenir).\"\"\"\n    src = (ICI.parent / \"moteur\" / \"peupler.py\").read_text(encoding=\"utf-8\")\n    m = re.search(r\"^SOCIETES\\s*=\\s*\\[(.*?)^\\]\", src, re.S | re.M)\n    table = {}\n    if not m:\n        return table\n    for ligne in m.group(1).split(\"\\n\"):\n        t = re.match(r'\\s*\\(\"([A-Z0-9]+)\"\\s*,\\s*\"([^\"]+)\"', ligne)\n        if t:\n            nom = t.group(2)\n            table[reduire(nom)] = t.group(1)\n            sans_parenthese = re.sub(r\"\\s*\\([^)]*\\)\", \"\", nom).strip()\n            if sans_parenthese and sans_parenthese != nom:\n                table[reduire(sans_parenthese)] = t.group(1)\n    return table\n\n\n", "\n\ndef charger_tickers():\n    \"\"\"Correspondance nom BRVM -> ticker, lue depuis donnees/base/societes.csv,\n    unique source de verite du projet (pas de second dictionnaire a maintenir).\n\n    27/09/2026 : lisait auparavant le TEXTE de peupler.py par expression\n    reguliere, et rendait un dictionnaire VIDE si la structure du fichier\n    changeait -- sans rien signaler. La veille P13 aurait alors tourne tous\n    les jours en ne reconnaissant aucun titre, donc en n'enregistrant aucun\n    avis, sans qu'aucune erreur n'apparaisse. On echoue desormais bruyamment.\"\"\"\n    import csv\n    chemin = ICI.parent / \"donnees\" / \"base\" / \"societes.csv\"\n    if not chemin.exists():\n        raise SystemExit(\"Referentiel des societes introuvable : %s\" % chemin)\n    table = {}\n    with chemin.open(encoding=\"utf-8\", newline=\"\") as f:\n        for ligne in csv.DictReader(f):\n            ticker, nom = ligne.get(\"ticker\"), ligne.get(\"nom\")\n            if not ticker or not nom or ticker.startswith(\"TEST_\"):\n                continue  # les fixtures synthetiques ne sont pas des titres cotes\n            table[reduire(nom)] = ticker\n            sans_parenthese = re.sub(r\"\\s*\\([^)]*\\)\", \"\", nom).strip()\n            if sans_parenthese and sans_parenthese != nom:\n                table[reduire(sans_parenthese)] = ticker\n    if not table:\n        raise SystemExit(\"Referentiel des societes vide : %s\" % chemin)\n    return table\n\n\n"]], "collecte/extraire_lot.py": [["\n\ndef charger_referentiels():\n    \"\"\"ticker -> referentiel_comptable, lu directement dans SOCIETES\n    (peupler.py) -- evite de dependre d'une base SQLite deja construite.\"\"\"\n    src = (RACINE / \"moteur\" / \"peupler.py\").read_text(encoding=\"utf-8\")\n    m = re.search(r\"SOCIETES = \\[(.*?)\\n\\]\", src, re.S)\n    lignes = re.findall(r'\\(\"([A-Z_]+)\",\\s*\"[^\"]*\",\\s*\"[^\"]*\",\\s*\"([A-Z_]+)\"', m.group(1))\n    return dict(lignes)\n\n\ndef documents_a_traiter(mapping, traites_set):\n", "\n\ndef charger_referentiels():\n    \"\"\"ticker -> referentiel_comptable, lu dans donnees/base/societes.csv --\n    evite de dependre d'une base SQLite deja construite.\n\n    27/09/2026 : lisait le TEXTE de peupler.py, d'ou les donnees ont ete sorties.\"\"\"\n    chemin = RACINE / \"donnees\" / \"base\" / \"societes.csv\"\n    if not chemin.exists():\n        raise SystemExit(\"Referentiel des societes introuvable : %s\" % chemin)\n    with chemin.open(encoding=\"utf-8\", newline=\"\") as f:\n        return {r[\"ticker\"]: r[\"referentiel\"] for r in csv.DictReader(f)\n                if r.get(\"ticker\") and r.get(\"referentiel\")}\n\n\ndef documents_a_traiter(mapping, traites_set):\n"]], "collecte/preparer_integration.py": [["\nUsage : python3 collecte/preparer_integration.py\n\"\"\"\nimport json\nimport re\nfrom pathlib import Path\n\nRACINE = Path(__file__).resolve().parent.parent\nPROPOSITIONS = RACINE / \"collecte\" / \"propositions_extraction\"\nPEUPLER = RACINE / \"moteur\" / \"peupler.py\"\nSORTIE = RACINE / \"collecte\" / \"candidats_integration.txt\"\n\n\ndef charger_exercices_existants():\n    \"\"\"(ticker, exercice) deja presents dans ETATS -- jamais ecrases.\"\"\"\n    src = PEUPLER.read_text(encoding=\"utf-8\")\n    m = re.search(r\"^ETATS = \\[(.*?)\\n\\]\", src, re.S | re.M)\n    lignes = re.findall(r'\\(\"([A-Z_]+)\",\\s*(\\d{4}),', m.group(1))\n    return {(t, int(e)) for t, e in lignes}\n\n\ndef date_depuis_nom_fichier(nom):\n", "\nUsage : python3 collecte/preparer_integration.py\n\"\"\"\nimport csv\nimport json\nimport re\nfrom pathlib import Path\n\nRACINE = Path(__file__).resolve().parent.parent\nPROPOSITIONS = RACINE / \"collecte\" / \"propositions_extraction\"\nPEUPLER = RACINE / \"moteur\" / \"peupler.py\"  # conserve : cite dans les messages\nETATS_CSV = RACINE / \"donnees\" / \"base\" / \"etats_financiers.csv\"\nSORTIE = RACINE / \"collecte\" / \"candidats_integration.txt\"\n\n\ndef charger_exercices_existants():\n    \"\"\"(ticker, exercice) deja presents en base -- jamais ecrases.\n\n    27/09/2026 : lu depuis donnees/base/etats_financiers.csv, ou les donnees\n    ont ete sorties de peupler.py.\"\"\"\n    if not ETATS_CSV.exists():\n        raise SystemExit(\"Referentiel des etats financiers introuvable : %s\" % ETATS_CSV)\n    with ETATS_CSV.open(encoding=\"utf-8\", newline=\"\") as f:\n        out = set()\n        for r in csv.DictReader(f):\n            try:\n                out.add((r[\"ticker\"], int(r[\"exercice\"])))\n            except (TypeError, ValueError, KeyError):\n                continue\n        return out\n\n\ndef date_depuis_nom_fichier(nom):\n"]], "moteur/calendrier.py": [["    return \"autre\"\n\n\ndef construire_mapping(peupler_path):\n    \"\"\"Derive ticker -> slug de fichier depuis SOCIETES (peupler.py) et les\n    slugs reellement observes dans le MANIFESTE. Jamais fige en dur.\"\"\"\n    src = peupler_path.read_text()\n    m = re.search(r\"SOCIETES = \\[(.*?)\\n\\]\", src, re.S)\n    lignes = re.findall(r'\\(\"([A-Z_]+)\",\\s*\"([^\"]+)\"', m.group(1))\n    noms = {t: n for t, n in lignes if not t.startswith(\"TEST_\")}\n\n    rows = list(csv.DictReader(open(MANIFESTE, encoding=\"utf-8\")))\n    slugs_fichiers = Counter()\n", "    return \"autre\"\n\n\ndef construire_mapping(_peupler_path=None):\n    \"\"\"Derive ticker -> slug de fichier depuis donnees/base/societes.csv et les\n    slugs reellement observes dans le MANIFESTE. Jamais fige en dur.\n\n    27/09/2026 : lisait le TEXTE de peupler.py, d'ou les donnees ont ete\n    sorties. Le parametre est conserve pour ne pas casser les appelants ;\n    il n'est plus utilise.\"\"\"\n    chemin = RACINE / \"donnees\" / \"base\" / \"societes.csv\"\n    if not chemin.exists():\n        raise SystemExit(\"Referentiel des societes introuvable : %s\" % chemin)\n    with chemin.open(encoding=\"utf-8\", newline=\"\") as f:\n        noms = {r[\"ticker\"]: r[\"nom\"] for r in csv.DictReader(f)\n                if r.get(\"ticker\") and not r[\"ticker\"].startswith(\"TEST_\")}\n\n    rows = list(csv.DictReader(open(MANIFESTE, encoding=\"utf-8\")))\n    slugs_fichiers = Counter()\n"]], "moteur/arbitrage.py": [["        return dict(vide, regle=4, drapeau=\"FONDAMENTAL_EN_RETARD\", mesures=mesures,\n                    detail=\"exercice %d disponible chez l'agregateur (resultat net %s) \"\n                           \"alors que la base s'arrete a %d : le profil porte sur des \"\n                           \"comptes perimes, saisir l'exercice manquant dans peupler.py\"\n                           % (ex_agr, _fr(agr[\"rn\"]), ex_base))\n\n    if croi_agr is None:\n", "        return dict(vide, regle=4, drapeau=\"FONDAMENTAL_EN_RETARD\", mesures=mesures,\n                    detail=\"exercice %d disponible chez l'agregateur (resultat net %s) \"\n                           \"alors que la base s'arrete a %d : le profil porte sur des \"\n                           \"comptes perimes, saisir l'exercice manquant dans \"\n                           \"donnees/base/etats_financiers.csv\"\n                           % (ex_agr, _fr(agr[\"rn\"]), ex_base))\n\n    if croi_agr is None:\n"], ["                        axe_retire=True, mesures=mesures,\n                        detail=\"colonnes resultat_net et resultat_net_n1 vraisemblablement \"\n                               \"permutees sur l'exercice %d : %s. CORRECTION A PORTER dans \"\n                               \"moteur/peupler.py : remplacer (\\\"%s\\\", %d, %s, %s, ...) par \"\n                               \"(\\\"%s\\\", %d, %s, %s, ...) apres verification du document \"\n                               \"source.\"\n                               % (ex_base, \" ; \".join(preuves), ticker, ex_base,\n                                  _py(rn), _py(rn_n1), ticker, ex_base, _py(rn_n1), _py(rn)))\n\n    # --- Regle 1 : concordance. Deux lectures independantes des memes comptes\n    # publies se rejoignent : la transcription est corroboree.\n", "                        axe_retire=True, mesures=mesures,\n                        detail=\"colonnes resultat_net et resultat_net_n1 vraisemblablement \"\n                               \"permutees sur l'exercice %d : %s. CORRECTION A PORTER dans \"\n                               \"donnees/base/etats_financiers.csv : sur la ligne %s/%d, \"\n                               \"echanger resultat_net (%s) et resultat_net_n1 (%s) apres \"\n                               \"verification du document source.\"\n                               % (ex_base, \" ; \".join(preuves), ticker, ex_base,\n                                  _py(rn), _py(rn_n1)))\n\n    # --- Regle 1 : concordance. Deux lectures independantes des memes comptes\n    # publies se rejoignent : la transcription est corroboree.\n"], ["\n\ndef _py(x):\n    \"\"\"Reproduit le litteral Python tel qu'il figure dans peupler.py.\"\"\"\n    if x is None:\n        return \"None\"\n    return str(int(x)) if float(x).is_integer() else repr(x)\n", "\n\ndef _py(x):\n    \"\"\"Reproduit la valeur telle qu'elle figure dans le CSV de reference.\"\"\"\n    if x is None:\n        return \"None\"\n    return str(int(x)) if float(x).is_integer() else repr(x)\n"]], "moteur/tester_donnees.py": [["def test_fraicheur():\n    print(\"\\n=== 1. Fraicheur des donnees (non bloquant) ===\")\n    if not DB.exists():\n        verifie(False, \"brvm.db absente — lancer peupler.py puis charger_cours*.py\",\n                bloquant=False)\n        return\n    cur = sqlite3.connect(DB).cursor()\n", "def test_fraicheur():\n    print(\"\\n=== 1. Fraicheur des donnees (non bloquant) ===\")\n    if not DB.exists():\n        verifie(False, \"brvm.db absente — lancer moteur/peupler.py puis charger_cours*.py\",\n                bloquant=False)\n        return\n    cur = sqlite3.connect(DB).cursor()\n"], ["        verifie(v[\"bloquant\"] and v[\"axe_retire\"] and not v[\"correctif\"],\n                f\"regle 5 : {t} bloque le profil et retire l'axe sans reecrire \"\n                f\"la base (bloquant={v['bloquant']}, correctif={v['correctif']})\")\n        verifie(\"peupler.py\" in (v[\"detail\"] or \"\"),\n                f\"regle 5 : le detail de {t} nomme la correction a porter dans peupler.py\")\n    verifie(arb.arbitrer(cur, \"CONCORDE\", {})[\"regle\"] == 0,\n            \"agregateur absent : l'arbitrage se retire sans bloquer le moteur\")\n    verifie(arb.arbitrer(cur, \"INCONNU\", agr)[\"regle\"] == 0,\n", "        verifie(v[\"bloquant\"] and v[\"axe_retire\"] and not v[\"correctif\"],\n                f\"regle 5 : {t} bloque le profil et retire l'axe sans reecrire \"\n                f\"la base (bloquant={v['bloquant']}, correctif={v['correctif']})\")\n        verifie(\"etats_financiers.csv\" in (v[\"detail\"] or \"\"),\n                f\"regle 5 : le detail de {t} nomme le fichier ou porter la correction\")\n    verifie(arb.arbitrer(cur, \"CONCORDE\", {})[\"regle\"] == 0,\n            \"agregateur absent : l'arbitrage se retire sans bloquer le moteur\")\n    verifie(arb.arbitrer(cur, \"INCONNU\", agr)[\"regle\"] == 0,\n"], ["                                              \"PERMUTATION_SUSPECTEE\"))\n    verifie(not permutations,\n            \"aucune permutation de colonnes ouverte — a corriger dans \"\n            f\"moteur/peupler.py : {permutations}\" if permutations\n            else \"aucune permutation de colonnes ouverte dans la base\")\n\n    retards = sorted(t for t, v in verdicts.items()\n                     if v[\"drapeau\"] == \"FONDAMENTAL_EN_RETARD\")\n    verifie(not retards,\n            \"aucun exercice publie manquant en base — a saisir dans \"\n            f\"moteur/peupler.py : {retards}\" if retards\n            else \"aucun exercice publie manquant en base\",\n            bloquant=False)\n\n", "                                              \"PERMUTATION_SUSPECTEE\"))\n    verifie(not permutations,\n            \"aucune permutation de colonnes ouverte — a corriger dans \"\n            f\"donnees/base/etats_financiers.csv : {permutations}\" if permutations\n            else \"aucune permutation de colonnes ouverte dans la base\")\n\n    retards = sorted(t for t, v in verdicts.items()\n                     if v[\"drapeau\"] == \"FONDAMENTAL_EN_RETARD\")\n    verifie(not retards,\n            \"aucun exercice publie manquant en base — a saisir dans \"\n            f\"donnees/base/etats_financiers.csv : {retards}\" if retards\n            else \"aucun exercice publie manquant en base\",\n            bloquant=False)\n\n"], ["                f\"(absents : {muets})\")\n\n\ndef main():\n    sans_app = \"--sans-app\" in sys.argv\n    print(\"=\" * 60)\n", "                f\"(absents : {muets})\")\n\n\n\n# ----------------------------------------------------------------------\n# 13. BASE DE REFERENCE EN CSV (bloquant)\n# ----------------------------------------------------------------------\ndef test_base_reference():\n    \"\"\"Les donnees de reference du projet vivent dans donnees/base/.\n\n    POURQUOI CETTE SECTION EXISTE (27/09/2026). Jusqu'a cette date, les 449\n    lignes de reference etaient des tuples Python codes en dur dans\n    moteur/peupler.py (83 Ko, 975 lignes). Quatre scripts en tiraient leurs\n    correspondances par EXPRESSION REGULIERE sur le texte du fichier --\n    dont collecte/avis_brvm.py, qui tourne tous les jours dans P13 et qui\n    rendait un dictionnaire VIDE, sans rien signaler, si la structure\n    changeait. La veille aurait alors tourne quotidiennement en ne\n    reconnaissant aucun titre.\n\n    Ces tests verifient que la base de reference est lisible, complete et\n    coherente, et qu'aucune donnee n'est revenue se loger dans le code.\n    \"\"\"\n    print(\"\\n=== 13. Base de reference en CSV (bloquant) ===\")\n    base = RACINE / \"donnees\" / \"base\"\n    if not base.exists():\n        verifie(False, f\"dossier {base} absent : la base de reference a disparu\")\n        return\n\n    # Effectifs attendus au moment de la migration. Ces nombres NE SONT PAS\n    # figes : ils doivent croitre (exercices ajoutes, societes nouvelles).\n    # Le test attrape une CHUTE, qui signalerait une troncature ou un\n    # ecrasement de fichier -- pas une augmentation, qui est le but.\n    PLANCHERS = {\n        \"societes.csv\": 50,\n        \"etats_financiers.csv\": 184,\n        \"resultat_activites_ordinaires.csv\": 11,\n        \"resultat_exploitation.csv\": 3,\n        \"resultats_intermediaires.csv\": 3,\n        \"source_urls.csv\": 167,\n        \"dividendes.csv\": 15,\n        \"avis_reglementaires.csv\": 16,\n    }\n    import csv as _csv\n    contenus = {}\n    for fichier, plancher in sorted(PLANCHERS.items()):\n        chemin = base / fichier\n        if not chemin.exists():\n            verifie(False, f\"{fichier} absent de donnees/base/\")\n            continue\n        with chemin.open(encoding=\"utf-8\", newline=\"\") as f:\n            lignes = list(_csv.DictReader(f))\n        contenus[fichier] = lignes\n        verifie(len(lignes) >= plancher,\n                f\"{fichier} : {len(lignes)} lignes (plancher {plancher} — \"\n                f\"une chute signale une troncature)\")\n\n    # L'en-tete doit correspondre a ce que peupler.py attend. Une colonne\n    # renommee, ajoutee ou deplacee decalerait silencieusement toutes les\n    # valeurs d'une colonne : c'est le mode de defaillance le plus couteux\n    # du projet (cf. permutation ECOC/BOAS, section 12).\n    sys.path.insert(0, str(ICI))\n    try:\n        import peupler\n    except Exception as e:  # noqa: BLE001\n        verifie(False, f\"moteur/peupler.py non importable : {e}\")\n        return\n    for fichier, attendu in sorted(peupler.SCHEMA_CSV.items()):\n        lignes = contenus.get(fichier)\n        if lignes is None:\n            continue\n        entete = [c for c in (lignes[0].keys() if lignes else []) if c != \"note\"]\n        verifie(entete == attendu,\n                f\"{fichier} : en-tete conforme au schema attendu\"\n                + (\"\" if entete == attendu else f\" — trouve {entete}\"))\n\n    # Une cle dupliquee ferait qu'INSERT OR REPLACE garde silencieusement la\n    # DERNIERE ligne lue, en perdant la premiere sans rien dire.\n    etats = contenus.get(\"etats_financiers.csv\") or []\n    cles = [(r[\"ticker\"], r[\"exercice\"]) for r in etats]\n    doublons = sorted({c for c in cles if cles.count(c) > 1})\n    verifie(not doublons,\n            f\"aucun couple (ticker, exercice) en double dans etats_financiers.csv\"\n            + (\"\" if not doublons else f\" — doublons : {doublons}\"))\n\n    societes = contenus.get(\"societes.csv\") or []\n    tickers = [r[\"ticker\"] for r in societes]\n    doublons_t = sorted({t for t in tickers if tickers.count(t) > 1})\n    verifie(not doublons_t,\n            \"aucun ticker en double dans societes.csv\"\n            + (\"\" if not doublons_t else f\" — doublons : {doublons_t}\"))\n\n    # Integrite referentielle : un etat financier sans societe correspondante\n    # viole la contrainte du schema et ferait echouer le peuplement.\n    connus = set(tickers)\n    orphelins = sorted({r[\"ticker\"] for r in etats if r[\"ticker\"] not in connus})\n    verifie(not orphelins,\n            \"tout etat financier se rattache a une societe declaree\"\n            + (\"\" if not orphelins else f\" — orphelins : {orphelins}\"))\n\n    # Les notes de provenance sont l'essentiel de la valeur de la saisie\n    # manuelle : document source, correction datee, reserve de lecture. Une\n    # chute brutale signalerait une reecriture du fichier qui les aurait\n    # perdues (c'est ce qu'une extraction naive aurait fait le 27/09).\n    avec_note = sum(1 for r in etats if (r.get(\"note\") or \"\").strip())\n    verifie(avec_note >= 120,\n            f\"{avec_note} lignes d'etats financiers portent une note de provenance \"\n            f\"(plancher 120 — une chute signale une perte de tracabilite)\")\n\n    # Aucune donnee ne doit etre revenue dans le code. Le motif cherche est\n    # celui d'un tuple de saisie : (\"XXXX\", 2025, ...\n    code_peupler = (ICI / \"peupler.py\").read_text(encoding=\"utf-8\")\n    import re as _re\n    tuples = _re.findall(r'\\(\"[A-Z][A-Z0-9_]{2,6}\",\\s*(?:19|20)\\d{2},', code_peupler)\n    verifie(not tuples,\n            f\"moteur/peupler.py ne contient plus de donnees codees en dur\"\n            + (\"\" if not tuples else f\" — {len(tuples)} tuple(s) retrouve(s)\"))\n\n    # Les quatre scripts qui lisaient le TEXTE de peupler.py doivent lire le CSV.\n    for chemin_rel, fonction in (\n            (\"collecte/avis_brvm.py\", \"charger_tickers\"),\n            (\"moteur/calendrier.py\", \"construire_mapping\"),\n            (\"collecte/extraire_lot.py\", \"charger_referentiels\"),\n            (\"collecte/preparer_integration.py\", \"charger_exercices_existants\")):\n        chemin = RACINE / chemin_rel\n        if not chemin.exists():\n            verifie(False, f\"{chemin_rel} absent\", bloquant=False)\n            continue\n        code = chemin.read_text(encoding=\"utf-8\")\n        bloc = code.split(\"def %s(\" % fonction, 1)\n        if len(bloc) < 2:\n            verifie(False, f\"{chemin_rel} : fonction {fonction}() introuvable\")\n            continue\n        corps = bloc[1].split(\"\\ndef \", 1)[0]\n        verifie(\"peupler.py\" not in corps.replace(\"peupler.py, d'ou\", \"\")\n                or \"societes.csv\" in corps or \"etats_financiers.csv\" in corps,\n                f\"{chemin_rel} : {fonction}() lit un CSV de reference, \"\n                f\"plus le texte de peupler.py\")\n\n\ndef main():\n    sans_app = \"--sans-app\" in sys.argv\n    print(\"=\" * 60)\n"], ["    test_statuts_cotation()\n    test_integrite_app()\n    test_arbitrage()\n    if not sans_app:\n        test_application()\n\n", "    test_statuts_cotation()\n    test_integrite_app()\n    test_arbitrage()\n    test_base_reference()\n    if not sans_app:\n        test_application()\n\n"]], "app.py": [["         conteneur vivait : la base construite au premier lancement restait en\n         place indefiniment, meme apres l'arrivee de nouvelles donnees.\n    \"\"\"\n    parties = []\n    for f in (QUOTIDIEN, RACINE / \"collecte\" / \"cours_extraits.csv\",\n              RACINE / \"collecte\" / \"dividendes_par_exercice.csv\",\n              RACINE / \"collecte\" / \"notations_financieres.csv\"):\n        parties.append(f\"{f.name}:{int(f.stat().st_mtime)}\" if f.exists() else f\"{f.name}:0\")\n    return \"|\".join(parties)\n\n", "         conteneur vivait : la base construite au premier lancement restait en\n         place indefiniment, meme apres l'arrivee de nouvelles donnees.\n    \"\"\"\n    # Ajout du 27/09/2026 : les donnees de reference du projet (etats\n    # financiers, societes, dividendes) sont sorties de peupler.py vers\n    # donnees/base/. Sans elles dans l'empreinte, corriger un resultat net\n    # dans un CSV ne reconstruirait pas la base : le tableau de bord\n    # afficherait l'ancienne valeur jusqu'au prochain redemarrage du\n    # conteneur. C'est exactement le defaut du 03/09 decrit ci-dessus.\n    parties = []\n    base_ref = sorted((RACINE / \"donnees\" / \"base\").glob(\"*.csv\"))\n    for f in (QUOTIDIEN, RACINE / \"collecte\" / \"cours_extraits.csv\",\n              RACINE / \"collecte\" / \"dividendes_par_exercice.csv\",\n              RACINE / \"collecte\" / \"notations_financieres.csv\",\n              *base_ref):\n        parties.append(f\"{f.name}:{int(f.stat().st_mtime)}\" if f.exists() else f\"{f.name}:0\")\n    return \"|\".join(parties)\n\n"]]}'''

# ----------------------------------------------------------------------
# Extraction des donnees codees en dur vers des CSV
# ----------------------------------------------------------------------
STRUCTURES = {
    "SOCIETES": ("societes.csv", [
        "ticker", "nom", "secteur", "referentiel", "pays", "compartiment",
        "actionnariat"]),
    "ETATS": ("etats_financiers.csv", [
        "ticker", "exercice", "resultat_net", "resultat_net_n1", "total_actif",
        "total_passif", "capitaux_propres", "dettes_financieres", "payout_ratio",
        "solvabilite_bancaire", "source_type", "statut_donnee", "date_publication"]),
    "RAO": ("resultat_activites_ordinaires.csv", [
        "ticker", "exercice", "resultat_activites_ordinaires"]),
    "EXPLOITATION": ("resultat_exploitation.csv", [
        "ticker", "exercice", "resultat_exploitation", "resultat_financier", "source"]),
    "INTERMEDIAIRES": ("resultats_intermediaires.csv", [
        "ticker", "exercice", "periode", "resultat_net", "resultat_net_n1",
        "produit_net_bancaire", "resultat_brut_exploitation", "cout_du_risque",
        "coefficient_exploitation", "statut_donnee", "date_publication",
        "source_url", "note_source"]),
    "SOURCE_URLS": ("source_urls.csv", ["ticker", "exercice", "source_url"]),
    "DIVIDENDES": ("dividendes.csv", [
        "ticker", "montant_net", "date_paiement", "exercice_couvert"]),
    "AVIS": ("avis_reglementaires.csv", ["ticker", "type", "date_avis", "note_avis"]),
}


def commentaires_par_ligne(source):
    """{numero de ligne: texte du commentaire} pour tout le fichier."""
    out = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            out[tok.start[0]] = tok.string.lstrip("#").strip()
    return out


def extraire(source, arbre, nom):
    """Rend [(valeurs, note)] pour la liste nommee `nom`.

    Les commentaires de fin de ligne portent la provenance de chaque saisie :
    document source, correction datee, reserve de lecture. Ils sont
    l'essentiel de la valeur du fichier ; une extraction qui les perdrait
    detruirait la tracabilite. Ils sont donc rapatries en colonne "note"."""
    cible = None
    for noeud in arbre.body:
        if (isinstance(noeud, ast.Assign) and len(noeud.targets) == 1
                and isinstance(noeud.targets[0], ast.Name)
                and noeud.targets[0].id == nom):
            cible = noeud.value
            break
    if cible is None:
        raise SystemExit("Structure %s introuvable dans peupler.py" % nom)
    comments = commentaires_par_ligne(source)
    elements = cible.elts
    sorties = []
    for i, el in enumerate(elements):
        valeurs = list(ast.literal_eval(el))
        debut = el.lineno
        fin = (elements[i + 1].lineno - 1 if i + 1 < len(elements)
               else cible.end_lineno - 1)
        notes = [comments[n] for n in range(debut, fin + 1) if n in comments]
        sorties.append((valeurs, " ".join(notes).strip()))
    return sorties


def ecrire_csv(chemin, colonnes, lignes):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(colonnes + ["note"])
        for valeurs, note in lignes:
            # repr() sur les flottants : preserve la valeur EXACTE. Sans cela,
            # la base reconstruite differerait de l'originale sur les decimales.
            cellules = ["" if v is None else (repr(v) if isinstance(v, float) else str(v))
                        for v in valeurs]
            w.writerow(cellules + [note])


def tables_peuplees(chemin_db):
    """Empreinte comparable de la base : toutes les tables que peuple
    peupler.py, triees, colonne par colonne, sans la cle technique."""
    conn = sqlite3.connect(chemin_db)
    out = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for t in tables:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % t) if r[1] != "id"]
        if not cols:
            continue
        try:
            out[t] = conn.execute("SELECT %s FROM %s ORDER BY %s"
                                  % (", ".join(cols), t, ", ".join(cols))).fetchall()
        except sqlite3.OperationalError:
            continue
    conn.close()
    return out


def construire_base(etiquette):
    """Lance peupler.py et rend l'empreinte de la base obtenue."""
    db = MOTEUR / "brvm.db"
    if db.exists():
        db.unlink()
    r = subprocess.run([sys.executable, "peupler.py"], cwd=str(MOTEUR),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("peupler.py a echoue (%s)" % etiquette)
    return tables_peuplees(str(db))


def appliquer_patches():
    """Remplacements exacts, un par un, avec verification d'unicite.

    Chaque ancre inclut son contexte et doit apparaitre EXACTEMENT une fois.
    C'est la garantie que rien n'est ecrase au hasard : le 24/09, un
    remplacement par ancrage de lignes dont l'ancre n'existait pas avait
    tronque app.py de 943 a 444 lignes sans lever la moindre erreur."""
    patches = json.loads(PATCHES_JSON)
    total = 0
    for chemin_rel, blocs in sorted(patches.items()):
        chemin = RACINE / chemin_rel
        if not chemin.exists():
            raise SystemExit("Fichier a corriger absent : %s" % chemin_rel)
        s = chemin.read_text(encoding="utf-8")
        avant = len(s)
        for ancien, nouveau in blocs:
            if s.count(ancien) == 0 and s.count(nouveau) >= 1:
                continue  # deja applique
            if s.count(ancien) != 1:
                raise SystemExit(
                    "%s : ancre trouvee %d fois au lieu d'une seule.\n"
                    "Le fichier a change depuis la preparation de cette migration.\n"
                    "Extrait de l'ancre :\n%s"
                    % (chemin_rel, s.count(ancien), ancien[:300]))
            s = s.replace(ancien, nouveau, 1)
            total += 1
        chemin.write_text(s, encoding="utf-8")
        print("    %-36s %d bloc(s), %d -> %d octets"
              % (chemin_rel, len(blocs), avant, len(s)))
    return total


def main():
    peupler = MOTEUR / "peupler.py"
    if not peupler.exists():
        raise SystemExit("moteur/peupler.py introuvable — lancer depuis la racine du depot")
    source = peupler.read_text(encoding="utf-8")

    if "donnees/base/" in source and "SCHEMA_CSV" in source:
        print("Migration deja appliquee : peupler.py lit deja donnees/base/.")
        print("Rien a faire.")
        return 0

    print("=" * 66)
    print("MIGRATION DES DONNEES DE REFERENCE VERS donnees/base/")
    print("=" * 66)

    print("\n[1/5] Empreinte de la base AVANT migration")
    avant = construire_base("avant migration")
    print("      %d tables, %d lignes au total"
          % (len(avant), sum(len(v) for v in avant.values())))

    print("\n[2/5] Extraction des donnees codees en dur vers des CSV")
    arbre = ast.parse(source)
    total = 0
    for nom, (fichier, colonnes) in STRUCTURES.items():
        lignes = extraire(source, arbre, nom)
        for valeurs, _ in lignes:
            if len(valeurs) != len(colonnes):
                raise SystemExit(
                    "%s : un tuple a %d valeurs pour %d colonnes declarees"
                    % (nom, len(valeurs), len(colonnes)))
        ecrire_csv(DONNEES / fichier, colonnes, lignes)
        avec_note = sum(1 for _, n in lignes if n)
        print("      %-34s %3d lignes, %3d avec note de provenance"
              % (fichier, len(lignes), avec_note))
        total += len(lignes)
    print("      total : %d lignes extraites" % total)

    print("\n[3/5] Remplacement de peupler.py et fusionner_fondamentaux.py")
    peupler.write_text(NOUVEAU_PEUPLER, encoding="utf-8")
    (MOTEUR / "fusionner_fondamentaux.py").write_text(NOUVEAU_FUSIONNER, encoding="utf-8")
    print("      moteur/peupler.py                    %d -> %d octets"
          % (len(source), len(NOUVEAU_PEUPLER)))
    print("      moteur/fusionner_fondamentaux.py     reecrit (%d octets)"
          % len(NOUVEAU_FUSIONNER))

    print("\n[4/5] Correction des fichiers qui lisaient le TEXTE de peupler.py")
    n = appliquer_patches()
    print("      %d bloc(s) remplace(s)" % n)

    print("\n[5/5] Verification : la base reconstruite doit etre IDENTIQUE")
    apres = construire_base("apres migration")
    ecarts = []
    for t in sorted(set(avant) | set(apres)):
        if avant.get(t) != apres.get(t):
            ecarts.append(t)
        else:
            print("      %-28s IDENTIQUE (%d lignes)" % (t, len(avant.get(t) or [])))
    if ecarts:
        print("\n      *** DIVERGENCE sur : %s" % ", ".join(ecarts))
        raise SystemExit("La base reconstruite differe de l'originale — migration ANNULEE")

    print("\n" + "=" * 66)
    print("MIGRATION REUSSIE — base identique sur les %d tables" % len(avant))
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
