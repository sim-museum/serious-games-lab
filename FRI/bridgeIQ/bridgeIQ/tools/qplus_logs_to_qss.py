#!/usr/bin/env python3
"""Rebuild a teams .qss score sheet from Q-Plus's per-room play logs.

Q-Plus's own score sheet (View > Scoring table, autosaved as
DATA/LOCAL-MATCHES/M<date>-<x>.qss) can come up empty, e.g. when a match is
restarted mid-deck. Q-Plus still writes every deal of both rooms to
DATA/LOG/log-NNN.bdl (open room: biq N/S) and log-NNN.cdl (closed room:
Q-Plus vs Q-Plus). This joins the two into the .qss layout that
whole_system_analyze.py / qss_score_aggregate.py read, and can merge earlier
boards from an existing .qss (e.g. the first half of an interrupted run).

For each deal: DI, DD (from the log's card diagram), RE (N/S score in each
room), IM (IMPs to open / closed room), then the open-room block prefixed
"D1 " and the closed-room block prefixed "D2 ".

Usage:
  python3 tools/qplus_logs_to_qss.py --bdl log-023.bdl --cdl log-023.cdl \\
      [--base M2026-09-26-K.qss] [--from-board 25] -o out.qss
Boards from --base are kept for deal numbers below --from-board; the logs
supply the rest. When a log has a deal twice (a re-dealt board) the LAST
complete copy is used.
"""
from __future__ import annotations

import argparse
import re
import sys

_IMPTAB = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
           900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]
_SEP = "*" * 60


def imp(diff: int) -> int:
    n = sum(1 for t in _IMPTAB if abs(diff) >= t)
    return n if diff >= 0 else -n


def log_deals(path: str) -> dict:
    """{deal label: [lines of that deal's block]} from a .bdl/.cdl log."""
    text = open(path, errors="replace").read().replace("\r", "")
    out = {}
    for chunk in text.split(_SEP):
        m = re.search(r"^Deal\s*:\s*(\S+)", chunk, re.M)
        if m and re.search(r"^Result\s*:", chunk, re.M):
            lines = chunk.strip("\n").split("\n")
            out[m.group(1)] = lines + ["", _SEP, "", ""]
    return out


def ns_score(block: list) -> int:
    """N/S score from the 'Result' line (Q-Plus prints declarer's score)."""
    line = next(l for l in block if l.startswith("Result"))
    if "No Contract" in line:
        return 0
    m = re.search(r"(North|South|East|West)\s+([=+-]\d*)\s+(-?\d+)", line)
    s = int(m.group(3))
    return s if m.group(1) in ("North", "South") else -s


def pbn(block: list) -> str:
    """'<dealer> <vul> N:<hands>' from the log's card diagram."""
    get = lambda k: next(l for l in block if l.startswith(k)).split(":", 1)[1].strip()
    dealer = get("Dealer")[0]
    vul = {"---": "None", "N/S": "NS", "E/W": "EW", "All": "All"}.get(
        get("Vuln"), "All")
    i = next(k for k, l in enumerate(block) if l.startswith("Cards"))
    rows = [l.split(":", 1)[1] for l in block[i:i + 12]]
    north = [r.split() for r in rows[0:4]]
    south = [r.split() for r in rows[8:12]]
    west, east = [], []
    for r in rows[4:8]:
        # West's suit sits in the left columns, East's from column ~33 on.
        west.append(r[:30].split())
        east.append(r[30:].split())

    def hand(h):
        return ".".join("".join(x for x in suit if x != "-") for suit in h)
    return f"{dealer} {vul} N:{hand(north)} {hand(east)} {hand(south)} {hand(west)}"


def base_boards(path: str):
    """(header lines, {label: lines}) of an existing .qss."""
    lines = open(path, errors="replace").read().replace("\r", "").split("\n")
    header, boards, cur = [], {}, None
    for l in lines:
        if l.startswith("DI "):
            cur = l.split('"')[1]
            boards[cur] = []
        if cur is None:
            header.append(l)
        else:
            boards[cur].append(l)
    return header, boards


def num(label: str) -> int:
    m = re.search(r"(\d+)$", label)
    return int(m.group(1)) if m else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bdl", required=True, help="open-room log (biq N/S)")
    ap.add_argument("--cdl", required=True, help="closed-room log")
    ap.add_argument("--base", help="existing .qss to take earlier boards from")
    ap.add_argument("--from-board", type=int, default=1)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    op, cl = log_deals(a.bdl), log_deals(a.cdl)
    header, boards = (base_boards(a.base) if a.base
                      else (["# Q-plus Bridge score sheet", "", ".version = 17.1",
                             "SM T", ""], {}))
    boards = {k: v for k, v in boards.items() if num(k) < a.from_board}
    if not a.base:
        # Keep the system on record (miners filter on it).
        m = re.search(r"Bidding cnv\s*:\s*N/S:\s*(\S+)", open(a.bdl, errors="replace").read(5000))
        if m:
            header.insert(4, f"CG conv.bidding.N/S = {m.group(1)};")
    added = 0
    for label in sorted(set(op) & set(cl), key=num):
        if num(label) < a.from_board:
            continue
        b1, b2 = op[label], cl[label]
        r1, r2 = ns_score(b1), ns_score(b2)
        sw = imp(r1 - r2)
        boards[label] = ([f'DI "{label}"', f'DD "{pbn(b1)}"', f"RE {r1} {r2}",
                          f"IM {max(sw, 0)} {max(-sw, 0)}", "NC 1 1"]
                         + ["D1 " + l for l in b1] + ["D2 " + l for l in b2])
        added += 1
    with open(a.out, "w") as fh:
        for l in header:
            fh.write(l + "\n")
        for label in sorted(boards, key=num):
            for l in boards[label]:
                fh.write(l + "\n")
    missing = sorted((set(op) ^ set(cl)), key=num)
    print(f"{len(boards)} boards written to {a.out} ({added} from the logs)"
          + (f"; only in one room's log: {' '.join(missing)}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
