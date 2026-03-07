#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment
setup_wine_runner() {
    local runner_name="$1"
    local runner_dir="$HOME/.local/share/lutris/runners/wine/$runner_name"
    if [[ -d "$runner_dir" && -x "$runner_dir/bin/wine" ]]; then
        export PATH="$runner_dir/bin:$PATH"
        export WINE="$runner_dir/bin/wine"
        export WINELOADER="$runner_dir/bin/wine"
        export WINESERVER="$runner_dir/bin/wineserver"
        export LD_LIBRARY_PATH="$runner_dir/lib64:$runner_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        export WINEDLLPATH="$runner_dir/lib64/wine/x86_64-unix:$runner_dir/lib/wine/i386-unix${WINEDLLPATH:+:$WINEDLLPATH}"
    fi
}

RUNNER_INSTALL="lutris-5.7-11-x86_64"
RUNNER_GAME="lutris-fshack-5.7-x86_64"

DGVOODOO_URL="https://github.com/dege-diosg/dgVoodoo2/releases/download/v2.86.5/dgVoodoo2_86_5.zip"

# Install dgVoodoo2 x86 DLLs into Wine system32 for DirectDraw/Direct3D support
install_dgvoodoo2() {
    local sys32="$WINEPREFIX/drive_c/windows/system32"
    local ddraw="$sys32/ddraw.dll"
    # Skip if already installed (Wine placeholder is ~5KB, dgVoodoo2 is ~250KB)
    if [ -f "$ddraw" ] && [ "$(stat -c%s "$ddraw")" -gt 50000 ]; then
        return 0
    fi
    echo "Installing dgVoodoo2 (DirectDraw/Direct3D wrapper)..."
    local tmpdir
    tmpdir=$(mktemp -d)
    if ! curl -sL -o "$tmpdir/dgvoodoo2.zip" "$DGVOODOO_URL"; then
        echo "Warning: failed to download dgVoodoo2. 3D acceleration may not work."
        rm -rf "$tmpdir"
        return 1
    fi
    if ! unzip -qo "$tmpdir/dgvoodoo2.zip" 'MS/x86/*' -d "$tmpdir"; then
        echo "Warning: failed to extract dgVoodoo2."
        rm -rf "$tmpdir"
        return 1
    fi
    cp "$tmpdir/MS/x86/DDraw.dll"  "$sys32/ddraw.dll"
    cp "$tmpdir/MS/x86/D3DImm.dll" "$sys32/d3dimm.dll"
    cp "$tmpdir/MS/x86/D3D8.dll"   "$sys32/d3d8.dll"
    cp "$tmpdir/MS/x86/D3D9.dll"   "$sys32/d3d9.dll"
    rm -rf "$tmpdir"
    # Set video memory size so FS9 detects GPU
    local vram
    vram=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null)
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\Direct3D" \
        /v VideoMemorySize /t REG_SZ /d "${vram:-2048}" /f &>/dev/null
    echo "dgVoodoo2 installed."
}

# Set up runner unless already configured by the launcher
if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner "$RUNNER_GAME"
fi

# Set Wine prefix
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


# Check if Flight Simulator executable exists
if [ -f "$WINEPREFIX/drive_c/Program Files/Microsoft Games/Flight Simulator 9/fs9.exe" ]; then
    install_dgvoodoo2
    clear

    # Disable NVIDIA threaded optimizations (causes issues with Wine)
    export __GL_THREADED_OPTIMIZATIONS=0

    # Disable winegstreamer to prevent crash in lesson/media pages
    # Use dgVoodoo2 native DLLs for DirectDraw/Direct3D + DXVK for D3D11->Vulkan
    export WINEDLLOVERRIDES="winegstreamer=d;ddraw,d3dimm,d3d8,d3d9,d3d11,dxgi=n,b"

    printf "If a blue title bar flashes, drag it a short distance to cause the run to proceed.\n\n"

    # Run Flight Simulator
    wine "$WINEPREFIX/drive_c/Program Files/Microsoft Games/Flight Simulator 9/fs9.exe" 2>/dev/null 1>/dev/null
    exit 0
fi

# Define commonly used directory path
export INSTALL_DIR="$WINEPREFIX/../INSTALL"

# Check if installation files exist
if [ ! -f "$INSTALL_DIR/Microsoft-Flight-Simulator-2004-A-Century-of-Flight_Win_EN_OEM-version-Updated-to-91.zip" ]; then
    clear
    printf "Microsoft Flight Simulator 2004: A Century of Flight\ninstall files not found in the directory TUE/FS9/INSTALL\n"
    echo ""
    echo "From this link:"; echo ""
    echo "https://www.myabandonware.com/game/microsoft-flight-simulator-2004-a-century-of-flight-g3u#download"
    echo ""
    echo "download the following file:"
    echo "Microsoft-Flight-Simulator-2004-A-Century-of-Flight_Win_EN_OEM-version-Updated-to-91.zip"
    echo ""
    echo "Place this file in the TUE/FS9/INSTALL directory."
    echo ""
    echo "Then run this script again."
    echo ""
    exit 0
fi

# Check if setup executable exists
if [ ! -f "$INSTALL_DIR/isoMnt/Setup.Exe" ]; then
    # Use older runner for installation (InstallShield compatibility)
    setup_wine_runner "$RUNNER_INSTALL"
    clear

    printf "If a blue title bar flashes, drag it a short distance to cause the run to proceed.\n\nIn the Wine Configuration Dialog that follows:\n1. In the application tab, to the right of \"Windows Version\" select Windows XP.\n2. In the graphics tab, deselect  'Allow the window manager to decorate the windows'\n3. Select virtual Desktop and enter your monitor resolution.\n4.Then select OK.\n\nPress a key to continue.\n\n"
    read replyString

    winecfg 2>/dev/null 1>/dev/null

    echo "Microsoft Flight Simulator 2004 (Flight Simulator 9) zipped iso file found in TUE/FS9/INSTALL"
    cd "$INSTALL_DIR"
    clear
    printf  "\nunpacking iso ...\n"
    unzip -o "Microsoft-Flight-Simulator-2004-A-Century-of-Flight_Win_EN_OEM-version-Updated-to-91.zip" 2>/dev/null 1>/dev/null

    # Auto-mount the ISO if available
    if [ -f "$INSTALL_DIR/Microsoft Flight Simulator 2004/FS_OEM.mdf" ]; then
        echo "Mounting FS9 ISO (requires sudo)..."
        mkdir -p "$INSTALL_DIR/isoMnt"
        sudo mount -o loop "$INSTALL_DIR/Microsoft Flight Simulator 2004/FS_OEM.mdf" "$INSTALL_DIR/isoMnt" && { echo "ISO mounted. Run this script again to install."; exit 0; } || {
            printf "Auto-mount failed. To install Flight Simulator 9, run the following command in a terminal:\n\nsudo mount -o loop \"$INSTALL_DIR/Microsoft Flight Simulator 2004/FS_OEM.mdf\" \"$INSTALL_DIR/isoMnt\"\n\nThen run this script again.\n"
            exit 0
        }
    else
        printf "To install Flight Simulator 9, run the following command in a terminal:\n\nsudo mount -o loop \"$INSTALL_DIR/Microsoft Flight Simulator 2004/FS_OEM.mdf\" \"$INSTALL_DIR/isoMnt\"\n\nThen run this script again.\n"
        exit 0
    fi
fi

# If setup executable exists, start installation
if [ -f "$INSTALL_DIR/isoMnt/Setup.Exe" ]; then
    # Use older runner for installation (InstallShield compatibility)
    setup_wine_runner "$RUNNER_INSTALL"
    cd "$INSTALL_DIR/isoMnt/"
    clear
    printf "If a blue title bar flashes, drag it a short distance to cause the run to proceed.\n\nFlight Simulator 9 installation instructions:\n\n1. If asked whether to install Mono, do not install it.\n2. Install. \n3. After installing, deselect fly.\nSelect Exit by clicking on the X at upper right.\n\nPress a key to begin installation.\n\n"


    read replyString
    wine "Setup.exe" 2>/dev/null 1>/dev/null

    # Wait for the installer to finish (wine returns early when InstallShield spawns a subprocess)
    wineserver -w 2>/dev/null

    # Post-install: extract scenery cab files and fix scenery.cfg paths
    # The OEM installer does a compact install that leaves scenery in cab files
    # and omits Local= paths (expecting the CD-ROM for Remote= access)
    local_game_dir="$WINEPREFIX/drive_c/Program Files/Microsoft Games/Flight Simulator 9"
    if [ -d "$local_game_dir/Scenery" ]; then
        echo "Extracting scenery cab files..."
        cd "$local_game_dir/Scenery"
        for cab in *.cab; do
            [ -f "$cab" ] || continue
            dir="${cab%.cab}"
            if [ ! -d "$dir" ]; then
                mkdir -p "$dir" && cabextract -q -d "$dir" "$cab"
            fi
        done

        # Also extract city scenery cabs from ISO if mounted
        if [ -d "$INSTALL_DIR/isoMnt/SCENERY/CITIES" ]; then
            for cab in "$INSTALL_DIR/isoMnt/SCENERY/CITIES/"*.cab; do
                [ -f "$cab" ] || continue
                dir="Cities/$(basename "${cab%.cab}")"
                if [ ! -d "$dir" ]; then
                    mkdir -p "$dir" && cabextract -q -d "$dir" "$cab"
                fi
            done
        fi

        # Fix scenery.cfg: add Local= paths for entries missing them
        cfg="$local_game_dir/scenery.cfg"
        if [ -f "$cfg" ] && grep -q '^\[Area\.001\]' "$cfg" && ! grep -A3 '^\[Area\.001\]' "$cfg" | grep -q '^Local='; then
            echo "Fixing scenery.cfg paths..."
            sed -i '/^\[Area\.001\]/{n;n;/^Layer=/i Local=Scenery\\World
}' "$cfg"
            sed -i '/^\[Area\.003\]/{n;/^Layer=/i Local=Scenery\\Afri
}' "$cfg"
            sed -i '/^\[Area\.004\]/{n;/^Layer=/i Local=Scenery\\Asia
}' "$cfg"
            sed -i '/^\[Area\.005\]/{n;/^Layer=/i Local=Scenery\\Aust
}' "$cfg"
            sed -i '/^\[Area\.011\]/{n;/^Layer=/i Local=Scenery\\Ocen
}' "$cfg"
            sed -i '/^\[Area\.012\]/{n;/^Layer=/i Local=Scenery\\Same
}' "$cfg"
            # Fix city entries missing Local= paths
            declare -A city_map=(
                ["013"]="Amsterd" ["014"]="Anchor" ["015"]="Atlanta" ["016"]="Chicago"
                ["019"]="Heathrow" ["020"]="Hongkong" ["021"]="Kittyhwk" ["022"]="Lasvegas"
                ["023"]="La" ["024"]="Miami" ["026"]="Niagara" ["028"]="Paris"
                ["029"]="Phoenix" ["030"]="Sanfran" ["033"]="Sydney" ["034"]="Tokyo"
            )
            for area in "${!city_map[@]}"; do
                dir="${city_map[$area]}"
                sed -i "/^\[Area\.${area}\]/{n;/^Layer=/i Local=Scenery\\\\Cities\\\\${dir}
}" "$cfg"
            done
        fi
        cd "$INSTALL_DIR/isoMnt/"
    fi

    install_dgvoodoo2

    printf "\n\nInstallation completed.  Run this script again to start fs9.  (Ignore missing font warnings). \n"
    exit 0
fi

