#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/arbitrage.py (26/09/2026) — CONFRONTATION DE LA BASE A UNE SOURCE EXTERIEURE.

POURQUOI CE MODULE EXISTE
-------------------------
Les 28 golden tests et les 11 sections de tester_donnees.py verifient la
coherence INTERNE de la base : echelles, statuts, series consecutives,
contradictions entre une ligne d'exercice et un comparatif N-1 du meme
document. Aucun ne confronte la base a une source EXTERIEURE. Une base peut
donc etre parfaitement coherente avec elle-meme et fausse.

Mesure du 26/09/2026 qui a motive ce module : sur les 37 titres ou les deux
chaines du projet donnent le glissement du MEME exercice, l'ecart median est
de 0,0 point et 32 titres sur 37 sont sous les 10 points. La saisie manuelle
de peupler.py est donc fiable. Mais les 5 ecarts restants contenaient DEUX
erreurs de saisie qu'aucun test n'avait vues :

  ECOC 2025 : resultat_net=57477 / resultat_net_n1=63482 -> -9,5 %/an.
              En permutant les deux colonnes : +10,45 %, soit exactement le
              taux publie par l'agregateur ; et 63482/132725 = 47,83 %, soit
              exactement la marge nette publiee. Le profil GARP d'ECOC
              (+26,5 %/an) reposait sur une serie au dernier point inverse.
  BOAS 2025 : meme signature. Permutation -> +9,62 % contre +9,61 % publie,
              et 21906/51926 = 42,19 % = marge publiee. Profil VALUE.

DOCTRINE (a ne pas contourner en aval)
--------------------------------------
1. Ce module NE REECRIT JAMAIS une donnee certifiee au demarrage. Une ligne
   VALIDE prise en defaut est SIGNALEE et son profil est SUSPENDU, avec dans
   la reserve la correction exacte a porter dans peupler.py. Si le moteur
   corrigeait de lui-meme, la base dirait une chose et le tableau de bord une
   autre, et la correction ne serait jamais faite.
2. La substitution automatique est autorisee dans UN seul cas : une ligne
   PROBABLE issue d'un OCR a source unique, jamais certifiable par
   construction. Elle est alors journalisee dans le rapport.
3. Jamais de moyenne entre les deux sources : elle fabriquerait un chiffre
   qu'aucun document ne publie et qu'on ne pourrait justifier. Jamais non
   plus "la valeur la plus prudente" : cela biaiserait tout l'outil vers le
   pessimisme et rendrait son erreur non mesurable.
4. La confrontation porte sur le GLISSEMENT D'UN EXERCICE (grandeur commune
   aux deux sources), jamais sur le taux annuel moyen du moteur. Le taux
   annuel moyen reste le bon axe de profilage (GARP suppose une croissance
   soutenable, pas un bon exercice) : l'agregateur controle sa matiere
   premiere, exercice par exercice, il ne le remplace pas.

CE QUE CE MODULE NE PROUVE PAS
------------------------------
La concordance valide la TRANSCRIPTION, pas la substance economique. AGL CI
le rappelle : les deux sources s'accordaient sur un resultat des activites
ordinaires de 21,8 milliards, fait a 96 % de produits financiers, et le
resultat net s'est effondre de 96 % l'exercice suivant. C'est le role du
resultat d'exploitation (drapeau RESULTAT_NON_OPERATIONNEL), pas celui-ci.

SORTIE
------
collecte/arbitrage_croissance.csv — une ligne par titre confronte, pour que
les cas a corriger soient actionnables sans relire les journaux.
"""

import csv
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
AGREGATEUR = RACINE / "docs" / "data_brvm.json"
RAPPORT = RACINE / "collecte" / "arbitrage_croissance.csv"

# Seuils. PROVISOIRES, calibres sur la mesure du 26/09/2026 (37 titres) :
#   - 10 pts : separe les 32 concordants des 5 ecarts reels sans coupe arbitraire
#     (le 32e concordant est a 8,3 pts, le 1er ecart reel a 13,2 pts)
#   - 30 pts : au-dela, aucune difference de convention comptable plausible
#   - 0,1 pt et 0,05 pt : tolerances d'arrondi des deux identites de permutation
SEUIL_CONCORDANCE = 10.0
SEUIL_CONTESTATION = 30.0
TOLERANCE_PERMUTATION = 0.15
TOLERANCE_MARGE = 0.06

DRAPEAUX = (
    "CROISSANCE_CORROBOREE",
    "ECART_AGREGATEUR",
    "VALEUR_REPRISE_AGREGATEUR",
    "FONDAMENTAL_EN_RETARD",
    "PERMUTATION_PROBABLE",
    "PERMUTATION_SUSPECTEE",
    "CROISSANCE_CONTESTEE",
)


# La chaine pipeline/ et le moteur ne nomment pas toujours le titre de la meme
# facon. Sans cet alias, Bridge Bank serait invisible a l'arbitrage alors que
# les deux chaines la connaissent — chacune sous son code.
ALIAS_TICKERS = {"BBGC": "BBGCI"}


def charger_agregateur(chemin=AGREGATEUR):
    """Lit docs/data_brvm.json (chaine pipeline/). Absent -> {} sans echouer.

    L'arbitrage est un garde-fou, jamais une dependance bloquante : si le
    fichier manque, le moteur doit continuer a profiler comme avant.

    Complete le 27/09/2026 : le fichier ne sert plus seulement a confronter la
    croissance. Il porte, pour 47 titres sur 47, le chiffre d'affaires, la
    marge nette et la croissance du chiffre d'affaires — trois grandeurs que le
    moteur n'avait PAS DU TOUT — et, pour 25 titres, des capitaux propres avec
    leur millesime et l'URL du rapport de notation dont ils sont tires.
    """
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    lignes = brut.get("rows") or []
    out = {}
    for r in lignes:
        sym = r.get("sym")
        if not sym:
            continue
        sym = ALIAS_TICKERS.get(sym, sym)
        try:
            exercice = int(str(r.get("exercice") or "").strip()[:4])
        except ValueError:
            exercice = None
        try:
            exercice_cp = int(str(r.get("cp_exercice") or "").strip()[:4])
        except ValueError:
            exercice_cp = None
        out[sym] = {
            "exercice": exercice,
            "rn": r.get("rn"),
            "ca": r.get("ca"),
            "croissance_rn": r.get("croiRN"),
            "croissance_ca": r.get("croiCA"),
            "marge_nette": r.get("margeN"),
            "capitaux_propres": r.get("cp"),
            "exercice_cp": exercice_cp,
            "source_roe": r.get("roe_src"),
            "reference_31_decembre": r.get("ref31"),
            "seance": (brut.get("meta") or {}).get("boc_seance"),
        }
    return out


def _glissement(rn, rn_n1):
    """Variation en % d'un exercice sur le precedent. None si incalculable."""
    if rn is None or rn_n1 in (None, 0):
        return None
    return 100.0 * (rn - rn_n1) / abs(rn_n1)


def _proche(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def _derniere_ligne(cur, ticker):
    """Ligne d'exercice la plus recente portant un resultat net."""
    return cur.execute(
        "SELECT exercice, resultat_net, resultat_net_n1, statut_donnee, source_type "
        "FROM etats_financiers WHERE ticker=? AND resultat_net IS NOT NULL "
        "ORDER BY exercice DESC LIMIT 1", (ticker,)).fetchone()


def arbitrer(cur, ticker, agregateur):
    """Confronte le dernier exercice de la base a l'agregateur.

    Retourne un dict :
      regle          : numero de la regle appliquee (0 = aucune confrontation)
      drapeau        : nom du drapeau a ajouter, ou None
      correctif      : {exercice: resultat_net} a appliquer a la serie, ou {}
      corroboree     : True si la regle 1 s'applique (peut relever le grade)
      bloquant       : True si le profil doit etre suspendu
      axe_retire     : True si l'axe croissance doit etre retire
      detail         : phrase prete a figurer dans les reserves
      mesures        : les nombres, pour le rapport CSV
    """
    vide = dict(regle=0, drapeau=None, correctif={}, corroboree=False,
                bloquant=False, axe_retire=False, detail=None, mesures={})
    agr = (agregateur or {}).get(ticker)
    if not agr:
        return vide
    base = _derniere_ligne(cur, ticker)
    if not base:
        return vide
    ex_base, rn, rn_n1, statut, source_type = base
    ex_agr = agr["exercice"]
    croi_agr = agr["croissance_rn"]

    mesures = dict(exercice_base=ex_base, exercice_agregateur=ex_agr,
                   rn_base=rn, rn_n1_base=rn_n1, rn_agregateur=agr["rn"],
                   statut_base=statut, source_base=source_type,
                   glissement_base=None, glissement_agregateur=croi_agr,
                   ecart=None)

    # --- Regle 4 : l'agregateur a un exercice plus recent que la base.
    # Ce n'est pas un desaccord, c'est un fondamental manquant. On ne fabrique
    # PAS la ligne (elle doit etre lue dans le document certifie), on signale.
    if ex_agr is not None and ex_base is not None and ex_agr > ex_base:
        return dict(vide, regle=4, drapeau="FONDAMENTAL_EN_RETARD", mesures=mesures,
                    detail="exercice %d disponible chez l'agregateur (resultat net %s) "
                           "alors que la base s'arrete a %d : le profil porte sur des "
                           "comptes perimes, saisir l'exercice manquant dans "
                           "donnees/base/etats_financiers.csv"
                           % (ex_agr, _fr(agr["rn"]), ex_base))

    if croi_agr is None:
        return vide

    glissement = _glissement(rn, rn_n1)
    if glissement is None:
        return vide
    mesures["glissement_base"] = round(glissement, 2)
    ecart = glissement - croi_agr
    mesures["ecart"] = round(ecart, 2)

    # --- Regle 5 : permutation des colonnes resultat_net / resultat_net_n1.
    # Deux identites independantes, exigees ensemble pour parler de permutation
    # PROBABLE ; une seule suffit a la juger SUSPECTEE (et a bloquer quand meme,
    # mais sans affirmer le diagnostic).
    if abs(ecart) > SEUIL_CONCORDANCE:
        glissement_permute = _glissement(rn_n1, rn)
        identite_taux = _proche(glissement_permute, croi_agr, TOLERANCE_PERMUTATION)
        marge_permutee = (100.0 * rn_n1 / agr["ca"]) if (rn_n1 and agr["ca"]) else None
        identite_marge = _proche(marge_permutee, agr["marge_nette"], TOLERANCE_MARGE)
        if identite_taux:
            mesures["glissement_permute"] = round(glissement_permute, 2)
            if marge_permutee is not None:
                mesures["marge_permutee"] = round(marge_permutee, 2)
            preuves = ["en permutant les deux colonnes, le glissement devient "
                       "%+.2f %% contre %+.2f %% publie par l'agregateur"
                       % (glissement_permute, croi_agr)]
            if identite_marge:
                preuves.append("et %s rapporte au chiffre d'affaires de %s donne "
                               "%.2f %%, soit la marge nette publiee (%.2f %%)"
                               % (_fr(rn_n1), _fr(agr["ca"]), marge_permutee,
                                  agr["marge_nette"]))
            drapeau = ("PERMUTATION_PROBABLE" if identite_marge
                       else "PERMUTATION_SUSPECTEE")
            return dict(vide, regle=5, drapeau=drapeau, bloquant=True,
                        axe_retire=True, mesures=mesures,
                        detail="colonnes resultat_net et resultat_net_n1 vraisemblablement "
                               "permutees sur l'exercice %d : %s. CORRECTION A PORTER dans "
                               "donnees/base/etats_financiers.csv : sur la ligne %s/%d, "
                               "echanger resultat_net (%s) et resultat_net_n1 (%s) apres "
                               "verification du document source."
                               % (ex_base, " ; ".join(preuves), ticker, ex_base,
                                  _py(rn), _py(rn_n1)))

    # --- Regle 1 : concordance. Deux lectures independantes des memes comptes
    # publies se rejoignent : la transcription est corroboree.
    if abs(ecart) <= SEUIL_CONCORDANCE:
        return dict(vide, regle=1, drapeau="CROISSANCE_CORROBOREE",
                    corroboree=(statut == "VALIDE"), mesures=mesures,
                    detail="glissement %+.2f %% en base contre %+.2f %% chez "
                           "l'agregateur (ecart %.1f pt) : transcription corroboree "
                           "par une source independante"
                           % (glissement, croi_agr, abs(ecart)))

    # --- Regle 2 : le document certifie l'emporte sur l'agregateur.
    if statut == "VALIDE":
        return dict(vide, regle=2, drapeau="ECART_AGREGATEUR", mesures=mesures,
                    detail="glissement %+.2f %% en base (ligne certifiee) contre "
                           "%+.2f %% chez l'agregateur : ecart de %.1f pt non explique, "
                           "la ligne certifiee est conservee mais le perimetre "
                           "(consolide, part du groupe) reste a verifier"
                           % (glissement, croi_agr, abs(ecart)))

    # --- Regle 3 : une ligne PROBABLE issue d'un OCR a source unique n'est
    # jamais certifiable ; l'agregateur arbitre, et la substitution est journalisee.
    if statut == "PROBABLE" and source_type == "OCR" and agr["rn"]:
        return dict(vide, regle=3, drapeau="VALEUR_REPRISE_AGREGATEUR",
                    correctif={ex_base: float(agr["rn"])}, mesures=mesures,
                    detail="ligne %d transcrite par OCR a source unique (jamais "
                           "certifiable) et en ecart de %.1f pt : resultat net repris "
                           "de l'agregateur (%s au lieu de %s)"
                           % (ex_base, abs(ecart), _fr(agr["rn"]), _fr(rn)))

    # --- Regle 6 : aucune regle ne tranche et l'ecart est trop large pour
    # qu'une convention comptable l'explique. On retire l'axe plutot que de
    # profiler sur un chiffre contested.
    if abs(ecart) > SEUIL_CONTESTATION:
        return dict(vide, regle=6, drapeau="CROISSANCE_CONTESTEE", axe_retire=True,
                    mesures=mesures,
                    detail="glissement %+.2f %% en base contre %+.2f %% chez "
                           "l'agregateur (ecart %.1f pt) sans regle d'arbitrage "
                           "applicable : l'axe croissance est retire"
                           % (glissement, croi_agr, abs(ecart)))

    return dict(vide, regle=2, drapeau="ECART_AGREGATEUR", mesures=mesures,
                detail="glissement %+.2f %% en base contre %+.2f %% chez "
                       "l'agregateur (ecart %.1f pt)"
                       % (glissement, croi_agr, abs(ecart)))


def _fr(x):
    """Formate un montant en millions FCFA, separateur d'espace insecable."""
    if x is None:
        return "n.d."
    if abs(x) >= 1000:
        return format(x, ",.0f").replace(",", " ")
    return "%.2f" % x


def _py(x):
    """Reproduit la valeur telle qu'elle figure dans le CSV de reference."""
    if x is None:
        return "None"
    return str(int(x)) if float(x).is_integer() else repr(x)


def ecrire_rapport(verdicts, chemin=RAPPORT):
    """Un CSV des confrontations, pour rendre les cas a corriger actionnables."""
    colonnes = ["ticker", "regle", "drapeau", "exercice_base", "exercice_agregateur",
                "rn_base", "rn_n1_base", "rn_agregateur", "statut_base", "source_base",
                "glissement_base", "glissement_agregateur", "ecart",
                "glissement_permute", "marge_permutee", "detail"]
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        w.writeheader()
        for ticker, v in sorted(verdicts.items()):
            if not v.get("drapeau"):
                continue
            ligne = {"ticker": ticker, "regle": v["regle"], "drapeau": v["drapeau"],
                     "detail": v.get("detail") or ""}
            ligne.update(v.get("mesures") or {})
            w.writerow(ligne)
    return chemin


EXPLICATIONS = {
    "CROISSANCE_CORROBOREE":
        "le glissement du dernier exercice concorde avec une source exterieure "
        "independante : la transcription des comptes est corroboree",
    "ECART_AGREGATEUR":
        "une source exterieure donne un glissement sensiblement different sur le "
        "meme exercice — la ligne certifiee est conservee, mais le perimetre "
        "(consolide ou part du groupe) reste a verifier sur le document",
    "VALEUR_REPRISE_AGREGATEUR":
        "resultat net repris d'une source exterieure parce que la ligne en base "
        "provient d'un OCR a source unique, jamais certifiable",
    "FONDAMENTAL_EN_RETARD":
        "un exercice plus recent est publie et absent de la base : le profil porte "
        "sur des comptes perimes",
    "PERMUTATION_PROBABLE":
        "les colonnes resultat_net et resultat_net_n1 sont permutees sur le dernier "
        "exercice — demontre par deux identites independantes, profil suspendu",
    "PERMUTATION_SUSPECTEE":
        "les colonnes resultat_net et resultat_net_n1 sont probablement permutees "
        "(une seule identite verifiee) — profil suspendu, arbitrer sur le document",
    "CROISSANCE_CONTESTEE":
        "deux sources donnent des glissements inconciliables sans qu'aucune regle "
        "ne puisse trancher : l'axe croissance est retire",
}


if __name__ == "__main__":
    import sqlite3
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "brvm.db")
    conn = sqlite3.connect(base)
    cur = conn.cursor()
    agr = charger_agregateur()
    if not agr:
        print("agregateur introuvable (%s) — rien a confronter" % AGREGATEUR)
        raise SystemExit(0)
    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]
    verdicts = {t: arbitrer(cur, t, agr) for t in tickers}
    conn.close()
    par_regle = {}
    for t, v in verdicts.items():
        if v["drapeau"]:
            par_regle.setdefault(v["drapeau"], []).append(t)
    chemin = ecrire_rapport(verdicts)
    print("arbitrage : %d titres confrontes a %s (seance %s)"
          % (sum(1 for v in verdicts.values() if v["regle"]), AGREGATEUR.name,
             (list(agr.values())[0] or {}).get("seance")))
    for d in DRAPEAUX:
        if d in par_regle:
            print("  %-26s %2d  %s" % (d, len(par_regle[d]), " ".join(sorted(par_regle[d]))))
    print("rapport : %s" % chemin)
    for t, v in sorted(verdicts.items()):
        if v["bloquant"] or v["axe_retire"]:
            print("\n[%s] %s\n  %s" % (t, v["drapeau"], v["detail"]))
