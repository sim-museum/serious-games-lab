#!/usr/bin/env python3
"""Replay biq's real card decisions from the Q-Plus matches.

`extract` walks the open room of every recorded match (biq N/S vs Q-Plus E/W)
and keeps each biq card decision after the opening lead where the choice
mattered double-dummy (not every legal card gives the same result). For each
it stores the full position: all four original hands, auction, contract,
tricks so far, the current trick, and the double-dummy result of every legal
card. Positions where biq lost tricks and a control sample where it did not
are both kept, so a change is judged on the errors AND on what biq already
did right.

`bench` asks the CURRENT engine (backend.nopeek.decide, no peeking) for its
card in each position and scores it: double-dummy tricks lost vs the best
card. Compare configurations (env knobs, code changes) on the same position
file; the sampler seed is fixed per position.

  python3 tools/play_replay_bench.py extract tools/runs/results/run*.qss \\
          --out tools/runs/mine/replay_positions.jsonl
  python3 tools/play_replay_bench.py bench tools/runs/mine/replay_positions.jsonl \\
          --shard 0/3 --jsonl out0.jsonl
  python3 tools/play_replay_bench.py summary out*.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_ORDER = "NESW"
_RK = "AKQJT98765432"
_SU = {"s": 0, "h": 1, "d": 2, "c": 3}
_STRAIN = {"s": 1, "h": 2, "d": 3, "c": 4, "nt": 5}


def _code(tok):
    return _SU[tok[0]] * 13 + _RK.index(tok[1])


def _name(c):
    return "SHDC"[c // 13] + _RK[c % 13]


def _pbn(hands):
    out = []
    for s in _ORDER:
        suits = [[] for _ in range(4)]
        for c in sorted(hands[s]):
            suits[c // 13].append(_RK[c % 13])
        out.append(".".join("".join(x) for x in suits))
    return "N:" + " ".join(out)


# ------------------------------------------------------------------ extract

def extract(paths, out, control_every=4):
    from backend.dds import DDSolver
    from qplus_auction_mine import parse_block
    dds = DDSolver()
    n_err = n_ctl = 0
    k_ctl = 0
    with open(out, "w") as fh:
        for path in paths:
            text = open(path, errors="replace").read().replace("\r", "")
            for rec in text.split('\nDI "')[1:]:
                lines = [l[3:] for l in rec.split("\n") if l.startswith("D1 ")]
                d = parse_block(lines)
                if d is None:
                    continue
                cl = next((l for l in lines if l.startswith("Contract")), None)
                if cl is None or "passed" in cl:
                    continue
                w = cl.split(":", 1)[1].split()
                strain = w[0][1:].lower()
                level = int(w[0][0])
                dbl = "xx" if "xx" in w[1:] else ("x" if "x" in w[1:] else "")
                decl = next(x for x in w if x in ("North", "South", "East", "West"))[0]
                i = next((k for k, l in enumerate(lines) if l.startswith("Tricks")), None)
                if i is None:
                    continue
                tricks = []
                for l in lines[i:i + 13]:
                    body = l.split(":", 1)[1].split()
                    if len(body) < 6:
                        break
                    tricks.append((body[1], [_code(x.rstrip("+-").lower()[0] + x.rstrip("+-")[1])
                                             for x in body[2:6]]))
                biq = {s for s, n in d["players"].items() if "biq" in n.lower()} or {"N", "S"}
                orig = {s: [_code(x.lower()[0] + x[1]) for x in _cards(d["hands"][s])]
                        for s in _ORDER}
                hands = {s: set(orig[s]) for s in _ORDER}
                done = []
                for t, (leader, cards) in enumerate(tricks):
                    seat = leader
                    played = []
                    for pos, card in enumerate(cards):
                        if seat in biq and not (t == 0 and pos == 0):
                            led = played[0] // 13 if played else None
                            legal = [c for c in hands[seat]
                                     if led is None or c // 13 == led]
                            if not legal:
                                legal = list(hands[seat])
                            if len(legal) > 1:
                                res = dds.solve(_STRAIN[strain], _ORDER.index(leader),
                                                played, [_pbn(hands)], solutions=3)
                                vals = {c: res[c][0] for c in legal if res and c in res}
                                if vals and len(set(vals.values())) > 1:
                                    best = max(vals.values())
                                    loss = best - vals.get(card, best)
                                    keep = loss > 0
                                    if not keep:
                                        k_ctl += 1
                                        keep = k_ctl % control_every == 0
                                    if keep:
                                        n_err += loss > 0
                                        n_ctl += loss == 0
                                        fh.write(json.dumps({
                                            "file": os.path.basename(path),
                                            "label": d["label"],
                                            "dealer": d["dealer"].name[0],
                                            "vul": d["vul"].name,
                                            "calls": d["calls"],
                                            "hands": {s: d["hands"][s] for s in _ORDER},
                                            "contract": [level, strain, decl, dbl],
                                            "tricks": [[l_, [_name(c) for c in cs]]
                                                       for l_, cs in done],
                                            "trick": [_name(c) for c in played],
                                            "leader": leader, "seat": seat,
                                            "played": _name(card),
                                            "dd": {_name(c): v for c, v in vals.items()},
                                            "loss": loss}) + "\n")
                        hands[seat].discard(card)
                        played.append(card)
                        seat = _ORDER[(_ORDER.index(seat) + 1) % 4]
                    done.append((leader, cards))
    print(f"wrote {n_err} positions where biq lost tricks + {n_ctl} control "
          f"positions -> {out}")


def _cards(hand_str):
    out = []
    for su, part in zip("shdc", hand_str.split(".")):
        for r in part:
            out.append(su + r)
    return out


# ------------------------------------------------------------------ bench

def _board(p):
    from backend.models import (Bid, BoardState, Card, Contract, Hand, Rank,
                                Seat, Suit, Trick, Vulnerability)
    from qplus_auction_mine import _call
    S = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
    SU = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
    RANKS = {r.value: r for r in Rank}

    def card(name):
        return Card(SU["SHDC".index(name[0])], RANKS[_RK.index(name[1])])
    level, strain, decl, dbl = p["contract"]
    trump = None if strain == "nt" else SU[_SU[strain]]
    contract = Contract(level=level,
                        suit=Suit.NOTRUMP if strain == "nt" else SU[_SU[strain]],
                        declarer=S[decl], doubled=dbl == "x", redoubled=dbl == "xx")
    calls = []
    for tok in p["calls"]:
        b, alert = _call(tok)
        if b is None:
            break
        calls.append(b)
    remaining = {s: [card(su.upper() + r) for su, part in zip("shdc", p["hands"][s].split("."))
                     for r in part] for s in _ORDER}
    used = set(n for _, cs in p["tricks"] for n in cs) | set(p["trick"])
    hands = {S[s]: Hand(cards=[c for c in remaining[s]
                               if "SHDC"[c.suit.value] + _RK[c.rank.value] not in used])
             for s in _ORDER}
    vul = {"NONE": Vulnerability.NONE, "NS": Vulnerability.NS,
           "EW": Vulnerability.EW, "BOTH": Vulnerability.BOTH}[p["vul"]]
    board = BoardState(board_number=1, dealer=S[p["dealer"]], vulnerability=vul,
                       hands=hands, auction=calls, contract=contract)
    for leader, cs in p["tricks"]:
        tr = Trick(leader=S[leader])
        for n in cs:
            tr.add_card(card(n), trump)
        board.tricks.append(tr)
    cur = Trick(leader=S[p["leader"]])
    for n in p["trick"]:
        cur.add_card(card(n), trump)
    board.current_trick = cur
    return board, S[p["seat"]], [card(n) for n in p["trick"]]


def bench(path, shard, out, limit=None):
    from backend import nopeek
    k, m = (int(x) for x in shard.split("/"))
    pos = [json.loads(l) for l in open(path)]
    with open(out, "w") as fh:
        for idx, p in enumerate(pos):
            if idx % m != k or (limit and idx >= limit):
                continue
            random.seed(zlib.crc32(f"{p['file']}{p['label']}{p['tricks']}{p['trick']}".encode()))
            board, seat, trick = _board(p)
            t0 = time.time()
            c = nopeek.decide(board, seat, trick)
            name = "SHDC"[c.suit.value] + _RK[c.rank.value]
            best = max(p["dd"].values())
            loss = best - p["dd"].get(name, best)
            fh.write(json.dumps({"i": idx, "file": p["file"], "label": p["label"],
                                 "seat": p["seat"], "kind": _kind(p),
                                 "orig_loss": p["loss"], "played": p["played"],
                                 "now": name, "loss": loss,
                                 "secs": round(time.time() - t0, 2)}) + "\n")
            fh.flush()


def _kind(p):
    decl_side = (p["seat"] in "NS") == (p["contract"][2] in "NS")
    role = "decl" if decl_side else "def"
    strain = "NT" if p["contract"][1] == "nt" else "suit"
    if not p["trick"]:
        k = "lead"
    else:
        led = p["trick"][0][0]
        hand = p["hands"][p["seat"]]
        used = set(n for _, cs in p["tricks"] for n in cs) | set(p["trick"])
        have = [su.upper() + r for su, part in zip("shdc", hand.split(".")) for r in part
                if su.upper() + r not in used]
        k = "follow" if any(h[0] == led for h in have) else "discard/ruff"
    return f"{role} {strain} {k}"


def summary(paths):
    rows = [json.loads(l) for p in paths for l in open(p)]
    by = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        for key in (r["kind"], "ALL"):
            b = by[key]
            b[0] += 1
            b[1] += r["loss"]
            b[2] += r["orig_loss"]
            b[3] += r["secs"]
    print(f"{'kind':24s} {'n':>5} {'now lost':>8} {'live lost':>9} {'s/card':>7}")
    for k in sorted(by, key=lambda k: (k == "ALL", k)):
        n, l, o, s = by[k]
        print(f"{k:24s} {n:5d} {l:8d} {o:9d} {s / max(n, 1):7.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("qss", nargs="+")
    e.add_argument("--out", required=True)
    e.add_argument("--control-every", type=int, default=4)
    b = sub.add_parser("bench")
    b.add_argument("positions")
    b.add_argument("--shard", default="0/1")
    b.add_argument("--jsonl", required=True)
    b.add_argument("--limit", type=int)
    s = sub.add_parser("summary")
    s.add_argument("jsonl", nargs="+")
    a = ap.parse_args()
    if a.cmd == "extract":
        extract(a.qss, a.out, a.control_every)
    elif a.cmd == "bench":
        bench(a.positions, a.shard, a.jsonl, a.limit)
    else:
        summary(a.jsonl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
