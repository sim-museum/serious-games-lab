#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment (use lutris-fshack-5.7 for MFC dialog compatibility)
setup_wine_runner() {
    local runner_name="lutris-fshack-5.7-x86_64"
    local runner_dir="$HOME/.local/share/lutris/runners/wine/$runner_name"
    if [[ -d "$runner_dir" && -x "$runner_dir/bin/wine" ]]; then
        export PATH="$runner_dir/bin:$PATH"
        export WINE="$runner_dir/bin/wine"
        export WINELOADER="$runner_dir/bin/wine"
        export WINESERVER="$runner_dir/bin/wineserver"
        export LD_LIBRARY_PATH="$runner_dir/lib64:$runner_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export WINEDLLPATH="$runner_dir/lib64/wine/x86_64-unix:$runner_dir/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"
    fi
}

# Set up runner unless already configured by the launcher
if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner
fi

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
    echo ""
    echo "Note: File > Open and File > Save As do not work (known Wine bug)."
    echo "Evaluation results are automatically appended to pokerstove.txt"
    echo "in the PokerStove directory."
    echo ""
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"

    # Snapshot pokerstove.txt before launch so we can extract only new results
    local snapshot=""
    if [[ -f pokerstove.txt ]]; then
        snapshot="$(wc -c < pokerstove.txt)"
    else
        snapshot=0
    fi

    # Mark game start so afterGamesReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    wine "C:\\Program Files\\PokerStove\\PokerStove.exe" 2>/dev/null

    # Extract only the new results appended during this session
    if [[ -f pokerstove.txt ]]; then
        local new_size
        new_size="$(wc -c < pokerstove.txt)"
        if [[ "$new_size" -gt "$snapshot" ]]; then
            tail -c +"$((snapshot + 1))" pokerstove.txt > "$WINEPREFIX/../pokerstove_$(date '+%y%m%d_%H%M').txt"
            # Restore pokerstove.txt to its pre-session state
            head -c "$snapshot" pokerstove.txt > pokerstove.txt.tmp
            mv pokerstove.txt.tmp pokerstove.txt
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
WINEDEBUG=-all wine PokerStoveSetup124.exe

if [ -f "$WINEPREFIX/drive_c/Program Files/PokerStove/PokerStove.exe" ]; then
    echo "PokerStove installed. Launching..."
    cd "$WINEPREFIX/drive_c/Program Files/PokerStove/"
    # Mark game start so afterGamesReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    wine PokerStove.exe 2>/dev/null
else
    echo "Installation may have failed. Run this script again to retry."
fi
