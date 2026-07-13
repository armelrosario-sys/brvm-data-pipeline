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
