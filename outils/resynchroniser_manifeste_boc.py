#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C35 — les deux releves ne sont pas en panne : MANIFESTE.csv est en panne
=============================================================================

LE CONSTAT, MESURE LE 08/10/2026 (cycle 23)
-------------------------------------------
``collecte/dividendes_historique.csv`` et
``collecte/liquidite_quotidienne_historique.csv`` s'arretent tous deux le
2026-07-24. Les deux sont produits par ``collecte/backfill_dividendes.py`` et
``collecte/backfill_liquidite.py``, qui parcourent les lignes ``type=boc`` de
``MANIFESTE.csv`` et telechargent le PDF correspondant depuis les Releases.

Or les PDF SONT dans la Release. ``boc-2026`` porte 20 bulletins dates du
2026-08-05 au 2026-10-01 que ``MANIFESTE.csv`` ne declare pas. Les deux
backfills ne sont donc pas en retard : ils sont AVEUGLES. Aucune relance, aucun
workflow, aucune planification ne les ferait avancer d'une ligne tant que le
manifeste ne declare pas ces bulletins.

LA CAUSE, ET ELLE EST DANS LE JOURNAL DU RUN, PAS DANS UNE HYPOTHESE
--------------------------------------------------------------------
``collecte.yml`` (P2b) s'execute lundi et jeudi et REUSSIT a chaque fois. Son
run 26 du 2026-10-05 a collecte 3 fichiers, les a publies dans la Release...
puis a jete leurs lignes de manifeste. Journal du run, verbatim :

    fatal: pathspec 'echecs_upload.txt' did not match any files
    Changes not staged for commit:  modified: MANIFESTE.csv ...
    no changes added to commit
    rien a committer
    Everything up-to-date

L'etape de commit faisait::

    git add MANIFESTE.csv collecte/etat_rapports.json \\
            collecte/a_reteleverser.json a_uploader.txt echecs_upload.txt || true

``echecs_upload.txt`` n'est cree que lorsqu'un upload ECHOUE. Il n'existe donc
pas dans le cas sain. Et ``git add`` sur plusieurs chemins est ATOMIQUE : un
seul chemin absent et il n'indexe RIEN et sort en 128. Le ``|| true`` avale ce
128, ``git commit`` ne trouve rien, le run se termine en succes. Mecanisme
reproduit a part en trois commandes : ``git add A.txt B.txt ABSENT.txt`` sort en
128 et laisse l'index vide.

Autrement dit : plus la collecte se portait bien, plus surement elle perdait son
manifeste. Le correctif vit dans ``collecte.yml`` ; la section 37 de
``moteur/tester_donnees.py`` ferme la famille pour tous les workflows.

CE QUE FAIT CE PROCES-VERBAL
----------------------------
Il remet dans ``MANIFESTE.csv`` les lignes des bulletins que les Releases
portent deja. La source est la liste d'assets de la Release — un cote
INDEPENDANT du depot — et chaque valeur ecrite est verifiee contre elle :

* le motif du nom (``boc_AAAAMMJJ[_N].pdf``, les editions anglaises
  ``boc_eng_*`` exclues) ;
* ``taille_octets`` : la taille declaree par l'API doit egaler le nombre
  d'octets effectivement recus ;
* le contenu doit commencer par ``%PDF-`` ;
* ``sha256`` est calcule sur les octets recus, jamais repris d'ailleurs, et il
  est REFUSE s'il figure deja au manifeste sous une autre url (ce serait un
  doublon de contenu, pas un bulletin neuf).

Il n'ECRASE rien : il n'ajoute que des lignes dont l'url est absente, en fin de
fichier, comme ``collecteur.py`` le fait. L'ancre est verifiee avant toute
ecriture : l'en-tete doit etre exactement celui attendu, et le fichier doit se
terminer par un saut de ligne.

IDEMPOTENCE. ``ATTENDU_A_AJOUTER = 20`` est la mesure du 08/10/2026. Le script
accepte exactement deux realites : 20 lignes a ajouter (jamais applique) ou 0
(deja applique). Toute autre valeur l'arrete sans rien ecrire, parce qu'elle
voudrait dire que la realite a bouge depuis la mesure et qu'un humain doit
relire. Un second passage ne fait rien et le dit.

LA LIMITE, DITE PLUTOT QUE COMBLEE
----------------------------------
Les Releases ne portent que 20 des 48 seances publiees apres le 2026-07-24. Ce
script ne peut donc rattraper que celles-la : les 28 autres n'ont jamais ete
archivees et seule une collecte vers brvm.org les ramenerait. Une case vide vaut
mieux qu'une valeur approchee : on ne devine aucun bulletin absent.

Usage : python3 outils/resynchroniser_manifeste_boc.py [--verifier]
        --verifier : mesure et rend le verdict, sans ecrire une ligne.
"""
import argparse
import csv
import hashlib
import os
import re
import sys
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
MANIFESTE = RACINE / "MANIFESTE.csv"
DEPOT = "armelrosario-sys/brvm-data-pipeline"
BASE_BRVM = "https://www.brvm.org/sites/default/files"

# L'en-tete exact de MANIFESTE.csv : l'ancre de ce script. S'il a change, le
# format a change, et ajouter des lignes a l'aveugle serait une faute.
COLONNES = ["sha256", "type", "periode", "url", "nom_fichier",
            "taille_octets", "date_collecte_utc", "release_tag"]

# Mesure du 08/10/2026 (cycle 23) : assets BOC presents dans les Releases et
# absents de MANIFESTE.csv. Garde d'idempotence : 20 ou 0, rien d'autre.
ATTENDU_A_AJOUTER = 20

MOTIF_BOC = re.compile(r"^boc_(\d{8})(_\d)?\.pdf$")


def session_github():
    s = requests.Session()
    entetes = {"Accept": "application/vnd.github+json"}
    jeton = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    s.headers.update(entetes)
    return s


def lire_manifeste():
    with MANIFESTE.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        entete = lecteur.fieldnames
        lignes = list(lecteur)
    return entete, lignes


def assets_boc(s):
    """Tous les assets BOC des Releases boc-*, cote independant du depot."""
    trouves = []
    page = 1
    while True:
        r = s.get(f"https://api.github.com/repos/{DEPOT}/releases",
                  params={"per_page": 100, "page": page}, timeout=60)
        r.raise_for_status()
        lot = r.json()
        if not lot:
            break
        for rel in lot:
            if not rel["tag_name"].startswith("boc-"):
                continue
            for a in rel["assets"]:
                m = MOTIF_BOC.match(a["name"])
                if not m:
                    continue          # exclut boc_eng_* et tout autre nom
                trouves.append({"tag": rel["tag_name"], "nom": a["name"],
                                "taille": a["size"], "url_api": a["url"],
                                "aaaammjj": m.group(1)})
        page += 1
    return trouves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true",
                    help="mesure seule, aucune ecriture")
    ap.add_argument("--relance", action="store_true",
                    help="leve la seule garde ATTENDU_A_AJOUTER, pour l'usage "
                         "recurrent par .github/workflows/rattrapage_releves.yml. "
                         "Toutes les gardes de CONTENU restent en place : taille "
                         "declaree contre octets recus, %%PDF-, sha256 calcule et "
                         "refuse s'il existe deja, url absente, ancre de l'en-tete, "
                         "relecture apres ecriture. Sans ce drapeau le script est le "
                         "proces-verbal du 08/10/2026 et n'accepte que 20 ou 0.")
    args = ap.parse_args()

    # --- ancre : l'en-tete, et le fichier qui se termine proprement ----------
    entete, lignes = lire_manifeste()
    if entete != COLONNES:
        sys.exit(f"REFUS : en-tete de MANIFESTE.csv inattendu.\n"
                 f"  attendu : {COLONNES}\n  trouve  : {entete}")
    brut = MANIFESTE.read_bytes()
    if not brut.endswith(b"\n"):
        sys.exit("REFUS : MANIFESTE.csv ne se termine pas par un saut de ligne ; "
                 "ajouter des lignes collerait la premiere a la derniere.")

    urls_connues = {r["url"] for r in lignes}
    noms_boc = {r["nom_fichier"] for r in lignes if r["type"] == "boc"}
    sha_connus = {r["sha256"]: r["url"] for r in lignes}

    s = session_github()
    tous = assets_boc(s)
    manquants = sorted((a for a in tous if a["nom"] not in noms_boc),
                       key=lambda a: a["nom"])
    print(f"{len(tous)} asset(s) BOC dans les Releases, "
          f"{len(noms_boc)} declare(s) au manifeste, "
          f"{len(manquants)} absent(s) du manifeste.")
    for a in manquants:
        print(f"  a ajouter : {a['tag']} {a['nom']} ({a['taille']} octets)")

    # --- garde d'idempotence -------------------------------------------------
    if len(manquants) == 0:
        print("Rien a faire : le manifeste declare deja tous les bulletins "
              "archives. Deuxieme passage sans effet, comme attendu.")
        return 0
    if len(manquants) != ATTENDU_A_AJOUTER and not args.relance:
        sys.exit(f"REFUS : {len(manquants)} ligne(s) a ajouter, "
                 f"ATTENDU_A_AJOUTER={ATTENDU_A_AJOUTER}. La realite a bouge "
                 f"depuis la mesure du 08/10/2026 : relire avant d'ecrire, ou "
                 f"passer --relance pour l'usage recurrent.")

    if args.verifier:
        print(f"--verifier : {len(manquants)} ligne(s) manquante(s), "
              f"conforme a la mesure. Rien ecrit.")
        return 0

    # --- telechargement et verification valeur par valeur --------------------
    nouvelles = []
    for a in manquants:
        rep = s.get(a["url_api"],
                    headers={"Accept": "application/octet-stream"}, timeout=120)
        if rep.status_code != 200:
            sys.exit(f"REFUS : {a['nom']} -> HTTP {rep.status_code} ; "
                     f"rien n'a ete ecrit.")
        contenu = rep.content
        if len(contenu) != a["taille"]:
            sys.exit(f"REFUS : {a['nom']} : taille declaree par l'API "
                     f"{a['taille']} octets, recue {len(contenu)} ; "
                     f"rien n'a ete ecrit.")
        if not contenu.startswith(b"%PDF-"):
            sys.exit(f"REFUS : {a['nom']} ne commence pas par %PDF- ; "
                     f"rien n'a ete ecrit.")
        sha = hashlib.sha256(contenu).hexdigest()
        aaaammjj = a["aaaammjj"]
        url = f"{BASE_BRVM}/{a['nom']}"
        if url in urls_connues:
            sys.exit(f"REFUS : l'url {url} est deja au manifeste alors que son "
                     f"nom_fichier n'y est pas ; rien n'a ete ecrit.")
        if sha in sha_connus:
            sys.exit(f"REFUS : le sha256 de {a['nom']} figure deja au manifeste "
                     f"sous {sha_connus[sha]} ; ce n'est pas un bulletin neuf. "
                     f"Rien n'a ete ecrit.")
        sha_connus[sha] = url
        urls_connues.add(url)
        nouvelles.append({
            "sha256": sha,
            "type": "boc",
            "periode": f"{aaaammjj[:4]}-{aaaammjj[4:6]}",
            "url": url,
            "nom_fichier": a["nom"],
            "taille_octets": str(len(contenu)),
            # Date de resynchronisation, pas de collecte : ce script ne collecte
            # rien, il redeclare ce que la Release porte deja.
            "date_collecte_utc": "2026-10-08T00:00:00Z",
            "release_tag": a["tag"],
        })
        print(f"  verifie : {a['nom']} sha256={sha[:12]}... "
              f"{len(contenu)} octets, periode {nouvelles[-1]['periode']}")

    if len(nouvelles) != len(manquants):
        sys.exit(f"REFUS : {len(nouvelles)} ligne(s) verifiee(s) pour "
                 f"{len(manquants)} manquante(s) ; rien n'a ete ecrit.")

    # --- une seule ecriture, en ajout pur ------------------------------------
    with MANIFESTE.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writerows(nouvelles)
        f.flush()
        os.fsync(f.fileno())

    entete2, lignes2 = lire_manifeste()
    if entete2 != COLONNES or len(lignes2) != len(lignes) + len(nouvelles):
        sys.exit(f"REFUS APRES ECRITURE : {len(lignes2)} ligne(s) relues pour "
                 f"{len(lignes) + len(nouvelles)} attendue(s). "
                 f"Annuler par git checkout -- MANIFESTE.csv")
    print(f"{len(nouvelles)} ligne(s) ajoutee(s) a MANIFESTE.csv "
          f"({len(lignes)} -> {len(lignes2)}). Les deux backfills les voient "
          f"desormais.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
