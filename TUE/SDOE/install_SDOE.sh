# Script Outline:
# 1. Check if SDOE is already installed.
# 2. Move required files to INSTALL directory.
# 3. Check if installation files exist.
# 4. Provide instructions for Wine configuration and installation.
# 5. Begin installation process.
# 6. Script ends.

#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Pin Lutris wine runner if not already set up by the caller (WWI/WWII_SDOE.sh).
# Required on Ubuntu 26.04: system wine 10 in wow64 mode silently rejects
# WINEARCH=win32 and leaves the prefix empty — the installer then runs
# against nothing and produces no Sdemons.exe.  fshack-7.2 also dodges the
# DDraw 32→16 BPP refusal that crashes the game on entering 3D.
if [[ -z "${WINELOADER:-}" || "$WINELOADER" != *"/lutris/runners/wine/"* ]]; then
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
fi

# Set WINEPREFIX
export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
mkdir -p "$WINEPREFIX"

# Synchronously initialize the prefix before any other wine call.  Without
# this, `wine reg add` can return before wineserver finishes its implicit
# wineboot, racing subsequent calls.
wine wineboot --init >/dev/null 2>&1

# Set Windows 98 mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d win98 /f &>/dev/null

# Define variables for readability
export INSTALL_DIR="$PWD/INSTALL"

# Check if SDOE is already installed
if [ -f "$WINEPREFIX/drive_c/Program Files/Fighter Squadron/Sdemons.exe" ] && \
   [ -f "$WINEPREFIX/drive_c/Program Files/FS-WWI/Sdemons.exe" ]; then
    clear
    printf "SDOE already installed. Run ./WWI_SDOE.sh for the World War I aircraft or ./WWII_SDOE.sh for the World War II aircraft.\n\n  SDOE is a Windows 98 flight simulator known for its flight and damage models.\n\n"
    exit 0
elif [ -f "$WINEPREFIX/drive_c/Program Files/FS-WWI/Sdemons.exe" ]; then
    printf "SDOE WWII planes already installed. Run ./installSDOE.sh and install the WWI aircraft next.\n\n"
    exit 0
fi

# Check if installation files exist
if [ ! -f "$INSTALL_DIR/Fighter_Squadron_SDOE_DVD.iso" ]; then
    clear
    printf "Fighter Squadron: Screaming Demons Over Europe (SDOE) install files not found in the directory $INSTALL_DIR.\n\n"
    printf "Download the files from: https://www.myabandonware.com/game/fighter-squadron-the-screamin-demons-over-europe-evp#download\n"
    printf "Place these files in the TUE/FighterSquadron/INSTALL directory, then run this script again.\n\n"
    exit 0
elif [ ! -f "$INSTALL_DIR/isoMnt/FILES/SDOEDVD.exe" ]; then
    clear
    printf "In the Wine Configuration Dialog that follows:\n1. In the application tab, select WINDOWS 98.\n2. In the graphics tab, deselect 'Allow the window manager to decorate the windows'.\n3. Select virtual Desktop with resolution of AT LEAST 1024x768, otherwise the install dialog box will not fit on the screen.\n4. Then select OK to continue the installation.\n\nPress a key to continue.\n\n"
    read -r replyString
    WINEARCH=win32 winecfg 2>/dev/null 1>/dev/null

    # Auto-mount SDOE ISO if available
    if [ -f "$INSTALL_DIR/Fighter_Squadron_SDOE_DVD.iso" ]; then
        echo "Mounting SDOE ISO (requires sudo)..."
        mkdir -p "$INSTALL_DIR/isoMnt"
        sudo mount -o loop "$INSTALL_DIR/Fighter_Squadron_SDOE_DVD.iso" "$INSTALL_DIR/isoMnt" && echo "ISO mounted. Continuing installation..." || {
            printf "\nTo install Fighter Squadron, run the following command in a terminal:\n\nsudo mount -o loop $INSTALL_DIR/Fighter_Squadron_SDOE_DVD.iso $INSTALL_DIR/isoMnt\n\nThen run this script again.\n"
            exit 0
        }
    else
        printf "\nTo install Fighter Squadron, run the following command in a terminal:\n\nsudo mount -o loop $INSTALL_DIR/Fighter_Squadron_SDOE_DVD.iso $INSTALL_DIR/isoMnt\n\nThen run this script again.\n"
        exit 0
    fi
fi

# Unpack files and begin installation
if [ -f "$INSTALL_DIR/isoMnt/FILES/SDOEDVD.exe" ]; then
    cd "$INSTALL_DIR/isoMnt/FILES"
    clear
    printf "Fighter Squadron installation instructions:\n\n1. If asked whether to install Mono, do not install it.\n2. select \"Fighter Squadron: SDOE\"\n3. After installing, deselect fly. Select Exit.\n4. select \"Fighter Squadron: WWI\"\n5. select \"Quit\"\n6. follow the dialog box prompts to install the patch\n7. Click on the desktop icon to run WWI or WWII\n\nPress a key to begin installation.\n\n"
    read -r replyString
    wine "SDOEDVD.exe" 2>/dev/null 1>/dev/null
    wineserver -k 2>/dev/null
    cd "$INSTALL_DIR"
    wine fspatch150.exe 2>/dev/null 1>/dev/null
    wineserver -k 2>/dev/null

    # Disable virtual desktop (was needed for install dialog, not for gameplay)
    wine reg delete "HKCU\\Software\\Wine\\Explorer\\Desktops" /v Default /f 2>/dev/null 1>/dev/null
    wineserver -k 2>/dev/null

    printf "\n\nInstallation completed. Run ./WWI_SDOE.sh or ./WWII_SDOE.sh\n"
    exit 0
fi

