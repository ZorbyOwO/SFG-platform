@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [SFG] Python was not found. Install Python 3.13 or newer, then try again.
    pause
    exit /b 1
)

start "SFG Development" /D "%~dp0" python scripts\run_dev.py --pause-on-error
