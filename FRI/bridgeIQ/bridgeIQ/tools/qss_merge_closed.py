#!/usr/bin/env python3
"""Score an open-room-only Q-Plus sheet against another run's closed room.

In an A/B of two biq versions on the same deck, Q-Plus's closed room (Q-Plus
at all four seats) is identical in both runs, so the second run can skip it.
This copies the closed room (D2 lines) of each deal from `--closed` into the
open-room-only sheet `--open`, after checking the deal (label and all four
hands) is the same, and rewrites each deal's RE/IM lines.

  python3 tools/qss_merge_closed.py --open M2026-10-01-D.qss \\
      --closed run18.qss -o run19.qss
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import bid_sim                                           # noqa: E402


def records(text):
    head, *recs = text.split('\nDI "')
    return head, ['DI "' + r for r in recs]


def label_hands(rec):
    m = re.search(r'^DI "([^"]*)"', rec)
    hands = re.findall(r"^D1 (?:\s*[NESW]:|Deal|.*hand).*$", rec, re.M)
    dd = re.search(r'^DD "([^"]*)"', rec, re.M)
    return m.group(1) if m else None, dd.group(1) if dd else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", required=True)
    ap.add_argument("--closed", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    ho, ro = records(open(a.open, errors="replace").read().replace("\r", ""))
    hc, rc = records(open(a.closed, errors="replace").read().replace("\r", ""))
    closed = {}
    for r in rc:
        lab, dd = label_hands(r)
        closed[lab] = (dd, r)
    out, n, tot = [ho], 0, 0
    for r in ro:
        lab, dd = label_hands(r)
        if lab not in closed:
            sys.exit(f"deal {lab} missing from the closed-room sheet")
        cdd, cr = closed[lab]
        if dd != cdd:
            sys.exit(f"deal {lab} differs between the two sheets ({dd} / {cdd})")
        d2 = [l for l in cr.split("\n") if l.startswith("D2 ")]
        mo = re.search(r"^RE (-?\d+) (-?\d+)", r, re.M)
        mc = re.search(r"^RE (-?\d+) (-?\d+)", cr, re.M)
        ns_open, ns_closed = int(mo.group(1)), int(mc.group(2))
        imp = bid_sim._imp(ns_open - ns_closed)
        tot += imp
        n += 1
        lines = [l for l in r.split("\n") if not l.startswith("D2 ")]
        lines = [f"RE {ns_open} {ns_closed}" if l.startswith("RE ") else
                 f"IM {max(imp, 0)} {max(-imp, 0)}" if l.startswith("IM ") else l
                 for l in lines]
        # D2 lines go right after the D1 block.
        last_d1 = max(i for i, l in enumerate(lines) if l.startswith("D1 "))
        lines = lines[:last_d1 + 1] + d2 + lines[last_d1 + 1:]
        out.append("\n".join(lines))
    Path(a.out).write_text("\n".join(out))
    print(f"{n} deals merged -> {a.out}; open room (biq N/S) {tot:+d} IMP "
          f"({tot / max(n, 1):+.2f}/deal)")


if __name__ == "__main__":
    main()
