#!/bin/bash

# Check that Wine is available
if ! command -v wine &>/dev/null; then
    echo "Error: Wine is not installed. Install it with:"
    echo "  sudo apt install wine wine32:i386 wine64 winetricks"
    echo "Or re-run the launcher — it will auto-install Wine when sglBinaries are present."
    exit 1
fi

# Set Wine prefix directory
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32

# Initialise Wine prefix if it doesn't exist yet
if [ ! -d "$WINEPREFIX" ]; then
    echo "Creating Wine prefix..."
    wineboot -i 2>/dev/null
fi

# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# Check if PokerStove.exe exists
if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"
    wine PokerStove.exe 2>/dev/null
    exit
fi

# Install PokerStove
if [ ! -f "./INSTALL/PokerStoveSetup124.exe" ]; then
    echo "Error: PokerStoveSetup124.exe not found in ./INSTALL/"
    echo "This file is provided by sglBinaries_1. Extract it first."
    exit 1
fi

cd "./INSTALL/"
echo "Installing PokerStove..."
WINEDEBUG=-all wine PokerStoveSetup124.exe

if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    echo "PokerStove installed. Launching..."
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"
    wine PokerStove.exe 2>/dev/null
else
    echo "Installation may have failed. Run this script again to retry."
fi
