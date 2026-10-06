#!/usr/bin/env python3
"""Controlled probe deals for studying Q-Plus's card play through the table
manager (tools/biq_bluechip_tm.py --script).

biq sits North/South and follows a script: a fixed auction and, as soon as
its side is on lead, a lead in the probe suit. Q-Plus defends East/West. Each
board changes ONE thing in the probe suit (who holds the ace, each defender's
length and spots, dummy's entries), so Q-Plus's card in that trick can be
read against the variable. Every design is dealt twice (different board
numbers) to test that Q-Plus is deterministic.

  python3 tools/qplus_probe.py count --out tools/runs/probes/count1
  -> deals.pbn, script.jsonl, design.jsonl

Family "count": N opens 1NT, S raises to 3NT, N declares. Dummy (S) holds a
long club suit; declarer leads a club at the first chance (from N if N is on
lead, else from dummy), so East follows second and West fourth (or the
reverse when dummy leads).
"""
from __future__ import annotations
import argparse
import itertools
import json
import random
from pathlib import Path

RK = "AKQJT98765432"
HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}
SEATS = "NESW"


def hcp(cards):
    return sum(HCP.get(r, 0) for _, r in cards)


def fill(rng, fixed, side_need, tries=20000):
    """Deal the three side suits (S, H, D) around the fixed club holdings so
    that N is a balanced 15-17 with an ace or king in every side suit (it
    wins the opening lead), E and W are weak (<= 7 HCP, no 6-card suit, so
    Q-Plus passes) and S has the rest. `side_need`: S must (or must not) hold
    a side-suit ace as an entry."""
    side = [(s, r) for s in "SHD" for r in RK]
    for _ in range(tries):
        rng.shuffle(side)
        hands, i = {}, 0
        for seat in SEATS:
            n = 13 - len(fixed[seat])
            hands[seat] = list(fixed[seat]) + side[i:i + n]
            i += n
        n_h, e_h, w_h, s_h = (hands[x] for x in SEATS[0] + "EWS")
        if not 15 <= hcp(n_h) <= 17:
            continue
        lens = {x: {s: sum(1 for c in hands[x] if c[0] == s) for s in "SHDC"} for x in SEATS}
        if sorted(lens["N"].values()) not in ([3, 3, 3, 4], [2, 3, 4, 4], [2, 3, 3, 5]):
            continue
        if not all(any(c[0] == s and c[1] in "AK" for c in n_h) for s in "SHD"):
            continue
        if hcp(e_h) > 7 or hcp(w_h) > 7 or max(lens["E"].values()) > 5 or max(lens["W"].values()) > 5:
            continue
        s_entry = any(c[0] in "SHD" and c[1] == "A" for c in s_h)
        if s_entry != side_need:
            continue
        return hands
    raise RuntimeError("no fill found")


def pbn_hand(cards):
    return ".".join("".join(sorted((r for s2, r in cards if s2 == s), key=RK.index)) for s in "SHDC")


def count_designs():
    """Club layouts: dummy's long suit, N's two clubs, and the split of the
    rest between E and W with the ace placed in turn with N, E, W or dummy."""
    out = []
    dummies = {"KQJT8": "KQJT8", "KQJT87": "KQJT87"}
    for dname, dummy in dummies.items():
        for ace in ("N", "E", "W", "dummy"):
            d = dummy if ace != "dummy" else "A" + dummy[:-1]          # keep length
            pool = [r for r in RK if r not in d]
            if ace == "N":
                n = ["A", pool[-1]]
            else:
                n = [pool[-2], pool[-1]]
            rest = [r for r in pool if r not in n]
            # E/W lengths: every split of `rest`, both parities for each side.
            for le in range(1, len(rest)):
                lw = len(rest) - le
                if not (2 <= le <= 4 and 2 <= lw <= 4):
                    continue
                spots = [r for r in rest if r != "A"]
                hon = ["A"] if "A" in rest else []
                # deterministic split: alternate spots so both sides get high and low ones
                for variant in range(2):
                    e, w = [], []
                    if ace == "E":
                        e.append("A")
                    if ace == "W":
                        w.append("A")
                    order = spots if variant == 0 else spots[::-1]
                    for r in order:
                        if len(e) < le and (len(e) <= len(w) or len(w) >= lw):
                            e.append(r)
                        elif len(w) < lw:
                            w.append(r)
                        else:
                            e.append(r)
                    if len(e) != le or len(w) != lw or sorted(e + w + hon * 0, key=RK.index) == []:
                        continue
                    out.append({"dummy": d, "N": "".join(n), "E": "".join(sorted(e, key=RK.index)),
                                "W": "".join(sorted(w, key=RK.index)), "ace": ace})
    # unique
    seen, uniq = set(), []
    for x in out:
        k = (x["dummy"], x["N"], x["E"], x["W"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


# Family "count2": ONE side-suit frame for every board; only the clubs move.
# N: S AQ32 H AK86 D K74 + 2 clubs (1NT opener), S (dummy): S K54 H Q73 D QJ
# + KQJT8 (or AKQJT when dummy has the ace). The other 20 side cards go to
# E/W in a fixed order, E taking as many as its club length leaves room for
# (they hold 6 HCP between them, so Q-Plus passes).
_N_SIDE = [("S", r) for r in "AQ32"] + [("H", r) for r in "AK86"] + [("D", r) for r in "K74"]
_S_SIDE = [("S", r) for r in "K54"] + [("H", r) for r in "Q73"] + [("D", r) for r in "QJ"]
_EW_POOL = [(x[0], x[1]) for x in ("DA SJ HJ DT ST HT D9 S9 H9 D8 S8 H5 D6 S7 "
                                     "H4 D5 S6 H2 D3 D2").split()]


def count2_boards():
    boards = []
    for ace in ("N", "E", "W", "dummy"):
        dummy = "AKQJT" if ace == "dummy" else "KQJT8"
        n = "A2" if ace == "N" else "32"
        rest = [r for r in RK if r not in dummy and r not in n]       # 6 clubs for E/W
        for le in (2, 3, 4):
            for e in itertools.combinations(rest, le):
                w = [r for r in rest if r not in e]
                if ace == "E" and "A" not in e or ace == "W" and "A" not in w:
                    continue
                # E takes side cards alternately from the front, W from the back,
                # so both keep a similar spread of suits and honours.
                pool = list(_EW_POOL)
                e_side, w_side = [], []
                while len(e_side) < 13 - le or len(w_side) < 13 - len(w):
                    if len(e_side) < 13 - le:
                        e_side.append(pool.pop(0))
                    if len(w_side) < 13 - len(w):
                        w_side.append(pool.pop())
                hands = {"N": _N_SIDE + [("C", r) for r in n], "S": _S_SIDE + [("C", r) for r in dummy],
                         "E": e_side + [("C", r) for r in e], "W": w_side + [("C", r) for r in w]}
                assert sorted(c for h in hands.values() for c in h) == sorted((s, r) for s in "SHDC" for r in RK)
                boards.append({"ace": ace, "dummy": dummy, "N": n, "E": "".join(e), "W": "".join(w),
                               "dummy_entry": False, "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    return boards


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("family", choices=["count", "count2"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--repeat", type=int, default=2, help="deal each design this many times")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    boards = []
    designs = [] if a.family == "count2" else count_designs()
    if a.family == "count2":
        boards = count2_boards()
    rng.shuffle(designs)
    designs = designs[: a.max]
    for i, d in enumerate(designs):
        for entry in (False, True) if i % 2 else (False,):
            fixed = {"N": [("C", r) for r in d["N"]], "S": [("C", r) for r in d["dummy"]],
                     "E": [("C", r) for r in d["E"]], "W": [("C", r) for r in d["W"]]}
            hands = fill(rng, fixed, entry)
            boards.append({**d, "dummy_entry": entry, "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    order = list(range(len(boards))) * a.repeat
    pbn, script, design = [], [], []
    for n, bi in enumerate(order, 1):
        b = boards[bi]
        deal = "N:" + " ".join(b["hands"][x] for x in SEATS)
        pbn += [f'[Board "{n}"]', '[Dealer "N"]', '[Vulnerable "None"]', f'[Deal "{deal}"]', ""]
        n_low = "C" + b["N"][-1]
        d_low = "C" + b["dummy"][-1]
        script.append({"board": n, "calls": {"N": ["1NT", "P", "P", "P"], "S": ["3NT", "P", "P", "P"]},
                       "leads": [n_low, d_low]})
        design.append({"board": n, "design": bi, **{k: v for k, v in b.items() if k != "hands"}, "deal": deal})
    (out / "deals.pbn").write_text("\n".join(pbn))
    (out / "script.jsonl").write_text("".join(json.dumps(x) + "\n" for x in script))
    (out / "design.jsonl").write_text("".join(json.dumps(x) + "\n" for x in design))
    print(f"{len(boards)} designs x {a.repeat} = {len(order)} boards -> {out}")


if __name__ == "__main__":
    main()
