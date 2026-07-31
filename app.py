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
@st.cache_resource(show_spinner="Construction de la base (30 s au premier lancement)…")
def preparer_base():
    """Reconstruit brvm.db si absente. La base n'est jamais commitee."""
    if not DB.exists():
        for script in [RACINE / "moteur" / "peupler.py",
                       RACINE / "collecte" / "charger_cours.py",
                       RACINE / "moteur" / "profils.py"]:
            subprocess.run([sys.executable, str(script)], cwd=str(script.parent),
                           check=False, capture_output=True, timeout=300)
    elif not PROFILS.exists():
        subprocess.run([sys.executable, str(RACINE / "moteur" / "profils.py")],
                       cwd=str(RACINE / "moteur"), check=False, capture_output=True)
    return DB.exists()


@st.cache_data(ttl=3600)
def charger():
    profils = json.loads(PROFILS.read_text(encoding="utf-8")) if PROFILS.exists() else {}
    conn = sqlite3.connect(DB)
    noms = dict(conn.execute("SELECT ticker, nom FROM societes").fetchall())
    cours = pd.read_sql_query(
        "SELECT ticker, fin_mois, cours, per, rendement FROM cours_mensuels "
        "WHERE cours IS NOT NULL ORDER BY fin_mois", conn)
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
            confiance=v.get("confiance"), gate=v.get("gate")))
    return pd.DataFrame(lignes), profils, cours, etats


@st.cache_data(ttl=3600)
def regime_marche(cours):
    """Condition 0 : ou en est le marche dans son cycle.
    Un profil se lit differemment selon le regime — la mesure historique montre
    que le regime domine tout le reste."""
    piv = cours.pivot_table(index="fin_mois", columns="ticker", values="cours").sort_index()
    var12 = (piv / piv.shift(12) - 1).median(axis=1)
    var24 = (piv / piv.shift(24) - 1).median(axis=1)
    return var12, var24


def puce(profil):
    return (f"<span class='puce' style='background:{COULEURS.get(profil, '#6c757d')}'>"
            f"{profil.replace('_', ' ')}</span>")


def badge_grade(g):
    couleur = {"A": "#1f4e79", "B": "#7d6608", "C": "#8a8a8a"}.get(g, "#8a8a8a")
    return f"<span class='grade' style='background:{couleur}'>grade {g}</span>"


preparer_base()
if not DB.exists() or not PROFILS.exists():
    st.error("Base indisponible. Verifier que moteur/peupler.py et collecte/charger_cours.py "
             "s'executent sans erreur.")
    st.stop()
df, profils, cours, etats = charger()
var12, var24 = regime_marche(cours)

# ----------------------------------------------------------------------
# Barre laterale
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Profilage BRVM")
    st.caption(f"{len(df)} titres · donnees au {cours.fin_mois.max()}")
    st.markdown("---")
    f_profil = st.multiselect("Profil", ORDRE, default=[])
    f_grade = st.multiselect("Grade de confiance", ["A", "B", "C"], default=[])
    f_secteur = st.multiselect("Secteur", sorted(df.secteur.dropna().unique()), default=[])
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

st.title("Profilage fondamental — BRVM")

o1, o2, o3, o4 = st.tabs(["Vue d'ensemble", "Explorer", "Fiche titre",
                          "Qualite des donnees & methode"])

# ----------------------------------------------------------------------
# 1. Vue d'ensemble
# ----------------------------------------------------------------------
with o1:
    r12 = var12.dropna().iloc[-1] if len(var12.dropna()) else None
    r24 = var24.dropna().iloc[-1] if len(var24.dropna()) else None
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
        c1.metric("Marche sur 12 mois", f"{r12:+.0%}", help="Progression mediane des 47 titres")
        c2.metric("Marche sur 24 mois", f"{r24:+.0%}" if r24 is not None else "n/d")
        c3.info(lecture)

    st.markdown("#### Repartition des profils")
    comptes = df.profil.value_counts().reindex(ORDRE).dropna()
    cols = st.columns(len(comptes)) if len(comptes) <= 5 else st.columns(5)
    for i, (prof, n) in enumerate(comptes.items()):
        with cols[i % len(cols)]:
            st.markdown(f"{puce(prof)}<br><span style='font-size:1.6rem;font-weight:700'>{int(n)}</span>",
                        unsafe_allow_html=True)
            st.caption(LIBELLES[prof].split("—")[1].strip() if "—" in LIBELLES[prof] else "")

    st.markdown("---")
    st.markdown("#### Plan cherte × croissance")
    st.caption("Percentiles au sein du secteur si celui-ci compte au moins 8 titres, "
               "sinon au sein du marche (reference indiquee dans la fiche titre). "
               "Des rangs voisins ne sont pas significativement differents : "
               "lire des zones, pas des positions.")
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
               "croissance", "source", "pegy", "payout", "drapeaux"]].copy()
    aff.columns = ["Ticker", "Societe", "Secteur", "Profil", "Secondaire", "Grade",
                   "PER", "Rdt brut %", "Croiss. %/an", "Source croissance", "PEGY",
                   "Payout", "Drapeaux"]
    st.dataframe(
        aff.sort_values(["Grade", "Profil", "Ticker"]), hide_index=True,
        width='stretch', height=560,
        column_config={
            "PER": st.column_config.NumberColumn(format="%.1f"),
            "Rdt brut %": st.column_config.NumberColumn(format="%.1f"),
            "Croiss. %/an": st.column_config.NumberColumn(format="%.1f"),
            "PEGY": st.column_config.NumberColumn(format="%.2f"),
            "Payout": st.column_config.NumberColumn(format="%.2f"),
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
        st.metric("PER", f"{r.per:.1f}" if pd.notna(r.per) else "n/d")
        st.metric("Rendement brut", f"{r.dy:.1f} %" if pd.notna(r.dy) else "n/d")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Croissance", f"{r.croissance:+.1f} %/an" if pd.notna(r.croissance) else "n/d",
              help=f"Source : {r.source}")
    m2.metric("PEGY", f"{r.pegy:.2f}" if pd.notna(r.pegy) else "n/d",
              help="PER / (croissance % + rendement %). Lynch 1989 ; fondement Easton 2004.")
    m3.metric("Payout", f"{r.payout:.0%}" if pd.notna(r.payout) else "non disponible")
    m4.metric("ROE", f"{r.roe:.1f} %" if pd.notna(r.roe) else "non disponible")

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
        s = cours[cours.ticker == choix].tail(36)
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
