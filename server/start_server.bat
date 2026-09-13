@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   SISTEMA CAMARA - SERVIDOR CENTRAL
echo ===============================================

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creando entorno virtual...
    python -m venv .venv

    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )

    call ".venv\Scripts\activate.bat"

    echo [SETUP] Instalando dependencias...
    python -m pip install -r requirements.txt

    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

echo.
echo [SERVER] Iniciando API en http://127.0.0.1:8000
echo [SERVER] Swagger: http://127.0.0.1:8000/docs
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
endlocal
