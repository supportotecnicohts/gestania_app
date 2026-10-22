"""Avvio del programma: server locale su 127.0.0.1 + apertura del browser. Una sola istanza per utente."""
import os
import socket
import sys
import threading
import webbrowser

import requests
import uvicorn

from .app import app
from .config import cartella_dati

PORTE = range(8765, 8776)


def _istanza_attiva():
    """Porta su cui gira gia' il programma, se c'e'."""
    for porta in PORTE:
        try:
            r = requests.get(f"http://127.0.0.1:{porta}/api/stato", timeout=1)
            if r.ok and r.json().get("app") == "ConvertitoreANIA":
                return porta
        except (requests.RequestException, ValueError):
            continue
    return None


def _porta_libera():
    for porta in PORTE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                return porta
    raise RuntimeError("Nessuna porta libera tra 8765 e 8775")


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
        threading.Timer(1.2, webbrowser.open, args=(f"http://127.0.0.1:{porta}",)).start()
    server.run()


if __name__ == "__main__":
    main()
