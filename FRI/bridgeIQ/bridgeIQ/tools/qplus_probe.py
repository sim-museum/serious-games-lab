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


def count2_boards(base="KQJT8", aces=("N", "E", "W", "dummy"), family="count2"):
    boards = []
    for ace in aces:
        dummy = "AKQJT" if ace == "dummy" else base
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
                if hcp(hands["E"]) > 10 or hcp(hands["W"]) > 10:
                    continue                     # Q-Plus would not pass 1NT throughout
                boards.append({"family": family, "ace": ace, "dummy": dummy, "N": n, "E": "".join(e),
                               "W": "".join(w), "dummy_entry": False, "calls": _CALLS["3NT"],
                               "leads": ["C" + n[-1], "C" + dummy[-1]],
                               "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    return boards


# Family "att": attitude on partner's opening lead. N opens 1NT, S raises to
# 3NT, East (Q-Plus) leads from a fixed five-card heart sequence and West's
# (Q-Plus) card at trick 1 is the probe. Dummy ducks with its lowest heart and
# so does declarer. What moves: East's sequence, dummy's three hearts (three
# spots, or the ace and two spots) and every holding of 1-4 cards West can
# have from the five hearts left; N holds the rest. Side suits are fixed:
# N S AQ3 D AK74 C K + spots, dummy S K54 D QJ C AQJT9, E/W share the other
# 21-w side cards in an interleaved order (one jack between them, so Q-Plus
# passes 1NT).
#
# The same deals are also played in 5C by N (clubs trump: "attS"), and East's
# holding includes two low-card leads (KJ853, QT853) so West's third-hand
# play shows up too.
_ATT_SEQ = ("KQJT9", "KQT98", "QJT98", "KJ853", "QT853")
# Scripted auctions, all declared by N so East is on lead.
_CALLS = {"3NT": {"N": ["1NT", "P", "P"], "S": ["3NT", "P", "P"]},
          "5C": {"N": ["1C", "P", "P"], "S": ["5C", "P", "P"]},
          "4S": {"N": ["1S", "P", "P"], "S": ["4S", "P", "P"]},
          "4H": {"N": ["1H", "P", "P"], "S": ["4H", "P", "P"]},
          "6NT": {"N": ["1NT", "P", "P"], "S": ["6NT", "P", "P"]},
          "1C-1H-1NT-3NT": {"N": ["1C", "1NT", "P", "P"], "S": ["1H", "3NT", "P", "P"]}}
_ATT_EW_POOL = "SJ DT ST D9 S9 D8 S8 C8 D6 S7 C7 D5 S6 C6 D3 S2 C5 D2 C4 C3 C2".split()


def att_boards(contract="3NT", family="att"):
    boards = []
    for seq in _ATT_SEQ:
        miss = [r for r in RK if r not in seq]
        spots = [r for r in miss if r not in "AKQJT"]
        for dv in ("low", "ace"):
            dummy = [spots[1], spots[3], spots[-1]] if dv == "low" else ["A", spots[2], spots[-1]]
            free = [r for r in miss if r not in dummy]
            for w in (1, 2, 3, 4):
                for wh in itertools.combinations(free, w):
                    nh = [r for r in free if r not in wh]
                    pool = [(x[0], x[1]) for x in _ATT_EW_POOL]
                    # N's club spots come off the low end of the pool's clubs
                    n_c = [c for c in pool if c[0] == "C"][::-1][:w]
                    pool = [c for c in pool if c not in n_c]
                    e_side, w_side = [], []
                    while len(e_side) < 8 or len(w_side) < 13 - w:
                        if len(e_side) < 8:
                            e_side.append(pool.pop(0))
                        if len(w_side) < 13 - w:
                            w_side.append(pool.pop())
                    assert not pool, pool
                    hands = {
                        "N": [("S", r) for r in "AQ3"] + [("D", r) for r in "AK74"] + [("C", "K")] + n_c
                             + [("H", r) for r in nh],
                        "S": [("S", r) for r in "K54"] + [("D", r) for r in "QJ"] + [("C", r) for r in "AQJT9"]
                             + [("H", r) for r in dummy],
                        "E": e_side + [("H", r) for r in seq],
                        "W": w_side + [("H", r) for r in wh]}
                    assert sorted(c for h in hands.values() for c in h) == sorted((s, r) for s in "SHDC" for r in RK)
                    assert all(len(h) == 13 for h in hands.values())
                    follows = {"1S": "H" + dummy[-1]}
                    if nh:
                        follows["1N"] = "H" + nh[-1]
                    boards.append({"family": family, "contract": contract, "seq": seq, "dummy": "".join(dummy),
                                   "dv": dv, "W": "".join(wh), "N": "".join(nh), "calls": _CALLS[contract],
                                   "follows": follows, "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    return boards


# Family "leads": Q-Plus's opening lead. Random East hands that pass
# throughout (<= 7 HCP, or <= 9 with no five-card suit) and a West that passes
# too; each East hand is dealt once under every scripted auction, so the lead
# can be read against the auction with the hand held fixed. N/S get the rest.
_LEAD_AUCTIONS = ("3NT", "4S", "4H", "6NT", "1C-1H-1NT-3NT")


def leads_boards(rng, n_hands):
    boards = []
    deck = [(s, r) for s in "SHDC" for r in RK]
    while len(boards) < n_hands * len(_LEAD_AUCTIONS):
        rng.shuffle(deck)
        h = {x: deck[13 * i:13 * i + 13] for i, x in enumerate(SEATS)}
        le = {x: max(sum(1 for c in h[x] if c[0] == s) for s in "SHDC") for x in "EW"}
        if not (hcp(h["E"]) <= 7 and le["E"] <= 5 or hcp(h["E"]) <= 9 and le["E"] <= 4):
            continue
        if hcp(h["W"]) > 7 or le["W"] > 5:
            continue
        hands = {x: pbn_hand(h[x]) for x in SEATS}
        for au in _LEAD_AUCTIONS:
            boards.append({"family": "leads", "auction": au, "E": hands["E"], "calls": _CALLS[au],
                           "hands": hands})
    return boards


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("family", choices=["count", "count2", "att", "all"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--lead-hands", type=int, default=60)
    ap.add_argument("--repeat", type=int, default=1, help="deal each design this many times")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    boards = []
    if a.family == "count":
        designs = count_designs()
        rng.shuffle(designs)
        for i, d in enumerate(designs[: a.max]):
            for entry in (False, True) if i % 2 else (False,):
                fixed = {"N": [("C", r) for r in d["N"]], "S": [("C", r) for r in d["dummy"]],
                         "E": [("C", r) for r in d["E"]], "W": [("C", r) for r in d["W"]]}
                hands = fill(rng, fixed, entry)
                boards.append({**d, "family": "count", "dummy_entry": entry, "calls": _CALLS["3NT"],
                               "leads": ["C" + d["N"][-1], "C" + d["dummy"][-1]],
                               "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    if a.family == "count2":
        boards = count2_boards()
    if a.family == "att":
        boards = att_boards()
    if a.family == "all":
        # One long session: attitude in NT and in clubs, opening leads, and
        # count with dummy's suit changed (a missing ten or a missing king).
        boards = (att_boards("3NT", "att") + att_boards("5C", "attS") + leads_boards(rng, a.lead_hands)
                  + count2_boards("KQJ98", ("N", "E", "W"), "count3")
                  + count2_boards("QJT98", ("N", "E", "W"), "count3"))
    order = list(range(len(boards))) * a.repeat
    if a.family == "all":
        rng.shuffle(order)      # interleave the families
    pbn, script, design = [], [], []
    for n, bi in enumerate(order, 1):
        b = boards[bi]
        deal = "N:" + " ".join(b["hands"][x] for x in SEATS)
        pbn += [f'[Board "{n}"]', '[Dealer "N"]', '[Vulnerable "None"]', f'[Deal "{deal}"]', ""]
        x = {"board": n, "calls": {k: list(v) for k, v in b["calls"].items()}}
        for k in ("leads", "follows"):
            if k in b:
                x[k] = b[k] if k == "follows" else list(b[k])
        script.append(x)
        design.append({"board": n, "design": bi, **{k: v for k, v in b.items() if k not in ("hands", "calls")},
                       "deal": deal})
    (out / "deals.pbn").write_text("\n".join(pbn))
    (out / "script.jsonl").write_text("".join(json.dumps(x) + "\n" for x in script))
    (out / "design.jsonl").write_text("".join(json.dumps(x) + "\n" for x in design))
    fams = {}
    for d in design:
        fams[d["family"]] = fams.get(d["family"], 0) + 1
    print(f"{len(boards)} designs x {a.repeat} = {len(order)} boards -> {out}  {fams}")


if __name__ == "__main__":
    main()
