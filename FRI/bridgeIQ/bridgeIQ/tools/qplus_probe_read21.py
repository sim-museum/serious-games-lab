#!/usr/bin/env python3
"""Reader for the bid21 / bid21second probe runs (qplus_probe.py families
mlandy, wslam, hicomp, second).

For every call Q-Plus made, biq's own bidder (--system, default TwoOverOne)
is asked what it would call in the same seat after the same auction, so each
row shows where biq parts from Q-Plus. Every board also gets the double-dummy
tricks of its final contract. "second" boards report the second-hand card in
the probe suit.
  python3 tools/qplus_probe_read21.py tools/runs/probes/bid21second1 \\
      tools/runs/bluechip/probe_bid21second1 [--system TwoOverOne] [--json out.jsonl]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.models import Bid, Vulnerability                                  # noqa: E402
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid      # noqa: E402
from backend.bidding_systems import get_system                                 # noqa: E402
from backend.dds import DDSolver                                               # noqa: E402
from biq_bluechip_tm import read_pbn, _call_str                                # noqa: E402

SEATS = "NESW"


def biq_calls(rec, hands, dealer, vul, system):
    """[(index, seat, qplus_call, biq_call)] for each call by E/W (Q-Plus)."""
    calls = rec["auction"].split()
    out, seat, auction = [], dealer, []
    for i, c in enumerate(calls):
        s = seat.name[0].upper()
        if s in "EW":
            st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
            try:
                b = _call_str(decide_bid(st, evaluate_hand(hands[seat]), system, hand=hands[seat]))
            except Exception as ex:                       # report, don't stop
                b = f"err:{type(ex).__name__}"
            out.append((i, s, c, b))
        auction.append(Bid.from_str(c))
        seat = seat.next()
    return out


def dd_contract(dd, rec):
    ct = rec["contract"]
    if not ct.strip() or ct.split()[0] in ("P", "Pass", "PASS"):
        return None
    lvl, decl = ct.split()
    st = lvl[1:].rstrip("X")
    return dd.solve_dd_table(rec["deal"])[decl][st] - (int(lvl[0]) + 6)


def second_card(rec, d):
    """Second-hand card in the probe suit: the first trick in d['psuit'] after
    trick 1, and the card the second seat played to it."""
    play, ps = rec["play"], d["psuit"]
    for k in range(0, len(play), 4):
        trick = play[k:k + 4]
        if k == 0 or len(trick) < 2:
            continue
        if trick[0][0] == ps:
            return trick[1]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("run")
    ap.add_argument("--system", default="TwoOverOne")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    system = get_system(a.system)
    deck = {n: (dl, v, h) for n, dl, v, h in read_pbn(str(Path(a.deck) / "deals.pbn"))}
    design = {x["board"]: x for x in map(json.loads, open(Path(a.deck) / "design.jsonl"))}
    dd = DDSolver()
    rows = []
    for line in open(Path(a.run) / "results.jsonl"):
        rec = json.loads(line)
        n = rec["board"]
        d = design[n]
        dealer, vul, hands = deck[n]
        row = {k: v for k, v in d.items() if k not in ("deal", "P")}
        row.update(auction=rec["auction"], alerts=rec.get("alerts", {}), contract=rec["contract"],
                   tricks=rec["tricks"], ns_score=rec["ns_score"], dd_over=dd_contract(dd, rec),
                   opening_lead=rec["play"][0] if rec.get("play") else None)
        if d["family"] == "second":
            row["second_card"] = second_card(rec, d)
        else:
            row["calls"] = biq_calls(rec, hands, dealer, vul, system)
        rows.append(row)
        print(json.dumps(row), flush=True)
    if a.json:
        Path(a.json).write_text("".join(json.dumps(r) + "\n" for r in rows))


if __name__ == "__main__":
    main()
