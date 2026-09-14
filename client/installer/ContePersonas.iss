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
Name: "autostart"; Description: "Iniciar ContePersonas al iniciar sesión en Windows y reiniciarlo si falla"; GroupDescription: "Inicio automático:"

[Files]
Source: "..\dist\ContePersonas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "watchdog.vbs"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env"; Flags: onlyifdoesntexist uninsneveruninstall

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"

[Icons]
Name: "{group}\ContePersonas"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userstartup}\ContePersonas"; Filename: "{sys}\wscript.exe"; Parameters: "//B //Nologo ""{app}\watchdog.vbs"""; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "notepad.exe"; Parameters: "{app}\.env"; Description: "Configurar conexión de cámara y servidor"; Flags: postinstall skipifsilent
Filename: "{sys}\wscript.exe"; Parameters: "//B //Nologo ""{app}\watchdog.vbs"""; Description: "Iniciar ContePersonas en segundo plano"; WorkingDir: "{app}"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
; SQLite y .env se conservan para evitar perdida accidental de pendientes/configuracion.
