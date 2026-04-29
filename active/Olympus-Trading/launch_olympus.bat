@echo off
set "OLYMPUS_ROOT=C:\Users\ignac\Documents\AI PROJECTS\Olympus Trading\olympus"
set "LOCAL_PYTHON=%USERPROFILE%\OlympusLocal\venv\Scripts\python.exe"
set "FALLBACK_PYTHON=C:\Users\ignac\Documents\AI PROJECTS\Olympus Trading\venv\Scripts\python.exe"

if exist "%LOCAL_PYTHON%" (
    set "PYTHON_EXE=%LOCAL_PYTHON%"
) else (
    set "PYTHON_EXE=%FALLBACK_PYTHON%"
)

cd /d "%OLYMPUS_ROOT%"
"%PYTHON_EXE%" run_live.py
