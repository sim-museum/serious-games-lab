#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment
setup_wine_runner() {
    local runner_name="lutris-fshack-7.2-x86_64"
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

SCRIPT_DIR="$PWD"
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
# Set Windows 7 mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d win7 /f &>/dev/null

# --- Already installed: launch rFactor ---
if [ -f "$WINEPREFIX/drive_c/Program Files/rFactor/rFactor.exe" ]; then
    cd "$WINEPREFIX/drive_c/Program Files/rFactor"
    wine rFactor.exe
    printf "\nrFactor Optional Scripts\n\nTelemetry:\n$SCRIPT_DIR/addTelemetryLoggerToRfactor.sh\n\nImprove AI:\n$SCRIPT_DIR/offlineAIimprovement_rFactor.sh\n\nConfigure Graphics:\n$SCRIPT_DIR/graphicsConfig_rFactor.sh\n\nTip: to become owner of all cars in a mod, type the code \"ISI_BABYFACTORY\" in\nthe chat window. (The chat window is at lower left on the screen just before\nyou enter the 3D view.)\n\n"
    exit 0
fi

# --- Not installed: check for install files ---

# Check if cars and tracks are present
if [ ! -d "$SCRIPT_DIR/INSTALL/newTracks" ]; then
    clear
    printf "rFactor cars and tracks not found in $SCRIPT_DIR/INSTALL.\n\n"
    printf "The INSTALL directory should contain newTracks, rF.iso, and car mod directories.\n\n"
    exit 0
fi

# Auto-mount rF.iso if available but not yet mounted
if [ ! -f "$SCRIPT_DIR/INSTALL/isoMnt/Setup.exe" ] && [ -f "$SCRIPT_DIR/INSTALL/rF.iso" ]; then
    printf "Mounting rFactor ISO. Enter sudo password if prompted.\n"
    mkdir -p "$SCRIPT_DIR/INSTALL/isoMnt"
    sudo mount -o loop "$SCRIPT_DIR/INSTALL/rF.iso" "$SCRIPT_DIR/INSTALL/isoMnt"
fi

if [ ! -f "$SCRIPT_DIR/INSTALL/isoMnt/Setup.exe" ]; then
    clear
    echo "rFactor is not installed, and the rFactor iso is not mounted at INSTALL/isoMnt."
    echo ""
    echo "Place rF.iso in the INSTALL directory and run this script again."
    echo ""
    exit 0
fi

# --- Install rFactor ---
clear
printf "Installing rFactor\n\n"

# Install DXVK via winetricks (sets up DLLs and overrides correctly)
printf "Installing DXVK via winetricks...\n"
winetricks dxvk 2>/dev/null 1>/dev/null

printf "\nIn the rFactor Video Setup screen, choose:\n"
printf "  Shader Level: Quality (DX9)\n"
printf "  Anti-Aliasing: Level 4\n"
printf "  Select the Windowed checkbox\n"
printf "  Leave the Resolution field blank\n\n"
printf "In Completing the rFactor Setup Wizard, unselect Run rFactor\n"
printf "so the script can proceed to install additional cars and tracks.\n\n"
printf "Press ENTER to begin installation ...\n"
read -r replyString

wine "$SCRIPT_DIR/INSTALL/isoMnt/Setup.exe" 2>/dev/null 1>/dev/null

# Copy rFactor executable (NoCD)
cp "$SCRIPT_DIR/INSTALL/rFactor.exe" "$WINEPREFIX/drive_c/Program Files/rFactor/" 2>/dev/null 1>/dev/null

# --- Install carsets ---
formula_e_dir="$SCRIPT_DIR/INSTALL/Bravo Formula E 2019-20 Mod/"
f1_1958_dir="$SCRIPT_DIR/INSTALL/F1 1958 by ORM - v4.35 COMPLETE/F1 1958 by ORM - v4.35 COMPLETE/"
f1_1958_noDir="$SCRIPT_DIR/INSTALL/F1 1958 by ORM - v4.35 COMPLETE/F1 1958 by ORM - v4.35 COMPLETE"
f1lr_mod_dir="$SCRIPT_DIR/INSTALL/F1LR_mod_V203/Mod/"
rfactor_dir="$WINEPREFIX/drive_c/Program Files/rFactor/"

printf "\nInstalling 2019 Formula E carset\n"
rsync -a "$formula_e_dir" "$rfactor_dir"

printf "\nInstalling 1958 carset\n"
# Fix case mismatch if present (some archives extract as "Gamedata" instead of "GameData")
if [ -d "$f1_1958_noDir/Gamedata" ] && [ ! -d "$f1_1958_noDir/GameData" ]; then
    mv "$f1_1958_noDir/Gamedata" "$f1_1958_noDir/GameData"
fi
rsync -a "$f1_1958_dir" "$rfactor_dir"

printf "\nInstalling 1967 carset\n"
rsync -a "$f1lr_mod_dir" "$rfactor_dir"

printf "\nInstalling 60's sportscars Historix1.9 (large: takes 4 minutes to load)\n"
rsync -a "$SCRIPT_DIR/INSTALL/Historix1.9/Historix/" "$rfactor_dir"

# --- Install tracks ---
printf "\nInstalling 60's tracks:\n"

SOURCE_DIR="$SCRIPT_DIR/INSTALL/newTracks/2"
SOURCE_OTHER_DIR="$SCRIPT_DIR/INSTALL/newTracks/"
DEST_DIR="$WINEPREFIX/drive_c/Program Files/rFactor/GameData/Locations"
SETUPS_DIR="$WINEPREFIX/drive_c/Program Files/rFactor/UserData/"

rsync -a "$SCRIPT_DIR/INSTALL/newTracks/FDsign Spa58 Rfactor/" "$WINEPREFIX/drive_c/Program Files/rFactor/GameData/"
rsync -a "$SOURCE_DIR/Aintree 1955 v1 by jpalesi/" "$rfactor_dir"
rsync -a "$SOURCE_DIR/Imola1960s_v1.0/GameData/" "$WINEPREFIX/drive_c/Program Files/rFactor/GameData/"

for track in "Brands Hatch 1950 v1_0 by Rodrrico" "Bugatti67" "Clermont65" \
             "60s Oulton Park v1_0 by philrob/60Oulton" "Monaco_1967_by_Fero/Monaco67" \
             "Nurburg67" "Reims67" "Riverside70" "Sebring1970_v1" "snett" \
             "Solitude_64" "Zeltweg" "Zandvoort67"; do
    printf "  %s\n" "$track"
    cp -R "$SOURCE_DIR/$track" "$DEST_DIR"
done

for track in "67panorama" "Avus1967_v1.0_by_ZWISS_for_rF/Avus1967" \
             "BremgartenGP_54" "Monza_1000km" "FDsign Spa58 Rfactor"; do
    printf "  %s\n" "$track"
    cp -R "$SOURCE_OTHER_DIR/$track" "$DEST_DIR"
done

printf "\nPlacing HistoricX setups in $WINEPREFIX/drive_c/Program Files/rFactor/UserData\n"
cp -R "$SCRIPT_DIR/INSTALL/HistorX 1.96 Club setups 2016/" "$SETUPS_DIR"

# Unmount ISO
sudo umount "$SCRIPT_DIR/INSTALL/isoMnt" 2>/dev/null

clear
printf "\nrFactor installed.\n\n"
printf "After rFactor starts, choose Customize.\n"
printf "In Customize/Player, choose customize player racing series.\n"
printf "Choose either '1958 Formula One World Championship' or\n"
printf "'F1 Legends Racing v2.03' (the 1967 carset)\n"
printf "In Customize/Vehicle choose a car and select 'buy car'\n"
printf "In Customize/Settings/Difficulty turn off automatic shifting and all other driver aids.\n"
printf "If the 3D view appears too dark, increase monitor brightness setting.\n\n"
printf "Run this script again to race.\n"
exit 0
