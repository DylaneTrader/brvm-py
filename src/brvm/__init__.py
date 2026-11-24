"""brvm : données de marché de la Bourse Régionale des Valeurs Mobilières (UEMOA).

    import brvm
    brvm.cours("SNTS")           # cours de Sonatel, au nominal le plus récent
    brvm.indice("BRVMC")         # BRVM Composite
    brvm.panneau("cloture")      # clôtures de toutes les actions
    brvm.dividendes("ORAC")      # dividendes d'Orange CI, nets d'IRVM
    brvm.societes()              # fiches des sociétés cotées
    brvm.fondamentaux("SNTS")    # comptes par exercice
    brvm.composition("BRVMC")    # poids des titres dans un indice, à chaque séance
    brvm.rapports("SNTS")        # rapports publiés sur brvm.org, avec leurs liens
    brvm.chiffres("SNTS")        # chiffres lus dans ces rapports (lignes fiables)
    brvm.mesures.beta("SNTS")    # mesures de marché : rendements, risque, valorisation, régime
"""

from ._donnees import (
    chiffres,
    composition,
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
from . import mesures

__version__ = "0.1.0"

__all__ = [
    "chiffres", "composition", "configurer", "cours", "dividendes", "fondamentaux", "indice", "indices", "infos", "panneau",
    "mesures", "rapports", "resoudre", "seances", "societe", "societes", "tickers", "vider_cache",
]
