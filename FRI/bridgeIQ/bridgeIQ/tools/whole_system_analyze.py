#!/usr/bin/env python3
"""Whole-system (bidding + cardplay) analysis of biq-vs-Q-Plus TEAMS .qss files.

Each board in a teams .qss has two tables: D1/RE[0] = OPEN room (biq plays N/S),
D2/RE[1] = CLOSED room (Q-Plus N/S). RE is the N/S-perspective score per table,
so biq's result on a board is RE[0] and Q-Plus's is RE[1]; the IMP swing to biq
is IMP(RE[0] - RE[1]). This sums the net IMP across one or more decks AND buckets
every board biq lost into WHY, using the double-dummy table:

  OVERBID        biq declared a contract that is DD-UNMAKEABLE (bid too high).
  MISSED GAME    NS can make a game DD and Q-Plus bid it, biq stopped in part.
  MISSED SLAM    NS can make a slam DD and Q-Plus bid it, biq did not.
  CARDPLAY       same contract both tables, biq (declaring) took fewer tricks.
  DEFENSE        E/W declared both tables, biq (defending) let more tricks.
  BIDDING-OTHER  different contracts, not cleanly over/under (partscore judgement)

Usage:  python3 tools/whole_system_analyze.py <a.qss> [<b.qss> ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models import Suit                                       # noqa: E402
from backend.dds import DDSolver                                      # noqa: E402
from tools.cardplay_eval import _STRAIN                               # noqa: E402

_SUIT = {"s": Suit.SPADES, "h": Suit.HEARTS, "d": Suit.DIAMONDS,
         "c": Suit.CLUBS, "nt": Suit.NOTRUMP}
_IMPTAB = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
           900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def _imp(diff: int) -> int:
    """IMPs for a point difference (sign = direction)."""
    a = abs(diff)
    n = 0
    for t in _IMPTAB:
        if a >= t:
            n += 1
        else:
            break
    return n if diff >= 0 else -n


_RES = re.compile(r'D(\d) Result\s*:\s*(\d)(nt|[shdc])\s+(x\s+)?'
                  r'(North|South|East|West)\s+([=+-]\d*)\s')


def parse_qss(path: str):
    boards, cur = [], None
    for line in open(path, errors="ignore"):
        if line.startswith("DI "):
            cur = {"di": line.split('"')[1], "t": {}}
        elif cur is not None and line.startswith("DD "):
            cur["deal"] = line.split('"')[1]
        elif cur is not None and line.startswith("RE "):
            p = line.split()
            cur["re"] = (int(p[1]), int(p[2]))
        else:
            m = _RES.search(line)
            if m and cur is not None:
                tbl = int(m.group(1))
                rn = 0 if m.group(6) == "=" else int(m.group(6))
                cur["t"][tbl] = {"lvl": int(m.group(2)), "strain": m.group(3),
                                 "decl": m.group(5)[0], "took": 6 + int(m.group(2)) + rn,
                                 "dbl": bool(m.group(4))}
        if cur is not None and "re" in cur and 1 in cur["t"] and 2 in cur["t"]:
            boards.append(cur)
            cur = None
    return boards


def _ns_dd(dd, strain):                      # best NS DD tricks in a strain
    k = _STRAIN[_SUIT[strain]]
    return max(dd["N"][k], dd["S"][k])


def _game_level(lvl, strain):                # is this a game-level contract?
    if strain == "nt":
        return lvl >= 3
    if strain in ("s", "h"):
        return lvl >= 4
    return lvl >= 5                          # minor


def classify(b, dd):
    t1, t2 = b["t"][1], b["t"][2]            # t1 = biq table, t2 = Q-Plus table
    biq_ns, qp_ns = b["re"]
    swing = _imp(biq_ns - qp_ns)             # +ve = biq gained
    if swing >= 0:
        return ("biq-won-or-push", swing)
    t1_ns, t2_ns = t1["decl"] in "NS", t2["decl"] in "NS"
    # same contract at both tables -> pure play, no bidding difference
    if (t1["lvl"], t1["strain"], t1_ns) == (t2["lvl"], t2["strain"], t2_ns):
        return ("CARDPLAY" if t1_ns else "DEFENSE", swing)
    # biq let E/W buy the contract (passive / bad competitive decision)
    if not t1_ns:
        if t1["dbl"] and t1["took"] >= 6 + t1["lvl"]:
            return ("BAD DOUBLE", swing)     # doubled E/W into a make
        return ("UNDER-COMPETE", swing)      # passed, E/W bought + made it
    # biq's N/S declared a different contract than Q-Plus's N/S:
    need = 6 + t1["lvl"]
    if _ns_dd(dd, t1["strain"]) < need:      # biq's contract DD-unmakeable
        return ("OVERBID", swing)
    qp_made = t2_ns and t2["took"] >= 6 + t2["lvl"]
    if t2_ns and t2["lvl"] >= 6 and qp_made and t1["lvl"] < 6:
        return ("MISSED SLAM", swing)
    if qp_made and _game_level(t2["lvl"], t2["strain"]) \
            and not _game_level(t1["lvl"], t1["strain"]):
        return ("MISSED GAME", swing)        # biq in part, Q-Plus bid+made game
    if t1["took"] < need:                    # makeable but biq played it down
        return ("CARDPLAY", swing)
    return ("PARTSCORE", swing)              # both make, biq's worth less


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    dds = DDSolver()
    buckets, net, nb = {}, 0, 0
    per_file = []
    for path in sys.argv[1:]:
        f_net, f_nb = 0, 0
        for b in parse_qss(path):
            try:
                deal = b["deal"].split(" ", 2)[2]
                dd = dds.solve_dd_table(deal if deal.startswith("N:")
                                        else "N:" + deal)
            except Exception:
                continue
            bucket, swing = classify(b, dd)
            buckets.setdefault(bucket, [0, 0])
            buckets[bucket][0] += 1
            buckets[bucket][1] += swing
            net += swing
            f_net += swing
            nb += 1
            f_nb += 1
        per_file.append((Path(path).name, f_net, f_nb))

    print("=" * 64)
    for name, fn, fnb in per_file:
        print(f"  {name:28s} {fn:+5d} IMP / {fnb} boards "
              f"({fn / max(fnb, 1):+.2f}/bd)")
    print("=" * 64)
    print(f"  TOTAL: {net:+d} IMP over {nb} boards = {net / max(nb, 1):+.2f}/board\n")
    print(f"  {'bucket':16s} {'boards':>7} {'IMP':>7}   (negative = biq lost)")
    bidding = ("OVERBID", "MISSED GAME", "MISSED SLAM", "UNDER-COMPETE",
               "BAD DOUBLE", "PARTSCORE")
    play = ("CARDPLAY", "DEFENSE")
    for k in bidding + play + ("biq-won-or-push",):
        if k in buckets:
            c, im = buckets[k]
            print(f"  {k:16s} {c:>7} {im:>+7}")
    bid_imp = sum(buckets.get(k, [0, 0])[1] for k in bidding)
    play_imp = sum(buckets.get(k, [0, 0])[1] for k in play)
    print(f"\n  --> BIDDING losses {bid_imp:+d} IMP  |  CARDPLAY/DEFENSE "
          f"{play_imp:+d} IMP")
    lost = bid_imp + play_imp
    if lost:
        print(f"      bidding is {100 * bid_imp // lost}% of the gross loss")
    return 0


if __name__ == "__main__":
    sys.exit(main())
