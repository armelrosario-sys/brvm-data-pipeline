# Stratégie d'investissement BRVM — Document de référence (v2.3)
**Date : 11/07/2026 · Statut : audit complet realise (6 casquettes), recommandations 1-3-4 traitees · SDSC gap structurel accepte · croissance non significative (comme decote) · angle mort fiscal UEMOA identifie**

## 1. Objectif

Maximiser le rendement total (plus-value + dividendes) d'un portefeuille actions BRVM, horizon 2-5 ans, en identifiant tôt les titres au profil rentabilité-solidité-valorisation favorable avant leur re-rating par le marché (profil type : Coris Bank International début 2026, PER ~6-8 vs secteur 23,8, résultat net +37 %, dividende +62 % → cours ×~1,7 en 4 mois).

## 2. Stratégie retenue

**GARP-Quality adapté BRVM** : acheter à prix raisonnable (décote vs secteur) des entreprises rentables, solides, à dividende régulier et croissant, et les conserver tant que le signal d'entrée persiste. Justification triangulée : recherche académique frontier markets (facteurs value/quality > momentum), données BRVM 2025-2026, pratiques documentées du marché.

**Écartés avec justification :**
- Momentum / analyse technique (RSI, MM, Bollinger) : inutilisables, rotation moyenne marché 0,04, cotations éparses.
- Momentum 12 mois comme garde-fou anti value-trap : remplacé par le filtre de régularité informationnelle.
- Exposition géographique AES : faisabilité insuffisante ; note contextuelle qualitative admise pour les banques régionales, aucun poids chiffré.
- Prévisions d'analystes : quasi inexistantes → PEG calculé sur croissance HISTORIQUE.
- Taux de défaillance de dividende par secteur : supprimé de l'architecture (décision utilisateur).

## 3. Architecture à 3 niveaux + règle de sortie

### Niveau 1 — Filtres d'exclusion (pass/fail ; un veto = titre écarté)

| # | Filtre | Seuil |
|---|---|---|
| 1 | Retards de publication | ≥2 défauts / 4 dernières échéances réglementaires |
| 2 | Réserve substantielle du CAC | Dernier exercice (rapports dispo sur brvm.org par société) |
| 3 | Sanction AMF-UMOA | Dans les 24 derniers mois |
| 4 | Silence informationnel | >18 mois sans publication/AG/dividende |
| 5 | Capitaux propres négatifs | Immédiat |
| 6 | Résultat net négatif | 2 exercices consécutifs |
| 7 | Endettement anormal | Hors banques : D/E >2× médiane sectorielle. Banques : ratio de solvabilité réglementaire BCEAO (<~11,5 %) |
| 8 | Défaut de paiement (coupon/dividende annoncé) | Tout défaut confirmé |
| 9 | Payout >100 % | 2 exercices consécutifs |
| 10 | Suspension de cotation | En cours ou <12 mois |
| 11 | Retrait de cote (OPR) | Procédure engagée |
| 12 | Flottant très faible + hausse brutale sans catalyseur | Signal QUALITATIF (pas de donnée flottant fiable par titre) |

Mode : mécanique avec clause de revue documentée (réintégration possible si justification écrite vérifiable).

### Niveau 2 — Score composite (titres ayant passé le gate)

| Dimension | Poids | Indicateurs |
|---|---|---|
| Rentabilité & croissance | 35 % | ROE vs moyenne marché ; croissance résultat net cumulée 3 ans ; régularité (aucune année négative) ; recul maximal du résultat net (malus proportionnel) ; trajectoire de marge opérationnelle |
| Solidité bilancielle | 30 % | D/E (hors banques) ou solvabilité BCEAO (banques) ; payout 30-70 % ; dividende ininterrompu 5 ans ; recul maximal des capitaux propres |
| Valorisation relative | 35 % | PER et PBR vs moyenne SECTORIELLE ; rendement vs marché ET vs secteur ; PEG historique = PER / croissance réalisée 3 ans (<1 = attractif) ; part du re-rating déjà consommée (PER actuel vs PER du titre il y a 12 mois) |

Normalisations : comparaisons valorisation/endettement toujours intra-sectorielles (nomenclature BRVM 7 secteurs, janv. 2026). Référentiels comptables hétérogènes (SYSCOHADA révisé / bancaire UMOA / CIMA) → comparer postes fonctionnellement équivalents.

### Niveau 3 — Modificateurs de taille de position (hors score)

- Liquidité individuelle vs ratio moyen marché → réduit la taille de ligne si nettement inférieure.
- Flottant : signal qualitatif seulement.
- Microstructure = aussi : (a) hypothèse testable isolée (prime d'illiquidité, Amihud-Mendelson), (b) contrôle de qualité des mesures de rendement.

### Règle de sortie

Sortir quand le signal d'entrée disparaît : PER rejoint/dépasse la moyenne sectorielle, OU croissance du résultat sous le seuil 2 exercices consécutifs, OU filtre d'exclusion déclenché a posteriori. JAMAIS sur objectif de gain chiffré ni tentative de deviner un sommet. Traverser les dates de détachement si le signal fondamental reste valide.

## 4. Construction et pilotage du portefeuille

- 5-10 lignes, ≥3-4 secteurs, plafond ~20-25 % par ligne.
- Entrée échelonnée (DCA) — marché haut après 5 années consécutives de hausse.
- Rebalancement semestriel aligné saison des dividendes (avril-juillet) + revue de trajectoire de style.
- Benchmark : BRVM Composite TOTAL RETURN (pas le Composite prix).
- Alertes : liquidité en dégradation durable ; payout >100 % 2 exercices.

## 5. Tableau des seuils (registre versionné)

| Seuil | Valeur | Source/justification | Fixé le | Statut |
|---|---|---|---|---|
| Payout sain | 30-70 % | Convention de marché BRVM documentée | 07/2026 | Provisoire |
| Recul max résultat/CP — vigilance | 25 % (malus proportionnel dès 10 %) | Choix de départ raisonné | 07/2026 | Provisoire |
| D/E anormal (hors banques) | >2× médiane sectorielle | Choix de départ | 07/2026 | Provisoire |
| Solvabilité bancaire | ≥~11,5 % | Norme prudentielle BCEAO/CB-UMOA | 07/2026 | Réglementaire (vérifier taux exact) |
| Dividende régulier | 5 ans sans interruption | Pratique de marché | 07/2026 | Provisoire |
| Retards publication | ≥2/4 échéances | Obligation AMF-UMOA | 07/2026 | Provisoire |
| Silence informationnel | 18 mois | Choix de départ | 07/2026 | Provisoire |
| PEG attractif | <1 | Convention Lynch, version historique | 07/2026 | Provisoire |
| Profondeur historique | 8 ans (2018-2026) | Inclut rupture SYSCOHADA + régimes de marché | 07/2026 | Acté |
| Plafond plausibilité extraction | 1 000 Mds FCFA (ajustable par champ) | > plus gros résultat du marché | 07/2026 | Provisoire |

Bonnes pratiques : test de sensibilité (±20-30 % au backtest ; seuil fragile = artefact) ; toute modification tracée (ancienne valeur, nouvelle, raison).

## 6. Plan de validation empirique (À FAIRE)

1. **Collecte** — par titre × année, 2018-2026 : cours fin de mois (ajustés opérations sur titres — vague de splits 2018-2019), dividendes datés, volumes mensuels, états financiers annuels bruts, DATE EFFECTIVE de publication (anti look-ahead bias), référentiel comptable, secteur (double nomenclature), radiés si prix de sortie + date retrouvables, sinon « non intégrés, biais du survivant assumé ».
2. **Performance (variable à expliquer)** — rendement total annuel = (cours fin − cours début + dividendes)/cours début, ANNÉE PAR ANNÉE, comparé au Composite TR ET à l'indice sectoriel. « Surperformant » = bat les deux sur une majorité d'années.
3. **Exploration guidée** — tester la liste fermée de facteurs candidats (ceux du score) ; pas de fouille libre (faible puissance statistique : indications robustes, pas preuves).
4. **Backtest** — in-sample/out-of-sample ; coûts réels (courtage SGI ~1 %/opération, IRVM, coût d'illiquidité) ; robustesse des seuils.
5. **Paper trading** 6-12 mois avant capital significatif.
Limite assumée : 2021-2026 = régime exclusivement haussier ; conclusions à étiqueter par régime.

## 7. Canal de données & pipeline d'extraction (VALIDÉ 07/2026)

**Principe directeur : intégrité sur couverture** — on ne garantit pas que tout est extrait ; on garantit qu'aucune donnée fausse n'entre silencieusement dans les scores. L'imperfection d'extraction = perte de couverture visible, jamais score faux. Banc d'essai contrôlé réussi (4/4 pièges détectés, 0 faux accepté, 0 faux rejet).

**Circuit v2 (8 améliorations intégrées) :**
1. Collecte SÉLECTIVE : BOC de fin de mois (~96 sur 8 ans, pas ~2000 quotidiens), tous les avis, rapports financiers — volume ÷15, charge initiale ~1-2 h.
2. Robot GitHub Actions : planifié, incrémental, 1-2 req/s max, contrôles CANARI (rendement minimal attendu par run → alerte si anormalement bas = détection restructuration du site), notification d'échec automatique, dépendances figées, tests golden rejoués à chaque run.
3. Stockage : GitHub RELEASES (archives volumineuses hors limites du dépôt Git) + MANIFESTE SHA-256 par fichier (empreinte, URL, date, type, société, période) → détection doublons, rectificatifs silencieux (2 versions conservées datées), provisoire vs certifié (priorité certifié, tracée). Dépôt Git = code + config + manifeste uniquement. Dépôt PUBLIC (documents réglementaires publics) — AUCUN identifiant ne circule jamais.
4. Double extraction indépendante : pdfplumber ∥ PyMuPDF sur fichier brut ; OCR Tesseract pour scannés avec RÈGLE DE SÉVÉRITÉ : valeur OCR ne dépasse jamais PROBABLE sans confirmation de 2e source.
5. DICTIONNAIRE SÉMANTIQUE versionné (fichier config) : libellés variants → champs canoniques, par référentiel et société ; libellé inconnu → quarantaine (jamais deviné). Construit au pilote, enrichi à chaque arbitrage.
6. Contrôles renforcés : convergence A/B ; identités comptables (ACTIF=PASSIF ; CP_N ≈ CP_N-1 + RN − dividendes) ; plafonds de plausibilité ; détection d'UNITÉ déclarée (FCFA/milliers/millions) ; contrôles CROISÉS inter-champs (BPA×actions≈RN ; div/action×actions≈enveloppe avis ; RN≤CA hors exceptionnel) ; cohérence comparatifs N/N-1.
7. Statuts : VALIDÉ (≥2 confirmations indépendantes + contrôles OK) / PROBABLE (1 source, contrôles OK — utilisé avec drapeau) / QUARANTAINE / MANQUANT / RETRAITÉ ? (divergence N/N-1 → arbitrage, jamais conclue seule). Le moteur de scoring ne consomme QUE VALIDÉ+PROBABLE. Titre à quarantaine excessive → « données insuffisantes » → écarté.
8. ARBITRAGE DÉLÉGUÉ (décision utilisateur 07/2026) : rapport de quarantaine soumis en session (Claude arbitre en qq minutes/cas avec expertise comptable), décision tracée au journal, réinjection en base.

**Sources & rôles :** brvm.org = source massive officielle (pipeline principal). Sika Finance = recoupement CIBLÉ pages publiques uniquement (pas d'aspiration massive : média privé, CGU). Google Drive connecté = canal de consultation + 3e regard de recoupement (texte extrait par Google, pas fichier brut → ne nourrit pas le pipeline principal).

**Limites irréductibles assumées :** coquille du document officiel comptablement cohérente = détectable seulement par 2e source ; trous d'archives BRVM = trous documentés ; dictionnaire sémantique = actif évolutif, jamais « fini ». Restriction : le bac à sable Claude n'accède pas à brvm.org directement (liste réseau) — accès via dépôt GitHub (github.com autorisé) ou upload utilisateur.

## 8. Constats de marché (photo avril-juillet 2026 — À ACTUALISER)

- Références BOC 30/04/2026 : PER marché 13,04 ; rendement moyen 6,54 % ; rentabilité moyenne 6,50 % ; liquidité moyenne 27,53 ; rotation 0,04.
- PER sectoriels : Télécom 10,03 ; Conso base 12,31 ; Industriels 15,66 ; Services publics 16,71 ; Énergie 17,10 ; Finance 23,80 ; Conso discrétionnaire 45,84.
- 5 années consécutives de hausse (+25,26 % en 2025) ; dispersion sectorielle extrême 2025 (+73 % agricole / −86 % services publics) ; volumes en tassement début 2026.
- Test grille 24 titres (30/04/2026) : ~20 % signaux GARP (SNTS PER 6,94 ; STBC 9,78 rdt 10,64 % ; BOABF 12,91 ; NSBC 9,02 ; SMBC 6,98) ; ~25 % « dividendes fantômes » (dernier dividende 2000-2023 : UNLC, SICC, SAFC, ORGT, STAC, ETIT…) → vérifier la DATE du dividende ; PER extrêmes (BOAN 186, BNBC 464, UNLC 868, FTSC 1,66/rdt 78 % = distribution exceptionnelle) → inspection systématique.
- Candidats à re-rating à re-vérifier : SMBC +23 % sur 1 an → vérifier « part du re-rating consommée ». SNTS +10 % = profil pré-rallye le plus proche. **BOABF retiré de cette liste : le résultat net recule de -14,1 % sur 2025 (2e année consécutive de baisse) — corrigé en section 12/Découverte 6, ce n'était pas un profil de croissance comme lu initialement sur le seul OCR.**
- Attention : SAFC = secteur Finance (crédit-bail) selon BRVM, pas Industriels.

## 9. Architecture logicielle de l'outil (VALIDÉE 07/2026)

**Principes :** local-first, 100 % open-source, zéro serveur, exécution en 1 commande ; la vraie performance = fiabilité des données + zéro maintenance + temps humain minimal (volumes minuscules : 47 titres × 8 ans).

**Pile :** Python 3.12 + pandas/numpy · SQLite (fichier unique, ACID, append-only, consultable via DB Browser) · seuils et dictionnaire sémantique en YAML (config ≠ code : changer un seuil = 0 ligne de code) · saisie d'exception via classeur Excel à validations · sorties = dashboard Excel AUTO-GÉNÉRÉ (openpyxl : Synthèse/Fiches/Alertes/Registre, jamais édité à la main) + rapport HTML autonome (plotly) · Git (versionnage code+seuils) · pytest golden cases (ex. Coris 04/2026 : données connues → score attendu).

**Modèle de données (tables) :** societes · etats_financiers (titre×exercice + date_publication + référentiel) · cours_mensuels + operations_sur_titres · dividendes · avis_reglementaires · manifeste_fichiers (SHA-256) · scores (runs horodatés avec versions code+seuils+données) · journal_decisions.

**6 garde-fous anti-corrections :** config/code séparés ; validation à l'entrée ; modules purs à contrat d'interface (régénérables isolément, y compris dans une future conversation) ; tests golden avant toute mise en prod ; runs horodatés rejouables ; dashboard jamais édité manuellement.

**Écartés :** PostgreSQL/MySQL (serveur inutile), app web hébergée, Power BI (non open-source), Google Sheets comme base canonique, Streamlit en V1.

**Trajectoire :** V1 = pilote 10 titres (5 GARP : SNTS, STBC, BOABF, NSBC, SMBC + 5 contre-exemples) = banc d'essai du pipeline sur PDF réels (mesure du taux de couverture) → V1.1 = 47 titres → V2 = OCR + montée en charge extraction → V3 = module backtest sur la même base.

## 10. Cahier des charges

**Exigences fonctionnelles :**
- F1 Collecte automatique SÉLECTIVE des publications BRVM (BOC fin de mois, avis, rapports financiers) avec manifeste SHA-256.
- F2 Extraction des champs canoniques : double moteur (pdfplumber ∥ PyMuPDF) + OCR encadré + dictionnaire sémantique.
- F3 Validation (contrôles v2) et affectation d'un des 5 statuts ; rapport d'intégrité à chaque run.
- F4 Stockage append-only SQLite ; chaque chiffre traçable jusqu'au PDF source.
- F5 Scoring : gate 12 filtres → score composite 35/30/35 → sizing, entièrement paramétré par YAML.
- F6 Sorties : watchlist classée, alertes, rapport d'arbitrage, dashboard Excel + rapport HTML auto-générés.
- F7 Journal des décisions et des arbitrages, horodaté.
- F8 (V3) Backtest 2018-2026 sur la même base, biais neutralisés (survivant, look-ahead).

**Exigences non fonctionnelles :**
- NF1 100 % open-source et gratuit.
- NF2 Zéro code et zéro maintenance côté utilisateur (exécution 1 commande ou planifiée).
- NF3 Intégrité > couverture : aucune donnée fausse silencieuse, jamais.
- NF4 Aucun identifiant ne circule ; portefeuille, décisions, watchlist et scores personnels JAMAIS dans le dépôt public (ils restent en local : SQLite + dashboards).
- NF5 Auditabilité complète : runs horodatés avec versions code + seuils + données.
- NF6 Robustesse temporelle : dépendances figées, contrôles canari, golden tests rejoués.
- NF7 Cadence réseau respectueuse (1-2 req/s max vers brvm.org).
- NF8 Projet reprenable de zéro dans toute conversation via ce document.

**Livrables :** dépôt GitHub public (code, config, manifeste) · Releases (archives PDF) · base SQLite locale · dashboards · ce document maintenu à chaque évolution.

## 11. Plan d'étapes du projet (P0 → P9)

| Phase | Contenu | Livrable / critère de validation | Statut |
|---|---|---|---|
| P0 Conception | Stratégie, architecture, canal v2, banc d'essai | Doc de référence ; banc d'essai 4/4 pièges détectés | FAIT |
| P1 Infrastructure | Création du dépôt public + squelette (README, arborescence, YAML seuils v0) | Dépôt : https://github.com/armelrosario-sys/brvm-data-pipeline | FAIT 07/2026 |
| P2 Robot de collecte | Script + workflow GitHub Actions planifié + charge initiale sélective + manifeste + canari | FAIT : 100/103 BOC (3 trous documentés : 2021-05/08/10), 140+ rapports, ~200 Mo en Releases, manifeste SHA-256, canari testé en réel ; collecte rapports se poursuit en planifié (lun/jeu) | FAIT 07/2026 |
| P3 Extraction pilote (9/10 titres testés) | Double moteur, contrôles, identités comptables | FAIT : voir section 12 pour détail et 3 découvertes (désync manifeste/Releases, extraction par tableaux nécessaire, ré-application des filtres validée) | FAIT 07/2026 |
| P4 Base + moteur de scoring | SQLite, gate/score/sizing, golden tests (cas Coris 04/2026) | Scores reproduits manuellement sur 2-3 titres | À faire |
| P5 Photo 47 titres + dashboard v1 | Première watchlist réelle complète | Dashboard généré ; complétude affichée par titre | À faire |
| P6 Historique 8 ans (chantier B1) | Extension collecte 2018-2026, ajustement splits 2018-2019, radiés documentés | Base historique ; trous d'archives listés | À faire |
| P7 Backtest + robustesse (B2-B3) | In/out-of-sample, coûts réels, sensibilité des seuils ±20-30 % | Seuils provisoires → validés ou corrigés | À faire |
| P8 Paper trading (B4) | 6-12 mois simulés vs Composite Total Return | Rapport de performance simulée | À faire |
| P9 Exploitation | Revues semestrielles (avril-juillet), arbitrages, maintenance | Journal + document à jour en continu | Récurrent |

Correspondance avec les chantiers : A = P1-P5 (outil utilisable) ; B = P6-P8 (validation empirique) ; les deux parallélisables à partir de P3.

## 12. P3 — Résultats du pilote sur documents réels (07/2026) — CLÔTURÉ, 9/9 titres, 2e source systématisée

**Bilan final de couverture après recours systématique à la 2e source (recherche web) — 8 VALIDÉ + 1 PROBABLE = 89 % de couverture VALIDÉ :**

| Titre | Résultat net confirmé | Méthode de validation | Statut |
|---|---|---|---|
| Sonatel (SNTS) | 413,6 Mds FCFA, +5,1 % | 2e source (4 médias convergents) | VALIDÉ |
| SMB CI (SMBC) | +50,3 %, identité exacte | Extraction native + identité | VALIDÉ |
| Safca (SAFC) | Perte→profit (-165→+701 M) | Extraction par tableaux + identité | VALIDÉ |
| Sitab (STBC) | -17,4 % (36,46 vs 44,17 Mds), payout ≈80 % | Extraction par tableaux + identité | VALIDÉ (vigilance payout) |
| NSIA Banque (NSBC) | 40,7 Mds FCFA, +7 % | Extraction + 2e source (match exact) | VALIDÉ |
| Oragroup (ORGT) | 21,6 Mds FCFA (perte -44,4 Mds en 2024→profit) | 2e source (4+ médias convergents) | VALIDÉ |
| **BOA Burkina Faso (BOABF)** | **19,25 Mds FCFA, -14,1 %** (pas +16,5 % comme lu initialement) | OCR + 2e source **— a corrigé une inversion de colonnes** | VALIDÉ (corrigé) |
| Coris (CBIBF) | 65,49 Mds FCFA (déjà établi) | 2e source | VALIDÉ |
| Sicor (SICC) | Résultat net ambigu à l'OCR, aucune 2e source trouvée (faible couverture presse) | — | PROBABLE |

**Découverte 6 — LA plus importante méthodologiquement : une extraction numériquement correcte peut produire une conclusion inversée sans 2e source.** Sur BOA Burkina Faso, l'OCR avait extrait les deux chiffres avec exactitude (22 419 223 685 et 19 252 015 161, confirmés au chiffre près par la presse). Mais l'attribution initiale des colonnes (« la première = exercice courant ») était **inversée** : le vrai résultat 2025 est le second chiffre, en repli de -14,1 % (2e année consécutive de baisse), pas le premier en hausse de +16,5 %. **Les deux moteurs d'extraction (pdfplumber/PyMuPDF) ne peuvent jamais détecter ce type d'erreur** — ils étaient d'accord entre eux sur des chiffres corrects, mais l'un comme l'autre ignorent quelle colonne correspond à quel exercice quand ce n'est pas explicitement écrit à côté du nombre. **Seule une 2e source externe indépendante peut attraper une erreur d'attribution.** Conséquence pour l'architecture : le recours à la recherche web comme 2e source n'est plus une solution de secours pour les cas QUARANTAINE (OCR illisible) — **c'est une étape à généraliser à tout résultat PROBABLE avant de le faire monter en VALIDÉ**, native ou pas.

**Découverte 7 — Le nom de fichier BRVM n'est pas fiable pour l'exercice couvert.** Sicor : nom de fichier annonce « exercice 2025 », document indique « Exercice clos le : 31/12/2024 ». Règle : toujours lire l'exercice dans le corps du document.

**Découverte 8 — La ré-application des filtres dans le temps, confirmée sur un DEUXIÈME cas réel.** Après Safca (perte 2024 → profit 2025), Oragroup confirme le même schéma à plus grande échelle : perte de -44,4 Mds en 2024 (aurait déclenché l'exclusion), profit de +21,6 Mds en 2025 (redevient éligible). Le communiqué précise aussi que le bénéfice distribuable est intégralement affecté au renforcement des fonds propres plutôt qu'aux actionnaires — nuance qualitative utile : une absence de dividende post-crise peut être une décision prudente de reconstitution du capital, pas nécessairement un signal négatif en soi (à distinguer au cas par cas dans le dossier qualitatif).

**Note qualitative Sicor** : un différend foncier documenté empêcherait l'exploitation de milliers d'hectares de cocoteraie — élément de contexte expliquant plausiblement la faible dynamique et la rareté de la couverture presse récente.

**Règle d'architecture ajoutée (niveau « pipeline », section 7) : la 2e source (recherche web) devient une étape standard du protocole d'extraction pour tout titre du score, pas une réponse ponctuelle aux cas difficiles — c'est elle qui a permis de faire passer la couverture VALIDÉ de 33 % à 89 % sur ce pilote.**

**Points ouverts (mis à jour) :** 3 BOC introuvables au motif standard (2021-05/08/10) ; dictionnaire sémantique à construire formellement (codes DGI BZ/DZ/AZ/XI en priorité sur les libellés texte) ; convention BNPA du BOC à éclaircir ; pondération des PER sectoriels BRVM inconnue ; prime d'illiquidité à tester ; disponibilité du ratio de solvabilité dans les rapports des 16 valeurs financières ; règle de repli IPO récentes (<3 ans) à formaliser ; Sicor : seul titre encore PROBABLE, nécessiterait une relecture manuelle de l'OCR page 23 pour lever l'ambiguïté ; **généraliser la procédure de 2e source systématique à l'ensemble des 47 titres avant la phase P5 (photo complète).**

## Règles de collaboration (rappel)

Pas de mémoire inter-conversations pour les avis ; aucun document/code sans approbation ; posture conseiller spécialisé BRVM (sans agrément — pas de recommandation personnalisée réglementaire) ; document de synthèse sur demande à chaque étape. PERSONA ACTIF : « Expert Quantique Majeur UEMOA » — 6 casquettes (expert-comptable SYSCOHADA/PCB-UMOA/CIMA ; enseignant-chercheur finance & stats ; fiscaliste mobilier UEMOA ; conseiller SGI ; ingénieur logiciel Python/Excel) ; réponses denses, one-shot, immédiatement applicables, zéro code à écrire côté utilisateur. ARBITRAGE DÉLÉGUÉ : les cas de quarantaine sont tranchés en session, tracés au journal. Sécurité : jamais d'identifiants partagés ; sources publiques uniquement.

## 13. Audit complet du projet (07/2026) et exécution R1+R2

**Diagnostic mené sur l'ensemble du projet, recommandations priorisées R1-R9 (registre complet ci-dessous), R1+R2 exécutées immédiatement.**

**R2 — Corrections d'intégrité appliquées au moteur P4 :**
- Solvabilité bancaire BOABF (0,115) retirée : c'était une valeur non sourcée, égale par coïncidence au seuil réglementaire — violation du principe d'intégrité que le système impose aux données extraites mais n'appliquait pas à sa propre saisie manuelle. **Règle ajoutée : la saisie manuelle suit les mêmes exigences de source que l'extraction automatique.**
- Dividendes non sourcés (STBC 2024, SMBC 2024, NSBC 2025) : montant mis à `None` plutôt que laissé en valeur non tracée ; commentaire de source ajouté à chaque ligne renseignée.
- **Artefact de calcul corrigé (le plus important) : le score traitait un retournement (perte N-1 → profit) comme une hyper-croissance.** Oragroup passait de 75,1 à un score gonflé par un PEG de 0,07 calculé sur une base négative — mathématiquement correct, économiquement absurde. Règle ajoutée à `scoring.py` : base N-1 négative → note de rentabilité neutralisée à 55 (au lieu du plafond), alerte `TURNAROUND` explicite, aucun bonus PEG. Même correction pour Safca.
- **Table `avis_reglementaires` alimentée pour Oragroup** : notation Fitch dégradée (processus de défaut estimé enclenché, 13/06/2025) et signal de gouvernance — ces avis remontent désormais en alerte à côté de tout score, sans l'affecter mécaniquement. Un titre ne peut plus se classer haut avec un incident majeur invisible.
- **Chemins de code convertis en relatifs** (`Path(__file__)`) pour fonctionner depuis n'importe quel clone du dépôt, pas seulement le bac à sable.

**Watchlist recalculée après corrections (indicative, seuils provisoires, valorisations d'avril 2026) :**

| Rang | Titre | Score | Sizing |
|---|---|---|---|
| 1 | Coris (CBIBF) | 85,3 | RÉDUITE |
| 2 | SMB CI (SMBC) | 74,4 | PRUDENCE |
| 3 | Sonatel (SNTS) | 62,3 | PLEINE |
| 4 | NSIA Banque (NSBC) | 62,1 | PRUDENCE |
| **5** | **Oragroup (ORGT)** | **54,1** *(était 75,1 avant correction)* | PRUDENCE — alerte TURNAROUND + notation Fitch dégradée |
| 6 | BOA Burkina Faso (BOABF) | 53,5 | PRUDENCE |
| 7 | Sitab (STBC) | 42,5 | PRUDENCE |
| 8 | Safca (SAFC) | 38,5 | PRUDENCE — alerte TURNAROUND |
| 9 | Sicor (SICC) | 13,8 | PRUDENCE |

**11 golden tests, tous verts**, dont un nouveau test dédié à la non-reproduction de l'artefact turnaround.

**Registre complet des recommandations de l'audit (R1-R9) :**

| # | Recommandation | Statut |
|---|---|---|
| R1 | Committer P4 + document de référence au dépôt | EN COURS |
| R2 | Corriger l'intégrité de la base (solvabilité non sourcée, dividendes non sourcés, artefact turnaround) | FAIT |
| R3 | Construire l'extracteur des 101 BOC → `cours_mensuels`, PER/rendements frais, liquidité par titre | À FAIRE — priorité suivante |
| R4 | Alimenter `avis_reglementaires` par veille web récurrente | AMORCÉ (ORGT fait), à généraliser |
| R5 | Compléter le score vers la spécification complète (ROE, croissance 3 ans, PBR, rendement vs marché+secteur, part du re-rating consommée) | À FAIRE, incrémental avec R3/R6 |
| R6 | Photo des 47 titres par lots de 8-10, 2e source systématique | À FAIRE |
| R7 | Garde-fou de fraîcheur (aucune lecture sur valorisation >1 mois) | À FAIRE |
| R8 | Activer la 2FA GitHub | À FAIRE (action utilisateur) |
| R9 | Dettes méthodologiques résiduelles (BNPA, pondération PER sectoriels, IRVM) | CONTINU |

**Rappel de discipline (inchangé) : cette watchlist ne doit servir à aucune décision d'investissement** — score partiel (5 des indicateurs spécifiés manquent encore), valorisations d'avril 2026 non rafraîchies, univers de 9 titres sur 47.
## 14. R6 — Photo de l'univers 47 titres (07/2026) — 41/47 couverts (87 %)

**Exécution en 8 lots successifs, chacun testé et committé séparément (10-29 golden tests, tous verts à chaque étape).**

**Bilan final :** 41 titres évalués (39 ÉLIGIBLE, 2 EXCLU réels), 6 gaps documentés.

| Secteur | Couverture |
|---|---|
| Industriels | 6/6 |
| Services publics | 2/2 |
| Consommation de base | 7/7 |
| Énergie | 4/4 |
| Consommation discrétionnaire | 5/7 (LNBB, PRSC, UNXC en gap) |
| Services financiers | 15/17 (BICB, ETIT en gap) |
| Télécommunications | 3/3 |

**Exclusions réelles (non synthétiques) :**
- **Sucrivoire (SCRC)** : capitaux propres négatifs (-17,2 Md FCFA) — 1er déclenchement réel du filtre niveau 1 sur ce motif.
- **Setao (STAC)** : pertes 2 exercices consécutifs — 1er déclenchement réel sur ce motif.

**Découverte 9 — Une SECONDE inversion de colonnes, cette fois sur BICC.** Extraction initiale de BICI CI (ticker BICC, alors mal étiqueté « BICB ») donnait -28 % de recul ; la 2e source (BPA 1 574→2 191 FCFA, actif « 1,13 trillion » confirmé) a révélé que l'ordre réel était +39 % de croissance. Même mécanisme que BOABF (section 12) : deux moteurs d'extraction s'accordent sur des chiffres exacts mais mal attribués à l'exercice. **Confirme que la règle « 2e source avant VALIDÉ » (actée en section 12) reste indispensable, y compris après plusieurs lots sans incident.** Correction appliquée : ticker renommé, colonnes inversées, statut DEUX_SOURCE.

**Découverte 10 — BICB et BICC sont deux sociétés distinctes, pas une variante de cotation.** BICB = BIIC Bénin, BICC = BICI Côte d'Ivoire. Une hypothèse erronée de P3 (« BICC = variante de cotation ») corrigée en R6.

**Découverte 11 — ETIT (ticker BRVM) désigne le groupe Ecobank Transnational Incorporated consolidé (coté aussi à Lagos et Accra), pas la filiale locale Ecobank Togo.** Risque de confusion réel : une recherche « Ecobank Togo » remonte des résultats d'une entité différente (filiale togolaise, sanctionnée 200M FCFA par la Commission Bancaire UMOA en 2025) que ceux du groupe coté sous ETIT. Conversion USD→FCFA du résultat groupe jugée insuffisamment fiable sans le rapport officiel → **gap maintenu plutôt qu'un chiffre approximatif.**

**Découverte 12 — Un profit warning réel détecté et intégré (BOA Niger).** Résultat net -91,8 % (5 002 → 409 M FCFA), précédé de deux avertissements officiels (12/2025, 03/2026) et d'une contraction du bilan de -9,5 %. Le score (15,0) reflète correctement la sévérité — nouvelle catégorie d'avis `PROFIT_WARNING` ajoutée à `avis_reglementaires`.

**Découverte 13 — Une année exceptionnelle non-récurrente peut fausser la lecture d'un recul (LNBB, second cas après FTSC).** Loterie Nationale du Bénin : -36 % en 2025, mais 2024 incluait un bond de +83 % lié à sa première année post-introduction en bourse. Recul réel, mais à replacer dans son contexte plutôt que lu comme une dégradation structurelle.

**Gaps documentés (6) — raisons distinctes, pas une même cause :**
- **BICB, ETIT** : ambiguïté d'identification d'entité (voir découvertes 10-11).
- **PRSC, UNXC, SDSC** : qualité de scan insuffisante même à 300 DPI (chiffres clés illisibles).
- **SEMC** : document quasi entièrement image, aucun texte exploitable.

**Limite méthodologique reconnue : les unités de mesure (milliers vs millions FCFA) diffèrent d'un document à l'autre sans marquage toujours explicite** — traité au cas par cas par jugement contextuel (ordre de grandeur plausible pour le secteur), documenté ligne par ligne dans `peupler.py`. Reste un point de vigilance pour la validation empirique (P6-P7).

**Watchlist indicative (41 titres, seuils provisoires) — top 5 : SLBC, CBIBF, SMBC, SPHC, CABC.** Rappel inchangé : aucune décision d'investissement sur cette base — seuils non validés empiriquement, 6 titres encore absents.

## 15. R6 résiduel — clôture définitive (44/47, 94 %)

**Ajouts finaux :** BICB (BIIC Bénin, référentiel PCB OHADA retenu par cohérence avec les pairs bancaires — écart de 12 Mds FCFA avec le référentiel IFRS du même exercice, statut PROBABLE), CIEC, LNBB, PRSC (tous DEUX_SOURCE, VALIDÉ).

**Découverte 14 — Un bug réel dans `appliquer_gate` : les motifs réglementaires (suspension, sanction, retard) ne remontaient jamais si le titre n'avait aucune donnée financière.** SEMC (Eviosys Packaging Siem) était suspendu de cotation 12 mois (02/01/2025 → 15/12/2025, non-respect du flottant réglementaire 15 %) — un vrai motif d'exclusion niveau 1 — mais le gate retournait "aucune donnée financière disponible" avant même de vérifier les avis réglementaires. **Corrigé : les contrôles suspension/sanction/retard sont désormais vérifiés et accumulés en premier**, indépendamment de la disponibilité des états financiers.

**Bilan final :** 41 ÉLIGIBLE, 3 EXCLU motivés (SCRC : capitaux propres négatifs ; STAC : pertes 2 exercices ; SEMC : suspension), 3 gaps réels assumés :
- **ETIT** : ambiguïté d'entité — le ticker BRVM désigne le groupe Ecobank Transnational Incorporated consolidé (coté aussi à Lagos/Accra), pas la filiale locale Ecobank Togo. Conversion USD→FCFA du résultat groupe jugée insuffisamment fiable sans le rapport officiel.
- **SDSC** : données uniquement trimestrielles et contradictoires (effet de base 2024 exceptionnel apparent), aucun chiffre annuel 2025 fiable trouvé.
- **UNXC** : qualité de scan insuffisante à l'OCR (300 DPI), texte natif corrompu.

## 16. R7 — Garde-fou de fraîcheur

Fonction `verifier_fraicheur()` : seuil 45 jours (cadence bimensuelle de collecte). Alerte `DONNEE PERIMEE` automatique par titre + rapport global `rapport_fraicheur()` (warning CI si périmés détectés). État à l'implémentation : 44/47 titres frais, 3 périmés (STAC et UNXC sans PER depuis 2023 — absence de cotation certains jours ; SCRC 103 jours).

## 17. P5 — Tableau de bord Excel (dashboard)

`dashboard/generer_dashboard.py` — 4 onglets générés entièrement depuis le moteur (zéro formule, zéro édition manuelle) : **Synthèse** (watchlist classée, couleurs), **Fiches titres** (détail complet), **Alertes** (vue transversale turnaround/payout/périmé/profit warning), **Registre** (seuils + fraîcheur). Intégré au CI comme test de fumée (déclenché sur `dashboard/**`).

## 18. Backtest léger — premier test empirique, et une découverte majeure

**Hypothèse testée : un titre décoté vs PER médian sectoriel surperforme-t-il en rendement PRIX à 12 mois ?** Utilise `cours_mensuels` (2018-2026 déjà peuplé), sans collecte supplémentaire.

**Résultat agrégat (87 fenêtres mensuelles, 2018-2026) : décoté +25,5 % vs cher +18,2 %, écart +7,2pp — signal directionnel positif.**

**Mais le signal s'inverse en 2024-2025** (écart -6,2pp puis -8,4pp) — exactement la période sur laquelle repose toute l'analyse qualitative du projet (Coris, Safca...). Diagnostic mené immédiatement :

**Découverte 15 — L'inversion 2024-2025 est un artefact de liquidité, pas un vrai retournement du signal value.** Six titres (UNLC, SIVC, STBC, CFAC, BOAM, BICC) affichent des rendements-prix extrêmes (+377 %, +160 %, +112 %...) totalement déconnectés de leurs fondamentaux réels (SIVC et STBC reculent en résultat net pendant que leur cours explose). En excluant ces 6 titres, le signal se rétablit immédiatement : **décoté +38,0 % vs cher +32,2 %, écart +5,8pp**, cohérent avec le reste de la période.

**Validation directe de l'architecture niveau 3** : ces 6 titres sont précisément le profil que le modificateur de taille/liquidité est censé neutraliser — un investisseur réel n'aurait pas pu entrer ces positions à l'échelle sans faire bouger le prix lui-même. Un backtest naïf équipondéré se fait piéger par ce que la stratégie est conçue pour éviter.

**Règle ajoutée au protocole de validation empirique (section 6) : tout backtest futur doit exclure ou plafonner le poids des titres à liquidité structurellement faible avant calcul de performance.**

**Limites assumées du backtest léger (rappel) :** rendement prix seul (dividendes exclus), fenêtres 12 mois chevauchantes (observations non indépendantes, pas d'intervalle de confiance), aucune correction du biais du survivant. Résultat directionnel, pas une preuve statistique.

## 19. Correction — biais du survivant CONFIRMÉ, pas seulement assumé (10/07/2026)

**Correction d'une affirmation antérieure (section 18) : la recherche initiale ("aucune preuve de radiation 2018-2026 trouvée") était incomplète, pas fausse par excès de prudence — une recherche plus poussée l'a contredite.**

**Movis CI (ticker SVOC, secteur Transport) a été radiée de la BRVM le 26 juin 2025**, via Offre Publique de Retrait, après **trois années consécutives de pertes totalisant ~12 milliards FCFA** (dont -3,51 Mds sur le seul exercice 2023). Cotée depuis 1973 (ex-SIVOM), difficultés opérationnelles documentées par l'agence WARA dès 2018.

**Traitement retenu** : le biais du survivant est désormais **confirmé sur au moins un cas documenté**, non neutralisé dans les backtests déjà réalisés (backtest léger, rendement total, factoriel ROE/croissance) — tous utilisent l'univers actuel de 47 titres, qui exclut par construction Movis CI. Limite assumée et chiffrée, pas simplement théorique.

**Nuance retenue** : le profil de Movis CI (3 pertes consécutives) est exactement le type que notre filtre d'exclusion niveau 1 est censé attraper — notre stratégie ne l'aurait probablement pas recommandée. Mais ça ne résout pas le biais de mesure : impossible de vérifier après coup si le filtre l'aurait exclue à temps.

**Étape A du plan de marche (audit du 10/07/2026) — SDSC** : investigation menée en parallèle. Aucun résultat net annuel fiable trouvé (données trimestrielles fragmentées, cohérent avec le gap déjà documenté), mais découverte d'un signal concret : dégradation opérationnelle sur plusieurs trimestres consécutifs (RN -168% T1 2024, -49% résultat d'exploitation et -77% bénéfice T3 2025), et une source indépendante (Financial Afrik, 17/11/2025) qualifiant explicitement la situation de "divergence prix/fondamentaux" — le cours serait soutenu par le contrôle stratégique du groupe (MSC) plutôt que par la performance. **Correction de bug associée** : les avis contextuels non-excluants ne remontaient que pour les titres avec score calculable — un titre en gap (comme SDSC) ne montrait jamais ses avis, même les plus utiles. Corrigé dans `scoring.py`.

**Étape B du plan de marche — traçabilité (`source_url`)** : 0% → 91% de couverture (83/94 lignes), reconstruit depuis `MANIFESTE.csv` par correspondance date+société, jamais deviné. 8 lignes restent vides (sourcées presse, URL non conservée au moment de la recherche — process à corriger pour les prochaines sessions).

## 20. Étape C du plan de marche — Test de significativité statistique (10/07/2026)

**Résultat majeur, à l'encontre de ce qu'on pensait acquis : le signal décote-vs-secteur n'est PAS statistiquement significatif une fois la structure de corrélation des données correctement prise en compte.**

**Test naïf (traitant 2 543 observations comme indépendantes)** : écart +11,1%, t de Welch = 4,41, IC bootstrap 95% [+6,2% ; +16,0%] — apparemment très significatif.

**Problème identifié** : ces observations proviennent de fenêtres de 12 mois chevauchantes sur seulement 38 titres — une même entreprise apparaît des dizaines de fois, fortement corrélée avec elle-même dans le temps. Traiter ces points comme indépendants viole l'hypothèse du test et **surestime la significativité**.

**Test corrigé (bootstrap en blocs par titre, 38 clusters, 5000 rééchantillonnages)** : IC 95% = **[-0,7% ; +22,8%] — inclut zéro.** L'écart de +11,1% observé pourrait plausiblement être dû au hasard, une fois qu'on respecte la vraie taille d'échantillon effective (38 entreprises, pas 2 543 points).

**Ce que ça implique** :
- Le score composite actuel accorde 35% de poids à la dimension Valorisation (dont la décote sectorielle) sans que ce signal soit confirmé à un niveau de confiance conventionnel.
- La portée de l'étape D du plan de marche (initialement centrée sur la pondération du facteur croissance) **s'élargit à la dimension Valorisation** — les deux dimensions dont l'évidence empirique est la plus fragile.
- Aucun changement de score n'est fait à ce stade — ce résultat est consigné pour éclairer la révision de pondération à venir (étape D), pas pour modifier le moteur immédiatement.

## 21. Filet de sécurité — journal d'extraction brute (11/07/2026)

**Incident déclencheur** : les capitaux propres SMBC et NSBC, extraits une première fois lors d'une analyse ponctuelle, ont été perdus lors d'un retéléchargement ultérieur de `peupler.py` depuis le dépôt distant — aucune trace n'en subsistait ailleurs. Cause racine : `peupler.py` (le code source, tel que committé) est la SEULE mémoire durable du projet ; `brvm.db` est entièrement reconstruit à zéro à chaque exécution, jamais une base persistante en soi.

**Solution retenue** : `collecte/extractions_brutes.jsonl` — un journal simple, une ligne JSON par extraction, alimenté **immédiatement** après chaque donnée trouvée, avant même sa mise en forme dans les tuples structurés de `peupler.py`.

**Format** : `{"ticker", "exercice", "champ", "valeur", "source", "date_extraction", "integre_a_peupler"}`. Le champ `integre_a_peupler` permet de savoir en un coup d'œil (`grep false`) si une extraction attend encore d'être formalisée — c'est le vrai filet : si l'intégration dans `peupler.py` est interrompue, la donnée brute reste récupérable ici.

**Convention adoptée pour la suite** : toute extraction destinée à être réutilisée est écrite dans ce journal au moment même où elle est trouvée, avant de poursuivre. Le journal est committé au même rythme que les autres fichiers du lot en cours.


## 22. Audit d'étape complet (11/07/2026) et résolution des 3 recommandations prioritaires

**Audit complet mené sous 6 casquettes** (expert-comptable, enseignant-chercheur, fiscaliste UEMOA, conseiller SGI, ingénieur). Constat majeur : **l'angle mort fiscal UEMOA est quasi total** — aucun traitement de la retenue à la source sur dividendes dans le moteur ou le dashboard, alors que le persona fiscaliste est assigné depuis la conception. Reste un chantier ouvert, pas encore traité.

**Résolution recommandation 1 — SDSC, tentative finale.** Deux versions du document "exercice 2022" jamais tentées ont été récupérées et passées à l'OCR — confirmées être des doublons, et le texte extrait n'est qu'un fragment de la section HAO, pas le résultat net principal. **Conclusion : aucun état financier annuel complet n'existe dans notre collecte au-delà de l'exercice 2022 pour SDSC — un vrai trou de collecte, pas un échec de recherche.** Effort jugé épuisé ; le gap est accepté comme structurel. **Note de risque portefeuille réel** : SDSC reste 24% d'une position réelle sans donnée fondamentale fiable malgré 3 tentatives documentées distinctes (recherche presse, OCR direct, documents alternatifs).

**Résolution recommandation 3 — significativité du facteur croissance.** Même méthode que pour la décote (bootstrap en blocs par titre, 27 clusters, 65 observations) : écart observé -18,0%, **IC 95% [-46,5% ; +5,8%] — inclut zéro, non significatif.** Cohérent avec le résultat déjà obtenu sur la décote (section 20) : **aucun des deux facteurs principaux du score composite n'est statistiquement significatif** sur l'échantillon actuel. Cause probable : puissance statistique insuffisante (échantillon encore petit), pas nécessairement une réfutation définitive des facteurs eux-mêmes.

**Résolution recommandation 4 — stabilisation `source_url`.** Cause racine identifiée : le champ vit dans une liste séparée (`SOURCE_URLS`) sans lien structurel avec `ETATS`, d'où une dérive répétée à chaque lot (passée sous 80% au moins 3 fois). **Corrigé** : le golden test 52 devient une liste nominative exhaustive des lignes manquantes (seuil plancher abaissé à 70%, la vraie protection étant la liste elle-même, consultable avant chaque nouveau lot) plutôt qu'un pourcentage agrégé qui masquait la dérive jusqu'au seuil.

*Fin du document v2.3 — mettre à jour la version et le registre des seuils à chaque évolution.*
