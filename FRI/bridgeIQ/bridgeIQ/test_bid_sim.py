"""Tests for the hybrid (rules + simulation) bidding and the simulated lead.

Run: python3 test_bid_sim.py   (exit 0 = all pass). Takes ~1 minute.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend import bid_sim, lead_sim, native_lead                     # noqa: E402
from backend.bidding_systems import get_system                         # noqa: E402
from backend.models import (BoardState, Contract, Seat, Suit,          # noqa: E402
                            Vulnerability)
from backend.native_bidder import (decide_bid, evaluate_hand,          # noqa: E402
                                   parse_auction)
from tools.competitive_decision_probe import (parse_call, hand_from,   # noqa: E402
                                              _DLR, _VUL)

SAYC = get_system("SAYC")
FAILS = []


def check(name, ok, detail=""):
    print(f"[{'ok ' if ok else 'BAD'}] {name}  {detail}")
    if not ok:
        FAILS.append(name)


def state_of(seat, dlr, vul, auc):
    return parse_auction(_DLR[seat], _DLR[dlr],
                         [parse_call(t) for t in auc.split()],
                         vulnerability=_VUL[vul])


def test_sampler_reproduces_auction():
    """Every sampled layout is one where biq's rules make the calls made."""
    for hand, seat, dlr, vul, auc in (
            ("872.K5.AQ762.932", "N", "W", "NS", "p p 1h x p 2d 2h 3d p p"),
            ("9.54.T87642.K954", "N", "W", "EW", "p p 1h 2h p"),
            ("Q6.K9752.QT.K942", "S", "S", "NS", "p p 1n p 2d p 3h p")):
        st = state_of(seat, dlr, vul, auc)
        smp = bid_sim._Sampler(st, hand_from(hand), SAYC, random.Random(3),
                               time.time() + 60)
        lay = smp.sample(24)
        bad = sum(smp._mismatch(s, L[s]) for L in lay for s in smp.hidden)
        mine = {bid_sim._code(c) for c in hand_from(hand).cards}
        disjoint = all(len({c for s in L for c in L[s]} | mine) == 52 for L in lay)
        check(f"sampler exact: {auc}", len(lay) >= 16 and bad == 0 and disjoint,
              f"{len(lay)} layouts, {bad} mismatching calls")


def test_conventions_left_to_rules():
    """No simulation inside conventional / slam sequences."""
    for hand, seat, dlr, vul, auc in (
            ("T652.J.AJ972.AT6", "N", "N", "All", "p p 2n p 3c p 3s p"),   # RKC
            ("Q6.K9752.QT.K942", "S", "S", "NS", "p p 1n p"),               # transfer
            ("64.AQ8.AJT8.AJT2", "N", "E", "All", "p p p 1n 2c 2n x")):     # lebensohl
        st = state_of(seat, dlr, vul, auc)
        h = hand_from(hand)
        rule = decide_bid(st, evaluate_hand(h), SAYC)
        hyb = decide_bid(st, evaluate_hand(h), SAYC, hand=h)
        check(f"rules kept: {auc}", bid_sim._key(rule) == bid_sim._key(hyb),
              f"{bid_sim._key(rule)} / {bid_sim._key(hyb)}")


def test_deterministic_and_bounded():
    # Run 7 (live, FRESH64E) RANDOM-060: 1D-2NT-3D, the rules pass 3D with
    # 13 HCP and six clubs; simulation bids 3NT (made 10, +10 IMP live).
    st = state_of("S", "W", "NS", "p 1d p 2nt p 3d p")
    h = hand_from("A87.AQ5.8.QT9832")
    t = time.time()
    a = decide_bid(st, evaluate_hand(h), SAYC, hand=h)
    dt = time.time() - t
    b = decide_bid(st, evaluate_hand(h), SAYC, hand=h)
    check("same call twice", bid_sim._key(a) == bid_sim._key(b),
          f"{bid_sim._key(a)} / {bid_sim._key(b)}")
    # The work is fixed-count; time only matters as a safety cap (3x budget).
    # Fixed-count work: time depends on machine load (8 parallel A/B shards
    # push it to ~30 s); on an idle machine it is a few seconds.
    check("finishes", dt < 60.0, f"{dt:.1f}s")
    check("simulation acted on a judgment point",
          "Simulation:" in (a.explanation or ""), a.explanation[:90])


def test_candidates_legal():
    st = state_of("N", "W", "NS", "p p 1h x p 2d 2h 3d p p")
    h = hand_from("872.K5.AQ762.932")
    import backend.native_bidder as nb
    rule = decide_bid(st, evaluate_hand(h), SAYC)
    cands = bid_sim.candidates(st, h, SAYC, rule)
    check("candidates legal", all(nb._is_legal_bid(c, st) for c in cands),
          " ".join(bid_sim._key(c) for c in cands))


def test_scoring():
    s = bid_sim.duplicate_score
    ok = (s(4, Suit.SPADES, 10, True, 0) == 620
          and s(3, Suit.NOTRUMP, 9, False, 0) == 400
          and s(4, Suit.HEARTS, 8, True, 1) == -500
          and s(5, Suit.CLUBS, 8, False, 1) == -500
          and s(1, Suit.NOTRUMP, 8, False, 1) == 280)
    check("duplicate scoring", ok)


def test_lead_sim_runs():
    auc = "1d p 1n p 2h p 2s p 3n p p p"
    b = BoardState(dealer=Seat.WEST, vulnerability=Vulnerability.NONE,
                   auction=[parse_call(t) for t in auc.split()],
                   contract=Contract(level=3, suit=Suit.NOTRUMP,
                                     declarer=Seat.WEST))
    b.hands = {Seat.NORTH: hand_from("AT92.QT74.QJ7.64")}
    d = native_lead.select_opening_lead(b.hands[Seat.NORTH], b.contract,
                                        b.auction, Seat.WEST, Seat.NORTH,
                                        Vulnerability.NONE)
    r = lead_sim.choose_opening_lead(b, Seat.NORTH, d.card)
    card = r[0] if r else d.card
    check("simulated lead is a card from the hand",
          any(c.suit == card.suit and c.rank == card.rank
              for c in b.hands[Seat.NORTH].cards), str(card))


if __name__ == "__main__":
    for fn in (test_scoring, test_sampler_reproduces_auction,
               test_conventions_left_to_rules, test_candidates_legal,
               test_deterministic_and_bounded, test_lead_sim_runs):
        fn()
    print(f"\n{len(FAILS)} failing")
    sys.exit(1 if FAILS else 0)
