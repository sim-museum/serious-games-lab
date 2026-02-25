# Script Outline:
#
# 1. Check if FlightGear is installed.
# 2. Check if FlightGear add-on aircraft are installed.
# 3. Set variables for readability.
# 4. Set the aircraft to F-86F and set time to noon on June 1, 2020 at the user's location.
# 5. Provide instructions and guidance for using the script.
# 6. Start FlightGear with specified options.
# 7. Display a message indicating the completion of the script with relevant information.

#!/bin/bash
[[ -d "$HOME/.local/share/flightgear/bin" ]] && export PATH="$HOME/.local/share/flightgear/bin:$PATH"

# Learn cockpit instruments, practice takeoff and landing in a US F-86F Sabre

# Check if FlightGear is installed
if ! command -v fgfs &>/dev/null; then
    echo "The FlightGear open source flight simulator is not installed."
    echo "Run: ./scripts/setup_flightgear.sh"
    exit 1
fi

# Find the fgaddon aircraft directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FGADDON_DIR="$(ls -d "$SCRIPT_DIR"/Aircraft/org.flightgear.fgaddon.* "$HOME/.fgfs/Aircraft/org.flightgear.fgaddon.*" 2>/dev/null | head -1)"

# Check if FlightGear add-on aircraft are installed
if [ -z "$FGADDON_DIR" ]; then
    bash "$SCRIPT_DIR/installFlightgear.sh"
    exit 1
fi

# Set variables for readability
export flight_script="$PWD/training_F86_startInAir.sh"

# Set the aircraft to F-86F and set time to noon on June 1, 2020 at the user's location
echo " "; echo "For landing help select View/Toggle Glide Slope Tunnel"; echo " ";
echo "Study the cockpit instruments and practice takeoff and landing."
echo " "; echo "For help on this aircraft, see:"
echo "Help/Aircraft Help"
echo "Sabre"; echo " "

# Start FlightGear with specified options
fgfs --start-date-sys=2020:06:01:12:00:00 --aircraft=F-86F 2>/dev/null 1>/dev/null

clear
printf "F-86F optional script\n\nStart with the F-86F in the air:\n%s\n\n" "$flight_script"

