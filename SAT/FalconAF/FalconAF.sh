#!/bin/bash
# Script Outline:
#
# This script checks if FalconAF is installed. If not, it looks for the mounted FalconAF iso for installation.
# If the iso is found, it proceeds with the installation. If not, it prompts the user to mount the iso.
# After installation, or if FalconAF is already installed, it launches FalconAF.

# Define variables for directory paths (anchored to this script's location,
# not $PWD — the launcher runs game scripts from the day directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ISO_MNT_DIR="$SCRIPT_DIR/isoMnt"
export INSTALL_DIR="$SCRIPT_DIR/INSTALL"
export WINEPREFIX="$SCRIPT_DIR/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


export FALCON_EXE_PATH="$WINEPREFIX/drive_c/Program Files/Lead Pursuit/Battlefield Operations/FalconAF.exe"

# Check if FalconAF is installed
if [ ! -f "$FALCON_EXE_PATH" ]; then
    # Auto-mount FalconAF ISO if available but not yet mounted
    if [ ! -f "$ISO_MNT_DIR/Setup.exe" ] && [ -f "$INSTALL_DIR/FalconAF.iso" ]; then
        echo "Mounting FalconAF ISO (requires sudo)..."
        mkdir -p "$ISO_MNT_DIR"
        sudo mount -o loop "$INSTALL_DIR/FalconAF.iso" "$ISO_MNT_DIR"
    fi

    # Check if FalconAF iso is mounted
    if [ -f "$ISO_MNT_DIR/Setup.exe" ]; then
        clear
        echo ""
        echo "Installing using mounted FalconAF iso ..."
        echo ""
        echo "If asked whether to install wine-mono package, select Cancel."
        echo "When prompted for Setup Type, select Install"
        echo "Before entering 3D view, check that SETUP/GRAPHICS/VIDEO MODE is set to Direct3D HAL"
        echo ""
        
        # Install FalconAF
        wine "$ISO_MNT_DIR/Setup.exe" 2>/dev/null 1>/dev/null
        cp "$INSTALL_DIR/FalconAF/display.dsp" "$WINEPREFIX/drive_c/Program Files/Lead Pursuit/Battlefield Operations/config"
        cp "$INSTALL_DIR/FalconAF/Viper."* "$WINEPREFIX/drive_c/Program Files/Lead Pursuit/Battlefield Operations/config"
        cp "$INSTALL_DIR/FalconAF/global.cfg" "$WINEPREFIX/drive_c/Program Files/Lead Pursuit/Battlefield Operations"
        cp "$INSTALL_DIR/FalconAF/BFOpslog.txt" "$WINEPREFIX/drive_c/Program Files/Lead Pursuit/Battlefield Operations"
    else
        echo ""
        echo "FalconAF is not installed, and the FalconAF iso is not mounted at $ISO_MNT_DIR for installation."
        echo ""
        mkdir -p "$ISO_MNT_DIR"
        echo "To install FalconAF, follow these 3 steps:"
        echo "1. download the iso from, e.g., https://www.myabandonware.com/game/falcon-4-0-allied-force-e53"
        echo "2. mount the iso to the $ISO_MNT_DIR directory via"
        echo "   sudo mount -o loop <path to iso>FalconAF.iso $ISO_MNT_DIR"
        echo "3. run this script again"
        echo ""
        exit 0
    fi
fi

# Launch FalconAF in virtual desktop (prevents black screen fullscreen capture)
# Mark game start so afterGamesReport only collects files from gameplay, not install
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
wine explorer /desktop=FalconAF,1024x768 "$FALCON_EXE_PATH" 2>/dev/null 1>/dev/null

