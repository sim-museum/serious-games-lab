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


# Family "decl": Q-Plus DECLARES. Q-Plus sits N/S (--remote N,S) and bids
# its own hands: N a balanced 15-17 (1NT), S a 9-12 raise with no four-card
# major, so the contract is 3NT by N. biq sits E/W, passes throughout, leads
# a low card of its longest side suit and follows clubs with its lowest
# club ("low": "C"). Every side suit is double-stopped by N/S (the ace plus
# another of A-K-Q), so the play is about the club combination: which hand
# Q-Plus leads clubs from, finesse or drop, and in what order. Each
# combination is dealt with several E/W club splits (the missing honours on
# either side, short and long) and fresh side cards; a line that changes with
# the hidden split would show that Q-Plus looks at hidden cards.
_DECL_COMBOS = (                        # name, N (declarer) clubs, S (dummy) clubs
    ("AQx-xxx", "AQ4", "532"),
    ("AQT-xxx", "AQT", "532"),
    ("AJ9-xxx", "AJ9", "532"),
    ("KJx-xxx", "KJ4", "532"),
    ("KQxx-xxx", "KQ54", "632"),
    ("AKJx-xxx", "AKJ4", "532"),        # 7 cards missing the Q: finesse
    ("AKJxx-xxx", "AKJ43", "652"),      # 8 cards: finesse
    ("AKJxx-xxxx", "AKJ43", "7652"),    # 9 cards: drop
    ("AKTx-xxx", "AKT4", "532"),
    ("AKxxx-xx", "AK654", "32"),
    ("xxx-AQx", "532", "AQ4"),          # the tenace in dummy
    ("xxx-AKJx", "532", "AKJ4"),
)


def _decl_splits(rng, miss, k=8):
    """Up to k E/W splits of the missing clubs: one per (holder of each
    missing honour, E's length), shuffled."""
    groups = {}
    for le in range(len(miss) + 1):
        for e in itertools.combinations(miss, le):
            if not 1 <= le <= len(miss) - 1 or max(le, len(miss) - le) > 5:
                continue
            key = (tuple(r in e for r in miss if r in "KQJT"), le)
            groups.setdefault(key, []).append("".join(e))
    keys = sorted(groups)
    rng.shuffle(keys)
    return [rng.choice(groups[x]) for x in keys[:k]]


def _decl_fill(rng, clubs, tries=200000):
    side = [(s, r) for s in "SHD" for r in RK]
    for _ in range(tries):
        rng.shuffle(side)
        hands, i = {}, 0
        for seat in SEATS:
            n = 13 - len(clubs[seat])
            hands[seat] = [("C", r) for r in clubs[seat]] + side[i:i + n]
            i += n
        ln = {x: {s: sum(1 for c in hands[x] if c[0] == s) for s in "SHDC"} for x in SEATS}
        if not 15 <= hcp(hands["N"]) <= 17 or not 9 <= hcp(hands["S"]) <= 12:
            continue
        if sorted(ln["N"].values()) not in ([3, 3, 3, 4], [2, 3, 4, 4], [2, 3, 3, 5]) \
                or max(ln["N"]["S"], ln["N"]["H"]) > 4:
            continue
        if max(ln["S"]["S"], ln["S"]["H"]) > 3 or min(ln["S"].values()) < 2 or max(ln["S"].values()) > 5:
            continue
        if hcp(hands["E"]) > 10 or hcp(hands["W"]) > 10 or max(ln["E"].values()) > 6 \
                or max(ln["W"].values()) > 6:
            continue
        ns = {s: {r for x in "NS" for s2, r in hands[x] if s2 == s} for s in "SHD"}
        if not all("A" in ns[s] and len(ns[s] & set("KQ")) >= 1 for s in "SHD"):
            continue
        return hands
    raise RuntimeError("no fill found")


def decl_boards(rng, k=8):
    boards = []
    for name, n, s in _DECL_COMBOS:
        miss = [r for r in RK if r not in n + s]
        for e in _decl_splits(rng, miss, k):
            w = "".join(r for r in miss if r not in e)
            hands = _decl_fill(rng, {"N": n, "S": s, "E": e, "W": w})
            leads = []
            for x in "EW":
                ln = {su: sorted((r for s2, r in hands[x] if s2 == su), key=RK.index) for su in "SHD"}
                su = max("SHD", key=lambda q: (len(ln[q]), -"SHD".index(q)))
                h = ln[su]
                leads.append(su + (h[3] if len(h) >= 4 else h[-1]))
            boards.append({"family": "decl", "combo": name, "N": n, "S": s, "E": e, "W": w,
                           "calls": {"E": ["P"] * 6, "W": ["P"] * 6}, "leads": leads, "low": "C",
                           "hands": {x: pbn_hand(hands[x]) for x in SEATS}})
    return boards


# ---------------------------------------------------------------------------
# Bidding probes (2026-10-11), from the worst boards of the 2/1 run
# (tools/runs/bluechip/261009_qplus_21_biqS, boards 385-569). biq N/S make
# scripted calls and Q-Plus E/W bid freely on its A-2-1-A card; each family
# holds the scripted calls fixed and moves one thing in a Q-Plus hand, so
# Q-Plus's calls can be read against it. Hands are dealt seat by seat to
# exact shapes and HCP ranges.

def _lens(h):
    return {s: sum(1 for c in h if c[0] == s) for s in "SHDC"}


def _balanced(h):
    return sorted(_lens(h).values()) in ([3, 3, 3, 4], [2, 3, 4, 4], [2, 3, 3, 5])


def _shapes(ok):
    """Every (S, H, D, C) shape accepted by ok(shape dict)."""
    out = []
    for s, h, d in itertools.product(range(14), repeat=3):
        c = 13 - s - h - d
        if c >= 0 and ok({"S": s, "H": h, "D": d, "C": c}):
            out.append((s, h, d, c))
    return out


def _draw(rng, pool, fixed, shapes, ok, tries=400):
    """13 cards: `fixed` plus cards from `pool`, with one of `shapes` (exact
    suit lengths; None = any) and accepted by ok(hand)."""
    for _ in range(tries):
        if shapes:
            h = list(fixed)
            for s, n in zip("SHDC", rng.choice(shapes)):
                need = n - sum(1 for c in fixed if c[0] == s)
                cs = [c for c in pool if c[0] == s]
                if need < 0 or need > len(cs):
                    break
                h += rng.sample(cs, need)
            else:
                if ok is None or ok(h):
                    return h
        else:
            h = list(fixed) + rng.sample(pool, 13 - len(fixed))
            if ok is None or ok(h):
                return h
    return None


def _deal(rng, specs, order, tries=3000):
    """Deal seat by seat in `order`; the last seat takes what is left. specs:
    {seat: {"shapes": [...], "fixed": [cards], "ok": hand -> bool}}; a seat's
    fixed cards are kept out of the other seats' draws."""
    full = [(s, r) for s in "SHDC" for r in RK]
    reserved = {c for sp in specs.values() for c in sp.get("fixed", ())}
    for _ in range(tries):
        left, hands = list(full), {}
        for i, seat in enumerate(order):
            sp = specs.get(seat, {})
            if i == 3:
                h = left
                if sp.get("shapes") and tuple(_lens(h)[s] for s in "SHDC") not in sp["shapes"]:
                    break
                if sp.get("ok") and not sp["ok"](h):
                    break
            else:
                mine = set(sp.get("fixed", ()))
                pool = [c for c in left if c not in reserved and c not in mine]
                h = _draw(rng, pool, sp.get("fixed", ()), sp.get("shapes"), sp.get("ok"))
                if h is None:
                    break
            hands[seat] = h
            left = [c for c in left if c not in h]
        else:
            return hands
    raise RuntimeError("no deal found")


def _band(lo, hi, extra=None):
    return lambda h: lo <= hcp(h) <= hi and (extra is None or extra(h))


def _pass(n=10):
    return ["P"] * n


def _board(family, hands, dealer, vul, calls, **design):
    return {"family": family, "dealer": dealer, "vul": vul, "calls": calls,
            "hands": {x: pbn_hand(hands[x]) for x in SEATS}, **design}


# Family "mlandy": Q-Plus over a 1NT opening (A-2-1-A plays Multi-Landy:
# O-1NT.Multi-Landy). N opens 1NT (15-17 balanced, no five-card major), S
# passes. Part "overcall": East's hand type moves (both majors, one major,
# major + minor, minors, a strong balanced hand, a light 4-4), at both
# vulnerabilities. Part "advance": East's hand is FIXED per type and West's
# major lengths and strength move, so West's answer to East's call shows.
# Board 408 (-15): biq passed partner's 2C (both majors) as natural, 2CX -6.
_NT_OPENER = {"ok": lambda h: 15 <= hcp(h) <= 17 and _balanced(h) and max(_lens(h)["S"], _lens(h)["H"]) <= 4}
_ML_TYPES = {
    "44M": (lambda x: x["S"] == 4 and x["H"] == 4 and min(x.values()) >= 1, 8, 14),
    "54M": (lambda x: x["S"] == 5 and x["H"] == 4 and min(x.values()) >= 1, 8, 14),
    "45M": (lambda x: x["S"] == 4 and x["H"] == 5 and min(x.values()) >= 1, 8, 14),
    "55M": (lambda x: x["S"] == 5 and x["H"] == 5, 6, 14),
    "6S": (lambda x: x["S"] == 6 and x["H"] <= 3 and max(x["D"], x["C"]) <= 3, 8, 14),
    "6H": (lambda x: x["H"] == 6 and x["S"] <= 3 and max(x["D"], x["C"]) <= 3, 8, 14),
    "5S5m": (lambda x: x["S"] == 5 and x["H"] <= 2 and max(x["D"], x["C"]) == 5, 8, 14),
    "5H5m": (lambda x: x["H"] == 5 and x["S"] <= 2 and max(x["D"], x["C"]) == 5, 8, 14),
    "5S4m": (lambda x: x["S"] == 5 and x["H"] <= 2 and max(x["D"], x["C"]) == 4, 9, 14),
    "5H4m": (lambda x: x["H"] == 5 and x["S"] <= 2 and max(x["D"], x["C"]) == 4, 9, 14),
    "6m": (lambda x: max(x["D"], x["C"]) == 6 and max(x["S"], x["H"]) <= 3 and min(x["D"], x["C"]) <= 3, 8, 14),
    "55m": (lambda x: x["D"] >= 5 and x["C"] >= 5, 7, 13),
    "bal": (lambda x: sorted(x.values()) in ([3, 3, 3, 4], [2, 3, 4, 4]), 15, 18),
    "44M_light": (lambda x: x["S"] == 4 and x["H"] == 4 and min(x.values()) >= 1, 4, 7),
}
_ML_ADVANCE = {         # East type -> West (spades, hearts) lengths to try
    "44M": [(2, 2), (3, 2), (2, 3), (3, 3), (4, 2), (2, 4), (1, 3), (3, 1)],
    "54M": [(2, 2), (3, 2), (2, 3), (3, 3), (4, 2), (2, 4), (1, 3), (3, 1)],
    "45M": [(2, 2), (3, 2), (2, 3), (3, 3), (4, 2), (2, 4), (1, 3), (3, 1)],
    "55M": [(2, 2), (3, 2), (2, 3), (3, 3), (4, 2), (2, 4), (1, 3), (3, 1)],
    "6S": [(1, 1), (2, 1), (1, 2), (3, 1), (1, 3), (2, 2), (3, 2), (2, 3)],
    "6H": [(1, 1), (2, 1), (1, 2), (3, 1), (1, 3), (2, 2), (3, 2), (2, 3)],
    "5S5m": [(1, 3), (2, 3), (3, 2), (4, 2)],
    "5H5m": [(3, 1), (3, 2), (2, 3), (2, 4)],
}
_ML_W_BANDS = ((2, 6), (9, 12))


def mlandy_boards(rng, per_type=2):
    boards = []
    calls = {"N": ["1NT"] + _pass(9), "S": _pass()}
    for et, (shape_ok, lo, hi) in _ML_TYPES.items():
        e_spec = {"shapes": _shapes(shape_ok), "ok": _band(lo, hi)}
        for vul in ("None", "Both"):
            for _ in range(per_type):
                hands = _deal(rng, {"E": e_spec, "N": _NT_OPENER}, "ENWS")
                boards.append(_board("mlandy", hands, "N", vul, calls, part="overcall", etype=et,
                                     E=pbn_hand(hands["E"])))
    for et, w_lens in _ML_ADVANCE.items():
        shape_ok, lo, hi = _ML_TYPES[et]
        mid = (max(lo, 10), min(hi, 12))      # a clear overcall, so West gets to answer
        e_hand = _deal(rng, {"E": {"shapes": _shapes(shape_ok), "ok": _band(*mid)}, "N": _NT_OPENER}, "ENWS")["E"]
        for sp, hr in w_lens:
            for wlo, whi in _ML_W_BANDS:
                w_ok = _band(wlo, whi, lambda h, sp=sp, hr=hr: _lens(h)["S"] == sp and _lens(h)["H"] == hr
                             and max(_lens(h)["D"], _lens(h)["C"]) <= 6)
                hands = _deal(rng, {"E": {"fixed": e_hand}, "N": _NT_OPENER, "W": {"ok": w_ok}}, "ENWS")
                boards.append(_board("mlandy", hands, "N", "None", calls, part="advance", etype=et,
                                     E=pbn_hand(e_hand), w_sp=sp, w_hr=hr, w_band=f"{wlo}-{whi}"))
    return boards


# Family "wslam": slam bidding opposite partner's weak two. East (dealer) holds
# a weak two (six cards in S, H or D, 6-10 HCP, a top honour); West's strength,
# fit and shape move; N/S pass. Board 481 (-14): biq jumped to 4S over
# partner's 2S with AK8.-.AQT932.AJ73; Q-Plus asked with 2NT and bid 7S.
_WS_TYPES = {           # name: (West's length in East's suit -> ok, shape ok, HCP range)
    "fit3_void": (lambda k: k == 3, lambda x: min(x.values()) == 0, 15, 19),
    "fit3_bal": (lambda k: k == 3, lambda x: min(x.values()) >= 2, 17, 20),
    "fit3_big": (lambda k: k == 3, lambda x: True, 20, 22),
    "fit4_short": (lambda k: k == 4, lambda x: min(x.values()) == 1, 14, 18),
    "fit2_own": (lambda k: k == 2, lambda x: max(x.values()) >= 6, 17, 21),
    "fit2_bal": (lambda k: k == 2, lambda x: min(x.values()) >= 2 and max(x.values()) <= 4, 16, 19),
    "fit01_own": (lambda k: k <= 1, lambda x: max(x.values()) >= 6, 16, 20),
}


def wslam_boards(rng, per=3):
    boards = []
    calls = {"N": _pass(), "S": _pass()}
    for suit in "SHD":
        others = [s for s in "SH" if s != suit]
        e_shapes = _shapes(lambda x: x[suit] == 6 and all(x[s] <= 3 for s in others) and min(x.values()) >= 1)
        e_ok = _band(6, 10, lambda h: sum(1 for c in h if c[0] == suit and c[1] in "AKQ") >= 1
                     and sum(HCP.get(c[1], 0) for c in h if c[0] == suit) >= 4)
        for wt, (k_ok, sh_ok, lo, hi) in _WS_TYPES.items():
            w_shapes = _shapes(lambda x: k_ok(x[suit]) and sh_ok(x) and max(x.values()) <= 7)
            for _ in range(per):
                hands = _deal(rng, {"E": {"shapes": e_shapes, "ok": e_ok},
                                    "W": {"shapes": w_shapes, "ok": _band(lo, hi)}}, "EWNS")
                boards.append(_board("wslam", hands, "E", "None", calls, suit=suit, wtype=wt,
                                     E=pbn_hand(hands["E"]), W=pbn_hand(hands["W"])))
    return boards


# Family "hicomp": the 5-6 level after a raised preempt (board 535, -19).
# Part "raise": W (Q-Plus, dealer) holds a 3S preempt, N overcalls 4H, East is
# the raiser (spade support, heart shortness and strength move), S jumps to 5H
# or 6H; read East's raise and both Q-Plus hands' answer to 5H/6H.
# Part "sac": N opens 3S, East (6-7 hearts, 14-17) overcalls, S raises to 4S
# and later bids 5S; West (heart support, spade shortness, strength move)
# decides whether to save / bid on at the 5- and 6-level.
def hicomp_boards(rng):
    boards = []
    w_pre = {"shapes": _shapes(lambda x: x["S"] == 7 and x["H"] <= 2 and max(x["D"], x["C"]) <= 3),
             "ok": _band(5, 9, lambda h: sum(1 for c in h if c[0] == "S" and c[1] in "AKQ") >= 1)}
    n_ovc = {"shapes": _shapes(lambda x: x["H"] >= 6 and x["S"] <= 1), "ok": _band(13, 17)}
    s_fit = {"shapes": _shapes(lambda x: x["H"] >= 4 and x["S"] <= 2), "ok": _band(6, 12)}
    for k in (3, 4):
        for hr in (0, 1, 2):
            for lo, hi in ((6, 9), (10, 13), (14, 17)):
                e = {"shapes": _shapes(lambda x, k=k, hr=hr: x["S"] == k and x["H"] == hr and max(x.values()) <= 6),
                     "ok": _band(lo, hi)}
                for jump in ("5H", "6H"):
                    for vul in ("None", "Both"):
                        hands = _deal(rng, {"W": w_pre, "N": n_ovc, "E": e, "S": s_fit}, "WNES")
                        calls = {"N": ["4H"] + _pass(9), "S": [jump] + _pass(9)}
                        boards.append(_board("hicomp", hands, "W", vul, calls, part="raise", e_sp=k, e_hr=hr,
                                             e_band=f"{lo}-{hi}", jump=jump, E=pbn_hand(hands["E"])))
    n_pre = {"shapes": _shapes(lambda x: x["S"] == 7 and x["H"] <= 2 and max(x["D"], x["C"]) <= 3),
             "ok": _band(6, 10, lambda h: sum(1 for c in h if c[0] == "S" and c[1] in "AKQ") >= 1)}
    e_ovc = {"shapes": _shapes(lambda x: x["H"] in (6, 7) and x["S"] <= 1 and max(x["D"], x["C"]) <= 4),
             "ok": _band(14, 17)}
    s_rai = {"shapes": _shapes(lambda x: x["S"] >= 3), "ok": _band(10, 15)}
    for k in (3, 4, 5):
        for sp in (0, 1, 2):
            for lo, hi in ((2, 6), (7, 11)):
                w = {"shapes": _shapes(lambda x, k=k, sp=sp: x["H"] == k and x["S"] == sp and max(x.values()) <= 6),
                     "ok": _band(lo, hi)}
                for vul in ("None", "Both"):
                    hands = _deal(rng, {"N": n_pre, "E": e_ovc, "W": w, "S": s_rai}, "NEWS")
                    calls = {"N": ["3S"] + _pass(9), "S": ["4S", "5S"] + _pass(8)}
                    boards.append(_board("hicomp", hands, "N", vul, calls, part="sac", w_hr=k, w_sp=sp,
                                         w_band=f"{lo}-{hi}", W=pbn_hand(hands["W"])))
    return boards


# Family "second": second-hand play in a SUIT contract (BACKLOG; the earlier
# probes saw Q-Plus second in hand only in 3NT). N opens 4S, all pass; East
# leads from a QJT9 sequence and declarer's side wins with the A-K. Then the
# leader (N, or dummy S when it holds the A-K) leads its lowest card of the
# probe suit toward the third hand's honours (dummy's K-x, K-Q-x, Q-x ...);
# the second-hand Q-Plus defender holds A-x, A-x-x, K-x ... or two small
# (control); the fourth hand gets the rest of the suit. Part "trump": the
# same with trumps (N leads low from Q-J-T-x-x-x toward dummy's K-x / K-x-x,
# East holds A-x / A-x-x).
_SH_THIRD = ("Kx", "Kxx", "KQx", "KJx", "Qx", "QJx")
_SH_SECOND = ("Ax", "Axx", "Axxx", "Kx", "Kxx", "xx")


def _ranks_for(rng, pattern, used):
    """Ranks for an honour pattern like 'KQx': the honours, spots from 2-9."""
    hon = [r for r in pattern if r != "x"]
    spots = [r for r in "98765432" if r not in used and r not in hon]
    return hon + rng.sample(spots, pattern.count("x"))


def second_boards(rng, fills=2):
    designs = []
    for third in _SH_THIRD:
        for sec in _SH_SECOND:
            if set(third) & set(sec) - {"x"}:
                continue
            for lead_from in ("N", "S"):
                designs.append(("side", third, sec, lead_from))
    for third in ("Kx", "Kxx"):
        for sec in ("Ax", "Axx"):
            designs.append(("trump", third, sec, "N"))
    boards = []
    calls = {"N": ["4S"] + _pass(9), "S": _pass()}
    ew_ok = _band(0, 10, lambda h: max(_lens(h).values()) <= 6)
    for part, third, sec, lead_from in designs:
        for _ in range(fills):
            lsuit, psuit = rng.sample("HDC", 2)
            if part == "trump":
                psuit = "S"
            o = {"N": "S", "S": "N"}
            leader, third_seat = lead_from, o[lead_from]
            second_seat = "E" if leader == "N" else "W"
            fourth_seat = "W" if second_seat == "E" else "E"
            used = []
            t_r = _ranks_for(rng, third, used)
            s_r = _ranks_for(rng, sec, used + t_r)
            if part == "trump":
                l_r = ["Q", "J", "T"] + rng.sample([r for r in "98765432" if r not in t_r + s_r], 3)
            else:
                l_r = rng.sample([r for r in "T98765432" if r not in t_r + s_r], 3)
            f_r = [r for r in RK if r not in t_r + s_r + l_r]
            if not 0 <= len(f_r) <= 6:
                continue
            fixed = {leader: [(psuit, r) for r in l_r], third_seat: [(psuit, r) for r in t_r],
                     second_seat: [(psuit, r) for r in s_r], fourth_seat: [(psuit, r) for r in f_r]}
            # trick 1: East leads from QJT9 in lsuit, the leader holds A-K-x there
            fixed["E"] += [(lsuit, r) for r in "QJT9"]
            fixed[leader] += [(lsuit, r) for r in "AK"]
            if part == "side":       # declarer N holds six trumps with the A-K
                fixed["N"] += [("S", r) for r in "AK"]
            specs = {"N": {"fixed": fixed["N"], "ok": lambda h: _lens(h)["S"] == 6 and _lens(h)[lsuit] <= 3},
                     "S": {"fixed": fixed["S"], "ok": lambda h: 2 <= _lens(h)["S"] <= 3},
                     "E": {"fixed": fixed["E"], "ok": ew_ok},
                     "W": {"fixed": fixed["W"], "ok": ew_ok}}
            if part == "trump":
                specs["N"]["ok"] = lambda h: _lens(h)[lsuit] <= 3
                specs["S"]["ok"] = None
            try:
                hands = _deal(rng, specs, "NSEW")
            except RuntimeError:
                continue
            lead = psuit + min(l_r, key=lambda r: -RK.index(r))
            boards.append(_board("second", hands, "N", "None", calls, part=part, psuit=psuit, lsuit=lsuit,
                                 third=third, second=sec, lead_from=leader, second_seat=second_seat,
                                 P={leader: "".join(l_r), third_seat: "".join(t_r), second_seat: "".join(s_r),
                                    fourth_seat: "".join(f_r)},
                                 leads=[lead]))
    return boards


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("family", choices=["count", "count2", "att", "all", "decl", "mlandy", "wslam", "hicomp",
                                       "bid21", "second", "bid21second"])
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
    if a.family == "decl":
        boards = decl_boards(rng)
    if a.family == "all":
        # One long session: attitude in NT and in clubs, opening leads, and
        # count with dummy's suit changed (a missing ten or a missing king).
        boards = (att_boards("3NT", "att") + att_boards("5C", "attS") + leads_boards(rng, a.lead_hands)
                  + count2_boards("KQJ98", ("N", "E", "W"), "count3")
                  + count2_boards("QJT98", ("N", "E", "W"), "count3"))
    if a.family == "mlandy":
        boards = mlandy_boards(rng)
    if a.family == "wslam":
        boards = wslam_boards(rng)
    if a.family == "hicomp":
        boards = hicomp_boards(rng)
    if a.family in ("bid21", "bid21second"):
        boards = mlandy_boards(rng) + wslam_boards(rng) + hicomp_boards(rng)
    n_first = len(boards)
    if a.family == "second":
        boards = second_boards(rng)
    if a.family == "bid21second":
        boards += second_boards(rng)
    order = list(range(len(boards))) * a.repeat
    if a.family in ("all", "decl", "bid21", "second"):
        rng.shuffle(order)      # interleave the families / combinations
    if a.family == "bid21second":
        # bidding boards first (interleaved), then the card-play boards
        first = [i for i in order if i < n_first]
        then = [i for i in order if i >= n_first]
        rng.shuffle(first)
        rng.shuffle(then)
        order = first + then
    pbn, script, design = [], [], []
    for n, bi in enumerate(order, 1):
        b = boards[bi]
        deal = "N:" + " ".join(b["hands"][x] for x in SEATS)
        pbn += [f'[Board "{n}"]', f'[Dealer "{b.get("dealer", "N")}"]',
                f'[Vulnerable "{b.get("vul", "None")}"]', f'[Deal "{deal}"]', ""]
        x = {"board": n, "calls": {k: list(v) for k, v in b["calls"].items()}}
        for k in ("leads", "follows", "low"):
            if k in b:
                x[k] = list(b[k]) if k == "leads" else b[k]
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
