#!/usr/bin/env python3
"""Progress curve: each biq version vs one fixed reference, same deals, DD-scored.

Live IMPs against Q-Plus can't show bidding progress: about 100 random boards
per system give an SE near 0.7 IMP/board, and card play swings more than the
bidding changes do. This tool plays a TEAMS match per version on a fixed
deal set:

  table A: VERSION sits N/S, REFERENCE sits E/W
  table B: REFERENCE sits N/S, VERSION sits E/W

Both contracts are scored double-dummy (no card-play or lead noise), and the
swing to VERSION is IMP(A_ns - B_ns). The two tables bid identically on most
boards, so deal luck cancels and the SE is a few hundredths of an IMP.

Every version runs as its own worker process from a full code snapshot
(`git archive` into tools/runs/code/progress_<sha>), so changes outside
native_bidder.py (auction_context, bidding_systems, ...) count too, unlike
bidder_teams_ab.py. Rules only (BIQ_BID_SIM=0) unless --sim. Calls reach
the other seats without alerts, as over Q-NET.

  python3 tools/biq_progress.py --ref bf28628b --versions fd674b5e ... 3fb1715a \\
      --system TwoOverOne [--boards 2000] [--seed 1018] [--jobs 6] [--sim]

Writes tools/runs/progress/<system>_<seed>_<boards>/<sha>.jsonl (one row per
board) and summary.md; deals + DD tables are cached in
tools/runs/progress/deals_<seed>_<boards>.jsonl and shared by all runs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import tarfile
import io
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "tools" / "runs" / "progress"
CODE = ROOT / "tools" / "runs" / "code"
SEATS = "NESW"
RANKS = "AKQJT98765432"
# Board-number dealer / vulnerability (duplicate 16-board cycle).
VULS = ["None", "NS", "EW", "All", "NS", "EW", "All", "None",
        "EW", "All", "None", "NS", "All", "None", "NS", "EW"]
_IMPTAB = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
           900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imp(d: int) -> int:
    n = sum(1 for t in _IMPTAB if abs(d) >= t)
    return n if d >= 0 else -n


# ------------------------------------------------------------------ worker
def worker(snap: str, system: str) -> None:
    """Bid for one code snapshot: a JSON request per stdin line, a call back."""
    sys.path.insert(0, snap)
    os.chdir(snap)
    from backend.models import Bid, Card, Hand, Rank, Seat, Suit, Vulnerability
    from backend.native_bidder import parse_auction, evaluate_hand, decide_bid
    from backend.bidding_systems import get_system
    sy = get_system(system)
    S = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
    V = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
         "EW": Vulnerability.EW, "All": Vulnerability.BOTH}
    SU = {"C": Suit.CLUBS, "D": Suit.DIAMONDS, "H": Suit.HEARTS, "S": Suit.SPADES,
          "N": Suit.NOTRUMP}
    R = {c: r for c, r in zip(RANKS, (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                                      Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                                      Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE,
                                      Rank.TWO))}

    def mk(t, alert):
        if t == "P":
            return Bid(is_pass=True)
        if t == "X":
            return Bid(is_double=True)
        if t == "XX":
            return Bid(is_redouble=True)
        return Bid(level=int(t[0]), suit=SU[t[1]], alert=alert)

    def out(b):
        if b.is_pass:
            return "P"
        if b.is_double:
            return "X"
        if b.is_redouble:
            return "XX"
        return f"{b.level}{'N' if b.suit == Suit.NOTRUMP else b.suit.to_char()}"

    for line in sys.stdin:
        q = json.loads(line)
        hand = Hand(cards=[Card(su, R[c]) for su, part in
                           zip((Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS),
                               q["hand"].split(".")) for c in part])
        random.seed(q["rs"])
        try:
            st = parse_auction(S[q["seat"]], S[q["dealer"]],
                               [mk(t, a) for t, a in q["calls"]], vulnerability=V[q["vul"]])
            b = decide_bid(st, evaluate_hand(hand), sy, hand=hand)
            r = {"call": out(b), "alert": bool(b.alert)}
        except Exception as e:                                       # noqa: BLE001
            r = {"call": "P", "alert": False, "err": repr(e)[:200]}
        sys.stdout.write(json.dumps(r) + "\n")
        sys.stdout.flush()


# ------------------------------------------------------------------ deals
def deals(seed: int, n: int) -> list:
    """Fixed deal set with DD tables, cached on disk."""
    f = OUT / f"deals_{seed}_{n}.jsonl"
    if f.exists():
        return [json.loads(x) for x in open(f)]
    sys.path.insert(0, str(ROOT))
    from backend.dds import DDSolver
    rows = []
    for bd in range(1, n + 1):
        rng = random.Random(seed * 100003 + bd)
        cards = [s + r for s in "SHDC" for r in RANKS]
        rng.shuffle(cards)
        hands = {}
        for i, seat in enumerate(SEATS):
            h = cards[13 * i:13 * i + 13]
            hands[seat] = ".".join("".join(r for r in RANKS if s + r in h) for s in "SHDC")
        rows.append({"board": bd, "dealer": SEATS[(bd - 1) % 4], "vul": VULS[(bd - 1) % 16],
                     "hands": hands, "pbn": "N:" + " ".join(hands[s] for s in SEATS)})
    tabs = DDSolver().solve_dd_tables([r["pbn"] for r in rows])
    for r, t in zip(rows, tabs):
        r["tab"] = t
    OUT.mkdir(parents=True, exist_ok=True)
    with open(f, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return rows


# ------------------------------------------------------------------ scoring
def contract(calls, dealer):
    """(level, strain, declarer, dbl) or None for a pass-out."""
    last, lidx, dbl = None, None, 0
    for i, t in enumerate(calls):
        if t == "X":
            dbl = 1
        elif t == "XX":
            dbl = 2
        elif t != "P":
            last, lidx, dbl = t, i, 0
    if last is None:
        return None
    side = lidx % 2
    strain = last[1]
    first = next(i for i, t in enumerate(calls)
                 if i % 2 == side and t not in ("P", "X", "XX") and t[1] == strain)
    return int(last[0]), strain, SEATS[(SEATS.index(dealer) + first) % 4], dbl


def dup(level, strain, tricks, vul, dbl):
    need = level + 6
    if tricks >= need:
        per = 20 if strain in "CD" else 30
        tp = (per * level + (10 if strain == "N" else 0)) * (1, 2, 4)[dbl]
        s = tp + ((500 if vul else 300) if tp >= 100 else 50)
        if level == 6:
            s += 750 if vul else 500
        if level == 7:
            s += 1500 if vul else 1000
        if dbl:
            s += (0, 50, 100)[dbl] + (tricks - need) * (200 if vul else 100) * dbl
        else:
            s += (tricks - need) * per
        return s
    down = need - tricks
    if not dbl:
        return -down * (100 if vul else 50)
    pen = (200 + 300 * (down - 1)) if vul else (100 + 200 * min(down - 1, 2)
                                                 + 300 * max(down - 3, 0))
    return -pen * dbl


def ns_score(c, d):
    if c is None:
        return 0
    lvl, st, dec, dbl = c
    t = d["tab"][dec]["NT" if st == "N" else st]
    vul = d["vul"] == "All" or (d["vul"] == "NS" and dec in "NS") or (d["vul"] == "EW" and dec in "EW")
    s = dup(lvl, st, t, vul, dbl)
    return s if dec in "NS" else -s


# ------------------------------------------------------------------ match
_W = {}


def _ask(snap, system, sim, q):
    key = snap
    if key not in _W:
        env = dict(os.environ, BIQ_BID_SIM="1" if sim else "0",
                   WINEPREFIX=os.environ.get("WINEPREFIX", "/home/m/sgl/FRI/WP"))
        _W[key] = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker",
                                    snap, "--system", system], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True, env=env, cwd=snap)
    p = _W[key]
    p.stdin.write(json.dumps(q) + "\n")
    p.stdin.flush()
    return json.loads(p.stdout.readline())


def bid_table(d, ns, ew, system, sim):
    calls, alerts = [], []
    seat = d["dealer"]
    while len(calls) < 60:
        snap = ns if seat in "NS" else ew
        seen = [[t, a if (len(calls) - i) % 4 == 0 else False]
                for i, (t, a) in enumerate(zip(calls, alerts))]
        r = _ask(snap, system, sim, {"seat": seat, "dealer": d["dealer"], "vul": d["vul"],
                                     "hand": d["hands"][seat], "calls": seen,
                                     "rs": d["board"] * 1000 + len(calls)})
        calls.append(r["call"])
        alerts.append(r["alert"])
        if (len(calls) >= 4 and calls[-3:] == ["P"] * 3) or calls == ["P"] * 4:
            break
        seat = SEATS[(SEATS.index(seat) + 1) % 4]
    return calls


def play_board(job):
    d, ver, ref, system, sim = job
    a = bid_table(d, ver, ref, system, sim)
    b = a if ver == ref else bid_table(d, ref, ver, system, sim)
    ca, cb = contract(a, d["dealer"]), contract(b, d["dealer"])
    sa, sb = ns_score(ca, d), ns_score(cb, d)
    return {"board": d["board"], "a": " ".join(a), "b": " ".join(b),
            "ns_a": sa, "ns_b": sb, "swing": imp(sa - sb)}


def snapshot(sha: str) -> str:
    full = subprocess.run(["git", "rev-parse", sha], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    d = CODE / f"progress_{full[:10]}"
    if not (d / "backend" / "native_bidder.py").exists():
        top = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        top_dir = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.strip()
        tar = subprocess.run(["git", "archive", f"{full}:{top}"], cwd=top_dir,
                             capture_output=True, check=True).stdout
        d.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            tf.extractall(d, filter="data")
    return str(d)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--worker")
    ap.add_argument("--system", default="TwoOverOne")
    ap.add_argument("--ref")
    ap.add_argument("--versions", nargs="*", default=[])
    ap.add_argument("--boards", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1018)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--sim", action="store_true")
    a = ap.parse_args()
    if a.worker:
        worker(a.worker, a.system)
        return 0
    ds = deals(a.seed, a.boards)
    out = OUT / f"{a.system}_{a.seed}_{a.boards}{'_sim' if a.sim else ''}"
    out.mkdir(parents=True, exist_ok=True)
    ref = snapshot(a.ref)
    rows = []
    for v in a.versions:
        f = out / f"{v}.jsonl"
        if not f.exists():
            snap = snapshot(v)
            with Pool(a.jobs) as p:
                res = sorted(p.imap_unordered(play_board, [(d, snap, ref, a.system, a.sim)
                                                           for d in ds], chunksize=8),
                             key=lambda r: r["board"])
            with open(f, "w") as fh:
                for r in res:
                    fh.write(json.dumps(r) + "\n")
        res = [json.loads(x) for x in open(f)]
        sw = [r["swing"] for r in res]
        m = sum(sw) / len(sw)
        se = math.sqrt(sum((x - m) ** 2 for x in sw) / (len(sw) - 1) / len(sw))
        when = subprocess.run(["git", "log", "-1", "--format=%ad %s", "--date=format:%m-%d %H:%M", v],
                              cwd=ROOT, capture_output=True, text=True).stdout.strip()
        rows.append((v, when, len(sw), sum(1 for r in res if r["a"] != r["b"]), m, se))
        print(f"{v}  {when[:11]}  {m:+.3f} IMP/board (SE {se:.3f})  "
              f"{rows[-1][3]} of {len(sw)} boards differ", flush=True)
    lines = [f"# Progress curve: {a.system}, {a.boards} deals (seed {a.seed}), "
             f"reference {a.ref}{', simulation on' if a.sim else ', rules only'}", "",
             "Teams match per version against the reference on the same deals, both "
             "tables scored double-dummy. + = the version is stronger.", "",
             "| version | date | IMP/board vs ref | SE | boards that differ |",
             "|---|---|---|---|---|"]
    for v, when, n, ch, m, se in rows:
        lines.append(f"| {v} | {when[:11]} | {m:+.3f} | {se:.3f} | {ch} of {n} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
