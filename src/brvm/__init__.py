"""brvm : données de marché de la Bourse Régionale des Valeurs Mobilières (UEMOA).

    import brvm
    brvm.cours("SNTS")           # cours de Sonatel, au nominal le plus récent
    brvm.indice("BRVMC")         # BRVM Composite
    brvm.panneau("cloture")      # clôtures de toutes les actions
    brvm.dividendes("ORAC")      # dividendes d'Orange CI, nets d'IRVM
    brvm.societes()              # fiches des sociétés cotées
    brvm.fondamentaux("SNTS")    # comptes par exercice
    brvm.rapports("SNTS")        # rapports publiés sur brvm.org, avec leurs liens
    brvm.chiffres("SNTS")        # chiffres lus dans ces rapports (lignes fiables)
"""

from ._donnees import (
    chiffres,
    configurer,
    cours,
    dividendes,
    fondamentaux,
    indice,
    indices,
    infos,
    panneau,
    rapports,
    resoudre,
    seances,
    societe,
    societes,
    tickers,
    vider_cache,
)

__version__ = "0.1.0"

__all__ = [
    "chiffres", "configurer", "cours", "dividendes", "fondamentaux", "indice", "indices", "infos", "panneau",
    "rapports", "resoudre", "seances", "societe", "societes", "tickers", "vider_cache",
]
