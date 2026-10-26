# Costruisce exe + installer di una versione e stampa i comandi per pubblicarla. Da lanciare dalla cartella del progetto:
#   powershell -ExecutionPolicy Bypass -File build\pubblica.ps1
# Prima aumentare __version__ in ania_client\__init__.py. Non pubblica nulla: stampa cosa fare dopo.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$versione = (Select-String -Path ania_client\__init__.py -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
& powershell -ExecutionPolicy Bypass -File build\costruisci.ps1
if ($LASTEXITCODE -ne 0) { throw "Costruzione dell'exe non riuscita" }
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 non trovato: $iscc" }
& $iscc "/DVersione=$versione" build\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Costruzione dell'installer non riuscita" }
$installer = "dist\ConvertitoreANIA-Setup-$versione.exe"
$sha = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
@"

=== Versione $versione pronta ===
1. GitHub: crea una release con tag v$versione e allega  $((Resolve-Path $installer).Path)
2. Sul server (cartella C:\GestAnia2), dopo aver caricato la release:
   .venv\Scripts\python.exe scripts\pubblica_client.py $versione $sha --repo supportotecnicohts/gestania_app
"@
