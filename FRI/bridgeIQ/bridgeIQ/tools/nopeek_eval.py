#!/usr/bin/env python3
"""Measure the no-peek engine (backend.nopeek) the same way as PIMC.

biq's no-peek engine plays one side; a double-dummy yardstick plays the other
(DD is only the measuring opponent — the no-peek engine itself never peeks).
Reports the declarer leak (no-peek declares vs DD defence) and defence leak
(no-peek defends vs DD declarer), directly comparable to cardplay_eval's PIMC
numbers (PIMC declarer ~0.75, defence ~0.93 tr/deal).

  python3 tools/nopeek_eval.py --deals 100 --seed 5
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import Seat, Suit, Hand, BoardState, Trick      # noqa
from backend.dds import DDSolver                                    # noqa
from backend import nopeek                                          # noqa
from tools.cardplay_eval import (_deal, _pbn, _over, _contract, _dd_card,
                                 _STRAIN)                            # noqa
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid  # noqa
from backend.bidding_systems import get_system                      # noqa


def _play(dds, hands, contract, vul, dd_side):
    """dd_side ('declarer'/'defense') plays double-dummy; the other side plays
    the no-peek engine. Returns declarer tricks."""
    trump = None if contract.suit == Suit.NOTRUMP else contract.suit
    board = BoardState(board_number=1, dealer=contract.declarer,
                       vulnerability=vul,
                       hands={s: Hand(cards=list(hands[s].cards)) for s in hands},
                       auction=[], contract=contract)
    decl_ns = contract.declarer.is_ns()
    decl_tricks, leader = 0, contract.declarer.next()
    for _ in range(13):
        trick = Trick(leader=leader)
        board.current_trick = trick
        cur = leader
        for _ in range(4):
            cur_is_decl = (cur.is_ns() == decl_ns)
            use_dd = ((dd_side == "declarer" and cur_is_decl)
                      or (dd_side == "defense" and not cur_is_decl))
            card = None
            if use_dd:
                card = _dd_card(dds, board, contract, list(trick.cards))
            if card is None:
                card = nopeek.decide(board, cur, list(trick.cards))
            board.hands[cur].remove_card(card)
            trick.add_card(card, trump)
            cur = cur.next()
        board.current_trick = None
        board.tricks.append(trick)
        w = trick.winner
        if w.is_ns() == decl_ns:
            decl_tricks += 1
        leader = w
    return decl_tricks


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--ns-system", default="SAYC")
    ap.add_argument("--ew-system", default="SAYC")
    ap.add_argument("--rng", type=int, default=None,
                    help="sampler seed (default=--seed); vary it (same --seed) "
                         "to gauge Monte-Carlo variance on the SAME deals")
    a = ap.parse_args()
    import random
    random.seed(a.seed if a.rng is None else a.rng)   # reproducible sampler
    # draws -> A/B comparisons aren't swamped by run-to-run noise (~0.2 tr/deal)
    dds = DDSolver()
    ns_sys, ew_sys = get_system(a.ns_system), get_system(a.ew_system)

    boards = []
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
        if c is None:
            continue
        t = dds.solve_dd_table(_pbn(hands))
        dd = t["NESW"[c.declarer.value]][_STRAIN[c.suit]]
        boards.append((hands, c, vul, dd))

    n = len(boards)
    print(f"NO-PEEK engine — {n} contracts (seed {a.seed}, "
          f"{a.ns_system}/{a.ew_system}). Each side vs DD-perfect yardstick:")
    decl_leak = def_leak = decl_b = def_b = 0
    for hands, c, vul, dd in boards:
        d = _play(dds, hands, c, vul, "defense")     # no-peek DECLARES
        f = _play(dds, hands, c, vul, "declarer")    # no-peek DEFENDS
        decl_leak += dd - d
        def_leak += f - dd
        decl_b += (d < dd)
        def_b += (f > dd)
    print(f"  no-peek DECLARER (vs DD defense): loses {decl_leak} tricks = "
          f"{decl_leak/n:+.3f}/deal (worse on {decl_b}/{n})   [PIMC ~0.75]")
    print(f"  no-peek DEFENSE  (vs DD declarer): gives {def_leak} tricks = "
          f"{def_leak/n:+.3f}/deal (worse on {def_b}/{n})   [PIMC ~0.93]")
    print("  (the price of never peeking — compare to PIMC's DD-assisted leaks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
