#!/usr/bin/env python3
"""Dump hands + auction + both-room contracts for given boards from a Q-Plus
teams .qss — for scoping a bidding fix. Reads the permanent D1/D2 blocks."""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path

_HV = {"A": 4, "K": 3, "Q": 2, "J": 1}
_SEATS = ["N", "E", "S", "W"]


def _hcp(h):
    return sum(_HV.get(c, 0) for c in h)


def _blocks(qss):
    deals, cur, lines = {}, None, []
    for raw in Path(qss).read_text(errors="replace").splitlines():
        if raw.startswith("DI "):
            if cur:
                deals[cur] = lines
            m = re.search(r'"([^"]*)"', raw)
            cur, lines = (m.group(1) if m else None), [raw]
        elif cur:
            lines.append(raw)
    if cur:
        deals[cur] = lines
    return deals


def _hands(lines):
    for ln in lines:
        if ln.startswith("DD "):
            m = re.search(r'"\S+ \S+ N:(.*)"', ln)
            if m:
                hs = m.group(1).split()
                return dict(zip(_SEATS, hs)) if len(hs) == 4 else None
    return None


_BID = re.compile(r'^(-|p|pass|x|xx|\d[cdhs]~?|\dnt~?)$', re.I)


def _auction(lines):
    """The D1 'Bids' grid is row-major in dealer order; collect only bid-like
    tokens and assign seats cyclically from the dealer (column-1 seat)."""
    grab, order, toks = False, None, []
    for ln in lines:
        if not ln.startswith("D1"):
            continue
        body = ln[2:]
        if "Bids" in body:
            grab = True
            order = body.split(":", 1)[1].split() if ":" in body else None
            continue
        if not grab:
            continue
        if "Contract" in body:
            break
        stop = False
        for t in body.split():
            if t.startswith("=="):
                stop = True
                break
            if _BID.match(t):
                toks.append(t)
        if stop:
            break
    if not order:
        order = ["N", "E", "S", "W"]
    return [(order[i % len(order)], t) for i, t in enumerate(toks)]


def _contract(lines, tag):
    for ln in lines:
        if ln.startswith(tag) and "Result" in ln:
            v = ln.split(":", 1)[1].strip()
            return re.sub(r'\s+(RANDOM|SLAM|SLE|RND)\S*\s*$', '', v)
    return "?"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--qss", required=True)
    ap.add_argument("--boards", required=True, help="comma list, e.g. RANDOM-055,RANDOM-019")
    ap.add_argument("--biq-side", choices=["NS", "EW"], default="NS")
    a = ap.parse_args(argv)
    deals = _blocks(a.qss)
    for b in a.boards.split(","):
        lines = deals.get(b)
        if not lines:
            print(f"{b}: not found"); continue
        hands = _hands(lines) or {}
        seq = _auction(lines)
        biq = {"NS": ["N", "S"], "EW": ["E", "W"]}[a.biq_side]
        print(f"\n=== {b}  (biq {a.biq_side}) ===")
        for s in _SEATS:
            mark = "*biq*" if s in biq else "     "
            h = hands.get(s, "?")
            print(f"  {s}{mark} {_hcp(h):2}hcp  {h}")
        au = "  ".join(f"{s}:{tk}" for s, tk in seq)
        print(f"  AUCTION: {au}")
        print(f"  open(biq room)  = {_contract(lines, 'D1')}")
        print(f"  closed(all QP)  = {_contract(lines, 'D2')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
