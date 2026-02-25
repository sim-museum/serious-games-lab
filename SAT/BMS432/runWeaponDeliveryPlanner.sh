#!/bin/bash
#
# runWeaponDeliveryPlanner.sh - Installer/launcher for Weapon Delivery Planner
#
# WDP is a mission planning utility for Falcon BMS that generates maps,
# schedule sheets, and cockpit configuration views.
#
# NOTE: dotnet40 installation may hang the wineserver after completing.
# If the script appears stuck after "Installing .NET Framework 4 ...",
# run in another terminal:
#   ~/.local/share/lutris/runners/wine/lutris-5.7-x86_64/bin/wineserver -k
# Installation will then continue normally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export WINEPREFIX="$SCRIPT_DIR/WP"
export WINEARCH=win32

WDP_DIR="$WINEPREFIX/drive_c/Weapon Delivery Planner"
WDP_INSTALL="$SCRIPT_DIR/Weapon_Delivery_Planner_3.7.2.69"

# =====================================================================
# Already installed → launch
# =====================================================================
if [[ -f "$WDP_DIR/WeaponDeliveryPlanner.exe" ]]; then
    echo "Running Weapon Delivery Planner ..."
    cd "$WDP_DIR"
    wine WeaponDeliveryPlanner.exe 2>/dev/null
    exit 0
fi

# =====================================================================
# Not installed → install
# =====================================================================

if [[ ! -f "$WDP_INSTALL/setup.exe" ]]; then
    echo "Weapon Delivery Planner not found."
    echo ""
    echo "To install, download WDP from:"
    echo "  https://web.archive.org/web/20160330163200/http://weapondeliveryplanner.nl/files/wdp/Weapon_Delivery_Planner_3.7.2.69.7z"
    echo ""
    echo "Extract the .7z file and place the Weapon_Delivery_Planner_3.7.2.69"
    echo "directory under: $SCRIPT_DIR/"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "=== Weapon Delivery Planner installer ==="
echo ""

# --- Install winetricks dependencies needed by WDP ---
echo "[1/3] Installing .NET Framework 4 and database support ..."
echo ""
echo "  NOTE: dotnet40 may hang the wineserver after finishing."
echo "  If this step appears stuck, run in another terminal:"
echo "    ~/.local/share/lutris/runners/wine/lutris-5.7-x86_64/bin/wineserver -k"
echo ""
WINEDEBUG=-all winetricks -q dotnet40 2>/dev/null
WINEDEBUG=-all winetricks -q mdac28 mdac27 wsh57 jet40 2>/dev/null || true

# --- Install WDP ---
echo "[2/3] Installing Weapon Delivery Planner ..."
echo "  When prompted, enter the default callsign: Viper"
echo ""
cd "$WDP_INSTALL"
wine setup.exe 2>/dev/null || true

# --- Verify ---
if [[ -f "$WDP_DIR/WeaponDeliveryPlanner.exe" ]]; then
    echo ""
    echo "[3/3] Installation complete."
    echo "Run this script again to launch Weapon Delivery Planner."
else
    echo ""
    echo "WARNING: WeaponDeliveryPlanner.exe not found after install."
    echo "The installer may have failed. Try running this script again."
fi
echo ""
