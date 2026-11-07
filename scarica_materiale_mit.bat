@echo off
cd /d "%~dp0"
set PY=C:\Python313\python.exe
if not exist "%PY%" set PY=python
"%PY%" -m pip install -q pypdf
"%PY%" scarica_materiale_mit.py
"%PY%" prepara_mit.py
pause
