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
# Un titre peu liquide peut ne pas être coté d'une séance à l'autre : le bulletin
# ne lui consacre alors aucune ligne. Le laisser disparaître retirerait aussi ses
# fondamentaux et son historique, et déplacerait la médiane de son secteur — donc
# tous les écarts calculés pour ses voisins. On le reporte avec son dernier cours
# connu, volume nul, tant que cette cotation n'est pas trop ancienne.
REPORT_MAX_JOURS = 30
# Registre durable de la cote : dernière ligne connue pour chaque symbole. Il ne
# peut pas être déduit de la construction précédente — un titre absent en aurait
# déjà disparu. Il est tenu à jour à chaque séance et sert de filet.
REGISTRE = os.path.join("donnees", "cote_reference.json")
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


def lire_registre():
    if os.path.exists(REGISTRE):
        try:
            return json.load(open(REGISTRE, encoding="utf-8"))
        except (ValueError, OSError):
            print(f"  {REGISTRE} illisible : il sera reconstruit.")
    return {}


def completer_bulletin(valeurs, seance):
    """Ajoute les titres du registre absents du bulletin, au dernier cours connu."""
    if not seance:
        return valeurs, []
    registre = lire_registre()
    presents = {v["symbole"] for v in valeurs}
    jour = date.fromisoformat(seance)
    reportes = []

    for sym, e in sorted(registre.items()):
        if sym in presents or not e.get("seance"):
            continue
        age = (jour - date.fromisoformat(e["seance"])).days
        if age <= 0:
            continue
        if age > REPORT_MAX_JOURS:
            print(f"  retiré : {sym} sans cotation depuis {age} jours "
                  f"(seuil {REPORT_MAX_JOURS}) — sortie de cote probable")
            continue
        v = {k: val for k, val in e.items() if k != "seance"}
        v.update(volume=0, valeur=0, variation_jour=None,
                 cours_precedent=e.get("cloture"), ouverture=None,
                 _seance=e["seance"], _age=age)
        valeurs.append(v)
        reportes.append((sym, e["seance"], age))
    return valeurs, reportes


def ecrire_registre(valeurs, seance):
    """Mémorise la dernière cotation réelle de chaque titre. Les lignes reportées
    ne rafraîchissent rien : leur date d'origine doit continuer de vieillir."""
    registre = lire_registre()
    for v in valeurs:
        if v.get("variation_jour") is None:
            continue
        e = {k: val for k, val in v.items()
             if k not in ("volume", "valeur", "_seance", "_age")}
        e["seance"] = seance
        registre[v["symbole"]] = e
    os.makedirs(os.path.dirname(REGISTRE) or ".", exist_ok=True)
    json.dump(registre, open(REGISTRE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    return len(registre)


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

    valeurs, reportes = completer_bulletin(list(boc["valeurs"]), boc.get("seance"))

    lignes = []
    for v in valeurs:
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
        r["cp"] = e["montant"] if e else None
        r["cp_exercice"] = e["exercice"] if e else None
        if e and e["montant"] <= 0:
            # Rapporter un bénéfice à des capitaux propres négatifs inverse le signe :
            # une société rentable afficherait un ROE négatif. La mesure n'a pas de sens.
            r["roe"] = None
            motifs["roe"] = (f"capitaux propres négatifs ({e['montant']:,.0f} M FCFA)".replace(",", " ")
                             + " — le ROE n'a pas de signification")
        elif e and r["rn"] is not None:
            r["roe"] = round(r["rn"] / e["montant"] * 100, 2)
            # Pas de contre-oblique dans une expression de f-string : Python 3.11
            # la refuse, et les runners GitHub Actions tournent en 3.11.
            ex_cp = e["exercice"] or "d'exercice non identifié"
            ex_rn = ch.get("exercice") or "?"
            origine = e["source"] or "saisie manuelle"
            r["roe_src"] = (f"résultat net {ex_rn} rapporté aux capitaux propres "
                            f"{ex_cp} — {origine}")
            if not e["exercice"]:
                motifs["roe_reserve"] = "exercice des capitaux propres non identifié dans le rapport"
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

        r["seance_cotation"] = v.get("_seance") or boc.get("seance")
        r["hors_seance"] = v.get("_age", 0)
        if r["hors_seance"]:
            motifs["varJ"] = (f"titre non coté lors de la séance du {boc.get('seance')} — "
                              f"clôture du {r['seance_cotation']} conservée, {r['hors_seance']} j")
        r["motifs"] = motifs
        r["flags"] = signalements(r)
        if r["hors_seance"]:
            r["flags"].insert(0, f"Non coté depuis le {r['seance_cotation']} "
                                 f"({r['hors_seance']} j) — cours et ratios inchangés, volume nul")
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
        hors_seance=[dict(symbole=s, derniere_cotation=d, jours=j) for s, d, j in reportes],
        couverture={c: sum(1 for r in lignes if r[c] is not None)
                    for c in ("per", "rdt", "bnpa", "ca", "rn", "croiRN", "roe", "peg",
                              "v1s", "v1m", "ytd", "v1an", "v3a", "v5a")},
        total=len(lignes))

    n_reg = ecrire_registre(boc["valeurs"], boc.get("seance"))
    print(f"{REGISTRE} : {n_reg} titres au registre de la cote")

    os.makedirs(os.path.dirname(SORTIE) or ".", exist_ok=True)
    json.dump(dict(meta=meta, bench=bench, rows=lignes),
              open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    print(f"\n{SORTIE} écrit — BOC n° {meta['boc_numero']} du {meta['boc_seance']}, "
          f"{meta['total']} valeurs")
    if reportes:
        print("Titres non cotés lors de cette séance, reportés au dernier cours connu :")
        for sym, d, j in reportes:
            print(f"  {sym:6s} clôture du {d} ({j} j)")
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
    if r.get("cp") is not None and r["cp"] <= 0:
        f.append(f"Capitaux propres négatifs ({r['cp']:,.0f} M FCFA) — ROE et PBR sans objet"
                 .replace(",", " "))
    if r.get("cp") is not None and not r.get("cp_exercice"):
        f.append("Exercice des capitaux propres non identifié — ROE à confirmer")
    if r["croiRN"] is not None and r["croiRN"] > 100:
        f.append(f"Croissance du résultat de {r['croiRN']} % — effet de base, PEG peu fiable")
    for cle, lib in (("v3a", "3 ans"), ("v5a", "5 ans")):
        if r[cle] is None:
            f.append(f"Performance {lib} indisponible — historique de cotation trop court")
    return f


if __name__ == "__main__":
    main()
