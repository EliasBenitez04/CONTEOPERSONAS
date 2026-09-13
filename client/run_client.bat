@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_client.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" (
    echo [CLIENT] Falta client\.env
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m app.runner
endlocal
