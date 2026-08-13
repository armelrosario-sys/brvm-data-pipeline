#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecte Sikafinance pour les 47 valeurs de la cote BRVM.

    python collecte_sikafinance.py              # tout
    python collecte_sikafinance.py SNTS CBIBF   # quelques titres, pour tester

Deux pages par société :
  /marches/cotation_{SYM}.{pays}  -> bloc HISTORIQUE : 1S, 1M, 1er janvier, 1A, 3A, 5A
  /marches/societe/{SYM}.{pays}   -> chiffres clés : CA, croissances, RN, BNPA

Produit donnees/sikafinance.json.
Dépendances : requests, beautifulsoup4.
"""
import json, os, re, sys, time
from datetime import date

import requests
from bs4 import BeautifulSoup

BASE = "https://www.sikafinance.com/marches/"
PAUSE = 1.5
EXERCICE = "2025"
SORTIE = os.path.join("donnees", "sikafinance.json")

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

HORIZONS = {"1 semaine": "v1s", "1 mois": "v1m", "1er janvier": "ytd",
            "1 an": "v1an", "3 ans": "v3a", "5 ans": "v5a"}

CHIFFRES = {"chiffre d'affaires": "ca", "croissance ca": "croissance_ca",
            "résultat net": "rn", "croissance rn": "croissance_rn", "bnpa": "bnpa"}


def net(t):
    return re.sub(r"\s+", " ", t.replace("\xa0", " ").replace("\u202f", " ")).strip().lower()


def nombre(t):
    if t is None:
        return None
    s = (t.replace("\xa0", "").replace("\u202f", "").replace(" ", "")
          .replace("%", "").replace(",", "."))
    if s in ("", "-", "–", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_historique(html):
    """Bloc HISTORIQUE : un tiret « – » signale un historique de cotation trop court."""
    soup = BeautifulSoup(html, "html.parser")
    perf = {v: None for v in HORIZONS.values()}
    trouve = False
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 4:
            continue
        lib = net(cells[0].get_text())
        for motif, champ in HORIZONS.items():
            if lib == motif:
                perf[champ] = nombre(cells[3].get_text())
                trouve = True
    return perf if trouve else None


def parse_chiffres(html):
    """Tableau quinquennal des chiffres clés, colonne de l'exercice retenu."""
    soup = BeautifulSoup(html, "html.parser")
    for tab in soup.find_all("table"):
        libelles = [net(l.find(["th", "td"]).get_text())
                    for l in tab.find_all("tr") if l.find(["th", "td"])]
        if not any(l.startswith("bnpa") for l in libelles):
            continue
        lignes = tab.find_all("tr")
        annees = [net(c.get_text()) for c in lignes[0].find_all(["th", "td"])]
        col = annees.index(EXERCICE) if EXERCICE in annees else len(annees) - 1
        fiche = {"exercice": annees[col] if col < len(annees) else EXERCICE}
        for tr in lignes[1:]:
            cells = tr.find_all(["th", "td"])
            if len(cells) <= col:
                continue
            lib = net(cells[0].get_text())
            for motif, champ in CHIFFRES.items():
                if lib.startswith(motif):
                    fiche[champ] = nombre(cells[col].get_text())
        return fiche
    return None


def collecte(symboles):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; pipeline-brvm/1.0)"
    valeurs, echecs = {}, []

    for i, sym in enumerate(symboles, 1):
        pays = TITRES[sym]
        fiche = {"symbole": sym}
        for genre, parseur, cle in (("cotation_", parse_historique, "perf"),
                                    ("societe/", parse_chiffres, "chiffres")):
            url = f"{BASE}{genre}{sym}.{pays}"
            try:
                r = s.get(url, timeout=30)
                if r.status_code != 200:
                    r = s.get(f"{BASE}{genre}{sym}.{pays.upper()}", timeout=30)
                r.raise_for_status()
                res = parseur(r.text)
                if res is None:
                    raise ValueError("bloc introuvable")
                fiche[cle] = res
                fiche.setdefault("sources", []).append(url)
            except Exception as e:
                echecs.append(f"{sym}/{cle} : {e}")
                fiche[cle] = None
            time.sleep(PAUSE)
        valeurs[sym] = fiche
        p = fiche.get("perf") or {}
        c = fiche.get("chiffres") or {}
        print(f"[{i:2}/{len(symboles)}] {sym:6s} perf {'OK' if fiche.get('perf') else '--'}"
              f"  ytd {p.get('ytd')}   CA {c.get('ca')}")

    os.makedirs(os.path.dirname(SORTIE) or ".", exist_ok=True)
    json.dump(dict(releve_le=date.today().isoformat(), exercice=EXERCICE,
                   source="sikafinance.com", echecs=echecs, valeurs=valeurs),
              open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    nperf = sum(1 for v in valeurs.values() if v.get("perf"))
    nca = sum(1 for v in valeurs.values() if (v.get("chiffres") or {}).get("ca") is not None)
    print(f"\n{SORTIE} écrit — performances {nperf}/{len(symboles)}, "
          f"chiffre d'affaires {nca}/{len(symboles)}")
    if echecs:
        print("Échecs :\n  " + "\n  ".join(echecs))


if __name__ == "__main__":
    demandes = [x.upper() for x in sys.argv[1:]] or list(TITRES)
    inconnus = [x for x in demandes if x not in TITRES]
    if inconnus:
        sys.exit("Hors cote BRVM : " + ", ".join(inconnus))
    collecte(demandes)
