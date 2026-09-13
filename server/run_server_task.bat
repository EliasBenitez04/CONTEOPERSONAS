@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

:restart
powershell -NoProfile -Command "$p='logs\server.log'; if(Test-Path $p){ if((Get-Item $p).Length -gt 10485760){ $n='logs\server_'+(Get-Date -Format yyyyMMdd_HHmmss)+'.log'; Move-Item $p $n -Force } }"

echo [%date% %time%] Iniciando servidor... >> "logs\server.log"
call run_server.bat >> "logs\server.log" 2>&1
set "EXITCODE=%ERRORLEVEL%"
echo [%date% %time%] Servidor finalizado con codigo %EXITCODE%. Reintento en 15s. >> "logs\server.log"
timeout /t 15 /nobreak >nul
goto restart
