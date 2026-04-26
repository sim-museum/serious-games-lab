#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# --- Wine runner pin (lutris-fshack-7.2-x86_64) ---
# Same rationale as WWII_SDOE.sh: SDOE asks DDraw to switch BPP from 32 to
# 16 when entering 3D; vanilla wine on Ubuntu 26.04 X11 refuses, DDraw
# init half-fails, and opsim.dll page-faults at the first surface flip.
# fshack 7.2 absorbs the BPP refusal.  Pairs with the xdotool snapper
# below (fshack positions the game window offscreen on every mode change).
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

export WINEPREFIX=$PWD/WP
export WINEARCH=win32

if [ -f "$WINEPREFIX/drive_c/Program Files/FS-WWI/Sdemons.exe" ]
then
	export WINEDLLOVERRIDES="winegstreamer=d"
	# Set Windows 98 mode silently (no GUI)
	wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d win98 /f &>/dev/null
	cd "$WINEPREFIX/drive_c/Program Files/FS-WWI"
	[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
	WINE_LOG="$OLDPWD/wine_crash.log"
	# Virtual desktop size MUST match sdemons.ini ScreenWidth/ScreenHeight
	# (WWI ships 1024x768).  When they differ, the DDraw primary surface
	# flips into "the void" — sound plays, X11 window stays black.
	wine explorer /desktop=SDOE,1024x768 Sdemons.exe >"$WINE_LOG" 2>&1 &
	WINE_PID=$!
	# fshack-7.2 positions the game window at +1920+0 inside the virtual
	# desktop (fully offscreen) and re-positions it on every mode change
	# — e.g. when entering 3D.  Pin it to (0,0) for the lifetime of the
	# session so the rendering stays inside the visible desktop.
	if command -v xdotool >/dev/null 2>&1; then
	    (
	        while kill -0 "$WINE_PID" 2>/dev/null; do
	            for WID in $(xdotool search --name "Screamin' Demons" 2>/dev/null); do
	                xdotool windowmove "$WID" 0 0 2>/dev/null
	            done
	            sleep 1
	        done
	    ) &
	fi
	wait "$WINE_PID"
	wineserver -k 2>/dev/null
	if grep -qE 'err:|wine: Unhandled|Assertion|Backtrace' "$WINE_LOG" 2>/dev/null; then
	    echo ""
	    echo "Wine reported errors — see $WINE_LOG"
	fi
	exit 0
fi

if [[ -n "${_SDOE_INSTALL_ATTEMPTED:-}" ]]; then
    printf "\nInstall did not produce Sdemons.exe at:\n  %s\nCheck the wine prefix; you may need to re-run install_SDOE.sh manually.\n\n" \
        "$WINEPREFIX/drive_c/Program Files/FS-WWI/Sdemons.exe" >&2
    exit 1
fi

printf "\n\nWWI Fighter Squadron not installed.  Running installer...\n\n"
bash "$PWD/install_SDOE.sh"
export _SDOE_INSTALL_ATTEMPTED=1
exec "$0" "$@"
