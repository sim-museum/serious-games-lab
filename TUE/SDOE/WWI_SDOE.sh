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

# Use system Wine (game works with wine-9.0)
# setup_wine_runner "lutris-fshack-5.7-x86_64"

export WINEPREFIX=$PWD/WP
export WINEARCH=win32

if [ -f "$WINEPREFIX/drive_c/Program Files/FS-WWI/Sdemons.exe" ]
then
	export WINEDLLOVERRIDES="winegstreamer=d"
	wine winecfg -v win98 2>/dev/null 1>/dev/null
	cd "$WINEPREFIX/drive_c/Program Files/FS-WWI"
	wine explorer /desktop=SDOE,1920x1080 Sdemons.exe 2>/dev/null 1>/dev/null
	wineserver -k 2>/dev/null
	exit 0
fi

printf "\n\nWWI Fighter Squadron not installed.  Running installer...\n\n"
bash "$PWD/install_SDOE.sh"
