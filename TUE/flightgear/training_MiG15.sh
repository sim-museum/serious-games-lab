# Script Outline:
#
# 1. Check if FlightGear is installed, exit if not.
# 2. Check if FlightGear add-on aircraft are installed, exit if not.
# 3. Set variables for FlightGear executable and add-on aircraft directory.
# 4. Launch FlightGear with MiG 15 aircraft and set the time.
# 5. Provide instructions for using FlightGear and practicing with the MiG 15.
# 6. Provide information on where to find help for the MiG 15 aircraft.
# 7. Run FlightGear in the background.

#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# This script launches the FlightGear open source flight simulator with a Soviet MiG 15 aircraft for practice.

# Check if FlightGear is installed
if ! command -v fgfs &>/dev/null; then
    echo "The FlightGear open source flight simulator is not installed."
    echo "Run: ./scripts/setup_flightgear.sh"
    exit 1
fi

# Find the fgaddon aircraft directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FGADDON_DIR="$(ls -d "$SCRIPT_DIR"/Aircraft/org.flightgear.fgaddon.* "$HOME/.fgfs/Aircraft/org.flightgear.fgaddon.*" 2>/dev/null | head -1)"

# Check if the flightgear add-on aircraft are installed
if [ -z "$FGADDON_DIR" ]; then
    bash "$SCRIPT_DIR/installFlightgear.sh"
    exit 1
fi

# Launch FlightGear with MiG 15 aircraft and set time to noon on June 1, 2020 at the user's location
echo " "
echo "For landing help select View/Toggle Glide Slope Tunnel"
echo " "
echo "Study the cockpit instruments and practice takeoff and landing."
echo " "
echo "For help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "MiG-15bis"
echo " "

fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=MiG-15bis 2>/dev/null 1>/dev/null

