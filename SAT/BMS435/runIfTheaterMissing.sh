export WINEPREFIX=$PWD/WP
INSTALL_DIR="$PWD/INSTALL"
clear
printf "If all theaters are installed, but the list of theaters\n in the BMS Theater tab is incorrect, press a key to continue.\nOtherwise, press CONTROL C\n\n"


read replyString

cp "$INSTALL_DIR/theater.lst" "$WINEPREFIX/drive_c/Falcon BMS 4.35/Data/TerrData/TheaterDefinition"
