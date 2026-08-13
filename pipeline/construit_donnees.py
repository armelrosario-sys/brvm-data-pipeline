#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fusionne les collectes en un fichier unique lu par le tableau de bord.

    python construit_donnees.py

Entrées  : donnees/boc.json, donnees/sikafinance.json, donnees/fonds_propres.csv
Sortie   : docs/data_brvm.json

Règles de dérivation, appliquées dans cet ordre :
  BNPA   = cours de clôture / PER du BOC ; à défaut, BNPA publié par Sikafinance
  PER    = PER du BOC ; à défaut, cours de clôture / BNPA Sikafinance
  ROE    = résultat net / fonds propres, uniquement si les fonds propres sont saisis
  PEG    = PER / croissance du RN, uniquement si cette croissance est > 0
Rien n'est estimé : une donnée absente reste nulle et porte un motif d'absence.
"""
import csv, json, os, statistics as st
from datetime import date

SORTIE = os.path.join("docs", "data_brvm.json")
SECTEURS = {"TEL": "Télécommunications", "FIN": "Services financiers",
            "CD": "Consommation discrétionnaire", "CB": "Consommation de base",
            "IND": "Industriels", "ENE": "Énergie", "SPU": "Services publics"}
METRIQUES = ["per", "rdt", "ytd", "v1an", "v3a", "v5a", "bnpa", "roe", "croiRN", "croiCA", "margeN"]
N_MIN_Z = 5


def lit(chemin, defaut=None):
    if not os.path.exists(chemin):
        print(f"  absent : {chemin}")
        return defaut
    return json.load(open(chemin, encoding="utf-8"))


def fonds_propres():
    """Capitaux propres saisis à la main : Sikafinance ne les publie pas."""
    chemin = os.path.join("donnees", "fonds_propres.csv")
    table = {}
    if not os.path.exists(chemin):
        return table
    with open(chemin, encoding="utf-8") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            v = (ligne.get("fonds_propres") or "").replace(" ", "").replace(",", ".")
            if v:
                try:
                    table[ligne["symbole"].strip().upper()] = {
                        "montant": float(v), "exercice": (ligne.get("exercice") or "").strip(),
                        "source": (ligne.get("source") or "").strip()}
                except ValueError:
                    pass
    return table


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    med = st.median(vals)
    return dict(n=len(vals), moy=round(st.mean(vals), 4), med=round(med, 4),
                ec=round(st.pstdev(vals), 4) if len(vals) > 1 else 0.0,
                mad=round(st.median([abs(v - med) for v in vals]), 4))


def ecart(v, ref):
    return None if (v is None or not ref) else round((v - ref) / abs(ref) * 100, 2)


def zrob(v, s):
    if v is None or s is None or s["n"] < N_MIN_Z or not s["mad"]:
        return None
    return round((v - s["med"]) / (s["mad"] * 1.4826), 2)


def main():
    print("Lecture des collectes")
    boc = lit(os.path.join("donnees", "boc.json"))
    sika = lit(os.path.join("donnees", "sikafinance.json"), {"valeurs": {}})
    fp = fonds_propres()
    if not boc:
        raise SystemExit("donnees/boc.json manquant : lancer collecte_boc.py d'abord.")

    lignes = []
    for v in boc["valeurs"]:
        sym = v["symbole"]
        s = sika["valeurs"].get(sym, {}) or {}
        perf = s.get("perf") or {}
        ch = s.get("chiffres") or {}
        motifs = {}

        r = dict(sym=sym, titre=v["titre"], sect=v["secteur"],
                 sectLib=SECTEURS.get(v["secteur"], v["secteur"]), comp=v["compartiment"],
                 prec=v["cours_precedent"], ouv=v["ouverture"], clot=v["cloture"],
                 varJ=v["variation_jour"], vol=v["volume"], val=v["valeur"],
                 ytd=v["perf_1er_janvier"], divM=v["dividende_montant"],
                 divISO=v["dividende_date"], rdt=v["rendement_net"], per=v["per"],
                 divD=("-".join(reversed(v["dividende_date"].split("-")))
                       .replace("-", "/") if v["dividende_date"] else None))

        for cle in ("v1s", "v1m", "v1an", "v3a", "v5a"):
            r[cle] = perf.get(cle)
            if r[cle] is None:
                motifs[cle] = "historique de cotation trop court"

        # cours de clôture du 31 décembre précédent, déduit de la performance annuelle
        r["ref31"] = round(v["cloture"] / (1 + v["perf_1er_janvier"] / 100)) \
            if v["perf_1er_janvier"] not in (None, -100) else None

        # --- BNPA puis PER : le BOC d'abord, Sikafinance en secours
        r["bnpa25"] = ch.get("bnpa")
        if r["per"]:
            r["bnpa"] = round(v["cloture"] / r["per"], 2)
            r["bnpa_src"] = "BOC (cours / PER)"
        elif r["bnpa25"]:
            r["bnpa"] = r["bnpa25"]
            r["bnpa_src"] = "Sikafinance"
            r["per"] = round(v["cloture"] / r["bnpa25"], 2)
            r["per_src"] = "calculé (cours / BNPA Sikafinance)"
        else:
            r["bnpa"] = None
            r["bnpa_src"] = None
            motifs["bnpa"] = "ni PER au BOC ni BNPA publié"
            motifs["per"] = "BNPA indisponible"

        # --- compte de résultat
        for src, dst in (("ca", "ca"), ("croissance_ca", "croiCA"),
                         ("rn", "rn"), ("croissance_rn", "croiRN")):
            r[dst] = ch.get(src)
            if r[dst] is None:
                motifs[dst] = "non publié par la source"
        r["exercice"] = ch.get("exercice")
        r["margeN"] = round(r["rn"] / r["ca"] * 100, 2) if (r["ca"] and r["rn"] is not None) else None

        # --- ROE : impossible sans capitaux propres
        e = fp.get(sym)
        if e and r["rn"] is not None:
            r["roe"] = round(r["rn"] / e["montant"] * 100, 2)
            r["roe_src"] = f"fonds propres {e['exercice']} — {e['source'] or 'saisie manuelle'}"
        else:
            r["roe"] = None
            motifs["roe"] = ("capitaux propres non saisis dans fonds_propres.csv"
                             if r["rn"] is not None else "résultat net indisponible")

        # --- PEG : sans objet si la croissance du résultat n'est pas positive
        if r["per"] and r["croiRN"] is not None and r["croiRN"] > 0:
            r["peg"] = round(r["per"] / r["croiRN"], 2)
        else:
            r["peg"] = None
            motifs["peg"] = ("croissance du résultat net négative ou nulle"
                             if r["croiRN"] is not None and r["croiRN"] <= 0
                             else "croissance du résultat net indisponible")

        # --- rendement : distinguer « pas de dividende » de « non publié »
        if r["rdt"] is None:
            motifs["rdt"] = ("aucun dividende récent" if not r["divISO"]
                             else "rendement non publié au BOC")

        r["motifs"] = motifs
        r["flags"] = signalements(r)
        lignes.append(r)

    # --- repères sectoriels et de marché
    bench = {"MARCHE": {m: stats([x[m] for x in lignes]) for m in METRIQUES}}
    for sct in SECTEURS:
        bench[sct] = {m: stats([x[m] for x in lignes if x["sect"] == sct]) for m in METRIQUES}
    for r in lignes:
        for m in METRIQUES:
            ss, sm = bench[r["sect"]][m], bench["MARCHE"][m]
            r[f"es_{m}"] = ecart(r[m], ss["med"] if ss else None)
            r[f"em_{m}"] = ecart(r[m], sm["med"] if sm else None)
            r[f"zs_{m}"] = zrob(r[m], ss)
            r[f"zm_{m}"] = zrob(r[m], sm)

    meta = dict(
        boc_numero=boc.get("numero"), boc_seance=boc.get("seance"),
        boc_reconcilie=boc.get("reconcilie"), boc_controles=boc.get("controles"),
        sika_releve=sika.get("releve_le"), sika_exercice=sika.get("exercice"),
        construit_le=date.today().isoformat(),
        couverture={c: sum(1 for r in lignes if r[c] is not None)
                    for c in ("per", "rdt", "bnpa", "ca", "rn", "croiRN", "roe", "peg",
                              "v1s", "v1m", "ytd", "v1an", "v3a", "v5a")},
        total=len(lignes))

    os.makedirs(os.path.dirname(SORTIE) or ".", exist_ok=True)
    json.dump(dict(meta=meta, bench=bench, rows=lignes),
              open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    print(f"\n{SORTIE} écrit — BOC n° {meta['boc_numero']} du {meta['boc_seance']}, "
          f"{meta['total']} valeurs")
    print("Couverture :")
    for c, n in meta["couverture"].items():
        etat = "" if n == meta["total"] else "   <-- incomplet"
        print(f"  {c:10s} {n:>2}/{meta['total']}{etat}")


def signalements(r):
    """Mises en garde attachées à une ligne, affichées au survol du symbole."""
    f = []
    if r["divISO"]:
        an, mo, jo = (int(x) for x in r["divISO"].split("-"))
        mois = (date.today().year - an) * 12 + date.today().month - mo
        if mois > 18:
            f.append(f"Dernier dividende vieux de {mois} mois — rendement non représentatif")
    if r["per"] and r["per"] > 50:
        f.append(f"PER de {r['per']} — valeur extrême, à ne pas comparer telle quelle")
    if r["rdt"] and r["rdt"] > 20:
        f.append(f"Rendement de {r['rdt']} % — dividende exceptionnel, non récurrent")
    if r["croiRN"] is not None and r["croiRN"] > 100:
        f.append(f"Croissance du résultat de {r['croiRN']} % — effet de base, PEG peu fiable")
    for cle, lib in (("v3a", "3 ans"), ("v5a", "5 ans")):
        if r[cle] is None:
            f.append(f"Performance {lib} indisponible — historique de cotation trop court")
    return f


if __name__ == "__main__":
    main()
