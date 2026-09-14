@echo off
setlocal
cd /d "%~dp0"

call build_client.bat
if errorlevel 1 exit /b 1

set "ISCC="

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC (
    for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do (
        set "ISCC=%%I"
        goto :found_iscc
    )
)

:found_iscc
if not defined ISCC (
    echo [INSTALLER] Inno Setup 6 no encontrado.
    echo [INSTALLER] Rutas revisadas:
    echo   %LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
    echo   C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    echo   C:\Program Files\Inno Setup 6\ISCC.exe
    echo   PATH de Windows
    exit /b 1
)

echo [INSTALLER] Usando: %ISCC%
"%ISCC%" "installer\ContePersonas.iss"
if errorlevel 1 (
    echo [INSTALLER] Error compilando instalador.
    exit /b 1
)

echo [INSTALLER] Listo: client\dist\installer\SetupContePersonas.exe
endlocal
