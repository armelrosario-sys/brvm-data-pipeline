# Tableau de bord BRVM — chaîne automatisée

Le tableau de bord `docs/index.html` lit `docs/data_brvm.json`, régénéré par deux
workflows GitHub Actions. Aucune intervention manuelle en régime courant, à une
exception près : les capitaux propres (voir plus bas).

## Arborescence

    pipeline/collecte_boc.py           bulletin officiel de la cote, quotidien
    pipeline/collecte_sikafinance.py   performances et fondamentaux, hebdomadaire
    pipeline/construit_donnees.py      fusion et calculs dérivés
    donnees/                           collectes brutes + capitaux propres saisis
    docs/                              ce qui est publié sur GitHub Pages

## Mise en service

1. Copier cette arborescence à la racine d'un dépôt.
2. Settings > Pages > Source : *Deploy from a branch*, branche `main`, dossier `/docs`.
3. Settings > Actions > General > Workflow permissions : *Read and write permissions*.
4. Onglet Actions, lancer *BOC quotidien* à la main une première fois.

Le tableau de bord est alors servi à l'adresse indiquée par Settings > Pages.

## Vérifier avant d'automatiser

    python pipeline/collecte_boc.py --pdf un_boc.pdf     # doit afficher 7 contrôles OK
    python pipeline/collecte_sikafinance.py SNTS CBIBF   # CA attendus 1923122 et 138986
    python pipeline/construit_donnees.py                 # affiche la couverture

## Capitaux propres

Sikafinance ne publie pas les capitaux propres : le ROE ne peut pas être collecté.
Saisir la colonne `fonds_propres` de `donnees/fonds_propres.csv` depuis les rapports
annuels, une fois par exercice. Tant qu'une ligne reste vide, la cellule ROE affiche
un tiret et le motif au survol, plutôt qu'une valeur approchée.

## Contrôles automatiques

`collecte_boc.py` réconcilie les lignes extraites avec la page de synthèse du
bulletin : volume, valeur transigée, répartition hausse/baisse/inchangé, et
recalcul des 47 variations du jour. En cas d'écart, le script sort en erreur et le
workflow échoue sans rien publier — un changement de format du BOC est ainsi signalé
au lieu d'être propagé silencieusement.
