clear

export WINEPREFIX=$PWD/WP
INSTALL_DIR="$PWD/INSTALL"
DOWNLOADS_DIR="$PWD/../../downloads"

if [ -f "$WINEPREFIX/drive_c//Program Files (x86)/Tacview/Tacview64.exe" ]
then
	wine "$WINEPREFIX/drive_c//Program Files (x86)/Tacview/Tacview64.exe" 2>/dev/null 1>/dev/null
	clear
	exit 0
fi

mv "$DOWNLOADS_DIR/Tacview187Setup.exe" $INSTALL_DIR 2>/dev/null 1>/dev/null

if [ ! -f "$INSTALL_DIR/Tacview187Setup.exe" ]
then
	printf "Tacview187Setup.exe file not found in $INSTALL_DIR.\nFrom www.tacview.net,\nDownload this file:\n\nTacview187Setup.exe\n\nPlace this file in the $INSTALL_DIR directory,\n\nthen run this script again.\n\n"
	exit 0
fi

cd "$INSTALL_DIR"
wine "Tacview187Setup.exe" 2>/dev/null 1>/dev/null
clear
printf "\ntacview installed successfully.\n"
exit 0

