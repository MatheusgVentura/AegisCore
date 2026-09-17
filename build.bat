@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo    AegisCore - Build do Executavel e Pacote Portatil
echo ======================================================
echo.

echo [1/3] Limpando pastas de build anteriores...
if exist "build" rd /s /q "build"
if exist "dist\AegisCore" rd /s /q "dist\AegisCore"

echo [2/3] Compilando AegisCore com PyInstaller...
python -m PyInstaller --name "AegisCore" --noconsole --icon "aegiscore.ico" --add-data "ui;ui" --add-data "aegiscore.ico;." --clean --noconfirm app.py

if errorlevel 1 (
    echo [ERRO] Falha ao compilar com o PyInstaller.
    pause
    exit /b 1
)

echo [3/3] Criando arquivo portatil zip em dist\...
powershell -Command "Compress-Archive -Path 'dist\AegisCore\*' -DestinationPath 'dist\AegisCore-Portable.zip' -Force"

echo.
echo ======================================================
echo  Build concluida com sucesso!
echo  Executavel: dist\AegisCore\AegisCore.exe
echo  Pacote Zip: dist\AegisCore-Portable.zip
echo ======================================================
echo.
pause
