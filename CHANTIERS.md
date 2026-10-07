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
   qui se marchent dessus coûtent deux fois tout. **Une annonce `Annonce hors
   cycle :` sans son commit `Cloture hors cycle :` compte exactement comme une
   annonce de cycle ouverte** (voir *Travail hors cycle*, plus bas).
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

## Travail hors cycle : la conversation de développement

Ajouté le 02/10/2026, à la demande de Claudia. Deux acteurs poussent sur `main` :
**la boucle** (tâche planifiée « BRVM — boucle des chantiers (2 passages/jour) »,
06h53 et 18h53 UTC, une session neuve à chaque passage) et **la conversation de
développement**, où Claudia demande des évolutions en direct (titre : *Fiche de
reprise — Profilage BRVM (application Streamlit)*). Ils ne se parlent pas : **ce
fichier est leur seul point de contact.** Ce qui suit les empêche de se marcher
dessus et garantit que chacun voit le travail de l'autre.

**Pour la conversation de développement :**

- **Jamais pendant un passage.** Ne rien commencer entre **06h40 et 07h45 UTC**, ni
  entre **18h40 et 19h45 UTC** (un passage dure une vingtaine de minutes ; la marge
  couvre un retard de déclenchement). Un travail plus long que le temps restant
  avant la fenêtre attend qu'elle soit passée.
- **Même contrôle anti-collision que la boucle**, avant tout travail.
- **Annoncer, puis clore.** Pousser seul un commit `Annonce hors cycle : <objet>`
  avant de travailler, et terminer par un commit `Cloture hors cycle : <objet>`
  (qui peut être le commit de livraison lui-même). Si le travail est abandonné, le
  commit de clôture le dit.
- **Mêmes règles, mêmes barrières** que la boucle : celles de ce fichier valent pour
  les deux.
- **Tracer.** Entrée `hors cycle` en tête de `docs/JOURNAL.md` ; et si le travail
  touche un chantier de la file, mettre à jour son bloc (statut, mesure). Une
  demande nouvelle de Claudia qui ne sera pas finie dans la conversation devient un
  **chantier de la file**, avec sa classe : c'est ainsi que la boucle la reprend.

**Pour la boucle :** une annonce hors cycle ouverte l'arrête comme une annonce de
cycle (étape 2). Les commits hors cycle sont du travail validé par Claudia en
direct : les relire au contrôle d'état (étape 3), ne jamais les défaire.

## Barrières : lesquelles, et quand

**Complètes** — `peupler.py`, les quatre chargeurs, `tester.py`, `profils.py`,
`tester_donnees.py`, `avis_brvm.py --test`, `notations.py --test`,
`generer_dashboard.py` — dès que le commit touche `moteur/`, `collecte/`,
`config/`, `donnees/`, `outils/`, `app.py` ou `dashboard/`.

**Aucune** si le commit ne touche que `CHANTIERS.md` ou `docs/`. Reconstruire la
base pour un commit de texte a coûté un cycle entier les 28 et 30/09.

**La barrière qui ne tournait pas dans le bac à sable y tourne à nouveau.**
`dashboard/generer_dashboard_html.py` échouait à la compilation avec
`SyntaxError: f-string expression part cannot include a backslash` parce que le bac à
sable portait Python **3.11** alors que `pages.yml` et `tests.yml` épinglent **3.12**,
où PEP 701 autorise l'antislash dans une f-string. **Revérifié le 01/10/2026 (cycle
12) : le bac à sable porte désormais Python 3.13.15 et le fichier compile.** La
conclusion de 2026-09-30 tenait, et elle est confirmée par l'autre bout : c'était
l'environnement, jamais le fichier. Ne pas « réparer » ce fichier ; et ne pas s'étonner
non plus si un bac à sable futur retombe en 3.11 — vérifier la version avant de
conclure à une régression.

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

**Ce que C17 a fourni le 01/10/2026 (cycle 12), et ce qu'il n'a pas fourni.** Le
rapport implicite/déclaré, que C17 annonçait comme « la mesure qui manquait à C2 »,
est désormais sous 10 % sur **44 titres sur 44** (il l'était sur 31). L'écart entre
convention brute et nette ne peut donc plus être grand sur aucun titre. Le **second**
axe — l'exercice de rattachement — reste entier : il ne se lit pas sur ce rapport.
Trois des 8 refus de C22 (SEMC, BOABF, BOAC) sont la même question brut/net vue sur
des montants.

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

**Mise à jour du 03/10/2026 (cycle 17) : elles sont 12, et DEUX d'entre elles sont
des divisions réelles, prouvées.** C18 a corrigé STBC 12/07/2018, qui sort donc de
l'alerte. Surtout, il a trouvé la preuve indépendante de deux divisions de nominal
que ce chantier cherchait à l'aveugle — le **rebasement du dividende publié par le
BOC** dans `collecte/cours_extraits.csv`, colonne `dividende_montant` :

- **SAFC, 1 pour 25, fin décembre 2018** : dividende **576,00 → 23,04** entre le
  bulletin de novembre et celui de décembre, soit **576 / 23,04 = 25,0 exact**. Le
  cours passe de 5 300 à 215 le 21/12/2018 et la série reste à 215, 210, 200 toute
  l'année 2019. C'est la date `SAFC 2018-12-21` de l'alerte.
- **STBC, 1 pour 20, le 27/07/2018** : dividende **4 124,0 → 206,2** entre le
  bulletin de juillet et celui d'août, soit **÷20 exact** ; le cours passe de
  40 000 à 2 000 le 27/07/2018, **÷20 exact** lui aussi. C'est la date
  `STBC 2018-07-27` de l'alerte. (C'est aussi l'explication du rendement STBC de
  210,41 % au 31/07/2018 que C15 avait laissé vide : un dividende non ajusté de la
  division.)

Deux sources indépendantes se ferment donc sur chacune : le dividende et le cours,
du même facteur. **Cette voie — relire la colonne `dividende_montant` du mensuel —
est à appliquer aux dix autres dates avant de chercher le moindre avis de
fractionnement.** Elle est gratuite, sans réseau, et elle vient du BOC lui-même.

Les deux dates `SAFC 2019-01-02` et `SAFC 2019-01-07` restantes ne sont pas des
divisions : elles tomberont d'elles-mêmes quand **C30** aura tranché le sort des
lignes fautives du 31/12/2018 et du 04/01/2019.

**Terminé quand** : chacune des 12 dates est soit documentée avec sa source, soit
explicitement écartée avec son motif — les deux artefacts SAFC relèvent de C30 et
s'écartent par là ; l'alerte de fraîcheur s'éteint.

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
- statut : **FAIT le 01/10/2026 (cycle 11)** — option (b) appliquée et figée par un
  test ; effet mesuré au bas de ce bloc. Les deux passes de ce chantier sont
  consommées : la mesure (cycle 9) et l'application (cycle 11). **Aucun cycle ne le
  reprend.** Ce que l'application a rendu visible est inscrit en **C20**, à part.
- validation : OK option (b) 
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

### Fait le 01/10/2026 (cycle 11)

Claudia a écrit `validation : OK option (b)` le 30/09 à 19h54. L'axe de décote lit
désormais `dy_axe` — le rendement **récurrent** — et non plus `dy`, le rendement
facial du BOC. Un titre drapeauté a donc une case vide sur cet axe et sort du
bassin de comparaison.

**Effet mesuré sur la base du jour, (a) → (b), 47 titres.** Les trois effets
annoncés par la mesure du cycle 9 sont confirmés, au titre près :

| | prévu (cycle 9) | mesuré (cycle 11) |
|---|---|---|
| `decote_pctl` bouge | 28 / 47 | **29 / 47** |
| amplitude hors ORGT | −1 à −3 points | **−1 à −3 points** |
| ORGT | 54 → 93, gagne `VALUE` | **54 → 93, `AUCUN_PROFIL` → `VALUE`** |
| SMBC | perd son secondaire `VALUE` | **perd son secondaire `VALUE`** (68 → 66) |
| `grade`, `gate`, `drapeaux` | 0 | **0, 0, 0** |

Le bloc des bassins a été **hissé au niveau module** dans
`moteur/profils.py::bassins_et_axes()`, sans changer un calcul : il vivait dans
`calculer()`, donc la règle n'était testable qu'en refaisant tourner tout le
moteur. Garde posée à l'extraction : `profils.json` identique au champ près,
**0 titre d'écart**.

**Test : section 21, 5 contrôles**, sur un bassin **jetable** de quatre titres —
donc indépendant des données du jour — et portant son **contre-exemple** : les
mêmes titres sous l'option (a) donnent D P62 au lieu de P100, B P62 au lieu de
P58, C P38 au lieu de P29. Sans ce contre-exemple le contrôle passerait aussi sur
l'option refusée.

**Ce que l'application a rendu visible, et qui n'est pas tranché** : 28 titres ont
perdu 1 à 3 points de décote **sans qu'aucune de leurs données change**, et le
basculement de SMBC n'a rien à voir avec un dividende périmé. C'est l'effet de
bassin, inscrit en **C20**.

## C17 — Pour 13 titres sur 44, le dividende que le BOC divise reste introuvable

- classe : ORANGE — l'inventaire est pré-autorisé ; écrire un dividende en base ne l'est pas
- statut : **FAIT le 01/10/2026 (cycle 12)** — voir *Fait le 01/10/2026* en bas de ce
  bloc. Les deux passes de ce chantier sont consommées : l'inventaire et l'écriture,
  celle-ci sur le `validation : OK` de Claudia du 01/10 à 08h32. **Aucun cycle ne le
  reprend.** Ce que l'exécution a laissé ouvert est inscrit à part, en **C21** et **C22**.
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

### Fait le 01/10/2026 (cycle 12)

**Le diagnostic de ce chantier était faux, et c'est le résultat.** Il parlait d'une
« lacune de collecte ». Il n'y en avait aucune. Les **13** références étaient dans
`collecte/dividendes_boc.csv` — fichier **commité**, écrit par
`collecte_boc_quotidien.py` depuis la colonne « Dernier dividende payé » du bulletin,
collectées entre le **28/07** et le **30/09/2026** — et **aucun chargeur de la chaîne
ne lisait ce fichier**. `collecte_boc_quotidien.py` les insérait dans une base jetée à
chaque reconstruction. La donnée était collectée, commitée, et perdue à l'entrée.

**Comment la cause a été trouvée.** En datant le dividende implicite séance par
séance sur 2026 au lieu de ne regarder que la dernière : il forme des **paliers**. Pour
chacun des 13, le palier d'avant la bascule égale à moins de 0,1 % le versement que
nous avons en base, et le palier d'après égale l'implicite non concordant. Ce n'était
donc pas un dividende introuvable mais un dividende **suivant**, adopté par le BOC
entre le 28/07 et le 24/09/2026. Les bascules, titre par titre : SLBC 29/07, BICB et
SIBC 30-31/07, LNBB 03/08, SOGC 05/08, STBC 12/08, CFAC 13/08, SGBC 21/08, SPHC 27/08,
TTLC 28/08, NTLC 04/09, NEIC 09/09, SDCC 15/09, SMBC 17/09, SHEC 24/09, ABJC 29/09.

**Preuve à deux côtés**, exigée avant d'écrire une donnée certifiée. Les deux côtés
sont **deux colonnes différentes du même bulletin**, extraites indépendamment : la
colonne « Dernier dividende payé » (montant et date) d'un côté, le rendement publié ×
le cours publié de l'autre, en palier sur 5 à 41 séances à cours mouvant. Les 16
lignes chargées concordent entre **0,01 % et 0,16 %**.

**Ce qui a été écrit.** `collecte/charger_dividendes_boc.py`, cinquième chargeur,
branché dans `app.py` et dans les **8** workflows qui enchaînent les chargeurs. Sur la
base du jour : **16 ajouts, 2 compléments, 8 refus, 0 écart**. La table passe de
**311 à 327** lignes. Pas de script de migration dans `outils/` : rien dans le dépôt
n'est modifié, la base est rebâtie à neuf à chaque passage.

**Les 2 compléments** sont STBC 2024 et SMBC 2024. `donnees/base/dividendes.csv` y
portait un marqueur « date BOC ; montant à re-sourcer » à montant **vide**, et
`charger_dividendes_exercice.py` déduplique par `(ticker, exercice)` : le marqueur
**masquait** le montant que la Piste D portait déjà (2 096,00 et 616,00, aux mêmes
dates). Le montant n'est complété que si la `date_paiement` est **identique des deux
côtés** — c'est la seconde moitié de la preuve, et c'est ce qui fait refuser NSBC.

**Défaut trouvé en posant la garde, corrigé dans le même commit.** La clef naturelle
de `peupler.py` inclut `montant_net` : une ligne vide et sa version complétée sont
deux lignes différentes pour elle. Le passage suivant de `peupler.py` — et
`app.py::preparer_base()` le relance sur une base **existante** dès que l'empreinte
change — **réinsérait le marqueur vide à côté de la ligne complétée**. Trouvé parce
que la section 24 tombait après le seul test d'idempotence de la section 16. Seconde
garde posée, étroite : elle ne retient que l'insertion d'un montant **vide** déjà
renseigné pour le même (ticker, exercice, jour). Trois passages de `peupler.py` sur la
base chargée : **327 lignes, stable**.

**Effet mesuré, et il faut le dire franchement : aucun verdict ne bouge.**
`collecte/profils.json` est **identique à l'octet** avant et après, 0 titre d'écart sur
47. Les 16 versements chargés sont tous récents (2026-07 à 2026-09) : aucun n'est
périmé au sens de la règle 1, aucun ne dépasse 3 fois le plus fort des précédents.

**Le vrai gain est ailleurs, et il était invisible.** La règle 1 de C1 n'identifie son
dividende de référence que par coïncidence entre l'implicite du BOC et le versement le
**plus récent** de la table ; sans coïncidence elle ne conclut pas. Elle était donc
**silencieusement inapplicable sur 13 des 44 titres**, soit 30 % du marché, sans
qu'aucun contrôle ne le dise. Après chargement : **44 / 44**.

**Ce que C2 attendait de ce chantier est fourni.** C2 disait « c'est la mesure qui
manquait » : le rapport implicite/déclaré est désormais à moins de 10 % sur **44
titres sur 44**, contre 31. L'écart entre convention brute et nette ne peut donc plus
être grand sur aucun d'entre eux — mais cela ne tranche pas le **second** axe de C2,
l'exercice de rattachement, qui reste entier.

**Test : section 24, 9 contrôles**, vérifié par **injection** — base reconstruite sans
le cinquième chargeur : 2 contrôles tombent en ÉCHEC (« chaîne amputée », « masqués :
STBC ex.2024, SMBC ex.2024 ») et l'alerte redescend à **31 / 44** en nommant les 13
titres. La section 17 verrouille d'elle-même la présence du nouveau chargeur dans
`app.py`, `pages.yml` et les workflows qui recommitent `profils.json`, parce qu'elle
découvre les chargeurs par `glob("charger_*.py")`.

## C18 — Cinq collisions d'échelle dans la série de cours

- classe : ORANGE — corriger une série de cours commitée exige la preuve à deux côtés ; la mesure est faite
- statut : **FAIT le 03/10/2026 (cycle 17) pour 5 des 7 séances** — 3 corrigées, 2
  requalifiées, 2 mesurées et **non écrites** parce que les corriger fait tomber la
  section 19 : cet arbitrage-là part en **C30**. La passe autorisée est consommée ;
  **aucun cycle ne reprend C18.** Voir *Ce qu'a trouvé le cycle 17*, au bas du bloc.
- validation : OK
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

### Ce qu'a trouvé le cycle 17 (03/10/2026) : le tableau ci-dessus se trompait de séance sur deux cas

Le détecteur de la section 22 signale la séance de **chute**, jamais celle du
**retour**. Sur SAFC, la chute est l'événement réel et c'est le retour qui est
fautif — le texte d'ouverture de ce bloc le disait déjà (« la séance du 31/12/2018
de SAFC … porte 5 300 quand elles portent 215 ») ; c'est son tableau, bâti par le
détecteur, qui nommait les mauvaises lignes.

| séance | valeur | tranché | preuve à deux côtés, vérifiée à l'exécution |
|---|---|---|---|
| SLBC 12/01/2022 | 154,0 | **corrigée → 154 000** | PER 14,47 publié *sur la ligne* × BPA 10 642,71 (154 000 / 14,47 des deux côtés) = 154 000 ; facteur **1 000** exact |
| SLBC 02/06/2023 | 67,6 | **corrigée → 67 600** | BPA 739,48 identique le 01/06 (73 075 / 98,82) et le 05/06 (62 530 / 84,56) ; PER 91,41 de la ligne ⇒ 67 596, à 0,005 % de 67 600 — facteur **1 000**, pas 1 081 : le cours de SLBC *baissait* dans cette fenêtre |
| STBC 12/07/2018 | 11 315 | **corrigée → 44 995** | pas une erreur d'échelle (facteur 3,98, rien de rond) ; le rendement 9,17 % publié sur la ligne, avec le dividende 4 124 alors en vigueur, impose un cours dans **[44 948 ; 45 001]** ; 11 315 donnerait 36,45 % |
| SAFC 21/12/2018 | 215 | **laissée — ce n'est pas une collision** | **division de nominal 1:25 réelle** : le dividende publié par le BOC passe de **576,00 à 23,04** entre les bulletins de nov. et déc. 2018, soit **576 / 23,04 = 25,0 exact** ; la série reste à 215, 210, 200 toute l'année 2019 |
| SAFC 02/01/2019 | 215 | **laissée** | la « chute » n'existe que par la ligne fautive du 31/12 ; elle disparaît dès que celle-ci est corrigée |
| SAFC 31/12/2018 | 5 300 | **fautive, NON écrite — C30** | vaut **215** : le bulletin de **janvier 2019** publie cours 200 et variation annuelle **−6,98 %**, donc clôture 2018 = 200 / (1 − 0,0698) = **215,0**. Le BOC se contredit d'un bulletin à l'autre et c'est son propre calcul qui tranche |
| SAFC 04/01/2019 | 5 300 | **fautive, NON écrite — C30** | valeur d'avant division réapparue ; encadrantes à 215 le 03/01 et le 07/01 |

**Pourquoi les deux dernières ne sont pas écrites.** Les corriger fait tomber la
**section 19** : la ligne du 31/12 est une **copie** de la ligne mensuelle versée par
C15, et ce contrôle bloquant exige l'égalité au franc entre les deux séries, plafond
zéro. Vérifié en le faisant : `4508 paires confrontées, 1 divergente — SAFC 2018-12-31 :
mensuel 5300 contre quotidien 215`. Tout a été annulé. Trancher laquelle des deux
extractions fait foi, et inscrire une exception nommée dans un contrôle bloquant, est un
arbitrage de méthode qui ne revient pas à la boucle. **C30.**

**Livré** : `outils/correction_collisions_echelle.py` (idempotent — relancé deux fois,
« correction DEJA APPLIQUEE » ; entête et comptes attendus, ancres avec assertion
d'unicité, garde `ATTENDU` sur la valeur fautive **et** sur les deux encadrantes,
témoins de la division 1:25 relus dans `cours_extraits.csv`, SHA-256 avant/après,
réserialisation exigée à l'octet près, relecture après écriture) ; **3 lignes modifiées
sur 90 660**, aucune autre case touchée.

**Effet mesuré, avant/après, sur la base du jour.**

| | avant | après |
|---|---|---|
| dates à l'alerte « divisions de nominal » (section 7) | 13 | **12** |
| chutes de plus de 99,5 % dans la série | 2, **écartées en silence** | **0**, et le seuil bas est retiré |
| registre `COLLISIONS_ECHELLE` | 5 | **2** (les deux SAFC, requalifiées, en attente de C30) |
| champs de `collecte/profils.json` déplacés | — | **0** (fichier identique) |

Le défaut était bien **latent** : 0 champ de `profils.json` bouge. Ce qui en dépendait,
ce sont les trois backtests du dépôt, qui lisent la série entière.

**Le seuil de la section 7 est retiré, et remplacé.** Le tri valait `var < −0,60` **et**
`var > −0,995`, avec pour commentaire « on ignore les erreurs de saisie manifestes ». Les
deux seules chutes que cette borne écartait étaient les deux SLBC — écartées, et
enregistrées nulle part. La borne basse disparaît ; un contrôle neuf **nomme** désormais
toute chute de plus de 99,5 % qui ne serait pas au registre.

**Trouvé en chemin, et inscrit en C4** : deux divisions de nominal réelles, toutes deux
corroborées par le rebasement du dividende publié — **SAFC 1:25 fin décembre 2018** et
**STBC 1:20 le 27/07/2018** (dividende 4 124,0 → 206,2, soit **÷20 exact**, et cours
40 000 → 2 000, **÷20 exact** lui aussi).

## C19 — `dividendes_par_exercice.csv` porte des doublons, et son générateur ne le rend plus

- classe : ORANGE — décider quelle ligne est la bonne est un arbitrage ; la mesure est faite
- statut : **MESURÉ le 03/10/2026 (cycle 15) — la passe autorisée est consommée, aucun cycle
  ne la refait.** L'arbitrage « remettre FTSC 2016 » **fait tomber la barrière** : trois
  contrôles passent en ÉCHEC et la prime de rendement de **+79,5 points** revient sur FTSC.
  **Rien n'a été écrit.** Le dédoublonnage seul, lui, est mesuré **vert**. Voir *La mesure,
  faite le 03/10/2026* en bas de ce bloc : il faut un nouveau mot de Claudia.
- validation : OK — remettre FTSC 2016
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 2

**Mesuré le 02/10/2026 (cycle 14), en passant les barrières, et cela change l'enjeu de ce
chantier.** Les doublons rendent **`collecte/profils.json` non reproductible** : reconstruire
la base et relancer `profils.py` sur le dépôt inchangé redonne le fichier commité **au champ
près sauf une valeur**, et cette valeur vient d'un doublon. `SEMC` porte **deux lignes pour
l'exercice 2020**, 14,4 et 14,0 FCFA, même date de paiement — le `profils.json` commité a
retenu 14,40, une reconstruction retient 14,00. Les deux sont de vraies observations du BOC
(14,4 jusqu'au 13/05/2024, 14,0 depuis le 14/05/2024, lu dans `dividendes_historique.csv`),
mais rien ne départage les lignes, donc **c'est l'ordre de lecture qui décide**. `SEMC` 2016
en porte **trois** (677,0 / 676,8 / 16,92). Ce n'est donc pas une question de propreté : un
artefact commité et publié dépend de l'ordre des lignes d'un CSV. **Rien n'a été écrit** —
choisir la ligne est l'arbitrage de ce chantier. La boucle propose de porter sa **priorité
de 6 à 2** ; seule Claudia édite cette ligne.

**CORRIGÉ le 03/10/2026 (cycle 15) : ce paragraphe est faux, et c'est un artefact de la
barrière amputée du cycle 14.** Sur la chaîne **complète** des cinq chargeurs, `profils.json`
est reproduit **identique à l'octet** et `SEMC` 2020 vaut **14,4**, la valeur commitée — parce
que la ligne 14,4 précède la 14,0 dans le CSV (lignes 247 et 248) et que
`charger_dividendes_exercice.py` garde la première. Rejoué ce cycle sur la chaîne **amputée**
du cycle 14, sans `charger_dividendes_exercice.py` : la table tombe à **72 lignes** au lieu de
327 et `SEMC` 2020 vaut **14,00**, chargé par `charger_dividendes_boc.py` sur une case laissée
vide. C'est le même quatrième-chargeur-manquant que le cycle 14 a reconnu dans son propre
message de commit. **Les doublons ne rendent donc rien d'irreproductible**, et la priorité 2
repose sur une mesure qui ne tient pas.

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

### La mesure, faite le 03/10/2026 (cycle 15)

Trois états du fichier construits dans des copies jetables du dépôt, base reconstruite à
chaque fois par la chaîne complète des cinq chargeurs. **Aucun fichier du dépôt modifié.**

**L'état des lieux, recompté ce cycle.** Le fichier commité porte **364 lignes de données
pour 348 clés** : **16 lignes excédentaires en 10 groupes** — ABJC 2017 ×3, ETIT 2016 ×7,
puis BOAM 2024 (deux montants, ×2 chacun), ECOC 2022, ETIT 2021, ORAC 2023, SLBC 2017 et
STBC 2016 (deux montants) ×2. La régénération rend **365 lignes**, la ligne de plus étant
`FTSC,2016,1045.0,2017-07-31,ELEVEE`. **Et elle ne reproduirait pas le fichier même sans
cela** : le générateur écrit en **CRLF** (défaut du module `csv`) là où le fichier commité
est en **LF**. L'égalité exigée par le critère de terminaison demande donc trois choses, pas
une.

| | dédoublonnage seul (348 lignes) | dédoublonnage + FTSC 2016 (349 lignes) |
|---|---|---|
| `collecte/profils.json` | **identique à l'octet** | **4 champs bougent, tous sur FTSC** |
| `tester_donnees.py` | **241 OK, 0 ÉCHEC**, code 2 (alertes de fraîcheur seules) | **3 INCOHÉRENCES BLOQUANTES** |
| `profil`, `secondaire`, `grade`, `gate` | 0, 0, 0, 0 | **0, 0, 0, 0** |
| `decote_pctl` sur les 47 | **0** | **0** — FTSC n'est pas analysable, aucun effet de bassin |

**Pourquoi la barrière tombe, et ce n'est pas le test qui a tort.** La règle 2 de C1 compare
le dernier versement au **plus fort des précédents**. Aujourd'hui ce plus fort vaut **235,00**
(2021-07-30) et le rapport fait **7,35**, au-delà de `distribution_ratio_max` = 3,0 : FTSC
porte `DISTRIBUTION_NON_RECURRENTE`. Avec FTSC 2016 à **1 045,00**, le plus fort des
précédents devient 1 045,00 et le rapport tombe à **1,65** : le drapeau disparaît, `dy_axe` et
`dy_recurrent` se remplissent du rendement facial de **86,54 %**, et la **prime de +79,5
points** que C1 existe pour éteindre revient. Les trois ÉCHEC le disent mot pour mot :
« FTSC porte le drapeau… », « aucune prime au-delà de +10 points sans le drapeau — SANS
DRAPEAU : FTSC », « la plus forte prime restante est de +79,5 points ».

**Ce que la boucle ne peut pas trancher seule, et pourquoi elle s'arrête.** Le montant de
1 045,00 n'a **qu'un seul côté**. L'avis BRVM N° 072-2017/DC/BR/DG, cité par le générateur
lui-même, corrobore la **date** (exercice 2016 payé le 31/07/2017) — pas le montant. Et
l'identité de couverture ne peut pas être fermée : la base **ne porte aucun exercice FTSC
avant 2021** (le plus ancien est 2021, résultat net **−1 276,336 M**), donc rien à confronter
à 1 045,00 × 14,1 millions d'actions. Écrire cette ligne serait écrire une donnée certifiée
sur une source unique, **et** défaire une analyse humaine — les deux règles que la boucle ne
franchit pas.

**Les trois issues, pour que la décision tienne en un mot.**

1. **Dédoublonner seul**, et corriger le générateur pour qu'il écarte FTSC 2016 avec le motif
   écrit ci-dessus (source unique, identité infermable). Mesuré : **vert**, effet nul.
2. **Remettre FTSC 2016 et réviser la règle 2 de C1** — comparer la distribution au
   **résultat** de l'exercice et non au plus fort des versements passés, puisqu'une seconde
   distribution exceptionnelle dans l'historique désarme la règle actuelle. C'est un chantier,
   pas une passe : il touche la règle que C1 a figée.
3. **Remettre FTSC 2016 et retirer les trois contrôles** : à écrire, mais c'est rendre à FTSC
   la prime de +79,5 points pour laquelle C1 a été ouvert.

La boucle ne propose rien entre les trois : (1) est mécanique, (2) est un arbitrage de
méthode, (3) défait C1.

## C20 — L'effet de bassin : un titre qui sort d'un axe déplace le rang des autres

- classe : ORANGE — arbitrage de méthode sur la lecture des axes ; le diagnostic est fait
- statut : **FAIT le 02/10/2026 (cycle 13)** — les trois lectures sont mesurées (tableau
  en bas de ce bloc) et l'option (a) est figée par la section 25, vérifiée par injection.
  **Les deux passes de ce chantier sont consommées** : la mesure et l'application.
  **Aucun cycle ne le reprend.**
- validation : OK option (a)
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 3

**Le constat, mesuré le 01/10/2026 (cycle 11) en appliquant C16.** Retirer deux
titres du bassin de rendement — ORGT (2,05 %) et SEMC (0,94 %), deux valeurs
**basses** — a fait perdre **1 à 3 points de décote à 28 titres sur 47**, sans
qu'aucune de leurs données ait changé. Et cela a produit un basculement de verdict
qui n'a rien à voir avec un dividende périmé : **SMBC perd son secondaire `VALUE`**
parce que sa décote passe de 68 à 66, pour un seuil `value_pctl_min` de 67.

**Pourquoi c'est un chantier et pas la conséquence normale d'un percentile.** Trois
mesures de ce cycle, sur la base du jour :

1. **Le cran du percentile est plus gros que la marge des seuils.** Le bassin
   marché porte 36 valeurs en bénéfice/prix et 34 en rendement, soit **2,8 et
   2,9 points par cran**. Mais les 14 titres des `SERVICES_FINANCIERS` lisent un
   bassin **sectoriel de 14 valeurs**, soit **7,1 points par cran** sur l'axe
   bénéfice/prix et **7,7** sur celui du rendement. Un seul titre qui entre ou sort
   déplace donc un rang de plus de 7 points dans ce secteur.
2. **Trois titres sont aujourd'hui à 3 points ou moins du seuil VALUE** (67) :
   ONTBF P66, SMBC P66, SLBC P70. Trois autres sont à 3 points ou moins du seuil
   GROWTH sur l'axe croissance : ETIT, SNTS, SPHC. **Six verdicts** sont donc à la
   portée d'un seul mouvement de bassin, soit un titre qui entre, sort, est
   suspendu, ou devient non analysable.
3. **Un titre est dans son propre bassin.** `pctl()` compte `val <= x` en incluant
   la valeur du titre : dans un bassin de 14, un titre ne peut pas descendre sous
   P7. Le rang mesure donc en partie la présence du titre lui-même.

**Ce qu'il faut trancher, et ce qui se mesure sans rien écrire.** Trois lectures,
toutes défendables : (a) laisser tel quel — le rang est relatif, un bassin qui
change est une information ; (b) percentile **laisser-un-dehors**, chaque titre
classé contre les autres seulement, ce qui supprime l'auto-inclusion ; (c) **plancher
de taille de bassin** — relever `n_secteur_min` ou basculer sur le marché quand le
bassin de l'axe considéré descend sous un seuil, puisque la borne actuelle (8) porte
sur le bassin bénéfice/prix et non sur celui du rendement, qui peut être plus petit.

**Terminé quand** : les trois lectures sont mesurées titre par titre sur les
47 titres — décote avant/après, profils et grades qui basculent — et le tableau est
inscrit ici. L'application attend un mot de Claudia, comme pour C16.

### La mesure, faite le 02/10/2026 (cycle 13)

Trois variantes de `bassins_et_axes()` substituées au niveau module — le hissage du
cycle 11 rend la mesure possible sans toucher au dépôt — exécutées sur la base du
jour, chacune écrivant son `profils.json` hors du dépôt. **Garde vérifiée** : la
variante (a) reproduit le `profils.json` commité au champ près, **0 titre d'écart sur
47**, sur les huit champs `profil`, `secondaire`, `grade`, `gate`, `drapeaux`,
`decote_pctl`, `croissance_pctl`, `reference_axes`. Aucun fichier du dépôt modifié.

| | (b) laisser-un-dehors | (c) plancher par axe |
|---|---|---|
| `decote_pctl` bouge | **31 / 47** | **0 / 47** |
| amplitude | **−1 à −6 points**, jamais à la hausse | aucune |
| écart absolu moyen | 2,84 point | 0 |
| `croissance_pctl` bouge | 30 | 0 |
| `profil`, `secondaire`, `grade`, `gate`, `drapeaux` | **0, 0, 0, 0, 0** | 0, 0, 0, 0, 0 |
| `reference_axes` bouge | 0 | 0 |

**Ce que la mesure apprend, et qui n'était pas prévu.**

1. **L'option (b) ne déplace aucun verdict, mais elle déplace tout le monde dans le
   même sens.** 31 titres sur 47 perdent de 1 à 6 points, **aucun n'en gagne** :
   retirer sa propre valeur d'un bassin ne peut que faire remonter le titre dans le
   classement par le cher. Ce n'est donc pas un recentrage, c'est un décalage
   systématique — et la marge aux seuils s'en trouve rognée partout, pas corrigée.
   Les trois titres proches du seuil GROWTH descendent de 2 à 3 points tous les
   trois (ETIT 69→67, SNTS 66→65, SPHC 69→68).
2. **L'option (c) est un non-événement sur les données du jour, et la mesure dit
   pourquoi.** Un seul secteur est lu en sectoriel — `SERVICES_FINANCIERS`, 14 titres
   — et ses trois bassins passent le plancher : 14 en bénéfice/prix, **13** en
   rendement, 13 en croissance. Le défaut que le texte de ce chantier décrivait (« la
   borne porte sur le bassin bénéfice/prix et non sur celui du rendement ») est donc
   **réel dans le code et latent dans les données**. La section 25 porte désormais une
   alerte qui s'allumera le jour où un axe sectoriel descendra sous 8.
3. **La variante « relever `n_secteur_min` » de l'option (c) ne change rien jusqu'à
   15.** Mesurée à 8, 10, 12, 14, 15 et 20 : aucun mouvement jusqu'à 14 ; à **15**,
   `SERVICES_FINANCIERS` bascule sur le marché et **13 titres sur 47** bougent, mais
   **0 profil, 0 secondaire, 0 grade**. Le levier existe, il est brutal, et il
   n'achète aucun verdict.
4. **Les trois chiffres de portée du diagnostic d'origine ont bougé en un jour, deux
   sur trois dans le bon sens.** Le cran du percentile est confirmé exactement (marché
   2,8 et 2,9 points ; `SERVICES_FINANCIERS` 7,1 et 7,7). Mais **« six verdicts à
   portée d'un seul mouvement de bassin » n'en fait plus que quatre** : sur l'axe de
   décote, seul **SMBC (P66)** est encore à 3 points ou moins du seuil 67 — ONTBF est
   passé à P63 et SLBC à P73. Sur l'axe de croissance, les trois nommés y sont
   toujours (ETIT P69, SNTS P66, SPHC P69). Le plancher par auto-inclusion est
   confirmé : P7 en bénéfice/prix et **P8** en rendement dans `SERVICES_FINANCIERS`,
   P3 sur le marché.

### Fait le 02/10/2026 (cycle 13)

**L'option (a) est appliquée, c'est-à-dire que rien n'est écrit dans le moteur** —
c'est le sens du choix : le rang est relatif, un bassin qui change EST une
information. Ce que le cycle écrit, c'est le **test qui empêche de changer d'avis par
inadvertance** : **section 25 de `tester_donnees.py`, 7 contrôles**, sur un bassin
**jetable** de 12 titres — donc indépendant des données du jour — construit pour que
les trois lectures donnent trois nombres différents sur le même titre : **46** en (a),
**32** en (b), **41** en (c). Le bassin jetable porte 8 valeurs en bénéfice/prix et 3
en rendement, exactement la configuration que l'option (c) traiterait autrement.

**Vérifié par injection**, parce qu'un test qui fige un choix doit tomber sur les
choix refusés : `profils.py` basculé par substitution textuelle sur (b) → **5
contrôles en ÉCHEC** ; basculé sur (c) → **3 contrôles en ÉCHEC**. Sans cette
vérification le test aurait pu passer sur les trois options.

**Ce qui reste ouvert, et c'est volontaire** : l'option (a) accepte que le rang d'un
titre dépende de qui est dans son bassin. La seule chose que le cycle a armée est la
veille : si un secteur lu en sectoriel porte un jour un axe sous 8, la section 25 le
nomme. Rien d'autre n'est à reprendre ici.

## C21 — Un facteur 100 dans la colonne `rendement` du BOC

- classe : ORANGE — corriger une série commitée exige la preuve à deux côtés ; le diagnostic est fait
- statut : **FAIT le 04/10/2026 (cycle 18), et le diagnostic de ce chantier était faux
  d'un facteur 40.** Ce ne sont pas 29 séances : la colonne mélangeait **deux
  conventions** depuis l'origine, 68 426 lignes en pourcentage contre 5 370 en fraction,
  et le chargeur tranchait entre elles **par la grandeur**. 68 425 lignes ramenées à la
  fraction, **1 683 valeurs corrigées en base**, toutes d'un facteur 100 exact. La passe
  autorisée est consommée ; **aucun cycle ne reprend C21.** Ce qui reste — 1 756 lignes
  qu'aucun côté ne tranche — est plafonné par la section 29. Voir *Ce qu'a trouvé le
  cycle 18*, au bas du bloc.
- validation : OK
- autonomie : complète, **sans réseau** — tout est dans `collecte/cours_quotidien_boc.csv`
- priorité : 4 — à égalité avec C18, même famille vue dans une autre colonne

**Le constat, mesuré le 01/10/2026 (cycle 12), trouvé en datant l'implicite de C17.**
C18 a trouvé des collisions d'échelle dans la colonne `cours`. Il y en a aussi dans la
colonne `rendement`, et elles ne se voient pas de la même façon : le rendement y est
multiplié par **100**, c'est-à-dire qu'un « 1,26 % » est entré comme la fraction
`1,26` au lieu de `0,0126`.

Signature retenue, volontairement étroite : une séance dont le rendement vaut 50 à
200 fois celui de la veille **et** celui du lendemain, alors que le cours bouge de
moins de 20 %. **29 séances** sur **7 titres** : ORGT 14, CFAC 3, ETIT 3, SCRC 3,
SEMC 3, NSBC 2, SPHC 1. Treize des 29 sont en 2026. Exemple, ETIT : 0,0122 le 23/07,
**1,2600** le 24/07, 0,0124 le 27/07, à cours quasi constant (75 → 73 → 74).

**Un second cas, inverse, que cette signature ne voit presque pas.** Chez **CFAC**, la
mauvaise échelle est **majoritaire** : **227 séances sur 2 019** portent un rendement
supérieur à 25 %, et sur le premier semestre 2026 ce sont les séances **courantes** qui
sont fausses (implicite ≈ 703 FCFA, soit 45 % de rendement) tandis que la **dernière
séance du mois** porte la bonne valeur (implicite 7,04). La signature ne retient là que
les 3 séances dont les deux voisines sont saines. Le compte de 29 est donc un
**plancher**, pas un total.

**Portée, dite franchement : le défaut est LATENT.** Aucune des 29 séances n'est la
**dernière** séance de son titre — vérifié titre par titre — donc aucun `dy`, aucun
`dy_axe`, aucun profil ni grade d'aujourd'hui n'en dépend ; CFAC termine à 0,0359, qui
est la bonne échelle. Ce qui en dépendra : tout backtest lisant la série entière, et
toute confrontation historique du type de celle qui a résolu C17.

**Attention — ne pas confondre avec FTSC.** FTSC porte 246 séances au-dessus de 25 %
de rendement et ce n'est **pas** un défaut : C1 a établi que sa distribution de 2025
est arithmétiquement exacte. Une règle qui écarterait tout rendement supérieur à un
seuil effacerait un fait réel. C'est la **rupture entre voisines**, pas le niveau, qui
identifie le défaut.

**Terminé quand** : chacune des séances retenues est corrigée par un script idempotent
dans `outils/` avec la preuve à deux côtés (les séances qui l'encadrent), ou motivée
une par une ; le cas CFAC est tranché dans le bon sens (c'est la majorité des séances
qu'il faut corriger, pas la minorité) ; et un test refuse une rupture d'échelle entre
deux séances voisines sans faire tomber FTSC.

### Ce qu'a trouvé le cycle 18 (04/10/2026) : la signature de ce chantier mesurait les frontières, pas le défaut

La signature de C21 — une séance dont le rendement vaut 50 à 200 fois celui de la veille
**et** celui du lendemain, à cours quasi constant — rend aujourd'hui **136** séances et
non 29. Mais elle ne mesure pas le défaut : elle mesure les **frontières** entre deux
conventions qui coexistent dans le fichier depuis l'origine. Ce n'était d'ailleurs pas
une découverte : le docstring de `_rendement_normalise`, dans
`collecte/charger_cours_quotidien.py`, l'écrit noir sur blanc depuis le 12/09/2026.
Personne n'avait compté la proportion.

**Mesure du 04/10/2026, ligne à ligne, par la preuve à deux côtés.**

| | lignes |
|---|---|
| renseignées | 75 552 |
| prouvées **POURCENTAGE** (`6.28` pour 6,28 %) | **68 426** |
| prouvées **FRACTION** (`0.0628` pour le même 6,28 %) | **5 370** |
| qu'aucun des deux côtés ne tranche | 1 756 |

Les lignes en fraction sont exactement les **101 dates mensuelles** versées par C15 plus
les **52 séances depuis le 2026-07-17**, où la collecte quotidienne P11 écrit désormais
la fraction. Tout le reste de la série est en pourcentage.

**Le défaut n'était pas dans la donnée, il était dans la façon de la lire.** Le moteur
veut une fraction — `profils.py` l'écrit sur la ligne même (`dy = dy_row[0]  # fraction
(0,056 = 5,6 %)`). Le pont arbitre entre les deux unités **par la grandeur** : au-dessus
de 1,5 on divise par cent, en dessous on ne touche à rien. C'est une estimation, que la
première règle du dépôt interdit, et elle est **mesurablement fausse sur 1 683 lignes** :
un rendement publié **sous 1,5 %** restait non divisé et entrait en base **cent fois trop
grand**. ORGT 403, NSBC 291, CFAC 211, UNXC 184, BICC 174, PALC 150, SEMC 121, SPHC 91,
SCRC 33, SLBC 17, ETIT 8.

**La preuve à deux côtés, pour chaque ligne.** Côté 1 : le **dividende que le BOC publie
lui-même**, colonne `dividende_montant` du bulletin mensuel — une seule des deux lectures
(`rendement × cours` ou `rendement / 100 × cours`) retombe à moins de 5 % de lui. Côté
2 : **les séances qui l'encadrent**, dont le dividende implicite est constant par
morceaux, tolérance 10 %, médiane des six voisines tranchées. Une ligne qu'aucun des deux
ne tranche n'est **pas** convertie.

**Livré** : `outils/normalisation_rendement_boc.py` (autotest `--test` **15 cas, 0
échec** ; rapport par défaut, `--appliquer` pour écrire). Idempotent — relancé, il
constate « normalisation DEJA APPLIQUEE ». Six gardes : entête et comptes attendus,
SHA-256 avant **et** après, conversion par **décalage décimal exact** (`Decimal` / 100,
jamais une division flottante : `2.61` devient `0.0261`, pas `0.026099999999999998`),
ancre (ticker, date) et garde `ATTENDU` sur chaque valeur avant écriture, réécriture en
texte brut avec fins de ligne CRLF conservées et **22 235 lignes intactes à l'octet**,
relecture et reclassement après écriture.

**Une ligne n'est PAS convertie, délibérément** : `STBC 2018-08-01`, **206,2 %** — le
dividende de 4 124 FCFA non réajusté après la division 1:20 du 27/07/2018 (C4). En
fraction elle vaudrait 2,062, au-delà du plafond de 1,5 du chargeur, qui la diviserait
une **seconde** fois et ferait entrer en base une valeur fausse là où il laisse
aujourd'hui une **case vide**. Une case vide vaut mieux.

**Effet mesuré, avant/après, sur la base du jour.**

| | avant | après |
|---|---|---|
| conventions dans la colonne | 2 (68 426 % / 5 370 fraction) | **1** (73 795 fraction, 1 résidu nommé) |
| valeurs de `rendement` fausses en base | **1 683**, toutes ×100 | **0** |
| valeurs perdues ou créées | — | **0** (75 551 non nulles des deux côtés) |
| champs de `collecte/profils.json` déplacés | — | **0** (fichier identique) |

Le défaut était donc bien **latent** au sens de C21 : aucune des 1 683 n'est la dernière
séance d'un titre. Il ne l'était pas pour les **trois backtests du dépôt**, qui lisent la
série entière, ni pour aucune confrontation historique.

**Le cas CFAC est tranché dans le sens que ce chantier demandait** : ce sont bien les
séances **courantes** qui étaient fausses et non la dernière du mois — 211 lignes CFAC
corrigées, et la dernière séance (0,0365) était déjà juste.

**Test : section 29 de `tester_donnees.py`, 6 contrôles**, dont le plafond à **0** sur
les lignes mal échelonnées, le plafond à **1 756** sur le résidu non tranché, et le
contrôle que C21 réclamait nommément : **FTSC n'est pas balayé**. Son rendement de 86,5 %
est réel (C1) ; le test exige qu'il reste entre 0,50 et 1,5, donc ni effacé par un seuil
de niveau ni divisé une seconde fois.

**Ce qui reste, et pourquoi la boucle s'arrête là.** 1 756 lignes ne se tranchent par
aucun des deux côtés — elles bordent les séances où le **dividende de référence change**,
et là une multiplication par cent ne se distingue pas d'un dividende qui double. Les 291
ruptures d'échelle résiduelles entre séances voisines sont exactement celles-là. Les
trancher demanderait une troisième source ; la section 29 les plafonne en attendant.

## C22 — Les 8 refus du pont BOC, un arbitrage chacun

- classe : ORANGE — chaque refus oppose deux valeurs certifiées ; la mesure est faite
- statut : **FAIT le 05/10/2026 (cycle 20)** — les 8 sont tranchés et motivés dans
  `collecte/arbitrages_pont_boc.csv` ; **2 appliqués** (SNTS, NSBC), **3 tranchés mais
  renvoyés à C34** parce que leur valeur vit dans un fichier généré, **2 refus maintenus**
  (SICC, BOABF), **1 signalé à Claudia** (ORGT, ci-dessous, c'est le seul point qui attend
  un mot). La passe autorisée est consommée ; aucun cycle ne refait l'arbitrage. Voir *Ce
  qu'a trouvé le cycle 20*, au bas du bloc.
- validation : OK
- autonomie : complète, **sans réseau** pour six d'entre eux
- priorité : 7

**Le constat, mesuré le 01/10/2026 (cycle 12).** `charger_dividendes_boc.py` refuse
d'écrire quand le couple (ticker, exercice) porte déjà autre chose. Il a refusé **8
fois**, et aucun des 8 ne se tranche sans arbitrage :

| titre | exercice | le BOC dit | la base porte | lecture |
|---|---|---|---|---|
| SICC | 1999 | 1 919,00 le 25/09/2000 | **0,0** même jour | le 0 est un marqueur d'obsolescence posé à la main — ne pas écraser |
| ORGT | 2019 | 59,52 le 17/07/2020 | **0,0** même jour | idem : « 5e année sans dividende confirmée presse 05/2026 » |
| SAFC | 2010 | 23,04 le 29/07/2011 | **576,0** même jour | facteur **25,0** — exactement le facteur des collisions SAFC de **C18** |
| SEMC | 2020 | 14,00 le 28/12/2021 | **14,4** même jour | écart 2,8 %, sous la tolérance de C1 : lequel est le net ? |
| BOABF | 2025 | 397,00 le 23/04/2026 | **397,25** même jour | la base vient d'Ecofin 03/2026, net après IRVM 12,5 % |
| BOAC | 2025 | 597,53 le 06/05/2026 | **594,53** même jour | 3,00 FCFA d'écart exactement — chiffre transposé ? |
| SNTS | 2025 | 1 740,00 le **26**/05/2026 | 1 740,00 le **25**/05/2026 | **même montant, un jour d'écart** : c'est la date qu'il faut trancher |
| NSBC | 2025 | 675,98 le 04/08/2026 | **vide**, daté du 30/06/2026 | la date de la base est celle de l'**AGO**, pas du paiement |

**Pourquoi c'est un chantier et pas du ménage.** Trois de ces lignes relèvent d'autres
chantiers et le disent : SAFC 2010 est une collision d'échelle de la famille de C18
(facteur 25, le même que SAFC 21/12/2018 et 02/01/2019) ; SEMC, BOABF et BOAC sont
exactement la question brut/net de **C2**, vue sur des montants au lieu d'un
`payout_ratio` ; NSBC est une confusion entre **date d'AGO** et **date de paiement**,
qui peut toucher d'autres lignes saisies à la main. Et SNTS montre que la clef
`(ticker, montant, date)` ne protège pas d'un doublon à un jour près.

**Portée : latente pour six, visible pour deux.** Aucun des 8 ne déplace un profil
aujourd'hui. Mais NSBC 2025 reste le **seul** montant vide de la table, et SAFC 2010
est un montant faux d'un facteur 25 affiché sur la fiche publiée.

**Terminé quand** : chacun des 8 est tranché avec son motif écrit — valeur retenue,
source, et renvoi au chantier dont il relève quand c'en est un ; les refus qui
subsistent sont motivés dans un registre que la section 24 relit ; et aucun refus
nouveau n'apparaît sans être inscrit.

### Ce qu'a trouvé le cycle 20, le 05/10/2026

**Les 8 refus sont exactement ceux que ce bloc annonçait** — vérifié en reconstruisant la
base et en relançant les cinq chargeurs : `8 refusé(s)`, aux 8 mêmes couples. Mais le
diagnostic d'origine se trompait sur la **nature** de trois d'entre eux.

**Pour SAFC 2010, SEMC 2020 et BOAC 2025, il n'y a pas deux sources qui s'opposent.** Les
deux valeurs sont **deux observations successives de la même colonne du BOC**, et elles sont
toutes les deux dans `collecte/dividendes_par_exercice.csv` — qui n'est pas une saisie mais
un fichier **généré** par `historiser_dividendes_exercice.py` depuis
`collecte/dividendes_historique.csv`, à raison d'une ligne par valeur observée.
`charger_dividendes_exercice.py` garde **la première ligne du fichier**, c'est-à-dire, ici,
celle que la BRVM a **retirée** :

| titre | retirée, en base | courante, refusée | fenêtres d'observation |
|---|---|---|---|
| SAFC 2010 | 576,00 | **23,04** | retirée le 2018-12-21 ; la courante tient depuis **7,6 ans** |
| SEMC 2020 | 14,40 | **14,00** | retirée le 2024-05-14 ; la courante tient depuis **2,4 ans** |
| BOAC 2025 | 594,53 | **597,53** | la retirée n'a vécu **qu'une séance**, le 2026-05-04 |

Le second côté sépare nettement deux des trois : l'implicite `rendement × cours` du BOC vaut
14,053 pour SEMC (**0,38 %** de 14,00 contre **2,47 %** de 14,40) et 597,1 à 598,0 pour BOAC
(**0,01 à 0,08 %** de 597,53 contre **0,44 à 0,58 %** de 594,53). SAFC ne publie aucun
rendement, mais sa série de cours divise par **le même 25** à la même séance (5 300 le 20/12,
215 le 21/12 ; médiane 6 000 en 2018 contre 335 en 2019) — la division de nominal que le
cycle 17 avait déjà établie en section 19. **Décision inscrite : la publication courante de
la BRVM fait foi sur celle qu'elle a retirée.** Non appliquée ici : écrire dans un fichier
généré serait défait à la première régénération, et la règle de chargement qui le ferait
proprement déplace **31 valeurs**, pas 3 → **C34**, mesuré.

**Appliqué, et seulement cela** (`outils/arbitrage_refus_pont_boc.py`, `--test` **25
contrôles, 0 échec** ; relancé deux fois : « DÉJÀ APPLIQUÉ », rien écrit). Les deux cas dont
l'arbitrage porte sur une **date saisie à la main**, donc sur `donnees/base/dividendes.csv` :

- **NSBC 2025** : la base portait un montant **vide** daté du **30/06/2026**, et sa propre
  note disait pourquoi (« AGO 30/06/2026 […] par action à sourcer ») — une date d'**AGO** à
  la place d'une date de paiement, et le **seul** montant vide de la table. Date corrigée en
  **2026-08-04** ; le montant **675,98** est ensuite écrit par le pont lui-même, sous sa
  garde de date identique des deux côtés. Second côté : implicite **675,0 à 676,8** sur 8
  séances, soit **0,02 à 0,15 %**. *Réserve, et elle ne ferme pas* : les 19 Md approuvés
  rapportés à 675,98 impliquent 28,1 M d'actions contre 24,7 à 26,4 M déduites du BNPA de
  référence — elle n'est donc **pas** comptée comme preuve.
- **SNTS 2025** : même montant des deux côtés, seule la date diffère. Le BOC publie le
  **26/05/2026** du 2026-05-21 au 2026-07-24, donc deux mois **après** le versement, quand la
  date du 25/05 venait d'une annonce de presse de **février**, antérieure à l'événement. Date
  alignée ; **1 740,00 inchangé**, confirmé par l'implicite (1 738,2 à 1 741,5, 0,07 à
  0,10 %). Effet second : la clef de déduplication du pont est le triplet (ticker, montant,
  date) — elle ne protégeait **pas** d'un doublon à un jour près.

**Les deux refus maintenus, motifs écrits.** **SICC 1999** : le 0 est un marqueur
d'obsolescence posé à la main, le montant du BOC date du 25/09/2000, et aucun second côté
n'existe — SICC ne publie **aucun** rendement sur ses **2 029** séances. **BOABF 2025** : la
base fait foi, parce que sa note dit « net après IRVM 12,5 % » et que **397,25 / 0,875 =
454,00 exactement** quand 397,00 / 0,875 = 453,71 ne l'est pas ; l'implicite, lui, **ne
sépare pas** les deux (0,02 à 0,09 % contre 0,01 à 0,15 %), et il faut le dire ainsi. Écart
0,06 %, aucun rang déplacé. Renvoi C2.

**Le seul point qui attend un mot de Claudia — ORGT 2019.** Le BOC divise **aujourd'hui**
par **59,52** : l'implicite vaut 59,40 à 59,64 sur les 8 dernières séances (écart **0,08 à
0,20 %**). Un dividende a donc bien été versé le 17/07/2020 **pour l'exercice 2019**, alors
que la note du marqueur — « 5e année sans dividende confirmée presse 05/2026 » — porte sur
les exercices **2020 à 2024**. Le marqueur 0 est posé sur un exercice qui a payé. Effet
latent mesuré : la section 24 compte ORGT comme « référence identifiée », mais contre le
versement **2018** (56,73, écart 4,5 % à l'implicite, sous la tolérance de 10 %) et non
contre celui que le BOC utilise. **Rien n'a été écrit** : règle 1 du dépôt. Deux issues
possibles — déplacer le marqueur sur 2020-2024 et laisser le pont écrire 59,52 sur 2019, ou
confirmer que le 0 de 2019 est voulu.

**Ce que cela ne change pas, et il faut le dire.** `collecte/profils.json` est **identique au
champ près** avant et après ce cycle : **0 champ** sur 47 titres. NSBC était déjà « référence
identifiée » via son versement 2024 (668,15, à 1,1 % de l'implicite). Le défaut était
**latent**, comme C10, C17 et C19 : armé, en attente.

**Verrouillé par la section 24**, qui relit désormais le registre dans les **deux sens** : les
refus que le pont émet sont tous inscrits (sinon ÉCHEC, avec le nom du cas), et les lignes
marquées `refus_subsiste : oui` sont toutes réellement émises (sinon le registre a dérivé).
Un `TRANCHE_APPLIQUE` dont le refus subsiste est un ÉCHEC — c'est le faux vert que la chasse
du cycle 11 cherchait. 8 contrôles neufs. Le pont émet désormais **6** refus, non 8.
`RATTACHEMENTS_CONNUS`, en section 26, est **vide** : son unique exemption était NSBC 2025,
et elle n'a plus d'objet.

## C23 — Le PER normalisé mesure la croissance, pas un pic

- classe : ORANGE — arbitrage de méthode sur une mesure publiée ; le diagnostic est fait
- statut : **FAIT le 02/10/2026** — **retrait définitif** tranché par Claudia : la mesure
  et son drapeau sont retirés du code, pas seulement de l'affichage. Les deux passes de ce
  chantier sont consommées. **Aucun cycle ne le reprend.**
- validation : OK — retrait définitif
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 2 — **une mesure fausse est publiée et lue**

**Le constat, signalé par Claudia le 01/10/2026 sur le tableau de bord publié**, et
mesuré le même jour. `per_normalise()` calcule `PER_affiché × (dernier bénéfice /
moyenne des 4 derniers)`. Le texte de la fonction dit corriger un **pic** de bénéfice.
Le rapport mesure en réalité la **croissance** : sur une série géométrique de taux g,
le dernier terme dépasse la moyenne de quatre termes d'environ **1,5 g**, sans qu'il y
ait le moindre pic.

**Mesuré sur les séries strictement croissantes — où un pic est impossible par
construction** (chiffres après les deux correctifs de sélection du 01/10) :

| titre | série des RN | PER | PER « normalisé » | surcoût | g %/an |
|---|---|---|---|---|---|
| BOAC | 20 069 → 26 075 → 32 044 → 35 540 | 12,9 | 16,2 | **+25 %** | 21,0 |
| CABC | 796 → 1 135 → 1 375 → 1 439 | 14,0 | 16,9 | **+21 %** | 21,9 |
| SHEC | 3 549 → 4 012 → 5 354 → 6 028 | 24,7 | 31,4 | **+27 %** | 19,3 |
| SNTS | 278 912 → 331 748 → 393 662 → 413 588 | 10,9 | 12,7 | **+17 %** | 14,0 |
| NSBC | 32 382 → 34 813 → 38 112 → 40 712 | 13,1 | 14,6 | **+12 %** | 7,9 |
| BICC | 16 694 → 26 226 → 36 520 | 14,9 | 20,5 | **+38 %** | 47,9 |

Le surcoût suit g, pas une irrégularité : c'est la signature de la formule, pas des
sociétés. **Le PER affiché, lui, est juste** — vérifié contre brvm.org le 01/10 : BOAN,
BICC et ABJC concordent à 0,0 %, 0,0 % et 0,3 % une fois appliquée la variation de
séance du jour.

**Trois lectures, toutes défendables, mesurées sans rien écrire.**

- **(a) laisser la moyenne** — c'est un CAPE à quatre ans, et pénaliser la croissance
  est une critique connue et assumée du CAPE ; mais à quatre ans et aux taux de
  croissance de la BRVM, la pénalité de croissance domine le signal de pic ;
- **(b) normaliser sur la TENDANCE** — rapport = dernier / valeur ajustée par
  régression log-linéaire sur la fenêtre. Mesuré : les titres monotones retombent à
  **0,93–1,02** (BOAC 1,25 → 0,96 ; CABC 1,21 → 0,93 ; BICC 1,64 → 1,02), et SPHC
  reste à 1,25, STBC passe à 0,81. **Son défaut**, mesuré lui aussi : sur un
  effondrement récent la régression extrapole l'ancienne pente, et SICC rendrait 327,
  BNBC 875 ;
- **(c) retirer l'affichage** et ne garder que le PER du BOC, qui est juste.

**Ce qui est déjà corrigé, et qui ne relève pas de cet arbitrage** — fait le
01/10/2026, voir le journal : la fenêtre n'était pas consécutive (6 titres sur 25 ;
SICC n'avait aucun exercice postérieur à 2021) et le filtre `resultat_net > 0` écartait
17 exercices déficitaires en faisant paraître le titre **moins** cher. Ces deux-là
portaient sur la sélection des exercices, pas sur la lecture du rapport.

**Terminé quand** : les trois lectures sont mesurées titre par titre sur les titres
calculables — PER normalisé avant/après, drapeaux qui basculent — le tableau est
inscrit ici, et la lecture retenue est figée par un test portant son contre-exemple.

### Fait le 02/10/2026 — l'affichage, et lui seul

Claudia a écrit `validation : OK (c) retirer l'affichage` le 02/10 à 07h53, quarante
minutes après la clôture du cycle 13 — qui avait donc raison d'exécuter C20.

Le nombre sortait à **quatre endroits de `app.py`**, et c'est pour cela qu'il a survécu à
une première lecture : la liste du plan (`**16.2 normalise**`), le `delta` de la métrique
PER, l'aide de cette métrique, et l'encadré de la fiche. Les quatre sont retirés. Le
tableau de bord publié (`generer_dashboard_html.py`) et le classeur Excel ne l'affichaient
pas : vérifié, rien à y faire.

**Le nombre reste calculé** et reste dans `collecte/profils.json` — 19 titres — parce que
c'est l'affichage qui est suspendu, pas la mesure : les trois lectures ci-dessus se
mesureront sur lui.

**Le drapeau `BENEFICE_NON_REPRESENTATIF` reste**, mais son texte perdait les deux moitiés
en même temps. Il disait « le PER affiché SOUS-ESTIME la cherté réelle du titre (comparer
au PER normalisé) » : la conclusion sur la cherté est précisément ce qui est en litige, et
le nombre auquel elle renvoyait n'est plus affiché. Il ne dit plus que ce qui est mesuré —
l'écart du dernier bénéfice à la moyenne des exercices précédents — et renvoie ici.
Effet sur `profils.json` : **4 champs `reserves`** (BICC, SLBC, SPHC, STBC), rien d'autre ;
0 profil, 0 grade, 0 gate.

**Test : 2 contrôles ajoutés à la section 7.** Le premier cherche un **formatage** de
`per_norm` dans `app.py` et dans `dashboard/*.py` — pas une mention, sinon les commentaires
de ce chantier le déclencheraient — et le second exige que le nombre reste calculé.
Vérifié par **injection** : réintroduire `bits.append(f"**{r.per_norm:.1f} normalise**")`
fait tomber le premier en ÉCHEC. La colonne `per_norm` reste dans le DataFrame de
`app.py` : sans ce contrôle, un affichage se réintroduit sans qu'on y pense.

**Ce qui reste à trancher est tout le reste** : (a) la moyenne, (b) la tendance, (c) le
retrait définitif. L'affichage est suspendu, pas supprimé du code.

### Fait le 02/10/2026 — retrait définitif

Claudia a tranché : non pas (a) la moyenne, non pas (b) la tendance, mais le **retrait
définitif**. Ce n'est donc plus l'affichage qui est suspendu, c'est la mesure qui
disparaît.

**Retiré de `moteur/profils.py`** : la fonction `per_normalise()` (93 lignes), son appel,
les trois champs `per_normalise`, `ecart_benefice`, `n_ex_normalise` de la sortie JSON, et
le seuil `ecart_benefice_max` devenu sans objet (paramètre, argument, valeur par défaut).
**Retiré de `app.py`** : les deux colonnes du DataFrame et les trois derniers points
d'affichage. À la place, un bloc de **procès-verbal** dans `profils.py` qui dit pourquoi la
mesure n'existe plus, avec le tableau des cinq titres monotones, les trois lectures
mesurées, et une consigne explicite de ne pas la reconstruire sous un autre nom sans
résoudre d'abord ce que ni (a) ni (b) ne résolvent.

**Le drapeau `BENEFICE_NON_REPRESENTATIF` est parti avec**, et c'était inévitable : il se
déclenchait sur le **même rapport** (`écart > ecart_benefice_max`) et portait donc le même
défaut — il retenait BICC et SLBC, qui croissent sans pic. Son texte avait déjà été amputé
le matin même de sa conclusion sur la cherté ; il ne restait qu'un constat sans portée.

**Effet mesuré, titre par titre, avant/après sur les 47 :**

| | avant | après |
|---|---|---|
| titres portant `per_normalise` | 19 | **0** |
| titres portant `ecart_benefice` | 19 | **0** |
| titres portant `n_ex_normalise` | 47 | **0** |
| titres portant le drapeau | 4 | **0** |
| `profil`, `secondaire`, `grade`, `gate` | — | **0, 0, 0, 0** |

**Aucun grade ne monte, et ce n'est pas un hasard.** Le drapeau bloquait le grade A
(`grade_confiance` teste l'ensemble des drapeaux). Les quatre titres concernés en portent
d'autres qui bloquaient déjà : BICC `RATTRAPAGE`, SLBC `PIC_YOY` + `CAP_60` +
`RATTRAPAGE`, SPHC `PIC_YOY`, STBC quatre autres. Vérifié après coup : B, B, B, C
inchangés.

**Une conséquence visible à dire** : dans les tableaux des cadrans, **SPHC** perd son seul
signal et sa cellule devient vide. BICC et SLBC gardent « croissance de rattrapage ».

**Test : section 7 réécrite, 4 contrôles**, qui gardent le retrait **des deux côtés** — le
code ne porte plus la mesure (`def per_normalise(`, l'émission du drapeau), et le fichier
publié ne porte plus ses champs. Un seul des deux ne suffirait pas : une fonction
rebranchée sans champ exposé, ou un champ réintroduit depuis ailleurs, passeraient l'autre.
**Vérifié par injection** : en remettant une `per_normalise()` fictive et l'émission du
drapeau, 2 contrôles tombent en ÉCHEC.

**Non touchés, et volontairement** : `outils/branchement_agregateur.py` et
`outils/lot2_referentiels_et_interimaires.py` nomment encore le drapeau. Ce sont des
procès-verbaux exécutables de migrations déjà appliquées, à usage unique et portant leur
garde « déjà appliqué » — les réécrire falsifierait l'archive.


## C24 — Douze avis de dividende nomment leur société et ne sont rattachés à rien

- classe : ORANGE — un mauvais rattachement est pire que pas de rattachement, et le
  piège est démontré ci-dessous ; le diagnostic et l'effet sont mesurés
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau** — tout est dans `collecte/avis_brvm.csv`
- priorité : 5

**Le constat, mesuré le 02/10/2026 (cycle 13) par la chasse du matin.** Sur les
**47** avis de type `DIVIDENDE`/`DIVIDENDE_EXCEPTIONNEL` du corpus, **19 ne portent
aucun ticker**. Sept d'entre eux sont le générique « Avis : Calendrier de paiement de
dividendes », qui ne nomme aucune société : ceux-là sont correctement non rattachés et
ne sont pas le sujet. Les **douze autres nomment leur société en clair** et le
résolveur `ticker_depuis()` les manque tous les douze :

| titre de l'avis | base | ce qui bloque |
|---|---|---|
| `nei ceda ci` | NEI-CEDA CI (NEIC) | le **trait d'union** : `reduire()` ne l'enlève pas |
| `cfao motors ci` | CFAO Mobility CI (CFAC) | **changement de dénomination** (Motors → Mobility) |
| `biic bn` ×2 | BIIC Benin (BICB) | pays **abrégé** en code ISO |
| `eti tg` ×2 | Ecobank Transnational… Togo (ETIT) | **sigle** + code pays |
| `sib ci` | Société Ivoirienne de Banque (SIBC) | **sigle** |
| `bicici` | BICI CI (BICC) | une **espace** de différence |
| `boam` | BOA Mali (BOAM) | sigle collé au code pays |
| `boa sn` | BOA Senegal (BOAS) | pays abrégé |
| `boab` | BOA Benin (BOAB) | sigle collé — **et préfixe de BOABF** |
| `boa bf` | BOA Burkina Faso (BOABF) | pays abrégé |

**Pourquoi c'est un chantier et pas du ménage.** Un avis sans ticker ne corrobore
rien : il ne peut ni dater une suspension, ni confirmer un fractionnement, ni servir
de second côté à un rattachement d'exercice. Et l'effet est **mesuré** : les douze
nomment tous leur exercice en clair, et confrontés à la table `dividendes` avec le
rattachement lu ci-dessus ils donnent **12 concordants, 0 divergent, 0 absent** — ils
corroboreraient donc douze rattachements de plus, faisant passer le côté indépendant
de la section 26 de **15 à 27** avis. Deux d'entre eux portent sur **NEIC ex.2025 et
CFAC ex.2025**, soit exactement les deux titres de **C5** : l'avis date le paiement du
dividende (27/08 et 30/07/2026) et la table le porte déjà — ce qui manque à C5, c'est
le document d'états financiers, pas le dividende.

**Pourquoi ORANGE, et le piège est dans la liste.** `ticker_depuis()` refuse
explicitement de devenir : « un mauvais rattachement poserait une suspension sur le
mauvais titre, ce qui serait pire que de n'avoir rien collecté ». La liste ci-dessus
le prouve : **`boab` est un préfixe de `boabf`**, et `boa bf` contient `boa b`. Toute
règle par préfixe ou par sous-chaîne rattacherait BOA Burkina à BOA Benin. C10 avait
déjà tranché la même question dans l'autre sens — liste blanche exacte, pas de
correspondance par préfixe. C'est cette méthode-là qu'il faut, et c'est elle qui
demande un arbitrage : écrire douze alias exacts à la main, ou ajouter au résolveur
une table ticker↔(sigle, code pays) construite depuis `societes`.

**Terminé quand** : les douze avis portent leur ticker par une correspondance
**exacte** (jamais par préfixe), un contre-exemple `boab`/`boabf` est figé par un
test, le plafond `AVIS_DIVIDENDE_SANS_TICKER_MAX` de la section 26 descend de 19 à 7,
et l'autotest de `collecte/avis_brvm.py` porte les cas de la liste.


## C25 — Confronter le bulletin PDF à la page « Volumes / Valeurs », source contre source

- classe : ORANGE — ouvre une seconde source de données certifiées ; le diagnostic est fait
- statut : **FAIT le 02/10/2026 (cycle 14)** — relevé, workflow et confrontation livrés ;
  voir *Fait le 02/10/2026* en bas de ce bloc. **La passe autorisée est consommée, aucun
  cycle ne le reprend.** Ce que la page ne permet pas est passé à **C27**.
- validation : OK
- autonomie : partielle — **la page est hors de portée du bac à sable**, il faut un workflow
- priorité : 3

**D'où vient ce chantier.** Claudia, le 01/10/2026, en signalant les PER du tableau de
bord : « mettre en place un système automatisé permettant de récupérer périodiquement
les PER de tous les titres cotés chaque fois qu'ils sont actualisés sur les sites de la
BRVM ». Vérifié le jour même : **ce n'est pas un défaut de collecte**. `boc_quotidien.yml`
tourne deux fois par jour du lundi au vendredi (18h et 21h UTC, le second passage
rattrapant le différé de publication), la table porte **79 206 PER**, et les dix-sept
dernières séances ouvrées en portent chacune 43 sans un seul trou. Un second collecteur
de PER ne ramènerait rien de neuf.

**Ce qui a de la valeur, en revanche, c'est que ce soit une AUTRE source.** Tout ce que
nous savons des cours, du PER et du rendement vient d'**un seul document**, le bulletin
officiel en PDF, lu par **un seul analyseur**, `extracteur_boc.py`. La page
`brvm.org/fr/volumes/0` publie les mêmes nombres en **HTML**, mise à jour à 19h30, par
une autre chaîne. Une divergence entre les deux ne peut venir que de l'une des deux, et
c'est exactement la **preuve à deux côtés** que la doctrine du dépôt exige — celle qui a
résolu C17 le 01/10, en confrontant deux colonnes du même bulletin.

**Ce que la confrontation couvrirait, mesuré sur la base du jour** : `cours` (47 titres,
90 469 lignes), `per` (43 titres, 79 206), `rendement` (43 titres, 75 551), et les
volumes échangés contre `liquidite_quotidienne` (73 141 lignes).

**Ce qu'elle trancherait tout de suite.** **C21** — le facteur 100 dans la colonne
`rendement` — se lit aujourd'hui par la seule rupture entre séances voisines, méthode qui
ne distingue pas FTSC (247 séances au-dessus de 25 %, et c'est un fait réel) d'ORGT (403,
et c'est une erreur d'échelle). Une seconde source tranche chaque séance au lieu de
raisonner sur la forme de la série. Elle armerait aussi un contrôle que rien ne fait :
**aujourd'hui, une erreur d'extraction du PDF est invisible** tant qu'elle ne produit pas
une valeur absurde.

**Ce qu'elle ne ferait PAS, et qu'il faut écrire pour que personne ne s'y trompe.** Elle
ne corrige rien de ce que Claudia a signalé : le PER affiché était déjà juste — vérifié
contre le site, BOAN et BICC à **0,0 %** une fois appliquée la variation de séance du
jour, ABJC à 0,3 % — et le PER normalisé est un calcul qui nous appartient, fait à partir
de `etats_financiers`. Aucune collecte supplémentaire ne l'aurait touché. **C'est C23.**

**Ce qu'il faut faire.** Un workflow quotidien, après `boc_quotidien.yml`, qui relève la
page, écrit son relevé dans un CSV commité horodaté — jamais dans les tables existantes —
et une section de `tester_donnees.py` qui confronte les deux sources séance par séance et
**nomme** chaque divergence. Ne jamais corriger automatiquement sur la foi de la page :
une divergence est un signalement, et c'est l'inspection qui dit laquelle des deux a tort.

**Attention, trois pièges mesurés.** (1) La page porte l'**intraday** : à 19h30 elle peut
publier une séance que le bulletin n'a pas encore arrêtée — confronter sur la **date**, pas
sur « le dernier des deux », sans quoi la confrontation comparera deux jours différents,
l'erreur exacte que C15 a dû défaire. (2) Les deux sources arrondissent peut-être
différemment : mesurer la granularité publiée de chaque côté **avant** de fixer le moindre
seuil. (3) Un analyseur HTML casse à la première refonte du site, en silence : il doit
**échouer bruyamment** sur une page dont il ne reconnaît pas la structure, jamais rendre
une table vide — c'est le faux vert que la section 19 portait avant C15.

**Terminé quand** : le relevé quotidien existe et s'alimente, la confrontation porte sur
plus de 40 titres et nomme ses divergences, le plancher de titres confrontés est figé par
un test qui ne peut que monter, et un relevé illisible fait échouer le workflow au lieu de
rendre une table vide.

### Fait le 02/10/2026 (cycle 14)

**Trois faits mesurés sur la page réelle contredisent le texte de ce chantier.** Deux
déclenchements du workflow (runs 37070740659 et 37070996821), page à **HTTP 200, 53 773
octets**, **cinq tables** : Top 5, Flop 5, *Activités du marché*, la cote, synthèse.

1. **La page ne publie PAS le cours de la cote.** Les colonnes de la table de la cote sont
   « Code obligation » (en fait le ticker), Nom, Nombre de titres échangés, Valeur échangée,
   **PER**, Pourcentage de la valeur globale échangée. Seuls les dix titres du Top 5 et du
   Flop 5 portent un cours. La confrontation des **90 469 cours** annoncée par ce chantier
   **n'est pas possible par cette page**.
2. **Elle ne publie pas le rendement non plus.** Donc **C21 ne peut pas être tranché par
   elle** : ce que ce bloc annonçait comme « ce qu'elle trancherait tout de suite » est faux.
3. **Elle ne publie aucune date.** Vérifié dans le texte rendu **et** dans le HTML brut,
   attributs et scripts compris. `<title>` et `<h1>` disent « Volumes / Valeurs », rien de plus.

**Ce qu'elle publie, et qui vaut le chantier : le PER des 48 titres**, à deux décimales —
exactement la mesure que Claudia signalait le 01/10. Granularité mesurée **des deux côtés
avant tout seuil** : page 43 valeurs à 2 décimales et 1 à 1 décimale ; bulletin 71 020 à 2
décimales et 8 186 à 1 sur 79 206. D'où `TOLERANCE_PER = 0,005`, la moitié du dernier rang
publié, et non un seuil choisi.

**La date de séance n'est pas supposée, elle est prouvée.** `date_seance` reste **vide** et
`date_seance_source` dit « absente de la page » : stamper la date du jour aurait été une
estimation pour combler un trou. L'ancrage est **à deux côtés et indépendant du PER
confronté** — les trois indices. Mesure du 02/10 à 22h16 UTC : page **BRVM-C 546,78** avec
**variation veille −0,41 %**, bulletin de la séance du 01/10 **composite 549,02**. La veille
implicite de la page vaut **549,031**, soit **0,0020 %** du composite du bulletin : la page
montre donc la séance **suivante**, et elle le prouve sans passer par le PER.

**Pourquoi l'ancrage n'est pas une précaution de style.** Confronter ce relevé au bulletin
de la séance **voisine** du 01/10 donne **21 divergences sur 43 paires** au-delà de la
tolérance ; au bulletin du 30/09, **35 sur 43**. Confronter « le dernier des deux » ne
produirait donc pas du bruit : il **nommerait 21 fausses erreurs d'extraction**. C'est
l'erreur exacte que C15 a dû défaire, et c'est le contre-exemple figé par le test.

**Livré** : `pipeline/collecte_volumes.py`, `.github/workflows/volumes_quotidien.yml` (19h45
et 21h30 UTC du lundi au vendredi, groupe `donnees-brvm`), `collecte/releve_volumes.csv`
(48 lignes) et `collecte/releve_volumes_marche.csv` (10 totaux, dont la valeur des
transactions du jour et les trois indices), **section 27 de `tester_donnees.py`, 7
contrôles**. Le relevé n'écrit dans aucune table existante et ne corrige rien : une
divergence est un **signalement**.

**Vérifié par injection**, parce qu'un test qui garde un ancrage doit tomber quand on le
contourne : relevé vidé → **1 bloquant** ; date de séance stampée sur 3 lignes → **1
bloquant** ; indices forcés à ceux du bulletin, donc séance faussement établie → **1
bloquant nommant les 21 divergences**. Les trois fichiers restaurés à l'identique après
chaque injection. Sans la troisième, la confrontation aurait pu n'être qu'un ornement.

**État au soir du 02/10 : la confrontation ne confronte encore rien, et c'est voulu.** Le
bulletin de la séance du 02/10 n'est pas collecté (le plus récent en base est le 01/10) :
la section le dit en **alerte**, nomme la séance du relevé, et **ne confronte rien**. Le
premier verdict tombera au prochain passage de `boc_quotidien.yml`.

## C26 — La collecte des publications intermédiaires : 3 lignes pour 47 titres

- classe : ORANGE — saisie d'exercices intermédiaires certifiés ; le diagnostic est fait
- statut : **PREMIÈRE PASSE FAITE le 03/10/2026 (cycle 16) — la passe autorisée est
  consommée, aucun cycle ne la refait.** Verdict : **0 ligne versable sur 139**, chacune
  refusée avec son motif par `outils/versement_intermediaires.py`, relançable en une
  commande. Rien n'a été écrit dans `donnees/base/`. Le plancher du PER glissant est posé
  dans la barrière (section 28, `TITRES_PER_GLISSANT_MIN = 1`). Ce qui reste est une
  **réextraction**, pas un versement : voir *La première passe* en bas de ce bloc, et le
  nouveau **C29** pour le rattachement des lignes.
- validation : OK
- autonomie : partielle — première passe **sans réseau** sur le corpus déjà collecté
- priorité : 3

**D'où vient ce chantier.** Claudia a demandé le 02/10/2026 un **PER glissant (TTM)** sur
le tableau de bord. Il est construit et branché le jour même. Mais il ne s'affiche que sur
**1 titre sur 47**, et ce qui le limite n'est pas le calcul : c'est la collecte.

**Ce que la base porte aujourd'hui.** `resultats_intermediaires` compte **3 lignes, pour
2 titres** : BOAC (T1 2026) et SGBC (T1 et T2 2026). Sur ces deux-là :

- **BOAC** donne un PER glissant de **12,89** contre 12,93 au bulletin, référence vérifiée
  à **0,00 %** par le rapport des paliers du BPA implicite ;
- **SGBC** est **refusé**, non pas faute d'intermédiaire mais parce que nos exercices
  **2022, 2023 et 2024 manquent** : le rapport des paliers n'a rien à confronter. C'est la
  même lacune que C5 et C6, vue par une troisième porte.

**Le gisement existe, et il n'est pas exploitable en l'état.**
`collecte/fondamentaux_extraits.csv` porte **260 lignes**, dont **138 tirées d'un rapport
trimestriel ou semestriel**, sur **32 titres**. Mais : **94 de ces 138 n'ont aucun
exercice**, **254 des 260 sont `PROBABLE`** et jamais validées, et les unités sont
visiblement incohérentes — BOABF y porte `RN = 20,0` à côté de `RN_n1 = 9 043,0`, SHEC un
résultat en unités là où la base est en millions. Le charger tel quel violerait les deux
premières règles du dépôt. **Ce n'est donc pas un pont manquant comme C17 : c'est une
extraction à reprendre.**

**Pourquoi cela vaut le travail, et c'est mesurable.** Le moteur lit des exercices
**clos**, donc le passé. Les deux seules publications intermédiaires en base ont déjà
contredit les deux profils bancaires les mieux notés : SGBC affichait +15,9 %/an et son
premier semestre 2026 ressort à **+0,6 %** ; BOAC affichait +21 %/an certifiés et son
premier trimestre à **+0,91 %**. Chaque titre dont l'intermédiaire manque est un profil
qui peut dire la même chose sans que rien ne le signale.

**Ce qu'il faut faire.** Première passe **sans réseau** : reprendre les 138 lignes
d'extraction intermédiaire, en retenir celles dont l'exercice, la période et l'unité sont
déterminables **sans deviner**, et les verser dans `donnees/base/resultats_intermediaires.csv`
avec leur source. Ce qui reste indéterminable après cela justifie seul un passage par
`extraction_etats.yml`.

**Attention, deux pièges mesurés.** (1) Les lignes trimestrielles portent **un trimestre
chacune**, pas un cumul — vérifié sur SGBC, dont la note écrit « cumul du semestre : 53,4 »
pour T1 24,0 + T2 29,4. Une ligne semestrielle, elle, porte déjà le cumul : les mélanger
compte deux fois les mêmes mois, et `benefice_glissant()` refuse pour cette raison.
(2) `resultat_net_n1` est **lu dans le document**, jamais reconstruit ; une ligne sans lui
ne sert à rien pour le glissant, puisque c'est la soustraction qui fait la fenêtre.

**Terminé quand** : chaque ligne versée porte son exercice, sa période, son unité et sa
source ; le nombre de titres à PER glissant calculable est figé par un test qui ne peut que
monter ; et ce qui n'a pas pu être versé est écarté avec un motif daté.

**Ajouté le 02/10/2026 (hors cycle), et cela change la portée de C26.** Le PER glissant
est désormais le **PER d'analyse** quand il existe (`per_analyse`, `per_source` dans
`profils.json`) : axe de décote, PEGY, périmètre analysable et médianes le lisent avant le
PER du BOC. Chaque ligne intermédiaire versée peut donc **déplacer des rangs, des profils
et des grades**, et plus seulement remplir une case. Le cycle qui exécute C26 doit mesurer
et publier cet effet titre par titre (avant/après sur `profils.json`), comme C16 et C20.

### La première passe, faite le 03/10/2026 (cycle 16)

`outils/versement_intermediaires.py` — procès-verbal exécutable, autotest `--test` (**18
cas, 0 échec**), rapport par défaut, `--verser` pour écrire. Il examine les **139** lignes
tirées d'un rapport trimestriel ou semestriel (le texte de C26 en annonçait 138 : recompté
ce cycle, elles sont 139) et en **refuse 139**, par quatre contrôles. **Aucun fichier de
`donnees/base/` n'est touché, et `collecte/profils.json` est identique à l'octet** — l'effet
titre par titre que ce chantier demandait de mesurer est donc **nul**, parce que rien n'a
franchi les contrôles.

| motif de refus | lignes |
|---|---|
| unité non déclarée et aucune identité à fermer | **119** |
| résultat net absent de l'extraction | 12 |
| le titre nomme aussi un exercice annuel : on ne sait pas lequel a été extrait | 2 |
| rattachée à un ticker qui n'est pas la société du document | 2 |
| période ou millésime absent du titre | 2 |
| période T3 : période seule ou cumul, le titre ne le dit pas | 1 |
| le titre nomme deux périodes | 1 |

**L'exercice et la période SONT déterminables, l'unité ne l'est pas.** Le titre du document
nomme les deux premiers, et le lire n'est pas deviner : **134** lignes sur 139 livrent ainsi
leur couple (période, millésime). L'unité, elle, n'a aucune source :

- la colonne `unite` est **vide sur 138 des 139** lignes (une seule dit « milliers ») ;
- **aucun exercice n'est entièrement pavé par ses intermédiaires** — ni T1..T4, ni S1+S2,
  **0 cas** : il n'existe donc pas une seule identité « somme des intermédiaires = résultat
  annuel certifié » à fermer, la seule preuve d'unité disponible sans réseau ;
- le facteur n'est pas une propriété du ticker. Sur les **37** lignes **annuelles** du même
  fichier confrontables à une valeur certifiée, **17** tombent sur un rapport qui est une
  puissance de 10 — et elles emploient **quatre** conventions : ×1 (6 lignes), ×10³ (5),
  ×10⁶ (5), ×10⁻³ (1). Les **20 autres** ne tombent sur aucune puissance de 10 (NSBC
  0,30 / 0,73 / 0,93 / 0,91 / 0,94 ; CABC 890 721 et 1 184 079 ; SPHC 584 398 ; STBC
  927 751 ; SNTS 0,0001 et 0,0008) : le nombre extrait n'est alors **pas** le résultat net
  du document. Un facteur lu sur une ligne ne se transporte donc pas sur une autre.

Convertir reviendrait à choisir 10^k par vraisemblance d'ordre de grandeur. C'est
l'estimation que la première règle du dépôt interdit.

**Le gisement utile est beaucoup plus petit qu'il n'y paraît, et c'est mesuré.** Le PER
glissant exige que l'exercice intermédiaire **suive immédiatement** le dernier exercice clos
en base. Le dernier clos étant 2025 partout, seules les lignes d'exercice **2026** peuvent
produire un PER glissant : il y en a **10**, sur 9 tickers — les 124 autres lignes lisibles
(2020 à 2025) sont refusées par `benefice_glissant()` même versées, avec le motif « ils ne se
suivent pas ». Le chantier ne vaut donc pas 138 lignes de gain potentiel mais **10**, dont
2 sans résultat net, 2 mal rattachées (TTLC sous TTLS, voir C29) et 6 sans unité.

**Troisième trouvaille, et elle élargit le piège que C26 avait repéré.** C26 avait vérifié
sur les T1/T2 de SGBC que les lignes trimestrielles portent **un trimestre chacune**. La
seule ligne du fichier dont l'unité soit déclarée mesure l'inverse sur un T3 : **PALC « 3ᵉ
trimestre 2024 » vaut 16 156,388 M contre un exercice 2024 certifié à 15 861,643 M**. Un
trimestre seul ne peut pas dépasser son exercice entier sans que les trois autres se soldent
en négatif ; un cumul de neuf mois, si. Au moins un document « 3ᵉ trimestre » porte donc le
cumul, et le coder `T3` ferait compter neuf mois pour trois. Le fichier en porte **44**.
Seuls `T1` et `S1` ont une lecture unique — la période et le cumul depuis l'ouverture y
coïncident ; le script refuse `T2`, `T3`, `T4` et `S2` pour cette raison.

**Terminé quand — critère révisé le 03/10/2026, l'ancien n'était pas atteignable sans
réseau.** La réextraction renseigne, pour chaque ligne intermédiaire, (1) son **unité**
telle que le document l'écrit, (2) la **nature** de la période — période seule ou cumul
depuis l'ouverture — et (3) le **ticker** de la société du document (C29) ; puis
`outils/versement_intermediaires.py --verser` verse ce qui franchit ses quatre contrôles,
`TITRES_PER_GLISSANT_MIN` est relevé d'autant, et l'effet sur `profils.json` est mesuré
titre par titre.


## C27 — La page confirme BBGC là où la base porte BBGCI, et le cours reste sans seconde source

- classe : ORANGE — renomme un ticker dans une table certifiée, et choisit une seconde source
- statut : **FAIT le 04/10/2026 (cycle 19)** — premier axe appliqué et figé par un test,
  second axe tranché : la seconde source **existe et était déjà dans le dépôt**. La passe
  autorisée est consommée ; **aucun cycle ne reprend C27.** Ce que l'application a rendu
  visible part en **C32** (la cause, chiffrée) et **C33** (le branchement de la seconde
  source). Voir *Fait le 04/10/2026* au bas de ce bloc.
- validation : OK
- autonomie : partielle — le renommage est sans réseau ; une seconde source de cours ne l'est pas
- priorité : 4

**D'où vient ce chantier.** C25 a ouvert la page « Volumes / Valeurs » et y a trouvé deux
choses qu'il n'avait pas prévues, l'une qui se règle, l'autre qui reste ouverte.

**Premier axe, mesuré et prouvé des deux côtés.** La page publie **`BBGC`** sur les 48 lignes
de la cote. `donnees/base/societes.csv` porte **`BBGCI`**, et sa propre note dit : « Ticker
*BBGCI* provisoire (non confirmé par mnémonique officiel BRVM, ISIN CI0000010609 connu) […] **À
RECONFIRMER dès qu'un avis BRVM officiel de première cotation sera publié** ». La page officielle
de la BRVM **est** cette confirmation. Le relevé l'enregistre tel quel avec `connu_en_base=non`,
et la section 27 porte le registre `TICKERS_HORS_BASE = {"BBGC"}` : un ticker hors base de plus
sera signalé, jamais silencieux. **Rien n'a été écrit** : renommer un ticker touche `societes.csv`
et tout ce qui s'y adosse, c'est un arbitrage. Effet à mesurer avant d'écrire : combien de lignes
de combien de tables portent `BBGCI`, et ce que le renommage déplace dans `profils.json`.

**Second axe, et c'est le trou que C25 laisse ouvert.** Les **90 469 cours** et les **75 551
rendements** n'ont **toujours aucune seconde source** : la page ne publie ni l'un ni l'autre pour
la cote. Une erreur d'extraction du PDF sur un cours reste donc invisible tant qu'elle ne produit
pas une valeur absurde, et **C21 (le facteur 100 dans la colonne `rendement`) ne peut pas être
tranché séance par séance** — C25 annonçait le contraire, à tort. Les dix titres du Top 5 et du
Flop 5 portent un cours : c'est une confrontation de dix lignes par séance, à peser contre les
autres pistes (`sikafinance.json`, déjà collecté ; la page de cotation par titre).

**Terminé quand** : le mnémonique officiel est tranché et, s'il change, un script de migration
idempotent le porte partout avec son effet mesuré ; et la seconde source des cours est soit
trouvée et branchée, soit écartée avec un motif daté qui dit ce qui reste non surveillé.

### Fait le 04/10/2026 (cycle 19)

**Premier axe : le mnémonique officiel est BBGC, et ce n'était pas cosmétique.** La preuve
est à deux côtés et les deux côtés sont la BRVM : l'**avis de première cotation du
25/09/2026**, déjà dans `collecte/avis_brvm.csv`, s'intitule « Résultats de première
cotation — BRIDGE BANK GROUP COTE D'IVOIRE (**BBGC**) » — c'est exactement le document que
la note de `societes.csv` attendait ; et la **page Volumes / Valeurs** relevée le 02/10/2026
publie `BBGC` sur les 48 lignes. Corroboré deux fois de plus : le bulletin officiel n° 186
du 01/10/2026 (`donnees/boc.json`) porte le symbole `BBGC`, clôture 8 800 ; et
`donnees/cote_reference.json` nomme 48 titres dont `BBGC`.

**Ce que la mesure préalable a trouvé, et que le chantier n'avait pas prévu.** Bridge Bank
est **la seule société réelle de la base sans aucun cours** : 5 exercices fondamentaux,
**0** ligne de `cours_mensuels`, **0** de `cours_quotidien_boc`, **absente de
`collecte/profils.json`**, qui n'en compte que 47. Pendant ce temps le dépôt détenait déjà,
**sous le nom `BBGC`**, 7 séances de valeur transigée dans
`collecte/historique_liquidite.json` (24/09 → 02/10/2026), une ligne de bulletin complète
dans `donnees/boc.json` et un cours de référence dans `donnees/cote_reference.json`. Les
deux moitiés du titre existaient et ne se rencontraient jamais, faute de porter le même nom.
`moteur/arbitrage.py` avait posé un pansement — `ALIAS_TICKERS = {"BBGC": "BBGCI"}` — qui
tranchait **dans le mauvais sens** : il faisait du mnémonique officiel l'alias du provisoire.

**Livré** `outils/migration_ticker_bbgci_vers_bbgc.py` (`--test` **13 contrôles, 0 échec**,
idempotent — relancé deux fois, il constate « DEJA APPLIQUEE » sans rien écrire). **13 lignes
renommées** sur quatre fichiers : `societes.csv` 1, `etats_financiers.csv` 5,
`source_urls.csv` 5, `avis_brvm.csv` 2. Six gardes : entête, nombre de lignes, empreinte
SHA-256 avant, cardinalité exacte de chaque ancre, nombre de colonnes inchangé ligne à ligne,
relecture après écriture. La note de `societes.csv` **n'est pas écrasée** — la règle du dépôt
l'interdit : la phrase d'origine reste mot pour mot et la confirmation datée est ajoutée
derrière. `ALIAS_TICKERS` passe à `{}` ; le contrôle de la section 14 est retourné.

**Non renommé, à dessein** : la ligne `"ticker": "BBGCI"` de
`collecte/fondamentaux_echecs.jsonl` porte un `nom_fichier` de **BOA Burkina Faso**. C'est
**C29**, et la renommer porterait plus loin une attribution fausse.

**Effet mesuré, avant/après, sur la base du jour.**

| | avant | après |
|---|---|---|
| lignes portant `BBGCI` dans les données | 13 | **0** |
| `societes` / `etats_financiers` sous `BBGC` | 0 / 0 | **1 / 5** |
| entrées dans `ALIAS_TICKERS` | 1 | **0** |
| titres dans `profils.json` | 47 | **47** — champs déplacés : **0** |
| titres au tableau de bord | 48 | **48** |
| `docs_site/index.html` régénéré : `BBGCI` / `BBGC` | 10 / 0 | **0 / 10** |
| `tester_donnees.py` | 252 OK, 0 ÉCHEC | **252 OK, 0 ÉCHEC** |

Le renommage ne déplace **rien** aujourd'hui, et c'est attendu : sans cours, Bridge Bank
n'entre dans aucun classement. Ce qu'il change est à venir — les deux moitiés du titre
portent enfin le même nom.

**Second axe : la seconde source de cours existe, elle est gratuite, et elle était déjà
dans le dépôt.** `donnees/boc.json` est produit par `pipeline/collecte_boc.py`, un analyseur
**différent** de `collecte/extracteur_boc.py` qui alimente `cours_quotidien_boc.csv` : deux
extractions indépendantes du **même** bulletin. Confrontées sur la séance du 01/10/2026 :
**45 tickers communs, 0 divergence de cours**. Elles ne sont pas d'accord sur *quelles
lignes existent* — `boc.json` porte `BBGC` que le CSV n'a pas, le CSV porte `SEMC` et `SICC`
que `boc.json` n'a pas (toutes deux cotées pour la dernière fois le 15/09 selon
`cote_reference.json`). C'est donc une vraie seconde source, et non la copie que C30
dénonce à la section 19. **Sa limite, dite franchement** : `donnees/boc.json` est réécrit à
chaque séance par `boc_quotidien.yml` — une séance à la fois, aucun historique. Elle ne
rattrape pas les 90 660 cours déjà en base ; elle les surveille à partir d'aujourd'hui.
Rien n'a été branché : inscrit en **C33**.

## C32 — Un univers de 47 tickers écrit en dur écarte la 48e ligne de chaque bulletin

- classe : ORANGE — ouvre l'entrée d'une série de cours certifiée à un titre qu'elle n'acceptait pas ; le diagnostic est fait
- statut : **FAIT le 07/10/2026 (cycle 21) pour l'entrée de la série ; le rattrapage des
  8 séances déjà écrites part en C37.** La passe autorisée est consommée ; aucun cycle ne
  reprend C32. Voir *Ce qu'a fait le cycle 21*, au bas du bloc.
- validation : OK
- autonomie : complète, **sans réseau** — la correction est dans le dépôt ; sa vérification demande un passage de `boc_quotidien.yml`
- priorité : 2 — **un titre coté depuis dix séances n'a aucun prix, et rien ne le dit**

**Le constat, mesuré le 04/10/2026 (cycle 19), en cherchant pourquoi BBGC n'a pas de cours.**
`collecte/extracteur_boc.py` filtre chaque bulletin par un ensemble écrit en dur :

```
# Univers des 47 actions BRVM (hors obligations/FCTC/OPCVM ...)
UNIVERS_ACTIONS = { "ABJC", "BICB", ... }   # 47 tickers, BBGC absent
```

Bridge Bank est cotée depuis le **24/09/2026** (BOC n° 181). Depuis, `cours_quotidien_boc.csv`
porte **exactement 47 lignes à chaque séance** — 24/09, 25/09, 28/09, 29/09, 30/09, 01/10 —
et **jamais `BBGC`**. La 48e ligne du bulletin est écartée **en silence**, séance après
séance. Le même bulletin, lu par l'autre analyseur, la rend sans difficulté : `donnees/boc.json`
porte `BBGC` avec clôture 8 800, volume 60 416, valeur 535 765 635.

**Pourquoi c'est un arbitrage et pas une évidence.** La liste a une raison d'être, écrite
au-dessus d'elle : des OPCVM et des obligations partagent le motif à 2–6 majuscules et ont
déjà été pris pour des actions (cas réel : FGI, SBIF). L'ouvrir sans la remplacer par un
critère plus sûr rouvre ce défaut-là. Trois voies, à peser : ajouter `BBGC` à la main (une
ligne, mais la prochaine introduction retombera dans le trou) ; dériver l'univers de
`donnees/base/societes.csv` à l'exécution (comme `moteur/calendrier.py` le fait déjà pour les
slugs) ; ou garder la liste et **signaler** tout ticker du bulletin qu'elle écarte, au lieu
de le jeter.

**Ce que la boucle ne fera pas sans un mot de Claudia** : ouvrir l'entrée de la série. Le
golden test 54 de `moteur/tester.py` **fige aujourd'hui ce zéro** (`aucune entrée
cours_mensuels pour BBGC`) ; le commentaire posé ce cycle dit qu'il devra être retourné, pas
conservé — un golden test qui fige un trou de collecte le protège au lieu de le surveiller.

**Terminé quand** : aucun ticker présent au bulletin n'est écarté sans être nommé, Bridge
Bank a ses cours depuis le 24/09/2026 ou le motif de leur absence est écrit, et un test
refuse qu'un bulletin perde une ligne en silence.

### Ce qu'a fait le cycle 21 (07/10/2026), et ce qu'il n'a pas fait

**Les trois critères de terminaison sont remplis, le deuxième par son second membre.**

- **`collecte/univers_actions.py`** — seule définition de l'univers dans le dépôt, dérivée
  de `donnees/base/societes.csv` à l'exécution, avec autotest (`--test`, **9 contrôles,
  0 échec**). La liste blanche est **conservée** — des OPCVM et des obligations du même
  document partagent le motif de ticker, FGI et SBIF l'ont déjà prouvé — mais sa source
  devient le référentiel que le dépôt tient à jour. Deux exclusions, toutes deux lisibles
  dans la donnée : le motif du BOC, et le préfixe `[SYNTHETIQUE]` qui écarte `TEST_EXCLU`
  et `TEST_VIGIL`. Et un **refus** plutôt qu'une devinette : référentiel absent, illisible,
  sans colonne `ticker`, ou sous le plancher de 40 tickers → exception, jamais un ensemble
  dégradé. **48 tickers dérivés, les 47 de l'ancienne liste tous retenus.**
- **`collecte/extracteur_boc.py`** ne porte plus d'univers. Et surtout, tout candidat qui
  ressemble à un ticker de cotation et que l'univers écarte est désormais **nommé** —
  `lignes_ecartees`, plus une ligne sur stderr. La signature `extraire_boc()` reste
  compatible avec ses quatre appelants.
- **Test : section 33 de `tester_donnees.py`, 8 contrôles.** Le plus utile n'est pas
  « BBGC est dans l'univers » mais **« les 48 titres de `donnees/cote_reference.json` sont
  tous dans l'univers »** : c'est lui qui tombera, en la nommant, le jour où une 49e société
  sera cotée sans être inscrite au référentiel.
- **Golden test 54 de `moteur/tester.py` retourné, pas conservé.** Il exigeait
  `n_cours_bbgc == 0` en disant « rien collecté encore, aucun prix inventé » : il figeait un
  **trou de collecte** en le prenant pour une abstention. Ce qui est figé désormais vaut à 0
  cours comme à 400 : aucun cours BBGC n'est antérieur au 24/09/2026 **dans aucune des deux
  séries**, et aucun n'égale le prix d'offre de l'IPO (6 750 FCFA), que la note de
  `societes.csv` interdit d'utiliser comme un cours.

**Effet sur la base, mesuré : aucun, et c'était prévisible.** `collecte/profils.json` est
**identique au champ près, 0 champ sur 47** ; dashboard **48 titres**. L'univers s'ouvre,
mais aucune ligne BBGC n'existe encore dans `cours_quotidien_boc.csv` : la correction porte
sur les séances **à venir**.

**Ce que la correction du code ne répare pas, dit franchement.** Les **8 séances** du
24/09 au 06/10 (24, 25, 28, 29, 30/09, 01, 05, 06/10) sont déjà écrites à 47 lignes, et
`collecte_boc_quotidien.py` **saute toute séance déjà en base** (`seances_deja_en_base()`) ;
`backfill_boc_quotidien.py` fait de même (`iso in deja_en_base`). Aucun des deux ne les
retentera. Leur rattrapage demande une **réextraction ciblée** des 8 bulletins, donc du
réseau, donc un workflow : c'est **C37**. Les 8 dates sont **nommées** dans
`SEANCES_SANS_BBGC_CONNUES` (section 33), et le contrôle exige **zéro séance nouvelle** hors
de cette liste — une 9e tombe immédiatement.

## C33 — Brancher la seconde extraction du bulletin comme contrôle de la première

- classe : ORANGE — décide laquelle des deux extractions fait foi en cas de divergence ; la mesure est faite
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau** pour la première passe
- priorité : 3

**Ce que C27 a trouvé le 04/10/2026.** Le dépôt lit chaque bulletin **deux fois**, avec deux
analyseurs écrits séparément : `pipeline/collecte_boc.py` → `donnees/boc.json`, et
`collecte/extracteur_boc.py` → `collecte/cours_quotidien_boc.csv`. Personne ne les a jamais
confrontés. Mesure de la séance du 01/10/2026 : **45 tickers communs, 0 divergence de cours**,
et un désaccord sur trois lignes (`BBGC` d'un côté, `SEMC` et `SICC` de l'autre).

**Pourquoi cela compte.** C25 puis C27 concluaient que les 90 660 cours n'ont aucune seconde
source — la page « Volumes / Valeurs » ne publie pas les cours de la cote. C'était vrai de
*cette* source-là, et faux du dépôt : la seconde extraction existe depuis toujours, et elle
est gratuite. C'est aussi la réponse à **C30**, qui montre que la section 19 confronte une
copie à sa source : celle-ci confronte deux lectures indépendantes du même PDF.

**Sa limite, à dire avant de la brancher.** `donnees/boc.json` est écrasé à chaque séance :
une séance à la fois, aucun historique. Le contrôle ne vaut que pour la séance du jour, et il
ne dit rien des 90 660 cours déjà en base. L'arbitrage porte sur ce qu'on fait d'une
divergence : signalement seul, ou refus de charger.

**Terminé quand** : chaque séance est confrontée entre les deux extractions, une divergence
de cours est signalée et nommée, un désaccord sur les lignes présentes l'est aussi, et le
plafond est figé dans `tester_donnees.py`.

## C28 — Cinq fichiers dérivés commités que leur propre générateur ne reproduit pas

- classe : ORANGE — l'un d'eux écrase un fichier commité par un faux rapport complet, et
  choisir ce que chacun doit rendre est un arbitrage ; le diagnostic et l'effet sont mesurés
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 3

**Le constat, mesuré le 03/10/2026 (cycle 15) par la chasse du matin.** Le dépôt commite des
fichiers **dérivés** : produits par un script à partir d'autres fichiers du dépôt ou de la
base. Rien ne vérifie qu'un de ces fichiers est encore ce que son générateur rend. Les **cinq**
générateurs hors réseau ont été relancés dans une copie jetable et leur sortie comparée à
l'octet au fichier commité. **Deux reproduisent** — `docs/data_brvm.json` et
`collecte/arbitrage_croissance.csv`, identiques à l'octet. **Trois ne reproduisent pas, et
pour trois causes différentes :**

| fichier | commité | régénéré | cause |
|---|---|---|---|
| `collecte/a_reteleverser.json` | **148** entrées | **2 908** entrées | le générateur ne distingue pas « asset absent » de « je n'ai pas pu demander » |
| `collecte/dividendes_par_exercice.csv` | 364 lignes, LF | 365 lignes, **CRLF** | doublons, FTSC 2016, et terminaison de ligne — **C19** |
| `collecte/continuite_suspecte.jsonl` | 75 lignes | 81 lignes | le fichier commité est **antérieur à C15** |

**Le premier est le seul des trois qui soit armé, et il est grave.**
`collecte/verifier_releases.py::assets_du_tag()` rend `None` dès que `gh release view` sort en
non-zéro — binaire absent, jeton sans droit, limite d'API, tag renommé — et l'appelant traite
ce `None` comme « release introuvable », donc inscrit **toutes** les lignes du tag en
`"asset absent"`, avec le **même libellé** que les vrais manquants. Mesuré ce cycle : `gh` sort
en erreur dans le bac à sable, et le fichier régénéré porte alors les **2 908** lignes de
`MANIFESTE.csv` sur ses **26** tags, contre 148 manquants réels, soit **38 654 → 868 318
octets**. Ce n'est pas théorique : `.github/workflows/reparation.yml` lance ce script avec
`if: always()` **et committe `collecte/a_reteleverser.json`** à l'étape suivante ;
`collecte.yml` fait de même. Un seul échec de `gh` remplace donc 148 cas réels par 2 908 faux,
poussés sur `main`. **C'est le faux vert de la section 19 d'avant C15, pris dans l'autre sens :
un outil qui ne peut pas faire son travail rend un rapport complet et confiant.**

**Le troisième est bénin et le dire franchement vaut mieux que le corriger vite.**
`continuite_suspecte.jsonl` est un rapport d'état, **lu par aucun `.py` du dépôt** (vérifié par
balayage), et l'écart vient de C15 : les 101 séances mensuelles versées dans le quotidien ont
changé la séance *précédente* de plusieurs lignes — BNBC passe de `2021-07-07 / +129,6 %` à
`2021-06-25 / +113,8 %`, BOAB de `2024-08-29 / 7 300` à `2024-08-30 / 7 500`. Le fichier
commité décrit donc une série qui n'existe plus.

**Ce qui demande un arbitrage.** Pour chacun des trois, il faut dire ce que le fichier commité
**est censé être** : la dernière sortie du générateur, ou une archive datée qu'on ne régénère
pas. Les deux se défendent et le dépôt ne l'a jamais écrit. `a_reteleverser.json` demande en
plus que `verifier_releases.py` distingue les deux cas et **échoue bruyamment** sur le second
plutôt que d'écrire un faux — c'est la seule pièce des trois qui soit du code pur, donc
VERTE si Claudia la détache.

**Ils sont cinq. Deux de plus, mesurés le 04/10/2026 (cycle 19) en passant les barrières de
C27 — et constatés AVANT toute modification, donc sans rapport avec elle.**

- **`collecte/profils.json`** : régénéré par `moteur/profils.py` sur la base reconstruite à
  neuf depuis les fichiers commités, il diffère du fichier commité sur **un titre, SEMC, deux
  champs** — le dividende de référence y vaut **14,40** quand le dépôt porte **14,00**
  (`collecte/dividendes_boc.csv`, `SEMC,14.0,2021-12-28`). Aucun champ décisionnel : ni
  profil, ni grade, ni gate ne bouge. Le cycle 18 annonçait « `profils.json` identique » ; sur
  son propre périmètre c'était vrai, mais la paire fichier/générateur, elle, ne l'est pas.
- **`docs_site/index.html`** : régénéré par `dashboard/generer_dashboard_html.py`, il passe de
  **1 160 à 1 403 lignes**, **109 blocs de différences**. Le fichier commité est une build
  largement périmée. Le cas est bénin — `pages.yml` régénère la page à chaque publication,
  donc c'est bien la version fraîche qui est publiée — mais il illustre exactement la question
  du chantier : ce fichier commité est-il une sortie, ou rien du tout ?

Aucun des deux n'a été commité régénéré par le cycle 19 : ce serait un second chantier dans
le même commit, et pour `profils.json` cela effacerait en silence un cas que ce chantier doit
trancher.

**Terminé quand** : chacun des **cinq** est soit régénéré et commité, soit déclaré archive avec
son motif daté ; `verifier_releases.py` ne peut plus écrire « asset absent » quand il n'a pas
pu interroger la release ; et une section de `tester_donnees.py` relance chaque générateur hors
réseau, exige l'égalité à l'octet, et porte un registre des paires déclarées archives — de
sorte qu'une paire neuve qui ne reproduit pas soit **bloquante** et qu'une paire du registre
qui reproduit à nouveau le soit aussi, pour que le registre ne pourrisse pas.

## C29 — Quinze extractions portent le ticker d'une autre société que celle du document

- classe : ORANGE — rattacher une extraction à un autre ticker décide de quelle société une
  valeur parle ; le diagnostic et l'effet sont mesurés
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 2 — **devant C7**, qu'il protège

**Le constat, mesuré le 03/10/2026 (cycle 16) en exécutant C26.**
`collecte/fondamentaux_extraits.csv` rattache **15 lignes à un ticker qui n'est pas la
société nommée dans l'URL de son propre document** :

| document | rattaché à | société du document | lignes |
|---|---|---|---|
| `totalenergies_marketing_ci` | **TTLS** (TotalEnergies Marketing SN) | **TTLC** (TotalEnergies Marketing CI) | **12** |
| `filtisac_ci` | LNBB (Loterie Nationale du Bénin) | FTSC (Filtisac CI) | 1 |
| `setao_ci` | LNBB (Loterie Nationale du Bénin) | STAC (Setao CI) | 1 |
| `agl_cote_divoire` | ECOC (Ecobank Côte d'Ivoire) | AGL Côte d'Ivoire, hors cote | 1 |

**Pourquoi c'est le cas le plus dangereux trouvé ce cycle.** **TTLC n'a aucune ligne à son
nom dans ce fichier** : les douze lignes de la Côte d'Ivoire y sont toutes sous le Sénégal.
Et TTLS est exactement le ticker de **C7**, « TTLS, dernier titre sans ROE », dont les
capitaux propres manquent. Un cycle qui aurait puisé dans ce fichier pour combler C7 aurait
écrit la Côte d'Ivoire dans le Sénégal — avec un `source_url` qui l'aurait dit, et que
personne ne relit.

**La base certifiée, elle, est saine — vérifié ce cycle.** Les lignes annuelles de TTLC
portent les documents CI et leurs valeurs (11 143 / 12 279 / 8 709 / 9 374 / 9 087), celles
de TTLS les documents SN. La contamination est **confinée au fichier d'extraction**, dont les
260 lignes sont `PROBABLE` et n'ont jamais été validées. **Un seul point à éclaircir** :
`TTLS 2022 = 6 559,0` est `PROBABLE` **sans source**, et c'est exactement la valeur qu'une
ligne tirée du document **CI** « 1ᵉʳ semestre 2023 » porte dans le fichier d'extraction. La
coïncidence ne prouve rien — TTLC 2022 certifié vaut 12 279, donc 6 559 n'est pas non plus le
résultat CI de cet exercice — mais elle demande le document avant qu'on s'appuie sur cette
ligne.

**Pourquoi la garde de C26 ne suffit pas, dit franchement.**
`outils/versement_intermediaires.py` lit le fichier contre lui-même : un slug de société
porté par quatorze lignes sous STAC et une seule sous LNBB désigne Setao. Cela n'attrape
qu'une erreur **isolée** — 2 des 15. La TTLC → TTLS est **systématique** : TTLS est le ticker
majoritaire de son slug, donc le majoritaire **est** l'erreur. Les attraper demande de
confronter le nom du document à `donnees/base/societes.csv`, pas au fichier lui-même.

**Ce qu'il faut faire.** Une correspondance slug de document → ticker adossée aux noms de
`societes.csv`, un script idempotent dans `outils/` qui rerattache les 15 lignes avec son
procès-verbal, un motif daté pour celle d'AGL (société hors cote : la ligne n'a pas de ticker
à recevoir), et un contrôle de barrière qui refuse qu'une extraction porte un ticker dont le
nom ne correspond pas à son document.

**Terminé quand** : chaque ligne porte le ticker de la société de son document ou est écartée
avec son motif ; `TTLS 2022` est soit sourcé, soit déclaré sans source avec son motif daté ;
et un test de `tester_donnees.py` empêche le retour du mélange.

## C30 — La confrontation des deux séries compare une copie à sa source

- classe : ORANGE — inscrire une exception nommée dans un contrôle bloquant, et dire laquelle des deux extractions fait foi, sont deux arbitrages de méthode ; le diagnostic est fait
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau**
- priorité : 3 — un contrôle bloquant qui se croit indépendant est plus dangereux qu'un contrôle absent

**Le constat, mesuré le 03/10/2026 (cycle 17) en butant dessus.** La section 19 est
présentée dans son propre en-tête comme « le premier verdict que le projet possède sur
la qualité de ses prix » : *« deux extractions indépendantes des mêmes bulletins, faites
à des dates différentes par des codes différents, donnent exactement le même cours
partout »*, **4 508 paires, 0 divergence**.

**Ces 4 508 paires sont exactement les lignes que C15 a copiées du mensuel vers le
quotidien.** Avant C15, les deux séries ne partageaient **aucune** date — 0 sur 101, le
chantier le dit lui-même. Toutes les paires communes sont donc nées de la copie, et le
script de versement **refusait déjà d'écrire sur une paire différente**. La section 19
ne confronte pas deux extractions : elle vérifie que la copie est fidèle à sa source.
C'est un contrôle utile — une régression du versement se verrait — mais ce n'est pas ce
que son en-tête affirme, et le projet s'appuie sur cette affirmation.

**La preuve par l'exemple, faite ce cycle.** C18 a prouvé que `SAFC 2018-12-31` porte
5 300, valeur d'avant la division de nominal 1:25, là où la séance vaut **215** — le
bulletin de janvier 2019 publie cours 200 et variation annuelle −6,98 %, donc clôture
2018 = 200 / (1 − 0,0698) = 215,0, et le bulletin de décembre se contredit lui-même en
portant déjà le dividende rebasé (23,04) avec un cours d'avant division. Corriger le
quotidien fait aussitôt tomber la section 19 : `4508 paires confrontées, 1 divergente —
SAFC 2018-12-31 : mensuel 5300 contre quotidien 215`. **Le contrôle interdit donc de
corriger une valeur fausse** — parce qu'il prend la copie pour une corroboration.

**Ce qu'il faut trancher, et c'est Claudia.**

1. **Laquelle des deux séries fait foi** quand elles divergent sur un bulletin dont la
   source est elle-même incohérente ? Ici le quotidien a raison, prouvé des deux côtés.
2. **Faut-il un registre nommé** `DIVERGENCES_COURS_SOURCE`, sur le modèle de
   `BPA_ANNUEL_SUR_PER_FIGE` et de `COLLISIONS_ECHELLE` — chaque exception portant sa
   preuve écrite, le plafond restant à zéro partout ailleurs — ou faut-il corriger aussi
   `cours_extraits.csv`, au risque d'écraser une transcription fidèle d'un document
   officiel ?
3. **L'en-tête de la section 19 doit dire ce qu'elle mesure vraiment** : la fidélité
   d'une copie, et non l'accord de deux lectures indépendantes. Tant qu'il affirme
   l'inverse, un cycle futur y lira une garantie qui n'existe pas.

**Les deux séances concernées, prouvées et non écrites** : `SAFC 2018-12-31` (5 300 →
215) et `SAFC 2019-01-04` (5 300 → 215). Le script existe et les porte déjà, en
`apres: None` : `outils/correction_collisions_echelle.py`. Une fois l'arbitrage rendu,
les faire passer coûte une ligne. Elles éteindront du même coup les deux dernières
fausses dates de C4 (`SAFC 2019-01-02` et `SAFC 2019-01-07`) et videront le registre
`COLLISIONS_ECHELLE`.

**Terminé quand** : la règle de préséance entre les deux séries est écrite, la section
19 dit ce qu'elle mesure, les deux séances SAFC sont corrigées ou motivées, et un test
empêche qu'une divergence nouvelle passe sans être nommée.

## C31 — Le PER du BOC bascule entre deux branches, et quatre titres portent la mauvaise

- classe : ORANGE — trancher quelle branche fait foi demande une source que la base ne porte pas, et le PER retenu déplace des rangs ; le diagnostic est fait
- statut : PROPOSÉ
- validation : —
- autonomie : partielle — la mesure est **sans réseau** ; trancher demande le nombre d'actions
- priorité : 2 — **un PER faux est publié et lu**, comme C23 l'était

**D'où vient ce chantier.** Chasse du cycle 18 (04/10/2026). Trois choses lisent le PER
du BOC : l'axe de décote, le PEG/PEGY, et le payout implicite (`rendement × PER`). Une
seule le confronte à quoi que ce soit — la section 27, et seulement sur **une** séance,
contre la page Volumes / Valeurs. Les **75 000 autres valeurs ne sont confrontées à
rien**.

**L'identité disponible sans rien ouvrir.** Le BPA implicite d'une ligne vaut
`cours / PER`, et il ne change qu'à la publication d'un résultat. Le **cours** et le
**rendement** de la même ligne servent de témoins : s'ils sont continus et que le PER
saute d'un facteur cinq, ce n'est pas le marché qui a bougé, c'est la définition du PER.

**Mesuré : 23 bascules sur 12 titres**, toutes entre mars et juillet, et plusieurs
**alternent** d'une année sur l'autre :

| titre | séances | PER avant → après | facteur |
|---|---|---|---|
| SLBC | 23→24/05/2018 | 4,60 → 29,82 | 6,5 |
| SLBC | 03→04/05/2021 | 78,20 → 5,83 | 13,4 |
| SLBC | 11→12/05/2023 | 6,43 → 116,29 | 18,1 |
| SLBC | 10→13/05/2024 | 112,57 → 9,09 | 12,4 |
| SMBC | 28→29/04/2020 | 2,71 → 371,45 | **137** |
| SMBC | 14→15/04/2021 | 550,40 → 3,62 | **152** |
| CABC | 21→22/03/2022 | 5,99 → 177,18 | 29,6 |
| BNBC | 06→07/05/2024 | 4,23 → 196,88 | 46,5 |
| SDSC | 30/07→03/08/2026 | 6,98 → 190,70 | 27,3 |

Un bénéfice n'alterne pas d'un facteur douze tous les ans ; **deux définitions du BPA,
si** — résultat net contre résultat part du groupe, ou un nombre d'actions changé d'un
côté seulement.

**Le défaut n'est pas latent, et c'est ce qui le distingue de C18 et de C21.** Le moteur
ne lit que la **dernière** valeur, et quatre titres portent aujourd'hui celle de la
branche haute, qui est le `per` publié dans `collecte/profils.json` :

| titre | PER du jour | médiane de sa propre série | rapport |
|---|---|---|---|
| BNBC | **563,92** | 10,96 | 51,5 |
| BOAN | **254,11** | 7,37 | 34,5 |
| SDSC | **202,15** | 7,32 | 27,6 |
| SICC | **139,98** | 11,80 | 11,9 |

FTSC, cinquième au compteur (60,38 contre une médiane de 9,62), est **expliqué** : C1 a
établi que son résultat 2025 s'est effondré de 18 595 M à 466 M. Les quatre autres ne le
sont pas. **UNLC porte 731,42 sans qu'aucune bascule ne soit détectée** : sa dérive est
graduelle, donc d'une autre famille — à regarder séparément.

**Pourquoi c'est un arbitrage et pas du ménage.** Trancher laquelle des deux branches
fait foi demande le **nombre d'actions**, que `societes.csv` ne porte pas : la table n'a
que ticker, nom, secteur, référentiel, pays, date d'introduction, contrôle actionnarial.
Deux voies sans réseau : le nombre d'actions implicite `résultat_net / BPA implicite`
doit être **constant d'un exercice à l'autre** hors augmentation de capital — c'est la
machinerie des paliers du BPA que C17 et C26 emploient déjà ; et la page Volumes /
Valeurs de C25 publie le PER des 48 titres, donc une seconde lecture existe pour la
séance du jour.

**Terminé quand** : chacune des 23 bascules est datée et rattachée à un fait (publication
de résultat, changement de définition, erreur d'extraction) ou écartée avec son motif ;
les quatre PER hors branche sont tranchés avec leur preuve à deux côtés ; l'effet sur
`profils.json` est mesuré titre par titre ; et le plafond de la section 30 tombe.

## C34 — Le chargeur retient la publication que la BRVM a retirée, 31 fois

- classe : ORANGE — tranche une règle de lecture et déplace 31 valeurs certifiées ; le diagnostic est fait et l'effet est mesuré
- statut : PROPOSÉ
- validation : OK
- autonomie : complète, **sans réseau** — tout est dans le dépôt
- priorité : 2 — **une règle de lecture fausse, huit valeurs décalées d'un facteur 2 à 64**

**Le constat, mesuré le 05/10/2026 (cycle 20), en exécutant C22.**
`collecte/dividendes_par_exercice.csv` n'est pas une saisie : il est **généré** par
`historiser_dividendes_exercice.py` depuis `collecte/dividendes_historique.csv`, à raison
d'**une ligne par valeur observée** dans la colonne « Dernier dividende payé » du BOC. Quand
la BRVM **révise** cette colonne — et elle le fait —, le générateur émet donc **deux** lignes
pour le même (ticker, exercice, date de paiement), et `charger_dividendes_exercice.py` garde
**la première du fichier**, sans jamais regarder `premiere_observation` ni
`derniere_observation`, les deux colonnes qui disent laquelle est courante.

**La portée, mesurée des deux côtés.** Sur **313** groupes (ticker, exercice, date), **33**
portent plusieurs montants, et dans **33 sur 33** le chargeur retient une observation
**périmée**. En base, après filtrage des lignes de confiance ELEVEE et des valeurs dont la
provenance n'est pas le fichier généré : **31 valeurs**. Huit ne sont pas des arrondis mais
des **restatements de nominal**, et le facteur le dit :

| titre | exercice | en base (retirée) | courante | facteur |
|---|---|---|---|---|
| PRSC | 2018 | 9 623,00 | 150,36 | **64,0** |
| SEMC | 2016 | 677,00 | 16,92 | **40,0** |
| SAFC | 2010 | 576,00 | 23,04 | **25,0** |
| STBC | 2016 | 4 124,00 | 206,20 | **20,0** |
| ECOC | 2017 | 1 844,00 | 368,80 | **5,0** |
| SIBC | 2017 | 945,00 | 189,00 | **5,0** |
| TTLC | 2016 | 485,00 | 97,00 | **5,0** |
| ONTBF | 2017 | 727,91 | 363,96 | **2,0** |

Les 23 autres sont des écarts sous 6 % (arrondis au franc, corrections de centimes), dont
BOAC 2025 et SEMC 2020, deux des huit refus de C22.

**L'effet sur les verdicts du jour, mesuré et non supposé.** La règle appliquée en base puis
`profils.py` relancé : `collecte/profils.json` diffère de **2 champs**, les deux du **texte**
de la réserve de SEMC (« un dividende de 14.40 » → « 14.00 »). **0 profil, 0 grade, 0 rang.**
Le défaut est **latent** — mais il est armé sur huit valeurs fausses d'un ordre de grandeur,
et la fiche publiée les affiche.

**Préalable que la section 31 vient de verrouiller.** La règle repose sur
`derniere_observation`, donc sur un relevé qui doit être à jour et bien formé. Vérifié ce
cycle : **0 chevauchement** de fenêtres, **0 fenêtre inversée**, **0 doublon exact** dans
`dividendes_historique.csv` — le relevé est sain. Mais il est **en retard de 44 séances**
(C35) : la règle doit donc lire les fenêtres, pas supposer que la dernière ligne du fichier
est la bonne.

**L'arbitrage, et c'est à Claudia.** Deux options. **(a)** le chargeur retient l'observation
**la plus récemment publiée** : une seule règle, 31 valeurs, et la base se met sur le même
nominal que la série de cours. **(b)** le générateur n'émet plus qu'une ligne par groupe, la
courante, et garde l'historique ailleurs : plus propre en aval, mais le fichier commité
change de forme et C28 le surveille. Dans les deux cas, un test fige la règle et le
procès-verbal est un script de migration.

**Terminé quand** : le chargeur ne retient plus jamais une observation retirée ; les 31
valeurs sont corrigées par un script idempotent à gardes `attendu` ; l'effet sur
`profils.json` est mesuré et publié ; un test fige la règle et interdit son retour.

## C35 — Deux relevés de collecte se sont arrêtés le même jour, il y a 44 séances

- classe : ORANGE — relancer une collecte sur quarante-quatre séances écrit dans des relevés certifiés ; le diagnostic est fait
- statut : PROPOSÉ
- validation : OK
- autonomie : **réseau nécessaire** — passe par les workflows du dépôt (`boc_quotidien.yml`, `collecte.yml`)
- priorité : 3 — latent aujourd'hui, armé dès qu'un fichier généré est régénéré

**Le constat, chasse du cycle 20, 05/10/2026.** Le dépôt surveille la fraîcheur de ce qu'il
**lit** — `cours_mensuels` contre le quotidien (section 2), `profils.json` contre la base
(section 23). Il ne surveillait pas la fraîcheur de ce qu'il **écrit**. Deux relevés commités
se sont arrêtés **le même jour**, le **2026-07-24**, et rien ne le disait :

| relevé | dernière date | retard | lignes |
|---|---|---|---|
| `collecte/dividendes_historique.csv` | 2026-07-24 | **44 séances** | 365 |
| `collecte/liquidite_quotidienne_historique.csv` | 2026-07-24 | **44 séances** | 73 141 |

Pendant ce temps `cours_quotidien_boc.csv` est allé jusqu'au **2026-10-01** (2 029 séances),
et `dividendes_boc.csv` jusqu'au bulletin du **2026-09-28**.

**Ce que cela coûte, chiffré.** `dividendes_par_exercice.csv` est **généré** depuis
`dividendes_historique.csv` : or **17 des 64** lignes de `dividendes_boc.csv` — toutes
collectées entre le 2026-07-28 et le 2026-09-28 — sont **absentes** du relevé. Une
régénération du fichier généré les perdrait **toutes les 17**, dont **NSBC 675,98 du
04/08/2026**, la valeur même que C22 vient de faire entrer en base ce cycle. Côté liquidité,
les 44 séances postérieures au 2026-07-24 sont exactement 44 des **195** séances du quotidien
sans aucune ligne de liquidité.

**Pourquoi c'est un chantier et pas une relance.** Rattraper 44 séances de la colonne
« Dernier dividende payé » demande de rejouer des bulletins passés, ce que seule la voie des
workflows atteint, et l'écriture dans un relevé qui sert de mémoire longue à deux fichiers
générés n'est pas réversible d'un `git revert` sans perdre la collecte entre-temps. Il faut
aussi décider **qui** rattrape : un backfill dédié, ou le passage quotidien rendu
idempotent sur son propre relevé.

**Déjà verrouillé.** La **section 31**, livrée par ce cycle, mesure le retard **en séances**
pour les quatre relevés commités qui portent une date, contre un registre adossé aux valeurs
observées (plafonds 60 / 60 / 30 / 10, observés 44 / 44 / 1 / 0), compte les observations non
relevées (plafond **17**, qui ne peut que descendre) et nomme le cas NSBC. 16 contrôles.

**Terminé quand** : les deux relevés suivent la dernière séance à moins de cinq séances ; les
17 observations manquantes y sont ; les plafonds de la section 31 sont abaissés d'autant ; et
la relance est portée par un workflow qu'un cycle peut déclencher.

## C36 — Quand la BRVM ne publie que l'édition anglaise du BOC, la séance est perdue

- classe : ORANGE — charger une seconde édition, au format et à la précision différents, est un arbitrage sur une donnée certifiée
- statut : PROPOSÉ
- validation : OK option (b)
- priorité : 3

**D'où vient ce chantier.** Signalement de Claudia le 05/10/2026 : le BOC du **02/10/2026**
est publié (`boc_eng_20261002.pdf`) et n'a jamais été chargé. Deux défauts, dont un seul est
réglé hors cycle le même jour :

- **Réglé (commit hors cycle du 05/10)** : `collecte_boc_quotidien.py` s'arrêtait au premier
  BOC trouvé en remontant et n'essayait que le suffixe `_2`. Il tente désormais **toutes** les
  séances ouvrées des 10 derniers jours absentes de l'historique, sous `_2`, `_1` et `_3`, et
  journalise pour chaque absence son motif — dont « ÉDITION ANGLAISE SEULE ».
- **Ouvert, c'est ce chantier** : si seule l'édition anglaise existe, la séance n'est pas
  chargée, et c'est voulu tant que Claudia n'a pas tranché.

**Pourquoi l'édition anglaise n'est pas chargée d'office.** Lue le 05/10 sur le 02/10 et
confrontée à l'édition française du 01/10 : cours et PER sont écrits en entier (SNTS 45,000
et 10.88 ; BOAC 12.89), mais le **rendement est arrondi à deux décimales de la fraction**
(SNTS **0.04**, BOAC 0.05, SGBC 0.06, contre 3,87 %, 5,20 %, 5,89 % en français). Nombres à
l'anglaise (virgule des milliers, point décimal), mois en anglais (« 26 May 26 ») :
`extracteur_boc.py` n'en lit rien aujourd'hui. Le même bulletin annonce **46** titres cotés.

**Les options.**
- **(a)** Ne rien charger : la séance reste un trou daté, signalé par le collecteur.
- **(b)** Charger **cours et PER** depuis l'édition anglaise, **rendement laissé vide** (une
  case vide vaut mieux qu'une valeur approchée), source étiquetée `BOC_ENG` ; la ligne est
  remplacée si l'édition française paraît plus tard.
- **(c)** Charger aussi le rendement arrondi. **Déconseillé** : contraire à la deuxième règle
  de ce fichier.

**Première mesure à faire** (pré-autorisée, sans écriture) : sur les 60 dernières séances,
combien n'ont qu'une édition anglaise ? Si c'est le 02/10 seul, (a) suffit peut-être.

---

## C37 — Les 8 séances de BBGC déjà écrites à 47 lignes, et personne ne les retentera

- classe : ORANGE — écrit dans une série de cours certifiée, et demande un passage réseau
- statut : PROPOSÉ
- validation : —
- autonomie : partielle — la réextraction demande brvm.org, donc un workflow
- priorité : 3 — le titre est coté depuis 8 séances et n'a toujours aucun prix en base

**D'où vient ce chantier.** C32 a rouvert l'entrée de la série le 07/10/2026 : l'univers est
désormais dérivé de `donnees/base/societes.csv` et `BBGC` y figure. Mais les 8 séances déjà
collectées restent à 47 lignes, et **les deux collecteurs les sautent par construction** —
`collecte_boc_quotidien.py` par `seances_deja_en_base()`, `backfill_boc_quotidien.py` par
`iso in deja_en_base`. La correction de C32 ne vaut donc que pour les séances à venir ; ces
huit-là resteront vides indéfiniment si rien ne les reprend nommément.

**Ce qui est mesuré, et ce qui ne l'est pas.** Les 8 dates sont nommées :
2026-09-24, 09-25, 09-28, 09-29, 09-30, 10-01, 10-05, 10-06 — chacune à exactement 47 lignes
dans `collecte/cours_quotidien_boc.csv`, aucune portant `BBGC`. Le dépôt n'archive **aucun
PDF** (`find . -name "*.pdf"` → 0) : les bulletins doivent être retéléchargés. Une valeur est
déjà connue d'une seconde source, et elle servira de témoin : `donnees/cote_reference.json`
porte `BBGC` clôture **9 650** pour la séance du **2026-10-06**.

**Pourquoi c'est un arbitrage.** Le script doit **ajouter** la 48e ligne sans toucher les 47
existantes — jamais réécrire une séance entière, sous peine de remplacer des valeurs
certifiées par une nouvelle extraction au lieu de les confronter. Et si la réextraction
rend, pour un des 47, une valeur **différente** de celle en base, c'est une divergence à
signaler, pas à écraser : deux lectures du même bulletin qui ne concordent pas est
exactement l'objet de **C33**, et le refus d'écraser est la règle 1 du dépôt.

**Ce que la boucle ne fera pas sans un mot de Claudia** : écrire dans
`cours_quotidien_boc.csv`. Ce qu'elle peut faire sans attendre, et qui est sa passe de
mesure : écrire le script de réextraction ciblée dans `outils/`, idempotent, avec sa garde
`attendu` sur chacune des 47 lignes préexistantes, et le faire tourner **en lecture seule**
par un workflow pour mesurer ce que les 8 bulletins rendent réellement.

**Terminé quand** : les 8 séances portent 48 lignes avec leur source, ou l'impossibilité de
relire un bulletin est constatée et datée ; aucune des 47 valeurs préexistantes n'est
modifiée ; toute divergence entre les deux extractions est nommée ; et
`SEANCES_SANS_BBGC_CONNUES` (section 33 de `tester_donnees.py`) se vide d'autant.

## C38 — Cinq plafonds de la barrière sont encore des cumuls, dont trois à marge nulle

- classe : VERTE — ne touche que des seuils de test et leur unité ; aucune donnée, aucune valeur certifiée
- statut : PROPOSÉ
- validation : —
- autonomie : complète, **sans réseau**
- priorité : 3

**D'où vient ce chantier : d'une panne, pas d'une idée.** Le 07/10/2026, la barrière était
**déjà rouge sur `main`** avant tout travail du cycle 21, et aucune régression ne
l'expliquait. `NON_TRANCHEES_MAX` valait 1756, posé le 04/10/2026 ; la mesure du cycle 21 l'a
retrouvé **à la ligne près** — 1756 jusqu'au 2026-10-01 inclus, plus 15 pour le 05/10 et 15
pour le 06/10. Le plafond était un **compte absolu** sur une série que la collecte allonge de
47 lignes par séance : il était condamné à rougir seul, et il l'a fait après **deux séances**.

**La famille, inventoriée le 07/10/2026.** Sur les 17 plafonds scalaires de
`tester_donnees.py`, **5 restent des cumuls**, et trois sont à **marge nulle** — une seule
séance de plus les fait crier :

| plafond | observé | plafond | marge |
|---|---|---|---|
| `RUPTURES_VOISINES_MAX` | 291 | 291 | **0** |
| `OBSERVATIONS_NON_RELEVEES_MAX` | 17 | 17 | **0** |
| `AVIS_DIVIDENDE_SANS_TICKER_MAX` | 18 | 19 | 1 |
| `FIGEMENTS_PER_MAX` | 106 | 108 | 2 |
| `FIGEMENTS_RENDEMENT_MAX` | 43 | 327 | 284 |

Les cinq sont **non bloquants**, donc ils crieront sans rien arrêter — c'est pourquoi ce
chantier est VERTE et pas urgent. Mais une alerte qui se déclenche sans motif est une alerte
qu'on apprend à ignorer, et c'est ainsi qu'on rate la vraie.

**La méthode est déjà écrite et éprouvée**, deux fois dans le cycle 21 : `NON_TRANCHEES`
est devenu un **taux par séance** (34 sur toute la série, 15 sur le régime 2026), et
`BASCULES_PER_MAX` un **registre par titre** (`BASCULES_PAR_TICKER`, 23 bascules sur 12
titres, aussi sévère que le cumul et indexé par titre au lieu du temps). La section **34**
interdit désormais qu'un plafond **bloquant** soit un cumul, et exige que tout plafond
nouveau soit classé dans `UNITE_PLAFONDS`.

**Terminé quand** : aucun des 5 ne reste un cumul — chacun est un taux, un retard ou un
registre de cas nommés —, chaque conversion est justifiée par sa mesure, et `UNITE_PLAFONDS`
ne porte plus la valeur `cumul`.

# Veille datée, hors file

- **08/10/2026 — AGE Sonatel, fractionnement.** Si elle passe, la division de
  nominal doit être enregistrée dans `operations_sur_titre.csv` le jour même.
  (C4 en compte déjà treize ; ce serait le quatorzième.)

---

# Dernier cycle

Vingt-cinq lignes au plus. L'entrée complète va dans `docs/JOURNAL.md`.

## 2026-10-07 — cycle 21 (matin)

**La barrière était DÉJÀ ROUGE sur `main` avant tout travail, sans aucune régression.**
`NON_TRANCHEES_MAX` valait 1756, posé le 04/10 ; retrouvé **à la ligne près** — 1756 jusqu'au
2026-10-01 inclus, **+15** le 05/10, **+15** le 06/10. Un compte **absolu** sur une série qui
s'allonge de 47 lignes par séance était condamné à rougir seul. Même échec sur l'arbre intact
(`git stash`). Réparé en changeant d'**unité**, pas de valeur : taux par séance, **34** sur la
série entière, **15** sur le régime 2026 — mon premier chiffre (15 partout) venait de huit
séances et **mon propre test l'a fait tomber** (max réel 34, le 2025-01-02).

**Exécuté : C32.** `collecte/univers_actions.py` (`--test` **9 contrôles, 0 échec**) dérive
l'univers de `donnees/base/societes.csv` : **48 tickers**, les 47 anciens tous retenus,
`[SYNTHETIQUE]` écartés, **refus** plutôt qu'ensemble dégradé sous 40. L'extracteur **nomme**
ce qu'il écarte. **Section 33, 8 contrôles** — le plus utile : les **48** titres de
`cote_reference.json` sont dans l'univers, et c'est lui qui nommera la 49e société non
inscrite. **Golden test 54 retourné** : il figeait un trou de collecte en le prenant pour une
abstention. **`profils.json` identique au champ près : 0 champ sur 47.** **Non réparé, et
dit** : les 8 séances déjà à 47 lignes (24→30/09, 01, 05, 06/10) — les deux collecteurs
sautent toute séance déjà en base → **C37**, dates **nommées**, pas comptées.

**Chasse : un plafond bloquant ne peut pas être un cumul. Section 34**, qui classe les **17**
plafonds du fichier. Elle a aussitôt pris `BASCULES_PER_MAX` (23 sur 23, **marge nulle**,
bloquant) → registre par titre. **5 cumuls restent**, 3 à marge nulle, tous **non bloquants**
→ **C38** (VERTE). Contre-exemple : la section 31 compte en **séances de retard**.

**Barrières** : base complète, golden tests **tous passent**, `tester_donnees.py` **290 OK,
0 ÉCHEC**, code 2 (C4, C5, section 27, relevé NSBC), `avis_brvm` et `notations --test`
passent, dashboard **48 titres**. `docs_site/index.html` régénéré **non commité** :
`pages.yml` le recopie depuis `docs/index.html` — cas de plus pour **C28**. **Prochain, par
l'ordre déterministe : C34** (ORANGE, `validation : OK`, passe non consommée, priorité 2).

## 2026-10-05 — cycle 20 (matin)

**Exécuté : C22. Les 8 refus sont bien les 8 annoncés, mais trois ne sont pas ce que le
chantier croyait : ce n'est pas deux sources qui s'opposent, c'est la BRVM contre elle-même.**
SAFC 2010, SEMC 2020 et BOAC 2025 portent **deux observations successives de la même colonne**
du BOC, toutes deux dans `dividendes_par_exercice.csv` — un fichier **généré** — et
`charger_dividendes_exercice.py` garde **la première ligne**, donc la valeur **retirée** :
576,00 depuis 7,6 ans, 14,40 depuis 2,4 ans, 594,53 après **une seule séance**. L'implicite
tranche (SEMC 0,38 % contre 2,47 % ; BOAC 0,01-0,08 % contre 0,44-0,58 %) et la série de cours
de SAFC divise par le même 25 à la même séance. Décision inscrite — 23,04 / 14,00 / 597,53 —
application renvoyée à **C34** : la règle propre déplace **31 valeurs**, dont **8 d'un facteur
2 à 64**, pour **2 champs de texte, 0 profil, 0 grade, 0 rang**.

**Appliqué, et seulement cela** (`outils/arbitrage_refus_pont_boc.py`, `--test` **25 contrôles,
0 échec** ; relancé deux fois : « DÉJÀ APPLIQUÉ »). **NSBC 2025**, seul montant vide de la
table, portait une date d'**AGO** au lieu du paiement → **04/08/2026**, et le pont a écrit
**675,98** sous sa propre garde. **SNTS 2025** : date alignée sur le BOC, montant inchangé.
**Maintenus** : SICC (marqueur manuel, **0** rendement sur 2 029 séances) et BOABF (397,25 /
0,875 = **454,00 exact**, mais l'implicite ne sépare pas). **`profils.json` identique au champ
près : 0 champ sur 47** — latent. **Attend Claudia, ORGT 2019** : le BOC divise aujourd'hui par
**59,52**, donc 2019 **a payé**, quand le marqueur 0 cite « 5e année sans dividende », qui porte
sur 2020-2024. Rien écrit : règle 1.

**Chasse : deux relevés commités se sont arrêtés le même jour, le 2026-07-24, et rien ne le
disait.** `dividendes_historique.csv` et `liquidite_quotidienne_historique.csv`, **44 séances**
de retard ; **17 des 64** lignes de `dividendes_boc.csv` absentes du relevé, dont NSBC 675,98 —
une régénération du fichier généré les perdrait. Relevé sain par ailleurs. **Section 31** → **C35**.

**Barrières** : base complète, golden tests tous passent, `tester_donnees.py` **276 OK, 0
ÉCHEC**, code 2 (C4, C5, section 28, et l'alerte NSBC voulue de la section 31), `avis_brvm
--test` et `notations --test` passent, dashboard 48 titres. Section 24 relit le registre **dans
les deux sens** ; `RATTACHEMENTS_CONNUS` est **vide**. **Proposés : C34** (priorité 2) et
**C35** (priorité 3). **Prochain : le rang 1 est vide — C3** (première `VERTE` non faite,
priorité 3), sauf si Claudia valide C32, C34 ou C35.

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

