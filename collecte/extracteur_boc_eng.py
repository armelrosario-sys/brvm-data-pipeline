#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/extracteur_boc_eng.py — l'edition ANGLAISE du BOC (chantier C36).

POURQUOI CE FICHIER EXISTE. Quand la BRVM ne publie que l'edition anglaise du
bulletin, la seance etait perdue. Le 02/10/2026 en est le cas reel :
`boc_eng_20261002*.pdf` existe, `collecte/cours_quotidien_boc.csv` porte
0 ligne a cette date, et la serie passe du 10-01 au 10-05.

CE QUI EST CHARGE, ET CE QUI NE L'EST PAS — option (b), tranchee par Claudia le
05/10/2026. Cours, PER, volume et valeur echangee sont lus. Le **rendement n'est
PAS lu**, et ce n'est pas un oubli : mesure du 05/10 sur le bulletin du 02/10
confronte au francais du 01/10, l'edition anglaise arrondit le rendement a deux
decimales de la FRACTION — SNTS 0.04 contre 3,87 %, BOAC 0.05 contre 5,20 %,
SGBC 0.06 contre 5,89 %. Le charger approcherait une valeur certifiee, ce que la
deuxieme regle de CHANTIERS.md interdit : une case vide vaut mieux qu'une valeur
approchee.

CE QUI IDENTIFIE UNE SEANCE ANGLAISE EST LE REGISTRE, PAS LA CASE VIDE. Premiere
redaction de ce fichier, le 07/10/2026 : « une ligne BOC_ENG se reconnait a son
rendement vide ». FAUX, et mesure a l'appui : `cours_quotidien_boc.csv` porte
deja **15 116** lignes a rendement vide sur 90 754, reparties sur les 2 031
seances, et 8 seances de janvier 2018 n'en ont aucun. Le rendement vide est donc
une CONSEQUENCE de l'option (b), jamais une signature. L'identification se lit
dans `collecte/seances_boc_eng.csv`, que le versement inscrit.

LES DEUX PIEGES DE FORMAT, ET POURQUOI ILS NE SE DEVINENT PAS.

1. **Les nombres sont a l'anglaise.** « 45,000 » vaut quarante-cinq mille, pas
   quarante-cinq. Le `to_float()` de extracteur_boc.py fait
   `.replace(",", ".")` : il aurait rendu **45.0** pour le cours de SNTS, soit
   un facteur 1 000. C'est pourquoi ce fichier porte son propre convertisseur,
   et pourquoi celui-ci REFUSE tout nombre ou la virgule n'est pas suivie
   d'exactement trois chiffres — « 45,00 » est ambigu entre les deux
   conventions, donc illisible, donc None.
2. **Les mois sont en anglais** (« 26 May 26 »), et le separateur est l'espace
   et non le tiret. `date_dividende_vers_iso()` du collecteur n'en lit rien.

LA DISPOSITION DES COLONNES N'EST PAS SUPPOSEE, ELLE EST VERIFIEE AILLEURS.
Ce fichier ancre les colonnes depuis la DROITE, comme l'extracteur francais, et
c'est une hypothese : les deux editions du meme bulletin ont vraisemblablement
la meme structure, mais « vraisemblablement » n'est pas une preuve. La preuve
est exigee par `outils/versement_boc_eng.py`, qui refuse d'ecrire une seance
dont le PER extrait ne concorde pas avec celui du releve independant de la page
« Volumes / Valeurs » (`collecte/releve_volumes.csv`). C'est la preuve a deux
cotes de CHANTIERS.md, et elle porte precisement sur ce que ce fichier suppose.

Chaque ligne rendue porte `row_brut`, pour que le mode rapport puisse montrer la
ligne telle que le PDF la donne, avant toute ecriture.

Usage : python3 collecte/extracteur_boc_eng.py --test
        python3 collecte/extracteur_boc_eng.py <fichier.pdf>   (mode rapport)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from univers_actions import univers_actions

NON_TICKERS = {"TOTAL", "SECTOR", "SECTEUR", "COMPARTMENT", "COMPARTIMENT", "",
               "CB", "CD", "FIN", "ENE", "TEL", "IND", "SPU"}
RE_TICKER = re.compile(r"^[A-Z]{2,6}\d{0,2}$")

# Un nombre a l'anglaise : groupes de milliers par virgule, decimales par point.
# La virgule doit etre suivie d'EXACTEMENT trois chiffres, sinon le nombre est
# ambigu entre les deux conventions et on refuse de le lire.
RE_NOMBRE_ENG = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")

MOIS_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

VIDES = {"", "-", "--", "NC", "SP", "N/A", "NA", "ND"}


def to_float_eng(s):
    """Nombre a l'anglaise -> float, ou None. Jamais une valeur devinee.

    Refuse explicitement une virgule qui n'est pas un separateur de milliers :
    « 45,00 » et « 3,87 » sont ambigus entre convention anglaise et francaise,
    donc illisibles. « 45,000 » vaut 45000.0.
    """
    if s is None:
        return None
    t = str(s).replace("\xa0", " ").strip()
    t = t.replace("%", "").strip()
    if t.upper() in VIDES:
        return None
    # Parentheses comptables : (1.21) vaut -1.21
    negatif = False
    if t.startswith("(") and t.endswith(")"):
        negatif, t = True, t[1:-1].strip()
    t = t.replace(" ", "")
    if not RE_NOMBRE_ENG.match(t):
        return None
    try:
        v = float(t.replace(",", ""))
    except ValueError:
        return None
    return -v if negatif else v


def date_dividende_eng_vers_iso(texte):
    """« 26 May 26 », « 26-May-26 », « 26 May 2026 » -> « 2026-05-26 ».

    Retourne None si illisible, jamais une date inventee. L'annee a deux
    chiffres est bornee a la fenetre 1998-2027, comme le fait
    collecte/dates_dividendes.py pour le francais : hors fenetre, on refuse au
    lieu de masquer l'ambiguite du siecle.
    """
    if not texte:
        return None
    t = str(texte).split("\n")[0].strip().lower().replace(".", "")
    m = re.match(r"^(\d{1,2})[\s\-/]+([a-z]{3,9})[\s\-/]+(\d{2}|\d{4})$", t)
    if not m:
        return None
    jour, mois_txt, annee_txt = m.groups()
    mois = MOIS_EN.get(mois_txt[:3])
    if not mois:
        return None
    annee = int(annee_txt)
    if annee < 100:
        annee += 2000
    if not (1998 <= annee <= 2027):
        return None
    jour = int(jour)
    jours_max = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois - 1]
    if not (1 <= jour <= jours_max):
        return None
    return f"{annee:04d}-{mois:02d}-{jour:02d}"


def parser_ligne_eng(row, ecartes=None, univers=None):
    """Une ligne de cotation de l'edition anglaise, ou None.

    Ancrage depuis la DROITE, comme extracteur_boc.py : row[-1] PER,
    row[-2] rendement (DELIBEREMENT NON LU, option b), row[-3] date du
    dividende, row[-4] montant du dividende, row[-5] variation annuelle,
    row[-6] cours de reference, row[-7] valeur echangee, row[-8] volume.
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
            if to_float_eng(row[-6]) is not None or to_float_eng(row[-1]) is not None:
                ecartes.add(candidat_inconnu)
        return None

    per = to_float_eng(row[-1])
    cours = to_float_eng(row[-6])
    if cours is None and per is None:
        return None
    return {
        "ticker": ticker,
        "cours": cours,
        "per": per,
        # Option (b) : le rendement de l'edition anglaise est arrondi a deux
        # decimales de la fraction. On ne le lit pas, et la case reste vide.
        "rendement": None,
        "rendement_brut_non_lu": row[-2],   # conserve pour le mode rapport seul
        "variation_annee": to_float_eng(row[-5]),
        "dividende_montant": to_float_eng(row[-4]),
        "dividende_date": date_dividende_eng_vers_iso(row[-3]),
        "volume_echange": to_float_eng(row[-8]),
        "valeur_echangee": to_float_eng(row[-7]),
        "row_brut": row,
    }


def extraire_boc_eng(chemin_pdf, ecartes=None):
    """(date_bulletin_aaaammjj, [lignes]) ou (None, []) si echec de lecture."""
    import pdfplumber
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
                        r = parser_ligne_eng(row, ecartes=ecartes_locaux, univers=univers)
                        if r and r["ticker"] not in vus:
                            lignes.append(r)
                            vus.add(r["ticker"])
    except Exception as e:
        print(f"[extraction eng] {nom} : ECHEC ({type(e).__name__}: {e})", file=sys.stderr)
        return None, []
    if ecartes is not None:
        ecartes.update(ecartes_locaux)
    if ecartes_locaux:
        print(f"[extraction eng] {nom} : {len(ecartes_locaux)} mnemonique(s) ECARTE(S) "
              f"par l'univers : " + ", ".join(sorted(ecartes_locaux)), file=sys.stderr)
    return date_bulletin, lignes


# --- autotest ---------------------------------------------------------------

def _autotest():
    ok = ech = 0

    def verifie(cond, libelle):
        nonlocal ok, ech
        if cond:
            ok += 1
            print(f"  OK    {libelle}")
        else:
            ech += 1
            print(f"  ECHEC {libelle}")

    print("=== extracteur_boc_eng : autotest ===")

    # --- Les nombres a l'anglaise, et le refus de l'ambigu -------------------
    verifie(to_float_eng("45,000") == 45000.0,
            "« 45,000 » vaut 45000 (le cours de SNTS au 02/10), pas 45")
    verifie(to_float_eng("10.88") == 10.88, "« 10.88 » vaut 10.88")
    verifie(to_float_eng("1,234,567") == 1234567.0, "« 1,234,567 » vaut 1234567")
    verifie(to_float_eng("12.89") == 12.89, "« 12.89 » vaut 12.89 (PER de BOAC)")
    verifie(to_float_eng("535,765,635") == 535765635.0,
            "une valeur echangee a trois groupes de milliers est lue")
    verifie(to_float_eng("(1.21)") == -1.21, "les parentheses comptables valent un negatif")
    verifie(to_float_eng("-1.21") == -1.21, "le signe moins est lu")
    verifie(to_float_eng("0.04") == 0.04, "« 0.04 » vaut 0.04")
    for ambigu in ("45,00", "3,87", "1,2", "45,0000"):
        verifie(to_float_eng(ambigu) is None,
                f"« {ambigu} » est AMBIGU entre les deux conventions -> refuse")
    for vide in ("", "-", "NC", "SP", "N/A", None):
        verifie(to_float_eng(vide) is None, f"« {vide} » -> None, jamais zero")
    verifie(to_float_eng("abc") is None, "un texte -> None")

    # --- Les dates en anglais ------------------------------------------------
    verifie(date_dividende_eng_vers_iso("26 May 26") == "2026-05-26",
            "« 26 May 26 » -> 2026-05-26 (la forme vue sur le bulletin du 02/10)")
    verifie(date_dividende_eng_vers_iso("26-May-26") == "2026-05-26",
            "« 26-May-26 » -> 2026-05-26")
    verifie(date_dividende_eng_vers_iso("1 Aug 2026") == "2026-08-01",
            "« 1 Aug 2026 » -> 2026-08-01")
    verifie(date_dividende_eng_vers_iso("30 September 24") == "2024-09-30",
            "le mois en entier est lu")
    verifie(date_dividende_eng_vers_iso("31 Feb 26") is None,
            "« 31 Feb 26 » n'existe pas -> refus")
    verifie(date_dividende_eng_vers_iso("26 Mai 26") is None,
            "« Mai » est francais, pas anglais -> refus (aucun melange de langues)")
    verifie(date_dividende_eng_vers_iso("30 Sep 97") is None,
            "hors fenetre 1998-2027 -> refus, l'ambiguite du siecle n'est pas masquee")
    verifie(date_dividende_eng_vers_iso("24/07/2017") is None,
            "un mois numerique est ambigu -> refus")
    verifie(date_dividende_eng_vers_iso("") is None, "vide -> None")

    # --- Une ligne de cotation complete, aux valeurs mesurees le 05/10 -------
    univers = univers_actions()
    # SNTS : cours 45,000 et PER 10.88 releves sur le bulletin anglais du
    # 02/10/2026 ; rendement 0.04 (arrondi) qui NE DOIT PAS entrer.
    snts = ["SNTS", "SONATEL SN", "TEL", "", "", "", "",
            "2,500", "112,500,000", "45,000", "12.50", "1,200.00", "26 May 26",
            "0.04", "10.88"]
    r = parser_ligne_eng(snts, univers=univers)
    verifie(r is not None, "la ligne SNTS est reconnue")
    if r:
        verifie(r["ticker"] == "SNTS", f"ticker SNTS (obtenu {r['ticker']})")
        verifie(r["cours"] == 45000.0,
                f"cours 45000, PAS 45 — le piege du facteur 1 000 (obtenu {r['cours']})")
        verifie(r["per"] == 10.88, f"PER 10.88 (obtenu {r['per']})")
        verifie(r["rendement"] is None,
                f"rendement VIDE, option (b) : l'anglais l'arrondit a 0.04 "
                f"(obtenu {r['rendement']})")
        verifie(r["rendement_brut_non_lu"] == "0.04",
                "la valeur arrondie est conservee pour le rapport, hors de la base")
        verifie(r["dividende_date"] == "2026-05-26",
                f"date de dividende 2026-05-26 (obtenu {r['dividende_date']})")
        verifie(r["volume_echange"] == 2500.0, f"volume 2500 (obtenu {r['volume_echange']})")
        verifie(r["valeur_echangee"] == 112500000.0,
                f"valeur 112500000 (obtenu {r['valeur_echangee']})")
        verifie(r["row_brut"] == snts, "la ligne brute est conservee pour le mode rapport")

    # --- Le cas qui prouve que le convertisseur francais aurait casse --------
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extracteur_boc import to_float as to_float_fr
    verifie(to_float_fr("45,000") == 45.0 and to_float_eng("45,000") == 45000.0,
            "le convertisseur FRANCAIS rend 45.0 la ou l'anglais rend 45000.0 : "
            "c'est tout l'objet de ce fichier")

    # --- Les refus de ligne --------------------------------------------------
    verifie(parser_ligne_eng(["SNTS", "x"] + [""] * 3, univers=univers) is None,
            "une ligne trop courte est refusee")
    entete = ["SECTOR", "TOTAL"] + [""] * 12
    vus = set()
    parser_ligne_eng(entete, ecartes=vus, univers=univers)
    verifie(not vus, "un entete anglais ne declenche aucune fausse alerte")
    inconnu = ["ZZZC", "UNKNOWN", "CD"] + [""] * 4 + [
        "10", "1,000", "5,000", "0.0", "5,100", "", "0.0", "9.9"]
    vus2 = set()
    verifie(parser_ligne_eng(inconnu, ecartes=vus2, univers=univers) is None
            and vus2 == {"ZZZC"},
            f"un mnemonique hors univers est NOMME, pas jete (obtenu {sorted(vus2)})")

    print(f"--- {ok} OK, {ech} ECHEC")
    return 0 if ech == 0 else 1


def _rapport(chemin):
    """Mode rapport : montre ce que le bulletin rend, sans rien ecrire."""
    ecartes = set()
    date_b, lignes = extraire_boc_eng(chemin, ecartes=ecartes)
    print(f"Bulletin : {Path(chemin).name}  |  date lue : {date_b}  |  "
          f"{len(lignes)} ligne(s) de cotation  |  {len(ecartes)} ecartee(s)")
    if ecartes:
        print("Ecartes par l'univers :", ", ".join(sorted(ecartes)))
    print()
    print(f"{'ticker':8} {'cours':>12} {'per':>8} {'volume':>12} {'valeur':>16} "
          f"{'div':>12} {'rdt NON LU':>11}")
    for l in sorted(lignes, key=lambda x: x["ticker"]):
        print(f"{l['ticker']:8} {str(l['cours']):>12} {str(l['per']):>8} "
              f"{str(l['volume_echange']):>12} {str(l['valeur_echangee']):>16} "
              f"{str(l['dividende_date']):>12} {str(l['rendement_brut_non_lu']):>11}")
    print()
    print("--- lignes brutes, telles que le PDF les donne (3 premieres) ---")
    for l in lignes[:3]:
        print(f"  {l['ticker']} : {l['row_brut']}")
    return 0 if lignes else 1


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_autotest())
    if len(sys.argv) > 1:
        sys.exit(_rapport(sys.argv[1]))
    print(__doc__)
    sys.exit(2)
