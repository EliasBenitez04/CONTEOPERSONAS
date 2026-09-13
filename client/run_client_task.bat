@echo off
setlocal
cd /d "%~dp0"

:restart
call run_client.bat
set "EXITCODE=%ERRORLEVEL%"
echo [CLIENT] Proceso finalizado con codigo %EXITCODE%. Reintento en 10s.
timeout /t 10 /nobreak >nul
goto restart
