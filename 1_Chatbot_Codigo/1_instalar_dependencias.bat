@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
echo Instalando librerias: Flask, Requests y python-dotenv...
%PY% -m pip install -r requirements.txt
echo.
echo Listo. Ya podes usar el bot.
pause
