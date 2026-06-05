#!/usr/bin/env python3
"""Generate a curated TEST DECK (a BDE file) for Q-Plus to play.

Q-Plus normally deals from its own (major, minor) seed. This instead writes
a BDE deck of deals matching a criterion — slam-eligible, definite-slam,
grand-slam, or random — into Q-Plus's OWN-DEALS directory. Load it in
Q-Plus via File ▸ Open Own deals, then run the harness as usual.

Why this helps the A/B: a BDE is a FIXED file of specific deals played in
order, so BOTH Run A and Run B draw the identical hands just by loading the
same file — no Match-Control seed juggling, and you can target exactly the
situations you want to stress (e.g. slams, where the bidder fixes live).

Kinds:
  slam-eligible  one side has >= --slam-hcp combined HCP (slam worth a look)
  definite-slam  double-dummy: a side makes >= 12 tricks in some strain
  grand-slam     double-dummy: a side makes 13 tricks in some strain
  random         any deal (a reproducible deck from --seed)

Usage:
  python3 tools/gen_test_deck.py --kind definite-slam --count 64 --seed 1
  #   -> writes SLAM_DEF.BDE into Q-Plus OWN-DEALS; load it in Q-Plus via
  #      File ▸ Open Own deals, then run Run A and Run B on it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.dds import DDSolver                            # noqa: E402
from backend.models import Seat                             # noqa: E402
from backend.qplus_driver import (                          # noqa: E402
    write_multi_deal_bde, qplus_own_deals_dir,
)
from tools.qplus_mixed_corpus import gen_random_deals       # noqa: E402
from tools.score_diff import _deal_to_pbn                   # noqa: E402

_STRAINS = ("S", "H", "D", "C", "NT")
_DEFAULT_NAME = {
    "slam-eligible": "SLAM_ELG.BDE",
    "definite-slam": "SLAM_DEF.BDE",
    "grand-slam": "SLAM_GR.BDE",
    "random": "RANDOM.BDE",
}


def _side_hcps(board):
    h = board.hands
    return (h[Seat.NORTH].hcp() + h[Seat.SOUTH].hcp(),
            h[Seat.EAST].hcp() + h[Seat.WEST].hcp())


def _best_dd_tricks(dds, board):
    t = dds.solve_dd_table(_deal_to_pbn(board))
    return max(t[s][st] for s in ("N", "E", "S", "W") for st in _STRAINS)


def _matches(kind, board, dds, slam_hcp):
    if kind == "random":
        return True
    if kind == "slam-eligible":
        ns, ew = _side_hcps(board)
        return ns >= slam_hcp or ew >= slam_hcp
    if kind == "definite-slam":
        return _best_dd_tricks(dds, board) >= 12
    if kind == "grand-slam":
        return _best_dd_tricks(dds, board) >= 13
    return False


def generate(kind, count, seed, slam_hcp, max_candidates):
    """Return (picked_boards, scanned)."""
    dds = DDSolver()
    picked = []
    scanned = 0
    batch_seed = seed
    batch = max(count * 4, 256)
    while len(picked) < count and scanned < max_candidates:
        for b in gen_random_deals(batch, batch_seed):
            scanned += 1
            if _matches(kind, b, dds, slam_hcp):
                picked.append(b)
                if len(picked) >= count:
                    break
            if scanned >= max_candidates:
                break
        batch_seed += 1               # fresh deals next batch (deterministic)
    return picked, scanned


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="slam-eligible",
                    choices=list(_DEFAULT_NAME))
    ap.add_argument("--count", type=int, default=64)
    ap.add_argument("--seed", type=int, default=1,
                    help="reproducible — same seed+kind => same deck")
    ap.add_argument("--slam-hcp", type=int, default=30,
                    help="[slam-eligible] min combined HCP for a side")
    ap.add_argument("--max-candidates", type=int, default=40000)
    ap.add_argument("--out", default=None,
                    help="output .BDE path (default: OWN-DEALS/<kind>.BDE)")
    args = ap.parse_args()

    picked, scanned = generate(args.kind, args.count, args.seed,
                               args.slam_hcp, args.max_candidates)
    if not picked:
        print(f"No {args.kind} deals found in {scanned} candidates — loosen "
              f"the criterion or raise --max-candidates.", file=sys.stderr)
        return 1
    if len(picked) < args.count:
        print(f"WARNING: only {len(picked)}/{args.count} {args.kind} deals "
              f"found in {scanned} candidates (capped by --max-candidates).",
              file=sys.stderr)

    if args.out:
        out = Path(args.out)
    else:
        odir = qplus_own_deals_dir()
        out = ((odir / _DEFAULT_NAME[args.kind]) if odir
               else Path(_DEFAULT_NAME[args.kind]))
    write_multi_deal_bde(
        picked, out, description=f"biq test deck: {args.kind} (seed {args.seed})",
        label_prefix=args.kind.split("-")[0][:6].upper())
    print(f"wrote {len(picked)} {args.kind} deals (scanned {scanned}) -> {out}")
    print(f"In Q-Plus: File ▸ Open Own deals ▸ {out.name}, then run the "
          f"harness. Both A and B draw the same deals from this file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
