# brvm-data-pipeline

Collecte et archivage automatisés des publications officielles de la BRVM
(Bourse Régionale des Valeurs Mobilières — UEMOA).

## Contenu du dépôt
- `config/` — paramètres du pipeline : registre des seuils, dictionnaire sémantique
- `collecte/` — robot de collecte sélective (à venir, phase P2)
- Les documents PDF collectés sont archivés dans les **Releases**, pas dans le dépôt
- `MANIFESTE.csv` — registre SHA-256 de chaque document collecté (à venir)

## Principes
- Sources publiques uniquement (publications réglementaires brvm.org)
- Cadence de collecte respectueuse (max 1-2 requêtes/seconde)
- Intégrité avant couverture : aucune donnée n'est devinée
- **Aucune donnée personnelle** (portefeuille, décisions, scores) n'est
  stockée dans ce dépôt — infrastructure de collecte uniquement.

## Orchestration des workflows (documenté le 14/07/2026)

Cinq workflows GitHub Actions composent le pipeline :

| Workflow | Déclencheur | Écrit sur `main` ? |
|---|---|---|
| `collecte.yml` (P2b) | cron lundi/jeudi 3h UTC + manuel | Oui — `MANIFESTE.csv`, `collecte/etat_rapports.json`, `collecte/a_reteleverser.json` |
| `inventaire.yml` (P2a) | manuel | Oui — `collecte/inventaire.json`, `collecte/rapport_inventaire.md` |
| `reparation.yml` (P2c) | manuel | Oui — `collecte/a_reteleverser.json`, `collecte/anomalies_integrite.json` |
| `tests.yml` (P4) | push sur `moteur/config/collecte/dashboard` | Non |
| `pages.yml` (P5b) | push sur `moteur/config/collecte/dashboard` + cron | Non |

**Cascade intentionnelle** : les trois premiers workflows committent des fichiers
sous `collecte/**`, ce qui redéclenche automatiquement `tests.yml` et `pages.yml`
(chemins surveillés). C'est voulu — chaque collecte programmée republie le site
si les golden tests passent. Aucun risque de boucle infinie : `tests.yml` et
`pages.yml` ne committent jamais rien.

**Garde-fou de déploiement** : `pages.yml` ne dépend pas explicitement de
`tests.yml` mais les deux exécutent `peupler.py` + `tester.py` implicitement
dans leur propre job — un échec des golden tests dans `tests.yml` n'empêche
*pas* mécaniquement `pages.yml` de publier une version buguée s'ils sont
déclenchés par le même push et s'exécutent en parallèle. **Limite connue,
non corrigée à ce jour** : faire dépendre `pages.yml` du succès de
`tests.yml` (`needs:` ou déclenchement en chaîne) est un chantier ouvert.

## Chantier ouvert — extraction automatique (priorité longue, ouvert le 14/07/2026)

L'essentiel des 147 lignes de `moteur/peupler.py` (table `ETATS`) est
**transcrit à la main** depuis les PDF collectés, pas extrait automatiquement.
`collecte/extractions_brutes.jsonl` (extraction automatisée réelle) ne couvre
que 62 lignes. Tant que ce chantier n'est pas mené, chaque nouvelle publication
BRVM exige une transcription manuelle avant d'entrer dans le moteur — c'est la
cause principale de la lenteur du projet, pas l'interface. Non planifié à ce
jour faute de temps disponible ; à reprendre en priorité une fois les
finitions d'ergonomie du dashboard terminées.
