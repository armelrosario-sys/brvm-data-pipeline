# Chantiers — file de travail de la boucle automatique

Ce fichier est la **mémoire de la boucle**. Toutes les six heures, une session
neuve démarre, sans aucun souvenir de la précédente : elle clone le dépôt, lit
ce fichier, et c'est tout ce qu'elle sait. Ce qui n'est pas écrit ici n'existe
pas pour elle.

Mis en place le 28/09/2026. Régime d'autonomie retenu : **documenté**.

---

## Comment Claudia valide un chantier

Chaque cycle **propose** un chantier et **n'y touche pas** tant qu'il n'est pas
validé. Pour valider, une seule chose à changer, directement sur GitHub (le
crayon en haut à droite de ce fichier, faisable depuis un téléphone) :

```
- validation : EN ATTENTE     →     - validation : OK
```

Pour refuser ou réorienter :

```
- validation : NON — le motif en clair
```

Le cycle suivant lit cette ligne et agit en conséquence. Aucune réponse dans
la conversation n'est nécessaire : la boucle ne lit que ce fichier.

## Ce que fait chaque cycle, dans l'ordre

1. Cloner le dépôt, lire ce fichier, lire le journal en bas.
2. Vérifier l'état : CI verte ? nouveaux commits ? le dernier cycle a-t-il
   laissé quelque chose en suspens ?
3. **Exécuter** le chantier dont `validation : OK`, s'il y en a un — un seul.
4. **Chasser une famille de défauts que rien ne surveille**, et transformer ce
   qui est trouvé en test. Étape permanente : aucun des défauts trouvés le
   27/09/2026 n'avait été attrapé par les tests existants.
5. **Proposer** le chantier suivant, diagnostic fait, effet mesuré, en le
   passant à `statut : PROPOSÉ` et `validation : EN ATTENTE`.
6. Réécrire ce fichier, ajouter une entrée au journal, committer, pousser.

## Règles que la boucle ne franchit pas

Chacune vient d'une erreur réelle du 27/09/2026.

- **Ne jamais écraser une valeur adossée à `config/faits_qualitatifs.yaml` ou à
  une note qui documente une analyse humaine.** Signaler, et s'arrêter. Le
  résultat 2025 d'Uniwax avait été validé à la main sur les résolutions d'AGO ;
  une mise en quarantaine automatique l'a effacé, et c'est un golden test qui a
  arrêté l'erreur.
- **Une case vide vaut mieux qu'une valeur approchée.** Jamais d'estimation
  pour combler un trou.
- **Preuve à deux côtés obligatoire** avant de corriger une donnée certifiée :
  une identité comptable qui se ferme, ou deux sources indépendantes. C'est ce
  qu'autorise le régime « documenté » — corriger avec preuve, tout écrire dans
  la note et le message de commit, et laisser la révocation possible d'un
  `git revert`.
- **Un chantier par cycle, un commit par chantier.**
- **Jamais de commit si une barrière tombe** : golden tests, `tester_donnees.py`,
  garde-fous des collecteurs, génération du dashboard, démarrage de `app.py`.
  En cas d'échec : tout annuler, et committer le seul constat d'échec.
- **Mesurer avant d'affirmer.** Ne citer que des nombres calculés dans le cycle.

## Moyens disponibles

- **Poussée directe sur `main`** : opérationnelle depuis le 27/09/2026.
- **Déclenchement des workflows par l'API** : vérifié le 28/09/2026 (`204` sur
  `tests.yml`). C'est la seule voie vers brvm.org — le bac à sable ne l'atteint
  pas, la liste blanche ne couvre que les dépôts de paquets et GitHub. Les
  workflows utiles : `collecte.yml` (P2b, collecte sélective brvm.org),
  `inventaire.yml` (P2a), `extraction_etats.yml` (P10), `reparation.yml` (P2c),
  `notations.yml` (P12).
- **Ce qui reste hors de portée** : un PDF scanné que l'OCR ne rend pas. Le
  bilan Uniwax 2024 n'est passé que par des captures d'écran envoyées à la
  main. Quand l'OCR ne rend rien, le dire, pas deviner.

---

# La file

## C1 — Distributions non récurrentes faussent l'axe rendement

- statut : PROPOSÉ
- validation : EN ATTENTE
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

- statut : À FAIRE
- validation : —
- autonomie : partielle
- priorité : 4

`collecte/operations_sur_titre.csv` contient **une seule ligne**, et le test de
continuité signale **12 chutes de cours supérieures à 60 %** non documentées :
ECOC 26/12/2018, FTSC 30/01/2018, PRSC 24/10/2019, SAFC 21/12/2018 et
07/01/2019, SEMC 19/12/2018, SIBC 15/06/2018, SLBC 27/09/2024, SMBC 22/02/2019,
STBC 12/07/2018 et 27/07/2018, TTLC 12/02/2018.

Première passe **sans réseau** : `collecte/avis_brvm.py` sait déjà reconnaître
un fractionnement, donc fouiller d'abord le corpus d'avis déjà collecté. Ce qui
manque après cela seulement justifie un `collecte.yml`.

**Terminé quand** : chaque date est soit documentée avec sa source, soit
explicitement écartée avec son motif ; l'alerte de fraîcheur s'éteint.

## C5 — Exercices manquants : CFAC 2025 et NEIC 2025

- statut : À FAIRE
- validation : —
- autonomie : complète (dispatch vérifié)
- priorité : 5

Nommés par l'alerte de fraîcheur de `tester_donnees.py`. CFAO Mobility Côte
d'Ivoire et Nei-Ceda. Passer par `collecte.yml` puis `extraction_etats.yml`.

**Terminé quand** : les deux exercices sont en base avec leur source, ou
l'absence du document est constatée et datée.

## C6 — Trou BICC 2022

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

- statut : À FAIRE
- validation : —
- autonomie : complète (dispatch vérifié)
- priorité : 7

46 titres sur 47 ont un ROE depuis le 27/09/2026. TotalEnergies Marketing
Sénégal est le dernier. Ses capitaux propres manquent.

**Terminé quand** : 47/47, ou l'impossibilité est documentée.

## C8 — Extracteur GCR

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

**Terminé quand** : l'extracteur passe les 10 PDF GCR d'échantillon, ou le
motif d'abandon est chiffré sur des données fraîches.

## C9 — Extinction de P5b et retrait du code mort

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

- statut : À FAIRE
- validation : —
- autonomie : complète, aucune donnée extérieure nécessaire
- priorité : 3 — **avant C3**, dont le journal datera ses lignes

Trouvé le 28/09/2026 en cherchant à dater les dividendes. La colonne mélange
**deux formats incompatibles**, comptés sur les 326 lignes de la base :

- **296 lignes** (91 %) au format français abrégé, année sur deux chiffres :
  `24-juil.-17`, `30-sept.-24`, `24-août-22`. Toutes issues de
  `collecte/dividendes_par_exercice.csv (Piste D, confiance ELEVEE)` —
  `charger_dividendes_exercice.py` insère la chaîne brute sans la normaliser.
- **24 lignes** en ISO `aaaa-mm-jj`, venues de `donnees/base/dividendes.csv`.
- **6 lignes** nulles (SDSC).

Trois conséquences, dont une déjà armée :

1. **Tri et comparaison faux.** `scoring.py::dividendes()` fait
   `ORDER BY date_paiement DESC` : sur du français abrégé l'ordre est
   alphabétique, pas chronologique.
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
   n'existe encore (vérifié : 0 sur 326) — le défaut est latent, pas actif.

**Attention** : la conversion doit lever l'ambiguïté du siècle sur l'année à
deux chiffres, et refuser plutôt que deviner sur un mois non reconnu. Un mois
français abrégé mal orthographié doit échouer bruyamment.

**Terminé quand** : la colonne est ISO sur les 326 lignes via un script de
migration idempotent dans `outils/`, les chargeurs normalisent à l'entrée, la
déduplication de `collecte_boc_quotidien.py` retrouve bien les lignes
existantes, et un test refuse toute date non ISO dans la table.

---

# Veille datée, hors file

- **08/10/2026 — AGE Sonatel, fractionnement.** Si elle passe, la division de
  nominal doit être enregistrée dans `operations_sur_titre.csv` le jour même,
  sous peine d'ajouter un treizième cas à C4.

---

# Journal

Une entrée par cycle. La plus récente en haut.

## 2026-09-28 — cycle 1

**Aucun chantier exécuté.** C1 était le seul `PROPOSÉ` et sa validation est
restée `EN ATTENTE` : rien n'a été touché dans la file, conformément au
protocole. Le cycle a porté sur l'étape permanente, la chasse aux défauts.

**Défaut trouvé et corrigé : `peupler.py` n'était pas idempotent, et la barrière
corrompait la base qu'elle validait.**

Le chemin, mesuré de bout en bout :

1. `peupler.py` insérait `dividendes` et `avis_reglementaires` par un `INSERT`
   simple. Ce sont les **seules** tables de la base de référence sans clef
   unique — leur seule clef est un `id AUTOINCREMENT`. Les quatre autres
   (`societes`, `etats_financiers`, `resultats_intermediaires` en
   `INSERT OR REPLACE` sur clef unique ; `liste_suivi` en `DELETE` puis
   insertion) étaient idempotentes. L'idempotence du chargeur reposait donc
   entièrement sur la présence d'une clef unique, et deux tables n'en avaient
   pas.
2. Croissance mesurée, linéaire et non bornée : **+15 dividendes et +16 avis par
   passage** — 311/16 → 326/32 → 341/48 → 356/64 → 371/80.
3. `app.py::preparer_base()` relance `peupler.py` sur une base **existante** dès
   que l'empreinte des sources change, en annonçant une « reconstruction » qui
   n'en est pas une. Et `tester_donnees.py` démarre `app.py` en section 4 :
   la barrière dupliquait donc les données à chaque exécution. Vérifié en
   instrumentant la chaîne : `tester.py` et `profils.py` laissent la base à
   311/16, `tester_donnees.py` la rendait à 326/32.
4. **Ce n'était pas cosmétique.** `appliquer_gate()` **compte** les avis :
   `if len(retards) >= defauts_max` avec `defauts_max: 2`. SDSC porte **un**
   retard de publication (2025-04-30, confirmé par ses propres commissaires aux
   comptes). Dupliqué, il en porte deux, le seuil tombe, et le titre passe de
   `ELIGIBLE` à **`EXCLU`** — écarté de toute l'analyse sur la base d'un
   manquement enregistré une fois et compté deux fois. Diff mesuré sur
   `profils.json` entre base propre et base dupliquée : **1 titre sur 47
   change, SDSC, sur le seul champ `gate`**.
5. Le `collecte/profils.json` **commité portait ce verdict corrompu** : il avait
   été produit sur une base dupliquée. Régénéré sur base propre dans ce commit,
   SDSC repasse à `ELIGIBLE` (une ligne de diff).

**Correctif.** Déduplication à l'insertion, avec l'opérateur `IS` (NULL-safe :
trois dividendes SDSC ont une `date_paiement` nulle, et `NULL = NULL` est faux
en SQL, ce qui laisserait passer le doublon). Pas de `DELETE` : 
`charger_dividendes_exercice.py` (296 lignes) et `collecte_boc_quotidien.py`
écrivent aussi dans `dividendes`, et `app.py` ne les relance pas — vider la
table les effacerait sans les rebâtir. Clefs naturelles vérifiées uniques dans
les deux CSV sources (0 doublon sur 15 et sur 16 lignes) avant d'y toucher.

**Test.** Nouvelle **section 16** de `tester_donnees.py` : `peupler.main()` deux
fois sur une base jetable (`tempfile`, jamais `brvm.db`), comparaison des six
tables. Plus un garde-fou vérifiant que la base jetable est bien peuplée — une
base vide serait trivialement stable — et un contrôle de doublons d'avis dans
`brvm.db`, puisque c'est ce compte que lit le gate. **Vérifié dans les deux
sens** : le test échoue sur le code d'avant (`dividendes : 15 -> 30 ;
avis_reglementaires : 16 -> 32`) et passe sur le corrigé. Après correctif,
`tester_donnees.py` laisse la base à 311/16.

**Fausse piste, écartée.** `TEST_EXCLU` et `TEST_VIGIL` apparaissent dans
`societes` et `etats_financiers` en production. Ce ne sont pas des fuites : ce
sont des fixtures délibérées, marquées `[SYNTHETIQUE]`, utilisées par
`tester.py` et `scoring.py`, et exclues du profilage (47 titres profilés sur 50
sociétés). Signalé ici pour qu'un cycle suivant ne « corrige » pas ce qui est
volontaire — mais elles doivent être exclues de toute mesure statistique sur la
base, ce que fait le diagnostic ci-dessus.

**Barrières** : toutes passent. `tester.py` 0, `tester_donnees.py` 2 (les deux
mêmes alertes de fraîcheur qu'en référence, C4 et C5 — aucune nouvelle),
`avis_brvm.py --test` 0, `notations.py --test` 0, `generer_dashboard.py` 0
(48 titres), `app.py` démarre, 4 onglets.

**C1 reste `PROPOSÉ` / `EN ATTENTE`, non touché.** Sa prémisse a été revérifiée
sur données fraîches et tient : prime de rendement FTSC **+79,3 points**
(rendement 86,33 %), SIVC **+19,7 points** (26,81 %), et le troisième du
classement, STBC, à **+0,9 point** seulement. L'écrasement du classement est
donc réel et intact.

**C10 ouvert** (nouveau, `À FAIRE`) : `dividendes.date_paiement` mélange deux
formats — 296 lignes en français abrégé à année sur deux chiffres, 24 en ISO,
6 nulles. Le tri `ORDER BY date_paiement` de `scoring.py` est donc faux, et la
déduplication de `collecte_boc_quotidien.py` est cassée en attente de se
déclencher. **C2 enrichi** d'un second axe mesuré, l'exercice de rattachement du
`payout_ratio` — avec sa réserve : signal, pas preuve.

## 2026-09-28 — cycle 0 (mise en place)

- Fichier créé, neuf chantiers inscrits, règles et protocole de validation posés.
- Droit `actions: write` du jeton **vérifié** par un dispatch réel de
  `tests.yml` : `204`, run démarré en `workflow_dispatch`. C1 à C9 sont donc
  tous exécutables sans intervention, sauf blocage OCR.
- Correction d'une erreur de la veille : la prime de rendement de FTSC avait
  été attribuée à un dividende non ajusté d'une division de nominal. C'est
  faux — c'est une distribution exceptionnelle réelle, vérifiée par le
  recoupement entre le dividende par action, le nombre d'actions et la chute
  des capitaux propres. C1 est reformulé en conséquence.
- **C1 proposé**, en attente de validation.
