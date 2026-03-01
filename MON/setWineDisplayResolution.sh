#!/bin/bash

export WINEPREFIX="$PWD/WP"
export WINEARCH=win32
# Set Windows XP mode silently (no GUI)
wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d winxp /f &>/dev/null

winecfg 2>/dev/null 1>/dev/null
exit 0
