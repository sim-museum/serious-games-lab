#!/bin/bash
# chessIQ.sh - Kramnik's chess variant (no castling / capture anything) as a PyQt app: vs the computer, hotseat,
# computer vs computer, or another player over the network (Network menu; games are found through squeak, the
# Serious Games Week matchmaker, once `sgw url http://<matchmaker>:8090` is set). Needs python3 + PyQt6.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/chessIQ" && exec python3 -m chessiq "$@"
