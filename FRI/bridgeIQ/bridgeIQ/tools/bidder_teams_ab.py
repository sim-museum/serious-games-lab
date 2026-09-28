#!/usr/bin/env python3
"""Head-to-head TEAMS match between two versions of the native bidder.

Table A: NEW bidder sits N/S, BASELINE bidder sits E/W.
Table B: BASELINE sits N/S, NEW sits E/W.
Every contract is scored double-dummy; the swing to NEW on a board is
IMP(A_ns - B_ns). Because each version plays both directions against the
other, a change that only helps one side of the table cannot hide behind
biq-vs-biq symmetry, and a change that makes biq overbid or over-compete
shows up as a loss.

Also counts, per version, the auction pathologies the 2026-09 Q-Plus runs
exposed: PHANTOM slams (6+ bid, DD-unmakeable), doubled contracts that make
against the side that doubled, and deals passed out.

Usage:
  git show HEAD:FRI/bridgeIQ/bridgeIQ/backend/native_bidder.py > /tmp/nb_base.py
  python3 tools/bidder_teams_ab.py /tmp/nb_base.py [--boards 400] [--seed 7]
                                                     [--system SAYC] [--show 10]
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend                                                        # noqa: E402,F401
from backend.models import Seat, Suit, Vulnerability                  # noqa: E402
from backend.dds import DDSolver                                      # noqa: E402
from backend import native_bidder as NEW                              # noqa: E402
from backend.bidding_systems import get_system                        # noqa: E402
from tools.cardplay_eval import _deal, _pbn, _over, _STRAIN           # noqa: E402

_IMPTAB = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
           900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imp(diff: int) -> int:
    n = sum(1 for t in _IMPTAB if abs(diff) >= t)
    return n if diff >= 0 else -n


def load_baseline(path: str):
    spec = importlib.util.spec_from_file_location("backend._nb_baseline", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "backend"
    spec.loader.exec_module(mod)
    return mod


HYBRID = set()          # module objects that bid with simulation (hand=...)


def bid_auction(hands, dealer, vul, system, ns_mod, ew_mod):
    auction, seat = [], dealer
    for _ in range(60):
        mod = ns_mod if seat.is_ns() else ew_mod
        st = mod.parse_auction(seat, dealer, list(auction), vulnerability=vul)
        if id(mod) in HYBRID:
            auction.append(mod.decide_bid(st, mod.evaluate_hand(hands[seat]),
                                          system, hand=hands[seat]))
        else:
            auction.append(mod.decide_bid(st, mod.evaluate_hand(hands[seat]), system))
        if _over(auction):
            break
        seat = seat.next()
    return auction


def final_contract(auction, dealer):
    """(level, suit, declarer, doubled 0/1/2) or None if passed out."""
    seat, last, last_seat, dbl, first = dealer, None, None, 0, {}
    for b in auction:
        if b.is_double:
            dbl = 1
        elif b.is_redouble:
            dbl = 2
        elif not b.is_pass:
            last, last_seat, dbl = b, seat, 0
            first.setdefault((seat.is_ns(), b.suit), seat)
        seat = seat.next()
    if last is None:
        return None
    return last.level, last.suit, first[(last_seat.is_ns(), last.suit)], dbl


def score(level, suit, tricks, vul, dbl):
    """Duplicate score for declarer's side."""
    need = level + 6
    if tricks >= need:
        per = 20 if suit in (Suit.CLUBS, Suit.DIAMONDS) else 30
        trick_pts = per * level + (10 if suit == Suit.NOTRUMP else 0)
        trick_pts *= (1, 2, 4)[dbl]
        s = trick_pts
        s += (500 if vul else 300) if trick_pts >= 100 else 50
        if level == 6:
            s += 750 if vul else 500
        if level == 7:
            s += 1500 if vul else 1000
        s += (50, 50, 100)[dbl] if dbl else 0          # insult
        over = tricks - need
        if dbl:
            s += over * (200 if vul else 100) * dbl
        else:
            s += over * per
        return s
    down = need - tricks
    if not dbl:
        return -down * (100 if vul else 50)
    if vul:
        pen = 200 + 300 * (down - 1)
    else:
        pen = 100 + 200 * min(down - 1, 2) + 300 * max(down - 3, 0)
    return -pen * dbl


def table_result(hands, dealer, vul, system, ns_mod, ew_mod, dd):
    auction = bid_auction(hands, dealer, vul, system, ns_mod, ew_mod)
    c = final_contract(auction, dealer)
    if c is None:
        return 0, None, auction
    level, suit, decl, dbl = c
    tricks = dd[decl.name[0]][_STRAIN[suit]]
    v = vul in (Vulnerability.BOTH,) or (
        vul == Vulnerability.NS and decl.is_ns()) or (
        vul == Vulnerability.EW and not decl.is_ns())
    s = score(level, suit, tricks, v, dbl)
    return (s if decl.is_ns() else -s), (level, suit, decl, dbl, tricks), auction


def _cstr(c):
    if c is None:
        return "passed out"
    level, suit, decl, dbl, tricks = c
    s = "NT" if suit == Suit.NOTRUMP else suit.to_char()
    return (f"{level}{s}{'x' * dbl} {decl.name[0]} "
            f"{'=' if tricks == level + 6 else f'{tricks - level - 6:+d}'}")


def _astr(auction):
    out = []
    for b in auction:
        if b.is_pass:
            out.append("P")
        elif b.is_double:
            out.append("X")
        elif b.is_redouble:
            out.append("XX")
        else:
            out.append(f"{b.level}{'N' if b.suit == Suit.NOTRUMP else b.suit.to_char()}")
    return " ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("--boards", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--system", default="SAYC")
    ap.add_argument("--show", type=int, default=10,
                    help="print the N biggest swings each way")
    ap.add_argument("--new-hybrid", action="store_true",
                    help="NEW bids with the simulation layer (hand=...)")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--jsonl", default=None,
                    help="append one JSON line per board (for merging shards)")
    a = ap.parse_args()
    if a.baseline == "current":
        # Same code, rules only: a second import of the module object.
        import importlib.util as _u
        spec = _u.spec_from_file_location("backend._nb_current",
                                          str(Path(NEW.__file__)))
        base = _u.module_from_spec(spec)
        base.__package__ = "backend"
        spec.loader.exec_module(base)
    else:
        base = load_baseline(a.baseline)
    if a.new_hybrid:
        HYBRID.add(id(NEW))
    system = get_system(a.system)
    dds = DDSolver()
    total, changed, swings = 0, 0, []
    stats = {"new": {"phantom": 0, "dbl_made": 0, "slams_made": 0},
             "base": {"phantom": 0, "dbl_made": 0, "slams_made": 0}}
    import json as _json
    for bd in range(a.start, a.start + a.boards):
        dealer, vul, hands = _deal(a.seed, bd)
        dd = dds.solve_dd_table(_pbn(hands))
        sa, ca, aa = table_result(hands, dealer, vul, system, NEW, base, dd)
        sb, cb, ab = table_result(hands, dealer, vul, system, base, NEW, dd)
        # Pathology counts, attributed to the side that bid the contract.
        for c, ns_is_new in ((ca, True), (cb, False)):
            if c is None:
                continue
            level, suit, decl, dbl, tricks = c
            who = "new" if decl.is_ns() == ns_is_new else "base"
            if level >= 6:
                stats[who]["phantom" if tricks < level + 6 else "slams_made"] += 1
            if dbl == 1 and tricks >= level + 6:
                stats["base" if who == "new" else "new"]["dbl_made"] += 1
        sw = imp(sa - sb)
        total += sw
        # Robust judge: the side defending each final contract replies
        # competently (doubles / outbids with its best DD contract), so a
        # call that only works because the rule-bidder opponents get
        # confused earns nothing (live 2026-09-26 paired run: junk bids won
        # offline, lost live).
        from backend import bid_sim as _bs
        ra = _bs.robust_result(ca[:4] if ca else None, dd, vul, noise=False)
        rb = _bs.robust_result(cb[:4] if cb else None, dd, vul, noise=False)
        rsw = imp(ra - rb)
        if a.jsonl:
            with open(a.jsonl, "a") as fh:
                fh.write(_json.dumps({"bd": bd, "seed": a.seed, "sw": sw,
                                      "rsw": rsw,
                                      "a": _cstr(ca), "b": _cstr(cb),
                                      "aa": _astr(aa), "ab": _astr(ab),
                                      "pbn": _pbn(hands)}) + "\n")
        if _astr(aa) != _astr(ab):
            changed += 1
        if sw:
            swings.append((sw, bd, _pbn(hands), _cstr(ca), _astr(aa),
                           _cstr(cb), _astr(ab)))
    print(f"{a.boards} boards, seed {a.seed}, {a.system}: NEW vs BASELINE "
          f"{total:+d} IMP ({total / a.boards:+.3f}/bd); auctions differ on "
          f"{changed} boards")
    for k in ("new", "base"):
        st = stats[k]
        print(f"  {k:4s}: slams bid+made {st['slams_made']:3d}  phantom slams "
              f"{st['phantom']:3d}  doubled opponents into a make "
              f"{st['dbl_made']:3d}")
    swings.sort()
    for title, rows in (("NEW's worst boards", swings[:a.show]),
                        ("NEW's best boards", swings[::-1][:a.show])):
        print(f"\n{title}:")
        for sw, bd, pbn, ca, aa, cb, ab in rows:
            if (sw < 0) != (title.startswith("NEW's worst")):
                continue
            print(f"  bd {bd:4d} {sw:+3d}  {pbn}")
            print(f"      A (new NS): {ca:14s} {aa}")
            print(f"      B (old NS): {cb:14s} {ab}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
