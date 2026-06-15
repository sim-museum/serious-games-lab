#!/usr/bin/env python3
"""No-peek vs PIMC head-to-head — the realistic yardstick.

Double-dummy is too harsh a measure for a no-peek engine: DD defenders are never
fooled, so finesses/inference (which gain vs real opponents) score zero. Here the
opponent is biq's own PIMC engine (a realistic, beatable defender), so sound
no-peek technique can show its value. For each deal we play the SAME contract
four ways and compare declarer tricks:

  declarer skill:  no-peek declares vs PIMC defence   vs   PIMC declares vs PIMC defence
  defence skill:   PIMC declares vs no-peek defence   vs   PIMC declares vs PIMC defence

If no-peek declarer tricks >= PIMC declarer tricks (vs the same PIMC defence),
no-peek declares as well as PIMC against real opposition — while never peeking.

  python3 tools/nopeek_vs_pimc.py --deals 25 --seed 5 --samples 30
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import Seat, Suit, Hand, BoardState, Trick      # noqa
from backend.dds import DDSolver                                    # noqa
from backend.engine import BridgeEngine                             # noqa
from backend import nopeek                                          # noqa
from tools.cardplay_eval import (_deal, _pbn, _over, _contract, _STRAIN)  # noqa
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid  # noqa
from backend.bidding_systems import get_system                      # noqa


def _card(engine, who, board, seat, trick, samples):
    if who == "nopeek":
        return nopeek.decide(board, seat, list(trick))
    if not board.tricks and not trick:
        return engine.get_opening_lead(board).action
    return engine.get_mc_card_play(board, seat, list(trick),
                                   num_samples=samples).action


def _play(engine, hands, contract, vul, decl_who, def_who, samples):
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
            who = decl_who if (cur.is_ns() == decl_ns) else def_who
            card = _card(engine, who, board, cur, list(trick.cards), samples)
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
    ap.add_argument("--deals", type=int, default=25)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--samples", type=int, default=30)
    a = ap.parse_args()
    engine, dds = BridgeEngine(), DDSolver()
    ns_sys, ew_sys = get_system("SAYC"), get_system("SAYC")

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
        if c is not None:
            boards.append((hands, c, vul))

    n = len(boards)
    print(f"no-peek vs PIMC — {n} contracts (seed {a.seed}, {a.samples} samples)")
    decl_np = decl_pi = def_np = def_pi = 0
    for hands, c, vul in boards:
        decl_np += _play(engine, hands, c, vul, "nopeek", "pimc", a.samples)
        decl_pi += _play(engine, hands, c, vul, "pimc", "pimc", a.samples)
        def_np_t = _play(engine, hands, c, vul, "pimc", "nopeek", a.samples)
        def_pi_t = _play(engine, hands, c, vul, "pimc", "pimc", a.samples)
        def_np += def_np_t
        def_pi += def_pi_t
    print(f"  DECLARER (vs PIMC defence): no-peek {decl_np} vs PIMC {decl_pi} "
          f"tricks -> {(decl_np-decl_pi)/n:+.3f}/deal (no-peek minus PIMC)")
    print(f"  DEFENCE  (vs PIMC declarer): declarer made {def_np} vs {def_pi} "
          f"tricks -> {(def_pi-def_np)/n:+.3f}/deal better defence (lower=better)")
    print("  >=0 declarer / >=0 defence => no-peek matches PIMC vs real opp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
