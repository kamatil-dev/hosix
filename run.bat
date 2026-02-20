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
set "RUN_BAT_URL=https://raw.githubusercontent.com/kamatil-dev/hosix/main/run.bat"

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
    echo [INFO] Python is not installed. Attempting automatic installation...
    echo.
    
    REM Try winget first (Windows 10/11)
    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo Installing Python via winget...
        winget install Python.Python.3.10 --version 3.10.11 --accept-package-agreements --accept-source-agreements
        if %errorlevel% equ 0 (
            echo.
            echo [SUCCESS] Python installed successfully!
            echo [INFO] Please close this window and run the script again.
            echo         This is needed to refresh the PATH environment variable.
            echo.
            pause
            exit /b 0
        )
    )
    
    echo.
    echo [INFO] winget not available. Trying direct download from python.org...
    set "PY_INSTALLER=%TEMP%\python_installer.exe"
    powershell -Command "try { Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%PY_INSTALLER%' -UseBasicParsing; Write-Host 'Downloaded.' } catch { Write-Host 'Download failed.'; exit 1 }"
    if exist "%PY_INSTALLER%" (
        echo Running Python installer silently...
        "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1
        del "%PY_INSTALLER%" >nul 2>&1
        echo.
        echo [SUCCESS] Python installed successfully!
        echo [INFO] Please close this window and run the script again.
        echo         This is needed to refresh the PATH environment variable.
        echo.
        pause
        exit /b 0
    )
    echo.
    echo [ERROR] Automatic installation failed!
    echo.
    echo Please install Python manually from: https://www.python.org/downloads/
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

REM Update script and launcher from GitHub
echo.
echo [5/5] Checking for updates...
    powershell -Command "try { Invoke-WebRequest -Uri '%GITHUB_RAW_URL%' -OutFile 'script.py.tmp' -UseBasicParsing -Headers @{'Cache-Control'='no-cache, no-store'; 'Pragma'='no-cache'}; Move-Item -Force 'script.py.tmp' 'script.py'; Write-Host 'Script updated successfully!' } catch { Write-Host 'Script update check failed, using local version.' }"
    powershell -Command "try { Invoke-WebRequest -Uri '%RUN_BAT_URL%' -OutFile 'run.bat.new' -UseBasicParsing -Headers @{'Cache-Control'='no-cache, no-store'; 'Pragma'='no-cache'}; Write-Host 'Launcher update downloaded.' } catch { Write-Host 'Launcher update check failed, using local version.' }"

echo.
echo ========================================
echo          Starting Script...
echo ========================================
echo.

REM Run the script
python script.py
set exit_code=%errorlevel%

REM Apply launcher update now that python has exited (safe to replace run.bat here)
if exist run.bat.new (
    move /y run.bat.new run.bat >nul 2>&1
    if %errorlevel% equ 0 (
        echo [INFO] Launcher updated. Changes take effect on next run.
    ) else (
        del run.bat.new >nul 2>&1
    )
)

echo.
if %exit_code% neq 0 (
    echo [Script exited with error code: %exit_code%]
)
echo.
echo Press any key to close...
pause >nul
