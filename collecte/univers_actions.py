#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/univers_actions.py — l'univers des actions BRVM, derive de la base.

CHANTIER C32 (07/10/2026, cycle 21). Avant ce fichier, collecte/extracteur_boc.py
portait l'univers en dur :

    UNIVERS_ACTIONS = { "ABJC", "BICB", ... }   # 47 tickers, BBGC absent

Bridge Bank Group CI est cotee depuis le 24/09/2026 (BOC n(deg) 181). De cette
seance au 06/10/2026 incluse, cours_quotidien_boc.csv a porte EXACTEMENT 47
lignes a chaque seance, et jamais BBGC : la 48e ligne du bulletin etait jetee en
silence, seance apres seance, parce que son mnemonique ne figurait pas dans un
ensemble ecrit a la main. Un univers en dur ne se trompe pas une fois : il se
trompe a chaque introduction en bourse, et sans le dire.

POURQUOI UNE LISTE BLANCHE RESTE NECESSAIRE. Le motif de ticker du BOC
(^[A-Z]{2,6}\\d{0,2}$) est partage par des OPCVM et des obligations qui figurent
dans le meme document -- cas reel rencontre et consigne dans l'ancien
commentaire : FGI et SBIF sont des OPCVM, pas des actions. Ouvrir le filtre a
tout ce qui ressemble a un ticker rouvrirait ce defaut-la. La liste blanche est
donc conservee ; ce qui change, c'est sa SOURCE : donnees/base/societes.csv, le
referentiel des societes que le depot tient a jour de toute facon, au lieu d'une
copie figee dans un script de collecte.

LA REGLE DE DERIVATION, ET SES DEUX EXCLUSIONS, TOUTES DEUX LISIBLES DANS LA DONNEE
  1. le ticker doit correspondre au motif du BOC -- un mnemonique qui ne peut pas
     apparaitre dans un bulletin n'a rien a faire dans le filtre d'un bulletin ;
  2. le nom ne doit pas commencer par "[SYNTHETIQUE]" -- societes.csv porte deux
     titres fabriques pour les golden tests (TEST_EXCLU, TEST_VIGIL) et ils ne
     sont pas cotes. Ils sont deja ecartes par la regle 1 (l'underscore ne passe
     pas le motif) ; la regle 2 est la ceinture de la bretelle, et elle est
     explicite au lieu d'etre un effet de bord d'une expression reguliere.

ET UN REFUS PLUTOT QU'UNE DEVINETTE. Un univers derive qui serait vide, illisible
ou anormalement court ferait exactement ce que ce chantier corrige : ecarter des
lignes de bulletin en silence. Le fichier leve donc une exception au lieu de
rendre un ensemble degrade -- mieux vaut une collecte qui s'arrete bruyamment
qu'une collecte qui perd des titres sans le dire.

Usage : python3 collecte/univers_actions.py --test
"""
import csv
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SOCIETES = RACINE / "donnees" / "base" / "societes.csv"

# Le motif du BOC, repris a l'identique de extracteur_boc.py : c'est le meme
# document qui est filtre.
RE_TICKER = re.compile(r"^[A-Z]{2,6}\d{0,2}$")

# Marqueur des titres fabriques pour les golden tests, porte par la colonne `nom`.
PREFIXE_SYNTHETIQUE = "[SYNTHETIQUE]"

# Plancher de vraisemblance. La cote comptait 47 actions jusqu'au 23/09/2026 et
# 48 depuis. Un univers derive qui tomberait sous ce plancher signale un
# societes.csv tronque ou mal lu, pas une cote qui a fondu : on refuse.
PLANCHER_VRAISEMBLANCE = 40

_cache = None


class UniversIndisponible(RuntimeError):
    """L'univers n'a pas pu etre derive : on refuse de collecter a l'aveugle."""


def univers_actions(chemin=None, forcer=False):
    """Rend le frozenset des mnemoniques d'actions cotees, derive de societes.csv.

    Leve UniversIndisponible si le referentiel est absent, illisible, prive de
    sa colonne `ticker`, ou s'il rend moins de PLANCHER_VRAISEMBLANCE tickers.
    """
    global _cache
    if _cache is not None and chemin is None and not forcer:
        return _cache
    source = Path(chemin) if chemin else SOCIETES
    if not source.exists():
        raise UniversIndisponible(f"referentiel des societes absent : {source}")
    try:
        with open(source, newline="", encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
    except Exception as e:  # lecture illisible : on le dit, on ne devine pas
        raise UniversIndisponible(f"{source} illisible ({type(e).__name__}: {e})")
    if not lignes or "ticker" not in (lignes[0].keys() if lignes else {}):
        raise UniversIndisponible(f"{source} sans colonne `ticker` exploitable")
    retenus = set()
    for ligne in lignes:
        ticker = (ligne.get("ticker") or "").strip()
        nom = (ligne.get("nom") or "").strip()
        if not RE_TICKER.match(ticker):
            continue
        if nom.startswith(PREFIXE_SYNTHETIQUE):
            continue
        retenus.add(ticker)
    if len(retenus) < PLANCHER_VRAISEMBLANCE:
        raise UniversIndisponible(
            f"{source} ne rend que {len(retenus)} ticker(s), plancher "
            f"{PLANCHER_VRAISEMBLANCE} : referentiel vraisemblablement tronque")
    univers = frozenset(retenus)
    if chemin is None:
        _cache = univers
    return univers


# --- autotest ---------------------------------------------------------------

def _autotest():
    import tempfile
    ok = ech = 0

    def verifie(cond, libelle):
        nonlocal ok, ech
        if cond:
            ok += 1
            print(f"  OK    {libelle}")
        else:
            ech += 1
            print(f"  ECHEC {libelle}")

    print("=== univers_actions : autotest ===")
    u = univers_actions(forcer=True)
    verifie(len(u) >= PLANCHER_VRAISEMBLANCE, f"univers derive de {len(u)} tickers")
    verifie("BBGC" in u, "BBGC present (la 48e ligne du bulletin est desormais acceptee)")
    verifie("TEST_EXCLU" not in u and "TEST_VIGIL" not in u,
            "les titres [SYNTHETIQUE] sont ecartes")
    verifie(all(RE_TICKER.match(t) for t in u),
            "tous les tickers retenus passent le motif du BOC")
    verifie("FGI" not in u and "SBIF" not in u,
            "les OPCVM connus (FGI, SBIF) restent hors univers")

    # Les 47 de l'ancienne liste en dur doivent tous survivre : la derivation
    # elargit l'univers, elle ne doit en retirer aucun.
    anciens = {
        "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM", "BOAN",
        "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT", "FTSC", "LNBB",
        "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT", "PALC", "PRSC", "SAFC",
        "SCRC", "SDCC", "SDSC", "SEMC", "SGBC", "SHEC", "SIBC", "SICC", "SIVC",
        "SLBC", "SMBC", "SNTS", "SOGC", "SPHC", "STAC", "STBC", "TTLC", "TTLS",
        "UNLC", "UNXC",
    }
    verifie(anciens <= u, f"les 47 tickers de l'ancienne liste en dur sont tous retenus "
                          f"(manquants : {sorted(anciens - u)})")

    # Le refus, sur trois referentiels fabriques.
    with tempfile.TemporaryDirectory() as d:
        absent = Path(d) / "pas_la.csv"
        try:
            univers_actions(absent)
            verifie(False, "fichier absent : refus attendu")
        except UniversIndisponible:
            verifie(True, "fichier absent : refus leve")

        tronque = Path(d) / "tronque.csv"
        tronque.write_text("ticker,nom\nABJC,Servair\n", encoding="utf-8")
        try:
            univers_actions(tronque)
            verifie(False, "referentiel tronque : refus attendu")
        except UniversIndisponible as e:
            verifie("plancher" in str(e), "referentiel tronque : refus leve, plancher cite")

        sans_colonne = Path(d) / "sans_colonne.csv"
        sans_colonne.write_text("mnemo,nom\nABJC,Servair\n", encoding="utf-8")
        try:
            univers_actions(sans_colonne)
            verifie(False, "colonne `ticker` absente : refus attendu")
        except UniversIndisponible:
            verifie(True, "colonne `ticker` absente : refus leve")

    print(f"--- {ok} OK, {ech} ECHEC")
    return 0 if ech == 0 else 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_autotest())
    for t in sorted(univers_actions()):
        print(t)
