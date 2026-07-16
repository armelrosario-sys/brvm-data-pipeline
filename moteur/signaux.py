#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANTIER 1 — Moteur de reconciliation des signaux (le "film").

Principes :
- La "photo" (scores.alertes) n'est pas modifiee : les deux coexistent.
- APPEND-ONLY : un signal eteint n'est jamais modifie ni supprime ;
  une rechute cree un NOUVEAU signal (nouveau cycle, nouvel id).
- Idempotent : relancer sans changement de donnees ne cree rien
  (garanti par l'index unique partiel ux_signaux_actifs + logique candidats).
- Conflit inter-signaux : un ticker avec un signal D actif ne peut pas
  porter de signal favorable (l'alarme prime sur la fenetre) ; les
  favorables actifs sont eteints (voie CONFLIT_ALARME) si un D apparait.

Catalogue v1 (uniquement ce qui est calculable avec les donnees auditees) :
  D1_PREMIERE_PERTE, D2_CHUTE_RESULTAT, D3_COUPE_DIVIDENDE,
  D4_RETARD_PUBLICATION, A_QUALITE_DECOTEE, B1_RECORD, RERATING_EN_COURS.
Hors v1 (donnees pas encore accumulees) : D5 liquidite jour, B3 volume, C1/C2.

Usage :
  python3 signaux.py            # run de reconciliation sur la base par defaut
  python3 signaux.py --db X.db  # run sur une autre base (tests)
"""
import argparse
import json
import sqlite3
from datetime import date
from pathlib import Path

from calendrier import echeance_reglementaire, cycle_le_plus_recent, deja_satisfait, age_meilleure_information

from scoring import (charger_seuils, charger_marche, appliquer_gate,
                     per_secteur_reproductible)

DB_DEFAUT = Path(__file__).resolve().parent / "brvm.db"

# Correctif 14/07/2026 : ces seuils vivaient en dur ici, violation de la
# doctrine "parametres geles ET versionnes dans seuils.yaml". Rapatries.
_seuils_signaux = charger_seuils().get("signaux", {})
SEUIL_DECOTE = _seuils_signaux.get("seuil_decote", 0.70)
SEUIL_CHUTE_RN = _seuils_signaux.get("seuil_chute_rn", 0.30)
SEUIL_RERATING_ACHEVE = _seuils_signaux.get("seuil_rerating_acheve", 1.30)
EXPIRATION_B1_BULLETINS = _seuils_signaux.get("expiration_b1_bulletins", 2)

FAVORABLES = ("A_QUALITE_DECOTEE", "B1_RECORD", "RERATING_EN_COURS")


# ------------------------------------------------------------------ outillage
def _mois_index(cur):
    """Liste ordonnee des mois de bulletin disponibles (bornage global)."""
    return [r[0] for r in cur.execute(
        "SELECT DISTINCT fin_mois FROM cours_mensuels ORDER BY fin_mois")]


def _serie_cours(cur, ticker):
    return cur.execute(
        "SELECT fin_mois, cours FROM cours_mensuels WHERE ticker=? "
        "AND cours IS NOT NULL ORDER BY fin_mois", (ticker,)).fetchall()


def _deux_derniers_rn(cur, ticker):
    return cur.execute(
        "SELECT exercice, resultat_net FROM etats_financiers "
        "WHERE ticker=? AND resultat_net IS NOT NULL "
        "ORDER BY exercice DESC LIMIT 2", (ticker,)).fetchall()


def _deux_derniers_dividendes(cur, ticker):
    return cur.execute(
        "SELECT exercice_couvert, montant_net FROM dividendes "
        "WHERE ticker=? AND montant_net IS NOT NULL AND exercice_couvert IS NOT NULL "
        "ORDER BY exercice_couvert DESC LIMIT 2", (ticker,)).fetchall()


def _per_recent_et_cours(cur, ticker):
    row = cur.execute(
        "SELECT per, cours, fin_mois FROM cours_mensuels WHERE ticker=? "
        "AND per IS NOT NULL ORDER BY fin_mois DESC LIMIT 1", (ticker,)).fetchone()
    return row if row else (None, None, None)


# ------------------------------------------------------------------ candidats
CALENDRIER_PATH = Path(__file__).resolve().parent.parent / "collecte" / "calendrier.json"
LIQUIDITE_JOUR_PATH = Path(__file__).resolve().parent.parent / "collecte" / "liquidite_jour.json"


def _calculer_retards_calendrier(cur, seuils, aujourd_hui, cal):
    """D4_RETARD_CALENDRIER (revise le 15/07/2026) : retard mesure contre
    l'ECHEANCE REGLEMENTAIRE CREPMF (config: delais_reglementaires), plus
    l'intervalle historique typique observe -- pas l'inverse. L'historique
    (moteur/calendrier.py) sert desormais a DEUX choses seulement : (1)
    confirmer que le titre publie reellement cette categorie de facon
    recurrente (min_occurrences), (2) determiner si le cycle en cours est
    deja satisfait par un depot recent. La date limite elle-meme est fixe,
    fondee sur le texte reglementaire, jamais sur la moyenne des annees
    passees. Coexiste avec le D4 manuel (avis_reglementaires)."""
    if cal is None:
        return {}
    cfg = seuils.get("calendrier", {})
    delais_cfg = seuils.get("delais_reglementaires", {})
    min_occ = cfg.get("min_occurrences", 3)
    exclues = set(cfg.get("categories_exclues", ["autre", "rapport_cac"]))

    retards = {}
    for t, categories in cal.items():
        for categorie, v in categories.items():
            if categorie in exclues or categorie not in delais_cfg:
                continue
            hist = sorted(date(*map(int, d.split("-"))) for d in v["historique"])
            if len(hist) < min_occ:
                continue  # pas assez d'historique pour confirmer que ce titre publie bien cette categorie
            annee_ref, echeance = cycle_le_plus_recent(categorie, aujourd_hui, delais_cfg)
            if deja_satisfait(categorie, hist, annee_ref, delais_cfg):
                continue  # le cycle en cours a deja son depot, rien a signaler
            jours_ecart = (aujourd_hui - echeance).days
            if jours_ecart > 0:  # echeance reglementaire depassee sans depot
                prec = retards.get(t)
                if prec is None or jours_ecart > prec[0]:
                    retards[t] = (jours_ecart, categorie, hist[-1], echeance, jours_ecart)
    return retards


def calculer_candidats(cur, seuils, marche, aujourd_hui=None):
    """Retourne {(ticker,type): dict(direction, detail, valeur_reference,
    source_donnee)} pour toutes les conditions VRAIES a la date consideree
    (aujourd_hui=None -> date reelle du systeme ; sinon date de test, cf.
    l'argument --date de reconcilier(), pour rejouer un scenario passe)."""
    cand = {}
    aujourd_hui = aujourd_hui or date.today()
    calendrier_cache = json.loads(CALENDRIER_PATH.read_text()) if CALENDRIER_PATH.exists() else None
    liquidite_jour_cache = json.loads(LIQUIDITE_JOUR_PATH.read_text()) if LIQUIDITE_JOUR_PATH.exists() else None
    retards_calendrier = _calculer_retards_calendrier(cur, seuils, aujourd_hui, calendrier_cache)
    tickers = [r[0] for r in cur.execute(
        "SELECT ticker FROM societes WHERE ticker NOT LIKE 'TEST_%' ORDER BY ticker")]
    secteur = {t: s for t, s in cur.execute("SELECT ticker, secteur FROM societes")}
    mois_globaux = _mois_index(cur)
    dernier_mois = mois_globaux[-1] if mois_globaux else None

    for t in tickers:
        # ---------- DEFAVORABLES ----------
        rns = _deux_derniers_rn(cur, t)
        if len(rns) == 2:
            (ex0, rn0), (ex1, rn1) = rns
            if rn0 is not None and rn1 is not None:
                if rn0 < 0 and rn1 > 0:
                    cand[(t, "D1_PREMIERE_PERTE")] = dict(
                        direction="DEFAVORABLE",
                        detail=f"RN {ex0} negatif ({rn0:.0f} M FCFA) apres un "
                               f"exercice {ex1} positif ({rn1:.0f} M FCFA)",
                        valeur_reference=rn0,
                        source_donnee=f"etats_financiers {ex1}->{ex0}")
                elif rn0 > 0 and rn1 > 0 and rn1 > 0 and (rn1 - rn0) / rn1 >= SEUIL_CHUTE_RN:
                    recul = 100 * (rn1 - rn0) / rn1
                    cand[(t, "D2_CHUTE_RESULTAT")] = dict(
                        direction="DEFAVORABLE",
                        detail=f"RN en recul de {recul:.1f}% : {rn1:.0f} ({ex1}) "
                               f"-> {rn0:.0f} M FCFA ({ex0})",
                        valeur_reference=recul,
                        source_donnee=f"etats_financiers {ex1}->{ex0}")

        divs = _deux_derniers_dividendes(cur, t)
        if len(divs) == 2:
            (dex0, d0), (dex1, d1) = divs
            if dex0 == dex1 + 1 and d0 < d1:
                cand[(t, "D3_COUPE_DIVIDENDE")] = dict(
                    direction="DEFAVORABLE",
                    detail=f"Dividende {dex0} ({d0:.0f} FCFA) < dividende "
                           f"{dex1} ({d1:.0f} FCFA)",
                    valeur_reference=d0,
                    source_donnee=f"dividendes {dex1}->{dex0}")

        # D4 : retard constate par avis, eteint par une publication posterieure
        for type_avis, date_avis, note in cur.execute(
                "SELECT type, date_avis, note FROM avis_reglementaires "
                "WHERE ticker=? AND type='RETARD_PUBLICATION'", (t,)):
            pub_apres = cur.execute(
                "SELECT COUNT(*) FROM etats_financiers WHERE ticker=? "
                "AND date_publication > ?", (t, date_avis)).fetchone()[0]
            if not pub_apres:
                cand[(t, "D4_RETARD_PUBLICATION")] = dict(
                    direction="DEFAVORABLE",
                    detail=f"Retard de publication constate le {date_avis}, "
                           f"aucune publication enregistree depuis",
                    valeur_reference=None,
                    source_donnee=f"avis_reglementaires {date_avis}")

        # D4 automatique : echeance reglementaire CREPMF depassee (calendrier.py)
        if t in retards_calendrier:
            jours_ecart, categorie, dernier, echeance, _ = retards_calendrier[t]
            cand[(t, "D4_RETARD_CALENDRIER")] = dict(
                direction="DEFAVORABLE",
                detail=f"{categorie} : echeance reglementaire CREPMF du "
                       f"{echeance.isoformat()} depassee de {jours_ecart}j "
                       f"(dernier depot connu : {dernier.isoformat()})",
                valeur_reference=jours_ecart,
                source_donnee=f"calendrier.json + delais_reglementaires ({categorie})")

        # D5 automatique (15/07/2026) : information globalement perimee --
        # AXE INDEPENDANT de D4. Ne regarde PAS une categorie precise ni une
        # echeance reglementaire : uniquement "depuis quand n'a-t-on RIEN
        # reçu de ce titre, toutes categories confondues ?". Ne peut ni
        # attenuer ni remplacer D4 -- les deux coexistent sans se toucher.
        if calendrier_cache and t in calendrier_cache:
            derniere_info, jours_info = age_meilleure_information(calendrier_cache[t], aujourd_hui)
            seuil_perime = seuils.get("fraicheur_fondamentaux", {}).get("seuil_perimee_jours", 365)
            if derniere_info is not None and jours_info > seuil_perime:
                cand[(t, "D5_INFO_PERIMEE")] = dict(
                    direction="DEFAVORABLE",
                    detail=f"Aucun document recu (toutes categories confondues) depuis "
                           f"{jours_info}j (dernier : {derniere_info.isoformat()}) -- "
                           f"seuil de {seuil_perime}j depasse",
                    valeur_reference=jours_info,
                    source_donnee="calendrier.json (toutes categories)")

        # ---------- FAVORABLES (bloques si un D est candidat sur ce ticker) ----------
        d_actif_candidat = any(k[0] == t and k[1].startswith("D") for k in cand)
        if d_actif_candidat:
            continue

        per, cours_per, mois_per = _per_recent_et_cours(cur, t)
        med, src_med = per_secteur_reproductible(cur, secteur.get(t, ""), marche)
        statut_gate, _ = appliquer_gate(cur, t, secteur.get(t, ""), seuils, marche)

        # A_QUALITE_DECOTEE : decote + RN en progression + eligible
        if (per and per > 0 and med and statut_gate == "ELIGIBLE"
                and len(rns) == 2 and rns[0][1] is not None and rns[1][1] is not None
                and rns[0][1] > rns[1][1] > 0
                and per < SEUIL_DECOTE * med):
            peg_txt = ""
            g_ann = None
            if rns[1][1] and rns[1][1] > 0:
                g_ann = 100 * (rns[0][1] / rns[1][1] - 1)
                if g_ann > 0:
                    peg_txt = f" ; PEG {per / g_ann:.2f}"
            cand[(t, "A_QUALITE_DECOTEE")] = dict(
                direction="FAVORABLE",
                detail=f"PER {per:.2f} < 70% de la mediane sectorielle {med:.2f} "
                       f"({src_med}) ; RN {rns[1][1]:.0f} -> {rns[0][1]:.0f} M FCFA{peg_txt} ; titre eligible",
                valeur_reference=cours_per,
                source_donnee=f"cours_mensuels {mois_per} + etats_financiers")

        # B1_RECORD : cloture la plus RECENTE connue > max des 12 mois
        # precedents. Correctif T1 (13/07/2026) : exige gate ELIGIBLE.
        #
        # Correctif de coherence (15/07/2026, retour utilisateur) : les deux
        # sources (bulletin mensuel, cours quotidien) etaient auparavant
        # traitees en either/or ("si le mensuel detecte deja un record, on
        # n'examine meme pas le jour") -- un titre dont le bulletin de juillet
        # etablissait deja un record restait fige a CETTE valeur, meme si le
        # cours du jour avait ensuite grimpe plus haut encore (CBIBF : signal
        # fige a 25700 FCFA/bulletin alors que la Synthese affichait 30005
        # FCFA/jour, le MEME jour -- incoherence visible entre les deux
        # tableaux). Desormais : UNE SEULE source de verite pour "le cours
        # actuel" -- le jour s'il existe, sinon le mensuel -- utilisee a la
        # fois pour la comparaison au record ET pour la valeur affichee,
        # exactement comme la colonne "Cours (FCFA)" de la Synthese le fait
        # deja (generer_dashboard_html.py) : les deux tableaux ne peuvent
        # plus diverger, ils lisent desormais la meme regle de priorite.
        serie = _serie_cours(cur, t)
        if statut_gate == "ELIGIBLE" and len(serie) >= 12:
            entree_jour = (liquidite_jour_cache or {}).get(t)
            cours_jour = entree_jour.get("cours_cloture") if entree_jour else None
            if cours_jour is not None:
                cours_actuel = cours_jour
                source_prix = "liquidite_jour.json (cours quotidien)"
                mention_source = f"cours du jour, {entree_jour.get('date_maj_brvm', 'date inconnue')}"
                fenetre_12m = serie[-12:]
                fenetre_hist = serie
            elif dernier_mois and serie[-1][0] == dernier_mois:
                cours_actuel = serie[-1][1]
                source_prix = f"cours_mensuels {dernier_mois}"
                mention_source = f"bulletin {dernier_mois}"
                fenetre_12m = serie[-13:-1]
                fenetre_hist = serie[:-1]
            else:
                cours_actuel = None

            if cours_actuel is not None and len(fenetre_12m) >= 1:
                max12 = max(x for _, x in fenetre_12m)
                if cours_actuel > max12:
                    max_hist = max(x for _, x in fenetre_hist) if fenetre_hist else max12
                    historique = cours_actuel > max_hist
                    cand[(t, "B1_RECORD")] = dict(
                        direction="FAVORABLE",
                        detail=("Plus-haut historique" if historique else "Plus-haut 12 mois")
                               + f" a {cours_actuel:.0f} FCFA ({mention_source})",
                        valeur_reference=cours_actuel,
                        source_donnee=source_prix)
    return cand


# --------------------------------------------------------------- reconciliation
def reconcilier(db_path=DB_DEFAUT, aujourd_hui=None):
    auj_date = date.fromisoformat(aujourd_hui) if aujourd_hui else date.today()
    auj = auj_date.isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    seuils, marche = charger_seuils(), charger_marche()
    # scoring lit sa propre connexion sur DB par defaut ; ici tout passe par cur
    cand = calculer_candidats(cur, seuils, marche, auj_date)

    actifs = {(t, ty): (i, vref, det) for i, t, ty, vref, det in cur.execute(
        "SELECT id, ticker, type, valeur_reference, detail FROM signaux WHERE statut='ACTIF'")}
    secteur = {t: s for t, s in cur.execute("SELECT ticker, secteur FROM societes")}

    nouveaux, eteints = [], []

    def eteindre(sid, voie):
        cur.execute("UPDATE signaux SET statut='ETEINT', date_extinction=?, "
                    "voie_extinction=? WHERE id=? AND statut='ACTIF'", (auj, voie, sid))

    def inserer(t, ty, c):
        cur.execute("INSERT INTO signaux(ticker,type,direction,detail,"
                    "valeur_reference,date_detection,source_donnee) VALUES(?,?,?,?,?,?,?)",
                    (t, ty, c["direction"], c["detail"], c["valeur_reference"],
                     auj, c["source_donnee"]))
        nouveaux.append((t, ty))

    # 1) Conflit : D candidat => eteindre les favorables actifs du ticker
    tickers_d = {t for (t, ty) in cand if ty.startswith("D")}
    for (t, ty), (sid, _, _det) in list(actifs.items()):
        if t in tickers_d and ty in FAVORABLES:
            eteindre(sid, "CONFLIT_ALARME")
            eteints.append((t, ty, "CONFLIT_ALARME"))
            del actifs[(t, ty)]

    # 2) Nouveaux signaux (candidat vrai, pas de signal actif equivalent)
    for (t, ty), c in cand.items():
        if (t, ty) not in actifs:
            inserer(t, ty, c)
        elif ty == "D4_RETARD_CALENDRIER":
            # Cas particulier decouvert au test du 14/07/2026 : ce type peut
            # rester candidat en continu tout en changeant de categorie sous-
            # jacente (ex. le retard T1 se resorbe mais les etats financiers
            # restent en retard) -- l'append-only figerait alors un detail
            # perime indefiniment. Ici seulement : si la categorie source a
            # change, on eteint proprement (le fait initial reste vrai et
            # archive) et on recree (le nouveau fait est un nouveau cycle).
            _, _, detail_existant = actifs[(t, ty)]
            categorie_existante = detail_existant.split(" : ")[0]
            categorie_candidate = c["detail"].split(" : ")[0]
            if categorie_existante != categorie_candidate:
                sid_ancien = actifs[(t, ty)][0]
                eteindre(sid_ancien, "CONDITION_CESSEE")
                eteints.append((t, ty, "CONDITION_CESSEE (categorie resorbee)"))
                inserer(t, ty, c)
                del actifs[(t, ty)]

    # 3) Extinctions et transitions
    for (t, ty), (sid, vref, _det) in list(actifs.items()):
        if (t, ty) in cand:
            continue  # condition toujours vraie -> reste actif
        if ty == "A_QUALITE_DECOTEE":
            # cause de la sortie ? si PER remonte PAR HAUSSE DU COURS,
            # avec fondamentaux/gate intacts -> transition RERATING_EN_COURS
            per, cours_now, mois = _per_recent_et_cours(cur, t)
            med, _ = per_secteur_reproductible(cur, secteur.get(t, ""), marche)
            statut_gate, _m = appliquer_gate(cur, t, secteur.get(t, ""), seuils, marche)
            rns = _deux_derniers_rn(cur, t)
            fondamentaux_ok = (statut_gate == "ELIGIBLE" and len(rns) == 2
                               and rns[0][1] is not None and rns[1][1] is not None
                               and rns[0][1] > rns[1][1] > 0)
            hausse_cours = (cours_now is not None and vref is not None
                            and cours_now > vref)
            if fondamentaux_ok and hausse_cours and per and med and per >= SEUIL_DECOTE * med:
                eteindre(sid, "REMPLACE")
                eteints.append((t, ty, "REMPLACE->RERATING_EN_COURS"))
                inserer(t, "RERATING_EN_COURS", dict(
                    direction="FAVORABLE",
                    detail=f"Sortie de decote par hausse du cours ({vref:.0f} -> "
                           f"{cours_now:.0f} FCFA), fondamentaux intacts ; PER {per:.2f} "
                           f"vs mediane {med:.2f}",
                    valeur_reference=cours_now,
                    source_donnee=f"cours_mensuels {mois}"))
            else:
                eteindre(sid, "CONDITION_CESSEE")
                eteints.append((t, ty, "CONDITION_CESSEE"))
        elif ty == "RERATING_EN_COURS":
            # Correctif T4 (13/07/2026) : ce statut nait d'une transition et
            # n'est jamais "candidat" — il doit PERSISTER tant qu'aucune de ses
            # portes de sortie n'est franchie (bug : extinction silencieuse au
            # run suivant sa creation).
            per, cours_now, mois = _per_recent_et_cours(cur, t)
            med, _ = per_secteur_reproductible(cur, secteur.get(t, ""), marche)
            statut_gate, _m = appliquer_gate(cur, t, secteur.get(t, ""), seuils, marche)
            rns = _deux_derniers_rn(cur, t)
            fondamentaux_ok = (statut_gate == "ELIGIBLE" and len(rns) == 2
                               and rns[0][1] is not None and rns[1][1] is not None
                               and rns[0][1] > rns[1][1] > 0)
            if per and med and per > SEUIL_RERATING_ACHEVE * med:
                eteindre(sid, "RERATING_ACHEVE")
                eteints.append((t, ty, "RERATING_ACHEVE"))
            elif per and med and per < SEUIL_DECOTE * med:
                eteindre(sid, "REMPLACE")  # retour en decote : A recree au prochain run
                eteints.append((t, ty, "REMPLACE"))
            elif not fondamentaux_ok:
                eteindre(sid, "CONDITION_CESSEE")
                eteints.append((t, ty, "CONDITION_CESSEE"))
            # sinon : reste ACTIF (persistance entre les portes de sortie)
        elif ty == "B1_RECORD":
            # expiration : plus de record depuis >= 2 bulletins
            serie = _serie_cours(cur, t)
            mois_globaux = _mois_index(cur)
            dernier_record = None
            for i in range(12, len(serie)):
                if serie[i][1] > max(x for _, x in serie[i-12:i]):
                    dernier_record = serie[i][0]
            if dernier_record and dernier_record in mois_globaux and \
               mois_globaux.index(mois_globaux[-1]) - mois_globaux.index(dernier_record) \
               >= EXPIRATION_B1_BULLETINS:
                eteindre(sid, "EXPIRATION")
                eteints.append((t, ty, "EXPIRATION"))
            elif (t, ty) not in cand and dernier_record is None:
                eteindre(sid, "CONDITION_CESSEE")
                eteints.append((t, ty, "CONDITION_CESSEE"))
            # sinon : reste actif pendant la fenetre d'expiration
        else:
            eteindre(sid, "CONDITION_CESSEE")
            eteints.append((t, ty, "CONDITION_CESSEE"))

    conn.commit()
    tjs_actifs = cur.execute("SELECT COUNT(*) FROM signaux WHERE statut='ACTIF'").fetchone()[0]
    print(f"[signaux {auj}] base={Path(db_path).name} : "
          f"{len(nouveaux)} nouveau(x), {tjs_actifs} actif(s) au total, "
          f"{len(eteints)} eteint(s) ce run")
    for t, ty in nouveaux:
        print(f"  + {t:7} {ty}")
    for t, ty, v in eteints:
        print(f"  - {t:7} {ty} ({v})")
    conn.close()
    return nouveaux, eteints


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DB_DEFAUT))
    p.add_argument("--date", default=None, help="date du run (AAAA-MM-JJ)")
    a = p.parse_args()
    reconcilier(a.db, a.date)
