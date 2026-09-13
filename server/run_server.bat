@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [SERVER] Falta .venv. Ejecuta primero start_server.bat.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m app.setup_database
if errorlevel 1 exit /b 1

python -m uvicorn app.web:app --host 0.0.0.0 --port 8000 --workers 1
endlocal
