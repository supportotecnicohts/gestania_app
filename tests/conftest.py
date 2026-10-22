import base64
import io
import json
import zipfile

import pytest

FILES = {"EXPERIZ.TXT": b"a", "EXPERIZ2.TXT": b"b", "EXPDANNI.TXT": b"c", "EXPDANNI2.TXT": b"d", "INFO.TXT": b"e",
         "pratica.pdf": b"%PDF-1.4"}


def zip_b64(files=FILES):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n, c in files.items():
            zf.writestr(n, c)
    return base64.b64encode(buf.getvalue()).decode()


class Risposta:
    def __init__(self, stato=200, dati=None, testo=None):
        self.status_code = stato
        self._dati = dati
        self.text = testo if testo is not None else json.dumps(dati)

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._dati is None:
            raise ValueError("non json")
        return self._dati

    def raise_for_status(self):
        if not self.ok:
            import requests
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture(autouse=True)
def dati_isolati(tmp_path, monkeypatch):
    monkeypatch.setenv("ANIA_CLIENT_DATA", str(tmp_path / "dati"))
    from ania_client import app as _app
    _app._server.update(quando=0.0, dati=None)
    return tmp_path


@pytest.fixture
def server(monkeypatch):
    """Server finto: registra le richieste fatte e risponde in base al percorso."""
    class S:
        chiamate = []
        risposte = {}

    S.chiamate = []
    S.risposte = {
        "/v1/stato": Risposta(200, {"stato": "ok", "versione_api": "1", "client_minimo": "0.0.0"}),
        "/v1/licenza": Risposta(200, {"valida": True, "cliente": "Autoservizi Srl", "postazione": "PC 1",
                                      "scadenza": None}),
        "/v1/converti": Risposta(200, {"esito": "ok", "tipo": "ALDmecc", "id_documento": "1367214",
                                       "avvisi": [], "errori": [], "nome_file": "pratica.zip",
                                       "file_base64": zip_b64()}),
    }

    def finto(metodo, url, **kw):
        percorso = "/" + url.split("//", 1)[1].split("/", 1)[1]
        S.chiamate.append((metodo, percorso, kw))
        r = S.risposte[percorso]
        if isinstance(r, Exception):
            raise r
        return r

    from ania_client import server_api
    monkeypatch.setattr(server_api.requests, "request", finto)
    return S
