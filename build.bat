@echo off
setlocal
title Otomatik - Build
cd /d "%~dp0"

echo Installation des dependances...
py -3.13 -m pip install --upgrade pip
if errorlevel 1 goto error
py -3.13 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error

echo.
echo Compilation de l'EXE...
py -3.13 -m PyInstaller --noconfirm --clean Otomatik.spec
if errorlevel 1 goto error

echo.
echo Build termine : dist\Otomatik.exe
echo Etape suivante : ouvrir installer\Otomatik.iss dans Inno Setup et compiler.
pause
exit /b 0

:error
echo.
echo La compilation a echoue.
pause
exit /b 1
