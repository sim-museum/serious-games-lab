#!/usr/bin/env python3
"""Clean no-peek-vs-Q-Plus cardplay from two forced-contract .qss sessions.

The teams closed room re-bids its own contracts, so it can't give a clean
cardplay comparison. Instead run the SAME forced-contract PBN twice:

  A) biq N/S (no-peek) vs Q-Plus E/W   — the open room of the live run
  B) all-Q-Plus                        — a separate session (LOCAL, all four
                                          seats Computer, Autoplay)

Both play the identical forced contracts with Q-Plus on E/W, so per board the
difference in the N/S-side declarer tricks is purely no-peek-NS vs Q-Plus-NS
cardplay (E/W is the common Q-Plus opponent). This pairs the two .qss files by
board and reports the split.

  python3 tools/nopeek_qss_compare.py --biq A.qss --qplus B.qss
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

_SEATS = {"North": "N", "East": "E", "South": "S", "West": "W"}


def _parse(qss: str):
    """{board: (contract_norm, declarer_seat, declarer_tricks)} from the OPEN
    room (D1 Contract + C1; C1's last field is the declarer's trick count)."""
    out, cur, k1, c1 = {}, None, None, None
    for ln in Path(qss).read_text(errors="replace").splitlines():
        if ln.startswith("DI "):
            if cur is not None and k1 and c1:
                out[cur] = (k1, c1)
            cur = ln.split('"')[1] if '"' in ln else None
            k1 = c1 = None
        elif ln.startswith("C1 "):
            try:
                c1 = int(ln.split('"')[1].split()[-1])
            except (IndexError, ValueError):
                c1 = None
        elif ln.startswith("D1 Contract"):
            k1 = re.sub(r"\s+", " ", ln.split(":", 1)[1]).strip()
    if cur is not None and k1 and c1:
        out[cur] = (k1, c1)
    res = {}
    for b, (k, t) in out.items():
        toks = k.split()
        decl = toks[-1]                       # last word = declarer seat
        norm = " ".join(toks[:-1])            # contract w/o seat (level+strain[+x])
        res[b] = (norm, decl, t)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--biq", required=True, help="session A .qss (biq N/S)")
    ap.add_argument("--qplus", required=True, help="session B .qss (all Q-Plus)")
    a = ap.parse_args()
    A, B = _parse(a.biq), _parse(a.qplus)

    dec_b = dec_q = dec_n = 0
    def_b = def_q = def_n = 0
    skip = 0
    decl_rows = []
    for b in sorted(A, key=lambda x: int(x) if x.isdigit() else 0):
        if b not in B:
            skip += 1
            continue
        ka, da, ta = A[b]
        kb, db, tb = B[b]
        if ka != kb or da != db:              # contracts must match (same PBN)
            skip += 1
            continue
        ns_decl = da in ("North", "South")
        if ns_decl:                           # biq declares (A), Q-Plus declares (B)
            dec_b += ta; dec_q += tb; dec_n += 1
            decl_rows.append((b, ka, da, ta, tb))
        else:                                 # E/W declares: N/S defends both rooms
            def_b += ta; def_q += tb; def_n += 1

    print(f"no-peek vs Q-Plus — forced contracts, {dec_n+def_n} paired boards "
          f"({skip} unmatched/contract-mismatch)")
    if dec_n:
        print(f"  DECLARER ({dec_n} boards): no-peek {dec_b} tr vs Q-Plus "
              f"{dec_q} tr -> {(dec_b-dec_q)/dec_n:+.2f} tr/board")
    if def_n:
        print(f"  DEFENCE  ({def_n} boards, declarer tricks; lower=better "
              f"defence): no-peek lets {def_b} vs Q-Plus {def_q} -> "
              f"{(def_b-def_q)/def_n:+.2f} tr/board")
    print("  worst declarer boards (no-peek minus Q-Plus tricks):")
    for b, k, d, ta, tb in sorted(decl_rows, key=lambda r: r[3]-r[4])[:8]:
        print(f"    board {b:>3}  {k} by {_SEATS.get(d,d)}: "
              f"no-peek {ta} vs Q-Plus {tb}  ({ta-tb:+d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
