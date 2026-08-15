#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capitaux propres depuis les fiches de notation financière.

Ce script ne re-parcourt PAS les 30 pages d'index de la BRVM : il réutilise
collecte/notations_financieres.csv, déjà produit par le workflow P12, qui porte
pour chaque annonce le ticker, la date et l'URL du PDF.

    python collecte/capitaux_propres.py --test        # analyseur seul, sans réseau
    python collecte/capitaux_propres.py               # rapports de moins de 18 mois
    python collecte/capitaux_propres.py --mois 12     # fenêtre plus stricte

Écrit donnees/fonds_propres.csv, lu tel quel par pipeline/construit_donnees.py.
Les lignes déjà renseignées à la main y sont conservées : la saisie manuelle
prime toujours sur l'extraction automatique.

Dépendances : requests, et pdftotext (paquet poppler-utils).
"""
import argparse, csv, os, re, subprocess, sys, tempfile, time
from datetime import date

import requests

INDEX = os.path.join("collecte", "notations_financieres.csv")
SORTIE = os.path.join("donnees", "fonds_propres.csv")
PAUSE = 1.5
ENTETES = ["symbole", "exercice", "fonds_propres", "source", "agence",
           "date_rapport", "statut", "releve_le"]

# « En millions de francs CFA 2023 2024 » — donne l'unité et les exercices colonnés
DEVISE = r"(?:F\s?)?CFA|XOF"        # « FCFA », « F CFA » ou « francs CFA »
RE_UNITE = re.compile(
    r"en\s+millions?\s+de\s+(?:francs?\s+)?(?:" + DEVISE + r")\s*"
    r"((?:\s*(?:19|20)\d{2}){1,6})", re.I)
RE_MILLIARDS = re.compile(
    r"en\s+milliards?\s+de\s+(?:francs?\s+)?(?:" + DEVISE + r")", re.I)
# « Capitaux propres 17 743 17 748 » : on isole la ligne, puis on découpe en
# nombres. L'espace n'est un séparateur de milliers que suivi d'exactement trois
# chiffres — sans quoi deux colonnes voisines fusionneraient en un seul nombre.
RE_CAPITAUX = re.compile(
    r"(?:capitaux|fonds)\s+propres(?:\s+(?:part\s+du\s+groupe|nets?))?\s*\*?\s*[:|]?\s*([^\n]*)",
    re.I)
RE_MONTANT = re.compile(
    r"\(?-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?\)?"      # 17 743 / 1 274 638
    r"|\(?-?\d+(?:[.,]\d+)?\)?")                                  # 17743 / 17743,5


def nombre(t):
    t = t.strip()
    negatif = t.startswith("(") and t.endswith(")")
    s = re.sub(r"[()\s\u00a0\u202f]", "", t).replace(",", ".")
    if s.count(".") == 1 and len(s.split(".")[1]) == 3:      # 17.743 = séparateur de milliers
        s = s.replace(".", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s or ""):
        return None
    v = float(s)
    return -v if negatif else v


def extrait(texte):
    """Capitaux propres du dernier exercice publié, en millions de FCFA."""
    m_cap = RE_CAPITAUX.search(texte)
    if not m_cap:
        return None
    valeurs = [v for v in (nombre(x) for x in RE_MONTANT.findall(m_cap.group(1))) if v is not None]
    if not valeurs:
        return None

    m_u = RE_UNITE.search(texte)
    annees = re.findall(r"(?:19|20)\d{2}", m_u.group(1)) if m_u else []
    facteur = 1000 if RE_MILLIARDS.search(texte) else 1      # tout ramené en millions

    # Une colonne par exercice. Si le compte ne tombe pas juste, la mise en page a
    # été mal découpée : on renonce plutôt que de retenir un montant douteux.
    if annees and len(valeurs) != len(annees):
        return None
    exercice = annees[-1] if annees else ""
    return dict(fonds_propres=valeurs[-1] * facteur, exercice=exercice,
                unite="millions" if facteur == 1 else "milliards convertis",
                colonnes=len(valeurs))


def texte_pdf(octets):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(octets)
        chemin = f.name
    try:
        return subprocess.run(["pdftotext", "-layout", chemin, "-"],
                              capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(chemin)


def autotest():
    """Analyseur rejoué sur des fiches réelles, sans réseau — garde-fou avant collecte."""
    cas = [
        ("Bernabé CI, Bloomfield juillet 2025", """
Informations financières de base
En millions de francs CFA          2023      2024
Actif immobilisé net              7 118     6 463
Stocks                           31 131    27 767
Capitaux propres                 17 743    17 748
Dettes financières *                649       897
Chiffre d'affaires               45 955    45 312
Résultat net                         36         7
""", 17748.0, "2024"),
        ("capitaux propres négatifs entre parenthèses", """
En millions de FCFA   2024   2025
Capitaux propres    (8 420) (10 659)
""", -10659.0, "2025"),
        ("exercice unique", """
Informations financières de base En millions de FCFA 2025
Capitaux propres 1 274 638
""", 1274638.0, "2025"),
        ("intitulé bancaire « Fonds propres part du groupe »", """
Informations financières de base
En millions de FCFA            2023      2024
Fonds propres part du groupe  214 500   215 330
Résultat net                   38 100    40 712
""", 215330.0, "2024"),
        ("fiche libellée en milliards", """
Informations financières de base En milliards de FCFA 2024
Capitaux propres 1 274
""", 1274000.0, ""),
    ]
    ok = True
    for libelle, texte, attendu, exercice in cas:
        r = extrait(texte)
        bon = r and abs(r["fonds_propres"] - attendu) < 0.5 and (not exercice or r["exercice"] == exercice)
        ok &= bool(bon)
        print(f"  {'OK   ' if bon else 'ECHEC'} {libelle:45s} -> "
              f"{r['fonds_propres'] if r else None} (attendu {attendu})")
    brouille = extrait("En millions de FCFA 2023 2024\nCapitaux propres 17 743\n")
    print(f"  {'OK   ' if brouille is None else 'ECHEC'} colonnes illisibles : renoncement            -> None")
    ok &= brouille is None
    absent = extrait("Ce communiqué ne contient aucun tableau financier.")
    print(f"  {'OK   ' if absent is None else 'ECHEC'} fiche sans tableau financier                  -> None")
    ok &= absent is None
    return ok


def conserver_diagnostic(ticker, url, texte):
    """Écrit un extrait du rapport autour des mentions utiles, pour comprendre
    pourquoi l'analyseur n'a rien trouvé sans avoir à rouvrir le PDF."""
    dossier = os.path.join("donnees", "diagnostic")
    os.makedirs(dossier, exist_ok=True)
    lignes = texte.split("\n")
    reperes = [i for i, l in enumerate(lignes)
               if re.search(r"propres|informations\s+financi|en\s+milli", l, re.I)]
    extraits = []
    for i in reperes[:6]:
        extraits.append("\n".join(lignes[max(0, i - 4):i + 8]))
    with open(os.path.join(dossier, f"{ticker}.txt"), "w", encoding="utf-8") as f:
        f.write(url + "\n" + "=" * 70 + "\n")
        f.write("\n\n---\n\n".join(extraits) if extraits
                else "Aucune mention de capitaux propres : communiqué sans tableau financier.\n"
                     + "\n".join(lignes[:25]))


def recule_de_mois(jour, mois):
    """Même quantième, `mois` mois plus tôt, en bornant les fins de mois."""
    total = jour.year * 12 + (jour.month - 1) - mois
    an, m = divmod(total, 12)
    dernier = [31, 29 if an % 4 == 0 and (an % 100 or an % 400 == 0) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m]
    return date(an, m + 1, min(jour.day, dernier))


def deja_saisi():
    """Lignes renseignées à la main : elles ne sont jamais écrasées."""
    garde = {}
    if os.path.exists(SORTIE):
        with open(SORTIE, encoding="utf-8") as f:
            for l in csv.DictReader(f, delimiter=";"):
                if (l.get("fonds_propres") or "").strip() and (l.get("statut") or "") != "notation":
                    garde[l["symbole"].strip().upper()] = l
    return garde


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="analyseur seul, sans réseau")
    ap.add_argument("--mois", type=int, default=18, help="ancienneté maximale du rapport")
    ap.add_argument("--diagnostic", action="store_true",
                    help="conserver le texte des rapports non exploités, pour analyse")
    a = ap.parse_args()

    print("Autotest de l'analyseur")
    if not autotest():
        sys.exit("Analyseur en échec : ne pas collecter tant que ce n'est pas corrigé.")
    if a.test:
        return

    if not os.path.exists(INDEX):
        sys.exit(f"{INDEX} introuvable : lancer d'abord le workflow P12 (notations).")

    with open(INDEX, encoding="utf-8") as f:
        lignes = [l for l in csv.DictReader(f) if (l.get("url_pdf") or "").strip()]

    # un seul rapport par titre : le plus récent, dans la fenêtre demandée
    limite = recule_de_mois(date.today(), a.mois)
    print(f"Rapports retenus à partir du {limite.isoformat()}")
    recents = {}
    for l in lignes:
        t = (l.get("ticker") or "").strip().upper()
        d = (l.get("date_annonce") or "").strip()
        if not t or not d:
            continue
        if d > str(limite) and (t not in recents or d > recents[t]["date_annonce"]):
            recents[t] = l
    print(f"{len(recents)} titre(s) avec un rapport de moins de {a.mois} mois")

    garde = deja_saisi()
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; pipeline-brvm/1.0)"
    trouves, echecs = {}, []

    for i, (t, l) in enumerate(sorted(recents.items()), 1):
        if t in garde:
            print(f"[{i:2}/{len(recents)}] {t:6s} saisie manuelle conservée")
            continue
        try:
            r = s.get(l["url_pdf"], timeout=60)
            r.raise_for_status()
            texte = texte_pdf(r.content)
            res = extrait(texte)
            if not res:
                if a.diagnostic:
                    conserver_diagnostic(t, l["url_pdf"], texte)
                raise ValueError("ni tableau financier ni ligne de capitaux propres exploitable")
            trouves[t] = dict(symbole=t, exercice=res["exercice"],
                              fonds_propres=res["fonds_propres"], source=l["url_pdf"],
                              agence=l.get("agence", ""), date_rapport=l["date_annonce"],
                              statut="notation", releve_le=date.today().isoformat())
            print(f"[{i:2}/{len(recents)}] {t:6s} {res['fonds_propres']:>14,.0f} M FCFA "
                  f"({res['exercice'] or 'exercice non lu'}, {res['colonnes']} colonne(s))"
                  .replace(",", " "))
        except Exception as e:
            echecs.append(f"{t} : {e}")
            print(f"[{i:2}/{len(recents)}] {t:6s} ECHEC {e}")
        time.sleep(PAUSE)

    os.makedirs(os.path.dirname(SORTIE) or ".", exist_ok=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ENTETES, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for t in sorted(set(garde) | set(trouves)):
            w.writerow(garde.get(t) or trouves[t])

    total = len(recents)
    print(f"\n{SORTIE} écrit — {len(trouves)} extraction(s) sur {total} rapport(s) examiné(s), "
          f"{len(garde)} saisie(s) manuelle(s)")
    if echecs:
        print(f"\n{len(echecs)} rapport(s) sans capitaux propres exploitables :")
        for e in echecs:
            print("  " + e)
        print("Beaucoup de communiqués GCR ne comportent aucun tableau financier.")
        print("Relancer avec --diagnostic pour conserver le texte de ces rapports.")


if __name__ == "__main__":
    main()
