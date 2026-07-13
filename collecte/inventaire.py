#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2a — Inventaire de reconnaissance de brvm.org.
Cartographie les pages listant des PDF (BOC, rapports, avis) AVANT d'écrire
le collecteur complet. Volume minimal, cadence respectueuse (1 req / 2 s).
Sorties : collecte/inventaire.json + collecte/rapport_inventaire.md
"""
import json, re, time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://www.brvm.org"
UA = {"User-Agent": "brvm-data-pipeline/0.1 (inventaire respectueux; "
      "https://github.com/armelrosario-sys/brvm-data-pipeline)"}
DELAI = 2.0
MOTS_CLES = ["bulletin", "boc", "rapport", "avis", "societe", "sociét",
             "cote", "publication", "communiqu", "financier", "etats", "état"]
MAX_PAGES = 15

session = requests.Session()
session.headers.update(UA)

def get(url):
    time.sleep(DELAI)
    try:
        return session.get(url, timeout=30)
    except Exception as e:
        return e

def interne(href):
    if not href:
        return None
    u = urljoin(BASE + "/", href)
    p = urlparse(u)
    if p.netloc and "brvm.org" not in p.netloc:
        return None
    return u.split("#")[0]

resultats = {"date_utc": datetime.now(timezone.utc).isoformat(),
             "base": BASE, "pages": {}, "erreurs": []}

# 0. robots.txt (transparence : on enregistre ce que le site autorise)
r = get(BASE + "/robots.txt")
resultats["robots_txt"] = r.text[:2000] if hasattr(r, "text") else str(r)

# 1. Accueil -> liens de sections candidats
candidats, vus = [], set()
for accueil in ("/fr", "/"):
    r = get(BASE + accueil)
    if hasattr(r, "status_code") and r.ok:
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            u = interne(a["href"])
            if not u or u in vus:
                continue
            texte = (a.get_text(" ", strip=True) or "").lower()
            if any(m in (u.lower() + " " + texte) for m in MOTS_CLES):
                vus.add(u)
                candidats.append({"url": u, "texte": texte[:80]})
        if len(candidats) >= 3:
            break
    else:
        resultats["erreurs"].append(
            f"accueil {accueil}: {getattr(r, 'status_code', r)}")

# 2. Sitemap
r = get(BASE + "/sitemap.xml")
sitemap_urls = []
if hasattr(r, "status_code") and r.ok and "<" in r.text[:300]:
    sitemap_urls = re.findall(r"<loc>(.*?)</loc>", r.text)
resultats["sitemap"] = {
    "disponible": bool(sitemap_urls), "nb_urls": len(sitemap_urls),
    "urls_pertinentes": [u for u in sitemap_urls
                         if any(m in u.lower() for m in MOTS_CLES)][:30]}

# 3. Visite des pages candidates
for c in candidats[:MAX_PAGES]:
    r = get(c["url"])
    if not hasattr(r, "status_code"):
        resultats["pages"][c["url"]] = {"texte_lien": c["texte"],
                                        "erreur": str(r)}
        continue
    info = {"texte_lien": c["texte"], "status": r.status_code}
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")
        pdfs, sections = [], []
        for a in soup.find_all("a", href=True):
            u = interne(a["href"])
            if not u:
                continue
            if u.lower().endswith(".pdf"):
                pdfs.append(u)
            elif any(m in u.lower() for m in MOTS_CLES):
                sections.append(u)
        info["nb_pdf"] = len(pdfs)
        info["echantillon_pdf"] = pdfs[:10]
        info["nb_liens_sections"] = len(set(sections))
        info["echantillon_sections"] = list(dict.fromkeys(sections))[:10]
        info["pagination"] = bool(
            soup.select("[class*=pager], [class*=pagination]"))
    resultats["pages"][c["url"]] = info

# 4. Rapport lisible
L = [f"# Rapport d'inventaire — {resultats['date_utc']}", ""]
L.append(f"Sitemap : {'OUI' if resultats['sitemap']['disponible'] else 'NON'}"
         f" ({resultats['sitemap']['nb_urls']} URLs)")
L.append(f"Sections candidates trouvées : {len(candidats)}"
         f" (visitées : {min(len(candidats), MAX_PAGES)})")
L.append("")
for u, i in resultats["pages"].items():
    L.append(f"## {u}")
    L.append(f"- lien « {i.get('texte_lien', '')} » | statut : "
             f"{i.get('status', i.get('erreur'))} | PDF : {i.get('nb_pdf', 0)}"
             f" | pagination : {i.get('pagination', False)}")
    for p in i.get("echantillon_pdf", []):
        L.append(f"  - {p}")
    L.append("")

with open("collecte/inventaire.json", "w", encoding="utf-8") as f:
    json.dump(resultats, f, ensure_ascii=False, indent=2)
with open("collecte/rapport_inventaire.md", "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print(f"Inventaire terminé : {len(resultats['pages'])} pages visitées.")
