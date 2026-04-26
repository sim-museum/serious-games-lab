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

    # DXVK-Sarek for D3D9 acceleration. The actual game binary
    # (Bin/x86/Falcon BMS.exe) imports d3d9.dll + d3dx9_43.dll. wined3d
    # works fine but Sarek gives 2-5x higher draw-call throughput. Same
    # detection-by-content + curl-based install used in rFactor / bracelets
    # / BMS435 / CFL — gh CLI is NOT a hard dep and silently fails when
    # missing, so don't use it.
    if ! strings "$WINEPREFIX/drive_c/windows/system32/d3d9.dll" 2>/dev/null \
            | grep -q dxvk; then
        echo "Installing DXVK-Sarek for Vulkan acceleration..."
        sarek_ver="v1.11.0"
        sarek_tar="/tmp/dxvk-sarek-${sarek_ver}.tar.gz"
        sarek_url="https://github.com/pythonlover02/DXVK-Sarek/releases/download/${sarek_ver}/dxvk-sarek-${sarek_ver}.tar.gz"
        [ -s "$sarek_tar" ] || curl -sL -o "$sarek_tar" "$sarek_url"
        if [ -s "$sarek_tar" ]; then
            sarek_dir="/tmp/dxvk-sarek-${sarek_ver}"
            [ -d "$sarek_dir" ] || tar xzf "$sarek_tar" -C /tmp
            cp "$sarek_dir/x32/d3d9.dll"     "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x32/dxgi.dll"     "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x32/d3d11.dll"    "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x32/d3d10core.dll" "$WINEPREFIX/drive_c/windows/system32/" 2>/dev/null || true
            # Write all 4 overrides via a single regedit invocation; doing
            # them one-by-one with `wine reg add` races wineserver flush
            # and the values can fail to land.
            cat > /tmp/bms432_dxvk_overrides.reg <<'EOF'
REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"d3d9"="native"
"d3d10core"="native"
"d3d11"="native"
"dxgi"="native"
EOF
            wine regedit /S /tmp/bms432_dxvk_overrides.reg &>/dev/null
            wineserver -k 2>/dev/null
            sleep 1
        fi
        if ! strings "$WINEPREFIX/drive_c/windows/system32/d3d9.dll" 2>/dev/null \
                | grep -q dxvk; then
            echo "WARNING: DXVK-Sarek install did not land — BMS 4.32 will use slow wined3d."
        fi
    fi

    # Mark game start so afterGameReport only collects files from gameplay, not install
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
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
