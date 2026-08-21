#!/usr/bin/env bash
# Publie les fichiers produits par une collecte, en résistant aux écritures
# concurrentes sur main.
#
#   bash pipeline/publier.sh "donnees/boc.json" "BOC séance du 2026-08-20"
#
# Le dépôt reçoit des poussées d'autres chaînes (P9 à P12, backfills) et vos
# propres commits depuis l'interface web. Entre le checkout et la poussée, main
# a donc pu avancer : git refuse alors la poussée, et la collecte est perdue.
#
# La parade tient en une idée : les fichiers produits ici sont des artefacts
# dérivés, régénérables. Plutôt que de fusionner, on se replace sur l'état
# distant le plus récent, on y repose le fichier qu'on vient de collecter, on
# reconstruit le tableau de bord sur cet ensemble fusionné, puis on pousse.
# La poussée est alors forcément en avance rapide.
set -euo pipefail

ARTEFACT="${1:?fichier collecté attendu}"
MESSAGE="${2:?message de commit attendu}"
REBUILD="${REBUILD:-python pipeline/construit_donnees.py}"
DERIVES="donnees/cote_reference.json docs/data_brvm.json"
ESSAIS="${ESSAIS:-3}"

git config user.name  "pipeline-brvm"
git config user.email "actions@users.noreply.github.com"

SAUVE="$(mktemp -d)"
cp -f "$ARTEFACT" "$SAUVE/"

for essai in $(seq 1 "$ESSAIS"); do
  git fetch --quiet origin main
  git reset --quiet --hard origin/main
  cp -f "$SAUVE/$(basename "$ARTEFACT")" "$ARTEFACT"

  eval "$REBUILD"

  git add -- "$ARTEFACT" $DERIVES 2>/dev/null || git add -- "$ARTEFACT"
  if git diff --cached --quiet; then
    echo "Aucun changement : rien à publier."
    exit 0
  fi
  git commit --quiet -m "$MESSAGE"

  if git push --quiet origin HEAD:main 2>/dev/null; then
    echo "Publié : $MESSAGE"
    exit 0
  fi
  echo "Poussée refusée (tentative $essai/$ESSAIS) : le dépôt a avancé, on reprend sur l'état à jour."
  sleep 5
done

echo "::error::Poussée refusée après $ESSAIS tentatives. Le dépôt reçoit des écritures trop rapprochées."
exit 1
