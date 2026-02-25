#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
KATAGO_DIR="$ROOT/katago"
GUI_DIR="$ROOT/gui"

SABAKI_APP="$GUI_DIR/Sabaki.AppImage"
LIZGOBAN_DIR="$GUI_DIR/lizgoban"

while true; do
    echo ""
    echo "=============================="
    echo "  Human-Like Go GUI Launcher"
    echo "=============================="
    echo "  1. Sabaki"
    echo "  2. LizGoban"
    echo "  3. Quit"
    echo "=============================="
    echo ""
    read -rp "Select an option [1-3]: " choice

    case "$choice" in
        1)
            echo "Starting Sabaki..."
            if [[ -x "$SABAKI_APP" ]]; then
                "$SABAKI_APP" --no-sandbox &
                disown
                echo "Sabaki launched."
                echo "Note: Configure engine via Engines > Manage Engines if not already set."
            else
                echo "Error: Sabaki not found at $SABAKI_APP" >&2
            fi
            ;;
        2)
            echo "Starting LizGoban..."
            if [[ -d "$LIZGOBAN_DIR" ]]; then
                cd "$LIZGOBAN_DIR"
                npm start -- --no-sandbox &
                disown
                cd "$ROOT"
                echo "LizGoban launched."
            else
                echo "Error: LizGoban not found at $LIZGOBAN_DIR" >&2
            fi
            ;;
        3)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option. Please select 1-3."
            ;;
    esac
done
