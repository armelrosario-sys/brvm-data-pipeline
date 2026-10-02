#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Releve de la page HTML « Volumes / Valeurs » de la BRVM — SECONDE SOURCE.

    python collecte_volumes.py                  # releve la page, ajoute aux CSV
    python collecte_volumes.py --diagnostic     # decrit la structure, n'ecrit rien
    python collecte_volumes.py --html f.html    # depuis un HTML deja telecharge

POURQUOI CE RELEVEUR EXISTE (chantier C25). Tout ce que le depot sait des cours,
du PER et du rendement vient d'UN SEUL document — le bulletin officiel en PDF —
lu par UN SEUL analyseur, collecte/extracteur_boc.py. Une erreur d'extraction du
PDF est aujourd'hui invisible tant qu'elle ne produit pas une valeur absurde. La
page brvm.org/fr/volumes/0 publie une partie des memes nombres en HTML, par une
autre chaine : une divergence entre les deux ne peut venir que de l'une des deux,
et c'est exactement la preuve a deux cotes que la doctrine du depot exige.

CE QUE LA PAGE PUBLIE VRAIMENT, mesure le 02/10/2026 (cycle 14, deux
declenchements reels, HTTP 200, 53 773 octets). Cinq tables :

    0  Top 5     : ticker, cours, variation        (5 lignes)
    1  Flop 5    : ticker, cours, variation        (5 lignes)
    2  Activites du marche : libelle / montant     (6 lignes)
    3  LA COTE   : « Code obligation » (en fait le ticker), nom,
                   nombre de titres echanges, valeur echangee, PER,
                   pourcentage de la valeur globale echangee   (48 lignes)
    4  Synthese  : nombre de societes, capitalisation, variations

Trois consequences, contraires a ce que le chantier C25 supposait :

  - LA PAGE NE PUBLIE PAS LE COURS de la cote. Seuls les dix titres du Top 5 et
    du Flop 5 en portent un. La confrontation des 90 469 cours n'est donc PAS
    possible par cette page.
  - ELLE PUBLIE LE PER des 48 titres. C'est la colonne confrontable, et c'est
    precisement la mesure que Claudia signalait le 01/10.
  - ELLE NE PUBLIE AUCUNE DATE. Verifie des deux cotes : aucune date lisible ni
    dans le texte rendu, ni dans le HTML brut (attributs et scripts compris).

CE QU'IL NE FAIT PAS. Il n'ecrit jamais dans les tables existantes et ne corrige
jamais rien. Il depose un releve horodate dans collecte/releve_volumes.csv ; la
confrontation est un test (section 27 de moteur/tester_donnees.py), et une
divergence y est un SIGNALEMENT : c'est l'inspection qui dit laquelle des deux
sources a tort.

ET IL NE DATE PAS LA SEANCE A SA PLACE. La page ne portant pas de date, la
colonne date_seance reste VIDE et date_seance_source dit « absente de la page ».
Stamper la date du jour serait une estimation pour combler un trou, ce que la
deuxieme regle du depot interdit : une case vide vaut mieux qu'une valeur
approchee. La garantie « ne jamais confronter deux jours differents » passe donc
du releveur au test, qui refuse de confronter une seance qu'il n'a pas etablie.
Le releveur capture pour cela les totaux de marche (releve_volumes_marche.csv) :
la valeur des transactions du jour est l'ancrage a deux cotes qui identifiera la
seance sans la supposer, le jour ou Claudia tranchera la convention.

DEUX GARDE-FOUS, chacun contre une erreur deja faite dans ce depot.

1. IL ECHOUE BRUYAMMENT, JAMAIS EN RENDANT UNE TABLE VIDE. Un analyseur HTML
   casse a la premiere refonte du site, en silence. Toute sortie est soit
   >= LIGNES_MINIMUM lignes, soit une exception avec le diagnostic complet. C'est
   le faux vert que la section 19 portait avant C15 : verte parce qu'elle ne
   confrontait rien.

2. LA COLONNE DES TICKERS EST RECONNUE PAR SON CONTENU, PAS PAR SON EN-TETE.
   La preuve est dans la page elle-meme : l'en-tete de cette colonne est
   « Code obligation » alors qu'elle porte des actions, et le mot « Valeur »
   designe ailleurs tantot le nom du titre, tantot un montant. Se fier aux
   en-tetes, c'etait se tromper de colonne sans le voir. On cherche la colonne
   dont les cellules sont des tickers de la base (>= PART_TICKERS_MINIMUM), ce
   qui se verifie tout seul. Les colonnes de nombres, elles, sont nommees par
   leur en-tete, et une colonne de nombres non reconnue est DECRITE dans le
   diagnostic plutot que rangee au hasard.

Dependances : requests, beautifulsoup4.
"""
import argparse, csv, os, re, sys, unicodedata
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://www.brvm.org/fr/volumes/0"
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join("collecte", "releve_volumes.csv")
SORTIE_MARCHE = os.path.join("collecte", "releve_volumes_marche.csv")
SOCIETES = os.path.join(RACINE, "donnees", "base", "societes.csv")

COLONNES = ["date_releve", "ticker", "connu_en_base", "cours", "per", "volume",
            "valeur", "part_valeur", "date_seance", "date_seance_source",
            "releve_le", "source"]
COLONNES_MARCHE = ["date_releve", "libelle", "valeur", "releve_le", "source"]

# La cote porte 48 lignes au 02/10/2026. En dessous de 30, la page n'est pas
# celle qu'on croit, ou l'analyseur n'en lit qu'un morceau : on echoue.
LIGNES_MINIMUM = 30
# Part des cellules d'une colonne qui doivent etre des tickers de la base pour que
# la colonne soit reconnue comme celle des tickers. La page peut porter un titre
# que la base ignore encore — c'est le cas de BBGC le 02/10/2026 — donc le
# plancher est en dessous de 1.
PART_TICKERS_MINIMUM = 0.80
# Une date de seance plus vieille que cela, c'est une page de cache ou une archive.
ECART_DATE_MAX_JOURS = 15

# Repli si societes.csv est illisible : les 48 tickers vus le 02/10/2026.
TICKERS_REPLI = {
    "ABJC", "BBGCI", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM",
    "BOAN", "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT", "FTSC",
    "LNBB", "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT", "PALC", "PRSC",
    "SAFC", "SCRC", "SDCC", "SDSC", "SEMC", "SGBC", "SHEC", "SIBC", "SICC",
    "SIVC", "SLBC", "SMBC", "SNTS", "SOGC", "SPHC", "STAC", "STBC", "TTLC",
    "TTLS", "UNLC", "UNXC",
}

# En-tetes acceptes pour chaque colonne de nombres, normalises (sans accents,
# minuscules, espaces reduits). Les libelles reellement vus sur la page le
# 02/10/2026 sont marques (vu). Une colonne de nombres dont l'en-tete n'est dans
# aucune de ces listes est signalee, pas rangee.
EN_TETES = {
    "cours": ("cours", "cours de cloture", "cours cloture", "cours du jour",
              "cours (fcfa)", "cloture", "dernier cours", "prix"),
    "per": ("per", "p/e", "pe", "per (x)"),                      # (vu)
    "volume": ("nombre de titres echanges",                      # (vu)
               "volume", "volumes", "titres echanges", "quantite",
               "nombre de titres", "volume echange", "volume (titres)"),
    "valeur": ("valeur echangee",                                # (vu)
               "valeur transigee", "valeurs transigees", "montant",
               "montant echange", "valeur (fcfa)", "capitaux", "transactions"),
    "part_valeur": ("pourcentage de la valeur globale echangee",  # (vu)
                    "pourcentage de la valeur globale", "part de la valeur",
                    "% de la valeur globale echangee"),
    "rendement": ("rendement", "rendement (%)", "taux de rendement",
                  "rendement net", "dividend yield"),
}
# Colonnes que la confrontation peut exploiter. Le releve est refuse si aucune
# n'est nommee : un releve sans rien a confronter ne prouve rien.
CONFRONTABLES = ("cours", "per", "rendement")

MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
        "decembre": 12}


class PageInattendue(RuntimeError):
    """La page n'a pas la structure attendue. Toujours levee avec le diagnostic."""


def sans_accent(t):
    d = unicodedata.normalize("NFKD", t)
    return "".join(c for c in d if not unicodedata.combining(c))


def net(t):
    t = t.replace("\xa0", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip()


def cle(t):
    return sans_accent(net(t)).lower().strip(" :.*%()")


def tickers_connus():
    """Les tickers de donnees/base/societes.csv, hors fictifs de test."""
    try:
        with open(SOCIETES, encoding="utf-8") as f:
            vus = {r["ticker"].strip().upper() for r in csv.DictReader(f)
                   if r.get("ticker")}
    except (OSError, KeyError, csv.Error):
        return set(TICKERS_REPLI)
    vus = {t for t in vus if not t.startswith("TEST_")}
    return vus or set(TICKERS_REPLI)


def nombre(t):
    """Rend (valeur, decimales_publiees) ou (None, None).

    Le nombre de decimales est retourne parce que la granularite publiee de
    chaque cote doit etre MESUREE avant qu'un seuil de confrontation soit fixe :
    deux sources qui arrondissent differemment divergent sans qu'aucune ait tort.
    """
    if t is None:
        return None, None
    s = net(t).replace(" ", "").replace("%", "").replace("+", "")
    s = s.replace("FCFA", "").replace("fcfa", "")
    if s in ("", "-", "--", "–", "—", "n/a", "nd", "ND"):
        return None, None
    # 1 234 567,89 ou 1,234,567.89 : on tranche sur le dernier separateur vu.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None, None
    dec = len(s.split(".")[1]) if "." in s else 0
    return v, dec


def texte_nombre(v):
    if v is None:
        return ""
    return str(int(v)) if v == int(v) else repr(v)


def dates_vues(texte):
    """Toutes les dates lisibles dans un texte, SANS filtre de plausibilite.

    Sert au diagnostic : une page qui ne porte aucune date et une page qui en
    porte une trop vieille sont deux pannes differentes, et la seconde se repare.
    """
    t = sans_accent(net(texte)).lower()
    vues = set()
    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t):
        vues.add((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", t):
        vues.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    motif = r"\b(\d{1,2})\s+(" + "|".join(MOIS) + r")\s+(20\d{2})\b"
    for m in re.finditer(motif, t):
        vues.add((int(m.group(3)), MOIS[m.group(2)], int(m.group(1))))
    out = []
    for a, mo, j in sorted(vues):
        try:
            out.append(date(a, mo, j))
        except ValueError:
            continue
    return out


def date_de_seance(*textes):
    """Rend la date de seance lue dans la page, ou None si elle n'y est pas.

    On balaie le texte rendu PUIS le HTML brut : la BRVM publie selon les pages
    dans un attribut, un <option> ou une variable de script, qu'aucun get_text()
    ne rend. Mesure du 02/10/2026 : la page Volumes / Valeurs n'en porte aucune,
    des deux cotes. On rend None plutot que de lever : la date manquante n'est
    pas un defaut de structure, c'est une propriete de la page, et c'est le test
    qui refuse de confronter une seance non etablie.
    """
    aujourdhui = date.today()
    for texte in textes:
        valides = [d for d in dates_vues(texte)
                   if -1 <= (aujourdhui - d).days <= ECART_DATE_MAX_JOURS]
        if valides:
            return max(valides)
    return None


def tables(soup):
    """Rend la liste des tables de la page, chacune (en_tetes, lignes)."""
    out = []
    for tb in soup.find_all("table"):
        lignes = []
        for tr in tb.find_all("tr"):
            cellules = [net(c.get_text(" ")) for c in tr.find_all(["td", "th"])]
            if cellules:
                lignes.append(cellules)
        if not lignes:
            continue
        prem = tb.find("tr")
        en_tetes = ([net(c.get_text(" ")) for c in prem.find_all("th")]
                    if prem and prem.find("th") else [])
        corps = lignes[1:] if en_tetes else lignes
        if not en_tetes:
            en_tetes = lignes[0]
            corps = lignes[1:]
        out.append((en_tetes, corps))
    return out


def colonne_tickers(corps, connus):
    """Rend (indice, part) de la colonne dont les cellules sont des tickers."""
    if not corps:
        return None, 0.0
    largeur = max(len(l) for l in corps)
    meilleur, part_max = None, 0.0
    for i in range(largeur):
        vues = [l[i] for l in corps if i < len(l) and net(l[i])]
        if not vues:
            continue
        part = sum(1 for v in vues if net(v).upper() in connus) / len(vues)
        if part > part_max:
            meilleur, part_max = i, part
    return meilleur, part_max


def reperes(soup, html):
    """Ce qui permet de retrouver la date de seance quand elle manque."""
    lignes = ["REPERES DE DATE"]
    titre = soup.find("title")
    lignes.append("  <title> : " + (net(titre.get_text(" ")) if titre else "absent"))
    for balise in ("h1", "caption", "legend"):
        vus = [net(e.get_text(" ")) for e in soup.find_all(balise)][:4]
        if vus:
            lignes.append("  <" + balise + "> : " + " / ".join(v[:90] for v in vus))
    opts = [net(o.get_text(" ")) for o in soup.find_all("option")][:8]
    if opts:
        lignes.append("  <option> : " + " / ".join(o[:40] for o in opts))
    d_texte = dates_vues(soup.get_text(" "))
    d_brut = dates_vues(html)
    lignes.append("  dates dans le texte rendu : "
                  + (", ".join(d.isoformat() for d in d_texte[:12]) if d_texte else "aucune"))
    lignes.append("  dates dans le HTML brut   : "
                  + (", ".join(d.isoformat() for d in d_brut[:12]) if d_brut else "aucune"))
    return "\n".join(lignes)


def decrire(tbs, connus):
    """Diagnostic imprime a chaque execution : ce que l'analyseur a vu."""
    lignes = ["DIAGNOSTIC DE STRUCTURE : " + str(len(tbs)) + " table(s) dans la page"]
    for n, (en_tetes, corps) in enumerate(tbs):
        idx, part = colonne_tickers(corps, connus)
        lignes.append("  table " + str(n) + " : " + str(len(corps)) + " ligne(s), "
                      + str(len(en_tetes)) + " en-tete(s)")
        lignes.append("    en-tetes : " + " | ".join(en_tetes[:14]))
        lignes.append("    colonne de tickers : "
                      + ("aucune" if idx is None else
                         "indice " + str(idx) + ", part " + ("%.2f" % part)))
        for l in corps[:2]:
            lignes.append("    ligne    : " + " | ".join(c[:40] for c in l[:14]))
    return "\n".join(lignes)


def totaux_marche(tbs, connus):
    """Les lignes libelle/montant des tables sans colonne de tickers.

    Ces totaux — valeur des transactions du jour, capitalisations, nombre de
    societes — sont l'ANCRAGE A DEUX COTES qui permettra d'identifier la seance
    que la page montre sans la supposer, en la confrontant a
    liquidite_quotidienne. Capture au mieux : leur absence n'est pas un echec.
    """
    out = []
    for en_tetes, corps in tbs:
        idx, part = colonne_tickers(corps, connus)
        if idx is not None and part >= PART_TICKERS_MINIMUM:
            continue
        if len(en_tetes) >= 2 and len(corps) == 1 and len(corps[0]) >= 2:
            # Table de synthese : en-tetes = libelles, unique ligne = valeurs.
            for h, v in zip(en_tetes, corps[0]):
                if net(h) and net(v):
                    out.append((net(h), net(v)))
            continue
        for l in corps:
            if len(l) >= 2 and net(l[0]) and net(l[1]):
                out.append((net(l[0]), net(l[1])))
    return out


def analyser(html):
    """Rend (releves, totaux, rapport). Leve PageInattendue si la page a change."""
    soup = BeautifulSoup(html, "html.parser")
    connus = tickers_connus()
    tbs = tables(soup)
    diag = decrire(tbs, connus) + "\n" + reperes(soup, html)

    retenue = None
    for en_tetes, corps in tbs:
        idx, part = colonne_tickers(corps, connus)
        if idx is not None and part >= PART_TICKERS_MINIMUM and len(corps) >= LIGNES_MINIMUM:
            retenue = (en_tetes, corps, idx, part)
            break
    if retenue is None:
        raise PageInattendue(
            "aucune table ne porte une colonne de tickers a plus de "
            + ("%.0f" % (PART_TICKERS_MINIMUM * 100)) + " % sur au moins "
            + str(LIGNES_MINIMUM) + " lignes.\n" + diag)
    en_tetes, corps, i_ticker, part = retenue

    champs, inconnues = {}, []
    for i, h in enumerate(en_tetes):
        if i == i_ticker:
            continue
        k = cle(h)
        nom = None
        for cible, synonymes in EN_TETES.items():
            if k in [cle(s) for s in synonymes]:
                nom = cible
                break
        valeurs = [nombre(l[i])[0] for l in corps if i < len(l)]
        numerique = sum(1 for v in valeurs if v is not None) >= len(corps) * 0.5
        if nom and nom not in champs:
            champs[nom] = i
        elif numerique:
            inconnues.append(str(i) + " « " + net(h) + " »")

    presentes = [c for c in CONFRONTABLES if c in champs]
    if not presentes:
        raise PageInattendue(
            "la table de la cote est reconnue mais aucune colonne confrontable ("
            + ", ".join(CONFRONTABLES) + ") n'y est nommee ; en-tetes vus : "
            + " | ".join(en_tetes) + "\n" + diag)

    seance = date_de_seance(soup.get_text(" "), html)
    maintenant = datetime.now(timezone.utc).replace(microsecond=0)
    jour = maintenant.date().isoformat()
    horodate = maintenant.isoformat()

    releves, decimales, inconnus_base, doublons = [], {}, [], []
    for l in corps:
        if i_ticker >= len(l):
            continue
        tk = net(l[i_ticker]).upper()
        if not re.fullmatch(r"[A-Z0-9]{3,8}", tk):
            continue
        if tk in [r["ticker"] for r in releves]:
            doublons.append(tk)
            continue
        if tk not in connus:
            inconnus_base.append(tk)
        ligne = {"date_releve": jour, "ticker": tk,
                 "connu_en_base": "oui" if tk in connus else "non",
                 "date_seance": seance.isoformat() if seance else "",
                 "date_seance_source": "page" if seance else "absente de la page",
                 "releve_le": horodate, "source": URL}
        for nom in ("cours", "per", "volume", "valeur", "part_valeur"):
            i = champs.get(nom)
            v, dec = nombre(l[i]) if i is not None and i < len(l) else (None, None)
            ligne[nom] = texte_nombre(v)
            if dec is not None:
                decimales.setdefault(nom, {})
                decimales[nom][dec] = decimales[nom].get(dec, 0) + 1
        releves.append(ligne)

    if len(releves) < LIGNES_MINIMUM:
        raise PageInattendue(
            "seulement " + str(len(releves)) + " ticker(s) releve(s), plancher "
            + str(LIGNES_MINIMUM) + " : l'analyseur ne lit qu'un morceau de la "
            "table, ou la page n'est pas celle de la cote.\n" + diag)

    totaux = [{"date_releve": jour, "libelle": h, "valeur": v,
               "releve_le": horodate, "source": URL}
              for h, v in totaux_marche(tbs, connus)]

    rapport = [diag, "",
               "TABLE DE LA COTE RETENUE : colonne de tickers " + str(i_ticker)
               + " (part " + ("%.2f" % part) + " des cellules sont des tickers de "
               "la base), " + str(len(releves)) + " ticker(s) releve(s)",
               "  colonnes nommees  : " + ", ".join(
                   n + "=" + str(i) for n, i in sorted(champs.items(), key=lambda x: x[1])),
               "  colonnes de nombres NON reconnues : "
               + (", ".join(inconnues) if inconnues else "aucune"),
               "  confrontables     : " + ", ".join(presentes),
               "  date de seance    : " + (seance.isoformat() if seance
                                           else "ABSENTE DE LA PAGE — "
                                           "date_seance laissee vide, jamais supposee")]
    for nom, compte in sorted(decimales.items()):
        detail = ", ".join(str(d) + " dec. : " + str(c) for d, c in sorted(compte.items()))
        rapport.append("  granularite " + nom + " : " + detail)
    if inconnus_base:
        rapport.append("  TICKER(S) QUE LA BASE IGNORE : " + ", ".join(sorted(set(inconnus_base)))
                       + " — releve(s) tel(s) quel(s), jamais ecrit(s) en base")
    if doublons:
        rapport.append("  tickers vus deux fois (premiere occurrence retenue) : "
                       + ", ".join(sorted(set(doublons))))
    rapport.append("  totaux de marche captures : " + str(len(totaux)))
    return releves, totaux, "\n".join(rapport)


def fusionner(chemin, colonnes, lignes, cles):
    """Ajoute des lignes a un CSV. Un re-releve du MEME jour remplace le precedent
    et dit ce qu'il change ; les jours passes ne sont jamais touches."""
    anciennes = []
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8", newline="") as f:
            anciennes = list(csv.DictReader(f))
    index = {tuple(r.get(c, "") for c in cles): r for r in anciennes}
    neuves, remplacees, changees = 0, 0, []
    for r in lignes:
        k = tuple(r.get(c, "") for c in cles)
        vieux = index.get(k)
        if vieux is None:
            neuves += 1
        else:
            remplacees += 1
            for c in colonnes:
                if c in ("releve_le", "source"):
                    continue
                if (vieux.get(c) or "") != (r.get(c) or ""):
                    changees.append(" ".join(k) + " " + c + " : "
                                    + (vieux.get(c) or "vide") + " -> "
                                    + (r.get(c) or "vide"))
        index[k] = r
    ordonnees = sorted(index.values(), key=lambda r: tuple(r.get(c, "") for c in cles))
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes)
        w.writeheader()
        for r in ordonnees:
            w.writerow({c: r.get(c, "") for c in colonnes})
    return neuves, remplacees, changees, len(ordonnees)


def main():
    ap = argparse.ArgumentParser(description="Releve de la page Volumes / Valeurs")
    ap.add_argument("--html", help="analyser un fichier HTML au lieu de la page")
    ap.add_argument("--diagnostic", action="store_true",
                    help="decrire la structure et n'ecrire aucun fichier")
    ap.add_argument("--trace", help="ecrire le HTML recu dans ce fichier")
    a = ap.parse_args()

    if a.html:
        html = open(a.html, encoding="utf-8", errors="replace").read()
        print("Source : " + a.html + " (" + str(len(html)) + " octets)")
    else:
        rep = requests.get(URL, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (compatible; brvm-data-pipeline/C25)"})
        rep.raise_for_status()
        rep.encoding = rep.encoding or "utf-8"
        html = rep.text
        print("Source : " + URL + " — HTTP " + str(rep.status_code) + ", "
              + str(len(html)) + " octets")
    if a.trace:
        open(a.trace, "w", encoding="utf-8").write(html)

    try:
        releves, totaux, rapport = analyser(html)
    except PageInattendue as e:
        print("ECHEC : la page n'a pas la structure attendue.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 1
    print(rapport)

    if a.diagnostic:
        print("\n--diagnostic : aucun fichier ecrit.")
        return 0

    neuves, remplacees, changees, total = fusionner(
        SORTIE, COLONNES, releves, ("date_releve", "ticker"))
    print("\n" + SORTIE + " : " + str(neuves) + " ligne(s) neuve(s), "
          + str(remplacees) + " re-relevee(s), " + str(total) + " au total.")
    for c in changees[:20]:
        print("    " + c)
    if totaux:
        n2, r2, c2, t2 = fusionner(SORTIE_MARCHE, COLONNES_MARCHE, totaux,
                                   ("date_releve", "libelle"))
        print(SORTIE_MARCHE + " : " + str(n2) + " neuve(s), " + str(r2)
              + " re-relevee(s), " + str(t2) + " au total.")
        for c in c2[:10]:
            print("    " + c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
