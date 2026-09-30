# Chantiers — file de travail de la boucle automatique

Ce fichier est la **mémoire de la boucle**. Deux fois par jour, une session neuve
démarre sans aucun souvenir de la précédente : elle clone le dépôt, lit ce
fichier, et c'est tout ce qu'elle sait. Ce qui n'est pas écrit ici n'existe pas
pour elle.

Mis en place le 28/09/2026. **Protocole révisé le 30/09/2026** (voir *Pourquoi ce
protocole a changé*, en bas). Régime d'autonomie : **pré-autorisation par
classe**.

**Le journal complet vit dans `docs/JOURNAL.md` et ne se lit PAS au démarrage.**
Le résumé du dernier cycle, plus bas, suffit à reprendre. On ouvre l'archive
seulement pour retrouver une mesure ancienne ou l'origine d'une règle.

---

## Les deux classes, et ce que Claudia valide

Claudia ne valide plus ligne par ligne : elle a validé **une fois** la règle
ci-dessous, le 30/09/2026. Chaque chantier porte une ligne `- classe :`.

**`VERTE` — le cycle exécute sans attendre.** Réservée à ce qui est réversible
d'un `git revert`, ne touche aucune donnée certifiée, et reste couvert par une
barrière existante : code, tests, outillage, fichiers nouveaux, suppression de
code mort, normalisation de format qui ne change aucune valeur.

**`ORANGE` — le cycle mesure sans attendre, et s'arrête avant d'écrire.** Tout ce
qui demande un arbitrage de méthode ou modifie une donnée certifiée. Le cycle
produit le **diagnostic chiffré**, l'inscrit dans le bloc du chantier, et n'écrit
rien. L'écriture attend `- validation : OK`.

Conséquence voulue : **aucun cycle n'est jamais inoccupé**, et tout chantier
ORANGE arrive chez Claudia déjà mesuré — sa décision tient en un mot.

**La boucle ne reclasse jamais un ORANGE en VERTE.** Elle peut proposer un
reclassement dans son compte rendu ; seule Claudia édite la ligne `- classe :`.
Dans le doute, un chantier neuf naît **ORANGE**.

### Ce que Claudia édite, et rien d'autre

```
- validation : EN ATTENTE     →     - validation : OK      (autoriser l'écriture)
- validation : NON — motif                                 (refuser ou réorienter)
- classe : ORANGE             →     - classe : VERTE       (élargir l'autonomie)
```

Directement sur GitHub, au crayon, depuis un téléphone. Aucune réponse en
conversation n'est nécessaire : la boucle ne lit que ce fichier.

## Ce que fait chaque cycle, dans l'ordre

1. **Cloner, lire ce fichier.** Pas le journal.
2. **Contrôle anti-collision, avant tout travail.** `git log --since="3 hours ago"`
   sur `main` : si une annonce de cycle y figure **sans** son commit de clôture,
   une autre session travaille. **S'arrêter immédiatement**, le dire en une ligne,
   ne rien reconstruire. Un cycle abandonné tôt coûte presque rien ; deux cycles
   qui se marchent dessus coûtent deux fois tout.
3. **Vérifier l'état** : CI verte ? commits nouveaux ? le bloc *Dernier cycle*
   signale-t-il quelque chose en suspens ?
4. **Exécuter un chantier, et un seul.** L'ordre est **entièrement déterminé** —
   aucun arbitrage n'est laissé au cycle, parce que deux cycles qui arbitrent
   séparément arbitrent différemment :

   1. un `ORANGE` portant `validation : OK` **dont la ligne `statut` ne dit pas que
      la passe autorisée est déjà consommée** — Claudia attend un résultat, il passe
      avant tout ;
   2. sinon la première `VERTE` ;
   3. sinon le premier `ORANGE` non encore mesuré, dont on ne fait que **la
      mesure**, sans rien écrire.

   Dans chaque rang : priorité la plus haute d'abord, et **à priorité égale, le
   plus petit numéro de chantier**. Aucun cycle n'est jamais inoccupé.

   *Clause ajoutée au rang 1 le 30/09/2026 (cycle 9), et pourquoi.* Sans elle, un
   ORANGE dont la mesure pré-autorisée est faite reste le premier du rang 1 et
   **chaque cycle suivant la refait** : C16, mesuré ce cycle, aurait été repris
   indéfiniment. Corollaire : un cycle qui consomme une passe pré-autorisée **doit**
   l'écrire sur la ligne `statut` du chantier, comme C16 le fait maintenant.
5. **Chasser une famille de défauts que rien ne surveille**, et en faire un test.
   **Une fois par jour, au cycle du matin seulement** — c'est l'étape la plus
   chère et la plus facile à dupliquer, et deux sessions qui lisent le même
   fichier arrivent aux mêmes soupçons.
6. **Proposer** le chantier suivant, diagnostic fait, effet mesuré, avec sa classe.
7. **Réécrire ce fichier** — file, bloc *Dernier cycle* (25 lignes au plus) —
   **ajouter l'entrée complète en tête de `docs/JOURNAL.md`**, committer, pousser.

## Règles que la boucle ne franchit pas

Chacune vient d'une erreur réelle.

- **Ne jamais écraser une valeur adossée à `config/faits_qualitatifs.yaml` ou à
  une note qui documente une analyse humaine.** Signaler, et s'arrêter. Le
  résultat 2025 d'Uniwax avait été validé à la main sur les résolutions d'AGO ;
  une mise en quarantaine automatique l'a effacé, et c'est un golden test qui a
  arrêté l'erreur.
- **Une case vide vaut mieux qu'une valeur approchée.** Jamais d'estimation pour
  combler un trou.
- **Preuve à deux côtés obligatoire** avant de corriger une donnée certifiée :
  une identité comptable qui se ferme, ou deux sources indépendantes. Tout écrire
  dans la note et dans le message de commit, et laisser la révocation possible
  d'un `git revert`.
- **Un chantier par cycle, un commit par chantier.**
- **Refaire `git fetch origin main` juste avant de committer, et relire ce qui est
  arrivé.** Si un cycle concurrent a poussé entre-temps : reprendre son travail
  par rebase, repasser les barrières **après** la fusion, et **abandonner ce qui
  est devenu redondant** plutôt que de le fusionner. Deux contrôles sur la même
  identité, avec deux registres listant les mêmes cas, se désynchronisent et ne
  surveillent plus rien. Le 28/09 puis le 30/09, deux sessions ont écrit deux
  fois le même contrôle, puis deux fois le même chantier.
- **Annoncer la famille chassée avant de travailler**, et pousser cette annonce
  seule. C'est ce que lit le contrôle anti-collision de l'étape 2.
- **Jamais de commit si une barrière tombe.** Tout annuler, ne committer que le
  constat d'échec.
- **Mesurer avant d'affirmer.** Ne citer que des nombres calculés dans le cycle.

## Barrières : lesquelles, et quand

**Complètes** — `peupler.py`, les quatre chargeurs, `tester.py`, `profils.py`,
`tester_donnees.py`, `avis_brvm.py --test`, `notations.py --test`,
`generer_dashboard.py` — dès que le commit touche `moteur/`, `collecte/`,
`config/`, `donnees/`, `outils/`, `app.py` ou `dashboard/`.

**Aucune** si le commit ne touche que `CHANTIERS.md` ou `docs/`. Reconstruire la
base pour un commit de texte a coûté un cycle entier les 28 et 30/09.

**Une barrière ne tourne pas dans le bac à sable, et ce n'est pas une régression.**
`dashboard/generer_dashboard_html.py` échoue à la compilation avec
`SyntaxError: f-string expression part cannot include a backslash`. Vérifié le
30/09/2026 (cycle 10) : **il échoue identiquement sur `HEAD`**, parce que le bac à
sable porte Python **3.11** alors que `pages.yml` et `tests.yml` épinglent
**3.12**, où PEP 701 autorise l'antislash dans une f-string. Ne pas chercher à le
« réparer » : c'est l'environnement qui diffère, pas le fichier. Les barrières à
passer sont `generer_dashboard.py` (celle de la liste) et la CI pour l'autre.

## Moyens disponibles

- **Poussée directe sur `main`** : opérationnelle depuis le 27/09/2026.
- **Déclenchement des workflows par l'API** avec `$GH_TOKEN` : vérifié le
  28/09/2026 (`204` sur `tests.yml`). Seule voie vers brvm.org, le bac à sable ne
  l'atteint pas. Utiles : `collecte.yml` (P2b), `inventaire.yml` (P2a),
  `extraction_etats.yml` (P10), `reparation.yml` (P2c), `notations.yml` (P12).
- **Hors de portée** : un PDF scanné que l'OCR ne rend pas. Quand l'OCR ne rend
  rien, le dire, pas deviner.

---

# La file

## C1 — Distributions non récurrentes faussent l'axe rendement

- classe : VERTE — fait ; toute reprise ne touche que du code et des seuils versionnés
- statut : FAIT le 30/09/2026 (cycle 7) — voir le journal ; retrait de l'axe de décote laissé à C16
- validation : OK
- autonomie : complète, aucune donnée extérieure nécessaire
- priorité : 1

**Le constat.** FTSC porte une prime de rendement de **+79 points** et SIVC de
**+20 points**, quand les 45 autres titres tiennent entre −6 et +1. Ces deux-là
écrasent tout classement par le rendement.

**Ce n'est pas une erreur de données.** Filtisac a bien versé 1 726,56 FCFA par
action le 30/09/2025 : avec 14,1 millions d'actions cela fait 24,4 Md
distribués, et ses capitaux propres passent de 43 454 à 15 703 M sur l'exercice.
La société a distribué le pic HAO de 2024 (résultat 18 595 M, contre 466 M en
2025). Le rendement de 86,3 % est arithmétiquement exact et économiquement
non reproductible. SIVC est un autre cas : son dividende de référence date de
**2017**, neuf ans.

**Ce qu'il faut faire.** Distinguer un rendement récurrent d'un rendement
accidentel : drapeau `DISTRIBUTION_NON_RECURRENTE` quand la distribution
dépasse nettement la moyenne des exercices précédents ou quand le dividende de
référence a plus de deux ans, retrait de ces titres de l'axe rendement et de la
prime, mention explicite sur la fiche. Un test verrouille le seuil.

**Terminé quand** : aucune prime de rendement n'excède un seuil de plausibilité
sans porter le drapeau ; FTSC et SIVC sortent du classement par rendement en
l'expliquant ; un test de la section 13 fige la règle.

## C2 — Convention brut/net du rendement

- classe : ORANGE — tranche une convention et modifie des valeurs certifiées
- statut : À FAIRE
- validation : —
- autonomie : complète
- priorité : 2

La base mélange deux conventions. BICB porte un dividende de 254,60, soit
exactement 268 × 0,95 — donc **net**. SHEC porte ~85,56, soit le brut de son
projet d'affectation. La note qualitative d'ECOC dit déjà que **son profil est
sensible à cette convention** : en brut, le seuil du profil RENDEMENT serait
franchi. Le `payout_ratio` saisi, lui, est uniformément brut (vérifié sur les
29 lignes renseignées le 27/09/2026).

**Second axe, mesuré le 28/09/2026 — l'exercice de rattachement.** L'échelle de
`payout_ratio` est saine : 29 valeurs réelles, toutes entre 0,000 et 1,258, donc
uniformément des fractions, aucun mélange fraction/pourcentage. Mais le
*rattachement* n'est pas uniforme. Testé par l'identité de variation des
capitaux propres — distribution implicite = `RN(n) − ΔCP` — contre la
distribution déclarée, sur les 11 paires où `payout_ratio` est disponible :

| alignement | définition | BBGCI (4 paires) | CABC (6 paires) |
|---|---|---|---|
| A | `payout(n−1) × RN(n−1)` — proposé sur n−1, versé en n | 0,6 à 12,3 % | 7,1 à 79,3 % |
| B | `payout(n) × RN(n)` — rattaché à l'exercice de versement | 5,4 à 48,6 % | 1,2 à 26,2 % |

BBGCI ferme sous A, CABC sous B, et SDSC 2024 ferme sous B **à 0,0 %** (5 008,0
implicite contre 5 008,1 déclaré — le même nombre). Le moteur, lui, prend le
`payout_ratio` le plus récent non nul sans jamais regarder son exercice
(`profils.py`, boucle `for _e, _rn, _cp, p in etats`), et s'en sert pour fermer
les profils RENDEMENT et VALUE via `payout_ok = payout <= 1.00`. Un décalage
d'un an peut donc basculer un profil.

**Réserve explicite** : ce n'est pas une preuve, c'est un signal. L'identité ne
se ferme exactement que si les seuls mouvements de capitaux propres sont le
résultat et le dividende — une augmentation de capital, des écarts de
conversion, des réserves reclassées ou des intérêts minoritaires la faussent
aussi. Deux sources indépendantes ou un tableau de variation des capitaux
propres trancheraient. À faire avant de corriger quoi que ce soit.

**Terminé quand** : la convention est tranchée sur les DEUX axes (brut/net ET
exercice de rattachement), écrite dans `config/`, appliquée partout, l'effet est
mesuré titre par titre, et un test empêche le mélange.

## C3 — Journal des prédictions

- classe : VERTE — crée un fichier neuf, n'en touche aucun
- statut : À FAIRE
- validation : —
- autonomie : complète
- priorité : 3

`journal_profils.csv` n'existe pas. À chaque exécution, figer par titre le
profil, le grade, le cours, le PER et la date. Sans cela l'outil reste un
instantané dont personne ne pourra jamais dire s'il avait raison.

**Terminé quand** : le fichier existe, s'alimente à chaque passage de
`profils.py`, ne réécrit jamais une ligne passée, et un test vérifie qu'il
s'allonge.

## C4 — Divisions de nominal non enregistrées

- classe : ORANGE — écrit dans `operations_sur_titre.csv` et change la lecture des cours
- statut : À FAIRE
- validation : —
- autonomie : partielle
- priorité : 4

`collecte/operations_sur_titre.csv` contient **une seule ligne**, et le test de
continuité signale **12 chutes de cours supérieures à 60 %** non documentées :
ECOC 26/12/2018, FTSC 30/01/2018, PRSC 24/10/2019, SAFC 21/12/2018 et
07/01/2019, SEMC 19/12/2018, SIBC 15/06/2018, SLBC 27/09/2024, SMBC 22/02/2019,
STBC 12/07/2018 et 27/07/2018, TTLC 12/02/2018.

**Mise à jour du 30/09/2026 (cycle 8) : elles sont 13, et 3 n'en sont pas.**
Le versement de C15 a ajouté une date à l'alerte — **SAFC 02/01/2019** — qui monte
donc à **13**. Surtout, la chasse du même cycle a mesuré que **trois de ces dates
ne sont pas des divisions de nominal** : le cours y chute puis **revient** au
niveau d'avant en une à dix séances, ce qu'une division ne fait jamais.

- **STBC 12/07/2018** : 44 995 → 11 315 → **44 995 le lendemain** (facteur 3,98).
- **SAFC 21/12/2018** : 5 300 → 215 → **5 300 le 31/12** (facteur 24,65).
- **SAFC 02/01/2019** : 5 300 → 215 → **5 300 le 04/01** (facteur 24,65).

Ce sont des **collisions d'échelle**, inscrites en **C18** avec deux cas de plus
que ce contrôle-ci ne voit même pas. Ne pas chercher d'avis de fractionnement pour
ces trois dates : il n'y en a pas. Les dix autres restent à documenter.

Première passe **sans réseau** : `collecte/avis_brvm.py` sait déjà reconnaître
un fractionnement, donc fouiller d'abord le corpus d'avis déjà collecté. Ce qui
manque après cela seulement justifie un `collecte.yml`.

**Terminé quand** : chacune des 13 dates est soit documentée avec sa source, soit
explicitement écartée avec son motif — les trois collisions d'échelle relèvent de
C18 et s'écartent par là ; l'alerte de fraîcheur s'éteint.

## C5 — Exercices manquants : CFAC 2025 et NEIC 2025

- classe : ORANGE — saisie d'exercices certifiés
- statut : À FAIRE
- validation : —
- autonomie : complète (dispatch vérifié)
- priorité : 5

Nommés par l'alerte de fraîcheur de `tester_donnees.py`. CFAO Mobility Côte
d'Ivoire et Nei-Ceda. Passer par `collecte.yml` puis `extraction_etats.yml`.

**Terminé quand** : les deux exercices sont en base avec leur source, ou
l'absence du document est constatée et datée.

## C6 — Trou BICC 2022

- classe : ORANGE — saisie d'un bilan certifié
- statut : À FAIRE
- validation : —
- autonomie : complète (dispatch vérifié)
- priorité : 6

Seule chose qui maintient `RATTRAPAGE` et `BENEFICE_NON_REPRESENTATIF` sur la
BICI CI. La chaîne certifiée est connue et écrite dans la note de la ligne 2023
(2021=9603 → 2022=12391 → 2023=16694 → 2024=26226 → 2025=36520) : il manque le
bilan, pas le résultat.

**Terminé quand** : la ligne 2022 est complète et les deux drapeaux tombent, ou
le motif de leur maintien est documenté.

## C7 — TTLS, dernier titre sans ROE

- classe : ORANGE — saisie de capitaux propres certifiés
- statut : À FAIRE
- validation : —
- autonomie : complète (dispatch vérifié)
- priorité : 7

46 titres sur 47 ont un ROE depuis le 27/09/2026. TotalEnergies Marketing
Sénégal est le dernier. Ses capitaux propres manquent.

**À traiter d'une seule main avec C11** : le cycle qui ouvrira les documents TTLS
pour y lire les capitaux propres y lira aussi le référentiel comptable des
exercices 2024 et 2025 — c'est exactement ce que C11 réclame, et la divergence de
comparatif TTLS 2025 se tranche alors sans second accès à brvm.org.

**Terminé quand** : 47/47, ou l'impossibilité est documentée.

## C8 — Extracteur GCR

- classe : VERTE — code d'extraction ; toute écriture dans le fonds de notations repasse en ORANGE
- statut : À FAIRE (maintenu en file sur décision du 27/09/2026)
- validation : —
- autonomie : complète
- priorité : 8

Les 25 extractions de notations réussies sont toutes Bloomfield ; 8 des 10
échecs sont GCR. Mon estimation du 27/09/2026 était qu'il ne rapporterait
qu'un seul ROE, celui de TTLS — **estimation à refaire** une fois C7 traité,
puisque le gain dépend de ce qui reste réellement manquant. Sa vraie valeur est
ailleurs : une deuxième agence permet de croiser les notations au lieu de
dépendre d'une seule.

**Mesuré le 28/09/2026 (cycle 2)** : l'autotest de `collecte/notations.py` rend
déjà « PDF GCR 10/10 ». Le critère de terminaison ci-dessous est donc **déjà
satisfait tel qu'il est écrit**, ce qui veut dire qu'il ne décrit pas le vrai
travail. Le fonds compte 4 `ECHEC` pour 291 `OK` et 87 `SANS_NOTE` : c'est sur
ces 4 qu'il faut regarder, pas sur l'analyseur d'échantillon. À rediagnostiquer
avant toute proposition.

**Terminé quand** : l'extracteur passe les 10 PDF GCR d'échantillon, ou le
motif d'abandon est chiffré sur des données fraîches.

## C9 — Extinction de P5b et retrait du code mort

- classe : VERTE — retrait de code mort, réversible, couvert par `pages.yml` et le test de fumée
- statut : À FAIRE
- validation : —
- autonomie : complète
- priorité : 9 — **en dernier**

`dashboard/generer_dashboard.py` (208 lignes), `moteur/scoring.py` (735) et
`moteur/signaux.py` (439). Attention : `tester_donnees.py` lance
`generer_dashboard.py` comme test de fumée, et `pages.yml` en dépend. Les trois
se démontent ensemble ou pas du tout.

**Terminé quand** : le code est retiré, aucune barrière ne s'appuie plus
dessus, et la publication GitHub Pages fonctionne toujours.

## C10 — `dividendes.date_paiement` n'est pas une colonne de dates

- classe : VERTE — normalisation de format : aucune valeur ne change, un mois non reconnu arrête le script
- statut : **FAIT le 30/09/2026 (cycle 10)** — voir *Fait le 30/09/2026* en bas de ce bloc
- validation : —
- autonomie : complète, aucune donnée extérieure nécessaire
- priorité : **2** — **avant C3**, dont le journal datera ses lignes. *Corrigé le
  30/09/2026 (cycle 9) : la priorité était 3, à égalité avec C3, et l'ordre
  déterministe (« à priorité égale, le plus petit numéro ») faisait donc passer C3
  d'abord — l'inverse exact de ce que cette ligne demande. C10 est le prochain
  chantier du rang VERTE.*

Trouvé le 28/09/2026 en cherchant à dater les dividendes. La colonne mélange
**deux formats incompatibles**. **Comptes refaits sur la base du 30/09/2026
(cycle 9) — ceux du 28/09 ne valent plus** : la table porte **311 lignes**, pas 326.

- **296 lignes** (95 %) au format français abrégé, année sur deux chiffres :
  `24-juil.-17`, `30-sept.-24`, `24-août-22`. Toutes issues de
  `collecte/dividendes_par_exercice.csv (Piste D, confiance ELEVEE)` —
  `charger_dividendes_exercice.py` insère la chaîne brute sans la normaliser.
- **12 lignes** en ISO `aaaa-mm-jj`, venues de `donnees/base/dividendes.csv`.
- **3 lignes** nulles (SDSC).

Trois conséquences, dont une déjà armée :

1. **Tri et comparaison faux, et l'ampleur est maintenant chiffrée.**
   `scoring.py::dividendes()` fait `ORDER BY date_paiement DESC` : sur du français
   abrégé l'ordre est alphabétique, pas chronologique. **Mesuré le 30/09/2026
   (cycle 9)** : sur les **49 tickers** portant au moins deux dividendes datés, ce
   tri rend un autre versement que le plus récent pour **34 d'entre eux** — ABJC,
   BNBC, BOAB, BOABF, BOAC, BOAM, BOAN, BOAS, CABC, CBIBF, CFAC, CIEC, ECOC, ETIT,
   FTSC, NEIC, NSBC, NTLC, ONTBF, PALC, PRSC, SCRC, SDSC, SEMC, SHEC, SIBC, SLBC,
   SMBC, SNTS, SOGC, SPHC, STBC, TTLC, TTLS. Ce n'est donc pas un défaut latent :
   il est actif partout où ce tri sert.
2. **Extraction d'année impossible.** `substr(date_paiement,1,4)` rend `24-j`.
   C'est ce qui a fait échouer ma première tentative de mesurer le décalage
   entre année de paiement et exercice couvert — mesure donc **non faite**,
   elle reste à produire une fois la colonne normalisée.
3. **Déduplication déjà cassée, en attente de se déclencher.**
   `collecte_boc_quotidien.py` normalise en ISO (`date_dividende_vers_iso`)
   puis déduplique par `SELECT 1 FROM dividendes WHERE ticker=? AND
   montant_net=? AND date_paiement=?`. Une date ISO ne s'égalera jamais à la
   forme française du même jour : le jour où le BOC réobserve un dividende déjà
   chargé par la Piste D, il l'insère en double. Aucun doublon mixte
   n'existe encore (revérifié le 30/09/2026 : **0 paire (ticker, jour) portant les
   deux formats**, sur 311 lignes) — ce défaut-là, lui, reste latent.

**Faisabilité vérifiée le 30/09/2026 (cycle 9)** : `date_dividende()` de
`profils.py`, qui porte déjà la table des mois français abrégés, convertit les
**311 lignes sans une seule exception**. La migration peut donc être totale, et le
refus d'écrire sur mois non reconnu ne devrait rien écarter.

**Attention** : la conversion doit lever l'ambiguïté du siècle sur l'année à
deux chiffres, et refuser plutôt que deviner sur un mois non reconnu. Un mois
français abrégé mal orthographié doit échouer bruyamment.

**Terminé quand** : la colonne est ISO sur les 311 lignes via un script de
migration idempotent dans `outils/`, les chargeurs normalisent à l'entrée, la
déduplication de `collecte_boc_quotidien.py` retrouve bien les lignes
existantes, et un test refuse toute date non ISO dans la table.

### Fait le 30/09/2026 (cycle 10)

Quatre pièces, et les quatre critères de terminaison sont remplis.

- **`collecte/dates_dividendes.py`** — seule définition de la conversion dans le
  dépôt, avec autotest (`--test`, **27 cas, 0 échec**). Liste **blanche exacte**
  de mois, sans aucune correspondance par préfixe : `24-jullet-17` échoue, là où
  un préfixe de trois lettres l'aurait pris pour un 24 juillet. Refuse aussi un
  jour inexistant (`31-fevr.-20`, et `2025-02-31` en ISO), une année hors de la
  fenêtre 1998–2027 (`30-sept.-97` → refus, c'est ainsi que l'ambiguïté du siècle
  est levée au lieu d'être masquée), et un mois numérique (`24/07/2017`, ambigu).
- **`outils/migration_dates_dividendes_iso.py`** — procès-verbal exécutable.
  **362 lignes converties sur 364**, 2 cases vides laissées vides, aucune autre
  colonne touchée. Six gardes : entête et comptes, ancres, empreintes SHA-256
  **avant** et **après**, réserialisation exigée à l'octet près avant écriture,
  refus sur date illisible (0 cas), et relecture après écriture. **Relancé deux
  fois : sans effet**, il constate « migration DEJA APPLIQUEE ».
- **Les trois chargeurs normalisent à l'entrée** — `charger_dividendes_exercice.py`
  (une date illisible fait écarter la ligne, avec message, jamais une date
  devinée), `moteur/peupler.py` (garde sur `donnees/base/dividendes.csv`, qui est
  déjà ISO : aucune valeur ne change), et `historiser_dividendes_exercice.py`, qui
  émet désormais de l'ISO — sans quoi une régénération aurait défait la migration.
- **Test : section 23 de `tester_donnees.py`, 13 contrôles.**

**Effet mesuré, avant/après, sur la base du jour.**

| | avant | après |
|---|---|---|
| dates non ISO en base | 296 | **0** (308 ISO, 3 nulles sur 311) |
| tickers dont `ORDER BY date_paiement DESC` rend le mauvais versement | **34 / 49** | **0 / 49** |
| tickers dont `int(date[:4])` échoue, donc bloc « régularité du dividende » de `scoring.py` sauté en silence | **45 / 49** | **0 / 49** |
| dividendes témoins retrouvés par la déduplication du BOC | **0 / 40** | **40 / 40** |
| champs de `collecte/profils.json` déplacés | — | **0** (fichier identique) |

Le deuxième effet n'était pas chiffré avant ce cycle et c'est le plus grave :
`int("24-j")` lève `ValueError`, avalée par un `except (ValueError, TypeError):
pass`, donc le bonus de 20 points, le malus de 20 et l'alerte « dernier dividende
versé il y a N ans » ne s'exécutaient sur **aucun** des 45 titres concernés.

**Trouvé en posant les gardes, inscrit en C19** : 12 lignes strictement dupliquées
dans `dividendes_par_exercice.csv`, qui passent à 16 après migration — quatre
événements y étaient dédoublés sous **deux orthographes du même jour**. Et une
régénération du fichier par son propre générateur ne rend pas le fichier commité :
un événement de plus (FTSC 2016).

## C11 — Le référentiel comptable n'est pas une colonne de la base

- classe : ORANGE — décide de refuser un calcul : arbitrage de méthode
- statut : À FAIRE
- validation : —
- autonomie : complète, aucune donnée extérieure nécessaire
- priorité : 4

**Le constat, trouvé le 28/09/2026 par la confrontation du comparatif N-1.**
Sur les **95 paires confrontables** de `etats_financiers.csv`, **4** sont en
désaccord : le document de l'exercice N republie pour N−1 un résultat qui n'est
pas celui de notre ligne N−1. **Trois de ces quatre sont une rupture de
référentiel comptable**, lisible dans l'URL de la source :

- **CIEC 2022** vient d'un document IFRS, les lignes 2023 et 2024 de documents
  SYSCOHADA, et le document 2025 publie les deux. Écart 4,60 % sur la paire
  2023, 4,31 % sur la paire 2025.
- **TTLS 2025** est en IFRS, sa ligne 2024 en SYSCOHADA. Écart 0,69 %.
- La quatrième, **STBC 2025**, n'est pas une rupture de référentiel mais un
  retraitement assumé : le document s'intitule « annule et remplace le
  précédent » et republie 2024 à 44 173,762 contre 44 730,358. Écart
  556,596 M (1,24 %).

**Pourquoi c'est grave.** La croissance est calculée sur la série complète, donc
à travers la rupture. Mesuré ce cycle : la croissance de CIEC passe de
**10,09 %/an à 6,69 %/an** — 3,40 points — si l'on retire 2022, le seul
exercice IFRS de sa série. Pour TTLS la rupture est à l'autre bout : le
glissement du dernier exercice (−5,06 %) est homogène, car le moteur utilise
bien le comparatif IFRS du document lui-même, mais la moyenne sur quatre
exercices (1,11 %/an) enjambe le changement. Les deux titres portent pourtant le
drapeau `CROISSANCE_CORROBOREE` : une corroboration de **transcription** ne dit
rien de l'**homogénéité du référentiel**, et rassure donc à tort.

**Pourquoi la base ne peut pas encore l'exprimer.** Il n'y a aucune colonne de
référentiel dans `etats_financiers.csv`. Le référentiel n'est aujourd'hui
devinable que par l'URL de la source, et seulement **20 des 167 lignes** de
`source_urls.csv` le nomment. Deux titres à rupture sont détectés par cette
voie (CIEC, TTLS) — exactement deux des quatre divergences ci-dessus, ce qui
corrobore la méthode sans couvrir les 147 lignes muettes.

**Ce qu'il faut faire.** Une colonne `referentiel` dans
`etats_financiers.csv`, renseignée quand le document le dit et laissée **vide**
sinon (une case vide vaut mieux qu'une valeur approchée), puis le refus de
calculer une croissance moyenne à travers une rupture : soit la série est
restreinte au référentiel homogène le plus récent, soit un drapeau
`RUPTURE_REFERENTIEL` le dit sur la fiche. BICB, traité à la main le
27/09/2026, est le précédent : la même question avait alors été tranchée pour
un seul titre.

**Terminé quand** : la colonne existe, aucune croissance ne traverse une
rupture sans drapeau, l'effet est mesuré titre par titre, et un test de la
section 13 empêche le retour du mélange.

## C12 — Le bilan de SIBC 2025 ne se ferme pas

- classe : ORANGE — correction d'un bilan certifié, document hors de portée
- statut : À FAIRE
- validation : —
- autonomie : partielle — document hors de portée du bac à sable
- priorité : 5

**Le constat, trouvé le 28/09/2026.** Sur les **113 bilans renseignés**, un
seul ne se ferme pas : **SIBC 2025**, total actif **1 881 733** contre total
passif **1 685 249**, soit **196 484 M d'écart (10,44 %)**, sur une ligne
marquée **VALIDE**. Ce n'est pas un retraitement : un bilan qui ne se ferme pas
est une impossibilité arithmétique, donc un défaut d'extraction.

**Hypothèse, non tranchée.** Les capitaux propres de la ligne valent
204 765 M ; 1 685 249 + 204 765 = 1 890 014, à 8 281 M du total actif. Le total
passif extrait est donc vraisemblablement le **passif exigible seul, hors
capitaux propres** — mais les 8 281 M résiduels interdisent de l'affirmer, et
rien ne sera corrigé à l'aveugle.

**Portée du défaut, mesurée.** `total_actif` et `total_passif` ne traversent
pas le moteur de profilage : ils ne servent à aucun score. Ils sont en revanche
**affichés sur la fiche publiée** (`dashboard/generer_dashboard_html.py`, la
requête des fondamentaux les sélectionne). Le défaut est donc visible par le
lecteur sans peser sur le classement — d'où sa priorité derrière C11.

**Terminé quand** : le bilan se ferme sur les valeurs du document source
(`20260421 — rapport d'activités annuel et états financiers — exercice 2025 —
SIB`), relevé par `extraction_etats.yml` ou à la main, avec son procès-verbal
dans `outils/` ; ou l'impossibilité de lire le document est constatée et datée,
et la ligne repasse de VALIDE à PROBABLE.

## C13 — `preparer_base()` avale tout échec de chargeur

- classe : VERTE — fait ; plomberie pure
- statut : FAIT le 30/09/2026 (cycle 6) — voir le journal
- validation : OK
- autonomie : complète, aucune donnée extérieure nécessaire
- priorité : 1 — à égalité avec C1, sur un autre axe : plomberie contre méthode

**Le constat, mesuré le 28/09/2026 (cycle 4).** `app.py::preparer_base()` lance
ses chargeurs en `subprocess.run(..., check=False, capture_output=True)` puis
rend `DB.exists()`. Un chargeur qui échoue rend donc `1`, ce code est jeté, sa
sortie d'erreur est capturée puis abandonnée, et la fonction répond « base
disponible ».

**Mesuré par injection d'une panne dans `charger_cours_quotidien.py`**, sur la
chaîne des six scripts :

- codes de retour réellement vus : `charger_cours_quotidien.py` → **1**, tous
  les autres 0 ;
- valeur rendue par `preparer_base()` : **`True`** ;
- `cours_quotidien_boc` : **0 ligne** ;
- `app.py::charger()` bascule alors sur sa branche de repli `cours_mensuels`, et
  le dernier cours servi devient **2026-07** au lieu du **2026-09-25** collecté.

**Pourquoi c'est grave : c'est la régression n°2 rejouée.** L'en-tête de
`moteur/tester_donnees.py` explique que ce fichier existe à cause de trois
régressions, dont celle-ci mot pour mot — « le moteur et l'application lisaient
`cours_mensuels` alors que la collecte quotidienne allait jusqu'au 01/09 ». Le
repli est conçu pour être silencieux, et il est aujourd'hui atteignable par une
simple panne de chargeur sans qu'aucune erreur n'apparaisse nulle part.

**Second effet, du même ordre que celui du cycle 1.** `profils.py` est dans la
même liste et tourne sur la base dégradée : la mesure a produit
**849 insertions et 854 suppressions** dans `collecte/profils.json`, fichier
commité. Un échec de chargeur ne dégrade donc pas seulement l'affichage, il
réécrit un fichier de référence. (Restauré par `git checkout` dans le cycle.)

**Ce qu'il faut faire.** Relever le code de retour de chaque script, refuser de
servir une base construite sur un échec, et faire remonter le motif à l'écran
plutôt que de le capturer pour le jeter. La branche de repli `cours_mensuels`
doit dire explicitement qu'elle est un repli, jamais l'afficher comme la donnée
du jour. Un test injecte la panne et vérifie que le silence est rompu.

**Terminé quand** : un chargeur en échec empêche le service ou s'annonce à
l'écran, `profils.json` n'est plus réécrit sur une base incomplète, et un test
de `tester_donnees.py` fige la propriété par injection de panne.

## C14 — `liquidite_quotidienne` : 73 141 lignes écrites, lues par personne

- classe : ORANGE — brancher ou retirer la liquidité est un arbitrage, le chantier le dit lui-même
- statut : À FAIRE
- validation : —
- autonomie : complète
- priorité : 8

**Le constat, mesuré le 28/09/2026 (cycle 4).** La table contient
**73 141 lignes** (47 tickers, 1 834 jours, du 02/01/2018 au 24/07/2026). Elle
est écrite par `collecte/charger_liquidite_quotidienne.py`, alimentée par
`collecte/backfill_liquidite.py`, et **aucun `SELECT` du dépôt ne la lit** :
vérifié par balayage de tous les `.py`, seul le chargeur la nomme. C'est le seul
cas de ce genre dans la base — les onze autres tables ont un lecteur.

**Ce qui rend le cas intéressant plutôt que cosmétique.** `app.py` écrit
lui-même, dans sa section de limites : « VALUE et RENDEMENT, et surtout la
liquidité, n'ont jamais été éprouvées ». La donnée nécessaire à cette
éprouvation est donc **déjà en base depuis 2018**, et personne ne s'en sert. Le
choix est binaire et demande un arbitrage : brancher la liquidité comme critère
(filtre d'éligibilité, ou axe de la fiche), ou retirer la table et son chargeur.

**Terminé quand** : soit la table a un lecteur et l'effet sur les 47 titres est
mesuré, soit elle et son chargeur sont retirés et la section 17 est mise à jour.

## C15 — Les 101 séances du mensuel manquent au quotidien

- classe : VERTE — fait ; versement sans réseau, aucune valeur préexistante touchée
- statut : FAIT le 30/09/2026 (cycle 8) — voir le journal
- validation : OK
- autonomie : complète, **sans réseau** — les données sont déjà dans le dépôt
- priorité : 2

**Le constat, mesuré le 30/09/2026 (cycle 6).** Les deux séries de prix de la
base, `cours_mensuels` (depuis `collecte/cours_extraits.csv`) et
`cours_quotidien_boc` (depuis `collecte/cours_quotidien_boc.csv`), ne partagent
**aucune date** : **0 sur 101**. Les 101 séances du mensuel sont exactement 101 des
**355** jours ouvrés absents du quotidien (2 281 jours ouvrés du 02/01/2018 au
29/09/2026, 1 926 présents). Il n'existe donc pas une seule paire (ticker, jour)
commune, et leurs valeurs n'ont jamais pu être confrontées.

**Cause, écrite dans le code.** `collecte/backfill_boc_quotidien.py` porte depuis le
25/07/2026 une « LIMITE CONNUE, non corrigée » : un BOC déjà archivé par le
collecteur mensuel n'est jamais réextrait vers `cours_quotidien_boc.csv`.

**Ce que la comparaison naïve cachait.** Comparer le dernier cours quotidien du mois
au cours mensuel donne 1 561 égalités au franc sur 4 463 paires — mais ce sont deux
jours *différents* (1 à 3 jours d'écart), donc du bruit, pas un accord. Ne pas
s'appuyer dessus.

**Ce qu'il faut faire.** Verser les lignes de `cours_extraits.csv` dans
`cours_quotidien_boc.csv` pour ces 101 dates, par un script idempotent dans
`outils/`, sans réseau. Le test de la section 19 de `tester_donnees.py` dit
aussitôt si le versement est fidèle : il exige l'égalité au franc sur toute date
commune et fait baisser son plafond.

**Effet mesuré avant de proposer**, en versant les 4 508 lignes dans une base
jetable puis en relançant `profils.py` : **9 titres sur 47** voient un champ bouger
(`comparaisons` 6, `g` 3, `peg` 2, `motif` 1), **aucun champ décisionnel** (`profil`,
`secondaire`, `grade`, `gate`, `drapeaux`) : 0 titre sur 47.

**Hors de portée, dit franchement.** Restent **254** jours ouvrés absents du
quotidien hors mensuel : 247 confirmés absents chez brvm.org par le backfill, 5 jamais
tentés. **2021 en porte 107**, contre 15 à 24 les autres années — un trou côté
source, que ce chantier ne comble pas.

**Terminé quand** : les 101 dates sont dans le quotidien avec leur source, le
plafond de la section 19 tombe à 0, et la confrontation compte plus de 4 000 paires
sans aucune divergence.

**Fait le 30/09/2026 (cycle 8)**, par `outils/versement_mensuel_vers_quotidien.py`,
idempotent et sans réseau : 4 509 lignes ajoutées, 0 ligne préexistante modifiée,
plafond de la section 19 à **0**, et la confrontation rend **4 508 paires, 0
divergence au franc**. La prévision d'effet du cycle 6 est vérifiée au champ près :
9 titres bougent (`comparaisons` 6, `g` 3, `peg` 2, `motif` 1), **0 champ
décisionnel**. Deux conséquences non prévues, toutes deux inscrites ailleurs : une
**treizième** date est apparue dans l'alerte de C4 (SAFC 2019-01-02), et la
confrontation des deux extractions a rendu mesurables les **collisions d'échelle**
de C18.

## C16 — Retirer aussi l'axe de décote des titres à dividende périmé

- classe : ORANGE — arbitrage de méthode — **la passe de mesure des trois options est pré-autorisée**
- statut : **MESURÉ le 30/09/2026 (cycle 9)** — la passe pré-autorisée est CONSOMMÉE, le
  tableau est plus bas. **Aucun cycle ne la refait** : l'application attend que Claudia
  écrive son choix sur la ligne `validation` (voir *Ce qu'il reste à trancher*).
- validation : OK
- autonomie : complète, mais **c'est un arbitrage de méthode**
- priorité : 3

**Ce que C1 n'a volontairement pas fait.** Le texte de C1 demandait de retirer les
titres à dividende de référence périmé « de l'axe rendement ». Le cycle 7 a retiré
leur **prime** et leur **rendement des classements**, mais a laissé le rendement
facial dans l'**axe de décote** (`decote_pctl`), parce que le retirer déplace des
verdicts.

**Pourquoi ce n'est pas une évidence.** ORGT n'a pas versé depuis 2019 : son
rendement récurrent est **zéro**, pas **inconnu**. Le retirer de l'axe (case vide)
fait monter sa décote de 54 à 93 en ne gardant que le rendement bénéfice/prix, ce
qui récompense un titre qui ne distribue rien. Laisser le rendement facial faux
(1,98 %) est une erreur ; le compter pour 0 est une autre lecture, défendable, qui
ne fait pas basculer ORGT de la même façon. **La règle « une case vide vaut mieux
qu'une valeur approchée » ne tranche pas ici** : zéro n'est pas une approximation
pour un titre qui ne verse rien.

**À trancher par Claudia** : (a) laisser tel quel (le rendement facial reste dans
la décote, prime et classements corrigés) ; (b) retirer l'axe (case vide) ; (c)
compter zéro pour les dividendes périmés. Le cycle mesurera l'option choisie.

**TRANCHÉ le 30/09/2026 par Claudia : « mesurer d'abord, décider après ».** Le
cycle qui prendra C16 **n'applique rien**. Il mesure les **trois** options (a), (b)
et (c) sur les **6** titres aujourd'hui drapeautés — et non les 10 de la mesure
d'origine, périmée depuis la correction de la règle 1 — et rend, titre par titre :
le `decote_pctl` avant/après, les `profil` qui basculent, les `grade` qui bougent.
Les trois mesures et rien d'autre : le choix revient ensuite à Claudia.

**Terminé quand** : les trois options sont mesurées sur les 6 titres, titre par
titre, et le tableau est inscrit ici. L'application, elle, attend un second
arbitrage de Claudia — et c'est alors seulement qu'un test de la section 21 figera
la règle retenue.

### La mesure, faite le 30/09/2026 (cycle 9)

Trois variantes jetables de `moteur/profils.py`, générées par substitution
textuelle avec assertion d'unicité sur chaque ancre, exécutées sur la base du jour,
écrivant chacune son `profils.json` hors du dépôt. **Garde vérifiée** : la variante
(a) reproduit le `profils.json` commité **au champ près, 0 titre d'écart** — sans
quoi la mesure n'aurait rien valu. Aucun fichier du dépôt modifié.

Seule la lecture de l'**axe de décote** change d'une option à l'autre (les deux
percentiles `dy` : celui du titre et le bassin de comparaison). La prime, les
classements et le test du profil RENDEMENT restent tels que C1 les a laissés.

**Les 6 titres drapeautés.** Cinq sont drapeautés PÉRIMÉ, un seul EXCEPTIONNEL
(FTSC). Quatre des six ne sont pas analysables — leur profil vient d'un fait
qualitatif, ils n'ont pas de `decote_pctl` du tout, et **aucune option ne les
touche** : seuls ORGT et SEMC sont sur les axes.

| titre | motif | `dy` facial | décote (a) | décote (b) | décote (c) | profil/grade, les trois options |
|---|---|---|---|---|---|---|
| ORGT | PÉRIMÉ (2019-07-01) | 1,98 % | 54 | **93** | **50** | `AUCUN_PROFIL`/B → **`VALUE`**/B en (b) ; `AUCUN_PROFIL`/B en (c) |
| SEMC | PÉRIMÉ (2021-12-28) | 0,94 % | 3 | 3 | **4** | `VIGILANCE_CONTRACTION`/C, inchangé partout |
| BNBC | PÉRIMÉ (2023-07-24) | 7,54 % | — | — | — | `RETOURNEMENT`/B, inchangé (hors axes) |
| SCRC | PÉRIMÉ (2021-08-20) | 1,37 % | — | — | — | `RETOURNEMENT`/B, inchangé (hors axes) |
| SIVC | PÉRIMÉ (2017-09-29) | 26,81 % | — | — | — | `MUTATION`/B, inchangé (hors axes) |
| FTSC | EXCEPTIONNEL (×7,3) | 86,54 % | — | — | — | `MUTATION`/B, inchangé (hors axes) |

**Effet sur les 47 titres.**

| | (b) case vide | (c) zéro si périmé |
|---|---|---|
| `decote_pctl` bouge | **28 / 47** | **3 / 47** |
| amplitude hors ORGT | −1 à −3 points | +1 à +3 points |
| `profil` ou `secondaire` bascule | **2** : ORGT `AUCUN_PROFIL` → `VALUE` ; SMBC perd son secondaire `VALUE` (décote 68 → 66, seuil `value_pctl_min` = 67) | **0** |
| `grade` bouge | **0** | **0** |
| `gate` bouge | **0** | **0** |

**Ce que la mesure apprend, et qui n'était pas prévu.**

1. **L'option (b) déplace tout le monde d'un cran vers le cher.** Retirer ORGT
   (1,98 %) et SEMC (0,94 %) du bassin ôte deux valeurs **basses** : les 26 autres
   titres perdent 1 à 3 points de décote sans qu'aucune de leurs données n'ait
   changé. C'est l'effet de bassin, pas un effet de titre — et il produit le second
   basculement, SMBC, qui n'a rien à voir avec un dividende périmé.
2. **L'option (c) est presque neutre** : 3 titres, aucun verdict. ORGT descend de
   54 à 50 au lieu de monter à 93 ; ETIT gagne 3 points (même secteur qu'ORGT).
3. **L'option (b) récompense bien ORGT de ne rien distribuer** — 54 → 93, et un
   profil `VALUE` gagné — exactement ce que le texte de ce chantier redoutait.
   La mesure le confirme sur les chiffres du jour.
4. **Zéro n'est pas défendable pour FTSC**, seul titre EXCEPTIONNEL : la société a
   bel et bien distribué. L'option (c) a donc été mesurée comme « zéro pour les 5
   périmés, case vide pour l'exceptionnel ». FTSC étant hors axes, la distinction
   ne change aucun chiffre aujourd'hui — mais elle changera dès qu'un titre
   EXCEPTIONNEL sera analysable, et la règle doit le dire.

### Ce qu'il reste à trancher

Un mot de Claudia sur la ligne `validation`, par exemple `- validation : OK —
option (c)`. Le cycle suivant appliquera l'option nommée et figera la règle par un
test de la section 21. **Sans ce mot, aucun cycle ne reprend C16** : la passe
pré-autorisée est consommée.

## C17 — Pour 13 titres sur 44, le dividende que le BOC divise reste introuvable

- classe : ORANGE — l'inventaire est pré-autorisé ; écrire un dividende en base ne l'est pas
- statut : PROPOSÉ
- validation : EN ATTENTE
- autonomie : partielle — première passe **sans réseau** sur le corpus déjà collecté
- priorité : 3

**Le constat, mesuré le 30/09/2026 (cycle 7 bis), sur la règle de C1 corrigée.**
Le rendement du BOC est un rapport : dernier dividende par action sur cours. En
reconstruisant le dividende implicite (`rendement × cours`) et en le confrontant au
versement **le plus récent** de notre table `dividendes`, **31 titres sur 44
concordent** à 10 % près — la plupart à moins de 1 %, ce qui prouve que la méthode
identifie bien la référence. Les **13 autres** ne concordent pas :

| titre | implicite du BOC | dernier versement en base | écart |
|---|---|---|---|
| NTLC | 369,60 | 2025-08-18 · 721,60 | +95 % |
| CFAC | 55,52 | 2025-08-19 · 7,04 | −87 % |
| LNBB | 164,19 | 2025-07-31 · 275,50 | +68 % |
| STBC | 1 707,46 | 2024-07-29 · 675,00 | −60 % |
| SMBC | 704,55 | 2024-09-30 · 1 080,00 | +53 % |
| SLBC | 1 871,10 | 2025-07-29 · 1 073,60 | −43 % |
| NEIC | 140,30 | 2024-06-25 · 81,78 | −42 % |
| TTLC | 139,70 | 2025-09-03 · 195,67 | +40 % |
| SGBC | 2 298,99 | 2025-08-05 · 1 645,78 | −28 % |
| SPHC | 430,55 | 2025-07-17 · 323,84 | −25 % |
| SDCC | 462,44 | 2025-09-30 · 352,00 | −24 % |
| SHEC | 85,08 | 2025-10-22 · 75,29 | −12 % |
| SIBC | 374,24 | 2025-07-31 · 330,00 | −12 % |

**Pourquoi c'est un chantier et pas une curiosité.** Le BOC divise par un dividende
que nous n'avons pas. C'est une **lacune de collecte**, mesurée et nommée titre par
titre, et elle a trois conséquences immédiates :

1. **la règle de C1 est inapplicable sur ces 13 titres.** Ni périmé ni exceptionnel
   ne peut être établi pour eux — c'est précisément ce qui a produit les quatre faux
   drapeaux corrigés ce cycle (NTLC, SDCC, SIBC, SMBC) : faute de référence, la
   règle d'origine en inventait une par coïncidence de montant ;
2. **c'est la mesure qui manquait à C2.** Le rapport implicite/déclaré est ce qui
   trancherait la convention brut/net ; et 31 concordances à 10 % disent déjà que
   pour celles-là l'écart entre les deux conventions ne peut pas être grand ;
3. **CFAC à −87 % n'est pas un écart de convention, c'est un ordre de grandeur.**
   Sa ligne 2025 porte 7,04 FCFA quand le BOC en divise 55,5. À regarder en premier,
   avec STBC (−60 %) et NTLC (+95 %).

**Première passe sans réseau** : `collecte/dividendes_boc.csv` et le corpus de
bulletins déjà archivés n'ont pas été fouillés pour ces 13 titres. Ce qui manque
après cela seulement justifie un `collecte.yml`.

**Attention, une piste et une seule** : **NTLC est à +95 %**, soit presque
exactement un facteur deux — la signature d'une division de nominal non ajustée.
Et **SLBC** (−43 %) est le seul titre de cette liste dont **C4** signale une chute
de cours non documentée **récente**, le 27/09/2024, donc antérieure à son versement
de 2025. Les onze autres chutes listées par C4 datent de 2018-2019 et ne peuvent
pas expliquer un écart sur un dividende de 2024 ou 2025. À vérifier sur ces deux
titres avant de conclure à un dividende manquant : ce serait le même défaut vu
d'ailleurs.

**Terminé quand** : chaque titre a soit son dividende de référence en base avec sa
source, soit un motif daté d'impossibilité ; l'effet sur la règle de C1 est mesuré
titre par titre ; et le compte de titres à référence identifiée, aujourd'hui 31 sur
44, est figé par un test qui ne peut que monter.

## C18 — Cinq collisions d'échelle dans la série de cours

- classe : ORANGE — corriger une série de cours commitée exige la preuve à deux côtés ; la mesure est faite
- statut : PROPOSÉ
- validation : EN ATTENTE
- autonomie : complète, **sans réseau** — tout est dans `collecte/cours_quotidien_boc.csv`
- priorité : 4 — **avant C4**, dont il retire trois dates

**Le constat, mesuré le 30/09/2026 (cycle 8), rendu visible par C15.** En versant
les séances mensuelles dans la série quotidienne, la séance du **31/12/2018 de
SAFC** est venue se placer entre des séances quotidiennes qui l'encadrent — et
elle porte **5 300** quand elles portent **215**. En cherchant systématiquement
les chutes de plus de 60 % qui **reviennent** au niveau d'avant dans les quinze
séances, il y en a **cinq**, sur trois titres :

| titre | séance | cours avant → pendant → après | facteur |
|---|---|---|---|
| SLBC | 12/01/2022 | 154 000 → **154** → 154 000 le lendemain | **1 000** |
| SLBC | 02/06/2023 | 73 075 → **67,6** → 73 075 le 19/06 | **1 081** |
| SAFC | 21/12/2018 | 5 300 → **215** → 5 300 le 31/12 | 24,65 |
| SAFC | 02/01/2019 | 5 300 → **215** → 5 300 le 04/01 | 24,65 |
| STBC | 12/07/2018 | 44 995 → **11 315** → 44 995 le lendemain | 3,98 |

**Une division de nominal ne revient jamais sur ses pas.** Ce ne sont donc pas des
opérations sur titre mais des valeurs d'une **autre échelle** déposées dans la
série. Les deux SLBC sont des facteurs 1 000 : une erreur d'unité, pas un prix.

**Ce que les contrôles existants en font, et c'est le vrai sujet.** Le contrôle
des divisions de nominal (section 7) trie sur `var < -0,60` **et** `var > -0,995` :

1. les **deux SLBC** tombent sous −99,5 % et sont donc **écartés explicitement**
   comme « erreurs de saisie manifestes » — écartés, et **enregistrés nulle part**.
   Ils restent dans le CSV commité et dans la base ;
2. les **trois autres** sont comptés **à tort** comme divisions de nominal non
   documentées, et gonflent la file de C4 de trois dates pour lesquelles aucun
   avis de fractionnement ne sera jamais trouvé.

**Portée, mesurée et dite franchement : le défaut est LATENT.** Aucune des cinq
séances n'est un point de BPA annuel lu par `croissance_bpa_implicite`, et aucune
n'est la dernière séance : **aucun profil, grade ni gate d'aujourd'hui n'en
dépend**. Ce qui en dépendra, c'est tout backtest lisant la série entière — et
`backtest_rendement_total.py`, `backtest_leger.py` et
`backtest_bootstrap_blocs.py` sont dans le dépôt.

**Ce qu'il faut faire.** Trancher, pour chacune des cinq, entre corriger la valeur
dans `collecte/cours_quotidien_boc.csv` par un script de migration idempotent dans
`outils/` — avec la preuve à deux côtés que le projet exige, ici le cours des
séances qui l'encadrent — et la laisser en l'état avec son motif. Puis faire en
sorte que la section 7 cesse de compter les collisions comme des divisions.

**Terminé quand** : les cinq séances sont corrigées ou motivées une par une, le
registre `COLLISIONS_ECHELLE` de la section 22 reflète ce qui reste, l'alerte de
C4 retombe de 13 à 10 dates, et le seuil `var > -0,995` de la section 7 n'écarte
plus rien en silence.

## C19 — `dividendes_par_exercice.csv` porte des doublons, et son générateur ne le rend plus

- classe : ORANGE — décider quelle ligne est la bonne est un arbitrage ; la mesure est faite
- statut : PROPOSÉ
- validation : EN ATTENTE
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 6

**Le constat, mesuré le 30/09/2026 (cycle 10), trouvé par les gardes de C10.**
Le script de migration de C10 a refusé de tourner au premier essai : son assertion
d'unicité a buté sur les lignes 4 et 6 du fichier (`ABJC, 2017, 98,97,
20-juin-18`). Deux mesures en sont sorties.

**1. Douze lignes strictement dupliquées, qui deviennent seize.** Sur les 364
lignes, **12** sont identiques sur les six colonnes, note comprise : 352 clés pour
364 lignes. Après la normalisation ISO elles sont **16**, parce que **quatre
événements étaient dédoublés sous deux orthographes du même jour** — ce que le
format français cachait :

| titre | exercice | montant | jour | les deux formes brutes |
|---|---|---|---|---|
| ABJC | 2017 | 98,97 | 2018-06-20 | `20-juin-18` et `20-juin.-18` |
| ORAC | 2023 | 780,00 | 2024-06-03 | `3-juin-24` et `03-juin-24` |
| ETIT | 2016 | 1,21 | 2017-04-28 | `28 Apr 17` et `28-avr.-17` |
| ETIT | 2021 | 0,90 | 2022-06-20 | `20 Jun 22` et `20-juin-22` |

Les deux ETIT sont les plus parlants : le même versement a été saisi une fois en
anglais et une fois en français. C'est une **corroboration** involontaire de la
valeur, pas une contradiction.

**2. Le fichier commité n'est plus ce que son générateur produit.**
`collecte/historiser_dividendes_exercice.py` lit `dividendes_historique.csv`
(365 lignes) et écrit `dividendes_par_exercice.csv` (364 lignes commitées). Relancé
sur l'état du dépôt **avant tout changement de ce cycle**, il rend **365 lignes**,
donc une de plus : **FTSC 2016, 1 045,00, payé le 31/07/2017**. C'est exactement le
cas que le générateur documente dans son propre commentaire (avis BRVM
N° 072-2017/DC/BR/DG). Le fichier dérivé a donc été retouché à la main sans que le
générateur le sache, et personne ne peut plus le régénérer sans changer les données.

**Portée, dite franchement : le défaut est LATENT.**
`charger_dividendes_exercice.py` déduplique par `(ticker, exercice_couvert)` : les
doublons ne produisent **aucun doublon en base**, vérifié — la table porte 311
lignes avant comme après. Aucun profil, grade ni gate n'en dépend. Ce qui en
dépend : tout comptage d'événements de dividende lu sur ce fichier (le générateur
annonce « 364 événements » là où il y en a 352), et la prochaine régénération, qui
ajouterait FTSC 2016 sans que ce soit une décision de quiconque.

**Ce qu'il faut faire, et ce qui demande un arbitrage.** Retirer 16 lignes
strictement identiques est mécanique. Mais trancher le cas FTSC 2016 ne l'est pas :
soit le versement est légitime et le fichier commité a **tort** de ne pas le porter
(et il faut l'y remettre), soit il a été retiré à la main pour une raison qui n'est
écrite nulle part (et c'est le générateur qu'il faut corriger). Les deux se
défendent, et la doctrine du projet interdit de deviner laquelle.

**Terminé quand** : les 16 doublons sont retirés par un script idempotent dans
`outils/`, le cas FTSC 2016 est tranché avec son motif écrit, une régénération par
`historiser_dividendes_exercice.py` rend **exactement** le fichier commité, et un
test de la section 23 fige l'égalité entre le fichier et sa régénération.

---

# Veille datée, hors file

- **08/10/2026 — AGE Sonatel, fractionnement.** Si elle passe, la division de
  nominal doit être enregistrée dans `operations_sur_titre.csv` le jour même.
  (C4 en compte déjà treize ; ce serait le quatorzième.)

---

# Dernier cycle

Vingt-cinq lignes au plus. L'entrée complète va dans `docs/JOURNAL.md`.

## 2026-09-30 — cycle 10 (hors cadence, demandé par Claudia)

**Exécuté : C10, jusqu'au bout** — `collecte/dates_dividendes.py` (autotest 27 cas),
`outils/migration_dates_dividendes_iso.py` (**362 lignes converties sur 364**, six
gardes, relancé sans effet), les trois chargeurs normalisent à l'entrée, et la
**section 23** de `tester_donnees.py` (16 contrôles).

**Effet, avant → après** : dates non ISO en base **296 → 0** ; `ORDER BY
date_paiement DESC` rend le mauvais versement sur **34/49 → 0/49** ; `int(date[:4])`
échoue — donc le bloc « régularité du dividende » de `scoring.py` est sauté en
silence — sur **45/49 → 0/49** ; déduplication du BOC **0/40 → 40/40**.
**`profils.json` identique** : aucun verdict ne bouge.

**Inscrit en C19** (ORANGE, `EN ATTENTE`), trouvé par les gardes : 12 lignes
dupliquées dans `dividendes_par_exercice.csv`, **16** après normalisation (quatre
événements dédoublés sous deux orthographes du même jour, dont deux en anglais), et
une régénération par `historiser_dividendes_exercice.py` ne rend plus le fichier
commité — un événement de plus, FTSC 2016. Latent en base.

**CI tombée puis réparée dans le même cycle, et c'est ma faute.** La section 23
importait `collecte_boc_quotidien`, dont les imports tirent `pdfplumber`, **absent
de `requirements.txt`** et préinstallé par hasard dans le bac à sable : P4 est tombé
sur `ModuleNotFoundError` quand la barrière était verte en local. Fonction extraite
par AST, et un contrôle interdit cet import. **Leçon : une barrière verte dans le
bac à sable ne prouve rien si le test importe hors `requirements.txt`.**

**Barrières rejouées `pdfplumber` indisponible** : golden OK, `tester_donnees.py`
**175 OK, 0 échec**, code 2 sur C4 et C5. **Prochain : C3** (VERTE, priorité 3).

---

# Pourquoi ce protocole a changé

Décidé par Claudia le 30/09/2026, sur trois mesures et non sur une impression.

**1. Cinq cycles sur huit n'avaient rien exécuté**, faute d'une ligne
`validation : OK` — en payant chaque fois le prix plein : clone, installation,
reconstruction de la base, barrières, chasse. D'où les **classes** : la boucle a
toujours quelque chose à faire, et Claudia garde le veto sur toute écriture qui
engage une méthode ou une donnée certifiée.

**2. Ce fichier pesait 23 000 tokens, dont 13 000 de journal**, relus quatre fois
par jour, et il grossissait d'environ 1 500 tokens par cycle. Le journal est
sorti dans `docs/JOURNAL.md` ; il ne se lit plus au démarrage.

**3. Deux fois — le 28/09 et le 30/09 — des sessions parallèles ont refait le
même travail.** La collision n'était détectée qu'au `git fetch` final, donc après
coup : une heure de travail perdue à chaque fois. D'où le contrôle
anti-collision en étape 2, qui coûte un `git log` et arrête la session avant
qu'elle ne reconstruise quoi que ce soit.

**Et la cadence est passée de quatre à deux passages par jour**, 06h53 et 18h53
UTC. Douze heures d'écart : deux cycles ne peuvent plus se croiser. La chasse aux
défauts, elle, n'a lieu qu'au cycle du matin.

