#!/usr/bin/env python3
"""Double-pair (board-a-match) validation: biq vs Q-Plus with the cards swapped.

The gold-standard teams test from project_biq_validation_plan: play the SAME
deck in TWO rooms, with biq sitting on OPPOSITE sides each time, so biq holds
both pairs of cards over the two rooms and card luck cancels exactly.

  Room 1 (biq N/S):  biq N/S  vs  Q-Plus E/W   → biq_NS.log
  Room 2 (biq E/W):  Q-Plus N/S  vs  biq E/W   → biq_EW.log

For each board the teams result for biq is the IMP of the two N/S scores:

    biq team net = (biq's N/S score in Room 1) + (biq's E/W score in Room 2)
                 = Room1_NS  +  (−Room2_NS)
                 = Room1_NS − Room2_NS

    board IMP (biq) = diff_to_imps(Room1_NS − Room2_NS)

Positive = biq's pair beat Q-Plus's pair on that board. A net positive over
the deck (in all four cases: SAYC/Precision × random/slam) is the acceptance
bar for "biq ahead".

Both inputs are biq client logs — Room 1's carries biq's N/S result, Room 2's
carries Q-Plus's N/S result (biq sat E/W there). Deals are matched by label
(e.g. SLAM-001) when both decks are labelled, else by hand identity, else by
order (both play the fixed deck in sequence).

Usage:
  python3 tools/double_pair_compare.py \
      --room1 tools/runs/biq_N.log \
      --room2 tools/runs/biq_E.log \
      [--label SAYC-random] [--biq-prefix SLAM] [--worst 15]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.scoring import diff_to_imps          # noqa: E402
from tools.deck_teams_compare import parse_biq     # noqa: E402


def _match(room1, room2):
    """Pair Room-1 and Room-2 deals: by label, else hand-key, else order."""
    by_lbl1 = {d["label"]: d for d in room1 if d.get("label")}
    by_lbl2 = {d["label"]: d for d in room2 if d.get("label")}
    common = set(by_lbl1) & set(by_lbl2)
    if common and len(common) >= min(len(room1), len(room2)) * 0.5:
        return [(by_lbl1[l], by_lbl2[l]) for l in sorted(common)], "label"
    by_key1 = {d["key"]: d for d in room1 if d.get("key")}
    by_key2 = {d["key"]: d for d in room2 if d.get("key")}
    kcommon = set(by_key1) & set(by_key2)
    if kcommon:
        return [(by_key1[k], by_key2[k]) for k in kcommon], "hand"
    n = min(len(room1), len(room2))
    return list(zip(room1[:n], room2[:n])), "order"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--room1", required=True,
                    help="biq N/S log (Room 1: biq N/S vs Q-Plus E/W)")
    ap.add_argument("--room2", required=True,
                    help="biq E/W log (Room 2: Q-Plus N/S vs biq E/W)")
    ap.add_argument("--biq-prefix", default="SLAM",
                    help="keep only deals whose label starts with this "
                         "(default SLAM — drops the seed transition deal); "
                         "'' = keep all")
    ap.add_argument("--label", default="",
                    help="free-text case label for the report header, e.g. "
                         "'both-Precision slam-eligible'")
    ap.add_argument("--worst", type=int, default=15)
    args = ap.parse_args()

    pref = args.biq_prefix or None
    room1 = parse_biq(args.room1, pref)
    room2 = parse_biq(args.room2, pref)
    pairs, mode = _match(room1, room2)

    hdr = f"# double-pair board-a-match — biq vs Q-Plus (cards swapped)"
    if args.label:
        hdr += f"   [{args.label}]"
    print(hdr)
    print(f"  Room 1 (biq N/S): {len(room1)} deals  [{args.room1}]")
    print(f"  Room 2 (biq E/W): {len(room2)} deals  [{args.room2}]")
    print(f"  matched {len(pairs)} boards by {mode}\n")
    if not pairs:
        print("  no boards matched — check the two logs are the same deck.")
        return 1

    rows = []
    for r1, r2 in pairs:
        imp = diff_to_imps(r1["ns"] - r2["ns"])
        rows.append((r1.get("label", "?"), r1["c"], r1["ns"],
                     r2["c"], r2["ns"], imp))
    tot = sum(r[5] for r in rows)
    n = len(rows)
    wins = sum(1 for r in rows if r[5] > 0)
    losses = sum(1 for r in rows if r[5] < 0)
    verdict = "biq AHEAD" if tot > 0 else ("biq BEHIND" if tot < 0 else "TIED")
    print(f"  Net teams IMP (biq − Q-Plus): {tot:+d}  "
          f"({tot / n:+.2f}/board over {n})   →  {verdict}")
    print(f"  biq better on {wins} boards, Q-Plus better on {losses}, "
          f"tie {n - wins - losses}\n")
    print(f"## Biggest swings  (Room1 = biq N/S · Room2 = Q-Plus N/S)")
    for lbl, c1, ns1, c2, ns2, imp in sorted(rows, key=lambda r: r[5])[:args.worst]:
        print(f"  {lbl:9} biqNS {c1:6}({ns1:+5})   qpNS {c2:6}({ns2:+5})   "
              f"IMP={imp:+3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
