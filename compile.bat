@echo off
title Compilador NitroLink DNS - Auto Open
color 0A

echo ==============================================
echo   NitroLink DNS - Generador de Ejecutable
echo ==============================================
echo.

:: 1. Instalar dependencias necesarias
echo [1/6] Verificando dependencias...
pip install pyinstaller requests dnslib pypresence --upgrade

:: 2. Limpiar compilaciones anteriores
echo [2/6] Limpiando carpetas temporales...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: 3. Compilar el script
echo [3/6] Compilando NitroLink...
if exist icono.ico (
    pyinstaller --noconfirm --onefile --windowed --icon "icono.ico" --name "NitroLink-DNS" "lol.py"
) else (
    pyinstaller --noconfirm --onefile --windowed --name "NitroLink-DNS" "lol.py"
)

:: 4. Copiar archivos necesarios a la carpeta 'dist'
echo [4/6] Copiando archivos de soporte a la carpeta 'dist'...
copy "icono.ico" "dist\" /y
copy "dns_zones.json" "dist\" /y
copy "game_ids.json" "dist\" /y
copy "NitroLink-DNS.spec" "dist\" /y
copy "LICENSE" "dist\" /y
copy "requirements.txt" "dist\" /y

:: 5. Abrir la carpeta contenedora
echo [5/6] Abriendo carpeta de destino...
start "" "dist"

:: 6. Finalizar
echo.
echo [6/6] ¡Proceso terminado con exito!
echo.
pause