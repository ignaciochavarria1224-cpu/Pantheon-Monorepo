@echo off
set "OLYMPUS_ROOT=%~dp0olympus"
set "LOCAL_PYTHON=%USERPROFILE%\OlympusLocal\venv\Scripts\python.exe"
set "FALLBACK_PYTHON=C:\Users\ignac\Documents\AI PROJECTS\Olympus Trading\venv\Scripts\python.exe"

if exist "%LOCAL_PYTHON%" (
    set "PYTHON_EXE=%LOCAL_PYTHON%"
) else (
    set "PYTHON_EXE=%FALLBACK_PYTHON%"
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found:
    echo   %LOCAL_PYTHON%
    echo   %FALLBACK_PYTHON%
    pause
    exit /b 1
)

if not exist "%OLYMPUS_ROOT%\run_live.py" (
    echo [ERROR] Olympus runtime not found at:
    echo   %OLYMPUS_ROOT%
    pause
    exit /b 1
)

cd /d "%OLYMPUS_ROOT%"
"%PYTHON_EXE%" run_live.py
if errorlevel 1 (
    echo.
    echo [LAUNCH FAILED] Olympus exited with an error. See the message above.
    pause
    exit /b 1
)
