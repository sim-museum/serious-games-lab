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

# BASE_REF = the PRE-fix bidder (baseline, Run A); CAND_REF = the latest
# bidder with all fixes including the slam-bidding work (candidate, Run B).
# The slam fixes land after the original 3-fix commit, so candidate = a ref
# (default the branch tip), not 91f4fdd. Override either with env vars.
BASE_REF="${BASE_REF:-f50a1ce}"
CAND_REF="${CAND_REF:-24.04}"

SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
BRIDGE="$(dirname "$SCRIPT_DIR")"          # .../bridgeIQ/bridgeIQ (has backend/)
FILE="$BRIDGE/backend/native_bidder.py"
cd "$BRIDGE"

REL="$(git ls-files --full-name backend/native_bidder.py)"
[ -n "$REL" ] || { echo "native_bidder.py not tracked by the outer repo" >&2; exit 1; }

BASE_BLOB="$(git rev-parse "${BASE_REF}:${REL}")"
CAND_BLOB="$(git rev-parse "${CAND_REF}:${REL}")"

current() {
  local h; h="$(git hash-object "$FILE")"
  if   [ "$h" = "$CAND_BLOB" ]; then echo "candidate (with all fixes incl. slam)"
  elif [ "$h" = "$BASE_BLOB" ]; then echo "baseline (pre-fix)"
  else echo "MODIFIED/other (matches neither baseline nor candidate)"; fi
}

case "${1:-status}" in
  baseline)
    git checkout "${BASE_REF}" -- backend/native_bidder.py
    echo "✓ loaded BASELINE (pre-fix) bidder  →  use for Run A" ;;
  candidate)
    git checkout "${CAND_REF}" -- backend/native_bidder.py
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
