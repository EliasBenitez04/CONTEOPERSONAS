@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist ".env" (
    echo [BACKUP] Falta server\.env
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "KEY=%%A"
    if not "%%A"=="" if not "%%A:~0,1"=="#" set "%%A=%%B"
)

if "%PG_HOST%"=="" set "PG_HOST=127.0.0.1"
if "%PG_PORT%"=="" set "PG_PORT=5432"
if "%PG_DATABASE%"=="" set "PG_DATABASE=contepersonas"
if "%PG_USER%"=="" set "PG_USER=postgres"
if "%BACKUP_RETENTION_DAYS%"=="" set "BACKUP_RETENTION_DAYS=30"

if not exist "backups" mkdir "backups"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%T"
set "OUT=%CD%\backups\contepersonas_%STAMP%.backup"
set "PGPASSWORD=%PG_PASSWORD%"

set "PGDUMP=pg_dump"
if not "%PG_BIN%"=="" if exist "%PG_BIN%\pg_dump.exe" set "PGDUMP=%PG_BIN%\pg_dump.exe"

"%PGDUMP%" -h "%PG_HOST%" -p "%PG_PORT%" -U "%PG_USER%" -F c -b -v -f "%OUT%" "%PG_DATABASE%"
if errorlevel 1 (
    echo [BACKUP] ERROR: no se pudo crear el backup.
    exit /b 1
)

echo [BACKUP] Creado: %OUT%
powershell -NoProfile -Command "$limit=(Get-Date).AddDays(-%BACKUP_RETENTION_DAYS%); Get-ChildItem '%CD%\backups\*.backup' | Where-Object {$_.LastWriteTime -lt $limit} | Remove-Item -Force"
echo [BACKUP] Retencion aplicada: %BACKUP_RETENTION_DAYS% dias.
endlocal
