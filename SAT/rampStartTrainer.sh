#!/bin/bash

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null


if [ -d "$WINEPREFIX/drive_c/FreeFalcon6/Docs/SP3" ]
then
  cd $WINEPREFIX/drive_c/FreeFalcon6/Docs/SP3
  wine sp3_ramp_start_trainer.exe 2>/dev/null 1>/dev/null
  exit 0
else
  echo "run ./FreeFalcon.sh first"
  echo "the trainer isn't installed until you've run FreeFalcon.sh at least once."
  exit 1
fi

