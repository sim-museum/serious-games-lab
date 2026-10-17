#!/usr/bin/env python3
"""Agreement benchmark: biq against Q-Plus's own recorded decisions.

Live matches cannot measure one change (a board's IMP result has an SD of
~6.8 and Q-Plus itself plays a replayed deal differently ~40% of the time).
This replays every call and card that a Q-Plus player made in the table-
manager runs and asks biq for ITS choice in the same position, seen from the
same seat, through the same entry points the TM uses (decide_bid with the
hand, i.e. with simulation; nopeek.decide in a forked child). Deterministic
(biq's bidder seeds its own simulation; card searches are seeded per
position), so two biq versions can be compared decision by decision.

  bid   every distinct Q-Plus call. Agreement, and for a disagreement the
        cost: the auction is finished twice by biq's rules (after Q-Plus's
        call and after biq's) and both contracts are scored on the real deal
        (robust judge as in qplus_auction_mine; + = biq's call better).
  card  a fixed sample of Q-Plus's non-forced cards. Agreement, and the
        double-dummy tricks each program's card gives up at that moment.
  compare A.jsonl B.jsonl
        decision-by-decision change between two runs of the same mode.

  python3 tools/qplus_agreement.py bid  [--runs DIR ...] [--system Precision90M]
                                        [--jobs 7] [--out bid.jsonl]
  python3 tools/qplus_agreement.py card [--sample 1500] [--jobs 7] [--out card.jsonl]
  python3 tools/qplus_agreement.py compare old.jsonl new.jsonl

Q-Plus's seats in a run come from the first line of its tm.log ("biq plays
...")."""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import zlib
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

# Card searches stop on a 12 s clock in live play (BIQ_AMU_BUDGET), which
# makes them load-dependent; here they run to their depth / world limits so
# a rerun gives the same cards. The clock rarely binds live.
os.environ.setdefault("BIQ_AMU_BUDGET", "600")
# The bidding simulation's clock is only a safety cap (3 x 6 s), but it
# binds on a loaded machine; lift it so results do not depend on load.
os.environ.setdefault("BIQ_BID_SIM_BUDGET", "600")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import biq_bluechip_tm as tm                                          # noqa: E402
from backend import bid_sim                                           # noqa: E402
from backend import native_bidder as nb                               # noqa: E402
from backend.bidding_systems import get_system                        # noqa: E402
from backend.models import (Bid, BoardState, Hand, Seat, Suit, Trick,  # noqa: E402
                            Vulnerability)
from qplus_auction_mine import _pure_ns, _rule_key, _side             # noqa: E402

RUNS = ROOT / "tools" / "runs" / "bluechip"
PRECISION_RUNS = ["261004_qplus_prec", "261004_qplus_prec3",
                  "261005_qplus_biqS", "261007_qplus_biqS"]
SEATS = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
VUL = {v: k for k, v in tm.VUL_TEXT.items()}
_L = "NESW"


# ------------------------------------------------------------------ loading
def qplus_seats(run_dir: Path) -> set:
    first = open(run_dir / "tm.log").readline()
    m = re.search(r"biq plays (.+)$", first)
    biq = {w.strip()[0].upper() for w in m.group(1).split(",")} if m else {"N", "S"}
    return set(_L) - biq


def records(dirs):
    """(run name, record, Q-Plus seat letters) for every played board."""
    for d in dirs:
        p = Path(d) if os.path.isabs(d) else RUNS / d
        qs = qplus_seats(p)
        for f in ("results_before_restart.jsonl", "results.jsonl"):
            if (p / f).exists():
                for line in open(p / f):
                    yield p.name, json.loads(line), qs


def _hands(deal):
    first, rest = deal.split(":", 1)
    start = _L.index(first)
    hs = rest.split()
    return {SEATS[(start + i) % 4]: Hand.from_pbn(h) for i, h in enumerate(hs)}


def _toks(auction):
    return auction.split() if auction else []


def _seed(*key):
    return zlib.crc32(repr(key).encode())


def _category(prefix, seat, dealer):
    ours = theirs = False
    s = dealer
    for b in prefix:
        if not b.is_pass:
            if s.is_ns() == seat.is_ns():
                ours = True
            else:
                theirs = True
        s = s.next()
    if not ours and not theirs:
        return "opening"
    if not theirs:
        return "uncontested"
    if not ours:
        return "first action vs opponents"
    return "competitive"


# ------------------------------------------------------------------ bidding
_SYS = None
_TABS = {}


def _init(system_name):
    global _SYS
    _SYS = get_system(system_name)
    bid_sim.set_play_system(system_name)
    from backend import nopeek                                        # noqa: F401  (pre-import for fork)


def _tab(deal):
    if deal not in _TABS:
        from backend.dds import DDSolver
        _TABS[deal] = DDSolver().solve_dd_table(deal)
    return _TABS[deal]


def bid_decisions(dirs, system=None):
    seen, out = set(), []
    for run, r, qs in records(dirs):
        # Mixed runs (2/1 then Precision) label each board; older runs don't.
        if system and r.get("system", system) != system:
            continue
        dealer = tm.BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[r["dealer"]]]
        toks = _toks(r["auction"])
        seat = dealer
        for i, t in enumerate(toks):
            if seat.name[0] in qs:
                key = (r["deal"], tuple(toks[:i]), seat.name[0])
                if key not in seen:
                    seen.add(key)
                    out.append({"run": run, "label": r["label"], "deal": r["deal"],
                                "dealer": r["dealer"], "vul": r["vul"],
                                "seat": seat.name[0], "prefix": toks[:i], "qplus": t})
            seat = seat.next()
    return out


def bid_one(d):
    try:
        hands = _hands(d["deal"])
        dealer = SEATS[_L.index(d["dealer"])]
        seat = SEATS[_L.index(d["seat"])]
        vul = VUL.get(d["vul"], Vulnerability.NONE)
        prefix = [Bid.from_str(t) for t in d["prefix"]]
        qb = Bid.from_str(d["qplus"])
        random.seed(_seed(d["deal"], d["prefix"], d["seat"]))
        st = nb.parse_auction(seat, dealer, list(prefix), vulnerability=vul)
        try:
            b = nb.decide_bid(st, nb.evaluate_hand(hands[seat]), _SYS, hand=hands[seat])
        except Exception as e:                                       # noqa: BLE001
            b = nb.passb(f"CRASH {type(e).__name__}")
        if not tm.legal_call(prefix, dealer, seat, b):
            b = Bid.make_pass()
        row = {k: d[k] for k in ("run", "label", "deal", "dealer", "vul", "seat", "qplus")}
        row.update(auction=" ".join(d["prefix"]), biq=bid_sim._key(b),
                   cat=_category(prefix, seat, dealer),
                   agree=bid_sim._key(b) == bid_sim._key(qb),
                   rule=_rule_key(b.explanation), imp=0, imp_dd=0)
        row["key"] = f'{d["deal"]}|{row["auction"]}|{d["seat"]}'
        if not row["agree"]:
            tab = _tab(d["deal"])
            evals = {s: nb.evaluate_hand(h) for s, h in hands.items()}
            cq = bid_sim._rollout(nb, st, _SYS, hands, evals, qb)
            cb = bid_sim._rollout(nb, st, _SYS, hands, evals, b)
            opp_ns = not seat.is_ns()
            rq = _side(bid_sim.robust_result(cq, tab, vul, True, opp_ns), seat)
            rb = _side(bid_sim.robust_result(cb, tab, vul, True, opp_ns), seat)
            row["imp"] = bid_sim._imp(rb - rq)
            row["imp_dd"] = bid_sim._imp(_side(_pure_ns(cb, tab, vul), seat)
                                         - _side(_pure_ns(cq, tab, vul), seat))
        return row
    except Exception as e:                                           # noqa: BLE001
        return {"key": f'{d["deal"]}|{" ".join(d["prefix"])}|{d["seat"]}',
                "error": repr(e)}


def report_bid(rows):
    rows = [r for r in rows if "error" not in r]
    n = len(rows)
    ag = sum(r["agree"] for r in rows)
    p = ag / max(n, 1)
    print(f"{n} Q-Plus calls: biq agrees on {ag} ({100 * p:.1f}% +- "
          f"{100 * math.sqrt(p * (1 - p) / max(n, 1)):.1f})")
    cost = sum(r["imp"] for r in rows)
    print(f"cost of disagreeing (biq's call minus Q-Plus's, robust judge): {cost:+d} IMP "
          f"= {cost / max(n, 1):+.3f} per call; plain DD {sum(r['imp_dd'] for r in rows):+d}")
    by = defaultdict(list)
    for r in rows:
        by[r["cat"]].append(r)
    print(f"\n  {'category':28s} {'calls':>6} {'agree':>7} {'IMP':>6} {'IMP/call':>9}")
    for c, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        a = sum(x["agree"] for x in rs) / len(rs)
        im = sum(x["imp"] for x in rs)
        print(f"  {c:28s} {len(rs):6d} {100 * a:6.1f}% {im:+6d} {im / len(rs):+9.3f}")
    rule = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["agree"]:
            rule[r["rule"]][0] += 1
            rule[r["rule"]][1] += r["imp"]
    print("\n  costliest biq rules when disagreeing (IMP, n):")
    for k, (c, im) in sorted(rule.items(), key=lambda kv: kv[1][1])[:15]:
        print(f"  {im:+5d} {c:4d}  {k}")


# ------------------------------------------------------------------ card play
def _strain_i(suit):
    return {Suit.SPADES: 1, Suit.HEARTS: 2, Suit.DIAMONDS: 3, Suit.CLUBS: 4,
            Suit.NOTRUMP: 5}[suit]


def card_decisions(dirs):
    seen, out = set(), []
    for run, r, qs in records(dirs):
        if len(r.get("play", [])) < 52 or len(r["contract"].split()) != 2:
            continue
        decl_l = r["contract"].split()[1]
        decl = SEATS[_L.index(decl_l)]
        dummy = decl.partner()
        hands = _hands(r["deal"])
        live = {s: list(hands[s].cards) for s in SEATS}
        trump = tm.derive_contract([Bid.from_str(t) for t in _toks(r["auction"])],
                                   SEATS[_L.index(r["dealer"])])
        trump = None if trump.suit == Suit.NOTRUMP else trump.suit
        leader = decl.next()
        p = r["play"]
        for t in range(13):
            cur = []
            for k in range(4):
                seat = SEATS[(leader.value + k) % 4]
                actor = decl if seat == dummy else seat
                card = tm.parse_card(p[4 * t + k])
                legal = tm.legal_cards(Hand(cards=live[seat]), cur)
                if actor.name[0] in qs and len(legal) > 1:
                    key = (r["deal"], r["auction"], tuple(p[:4 * t + k]))
                    if key not in seen:
                        seen.add(key)
                        out.append({"run": run, "label": r["label"], "deal": r["deal"],
                                    "dealer": r["dealer"], "vul": r["vul"],
                                    "auction": r["auction"], "play": p[:4 * t + k],
                                    "qplus": p[4 * t + k], "seat": seat.name[0],
                                    "role": "declarer" if actor == decl else "defender",
                                    "pos": k, "trick": t + 1})
                live[seat].remove(card)
                cur.append(card)
            leader = tm.trick_winner(cur, leader, trump)
    return out


def card_one(d):
    key = f'{d["deal"]}|{d["auction"]}|{" ".join(d["play"])}'
    try:
        from backend.dds import DDSolver
        sys.path.insert(0, str(ROOT / "tools"))
        from play_audit import _pbn
        hands = _hands(d["deal"])
        dealer = SEATS[_L.index(d["dealer"])]
        vul = VUL.get(d["vul"], Vulnerability.NONE)
        auction = [Bid.from_str(t) for t in _toks(d["auction"])]
        contract = tm.derive_contract(auction, dealer)
        decl = contract.declarer
        trump = None if contract.suit == Suit.NOTRUMP else contract.suit
        live = {s: Hand(cards=list(hands[s].cards)) for s in SEATS}
        board = BoardState(board_number=1, dealer=dealer, vulnerability=vul,
                           hands=live, auction=list(auction), contract=contract, tricks=[])
        leader = decl.next()
        cards = [tm.parse_card(x) for x in d["play"]]
        cur = []
        for i, c in enumerate(cards):
            seat = SEATS[(leader.value + len(cur)) % 4]
            live[seat].cards.remove(c)
            cur.append(c)
            if len(cur) == 4:
                w = tm.trick_winner(cur, leader, trump)
                board.tricks.append(Trick(cards=list(cur), leader=leader, winner=w))
                leader, cur = w, []
        seat = SEATS[(leader.value + len(cur)) % 4]
        random.seed(_seed(key))
        bc = tm.biq_card(board, seat, list(cur))
        qc = tm.parse_card(d["qplus"])
        hh = {s.name[0]: {c.code52() for c in live[s].cards} for s in SEATS}
        res = DDSolver().solve(_strain_i(contract.suit), leader.value,
                               [c.code52() for c in cur], [_pbn(hh)], solutions=3)
        best = max(v[0] for v in res.values())
        row = {k: d[k] for k in ("run", "label", "seat", "role", "pos", "trick", "qplus")}
        row.update(key=key, biq=tm.fmt_card(bc) if bc else None,
                   agree=bc == qc,
                   equiv=bc is not None and bc.code52() in res
                   and res[bc.code52()][0] == res[qc.code52()][0],
                   q_loss=best - res[qc.code52()][0],
                   b_loss=(best - res[bc.code52()][0]) if bc is not None
                   and bc.code52() in res else None,
                   lead=d["trick"] == 1 and d["pos"] == 0)
        return row
    except Exception as e:                                           # noqa: BLE001
        return {"key": key, "error": repr(e)}


def report_card(rows):
    bad = [r for r in rows if "error" in r or r.get("b_loss") is None]
    rows = [r for r in rows if r not in bad]
    n = len(rows)
    ag = sum(r["agree"] for r in rows)
    p = ag / max(n, 1)
    diff = [r["b_loss"] - r["q_loss"] for r in rows]
    m = sum(diff) / max(n, 1)
    sd = math.sqrt(sum((x - m) ** 2 for x in diff) / max(n - 1, 1))
    print(f"{n} Q-Plus cards ({len(bad)} failed): biq agrees on {ag} "
          f"({100 * p:.1f}% +- {100 * math.sqrt(p * (1 - p) / max(n, 1)):.1f})")
    eq = sum(r["equiv"] for r in rows)
    print(f"same card or a double-dummy equal one: {eq} ({100 * eq / max(n, 1):.1f}%)")
    print(f"DD tricks given up: Q-Plus {sum(r['q_loss'] for r in rows)}, "
          f"biq {sum(r['b_loss'] for r in rows)}; biq minus Q-Plus "
          f"{m:+.4f} per card (SE {sd / math.sqrt(max(n, 1)):.4f})")
    by = defaultdict(list)
    for r in rows:
        k = "opening lead" if r["lead"] else \
            f'{r["role"]} {["lead", "2nd", "3rd", "4th"][r["pos"]]}'
        by[k].append(r)
    print(f"\n  {'situation':18s} {'cards':>6} {'agree':>7} {'Q-Plus DD':>10} {'biq DD':>7}")
    for k, rs in sorted(by.items()):
        a = sum(x["agree"] for x in rs) / len(rs)
        print(f"  {k:18s} {len(rs):6d} {100 * a:6.1f}% {sum(x['q_loss'] for x in rs):10d} "
              f"{sum(x['b_loss'] for x in rs):7d}")


# ------------------------------------------------------------------ compare
def compare(fa, fb):
    A = {r["key"]: r for r in map(json.loads, open(fa)) if "error" not in r}
    B = {r["key"]: r for r in map(json.loads, open(fb)) if "error" not in r}
    common = [k for k in A if k in B]
    card = "q_loss" in next(iter(A.values()))
    ch = [k for k in common if A[k]["biq"] != B[k]["biq"]]
    ga = sum(A[k]["agree"] for k in common)
    gb = sum(B[k]["agree"] for k in common)
    print(f"{len(common)} common decisions, {len(ch)} changed; agreement "
          f"{ga} -> {gb} ({gb - ga:+d})")
    if card:
        la = sum(A[k]["b_loss"] or 0 for k in common)
        lb = sum(B[k]["b_loss"] or 0 for k in common)
        print(f"biq DD tricks given up {la} -> {lb} ({lb - la:+d})")
    else:
        ia = sum(A[k]["imp"] for k in common)
        ib = sum(B[k]["imp"] for k in common)
        print(f"cost vs Q-Plus (robust IMP) {ia:+d} -> {ib:+d} ({ib - ia:+d})")
        for k in ch[:30]:
            print(f"  {A[k]['label']} {A[k]['seat']} [{A[k]['auction']}] Q-Plus "
                  f"{A[k]['qplus']}: {A[k]['biq']} ({A[k]['imp']:+d}) -> "
                  f"{B[k]['biq']} ({B[k]['imp']:+d})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["bid", "card", "compare"])
    ap.add_argument("files", nargs="*", help="compare: two jsonl files")
    ap.add_argument("--runs", nargs="*", default=PRECISION_RUNS)
    ap.add_argument("--system", default="Precision90M")
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--sample", type=int, default=1500, help="card mode: positions")
    ap.add_argument("--limit", type=int, help="first N decisions only (smoke test)")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.mode == "compare":
        compare(*a.files)
        return 0
    if a.mode == "bid":
        decs = bid_decisions(a.runs, a.system)
        fn, rep = bid_one, report_bid
    else:
        decs = card_decisions(a.runs)
        total = len(decs)
        decs.sort(key=lambda d: _seed(d["deal"], d["auction"], d["play"]))
        decs = decs[:a.sample]
        print(f"{total} distinct non-forced Q-Plus cards; sampling {len(decs)}")
        fn, rep = card_one, report_card
    if a.limit:
        decs = decs[:a.limit]
    print(f"{len(decs)} decisions from {len(a.runs)} runs, {a.jobs} jobs", flush=True)
    rows = []
    with Pool(a.jobs, initializer=_init, initargs=(a.system,)) as pool:
        for i, r in enumerate(pool.imap(fn, decs, chunksize=4)):
            rows.append(r)
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(decs)}", flush=True)
    if a.out:
        with open(a.out, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    errs = [r for r in rows if "error" in r]
    if errs:
        print(f"{len(errs)} errors, first: {errs[0]['error']}")
    rep(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
