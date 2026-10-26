# Costruisce la cartella dist\ConvertitoreANIA\ (exe + librerie, senza console). Da lanciare dalla cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File build\costruisci.ps1
# Niente exe "a file unico": si estrae in una cartella temporanea a ogni avvio (2 secondi persi, errori
# "Failed to load Python DLL", piu' falsi allarmi antivirus).
# Finisce con errore se PyInstaller non riesce o se l'exe prodotto non e' della versione di ania_client\__init__.py:
# in passato un exe vecchio (bloccato da una copia in esecuzione) e' finito per sbaglio negli installer 0.2.0 e 0.2.1.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$radice = (Get-Location).Path
$versione = (Select-String -Path ania_client\__init__.py -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$v4 = (($versione.Split('.') + @('0','0','0','0'))[0..3]) -join ','

# la versione dentro l'exe (Proprieta' -> Dettagli) permette di controllare che sia quello appena costruito
New-Item -ItemType Directory -Force build\work | Out-Null
$infoVersione = "$radice\build\work\version_info.txt"
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($v4), prodvers=($v4), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', 'Convertitore ANIA'), StringStruct('ProductName', 'Convertitore ANIA'),
      StringStruct('FileVersion', '$versione'), StringStruct('ProductVersion', '$versione')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Encoding UTF8 $infoVersione

$inizio = Get-Date
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --name ConvertitoreANIA --version-file $infoVersione `
    --add-data "$radice\ania_client\static;ania_client\static" `
    --collect-submodules uvicorn --hidden-import multipart --hidden-import python_multipart `
    --distpath dist --workpath build\work --specpath build `
    run_client.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller non e' riuscito (codice $LASTEXITCODE): chiudere il programma se e' aperto e riprovare" }

$exe = "dist\ConvertitoreANIA\ConvertitoreANIA.exe"
if (-not (Test-Path $exe)) { throw "Build non riuscita: $exe non esiste" }
$info = Get-Item $exe
if ($info.LastWriteTime -lt $inizio) { throw "L'exe non e' stato ricostruito (data $($info.LastWriteTime)): era bloccato da una copia in esecuzione?" }
if ($info.VersionInfo.FileVersion -ne $versione) { throw "L'exe dichiara la versione '$($info.VersionInfo.FileVersion)', attesa '$versione'" }
"Creato: " + (Resolve-Path $exe) + "  (versione $versione)"
