#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3 — Extracteur des BOC (Bulletin Officiel de la Cote) vers cours_mensuels.
Format stable 2018-2026 : PER et Rdt.Net sont TOUJOURS les 2 dernieres colonnes
de chaque ligne de cotation, quel que soit le nombre total de colonnes (15 sans
code secteur avant ~2022, 16 avec depuis) -> indexation par la fin, robuste aux
deux formats sans les distinguer explicitement.
"""
import csv, os, re, sys
from pathlib import Path
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from univers_actions import univers_actions

NON_TICKERS = {"TOTAL", "SECTEUR", "COMPARTIMENT", "",
               "CB", "CD", "FIN", "ENE", "TEL", "IND", "SPU"}  # codes sectoriels BOC
RE_TICKER = re.compile(r"^[A-Z]{2,6}\d{0,2}$")

# CHANTIER C32 (07/10/2026, cycle 21) — l'univers n'est plus ecrit ici.
#
# Il etait en dur : 47 tickers, BBGC absent. Bridge Bank Group CI est cotee
# depuis le 24/09/2026 et chaque bulletin porte depuis 48 lignes de cotation ;
# cours_quotidien_boc.csv en a enregistre 47, toutes les seances du 24/09 au
# 06/10 incluses, et la 48e etait jetee SANS AUCUNE TRACE. Une liste blanche
# ecrite a la main ne se trompe pas une fois, elle se trompe a chaque
# introduction en bourse -- et le silence est le vrai defaut, plus encore que la
# liste.
#
# Deux corrections, et pas une :
#   1. l'univers est derive de donnees/base/societes.csv a l'execution
#      (collecte/univers_actions.py, qui porte la regle et son autotest) : la
#      liste blanche reste -- des OPCVM et des obligations partagent le motif de
#      ticker, FGI et SBIF l'ont deja prouve -- mais sa source est le
#      referentiel que le depot tient a jour, plus une copie figee ici ;
#   2. tout candidat qui ressemble a un ticker de cotation et que l'univers
#      ECARTE est desormais NOMME (`lignes_ecartees`, et une ligne sur stderr).
#      La correction 1 reparera les introductions connues ; la correction 2 est
#      ce qui fera du bruit la prochaine fois qu'elle se trompe quand meme.
RE_NOMBRE = re.compile(r"^-?[\d\s]+(?:,\d+)?\s?%?$")


def to_float(s):
    if not s or s.strip() in ("", "NC", "SP"):
        return None
    s = s.replace("\xa0", " ").replace(" ", "").replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parser_ligne(row, ecartes=None, univers=None):
    """Retourne dict ou None si la ligne n'est pas une ligne de cotation valide.

    `ecartes` (set, optionnel) recueille les mnemoniques qui ressemblent a un
    ticker de cotation, portent des valeurs exploitables, et que l'univers
    ECARTE : c'est la seule chose qui distingue « cette ligne n'est pas une
    cotation » de « cette ligne est une cotation que je ne sais pas nommer ».
    Avant C32, les deux cas rendaient None et se taisaient pareillement.
    """
    row = [c.strip() if c else "" for c in row]
    if len(row) < 12:
        return None
    if univers is None:
        univers = univers_actions()
    ticker, candidat_inconnu = None, None
    for idx in (0, 1):
        cand = row[idx].split("\n")[0].strip()
        if cand in univers:
            ticker = cand
            break
        if (candidat_inconnu is None and cand not in NON_TICKERS
                and RE_TICKER.match(cand)):
            candidat_inconnu = cand
    if ticker is None:
        if ecartes is not None and candidat_inconnu is not None:
            # On ne le signale que si la ligne porte vraiment des valeurs de
            # cotation : sinon on nommerait des entetes et des totaux.
            if to_float(row[-6]) is not None or to_float(row[-1]) is not None:
                ecartes.add(candidat_inconnu)
        return None

    per = to_float(row[-1])
    rendement = to_float(row[-2])
    date_div = row[-3].split("\n")[0].strip() if len(row) >= 3 else None
    montant_div = to_float(row[-4]) if len(row) >= 4 else None
    var_annee = to_float(row[-5]) if len(row) >= 5 else None
    cours_ref = to_float(row[-6]) if len(row) >= 6 else None
    # Ajout 25/07/2026 : volume et valeur echangee du jour, presents dans le
    # BOC depuis toujours mais jamais extraits jusqu'ici (colonnes "Seance
    # de cotation : Volume Valeur", ancrees comme le reste depuis la droite
    # -- verifie sur boc_20251113_2.pdf, colonnes 16 : row[-8]=volume,
    # row[-7]=valeur). C'est ce qui alimente desormais l'historique de
    # liquidite SANS collecte live supplementaire (backfill_liquidite.py).
    volume_echange = to_float(row[-8]) if len(row) >= 8 else None
    valeur_echangee = to_float(row[-7]) if len(row) >= 7 else None

    if cours_ref is None and per is None:
        return None  # ligne vide/illisible : rien d'exploitable

    return {
        "ticker": ticker, "cours": cours_ref, "per": per,
        "rendement": rendement, "variation_annee": var_annee,
        "dividende_montant": montant_div, "dividende_date": date_div,
        "volume_echange": volume_echange, "valeur_echangee": valeur_echangee,
    }


def extraire_boc(chemin_pdf, ecartes=None):
    """Retourne (date_bulletin, [lignes]) ou (None, []) si echec de lecture.

    `ecartes` (set, optionnel) est rempli des mnemoniques de cotation que
    l'univers a ecartes. Qu'il soit fourni ou non, chacun est NOMME sur stderr :
    c'est ce que C32 reproche a la version precedente, qui les jetait sans un
    mot. La signature reste compatible avec les quatre appelants du depot.
    """
    nom = Path(chemin_pdf).name
    m = re.search(r"(\d{8})", nom)
    date_bulletin = m.group(1) if m else None
    lignes, vus = [], set()
    ecartes_locaux = set()
    univers = univers_actions()
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        r = parser_ligne(row, ecartes=ecartes_locaux, univers=univers)
                        if r and r["ticker"] not in vus:
                            lignes.append(r)
                            vus.add(r["ticker"])
    except Exception as e:
        print(f"[extraction] {nom} : ECHEC ({type(e).__name__}: {e})", file=sys.stderr)
        return None, []
    if ecartes is not None:
        ecartes.update(ecartes_locaux)
    if ecartes_locaux:
        print(f"[extraction] {nom} : {len(ecartes_locaux)} mnemonique(s) de cotation "
              f"ECARTE(S) par l'univers, hors referentiel donnees/base/societes.csv : "
              + ", ".join(sorted(ecartes_locaux))
              + " -- si l'un d'eux est une action, il manque a societes.csv (chantier C32)",
              file=sys.stderr)
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
