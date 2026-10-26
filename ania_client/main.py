"""Avvio del programma: server locale su 127.0.0.1 + apertura del browser. Una sola istanza per utente."""
import os
import socket
import sys
import threading
import time
import webbrowser

import requests
import uvicorn

from .app import app
from .config import cartella_dati

PORTE = range(8765, 8776)


def _porta_occupata(porta):
    """True se qualcosa e' in ascolto su quella porta. Si prova a occuparla invece di collegarsi: su Windows
    una connessione a una porta chiusa impiega circa 2 secondi a fallire, un `bind` risponde subito."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", porta))
        except OSError:
            return True
    return False


def _istanza_attiva():
    """Porta su cui gira gia' il programma, se c'e'. Si interrogano solo le porte occupate."""
    for porta in PORTE:
        if not _porta_occupata(porta):
            continue
        try:
            r = requests.get(f"http://127.0.0.1:{porta}/api/stato", timeout=1)
            if r.ok and r.json().get("app") == "ConvertitoreANIA":
                return porta
        except (requests.RequestException, ValueError):
            continue
    return None


def _porta_libera():
    for porta in PORTE:
        if not _porta_occupata(porta):
            return porta
    raise RuntimeError("Nessuna porta libera tra 8765 e 8775")


def _apri_browser_quando_pronto(server, porta, attesa=15):
    """Apre la pagina appena il server accetta connessioni (non dopo un'attesa fissa)."""
    def lavoro():
        fine = time.time() + attesa
        while not server.started and time.time() < fine:
            time.sleep(0.05)
        webbrowser.open(f"http://127.0.0.1:{porta}")
    threading.Thread(target=lavoro, daemon=True).start()


def main():
    if sys.stdout is None or sys.stderr is None:  # eseguibile senza console: i messaggi vanno su file
        log = open(cartella_dati() / "client.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    attiva = _istanza_attiva()
    if attiva:
        if not os.getenv("ANIA_NO_BROWSER"):
            webbrowser.open(f"http://127.0.0.1:{attiva}")
        return

    porta = _porta_libera()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_config=None))
    app.state.chiudi = lambda: setattr(server, "should_exit", True)
    if not os.getenv("ANIA_NO_BROWSER"):
        _apri_browser_quando_pronto(server, porta)
    server.run()


if __name__ == "__main__":
    main()
