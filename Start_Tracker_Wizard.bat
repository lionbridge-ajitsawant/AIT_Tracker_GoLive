@echo off
title AIT Tracker Wizard
cd /d "%~dp0"

rem --- check Python is available ---------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python was not found on this computer.
  echo  Install Python 3 from https://www.python.org/downloads/
  echo  and tick "Add python.exe to PATH" during setup, then run this again.
  echo.
  pause
  exit /b 1
)

rem --- first run: install components if they are missing ----------------------
python -c "import flask, msal, openpyxl, requests, dotenv" >nul 2>nul
if errorlevel 1 (
  echo.
  echo  First run - installing components, this takes a minute...
  if exist "wheels" (
    python -m pip install --no-index --find-links wheels -r requirements.txt
  ) else (
    python -m pip install -r requirements.txt
  )
  if errorlevel 1 (
    echo.
    echo  Component install failed. Check internet/proxy, or ask IT to allow pip.
    pause
    exit /b 1
  )
)

rem --- launch -----------------------------------------------------------------
echo.
echo  Starting the AIT Tracker Wizard...
echo  Your browser will open at http://127.0.0.1:5050
echo  Keep THIS window open while you use the wizard. Close it when you are done.
echo.
cd webapp
python app.py
pause
