#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecte quotidienne du Bulletin Officiel de la Cote de la BRVM.

    python collecte_boc.py                          # BOC du jour
    python collecte_boc.py --date 2026-08-10        # une séance précise
    python collecte_boc.py --pdf chemin/boc.pdf     # depuis un PDF déjà téléchargé

Produit donnees/boc.json : les 47 lignes du marché des actions + les totaux de
synthèse, avec le numéro et la date du bulletin lus dans le document lui-même.

Dépendances : requests, et l'utilitaire pdftotext (paquet poppler-utils).
"""
import argparse, json, os, re, subprocess, sys, tempfile
from datetime import date, timedelta

import requests

URL = "https://www.brvm.org/sites/default/files/boc_{aaaammjj}_{n}.pdf"
SUFFIXES = (2, 1, 3)          # le suffixe observé est _2 ; on essaie les variantes
DOSSIER = "donnees"

MOIS = {"janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
        "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}

# une ligne de cotation se termine par une date de dividende de la forme 18-août-25
RE_DATE_DIV = re.compile(r"(\d{1,2}-[a-zéû]{3,5}\.?-\d{2})\s*$", re.I)
RE_SECTEUR = re.compile(r"^(TEL|FIN|CD|CB|IND|ENE|SPU)$")
RE_NOMBRE = re.compile(r"^-?[\d  \u202f]+(,\d+)?$")


def nombre(txt):
    s = txt.replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace("%", "").strip()
    if s in ("", "-", "–"):
        return None
    s = s.replace(",", ".")
    if s.startswith("."):                      # le BOC écrit « ,92 » pour 0,92
        s = "0" + s
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v == int(v) and "." not in s else v


def date_div(txt):
    m = re.match(r"(\d{1,2})-([a-zéû]{3,5})\.?-(\d{2})", txt, re.I)
    if not m:
        return None
    j, mois, a = int(m.group(1)), m.group(2).lower().rstrip("."), int(m.group(3))
    mo = MOIS.get(mois)
    if not mo:
        return None
    an = 2000 + a if a < 80 else 1900 + a
    return f"{an:04d}-{mo:02d}-{j:02d}"


def telecharge(jour):
    """Renvoie le contenu du PDF du BOC pour la séance demandée."""
    aaaammjj = jour.strftime("%Y%m%d")
    erreurs = []
    for n in SUFFIXES:
        url = URL.format(aaaammjj=aaaammjj, n=n)
        try:
            rep = requests.get(url, timeout=45,
                               headers={"User-Agent": "Mozilla/5.0 (compatible; pipeline-brvm/1.0)"})
            if rep.status_code == 200 and rep.content[:4] == b"%PDF":
                print(f"BOC téléchargé : {url}")
                return rep.content
            erreurs.append(f"{url} -> HTTP {rep.status_code}")
        except requests.RequestException as e:
            erreurs.append(f"{url} -> {e}")
    raise SystemExit("Aucun BOC pour cette date.\n  " + "\n  ".join(erreurs))


def texte_pdf(chemin):
    try:
        return subprocess.run(["pdftotext", "-layout", chemin, "-"],
                              capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        raise SystemExit("pdftotext introuvable : installer poppler-utils.")


def entete(txt):
    """Numéro et date du bulletin, lus en première page."""
    num = re.search(r"N°\s*(\d+)", txt)
    jour = re.search(r"(lundi|mardi|mercredi|jeudi|vendredi)\s+(\d{1,2})\s+([a-zéû]+)\s+(\d{4})", txt, re.I)
    iso = None
    if jour:
        mo = MOIS.get(jour.group(3).lower()[:4].rstrip("."), MOIS.get(jour.group(3).lower()[:3]))
        if mo:
            iso = f"{int(jour.group(4)):04d}-{mo:02d}-{int(jour.group(2)):02d}"
    return (int(num.group(1)) if num else None), iso


def lignes_actions(txt):
    """Extrait les lignes du MARCHE DES ACTIONS (compartiments Prestige et Principal)."""
    debut = txt.find("COMPARTIMENT PRESTIGE")
    if debut < 0:
        raise SystemExit("Bloc « COMPARTIMENT PRESTIGE » introuvable : format du BOC modifié.")
    fin = txt.find("MARCHE DES DROITS", debut)
    bloc = txt[debut:fin if fin > 0 else None].split("\n")

    valeurs, compartiment = [], None
    for i, brute in enumerate(bloc):
        ligne = brute.rstrip()
        if "COMPARTIMENT PRESTIGE" in ligne:
            compartiment = "Prestige"; continue
        if "COMPARTIMENT PRINCIPAL" in ligne:
            compartiment = "Principal"; continue
        if not compartiment or not ligne.strip():
            continue

        champs = re.split(r"\s{2,}", ligne.strip())
        pos = m_date = None
        for k, c in enumerate(champs):
            m = RE_DATE_DIV.search(c.strip())
            if m:
                pos, m_date = k, m
                break
        if pos is None:
            continue
        # « 616 15-sept.-25 » : le montant du dividende précède la date sans double espace
        reste = champs[pos][:m_date.start()].strip()
        avant = champs[:pos] + ([reste] if reste else [])
        apres = champs[pos + 1:]
        if len(avant) < 11:
            continue
        sym = avant[0].strip()
        if not re.match(r"^[A-Z]{3,6}$", sym):
            continue

        # les 9 derniers champs avant la date sont numériques et d'ordre fixe
        chiffres = [nombre(c) for c in avant[-9:]]
        if any(v is None for v in chiffres[:8]):
            continue
        prec, ouv, clot, varj, vol, val, ref, vara, divm = chiffres
        titre = " ".join(avant[1:-9]).strip()

        # « 7,87 % 565,40 » : rendement et PER parfois collés dans un même champ
        rdt = per = None
        queue = " ".join(c.strip() for c in apres if c.strip())
        m_rdt = re.match(r"\s*(-?[\d ,]+?)\s*%", queue)
        if m_rdt:
            rdt = nombre(m_rdt.group(1))
            queue = queue[m_rdt.end():]
        m_per = re.search(r"(-?[\d ]+,\d+|-?\d+)\s*$", queue.strip())
        if m_per:
            per = nombre(m_per.group(1))

        # le code secteur et la suite du libellé figurent sur la ligne suivante
        secteur = None
        for suite in bloc[i + 1:i + 3]:
            jetons = re.split(r"\s{2,}", suite.strip())
            if jetons and RE_SECTEUR.match(jetons[0].strip()):
                secteur = jetons[0].strip()
                if len(jetons) > 1:
                    titre = (titre + " " + " ".join(jetons[1:])).strip()
                break

        valeurs.append(dict(
            symbole=sym, titre=re.sub(r"\s+", " ", titre).replace("''", "'"), secteur=secteur,
            compartiment=compartiment, cours_precedent=prec, ouverture=ouv, cloture=clot,
            variation_jour=varj, volume=vol, valeur=val, cours_reference=ref,
            perf_1er_janvier=vara, dividende_montant=divm,
            dividende_date=date_div(m_date.group(1)), rendement_net=rdt, per=per))
    return valeurs


def totaux(txt):
    """Totaux de la page de synthèse, utilisés comme contrôle de réconciliation."""
    def cherche(motif):
        m = re.search(motif, txt)
        return nombre(m.group(1)) if m else None
    return dict(
        volume=cherche(r"Volume échangé \(Actions & Droits\)\s+([\d\u00a0\u202f ]+?)\s{2,}"),
        valeur=cherche(r"Valeur transigée \(FCFA\) \(Actions & Droits\)\s+([\d\u00a0\u202f ]+?)\s{2,}"),
        titres=cherche(r"Nombre de titres transigés\s+(\d+)\s{2,}"),
        hausse=cherche(r"Nombre de titres en hausse\s+(\d+)\s{2,}"),
        baisse=cherche(r"Nombre de titres en baisse\s+(\d+)\s{2,}"),
        inchange=cherche(r"Nombre de titres inchangés\s+(\d+)\s{2,}"),
        per_moyen=cherche(r"PER moyen du marché\s+\(\*\*\)\s+([\d,]+)"),
        rendement_moyen=cherche(r"Taux de rendement moyen du marché\s+([\d,]+)"))


def controle(valeurs, tot):
    """Réconcilie les lignes extraites avec la page de synthèse du bulletin."""
    calc = dict(volume=sum(v["volume"] for v in valeurs),
                valeur=sum(v["valeur"] for v in valeurs),
                titres=len(valeurs),
                hausse=sum(1 for v in valeurs if v["variation_jour"] > 0),
                baisse=sum(1 for v in valeurs if v["variation_jour"] < 0),
                inchange=sum(1 for v in valeurs if v["variation_jour"] == 0))
    rapport, ok = [], True
    for cle, attendu in tot.items():
        if cle not in calc or attendu is None:
            continue
        concorde = calc[cle] == attendu
        ok &= concorde
        rapport.append(dict(controle=cle, calcule=calc[cle], bulletin=attendu, concorde=concorde))
    # variations du jour recalculées depuis le cours précédent
    ecarts = [v["symbole"] for v in valeurs
              if abs((v["cloture"] - v["cours_precedent"]) / v["cours_precedent"] * 100
                     - v["variation_jour"]) > 0.05]
    rapport.append(dict(controle="variation_jour_recalculee", calcule=len(valeurs) - len(ecarts),
                        bulletin=len(valeurs), concorde=not ecarts))
    return rapport, ok and not ecarts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="séance au format AAAA-MM-JJ")
    ap.add_argument("--pdf", help="PDF local, sans téléchargement")
    ap.add_argument("--sortie", default=os.path.join(DOSSIER, "boc.json"))
    a = ap.parse_args()

    if a.pdf:
        chemin, tmp = a.pdf, None
    else:
        jour = date.fromisoformat(a.date) if a.date else date.today()
        if not a.date:                                  # week-end : dernière séance ouvrée
            while jour.weekday() > 4:
                jour -= timedelta(days=1)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(telecharge(jour)); tmp.close()
        chemin = tmp.name

    txt = texte_pdf(chemin)
    numero, jour_iso = entete(txt)
    valeurs = lignes_actions(txt)
    tot = totaux(txt)
    rapport, ok = controle(valeurs, tot)

    print(f"BOC n° {numero} — séance du {jour_iso} — {len(valeurs)} valeurs extraites")
    for r in rapport:
        print(f"  {'OK   ' if r['concorde'] else 'ECART'} {r['controle']:28s} "
              f"{r['calcule']:>15,} / {r['bulletin']:>15,}".replace(",", " "))

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    json.dump(dict(numero=numero, seance=jour_iso, source="brvm.org",
                   synthese=tot, controles=rapport, reconcilie=ok, valeurs=valeurs),
              open(a.sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{a.sortie} écrit.")
    if tmp:
        os.unlink(tmp.name)
    if not ok:
        sys.exit("Réconciliation en échec : le BOC a probablement changé de format.")


if __name__ == "__main__":
    main()
