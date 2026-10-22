"""Registro locale delle conversioni (una riga JSON per file) in %APPDATA%\\ConvertitoreANIA\\registro.jsonl."""
import csv
import io
import json
import threading
from datetime import datetime

from .config import cartella_dati

_lock = threading.Lock()


def _file():
    return cartella_dati() / "registro.jsonl"


def scrivi(file, esito, tipo=None, avvisi=(), errori=(), files=(), formato=""):
    voce = {
        "quando": datetime.now().isoformat(timespec="seconds"),
        "file": file,
        "esito": esito,
        "tipo": tipo,
        "formato": formato,
        "avvisi": list(avvisi),
        "errori": list(errori),
        "files": list(files),
    }
    try:
        with _lock, _file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(voce, ensure_ascii=False) + "\n")
    except OSError:
        pass  # un problema di registro non deve bloccare la conversione
    return voce


def leggi(limite=200, solo_problemi=False):
    f = _file()
    if not f.exists():
        return []
    voci = []
    with f.open(encoding="utf-8") as fh:
        for riga in fh:
            try:
                voci.append(json.loads(riga))
            except ValueError:
                continue
    if solo_problemi:
        voci = [v for v in voci if v["esito"] != "ok"]
    return voci[::-1][:limite]


def csv_text(voci):
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["quando", "file", "tipo", "formato", "esito", "errori", "avvisi", "file creati"])
    for v in voci:
        w.writerow([v["quando"], v["file"], v.get("tipo") or "", v.get("formato", ""), v["esito"],
                    " | ".join(v["errori"]), " | ".join(v["avvisi"]), " | ".join(v["files"])])
    return "﻿" + out.getvalue()  # BOM: Excel apre bene gli accenti
