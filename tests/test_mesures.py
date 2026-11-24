"""Tests de brvm.mesures sur l'extrait de tests/donnees (Sonatel, Orange CI, BRVMC depuis 2024).

Les chiffres de référence ont été recoupés avec les fonctions de l'application BRVM Analytics
(quant/performances, beta, regime, fear_greed, comparables, fondamental) sur les données complètes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import brvm

M = brvm.mesures
DONNEES = Path(__file__).parent / "donnees"


@pytest.fixture(autouse=True)
def local():
    brvm.configurer(url=str(DONNEES))
    yield
    brvm.configurer()


# ---------------------------------------------------------------------------
# A. Rendements
# ---------------------------------------------------------------------------

def test_rendement_total():
    rt = M.rendement_total("ORAC")
    assert list(rt.columns) == ["cloture", "valeur", "dividende"]
    assert rt["valeur"].iloc[0] == 100
    assert rt.attrs["dividendes"] == 3 and rt["dividende"].gt(0).sum() == 3
    # dividendes réinvestis : la valeur fait mieux que le cours seul
    assert rt["valeur"].iloc[-1] / 100 > rt["cloture"].iloc[-1] / rt["cloture"].iloc[0]
    assert rt["valeur"].iloc[-1] == pytest.approx(229.981015, rel=1e-6)
    # profil institutionnel : IRVM à 10 % au lieu de 12 %, valeur au moins égale
    inst = M.rendement_total("ORAC", profil="institutionnel")
    assert inst["valeur"].iloc[-1] >= rt["valeur"].iloc[-1]
    # fenêtre : base 100 à sa première séance
    f = M.rendement_total("SNTS", debut="2025-06-01")
    assert f.index[0] >= pd.Timestamp("2025-06-01") and f["valeur"].iloc[0] == 100
    # BRVM Composite dividendes réinvestis (poids de composition()) : au-dessus de l'indice publié
    b = M.rendement_total("BRVMC")
    assert "dividende" not in b.columns
    assert b["valeur"].iloc[-1] > b["cloture"].iloc[-1] / b["cloture"].iloc[0] * 100
    with pytest.raises(ValueError):
        M.rendement_total("SNTS", profil="autre")


def test_performances():
    p = M.performances(["SNTS", "ORAC", "BRVMC"])
    assert list(p.columns) == list(M.PERIODES) and list(p.index) == ["SNTS.sn", "ORAC.ci", "BRVMC"]
    assert p.attrs["fin"] == pd.Timestamp("2026-10-28")
    assert p.attrs["bases"]["AN"] == pd.Timestamp("2025-12-31")      # dernière séance de l'année précédente
    assert p.loc["SNTS.sn", "AN"] == pytest.approx(0.607963, rel=1e-5)
    # même calcul à la main : clôture de fin / clôture de la base
    c = M._prix("SNTS.sn")
    assert p.loc["SNTS.sn", "1A"] == pytest.approx(c.loc["2026-10-28"] / c.loc[p.attrs["bases"]["1A"]] - 1)
    assert p["3A"].isna().all()                                       # extrait trop court
    toutes = M.performances()
    assert list(toutes.index) == brvm.tickers()
    avec = M.performances(dividendes=True)
    assert (avec["AN"] >= toutes["AN"] - 1e-12).all()
    # rythme annuel : inchangé sous un an
    assert M.performances("SNTS", annualise=True).loc["SNTS.sn", "6M"] == p.loc["SNTS.sn", "6M"]
    passe = M.performances("SNTS", fin="2025-06-30")
    assert passe.attrs["fin"] == pd.Timestamp("2025-06-30")


def test_rendements_annuels_et_mensuels():
    a = M.rendements_annuels(depuis=2024)
    assert list(a.columns) == [2024, 2025, 2026]
    assert a.attrs["partielles"]["SNTS.sn"] == [2024]                 # l'extrait commence en 2024
    m = M.rendements_mensuels("SNTS")
    assert list(m.columns) == list(range(1, 13)) and list(m.index) == [2024, 2025, 2026]
    # le produit des mois de 2025 redonne l'année 2025
    assert np.prod(1 + m.loc[2025].dropna()) - 1 == pytest.approx(a.loc["SNTS.sn", 2025])
    s = M.saisonnalite("ORAC")
    assert list(s.columns) == ["moyenne", "mediane", "hausse", "annees"] and len(s) == 12
    assert s["hausse"].between(0, 1).all()


# ---------------------------------------------------------------------------
# B. Risque
# ---------------------------------------------------------------------------

def test_volatilite():
    v = M.volatilite("ORAC")
    assert v["frequence"] == "hebdomadaire" and v["n"] > 100
    assert v["volatilite"] == pytest.approx(0.265670, rel=1e-5)
    j = M.volatilite("ORAC", frequence="J")
    assert j["frequence"] == "quotidienne" and j["n"] > 4 * v["n"]
    g = M.volatilite("SNTS", fenetre=52)
    assert isinstance(g, pd.Series) and g.attrs["fenetre"] == 52 and (g > 0).all()
    with pytest.raises(ValueError):
        M.volatilite("SNTS", frequence="M")


def test_perte_maximale():
    p = M.perte_maximale("ORAC")
    assert p["perte_max"] == pytest.approx(-0.277778, rel=1e-5)
    assert p["date_sommet"] < p["date_creux"] < p["date_reprise"]
    assert p["seances_baisse"] > 0 and p["seances_reprise"] > 0
    c = M._prix("ORAC.ci")
    assert c.loc[p["date_creux"]] / c.loc[p["date_sommet"]] - 1 == pytest.approx(p["perte_max"])
    assert -1 < p["perte_courante"] <= 0


def test_var():
    v = M.var("SNTS")
    assert v["var"] == pytest.approx(-0.030660, rel=1e-4)
    assert v["cvar"] <= v["var"] < 0 and v["niveau"] == 0.95
    assert M.var("SNTS", niveau=0.99)["var"] <= v["var"]
    with pytest.raises(ValueError):
        M.var("SNTS", niveau=95)


def test_beta():
    b = M.beta("SNTS")
    assert b["beta"] == pytest.approx(1.106898, rel=1e-5)
    assert b["ic_bas"] < b["beta"] < b["ic_haut"] and b["lecture"] == "Offensif"
    assert b["r2"] == pytest.approx(b["correlation"] ** 2)
    assert b["reference"] == "BRVMC" and b["n"] >= 26
    # face à lui-même : bêta de 1
    assert M.beta("BRVMC")["beta"] == pytest.approx(1)
    # trop peu d'observations communes : rien n'est publié
    court = M.beta("SNTS", debut="2026-09-01")
    assert np.isnan(court["beta"]) and court["n"] < 26
    g = M.beta("ORAC", fenetre=365)
    assert isinstance(g, pd.Series) and g.index.min() >= pd.Timestamp("2024-12-31")


# ---------------------------------------------------------------------------
# C. Valorisation datée et ratios
# ---------------------------------------------------------------------------

def test_valorisation_datee():
    v = M.valorisation()
    assert list(v.index) == ["ORAC.ci", "SNTS.sn"] and v.attrs["date"] == pd.Timestamp("2026-10-28")
    s = v.loc["SNTS.sn"]
    assert s["capitalisation_mfcfa"] == pytest.approx(s["cours"] * 1e9 / 1e6)
    assert s["per"] == pytest.approx(s["capitalisation_mfcfa"] / s["resultat_net_mfcfa"])
    # Au 1er mars 2025, l'exercice 2024 n'est pas encore publié : PER sur 2023 (publié le 22/02/2024)
    m25 = M.valorisation("SNTS", date="2025-03-01").loc["SNTS.sn"]
    assert m25["exercice"] == 2023 and m25["date_connue"] == pd.Timestamp("2024-02-22")
    assert m25["per"] == pytest.approx(7.764930, rel=1e-5)
    assert m25["date_dividende"] <= pd.Timestamp("2025-03-01")
    assert m25["rendement"] == pytest.approx(m25["dividende_net_fcfa"] / m25["cours"])
    # Mi-janvier 2024 : sans rapport annuel 2023, l'exercice 2022 (connu au 1er juillet 2023 au plus tard)
    j24 = M.valorisation("SNTS", date="2024-01-15").loc["SNTS.sn"]
    assert j24["exercice"] == 2022 and j24["date_connue"] <= pd.Timestamp("2024-01-15")
    with pytest.raises(ValueError):
        M.valorisation("BRVMC")


def test_ratios():
    r = M.ratios("SNTS")
    assert r.index.name == "exercice" and r.index.is_monotonic_increasing and not r.attrs["financier"]
    r23 = r.loc[2023]
    assert r23["source_rn"] == "Sikafinance"
    assert r23["marge_nette"] == pytest.approx(r23["resultat_net"] / r23["ca"])
    assert r23["croissance_ca"] == pytest.approx(r.loc[2023, "ca"] / r.loc[2022, "ca"] - 1)
    assert r23["bnpa_fcfa"] == pytest.approx(r23["resultat_net"] * 1e6 / 1e9)
    assert r23["taux_distribution"] == pytest.approx(r23["dividende_action"] / r23["bnpa_fcfa"])
    assert {"marge_ebe", "endettement", "conversion"} <= set(r.columns)
    assert "coef_exploitation" not in r.columns
    # bornes : aucun ratio aberrant n'est publié
    for nom, (bas, haut) in M.BORNES_RATIOS.items():
        if nom in r:
            assert r[nom].dropna().between(bas, haut).all()


# ---------------------------------------------------------------------------
# D. Marché
# ---------------------------------------------------------------------------

def test_regime():
    g = M.regime()
    assert list(g.columns) == ["prix", "mm_moyen", "mm_long", "regime"]
    assert set(g["regime"].dropna()) <= set(M.REGIMES)
    assert g["regime"].iloc[:199].isna().all() and g["regime"].iloc[200:].notna().all()
    assert g.attrs["regime_actuel"] == "Correction" and g.attrs["depuis"] == pd.Timestamp("2026-10-21")
    # la fenêtre coupe un calcul fait sur tout l'historique
    f = M.regime(debut="2026-01-01")
    assert f["regime"].equals(g.loc["2026-01-01":, "regime"])
    # bande nulle et confirmation d'une séance : comparaisons brutes
    brut = M.regime(bande=0, confirmation=1).dropna()
    haussier = brut["prix"] > brut["mm_long"]
    assert brut.loc[haussier, "regime"].isin(["Strong Bull", "Correction", "Transition haussière"]).all()


def test_participation():
    p = M.participation()
    assert p.dropna().between(0, 100).all()
    assert p.iloc[:199].isna().all()
    assert M.participation(n=50).dropna().index[0] < p.dropna().index[0]


def test_fear_greed():
    f = M.fear_greed()
    assert list(f.columns[:5]) == ["score", "libelle", "pilier_tendance", "pilier_participation", "pilier_flux_stress"]
    assert f["score"].between(0, 100).all() and f.index.min() >= pd.Timestamp("2024-12-01")   # 250 séances
    assert f["score"].iloc[-1] == pytest.approx(38.774370, rel=1e-5)
    assert f["libelle"].iloc[-1] == "Peur"
    brut = M.fear_greed(lisse=False)
    piliers = brut[["pilier_tendance", "pilier_participation", "pilier_flux_stress"]]
    assert brut["score"].equals(piliers.mean(axis=1).rename("score"))
    assert f["score"].std() < brut["score"].std()                     # le lissage réduit le bruit
    assert [M.libelle_fear_greed(x) for x in (10, 30, 50, 60, 90)] == \
        ["Peur extrême", "Peur", "Neutre", "Cupidité", "Cupidité extrême"]
