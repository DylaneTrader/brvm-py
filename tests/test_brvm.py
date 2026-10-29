"""Tests sur un extrait des données (tests/donnees : Sonatel, Orange CI, BRVMC depuis 2024)."""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pandas as pd
import pytest

import brvm
from brvm import _donnees
from brvm._source import Source

DONNEES = Path(__file__).parent / "donnees"


@pytest.fixture(autouse=True)
def local():
    brvm.configurer(url=str(DONNEES))
    yield
    brvm.configurer()


def test_codes():
    assert brvm.tickers() == ["ORAC.ci", "SNTS.sn"]
    assert brvm.resoudre("snts") == brvm.resoudre("SNTS.sn") == "SNTS.sn"
    assert brvm.resoudre("brvmc") == "BRVMC"
    with pytest.raises(KeyError):
        brvm.resoudre("XXXX")
    assert "BRVMC" in brvm.indices().index


def test_cours_au_nominal_le_plus_recent():
    c = brvm.cours("SNTS")
    assert list(c.columns) == list(_donnees.CHAMPS)
    assert isinstance(c.index, pd.DatetimeIndex) and c.index.is_monotonic_increasing
    # Sonatel divisée par 10 le 26/10/2026 : pas de chute de 90 % dans l'historique ajusté
    assert c["cloture"].pct_change().min() > -0.5
    assert c.loc["2026-10-23", "cloture"] < 10_000
    assert len(brvm.cours("SNTS", debut="2026-01-01", fin="2026-03-31")) > 0
    with pytest.raises(KeyError):
        brvm.cours("BRVMC")


def test_indice_et_panneau():
    i = brvm.indice()
    assert "volume_fcfa" not in i.columns and i["cloture"].notna().all()
    assert brvm.seances().equals(i.index)
    p = brvm.panneau("cloture")
    assert list(p.columns) == ["ORAC.ci", "SNTS.sn"]
    with pytest.raises(ValueError):
        brvm.panneau("prix")


def test_dividendes():
    d = brvm.dividendes()
    assert {"STBC.ci", "SNTS.sn", "ORAC.ci"} <= set(d["ticker"])
    # SITAB 2016 : publié avant le fractionnement par 20 de 2018, ramené au nominal des cours
    stbc = d[(d["ticker"] == "STBC.ci") & (d["exercice"] == 2015)].iloc[0]
    assert stbc["montant_net_fcfa"] == pytest.approx(stbc["montant_publie_fcfa"] / 20)
    # Orange CI, exercice 2024 : 750 FCFA brut, 660 net (particulier), 675 net (institutionnel)
    orac = brvm.dividendes("ORAC")
    o24 = orac[orac["exercice"] == 2024].iloc[0]
    assert (o24["montant_brut_fcfa"], o24["montant_net_fcfa"]) == (750, 660)
    inst = brvm.dividendes("ORAC", profil="institutionnel")
    assert inst[inst["exercice"] == 2024].iloc[0]["montant_net_fcfa"] == 675
    assert brvm.dividendes(retenus=True)["retenu"].all()
    assert set(d["statut"]) <= {"Passé", "A venir", "A préciser"}
    with pytest.raises(ValueError):
        brvm.dividendes(profil="autre")


def test_societes_et_fondamentaux():
    s = brvm.societe("SNTS")
    assert s["nom"] == "SONATEL" and s["pays"] == "Sénégal"
    assert s["nombre_titres"] == 1_000_000_000
    assert s["capitalisation_fcfa"] == pytest.approx(s["dernier_cours"] * s["nombre_titres"])
    f = brvm.fondamentaux("SNTS")
    assert "per_publie" not in f.columns and f["exercice"].is_monotonic_increasing


def test_infos():
    m = brvm.infos()
    assert m["version_format"] == 1
    assert m["operations_titres"][0]["ticker"] == "SNTS.sn"


# ---------------------------------------------------------------------------
# Téléchargement et cache
# ---------------------------------------------------------------------------

def test_cache_puis_copie_hors_ligne(tmp_path, monkeypatch):
    src = Source(url="https://exemple.invalid/donnees", cache=tmp_path, ttl=3600)
    appels = []

    def telecharger(chemin):
        appels.append(chemin)
        return (DONNEES / chemin).read_bytes()

    monkeypatch.setattr(src, "_telecharger", telecharger)
    assert src.lire("meta.json") == src.lire("meta.json")
    assert appels == ["meta.json"]                      # deuxième lecture : cache disque

    src.ttl = 0                                         # cache périmé, réseau coupé : copie rendue
    def coupe(chemin):
        raise urllib.error.URLError("hors ligne")
    monkeypatch.setattr(src, "_telecharger", coupe)
    with pytest.warns(UserWarning, match="copie en cache"):
        assert src.lire("meta.json") == (DONNEES / "meta.json").read_bytes()
    with pytest.raises(ConnectionError):
        src.lire("societes.csv")                        # jamais téléchargé
    src.vider()
    assert not any(tmp_path.iterdir())
