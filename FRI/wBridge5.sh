# Script Outline:
# 1. Check if Wbridge5 is already installed. If so, run the application.
# 2. If Wbridge5 is not installed, guide the user through the installation process.
# 3. Check Wine version for compatibility. If incompatible, display message and exit.
# 4. If Wine version is compatible, install Wbridge5 and display exit message.
#!/bin/bash

# This script installs and runs Wbridge5 on Wine, ensuring Wine version compatibility.
# If Wbridge5 is already installed, it launches the application.
# If Wbridge5 is not installed, it guides the user through the installation process.

# Check Wine version and installation
# $PWD/INSTALL/checkWineVersion.sh 2>/dev/null 1>/dev/null
# if [ $? -ne 0 ]; then
#     exit 1
# fi

# Set Wine prefix directory
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
INSTALL_DIR="$PWD/INSTALL"
# Set Windows XP mode silently (no GUI)
mkdir -p "$WINEPREFIX"
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


# Check if Wbridge5 is already installed
if [ -d "$WINEPREFIX/drive_c/wbridge5" ]; then
    # If installed, run Wbridge5
    # Mark game start so afterGameReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    FRI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="${REPO_ROOT:-$(cd "$FRI_DIR/.." && pwd)}"
    source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
    capture_marker_epoch
    # Snapshot existing PBN files before launching
    _wb5_snapshot_time=$(date +%s)
    wine "$WINEPREFIX/drive_c/wbridge5/Wbridge5.exe" 2>/dev/null 1>/dev/null
    clear

    # Convert any new/modified .pbn files to .bdl in afterGameReport
    REPORT_DIR="$FRI_DIR/afterGameReport"
    HARNESS_DIR="$FRI_DIR/guiHarness"

    # Subdir name derived from the marker's mtime so it matches the one
    # collect_after_game_report will derive, even if a concurrent game
    # has perturbed the marker.
    _wb5_dest="$(post_game_subdir "$FRI_DIR" wbridge5)"

    # Search Wine prefix and FRI dir for new .pbn files
    _wb5_last_pbn=""
    while IFS= read -r -d '' pbn_file; do
        fmod=$(stat -c %Y "$pbn_file" 2>/dev/null) || continue
        [[ "$fmod" -le "$_wb5_snapshot_time" ]] && continue
        base=$(basename "$pbn_file" .pbn)
        [[ "$base" == "precedent" ]] && continue
        # Copy to report dir if not already there
        if [[ "$(dirname "$pbn_file")" != "$_wb5_dest" ]]; then
            cp "$pbn_file" "$_wb5_dest/${base}.pbn"
        fi
        _wb5_last_pbn="$_wb5_dest/${base}.pbn"
        # Convert to BDL
        if [[ -f "$HARNESS_DIR/bridge_harness.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import bridge_harness as bh
bdl = bh.pbn_file_to_bdl('$_wb5_dest/${base}.pbn', source_label='WB')
with open('$_wb5_dest/${base}.bdl', 'w') as f:
    f.write(bdl)
print('  Converted ${base}.pbn -> ${base}.bdl')
" 2>/dev/null && true
        fi
        # Add Claude annotation alongside the converted BDL.
        if [[ -f "$_wb5_dest/${base}.bdl" && -x "$FRI_DIR/claude_annotate_bridge_single.sh" ]]; then
            echo "Running Claude annotation on WBridge5 deal log..."
            bash "$FRI_DIR/claude_annotate_bridge_single.sh" \
                "$_wb5_dest/${base}.bdl" "$_wb5_dest/${base}_annotated.bdl"
        fi
    done < <(find "$WINEPREFIX/drive_c/wbridge5" "$FRI_DIR" "$_wb5_dest" \
                 -maxdepth 1 -name "*.pbn" -type f -print0 2>/dev/null)

    # Q-Plus gold-standard comparison flow.
    # Extract base-72 code from the last hand played, then auto-launch
    # Q-Plus Bridge (same wineprefix) + the GUI harness with the deal
    # pre-loaded so the user doesn't have to re-enter the hand.
    if [[ -n "$_wb5_last_pbn" && -f "$HARNESS_DIR/bridge_harness.py" \
          && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
        _wb5_b72=$(PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import bridge_harness as bh
print(bh.pbn_file_to_base72('$_wb5_last_pbn'))
" 2>/dev/null)

        QBRIDGE_DIR=""
        [[ -d "$WINEPREFIX/drive_c/games/qbridge17" ]] && QBRIDGE_DIR="$WINEPREFIX/drive_c/games/qbridge17"
        [[ -z "$QBRIDGE_DIR" && -d "$WINEPREFIX/drive_c/games/qbridge15" ]] && QBRIDGE_DIR="$WINEPREFIX/drive_c/games/qbridge15"

        if [[ -n "$_wb5_b72" ]]; then
            echo ""
            if [[ -n "$QBRIDGE_DIR" ]]; then
                echo "Launching Q-Plus Bridge + GUI Harness for comparison..."
                echo "  Hand pre-loaded (base-72): $_wb5_b72"
                (cd "$QBRIDGE_DIR" && wine QBRIDGE.EXE 2>/dev/null 1>/dev/null) &
            else
                echo "Q-Plus not installed; launching GUI Harness only."
                echo "  Hand pre-loaded (base-72): $_wb5_b72"
            fi
            (cd "$HARNESS_DIR" && \
                PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" \
                    bridge_harness.py --base72 "$_wb5_b72" --game wbridge5 \
                    2>/dev/null)
        fi
    fi

    # Display exit message
    cat "$PWD/DOC/REFERENCE/exitMessageWbridge5.txt"
    echo ""; echo ""
    restore_marker_epoch
    exit 0
else
    # Check Wine version for compatibility
    clear
    if wine --version | grep -q "wine-6.0"; then
        printf "Version 6.0 of wine detected.\nFor installation, Omar Sharif Bridge requires wine version 7 or greater.\n\nFrom the esports-for-engineers directory, run \n\n./wine-experimental.sh\n\nto install wine 7.\n\nThen run this script again.\n\n"
        exit 0
    fi

    # If Wbridge5 is not installed and Wine version is compatible, install it
    echo "Installing Wbridge5 for the first time; simply accept all defaults."
    echo ""
    echo "Install gecko when prompted."
    echo "this will cause online help, as well as file load and save, to work."; echo ""
    wine "$INSTALL_DIR/Wbridge5_setup.exe" 2>/dev/null 1>/dev/null
    clear
    # Display exit message
    cat "$PWD/DOC/REFERENCE/exitMessageWbridge5.txt"
    echo ""; echo ""   
    exit 0
fi

