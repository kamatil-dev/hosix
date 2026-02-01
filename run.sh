#!/bin/bash
# ============================================
# Cross-platform Launcher for Linux/macOS
# Double-click this file to run script.py
# ============================================

# ============================================
# CONFIGURATION - Set your GitHub raw URL here
# ============================================
GITHUB_RAW_URL="https://raw.githubusercontent.com/kamatil-dev/hosix/main/script.py"

# Change to script directory
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "       Script Launcher (Linux)"
echo "========================================"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python is installed
echo "[1/5] Checking Python installation..."
if command_exists python3; then
    PYTHON=python3
    PIP=pip3
elif command_exists python; then
    PYTHON=python
    PIP=pip
else
    echo ""
    echo "[ERROR] Python is not installed!"
    echo ""
    echo "Please install Python using your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    echo "  macOS:         brew install python3"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi
$PYTHON --version

# Check/Create virtual environment
echo ""
echo "[2/5] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment!"
        echo "Try: sudo apt install python3-venv"
        read -p "Press Enter to close..."
        exit 1
    fi
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo ""
echo "[3/5] Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "[4/5] Installing/checking dependencies..."
python -m pip install playwright beaupy --quiet
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Python packages!"
    read -p "Press Enter to close..."
    exit 1
fi

# Install Playwright browsers
echo ""
echo "[4.5/5] Installing Playwright browsers (skipped if already installed)..."
python -m playwright install chromium
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Playwright browsers!"
    echo "You may need to install system dependencies:"
    echo "  python -m playwright install-deps chromium"
    read -p "Press Enter to close..."
    exit 1
fi

# Update script from GitHub
echo ""
echo "[5/5] Checking for script updates..."
if command_exists curl; then
    if curl -fsSL -H "Cache-Control: no-cache, no-store" -H "Pragma: no-cache" "$GITHUB_RAW_URL" -o script.py.tmp 2>/dev/null; then
        mv script.py.tmp script.py
        echo "Script updated successfully!"
    else
        echo "Update check failed, using local version."
        rm -f script.py.tmp
    fi
elif command_exists wget; then
    if wget -q --no-cache "$GITHUB_RAW_URL" -O script.py.tmp 2>/dev/null; then
        mv script.py.tmp script.py
        echo "Script updated successfully!"
    else
        echo "Update check failed, using local version."
        rm -f script.py.tmp
    fi
else
    echo "Neither curl nor wget found, skipping update check."
fi

echo ""
echo "========================================"
echo "         Starting Script..."
echo "========================================"
echo ""

# Run the script
python script.py
exit_code=$?

echo ""
if [ $exit_code -ne 0 ]; then
    echo "[Script exited with error code: $exit_code]"
fi
echo ""
read -p "Press Enter to close..."
