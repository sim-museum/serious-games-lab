#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

export WINEPREFIX="$PWD/WP"
INSTALL_DIR="$PWD/INSTALL"
mkdir -p "$WINEPREFIX"

if [ -d "$WINEPREFIX/drive_c/Program Files (x86)/Tacview" ]; then
	cd "$WINEPREFIX/drive_c/Program Files (x86)/Tacview"
	wine Tacview 2>/dev/null 1>/dev/null
else
	cd "$INSTALL_DIR"
	wine Tacview176Setup.exe 2>/dev/null 1>/dev/null
fi
exit 0
