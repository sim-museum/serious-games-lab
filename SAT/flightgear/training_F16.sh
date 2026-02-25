
# Script Outline:
#
# This script checks for the existence of the FlightGear simulator and its add-on aircraft.
# If FlightGear is not installed, it prompts the user to run the installation script.
# If the add-on aircraft are not installed, it provides instructions for installation.
# Then, it informs the user about how to use the simulator and suggests studying cockpit instruments.
# Finally, it starts the FlightGear simulator with predefined settings.

#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# Check if FlightGear simulator is installed
if ! command -v fgfs &>/dev/null; then
    echo "FlightGear open source flight simulator is not installed."
    echo "Run: ./scripts/setup_flightgear.sh"
    exit 1
fi

# Find the fgaddon aircraft directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FGADDON_DIR="$(ls -d "$SCRIPT_DIR"/Aircraft/org.flightgear.fgaddon.* "$SCRIPT_DIR/../../TUE/flightgear"/Aircraft/org.flightgear.fgaddon.* "$HOME/.fgfs/Aircraft/org.flightgear.fgaddon.*" 2>/dev/null | head -1)"

# Check if FlightGear add-on aircraft are installed
if [ -z "$FGADDON_DIR" ]; then
    bash "$SCRIPT_DIR/../../TUE/flightgear/installFlightgear.sh"
    exit 1
fi

# Inform user about how to use the simulator
echo " "
echo "For landing help, select View/Toggle Glide Slope Tunnel"
echo " "
echo "Study the cockpit instruments and practice takeoff and landing."
echo " "
echo "For help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "Help/Aircraft Checklists"
echo "Help/Tutorials"
echo "F-16CJ Block 52"
echo " "

# Start FlightGear simulator with specified settings
fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=f16-block-52 2>/dev/null 1>/dev/null

