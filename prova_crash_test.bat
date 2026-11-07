@echo off
cd /d "%~dp0"
set PY=C:\Python313\python.exe
if not exist "%PY%" set PY=python
set MAX_ESERCIZI=2
set TIMEOUT_SECONDI=90
"%PY%" prova_crash_test.py %1
pause
