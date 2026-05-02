#!/bin/bash

# Set the Wine prefix to the current directory's 'WP' folder
export WINEPREFIX="$PWD/WP"

# Check if the Sierra directory exists in the Wine prefix
if [ -d "$WINEPREFIX/drive_c/Sierra" ]; then
  # Scale wine's logical DPI so the legacy form is legible on hi-DPI displays.
  # 96 = default, 144 = 1.5x. Going higher overflows the fixed-pixel controls.
  wine reg add "HKCU\\Control Panel\\Desktop" /v LogPixels /t REG_DWORD /d 144 /f &>/dev/null

  # Navigate to the GPL Setup Manager directory and run the executable
  cd "$WINEPREFIX/drive_c/Program Files/GPLSecrets/GPL Setup Manager" || exit 1
  wine "GPL Setup Manager.exe"
  exit 0
else
   # Display a message if GPL Setup Manager is not installed
   echo ""
   echo "GPL Setup Manager not installed."
   echo "To install it, from launcher.py choose THU, then Historical Grand Prix Sim Racing"
   echo "Or cd to the THU directory and run the script ./gpl.sh"
   echo ""
   exit 0
fi

# End of script

