# Convertitore ANIA – programma per i PC dei clienti

Il cliente trascina i preventivi in PDF nella finestra del programma (nel browser, sul proprio PC). Il programma li
manda al servizio di conversione (`https://api.gestania.it`), riceve il pacchetto ANIA e lo salva come **`.ADZ`**,
**`.zip`** oppure **TXT separati** nella cartella scelta, da cui si importa in WinCar.

**Questo programma non contiene nessun segreto**: né i layout, né le regole di conversione, né la chiave di natif.ai.
Tutta la conversione sta sul server (progetto `docuware-idp-ania`, privato). Per questo il codice può stare su un
repository GitHub pubblico.

```
PC cliente: Convertitore ANIA --PDF + chiave di licenza--> api.gestania.it (server)
                              <--pacchetto zip + avvisi---
            salva .ADZ / .zip / TXT nella cartella scelta
```

## Come lo usa il cliente

1. Installa `ConvertitoreANIA-Setup-X.Y.Z.exe` e lo avvia (si apre la pagina nel browser).
2. Riquadro **3**: inserisce la **chiave di licenza** ricevuta e preme *Salva e verifica*.
3. Riquadro **2**: sceglie formato e cartella di salvataggio.
4. Riquadro **1**: trascina uno o più PDF e preme *Converti*. Ogni file mostra **OK**, **ATTENZIONE** (creato ma con
   avvisi da controllare) o **ERRORE**.
5. In fondo c'è il **registro delle conversioni** (con filtro "solo problemi" e download CSV).

Il pulsante *Esci* chiude il programma. Una seconda apertura non lancia un'altra copia: riapre la pagina.

## Dove salva i dati

`%APPDATA%\ConvertitoreANIA\` contiene `impostazioni.json` (indirizzo del server, chiave di licenza, cartella e
formato), `registro.jsonl` e `client.log`. La chiave di licenza è in chiaro in quel file, accessibile solo all'utente
di Windows. I PDF **non** vengono copiati da nessuna parte dal programma.

## Sicurezza

- La pagina è servita solo su `127.0.0.1` (non raggiungibile da altri PC) e rifiuta richieste con `Host` diverso da
  localhost e richieste di modifica provenienti da altri siti (`Origin` diverso).
- La chiave non viene mai restituita in chiaro dall'API locale (solo mascherata: `ANIA-…7C2A`).
- Il file ricevuto viene scritto prima come file nascosto e poi rinominato: la cartella non contiene mai file a metà.
- I nomi dei file nel pacchetto ricevuto vengono ripuliti (nessun percorso fuori dalla cartella scelta).

## Aggiornamenti

- **Versione minima obbligatoria**: il server può dichiarare (variabile `CLIENT_MINIMO`) la versione minima accettata;
  un client più vecchio mostra "Aggiornamento obbligatorio" e non converte finché non si aggiorna.
- **Nuove versioni**: all'apertura il programma controlla le *release* del repository GitHub pubblico
  (`ania_client/config.py`, `REPO_GITHUB`, oppure la variabile `ANIA_REPO_GITHUB`) e mostra un avviso con il link per
  scaricare l'installer. L'installer nuovo si lancia sopra il vecchio: impostazioni e registro restano.

## Per chi sviluppa

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests -q          # 24 test, server simulato
.venv\Scripts\python.exe run_client.py               # avvia il programma
powershell -ExecutionPolicy Bypass -File build\costruisci.ps1     # dist\ConvertitoreANIA.exe
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DVersione=0.1.0 build\installer.iss    # dist\ConvertitoreANIA-Setup-0.1.0.exe
```

Variabili utili: `ANIA_NO_BROWSER=1` (non apre il browser), `ANIA_CLIENT_DATA` (sposta la cartella dei dati),
`ANIA_REPO_GITHUB` (repository per gli aggiornamenti).

### Pubblicare una nuova versione

1. Aumentare `__version__` in `ania_client/__init__.py`.
2. Costruire l'`.exe` e l'installer (vedi sopra).
3. Su GitHub creare una **release** con tag `vX.Y.Z` e allegare `ConvertitoreANIA-Setup-X.Y.Z.exe`.
4. I client la vedranno al prossimo avvio. Per **imporla**, impostare `CLIENT_MINIMO=X.Y.Z` sul server e riavviare
   il servizio.

### Note sulla distribuzione

- L'`.exe` non è firmato: Windows (SmartScreen) può mostrare "app non riconosciuta" al primo avvio, e alcuni antivirus
  segnalano a torto gli eseguibili creati con PyInstaller. Un certificato di firma del codice (a pagamento) risolve il
  primo problema; in caso di falsi positivi si può passare alla modalità `--onedir` o segnalare il file all'antivirus.
- Prima di pubblicare, impostare in `ania_client/config.py` il valore di `REPO_GITHUB` ("proprietario/repository").
