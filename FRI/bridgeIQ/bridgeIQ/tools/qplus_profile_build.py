#!/usr/bin/env python3
"""Build backend/data/qplus_call_profiles.json from Q-Plus's recorded deals,
and test on held-out deals whether it reads Q-Plus's hands better than biq's
own rules do.

Every call a Q-Plus player made (closed room: all four seats; open room: E/W)
becomes one example: the situation (seat-relative calls so far), the call,
and the caller's HCP and suit lengths. backend/qplus_model.py turns them into
per-situation ranges.

  python3 tools/qplus_profile_build.py            # build the shipped table
  python3 tools/qplus_profile_build.py --eval 150 # held-out sampler test

--eval: deals are split by a hash into build (2/3) and test (1/3). At random
points of the TEST deals' closed-room auctions, one Q-Plus player's view is
taken as "me"; the bid_sim sampler deals the hidden hands with the opponents'
calls read (a) by biq's rules, (b) by the Q-Plus profiles built from the
build deals only. Error = how far the sampled opponents' HCP and suit
lengths are from their real hands (mean absolute error per seat).
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backend import bid_sim, qplus_model                              # noqa: E402
from backend.bidding_systems import get_system                       # noqa: E402
from backend.native_bidder import parse_auction                      # noqa: E402
from qplus_auction_mine import (_blocks, parse_block, _call, QPLUS_DATA,  # noqa: E402
                                _SEATS, file_system)
from competitive_decision_probe import hand_from                     # noqa: E402


def gather(paths):
    """(rows, deals): one row per distinct Q-Plus call; deals by pbn."""
    rows, seen, deals = [], set(), {}
    for path in paths:
        for room, lines in _blocks(path):
            d = parse_block(lines)
            if d is None:
                continue
            pbn = "N:" + " ".join(d["hands"][s] for s in "NESW")
            biq = {s for s, n in d["players"].items() if "biq" in n.lower()}
            if room == "closed":
                deals[pbn] = d
            seat, prefix = d["dealer"], []
            for tok in d["calls"]:
                b, _alert = _call(tok)
                if b is None:
                    break
                sc = seat.name[0]
                key = (pbn, tuple(prefix), sc)
                if sc not in biq and key not in seen:
                    seen.add(key)
                    h = d["hands"][sc].split(".")
                    rows.append({
                        "deal": pbn,
                        "ctx": qplus_model.context(prefix, d["dealer"].value, seat.value),
                        "call": bid_sim._key(b),
                        "hcp": sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(c, 0)
                                   for s in h for c in s),
                        "len": [len(s) for s in h]})
                prefix.append(bid_sim._key(b))
                seat = seat.next()
    return rows, deals


def _split(pbn):
    return int(hashlib.sha1(pbn.encode()).hexdigest()[:8], 16) % 3 == 0   # test


def evaluate(rows, deals, n_points, seed=5):
    train = [r for r in rows if not _split(r["deal"])]
    table = qplus_model.build(train)
    rng = random.Random(seed)
    system = get_system("SAYC")
    test_deals = [p for p in deals if _split(p)]
    points = []
    for pbn in test_deals:
        d = deals[pbn]
        calls = [_call(t)[0] for t in d["calls"]]
        if None in calls:
            continue
        seat = d["dealer"]
        for i in range(len(calls)):
            opp_bid = any(not b.is_pass for k, b in enumerate(calls[:i])
                          if ((d["dealer"].value + k) - seat.value) % 2 == 1)
            if opp_bid and i >= 2:
                points.append((pbn, seat, i))
            seat = seat.next()
    rng.shuffle(points)
    points = points[:n_points]
    err = {"biq": [0.0, 0.0, 0], "qplus": [0.0, 0.0, 0]}
    t0 = time.time()
    for k, (pbn, seat, i) in enumerate(points):
        d = deals[pbn]
        calls = [_call(t)[0] for t in d["calls"]][:i]
        me = hand_from(d["hands"][seat.name[0]])
        st = parse_auction(seat, d["dealer"], calls, vulnerability=d["vul"])
        opps = [s for s in (seat.next(), seat.partner().next())]
        real = {}
        for o in opps:
            h = d["hands"][o.name[0]].split(".")
            real[o] = (sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(c, 0) for s in h for c in s),
                       [len(s) for s in h])
        for model in ("biq", "qplus"):
            os.environ["BIQ_OPP_MODEL"] = model
            qplus_model.set_table(table)
            smp = bid_sim._Sampler(st, me, system, random.Random(k), time.time() + 20)
            lay = smp.sample(24)
            if not lay:
                continue
            for o in opps:
                hcp_e = sum(abs(sum(bid_sim._HCP[c % 13] for c in L[o]) - real[o][0])
                            for L in lay) / len(lay)
                len_e = sum(sum(abs(sum(1 for c in L[o] if c // 13 == sv) - real[o][1][sv])
                                for sv in range(4)) for L in lay) / len(lay)
                err[model][0] += hcp_e
                err[model][1] += len_e
                err[model][2] += 1
        if (k + 1) % 25 == 0:
            print(f"  {k + 1}/{len(points)} points ({time.time() - t0:.0f}s)", flush=True)
    for m, (h, l, n) in err.items():
        if n:
            print(f"  opponents read by {m:5s}: HCP error {h / n:.2f}, "
                  f"suit-length error {l / n:.2f} (sum over 4 suits), {n} seat-samples")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--eval", type=int, default=0)
    ap.add_argument("-o", "--out", default=str(qplus_model._PATH))
    a = ap.parse_args()
    paths = []
    for p in a.paths or [str(ROOT / "tools/runs/results"),
                         str(QPLUS_DATA / "LOCAL-MATCHES"), str(QPLUS_DATA / "LOG")]:
        if os.path.isdir(p):
            for ext in ("qss", "bdl", "cdl"):
                paths += sorted(glob.glob(os.path.join(p, f"*.{ext}")))
        else:
            paths.append(p)
    kept = [p for p in paths if file_system(p) == "A-SAYC-I"]
    print(f"{len(paths) - len(kept)} files skipped (not SAYC or system unknown)")
    rows, deals = gather(kept)
    print(f"{len(rows)} Q-Plus calls from {len(deals)} deals")
    if a.eval:
        evaluate(rows, deals, a.eval)
        return 0
    table = qplus_model.build(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(table, sort_keys=True))
    print(f"{len(table)} situation profiles written to {a.out}")
    qplus_model.set_table(table)
    cover = sum(1 for r in rows if qplus_model.profile(r["ctx"], r["call"]) is not None)
    print(f"calls covered by a profile: {cover}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
