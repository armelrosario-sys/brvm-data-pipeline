# Journal des cycles — archive

Une entrée par cycle, la plus récente en haut. **Ce fichier n'est PAS lu au
démarrage d'un cycle** : `CHANTIERS.md` porte le résumé du dernier cycle, ce qui
suffit à reprendre. On vient ici pour retrouver une mesure ancienne, vérifier ce
qu'un cycle a réellement fait, ou comprendre d'où vient une règle — jamais par
routine. Sorti de `CHANTIERS.md` le 30/09/2026 : il y pesait 13 000 tokens relus
quatre fois par jour pour rien.

Une entrée par cycle. La plus récente en haut.

## 2026-09-30 — cycle 9 (soir, 18h53 UTC)

**Contrôle anti-collision.** `git log --since="3 hours ago"` sur `main` : aucun
commit. Dernier commit `d33ac0a`, 09h18 UTC, cycle 8. Annonce poussée seule
(`b107732`) avant tout travail, puis effacée par ce commit de clôture.

**État à la reprise.** CI verte (`P4 - Golden tests`, `P5b - Publication dashboard`
et `pages` en succès sur les derniers commits de `main`). Arbre propre. Base
reconstruite par `peupler.py` et les quatre chargeurs, sans erreur : 50 sociétés,
185 lignes d'états financiers, 4 509 lignes de cours mensuels, 90 566 lignes de
cours quotidiens (47 tickers, 2 027 jours, 2018-01-02 → 2026-09-29), 73 141 lignes
de liquidité. `profils.py` rend 47 titres profilés et **ne modifie pas**
`collecte/profils.json` (arbre resté propre après exécution) — la base du jour
reproduit donc exactement l'état commité.

**Cycle du soir : pas de chasse aux défauts** (étape 5, réservée au cycle du matin).

### Exécuté : C16 — mesure des trois options de l'axe de décote

Chantier choisi par l'ordre déterministe : seul ORANGE portant `validation : OK`.
Passe de mesure pré-autorisée, **aucune écriture de donnée**.

**Méthode.** Trois variantes de `moteur/profils.py` générées par substitution
textuelle, **assertion d'unicité sur chacune des cinq ancres** (la ligne `SORTIE`,
le remplissage du bassin sectoriel `d["dy"]`, le bassin de marché `marche_dy`, et
les deux `pctl(..., v["dy"])` des branches secteur et marché). Chaque variante
écrit son `profils.json` dans le bac à sable, jamais dans le dépôt ; les trois
fichiers de variante sont supprimés dans un `finally`. Seule la lecture de l'axe de
décote change : la prime de rendement, les classements et le test du profil
RENDEMENT restent tels que C1 les a laissés.

**Garde, sans laquelle la mesure ne vaudrait rien.** La variante (a) — censée
reproduire l'état actuel — est comparée champ par champ (`decote_pctl`, `profil`,
`secondaire`, `grade`, `dy`, `dy_recurrent`, `prime_rendement`, `gate`, `drapeaux`,
`reference_axes`) au `profils.json` commité : **0 titre d'écart sur 47**. Le
harnais est donc fidèle.

**Les 6 titres drapeautés `DISTRIBUTION_NON_RECURRENTE`** : BNBC, FTSC, ORGT, SCRC,
SEMC, SIVC. Cinq PÉRIMÉ, un seul EXCEPTIONNEL (FTSC, dividende de 1 726,56 FCFA le
2025-09-30, 7,3 fois le plus fort des 5 versements précédents). **Quatre des six ne
sont pas analysables** — leur profil vient d'un fait qualitatif, ils n'ont pas de
`decote_pctl`, aucune option ne les touche. Seuls **ORGT** et **SEMC** sont sur les
axes. C'est le fait le plus important de la mesure, et il n'était pas prévu : le
chantier parlait de « 6 titres », l'arbitrage ne porte en réalité que sur deux.

| titre | motif | `dy` facial | (a) | (b) | (c) | profil/grade |
|---|---|---|---|---|---|---|
| ORGT | PÉRIMÉ 2019-07-01 | 1,98 % | 54 | 93 | 50 | `AUCUN_PROFIL`/B, → `VALUE`/B en (b) |
| SEMC | PÉRIMÉ 2021-12-28 | 0,94 % | 3 | 3 | 4 | `VIGILANCE_CONTRACTION`/C partout |
| BNBC | PÉRIMÉ 2023-07-24 | 7,54 % | — | — | — | `RETOURNEMENT`/B, hors axes |
| SCRC | PÉRIMÉ 2021-08-20 | 1,37 % | — | — | — | `RETOURNEMENT`/B, hors axes |
| SIVC | PÉRIMÉ 2017-09-29 | 26,81 % | — | — | — | `MUTATION`/B, hors axes |
| FTSC | EXCEPTIONNEL ×7,3 | 86,54 % | — | — | — | `MUTATION`/B, hors axes |

**Effet sur les 47 titres.**

| | (b) case vide | (c) zéro si périmé |
|---|---|---|
| `decote_pctl` bouge | **28 / 47** | **3 / 47** |
| amplitude hors ORGT | −1 à −3 points | +1 à +3 points |
| `profil` / `secondaire` bascule | **2** | **0** |
| `grade` bouge | **0** | **0** |
| `gate` bouge | **0** | **0** |

Détail de (b), les 28 : ABJC 47→46, BICB 43→40, BICC 36→34, BOABF 39→38, BOAC
79→78, BOAM 57→56, BOAS 75→74, CABC 56→54, CBIBF 28→26, CFAC 18→16, CIEC 16→14,
ECOC 54→52, LNBB 42→40, NSBC 58→55, NTLC 21→18, ONTBF 64→63, ORAC 24→22, **ORGT
54→93**, PALC 86→85, SDCC 28→26, SGBC 90→89, SHEC 25→23, SIBC 36→34, SLBC 69→68,
SMBC 68→66, SNTS 62→60, SPHC 89→88, TTLC 34→32. Détail de (c), les 3 : ETIT 54→57,
ORGT 54→50, SEMC 3→4.

**Quatre enseignements.**

1. **(b) déplace tout le monde vers le cher par effet de bassin.** Retirer ORGT
   (1,98 %) et SEMC (0,94 %) ôte deux valeurs basses du bassin : 26 titres perdent
   1 à 3 points de décote sans qu'aucune de leurs données n'ait changé. C'est ce
   qui produit le second basculement, **SMBC**, qui perd son secondaire `VALUE` en
   passant de 68 à 66 pour un `value_pctl_min` de 67 — un titre qui n'a aucun
   dividende périmé et que personne n'aurait pensé toucher.
2. **(c) est presque neutre** : 3 titres, aucun verdict, aucun grade.
3. **(b) récompense bien ORGT de ne rien distribuer** : 54 → 93 et un profil
   `VALUE` gagné. Ce que le texte du chantier redoutait est confirmé sur les
   chiffres du jour.
4. **Zéro n'est pas défendable pour un titre EXCEPTIONNEL.** FTSC a bel et bien
   distribué. (c) a donc été mesurée comme « zéro pour les 5 périmés, case vide
   pour l'exceptionnel ». FTSC étant hors axes, la distinction ne change rien
   aujourd'hui, mais la règle devra la porter explicitement le jour où un titre
   EXCEPTIONNEL sera analysable.

**Écarts avec la mesure du cycle 7.** Celle-ci annonçait 2 profils et 30
`decote_pctl` sur 10 titres drapeautés, dont SLBC `VALUE` → `AUCUN_PROFIL`. Sur les
6 drapeautés d'aujourd'hui, l'option (b) donne 28 `decote_pctl` et 2 profils, mais
**pas les mêmes** : ORGT (identique) et SMBC (nouveau) ; SLBC ne bascule plus, il
passe de 69 à 68. L'ancien chiffre était bien périmé, comme la note du cycle 7 bis
l'annonçait.

### Deux incohérences de `CHANTIERS.md`, trouvées en l'exécutant et corrigées

1. **Le rang 1 de l'ordre de passage bouclait.** « un ORANGE portant
   `validation : OK` passe avant tout » n'a aucune condition de sortie : C16 mesuré
   ce cycle serait resté premier du rang 1 et **chaque cycle suivant aurait refait
   la même mesure**. Clause ajoutée — le rang 1 ignore un chantier dont la ligne
   `statut` dit la passe consommée — et corollaire écrit : un cycle qui consomme une
   passe pré-autorisée doit l'inscrire sur `statut`. C16 le porte.
2. **C10 contredisait l'ordre déterministe.** Sa ligne disait « priorité : 3 —
   **avant C3** », alors que C3 porte aussi la priorité 3 et un numéro plus petit :
   la règle « à priorité égale, le plus petit numéro » faisait donc passer C3
   d'abord, l'inverse de l'intention écrite. C10 passe à **priorité 2**.

### Comptes de C10 refaits — les anciens étaient faux

Mesuré sur la base du jour, contre les chiffres du 28/09 inscrits dans le chantier :

| | inscrit (28/09) | mesuré (30/09, cycle 9) |
|---|---|---|
| lignes de `dividendes` | 326 | **311** |
| français abrégé | 296 | **296** |
| ISO | 24 | **12** |
| nulles | 6 | **3** |

Le 296 tient exactement (`charger_dividendes_exercice.py` : 296 ajoutés, 63 déjà
présents). L'écart porte sur l'apport de `donnees/base/dividendes.csv`, qui compte
15 lignes de données. Deux mesures ajoutées au chantier :

- **le défaut de tri est ACTIF, pas latent** : `ORDER BY date_paiement DESC` rend un
  autre versement que le plus récent pour **34 des 49** tickers portant au moins deux
  dividendes datés (ABJC, BNBC, BOAB, BOABF, BOAC, BOAM, BOAN, BOAS, CABC, CBIBF,
  CFAC, CIEC, ECOC, ETIT, FTSC, NEIC, NSBC, NTLC, ONTBF, PALC, PRSC, SCRC, SDSC,
  SEMC, SHEC, SIBC, SLBC, SMBC, SNTS, SOGC, SPHC, STBC, TTLC, TTLS) ;
- **la migration peut être totale** : `date_dividende()` de `profils.py` convertit
  les 311 lignes **sans une seule exception**, et **0 paire (ticker, jour) ne porte
  les deux formats** — le défaut de déduplication reste donc latent, lui.

### Barrières

**Aucune requise** : le commit ne touche que `CHANTIERS.md` et `docs/JOURNAL.md`.
Aucune donnée, aucun code. `dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés
avant le commit ; `collecte/profils.json` vérifié identique à l'état commité.

### Proposé pour le cycle suivant

**C10** (VERTE, priorité 2) — normalisation ISO de `dividendes.date_paiement` par
un script de migration idempotent dans `outils/`, normalisation à l'entrée des
chargeurs, et test refusant toute date non ISO. Diagnostic et faisabilité mesurés
ci-dessus. Aucun nouveau chantier ouvert ce cycle : les deux défauts trouvés sont
des défauts de `CHANTIERS.md` lui-même, corrigés sur place plutôt qu'inscrits.

## 2026-09-30 — révision du protocole (hors cycle)

Décidée par Claudia après le cycle 8, sur trois mesures : 5 cycles sur 8 n'avaient
rien exécuté faute de validation ; `CHANTIERS.md` pesait 23 000 tokens dont 13 000
de journal, relus 4 fois par jour et grossissant de ~1 500 tokens par cycle ;
deux sessions parallèles avaient refait le même travail les 28 et 30/09.

Quatre changements, aucun chantier exécuté, aucune barrière requise (le commit ne
touche que `CHANTIERS.md` et `docs/`) :

1. **Classes `VERTE` / `ORANGE`** sur chaque chantier. VERTE : le cycle exécute
   sans attendre. ORANGE : le cycle **mesure** sans attendre et s'arrête avant
   d'écrire. Répartition posée : 4 VERTE et 11 ORANGE parmi les 15 chantiers
   ouverts. La boucle ne reclasse jamais un ORANGE en VERTE.
2. **Journal sorti dans ce fichier**, qui ne se lit plus au démarrage.
   `CHANTIERS.md` passe de 23 254 à 11 899 tokens et cesse de grossir.
3. **Contrôle anti-collision** en étape 2 : un `git log --since="3 hours ago"`
   qui trouve une annonce sans son commit de clôture arrête la session avant
   toute reconstruction.
4. **Cadence de 4 à 2 passages par jour**, 06h53 et 18h53 UTC ; la chasse aux
   défauts n'a lieu qu'au cycle du matin.

Le détail du raisonnement est inscrit dans `CHANTIERS.md`, section *Pourquoi ce
protocole a changé* — il y est utile, ici il serait perdu.

## 2026-09-30 — cycle 8

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


### Chantier exécuté : C15

**Prémisse revérifiée avant d'agir**, sans reprendre les chiffres du journal :
`cours_extraits.csv` porte 4 509 lignes, 101 dates, 47 tickers, aucune paire
(ticker, jour) en double ; `cours_quotidien_boc.csv` en porte 86 057 sur
1 926 dates ; **dates communes : 0**. La confrontation de la section 19 était donc
bien vide — et **verte**, ce qui est le vrai danger : elle ne prouvait rien.

**Le piège des unités, trouvé avant d'écrire et non après.** Les deux fichiers
n'écrivent pas le rendement dans la même unité. Le mensuel le porte en
**pourcentage** ; le quotidien mélange les deux unités et son chargeur les
discrimine par un seuil — au-delà de 1,5 c'est un pourcentage, en dessous une
fraction. Or **105 lignes** du mensuel portent un rendement inférieur ou égal à
1,5 % (BICC, CFAC, NSBC, ORGT, PALC, SCRC, SEMC, SPHC, UNXC) : recopiées telles
quelles, elles auraient été relues **cent fois trop grandes**. Le versement
convertit donc en fraction. Reste **une** case que la fraction ne sauve pas :
**STBC au 31/07/2018, rendement 210,41 %**, soit 2,1041 en fraction, au-dessus du
plafond de 1,5 du lecteur, qui l'aurait servi à 2,10 %. Cette case part **vide** —
une case vide vaut mieux qu'une valeur approchée. Note pour C4 : ce 210 % tombe
entre les deux chutes STBC des 12 et 27/07/2018.

**`outils/versement_mensuel_vers_quotidien.py`**, idempotent, sans réseau, sur le
modèle des deux scripts déjà présents : ancres exactes, assertion d'unicité, garde
`ATTENDU` sur chaque grandeur, refus d'écrire si une paire existe déjà avec des
valeurs **différentes** (trancher une divergence n'est pas le travail d'un script
de migration), relance sans effet une fois appliqué. Une garde de plus, propre au
cas : **réserialiser le fichier existant et exiger l'octet près l'original avant
d'y ajouter quoi que ce soit**. Elle a mordu au premier essai — le fichier est en
CRLF, et une réécriture en LF aurait produit un diff de 86 057 lignes sans changer
une valeur.

**Résultat** : 4 509 lignes ajoutées, **0 ligne préexistante modifiée** (vérifié
paire par paire), fins de ligne intactes, relance sans effet. Le plafond de la
section 19 tombe de 101 à **0**, et un **plancher** de 4 508 paires confrontables
est ajouté : sans lui, vider la confrontation suffirait à rendre la section verte,
ce qu'elle était exactement avant ce chantier.

**Et le verdict que le projet attendait depuis le début : sur 4 508 paires
(ticker, jour), 0 divergence au franc.** Deux extractions indépendantes des mêmes
bulletins, écrites à des dates différentes par des codes différents, donnent
partout le même cours.

**Effet sur les sorties, mesuré champ par champ : la prévision du cycle 6 est
exacte.** 9 titres sur 47 voient un champ bouger — `comparaisons` 6, `g` 3,
`peg` 2, `motif` 1 — et **0 champ décisionnel** (`profil`, `secondaire`, `grade`,
`gate`, `drapeaux`). Répartition et grades inchangés.

**Deux conséquences non prévues, dites pour ce qu'elles sont.** L'alerte de C4
passe de 12 à **13** dates (SAFC 02/01/2019 apparaît) ; et le versement a rendu
mesurables les collisions d'échelle de C18, ci-dessous.

### Chasse : l'implicite du BOC dans le temps

**Mesure.** Sur les 52 368 séances à cours mouvant, une fois défalqué tout ce que
l'arrondi de publication explique (PER à deux décimales, rendement à quatre) :
**108 PER figés** (0,2 %) et **327 rendements figés** (0,6 %), avec des écarts de
cours non répercutés de **0,6 % à 6,8 %**. La propriété de palier ne tient donc
pas.

**Ce ne sont pas nos erreurs de transcription, et c'est C15 qui permet de le
dire.** **12** de ces cas (10 PER, 2 rendement) enjambent **deux extractions
indépendantes** — une séance venue de la collecte quotidienne, la suivante du
bulletin mensuel versé le jour même. Deux codes différents ne recopient pas la
même valeur par hasard : **c'est le BOC qui a publié la valeur figée.** Cette
confrontation était impossible il y a une heure.

**Exposition du moteur, mesurée : minime.** **Aucun** figement sur la dernière
séance — aucun profil du jour n'en dépend. Un seul des 108 tombe sur un point de
**BPA annuel** lu par `croissance_bpa_implicite` : **BOAS au 31/12/2024**, PER
figé à 6,66, pour **0,63 %** sur une borne de son CAGR. Et ce cas-là est
précisément l'un des 12 corroborés.

**Une hypothèse écartée, et c'est utile.** Les figements n'expliquent **pas** C17 :
les 13 titres dont le dividende de référence est introuvable y affichent des
écarts de −87 % à +95 %, deux ordres de grandeur au-dessus de ce qu'un rendement
figé d'une séance peut produire.

**La trouvaille que la question a déplacée : cinq collisions d'échelle.** En
plaçant la séance mensuelle du 31/12/2018 de SAFC entre les séances quotidiennes
qui l'encadrent, le versement a exposé un cours de **5 300** au milieu de cours de
**215**. En cherchant les chutes de plus de 60 % qui **reviennent** au niveau
d'avant, il y en a **cinq**, sur trois titres, jusqu'à un facteur **1 000**
(SLBC : 154 000 → 154 → 154 000 le lendemain). Une division de nominal ne revient
jamais sur ses pas. Le contrôle des divisions de la section 7 **écarte** les deux
SLBC comme « erreurs de saisie manifestes » sans les enregistrer nulle part, et
compte les trois autres **à tort** comme des divisions non documentées. Inscrit en
**C18**, et C4 corrigé en conséquence. Défaut **latent** : aucune des cinq n'est un
point de BPA annuel ni une dernière séance.

**Test : section 22**, huit contrôles. En **alerte** — les plafonds de figements
(108 et 327) et la dernière séance : une hausse vient du BOC et non du code, et la
doctrine de ce fichier ne bloque pas un commit pour un défaut de source. En
**bloquant** — qu'aucun point de BPA annuel hors registre ne repose sur un PER
figé (c'est un nombre que le moteur *calcule*), et qu'aucune collision d'échelle
hors registre n'apparaisse (un cours qui chute de 99,9 % et revient le lendemain
n'est pas un fait de marché). Plus un garde-fou de population : une mesure sur un
ensemble vide serait verte et vide.

**Contre-essais, six, tous rejetés comme prévu.** Section 19 : une séance versée
retirée → plafond dépassé **et** plancher enfoncé, les deux contrôles tombent ;
un cours modifié de 50 F sur une date versée → la divergence est nommée (SNTS
07/07/2026). Section 22 : un PER figé injecté sur la dernière séance → l'alerte le
nomme **et** le contrôle bloquant le prend, le 29/09/2026 étant aussi le point
annuel 2026 ; le même figement sur le point annuel 2023 d'un autre titre → le
bloquant seul ; une collision d'échelle neuve (SNTS divisé par 1 000) → bloquant,
facteur 1 008 nommé ; une collision inscrite qui disparaît → alerte. Base restaurée
après chacun, `git diff` vérifié.

**Barrières, toutes repassées sur base reconstruite** : `peupler.py` 50 sociétés /
185 lignes d'états ; les quatre chargeurs OK (4 509 / **90 566** / 296+63 /
73 141) ; `tester.py` **0**, tous les golden tests ; `profils.py` **0** (A=5,
B=28, C=14) ; `tester_donnees.py` **2**, **159 contrôles OK, 0 échec**, les deux
mêmes alertes de fraîcheur qu'en référence — C4, passée de 12 à 13 dates, et C5 —
aucune nouvelle ; `app.py` démarre, 4 onglets ; `avis_brvm.py --test` **0** ;
`notations.py --test` **0** ; `generer_dashboard.py` **0** (48 titres).
`dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés avant commit.

**C16 et C17 restent `OK` et non touchés.** **C18 proposé** à `EN ATTENTE`.

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
