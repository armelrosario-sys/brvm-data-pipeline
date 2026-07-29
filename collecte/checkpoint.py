#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collecte/checkpoint.py — (25/07/2026).

Sauvegarde intermediaire (commit + push) pendant un run long, pour ne plus
perdre le travail deja fait si le job echoue ou depasse son budget de temps.
Ne bloque jamais la collecte : un echec de sauvegarde est logge, jamais
fatal (les donnees restent sur disque de toute facon, un prochain
checkpoint reessaiera).

Usage dans un script de backfill :
    from checkpoint import sauvegarder
    ...
    for item in items:
        traiter(item)
        ecrire_immediatement_sur_disque(...)   # <- important, voir plus bas
        sauvegarder("message court")            # no-op sauf si 10 min ecoulees
    sauvegarder("message final", force=True)     # toujours en fin de run

IMPORTANT : ce module ne fait que commit+push ce qui est DEJA sur disque.
Chaque script doit ecrire ses resultats au fur et a mesure (une ligne CSV
des qu'un document est traite, pas tout accumule puis ecrit a la fin) --
sinon il n'y a rien de nouveau a sauvegarder entre deux checkpoints.
"""
import subprocess
import time

INTERVALLE_DEFAUT = 600  # 10 min
_dernier = {"t": 0.0}


def sauvegarder(message="Checkpoint automatique (auto)", intervalle=INTERVALLE_DEFAUT,
                 force=False, exclure=None):
    """exclure : liste de chemins a NE PAS committer sauf si force=True --
    utile pour un gros fichier qui change a chaque item traite (ex.
    collecte/_dividendes_observations.json) : le committer a CHAQUE
    checkpoint intermediaire (toutes les 10 min) gonfle l'historique Git de
    plusieurs Mo par commit inutilement. Avec exclure=[...], ce fichier
    n'est committe qu'au checkpoint final (force=True), une seule fois par
    run au lieu d'une dizaine de fois."""
    maintenant = time.time()
    if not force and (maintenant - _dernier["t"]) < intervalle:
        return False
    try:
        if exclure and not force:
            pathspec = ["--"] + ["."] + [f":!{p}" for p in exclure]
            subprocess.run(["git", "add", "-A"] + pathspec, check=True, capture_output=True, timeout=30)
        else:
            subprocess.run(["git", "add", "-A"], check=True, capture_output=True, timeout=30)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if diff.returncode == 0:
            _dernier["t"] = maintenant
            return False  # rien de nouveau depuis le dernier checkpoint
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True, timeout=30)
        if not exclure or force:
            # pull --rebase seulement si rien ne reste volontairement non
            # commite (sinon git le refuse : "unstaged changes")
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, capture_output=True, timeout=90)
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True, timeout=90)
        _dernier["t"] = maintenant
        print(f"[checkpoint] sauvegarde poussee : {message}")
        return True
    except subprocess.TimeoutExpired:
        print("[checkpoint] delai depasse, non bloquant -- le prochain checkpoint reessaiera")
        return False
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or b"").decode(errors="ignore")[:300]
        print(f"[checkpoint] echec non bloquant : {detail}")
        return False
