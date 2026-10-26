@echo off
REM =====================================================================
REM  lancer_windows.bat - installe (1re fois) puis lance le terminal
REM  Double-clic pour lancer. Ferme cette fenetre noire pour arreter.
REM  A laisser a la racine du depot (a cote de app.py).
REM =====================================================================
setlocal
title Terminal quant
cd /d "%~dp0"
if not exist "%~dp0app.py" (
    echo ERREUR : ce fichier doit etre dans le meme dossier que app.py.
    pause
    exit /b 1
)

REM --- 1. Trouver Python ---
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
    echo ERREUR : Python introuvable. Installe Python 3.12 depuis https://www.python.org/downloads/
    echo et coche "Add python.exe to PATH" pendant l'installation.
    pause
    exit /b 1
)
echo [1/3] Python trouve :
%PY% --version

REM --- 2. Environnement virtuel HORS du dossier (evite la synchro OneDrive) ---
set "VENV=%LOCALAPPDATA%\TerminalQuant\venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo [2/3] Creation de l'environnement virtuel dans %VENV% ...
    %PY% -m venv "%VENV%"
    if errorlevel 1 ( echo ERREUR : creation de l'environnement impossible. & pause & exit /b 1 )
)
echo [2/3] Installation / verification des bibliotheques...
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 ( echo ERREUR : installation des bibliotheques echouee. & pause & exit /b 1 )

REM --- 3. Lancer en local puis ouvrir le navigateur ---
echo [3/3] Terminal sur http://localhost:8501 - laisse cette fenetre ouverte.
start "" /b cmd /c "timeout /t 8 /nobreak >nul & start "" http://localhost:8501"
"%VENV%\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.address localhost --server.port 8501 --browser.gatherUsageStats false
pause
