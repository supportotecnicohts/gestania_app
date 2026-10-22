"""Chiamate al servizio di conversione e salvataggio del pacchetto ricevuto."""
import base64
import io
import os
import re
import zipfile
from pathlib import Path

import requests

from . import __version__

TIMEOUT_CONVERSIONE = 130  # il server aspetta natif.ai fino a ~100 s (limite Cloudflare)

MESSAGGI_HTTP = {
    429: "Troppe richieste in poco tempo: riprovare tra qualche secondo",
    502: "Servizio momentaneamente non disponibile: riprovare tra poco",
    503: "Servizio momentaneamente non disponibile: riprovare tra poco",
    504: "Il server ha impiegato troppo tempo a rispondere: riprovare",
    524: "Il server ha impiegato troppo tempo a rispondere: riprovare",
}


class ErroreServizio(Exception):
    """Problema di comunicazione o di salvataggio: il messaggio e' pronto per l'utente."""


def versione_tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:4]) or (0,)


def _intestazioni(imp):
    return {"X-Licenza": imp.get("chiave", ""), "X-Versione-Client": __version__}


def _chiama(metodo, imp, percorso, **kw):
    url = imp["url"].rstrip("/") + percorso
    try:
        r = requests.request(metodo, url, headers=_intestazioni(imp), **kw)
    except requests.exceptions.Timeout:
        raise ErroreServizio("Il server non ha risposto in tempo: riprovare tra poco")
    except requests.exceptions.ConnectionError:
        raise ErroreServizio("Impossibile contattare il server: controllare la connessione a internet")
    except requests.RequestException as e:
        raise ErroreServizio(f"Errore di comunicazione con il server: {e}")
    try:
        dati = r.json()
    except ValueError:
        dati = None
    if not isinstance(dati, dict):
        raise ErroreServizio(MESSAGGI_HTTP.get(r.status_code, f"Risposta non valida dal server (HTTP {r.status_code})"))
    return r.status_code, dati


def stato_server(imp, timeout=10):
    """{'stato', 'versione_api', 'client_minimo'} oppure ErroreServizio."""
    _, dati = _chiama("GET", imp, "/v1/stato", timeout=timeout)
    return dati


def verifica_licenza(imp, timeout=15):
    """Ritorna (valida, dati). `dati` ha cliente/postazione/scadenza, oppure `errori`.
    `valida` e' None se il server e' una versione vecchia che non sa verificare la chiave (404)."""
    codice, dati = _chiama("GET", imp, "/v1/licenza", timeout=timeout)
    if codice == 404:
        return None, dati
    return codice == 200 and bool(dati.get("valida")), dati


def nome_sicuro(nome):
    pulito = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(nome)).strip(" .")
    return pulito or "documento"


def salva_pacchetto(file_base64, nome_file, formato, cartella):
    """Scrive lo zip ricevuto come .ADZ / .zip, oppure lo estrae in TXT separati. Ritorna i percorsi creati."""
    try:
        dati = base64.b64decode(file_base64, validate=True)
        zf = zipfile.ZipFile(io.BytesIO(dati))
    except (ValueError, zipfile.BadZipFile):
        raise ErroreServizio("Il file ricevuto dal server non e' valido: riprovare")
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    stem = nome_sicuro(Path(nome_file).stem)

    def scrivi(dest, contenuto):
        # prima in un file nascosto, poi rinominato: chi guarda la cartella non vede mai file a meta'
        tmp = dest.with_name("." + dest.name + ".tmp")
        tmp.write_bytes(contenuto)
        os.replace(tmp, dest)
        return str(dest)

    if formato in ("adz", "zip"):
        return [scrivi(cartella / f"{stem}.{'ADZ' if formato == 'adz' else 'zip'}", dati)]
    cartella_pratica = cartella / stem
    cartella_pratica.mkdir(parents=True, exist_ok=True)
    with zf:
        return [scrivi(cartella_pratica / nome_sicuro(Path(n).name), zf.read(n))
                for n in zf.namelist() if not n.endswith("/")]


def converti(pdf_bytes, nome_pdf, imp, autorizzazione=""):
    """Invia il PDF e salva il pacchetto. Ritorna sempre un dizionario con esito, avvisi, errori, files."""
    codice, dati = _chiama(
        "POST", imp, "/v1/converti",
        files={"file": (nome_pdf, pdf_bytes, "application/pdf")},
        data={"autorizzazione": autorizzazione or ""},
        timeout=TIMEOUT_CONVERSIONE,
    )
    esito = {
        "esito": dati.get("esito", "errore"),
        "tipo": dati.get("tipo"),
        "id_documento": dati.get("id_documento"),
        "avvisi": list(dati.get("avvisi") or []),
        "errori": list(dati.get("errori") or []),
        "files": [],
    }
    if codice != 200 or esito["esito"] == "errore" or not dati.get("file_base64"):
        esito["esito"] = "errore"
        if not esito["errori"]:
            esito["errori"] = [MESSAGGI_HTTP.get(codice, f"Conversione non riuscita (HTTP {codice})")]
        return esito
    esito["files"] = salva_pacchetto(dati["file_base64"], dati.get("nome_file") or nome_pdf, imp["formato"],
                                     imp["cartella"])
    return esito
