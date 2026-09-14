@echo off
setlocal
cd /d "%~dp0"

call build_client.bat
if errorlevel 1 goto :build_error

set "ISCC="

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if defined ISCC goto :found_iscc

for /f "delims=" %%I in ('where.exe ISCC.exe 2^>nul') do set "ISCC=%%I" & goto :found_iscc

goto :not_found

:found_iscc
echo [INSTALLER] Usando: %ISCC%
"%ISCC%" "installer\ContePersonas.iss"
if errorlevel 1 goto :compile_error

echo [INSTALLER] Listo: client\dist\installer\SetupContePersonas.exe
exit /b 0

:not_found
echo [INSTALLER] Inno Setup 6 no encontrado.
echo [INSTALLER] Se reviso LOCALAPPDATA, Program Files y PATH de Windows.
echo [INSTALLER] Verifica con: where.exe ISCC.exe
exit /b 1

:compile_error
echo [INSTALLER] Error compilando instalador.
exit /b 1

:build_error
echo [BUILD] Error generando ContePersonas.
exit /b 1
