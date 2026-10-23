#!/usr/bin/env python3
"""Build backend/data/biq_partner_profiles.json.gz (see backend/partner_model.py).

biq's rules bid random deals at all four seats (random dealer and
vulnerability, the wire view: other seats' alerts stripped, as over Q-NET or
the Blue Chip table manager). At every turn, the auction so far is recorded
from the seat to call, with partner's actual HCP and suit lengths. Profiles
are kept for situations with enough deals behind them (partner_model.MIN_N).

  python3 tools/biq_profile_build.py --deals 300000 [--system SAYC] [--seed 1] [--jobs 7]
  python3 tools/biq_profile_build.py --deals 20000 --out /tmp/held.json.gz
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
import time
from array import array
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import partner_model as PM            # noqa: E402
from backend.models import Seat, Hand, Vulnerability  # noqa: E402

SEATS = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
VULS = [Vulnerability.NONE, Vulnerability.NS, Vulnerability.EW, Vulnerability.BOTH]
RANKS = "AKQJT98765432"
SUITS = "SHDC"


def deal_hands(rng):
    cards = list(range(52))
    rng.shuffle(cards)
    hands = []
    for i in range(4):
        h = cards[13 * i:13 * (i + 1)]
        by = [sorted(RANKS[c % 13] for c in h if c // 13 == s) for s in range(4)]
        pbn = ".".join("".join(sorted(x, key=RANKS.index)) for x in by)
        hcp = sum(max(0, 4 - c % 13) for c in h)
        hands.append((pbn, hcp, [len(x) for x in by]))
    return hands


def work(args):
    seed, n, system_name = args
    from tools.bidder_teams_ab import bid_auction
    from backend import native_bidder as NB
    from backend.bidding_systems import get_system
    system = get_system(system_name)
    rng = random.Random(seed)
    recs = {}
    for _ in range(n):
        hands = deal_hands(rng)
        dealer = rng.randrange(4)
        vul = rng.choice(VULS)
        objs = {SEATS[i]: Hand.from_pbn(hands[i][0]) for i in range(4)}
        try:
            auc = bid_auction(objs, SEATS[dealer], vul, system, NB, NB)
        except Exception:
            continue
        calls = [PM.call_key(b) for b in auc]
        for k in range(len(calls)):
            s = (dealer + k) % 4
            p = (s + 2) % 4
            ctx = PM.context(calls[:k], dealer, s)
            v = PM.pack(hands[p][1], hands[p][2])
            for lvl, key in PM.keys(ctx).items():
                recs.setdefault(f"{lvl} {key}", []).append(v)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deals", type=int, default=300000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--system", default="SAYC")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    chunk = 500
    a.out = a.out or str(PM.path_for(a.system))
    tasks = [(a.seed * 1_000_003 + i, min(chunk, a.deals - i * chunk), a.system)
             for i in range((a.deals + chunk - 1) // chunk)]
    agg = {}
    t0 = time.time()
    with Pool(a.jobs) as pool:
        for done, recs in enumerate(pool.imap_unordered(work, tasks), 1):
            for k, vs in recs.items():
                arr = agg.get(k)
                if arr is None:
                    agg[k] = arr = array("I")
                arr.extend(vs)
            if done % 50 == 0:
                print(f"{done * chunk} deals, {len(agg)} situations, "
                      f"{time.time() - t0:.0f}s", flush=True)
    profiles = {}
    for k, arr in agg.items():
        if len(arr) >= PM.MIN_N[k.split()[0]]:
            profiles[k] = PM.summarize(arr)
    out = {"bidder": PM.bidder_fingerprint(), "system": a.system,
           "deals": a.deals, "seed": a.seed,
           "built": time.strftime("%Y-%m-%d"), "profiles": profiles}
    with gzip.open(a.out, "wt") as fh:
        json.dump(out, fh, separators=(",", ":"))
    by = {}
    for k in profiles:
        by[k.split()[0]] = by.get(k.split()[0], 0) + 1
    print(f"{len(profiles)} profiles {by} from {a.deals} deals -> {a.out} "
          f"({Path(a.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
