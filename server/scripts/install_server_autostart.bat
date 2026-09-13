@echo off
setlocal
set "SCRIPT=%~dp0..\run_server_task.bat"
echo [TASK] Instalando servidor al iniciar Windows...
schtasks /Create /TN "SistemaCamara_Servidor" /TR "\"%SCRIPT%\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 (
    echo [TASK] No se pudo crear la tarea. Ejecuta como Administrador.
    exit /b 1
)
echo [TASK] Servidor configurado para iniciar con Windows.
echo [TASK] Log: server\logs\server.log
endlocal
