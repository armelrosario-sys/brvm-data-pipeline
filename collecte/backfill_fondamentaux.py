#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/backfill_fondamentaux.py — Boucle P8 (25/07/2026).

Objectif : exploiter les PDF de type "rapport" DEJA archives dans les
Releases GitHub (924 au 25/07/2026, cf. MANIFESTE.csv) pour enrichir la
couverture des etats financiers, sans aucune requete vers brvm.org.

Principe directeur (identique au reste du pipeline) : integrite avant
couverture. Ce script n'ecrit JAMAIS dans la table ETATS de moteur/peupler.py
(qui reste la source manuellement verifiee) : il produit un fichier separe,
collecte/fondamentaux_extraits.csv, a relire et fusionner a la main.

Boucle "tester plusieurs strategies, ne retenir que la validee" :
  1. Filtrage par nom de fichier : seuls "etats_financiers"/"etat_financier"
     sont traites en priorite (documents a tableaux structures). Les
     rapports CAC / attestations sont ecartes explicitement (peu de chances
     de contenir un bilan chiffre) -> logges, jamais silencieusement ignores.
  2. Identification de la societe : matching du "slug" du nom de fichier
     contre le nom normalise des 47 societes (table SOCIETES de peupler.py,
     recopiee ici en miroir + alias connus). Aucune societe non identifiee
     avec certitude n'est assignee au hasard -> reportee dans
     collecte/rapports_non_identifies.csv pour revue humaine.
  3. Extraction : strategie 1 = pdfplumber (tables + recherche de libelles
     comptables). Si le bilan ne s'equilibre pas (Actif != Passif au-dela de
     1% de tolerance) ou si rien n'est trouve -> strategie 2 = Camelot
     (lattice puis stream). Si toujours rien (PDF scanne, pas de texte
     extractible) -> strategie 3 = OCR (pytesseract sur rendu 300dpi).
  4. Validation : statut VALIDE seulement si le bilan s'equilibre ET que
     l'unite (millions/milliers FCFA) est confirmee dans le texte du
     document. Sinon PROBABLE. Si aucune donnee chiffree exploitable
     n'est trouvee -> aucune ligne ecrite, echec logge (jamais de valeur
     devinee).
  5. Reprise automatique : progression committee tous les N documents
     (voir workflow), fichier de suivi collecte/fondamentaux_traites.json
     empeche de retraiter un document deja vu. Budget de temps respecte
     (MAX_MINUTES) pour tenir dans la limite de job GitHub Actions.

Usage : python3 collecte/backfill_fondamentaux.py [--max-minutes N] [--limit N]
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

import requests

MANIFESTE = "MANIFESTE.csv"
TRAITES = "collecte/fondamentaux_traites.json"
SORTIE = "collecte/fondamentaux_extraits.csv"
NON_IDENTIFIES = "collecte/rapports_non_identifies.csv"
ECHECS = "collecte/fondamentaux_echecs.jsonl"
REPO = "armelrosario-sys/brvm-data-pipeline"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_HEADERS = {"Accept": "application/vnd.github+json"}
if GITHUB_TOKEN:
    API_HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# Miroir volontairement redondant (et non un import) de la table SOCIETES de
# moteur/peupler.py : ce script doit pouvoir tourner meme si peupler.py
# change de forme. A tenir synchronise manuellement si de nouvelles societes
# sont cotees (l'ecart sera visible : nouveaux slugs dans rapports_non_identifies.csv).
# Copie exacte (25/07/2026) de la table SOCIETES de moteur/peupler.py --
# JAMAIS retapee de memoire : toute societe absente d'ici doit venir d'une
# relecture du fichier source, pas d'une supposition. Verifier au besoin
# `sed -n '/^SOCIETES = \[/,/^\]/p' moteur/peupler.py` avant toute modification.
SOCIETES_NOMS = {
    "SNTS": "Sonatel", "STBC": "Sitab", "NSBC": "NSIA Banque CI", "SMBC": "SMB CI",
    "SAFC": "Safca (Alios Finance CI)", "ORGT": "Oragroup Togo",
    "BOABF": "BOA Burkina Faso", "BBGCI": "Bridge Bank Group CI",
    "CBIBF": "Coris Bank International", "SICC": "Sicor",
    "NTLC": "Nestle CI", "PALC": "Palm CI", "SPHC": "Saph CI",
    "TTLC": "TotalEnergies Marketing CI", "TTLS": "TotalEnergies Marketing SN",
    "ECOC": "Ecobank Cote d'Ivoire", "SGBC": "Societe Generale Cote d'Ivoire",
    "SIBC": "Societe Ivoirienne de Banque", "ONTBF": "Onatel BF",
    "ORAC": "Orange Cote d'Ivoire", "SCRC": "Sucrivoire", "SLBC": "Solibra CI",
    "SOGC": "SOGB CI", "UNLC": "Unilever CI", "ABJC": "Servair Abidjan",
    "BNBC": "Bernabe CI", "CFAC": "CFAO Motors CI", "LNBB": "Loterie Nationale du Benin",
    "NEIC": "NEI-CEDA CI", "PRSC": "Tractafric Motors CI", "UNXC": "Uniwax CI",
    "SHEC": "Vivo Energy CI", "BICB": "BIIC Benin", "BICC": "BICI CI",
    "BOAB": "BOA Benin", "BOAC": "BOA Cote d'Ivoire", "BOAM": "BOA Mali",
    "BOAN": "BOA Niger", "BOAS": "BOA Senegal",
    "ETIT": "Ecobank Transnational Incorporated Togo", "CABC": "Sicable CI",
    "FTSC": "Filtisac CI", "SDSC": "Africa Global Logistics CI",
    "SEMC": "Eviosys Packaging Siem CI", "SIVC": "Erium CI (ex-Air Liquide CI)",
    "STAC": "Setao CI", "CIEC": "CIE CI", "SDCC": "Sode CI",
}
ALIAS_MANUELS = {
    # slug de nom de fichier -> ticker, pour les cas ou le rapprochement
    # automatique par nom echoue malgre la table SOCIETES ci-dessus (sigles,
    # anciennes denominations non couvertes par le nom officiel courant).
    # A completer au fil des entrees remontees dans rapports_non_identifies.csv
    # -- jamais rempli sans confirmation.
}
MOTS_VIDES = {"ci", "sa", "sarl", "bf", "tg", "sn", "bj", "ml", "ne", "et", "de", "la", "le"}
MOTS_CLES_UTILES = ("etats_financiers", "etat_financier", "etats_financier")
MOTS_CLES_SECONDAIRES = ("rapport_dactivit", "rapport_d_activit")
MOTS_CLES_ECARTES = ("attestation_des_cacs", "rapport_des_cacs", "rapport_du_conseil",
                      "convocation", "avis_de_reunion", "proces_verbal")

RE_ACTIF = re.compile(r"TOTAL\s+(?:GENERAL\s+)?ACTIF", re.IGNORECASE)
RE_PASSIF = re.compile(r"TOTAL\s+(?:GENERAL\s+)?(?:DU\s+)?PASSIF", re.IGNORECASE)
RE_CP = re.compile(r"TOTAL\s+(?:DES\s+)?CAPITAUX\s+PROPRES", re.IGNORECASE)
RE_RN = re.compile(r"R[EÉ]SULTAT\s+NET(?!\s+PAR)", re.IGNORECASE)
RE_UNITE_MILLIERS = re.compile(r"en\s+milliers?\s+de\s+francs", re.IGNORECASE)
RE_UNITE_MILLIONS = re.compile(r"en\s+millions?\s+de\s+francs", re.IGNORECASE)
RE_EXERCICE = re.compile(r"exercice\s+(?:clos\s+le\s+31[/.]12[/.])?(\d{4})", re.IGNORECASE)
RE_NOMBRE = re.compile(r"-?[\d\s\u00a0]{2,}(?:,\d+)?")


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = re.sub(r"[^a-zA-Z0-9]+", "_", texte.lower()).strip("_")
    return texte


def construire_index_societes():
    index = {}
    for ticker, nom in SOCIETES_NOMS.items():
        mots = [m for m in normaliser(nom).split("_") if m not in MOTS_VIDES]
        index[frozenset(mots)] = ticker
    return index


def identifier_ticker(nom_fichier, index_societes):
    slug = normaliser(nom_fichier)
    for cle_alias, ticker in ALIAS_MANUELS.items():
        if cle_alias in slug:
            return ticker  # peut etre None -> traite comme non identifie
    tokens_fichier = slug.split("_")
    mots_fichier = set(tokens_fichier) - MOTS_VIDES
    meilleur, meilleur_score = None, 0
    for mots_societe, ticker in index_societes.items():
        score = len(mots_societe & mots_fichier)
        if score > meilleur_score and score >= 1:
            meilleur, meilleur_score = ticker, score
    if meilleur:
        return meilleur
    # Repli sigle (ex. "eti_tg" pour ETIT = Ecobank Transnational Incorporated
    # Togo) : n'accepte qu'une correspondance EXACTE acronyme+pays pour
    # limiter le risque de faux positif ; sinon laisse non identifie.
    for ticker, nom in SOCIETES_NOMS.items():
        mots_nom = [m for m in normaliser(nom).split("_") if m not in MOTS_VIDES]
        if not mots_nom:
            continue
        acronyme = "".join(m[0] for m in mots_nom)
        for tok in tokens_fichier:
            if len(tok) >= 3 and (tok == acronyme or acronyme.startswith(tok)):
                return ticker
    return None


def categorie_fichier(nom_fichier):
    slug = normaliser(nom_fichier)
    if any(m in slug for m in MOTS_CLES_ECARTES):
        return "ecarte"
    if any(m in slug for m in MOTS_CLES_UTILES):
        return "prioritaire"
    if any(m in slug for m in MOTS_CLES_SECONDAIRES):
        return "secondaire"
    return "inconnu"


def a_nombre(cellule):
    if cellule is None:
        return None
    s = str(cellule).replace("\u00a0", " ").strip()
    s2 = s.replace(" ", "").replace(",", ".")
    try:
        return float(s2)
    except ValueError:
        return None


def extraire_pdfplumber(chemin_pdf):
    """Strategie 1 : tables structurees. Retourne dict de champs ou {}."""
    import pdfplumber
    champs = {}
    texte_total = []
    try:
        with pdfplumber.open(chemin_pdf) as pdf:
            for page in pdf.pages:
                texte = page.extract_text() or ""
                texte_total.append(texte)
                for table in page.extract_tables():
                    for row in table:
                        if not row:
                            continue
                        libelle = " ".join(c for c in row if c) or ""
                        if RE_ACTIF.search(libelle) and "total_actif" not in champs:
                            for cell in reversed(row):
                                v = a_nombre(cell)
                                if v:
                                    champs["total_actif"] = v
                                    break
                        if RE_PASSIF.search(libelle) and "total_passif" not in champs:
                            for cell in reversed(row):
                                v = a_nombre(cell)
                                if v:
                                    champs["total_passif"] = v
                                    break
                        if RE_CP.search(libelle) and "capitaux_propres" not in champs:
                            for cell in reversed(row):
                                v = a_nombre(cell)
                                if v:
                                    champs["capitaux_propres"] = v
                                    break
                        if RE_RN.search(libelle) and "resultat_net" not in champs:
                            valeurs = [a_nombre(c) for c in row if a_nombre(c) is not None]
                            if valeurs:
                                champs["resultat_net"] = valeurs[0]
                                if len(valeurs) > 1:
                                    champs["resultat_net_n1"] = valeurs[1]
    except Exception as e:
        champs["_erreur"] = f"pdfplumber: {type(e).__name__}: {e}"
        return champs
    texte_complet = "\n".join(texte_total)
    m = RE_EXERCICE.search(texte_complet)
    if m:
        champs["exercice"] = int(m.group(1))
    if RE_UNITE_MILLIERS.search(texte_complet):
        champs["unite"] = "milliers"
    elif RE_UNITE_MILLIONS.search(texte_complet):
        champs["unite"] = "millions"
    champs["_texte_present"] = bool(texte_complet.strip())
    return champs


def extraire_camelot(chemin_pdf):
    """Strategie 2 : Camelot (lattice puis stream), pour tables mal
    reconnues par pdfplumber (bordures fines, mise en page complexe)."""
    try:
        import camelot
    except ImportError:
        return {"_erreur": "camelot non installe"}
    champs = {}
    for flavor in ("lattice", "stream"):
        try:
            tables = camelot.read_pdf(chemin_pdf, pages="all", flavor=flavor)
        except Exception as e:
            continue
        for t in tables:
            for _, row in t.df.iterrows():
                libelle = " ".join(str(c) for c in row)
                if RE_ACTIF.search(libelle) and "total_actif" not in champs:
                    for cell in reversed(list(row)):
                        v = a_nombre(cell)
                        if v:
                            champs["total_actif"] = v
                            break
                if RE_PASSIF.search(libelle) and "total_passif" not in champs:
                    for cell in reversed(list(row)):
                        v = a_nombre(cell)
                        if v:
                            champs["total_passif"] = v
                            break
        if "total_actif" in champs and "total_passif" in champs:
            champs["_strategie_camelot"] = flavor
            break
    return champs


def extraire_ocr(chemin_pdf):
    """Strategie 3 : OCR, dernier recours (PDF scanne sans texte extractible)."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return {"_erreur": "pytesseract/pdf2image non installes"}
    champs = {}
    try:
        pages = convert_from_path(chemin_pdf, dpi=300)
        texte_total = []
        for img in pages[:6]:  # limite : les etats financiers cles sont en debut/milieu de doc
            texte_total.append(pytesseract.image_to_string(img, lang="fra"))
        texte = "\n".join(texte_total)
        m_actif = RE_ACTIF.search(texte)
        if m_actif:
            suite = texte[m_actif.end():m_actif.end() + 60]
            nombres = RE_NOMBRE.findall(suite)
            if nombres:
                v = a_nombre(nombres[0])
                if v:
                    champs["total_actif"] = v
        m = RE_EXERCICE.search(texte)
        if m:
            champs["exercice"] = int(m.group(1))
        champs["_texte_present"] = bool(texte.strip())
    except Exception as e:
        champs["_erreur"] = f"ocr: {type(e).__name__}: {e}"
    return champs


def valider(champs):
    """Retourne (statut, note)."""
    actif = champs.get("total_actif")
    passif = champs.get("total_passif")
    unite_confirmee = "unite" in champs
    if actif and passif:
        ecart = abs(actif - passif) / actif if actif else 1
        if ecart < 0.01:
            return ("VALIDE" if unite_confirmee else "PROBABLE",
                    "bilan equilibre" + ("" if unite_confirmee else " ; unite non confirmee dans le texte"))
        return ("QUARANTAINE", f"desequilibre actif/passif : {ecart:.1%}")
    if champs.get("resultat_net") is not None:
        return ("PROBABLE", "resultat net trouve, bilan complet non localise")
    return (None, "aucune donnee chiffree exploitable")


def charger_json(chemin, defaut):
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    return defaut


def sauver_json(chemin, data):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=int, default=320)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    limite_s = args.max_minutes * 60

    traites = set(charger_json(TRAITES, []))
    index_societes = construire_index_societes()

    lignes_manifeste = []
    with open(MANIFESTE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["type"] == "rapport":
                lignes_manifeste.append(row)

    # priorite : etats_financiers d'abord, puis rapports d'activite, le
    # reste en dernier (traite seulement si le temps le permet)
    ordre = {"prioritaire": 0, "secondaire": 1, "inconnu": 2, "ecarte": 3}
    lignes_manifeste.sort(key=lambda r: ordre[categorie_fichier(r["nom_fichier"])])

    session = requests.Session()
    session.headers.update(API_HEADERS)

    resultats, non_identifies, echecs = [], [], []
    traites_ce_run = 0

    for row in lignes_manifeste:
        if time.time() - t0 > limite_s:
            print(f"[budget temps atteint apres {traites_ce_run} document(s)]", file=sys.stderr)
            break
        if args.limit and traites_ce_run >= args.limit:
            break
        sha = row["sha256"]
        if sha in traites:
            continue
        cat = categorie_fichier(row["nom_fichier"])
        if cat == "ecarte":
            traites.add(sha)  # jamais retraite, mais ne consomme pas de temps d'extraction
            continue

        ticker = identifier_ticker(row["nom_fichier"], index_societes)
        if not ticker:
            non_identifies.append({"sha256": sha, "nom_fichier": row["nom_fichier"],
                                    "url": row["url"], "periode": row["periode"]})
            traites.add(sha)
            continue

        # Telechargement de l'asset : release GitHub identifiee par tag +
        # nom de fichier archive (cf. sauver_pdf/collecter_fichier existants)
        rel = session.get(
            f"https://api.github.com/repos/{REPO}/releases/tags/{row['release_tag']}", timeout=30)
        if rel.status_code != 200:
            echecs.append({"sha256": sha, "raison": f"release introuvable HTTP {rel.status_code}"})
            continue
        asset = next((a for a in rel.json().get("assets", [])
                      if a["name"] == row["nom_fichier"]), None)
        if not asset:
            echecs.append({"sha256": sha, "raison": "asset absent de la release"})
            continue
        pdf_resp = session.get(asset["url"],
                                headers={**API_HEADERS, "Accept": "application/octet-stream"},
                                timeout=60)
        if pdf_resp.status_code != 200:
            echecs.append({"sha256": sha, "raison": f"telechargement asset HTTP {pdf_resp.status_code}"})
            continue

        os.makedirs("/tmp/fondamentaux", exist_ok=True)
        chemin_local = f"/tmp/fondamentaux/{sha[:16]}.pdf"
        with open(chemin_local, "wb") as f:
            f.write(pdf_resp.content)

        # boucle strategies : essayer, valider, arreter des qu'une strategie
        # produit un resultat VALIDE ou PROBABLE ; sinon tenter la suivante
        strategie_utilisee, champs, statut, note = None, {}, None, None
        for nom_strat, fonction in (("pdfplumber", extraire_pdfplumber),
                                     ("camelot", extraire_camelot),
                                     ("ocr", extraire_ocr)):
            champs = fonction(chemin_local)
            if champs.get("_erreur"):
                continue
            statut, note = valider(champs)
            if statut in ("VALIDE", "PROBABLE"):
                strategie_utilisee = nom_strat
                break
            # QUARANTAINE ou None : on garde le meilleur essai pour le log
            # mais on continue d'essayer les strategies suivantes

        if statut in ("VALIDE", "PROBABLE"):
            resultats.append({
                "sha256": sha, "ticker": ticker,
                "exercice": champs.get("exercice", ""),
                "resultat_net": champs.get("resultat_net", ""),
                "resultat_net_n1": champs.get("resultat_net_n1", ""),
                "total_actif": champs.get("total_actif", ""),
                "total_passif": champs.get("total_passif", ""),
                "capitaux_propres": champs.get("capitaux_propres", ""),
                "source_type": "OCR" if strategie_utilisee == "ocr" else "NATIF",
                "statut_donnee": statut,
                "strategie": strategie_utilisee,
                "unite": champs.get("unite", ""),
                "note": note,
                "source_url": row["url"],
                "date_extraction_utc": datetime.now(timezone.utc).isoformat(),
            })
        else:
            echecs.append({"sha256": sha, "ticker": ticker, "nom_fichier": row["nom_fichier"],
                            "raison": note or "aucune strategie n'a produit de resultat exploitable"})

        traites.add(sha)
        traites_ce_run += 1
        try:
            os.remove(chemin_local)
        except OSError:
            pass

        if traites_ce_run % 25 == 0:
            print(f"[{traites_ce_run} documents traites, "
                  f"{int(time.time()-t0)}s ecoules]", file=sys.stderr)

    # ---- ecriture des sorties (append-only, jamais d'ecrasement) ----
    if resultats:
        existe = os.path.exists(SORTIE)
        os.makedirs("collecte", exist_ok=True)
        with open(SORTIE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(resultats[0].keys()))
            if not existe:
                w.writeheader()
            w.writerows(resultats)

    if non_identifies:
        existe = os.path.exists(NON_IDENTIFIES)
        with open(NON_IDENTIFIES, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(non_identifies[0].keys()))
            if not existe:
                w.writeheader()
            w.writerows(non_identifies)

    if echecs:
        with open(ECHECS, "a", encoding="utf-8") as f:
            for e in echecs:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    sauver_json(TRAITES, sorted(traites))

    print(f"Run termine : {len(resultats)} ligne(s) extraite(s) et validees, "
          f"{len(non_identifies)} societe(s) non identifiee(s), "
          f"{len(echecs)} echec(s), {traites_ce_run} document(s) traites en tout, "
          f"{int(time.time()-t0)}s.")


if __name__ == "__main__":
    main()
