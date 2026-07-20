#!/usr/bin/env bash
# dump_mig_stack.sh — capture stacks from a hung Mig Alley (or any wine game).
#
# Ubuntu sets kernel.yama.ptrace_scope=1, so only root or an ancestor process
# may attach a debugger. Hence the sudo. Run this WHILE the game is hung —
# the whole point is to catch where it is stuck.
#
# Usage: sudo scripts/dump_mig_stack.sh [process-name]   (default Mig.exe)

set -uo pipefail

PROC="${1:-Mig.exe}"
OUT="/tmp/${PROC%.exe}_stacks_$(date +%H%M%S).txt"

PIDS=$(pgrep -x "$PROC" || true)
if [[ -z "$PIDS" ]]; then
    echo "No process named $PROC is running." >&2
    exit 1
fi

{
    echo "=== $PROC stacks, $(date) ==="
    for p in $PIDS; do
        echo ""
        echo "--- pid $p ---"
        # utime/stime deltas distinguish a spin (climbing) from a block (flat).
        echo "cpu sample 1: $(awk '{print "utime="$14" stime="$15}' /proc/$p/stat 2>/dev/null)"
        sleep 2
        echo "cpu sample 2: $(awk '{print "utime="$14" stime="$15}' /proc/$p/stat 2>/dev/null)"
        echo ""
        gdb -p "$p" -batch -ex "thread apply all bt" 2>&1
    done
} > "$OUT" 2>&1

chmod a+r "$OUT"
echo "Wrote $OUT"
echo "Threads captured: $(grep -c '^Thread ' "$OUT" 2>/dev/null || echo 0)"
