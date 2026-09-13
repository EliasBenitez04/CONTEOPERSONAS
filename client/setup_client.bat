@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [CLIENT] Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo [CLIENT] Se creo client\.env. Configuralo antes de iniciar.
)

echo [CLIENT] Entorno preparado.
endlocal
