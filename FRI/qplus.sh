# Script Outline:
# 1. Set Wine prefix directory.
# 2. Check if Qplus Bridge 15 is installed. If installed, run the application.
# 3. Check Wine version for compatibility. If Wine version is 6.0, display message and exit.
# 4. If Qplus Bridge 15 is not installed and Wine version is compatible, check if installation file exists.
# 5. If installation file exists, initiate the installation process.
# 6. If installation file does not exist, guide the user on how to install Qplus Bridge 15.
#!/bin/bash

# This script launches Qplus Bridge 15 under Wine, ensuring Wine version compatibility.
# If Qplus Bridge 15 is not installed, it guides the user through the installation process.

# Set Wine prefix directory
cd "$(dirname "${BASH_SOURCE[0]}")"
BASE_DIR="$PWD"
export WINEPREFIX="$BASE_DIR/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# GUI harness directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$SCRIPT_DIR/guiHarness"
HARNESS_VENV="$HARNESS_DIR/venv"

# Check if Qplus Bridge is installed (17.1 installs to qbridge17, 15 to qbridge15)
QBRIDGE_DIR=""
if [ -d "$WINEPREFIX/drive_c/games/qbridge17" ]; then
    QBRIDGE_DIR="$WINEPREFIX/drive_c/games/qbridge17"
elif [ -d "$WINEPREFIX/drive_c/games/qbridge15" ]; then
    QBRIDGE_DIR="$WINEPREFIX/drive_c/games/qbridge15"
fi

if [ -n "$QBRIDGE_DIR" ]; then
    # Launch GUI harness in a separate terminal if venv is available
    if [ -x "$HARNESS_VENV/bin/python" ]; then
        gnome-terminal -- bash -c "
            cd '$HARNESS_DIR'
            source venv/bin/activate
            echo 'GUI Harness ready. Open Hand Input dialog in Q-plus, then run:'
            echo '  python bridge_input.py'
            echo ''
            exec bash
        " 2>/dev/null &
    fi

    # Run Qplus Bridge
    cd "$QBRIDGE_DIR"
    wine QBRIDGE.EXE 2>/dev/null 1>/dev/null
    cd "$BASE_DIR"
    clear
    # Display exit message
    cat "$BASE_DIR/DOC/REFERENCE/exitMessageQplus.txt"
    echo ""; echo ""
    exit 0
else
    # Check Wine version for compatibility
    if wine --version | grep "wine-6.0"; then
        # If Wine version is 6.0, display message and exit
        clear
        printf "Version 6.0 of wine detected.\nFor installation, Qplus Bridge requires wine version 7 or greater.\n\nFrom the esports-for-engineers directory, run \n\n./wine-experimental.sh\n\nto install wine 7.\n\nThen run this script again.\n\n"
        exit 0
    fi

    # If Qplus Bridge is not installed and Wine version is compatible, check if installation file exists
    if [ -f "$BASE_DIR/INSTALL/qplus171.exe" ]; then
        # If installation file exists, initiate the installation process
        clear
        echo "Installing Qplus Bridge for the first time; simply accept all defaults."
        echo ""
        wine "$BASE_DIR/INSTALL/qplus171.exe" 2>/dev/null 1>/dev/null
        clear
        # Display exit message
        cat "$BASE_DIR/DOC/REFERENCE/exitMessageQplus.txt"
        echo ""; echo ""
        exit 0
    elif [ -f "$BASE_DIR/INSTALL/qplus15-eng.exe" ]; then
        # Fallback to older installer if available
        clear
        echo "Installing Qplus Bridge for the first time; simply accept all defaults."
        echo ""
        wine "$BASE_DIR/INSTALL/qplus15-eng.exe" 2>/dev/null 1>/dev/null
        clear
        # Display exit message
        cat "$BASE_DIR/DOC/REFERENCE/exitMessageQplus.txt"
        echo ""; echo ""
        exit 0
    else
        # Guide user on how to install Qplus Bridge
        echo " "; echo "To install Qplus Bridge, follow these steps:"
        echo "1. Download qplus171.exe from https://www.q-plus.com/engl/download/download_f.htm"
        echo "2. Copy the exe into the FRI/INSTALL directory"
        echo "3. Run this script again."; echo " "
    fi
fi

