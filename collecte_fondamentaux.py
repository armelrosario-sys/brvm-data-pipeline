#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecte des fondamentaux des 47 sociétés cotées à la BRVM depuis Sikafinance.

Produit fondamentaux_brvm.csv, directement importable dans le tableau de bord
(bouton « Importer les fondamentaux »).

    pip install requests beautifulsoup4
    python collecte_fondamentaux.py                 # les 47 titres
    python collecte_fondamentaux.py SNTS CBIBF      # quelques titres, pour tester

À exécuter depuis un poste ou un runner GitHub Actions : le bac à sable de Claude
n'a pas accès à sikafinance.com.
"""
import csv, re, sys, time
from datetime import date

import requests
from bs4 import BeautifulSoup

BASE = "https://www.sikafinance.com/marches/societe/"
PAUSE = 1.5          # secondes entre deux requêtes — rester courtois
EXERCICE = "2025"    # colonne à extraire du tableau quinquennal

# Suffixe pays relevé sur la page « Cotations de A à Z » de Sikafinance.
# MOVIS CI (SVOC) figure chez Sikafinance mais pas dans la cote du BOC : exclu.
TITRES = {
    "SDSC": "ci", "BOAB": "bj", "BOABF": "bf", "BOAC": "ci", "BOAM": "ml",
    "BOAN": "ne", "BOAS": "sn", "BICB": "bj", "BNBC": "ci", "BICC": "ci",
    "CFAC": "ci", "CIEC": "ci", "CBIBF": "bf", "SEMC": "ci", "ECOC": "ci",
    "SIVC": "ci", "ETIT": "tg", "FTSC": "ci", "LNBB": "bj", "NEIC": "ci",
    "NTLC": "ci", "NSBC": "ci", "ONTBF": "bf", "ORGT": "tg", "ORAC": "ci",
    "PALC": "ci", "SAFC": "ci", "SPHC": "ci", "ABJC": "ci", "STAC": "ci",
    "SGBC": "ci", "CABC": "ci", "SICC": "ci", "STBC": "ci", "SMBC": "ci",
    "SIBC": "ci", "SDCC": "ci", "SOGC": "ci", "SLBC": "ci", "SNTS": "sn",
    "SCRC": "ci", "TTLC": "ci", "TTLS": "sn", "PRSC": "ci", "UNLC": "ci",
    "UNXC": "ci", "SHEC": "ci",
}

# Intitulés de la première colonne du tableau des chiffres clés -> champ CSV.
LIGNES = {
    "chiffre d'affaires": "ca",
    "croissance ca": "croissance_ca",
    "résultat net": "rn",
    "croissance rn": "croissance_rn",
    "bnpa": "bnpa",
}

ENTETES = ["symbole", "exercice", "ca", "croissance_ca", "rn", "croissance_rn",
           "bnpa", "fonds_propres", "nb_titres", "flottant", "valorisation",
           "source", "releve_le"]


def nettoie(txt):
    """Normalise un libellé : minuscules, sans accent parasite ni espace multiple."""
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip().lower()


def nombre(txt):
    """« 1 923 122 » -> 1923122.0 ; « 8,26% » -> 8.26 ; « » -> None."""
    if txt is None:
        return None
    s = txt.replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    s = s.replace("%", "").replace(",", ".")
    if s in ("", "-", "–", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extrait(html, symbole):
    """Renvoie le dictionnaire des fondamentaux, ou None si la page n'a pas le tableau."""
    soup = BeautifulSoup(html, "html.parser")
    fiche = {"symbole": symbole, "exercice": EXERCICE}

    # --- bloc d'identité : nombre de titres, flottant, valorisation
    texte = nettoie(soup.get_text(" "))
    for motif, champ in [(r"nombre de titres\s*:?\s*([\d  \u202f]+)", "nb_titres"),
                         (r"flottant\s*:?\s*([\d,\.]+)\s*%", "flottant"),
                         (r"valorisation de la société\s*:?\s*([\d  \u202f]+)", "valorisation")]:
        m = re.search(motif, texte)
        fiche[champ] = nombre(m.group(1)) if m else None

    # --- tableau des chiffres clés : repéré par la présence d'une ligne « BNPA »
    cible = None
    for tab in soup.find_all("table"):
        entetes = [nettoie(c.get_text()) for c in tab.find_all(["th", "td"])[:12]]
        if any(e.startswith("bnpa") for e in
               [nettoie(l.find(["th", "td"]).get_text()) for l in tab.find_all("tr")
                if l.find(["th", "td"])]):
            cible = tab
            break
    if cible is None:
        return None

    lignes = cible.find_all("tr")
    # première ligne = années ; on localise la colonne de l'exercice voulu
    annees = [nettoie(c.get_text()) for c in lignes[0].find_all(["th", "td"])]
    try:
        col = annees.index(EXERCICE)
    except ValueError:
        col = len(annees) - 1          # à défaut, l'exercice le plus récent

    for ligne in lignes[1:]:
        cells = ligne.find_all(["th", "td"])
        if len(cells) <= col:
            continue
        lib = nettoie(cells[0].get_text())
        for motif, champ in LIGNES.items():
            if lib.startswith(motif):
                fiche[champ] = nombre(cells[col].get_text())
    return fiche


def collecte(symboles):
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; collecte-brvm/1.0)"
    resultats, echecs = [], []

    for i, sym in enumerate(symboles, 1):
        url = f"{BASE}{sym}.{TITRES[sym]}"
        try:
            rep = session.get(url, timeout=25)
            if rep.status_code != 200:                      # certaines fiches sont en majuscules
                rep = session.get(f"{BASE}{sym}.{TITRES[sym].upper()}", timeout=25)
            rep.raise_for_status()
            fiche = extrait(rep.text, sym)
            if fiche is None:
                raise ValueError("tableau des chiffres clés introuvable")
            fiche["source"] = url
            fiche["releve_le"] = date.today().isoformat()
            resultats.append(fiche)
            ca = fiche.get("ca")
            print(f"[{i:2}/{len(symboles)}] {sym:6s} OK    CA {ca if ca else '—'}")
        except Exception as err:
            echecs.append((sym, str(err)))
            print(f"[{i:2}/{len(symboles)}] {sym:6s} ECHEC {err}")
        time.sleep(PAUSE)

    with open("fondamentaux_brvm.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ENTETES, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in resultats:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in ENTETES})

    print(f"\nfondamentaux_brvm.csv écrit — {len(resultats)}/{len(symboles)} sociétés")
    manquants = [r["symbole"] for r in resultats if r.get("ca") is None]
    if manquants:
        print("Sans chiffre d'affaires publié : " + ", ".join(manquants))
    if echecs:
        print("Échecs : " + ", ".join(f"{s} ({e})" for s, e in echecs))
    print("\nfonds_propres reste vide : Sikafinance ne publie pas les capitaux propres.")
    print("Les saisir depuis les rapports annuels pour obtenir le ROE.")


if __name__ == "__main__":
    demandes = [s.upper() for s in sys.argv[1:]] or list(TITRES)
    inconnus = [s for s in demandes if s not in TITRES]
    if inconnus:
        sys.exit("Symbole(s) hors cote BRVM : " + ", ".join(inconnus))
    collecte(demandes)
