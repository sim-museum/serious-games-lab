"""Defensive SIGNALLING — standard (textbook) attitude / count / suit-preference.

A good player reads a defender's spot cards as a running commentary. biq's no-peek
defence used to play the LOWEST card whenever it couldn't win (signalling was a
TODO), so its carding told partner nothing — the clearest "this is a bot" tell.
This picks the signalling card AMONG TRICK-EQUIVALENT candidates, so it costs no
tricks while making the play read like a real defender:

  * ATTITUDE on partner's suit (partner led or is winning): a HIGH spot
    ENCOURAGES (I have something / want it continued), a LOW spot discourages.
  * COUNT when following an opponent's suit without trying to win: high spot =
    even remaining, low spot = odd (present count).
  * SUIT-PREFERENCE / attitude on a DISCARD (mixed suits): pitch in the suit you
    care least about, the rank giving Lavinthal suit-preference for the others.

All "standard signals" (high = encourage / even) — the most universally read, in
keeping with biq's textbook-not-eccentric philosophy. The single entry point is
choose_signal_card(); per-seat carding and the alpha-mu tie-break both call it.
"""
from __future__ import annotations
import os
from typing import List, Optional

from .models import Seat, Suit, Rank, Card, BoardState

_HONOUR = 3   # rank.value: A=0,K=1,Q=2,J=3 are honours; T=4; spots are 5..12

# Signalling CONVENTION (the config setting every serious app exposes). False =
# STANDARD (high spot encourages / high-low shows even count); True = UPSIDE-DOWN
# (UDCA: low spot encourages / low-high shows even). The emitter AND the reader
# (signal_read) both consult this, so biq's signals and its reading of partner
# always agree. Set from the GUI preference via set_convention().
_UDCA = os.environ.get("BIQ_SIGNAL_UDCA", "0") == "1"


def set_convention(udca: bool) -> None:
    global _UDCA
    _UDCA = bool(udca)


def is_udca() -> bool:
    return _UDCA


def _winner_seat(trick: List[Card], leader: Seat, trump: Optional[Suit]) -> Seat:
    wi, wc, lead = 0, trick[0], trick[0].suit
    for i, c in enumerate(trick[1:], 1):
        c_t = trump is not None and c.suit == trump
        w_t = trump is not None and wc.suit == trump
        if c_t and not w_t:
            wi, wc = i, c
        elif c_t and w_t and c.rank.value < wc.rank.value:
            wi, wc = i, c
        elif not c_t and not w_t and c.suit == lead \
                and c.rank.value < wc.rank.value:
            wi, wc = i, c
    return Seat((leader.value + wi) % 4)


def _hl(cands: List[Card], high: bool) -> Card:
    """Among `cands`, return the high or low SPOT (keep honours back when there
    is a spot to spend). rank.value: 0=A (high) .. 12=2 (low)."""
    spots = [c for c in cands if c.rank.value > _HONOUR + 1] or list(cands)
    spots = sorted(spots, key=lambda c: c.rank.value)   # high card first
    return spots[0] if high else spots[-1]


def _like_suit(suit_cards: List[Card], trump: Optional[Suit]) -> bool:
    """Do we want partner to continue this suit? Encourage when we hold an
    honour to contribute, or (in a trump contract) a doubleton to ruff."""
    if any(c.rank.value <= _HONOUR for c in suit_cards):
        return True
    return trump is not None and len(suit_cards) == 2


def _discard_signal(cands: List[Card], board: BoardState, seat: Seat,
                    trump: Optional[Suit]) -> Card:
    """Mixed-suit candidates (a discard): pitch in the suit we care least about
    (no honour, longest), giving Lavinthal suit-preference within it — a HIGH
    pitch points to the higher-ranking of the other suits, LOW to the lower."""
    by: dict = {}
    for c in cands:
        by.setdefault(c.suit, []).append(c)
    # prefer a suit with no honour; among those the longest (most expendable)
    def honourless(s):
        return not any(c.rank.value <= _HONOUR
                       for c in board.hands[seat].cards if c.suit == s)
    suits = sorted(by, key=lambda s: (not honourless(s), -len(by[s]), s.value))
    suit = suits[0]
    group = sorted(by[suit], key=lambda c: c.rank.value)        # high → low
    # Suit-preference: high pitch = like the higher of the OTHER two side suits.
    others = sorted((s for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS,
                                 Suit.CLUBS) if s != suit and s != trump),
                    key=lambda s: s.value)
    if len(others) >= 2:
        hi_like = _like_suit([c for c in board.hands[seat].cards
                              if c.suit == others[0]], trump)
        lo_like = _like_suit([c for c in board.hands[seat].cards
                              if c.suit == others[1]], trump)
        if hi_like and not lo_like:
            return group[0]            # high spot → points to higher suit
        if lo_like and not hi_like:
            return group[-1]           # low spot → points to lower suit
    return group[-1]                   # default: low (discouraging the pitch suit)


def choose_signal_card(cands: List[Card], board: BoardState, seat: Seat,
                       trick: List[Card], declarer: Seat,
                       trump: Optional[Suit]) -> Card:
    """Among TRICK-EQUIVALENT candidates `cands`, return the one carrying the
    standard signal. Same-suit follows → attitude (partner's suit) or count
    (opponent's suit); mixed suits / on a discard → suit-preference."""
    if len(cands) <= 1:
        return cands[0]
    pos = len(trick)
    if pos == 0 or len({c.suit for c in cands}) > 1:
        return _discard_signal(cands, board, seat, trump)
    led = trick[0].suit
    leader = Seat((seat.value - pos) % 4)
    winner = _winner_seat(trick, leader, trump)
    partner_context = leader.is_ns() == seat.is_ns() \
        or winner.is_ns() == seat.is_ns()
    suit_cards = [c for c in board.hands[seat].cards if c.suit == led]
    if partner_context:                       # ATTITUDE
        like = _like_suit(suit_cards, trump)
        return _hl(cands, high=(like != _UDCA))          # UDCA flips encourage
    even = (len(suit_cards) % 2 == 0)                     # COUNT
    return _hl(cands, high=(even != _UDCA))               # std: even=high spot
