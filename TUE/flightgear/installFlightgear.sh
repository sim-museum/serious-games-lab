#!/usr/bin/env bash
# installFlightgear.sh - FlightGear add-on aircraft installation guide
# Checks prerequisites, sets up .fgfs symlink, then shows aircraft install steps.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FGFS_TARGET="$SCRIPT_DIR/.fgfs"

# Ensure fgfs is on PATH
FG_BIN="$HOME/.local/share/flightgear/bin"
[[ -d "$FG_BIN" ]] && export PATH="$FG_BIN:$PATH"

echo "=============================================="
echo "  FlightGear Add-on Aircraft Installation"
echo "=============================================="
echo ""

# Step 1: Check if FlightGear is installed
if ! command -v fgfs &>/dev/null; then
    echo "  FlightGear is not yet installed."
    echo "  Select Basic Flight Training (Cessna) from the launcher"
    echo "  to install FlightGear automatically, then run this again."
    echo ""
    exit 1
fi

# Step 2: Ensure .fgfs is in TUE/flightgear
FGFS_REAL="$(readlink -f "$HOME/.fgfs" 2>/dev/null || true)"
FGFS_TARGET_REAL="$(readlink -f "$FGFS_TARGET" 2>/dev/null || true)"

if [ "$FGFS_REAL" = "$FGFS_TARGET_REAL" ] && [ -n "$FGFS_REAL" ]; then
    # Already in the right place (symlink or direct)
    :
elif [ -L "$HOME/.fgfs" ]; then
    # Symlink pointing elsewhere — repoint it
    rm "$HOME/.fgfs"
    mkdir -p "$FGFS_TARGET"
    ln -s "$FGFS_TARGET" "$HOME/.fgfs"
    echo "  Relinked ~/.fgfs -> $FGFS_TARGET"
    echo ""
elif [ -d "$HOME/.fgfs" ]; then
    # Real directory elsewhere — move it
    mkdir -p "$FGFS_TARGET"
    rsync -a "$HOME/.fgfs/" "$FGFS_TARGET/"
    rm -rf "$HOME/.fgfs"
    ln -s "$FGFS_TARGET" "$HOME/.fgfs"
    echo "  Moved ~/.fgfs to $FGFS_TARGET"
    echo ""
else
    # No .fgfs at all
    mkdir -p "$FGFS_TARGET"
    ln -s "$FGFS_TARGET" "$HOME/.fgfs"
    echo "  Created ~/.fgfs -> $FGFS_TARGET"
    echo ""
fi

# Step 3: Install add-on aircraft
echo "  You don't have to wait for each aircraft to finish installing."
echo "  Aircraft are queued up as you add them."
echo ""
echo '  In the FlightGear launcher that follows:'
echo ""
echo '  Select "Aircraft" on the left menu'
echo '  Select "Browse" at top center'
echo '  Select "Add default hangar" at top right'
echo ""
echo "  (If FlightGear crashes, restart it and navigate back to"
echo "   Aircraft > Browse > Add Default Hangar)"
echo ""
echo "  Using the search box, find and install these aircraft."
echo "  You can search for just a few characters of the aircraft name."
echo ""
echo "  1. Supermarine Spitfire IIa (select this specific model from the drop-down list)"
echo "  2. Messerschmitt BF-109 G14"
echo "  3. North American Aviation P-51D-25-NA"
echo "  4. MiG-15bis"
echo "  5. F-86F Sabre"
echo "  6. General Dynamics F-16CJ Block 52"
echo "  7. Mikoyan-Gurevich MiG-21bis JSBSim"
echo "=============================================="
echo ""
echo "  Press a key to launch FlightGear."
read -r -n 1 -s
fgfs --launcher 2>/dev/null 1>/dev/null
