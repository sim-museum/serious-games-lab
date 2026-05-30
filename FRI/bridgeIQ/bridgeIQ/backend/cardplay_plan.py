"""Strategic cardplay planner — above DDS.

biq's MC+DDS engine plays each card *locally optimally against a
probabilistic guess of the layout*. That's an architectural ceiling:
no per-card decision can encode "I need to draw trumps and cash my
top tricks in the right order to make 4 spades". This module is the
beginning of a textbook-anchored plan-builder that operates above
DDS, similar to how `native_bidder.py` operates above the simple
"first legal bid" fallback.

Built incrementally, one rule per phase, with measured impact each
time. This file is Phase 1 only — the trump-drawing lead rule.

Phase 1 (this file): declarer's trump-drawing lead.
Phase 2 (later): follow-suit rules (second-hand-low, unblock
  prevention from dummy).
Phase 3 (later): suit-establishment plans, entry counting.
Phase 4 (later): defender signaling.
Phase 5 (later): endplay / squeeze recognition.
"""

from typing import List, Optional
from .models import Card, Hand, Suit, Rank, Seat, BoardState

_RANK_HI_TO_LO = [Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                  Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                  Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE,
                  Rank.TWO]


def _partner(seat: Seat) -> Seat:
    return Seat((seat + 2) % 4)


def _is_declarer_side(seat: Seat, declarer: Seat) -> bool:
    return seat == declarer or seat == _partner(declarer)


def _trump_cards_sorted_high(hand: Hand, trump: Suit) -> List[Card]:
    """Cards of the trump suit in `hand`, sorted high to low (Ace
    first). Rank.value ordering is ACE=0 ... TWO=12, so sort
    ascending by .value."""
    return sorted([c for c in hand.cards if c.suit == trump],
                  key=lambda c: c.rank.value)


def _played_trump_ranks(board: BoardState, trump: Suit,
                         current_trick_cards: List[Card]) -> set:
    """Ranks of the trump suit already played (completed tricks +
    current trick)."""
    played = set()
    for trick in getattr(board, "tricks", []) or []:
        for c in (getattr(trick, "cards", []) or []):
            if c.suit == trump:
                played.add(c.rank)
    for c in current_trick_cards or []:
        if c.suit == trump:
            played.add(c.rank)
    return played


def _highest_outstanding_opp_trump(board: BoardState, seat: Seat,
                                    declarer: Seat, trump: Suit,
                                    current_trick_cards: List[Card]
                                    ) -> Optional[Rank]:
    """Return the highest trump rank that could be in an opponent's
    hand right now, or None if opponents are out of trumps.
    "Visible" = own side's hands (declarer + dummy, both visible
    when declarer-side computes the plan) + played cards."""
    visible_ranks = set(_played_trump_ranks(board, trump,
                                              current_trick_cards))
    own_side = (declarer, _partner(declarer))
    for s in own_side:
        for c in board.hands[s].cards:
            if c.suit == trump:
                visible_ranks.add(c.rank)
    for r in _RANK_HI_TO_LO:
        if r not in visible_ranks:
            return r
    return None  # all 13 trump ranks accounted for on our side or played


def _opponent_trump_count(board: BoardState, declarer: Seat,
                           trump: Suit,
                           current_trick_cards: List[Card]) -> int:
    own_side = (declarer, _partner(declarer))
    own_count = sum(1 for s in own_side
                    for c in board.hands[s].cards
                    if c.suit == trump)
    played_count = len(_played_trump_ranks(board, trump,
                                            current_trick_cards))
    return max(0, 13 - own_count - played_count)


def planned_lead(board: BoardState, seat: Seat,
                  current_trick_cards: Optional[List[Card]] = None
                  ) -> Optional[Card]:
    """Return the strategic-plan card for a LEAD decision, or None
    to fall through to MC+DDS.

    Phase 1 — declarer's trump-drawing lead. In a suit contract,
    when declarer or dummy is leading and opponents still hold
    trumps, lead the highest trump from this hand if it would win
    the trick (higher than any outstanding opponent trump).

    The textbook rule: 'Draw trumps before cashing side suits' and
    'Lead top trumps from the long hand'. This handles the Deal 17
    family (declarer led ♠7 from ♠AQ732 instead of ♠A).

    Returns None for: defender plays, NT contracts, opponents-out-of-
    trumps positions, hands where our highest trump can't beat
    opponents' highest. In those cases MC+DDS is left to choose.
    """
    if board.contract is None:
        return None
    if current_trick_cards:
        return None  # this is a follow-suit, not a lead
    trump = board.contract.suit
    if trump == Suit.NOTRUMP:
        return None  # no trump → no trump-drawing rule
    declarer = board.contract.declarer
    if not _is_declarer_side(seat, declarer):
        return None  # defender lead — leave to MC+DDS / future phase
    opp_trumps = _opponent_trump_count(board, declarer, trump,
                                        current_trick_cards or [])
    if opp_trumps <= 0:
        return None  # trumps drawn; no work for this rule
    my_trumps = _trump_cards_sorted_high(board.hands[seat], trump)
    if not my_trumps:
        return None  # no trumps to lead
    my_highest = my_trumps[0]
    opp_highest = _highest_outstanding_opp_trump(
        board, seat, declarer, trump, current_trick_cards or [])
    if opp_highest is None:
        return None  # contradiction with opp_trumps > 0; bail safely
    # Only cash if our highest beats their highest.
    if my_highest.rank.value < opp_highest.value:
        return my_highest
    return None


def planned_card(board: BoardState, seat: Seat,
                  current_trick_cards: Optional[List[Card]] = None
                  ) -> Optional[Card]:
    """Top-level entry point for the strategic planner. Returns a
    card to play, or None to fall through to MC+DDS.

    Currently dispatches LEAD vs FOLLOW. Phase 1 implements LEAD
    only; follow-suit support is left to MC+DDS for now."""
    if current_trick_cards:
        return None  # follow-suit → future phase
    return planned_lead(board, seat, current_trick_cards)
