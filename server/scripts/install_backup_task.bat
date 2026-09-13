@echo off
setlocal
set "SCRIPT=%~dp0backup_postgres.bat"
echo [TASK] Instalando backup diario a las 02:00...
schtasks /Create /TN "SistemaCamara_Backup_PostgreSQL" /TR "\"%SCRIPT%\"" /SC DAILY /ST 02:00 /RL HIGHEST /F
if errorlevel 1 (
    echo [TASK] No se pudo crear la tarea. Ejecuta como Administrador.
    exit /b 1
)
echo [TASK] Backup diario instalado.
endlocal
