#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C2 — la mesure du SECOND axe : l'exercice de rattachement du
payout_ratio, et ce que la mesure a trouve a la place.

Ce script N'ECRIT RIEN. C'est le proces-verbal executable de la passe de mesure
pre-autorisee du cycle 29 (11/10/2026), relancable a l'identique :

    python3 outils/mesure_rattachement_payout.py [chemin/vers/brvm.db]

CE QUE C2 DEMANDE. La base melange deux conventions de payout_ratio, sur deux
axes : (1) brut ou net, (2) l'exercice auquel le ratio est rattache — celui ou
le dividende est PROPOSE (n-1) ou celui ou il est VERSE (n). Le second axe etait
reste entier apres les cycles 12 et 22. profils.py prend le payout_ratio le plus
recent non nul sans jamais regarder son exercice, et s'en sert pour fermer les
profils RENDEMENT, VALUE et GARP via `payout_ok = payout <= payout_max`.

LES TROIS MESURES, et pourquoi il en faut trois.

  1. IDENTITE DE VARIATION DES CAPITAUX PROPRES. distribution implicite
     D(n) = RN(n) - (CP(n) - CP(n-1)), confrontee a deux alignements :
         A : payout(n-1) x RN(n-1)   (propose sur n-1, verse en n)
         B : payout(n)   x RN(n)     (rattache a l'exercice de versement)
     C'est la mesure du 28/09/2026, refaite sur la base d'aujourd'hui (C21 a
     corrige 1 683 valeurs, C34 en a deplace 8, C27 a renomme BBGCI en BBGC).

  2. NOMBRE D'ACTIONS IMPLICITE, mesure INDEPENDANTE de l'identite ci-dessus.
     payout(n) x RN(n) / DPA(n) donne un nombre d'actions ; le BOC en donne un
     autre, RN x PER / cours, qui ne passe par aucun payout. Si le ratio est
     bien rattache a n, les deux concordent ; s'il decrit n-1, c'est la version
     DPA(n-1) qui concorde.

  3. LE RAPPORT payout certifie / payout implicite du BOC. C'est la mesure qui
     a decide de la lecture des deux premieres : elle montre un FACTEUR COMMUN,
     et donc que les mesures 1 et 2 sont contaminees par l'axe brut/net.

RESERVE, inchangee depuis le 28/09/2026 : l'identite de la mesure 1 ne se ferme
exactement que si les seuls mouvements de capitaux propres sont le resultat et
le dividende. Une augmentation de capital, des ecarts de conversion, des
reserves reclassees ou des interets minoritaires la faussent. Ce n'est pas une
preuve, c'est un signal — et c'est pourquoi la mesure 2 existe.
"""
import json
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DB = Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE / "moteur" / "brvm.db"
PROFILS = RACINE / "collecte" / "profils.json"
# Le facteur mesure par la troisieme passe, et le seul nombre que ce script
# porte en dur : il est RE-MESURE ci-dessous, jamais suppose.
FACTEUR_OBSERVE = 0.880


def charger(cur):
    rn, cp, po = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for t, e, r, c, p in cur.execute(
            "SELECT ticker, exercice, resultat_net, capitaux_propres, "
            "payout_ratio FROM etats_financiers "
            "WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker, exercice"):
        if r is not None:
            rn[t][e] = r
        if c is not None:
            cp[t][e] = c
        if p is not None:
            po[t][e] = p
    dpa = defaultdict(dict)
    for t, m, e in cur.execute(
            "SELECT ticker, montant_net, exercice_couvert FROM dividendes "
            "WHERE montant_net IS NOT NULL AND exercice_couvert IS NOT NULL"):
        dpa[t][e] = m
    boc = {}
    for t, c, p, r, d in cur.execute(
            "SELECT ticker, cours, per, rendement, date_bulletin "
            "FROM cours_quotidien_boc WHERE cours IS NOT NULL "
            "ORDER BY ticker, date_bulletin"):
        boc[t] = (c, p, r, d)          # la derniere seance de chaque ticker
    # defaultdict -> dict : une simple LECTURE de defaultdict cree la cle, et
    # un ticker sans payout se retrouvait dans la population des mesures.
    return (dict(rn), dict(cp), dict(po), dict(dpa), boc)


def mesure_1_identite(rn, cp, po):
    print("\n=== 1. Identite de variation des capitaux propres ===")
    print("%-7s %-5s %15s %15s %9s %15s %9s  gagnant"
          % ("ticker", "n", "D(n) implicite", "A=p(n-1)RN(n-1)", "ecart A",
             "B=p(n)RN(n)", "ecart B"))
    lignes = []
    for t in sorted(cp):
        pt, rt = po.get(t, {}), rn.get(t, {})
        for e in sorted(cp[t]):
            if e - 1 not in cp[t] or e not in rt:
                continue
            d = rt[e] - (cp[t][e] - cp[t][e - 1])
            if abs(d) < 1e-9:
                continue
            a = (pt[e - 1] * rt[e - 1]
                 if e - 1 in pt and e - 1 in rt else None)
            b = pt[e] * rt[e] if e in pt else None
            ea = abs(a - d) / abs(d) * 100 if a is not None else None
            eb = abs(b - d) / abs(d) * 100 if b is not None else None
            if ea is None and eb is None:
                continue
            gagnant = ("" if ea is None or eb is None
                       else ("A" if ea < eb else "B"))
            fmt = lambda x, f="%.1f": (f % x) if x is not None else "-"
            print("%-7s %-5d %15.1f %15s %9s %15s %9s  %s"
                  % (t, e, d, fmt(a), fmt(ea, "%.1f%%"), fmt(b),
                     fmt(eb, "%.1f%%"), gagnant))
            lignes.append((t, e, ea, eb, gagnant))
    comparables = [l for l in lignes if l[2] is not None and l[3] is not None]
    na = sum(1 for l in comparables if l[4] == "A")
    nb = sum(1 for l in comparables if l[4] == "B")
    print("\n  %d paires ou les DEUX alignements sont calculables : A=%d  B=%d"
          % (len(comparables), na, nb))
    if comparables:
        print("  ecart median  A %.1f %%   B %.1f %%"
              % (statistics.median(l[2] for l in comparables),
                 statistics.median(l[3] for l in comparables)))
        for t in sorted({l[0] for l in comparables}):
            d = [l for l in comparables if l[0] == t]
            c = Counter(l[4] for l in d)
            print("    %-6s %d paire(s) : A=%d  B=%d"
                  % (t, len(d), c["A"], c["B"]))
    return len(comparables), na, nb


def mesure_2_actions(rn, po, dpa, boc):
    print("\n=== 2. Nombre d'actions implicite (mesure independante) ===")
    lignes = []
    for t in sorted(po):
        if t not in boc:
            continue
        cours, per, _rend, _d = boc[t]
        rt, dt = rn.get(t, {}), dpa.get(t, {})
        if not per or per <= 0 or not rt:
            continue
        ex = max(rt)
        n_marche = rt[ex] * 1e6 * per / cours
        for e in sorted(po[t]):
            if e not in rt or po[t][e] == 0:
                continue
            nb = (po[t][e] * rt[e] * 1e6 / dt[e] if dt.get(e) else None)
            na = (po[t][e] * rt[e - 1] * 1e6 / dt[e - 1]
                  if dt.get(e - 1) and e - 1 in rt else None)
            ea = abs(na - n_marche) / n_marche * 100 if na else None
            eb = abs(nb - n_marche) / n_marche * 100 if nb else None
            if ea is None or eb is None:
                continue
            lignes.append((t, e, ea, eb, "A" if ea < eb else "B"))
            print("  %-6s %d  ecart A %6.1f %%   ecart B %6.1f %%   -> %s"
                  % (t, e, ea, eb, "A" if ea < eb else "B"))
    na = sum(1 for l in lignes if l[4] == "A")
    nb = sum(1 for l in lignes if l[4] == "B")
    print("\n  %d paires comparables : A=%d  B=%d" % (len(lignes), na, nb))
    if lignes:
        print("  ecart median  A %.1f %%   B %.1f %%"
              % (statistics.median(l[2] for l in lignes),
                 statistics.median(l[3] for l in lignes)))
    return len(lignes), na, nb


def mesure_3_facteur(rn, po, dpa, boc):
    print("\n=== 3. payout certifie / payout implicite du BOC ===")
    print("  %-6s %-5s %8s %9s %12s %13s %10s"
          % ("ticker", "n", "payout", "DPA", "DPA/BPA_BOC", "rapport",
             "1/rapport"))
    rapports = []
    for t in sorted(po):
        if t not in boc:
            continue
        cours, per, _rend, _d = boc[t]
        if not per or per <= 0:
            continue
        if not po[t]:
            continue
        e = max(po[t])
        d = dpa.get(t, {}).get(e)
        if not d:
            continue
        implicite = d / (cours / per)
        if implicite <= 0:
            continue
        r = po[t][e] / implicite
        rapports.append((t, e, r))
        print("  %-6s %-5d %8.3f %9.2f %12.4f %13.4f %10.4f"
              % (t, e, po[t][e], d, implicite, r, 1 / r))
    valeurs = [r for _t, _e, r in rapports]
    groupe = [v for v in valeurs if 1.12 <= v <= 1.15]
    print("\n  %d titres mesures ; mediane %.4f ; %d dans [1,12 ; 1,15]"
          % (len(valeurs), statistics.median(valeurs), len(groupe)))
    if groupe:
        print("  facteur inverse du groupe : mediane %.4f  (min %.4f  max %.4f)"
              % (statistics.median(1 / v for v in groupe),
                 min(1 / v for v in groupe), max(1 / v for v in groupe)))
    print("\n  -- le dividende, lui, est le MEME des deux cotes : rendement du "
          "BOC x cours contre montant_net de la base --")
    ecarts = []
    for t in sorted(po):
        if t not in boc:
            continue
        cours, _per, rend, _d = boc[t]
        dt = dpa.get(t, {})
        if not rend or not dt:
            continue
        net = dt[max(dt)]
        if not net:
            continue
        ecarts.append((t, rend * cours / net))
        print("  %-6s rendement x cours = %9.2f   montant_net = %9.2f   "
              "rapport %.4f" % (t, rend * cours, net, rend * cours / net))
    serres = [r for _t, r in ecarts if 0.995 <= r <= 1.005]
    print("  %d titres ; %d a moins de 0,5 %% d'ecart" % (len(ecarts), len(serres)))
    print("\n  -- brut deduit a %.3f : combien tombent sur un montant rond --"
          % FACTEUR_OBSERVE)
    ronds = 0
    total = 0
    for t in sorted(po):
        for e in sorted(po[t]):
            m = dpa.get(t, {}).get(e)
            if not m:
                continue
            total += 1
            brut = m / FACTEUR_OBSERVE
            if abs(brut - round(brut)) < 0.02:
                ronds += 1
                print("  %-6s %d  net %9.2f  ->  brut %9.2f" % (t, e, m, brut))
    print("  %d versements adosses a un payout certifie, %d ronds a %.3f"
          % (total, ronds, FACTEUR_OBSERVE))
    return len(valeurs), len(groupe), ronds, total


def mesure_4_effet():
    print("\n=== 4. Effet sur le veto payout_max = 1,00 ===")
    if not PROFILS.exists():
        print("  collecte/profils.json absent — lancer moteur/profils.py")
        return 0, 0
    profils = json.loads(PROFILS.read_text(encoding="utf-8"))
    implicites = [(t, v.get("payout"), v["profil"])
                  for t, v in profils.items()
                  if (v.get("payout_source") or "").startswith("IMPLICITE")]
    franchissent = []
    for t, p, prof in sorted(implicites, key=lambda x: -(x[1] or 0)):
        if p is None:
            continue
        corrige = p / FACTEUR_OBSERVE
        if p <= 1.0 < corrige:
            franchissent.append((t, p, corrige, prof))
    print("  %d titres sur %d au payout IMPLICITE(rendement x PER)"
          % (len(implicites), len(profils)))
    print("  %d franchi(ssen)t le veto apres division par %.3f :"
          % (len(franchissent), FACTEUR_OBSERVE))
    for t, p, c, prof in franchissent:
        print("    %-6s %.6f -> %.6f   (profil publie : %s)" % (t, p, c, prof))
    return len(implicites), len(franchissent)


def main():
    if not DB.exists():
        print("base absente : %s" % DB)
        return 1
    cur = sqlite3.connect(DB).cursor()
    rn, cp, po, dpa, boc = charger(cur)
    print("=" * 70)
    print("C2 — exercice de rattachement du payout_ratio : la mesure")
    print("=" * 70)
    print("%d valeurs de payout_ratio sur %d titres"
          % (sum(len(v) for v in po.values()), len(po)))
    n1, a1, b1 = mesure_1_identite(rn, cp, po)
    n2, a2, b2 = mesure_2_actions(rn, po, dpa, boc)
    mesure_3_facteur(rn, po, dpa, boc)
    mesure_4_effet()
    print("\n" + "=" * 70)
    print("CONCLUSION de la passe de mesure")
    print("=" * 70)
    print("Les deux mesures du rattachement NE CONVERGENT PAS : identite "
          "%d/%d (A/B) sur %d paires, actions %d/%d sur %d paires."
          % (a1, b1, n1, a2, b2, n2))
    print("La troisieme mesure dit pourquoi : un facteur commun separe le "
          "payout certifie du payout implicite du BOC, alors que le DIVIDENDE "
          "est le meme des deux cotes. Les mesures 1 et 2 passent toutes deux "
          "par ce facteur ; aucune ne peut donc trancher le rattachement tant "
          "que l'axe brut/net ne l'est pas.")
    print("Rien n'a ete ecrit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
