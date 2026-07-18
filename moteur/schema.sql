-- Schema BRVM — v1.0 — genere le 08/07/2026
-- Principe : donnees brutes immuables (append-only), jamais de reecriture destructive.

CREATE TABLE IF NOT EXISTS societes (
    ticker TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    secteur TEXT NOT NULL,           -- nomenclature BRVM 2026 (7 secteurs)
    referentiel_comptable TEXT,      -- SYSCOHADA | BANCAIRE_UMOA | CIMA
    pays_immatriculation TEXT,
    date_introduction TEXT,
    controle_actionnarial TEXT       -- note libre : actionnaire(s) de controle
);

CREATE TABLE IF NOT EXISTS etats_financiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    exercice INTEGER NOT NULL,               -- annee civile de l'exercice (lu DANS le document, jamais du nom de fichier)
    resultat_net REAL,                       -- en millions FCFA
    resultat_net_n1 REAL,                    -- comparatif N-1 republie dans le meme document
    resultat_activites_ordinaires REAL,       -- RAO (SYSCOHADA) : resultat hors elements HAO, quand
                                              -- disponible dans le document source (jamais devine)
    total_actif REAL,
    total_passif REAL,
    capitaux_propres REAL,
    dettes_financieres REAL,
    payout_ratio REAL,                       -- dividende propose / benefice distribuable
    solvabilite_bancaire REAL,               -- uniquement pour secteur FIN, ratio reglementaire
    source_type TEXT NOT NULL,               -- NATIF | OCR | DEUX_SOURCE
    statut_donnee TEXT NOT NULL,             -- VALIDE | PROBABLE | QUARANTAINE | MANQUANT
    date_publication TEXT,                   -- date EFFECTIVE de publication (anti look-ahead bias)
    source_url TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS cours_mensuels (
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    fin_mois TEXT NOT NULL,          -- 'AAAA-MM'
    cours REAL,
    per REAL,
    rendement REAL,
    liquidite_ratio REAL,
    PRIMARY KEY (ticker, fin_mois)
);

-- Cours quotidiens du BOC (18/07/2026) : contrairement a cours_mensuels
-- (une seule ligne par mois, la plus tardive -- ecrase volontairement
-- l'intra-mensuel), cette table ACCUMULE une ligne par jour de cotation,
-- sans jamais rien ecraser. Necessaire des lors que la collecte du BOC
-- passe a une cadence quotidienne (la BRVM publie un BOC chaque jour de
-- cotation) -- continuer a tout ecraser dans cours_mensuels aurait jete
-- l'historique intra-mensuel chaque jour, une vraie perte d'information.
CREATE TABLE IF NOT EXISTS cours_quotidien_boc (
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    date_bulletin TEXT NOT NULL,     -- 'AAAA-MM-JJ', date du BOC (pas la date de collecte)
    cours REAL,
    per REAL,
    rendement REAL,
    PRIMARY KEY (ticker, date_bulletin)
);

CREATE TABLE IF NOT EXISTS dividendes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    montant_net REAL,
    date_paiement TEXT,
    exercice_couvert INTEGER,
    statut_donnee TEXT NOT NULL DEFAULT 'VALIDE',   -- VALIDE | A_RESOURCER
    source TEXT                                      -- origine de la valeur (meme exigence que l'extraction)
);

CREATE TABLE IF NOT EXISTS avis_reglementaires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    type TEXT NOT NULL,              -- RETARD_PUBLICATION | RESERVE_CAC | SANCTION | SUSPENSION | OPR
    date_avis TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    date_run TEXT NOT NULL,
    version_seuils TEXT NOT NULL,
    statut_gate TEXT NOT NULL,       -- ELIGIBLE | EXCLU
    motif_exclusion TEXT,
    score_rentabilite REAL,
    score_solidite REAL,
    score_valorisation REAL,
    score_composite REAL,
    alertes TEXT                     -- JSON liste des signaux de vigilance (non-exclusion)
);

CREATE TABLE IF NOT EXISTS journal_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_decision TEXT NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,            -- ACHAT | VENTE | ARBITRAGE_DONNEE
    detail TEXT,
    score_id INTEGER REFERENCES scores(id)
);


-- Deduplication des lots de donnees (correctif 14/07/2026) : le lot le plus
-- recent (corrections R6+) remplace les lignes anterieures du meme exercice.
CREATE UNIQUE INDEX IF NOT EXISTS ux_etats_ticker_exercice
    ON etats_financiers(ticker, exercice);

-- ============================================================
-- CHANTIER 1 (13/07/2026) — Table des signaux avec cycle de vie
-- La "photo" reste dans scores.alertes ; ceci est le "film" :
-- evenements dates, statut actif/eteint, append-only.
-- ============================================================
CREATE TABLE IF NOT EXISTS signaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES societes(ticker),
    type TEXT NOT NULL,             -- catalogue v1 : D1..D4, A_QUALITE_DECOTEE, B1_RECORD, RERATING_EN_COURS
    direction TEXT NOT NULL,        -- FAVORABLE | DEFAVORABLE | NEUTRE
    detail TEXT,                    -- phrase factuelle avec les chiffres constates
    valeur_reference REAL,          -- ex : cours au declenchement (anti-poursuite)
    date_detection TEXT NOT NULL,   -- date du RUN qui a detecte
    source_donnee TEXT,             -- ex : 'etats_financiers 2025', 'cours_mensuels 2026-07'
    statut TEXT NOT NULL DEFAULT 'ACTIF',    -- ACTIF | ETEINT
    date_extinction TEXT,
    voie_extinction TEXT            -- CONDITION_CESSEE | EXPIRATION | REMPLACE | RERATING_ACHEVE | DECISION_HUMAINE | CONFLIT_ALARME
);
-- Un seul signal ACTIF par couple (ticker,type) : garantit l'idempotence.
CREATE UNIQUE INDEX IF NOT EXISTS ux_signaux_actifs
    ON signaux(ticker, type) WHERE statut='ACTIF';
-- Regle d'or : APPEND-ONLY. On ne touche jamais un signal eteint ;
-- une rechute cree un NOUVEAU signal (nouveau cycle, nouvel id).

CREATE TABLE IF NOT EXISTS liste_suivi (
    ticker TEXT PRIMARY KEY REFERENCES societes(ticker),
    date_ajout TEXT NOT NULL,
    note TEXT                       -- libre ; JAMAIS de quantite ni de prix
);
