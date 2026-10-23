import pytest
import requests
from fastapi.testclient import TestClient

from ania_client import aggiornamenti, app as appmod, config, registro
from .conftest import Risposta


@pytest.fixture
def client(dati_isolati):
    return TestClient(appmod.app, base_url="http://127.0.0.1:8765")


def configura(client, tmp_path, **extra):
    r = client.post("/api/impostazioni", json={"chiave": "ANIA-1111-2222-3333-4444",
                                               "cartella": str(tmp_path / "out"), "formato": "adz", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def invia(client, nome="pratica.pdf", aut=""):
    return client.post("/api/converti", files={"file": (nome, b"%PDF-1.4", "application/pdf")},
                       data={"autorizzazione": aut})


def test_la_chiave_non_esce_mai_in_chiaro(client, tmp_path):
    configura(client, tmp_path)
    for p in ("/api/stato", "/api/impostazioni"):
        testo = client.get(p).text
        assert "ANIA-1111-2222-3333-4444" not in testo and "ha_chiave" in testo


def test_salvare_senza_toccare_la_chiave_la_conserva(client, tmp_path):
    configura(client, tmp_path)
    mascherata = client.get("/api/impostazioni").json()["chiave"]
    client.post("/api/impostazioni", json={"chiave": mascherata, "cartella": str(tmp_path / "altra")})
    assert config.carica()["chiave"] == "ANIA-1111-2222-3333-4444"
    client.post("/api/impostazioni", json={"cartella": str(tmp_path / "altra")})
    assert config.carica()["chiave"] == "ANIA-1111-2222-3333-4444"


def test_impostazioni_non_valide(client, tmp_path):
    r = client.post("/api/impostazioni", json={"url": "http://esempio.it", "formato": "rar"})
    assert r.status_code == 400 and {"url", "formato"} <= set(r.json()["errori"])


def test_converte_e_registra(client, server, tmp_path):
    configura(client, tmp_path)
    r = invia(client, aut="NEM1").json()
    assert r["esito"] == "ok" and r["tipo"] == "ALDmecc" and r["files"][0].endswith("pratica.ADZ")
    assert (tmp_path / "out" / "pratica.ADZ").exists()
    v = client.get("/api/registro").json()
    assert v[0]["file"] == "pratica.pdf" and v[0]["esito"] == "ok"
    assert "esito" in client.get("/api/registro.csv").text.splitlines()[0]


def test_senza_chiave_non_chiama_il_server(client, server):
    r = invia(client).json()
    assert r["esito"] == "errore" and "chiave" in r["errori"][0]
    assert not [c for c in server.chiamate if c[1] == "/v1/converti"]


def test_solo_pdf_e_limite_dimensione(client, tmp_path, monkeypatch):
    configura(client, tmp_path)
    assert client.post("/api/converti", files={"file": ("a.txt", b"x")}).status_code == 400
    monkeypatch.setattr(appmod, "MAX_PDF_MB", 0)
    assert invia(client).status_code == 413


def test_errore_del_server_viene_registrato(client, server, tmp_path):
    configura(client, tmp_path)
    server.risposte["/v1/converti"] = Risposta(401, {"esito": "errore", "errori": ["Licenza non valida"]})
    r = invia(client).json()
    assert r["esito"] == "errore" and r["errori"] == ["Licenza non valida"]
    assert client.get("/api/registro?solo_problemi=true").json()[0]["errori"] == ["Licenza non valida"]


def test_server_non_raggiungibile(client, server, tmp_path):
    configura(client, tmp_path)
    server.risposte["/v1/converti"] = requests.exceptions.ConnectionError()
    r = invia(client).json()
    assert r["esito"] == "errore" and "connessione" in r["errori"][0]


def test_aggiornamento_obbligatorio_blocca(client, server, tmp_path):
    configura(client, tmp_path)
    server.risposte["/v1/stato"] = Risposta(200, {"stato": "ok", "versione_api": "1", "client_minimo": "9.0.0"})
    v = client.get("/api/server").json()
    assert v["obbligatorio"] is True and v["licenza"]["valida"] is True
    r = invia(client).json()
    assert r["esito"] == "errore" and "obbligatorio" in r["errori"][0]
    assert not [c for c in server.chiamate if c[1] == "/v1/converti"]


def test_verifica_licenza_non_valida(client, server, tmp_path):
    configura(client, tmp_path)
    server.risposte["/v1/licenza"] = Risposta(401, {"esito": "errore", "errori": ["Licenza scaduta il 2026-01-01"]})
    v = client.get("/api/server").json()
    assert v["raggiungibile"] and v["licenza"] == {"valida": False, "errore": "Licenza scaduta il 2026-01-01"}


def test_solo_richieste_locali(client, dati_isolati):
    esterno = TestClient(appmod.app, base_url="http://sito-malevolo.example")
    assert esterno.get("/api/stato").status_code == 403
    # una pagina di un altro sito non puo' modificare le impostazioni
    r = client.post("/api/impostazioni", json={"formato": "zip"}, headers={"Origin": "http://sito-malevolo.example"})
    assert r.status_code == 403
    assert client.get("/api/stato").json()["app"] == "ConvertitoreANIA"


def test_aggiornamenti_da_github(monkeypatch):
    aggiornamenti._cache.update(quando=0.0, risultato=None)
    monkeypatch.setattr(aggiornamenti.requests, "get", lambda *a, **k: Risposta(200, {
        "tag_name": "v9.9.9", "html_url": "https://github.com/x/y/releases/tag/v9.9.9", "body": "novita"}))
    r = aggiornamenti.controlla(repo="x/y", versione="0.1.0", forza=True)
    assert r["disponibile"] and r["versione"] == "9.9.9" and r["url"].endswith("v9.9.9")
    r = aggiornamenti.controlla(repo="x/y", versione="9.9.9", forza=True)
    assert not r["disponibile"]
    assert aggiornamenti.controlla(repo="")["disponibile"] is False  # nessun repository: nessun controllo


def test_aggiornamenti_mai_eccezioni(monkeypatch):
    aggiornamenti._cache.update(quando=0.0, risultato=None)

    def giu(*a, **k):
        raise requests.ConnectionError()

    monkeypatch.setattr(aggiornamenti.requests, "get", giu)
    assert aggiornamenti.controlla(repo="x/y", forza=True)["disponibile"] is False


def test_registro_csv_e_filtro(dati_isolati):
    registro.scrivi("a.pdf", "ok", "ALDmecc")
    registro.scrivi("b.pdf", "attenzione", avvisi=["x"])
    registro.scrivi("c.pdf", "errore", errori=["y"])
    assert [v["file"] for v in registro.leggi()] == ["c.pdf", "b.pdf", "a.pdf"]
    assert [v["file"] for v in registro.leggi(solo_problemi=True)] == ["c.pdf", "b.pdf"]
    assert registro.csv_text(registro.leggi()).startswith("﻿quando;")


def test_server_vecchio_senza_verifica_licenza(client, server, tmp_path):
    configura(client, tmp_path)
    server.risposte["/v1/licenza"] = Risposta(404, {"detail": "Not Found"})
    v = client.get("/api/server").json()
    assert v["raggiungibile"] and v["licenza"] is None


# --- aggiornamento con un clic -------------------------------------------------------------------------------------

import hashlib

from ania_client import aggiorna

INSTALLER = b"MZ-installer-finto" * 1000
URL_RELEASE = "https://github.com/x/gestania_app/releases/download/v9.9.9/ConvertitoreANIA-Setup-9.9.9.exe"


def release(sha=None, url=URL_RELEASE):
    return {"versione": "9.9.9", "sha256": sha or hashlib.sha256(INSTALLER).hexdigest(), "url": url}


def stato_con_release(server, rel):
    server.risposte["/v1/stato"] = Risposta(200, {"stato": "ok", "versione_api": "1", "client_minimo": "0.0.0",
                                                  "client_ultima": rel})


class Scaricamento:
    """requests.get finto in streaming: opzionalmente passa da un reindirizzamento."""
    def __init__(self, contenuto, url=URL_RELEASE, history=()):
        self.contenuto, self.url, self.history = contenuto, url, list(history)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        for i in range(0, len(self.contenuto), n):
            yield self.contenuto[i:i + n]


def test_aggiornamento_proposto_dal_server(client, server, tmp_path, monkeypatch):
    configura(client, tmp_path)
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    stato_con_release(server, release())
    a = client.get("/api/aggiornamenti").json()
    assert a["disponibile"] and a["versione"] == "9.9.9" and a["automatico"] is True


def test_nessun_aggiornamento_se_la_versione_e_gia_questa(client, server, tmp_path):
    configura(client, tmp_path)
    stato_con_release(server, {**release(), "versione": "0.1.0"})
    assert client.get("/api/aggiornamenti").json()["disponibile"] is False


def test_release_del_server_non_valida_viene_ignorata(client, server, tmp_path):
    configura(client, tmp_path)
    for rel in (release(url="https://sito-strano.example/a.exe"), release(sha="1234"), {"versione": "9.9.9"}):
        appmod._server.update(quando=0.0, dati=None)
        stato_con_release(server, rel)
        assert client.get("/api/server").json()["client_ultima"] is None


def test_aggiorna_scarica_verifica_e_lancia(client, server, tmp_path, monkeypatch):
    configura(client, tmp_path)
    lanciati, chiusure = [], []
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    monkeypatch.setattr(aggiorna.requests, "get", lambda *a, **k: Scaricamento(INSTALLER))
    monkeypatch.setattr(aggiorna, "lancia", lanciati.append)
    monkeypatch.setattr(appmod.threading, "Timer", lambda t, f: type("T", (), {"start": lambda s: chiusure.append(f)})())
    appmod.app.state.chiudi = lambda: None
    stato_con_release(server, release())
    r = client.post("/api/aggiorna")
    assert r.status_code == 200 and r.json()["versione"] == "9.9.9"
    assert len(lanciati) == 1 and lanciati[0].read_bytes() == INSTALLER and len(chiusure) == 1
    appmod._aggiornamento_in_corso.release()


def test_aggiorna_rifiuta_file_con_impronta_diversa(client, server, tmp_path, monkeypatch):
    configura(client, tmp_path)
    lanciati = []
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    monkeypatch.setattr(aggiorna.requests, "get", lambda *a, **k: Scaricamento(b"file manomesso"))
    monkeypatch.setattr(aggiorna, "lancia", lanciati.append)
    stato_con_release(server, release())
    r = client.post("/api/aggiorna")
    assert r.status_code == 502 and "non corrisponde" in r.json()["detail"]
    assert not lanciati and not list((tmp_path / "dati" / "aggiornamenti").glob("*"))  # nulla resta su disco
    assert appmod._aggiornamento_in_corso.acquire(blocking=False)  # il blocco e' stato rilasciato
    appmod._aggiornamento_in_corso.release()


def test_aggiorna_rifiuta_reindirizzamento_fuori_da_github(client, server, tmp_path, monkeypatch):
    configura(client, tmp_path)
    lanciati = []
    cattivo = Scaricamento(INSTALLER, url="https://sito-strano.example/a.exe", history=[Scaricamento(b"", URL_RELEASE)])
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    monkeypatch.setattr(aggiorna.requests, "get", lambda *a, **k: cattivo)
    monkeypatch.setattr(aggiorna, "lancia", lanciati.append)
    stato_con_release(server, release())
    assert client.post("/api/aggiorna").status_code == 502 and not lanciati


def test_aggiorna_non_parte_con_conversione_in_corso_o_senza_exe(client, server, tmp_path, monkeypatch):
    configura(client, tmp_path)
    stato_con_release(server, release())
    assert client.post("/api/aggiorna").status_code == 400  # eseguito da sorgente, non installato
    monkeypatch.setattr(aggiorna, "puo_installare", lambda: True)
    appmod._conversioni_in_corso["n"] = 1
    try:
        assert client.post("/api/aggiorna").status_code == 409
    finally:
        appmod._conversioni_in_corso["n"] = 0
    stato_con_release(server, None)
    appmod._server.update(quando=0.0, dati=None)
    assert client.post("/api/aggiorna").status_code == 404
