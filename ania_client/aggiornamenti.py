"""Controllo delle nuove versioni sulle release pubbliche di GitHub."""
import time

import requests

from . import __version__
from .config import REPO_GITHUB
from .server_api import versione_tupla

_cache = {"quando": 0.0, "risultato": None}
DURATA_CACHE = 6 * 3600


def controlla(repo=None, versione=None, forza=False):
    """{'disponibile': bool, 'versione': str, 'url': str, 'note': str}. Mai eccezioni: se non riesce, 'disponibile' e' False."""
    repo = REPO_GITHUB if repo is None else repo
    versione = versione or __version__
    nessuno = {"disponibile": False, "versione": versione, "url": "", "note": ""}
    if not repo:
        return nessuno
    if not forza and _cache["risultato"] is not None and time.time() - _cache["quando"] < DURATA_CACHE:
        return _cache["risultato"]
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=8,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        rel = r.json()
        ultima = str(rel.get("tag_name", "")).lstrip("vV")
        risultato = {
            "disponibile": versione_tupla(ultima) > versione_tupla(versione),
            "versione": ultima or versione,
            "url": rel.get("html_url", ""),
            "note": (rel.get("body") or "")[:600],
        }
    except (requests.RequestException, ValueError, AttributeError):
        return nessuno
    _cache.update(quando=time.time(), risultato=risultato)
    return risultato
