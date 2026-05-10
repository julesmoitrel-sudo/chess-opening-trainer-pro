@echo off
REM ------------------------------------------------------------------
REM  Build Chess Opening Trainer Pro -> chess_opening_trainer_pro.exe
REM ------------------------------------------------------------------
SETLOCAL ENABLEDELAYEDEXPANSION

echo.
echo === Chess Opening Trainer Pro - Build Windows ===
echo.

REM 1) Verifier Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python est introuvable dans le PATH.
    echo Installez Python 3.10+ puis relancez ce script.
    pause
    exit /b 1
)

REM 2) Installer les dependances
echo Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM 3) Nettoyer les anciens builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist chess_opening_trainer_pro.spec del /q chess_opening_trainer_pro.spec

REM 4) Lancer PyInstaller
echo Construction de l'executable...
pyinstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name chess_opening_trainer_pro ^
    --add-data "openings.json;." ^
    --add-data "config.json;." ^
    --add-data "assets;assets" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERREUR] La construction PyInstaller a echoue.
    pause
    exit /b 1
)

echo.
echo === Build termine ===
echo Executable disponible dans : dist\chess_opening_trainer_pro\chess_opening_trainer_pro.exe
echo.
pause
ENDLOCAL
