#!/usr/bin/env python3
"""Deal-only PBN decks for WHOLE-SYSTEM (bidding + cardplay) runs vs Q-Plus.

Unlike gen_forced_pbn (which adds an [Auction] tag to FORCE biq's contract for
cardplay-only tests), these carry ONLY the deal — no auction — so BOTH sides bid
and play normally. Load in Q-Plus with **Read=Auto** (NOT Read=Bids, which would
skip bidding) for an end-to-end comparison.

Kinds:
  random         any deal (reproducible from --seed)
  slam-eligible  one side has >= --slam-hcp combined HCP (slam worth a look)

Usage:
  python3 tools/gen_deal_pbn.py --kind random --count 64 --seed 11 --out RND_S11.PBN
  python3 tools/gen_deal_pbn.py --kind slam-eligible --count 64 --seed 21 \
          --out SLAM_S21.PBN
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import Seat                                       # noqa: E402
from tools.cardplay_eval import _deal, _pbn                           # noqa: E402
from tools.gen_forced_pbn import _vuln                                # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["random", "slam-eligible"],
                    default="random")
    ap.add_argument("--count", type=int, default=64)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--slam-hcp", type=int, default=30,
                    help="[slam-eligible] min combined HCP on a side")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = ["% PBN 2.1",
           '[Event "BridgeIQ whole-system vs Q-Plus"]',
           '[Site "?"]',
           '[Scoring "IMP"]',
           f"%% kind={a.kind} seed={a.seed} count={a.count}"
           + (f" slam-hcp={a.slam_hcp}" if a.kind == "slam-eligible" else ""),
           "% Deal-only (no [Auction]) — load with Read=Auto so Q-Plus BIDS.",
           ""]

    n, probe = 0, 0
    while n < a.count:
        probe += 1
        if probe > a.count * 2000:
            print(f"gave up after {probe} probes — only {n} matched", flush=True)
            break
        dealer, vul, hands = _deal(a.seed, probe)
        if a.kind == "slam-eligible":
            ns = hands[Seat.NORTH].hcp() + hands[Seat.SOUTH].hcp()
            ew = hands[Seat.EAST].hcp() + hands[Seat.WEST].hcp()
            if max(ns, ew) < a.slam_hcp:
                continue
        n += 1
        out.append("% " + "=" * 66)
        out.append(f'[Board "{n}"]')
        out.append(f'[Dealer "{dealer.name[0]}"]')
        out.append(f'[Vulnerable "{_vuln(n)}"]')
        out.append(f'[Deal "{_pbn(hands)}"]')
        out.append("")

    Path(a.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {n} {a.kind} deals (probed {probe})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
