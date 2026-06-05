#!/usr/bin/env python3
"""Slam-bidding probe — grade biq's slam accuracy vs double-dummy.

Regression guard for slam-bidding work. Runs biq's bidder on the
reproducible slam-eligible deck (same deals as gen_test_deck --seed) and,
per deal, compares the contract biq reaches to the double-dummy facts:

  makeable slams in deck    a side makes 12+ DD tricks in some strain
  biq bid a slam & MAKES    biq's 6/7 contract makes double-dummy   ← grow this
  biq bid a slam & DOWN     biq bid a slam that fails (overbid / wrong strain) ← keep ~0
  makeable slams MISSED     biq stopped below 6 on a makeable-slam deal
  net IMP vs DD par         overall (biq's contract scored vs par)

Usage:
  python3 tools/slam_probe.py [--ns Precision90M] [--ew Precision90M]
                              [--count 64] [--seed 1] [--show 12]
"""
import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.dds import DDSolver                                  # noqa: E402
from backend.models import Seat                                  # noqa: E402
from tools.gen_test_deck import generate                         # noqa: E402
from tools.mixed_corpus_diff import drive_bridgeIQ_mixed         # noqa: E402
from tools.score_diff import (                                   # noqa: E402
    _determine_contract, _deal_to_pbn, _ns_score, _imp_lookup,
)
from tools.qnet_log_score import _par_ns                         # noqa: E402

_STR = {0: "S", 1: "H", 2: "D", 3: "C", 4: "NT"}


def _auc_str(board, auction):
    seat = board.dealer
    out = []
    for x in auction:
        t = ("P" if x.is_pass else "X" if x.is_double
             else f"{x.level}{x.suit.to_char() if x.suit else '?'}")
        out.append(f"{seat.name[0]}:{t}")
        seat = seat.next()
    return " ".join(out)


def run(ns, ew, count, seed, show):
    deals, _ = generate("slam-eligible", count, seed, 30, 40000)
    dds = DDSolver()
    makeable = made = down = missed = 0
    tot_imp = 0
    levels = {}
    misses = []
    for i, b in enumerate(deals, 1):
        t = dds.solve_dd_table(_deal_to_pbn(b))
        best = max(t[s][st] for s in "NESW" for st in ("S", "H", "D", "C", "NT"))
        is_makeable = best >= 12
        makeable += is_makeable
        c = _determine_contract(b, drive_bridgeIQ_mixed(b, ns, ew))
        lvl = c.level if c else 0
        levels[lvl] = levels.get(lvl, 0) + 1
        vns = b.vulnerability.is_vulnerable(Seat.NORTH)
        vew = b.vulnerability.is_vulnerable(Seat.EAST)
        par = _par_ns(t, vns, vew)
        if c is None:
            biq_ns = 0
        else:
            strain = "NT" if c.suit.value == 4 else _STR[c.suit.value]
            tricks = t["NESW"[c.declarer.value]][strain]
            biq_ns = _ns_score(c, tricks, b.vulnerability)
        tot_imp += _imp_lookup(biq_ns - par)
        if c and c.level >= 6:
            strain = "NT" if c.suit.value == 4 else _STR[c.suit.value]
            tricks = t["NESW"[c.declarer.value]][strain]
            if tricks >= 6 + c.level:
                made += 1
            else:
                down += 1
        elif is_makeable:
            missed += 1
            misses.append((i, _auc_str(b, drive_bridgeIQ_mixed(b, ns, ew))))
    n = len(deals)
    print(f"# slam probe — {n} slam-eligible deals (seed {seed}), "
          f"NS={ns} EW={ew}")
    print(f"  makeable slams (DD 12+):     {makeable}")
    print(f"  biq bid slam & MAKES:        {made}    <- grow this")
    print(f"  biq bid slam & DOWN:         {down}    <- keep ~0")
    print(f"  makeable slams MISSED (<6):  {missed}")
    print(f"  net IMP vs DD par:           {tot_imp:+d}  ({tot_imp / n:+.2f}/deal)")
    print(f"  contract-level histogram:    {dict(sorted(levels.items()))}")
    for idx, auc in misses[:show]:
        print(f"    miss #{idx}: {auc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", default="Precision90M")
    ap.add_argument("--ew", default="Precision90M")
    ap.add_argument("--count", type=int, default=64)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--show", type=int, default=0)
    a = ap.parse_args()
    run(a.ns, a.ew, a.count, a.seed, a.show)


if __name__ == "__main__":
    main()
