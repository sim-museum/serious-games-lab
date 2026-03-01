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
wine winecfg -v winxp  2>/dev/null 1>/dev/null


# Check if PokerStove.exe exists
if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"
    wine PokerStove.exe 2>/dev/null
    exit
else
    # Change directory to PokerStove installation directory
    cd "./INSTALL/"

    # Print installation instructions
    clear;
    echo "In the configuration dialog, choose Windows XP as the MS Windows version."
    echo "Press Enter to continue ..."

    read replyString

    winecfg 2>/dev/null 1>/dev/null

    # Run PokerStoveSetup124.exe using Wine
    wine PokerStoveSetup124.exe 2>/dev/null 1>/dev/null

    # Print success message
    clear
    echo "Hold Em calculator installed, run this script again."
    exit
fi
