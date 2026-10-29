"""Lecture des données de marché de la BRVM : cours, indices, dividendes, sociétés, fondamentaux."""

from __future__ import annotations

import io
import json
from functools import lru_cache
from typing import Iterable, Optional

import pandas as pd

from ._source import Source

_source = Source()
PROFILS = ("particulier", "institutionnel")
CHAMPS = ("ouverture", "plus_haut", "plus_bas", "cloture", "volume_titres", "volume_fcfa", "variation_pct")


def configurer(url: Optional[str] = None, cache: Optional[str] = None, ttl: Optional[float] = None) -> None:
    """Règle la source des données.

    - ``url`` : adresse des fichiers ou dossier local (par défaut, la branche ``donnees`` du dépôt
      DylaneTrader/brvm-py ; variable d'environnement ``BRVM_DONNEES``) ;
    - ``cache`` : dossier du cache (``BRVM_CACHE`` ; par défaut ``~/.cache/brvm-py``) ;
    - ``ttl`` : durée de validité du cache en secondes (``BRVM_TTL`` ; 3600 par défaut).
    """
    _source.configurer(url, cache, ttl)
    _vider_memoire()


def vider_cache() -> None:
    """Oublie toutes les données lues (mémoire et disque) : le prochain appel les télécharge."""
    _source.vider()
    _vider_memoire()


def _vider_memoire() -> None:
    for f in (_meta, _csv):
        f.cache_clear()


@lru_cache(maxsize=4)
def _meta(_cle: float) -> dict:
    return json.loads(_source.lire("meta.json").decode("utf-8"))


def infos() -> dict:
    """Description de l'export : dernière séance, séance close ou non, heure du relevé, titres,
    indices, divisions du nominal appliquées, taux d'IRVM, sources."""
    return _meta(_source.cle("meta.json"))


@lru_cache(maxsize=256)
def _csv(chemin: str, _cle: float) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(_source.lire(chemin)), encoding="utf-8")


def _table(chemin: str) -> pd.DataFrame:
    return _csv(chemin, _source.cle(chemin)).copy()


# ---------------------------------------------------------------------------
# Titres et indices
# ---------------------------------------------------------------------------

def tickers() -> list[str]:
    """Codes des actions cotées, au format ``SNTS.sn`` (code et pays)."""
    return sorted(infos()["actions"])


def indices() -> pd.DataFrame:
    """Indices publiés : code, nom, ISIN, première et dernière séance."""
    df = pd.DataFrame.from_dict(infos()["indices"], orient="index")
    df.index.name = "code"
    return df.sort_index()


def resoudre(code: str) -> str:
    """``snts``, ``SNTS`` ou ``SNTS.sn`` -> ``SNTS.sn`` ; ``brvmc`` -> ``BRVMC``.

    Lève ``KeyError`` pour un code inconnu."""
    c = str(code or "").strip().upper()
    for t in tickers():
        if t.upper() == c or t.split(".")[0].upper() == c:
            return t
    for i in infos()["indices"]:
        if i.upper() == c.replace(" ", "_"):
            return i
    raise KeyError(f"brvm : code inconnu : {code!r}")


def _serie(chemin: str, debut, fin) -> pd.DataFrame:
    df = _table(chemin)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df.loc[pd.Timestamp(debut) if debut else None: pd.Timestamp(fin) if fin else None]


def cours(ticker: str, debut=None, fin=None) -> pd.DataFrame:
    """Cours d'une action, une ligne par séance où le titre a échangé (un jour sans échange n'a pas
    de ligne). Colonnes : ``ouverture``, ``plus_haut``, ``plus_bas``, ``cloture`` (FCFA),
    ``volume_titres``, ``volume_fcfa``, ``variation_pct``.

    Cours et volumes au nominal le plus récent : les divisions du nominal sont appliquées à tout
    l'historique (Sonatel divisée par 10 le 26/10/2026, voir ``infos()["operations_titres"]``)."""
    t = resoudre(ticker)
    if t not in infos()["actions"]:
        raise KeyError(f"brvm : {t} est un indice, lire brvm.indice({t!r})")
    return _serie(f"actions/{t}.csv", debut, fin)


def indice(code: str = "BRVMC", debut=None, fin=None) -> pd.DataFrame:
    """Valeurs d'un indice publié (``BRVMC``, ``BRVM30``, ``BRVMPR``…), une ligne par séance."""
    c = resoudre(code)
    if c not in infos()["indices"]:
        raise KeyError(f"brvm : {c} est une action, lire brvm.cours({c!r})")
    return _serie(f"indices/{c}.csv", debut, fin)


def panneau(champ: str = "cloture", titres: Optional[Iterable[str]] = None, debut=None, fin=None) -> pd.DataFrame:
    """Une colonne par action, une ligne par séance où au moins un titre a échangé ; NaN les jours où
    le titre n'a pas échangé. ``champ`` : une colonne de ``cours()``."""
    if champ not in CHAMPS:
        raise ValueError(f"brvm : champ inconnu {champ!r}, choisir parmi {CHAMPS}")
    liste = [resoudre(t) for t in titres] if titres is not None else tickers()
    return pd.DataFrame({t: cours(t, debut, fin)[champ] for t in liste}).sort_index()


def seances(debut=None, fin=None) -> pd.DatetimeIndex:
    """Calendrier des séances : les dates de l'indice BRVM Composite."""
    return indice("BRVMC", debut, fin).index


# ---------------------------------------------------------------------------
# Dividendes
# ---------------------------------------------------------------------------

def dividendes(ticker: Optional[str] = None, profil: str = "particulier", retenus: bool = False) -> pd.DataFrame:
    """Dividendes passés et à venir, montants par action en FCFA.

    - Montants au nominal des cours de ``cours()`` : un dividende publié avant une division du
      nominal est divisé par son rapport (``montant_publie_fcfa`` garde le montant publié,
      ``rapport_division`` le rapport).
    - ``montant_net_fcfa`` : net d'IRVM pour le ``profil`` choisi (``particulier`` : 12 %,
      ``institutionnel`` : 10 %) quand la BRVM publie le brut (titres ivoiriens depuis l'exercice
      2024) ; sinon, montant publié net, le même pour tous.
    - ``retenu`` : le montant est cohérent avec les cours (au plus 15 % du cours de la veille, ou
      baisse du cours d'au moins 60 % du montant le jour du détachement, ou correction vérifiée).
      ``retenus=True`` ne garde que ceux-là : ceux à créditer dans un rendement total.
    - ``statut`` : « A venir » jusqu'au jour du détachement compris, « Passé » ensuite,
      « A préciser » sans date.
    """
    if profil not in PROFILS:
        raise ValueError(f"brvm : profil inconnu {profil!r}, choisir parmi {PROFILS}")
    df = _table("dividendes.csv")
    for col in ("date_detachement", "date_paiement", "date_baisse"):
        df[col] = pd.to_datetime(df[col])
    df["exercice"] = df["exercice"].astype("Int64")
    df["montant_net_fcfa"] = df[f"montant_net_{profil}_fcfa"]
    jour = pd.Timestamp.today().normalize()
    d = df["date_detachement"]
    df["statut"] = "A venir"
    df.loc[d < jour, "statut"] = "Passé"
    df.loc[d.isna(), "statut"] = "A préciser"
    if ticker is not None:
        df = df[df["ticker"] == resoudre(ticker)]
    if retenus:
        df = df[df["retenu"]]
    colonnes = ["ticker", "nom", "exercice", "statut", "date_detachement", "detachement_estime", "date_paiement",
                "montant_net_fcfa", "montant_brut_fcfa", "nature_montant", "montant_publie_fcfa", "rapport_division",
                "montant_net_particulier_fcfa", "montant_net_institutionnel_fcfa", "part_du_cours",
                "baisse_du_jour", "date_baisse", "retenu", "avis_url", "sources"]
    return df[colonnes].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Sociétés
# ---------------------------------------------------------------------------

def societes() -> pd.DataFrame:
    """Une ligne par société : nom, ISIN, pays, secteur, nombre de titres (au nominal des cours),
    flottant en %, dernier cours, capitalisation en FCFA, description, adresse, dirigeants."""
    return _table("societes.csv").set_index("ticker")


def societe(ticker: str) -> dict:
    """Fiche d'une société, en dictionnaire."""
    t = resoudre(ticker)
    s = societes()
    if t not in s.index:
        raise KeyError(f"brvm : pas de fiche pour {t}")
    return {"ticker": t, **{k: (None if pd.isna(v) else v) for k, v in s.loc[t].items()}}


def fondamentaux(ticker: Optional[str] = None) -> pd.DataFrame:
    """Indicateurs par exercice : chiffre d'affaires et résultat net (millions de FCFA), croissances
    (%), bénéfice et dividende par action (FCFA). Le PER publié par la source n'est pas fourni :
    calculé au cours du jour de la collecte, il n'est pas daté ; le recalculer avec ``cours()``."""
    df = _table("fondamentaux.csv")
    df["exercice"] = df["exercice"].astype(int)
    if ticker is not None:
        df = df[df["ticker"] == resoudre(ticker)]
    return df.reset_index(drop=True)
