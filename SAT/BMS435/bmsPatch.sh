clear

export WINEPREFIX=$PWD/WP
INSTALL_DIR="$PWD/INSTALL"
DOWNLOADS_DIR="$PWD/../../downloads"

if [ ! -f "$WINEPREFIX/drive_c/Falcon BMS 4.35/Launcher.exe" ]
then
	printf "You must install Falcon BMS 4.35.3 before installing\nadd-on theaters.  Run ./BMS435.sh first, then run this script again.\n\n"
	exit 0
fi

mv "$DOWNLOADS_DIR/bms-4.35.3-radar-xml-patch.exe" "$INSTALL_DIR" 2>/dev/null 1>/dev/null

if [ ! -f "$INSTALL_DIR/bms-4.35.3-radar-xml-patch.exe" ]
then
	printf "BMS 4.35 patch file not found in $INSTALL_DIR.\nFrom the theaters section of www.falcon-bms.com,\nDownload the BMS 4.35.3 radar xml patch file:\n\nbms-4.35.3-radar-xml-patch.exe\n\nPlace this file in the $INSTALL_DIR directory,\n\nthen run this script again.\n\n"
	exit 0
fi

cd "$INSTALL_DIR"

wine "bms-4.35.3-radar-xml-patch.exe" 2>/dev/null 1>/dev/null
clear
printf "\nBMS 4.35.3 radar xml patch applied successfully.\n"
exit 0

