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


def _card_beats(candidate: Card, current_winner: Card,
                 lead_suit: Suit, trump: Optional[Suit]) -> bool:
    """Returns True if `candidate` would win over `current_winner`
    given the lead suit and trump suit (None for NT)."""
    cand_is_trump = trump is not None and candidate.suit == trump
    win_is_trump = trump is not None and current_winner.suit == trump
    if cand_is_trump and not win_is_trump:
        return True
    if win_is_trump and not cand_is_trump:
        return False
    if cand_is_trump and win_is_trump:
        return candidate.rank.value < current_winner.rank.value
    # Neither trump: only lead-suit cards can win
    if candidate.suit != lead_suit:
        return False
    if current_winner.suit != lead_suit:
        return True  # shouldn't happen in normal play, but be safe
    return candidate.rank.value < current_winner.rank.value


def _winning_index(trick_cards: List[Card],
                    trump: Optional[Suit]) -> int:
    """Index (0..n-1) of the card currently winning a partial or
    full trick."""
    if not trick_cards:
        return 0
    lead = trick_cards[0].suit
    best_idx = 0
    best = trick_cards[0]
    for i in range(1, len(trick_cards)):
        if _card_beats(trick_cards[i], best, lead, trump):
            best_idx = i
            best = trick_cards[i]
    return best_idx


def _lowest_in_suit(cards: List[Card]) -> Card:
    """Lowest rank from a list of single-suit cards (ACE=0 highest,
    TWO=12 lowest in Rank.value)."""
    return max(cards, key=lambda c: c.rank.value)


def _highest_in_suit(cards: List[Card]) -> Card:
    return min(cards, key=lambda c: c.rank.value)


def _max_opp_rank_in_suit(suit: Suit, board: BoardState, seat: Seat,
                           current_trick_cards: List[Card],
                           declarer: Seat) -> Optional[Rank]:
    """Highest rank of `suit` that could still be in opponents'
    hands from `seat`'s point of view. Visible = own hand + visible
    partner's hand (dummy if declarer-side; dummy if defender, since
    dummy is open) + played cards."""
    visible = set()
    visible |= {c.rank for c in board.hands[seat].cards if c.suit == suit}
    dummy = Seat((declarer + 2) % 4)
    if _is_declarer_side(seat, declarer):
        partner = _partner(seat)
        visible |= {c.rank for c in board.hands[partner].cards
                    if c.suit == suit}
    else:
        # Defender: dummy is open to all
        visible |= {c.rank for c in board.hands[dummy].cards
                    if c.suit == suit}
    for trick in getattr(board, "tricks", []) or []:
        for c in (getattr(trick, "cards", []) or []):
            if c.suit == suit:
                visible.add(c.rank)
    for c in current_trick_cards or []:
        if c.suit == suit:
            visible.add(c.rank)
    for r in _RANK_HI_TO_LO:
        if r not in visible:
            return r
    return None


def _partner_safe(partner_card: Card, board: BoardState, seat: Seat,
                   declarer: Seat, current_trick_cards: List[Card],
                   trump: Optional[Suit]) -> bool:
    """True if partner's already-played card cannot be beaten by any
    opponent card still possibly in play. Trump-aware: a non-trump
    partner-card is unsafe if opponents could trump."""
    # If partner's card is in the lead suit but opponents could
    # trump (suit contract, opponents short in lead suit), partner
    # is not safe. For Phase 2 we approximate: if trump != lead suit
    # and there's any chance opps are out of lead, we can't be sure.
    # Be conservative — if any unaccounted opponent trump and they
    # might be out of lead, consider partner unsafe.
    lead_suit = current_trick_cards[0].suit if current_trick_cards else partner_card.suit
    # Highest opp rank in the lead suit (the suit partner-card needs
    # to defend against).
    opp_max_lead = _max_opp_rank_in_suit(
        lead_suit, board, seat, current_trick_cards, declarer)
    if opp_max_lead is not None:
        if partner_card.suit == lead_suit:
            if partner_card.rank.value > opp_max_lead.value:
                return False  # opp could overtake in lead suit
        else:
            # Partner played off-suit (ruff in suit contract).
            # If it's a ruff, we have to ask: could opp over-ruff?
            if partner_card.suit == trump:
                opp_max_tr = _max_opp_rank_in_suit(
                    trump, board, seat, current_trick_cards, declarer)
                if opp_max_tr is not None and opp_max_tr.value < partner_card.rank.value:
                    return False
    # Suit-contract ruff risk: opponents trump our non-trump winner.
    if (trump is not None and partner_card.suit != trump):
        opp_max_trump = _max_opp_rank_in_suit(
            trump, board, seat, current_trick_cards, declarer)
        if opp_max_trump is not None:
            # Opponents could have a trump; partner not safe.
            return False
    return True


def _unblock_card(my_in_suit: List[Card], winning_card: Card,
                   board: BoardState, seat: Seat,
                   declarer: Seat) -> Optional[Card]:
    """Phase 3 rule — declarer-side unblock to preserve partner's
    length, tightly gated.

    Returns a card to UNBLOCK (a higher card to drop), or None.

    A first-cut version fired whenever own-side was shorter than
    partner; that over-fired in NT (−0.50 tricks/deal) because
    "drop the K under partner's Q" is wrong when entries to the
    long hand exist elsewhere. Tightened to the classic unblock
    case only:

    - I have ≤ 2 cards in this suit (singleton or doubleton —
      i.e., I will likely be void within 1-2 rounds and can't
      provide later entries via this suit).
    - Partner has ≥ 3 cards (genuine length to preserve).
    - Partner's winning card is an actual honor (T or higher) —
      a winning spot card isn't worth dropping high under.
    - I have a card HIGHER than partner's winning card.

    Drops the LOWEST of my higher cards (preserve absolute boss).
    """
    if not _is_declarer_side(seat, declarer):
        return None
    if len(my_in_suit) > 2:
        return None
    partner = _partner(seat)
    suit = winning_card.suit
    partner_count = sum(1 for c in board.hands[partner].cards
                        if c.suit == suit)
    if partner_count < 3:
        return None
    # Honor check: Rank.value 0..4 = A,K,Q,J,T
    if winning_card.rank.value > 4:
        return None
    higher = [c for c in my_in_suit
              if c.rank.value < winning_card.rank.value]
    if not higher:
        return None
    return _lowest_in_suit(higher)


def planned_follow(board: BoardState, seat: Seat,
                    current_trick_cards: List[Card]) -> Optional[Card]:
    """Return the strategic-plan card for a FOLLOW-SUIT decision,
    or None to fall through to MC+DDS.

    Phase 2 rules (defender-mostly, all safety-gated):

    1. Don't overtake partner's safe winner. Universal — but only
       when partner's played card can't be beaten by any remaining
       opponent card (accounts for ruff threat in suit contracts).

    2. Second-hand-low (defender). When defender is 2nd-to-play,
       play lowest of suit.

    3. Third-hand-high (defender). When defender is 3rd-to-play and
       partner is NOT safe, play highest of suit to push declarer.

    4. Fourth-hand cheap-win-or-low (defender). Last-to-play: lowest
       card that beats the current winner, else lowest of suit.

    Declarer-side 2nd/3rd/4th-hand play is left to MC+DDS — those
    decisions depend on the declarer's strategic plan (entries, suit
    establishment, finesse position), which Phases 3+ will encode.
    Only the safety-gated Rule 1 applies universally.
    """
    if not current_trick_cards:
        return None  # this is a lead
    if board.contract is None:
        return None
    lead_suit = current_trick_cards[0].suit
    my_in_suit = [c for c in board.hands[seat].cards
                  if c.suit == lead_suit]
    if not my_in_suit:
        return None  # discarding — handled by cardplay_planner
    if len(my_in_suit) == 1:
        return my_in_suit[0]  # forced
    declarer = board.contract.declarer
    trump = (board.contract.suit
             if board.contract.suit != Suit.NOTRUMP else None)
    position = len(current_trick_cards) + 1  # 1..4
    leader = Seat((seat.value - (position - 1)) % 4)
    win_idx = _winning_index(current_trick_cards, trump)
    winning_seat = Seat((leader.value + win_idx) % 4)
    winning_card = current_trick_cards[win_idx]
    partner_seat = Seat((seat.value + 2) % 4)
    is_defender = not _is_declarer_side(seat, declarer)

    # (Phase 3 attempt — declarer-side unblock — was tested on
    # 62 deals and regressed vs Phase 2 v2 even with tight gates.
    # Without entry counting we can't tell when dropping a high
    # card under partner's honor preserves length vs throws away
    # the trick. Reverting until Phase 5+ when an entry tracker
    # exists; the `_unblock_card` helper is kept dead-code for the
    # entry-aware version to grow from.)

    # Rule 1 — Don't overtake partner's SAFE winner. Safety-gated:
    # only fires when partner's card can't be beaten by any
    # remaining opponent card (no ruff threat in suit contracts,
    # no higher card outstanding in the lead suit).
    if winning_seat == partner_seat:
        if _partner_safe(winning_card, board, seat, declarer,
                          current_trick_cards, trump):
            return _lowest_in_suit(my_in_suit)
        # Partner not safe — fall through to position-specific logic.

    # Defender-only rules below. Declarer-side 2nd/3rd/4th-hand play
    # is plan-driven and left to MC+DDS until Phase 3+.
    if not is_defender:
        return None

    # Rule 2 — Second hand low (defender).
    if position == 2:
        return _lowest_in_suit(my_in_suit)

    # Rule 3 — Third hand high (defender) when partner not safe.
    if position == 3:
        if _card_beats(_highest_in_suit(my_in_suit), winning_card,
                        lead_suit, trump):
            return _highest_in_suit(my_in_suit)
        return _lowest_in_suit(my_in_suit)

    # Rule 4 — Fourth hand cheap-win-or-low (defender).
    if position == 4:
        beat = [c for c in my_in_suit
                if _card_beats(c, winning_card, lead_suit, trump)]
        if beat:
            return _lowest_in_suit(beat)
        return _lowest_in_suit(my_in_suit)

    return None


def _cards_by_suit(hand) -> dict:
    out = {Suit.SPADES: [], Suit.HEARTS: [],
           Suit.DIAMONDS: [], Suit.CLUBS: []}
    for c in hand.cards:
        out[c.suit].append(c)
    return out


def _three_card_sequence_top(cards: List[Card]) -> Optional[Card]:
    """If `cards` contains 3 consecutive ranks (e.g. KQJ, QJT, JT9),
    return the highest card of that sequence. Otherwise None."""
    if len(cards) < 3:
        return None
    sorted_cards = sorted(cards, key=lambda c: c.rank.value)
    # Walk down looking for any 3-run of consecutive values
    for i in range(len(sorted_cards) - 2):
        a, b, c = sorted_cards[i], sorted_cards[i+1], sorted_cards[i+2]
        if (a.rank.value + 1 == b.rank.value
                and b.rank.value + 1 == c.rank.value):
            return a
    return None


def _partner_bid_suit(board: BoardState, seat: Seat) -> Optional[Suit]:
    """Find partner's first real suit bid in the auction. Returns
    Suit or None. Doubles, redoubles, NT bids, and passes are
    skipped."""
    auction = getattr(board, "auction", None) or []
    if not auction:
        return None
    dealer = board.dealer
    partner = _partner(seat)
    for i, bid in enumerate(auction):
        bidder = Seat((dealer.value + i) % 4)
        if bidder != partner:
            continue
        if bid.is_pass or bid.is_double or bid.is_redouble:
            continue
        if bid.suit is None or bid.suit == Suit.NOTRUMP:
            continue
        return bid.suit
    return None


def planned_opening_lead(board: BoardState, seat: Seat
                          ) -> Optional[Card]:
    """Phase 3 — defender's opening-lead rules (textbook).

    Fires only when:
    - There's a contract.
    - Seat is LHO of declarer (the standard opening leader).
    - No card has been played yet (board.tricks is empty AND no
      current trick cards — caller's responsibility).

    Lead-selection priority:
    1. Partner's bid suit — 4th-best if 4+, top of 3-card sequence,
       else top of doubleton, else low from honor in 3-card.
    2. Top of a 3-card sequence (KQJ, QJT, JT9) in any non-trump
       suit.
    3. 4th-best from the longest non-trump suit, if 4+ cards.

    Returns None if no rule fires cleanly (then MC+DDS picks).
    Avoids leading trumps and avoids singletons/short suits when no
    clear textbook lead applies — those need more context (ruff
    play, suit-preference signal expectations) than Phase 3 has.
    """
    if board.contract is None:
        return None
    declarer = board.contract.declarer
    if _is_declarer_side(seat, declarer):
        return None
    if seat != Seat((declarer.value + 1) % 4):
        return None  # not LHO; not the opening leader
    if getattr(board, "tricks", None):
        return None  # not T1
    hand = board.hands[seat]
    trump = (board.contract.suit
             if board.contract.suit != Suit.NOTRUMP else None)
    by_suit = _cards_by_suit(hand)

    # Rule 1: Partner's bid suit
    partner_suit = _partner_bid_suit(board, seat)
    if partner_suit is not None and by_suit.get(partner_suit):
        cards = by_suit[partner_suit]
        if trump is None or partner_suit != trump:
            # Top of 3-card sequence in partner's suit
            seq = _three_card_sequence_top(cards)
            if seq is not None:
                return seq
            if len(cards) >= 4:
                # 4th-best
                sorted_hi_lo = sorted(cards, key=lambda c: c.rank.value)
                return sorted_hi_lo[3]
            if len(cards) == 2:
                # Top of doubleton
                return min(cards, key=lambda c: c.rank.value)
            if len(cards) == 3:
                # Low from honor (Hxx) — lowest of three
                return max(cards, key=lambda c: c.rank.value)
            # Singleton — lead it (mild signal; partner expects honor here)
            if len(cards) == 1:
                return cards[0]

    # Rule 2: Top of a 3-card sequence in any non-trump suit
    for suit, cards in by_suit.items():
        if suit == trump:
            continue
        seq = _three_card_sequence_top(cards)
        if seq is not None:
            return seq

    # Rule 3: 4th best from longest non-trump
    non_trump_lengths = {
        s: len(cs) for s, cs in by_suit.items()
        if s != trump}
    if non_trump_lengths:
        longest = max(non_trump_lengths, key=non_trump_lengths.get)
        if non_trump_lengths[longest] >= 4:
            cards = sorted(by_suit[longest], key=lambda c: c.rank.value)
            return cards[3]

    return None


def planned_card(board: BoardState, seat: Seat,
                  current_trick_cards: Optional[List[Card]] = None
                  ) -> Optional[Card]:
    """Top-level entry point for the strategic planner. Returns a
    card to play, or None to fall through to MC+DDS.

    Dispatches LEAD vs FOLLOW. Phase 1 handles declarer's trump-
    drawing LEAD; Phase 3 handles defender's opening-lead T1; Phase
    2 handles FOLLOW (don't-overtake-partner, second/third-hand
    defender, fourth-hand cheap-win-or-low).
    """
    if current_trick_cards:
        return planned_follow(board, seat, current_trick_cards)
    # Phase 3: defender opening lead (only fires on T1 from LHO).
    op_lead = planned_opening_lead(board, seat)
    if op_lead is not None:
        return op_lead
    return planned_lead(board, seat, current_trick_cards)
