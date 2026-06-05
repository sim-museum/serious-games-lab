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

from backend.scoring import diff_to_imps                      # noqa: E402
from tools.deck_teams_compare import parse_biq, parse_qplus   # noqa: E402


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
    ap.add_argument("--baseline", default=None,
                    help="optional all-Q-Plus reference log on the SAME deck. "
                         "When given, ALSO print the closed-room decomposition: "
                         "the overall (= double-pair) split into the N/S-side "
                         "and E/W-side edges, so you can see WHICH side carries "
                         "biq's advantage. The baseline cancels from the total "
                         "(R1_NS − baseline_NS) + (baseline_NS − R2_NS) = "
                         "R1_NS − R2_NS, so it only splits, never shifts it.")
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

    if args.baseline:
        _print_decomposition(args, pref, room1, room2)
    return 0


def _print_decomposition(args, pref, room1, room2):
    """Closed-room both-directions split, using an all-Q-Plus baseline run.

      N/S edge = imp(biq_NS[R1] − qplus_NS[baseline])   biq's N/S-pair skill
      E/W edge = imp(biq_EW[R2] − qplus_EW[baseline])   biq's E/W-pair skill
              with biq_EW = −R2_NS and qplus_EW = −baseline_NS, this is
                       = imp(baseline_NS − R2_NS)

    Raw edges sum exactly to the overall (the baseline cancels); the IMP'd
    edges sum only ~approximately (the IMP scale is concave per board).

    The baseline is an ALL-Q-Plus run → a Q-Plus .qss/.bdl score file (no biq
    client, so no biq log). It's parsed with parse_qplus and aligned to the two
    biq rooms by hand-key when the file carries hands (.bdl), else by deck
    order (.qss has no hands — both sides play the fixed deck in sequence).
    """
    base, bmode = parse_qplus(args.baseline)
    if any(b["ns"] is None for b in base):
        print("\n  [decomposition] baseline .bdl has no parsed scores — export "
              "an all-computer .qss (carries ns_score per board) and pass that.")
        return
    # Pair up the two biq rooms by label, in deck order.
    by1 = {d["label"]: d for d in room1 if d.get("label")}
    by2 = {d["label"]: d for d in room2 if d.get("label")}
    labels = sorted(set(by1) & set(by2))
    rooms = [(by1[l], by2[l]) for l in labels]
    # Attach the baseline: by hand-key (.bdl) else by order (.qss).
    if bmode == "hands":
        bkey = {b["key"]: b for b in base if b.get("key")}
        triples = [(r1, r2, bkey[r1["key"]]) for r1, r2 in rooms
                   if r1.get("key") in bkey]
    else:
        if len(base) != len(rooms):
            print(f"\n  [decomposition] ⚠ baseline has {len(base)} boards, "
                  f"rooms have {len(rooms)} — aligning the first "
                  f"{min(len(base), len(rooms))} by order (drop the seed "
                  f"transition deal so counts match for a clean align).")
        triples = [(r1, r2, b) for (r1, r2), b in zip(rooms, base)]
    if not triples:
        print("\n  [decomposition] baseline didn't match the two rooms — "
              "same deck? (.qss matches by order; .bdl by hands)")
        return
    ns_tot = ew_tot = overall_tot = 0
    rows = []
    for r1, r2, b in triples:
        ns_edge = diff_to_imps(r1["ns"] - b["ns"])        # biq N/S vs QP N/S
        ew_edge = diff_to_imps(b["ns"] - r2["ns"])        # biq E/W vs QP E/W
        overall = diff_to_imps(r1["ns"] - r2["ns"])       # = double-pair
        ns_tot += ns_edge; ew_tot += ew_edge; overall_tot += overall
        rows.append((r1.get("label", "?"), ns_edge, ew_edge, overall))
    n = len(rows)
    print(f"\n## Closed-room decomposition  ({n} boards, baseline "
          f"[{args.baseline}])")
    print(f"  N/S-side edge (biq N/S − Q-Plus N/S): {ns_tot:+5d}  "
          f"({ns_tot / n:+.2f}/board)")
    print(f"  E/W-side edge (biq E/W − Q-Plus E/W): {ew_tot:+5d}  "
          f"({ew_tot / n:+.2f}/board)")
    print(f"  Overall (= double-pair, baseline cancels): {overall_tot:+5d}  "
          f"({overall_tot / n:+.2f}/board)")
    print(f"  [note: IMP'd edges sum ≈ overall — exact on raw scores, "
          f"approximate after the concave IMP scale]")
    worse = sorted(rows, key=lambda r: r[1] + r[2])[:args.worst]
    print(f"## Worst boards by side (which side is leaking)")
    for lbl, ns, ew, ov in worse:
        print(f"  {lbl:9} N/S={ns:+3}  E/W={ew:+3}  overall={ov:+3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
