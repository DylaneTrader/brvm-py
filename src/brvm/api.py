"""Génère l'API statique : un fichier JSON par ressource, publiable sur GitHub Pages.

    python -m brvm.api --donnees chemin/vers/donnees --sortie site

Les fichiers sont produits avec les mêmes fonctions que le paquet (divisions du nominal appliquées,
dividendes contrôlés). Aucun serveur : les clients font des requêtes GET sur des adresses fixes.

Format des tables : ``{"colonnes": [...], "lignes": [[...], ...]}``, dates ISO (``2026-10-28``),
valeurs manquantes à ``null``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from . import _donnees as d

VERSION_API = "v1"


def _json(chemin: Path, contenu: Any) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(contenu, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    chemin.write_text(texte, encoding="utf-8")


def _table(df: pd.DataFrame, **entete: Any) -> dict:
    """DataFrame -> ``{"colonnes", "lignes"}`` (dates en texte ISO, manquants à ``None``)."""
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    df = df.astype(object).where(df.notna(), None)
    return {**entete, "colonnes": [str(c) for c in df.columns], "lignes": df.values.tolist()}


def _par_titre(df: pd.DataFrame, colonne: str = "ticker") -> dict:
    return {t: g.reset_index(drop=True) for t, g in df.groupby(colonne, sort=True)}


def generer(sortie: str | Path, donnees: Optional[str] = None) -> list[Path]:
    """Écrit l'API dans le dossier ``sortie`` et rend la liste des fichiers créés.

    ``donnees`` : dossier ou adresse des fichiers sources (par défaut, la configuration du paquet)."""
    if donnees is not None:
        d.configurer(url=donnees)
    racine = Path(sortie)
    v1 = racine / VERSION_API
    ecrits: list[Path] = []

    def ecrire(chemin: Path, contenu: Any) -> None:
        _json(chemin, contenu)
        ecrits.append(chemin)

    infos = d.infos()
    tickers = d.tickers()
    codes_indices = list(d.indices().index)
    genere_le = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ecrire(v1 / "infos.json", {**infos, "genere_le": genere_le})
    ecrire(v1 / "tickers.json", tickers)
    ecrire(v1 / "seances.json", [x.strftime("%Y-%m-%d") for x in d.seances()])
    ecrire(v1 / "indices.json", _table(d.indices().reset_index()))

    for t in tickers:
        ecrire(v1 / "cours" / f"{t}.json", _table(d.cours(t).reset_index(), ticker=t))
    for c in codes_indices:
        ecrire(v1 / "indices" / f"{c}.json", _table(d.indice(c).reset_index(), code=c))

    # Montants nets des deux profils présents dans chaque ligne : pas de paramètre côté serveur.
    div = d.dividendes().drop(columns="montant_net_fcfa")
    ecrire(v1 / "dividendes.json", _table(div))
    for t, g in _par_titre(div).items():
        ecrire(v1 / "dividendes" / f"{t}.json", _table(g, ticker=t))

    soc = d.societes().reset_index()
    ecrire(v1 / "societes.json", _table(soc))
    for t, g in _par_titre(soc).items():
        t_table = _table(g)
        ecrire(v1 / "societes" / f"{t}.json", dict(zip(t_table["colonnes"], t_table["lignes"][0])))

    fond = d.fondamentaux()
    ecrire(v1 / "fondamentaux.json", _table(fond))
    for t, g in _par_titre(fond).items():
        ecrire(v1 / "fondamentaux" / f"{t}.json", _table(g, ticker=t))

    points = {
        "infos": f"{VERSION_API}/infos.json",
        "tickers": f"{VERSION_API}/tickers.json",
        "seances": f"{VERSION_API}/seances.json",
        "indices": f"{VERSION_API}/indices.json",
        "cours": f"{VERSION_API}/cours/{{ticker}}.json",
        "indice": f"{VERSION_API}/indices/{{code}}.json",
        "dividendes": f"{VERSION_API}/dividendes.json",
        "dividendes_titre": f"{VERSION_API}/dividendes/{{ticker}}.json",
        "societes": f"{VERSION_API}/societes.json",
        "societe": f"{VERSION_API}/societes/{{ticker}}.json",
        "fondamentaux": f"{VERSION_API}/fondamentaux.json",
        "fondamentaux_titre": f"{VERSION_API}/fondamentaux/{{ticker}}.json",
    }
    ecrire(racine / "index.json", {
        "version": VERSION_API,
        "genere_le": genere_le,
        "derniere_seance": infos["derniere_seance"],
        "derniere_seance_close": infos["derniere_seance_close"],
        "points_d_acces": points,
        "tickers": tickers,
        "indices": codes_indices,
    })
    page = racine / "index.html"
    page.write_text(_page(points, tickers, codes_indices, infos["derniere_seance"]), encoding="utf-8")
    ecrits.append(page)
    return ecrits


def _page(points: dict, tickers: list, codes_indices: list, derniere_seance: str) -> str:
    lignes = "\n".join(f"<tr><td>{nom}</td><td><code>{chemin}</code></td></tr>" for nom, chemin in points.items())
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>API BRVM</title>
<style>
body {{ font-family: "Times New Roman", Times, serif; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
table {{ border-collapse: collapse; width: 100%; }}
td {{ border-bottom: 1px solid #ccc; padding: .3rem .5rem; }}
pre {{ background: #f4f4f4; padding: .75rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>API BRVM</h1>
<p>Données de la Bourse Régionale des Valeurs Mobilières (UEMOA) en JSON, mises à jour chaque jour de
séance après la clôture. Dernière séance : <strong>{derniere_seance}</strong>.
Accès libre, sans clé, requêtes GET uniquement.</p>
<h2>Points d'accès</h2>
<table>
{lignes}
</table>
<p>Codes des actions : {", ".join(tickers)}.<br>Indices : {", ".join(codes_indices)}.</p>
<h2>Exemple</h2>
<pre>fetch("{VERSION_API}/cours/SNTS.sn.json")
  .then(r =&gt; r.json())
  .then(t =&gt; console.log(t.colonnes, t.lignes.at(-1)));</pre>
<p>Chaque table a la forme <code>{{"colonnes": [...], "lignes": [[...]]}}</code>, avec des dates ISO et
<code>null</code> pour les valeurs manquantes. Le code et la documentation complète sont sur
<a href="https://github.com/DylaneTrader/brvm-py">GitHub</a>. Données fournies sans garantie, ne constituant
pas un conseil en investissement.</p>
</body>
</html>
"""


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(prog="python -m brvm.api", description=__doc__.split("\n")[0])
    p.add_argument("--donnees", help="dossier ou adresse des fichiers sources (par défaut : branche donnees)")
    p.add_argument("--sortie", required=True, help="dossier où écrire l'API")
    args = p.parse_args(argv)
    fichiers = generer(args.sortie, args.donnees)
    print(f"{len(fichiers)} fichiers écrits dans {args.sortie}")


if __name__ == "__main__":
    main()
