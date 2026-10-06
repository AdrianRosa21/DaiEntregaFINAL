@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
echo Deja esta ventana abierta mientras usas el bot en WhatsApp.
%PY% app.py
pause
