#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2b — Collecteur sélectif brvm.org (v0.3, incrémental, reprise automatique).
Corrections v0.3 : (1) BOC parcourus du plus récent au plus ancien
(fraîcheur d'abord, canari fiable) ; (2) mois introuvables mémorisés
dans l'état pour ne plus gaspiller le budget, avec passe de rattrapage
élargie quand tout le reste est couvert.
Respect strict du Crawl-delay: 10 du robots.txt du site.
"""
import csv, hashlib, json, os, re, sys, time
from datetime import datetime, timezone, date, timedelta
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://www.brvm.org"
UA = {"User-Agent": "brvm-data-pipeline/0.3 (collecte selective respectueuse; "
      "https://github.com/armelrosario-sys/brvm-data-pipeline)"}
DELAI = 10.0
BUDGET_REQUETES = 220
BUDGET_RAPPORTS_MIN = 80  # (11/07/2026) : reserve un plancher a la collecte des rapports,
# meme si la collecte BOC a deja beaucoup consomme sur ce run — corrige la cause racine
# du gap ETIT (jamais visite en plusieurs mois de runs, cf. audit du 11/07/2026)
DEBUT_BOC = (2018, 1)
MANIFESTE = "MANIFESTE.csv"
ETAT = "collecte/etat_rapports.json"
COLONNES = ["sha256", "type", "periode", "url", "nom_fichier",
            "taille_octets", "date_collecte_utc", "release_tag"]
SECTIONS_EXCLUES = ("/fr/rapports-societes-cotees", "/fr/bulletins-officiels",
                    "/fr/mediacentre", "/fr/emetteurs", "/fr/intervenants",
                    "/fr/newsletter", "/fr/comment-etre")

session = requests.Session(); session.headers.update(UA)
requetes_faites = 0

def get(url, binaire=False):
    global requetes_faites
    if requetes_faites >= BUDGET_REQUETES:
        return None
    time.sleep(DELAI); requetes_faites += 1
    try:
        r = session.get(url, timeout=60)
        if r.status_code != 200:
            print(f"[diagnostic] {url} -> HTTP {r.status_code} "
                  f"(len={len(r.content)})", file=sys.stderr)
            return None
        return r.content if binaire else r.text
    except Exception as e:
        print(f"[diagnostic] {url} -> EXCEPTION {type(e).__name__}: {e}",
              file=sys.stderr)
        return None

def charger_manifeste():
    lignes = {}
    if os.path.exists(MANIFESTE):
        with open(MANIFESTE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lignes[row["url"]] = row
    return lignes

def ajouter_manifeste(rows):
    existe = os.path.exists(MANIFESTE)
    with open(MANIFESTE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        if not existe:
            w.writeheader()
        for r in rows:
            w.writerow(r)

def sauver_pdf(contenu, tag, nom):
    os.makedirs(f"data/{tag}", exist_ok=True)
    chemin = f"data/{tag}/{nom}"
    with open(chemin, "wb") as f:
        f.write(contenu)
    with open("a_uploader.txt", "a", encoding="utf-8") as f:
        f.write(f"{tag}\t{chemin}\n")

def collecter_fichier(url, type_, periode, tag, nom=None):
    contenu = get(url, binaire=True)
    if contenu is None or not contenu.startswith(b"%PDF"):
        return None
    sha = hashlib.sha256(contenu).hexdigest()
    nom = nom or os.path.basename(urlparse(url).path)
    sauver_pdf(contenu, tag, nom)
    return {"sha256": sha, "type": type_, "periode": periode, "url": url,
            "nom_fichier": nom, "taille_octets": len(contenu),
            "date_collecte_utc": datetime.now(timezone.utc).isoformat(),
            "release_tag": tag}

# ---------------- CIBLE 1 : BOC de fin de mois ----------------
def mois_cibles_descendants():
    y, m = DEBUT_BOC
    auj = date.today()
    liste = []
    while (y, m) <= (auj.year, auj.month):
        liste.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return list(reversed(liste))          # du plus récent au plus ancien

def jours_ouvres_fin_de_mois(y, m, n=4):
    if m == 12:
        d = date(y, 12, 31)
    else:
        d = date(y, m + 1, 1) - timedelta(days=1)
    if (y, m) == (date.today().year, date.today().month):
        d = min(d, date.today() - timedelta(days=1))
    jours = []
    while len(jours) < n and d.month == m:
        if d.weekday() < 5:
            jours.append(d)
        d -= timedelta(days=1)
    return jours

def tenter_mois(y, m, nouveaux, n_jours=4, suffixes=("_2", "_1", "")):
    """Retourne (trouve, tentatives_completes)."""
    periode = f"{y}-{m:02d}"
    for d in jours_ouvres_fin_de_mois(y, m, n_jours):
        for suf in suffixes:
            if requetes_faites >= BUDGET_REQUETES:
                return False, False
            url = f"{BASE}/sites/default/files/boc_{d:%Y%m%d}{suf}.pdf"
            row = collecter_fichier(url, "boc", periode, f"boc-{y}")
            if row:
                nouveaux.append(row)
                return True, True
    return False, True

def collecter_boc(manifeste, nouveaux, etat):
    deja = {r["periode"] for r in manifeste.values() if r["type"] == "boc"}
    epuises = set(etat.setdefault("boc_epuises", []))
    restants = []
    for y, m in mois_cibles_descendants():
        periode = f"{y}-{m:02d}"
        if periode in deja:
            continue
        if periode in epuises:
            restants.append((y, m))
            continue
        if requetes_faites >= BUDGET_REQUETES - BUDGET_RAPPORTS_MIN:
            return  # (11/07/2026) reserve le plancher a collecter_rapports
        trouve, complet = tenter_mois(y, m, nouveaux)
        if trouve:
            deja.add(periode)
        elif complet:
            epuises.add(periode)
    # Passe de rattrapage élargie sur les mois épuisés (6 jours, 4 suffixes)
    for y, m in restants:
        if requetes_faites >= BUDGET_REQUETES - BUDGET_RAPPORTS_MIN:
            break
        trouve, complet = tenter_mois(y, m, nouveaux, n_jours=6,
                                      suffixes=("_2", "_1", "_3", ""))
        if trouve and f"{y}-{m:02d}" in epuises:
            epuises.discard(f"{y}-{m:02d}")
    etat["boc_epuises"] = sorted(epuises)

# ---------------- CIBLE 2 : rapports des sociétés cotées ----------------
def charger_etat():
    if os.path.exists(ETAT):
        with open(ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {"listing_page_suivante": 0, "details_visites": [],
            "details_a_visiter": [], "boc_epuises": []}

def interne_fr(href, page_courante):
    u = urljoin(page_courante, href).split("#")[0]
    p = urlparse(u)
    if "brvm.org" not in p.netloc or not p.path.startswith("/fr/"):
        return None
    return u

def collecter_rapports(manifeste, nouveaux, etat):
    while requetes_faites < BUDGET_REQUETES - 2:
        # Reapprovisionner si la file est courte
        while len(etat["details_a_visiter"]) < 10 and requetes_faites < BUDGET_REQUETES:
            n = etat["listing_page_suivante"]
            html = get(f"{BASE}/fr/rapports-societes-cotees?page={n}")
            if html is None:
                break   # cette tentative de reapprovisionnement echoue,
                        # mais on continue avec ce qui est deja en file
            soup = BeautifulSoup(html, "html.parser")
            ajouts = 0
            for a in soup.find_all("a", href=True):
                u = interne_fr(a["href"], f"{BASE}/fr/rapports-societes-cotees")
                if (not u or "?" in u or any(s in u for s in SECTIONS_EXCLUES)
                        or len(urlparse(u).path) < 20):
                    continue
                if u not in etat["details_visites"] and u not in etat["details_a_visiter"]:
                    etat["details_a_visiter"].append(u); ajouts += 1
            etat["listing_page_suivante"] = n + 1
            if ajouts == 0:
                etat["listing_page_suivante"] = 0   # listing termine : on reboucle au debut
                break
        # Visiter une page de la file
        if not etat["details_a_visiter"]:
            break
        page = etat["details_a_visiter"].pop(0)
        html = get(page)
        etat["details_visites"].append(page)
        if html is None:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            u = urljoin(page, a["href"]).split("#")[0]
            if not u.lower().endswith(".pdf") or u in manifeste:
                continue
            annee = (re.search(r"(20[12]\d)", os.path.basename(u)) or
                     re.search(r"(20[12]\d)", page))
            periode = annee.group(1) if annee else "divers"
            sha_nom = hashlib.sha256(u.encode()).hexdigest()[:8]
            nom = f"{sha_nom}_{os.path.basename(urlparse(u).path)}"
            row = collecter_fichier(u, "rapport", periode, f"rapports-{periode}", nom)
            if row:
                nouveaux.append(row); manifeste[u] = row
        # (11/07/2026) CORRECTION BUG CONFIRME : chaque page societe est elle-meme
        # paginee (ex. ETIT avait 6 pages de documents, jamais visitees au-dela
        # de la 1ere — cause racine du gap ETIT, audit du 11/07/2026). Suit
        # desormais le lien "page suivante" DE LA MEME societe (meme chemin de
        # base avant "?page="), en file separee prioritaire.
        base_page = page.split("?")[0]
        for a in soup.find_all("a", href=True):
            u_pag = urljoin(page, a["href"]).split("#")[0]
            if (u_pag.startswith(base_page + "?page=")
                    and u_pag not in etat["details_visites"]
                    and u_pag not in etat["details_a_visiter"]):
                etat["details_a_visiter"].insert(0, u_pag)  # priorite : finir cette societe

# ---------------- ORCHESTRATION + CANARI ----------------
def main():
    manifeste = charger_manifeste()
    etat = charger_etat()
    nouveaux = []
    collecter_boc(manifeste, nouveaux, etat)
    collecter_rapports(manifeste, nouveaux, etat)
    if nouveaux:
        ajouter_manifeste(nouveaux)
    os.makedirs("collecte", exist_ok=True)
    with open(ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)
    print(f"Run terminé : {len(nouveaux)} nouveau(x) fichier(s), "
          f"{requetes_faites} requêtes.")
    auj = date.today()
    prec = auj.replace(day=1) - timedelta(days=1)
    periode_attendue = f"{prec.year}-{prec.month:02d}"
    tout = charger_manifeste()
    if auj.day > 7 and not any(r["type"] == "boc" and
                               r["periode"] == periode_attendue
                               for r in tout.values()):
        print(f"CANARI ROUGE : aucun BOC pour {periode_attendue} — "
              f"structure du site à revérifier.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
