#!/usr/bin/env python3
"""Card-by-card double-dummy audit of the play in Q-Plus score sheets.

For every card of every deal in both rooms (open room: biq N/S vs Q-Plus E/W;
closed room: Q-Plus at all four seats), the double-dummy result of each legal
card at that moment is computed; a card that gives up tricks against the best
card costs that many "DD tricks". Summed by who played it (biq declarer, biq
defender, Q-Plus declarer, Q-Plus defender), this compares the two programs'
card play on the same deals, and lists biq's costliest cards to study.

Double-dummy is a yardstick, not the truth: a card can be DD-wrong and still
the right percentage play. Averaged over hundreds of deals the comparison
between the two programs is what counts.

  python3 tools/play_audit.py tools/runs/results/run1*.qss [--top 30]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from backend.dds import DDSolver                                     # noqa: E402
from qplus_auction_mine import parse_block, _SEATS                   # noqa: E402

_SU = {"s": 0, "h": 1, "d": 2, "c": 3}
_RK = "AKQJT98765432"
_STRAIN = {"s": 1, "h": 2, "d": 3, "c": 4, "nt": 5}


def _code(tok):
    return _SU[tok[0]] * 13 + _RK.index(tok[1])


def _name(c):
    return "SHDC"[c // 13] + _RK[c % 13]


def _pbn(hands):
    out = []
    for s in "NESW":
        suits = [[] for _ in range(4)]
        for c in sorted(hands[s]):
            suits[c // 13].append(_RK[c % 13])
        out.append(".".join("".join(x) for x in suits))
    return "N:" + " ".join(out)


def audit_block(lines, dds):
    """[(seat, is_declarer_side, card, loss, trick_no)] for one room's play."""
    d = parse_block(lines)
    if d is None:
        return None
    cl = next((l for l in lines if l.startswith("Contract")), None)
    if cl is None or "passed" in cl:
        return None
    w = cl.split(":", 1)[1].split()
    strain = w[0][1:]
    decl = next(x for x in w if x in ("North", "South", "East", "West"))[0]
    hands = {s: {_code(x.lower()[0] + x[1]) for x in _cards(d["hands"][s])}
             for s in "NESW"}
    i = next((k for k, l in enumerate(lines) if l.startswith("Tricks")), None)
    if i is None:
        return None
    out = []
    order = "NESW"
    for t, l in enumerate(lines[i:i + 13]):
        body = l.split(":", 1)[1].split()
        if len(body) < 6:
            break
        leader = body[1]
        toks = [x.rstrip("+-") for x in body[2:6]]
        played = []
        seat = leader
        for pos, tok in enumerate(toks):
            c = _code(tok)
            led = played[0] // 13 if played else None
            has_led = led is not None and any(x // 13 == led for x in hands[seat])
            res = dds.solve(_STRAIN[strain], order.index(leader),
                            played, [_pbn(hands)], solutions=3)
            if res and c in res:
                best = max(v[0] for v in res.values())
                loss = best - res[c][0]
                decl_side = (seat in "NS") == (decl in "NS")
                if t == 0 and pos == 0:
                    kind = "opening lead"
                elif pos == 0:
                    kind = "lead"
                elif has_led:
                    kind = f"follow {('2nd', '3rd', '4th')[pos - 1]}"
                elif strain != "nt" and c // 13 == _SU[strain]:
                    kind = "ruff"
                else:
                    kind = "discard"
                out.append((seat, decl_side, _name(c), loss, t + 1,
                            ("NT " if strain == "nt" else "suit ") + kind))
            hands[seat].discard(c)
            played.append(c)
            seat = order[(order.index(seat) + 1) % 4]
    return {"label": d["label"], "contract": " ".join(w[:3]), "decl": decl,
            "cards": out}


def _cards(hand_str):
    out = []
    for su, part in zip("shdc", hand_str.split(".")):
        for r in part:
            out.append(su + r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("qss", nargs="+")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    dds = DDSolver()
    tot = defaultdict(lambda: [0, 0])          # role -> [tricks lost, deals]
    same = defaultdict(lambda: [0, 0])
    kinds = defaultdict(lambda: [0, 0])        # (who, role, kind) -> [lost, cards]
    worst = []
    for path in a.qss:
        text = open(path, errors="replace").read().replace("\r", "")
        for rec in text.split('\nDI "')[1:]:
            rooms = {}
            for pre, room in (("D1", "biq"), ("D2", "qplus")):
                lines = [l[3:] for l in rec.split("\n") if l.startswith(pre + " ")]
                rooms[room] = audit_block(lines, dds)
            if rooms["biq"] is None:
                continue
            same_contract = (rooms["qplus"] is not None
                             and rooms["qplus"]["contract"] == rooms["biq"]["contract"])
            for room, r in rooms.items():
                if r is None:
                    continue
                biq_seats = "NS" if room == "biq" else ""
                for role_decl in (True, False):
                    lost = 0
                    for seat, ds, card, loss, t, kind in r["cards"]:
                        if ds != role_decl:
                            continue
                        who = "biq" if seat in biq_seats else "Q-Plus"
                        # In the biq room the E/W side is Q-Plus: count only
                        # the side whose program we are measuring there.
                        if room == "biq" and who != "biq":
                            continue
                        if room == "qplus" and (seat in "NS") != True:
                            continue
                        lost += loss
                        kinds[(who, "declarer" if ds else "defender", kind)][0] += loss
                        kinds[(who, "declarer" if ds else "defender", kind)][1] += 1
                        if room == "biq" and loss > 0:
                            worst.append((loss, Path(path).name, r["label"],
                                          r["contract"], seat,
                                          "declarer" if ds else "defender", t, card))
                    role = ("declarer" if role_decl else "defender")
                    key = f"{'biq' if room == 'biq' else 'Q-Plus'} N/S as {role}"
                    n_side = any((s in "NS") and (ds == role_decl) for s, ds, *_ in r["cards"])
                    if not n_side:
                        continue
                    tot[key][0] += lost
                    tot[key][1] += 1
                    if same_contract:
                        same[key][0] += lost
                        same[key][1] += 1
    print("DD tricks given away by the N/S side (biq in the open room, Q-Plus "
          "in the closed room), same deals:")
    for key in sorted(tot):
        l, n = tot[key]
        sl, sn = same[key]
        print(f"  {key:26s} {l:5d} tricks over {n:4d} deals = {l / max(n, 1):.2f}/deal"
              f"   | same contract both rooms: {sl / max(sn, 1):.2f}/deal ({sn})")
    print("\nDD tricks lost per 100 cards of each kind (biq vs Q-Plus as N/S):")
    rows = sorted({(r, k) for (_w, r, k) in kinds})
    for role, kind in rows:
        b = kinds[("biq", role, kind)]
        q = kinds[("Q-Plus", role, kind)]
        print(f"  {role:8s} {kind:22s} biq {100 * b[0] / max(b[1], 1):5.1f} "
              f"({b[0]:3d}/{b[1]:4d})   Q-Plus {100 * q[0] / max(q[1], 1):5.1f} "
              f"({q[0]:3d}/{q[1]:4d})")
    print(f"\nbiq's costliest cards:")
    for loss, f, lab, con, seat, role, t, card in sorted(worst, reverse=True)[:a.top]:
        print(f"  -{loss} {f[:24]:24s} {lab} {con:18s} {seat} {role:8s} trick {t:2d} {card}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
