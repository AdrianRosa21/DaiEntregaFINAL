@echo off
chcp 65001 >nul
cd /d "%~dp0"
set CF=C:\cloudflared\cloudflared.exe
set URL_CF=https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
if exist "%CF%" goto tunel
where cloudflared >nul 2>nul
if not errorlevel 1 (
  set CF=cloudflared
  goto tunel
)
echo No encontre cloudflared. Descargandolo en C:\cloudflared ...
mkdir C:\cloudflared 2>nul
curl.exe -fL -o "%CF%" "%URL_CF%" || del "%CF%" 2>nul
if exist "%CF%" goto tunel
echo.
echo No se pudo descargar automaticamente. Hacelo a mano:
echo   1. Descarga: %URL_CF%
echo   2. Crea la carpeta C:\cloudflared
echo   3. Guarda ahi el archivo con el nombre cloudflared.exe
pause
exit /b 1

:tunel
echo ================================================================
echo  Abajo aparecera un cuadro con una direccion como:
echo     https://palabras-al-azar.trycloudflare.com
echo  Copiala y en dashboard.vonage.com/messages/sandbox pega:
echo     Inbound:  https://...trycloudflare.com/webhooks/inbound
echo     Status:   https://...trycloudflare.com/webhooks/status
echo  Luego presiona Save webhooks.  NO cierres esta ventana.
echo  Ojo: cada vez que abris el tunel la direccion CAMBIA.
echo ================================================================
"%CF%" tunnel --url http://localhost:5000
pause
