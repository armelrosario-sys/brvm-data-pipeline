# Fiche de reprise — Profilage BRVM (application Streamlit)

**Établie le 02/10/2026**, après la suppression accidentelle de la conversation de travail.
**Source unique de cette fiche : le dépôt `armelrosario-sys/brvm-data-pipeline`**, lu commit par commit (971 commits, dernier à 10:30:46 UTC le 02/10/2026). Rien n'y est reconstitué de mémoire.

---

## 1. Ce qui est perdu, et ce qui ne l'est pas

**Perdu** : le fil de discussion lui-même (vos questions, mes réponses, les arbitrages exprimés en conversation).

**Intact**, parce que le projet a toujours tout écrit dans le dépôt :

| Fichier | Ce qu'il contient |
|---|---|
| `app.py` (1 222 lignes) | L'application déployée |
| `moteur/profils.py` (1 693 lignes) | Le moteur de profilage, avec sa doctrine en tête de fichier |
| `config/seuils.yaml` | Tous les seuils, chacun avec sa justification |
| `CHANTIERS.md` | La file de travail, le protocole, l'état du dernier cycle |
| `docs/JOURNAL.md` (2 267 lignes) | Le journal complet des cycles et des travaux hors cycle |
| `docs/strategie_brvm_reference.md` | Le document de référence v2.3 (11/07/2026) |

Le dernier travail fait dans la conversation supprimée est le commit **`75b07af` — « PER glissant (TTM) : calculé, vérifié, affiché »**, poussé à 10:30 UTC le 02/10/2026. Il est complet : barrières passées, rendu vérifié à l'écran.

---

## 2. L'outil

- **URL** : https://brvm-data-pipeline-profilage.streamlit.app/
- **Dépôt** : `armelrosario-sys/brvm-data-pipeline`, branche `main`, fichier `app.py`
- **Hébergement** : Streamlit Community Cloud
- **Base** : `moteur/brvm.db` n'est **jamais commitée**. Elle est reconstruite au démarrage (`peupler.py` + chargeurs, via `moteur/chaine.py`).
- **Dépendances** : `streamlit>=1.40,<2`, `pandas`, `altair`, `PyYAML`, et **`starlette<1.4`** — verrou posé le 05/08/2026 : sans lui, Streamlit 1.61 renvoie une erreur 500 à tous les contrôles de santé et l'application ne démarre jamais. À retirer quand Streamlit corrigera l'appel.
- **Quatre onglets** : *Vue d'ensemble* · *Explorer* · *Fiche titre* · *Qualité des données & méthode*.
- **Principe éditorial** : la réponse d'abord, la donnée ensuite ; l'incertitude (grade, source, réserves) affichée au même rang que le résultat. Aucun score composite, aucun classement décisionnel.

---

## 3. Chronologie

| Date | Étape |
|---|---|
| 13/07/2026 | Dépôt reconstruit (purge de l'historique Git) |
| **31/07/2026** | **Changement de doctrine** : le cadre sert au *profilage*, plus à la détection de re-rating. Le score de style 0-100 (v1) est supprimé. Première version de `app.py`, déploiement Streamlit. |
| 02/08/2026 | Nouveaux seuils, `croissance_rn` enrichie |
| 04/08/2026 | Collecte des notations financières (Bloomfield, GCR) ; filtre « contradiction de notation » dans l'app |
| 05/08/2026 | Verrou `starlette<1.4` |
| 06/08/2026 | Gardes v3.2 : part opérationnelle du résultat, inflexion récente |
| 03/09/2026 | L'app lit enfin les cours **quotidiens** (elle affichait des cours arrêtés au 07/07) |
| 18/09/2026 | `SERIE_TROUEE` devient bloquant (cas SGBC) |
| 26/09/2026 | Arbitrage contre une source extérieure (`moteur/arbitrage.py`) |
| 27/09/2026 | Création de `CHANTIERS.md` et de la **boucle automatique** |
| 30/09/2026 | Protocole révisé : classes VERTE/ORANGE, anti-collision, deux passages par jour |
| 02/10/2026 | Cycle 13 (C20) ; C23 : retrait définitif du PER normalisé ; quadrants du plan en tableaux ; **PER glissant (TTM)** |

---

## 4. Doctrine du profilage

### Trois interdits actés (à ne jamais contourner)

1. Le profilage **ne sert pas** à chercher les re-ratings explosifs ; il en est structurellement l'anti-outil.
2. Le test point-in-time (GARP +94 % contre marché +80 % sur 12 mois) **n'est pas une preuve** : p = 0,43, IC 90 % [−14 % ; +89 %]. Aucune supériorité de style n'est établie sur la BRVM.
3. L'étiquette est **descriptive, jamais décisionnelle**. Le système ne décide seul d'aucune position.

### Profils produits (`moteur/profils.py`, fonction `profil_par_signature`)

Profil déduit **par signature**, sans score. Un titre peut porter un profil principal et un secondaire. Ordre de priorité : GARP > GROWTH > VALUE > RENDEMENT.

| Profil | Signature (seuils de `config/seuils.yaml`) |
|---|---|
| **GARP** | croissance entre 8 % et 30 %/an, PEGY ≤ 1,5, payout ≤ 100 %, aucun blocage |
| **GROWTH** | croissance au tercile supérieur (≥ P67) et > 5 %/an, aucun blocage |
| **VALUE** | décote ≥ P67, payout ≤ 100 %, contraction pas pire que −10 %/an |
| **RENDEMENT** | rendement brut ≥ 4,8 %, payout ≤ 100 %, croissance quasi nulle (< 8 % en valeur absolue) |
| **VIGILANCE_CONTRACTION** | bénéfices en recul de plus de 10 %/an sans décote suffisante |
| **AUCUN_PROFIL** | cœur de cote correctement payé ; le motif précis est toujours affiché |
| **RETOURNEMENT** | pertes ou sortie de pertes avec catalyseur documenté — hors périmètre |
| **MUTATION** | nature économique changée : l'historique n'est plus prédictif — hors périmètre |
| **NON_ANALYSABLE** | PER absent ou bénéfices résiduels (PER > 50) |

RETOURNEMENT et MUTATION viennent de faits datés et sourcés dans `config/faits_qualitatifs.yaml`.

**Blocages de la croissance** (GARP et GROWTH interdits) : inflexion récente (dernier exercice < −10 %), série à trous, base écrasée (1er exercice < 30 % de la médiane), croissance plafonnée (cap à 60 %/an), rattrapage > 30 %/an.

### Sources de croissance, par priorité

1. Résultats nets transcrits en base (VALIDÉ > PROBABLE), ≥ 3 exercices consécutivement bénéficiaires.
2. Repli : BPA implicite (cours / PER du BOC), statut PROBABLE.

### Axes

Percentile **intra-secteur** si le secteur compte au moins 8 titres, sinon **marché** ; la référence est toujours étiquetée. La variable de décote s'appelle `decote_pctl` depuis le 27/09 (P100 = le moins cher).

### Grades de confiance

- **A** — exploitable tel quel : source certifiée, aucun drapeau de croissance (ou corroboration par une source extérieure).
- **B** — solide avec réserve nommée. RETOURNEMENT/MUTATION documentés, BPA implicite, VALUE/RENDEMENT sans payout.
- **C** — travail requis : NON_ANALYSABLE, ou drapeau critique (contradiction RN/BPA, base gonflée, conflit N-1, résultat non opérationnel, inflexion récente, données périmées, contradiction par une publication intermédiaire, arbitrage contesté).
- Un titre **suspendu** ou en **contradiction de notation** ne peut pas être A.

---

## 5. État au 02/10/2026 (`collecte/profils.json`)

**47 titres.**

| Profil | Titres |
|---|---|
| AUCUN_PROFIL | 17 |
| GARP | 8 |
| VALUE | 6 |
| RETOURNEMENT | 6 |
| VIGILANCE_CONTRACTION | 4 |
| NON_ANALYSABLE | 3 |
| MUTATION | 2 |
| GROWTH | 1 |

**Grades** : A = 5 · B = 28 · C = 14.

**Barrières au dernier commit** : golden tests verts ; `tester_donnees.py` 231 OK, 0 échec (alertes de fraîcheur connues C4, C5) ; l'app démarre et rend ses 4 onglets.

---

## 6. La boucle automatique

Deux passages par jour, **06h53 et 18h53 UTC**. Chaque session part de zéro : elle clone le dépôt, lit `CHANTIERS.md`, exécute **un** chantier, écrit le journal, pousse. Elle ne lit pas les conversations.

**La conversation de développement et la boucle** partagent le dépôt et rien d'autre. Leur coordination est écrite dans `CHANTIERS.md`, section *Travail hors cycle* (ajoutée le 02/10/2026) : pas de travail interactif entre 06h40-07h45 ni 18h40-19h45 UTC, annonce et clôture de chaque travail hors cycle, et toute demande non finie en conversation devient un chantier de la file.

**Vous pilotez uniquement depuis `CHANTIERS.md`**, au crayon sur GitHub :

```
- validation : EN ATTENTE   →   - validation : OK
- validation : NON — motif
- classe : ORANGE           →   - classe : VERTE
```

- **VERTE** : exécuté sans attendre (réversible, aucune donnée certifiée touchée).
- **ORANGE** : mesuré, puis arrêt avant écriture jusqu'à votre `validation : OK`.

### Chantiers ouverts

| Chantier | Objet | Validation |
|---|---|---|
| C18 | Cinq collisions d'échelle dans la série de cours | **OK** — prochain prévu |
| C19 | Doublons de `dividendes_par_exercice.csv` | **OK** — remettre FTSC 2016 |
| C21 | Facteur 100 dans la colonne rendement du BOC | **OK** |
| C22 | Les 8 refus du pont BOC | **OK** |
| C25 | Bulletin PDF contre page « Volumes / Valeurs » | **OK** |
| C24 | Douze avis de dividende non rattachés | à décider |
| C26 | Publications intermédiaires (3 lignes pour 47 titres) — c'est elle qui remplira le PER glissant, vide pour 46 titres sur 47 | à décider |
| C2 à C9, C11, C12, C14 | Chantiers plus anciens | à décider |

**Veille datée** : 08/10/2026, AGE Sonatel (fractionnement) — si elle passe, enregistrer la division de nominal le jour même.

---

## 7. Texte à coller pour reprendre dans une nouvelle conversation

*À n'utiliser que si la conversation de développement en cours était, elle aussi, perdue.*

```
Je reprends le développement de mon application Streamlit de profilage BRVM
(https://brvm-data-pipeline-profilage.streamlit.app/, dépôt public
armelrosario-sys/brvm-data-pipeline, fichier app.py). La conversation
précédente a été supprimée par erreur le 02/10/2026.

Avant toute proposition :
1. Clone le dépôt et lis, dans cet ordre : CHANTIERS.md (protocole, file,
   dernier cycle), l'en-tête de moteur/profils.py (doctrine), config/seuils.yaml
   (section profils), puis l'entrée la plus récente de docs/JOURNAL.md.
2. Le dernier travail fait est le commit 75b07af (PER glissant TTM).
3. Une boucle automatique tourne à 06h53 et 18h53 UTC et pousse sur main :
   applique la section « Travail hors cycle » de CHANTIERS.md (fenêtres
   interdites, annonce et clôture) et refais un git fetch avant tout commit.
4. Respecte les règles de CHANTIERS.md : une case vide vaut mieux qu'une valeur
   approchée ; preuve à deux côtés avant de corriger une donnée certifiée ;
   jamais de commit si une barrière tombe ; ne cite que des nombres mesurés.

Ma demande : [à compléter]
```
