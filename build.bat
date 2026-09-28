@echo off
setlocal
title Otomatik - Build

py -3.13 -m pip install pyinstaller
if errorlevel 1 goto error

py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name Otomatik app\main.py
if errorlevel 1 goto error

echo.
echo Build termine : dist\Otomatik.exe
pause
exit /b 0

:error
echo.
echo La compilation a echoue.
pause
exit /b 1
