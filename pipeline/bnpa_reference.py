#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BNPA de clôture d'exercice, figé une fois par an.

    python bnpa_reference.py                    # 31 décembre de l'année précédente
    python bnpa_reference.py --annee 2025       # une année précise
    python bnpa_reference.py --pdf chemin.pdf   # depuis un bulletin déjà téléchargé

Produit donnees/bnpa_reference.json : pour chaque symbole, le cours de clôture,
le PER et le BNPA qui s'en déduit, lus dans le dernier Bulletin Officiel de la
Cote de l'année.

Pourquoi ce bulletin-là. Le PER publié au 31 décembre se rapporte au dernier
exercice clos et publié à cette date, c'est-à-dire l'exercice précédent, tandis
que le PER du jour se rapporte à l'exercice en cours de publication. Le rapport
des deux BNPA donne donc la progression du bénéfice par action d'un exercice à
l'autre — par la même arithmétique, la même source et le même extracteur que le
BNPA courant, ce qui évite d'introduire une seconde méthode qu'il faudrait
réconcilier avec la première.

Ce fichier ne se recalcule pas chaque jour : une fois écrit, il vaut pour toute
l'année. Le relancer est sans effet de bord, il réécrit le même contenu.

Dépendances : les mêmes que collecte_boc.py, dont il réutilise l'extracteur.
"""
import argparse, json, os, sys, tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collecte_boc import (DOSSIER, PAGE_LISTE, entete, lignes_actions, pdf_si_present,
                          session_http, texte_pdf, SUFFIXES, URL)

SORTIE = os.path.join(DOSSIER, "bnpa_reference.json")
# Le 31 décembre n'est pas toujours coté : jour férié, week-end, fermeture
# exceptionnelle. On remonte alors vers le dernier jour de bourse de l'année.
RECUL_MAX = 10


def session_amorcee():
    """Session HTTP ayant déjà obtenu son cookie auprès du site.

    Le pare-feu applicatif de brvm.org refuse en 403 un GET isolé sur un PDF, même
    avec un en-tête d'agent correct : il attend le cookie que pose une page
    ordinaire. La collecte quotidienne ne s'en aperçoit pas, parce qu'elle lit la
    page des publications avant de demander le fichier. Ici, où l'adresse du
    bulletin se déduit de la date, cette visite n'a aucune utilité pour trouver
    l'URL — elle reste pourtant nécessaire pour être servi.
    """
    s = session_http()
    try:
        r = s.get(PAGE_LISTE, timeout=45)
        print(f"  amorçage de session : {PAGE_LISTE} -> {r.status_code}, "
              f"{len(s.cookies)} cookie(s)")
    except Exception as e:                      # noqa: BLE001 — l'échec n'est pas bloquant
        print(f"  page d'accueil injoignable ({type(e).__name__}) — on tente quand même")
    return s


def essayer(s, url):
    """Télécharge le bulletin, en disant ce que le serveur a répondu.

    Un échec muet se diagnostique mal : trois tentatives silencieuses et dix jours
    de recul produisent le même message qu'un changement d'adresse, qu'un refus du
    pare-feu ou qu'une coupure réseau. Le code de réponse les sépare d'emblée.
    """
    try:
        r = s.get(url, timeout=45)
    except Exception as e:                      # noqa: BLE001
        print(f"    {url} -> échec réseau ({type(e).__name__})")
        return None
    if r.status_code != 200:
        print(f"    {url} -> {r.status_code}")
        return None
    if r.content[:4] != b"%PDF":
        print(f"    {url} -> 200 mais ce n'est pas un PDF ({len(r.content)} octets)")
        return None
    return r.content


def dernier_bulletin_de_lannee(annee):
    """Contenu du dernier bulletin publié en décembre de cette année-là."""
    s = session_amorcee()
    jour = date(annee, 12, 31)
    essais = []
    for _ in range(RECUL_MAX):
        if jour.weekday() < 5:
            for n in SUFFIXES:
                u = URL.format(aaaammjj=jour.strftime("%Y%m%d"), n=n)
                contenu = essayer(s, u)
                if contenu:
                    print(f"Bulletin de clôture {annee} : {u} "
                          f"({len(contenu):,} octets)".replace(",", " "))
                    return contenu
                essais.append(u)
        else:
            print(f"    {jour.isoformat()} : week-end, ignoré sans requête")
        jour -= timedelta(days=1)
    raise SystemExit(
        f"Aucun bulletin trouvé sur les {RECUL_MAX} derniers jours de {annee}.\n  "
        + "\n  ".join(essais[:6]))


def releve(txt):
    """BNPA de chaque titre coté, par la même règle que le tableau de bord."""
    table, sans_per = {}, []
    for v in lignes_actions(txt):
        if not v.get("per") or not v.get("cloture"):
            sans_per.append(v["symbole"])
            continue
        table[v["symbole"]] = dict(
            cours=v["cloture"], per=v["per"],
            bnpa=round(v["cloture"] / v["per"], 2))
    return table, sans_per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annee", type=int, default=date.today().year - 1,
                    help="année de clôture à relever ; par défaut l'année précédente")
    ap.add_argument("--pdf", help="bulletin local, sans téléchargement")
    ap.add_argument("--sortie", default=SORTIE)
    a = ap.parse_args()

    if a.pdf:
        chemin, tmp = a.pdf, None
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(dernier_bulletin_de_lannee(a.annee))
        tmp.close()
        chemin = tmp.name

    txt = texte_pdf(chemin)
    numero, jour_iso = entete(txt)
    table, sans_per = releve(txt)

    print(f"BOC n° {numero} — séance du {jour_iso} — {len(table)} BNPA relevés")
    if sans_per:
        print(f"  sans PER au bulletin, donc sans BNPA : {', '.join(sorted(sans_per))}")
    if table:
        ech = sorted(table.items())[:3]
        for s, d in ech:
            print(f"    {s:6s} cours {d['cours']:>9,} / PER {d['per']:>6} "
                  f"= BNPA {d['bnpa']:>10,.2f}".replace(",", " "))

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    json.dump(dict(numero=numero, seance=jour_iso, annee=a.annee,
                   source="brvm.org — bulletin de clôture d'exercice",
                   methode="cours de clôture / PER publié",
                   valeurs=table, sans_per=sorted(sans_per)),
              open(a.sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{a.sortie} écrit.")
    if tmp:
        os.unlink(tmp.name)


if __name__ == "__main__":
    main()
