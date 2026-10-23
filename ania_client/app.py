"""Interfaccia locale (solo 127.0.0.1) del convertitore: la pagina nel browser parla con questa API,
che inoltra i PDF al servizio di conversione e salva i pacchetti nella cartella scelta."""
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, aggiorna, aggiornamenti, config, registro, server_api

MAX_PDF_MB = 20
STATIC = Path(__file__).parent / "static"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.state.chiudi = None  # funzione che ferma il server (impostata da main.py)
_server = {"quando": 0.0, "dati": None}
_conversioni_in_corso = {"n": 0}
_aggiornamento_in_corso = threading.Lock()


@app.middleware("http")
async def solo_locale(request: Request, call_next):
    """Accetta solo richieste dirette a localhost e, per le modifiche, dalla pagina stessa:
    un altro sito aperto nel browser non puo' usare questa API."""
    host = (request.headers.get("host") or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost"):
        return JSONResponse({"errori": ["Richiesta non consentita"]}, status_code=403)
    origine = request.headers.get("origin")
    if request.method not in ("GET", "HEAD") and origine and urlparse(origine).netloc != request.headers.get("host"):
        return JSONResponse({"errori": ["Richiesta non consentita"]}, status_code=403)
    return await call_next(request)


def _maschera(chiave):
    return chiave[:5] + "…" + chiave[-4:] if len(chiave) > 10 else ("•" * len(chiave))


def _pubbliche(imp):
    return {**imp, "chiave": _maschera(imp["chiave"]), "ha_chiave": bool(imp["chiave"])}


@app.get("/api/stato")
def stato():
    imp = config.carica()
    return {
        "app": "ConvertitoreANIA",
        "versione": __version__,
        "configurata": bool(imp["chiave"]),
        "impostazioni": _pubbliche(imp),
        "formati": config.FORMATI,
    }


@app.get("/api/impostazioni")
def leggi_impostazioni():
    return _pubbliche(config.carica())


@app.post("/api/impostazioni")
def salva_impostazioni(payload: dict):
    attuali = config.carica()
    nuove = {**attuali, **{k: payload[k] for k in ("url", "cartella", "formato") if k in payload}}
    chiave = str(payload.get("chiave") or "").strip()
    if chiave and chiave != _maschera(attuali["chiave"]):
        nuove["chiave"] = chiave
    errori = config.valida(nuove)
    if errori:
        return JSONResponse({"errori": errori}, status_code=400)
    _server.update(quando=0.0, dati=None)
    return _pubbliche(config.salva(nuove))


def _verifica_server(forza=False):
    """Stato del server e della licenza, con una breve cache."""
    if not forza and _server["dati"] and time.time() - _server["quando"] < 300:
        return _server["dati"]
    imp = config.carica()
    esito = {"raggiungibile": False, "errore": None, "client_minimo": "0.0.0", "obbligatorio": False, "licenza": None,
             "client_ultima": None}
    try:
        st = server_api.stato_server(imp)
        esito.update(raggiungibile=True, client_minimo=st.get("client_minimo", "0.0.0"),
                     client_ultima=st.get("client_ultima") if aggiorna.release_valida(st.get("client_ultima")) else None)
        esito["obbligatorio"] = server_api.versione_tupla(__version__) < server_api.versione_tupla(esito["client_minimo"])
        if imp["chiave"]:
            valida, dati = server_api.verifica_licenza(imp)
            esito["licenza"] = None if valida is None else (
                {"valida": True, "cliente": dati.get("cliente"), "postazione": dati.get("postazione"),
                 "scadenza": dati.get("scadenza")}
                if valida else {"valida": False, "errore": (dati.get("errori") or ["Licenza non valida"])[0]})
    except server_api.ErroreServizio as e:
        esito["errore"] = str(e)
    _server.update(quando=time.time(), dati=esito)
    return esito


@app.get("/api/server")
def verifica_server():
    return _verifica_server(forza=True)


def _release_dal_server():
    """L'ultima versione dichiarata dal server, solo se e' piu' nuova di quella installata."""
    r = _verifica_server().get("client_ultima")
    if r and server_api.versione_tupla(r["versione"]) > server_api.versione_tupla(__version__):
        return r
    return None


@app.get("/api/aggiornamenti")
def aggiornamenti_disponibili():
    """Se il server dichiara una versione piu' nuova si puo' installare con un clic ('automatico');
    altrimenti (server vecchio) resta l'avviso con il link alla release GitHub."""
    r = _release_dal_server()
    if r:
        return {"disponibile": True, "versione": r["versione"], "url": r["url"], "note": "",
                "automatico": aggiorna.puo_installare()}
    if _verifica_server().get("client_ultima"):
        return {"disponibile": False, "versione": __version__, "url": "", "note": "", "automatico": False}
    return {**aggiornamenti.controlla(), "automatico": False}


@app.post("/api/aggiorna")
def aggiorna_ora():
    """Scarica l'installer della versione dichiarata dal server, ne verifica l'impronta, lo lancia e chiude il programma."""
    if _conversioni_in_corso["n"]:
        raise HTTPException(409, "Conversione in corso: attendere la fine e riprovare")
    if not aggiorna.puo_installare():
        raise HTTPException(400, "L'aggiornamento automatico funziona solo con il programma installato")
    r = _release_dal_server()
    if not r:
        raise HTTPException(404, "Nessun aggiornamento disponibile")
    if not _aggiornamento_in_corso.acquire(blocking=False):
        raise HTTPException(409, "Aggiornamento gia' in corso")
    try:
        aggiorna.lancia(aggiorna.scarica(r["url"], r["sha256"]))
    except aggiorna.ErroreAggiornamento as e:
        _aggiornamento_in_corso.release()
        raise HTTPException(502, str(e))
    if app.state.chiudi:  # l'installer sostituisce il programma: questo si chiude e l'installer lo riapre
        threading.Timer(1.0, app.state.chiudi).start()
    return {"ok": True, "versione": r["versione"]}


@app.post("/api/converti")
async def converti(file: UploadFile = File(...), autorizzazione: str = Form("")):
    nome = Path(file.filename or "documento.pdf").name
    if not nome.lower().endswith(".pdf"):
        raise HTTPException(400, "Sono accettati solo file PDF")
    contenuto = await file.read()
    if len(contenuto) > MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(413, f"File oltre {MAX_PDF_MB} MB")
    imp = config.carica()

    def chiudi(esito, tipo=None, avvisi=(), errori=(), files=(), extra=None):
        registro.scrivi(nome, esito, tipo, avvisi, errori, files, imp["formato"])
        return {"file": nome, "esito": esito, "tipo": tipo, "avvisi": list(avvisi), "errori": list(errori),
                "files": list(files), **(extra or {})}

    if not imp["chiave"]:
        return chiudi("errore", errori=["Inserire la chiave di licenza nelle impostazioni"])
    stato_srv = _server["dati"] or {}
    if stato_srv.get("obbligatorio"):
        return chiudi("errore", errori=[f"Aggiornamento obbligatorio: serve la versione {stato_srv['client_minimo']} "
                                        f"o successiva (installata: {__version__})"])
    _conversioni_in_corso["n"] += 1
    try:
        r = server_api.converti(contenuto, nome, imp, autorizzazione.strip())
    except server_api.ErroreServizio as e:
        return chiudi("errore", errori=[str(e)])
    except OSError as e:
        return chiudi("errore", errori=[f"Impossibile salvare il file nella cartella scelta: {e.strerror or e}"])
    finally:
        _conversioni_in_corso["n"] -= 1
    return chiudi(r["esito"], r["tipo"], r["avvisi"], r["errori"], r["files"], {"id_documento": r["id_documento"]})


@app.get("/api/registro")
def leggi_registro(limite: int = 200, solo_problemi: bool = False):
    return registro.leggi(limite, solo_problemi)


@app.get("/api/registro.csv")
def registro_csv():
    return Response(registro.csv_text(registro.leggi(100000)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="registro_conversioni.csv"'})


@app.post("/api/apri-cartella")
def apri_cartella():
    cartella = Path(config.carica()["cartella"])
    cartella.mkdir(parents=True, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(str(cartella))  # noqa: S606 - apre la cartella scelta dall'utente in Esplora risorse
    return {"cartella": str(cartella)}


@app.post("/api/esci")
def esci():
    if app.state.chiudi:
        app.state.chiudi()
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
