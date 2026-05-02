#!/bin/bash
# Launch Poker IQ trainer
cd "$(dirname "$0")"
SCRIPT_DIR="$PWD"
MON_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -d venv ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

# Remove log files from previous sessions (already collected by afterGameReport)
rm -f "$SCRIPT_DIR"/poker_log_*.txt

REPO_ROOT="${REPO_ROOT:-$(cd "$MON_DIR/.." && pwd)}"
source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"

snapshot_time=$(date +%s)
[[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && touch "$SGL_GAME_STARTED_MARKER"
capture_marker_epoch
python3 pokerIQ.py "$@"

# Find poker log files created during this session.  Move each into the
# timestamped afterGameReport subdir BEFORE running Claude annotation so
# a concurrent game's collect_after_game_report can't grab them
# mid-annotation.
report_subdir=""
source "$MON_DIR/claude_annotate_poker.sh"
while IFS= read -r -d '' log_file; do
    fmod=$(stat -c %Y "$log_file" 2>/dev/null) || continue
    if [[ "$fmod" -gt "$snapshot_time" ]]; then
        [[ -z "$report_subdir" ]] && report_subdir="$(post_game_subdir "$MON_DIR" pokeriq)"
        target="$report_subdir/$(basename "$log_file")"
        mv -f "$log_file" "$target"
        claude_annotate_poker "$target"
    fi
done < <(find "$SCRIPT_DIR" -maxdepth 1 -name "poker_log_*.txt" -type f -print0 2>/dev/null)
[[ -n "$report_subdir" ]] && echo "  Annotated poker log saved to afterGameReport/$(basename "$report_subdir")/"

restore_marker_epoch
