@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_client.bat
    if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install pyinstaller
if errorlevel 1 exit /b 1

if not exist "yolov8n.pt" (
    echo [BUILD] Falta client\yolov8n.pt
    exit /b 1
)

rmdir /S /Q build 2>nul
rmdir /S /Q dist\ContePersonas 2>nul

pyinstaller --noconfirm --clean --onedir --noconsole ^
  --name ContePersonas ^
  --add-data "yolov8n.pt;." ^
  --collect-all ultralytics ^
  --collect-all torch ^
  --collect-all torchvision ^
  --hidden-import=cv2 ^
  app\runner.py

if errorlevel 1 (
    echo [BUILD] Error generando el cliente.
    exit /b 1
)

echo [BUILD] Generado en client\dist\ContePersonas
endlocal
