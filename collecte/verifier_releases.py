#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verification post-publication : compare le manifeste aux assets reellement
presents sur chaque Release GitHub. Tout ecart -> marque A_RETELEVERSER dans
un fichier separe (jamais de silence, jamais de correction automatique
du manifeste lui-meme, qui reste un journal append-only)."""
import csv, json, subprocess, sys
from collections import defaultdict

MANIFESTE = "MANIFESTE.csv"
SORTIE = "collecte/a_reteleverser.json"

def assets_du_tag(tag):
    r = subprocess.run(
        ["gh", "release", "view", tag, "--json", "assets",
         "-q", ".assets[].name"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None  # release elle-meme introuvable
    return set(r.stdout.strip().split("\n")) if r.stdout.strip() else set()

def main():
    rows = list(csv.DictReader(open(MANIFESTE, encoding="utf-8")))
    par_tag = defaultdict(list)
    for row in rows:
        par_tag[row["release_tag"]].append(row)

    manquants = []
    for tag, lignes in par_tag.items():
        presents = assets_du_tag(tag)
        if presents is None:
            for l in lignes:
               manquants.append({"tag": tag, "fichier": l["nom_fichier"],
                                  "url": l["url"], "sha256_attendu": l["sha256"],
                                  "raison": "asset absent"})
            continue
        for l in lignes:
            if l["nom_fichier"] not in presents:
                manquants.append({"tag": tag, "fichier": l["nom_fichier"],
                                  "url": l["url"], "sha256_attendu": l["sha256"],
                                  "raison": "asset absent"})

    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(manquants, f, ensure_ascii=False, indent=2)

    print(f"Verification terminee : {len(rows)} lignes de manifeste, "
          f"{len(manquants)} fichier(s) a reteleverser.")
    if manquants:
        print("::warning::" + f"{len(manquants)} fichier(s) manquant(s) "
              "dans les Releases malgre leur presence au manifeste — "
              "voir collecte/a_reteleverser.json")
        for m in manquants[:10]:
            print(f"  - {m['fichier']} (tag {m['tag']}, {m['raison']})")

if __name__ == "__main__":
    main()
