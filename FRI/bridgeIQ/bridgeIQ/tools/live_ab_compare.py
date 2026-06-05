#!/usr/bin/env python3
"""Live A/B — compare TWO real Q-Plus runs on the SAME boards.

This is the honest A/B the DD shortcut (tools/same_deals_ab.py) can't be:
both numbers come from biq's ACTUAL MC+DDS cardplay against a LIVE Q-Plus
that bids, competes, and adapts to biq's moves. The DD/bidding-only tool
plays both sides double-dummy with no live opponent — which flattered us
before; use it only as a quick pre-screen, never as the verdict.

Method (variance-cancelled, like a teams match):
  1. Run A — biq version A vs Q-Plus, 64 deals.
  2. Run B — biq version B vs Q-Plus, the SAME 64 boards (same Q-Plus
     major seed + minor start board, so it re-deals the identical set).
  3. This tool diffs the two runs' per-deal teams IMP. Because the boards
     are identical and the closed-room (Q-Plus-vs-Q-Plus) reference is the
     same in both, card luck cancels and the per-deal difference is purely
     biq-A vs biq-B (bidding AND cardplay) against the live opponent.

Each run's per-deal teams IMP and the full deal come straight from the biq
client log's `report_score` lines (`IM` and `DD` fields). Deals are matched
across the two runs by DEAL IDENTITY (the canonical 4-hand layout), not by
position or label — so the tool also VERIFIES the two runs really were the
same boards and refuses to pretend otherwise if they weren't.

Workflow:
    # --- run A (e.g. the committed baseline) ---
    git checkout HEAD~1 -- backend/native_bidder.py     # or stash your change
    #   launch the panel, run a 64-deal session vs Q-Plus
    cp tools/runs/biq_N.log /tmp/runA.log               # preserve it
    # --- run B (your candidate), SAME Q-Plus seed/start board ---
    git checkout HEAD -- backend/native_bidder.py        # restore the change
    #   run another 64-deal session WITHOUT changing Q-Plus's major seed
    cp tools/runs/biq_N.log /tmp/runB.log
    # --- compare ---
    python3 tools/live_ab_compare.py /tmp/runA.log /tmp/runB.log

Usage:
    python3 tools/live_ab_compare.py A.log B.log [--our-seat N]
        [--worst 20] [--label-a baseline] [--label-b candidate]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from tools.qnet_score_aggregate import (          # noqa: E402
    _payloads_from_client_log, _payloads_from_proxy_log,
    _parse_report_score, _parse_imp, _parse_re,
)

_RANK_ORDER = "AKQJT98765432"


def _canon_hand(h: str) -> str:
    """Sort each suit of a PBN hand high→low so the same holding always
    renders identically."""
    suits = h.split(".")
    out = []
    for s in suits:
        if not s or s == "-":
            out.append(s)
        else:
            out.append("".join(sorted(s, key=lambda c: _RANK_ORDER.index(c)
                                       if c in _RANK_ORDER else 99)))
    return ".".join(out)


def _deal_key(dd: str):
    """Canonical, seat-keyed deal identity from a `DD` field
    '<dealer> <vul> <starter>:<h1> <h2> <h3> <h4>'. Independent of which
    seat the hand list starts from, so the same board always keys equal."""
    m = re.match(r"^\s*\S+\s+\S+\s+([NESW]):(.+)$", dd.strip())
    if not m:
        return None
    starter, rest = m.group(1), m.group(2)
    hands = rest.split()
    if len(hands) != 4:
        return None
    order = "NESW"
    si = order.index(starter)
    by = {}
    for k, h in enumerate(hands):
        by[order[(si + k) % 4]] = _canon_hand(h)
    return "|".join(f"{s}:{by[s]}" for s in order)


def _dealset_key(dd: str):
    """Rotation-INVARIANT key: the unordered set of the 4 hands. Two deals
    with the same cards dealt to different seats (a rotation) share this."""
    m = re.match(r"^\s*\S+\s+\S+\s+[NESW]:(.+)$", dd.strip())
    if not m:
        return None
    hands = m.group(1).split()
    if len(hands) != 4:
        return None
    return tuple(sorted(_canon_hand(h) for h in hands))


def parse_run(path: Path, our_seat: str):
    """Return {deal_key: row} for one run. row carries biq's per-deal teams
    IMP (biq side), the opponent IMP, biq's NS raw score, and a label."""
    head = path.read_text(errors="replace")[:4000]
    if "[biq_qnet]" in head:
        payloads = _payloads_from_client_log(path)
    else:
        payloads = _payloads_from_proxy_log(path)
    biq_is_ns = our_seat.upper() in ("N", "S", "NS")
    out = {}
    order = []
    for _ms, _d, payload in payloads:
        if not payload.startswith('"report_score"'):
            continue
        r = _parse_report_score(payload)
        if not r:
            continue
        dd = r.get("DD", "")
        key = _deal_key(dd)
        if key is None:
            continue
        ns_imp, ew_imp = _parse_imp(r.get("IM", "0 0"))
        re_ns, _re_par = _parse_re(r.get("RE", "0 0"))
        biq_imp = ns_imp if biq_is_ns else ew_imp
        opp_imp = ew_imp if biq_is_ns else ns_imp
        row = {"key": key, "di": r.get("DI", "?"),
               "biq_imp": biq_imp, "opp_imp": opp_imp,
               "ns_score": re_ns, "dd": dd}
        # last occurrence wins (a board replayed after a reset)
        if key not in out:
            order.append(key)
        out[key] = row
    return out, order


def compare(a_path: Path, b_path: Path, our_seat: str,
            label_a: str, label_b: str, worst: int) -> int:
    A, a_order = parse_run(a_path, our_seat)
    B, b_order = parse_run(b_path, our_seat)
    if not A or not B:
        print(f"[live A/B] no report_score deals in "
              f"{'A' if not A else 'B'} log", file=sys.stderr)
        return 1

    common = [k for k in a_order if k in B]
    only_a = [k for k in a_order if k not in B]
    only_b = [k for k in b_order if k not in A]

    biq_side = "NS" if our_seat.upper() in ("N", "S", "NS") else "EW"
    print(f"# live A/B — biq vs Q-Plus on the SAME boards (biq plays {biq_side})")
    print(f"  A = {label_a:<10} {a_path}   ({len(A)} deals)")
    print(f"  B = {label_b:<10} {b_path}   ({len(B)} deals)")
    print()

    # --- same-boards verification: the whole method depends on it ---
    if only_a or only_b:
        print("  ⚠ BOARDS DON'T FULLY MATCH — the two runs were NOT the same "
              "deals (by seat).")
        print(f"    {len(common)} aligned, {len(only_a)} only in A, "
              f"{len(only_b)} only in B.")
        # Are the unmatched boards actually the SAME deals, just ROTATED to
        # different seats? (Same 4 hands, different dealer/seat assignment.)
        a_sets = {}
        for k in only_a:
            ds = _dealset_key(A[k]["dd"])
            if ds:
                a_sets.setdefault(ds, k)
        b_sets = set()
        for k in only_b:
            ds = _dealset_key(B[k]["dd"])
            if ds:
                b_sets.add(ds)
        rotated = sum(1 for ds in a_sets if ds in b_sets)
        if rotated:
            print(f"    ↻ {rotated} of those are the SAME DEALS ROTATED — same "
                  "cards, different seats/dealer. Q-Plus dealt the same set in "
                  "both runs but at a DIFFERENT START BOARD, so every deal "
                  "shifted seats and biq held different cards.")
            print("    FIX: make BOTH runs start at the SAME board number "
                  "(Match Control ‘minor’), then biq holds identical cards "
                  "each run and the boards align.")
        else:
            print("    Fix Q-Plus's major seed + minor start board so both "
                  "runs deal the identical set, then re-run B.")
        print()
    else:
        print(f"  ✓ same boards: all {len(common)} deals matched by deal "
              "identity.\n")
    if not common:
        print("  No shared boards — nothing to compare.")
        return 1

    a_tot = sum(A[k]["biq_imp"] - A[k]["opp_imp"] for k in common)
    b_tot = sum(B[k]["biq_imp"] - B[k]["opp_imp"] for k in common)
    n = len(common)
    print(f"  {label_a:<10} net teams IMP vs Q-Plus: {a_tot:+d}  "
          f"({a_tot / n:+.2f}/deal)")
    print(f"  {label_b:<10} net teams IMP vs Q-Plus: {b_tot:+d}  "
          f"({b_tot / n:+.2f}/deal)")
    print(f"  ── B − A (the candidate's net gain): {b_tot - a_tot:+d}  "
          f"({(b_tot - a_tot) / n:+.3f}/deal over {n})")
    print()

    rows = []
    moved = 0
    for k in common:
        da = A[k]["biq_imp"] - A[k]["opp_imp"]
        db = B[k]["biq_imp"] - B[k]["opp_imp"]
        delta = db - da
        if delta != 0:
            moved += 1
        rows.append({"k": k, "a": A[k], "b": B[k], "da": da, "db": db,
                     "delta": delta})
    wins = [r for r in rows if r["delta"] > 0]
    losses = [r for r in rows if r["delta"] < 0]
    print(f"  Deals that moved: {moved}/{n}  "
          f"(B better {len(wins)}, A better {len(losses)}, "
          f"same {n - moved})")
    print()

    movers = sorted([r for r in rows if r["delta"] != 0],
                    key=lambda r: r["delta"])
    if movers:
        print(f"## Deals where the runs diverged "
              f"(worst {worst} for B first, then best)")
        head = movers[:worst]
        tail = movers[-worst:] if len(movers) > 2 * worst else []
        shown = head + ([None] if tail else []) + tail \
            if tail else movers
        print(f"   {'deal(A/B)':<16} {'A:biq/opp':>10} {'B:biq/opp':>10} "
              f"{'Δ(B-A)':>7}")
        for r in shown:
            if r is None:
                print("   …")
                continue
            a, b = r["a"], r["b"]
            print(f"   {a['di'][:7]:>7}/{b['di'][:7]:<8} "
                  f"{a['biq_imp']:+d}/{a['opp_imp']:+d}".rjust(10)
                  + f"   {b['biq_imp']:+d}/{b['opp_imp']:+d}".rjust(10)
                  + f"   {r['delta']:>+5}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a_log", help="run A's biq client log (e.g. baseline)")
    ap.add_argument("b_log", help="run B's biq client log (candidate)")
    ap.add_argument("--our-seat", default="N", choices=["N", "E", "S", "W"],
                    help="which side biq plays (default N; biq+biq = NS)")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--worst", type=int, default=20)
    args = ap.parse_args()
    return compare(Path(args.a_log), Path(args.b_log), args.our_seat,
                   args.label_a, args.label_b, args.worst)


if __name__ == "__main__":
    sys.exit(main())
