@echo off
setlocal
cd /d "%~dp0"

:restart
start /wait "ContePersonas" "%~dp0ContePersonas.exe"
echo [CLIENT] ContePersonas se cerro. Reinicio en 10 segundos.
timeout /t 10 /nobreak >nul
goto restart
