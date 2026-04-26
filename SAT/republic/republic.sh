#!/bin/bash
# Republic: The Revolution (2003) - Elixir Studios / Demis Hassabis
# GOG edition, runs via Wine with DXVK (D3D8 → Vulkan)

cd "$(dirname "${BASH_SOURCE[0]}")"

# --- Wine runner pin (lutris-fshack-7.2-x86_64, per config/wine_runners.csv) ---
# Republic is a 32-bit DX8 game using DXVK 2.4 (which requires wine >= 7.1).
# Ubuntu 26.04 ships wine 10 in wow64 mode and silently rejects WINEARCH=win32,
# so falling through to /usr/bin/wine creates no prefix and the launch no-ops.
RUNNER_NAME="lutris-fshack-7.2-x86_64"
RUNNER_DIR="$HOME/.local/share/lutris/runners/wine/$RUNNER_NAME"
if [[ ! -x "$RUNNER_DIR/bin/wine" ]]; then
    echo "ERROR: Lutris wine runner '$RUNNER_NAME' not installed at $RUNNER_DIR" >&2
    echo "       Install it: sudo $(cd ../.. && pwd)/install.sh" >&2
    exit 1
fi
export PATH="$RUNNER_DIR/bin:$PATH"
export WINE="$RUNNER_DIR/bin/wine"
export WINELOADER="$RUNNER_DIR/bin/wine"
export WINESERVER="$RUNNER_DIR/bin/wineserver"
export LD_LIBRARY_PATH="$RUNNER_DIR/lib64:$RUNNER_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WINEDLLPATH="$RUNNER_DIR/lib64/wine/x86_64-unix:$RUNNER_DIR/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"

INSTALLER="INSTALL/Republic-The-Revolution_Win_EN.exe"
GAME_DIR="game"
DXVK_VER="2.4"
DXVK_DIR="INSTALL/dxvk-${DXVK_VER}/x32"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
export WINEDLLOVERRIDES="d3d8,d3d9,dxgi=n,b"

# Find the game executable after extraction
find_exe() {
    GAME_EXE=$(find "$GAME_DIR" -iname "Republic.exe" -not -iname "*setup*" -not -iname "*unins*" 2>/dev/null | head -1)
    [ -n "$GAME_EXE" ] || return 1
    GAME_EXE_DIR="$(dirname "$GAME_EXE")"
}

# --- Already installed: just launch ---
if find_exe 2>/dev/null && [ -d "$WINEPREFIX" ]; then
    cd "$GAME_EXE_DIR"
    [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
    # NOTE: no /desktop= here. Republic's launcher/menu windows position
    # themselves using GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN), so inside
    # a 1024x768 virtual desktop they get drawn at X>1920 (off the visible
    # area) and the desktop appears black. Letting them land on the host
    # display puts them where the user can actually see and click them.
    wine Republic.exe
    wineserver -k
    exit 0
fi

# --- First run: extract, configure, launch ---

# Check for GOG installer
if [ ! -f "$INSTALLER" ]; then
    echo "ERROR: Republic installer not found at $INSTALLER"
    echo ""
    echo "Place sglBinaries_2 in ~/sgl/downloads/ and run:"
    echo "  sudo ./install.sh"
    exit 1
fi

# Check dependencies
for cmd in wine innoextract curl; do
    if ! command -v "$cmd" >/dev/null; then
        echo "ERROR: $cmd not found. Install with: sudo apt install $cmd"
        exit 1
    fi
done

# Extract GOG installer
if [ ! -d "$GAME_DIR" ]; then
    echo "Extracting Republic: The Revolution..."
    mkdir -p "$GAME_DIR"
    innoextract -d "$GAME_DIR" "$INSTALLER"
fi

find_exe || { echo "ERROR: Could not find Republic.exe after extraction"; exit 1; }

# Download DXVK if needed
if [ ! -f "$DXVK_DIR/d3d8.dll" ]; then
    echo "Downloading DXVK ${DXVK_VER}..."
    mkdir -p INSTALL
    curl -sL "https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VER}/dxvk-${DXVK_VER}.tar.gz" \
        -o "INSTALL/dxvk-${DXVK_VER}.tar.gz"
    tar xzf "INSTALL/dxvk-${DXVK_VER}.tar.gz" -C INSTALL/
    rm -f "INSTALL/dxvk-${DXVK_VER}.tar.gz"
fi

# Install DXVK DLLs into game directory
cp "$DXVK_DIR/d3d8.dll" "$GAME_EXE_DIR/"
cp "$DXVK_DIR/d3d9.dll" "$GAME_EXE_DIR/"
cp "$DXVK_DIR/dxgi.dll" "$GAME_EXE_DIR/"

# Create DXVK config to force windowed mode (fixes mouse input)
cat > "$GAME_EXE_DIR/dxvk.conf" << 'DXVKEOF'
d3d9.forceWindowed = True
DXVKEOF

# Create Wine prefix
echo "Creating Wine prefix..."
wineboot --init
wineserver -w
wine reg add "HKCU\\Software\\Wine" /v Version /t REG_SZ /d winxp /f

# Launch (no /desktop= — see comment in the already-installed branch above)
cd "$GAME_EXE_DIR"
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
wine Republic.exe
