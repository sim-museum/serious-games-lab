#!/bin/bash

$PWD/INSTALL/checkWineVersion.sh 2>/dev/null 1>/dev/null
if [ $? -ne 0 ]; then
        exit 1
fi

export WINEPREFIX="$PWD/WP"
INSTALL_DIR="$PWD/INSTALL"
if [ ! -d $WINEPREFIX/drive_c/FreeFalcon6 ]
then
	# free falcon not installed yet
	echo ""; echo "Run freeFalcon.sh, then run this script again."; echo ""
fi

if [ ! -f "$INSTALL_DIR/alreadyRanDoghouseFlag.txt" ]
then
	echo ""; echo " installing mfc42 windows component needed by f4doghouse"; echo ""
	# Not a bare `winetricks mfc42` — that step is fragile on a fresh prefix;
	# see scripts/install_mfc42.sh. Only set the flag if it actually worked,
	# so a failed run retries next time instead of silently staying broken.
	if "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/install_mfc42.sh" "$WINEPREFIX"
	then
		touch "$INSTALL_DIR/alreadyRanDoghouseFlag.txt"
	else
		echo ""; echo "WARNING: mfc42 install failed — f4doghouse may not run."; echo ""
	fi
fi
clear
echo "To view graphs of flight performance, open an aircraft .dat file in the following directory:"
echo "$WINEPREFIX/drive_c/FreeFalcon6/Zips/sim/ACDATA"; echo ""
wine INSTALL/f4doghouse.exe 2>/dev/null 1>/dev/null
exit 0

