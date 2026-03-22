#!/bin/bash
# Launch Poker IQ trainer
cd "$(dirname "$0")"
source venv/bin/activate
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
python3 pokerIQ.py "$@"
