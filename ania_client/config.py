"""Impostazioni del programma cliente, salvate per utente in %APPDATA%\\ConvertitoreANIA."""
import json
import os
from pathlib import Path

NOME_APP = "ConvertitoreANIA"
URL_PREDEFINITO = "https://api.gestania.it"
# Repository GitHub pubblico delle release ("proprietario/repository"); vuoto = nessun controllo aggiornamenti.
REPO_GITHUB = os.getenv("ANIA_REPO_GITHUB", "")
FORMATI = {
    "adz": "Pacchetto .ADZ",
    "zip": "Pacchetto .zip",
    "txt": "File TXT separati (+ PDF)",
}


def cartella_dati():
    """Cartella dei dati dell'utente (impostazioni, registro). `ANIA_CLIENT_DATA` la sposta (test)."""
    base = os.getenv("ANIA_CLIENT_DATA")
    d = Path(base) if base else Path(os.getenv("APPDATA") or Path.home()) / NOME_APP
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file():
    return cartella_dati() / "impostazioni.json"


def predefinite():
    return {
        "url": URL_PREDEFINITO,
        "chiave": "",
        "cartella": str(Path.home() / "Documents" / "ANIA"),
        "formato": "adz",
    }


def carica():
    imp = predefinite()
    try:
        imp.update({k: v for k, v in json.loads(_file().read_text(encoding="utf-8")).items() if k in imp})
    except (OSError, ValueError):
        pass
    return imp


def valida(imp):
    """Dizionario campo -> messaggio per ogni campo non valido (vuoto se tutto ok)."""
    errori = {}
    url = (imp.get("url") or "").strip()
    locale = url.startswith(("http://127.0.0.1", "http://localhost"))
    if not (url.startswith("https://") or locale):
        errori["url"] = "L'indirizzo del server deve iniziare con https://"
    if imp.get("formato") not in FORMATI:
        errori["formato"] = "Formato non valido"
    cartella = (imp.get("cartella") or "").strip()
    if not cartella:
        errori["cartella"] = "Scegliere la cartella di salvataggio"
    else:
        try:
            p = Path(cartella)
            p.mkdir(parents=True, exist_ok=True)
            prova = p / ".scrittura_ok"
            prova.write_text("", encoding="utf-8")
            prova.unlink()
        except OSError as e:
            errori["cartella"] = f"Cartella non scrivibile: {e.strerror or e}"
    return errori


def salva(imp):
    pulite = {k: (str(imp.get(k, v)).strip()) for k, v in predefinite().items()}
    pulite["url"] = pulite["url"].rstrip("/")
    _file().write_text(json.dumps(pulite, indent=2, ensure_ascii=False), encoding="utf-8")
    return pulite
