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
pip install playwright beaupy --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python packages!
    pause
    exit /b 1
)

REM Install Playwright browsers (only if not already installed)
if not exist "venv\Lib\site-packages\playwright\driver\package\.local-browsers" (
    echo Installing Playwright browsers (first time only, please wait)...
    playwright install chromium
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Playwright browsers!
        pause
        exit /b 1
    )
)

REM Update script from GitHub
echo.
echo [5/5] Checking for script updates...
if not "%GITHUB_RAW_URL%"=="https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/script.py" (
    echo Downloading latest version from GitHub...
    powershell -Command "try { Invoke-WebRequest -Uri '%GITHUB_RAW_URL%' -OutFile 'script.py.tmp' -UseBasicParsing; Move-Item -Force 'script.py.tmp' 'script.py'; Write-Host 'Script updated successfully!' } catch { Write-Host 'Update check failed, using local version.' }"
) else (
    echo [INFO] GitHub URL not configured. Using local script.py
    echo To enable auto-updates, edit run.bat and set GITHUB_RAW_URL
)

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
