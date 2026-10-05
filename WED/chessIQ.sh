#!/bin/bash
# chessIQ.sh - Kramnik's chess variant (no castling / capture anything) as a PyQt app: vs the computer, hotseat,
# computer vs computer, or another player over the network (Network menu; games are found through the
# Serious Games Week matchmaker, once `sgw url http://<matchmaker>:8090` is set). Needs python3 + PyQt6.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Backlog 26: the Serious Games Week matchmaker only matches copies built from the same commit (sgw sends $SGW_BUILD).
if [ -z "${SGW_BUILD:-}" ] && b=$(git -C "$SCRIPT_DIR" rev-parse --short=12 HEAD 2>/dev/null); then
    git -C "$SCRIPT_DIR" diff --quiet HEAD -- ":(glob)WED/chessIQ/**/*.py" 2>/dev/null || b="$b-dirty"
    export SGW_BUILD="$b"
fi
cd "$SCRIPT_DIR/chessIQ" && exec python3 -m chessiq "$@"
