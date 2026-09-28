@echo off
py -3 -m pip install -r requirements.txt
py -3 -m pip install pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name Otomatik app\main.py
pause
