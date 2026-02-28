#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# This script launches the FlightGear flight simulator with a German ME 109G aircraft for learning cockpit instruments,
# and practicing takeoff and landing.

# Check if FlightGear is installed
if ! command -v fgfs &>/dev/null; then
    echo "The FlightGear open-source flight simulator is not installed."
    echo "Run: ./scripts/setup_flightgear.sh"
    exit 1
fi

# Find the fgaddon aircraft directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FGADDON_DIR="$(ls -d "$SCRIPT_DIR"/Aircraft/org.flightgear.fgaddon.* "$HOME"/.fgfs/Aircraft/org.flightgear.fgaddon.* 2>/dev/null | head -1)"

# Check if FlightGear add-on aircraft are installed
if [ -z "$FGADDON_DIR" ]; then
    bash "$SCRIPT_DIR/installFlightgear.sh"
    exit 1
fi

# Launch FlightGear with p51d aircraft
# Set time to noon on June 1, 2020 at the user's location
echo " "; echo "For landing help select View/Toggle Glide Slope Tunnel"; echo " ";
echo "Study the cockpit instruments and practice takeoff and landing."
echo " "; echo "For help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "Help/Tutorials"
echo "p51d"; echo " "

fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=p51d-jsbsim 2>/dev/null 1>/dev/null

# Provide optional script instructions
clear
printf "p51d optional script\n\nStart with the p51d in the air:\n%s/training_p51d_startInAir.sh\n\n" "$PWD"


