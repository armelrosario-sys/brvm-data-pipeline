#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3 — Extracteur des BOC (Bulletin Officiel de la Cote) vers cours_mensuels.
Format stable 2018-2026 : PER et Rdt.Net sont TOUJOURS les 2 dernieres colonnes
de chaque ligne de cotation, quel que soit le nombre total de colonnes (15 sans
code secteur avant ~2022, 16 avec depuis) -> indexation par la fin, robuste aux
deux formats sans les distinguer explicitement.
"""
import csv, re, sys
from pathlib import Path
import pdfplumber

NON_TICKERS = {"TOTAL", "SECTEUR", "COMPARTIMENT", "",
               "CB", "CD", "FIN", "ENE", "TEL", "IND", "SPU"}  # codes sectoriels BOC
RE_TICKER = re.compile(r"^[A-Z]{2,6}\d{0,2}$")

# Univers des 47 actions BRVM (hors obligations/FCTC/OPCVM, qui partagent parfois
# des symboles a 2-4 lettres majuscules coincidant avec le motif ci-dessus —
# cas reel rencontre : FGI/SBIF sont des OPCVM, pas des actions).
UNIVERS_ACTIONS = {
    "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM", "BOAN",
    "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT", "FTSC", "LNBB",
    "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT", "PALC", "PRSC", "SAFC",
    "SCRC", "SDCC", "SDSC", "SEMC", "SGBC", "SHEC", "SIBC", "SICC", "SIVC",
    "SLBC", "SMBC", "SNTS", "SOGC", "SPHC", "STAC", "STBC", "TTLC", "TTLS",
    "UNLC", "UNXC",
}
RE_NOMBRE = re.compile(r"^-?[\d\s]+(?:,\d+)?\s?%?$")


def to_float(s):
    if not s or s.strip() in ("", "NC", "SP"):
        return None
    s = s.replace("\xa0", " ").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parser_ligne(row):
    """Retourne dict ou None si la ligne n'est pas une ligne de cotation valide."""
    row = [c.strip() if c else "" for c in row]
    if len(row) < 12:
        return None
    ticker = None
    for idx in (0, 1):
        cand = row[idx].split("\n")[0].strip()
        if cand in UNIVERS_ACTIONS:
            ticker = cand
            break
    if ticker is None:
        return None

    per = to_float(row[-1])
    rendement = to_float(row[-2])
    date_div = row[-3].split("\n")[0].strip() if len(row) >= 3 else None
    montant_div = to_float(row[-4]) if len(row) >= 4 else None
    var_annee = to_float(row[-5]) if len(row) >= 5 else None
    cours_ref = to_float(row[-6]) if len(row) >= 6 else None

    if cours_ref is None and per is None:
        return None  # ligne vide/illisible : rien d'exploitable

    return {
        "ticker": ticker, "cours": cours_ref, "per": per,
        "rendement": rendement, "variation_annee": var_annee,
        "dividende_montant": montant_div, "dividende_date": date_div,
    }


def extraire_boc(chemin_pdf):
    """Retourne (date_bulletin, [lignes]) ou (None, []) si echec de lecture."""
    nom = Path(chemin_pdf).name
    m = re.search(r"(\d{8})", nom)
    date_bulletin = m.group(1) if m else None
    lignes, vus = [], set()
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        r = parser_ligne(row)
                        if r and r["ticker"] not in vus:
                            lignes.append(r)
                            vus.add(r["ticker"])
    except Exception as e:
        print(f"[extraction] {nom} : ECHEC ({type(e).__name__}: {e})", file=sys.stderr)
        return None, []
    return date_bulletin, lignes


if __name__ == "__main__":
    # Auto-test sur l'echantillon 2018-2026 avant tout run massif
    dossier = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for f in sorted(dossier.glob("*.pdf")):
        date_b, lignes = extraire_boc(f)
        pers = [l["per"] for l in lignes if l["per"]]
        print(f"{f.name:<28} date={date_b} | {len(lignes)} titres | "
              f"PER min/med/max = {min(pers):.1f}/{sorted(pers)[len(pers)//2]:.1f}/{max(pers):.1f}"
              if pers else f"{f.name:<28} date={date_b} | {len(lignes)} titres | aucun PER")
