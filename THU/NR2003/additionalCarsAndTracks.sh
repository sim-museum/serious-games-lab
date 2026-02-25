#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment
setup_wine_runner() {
    local runner_name="lutris-6.21-6-x86_64"
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

if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner
fi

# Set Wine prefix
export WINEPREFIX="$PWD/WP"

# Check if NR2003 is installed
if [ ! -d "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season" ]; then
    clear
    printf "NR2003 not installed. Run:\n\n./NR2003.sh\n\nfirst to install it.\n\nThen run this script again if you want to install optional\n1960's cars and tracks.\n"
    exit 0
fi

# Inform user about optional downloads
clear
echo "Adding 1960's cars and tracks to NR2003."
printf "\n\nOptional: Download the 1970 Nurburgring at this link\n\nhttps://www.theuspits.com/files/n2003/tracks/n2003_nurburgring_1970_v1.0.exe\n\nand place it in the NR2003/INSTALL directory.\nDownload the 67 sports cars mod at this link:\n\nhttps://www.theuspits.com/files/n2003/mods/AD67_v1.0.exe\n\nand also add it to the NR2003/INSTALL directory.\nPress CONTROL C now, add the Nurburgring and sports cars,\nand run this script again to include them in the car/track upgrade\n\nPress CONTROL C, or any other key to continue.\n\n"
read replyString

# Extract additional cars and tracks
cd "$WINEPREFIX/../INSTALL"
tar xzf NR2003_additionalCarsAndTracks.tar.gz 2>/dev/null 1>/dev/null
cd NR2003_additionalCarsAndTracks

# Copy tracks to NR2003 directory
printf "\nTracks:\nBrands Hatch\nBridgehamption\nDundrod\nMonaco\nRouen\nWatkins Glen 1964\nZandervoort\n"
rsync -a tracks/ "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season/tracks/" 2>/dev/null 1>/dev/null

# Add Grand National 1963 cars
printf "\nAdding Grand National 1963 cars\n"
cp -r gn63 "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season/series/"

# Install optional components if available
cd "$WINEPREFIX/../INSTALL"
if [ -f n2003_nurburgring_1970_v1.0.exe ]; then
    echo "Adding Nurburgring track"
    wine n2003_nurburgring_1970_v1.0.exe 2>/dev/null 1>/dev/null
fi
if [ -f AD67_v1.0.exe ]; then
    printf "Adding 1967 sports cars\n"
    wine AD67_v1.0.exe 2>/dev/null 1>/dev/null
fi
