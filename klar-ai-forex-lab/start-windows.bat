@echo off
rem Dubbelklicka for att starta Klar AI Forex Lab (kräver att Docker Desktop är igång).
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop verkar inte vara igang. Starta Docker Desktop, vanta pa "Engine running" och forsok igen.
  pause
  exit /b 1
)
echo Bygger och startar (forsta gangen tar det nagra minuter)...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo Nagot gick fel. Kopiera texten ovan och skicka den till Claude.
  pause
  exit /b 1
)
echo Klart! Oppnar http://localhost:8080
start http://localhost:8080
pause
