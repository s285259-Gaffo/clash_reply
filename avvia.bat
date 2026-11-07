@echo off
cd /d "%~dp0"
set "PY="
if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY for /d %%D in ("%APPDATA%\uv\python\cpython-3*-windows-x86_64-none") do if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
if not defined PY set "PY=python"
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo Python non trovato. Installa Python 3.11 o successivo, poi riavvia questo file.
  pause
  exit /b 1
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo === Creo l'ambiente Python del progetto ===
  "%PY%" -m venv "%~dp0.venv"
  if errorlevel 1 goto errore
)

echo === Controllo librerie nell'ambiente del progetto ===
"%VENV_PY%" -c "import crewai, fastapi, uvicorn, dotenv" 2>nul
if errorlevel 1 (
  echo Installo le librerie, ci vuole qualche minuto...
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto errore
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo === Avvio server: apri http://localhost:8000 ===
start "" http://localhost:8000
"%VENV_PY%" server.py
pause
exit /b 0

:errore
echo.
echo ERRORE durante la preparazione. Leggi le righe sopra per il dettaglio.
pause
exit /b 1
