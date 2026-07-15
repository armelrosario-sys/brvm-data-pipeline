#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Peuplement de la base BRVM avec :
   - les 9 titres du pilote P3, donnees REELLES issues de l'extraction + 2e source
   - 2 cas SYNTHETIQUES clairement etiquetes (prefixe TEST_), pour valider que le
     moteur de gate exclut correctement des profils degrades qu'aucun titre reel
     du pilote ne presentait actuellement.
Toute valeur ci-dessous est tracee a sa source (extraction directe ou 2e source
web, cf. document de reference section 12).

REGLE D'UNITE (formalisee 11/07/2026, suite audit AUDCIF/SYSCOHADA) : avant
toute extraction, LIRE la mention d'unite ecrite sur le document lui-meme
("en milliers de F CFA" ou "en millions FCFA", quasi toujours presente en
en-tete du bilan) — JAMAIS la deviner ou la supposer par habitude. Pattern
observe et confirme sur de nombreux documents cette session : comptes
individuels SYSCOHADA -> quasi systematiquement en MILLIERS (ex. FTSC,
Unilever CI) ; comptes consolides IFRS des grands groupes cotes (article 8
AUDCIF) -> en MILLIONS (ex. Sonatel, ETI). Ce n'est pas arbitraire, c'est
correle au referentiel comptable utilise. Toute ligne ETATS ajoutee doit
pouvoir tracer, dans son commentaire, la mention d'unite trouvee dans le
document source. Le controle croise (rapport_ordre_grandeur, scoring.py)
reste un FILET DE SECURITE en second rang, jamais le mecanisme principal.
"""
import sqlite3, json
from datetime import date

from pathlib import Path
_BASE = Path(__file__).resolve().parent
DB = str(_BASE / "brvm.db")

SOCIETES = [
    # ticker, nom, secteur, referentiel, pays, intro, controle
    ("SNTS", "Sonatel", "TELECOMMUNICATIONS", "SYSCOHADA", "SN", None, "Orange MEA (majoritaire)"),
    ("STBC", "Sitab", "CONSOMMATION_DE_BASE", "SYSCOHADA", "CI", None, None),
    ("NSBC", "NSIA Banque CI", "SERVICES_FINANCIERS", "BANCAIRE_UMOA", "CI", None, None),
    ("SMBC", "SMB CI", "ENERGIE", "SYSCOHADA", "CI", None, None),
    ("SAFC", "Safca (Alios Finance CI)", "SERVICES_FINANCIERS", "BANCAIRE_UMOA", "CI", None, None),
    ("ORGT", "Oragroup Togo", "SERVICES_FINANCIERS", "IFRS", "TG", None, "ECP Financial Holdings (50,01%)"),
    ("BOABF", "BOA Burkina Faso", "SERVICES_FINANCIERS", "BANCAIRE_UMOA", "BF", None, "Groupe BOA/BMCE"),
    ("BBGCI", "Bridge Bank Group CI", "SERVICES_FINANCIERS", "BANCAIRE_UMOA", "CI", "2026-08-21",
     "Bridge Group West Africa (BGWA) 57% post-IPO, CNPS 20%, flottant BRVM 20%, "
     "divers personnes physiques 3% -- source : Note d'Information IPO visee AMF-UMOA "
     "AO/26-03 du 26/06/2026. CORRECTIF 15/07/2026 : la mention anterieure 'Groupe Teyliom' "
     "etait une erreur (aucune trace de Teyliom dans le document officiel ; confusion "
     "probable avec un autre dossier). date_introduction = 21/08/2026 : ESTIMATION, pas une "
     "date de cotation confirmee -- la note precise seulement la periode de placement "
     "(20/07-06/08/2026) et une date de 'transmission du calendrier indicatif de premiere "
     "cotation' (21/08/2026, dans un tableau partiellement degrade a l'extraction). "
     "A RECONFIRMER des qu'un avis BRVM officiel de premiere cotation sera publie."),
    # PAS ENCORE COTE au 10/07/2026 — IPO en cours (periode de placement 20/07-06/08/2026,
    # premiere cotation attendue ~1 mois apres). Ticker "BBGCI" provisoire (non confirme par
    # mnemonique officiel BRVM, ISIN CI0000010609 connu). Ajoute en preparation, etape E du
    # plan de marche (10/07/2026) — donnees fondamentales sourcees a la note d'information
    # visee AMF-UMOA n(deg) AO/26-03 du 26/06/2026, AUCUNE donnee cours_mensuels (le prix
    # d'offre 6750 FCFA n'est PAS un cours de marche, ne jamais l'utiliser comme tel).
    ("CBIBF", "Coris Bank International", "SERVICES_FINANCIERS", "BANCAIRE_UMOA", "BF", "2016-12-23", "Coris Holding (63,61%)"),
    ("SICC", "Sicor", "CONSOMMATION_DE_BASE", "SYSCOHADA", "CI", None, None),
    # --- Reste de l'univers (47 titres) : secteur reel extrait du BOC 07/07/2026
    # (collecte/secteurs_boc.json), donnees financieres detaillees non encore
    # collectees (R6, a venir) — permet des a present un calcul sectoriel
    # reproductible sur PER/rendement (R5) plutot qu'une valeur figee non tracee.
    ("NTLC", "Nestle CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("PALC", "Palm CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("SPHC", "Saph CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("TTLC", "TotalEnergies Marketing CI", "ENERGIE", None, "CI", None, None),
    ("TTLS", "TotalEnergies Marketing SN", "ENERGIE", None, "SN", None, None),
    ("ECOC", "Ecobank Cote d'Ivoire", "SERVICES_FINANCIERS", None, "CI", None, None),
    ("SGBC", "Societe Generale Cote d'Ivoire", "SERVICES_FINANCIERS", None, "CI", None, None),
    ("SIBC", "Societe Ivoirienne de Banque", "SERVICES_FINANCIERS", None, "CI", None, None),
    ("ONTBF", "Onatel BF", "TELECOMMUNICATIONS", None, "BF", None, None),
    ("ORAC", "Orange Cote d'Ivoire", "TELECOMMUNICATIONS", None, "CI", None, None),
    ("SCRC", "Sucrivoire", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("SLBC", "Solibra CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("SOGC", "SOGB CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("UNLC", "Unilever CI", "CONSOMMATION_DE_BASE", None, "CI", None, None),
    ("ABJC", "Servair Abidjan", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("BNBC", "Bernabe CI", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("CFAC", "CFAO Motors CI", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("LNBB", "Loterie Nationale du Benin", "CONSOMMATION_DISCRETIONNAIRE", None, "BJ", None, None),
    ("NEIC", "NEI-CEDA CI", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("PRSC", "Tractafric Motors CI", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("UNXC", "Uniwax CI", "CONSOMMATION_DISCRETIONNAIRE", None, "CI", None, None),
    ("SHEC", "Vivo Energy CI", "ENERGIE", None, "CI", None, None),
    ("BICB", "BIIC Benin", "SERVICES_FINANCIERS", None, "BJ", None, None),
    ("BICC", "BICI CI", "SERVICES_FINANCIERS", None, "CI", None, None),
    ("BOAB", "BOA Benin", "SERVICES_FINANCIERS", None, "BJ", None, None),
    ("BOAC", "BOA Cote d'Ivoire", "SERVICES_FINANCIERS", None, "CI", None, None),
    ("BOAM", "BOA Mali", "SERVICES_FINANCIERS", None, "ML", None, None),
    ("BOAN", "BOA Niger", "SERVICES_FINANCIERS", None, "NE", None, None),
    ("BOAS", "BOA Senegal", "SERVICES_FINANCIERS", None, "SN", None, None),
    ("ETIT", "Ecobank Transnational Incorporated Togo", "SERVICES_FINANCIERS", None, "TG", None, None),
    ("CABC", "Sicable CI", "INDUSTRIELS", None, "CI", None, None),
    ("FTSC", "Filtisac CI", "INDUSTRIELS", None, "CI", None, None),
    ("SDSC", "Africa Global Logistics CI", "INDUSTRIELS", None, "CI", None, None),
    ("SEMC", "Eviosys Packaging Siem CI", "INDUSTRIELS", None, "CI", None, None),
    ("SIVC", "Erium CI (ex-Air Liquide CI)", "INDUSTRIELS", None, "CI", None, None),
    ("STAC", "Setao CI", "INDUSTRIELS", None, "CI", None, None),
    ("CIEC", "CIE CI", "SERVICES_PUBLICS", None, "CI", None, None),
    ("SDCC", "Sode CI", "SERVICES_PUBLICS", None, "CI", None, None),
    # --- Cas synthetiques de test (NE SONT PAS des donnees reelles BRVM) ---
    ("TEST_EXCLU", "[SYNTHETIQUE] Titre a exclure", "INDUSTRIELS", "SYSCOHADA", "CI", None, None),
    ("TEST_VIGIL", "[SYNTHETIQUE] Titre en vigilance", "INDUSTRIELS", "SYSCOHADA", "CI", None, None),
]

# ticker, exercice, RN, RN_N1, actif, passif, CP, dettes_fin, payout, solva, source_type, statut, date_pub
ETATS = [
    ("SDSC", 2024, 21068.974, 17138.527, 188126.016, 188126.016, 77808.004, 8324.985, 0.2377, None,
     "NATIF", "VALIDE", "2025-08-29"),  # AJOUT 14/07/2026 (relance SDSC) : PDF officiel certifie
    # "Etats financiers et rapport des CAC - Exercice 2024" (ECR International, signe
    # Abidjan 20/06/2025, depose BRVM 29/08/2025). Verification arithmetique : RN
    # 21068.974 - dividende propose 5008.048 = report a nouveau 16060.926 (exact).
    # Document en MILLIERS de FCFA dans l'original -> converti en millions (/1000)
    # pour coherence avec le reste de la base. CP = Capital + Primes et Reserves +
    # Resultat + Autres capitaux propres (10887.060+45139.150+21068.974+712.820).
    # RAO non retranscrit (tableau compte de resultat trop degrade a l'extraction
    # pour une lecture fiable ligne a ligne) -> laisse a None, integrite > couverture.
    ("SDSC", 2023, 17138.527, 10044, 157733.319, 157733.319, 61747.077, 10733.982, None, None,
     "NATIF", "VALIDE", "2025-08-29"),  # meme document (colonne comparative 2023, certifiee)
    ("SDSC", 2022, 10044, 13942, None, None, None, None, None, None,
     "NATIF", "PROBABLE", None),  # AJOUT 14/07/2026 (relance SDSC) : source = fiche officielle
    # BRVM (page profil emetteur, tableau "indicateurs sur les 3 dernieres annees"),
    # PAS le PDF d'etats financiers complet -> bilan (actif/passif/CP) inconnu ici,
    # d'ou PROBABLE et non VALIDE. CA 86997 M FCFA non stocke (colonne absente du schema,
    # gap connu). date_publication=None : la page profil ne donne pas la date reelle de
    # depot, et en fabriquer une fausserait l'anti-look-ahead documente dans le schema.
    # URL : brvm.org/fr/emetteurs/societes-cotees/africa-global-logistics-agl-cote-divoire
    ("SDSC", 2021, 13942, 13455, None, None, None, None, None, None,
     "NATIF", "PROBABLE", None),  # meme source, meme reserve bilan et date
    ("SDSC", 2020, 13455, None, None, None, None, None, None, None,
     "NATIF", "PROBABLE", None),  # meme source ; pas d'annee anterieure pour RN N-1
    ("ETIT", 2025, 345523, 299708, 19243865, 19243865, 1597846, None, None, None,
     "NATIF", "VALIDE", "2026-04-13"),  # RESOLU 11/07/2026 via web_fetch direct sur brvm.org — page dediee
    # jamais collectee par le robot (gap depuis le debut du projet). Donnees consolidees groupe (part
    # du Groupe seule : RN=236781, CP=1077652 si preference future — convention consolidee retenue ici
    # pour coherence avec CIEC/SDCC deja traites en consolide).
    ("SNTS", 2025, 413588, 393662, 3270175, 3270175, 1399263, None, None, None,
     "NATIF", "VALIDE", "2026-02-16"),  # confirme exactement DEUX_SOURCE (413600~413588) + CP/TA obtenus
    ("STBC", 2025, 36463.616375, 44173.762491, 75047.177792, 75047.177792, 45642.447915, None, 0.800, None,
     "NATIF", "VALIDE", "2026-06-25"),  # CP reconstruit (capital+primes+reserves+report+RN, pas de ligne
    # TOTAL directement libellee). Note : le comparatif 2024 ici (RN=44173.762491, TA=94925.572191)
    # diverge legerement de la ligne 2024 deja en base (RN=44730.358142, TA=94359.747890) — plusieurs
    # versions "annule et remplace" existent pour ce document, ligne 2024 existante non ecrasee
    ("NSBC", 2025, 40712, 38112, 3073062, 3073062, 233300, None, None, None, "DEUX_SOURCE", "VALIDE", "2026-05-13"),
    ("SMBC", 2025, 13075, 8698, 180003, 180003, None, None, None, None, "NATIF", "VALIDE", "2026-05-12"),
    ("SAFC", 2025, 701, -165, 79555, 79555, 5916, None, None, None, "NATIF", "VALIDE", "2026-06-09"),
    ("SAFC", 2024, -165, -603, 74195, 74195, 5215, None, None, None,
     "NATIF", "VALIDE", "2025-07-03"),  # en millions FCFA (mention explicite du document)
    ("ORGT", 2025, 21640, -44400, 4014192, 4014192, 113000, None, 0.0, None, "DEUX_SOURCE", "VALIDE", "2026-05-04"),
    # --- P6/P7 : historique multi-exercices (preuve de concept) ---
    ("ORGT", 2024, -44363, -18186, None, None, 96720, None, None, None,
     "OCR", "PROBABLE", "2025-04-30"),  # comble le trou 2024 detecte par le detecteur ; confirme le 2023
    # deja en base (RN -18186 exact, CP 143822 exact) — OCR propre malgre document scanne
    ("ORGT", 2023, -18186, 19199, 4236478, 4236478, 143822, None, None, None,
     "NATIF", "VALIDE", "2024-04-29"),  # 2e annee de perte consecutive (avec 2024) — decouverte P6
    ("ORGT", 2022, 19199, 19798, None, None, 165995, None, None, None,
     "NATIF", "VALIDE", "2023-04-26"),
    ("ORGT", 2021, 19798, 9440, None, None, 164752, None, None, None,
     "NATIF", "VALIDE", "2022-04-26"),
    ("SAFC", 2021, -603, -1640, 64690, 64690, None, None, None, None,
     "NATIF", "VALIDE", "2022-04-25"),  # 2e annee de perte consecutive (2020-2021), avant redressement 2025
    ("STBC", 2024, 44730.358142, 12399.004223, 94359.747890, 94359.747890, None, None, None, None,
     "NATIF", "VALIDE", "2025-05-07"),  # CONFIRME PAR SOURCAGE (lejecos.com, financialafrik.com, 05/2025) :
    # vraie performance operationnelle (EBE +233%, resultat d'exploitation x3.4), PAS un artefact.
    # Repli -18% en 2025 = vrai cycle d'affaires (pression fiscale tabac accrue), pas un retour d'artefact.
    ("STBC", 2023, 12399.004223, 11503.188097, 35417.065559, 35417.065559, None, None, None, None,
     "NATIF", "VALIDE", "2024-06-05"),
    ("STBC", 2022, 11503.188097, 9642.415475, 31612.312100, 31612.312100, None, None, None, None,
     "NATIF", "VALIDE", "2023-08-14"),
    ("NSBC", 2024, 38112, 34813, 2514388, 2514388, 215330, None, None, None,
     "NATIF", "VALIDE", "2025-03-25"),  # ordre colonnes INVERSE (ancien->recent) sur cette serie de documents —
    # confirme par coherence en chaine entre rapports successifs (decouverte proactive P6)
    ("NSBC", 2023, 34813, 32382, 2037064, 2037064, 189719, None, None, None,
     "NATIF", "VALIDE", "2024-03-28"),
    ("NSBC", 2022, 32382, 23713, 1885056, 1885056, 164905, None, None, None,
     "NATIF", "VALIDE", "2023-03-31"),
    ("NSBC", 2021, 23713, 7201, 1644547, 1644547, 132524, None, None, None,
     "NATIF", "VALIDE", "2022-05-12"),
    ("SMBC", 2023, 17255, 9421, 183993, 183993, 35951, None, None, None,
     "NATIF", "VALIDE", "2024-05-13"),
    ("SMBC", 2022, 9421, 8623, 164780, 164780, 24932, None, None, None,
     "NATIF", "VALIDE", "2023-08-16"),
    ("SMBC", 2024, 8698, 17255, 163113, 163113, 35294, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),
    # --- P6 lot 4 : CABC (serie complete 7 ans, un seul document source) + CBIBF 2022 ---
    ("CABC", 2024, 1375.096, 1134.614, 21797.159, 21797.159, 8677.962, 427.574, 0.381, None,
     "NATIF", "VALIDE", "2026-03-11"),
    ("CABC", 2023, 1134.614, 795.528, 21402.583, 21402.583, 7889.777, 436.992, 0.400, None,
     "NATIF", "VALIDE", "2026-03-11"),
    ("CABC", 2022, 795.528, 695.648, 19534.981, 19534.981, 7090.018, 445.884, 0.571, None,
     "NATIF", "VALIDE", "2026-03-11"),
    ("CABC", 2021, 695.648, 1278.894, 18473.162, 18473.162, 6924.235, 458.336, 1.258, None,
     "NATIF", "VALIDE", "2026-03-11"),  # payout >100% cet exercice (dividende 874.844 vs RN 695.648)
    ("CABC", 2020, 1278.894, 576.556, 14786.028, 14786.028, 7113.911, 471.554, 0.386, None,
     "NATIF", "VALIDE", "2026-03-11"),
    ("CABC", 2019, 576.556, None, 15307.205, 15307.205, 6363.516, 485.004, 0.856, None,
     "NATIF", "VALIDE", "2026-03-11"),  # premiere annee de la serie, pas de comparatif N-1 dans ce document
    ("CBIBF", 2022, 56478, None, 2289034, 2289034, 189815.228513, None, None, None,
     "NATIF", "PROBABLE", "2023-04-27"),  # RN N-1 illisible (texte source corrompu), TA/TP identite confirmee
    ("SNTS", 2024, 393662, 331748, 3105287, 3105287, None, None, None, None,
     "NATIF", "VALIDE", "2025-02-21"),  # coherent avec le N-1 deja stocke pour 2025 (393600, ecart d'arrondi)
    ("SNTS", 2023, 331748, 278912, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2024-02-22"),
    # --- P6 lot 6 : SPHC (chaine 5 ans validee) + SOGC (3 ans) ---
    ("SPHC", 2024, 18790.217905, 3635.138559, 222208.164550, 222208.164550, 122370.184084, None, None, None,
     "NATIF", "VALIDE", "2025-03-19"),  # chaine confirmee, coincide exactement avec le N-1 deja stocke pour 2025
    ("SPHC", 2023, 3635.138559, 16700.611131, 195801.292931, 195801.292931, 105420.142539, None, None, None,
     "NATIF", "VALIDE", "2024-07-18"),
    ("SPHC", 2022, 16700.611131, 20750.470464, 183889.630318, 183889.630318, 103818.410514, None, None, None,
     "NATIF", "VALIDE", "2023-08-02"),
    ("SOGC", 2024, 13110.790, 5270.304, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),  # coherent avec le N-1 deja stocke pour 2025
    ("SOGC", 2023, 5270.304, 15652.983, None, None, None, None, None, None,
     "NATIF", "PROBABLE", "2024-04-29"),  # extraction moins nette (cellule multi-lignes concatenee)
    ("SOGC", 2022, 15652.983, 14728.280, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2023-04-24"),
    # --- P6 lot 7 : SHEC (chaine 6 ans, perte 2020 revelee) + PALC ---
    ("SHEC", 2024, 5353.993378, 4011.602748, 207064.380555, 207064.380555, None, None, None, None,
     "NATIF", "VALIDE", "2025-05-16"),  # coincide exactement avec le N-1 deja stocke pour 2025
    ("SHEC", 2023, 4011.602748, 3548.638458, 169830.273541, 169830.273541, None, None, None, None,
     "NATIF", "VALIDE", "2024-06-06"),
    ("SHEC", 2022, 3548.638458, 2359.622661, 119461.700193, 119461.700193, None, None, None, None,
     "NATIF", "VALIDE", "2023-11-03"),
    ("SHEC", 2021, 2359.622661, -4788.012834, 101262.735128, 101262.735128, None, None, None, None,
     "NATIF", "VALIDE", "2022-09-06"),  # revele une perte en 2020 (COVID probable), redressement continu depuis
    ("PALC", 2024, 15861.643, 19351.846, 202603.319, 202603.319, 135061.151, None, None, None,
     "NATIF", "VALIDE", "2025-04-17"),
    ("PALC", 2023, 19351.846, None, 205938.435, 205938.435, 128875.431, None, None, None,
     "NATIF", "PROBABLE", "2025-04-17"),  # extraction partielle (tableau desorganise), N-2 non capture
    ("BOABF", 2025, 19252, 22419, None, None, 56140, None, 1.037, None, "DEUX_SOURCE", "VALIDE", "2026-03-23"),
    ("BOABF", 2023, 29062.589535, 25476.935672, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2024-03-01"),  # chaine confirmee : 2024=22419.223685 exact vs deja en base
    ("BOABF", 2022, 25476.935672, 21244.692497, 1163299.866414, 1163299.866414, None, None, None, None,
     "OCR", "PROBABLE", "2023-02-23"),
    ("BOABF", 2021, 21244.692497, None, 1073229.476522, 1073229.476522, None, None, None, None,
     "OCR", "PROBABLE", "2023-02-23"),  # donnee N-1 extraite du document exercice 2022 (pas de document
    # 2021 dedie telecharge), pas de N-1 propre a cette ligne
    # NB solvabilite_bancaire BOABF retiree (etait 0.115 = valeur non sourcee egale
    # au seuil reglementaire — violation du principe d'integrite, a lire dans le
    # rapport annuel avant reintegration)
    ("CBIBF", 2025, 65490, 48000, None, None, None, None, 0.44, None, "DEUX_SOURCE", "VALIDE", "2026-07-07"),
    ("SICC", 2024, None, None, None, None, None, None, None, None, "OCR", "PROBABLE", "2026-06-12"),
    ("SICC", 2018, 989.401440, 100.567494, 3933.301419, 3933.301419, None, None, None, None,
     "NATIF", "VALIDE", "2019-06-11"),  # premiere donnee VALIDE pour ce titre, jusque-la sans exercice exploitable
    ("SICC", 2021, 119.234795, 109.826085, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2023-07-06"),  # chaine auto-coherente 2018-2021 (verifiee via 3 documents distincts)
    ("SICC", 2020, 109.826085, 2.350841, 4087.383318, 4087.383318, None, None, None, None,
     "OCR", "PROBABLE", "2023-07-06"),
    ("SICC", 2019, 2.350841, 989.401440, 3925.048002, 3925.048002, None, None, None, None,
     "OCR", "PROBABLE", "2021-11-22"),  # EFFONDREMENT -99.8% vs 2018, coherent avec le differend foncier
    # cocoteraie deja documente (section anterieure du projet) — confirme un vrai evenement, pas un artefact
    # --- R6 lot 1 : Industriels + Services publics (secteurs absents du pilote) ---
    ("CABC", 2025, 1439.474, 1375.096, 23609.026, 23609.026, 9345.551, 417.601, 0.527, None,
     "NATIF", "VALIDE", "2026-03-11"),  # Sicable CI, serie 7 ans, identite exacte
    ("FTSC", 2025, 465.981, 18595.275, 39148.981, 39148.981, 15703.201, None, None, None,
     "NATIF", "VALIDE", "2026-06-10"),  # Filtisac CI ; recul du a un HAO exceptionnel 2024 (alerte a ajouter)
    ("STAC", 2025, -96.558, -348.195, 5446.509, 5446.509, 356.746, 463.307, None, None,
     "OCR", "PROBABLE", "2026-04-10"),  # Setao CI ; pertes 2 exercices consecutifs -> exclusion attendue
    ("STAC", 2024, -348.195, -1117.719, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2025-04-10"),  # confirme exactement le N-1 de 2025 ; revele 4 pertes consecutives
    # (2022-2025), pas 2 comme precedemment documente — exclusion encore mieux fondee
    ("STAC", 2023, -1117.719, -70.544, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2025-04-10"),  # extrait de la colonne N-1 du document 2024
    ("STAC", 2022, -70.544, 1119.448, 15068.263, 15068.263, None, None, None, None,
     "NATIF", "VALIDE", "2023-04-26"),  # premiere annee de perte, apres 2 annees beneficiaires
    ("STAC", 2021, 1119.448, 2320.633, 16260.295, 16260.295, None, None, None, None,
     "NATIF", "VALIDE", "2022-04-26"),
    ("STAC", 2020, 2320.633, None, 18586.404, 18586.404, None, None, None, None,
     "NATIF", "VALIDE", "2021-04-29"),
    ("SDCC", 2025, 4663, 3959, None, None, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-04-14"),  # RN_n1 CORRIGE : 3959 (valeur reelle trouvee dans le document
    # source, remplace l'estimation 3559.5 deduite a tort d'un "+31%" de communique de presse)
    ("SDCC", 2024, 3959, 6127, 433424, 433424, 25798, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),  # IFRS consolide, en milliards FCFA converti en millions
    ("SDCC", 2021, 5184, 4599, None, None, 23956, None, None, None,
     "OCR", "PROBABLE", "2022-04-26"),  # donnees consolidees retenues (document distingue individuel/consolide)
    ("FTSC", 2024, 18595.275, 3075.971, 61061.747, 61061.747, 43454.156, None, None, None,
     "NATIF", "VALIDE", "2025-05-23"),  # pic HAO exceptionnel (deja note en alerte ARTEFACT_COMPTABLE)
    ("FTSC", 2023, 3075.971, 153.483, 50701.178, 50701.178, None, None, None, None,
     "NATIF", "VALIDE", "2024-05-13"),
    ("FTSC", 2022, 153.483, -1276.336, 54851.509, 54851.509, None, None, None, None,
     "NATIF", "VALIDE", "2023-05-11"),
    ("FTSC", 2021, -1276.336, None, 53741.474, 53741.474, None, None, None, None,
     "NATIF", "VALIDE", "2022-05-06"),  # perte 2021, premiere annee de la serie disponible (pas de N-1)
    # --- P6 lot 9 : UNXC (2 pertes consecutives reveelees, ex-gap OCR) ---
    ("UNXC", 2023, -2035.492389, -1298.674972, 38585.032514, 38585.032514, None, None, None, None,
     "NATIF", "VALIDE", "2024-04-30"),  # 2e annee de perte consecutive -> exclusion attendue
    ("UNXC", 2022, -1298.674972, 1400.692889, 39705.901306, 39705.901306, None, None, None, None,
     "NATIF", "VALIDE", "2023-04-28"),
    ("UNXC", 2021, 1400.692889, 231.265060, 37292.681535, 37292.681535, None, None, None, None,
     "NATIF", "VALIDE", "2022-06-13"),
    ("SIVC", 2025, 179.293282, 376.956818, 14611.080094, 14611.080094, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-06-26"),  # Erium CI (ex Air Liquide) ; teste en P3
    # SDSC (Africa Global Logistics) et SEMC (Eviosys) : donnees insuffisantes
    # dans les documents collectes (SDSC = rapport CAC sans bilan chiffre lisible,
    # exercice 2022 seulement ; SEMC = document quasi entierement image, 235 car.
    # natifs) -> pas de ligne etats_financiers, gap documente pour prochain lot.
    # --- R6 lot 2 (partiel) : Consommation discretionnaire ---
    ("ABJC", 2025, 1331, 1515, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2026-04-27"),  # Servair Abidjan, format IFRS, texte brut direct
    ("ABJC", 2023, 1358, 1272, None, None, 5167, None, None, None,
     "NATIF", "VALIDE", "2024-08-19"),
    ("BNBC", 2025, 22.318122, 7.31344, 49140.780873, 49140.780873, 17769.953951, 942.437472, None, None,
     "NATIF", "VALIDE", "2026-04-30"),  # Bernabe CI, identite exacte
    ("CFAC", 2024, 4693.479450, 6399.494092, None, None, None, None, None, None,
     "NATIF", "PROBABLE", "2025-05-16"),  # CFAO Motors CI, exercice 2024 seul dispo, bilan non recoupe (ecart ~4%)
    ("CFAC", 2021, 5533.563559, None, None, None, None, None, None, None,
     "OCR", "PROBABLE", None),  # date de publication absente du nom de fichier (cas rare), non inventee ;
    # document 2022 "provisoire" (non certifie) ; son propre chiffre 2022 (6710.916633) diverge de celui
    # certifie plus tard (6399.494092, cf. ligne 2024 ci-dessus) — ecart documente, seul 2021 retenu ici
    ("NEIC", 2024, -759.371358, 1167.140182, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2025-06-13"),  # Nei-Ceda CI, bascule en perte 2024 vs profit 2023
    # LNBB (aucun document trouve — page de collecte pas encore atteinte),
    # PRSC, UNXC (tableaux illisibles a l'OCR 300 DPI, reprise a plus haute
    # resolution necessaire) : gaps documentes, R6 lot suivant.
    # --- R6 lot 3 : Consommation de base ---
    ("NTLC", 2025, 18426.899479, 18149.967087, 189958.727992, 189958.727992, None, None, 0.503, None,
     "NATIF", "VALIDE", "2026-04-30"),  # Nestle CI, identite exacte, payout sain
    ("NTLC", 2024, 18149.967087, 16556.698463, 177852.053839, 177852.053839, None, None, 0.997, None,
     "NATIF", "VALIDE", "2025-05-05"),
    ("NTLC", 2023, 16556.698463, 16627.044028, 170340.779234, 170340.779234, None, None, 0.9998, None,
     "NATIF", "VALIDE", "2024-04-25"),
    ("NTLC", 2022, 16627.044028, 21268.135622, 173973.911073, 173973.911073, None, None, 1.074, None,
     "NATIF", "VALIDE", "2023-04-24"),  # payout >100% cet exercice (dividende 17855 vs RN 16627, isole)
    ("PALC", 2025, 15508.655, 15861.643, 199116.293, 199116.293, None, None, None, None,
     "NATIF", "VALIDE", "2026-03-23"),  # Palm CI, identite exacte (unite : milliers FCFA supposee)
    ("SPHC", 2025, 24972.070150, 18790.217905, 225842.735644, 225842.735644, None, None, None, None,
     "NATIF", "VALIDE", "2026-03-18"),  # Saph CI, identite exacte, forte croissance
    ("SCRC", 2025, -7953.932, 2473.760, 156426.278, 156426.278, -17243.172, None, None, None,
     "NATIF", "VALIDE", "2026-05-18"),  # Sucrivoire ; CAPITAUX PROPRES NEGATIFS -> exclusion attendue
    ("SCRC", 2023, -10324.162375, -8755.668861, 115465.464814, 115465.464814, None, None, None, None,
     "NATIF", "VALIDE", "2024-05-10"),  # 2 pertes deja en 2022-2023, avant l'aggravation en capitaux
    # propres negatifs de 2025 — profil degrade documente sur une plus longue periode
    ("SLBC", 2025, 45781, 21472, 339517, 339517, None, None, None, None,
     "OCR", "PROBABLE", "2026-05-19"),  # Solibra ; texte natif corrompu, OCR utilise ; +113% confirme par presse (05/2026)
    # TP corrige (etait 307546, la valeur N-1, au lieu de repeter 339517 — meme bug que les lignes ci-dessous,
    # revele par le golden test 65 lors de son ajout)
    ("SLBC", 2024, 21472, 15078, 307546, 307546, None, None, None, None,
     "NATIF", "VALIDE", "2025-05-02"),  # chaine 2018-2024 entierement coherente, texte natif propre cette fois
    ("SLBC", 2023, 15078, 1217, 327698, 327698, None, None, None, None,
     "NATIF", "VALIDE", "2024-05-13"),
    ("SLBC", 2022, 1217, 22020, 334102, 334102, None, None, None, None,
     "NATIF", "VALIDE", "2023-05-12"),  # chute ponctuelle 2022 (une seule annee), a signaler
    ("SLBC", 2021, 22020, 17520, 316350, 316350, None, None, None, None,
     "NATIF", "VALIDE", "2022-06-03"),
    ("SLBC", 2020, 17520, 13095, 294111, 294111, None, None, None, None,
     "NATIF", "VALIDE", "2021-05-04"),
    ("SLBC", 2018, 4250, 1305, 271179, 271179, None, None, None, None,
     "NATIF", "VALIDE", "2019-04-05"),  # 2019 manquant (document non disponible), serie discontinue mais fiable
    ("SOGC", 2025, 12492.623, 13110.790, 90288.082, 90288.082, None, None, None, None,
     "NATIF", "VALIDE", "2026-04-22"),  # SOGB CI, identite exacte (unite : milliers FCFA supposee)
    ("UNLC", 2023, 640.334855, -6908.362002, 23009.562675, 23009.562675, None, None, None, None,
     "NATIF", "VALIDE", "2024-09-04"),  # Unilever CI ; exercice 2023 seul disponible (donnee datee)
    ("UNLC", 2021, 6090.755732, None, 48697.419272, 48697.419272, None, None, None, None,
     "NATIF", "PROBABLE", "2022-05-20"),  # lecture propre annee propre uniquement ; N-1(2020) ecarte,
    # incoherent de +/-1.3 Md avec la lecture 2020 propre ci-dessous — ecart non resolu, signale
    ("UNLC", 2020, -3690.619307, None, 50984.552374, 50984.552374, None, None, None, None,
     "NATIF", "PROBABLE", "2021-04-30"),
    # --- R6 lot 4 : Energie (secteur complet) ---
    ("TTLC", 2025, 9087, 9374, 188472, 188472, 36202, 3450, 1.10, None,
     "NATIF", "VALIDE", "2026-06-01"),  # TotalEnergies Marketing CI ; payout >100% sur cet exercice (vigilance)
    ("TTLC", 2024, 9374, 8709, 191526, 191526, None, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),  # confirme exactement le N-1 de 2025
    ("TTLC", 2023, 8709, None, 167625, 167625, None, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),
    ("TTLC", 2022, 12279, 11143, 159651, 159651, None, None, None, None,
     "NATIF", "VALIDE", "2023-06-30"),
    ("TTLC", 2021, 11143, None, 156297, 156297, None, None, None, None,
     "NATIF", "VALIDE", "2023-06-30"),  # extrait de la colonne N-1 du document 2022
    ("TTLS", 2025, 6779, 7140, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2026-04-30"),  # TotalEnergies Marketing SN, IFRS consolide
    ("TTLS", 2024, 7090.811, 4222.465, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2025-05-02"),  # +68% ; recul 2025 (-4.4%) confirme un vrai retour a la normale
    ("TTLS", 2023, 4222.465, None, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2025-05-02"),
    ("SHEC", 2025, 6028.125958, 5353.993378, 193561.278972, 193561.278972, None, None, None, None,
     "NATIF", "VALIDE", "2026-06-03"),  # Vivo Energy CI, identite exacte
    # --- R6 lot 5 : Services financiers (partiel) + Telecommunications ---
    ("BICC", 2025, 36520, 26226, 1126270, 1126270, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-04-17"),  # BICI CI ; INVERSION DE COLONNES CORRIGEE (2e source :
    # BPA 1574->2191 FCFA +39%, actif "1,13 trillion" = 1 126 270 M confirme — meme
    # type d'erreur que BOABF, detectee ici uniquement grace a la 2e source
    ("BICC", 2023, 16694, 12391, 920563, 920563, None, None, None, None,
     "NATIF", "VALIDE", "2024-05-02"),  # chaine coherente : 2021=9603->2022=12391->2023=16694->2024=26226->2025=36520
    ("BICC", 2021, 9603, 4672, 847724, 847724, 71522, None, None, None,
     "NATIF", "VALIDE", "2022-04-06"),
    ("ECOC", 2025, 57477, 63482, None, None, None, None, None, None,
     "NATIF", "VALIDE", "2026-04-14"),  # Ecobank CI, bilan non recoupe
    ("SIBC", 2025, 55623, 50234, 1881733, 1685249, None, None, None, None,
     "NATIF", "VALIDE", "2026-04-21"),  # Societe Ivoirienne de Banque, croissance +11% confirmee par le document
    ("ORAC", 2025, 167800, 158200, 2554100, 2554100, 616300, None, None, None,
     "NATIF", "VALIDE", "2026-06-08"),
    ("ORAC", 2023, 154900, None, None, None, 627200, None, None, None,
     "NATIF", "PROBABLE", "2025-02-21"),  # RN 2023 seul (N-1 non capture dans ce document)  # Orange CI, IFRS consolide, milliards->millions
    ("SGBC", 2025, 101228, 101352, None, None, None, None, None, None,
     "NATIF", "PROBABLE", "2026-04-16"),  # Societe Generale CI, ordre colonnes incertain
    ("SGBC", 2021, 67438, 48435, 3021481, 3021481, 304993, None, 0.513, None,
     "NATIF", "VALIDE", "2022-06-30"),
    ("BOAB", 2025, 19647.175711, 20107.229743, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2026-04-15"),  # BOA Benin, bilan non recoupe (OCR)
    ("BOAB", 2021, 13312.371256, 16663.938680, 902792.134544, 902792.134544, 89836.969716, None, None, None,
     "OCR", "PROBABLE", "2022-03-22"),  # 1er succes OCR sur ce titre (tentative precedente sans OCR avait echoue)
    ("BOAS", 2025, 19984, 21906, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2026-03-17"),  # BOA Senegal, bilan illisible a l'OCR
    ("ONTBF", 2025, 15886.921152, 21471.148928, 324902.379845, 324902.379845, None, None, None, None,
     "NATIF", "VALIDE", "2026-06-11"),  # Onatel BF, identite exacte, recul -26%
    ("CIEC", 2025, 13100, 10100, None, None, None, None, 1.0, None,
     "DEUX_SOURCE", "VALIDE", "2026-05-22"),  # CIE CI ; 5+ sources convergentes, payout 100% confirme
    ("CIEC", 2024, 10555, 11508, 2019136, 2019136, 40037, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),  # donnees consolidees (le document distingue consolide/individuel)
    ("CIEC", 2023, 11508, 10271, 1975051, 1975051, 40227, None, None, None,
     "NATIF", "VALIDE", "2024-05-02"),
    # --- Etape E : Bridge Bank Group CI, source note d'information IPO visee AMF-UMOA ---
    ("BBGCI", 2025, 27200, 22800, 1427000, 1427000, 105000, None, 0.65, 0.279,
     "NATIF", "VALIDE", "2026-06-26"),  # visa AO/26-03, ROE 27.9%, TCAM 21-25 RN +15.8%
    ("BBGCI", 2024, 22800, 19800, 1120000, 1120000, 90000, None, 0.53, 0.273,
     "NATIF", "VALIDE", "2026-06-26"),
    ("BBGCI", 2023, 19800, 17500, 837000, 837000, 77000, None, 0.47, 0.278,
     "NATIF", "VALIDE", "2026-06-26"),
    ("BBGCI", 2022, 17500, 15100, 908000, 908000, 66000, None, 0.50, 0.294,
     "NATIF", "VALIDE", "2026-06-26"),
    ("BBGCI", 2021, 15100, None, 710000, 710000, 53000, None, 0.34, 0.312,
     "NATIF", "VALIDE", "2026-06-26"),  # premiere annee de la serie, pas de N-1 dans le document
    ("LNBB", 2025, 4620, 7170, None, None, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-05-18"),  # Loterie Nationale du Benin ; 2024 annee exceptionnelle (+83%,
    # non recurrente, 1ere annee post-IPO) ; document source non encore collecte par le robot
    ("PRSC", 2025, 2370, 2346.711607, None, None, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-06-05"),  # RN_n1 corrige : 2346.71 (valeur reelle du document, remplace
    # l'estimation web 2349 — ecart mineur 0.1%, coherent)
    ("PRSC", 2024, 2346.711607, 2044.698, None, None, 11283.033493, None, None, None,
     "NATIF", "VALIDE", "2025-04-30"),
    ("PRSC", 2023, 2044.698, 3562.811, 54277.216, 54277.216, 10916.681, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),  # document unique couvrant 2018-2023, annees explicitement etiquetees
    ("PRSC", 2022, 3562.811, 2952.005, 55623.135, 55623.135, 11408.600, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),
    ("PRSC", 2021, 2952.005, 1723.627, 39785.218, 39785.218, 9735.650, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),
    ("PRSC", 2020, 1723.627, 1804.027, 33234.672, 33234.672, 8597.857, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),
    ("PRSC", 2019, 1804.027, 2048.423, 36358.437, 36358.437, 8569.730, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),
    ("PRSC", 2018, 2048.423, None, 37086.474, 37086.474, 8478.097, None, None, None,
     "NATIF", "VALIDE", "2025-06-17"),  # premiere annee disponible, pas de N-1
    ("BICB", 2025, 24200, 30340, None, None, None, None, None, None,
     "DEUX_SOURCE", "PROBABLE", "2026-06-22"),  # BIIC Benin ; referentiel PCB OHADA retenu (coherence pairs bancaires) ;
    # IFRS donne +24.7% (36.2 vs 29.1 Mds) contre -20% en PCB OHADA (24.2 vs 30.34 Mds) — ecart de 12 Mds
    # entre referentiels, statut PROBABLE tant que la source du double-reporting n'est pas expertisee
    ("BOAM", 2025, 11081.189907, 9123.471904, None, None, None, None, None, None,
     "OCR", "PROBABLE", "2026-03-24"),  # BOA Mali ; RN = resultat avant impot - impot (ligne RN non visible a l'OCR)
    ("BOAC", 2025, 35540, 32044, None, None, 127300, None, 0.76, None,
     "DEUX_SOURCE", "VALIDE", "2026-04-13"),  # BOA Cote d'Ivoire ; communique groupe BOA + 2 articles convergents, ROE 27.9%
    ("BOAC", 2024, 32044, 26075, 1075479, 1075479, 112644, None, None, None,
     "NATIF", "VALIDE", "2025-04-02"),  # confirme exactement le 2025 (32044) — 2e source native, pas seulement web
    ("BOAC", 2023, 26075, 20069, 938739, 938739, 95801, None, None, None,
     "NATIF", "VALIDE", "2024-03-14"),
    ("BOAC", 2022, 20069, None, 843300, 843300, 81726, None, None, None,
     "NATIF", "VALIDE", "2023-04-05"),  # premiere annee de la serie disponible, pas de N-1
    ("BOAN", 2025, 409, 5002, None, None, None, None, None, None,
     "DEUX_SOURCE", "VALIDE", "2026-04-20"),  # BOA Niger ; effondrement -91.8%, 2 profit warnings emis (12/2025 et 03/2026)
    # BOAC/BOAN : bilan et OCR direct restent illisibles (tampon/signature sur
    # la ligne RN) ; donnees ci-dessus proviennent du communique officiel
    # BOA Group (16/04/2026), recoupe par plusieurs articles independants.
    # BOAC, BOAM, BOAN : documents scannes volumineux (49-53 pages, format
    # reglementaire complet type Coris) non traites ce lot, report necessaire
    # avec classement de pages + OCR haute resolution cible.
    # ETIT (Ecobank Transnational Incorporated Togo) : aucun document trouve.
    # Synthetiques : profil clairement degrade (exclusion attendue) et profil limite (vigilance attendue)
    ("TEST_EXCLU", 2025, -320, -410, 1200, 1200, -150, 900, 1.45, None, "NATIF", "VALIDE", "2026-05-01"),
    ("TEST_EXCLU", 2024, -410, -180, 1500, 1500, 180, 950, 1.60, None, "NATIF", "VALIDE", "2025-05-01"),
    ("TEST_VIGIL", 2025, 850, 1150, 9000, 9000, 4200, 2000, 0.85, None, "NATIF", "VALIDE", "2026-05-01"),
]

DIVIDENDES = [
    # SDSC 2020-2022 : RESOLU le 14/07/2026. La fiche profil BRVM donnait
    # "5443/5443/5008" sous l'intitule "Dividende net/action (FCFA)" -- en realite
    # le DIVIDENDE TOTAL en MILLIONS FCFA, mal etiquete (verifie : 92 FCFA/action brut
    # x 54 435 300 actions = 5008,05 M FCFA, exact au centime pres vs le document de
    # resolutions d'AG qui confirme independamment "92 FCFA brut" pour 2022).
    # 2022 : brut confirme par document primaire (resolutions AG). 2020/2021 :
    # brut RECONSTRUIT par le meme calcul (5443 M / 54 435 300 actions = 100,00 FCFA,
    # chiffre rond, coherent avec un resserrement a 92 FCFA en 2022) -- non enonce
    # explicitement par action dans un document, donc moins sur que 2022.
    # Net = brut x (1 - IRVM_CI 10%), cf. moteur/scoring.py IRVM_PAR_PAYS.
    ("SDSC", 82.8, None, 2022),   # 92 FCFA brut confirme (resolutions AG) -> net apres IRVM 10%
    ("SDSC", 90.0, None, 2021),   # 100 FCFA brut reconstruit (voir note ci-dessus) -> net
    ("SDSC", 90.0, None, 2020),   # idem
    # ticker, montant_net, date_paiement, exercice_couvert
    # REGLE D'INTEGRITE : montant renseigne UNIQUEMENT si source dans la conversation ;
    # sinon None (date seule, issue du BOC) — la saisie manuelle suit les memes
    # regles que l'extraction automatique.
    ("SNTS", 1740, "2026-05-25", 2025),        # source : Sika Finance 02/2026 (1933 brut / 1740 net)
    ("STBC", None, "2025-08-29", 2024),        # date BOC ; montant a re-sourcer
    ("NSBC", None, "2026-06-30", 2025),        # AGO 30/06/2026 : 19 Mds FCFA approuves (Ecofin) ; par action a sourcer
    ("SMBC", None, "2025-09-15", 2024),        # date BOC ; montant a re-sourcer
    ("BOABF", 397.25, "2026-04-23", 2025),     # source : Ecofin 03/2026 (dividende net apres IRVM 12,5%)
    ("CBIBF", 900, "2026-06-19", 2025),        # source : avis BRVM + presse 06/2026
    ("CBIBF", 555, "2025-06-01", 2024),        # source : presse (croissance +62% documentee)
    ("SICC", 0, "2000-09-25", 1999),           # marqueur d'obsolescence, date BOC
    ("ORGT", 0, "2020-07-17", 2019),           # 5e annee sans dividende confirmee presse 05/2026
    ("TEST_EXCLU", 0, "2019-01-01", 2018),
    ("TEST_VIGIL", 300, "2025-09-01", 2024), ("TEST_VIGIL", 310, "2024-09-01", 2023),
]

AVIS = [
    # REGLE FORMALISEE (11/07/2026, suite audit collecteur.py) : un avis
    # RETARD_PUBLICATION ne doit JAMAIS etre pose sur la seule base d'une absence
    # de document dans notre collecte — ce collecteur peut manquer des pages
    # (cas confirme : ETIT jamais visite, bug de pagination corrige le 11/07/2026 ;
    # SDSC partiellement rate). Un retard ne doit etre enregistre QUE s'il est
    # explicitement constate DANS un document trouve (ex. rapport des commissaires
    # aux comptes declarant noir sur blanc un manquement au delai legal — cf. SDSC
    # 2024, seul cas actuellement conforme a cette regle). Toute violation future
    # de cette regle est un bug a corriger, pas une interpretation valide.
    ("TEST_EXCLU", "RETARD_PUBLICATION", "2025-06-01", "echeance semestrielle 2025 manquee (synthetique)"),
    ("TEST_EXCLU", "RETARD_PUBLICATION", "2026-01-01", "echeance annuelle 2025 manquee (synthetique)"),
    ("STBC", "ANOMALIE_NON_EXPLIQUEE", "2025-05-07",
     "Exercice 2024 : resultat net +261% et total actif triple vs 2023, cause non confirmee "
     "(hypothese : element exceptionnel type HAO, non verifie faute de detail ligne par ligne) — "
     "a investiguer avant tout usage en test de facteur historique"),
    # R4 — flux d'avis contextuels (non-exclusion mais surfaces en alerte)
    ("ORGT", "NOTATION_DEGRADEE", "2025-06-13",
     "Fitch estime le processus de defaut enclenche (source : Sika Finance, 13/06/2025)"),
    ("ORGT", "GOUVERNANCE", "2024-06-01",
     "crise de gouvernance, departs de dirigeants et echec du rachat par Vista documentes par la presse (Togo First, 05/2026)"),
    ("SAFC", "GOUVERNANCE", "2025-04-01",
     "Changement d'actionnaire de controle : CREDAF Group prend le controle en avril 2025 ; "
     "le redressement 2025 est explicitement attribue a la nouvelle gouvernance (source : Sika Finance, 05/2026)"),
    ("SAFC", "OPERATION_CAPITAL", "2026-05-01",
     "Augmentation de capital de 1,5 Md FCFA en cours (souscriptions closes 06/2026) — "
     "dilution a anticiper sur le BPA futur (source : Sika Finance, 05/2026)"),
    ("SAFC", "GUIDANCE_DIVIDENDE", "2025-04-28",
     "La direction annonce ne pas prevoir de distribution avant 2028 (3 ans de stabilisation "
     "de la rentabilite post-redressement) — a distinguer d'un simple oubli (source : Sika Finance)"),
    ("FTSC", "ARTEFACT_COMPTABLE", "2024-12-31",
     "Resultat net 2024 domine par un gain HAO exceptionnel (18,86 Mds FCFA) ; le recul "
     "2025 reflete un retour a un resultat operationnel normalise, pas une degradation reelle"),
    ("BOAN", "PROFIT_WARNING", "2026-03-01",
     "Deux avertissements sur resultat emis (12/2025 et 03/2026) avant publication ; "
     "effondrement -91.8% du resultat net, bilan total en contraction de 9.5% (source : BOA Group, Le Sahel 04/2026)"),
    ("SEMC", "SUSPENSION", "2025-01-02",
     "Suspension temporaire de cotation (non-respect du flottant reglementaire minimum 15%), "
     "levee le 15/12/2025 (pres de 12 mois) ; societe renommee Crown Siem -> Eviosys -> Sonoco "
     "Packaging Siem sur la periode (source : Sika Finance)"),
    ("SPHC", "CYCLE_MATIERE_PREMIERE", "2025-03-24",
     "Croissance 2024 (+417%) confirmee liee au cycle mondial du caoutchouc naturel (plus haut niveau "
     "en 7 ans, deficit d'offre Thailande/Indonesie/Vietnam + demande vehicules electriques) — choc "
     "externe sectoriel reel et documente, PAS un artefact comptable, mais exposition cyclique a noter"),
    ("SOGC", "CYCLE_MATIERE_PREMIERE", "2025-05-07",
     "Croissance 2024 (+149%) confirmee liee au meme cycle mondial du caoutchouc (+29% sur les prix) "
     "et de l'huile de palme (+14%) — retournement 2025 (-4.71%, concurrence accrue sur le coagulum) "
     "confirme un vrai cycle de marche, pas un artefact qui s'inverse"),
    ("UNXC", "CHOC_EXTERNE_DOCUMENTE", "2021-05-25",
     "Croissance 2021 (+505.7%) confirmee liee a un vrai choc COVID en 2020 (CA -13%, RN -92.5% du fait "
     "du couvre-feu et de la fermeture des frontieres, explicitement documente par la direction) suivi "
     "d'une reprise operationnelle reelle en 2021 — pas un artefact comptable. Point de vigilance : "
     "actualite 2026 mentionne des soupcons de 'mirage comptable' chez Uniwax, hors periode actuelle, "
     "a verifier lors d'une future collecte des exercices 2024-2026"),
    ("SDSC", "RETARD_PUBLICATION", "2025-04-30",
     "Manquement legal CONFIRME par les commissaires aux comptes eux-memes (Deloitte CI, ECR International, "
     "rapport du 20/06/2025) : etats financiers 2024 non arretes dans le delai legal de 4 mois (echeance "
     "30/04/2025, non respectee) — 'manquement aux obligations comptables formelles'. Comptes 2023 "
     "encore en cours de cloture en aout 2025. Chiffre d'affaires 2024 confirme : 85 643 M FCFA."),
    ("SDSC", "DIVERGENCE_PRIX_FONDAMENTAUX", "2025-11-17",
     "Resultat net annuel non extrait avec confiance malgre documents 2023/2024 localises sur brvm.org "
     "(le robot de collecte ne les avait jamais recuperes — corrige le 11/07/2026, section documentaire "
     "trouvee mais tableaux chiffres non exploites). Tendance operationnelle en degradation confirmee sur "
     "plusieurs trimestres consecutifs : RN -168% (T1 2024), contraction (T3 2024), resultat d'exploitation "
     "-49% a -662M FCFA et benefice -77% (T3 2025). Financial Afrik (17/11/2025) qualifie explicitement la "
     "situation d'asymetrie de l'information : le cours serait soutenu par le controle strategique du "
     "groupe (MSC) et la rarete des valeurs logistiques BRVM, independamment de la performance."),
]

# R5+ — Resultat des Activites Ordinaires (RAO), quand trouve explicitement dans le
# document source ou confirme par sourcage documentaire. Jamais devine. Utilise en
# COMPARAISON au resultat net (jamais en substitution), cf. principe "quality of
# earnings" applique sans distordre le score (voir discussion methodologique 07/2026).
RAO = [
    ("FTSC", 2025, 142.325),   # trouve directement dans le document, complete la serie 2023-2025
    ("FTSC", 2024, 4340.0),    # confirme (croissanceafrique.com) : RAO +26% a 4,34 Mds vs RN +504.7%
    ("FTSC", 2023, 3444.4),    # derive de la meme source (4340/1.26)
    ("TTLC", 2024, 13178.0),   # RAO directement dans le document source (colonne "Resultat des activites ordinaires")
    ("TTLC", 2023, 12033.0),
    ("TTLC", 2022, 16109.0),
    ("TTLC", 2021, 15778.0),
    ("STBC", 2024, 56541.0),   # confirme (allafrica.com, 05/2026) : RAO vs 16 800 en 2023
    ("STBC", 2023, 16800.0),
    ("SOGC", 2025, 17161.525), # extrait directement du document source (compte de resultat complet)
    ("SOGC", 2024, 18040.224),
]

SOURCE_URLS = [  # Etape B du plan (10/07/2026) : reconstruit depuis MANIFESTE.csv
    ("STAC", 2024, "https://www.brvm.org/sites/default/files/20250410_-_etats_financiers_provisoires_-_exercice_2024_-_setao_ci.pdf"),
    ("STAC", 2022, "https://www.brvm.org/sites/default/files/20230426_-_etats_financiers_exercice_2022_-_setao_ci.pdf"),
    ("STAC", 2021, "https://www.brvm.org/sites/default/files/20220426_-_etats_financiers_exercice_2021_-_setao_ci.pdf"),
    ("STAC", 2020, "https://www.brvm.org/sites/default/files/20210429_-_etats_financiers_-_exercice_2020_-_setao_ci.pdf"),
    ("SHEC", 2023, "https://www.brvm.org/sites/default/files/20240606_-_etats_financiers_provisoire_-_exercice_2023_-_vivo_energy_ci.pdf"),
    ("SCRC", 2023, "https://www.brvm.org/sites/default/files/20240510_-_etats_financiers_-_exercice_2023_-_sucrivoire_ci.pdf"),
    ("TTLC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_totalenergies_marketing_ci.pdf"),
    ("TTLC", 2022, "https://www.brvm.org/sites/default/files/20230630_-_etats_financiers_certifies_et_approuves_exercice_2022_-_totalenergies_marketing_ci.pdf"),
    ("UNLC", 2021, "https://www.brvm.org/sites/default/files/20220520_-_etats_financiers_exercice_2021_-_unilever_ci.pdf"),
    ("UNLC", 2020, "https://www.brvm.org/sites/default/files/20210430_-_etats_financiers_-_exercice_2020_-_unilever_ci.pdf"),
    ("SLBC", 2024, "https://www.brvm.org/sites/default/files/20250502_-_etats_financiers_-_exercice_2024_-_solibra_ci.pdf"),
    ("SLBC", 2023, "https://www.brvm.org/sites/default/files/20240513_-_etats_financiers_de_synthese_-_exercice_2023_-_solibra_ci.pdf"),
    ("SLBC", 2022, "https://www.brvm.org/sites/default/files/20230512_-_etats_financiers_exercice_2022_-_solibra_ci.pdf"),
    ("SLBC", 2021, "https://www.brvm.org/sites/default/files/20220603_-_etats_financiers_exercice_2021_-_solibra.pdf"),
    ("SLBC", 2020, "https://www.brvm.org/sites/default/files/20210504_-_etats_financiers_-_exercice_2020_-_solibra_ci.pdf"),
    ("SLBC", 2018, "https://www.brvm.org/sites/default/files/20190405_-_etats_financiers_exercice_2018_-_solibra_ci.pdf"),
    ("BOABF", 2023, "https://www.brvm.org/sites/default/files/20240301_-_etats_financiers_certifies_-_exercice_2023_-_boa_bf.pdf"),
    ("BOABF", 2022, "https://www.brvm.org/sites/default/files/20230223_-_etats_financiers_exercice_2022_-_boa_bf.pdf"),
    ("BOAC", 2024, "https://www.brvm.org/sites/default/files/20250402_-_etats_financiers_-_exercice_2024_-_boa_ci.pdf"),
    ("BOAC", 2023, "https://www.brvm.org/sites/default/files/20240314_-_etats_financiers_-_exercice_2023_-_boa_ci.pdf"),
    ("BOAC", 2022, "https://www.brvm.org/sites/default/files/20230405_-_etats_financiers_exercice_2022_-_boa_ci.pdf"),
    ("BICC", 2023, "https://www.brvm.org/sites/default/files/20240502_-_etats_financiers_-_exercice_2023_-_bici_ci.pdf"),
    ("BICC", 2021, "https://www.brvm.org/sites/default/files/20220406_-_etats_financiers_exercice_2021_-_bicici.pdf"),
    ("CIEC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_norme_syscohada_-_exercice_2024_-_cie_ci.pdf"),
    ("CIEC", 2023, "https://www.brvm.org/sites/default/files/20240502_-_etats_financiers_syscohada_-_exercice_2023_-_cie_ci.pdf"),
    ("ORGT", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_oragroup_tg.pdf"),
    ("ABJC", 2023, "https://www.brvm.org/sites/default/files/20240819_-_etats_financiers_approuves_-_exercice_2023_-_servair_abidjan_ci.pdf"),
    ("SGBC", 2021, "https://www.brvm.org/sites/default/files/20220630_-_etats_financiers_certifies_exercice_2021_-_societe_generale_ci_0.pdf"),
    ("TTLS", 2024, "https://www.brvm.org/sites/default/files/20250502_-_etats_financiers_-_norme_syscohada_-_exercice_2024_-_totalenergies_marketing_sn.pdf"),
    ("TTLS", 2023, "https://www.brvm.org/sites/default/files/20250502_-_etats_financiers_-_norme_syscohada_-_exercice_2024_-_totalenergies_marketing_sn.pdf"),
    ("CBIBF", 2022, "https://www.brvm.org/sites/default/files/20230427_-_etats_financiers_exercice_2022_-_coris_bank_international_bf.pdf"),
    ("ORAC", 2023, "https://www.brvm.org/sites/default/files/20250221_-_etats_financiers_-_exercice_2024_-_orange_ci.pdf"),
    ("PALC", 2024, "https://www.brvm.org/sites/default/files/20250417_-_etats_financiers_provisoires_valides_par_le_ca_-_exercice_2024_-_palm_ci.pdf"),
    ("ABJC", 2025, "https://www.brvm.org/sites/default/files/20260427_-_etats_financiers_ifrs_-_exercice_2025_-_servair_abidjan_ci.pdf"),
    ("BICC", 2025, "https://www.brvm.org/sites/default/files/20260417_-_etats_financiers_-_exercice_2025_-_bici_ci.pdf"),
    ("BNBC", 2025, "https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_bernabe_ci.pdf"),
    ("BOABF", 2025, "https://www.brvm.org/sites/default/files/20260323_-_etats_financiers_-_exercice_2025_-_boa_bf.pdf"),
    ("BOAB", 2025, "https://www.brvm.org/sites/default/files/20260415_-_etats_financiers_-_exercice_2025_-_boa_bn.pdf"),
    ("BOAM", 2025, "https://www.brvm.org/sites/default/files/20260324_-_etats_financiers_-_exercice_2025_-_boa_ml.pdf"),
    ("BOAS", 2025, "https://www.brvm.org/sites/default/files/20260317_-_etats_financiers_-_exercice_2025_-_boa_sn.pdf"),
    ("CABC", 2019, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2020, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2021, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2022, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2023, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2024, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CABC", 2025, "https://www.brvm.org/sites/default/files/20260311_-_etats_financiers_ifrs_-_exercice_2025_-_sicable_ci.pdf"),
    ("CBIBF", 2022, "https://www.brvm.org/sites/default/files/20230427_-_etats_financiers_exercice_2022_-_coris_bank_international_bf.pdf"),
    ("CBIBF", 2025, "https://www.brvm.org/sites/default/files/20260707_-_etats_financiers_-_exercice_2025_-_coris_bank_international_bf.pdf"),
    ("CFAC", 2024, "https://www.brvm.org/sites/default/files/20250516_-_etats_financiers_-_exercice_2024_-_cfao_motors_ci.pdf"),
    ("ECOC", 2025, "https://www.brvm.org/sites/default/files/20260414_-_rapport_dactivites_et_etats_financiers_-_exercice_2025_-_ecobank_ci.pdf"),
    ("FTSC", 2021, "https://www.brvm.org/sites/default/files/20220506_-_etats_financiers_exercice_2021_-_filtisac_ci.pdf"),
    ("FTSC", 2022, "https://www.brvm.org/sites/default/files/20230511_-_etats_financiers_exercice_2022_-_filtisac_ci.pdf"),
    ("FTSC", 2023, "https://www.brvm.org/sites/default/files/20240513_-_etats_financiers_-_exercice_2023_-_filtisac_ci.pdf"),
    ("FTSC", 2024, "https://www.brvm.org/sites/default/files/20250523_-_etats_financiers_-_exercice_2024_-_filtisac_ci.pdf"),
    ("FTSC", 2025, "https://www.brvm.org/sites/default/files/20260610_-_etats_financiers_-_exercice_2025_-_filtisac_ci.pdf"),
    ("NEIC", 2024, "https://www.brvm.org/sites/default/files/20250613_-_etats_financiers_approuves_-_exercice_2024_-_nei-ceda_ci.pdf"),
    ("NSBC", 2021, "https://www.brvm.org/sites/default/files/20220512_-_etats_financiers_-_exercice_2021_-_nsia_banque_ci_annule_et_remplace_le_precedent.pdf"),
    ("NSBC", 2022, "https://www.brvm.org/sites/default/files/20230331_-_etats_financiers_exercice_2022_-_nsia_banque_ci.pdf"),
    ("NSBC", 2023, "https://www.brvm.org/sites/default/files/20240328_-_etats_financiers_-_exercice_2023_-_nsia_banque_ci.pdf"),
    ("NSBC", 2024, "https://www.brvm.org/sites/default/files/20250325_-_etats_financiers_certifies_par_les_commissaires_aux_comptes_-_exercice_2024_-_nsia_banque_ci.pdf"),
    ("NSBC", 2025, "https://www.brvm.org/sites/default/files/20260513_-_etats_financiers_et_communique_-_exercice_2025_-_nsia_banque_ci.pdf"),
    ("NTLC", 2025, "https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_-_exercice_2025_-_nestle_ci.pdf"),
    ("ONTBF", 2025, "https://www.brvm.org/sites/default/files/20260611_-_etats_financiers_approuves_-_exercice_2025_-_onatel_bf.pdf"),
    ("ORAC", 2025, "https://www.brvm.org/sites/default/files/20260608_-_etats_financiers_approuves_-_exercice_2025_-_orange_ci.pdf"),
    ("ORGT", 2021, "https://www.brvm.org/sites/default/files/20220426_-_etats_financiers_exercice_2021_-_oragroup_tg.pdf"),
    ("ORGT", 2022, "https://www.brvm.org/sites/default/files/20230426_-_etats_financiers_exercice_2022_-_oragroup_tg.pdf"),
    ("ORGT", 2023, "https://www.brvm.org/sites/default/files/20240429_-_etats_financiers_-_exercice_2023_-_oragroup_togo.pdf"),
    ("ORGT", 2025, "https://www.brvm.org/sites/default/files/20260504_-_etats_financiers_-_exercice_2025_-_oragroup_tg.pdf"),
    ("PALC", 2023, "https://www.brvm.org/sites/default/files/20250417_-_etats_financiers_provisoires_valides_par_le_ca_-_exercice_2024_-_palm_ci.pdf"),
    ("PALC", 2025, "https://www.brvm.org/sites/default/files/20260323_-_etats_financiers_-_exercice_2025_-_palm_ci.pdf"),
    ("PRSC", 2018, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2019, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2020, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2021, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2022, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2023, "https://www.brvm.org/sites/default/files/20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf"),
    ("PRSC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_tractafric_motors_ci.pdf"),
    ("SAFC", 2021, "https://www.brvm.org/sites/default/files/20220425_-_etats_financiers_exercice_2021_-_safca_ci.pdf"),
    ("SAFC", 2025, "https://www.brvm.org/sites/default/files/20260609_-_etats_financiers_-_exercice_2025_-_safca_ci_annule_et_remplace_le_precedent.pdf"),
    ("SCRC", 2025, "https://www.brvm.org/sites/default/files/20260518_-_etats_financiers_-_exercice_2025_-_sucrivoire_ci_annule_et_remplace_le_precedent.pdf"),
    ("SDCC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_sode_ci.pdf"),
    ("SGBC", 2025, "https://www.brvm.org/sites/default/files/20260416_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_societe_generale_ci.pdf"),
    ("SHEC", 2021, "https://www.brvm.org/sites/default/files/20220906_-_etats_financiers_exercice_2021_-_vivo_energy_ci.pdf"),
    ("SHEC", 2022, "https://www.brvm.org/sites/default/files/20231103_-_etats_financiers_-_exercice_2022_-_vivo_energy_ci.pdf"),
    ("SHEC", 2024, "https://www.brvm.org/sites/default/files/20250516_-_etats_financiers_2024_et_rapport_dactivites_du_1er_trimestre_2025_-_vivo_energy_ci.pdf"),
    ("SHEC", 2025, "https://www.brvm.org/sites/default/files/20260603_-_etats_financiers_-_exercice_2025_-_vivo_energy.pdf"),
    ("SIBC", 2025, "https://www.brvm.org/sites/default/files/20260421_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_sib_ci.pdf"),
    ("SICC", 2024, "https://www.brvm.org/sites/default/files/20260612_-_rapport_dactivites_annuel_et_etats_financiers_-_exercice_2025_-_sicor_ci.pdf"),
    ("SIVC", 2025, "https://www.brvm.org/sites/default/files/20260626_-_etats_financiers_-_exercice_2025_-_erium_ci.pdf"),
    ("SLBC", 2025, "https://www.brvm.org/sites/default/files/20260519_-_etats_financiers_-_exercice_2025_-_solibra_ci.pdf"),
    ("SMBC", 2022, "https://www.brvm.org/sites/default/files/20230816_-_etats_financiers_certifies_et_approuves_-_exercice_2022_-_smb_ci.pdf"),
    ("SMBC", 2023, "https://www.brvm.org/sites/default/files/20240513_-_etats_financiers_de_synthese_-_exercice_2023_-_smb_ci.pdf"),
    ("SMBC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_smb_ci.pdf"),
    ("SMBC", 2025, "https://www.brvm.org/sites/default/files/20260512_-_etats_financiers_et_projet_daffectation_du_resultat_-_exercice_2025_-_smb_ci.pdf"),
    ("SNTS", 2023, "https://www.brvm.org/sites/default/files/20240222_-_etats_financiers_-_exercice_2023_-_sonatel_sn.pdf"),
    ("SNTS", 2024, "https://www.brvm.org/sites/default/files/20250221_-_etats_financiers_-_exercice_2024_-_sonatel_sn.pdf"),
    ("SNTS", 2025, "https://www.brvm.org/sites/default/files/20260216_-_etats_financiers_2025_et_attestation_des_cac_-_sonatel_sn.pdf"),
    ("SOGC", 2022, "https://www.brvm.org/sites/default/files/20230424_-_etats_financiers_exercice_2022_-_sogb_ci.pdf"),
    ("SOGC", 2023, "https://www.brvm.org/sites/default/files/20240429_-_etats_financiers_-_exercice_2023_-_sogb_ci.pdf"),
    ("SOGC", 2024, "https://www.brvm.org/sites/default/files/20250430_-_etats_financiers_-_exercice_2024_-_sogb_ci.pdf"),
    ("SOGC", 2025, "https://www.brvm.org/sites/default/files/20260422_-_etats_financiers_syscohada_-_exercice_2025_-_sogb_ci.pdf"),
    ("SPHC", 2022, "https://www.brvm.org/sites/default/files/20230802_-_etats_financiers_certifies_et_approuves_-_exercice_2022_-_saph_ci.pdf"),
    ("SPHC", 2023, "https://www.brvm.org/sites/default/files/20240718_-_etats_financiers_certifies_et_approuves_par_les_cac_-_exercice_2023_-_syscohada_-_saph_ci.pdf"),
    ("SPHC", 2024, "https://www.brvm.org/sites/default/files/20250319_-_etats_financiers_certifies_par_les_cacs_-_exercice_2024_-_saph_ci.pdf"),
    ("SPHC", 2025, "https://www.brvm.org/sites/default/files/20260318_-_etats_financiers_syscohada_-_exercice_2025_-_saph_ci.pdf"),
    ("STBC", 2022, "https://www.brvm.org/sites/default/files/20230814_-_attestation_dexecution_de_la_mission_de_commissariat_aux_comptes_-_etats_financiers_exercice_2022_-_sitab_ci.pdf"),
    ("STBC", 2023, "https://www.brvm.org/sites/default/files/20240605_-_etats_financiers_verifie_par_les_cac_-_exercice_2023_-_sitab_ci.pdf"),
    ("STBC", 2024, "https://www.brvm.org/sites/default/files/20250507_-_etats_financiers_-_exercice_2024_-_sitab_ci.pdf"),
    ("STBC", 2025, "https://www.brvm.org/sites/default/files/20260625_-_etats_financiers_-_exercice_2025_-_sitab_ci_annule_et_remplace_le_precedent.pdf"),
    ("TTLC", 2025, "https://www.brvm.org/sites/default/files/20260601_-_etats_financiers_approuves_-_exercice_2025_-_totalenergies_marketing_ci.pdf"),
    ("TTLS", 2025, "https://www.brvm.org/sites/default/files/20260430_-_etats_financiers_ifrs_-_exercice_2025_-_totalenergies_marketing_sn.pdf"),
    ("UNLC", 2023, "https://www.brvm.org/sites/default/files/20240904_-_etats_financiers_-_exercice_2023_-_unilever_ci.pdf"),
    ("UNXC", 2021, "https://www.brvm.org/sites/default/files/20220613_-_etats_financiers_certifies_exercice_2021_-_uniwax_ci.pdf"),
    ("UNXC", 2022, "https://www.brvm.org/sites/default/files/20230428_-_etats_financiers_exercice_2022_-_uniwax_ci.pdf"),
    ("UNXC", 2023, "https://www.brvm.org/sites/default/files/20240430_-_etats_financiers_de_synthese_projets_daffectation_non_verifies_par_les_cac_-_exercice_2023_-_uniwax_ci.pdf"),
]

def main():
    conn = sqlite3.connect(DB)
    conn.executescript(open(_BASE / "schema.sql", encoding="utf-8").read())
    cur = conn.cursor()
    cur.executemany(
        "INSERT OR REPLACE INTO societes VALUES (?,?,?,?,?,?,?)", SOCIETES)
    cur.executemany(
        "INSERT OR REPLACE INTO etats_financiers "
        "(ticker,exercice,resultat_net,resultat_net_n1,total_actif,total_passif,"
        "capitaux_propres,dettes_financieres,payout_ratio,solvabilite_bancaire,"
        "source_type,statut_donnee,date_publication) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ETATS)
    cur.executemany(
        "UPDATE etats_financiers SET resultat_activites_ordinaires=? "
        "WHERE ticker=? AND exercice=?",
        [(rao, t, e) for t, e, rao in RAO])
    cur.executemany(
        "UPDATE etats_financiers SET source_url=? WHERE ticker=? AND exercice=?",
        [(url, t, e) for t, e, url in SOURCE_URLS])
    cur.executemany(
        "INSERT INTO dividendes (ticker,montant_net,date_paiement,exercice_couvert) "
        "VALUES (?,?,?,?)", DIVIDENDES)
    cur.executemany(
        "INSERT INTO avis_reglementaires (ticker,type,date_avis,note) VALUES (?,?,?,?)",
        AVIS)
    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM societes").fetchone()[0]
    m = cur.execute("SELECT COUNT(*) FROM etats_financiers").fetchone()[0]
    print(f"Base peuplee : {n} societes, {m} lignes d'etats financiers.")
    conn.close()

if __name__ == "__main__":
    main()
