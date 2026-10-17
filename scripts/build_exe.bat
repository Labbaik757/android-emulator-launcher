@echo off
REM Build a standalone Windows .exe (no Python needed to run it afterwards).
REM Run this file on Windows after: pip install -r requirements.txt

pyinstaller --onefile --windowed --name AndroidEmulatorLauncher main.py

echo.
echo Done. Your file is at: dist\AndroidEmulatorLauncher.exe
pause
