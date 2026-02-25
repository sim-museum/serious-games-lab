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

export WINEPREFIX=$PWD/WP

if [ ! -d "$WINEPREFIX/drive_c/Papyrus/NASCAR Racing 2003 Season" ]
then
	clear
	echo -e "Run ./NR2003.sh first, then run this script again.\n\n"
	exit 0
fi

if [ ! -f /usr/bin/winetricks ]
then
	clear
	echo -e "Install winetricks via\\nsudo install -y winetricks\n\nThen run this script again.\n\n"
	exit 0
fi

#install needed Visual Basic 6 runtime
winetricks vb6run 2>/dev/null 1>/dev/null

wine "$WINEPREFIX/../INSTALL/editorForNR2003/NR2003 Editor.exe" 2>/dev/null 1>/dev/null
