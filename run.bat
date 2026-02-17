@echo off
echo ==========================================
echo   InventoryPro Setup Script
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [OK] Python detected
python --version
echo.

REM Install dependencies
echo [STEP 1/2] Installing dependencies...
echo This will install Flask and Werkzeug (no C compiler needed)
echo.
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo [OK] Dependencies installed successfully
    echo.
) else (
    echo.
    echo [ERROR] Failed to install dependencies
    echo.
    echo Try running: pip install Flask==3.0.0 Werkzeug==3.0.1
    echo.
    pause
    exit /b 1
)

echo ==========================================
echo   Starting InventoryPro...
echo ==========================================
echo.
echo [STEP 2/2] Launching application...
echo.
echo Access the application at: http://127.0.0.1:5000
echo.
echo Default login credentials:
echo    Username: admin
echo    Password: admin123
echo.
echo Press Ctrl+C to stop the server
echo.

REM Run the application
python app.py

pause