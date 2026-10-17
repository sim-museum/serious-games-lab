#!/usr/bin/env python3
"""Rules-only A/B on Q-Plus's recorded calls (fast companion to qplus_agreement).

qplus_agreement's bid mode runs the full bidder (simulation included) and
re-scores every disagreement with the current code's rollouts, so its IMP
total drifts between code versions even on calls that did not change, and a
2/1 run takes ~10 h. This tool asks biq's RULES (BIQ_BID_SIM=0) for every
recorded Q-Plus call (17,420 2/1 calls in ~8 min on 2 cores), then scores only
the calls that changed between two scans: old call and new call are both
rolled out with the NEW code and compared with Q-Plus's call (robust judge),
so the difference is attributable to the change.

  scan    SYSTEM OUT.jsonl [--jobs 2] [--runs DIR ...]
          one row per Q-Plus call: biq's rule call, its reason, agreement;
          "origin" = the function that returned a reasonless pass.
  changed SYSTEM OLD.jsonl NEW.jsonl OUT.jsonl [--jobs 2]
          IMP of new - old on the changed calls (+ = the change helps).

Typical use: scan from a code snapshot (tools/runs/code/<stamp>) for OLD and
from the working tree for NEW, then `changed` from the working tree. Run
both scans with the same WINEPREFIX (~/sgl/FRI/WP).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

os.environ["BIQ_BID_SIM"] = "0"
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "tools"))

import qplus_agreement as q                                           # noqa: E402
from qplus_auction_mine import _context                              # noqa: E402
from multiprocessing import Pool                                     # noqa: E402

_orig_passb = q.nb.passb
_ORIGIN = [None]


def _passb(why=""):
    if not why:
        f = sys._getframe(1)
        _ORIGIN[0] = f"{f.f_code.co_name}:{f.f_lineno}"
    return _orig_passb(why)


q.nb.passb = _passb


def _key(r):
    return (r["deal"], r["auction"], r["seat"])


def scan_one(d):
    try:
        hands = q._hands(d["deal"])
        dealer = q.SEATS[q._L.index(d["dealer"])]
        seat = q.SEATS[q._L.index(d["seat"])]
        vul = q.VUL.get(d["vul"], q.Vulnerability.NONE)
        prefix = [q.Bid.from_str(t) for t in d["prefix"]]
        qb = q.Bid.from_str(d["qplus"])
        random.seed(q._seed(d["deal"], d["prefix"], d["seat"]))
        _ORIGIN[0] = None
        st = q.nb.parse_auction(seat, dealer, list(prefix), vulnerability=vul)
        try:
            b = q.nb.decide_bid(st, q.nb.evaluate_hand(hands[seat]), q._SYS)
        except Exception as e:                                       # noqa: BLE001
            b = q.nb.passb(f"CRASH {type(e).__name__}")
        if not q.tm.legal_call(prefix, dealer, seat, b):
            b = q.Bid.make_pass()
        return {"deal": d["deal"], "dealer": d["dealer"], "vul": d["vul"], "seat": d["seat"],
                "auction": " ".join(d["prefix"]), "ctx": _context(prefix, seat, dealer),
                "hand": hands[seat].to_pbn() if hasattr(hands[seat], "to_pbn") else str(hands[seat]),
                "qplus": d["qplus"], "biq": q.bid_sim._key(b),
                "agree": q.bid_sim._key(b) == q.bid_sim._key(qb),
                "cat": q._category(prefix, seat, dealer),
                "rule": q._rule_key(b.explanation), "why": (b.explanation or "")[:160],
                "origin": _ORIGIN[0] if (b.is_pass and not b.explanation) else None}
    except Exception as e:                                           # noqa: BLE001
        return {"error": repr(e), "auction": " ".join(d["prefix"])}


def _score(st, seat, hands, evals, tab, vul, call):
    c = q.bid_sim._rollout(q.nb, st, q._SYS, hands, evals, q.Bid.from_str(call))
    return q._side(q.bid_sim.robust_result(c, tab, vul, True, not seat.is_ns()), seat), str(c)


def changed_one(pair):
    o, n = pair
    try:
        hands = q._hands(n["deal"])
        dealer = q.SEATS[q._L.index(n["dealer"])]
        seat = q.SEATS[q._L.index(n["seat"])]
        vul = q.VUL.get(n["vul"], q.Vulnerability.NONE)
        toks = n["auction"].split() if n["auction"] else []
        st = q.nb.parse_auction(seat, dealer, [q.Bid.from_str(t) for t in toks], vulnerability=vul)
        random.seed(q._seed(n["deal"], toks, n["seat"]))
        tab = q._tab(n["deal"])
        evals = {s: q.nb.evaluate_hand(h) for s, h in hands.items()}
        rq, cq = _score(st, seat, hands, evals, tab, vul, n["qplus"])
        ro, co = _score(st, seat, hands, evals, tab, vul, o["biq"])
        rn, cn = _score(st, seat, hands, evals, tab, vul, n["biq"])
        n.update(old=o["biq"], old_rule=o["rule"], imp_old=q.bid_sim._imp(ro - rq),
                 imp_new=q.bid_sim._imp(rn - rq), c_q=cq, c_old=co, c_new=cn)
    except Exception as e:                                           # noqa: BLE001
        n["cerr"] = repr(e)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["scan", "changed"])
    ap.add_argument("system")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--runs", nargs="*", default=q.PRECISION_RUNS)
    a = ap.parse_args()
    q._init(a.system)
    if a.mode == "scan":
        decs = q.bid_decisions(a.runs, a.system)
        print(len(decs), "decisions", flush=True)
        with Pool(a.jobs, initializer=q._init, initargs=(a.system,)) as p, \
                open(a.files[0], "w") as f:
            for r in p.imap(scan_one, decs, chunksize=20):
                f.write(json.dumps(r) + "\n")
        return 0
    fo, fn, out = a.files[:3]
    old = {_key(r): r for r in map(json.loads, open(fo)) if "error" not in r}
    new = [r for r in map(json.loads, open(fn)) if "error" not in r]
    pairs = [(old[_key(r)], r) for r in new if _key(r) in old and old[_key(r)]["biq"] != r["biq"]]
    ao = sum(old[_key(r)]["agree"] for r in new if _key(r) in old)
    print(f"{len(pairs)} changed of {len(new)}; agreement {ao} -> {sum(r['agree'] for r in new)}",
          flush=True)
    with Pool(a.jobs, initializer=q._init, initargs=(a.system,)) as p:
        rows = list(p.imap_unordered(changed_one, pairs, chunksize=2))
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    rows = [r for r in rows if "imp_new" in r]
    d = [r["imp_new"] - r["imp_old"] for r in rows]
    m = sum(d) / max(len(d), 1)
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1))
    print(f"changed calls: new - old = {sum(d):+d} IMP over {len(d)} "
          f"(SE {sd * math.sqrt(len(d)):.0f}); better {sum(x > 0 for x in d)}, "
          f"worse {sum(x < 0 for x in d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
