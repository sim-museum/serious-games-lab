#!/bin/bash
cd "$(dirname "${BASH_SOURCE[0]}")"

# Set up Wine runner environment
setup_wine_runner() {
    local runner_name="lutris-fshack-7.2-x86_64"
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

if [[ -z "${SGL_GAME_SCRIPT:-}" ]]; then
    setup_wine_runner
fi

export WINEPREFIX="$PWD/WP"
if [ ! -d "$WINEPREFIX/drive_c/Program Files/rFactor/Plugins/rFactor Data Acquisition Plugin" ]
then
       echo ""; echo "Installing telemetry logger.  During installation, deselect check for updates."
       echo "Otherwise, accept defaults."
       echo "To start logging time series telemetry data to a csv file,"
       echo "type <CTRL> m when in the rFactor 3D view."
       echo "Each time you cross the start/finish line, type <CTRL> m twice to create a new csv file for each lap."
       echo "To view telemetry data, exit rFactor and examine the csv files in the directory"
       echo "$WINEPREFIX/drive_c/Program Files/rFactor/UserData/LOG/MoTeC"
       echo ""
       wine "$WINEPREFIX/../INSTALL/rFactorDAQPluginSetup_1.3.2.exe" 2>/dev/null 1>/dev/null
       # switch log file format to .csv (the default is MoTec)
       cp "$WINEPREFIX/../INSTALL/DataAcquisitionPlugin.ini" "$WINEPREFIX/drive_c/Program Files/rFactor"
else
      echo " "; echo "The rFactor telemetry logger is already installed."; echo ""
fi
exit 0
