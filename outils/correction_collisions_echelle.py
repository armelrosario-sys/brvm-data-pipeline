#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier C18 — les collisions d'echelle de la serie de cours quotidienne
==========================================================================

Ce que ce script repare, et ce qu'il refuse de reparer
------------------------------------------------------
C18 recensait **cinq** seances ou le cours chute de plus de 60 % puis REVIENT
au niveau d'avant en quelques seances. Une division de nominal ne revient
jamais sur ses pas : le detecteur de la section 22 en concluait cinq « valeurs
d'une autre echelle deposees dans la serie ».

La mesure du 03/10/2026 (cycle 17) coupe ce lot en deux, et le registre de C18
se trompait de seance sur deux des cinq cas.

**TROIS sont bien des valeurs fautives, et se corrigent** :

  * ``SLBC 2022-01-12`` : 154,0 la ou la seance vaut 154 000. Facteur 1 000
    exact. Le PER publie SUR CETTE LIGNE (14,47) est celui des seances qui
    l'encadrent ; avec le BPA implicite 154 000 / 14,47 = 10 642,71, il rend
    154 000. Les deux seances encadrantes portent 154 000.
  * ``SLBC 2023-06-02`` : 67,6 la ou la seance vaut 67 600. Facteur 1 000 exact
    la aussi -- et **pas** 73 075 comme le registre de C18 le laissait croire en
    mesurant le facteur sur la seance d'avant. Le BPA implicite vaut 739,48 des
    deux cotes (73 075 / 98,82 le 01/06 et 62 530 / 84,56 le 05/06) ; le PER de
    la ligne, 91,41, rend donc 67 596, a 0,005 % de 67 600. Le cours de SLBC
    BAISSE pendant cette fenetre : la seance du 02/06 n'avait aucune raison de
    revenir a 73 075.
  * ``STBC 2018-07-12`` : 11 315 entre deux seances a 44 995. Ce n'est pas une
    erreur d'echelle -- 44 995 / 11 315 = 3,98, aucun facteur rond -- mais la
    valeur est fausse des deux cotes : le rendement publie sur la ligne meme,
    9,17 %, avec le dividende de 4 124 FCFA alors en vigueur, impose un cours
    entre 44 948 et 45 001 (bornes de l'arrondi a deux decimales). 11 315
    donnerait 36,45 %. La valeur retenue, 44 995, est celle des deux seances
    encadrantes et tombe dans cet intervalle.

**DEUX n'en sont pas, et ne se corrigent pas : ce sont de vraies divisions de
nominal.** Le detecteur signale la seance de CHUTE ; sur SAFC, la chute est
l'evenement reel et c'est le RETOUR qui est fautif.

  * ``SAFC 2018-12-21`` (5 300 -> 215) et ``SAFC 2019-01-02`` : la serie reste a
    215, 210, 200 pendant toute l'annee 2019 et ne remonte jamais. Preuve
    independante dans ``collecte/cours_extraits.csv`` : le dividende que le BOC
    publie pour SAFC passe de **576,00 a 23,04** entre le bulletin de novembre
    2018 et celui de decembre 2018, soit **exactement 576 / 23,04 = 25,0**.
    C'est une division de nominal au vingt-cinquieme, pas une collision. Ces
    deux seances restent telles quelles ; leur documentation releve de C4.

**Les deux vraies collisions de SAFC sont ailleurs**, et le texte d'ouverture de
C18 les nommait deja -- c'est son tableau, bati par le detecteur, qui s'etait
trompe de ligne. Elles sont PROUVEES mais **non corrigees par ce script** :

  * ``SAFC 2018-12-31`` : 5 300 au milieu de seances a 215. Cette ligne vient du
    bulletin MENSUEL de fin decembre 2018, versee par C15 ; ce bulletin porte
    deja le dividende rebase (23,04) mais un cours d'avant division. Preuve a
    deux cotes, et elle vient de la source elle-meme : le bulletin de **janvier
    2019** publie un cours de 200 et une variation annuelle de **-6,98 %**, ce
    qui impose une cloture 2018 de 200 / (1 - 0,0698) = **215,0**. Le BOC se
    contredit donc d'un bulletin a l'autre, et c'est son propre calcul de
    variation qui tranche.
  * ``SAFC 2019-01-04`` : 5 300 entre deux seances a 215 (03/01 et 07/01), autre
    reapparition de la valeur d'avant division.

**Pourquoi ce script ne les corrige pas.** Les corriger fait tomber la section
19 : cette ligne du quotidien est une COPIE de la ligne mensuelle, versee par
C15, et la section 19 exige l'egalite au franc entre les deux series sur toute
paire commune, plafond zero. La divergence serait reelle et le quotidien aurait
raison -- mais trancher laquelle des deux extractions fait foi, et inscrire une
exception nommee dans un controle bloquant, est un arbitrage de methode. Mesure,
prouve, pas ecrit : c'est la discipline ORANGE. Voir C30.

Effet attendu, et pourquoi il compte
-------------------------------------
Le defaut est LATENT : aucune des sept seances n'est un point de BPA annuel lu
par ``croissance_bpa_implicite``, aucune n'est la derniere seance, donc aucun
profil, grade ni gate d'aujourd'hui n'en depend. Ce qui en depend, c'est tout
backtest lisant la serie entiere -- et le depot en porte trois.

Effet sur les controles, mesure dans le cycle :

  * l'alerte des divisions de nominal de la section 7 tombe de **13 a 12** dates
    (STBC 2018-07-12 disparait) ; elle tombera a 10 quand C30 sera tranche, et a
    8 quand C4 documentera les deux divisions reelles trouvees ici ;
  * le registre ``COLLISIONS_ECHELLE`` de la section 22 tombe de **5 a 2** -- les
    deux SAFC, requalifiees, y restent le temps de C30 ;
  * plus aucune chute n'atteint -99,5 %, donc le seuil bas de la section 7, qui
    ecartait les deux SLBC en silence, est retire.

Garde-fous
----------
Comme ``outils/versement_mensuel_vers_quotidien.py`` : entete et comptes
attendus, ancres exactes avec assertion d'unicite, garde ``ATTENDU`` sur chaque
valeur AVANT ecriture (la valeur fautive ET les deux seances encadrantes),
empreinte SHA-256 du fichier avant et apres, reserialisation exigee a l'octet
pres avant toute ecriture, et relecture apres ecriture. Une relance sur un
fichier deja migre ne fait rien et le dit.

Usage : python3 outils/correction_collisions_echelle.py [--verifier]
        --verifier : ne touche a rien, dit seulement ou en est la correction.
"""

import csv
import hashlib
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUOTIDIEN = os.path.join(RACINE, "collecte", "cours_quotidien_boc.csv")

ENTETE = ["ticker", "date_bulletin", "cours", "per", "rendement"]

# Etat du fichier AVANT correction, mesure le 03/10/2026. Le script s'arrete si
# la realite en differe : c'est ce qui empeche d'ecrire dans un fichier qui a
# change de forme ou de taille depuis la redaction de celui-ci.
ATTENDU = {
    "lignes": 90660,
    "dates": 2029,
    "tickers": 47,
    "sha256_avant": "1ec8b539d857ba35bd6909948d821ca542676dd799c3f42e97912c40b4372c46",
    "corrigees": 3,
    "intactes": 4,
}

# Les sept seances tranchees par C18. Pour chacune : la valeur fautive attendue,
# la valeur retenue (None = on ne touche a rien), et les deux seances
# encadrantes avec leur cours attendu -- la preuve a deux cotes, verifiee a
# l'execution et non pas seulement ecrite dans ce commentaire.
#
# cle = (ticker, date) ; valeurs = dict(avant, apres, gauche, droite, motif)
CORRECTIONS = {
    ("SLBC", "2022-01-12"): {
        "avant": "154.0", "apres": "154000.0",
        "gauche": ("2022-01-11", "154000.0"),
        "droite": ("2022-01-13", "154000.0"),
        "motif": "facteur 1000 ; PER 14.47 de la ligne x BPA 10642.71 = 154000",
    },
    ("SLBC", "2023-06-02"): {
        "avant": "67.6", "apres": "67600.0",
        "gauche": ("2023-06-01", "73075.0"),
        "droite": ("2023-06-05", "62530.0"),
        "motif": "facteur 1000 ; PER 91.41 de la ligne x BPA 739.48 = 67596",
    },
    ("STBC", "2018-07-12"): {
        "avant": "11315.0", "apres": "44995.0",
        "gauche": ("2018-07-11", "44995.0"),
        "droite": ("2018-07-13", "44995.0"),
        "motif": "rendement 9.17 de la ligne avec dividende 4124 => cours dans "
                 "[44948 ; 45001] ; encadrantes a 44995",
    },
    # --- EN ATTENTE D'ARBITRAGE : mesurees, prouvees, PAS ecrites -----------
    # Corriger ces deux-la fait tomber la section 19 (confrontation des deux
    # series) : le mensuel porterait 5 300 la ou le quotidien porterait 215, et
    # ce controle exige l'egalite au franc sur toute paire commune, plafond
    # zero. La divergence serait REELLE -- le bulletin mensuel de decembre 2018
    # est lui-meme incoherent, dividende deja rebase a 23,04 et cours d'avant
    # division -- mais trancher laquelle des deux extractions fait foi, et
    # inscrire une exception nommee dans un controle bloquant, est un arbitrage
    # de methode qui revient a Claudia. Le cycle 17 mesure et s'arrete la.
    # Vu de plus pres : les 4 508 paires que la section 19 confronte sont
    # EXACTEMENT les lignes que C15 a copiees du mensuel vers le quotidien. Son
    # « 0 divergence » compare donc une copie a sa source. Inscrit en C30.
    ("SAFC", "2018-12-31"): {
        "avant": "5300.0", "apres": None,
        "gauche": ("2018-12-28", "215.0"),
        "droite": ("2019-01-02", "215.0"),
        "motif": "FAUTIVE, non corrigee : vaut 215 (bulletin de janvier 2019, "
                 "cours 200 et variation annuelle -6.98 % => cloture 2018 = 215.0) "
                 "mais la corriger fait tomber la section 19 — arbitrage C30",
    },
    ("SAFC", "2019-01-04"): {
        "avant": "5300.0", "apres": None,
        "gauche": ("2019-01-03", "215.0"),
        "droite": ("2019-01-07", "215.0"),
        "motif": "FAUTIVE, non corrigee : valeur d'avant division reapparue, "
                 "encadrantes a 215 — meme arbitrage C30 que le 31/12",
    },
    # Laissees telles quelles : vraies divisions de nominal, pas des collisions.
    ("SAFC", "2018-12-21"): {
        "avant": "215.0", "apres": None,
        "gauche": ("2018-12-20", "5300.0"),
        "droite": ("2018-12-24", "215.0"),
        "motif": "division de nominal 1:25 reelle (dividende BOC 576.00 -> "
                 "23.04 = /25 exact) ; a documenter dans C4, pas ici",
    },
    ("SAFC", "2019-01-02"): {
        "avant": "215.0", "apres": None,
        "gauche": ("2018-12-31", "5300.0"),
        "droite": ("2019-01-03", "215.0"),
        "motif": "la chute n'existe que par la ligne fautive du 31/12 ; une "
                 "fois celle-ci corrigee, cette seance n'est plus une chute",
    },
}

# Verifiee a l'execution sur cours_extraits.csv : c'est la preuve independante
# qui requalifie les deux SAFC en division de nominal. (ticker, bulletin) -> montant.
DIVIDENDES_TEMOINS = {
    ("SAFC", "20181130"): 576.0,
    ("SAFC", "20181231"): 23.04,
    ("SAFC", "20190131"): 23.04,
}
# Le bulletin de janvier 2019 : cours et variation annuelle qui ferment
# l'identite de la cloture 2018.
ANCRE_VARIATION = {"ticker": "SAFC", "bulletin": "20190131",
                   "cours": 200.0, "variation_annee": -6.98,
                   "cloture_2018_impliquee": 215.0}


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


def fin_de_ligne(texte):
    """Fin de ligne reellement utilisee par le fichier, jamais supposee."""
    i = texte.find("\n")
    if i <= 0:
        raise SystemExit("ERREUR : fichier sans fin de ligne exploitable")
    return "\r\n" if texte[i - 1] == "\r" else "\n"


def serialiser(lignes, fin):
    tampon = io.StringIO(newline="")
    ecrivain = csv.DictWriter(tampon, fieldnames=ENTETE, lineterminator=fin)
    ecrivain.writeheader()
    for ligne in lignes:
        ecrivain.writerow(ligne)
    return tampon.getvalue()


def controler_les_temoins():
    """Le dividende divise par 25 et l'identite de variation, relus a la source.

    Sans ce controle, la requalification des deux SAFC ne reposerait que sur un
    commentaire. Avec lui, le script refuse de tourner le jour ou la preuve
    s'evapore du depot.
    """
    chemin = os.path.join(RACINE, "collecte", "cours_extraits.csv")
    with open(chemin, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    index = {(r["ticker"], r["date_bulletin"]): r for r in lignes}
    for (ticker, bulletin), attendu in DIVIDENDES_TEMOINS.items():
        r = index.get((ticker, bulletin))
        if r is None:
            raise SystemExit("ERREUR : bulletin temoin absent de cours_extraits.csv : "
                             "%s %s" % (ticker, bulletin))
        vu = float(r["dividende_montant"])
        if abs(vu - attendu) > 1e-9:
            raise SystemExit("ERREUR : dividende temoin %s %s = %s (attendu %s) — la "
                             "preuve de la division 1:25 de SAFC a change, relire C18 "
                             "avant d'ecrire quoi que ce soit"
                             % (ticker, bulletin, vu, attendu))
    rapport = (DIVIDENDES_TEMOINS[("SAFC", "20181130")]
               / DIVIDENDES_TEMOINS[("SAFC", "20181231")])
    if abs(rapport - 25.0) > 1e-9:
        raise SystemExit("ERREUR : le rapport des dividendes SAFC vaut %.6f, pas 25" % rapport)

    a = ANCRE_VARIATION
    r = index.get((a["ticker"], a["bulletin"]))
    if r is None:
        raise SystemExit("ERREUR : bulletin d'ancrage %s %s absent" % (a["ticker"], a["bulletin"]))
    if abs(float(r["cours"]) - a["cours"]) > 1e-9:
        raise SystemExit("ERREUR : cours du bulletin d'ancrage = %s (attendu %s)"
                         % (r["cours"], a["cours"]))
    if abs(float(r["variation_annee"]) - a["variation_annee"]) > 1e-9:
        raise SystemExit("ERREUR : variation annuelle du bulletin d'ancrage = %s (attendu %s)"
                         % (r["variation_annee"], a["variation_annee"]))
    impliquee = a["cours"] / (1.0 + a["variation_annee"] / 100.0)
    if abs(impliquee - a["cloture_2018_impliquee"]) > 0.05:
        raise SystemExit("ERREUR : la cloture 2018 impliquee vaut %.3f, pas %.1f"
                         % (impliquee, a["cloture_2018_impliquee"]))
    print("temoins OK : dividende SAFC 576.00 -> 23.04 (/25 exact) ; bulletin 2019-01 "
          "cours 200 et variation -6.98 %% => cloture 2018 = %.1f" % impliquee)


def main():
    verifier_seulement = "--verifier" in sys.argv

    with open(QUOTIDIEN, "rb") as f:
        octets_avant = f.read()
    texte = octets_avant.decode("utf-8")
    fin = fin_de_ligne(texte)

    lecteur = csv.DictReader(io.StringIO(texte, newline=""))
    if lecteur.fieldnames != ENTETE:
        raise SystemExit("ERREUR : entete inattendue : %s" % lecteur.fieldnames)
    lignes = list(lecteur)

    if len(lignes) != ATTENDU["lignes"]:
        raise SystemExit("ERREUR : %d lignes (attendu %d)" % (len(lignes), ATTENDU["lignes"]))
    if len({r["date_bulletin"] for r in lignes}) != ATTENDU["dates"]:
        raise SystemExit("ERREUR : nombre de dates inattendu")
    if len({r["ticker"] for r in lignes}) != ATTENDU["tickers"]:
        raise SystemExit("ERREUR : nombre de tickers inattendu")

    # --- Ancres : une paire (ticker, jour) et une seule ---------------------
    index = {}
    for i, r in enumerate(lignes):
        cle = (r["ticker"], r["date_bulletin"])
        if cle in index:
            raise SystemExit("ERREUR : paire (ticker, jour) en double : %s" % (cle,))
        index[cle] = i

    # --- Reserialisation a l'octet pres, AVANT toute modification -----------
    temoin = serialiser(lignes, fin).encode("utf-8")
    if temoin != octets_avant:
        raise SystemExit("ERREUR : la reserialisation ne rend pas le fichier d'origine "
                         "a l'octet pres ; ne rien ecrire")

    controler_les_temoins()

    # --- Etat : deja applique, a appliquer, ou incoherent -------------------
    a_ecrire, deja, intacts = [], [], []
    for cle, c in sorted(CORRECTIONS.items()):
        i = index.get(cle)
        if i is None:
            raise SystemExit("ERREUR : seance absente du fichier : %s" % (cle,))
        vu = lignes[i]["cours"]
        if c["apres"] is None:
            if vu != c["avant"]:
                raise SystemExit("ERREUR : %s porte %s, attendu %s (seance laissee "
                                 "telle quelle par C18)" % (cle, vu, c["avant"]))
            intacts.append(cle)
            continue
        if vu == c["apres"]:
            deja.append(cle)
            continue
        if vu != c["avant"]:
            raise SystemExit("ERREUR : %s porte %s, ni la valeur fautive attendue (%s) "
                             "ni la valeur corrigee (%s) — ne rien ecrire"
                             % (cle, vu, c["avant"], c["apres"]))
        a_ecrire.append(cle)

    # --- Preuve a deux cotes, verifiee a l'execution ------------------------
    for cle, c in sorted(CORRECTIONS.items()):
        ticker = cle[0]
        for cote in ("gauche", "droite"):
            jour, cours = c[cote]
            j = index.get((ticker, jour))
            if j is None:
                raise SystemExit("ERREUR : seance encadrante absente : %s %s" % (ticker, jour))
            # La seance encadrante peut elle-meme etre corrigee par ce script
            # (SAFC 2019-01-02 est encadree par 2018-12-31). On accepte donc la
            # valeur d'avant comme celle d'apres.
            autre = CORRECTIONS.get((ticker, jour))
            attendues = {cours}
            if autre and autre["apres"]:
                attendues |= {autre["avant"], autre["apres"]}
            if lignes[j]["cours"] not in attendues:
                raise SystemExit("ERREUR : encadrante %s %s porte %s, attendu %s"
                                 % (ticker, jour, lignes[j]["cours"], sorted(attendues)))

    for cle in intacts:
        print("INTACTE  %s %s : %s" % (cle[0], cle[1], CORRECTIONS[cle]["motif"]))
    if len(intacts) != ATTENDU["intactes"]:
        raise SystemExit("ERREUR : %d seance(s) laissee(s) telle(s) quelle(s), attendu %d"
                         % (len(intacts), ATTENDU["intactes"]))
    for cle in deja:
        print("DEJA     %s %s -> %s" % (cle[0], cle[1], CORRECTIONS[cle]["apres"]))

    if not a_ecrire:
        print("correction DEJA APPLIQUEE : %d seance(s) corrigee(s), %d laissee(s) "
              "telle(s) quelle(s), rien a faire" % (len(deja), len(intacts)))
        return 0

    # Le fichier n'a pas encore ete touche : il doit etre celui qui a ete
    # mesure. La garde ne vaut que dans cet etat, sans quoi une relance apres
    # migration la ferait echouer -- ce qui casserait l'idempotence.
    if not deja and sha256(octets_avant) != ATTENDU["sha256_avant"]:
        raise SystemExit("ERREUR : empreinte du fichier avant correction = %s "
                         "(attendu %s) ; le fichier a change depuis la mesure, "
                         "ne rien ecrire" % (sha256(octets_avant), ATTENDU["sha256_avant"]))

    for cle in a_ecrire:
        c = CORRECTIONS[cle]
        print("A CORRIGER %s %s : %s -> %s  (%s)"
              % (cle[0], cle[1], c["avant"], c["apres"], c["motif"]))

    if verifier_seulement:
        print("--verifier : rien n'a ete ecrit")
        return 0

    for cle in a_ecrire:
        lignes[index[cle]]["cours"] = CORRECTIONS[cle]["apres"]

    nouveau = serialiser(lignes, fin).encode("utf-8")
    if len(nouveau.splitlines()) != len(octets_avant.splitlines()):
        raise SystemExit("ERREUR : le nombre de lignes a change ; ne rien ecrire")
    with open(QUOTIDIEN, "wb") as f:
        f.write(nouveau)

    # --- Relecture apres ecriture ------------------------------------------
    with open(QUOTIDIEN, "rb") as f:
        octets_apres = f.read()
    relues = list(csv.DictReader(io.StringIO(octets_apres.decode("utf-8"), newline="")))
    if len(relues) != ATTENDU["lignes"]:
        raise SystemExit("ERREUR : relecture : %d lignes" % len(relues))
    index2 = {(r["ticker"], r["date_bulletin"]): r for r in relues}
    for cle, c in CORRECTIONS.items():
        attendu = c["apres"] if c["apres"] is not None else c["avant"]
        if index2[cle]["cours"] != attendu:
            raise SystemExit("ERREUR : relecture : %s porte %s, attendu %s"
                             % (cle, index2[cle]["cours"], attendu))
    # Aucune autre case n'a bouge.
    avant_index = {(r["ticker"], r["date_bulletin"]): r
                   for r in csv.DictReader(io.StringIO(texte, newline=""))}
    bouges = [k for k, r in index2.items() if r != avant_index[k]]
    if sorted(bouges) != sorted(a_ecrire):
        raise SystemExit("ERREUR : relecture : lignes modifiees %s, attendu %s"
                         % (sorted(bouges), sorted(a_ecrire)))

    if len(a_ecrire) + len(deja) != ATTENDU["corrigees"]:
        raise SystemExit("ERREUR : %d seance(s) corrigee(s) au total, attendu %d"
                         % (len(a_ecrire) + len(deja), ATTENDU["corrigees"]))

    print("sha256 avant : %s" % sha256(octets_avant))
    print("sha256 apres : %s" % sha256(octets_apres))
    print("%d seance(s) corrigee(s), %d laissee(s) telle(s) quelle(s), "
          "%d ligne(s) au total inchangees" % (len(a_ecrire), len(intacts),
                                               len(relues) - len(a_ecrire)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
