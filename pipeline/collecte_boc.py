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
PAGE_LISTE = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
SUFFIXES = (2, 1, 3)          # le suffixe observé est _2 ; on essaie les variantes
RECUL_MAX = 12                # jours de repli si la page de publication est injoignable
# boc_20260811_2.pdf — le motif exclut les éditions anglaises boc_eng_AAAAMMJJ_N.pdf
RE_LIEN_BOC = re.compile(r"/sites/default/files/boc_(\d{8})_(\d)\.pdf")
DOSSIER = "donnees"

MOIS = {"janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
        "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}

# une ligne de cotation se termine par une date de dividende de la forme 18-août-25
RE_DATE_DIV = re.compile(r"(\d{1,2}-[a-zéû]{3,5}\.?-\d{2})\s*$", re.I)
# Même motif, sans ancrage de fin : une ligne de cotation porte sa date suivie du
# rendement et du PER, donc RE_DATE_DIV ne la reconnaît pas. Sert uniquement à
# savoir qu'une ligne est déjà la cotation suivante.
RE_DATE_PARTOUT = re.compile(r"\d{1,2}-[a-zéû]{3,5}\.?-\d{2}", re.I)
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


def session_http():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; pipeline-brvm/1.0)"
    return s


def pdf_si_present(s, url):
    """Renvoie le contenu si l'URL sert bien un PDF, sinon None."""
    try:
        r = s.get(url, timeout=45)
    except requests.RequestException:
        return None
    return r.content if (r.status_code == 200 and r.content[:4] == b"%PDF") else None


def url_dernier_publie(s):
    """Lit la page des publications et renvoie l'URL du bulletin le plus récent.

    Toutes les journées ne donnent pas lieu à une séance : jours fériés régionaux,
    fermetures exceptionnelles. Interroger la page évite de deviner ces dates."""
    try:
        r = s.get(PAGE_LISTE, timeout=45)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Page des publications injoignable ({e}) — repli sur les dates.")
        return None
    liens = RE_LIEN_BOC.findall(r.text)
    if not liens:
        print("Aucun lien de bulletin reconnu sur la page — repli sur les dates.")
        return None
    aaaammjj, n = max(liens)
    return URL.format(aaaammjj=aaaammjj, n=n)


def telecharge(jour=None):
    """Contenu du PDF : la séance demandée, ou le dernier bulletin publié."""
    s = session_http()

    if jour is None:
        url = url_dernier_publie(s)
        if url:
            contenu = pdf_si_present(s, url)
            if contenu:
                print(f"Dernier bulletin publié : {url}")
                return contenu
            print(f"{url} annoncé mais illisible — repli sur les dates.")
        # repli : on remonte les jours ouvrés jusqu'à trouver une séance
        essai = date.today()
        for _ in range(RECUL_MAX):
            if essai.weekday() < 5:
                for n in SUFFIXES:
                    u = URL.format(aaaammjj=essai.strftime("%Y%m%d"), n=n)
                    contenu = pdf_si_present(s, u)
                    if contenu:
                        print(f"BOC trouvé en remontant : {u}")
                        return contenu
            essai -= timedelta(days=1)
        raise SystemExit(f"Aucun bulletin trouvé sur les {RECUL_MAX} derniers jours.")

    erreurs = []
    for n in SUFFIXES:
        url = URL.format(aaaammjj=jour.strftime("%Y%m%d"), n=n)
        contenu = pdf_si_present(s, url)
        if contenu:
            print(f"BOC téléchargé : {url}")
            return contenu
        erreurs.append(url)
    raise SystemExit(
        f"Aucun bulletin pour le {jour.isoformat()} : séance non tenue, ou bulletin "
        f"pas encore publié.\n  " + "\n  ".join(erreurs))


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

    valeurs, reparations, compartiment = [], [], None
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
            # Une valeur qui n'a encore payé aucun dividende — une première
            # cotation, typiquement — n'a pas de date sur sa ligne. L'ancrage
            # habituel la laisserait passer sans bruit.
            intro = ligne_sans_dividende(champs)
            if intro is None:
                continue
            sym, titre = intro["symbole"], intro["titre"]
            prec, ouv, clot, varj = intro["prec"], intro["ouv"], intro["clot"], intro["varj"]
            vol, val, ref = intro["vol"], intro["val"], intro["ref"]
            vara = divm = None
            apres = []
        else:
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

        # Une valeur transigée trop large pour sa colonne est renvoyée à la ligne
        # par pdftotext : « 1 389 733 920 » devient « 1 389 733 » suivi de « 920 »
        # sur la ligne d'après. Le montant tronqué reste un nombre valide, donc
        # rien ne le signale — sauf le cours qu'il implique.
        val, repare = recoud_valeur(val, vol, (prec, ouv, clot), bloc[i + 1:i + 4])
        if repare:
            reparations.append((sym, repare, val))

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
            dividende_date=date_div(m_date.group(1)) if m_date else None,
            rendement_net=rdt, per=per))

    for sym, tronque, entier in reparations:
        print(f"  valeur recousue  {sym:6s} {tronque:>15,} -> {entier:>18,}".replace(",", " "))
    return valeurs


def cours_implicite_plausible(val, vol, cours):
    """La valeur transigée divisée par le volume doit retomber près des cours du jour."""
    if not vol or val is None:
        return True
    reels = [c for c in cours if c]
    if not reels:
        return True
    moyen = val / vol
    return min(reels) * 0.5 <= moyen <= max(reels) * 2


def recoud_valeur(val, vol, cours, suites):
    """Rattache le fragment renvoyé à la ligne, et seulement s'il rétablit la cohérence.

    On ne rafistole jamais à l'aveugle : le montant recousu n'est retenu que si le
    cours qu'il implique rentre dans la fourchette des cours du jour, alors que le
    montant tronqué en sortait. Ce contrôle valide l'ordre de grandeur, pas les
    trois derniers chiffres : c'est la réconciliation de la valeur totale avec le
    bulletin qui les confirme, et qui échouerait si le fragment était le mauvais.
    """
    if cours_implicite_plausible(val, vol, cours):
        return val, None
    for frag in fragments_suivants(suites):
        candidat = val * 1000 + int(frag)
        if cours_implicite_plausible(candidat, vol, cours):
            return candidat, val
    return val, None


def fragments_suivants(suites):
    """Groupes de milliers isolés sur les lignes qui suivent celle du titre.

    Le fragment ne se présente pas seul : la ligne suivante porte aussi le code
    secteur, et parfois la fin d'un libellé trop long. On examine donc les champs
    de la ligne, pas la ligne entière, et on ne retient que ceux faits d'exactement
    trois chiffres — un numéro de page, à un ou deux chiffres, ne peut pas être
    happé. Le balayage s'arrête à la cotation suivante, reconnue à sa date de
    dividende, pour ne pas aller puiser dans le titre d'après.
    """
    frags = []
    for ligne in suites:
        if RE_DATE_PARTOUT.search(ligne):
            break
        champs = [c.strip() for c in re.split(r"\s{2,}", ligne.strip()) if c.strip()]
        frags += [c for c in champs if re.fullmatch(r"\d{3}", c)]
    return frags


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


def ligne_sans_dividende(champs):
    """Cotation d'une valeur qui n'a encore payé aucun dividende.

    C'est le cas d'une première cotation : la colonne « Dernier dividende payé »
    est vide, donc la ligne ne porte aucune date et l'ancrage habituel ne la voit
    pas. On se rabat sur la variation du jour — premier champ en pourcentage de la
    ligne — dont la position dans le tableau est tout aussi fixe : les trois cours
    la précèdent, le volume et la valeur transigée la suivent.

    Renvoie None dès que la forme s'écarte de celle attendue : mieux vaut laisser
    la réconciliation échouer que fabriquer une ligne mal alignée.
    """
    sym = champs[0].strip() if champs else ""
    if not re.match(r"^[A-Z]{3,6}$", sym):
        return None
    pc = next((k for k, c in enumerate(champs) if c.strip().endswith("%")), None)
    if pc is None or pc < 5:          # symbole, titre, puis les trois cours au minimum
        return None
    varj = nombre(champs[pc])
    cours = [nombre(c) for c in champs[pc - 3:pc]]
    suite = [nombre(c) for c in champs[pc + 1:pc + 4]]
    if varj is None or any(v is None for v in cours):
        return None
    if len(suite) < 2 or any(v is None for v in suite[:2]):
        return None
    return dict(symbole=sym, titre=" ".join(champs[1:pc - 3]).strip(),
                prec=cours[0], ouv=cours[1], clot=cours[2], varj=varj,
                vol=suite[0], val=suite[1],
                ref=suite[2] if len(suite) > 2 else None)


def roster_carnet(txt):
    """Symboles listés au carnet d'ordres du marché des actions, en fin de bulletin.

    Le carnet recense toute la cote, y compris les valeurs qui n'ont pas traité.
    Il sert de liste de contrôle : un symbole qui y figure mais qu'on n'a pas
    extrait du tableau de cotation est soit suspendu, soit une ligne perdue.
    """
    i = txt.rfind("MARCHE DES ACTIONS")          # la dernière occurrence est le carnet
    if i < 0:
        return set()
    fin = txt.find("MARCHE DES DROITS", i)
    bloc = txt[i:fin if fin > 0 else None]
    return set(re.findall(r"^\s*([A-Z]{3,6})\s{2,}\S", bloc, re.M))


def lignes_brutes(txt, symboles):
    """Lignes du bulletin qui portent l'un des symboles donnés, telles quelles.

    Un écart nommé sans sa ligne oblige à rouvrir le PDF, donc à attendre une
    séance de plus pour corriger. La ligne brute, elle, dit immédiatement
    pourquoi l'extraction l'a laissée passer.
    """
    trouvees = []
    for ligne in txt.split("\n"):
        tete = ligne.strip()[:8]
        for s in symboles:
            if tete.startswith(s):
                trouvees.append((s, ligne.rstrip()))
                break
    return trouvees


def diagnostiquer(txt, valeurs, tot):
    """Quand les totaux ne tombent pas, dire ce qui manque et où le chercher.

    Sans cela, un écart de plusieurs centaines de millions n'indique rien : il
    faut rouvrir le PDF à la main. Les indices ci-dessous suffisent en général
    à nommer la ligne fautive — et à la montrer.
    """
    lignes = []

    def dire(s):
        print(s)
        lignes.append(s)

    dv = (tot.get("volume") or 0) - sum(v["volume"] for v in valeurs)
    dval = (tot.get("valeur") or 0) - sum(v["valeur"] for v in valeurs)
    if dv or dval:
        dire(f"\n  Manquant : {dv:,} titres et {dval:,} FCFA".replace(",", " "))
        if dv:
            moyen = dval / dv
            dire(f"  Cours moyen implicite : {moyen:,.2f} FCFA".replace(",", " ")
                 + ("  — un cours entier désigne une ligne unique perdue"
                    if abs(moyen - round(moyen)) < 0.01 else ""))

    absents = sorted(roster_carnet(txt) - {v["symbole"] for v in valeurs})
    if absents:
        dire("  Au carnet d'ordres mais pas dans le tableau de cotation : "
             + ", ".join(absents))
        dire("  (une valeur non traitée ce jour-là y figure légitimement : le tableau"
             " de cotation ne recense que les valeurs qui ont transigé)")
        brutes = lignes_brutes(txt, absents)
        if brutes:
            dire("  Lignes du bulletin portant ces symboles, telles que pdftotext les rend :")
            for s, l in brutes:
                dire(f"    [{s}] {l!r}")
        else:
            dire("  Aucune ligne du bulletin ne commence par ces symboles : ils ne"
                 " figurent qu'au carnet, donc n'ont pas traité.")

    nuls = [v["symbole"] for v in valeurs if not v["volume"]]
    if nuls:
        dire("  Lignes extraites à volume nul : " + ", ".join(nuls))

    # Le journal du workflow défile ; le fichier, lui, se relit et se joint.
    try:
        os.makedirs(DOSSIER, exist_ok=True)
        with open(os.path.join(DOSSIER, "diagnostic_boc.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
        print(f"  Diagnostic écrit dans {os.path.join(DOSSIER, 'diagnostic_boc.txt')}")
    except OSError as e:
        print(f"  (diagnostic non écrit : {e})")
    return absents


# Nombre de lignes manquantes au-delà duquel on préfère bloquer : un format qui
# change casse bien plus de lignes qu'une introduction en bourse.
LIGNES_MANQUANTES_MAX = 3
# Part de la séance qu'on accepte de perdre quand PLUSIEURS lignes manquent. Une
# ligne unique est publiée quel que soit son poids : à la BRVM, une seule valeur
# très liquide emporte couramment l'essentiel du volume d'une séance — ETIT en a
# porté 90 % le 10 août 2026 — et son absence, nommée, ne fausse pas les autres.
PART_MANQUANTE_MAX = 0.60


def ecart_par_manque(txt, valeurs, tot, rapport):
    """L'écart s'explique-t-il par des lignes absentes plutôt que par des chiffres faux ?

    Les deux cas n'appellent pas la même conduite. Des chiffres faux — une valeur
    transigée mal recousue, une variation qui ne retombe pas sur ses cours — sont
    une extraction à jeter : publier reviendrait à afficher des cours inventés.
    Des lignes absentes, au contraire, laissent intactes celles qui ont été lues :
    la bonne conduite est de publier les 47 justes en nommant la 48e qui manque,
    et non de priver le tableau de bord d'une séance entière.

    Limite connue, assumée : une ligne légitimement absente masque l'écart qu'une
    AUTRE ligne mal lue aurait produit. Les deux écarts s'additionnent dans le même
    total et rien ne les sépare, faute de connaître le volume du titre absent. Le
    rempart restant est la cohérence interne de chaque ligne lue, et la séance est
    alors publiée sous la mention « réconciliation BOC en échec » — jamais présentée
    comme certifiée. Le cours implicite du manque est journalisé pour que l'anomalie
    se voie : un cours hors de la cote trahit une seconde cause.

    Renvoie (oui, absents, motif).
    """
    coherence = {r["controle"]: r for r in rapport}
    # Ces deux contrôles ne comparent pas au bulletin : ils vérifient que chaque
    # ligne lue se tient toute seule. S'ils passent, ce qui a été lu est juste.
    for cle in ("coherence_valeur_volume", "variation_jour_recalculee"):
        r = coherence.get(cle)
        if r and not r["concorde"]:
            return False, [], f"{cle} en échec : les lignes lues sont elles-mêmes fausses"

    manquants = {}
    for cle in ("volume", "valeur", "titres"):
        r = coherence.get(cle)
        if not r or r["concorde"]:
            continue
        if r["calcule"] > r["bulletin"]:
            return False, [], (f"{cle} : {r['calcule']:,} lus pour {r['bulletin']:,} annoncés — "
                               "un excédent ne s'explique pas par une ligne oubliée"
                               ).replace(",", " ")
        manquants[cle] = r["bulletin"] - r["calcule"]

    if not manquants:
        return False, [], "aucun écart par défaut à expliquer"

    absents = sorted(roster_carnet(txt) - {v["symbole"] for v in valeurs})
    if not absents:
        return False, [], ("écart sans porteur : aucun symbole du carnet ne manque au "
                           "tableau, donc l'écart vient d'une ligne mal lue")

    n = manquants.get("titres")
    if n is None:
        return False, [], ("le nombre de titres transigés concorde alors que les volumes "
                           "non : une ligne a donc été lue avec un mauvais volume")
    if n > LIGNES_MANQUANTES_MAX:
        return False, [], f"{n} lignes manquantes : trop pour une omission ponctuelle"
    if n > len(absents):
        return False, [], (f"{n} lignes manquantes pour seulement {len(absents)} symbole(s) "
                           "absent(s) du tableau : le compte ne se fait pas")

    if n > 1:
        for cle in ("volume", "valeur"):
            if cle in manquants and tot.get(cle):
                part = manquants[cle] / tot[cle]
                if part > PART_MANQUANTE_MAX:
                    return False, [], (f"{n} lignes manquantes emportant {part:.0%} du {cle} "
                                       "de la séance : c'est le format qui a changé")

    # Le cours que le manque implique : hors de la cote, il désigne une seconde cause.
    implicite = ""
    dv, dval = manquants.get("volume"), manquants.get("valeur")
    if dv and dval:
        cours = [v["cloture"] for v in valeurs if v["cloture"]]
        m = dval / dv
        borne = "" if not cours or min(cours) / 2 <= m <= max(cours) * 2 else \
                " — hors de la fourchette de la cote, donc suspect"
        implicite = f" ; cours implicite du manque {m:,.0f} FCFA{borne}".replace(",", " ")
    return True, absents, (f"{n} ligne(s) non lue(s) parmi {', '.join(absents)} ; "
                           "les lignes extraites sont cohérentes entre elles" + implicite)


# Contrôles bloquants : une divergence signale une extraction fausse.
# Le dénombrement hausse/baisse/inchangé est seulement indicatif — la BRVM le
# calcule sur le cours de référence, ajusté les jours de détachement de dividende
# ou d'opération sur titres, alors que la colonne « Variation jour » du bulletin
# se rapporte au cours précédent. Les deux bases divergent alors d'un titre ou deux.
BLOQUANTS = ("volume", "valeur", "titres", "variation_jour_recalculee",
             "coherence_valeur_volume")


def indices(txt):
    """Niveaux et variations des trois indices, lus en tête de première page.

    Les trois blocs sont côte à côte sur la même ligne : on lit donc les
    occurrences dans l'ordre COMPOSITE, 30, PRESTIGE."""
    def suite(motif, n):
        m = re.search(motif, txt)
        if not m:
            return [None] * n
        # l'espace ne sépare les milliers que suivi de trois chiffres, sinon le
        # « 30 » du libellé « BRVM 30 » se collerait au niveau qui suit
        vals = re.findall(r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})*,\d+", m.group(0))
        return [nombre(v) for v in (vals + [None] * n)[:n]]

    niveaux = suite(r"BRVM COMPOSITE.*", 3)
    jour = suite(r"Variation Jour.*", 3)
    annuel = suite(r"Variation annuelle.*", 3)
    noms = ["composite", "brvm30", "prestige"]
    return {noms[i]: dict(niveau=niveaux[i], variation_jour=jour[i],
                          variation_annuelle=annuel[i]) for i in range(3)}


def controle(valeurs, tot):
    """Réconcilie les lignes extraites avec la page de synthèse du bulletin."""
    calc = dict(volume=sum(v["volume"] for v in valeurs),
                valeur=sum(v["valeur"] for v in valeurs),
                titres=len(valeurs),
                hausse=sum(1 for v in valeurs if v["variation_jour"] > 0),
                baisse=sum(1 for v in valeurs if v["variation_jour"] < 0),
                inchange=sum(1 for v in valeurs if v["variation_jour"] == 0))
    rapport = []
    for cle, attendu in tot.items():
        if cle not in calc or attendu is None:
            continue
        rapport.append(dict(controle=cle, calcule=calc[cle], bulletin=attendu,
                            concorde=calc[cle] == attendu, bloquant=cle in BLOQUANTS))
    # cohérence de chaque valeur transigée avec son volume
    incoherents = [v["symbole"] for v in valeurs
                   if not cours_implicite_plausible(v["valeur"], v["volume"],
                                                    (v["cours_precedent"], v["ouverture"],
                                                     v["cloture"]))]
    rapport.append(dict(controle="coherence_valeur_volume",
                        calcule=len(valeurs) - len(incoherents), bulletin=len(valeurs),
                        concorde=not incoherents, bloquant=True,
                        titres_en_ecart=incoherents))

    # variations du jour recalculées depuis le cours précédent
    ecarts = [v["symbole"] for v in valeurs
              if abs((v["cloture"] - v["cours_precedent"]) / v["cours_precedent"] * 100
                     - v["variation_jour"]) > 0.05]
    rapport.append(dict(controle="variation_jour_recalculee", calcule=len(valeurs) - len(ecarts),
                        bulletin=len(valeurs), concorde=not ecarts, bloquant=True,
                        titres_en_ecart=ecarts))
    ok = all(r["concorde"] for r in rapport if r["bloquant"])
    return rapport, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="séance précise au format AAAA-MM-JJ ; "
                                    "sans cette option, le dernier bulletin publié")
    ap.add_argument("--pdf", help="PDF local, sans téléchargement")
    ap.add_argument("--sortie", default=os.path.join(DOSSIER, "boc.json"))
    a = ap.parse_args()

    if a.pdf:
        chemin, tmp = a.pdf, None
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(telecharge(date.fromisoformat(a.date) if a.date else None)); tmp.close()
        chemin = tmp.name

    txt = texte_pdf(chemin)
    numero, jour_iso = entete(txt)
    valeurs = lignes_actions(txt)
    tot = totaux(txt)
    idx = indices(txt)
    rapport, ok = controle(valeurs, tot)

    print(f"BOC n° {numero} — séance du {jour_iso} — {len(valeurs)} valeurs extraites")
    for nom, v in idx.items():
        print(f"  indice {nom:10s} {v['niveau']}  jour {v['variation_jour']} %  "
              f"annuel {v['variation_annuelle']} %")
    for r in rapport:
        if r["concorde"]:
            marque = "OK   "
        else:
            marque = "ECART" if r["bloquant"] else "note "
        print(f"  {marque} {r['controle']:28s} "
              f"{r['calcule']:>15,} / {r['bulletin']:>15,}".replace(",", " "))
    indic = [r for r in rapport if not r["bloquant"] and not r["concorde"]]
    if indic:
        print("  note  Le dénombrement hausse/baisse du bulletin se rapporte au cours de")
        print("        référence, ajusté les jours de détachement de dividende ou")
        print("        d'opération sur titres. L'écart est attendu ces jours-là et")
        print("        n'affecte ni les cours ni les volumes extraits.")

    absents, motif, publiable = [], "", ok
    if not ok:
        rates = [r["controle"] for r in rapport if r["bloquant"] and not r["concorde"]]
        for r in rapport:
            if r.get("titres_en_ecart"):
                print("  titres en cause : " + ", ".join(r["titres_en_ecart"]))
        diagnostiquer(txt, valeurs, tot)
        publiable, absents, motif = ecart_par_manque(txt, valeurs, tot, rapport)

    os.makedirs(os.path.dirname(a.sortie) or ".", exist_ok=True)
    json.dump(dict(numero=numero, seance=jour_iso, source="brvm.org",
                   synthese=tot, indices=idx, controles=rapport, reconcilie=ok,
                   publiable=publiable, lignes_absentes=absents, motif_ecart=motif,
                   valeurs=valeurs),
              open(a.sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{a.sortie} écrit.")
    if tmp:
        os.unlink(tmp.name)

    if ok:
        return
    if publiable:
        # Une valeur nouvellement introduite, ou dont la ligne s'écarte de la mise
        # en page habituelle, ne doit pas priver les 47 autres de leur séance. On
        # publie ce qui est lu, on nomme ce qui manque, et rien n'est inventé :
        # le titre absent reste absent du tableau de bord.
        print("\n  ATTENTION — séance publiée sans réconciliation complète.")
        print(f"  Motif : {motif}")
        print("  Les lignes extraites sont cohérentes entre elles ; le tableau de bord")
        print("  affichera « réconciliation BOC en échec » et le ou les titres absents")
        print("  n'y figureront pas, plutôt que d'y figurer avec des chiffres devinés.")
        return
    sys.exit("Réconciliation en échec sur : " + ", ".join(rates)
             + f"\nÉcart non attribuable à une ligne absente ({motif})."
             + "\nLe format du bulletin a probablement changé ; rien n'a été publié.")


if __name__ == "__main__":
    main()
