#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/charger_cours_quotidien.py — (28/07/2026).

Pont manquant identifie le 28/07/2026 : la table cours_quotidien_boc existe
dans schema.sql depuis le 18/07/2026, concue precisement pour accumuler une
ligne par jour de cotation (contrairement a cours_mensuels qui n'en garde
qu'une par mois) -- mais rien ne l'alimentait depuis collecte/cours_quotidien_boc.csv
(1886 jours au 28/07/2026, Piste B). Ce script comble ce pont, sur le meme
modele que charger_cours.py (cours_mensuels).

INSERT OR REPLACE : idempotent, peut tourner a chaque publication sans
creer de doublons (cle primaire ticker+date_bulletin).

Usage : python3 collecte/charger_cours_quotidien.py [chemin_db]
"""
import csv
import sqlite3
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
CSV_SOURCE = str(_BASE / "cours_quotidien_boc.csv")
DB = sys.argv[1] if len(sys.argv) > 1 else str(_BASE.parent / "moteur" / "brvm.db")



def _rendement_normalise(valeur):
    """Ramene tous les rendements a la meme unite : la FRACTION (0,0493 = 4,93 %).

    Correctif du 12/09/2026. Le fichier cours_quotidien_boc.csv melange DEUX
    unites selon l'origine de la ligne :
      - extraction historique des bulletins : en POURCENTAGE (4,71 pour 4,71 %)
      - collecte quotidienne P11 : en FRACTION (0,0493 pour 4,93 %)
    Consequence mesuree : SIVC ressortait a 2 681 % de rendement, FTSC a 81 %.
    Le moteur ne lisant que la derniere valeur, les profils du jour restaient
    justes, mais toute lecture historique du rendement etait fausse d'un facteur
    cent — et la comparaison au taux souverain devenait absurde.

    Regle de discrimination, calee sur la distribution reelle : aucun rendement
    exprime en FRACTION ne depasse 1,5 (150 % du cours en dividende). Une valeur
    superieure a 1,5 est donc necessairement un pourcentage et se divise par
    cent ; en dessous, c'est deja une fraction.
    Un premier essai avec un seuil a 0,30 ecrasait a tort FTSC, dont le
    rendement de 81 % est REEL (dividende exceptionnel de cession) : 0,8144
    aurait ete divise et serait devenu 0,81 %. Le seuil a 1,5 traite
    correctement les trois familles observees :
       4,71  -> 0,0471 (ancienne extraction, en %)
      26,81  -> 0,2681 (SIVC, dividende exceptionnel en %)
       0,8144 -> inchange (FTSC, deja en fraction)
       0,0493 -> inchange (collecte quotidienne)
    Les rendements superieurs a 15 % restent de toute facon ecartes en aval
    comme non recurrents (regle Q0.3 du modele de fiche).
    """
    if valeur in (None, ""):
        return None
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    if v > 1.5:           # necessairement exprime en pourcentage
        v = v / 100.0
    return v if 0 <= v <= 1.5 else None


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n = 0
    tickers, dates = set(), set()
    with open(CSV_SOURCE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("date_bulletin") or not r.get("ticker"):
                continue
            cur.execute(
                "INSERT OR REPLACE INTO cours_quotidien_boc "
                "(ticker, date_bulletin, cours, per, rendement) "
                "VALUES (?,?,?,?,?)",
                (r["ticker"], r["date_bulletin"],
                 float(r["cours"]) if r.get("cours") else None,
                 float(r["per"]) if r.get("per") else None,
                 # BUG CORRIGE le 10/09/2026 : la division par 100 etait de trop.
                 # cours_quotidien_boc.csv stocke deja le rendement en FRACTION
                 # (0,0493 pour 4,93 %), comme cours_mensuels. La division le
                 # ramenait a 0,000493, soit un rendement cent fois trop petit.
                 # Consequences mesurees, toutes silencieuses :
                 #   - le profil RENDEMENT devenait INATTEIGNABLE (seuil 4,8 %) :
                 #     zero titre classe, contre un auparavant ;
                 #   - le payout implicite (rendement x PER) tombait sous 1 % pour
                 #     26 titres, donc la condition "payout <= 100 %" passait
                 #     TOUJOURS : des titres qui distribuent plus que leur benefice
                 #     n'etaient plus ecartes. SOLIBRA est ainsi passe de AUCUN
                 #     PROFIL a VALUE sans qu'aucun fait economique n'ait change.
                 # Detecte par l'utilisateur sur le graphique, pas par les tests :
                 # d'ou le controle d'echelle ajoute a tester_donnees.py.
                 _rendement_normalise(r.get("rendement"))))
            n += 1
            tickers.add(r["ticker"])
            dates.add(r["date_bulletin"])
    conn.commit()
    print(f"{n} lignes inserees/mises a jour dans cours_quotidien_boc "
          f"({len(tickers)} tickers, {len(dates)} jours, "
          f"{min(dates) if dates else '?'} -> {max(dates) if dates else '?'}).")
    conn.close()


if __name__ == "__main__":
    main()
