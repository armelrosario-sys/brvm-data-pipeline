#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C37 — rattraper la 48e ligne (BBGC) des seances deja ecrites a 47

Le probleme, en une phrase
--------------------------
Bridge Bank Group CI (``BBGC``) est cotee depuis le 24/09/2026. Jusqu'a la
correction de C32 (07/10/2026), ``collecte/extracteur_boc.py`` portait un
univers de 47 tickers ecrit en dur : chaque bulletin en portait 48 lignes de
cotation, et la 48e etait jetee sans trace. C32 a rouvert l'entree de la serie,
mais les deux collecteurs sautent par construction toute seance deja en base
(``seances_deja_en_base()`` et ``iso in deja_en_base``) : les seances deja
ecrites a 47 lignes resteront a 47 indefiniment si rien ne les reprend nommement.

Ce que ce script a trouve, et qui change la methode de C37
----------------------------------------------------------
C37 posait que les bulletins devaient etre **reteleverses depuis brvm.org**,
donc par un workflow, parce que ``find . -name "*.pdf"`` ne rend rien dans le
depot. C'est vrai du depot, et faux de l'**archive** : la Release ``boc-<annee>``
porte les bulletins, et ``MANIFESTE.csv`` en donne le ``sha256``. Le rattrapage
de toute seance dont le bulletin est archive ne demande donc **aucun acces a
brvm.org** -- seulement l'archive du depot, et la preuve que le PDF lu est bien
celui que le manifeste decrit.

C'est aussi ce qui donne la preuve a deux cotes exigee par la regle 3 du depot
avant d'ecrire dans une serie certifiee :

  * cote 1 -- le ``sha256`` du PDF telecharge egale celui de ``MANIFESTE.csv`` :
    le document lu est le document archive, a l'octet pres ;
  * cote 2 -- la **reextraction reproduit les 47 lignes deja en base a zero
    divergence** : l'extracteur lit ce bulletin-la correctement, donc la 48e
    ligne qu'il en tire n'est pas plus douteuse que les 47 autres.

Si l'un des deux cotes manque, la seance n'est pas ecrite. C'est le sens de la
garde ``attendu`` ci-dessous : elle ne compare pas pour informer, elle compare
pour **refuser**.

Ce que le script ne fait pas
---------------------------
Il n'ecrit **jamais** sur une ligne preexistante, et ne reecrit jamais une
seance entiere : il **ajoute** une ligne, a sa place alphabetique, et verifie
apres ecriture que toutes les autres lignes du fichier sont inchangees octet
pour octet. Une divergence entre les deux extractions est **nommee et refusee**,
jamais ecrasee -- c'est exactement l'objet de C33, et la regle 1 du depot.

Il ne touche pas aux seances dont le bulletin n'est pas archive : celles-la
restent a C37 (via C41, qui porte le trou d'archive) et ce script les reprendra
sans modification le jour ou le manifeste les declarera.

Usage
-----
    python3 outils/reextraction_bbgc_depuis_archive.py              # mesure seule
    python3 outils/reextraction_bbgc_depuis_archive.py --ecrire     # applique
    python3 outils/reextraction_bbgc_depuis_archive.py --cache DIR  # PDF deja la

Relance sans effet : une seance dont la ligne BBGC est deja en base est
declaree ``DEJA APPLIQUEE`` et n'est pas retouchee.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "collecte"))

CSV_QUOTIDIEN = RACINE / "collecte" / "cours_quotidien_boc.csv"
MANIFESTE = RACINE / "MANIFESTE.csv"
ENTETE_ATTENDUE = "ticker,date_bulletin,cours,per,rendement"
TICKER = "BBGC"
# Premiere seance de cotation de BBGC. Avant cette date, 47 lignes est le compte
# juste et une seance a 47 n'a rien a rattraper.
PREMIERE_SEANCE = "2026-09-24"
DEPOT = "armelrosario-sys/brvm-data-pipeline"


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------
def lire_csv_brut():
    """Rend (entete, [lignes brutes], terminateur) -- le texte, pas des objets :
    l'ecriture se fait par insertion dans cette liste, donc aucune autre ligne
    ne peut etre reserialisee differemment de ce qu'elle est aujourd'hui.

    Le terminateur est RELEVE, pas suppose. Mesure du 08/10/2026 : ce fichier
    est en **CRLF** (``csv.DictWriter`` ecrit ``\\r\\n`` par defaut, et c'est lui
    qui l'a ecrit depuis l'origine). Une premiere version de ce script
    reserialisait en ``\\n`` : 90 851 lignes reecrites a l'identique au sens du
    texte, et un diff de tout le fichier. Annule et corrige. Comparer des listes
    de lignes NE VOIT PAS ce defaut -- seule la comparaison des octets le voit,
    d'ou la garde ``octets_inchanges()``.
    """
    brut = CSV_QUOTIDIEN.read_bytes()
    texte = brut.decode("utf-8")
    terminateur = "\r\n" if "\r\n" in texte else "\n"
    assert texte.endswith(terminateur), "le fichier ne finit pas par une fin de ligne"
    lignes = texte[:-len(terminateur)].split(terminateur)
    for i, l in enumerate(lignes):
        assert "\r" not in l and "\n" not in l, (
            f"ligne {i + 1} : fins de ligne melangees dans le fichier -- REFUS")
    entete, corps = lignes[0], lignes[1:]
    assert entete == ENTETE_ATTENDUE, f"entete inattendue : {entete!r}"
    return entete, corps, terminateur


def indexer(corps):
    """(date -> {ticker: (index, champs)}) sur les lignes brutes."""
    par_date = {}
    for i, ligne in enumerate(corps):
        champs = ligne.split(",")
        assert len(champs) == 5, f"ligne {i + 2} : {len(champs)} champs, 5 attendus"
        par_date.setdefault(champs[1], {})[champs[0]] = (i, champs)
    return par_date


def lire_manifeste():
    """nom_fichier -> (sha256, release_tag). Un nom en double est une erreur :
    on ne saurait pas lequel est le bon."""
    index = {}
    with MANIFESTE.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["type"] != "boc":
                continue
            nom = r["nom_fichier"]
            if nom in index:
                assert index[nom] == (r["sha256"], r["release_tag"]), (
                    f"MANIFESTE.csv : {nom} declare deux fois avec deux sha256")
            index[nom] = (r["sha256"], r["release_tag"])
    return index


# --------------------------------------------------------------------------
# Cibles
# --------------------------------------------------------------------------
def cibles(par_date, manifeste):
    """Les seances a rattraper, deduites du fichier lui-meme -- aucune date
    n'est ecrite en dur. Rend (a_faire, deja_faites, sans_archive)."""
    a_faire, deja, sans_archive = [], [], []
    for date in sorted(par_date):
        if date < PREMIERE_SEANCE:
            continue
        if TICKER in par_date[date]:
            deja.append(date)
            continue
        compact = date.replace("-", "")
        trouve = None
        for suffixe in ("_2", "_1", ""):
            nom = f"boc_{compact}{suffixe}.pdf"
            if nom in manifeste:
                trouve = nom
                break
        if trouve:
            a_faire.append((date, trouve, manifeste[trouve]))
        else:
            sans_archive.append(date)
    return a_faire, deja, sans_archive


# --------------------------------------------------------------------------
# Recuperation du bulletin
# --------------------------------------------------------------------------
def _api(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "User-Agent": "brvm-data-pipeline/C37",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def _assets(tag, _cache={}):
    if tag not in _cache:
        d = _api(f"https://api.github.com/repos/{DEPOT}/releases/tags/{tag}")
        _cache[tag] = {a["name"]: a["id"] for a in d.get("assets", [])}
    return _cache[tag]


def recuperer_pdf(nom, sha_attendu, tag, cache_dir):
    """Rend le chemin local du PDF, apres verification du sha256 -- cote 1 de la
    preuve. Un PDF deja dans le cache est accepte seulement si son sha256 est
    bon ; sinon il est retelecharge."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local = cache_dir / nom
    if local.exists() and hashlib.sha256(local.read_bytes()).hexdigest() == sha_attendu:
        return local, "cache"
    ids = _assets(tag)
    if nom not in ids:
        raise RuntimeError(f"{nom} absent des assets de la Release {tag}")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{DEPOT}/releases/assets/{ids[nom]}",
        headers={"Accept": "application/octet-stream",
                 "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "User-Agent": "brvm-data-pipeline/C37"})
    with urllib.request.urlopen(req, timeout=300) as r:
        contenu = r.read()
    sha = hashlib.sha256(contenu).hexdigest()
    if sha != sha_attendu:
        raise RuntimeError(
            f"{nom} : sha256 {sha} != {sha_attendu} du manifeste -- REFUS, "
            "le document telecharge n'est pas celui que le manifeste decrit")
    if not contenu.startswith(b"%PDF"):
        raise RuntimeError(f"{nom} : ce n'est pas un PDF")
    local.write_bytes(contenu)
    return local, "telecharge"


# --------------------------------------------------------------------------
# Extraction et garde `attendu`
# --------------------------------------------------------------------------
def _nombre(s):
    return None if s in (None, "") else float(s)


def _egal(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < 1e-9


def extraire(chemin):
    """Rend {ticker: (cours, per, rendement_fraction)}.

    Le rendement du BOC est un POURCENTAGE ; la serie quotidienne porte une
    FRACTION depuis le 2026-07-17 (``collecte/collecte_boc_quotidien.py``,
    ``r.get("rendement") / 100``), et C21 a normalise tout l'historique. Les
    seances de ce chantier sont toutes posterieures : on divise par cent, comme
    le collecteur. Comparer sans cette division rend 43 fausses divergences par
    seance -- mesure du 08/10/2026.
    """
    from extracteur_boc import extraire_boc  # pdfplumber : hors requirements.txt
    _, lignes = extraire_boc(str(chemin))
    sortie = {}
    for l in lignes:
        r = l.get("rendement")
        sortie[l["ticker"]] = (l.get("cours"), l.get("per"),
                               None if r is None else r / 100)
    return sortie


def confronter(date, en_base, extrait):
    """Garde ``attendu`` -- cote 2 de la preuve. Rend (ok, motifs, ligne_bbgc)."""
    motifs = []
    attendus = {t for t in en_base}
    obtenus = set(extrait)
    if attendus - obtenus:
        motifs.append(f"en base et absents de l'extraction : {sorted(attendus - obtenus)}")
    inattendus = obtenus - attendus - {TICKER}
    if inattendus:
        motifs.append(f"extraits, inconnus de la base, et autres que {TICKER} : {sorted(inattendus)}")
    if TICKER not in extrait:
        motifs.append(f"{TICKER} absent de l'extraction")
    divergences = []
    for t in sorted(attendus & obtenus):
        _, champs = en_base[t]
        b = (_nombre(champs[2]), _nombre(champs[3]), _nombre(champs[4]))
        e = extrait[t]
        if not all(_egal(x, y) for x, y in zip(b, e)):
            divergences.append((t, b, e))
    if divergences:
        motifs.append(f"{len(divergences)} divergence(s) sur les lignes preexistantes "
                      f"-- REFUS, elles ne sont jamais ecrasees (C33) : {divergences[:5]}")
    if motifs:
        return False, motifs, None
    cours, per, rend = extrait[TICKER]
    ligne = ",".join([
        TICKER, date,
        "" if cours is None else str(cours),
        "" if per is None else str(per),
        "" if rend is None else str(rend),
    ])
    return True, [], ligne


# --------------------------------------------------------------------------
# Ecriture
# --------------------------------------------------------------------------
def inserer(corps, par_date, date, ligne):
    """Insere la ligne a sa place alphabetique dans le bloc de la seance.

    Ancre exacte, unicite asseree : le bloc d'une seance est contigu dans le
    fichier (ecrit seance par seance depuis l'origine). On refuse d'ecrire si ce
    n'est pas le cas, plutot que d'inserer au hasard.
    """
    indices = sorted(i for i, _ in par_date[date].values())
    assert indices == list(range(indices[0], indices[-1] + 1)), (
        f"{date} : le bloc de la seance n'est pas contigu ({indices[0]}..{indices[-1]}, "
        f"{len(indices)} lignes) -- REFUS")
    tickers = [par_date[date][t][1][0] for t in sorted(par_date[date],
                                                        key=lambda t: par_date[date][t][0])]
    assert tickers == sorted(tickers), f"{date} : bloc non trie par ticker -- REFUS"
    position = indices[0]
    while position <= indices[-1] and corps[position].split(",")[0] < TICKER:
        position += 1
    return corps[:position] + [ligne] + corps[position:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true",
                    help="applique ; sans ce drapeau le script mesure et n'ecrit rien")
    ap.add_argument("--cache", default=None,
                    help="repertoire des PDF (telechargement evite si le sha256 est bon)")
    args = ap.parse_args()
    cache = Path(args.cache) if args.cache else RACINE / ".cache_boc_c37"

    octets_avant = CSV_QUOTIDIEN.read_bytes()
    entete, corps, terminateur = lire_csv_brut()
    sha_avant = hashlib.sha256(octets_avant).hexdigest()
    n_avant = len(corps)
    par_date = indexer(corps)
    manifeste = lire_manifeste()
    a_faire, deja, sans_archive = cibles(par_date, manifeste)

    print(f"{CSV_QUOTIDIEN.name} : {n_avant} lignes, sha256 {sha_avant[:16]}")
    print(f"seances depuis {PREMIERE_SEANCE} portant deja {TICKER} : {len(deja)} {deja}")
    print(f"seances a rattraper, bulletin archive          : {len(a_faire)} "
          f"{[d for d, _, _ in a_faire]}")
    print(f"seances a rattraper, bulletin NON archive      : {len(sans_archive)} "
          f"{sans_archive}  (hors de portee de ce script : voir C41)")

    if not a_faire:
        print("\nmigration DEJA APPLIQUEE pour tout ce que l'archive permet : rien a faire.")
        return 0

    retenues, refusees = [], []
    for date, nom, (sha, tag) in a_faire:
        chemin, origine = recuperer_pdf(nom, sha, tag, cache)
        print(f"\n-- {date} : {nom} ({origine}), sha256 verifie contre le manifeste")
        extrait = extraire(chemin)
        ok, motifs, ligne = confronter(date, par_date[date], extrait)
        n_pre = len(par_date[date])
        if ok:
            print(f"   garde attendu : {n_pre} lignes preexistantes reproduites, "
                  f"0 divergence -> ligne ajoutee : {ligne}")
            retenues.append((date, ligne))
        else:
            print(f"   REFUS ({n_pre} lignes preexistantes) :")
            for m in motifs:
                print(f"     - {m}")
            refusees.append((date, motifs))

    if not args.ecrire:
        print(f"\nMESURE SEULE : {len(retenues)} seance(s) ecrivable(s), "
              f"{len(refusees)} refusee(s). Rien n'a ete ecrit. "
              "Relancer avec --ecrire pour appliquer.")
        return 0

    if not retenues:
        print("\nAucune seance ne passe la garde : rien n'est ecrit.")
        return 1

    nouveau = corps
    for date, ligne in retenues:
        nouveau = inserer(nouveau, indexer(nouveau), date, ligne)

    # Garde : seules les lignes retenues sont nouvelles, aucune autre ne change.
    ajoutees = sorted(set(nouveau) - set(corps))
    assert len(nouveau) == n_avant + len(retenues), (
        f"{len(nouveau)} lignes apres, {n_avant + len(retenues)} attendues -- REFUS")
    assert sorted(a for _, a in retenues) == ajoutees, (
        f"lignes ajoutees inattendues : {ajoutees} -- REFUS")
    ajoutes = {a for _, a in retenues}
    assert corps == [l for l in nouveau if l not in ajoutes], (
        "une ligne preexistante a change -- REFUS")

    # Garde a l'OCTET : le fichier d'apres est le fichier d'avant plus les
    # lignes ajoutees, et rien d'autre -- ni fin de ligne, ni encodage, ni
    # espace. C'est la garde qui manquait a la premiere version.
    texte = entete + terminateur + terminateur.join(nouveau) + terminateur
    octets_apres = texte.encode("utf-8")
    ajout = "".join(a + terminateur for _, a in retenues).encode("utf-8")
    assert len(octets_apres) == len(octets_avant) + len(ajout), (
        f"{len(octets_apres)} octets apres, {len(octets_avant) + len(ajout)} attendus -- REFUS")
    temoin = octets_apres
    for _, a in retenues:
        morceau = (a + terminateur).encode("utf-8")
        assert temoin.count(morceau) == 1, f"ligne ajoutee non unique : {a} -- REFUS"
        temoin = temoin.replace(morceau, b"", 1)
    assert temoin == octets_avant, (
        "les octets preexistants ne sont pas rendus a l'identique -- REFUS")

    CSV_QUOTIDIEN.write_bytes(octets_apres)

    # Relecture apres ecriture.
    entete2, corps2, terminateur2 = lire_csv_brut()
    sha_apres = hashlib.sha256(CSV_QUOTIDIEN.read_bytes()).hexdigest()
    assert entete2 == entete and corps2 == nouveau and terminateur2 == terminateur, (
        "relecture differente de l'ecrit -- REFUS")
    par_date2 = indexer(corps2)
    for date, _ in retenues:
        assert TICKER in par_date2[date], f"{date} : {TICKER} absent apres ecriture"
        assert len(par_date2[date]) == 48, f"{date} : {len(par_date2[date])} lignes, 48 attendues"

    print(f"\nECRIT : {len(retenues)} seance(s), {len(retenues)} ligne(s) ajoutee(s). "
          f"{n_avant} -> {len(corps2)} lignes. "
          f"sha256 {sha_avant[:16]} -> {sha_apres[:16]}. "
          f"Relecture conforme, 48 lignes sur chaque seance traitee.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
