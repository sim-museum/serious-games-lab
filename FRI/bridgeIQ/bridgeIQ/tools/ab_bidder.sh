#!/usr/bin/env bash
# ab_bidder.sh — foolproof bidder swap for the LIVE A/B of the three
# Precision fixes (commit 91f4fdd). Loads the BASELINE (pre-fix) or the
# CANDIDATE (with-fix) backend/native_bidder.py into the working tree and
# always reports which is active — with a one-line proof — so you can't run
# the wrong version by mistake.
#
#   tools/ab_bidder.sh baseline    # load the pre-fix bidder   -> Run A
#   tools/ab_bidder.sh candidate   # load the with-fix bidder  -> Run B
#   tools/ab_bidder.sh status      # just report which is loaded
#
# The candidate is the 3-fix commit; the baseline is its parent. Override
# the commit with  FIX_COMMIT=<sha> tools/ab_bidder.sh ...  if you rebase.
set -euo pipefail

FIX_COMMIT="${FIX_COMMIT:-91f4fdd}"

SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
BRIDGE="$(dirname "$SCRIPT_DIR")"          # .../bridgeIQ/bridgeIQ (has backend/)
FILE="$BRIDGE/backend/native_bidder.py"
cd "$BRIDGE"

REL="$(git ls-files --full-name backend/native_bidder.py)"
[ -n "$REL" ] || { echo "native_bidder.py not tracked by the outer repo" >&2; exit 1; }

BASE_BLOB="$(git rev-parse "${FIX_COMMIT}~1:${REL}")"
CAND_BLOB="$(git rev-parse "${FIX_COMMIT}:${REL}")"

current() {
  local h; h="$(git hash-object "$FILE")"
  if   [ "$h" = "$CAND_BLOB" ]; then echo "candidate (with the 3 fixes)"
  elif [ "$h" = "$BASE_BLOB" ]; then echo "baseline (pre-fix)"
  else echo "MODIFIED/other (matches neither baseline nor candidate)"; fi
}

case "${1:-status}" in
  baseline)
    git checkout "${FIX_COMMIT}~1" -- backend/native_bidder.py
    echo "✓ loaded BASELINE (pre-fix) bidder  →  use for Run A" ;;
  candidate)
    git checkout "${FIX_COMMIT}" -- backend/native_bidder.py
    echo "✓ loaded CANDIDATE (3 fixes) bidder →  use for Run B" ;;
  status|"") ;;
  *) echo "usage: ab_bidder.sh {baseline|candidate|status}" >&2; exit 2 ;;
esac

gate="$(grep -m1 -E 'e\.hcp >= 22|e\.hcp >= 20 or e\.controls >= 5' \
        backend/native_bidder.py | sed 's/^[[:space:]]*//' || true)"
echo "now loaded : $(current)"
echo "  proof    : RKC gate is  ‘${gate}’"
echo "             (baseline = 'e.hcp >= 20 or e.controls >= 5';"
echo "              candidate = 'e.hcp >= 22')"
