"""Mesures de marché sur les données de la BRVM : rendements, risque, valorisation datée, régime de
marché et Fear & Greed.

    import brvm
    brvm.mesures.performances()                  # rendements de toutes les actions par période
    brvm.mesures.rendement_total("SNTS")         # Sonatel, dividendes nets réinvestis, base 100
    brvm.mesures.beta("ORAC")                    # bêta d'Orange CI face au BRVM Composite
    brvm.mesures.valorisation(date="2025-12-31") # PER, P/B, rendement au cours de cette date
    brvm.mesures.regime()                        # régime de marché du BRVM Composite

Les conventions sont celles de l'application BRVM Analytics, pour qu'un chiffre calculé ici soit le
même que celui de l'application :

- prix d'une action à chaque séance du BRVM Composite : dernier cours connu (un jour sans échange
  reprend le cours de la veille), rien avant la première cotation ;
- dividendes réinvestis : seuls les dividendes ``retenus`` (cohérents avec les cours), nets d'IRVM
  pour le profil choisi, réinvestis au cours de la veille du détachement ;
- volatilité, VaR et bêta sur des rendements hebdomadaires par défaut (de vendredi à vendredi),
  annualisés par racine de 52 ; en quotidien, racine de 252 ;
- rendements en fractions (0,05 = 5 %), sauf la participation et le Fear & Greed, en points de 0 à 100.

Chaque mesure dit sur quoi elle repose : les fonctions qui rendent un dictionnaire donnent ``debut``,
``fin`` et le nombre d'observations ``n`` ; celles qui rendent un tableau le disent dans ``.attrs``.
Ces mesures décrivent le passé : elles ne constituent pas un conseil en investissement.
"""

from __future__ import annotations

from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd

from . import _donnees as d

__all__ = [
    "rendement_total", "performances", "rendements_annuels", "rendements_mensuels", "saisonnalite",
    "volatilite", "perte_maximale", "var", "beta", "valorisation", "ratios", "regime", "participation",
    "fear_greed", "libelle_fear_greed",
]

Codes = Union[str, Iterable[str], None]

SEMAINES_PAR_AN = 52
SEANCES_PAR_AN = 252
PAR_AN = {"S": SEMAINES_PAR_AN, "J": SEANCES_PAR_AN}
FREQUENCES = {"S": "hebdomadaire", "J": "quotidienne"}

# Périodes de la page Performances : (libellé, nature)
PERIODES = {
    "SEM": ("Semaine en cours", "calendaire"), "MOIS": ("Mois en cours", "calendaire"),
    "TRIM": ("Trimestre en cours", "calendaire"), "AN": ("Depuis le 1er janvier", "calendaire"),
    "1S": ("1 semaine", "glissante"), "1M": ("1 mois", "glissante"), "3M": ("3 mois", "glissante"),
    "6M": ("6 mois", "glissante"), "1A": ("1 an", "glissante"), "3A": ("3 ans", "glissante"),
    "5A": ("5 ans", "glissante"), "10A": ("10 ans", "glissante"),
}
_DECALAGES = {
    "1S": pd.DateOffset(weeks=1), "1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3),
    "6M": pd.DateOffset(months=6), "1A": pd.DateOffset(years=1), "3A": pd.DateOffset(years=3),
    "5A": pd.DateOffset(years=5), "10A": pd.DateOffset(years=10),
}

# Bêta : observations communes minimales, zones de lecture
MIN_OBS_BETA = {"S": 26, "J": 60}
ZONES_BETA = ((0.5, "Très défensif"), (0.9, "Défensif"), (1.1, "Proche du marché"), (1.5, "Offensif"),
              (np.inf, "Très offensif"))

# Régime de marché (méthode mm_50_200_filtre de l'application)
REGIMES = ("Strong Bull", "Correction", "Transition haussière", "Transition baissière", "Rebond", "Strong Bear")

# Valorisation et ratios : secteur des banques et bornes au-delà desquelles un chiffre est jugé mal lu
SECTEUR_FINANCIER = "Services Financiers"
BORNES_MULTIPLES = {"per": (0.5, 100.0), "pb": (0.05, 30.0), "roe": (-1.0, 1.0), "p_ca": (0.01, 50.0),
                    "ve_ebe": (0.5, 60.0), "rendement": (0.0, 0.25)}
BORNES_RATIOS = {"marge_nette": (-1.0, 1.0), "marge_ebe": (-1.0, 1.0), "marge_exploitation": (-1.0, 1.0),
                 "roe": (-1.0, 1.0), "roa": (-0.5, 0.5), "taux_impot": (0.0, 0.8), "taux_distribution": (0.0, 3.0),
                 "endettement": (0.0, 20.0), "dette_nette_ebe": (-20.0, 30.0), "conversion": (-5.0, 10.0),
                 "coef_exploitation": (0.0, 1.5), "cout_risque_pnb": (0.0, 1.0), "credits_depots": (0.1, 3.0),
                 "fonds_propres_bilan": (0.0, 1.0), "croissance_ca": (-0.9, 5.0), "croissance_rn": (-10.0, 20.0)}
POSTES = ["resultat_net", "capitaux_propres", "total_bilan", "excedent_brut_exploitation", "resultat_exploitation",
          "resultat_avant_impot", "impot_resultat", "dettes_financieres", "tresorerie_actif", "tresorerie_passif",
          "flux_tresorerie_operationnel", "flux_investissement", "resultat_brut_exploitation", "cout_du_risque",
          "credits_clientele", "depots_clientele", "dotations_amortissements", "capacite_autofinancement",
          "valeur_ajoutee"]

# Fear & Greed BRVM (version révisée de l'étude, comme l'application)
FG_FENETRE = 756
FG_LISSAGE = 10
FG_MIN_OBS = 250
FG_MM_MOMENTUM = 125
FG_MM_PARTICIPATION = 50
FG_JOURS_52_SEMAINES = 250
FG_LISSAGE_FORCE = 10
FG_FENETRE_DEMANDE = 20
FG_VOL_COURT, FG_VOL_LONG = 20, 120
FG_PILIERS = {"tendance": ["momentum"], "participation": ["participation", "force"],
              "flux_stress": ["demande", "vol_baissiere"]}
FG_ECHELLE = ((25, "Peur extrême"), (44, "Peur"), (55, "Neutre"), (75, "Cupidité"), (100, "Cupidité extrême"))


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

def _version_pandas() -> tuple:
    return tuple(int(x) for x in pd.__version__.split(".")[:2])


FIN_DE_MOIS = "ME" if _version_pandas() >= (2, 2) else "M"


def _profil(profil: str) -> str:
    if profil not in d.PROFILS:
        raise ValueError(f"brvm : profil inconnu {profil!r}, choisir parmi {d.PROFILS}")
    return profil


def _frequence(frequence: str) -> str:
    f = str(frequence).upper()
    if f not in PAR_AN:
        raise ValueError(f"brvm : fréquence inconnue {frequence!r}, choisir « S » (hebdomadaire) ou « J » (quotidienne)")
    return f


def _liste(codes: Codes) -> list:
    if codes is None:
        return d.tickers()
    if isinstance(codes, str):
        return [d.resoudre(codes)]
    return [d.resoudre(c) for c in codes]


def _est_indice(code: str) -> bool:
    return code in d.infos()["indices"]


def _date(x) -> Optional[pd.Timestamp]:
    return None if x is None else pd.Timestamp(x)


def _sur_seances(serie: pd.Series, seances: pd.DatetimeIndex) -> pd.Series:
    """Dernier cours connu à chaque séance ; rien avant la première cotation."""
    serie = serie.dropna()
    return serie.reindex(serie.index.union(seances)).ffill().reindex(seances)


def _cloture(code: str) -> pd.Series:
    """Clôtures brutes : séances d'échange d'une action, séances publiées d'un indice."""
    s = d.indice(code)["cloture"] if _est_indice(code) else d.cours(code)["cloture"]
    return s.astype(float).dropna()


def _dividendes_reinvestis(prix: pd.Series, dividendes: pd.DataFrame) -> pd.Series:
    """Cours ajustés des dividendes : chaque dividende est réinvesti au cours de la veille du détachement
    (le dernier cours reste le cours réel, les cours antérieurs sont réduits)."""
    s = prix.index
    col = prix.to_numpy(dtype=float)
    facteur = np.ones(len(s))
    for jour, montant in zip(dividendes["date_detachement"], dividendes["montant_net_fcfa"]):
        k = int(s.searchsorted(jour))                  # première séance au détachement ou après
        if k == 0 or k >= len(s) or not np.isfinite(col[k - 1]) or col[k - 1] <= 0 or not np.isfinite(montant):
            continue
        f = 1 - float(montant) / col[k - 1]
        if 0 < f < 1:
            facteur[:k] *= f
    return pd.Series(col * facteur, index=s, name=prix.name)


def _dividendes_retenus(profil: str, ticker: Optional[str] = None) -> pd.DataFrame:
    div = d.dividendes(ticker, profil=profil, retenus=True)
    return div.dropna(subset=["date_detachement", "montant_net_fcfa"])


def _indice_dividendes_reinvestis(code: str, profil: str = "particulier") -> pd.Series:
    """Indice dividendes réinvestis : chaque séance ajoute au rendement publié de l'indice le rendement en
    dividendes de ses titres (poids de la veille x dividende net détaché / cours de la veille)."""
    s = d.seances()
    ind = _sur_seances(_cloture(code), s).dropna()
    s = ind.index
    poids = d.composition(code)
    px = pd.DataFrame({t: _sur_seances(_cloture(t), s) for t in poids.columns})
    w = poids.reindex(poids.index.union(s)).ffill().reindex(s).fillna(0.0).shift(1).fillna(0.0)
    rd = pd.DataFrame(0.0, index=s, columns=px.columns)
    div = _dividendes_retenus(profil)
    for t, g in div[div["ticker"].isin(px.columns)].groupby("ticker"):
        for jour, montant in zip(g["date_detachement"], g["montant_net_fcfa"]):
            k = int(s.searchsorted(jour))
            veille = px[t].iloc[k - 1] if 0 < k < len(s) else np.nan
            if np.isfinite(veille) and veille > 0 and np.isfinite(montant):
                rd.iloc[k, rd.columns.get_loc(t)] += float(montant) / veille
    rend_div = (w * rd).sum(axis=1)
    out = ind.iloc[0] * ((1 + ind.pct_change().fillna(0.0)) * (1 + rend_div)).cumprod()
    out.name = code
    return out


def _prix(code: str, dividendes: bool = False, profil: str = "particulier") -> pd.Series:
    """Prix à chaque séance (dernier cours connu), dividendes nets réinvestis si demandé."""
    c = d.resoudre(code)
    if _est_indice(c):
        if not dividendes:
            out = _sur_seances(_cloture(c), d.seances())
        elif c in d.INDICES_COMPOSITION:
            out = _indice_dividendes_reinvestis(c, profil).reindex(d.seances())
        else:
            raise ValueError(f"brvm : pas de version dividendes réinvestis pour {c} (composition non publiée)")
        out.name = c
        return out
    prix = _sur_seances(_cloture(c), d.seances())
    prix.name = c
    if dividendes:
        prix = _dividendes_reinvestis(prix, _dividendes_retenus(profil, c))
    return prix


def _panneau(codes: list, dividendes: bool, profil: str) -> pd.DataFrame:
    return pd.DataFrame({c: _prix(c, dividendes, profil) for c in codes}, index=d.seances())


def _fenetre(prix: pd.Series, debut, fin) -> pd.Series:
    return prix.loc[_date(debut):_date(fin)].dropna()


def _rendements(prix, frequence: str = "S"):
    """Rendements simples : de vendredi à vendredi (dernier cours connu de la semaine) ou d'une séance
    à la suivante."""
    p = prix.resample("W-FRI").last() if frequence == "S" else prix
    return p.pct_change(fill_method=None).iloc[1:]


def _bornes(serie: pd.Series) -> tuple:
    s = serie.dropna()
    return (s.index.min(), s.index.max()) if len(s) else (pd.NaT, pd.NaT)


# ---------------------------------------------------------------------------
# A. Rendements
# ---------------------------------------------------------------------------

def rendement_total(ticker: str, debut=None, fin=None, profil: str = "particulier") -> pd.DataFrame:
    """Valeur d'un placement en base 100, dividendes nets d'IRVM réinvestis à la date de détachement.

    Une ligne par séance : ``cloture`` (cours ou valeur publiée), ``valeur`` (base 100 à la première
    séance de la fenêtre) et, pour une action, ``dividende`` (montant net par action détaché ce jour,
    0 sinon). Seuls les dividendes ``retenus`` sont crédités. Pour le BRVM Composite et les indices
    sectoriels, la valeur ajoute au rendement publié le rendement en dividendes de leurs titres, pondéré
    par ``brvm.composition()``.

    ``.attrs`` : ``debut``, ``fin``, ``seances``, ``dividendes`` (nombre de dividendes crédités) et
    ``profil``.
    """
    c = d.resoudre(ticker)
    _profil(profil)
    brut = _prix(c, False)
    total = _prix(c, True, profil)
    df = pd.DataFrame({"cloture": brut, "valeur": total}).loc[_date(debut):_date(fin)].dropna()
    if df.empty:
        raise KeyError(f"brvm : aucune séance de {c} dans la fenêtre demandée")
    df["valeur"] = df["valeur"] / df["valeur"].iloc[0] * 100
    nb = 0
    if not _est_indice(c):
        div = _dividendes_retenus(profil, c)
        jours = df.index[np.clip(df.index.searchsorted(div["date_detachement"]), 0, len(df) - 1)]
        dans = (div["date_detachement"] > df.index[0]).to_numpy() & (div["date_detachement"] <= df.index[-1]).to_numpy()
        df["dividende"] = pd.Series(div["montant_net_fcfa"].to_numpy()[dans], index=jours[dans]).groupby(level=0).sum()
        df["dividende"] = df["dividende"].fillna(0.0)
        nb = int(dans.sum())
    df.index.name = "date"
    df.attrs = {"debut": df.index[0], "fin": df.index[-1], "seances": len(df), "dividendes": nb, "profil": profil}
    return df


def _debut_calendaire(code: str, fin: pd.Timestamp) -> pd.Timestamp:
    fin = fin.normalize()
    if code == "SEM":
        return fin - pd.Timedelta(days=fin.weekday())
    if code == "MOIS":
        return fin.replace(day=1)
    if code == "TRIM":
        return pd.Timestamp(fin.year, 3 * ((fin.month - 1) // 3) + 1, 1)
    return pd.Timestamp(fin.year, 1, 1)


def _date_base(code: str, fin: pd.Timestamp, seances: pd.DatetimeIndex) -> Optional[pd.Timestamp]:
    """Séance dont la clôture sert de référence à la période ``code`` qui finit à ``fin``."""
    if code in _DECALAGES:
        avant = seances[seances <= fin - _DECALAGES[code]]
    else:
        avant = seances[seances < _debut_calendaire(code, fin)]
    return avant.max() if len(avant) else None


def _annualiser(r, base, fin):
    ans = (pd.Timestamp(fin) - pd.Timestamp(base)).days / 365.25
    return (1 + r) ** (1 / ans) - 1 if ans >= 1 else r


def _derniere_seance(fin=None) -> pd.Timestamp:
    s = d.seances()
    s = s[s <= pd.Timestamp(fin)] if fin is not None else s
    if not len(s):
        raise KeyError(f"brvm : aucune séance jusqu'au {fin}")
    return s.max()


def performances(tickers: Codes = None, fin=None, dividendes: bool = False, annualise: bool = False,
                 profil: str = "particulier") -> pd.DataFrame:
    """Rendement de chaque titre sur les périodes de l'application, une ligne par titre.

    Colonnes : ``SEM``, ``MOIS``, ``TRIM``, ``AN`` (semaine, mois, trimestre et année en cours, depuis la
    dernière clôture de la période précédente) puis ``1S``, ``1M``, ``3M``, ``6M``, ``1A``, ``3A``,
    ``5A``, ``10A`` (périodes glissantes, depuis la dernière séance à cette distance de ``fin``).

    - ``tickers`` : un code ou une liste (actions ou indices) ; toutes les actions par défaut ;
    - ``fin`` : date de fin (dernière séance par défaut) ;
    - ``dividendes`` : dividendes nets réinvestis ;
    - ``annualise`` : rythme annuel au-delà d'un an, inchangé en deçà.

    NaN quand le titre n'était pas coté à la séance de base. ``.attrs`` : ``fin`` et ``bases`` (séance
    de base de chaque période).
    """
    codes = _liste(tickers)
    _profil(profil)
    s = d.seances()
    fin_s = _derniere_seance(fin)
    prix = _panneau(codes, dividendes, profil)
    b = prix.loc[fin_s]
    out, bases = {}, {}
    for code in PERIODES:
        base = _date_base(code, fin_s, s)
        bases[code] = base
        if base is None:
            out[code] = pd.Series(np.nan, index=codes)
            continue
        a = prix.loc[base]
        r = (b / a - 1).where(a > 0)
        out[code] = _annualiser(r, base, fin_s) if annualise else r
    df = pd.DataFrame(out)
    df.index.name = "ticker"
    df.attrs = {"fin": fin_s, "bases": bases, "dividendes": dividendes, "annualise": annualise}
    return df


def rendements_annuels(tickers: Codes = None, depuis: int = 2010, fin=None, dividendes: bool = False,
                       profil: str = "particulier") -> pd.DataFrame:
    """Rendement de chaque titre par année civile, une colonne par année : dernière clôture de l'année
    rapportée à celle de l'année précédente.

    L'année d'introduction est mesurée depuis le premier cours : elle est partielle, et
    ``.attrs["partielles"]`` donne, pour chaque titre, ses années partielles.
    """
    codes = _liste(tickers)
    _profil(profil)
    s = d.seances()
    fin_s = _derniere_seance(fin)
    prix = _panneau(codes, dividendes, profil)
    res, partiel = {}, {}
    for annee in range(int(depuis), fin_s.year + 1):
        debut = pd.Timestamp(annee, 1, 1)
        dans = s[(s >= debut) & (s <= min(fin_s, pd.Timestamp(annee, 12, 31)))]
        if not len(dans):
            continue
        avant = s[s < debut]
        a0 = prix.loc[avant.max()] if len(avant) else pd.Series(np.nan, index=prix.columns)
        premier = prix.loc[dans].bfill().iloc[0]
        base = a0.where(a0 > 0, premier)
        res[annee] = (prix.loc[dans.max()] / base - 1).where(base > 0)
        partiel[annee] = ~(a0 > 0) & (premier > 0)
    df = pd.DataFrame(res, index=codes)
    df.index.name = "ticker"
    p = pd.DataFrame(partiel, index=codes)
    df.attrs = {"fin": fin_s, "partielles": {t: [int(a) for a in p.columns[p.loc[t]]] for t in codes}}
    return df


def rendements_mensuels(ticker: str, dividendes: bool = False, profil: str = "particulier") -> pd.DataFrame:
    """Années en lignes, mois (1 à 12) en colonnes : dernière clôture du mois rapportée à celle du mois
    précédent."""
    c = d.resoudre(ticker)
    _profil(profil)
    m = _prix(c, dividendes, profil).dropna().resample(FIN_DE_MOIS).last()
    r = m.pct_change(fill_method=None).dropna()
    if r.empty:
        return pd.DataFrame(columns=range(1, 13))
    df = pd.DataFrame({"annee": r.index.year, "mois": r.index.month, "r": r.to_numpy()})
    out = df.pivot(index="annee", columns="mois", values="r").reindex(columns=range(1, 13))
    out.columns.name = "mois"
    out.attrs = {"debut": r.index.min(), "fin": r.index.max(), "mois": int(r.notna().sum())}
    return out


def saisonnalite(ticker: str, dividendes: bool = False, profil: str = "particulier") -> pd.DataFrame:
    """Pour chaque mois (1 à 12) : rendement moyen, médian, part des années en hausse et nombre d'années."""
    m = rendements_mensuels(ticker, dividendes, profil)
    n = m.notna().sum()
    out = pd.DataFrame({"moyenne": m.mean(), "mediane": m.median(), "hausse": (m > 0).sum() / n.replace(0, np.nan),
                        "annees": n})
    out.index.name = "mois"
    out.attrs = dict(m.attrs)
    return out


# ---------------------------------------------------------------------------
# B. Risque
# ---------------------------------------------------------------------------

def volatilite(ticker: str, debut=None, fin=None, frequence: str = "S", fenetre: Optional[int] = None,
               dividendes: bool = False, profil: str = "particulier"):
    """Volatilité annualisée : écart-type des rendements hebdomadaires x racine de 52 (``frequence="S"``,
    comme l'application) ou quotidiens x racine de 252 (``"J"``).

    Sans ``fenetre`` : dictionnaire ``volatilite``, ``frequence``, ``n`` (rendements), ``debut``, ``fin``.
    Avec ``fenetre`` (nombre de rendements, par exemple 52 semaines) : Series de la volatilité glissante.

    En quotidien, un jour sans échange compte pour un rendement nul : la volatilité d'un titre peu
    liquide en est réduite. L'hebdomadaire est moins sensible à ces trous.
    """
    f = _frequence(frequence)
    r = _rendements(_fenetre(_prix(d.resoudre(ticker), dividendes, _profil(profil)), debut, fin), f).dropna()
    k = np.sqrt(PAR_AN[f])
    if fenetre is not None:
        out = (r.rolling(int(fenetre), min_periods=int(fenetre)).std(ddof=1) * k).dropna()
        out.name = "volatilite"
        out.attrs = {"frequence": FREQUENCES[f], "fenetre": int(fenetre)}
        return out
    debut_r, fin_r = _bornes(r)
    return {"volatilite": float(r.std(ddof=1) * k) if len(r) >= 2 else np.nan, "frequence": FREQUENCES[f],
            "n": int(len(r)), "debut": debut_r, "fin": fin_r}


def _plus_longue_baisse(dd: pd.Series) -> float:
    """Plus longue période sous un ancien plus haut, en jours calendaires (du plus haut au retour à ce
    niveau, ou à la fin de la fenêtre)."""
    sous = (dd < -1e-9).to_numpy()
    if not sous.any():
        return 0.0
    dates, plus_long, i, n = dd.index, 0, 0, len(dd)
    while i < n:
        if not sous[i]:
            i += 1
            continue
        j = i
        while j < n and sous[j]:
            j += 1
        plus_long = max(plus_long, (dates[min(j, n - 1)] - dates[max(i - 1, 0)]).days)
        i = j
    return float(plus_long)


def perte_maximale(ticker: str, debut=None, fin=None, dividendes: bool = False, profil: str = "particulier") -> dict:
    """Plus forte baisse depuis un plus haut, sur les cours de chaque séance.

    Rend ``perte_max`` (fraction négative), ``date_sommet``, ``date_creux``, ``date_reprise`` (première
    séance revenue au niveau du sommet, NaT si pas encore), ``seances_baisse`` (du sommet au creux),
    ``seances_reprise`` (du creux à la reprise), ``perte_courante`` (recul de la dernière séance depuis le
    plus haut), ``plus_longue_baisse_jours`` (plus longue période sous un ancien plus haut, en jours
    calendaires), ``n`` séances, ``debut`` et ``fin``.
    """
    p = _fenetre(_prix(d.resoudre(ticker), dividendes, _profil(profil)), debut, fin)
    vide = {"perte_max": np.nan, "date_sommet": pd.NaT, "date_creux": pd.NaT, "date_reprise": pd.NaT,
            "seances_baisse": None, "seances_reprise": None, "perte_courante": np.nan,
            "plus_longue_baisse_jours": np.nan, "n": int(len(p)), "debut": _bornes(p)[0], "fin": _bornes(p)[1]}
    if len(p) < 2:
        return vide
    dd = p / p.cummax() - 1
    out = {**vide, "perte_max": float(dd.min()), "perte_courante": float(dd.iloc[-1]),
           "plus_longue_baisse_jours": _plus_longue_baisse(dd)}
    if dd.min() >= 0:
        return out
    creux = dd.idxmin()
    sommet = p.loc[:creux].idxmax()
    apres = p.loc[creux:]
    revenu = apres[apres >= p.loc[sommet]]
    reprise = revenu.index[0] if len(revenu) else pd.NaT
    pos = p.index.get_loc
    out.update({"date_sommet": sommet, "date_creux": creux, "date_reprise": reprise,
                "seances_baisse": int(pos(creux) - pos(sommet)),
                "seances_reprise": int(pos(reprise) - pos(creux)) if pd.notna(reprise) else None})
    return out


def var(ticker: str, niveau: float = 0.95, debut=None, fin=None, frequence: str = "S", dividendes: bool = False,
        profil: str = "particulier") -> dict:
    """VaR historique : perte qu'un rendement n'a dépassée que dans ``1 - niveau`` des cas (quantile 5 % à
    95 %), d'une semaine par défaut comme l'application, d'une séance avec ``frequence="J"``.

    Rend ``var`` et ``cvar`` (moyenne des rendements au-delà de la VaR), en fractions négatives, avec
    ``niveau``, ``frequence``, ``n``, ``debut`` et ``fin``.
    """
    if not 0 < niveau < 1:
        raise ValueError("brvm : niveau entre 0 et 1, par exemple 0.95")
    f = _frequence(frequence)
    r = _rendements(_fenetre(_prix(d.resoudre(ticker), dividendes, _profil(profil)), debut, fin), f).dropna()
    debut_r, fin_r = _bornes(r)
    q = float(r.quantile(1 - niveau)) if len(r) else np.nan
    return {"var": q, "cvar": float(r[r <= q].mean()) if len(r) else np.nan, "niveau": niveau,
            "frequence": FREQUENCES[f], "n": int(len(r)), "debut": debut_r, "fin": fin_r}


def _lecture_beta(b: float) -> str:
    if b is None or not np.isfinite(b):
        return ""
    if b < 0:
        return "Inverse du marché"
    return next(lib for borne, lib in ZONES_BETA if b < borne)


def beta(ticker: str, reference: str = "BRVMC", debut=None, fin=None, frequence: str = "S",
         taux_sans_risque: float = 0.03, fenetre: Optional[int] = None):
    """Bêta d'un titre face à une référence (indice ou action), par régression de leurs rendements en
    excès du taux sans risque, sur leurs dates communes.

    Sans ``fenetre`` : dictionnaire ``beta``, ``erreur_type``, intervalle à 95 % (``ic_bas``,
    ``ic_haut``), ``r2``, ``correlation``, ``alpha`` (de Jensen, annualisé), volatilités annualisées du
    titre, de la référence et propre au titre (``vol_specifique``), ``lecture`` (« Défensif »,
    « Offensif »…), ``n`` observations, ``debut`` et ``fin``. Rien n'est publié (NaN) sous 26 semaines ou
    60 séances communes.

    Avec ``fenetre`` (en jours calendaires, 365 dans l'application en hebdomadaire) : Series du bêta
    glissant, publié quand la fenêtre est complète et compte 60 % des observations attendues.
    """
    f = _frequence(frequence)
    k = PAR_AN[f]
    r_t = _rendements(_fenetre(_prix(d.resoudre(ticker)), debut, fin), f)
    r_r = _rendements(_fenetre(_prix(d.resoudre(reference)), debut, fin), f)
    m = pd.concat([r_t, r_r], axis=1, keys=["y", "x"]).dropna()
    n = len(m)
    if fenetre is not None:
        jours = int(fenetre)
        if m.empty:
            return pd.Series(dtype=float, name="beta")
        attendu = jours / 7 if f == "S" else jours * SEANCES_PAR_AN / 365
        mini = max(int(0.6 * attendu), 8)
        fen = m.rolling(f"{jours}D", min_periods=mini)
        b = (fen["y"].cov(m["x"]) / fen["x"].var().replace(0, np.nan)).where(m["x"].rolling(f"{jours}D").count() >= mini)
        out = b.loc[b.index >= m.index[0] + pd.Timedelta(days=jours - 1)].dropna()
        out.name = "beta"
        out.attrs = {"reference": d.resoudre(reference), "frequence": FREQUENCES[f], "fenetre_jours": jours}
        return out
    vide = {"beta": np.nan, "erreur_type": np.nan, "ic_bas": np.nan, "ic_haut": np.nan, "r2": np.nan,
            "correlation": np.nan, "alpha": np.nan, "vol_titre": np.nan, "vol_ref": np.nan, "vol_specifique": np.nan,
            "lecture": "", "reference": d.resoudre(reference), "frequence": FREQUENCES[f], "n": n,
            "debut": m.index.min() if n else pd.NaT, "fin": m.index.max() if n else pd.NaT}
    if n < MIN_OBS_BETA[f] or not m["x"].var() > 0 or not m["y"].var() > 0:
        return vide
    rf = (1 + taux_sans_risque) ** (1 / k) - 1
    y, x = m["y"] - rf, m["x"] - rf
    b = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
    alpha = float(y.mean() - b * x.mean())
    resid = y - alpha - b * x
    sxx = float(((x - x.mean()) ** 2).sum())
    se = float(np.sqrt((resid ** 2).sum() / (n - 2) / sxx)) if sxx > 0 else np.nan
    corr = float(np.corrcoef(x, y)[0, 1])
    return {**vide, "beta": b, "erreur_type": se, "ic_bas": b - 1.96 * se, "ic_haut": b + 1.96 * se, "r2": corr ** 2,
            "correlation": corr, "alpha": alpha * k, "vol_titre": float(m["y"].std(ddof=1) * np.sqrt(k)),
            "vol_ref": float(m["x"].std(ddof=1) * np.sqrt(k)), "vol_specifique": float(resid.std(ddof=1) * np.sqrt(k)),
            "lecture": _lecture_beta(b)}


# ---------------------------------------------------------------------------
# C. Valorisation datée et ratios
# ---------------------------------------------------------------------------

def _date_regle(exercice: int, dividendes: pd.DataFrame) -> pd.Timestamp:
    """Date prudente à laquelle les comptes d'un exercice sont supposés connus, faute de date de
    publication : le plus tard du 1er juillet N+1 et du détachement du dividende N s'il est daté, sinon le
    1er octobre N+1."""
    det = dividendes.loc[dividendes["exercice"] == exercice, "date_detachement"].dropna()
    if len(det):
        return max(pd.Timestamp(exercice + 1, 7, 1), det.min())
    return pd.Timestamp(exercice + 1, 10, 1)


def _sources(ticker: str) -> tuple:
    """(chiffres annuels des rapports, fondamentaux Sikafinance, dividendes retenus) d'une action."""
    chf = d.chiffres(ticker)
    chf = chf[chf["periode"].isin(["A", "T4"])].copy()
    fond = d.fondamentaux(ticker)
    div = d.dividendes(ticker, retenus=True)
    return chf, fond, div


def _connu(chf: pd.DataFrame, fond: pd.DataFrame, div: pd.DataFrame, date: pd.Timestamp) -> tuple:
    """Lignes connues à ``date`` : un chiffre de rapport à sa date de publication, un fondamental
    Sikafinance à la première date de publication d'un rapport annuel de l'exercice ou, à défaut, à la
    date prudente ``_date_regle``. Rend aussi la date de connaissance de chaque exercice."""
    exercices = set(fond["exercice"]) | set(chf["exercice"])
    pub = chf.dropna(subset=["date_publication"]).groupby("exercice")["date_publication"].min()
    quand = {}
    for e in exercices:
        regle = _date_regle(int(e), div)
        quand[int(e)] = min(pub.get(e, regle), regle)
    date_ligne = chf["date_publication"].fillna(chf["exercice"].map(quand))
    return chf[date_ligne <= date], fond[fond["exercice"].map(quand) <= date], quand


def _candidats(chf: pd.DataFrame, fond: pd.DataFrame, indicateur: str, colonne_sika: Optional[str] = None) -> list:
    """(exercice, valeur, source) d'un poste annuel : Sikafinance d'abord, puis rapport annuel, puis
    cumul du 4e trimestre."""
    out = []
    lignes = chf[chf["indicateur"] == indicateur]
    for e, v, p in zip(lignes["exercice"], lignes["valeur_mfcfa"], lignes["periode"]):
        out.append((int(e), float(v), f"rapport {p}"))
    if colonne_sika is not None and colonne_sika in fond:
        for e, v in zip(fond["exercice"], fond[colonne_sika]):
            if pd.notna(v):
                out.append((int(e), float(v), "Sikafinance"))
    return out


_RANG_SOURCE = {"Sikafinance": 0, "rapport A": 1, "rapport T4": 2}


def _choisir(cands: list, exercice: Optional[int] = None, avant: bool = False) -> tuple:
    if exercice is not None:
        cands = [c for c in cands if (c[0] <= exercice if avant else c[0] == exercice)]
    if not cands:
        return None, None, None
    return sorted(cands, key=lambda c: (-c[0], _RANG_SOURCE.get(c[2], 9)))[0]


def _rapport(num, den) -> float:
    return num / den if num is not None and den is not None and np.isfinite(num) and np.isfinite(den) and den > 0 \
        else np.nan


def valorisation(ticker: Codes = None, date=None) -> pd.DataFrame:
    """Multiples de marché au cours d'une date, avec les seuls comptes connus à cette date.

    Une ligne par action (toutes par défaut) : ``cours`` à la dernière séance jusqu'à ``date`` (dernière
    séance par défaut), ``capitalisation_mfcfa`` (cours x nombre de titres actuel, en millions de FCFA),
    exercice retenu (le plus récent dont le résultat net est connu à la date) et sa ``date_connue``,
    postes en millions de FCFA, ``bnpa_fcfa``, dernier dividende net retenu détaché avant la date, puis
    ``per``, ``pb`` (cours / capitaux propres), ``roe``, ``p_ca`` (cours / chiffre d'affaires, PNB pour
    les banques), ``ve_ebe`` (hors banques) et ``rendement`` (dividende / cours).

    Un exercice est connu à la date de publication de son premier rapport annuel sur brvm.org ; à
    défaut, au plus tard du 1er juillet N+1 et du détachement du dividende N, ou au 1er octobre N+1 sans
    dividende daté. Un multiple sort (NaN) quand son dénominateur est négatif ou nul, ou qu'il dépasse
    des bornes plausibles (chiffre probablement mal lu). Le nombre de titres est celui de la fiche
    actuelle : une augmentation de capital passée n'est pas reconstituée.
    """
    codes = _liste(ticker)
    date_s = _derniere_seance(date)
    soc = d.societes()
    lignes = []
    for t in codes:
        if _est_indice(t):
            raise ValueError(f"brvm : {t} est un indice, la valorisation porte sur des actions")
        c = d.cours(t, fin=date_s)["cloture"].dropna()
        fiche = soc.loc[t] if t in soc.index else None
        nb = float(fiche["nombre_titres"]) if fiche is not None and pd.notna(fiche["nombre_titres"]) else np.nan
        ligne = {"ticker": t, "nom": fiche["nom"] if fiche is not None else t,
                 "secteur": fiche["secteur"] if fiche is not None else "", "date_cours": pd.NaT, "cours": np.nan,
                 "nombre_titres": nb, "capitalisation_mfcfa": np.nan}
        ligne["financier"] = ligne["secteur"] == SECTEUR_FINANCIER
        if len(c):
            ligne.update({"date_cours": c.index[-1], "cours": float(c.iloc[-1]),
                          "capitalisation_mfcfa": float(c.iloc[-1]) * nb / 1e6})
        chf, fond, div = _sources(t)
        chf, fond, quand = _connu(chf, fond, div, date_s)
        ex, rn, src_rn = _choisir(_candidats(chf, fond, "resultat_net", "resultat_net_mfcfa"))
        ligne.update({"exercice": ex, "date_connue": quand.get(ex, pd.NaT) if ex is not None else pd.NaT,
                      "resultat_net_mfcfa": rn, "source_rn": src_rn})
        if ex is not None:
            ca_nom = "produit_net_bancaire" if ligne["financier"] else "chiffre_affaires"
            _, ca, src_ca = _choisir(_candidats(chf, fond, ca_nom, "chiffre_affaires_mfcfa"), ex)
            if ca is None and ligne["financier"]:
                _, ca, src_ca = _choisir(_candidats(chf, fond, "chiffre_affaires", "chiffre_affaires_mfcfa"), ex)
            ex_cp, cp, _ = _choisir(_candidats(chf, fond, "capitaux_propres"), ex, avant=True)
            ligne.update({"chiffre_affaires_mfcfa": ca, "source_ca": src_ca, "capitaux_propres_mfcfa": cp,
                          "exercice_cp": ex_cp})
            if not ligne["financier"]:
                ebe = _choisir(_candidats(chf, fond, "excedent_brut_exploitation"), ex)[1]
                dettes = _choisir(_candidats(chf, fond, "dettes_financieres"), ex)[1]
                t_actif = _choisir(_candidats(chf, fond, "tresorerie_actif"), ex)[1]
                t_passif = _choisir(_candidats(chf, fond, "tresorerie_passif"), ex)[1] or 0.0
                ligne["ebe_mfcfa"] = ebe
                ligne["dette_nette_mfcfa"] = (dettes + abs(t_passif) - t_actif) \
                    if dettes is not None and t_actif is not None else None
        verses = div[(div["date_detachement"] <= date_s)].dropna(subset=["date_detachement", "montant_net_fcfa"])
        verses = verses.sort_values("date_detachement")
        if len(verses):
            ligne["dividende_net_fcfa"] = float(verses["montant_net_fcfa"].iloc[-1])
            ligne["date_dividende"] = verses["date_detachement"].iloc[-1]
        lignes.append(ligne)
    tab = pd.DataFrame(lignes)
    for col in ("exercice", "date_connue", "resultat_net_mfcfa", "source_rn", "chiffre_affaires_mfcfa", "source_ca",
                "capitaux_propres_mfcfa", "exercice_cp", "ebe_mfcfa", "dette_nette_mfcfa", "dividende_net_fcfa",
                "date_dividende"):
        if col not in tab:
            tab[col] = np.nan
    for col in ("resultat_net_mfcfa", "chiffre_affaires_mfcfa", "capitaux_propres_mfcfa", "ebe_mfcfa",
                "dette_nette_mfcfa", "dividende_net_fcfa"):
        tab[col] = pd.to_numeric(tab[col], errors="coerce")
    for col in ("exercice", "exercice_cp"):
        tab[col] = pd.to_numeric(tab[col], errors="coerce").astype("Int64")
    for col in ("date_connue", "date_dividende"):
        tab[col] = pd.to_datetime(tab[col])
    cap = tab["capitalisation_mfcfa"]
    pos = lambda s: s.where(s > 0)  # noqa: E731
    tab["bnpa_fcfa"] = tab["resultat_net_mfcfa"] * 1e6 / tab["nombre_titres"]
    tab["per"] = cap / pos(tab["resultat_net_mfcfa"])
    tab["pb"] = cap / pos(tab["capitaux_propres_mfcfa"])
    tab["roe"] = tab["resultat_net_mfcfa"] / pos(tab["capitaux_propres_mfcfa"])
    tab["p_ca"] = cap / pos(tab["chiffre_affaires_mfcfa"])
    tab["valeur_entreprise_mfcfa"] = cap + tab["dette_nette_mfcfa"]
    tab["ve_ebe"] = tab["valeur_entreprise_mfcfa"] / pos(tab["ebe_mfcfa"])
    tab["rendement"] = tab["dividende_net_fcfa"] / pos(tab["cours"])
    for m, (bas, haut) in BORNES_MULTIPLES.items():
        tab.loc[(tab[m] < bas) | (tab[m] > haut), m] = np.nan
    colonnes = ["ticker", "nom", "secteur", "financier", "date_cours", "cours", "nombre_titres", "capitalisation_mfcfa",
                "exercice", "date_connue", "resultat_net_mfcfa", "source_rn", "chiffre_affaires_mfcfa", "source_ca",
                "capitaux_propres_mfcfa", "exercice_cp", "ebe_mfcfa", "dette_nette_mfcfa", "bnpa_fcfa",
                "dividende_net_fcfa", "date_dividende", "per", "pb", "roe", "p_ca", "valeur_entreprise_mfcfa",
                "ve_ebe", "rendement"]
    tab = tab[colonnes].set_index("ticker")
    tab.attrs = {"date": date_s}
    return tab


def ratios(ticker: str) -> pd.DataFrame:
    """Comptes annuels et ratios d'une société, une ligne par exercice (montants en millions de FCFA).

    Chiffre d'affaires (PNB pour une banque) et résultat net : Sikafinance d'abord, puis les rapports de
    brvm.org (exercice complet, sinon cumul du 4e trimestre), avec leur source dans ``source_ca`` et
    ``source_rn`` ; les autres postes viennent des rapports (``brvm.chiffres()``).

    Ratios, en fractions : ``croissance_ca``, ``croissance_rn`` (sur deux exercices consécutifs),
    ``marge_nette``, ``roe``, ``roa``, ``taux_impot``, ``taux_distribution`` (dividende de l'exercice /
    BNPA) ; pour une banque ``coef_exploitation``, ``cout_risque_pnb``, ``credits_depots``,
    ``fonds_propres_bilan`` ; sinon ``marge_ebe``, ``marge_exploitation``, ``endettement`` (dettes
    financières / capitaux propres), ``dette_nette_ebe``, ``conversion`` (flux opérationnel / résultat
    net) et ``flux_libre``. Un ratio hors de bornes plausibles est mis à NaN (chiffre probablement mal lu).
    """
    t = d.resoudre(ticker)
    if _est_indice(t):
        raise ValueError(f"brvm : {t} est un indice, les ratios portent sur des actions")
    soc = d.societes()
    fiche = soc.loc[t] if t in soc.index else None
    financier = fiche is not None and fiche["secteur"] == SECTEUR_FINANCIER
    nb = float(fiche["nombre_titres"]) if fiche is not None and pd.notna(fiche["nombre_titres"]) else np.nan
    chf, fond, div = _sources(t)
    if len(chf):
        chf = chf.assign(_rang=(chf["periode"] != "A").astype(int)).sort_values("_rang")
        chf = chf.drop_duplicates(["exercice", "indicateur"])
        tab = chf.pivot(index="exercice", columns="indicateur", values="valeur_mfcfa")
    else:
        tab = pd.DataFrame()
    cle_ca = "produit_net_bancaire" if financier else "chiffre_affaires"
    for nom, cible, col_sika in (("ca", cle_ca, "chiffre_affaires_mfcfa"), ("rn", "resultat_net", "resultat_net_mfcfa")):
        if cible not in tab.columns:
            tab[cible] = np.nan
        tab[f"source_{nom}"] = pd.Series(np.where(tab[cible].notna(), "rapports brvm.org", None), index=tab.index,
                                         dtype=object)
        for an, v in zip(fond["exercice"], fond[col_sika]):
            if pd.isna(v):
                continue
            if an not in tab.index:
                tab.loc[an, :] = np.nan
            tab.at[an, cible] = float(v)
            tab.at[an, f"source_{nom}"] = "Sikafinance"
    if tab.empty:
        return tab
    tab = tab.sort_index()
    tab.index = tab.index.astype(int)
    tab.index.name = "exercice"
    tab["ca"] = pd.to_numeric(tab[cle_ca], errors="coerce")
    if financier and "chiffre_affaires" in tab.columns:
        tab["ca"] = tab["ca"].fillna(pd.to_numeric(tab["chiffre_affaires"], errors="coerce"))
    for col in POSTES:
        tab[col] = pd.to_numeric(tab[col], errors="coerce") if col in tab.columns else np.nan
    montant = div["montant_brut_fcfa"].fillna(div["montant_net_fcfa"])
    par_ex = montant.groupby(div["exercice"].astype("Int64")).sum()
    tab["dividende_action"] = [par_ex.get(e, np.nan) for e in tab.index]

    prec = tab.shift(1)
    consecutif = pd.Series(tab.index, index=tab.index).diff() == 1
    pos = lambda s: s.where(s > 0)  # noqa: E731
    tab["croissance_ca"] = np.where(consecutif & (prec["ca"] > 0), tab["ca"] / prec["ca"] - 1, np.nan)
    tab["croissance_rn"] = np.where(consecutif & (prec["resultat_net"].abs() > 0),
                                    (tab["resultat_net"] - prec["resultat_net"]) / prec["resultat_net"].abs(), np.nan)
    tab["marge_nette"] = tab["resultat_net"] / pos(tab["ca"])
    tab["roe"] = tab["resultat_net"] / pos(tab["capitaux_propres"])
    tab["roa"] = tab["resultat_net"] / pos(tab["total_bilan"])
    tab["taux_impot"] = tab["impot_resultat"].abs() / pos(tab["resultat_avant_impot"])
    if financier:
        tab["coef_exploitation"] = 1 - tab["resultat_brut_exploitation"] / pos(tab["ca"])
        tab["cout_risque_pnb"] = tab["cout_du_risque"].abs() / pos(tab["ca"])
        tab["credits_depots"] = tab["credits_clientele"] / pos(tab["depots_clientele"])
        tab["fonds_propres_bilan"] = tab["capitaux_propres"] / pos(tab["total_bilan"])
    else:
        dette_nette = tab["dettes_financieres"] + tab["tresorerie_passif"].abs().fillna(0) - tab["tresorerie_actif"]
        tab["dette_nette"] = dette_nette
        tab["marge_ebe"] = tab["excedent_brut_exploitation"] / pos(tab["ca"])
        tab["marge_exploitation"] = tab["resultat_exploitation"] / pos(tab["ca"])
        tab["endettement"] = tab["dettes_financieres"] / pos(tab["capitaux_propres"])
        tab["dette_nette_ebe"] = dette_nette / pos(tab["excedent_brut_exploitation"])
        tab["conversion"] = tab["flux_tresorerie_operationnel"] / pos(tab["resultat_net"])
        tab["flux_libre"] = tab["flux_tresorerie_operationnel"] + tab["flux_investissement"]
    tab["bnpa_fcfa"] = tab["resultat_net"] * 1e6 / nb if np.isfinite(nb) and nb > 0 else np.nan
    tab["taux_distribution"] = tab["dividende_action"] / pos(tab["bnpa_fcfa"])
    for r, (bas, haut) in BORNES_RATIOS.items():
        if r in tab.columns:
            tab[r] = pd.to_numeric(tab[r], errors="coerce")
            tab.loc[(tab[r] < bas) | (tab[r] > haut), r] = np.nan
    tab.columns.name = None
    tab.attrs = {"ticker": t, "financier": financier}
    return tab


# ---------------------------------------------------------------------------
# D. Marché
# ---------------------------------------------------------------------------

def _au_dessus(x: pd.Series, y: pd.Series, bande: float, confirmation: int) -> pd.Series:
    """État « x au-dessus de y » (1/0) : il ne bascule que si x dépasse y de plus de ``bande``, dans un
    sens ou dans l'autre, pendant ``confirmation`` séances consécutives."""
    haut = (x > y * (1 + bande)).astype(int).rolling(confirmation).min() == 1
    bas = (x < y * (1 - bande)).astype(int).rolling(confirmation).min() == 1
    etat = pd.Series(np.nan, index=x.index)
    etat[haut] = 1.0
    etat[bas] = 0.0
    valide = x.notna() & y.notna()
    etat = etat.where(valide)
    if valide.any():
        debut = valide.idxmax()
        if pd.isna(etat[debut]):
            etat[debut] = float(x[debut] > y[debut])
    return etat.ffill().where(valide)


def regime(indice: str = "BRVMC", debut=None, fin=None, mm_moyen: int = 50, mm_long: int = 200,
           bande: float = 0.01, confirmation: int = 3) -> pd.DataFrame:
    """Régime de marché de chaque séance, méthode de l'application (moyennes 50 et 200 filtrées).

    Trois comparaisons, chacune filtrée par une ``bande`` de 1 % et ``confirmation`` séances : prix et
    moyenne longue (direction), moyenne moyenne et moyenne longue (structure), prix et moyenne moyenne
    (court terme). Six régimes : « Strong Bull », « Correction », « Transition haussière », « Transition
    baissière », « Rebond », « Strong Bear ». Manquant avant ``mm_long`` séances.

    Colonnes : ``prix``, ``mm_moyen``, ``mm_long``, ``regime``. Calculé sur tout l'historique puis coupé
    à la fenêtre. ``.attrs`` : ``regime_actuel``, ``depuis`` (entrée dans ce régime), ``seances_depuis``.
    Le code peut être celui d'une action (séances où elle a échangé).
    """
    c = d.resoudre(indice)
    p = _cloture(c).sort_index()
    mm, ml = p.rolling(mm_moyen).mean(), p.rolling(mm_long).mean()
    dr = _au_dessus(p, ml, bande, confirmation)
    st = _au_dessus(mm, ml, bande, confirmation)
    ct = _au_dessus(p, mm, bande, confirmation)
    r = pd.Series(np.nan, index=p.index, dtype=object)
    r[(dr == 1) & (st == 1) & (ct == 1)] = "Strong Bull"
    r[(dr == 1) & (st == 1) & (ct == 0)] = "Correction"
    r[(dr == 1) & (st == 0)] = "Transition haussière"
    r[(dr == 0) & (st == 1)] = "Transition baissière"
    r[(dr == 0) & (st == 0) & (ct == 1)] = "Rebond"
    r[(dr == 0) & (st == 0) & (ct == 0)] = "Strong Bear"
    df = pd.DataFrame({"prix": p, "mm_moyen": mm, "mm_long": ml, "regime": r})
    df = df.loc[_date(debut):_date(fin)]
    df.index.name = "date"
    rr = df["regime"].dropna()
    attrs = {"code": c, "regime_actuel": None, "depuis": pd.NaT, "seances_depuis": 0}
    if len(rr):
        seg = (rr != rr.shift()).cumsum()
        courant = rr[seg == seg.iloc[-1]]
        attrs.update({"regime_actuel": rr.iloc[-1], "depuis": courant.index[0], "seances_depuis": len(courant)})
    df.attrs = attrs
    return df


def participation(n: int = 200, debut=None, fin=None) -> pd.Series:
    """Part des actions (en %, de 0 à 100) dont le dernier cours dépasse leur moyenne mobile ``n``
    séances, parmi celles cotées depuis au moins ``n`` séances, à chaque séance du BRVM Composite.

    Lecture de l'application : participation faible à 40 % ou moins, large à 60 % ou plus.
    """
    s = d.seances()
    cf = pd.DataFrame({t: _sur_seances(_cloture(t), s) for t in d.tickers()}, index=s)
    cote = cf.notna().rolling(n).sum() >= n
    mm = cf.rolling(n, min_periods=int(n * 0.9)).mean()
    out = ((cf > mm) & cote).sum(axis=1) / cote.sum(axis=1).replace(0, np.nan) * 100
    out = out.loc[_date(debut):_date(fin)]
    out.name = "participation"
    out.index.name = "date"
    out.attrs = {"n": n}
    return out


def libelle_fear_greed(score: float) -> str:
    """« Peur extrême » (0 à 25), « Peur » (26 à 44), « Neutre » (45 à 55), « Cupidité » (56 à 75),
    « Cupidité extrême » (76 à 100), sur le score arrondi à l'entier."""
    if score is None or not np.isfinite(score):
        return ""
    s = int(round(score))
    return next((lib for haut, lib in FG_ECHELLE if s <= haut), FG_ECHELLE[-1][1])


def _rang_glissant(s: pd.Series, fenetre: int = FG_FENETRE, min_obs: int = FG_MIN_OBS) -> pd.Series:
    return s.rolling(fenetre, min_periods=min_obs).apply(lambda x: (x <= x[-1]).mean() * 100, raw=True)


def _fg_brut(cours: pd.DataFrame, valeurs: pd.DataFrame, indice_t: pd.Series) -> pd.DataFrame:
    cf = cours.ffill()
    echange = cours.notna()
    rend = cf.pct_change(fill_method=None)
    actifs = cf.notna() & (cf.notna().rolling(60).sum() >= 60)
    n_actifs = actifs.sum(axis=1).replace(0, np.nan)
    out = pd.DataFrame(index=cours.index)
    out["momentum"] = indice_t / indice_t.rolling(FG_MM_MOMENTUM).mean() - 1
    mm = cf.rolling(FG_MM_PARTICIPATION, min_periods=int(FG_MM_PARTICIPATION * 0.8)).mean()
    out["participation"] = ((cf > mm) & actifs).sum(axis=1) / n_actifs
    hauts = cf >= cf.rolling(FG_JOURS_52_SEMAINES, min_periods=200).max()
    bas = cf <= cf.rolling(FG_JOURS_52_SEMAINES, min_periods=200).min()
    net = ((hauts.astype(int) - bas.astype(int)) * actifs).sum(axis=1) / n_actifs
    out["force"] = net.rolling(FG_LISSAGE_FORCE).mean()
    v = valeurs.reindex(columns=cours.columns).fillna(0.0)
    hausse = (v * ((rend > 0) & echange)).sum(axis=1).rolling(FG_FENETRE_DEMANDE).sum()
    baisse = (v * ((rend < 0) & echange)).sum(axis=1).rolling(FG_FENETRE_DEMANDE).sum()
    out["demande"] = hausse / (hausse + baisse).replace(0, np.nan)
    neg = indice_t.pct_change().clip(upper=0)
    semi_court = np.sqrt((neg ** 2).rolling(FG_VOL_COURT).mean())
    semi_long = np.sqrt((neg ** 2).rolling(FG_VOL_LONG).mean())
    out["vol_baissiere"] = -(semi_court / semi_long.replace(0, np.nan))
    return out


def fear_greed(lisse: bool = True, debut=None, fin=None) -> pd.DataFrame:
    """Fear & Greed BRVM : humeur du marché de 0 (peur extrême) à 100 (cupidité extrême), à chaque séance
    du BRVM Composite, selon la version révisée de l'étude de l'application.

    Cinq composantes, chacune ramenée à son rang percentile (0 à 100) sur les 756 dernières séances (au
    moins 250) : ``momentum`` (BRVM Composite dividendes réinvestis face à sa moyenne 125 séances),
    ``participation`` (titres au-dessus de leur moyenne 50 séances), ``force`` (nouveaux plus hauts moins
    nouveaux plus bas sur 52 semaines), ``demande`` (part de la valeur échangée qui va aux titres en
    hausse, 20 séances) et ``vol_baissiere`` (volatilité des seules baisses de l'indice, 20 séances
    rapportées à 120, échelle inversée). Trois piliers à poids égaux : ``pilier_tendance``,
    ``pilier_participation``, ``pilier_flux_stress``. ``score`` : moyenne des piliers, lissée sur 10
    séances si ``lisse`` ; ``libelle`` : sa zone. Les composantes restent non lissées.

    Calculé sur tout l'historique puis coupé à la fenêtre : le rang d'une séance ne dépend que des
    séances passées.
    """
    s = d.seances()
    codes = d.tickers()
    cours = pd.DataFrame({t: _cloture(t) for t in codes}).reindex(s)
    valeurs = pd.DataFrame({t: d.cours(t)["volume_fcfa"] for t in codes}).reindex(s).fillna(0.0)
    indice_t = _indice_dividendes_reinvestis("BRVMC", "particulier").reindex(s)
    rangs = pd.DataFrame({k: _rang_glissant(v) for k, v in _fg_brut(cours, valeurs, indice_t).items()})
    piliers = pd.DataFrame({f"pilier_{k}": rangs[comp].mean(axis=1) for k, comp in FG_PILIERS.items()})
    brut = piliers.mean(axis=1).where(piliers.notna().any(axis=1))
    score = brut.rolling(FG_LISSAGE, min_periods=1).mean().where(brut.notna()) if lisse else brut
    out = pd.concat([score.rename("score"), piliers, rangs], axis=1)
    out.insert(1, "libelle", out["score"].map(libelle_fear_greed))
    out = out.loc[_date(debut):_date(fin)].dropna(subset=["score"])
    out.index.name = "date"
    out.attrs = {"lisse": lisse, "fenetre": FG_FENETRE}
    return out
