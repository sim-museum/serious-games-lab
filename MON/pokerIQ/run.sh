#!/bin/bash
# Launch Poker IQ trainer
cd "$(dirname "$0")"
if [[ ! -d venv ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
python3 pokerIQ.py "$@"
