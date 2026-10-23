#!/usr/bin/env python3
"""Decode and quality-check the OpenSpiel WBridge5 dataset.

The dataset (DeepMind, gs://openspiel-data/bridge) is ~1.18M deals bid and
played by WBridge5 at all four seats: SAYC, strongest level, North dealer,
nobody vulnerable. It is NOT stored in this repo (no license is stated for
the data); download it to ~/bridge_data/openspiel_wbridge5 and point --dir
there. Nothing this tool writes goes into the repo either.

One deal per line, OpenSpiel action integers:
  52 deal actions  card c goes to player i % 4 (0=N 1=E 2=S 3=W);
                   card = rank * 4 + suit (suit 0=C 1=D 2=H 3=S, rank 0=2..12=A)
  auction          52 + call; call 0=Pass 1=X 2=XX, 3.. = bids
                   (level 1 + (call-3)//5, strain (call-3)%5 in C D H S NT)
  play             card indices 0..51, in play order

Usage:
  python3 tools/openspiel_wb5.py check  [--dir D] [--split train|valid|test|all]
  python3 tools/openspiel_wb5.py dd     [--dir D] [--split test] [--n 2000]
  python3 tools/openspiel_wb5.py show   [--dir D] [--split test] LINE...
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

DEFAULT_DIR = Path.home() / "bridge_data" / "openspiel_wbridge5"
SEATS = "NESW"
SUITS = "CDHS"            # OpenSpiel suit order
RANKS = "23456789TJQKA"   # OpenSpiel rank order
STRAINS = ["C", "D", "H", "S", "NT"]


# ----------------------------------------------------------------- decoding
def call_str(call: int) -> str:
    if call == 0:
        return "P"
    if call == 1:
        return "X"
    if call == 2:
        return "XX"
    level, strain = 1 + (call - 3) // 5, (call - 3) % 5
    return f"{level}{STRAINS[strain]}"


def card_str(c: int) -> str:
    return SUITS[c % 4] + RANKS[c // 4]


def decode(line: str) -> dict:
    """Raw decode, no validation: hands, calls, play (card ints)."""
    a = [int(x) for x in line.split()]
    deal, rest = a[:52], a[52:]
    hands = [[] for _ in range(4)]
    for i, c in enumerate(deal):
        hands[i % 4].append(c)
    calls = []
    i = 0
    while i < len(rest) and rest[i] >= 52:
        calls.append(rest[i] - 52)
        i += 1
    return {"deal": deal, "hands": hands, "calls": calls, "play": rest[i:]}


def hand_pbn(cards) -> str:
    """S.H.D.C holding, ranks high to low."""
    by = {s: [] for s in range(4)}
    for c in cards:
        by[c % 4].append(c // 4)
    return ".".join("".join(RANKS[r] for r in sorted(by[s], reverse=True))
                    for s in (3, 2, 1, 0))


def deal_pbn(hands) -> str:
    return "N:" + " ".join(hand_pbn(h) for h in hands)


def hcp(cards) -> int:
    return sum(max(0, c // 4 - 8) for c in cards)      # J=9->1 .. A=12->4


def lengths(cards):
    """(spades, hearts, diamonds, clubs)."""
    n = [0, 0, 0, 0]
    for c in cards:
        n[c % 4] += 1
    return n[3], n[2], n[1], n[0]


# --------------------------------------------------------------- validation
def check_auction(calls):
    """Returns (problem or None, contract) where contract is
    (level, strain_idx, declarer_seat, doubled 0/1/2) or None if passed out."""
    last_bid = -1           # call value of the last bid
    last_bidder = None
    dbl = 0
    first_namer = {}        # (side, strain) -> seat that first named it
    passes = 0
    seat = 0                # North deals
    for k, call in enumerate(calls):
        if call == 0:
            passes += 1
        elif call == 1:
            if last_bidder is None or last_bidder % 2 == seat % 2 or dbl:
                return f"illegal X at call {k}", None
            dbl, passes = 1, 0
        elif call == 2:
            if dbl != 1 or last_bidder % 2 != seat % 2:
                return f"illegal XX at call {k}", None
            dbl, passes = 2, 0
        else:
            if call <= last_bid or call > 37:
                return f"insufficient bid at call {k}", None
            strain = (call - 3) % 5
            first_namer.setdefault((seat % 2, strain), seat)
            last_bid, last_bidder, dbl, passes = call, seat, 0, 0
        seat = (seat + 1) % 4
        done = (last_bid < 0 and passes == 4) or (last_bid >= 0 and passes == 3)
        if done:
            if k != len(calls) - 1:
                return "calls after the auction ended", None
            if last_bid < 0:
                return None, None
            level, strain = 1 + (last_bid - 3) // 5, (last_bid - 3) % 5
            return None, (level, strain, first_namer[(last_bidder % 2, strain)], dbl)
    return "auction not finished", None


def check_play(hands, contract, play):
    """Returns (problem or None, declarer tricks)."""
    if contract is None:
        return ("play after a passed-out deal" if play else None), None
    if len(play) != 52:
        return f"play has {len(play)} cards, not 52", None
    level, strain, decl, dbl = contract
    holder = {}
    for p in range(4):
        for c in hands[p]:
            holder[c] = p
    left = [set(h) for h in hands]
    trump = None if strain == 4 else strain        # OpenSpiel suit index
    leader = (decl + 1) % 4
    decl_tricks = 0
    for t in range(13):
        trick = play[4 * t: 4 * t + 4]
        led = trick[0] % 4
        for j, c in enumerate(trick):
            p = (leader + j) % 4
            if holder.get(c) != p or c not in left[p]:
                return f"trick {t + 1}: {card_str(c)} not in {SEATS[p]}'s hand", None
            if j and c % 4 != led and any(x % 4 == led for x in left[p]):
                return f"trick {t + 1}: {SEATS[p]} revoked", None
            left[p].discard(c)

        def key(c):
            if trump is not None and c % 4 == trump:
                return 200 + c // 4
            return 100 + c // 4 if c % 4 == led else c // 4
        win = max(range(4), key=lambda j: key(trick[j]))
        leader = (leader + win) % 4
        if leader % 2 == decl % 2:
            decl_tricks += 1
    return None, decl_tricks


# ------------------------------------------------------- SAYC opening check
def opening_flags(hands, calls):
    """SAYC (as WBridge5 was configured) red flags for the opening call."""
    flags = []
    seat = None
    for k, call in enumerate(calls):
        if call != 0:
            seat = k % 4
            break
        h = hands[k % 4]
        if k < 2 and hcp(h) >= 13:
            flags.append(f"passes {hcp(h)} HCP in seat {k + 1}")
    if seat is None:
        return flags, None
    call = calls[seat]
    h = hands[seat]
    p = hcp(h)
    s, he, d, c = lengths(h)
    shape = sorted((s, he, d, c), reverse=True)
    balanced = shape in ([4, 3, 3, 3], [4, 4, 3, 2], [5, 3, 3, 2])
    name = call_str(call)
    if name == "1H" and he < 5:
        flags.append(f"1H with {he} hearts")
    if name == "1S" and s < 5:
        flags.append(f"1S with {s} spades")
    if name == "1NT":
        if not 15 <= p <= 17:
            flags.append(f"1NT with {p} HCP")
        if not balanced and shape != [6, 3, 2, 2]:
            flags.append(f"1NT with shape {''.join(map(str, shape))}")
    if name == "2NT" and not 20 <= p <= 21:
        flags.append(f"2NT with {p} HCP")
    if name == "2C" and p < 18:
        flags.append(f"strong 2C with {p} HCP")
    if name in ("2D", "2H", "2S"):
        ln = {"2D": d, "2H": he, "2S": s}[name]
        if ln < 6 and seat != 2:
            flags.append(f"weak {name} with {ln} cards")
        if p > 11:
            flags.append(f"weak {name} with {p} HCP")
    if name[0] == "1" and name != "1NT" and p < 10:
        flags.append(f"{name} with {p} HCP")
    return flags, (seat, name)


# ------------------------------------------------------------------ helpers
def split_files(d: Path, split: str):
    names = ["train", "valid", "test"] if split == "all" else [split]
    return [(n, d / f"{n}.txt") for n in names]


def cmd_check(a):
    d = Path(a.dir)
    out = d / "quality"
    out.mkdir(exist_ok=True)
    seen = {}               # deal hash -> (split, line)
    dup_within, dup_across = 0, 0
    tot = collections.Counter()
    open_ct = collections.Counter()
    flag_ct = collections.Counter()
    flagged_by_seat = collections.Counter()
    bad = open(out / "invalid.jsonl", "w")
    flagged = open(out / "opening_flags.jsonl", "w")
    for split, path in split_files(d, a.split):
        with open(path) as fh:
            for ln, line in enumerate(fh, 1):
                tot["deals"] += 1
                try:
                    r = decode(line)
                except ValueError:
                    tot["unparseable"] += 1
                    continue
                problem = None
                if sorted(r["deal"]) != list(range(52)):
                    problem = "deal is not 52 distinct cards"
                if problem is None:
                    problem, contract = check_auction(r["calls"])
                if problem is None:
                    problem, _tricks = check_play(r["hands"], contract, r["play"])
                    if contract is None:
                        tot["passed_out"] += 1
                if problem:
                    tot["invalid"] += 1
                    bad.write(json.dumps({"split": split, "line": ln,
                                          "problem": problem}) + "\n")
                    continue
                key = hashlib.md5(deal_pbn(r["hands"]).encode()).hexdigest()
                if key in seen:
                    if seen[key][0] == split:
                        dup_within += 1
                    else:
                        dup_across += 1
                else:
                    seen[key] = (split, ln)
                flags, op = opening_flags(r["hands"], r["calls"])
                if op:
                    open_ct[op[1]] += 1
                for f in flags:
                    flag_ct[re.sub(r"\d+", "n", f)] += 1
                if flags:
                    tot["flagged"] += 1
                    flagged_by_seat[op[0] if op else -1] += 1
                    flagged.write(json.dumps({"split": split, "line": ln,
                                              "deal": deal_pbn(r["hands"]),
                                              "auction": " ".join(call_str(c) for c in r["calls"]),
                                              "flags": flags}) + "\n")
        print(f"{split}: done", file=sys.stderr)
    bad.close()
    flagged.close()
    n = tot["deals"]
    print(f"deals {n}; unparseable {tot['unparseable']}; invalid "
          f"(deal/auction/play) {tot['invalid']}; passed out {tot['passed_out']}")
    print(f"duplicate deals: {dup_within} within a split, {dup_across} "
          f"across splits (train/valid/test overlap)")
    print(f"deals with a SAYC red flag on the opening: {tot['flagged']} "
          f"({100 * tot['flagged'] / max(n, 1):.1f}%)")
    for f, k in flag_ct.most_common():
        print(f"  {k:7d}  {f}")
    print("openings:", ", ".join(f"{k} {v}" for k, v in open_ct.most_common(14)))
    print(f"details in {out}/")


def cmd_dd(a):
    """Score WBridge5's own table (it bid and played all four seats) and a
    biq-rules table (biq at all four seats, same deals) against PAR, the
    double-dummy best result for both sides. Distance from par says how far
    a table's bidding strayed; it is not a teams match between the two
    programs. Also compares WBridge5's real card play with double dummy."""
    from backend.dds import DDSolver
    from backend.models import Seat, Suit, Hand, Vulnerability
    from backend import native_bidder as NB
    from backend.bidding_systems import get_system
    from tools.bidder_teams_ab import bid_auction, final_contract, score, imp, _astr

    system = get_system("SAYC")
    seats = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
    strain_key = ["C", "D", "H", "S", "NT"]
    to_suit = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES, Suit.NOTRUMP]
    recs = []
    path = dict(split_files(Path(a.dir), a.split))[a.split]
    with open(path) as fh:
        for ln, line in enumerate(fh, 1):
            if ln < a.start:
                continue
            if ln >= a.start + a.n:
                break
            r = decode(line)
            prob, contract = check_auction(r["calls"])
            if not prob:
                prob, tricks = check_play(r["hands"], contract, r["play"])
            if not prob:
                recs.append((ln, r, contract, tricks))
    tables = DDSolver().solve_dd_tables_par([deal_pbn(r["hands"]) for _, r, _, _ in recs], 0)

    def slam_side(dd):
        """Sides (0=N/S, 1=E/W) with a DD-makeable small slam."""
        return {side for side, pair in ((0, "NS"), (1, "EW"))
                if any(dd[p][st] >= 12 for p in pair for st in strain_key)}

    base = None
    if a.baseline:
        from tools.bidder_teams_ab import load_baseline
        base = load_baseline(a.baseline)

    def biq_table(mod, who, hands, dd, st):
        auction = bid_auction(hands, Seat.NORTH, Vulnerability.NONE, system, mod, mod)
        bc = final_contract(auction, Seat.NORTH)
        if bc is None:
            return 0, auction
        lv, su, de, db = bc
        ddt = dd[de.name[0]]["NT" if su == Suit.NOTRUMP else su.to_char()]
        s = score(lv, su, ddt, False, db)
        if lv >= 6:
            st[who + "_slams"] += 1
            st[who + "_phantom"] += ddt < lv + 6
            st[who + "_slam_found"] += ddt >= lv + 6
        if db == 1 and ddt >= lv + 6:
            st[who + "_dbl_made"] += 1
        return (s if de.is_ns() else -s), auction

    st = collections.Counter()
    play_loss = collections.Counter()
    rows = []
    for (ln, r, contract, tricks), (dd, par) in zip(recs, tables):
        st["deals"] += 1
        makeable = slam_side(dd)
        st["slam_makeable"] += bool(makeable)
        # WBridge5's table
        wb = 0
        if contract is not None:
            level, strain, decl, dbl = contract
            ddt = dd[SEATS[decl]][strain_key[strain]]
            sign = 1 if decl % 2 == 0 else -1
            wb = sign * score(level, to_suit[strain], ddt, False, dbl)
            st["played"] += 1
            st["dd_minus_real"] += ddt - tricks
            play_loss[ddt - tricks] += 1
            if level >= 6:
                st["wb_slams"] += 1
                st["wb_phantom"] += ddt < level + 6
            if dbl == 1 and ddt >= level + 6:
                st["wb_dbl_made"] += 1
        if makeable and contract and contract[0] >= 6 and contract[2] % 2 in makeable \
                and dd[SEATS[contract[2]]][strain_key[contract[1]]] >= contract[0] + 6:
            st["wb_slam_found"] += 1
        # biq rules at all four seats (and the baseline bidder, if given)
        hands = {seats[p]: Hand.from_pbn(hand_pbn(r["hands"][p])) for p in range(4)}
        bq, auction = biq_table(NB, "biq", hands, dd, st)
        if base is not None:
            bb, _ = biq_table(base, "base", hands, dd, st)
            st["base_par_imp"] += abs(imp(bb - par))
        dwb, dbq = abs(imp(wb - par)), abs(imp(bq - par))
        st["wb_par_imp"] += dwb
        st["biq_par_imp"] += dbq
        st["wb_closer"] += dwb < dbq
        st["biq_closer"] += dbq < dwb
        if abs(dwb - dbq) >= 8:
            rows.append({"line": ln, "wb_off_par": dwb, "biq_off_par": dbq,
                         "par_ns": par, "deal": deal_pbn(r["hands"]),
                         "wb": " ".join(call_str(c) for c in r["calls"]),
                         "biq": _astr(auction)})
    n, p = st["deals"], max(st["played"], 1)
    print(f"{n} deals from {a.split} (all NV, North deals)")
    print(f"WBridge5 card play (it plays both sides): declarers took "
          f"{-st['dd_minus_real'] / p:+.2f} tricks/deal vs double dummy")
    print("  DD minus actual:", dict(sorted(play_loss.items())))
    print(f"Distance from par, mean |IMP| per deal: WBridge5 "
          f"{st['wb_par_imp'] / n:.2f}, biq rules {st['biq_par_imp'] / n:.2f}; "
          f"WBridge5 closer on {st['wb_closer']}, biq closer on {st['biq_closer']}")
    print(f"Deals with a DD-makeable small slam for someone: {st['slam_makeable']}")
    if base is not None:
        print(f"Baseline bidder ({a.baseline}): {st['base_par_imp'] / n:.2f} IMP/deal "
              f"from par (current biq {st['biq_par_imp'] / n:.2f}; difference "
              f"{(st['biq_par_imp'] - st['base_par_imp']):+d} IMP over {n} deals, "
              f"negative = current closer to par)")
    for who in ("wb", "biq") + (("base",) if base is not None else ()):
        print(f"  {who:3s}: slams bid {st[who + '_slams']}, made DD "
              f"{st.get(who + '_slam_found', 0)}, phantom {st[who + '_phantom']}; "
              f"doubled into a DD make {st[who + '_dbl_made']}")
    out = Path(a.dir) / "quality" / f"par_{a.split}_{n}.jsonl"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w") as fh:
        for row in sorted(rows, key=lambda x: x["biq_off_par"] - x["wb_off_par"], reverse=True):
            fh.write(json.dumps(row) + "\n")
    print(f"deals where one table is 8+ IMP closer to par: {len(rows)} -> {out}")


def cmd_show(a):
    path = dict(split_files(Path(a.dir), a.split))[a.split]
    want = set(a.lines)
    with open(path) as fh:
        for ln, line in enumerate(fh, 1):
            if ln in want:
                r = decode(line)
                prob, contract = check_auction(r["calls"])
                print(f"line {ln}: {deal_pbn(r['hands'])}")
                print("  auction:", " ".join(call_str(c) for c in r["calls"]))
                if contract:
                    _, tricks = check_play(r["hands"], contract, r["play"])
                    lv, st, de, db = contract
                    print(f"  contract {lv}{STRAINS[st]}{'x' * db} by {SEATS[de]}, "
                          f"{tricks} tricks")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "dd", "show"])
    ap.add_argument("lines", nargs="*", type=int)
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    ap.add_argument("--split", default="test")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--start", type=int, default=1, help="first line (dd)")
    ap.add_argument("--baseline", default=None,
                    help="dd: also bid with this native_bidder.py copy")
    a = ap.parse_args()
    {"check": cmd_check, "dd": cmd_dd, "show": cmd_show}[a.cmd](a)


if __name__ == "__main__":
    main()
