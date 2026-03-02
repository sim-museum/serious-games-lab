# Script Outline:
# 1. Set Wine prefix directory.
# 2. Check if Falcon BMS 4.35 is already installed, if yes, start it.
# 3. Check Wine version, if it's 6.0, notify the user.
# 4. Provide instructions if Falcon4 directory is missing.
# 5. Notify user about the Weapon Delivery Planner utility.
# 6. Check and move Falcon BMS setup file to installation directory.
# 7. Unpack Falcon BMS setup file.
# 8. Install Falcon BMS 4.35.
# 9. Copy configuration files.
# 10. Provide final instructions.

#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set the Wine prefix directory
export WINEPREFIX="$PWD/WP"

# Esync/Fsync for thread sync
export WINEESYNC=1
export WINEFSYNC=1
# Point DXVK at the correct Vulkan ICD for the available GPU
if [ -f /usr/share/vulkan/icd.d/nvidia_icd.json ]; then
    export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
elif [ -f /usr/share/vulkan/icd.d/intel_icd.x86_64.json ]; then
    export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/intel_icd.x86_64.json
fi

# Define common directory paths for readability
export INSTALL_DIR="$PWD/INSTALL"
export FALCON_DIR="$WINEPREFIX/drive_c/Falcon BMS 4.35"

# Check if Falcon BMS 4.35 is already installed
if [ -d "$FALCON_DIR" ]; then
    cd "$FALCON_DIR"
    clear
    echo "Starting Falcon BMS 4.35"
    echo ""

    # Try DXVK 2.x first, fall back to DXVK-Sarek if GPU lacks Vulkan 1.3
    if [ ! -f "$WINEPREFIX/.dxvk_sarek" ]; then
        wine Launcher.exe -nomovie 2>"$WINEPREFIX/.dxvk_log"
        if grep -q "No adapters found\|maintenance5\|DXGIFactory" "$WINEPREFIX/.dxvk_log"; then
            wineserver -k 2>/dev/null || true
            echo "DXVK 2.x not supported on this GPU. Installing DXVK-Sarek fallback..."
            sarek_ver="v1.11.0"
            sarek_tar="/tmp/dxvk-sarek-${sarek_ver}.tar.gz"
            if [ ! -f "$sarek_tar" ]; then
                gh release download "$sarek_ver" -R pythonlover02/DXVK-Sarek \
                    -p "dxvk-sarek-${sarek_ver}.tar.gz" -D /tmp 2>/dev/null
            fi
            sarek_dir="/tmp/dxvk-sarek-${sarek_ver#v}"
            [ -d "$sarek_dir" ] || tar xzf "$sarek_tar" -C /tmp
            cp "$sarek_dir/x64/d3d9.dll" "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x64/dxgi.dll" "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x64/d3d11.dll" "$WINEPREFIX/drive_c/windows/system32/"
            cp "$sarek_dir/x64/d3d10core.dll" "$WINEPREFIX/drive_c/windows/system32/"
            touch "$WINEPREFIX/.dxvk_sarek"
            echo "DXVK-Sarek installed. Launching BMS..."
            wine Launcher.exe -nomovie 2>/dev/null
        fi
    else
        wine Launcher.exe -nomovie 2>/dev/null
    fi
    rm -f "$WINEPREFIX/.dxvk_log"
    exit 0
fi

# Check Wine version, if it's 6.0, notify the user to upgrade
if wine --version | grep "wine-6.0"; then
    clear
    printf "Version 6.0 of Wine detected.\nFalcon BMS 4.35 requires Wine version 7 or greater.\n\nFrom the esports-for-engineers directory, run \n\n./wine_experimental.sh\n\nto install Wine 7.\n\nThen run this script again.\n\n"
    exit 0
fi

if [ ! -d "$WINEPREFIX/drive_c/MicroProse/Falcon4" ]
then
   # Auto-mount falcon4Cd.iso if available but not yet mounted
   if [ ! -f "$INSTALL_DIR/isoMnt/Setup.exe" ] && [ -f "$INSTALL_DIR/falcon4Cd.iso" ]; then
       echo "Mounting Falcon 4 ISO (requires sudo)..."
       mkdir -p "$INSTALL_DIR/isoMnt"
       sudo mount -o loop "$INSTALL_DIR/falcon4Cd.iso" "$INSTALL_DIR/isoMnt"
   fi

   # If ISO is mounted, auto-install Falcon 4 base game
   if [ -f "$INSTALL_DIR/isoMnt/Setup.exe" ]; then
       clear
       echo "Installing base Falcon 4 from ISO..."
       echo "Click through the dialog boxes and ignore error messages."
       echo "When prompted to install Wine Mono, do not install it."
       echo ""
       echo "Press a key to begin installation..."
       read -r replyString
       cd "$INSTALL_DIR/isoMnt"
       wine Setup.exe 2>/dev/null 1>/dev/null
       cd "$INSTALL_DIR/../"
   elif [ -f "$INSTALL_DIR/falcon4Cd.iso" ]; then
       # ISO exists but not mounted - mount it and install
       clear
       echo "Falcon 4 ISO found. Mounting and installing base Falcon 4..."
       mkdir -p "$INSTALL_DIR/isoMnt"
       sudo mount -o loop "$INSTALL_DIR/falcon4Cd.iso" "$INSTALL_DIR/isoMnt"
       echo "Click through the dialog boxes and ignore error messages."
       echo "When prompted to install Wine Mono, do not install it."
       echo ""
       echo "Press a key to begin installation..."
       read -r replyString
       cd "$INSTALL_DIR/isoMnt"
       wine Setup.exe 2>/dev/null 1>/dev/null
       cd "$INSTALL_DIR/../"
   else
       # No ISO and no Falcon 4 installed
       clear
       echo "WP/drive_c/MicroProse/Falcon4/ directory not found."; echo ""
       echo "Before installing the BMS 4.35 free upgrades, you must install the original Falcon 4 game."; echo ""
       echo "Option A: Place the Falcon 4 ISO in the INSTALL directory and re-run this script:"
       echo "  cp falcon4Cd.iso $INSTALL_DIR/"
       echo "  (then re-run from the launcher - it will auto-mount and auto-install)"; echo ""
       echo "Option B: Buy Falcon 4.0 version 1.08 from GOG Games:"
       echo "  https://www.gog.com/game/falcon_collection"
       echo "  Copy the Falcon4 directory under WP/drive_c/MicroProse/"; echo ""
       echo "After installing Falcon 4, run this script again to upgrade to BMS 4.35."
       echo ""
       exit 1
   fi
fi


# Install DXVK 2.6.2 from Lutris runtime (2.7.1 requires VK_KHR_maintenance5
# which older NVIDIA drivers lack; winetricks would install the incompatible version)
DXVK_DIR="$HOME/.local/share/lutris/runtime/dxvk/v2.6.2"
if [ -d "$DXVK_DIR" ]; then
    clear
    echo "Installing DXVK 2.6.2..."
    cp "$DXVK_DIR/x64/"*.dll "$WINEPREFIX/drive_c/windows/system32/"
    cp "$DXVK_DIR/x32/"*.dll "$WINEPREFIX/drive_c/windows/syswow64/" 2>/dev/null
    # Set DLL overrides to native for DXVK
    wine reg add 'HKCU\Software\Wine\DllOverrides' /v dxgi /d native /f 2>/dev/null 1>/dev/null
    wine reg add 'HKCU\Software\Wine\DllOverrides' /v d3d11 /d native /f 2>/dev/null 1>/dev/null
    wine reg add 'HKCU\Software\Wine\DllOverrides' /v d3d10core /d native /f 2>/dev/null 1>/dev/null
    wine reg add 'HKCU\Software\Wine\DllOverrides' /v d3d9 /d native /f 2>/dev/null 1>/dev/null
    echo "DXVK 2.6.2 installed."
else
    clear
    echo "Installing DXVK via winetricks..."
    winetricks dxvk 2>/dev/null 1>/dev/null
    echo "DXVK installed."
fi
echo ""
echo "Note: the Weapon Delivery Planner utility is recommended."
echo "You can download this utility at http://www.weapondeliveryplanner.nl/"
echo ""

# Check if Falcon BMS setup file exists in installation directory
cd "$INSTALL_DIR"
if [ ! -f 'Falcon BMS 4.35 Setup (Full).zip' ]; then
    clear
    printf "Download this file:\n\n'Falcon BMS 4.35 Setup (Full).zip'\n\nfrom www.falcon-bms.com and put it in the "$WINEPREFIX"/../INSTALL directory.\nThen run this script again.\n\n"
    exit 0
fi

# Unpack Falcon BMS setup file
echo "Unpacking INSTALL/'Falcon BMS 4.35 Setup (Full).zip'"
unzip 'Falcon BMS 4.35 Setup (Full).zip'
cd "$INSTALL_DIR/Falcon BMS 4.35 Setup"

# Install Falcon BMS 4.35
echo "Installing BMS 4.35.3"
echo "To install, click through the following screens, accepting defaults to install."
echo "" 
echo "Installing BMS 4.35"
echo ""
echo "NOTE: A 'rundll32.exe - This application could not be started' error"
echo "may appear during installation. This is harmless - click No to dismiss it."
echo ""
wine Setup.exe 2>/dev/null 1>/dev/null

# Patch Falcon BMS.exe stack size from 1MB to 32MB (prevents stack overflow under Wine)
python3 -c "
import struct
exe = '$FALCON_DIR/Bin/x64/Falcon BMS.exe'
with open(exe, 'r+b') as f:
    f.seek(0x3C)
    pe_off = struct.unpack('<I', f.read(4))[0]
    f.seek(pe_off + 24 + 72)
    f.write(struct.pack('<Q', 32 * 1024 * 1024))
print('Patched Falcon BMS.exe stack to 32MB')
" 2>/dev/null

# Copy configuration files
cp "$INSTALL_DIR/Viper.ini" "$FALCON_DIR/User/Config"
cp "$INSTALL_DIR/Viper.lbk" "$FALCON_DIR/User/Config"
cp "$INSTALL_DIR/Viper.pop" "$FALCON_DIR/User/Config"
cp "$INSTALL_DIR/Viper.plc" "$FALCON_DIR/User/Config"

# Final instructions
echo "" 
clear
printf "Falcon BMS 4.35.3 installed.\n\nNext steps are:\n\n1. install optional add-on theaters; Iran/Iraq/Kuwait, Balkans, Israel, Somalia, Vietnam and Taiwan are available.\n\n2. run "$WINEPREFIX"/../INSTALL/bmsPatch.sh to patch the theaters.\n\n3. install optional utilities via "$WINEPREFIX"/../INSTALL/tacview.sh, "$WINEPREFIX"/../INSTALL/weaponDeliveryPlanner.sh and "$WINEPREFIX"/../INSTALL/missionCommander.sh\n4. If installed theaters are not listed in BMS, run\n
"$WINEPREFIX"/../runIfTheaterMissing.sh\n\n"

