@echo off
REM ============================================
REM Cross-platform Launcher for Windows
REM Double-click this file to run script.py
REM ============================================

title Script Launcher
cd /d "%~dp0"

REM ============================================
REM CONFIGURATION - Set your GitHub raw URL here
REM ============================================
set "GITHUB_RAW_URL=https://raw.githubusercontent.com/kamatil-dev/hosix/main/script.py"

echo.
echo ========================================
echo        Script Launcher (Windows)
echo ========================================
echo.

REM Check if Python is installed
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
python --version

REM Check/Create virtual environment
echo.
echo [2/5] Setting up virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo.
echo [4/5] Installing/checking dependencies...
python -m pip install playwright beaupy
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install Python packages!
    echo.
    pause
    exit /b 1
)
echo Dependencies installed successfully.

REM Install Playwright browsers
echo.
echo [4.5/5] Installing Playwright browsers (skipped if already installed)...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install Playwright browsers!
    echo.
    pause
    exit /b 1
)

REM Update script from GitHub
echo.
echo [5/5] Checking for script updates...
    powershell -Command "try { Invoke-WebRequest -Uri '%GITHUB_RAW_URL%' -OutFile 'script.py.tmp' -UseBasicParsing; Move-Item -Force 'script.py.tmp' 'script.py'; Write-Host 'Script updated successfully!' } catch { Write-Host 'Update check failed, using local version.' }"

echo.
echo ========================================
echo          Starting Script...
echo ========================================
echo.

REM Run the script
python script.py
set exit_code=%errorlevel%

echo.
if %exit_code% neq 0 (
    echo [Script exited with error code: %exit_code%]
)
echo.
echo Press any key to close...
pause >nul
