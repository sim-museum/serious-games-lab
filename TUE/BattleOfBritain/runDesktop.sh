#!/bin/bash

# Launch Battle of Britain in a Wine virtual desktop (windowed on your desktop).
# FORCE_WINDOWED_MODE in bdg.txt crashes 3D under Wine, so we use Wine's own
# virtual desktop instead — the game thinks it's fullscreen while running in
# a desktop window.
#
# For true fullscreen (dual monitors), run ./runFullScreen.sh

cd "$(dirname "${BASH_SOURCE[0]}")"

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
export WINEDLLOVERRIDES="winegstreamer=d"
BOB_DIR="$WINEPREFIX/drive_c/Program Files/Rowan Software/Battle Of Britain"

if [[ ! -f "$BOB_DIR/bob.exe" ]]; then
    echo "Error: Battle of Britain not installed. Run ./battleOfBritain.sh first."
    exit 1
fi

# Ensure FORCE_WINDOWED_MODE is OFF (it crashes 3D under Wine)
sed -i 's/FORCE_WINDOWED_MODE=ON/FORCE_WINDOWED_MODE=OFF/' "$BOB_DIR/bdg.txt"

# Prevent Wine from grabbing keyboard/mouse exclusively in 3D mode
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v GrabFullscreen /t REG_SZ /d N /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v GrabPointer /t REG_SZ /d N /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\DirectInput" /v MouseWarpOverride /t REG_SZ /d disable /f &>/dev/null
wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v DXGrab /t REG_SZ /d N /f &>/dev/null

echo "Launching Battle of Britain in virtual desktop mode..."
wine explorer /desktop=BoB,1920x1080 "C:\\Program Files\\Rowan Software\\Battle Of Britain\\bob.exe" 2>/dev/null
