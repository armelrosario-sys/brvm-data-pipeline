# Journal des cycles — archive

Une entrée par cycle, la plus récente en haut. **Ce fichier n'est PAS lu au
démarrage d'un cycle** : `CHANTIERS.md` porte le résumé du dernier cycle, ce qui
suffit à reprendre. On vient ici pour retrouver une mesure ancienne, vérifier ce
qu'un cycle a réellement fait, ou comprendre d'où vient une règle — jamais par
routine. Sorti de `CHANTIERS.md` le 30/09/2026 : il y pesait 13 000 tokens relus
quatre fois par jour pour rien.

Une entrée par cycle. La plus récente en haut.

## 2026-10-01 — hors cycle, signalement de Claudia : les PER normalisés

**Le signalement.** « Les PER normalisés que le tableau de bord affiche sont
incorrects. Les PER non normalisés sont plus proches de ceux retrouvés sur le site de
la BRVM. » Capture du tableau de bord et de `brvm.org/fr/volumes/0` à l'appui.

### 1. Le PER affiché est juste — vérifié

Relevé du site au 01/10/2026 19h30 contre notre dernière séance en base (2026-09-30).
Dix des seize titres relevés concordent à 2 % près ; les six autres s'expliquent
**exactement** par la séance du 01/10, que notre base n'a pas encore :

| titre | PER 30/09 en base | variation du 01/10 | PER prédit | PER du site | écart |
|---|---|---|---|---|---|
| BOAN | 269,36 | −5,66 % | 254,11 | 254,11 | **0,0 %** |
| BICC | 14,88 | +3,67 % | 15,43 | 15,43 | **0,0 %** |
| ABJC | 29,84 | −7,42 % | 27,63 | 27,71 | **0,3 %** |

Le PER brut du dépôt **est** celui de la BRVM. L'écart que Claudia voyait ne venait
donc pas de la collecte.

### 2. La collecte du PER tourne déjà, et elle est saine

Vérifié avant de répondre à sa question sur un système automatisé : `boc_quotidien.yml`
tourne **deux fois par jour** du lundi au vendredi (18h et 21h UTC, le second passage
rattrapant le différé de publication du bulletin), `collecte_boc_quotidien.yml` à 18h.
La table `cours_quotidien_boc` porte **79 163 PER**, et les **dix-sept dernières
séances ouvrées portent chacune 43 PER, sans un seul trou**. Dernière séance en base :
2026-09-30, soit J−1 au moment du signalement — normal, le bulletin du 01/10 n'est
publié qu'après 18h UTC.

### 3. Le défaut est entièrement dans notre calcul

`per_normalise()` rend `PER_affiché × (dernier RN / moyenne des 4 derniers RN)`. Trois
défauts, de nature différente.

**(a) La fenêtre n'était pas consécutive.** `ORDER BY exercice DESC LIMIT 4` prend les
quatre exercices les plus récents **disponibles**, pas les quatre dernières années. Sur
les 25 titres calculables, **6** avaient une fenêtre à trou :

| titre | fenêtre retenue | années couvertes |
|---|---|---|
| BICC | 2025, 2024, 2023, **2021** | 5 pour 4 exercices (trou de C6) |
| BNBC | 2025, **2023**, 2022, 2021 | 5 |
| BOABF | 2025, **2023**, 2022, 2021 | 5 |
| ECOC | 2025, **2023**, 2022 | 4 pour 3 |
| ORGT | 2025, **2022**, 2021 | 5 pour 3 |
| SDCC | 2025, 2024, **2021** | 5 pour 3 |

Et **SICC** n'avait aucun exercice postérieur à 2021 : son « PER normalisé » de 54,7
reposait sur les exercices **2018 à 2021**, des bénéfices vieux de quatre à sept ans,
sans que rien ne le signale au lecteur.

**(b) Le filtre `resultat_net > 0` écartait les pertes en silence, et à l'envers.**
**17 exercices déficitaires depuis 2021** étaient retirés de la moyenne — ORGT 2023 et
2024, STAC quatre années, UNXC quatre années, SCRC, SAFC, NEIC, FTSC, SICC. Or retirer
une perte **remonte** la moyenne, donc **baisse** le rapport dernier/moyenne, donc fait
paraître le titre **moins cher**. Un titre qui sort de pertes voyait la normalisation
jouer contre le lecteur, exactement à l'inverse de son intention affichée.

**(c) Le rapport mesure la croissance, pas un pic** — et c'est ce que Claudia voyait.
Sur une série géométrique de taux g, le dernier terme dépasse la moyenne de quatre
termes d'environ **1,5 g**. Mesuré sur les **8 titres à série strictement croissante**,
donc sans pic possible par construction : le PER est gonflé de **12 % à 119 %**, et le
gonflement suit g.

| titre | ratio mesuré | 1 + 1,5 g prédit | g %/an |
|---|---|---|---|
| NSBC | 1,12 | 1,12 | 7,9 |
| SNTS | 1,17 | 1,21 | 14,0 |
| ECOC | 1,22 | 1,29 | 19,3 |
| CABC | 1,21 | 1,33 | 21,9 |
| BOAC | 1,25 | 1,31 | 21,0 |
| SHEC | 1,27 | 1,29 | 19,3 |

BOAC — 20 069 → 26 075 → 32 044 → 35 540 — est monotone croissante, sans le moindre
pic, et son PER passe de 12,9 à 16,2.

**(d) Les chiffres du docstring étaient périmés et sa conclusion ne s'en déduisait
pas.** Il annonçait « médiane de la cote : 14,0 en affiché, 17,3 en normalisé — le
marché est environ un quart plus cher qu'il n'en a l'air ». Les deux médianes ne
portaient pas sur la même population : **47 titres** ont un PER affiché, **19
seulement** un PER normalisé. Sur les 19 calculables et sur eux seuls des deux côtés :
**14,0 affiché contre 16,2 normalisé, soit +16 %**. La médiane du PER affiché sur les
47 titres vaut 15,2, et ne doit jamais être comparée à celle du normalisé.

### 4. Ce qui a été corrigé, et ce qui ne l'est pas

Claudia a validé les correctifs **mécaniques** dans un commit à part. Corrigés :
(a) fenêtre prise par années **consécutives** à partir du dernier exercice connu, refus
de calculer sous trois exercices consécutifs ; (b) exercices déficitaires **inclus**
dans la moyenne, avec refus de conclure si la moyenne ou le dernier exercice n'est pas
strictement positif ; (d) chiffres du docstring refaits sur la base du jour, avec la
population explicitée.

**(c) n'est PAS corrigé** : c'est un arbitrage de méthode, inscrit en **C23**, avec les
trois lectures mesurées (moyenne, tendance, retrait). La lecture par **tendance**
— régression log-linéaire sur la fenêtre — ramène les titres monotones à **0,93–1,02**
(BOAC 1,25 → 0,96, CABC 1,21 → 0,93, BICC 1,64 → 1,02) tout en laissant SPHC à 1,25 ;
mais sur un effondrement récent elle extrapole l'ancienne pente et rendrait **327** pour
SICC et **875** pour BNBC. Aucune des deux n'est bonne partout : c'est pour cela que
cela se tranche et ne se décide pas dans un cycle.

### 5. Effet mesuré des deux correctifs

| | avant | après |
|---|---|---|
| titres avec un PER normalisé | 25 | **19** |
| fenêtres à trou | 6 | **0** |
| exercices déficitaires écartés en silence | 17 | **0** |
| `profil`, `secondaire`, `grade`, `gate` qui bougent | — | **0, 0, 0, 0** |

Six titres **perdent** leur PER normalisé, et c'est le résultat voulu : BNBC, BOABF,
ECOC, SDCC et SICC n'ont pas trois exercices consécutifs, ORGT a une moyenne négative
sur 2022-2025 (21 640, −44 363, −18 186, 19 199). Une case vide vaut mieux qu'une
valeur approchée. Un seul change de valeur : **BICC, 24,4 → 20,5**, désormais calculé
sur 2023-2025 au lieu d'enjamber 2022. **Aucun verdict ne bouge.**

### 6. Test

**Section 7 de `tester_donnees.py`, 5 contrôles ajoutés**, dont quatre sur une base
**jetable** — donc indépendants des données du jour — et portant chacun leur
**contre-exemple** : A (quatre années consécutives dont une perte : rapport attendu
1,60, l'ancienne règle donnait 1,00), B (fenêtre à trou : refus, l'ancienne règle
enjambait), C (série saine : inchangée, garde contre une sur-correction), D (moyenne
négative : refus). Le cinquième porte sur le fichier publié : toutes les fenêtres
retenues sont consécutives.

**Injection** — ancienne règle réinjectée dans `profils.py` : **3 des 4 contrôles sur
base jetable tombent en ÉCHEC**, et C reste vert comme il doit. Les contrôles
surveillent.

### 7. Barrières

Golden tests tous verts ; `tester_donnees.py` **197 OK, 0 ÉCHEC**, code 2 (alertes de
fraîcheur connues C4 et C5) — 192 avant, les 5 nouveaux en plus ;
`avis_brvm.py --test`, `notations.py --test`, `dates_dividendes.py --test` (27 cas),
`generer_dashboard.py` (48 titres) tous verts.

## 2026-10-01 — cycle 12 (soir, 18h54 UTC)

**Contrôle anti-collision.** `git log --since="3 hours ago"` sur `origin/main` ne rend
rien. Les deux derniers commits sont `b69570a` (clôture du cycle 11, 07h12 UTC) et
`d51a21b` (Claudia, 08h32 UTC), plus de dix heures plus tôt : aucune annonce de cycle
ouverte sans sa clôture. **Aucune annonce poussée par ce cycle** : la règle d'annonce
porte sur la famille chassée, et la chasse n'a lieu qu'au cycle du matin.

**Ce que Claudia a édité depuis le cycle 11** (`d51a21b`, 08h32 UTC) : trois lignes
`validation`, de `EN ATTENTE` à `OK` — **C17**, **C18**, et **C20 « OK option (a) »**.
Le bloc *Dernier cycle* du cycle 11 annonçait C19 comme prochain ; l'ordre déterminé par
le protocole le contredit désormais, et c'est l'ordre qui fait foi : au rang 1 (ORANGE
portant `validation : OK`, passe non consommée) la priorité la plus haute est **3**, et à
priorité égale le plus petit numéro — C17 passe donc avant C20, puis C18 (4) et C19 (6).

**Environnement, à noter.** Le bac à sable porte désormais **Python 3.13.15** (il portait
3.11 au cycle 10). `dashboard/generer_dashboard_html.py`, que CHANTIERS.md signalait comme
« barrière qui ne tourne pas dans le bac à sable » à cause de PEP 701, **compile**. La
note du cycle 10 était juste : c'était l'environnement, pas le fichier. Note corrigée.

---

### Exécuté : C17 — « Pour 13 titres sur 44, le dividende que le BOC divise reste introuvable »

**Le diagnostic du chantier était faux, et c'est le résultat du cycle.**

#### 1. La mesure d'origine, reproduite avant tout

Dividende implicite du BOC = `rendement × cours` sur la dernière séance de chaque titre,
confronté au versement le plus récent de la table `dividendes`. Reproduit à l'identique :
**44 titres** portent un rendement BOC non nul, **31 concordent** à 10 % près, **13 non**.
Les mêmes 13 titres que ceux inscrits au chantier, aux mêmes écarts.

#### 2. La fausse piste, mesurée puis écartée

Première hypothèse : le dividende de référence est en base, mais ce n'est pas le plus
récent. Testée en cherchant, pour chacun des 13, le versement le plus proche en montant
**parmi tous** : quatre « trouvailles » — NTLC 363,67 (2021), SMBC 720,00 (2023), SDCC
450,00 (2023), SIBC 360,00 (2021). Ce sont **exactement** les quatre fausses
identifications que la correction du cycle 7 bis avait retirées, et pour la même raison :
une coïncidence de montant sur une série de versements voisins n'identifie rien. Piste
abandonnée, et le commentaire de `diagnostic_distribution()` avait raison de l'interdire.

#### 3. La méthode qui a tranché : dater l'implicite au lieu de le lire une fois

Le dividende implicite ne peut bouger qu'à un détachement. Sur 2026, séance par séance,
avec un palier défini comme une suite de séances dont l'implicite varie de moins de 1,5 %
(bruit d'arrondi du rendement publié à quatre décimales) : **35 des 44 titres** changent
de palier en 2026, et la dispersion **à l'intérieur** de chaque palier va de 0,13 % à
1,08 % — sur 5 à 143 séances **à cours mouvant**. Un palier qui tient sur des dizaines de
séances pendant que le cours varie n'est pas un hasard d'arrondi : c'est un dividende.

Pour les 13 titres non concordants, la lecture est sans ambiguïté :

| titre | palier d'avant | = versement en base ? | bascule | palier d'après | = implicite ? |
|---|---|---|---|---|---|
| SLBC | 1 073,34 | oui (1 073,60) | 2026-07-29 | 1 872,26 | oui (1 871,25) |
| SIBC | 329,97 | oui (330,00) | 2026-07-30 | 374,04 | oui (373,73) |
| LNBB | 275,48 | oui (275,50) | 2026-08-03 | 164,13 | oui (164,26) |
| STBC | 2 095,92 | **non** (base 675,00) | 2026-08-12 | 1 707,20 | oui (1 707,07) |
| CFAC | 7,12 | oui (7,04) | 2026-08-13 | 55,44 | oui (55,47) |
| SGBC | 1 645,76 | oui (1 645,78) | 2026-08-21 | 2 298,45 | oui (2 300,41) |
| SPHC | 323,88 | oui (323,84) | 2026-08-27 | 430,36 | oui (430,13) |
| TTLC | 195,68 | oui (195,67) | 2026-08-28 | 139,73 | oui (139,84) |
| NTLC | 721,50 | oui (721,60) | 2026-09-04 | 369,72 | oui (369,00) |
| NEIC | 81,79 | oui (81,78) | 2026-09-09 | 140,39 | oui (140,30) |
| SDCC | 352,00 | oui (352,00) | 2026-09-15 | 461,99 | oui (461,50) |
| SMBC | 615,97 | **non** (base 1 080,00) | 2026-09-17 | 704,29 | oui (704,55) |
| SHEC | 75,27 | oui (75,29) | 2026-09-24 | 85,09 | oui (84,96) |

Onze des treize : le BOC a simplement **changé de référence** entre le 29/07 et le 24/09,
et notre base porte la précédente — elle n'avait pas tort, elle avait un exercice de
retard. Deux des treize, STBC et SMBC, sont un autre défaut (point 5).

#### 4. La cause : un fichier commité que personne ne charge

`collecte/dividendes_boc.csv`, **64 lignes, commité**, écrit par
`collecte_boc_quotidien.py` depuis la colonne « Dernier dividende payé » du bulletin
(montant net **et** date, lus directement, pas reconstruits). Il porte **les 13
références**, collectées entre le 28/07 et le 30/09/2026. Balayage de tous les `.py` et
`.yml` : seuls `collecte_boc_quotidien.py` lui-même et `backfill_dividendes.py` le
nomment. **Aucun chargeur de la chaîne ne le lit.** Et `collecte_boc_quotidien.py`
insère ses dividendes dans une base qui est dans `.gitignore` et rebâtie à neuf à chaque
passage : ses écritures sont perdues à chaque reconstruction.

La donnée était collectée, commitée, et perdue à l'entrée. Il n'y avait pas de lacune de
collecte : il y avait un **pont manquant**, le même genre de défaut que le pont de
`charger_dividendes_exercice.py` trouvé le 28/07 et que celui de
`charger_cours_quotidien.py` trouvé le 03/09.

#### 5. Les deux montants masqués

`donnees/base/dividendes.csv` portait deux marqueurs à montant **vide** :
`STBC,,2025-08-29,2024,date BOC ; montant a re-sourcer` et
`SMBC,,2025-09-15,2024,date BOC ; montant a re-sourcer`. Or
`charger_dividendes_exercice.py` déduplique par `(ticker, exercice_couvert)` : ces
marqueurs **masquaient** les montants que la Piste D portait déjà pour les mêmes
exercices et les **mêmes jours** — STBC 2024 = 2 096,00 au 2025-08-29, SMBC 2024 = 616,00
au 2025-09-15. La note disait « à re-sourcer » ; la source était dans le dépôt depuis le
début, rendue inatteignable par le marqueur lui-même. Et les paliers du point 3 les
confirment une troisième fois : 2 095,92 et 615,97.

#### 6. La preuve à deux côtés

Les deux côtés viennent de **deux colonnes différentes du même bulletin**, extraites par
deux chemins indépendants : la colonne « Dernier dividende payé » (ce fichier) et
`rendement × cours` (`cours_quotidien_boc`). Concordance des 16 lignes chargées :

```
SLBC -0,03 %   BICB +0,09 %   SIBC -0,07 %   LNBB +0,06 %
SOGC -0,04 %   STBC -0,01 %   CFAC +0,05 %   SGBC +0,07 %
SPHC -0,04 %   TTLC +0,05 %   NTLC -0,16 %   NEIC -0,07 %
SDCC -0,11 %   SMBC +0,08 %   SHEC -0,13 %   ABJC +0,07 %
```

#### 7. Ce qui a été écrit

**`collecte/charger_dividendes_boc.py`**, cinquième chargeur. Le rattachement à
l'exercice passe par `deduire_exercice()` de `historiser_dividendes_exercice.py` — une
seule définition dans le dépôt — et la validation de date par `est_iso()` de
`dates_dividendes.py`. Quatre refus par construction : jamais remplacer un montant
renseigné ; ne compléter un montant vide que si la `date_paiement` est **identique des
deux côtés** ; jamais deviner un exercice hors saison d'AGM ; jamais accepter une date
non ISO. Déduplication sur le triplet `(ticker, montant_net, date_paiement)`, la même
clef que `collecte_boc_quotidien.py`.

Sur la base du jour : **16 ajouts, 2 compléments, 38 déjà présents à l'identique, 8
refus, 0 écarté**. Table `dividendes` : **311 → 327** lignes ; montants vides : 3 → 1.
**Relancé une seconde fois : 0 ajout, 0 complément**, « 56 déjà présents ».

Branché dans `app.py::preparer_base()` et dans les **8** workflows qui enchaînent les
chargeurs (`pages.yml`, `tests.yml`, `avis_brvm.yml`, `notations.yml`, `migration_csv.yml`,
`releve_capitaux_propres.yml`, `lot2_referentiels_et_interimaires.yml`,
`branchement_agregateur.yml`). `collecte/dividendes_boc.csv` ajouté à `empreinte_donnees()`
de `app.py` : sans quoi un nouveau dividende collecté ne reconstruirait pas la base — le
défaut du 03/09 exactement.

**Pas de script de migration dans `outils/`**, et c'est voulu : aucun fichier du dépôt
n'est modifié. La correction vit dans le chargeur, et la base est rebâtie à neuf à chaque
passage. Le procès-verbal exécutable, ici, c'est le chargeur lui-même.

#### 8. Le défaut trouvé en posant la garde, corrigé dans le même commit

La clef naturelle de `peupler.py` inclut `montant_net`. Une ligne à montant vide et sa
version **complétée** sont donc deux lignes différentes pour elle, et le passage suivant
de `peupler.py` **réinsérait le marqueur vide à côté de la ligne complétée** — or
`app.py::preparer_base()` relance `peupler.py` sur une base **existante** dès que
l'empreinte change. Trouvé parce que la section 24 tombait en ÉCHEC après le seul test
d'idempotence de la section 16, qui relance `peupler.py` sur la base déjà chargée.

Seconde garde posée, volontairement étroite : elle ne retient que l'insertion d'un montant
**vide** déjà renseigné pour le même `(ticker, exercice, jour)`. Aucune valeur du CSV n'est
écartée, rien n'est écrasé. Vérifié : **trois passages de `peupler.py`** sur la base
chargée, **327 lignes, stable**, et le marqueur annoncé à l'écran à chaque fois.

#### 9. L'effet, dit franchement

`collecte/profils.json` est **identique à l'octet** avant et après — 0 titre d'écart sur
47, 0 champ sur les 57 du fichier. Les 16 versements chargés sont tous récents (2026-07 à
2026-09) : aucun n'est périmé au sens de `distribution_age_max_ans = 2`, aucun ne dépasse
`distribution_ratio_max = 3` fois le plus fort des précédents. **Aucun verdict du jour ne
dépend de ce chantier.**

Le gain est ailleurs, et il était invisible. La règle 1 de C1 n'identifie son dividende de
référence que par coïncidence entre l'implicite et le versement **le plus récent** ; sans
coïncidence, elle ne conclut pas — à juste titre. Elle était donc **silencieusement
inapplicable sur 13 des 44 titres**, soit **30 % du marché**, et rien ne le disait.
Désormais **44 / 44**. Effet visible sur la publication : 16 fiches gagnent une ligne
d'historique de dividende, et deux montants cessent d'être vides.

#### 10. Le test, et son injection

**Section 24 de `tester_donnees.py`, 9 contrôles.** Bloquants : le chargeur existe et lit
le bon fichier ; il ne porte qu'**un seul** `UPDATE` de montant ; la garde
`montant_base is None and date_base == date_p` est présente ; `peupler.py` porte sa
seconde garde ; le pont a **réellement tourné** sur cette base (compté sur
`source LIKE '%dividendes_boc.csv%'`) ; aucun montant vide ne masque un montant que le BOC
donne pour le même jour ; la population mesurée est réelle (≥ 40 titres). En alerte : le
plancher de **44** références identifiées, parce qu'une baisse peut venir du BOC et que ce
fichier ne bloque pas un commit pour un défaut de source. La tolérance est **lue dans
`config/seuils.yaml`**, pas recopiée : le contrôle doit suivre le moteur.

**Injection** — base reconstruite sans le cinquième chargeur. Deux contrôles tombent :
« 0 ligne … CHAÎNE AMPUTÉE » et « MASQUÉS : STBC ex.2024, SMBC ex.2024 ». L'alerte
redescend à **31 / 44** et nomme les 13 titres avec leurs écarts (CFAC 87 %, NTLC 96 %,
LNBB 68 %, STBC 60 %, SMBC 53 %, SLBC 43 %, NEIC 42 %, TTLC 40 %, SGBC 28 %, SPHC 25 %,
SDCC 24 %, SIBC 12 %, SHEC 11 %). Le contrôle tombe sous injection : il surveille.

La section 17 n'a pas eu besoin d'être modifiée : elle découvre les chargeurs par
`glob("charger_*.py")`, donc ses contrôles A, B et C exigent d'eux-mêmes le nouveau
chargeur dans `app.py`, `pages.yml` et tout workflow qui recommite `profils.json`.

---

### Ce que l'exécution a rendu visible, et qui n'est pas tranché

**C21 — un facteur 100 dans la colonne `rendement`.** En datant l'implicite, **29
séances** sur **7 titres** portent un rendement valant 50 à 200 fois celui de la veille
**et** du lendemain, à cours stable à 20 % près : ORGT 14, CFAC 3, ETIT 3, SCRC 3, SEMC 3,
NSBC 2, SPHC 1 ; 13 en 2026. C'est un « 1,26 % » entré comme la fraction `1,26`. Chez
**CFAC** le cas est inversé et la mauvaise échelle **domine** : 227 séances sur 2 019
au-dessus de 25 % de rendement, et au premier semestre 2026 ce sont les séances courantes
qui sont fausses (implicite ≈ 703) tandis que la dernière séance du mois porte la bonne
valeur (7,04). Le compte de 29 est un **plancher**. **Portée : latente** — aucune des 29
n'est la dernière séance de son titre (vérifié titre par titre), donc aucun `dy`, aucun
profil, aucun grade d'aujourd'hui n'en dépend ; ce qui en dépendra, ce sont les backtests.
**Piège à ne pas tendre** : FTSC porte 246 séances au-dessus de 25 % et ce n'est pas un
défaut — C1 a établi que sa distribution 2025 est exacte. C'est la **rupture entre
voisines**, pas le niveau, qui identifie le défaut.

**C22 — les 8 refus du pont.** Chacun oppose deux valeurs certifiées, et trois relèvent
d'autres chantiers : SAFC 2010 (23,04 contre 576,00, facteur **25,0** — le facteur exact
des collisions SAFC de C18) ; SEMC, BOABF et BOAC (écarts de 0,06 % à 2,8 %, soit la
question brut/net de C2 vue sur des montants) ; SICC 1999 et ORGT 2019 (la base porte un
**0** posé à la main, marqueur d'obsolescence — ne pas écraser) ; SNTS 2025 (même montant,
**un jour d'écart**, 25 contre 26/05/2026 : la clef `(ticker, montant, date)` ne protège
pas d'un doublon à un jour près) ; NSBC 2025 (le BOC dit 675,98 au 04/08/2026, la base
porte un montant vide daté du **30/06/2026**, qui est la date de l'**AGO** et non du
paiement — la garde de date a donc bien refusé, et NSBC reste le seul montant vide de la
table).

**Ce que C2 reçoit de ce cycle.** Le rapport implicite/déclaré, que C17 annonçait comme
« la mesure qui manquait à C2 », est sous 10 % sur **44 titres sur 44** contre 31 : la
convention brute/nette ne peut plus être loin sur aucun titre. Le **second** axe de C2 —
l'exercice de rattachement — reste entier.

---

### Barrières

Chaîne complète relancée après chaque modification : `peupler.py`, les **cinq** chargeurs,
`tester.py`, `profils.py`, `tester_donnees.py`, `avis_brvm.py --test`,
`notations.py --test`, `dates_dividendes.py --test`, `generer_dashboard.py`.

- `tester.py` : **tous les golden tests passent**.
- `tester_donnees.py` : **192 OK, 0 ÉCHEC**, code de sortie **2** — les deux alertes de
  fraîcheur connues, C4 (13 dates de division non documentées) et C5 (CFAC, NEIC).
  183 contrôles au cycle 11, 192 ici : les 9 de la section 24.
- `avis_brvm.py --test` : 11 avis, 10 rattachés, classification 8/8.
- `notations.py --test` : index 15/15, PDF GCR 10/10, Bloomfield 6/6, pièges 3/3.
- `dates_dividendes.py --test` : 27 cas, 0 échec.
- `generer_dashboard.py` : 48 titres.
- `generer_dashboard_html.py` : **compile** (bac à sable en Python 3.13.15).
- `dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés avant le commit.

### Prochain cycle

Par l'ordre déterminé, rang 1 (ORANGE portant `validation : OK`, passe non consommée),
priorité la plus haute puis plus petit numéro : **C20** (`OK option (a)`, priorité 3),
puis C18 (4), puis C19 (6). L'option (a) de C20 ne change aucune donnée : le cycle mesure
les lectures (b) et (c) pour documenter ce qui est écarté, et fige (a) par un test.
Candidate de chasse pour le prochain cycle du matin : les **tris et comparaisons sur
colonnes dont le type n'est pas celui qu'on croit** — généralisation de C10, annoncée au
cycle 11 et jamais chassée ; C21 en est une variante sur l'échelle plutôt que sur l'ordre.

## 2026-10-01 — cycle 11 (matin, 07h00 UTC)

**Contrôle anti-collision.** `git log --since="3 hours ago"` sur `main` ne rend
rien : le dernier commit datait de 00h39 UTC (`80e3c8b`, Sikafinance), six heures
plus tôt, et aucune annonce de cycle n'était ouverte. Annonce du cycle 11 poussée
seule (`deb5cdc`) avant tout travail.

**Incident technique au démarrage, à noter pour les cycles suivants.** Le dépôt
pré-cloné du bac à sable est **superficiel** (`--depth 1`), et `git push` y est
refusé avec un message trompeur — « a pushed branch tip is behind its remote
counterpart » — alors que le local était en avance d'un commit sur `origin/main`.
`git fetch --unshallow origin` (11 Mo, quelques secondes) a débloqué la poussée.
Ce n'est pas la collision que le message suggère : ne pas aller chercher un
conflit qui n'existe pas.

**État à la reprise.** Golden tests verts. Mais `collecte/profils.json` régénéré
par les barrières **différait du fichier commité sur six titres** — ce qui a
ouvert la chasse de ce cycle, plus bas.

**Lignes éditées par Claudia depuis le cycle 10.** `f673c88` (30/09, 19h54) :
C16 passe de `validation : OK` à `validation : OK option (b)`. `945b067`
(01/10, 00h11) : C19 passe de `EN ATTENTE` à `OK — remettre FTSC 2016`.

**Ordre déterministe, et la question qu'il a posée.** La ligne `statut` de C16
portait « la passe pré-autorisée est CONSOMMÉE », ce qui l'exclut du rang 1 à la
lettre. Mais la passe consommée était celle de la **mesure** ; le mot de Claudia
ouvre une passe **distincte**, l'application, et le bloc *Ce qu'il reste à
trancher* du chantier le disait explicitement : « le cycle suivant appliquera
l'option nommée ». C16 (priorité 3) passe donc avant C19 (priorité 6). La clause
du rang 1 gagnerait à dire « la passe que la ligne `validation` autorise
aujourd'hui », plutôt que « la passe autorisée ».

### Exécuté : C16 — option (b), l'axe de décote cesse de lire le rendement facial

**Ce qui a changé.** `moteur/profils.py` : les deux percentiles de rendement de
l'axe de décote — celui du titre et le bassin de comparaison — lisent `dy_axe`,
le rendement **récurrent**, et non plus `dy`, le rendement facial du BOC. Un titre
drapeauté `DISTRIBUTION_NON_RECURRENTE` a donc une case vide sur cet axe : il n'y
entre plus, et son rendement facial ne pèse plus sur le bassin des autres. `dy`
reste lu par le test du profil RENDEMENT et affiché sur la fiche, comme C1 l'avait
laissé.

**Le bloc des bassins a été hissé au niveau module**, dans
`bassins_et_axes(analysables, sp)`. Motif : il vivait à l'intérieur de
`calculer()`, donc la règle n'était testable que par ancrage textuel — un
commentaire qui dit ce que fait le code n'est pas un test. Garde posée à
l'extraction : `collecte/profils.json` **identique au champ près**, 0 titre
d'écart, avant et après le hissage. Le hissage est donc neutre, prouvé et non
supposé.

**Effet mesuré, option (a) → option (b), sur la base du jour.**

| | prévu (cycle 9) | mesuré (cycle 11) |
|---|---|---|
| `decote_pctl` bouge | 28 / 47 | **29 / 47** |
| amplitude hors ORGT | −1 à −3 points | **−1 à −3 points** |
| ORGT | 54 → 93, gagne `VALUE` | **54 → 93, `AUCUN_PROFIL` → `VALUE`** |
| SMBC | perd son secondaire `VALUE` | **perd son secondaire `VALUE`** (68 → 66) |
| `grade` | 0 | **0** |
| `gate` | 0 | **0** |
| `drapeaux` | 0 | **0** |

L'écart 28 → 29 vient des cours du jour, pas de la règle : la mesure du cycle 9
tournait sur la base du 30/09. Les champs touchés au total sont `decote_pctl`,
`dominant`, `mixte`, `motif`, `profil`, `secondaire` — c'est-à-dire les axes et
leur narration, rien d'autre.

**Ce que l'application confirme, et qui n'est pas confortable.** ORGT, qui n'a
pas versé de dividende depuis 2019, **gagne** un profil `VALUE` en passant de P54
à P93 : le titre est récompensé de ne rien distribuer, exactement ce que le texte
du chantier redoutait. Et SMBC, qui n'a aucun dividende périmé, perd un verdict
par simple effet de bassin. Les deux étaient annoncés avant la décision ; ils sont
maintenant réels. Le second est inscrit en **C20**, le premier est le choix de
Claudia et il est assumé tel quel.

**Test : section 21 de `tester_donnees.py`, 5 contrôles.** Ils tournent sur un
bassin **jetable** de quatre titres — A, B, C sains, D drapeauté dont le rendement
facial de 1,00 % est faux et dont le PER est celui de A — donc ils ne dépendent
d'aucune donnée du jour. Chaque contrôle porte son **contre-exemple** : les mêmes
quatre titres sous l'option (a) donnent D P62 au lieu de P100, B P62 au lieu de
P58, C P38 au lieu de P29. Sans ces valeurs opposées, le contrôle passerait aussi
bien sur l'option refusée, et ne figerait donc rien. Un cinquième contrôle vérifie
que la case vide de l'axe est la **même** que celle de `dy_recurrent` et de
`prime_rendement` sur la fiche, pour les six titres réels.

### Chasse : deux workflows réécrivaient `profils.json` sur une base amputée

**La famille.** Un workflow qui reconstruit un fichier de référence sur une chaîne
de chargement incomplète, et le commite. Rien ne la surveillait : le contrôle B de
la section 17 ne regardait que `pages.yml`, qu'il appelle « la chaîne de
référence » — or `pages.yml` **publie**, il ne commite rien.

**Ce n'est pas un défaut latent. Il s'est produit avant-hier.** Le 30/09 à 22h37,
`avis_brvm.yml` (P13, quotidien) a commité `collecte/profils.json` dans `548639e`,
1 025 lignes changées, après l'avoir recalculé sur une chaîne de **quatre**
scripts : `peupler.py`, `charger_cours.py`, `charger_cours_quotidien.py`,
`profils.py`. Il manquait `charger_dividendes_exercice.py`.

**Reproduction, au champ près.** En rejouant cette chaîne exacte dans le bac à
sable :

| | chaîne complète | chaîne de P13 |
|---|---|---|
| lignes dans `dividendes` | **311** | **15** |
| drapeaux `DISTRIBUTION_NON_RECURRENTE` | **6** | **0** |
| FTSC `prime_rendement` | *vide* | **+0,8035** |
| FTSC `dy_recurrent` | *vide* | **87,42** |
| SIVC `prime_rendement` | *vide* | **+0,1974** |

Les quatre dernières valeurs sont **exactement** celles du fichier commité le
30/09. `peupler.py` ne charge que les 15 dividendes de `donnees/base/` ; sans la
Piste D, `diagnostic_distribution()` n'a plus l'historique qu'il faut pour établir
« périmé » ou « exceptionnel », et les six drapeaux tombent en silence.
`notations.yml` (P12, mensuel) portait la même chaîne amputée.

**Pourquoi personne ne l'a vu.** La section 21 l'aurait attrapé — elle exige que
FTSC et SIVC portent le drapeau — mais aucun workflow de collecte ne lance les
barrières, et `tests.yml` n'avait plus tourné depuis `25f5a40` (30/09, 19h44). Le
fichier publié a donc contredit le code pendant huit heures sans que rien ne
s'allume. C'est **la régression n°2 de l'en-tête de `tester_donnees.py` pour la
troisième fois**, par une troisième porte : `app.py` (C13, section 18), puis les
workflows.

**Corrigé.** Les deux workflows enchaînent les cinq chargeurs, et l'ajout de
`collecte/profils.json` est subordonné à `steps.profils.outcome == success` dans
l'étape qui l'ajoute ; sinon le fichier est restauré par `git checkout --` et un
`::warning::` est émis. La chaîne complète seule ne suffisait pas : il restait la
panne d'un chargeur, qui est précisément le scénario de C13.

**Test : contrôle C de la section 17, deux assertions.** L'invariant est celui du
contrôle A, appliqué aux workflows : qui reconstruit un fichier de référence l'a
reconstruit sur la base complète.

**Et la leçon du cycle, qui vaut plus que le correctif : mes deux premières
versions de ce contrôle passaient à vide, et je les ai jetées.**

1. La première testait `nom_du_chargeur not in texte`. Elle passait — parce que le
   **commentaire que je venais d'ajouter** dans `avis_brvm.yml` nommait
   `charger_dividendes_exercice.py`. Vérifiée par injection : en retirant le
   chargeur de la chaîne, le contrôle restait `[OK]`. Elle lit maintenant les
   scripts **réellement lancés** (`python3 <...>.py` en début de ligne, hors
   commentaire).
2. La seconde cherchait `steps.profils.outcome` n'importe où dans le YAML. Elle
   passait aussi — les deux workflows nomment déjà cette sortie dans leur étape
   « Résumé », pour afficher un avertissement. Elle porte maintenant sur
   **l'étape** qui ajoute `profils.json`, par lecture YAML du workflow.

Les deux versions finales tombent sous injection, vérifié dans les trois sens :
chaîne amputée → `[ECHEC]` ; garde `env` neutralisée → `[ECHEC]` ; ajout rendu
inconditionnel → `[ECHEC]` ; état sain → `[OK]`. **Un contrôle qui ne tombe pas
sous injection ne surveille rien**, et c'est la deuxième fois en deux cycles qu'un
contrôle écrit de bonne foi se révèle vide (cycle 10 : la formulation d'origine du
contrôle NTLC/SMBC de la section 21 « passait à vide »).

**Incident de méthode, à dire aussi.** En restaurant un fichier après injection,
j'ai lancé `git checkout -- .github/workflows/notations.yml`, ce qui a effacé mes
propres corrections sur ce fichier — elles n'étaient pas encore commitées. Rattrapé
immédiatement, mais la règle est simple : pour restaurer un fichier après une
injection, recopier la sauvegarde hors du dépôt, **jamais** `git checkout`.

### Famille annoncée, non chassée

L'annonce du cycle nommait une autre famille : **les tris et comparaisons
lexicographiques sur des colonnes qui ne sont pas lexicographiquement ordonnées**,
généralisation de C10 à tous les `ORDER BY`, `MIN`, `MAX`, `BETWEEN` et `substr`
du dépôt. Elle a été remplacée en cours de cycle par la découverte ci-dessus, qui
était active et non spéculative. Elle reste la candidate du prochain cycle du
matin, et la substitution est dite ici plutôt que passée sous silence.

### Barrières

Golden tests OK. `tester_donnees.py` : **183 contrôles OK, 0 échec**, code **2**
— les deux alertes de fraîcheur sont celles de C4 (13 dates de division de nominal
non documentées) et C5 (CFAC et NEIC 2025). `avis_brvm.py --test` OK (11 avis,
classification 8/8). `notations.py --test` OK (index 15/15, PDF GCR 10/10).
`generer_dashboard.py` OK (48 titres). `generer_dashboard_html.py` échoue à
l'identique sur `HEAD` — revérifié ce cycle, c'est le Python 3.11 du bac à sable
contre le 3.12 de la CI, pas une régression. `dashboard_brvm.xlsx` et
`moteur/brvm.db` supprimés avant commit.

### Proposé

**C20 — l'effet de bassin**, ORANGE, `EN ATTENTE`, priorité 3. Diagnostic chiffré
ce cycle : le bassin marché porte 36 valeurs en bénéfice/prix et 34 en rendement
(2,8 et 2,9 points par cran), mais les 14 titres des `SERVICES_FINANCIERS` lisent
un bassin **sectoriel de 14 valeurs**, soit **7,1 et 7,7 points par cran** —
alors que **six verdicts** sont aujourd'hui à 3 points ou moins d'un seuil de
profil (ONTBF P66, SMBC P66 et SLBC P70 près du seuil VALUE 67 ; ETIT, SNTS et
SPHC près du seuil GROWTH sur l'axe croissance). Un seul titre qui entre ou sort
d'un bassin peut donc déplacer un verdict. Trois lectures à mesurer : laisser tel
quel, percentile laisser-un-dehors, plancher de taille de bassin sur l'axe
considéré — la borne `n_secteur_min = 8` porte aujourd'hui sur le bassin
bénéfice/prix, pas sur celui du rendement, qui peut être plus petit.

**Prochain chantier, par l'ordre déterministe : C19** (ORANGE, `validation : OK —
remettre FTSC 2016`, priorité 6, rang 1 non consommé).


## 2026-09-30 — cycle 10 (hors cadence, 19h25 UTC)

Cycle demandé par Claudia (« suite ») juste après le cycle 9, hors des deux
passages quotidiens. C10 étant `classe : VERTE`, il s'exécute sans attendre.

**Contrôle anti-collision.** `git log --since="3 hours ago"` sur `main` rend deux
commits, `b107732` et `b4edafd` : l'annonce du cycle 9 et son commit de clôture.
Aucune annonce orpheline, donc aucune session concurrente. Annonce du cycle 10
poussée seule (`ab5c1f5`) avant tout travail.

**État à la reprise.** CI verte, arbre propre.

### Exécuté : C10 — `dividendes.date_paiement` en ISO

Quatre pièces, et les quatre critères de terminaison du chantier.

**1. `collecte/dates_dividendes.py`** — seule définition de la conversion dans le
dépôt, avec autotest (`--test`) de **27 cas, 0 échec**. Choix de conception qui
compte : **liste blanche exacte de mois, aucune correspondance par préfixe**. La
première version faisait un repli sur les trois premières lettres ; son autotest a
immédiatement attrapé que `24-jullet-17` était alors accepté comme un 24 juillet,
c'est-à-dire exactement la devinette que le chantier interdit (« un mois français
abrégé mal orthographié doit échouer bruyamment »). Le module refuse aussi un jour
inexistant (`31-fevr.-20`, et `2025-02-31` côté ISO — l'ISO est revalidée, pas
recopiée), une année hors de la fenêtre 1998–2027 (c'est ainsi que l'ambiguïté du
siècle sur l'année à deux chiffres est **levée** plutôt que masquée : `30-sept.-97`
est refusé au lieu de devenir 2097), un mois numérique (`24/07/2017`, ambigu
jour/mois) et une ISO non zéro-paddée (`2017-7-24`). Couverture vérifiée sur les
trois CSV concernés : **0 valeur non convertible sur 364 + 365 + 15 lignes**.

**2. `outils/migration_dates_dividendes_iso.py`** — le procès-verbal exécutable.
**362 lignes converties sur 364**, 2 cases vides laissées vides, aucune autre
colonne modifiée (garde explicite champ par champ). Six gardes :

- entête, nombre de lignes (364), dates distinctes (253), cases vides (2),
  répartition des confiances (359 ELEVEE / 5 MANQUANT), fin de ligne ;
- ancres : toute clé répétée ne l'est que par des lignes rigoureusement
  identiques, et leur nombre est figé ;
- empreinte SHA-256 des clés et dates **avant** migration, et **après** ;
- réserialisation du fichier d'origine exigée **à l'octet près** avant toute
  écriture, sur le modèle de `versement_mensuel_vers_quotidien.py` ;
- refus sur date illisible — 0 cas ;
- relecture après écriture, empreinte revérifiée.

Relancé **deux fois** : il constate « migration DEJA APPLIQUEE », vérifie
l'empreinte d'après et sort sans écrire. `--verifier` ne touche à rien.

**3. Les trois chargeurs normalisent à l'entrée.**
`charger_dividendes_exercice.py` passe la date par `vers_iso` et **écarte la ligne
avec un message sur stderr** si elle est illisible (jamais une date devinée, jamais
une chaîne non ISO en base). `moteur/peupler.py` porte la même garde sur
`donnees/base/dividendes.csv` — déjà ISO, donc **aucune valeur ne change** : la
garde est là pour que la table ne puisse plus *mélanger* deux formats, et c'est le
mélange, non le format français en soi, qui cassait tout.
`historiser_dividendes_exercice.py` **émet désormais de l'ISO** : sans cela une
régénération aurait défait la migration.

`collecte_boc_quotidien.py` n'a pas été touché : son propre normaliseur
fonctionnait déjà, et ce que C10 lui demandait, c'était que sa déduplication
retrouve les lignes existantes — ce qui vient de la table, pas de lui.

**4. Test : section 23 de `tester_donnees.py`, 13 contrôles.** Les 27 cas du
module, les trois pièges nommément (`jullet`, jour inexistant, année 2097),
l'absence de toute date non ISO en base, un plancher de 308 dates ISO qui ne peut
que monter, la vérité du tri SQL, la faisabilité de `int(date[:4])`, la
reconnaissance par le dédoublonneur du BOC sur 40 témoins, et la présence de la
normalisation dans les trois chargeurs.

### Effet mesuré, avant → après, sur la base du jour

| | avant | après |
|---|---|---|
| dates non ISO dans `dividendes` | 296 | **0** (308 ISO, 3 nulles, 311 lignes) |
| tickers dont `ORDER BY date_paiement DESC` rend le mauvais versement | **34 / 49** | **0 / 49** |
| tickers dont `int(date[:4])` échoue | **45 / 49** | **0 / 49** |
| dividendes témoins retrouvés par la déduplication du BOC | **0 / 40** | **40 / 40** |
| champs déplacés dans `collecte/profils.json` | — | **0** (fichier identique) |

Le deuxième effet n'était pas chiffré avant le cycle 9 et c'est le plus grave des
trois conséquences du chantier. `scoring.py` fait
`int(dernier_div["date_paiement"][:4])` dans un `try` dont le `except (ValueError,
TypeError)` fait `pass`. Sur `24-juil.-17`, `[:4]` vaut `"24-j"` : `ValueError`,
avalée. Donc le bonus de 20 points « dividende versé cette année », le malus de 20
et l'alerte « dernier dividende versé il y a N ans » ne s'exécutaient sur **aucun**
des 45 titres concernés. Le troisième effet, la déduplication du BOC, était le seul
**latent** : 0 paire (ticker, jour) portant les deux formats, donc aucun doublon
n'existait encore — et c'est pour qu'il n'en existe jamais que la section 23 le
contrôle sur 40 témoins.

Que `profils.json` soit **identique au champ près** est attendu et vérifié :
`profils.py` lisait les dates par `date_dividende()`, qui acceptait déjà les deux
formats. C10 est de la plomberie, pas une révision de méthode — d'où sa classe
VERTE.

### Trouvé en posant les gardes : C19

L'assertion d'unicité du script de migration a **refusé de tourner au premier
essai**, sur les lignes 4 et 6 de `dividendes_par_exercice.csv` (`ABJC, 2017,
98,97, 20-juin-18`). C'est exactement ce pour quoi cette garde existe. Deux mesures
en sont sorties, inscrites en **C19** (ORANGE, `EN ATTENTE`, priorité 6) :

1. **12 lignes strictement dupliquées** sur les 364 (352 clés), identiques sur les
   six colonnes. Après normalisation elles sont **16**, parce que quatre événements
   étaient dédoublés sous **deux orthographes du même jour** : ABJC 2017
   (`20-juin-18` / `20-juin.-18`), ORAC 2023 (`3-juin-24` / `03-juin-24`),
   ETIT 2016 (`28 Apr 17` / `28-avr.-17`) et ETIT 2021 (`20 Jun 22` /
   `20-juin-22`). Les deux ETIT sont le même versement saisi une fois en anglais et
   une fois en français — une corroboration involontaire, pas une contradiction.
2. **Le fichier commité n'est plus ce que son générateur produit.** Relancé sur
   l'état du dépôt **avant tout changement de ce cycle** (vérifié sur des copies
   extraites de `HEAD`, pour ne pas imputer la dérive à ce cycle),
   `historiser_dividendes_exercice.py` rend **365 lignes** contre 364 commitées :
   une de plus, **FTSC 2016, 1 045,00, payé le 31/07/2017** — précisément le cas
   que le générateur documente dans son propre commentaire (avis BRVM
   N° 072-2017/DC/BR/DG). Le fichier dérivé a donc été retouché à la main.

Portée : **latente**. `charger_dividendes_exercice.py` déduplique par
`(ticker, exercice_couvert)`, donc la table porte 311 lignes avant comme après, et
aucun profil, grade ni gate n'en dépend. Ce qui en dépend : tout comptage
d'événements lu sur ce fichier (le générateur annonce « 364 événements » là où il
y en a 352), et la prochaine régénération, qui ajouterait FTSC 2016 sans que ce soit
la décision de quiconque. Le cas FTSC est un vrai arbitrage — soit le fichier a tort
de ne pas le porter, soit c'est le générateur qu'il faut corriger — d'où la classe
ORANGE.

### Barrières

**Complètes** (le commit touche `collecte/`, `moteur/` et `outils/`), toutes
vertes :

- les cinq scripts de construction de la base : 0 erreur, 296 dividendes chargés,
  **0 écarté pour date illisible** ;
- `moteur/tester.py` : TOUS LES GOLDEN TESTS PASSENT ;
- `moteur/profils.py` : 47 titres, et `collecte/profils.json` inchangé ;
- `moteur/tester_donnees.py` : **172 contrôles OK, 0 échec**, code de sortie 2 avec
  les deux seules alertes connues (C4 : 13 dates de division non documentées ;
  C5 : CFAC et NEIC 2025) ;
- `collecte/dates_dividendes.py --test` : 27 cas, 0 échec ;
- `collecte/avis_brvm.py --test` et `collecte/notations.py --test` : OK ;
- `dashboard/generer_dashboard.py` : dashboard généré, 48 titres.

**Une barrière ne tourne pas dans le bac à sable, et ce n'est pas une régression.**
`dashboard/generer_dashboard_html.py` échoue avec `SyntaxError: f-string
expression part cannot include a backslash`. Vérifié en compilant la version de
`HEAD` : **elle échoue identiquement**. Le bac à sable porte Python 3.11, tandis que
`pages.yml` et `tests.yml` épinglent 3.12, où PEP 701 autorise l'antislash dans une
f-string. La note est inscrite dans la section « Barrières » de `CHANTIERS.md` pour
qu'aucun cycle ne perde de temps à « réparer » un fichier sain.

`dashboard_brvm.xlsx` et `moteur/brvm.db` supprimés avant le commit.

### La CI est tombée, et c'était ma faute

Le premier commit de ce cycle (`c314f37`) a fait échouer **P4 — Golden tests** sur
`ModuleNotFoundError: No module named 'pdfplumber'`, alors que les barrières étaient
vertes dans le bac à sable une demi-heure plus tôt.

**Cause.** Le contrôle 4 de la section 23 faisait
`from collecte_boc_quotidien import date_dividende_vers_iso`. Ce module importe
`extracteur_boc`, qui fait `import pdfplumber` — et **`pdfplumber` n'est pas dans
`requirements.txt`**. Il se trouve préinstallé dans le bac à sable (0.11.9), donc la
barrière y passait ; le runner, qui n'installe que `pyyaml`, `openpyxl`, `pandas` et
`requirements.txt`, ne l'a pas.

**Correctif.** La fonction du BOC est désormais **extraite par AST** (`_extraire_fonction`
dans `tester_donnees.py`) : seuls son corps et l'affectation `MOIS_FR` sont compilés,
le reste du fichier — imports compris — est ignoré. Le contrôle teste donc toujours
la vraie fonction, sans dépendre de rien de plus que `requirements.txt`. Trois
contrôles s'ajoutent : deux qui vérifient que `collecte_boc_quotidien.py` convertit
toujours en ISO avant sa recherche de doublon et que cette recherche est toujours
l'égalité sur `(ticker, montant, date)` — sans quoi le contrôle 4 ne prouverait plus
rien — et un qui **interdit** l'import fautif. Ce dernier s'est déclenché sur son
propre commentaire à la première tentative (il cherchait la sous-chaîne) : il porte
maintenant sur les instructions, ligne par ligne.

**Vérification.** Les barrières ont été rejouées avec `pdfplumber` **rendu
indisponible** (un module factice en tête de `PYTHONPATH` qui lève
`ModuleNotFoundError`), pour reproduire le runner et non l'environnement local :
`tester.py` golden OK, `tester_donnees.py` **175 contrôles OK, 0 échec**, code 2 sur
les deux seules alertes connues.

**Leçon, à retenir par les cycles suivants.** Une barrière verte dans le bac à sable
ne prouve rien si le test importe quelque chose d'absent de `requirements.txt`. Le
bac à sable est plus riche que le runner. Quand un test a besoin d'une fonction qui
vit dans un fichier à imports lourds, l'extraire plutôt que l'importer.

### Proposé pour le cycle suivant

**C3** (VERTE, priorité 3) — `journal_profils.csv`, le journal des prédictions.
C10 était inscrit « avant C3, dont le journal datera ses lignes » : cette
dépendance est maintenant levée, les dates sont ISO. C19 attend, lui, une
validation de Claudia sur le cas FTSC 2016.

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
