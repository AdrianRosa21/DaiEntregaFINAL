@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
if not exist ".env" copy "credenciales_ejemplo.txt" ".env" >nul
echo ================================================================
echo  Se abrira el archivo .env en el Bloc de notas:
echo   1. Pega tu API Key despues de  VONAGE_API_KEY=
echo   2. Pega tu API Secret despues de  VONAGE_API_SECRET=
echo   3. En MI_NUMERO_WHATSAPP= escribi 503 y tu numero, sin + ni espacios
echo   4. CADA variable en SU PROPIA LINEA, sin espacios ni comillas
echo   5. Guarda con Ctrl + S: el punto de la pestana .env debe desaparecer
echo  NUNCA compartas ni subas el archivo .env: tiene tus claves.
echo ================================================================
notepad ".env"
echo.
echo Cuando ya hayas GUARDADO el .env, presiona una tecla aqui para revisarlo...
pause >nul
echo.
%PY% enviar_prueba.py --verificar
echo.
echo Si todo sale con check verde, segui con 6_enviar_mensaje_prueba.bat
pause
