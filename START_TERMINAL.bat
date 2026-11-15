@echo off
title Macro Terminal
cd /d "%~dp0"
set "VENV=.venv-mt"

rem ---- Python 3.11 a 3.13 recommande (toutes les librairies ont des versions pretes) ----
if exist "%VENV%\Scripts\python.exe" goto install
set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
if not defined PY (
  echo [Macro Terminal] Installation de Python 3.12 via winget, 1-2 minutes...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-source-agreements --accept-package-agreements
  set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
)
echo [Macro Terminal] Creation de l'environnement avec %PY%
%PY% -m venv %VENV%

:install
if not exist "%VENV%\installed.ok" (
  echo [Macro Terminal] Installation des modules, 2-3 minutes...
  "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
  "%VENV%\Scripts\python.exe" -m pip install --prefer-binary -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [Macro Terminal] ERREUR pendant l'installation. Envoie une capture de cette fenetre a Claude.
    pause
    exit /b 1
  )
  echo ok> "%VENV%\installed.ok"
)
if not exist ".env" copy ".env.example" ".env" >nul

rem ---- Lien https pour le telephone (Cloudflare), s'il n'est pas deja ouvert ----
tasklist /FI "IMAGENAME eq cloudflared-mt.exe" | find /I "cloudflared-mt.exe" >nul || start "Macro Terminal - Lien telephone" /min cmd /c "%~dp0LIEN_TELEPHONE.bat"

rem ---- Ouvre le site dans le navigateur apres le demarrage ----
start "" /min cmd /c "timeout /t 12 /nobreak >nul & start http://localhost:8787"

:loop
echo [Macro Terminal] En marche sur http://localhost:8787  (%date% %time%)
"%VENV%\Scripts\python.exe" -m server
echo [Macro Terminal] Arret inattendu - redemarrage dans 10 secondes...
timeout /t 10 /nobreak >nul
goto loop
