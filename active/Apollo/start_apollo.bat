@echo off
echo Starting Apollo...

:: Start Apollo backend
start "Apollo Backend" cmd /k "cd /d C:\Users\Ignac\Dropbox\Apollo && venv\Scripts\activate && python main.py"
timeout /t 4

:: Start Apollo UI
start "Apollo UI" cmd /k "cd /d C:\Users\Ignac\Dropbox\Apollo\ui && ..\venv\Scripts\reflex run"
timeout /t 3

:: Start WhatsApp bridge (requires Node.js installed)
:: start "Apollo WhatsApp" cmd /k "cd /d C:\Users\Ignac\Dropbox\Apollo\channels\whatsapp_bridge && node index.js"

echo.
echo Apollo is starting...
echo Web UI:   http://localhost:3000
echo API:      http://localhost:8001
echo Health:   http://localhost:8001/health
echo.
echo NOTE: Edit .env with your real credentials before first use.
