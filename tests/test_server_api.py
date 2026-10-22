import base64
import zipfile

import pytest
import requests

from ania_client import server_api as sa
from .conftest import FILES, Risposta, zip_b64

IMP = {"url": "https://api.gestania.it", "chiave": "ANIA-1111-2222-3333-4444", "formato": "adz"}


def test_salva_adz_zip_txt(tmp_path):
    adz = sa.salva_pacchetto(zip_b64(), "pratica.zip", "adz", tmp_path / "o")
    assert [p.split("\\")[-1] for p in adz] == ["pratica.ADZ"]
    assert zipfile.ZipFile(adz[0]).namelist()[0] == "EXPERIZ.TXT"
    assert sa.salva_pacchetto(zip_b64(), "pratica.zip", "zip", tmp_path / "o")[0].endswith("pratica.zip")
    txt = sa.salva_pacchetto(zip_b64(), "pratica.zip", "txt", tmp_path / "o")
    assert {p.split("\\")[-1] for p in txt} == set(FILES)
    assert not [f for f in (tmp_path / "o").rglob("*") if f.name.endswith(".tmp")]  # niente file a meta'


def test_pacchetto_non_valido(tmp_path):
    with pytest.raises(sa.ErroreServizio):
        sa.salva_pacchetto("non-base64!!", "a.zip", "adz", tmp_path)
    with pytest.raises(sa.ErroreServizio):
        sa.salva_pacchetto(base64.b64encode(b"non e uno zip").decode(), "a.zip", "adz", tmp_path)


def test_nomi_pericolosi_restano_nella_cartella(tmp_path):
    out = tmp_path / "o"
    sa.salva_pacchetto(zip_b64({"../../fuori.txt": b"x", "ok.txt": b"y"}), "../../evil.zip", "txt", out)
    assert not (tmp_path / "fuori.txt").exists() and not (tmp_path.parent / "evil").exists()
    assert (out / "evil" / "fuori.txt").exists() and (out / "evil" / "ok.txt").exists()


def test_converti_ok(server, tmp_path):
    r = sa.converti(b"%PDF", "pratica.pdf", {**IMP, "cartella": str(tmp_path)}, "NEM1")
    assert r["esito"] == "ok" and r["id_documento"] == "1367214" and r["files"][0].endswith("pratica.ADZ")
    metodo, percorso, kw = server.chiamate[-1]
    assert (metodo, percorso) == ("POST", "/v1/converti") and kw["data"] == {"autorizzazione": "NEM1"}


def test_intestazioni_con_licenza_e_versione(server, tmp_path):
    sa.converti(b"%PDF", "p.pdf", {**IMP, "cartella": str(tmp_path)})
    assert any(c[2]["headers"]["X-Licenza"] == IMP["chiave"] and "X-Versione-Client" in c[2]["headers"]
               for c in server.chiamate)


def test_converti_errore_licenza(server, tmp_path):
    server.risposte["/v1/converti"] = Risposta(401, {"esito": "errore", "errori": ["Licenza scaduta il 2026-01-01"]})
    r = sa.converti(b"%PDF", "p.pdf", {**IMP, "cartella": str(tmp_path)})
    assert r["esito"] == "errore" and r["errori"] == ["Licenza scaduta il 2026-01-01"] and r["files"] == []
    assert not list(tmp_path.iterdir())


def test_converti_con_avvisi_salva_comunque(server, tmp_path):
    server.risposte["/v1/converti"] = Risposta(200, {"esito": "attenzione", "tipo": "ALDcarr", "avvisi": ["Tempi"],
                                                    "errori": [], "nome_file": "p.zip", "file_base64": zip_b64()})
    r = sa.converti(b"%PDF", "p.pdf", {**IMP, "cartella": str(tmp_path)})
    assert r["esito"] == "attenzione" and r["avvisi"] == ["Tempi"] and len(r["files"]) == 1


def test_errori_di_rete_e_risposte_non_json(server, tmp_path):
    imp = {**IMP, "cartella": str(tmp_path)}
    server.risposte["/v1/converti"] = requests.exceptions.ConnectionError()
    with pytest.raises(sa.ErroreServizio, match="connessione a internet"):
        sa.converti(b"%PDF", "p.pdf", imp)
    server.risposte["/v1/converti"] = requests.exceptions.Timeout()
    with pytest.raises(sa.ErroreServizio, match="in tempo"):
        sa.converti(b"%PDF", "p.pdf", imp)
    server.risposte["/v1/converti"] = Risposta(524, None, "<html>timeout</html>")
    with pytest.raises(sa.ErroreServizio, match="troppo tempo"):
        sa.converti(b"%PDF", "p.pdf", imp)
    server.risposte["/v1/converti"] = Risposta(418, None, "boh")
    with pytest.raises(sa.ErroreServizio, match="HTTP 418"):
        sa.converti(b"%PDF", "p.pdf", imp)


def test_versioni():
    assert sa.versione_tupla("1.2.10") > sa.versione_tupla("1.2.9")
    assert sa.versione_tupla("v0.1.0") == (0, 1, 0)
    assert sa.versione_tupla("") == (0,)
