#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Releve de la page HTML « Volumes / Valeurs » de la BRVM — SECONDE SOURCE.

    python collecte_volumes.py                  # releve la page, ajoute au CSV
    python collecte_volumes.py --diagnostic     # decrit la structure, n'ecrit rien
    python collecte_volumes.py --html f.html    # depuis un HTML deja telecharge

POURQUOI CE RELEVEUR EXISTE (chantier C25). Tout ce que le depot sait des cours,
du PER et du rendement vient d'UN SEUL document — le bulletin officiel en PDF —
lu par UN SEUL analyseur, collecte/extracteur_boc.py. Une erreur d'extraction du
PDF est aujourd'hui invisible tant qu'elle ne produit pas une valeur absurde. La
page brvm.org/fr/volumes/0 publie les memes nombres en HTML, par une autre
chaine : une divergence entre les deux ne peut venir que de l'une des deux, et
c'est exactement la preuve a deux cotes que la doctrine du depot exige.

CE QU'IL NE FAIT PAS. Il n'ecrit jamais dans les tables existantes et ne corrige
jamais rien. Il depose un releve horodate dans collecte/releve_volumes.csv ; la
confrontation, elle, est un test (section 27 de moteur/tester_donnees.py), et une
divergence y est un SIGNALEMENT : c'est l'inspection qui dit laquelle des deux
sources a tort.

TROIS GARDE-FOUS, chacun contre une erreur deja faite dans ce depot.

1. IL ECHOUE BRUYAMMENT, JAMAIS EN RENDANT UNE TABLE VIDE. Un analyseur HTML
   casse a la premiere refonte du site, en silence. Toute sortie de ce script est
   soit >= LIGNES_MINIMUM lignes, soit une exception. C'est le faux vert que la
   section 19 portait avant C15 : verte parce qu'elle ne confrontait rien.

2. LA COLONNE DES TICKERS EST RECONNUE PAR SON CONTENU, PAS PAR SON EN-TETE.
   Sur les pages de la BRVM le mot « Valeur » designe tantot le nom du titre,
   tantot le montant echange en FCFA : se fier a l'en-tete, c'est se tromper de
   colonne un jour sans le voir. On cherche donc la colonne dont les cellules
   sont des tickers de la cote (>= PART_TICKERS_MINIMUM), ce qui se verifie tout
   seul. Les colonnes de nombres, elles, sont nommees par leur en-tete, et une
   colonne de nombres non reconnue est DECRITE dans le diagnostic plutot que
   rangee au hasard.

3. LA DATE DE SEANCE EST LUE DANS LA PAGE, JAMAIS SUPPOSEE. La page porte
   l'intraday : a 19h30 elle peut publier une seance que le bulletin n'a pas
   encore arretee. Confronter « le dernier des deux » comparerait deux jours
   differents — l'erreur exacte que C15 a du defaire. Sans date lisible dans la
   page, le script echoue.

Dependances : requests, beautifulsoup4.
"""
import argparse, csv, os, re, sys, unicodedata
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://www.brvm.org/fr/volumes/0"
SORTIE = os.path.join("collecte", "releve_volumes.csv")
COLONNES = ["date_seance", "ticker", "cours", "volume", "valeur", "releve_le", "source"]

# Une seance de la cote porte 40 a 47 lignes. En dessous de 30, la page n'est pas
# celle qu'on croit, ou l'analyseur n'en lit qu'un morceau : on echoue.
LIGNES_MINIMUM = 30
# Part des cellules d'une colonne qui doivent etre des tickers connus pour que la
# colonne soit reconnue comme celle des tickers.
PART_TICKERS_MINIMUM = 0.80
# Une date de seance plus vieille que cela, c'est une page de cache ou une archive.
ECART_DATE_MAX_JOURS = 15

# Les 47 tickers de la cote, tels que le depot les ecrit. Sert UNIQUEMENT a
# reconnaitre la colonne des tickers ; un ticker nouveau n'est pas rejete, il
# fait seulement baisser la part mesuree.
TICKERS = {
    "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOABF", "BOAC", "BOAM", "BOAN",
    "BOAS", "CABC", "CBIBF", "CFAC", "CIEC", "ECOC", "ETIT", "FTSC", "LNBB",
    "NEIC", "NSBC", "NTLC", "ONTBF", "ORAC", "ORGT", "PALC", "PRSC", "SAFC",
    "SCRC", "SDCC", "SDSC", "SEMC", "SGBC", "SHEC", "SIBC", "SICC", "SIVC",
    "SLBC", "SMBC", "SNTS", "SOGC", "SPHC", "STAC", "STBC", "TTLC", "TTLS",
    "UNLC", "UNXC",
}

# En-tetes acceptes pour chaque colonne de nombres, normalises (sans accents,
# minuscules, espaces reduits). Une colonne de nombres dont l'en-tete n'est dans
# aucune de ces listes est signalee, pas rangee.
EN_TETES = {
    "cours": ("cours", "cours de cloture", "cours cloture", "cours du jour",
              "cours (fcfa)", "clôture", "cloture", "dernier cours",
              "cours de reference", "prix"),
    "volume": ("volume", "volumes", "titres echanges", "quantite",
               "nombre de titres", "volume echange", "volume (titres)"),
    "valeur": ("valeur transigee", "valeurs transigees", "valeur echangee",
               "montant", "montant echange", "valeur (fcfa)", "capitaux",
               "valeur transaction", "transactions"),
    "per": ("per", "p/e", "pe", "per (x)"),
    "rendement": ("rendement", "rendement (%)", "taux de rendement",
                  "rendement net", "dividend yield"),
}

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
    return sans_accent(net(t)).lower().strip(" :.*")


def nombre(t):
    """Rend (valeur, decimales_publiees) ou (None, None).

    Le nombre de decimales est retourne parce que la granularite publiee de
    chaque cote doit etre MESUREE avant qu'un seuil de confrontation soit fixe :
    deux sources qui arrondissent differemment divergent sans qu'aucune ait tort.
    """
    if t is None:
        return None, None
    s = net(t).replace(" ", "").replace("%", "").replace("+", "")
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


def date_de_seance(texte):
    """Lit la date de seance dans le texte de la page. Echoue si elle n'y est pas."""
    t = sans_accent(net(texte)).lower()
    candidates = []
    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t):
        j, mo, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        candidates.append((m.start(), a, mo, j))
    for m in re.finditer(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", t):
        candidates.append((m.start(), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    motif_mois = r"\b(\d{1,2})\s+(" + "|".join(MOIS) + r")\s+(20\d{2})\b"
    for m in re.finditer(motif_mois, t):
        candidates.append((m.start(), int(m.group(3)), MOIS[m.group(2)], int(m.group(1))))

    aujourdhui = date.today()
    valides = []
    for pos, a, mo, j in candidates:
        try:
            d = date(a, mo, j)
        except ValueError:
            continue
        ecart = (aujourdhui - d).days
        if -1 <= ecart <= ECART_DATE_MAX_JOURS:
            valides.append((ecart, pos, d))
    if not valides:
        vues = sorted({"%04d-%02d-%02d" % (a, mo, j) for _, a, mo, j in candidates})
        raise PageInattendue(
            "aucune date de seance plausible dans la page (ecart tolere : -1 a "
            + str(ECART_DATE_MAX_JOURS) + " jours) ; dates vues : "
            + (", ".join(vues[:12]) if vues else "aucune"))
    # La plus recente ; a egalite, la premiere rencontree dans la page.
    valides.sort(key=lambda x: (x[0], x[1]))
    return valides[0][2]


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
        # En-tetes : la premiere ligne faite de <th>, sinon la premiere ligne.
        prem = tb.find("tr")
        en_tetes = ([net(c.get_text(" ")) for c in prem.find_all("th")]
                    if prem and prem.find("th") else [])
        corps = lignes[1:] if en_tetes else lignes
        if not en_tetes:
            en_tetes = lignes[0]
            corps = lignes[1:]
        out.append((en_tetes, corps))
    return out


def colonne_tickers(corps):
    """Rend (indice, part) de la colonne dont les cellules sont des tickers."""
    if not corps:
        return None, 0.0
    largeur = max(len(l) for l in corps)
    meilleur, part_max = None, 0.0
    for i in range(largeur):
        vues = [l[i] for l in corps if i < len(l) and net(l[i])]
        if not vues:
            continue
        bons = sum(1 for v in vues if net(v).upper() in TICKERS)
        part = bons / len(vues)
        if part > part_max:
            meilleur, part_max = i, part
    return meilleur, part_max


def decrire(tbs):
    """Diagnostic imprime a chaque execution : ce que l'analyseur a vu."""
    lignes = ["DIAGNOSTIC DE STRUCTURE : " + str(len(tbs)) + " table(s) dans la page"]
    for n, (en_tetes, corps) in enumerate(tbs):
        idx, part = colonne_tickers(corps)
        lignes.append("  table " + str(n) + " : " + str(len(corps)) + " ligne(s), "
                      + str(len(en_tetes)) + " en-tete(s)")
        lignes.append("    en-tetes : " + " | ".join(en_tetes[:14]))
        lignes.append("    colonne de tickers : "
                      + ("aucune" if idx is None else
                         "indice " + str(idx) + ", part " + ("%.2f" % part)))
        for l in corps[:3]:
            lignes.append("    ligne    : " + " | ".join(l[:14]))
    return "\n".join(lignes)


def analyser(html):
    """Rend (date_seance, releves, rapport). Leve PageInattendue si la page a change."""
    soup = BeautifulSoup(html, "html.parser")
    tbs = tables(soup)
    diag = decrire(tbs)

    retenue = None
    for en_tetes, corps in tbs:
        idx, part = colonne_tickers(corps)
        if idx is not None and part >= PART_TICKERS_MINIMUM and len(corps) >= LIGNES_MINIMUM:
            retenue = (en_tetes, corps, idx, part)
            break
    if retenue is None:
        raise PageInattendue(
            "aucune table ne porte une colonne de tickers a plus de "
            + ("%.0f" % (PART_TICKERS_MINIMUM * 100)) + " % sur au moins "
            + str(LIGNES_MINIMUM) + " lignes.\n" + diag)
    en_tetes, corps, i_ticker, part = retenue

    # Les colonnes de nombres, nommees par leur en-tete. Une colonne de nombres
    # non reconnue est signalee, jamais rangee au hasard.
    champs, inconnues = {}, []
    for i, h in enumerate(en_tetes):
        if i == i_ticker:
            continue
        k = cle(h)
        nom = None
        for cible, synonymes in EN_TETES.items():
            if k in synonymes:
                nom = cible
                break
        valeurs = [nombre(l[i])[0] for l in corps if i < len(l)]
        numerique = sum(1 for v in valeurs if v is not None) >= len(corps) * 0.5
        if nom and nom not in champs:
            champs[nom] = i
        elif numerique:
            inconnues.append(str(i) + " « " + net(h) + " »")

    confrontables = [c for c in ("cours", "per", "rendement") if c in champs]
    if not confrontables:
        raise PageInattendue(
            "la table est reconnue mais aucune colonne confrontable (cours, per, "
            "rendement) n'y est nommee ; en-tetes vus : "
            + " | ".join(en_tetes) + "\n" + diag)

    seance = date_de_seance(soup.get_text(" "))
    maintenant = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    releves, decimales, doublons = [], {}, []
    for l in corps:
        if i_ticker >= len(l):
            continue
        tk = net(l[i_ticker]).upper()
        if tk not in TICKERS:
            continue
        ligne = {"date_seance": seance.isoformat(), "ticker": tk,
                 "releve_le": maintenant, "source": URL}
        for nom in ("cours", "volume", "valeur"):
            i = champs.get(nom)
            v, dec = nombre(l[i]) if i is not None and i < len(l) else (None, None)
            ligne[nom] = "" if v is None else repr(v) if v != int(v) else str(int(v))
            if dec is not None:
                decimales.setdefault(nom, {})
                decimales[nom][dec] = decimales[nom].get(dec, 0) + 1
        if any(r["ticker"] == tk for r in releves):
            doublons.append(tk)
            continue
        releves.append(ligne)

    if len(releves) < LIGNES_MINIMUM:
        raise PageInattendue(
            "seulement " + str(len(releves)) + " ticker(s) releve(s), plancher "
            + str(LIGNES_MINIMUM) + " : l'analyseur ne lit qu'un morceau de la "
            "table, ou la page n'est pas celle de la cote.\n" + diag)

    rapport = [diag, "",
               "TABLE RETENUE : colonne de tickers " + str(i_ticker)
               + " (part " + ("%.2f" % part) + "), "
               + str(len(releves)) + " ticker(s) releve(s) pour la seance "
               + seance.isoformat(),
               "  colonnes nommees  : " + ", ".join(
                   n + "=" + str(i) for n, i in sorted(champs.items(), key=lambda x: x[1])),
               "  colonnes de nombres NON reconnues : "
               + (", ".join(inconnues) if inconnues else "aucune"),
               "  confrontables     : " + ", ".join(confrontables)]
    for nom, compte in sorted(decimales.items()):
        detail = ", ".join(str(d) + " dec. : " + str(c) for d, c in sorted(compte.items()))
        rapport.append("  granularite " + nom + " : " + detail)
    if doublons:
        rapport.append("  tickers vus deux fois (premiere occurrence retenue) : "
                       + ", ".join(sorted(set(doublons))))
    return seance, releves, "\n".join(rapport)


def fusionner(releves):
    """Ajoute les releves au CSV. Un re-releve de la MEME seance remplace le
    precedent et le dit ; les seances passees ne sont jamais touchees."""
    anciennes = []
    if os.path.exists(SORTIE):
        with open(SORTIE, encoding="utf-8", newline="") as f:
            anciennes = list(csv.DictReader(f))
    index = {(r["date_seance"], r["ticker"]): r for r in anciennes}
    neuves, remplacees, changees = 0, 0, []
    for r in releves:
        k = (r["date_seance"], r["ticker"])
        vieux = index.get(k)
        if vieux is None:
            neuves += 1
        else:
            remplacees += 1
            for c in ("cours", "volume", "valeur"):
                if (vieux.get(c) or "") != (r.get(c) or ""):
                    changees.append(r["ticker"] + " " + c + " : "
                                    + (vieux.get(c) or "vide") + " -> "
                                    + (r.get(c) or "vide"))
        index[k] = r
    lignes = sorted(index.values(), key=lambda r: (r["date_seance"], r["ticker"]))
    os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
    with open(SORTIE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES)
        w.writeheader()
        for r in lignes:
            w.writerow({c: r.get(c, "") for c in COLONNES})
    return neuves, remplacees, changees, len(lignes)


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
        seance, releves, rapport = analyser(html)
    except PageInattendue as e:
        print("ECHEC : la page n'a pas la structure attendue.", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 1
    print(rapport)

    if a.diagnostic:
        print("\n--diagnostic : aucun fichier ecrit.")
        return 0
    neuves, remplacees, changees, total = fusionner(releves)
    print("\n" + SORTIE + " : " + str(neuves) + " ligne(s) neuve(s), "
          + str(remplacees) + " re-relevee(s), " + str(total) + " au total.")
    if changees:
        print("  valeurs modifiees par le re-releve de la seance "
              + seance.isoformat() + " :")
        for c in changees[:20]:
            print("    " + c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
