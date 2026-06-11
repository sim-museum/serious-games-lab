#!/usr/bin/env python3
"""Generate a PBN deck with FORCED contracts for Q-Plus cardplay-only play.

Q-Plus skips the bidding phase when a deal carries an [Auction] tag (proven by
IMPORTED-DEALS/PROBES.PBN, whose own header says so). The .bdl log-table bid
format is NOT valid forced-auction input — PBN is. This emits biq's deals (same
seed as the offline harnesses) with the contract biq's bidder reaches, encoded
as a real auction, so Q-Plus loads each board and starts at the opening lead in
that exact contract. Drop the file in Q-Plus's IMPORTED-DEALS and load it with
Read = Bids (or Auto).

  python3 tools/gen_forced_pbn.py --deals 64 --seed 5 --out forced_s5.pbn
  # then copy forced_s5.pbn to <qplus>/DATA/IMPORTED-DEALS/

The same deals/contracts are reproducible offline for the no-peek side, so the
two can be compared head-to-head on identical contracts.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import Seat, Suit                                   # noqa
from tools.cardplay_eval import _deal, _pbn, _over, _contract           # noqa
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid  # noqa
from backend.bidding_systems import get_system                          # noqa

_STRAIN = {Suit.SPADES: "S", Suit.HEARTS: "H", Suit.DIAMONDS: "D",
           Suit.CLUBS: "C", Suit.NOTRUMP: "NT"}
_VULTAG = {1: "None", 2: "NS", 3: "EW", 4: "All", 5: "NS", 6: "EW", 7: "All",
           8: "None", 9: "EW", 10: "All", 11: "None", 12: "NS", 13: "All",
           14: "None", 15: "NS", 16: "EW"}


def _call_str(bid) -> str:
    if bid.is_pass:
        return "Pass"
    if bid.is_double:
        return "X"
    if bid.is_redouble:
        return "XX"
    return f"{bid.level}{_STRAIN[bid.suit]}"


def _vuln(board: int) -> str:
    return _VULTAG[((board - 1) % 16) + 1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deals", type=int, default=64)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--ns-system", default="SAYC")
    ap.add_argument("--ew-system", default="SAYC")
    ap.add_argument("--out", default="forced.pbn")
    a = ap.parse_args()
    ns_sys, ew_sys = get_system(a.ns_system), get_system(a.ew_system)

    out, n_ok, n_passed = [], 0, 0
    out.append("% PBN 2.1")
    out.append('[Event "BridgeIQ no-peek vs Q-Plus cardplay"]')
    out.append('[Site "?"]')
    out.append('[Scoring "IMP"]')
    out.append("%% seed=%d deals=%d systems=%s/%s" %
               (a.seed, a.deals, a.ns_system, a.ew_system))
    out.append("% Forced contracts via [Auction]; load with Read=Bids/Auto.")
    out.append("")

    for b in range(1, a.deals + 1):
        dealer, vul, hands = _deal(a.seed, b)
        auction, seat = [], dealer
        for _ in range(60):
            st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
            auction.append(decide_bid(st, evaluate_hand(hands[seat]),
                           ns_sys if seat.is_ns() else ew_sys))
            if _over(auction):
                break
            seat = seat.next()
        c = _contract(auction, dealer)
        if c is None:                       # passed out — Q-Plus can't play it
            n_passed += 1
            continue
        # PBN deal string is biq's _pbn (N:hand_N hand_E hand_S hand_W)
        deal_str = _pbn(hands)
        calls = [_call_str(x) for x in auction]
        out.append("% " + "=" * 66)
        out.append(f'[Board "{b}"]')
        out.append(f'[Dealer "{dealer.name[0]}"]')
        out.append(f'[Vulnerable "{_vuln(b)}"]')
        out.append(f'[Deal "{deal_str}"]')
        out.append(f'[Declarer "{c.declarer.name[0]}"]')
        out.append(f'[Contract "{c.level}{_STRAIN[c.suit]}"]')
        out.append(f'[Auction "{dealer.name[0]}"]')
        # PBN auction: 4 calls per line is conventional
        for i in range(0, len(calls), 4):
            out.append(" ".join(calls[i:i + 4]))
        out.append("")
        n_ok += 1

    text = "\n".join(out) + "\n"          # PBN is LF (PROBES.PBN is LF)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"wrote {a.out}: {n_ok} boards with forced contracts "
          f"({n_passed} passed-out boards skipped)")
    print(f"copy to <qplus>/DATA/IMPORTED-DEALS/ and load with Read=Bids/Auto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
