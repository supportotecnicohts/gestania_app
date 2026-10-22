# Costruisce dist\ConvertitoreANIA.exe (un solo file, senza console). Da lanciare dalla cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File build\costruisci.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$radice = (Get-Location).Path
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name ConvertitoreANIA `
    --add-data "$radice\ania_client\static;ania_client\static" `
    --collect-submodules uvicorn --hidden-import multipart --hidden-import python_multipart `
    --distpath dist --workpath build\work --specpath build `
    run_client.py
if (-not (Test-Path dist\ConvertitoreANIA.exe)) { throw "Build non riuscita" }
"Creato: " + (Resolve-Path dist\ConvertitoreANIA.exe)
