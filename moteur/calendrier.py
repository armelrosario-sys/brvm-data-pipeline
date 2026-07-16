#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moteur/calendrier.py — CHANTIER 2 (14/07/2026) : calendrier des publications.

Derive, quasi gratuitement, un calendrier des depots par titre et par
categorie de document a partir des DATES DEJA PRESENTES dans les noms de
fichiers du MANIFESTE (audit du 14/07/2026 : 866/924 rapports, soit 94%,
ont une date AAAAMMJJ et un nom d'entreprise extractibles du nom de fichier
sans aucune collecte supplementaire).

Ce module NE modifie PAS le signal D4 (retard de publication), qui reste
pour l'instant alimente manuellement via avis_reglementaires -- l'automatiser
completement est le prolongement naturel de ce chantier, delibrement laisse
pour une etape separee et testable independamment (discipline du projet :
un chantier a la fois).

Sortie : collecte/calendrier.json
  { ticker: { categorie: { dernier_depot: "AAAA-MM-JJ", mois_habituel: int,
                           nb_occurrences: int, historique: [dates] } } }

Correspondance ticker <-> slug de fichier : derivee DYNAMIQUEMENT depuis
SOCIETES (peupler.py) a chaque execution, jamais figee en dur -- si un
ticker est ajoute/renomme, la correspondance se recalcule automatiquement.
Un seul cas non deductible automatiquement (abreviation) : LNBB -> lnb_bn.
BBGCI : aucun document trouve dans le MANIFESTE sous quelque nom que ce
soit (meme situation que SDSC avant le 14/07/2026) -- signale, pas bloquant.
"""
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE = RACINE / "MANIFESTE.csv"
SORTIE = RACINE / "collecte" / "calendrier.json"

CORRECTIFS_MANUELS = {"LNBB": "lnb_bn"}  # abreviations non deductibles par slugification

PATTERN_NOM = re.compile(r"^[0-9a-f]{8}_(\d{8})_-_(.+?)_-_([a-z0-9_]+)\.pdf$", re.I)


def _slugify(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", txt.lower()).strip("_")


def _categoriser(libelle):
    """Categorie de document, dans un vocabulaire STABLE et VERSIONNABLE.
    'autre' capte tout ce qui ne correspond a aucun motif connu -- volontairement
    peu couvrant plutot que de deviner a tort (integrite > couverture)."""
    l = libelle.lower()
    # Correctif (15/07/2026, decouvert en branchant l'extracteur automatique) :
    # un vrai "rapport des CAC" s'intitule souvent "...sur les ETATS
    # FINANCIERS annuels" -- le test etats_financiers, place AVANT celui du
    # CAC, capturait donc a tort ces documents (aucune donnee chiffree
    # exploitable dedans, juste l'opinion textuelle des commissaires).
    # Le test CAC doit passer EN PREMIER.
    if ("rapport_des_cac" in l or "attestation_des_commissaires" in l or "attestation_des_cac" in l
            or "rapport_des_commissaires_aux_comptes" in l):
        return "rapport_cac"
    if "etats_financiers" in l or "etat_financier" in l:
        return "etats_financiers"
    if "1er_trimestre" in l or "premier_trimestre" in l or "1er_trim" in l:
        return "activite_T1"
    if "2eme_trimestre" in l or "2e_trimestre" in l:
        return "activite_T2"
    if "3eme_trimestre" in l or "3e_trimestre" in l or "3t" in l:
        return "activite_T3"
    if "1er_semestre" in l or "premier_semestre" in l:
        return "activite_S1"
    if "resolution" in l or "assemblee" in l or "_ago_" in l or l.startswith("ago"):
        return "resolutions_ago"
    return "autre"


def construire_mapping(peupler_path):
    """Derive ticker -> slug de fichier depuis SOCIETES (peupler.py) et les
    slugs reellement observes dans le MANIFESTE. Jamais fige en dur."""
    src = peupler_path.read_text()
    m = re.search(r"SOCIETES = \[(.*?)\n\]", src, re.S)
    lignes = re.findall(r'\("([A-Z_]+)",\s*"([^"]+)"', m.group(1))
    noms = {t: n for t, n in lignes if not t.startswith("TEST_")}

    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    slugs_fichiers = Counter()
    for r in rows:
        if r["type"] != "rapport":
            continue
        mm = PATTERN_NOM.match(r["nom_fichier"])
        if mm:
            slugs_fichiers[mm.group(3)] += 1

    # Correctif 15/07/2026 (decouvert via le signal D5) : departager par
    # FREQUENCE reelle plutot que par longueur du slug. "Longueur minimale"
    # choisissait systematiquement une variante rare/ancienne (souvent sans
    # suffixe pays -bf/-ci/-tg) plutot que le vrai slug utilise par la
    # quasi-totalite des documents -- 7 titres etaient touches (CBIBF, NSBC,
    # ORGT, SEMC, SHEC, SLBC, SOGC), chacun ampute de 90%+ de son historique
    # reel sans qu'aucune erreur ne soit visible (juste tres peu de donnees).
    mapping = dict(CORRECTIFS_MANUELS)
    non_couverts = []
    for t, n in noms.items():
        if t in mapping:
            continue
        s_nom = _slugify(n)
        # Correctif 15/07/2026 : departager par FREQUENCE reelle plutot que
        # par longueur (cf. Coris/NSIA/Oragroup/Vivo/Solibra/SOGB, chacun
        # ampute a 1 seul document par l'ancienne regle "plus court").
        # ATTENTION (2e decouverte, meme session) : fusionner ce candidat
        # precis avec le repli generique "premier mot" a ete tente puis
        # ANNULE -- ca provoquait des collisions entre entites d'une meme
        # marque multi-pays (6 filiales BOA, TotalEnergies, Ecobank, Societe
        # Generale toutes reduites au meme slug generique "boa_ci" etc.).
        # Le repli generique reste donc reserve au cas ou la recherche
        # precise (sur le nom complet) ne trouve LITTERALEMENT rien.
        candidats = {sf for sf in slugs_fichiers if s_nom in sf or sf in s_nom}
        if not candidats:
            premier_mot = s_nom.split("_")[0]
            candidats = {sf for sf in slugs_fichiers if sf.startswith(premier_mot + "_") or sf == premier_mot}
        if candidats:
            mapping[t] = max(candidats, key=lambda sf: slugs_fichiers[sf])
        else:
            non_couverts.append(t)

    # Filet de securite (15/07/2026) : toute collision restante (deux tickers
    # resolus au MEME slug -- cas encore ouverts : familles multi-pays comme
    # BOA/Ecobank ou homonymes partiels non repares aujourd'hui) est EXCLUE
    # plutot que laissee attribuer les documents d'une entite a une autre.
    # Une donnee manquante (non couvert) est toujours preferable a une donnee
    # fausse (mauvaise attribution silencieuse) -- integrite > couverture.
    compte_usage = Counter(mapping.values())
    tickers_en_collision = [t for t, sf in list(mapping.items())
                           if compte_usage[sf] > 1 and t not in CORRECTIFS_MANUELS]
    for t in tickers_en_collision:
        del mapping[t]
        non_couverts.append(t)

    return mapping, sorted(non_couverts)


def construire_calendrier(mapping):
    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    slug_vers_ticker = {v: k for k, v in mapping.items()}
    par_ticker = {}
    for r in rows:
        if r["type"] != "rapport":
            continue
        mm = PATTERN_NOM.match(r["nom_fichier"])
        if not mm:
            continue
        date_brute, libelle, slug = mm.groups()
        ticker = slug_vers_ticker.get(slug)
        if not ticker:
            continue
        date_iso = f"{date_brute[:4]}-{date_brute[4:6]}-{date_brute[6:]}"
        cat = _categoriser(libelle)
        par_ticker.setdefault(ticker, {}).setdefault(cat, []).append(date_iso)

    calendrier = {}
    for ticker, cats in par_ticker.items():
        calendrier[ticker] = {}
        for cat, dates in cats.items():
            dates_triees = sorted(dates)
            mois = Counter(int(d[5:7]) for d in dates_triees)
            mois_habituel = mois.most_common(1)[0][0] if mois else None
            calendrier[ticker][cat] = dict(
                dernier_depot=dates_triees[-1],
                mois_habituel=mois_habituel,
                nb_occurrences=len(dates_triees),
                historique=dates_triees,
            )
    return calendrier


def echeance_reglementaire(categorie, annee_reference, delais_cfg):
    """Date limite reglementaire CREPMF pour une categorie et une annee de
    reference donnees (l'annee du CYCLE, pas forcement l'annee de depot :
    pour etats_financiers, annee_reference = l'exercice concerne, l'echeance
    tombe l'annee suivante). Retourne None si la categorie n'a pas de regle
    reglementaire fiable (ex. rapport_cac)."""
    r = delais_cfg.get(categorie)
    if not r:
        return None
    annee_echeance = annee_reference + r.get("decalage_annee", 0)
    return date(annee_echeance, r["mois"], r["jour"])


def cycle_le_plus_recent(categorie, aujourd_hui, delais_cfg):
    """Retourne (annee_reference, echeance) du cycle EN COURS pour cette
    categorie a la date consideree -- c'est-a-dire le cycle dont l'echeance
    tombe dans l'annee civile courante. Utilise pour limiter l'affichage aux
    seules obligations de l'annee en cours, comme demande le 15/07/2026."""
    r = delais_cfg.get(categorie)
    if not r:
        return None, None
    annee_ref = aujourd_hui.year - r.get("decalage_annee", 0)
    echeance = echeance_reglementaire(categorie, annee_ref, delais_cfg)
    return annee_ref, echeance


def deja_satisfait(categorie, historique, annee_ref, delais_cfg):
    """Un depot couvre-t-il DEJA le cycle de annee_ref ? Approximation : tout
    depot posterieur a l'echeance du cycle PRECEDENT est considere comme
    couvrant le cycle courant (les rapports sont sequentiels par nature)."""
    r = delais_cfg.get(categorie)
    if not r or not historique:
        return False
    echeance_precedente = echeance_reglementaire(categorie, annee_ref - 1, delais_cfg)
    return any(d > echeance_precedente for d in historique)


def age_meilleure_information(ticker_categories, aujourd_hui):
    """Age (en jours) du document le plus RECENT pour un titre, toutes
    categories confondues (y compris celles exclues du calcul d'echeance
    D4 pour irregularite -- ici, tout document est une preuve de vie valable,
    peu importe sa categorie). Retourne (date_derniere_info, jours) ou
    (None, None) si aucune donnee. Sert exclusivement au signal D5, JAMAIS
    a D4 -- les deux mesurent des choses differentes et ne se melangent pas."""
    toutes_dates = []
    for categorie, v in ticker_categories.items():
        toutes_dates += [date(*map(int, d.split("-"))) for d in v["historique"]]
    if not toutes_dates:
        return None, None
    derniere = max(toutes_dates)
    return derniere, (aujourd_hui - derniere).days


def calculer():
    mapping, non_couverts = construire_mapping(RACINE / "moteur" / "peupler.py")
    calendrier = construire_calendrier(mapping)
    SORTIE.write_text(json.dumps(calendrier, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"calendrier.json : {len(calendrier)} tickers couverts "
          f"({len(mapping)} mappings, {len(non_couverts)} non couverts : {non_couverts})")
    return calendrier, non_couverts


if __name__ == "__main__":
    calculer()
