@echo off

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if the CLI file exists
if not exist "src\cli\simple.py" (
    echo Error: src\cli\simple.py not found
    pause
    exit /b 1
)

REM Run the CLI
set PYTHONPATH=.\src
python src\cli\simple.py
pause
