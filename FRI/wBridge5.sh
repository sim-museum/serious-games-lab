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
    # Snapshot existing PBN files before launching
    _wb5_snapshot_time=$(date +%s)
    wine "$WINEPREFIX/drive_c/wbridge5/Wbridge5.exe" 2>/dev/null 1>/dev/null
    clear

    # Convert any new/modified .pbn files to .bdl in afterGameReport
    FRI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPORT_DIR="$FRI_DIR/afterGameReport"
    HARNESS_DIR="$FRI_DIR/guiHarness"
    mkdir -p "$REPORT_DIR"
    while IFS= read -r -d '' pbn_file; do
        fmod=$(stat -c %Y "$pbn_file" 2>/dev/null) || continue
        [[ "$fmod" -le "$_wb5_snapshot_time" ]] && continue
        base=$(basename "$pbn_file" .pbn)
        [[ "$base" == "precedent" ]] && continue
        cp "$pbn_file" "$REPORT_DIR/${base}.pbn"
        if [[ -f "$HARNESS_DIR/bridge_harness.py" && -x "$HARNESS_DIR/venv/bin/python3" ]]; then
            PYTHONPATH="$HARNESS_DIR" "$HARNESS_DIR/venv/bin/python3" -c "
import bridge_harness as bh
bdl = bh.pbn_file_to_bdl('$REPORT_DIR/${base}.pbn', source_label='WB')
with open('$REPORT_DIR/${base}.bdl', 'w') as f:
    f.write(bdl)
print('  Converted ${base}.pbn -> ${base}.bdl')
" 2>/dev/null && true
        fi
    done < <(find "$WINEPREFIX/drive_c/wbridge5" "$FRI_DIR" -maxdepth 1 -name "*.pbn" -type f -print0 2>/dev/null)

    # Display exit message
    cat "$PWD/DOC/REFERENCE/exitMessageWbridge5.txt"
    echo ""; echo ""
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

