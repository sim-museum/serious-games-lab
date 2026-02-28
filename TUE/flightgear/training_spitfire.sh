#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# Outline of the script:
#
# This script checks if FlightGear simulator and its add-on aircraft are installed.
# If not installed, it provides instructions for installation and exits.
# It then sets the aircraft to Spitfire and starts the FlightGear simulator for practice.
#
# Script dependencies:
# - FlightGear simulator (fgfs)
# - Add-on aircraft directory (org.flightgear.fgaddon.*)
#
# Steps:
# 1. Check if FlightGear simulator is installed.
# 2. Check if FlightGear add-on aircraft are installed.
# 3. Set the aircraft to Spitfire and time to noon on June 1, 2020.
# 4. Start the FlightGear simulator.

# Check if FlightGear simulator is installed
if ! command -v fgfs &>/dev/null; then
    echo "The FlightGear open source flight simulator is not installed."
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

# Set the aircraft to Spitfire and time to noon on June 1, 2020 at the user's location
echo " "
echo "For landing help select View/Toggle Glide Slope Tunnel"
echo " "
echo "Study the cockpit instruments and practice takeoff and landing."
echo " "
echo "For help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "Help/Tutorials"
echo "Spitfire"
echo " "

# Start FlightGear simulator
fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=spitfireIIa 2>/dev/null 1>/dev/null

