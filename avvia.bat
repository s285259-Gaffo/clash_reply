@echo off
cd /d "%~dp0"
set PY=C:\Python313\python.exe
if not exist "%PY%" set PY=python

echo === Controllo librerie ===
"%PY%" -c "import crewai, fastapi, uvicorn, dotenv" 2>nul
if errorlevel 1 (
  echo Installo le librerie, ci vuole qualche minuto...
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo ERRORE durante l'installazione: copia le righe sopra e mandale a Claude.
    pause
    exit /b 1
  )
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo === Avvio server: apri http://localhost:8000 ===
start "" http://localhost:8000
"%PY%" server.py
pause
