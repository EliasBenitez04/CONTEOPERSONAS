#define MyAppName "ContePersonas"
#define MyAppVersion "3.0.0"
#define MyAppExeName "ContePersonas.exe"

[Setup]
AppId={{F490F68B-524B-4FD8-AFC4-278CA7C61C66}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\SistemaCamara\ContePersonas
DefaultGroupName=Sistema Cámara
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=SetupContePersonas
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "autostart"; Description: "Iniciar ContePersonas al iniciar sesión en Windows"; GroupDescription: "Inicio automático:"; Flags: unchecked

[Files]
Source: "..\dist\ContePersonas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"

[Icons]
Name: "{group}\ContePersonas"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userstartup}\ContePersonas"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "notepad.exe"; Parameters: "{app}\.env"; Description: "Configurar conexión de cámara y servidor"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
; data y .env se conservan deliberadamente al desinstalar/actualizar.
