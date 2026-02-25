#!/bin/bash
# Run the Math Quiz application
# Usage: ./run_quiz.sh [duration_in_seconds]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found. Run setup first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Default duration: 10 minutes (600 seconds)
DURATION=${1:-600}

echo "Starting Math Quiz (${DURATION}s duration)..."
python main.py --duration "$DURATION"
