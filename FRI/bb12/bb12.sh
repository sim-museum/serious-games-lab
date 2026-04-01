# Script Outline:
# 1. Check if Bridge Baron 12 is already installed. If so, run the application.
# 2. If Bridge Baron 12 is not installed, guide the user through the installation process.
# 3. Provide instructions for configuring Wine.
# 4. Inform the user about successful installation.

#!/bin/bash

# This script installs and runs Bridge Baron 12 on Wine, assuming Wine is properly configured.
# If Bridge Baron 12 is already installed, it launches the application.
# If Bridge Baron 12 is not installed, it guides the user through the installation process.

# Change to the script's own directory so $PWD-relative paths work
cd "$(dirname "${BASH_SOURCE[0]}")"

# Clear the terminal
clear

# Set Wine prefix directory
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
INSTALL_DIR="$PWD/INSTALL"
# Set Windows 98 mode silently (no GUI)
mkdir -p "$WINEPREFIX"
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d win98 /f &>/dev/null

# Check if Bridge Baron 12 is already installed
if [ -f "$WINEPREFIX/Bridge Baron/Baron.exe" ]; then
    # If installed, change directory and run Bridge Baron 12
    cd "$WINEPREFIX/Bridge Baron"
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    # Snapshot existing PPL files before launching
    _bb12_snapshot_time=$(date +%s)
    wine Baron.exe 2>/dev/null 1>/dev/null
    clear

    # Convert any new/modified .ppl files to .bdl in afterGameReport
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    FRI_DIR="$(dirname "$SCRIPT_DIR")"
    REPORT_DIR="$FRI_DIR/afterGameReport"
    HARNESS_DIR="$FRI_DIR/guiHarness"
    mkdir -p "$REPORT_DIR"
    while IFS= read -r -d '' ppl_file; do
        fmod=$(stat -c %Y "$ppl_file" 2>/dev/null) || continue
        [[ "$fmod" -le "$_bb12_snapshot_time" ]] && continue
        base=$(basename "$ppl_file" .ppl)
        [[ "$base" == "Sample" ]] && continue
        cp "$ppl_file" "$REPORT_DIR/${base}.ppl"
        if [[ -f "$HARNESS_DIR/ppl_to_pbn.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import ppl_to_pbn
bdl = ppl_to_pbn.ppl_to_bdl('$REPORT_DIR/${base}.ppl')
with open('$REPORT_DIR/${base}.bdl', 'w') as f:
    f.write(bdl)
print('  Converted ${base}.ppl -> ${base}.bdl')
" 2>/dev/null && true
        fi
    done < <(find "$WINEPREFIX/Bridge Baron" -maxdepth 1 -name "*.ppl" -type f -print0 2>/dev/null)

    exit 0
fi

# Check if installation file exists
if [ ! -f "$INSTALL_DIR/Bridge-Baron-12_Win_EN.zip" ]; then
    # If installation file not found, provide instructions for downloading and placing the file
    printf "Bridge-Baron-12_Win_EN.zip file not found in $INSTALL_DIR\n\nFrom \n\nhttps://www.myabandonware.com/game/bridge-baron-12-f44#download\n\nDownload this file:\n\nBridge-Baron-12_Win_EN.zip\n\nPlace this file in the $INSTALL_DIR directory,\n\nthen run this script again.\n\n\n"
    exit 0
fi

# Move the installation file to the Wine prefix directory and unzip it
mv "$INSTALL_DIR/Bridge-Baron-12_Win_EN.zip" "$WINEPREFIX"
cd "$WINEPREFIX"
unzip Bridge-Baron-12_Win_EN.zip 2>/dev/null 1>/dev/null

# Provide instructions for configuring Wine
#clear
#printf "In the wine configuration dialog box select Windows 98 for the Windows version,\nthen in the graphics tab select virtual desktop, and enter a screen resolution, such as 800x600.\nDeselect allow the window manager to decorate the windows.\n\nPress any key to continue.\n\n\n"
#read replyString
# Set Windows 98 mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d win98 /f &>/dev/null

# Inform user about successful installation
clear
printf "\nBridge Baron 12 installed successfully.  Run this script again to play.\n\n"
exit 0

