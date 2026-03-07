#!/bin/bash
#
# BMS432.sh - Installer/launcher for Falcon BMS 4.32 with Balkans & Kuwait theaters
#
# Installs from original files:
#   - Falcon BMS 4.32 Setup (with Updates 1-7)
#   - Balkans 3.0 theater
#   - Kuwait theater (Add-On, copied directly)
#   - falcon4.exe (required by installer, not by the game itself)
#
# Uses system wine (no GE-Proton, no DXVK — BMS 4.32 uses DirectX 9
# natively and does not benefit from DXVK translation).
#
# Required files in INSTALL/:
#   Falcon BMS 4.32 Setup Upd. 1-7/Setup.exe
#   Balkans_3.0_setup.exe
#   Add-On Kuwait/
#   kuwaitLink/
#   falcon4.exe
#   Viper.ini

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export WINEPREFIX="$SCRIPT_DIR/WP"
export WINEARCH=win32

GAME_DIR="$WINEPREFIX/drive_c/Falcon BMS 4.32"
INSTALL_DIR="$SCRIPT_DIR/INSTALL"

# Remove prefix if it has the wrong architecture (e.g. from sglBinaries)
if [[ -f "$WINEPREFIX/system.reg" ]]; then
    if grep -q '#arch=win64' "$WINEPREFIX/system.reg"; then
        echo "Removing win64 prefix (BMS 4.32 requires win32)..."
        rm -rf "$WINEPREFIX"
    fi
fi

# =====================================================================
# Already installed → launch
# =====================================================================
if [[ -d "$GAME_DIR" && -f "$GAME_DIR/Launcher.exe" ]]; then
    echo "Starting Falcon BMS 4.32 ..."
    cd "$GAME_DIR"
    wine explorer /desktop=BMS432,1024x768 Launcher.exe -window 2>/dev/null
    exit 0
fi

# =====================================================================
# Not installed → install from original files
# =====================================================================

echo "=== Falcon BMS 4.32 installer ==="
echo ""

# --- Verify install files ---
if [[ ! -f "$INSTALL_DIR/Falcon BMS 4.32 Setup Upd. 1-7/Setup.exe" ]]; then
    echo "ERROR: BMS installer not found."
    echo "Expected: $INSTALL_DIR/Falcon BMS 4.32 Setup Upd. 1-7/Setup.exe"
    echo ""
    echo "Place sglBinaries_2 in ~/sgl/downloads/ and run: sudo ./install.sh"
    exit 1
fi

# --- Step 1: Create/update Wine prefix ---
echo "[1/6] Creating Wine prefix ..."
WINEDEBUG=-all wineboot -u 2>/dev/null || true

# --- Step 2: Install winetricks dependencies ---
echo "[2/6] Installing winetricks dependencies ..."
# vcrun2015 is needed by BMS.  dotnet40 is deferred to the Weapon
# Delivery Planner install — it hangs the wineserver on Wine 5.7
# and requires a manual wineserver -k to continue.
WINEDEBUG=-all winetricks -q remove_mono 2>/dev/null || true
WINEDEBUG=-all winetricks -q vcrun2015 winxp 2>/dev/null || true

# --- Step 3: Install Falcon BMS 4.32 ---
echo "[3/6] Installing Falcon BMS 4.32 ..."
echo "  The BMS installer will open. Accept defaults to install."
echo "  Install directory: C:\\Falcon BMS 4.32"
echo ""
# falcon4.exe must be findable for the installer's ownership check
cp "$INSTALL_DIR/falcon4.exe" "$WINEPREFIX/drive_c/"

cd "$INSTALL_DIR/Falcon BMS 4.32 Setup Upd. 1-7"
wine Setup.exe 2>/dev/null || true

if [[ ! -d "$GAME_DIR" ]]; then
    echo ""
    echo "ERROR: BMS 4.32 installation directory not found after installer."
    echo "The installer may have failed. Try running it again."
    exit 1
fi

# --- Step 4: Install Balkans theater ---
echo ""
echo "[4/6] Installing Balkans theater ..."
echo "  The Balkans installer will open. Accept defaults."
echo ""
cd "$INSTALL_DIR"
wine Balkans_3.0_setup.exe 2>/dev/null || true

# --- Step 5: Install Kuwait theater ---
echo "[5/6] Installing Kuwait theater ..."
cp -R "$INSTALL_DIR/Add-On Kuwait" "$GAME_DIR/Data/"
cp "$INSTALL_DIR/kuwaitLink/"* "$GAME_DIR/Data/Terrdata/theaterdefinition/"

# --- Step 6: Configure ---
echo "[6/6] Configuring ..."
# Initialize cockpit settings (callsign: Viper)
mkdir -p "$GAME_DIR/User/Config"
cp "$INSTALL_DIR/Viper.ini" "$GAME_DIR/User/Config/" 2>/dev/null || true

echo ""
echo "=== Installation complete ==="
echo ""
echo "Falcon BMS 4.32 installed with Balkans and Kuwait theaters."
echo "Run this script again to play."
echo ""
