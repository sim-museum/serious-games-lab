#!/usr/bin/env python3
"""Write the deals of a finished Q-Plus .qss (teams score file) as a BDE deck,
so another run can replay EXACTLY the same boards (paired A/B).

Usage:  python3 tools/qss_to_bde.py <run.qss> [--out OWN-DEALS/NAME.BDE]
Then in Q-Plus: File ▸ Open Own deals ▸ NAME.BDE (Read = AUTO), Match Control
from the first deal, and run the harness as usual."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import BoardState, Seat, Vulnerability          # noqa: E402
from backend.qplus_driver import write_multi_deal_bde, qplus_own_deals_dir  # noqa: E402
from tools.whole_system_analyze import parse_qss                     # noqa: E402

_VUL = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
        "EW": Vulnerability.EW, "All": Vulnerability.BOTH, "Both": Vulnerability.BOTH}


def boards_from_qss(path: Path):
    out = []
    for i, b in enumerate(parse_qss(str(path)), 1):
        dealer, vul, pbn = b["deal"].split(" ", 2)      # "E EW N:... ... ... ..."
        bs = BoardState.from_pbn_deal(pbn, board_num=i)
        bs.dealer = Seat.from_char(dealer)
        bs.vulnerability = _VUL.get(vul, Vulnerability.NONE)
        out.append(bs)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("qss")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="REPLAY")
    a = ap.parse_args()
    boards = boards_from_qss(Path(a.qss))
    if not boards:
        print("no boards parsed", file=sys.stderr); return 1
    out = Path(a.out) if a.out else (qplus_own_deals_dir() or Path(".")) / f"{a.label}.BDE"
    write_multi_deal_bde(boards, out, description=f"replay of {Path(a.qss).name}",
                         label_prefix=a.label[:6])
    print(f"wrote {len(boards)} deals -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
