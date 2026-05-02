#!/usr/bin/env bash
# post_game_subdir.sh - shared helpers for game scripts that run
# in-script post-game annotation/analysis.
#
# Usage:
#   source "$REPO_ROOT/launcher/lib/post_game_subdir.sh"
#   ...
#   touch "$SGL_GAME_STARTED_MARKER"
#   capture_marker_epoch              # right after touching the marker
#   ...
#   subdir="$(post_game_subdir "$DAY_DIR" "banksiagui")"
#   mv "$pgn" "$subdir/"              # move BEFORE annotation
#   ... run annotation in-place in $subdir ...
#   restore_marker_epoch              # just before exit
#
# Why: when a second game starts in another launcher session while the
# first is still running its post-game annotation, both touch (and the
# launcher later deletes) the same .sgl_game_started marker.  Without
# these helpers:
#   - the first script computes the subdir from a clobbered/missing
#     marker, landing files under the wrong YYMMDD_HHMM
#   - a concurrent game's collect_after_game_report can race into the
#     day dir and "collect" the first game's mid-annotation file into
#     the wrong session
# Capturing the epoch once + moving files to afterGameReport before
# annotation begins + restoring the marker before exit closes both
# windows.

# Stash the started-marker's mtime in SGL_MARKER_EPOCH.  Falls back to
# wall-clock time if the marker is missing or the env var is unset
# (e.g. running the script directly, not via the launcher).
capture_marker_epoch() {
    if [[ -n "${SGL_GAME_STARTED_MARKER:-}" ]] && [[ -f "$SGL_GAME_STARTED_MARKER" ]]; then
        SGL_MARKER_EPOCH="$(stat -c %Y "$SGL_GAME_STARTED_MARKER")"
    else
        SGL_MARKER_EPOCH="$(date +%s)"
    fi
    export SGL_MARKER_EPOCH
}

# Echo the timestamped afterGameReport subdir for this run, creating it.
# Args: <day_dir> <game_short_name>
# The name format matches launcher/lib/after_game_report.sh:
#   YYMMDD_HHMM_<game>
post_game_subdir() {
    local day_dir="$1"
    local game="$2"
    local epoch="${SGL_MARKER_EPOCH:-$(date +%s)}"
    local name
    name="$(date -d "@$epoch" '+%y%m%d_%H%M')_${game}"
    local path="$day_dir/afterGameReport/$name"
    mkdir -p "$path"
    echo "$path"
}

# Restore the started-marker's mtime to SGL_MARKER_EPOCH (creating the
# marker if a concurrent game's launcher collect deleted it).  Call
# this just before the script exits so the launcher's
# collect_after_game_report derives the same subdir name we used.
restore_marker_epoch() {
    [[ -z "${SGL_GAME_STARTED_MARKER:-}" || -z "${SGL_MARKER_EPOCH:-}" ]] && return 0
    touch -d "@$SGL_MARKER_EPOCH" "$SGL_GAME_STARTED_MARKER" 2>/dev/null || true
}
