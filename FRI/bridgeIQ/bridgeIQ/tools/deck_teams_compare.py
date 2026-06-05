#!/usr/bin/env python3
"""Closed-room teams compare: biq's N/S vs Q-Plus's N/S on the same deck.

When a deck (BDE) is played as Q-Plus "Own deals", Q-Plus does NOT run a
teams (closed-room) comparison — biq just plays the deals. To get the
biq-vs-Q-Plus teams IMP anyway, run the SAME deck twice:

  1. the biq run  — biq plays N/S vs Q-Plus E/W  (biq client log)
  2. the qplus run — Q-Plus plays ALL four seats (its own .qss/.bdl)

This tool reconstructs the closed room: for each deal it computes the N/S
raw score in BOTH runs and the teams IMP = imp(biq_NS − qplus_NS). Positive
= biq's N/S beat Q-Plus's N/S on that deal.

Deals are matched by HAND IDENTITY when both sources carry the hands (biq
log + qplus .bdl); with a .qss (no hands) they're matched by ORDER, which
is correct because both play the fixed deck in sequence.

Usage:
  python3 tools/deck_teams_compare.py --biq tools/runs/ab/run_*.log \
      --qplus <newest .qss or .bdl from the all-computer run>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.dds import DDSolver                              # noqa: E402
from backend.models import Contract, Suit, Seat              # noqa: E402
from backend.scoring import calculate_contract_score, diff_to_imps  # noqa: E402

_SUIT = {"C": Suit.CLUBS, "D": Suit.DIAMONDS, "H": Suit.HEARTS,
         "S": Suit.SPADES, "N": Suit.NOTRUMP, "NT": Suit.NOTRUMP}
_SEAT = {"NORTH": Seat.NORTH, "EAST": Seat.EAST, "SOUTH": Seat.SOUTH,
         "WEST": Seat.WEST, "N": Seat.NORTH, "E": Seat.EAST,
         "S": Seat.SOUTH, "W": Seat.WEST}
_NS = {Seat.NORTH, Seat.SOUTH}
_RANK = "AKQJT98765432"


def _vul(tag, declarer):
    vns = tag in ("NS", "N/S", "All", "Both", "ALL", "BOTH")
    vew = tag in ("EW", "E/W", "All", "Both", "ALL", "BOTH")
    return (declarer in _NS and vns) or (declarer not in _NS and vew)


def _ns_score(level, strain, declarer, tricks, vul_tag):
    c = Contract(level=level, suit=_SUIT[strain], doubled=False,
                 redoubled=False, declarer=declarer)
    sc = calculate_contract_score(c, tricks, _vul(vul_tag, declarer))
    return sc if declarer in _NS else -sc


def _canon(pbn_hands):
    """pbn_hands: 'N:h1 h2 h3 h4' → seat-keyed canonical key."""
    m = re.match(r"\s*([NESW]):(.+)", pbn_hands)
    if not m:
        return None
    order = "NESW"; si = order.index(m.group(1)); hs = m.group(2).split()
    if len(hs) != 4:
        return None
    by = {}
    for k, h in enumerate(hs):
        suits = [("".join(sorted(s, key=lambda c: _RANK.index(c)
                  if c in _RANK else 99)) if s and s != "-" else s)
                 for s in h.split(".")]
        by[order[(si + k) % 4]] = ".".join(suits)
    return "|".join(f"{s}:{by[s]}" for s in order)


# ---------- biq client log (deck-aware) ----------
def parse_biq(path, prefix=None):
    text = Path(path).read_text(errors="replace")
    out = []
    for ch in re.split(r'(?="?new_deal_pbn)', text):
        m = re.search(r'new_deal_pbn"?\s*\[[^\]]*\]\s*\[[^\]]*\]\s*\['
                      r'([^\]]*)\]\s*\[([NESW])\s+(\S+)\s+([NESW]:[^\]]+)\]', ch)
        if not m:
            continue
        label, vul, pbn = m.group(1), m.group(3), m.group(4)
        if prefix and not label.startswith(prefix):
            continue                        # e.g. skip the seed transition deal
        cm = re.search(r'CONTRACT:\s*(\d)([CDHSN])\s+by\s+(\w+)', ch)
        won = re.findall(r'trick won by (\w+)', ch)
        key = _canon(pbn)
        if not cm:
            out.append({"label": label, "key": key, "ns": 0, "c": "PASS"})
            continue
        lvl, strain, decl = int(cm.group(1)), cm.group(2), _SEAT[cm.group(3)]
        tr = sum(1 for w in won if _SEAT.get(w) in {decl, decl.partner()})
        out.append({"label": label, "key": key,
                    "ns": _ns_score(lvl, strain, decl, tr, vul),
                    "c": f"{lvl}{strain}{cm.group(3)[0]}"})
    return out


# ---------- qplus side: .qss (ns_score direct) or .bdl (hands+result) ----------
def parse_qplus(path):
    txt = Path(path).read_text(errors="replace")
    if path.endswith(".qss") or "score sheet" in txt[:200].lower():
        rows = {}
        for m in re.finditer(r"board\.(\d+)\.(\w+)\s*=\s*(.+)", txt):
            rows.setdefault(int(m.group(1)), {})[m.group(2)] = m.group(3).strip()
        out = []
        for i in sorted(rows):
            r = rows[i]
            out.append({"key": None,        # .qss has no raw hands → order match
                        "ns": int(r.get("ns_score", 0)),
                        "c": r.get("contract", "?")})
        return out, "order"
    # .bdl — hands present → hand match
    from tools.qplus_mixed_corpus import parse_bdl_with_systems
    deals = parse_bdl_with_systems(Path(path))
    out = []
    for d in deals:
        h = d["hands"]
        pbn = "N:" + " ".join(
            ".".join(h[s][suit] for suit in ("S", "H", "D", "C"))
            for s in ("N", "E", "S", "W"))
        # .bdl result line parsing is format-specific; fall back to label/key
        out.append({"key": _canon(pbn), "ns": None, "c": "?",
                    "label": d.get("label")})
    return out, "hands"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--biq", required=True, help="biq client log of the deck run")
    ap.add_argument("--qplus", required=True, help="Q-Plus .qss or .bdl (all-computer)")
    ap.add_argument("--biq-prefix", default="SLAM",
                    help="keep only biq deals whose label starts with this "
                         "(default SLAM — drops the seed transition deal); "
                         "'' = keep all")
    ap.add_argument("--worst", type=int, default=15)
    args = ap.parse_args()

    biq = parse_biq(args.biq, args.biq_prefix or None)
    qp, mode = parse_qplus(args.qplus)
    print(f"# closed-room teams compare — biq N/S vs Q-Plus N/S")
    print(f"  biq run  : {len(biq)} deals  [{args.biq}]")
    print(f"  qplus run: {len(qp)} deals  [{args.qplus}]  (match by {mode})\n")
    if any(q["ns"] is None for q in qp):
        print("  NOTE: this .bdl path needs a result parser — re-run the "
              "all-computer match and 'Save and send' a .qss (it carries "
              "ns_score per board directly).")
        return 1

    pairs = []
    if mode == "hands":
        bymap = {b["key"]: b for b in biq if b["key"]}
        for q in qp:
            b = bymap.get(q["key"])
            if b:
                pairs.append((b, q))
    else:                                   # order
        n = min(len(biq), len(qp))
        if len(biq) != len(qp):
            print(f"  ⚠ deal counts differ ({len(biq)} vs {len(qp)}); matching "
                  f"the first {n} by order.\n")
        pairs = list(zip(biq[:n], qp[:n]))

    rows = []
    for b, q in pairs:
        imp = diff_to_imps(b["ns"] - q["ns"])
        rows.append((b.get("label", "?"), b["c"], b["ns"], q["c"], q["ns"], imp))
    tot = sum(r[5] for r in rows); n = len(rows) or 1
    wins = sum(1 for r in rows if r[5] > 0); losses = sum(1 for r in rows if r[5] < 0)
    print(f"  Net teams IMP (biq − Q-Plus): {tot:+d}  ({tot/n:+.2f}/deal over {len(rows)})")
    print(f"  biq better on {wins} deals, Q-Plus better on {losses}, tie {len(rows)-wins-losses}\n")
    print(f"## Biggest swings")
    for lbl, bc, bns, qc, qns, imp in sorted(rows, key=lambda r: r[5])[:args.worst]:
        print(f"  {lbl:9} biq {bc:6}({bns:+5})  qplus {qc:6}({qns:+5})  IMP={imp:+3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
