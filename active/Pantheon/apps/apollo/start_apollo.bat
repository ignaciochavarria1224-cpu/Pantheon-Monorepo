@echo off
echo Starting Pantheon Apollo...

set PYTHON=python
set APOLLO=C:\Users\Ignac\Documents\AI PROJECTS\Pantheon\apps\apollo
set WEB=%APOLLO%\web
set UI=%APOLLO%\ui

:: Start Apollo FastAPI backend (port 8001)
start "Apollo Backend" cmd /k "cd /d ""%APOLLO%"" && %PYTHON% -m uvicorn main:app --port 8001 --reload"
timeout /t 4

:: Start the Next.js HUD on port 3001 (Phase 5+)
start "Apollo HUD (Next.js)" cmd /k "cd /d ""%WEB%"" && npm run dev"

:: Reflex UI on port 3000 — kept alive during Phases 5-7 for parity, deleted in Phase 8.
:: Comment out the next line if you no longer want Reflex side-by-side.
start "Apollo UI (Reflex, legacy)" cmd /k "cd /d ""%UI%"" && %PYTHON% -m reflex run"

echo.
echo Pantheon Apollo is starting...
echo HUD (Next.js):  http://localhost:3001
echo Reflex (legacy): http://localhost:3000
echo API:             http://localhost:8001
echo Health:          http://localhost:8001/health
echo.
