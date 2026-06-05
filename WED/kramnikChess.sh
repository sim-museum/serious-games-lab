#!/bin/bash
# kramnikChess.sh - Kramnik's chess variant (no castling / capture anything)
#
# Self-contained HTML app: engine, opening book built from grandmaster games
# in which neither side castled, self-play mode, PGN save/load.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML="$SCRIPT_DIR/kramnik_chess.html"

if [[ ! -f "$HTML" ]]; then
    echo "Error: $HTML not found."
    exit 1
fi

# Open in the default browser, falling back to whatever is installed
for opener in xdg-open sensible-browser x-www-browser firefox chromium chromium-browser google-chrome; do
    if command -v "$opener" &>/dev/null; then
        "$opener" "$HTML" &>/dev/null &
        disown
        echo "Kramnik chess opened in the browser."
        echo "Use 'Save PGN' in the app to keep finished games; saved PGNs reload"
        echo "and continue exactly as they were being played."
        exit 0
    fi
done

echo "Error: no way to open a browser found (tried xdg-open, firefox, chromium, ...)."
echo "Open this file manually: $HTML"
exit 1
