@echo off
echo Starting 3D Model Generator GUI...
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or later
    pause
    exit /b 1
)

REM Check if required packages are installed
python -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error installing packages. Please run: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

REM Start the GUI
echo Starting GUI...
python ui.py

pause 