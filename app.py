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
import subprocess
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RACINE = Path(__file__).resolve().parent
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
    parties = []
    for f in (QUOTIDIEN, RACINE / "collecte" / "cours_extraits.csv",
              RACINE / "collecte" / "dividendes_par_exercice.csv",
              RACINE / "collecte" / "notations_financieres.csv"):
        parties.append(f"{f.name}:{int(f.stat().st_mtime)}" if f.exists() else f"{f.name}:0")
    return "|".join(parties)


@st.cache_resource(show_spinner="Construction de la base (30 s au premier lancement)…")
def preparer_base(_empreinte):
    """Reconstruit brvm.db quand l'empreinte des sources change.
    La base n'est jamais commitee : elle est rebatie depuis les CSV du depot."""
    scripts = [RACINE / "moteur" / "peupler.py",
               RACINE / "collecte" / "charger_cours.py",
               RACINE / "collecte" / "charger_cours_quotidien.py",  # pont ajoute 03/09
               RACINE / "moteur" / "profils.py"]
    for script in scripts:
        if not script.exists():
            continue
        subprocess.run([sys.executable, str(script)], cwd=str(script.parent),
                       check=False, capture_output=True, timeout=300)
    return DB.exists()


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
            secteur=v.get("secteur"), per=v.get("per"), dy=v.get("dy"),
            croissance=v.get("g"), source=v.get("source_croissance"),
            pegy=v.get("pegy"), payout=v.get("payout"), roe=v.get("roe"),
            cherte_pctl=v.get("cherte_pctl"), croissance_pctl=v.get("croissance_pctl"),
            reference=v.get("reference_axes"), drapeaux=", ".join(v.get("drapeaux") or []),
            confiance=v.get("confiance"), gate=v.get("gate"),
            motif=v.get("motif"), payout_source=v.get("payout_source"),
            part_op=v.get("part_operationnelle"),
            per_norm=v.get("per_normalise"), ecart_ben=v.get("ecart_benefice"),
            prime=v.get("prime_rendement"), taux_ref=v.get("taux_reference"),
            statut_cotation=v.get("statut_cotation", "NEGOCIABLE"),
            date_statut=v.get("date_statut_cotation"),
            historique_cotation=v.get("historique_cotation") or [],
            retablie=bool(v.get("statut_cotation") == "NEGOCIABLE"
                          and any(e.get("type") == "SUSPENSION"
                                  for e in (v.get("evenements_cotation") or []))),
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
        """Variation mediane, avec LISSAGE de la reference sur +/- 7 jours.

        Correctif du 24/09/2026. Sans lissage, la mesure dependait du cours d'UN
        SEUL jour, celui d'il y a douze mois : si ce jour-la quelques titres
        avaient un cours atypique, toute la mesure bougeait. Amplitude constatee
        sur quinze seances consecutives : de +77 % a +99 %, soit 22 points
        d'ecart pour un marche qui n'avait pas change. Avec lissage, l'amplitude
        tombe a 17 points et la valeur cesse de sauter d'un jour a l'autre.
        On prend la MEDIANE des cours de la fenetre, pas leur moyenne, pour ne
        pas se laisser entrainer par une seance extreme.
        """
        cible = fin - pd.DateOffset(months=mois)
        fenetre = piv.loc[(piv.index >= cible - pd.Timedelta(days=7))
                          & (piv.index <= cible + pd.Timedelta(days=7))]
        if fenetre.empty:
            anterieures = piv.index[piv.index <= cible]
            if not len(anterieures):
                return None
            reference = piv.loc[anterieures[-1]]
        else:
            reference = fenetre.median()
        v = (piv.loc[fin] / reference - 1).median()
        return None if pd.isna(v) else float(v)

    def variation_annee():
        """Variation depuis le 1er janvier de l'annee en cours.

        Ajout du 24/09/2026, proposition de l'utilisatrice — et c'est la bonne
        convention : le bulletin officiel appelle "variation annuelle" la
        variation DEPUIS LE DEBUT DE L'ANNEE CIVILE, pas sur douze mois
        glissants. Mesure au 22/09/2026 : mediane des titres +51,9 % depuis le
        1er janvier, contre +55,00 % annonces par l'indice BRVM Composite. Les
        deux concordent, alors que le chiffre sur douze mois glissants semblait
        contredire l'indice sans raison.
        La reference est la DERNIERE SEANCE de l'annee precedente, lissee sur
        les cinq seances qui la precedent pour la meme raison que ci-dessus :
        ne pas faire dependre toute la mesure d'un seul jour de cotation.
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
preparer_base(emp)
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
              "Cherte dans le tercile superieur (decote), croissance faible ou nulle, "
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
                          "L'indice BRVM Composite affiche +55 % sur la meme base : "
                          "l'ecart restant vient de la ponderation, l'indice pesant "
                          "les titres par leur capitalisation la ou cette mesure les "
                          "traite a egalite."))
        c2.metric("Sur 12 mois glissants", f"{r12:+.0%}" if r12 is not None else "n/d",
                  help=("Progression MEDIANE sur douze mois calendaires, reference "
                        "lissee sur +/- 7 jours.\n\nC'est cette mesure, et non la "
                        "precedente, qui sert a qualifier le regime de marche : les "
                        "reperes historiques (part de titres qui doublent selon le "
                        "regime) ont ete etablis sur douze mois glissants."))
        c3.metric("Sur 24 mois", f"{r24:+.0%}" if r24 is not None else "n/d")
        c4.info(lecture)
