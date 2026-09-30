#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/dates_dividendes.py — normalisation ISO des dates de paiement
=========================================================================

Chantier C10 (30/09/2026). ``dividendes.date_paiement`` melangeait deux
formats incompatibles : 296 lignes en francais abrege sur deux chiffres
d'annee (``24-juil.-17``, ``30-sept.-24``, ``24-aout-22``) et 12 en ISO. Trois
conséquences, mesurees le meme jour :

  1. **tri faux.** ``moteur/scoring.py::dividendes()`` fait
     ``ORDER BY date_paiement DESC`` : sur du francais abrege l'ordre est
     alphabetique. Sur les 49 tickers portant au moins deux dividendes dates,
     ce tri rendait un AUTRE versement que le plus recent pour **34** d'entre
     eux ;
  2. **extraction d'annee impossible.** ``scoring.py`` fait
     ``int(dernier_div["date_paiement"][:4])`` : sur ``24-juil.-17`` cela vaut
     ``int("24-j")``, donc ``ValueError``, avalee par un ``except`` -- tout le
     bloc « regularite du dividende » (bonus, malus et alerte) etait donc
     silencieusement saute ;
  3. **deduplication cassee, latente.** ``collecte_boc_quotidien.py``
     normalise en ISO puis deduplique par egalite de chaine : une date ISO ne
     s'egalera jamais a la forme francaise du meme jour.

Ce module est la seule definition de la conversion dans le depot. Il est
importe par ``charger_dividendes_exercice.py``,
``historiser_dividendes_exercice.py``, ``moteur/peupler.py`` et
``outils/migration_dates_dividendes_iso.py``.

Doctrine appliquee, mot pour mot celle du projet : **refuser plutot que
deviner**. Un mois non reconnu, un jour qui n'existe pas, une annee hors de la
fenetre de plausibilite du depot rendent ``None``, jamais une date approchee.
C'est a l'appelant de faire du bruit.

Usage : python3 collecte/dates_dividendes.py --test
"""
import re
import sys
from datetime import date

# Mois francais abreges tels que le BOC les ecrit, avec et sans accent, avec et
# sans point final. Les variantes anglaises viennent de bulletins a mise en page
# mixte, deja rencontrees par historiser_dividendes_exercice.py.
#
# Liste BLANCHE exacte, et aucune correspondance par prefixe. Un prefixe de
# trois lettres accepterait ``24-jullet-17`` comme un 24 juillet : c'est
# exactement la devinette que C10 interdit (« un mois francais abrege mal
# orthographie doit echouer bruyamment »). Toute forme absente de cette table
# rend None.
MOIS = {
    "janv": 1, "jan": 1, "janvier": 1,
    "fevr": 2, "févr": 2, "fev": 2, "fév": 2, "feb": 2,
    "fevrier": 2, "février": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "apr": 4, "avril": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6,
    "juil": 7, "jul": 7, "juillet": 7,
    "aout": 8, "août": 8, "aug": 8,
    "sept": 9, "sep": 9, "septembre": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "dec": 12, "déc": 12, "decembre": 12, "décembre": 12,
}

# Fenetre de plausibilite. La BRVM existe depuis 1998 et le depot ne porte
# aucune observation anterieure a 2017 ; une annee sur deux chiffres est donc
# lue comme 20AA, mais tout resultat hors de cette fenetre est REFUSE plutot que
# retenu -- c'est ce qui leve l'ambiguite du siecle au lieu de la masquer.
ANNEE_MIN = 1998
ANNEE_MAX = date.today().year + 1

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_FR = re.compile(r"^(\d{1,2})[-/ ]\s*([A-Za-zà-ÿ]+)\.?[-/ ]\s*(\d{2}|\d{4})$")


def vers_iso(texte):
    """Date de paiement en ``aaaa-mm-jj``, ou ``None`` si elle n'est pas lisible.

    Accepte l'ISO (revalide : ``2025-02-31`` est refuse) et le francais abrege.
    Rend ``None`` -- jamais une devinette -- sur un mois inconnu, un jour
    inexistant, une annee hors fenetre, ou toute autre forme.
    """
    if texte is None:
        return None
    t = str(texte).strip()
    if not t:
        return None

    m = _ISO.match(t)
    if m:
        a, mo, j = (int(x) for x in m.groups())
        return _valide(a, mo, j)

    m = _FR.match(t)
    if not m:
        return None
    jour, mois_txt, annee = m.groups()
    mois_txt = mois_txt.lower().rstrip(".")
    mois = MOIS.get(mois_txt)      # liste blanche exacte, jamais un prefixe
    if not mois:
        return None
    annee = int(annee)
    if annee < 100:
        annee += 2000
    return _valide(annee, mois, int(jour))


def _valide(annee, mois, jour):
    if not ANNEE_MIN <= annee <= ANNEE_MAX:
        return None
    try:
        return date(annee, mois, jour).isoformat()
    except ValueError:
        return None


def est_iso(texte):
    """La valeur est-elle DEJA une date ISO valide ? (une case vide ne l'est pas)"""
    return bool(texte) and _ISO.match(str(texte).strip()) is not None \
        and vers_iso(texte) == str(texte).strip()


# --------------------------------------------------------------------------
# Autotest. Chaque cas vient d'une forme reellement presente dans le depot ou
# d'un piege que la conversion doit refuser.
# --------------------------------------------------------------------------
CAS = [
    # --- formes presentes dans collecte/dividendes_par_exercice.csv ---------
    ("24-juil.-17", "2017-07-24"),
    ("30-sept.-24", "2024-09-30"),
    ("24-août-22", "2022-08-24"),
    ("2-août-21", "2021-08-02"),
    ("31-août-23", "2023-08-31"),
    ("18-août-25", "2025-08-18"),
    ("1-juil.-21", "2021-07-01"),
    ("28-déc.-21", "2021-12-28"),
    ("22-oct.-25", "2025-10-22"),
    # --- ISO : passe tel quel, mais revalide -------------------------------
    ("2025-08-18", "2025-08-18"),
    ("2022-01-31", "2022-01-31"),
    # --- variantes de forme acceptees --------------------------------------
    ("24-juil-17", "2017-07-24"),
    ("24-juillet-2017", "2017-07-24"),
    ("24-fevr.-20", "2020-02-24"),
    ("18-aug-25", "2025-08-18"),
    # --- refus : c'est la moitie du travail de ce module -------------------
    ("", None),
    (None, None),
    ("24-juil.-1", None),           # annee sur un chiffre
    ("24-jullet-17", None),         # mois mal orthographie
    ("24-xyz-17", None),            # mois inconnu
    ("31-fevr.-20", None),          # jour inexistant
    ("2025-02-31", None),           # ISO invalide, refusee comme le reste
    ("30-sept.-97", None),          # 2097 : hors fenetre de plausibilite
    ("juil.-24", None),             # pas de jour
    ("24/07/2017", None),           # mois numerique : ambigu jour/mois, refuse
    ("2017-7-24", None),            # ISO non zero-paddee
    ("le 24 juillet 2017", None),   # phrase
]


def autotest():
    echecs = []
    for entree, attendu in CAS:
        obtenu = vers_iso(entree)
        etat = "OK" if obtenu == attendu else "ECHEC"
        if obtenu != attendu:
            echecs.append((entree, attendu, obtenu))
        print("  [%s] %-22r -> %-12r (attendu %r)" % (etat, entree, obtenu, attendu))
    # est_iso() ne doit jamais dire "oui" a une forme francaise ni a une case vide
    for mauvais in ("24-juil.-17", "", None, "2025-02-31", "2017-7-24"):
        if est_iso(mauvais):
            echecs.append((mauvais, "est_iso=False", "est_iso=True"))
    if est_iso("2025-08-18") is not True:
        echecs.append(("2025-08-18", "est_iso=True", "est_iso=False"))
    print("\n%d cas, %d echec(s)" % (len(CAS), len(echecs)))
    for e in echecs:
        print("  ECHEC %r : attendu %r, obtenu %r" % e)
    return 1 if echecs else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=== autotest collecte/dates_dividendes.py ===")
        sys.exit(autotest())
    for arg in sys.argv[1:]:
        print("%r -> %r" % (arg, vers_iso(arg)))
