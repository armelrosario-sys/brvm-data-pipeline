#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Détecte les f-strings valides en Python 3.12 mais refusées en 3.11.

Le conteneur de développement tourne en 3.12 (PEP 701, qui a levé ces
restrictions) alors que les runners GitHub Actions sont en 3.11 : du code testé
localement peut échouer en production sur une simple erreur de syntaxe.

    python lint_fstring.py pipeline/*.py

Deux constructions sont refusées avant 3.12 :
  - une contre-oblique dans la partie expression
  - le même guillemet imbriqué dans l'expression

Le balayage se fait caractère par caractère : depuis 3.12 le tokenizer découpe
les f-strings en plusieurs jetons, un filtre sur STRING ne les voit plus.
"""
import sys

TRIPLES = ('"""', "'''")


def analyse(chemin):
    src = open(chemin, encoding="utf-8").read()
    ennuis = []
    i, ligne, n = 0, 1, len(src)

    while i < n:
        c = src[i]
        if c == "\n":
            ligne += 1
            i += 1
            continue
        if c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c not in "\"'":
            i += 1
            continue

        j, prefixe = i - 1, ""
        while j >= 0 and src[j].isalpha():
            prefixe = src[j].lower() + prefixe
            j -= 1
        quote = src[i:i + 3] if src[i:i + 3] in TRIPLES else c
        i += len(quote)
        est_f = "f" in prefixe
        profondeur, expr, depart = 0, [], ligne

        while i < n:
            if src[i] == "\n":
                ligne += 1
            if src[i] == "\\":
                if profondeur:
                    expr.append("\\")
                i += 2
                continue
            if profondeur and src[i] in "\"'":
                # chaine imbriquee dans l'expression : on la saute d'un bloc
                interne = src[i:i + 3] if src[i:i + 3] in TRIPLES else src[i]
                if interne == quote:
                    ennuis.append((depart, "guillemet identique imbrique",
                                   "".join(expr) + interne))
                i += len(interne)
                while i < n and not src.startswith(interne, i):
                    if src[i] == "\\":
                        i += 2
                        continue
                    if src[i] == "\n":
                        ligne += 1
                    expr.append(src[i])
                    i += 1
                i += len(interne)
                continue
            if src.startswith(quote, i):
                i += len(quote)
                break
            if est_f and src[i] == "{":
                if src.startswith("{{", i):
                    i += 2
                    continue
                profondeur += 1
                expr = []
                i += 1
                continue
            if est_f and src[i] == "}":
                if profondeur:
                    texte = "".join(expr)
                    if "\\" in texte:
                        ennuis.append((depart, "contre-oblique dans l'expression", texte))
                    if quote in texte:
                        ennuis.append((depart, "guillemet identique imbrique", texte))
                    profondeur -= 1
                    i += 1
                    continue
                if src.startswith("}}", i):
                    i += 2
                    continue
                i += 1
                continue
            if profondeur:
                expr.append(src[i])
            i += 1
    return ennuis


def main(chemins):
    total = 0
    for c in chemins:
        for ligne, motif, extrait in analyse(c):
            total += 1
            print(f"{c}:{ligne} — {motif} : {extrait.strip()[:70]}")
    if total:
        print(f"\n{total} construction(s) refusee(s) par Python 3.11.")
        return 1
    print(f"{len(chemins)} fichier(s) compatibles Python 3.11.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
