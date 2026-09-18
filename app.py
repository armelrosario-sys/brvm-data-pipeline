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
        return None, None, None
    fin = piv.index[-1]

    def variation(mois):
        cible = fin - pd.DateOffset(months=mois)
        anterieures = piv.index[piv.index <= cible]
        if not len(anterieures):
            return None
        v = (piv.loc[fin] / piv.loc[anterieures[-1]] - 1).median()
        return None if pd.isna(v) else float(v)

    return variation(12), variation(24), fin


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
r12, r24, fin_cours = regime_marche(cours)

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
        c1, c2, c3 = st.columns([1, 1, 3])
        c1.metric("Marche sur 12 mois", f"{r12:+.0%}",
                  help="Progression mediane des titres cotes, mesuree sur douze mois "
                       "calendaires reels (et non sur un nombre fixe de seances).")
        c2.metric("Marche sur 24 mois", f"{r24:+.0%}" if r24 is not None else "n/d")
        c3.info(lecture)
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
            ["ticker", "nom", "secteur", "grade", "per", "dy", "croissance", "motif"]].copy()
        grp.columns = ["Ticker", "Societe", "Secteur", "Grade", "PER", "Rdt %",
                       "Croiss. %/an", "Motif du classement"]
        st.dataframe(grp.sort_values(["Grade", "Ticker"]), hide_index=True, width='stretch',
                     column_config={
                         "PER": st.column_config.NumberColumn(format="%.1f"),
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

    st.markdown("#### Plan cherte × croissance")
    n_plan = int((vue.cherte_pctl.notna() & vue.croissance_pctl.notna()).sum())
    st.caption(f"**{n_plan} titres sur {len(vue)} positionnes.** Percentiles au sein du "
               "secteur si celui-ci compte au moins 8 titres, sinon au sein du marche "
               "(reference indiquee dans la fiche titre). Des rangs voisins ne sont pas "
               "significativement differents : lire des zones, pas des positions.")
    plan = vue.dropna(subset=["cherte_pctl", "croissance_pctl"])
    if len(plan):
        base = alt.Chart(plan).mark_circle(size=220, opacity=.85).encode(
            x=alt.X("cherte_pctl:Q", title="← plus cher     CHERTE (percentile)     moins cher →",
                    scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("croissance_pctl:Q", title="CROISSANCE (percentile) →",
                    scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("profil:N", scale=alt.Scale(
                domain=[p for p in ORDRE if p in plan.profil.unique()],
                range=[COULEURS[p] for p in ORDRE if p in plan.profil.unique()]),
                legend=alt.Legend(title="Profil", orient="right")),
            tooltip=["ticker", "nom", "profil", "grade", "per", "dy", "croissance", "pegy"])
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
            if "BENEFICE_NON_REPRESENTATIF" in dra and vv.get("per_normalise"):
                bits.append(f"PER trompeur ({r.per:.0f} affiche, "
                            f"{vv['per_normalise']:.0f} sur benefice moyen)")
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
            plan2["_q"] = [quadrant(r.cherte_pctl, r.croissance_pctl)[1]
                           for _, r in plan2.iterrows()]
            noms_q = ["Decote ET croissance (quadrant favorable)",
                      "Croissance deja payee (haut a gauche)",
                      "Bon marche mais sans dynamique (bas a droite)",
                      "Ni decote ni croissance (bas a gauche)"]
            for q in range(4):
                sous = plan2[plan2._q == q].sort_values("cherte_pctl", ascending=False)
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
            lambda r: ("Decote ET croissance" if r.cherte_pctl >= 67 and r.croissance_pctl >= 67
                       else "Croissance deja payee" if r.croissance_pctl >= 67
                       else "Bon marche sans dynamique" if r.cherte_pctl >= 67
                       else "Ni l'un ni l'autre"), axis=1)

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
            sub = plan2[plan2.zone == zone].sort_values("cherte_pctl", ascending=False)
            if not len(sub):
                continue
            st.markdown(ZONES[zone] + f"  ({len(sub)} titre(s))")
            for _, r in sub.iterrows():
                bits = []
                if pd.notna(r.per):
                    bits.append(f"PER {r.per:.1f}")
                if pd.notna(r.per_norm) and pd.notna(r.per) and abs(r.per_norm - r.per) > 1:
                    bits.append(f"**{r.per_norm:.1f} normalise**")
                if pd.notna(r.dy):
                    bits.append(f"rdt {r.dy:.1f} %")
                if pd.notna(r.croissance):
                    bits.append(f"croiss. {r.croissance:+.0f} %/an")
                alertes = []
                if r.statut_cotation == "SUSPENDU":
                    alertes.append("COTATION SUSPENDUE")
                if "BENEFICE_NON_REPRESENTATIF" in str(r.drapeaux):
                    alertes.append("benefice non representatif")
                if "RATTRAPAGE" in str(r.drapeaux) or "CAP_" in str(r.drapeaux):
                    alertes.append("croissance de rattrapage")
                if "RESULTAT_NON_OPERATIONNEL" in str(r.drapeaux):
                    alertes.append("benefice non operationnel")
                if pd.notna(r.payout) and r.payout > 1:
                    alertes.append("dividende non couvert")
                if pd.notna(r.prime) and r.prime > 0:
                    alertes.append("rend plus que l'Etat")
                suffixe = (f" — <span style='color:#b45f3f'>{' · '.join(alertes)}</span>"
                           if alertes else "")
                st.markdown(
                    f"<div class='reserve'><b>{r.ticker}</b> ({r.nom}) · "
                    f"{r.profil.replace('_', ' ').lower()} · grade {r.grade} · "
                    f"{' · '.join(bits)}{suffixe}</div>", unsafe_allow_html=True)

        # Les titres hors axes ne doivent pas DISPARAITRE du tableau de bord :
        # un plan qui n'affiche que 34 titres sur 47 laisse croire que les 13
        # autres n'existent pas, alors qu'ils portent un diagnostic explicite.
        hors = vue[vue.cherte_pctl.isna() | vue.croissance_pctl.isna()]
        if len(hors):
            with st.expander(f"{len(hors)} titre(s) hors du plan — pourquoi",
                             expanded=False):
                st.caption("Un titre n'apparait sur le plan que s'il a une position "
                           "sur les DEUX axes. Les profils Retournement, Mutation et "
                           "Non analysable sont hors perimetre par construction ; "
                           "les autres ont un axe manquant, ce qui est une lacune de "
                           "donnees et non un diagnostic.")
                h = hors[["ticker", "nom", "profil", "grade", "cherte_pctl",
                          "croissance_pctl", "motif"]].copy()
                h["Axe manquant"] = h.apply(
                    lambda r: "les deux" if pd.isna(r.cherte_pctl) and pd.isna(r.croissance_pctl)
                    else ("croissance" if pd.isna(r.croissance_pctl) else "cherte"), axis=1)
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
    aff = vue[["ticker", "nom", "secteur", "profil", "secondaire", "grade", "per", "dy",
               "croissance", "source", "pegy", "payout", "drapeaux",
               "notation", "contradiction", "motif"]].copy()
    aff.columns = ["Ticker", "Societe", "Secteur", "Profil", "Secondaire", "Grade",
                   "PER", "Rdt %", "Croiss. %/an", "Source croissance", "PEGY",
                   "Payout", "Drapeaux", "Notation", "Contradiction", "Motif"]
    st.dataframe(
        aff.sort_values(["Grade", "Profil", "Ticker"]), hide_index=True,
        width='stretch', height=560,
        column_config={
            "PER": st.column_config.NumberColumn(format="%.1f"),
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
        aide_per = _ctx("per") or ""
        if pd.notna(r.per_norm):
            aide_per += (f"\n\nPER normalise (sur le benefice MOYEN des derniers "
                         f"exercices) : {r.per_norm:.1f}")
        st.metric("PER", f"{r.per:.1f}" if pd.notna(r.per) else "n/d", help=aide_per,
                  delta=(f"normalise {r.per_norm:.1f}" if pd.notna(r.per_norm) else None),
                  delta_color="off")
        st.metric("Rendement", f"{r.dy:.1f} %" if pd.notna(r.dy) else "n/d",
                  delta=(f"{r.prime*100:+.1f} pts vs Etat" if pd.notna(r.prime) else None),
                  help=(_ctx("dy", " %") or "") + "\n\nConvention brut/net du champ "
                       "rendement du BOC : chantier de verification ouvert.")

    if v.get("statut_cotation") == "SUSPENDU":
        st.error(f"**Cotation suspendue depuis le {v.get('date_statut_cotation')}.** "
                 f"Ce titre ne peut etre ni achete ni vendu jusqu'a la levee de la "
                 f"suspension par la BRVM. Tout ce qui suit decrit ses comptes, pas "
                 f"une opportunite accessible.")

    for n in (v.get("notes") or []):
        if n.startswith("AVIS BRVM"):
            st.warning(n)

    if v.get("motif"):
        st.info(f"**Pourquoi ce profil** — {v['motif']}")

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
                   "Sous 0,25 : protocole de revue obligatoire.")
    m3.metric("Payout", f"{r.payout:.0%}" if pd.notna(r.payout) else "non disponible",
              help=(f"Source : {r.payout_source}\n\n" if pd.notna(r.payout_source) else "")
                   + contexte("payout", pct=True))
    m4.metric("ROE", f"{r.roe:.1f} %" if pd.notna(r.roe) else "non disponible",
              help=contexte("roe", " %"))

    # Representativite du benefice : un PER se calcule sur un benefice ; si ce
    # benefice est un pic, le PER parait bas alors que le titre est cher.
    if pd.notna(r.per_norm) and pd.notna(r.per):
        if "BENEFICE_NON_REPRESENTATIF" in str(v.get("drapeaux") or ""):
            st.warning(
                f"**Attention au PER affiche** — il vaut {r.per:.1f}, mais calcule sur "
                f"le benefice MOYEN des derniers exercices il vaut **{r.per_norm:.1f}**. "
                f"Le dernier benefice depasse de {r.ecart_ben*100:.0f} % la moyenne : "
                f"le titre est donc nettement plus cher qu'il n'en a l'air. A confirmer "
                f"au prochain exercice.")
        else:
            st.caption(f"**PER normalise** (sur le benefice moyen) : {r.per_norm:.1f} — "
                       f"proche du PER affiche, le dernier benefice est representatif.")

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

    if pd.notna(r.cherte_pctl):
        st.markdown(f"**Positionnement** — cherte P{int(r.cherte_pctl)} · "
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
