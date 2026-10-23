"""Aggiornamento del programma: scarica l'installer dalla release GitHub, controlla l'impronta SHA-256 dichiarata
dal server di conversione e lo lancia. GitHub e' solo il deposito del file: di cosa installare decide il server."""
import hashlib
import re
import subprocess
import sys
from urllib.parse import urlparse

import requests

from .config import cartella_dati

HOST_AMMESSI = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
MAX_BYTE = 200 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ErroreAggiornamento(Exception):
    """Il messaggio e' pronto per l'utente."""


def _host_ammesso(url):
    p = urlparse(str(url))
    return p.scheme == "https" and (p.hostname or "").lower() in HOST_AMMESSI


def release_valida(r):
    """True se la release dichiarata dal server ha il formato atteso e punta a GitHub."""
    return (isinstance(r, dict) and bool(re.match(r"^\d+(\.\d+){1,3}$", str(r.get("versione", ""))))
            and bool(_SHA256.match(str(r.get("sha256", "")).lower())) and _host_ammesso(r.get("url")))


def puo_installare():
    """L'installazione automatica ha senso solo nel programma installato (.exe) su Windows."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def scarica(url, sha256, cartella=None):
    """Scarica l'installer e ne verifica l'impronta; se non coincide il file viene cancellato. Ritorna il percorso."""
    if not _host_ammesso(url):
        raise ErroreAggiornamento("Indirizzo di download non consentito")
    cartella = cartella or cartella_dati() / "aggiornamenti"
    cartella.mkdir(parents=True, exist_ok=True)
    for vecchio in cartella.glob("*"):
        try:
            vecchio.unlink()
        except OSError:
            pass
    dest = cartella / "ConvertitoreANIA-Setup.exe"
    h = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=True) as r:
            r.raise_for_status()
            if not all(_host_ammesso(x.url) for x in [*r.history, r]):
                raise ErroreAggiornamento("Indirizzo di download non consentito")
            totale = 0
            with open(dest, "wb") as f:
                for blocco in r.iter_content(256 * 1024):
                    totale += len(blocco)
                    if totale > MAX_BYTE:
                        raise ErroreAggiornamento("File di aggiornamento troppo grande")
                    h.update(blocco)
                    f.write(blocco)
    except requests.RequestException as e:
        dest.unlink(missing_ok=True)
        raise ErroreAggiornamento(f"Download non riuscito: {e}")
    except ErroreAggiornamento:
        dest.unlink(missing_ok=True)
        raise
    if h.hexdigest() != str(sha256).lower():
        dest.unlink(missing_ok=True)
        raise ErroreAggiornamento("Il file scaricato non corrisponde a quello atteso: aggiornamento annullato")
    return dest


def lancia(installer):
    """Avvia l'installer in silenzio, staccato da questo programma (che si chiude subito dopo)."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                         creationflags=flags, close_fds=True)
    except OSError as e:
        raise ErroreAggiornamento(f"Impossibile avviare l'installazione: {e.strerror or e}")
