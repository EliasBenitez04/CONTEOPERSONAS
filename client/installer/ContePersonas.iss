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

[InstallDelete]
; Limpia restos de versiones antiguas antes de crear el nuevo autoinicio.
Type: files; Name: "{userstartup}\ContePersonas.lnk"
Type: files; Name: "{app}\watchdog.bat"
Type: files; Name: "{app}\run_client_task.bat"
Type: files; Name: "{app}\run_client.bat"
Type: files; Name: "{app}\install_autostart.bat"

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
; El bloqueo .installing sigue activo mientras se edita el .env, evitando que
; un watchdog anterior relance el EXE con configuracion vieja.
Filename: "notepad.exe"; Parameters: "{app}\.env"; Description: "Configurar conexión de cámara y servidor"; Flags: skipifsilent waituntilterminated
Filename: "{cmd}"; Parameters: "/C del /F /Q ""{app}\.installing"" 2>nul"; Flags: runhidden waituntilterminated
Filename: "{sys}\wscript.exe"; Parameters: "//B //Nologo ""{app}\watchdog.vbs"""; Description: "Iniciar ContePersonas"; WorkingDir: "{app}"; Flags: skipifsilent nowait

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\.installing"
; SQLite y .env se conservan para evitar perdida accidental de pendientes/configuracion.

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  PowerShellExe: String;
  PowerShellParams: String;
  LockFile: String;
begin
  ForceDirectories(ExpandConstant('{app}'));

  // Bloquea cualquier relanzamiento mientras el usuario edita el .env.
  LockFile := ExpandConstant('{app}\.installing');
  SaveStringToFile(LockFile, 'installing', False);

  // Detiene solamente los watchdog.vbs de ContePersonas que pudieran haber
  // quedado vivos de una instalacion anterior. No mata otros scripts VBS.
  PowerShellExe := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  PowerShellParams :=
    '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "' +
    'Get-CimInstance Win32_Process | Where-Object { ' +
    '($_.Name -eq ''wscript.exe'' -or $_.Name -eq ''cscript.exe'') -and ' +
    '$_.CommandLine -like ''*ContePersonas*watchdog.vbs*'' } | ' +
    'ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"';

  Exec(
    PowerShellExe,
    PowerShellParams,
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  // Cierra el ejecutable anterior para evitar archivos bloqueados y dos clientes.
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/F /IM ContePersonas.exe',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  // Compatibilidad con instalaciones antiguas basadas en Task Scheduler.
  Exec(
    ExpandConstant('{sys}\schtasks.exe'),
    '/Delete /TN "SistemaCamara_Cliente" /F',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  Result := '';
end;

procedure DeinitializeSetup();
begin
  // Si la instalacion se cancela o termina antes de [Run], no dejar el
  // cliente bloqueado permanentemente.
  if FileExists(ExpandConstant('{app}\.installing')) then
    DeleteFile(ExpandConstant('{app}\.installing'));
end;
