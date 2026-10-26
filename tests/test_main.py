import http.server
import json
import socket
import threading
import time

import pytest

from ania_client import main


def porta_libera():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_porta_occupata_e_libera():
    p = porta_libera()
    assert main._porta_occupata(p) is False
    with socket.socket() as s:
        s.bind(("127.0.0.1", p))
        s.listen()
        assert main._porta_occupata(p) is True
    assert main._porta_occupata(p) is False


def test_avvio_a_freddo_non_aspetta_le_porte_chiuse(monkeypatch):
    """Senza istanza attiva non si interroga nessuna porta chiusa (su Windows ognuna costava ~1-2 secondi)."""
    liberi = [porta_libera() for _ in range(6)]
    monkeypatch.setattr(main, "PORTE", liberi)
    inizio = time.perf_counter()
    assert main._istanza_attiva() is None
    assert main._porta_libera() == liberi[0]
    assert time.perf_counter() - inizio < 0.5


def test_trova_l_istanza_gia_attiva_e_salta_le_porte_di_altri_programmi(monkeypatch):
    class Gestore(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            corpo = json.dumps({"app": "ConvertitoreANIA"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *a):
            pass

    altro = socket.socket()                      # un altro programma qualunque: occupa la prima porta
    altro.bind(("127.0.0.1", 0))
    altro.listen()
    p_altro = altro.getsockname()[1]
    srv = http.server.HTTPServer(("127.0.0.1", 0), Gestore)
    p_noi = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(main, "PORTE", [p_altro, p_noi])
        assert main._istanza_attiva() == p_noi
        with pytest.raises(RuntimeError):
            main._porta_libera()
    finally:
        srv.shutdown()
        altro.close()
