#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P8 — Liquidite du jour (12/07/2026). Remplace la reconstruction statistique
sur 8 ans (abandonnee : trop complexe, pas ce qui etait demande) par une
lecture DIRECTE de la page BRVM qui publie deja le volume du jour pour les
47 titres — https://www.brvm.org/fr/cours-actions/0, mise a jour a chaque
cloture. Zero calcul, zero PDF, zero OCR : on lit ce que BRVM affiche.

A lancer une fois par jour de cotation, apres la cloture officielle (~15h00
UTC + delai de publication), jamais a l'ouverture (aucun volume significatif
disponible a ce moment). Respecte le meme Crawl-delay que collecteur.py.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.brvm.org"
UA = {"User-Agent": "brvm-data-pipeline/0.1 (liquidite quotidienne; "
      "https://github.com/armelrosario-sys/brvm-data-pipeline)"}
_BASE = Path(__file__).resolve().parent
SORTIE = _BASE / "liquidite_jour.json"


def to_nombre(s):
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def recuperer_liquidite_jour():
    resp = requests.get(f"{BASE}/fr/cours-actions/0", headers=UA, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Date de mise a jour affichee par BRVM elle-meme (pas la date du jour ou
    # tourne ce script — peut differer un jour non-ouvre)
    maj_texte = soup.find(string=re.compile("Dernière mise à jour"))
    date_maj = maj_texte.strip() if maj_texte else None

    resultats = {}
    table = soup.find("table")
    if table is None:
        raise RuntimeError("Table des cours introuvable sur la page — structure du site a peut-etre change")

    for ligne in table.find_all("tr")[1:]:  # saute l'entete
        cellules = [c.get_text(strip=True) for c in ligne.find_all("td")]
        if len(cellules) < 6:
            continue
        symbole = cellules[0]
        volume = to_nombre(cellules[2])
        cours_cloture = to_nombre(cellules[5])
        if volume is None or cours_cloture is None:
            continue
        resultats[symbole] = {
            "volume_jour": volume,
            "cours_cloture": cours_cloture,
            "valeur_echangee_jour": round(volume * cours_cloture, 2),
            "date_maj_brvm": date_maj,
            "collecte_le": datetime.now(timezone.utc).isoformat(),
        }
    return resultats


def main():
    resultats = recuperer_liquidite_jour()
    json.dump(resultats, open(SORTIE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(resultats)} titres — liquidite du jour ecrite dans {SORTIE}")
    if resultats:
        exemple = next(iter(resultats.items()))
        print(f"Exemple : {exemple[0]} -> {exemple[1]}")


if __name__ == "__main__":
    main()
