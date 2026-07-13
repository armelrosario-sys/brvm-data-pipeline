#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reparation : retelecharge depuis brvm.org les fichiers listes comme
manquants dans collecte/a_reteleverser.json, verifie leur integrite
(SHA-256 inchange depuis la premiere collecte), et les remet en file
pour republication (meme mecanisme que collecteur.py)."""
import hashlib, json, os, sys, time
import requests

BASE_UA = {"User-Agent": "brvm-data-pipeline/0.1 (reparation respectueuse; "
           "https://github.com/armelrosario-sys/brvm-data-pipeline)"}
DELAI = 10.0
BUDGET_REQUETES = 220
LISTE = "collecte/a_reteleverser.json"
RESTANTS = "collecte/a_reteleverser.json"   # on reecrit la meme liste, allegee
ANOMALIES = "collecte/anomalies_integrite.json"

session = requests.Session(); session.headers.update(BASE_UA)

def main():
    if not os.path.exists(LISTE):
        print("Rien a reparer : pas de fichier a_reteleverser.json")
        return
    items = json.load(open(LISTE, encoding="utf-8"))
    print(f"{len(items)} fichier(s) a reparer.")
    restants, anomalies, requetes = [], [], 0

    for item in items:
        if requetes >= BUDGET_REQUETES:
            restants.append(item)
            continue
        time.sleep(DELAI); requetes += 1
        try:
            r = session.get(item["url"], timeout=60)
        except Exception as e:
            print(f"[reparation] {item['fichier']} -> EXCEPTION {e}",
                  file=sys.stderr)
            restants.append(item)
            continue
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            print(f"[reparation] {item['fichier']} -> HTTP "
                  f"{r.status_code} ou non-PDF", file=sys.stderr)
            restants.append(item)
            continue
        sha = hashlib.sha256(r.content).hexdigest()
        sha_attendu = item.get("sha256_attendu")
        if sha_attendu and sha != sha_attendu:
            anomalies.append({**item, "sha256_retelecharge": sha,
                              "constat": "document different de la collecte initiale"})
        tag = item["tag"]
        os.makedirs(f"data/{tag}", exist_ok=True)
        chemin = f"data/{tag}/{item['fichier']}"
        with open(chemin, "wb") as f:
            f.write(r.content)
        with open("a_uploader.txt", "a", encoding="utf-8") as f:
            f.write(f"{tag}\t{chemin}\n")
        print(f"[reparation] OK : {item['fichier']}")

    json.dump(restants, open(RESTANTS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    if anomalies:
        anciennes = json.load(open(ANOMALIES, encoding="utf-8")) \
            if os.path.exists(ANOMALIES) else []
        json.dump(anciennes + anomalies, open(ANOMALIES, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"Termine : {len(items) - len(restants)} repare(s), "
          f"{len(restants)} restant(s), {len(anomalies)} anomalie(s) d'integrite.")

if __name__ == "__main__":
    main()
