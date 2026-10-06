@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
%PY% -m unittest discover -s pruebas -v
echo.
%PY% pruebas\evaluar_nlp.py
pause
