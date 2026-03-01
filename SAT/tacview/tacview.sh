#!/bin/bash
# Tacview - Flight data recorder and analysis tool
# Standalone installation with its own Wine prefix (win64)

cd "$(dirname "${BASH_SOURCE[0]}")"

INSTALLER="$(ls INSTALL/Tacview*Setup*.exe 2>/dev/null | sort -V | tail -1)"
TACVIEW_EXE="$PWD/WP/drive_c/Program Files (x86)/Tacview/Tacview64.exe"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win64

# --- Install Wine Mono if missing (Tacview needs .NET) ---
if [ -d "$WINEPREFIX" ] && ! wine uninstaller --list 2>/dev/null | grep -qi mono; then
    echo "Installing Wine Mono (.NET support)..."
    winetricks -q mono 2>/dev/null
fi

# --- Already installed: just launch ---
if [ -f "$TACVIEW_EXE" ]; then
    echo "Starting Tacview..."
    echo "To open a recording, use File > Open inside Tacview."
    echo ""
    wine explorer /desktop=Tacview,1280x800 "$TACVIEW_EXE" "$@" 2>/dev/null
    exit 0
fi

# --- First run: install ---

if [ -z "$INSTALLER" ]; then
    echo "ERROR: Tacview installer not found in INSTALL/"
    echo ""
    echo "Place sglBinaries_7 in ~/sgl/downloads/ and run:"
    echo "  ./scripts/distribute_binaries.sh"
    exit 1
fi

echo "Creating 64-bit Wine prefix..."
wineboot --init 2>/dev/null
sleep 2

echo "Installing Tacview..."
echo "Follow the installer prompts to complete installation."
echo ""
wine "$INSTALLER" 2>/dev/null

if [ -f "$TACVIEW_EXE" ]; then
    echo ""
    echo "Tacview installed. Launching..."
    wine "$TACVIEW_EXE" "$@" 2>/dev/null
else
    echo ""
    echo "Installation may not have completed. Re-run this script to try again."
fi
