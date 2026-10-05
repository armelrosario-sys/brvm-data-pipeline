# Mises à jour automatiques des briques sur lesquelles la chaîne repose.
#
# L'enjeu n'est pas la nouveauté mais la panne : une action GitHub figée finit
# par être retirée du service, et le jour où cela arrive, la collecte s'arrête
# sans prévenir. Dependabot ouvre une pull request à chaque version, ce qui
# laisse le temps de la lire plutôt que de la subir.
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
      day: monday
      time: "06:00"
      timezone: UTC
    open-pull-requests-limit: 3
    commit-message:
      prefix: actions
    labels:
      - dependances
    groups:
      # Une pull request par semaine plutôt qu'une par action : les montées de
      # version d'actions officielles se relisent ensemble.
      actions-officielles:
        patterns:
          - "actions/*"
