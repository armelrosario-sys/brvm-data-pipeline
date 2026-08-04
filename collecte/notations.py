#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/notations.py — Collecteur des notations financieres BRVM.

SOURCE : https://www.brvm.org/fr/emetteurs/type-annonces/notations-financieres
~30 pages d'annonces, chaque entree pointant vers le communique PDF d'une agence
agreee UEMOA (GCR Ratings principalement, WARA, Bloomfield).

POURQUOI CETTE SOURCE (decouverte du 02/08/2026) : c'est la premiere source
REELLEMENT INDEPENDANTE du pipeline. Jusqu'ici tout recoupement passait par la
BRVM elle-meme (BOC) ou par la presse, qui reprend les memes communiques. Une
agence de notation a acces aux comptes, aux entretiens de direction et a la
structure d'endettement : elle peut donc CONTREDIRE nos profils.

Cas fondateur ONTBF : le profilage le classait VIGILANCE_CONTRACTION a
-13,4 %/an (BPA implicite sur 2 points), alors que GCR rehaussait sa note de
A(WU) a A+(WU) le 19/12/2025. Les chiffres du rapport (CA 142 Mds en 2024
apres 139 en 2023, marge nette 15 %) donnent un RN implicite de 21,3 Mds,
identique a la valeur de notre base. Le -13,4 % etait un artefact de source.

CE QUE LA SOURCE APPORTE (par ordre de valeur) :
  1. verification independante des profils (drapeau de contradiction)
  2. donnees bilancielles absentes avant Track A (marges, levier, liquidite)
  3. substitut au Z-Score pour les BANQUES (Altman les exclut explicitement)
  4. series de chiffre d'affaires sur 5 ans -> second axe de croissance
  5. catalyseurs dates (declencheurs de hausse/baisse) -> future fiche de pari
  6. scores de risque pays et sectoriel UEMOA -> page macro

LIMITES A GARDER EN TETE (inscrites dans chaque ligne collectee) :
  - une notation mesure le RISQUE DE CREDIT, pas l'attractivite actionnaire.
    GCR ecrit explicitement que ses notations ne couvrent ni le risque de
    liquidite, ni le risque de marche, et ne sont pas des recommandations.
    Une note A+ n'est JAMAIS un profil GARP.
  - notations SOLLICITEES et remunerees par les emetteurs.
  - couverture partielle (~25 emetteurs cotes sur 47) et frequence annuelle.
  - DROITS : on ne stocke que des donnees extraites et l'URL source, jamais
    le texte des communiques.

Sortie : collecte/notations_financieres.csv (+ notations_echecs.jsonl)
Usage :
    python3 notations.py                 # index seul (rapide, ~30 pages)
    python3 notations.py --pdf 40        # + extraction des 40 PDF les plus recents
    python3 notations.py --pdf 0 --tout  # index complet sans extraction PDF
"""
import argparse
import csv
import io
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

BASE = "https://www.brvm.org"
INDEX = BASE + "/fr/emetteurs/type-annonces/notations-financieres"
ICI = Path(__file__).resolve().parent
SORTIE = ICI / "notations_financieres.csv"
ECHECS = ICI / "notations_echecs.jsonl"
ENTETES = {"User-Agent": "brvm-data-pipeline/1.0 (collecte notations, usage prive)"}

# --- Correspondance nom d'emetteur BRVM -> ticker. Les noms de la page d'index
# ne sont pas normalises (majuscules, accents, suffixes variables) : on compare
# sur une forme reduite. Seuls les 47 tickers actions nous interessent.
NOMS_TICKERS = {
    "sonatel": "SNTS", "bicici": "BICC", "bici ci": "BICC", "safca": "SAFC",
    "sgci": "SGBC", "societe generale ci": "SGBC", "societe generale cote divoire": "SGBC",
    "sgb ci": "SGBC", "bernabe": "BNBC", "cfao motors": "CFAC", "tractafric": "PRSC",
    "total": "TTLC", "totalenergies marketing ci": "TTLC", "sitab": "STBC",
    "nestle ci": "NTLC", "uniwax": "UNXC", "setao": "STAC", "sodeci": "SDCC",
    "cie ci": "CIEC", "compagnie ivoirienne delectricite": "CIEC", "filtisac": "FTSC",
    "sicor": "SICC", "sicable": "CABC", "smb": "SMBC", "smb ci": "SMBC",
    "sogb": "SOGC", "saph": "SPHC", "saph ci": "SPHC", "saph cote divoire": "SPHC",
    "crown siem": "SEMC", "eviosys packaging siem": "SEMC", "air liquide ci": "SIVC",
    "erium ci": "SIVC", "solibra": "SLBC", "palm ci": "PALC",
    "servair abidjan": "ABJC", "servair abidjan ci": "ABJC", "nei-ceda": "NEIC",
    "nei ceda": "NEIC", "bank of africa bn": "BOAB", "boa bn": "BOAB",
    "bank of africa ng": "BOAN", "boa ng": "BOAN", "onatel bf": "ONTBF",
    "onatel burkina faso": "ONTBF", "onatel-sa": "ONTBF", "ecobank tg": "ETIT",
    "bank of africa bf": "BOABF", "boa bf": "BOABF", "bank of africa ml": "BOAM",
    "boa ml": "BOAM", "bank of africa sn": "BOAS", "boa sn": "BOAS",
    "bank of africa ci": "BOAC", "boa ci": "BOAC", "oragroup": "ORGT",
    "total senegal": "TTLS", "totalenergies marketing sn": "TTLS",
    "vivo energy ci": "SHEC", "unilever ci": "UNLC", "sib": "SIBC",
    "societe ivoirienne de banque": "SIBC", "sucrivoire": "SCRC",
    "ecobank ci": "ECOC", "ecobank cote divoire": "ECOC", "nsbc": "NSBC",
    "nsia banque ci": "NSBC", "nsia banque cote divoire": "NSBC",
    "coris bank international": "CBIBF", "coris bank international bf": "CBIBF",
    "coris bank international burkina faso": "CBIBF", "orange ci": "ORAC",
    "cote divoire telecom": "ORAC", "bbgci": "BBGCI", "biic": "BICB", "lnb": "LNBB",
    "loterie nationale du benin": "LNBB", "bollore transport & logistics": "SDSC",
    "bollore transport et logistics": "SDSC", "agl ci": "SDSC",
}

# --- Echelles regionales UEMOA (suffixe WU). Le rang sert UNIQUEMENT a detecter
# les variations d'une revue a l'autre, jamais a classer les titres entre eux.
RANGS = ["D", "C", "CC", "CCC-", "CCC", "CCC+", "B-", "B", "B+", "BB-", "BB",
         "BB+", "BBB-", "BBB", "BBB+", "A-", "A", "A+", "AA-", "AA", "AA+", "AAA"]

RE_LIGNE = re.compile(
    r"\|\s*(\d{2}/\d{2}/\d{4})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*"
    r"\[T[ée]l[ée]charger\]\((https://[^\)]+\.pdf)\)")
RE_NOTE = re.compile(
    r"\b(AAA|AA[+-]?|A[+-]?|BBB[+-]?|BB[+-]?|B[+-]?|CCC[+-]?|CC|C|D)\s*\("
    r"\s*(WU|WR|WA|wu)\s*\)", re.I)
RE_PERSPECTIVE = re.compile(
    r"perspective[^.]{0,40}?\b(stable|positive|n[ée]gative|en d[ée]veloppement)\b", re.I)
RE_ACTION = re.compile(
    r"\b(rehauss|relev|abaiss|d[ée]grad|affirm|confirm|attribu|assign|retir)\w*", re.I)
RE_CA = re.compile(
    r"(\d[\d\s.,]{1,9})\s*milliards?\s*(?:de\s*)?(?:FCFA|F\s?CFA|XOF)", re.I)
RE_MARGE_NETTE = re.compile(r"marge\s+nette[^.\d]{0,30}(\d{1,2})\s*%", re.I)
RE_MARGE_BRUTE = re.compile(r"marge\s+brute[^.\d]{0,30}(\d{1,2})\s*%", re.I)
RE_SCORE_PAYS = re.compile(r"score\s+de\s+risque[- ]pays\s*\|?\s*([\d,\.]+)", re.I)
RE_SCORE_SECT = re.compile(r"score\s+de\s+risque\s+sectoriel\s*\|?\s*([\d,\.]+)", re.I)
RE_SCORE_TOTAL = re.compile(r"score\s+total\s*\|?\s*([\d,\.]+)", re.I)
RE_AGENCE = re.compile(r"\b(GCR Ratings|GCR|WARA|Bloomfield|Moody'?s|Fitch|S&P)\b")


def reduire(nom):
    """Forme comparable : minuscules, sans accents ni ponctuation."""
    s = (nom or "").lower().strip()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("ô", "o"), ("î", "i"),
                 ("ç", "c"), ("à", "a"), ("û", "u"), ("'", ""), ("’", ""),
                 (".", ""), ("  ", " ")):
        s = s.replace(a, b)
    s = re.sub(r"\s*(s\.?a\.?|sa|plc)$", "", s).strip()
    return re.sub(r"\s+", " ", s)


def ticker_depuis(nom_societe, titre_annonce, url):
    """Un ticker n'est retenu que si le nom correspond ; sinon None (jamais de
    devinette : un mauvais rattachement contaminerait un profil)."""
    for source in (nom_societe, titre_annonce, Path(url).stem.replace("_", " ")):
        red = reduire(source)
        if not red:
            continue
        if red in NOMS_TICKERS:
            return NOMS_TICKERS[red]
        for cle, tick in NOMS_TICKERS.items():
            if len(cle) >= 4 and cle in red:
                return tick
    return None


def rang(note):
    base = (note or "").split("(")[0].strip().upper()
    return RANGS.index(base) if base in RANGS else None


def lire_index(session, page_max=40):
    """Parcourt les pages d'index. Format Drupal 7 stable : tableau
    Date | Societe | Titre | [Telecharger](url.pdf)."""
    vues, lignes = set(), []
    for page in range(0, page_max):
        url = INDEX if page == 0 else f"{INDEX}?page={page}"
        try:
            r = session.get(url, timeout=45)
            r.raise_for_status()
        except Exception as e:
            journaliser({"etape": "index", "page": page, "erreur": str(e)})
            break
        txt = _texte(r)
        trouvees = RE_LIGNE.findall(txt)
        if not trouvees:
            break
        nouvelles = 0
        for d, soc, titre, pdf in trouvees:
            if pdf in vues:
                continue
            vues.add(pdf)
            nouvelles += 1
            lignes.append(dict(date_annonce=_iso(d), societe_brvm=soc.strip(),
                               titre=titre.strip(), url_pdf=pdf))
        print("  page %2d : %d annonces (%d nouvelles)" % (page + 1, len(trouvees), nouvelles))
        if nouvelles == 0:
            break
        time.sleep(0.6)  # courtoisie envers le serveur BRVM
    return lignes


def _texte(reponse):
    """HTML -> texte a plat, format tableau markdown-like conserve."""
    html = reponse.text
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<a[^>]+href=[\"'](https://[^\"']+\.pdf)[\"'][^>]*>\s*"
                  r"([^<]*)</a>", r"[Télécharger](\1)", html, flags=re.I)
    html = re.sub(r"</t[dh]>", " | ", html, flags=re.I)
    html = re.sub(r"</tr>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#039;", "'")
    return re.sub(r"[ \t]+", " ", html)


def _iso(d):
    j, m, a = d.split("/")
    return "%s-%s-%s" % (a, m, j)


def _nombre(s):
    return float(s.replace(" ", "").replace("\xa0", "").replace(",", ".")) if s else None


def extraire_pdf(session, url):
    """Extrait du communique ce qui est structurellement fiable. Tout champ
    absent reste None : aucune valeur n'est devinee."""
    import pdfplumber
    r = session.get(url, timeout=90)
    r.raise_for_status()
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
    return _analyser_texte(txt)


def _analyser_texte(txt):
    """Analyse le texte d'un communique. Separee du telechargement pour etre
    testable hors ligne (mode --test)."""
    plat = re.sub(r"\s+", " ", txt)

    # Note de long terme : la PREMIERE occurrence du texte est souvent
    # l'ANCIENNE note ("rehausse la note de A(WU) a A+(WU)"). Erreur mesuree sur
    # l'echantillon ONATEL : A(WU) retenu au lieu de A+(WU) -- soit un cran
    # d'ecart, et surtout le sens inverse du mouvement. Ordre de priorite :
    #   1. tableau recapitulatif "Emetteur de long terme ... <note>"
    #   2. tournure "de X a Y" -> Y (la nouvelle)
    #   3. premiere occurrence, en dernier recours
    notes = RE_NOTE.findall(txt)
    note_lt = None
    m_tab = re.search(r"[Ee]metteur\s+de\s+long\s+terme[^\n]{0,80}?" + RE_NOTE.pattern,
                      txt, re.I)
    if m_tab:
        note_lt = "%s(%s)" % (m_tab.group(1).upper(), m_tab.group(2).upper())
    if note_lt is None:
        m_vers = re.search(RE_NOTE.pattern + r"\s*(?:a|à|vers)\s*" + RE_NOTE.pattern,
                           txt, re.I)
        if m_vers:
            note_lt = "%s(%s)" % (m_vers.group(3).upper(), m_vers.group(4).upper())
    if note_lt is None and notes:
        note_lt = "%s(%s)" % (notes[0][0].upper(), notes[0][1].upper())

    # note precedente (si le communique la mentionne) -> variation en crans
    note_ancienne = None
    m_de_a = re.search(r"\bde\s+" + RE_NOTE.pattern + r"\s*(?:a|à)\s*" + RE_NOTE.pattern,
                       txt, re.I)
    if m_de_a:
        note_ancienne = "%s(%s)" % (m_de_a.group(1).upper(), m_de_a.group(2).upper())
    # note court terme : premiere occurrence de type A1/A2/B/C sur echelle WU
    m_ct = re.search(r"\b(A1\+?|A1|A2|A3|B|C|D)\s*\(\s*WU\s*\)", txt, re.I)
    note_ct = m_ct.group(0).replace(" ", "").upper() if m_ct else None

    persp = RE_PERSPECTIVE.search(plat)
    action = RE_ACTION.search(plat)
    agence = RE_AGENCE.search(plat)
    mn = RE_MARGE_NETTE.search(plat)
    mb = RE_MARGE_BRUTE.search(plat)
    sp = RE_SCORE_PAYS.search(plat)
    ss = RE_SCORE_SECT.search(plat)
    stot = RE_SCORE_TOTAL.search(plat)

    # serie de chiffre d'affaires : "142 milliards FCFA (2023 : 139 milliards ...)"
    ca = [c for c in (_nombre(x) for x in RE_CA.findall(plat)) if c and 1 <= c <= 5000]
    annees = re.findall(r"\b(20[12]\d)\s*:", plat)

    return dict(
        agence=agence.group(1) if agence else None,
        note_lt=note_lt, note_ct=note_ct,
        perspective=(persp.group(1).lower() if persp else None),
        action=(action.group(0).lower() if action else None),
        marge_nette=_nombre(mn.group(1)) if mn else None,
        marge_brute=_nombre(mb.group(1)) if mb else None,
        score_risque_pays=_nombre(sp.group(1)) if sp else None,
        score_risque_secteur=_nombre(ss.group(1)) if ss else None,
        score_total=_nombre(stot.group(1)) if stot else None,
        note_ancienne=note_ancienne,
        variation_crans=((rang(note_lt) - rang(note_ancienne))
                         if (rang(note_lt) is not None and rang(note_ancienne) is not None)
                         else None),
        ca_mds=";".join(str(c) for c in ca[:6]) if ca else None,
        annees_citees=";".join(sorted(set(annees))[:6]) if annees else None,
        nb_notes_trouvees=len(notes))


def journaliser(obj):
    obj["horodatage"] = date.today().isoformat()
    with ECHECS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


COLONNES = ["ticker", "societe_brvm", "date_annonce", "agence", "note_lt", "rang_lt",
            "note_ancienne", "variation_crans", "note_ct", "perspective", "action", "marge_nette", "marge_brute",
            "ca_mds", "annees_citees", "score_risque_pays", "score_risque_secteur",
            "score_total", "statut_extraction", "url_pdf", "date_collecte"]


def autotest():
    """Rejoue les analyseurs sur les echantillons capturés (collecte/echantillons/),
    sans acces reseau. Sert de garde-fou : si la BRVM change le format de sa page
    ou si GCR change la mise en page de ses communiques, ce test le signale avant
    que des donnees fausses n'entrent dans le pipeline."""
    dossier = ICI / "echantillons"
    echecs = []

    txt = (dossier / "index_notations.txt").read_text(encoding="utf-8")
    lignes = RE_LIGNE.findall(txt)
    if len(lignes) != 15:
        echecs.append("index : %d lignes reconnues au lieu de 15" % len(lignes))
    attendus = {"ABJC", "SCRC", "TTLC", "TTLS", "ONTBF", "SMBC", "CABC", "BOAN",
                "ECOC", "NSBC", "BOAS", "SPHC", "CBIBF", "SGBC"}
    obtenus = {t for t in (ticker_depuis(s_, ti, u) for _, s_, ti, u in lignes) if t}
    if obtenus != attendus:
        echecs.append("index : rattachements %s" % (attendus ^ obtenus))

    pdf = (dossier / "pdf_ontbf.txt").read_text(encoding="utf-8")
    d = _analyser_texte(pdf)
    for cle, attendu in (("note_lt", "A+(WU)"), ("note_ancienne", "A(WU)"),
                         ("note_ct", "A1(WU)"), ("perspective", "stable"),
                         ("marge_nette", 15.0), ("marge_brute", 24.0),
                         ("score_risque_pays", 2.0), ("score_total", 8.75),
                         ("variation_crans", 1), ("ca_mds", "142.0;139.0;146.0;155.0;157.0")):
        if d.get(cle) != attendu:
            echecs.append("pdf %s : %r au lieu de %r" % (cle, d.get(cle), attendu))

    if echecs:
        print("AUTOTEST : %d ECHEC(S)" % len(echecs))
        for e in echecs:
            print("  - %s" % e)
        return 1
    print("AUTOTEST : tous les analyseurs passent (index 15/15, 14 tickers, "
          "PDF 10/10 champs)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true",
                    help="rejouer les analyseurs sur les echantillons, sans reseau")
    ap.add_argument("--pdf", type=int, default=25,
                    help="nombre de PDF a extraire (0 = index seul)")
    ap.add_argument("--pages", type=int, default=40, help="pages d'index a parcourir")
    ap.add_argument("--tout", action="store_true",
                    help="extraire meme les annonces non rattachees a un ticker action")
    args = ap.parse_args()
    if args.test:
        return autotest()

    session = requests.Session()
    session.headers.update(ENTETES)

    print("Index des notations financieres BRVM :")
    lignes = lire_index(session, args.pages)
    print("  -> %d annonces au total" % len(lignes))

    for ligne in lignes:
        ligne["ticker"] = ticker_depuis(ligne["societe_brvm"], ligne["titre"],
                                        ligne["url_pdf"])
    actions = [x for x in lignes if x["ticker"]]
    print("  -> %d rattachees a un ticker de l'univers (%d tickers distincts)"
          % (len(actions), len({x["ticker"] for x in actions})))

    # ordre : plus recentes d'abord ; une notation ancienne a peu de valeur
    candidats = sorted(actions if not args.tout else lignes,
                       key=lambda x: x["date_annonce"], reverse=True)[:args.pdf]

    resultats = []
    for i, ligne in enumerate(candidats, 1):
        print("  [%d/%d] %s %s" % (i, len(candidats), ligne["date_annonce"],
                                   ligne["ticker"] or ligne["societe_brvm"][:28]))
        try:
            donnees = extraire_pdf(session, ligne["url_pdf"])
            ligne.update(donnees)
            ligne["statut_extraction"] = "OK" if donnees["note_lt"] else "SANS_NOTE"
            ligne["rang_lt"] = rang(donnees["note_lt"])
        except Exception as e:
            ligne["statut_extraction"] = "ECHEC"
            journaliser({"etape": "pdf", "url": ligne["url_pdf"], "erreur": str(e)[:200]})
        resultats.append(ligne)
        time.sleep(0.8)

    # les annonces non extraites sont conservees (URL + date) : l'index seul a
    # deja de la valeur (savoir QUAND une societe a ete notee).
    for ligne in (actions if not args.tout else lignes):
        if ligne not in resultats:
            ligne["statut_extraction"] = "NON_EXTRAIT"
            resultats.append(ligne)

    aujourdhui = date.today().isoformat()
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
        w.writeheader()
        for ligne in sorted(resultats, key=lambda x: (x["ticker"] or "zz",
                                                      x["date_annonce"]), reverse=True):
            ligne["date_collecte"] = aujourdhui
            w.writerow(ligne)

    ok = sum(1 for x in resultats if x.get("statut_extraction") == "OK")
    print("\n%s : %d lignes (%d avec note extraite)" % (SORTIE.name, len(resultats), ok))
    print("RAPPEL : une notation mesure le risque de CREDIT, pas l'attractivite")
    print("actionnaire. Une note A+ n'est jamais un profil GARP.")


if __name__ == "__main__":
    sys.exit(main())
