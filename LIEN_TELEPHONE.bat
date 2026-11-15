@echo off
echo %date% %time% demarrage> "%~dp0data\lien_start.log" 2>nul
title Macro Terminal - Lien telephone
cd /d "%~dp0"
if not exist data mkdir data
if not exist tools mkdir tools
set "CF=%~dp0tools\cloudflared-mt.exe"
if not exist "%CF%" (
  echo [Lien] Telechargement de cloudflared - Cloudflare Tunnel...
  curl.exe -L --fail -sS -o "%CF%.part" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" 2> "data\lien_erreur.log"
  if exist "%CF%.part" move /y "%CF%.part" "%CF%" >nul
)
if not exist "%CF%" (
  echo [Lien] ECHEC du telechargement de cloudflared. Details dans data\lien_erreur.log
  pause
  exit /b 1
)
if exist "data\tunnel.log" del "data\tunnel.log"
echo.
echo [Lien] Creation du lien https public vers http://localhost:8787 ...
echo [Lien] Le lien s'affiche aussi dans l'onglet ALERTES du terminal (avec un code QR).
echo [Lien] Garde cette fenetre ouverte : si elle se ferme, le lien change.
echo.
"%CF%" tunnel --no-autoupdate --url http://localhost:8787 --logfile "data\tunnel.log"
echo [Lien] Le tunnel s'est arrete.
pause
