#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/extracteur_etats.py — CHANTIER "extraction automatique" (15/07/2026).

v2 — reconstruction POSITIONNELLE des colonnes du bilan/compte de resultat.

Decouverte en testant sur un document reel (SDSC, exercice 2024) : le texte
OCR a plat ("Situation nette 77 095 183 61 034 257") est AMBIGU -- deux
nombres separes par un simple espace sont indiscernables d'un seul grand
nombre par regex. La v1 (texte OCR brut) donnait un resultat correct pour
resultat_net (separateur "]" fortuit) mais faux pour tous les autres champs.

Solution : tesseract en mode TSV (positions x/y de chaque mot), groupage par
ligne logique (block/par/line tesseract), puis reconstruction des nombres
par ECART HORIZONTAL entre mots :
  - ecart < 60 px  -> meme nombre (separateur de milliers SYSCOHADA)
  - ecart >= 60 px -> nouveau nombre / nouvelle colonne
Seuils mesures empiriquement (ecarts intra-nombre observes : 18-34 px ;
ecarts inter-nombre observes : 152-1828 px -- large marge de securite).

NE MODIFIE JAMAIS peupler.py NI la base directement. Produit une proposition
structuree (JSON) A VERIFIER PAR UN HUMAIN -- l'OCR peut se tromper.

Usage :
  python3 extracteur_etats.py chemin/vers/rapport.pdf --ticker SDSC --referentiel syscohada
"""
import argparse
import csv
import io
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

import pdfplumber
import yaml

SEUIL_CHARS_NATIFS = 400
SEUIL_ECART_NOUVEAU_NOMBRE = 60
RACINE = Path(__file__).resolve().parent.parent
DICTIONNAIRE_PATH = RACINE / "config" / "dictionnaire_semantique.yaml"


def _normaliser(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", txt.lower()).strip()


def charger_labels(referentiel):
    cfg = yaml.safe_load(DICTIONNAIRE_PATH.read_text())
    out = {}
    for champ, refs in cfg.get("champs_canoniques", {}).items():
        labels = refs.get(referentiel, [])
        if labels:
            out[champ] = [_normaliser(l) for l in labels]
    return out


def _ocr_tsv(page, index_page):
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / f"page_{index_page}.png"
        page.to_image(resolution=300).save(str(img_path))
        out_base = Path(tmp) / f"page_{index_page}_ocr"
        resultat = subprocess.run(
            ["tesseract", str(img_path), str(out_base), "-l", "fra", "tsv"],
            capture_output=True, timeout=90)
        if resultat.returncode != 0:
            return []
        tsv_texte = out_base.with_suffix(".tsv").read_text(encoding="utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(tsv_texte), delimiter="\t"))
    mots = [r for r in rows if r.get("level") == "5" and r.get("text", "").strip()]
    groupes = {}
    for m in mots:
        cle = (m["block_num"], m["par_num"], m["line_num"])
        groupes.setdefault(cle, []).append(m)
    lignes = []
    for cle, mots_ligne in groupes.items():
        tries = sorted(mots_ligne, key=lambda m: int(m["left"]))
        lignes.append([{"texte": m["text"], "left": int(m["left"]), "width": int(m["width"])}
                       for m in tries])
    return lignes


def _texte_natif_en_lignes(page):
    mots = page.extract_words()
    lignes_par_y = {}
    for m in mots:
        y = round(m["top"] / 3) * 3
        lignes_par_y.setdefault(y, []).append(m)
    lignes = []
    for y, mots_ligne in sorted(lignes_par_y.items()):
        tries = sorted(mots_ligne, key=lambda m: m["x0"])
        lignes.append([{"texte": m["text"], "left": m["x0"] * 10, "width": (m["x1"] - m["x0"]) * 10}
                       for m in tries])
    return lignes


def lire_page_en_lignes(page, index_page):
    texte_natif = page.extract_text() or ""
    if len(texte_natif) >= SEUIL_CHARS_NATIFS:
        try:
            return _texte_natif_en_lignes(page), "natif"
        except Exception:
            pass
    try:
        return _ocr_tsv(page, index_page), "ocr"
    except Exception as e:
        print(f"[extracteur_etats] OCR echec page {index_page} : {type(e).__name__}: {e}",
              file=sys.stderr)
        return [], "echec"


def _regrouper_nombres(mots_apres_label):
    nombres = []
    courant, fin_precedente = "", None
    for m in mots_apres_label:
        txt = m["texte"].strip()
        frag = re.sub(r"[^\d\-]", "", txt)
        if not frag or not re.search(r"\d", frag):
            if courant:
                nombres.append(courant)
                courant, fin_precedente = "", None
            continue
        ecart = (m["left"] - fin_precedente) if fin_precedente is not None else 0
        if courant and ecart >= SEUIL_ECART_NOUVEAU_NOMBRE:
            nombres.append(courant)
            courant = frag
        else:
            courant += frag
        fin_precedente = m["left"] + m["width"]
    if courant:
        nombres.append(courant)
    valeurs = []
    for n in nombres:
        try:
            valeurs.append(int(n))
        except ValueError:
            pass
    return valeurs


def extraire_annees_bilan(lignes):
    for ligne in lignes:
        texte_ligne = " ".join(m["texte"] for m in ligne)
        annees = re.findall(r"\b(20\d{2})\b", texte_ligne)
        if len(annees) >= 2 and ("actif" in texte_ligne.lower() or "bilan" in texte_ligne.lower()):
            return int(annees[0]), int(annees[1])
    return None, None


def extraire_champs(lignes, labels_normalises):
    resultats = {}
    annee_c, annee_p = extraire_annees_bilan(lignes)

    for champ, labels in labels_normalises.items():
        for ligne in lignes:
            mots_norm = [_normaliser(m["texte"]) for m in ligne]
            label_trouve, idx_fin = None, None
            for lbl in labels:
                n_mots_lbl = len(lbl.split())
                for i in range(len(mots_norm) - n_mots_lbl + 1):
                    if " ".join(mots_norm[i:i + n_mots_lbl]) == lbl:
                        label_trouve, idx_fin = lbl, i + n_mots_lbl
                        break
                if label_trouve:
                    break
            if label_trouve is None:
                continue
            mots_apres = ligne[idx_fin:]
            valeurs = _regrouper_nombres(mots_apres)
            if len(valeurs) >= 2:
                resultats[champ] = dict(valeur_courante=valeurs[0], valeur_precedente=valeurs[1],
                                        ligne_source=" ".join(m["texte"] for m in ligne))
            elif len(valeurs) == 1:
                resultats[champ] = dict(valeur_courante=valeurs[0], valeur_precedente=None,
                                        ligne_source=" ".join(m["texte"] for m in ligne))
            break
    return resultats, annee_c, annee_p


def extraire_pdf(chemin_pdf, ticker, referentiel="syscohada"):
    labels = charger_labels(referentiel)
    toutes_lignes, methodes = [], []
    with pdfplumber.open(chemin_pdf) as pdf:
        for i, page in enumerate(pdf.pages):
            lignes, methode = lire_page_en_lignes(page, i)
            toutes_lignes.extend(lignes)
            methodes.append(methode)

    champs, annee_c, annee_p = extraire_champs(toutes_lignes, labels)
    for champ, v in champs.items():
        if v["valeur_courante"] is not None:
            v["valeur_courante_M_FCFA"] = round(v["valeur_courante"] / 1000, 3)
        if v["valeur_precedente"] is not None:
            v["valeur_precedente_M_FCFA"] = round(v["valeur_precedente"] / 1000, 3)

    return dict(
        ticker=ticker, fichier_source=str(Path(chemin_pdf).name),
        exercice_courant=annee_c, exercice_precedent=annee_p, referentiel=referentiel,
        unite_detectee="milliers_fcfa_convertis_en_millions",
        methode_pages=methodes, champs=champs,
        date_extraction=date.today().isoformat(), statut="A_VERIFIER_HUMAIN",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("pdf")
    p.add_argument("--ticker", required=True)
    p.add_argument("--referentiel", default="syscohada", choices=["syscohada", "bancaire_umoa"])
    p.add_argument("--out", default=None)
    a = p.parse_args()
    prop = extraire_pdf(a.pdf, a.ticker, a.referentiel)
    texte_json = json.dumps(prop, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(texte_json, encoding="utf-8")
        print(f"Proposition ecrite dans {a.out} -- A VERIFIER AVANT TOUTE INTEGRATION.")
    else:
        print(texte_json)
