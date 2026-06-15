#!/usr/bin/env python3
"""Offline slam-bidding quality harness — iterate on slam bidding without live runs.

Collects deals where N/S can make a SLAM double-dummy (12+ tricks in some strain),
has biq bid them UNCONTESTED (N/S only, E/W pass), and scores the final contract:

  GOOD-SLAM   biq bid a makeable 6+ (reached the slam, it makes DD).
  MISSED      DD makes slam, biq stopped below 6 (the main −385 leak).
  PHANTOM     biq bid 6+ but it is NOT makeable DD (overbid).
  GRAND-OK    DD makes 13 and biq bid the right grand.
  GRAND-BAD   biq bid 7 but only 12 (or fewer) make (overbid to grand).

Also reports the non-slam control: among deals where slam does NOT make, how
often biq wrongly bids 6+ (phantom rate on normal hands).

Usage:  python3 tools/slam_bidding_eval.py [--slam-deals 120] [--system SAYC]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import Seat, Suit                                  # noqa: E402
from backend.dds import DDSolver                                       # noqa: E402
from backend.native_bidder import (parse_auction, evaluate_hand,       # noqa: E402
                                    decide_bid)
from backend.bidding_systems import get_system                         # noqa: E402
from tools.cardplay_eval import (_deal, _pbn, _over, _contract,        # noqa: E402
                                 _STRAIN)


def _ns_dd_best(dds, hands):
    """Best NS double-dummy trick count over all strains + the strain."""
    t = dds.solve_dd_table(_pbn(hands))
    best, best_s = 0, None
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS,
              Suit.NOTRUMP):
        v = max(t["N"][_STRAIN[s]], t["S"][_STRAIN[s]])
        if v > best:
            best, best_s = v, s
    return best, best_s


def _biq_contract(hands, dealer, vul, system):
    """biq bids UNCONTESTED (N/S bid, E/W forced to pass)."""
    auction, seat = [], dealer
    from backend.native_bidder import passb
    for _ in range(40):
        if seat.is_ns():
            st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
            auction.append(decide_bid(st, evaluate_hand(hands[seat]), system))
        else:
            auction.append(passb())
        if _over(auction):
            break
        seat = seat.next()
    return _contract(auction, dealer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slam-deals", type=int, default=120)
    ap.add_argument("--system", default="SAYC")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    dds = DDSolver()
    system = get_system(a.system)

    good = missed = phantom_on_slam = 0
    grand_ok = grand_bad = 0
    nonslam = phantom_on_nonslam = 0
    n_slam, probe = 0, 0
    missed_examples = []
    while n_slam < a.slam_deals and probe < a.slam_deals * 600:
        probe += 1
        dealer, vul, hands = _deal(a.seed, probe)
        ddbest, strain = _ns_dd_best(dds, hands)
        c = _biq_contract(hands, dealer, vul, system)
        biq_lvl = c.level if c is not None else 0
        # makeable level of biq's actual strain (if any)
        biq_make = False
        if c is not None:
            t = dds.solve_dd_table(_pbn(hands))
            biq_dd = max(t["N"][_STRAIN[c.suit]], t["S"][_STRAIN[c.suit]])
            biq_make = biq_dd >= 6 + c.level
        if ddbest >= 12:                          # NS can make a slam DD
            n_slam += 1
            if biq_lvl >= 6 and biq_make:
                good += 1
                if biq_lvl == 7 and ddbest >= 13:
                    grand_ok += 1
                elif biq_lvl == 7 and ddbest < 13:
                    grand_bad += 1
            elif biq_lvl >= 6 and not biq_make:
                phantom_on_slam += 1
            else:
                missed += 1
                if len(missed_examples) < 6:
                    nshcp = hands[Seat.NORTH].hcp() + hands[Seat.SOUTH].hcp()
                    missed_examples.append(
                        f"{nshcp}hcp DD{ddbest}{strain.to_char()} -> biq "
                        f"{biq_lvl}{c.suit.to_char() if c else '-'}")
        else:                                     # no slam — control
            nonslam += 1
            if biq_lvl >= 6:
                phantom_on_nonslam += 1

    print(f"=== {n_slam} DD-makeable-slam deals ({a.system}, probed {probe}) ===")
    print(f"  GOOD-SLAM (reached + makes): {good:3d} ({100*good//max(n_slam,1)}%)"
          f"   [grand: {grand_ok} ok, {grand_bad} bad]")
    print(f"  MISSED   (stopped < 6):      {missed:3d} "
          f"({100*missed//max(n_slam,1)}%)")
    print(f"  PHANTOM  (bid 6+, not make): {phantom_on_slam:3d}")
    print(f"  --- control: {nonslam} non-slam deals, phantom 6+ bid: "
          f"{phantom_on_nonslam} ({100*phantom_on_nonslam//max(nonslam,1)}%)")
    if missed_examples:
        print("  missed examples:")
        for m in missed_examples:
            print(f"     {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
