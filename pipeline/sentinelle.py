#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Surveillance du tableau de bord : dit si ce qui est publié est encore digne de foi.

    python sentinelle.py                  # contrôle le jeu publié
    python sentinelle.py --fichier X      # un autre jeu
    python sentinelle.py --rapport R      # où écrire le compte rendu

Les collectes signalent déjà leurs propres échecs, mais seulement quand elles
tournent. Ce qu'elles ne savent pas dire, c'est qu'elles n'ont pas tourné du
tout : un workflow désactivé, un quota épuisé, une branche qui ne reçoit plus
rien laissent le tableau de bord afficher sans broncher des chiffres d'il y a
trois semaines. C'est ce silence que ce script transforme en alerte.

Il ne collecte rien et ne corrige rien. Il lit le fichier publié, le confronte à
la date du jour et aux effectifs attendus, et sort en erreur si quelque chose ne
tient plus. Le workflow qui l'appelle ouvre alors une issue.

Code de sortie : 0 si tout va bien, 1 si au moins une alerte.
"""
import argparse, json, os, sys
from datetime import date, datetime, timedelta

PUBLIE = os.path.join("docs", "data_brvm.json")
REGISTRE = os.path.join("donnees", "cote_reference.json")
RAPPORT = os.path.join("donnees", "sentinelle.md")

# Une séance de bourse par jour ouvré ; le bulletin paraît en fin de journée et la
# collecte repasse le lendemain. Deux jours ouvrés de retard restent donc normaux.
COTE_MAX_JOURS_OUVRES = 3
# Sikafinance est relevé une fois par semaine : deux relevés manqués alertent.
PERF_MAX_JOURS = 16
FONDAMENTAUX_MAX_JOURS = 50
# Part minimale de la cote qu'une colonne structurante doit couvrir.
COUVERTURE_MIN = {"per": 0.85, "bnpa": 0.85, "ca": 0.90, "rn": 0.90}


def jours_ouvres(depuis, jusqu_a):
    """Nombre de jours ouvrés entre deux dates, bornes exclues côté départ."""
    n, j = 0, depuis
    while j < jusqu_a:
        j += timedelta(days=1)
        if j.weekday() < 5:
            n += 1
    return n


def iso(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


class Controle:
    def __init__(self):
        self.alertes, self.notes = [], []

    def alerte(self, titre, detail):
        self.alertes.append((titre, detail))

    def note(self, texte):
        self.notes.append(texte)


def controler(d, aujourd_hui, registre):
    c = Controle()
    meta = d.get("meta") or {}
    rows = d.get("rows") or []

    # --- 1. la cote est-elle encore fraîche ?
    seance = iso(meta.get("boc_seance"))
    if seance is None:
        c.alerte("Séance illisible",
                 f"`boc_seance` vaut {meta.get('boc_seance')!r} : le fichier publié est "
                 "mal formé ou tronqué.")
    else:
        retard = jours_ouvres(seance, aujourd_hui)
        if retard > COTE_MAX_JOURS_OUVRES:
            c.alerte(f"Cote en retard de {retard} jours ouvrés",
                     f"Dernière séance publiée : **{seance.isoformat()}** "
                     f"(BOC n° {meta.get('boc_numero')}). Au-delà de "
                     f"{COTE_MAX_JOURS_OUVRES} jours ouvrés, la collecte du bulletin "
                     "ne tourne plus ou échoue en silence.")
        else:
            c.note(f"Cote à jour — séance du {seance.isoformat()}, {retard} jour(s) ouvré(s).")

    # --- 2. la dernière séance s'est-elle réconciliée ?
    if meta.get("boc_reconcilie") is False:
        absents = meta.get("boc_absents") or []
        c.alerte("Dernière séance publiée sans réconciliation complète",
                 (f"Titres non lus dans le bulletin : **{', '.join(absents)}**. "
                  if absents else "")
                 + (meta.get("boc_motif_ecart") or "Motif non renseigné.")
                 + "\n\nLes lignes extraites restent cohérentes entre elles, mais la "
                   "ligne manquante doit être corrigée dans l'extracteur.")

    # --- 3. la cote n'a-t-elle pas rétréci ?
    total = meta.get("total") or len(rows)
    attendu = len(registre)
    if attendu and total < attendu - 2:
        c.alerte(f"La cote est passée de {attendu} à {total} titres",
                 "Le registre `donnees/cote_reference.json` connaît plus de titres que "
                 "le jeu publié n'en contient. Une radiation l'expliquerait ; une "
                 "extraction partielle aussi.")
    elif attendu:
        c.note(f"Effectif de la cote : {total} titres publiés, {attendu} au registre.")

    # --- 4. les relevés Sikafinance suivent-ils ?
    for cle, lib, limite in (("sika_perf", "performances multi-horizons", PERF_MAX_JOURS),
                             ("sika_fond", "fondamentaux", FONDAMENTAUX_MAX_JOURS)):
        j = iso(meta.get(cle))
        if j is None:
            c.alerte(f"Date de relevé manquante ({lib})",
                     f"`{cle}` est absent du fichier publié.")
            continue
        age = (aujourd_hui - j).days
        if age > limite:
            c.alerte(f"Relevé Sikafinance périmé ({lib}, {age} jours)",
                     f"Dernier relevé le **{j.isoformat()}**, au-delà des {limite} jours "
                     "attendus. La collecte hebdomadaire ne tourne plus.")
        else:
            c.note(f"Relevé {lib} : {j.isoformat()} ({age} j).")

    # --- 5. le BNPA de clôture correspond-il au bon exercice ?
    ref = iso(meta.get("bnpa_ref_seance"))
    if ref is None:
        c.note("Relevé de clôture d'exercice absent — la croissance du BNPA reste vide.")
    elif ref.year < aujourd_hui.year - 1:
        c.alerte(f"BNPA de référence daté de {ref.year}",
                 f"Le relevé de clôture porte sur le **{ref.isoformat()}** alors que "
                 f"l'exercice {aujourd_hui.year - 1} est clos. Relancer "
                 "`pipeline/bnpa_reference.py` pour le mettre à jour.")
    else:
        c.note(f"BNPA de référence : bulletin du {ref.isoformat()}.")

    # --- 6. les colonnes structurantes sont-elles encore remplies ?
    couv = meta.get("couverture") or {}
    for cle, part in COUVERTURE_MIN.items():
        n = couv.get(cle)
        if n is None or not total:
            continue
        if n / total < part:
            c.alerte(f"Couverture de « {cle} » tombée à {n}/{total}",
                     f"Le seuil attendu est {part:.0%}. Une source a changé de format, "
                     "ou une étape de la fusion échoue sans le dire.")

    # --- 7. le fichier contient-il bien des lignes exploitables ?
    sans_cours = [r.get("sym") for r in rows if r.get("clot") in (None, 0)]
    if sans_cours:
        c.alerte(f"{len(sans_cours)} titre(s) sans cours de clôture",
                 "Symboles : " + ", ".join(str(s) for s in sans_cours))

    return c


def ecrire_rapport(c, chemin, aujourd_hui, meta):
    lignes = [f"# Sentinelle — {aujourd_hui.isoformat()}", ""]
    if c.alertes:
        lignes.append(f"**{len(c.alertes)} point(s) à corriger.**")
        lignes.append("")
        for titre, detail in c.alertes:
            lignes += [f"## {titre}", "", detail, ""]
    else:
        lignes += ["Tout est en ordre.", ""]
    lignes += ["## État relevé", ""]
    for n in c.notes:
        lignes.append(f"- {n}")
    lignes += ["",
               f"<sub>BOC n° {meta.get('boc_numero')} du {meta.get('boc_seance')} · "
               f"jeu construit le {meta.get('construit_le')} · "
               f"{meta.get('total')} titres</sub>", ""]
    texte = "\n".join(lignes)
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(texte)
    return texte


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fichier", default=PUBLIE)
    ap.add_argument("--registre", default=REGISTRE)
    ap.add_argument("--rapport", default=RAPPORT)
    ap.add_argument("--date", help="date de référence, pour les essais (AAAA-MM-JJ)")
    a = ap.parse_args()

    aujourd_hui = date.fromisoformat(a.date) if a.date else date.today()

    if not os.path.exists(a.fichier):
        print(f"{a.fichier} introuvable : rien n'est publié.", file=sys.stderr)
        ecrire_rapport(
            type("C", (), {"alertes": [("Fichier publié introuvable",
                                        f"`{a.fichier}` n'existe pas dans le dépôt.")],
                           "notes": []})(),
            a.rapport, aujourd_hui, {})
        sys.exit(1)

    d = json.load(open(a.fichier, encoding="utf-8"))
    registre = {}
    if os.path.exists(a.registre):
        registre = json.load(open(a.registre, encoding="utf-8"))
        if isinstance(registre, dict) and "valeurs" in registre:
            registre = registre["valeurs"]

    c = controler(d, aujourd_hui, registre)
    texte = ecrire_rapport(c, a.rapport, aujourd_hui, d.get("meta") or {})
    print(texte)
    print(f"\nRapport écrit dans {a.rapport}")
    sys.exit(1 if c.alertes else 0)


if __name__ == "__main__":
    main()
