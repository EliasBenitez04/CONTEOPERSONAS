@echo off
setlocal
set "SCRIPT=%~dp0run_client.bat"
echo [TASK] Instalando cliente al iniciar sesion...
schtasks /Create /TN "SistemaCamara_Cliente" /TR "\"%SCRIPT%\"" /SC ONLOGON /RL HIGHEST /F
if errorlevel 1 (
    echo [TASK] No se pudo crear la tarea. Ejecuta como Administrador.
    exit /b 1
)
echo [TASK] Cliente configurado para iniciar al entrar a Windows.
endlocal
