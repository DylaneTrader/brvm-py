"""Téléchargement des fichiers de données et cache local.

Les données sont lues sur la branche ``donnees`` du dépôt DylaneTrader/brvm-py, ou dans un dossier
local. Chaque fichier téléchargé est gardé sur le disque ; il est relu sur le réseau quand il a plus
de ``ttl`` secondes. Sans réseau, la copie en cache est rendue avec un avertissement.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Optional

URL_DEFAUT = "https://raw.githubusercontent.com/DylaneTrader/brvm-py/donnees/"
TTL_DEFAUT = 3600.0
DELAI_RESEAU = 30


def _cache_defaut() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "brvm-py"


class Source:
    """Où lire les données (URL ou dossier), où les garder, combien de temps."""

    def __init__(self, url: Optional[str] = None, cache: Optional[str | Path] = None,
                 ttl: Optional[float] = None):
        self.configurer(url, cache, ttl)

    def configurer(self, url: Optional[str] = None, cache: Optional[str | Path] = None,
                   ttl: Optional[float] = None) -> None:
        url = url or os.environ.get("BRVM_DONNEES") or URL_DEFAUT
        self.local = None if url.startswith(("http://", "https://")) else Path(url).expanduser()
        self.url = url if url.endswith("/") or self.local is not None else url + "/"
        self.cache = Path(cache or os.environ.get("BRVM_CACHE") or _cache_defaut()).expanduser()
        self.ttl = float(ttl if ttl is not None else os.environ.get("BRVM_TTL", TTL_DEFAUT))

    def _telecharger(self, chemin: str) -> bytes:
        req = urllib.request.Request(self.url + chemin, headers={"User-Agent": "brvm-py"})
        with urllib.request.urlopen(req, timeout=DELAI_RESEAU) as rep:
            return rep.read()

    def lire(self, chemin: str) -> bytes:
        """Contenu d'un fichier de données (``meta.json``, ``actions/SNTS.sn.csv``…)."""
        if self.local is not None:
            return (self.local / chemin).read_bytes()
        copie = self.cache / chemin
        if copie.exists() and time.time() - copie.stat().st_mtime < self.ttl:
            return copie.read_bytes()
        try:
            contenu = self._telecharger(chemin)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if copie.exists():
                warnings.warn(f"brvm : {chemin} non téléchargé ({exc}), copie en cache utilisée", stacklevel=3)
                return copie.read_bytes()
            raise ConnectionError(f"brvm : impossible de télécharger {self.url + chemin} ({exc})") from exc
        copie.parent.mkdir(parents=True, exist_ok=True)
        temp = copie.with_suffix(copie.suffix + ".tmp")
        temp.write_bytes(contenu)
        temp.replace(copie)
        return contenu

    def cle(self, chemin: str) -> float:
        """Change quand le fichier doit être relu (invalide le cache mémoire)."""
        if self.local is not None:
            try:
                return (self.local / chemin).stat().st_mtime
            except OSError:
                return 0.0
        return time.time() // self.ttl if self.ttl > 0 else time.time()

    def vider(self) -> None:
        """Supprime les fichiers en cache sur le disque."""
        if self.local is None and self.cache.exists():
            for p in sorted(self.cache.rglob("*"), reverse=True):
                p.unlink() if p.is_file() else p.rmdir()
