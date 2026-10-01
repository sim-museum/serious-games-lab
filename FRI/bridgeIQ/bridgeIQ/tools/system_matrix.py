#!/usr/bin/env python3
"""Every bidding system against every other, offline (no Q-Plus).

`run` bids each deal of a fixed deck at 25 tables: every (N/S system, E/W
system) pair from the list, with biq's rule bidder at all four seats (rules
only, the wire view: a seat sees other seats' calls without alerts), and
scores each final contract double-dummy and against the deal's PAR. One JSON
line per (deal, table) with every call and the rule that made it.

`report` reads those lines and prints
  * the teams matrix: system X vs Y on the same deals (X N/S at one table,
    E/W at the other), IMP per deal from X's side,
  * per system: average IMP vs par when it bids, and the rate of
    pathologies (missed game / slam, phantom slam, game or slam down 2+,
    doubled into a make, -500 or worse, passed out with a game on),
  * per system: the rules whose calls most often precede a par loss
    (the side's calls on boards it lost 4+ IMP against par).

  python3 tools/system_matrix.py run --deals 400 --seed 9001 \\
          --shard 0/6 --jsonl m0.jsonl
  python3 tools/system_matrix.py report m*.jsonl [--system StandardAcol]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

SYSTEMS = ["SAYC", "Precision90M", "StandardAcol", "StandardFrench", "TwoOverOne"]
SHORT = {"SAYC": "SAYC", "Precision90M": "Prec", "StandardAcol": "Acol",
         "StandardFrench": "French", "TwoOverOne": "2/1"}
_IMPTAB = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
           900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imp(diff: int) -> int:
    n = sum(1 for t in _IMPTAB if abs(diff) >= t)
    return n if diff >= 0 else -n


def _key(b) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    from backend.models import Suit
    return f"{b.level}{'N' if b.suit == Suit.NOTRUMP else b.suit.to_char()}"


# ------------------------------------------------------------------ run

def run(deals, seed, shard, out, systems):
    import bidder_teams_ab as T
    from backend import native_bidder as nb
    from backend.bidding_systems import get_system
    from backend.dds import DDSolver
    from backend.models import Vulnerability
    from tools.cardplay_eval import _deal, _pbn, _STRAIN
    k, m = (int(x) for x in shard.split("/"))
    dds = DDSolver()
    sysobj = {s: get_system(s) for s in systems}
    vmode = {Vulnerability.NONE: 0, Vulnerability.BOTH: 1,
             Vulnerability.NS: 2, Vulnerability.EW: 3}
    with open(out, "w") as fh:
        for bd in range(1, deals + 1):
            if bd % m != k:
                continue
            dealer, vul, hands = _deal(seed, bd)
            pbn = _pbn(hands)
            tab, par = dds.solve_dd_tables_par([pbn], vmode[vul])[0]
            for ns in systems:
                for ew in systems:
                    auction, why, seat = [], [], dealer
                    for _ in range(60):
                        st = nb.parse_auction(seat, dealer,
                                              T._seen_by(seat, dealer, auction),
                                              vulnerability=vul)
                        try:
                            b = nb.decide_bid(st, nb.evaluate_hand(hands[seat]),
                                              sysobj[ns if seat.is_ns() else ew])
                        except Exception as e:                    # noqa: BLE001
                            b = nb.passb(f"CRASH {type(e).__name__}: {e}"[:80])
                        auction.append(b)
                        why.append(b.explanation or "")
                        if T._over(auction):
                            break
                        seat = seat.next()
                    c = T.final_contract(auction, dealer)
                    if c is None:
                        score, cstr = 0, "passed out"
                    else:
                        level, suit, decl, dbl = c
                        tricks = tab[decl.name[0]][_STRAIN[suit]]
                        v = (vul == Vulnerability.BOTH
                             or (vul == Vulnerability.NS and decl.is_ns())
                             or (vul == Vulnerability.EW and not decl.is_ns()))
                        s = T.score(level, suit, tricks, v, dbl)
                        score = s if decl.is_ns() else -s
                        cstr = T._cstr((level, suit, decl, dbl, tricks))
                    fh.write(json.dumps({
                        "bd": bd, "ns": ns, "ew": ew, "dealer": dealer.name[0],
                        "vul": vul.name, "pbn": pbn,
                        "calls": [_key(b) for b in auction], "why": why,
                        "contract": cstr, "score": score, "par": par,
                        "tab": tab}) + "\n")
            fh.flush()


# ------------------------------------------------------------------ report

def _hcp(hand: str) -> int:
    return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(c, 0) for c in hand)


def _rule_key(expl: str) -> str:
    k = re.sub(r"\d+", "#", expl or "(no reason)")
    k = re.sub(r"[♠♥♦♣]", "*", k)
    return k[:70]


def _pathologies(r, side):
    """Pathology tags for `side` ('NS'/'EW') at table r."""
    tags = []
    hands = dict(zip("NESW", r["pbn"][2:].split()))
    hcp = sum(_hcp(hands[s]) for s in side)
    ns = side == "NS"
    sign = 1 if ns else -1
    score = sign * r["score"]
    par = sign * r["par"]
    c = r["contract"]
    m = re.match(r"(\d)(NT|[SHDC])(x*) ([NESW]) (=|[+-]\d+)", c)
    ours = m is not None and (m.group(4) in side)
    if c == "passed out":
        if par >= 300:
            tags.append("passed out with a game on")
        return tags
    level, strain, dbl, res = int(m.group(1)), m.group(2), m.group(3), m.group(5)
    made = res == "=" or res.startswith("+")
    down = 0 if made else -int(res)
    game = (strain == "NT" and level >= 3) or (strain in "HS" and level >= 4) \
        or (strain in "DC" and level >= 5)
    tab = r["tab"]
    best_game = max(
        (1 for s in side for st in ("NT", "S", "H", "D", "C")
         if tab[s][st] >= {"NT": 9, "S": 10, "H": 10, "D": 11, "C": 11}[st]),
        default=0)
    best_slam = max((tab[s][st] for s in side for st in ("NT", "S", "H", "D", "C")),
                    default=0)
    if ours:
        if not game and best_game and hcp >= 24 and par >= 300 * (1 if ns else 1):
            tags.append("missed game")
        if level < 6 and best_slam >= 12 and hcp >= 31:
            tags.append("missed slam")
        if level >= 6 and not made:
            tags.append("phantom slam")
        elif game and down >= 2 and not dbl:
            tags.append("game down 2+")
        if dbl and not made and score <= -500:
            tags.append("-500 or worse")
    else:
        if dbl and made:
            tags.append("doubled them into a make")
        if best_game and hcp >= 24 and par >= 300 and score < 0:
            tags.append("sold out a game")
    return tags


def report(paths, only=None, top=25):
    rows = [json.loads(l) for p in paths for l in open(p)]
    systems = [s for s in SYSTEMS if any(r["ns"] == s for r in rows)]
    by = {(r["bd"], r["ns"], r["ew"]): r for r in rows}
    boards = sorted({r["bd"] for r in rows})
    print(f"{len(boards)} deals x {len(systems) ** 2} tables\n")

    # Teams matrix.
    print("Teams matrix: row system vs column system, IMP/deal from the row's side")
    print(f"{'':8s}" + "".join(f"{SHORT[s]:>8s}" for s in systems) + "     mean")
    for x in systems:
        line, tot, n_ = f"{SHORT[x]:8s}", 0.0, 0
        for y in systems:
            if x == y:
                line += f"{'-':>8s}"
                continue
            vals = [imp(by[(b, x, y)]["score"] - by[(b, y, x)]["score"])
                    for b in boards if (b, x, y) in by and (b, y, x) in by]
            v = sum(vals) / max(len(vals), 1)
            tot += v
            n_ += 1
            line += f"{v:+8.2f}"
        print(line + f"   {tot / max(n_, 1):+6.2f}")

    # Par and pathologies per system (as the side bidding, any opponents).
    print("\nPer system (every table it sits at, either direction):")
    stats = {s: defaultdict(int) for s in systems}
    vs_par = defaultdict(list)
    losses = {s: defaultdict(lambda: [0, 0]) for s in systems}
    examples = {s: defaultdict(list) for s in systems}
    for r in rows:
        for side, sysn in (("NS", r["ns"]), ("EW", r["ew"])):
            sign = 1 if side == "NS" else -1
            dpar = imp(sign * (r["score"] - r["par"]))
            vs_par[sysn].append(dpar)
            stats[sysn]["n"] += 1
            for t in _pathologies(r, side):
                stats[sysn][t] += 1
            if dpar <= -4:
                seat = "NESW".index(r["dealer"])
                seen = set()
                for c, w in zip(r["calls"], r["why"]):
                    s_ = "NESW"[seat]
                    seat = (seat + 1) % 4
                    if s_ not in side:
                        continue
                    k = _rule_key(w) if c != "P" or w else "(silent pass)"
                    if k in seen:
                        continue
                    seen.add(k)
                    losses[sysn][k][0] += 1
                    losses[sysn][k][1] += dpar
                    if len(examples[sysn][k]) < 3:
                        hands = dict(zip("NESW", r["pbn"][2:].split()))
                        examples[sysn][k].append(
                            f"bd{r['bd']} {SHORT[r['ns']]}/{SHORT[r['ew']]} d{r['dealer']} "
                            f"{r['vul']} [{' '.join(r['calls'])}] -> {r['contract']} "
                            f"par {r['par']}  {side}: {hands[side[0]]} {hands[side[1]]}")
    tags = ["missed game", "missed slam", "phantom slam", "game down 2+",
            "-500 or worse", "doubled them into a make", "sold out a game",
            "passed out with a game on"]
    print(f"{'system':8s} {'vs par':>7s} " + " ".join(f"{t[:10]:>10s}" for t in tags))
    for s in systems:
        n = max(stats[s]["n"], 1)
        print(f"{SHORT[s]:8s} {sum(vs_par[s]) / len(vs_par[s]):+7.2f} "
              + " ".join(f"{100 * stats[s][t] / n:10.1f}" for t in tags))
    print("(pathologies per 100 table-sides)")

    for s in systems:
        if only and s != only:
            continue
        print(f"\n== {s}: rules on boards lost 4+ IMP vs par "
              f"(count, total IMP vs par)")
        for k, (c, t) in sorted(losses[s].items(), key=lambda kv: kv[1][1])[:top]:
            print(f"  {c:4d} {t:+6d}  {k}")
            if only:
                for e in examples[s][k]:
                    print(f"         {e}")


def versus(paths, ref, only=None, top=30, min_n=3):
    """System X against the reference system in the SAME seat against the
    SAME opponents: the first call where X's auction leaves the reference's
    is X's (the opponents saw identical auctions before it), so the board's
    IMP difference is charged to the X rule that made that call."""
    rows = [json.loads(l) for p in paths for l in open(p)]
    by = {(r["bd"], r["ns"], r["ew"]): r for r in rows}
    systems = [s for s in SYSTEMS if any(r["ns"] == s for r in rows)]
    for x in systems:
        if x == ref or (only and x != only):
            continue
        per = defaultdict(lambda: [0, 0, 0, 0])   # n, sum, lost-boards, won
        ex = defaultdict(list)
        total = 0
        for (bd, ns, ew), r in by.items():
            for side in ("NS", "EW"):
                if (ns if side == "NS" else ew) != x:
                    continue
                other = by.get((bd, ref, ew) if side == "NS" else (bd, ns, ref))
                if other is None:
                    continue
                sign = 1 if side == "NS" else -1
                d = imp(sign * (r["score"] - other["score"]))
                total += d
                a, b = r["calls"], other["calls"]
                i = next((j for j in range(min(len(a), len(b))) if a[j] != b[j]), None)
                if i is None or d == 0:
                    continue
                k = _rule_key(r["why"][i]) if (a[i] != "P" or r["why"][i]) \
                    else "(silent pass)"
                k = f"{a[i]:>3s} {k}"
                v = per[k]
                v[0] += 1
                v[1] += d
                v[2] += d < 0
                v[3] += d > 0
                if d <= -3 and len(ex[k]) < 4:
                    hands = dict(zip("NESW", r["pbn"][2:].split()))
                    seat = "NESW"[("NESW".index(r["dealer"]) + i) % 4]
                    ex[k].append(f"bd{r['bd']} {seat} {hands[seat]} {r['vul']} "
                                 f"d{r['dealer']} [{' '.join(a[:i])}] {x} {a[i]} -> "
                                 f"{r['contract']} | {ref} {b[i]} -> {other['contract']}"
                                 f" ({d:+d})")
        print(f"\n== {x} vs {ref} (same seat, same opponents): {total:+d} IMP; "
              f"first-divergence calls ranked by IMP")
        for k, (n, t, lo, wi) in sorted(per.items(), key=lambda kv: kv[1][1])[:top]:
            if n < min_n:
                continue
            print(f"  {t:+5d} {n:4d} (won {wi:3d} lost {lo:3d})  {k}")
            for e in ex[k][:3]:
                print(f"           {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--deals", type=int, default=400)
    r.add_argument("--seed", type=int, default=9001)
    r.add_argument("--shard", default="0/1")
    r.add_argument("--jsonl", required=True)
    r.add_argument("--systems", default=",".join(SYSTEMS))
    p = sub.add_parser("report")
    p.add_argument("jsonl", nargs="+")
    p.add_argument("--system")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--vs", help="reference system for the first-divergence report")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.deals, a.seed, a.shard, a.jsonl, a.systems.split(","))
    elif a.vs:
        versus(a.jsonl, a.vs, a.system, a.top)
    else:
        report(a.jsonl, a.system, a.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
