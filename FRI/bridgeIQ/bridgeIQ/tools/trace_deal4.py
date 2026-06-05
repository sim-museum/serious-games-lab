"""Trace biq's MC+DDS play on Deal 4 of merged_15915_98879.
Prints every card decision with the leader, suit-led, and rank chosen,
so we can see exactly where the 11 lost tricks come from.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.mixed_corpus_diff import (
    _board_from_bdl_hands, _parse_bdl_bids_per_deal,
    _parse_qplus_results, _determine_contract, _trick_winner,
    parse_bdl_with_systems, _SYSTEM_BY_TAG)
from backend.engine import BridgeEngine
from backend.models import BoardState, Hand, Seat, Suit

import re
import json

QSS = ROOT / "data/qplus_corpora_archive/merged_15915_98879.qss"
MANI = ROOT / "data/qplus_corpora_archive/20260529_150758_s15915_98879.manifest.json"
import os
TARGET_DEAL = int(os.environ.get("TRACE_DEAL", "4"))

manifest = json.loads(MANI.read_text())
ns_sys, ew_sys = next(
    (d["ns_system"], d["ew_system"])
    for d in manifest["deals"] if d["deal"] == TARGET_DEAL)
print(f"NS system: {ns_sys}, EW system: {ew_sys}")

bdl_deals = parse_bdl_with_systems(QSS)
bd = next(bd for bd in bdl_deals
          if int(re.search(r"(\d+)\s*$", bd["label"]).group(1)) == TARGET_DEAL)
board = _board_from_bdl_hands(TARGET_DEAL, bd)
print(f"\nVul: {board.vulnerability.name}, Dealer: {board.dealer.to_char()}")
for s in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
    h = board.hands[s]
    by_suit = {Suit.SPADES: [], Suit.HEARTS: [],
               Suit.DIAMONDS: [], Suit.CLUBS: []}
    for c in h.cards:
        by_suit[c.suit].append(c.rank.to_char())
    print(f"  {s.to_char()}: "
          f"♠{''.join(by_suit[Suit.SPADES]) or '-'}  "
          f"♥{''.join(by_suit[Suit.HEARTS]) or '-'}  "
          f"♦{''.join(by_suit[Suit.DIAMONDS]) or '-'}  "
          f"♣{''.join(by_suit[Suit.CLUBS]) or '-'}")

bids = _parse_bdl_bids_per_deal(QSS)
qp_auction = bids.get(bd["label"]) or []
print(f"\nQ-Plus auction: "
      f"{' '.join(b.suit.to_char() + str(b.level) if b.level else 'P' for b in qp_auction)}")
contract = _determine_contract(board, qp_auction)
print(f"Contract: {contract.level}{contract.suit.to_char()}-{contract.declarer.to_char()}")

# Now drive biq's MC engine through 13 tricks, printing each decision.
engine = BridgeEngine()
engine.cardplay_relax_inference = 3
assert engine.initialize()
# Declarer is East → use the EW-side system to interpret Q-Plus's
# auction (declarer-side bids carry the bulk of the inference).
engine.set_bidding_system(ew_sys)
print(f"\n--- biq cardplay trace (MC samples=5, system={ew_sys}) ---")

from backend.models import Trick
declarer = contract.declarer
trump = contract.suit
leader = Seat((declarer + 1) % 4)
hands_state = {s: list(board.hands[s].cards) for s in
               (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)}
declarer_tricks = 0
completed_tricks: list = []
NUM_SAMPLES = 5
SUIT_GLYPH = {Suit.SPADES: "♠", Suit.HEARTS: "♥",
              Suit.DIAMONDS: "♦", Suit.CLUBS: "♣",
              Suit.NOTRUMP: "NT"}

for t_idx in range(13):
    trick_cards = []
    trick_seats = []
    seat = leader
    record = []
    for p_idx in range(4):
        sub_board = BoardState(
            board_number=board.board_number,
            dealer=board.dealer,
            vulnerability=board.vulnerability,
            hands={s: Hand(cards=list(hands_state[s])) for s in
                   (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST)},
            auction=list(qp_auction),
            contract=contract,
            tricks=list(completed_tricks),
        )
        try:
            resp = engine.get_mc_card_play(
                sub_board, seat,
                current_trick_cards=list(trick_cards),
                num_samples=NUM_SAMPLES)
        except Exception as e:
            print(f"   {seat.to_char()} EXCEPTION: {e}")
            resp = None
        card = resp.action if resp is not None else None
        chosen_via = "MC"
        if card is None:
            lead_suit = trick_cards[0].suit if trick_cards else None
            legal = [c for c in hands_state[seat]
                     if lead_suit is None or c.suit == lead_suit]
            if not legal:
                legal = hands_state[seat]
            card = legal[0]
            chosen_via = "FALLBACK"
        try:
            hands_state[seat].remove(card)
        except ValueError:
            print(f"   {seat.to_char()} PHANTOM CARD: {card}")
            break
        trick_cards.append(card)
        trick_seats.append(seat)
        record.append((seat, card, chosen_via))
        seat = Seat((seat + 1) % 4)
    winner_idx = _trick_winner(trick_cards, trump)
    winner_seat = trick_seats[winner_idx]
    wins_declarer = winner_seat in (declarer, Seat((declarer + 2) % 4))
    if wins_declarer:
        declarer_tricks += 1
    completed_tricks.append(Trick(
        cards=list(trick_cards), leader=trick_seats[0],
        winner=winner_seat))
    glyphs = " ".join(
        f"{s.to_char()}{SUIT_GLYPH[c.suit]}{c.rank.to_char()}"
        f"{'*' if v=='FALLBACK' else ''}"
        for (s, c, v) in record)
    print(f"  T{t_idx+1:>2} (led by {leader.to_char()}): {glyphs}  "
          f"=> {winner_seat.to_char()} "
          f"({'DECL' if wins_declarer else 'def '})")
    leader = winner_seat

print(f"\nbiq declarer tricks: {declarer_tricks} / 13")
print(f"Q-Plus declarer tricks: "
      f"{_parse_qplus_results(QSS).get(bd['label'])} / 13")
