#!/usr/bin/env python3
"""Reproduce biq's bidding on the seq-run deals to measure bidding changes
WITHOUT a live run — DECLARER-AWARE (T3).

biq bids all four seats with each deal's N/S system; for constructive
(uncontested) auctions this reproduces biq's stop/overbid. The key capability
this adds over a plain probe: it identifies the DECLARER and scores the
contract double-dummy, so an N/S game-bid-DOWN (a real overbid) is reported
separately from a correct E/W game. That distinction is what the biq-vs-biq
probe was structurally blind to and what hid the reverted GF-net's overbids.

Per deal it prints: contract, declaring SIDE, DD make/down, ddNS/ddEW, and a
flag — OVERBID (game/slam reached that goes down), MISSED-GAME / MISSED-SLAM
(a side makeable at game/slam that didn't reach it). The summary counts these
by side so a before/after run shows whether a bidder change traded underbids
for overbids.

Usage:
  python3 tools/seqrun_bid_probe.py [--all] [DEAL_ID ...]
  python3 tools/seqrun_bid_probe.py 3928-79 3928-103
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from backend.models import Bid, Seat, Hand, Card, Rank, Suit, Vulnerability  # noqa: E402
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid    # noqa: E402
from backend.bidding_systems import get_system                                # noqa: E402
from backend.dds import DDSolver                                              # noqa: E402

_R = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK,
      'T': Rank.TEN, '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
      '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
      '2': Rank.TWO}
_S = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
_STR = {0: "S", 1: "H", 2: "D", 3: "C", 4: "NT"}
_DEALER = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_VUL = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
        "EW": Vulnerability.EW, "All": Vulnerability.BOTH,
        "Both": Vulnerability.BOTH}


def hand_from(s):
    cards = []
    for su, part in zip(_S, s.split(".")):
        for c in part:
            if c != '-':
                cards.append(Card(su, _R[c]))
    return Hand(cards=cards)


def deal_hands(pbn):
    hs = pbn.split(":", 1)[1].strip().split()
    order = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
    return {order[i]: hand_from(hs[i]) for i in range(4)}


def biq_auction(hands, dealer, vul, nssys, ewsys):
    ns, ew = get_system(nssys), get_system(ewsys)
    vv = _VUL.get(vul, Vulnerability.NONE)
    auc = []
    seat = dealer
    for _ in range(60):
        st = parse_auction(seat, dealer, list(auc), vulnerability=vv)
        b = decide_bid(st, evaluate_hand(hands[seat]),
                       ns if seat.is_ns() else ew)
        auc.append(b)
        if (len(auc) >= 4 and all(x.is_pass for x in auc[-3:])
                and any(not x.is_pass for x in auc[:-3])):
            break
        if len(auc) >= 4 and all(x.is_pass for x in auc):
            break
        seat = seat.next()
    return auc


def contract_declarer(auc, dealer):
    """(final_contract_bid, declarer_seat) or (None, None) for a pass-out.
    Declarer = first player of the winning side to name the final strain."""
    seat = dealer
    last = None
    win_ns = None
    for b in auc:
        if not b.is_pass and not b.is_double and not b.is_redouble:
            last = b
            win_ns = seat.is_ns()
        seat = seat.next()
    if last is None:
        return None, None
    seat = dealer
    for b in auc:
        if (not b.is_pass and not b.is_double and not b.is_redouble
                and b.suit == last.suit and seat.is_ns() == win_ns):
            return last, seat
        seat = seat.next()
    return last, None


def is_game(level, suit):
    if suit == Suit.NOTRUMP:
        return level >= 3
    if suit in (Suit.SPADES, Suit.HEARTS):
        return level >= 4
    return level >= 5            # minor


def auc_str(auc, dealer):
    seat = dealer
    out = []
    for b in auc:
        t = ("P" if b.is_pass else "X" if b.is_double else "XX"
             if b.is_redouble else
             f"{b.level}{b.suit.to_char() if b.suit else 'N'}")
        out.append(f"{seat.name[0]}:{t}")
        seat = seat.next()
    return " ".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    deals = json.loads(Path("tools/runs/seqrun_deals.json").read_text())
    ids = (list(deals.keys()) if show_all
           else (args or ["3928-79", "3928-73", "3928-101", "3928-120"]))
    dds = DDSolver()
    tally = {"game_made": 0, "slam_made": 0,
             "overbid_ns": 0, "overbid_ew": 0,
             "missed_game": 0, "missed_slam": 0}
    for di in ids:
        d = deals[di]
        hands = deal_hands(d["pbn"])
        dealer = _DEALER[d["dealer"]]
        auc = biq_auction(hands, dealer, d["vul"], d["sys"][0], d["sys"][1])
        c, decl = contract_declarer(auc, dealer)
        t = dds.solve_dd_table(d["pbn"])
        ns_dd = max(max(t["N"][k], t["S"][k]) for k in _STR.values())
        ew_dd = max(max(t["E"][k], t["W"][k]) for k in _STR.values())
        flag = ""
        if c is None or decl is None:
            cs, mk = "PASS", ""
        else:
            strain = "NT" if c.suit == Suit.NOTRUMP else _STR[c.suit.value]
            tricks = t["NESW"[decl.value]][strain]
            need = 6 + c.level
            made = tricks >= need
            cs = f"{c.level}{strain} {decl.name[0]}"
            mk = f"{'MAKES' if made else f'DN{need - tricks}'}({tricks})"
            decl_side_dd = ns_dd if decl.is_ns() else ew_dd
            if is_game(c.level, c.suit):
                if made:
                    tally["slam_made" if c.level >= 6 else "game_made"] += 1
                else:
                    flag = " <<< OVERBID"
                    tally["overbid_ns" if decl.is_ns() else "overbid_ew"] += 1
            # missed: a side can make game/slam but the contract is below it
            top = max(ns_dd, ew_dd)
            reached = c.level if is_game(c.level, c.suit) else 0
            if top >= 12 and c.level < 6:
                flag = flag or " <<< MISSED-SLAM"
                tally["missed_slam"] += 1
            elif top >= 10 and not reached:
                flag = flag or " <<< MISSED-GAME"
                tally["missed_game"] += 1
        print(f"{di} [{d['sys'][0][:4]}/{d['sys'][1][:4]}] "
              f"ddNS={ns_dd} ddEW={ew_dd}  biq→ {cs:8} {mk}{flag}")
        if not show_all:
            print(f"   {auc_str(auc, dealer)}")
    print(f"\n# summary over {len(ids)} deals")
    print(f"  games made:    {tally['game_made']:3}   slams made: {tally['slam_made']}")
    print(f"  OVERBID (game/slam down):  N/S {tally['overbid_ns']}   "
          f"E/W {tally['overbid_ew']}")
    print(f"  MISSED game: {tally['missed_game']}   MISSED slam: {tally['missed_slam']}")


if __name__ == "__main__":
    main()
