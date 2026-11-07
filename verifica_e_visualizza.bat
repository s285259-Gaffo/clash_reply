@echo off
cd /d "%~dp0"
set "PY="
if exist "C:\Python313\python.exe" set "PY=C:\Python313\python.exe"
if not defined PY for /d %%D in ("%APPDATA%\uv\python\cpython-3*-windows-x86_64-none") do if exist "%%~fD\python.exe" set "PY=%%~fD\python.exe"
if not defined PY set "PY=python"
"%PY%" -c "import sys" >nul 2>&1
if errorlevel 1 (
  echo Python non trovato. Installa Python 3.11 o successivo.
  pause
  exit /b 1
)

echo === Compilazione dei file Python ===
"%PY%" -m py_compile materiale.py personas.py fantasma.py agenti.py visualizza_verifica.py
if errorlevel 1 goto errore

echo === Prove locali, senza API ===
"%PY%" -m unittest -v test_guardrail
if errorlevel 1 goto errore

echo === Generazione della pagina risultati ===
set "CORSO=%~1"
if not defined CORSO set "CORSO=analisi1_simulato"
"%PY%" visualizza_verifica.py "%CORSO%"
if errorlevel 1 goto errore
start "" "%~dp0materiale\%CORSO%\report\verifica_guardrail.html"
echo Pagina aperta nel browser. Premi un tasto per chiudere.
pause >nul
exit /b 0

:errore
echo La verifica si e' fermata: leggi l'errore qui sopra.
pause
exit /b 1
