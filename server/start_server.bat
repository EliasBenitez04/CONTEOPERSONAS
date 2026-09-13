@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   SISTEMA CAMARA - SERVIDOR CENTRAL POSTGRESQL
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
    echo [SETUP] Si PostgreSQL usa otra clave, edita server\.env.
)

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
echo [SERVER] Login: http://127.0.0.1:8000/login
echo [SERVER] Dashboard: http://127.0.0.1:8000/dashboard
echo [SERVER] Sucursales: http://127.0.0.1:8000/admin/branches
echo [SERVER] Camaras: http://127.0.0.1:8000/admin/cameras
echo [SERVER] Reportes: http://127.0.0.1:8000/reports
echo [SERVER] Usuarios: http://127.0.0.1:8000/users
echo [SERVER] API Health: http://127.0.0.1:8000/api/health
echo [SERVER] Swagger: http://127.0.0.1:8000/docs
echo.

python -m uvicorn app.web:app --host 0.0.0.0 --port 8000 --reload

pause
endlocal
