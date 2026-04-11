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
    # WINEPREFIX was set from $PWD before cd to Wine prefix, so derive paths from it
    BB12_DIR="$(dirname "$WINEPREFIX")"
    FRI_DIR="$(dirname "$BB12_DIR")"
    REPORT_DIR="$FRI_DIR/afterGameReport"
    HARNESS_DIR="$FRI_DIR/guiHarness"

    # Find the launcher's timestamped report dir (most recent bb12 subdir)
    _bb12_dest=""
    if [[ -d "$REPORT_DIR" ]]; then
        _bb12_dest=$(find "$REPORT_DIR" -mindepth 1 -maxdepth 1 -type d -name "*_bb12" \
                         -printf '%T@ %p\n' 2>/dev/null \
                     | sort -rn | head -1 | cut -d' ' -f2-)
    fi
    if [[ -z "$_bb12_dest" || ! -d "$_bb12_dest" ]]; then
        _bb12_dest="$REPORT_DIR/$(date '+%y%m%d_%H%M')_bb12"
    fi
    mkdir -p "$_bb12_dest"

    # Search Wine prefix, FRI dir, and the report dir for new .ppl files
    _bb12_last_pbn=""
    while IFS= read -r -d '' ppl_file; do
        fmod=$(stat -c %Y "$ppl_file" 2>/dev/null) || continue
        [[ "$fmod" -lt "$_bb12_snapshot_time" ]] && continue
        base=$(basename "$ppl_file" .ppl)
        [[ "$base" == "Sample" ]] && continue
        # Copy to report dir if not already there
        if [[ "$(dirname "$ppl_file")" != "$_bb12_dest" ]]; then
            cp "$ppl_file" "$_bb12_dest/${base}.ppl"
        fi
        # Convert to BDL and PBN
        if [[ -f "$HARNESS_DIR/ppl_to_pbn.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import ppl_to_pbn
bdl = ppl_to_pbn.ppl_to_bdl('$_bb12_dest/${base}.ppl')
with open('$_bb12_dest/${base}.bdl', 'w') as f:
    f.write(bdl)
pbn = ppl_to_pbn.ppl_to_pbn('$_bb12_dest/${base}.ppl')
with open('$_bb12_dest/${base}.pbn', 'w') as f:
    f.write(pbn)
print('  Converted ${base}.ppl -> ${base}.bdl + ${base}.pbn')
" 2>/dev/null && _bb12_last_pbn="$_bb12_dest/${base}.pbn" || true
        fi
    done < <(find "$WINEPREFIX/Bridge Baron" "$FRI_DIR" "$FRI_DIR/bb12" "$REPORT_DIR" "$_bb12_dest" \
                 -maxdepth 1 -name "*.ppl" -type f -print0 2>/dev/null)

    # Offer Q-Plus comparison workflow
    if [[ -n "$_bb12_last_pbn" && -f "$HARNESS_DIR/bridge_harness.py" && -x "$HARNESS_DIR/venv/bin/python" ]]; then
        # Q-Plus uses FRI/WP (shared Wine prefix with other FRI bridge games)
        FRI_WP="$FRI_DIR/WP"
        QBRIDGE_DIR=""
        [[ -d "$FRI_WP/drive_c/games/qbridge17" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge17"
        [[ -z "$QBRIDGE_DIR" && -d "$FRI_WP/drive_c/games/qbridge15" ]] && QBRIDGE_DIR="$FRI_WP/drive_c/games/qbridge15"

        if [[ -n "$QBRIDGE_DIR" ]]; then
            echo ""
            read -rp "Compare this hand with Q-Plus Bridge? (y/N): " _bb12_compare
            if [[ "$_bb12_compare" =~ ^[Yy]$ ]]; then
                echo "Launching Q-Plus Bridge and GUI Harness..."
                echo "Use the Comparison Workflow tab (source is pre-loaded from Bridge Baron 12)."
                echo "  1. Open Q-Plus → Own Deals → Enter, then click 'Enter into Q-Plus'"
                echo "  2. Play the hand in Q-Plus — do NOT exit Q-Plus yet"
                echo "  3. In harness: click 'Auto-detect latest' to find Q-Plus log"
                echo "  4. In harness: click 'Convert & copy' to save and annotate with Claude"
                echo "  5. Exit Q-Plus"
                echo ""

                # Launch harness with source pre-loaded (background)
                (
                    cd "$HARNESS_DIR"
                    source venv/bin/activate
                    python bridge_harness.py --source "$_bb12_last_pbn" --game bb12 2>/dev/null
                ) &
                _harness_pid=$!

                # Launch Q-Plus (foreground — blocks until user exits)
                export WINEPREFIX="$FRI_WP"
                export WINEARCH=win32
                wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
                cd "$QBRIDGE_DIR"
                wine QBRIDGE.EXE 2>/dev/null 1>/dev/null
                cd "$BB12_DIR"

                # Wait for harness to complete (user may still be doing steps 3-4)
                if kill -0 "$_harness_pid" 2>/dev/null; then
                    echo ""
                    echo "Waiting for GUI Harness to finish..."
                    echo "(Complete steps 3-4 in the harness, then close it)"
                    wait "$_harness_pid" 2>/dev/null
                fi
            fi
        fi
    fi

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

