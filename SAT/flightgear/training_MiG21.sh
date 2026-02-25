# Outline of what the script does:
# This script checks if FlightGear simulator and its add-on aircraft
# are installed. It then sets up the environment for practicing
# takeoff and landing in a Soviet MiG-21 aircraft. The user is
# provided with instructions on cockpit instrument study and given
# assistance for landing maneuvers. Finally, the script launches the
# FlightGear simulator with the specified aircraft and time settings.

#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# This script facilitates learning cockpit instruments and practicing takeoff and landing in a Soviet MiG-21.

# Check if FlightGear simulator is installed
#
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

# Display instructions
echo  "\nFor landing help, select View/Toggle Glide Slope Tunnel\n"
echo "Study the cockpit instruments and practice takeoff and landing."

echo "\nFor help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "MiG-21bis"

# Start FlightGear simulator
fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=MiG-21bis 2>/dev/null 1>/dev/null

