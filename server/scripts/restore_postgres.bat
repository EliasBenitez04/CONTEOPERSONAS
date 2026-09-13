@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if "%~1"=="" (
    echo Uso: restore_postgres.bat "C:\ruta\backup.backup"
    exit /b 1
)
if not exist "%~1" (
    echo [RESTORE] No existe: %~1
    exit /b 1
)
if not exist ".env" (
    echo [RESTORE] Falta server\.env
    exit /b 1
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do set "%%A=%%B"

if "%PG_HOST%"=="" set "PG_HOST=127.0.0.1"
if "%PG_PORT%"=="" set "PG_PORT=5432"
if "%PG_DATABASE%"=="" set "PG_DATABASE=contepersonas"
if "%PG_USER%"=="" set "PG_USER=postgres"

set "PGRESTORE=pg_restore"
if not "%PG_BIN%"=="" if exist "%PG_BIN%\pg_restore.exe" set "PGRESTORE=%PG_BIN%\pg_restore.exe"
set "PGPASSWORD=%PG_PASSWORD%"

echo ADVERTENCIA: se restaurara el backup sobre %PG_DATABASE%.
set /p CONFIRM=Escriba RESTAURAR para continuar: 
if /I not "%CONFIRM%"=="RESTAURAR" (
    echo [RESTORE] Cancelado.
    exit /b 0
)

"%PGRESTORE%" -h "%PG_HOST%" -p "%PG_PORT%" -U "%PG_USER%" -d "%PG_DATABASE%" --clean --if-exists --no-owner "%~1"
if errorlevel 1 (
    echo [RESTORE] La restauracion termino con errores. Revise la salida.
    exit /b 1
)
echo [RESTORE] Restauracion completada.
endlocal
