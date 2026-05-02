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
    BB12_DIR="$(dirname "$WINEPREFIX")"
    FRI_DIR="$(dirname "$BB12_DIR")"
    REPO_ROOT="${REPO_ROOT:-$(cd "$FRI_DIR/.." && pwd)}"
    source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
    capture_marker_epoch
    # Snapshot existing PPL files before launching
    _bb12_snapshot_time=$(date +%s)
    wine Baron.exe 2>/dev/null 1>/dev/null
    clear

    # Convert any new/modified .ppl files to .bdl in afterGameReport
    REPORT_DIR="$FRI_DIR/afterGameReport"
    HARNESS_DIR="$FRI_DIR/guiHarness"

    # Subdir derived from the marker's mtime so it matches what
    # collect_after_game_report will derive, even if a concurrent game
    # has perturbed the marker.
    _bb12_dest="$(post_game_subdir "$FRI_DIR" bb12)"

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
        # Add Claude annotation alongside the converted BDL.
        if [[ -f "$_bb12_dest/${base}.bdl" && -x "$FRI_DIR/claude_annotate_bridge_single.sh" ]]; then
            echo "Running Claude annotation on Bridge Baron deal log..."
            bash "$FRI_DIR/claude_annotate_bridge_single.sh" \
                "$_bb12_dest/${base}.bdl" "$_bb12_dest/${base}_annotated.bdl"
        fi
    done < <(find "$WINEPREFIX/Bridge Baron" "$FRI_DIR" "$FRI_DIR/bb12" "$REPORT_DIR" "$_bb12_dest" \
                 -maxdepth 1 -name "*.ppl" -type f -print0 2>/dev/null)

    # Q-Plus gold-standard comparison flow.
    # Extract base-72 code from the last hand played, then auto-launch
    # Q-Plus Bridge + the GUI harness with the deal pre-loaded so the
    # user doesn't have to re-enter the hand.  Q-Plus lives in a
    # separate wineprefix (FRI/WP) — override WINEPREFIX in the subshell.
    if [[ -n "$_bb12_last_pbn" && -f "$HARNESS_DIR/bridge_harness.py" \
          && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
        _bb12_b72=$(PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import bridge_harness as bh
print(bh.pbn_file_to_base72('$_bb12_last_pbn'))
" 2>/dev/null)

        QBRIDGE_DIR=""
        QPLUS_PREFIX="$FRI_DIR/WP"
        [[ -d "$QPLUS_PREFIX/drive_c/games/qbridge17" ]] && QBRIDGE_DIR="$QPLUS_PREFIX/drive_c/games/qbridge17"
        [[ -z "$QBRIDGE_DIR" && -d "$QPLUS_PREFIX/drive_c/games/qbridge15" ]] && QBRIDGE_DIR="$QPLUS_PREFIX/drive_c/games/qbridge15"

        if [[ -n "$_bb12_b72" ]]; then
            echo ""
            if [[ -n "$QBRIDGE_DIR" ]]; then
                echo "Launching Q-Plus Bridge + GUI Harness for comparison..."
                echo "  Hand pre-loaded (base-72): $_bb12_b72"
                (
                    export WINEPREFIX="$QPLUS_PREFIX"
                    cd "$QBRIDGE_DIR"
                    wine QBRIDGE.EXE 2>/dev/null 1>/dev/null
                ) &
            else
                echo "Q-Plus not installed; launching GUI Harness only."
                echo "  Hand pre-loaded (base-72): $_bb12_b72"
            fi
            (cd "$HARNESS_DIR" && \
                PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" \
                    bridge_harness.py --base72 "$_bb12_b72" --game bb12 \
                    2>/dev/null)
        fi
    fi

    restore_marker_epoch
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

