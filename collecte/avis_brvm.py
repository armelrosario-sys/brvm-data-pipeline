#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/avis_brvm.py — Veille automatique des avis de la BRVM.

POURQUOI (18/09/2026, constat de l'utilisatrice).
Trois informations capitales etaient totalement absentes de l'outil :
  1. SUSPENSIONS DE COTATION — Sucrivoire, SICOR et SONOCO suspendus depuis le
     16/09/2026 pour manquement aux obligations de publication. Le tableau de
     bord continuait de les profiler comme si de rien n'etait, alors qu'un titre
     suspendu ne peut tout simplement plus etre achete ni vendu.
  2. ASSEMBLEES GENERALES EXTRAORDINAIRES — une AGE Sonatel portant un projet de
     FRACTIONNEMENT du titre. C'est l'evenement le plus dangereux pour ce
     pipeline : un fractionnement non enregistre divise le cours sans diviser
     l'historique, et fausse silencieusement toutes les series. Le cas est deja
     documente — Solibra a divise son nominal le 27/09/2024 sans que personne ne
     l'enregistre, et les performances 24 mois du titre en etaient fausses. Le
     controle ajoute a tester_donnees.py a depuis trouve DOUZE cas comparables.
     Sonatel etant le titre le plus liquide de la cote, le rater couterait cher.
  3. PAIEMENTS DE DIVIDENDES — la table dividendes accusait deja un retard
     (dividende NSBC de 768,16 F annonce fin juin et absent des semaines durant).

Le point commun des trois : ce sont des FAITS DATES ET OFFICIELS, publies par la
BRVM elle-meme, qui changent la lecture d'un titre du jour au lendemain. Les
ignorer revient a profiler le passe.

CE QUE CE COLLECTEUR FAIT — ET NE FAIT PAS.
Il enregistre des evenements, il n'interprete pas. Une suspension devient un
drapeau, pas un profil. Un projet de fractionnement devient une alerte a
confirmer, pas un ajustement automatique des cours : ajuster une serie
historique est une operation irreversible qui merite une decision humaine, pas
une regle heuristique.

SOURCES (pages publiques de brvm.org) :
  /fr/marche/avis-et-publications/avis          -> suspensions, reprises, divers
  /fr/emetteurs/type-annonces/convocations-assemblees-generales -> AGO et AGE
  /fr/esv/paiement-de-dividendes                -> dividendes
  /fr/emetteurs/type-annonces/operations-sur-titres -> fractionnements, DPS

Sortie : collecte/avis_brvm.csv  (+ collecte/avis_echecs.jsonl)
Usage :
    python3 collecte/avis_brvm.py              # toutes les rubriques
    python3 collecte/avis_brvm.py --test       # analyseurs sur echantillons, hors ligne
    python3 collecte/avis_brvm.py --pages 5    # limiter la profondeur
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import date

import requests

BASE = "https://www.brvm.org"
ICI = __import__("pathlib").Path(__file__).resolve().parent
SORTIE = ICI / "avis_brvm.csv"
ECHECS = ICI / "avis_echecs.jsonl"
UA = {"User-Agent": "brvm-data-pipeline/1.0 (veille avis; "
                    "https://github.com/armelrosario-sys/brvm-data-pipeline)"}

RUBRIQUES = {
    "AVIS": "/fr/marche/avis-et-publications/avis",
    "ASSEMBLEE": "/fr/emetteurs/type-annonces/convocations-assemblees-generales",
    "DIVIDENDE": "/fr/esv/paiement-de-dividendes",
    "OPERATION": "/fr/emetteurs/type-annonces/operations-sur-titres",
}

# --- Classification des avis. L'ordre COMPTE : le premier motif qui correspond
#     l'emporte, donc les cas les plus specifiques passent en premier.
#     "Reprise" avant "Suspension" : un avis de reprise contient souvent le mot
#     suspension ("levee de la suspension") et serait sinon classe a l'envers.
TYPES = [
    ("REPRISE_COTATION", r"reprise\s+(?:de\s+la\s+)?cotation|lev[ée]e?\s+de\s+la\s+suspension"),
    ("SUSPENSION", r"suspension\s+(?:de\s+la\s+)?cotation"),
    ("FRACTIONNEMENT", r"fractionnement|division\s+(?:du\s+)?(?:la\s+)?(?:valeur\s+)?nominal|"
                       r"split\b|regroupement\s+d['’]actions"),
    ("AUGMENTATION_CAPITAL", r"augmentation\s+de\s+capital|droit\s+pr[ée]f[ée]rentiel|\bDPS\b"),
    ("AGE", r"assembl[ée]e\s+g[ée]n[ée]rale\s+extraordinaire|\bAGE\b"),
    ("AGO", r"assembl[ée]e\s+g[ée]n[ée]rale\s+(?:ordinaire|mixte|annuelle)|\bAGO\b"),
    ("DIVIDENDE_EXCEPTIONNEL", r"dividendes?\s+exceptionnels?"),
    ("DIVIDENDE", r"paiement\s+de\s+dividendes?|mise\s+en\s+paiement"),
    ("RADIATION", r"radiation|retrait\s+de\s+la\s+cote"),
    ("OPA_OPR", r"\bOPA\b|\bOPR\b|offre\s+publique"),
    ("PREMIERE_COTATION", r"premi[eè]re\s+cotation|introduction\s+en\s+bourse"),
    ("RETARD_PUBLICATION", r"manquement|non[- ]respect.{0,40}publication|retard.{0,30}publication"),
]

# Ces types changent la lecture d'un titre et doivent remonter au moteur.
CRITIQUES = {"SUSPENSION", "FRACTIONNEMENT", "AUGMENTATION_CAPITAL", "RADIATION",
             "OPA_OPR", "RETARD_PUBLICATION"}

RE_LIGNE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*\|?\s*([^|\n]{5,200}?)\s*\|?\s*"
    r"\[(?:T[ée]l[ée]charger|Lire|Voir)\]\((https?://[^\)]+)\)", re.I)
RE_DATE_SEULE = re.compile(r"(\d{2}/\d{2}/\d{4})")


def charger_tickers():
    """Correspondance nom BRVM -> ticker, lue depuis peupler.py pour rester
    l'unique source de verite du projet (pas de second dictionnaire a maintenir)."""
    src = (ICI.parent / "moteur" / "peupler.py").read_text(encoding="utf-8")
    m = re.search(r"^SOCIETES\s*=\s*\[(.*?)^\]", src, re.S | re.M)
    table = {}
    if not m:
        return table
    for ligne in m.group(1).split("\n"):
        t = re.match(r'\s*\("([A-Z0-9]+)"\s*,\s*"([^"]+)"', ligne)
        if t:
            nom = t.group(2)
            table[reduire(nom)] = t.group(1)
            sans_parenthese = re.sub(r"\s*\([^)]*\)", "", nom).strip()
            if sans_parenthese and sans_parenthese != nom:
                table[reduire(sans_parenthese)] = t.group(1)
    return table


# Alias necessaires parce que la BRVM n'emploie pas toujours la denomination
# enregistree dans peupler.py. Trois cas mesures au premier test :
#   - SEMC a CHANGE DE NOM : "Eviosys Packaging Siem CI" en base, mais les avis
#     de septembre 2026 disent "SONOCO METAL PACKAGING SIEM CI". A reporter dans
#     peupler.py, sans quoi tous ses avis futurs seront perdus.
#   - "COTE D'IVOIRE" ecrit en toutes lettres la ou la base abrege en "CI".
#   - "SAFCA CI" contre "Safca (Alios Finance CI)" en base.
ALIAS = {
    "sonoco metal packaging siem ci": "SEMC",
    "sonoco metal packaging": "SEMC",
    "bridge bank group cote divoire": "BBGCI",
    "safca ci": "SAFC",
    "safca": "SAFC",
    "agl ci": "SDSC",
    "africa global logistics ci": "SDSC",
    "erium ci": "SIVC",
    "totalenergies marketing ci": "TTLC",
    "totalenergies marketing senegal": "TTLS",
    "nsia banque ci": "NSBC",
}


def reduire(s):
    s = (s or "").lower().strip()
    # la BRVM alterne entre "Cote d'Ivoire" et "CI" dans ses libelles
    s = re.sub(r"c[oô]te\s+d[''’]?\s*ivoire", "ci", s)
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ô", "o"),
                 ("î", "i"), ("ç", "c"), ("û", "u"), ("'", ""), ("’", ""), (".", "")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def ticker_depuis(texte, table):
    """Un avis n'est rattache que si le nom correspond vraiment. Aucune
    devinette : un mauvais rattachement poserait une suspension sur le mauvais
    titre, ce qui serait pire que de n'avoir rien collecte."""
    red = reduire(texte)
    if not red:
        return None
    for nom, tick in ALIAS.items():
        if nom in red:
            return tick
    for nom, tick in table.items():
        if len(nom) >= 4 and nom in red:
            return tick
    # forme "SIGLE : libelle" frequente dans les avis BRVM
    m = re.match(r"\s*([A-Z][A-Z0-9 &'\-]{2,40}?)\s*[:_]", texte)
    if m:
        red2 = reduire(m.group(1))
        for nom, tick in ALIAS.items():
            if nom in red2 or red2 in nom:
                return tick
        for nom, tick in table.items():
            if len(nom) >= 4 and (nom in red2 or red2 in nom):
                return tick
    return None


def classer(titre):
    t = titre or ""
    for nom, motif in TYPES:
        if re.search(motif, t, re.I):
            return nom
    return "AUTRE"


def _texte(reponse):
    html = reponse.text
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<a[^>]+href=[\"'](https?://[^\"']+)[\"'][^>]*>\s*([^<]*)</a>",
                  r"[Télécharger](\1)", html, flags=re.I)
    html = re.sub(r"</t[dh]>", " | ", html, flags=re.I)
    html = re.sub(r"</tr>|</li>|<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#039;", "'"), ("&rsquo;", "'")):
        html = html.replace(a, b)
    return re.sub(r"[ \t]+", " ", html)


def _iso(d):
    j, m, a = d.split("/")
    return f"{a}-{m}-{j}"


def journaliser(obj):
    obj["horodatage"] = date.today().isoformat()
    with ECHECS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def analyser(texte, rubrique, table):
    """Extrait les avis d'une page. Separe du reseau pour etre testable hors ligne."""
    lignes = []
    for d, titre, url in RE_LIGNE.findall(texte):
        titre = titre.strip(" |")
        if len(titre) < 5:
            continue
        typ = classer(titre)
        lignes.append(dict(
            date_avis=_iso(d), rubrique=rubrique, type=typ,
            ticker=ticker_depuis(titre, table), titre=titre[:250],
            url=url, critique="oui" if typ in CRITIQUES else "non"))
    return lignes


def collecter(session, rubrique, chemin, pages, table):
    vus, resultats = set(), []
    for page in range(pages):
        url = BASE + chemin + ("" if page == 0 else f"?page={page}")
        try:
            r = session.get(url, timeout=(10, 30))
            r.raise_for_status()
        except Exception as e:
            journaliser({"rubrique": rubrique, "page": page, "erreur": str(e)[:200]})
            break
        lignes = analyser(_texte(r), rubrique, table)
        nouvelles = [x for x in lignes if x["url"] not in vus]
        for x in nouvelles:
            vus.add(x["url"])
        resultats.extend(nouvelles)
        print(f"  {rubrique:10s} page {page + 1} : {len(lignes)} avis "
              f"({len(nouvelles)} nouveaux)")
        if not nouvelles:
            break
        time.sleep(0.6)
    return resultats


ECHANTILLON = """
| 16/09/2026 | SONOCO METAL PACKAGING SIEM CI : Suspension de la cotation | [Télécharger](https://www.brvm.org/sites/default/files/a1.pdf) |
| 16/09/2026 | SICOR S.A : Suspension de la cotation | [Télécharger](https://www.brvm.org/sites/default/files/a2.pdf) |
| 14/09/2026 | SUCRIVOIRE S.A : Suspension de la cotation | [Télécharger](https://www.brvm.org/sites/default/files/a3.pdf) |
| 10/09/2026 | SONATEL : Convocation Assemblée Générale Extraordinaire - Projet de fractionnement de l'action | [Télécharger](https://www.brvm.org/sites/default/files/a4.pdf) |
| 04/09/2026 | SMB CI : Paiement de dividendes - Exercice 2025 | [Télécharger](https://www.brvm.org/sites/default/files/a5.pdf) |
| 01/09/2026 | SODE CI : Paiement de dividendes - Exercice 2025 | [Télécharger](https://www.brvm.org/sites/default/files/a6.pdf) |
| 04/09/2026 | BRIDGE BANK GROUP COTE D'IVOIRE : Première cotation | [Télécharger](https://www.brvm.org/sites/default/files/a7.pdf) |
| 23/04/2026 | SAFCA CI : Augmentation de capital - Droit préférentiel de souscription | [Télécharger](https://www.brvm.org/sites/default/files/a8.pdf) |
| 16/09/2025 | FILTISAC CI : Paiement de dividendes exercice 2024 et dividendes exceptionnels | [Télécharger](https://www.brvm.org/sites/default/files/a9.pdf) |
| 12/08/2026 | SONOCO METAL PACKAGING SIEM CI : Reprise de la cotation | [Télécharger](https://www.brvm.org/sites/default/files/a10.pdf) |
"""


def autotest():
    """Rejoue les analyseurs sur un echantillon fige, sans reseau. Le garde-fou
    voyage avec le code qu'il protege : un fichier annexe absent avait deja fait
    echouer un premier run de collecteur (notations, 02/08/2026)."""
    table = charger_tickers()
    lignes = analyser(ECHANTILLON, "AVIS", table)
    echecs = []
    if len(lignes) != 10:
        echecs.append(f"{len(lignes)} avis reconnus au lieu de 10")
    attendu = {
        "SONOCO METAL PACKAGING SIEM CI : Suspension de la cotation": "SUSPENSION",
        "SUCRIVOIRE S.A : Suspension de la cotation": "SUSPENSION",
        "SONOCO METAL PACKAGING SIEM CI : Reprise de la cotation": "REPRISE_COTATION",
        "SMB CI : Paiement de dividendes - Exercice 2025": "DIVIDENDE",
        "BRIDGE BANK GROUP COTE D'IVOIRE : Première cotation": "PREMIERE_COTATION",
        "SAFCA CI : Augmentation de capital - Droit préférentiel de souscription":
            "AUGMENTATION_CAPITAL",
        "FILTISAC CI : Paiement de dividendes exercice 2024 et dividendes exceptionnels":
            "DIVIDENDE_EXCEPTIONNEL",
    }
    par_titre = {x["titre"]: x for x in lignes}
    for titre, typ in attendu.items():
        obtenu = par_titre.get(titre, {}).get("type")
        if obtenu != typ:
            echecs.append(f"'{titre[:45]}...' classe {obtenu} au lieu de {typ}")
    # le fractionnement Sonatel doit etre repere ET rattache
    frac = [x for x in lignes if x["type"] == "FRACTIONNEMENT"]
    if len(frac) != 1:
        echecs.append(f"{len(frac)} fractionnement(s) detecte(s) au lieu de 1")
    elif frac[0]["ticker"] != "SNTS":
        echecs.append(f"fractionnement rattache a {frac[0]['ticker']} au lieu de SNTS")
    rattaches = sum(1 for x in lignes if x["ticker"])
    if rattaches < 8:
        echecs.append(f"{rattaches} avis rattaches a un ticker sur 10")

    if echecs:
        print(f"AUTOTEST : {len(echecs)} ECHEC(S)")
        for e in echecs:
            print(f"  - {e}")
        return 1
    print(f"AUTOTEST : analyseurs OK (10 avis, {rattaches} rattaches, "
          f"classification 7/7, fractionnement SNTS detecte)")
    return 0


COLONNES = ["date_avis", "rubrique", "type", "ticker", "critique", "titre", "url",
            "date_collecte"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="analyseurs hors ligne")
    ap.add_argument("--pages", type=int, default=4,
                    help="pages par rubrique (4 couvre environ 3 mois)")
    args = ap.parse_args()
    if args.test:
        return autotest()

    table = charger_tickers()
    print(f"Veille des avis BRVM — {len(table)} societes connues\n")
    session = requests.Session()
    session.headers.update(UA)

    tout = []
    for rubrique, chemin in RUBRIQUES.items():
        tout.extend(collecter(session, rubrique, chemin, args.pages, table))

    # deduplication par URL, le plus recent d'abord
    vus, final = set(), []
    for x in sorted(tout, key=lambda y: y["date_avis"], reverse=True):
        if x["url"] in vus:
            continue
        vus.add(x["url"])
        x["date_collecte"] = date.today().isoformat()
        final.append(x)

    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
        w.writeheader()
        w.writerows(final)

    critiques = [x for x in final if x["critique"] == "oui"]
    print(f"\n{SORTIE.name} : {len(final)} avis, dont {len(critiques)} critiques")
    for x in critiques[:15]:
        print(f"  {x['date_avis']}  {x['type']:22s} {x['ticker'] or '----':6s} "
              f"{x['titre'][:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
