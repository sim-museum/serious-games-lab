#!/bin/bash
# Run BEN Bridge application

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if it exists
if [ -f "$BRIDGE_DIR/venv/bin/activate" ]; then
    source "$BRIDGE_DIR/venv/bin/activate"
fi

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR:$BRIDGE_DIR/ben/src:$PYTHONPATH"
export TF_CPP_MIN_LOG_LEVEL=2
export QT_AUTO_SCREEN_SCALE_FACTOR=1

# Run the application
cd "$SCRIPT_DIR"
python main.py "$@"
