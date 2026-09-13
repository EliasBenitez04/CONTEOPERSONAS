@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   SISTEMA CAMARA - SERVIDOR CENTRAL V3
echo ===============================================

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
echo [SETUP] Verificando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [SETUP] Creando server\.env desde .env.example...
    copy /Y ".env.example" ".env" >nul
    echo [SETUP] Se creo .env con configuracion inicial.
)

set "ENVIRONMENT=development"
set "ENABLE_DOCS=1"
for /f "usebackq tokens=1,* delims==" %%A in (`findstr /B /C:"ENVIRONMENT=" /C:"ENABLE_DOCS=" ".env"`) do set "%%A=%%B"

echo.
echo [DB] Verificando PostgreSQL, estructura y usuarios...
python -m app.setup_database
if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo preparar PostgreSQL.
    echo Revisa server\.env: PG_HOST, PG_PORT, PG_DATABASE, PG_USER y PG_PASSWORD.
    pause
    exit /b 1
)

echo.
echo [SERVER] Login:      http://127.0.0.1:8000/login
echo [SERVER] Dashboard:  http://127.0.0.1:8000/dashboard
echo [SERVER] Sucursales: http://127.0.0.1:8000/admin/branches
echo [SERVER] Camaras:    http://127.0.0.1:8000/admin/cameras
echo [SERVER] Clientes:   http://127.0.0.1:8000/admin/clients
echo [SERVER] Reportes:   http://127.0.0.1:8000/reports
echo [SERVER] Usuarios:   http://127.0.0.1:8000/users
echo [SERVER] Auditoria:  http://127.0.0.1:8000/admin/audit
echo [SERVER] Health:     http://127.0.0.1:8000/api/health
if "%ENABLE_DOCS%"=="1" echo [SERVER] Swagger:    http://127.0.0.1:8000/docs
echo [SERVER] Entorno:    %ENVIRONMENT%
echo.

if /I "%ENVIRONMENT%"=="production" (
    python -m uvicorn app.web:app --host 0.0.0.0 --port 8000 --workers 1
) else (
    python -m uvicorn app.web:app --host 0.0.0.0 --port 8000 --reload
)

pause
endlocal
