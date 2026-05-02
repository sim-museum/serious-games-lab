#!/usr/bin/env bash
# clean_wineserver.sh - Kill a wine prefix's wineserver before launch.
#
# Stale wineserver shared-memory state (e.g. surviving a failed/aborted boot)
# can cause non-deterministic crashes on launch — observed with the Rowan
# engine (BoB, Mig Alley): same prefix that worked moments earlier hangs in
# 3D init and crashes with a null deref in a multimedia-timer callback.
# `wineserver -k` clears the bad state; this helper is idempotent (silent
# no-op when nothing is running).
#
# Caller must have a working `wineserver` on PATH (set up the runner first).
#
# Usage:
#     source "$REPO_ROOT/launcher/lib/clean_wineserver.sh"
#     clean_wineserver               # uses $WINEPREFIX
#     clean_wineserver /path/to/WP   # explicit prefix

clean_wineserver() {
    local prefix="${1:-${WINEPREFIX:-}}"
    [[ -n "$prefix" && -d "$prefix" ]] || return 0
    WINEPREFIX="$prefix" wineserver -k 2>/dev/null || true
    sleep 1
}
