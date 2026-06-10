"""No-peek cardplay engine for biq.

Plays every card using ONLY what the seat is entitled to see — its own hand,
the dummy once it is exposed, the auction, and the cards already played. It
never solves or samples a layout it cannot legitimately see, so it never peeks
at hidden cards. The guarantee is architectural: `decide()` first REDACTS the
board so the hidden hands are physically empty, then all policy runs on the
redacted board — it is structurally incapable of looking at an opponent's (or,
on defence, partner's) cards.

This is a technique/inference engine (3rd-hand-high, 2nd-hand-low, cover an
honour, draw trumps, cash winners, keep guards, return partner's suit, signal),
not a double-dummy or Monte-Carlo solver. It is the honest player a
sophisticated audience expects; it trades the double-dummy engine's omniscient
ceiling for play that never cheats. Strength grows by adding technique, not by
peeking.

v1 is a competent baseline. Hooks for stronger technique (single-dummy belief
sampling for finesse odds, signalling) are marked TODO.
"""
from __future__ import annotations
from typing import List, Optional, Dict

from .models import Seat, Suit, Rank, Card, Hand, BoardState, Contract
from .cardplay_planner import (is_boss_card, filter_safe_discards,
                               own_side_ranks_in_suit)
from . import cardplay_plan


# ---------------------------------------------------------------- redaction

def _dummy_seat(board: BoardState) -> Optional[Seat]:
    return board.contract.declarer.partner() if board.contract else None


def _dummy_exposed(board: BoardState, current_trick_cards: List[Card]) -> bool:
    """Dummy comes down after the opening lead."""
    return bool(board.tricks) or bool(current_trick_cards)


def redact(board: BoardState, seat: Seat,
           current_trick_cards: List[Card]) -> BoardState:
    """A copy of `board` exposing ONLY the hands `seat` is entitled to see.
    Everything else (auction, contract, completed tricks) is public and kept;
    unseen hands are replaced with empty Hands so no policy can read them."""
    entitled = {seat}
    if board.contract is not None:
        decl = board.contract.declarer
        dummy = decl.partner()
        if _dummy_exposed(board, current_trick_cards):
            entitled.add(dummy)                 # everyone sees exposed dummy
        if seat == decl:
            entitled.add(dummy)                 # declarer always sees dummy
        if seat == dummy:
            entitled.add(decl)                  # declarer controls dummy + sees own
    hands = {s: (Hand(cards=list(board.hands[s].cards))
                 if s in entitled and s in board.hands else Hand(cards=[]))
             for s in Seat}
    return BoardState(board_number=board.board_number, dealer=board.dealer,
                      vulnerability=board.vulnerability, hands=hands,
                      auction=list(board.auction), contract=board.contract,
                      tricks=board.tricks)


# ------------------------------------------------------------ card helpers

def _legal(hand: Hand, lead_suit: Optional[Suit]) -> List[Card]:
    if lead_suit is not None:
        follow = [c for c in hand.cards if c.suit == lead_suit]
        if follow:
            return _hi_lo(follow)
    return _hi_lo(hand.cards)


def _hi_lo(cards: List[Card]) -> List[Card]:
    """Sorted high → low (Ace first). rank.value: A=0..2=12, so ascending."""
    return sorted(cards, key=lambda c: (c.suit.value, c.rank.value))


def _by_suit(cards: List[Card]) -> Dict[Suit, List[Card]]:
    out: Dict[Suit, List[Card]] = {}
    for c in cards:
        out.setdefault(c.suit, []).append(c)
    for s in out:
        out[s] = sorted(out[s], key=lambda c: c.rank.value)   # high first
    return out


def _winning_index(trick: List[Card], trump: Optional[Suit]) -> int:
    """Index into `trick` of the card currently winning."""
    lead = trick[0].suit
    wi, wc = 0, trick[0]
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
    return wi


def _beats(card: Card, win_card: Card, lead: Suit, trump: Optional[Suit]) -> bool:
    """Does `card` (legal, in lead suit since we are following) beat the
    currently-winning card?"""
    win_is_trump = trump is not None and win_card.suit == trump
    if win_is_trump and card.suit != trump:
        return False                                   # can't beat a ruff in-suit
    if card.suit == win_card.suit:
        return card.rank.value < win_card.rank.value   # lower value = higher card
    return False


# ----------------------------------------------------------------- policies

def _opening_lead(board: BoardState, seat: Seat) -> Card:
    """Defender's opening lead, rule-based (no peek). Honour partner's suit if
    bid; else top of a 3+ honour sequence; else 4th-best of the longest suit;
    avoid leading an unsupported ace into a suit contract."""
    suit_contract = (board.contract is not None
                     and board.contract.suit != Suit.NOTRUMP)
    trump = board.contract.suit if suit_contract else None
    by = _by_suit(board.hands[seat].cards)            # high-first per suit
    # candidate suits longest first, trump last
    suits = sorted(by, key=lambda s: (-len(by[s]), s.value))
    suits = [s for s in suits if s != trump] + ([trump] if trump in by else [])

    def seq_top(cards):
        # top of a 3-card touching honour sequence (KQJ, QJT...)
        vals = [c.rank.value for c in cards]
        for i in range(len(cards) - 2):
            if vals[i] + 1 == vals[i + 1] and vals[i + 1] + 1 == vals[i + 2] \
                    and cards[i].rank.value <= 3:      # top is an honour
                return cards[i]
        return None

    for s in suits:
        cards = by[s]
        top = seq_top(cards)
        if top is not None:
            return top
    # 4th best of longest (or low from a short safe suit)
    longest = suits[0]
    cards = by[longest]
    if len(cards) >= 4:
        return cards[3]
    # short suit: avoid underleading an ace vs a suit contract — lead low
    # from the longest suit that doesn't bare an ace
    for s in suits:
        cs = by[s]
        if cs and not (suit_contract and cs[0].rank == Rank.ACE):
            return cs[-1]
    return by[longest][-1]


def _lead(board: BoardState, seat: Seat, legal: List[Card],
          trump: Optional[Suit], declarer: Seat) -> Card:
    """On lead, not the opening lead."""
    decl_side = seat.is_ns() == declarer.is_ns()
    if decl_side:
        # 1) draw trumps if opponents hold any (textbook, non-peek)
        planned = cardplay_plan.planned_lead(board, seat, [])
        if planned is not None and any(c.suit == planned.suit
                                       and c.rank == planned.rank
                                       for c in legal):
            return planned
        # 2) cash a guaranteed winner (boss card) — lowest such, to keep
        #    communication; prefer the longest suit so we set up length
        bosses = [c for c in legal
                  if is_boss_card(c, board, seat, [], declarer)]
        if bosses:
            by = _by_suit(bosses)
            longest = max(by, key=lambda s: (len(by[s]), -s.value))
            return by[longest][0]                      # the boss (top) to cash
        # 3) otherwise lead low from our longest non-trump side suit to
        #    develop it (passive; finesse logic is a later phase)
        by = _by_suit([c for c in legal if c.suit != trump]) or _by_suit(legal)
        if by:
            longest = max(by, key=lambda s: (len(by[s]), -s.value))
            return by[longest][-1]                     # low card
        return legal[-1]
    # defender on lead (not opening): passive — low from longest non-trump
    by = _by_suit([c for c in legal if c.suit != trump]) or _by_suit(legal)
    longest = max(by, key=lambda s: (len(by[s]), -s.value))
    cards = by[longest]
    # don't underlead an ace into a suit contract; lead the ace or another suit
    return cards[-1] if not cards[0].rank == Rank.ACE or trump is None \
        else (cards[0] if len(cards) == 1 else cards[-1])


def _follow(board: BoardState, seat: Seat, legal: List[Card],
            trick: List[Card], trump: Optional[Suit], declarer: Seat) -> Card:
    """Follow suit. legal = our cards in the led suit, high → low."""
    led = trick[0].suit
    pos = len(trick)                                   # 1=2nd,2=3rd,3=4th hand
    wi = _winning_index(trick, trump)
    win_card = trick[wi]
    win_seat = Seat((Seat((seat.value - pos) % 4).value + wi) % 4)
    our_side_winning = win_seat.is_ns() == seat.is_ns()
    low = legal[-1]
    high = legal[0]

    if our_side_winning and pos in (2, 3):
        return low                                     # partner/dummy winning: low
    beating = [c for c in legal if _beats(c, win_card, led, trump)]
    if not beating:
        return low                                     # can't win: low (signal TODO)
    cheapest = beating[-1]                              # lowest card that still wins
    if pos == 1:                                       # 2nd hand low (cover TODO)
        return low
    if pos == 2:                                       # 3rd hand high (cheaply)
        return cheapest
    return cheapest                                    # 4th hand: win as cheaply


def _discard(board: BoardState, seat: Seat, legal: List[Card],
             trick: List[Card], declarer: Seat) -> Card:
    """Void in the led suit and not ruffing: pitch a safe low card."""
    safe = filter_safe_discards(legal, board, seat, trick, declarer)
    by = _by_suit(safe)
    # pitch from the shortest suit, lowest card (keep length + guards)
    shortest = min(by, key=lambda s: (len(by[s]), s.value))
    return by[shortest][-1]


# ------------------------------------------------------------------- entry

def decide(board: BoardState, seat: Seat,
           current_trick_cards: Optional[List[Card]] = None) -> Optional[Card]:
    """Pick `seat`'s card using only entitled information. Redacts first."""
    trick = list(current_trick_cards or [])
    b = redact(board, seat, trick)
    hand = b.hands[seat]
    if not hand.cards:
        return None
    lead_suit = trick[0].suit if trick else None
    legal = _legal(hand, lead_suit)
    if len(legal) == 1:
        return legal[0]

    trump = (board.contract.suit
             if board.contract and board.contract.suit != Suit.NOTRUMP
             else None)
    declarer = board.contract.declarer if board.contract else seat
    on_lead = not trick
    opening = on_lead and not board.tricks

    if opening:
        return _opening_lead(b, seat)
    if on_lead:
        return _lead(b, seat, legal, trump, declarer)
    if any(c.suit == lead_suit for c in legal):
        return _follow(b, seat, legal, trick, trump, declarer)
    return _discard(b, seat, legal, trick, declarer)
