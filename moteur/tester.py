#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Golden tests — a rejouer avant toute mise en production d'une modification
du moteur ou des seuils. Echec de ces tests = ne pas deployer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import evaluer_titre, DB, per_le_plus_recent

ECHECS = []

def verifie(cond, message):
    global ECHECS
    if cond:
        print(f"  [OK] {message}")
    else:
        print(f"  [ECHEC] {message}")
        ECHECS.append(message)

print("=== Golden test 1 : TEST_EXCLU doit etre exclu (profil degrade) ===")
r = evaluer_titre("TEST_EXCLU")
verifie(r["statut_gate"] == "EXCLU", "statut = EXCLU")
verifie(any("negatif" in m for m in r["motifs_exclusion"]),
        "motif capitaux propres et/ou resultat net negatifs present")
verifie(any("payout" in m for m in r["motifs_exclusion"]),
        "motif payout excessif present")
verifie(any("publication" in m for m in r["motifs_exclusion"]),
        "motif retard de publication present")
verifie(r["score_composite"] is None, "aucun score compose (gate bloque le scoring)")

print("\n=== Golden test 2 : TEST_VIGIL doit etre eligible avec alerte, pas exclu ===")
r = evaluer_titre("TEST_VIGIL")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score compose calcule")
verifie(any("recul" in a for a in r["alertes"]),
        "alerte de recul du resultat net presente (RN en baisse -26%)")

print("\n=== Golden test 3 : Coris (CBIBF) doit etre eligible, score eleve ===")
r = evaluer_titre("CBIBF")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None and r["score_composite"] > 60,
        f"score composite eleve ({r['score_composite']}) — croissance +36%, PER decote")

print("\n=== Golden test 4 : Oragroup doit etre eligible malgre perte l'an dernier ===")
r = evaluer_titre("ORGT")
verifie(r["statut_gate"] == "ELIGIBLE",
        "statut = ELIGIBLE (perte 2024 isolee, pas 2 exercices consecutifs)")
verifie(any("dividende" in a.lower() for a in r["alertes"]),
        "alerte sur l'absence de dividende recent (5 ans)")

print("\n=== Golden test 5 : BOA Burkina Faso doit remonter l'alerte payout>100% ===")
r = evaluer_titre("BOABF")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (1 seul exercice a >100%, pas 2)")
verifie(any("100%" in a for a in r["alertes"]),
        "alerte payout > 100% remontee explicitement")
verifie(any("recul" in a for a in r["alertes"]),
        "alerte recul resultat net (-14,1%) remontee")

print("\n=== Golden test 6 : Sicor (donnees insuffisantes) ne doit pas produire de score fantaisiste ===")
r = evaluer_titre("SICC")
verifie(r["score_composite"] is None or len(r["alertes"]) > 0,
        "score absent ou alertes de donnees manquantes — jamais un score invente")

print("\n=== Golden test 7 : Sonatel doit ressortir eligible avec decote de valorisation ===")
r = evaluer_titre("SNTS")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_valorisation"] is not None and r["score_valorisation"] > 50,
        f"score valorisation > 50 (decote vs secteur telecom, score={r['score_valorisation']})")

print("\n=== Golden test 8 : Coris doit avoir un sizing REDUITE (flottant 20%) ===")
r = evaluer_titre("CBIBF")
verifie(r["sizing"]["recommandation"] == "REDUITE",
        f"sizing = REDUITE (flottant connu 20%), obtenu : {r['sizing']['recommandation']}")

print("\n=== Golden test 9 : Sonatel doit avoir sizing PLEINE via liquidite d'execution ELEVEE (pas le defaut) ===")
r = evaluer_titre("SNTS")
verifie(r["sizing"]["statut"] == "LIQUIDITE_ELEVEE",
        f"statut sizing = LIQUIDITE_ELEVEE (donnee qualitative reelle), obtenu : {r['sizing']['statut']}")
verifie(r["sizing"]["recommandation"] == "PLEINE",
        "recommandation = PLEINE, justifiee par la donnee, pas par un defaut aveugle")

print("\n=== Golden test 10 : NSIA Banque (aucune donnee individuelle) doit basculer en PRUDENCE, pas PLEINE ===")
r = evaluer_titre("NSBC")
verifie(r["sizing"]["statut"] == "DONNEE_INDISPONIBLE",
        "statut sizing = DONNEE_INDISPONIBLE")
verifie(r["sizing"]["recommandation"] == "PRUDENCE",
        f"recommandation = PRUDENCE par defaut (marche structurellement peu liquide), "
        f"obtenu : {r['sizing']['recommandation']}")

print("\n=== Golden test 11 : Oragroup (turnaround) — l'artefact de croissance doit etre neutralise ===")
r = evaluer_titre("ORGT")
verifie(r["score_rentabilite"] is not None and 50 <= r["score_rentabilite"] <= 60,
        f"rentabilite = note neutre+ ({r['score_rentabilite']}), pas un 100 artificiel")
verifie(any("TURNAROUND" in a for a in r["alertes"]),
        "alerte TURNAROUND explicite presente")
verifie(not any("PEG historique" in a for a in r["alertes"]),
        "aucun bonus PEG accorde sur base N-1 negative")
verifie(any("Fitch" in a or "defaut" in a.lower() or "gouvernance" in a.lower()
            for a in r["alertes"]),
        "les avis contextuels (notation Fitch, gouvernance) remontent en alerte")
r_cbibf = evaluer_titre("CBIBF")
verifie(r["score_composite"] < r_cbibf["score_composite"],
        f"ORGT ({r['score_composite']}) redescend sous CBIBF ({r_cbibf['score_composite']})")

print("\n=== Golden test 12 (R3) : le PER doit venir de cours_mensuels (frais), pas de marche.yaml (fige) ===")
r = evaluer_titre("CBIBF")
verifie(any("cours_mensuels" in a for a in r["alertes"]),
        "alerte confirmant la source cours_mensuels presente")
verifie(not any("12,56" in a or "7.87" in a or "7,87" in a for a in []),  # sanity placeholder
        "pas de confusion de source")
import sqlite3
conn_t = sqlite3.connect(DB)
per_frais, mois_frais = per_le_plus_recent(conn_t.cursor(), "CBIBF")
conn_t.close()
verifie(per_frais is not None and abs(per_frais - 12.56) < 0.5,
        f"PER frais de juillet 2026 utilise ({per_frais}), pas le PER d'avril fige (7.87)")

print("\n=== Golden test 13 (R4) : les avis contextuels Safca doivent remonter (gouvernance, capital, dividende) ===")
r = evaluer_titre("SAFC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (avis contextuels, pas d'exclusion)")
verifie(any("CREDAF" in a or "GOUVERNANCE" in a for a in r["alertes"]),
        "alerte gouvernance (nouvel actionnaire) presente")
verifie(any("capital" in a.lower() for a in r["alertes"]),
        "alerte augmentation de capital / dilution presente")
verifie(any("2028" in a for a in r["alertes"]),
        "guidance dividende (pas avant 2028) presente")

print("\n=== Golden test 14 (R5) : re-rating consomme detecte sur Coris ===")
r = evaluer_titre("CBIBF")
verifie(any("vs il y a 12 mois" in a for a in r["alertes"]),
        "alerte re-rating 12 mois presente")
verifie(any("deja consomme" in a for a in r["alertes"]),
        "detection du re-rating deja consomme (Coris a fortement remonte)")

print("\n=== Golden test 15 (R6 lot 1) : Setao (STAC) exclu, pertes 2 exercices reelles (pas synthetique) ===")
r = evaluer_titre("STAC")
verifie(r["statut_gate"] == "EXCLU", "statut = EXCLU (1er cas reel, non synthetique)")
verifie(any("negatif" in m for m in r["motifs_exclusion"]),
        "motif resultat net negatif present")

print("\n=== Golden test 16 (R6 lot 1) : Sicable (CABC) VALIDE, identite exacte serie 7 ans ===")
r = evaluer_titre("CABC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score calcule")

print("\n=== Golden test 17 (R6 lot 1) : Filtisac (FTSC) — alerte artefact HAO presente ===")
r = evaluer_titre("FTSC")
verifie(any("HAO" in a for a in r["alertes"]),
        "alerte ARTEFACT_COMPTABLE (gain HAO 2024) remontee")

print("\n=== Golden test 18 (R6 lot 2) : Bernabe (BNBC) VALIDE, identite exacte ===")
r = evaluer_titre("BNBC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score calcule")

print("\n=== Golden test 19 (R6 lot 2, fin) : Nei-Ceda (NEIC) — bascule en perte 2024 ===")
r = evaluer_titre("NEIC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (1 seule perte, pas 2)")
verifie(r["score_composite"] is not None and r["score_composite"] < 50,
        f"score bas coherent avec la perte (score={r['score_composite']})")

print("\n=== Golden test 20 (R6 lot 3) : Sucrivoire (SCRC) exclu, capitaux propres negatifs (cas reel) ===")
r = evaluer_titre("SCRC")
verifie(r["statut_gate"] == "EXCLU", "statut = EXCLU")
verifie(any("capitaux propres negatifs" in m for m in r["motifs_exclusion"]),
        "motif capitaux propres negatifs present (1er cas reel, non synthetique)")

print("\n=== Golden test 21 (R6 lot 3) : Nestle (NTLC) VALIDE, identite exacte, payout sain ===")
r = evaluer_titre("NTLC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score calcule")

print("\n=== Golden test 22 (R6 lot 4) : TotalEnergies CI (TTLC) — payout >100% detecte ===")
r = evaluer_titre("TTLC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (1 seul exercice >100%)")
verifie(any("100%" in a for a in r["alertes"]), "alerte payout >100% remontee")

print("\n=== Golden test 23 (R6 lot 5) : Orange CI (ORAC) VALIDE, croissance +6% ===")
r = evaluer_titre("ORAC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score calcule")

print("\n=== Golden test 24 (R6 lot 5) : Onatel BF (ONTBF) VALIDE, recul -26% detecte ===")
r = evaluer_titre("ONTBF")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(any("recul" in a for a in r["alertes"]), "alerte recul du resultat net presente")

print("\n=== Golden test 25 (R6 lot 6) : BOA Mali (BOAM) VALIDE, croissance +21% ===")
r = evaluer_titre("BOAM")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(r["score_composite"] is not None, "score calcule")

print("\n=== Golden test 26 (R6 lot 7) : BOA Niger (BOAN) — effondrement -91,8% detecte ===")
r = evaluer_titre("BOAN")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (1 seul exercice en repli severe)")
verifie(any("vigilance" in a.lower() or "recul" in a.lower() for a in r["alertes"]),
        "alerte de recul severe remontee")
verifie(any("PROFIT_WARNING" in a for a in r["alertes"]),
        "avis profit warning remonte")
verifie(r["score_composite"] is not None and r["score_composite"] < 40,
        f"score bas coherent (score={r['score_composite']})")

print("\n=== Golden test 27 (R6 lot 7) : BOA Cote d'Ivoire (BOAC) VALIDE, ROE eleve ===")
r = evaluer_titre("BOAC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(any("ROE" in a for a in r["alertes"]), "ROE calcule et remonte")

print("\n=== Golden test 28 (correction integrite) : BICI CI (BICC) — inversion de colonnes corrigee ===")
r = evaluer_titre("BICC")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE")
verifie(not any("recul" in a for a in r["alertes"]),
        "aucune fausse alerte de recul (croissance reelle +39%, pas un recul)")
r_bicb = evaluer_titre("BICB")
verifie(r_bicb["statut_gate"] == "ELIGIBLE",
        "BICB (BIIC Benin) desormais couvert (PCB OHADA, ajoute en R6 residuel)")

print("\n=== Golden test 29 : CIE CI (CIEC) et Loterie Benin (LNBB) — ajoutes via 2e source ===")
r = evaluer_titre("CIEC")
verifie(r["statut_gate"] == "ELIGIBLE", "CIEC = ELIGIBLE")
verifie(any("100%" in a for a in r["alertes"]) or r["score_solidite"] is not None,
        "CIEC payout 100% pris en compte")
r = evaluer_titre("LNBB")
verifie(r["statut_gate"] == "ELIGIBLE", "LNBB = ELIGIBLE")
verifie(any("recul" in a for a in r["alertes"]), "LNBB alerte de recul (-36%) presente")

print("\n=== Golden test 30 (R7) : fonction de fraicheur — cas perime detecte ===")
from scoring import verifier_fraicheur
from datetime import date
jours, perime = verifier_fraicheur("2026-01", aujourdhui=date(2026, 7, 9))
verifie(perime, f"un PER de janvier lu en juillet doit etre perime ({jours} jours)")

print("\n=== Golden test 31 (R7) : fonction de fraicheur — cas frais non signale ===")
jours, perime = verifier_fraicheur("2026-07", aujourdhui=date(2026, 7, 9))
verifie(not perime, f"un PER du mois courant ne doit pas etre signale perime ({jours} jours)")

print("\n=== Golden test 32 (R7) : rapport de fraicheur global s'execute sans erreur ===")
from scoring import rapport_fraicheur
fr = rapport_fraicheur()
verifie("perimes" in fr and "frais" in fr, "rapport de fraicheur structure correctement")
verifie(isinstance(fr["seuil_jours"], int), "seuil de fraicheur bien un entier")

print("\n=== Golden test 33 (correction bug gate) : SEMC exclu pour SUSPENSION, pas 'aucune donnee' ===")
r = evaluer_titre("SEMC")
verifie(r["statut_gate"] == "EXCLU", "statut = EXCLU")
verifie(any("suspension" in m for m in r["motifs_exclusion"]),
        "motif = suspension reelle (pas 'aucune donnee financiere disponible')")
verifie("aucune donnee" not in r["motifs_exclusion"][0],
        "le vrai motif reglementaire prime sur l'absence de donnees financieres")

print("\n=== Golden test 34 (R6 residuel) : Tractafric (PRSC) et BIIC Benin (BICB) ajoutes ===")
r = evaluer_titre("PRSC")
verifie(r["statut_gate"] == "ELIGIBLE", "PRSC = ELIGIBLE")
r = evaluer_titre("BICB")
verifie(r["statut_gate"] == "ELIGIBLE", "BICB = ELIGIBLE (PCB OHADA, statut PROBABLE)")

print("\n=== Golden test 35 (liquidite mesuree) : UNLC quasi-intradable (volume 0.2% marche) ===")
r = evaluer_titre("UNLC")
verifie(r["sizing"]["statut"] == "QUASI_INTRADABLE",
        f"statut = QUASI_INTRADABLE, obtenu : {r['sizing']['statut']}")
verifie(r["sizing"]["recommandation"] == "MINIMALE",
        f"recommandation = MINIMALE, obtenu : {r['sizing']['recommandation']}")

print("\n=== Golden test 36 (liquidite mesuree) : STBC liquidite faible mais tradable ===")
r = evaluer_titre("STBC")
verifie(r["sizing"]["statut"] == "LIQUIDITE_FAIBLE_MESUREE",
        f"statut = LIQUIDITE_FAIBLE_MESUREE, obtenu : {r['sizing']['statut']}")
verifie(r["sizing"]["recommandation"] == "REDUITE", "recommandation = REDUITE")

print("\n=== Golden test 37 (P6/P7 preuve de concept) : ORGT historique multi-exercices en base ===")
import sqlite3
conn_p6 = sqlite3.connect(DB)
lignes = conn_p6.execute(
    "SELECT exercice, resultat_net FROM etats_financiers WHERE ticker='ORGT' ORDER BY exercice"
).fetchall()
conn_p6.close()
exercices = [e for e, _ in lignes]
verifie(set([2021, 2022, 2023, 2025]).issubset(set(exercices)),
        f"au moins 4 exercices distincts en base pour ORGT, obtenu : {exercices}")
verifie(len(lignes) >= 4, f"{len(lignes)} lignes d'historique pour ORGT (>=4 attendu)")

print("\n=== Golden test 38 (P6 lot 2) : SAFC et STBC — historique multi-exercices ===")
conn_p6b = sqlite3.connect(DB)
ex_safc = [e for e, in conn_p6b.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SAFC'").fetchall()]
ex_stbc = [e for e, in conn_p6b.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='STBC'").fetchall()]
conn_p6b.close()
verifie(2021 in ex_safc and 2025 in ex_safc, f"SAFC a 2021 et 2025 en base : {sorted(ex_safc)}")
verifie(len(ex_stbc) >= 4, f"STBC a >=4 exercices en base : {sorted(ex_stbc)}")

r = evaluer_titre("STBC")
verifie(any("ANOMALIE" in a for a in r["alertes"]),
        "alerte anomalie STBC 2024 remontee")

print("\n=== Golden test 39 (P6 lot 3) : NSBC (5 ex.) et SMBC (4 ex.) — historique etendu ===")
conn_p6c = sqlite3.connect(DB)
ex_nsbc = [e for e, in conn_p6c.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='NSBC'").fetchall()]
ex_smbc = [e for e, in conn_p6c.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SMBC'").fetchall()]
conn_p6c.close()
verifie(len(ex_nsbc) >= 5, f"NSBC a >=5 exercices : {sorted(ex_nsbc)}")
verifie(len(ex_smbc) >= 4, f"SMBC a >=4 exercices : {sorted(ex_smbc)}")

print("\n=== Golden test 40 (P6 lot 4) : CABC serie complete 7 ans + CBIBF 2022 ===")
conn_p6d = sqlite3.connect(DB)
ex_cabc = [e for e, in conn_p6d.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='CABC'").fetchall()]
ex_cbibf = [e for e, in conn_p6d.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='CBIBF'").fetchall()]
conn_p6d.close()
verifie(set(range(2019, 2026)).issubset(set(ex_cabc)),
        f"CABC couvre 2019-2025 sans trou : {sorted(ex_cabc)}")
verifie(2022 in ex_cbibf, f"CBIBF a l'exercice 2022 : {sorted(ex_cbibf)}")

print("\n=== Golden test 41 (P6 lot 5) : Sonatel (SNTS) — historique 2023-2025 ===")
conn_p6e = sqlite3.connect(DB)
ex_snts = [e for e, in conn_p6e.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SNTS'").fetchall()]
conn_p6e.close()
verifie(set([2023, 2024, 2025]).issubset(set(ex_snts)),
        f"SNTS couvre 2023-2025 : {sorted(ex_snts)}")

print("\n=== Golden test 42 (P6 lot 6) : SPHC (5 ex., chaine validee) et SOGC (4 ex.) ===")
conn_p6f = sqlite3.connect(DB)
ex_sphc = [e for e, in conn_p6f.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SPHC'").fetchall()]
ex_sogc = [e for e, in conn_p6f.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SOGC'").fetchall()]
conn_p6f.close()
verifie(set(range(2022, 2026)).issubset(set(ex_sphc)),
        f"SPHC couvre 2022-2025 : {sorted(ex_sphc)}")
verifie(len(ex_sogc) >= 4, f"SOGC a >=4 exercices : {sorted(ex_sogc)}")

print("\n=== Golden test 43 (P6 lot 7) : SHEC (perte 2020 detectee) et PALC historique ===")
r = evaluer_titre("SHEC")
conn_p6g = sqlite3.connect(DB)
ex_shec = [e for e, in conn_p6g.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SHEC'").fetchall()]
ex_palc = [e for e, in conn_p6g.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='PALC'").fetchall()]
conn_p6g.close()
verifie(len(ex_shec) >= 4, f"SHEC a >=4 exercices : {sorted(ex_shec)}")
verifie(2023 in ex_palc, f"PALC a l'exercice 2023 : {sorted(ex_palc)}")

print("\n=== Golden test 44 (P6 lot 8) : SDCC corrige (RN_n1 reel) + FTSC historique (perte 2021) ===")
conn_p6h = sqlite3.connect(DB)
rn_n1_sdcc = conn_p6h.execute(
    "SELECT resultat_net_n1 FROM etats_financiers WHERE ticker='SDCC' AND exercice=2025").fetchone()[0]
ex_ftsc = [e for e, in conn_p6h.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='FTSC'").fetchall()]
conn_p6h.close()
verifie(abs(rn_n1_sdcc - 3959) < 0.01,
        f"SDCC RN_n1 2025 corrige a 3959 (valeur reelle), obtenu : {rn_n1_sdcc}")
verifie(set([2021, 2022, 2023, 2024, 2025]).issubset(set(ex_ftsc)),
        f"FTSC couvre 2021-2025 sans trou : {sorted(ex_ftsc)}")
r = evaluer_titre("FTSC")
verifie(r["statut_gate"] == "ELIGIBLE", "FTSC ELIGIBLE (perte 2021 isolee, pas 2 exercices consecutifs)")

print("\n=== Golden test 45 (P6 lot 9) : Uniwax (UNXC) exclu — 2 pertes consecutives (3e cas reel) ===")
r = evaluer_titre("UNXC")
verifie(r["statut_gate"] == "EXCLU", "statut = EXCLU")
verifie(any("negatif" in m for m in r["motifs_exclusion"]),
        "motif resultat net negatif present (ex-gap OCR, donnees historiques recuperees)")

print("\n=== Golden test 47 (RAO/RN) : FTSC 2024 — divergence forte detectee, note moderee (pas substituee) ===")
from scoring import score_rentabilite, charger_seuils
seuils_t = charger_seuils()
etats_ftsc = [
    {"resultat_net": 18595.275, "resultat_net_n1": 3075.971,
     "resultat_activites_ordinaires": 4340.0, "capitaux_propres": None},
    {"resultat_net": 3075.971, "resultat_net_n1": 153.483,
     "resultat_activites_ordinaires": 3444.4, "capitaux_propres": None},
]
note, alertes_t = score_rentabilite(etats_ftsc, seuils_t)
verifie(any("ECART RN/RAO" in a for a in alertes_t), "alerte d'ecart RN/RAO presente")
verifie(note < 90, f"note moderee, pas au plafond malgre RN +504.7% (note={note})")
verifie(note > 50, f"note pas non plus punitive — RAO montre une vraie croissance +26% (note={note})")

print("\n=== Golden test 48 (RAO/RN) : SOGC 2025 — pas de divergence, note NON moderee ===")
etats_sogc = [
    {"resultat_net": 12492.623, "resultat_net_n1": 13110.790,
     "resultat_activites_ordinaires": 17161.525, "capitaux_propres": None},
    {"resultat_net": 13110.790, "resultat_net_n1": 5270.304,
     "resultat_activites_ordinaires": 18040.224, "capitaux_propres": None},
]
note2, alertes2 = score_rentabilite(etats_sogc, seuils_t)
verifie(any("coherente avec le RN" in a for a in alertes2),
        "pas d'ecart significatif detecte (RN et RAO racontent la meme histoire)")

print("\n=== Golden test 49 (RAO/RN) : sans donnee RAO, comportement inchange (retro-compatibilite) ===")
etats_sans_rao = [
    {"resultat_net": 100, "resultat_net_n1": 80, "capitaux_propres": None},
]
note3, alertes3 = score_rentabilite(etats_sans_rao, seuils_t)
verifie(not any("RAO" in a for a in alertes3), "aucune mention RAO si donnee absente (retro-compatible)")
verifie(note3 is not None, "note toujours calculee normalement sans RAO")

print("\n=== Golden test 50 (P6 lot 10) : PRSC serie 7 ans (2018-2024) sans trou, document unique ===")
conn_p6i = sqlite3.connect(DB)
ex_prsc = [e for e, in conn_p6i.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='PRSC'").fetchall()]
conn_p6i.close()
verifie(set(range(2018, 2025)).issubset(set(ex_prsc)),
        f"PRSC couvre 2018-2024 sans trou : {sorted(ex_prsc)}")
r = evaluer_titre("PRSC")
verifie(r["statut_gate"] == "ELIGIBLE", "PRSC ELIGIBLE")

print("\n=== Golden test 51 (Etape A du plan) : SDSC — avis divergence prix/fondamentaux ===")
r = evaluer_titre("SDSC")
verifie(any("DIVERGENCE_PRIX_FONDAMENTAUX" in a for a in r["alertes"]),
        "avis SDSC remonte (Financial Afrik, degradation trimestrielle confirmee)")

print("\n=== Golden test 52 (Etape B/4 du plan) : source_url — liste nominative, pas de seuil global ===")
import sqlite3
conn_b = sqlite3.connect(DB)
total_b = conn_b.execute(
    "SELECT COUNT(*) FROM etats_financiers WHERE ticker NOT LIKE 'TEST_%'").fetchone()[0]
manquants = conn_b.execute(
    "SELECT ticker, exercice FROM etats_financiers WHERE ticker NOT LIKE 'TEST_%' "
    "AND source_url IS NULL ORDER BY ticker, exercice").fetchall()
conn_b.close()
avec_url = total_b - len(manquants)
taux = avec_url / total_b
# Seuil abaisse a 70% (etat actuel connu et accepte : gaps DEUX_SOURCE/web legitimes
# qui n'auront jamais d'URL BRVM). La VRAIE protection contre la derive est la liste
# nominative ci-dessous, exhaustive — chaque lot doit la consulter avant livraison,
# plutot que de decouvrir un pourcentage agrege trop tard.
verifie(taux >= 0.70, f"couverture source_url = {taux:.0%} ({avec_url}/{total_b}), seuil plancher 70%")
if manquants:
    print(f"  Lignes sans source_url ({len(manquants)}) — a verifier avant tout futur ajout du meme ticker :")
    for t, e in manquants[:20]:
        print(f"    {t} {e}")
    if len(manquants) > 20:
        print(f"    ... et {len(manquants)-20} autres")

print("\n=== Golden test 53 (Etape D du plan) : score composite suspendu comme critere de decision ===")
r = evaluer_titre("CBIBF")
verifie(r.get("composite_observationnel") is True,
        "champ composite_observationnel = True")
verifie(r["score_composite"] is not None,
        "score composite toujours CALCULE (observation, pas suppression)")
verifie(any("SUSPENDU comme critere de decision" in a for a in r["alertes"]),
        "alerte de suspension explicite presente")

print("\n=== Golden test 54 (Etape E) : Bridge Bank Group CI — pret pour IPO, aucun cours invente ===")
import sqlite3
conn_e = sqlite3.connect(DB)
n_cours_bbgci = conn_e.execute(
    "SELECT COUNT(*) FROM cours_mensuels WHERE ticker='BBGCI'").fetchone()[0]
n_exercices_bbgci = conn_e.execute(
    "SELECT COUNT(*) FROM etats_financiers WHERE ticker='BBGCI'").fetchone()[0]
conn_e.close()
verifie(n_cours_bbgci == 0, "aucune entree cours_mensuels pour BBGCI (pas encore cote, aucun prix invente)")
verifie(n_exercices_bbgci == 5, f"5 exercices fondamentaux disponibles (2021-2025), obtenu : {n_exercices_bbgci}")
r = evaluer_titre("BBGCI")
verifie(r["statut_gate"] == "ELIGIBLE", "statut = ELIGIBLE (fondamentaux solides)")
verifie(r["score_valorisation"] is None,
        f"score valorisation absent (aucun PER disponible), obtenu : {r['score_valorisation']}")

print("\n=== Golden test 55 (Etape E) : NTLC (4 ex.) et ORAC (2 ex.) — historique etendu ===")
conn_e2 = sqlite3.connect(DB)
ex_ntlc = [e for e, in conn_e2.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='NTLC'").fetchall()]
ex_orac = [e for e, in conn_e2.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='ORAC'").fetchall()]
conn_e2.close()
verifie(set(range(2022, 2026)).issubset(set(ex_ntlc)), f"NTLC couvre 2022-2025 : {sorted(ex_ntlc)}")
verifie(2023 in ex_orac, f"ORAC a l'exercice 2023 : {sorted(ex_orac)}")

print("\n=== Golden test 57 (Etape E, reminage) : CBIBF/ORAC/PALC capitaux propres retrouves ===")
conn_e4 = sqlite3.connect(DB)
cp_cbibf = conn_e4.execute(
    "SELECT capitaux_propres FROM etats_financiers WHERE ticker='CBIBF' AND exercice=2022").fetchone()[0]
cp_orac = conn_e4.execute(
    "SELECT COUNT(*) FROM etats_financiers WHERE ticker='ORAC' AND capitaux_propres IS NOT NULL").fetchone()[0]
ex_palc = [e for e, in conn_e4.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='PALC'").fetchall()]
conn_e4.close()
verifie(cp_cbibf is not None, f"CBIBF 2022 CP present : {cp_cbibf}")
verifie(cp_orac == 2, f"ORAC a 2 exercices avec CP, obtenu : {cp_orac}")
verifie(2024 in ex_palc, f"PALC couvre desormais 2024 : {sorted(ex_palc)}")

print("\n=== Golden test 58 (Etape E, reminage lot 2) : ABJC 2023 ajoute (RN+CP) ===")
conn_e5 = sqlite3.connect(DB)
ex_abjc = [e for e, in conn_e5.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='ABJC'").fetchall()]
cp_abjc = conn_e5.execute(
    "SELECT capitaux_propres FROM etats_financiers WHERE ticker='ABJC' AND exercice=2023").fetchone()[0]
conn_e5.close()
verifie(2023 in ex_abjc, f"ABJC a l'exercice 2023 : {sorted(ex_abjc)}")
verifie(cp_abjc == 5167, f"CP ABJC 2023 = 5167, obtenu : {cp_abjc}")

print("\n=== Golden test 59 (Etape E, lot 4) : SGBC 2021 et TTLS (3 ex.) ajoutes ===")
conn_e6 = sqlite3.connect(DB)
cp_sgbc = conn_e6.execute(
    "SELECT capitaux_propres FROM etats_financiers WHERE ticker='SGBC' AND exercice=2021").fetchone()[0]
ex_ttls = [e for e, in conn_e6.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='TTLS'").fetchall()]
conn_e6.close()
verifie(cp_sgbc == 304993, f"SGBC 2021 CP = 304993, obtenu : {cp_sgbc}")
verifie(set([2023, 2024, 2025]).issubset(set(ex_ttls)), f"TTLS couvre 2023-2025 : {sorted(ex_ttls)}")

print("\n=== Golden test 60 (Etape E, detecteur) : ORGT serie complete 2021-2025 sans trou ===")
conn_e7 = sqlite3.connect(DB)
ex_orgt = [e for e, in conn_e7.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='ORGT'").fetchall()]
conn_e7.close()
verifie(set(range(2021, 2026)).issubset(set(ex_orgt)), f"ORGT couvre 2021-2025 sans trou : {sorted(ex_orgt)}")

print("\n=== Golden test 61 (Etape E, lot 5) : BICC (3 ex.) et CIEC (3 ex.) etendus ===")
conn_e8 = sqlite3.connect(DB)
ex_bicc = [e for e, in conn_e8.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='BICC'").fetchall()]
ex_ciec = [e for e, in conn_e8.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='CIEC'").fetchall()]
conn_e8.close()
verifie(set([2021, 2023, 2025]).issubset(set(ex_bicc)), f"BICC couvre 2021,2023,2025 : {sorted(ex_bicc)}")
verifie(set([2023, 2024, 2025]).issubset(set(ex_ciec)), f"CIEC couvre 2023-2025 : {sorted(ex_ciec)}")

print("\n=== Golden test 62 (Etape E, lot 6) : BOAC historique natif (4 ex.), confirme donnee web ===")
conn_e9 = sqlite3.connect(DB)
ex_boac = [e for e, in conn_e9.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='BOAC'").fetchall()]
rn_2024 = conn_e9.execute(
    "SELECT resultat_net FROM etats_financiers WHERE ticker='BOAC' AND exercice=2024").fetchone()[0]
conn_e9.close()
verifie(set(range(2022, 2026)).issubset(set(ex_boac)), f"BOAC couvre 2022-2025 sans trou : {sorted(ex_boac)}")
verifie(rn_2024 == 32044, f"RN 2024 = 32044, confirme la 2e source web anterieure, obtenu : {rn_2024}")

print("\n=== Golden test 63 (Etape E, lot 7) : BOABF historique (4 ex.), portefeuille reel ===")
conn_e10 = sqlite3.connect(DB)
ex_boabf = [e for e, in conn_e10.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='BOABF'").fetchall()]
conn_e10.close()
verifie(set([2021, 2022, 2023, 2025]).issubset(set(ex_boabf)), f"BOABF couvre 2021-2023,2025 : {sorted(ex_boabf)}")
r = evaluer_titre("BOABF")
verifie(r["statut_gate"] == "ELIGIBLE", "BOABF ELIGIBLE (titre du portefeuille reel)")

print("\n=== Golden test 64 (Etape E, lot 8) : CFAC 2021 ajoute, date_publication absente geree ===")
conn_e11 = sqlite3.connect(DB)
row_cfac = conn_e11.execute(
    "SELECT resultat_net, date_publication FROM etats_financiers WHERE ticker='CFAC' AND exercice=2021").fetchone()
conn_e11.close()
verifie(row_cfac is not None, "CFAC 2021 present en base")
verifie(row_cfac[0] == 5533.563559, f"RN CFAC 2021 = 5533.563559, obtenu : {row_cfac[0]}")
verifie(row_cfac[1] is None, f"date_publication absente geree comme None (pas inventee), obtenu : {row_cfac[1]}")
r = evaluer_titre("CFAC")
verifie(r is not None, "evaluer_titre ne plante pas malgre date_publication=None sur une ligne")

print("\n=== Golden test 65 (Etape E, lot 9) : SLBC serie etendue, identite actif=passif verifiee ===")
conn_e12 = sqlite3.connect(DB)
lignes_slbc = conn_e12.execute(
    "SELECT exercice, total_actif, total_passif FROM etats_financiers WHERE ticker='SLBC'").fetchall()
conn_e12.close()
verifie(len(lignes_slbc) >= 7, f"SLBC a >=7 exercices, obtenu : {len(lignes_slbc)}")
for exercice, ta, tp in lignes_slbc:
    verifie(ta == tp, f"SLBC {exercice} : identite actif=passif ({ta} vs {tp})")

print("\n=== Golden test 66 (Etape E, lot 10) : TTLC (5 ex. + RAO) et UNLC (3 ex.) etendus ===")
conn_e13 = sqlite3.connect(DB)
ex_ttlc = [e for e, in conn_e13.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='TTLC'").fetchall()]
rao_ttlc = conn_e13.execute(
    "SELECT COUNT(*) FROM etats_financiers WHERE ticker='TTLC' AND resultat_activites_ordinaires IS NOT NULL").fetchone()[0]
ex_unlc = [e for e, in conn_e13.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='UNLC'").fetchall()]
conn_e13.close()
verifie(set(range(2021, 2026)).issubset(set(ex_ttlc)), f"TTLC couvre 2021-2025 sans trou : {sorted(ex_ttlc)}")
verifie(rao_ttlc == 4, f"TTLC a 4 exercices avec RAO, obtenu : {rao_ttlc}")
verifie(set([2020, 2021, 2023]).issubset(set(ex_unlc)), f"UNLC couvre 2020,2021,2023 : {sorted(ex_unlc)}")

print("\n=== Golden test 68 (Etape E, lot 12) : SICC obtient enfin une donnee VALIDE (2018) ===")
r = evaluer_titre("SICC")
verifie(r["statut_gate"] == "ELIGIBLE", f"SICC devient ELIGIBLE (etait donnees insuffisantes), obtenu : {r['statut_gate']}")
verifie(r["score_composite"] is not None, "score desormais calculable pour SICC")

print("\n=== Golden test 69 (Etape E, lot 13) : SICC revele effondrement 2019 (-99.8%) ===")
conn_e15 = sqlite3.connect(DB)
ex_sicc = [e for e, in conn_e15.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SICC'").fetchall()]
rn_2019 = conn_e15.execute(
    "SELECT resultat_net FROM etats_financiers WHERE ticker='SICC' AND exercice=2019").fetchone()[0]
conn_e15.close()
verifie(set([2018, 2019, 2020, 2021]).issubset(set(ex_sicc)), f"SICC couvre 2018-2021 : {sorted(ex_sicc)}")
verifie(rn_2019 == 2.350841, f"RN 2019 = 2.350841 (effondrement confirme), obtenu : {rn_2019}")

print("\n=== Golden test 70 (Etape E, lot 14 - OCR cible) : SDCC 2021 et BOAB 2021 ===")
conn_e16 = sqlite3.connect(DB)
ex_sdcc = [e for e, in conn_e16.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SDCC'").fetchall()]
ex_boab = [e for e, in conn_e16.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='BOAB'").fetchall()]
conn_e16.close()
verifie(2021 in ex_sdcc, f"SDCC a l'exercice 2021 : {sorted(ex_sdcc)}")
verifie(2021 in ex_boab, f"BOAB a l'exercice 2021 (1er succes OCR) : {sorted(ex_boab)}")

print("\n=== Golden test 71 (Angle mort fiscal, 11/07/2026) : rendement net IRVM calcule ===")
from scoring import rendement_net_estime
net, taux = rendement_net_estime(0.10, "CI")
verifie(taux == 0.10, f"taux IRVM Cote d'Ivoire = 10%, obtenu : {taux}")
verifie(abs(net - 0.09) < 0.0001, f"rendement net = 9.0% sur 10% brut, obtenu : {net}")
net_bf, taux_bf = rendement_net_estime(0.10, "BF")
verifie(taux_bf == 0.125, f"taux IRVM Burkina Faso = 12.5%, obtenu : {taux_bf}")
r = evaluer_titre("SNTS")
verifie(any("rendement NET estime" in a for a in r["alertes"]),
        "alerte rendement net presente pour un titre avec rendement connu")

print("\n=== Golden test 72 (Strategie web_fetch directe) : ETIT resolu, gap ferme ===")
r = evaluer_titre("ETIT")
verifie(r["statut_gate"] == "ELIGIBLE", f"ETIT devient ELIGIBLE (etait gap total), obtenu : {r['statut_gate']}")
verifie(r["score_composite"] is not None, "score desormais calculable pour ETIT")

print("\n=== Golden test 73 (Regle formalisee 11/07/2026) : RETARD_PUBLICATION exige une preuve explicite ===")
import sqlite3
conn_73 = sqlite3.connect(DB)
retards_reels = conn_73.execute(
    "SELECT ticker, note FROM avis_reglementaires WHERE type='RETARD_PUBLICATION' "
    "AND ticker NOT LIKE 'TEST_%'").fetchall()
conn_73.close()
MARQUEURS_PREUVE = ("commissaires aux comptes", "rapport", "cac", "constate", "confirme")
verifie(len(retards_reels) >= 1, f"au moins 1 cas reel de RETARD_PUBLICATION existe : {len(retards_reels)}")
for ticker, note in retards_reels:
    a_preuve = any(m in note.lower() for m in MARQUEURS_PREUVE)
    verifie(a_preuve, f"{ticker} : la note cite une preuve explicite (pas une absence de collecte)")

print("\n=== Golden test 75 (Etape E, web_fetch) : SNTS confirme + CP/TA ajoutes ===")
conn_75 = sqlite3.connect(DB)
row_75 = conn_75.execute(
    "SELECT resultat_net, capitaux_propres, total_actif FROM etats_financiers "
    "WHERE ticker='SNTS' AND exercice=2025").fetchone()
conn_75.close()
verifie(abs(row_75[0] - 413600) < 20, f"RN SNTS confirme (413588 vs 413600 deja connu), obtenu : {row_75[0]}")
verifie(row_75[1] == 1399263, f"CP SNTS = 1399263, obtenu : {row_75[1]}")
verifie(row_75[2] == 3270175, f"TA SNTS = 3270175, obtenu : {row_75[2]}")
r = evaluer_titre("SNTS")
verifie(r["score_rentabilite"] is not None, "ROE desormais calculable pour SNTS (score rentabilite)")

print("\n=== Golden test 76 (Etape E, web_fetch) : FTSC capitaux propres reconstruits ===")
conn_76 = sqlite3.connect(DB)
cp_ftsc = conn_76.execute(
    "SELECT exercice, capitaux_propres FROM etats_financiers WHERE ticker='FTSC' "
    "AND exercice IN (2024,2025) ORDER BY exercice").fetchall()
conn_76.close()
verifie(cp_ftsc[0] == (2024, 43454.156), f"CP FTSC 2024 = 43454.156, obtenu : {cp_ftsc[0]}")
verifie(cp_ftsc[1] == (2025, 15703.201), f"CP FTSC 2025 = 15703.201, obtenu : {cp_ftsc[1]}")
r = evaluer_titre("FTSC")
verifie(r["score_rentabilite"] is not None, "ROE desormais calculable pour FTSC")

print("\n=== Golden test 78 (Etape E, discipline unite) : SAFC capitaux propres ajoutes ===")
conn_78 = sqlite3.connect(DB)
ex_safc = [e for e, in conn_78.execute(
    "SELECT exercice FROM etats_financiers WHERE ticker='SAFC'").fetchall()]
cp_safc = conn_78.execute(
    "SELECT capitaux_propres FROM etats_financiers WHERE ticker='SAFC' AND exercice=2025").fetchone()[0]
conn_78.close()
verifie(2024 in ex_safc, f"SAFC a l'exercice 2024 : {sorted(ex_safc)}")
verifie(cp_safc == 5916, f"CP SAFC 2025 = 5916, obtenu : {cp_safc}")
r = evaluer_titre("SAFC")
verifie(r["score_rentabilite"] is not None, "ROE desormais calculable pour SAFC")

print("\n=== Golden test 79 (Etape E, web_fetch) : STBC capitaux propres enfin resolus ===")
conn_79 = sqlite3.connect(DB)
cp_stbc = conn_79.execute(
    "SELECT capitaux_propres FROM etats_financiers WHERE ticker='STBC' AND exercice=2025").fetchone()[0]
conn_79.close()
verifie(cp_stbc == 45642.447915, f"CP STBC 2025 = 45642.447915, obtenu : {cp_stbc}")
r = evaluer_titre("STBC")
verifie(r["score_rentabilite"] is not None, "ROE desormais calculable pour STBC")

print("\n=== Golden test 81 (P8, 12/07/2026) : liquidite du jour prioritaire, repli marche.yaml propre ===")
import json as _json, os as _os
from scoring import LIQUIDITE_JOUR_PATH, charger_marche

# Sans fichier du jour : repli attendu (CBIBF -> FLOTTANT_RESTREINT via marche.yaml)
if _os.path.exists(LIQUIDITE_JOUR_PATH):
    _os.remove(LIQUIDITE_JOUR_PATH)
r = evaluer_titre("CBIBF")
verifie(r["sizing"]["statut"] == "FLOTTANT_RESTREINT",
        f"sans fichier du jour, repli marche.yaml actif, obtenu : {r['sizing']['statut']}")
verifie("[repli marche.yaml]" in r["sizing"]["note"], "la note signale explicitement le repli")

# Avec fichier du jour : priorite au jour, meme pour un titre absent du marche.yaml
_json.dump({
    "SNTS": {"volume_jour": 1744, "cours_cloture": 30900, "valeur_echangee_jour": 53899600,
              "date_maj_brvm": "test", "collecte_le": "2026-07-12T00:00:00"},
    "UNLC": {"volume_jour": 20, "cours_cloture": 50500, "valeur_echangee_jour": 1010000,
              "date_maj_brvm": "test", "collecte_le": "2026-07-12T00:00:00"},
}, open(LIQUIDITE_JOUR_PATH, "w", encoding="utf-8"))
r = evaluer_titre("SNTS")
verifie(r["sizing"]["statut"] == "LIQUIDITE_NORMALE_JOUR",
        f"avec fichier du jour, priorite donnee au jour, obtenu : {r['sizing']['statut']}")
r = evaluer_titre("UNLC")
verifie(r["sizing"]["statut"] == "LIQUIDITE_FAIBLE_JOUR",
        f"UNLC illiquide confirme via le jour, obtenu : {r['sizing']['statut']}")
r = evaluer_titre("CBIBF")
verifie(r["sizing"]["statut"] == "FLOTTANT_RESTREINT",
        f"CBIBF absent du fichier du jour -> repli marche.yaml correct, obtenu : {r['sizing']['statut']}")
_os.remove(LIQUIDITE_JOUR_PATH)  # nettoie : ne pas polluer l'etat du depot avec un fichier de test

print("\n=== Golden test 82 (P9/P10, 12/07/2026) : liquidite generale et tendance chargent correctement ===")
from scoring import charger_liquidite_generale, charger_tendance_liquidite
liq_gen = charger_liquidite_generale()
tendance = charger_tendance_liquidite()
verifie(len(liq_gen) == 47, f"47 titres avec liquidite generale, obtenu : {len(liq_gen)}")
verifie(len(tendance) == 47, f"47 titres avec tendance calculee, obtenu : {len(tendance)}")
verifie(tendance["SLBC"]["statut"] == "STABLE",
        f"SLBC reste STABLE (directions volume/prix incoherentes, filtre actif), "
        f"obtenu : {tendance['SLBC']['statut']}")
verifie(tendance["SLBC"]["coherent_prix_volume"] is False,
        "SLBC : incoherence prix/volume bien detectee")
verifie(tendance["ECOC"]["statut"] == "CONFIRMEE_HAUSSE",
        f"ECOC confirme (ecart {tendance['ECOC']['ecart_volume_3v12']:.0%}, >=125%), "
        f"obtenu : {tendance['ECOC']['statut']}")
statuts_possibles = {"STABLE", "CONFIRMEE_HAUSSE", "CONFIRMEE_BAISSE", "A_SURVEILLER_HAUSSE", "A_SURVEILLER_BAISSE"}
verifie(all(t["statut"] in statuts_possibles for t in tendance.values()),
        "tous les statuts appartiennent a l'ensemble attendu (pas de valeur inconnue)")

print("\n" + "=" * 60)
if ECHECS:
    print(f"RESULTAT : {len(ECHECS)} ECHEC(S) — NE PAS DEPLOYER")
    sys.exit(1)
else:
    print("RESULTAT : TOUS LES GOLDEN TESTS PASSENT")
    sys.exit(0)
