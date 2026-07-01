@echo off
REM Double-click this file in Explorer to set up (first run only) and start
REM Project Manager. Safe to run repeatedly - setup steps are skipped once done.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python was not found.
        echo Install it from https://www.python.org/downloads/ and make sure to
        echo check "Add python.exe to PATH" during installation.
        pause
        exit /b 1
    )
    set "PYTHON=py"
) else (
    set "PYTHON=python"
)

if not exist ".venv" (
    echo First-time setup: creating a virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo Could not create a virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Could not install dependencies.
    pause
    exit /b 1
)

python main.py
if errorlevel 1 (
    echo.
    echo Project Manager exited with an error.
    pause
)
