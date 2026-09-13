@echo off
setlocal
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

powershell -NoProfile -Command "$p='logs\server.log'; if(Test-Path $p){ if((Get-Item $p).Length -gt 10485760){ $n='logs\server_'+(Get-Date -Format yyyyMMdd_HHmmss)+'.log'; Move-Item $p $n -Force } }"

call run_server.bat >> "logs\server.log" 2>&1
endlocal
