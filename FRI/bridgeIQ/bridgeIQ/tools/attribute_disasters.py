#!/usr/bin/env python3
"""Phase-2 attribution: bucket a run's big-swing losses by WHAT leaked.

Reads a Q-Plus teams .qss (which permanently records, per deal, the contract +
result in BOTH rooms via its D1/D2 blocks — the biq client logs are ephemeral,
the qss is not). For each board where the opponent won >= --imp IMPs, it prints
biq's open-room contract/result next to the closed-room (all-Q-Plus) one, plus a
heuristic category, so the dominant leak across the disasters is visible.

Categories: OVERCOMPETE (biq's side took a doubled minus when the closed room
let the opponents play a quiet partscore), UNDERBID (biq's side stopped below
the closed room's game/slam), CARDPLAY (same contract, biq took fewer tricks),
DEFENSE/DECLARE (opponents scored more in biq's room than in the closed room),
OTHER (eyeball it).

Usage:
  python3 tools/attribute_disasters.py --qss PATH.qss --biq-side EW [--imp 8]
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

_SEAT_SIDE = {"North": "NS", "South": "NS", "East": "EW", "West": "EW"}


def _parse(qss):
    deals = {}
    cur = None
    for raw in Path(qss).read_text(errors="replace").splitlines():
        t = raw.split()
        if not t:
            continue
        if t[0] == "DI":
            m = re.search(r'"([^"]*)"', raw)
            cur = m.group(1) if m else None
            deals[cur] = {"di": cur}
        elif cur is None:
            continue
        elif t[0] == "RE" and len(t) >= 3:
            try:
                deals[cur]["re"] = (int(t[1]), int(t[2]))
            except ValueError:
                pass
        elif t[0] == "IM" and len(t) >= 3:
            try:
                deals[cur]["im"] = (int(t[1]), int(t[2]))  # (ns_imp, ew_imp)
            except ValueError:
                pass
        elif t[0] in ("D1", "D2"):
            body = raw[2:].strip()
            for field in ("Contract", "Result"):
                if body.startswith(field):
                    val = body.split(":", 1)[1].strip() if ":" in body else ""
                    val = re.sub(r'\s+(RANDOM|SLAM|SLE|RND)\S*\s*$', '', val)
                    deals[cur][f"{t[0]}_{field.lower()}"] = " ".join(val.split())
    return deals


def _contract_side(contract):
    for name, side in _SEAT_SIDE.items():
        if name in (contract or ""):
            return side, name
    return None, None


def _level(contract):
    m = re.match(r'(\d)', contract or "")
    return int(m.group(1)) if m else 0


def _categorize(d, biq_side):
    """Heuristic bucket from the open (D1, biq's room) vs closed (D2) records."""
    d1c, d1r = d.get("D1_contract", ""), d.get("D1_result", "")
    d2c, d2r = d.get("D2_contract", ""), d.get("D2_result", "")
    opp_side = "NS" if biq_side == "EW" else "EW"
    d1_side, _ = _contract_side(d1c)
    d2_side, _ = _contract_side(d2c)
    open_doubled = " x " in f" {d1c} " or d1c.endswith(" x") or " x" in d1c
    open_minus = "-" in d1r.split()[-2] if len(d1r.split()) >= 2 else False
    # biq's side declared a doubled contract that went minus, closed room let
    # the opponents play (lower / their side) -> phantom save / over-compete.
    if d1_side == biq_side and open_doubled and "-" in d1r:
        if d2_side == opp_side or _level(d2c) <= _level(d1c):
            return "OVERCOMPETE", f"biq {d1c} ({d1r}) vs closed {d2c} ({d2r})"
    # same contract both rooms, different result -> cardplay.
    if d1c and d2c and d1c.split()[0] == d2c.split()[0] and \
            _contract_side(d1c)[0] == _contract_side(d2c)[0]:
        return "CARDPLAY", f"both {d1c}: biq {d1r} vs closed {d2r}"
    # closed room reached a higher contract on biq's side -> biq underbid.
    if d2_side == biq_side and _level(d2c) > _level(d1c):
        return "UNDERBID", f"biq {d1c} vs closed {d2c} (biq side)"
    # opponents declared in both, made more in biq's room -> defense/declare.
    if d1_side == opp_side and d2_side == opp_side:
        return "DEFENSE", f"opp {d1c} ({d1r}) vs closed {d2c} ({d2r})"
    return "OTHER", f"biq {d1c} ({d1r}) | closed {d2c} ({d2r})"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qss", required=True)
    ap.add_argument("--biq-side", choices=["NS", "EW"], required=True)
    ap.add_argument("--imp", type=int, default=8)
    a = ap.parse_args(argv)
    deals = _parse(a.qss)
    opp_idx = 0 if a.biq_side == "EW" else 1     # opp IMP column in IM
    from collections import Counter
    cats = Counter()
    print(f"Disaster attribution — {Path(a.qss).name}  (biq {a.biq_side}, "
          f"opp >= {a.imp} IMP)\n{'=' * 78}")
    rows = []
    for di, d in deals.items():
        im = d.get("im")
        if not im or im[opp_idx] < a.imp:
            continue
        cat, detail = _categorize(d, a.biq_side)
        cats[cat] += im[opp_idx]
        rows.append((im[opp_idx], di, cat, detail))
    for opp, di, cat, detail in sorted(rows, reverse=True):
        print(f"  -{opp:<3} {di:12} {cat:11} {detail}")
    print(f"{'=' * 78}\nLEAK TOTALS (IMP conceded by category):")
    for cat, imp in cats.most_common():
        print(f"  {cat:12} {imp:4} IMP  ({sum(1 for r in rows if r[2]==cat)} boards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
