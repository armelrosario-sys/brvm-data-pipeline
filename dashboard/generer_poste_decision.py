#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dashboard/generer_poste_decision.py — Poste de decision BRVM (4 vues).

Genere docs_site/poste_decision.html depuis les donnees reelles :
  Vue 1  Allocation (mode degrade tant que les donnees privees ne sont pas
         renseignees ; reference = taux obligataire en CONFIG, jamais scrape)
  Vue 2  Mes titres (liste_suivi, alarmes prioritaires, regle d'escalade)
  Vue 3  Opportunites — deux blocs etanches :
         coeur rendement-qualite (DY net IRVM > taux obligataire, gate OK,
         aucune alarme) et satellite re-rating (titres A uniquement ;
         records isoles replies — rafinement teste du 13/07/2026)
  Vue 4  Journal (lecture de journal_decisions)

Ordre d'execution du pipeline :
  peupler -> charger_cours -> signaux -> profils -> generer_dashboard_html
  -> bloc_signaux -> generer_poste_decision

Config : ajouter dans config/marche.yaml, sous indicateurs_marche :
  taux_obligataire_ref: 0.065   # a actualiser trimestriellement (UMOA-Titres)
Repli sur 6,5 % si absent.

Justification microstructure : toutes les entrees sont verifiees en base
(PER/rendement mensuels BOC, RN, liquidite mesuree 12m, signaux dates).
Aucun indicateur court terme. La capacite d'absorption = 20 % de la valeur
moyenne MENSUELLE echangee (seule granularite reelle disponible).
"""
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DB = RACINE / "moteur" / "brvm.db"
PROFILS = RACINE / "collecte" / "profils.json"
LIQ = RACINE / "collecte" / "liquidite_generale.json"
SORTIE = RACINE / "docs_site" / "poste_decision.html"

sys.path.insert(0, str(RACINE / "moteur"))
sys.path.insert(0, str(RACINE / "dashboard"))
from scoring import charger_marche, rendement_net_estime  # reutilisation moteur
from glossaire_signaux import libelle as libelle_signal  # 14/07/2026 : codes -> libelles clairs

def dy_net(dy_brut_pct, pays):
    """DY net d'IRVM en %, via la table officielle du moteur (moteur/scoring.py::IRVM_PAR_PAYS).

    Correctif 14/07/2026 (bug critique trouve a l'audit) : rendement_net_estime()
    retourne un TUPLE (rendement_net, taux), pas un flottant seul. L'ancien code
    faisait `100.0 * net` sur ce tuple -> TypeError -> avale par un except trop
    large -> repli SILENCIEUX sur une table IRVM dupliquee et moins a jour que
    celle du moteur (qui documente les cas particuliers FTSC/STBC). Corrige :
    deballage correct du tuple, plus de table dupliquee, plus de except muet.
    """
    net, taux = rendement_net_estime(dy_brut_pct / 100.0, pays or "CI")
    if net is None:
        return dy_brut_pct  # pays inconnu : aucun IRVM applique, affiche le brut tel quel
    return 100.0 * net


def chip(p):
    if not p or not p.get("dominant"):
        return "<span class='chip c-na'>profil n/d</span>"
    lab = p["dominant"] + (" (mixte)" if p.get("mixte") else "")
    extra = " ⚠PEG" if p.get("alerte_peg") else ""
    return f"<span class='chip c-{p['dominant'].lower()}'>{lab}{extra}</span>"


def absorption(liq, t):
    v = (liq.get(t) or {}).get("valeur_moyenne_12m")
    if not v:
        return ("n/d", "c-na")
    m = 0.20 * v / 1e6  # 20 % de la valeur moyenne mensuelle, en M FCFA
    if m >= 10:
        return (f"{m:.0f} M/mois — absorbable", "c-ok")
    if m >= 2:
        return (f"{m:.1f} M/mois — étroit", "c-mid")
    return (f"{m:.1f} M/mois — impraticable", "c-bad")


def generer():
    cur = sqlite3.connect(DB).cursor()
    profils = json.loads(PROFILS.read_text()) if PROFILS.exists() else {}
    liq = json.loads(LIQ.read_text()) if LIQ.exists() else {}
    marche = charger_marche()
    taux = 100 * float(marche.get("indicateurs_marche", {})
                       .get("taux_obligataire_ref", 0.065))

    noms = dict(cur.execute("SELECT ticker, nom FROM societes"))
    pays = dict(cur.execute("SELECT ticker, pays_immatriculation FROM societes"))
    suivi = [t for (t,) in cur.execute("SELECT ticker FROM liste_suivi ORDER BY ticker")]
    sig_par_t = {}
    for t, ty, di, de, dd in cur.execute(
            "SELECT ticker,type,direction,detail,date_detection FROM signaux "
            "WHERE statut='ACTIF'"):
        sig_par_t.setdefault(t, []).append((ty, di, de, dd))

    # ---------- Vue 2 : mes titres ----------
    rows2 = []
    for t in suivi:
        ss = sig_par_t.get(t, [])
        defav = [s for s in ss if s[1] == "DEFAVORABLE"]
        fav = [s for s in ss if s[1] == "FAVORABLE"]
        etat = "".join(f"<div class='al bad'>⚠ {ty} — {de} <i>({dd})</i></div>"
                       for ty, _, de, dd in defav)
        etat += "".join(f"<div class='al ok'>{ty} — {de}</div>"
                        for ty, _, de, _ in fav)
        etat = etat or "<div class='al ras'>RAS</div>"
        if len(defav) >= 2:
            etat += ("<b class='esc'>ESCALADE : ≥2 défavorables — revue sous "
                     "10 séances, décision au journal</b>")
        rows2.append(f"<tr><td><b>{t}</b><br><small>{noms.get(t,'')}</small></td>"
                     f"<td>{chip(profils.get(t))}</td><td>{etat}</td></tr>")

    # ---------- Vue 3A : coeur rendement-qualite ----------
    rows3a = []
    nets = []
    for t, p in sorted(profils.items(), key=lambda kv: -(kv[1].get("dy") or 0)):
        if p.get("dy") is None:
            continue
        net = dy_net(p["dy"], pays.get(t))
        nets.append(net)
        if net <= taux:
            continue
        if any(s[1] == "DEFAVORABLE" for s in sig_par_t.get(t, [])):
            continue
        ab, cl = absorption(liq, t)
        per = f"{p['per']:.1f}" if p.get("per") else "—"
        rows3a.append(f"<tr><td><b>{t}</b></td><td>{chip(p)}</td>"
                      f"<td>{p['dy']:.1f} %</td><td><b>{net:.1f} %</b></td>"
                      f"<td>{per}</td><td class='{cl}'>{ab}</td>"
                      f"<td>{p.get('confiance','n/d')}</td></tr>")

    # ---------- Vue 3B : satellite (A uniquement ; records isoles replies) ----------
    rows3b, records_isoles = [], []
    for t, ss in sig_par_t.items():
        if any(s[1] == "DEFAVORABLE" for s in ss):
            continue
        types = {s[0] for s in ss}
        aq = "A_QUALITE_DECOTEE" in types or "RERATING_EN_COURS" in types
        b1 = "B1_RECORD" in types
        if aq:
            conj = ("⚡ CONJONCTION A+B1 — le profil CBI" if b1
                    else "Décote qualifiée (A)" if "A_QUALITE_DECOTEE" in types
                    else "Re-rating en cours")
            ab, cl = absorption(liq, t)
            det = " · ".join(libelle_signal(s[0]) for s in ss if s[1] == "FAVORABLE")
            rows3b.append((2 if b1 else 1,
                f"<tr><td><b>{t}</b></td><td>{chip(profils.get(t))}</td>"
                f"<td><b>{conj}</b><br><small>{det}</small></td>"
                f"<td class='{cl}'>{ab}</td>"
                f"<td>{(profils.get(t) or {}).get('confiance','n/d')}</td></tr>"))
        elif b1:
            records_isoles.append(t)
    rows3b = [r for _, r in sorted(rows3b, key=lambda x: -x[0])]
    note_rec = ""
    if records_isoles:
        note_rec = (f"<div class='note'>+ {len(records_isoles)} records isolés "
                    f"non affichés (sélectivité faible sans décote) : "
                    f"{', '.join(sorted(records_isoles))}</div>")

    # ---------- Vue 1 : allocation (mode degrade) ----------
    moy = sum(nets) / len(nets) if nets else 0
    n_bat = sum(1 for d in nets if d > taux)

    # ---------- Vue 4 : journal ----------
    rows4 = [f"<tr><td>{r[0]}</td><td><b>{r[1]}</b></td><td>{r[2]}</td><td>{r[3] or ''}</td></tr>"
             for r in cur.execute(
                 "SELECT date_decision, ticker, action, detail FROM "
                 "journal_decisions ORDER BY date_decision DESC LIMIT 50")]
    corps4 = (f"<table><tr><th>Date</th><th>Titre</th><th>Action</th><th>Détail</th></tr>"
              f"{''.join(rows4)}</table>" if rows4 else
              "<div class='note'>Aucune entrée. Le journal est pré-rempli par le "
              "système au moment d'une décision — tu n'écris que la décision et sa raison.</div>")

    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Poste de décision BRVM</title><style>
body{{background:#0f172a;color:#e2e8f0;font:15px/1.5 system-ui,sans-serif;margin:0;padding:18px}}
.w{{max-width:1000px;margin:auto}} h1{{font-size:1.3em}} h2{{font-size:1.05em;margin:0 0 10px}}
.carte{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 16px;margin-bottom:14px}}
table{{width:100%;border-collapse:collapse;font-size:.9em}}
th{{text-align:left;color:#94a3b8;font-weight:500;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:7px 8px;border-bottom:1px solid rgba(148,163,184,.15);vertical-align:top}}
.chip{{display:inline-block;padding:1px 8px;border-radius:99px;font-size:.8em;font-weight:600}}
.c-value{{background:#173f2e;color:#34d399}}.c-growth{{background:#1e3a5f;color:#60a5fa}}
.c-garp{{background:#3f2e17;color:#fbbf24}}.c-na{{background:#334155;color:#94a3b8}}
.c-ok{{color:#34d399}}.c-mid{{color:#fbbf24}}.c-bad{{color:#f87171}}
.al{{margin:2px 0}}.al.bad{{color:#f87171}}.al.ok{{color:#34d399}}.al.ras{{color:#94a3b8}}
.esc{{color:#fb923c}} .note{{color:#94a3b8;font-size:.82em;margin-top:8px}}
.deg{{background:#3f2e17;color:#fbbf24;border:1px solid #fbbf24;border-radius:8px;padding:8px 12px;font-size:.85em;margin-bottom:10px}}
.onglets{{display:flex;gap:6px;margin:12px 0;flex-wrap:wrap}}
.o{{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:6px 12px;border-radius:8px;cursor:pointer}}
.o.a{{background:#2563eb;color:#fff}} .p{{display:none}}.p.a{{display:block}}
</style></head><body><div class="w">
<h1>Poste de décision BRVM <small style="color:#94a3b8">généré le {date.today()} ·
{len(profils)} titres profilés · {sum(len(v) for v in sig_par_t.values())} signaux actifs</small></h1>
<div class="onglets">
<div class="o a" onclick="go(0)">1 · Allocation</div><div class="o" onclick="go(1)">2 · Mes titres</div>
<div class="o" onclick="go(2)">3 · Opportunités</div><div class="o" onclick="go(3)">4 · Journal</div></div>

<div class="p a"><div class="carte"><h2>Mon allocation tient-elle ?</h2>
<div class="deg">MODE DÉGRADÉ — aucune donnée personnelle renseignée. Vue marché uniquement.
Renseigner (en privé, jamais dans le dépôt public) : patrimoine financier, poche actions, positions.</div>
<table><tr><th>Référence</th><th>Valeur</th></tr>
<tr><td>Taux obligataire UEMOA (config — à actualiser trimestriellement, UMOA-Titres)</td><td><b>{taux:.1f} %</b></td></tr>
<tr><td>DY net d'IRVM moyen des titres éligibles</td><td>{moy:.1f} %</td></tr>
<tr><td>Titres éligibles battant le taux sans risque (net)</td><td><b>{n_bat}</b> / {len(nets)}</td></tr></table>
<div class="note">Règles hors système (à écrire une fois) : plafond poche actions / patrimoine ·
satellite ≤ 25 % de la poche · ≤ 2 positions satellite par secteur. Le DY net est indicatif
(résidence fiscale non paramétrée) ; le rendement total inclut aussi croissance et revalorisation.</div></div></div>

<div class="p"><div class="carte"><h2>Mes titres vont-ils bien ?
<small style="color:#94a3b8">({len(suivi)} suivis — codes seuls, aucune donnée personnelle)</small></h2>
<table><tr><th>Titre</th><th>Profil</th><th>État (alarmes prioritaires)</th></tr>{''.join(rows2)}</table></div></div>

<div class="p"><div class="carte"><h2>Cœur rendement-qualité — DY net &gt; {taux:.1f} %, gate OK, aucune alarme</h2>
<table><tr><th>Titre</th><th>Profil</th><th>DY brut</th><th>DY net IRVM</th><th>PER</th>
<th>Capacité (20 % val. mens. 12m)</th><th>Confiance</th></tr>{''.join(rows3a)}</table>
<div class="note">La décision reste humaine — l'outil décrit, il ne recommande pas.</div></div>
<div class="carte"><h2>Satellite re-rating — signaux actifs (cycle de vie daté)</h2>
<table><tr><th>Titre</th><th>Profil</th><th>Signal</th><th>Capacité</th><th>Confiance</th></tr>{''.join(rows3b)}</table>
{note_rec}
<div class="note">Anti-poursuite : première entrée refusée au-delà de +25 % du cours au premier signal.
Sizing petit par construction.</div></div></div>

<div class="p"><div class="carte"><h2>Qu'ai-je décidé et pourquoi ?</h2>{corps4}</div></div>
<script>function go(i){{document.querySelectorAll('.o').forEach((e,j)=>e.classList.toggle('a',i==j));
document.querySelectorAll('.p').forEach((e,j)=>e.classList.toggle('a',i==j))}}</script>
</div></body></html>"""
    SORTIE.write_text(html, encoding="utf-8")
    print(f"Poste de décision généré : {SORTIE} | coeur {len(rows3a)} | "
          f"satellite {len(rows3b)} (+{len(records_isoles)} records repliés) | suivis {len(suivi)}")


if __name__ == "__main__":
    generer()
