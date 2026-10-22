; Installer di Convertitore ANIA (Inno Setup 6). Si compila DOPO build\costruisci.ps1:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DVersione=0.1.0 build\installer.iss
; Risultato: dist\ConvertitoreANIA-Setup-0.1.0.exe  (da allegare alla release di GitHub)
; Installa per l'utente corrente (nessun permesso di amministratore). Rilanciare l'installer di una versione
; piu' recente aggiorna il programma senza toccare impostazioni e registro (stanno in %APPDATA%\ConvertitoreANIA).

#ifndef Versione
  #define Versione "0.1.0"
#endif

[Setup]
AppId={{6F0B1A52-3C1E-4C7B-9B7B-7A2E5B1D9C44}
AppName=Convertitore ANIA
AppVersion={#Versione}
AppPublisher=Servizi ANIA
DefaultDirName={autopf}\Convertitore ANIA
DefaultGroupName=Convertitore ANIA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ConvertitoreANIA-Setup-{#Versione}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ConvertitoreANIA.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; GroupDescription: "Icone:"

[Files]
Source: "..\dist\ConvertitoreANIA.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Convertitore ANIA"; Filename: "{app}\ConvertitoreANIA.exe"
Name: "{autodesktop}\Convertitore ANIA"; Filename: "{app}\ConvertitoreANIA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ConvertitoreANIA.exe"; Description: "Avvia Convertitore ANIA"; Flags: nowait postinstall skipifsilent
