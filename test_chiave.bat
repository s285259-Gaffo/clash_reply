@echo off
cd /d "%~dp0"
set PY=C:\Python313\python.exe
if not exist "%PY%" set PY=python
"%PY%" test_chiave.py
pause
