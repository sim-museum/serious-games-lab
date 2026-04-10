#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$PWD"

# PokerStove works fine with system wine — no special runner needed

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
    wineserver -w 2>/dev/null
fi

# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
wineserver -w 2>/dev/null

# Check if PokerStove.exe exists
if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    echo ""
    echo "Note: File > Open and File > Save As do not work (known Wine bug)."
    echo "Evaluation results are automatically appended to pokerstove.txt"
    echo "in the PokerStove directory."
    echo ""
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"

    # Snapshot pokerstove.txt before launch so we can extract only new results
    snapshot=""
    if [[ -f pokerstove.txt ]]; then
        snapshot="$(wc -c < pokerstove.txt)"
    else
        snapshot=0
    fi

    # Mark game start so afterGameReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    wine "C:\\Program Files\\PokerStove\\PokerStove.exe" 2>/dev/null

    # Extract only the new results appended during this session
    if [[ -f pokerstove.txt ]]; then
        new_size="$(wc -c < pokerstove.txt)"
        if [[ "$new_size" -gt "$snapshot" ]]; then
            local_session_file="$SCRIPT_DIR/pokerstove_$(date '+%y%m%d_%H%M').txt"
            tail -c +"$((snapshot + 1))" pokerstove.txt > "$local_session_file"
            # Restore pokerstove.txt to its pre-session state
            head -c "$snapshot" pokerstove.txt > pokerstove.txt.tmp
            mv pokerstove.txt.tmp pokerstove.txt
            # Annotate session results with Claude Code
            source "$SCRIPT_DIR/claude_annotate_poker.sh"
            claude_annotate_poker "$local_session_file"
        fi
    fi
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
WINEDEBUG=-all wine PokerStoveSetup124.exe /SILENT /SUPPRESSMSGBOXES /NORESTART
wineserver -w 2>/dev/null

if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    echo "PokerStove installed. Launching..."
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"
    # Mark game start so afterGameReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    wine PokerStove.exe 2>/dev/null
else
    echo "Installation may have failed. Run this script again to retry."
fi
