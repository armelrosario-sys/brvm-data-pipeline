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
- **Refaire `git fetch origin main` juste avant de committer, et relire ce qui
  est arrivé.** Si un cycle concurrent a poussé entre-temps : reprendre son
  travail par rebase, repasser les barrières **après** la fusion, et surtout
  **abandonner ce qui est devenu redondant** plutôt que de le fusionner. Deux
  contrôles sur la même identité, avec deux registres d'exceptions listant les
  mêmes cas, se désynchronisent et ne surveillent plus rien. Cette règle vient
  d'un gâchis réel du 28/09/2026 : trois sessions ont tourné en parallèle, deux
  ont attribué le libellé `C10` au même moment, et deux ont écrit **le même
  contrôle du comparatif N-1** dans la même heure.
- **Annoncer la famille de défauts chassée dès le début du cycle**, en tête du
  journal, et pousser cette annonce seule avant de travailler. C'est le seul
  moyen qu'a une session concurrente de ne pas refaire le même travail : la
  chasse aux défauts est l'étape la plus coûteuse du cycle et la plus facile à
  dupliquer, parce que deux sessions qui lisent le même fichier arrivent aux
  mêmes soupçons.
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

**À traiter d'une seule main avec C11** : le cycle qui ouvrira les documents TTLS
pour y lire les capitaux propres y lira aussi le référentiel comptable des
exercices 2024 et 2025 — c'est exactement ce que C11 réclame, et la divergence de
comparatif TTLS 2025 se tranche alors sans second accès à brvm.org.

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

**Mesuré le 28/09/2026 (cycle 2)** : l'autotest de `collecte/notations.py` rend
déjà « PDF GCR 10/10 ». Le critère de terminaison ci-dessous est donc **déjà
satisfait tel qu'il est écrit**, ce qui veut dire qu'il ne décrit pas le vrai
travail. Le fonds compte 4 `ECHEC` pour 291 `OK` et 87 `SANS_NOTE` : c'est sur
ces 4 qu'il faut regarder, pas sur l'analyseur d'échantillon. À rediagnostiquer
avant toute proposition.

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

## C11 — Le référentiel comptable n'est pas une colonne de la base

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

- statut : PROPOSÉ
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

## C16 — Retirer aussi l'axe de décote des titres à dividende périmé

- statut : PROPOSÉ
- validation : OK
- autonomie : complète, mais **c'est un arbitrage de méthode**
- priorité : 3

**Ce que C1 n'a volontairement pas fait.** Le texte de C1 demandait de retirer les
titres à dividende de référence périmé « de l'axe rendement ». Le cycle 7 a retiré
leur **prime** et leur **rendement des classements**, mais a laissé le rendement
facial dans l'**axe de décote** (`decote_pctl`), parce que le retirer déplace des
verdicts.

**Effet mesuré, sur une variante jetable de `profils.py` où les axes lisent le
rendement récurrent** (10 titres portent le drapeau) : **2 profils basculent**
(ORGT `AUCUN_PROFIL` → `VALUE`, SLBC `VALUE` → `AUCUN_PROFIL`), aucun grade ne
bouge, et `decote_pctl` change sur **30 titres sur 47** (le bassin de comparaison
se déplace).

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

**Terminé quand** : l'option est tranchée, appliquée, l'effet mesuré titre par
titre, et un test de la section 21 fige la règle.

**Note du cycle 7 bis** : l'effet ci-dessus a été mesuré sur **10** titres
drapeautés. Ils sont **6** depuis la correction de la règle 1 (voir le journal).
**La mesure est à refaire** avant de trancher.

## C17 — Pour 13 titres sur 44, le dividende que le BOC divise reste introuvable

- statut : PROPOSÉ
- validation : OK
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

---

# Veille datée, hors file

- **08/10/2026 — AGE Sonatel, fractionnement.** Si elle passe, la division de
  nominal doit être enregistrée dans `operations_sur_titre.csv` le jour même,
  sous peine d'ajouter un treizième cas à C4.

---

# Journal

Une entrée par cycle. La plus récente en haut.

## 2026-09-30 — cycle 8 (en cours)

**Trois lignes portent `validation : OK` : C15, C16 et C17.** La règle n'en
autorise qu'une. **C15 est retenu** : priorité 2, désigné chantier du cycle 8 par
les journaux des cycles 6 et 7, autonomie complète et sans réseau, et il ne
demande aucun jugement. C16 et C17 restent `OK` et non touchés.

**C16 précisé par Claudia, inscrit dans son bloc** : l'option retenue est
**« mesurer d'abord, décider après »**. Le cycle qui prendra C16 mesurera les
trois options sur les 6 titres drapeautés et n'appliquera rien.

**Famille annoncée avant tout travail** : **l'implicite du BOC dans le temps**.
Le bulletin publie trois nombres par titre et par séance — `cours`, `per`,
`rendement` — dont deux sont dérivés : le bénéfice par action implicite
(`cours / per`) et le dividende par action implicite (`cours × rendement`). Ces
deux-là ne peuvent bouger qu'à une publication de résultats ou à un détachement
de dividende : entre deux, ce sont des **paliers**. Sur les 86 057 lignes du
quotidien, **rien ne vérifie cette propriété** — les sections 1 à 3 regardent la
fraîcheur, la fréquence et la source retenue, la section 19 confronte les deux
séries de *cours*, et le moteur ne lit jamais que la **dernière** ligne de chaque
titre. Un `per` ou un `rendement` resté collé à sa valeur de la veille pendant que
le cours bouge, ou l'inverse, passerait donc inaperçu. C'est la même famille que
celle qui a produit les 13 titres de C17, prise par l'autre bout : C17 demande
quel dividende le BOC divise, cette chasse demande **quand il en a changé**.

## 2026-09-30 — cycle 7 bis (session parallèle — C1 abandonné, une erreur de C1 corrigée)

**Deux sessions ont exécuté C1 en même temps.** Celle-ci a démarré sur `c546a1d`
et a travaillé une heure sans contact avec l'autre. Au `git fetch` d'avant
poussée, `e769287` était là : C1 fait, testé, poussé. **Mon implémentation de C1
est abandonnée, pas fusionnée** — c'est la règle écrite après le gâchis du
28/09, et elle a raison : deux règles concurrentes sur le même drapeau, avec deux
registres d'exceptions, se désynchronisent et ne surveillent plus rien. Pareil
pour ma section de test sur la forme de `profils.json`, que la section 20 de
`e769287` couvre **mieux** : elle mesure le retard sur 21 commits là où je n'avais
mesuré qu'un point, et elle en tire la bonne conclusion — comparer les **valeurs**
commitées serait un faux positif quotidien, seule la **forme** doit être figée.

**Ce que la double mesure vaut quand même : une corroboration indépendante.** Sans
aucun contact, les deux sessions ont mesuré les mêmes nombres sur le constat de
C1 : prime **FTSC +79,47 points** (rendement 86,54 %), **SIVC +19,74**, troisième
**STBC +0,70**, et **1 726,56 FCFA** pour la distribution FTSC de l'exercice 2024.
Ces chiffres sont sûrs. Deux corrections de forme au passage : les autres titres
sont **42**, pas 45 — la base compte 44 titres portant un rendement, pas 47 ; et
le dividende de référence de SIVC couvre l'**exercice 2016**, payé le 29/09/2017,
donc **dix ans** et non neuf.

**Ce que ce commit apporte : une erreur de `e769287`, mesurée et corrigée.**
Sa règle 1 cherchait le versement le plus proche **en montant** parmi **toutes**
les dates de la table. Sur une série de versements voisins, le plus proche en
montant n'est pas forcément le plus récent — et la règle concluait alors
« dividende périmé » sur un titre dont **la même table porte un versement
postérieur** :

| titre | implicite du BOC | versement retenu | versement le plus récent de la table |
|---|---|---|---|
| NTLC | 369,60 | 2021-07-30 (363,67) | **2025-08-18 (721,60)** |
| SDCC | 462,44 | 2023-09-15 (450,00) | **2025-09-30 (352,00)** |
| SIBC | 374,24 | 2021-07-23 (360,00) | **2025-07-31 (330,00)** |
| SMBC | 704,55 | 2022-08-24 (720,00) | **2024-09-30 (1 080,00)** |

**Quatre des neuf drapeaux de péremption reposaient donc sur une coïncidence de
montant, pas sur une identification**, et la fiche affirmait de quatre sociétés
qu'elles ne distribuent plus alors que notre propre base montre le contraire.

**Correctif, une ligne** : le BOC divise par le **dernier** dividende payé ; la
coïncidence ne vaut donc que sur le versement **le plus récent** de la table.
Ailleurs, la référence nous échappe et on ne conclut pas — exactement le
traitement que `e769287` réservait déjà à NEIC et STBC, dont la table a un trou.
**Effet mesuré** : 10 drapeaux → **6** (BNBC, FTSC, ORGT, SCRC, SEMC, SIVC) ;
les primes de NTLC, SDCC, SIBC et SMBC reviennent, toutes **négatives**
(−4,67 à −2,80 points), donc très loin du plancher de plausibilité ;
**0 écart** sur `profil`, `secondaire`, `grade`, `gate`, `decote_pctl`, `peg`,
`pegy`, `g` pour les 47 titres. Il reste **38 primes**, entre **−5,74 et +0,70**
point.

**Tests, dans la section 21 de `e769287` plutôt qu'à côté** — un contrôle de plus
sur la même identité, pas une seconde section. Trois ajouts : une injection
`COINCIDENCE` (100 en 2021, 180 en 2025, implicite 100) qui ne doit **pas**
conclure ; un contrôle sur le fonds réel — aucun motif de péremption ne doit être
contredit par un versement postérieur de la même table ; et les quatre titres
nommés. Le contrôle « NTLC et SMBC restent grade A » a été **réécrit** : depuis la
correction ils ne portent plus le drapeau, donc il passait à vide ; il vérifie
maintenant la propriété du code, que le drapeau est exclu de ceux que le grade
lit. **Contre-essai** : la ligne corrigée remise en `min`, **six contrôles
échouent**, en nommant les quatre titres et leurs deux dates ; remise en `max`,
tous passent.

**Conséquence pour C16, signalée sans être traitée.** Son effet mesuré (2 profils
basculent, `decote_pctl` bouge sur 30 titres) a été obtenu sur les **10** titres
drapeautés. Ils sont **6** désormais : **la mesure est à refaire** avant tout
arbitrage. Mon propre essai de retrait de l'axe, fait sur un jeu de 8 titres
obtenu par une autre règle, donnait 0 profil déplacé et 9 `decote_pctl` — deux
mesures non comparables, aucune ne vaut pour l'autre.

**Chasse aux défauts — ce que cette session a mesuré sur la famille annoncée**
(reproductibilité de `collecte/profils.json`), et qui ne recoupe pas la section 20
de `e769287` :

- le `profils.json` commité **est** reproductible : régénéré sur base propre,
  **0 champ différent sur 47 titres**, et **0 champ différent** également à
  `4656d9f` reconstruit dans un arbre de travail séparé avec le code de ce
  commit. Le résultat est négatif et il faut le dire ;
- il l'est **par ordonnancement, pas par construction** : sur les 11 derniers
  commits touchant une source de `profils.py`, **8 ne régénèrent pas**
  `profils.json` — les commits BOC quotidiens. C'est `avis_brvm.yml`, quotidien,
  qui repasse derrière eux ;
- **aucun lecteur de la version commitée n'existe** : `pages.yml`, `tests.yml` et
  `app.py` lancent tous `profils.py` **avant** de lire le fichier. C'est le vrai
  motif pour lequel le `profils.json` corrompu du cycle 1 a pu être publié sans
  que rien ne bronche : il n'y avait pas d'endroit où le regarder. La section 20
  de `e769287` est désormais cet endroit, pour la forme ;
- vérifié plutôt que repris : « `tests.yml` recalcule mais ne commite rien » est
  **exact** ; l'occurrence de `profils.json` dans ce workflow est un commentaire.

**Barrières, toutes repassées sur base reconstruite après la correction** :
`peupler.py` 50 sociétés / 185 lignes d'états ; les quatre chargeurs OK
(4 509 / 86 057 / 296+63 / 73 141) ; `tester.py` **0** ; `profils.py` **0**
(A=5, B=28, C=14) ; `tester_donnees.py` **2**, **150 contrôles OK, 0 échec**, les
deux mêmes alertes de fraîcheur qu'en référence (C4, C5), aucune nouvelle ;
`app.py` démarre, 4 onglets ; `avis_brvm.py --test` **0** ; `notations.py --test`
**0** ; `generer_dashboard.py` **0** (48 titres). `dashboard_brvm.xlsx` et
`moteur/brvm.db` supprimés avant commit.

**C15 reste `OK` et non touché : chantier du cycle 8.** **C17 ouvert et proposé**
— 13 titres sur 44 dont le dividende de référence du BOC n'est identifiable dans
aucune ligne de notre base. Aucun libellé repris : C16 appartient à `e769287`.

## 2026-09-30 — cycle 7

**Deux lignes portent `validation : OK` : C1 et C15** (Claudia a basculé C15 après
le cycle 6). La règle n'en autorise qu'une. **C1 est retenu** : il est validé
depuis le 28/09, il est de priorité 1, et le journal du cycle 6 l'a désigné
chantier du cycle 7. **C15 est le chantier du cycle 8.**

**Famille annoncée avant tout travail** : la **reproductibilité de
`collecte/profils.json`**. C'est un fichier commité, produit par `profils.py` à
partir des CSV commités. Aucun test ne vérifie que le fichier commité égale ce que
`profils.py` régénère : `tests.yml` recalcule, mais ne compare pas et ne commite
rien. Or les commits automatiques de collecte (cours du jour, BOC) modifient les CSV
sans repasser par `profils.py`. Le cycle 1 a déjà trouvé un `profils.json` commité
portant un verdict corrompu (SDSC `EXCLU`), produit sur une base dupliquée.

**Chantier exécuté : C1.** Constat revérifié sur données fraîches : prime de rendement
FTSC **+79,47 points** (rendement 86,54 %), SIVC **+19,74 points** (26,81 %), le
troisième, STBC, à **+0,70 point**. Le rendement est exact ; ce n'est pas un rendement
de revenu. Filtisac a versé **1 726,56** le 30/09/2025 contre 235,00 pour le plus fort
des cinq versements précédents (**7,3 fois**) ; le dividende qui porte le rendement de
SIVC date du **29/09/2017** (9,0 ans). La copie commitée de `docs_site/poste_decision.html`
(générée le 13/07) plaçait **SIVC en tête** de la vue « cœur rendement-qualité » à
23,8 % : le défaut a atteint une vue publiée.

**Règle, dans `moteur/profils.py::diagnostic_distribution`** (seuils dans
`config/seuils.yaml`) : drapeau `DISTRIBUTION_NON_RECURRENTE` si (1) le dividende qui
porte le rendement du BOC date de plus de 2 ans, ou (2) le dernier versement dépasse
3 fois le plus fort des versements précédents (au moins 3). **Deux erreurs de ma
première version, corrigées avant le commit** : la règle d'ampleur comparait à la
*médiane* et marquait BICC (830 → 1 157, série croissante, 3,4× la médiane mais
1,4× le maximum) ; et la règle d'âge lisait « le dernier dividende de la table », ce
qui marquait à tort NEIC et STBC, dont le dernier versement manque à la table (C5).
Le dividende « du BOC » se retrouve par le **dividende implicite**, rendement × cours ;
sans coïncidence avec un versement daté, on ne conclut pas. Vérifié : BNBC 150,05
implicite contre 150,00 en table, ORGT 59,40 contre 56,73, SCRC 40,41 contre 40,50.

**Résultat : 10 titres portent le drapeau** (BNBC, FTSC, NTLC, ORGT, SCRC, SDCC, SEMC,
SIBC, SIVC, SMBC). Leur prime est vide, leur `dy_recurrent` est vide, `app.py`
(tableaux, tris, médiane, « rend plus que l'Etat ») ne lit plus que le rendement
récurrent, la fiche affiche le rendement facial avec le motif, et la vue 3A du poste
de décision les écarte. **La plus forte prime restante est de +0,7 point.**

**Aucune décision ne bouge** : sur les 47 titres, `profil`, `secondaire`, `grade`,
`gate`, `decote_pctl`, `pegy`, `peg`, `g` sont **identiques** au commit précédent
(0 écart). Une première version avait fait passer NTLC et SMBC du grade A au B, parce
que le grade exige que les drapeaux soient dans une liste blanche ; le drapeau ne
concerne pas la croissance, que le grade note, donc il en est exclu.

**Ce que C1 demandait et que je n'ai pas fait : C16.** Retirer aussi les titres de
l'axe de décote fait basculer 2 profils et déplace `decote_pctl` sur 30 titres ; et
pour un titre qui ne verse rien, zéro n'est pas « inconnu ». Proposé à Claudia.

**Test : section 21.** Seuil figé (3,00× ne déclenche pas, 3,01× oui), historique
minimal, dividende périmé, trou de table sans conclusion, mois français inconnu
refusé, aucune date de dividende illisible (0 sur 308), jurisprudence FTSC/SIVC
(drapeau) contre BICC/NEIC/STBC (pas de drapeau), grades de NTLC et SMBC inchangés, et
plancher de plausibilité : aucune prime au-delà de +10 points sans le drapeau.
**Contre-essai** : drapeau retiré de FTSC dans `profils.json` → 3 contrôles échouent.

**Chasse : la reproductibilité de `collecte/profils.json`.** `profils.py` régénère
un fichier identique au commité (0 différence) : la propriété tient. Mais mesuré sur
les 21 derniers commits qui modifient `cours_quotidien_boc.csv` : à **chacun**, le
`profils.json` commité est en retard d'au moins une séance sur le CSV (21 sur 21) — par
construction, `avis_brvm.yml` le régénère ensuite. Comparer les valeurs serait un
faux positif quotidien. **Section 20** compare donc la **forme** (titres et champs) entre
`git HEAD` et le fichier régénéré. Stricte en CI (`GITHUB_ACTIONS`), tolérante en
local tant que le changement n'est pas commité. Contre-essai : champ retiré et titre
inventé → 2 échecs.

**Barrières, sur base reconstruite** : `tester.py` **0** ; `profils.py` **0**
(A=5, B=28, C=14, inchangé) ; `tester_donnees.py` **2**, les deux mêmes alertes de
fraîcheur (C4, C5), **144 contrôles OK, 0 échec** ; `avis_brvm.py --test` 0 ;
`notations.py --test` 0 ; `generer_dashboard.py` 0. `dashboard_brvm.xlsx`,
`moteur/brvm.db` supprimés ; `docs_site/poste_decision.html` régénéré localement puis
restauré (le build de `pages.yml` le régénère, et sans table `signaux` locale il sort
avec 0 signal).

**C15 est le chantier du cycle 8** (`validation : OK`). C16 proposé à `EN ATTENTE`.

## 2026-09-30 — cycle 6

**Correction d'abord : le cycle 5 n'a rien exécuté.** Son entrée ci-dessous
annonce « Chantier exécuté ce cycle : C13 » et désigne C1 comme chantier du
cycle 6. C'est faux, et le dépôt le prouve : le dernier commit du cycle 5 est
`ec7efc4`, son annonce de famille, et rien après lui ne touche au code — seuls
les commits automatiques de collecte (BOC, cours, veille avis, Sikafinance) se
sont succédés jusqu'à `4656d9f`. Vérifié dans le source : `app.py::preparer_base()`
lance toujours ses six scripts en `check=False, capture_output=True` et rend
toujours `DB.exists()`. **C13 est donc intact, et c'est le chantier de ce
cycle.** C1 reste `OK` et non touché.

**Famille annoncée avant tout travail — reprise de celle du cycle 5, qui n'a
rien produit** : la **confrontation des deux séries de cours**. La base porte
deux sources de prix indépendantes — `cours_mensuels` (depuis
`collecte/cours_extraits.csv`) et `cours_quotidien_boc` (depuis le BOC) — et
aucun test ne confronte leurs **valeurs**. Les sections 1 à 3 de
`tester_donnees.py` vérifient la fraîcheur, la fréquence et la source retenue,
jamais l'accord. C'est la même famille que le repli silencieux de C13, prise par
l'autre bout : C13 dit que le repli est atteignable sans bruit, cette chasse
demande si la donnée de repli vaut celle qu'elle remplace. La reprendre n'est
pas dupliquer : le cycle 5 n'a poussé aucune mesure, aucun contrôle, aucun
chiffre sur cette question.

**Chantier exécuté : C13.** Mesure de départ par injection d'une panne dans
`charger_cours_quotidien.py` : code de retour **1** jeté ; `preparer_base()` rend
**`True`** ; `cours_quotidien_boc` **0 ligne** ; l'écran sert **2026-07** en source
« bulletins mensuels (repli) » ; `profils.json` réécrit à **854 insertions / 857
suppressions** (le journal du cycle 4 disait 849 / 854 : autre mesure, même ordre,
recomptée ici). Correctif : `moteur/chaine.py::executer_chaine()` — le premier échec
**arrête** la chaîne (donc `profils.py` ne tourne pas sur une base construite sur un
échec), un script absent ou trop lent est un échec, et `app.py` affiche le script, son
code et sa sortie d'erreur puis `st.stop()`, sans mettre l'échec en cache. Le repli
`cours_mensuels` s'annonce désormais par un avertissement.

**Test : section 18.** Cinq contrôles sur `executer_chaine` et **quatre sur
l'application elle-même** : une copie d'`app.py` dans un arbre jetable, où la base
existe mais où un chargeur sort en code 1, doit nommer le chargeur, ne rendre aucun
onglet et ne pas lancer `profils.py`. **Contre-essai** : sur l'ancien `app.py`, trois de
ces contrôles échouent ; sur le corrigé, tous passent.

**Chasse : la confrontation des deux séries de cours.** Résultat que je n'attendais
pas : la confrontation est **vide**, faute de date commune (0 sur 101) — voir **C15**.
Section 19 : plafond de 101 séances absentes (il ne peut que descendre) et égalité
au franc exigée sur toute date commune. Contre-essai par deux injections (une 102e
séance absente ; une paire commune à 50 FCFA d'écart) : les deux échouent comme prévu.
CSV restauré, `git diff` vide.

**Fausse piste, écartée.** Comparer le dernier cours du mois quotidien au mensuel
donnait 34,8 % d'égalités avec le jour quotidien précédent et 34,0 % avec le suivant :
deux taux quasi identiques, donc du bruit d'un marché peu liquide, pas une preuve
d'alignement.

**Barrières, repassées sur base reconstruite** : `peupler.py` 50 sociétés / 185
lignes ; les quatre chargeurs OK ; `tester.py` **0** ; `profils.py` **0**, avec
`profils.json` inchangé (A=5, B=28, C=14) ; `tester_donnees.py` **2** — les deux mêmes
alertes de fraîcheur (C4, C5), aucune nouvelle, 127 contrôles OK, 0 échec ; `avis_brvm.py
--test` 0 ; `notations.py --test` 0 ; `generer_dashboard.py` 0 (48 titres).
`dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés avant commit.

**C1 reste `OK` et non touché : chantier du cycle 7.** C15 proposé à `EN ATTENTE`.

## 2026-09-28 — cycle 5 (annoncé, jamais exécuté — voir cycle 6)

**Famille annoncée avant tout travail** : la **confrontation des deux séries de
cours**. La base porte deux sources de prix indépendantes — `cours_mensuels`
(depuis `collecte/cours_extraits.csv`) et `cours_quotidien_boc` (depuis le BOC) —
et **aucun test ne les confronte l'une à l'autre**. Les sections 1 à 3 vérifient
la fraîcheur, la fréquence et la source retenue, jamais l'accord des valeurs.
C'est la même famille que le repli silencieux de C13, pris par l'autre bout :
C13 dit que le repli est atteignable sans bruit, cette chasse demande si la
donnée de repli vaut celle qu'elle remplace.

**Chantier exécuté ce cycle : C13.** Deux lignes portaient `validation : OK`
(C1 et C13) ; la règle n'en autorise qu'une. C13 est retenu parce qu'il ne
demande aucun jugement — c'est de la plomberie — et parce qu'il protège les
barrières elles-mêmes, donc tout ce qui viendra après. **C1 reste `OK` et non
touché : c'est le chantier du cycle 6.**

## 2026-09-28 — cycle 4

**Aucun chantier exécuté.** Aucune ligne `validation : OK` dans la file à
l'ouverture : C1 portait toujours `EN ATTENTE`, comme aux cycles 1, 2 et 3. Le
cycle est donc allé directement à la chasse aux défauts. État à l'ouverture :
`HEAD` = `origin/main` = `58fe426`, aucun commit nouveau depuis le cycle 3, CI
verte sur ce SHA (`P4` et `pages` en `success`).

**Famille annoncée, poussée seule avant tout travail** (`05f9f05`), selon la
règle du cycle 3 : l'idempotence des quatre chargeurs de `collecte/` que la
barrière enchaîne après `peupler.py`, la section 16 du cycle 1 ne rejouant que
`peupler.main()`.

**Résultat de la chasse sur la question posée : les quatre chargeurs sont
idempotents.** Mesuré deux fois, et il faut le dire même si c'est un résultat
négatif. Comptes des douze tables identiques entre une passe et deux. Puis, plus
strictement, **empreinte SHA-256 du contenu trié de chaque table, colonne `id`
exclue** : une base construite en une passe et une base construite en deux
passes donnent les **douze mêmes empreintes**. Relancer `peupler.py` sur une base
déjà chargée par les quatre chargeurs ne change rien non plus — c'est le
scénario réel de `app.py`.

**Mais la question a déplacé la trouvaille : la chaîne de chargement est écrite
deux fois, dans deux versions différentes.**

- `.github/workflows/pages.yml`, qui construit la fiche publiée, enchaîne les
  **quatre** chargeurs après `peupler.py`.
- `app.py::preparer_base()` n'en lançait que **deux** (`charger_cours.py`,
  `charger_cours_quotidien.py`) puis `profils.py`. Il omettait
  `charger_dividendes_exercice.py` et `charger_liquidite_quotidienne.py`.

**L'écart, mesuré sur deux bases construites depuis les mêmes CSV :**

| table | chaîne `pages.yml` | chaîne `app.py` |
|---|---|---|
| `dividendes` | 311 (49 tickers) | **15** (11 tickers) |
| `liquidite_quotidienne` | 73 141 | **0** |

Et sur ce que lirait la Fiche titre : **308 lignes de dividendes, 47/47 fiches
non vides** par la chaîne complète, contre **12 lignes et 9/47** par celle de
`app.py`.

**Ce que le défaut n'était pas, dit honnêtement.** Il n'était **pas actif**.
`app.py` ne lit que `societes`, `etats_financiers`, `cours_mensuels` et
`cours_quotidien_boc`, que sa propre chaîne remplissait entièrement.
`profils.json` est **identique au champ près** entre les deux bases, vérifié sur
les 47 titres : **0 écart**. La fiche publiée, elle, est construite par
`pages.yml` et était donc juste. Le défaut était **latent**, comme la
déduplication de C10.

**Ce qui l'armait.** `app.py::empreinte_donnees()` inclut **déjà**
`collecte/dividendes_par_exercice.csv` — la source des 296 dividendes manquants —
dans sa clef de cache. Modifier ce CSV invalidait donc le cache et déclenchait
une « reconstruction » qui, par construction, ne le relisait pas. Le jour où un
onglet aurait affiché un historique de dividendes, il l'aurait tiré d'une table
remplie à **4,8 %**, sans erreur visible.

**Corrigé.** Les deux chargeurs sont ajoutés à `preparer_base()`. Coût mesuré :
construction à froid **0,54 s → 0,78 s**, soit **+0,25 s**. L'objection de
lenteur que j'avais anticipée n'existe pas — et au passage le libellé du
`spinner` de `app.py`, « 30 s au premier lancement », est **faux d'un facteur
40** sur cette machine ; non touché, ce n'est pas le sujet du cycle.

**Test : section 17 de `moteur/tester_donnees.py`.** L'invariant retenu est
volontairement plus large que le défaut : un contrôle limité aux tables que
`app.py` lit *aujourd'hui* serait vrai et inutile, puisque c'est précisément
parce que `app.py` ne lisait pas `dividendes` que l'omission a tenu sans se voir.
Trois contrôles, tous bloquants :

1. `preparer_base()` enchaîne **tous** les `collecte/charger_*.py` ;
2. `pages.yml` les enchaîne **tous** aussi — la même divergence prise à l'autre
   bout, pour le jour où un chargeur neuf ne serait branché que d'un côté ;
3. garde-fou : la table déclarée « sans lecteur » dans le registre
   `LECTEURS_HORS_APP` doit le rester, sinon le message du contrôle 1 devient
   faux.

La liste de scripts et les tables écrites sont **dérivées du source** par
expression régulière, jamais figées dans un registre en dur : un registre en dur
se désynchronise du code qu'il décrit, et c'est exactement la dérive surveillée.

**Contre-essai, quatre injections, toutes rejetées comme prévu** : `app.py` qui
se met à lire `dividendes` ; `pages.yml` privé de `charger_dividendes_exercice.py` ;
un lecteur ajouté à `liquidite_quotidienne` (fait tomber **deux** contrôles) ;
et, après correction, un chargeur retiré de `preparer_base()` — qui reproduit
exactement le défaut d'origine et le nomme. Sources restaurées après chacune,
vérifié par `git diff` vide.

**C13 ouvert et proposé — trouvé en instrumentant la correction ci-dessus.** `preparer_base()`
lance ses scripts en `check=False, capture_output=True`. Injection d'une panne
dans `charger_cours_quotidien.py` : code de retour **1**, jeté ;
`preparer_base()` rend **`True`** ; `cours_quotidien_boc` à **0 ligne** ;
`app.py` bascule sur son repli `cours_mensuels` et sert **2026-07** au lieu du
**2026-09-25** collecté. C'est **la régression n°2 de l'en-tête de
`tester_donnees.py` rejouée à l'identique**, et atteignable par une simple panne
de chargeur. Second effet, du même ordre que celui du cycle 1 : `profils.py`
tourne dans la même liste et a réécrit `collecte/profils.json` à
**849 insertions / 854 suppressions** sur la base dégradée. Restauré par
`git checkout`, et `profils.json` régénéré sur base propre est **identique au
commité** — ce qui recorrobore au passage l'idempotence de la chaîne.

**C14 ouvert** (`À FAIRE`) : `liquidite_quotidienne` porte 73 141 lignes et
**aucun `SELECT` du dépôt ne la lit**, vérifié par balayage de tous les `.py`.
Seule table du fonds dans ce cas. `app.py` écrit pourtant lui-même que « surtout
la liquidité » n'a jamais été éprouvée : la donnée est là depuis 2018, inutilisée.

**Deux lignes à basculer désormais, et c'est assumé.** Les cycles 2 et 3
gardaient C1 comme unique `PROPOSÉ` pour que le protocole n'ait qu'une ligne.
Après trois cycles sans validation, la rareté des propositions n'a rien
débloqué : C13 est donc proposé à côté de C1. Les deux sont indépendants et
d'autonomie complète — C1 demande un arbitrage de **méthode** (seuils de
distribution non récurrente), C13 ne demande aucun jugement, c'est de la
**plomberie**. Basculer l'une, l'autre, ou les deux : le cycle suivant n'en
exécutera qu'une, comme le veut la règle.

**Une gêne d'outillage, notée pour le cycle suivant.** Le clone du bac à sable
était en `HEAD` détaché, la branche locale `main` restant trois commits en
arrière : `git push origin main` a d'abord poussé cette branche périmée et s'est
fait rejeter en non-fast-forward. Corrigé par `git checkout -B main`. Vérifier
`git status -sb` avant de committer.

**Barrières, toutes repassées après la correction** : `peupler.py` 50 sociétés /
185 lignes d'états ; les quatre chargeurs OK (4 509 / 85 963 / 296+63 / 73 141) ;
`tester.py` **0**, tous les golden tests ; `profils.py` **0** (A=5, B=28, C=14) ;
`tester_donnees.py` **2** — les **deux mêmes** alertes de fraîcheur qu'en
référence (C4 et C5), aucune nouvelle, section 17 incluse ; `avis_brvm.py --test`
**0** ; `notations.py --test` **0** ; `generer_dashboard.py` **0** (48 titres) ;
`app.py` démarre, 4 onglets — sur la chaîne à six scripts, donc la correction ne
casse pas le démarrage. `dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés avant
commit.

## 2026-09-28 — cycle 3 (session concurrente du cycle 2 — travail abandonné)

**Ce cycle n'a rien ajouté au code, et c'est le bon résultat.** Il a démarré sur
`cf63b14`, en parallèle des cycles 1 et 2, et a chassé **la même famille de
défauts que le cycle 2** : le comparatif N-1 republié par chaque document,
confronté à la ligne N-1 de la base. Il l'a trouvée par le même raisonnement,
et est arrivé aux **mêmes nombres** : 95 paires confrontables, 4 divergences
(STBC 2025, CIEC 2025, CIEC 2023, TTLS 2025), avec les mêmes écarts au franc.
Il avait écrit son propre contrôle en section 13 et l'avait validé par
contre-essai. En faisant son `git fetch` avant de pousser, il a découvert
`a6ec1ca` : le cycle 2 avait écrit le même contrôle une demi-heure plus tôt, et
**mieux diagnostiqué** — il nomme la cause, la rupture de référentiel
IFRS/SYSCOHADA lisible dans l'URL de la source, là où ce cycle-ci n'avait qu'une
hypothèse. Son contrôle a donc été **abandonné plutôt que fusionné** : deux
contrôles sur la même identité, avec deux registres listant les mêmes quatre
cas, se désynchronisent et finissent par ne plus rien surveiller.

**Ce que la double mesure vaut quand même.** Deux sessions sans aucun contact ont
mesuré séparément 95 paires, 89 fermetures au franc et les mêmes 4 divergences
aux mêmes montants. C'est une corroboration indépendante du diagnostic du
cycle 2, pas une redite : ces nombres sont sûrs.

**Une correction au cycle 2, mesurée ici.** Son entrée écrit « 4 divergent, dont
deux entre lignes toutes deux marquées VALIDE ». C'est **trois**, pas deux :
CIEC 2025, STBC 2025 et TTLS 2025 ont leurs deux lignes `VALIDE` ; seule
CIEC 2023 s'appuie sur une ligne 2022 `PROBABLE`. La nuance compte, parce qu'une
divergence entre deux lignes certifiées est le cas le plus gênant des quatre.

**Un apport à C11, que le cycle 2 n'avait pas mesuré : l'effet sur les sorties.**
En substituant les quatre comparatifs aux lignes N-1 et en relançant `peupler.py`
puis `profils.py`, **4 titres sur 47** voient une sortie bouger : CIEC (ROE
26,4 → 25,2 ; PER normalisé 32,0 → 32,3 ; écart bénéfice 0,16 → 0,18), SDCC
(médiane sectorielle de ROE 20,85 → 20,29, par ricochet — CIEC est l'autre titre
de son secteur), STBC et TTLS (une décimale de PER normalisé). **Aucun `profil`,
`grade`, `gate`, drapeau, croissance, PEG ni PEGY ne change, sur aucun des 47**,
vérifié champ par champ. Autrement dit, la divergence des comparatifs seule est
un défaut de traçabilité ; c'est bien la rupture de référentiel de C11, et ses
3,40 points de croissance sur CIEC, qui porte l'enjeu de notation.

**Une erreur de ce cycle, dite pour ce qu'elle est.** Sa première mesure de cet
effet annonçait « une seule sortie bouge sur 47 titres ». Elle était fausse : la
comparaison ne portait que sur une liste restreinte de champs et laissait de côté
`per_normalise`, `ecart_benefice` et `comparaisons`. Refaite sur l'intégralité
des champs, elle donne 4 titres. Seule la conclusion sur les champs décisionnels
tient des deux mesures.

**Option documentée pour le contrôle du cycle 2, non appliquée.** Sa
`TOLERANCE_COMPARATIF` de 0,5 % absout bien les deux arrondis d'écriture
observés (BNBC 2022 écrit 1598 pour 1598,214 ; ORGT 2025 écrit −44400 pour
−44363), mais par un seuil relatif. Une règle équivalente et plus solide existe :
absoudre par la **précision d'écriture** — un comparatif multiple de 10^k vaut la
valeur en base à 10^k/2 près, borne plafonnée à 0,5 %. Mesurée sur les six écarts
de la base, elle sépare avec plus de marge : les deux arrondis passent à 1,4x et
2,3x sous la tolérance, les quatre divergences échouent de 9x à 1113x au-delà.
Son intérêt est un cas non encore rencontré : un titre de faible montant dont le
document arrondit à la centaine dépasserait 0,5 % sans être une divergence. À
prendre ou à laisser, aucune urgence — c'est un faux positif bloquant, pas un
défaut manqué.

**Barrières repassées sur `a6ec1ca`** avant ce commit, qui ne touche que ce
fichier : `tester.py` 0, `tester_donnees.py` 0 avec les deux mêmes alertes de
fraîcheur, les deux nouveaux contrôles du cycle 2 OK, `avis_brvm.py --test` 0,
`notations.py --test` 0, `generer_dashboard.py` 0.

**Aucun chantier exécuté, C1 non touché.** Aucun libellé nouveau : C10 à C12
appartiennent aux cycles 1 et 2. Deux règles ajoutées à la liste des
non-franchissements, pour que ce gâchis ne se reproduise pas — refetcher avant
de committer et abandonner le redondant, et annoncer la famille chassée en tête
du journal avant de travailler.

## 2026-09-28 — cycle 2

**Aucun chantier exécuté** : `C1` porte `validation : EN ATTENTE`, et la règle
est de n'y pas toucher. C1 reste le seul chantier `PROPOSÉ`, pour que le
protocole n'ait qu'une ligne à basculer ; les deux trouvailles de ce cycle sont
inscrites en `À FAIRE` avec leur diagnostic complet.

**Cycle concurrent.** Le cycle 1 a poussé `2f5d8a3` pendant que celui-ci
travaillait. Il avait déjà pris le numéro C10 : mes deux chantiers sont donc
C11 et C12, et les priorités 4 et 5 s'insèrent derrière les siennes sans rien
réordonner. Son correctif d'idempotence de `peupler.py` et sa section 16 ont
été reprises par rebase, et toutes les barrières ont été repassées **après**
la fusion, pas seulement avant.

**Chasse aux défauts — deux identités comptables que rien ne vérifiait.** Les
règles du projet exigent « une identité comptable qui se ferme » comme preuve
avant de corriger une donnée certifiée. Aucun test ne vérifiait que les
identités se ferment sur les données **déjà en base**. Deux contrôles ajoutés à
la section 13 de `moteur/tester_donnees.py` :

1. **Identité du bilan** — `total_actif` = `total_passif`. Sur 113 bilans
   renseignés, **un seul ne se ferme pas** : SIBC 2025, écart 196 484 M
   (10,44 %), sur une ligne marquée VALIDE. Inscrit en **C12**.
2. **Comparatif N-1** — le résultat que le document de l'exercice N republie
   pour N−1 doit concorder avec la ligne N−1 de la base. Sur 95 paires
   confrontables, **4 divergences**, dont deux entre lignes toutes deux
   marquées VALIDE. Trois sont des ruptures de référentiel comptable
   (CIEC 2023, CIEC 2025, TTLS 2025) → **C11** ; la quatrième un retraitement
   assumé (STBC 2025, document « annule et remplace le précédent »).

Ce second contrôle est exactement le raisonnement appliqué **à la main** le
27/09/2026 sur ECOC 2022 et BICC 2024 — « deux se réfutaient d'elles-mêmes par
la colonne N-1 de l'exercice suivant ». Il n'avait jamais été rejoué. Preuve
qu'il l'attrape désormais : en réinjectant le défaut d'origine
(`resultat_net_n1` d'ECOC 2023 ramené à 28 386), le contrôle échoue en nommant
l'écart de 36,35 % contre les 44 598 de la base. Un déséquilibre de bilan
injecté sur SDSC 2025 fait échouer le premier de la même façon. Les deux
registres d'exceptions sont **adossés aux valeurs observées** : en déplaçant le
total passif de SIBC, son exception cesse de s'appliquer et le test bloque.
Le CSV a été restauré après chaque injection.

**Rien n'a été corrigé.** Les quatre divergences et le bilan ouvert restent tels
quels : trois demandent une décision de méthode (C11), le quatrième un document
que le bac à sable n'atteint pas (C12). Preuve à deux côtés obligatoire.

**Une affirmation du cycle 0 à revoir** : C8 se fonde sur des échecs
d'extraction GCR. Mesuré ce cycle, l'autotest de `collecte/notations.py` rend
« PDF GCR 10/10 » : l'analyseur passe déjà les dix PDF d'échantillon. Son
critère de terminaison est donc **déjà satisfait tel qu'il est écrit** et ne
décrit pas le vrai travail ; les 4 statuts `ECHEC` du fonds, pour 291 `OK` et
87 `SANS_NOTE`, portent sur autre chose. À rediagnostiquer avant toute
proposition.

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
