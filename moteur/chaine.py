#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chaine.py — execution d'une chaine de scripts qui ne se tait jamais.

POURQUOI CE MODULE EXISTE (chantier C13, 30/09/2026). app.py::preparer_base()
lancait ses six scripts en `check=False, capture_output=True` puis rendait
`DB.exists()`. Un chargeur en echec rendait donc un code 1, jete, dont la sortie
d'erreur etait capturee puis abandonnee ; la fonction repondait « base
disponible ». Mesure par injection d'une panne dans charger_cours_quotidien.py :

    code de retour du chargeur ............ 1  (jete)
    valeur rendue par preparer_base() ..... True
    cours_quotidien_boc ................... 0 ligne
    dernier cours servi a l'ecran ......... 2026-07  (repli cours_mensuels)
    collecte/profils.json ................. 854 insertions / 857 suppressions,
                                            reecrit par profils.py sur la base
                                            degradee

C'est la regression n°2 de l'en-tete de tester_donnees.py rejouee a l'identique.

Regle appliquee ici : le premier echec ARRETE la chaine. Les scripts en aval, et
surtout profils.py, qui reecrit un fichier commite, ne tournent pas sur une base
construite sur un echec. Un script absent est un echec, pas une omission
tolerable : `continue` sur un fichier manquant etait le meme silence.
"""
import subprocess
import sys

QUEUE_STDERR = 600  # caracteres de sortie d'erreur conserves pour l'affichage


def executer_chaine(scripts, timeout=300, python=None):
    """Lance les scripts dans l'ordre. Rend la liste des ECHECS (vide si tout va bien).

    Chaque echec est un dict : {"script": nom, "code": int | None, "motif": str}.
    `code` vaut None quand le script n'a pas pu etre lance ou a depasse le delai.
    La chaine s'arrete au premier echec.
    """
    python = python or sys.executable
    for script in scripts:
        if not script.exists():
            return [{"script": script.name, "code": None,
                     "motif": f"script introuvable : {script}"}]
        try:
            r = subprocess.run([python, str(script)], cwd=str(script.parent),
                               check=False, capture_output=True, text=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return [{"script": script.name, "code": None,
                     "motif": f"delai de {timeout} s depasse"}]
        if r.returncode != 0:
            queue = (r.stderr or r.stdout or "").strip()[-QUEUE_STDERR:]
            return [{"script": script.name, "code": r.returncode,
                     "motif": queue or "aucune sortie"}]
    return []
