#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C26 — verser les publications intermediaires deja collectees
=======================================================================

Ce que ce script est
--------------------
Le proces-verbal executable de la **premiere passe sans reseau** de C26 : il
relit ``collecte/fondamentaux_extraits.csv``, isole les lignes tirees d'un
rapport trimestriel ou semestriel, et pour chacune dit -- avec son motif -- si
elle peut etre versee dans ``donnees/base/resultats_intermediaires.csv`` ou non.

Il est fait pour etre **relance** : le jour ou une reextraction remplira la
colonne ``unite``, ou ou un exercice sera entierement pave par ses
intermediaires, les lignes concernees basculeront d'elles-memes du cote
versable, et ``--verser`` les ecrira. Tant que rien ne change, il constate la
meme chose et n'ecrit rien.

Pourquoi il n'ecrit rien aujourd'hui (mesure du 03/10/2026, cycle 16)
---------------------------------------------------------------------
C26 demandait de retenir les lignes dont **l'exercice, la periode et l'unite**
sont determinables *sans deviner*. Les deux premiers le sont : le titre du
document les nomme, et le lire n'est pas deviner. **L'unite, non.**

  * la colonne ``unite`` est vide sur 138 des 139 lignes intermediaires ;
  * **aucun** exercice n'est entierement pave par ses intermediaires (ni
    T1..T4, ni S1+S2) : il n'existe donc pas une seule identite
    ``somme des intermediaires = resultat annuel certifie`` a fermer, qui
    seule prouverait l'unite d'un document ;
  * le facteur d'unite n'est pas une propriete du ticker. Sur les 37 lignes
    ANNUELLES du meme fichier confrontables a une valeur certifiee, 17 tombent
    sur un rapport qui est une puissance de 10 -- et elles emploient **quatre**
    conventions differentes (x1 : 6 lignes, x10^3 : 5, x10^6 : 5, x10^-3 : 1).
    Les **20 autres** ne tombent sur aucune puissance de 10 : le nombre extrait
    n'est alors pas le resultat net du document. Un facteur lu sur une ligne ne
    peut donc pas etre transporte sur une autre.

Convertir une de ces valeurs reviendrait a choisir un facteur 10^k par
vraisemblance d'ordre de grandeur. C'est exactement l'estimation que la premiere
regle du depot interdit : une case vide vaut mieux qu'une valeur approchee.

Le second refus, independant du premier
---------------------------------------
Le fichier rattache **15 lignes a un ticker qui n'est pas la societe du
document** nomme dans son URL, dont **12 lignes de TotalEnergies Marketing Cote
d'Ivoire (TTLC) classees sous TTLS**, TotalEnergies Marketing Senegal -- et
TTLC n'a aucune ligne a son nom. TTLS est le ticker de C7, « le dernier titre
sans ROE » : un cycle qui aurait puise ici pour combler C7 aurait ecrit la Cote
d'Ivoire dans le Senegal. La base certifiee, elle, est saine (verifie : les
lignes annuelles TTLC portent les documents CI, TTLS les documents SN).

Le controle de rattachement ci-dessous en attrape **2** sur 15, et il faut le
dire : il lit le fichier contre lui-meme (un slug de societe porte par quatorze
lignes sous STAC et une seule sous LNBB designe Setao). Cela ne marche que pour
une erreur ISOLEE. La TTLC -> TTLS est SYSTEMATIQUE -- les douze lignes du slug
``totalenergies_marketing_ci`` sont sous TTLS, qui est donc son ticker
majoritaire, et TTLC n'en a aucune : le majoritaire EST l'erreur. Les attraper
demande de confronter le nom du document au nom de la societe dans
``donnees/base/societes.csv``, ce qui est un chantier a part et non une garde de
ce script.

Le troisieme refus : une periode seule ou un cumul ?
----------------------------------------------------
Voir le commentaire de ``cumul_ou_periode()``. Seuls ``T1`` et ``S1`` ont une
lecture unique. La mesure sur PALC « 3eme trimestre 2024 » -- 16 156,388 M
contre un exercice 2024 certifie a 15 861,643 M -- montre qu'au moins un
document « 3eme trimestre » porte le cumul de neuf mois et non le trimestre.
C'est le piege que C26 avait verifie sur les T1/T2 de SGBC et qui se referme
dans l'autre sens sur les T3, dont le fichier porte 44 lignes.

Usage
-----
    python3 outils/versement_intermediaires.py            # rapport, n'ecrit rien
    python3 outils/versement_intermediaires.py --verser   # ecrit les versables
    python3 outils/versement_intermediaires.py --test     # autotest des regles
"""
import csv
import hashlib
import math
import re
import sqlite3
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
EXTRAITS = RACINE / "collecte" / "fondamentaux_extraits.csv"
CIBLE = RACINE / "donnees" / "base" / "resultats_intermediaires.csv"
DB = RACINE / "moteur" / "brvm.db"

# Liste BLANCHE des rangs de periode. Pas de correspondance par prefixe : un
# titre qui ecrit « 4e trimestre » plutot que « 4eme » doit echouer bruyamment
# et non etre pris pour un quatrieme trimestre devine.
RANGS = {"1er": 1, "2eme": 2, "3eme": 3, "4eme": 4,
         "premier": 1, "deuxieme": 2, "troisieme": 3, "quatrieme": 4}
# Les familles de periodes que benefice_glissant() sait cumuler.
PERIODES = {("trimestre", 1): "T1", ("trimestre", 2): "T2",
            ("trimestre", 3): "T3", ("trimestre", 4): "T4",
            ("semestre", 1): "S1", ("semestre", 2): "S2"}
MARQUEUR_INTER = re.compile(r"trimestre|semestre|trimestriel|semestriel")
BLOC_PERIODE = re.compile(
    r"(%s)[_ ](trimestre|semestre)[_ ](\d{4})" % "|".join(RANGS))
BLOC_ANNUEL = re.compile(r"etats_financiers(?:_\w+)?_(?:exercice_)?(\d{4})")


# ----------------------------------------------------------------------
# Lecture du titre du document : la periode et le millesime, ou un refus
# ----------------------------------------------------------------------
def lire_periode(url):
    """Rend (periode, exercice, motif_refus). Ne devine jamais.

    Le titre du document est la seule source de la periode : le fichier
    d'extraction ne porte aucune colonne de periode, et sa colonne ``exercice``
    est vide 95 fois sur 139 (et fausse quand elle est remplie : elle porte
    l'exercice du comparatif sur plusieurs lignes). Lire le titre n'est pas
    deviner ; en revanche un titre qui nomme DEUX periodes, ou une periode et un
    exercice annuel, ne dit pas lequel des deux a ete extrait -- refus.
    """
    nom = url.rsplit("/", 1)[-1].lower()
    nom = re.sub(r"^\d{8}_-?_?", "", nom)
    blocs = set(BLOC_PERIODE.findall(nom))
    if not blocs:
        return None, None, "periode ou millesime absent du titre du document"
    if len(blocs) > 1:
        return None, None, ("le titre nomme %d periodes : on ne sait pas laquelle a "
                            "ete extraite" % len(blocs))
    annuel = BLOC_ANNUEL.search(nom)
    if annuel:
        return None, None, ("le titre nomme aussi l'exercice annuel %s : on ne sait "
                            "pas lequel des deux a ete extrait" % annuel.group(1))
    rang, nature, an = blocs.pop()
    periode = PERIODES.get((nature, RANGS[rang]))
    if periode is None:
        return None, None, "periode hors liste blanche : %s %s" % (rang, nature)
    return periode, int(an), None


def slug_societe(url):
    """Le fragment de l'URL qui nomme la societe (dernier segment du titre)."""
    nom = url.rsplit("/", 1)[-1].lower()
    nom = re.sub(r"\.pdf$", "", nom)
    nom = re.sub(r"_\d+$", "", nom)
    parts = nom.split("_-_")
    return parts[-1] if len(parts) > 1 else nom


def table_rattachement(lignes):
    """slug de societe -> ticker majoritaire, lu sur le fichier lui-meme.

    Le fichier est sa propre reference : un slug porte par quatorze lignes sous
    STAC et une seule sous LNBB designe Setao, et c'est la ligne isolee qui est
    mal rattachee. Un slug partage a egalite n'arbitre rien et ne rattache rien.
    """
    compte = {}
    for r in lignes:
        compte.setdefault(slug_societe(r["source_url"]), {}).setdefault(
            r["ticker"], 0)
        compte[slug_societe(r["source_url"])][r["ticker"]] += 1
    table = {}
    for s, c in compte.items():
        ordre = sorted(c.items(), key=lambda kv: -kv[1])
        if len(ordre) == 1 or ordre[0][1] > ordre[1][1]:
            table[s] = ordre[0][0]
    return table


# ----------------------------------------------------------------------
# L'unite : prouvee ou refusee, jamais estimee
# ----------------------------------------------------------------------
def pavages_fermables(lignes, cur):
    """Les (ticker, exercice) dont les intermediaires pavent l'exercice entier.

    C'est la SEULE preuve d'unite disponible sans reseau : si T1..T4 (ou S1+S2)
    d'un exercice sont tous la, leur somme doit egaler le resultat annuel
    certifie, et le rapport des deux donne le facteur -- mesure, pas suppose.
    Mesure du 03/10/2026 : l'ensemble est VIDE.
    """
    par = {}
    for r in lignes:
        p, an, motif = lire_periode(r["source_url"])
        if motif or not (r["resultat_net"] or "").strip():
            continue
        par.setdefault((r["ticker"], an), set()).add(p)
    fermables = {}
    for (t, an), periodes in par.items():
        if not ({"T1", "T2", "T3", "T4"} <= periodes or {"S1", "S2"} <= periodes):
            continue
        annuel = cur.execute(
            "SELECT resultat_net FROM etats_financiers WHERE ticker=? AND exercice=? "
            "AND resultat_net IS NOT NULL", (t, an)).fetchone()
        if annuel and annuel[0]:
            fermables[(t, an)] = annuel[0]
    return fermables


def unite_prouvee(ligne, fermables):
    """Rend (facteur, motif_refus). Le facteur convertit la valeur en millions."""
    declaree = (ligne["unite"] or "").strip().lower()
    if declaree in ("millions", "million", "m"):
        return 1.0, None
    if declaree in ("milliers", "millier", "k"):
        return 1e-3, None
    if declaree in ("milliards", "milliard", "md"):
        return 1e3, None
    if declaree in ("unites", "unite", "fcfa"):
        return 1e-6, None
    if declaree:
        return None, "unite declaree non reconnue : %r" % declaree
    p, an, _m = lire_periode(ligne["source_url"])
    if (ligne["ticker"], an) in fermables:
        return None, ("unite non declaree, mais l'exercice est pave : facteur a "
                      "mesurer sur l'identite avec l'annuel certifie")
    return None, ("unite non declaree et aucune identite a fermer (l'exercice n'est "
                  "pas pave par ses intermediaires) : la deduire serait une estimation")


# ----------------------------------------------------------------------
# Une periode seule, ou le cumul depuis l'ouverture de l'exercice ?
# ----------------------------------------------------------------------
# benefice_glissant() a besoin de le savoir : il cumule T1..Tk en supposant que
# chaque ligne porte UN trimestre, et traite S1 et 9M comme portant deja le
# cumul. Se tromper double des mois ou en saute.
#
# Seuls T1 et S1 sont non ambigus : le premier trimestre et le premier semestre
# sont a la fois la periode et le cumul depuis l'ouverture, les deux lectures
# coincident. « 2eme », « 3eme », « 4eme trimestre » et « 2eme semestre » se
# lisent des deux facons et le titre ne tranche pas -- l'usage de la BRVM dit
# plutot « au 3eme trimestre » pour un cumul et « du 3eme trimestre » pour la
# periode, mais les deux tournures coexistent dans le meme corpus.
#
# Mesure du 03/10/2026 qui ferme le debat du cote du cumul, au moins une fois :
# PALC « 3eme trimestre 2024 », seule ligne du fichier dont l'unite soit
# declaree (milliers), vaut 16 156,388 M -- contre un resultat ANNUEL 2024
# certifie de 15 861,643 M. Un trimestre seul ne peut pas depasser son exercice
# entier sans que les trois autres se soldent en negatif ; un cumul de neuf
# mois, si. La ligne est donc vraisemblablement un 9M, et la coder T3 ferait
# compter neuf mois pour trois.
AMBIGUES = {"T2", "T3", "T4", "S2"}


def cumul_ou_periode(ligne, periode, exercice, facteur, cur):
    """Rend un motif de refus si la nature de la periode n'est pas etablie."""
    if periode in AMBIGUES:
        valeur = float(ligne["resultat_net"]) * facteur
        annuel = cur.execute(
            "SELECT resultat_net FROM etats_financiers WHERE ticker=? AND exercice=? "
            "AND resultat_net IS NOT NULL", (ligne["ticker"], exercice)).fetchone()
        preuve = ""
        if annuel and annuel[0] and abs(valeur) > abs(annuel[0]):
            preuve = (" — et sa valeur (%.0f M) depasse le resultat annuel %d certifie "
                      "(%.0f M), ce qu'une periode seule ne peut pas faire"
                      % (valeur, exercice, annuel[0]))
        return ("periode %s : le titre ne dit pas si le document porte la periode "
                "seule ou le cumul depuis l'ouverture de l'exercice%s" % (periode, preuve))
    return None


# ----------------------------------------------------------------------
# Le verdict, ligne par ligne
# ----------------------------------------------------------------------
def examiner(lignes, cur):
    rattachement = table_rattachement(lignes)
    fermables = pavages_fermables(
        [r for r in lignes if MARQUEUR_INTER.search(r["source_url"].lower())], cur)
    verdicts = []
    for r in lignes:
        if not MARQUEUR_INTER.search(r["source_url"].lower()):
            continue
        attendu = rattachement.get(slug_societe(r["source_url"]))
        if attendu and attendu != r["ticker"]:
            verdicts.append((r, None, None,
                             "rattache a %s alors que le document est celui de %s"
                             % (r["ticker"], attendu)))
            continue
        p, an, motif = lire_periode(r["source_url"])
        if motif:
            verdicts.append((r, None, None, motif))
            continue
        if not (r["resultat_net"] or "").strip():
            verdicts.append((r, p, an, "resultat net absent de l'extraction"))
            continue
        if not (r["resultat_net_n1"] or "").strip():
            verdicts.append((r, p, an, "comparatif N-1 absent : la fenetre glissante "
                                       "ne peut pas se soustraire"))
            continue
        facteur, motif_u = unite_prouvee(r, fermables)
        if facteur is None:
            verdicts.append((r, p, an, motif_u))
            continue
        motif_c = cumul_ou_periode(r, p, an, facteur, cur)
        if motif_c:
            verdicts.append((r, p, an, motif_c))
            continue
        verdicts.append((r, p, an, None))
    return verdicts, fermables


def rapport(verdicts, fermables):
    versables = [v for v in verdicts if v[3] is None]
    print("Lignes intermediaires examinees : %d" % len(verdicts))
    print("Exercices pavables (identite d'unite fermable) : %d" % len(fermables))
    print("VERSABLES : %d" % len(versables))
    familles = {}
    for _r, _p, _a, motif in verdicts:
        if motif is None:
            continue
        cle = re.sub(r"\b(TTLS|TTLC|LNBB|ECOC|FTSC|STAC)\b", "<ticker>", motif)
        cle = re.sub(r"\d{4}", "<annee>", cle)
        familles[cle] = familles.get(cle, 0) + 1
    print("REFUSEES : %d, par motif :" % (len(verdicts) - len(versables)))
    for m, n in sorted(familles.items(), key=lambda kv: -kv[1]):
        print("  %4d  %s" % (n, m[:110]))
    return versables


def verser(versables):
    if not versables:
        print("\nRien a verser : aucune ligne ne franchit les quatre controles.")
        print("Le fichier %s n'est pas touche." % CIBLE.relative_to(RACINE))
        return 0
    avant = hashlib.sha256(CIBLE.read_bytes()).hexdigest()
    existantes = {(r["ticker"], r["exercice"], r["periode"])
                  for r in csv.DictReader(CIBLE.open(encoding="utf-8"))}
    neuves = [v for v in versables
              if (v[0]["ticker"], str(v[2]), v[1]) not in existantes]
    if not neuves:
        print("\nVersement DEJA APPLIQUE : les %d ligne(s) versable(s) sont en base."
              % len(versables))
        return 0
    raise SystemExit(
        "REFUS : %d ligne(s) versable(s) absente(s) de la cible. Ce script ne sait "
        "pas encore ecrire une ligne neuve -- il a ete ecrit le jour ou il n'y en "
        "avait aucune, et inventer le format d'ecriture sans un seul cas reel "
        "serait du code jamais execute. L'ajouter est le travail du cycle qui "
        "verra la premiere. Empreinte cible inchangee : %s"
        % (len(neuves), avant[:16]))


# ----------------------------------------------------------------------
# Autotest des regles
# ----------------------------------------------------------------------
def autotest():
    echecs = []

    def v(cond, libelle):
        print(("  [OK]   " if cond else "  [ECHEC] ") + libelle)
        if not cond:
            echecs.append(libelle)

    print("=== Lecture du titre du document ===")
    cas = [
        ("20260422_-_rapport_dactivites_-_1er_trimestre_2026_-_x.pdf", "T1", 2026),
        ("20250430_-_rapport_dactivites_-_1er_semestre_2025_-_x.pdf", "S1", 2025),
        ("20240101_-_rapport_dactivites_-_3eme_trimestre_2024_-_x.pdf", "T3", 2024),
    ]
    for nom, p, an in cas:
        got = lire_periode("https://h/" + nom)
        v(got == (p, an, None), "%s -> %s %s (obtenu %r)" % (nom[:46], p, an, got))
    refus = [
        ("20260703_-_rapport_dactivites_-_4e_trimestre_2024_-_x.pdf",
         "« 4e » hors liste blanche : refus, pas un T4 devine"),
        ("20220530_-_rapport_dactivite_-_1er_trimestre_exercice_2022_-_x.pdf",
         "millesime separe du mot periode : refus"),
        ("20260505_-_rapport_dactivite_-_4eme_trimestre_2025_et_du_1er_trimestre_2026_-_x.pdf",
         "deux periodes nommees : refus"),
        ("20240429_-_etats_financiers_provisoires_2023_rapport_dactivite_1er_trimestre_2024_-_x.pdf",
         "un annuel nomme a cote de la periode : refus"),
        ("eviosys_packaging_siem_rapport_dactivites_1er_trimestre.pdf",
         "aucun millesime : refus"),
    ]
    for nom, libelle in refus:
        p, an, motif = lire_periode("https://h/" + nom)
        v(p is None and an is None and motif, libelle + (" — ACCEPTE : %r" % p if p else ""))

    print("=== L'unite ===")
    base = {"ticker": "X", "unite": "", "source_url":
            "https://h/20260422_-_rapport_dactivites_-_1er_trimestre_2026_-_x.pdf"}
    f, m = unite_prouvee(base, {})
    v(f is None and "estimation" in m, "unite vide sans pavage : refus (%s)" % m[:48])
    f, m = unite_prouvee(dict(base, unite="milliers"), {})
    v(f == 1e-3 and m is None, "unite declaree « milliers » -> facteur 1e-3")
    f, m = unite_prouvee(dict(base, unite="kilo-francs"), {})
    v(f is None and "non reconnue" in m, "unite declaree inconnue : refus, jamais 1.0")
    f, m = unite_prouvee(base, {("X", 2026): 1000.0})
    v(f is None and "pave" in m,
      "unite vide mais exercice pave : refus ici, le facteur est a mesurer")

    print("=== Rattachement au document ===")
    lignes = ([{"ticker": "STAC", "source_url": "https://h/a_-_setao_ci.pdf"}] * 14
              + [{"ticker": "LNBB", "source_url": "https://h/b_-_setao_ci.pdf"}])
    t = table_rattachement(lignes)
    v(t.get("setao_ci.pdf") == "STAC" or t.get("setao_ci") == "STAC",
      "slug majoritaire -> STAC (obtenu %r)" % t)
    partage = [{"ticker": "A", "source_url": "https://h/x_-_s.pdf"},
               {"ticker": "B", "source_url": "https://h/y_-_s.pdf"}]
    v("s.pdf" not in table_rattachement(partage)
      and "s" not in table_rattachement(partage),
      "slug partage a egalite : aucun rattachement, donc aucune accusation")

    print("=== Periode seule ou cumul ===")
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE etats_financiers (ticker TEXT, exercice INT, "
                 "resultat_net REAL)")
    conn.execute("INSERT INTO etats_financiers VALUES ('X',2024,15861.643)")
    cj = conn.cursor()
    l = {"ticker": "X", "resultat_net": "16156388.0"}
    m = cumul_ou_periode(l, "T3", 2024, 1e-3, cj)
    v(m is not None and "depasse le resultat annuel" in m,
      "T3 refuse, et la preuve du depassement annuel est citee")
    v(cumul_ou_periode(l, "T1", 2024, 1e-3, cj) is None,
      "T1 accepte : la periode et le cumul coincident a l'ouverture")
    v(cumul_ou_periode({"ticker": "X", "resultat_net": "100.0"}, "S1", 2024, 1.0, cj)
      is None, "S1 accepte pour la meme raison")
    m = cumul_ou_periode({"ticker": "X", "resultat_net": "100.0"}, "T2", 2024, 1.0, cj)
    v(m is not None and "depasse" not in m,
      "T2 refuse sur l'ambiguite seule, sans preuve de depassement")
    conn.close()

    print("\n%s : %d cas, %d echec(s)" % (Path(__file__).name,
                                          len(cas) + len(refus) + 10, len(echecs)))
    return 1 if echecs else 0


def main():
    if "--test" in sys.argv:
        return autotest()
    if not DB.exists():
        raise SystemExit("REFUS : %s absent. Construire la base d'abord." % DB)
    lignes = list(csv.DictReader(EXTRAITS.open(encoding="utf-8")))
    cur = sqlite3.connect(DB).cursor()
    verdicts, fermables = examiner(lignes, cur)
    versables = rapport(verdicts, fermables)
    if "--verser" in sys.argv:
        return verser(versables)
    print("\nRapport seul (ajouter --verser pour ecrire). Aucun fichier touche.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
