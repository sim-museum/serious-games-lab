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

# Set up runner unless already configured by the launcher
if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner
fi

# Set the Wine prefix directory
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32

# Check if game directory exists — launch the game
if [ -d "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season" ]; then
    cd "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season"
    wine NR2003.exe 2>/dev/null 1>/dev/null
    clear
    printf "NR2003 Optional Scripts:\n\n"
    printf "Add additional 1960's era cars and tracks:\n$WINEPREFIX/../additionalCarsAndTracks.sh\n\n"
    printf "Change NR2003 track parameters, AI, etc:\n$WINEPREFIX/../trackEditor.sh\n\n\n\n"
    printf "Tip: always run NR2003 with the same version of Wine\nthat was used to install it, to avoid an 'installation\nappears to be incorrect' error message.\n\n"
    exit 0
fi

# Check if installation files are missing
if [ ! -f "$WINEPREFIX/../INSTALL/NASCAR-Racing-2003-Season_Win_EN_ISO-Version.zip" ]; then
    clear
    echo "Nascar Racing 2003 install files not found in the directory THU/NR2003/INSTALL"
    echo ""
    echo "From this link:"; echo ""
    echo "https://www.myabandonware.com/game/nascar-racing-2003-season-cox#download"
    echo ""
    echo "download the following 4 files:"
    echo "1. NASCAR-Racing-2003-Season_Win_EN_ISO-Version.zip"
    echo "2. NASCAR-Racing-2003-Season_Fix_Win_EN_Fix-for-Version-1201.exe"
    echo "3. NASCAR-Racing-2003-Season_Patch_Win_EN_Patch-1201.exe"
    echo "4. NASCAR-Racing-2003-Season_NoCD_Win_EN.zip"
    echo ""
    echo "Place these files in the THU/NR2003/INSTALL directory."
    echo ""
    echo "Then run this script again."
    echo ""
    exit 0
fi

# Check if required files are missing
if [ ! -f "$WINEPREFIX/../INSTALL/NASCAR-Racing-2003-Season_Fix_Win_EN_Fix-for-Version-1201.exe" ]; then
    printf "INSTALL/NASCAR-Racing-2003-Season_Fix_Win_EN_Fix-for-Version-1201.exe missing\n\n"
    exit 0
fi
if [ ! -f "$WINEPREFIX/../INSTALL/NASCAR-Racing-2003-Season_NoCD_Win_EN.zip" ]; then
    printf "NASCAR-Racing-2003-Season_NoCD_Win_EN.zip missing\n\n"
    exit 0
fi
if [ ! -f "$WINEPREFIX/../INSTALL/NASCAR-Racing-2003-Season_Patch_Win_EN_Patch-1201.exe" ]; then
    printf "NASCAR-Racing-2003-Season_Patch_Win_EN_Patch-1201.exe missing\n\n"
    exit 0
fi

# Unpack required files if ISO doesn't exist yet
if [ ! -f "$WINEPREFIX/../INSTALL/NR2003.iso" ]; then
    clear
    echo "Unpacking files..."
    cd "$WINEPREFIX/../INSTALL"
    unzip -o NASCAR-Racing-2003-Season_Win_EN_ISO-Version.zip
    unzip -o NASCAR-Racing-2003-Season_NoCD_Win_EN.zip
    cd NASCAR_Racing_2003_Season_ISO
    bchunk Nascar_Racing_2003_Season.FLT.ShareReactor.BIN Nascar_Racing_2003_Season.FLT.ShareReactor.CUE NR2003.iso 2>/dev/null 1>/dev/null
    mv NR2003.iso01.iso "$WINEPREFIX/../INSTALL/NR2003.iso"
    cd "$WINEPREFIX/.."
fi

# Mount ISO if not already mounted
if [ ! -f "$WINEPREFIX/../isoMnt/autorun.exe" ]; then
    mkdir -p "$WINEPREFIX/../isoMnt"
    clear
    printf "Mounting ISO. Enter sudo password if prompted.\n"
    sudo mount -o loop "$WINEPREFIX/../INSTALL/NR2003.iso" "$WINEPREFIX/../isoMnt"
    if [ ! -f "$WINEPREFIX/../isoMnt/autorun.exe" ]; then
        printf "Failed to mount ISO.\n"
        exit 1
    fi
fi

# Initialize Wine prefix
clear
printf "Initializing Wine prefix...\n"
wineboot 2>/dev/null 1>/dev/null

# Install vcrun2003
printf "Installing Visual C++ 2003 runtime...\n"
winetricks vcrun2003 2>/dev/null 1>/dev/null

# Set Windows XP mode and virtual desktop
wine reg add "HKCU\\Software\\Wine\\Explorer\\Desktops" /v Default /t REG_SZ /d 1920x1080 /f 2>/dev/null 1>/dev/null
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

# Install NR2003
clear
printf "Installing NR2003\n\n"
printf "Select Install\n"
printf "Do not select Register or look for updates\n\n"
printf "When asked for a serial number, enter\nRAB2-RAB2-RAB2-RAB2-8869\n\n"
printf "Press ENTER to begin installation ...\n"
read -r replyString

cd "$WINEPREFIX/../isoMnt"
wine autorun.exe 2>/dev/null 1>/dev/null

# Install 1201 patch
clear
printf "\nPress ENTER to install the 1201 patch\n"
read -r replyString
cd "$WINEPREFIX/../INSTALL"
wine NASCAR-Racing-2003-Season_Patch_Win_EN_Patch-1201.exe 2>/dev/null 1>/dev/null

# Copy NoCD crack
cp "$WINEPREFIX/../INSTALL/Nascar_Racing_2003_Season_1201_NoCD/NR2003.exe" "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season"

# Install DXVK
printf "\nInstalling DXVK...\n"
winetricks dxvk 2>/dev/null 1>/dev/null

# Unmount ISO
sudo umount "$WINEPREFIX/../isoMnt" 2>/dev/null

printf "\nNascar Racing 2003 Season installed.\n\n"
printf "To install optional 1960's era cars and tracks in NR2003, run:\n"
printf "$WINEPREFIX/../additionalCarsAndTracks.sh\n\n"
printf "Run this script again to race.\n"
exit 0
