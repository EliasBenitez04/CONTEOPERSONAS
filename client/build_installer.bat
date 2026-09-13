@echo off
setlocal
cd /d "%~dp0"

call build_client.bat
if errorlevel 1 exit /b 1

set "ISCC=ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

where "%ISCC%" >nul 2>&1
if errorlevel 1 (
    if not exist "%ISCC%" (
        echo [INSTALLER] Inno Setup 6 no encontrado.
        echo Instala Inno Setup 6 o agrega ISCC.exe al PATH.
        exit /b 1
    )
)

"%ISCC%" "installer\ContePersonas.iss"
if errorlevel 1 (
    echo [INSTALLER] Error compilando instalador.
    exit /b 1
)

echo [INSTALLER] Listo: client\dist\installer\SetupContePersonas.exe
endlocal
