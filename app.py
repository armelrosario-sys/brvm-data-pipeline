#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app.py — Tableau de bord de PROFILAGE BRVM (Streamlit).

Remplace le site statique GitHub Pages. Principe editorial : la reponse
d'abord, la donnee ensuite ; l'incertitude est affichee au meme rang que le
resultat (grade A/B/C, statut de source, reserves), jamais en note de bas de
page. Aucun score composite, aucun classement decisionnel.

Deploiement : Streamlit Community Cloud, branche main, fichier app.py.
La base brvm.db n'est jamais commitee : elle est reconstruite au demarrage
depuis peupler.py + charger_cours.py (doctrine du depot conservee).
"""
import json
import sqlite3
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE / "moteur"))
from chaine import executer_chaine  # noqa: E402  (C13, 30/09/2026)
DB = RACINE / "moteur" / "brvm.db"
PROFILS = RACINE / "collecte" / "profils.json"

st.set_page_config(page_title="Profilage BRVM", page_icon="◆",
                   layout="wide", initial_sidebar_state="expanded")

COULEURS = {
    "GARP": "#1f4e79", "VALUE": "#2e7d8f", "GROWTH": "#4a7c59",
    "RENDEMENT": "#7d6608", "VIGILANCE_CONTRACTION": "#b45f3f",
    "AUCUN_PROFIL": "#6c757d", "RETOURNEMENT": "#7b5ea7",
    "MUTATION": "#9c6644", "NON_ANALYSABLE": "#adb5bd",
}
LIBELLES = {
    "GARP": "GARP — croissance a prix raisonnable",
    "VALUE": "VALUE — decote sur benefices etablis",
    "GROWTH": "GROWTH — expansion reguliere",
    "RENDEMENT": "RENDEMENT — revenu regulier, croissance nulle",
    "VIGILANCE_CONTRACTION": "VIGILANCE — benefices en contraction",
    "AUCUN_PROFIL": "AUCUN PROFIL — coeur de cote correctement paye",
    "RETOURNEMENT": "RETOURNEMENT — hors perimetre du profilage",
    "MUTATION": "MUTATION — historique non predictif",
    "NON_ANALYSABLE": "NON ANALYSABLE — donnees insuffisantes",
}
ORDRE = ["GARP", "VALUE", "GROWTH", "RENDEMENT", "AUCUN_PROFIL",
         "VIGILANCE_CONTRACTION", "RETOURNEMENT", "MUTATION", "NON_ANALYSABLE"]

# PER (02/10/2026, decision de Claudia) : partout ou le PER du BOC s'affiche, le
# PER glissant l'accompagne, juste a sa droite, et SEULEMENT quand il existe --
# case vide sinon, sans motif. Les analyses (axes, PEGY, medianes) lisent le
# glissant en priorite et le BOC a defaut : voir per_analyse dans profils.json.
AIDE_PER_BOC = ("PER publie par la BRVM au Bulletin Officiel de la Cote (BOC) : "
                "cours sur le benefice par action du dernier exercice clos.")
AIDE_PER_GLISSANT = ("PER sur douze mois glissants : meme cours, rapporte au benefice "
                     "des douze derniers mois (dernier exercice corrige des periodes "
                     "intermediaires publiees). Quand il existe, c'est lui que lisent "
                     "les analyses.")


def vide_si_absent(table, colonnes, decimales):
    """Case VIDE, et non "None", quand le PER glissant manque.

    st.dataframe (1.64) affiche "None" dans toute case nulle d'une colonne
    numerique, et ignore pour ces cases le na_rep et la couleur d'un Styler
    (verifie a l'ecran le 02/10/2026). La colonne devient donc TEXTE, mais un
    texte qui se TRIE comme un nombre : chaque valeur est cadree a droite sur
    une largeur fixe, completee d'espaces, et l'espace se classe avant tout
    chiffre -- "   9.1" passe devant "  12.9". Le defaut que C10 a corrige (un
    tri alphabetique qui met 9.3 apres 14.0) ne peut donc pas revenir. Un PER
    n'est jamais negatif : aucun signe ne vient perturber l'ordre."""
    table = table.copy()
    for c in colonnes:
        if c in table.columns:
            table[c] = table[c].map(
                lambda x: "" if pd.isna(x) else f"{x:>10.{decimales}f}")
    return table


def texte_per(r):
    """PER pour une infobulle : '12.93 (glissant 12.89)' ou '10.88'."""
    if pd.isna(r.per):
        return "n/d"
    if pd.notna(r.per_ttm):
        return f"{r.per:.2f} (glissant {r.per_ttm:.2f})"
    return f"{r.per:.2f}"

st.markdown("""<style>
.bloc-verite{border-left:4px solid #b45f3f;background:#faf6f4;padding:.8rem 1rem;
 border-radius:4px;font-size:.88rem;line-height:1.5;margin-bottom:1rem}
.grade{display:inline-block;padding:.1rem .5rem;border-radius:10px;font-size:.75rem;
 font-weight:600;color:#fff}
.puce{display:inline-block;padding:.15rem .6rem;border-radius:12px;font-size:.8rem;
 color:#fff;font-weight:600}
.reserve{font-size:.83rem;color:#5a5a5a;border-left:2px solid #ddd;padding-left:.7rem;
 margin:.25rem 0}
div[data-testid="stMetricValue"]{font-size:1.5rem}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Donnees
# ----------------------------------------------------------------------
QUOTIDIEN = RACINE / "collecte" / "cours_quotidien_boc.csv"


def empreinte_donnees():
    """Signature des donnees sources. Sert de CLE DE CACHE : quand un workflow
    commite de nouveaux cours, l'empreinte change et la base est reconstruite.

    Correctif du 03/09/2026 (constat direct de l'utilisateur : "les donnees ne
    sont pas regulierement actualisees"). Deux causes cumulees :
      1. le moteur et l'application lisaient cours_mensuels (bulletins de FIN DE
         MOIS, arretes au 07/07/2026) alors que la collecte quotidienne allait
         jusqu'au 01/09 — pres de deux mois de retard. Le pont
         charger_cours_quotidien.py existait depuis le 28/07 mais n'etait appele
         par personne ;
      2. @st.cache_resource sans cle ne se reinvalidait JAMAIS tant que le
         conteneur vivait : la base construite au premier lancement restait en
         place indefiniment, meme apres l'arrivee de nouvelles donnees.
    """
    # Ajout du 27/09/2026 : les donnees de reference du projet (etats
    # financiers, societes, dividendes) sont sorties de peupler.py vers
    # donnees/base/. Sans elles dans l'empreinte, corriger un resultat net
    # dans un CSV ne reconstruirait pas la base : le tableau de bord
    # afficherait l'ancienne valeur jusqu'au prochain redemarrage du
    # conteneur. C'est exactement le defaut du 03/09 decrit ci-dessus.
    parties = []
    base_ref = sorted((RACINE / "donnees" / "base").glob("*.csv"))
    # Ajout du 01/10/2026 (C17) : collecte/dividendes_boc.csv porte la colonne
    # « Dernier dividende paye » du bulletin, et charger_dividendes_boc.py la
    # charge desormais. Sans ce fichier dans l'empreinte, un nouveau dividende
    # collecte ne reconstruirait pas la base -- le defaut du 03/09 ci-dessus.
    for f in (QUOTIDIEN, RACINE / "collecte" / "cours_extraits.csv",
              RACINE / "collecte" / "dividendes_par_exercice.csv",
              RACINE / "collecte" / "dividendes_boc.csv",
              RACINE / "collecte" / "notations_financieres.csv",
              *base_ref):
        parties.append(f"{f.name}:{int(f.stat().st_mtime)}" if f.exists() else f"{f.name}:0")
    return "|".join(parties)


@st.cache_resource(show_spinner="Construction de la base (30 s au premier lancement)…")
def preparer_base(_empreinte):
    """Reconstruit brvm.db quand l'empreinte des sources change.
    La base n'est jamais commitee : elle est rebatie depuis les CSV du depot."""
    # Correctif du 28/09/2026 : cette liste omettait DEUX des quatre chargeurs de
    # collecte/, alors que pages.yml — la chaine qui construit la fiche publiee —
    # les enchaine tous. Mesure des deux bases construites depuis les memes CSV :
    # dividendes 311 par la chaine complete contre 15 ici (4,8 %), et
    # liquidite_quotidienne 73141 contre 0. Sur les 47 fiches : 308 lignes de
    # dividendes et 47/47 fiches non vides par la chaine complete, contre 12
    # lignes et 9/47 par celle-ci.
    #
    # Le defaut etait LATENT, pas actif : app.py ne lit aujourd'hui que societes,
    # etats_financiers, cours_mensuels et cours_quotidien_boc, et profils.json est
    # identique au champ pres entre les deux bases (verifie sur les 47 titres,
    # 0 ecart). Mais il etait arme : empreinte() inclut DEJA
    # collecte/dividendes_par_exercice.csv dans la clef de cache, donc modifier ce
    # CSV declenchait une "reconstruction" qui ne le relisait pas — et les scripts
    # tournent en check=False, capture_output=True, donc aucun echec ne se voit.
    # Le jour ou un onglet aurait affiche un historique de dividendes, il l'aurait
    # tire d'une table remplie a 4,8 % sans qu'aucune erreur ne s'affiche.
    #
    # Cout mesure de la correction : construction a froid 0,54 s -> 0,78 s,
    # soit +0,25 s. La section 17 de tester_donnees.py verrouille desormais
    # l'egalite entre cette liste et les chargeurs de collecte/.
    scripts = [RACINE / "moteur" / "peupler.py",
               RACINE / "collecte" / "charger_cours.py",
               RACINE / "collecte" / "charger_cours_quotidien.py",  # pont ajoute 03/09
               RACINE / "collecte" / "charger_dividendes_exercice.py",
               RACINE / "collecte" / "charger_dividendes_boc.py",  # C17, 01/10/2026
               RACINE / "collecte" / "charger_liquidite_quotidienne.py",
               RACINE / "moteur" / "profils.py"]
    # C13 (30/09/2026) : la boucle d'origine lancait chaque script en
    # check=False, capture_output=True puis rendait DB.exists(). Un chargeur en
    # echec (code 1) etait jete, et l'application servait le repli cours_mensuels
    # (2026-07) a la place du BOC collecte (2026-09-25), en reecrivant
    # collecte/profils.json au passage. La chaine s'arrete desormais au premier
    # echec et rend la liste des echecs ; l'appelant refuse de servir.
    return executer_chaine(scripts)


@st.cache_data(ttl=1800)
def charger(_empreinte):
    profils = json.loads(PROFILS.read_text(encoding="utf-8")) if PROFILS.exists() else {}
    conn = sqlite3.connect(DB)
    noms = dict(conn.execute("SELECT ticker, nom FROM societes").fetchall())
    # Source la plus fraiche disponible, avec repli explicite sur le mensuel.
    try:
        n_quot = conn.execute("SELECT COUNT(*) FROM cours_quotidien_boc").fetchone()[0]
    except Exception:
        n_quot = 0
    if n_quot:
        cours = pd.read_sql_query(
            "SELECT ticker, date_bulletin AS fin_mois, cours, per, rendement "
            "FROM cours_quotidien_boc WHERE cours IS NOT NULL ORDER BY date_bulletin", conn)
        origine_cours = "BOC quotidien"
    else:
        cours = pd.read_sql_query(
            "SELECT ticker, fin_mois, cours, per, rendement FROM cours_mensuels "
            "WHERE cours IS NOT NULL ORDER BY fin_mois", conn)
        origine_cours = "bulletins mensuels (repli)"
    etats = pd.read_sql_query(
        "SELECT ticker, exercice, resultat_net, capitaux_propres, statut_donnee, "
        "source_url, date_publication FROM etats_financiers ORDER BY ticker, exercice", conn)
    conn.close()
    lignes = []
    for t, v in profils.items():
        lignes.append(dict(
            ticker=t, nom=noms.get(t, t), profil=v.get("profil"),
            secondaire=v.get("secondaire"), grade=v.get("grade"),
            secteur=v.get("secteur"), per=v.get("per"),
            # C1 (30/09/2026) : "dy" alimente tris, medianes et tableaux ; il ne porte
            # que le rendement RECURRENT. Le rendement facial, exact, reste sur la fiche.
            dy=v.get("dy_recurrent", v.get("dy")), dy_facial=v.get("dy"),
            dist_non_rec=v.get("distribution_non_recurrente"),
            croissance=v.get("g"), source=v.get("source_croissance"),
            pegy=v.get("pegy"), payout=v.get("payout"), roe=v.get("roe"),
            ca=v.get("chiffre_affaires"), marge=v.get("marge_nette"),
            croissance_ca=v.get("croissance_ca"), roe_source=v.get("roe_source"),
            decote_pctl=v.get("decote_pctl"), croissance_pctl=v.get("croissance_pctl"),
            reference=v.get("reference_axes"), drapeaux=", ".join(v.get("drapeaux") or []),
            arbitrage=((v.get("arbitrage") or {}).get("drapeau") or ""),
            arbitrage_detail=((v.get("arbitrage") or {}).get("detail") or ""),
            confiance=v.get("confiance"), gate=v.get("gate"),
            motif=v.get("motif"), payout_source=v.get("payout_source"),
            part_op=v.get("part_operationnelle"),
            per_ttm=v.get("per_ttm"), ttm_detail=v.get("ttm_detail"),
            ttm_motif=v.get("ttm_motif"),
            # PER d'analyse (02/10/2026) : le glissant quand il existe, le BOC a
            # defaut. C'est lui que le moteur a lu pour les axes, le PEGY et les
            # medianes. "per" reste le PER publie par le BOC, affiche en premier.
            per_analyse=v.get("per_analyse", v.get("per")),
            per_source=v.get("per_source"),
            prime=v.get("prime_rendement"), taux_ref=v.get("taux_reference"),
            statut_cotation=v.get("statut_cotation", "NEGOCIABLE"),
            date_statut=v.get("date_statut_cotation"),
            historique_cotation=v.get("historique_cotation") or [],
            notation=(v.get("notation") or {}).get("note"),
            notation_agence=(v.get("notation") or {}).get("agence"),
            notation_perspective=(v.get("notation") or {}).get("perspective"),
            notation_date=(v.get("notation") or {}).get("date"),
            contradiction=bool(v.get("contradiction_notation"))))
    return pd.DataFrame(lignes), profils, cours, etats, origine_cours


@st.cache_data(ttl=3600)
def regime_marche(cours):
    """Condition 0 : ou en est le marche dans son cycle.

    BUG CORRIGE le 04/09/2026, signale par l'utilisateur ("l'evolution du marche
    en 24 mois depasse largement les 8 % affiches" — il avait raison) :
    l'ancienne version utilisait piv.shift(12) et shift(24), un decalage
    POSITIONNEL de 12 et 24 LIGNES. Sur des cours mensuels cela valait bien 12 et
    24 mois ; depuis la migration vers cours_quotidien_boc (03/09), cela ne valait
    plus que 12 et 24 SEANCES, soit environ deux semaines et demie et cinq
    semaines. Ecart mesure au 01/09/2026 : +5,6 % et +6,6 % affiches contre
    +93,0 % et +126,8 % reels.

    Ce n'etait PAS un simple defaut d'affichage : la condition 0 de regime est
    l'element dont la profondeur historique a montre qu'il domine tout le reste
    (0-25 % d'explosions en annee plate contre 75-100 % en reprise). Le tableau
    de bord annoncait "marche calme, les profils se lisent sans distorsion" alors
    que le marche est en FIN DE RALLYE a +93 % sur douze mois — soit exactement
    le regime ou les nouvelles entrees sont historiquement le moins bien
    recompensees. Le message inversait la lecture.

    Correctif : decalage TEMPOREL reel (DateOffset), independant de la frequence
    d'echantillonnage. Le calcul donne desormais le meme resultat que la source
    soit quotidienne, hebdomadaire ou mensuelle.
    """
    piv = cours.pivot_table(index="fin_mois", columns="ticker", values="cours").sort_index()
    piv.index = pd.to_datetime(piv.index)
    if piv.empty:
        return None, None, None, None, None
    fin = piv.index[-1]

    def variation(mois):
        cible = fin - pd.DateOffset(months=mois)
        anterieures = piv.index[piv.index <= cible]
        if not len(anterieures):
            return None
        v = (piv.loc[fin] / piv.loc[anterieures[-1]] - 1).median()
        return None if pd.isna(v) else float(v)

    def variation_annee():
        """Variation depuis le 1er janvier de l'annee en cours.

        Ajout du 24/09/2026, proposition de l'utilisatrice — et c'est la bonne
        convention : le bulletin officiel appelle "variation annuelle" la
        variation DEPUIS LE DEBUT DE L'ANNEE CIVILE, pas sur douze mois
        glissants. Mesure au 22/09/2026 : mediane des titres +53 % depuis le
        1er janvier, contre +55,00 % annonces par l'indice BRVM Composite. Les
        deux concordent enfin ; l'ecart residuel vient de la ponderation, l'indice
        pesant les titres par leur capitalisation la ou cette mesure les traite a
        egalite. L'ancien chiffre sur douze mois glissants (+78 %) semblait
        contredire l'indice sans raison.

        La reference est la derniere seance de l'annee precedente, lissee sur les
        dix jours qui la precedent : sans cela, toute la performance annuelle
        dependrait du cours d'un seul jour de cotation.
        """
        anterieures = piv.index[piv.index < pd.Timestamp(fin.year, 1, 1)]
        if not len(anterieures):
            return None, None
        derniere = anterieures[-1]
        fenetre = piv.loc[(piv.index >= derniere - pd.Timedelta(days=10))
                          & (piv.index <= derniere)]
        reference = fenetre.median() if not fenetre.empty else piv.loc[derniere]
        v = (piv.loc[fin] / reference - 1).median()
        return (None if pd.isna(v) else float(v)), derniere

    ytd, ref_ytd = variation_annee()
    return ytd, variation(12), variation(24), fin, ref_ytd


def puce(profil):
    return (f"<span class='puce' style='background:{COULEURS.get(profil, '#6c757d')}'>"
            f"{profil.replace('_', ' ')}</span>")


def badge_grade(g):
    couleur = {"A": "#1f4e79", "B": "#7d6608", "C": "#8a8a8a"}.get(g, "#8a8a8a")
    return f"<span class='grade' style='background:{couleur}'>grade {g}</span>"


emp = empreinte_donnees()
echecs_chaine = preparer_base(emp)
if echecs_chaine:
    # Ne pas figer l'echec dans le cache : le prochain rechargement doit retenter.
    preparer_base.clear()
    for e in echecs_chaine:
        st.error(f"**La base n'a pas pu etre construite** — `{e['script']}` a echoue "
                 f"(code {e['code'] if e['code'] is not None else 'n/a'}). "
                 f"Aucune donnee n'est servie plutot qu'une donnee de repli presentee "
                 f"comme celle du jour.\n\n```\n{e['motif']}\n```")
    st.stop()
if not DB.exists() or not PROFILS.exists():
    st.error("Base indisponible. Verifier que moteur/peupler.py et collecte/charger_cours.py "
             "s'executent sans erreur.")
    st.stop()
df, profils, cours, etats, origine_cours = charger(emp)
ytd, r12, r24, fin_cours, ref_ytd = regime_marche(cours)

# ----------------------------------------------------------------------
# Barre laterale
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Profilage BRVM")
    # Fraicheur comptee en SEANCES MANQUEES, pas en jours calendaires
    # (correctif 04/09/2026, question de l'utilisateur : "pourquoi des donnees du
    # 01 septembre pour estimer que nous sommes a jour, alors que nous sommes au
    # 04 ?"). Deux ajustements :
    #  - le compte se fait en jours OUVRES : un lundi apres un vendredi n'est pas
    #    un retard de 3 jours mais d'une seance ;
    #  - les seuils sont resserres. Sur des cours QUOTIDIENS, l'ancien seuil de
    #    5 jours calendaires laissait passer une semaine entiere de seances
    #    manquantes en affichant "a jour" — c'est ce qui a produit le message
    #    trompeur constate.
    # Une seance de decalage est NORMALE : le BOC du jour n'est publie qu'apres
    # la cloture, et le workflow P11 tourne en soiree.
    derniere = str(cours.fin_mois.max())[:10]
    try:
        import numpy as _np
        manquees = int(_np.busday_count(pd.Timestamp(derniere).date(),
                                        pd.Timestamp.today().date()))
    except Exception:
        manquees = None
    st.caption(f"{len(df)} titres · cours au **{derniere}** · source : {origine_cours}")
    if origine_cours != "BOC quotidien":
        st.warning("**REPLI** : la table des cours quotidiens est vide, les cours affiches "
                   "viennent des bulletins mensuels et ne sont PAS ceux du jour.")
    if manquees is not None:
        if manquees <= 1:
            st.success("Donnees a jour (derniere seance publiee)")
        elif manquees <= 3:
            st.warning(f"{manquees} seances manquantes — le BOC du jour n'est publie "
                       f"qu'apres cloture ; verifier P11 si cela persiste")
        else:
            st.error(f"{manquees} seances manquantes — la collecte quotidienne ne "
                     f"tourne plus correctement (workflows P11 / P9)")
    if st.button("Actualiser les donnees", width='stretch'):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.markdown("---")
    f_profil = st.multiselect("Profil", ORDRE, default=[])
    f_grade = st.multiselect("Grade de confiance", ["A", "B", "C"], default=[])
    f_secteur = st.multiselect("Secteur", sorted(df.secteur.dropna().unique()), default=[])
    f_contra = st.checkbox("Uniquement les contradictions avec une agence de notation")
    f_negoc = st.checkbox("Masquer les titres suspendus de cotation")
    st.markdown("---")
    st.markdown("""<div class='bloc-verite'><b>Ce que cet outil n'est pas</b><br>
    • Il ne cherche pas les hausses explosives : il en est structurellement l'anti-outil.<br>
    • Aucune superiorite de style n'est demontree sur la BRVM (et elle n'est pas
    testable en l'etat des donnees).<br>
    • Etiquettes descriptives, jamais decisionnelles. Le systeme ne decide seul
    d'aucune position.</div>""", unsafe_allow_html=True)

vue = df.copy()
if f_profil:
    vue = vue[vue.profil.isin(f_profil)]
if f_grade:
    vue = vue[vue.grade.isin(f_grade)]
if f_secteur:
    vue = vue[vue.secteur.isin(f_secteur)]
if f_contra:
    vue = vue[vue.contradiction]
if f_negoc:
    vue = vue[vue.statut_cotation != "SUSPENDU"]

st.title("Profilage fondamental — BRVM")

GLOSSAIRE = {
    "GARP": ("Croissance a prix raisonnable.",
             "Croissance entre 8 et 30 %/an, PEGY <= 1,5, distribution couverte.",
             "L'histoire : une croissance reelle que le prix n'a pas encore integree.",
             "Piege classique : une croissance passee tiree par un rebond ponctuel — "
             "les drapeaux 'rattrapage' signalent ce cas."),
    "VALUE": ("Decote sur benefices etablis.",
              "Decote dans le tercile superieur, croissance faible ou nulle, "
              "distribution couverte.",
              "L'histoire : la revalorisation, pas l'expansion.",
              "Piege classique : la value trap — une decote peut etre meritee. "
              "Sans catalyseur, le marche peut maintenir ce prix indefiniment."),
    "GROWTH": ("Expansion reguliere.",
               "Croissance dans le tercile superieur, positive chaque annee, reguliere.",
               "L'histoire : l'expansion ; la valorisation peut etre pleine.",
               "Piege classique : aucune marge de securite — une seule deception "
               "se paie immediatement sur le multiple."),
    "RENDEMENT": ("Revenu regulier, croissance nulle.",
                  "Rendement >= 4,8 %, payout <= 100 %, croissance quasi nulle.",
                  "L'histoire : le revenu — une quasi-obligation actions, profil "
                  "pleinement legitime sur la BRVM.",
                  "Piege classique : un payout qui derive au-dela de 100 %, ou une "
                  "remontee du taux souverain UEMOA qui rend le rendement banal."),
    "AUCUN_PROFIL": ("Coeur de cote correctement paye.",
                     "Aucune signature ne se declenche : ni decote, ni croissance "
                     "distinctive, ni rendement superieur.",
                     "Ce n'est pas un echec d'analyse : c'est un diagnostic. Le marche "
                     "price ce titre correctement, sans anomalie exploitable.",
                     "Attention : ce groupe recouvre cinq causes tres differentes "
                     "(croissance artefactuelle, croissance sous la fenetre, croissance "
                     "deja payee, distribution non couverte, croissance non calculable). "
                     "Le motif de chaque titre les distingue — le lire avant de conclure."),
    "VIGILANCE_CONTRACTION": ("Benefices en contraction.",
                              "Contraction superieure a 10 %/an, sans decote suffisante "
                              "pour la compenser.",
                              "L'histoire : le rendement affiche remunere un risque de "
                              "degradation, pas une valeur.",
                              "Une seule publication en inflexion positive reclasserait "
                              "le titre : a surveiller, pas a ecarter definitivement."),
    "RETOURNEMENT": ("Hors perimetre du profilage.",
                     "Pertes ou sortie de pertes avec un catalyseur public, date et "
                     "verifiable (config/faits_qualitatifs.yaml).",
                     "Ces dossiers relevent d'un outil distinct, qualitatif, a construire.",
                     "Taux de base mesures sur 2018-2026 pour ce compartiment : 33 % "
                     "d'explosion a 24 mois, 43 % de perte superieure a 30 %, "
                     "mediane -20 %. Le profilage ne les evalue pas."),
    "MUTATION": ("Historique non predictif.",
                 "Un evenement a change la nature economique de la societe (cession "
                 "transformante, changement de controle).",
                 "L'histoire est a reecrire : l'analyse reprend sur la nouvelle entite.",
                 "Deux exercices publies sur le nouveau perimetre sont necessaires "
                 "avant tout profil."),
    "NON_ANALYSABLE": ("Donnees insuffisantes.",
                       "PER absent ou benefices residuels, ou historique trop court.",
                       "Constat honnete, pas un jugement de valeur.",
                       "Indiquer ce qui manque et quand ce sera disponible : la plupart "
                       "de ces titres seront reclassables apres le backfill des bilans."),
}

with st.expander("Comprendre les profils — definitions, signatures et pieges", expanded=False):
    for prof in ORDRE:
        if prof not in GLOSSAIRE:
            continue
        titre, signature, histoire, piege = GLOSSAIRE[prof]
        st.markdown(f"{puce(prof)} &nbsp; **{titre}**", unsafe_allow_html=True)
        st.markdown(f"<div class='reserve'><b>Signature</b> — {signature}<br>"
                    f"<b>Lecture</b> — {histoire}<br>"
                    f"<b>A savoir</b> — {piege}</div>", unsafe_allow_html=True)
    st.caption("Les profils ne sont pas des cases exclusives : un titre peut porter un "
               "profil principal et un profil secondaire. Aucune superiorite de style "
               "n'est demontree sur la BRVM.")

o1, o2, o3, o4 = st.tabs(["Vue d'ensemble", "Explorer", "Fiche titre",
                          "Qualite des donnees & methode"])

# ----------------------------------------------------------------------
# 1. Vue d'ensemble
# ----------------------------------------------------------------------
with o1:
    if r12 is not None:
        if r12 > 0.35:
            lecture = ("**Fin de rallye.** Le marche a deja fortement re-rate : "
                       "les decotes sont rares et les profils de croissance sont "
                       "largement payes. Historiquement, c'est le regime ou les "
                       "nouvelles entrees sont les moins bien recompensees.")
        elif r12 < -0.05:
            lecture = ("**Marche en repli.** Regime historiquement le plus favorable "
                       "a la constitution de positions sur profils de qualite : "
                       "la majorite des doublements BRVM depuis 2018 partent de creux "
                       "de ce type, sur des titres deja valorises.")
        else:
            lecture = ("**Marche calme.** Ni euphorie ni capitulation : les profils "
                       "se lisent sans distorsion majeure de regime.")
        c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
        c1.metric(f"Depuis le 1er janvier {fin_cours.year}",
                  f"{ytd:+.0%}" if ytd is not None else "n/d",
                  help=("Progression MEDIANE des titres depuis la derniere seance de "
                        "l'an dernier"
                        + (f" ({ref_ytd.date()})" if ref_ytd is not None else "")
                        + ", reference lissee sur dix jours.\n\n"
                          "C'est la convention du bulletin officiel, qui appelle "
                          "'variation annuelle' la variation depuis le 1er janvier. "
                          "L'indice BRVM Composite affiche environ +55 % sur la meme "
                          "base : l'ecart restant vient de la ponderation, l'indice "
                          "pesant les titres par leur capitalisation la ou cette "
                          "mesure les traite a egalite."))
        c2.metric("Sur 12 mois glissants", f"{r12:+.0%}" if r12 is not None else "n/d",
                  help=("Progression mediane sur douze mois calendaires reels.\n\n"
                        "C'est cette mesure, et non la precedente, qui sert a "
                        "qualifier le regime de marche : les reperes historiques ont "
                        "ete etablis sur douze mois glissants."))
        c3.metric("Sur 24 mois", f"{r24:+.0%}" if r24 is not None else "n/d")
        c4.info(lecture)
    taux = df.taux_ref.dropna()
    if len(taux):
        tx = float(taux.iloc[0])
        au_dessus = int((df.prime.dropna() > 0).sum())
        st.warning(
            f"**Taux sans risque de la zone : {tx:.2%}** (obligations d'Etat UEMOA a "
            f"5 ans). Sur {int(df.prime.notna().sum())} titres, **{au_dessus}** rendent "
            f"davantage — et ceux-la portent un dividende exceptionnel ou non couvert. "
            f"Le rendement mediane de la cote est de {df.dy.median():.2f} %. "
            f"Autrement dit : acheter une action pour son revenu rapporte aujourd'hui "
            f"MOINS que preter a un Etat de la zone. La seule justification d'un achat "
            f"reste la croissance attendue.")

    susp = vue[vue.statut_cotation == "SUSPENDU"]
    if len(susp):
        noms = ", ".join(f"{r.ticker} ({r.nom})" for _, r in susp.iterrows())
        st.error(f"**{len(susp)} titre(s) suspendu(s) de cotation : {noms}.** "
                 f"Ces titres ne peuvent etre ni achetes ni vendus tant que la BRVM "
                 f"n'a pas leve la suspension. Leur profil reste affiche — il decrit "
                 f"les comptes, pas une opportunite accessible.")

    # Une suspension levee ne doit pas DISPARAITRE de l'affichage : l'episode
    # reste une information sur la societe. Sucrivoire, suspendue le 17/09 et
    # retablie le 22/09, repassait de "suspendue" a rien du tout, comme si
    # l'episode n'avait jamais eu lieu. On montre l'EVOLUTION.
    levees = []
    for _, r in vue.iterrows():
        h = r.historique_cotation or []
        if (r.statut_cotation == "NEGOCIABLE" and len(h) >= 2
                and h[0].get("type") == "REPRISE_COTATION"):
            susp = next((x for x in h[1:] if x.get("type") == "SUSPENSION"), None)
            if susp:
                levees.append((r.ticker, r.nom, susp.get("date"), h[0].get("date")))
    if levees:
        lignes_l = " · ".join(f"**{t}** ({n}) : suspendu le {d1}, retabli le {d2}"
                              for t, n, d1, d2 in levees)
        st.success(f"**Suspension levee recemment** — {lignes_l}. Le titre est de "
                   f"nouveau negociable. L'episode reste une information : une societe "
                   f"suspendue pour manquement a ses obligations de publication n'est "
                   f"pas dans la meme situation qu'une societe jamais inquietee.")

    st.markdown("#### Repartition des profils")
    st.caption("Cliquer sur un groupe pour afficher les societes qui le composent, "
               "avec le motif de chaque classement.")
    comptes = df.profil.value_counts().reindex(ORDRE).dropna()
    cols = st.columns(len(comptes)) if len(comptes) <= 5 else st.columns(5)
    for i, (prof, n) in enumerate(comptes.items()):
        with cols[i % len(cols)]:
            st.markdown(f"{puce(prof)}<br><span style='font-size:1.6rem;font-weight:700'>{int(n)}</span>",
                        unsafe_allow_html=True)
            st.caption(LIBELLES[prof].split("—")[1].strip() if "—" in LIBELLES[prof] else "")
            if st.button(f"Voir les {int(n)}", key=f"grp_{prof}", width='stretch'):
                st.session_state["groupe_ouvert"] = (
                    None if st.session_state.get("groupe_ouvert") == prof else prof)

    ouvert = st.session_state.get("groupe_ouvert")
    if ouvert:
        titre, signature, histoire, piege = GLOSSAIRE.get(ouvert, ("", "", "", ""))
        st.markdown("---")
        st.markdown(f"{puce(ouvert)} &nbsp; **{titre}** &nbsp; "
                    f"<span style='color:#666;font-size:.85rem'>{signature}</span>",
                    unsafe_allow_html=True)
        if piege:
            st.caption(piege)
        grp = df[df.profil == ouvert][
            ["ticker", "nom", "secteur", "grade", "per", "per_ttm", "dy", "croissance",
             "motif"]].copy()
        grp.columns = ["Ticker", "Societe", "Secteur", "Grade", "PER", "PER glissant",
                       "Rdt %", "Croiss. %/an", "Motif du classement"]
        st.dataframe(vide_si_absent(grp.sort_values(["Grade", "Ticker"]), ["PER glissant"],
                                    2), hide_index=True, width='stretch',
                     column_config={
                         "PER": st.column_config.NumberColumn(format="%.2f", help=AIDE_PER_BOC),
                         "PER glissant": st.column_config.TextColumn(
                             help=AIDE_PER_GLISSANT, alignment="right"),
                         "Rdt %": st.column_config.NumberColumn(format="%.1f"),
                         "Croiss. %/an": st.column_config.NumberColumn(format="%.1f"),
                         "Motif du classement": st.column_config.TextColumn(width="large")})

    st.markdown("---")
    tous_avis = []
    for t, v in profils.items():
        for a in (v.get("avis_recents") or []):
            tous_avis.append(dict(ticker=t, **a))
    if tous_avis:
        tous_avis.sort(key=lambda x: x.get("date") or "", reverse=True)
        critiques = [a for a in tous_avis
                     if a.get("type") in ("SUSPENSION", "FRACTIONNEMENT",
                                          "AUGMENTATION_CAPITAL", "RADIATION",
                                          "OPA_OPR", "RETARD_PUBLICATION")]
        titre_bloc = (f"Avis officiels BRVM — {len(critiques)} critique(s) "
                      f"sur {len(tous_avis)} recents")
        with st.expander(titre_bloc, expanded=bool(critiques)):
            st.caption("Suspensions, operations sur le capital, assemblees et "
                       "dividendes, collectes chaque jour ouvre sur brvm.org. "
                       "Les avis d'un titre figurent aussi sur sa fiche.")
            for a in (critiques or tous_avis)[:15]:
                lien = f" · [avis officiel]({a['url']})" if a.get("url") else ""
                st.markdown(f"- **{a.get('date')}** · `{a.get('type')}` · "
                            f"**{a['ticker']}** — {(a.get('titre') or '')[:110]}{lien}")
    else:
        st.info("Aucun avis BRVM collecte pour l'instant. Lancer le workflow "
                "**P13 - Veille des avis BRVM** depuis l'onglet Actions de GitHub.")

    st.markdown("#### Plan decote × croissance")
    n_plan = int((vue.decote_pctl.notna() & vue.croissance_pctl.notna()).sum())
    st.caption(f"**{n_plan} titres sur {len(vue)} positionnes.** Percentiles au sein du "
               "secteur si celui-ci compte au moins 8 titres, sinon au sein du marche "
               "(reference indiquee dans la fiche titre). Des rangs voisins ne sont pas "
               "significativement differents : lire des zones, pas des positions.")
    plan = vue.dropna(subset=["decote_pctl", "croissance_pctl"]).copy()
    # Une infobulle n'a pas a se trier : le PER y est donc une CHAINE, qui porte
    # le glissant entre parentheses quand il existe, et rien sinon.
    plan["PER"] = plan.apply(texte_per, axis=1)
    if len(plan):
        base = alt.Chart(plan).mark_circle(size=220, opacity=.85).encode(
            x=alt.X("decote_pctl:Q",
                    title="← plus cher          DECOTE (percentile)          moins cher →",
                    scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("croissance_pctl:Q", title="CROISSANCE (percentile) →",
                    scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("profil:N", scale=alt.Scale(
                domain=[p for p in ORDRE if p in plan.profil.unique()],
                range=[COULEURS[p] for p in ORDRE if p in plan.profil.unique()]),
                legend=alt.Legend(title="Profil", orient="right")),
            tooltip=["ticker", "nom", "profil", "grade", "PER", "dy", "croissance", "pegy"])
        texte = base.mark_text(dy=-14, fontSize=10, color="#333").encode(text="ticker:N")
        regles = (alt.Chart(pd.DataFrame({"v": [67]})).mark_rule(strokeDash=[4, 4], color="#bbb")
                  .encode(x="v:Q"))
        regles2 = (alt.Chart(pd.DataFrame({"v": [67]})).mark_rule(strokeDash=[4, 4], color="#bbb")
                   .encode(y="v:Q"))
        st.altair_chart((base + texte + regles + regles2).properties(height=460),
                        width='stretch')

        # Lecture du plan, titre par titre. Un nuage de points sans legende de
        # lecture laisse chacun interpreter les positions a sa facon ; ces phrases
        # sont derivees mecaniquement du quadrant, du profil et des drapeaux.
        def quadrant(ch, cr):
            if ch >= 67 and cr >= 67:
                return "Decote ET croissance", 0
            if ch < 67 <= cr:
                return "Croissance deja payee", 1
            if cr < 67 <= ch:
                return "Bon marche, sans dynamique", 2
            return "Ni decote ni croissance", 3

        def lecture(r, vv):
            bits = []
            dra = vv.get("drapeaux") or []
            if vv.get("statut_cotation") == "SUSPENDU":
                bits.append("**cotation suspendue**")
            if "RESULTAT_NON_OPERATIONNEL" in dra:
                bits.append("benefice non operationnel")
            if any(d in dra for d in ("RATTRAPAGE", "CAP_60", "BASE_ECRASEE", "PIC_YOY")):
                bits.append("croissance de rattrapage, non extrapolable")
            if "INFLEXION_RECENTE" in dra:
                bits.append("dernier exercice en recul")
            if pd.notna(r.prime) and r.prime > 0:
                bits.append(f"rend plus que l'Etat ({r.dy:.1f} %)")
            if vv.get("grade") == "C":
                bits.append("grade C : verifier avant usage")
            if not bits:
                if r.profil == "GARP":
                    bits.append("croissance encore payable au prix actuel")
                elif r.profil == "VALUE":
                    bits.append("decote sur des benefices etablis")
                elif r.profil == "VIGILANCE_CONTRACTION":
                    bits.append("benefices en recul")
                else:
                    bits.append("correctement paye, sans angle particulier")
            return " · ".join(bits)

        with st.expander(f"Lecture du plan — les {len(plan)} titres positionnes",
                         expanded=False):
            st.caption("Une ligne par titre, deduite de sa position, de son profil "
                       "et de ses drapeaux. A lire comme un point de depart, pas "
                       "comme un verdict : les rangs voisins ne sont pas "
                       "significativement differents.")
            plan2 = plan.copy()
            plan2["_q"] = [quadrant(r.decote_pctl, r.croissance_pctl)[1]
                           for _, r in plan2.iterrows()]
            noms_q = ["Decote ET croissance (quadrant favorable)",
                      "Croissance deja payee (haut a gauche)",
                      "Bon marche mais sans dynamique (bas a droite)",
                      "Ni decote ni croissance (bas a gauche)"]
            for q in range(4):
                sous = plan2[plan2._q == q].sort_values("decote_pctl", ascending=False)
                if not len(sous):
                    continue
                st.markdown(f"**{noms_q[q]}** — {len(sous)} titre(s)")
                for _, r in sous.iterrows():
                    vv = profils.get(r.ticker, {})
                    st.markdown(
                        f"- **{r.ticker}** ({r.nom}) · {r.profil.replace('_', ' ')} "
                        f"· grade {r.grade} — {lecture(r, vv)}")

        # --- Lecture du plan, titre par titre ---
        # Un nuage de points sans legende oblige chacun a reconstruire le sens de
        # chaque position. On explicite les quatre zones et ce que chaque titre y
        # fait, en une ligne.
        st.markdown("##### Comment lire ce plan")
        st.caption("Les pointilles marquent le tercile superieur de chaque axe. "
                   "Quatre zones en resultent. Rappel : ces percentiles sont "
                   "RELATIFS a la cote — un titre \"decote\" l'est par rapport aux "
                   "autres titres BRVM, pas dans l'absolu.")

        plan2 = plan.copy()
        plan2["zone"] = plan2.apply(
            lambda r: ("Decote ET croissance" if r.decote_pctl >= 67 and r.croissance_pctl >= 67
                       else "Croissance deja payee" if r.croissance_pctl >= 67
                       else "Bon marche sans dynamique" if r.decote_pctl >= 67
                       else "Ni l'un ni l'autre"), axis=1)

        # --- Un TABLEAU par cadran (02/10/2026, demande de Claudia) ------------
        #
        # Les quatre cadrans sortaient en listes a puces : une phrase par titre,
        # ou le PER, le rendement, la croissance et les signaux se suivaient
        # separes par des points mediums. Illisible des que le cadran passe
        # quatre ou cinq titres, et surtout IMPOSSIBLE A COMPARER -- l'oeil ne
        # peut pas aligner deux PER qui ne sont pas dans la meme colonne.
        #
        # Les colonnes restent NUMERIQUES et le formatage passe par
        # column_config : si les nombres etaient mis en forme en chaines, le tri
        # de l'en-tete redeviendrait alphabetique, et "9.3" se classerait apres
        # "14.0". C'est exactement le defaut que le chantier C10 a corrige dans
        # la table des dividendes -- ne pas le reintroduire ici.
        #
        # La decote est ajoutee en colonne : c'est la clef de tri des cadrans et
        # l'un des deux axes du plan, et le lecteur ne pouvait pas voir pourquoi
        # l'ordre etait celui-la.
        def _table_zone(sub):
            lignes = []
            for _, r in sub.iterrows():
                # L'ORDRE DES SIGNAUX EST DELIBERE, du plus grave au moins grave.
                # La colonne est la derniere et peut se tronquer quand un titre
                # en porte trois (STBC aujourd'hui) : ce qui disparait alors est
                # "rend plus que l'Etat", qui est une information, jamais une
                # cotation suspendue ni un benefice non representatif. Ne pas
                # reordonner cette liste sans refaire ce raisonnement.
                signaux = []
                if r.statut_cotation == "SUSPENDU":
                    signaux.append("COTATION SUSPENDUE")
                if "RATTRAPAGE" in str(r.drapeaux) or "CAP_" in str(r.drapeaux):
                    signaux.append("croissance de rattrapage")
                if "RESULTAT_NON_OPERATIONNEL" in str(r.drapeaux):
                    signaux.append("benefice non operationnel")
                if pd.notna(r.payout) and r.payout > 1:
                    signaux.append("dividende non couvert")
                if pd.notna(r.prime) and r.prime > 0:
                    signaux.append("rend plus que l'Etat")
                lignes.append({
                    "Code": r.ticker,
                    "Societe": r.nom,
                    "Profil": r.profil.replace("_", " ").lower(),
                    "Grade": r.grade,
                    "PER": r.per if pd.notna(r.per) else None,
                    "PER gl.": r.per_ttm if pd.notna(r.per_ttm) else None,
                    "Rendement": r.dy if pd.notna(r.dy) else None,
                    "Croissance": r.croissance if pd.notna(r.croissance) else None,
                    "Decote": r.decote_pctl if pd.notna(r.decote_pctl) else None,
                    "Signaux": " · ".join(signaux),
                })
            return vide_si_absent(pd.DataFrame(lignes), ["PER gl."], 1)

        # Largeurs en pixels plutot que "small"/"medium" : les huit premieres
        # colonnes sont calibrees sur leur contenu reel, pour que la colonne
        # Signaux recoive tout le reste. Avec les largeurs par defaut elle etait
        # tronquee des qu'un titre portait deux signaux, et "benefice non
        # representatif · croissance de rattrapage" se coupait au milieu --
        # exactement ce que ce tableau est cense eviter. Le composant ne sait pas
        # revenir a la ligne dans une cellule (ni TextColumn ni st.dataframe ne
        # l'offrent en 1.64) : la seule marge de manoeuvre est la largeur.
        COLONNES_ZONE = {
            "Code": st.column_config.TextColumn("Code", width=56),
            "Societe": st.column_config.TextColumn("Societe", width=150),
            "Profil": st.column_config.TextColumn("Profil", width=95),
            "Grade": st.column_config.TextColumn("Grade", width=52),
            "PER": st.column_config.NumberColumn(
                "PER", format="%.1f", width=58, help=AIDE_PER_BOC),
            "PER gl.": st.column_config.TextColumn(
                "PER gl.", width=58, help=AIDE_PER_GLISSANT, alignment="right"),
            "Rendement": st.column_config.NumberColumn(
                "Rdt", format="%.1f %%", width=64,
                help="Dernier dividende sur cours. Les titres a dividende perime "
                     "ou exceptionnel sont hors classement (chantier C1)."),
            "Croissance": st.column_config.NumberColumn(
                "Croissance", format="%+.0f %%/an", width=82,
                help="Croissance moyenne du benefice sur les exercices disponibles."),
            "Decote": st.column_config.NumberColumn(
                "Decote", format="P%d", width=60,
                help="Rang de decote, de P0 a P100, RELATIF a la cote BRVM. "
                     "C'est l'axe horizontal du plan et la clef de tri."),
            "Signaux": st.column_config.TextColumn("Signaux", width="large"),
        }

        ZONES = {
            "Decote ET croissance": (
                "**Haut a droite — decote ET croissance.** La zone la plus "
                "recherchee : le titre croit et n'est pas encore paye pour cela. "
                "C'est par construction l'endroit ou se trouvent les profils GARP."),
            "Croissance deja payee": (
                "**Haut a gauche — croissance deja payee.** Ces societes croissent, "
                "mais le marche l'a compris avant vous. Attention : plusieurs y sont "
                "pour une croissance de rattrapage, non extrapolable."),
            "Bon marche sans dynamique": (
                "**Bas a droite — bon marche, sans dynamique.** On y trouve autant "
                "de profils de rendement legitimes que de pieges a valeur : la "
                "decote peut etre meritee."),
            "Ni l'un ni l'autre": (
                "**Bas a gauche — ni decote, ni croissance.** La zone la moins "
                "attrayante, ou se concentrent logiquement les benefices en recul."),
        }
        for zone in ["Decote ET croissance", "Croissance deja payee",
                     "Bon marche sans dynamique", "Ni l'un ni l'autre"]:
            sub = plan2[plan2.zone == zone].sort_values("decote_pctl", ascending=False)
            if not len(sub):
                continue
            st.markdown(ZONES[zone] + f"  ({len(sub)} titre(s))")
            st.dataframe(_table_zone(sub), hide_index=True, use_container_width=True,
                         height=38 + 35 * len(sub), column_config=COLONNES_ZONE)

        # Les titres hors axes ne doivent pas DISPARAITRE du tableau de bord :
        # un plan qui n'affiche que 34 titres sur 47 laisse croire que les 13
        # autres n'existent pas, alors qu'ils portent un diagnostic explicite.
        hors = vue[vue.decote_pctl.isna() | vue.croissance_pctl.isna()]
        if len(hors):
            with st.expander(f"{len(hors)} titre(s) hors du plan — pourquoi",
                             expanded=False):
                st.caption("Un titre n'apparait sur le plan que s'il a une position "
                           "sur les DEUX axes. Les profils Retournement, Mutation et "
                           "Non analysable sont hors perimetre par construction ; "
                           "les autres ont un axe manquant, ce qui est une lacune de "
                           "donnees et non un diagnostic.")
                h = hors[["ticker", "nom", "profil", "grade", "decote_pctl",
                          "croissance_pctl", "motif"]].copy()
                h["Axe manquant"] = h.apply(
                    lambda r: "les deux" if pd.isna(r.decote_pctl) and pd.isna(r.croissance_pctl)
                    else ("croissance" if pd.isna(r.croissance_pctl) else "decote"), axis=1)
                h = h[["ticker", "nom", "profil", "grade", "Axe manquant", "motif"]]
                h.columns = ["Ticker", "Societe", "Profil", "Grade", "Axe manquant",
                             "Motif"]
                st.dataframe(h.sort_values(["Profil", "Ticker"]), hide_index=True,
                             width='stretch',
                             column_config={"Motif": st.column_config.TextColumn(width="large")})
    else:
        st.info("Aucun titre positionnable avec les filtres actuels "
                "(les profils hors axes n'ont pas de percentile).")

# ----------------------------------------------------------------------
# 2. Explorer
# ----------------------------------------------------------------------
with o2:
    st.caption("Le grade dit ce que vaut l'etiquette : "
               "**A** source certifiee et etiquette stable · **B** solide, reserve nommee · "
               "**C** travail complementaire requis avant tout usage.")
    # Le PER glissant figure ici des le 02/10/2026 : c'est la seule vue ou il se
    # TRIE et s'exporte, donc la seule ou il se compare d'un titre a l'autre.
    aff = vue[["ticker", "nom", "secteur", "profil", "secondaire", "grade", "per",
               "per_ttm", "dy",
               "croissance", "source", "pegy", "payout", "drapeaux",
               "arbitrage", "notation", "contradiction", "motif"]].copy()
    aff.columns = ["Ticker", "Societe", "Secteur", "Profil", "Secondaire", "Grade",
                   "PER", "PER glissant", "Rdt %", "Croiss. %/an", "Source croissance",
                   "PEGY", "Payout", "Drapeaux", "Arbitrage", "Notation",
                   "Contradiction", "Motif"]
    st.dataframe(
        vide_si_absent(aff.sort_values(["Grade", "Profil", "Ticker"]), ["PER glissant"],
                       2), hide_index=True,
        width='stretch', height=560,
        column_config={
            "PER": st.column_config.NumberColumn(format="%.2f", help=AIDE_PER_BOC),
            "PER glissant": st.column_config.TextColumn(
                width=100, help=AIDE_PER_GLISSANT, alignment="right"),
            "Rdt %": st.column_config.NumberColumn(format="%.1f"),
            "Croiss. %/an": st.column_config.NumberColumn(format="%.1f"),
            "PEGY": st.column_config.NumberColumn(format="%.2f"),
            "Payout": st.column_config.NumberColumn(format="%.2f"),
            "Motif": st.column_config.TextColumn(width="large"),
        })
    st.download_button("Telecharger (CSV)", aff.to_csv(index=False).encode("utf-8"),
                       "profilage_brvm.csv", "text/csv")

# ----------------------------------------------------------------------
# 3. Fiche titre
# ----------------------------------------------------------------------
with o3:
    choix = st.selectbox("Titre", sorted(df.ticker),
                         format_func=lambda t: f"{t} — {df.set_index('ticker').nom.get(t, t)}")
    v = profils.get(choix, {})
    r = df.set_index("ticker").loc[choix]
    g1, g2 = st.columns([3, 2])
    with g1:
        st.markdown(f"## {choix} — {r.nom}")
        st.markdown(
            puce(v.get("profil", "n/d"))
            + (f" &nbsp; <span class='puce' style='background:#8fa9c2'>secondaire : "
               f"{v['secondaire'].replace('_', ' ')}</span>" if v.get("secondaire") else "")
            + " &nbsp; " + badge_grade(v.get("grade", "C")), unsafe_allow_html=True)
        st.caption(LIBELLES.get(v.get("profil"), ""))
    with g2:
        cmp_haut = v.get("comparaisons") or {}
        def _ctx(cle, unite=""):
            c = cmp_haut.get(cle)
            if not c:
                return None
            ms = f"{c['mediane_secteur']:.2f}{unite}" if c["mediane_secteur"] is not None else "n/d"
            mm = f"{c['mediane_marche']:.2f}{unite}" if c["mediane_marche"] is not None else "n/d"
            return (f"Mediane du secteur {r.secteur} : {ms} (n={c['n_secteur']})"
                    + ("  — secteur trop etroit pour etre significatif"
                       if c["n_secteur"] < 8 else "")
                    + f"\n\nMediane du marche analysable : {mm} (n={c['n_marche']})")
        # C23, 02/10/2026 : le PER normalise sortait ici, en aide et en delta.
        # Retire des deux. Le PER affiche est celui du BOC, et il est juste :
        # verifie contre brvm.org le 01/10, BOAN et BICC a 0,0 % une fois
        # appliquee la variation de seance du jour.
        #
        # PER GLISSANT (TTM), 02/10/2026. Revu le meme jour sur demande de
        # Claudia : le PER du BOC vient EN PREMIER, et le PER glissant se place A
        # COTE, en seconde metrique, UNIQUEMENT quand il existe. Quand il manque,
        # rien n'est affiche, ni valeur, ni motif : l'absence est la norme tant
        # que C26 n'a pas rempli les publications intermediaires, et la repeter
        # sur 46 fiches sur 47 n'apprenait rien. Le motif reste dans
        # profils.json (ttm_motif) pour qui en a besoin.
        aide_per = (_ctx("per") or "") + ("\n\n" if _ctx("per") else "") + \
            AIDE_PER_BOC
        ecart_ttm = ((r.per_ttm / r.per - 1) * 100
                     if pd.notna(r.per_ttm) and pd.notna(r.per) and r.per else None)
        p1, p2 = st.columns(2)
        p1.metric("PER (BOC)", f"{r.per:.2f}" if pd.notna(r.per) else "n/d", help=aide_per)
        if pd.notna(r.per_ttm):
            # Le delta porte l'ECART SIGNE au PER du BOC : Streamlit lit le signe
            # pour orienter sa fleche (une valeur sans signe affichait une fleche
            # montante sur un glissant plus bas).
            p2.metric("PER glissant (12 mois)", f"{r.per_ttm:.2f}",
                      delta=(f"{ecart_ttm:+.1f} % vs BOC" if ecart_ttm is not None else None),
                      delta_color="off", help=str(r.ttm_detail or ""))
        if isinstance(r.dist_non_rec, str) and r.dist_non_rec:
            st.warning(f"**Rendement facial {r.dy_facial:.1f} % — hors classement.** {r.dist_non_rec}")
        st.metric("Rendement", f"{r.dy_facial:.1f} %" if pd.notna(r.dy_facial) else "n/d",
                  delta=(f"{r.prime*100:+.1f} pts vs Etat" if pd.notna(r.prime) else None),
                  help=(_ctx("dy", " %") or "") + "\n\nConvention brut/net du champ "
                       "rendement du BOC : chantier de verification ouvert.")

    hist_cot = v.get("historique_cotation") or []
    if v.get("statut_cotation") == "NEGOCIABLE" and len(hist_cot) >= 2:
        st.success("**Cotation retablie le %s** apres une suspension le %s. Le titre "
                   "est de nouveau negociable ; l'episode reste une information sur "
                   "la societe."
                   % (hist_cot[0].get("date"),
                      next((x.get("date") for x in hist_cot[1:]
                            if x.get("type") == "SUSPENSION"), "?")))
    if v.get("statut_cotation") == "SUSPENDU":
        st.error(f"**Cotation suspendue depuis le {v.get('date_statut_cotation')}.** "
                 f"Ce titre ne peut etre ni achete ni vendu jusqu'a la levee de la "
                 f"suspension par la BRVM. Tout ce qui suit decrit ses comptes, pas "
                 f"une opportunite accessible.")

    for n in (v.get("notes") or []):
        if n.startswith("AVIS BRVM") or n.startswith("CONTREDIT PAR L'EXERCICE"):
            st.warning(n)

    if v.get("roe") is None and v.get("roe_exercice"):
        st.caption(f"ROE non affiche : les capitaux propres en base datent de "
                   f"{v['roe_exercice']}. Un ratio calcule sur des fonds propres aussi "
                   f"anciens induirait en erreur.")

    if v.get("motif"):
        st.info(f"**Pourquoi ce profil** — {v['motif']}")

    # Arbitrage contre une source exterieure (26/09/2026). Le croisement ne se
    # contente pas de signaler : il retient une valeur et nomme sa source. On
    # affiche donc les trois -- verdict, consequence, detail chiffre -- au lieu
    # de laisser le lecteur deviner ce que le drapeau a change.
    arb = v.get("arbitrage") or {}
    if arb.get("drapeau"):
        TITRES = {
            "CROISSANCE_CORROBOREE": (
                st.success, "Croissance corroboree",
                "Une source exterieure independante lit le meme glissement sur le "
                "dernier exercice. La transcription des comptes est confirmee ; "
                "cela ne dit rien de l'origine du benefice."),
            "ECART_AGREGATEUR": (
                st.warning, "Ecart avec une source exterieure",
                "La valeur certifiee est CONSERVEE, mais le perimetre (consolide "
                "ou part du groupe) reste a verifier sur le document."),
            "VALEUR_REPRISE_AGREGATEUR": (
                st.warning, "Valeur reprise d'une source exterieure",
                "La ligne en base venait d'un OCR a source unique, jamais "
                "certifiable : c'est la source exterieure qui a ete retenue."),
            "FONDAMENTAL_EN_RETARD": (
                st.warning, "Exercice publie manquant en base",
                "Le profil ci-dessous porte sur des comptes perimes."),
            "PERMUTATION_PROBABLE": (
                st.error, "Profil suspendu — colonnes permutees",
                "Le resultat net et son comparatif N-1 sont inverses en base. "
                "Aucun profil n'est publie tant que la saisie n'est pas corrigee."),
            "PERMUTATION_SUSPECTEE": (
                st.error, "Profil suspendu — permutation suspectee",
                "Une seule des deux identites de controle est verifiee. A arbitrer "
                "sur le document avant tout usage."),
            "CROISSANCE_CONTESTEE": (
                st.error, "Axe croissance retire",
                "Deux sources donnent des glissements inconciliables et aucune "
                "regle ne peut trancher."),
        }
        afficher, titre, consequence = TITRES.get(
            arb["drapeau"], (st.info, arb["drapeau"], ""))
        afficher(f"**{titre}** — {consequence}")
        if arb.get("detail"):
            st.caption(f"Regle {arb.get('regle')} : {arb['detail']}")

    notation = v.get("notation")
    if notation and notation.get("note"):
        n_prec = notation.get("note_precedente")
        sens = ""
        if n_prec and n_prec != notation["note"]:
            sens = f" (precedemment {n_prec})"
        ligne = (f"**Notation {notation.get('agence') or 'agence'}** : "
                 f"{notation['note']}{sens} · perspective "
                 f"{notation.get('perspective') or 'n/d'} · {notation.get('date')}")
        if v.get("contradiction_notation"):
            st.warning(ligne + "\n\n**Cette opinion contredit le profil ci-dessus.** "
                       "Le profilage n'a pas ete modifie : c'est a l'analyste de "
                       "trancher, en verifiant d'abord la source de croissance.")
        else:
            st.caption(ligne)
        st.caption("Une notation mesure le risque de CREDIT, pas l'attractivite "
                   "actionnaire : une note elevee n'est jamais un profil GARP.")

    comp = v.get("comparaisons") or {}

    def contexte(cle, unite="", pct=False):
        """Infobulle : valeur du titre replacee dans son secteur et dans le marche."""
        c = comp.get(cle)
        if not c:
            return "Comparaison sectorielle indisponible pour ce titre."
        def fmt(x):
            if x is None:
                return "n/d"
            return f"{x*100:.0f} %" if pct else f"{x:.2f}{unite}"
        return (f"Ce titre : {fmt(c['titre'])}\n\n"
                f"Mediane du secteur {r.secteur} : {fmt(c['mediane_secteur'])} "
                f"(n={c['n_secteur']})"
                + ("  — secteur trop etroit pour etre significatif"
                   if c["n_secteur"] < 8 else "")
                + f"\n\nMediane du marche analysable : {fmt(c['mediane_marche'])} "
                  f"(n={c['n_marche']})")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Croissance", f"{r.croissance:+.1f} %/an" if pd.notna(r.croissance) else "n/d",
              help=f"Source : {r.source}\n\n" + contexte("g", " %"))
    m2.metric("PEGY", f"{r.pegy:.2f}" if pd.notna(r.pegy) else "n/d",
              help="PER / (croissance % + rendement %). Lynch 1989 ; fondement Easton 2004. "
                   "Sous 0,25 : protocole de revue obligatoire."
                   + ("\n\nCalcule sur le PER glissant." if r.per_source == "GLISSANT" else ""))
    m3.metric("Payout", f"{r.payout:.0%}" if pd.notna(r.payout) else "non disponible",
              help=(f"Source : {r.payout_source}\n\n" if pd.notna(r.payout_source) else "")
                   + contexte("payout", pct=True))
    aide_roe = contexte("roe", " %") or ""
    if r.roe_source == "AGREGATEUR" and v.get("source_capitaux_propres"):
        aide_roe += ("\n\nCapitaux propres absents de la base : repris d'un rapport "
                     "de notation.\n\n" + str(v["source_capitaux_propres"]))
    m4.metric("ROE", f"{r.roe:.1f} %" if pd.notna(r.roe) else "non disponible",
              help=aide_roe)

    # Activite (27/09/2026) : chiffre d'affaires, marge nette et croissance du
    # chiffre d'affaires viennent de la chaine pipeline/, qui les tient pour 47
    # titres sur 47. Le moteur ne les avait PAS DU TOUT. Ils repondent a une
    # question que les ratios de valorisation ne posent jamais : l'entreprise
    # vend-elle plus, et gagne-t-elle de l'argent en vendant ?
    if pd.notna(r.ca):
        a1, a2, a3 = st.columns(3)
        a1.metric("Chiffre d'affaires", f"{r.ca:,.0f} M".replace(",", " "),
                  help="Dernier exercice publie. Source : chaine pipeline/ "
                       "(Sikafinance), recoupee avec le bulletin officiel.")
        a2.metric("Marge nette", f"{r.marge:.1f} %" if pd.notna(r.marge) else "n/d",
                  help="Resultat net rapporte au chiffre d'affaires. Se lit dans son "
                       "secteur : une marge bancaire et une marge de distribution "
                       "ne se comparent pas.")
        a3.metric("Croissance du CA",
                  f"{r.croissance_ca:+.1f} %" if pd.notna(r.croissance_ca) else "n/d",
                  help="Glissement d'un exercice sur le precedent. A confronter a la "
                       "croissance du resultat : un CA qui monte alors que le resultat "
                       "recule signale une marge qui se comprime.")
        if pd.notna(r.marge) and pd.notna(r.croissance_ca) and pd.notna(r.croissance):
            if r.croissance_ca > 5 and r.croissance < 0:
                st.caption("**Lecture** — le chiffre d'affaires progresse alors que le "
                           "resultat recule : la marge se comprime. L'activite tient, "
                           "la rentabilite non.")
            elif r.croissance_ca < 0 and r.croissance > 5:
                st.caption("**Lecture** — le resultat progresse alors que le chiffre "
                           "d'affaires recule : la hausse vient des couts ou du bas du "
                           "compte de resultat, pas des ventes.")

    # Origine du resultat : la question que le cas AGL CI a rendue incontournable.
    if pd.notna(r.part_op):
        pct = r.part_op * 100
        libelle = (f"**Origine du resultat** — le resultat d'exploitation represente "
                   f"{pct:.0f} % du resultat net.")
        if "RESULTAT_NON_OPERATIONNEL" in str(v.get("drapeaux") or ""):
            st.warning(libelle + " Le benefice provient donc majoritairement du "
                       "financier ou de l'exceptionnel : **une croissance de ce "
                       "resultat ne mesure pas la dynamique du metier**. Jurisprudence "
                       "AGL CI, dont le resultat net a chute de 96 % l'exercice "
                       "suivant un profil GARP construit sur des produits financiers.")
        else:
            st.caption(libelle + " Le benefice vient bien du metier.")
    elif v.get("profil") not in ("NON_ANALYSABLE", "MUTATION"):
        st.caption("**Origine du resultat** — non disponible : le resultat "
                   "d'exploitation n'est pas encore extrait pour ce titre.")

    if pd.notna(r.decote_pctl):
        st.markdown(f"**Positionnement** — decote P{int(r.decote_pctl)} · "
                    f"croissance P{int(r.croissance_pctl) if pd.notna(r.croissance_pctl) else '—'} "
                    f"· reference : {r.reference}")

    if v.get("notes"):
        st.markdown("**Constats et points d'attention**")
        for n in v["notes"]:
            st.markdown(f"<div class='reserve'>{n}</div>", unsafe_allow_html=True)
    st.markdown("**Reserves attachees a cette etiquette**")
    for res in v.get("reserves", []):
        st.markdown(f"<div class='reserve'>{res}</div>", unsafe_allow_html=True)
    if v.get("source_fait"):
        st.caption(f"Source du fait qualitatif : {v['source_fait']}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Cours (36 derniers mois)**")
        s = cours[cours.ticker == choix].copy()
        s["_d"] = pd.to_datetime(s.fin_mois)
        if len(s):
            # meme piege que regime_marche : tail(36) valait 36 mois en mensuel,
            # 36 seances en quotidien. On borne par la DATE, pas par le rang.
            s = s[s._d >= s._d.max() - pd.DateOffset(months=36)]
        if len(s):
            st.altair_chart(alt.Chart(s).mark_line(color="#1f4e79").encode(
                x=alt.X("fin_mois:T", title=None), y=alt.Y("cours:Q", title=None,
                        scale=alt.Scale(zero=False))).properties(height=220),
                width='stretch')
    with c2:
        st.markdown("**Resultats nets en base**")
        e = etats[(etats.ticker == choix) & etats.resultat_net.notna()][
            ["exercice", "resultat_net", "statut_donnee", "date_publication"]]
        if len(e):
            e.columns = ["Exercice", "Resultat net", "Statut", "Publie le"]
            st.dataframe(e.sort_values("Exercice", ascending=False), hide_index=True,
                         width='stretch', height=220)
        else:
            st.info("Aucun resultat net transcrit en base pour ce titre "
                    "(profil appuye sur le BPA implicite).")

    recents = v.get("avis_recents") or []
    if recents:
        with st.expander(f"Derniers avis officiels BRVM ({len(recents)})", expanded=False):
            for a in recents:
                lien = f" — [avis]({a['url']})" if a.get("url") else ""
                st.markdown(f"- **{a.get('date')}** · `{a.get('type')}` · "
                            f"{(a.get('titre') or '')[:130]}{lien}")

    st.markdown("**A completer par l'analyste** — obligatoire avant tout usage reel")
    st.text_area("These adverse : quel est le meilleur argument pour le profil que je n'ai "
                 "pas retenu ? Qu'est-ce qui me ferait changer d'avis ?", key=f"adv_{choix}",
                 height=90)
    st.text_area("Prediction datee decoulant du profil (a verifier a la prochaine "
                 "publication)", key=f"pred_{choix}", height=70)
    st.caption("Ces deux champs ne sont pas enregistres : les recopier dans le journal "
               "des profils du depot prive.")

# ----------------------------------------------------------------------
# 4. Qualite des donnees & methode
# ----------------------------------------------------------------------
with o4:
    st.markdown("#### Sur quoi reposent les etiquettes")
    src = df.source.value_counts()
    q1, q2, q3 = st.columns(3)
    q1.metric("Croissance certifiee (RN VALIDE)",
              int(sum(n for s, n in src.items() if "VERIFIE" in str(s))))
    q2.metric("Croissance probable (RN PROBABLE)",
              int(sum(n for s, n in src.items() if "PROBABLE" in str(s))))
    q3.metric("BPA implicite (source BOC)", int(src.get("BPA_IMPLICITE", 0)))
    st.caption("Le BPA implicite (cours/PER du BOC) est une source **circulaire** : "
               "il vient de la BRVM elle-meme. Validation croisee faite sur NSBC "
               "uniquement (1 646,5 implicite contre 1 646 certifie). "
               "Chantier de validation 8-10 titres non clos.")

    n_gl = int((df.per_source == "GLISSANT").sum())
    st.markdown("#### Quel PER lisent les analyses")
    st.caption("Le PER **affiche en premier** est toujours celui du BOC. Les **analyses** "
               "(axe de decote, PEGY, perimetre analysable, medianes de comparaison) "
               "lisent le **PER glissant** quand il existe, et le PER du BOC a defaut. "
               f"Aujourd'hui : **{n_gl} titre(s) sur {len(df)}** analyse(s) sur le PER "
               "glissant. Seule exception : le payout implicite reste calcule sur le PER "
               "du BOC, parce qu'il rapporte le dividende d'un exercice au benefice de ce "
               "meme exercice.")

    st.markdown("#### Verification externe : notations d'agences")
    n_notes = int(df.notation.notna().sum())
    n_contra = int(df.contradiction.sum())
    v1, v2 = st.columns(2)
    v1.metric("Titres avec une notation collectee", n_notes,
              help="Source : brvm.org > Annonces emetteurs > Notations financieres")
    v2.metric("Contradictions signalees", n_contra,
              help="Le profil et l'opinion de l'agence divergent : a trancher par l'analyste")
    st.caption("C'est la premiere source reellement independante du pipeline : jusqu'ici, "
               "tout recoupement passait par la BRVM elle-meme ou par la presse, qui "
               "reprend les memes communiques. Reserves : une notation mesure le risque "
               "de credit et non l'attractivite actionnaire ; elle est sollicitee et "
               "remuneree par l'emetteur ; sa frequence est annuelle et sa couverture "
               "partielle.")

    st.markdown("#### Couverture par titre")
    cov = df.groupby("source").size().rename("titres").reset_index()
    st.dataframe(cov, hide_index=True, width='stretch')

    st.markdown("#### Limites permanentes du cadre")
    st.markdown("""
- **Un seul cycle observe**, haussier. Aucun test en marche baissier : les signatures
  VALUE et RENDEMENT, et surtout la liquidite, n'ont jamais ete eprouvees dans le
  regime ou elles comptent le plus.
- **Aucune detection de manipulation comptable ni de detresse bilancielle** :
  F-Score complet, Z-Score, accruals et M-Score ne sont pas calculables avant
  l'achevement du backfill des bilans.
- **Croissances non ajustees des operations sur capital** (une seule operation
  enregistree dans le pipeline a ce jour).
- **Gardes anti-artefact provisoires**, calibrees en echantillon (SLBC, CABC,
  ECOC, NEIC) : leur validation reelle sera le premier cas nouveau traite sans
  retouche.
- **Biais du survivant** : l'univers est celui des societes encore cotees et
  encore publiantes.
- **Aucune superiorite de style etablie** : sur le seul test non biaise disponible,
  l'ecart GARP contre marche est de +22,8 points avec p = 0,43 et un intervalle
  de confiance a 90 % de [-14 % ; +89 %]. La question n'est pas seulement sans
  reponse, elle n'est **pas testable** en l'etat (GARP calculable sur 3
  titres-annees seulement entre 2019 et 2024).
""")
    st.markdown("#### Ce qui est demontre, en revanche")
    st.markdown("""
La **valeur defensive** du cadre est verifiee sur des cas concrets : le dividende
exceptionnel de FTSC ecarte avant un repli de 59 %, la nature comptable du
redressement d'UNIWAX identifiee, les series artefactuelles (CABC a +230 %/an de
rebond) neutralisees. Le cadre evite des pieges ; il ne selectionne pas des
gagnants.
""")
    st.caption("Seuils, sources et jurisprudence : config/seuils.yaml et "
               "config/faits_qualitatifs.yaml, versionnes dans le depot.")
