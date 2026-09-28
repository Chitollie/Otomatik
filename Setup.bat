@echo off
setlocal
title Otomatik - Setup
echo ========================================
echo             OTOMATIK SETUP
echo ========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python n'est pas installe.
    echo Installez Python 3.13 depuis :
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

py -3.13 --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.13 est requis.
    echo Installez Python 3.13 puis relancez Setup.bat.
    pause
    exit /b 1
)

echo Installation des dependances...
py -3.13 -m pip install --upgrade pip
if errorlevel 1 goto error
py -3.13 -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo Installation terminee.
echo Lancement d'Otomatik...
py -3.13 -m app.main
exit /b 0

:error
echo.
echo Une erreur est survenue pendant l'installation.
pause
exit /b 1
