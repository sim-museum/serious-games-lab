#!/usr/bin/bash
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

export WINEPREFIX=$PWD/WP
if [ ! -d $WINEPREFIX/../INSTALL ]
then
        clear
        echo "$WINEPREFIX/../INSTALL not found.  Download the directory before proceeding."; echo ""
        echo "See the file 'additionalGames.txt' for information about where to download the"
        echo "INSTALL add-on package. Unpack this file into the INSTALL directory."
	echo "Then run this script again."
        exit 0
fi

if [ ! -f "$WINEPREFIX/drive_c/Program Files/rFactor/rFactor.exe" ]
then
        clear
	echo "Run rFactor.sh to install rFactor, then run this script again."
	exit 0
fi

clear
echo "Installing JR's rFactor AI improvement plugin v. 1.21"
echo "This prevents the AI from forcing you off the road or crashing into your car as if you weren't there."
echo "For best results, let the AI practice on a track for the complete practice session before racing."
echo "Set AI at 100% strength, 0% aggressiveness."
echo "This plugin is for offline racing against the AI only.  If racing online, remove this plugin via"; echo ""
echo "rm -rf \"$WINEPREFIX/drive_c/Program Files/rFactor/Plugins/rFJRPlugin\""
echo "rm \"$WINEPREFIX/drive_c/Program Files/rFactor/Plugins/rFJRPlugin.dll\""; echo ""
echo "After plugin installation, it may be harder to select buttons in rFactor.  Select near the top of the button."
echo "Make sure rFactor is set to run in a window via graphicsConfig_rFactor.sh"
echo ""

echo "Installing java runtime environment ..."
wine $WINEPREFIX/../INSTALL/jre-8u291-windows-i586.exe /s 2>/dev/null 1>/dev/null
echo "Installing AI improvement plugin v. 1.21"
rsync -a "$WINEPREFIX/../INSTALL/Plugins/"   "$WINEPREFIX/drive_c/Program Files/rFactor/Plugins/"
echo ""
