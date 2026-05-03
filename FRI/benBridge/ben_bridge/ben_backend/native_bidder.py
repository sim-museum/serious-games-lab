"""
NativeBiddingEngine — a from-scratch rule-based bidder modelled on Qplus 17.

Plug-compatible with BridgeEngine.get_bid: takes (BoardState, Seat) and
returns an EngineResponse whose `action` is the chosen Bid. Card play
is NOT handled here; the caller keeps using BEN for card decisions.

Two systems are wired:
  * "SAYC"      — SAYC/2-over-1 hybrid (the default)
  * "Precision" — strong-club Precision; just one variant, picked to match
                  what most casual players expect.

Conventions implemented across both systems:
  Stayman, Jacoby transfers (major + Texas), Blackwood / 1430 RKC,
  Splinters, Negative Doubles, Smolen, Lebensohl (over 1NT-(2X)),
  Michaels cuebid, Unusual 2NT, jump preempts, weak twos.

The dispatch is a flat decision tree keyed on auction state — there is no
attempt at tree search or probabilistic sampling. The goal is "a defensible
bid for every common situation"; pathological auctions fall back to Pass.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import (
    Bid, BoardState, Card, Hand, Seat, Suit, Vulnerability, Rank,
)


# ---------------------------------------------------------------------------
# Hand evaluation
# ---------------------------------------------------------------------------

@dataclass
class HandEval:
    """Cached metrics for the bidder. Computed once per call."""
    hcp: int
    suit_lengths: dict       # Suit -> int
    suit_hcp: dict           # Suit -> int (HCP within that suit)
    distribution: tuple      # (s, h, d, c) sorted descending
    longest_suit: Suit       # Best suit candidate (longest, tie → higher rank)
    second_suit: Optional[Suit]
    is_balanced: bool
    is_semi_balanced: bool   # 5-3-3-2
    voids: int
    singletons: int
    doubletons: int
    losers: int              # Losing-Trick Count
    controls: int            # A=2, K=1
    quick_tricks: float
    five_card_majors: List[Suit]
    six_card_suits: List[Suit]


def evaluate_hand(hand: Hand) -> HandEval:
    """Build a HandEval for the given hand."""
    by_suit = {s: [] for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)}
    for card in hand.cards:
        by_suit[card.suit].append(card)

    suit_lengths = {s: len(cs) for s, cs in by_suit.items()}
    suit_hcp = {s: sum(_card_hcp(c) for c in cs) for s, cs in by_suit.items()}
    hcp = sum(suit_hcp.values())

    dist = tuple(sorted(suit_lengths.values(), reverse=True))
    is_balanced = dist in ((4, 3, 3, 3), (4, 4, 3, 2), (5, 3, 3, 2))
    is_semi_balanced = dist == (5, 3, 3, 2)

    voids = sum(1 for v in suit_lengths.values() if v == 0)
    singletons = sum(1 for v in suit_lengths.values() if v == 1)
    doubletons = sum(1 for v in suit_lengths.values() if v == 2)

    # Pick the longest suit; break ties by rank (S > H > D > C)
    rank_order = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
    sorted_suits = sorted(rank_order,
                          key=lambda s: (suit_lengths[s], rank_order.index(s) * -1),
                          reverse=True)
    longest_suit = sorted_suits[0]
    second_suit = sorted_suits[1] if suit_lengths[sorted_suits[1]] >= 4 else None

    losers = _losing_trick_count(by_suit)
    controls = _controls(by_suit)
    quick_tricks = _quick_tricks(by_suit)

    five_card_majors = [s for s in (Suit.SPADES, Suit.HEARTS) if suit_lengths[s] >= 5]
    six_card_suits = [s for s, n in suit_lengths.items() if n >= 6]

    return HandEval(
        hcp=hcp,
        suit_lengths=suit_lengths,
        suit_hcp=suit_hcp,
        distribution=dist,
        longest_suit=longest_suit,
        second_suit=second_suit,
        is_balanced=is_balanced,
        is_semi_balanced=is_semi_balanced,
        voids=voids,
        singletons=singletons,
        doubletons=doubletons,
        losers=losers,
        controls=controls,
        quick_tricks=quick_tricks,
        five_card_majors=five_card_majors,
        six_card_suits=six_card_suits,
    )


def _card_hcp(c: Card) -> int:
    return max(0, 4 - c.rank.value)  # ACE=0 → 4 HCP, KING=1 → 3, ...


def _losing_trick_count(by_suit) -> int:
    """Standard LTC: per suit, lose for missing top three cards (A/K/Q)."""
    total = 0
    for cards in by_suit.values():
        n = len(cards)
        if n == 0:
            continue
        # Look at the top three cards of the suit (or fewer if short).
        ranks_held = {c.rank for c in cards}
        max_losers = min(n, 3)
        loser = max_losers
        if Rank.ACE in ranks_held:
            loser -= 1
        if Rank.KING in ranks_held and max_losers >= 2:
            loser -= 1
        if Rank.QUEEN in ranks_held and max_losers >= 3:
            loser -= 1
        total += loser
    return total


def _controls(by_suit) -> int:
    """Sum of A=2, K=1 across all suits."""
    total = 0
    for cards in by_suit.values():
        for c in cards:
            if c.rank == Rank.ACE:
                total += 2
            elif c.rank == Rank.KING:
                total += 1
    return total


def _quick_tricks(by_suit) -> float:
    """Per-suit quick tricks: AK=2, AQ=1.5, A=1, KQ=1, K=0.5 (only when not 1-card)."""
    total = 0.0
    for cards in by_suit.values():
        ranks = {c.rank for c in cards}
        n = len(cards)
        if Rank.ACE in ranks and Rank.KING in ranks:
            total += 2.0
        elif Rank.ACE in ranks and Rank.QUEEN in ranks:
            total += 1.5
        elif Rank.ACE in ranks:
            total += 1.0
        elif Rank.KING in ranks and Rank.QUEEN in ranks:
            total += 1.0
        elif Rank.KING in ranks and n >= 2:
            total += 0.5
    return total


# ---------------------------------------------------------------------------
# Auction state
# ---------------------------------------------------------------------------

@dataclass
class AuctionState:
    """Parsed auction information needed to choose the next bid."""
    seat: Seat                          # Whose turn it is
    dealer: Seat
    bids: List[Tuple[Seat, Bid]]        # (bidder, bid) in chronological order
    last_non_pass: Optional[Tuple[Seat, Bid]]
    consecutive_passes: int
    opener_seat: Optional[Seat]         # First non-pass bidder
    opening_bid: Optional[Bid]
    partner_bids: List[Bid]             # Partner's non-pass calls
    my_bids: List[Bid]                  # My non-pass calls
    rho_bids: List[Bid]                 # Bids by my RHO since my last action
    lho_bids: List[Bid]                 # Bids by my LHO since my last action
    suit_bid_by_partner: List[Suit]     # Suits partner has bid (no NT)
    suit_bid_by_me: List[Suit]
    suit_bid_by_opps: List[Suit]
    opp_overcalled: bool
    is_competitive: bool
    last_suit_bid: Optional[Suit]       # Most recent denomination
    last_level: int


def parse_auction(seat: Seat, dealer: Seat, auction: List[Bid]) -> AuctionState:
    """Build an AuctionState. The bidder seats rotate clockwise from dealer."""
    bids: List[Tuple[Seat, Bid]] = []
    bidder = dealer
    for bid in auction:
        bids.append((bidder, bid))
        bidder = bidder.next()

    last_non_pass = None
    consecutive_passes = 0
    for s, b in reversed(bids):
        if not (b.is_pass):
            last_non_pass = (s, b)
            break
        consecutive_passes += 1

    opener_seat = None
    opening_bid = None
    for s, b in bids:
        if not b.is_pass:
            opener_seat = s
            opening_bid = b
            break

    partner = seat.partner()
    lho = seat.next()
    rho = lho.next().next()  # = seat.partner().next() = seat.next().next().next()

    partner_bids = [b for s, b in bids if s == partner and not b.is_pass]
    my_bids = [b for s, b in bids if s == seat and not b.is_pass]
    rho_bids = [b for s, b in bids if s == rho and not b.is_pass]
    lho_bids = [b for s, b in bids if s == lho and not b.is_pass]

    def _suits(bs: List[Bid]) -> List[Suit]:
        return [b.suit for b in bs if b.suit is not None and b.suit != Suit.NOTRUMP]

    suit_bid_by_partner = _suits(partner_bids)
    suit_bid_by_me = _suits(my_bids)
    suit_bid_by_opps = _suits(rho_bids + lho_bids)

    opp_overcalled = bool(rho_bids + lho_bids)
    is_competitive = opp_overcalled

    last_suit_bid = last_non_pass[1].suit if last_non_pass else None
    last_level = last_non_pass[1].level if last_non_pass else 0

    return AuctionState(
        seat=seat,
        dealer=dealer,
        bids=bids,
        last_non_pass=last_non_pass,
        consecutive_passes=consecutive_passes,
        opener_seat=opener_seat,
        opening_bid=opening_bid,
        partner_bids=partner_bids,
        my_bids=my_bids,
        rho_bids=rho_bids,
        lho_bids=lho_bids,
        suit_bid_by_partner=suit_bid_by_partner,
        suit_bid_by_me=suit_bid_by_me,
        suit_bid_by_opps=suit_bid_by_opps,
        opp_overcalled=opp_overcalled,
        is_competitive=is_competitive,
        last_suit_bid=last_suit_bid,
        last_level=last_level,
    )


# ---------------------------------------------------------------------------
# Bid construction helpers
# ---------------------------------------------------------------------------

def bid(level: int, suit: Suit, *, alert: bool = False, why: str = "") -> Bid:
    return Bid(level=level, suit=suit, alert=alert, explanation=why)


def passb(why: str = "") -> Bid:
    return Bid(is_pass=True, explanation=why)


def double(why: str = "") -> Bid:
    return Bid(is_double=True, explanation=why)


_BID_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2,
             Suit.SPADES: 3, Suit.NOTRUMP: 4}


def is_legal_after(prev_level: int, prev_suit: Optional[Suit],
                   level: int, suit: Suit) -> bool:
    """Strictly-higher-than-previous check used for sanity."""
    if level > prev_level:
        return True
    if level < prev_level:
        return False
    if prev_suit is None:
        return False
    return _BID_RANK[suit] > _BID_RANK[prev_suit]


# ---------------------------------------------------------------------------
# Opening rules
# ---------------------------------------------------------------------------

def open_bid(eval_: HandEval, system: str = "SAYC") -> Bid:
    """Pick an opening bid (or Pass) given the hand."""
    if system == "Precision":
        return _open_precision(eval_)
    return _open_sayc(eval_)


def _open_sayc(e: HandEval) -> Bid:
    hcp = e.hcp

    # Strong artificial 2C
    if hcp >= 22 or (e.controls >= 4 and e.quick_tricks >= 4 and hcp >= 19):
        return bid(2, Suit.CLUBS, alert=True, why="Strong, artificial, GF unless 2C-2D-2NT")

    # Notrump openings (balanced)
    if e.is_balanced or e.is_semi_balanced:
        if 15 <= hcp <= 17:
            return bid(1, Suit.NOTRUMP, why="15-17 balanced")
        if 20 <= hcp <= 21:
            return bid(2, Suit.NOTRUMP, why="20-21 balanced")
        if 25 <= hcp <= 27:
            return bid(3, Suit.NOTRUMP, why="25-27 balanced")
        # 12-14 balanced opens 1 of a minor (better minor) — fall through
        # 18-19 balanced opens 1 of a suit then jumps in NT — fall through

    # Sub-opening hands → Pass (or skip preempts handled below)
    if hcp < 12 and not _has_preempt(e):
        return passb(why="Insufficient values")

    # Preempts
    pre = _preempt_bid(e)
    if pre is not None:
        return pre

    # Suit openings (12-21 HCP, unbalanced or with 5cM)
    if hcp < 12:
        return passb()

    # 5-card major
    if e.suit_lengths[Suit.SPADES] >= 5 and e.suit_lengths[Suit.SPADES] >= e.suit_lengths[Suit.HEARTS]:
        return bid(1, Suit.SPADES, why="5+ spades")
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(1, Suit.HEARTS, why="5+ hearts")

    # No 5cM → open longer minor; with 3-3 minors open 1C (better with 4-4 → 1D)
    cl = e.suit_lengths[Suit.CLUBS]
    di = e.suit_lengths[Suit.DIAMONDS]
    if di > cl:
        return bid(1, Suit.DIAMONDS, why="Better minor")
    if cl > di:
        return bid(1, Suit.CLUBS, why="Better minor")
    # 3-3 → 1C; 4-4 → 1D
    if cl >= 4:
        return bid(1, Suit.DIAMONDS, why="4-4 minors → 1D")
    return bid(1, Suit.CLUBS, why="3-3 minors → 1C")


def _open_precision(e: HandEval) -> Bid:
    """Single Precision variant: 1C = 16+ any shape, others limited."""
    hcp = e.hcp
    if hcp >= 16:
        return bid(1, Suit.CLUBS, alert=True, why="Precision: 16+ HCP, any shape")
    if hcp < 11:
        # weak preempts mirror SAYC
        pre = _preempt_bid(e)
        if pre is not None:
            return pre
        return passb()
    if 14 <= hcp <= 16 and (e.is_balanced or e.is_semi_balanced):
        return bid(1, Suit.NOTRUMP, alert=True, why="Precision: 14-16 balanced")
    # 11-15 unbalanced or 5-card major
    if e.suit_lengths[Suit.SPADES] >= 5 and e.suit_lengths[Suit.SPADES] >= e.suit_lengths[Suit.HEARTS]:
        return bid(1, Suit.SPADES, alert=True, why="Precision: 11-15, 5+ spades")
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(1, Suit.HEARTS, alert=True, why="Precision: 11-15, 5+ hearts")
    if e.suit_lengths[Suit.CLUBS] >= 6:
        return bid(2, Suit.CLUBS, alert=True, why="Precision: 11-15, 6+ clubs")
    if e.suit_lengths[Suit.DIAMONDS] >= 5 or hcp >= 11:
        return bid(1, Suit.DIAMONDS, alert=True, why="Precision: 11-15, no 5cM, no 6c clubs")
    return passb()


def _has_preempt(e: HandEval) -> bool:
    """Return True if the hand is shapely enough for a preempt (6-10 HCP)."""
    if 6 <= e.hcp <= 10:
        for s, n in e.suit_lengths.items():
            if n >= 6:
                return True
        return False
    if 5 <= e.hcp <= 9:
        # 7-card preempt at 3-level
        for s, n in e.suit_lengths.items():
            if n >= 7:
                return True
    return False


def _preempt_bid(e: HandEval) -> Optional[Bid]:
    """Pick a weak two / 3-level preempt if the hand fits."""
    if not (5 <= e.hcp <= 10):
        return None
    longest = e.longest_suit
    n = e.suit_lengths[longest]
    # Quality check: top two of the suit should include at least one honor
    # for a clean preempt. Loose for 3-level.
    if 6 <= n <= 6 and longest in (Suit.HEARTS, Suit.SPADES, Suit.DIAMONDS):
        return bid(2, longest, why="Weak two: 6-card suit, 6-10 HCP")
    if n >= 7:
        return bid(3, longest, why="Preempt: 7+ card suit, weak hand")
    if n >= 8:
        return bid(4, longest, why="Preempt: 8+ card suit, weak hand")
    return None


# ---------------------------------------------------------------------------
# Top-level decide
# ---------------------------------------------------------------------------

def decide_bid(state: AuctionState, eval_: HandEval, system: str) -> Bid:
    """Dispatch to the right decision function based on auction state."""
    # First call by anyone → opening
    if state.opener_seat is None:
        return open_bid(eval_, system=system)

    # Auction has already gone three passes after a bid → it's over
    if state.last_non_pass is None:
        return passb()
    if state.consecutive_passes >= 3 and state.last_non_pass[0] != state.seat:
        return passb()

    partner = state.seat.partner()
    is_my_partnership_opener = (state.opener_seat in (state.seat, partner))

    # Opener is partner → I'm responder (or rebidder)
    if state.opener_seat == partner:
        if not state.my_bids:
            return _respond_to_partner_opening(state, eval_, system)
        return _responder_rebid(state, eval_, system)

    # Opener is me → my rebid
    if state.opener_seat == state.seat:
        return _opener_rebid(state, eval_, system)

    # Opener is an opponent → competitive bidding
    if not is_my_partnership_opener:
        # If partner has acted, this is the advancer's job
        if state.partner_bids:
            return _advance_partner_overcall(state, eval_, system)
        return _overcall(state, eval_, system)

    return passb(why="(unhandled state)")


# ---------------------------------------------------------------------------
# Responses to partner's opening
# ---------------------------------------------------------------------------

def _respond_to_partner_opening(state, e, system):
    op = state.opening_bid
    hcp = e.hcp

    # Defenders' overcalls in between are handled separately. If RHO bid, this
    # is "opening + overcall + me", treated as competitive responses.
    rho_intervened = bool(state.rho_bids)

    # 1NT openings — Stayman, transfers, etc. (regardless of intervention,
    # but only the simple non-comp version here). Lebensohl handles 1NT-(2X).
    if op.level == 1 and op.suit == Suit.NOTRUMP:
        if rho_intervened:
            return _respond_to_1nt_competitive(state, e, system)
        return _respond_to_1nt(e)

    if op.level == 2 and op.suit == Suit.NOTRUMP:
        return _respond_to_2nt(e)

    # Strong 2C — by SAYC/2-over-1 convention 2C is always artificial GF
    # so we don't depend on the alert flag (auctions read off the wire
    # may not preserve it).
    if op.level == 2 and op.suit == Suit.CLUBS:
        return _respond_to_strong_2c(e)

    # Weak two openings
    if op.level == 2 and op.suit in (Suit.HEARTS, Suit.SPADES, Suit.DIAMONDS):
        return _respond_to_weak_two(state, e)

    # 3+ level preempts → mostly pass; raise to game with shape & values
    if op.level >= 3 and op.suit is not None and op.suit != Suit.NOTRUMP:
        return _respond_to_preempt(state, e)

    # 1-of-a-suit openings
    if op.level == 1 and op.suit in (Suit.CLUBS, Suit.DIAMONDS):
        if rho_intervened:
            return _respond_to_minor_competitive(state, e)
        return _respond_to_minor(state, e)

    if op.level == 1 and op.suit in (Suit.HEARTS, Suit.SPADES):
        if rho_intervened:
            return _respond_to_major_competitive(state, e)
        return _respond_to_major(state, e)

    return passb()


def _respond_to_1nt(e: HandEval) -> Bid:
    hcp = e.hcp

    # 0-7 with a long minor → drop on a partial / sign off
    if hcp <= 7 and not e.five_card_majors:
        # 5+ minor with weak hand → garbage Stayman (skipped) or pass
        return passb(why="0-7 HCP, no 4cM/5cM → pass 1NT")

    # Stayman with a 4-card major (and balanced or semi-balanced)
    has_4S = e.suit_lengths[Suit.SPADES] == 4
    has_4H = e.suit_lengths[Suit.HEARTS] == 4
    has_5S = e.suit_lengths[Suit.SPADES] >= 5
    has_5H = e.suit_lengths[Suit.HEARTS] >= 5

    # Jacoby transfers for 5+ cards in a major
    if has_5H or has_5S:
        # Texas (Jacoby Texas) for 6+ majors with game values
        if e.suit_lengths[Suit.HEARTS] >= 6 and hcp >= 10:
            return bid(4, Suit.DIAMONDS, alert=True, why="Texas: 6+ hearts, GF")
        if e.suit_lengths[Suit.SPADES] >= 6 and hcp >= 10:
            return bid(4, Suit.HEARTS, alert=True, why="Texas: 6+ spades, GF")
        # Standard Jacoby transfer
        if has_5H:
            return bid(2, Suit.DIAMONDS, alert=True, why="Jacoby transfer to hearts")
        return bid(2, Suit.HEARTS, alert=True, why="Jacoby transfer to spades")

    # Stayman
    if hcp >= 8 and (has_4S or has_4H):
        return bid(2, Suit.CLUBS, alert=True, why="Stayman, asks for 4cM")

    # No major → NT raises
    if hcp >= 10 and hcp <= 14:
        # Quantitative invitational
        if hcp <= 9:
            return passb()
        return bid(2, Suit.NOTRUMP, why="Invitational 8-9 → 9 HCP boundary")
    if hcp >= 15 and hcp <= 16:
        return bid(4, Suit.NOTRUMP, alert=True, why="Quantitative slam invite")
    if hcp >= 17:
        return bid(6, Suit.NOTRUMP, why="Slam values, no major fit")
    return bid(3, Suit.NOTRUMP, why="To-play game in NT")


def _respond_to_1nt_competitive(state, e, system):
    """Lebensohl after 1NT-(2X). Slow shows (2NT relay then bid suit) =
    weak; fast shows (direct 3X) = invitational+; cuebid of overcaller's
    suit = Stayman."""
    overcall = state.rho_bids[-1]
    if overcall.suit is None or overcall.suit == Suit.NOTRUMP:
        # Doubles / NT overcalls — fall back to non-competitive logic.
        return _respond_to_1nt(e)

    hcp = e.hcp
    overcall_suit = overcall.suit
    # With a stopper in opp's suit and game values, bid 3NT.
    if hcp >= 10 and _has_stopper(e, overcall_suit):
        return bid(3, Suit.NOTRUMP, why="Lebensohl: direct 3NT promises stopper")

    # 4-card major (different from opp's suit) → cuebid Stayman
    if hcp >= 10:
        majors = [Suit.SPADES, Suit.HEARTS]
        for m in majors:
            if e.suit_lengths[m] >= 4 and m != overcall_suit:
                return bid(overcall.level + 1, overcall_suit,
                           alert=True,
                           why="Lebensohl Stayman cuebid")

    # Long major → 5cM transfer-style (just bid the suit naturally at 3-level)
    for m in (Suit.SPADES, Suit.HEARTS):
        if e.suit_lengths[m] >= 5 and hcp >= 10 and m != overcall_suit:
            return bid(3, m, why="Long major, game values")

    # Weak with long suit → 2NT relay (signed off in 3 of own suit)
    if hcp <= 8 and any(e.suit_lengths[s] >= 5 for s in
                       (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
                       if s != overcall_suit):
        return bid(2, Suit.NOTRUMP, alert=True, why="Lebensohl relay (slow → weak)")

    # No fit, modest values → Pass
    if hcp <= 7:
        return passb(why="Insufficient to compete")

    # Negative double as catch-all takeout
    return double(why="Negative double for takeout (Lebensohl context)")


def _has_stopper(e: HandEval, suit: Suit) -> bool:
    """Heuristic: A, Kx, Qxx, Jxxx in a suit counts as a stopper."""
    n = e.suit_lengths.get(suit, 0)
    h = e.suit_hcp.get(suit, 0)
    if n >= 1 and h >= 4:  # Ace
        return True
    if n >= 2 and h >= 3:  # Kx
        return True
    if n >= 3 and h >= 2:  # Qxx
        return True
    if n >= 4 and h >= 1:  # Jxxx
        return True
    return False


def _respond_to_2nt(e: HandEval) -> Bid:
    hcp = e.hcp
    # 5-card major → transfer (2NT-3D=hearts, 2NT-3H=spades)
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(3, Suit.DIAMONDS, alert=True, why="Jacoby transfer to hearts (over 2NT)")
    if e.suit_lengths[Suit.SPADES] >= 5:
        return bid(3, Suit.HEARTS, alert=True, why="Jacoby transfer to spades (over 2NT)")
    # Stayman
    if e.suit_lengths[Suit.SPADES] == 4 or e.suit_lengths[Suit.HEARTS] == 4:
        return bid(3, Suit.CLUBS, alert=True, why="Stayman over 2NT")
    if hcp <= 4:
        return bid(3, Suit.NOTRUMP, why="Sign off in 3NT (modest values)")
    if hcp >= 11:
        return bid(4, Suit.NOTRUMP, alert=True, why="Quantitative slam invite")
    return bid(3, Suit.NOTRUMP, why="To-play 3NT")


def _respond_to_strong_2c(e: HandEval) -> Bid:
    """Default response: 2D = waiting (negative or any). With 8+ HCP and a
    decent 5+ suit, bid the suit naturally at the 2-level."""
    if e.hcp >= 8:
        for s in (Suit.HEARTS, Suit.SPADES):
            if e.suit_lengths[s] >= 5:
                return bid(2, s, why="Strong response to 2C: 5+ suit, 8+ HCP")
    return bid(2, Suit.DIAMONDS, alert=True, why="Waiting (2D after 2C)")


def _respond_to_weak_two(state, e: HandEval) -> Bid:
    op = state.opening_bid
    suit = op.suit
    hcp = e.hcp
    fit = e.suit_lengths.get(suit, 0)
    # 3-card raise pre-emptively (Law of Total Tricks)
    if fit >= 3 and hcp <= 12:
        return bid(3, suit, why="Furthering the preempt")
    # Solid game values + fit
    if fit >= 2 and hcp >= 16:
        return bid(4, suit, why="Game in major preempt")
    # 2NT inquiry (Ogust / feature) — convention-light, just use 2NT to ask.
    if hcp >= 14 and not e.is_balanced:
        return bid(2, Suit.NOTRUMP, alert=True, why="2NT inquiry (Ogust style)")
    if hcp >= 15 and e.is_balanced:
        return bid(3, Suit.NOTRUMP, why="3NT to play")
    return passb()


def _respond_to_preempt(state, e: HandEval) -> Bid:
    op = state.opening_bid
    suit = op.suit
    fit = e.suit_lengths.get(suit, 0)
    if fit >= 1 and e.hcp >= 16 and suit in (Suit.HEARTS, Suit.SPADES):
        return bid(4, suit, why="Game raise of preempt")
    if e.hcp >= 16 and e.is_balanced:
        return bid(3, Suit.NOTRUMP, why="3NT after preempt")
    return passb()


def _respond_to_minor(state, e: HandEval) -> Bid:
    op = state.opening_bid
    minor = op.suit
    hcp = e.hcp

    # 6-9 with a 4-card major bid 1H/1S
    if 6 <= hcp <= 18:
        if e.suit_lengths[Suit.HEARTS] >= 4 and e.suit_lengths[Suit.HEARTS] >= e.suit_lengths[Suit.SPADES]:
            return bid(1, Suit.HEARTS, why="4+ hearts, response to minor")
        if e.suit_lengths[Suit.SPADES] >= 4:
            return bid(1, Suit.SPADES, why="4+ spades, response to minor")

    # No 4cM
    if hcp <= 5:
        return passb()
    if 6 <= hcp <= 9:
        return bid(1, Suit.NOTRUMP, why="6-9 balanced, no 4cM, no minor fit")
    if 10 <= hcp <= 12:
        return bid(2, Suit.NOTRUMP, why="10-12 invitational")
    if 13 <= hcp <= 15:
        return bid(3, Suit.NOTRUMP, why="13-15 game values")
    if 16 <= hcp <= 17:
        # Jump shift / 2-level new suit
        if e.longest_suit not in (minor, Suit.NOTRUMP):
            return bid(2, e.longest_suit, why="Strong 2-over-1 forcing")
        return bid(3, Suit.NOTRUMP, why="To play")
    # 18+ slam-zone
    return bid(2, Suit.NOTRUMP, why="18+ HCP, exploring slam")


def _respond_to_minor_competitive(state, e: HandEval) -> Bid:
    """After 1m-(overcall): negative double with both unbid majors,
    new-suit 1H/1S still natural and forcing for one round."""
    overcall = state.rho_bids[-1]
    hcp = e.hcp
    overcall_suit = overcall.suit
    if overcall.is_double:
        # XX or new bid; default to redouble with 10+
        if hcp >= 10:
            return Bid(is_redouble=True, explanation="Redouble: 10+ HCP")
        return passb()
    if overcall_suit is None:  # NT overcall — treat as natural
        return _respond_to_minor(state, e)
    # Negative double with both unbid majors at 1- or 2-level
    can_neg_dbl = (overcall.level <= 2
                   and e.suit_lengths[Suit.HEARTS] >= 4
                   and e.suit_lengths[Suit.SPADES] >= 4
                   and hcp >= 6)
    if can_neg_dbl:
        return double(why="Negative double — both majors")
    # Bid an unbid major naturally
    for m in (Suit.HEARTS, Suit.SPADES):
        if m != overcall_suit and e.suit_lengths[m] >= 5:
            level = 1 if _BID_RANK[m] > _BID_RANK[overcall_suit] else 2
            return bid(level, m, why="Forcing bid in unbid major")
    if hcp >= 10 and _has_stopper(e, overcall_suit):
        return bid(2, Suit.NOTRUMP, why="2NT, 10-12, stopper in opp's suit")
    return passb()


def _respond_to_major(state, e: HandEval) -> Bid:
    op = state.opening_bid
    major = op.suit
    hcp = e.hcp
    fit = e.suit_lengths.get(major, 0)

    # 4+ support → raise structures
    if fit >= 4:
        # Splinter 3+1 or 4+0 with 13-15 game values
        for short in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
            if short == major:
                continue
            if e.suit_lengths[short] <= 1 and 13 <= hcp <= 15:
                # Splinter bid: jump in shortness suit
                level = 3 if _BID_RANK[short] > _BID_RANK[major] else 4
                return bid(level, short, alert=True,
                           why=f"Splinter raise: 4+ {major.to_char()}, "
                               f"shortness {short.to_char()}")
        # Jacoby 2NT: 4+ support, GF (13+ HCP)
        if hcp >= 13:
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Jacoby 2NT: 4+ support, GF")
        # Limit raise (3M): 10-12 with 4-card support
        if 10 <= hcp <= 12:
            return bid(3, major, why="Limit raise (10-12)")
        # Weak preemptive raise (4M with weak hand, lots of trumps)
        if hcp <= 9 and fit >= 5:
            return bid(4, major, why="Weak preemptive jump to game")
        # Simple raise
        if 6 <= hcp <= 9:
            return bid(2, major, why="Simple raise (6-9)")

    # 3-card support (or exactly 3-card raise)
    if fit == 3:
        if 6 <= hcp <= 9:
            return bid(2, major, why="3-card simple raise")
        if 10 <= hcp <= 12:
            return bid(3, major, why="3-card limit raise")
        # 13+ with 3-card support → 2/1 in a side suit, planning to support later

    # No fit → 1NT, 2/1, or 1S over 1H
    if major == Suit.HEARTS and e.suit_lengths[Suit.SPADES] >= 4 and 6 <= hcp <= 18:
        return bid(1, Suit.SPADES, why="1S response (4+ spades)")

    if hcp >= 13:
        # 2/1 game forcing
        for s in (Suit.CLUBS, Suit.DIAMONDS):
            if e.suit_lengths[s] >= 4 and (s != major):
                return bid(2, s, alert=True, why="2-over-1 game forcing")
        if major == Suit.SPADES and e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS, alert=True, why="2-over-1 GF")
        # Forcing 1NT not used in 2/1; jump to 3NT or 2NT GF
        if e.is_balanced:
            return bid(3, Suit.NOTRUMP, why="13-15 balanced, no fit")
        return bid(2, Suit.NOTRUMP, alert=True, why="Jacoby 2NT? No support — fallback")

    if 6 <= hcp <= 12:
        return bid(1, Suit.NOTRUMP, alert=True, why="1NT semi-forcing")

    return passb()


def _respond_to_major_competitive(state, e: HandEval) -> Bid:
    overcall = state.rho_bids[-1]
    hcp = e.hcp
    op_suit = state.opening_bid.suit
    other_major = Suit.SPADES if op_suit == Suit.HEARTS else Suit.HEARTS

    if overcall.is_double:
        if hcp >= 10:
            return Bid(is_redouble=True, explanation="Redouble (10+)")
        # Standard responses are still on
        return _respond_to_major(state, e)

    if overcall.suit is None or overcall.suit == Suit.NOTRUMP:
        return _respond_to_major(state, e)

    # Negative double showing the other major
    if hcp >= 6 and e.suit_lengths[other_major] >= 4 and overcall.level <= 2:
        return double(why=f"Negative double: 4+ {other_major.to_char()}")

    # Support partner with values — competitive raise
    fit = e.suit_lengths.get(op_suit, 0)
    if fit >= 3 and 6 <= hcp <= 9 and overcall.level <= 2:
        return bid(2, op_suit, why="Competitive raise")
    if fit >= 4 and hcp >= 10:
        return bid(3, op_suit, why="Limit raise (competitive)")

    if e.suit_lengths[other_major] >= 5 and hcp >= 10:
        # New suit at 2-level forcing
        return bid(2, other_major, alert=True, why="New suit forcing (competitive)")

    if hcp >= 10 and _has_stopper(e, overcall.suit):
        return bid(2, Suit.NOTRUMP, why="2NT, stopper, 10-12 HCP")

    return passb()


# ---------------------------------------------------------------------------
# Opener's rebid
# ---------------------------------------------------------------------------

def _opener_rebid(state, e: HandEval, system: str) -> Bid:
    if not state.partner_bids:
        # Partner passed — auction is dying. With a strong rebiddable hand,
        # might balance, but partner is silent ⇒ pass.
        return passb()

    p_last = state.partner_bids[-1]
    op = state.opening_bid

    # Stayman (1NT-2C)
    if op.level == 1 and op.suit == Suit.NOTRUMP and p_last.level == 2 and p_last.suit == Suit.CLUBS:
        if e.suit_lengths[Suit.HEARTS] == 4 and e.suit_lengths[Suit.SPADES] == 4:
            # Bid up the line — hearts first
            return bid(2, Suit.HEARTS, why="Stayman: 4 hearts (and 4 spades available)")
        if e.suit_lengths[Suit.HEARTS] == 4:
            return bid(2, Suit.HEARTS, why="Stayman: 4 hearts")
        if e.suit_lengths[Suit.SPADES] == 4:
            return bid(2, Suit.SPADES, why="Stayman: 4 spades")
        return bid(2, Suit.DIAMONDS, alert=True, why="Stayman: no 4cM")

    # Jacoby transfer accept
    if op.level == 1 and op.suit == Suit.NOTRUMP and p_last.level == 2:
        if p_last.suit == Suit.DIAMONDS:
            # Super-accept with maximum + 4-card hearts
            if e.hcp == 17 and e.suit_lengths[Suit.HEARTS] >= 4:
                return bid(3, Suit.HEARTS, alert=True, why="Super-accept (max + 4 hearts)")
            return bid(2, Suit.HEARTS, why="Accept transfer to hearts")
        if p_last.suit == Suit.HEARTS:
            if e.hcp == 17 and e.suit_lengths[Suit.SPADES] >= 4:
                return bid(3, Suit.SPADES, alert=True, why="Super-accept (max + 4 spades)")
            return bid(2, Suit.SPADES, why="Accept transfer to spades")

    # Smolen: 1NT-2C-2D-3M shows 5 cards in the OTHER major
    if op.level == 1 and op.suit == Suit.NOTRUMP:
        if (len(state.partner_bids) >= 2
                and state.partner_bids[0].level == 2
                and state.partner_bids[0].suit == Suit.CLUBS
                and p_last.level == 3
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)):
            shown_major = p_last.suit
            other_major = Suit.SPADES if shown_major == Suit.HEARTS else Suit.HEARTS
            # Partner has 5+ in OTHER major. Pick the fit.
            if e.suit_lengths[other_major] >= 3:
                return bid(4, other_major, why=f"Smolen accept: 3+ {other_major.to_char()}")
            return bid(3, Suit.NOTRUMP, why="Smolen no fit")

    # 1m / 1M opening — opener's rebid by partner's response
    if op.level == 1 and op.suit != Suit.NOTRUMP:
        return _opener_suit_rebid(state, e, op, p_last, system)

    # Strong 2C openings: rebid in the longest natural suit at the 2-level
    if op.level == 2 and op.suit == Suit.CLUBS and op.alert:
        if e.suit_lengths[Suit.SPADES] >= 5:
            return bid(2, Suit.SPADES, why="Natural rebid 2S (5+ spades)")
        if e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS, why="Natural rebid 2H (5+ hearts)")
        if e.is_balanced and 22 <= e.hcp <= 24:
            return bid(2, Suit.NOTRUMP, why="22-24 balanced rebid")
        return bid(3, Suit.NOTRUMP, why="25+ balanced rebid")

    return passb()


def _opener_suit_rebid(state, e, op, p_last, system) -> Bid:
    op_suit = op.suit

    # Partner raised our suit
    if p_last.suit == op_suit:
        if p_last.level == 2:
            # Simple raise → 6-9. Pass with min, invite with 17, jump with 18+.
            if e.hcp <= 14:
                return passb()
            if 15 <= e.hcp <= 17:
                return bid(3, op_suit, why="Game try (15-17)")
            return bid(4, op_suit, why="To-play game (18+)")
        if p_last.level == 3:  # limit raise
            if e.hcp <= 13:
                return passb()
            return bid(4, op_suit, why="Accept limit raise")
        if p_last.level == 4:  # weak preemptive
            return passb()

    # Partner's 1NT response (6-9 / 6-12 if 1M opening)
    if p_last.level == 1 and p_last.suit == Suit.NOTRUMP:
        if e.is_balanced and 12 <= e.hcp <= 14:
            return passb()
        if e.is_balanced and 15 <= e.hcp <= 17:
            return bid(2, Suit.NOTRUMP, why="15-17 NT rebid")
        if e.is_balanced and e.hcp >= 18:
            return bid(3, Suit.NOTRUMP, why="18-19 NT rebid")
        # Show second suit if 5-4 or longer (lower-ranked, no reverse)
        if e.second_suit and _BID_RANK[e.second_suit] < _BID_RANK[op_suit]:
            return bid(2, e.second_suit, why="Second suit (lower)")
        # Rebid 6-card original suit
        if e.suit_lengths[op_suit] >= 6:
            return bid(2, op_suit, why="Rebid 6-card suit")
        return passb()

    # Partner's new-suit at the 1-level (one-over-one)
    if (p_last.level == 1 and p_last.suit is not None
            and p_last.suit != Suit.NOTRUMP and p_last.suit != op_suit):
        # Support partner with 4+ in their major at the cheapest level
        if p_last.suit in (Suit.HEARTS, Suit.SPADES) and e.suit_lengths[p_last.suit] >= 4:
            if e.hcp <= 14:
                return bid(2, p_last.suit, why="Simple raise of partner's major")
            if e.hcp <= 18:
                return bid(3, p_last.suit, why="Game try / strong raise")
            return bid(4, p_last.suit, why="Game raise (19+ HCP)")
        # Rebid 6-card opener suit
        if e.suit_lengths[op_suit] >= 6:
            return bid(2, op_suit, why="Rebid 6-card suit")
        # Bid second suit
        if e.second_suit:
            target = e.second_suit
            # Reverse check: a higher-ranked second suit at the 2-level
            # promises 17+ HCP; otherwise show a lower-ranked second suit.
            if _BID_RANK[target] > _BID_RANK[op_suit] and e.hcp >= 17:
                return bid(2, target, why="Reverse (17+ HCP)")
            if _BID_RANK[target] < _BID_RANK[op_suit]:
                return bid(2, target, why="Second suit")
        # Rebid NT
        if e.is_balanced:
            if 12 <= e.hcp <= 14:
                return bid(1, Suit.NOTRUMP, why="12-14 balanced")
            if 15 <= e.hcp <= 17:
                return bid(1, Suit.NOTRUMP, why="15-17 not strong enough for 2NT?")
        return passb()

    # Partner's Jacoby 2NT (1M-2NT)
    if op_suit in (Suit.HEARTS, Suit.SPADES) and p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
        # Show shortness if any (split among singletons/voids in side suits)
        for short in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
            if short == op_suit:
                continue
            if e.suit_lengths[short] <= 1:
                return bid(3, short, alert=True, why="Jacoby 2NT: shortness")
        # Show extras — 3M = minimum, 3NT = 18-19 balanced extras, 4M = sign off
        if e.hcp >= 18:
            return bid(3, Suit.NOTRUMP, why="J2NT: 18+ extras, balanced")
        if e.hcp >= 16:
            return bid(3, op_suit, why="J2NT: 16-17 extras, no shortness")
        return bid(4, op_suit, why="J2NT: minimum, no shortness")

    # Partner splinter — accept slam interest based on losers
    if (p_last.alert and p_last.level >= 3
            and p_last.suit is not None and p_last.suit != op_suit):
        if e.losers <= 5 and e.controls >= 4:
            return bid(4, Suit.NOTRUMP, alert=True, why="RKC after splinter")
        return bid(4, op_suit, why="Sign off after splinter")

    # Partner 2-over-1 GF
    if p_last.level == 2 and p_last.suit is not None and p_last.suit != Suit.NOTRUMP:
        # Rebid 6-card original suit
        if e.suit_lengths[op_suit] >= 6:
            return bid(2, op_suit, why="6-card opener suit rebid")
        # Show second suit
        if e.second_suit and _BID_RANK[e.second_suit] < _BID_RANK[op_suit]:
            return bid(2, e.second_suit, why="Second suit")
        # Balanced rebid 2NT (forcing in 2/1 context)
        if e.is_balanced:
            return bid(2, Suit.NOTRUMP, why="2NT (balanced rebid in 2/1)")
        # Reverse / jump shift on stronger hands
        if (e.second_suit and _BID_RANK[e.second_suit] > _BID_RANK[op_suit]
                and e.hcp >= 17):
            return bid(2, e.second_suit, why="Reverse (17+ HCP, 2/1 context)")
        return bid(3, op_suit, why="Rebid (constructive)")

    return passb()


# ---------------------------------------------------------------------------
# Responder's rebid
# ---------------------------------------------------------------------------

def _responder_rebid(state, e: HandEval, system: str) -> Bid:
    if not state.partner_bids or len(state.partner_bids) < 2:
        # Opener has only made one bid — we should still be in our first
        # response, but the auction state suggests we made more than one bid.
        return passb()

    op = state.opening_bid
    p_last = state.partner_bids[-1]

    # 1NT-2C-(opener's response): if Stayman is in flight, handle specially
    if op.suit == Suit.NOTRUMP and op.level == 1 and len(state.my_bids) >= 1:
        my_first = state.my_bids[0]
        if my_first.level == 2 and my_first.suit == Suit.CLUBS:
            # Stayman: opener rebid 2D/2H/2S
            return _stayman_responder_rebid(state, e, p_last)

    # If partner showed extras, drive to game; if min, settle
    return _generic_responder_rebid(state, e, p_last)


def _stayman_responder_rebid(state, e, opener_rebid: Bid) -> Bid:
    hcp = e.hcp
    # Opener bid 2D — no major, fall back to NT
    if opener_rebid.suit == Suit.DIAMONDS:
        if hcp <= 7:
            return passb(why="Stayman, no fit, weak — pass 2D? actually 2D is artificial")
        # Smolen-eligible: 5-4 in majors with GF values
        if hcp >= 10 and e.suit_lengths[Suit.SPADES] >= 5 and e.suit_lengths[Suit.HEARTS] == 4:
            return bid(3, Suit.HEARTS, alert=True, why="Smolen: shows 5 spades, 4 hearts")
        if hcp >= 10 and e.suit_lengths[Suit.HEARTS] >= 5 and e.suit_lengths[Suit.SPADES] == 4:
            return bid(3, Suit.SPADES, alert=True, why="Smolen: shows 5 hearts, 4 spades")
        if 8 <= hcp <= 9:
            return bid(2, Suit.NOTRUMP, why="Invitational")
        if hcp >= 10:
            return bid(3, Suit.NOTRUMP, why="To-play game")
        return passb()
    # Opener bid 2H or 2S — major fit?
    if opener_rebid.suit in (Suit.HEARTS, Suit.SPADES):
        major = opener_rebid.suit
        fit = e.suit_lengths.get(major, 0)
        if fit >= 4:
            if hcp >= 10:
                return bid(4, major, why="Game in major fit")
            if 8 <= hcp <= 9:
                return bid(3, major, why="Invitational major raise")
            return bid(2, major, why="Sign off")  # very rare
        # No 4-card fit — push to NT
        if hcp >= 10:
            return bid(3, Suit.NOTRUMP, why="No fit, game values")
        if 8 <= hcp <= 9:
            return bid(2, Suit.NOTRUMP, why="No fit, invitational")
        return passb()
    return passb()


def _generic_responder_rebid(state, e, opener_rebid):
    hcp = e.hcp
    op = state.opening_bid

    # Opener rebid 1NT (12-14)
    if opener_rebid.level == 1 and opener_rebid.suit == Suit.NOTRUMP:
        if hcp <= 7:
            return passb()
        if 8 <= hcp <= 10 and e.suit_lengths.get(op.suit, 0) >= 5:
            return bid(2, op.suit, why="6-9 rebid in opener's suit (NMF substitute)")
        if 8 <= hcp <= 10:
            return bid(2, Suit.NOTRUMP, why="Invitational raise")
        if hcp >= 11:
            return bid(3, Suit.NOTRUMP, why="Game values")
        return passb()

    # Opener jumped to 2NT / 3NT — pass or escalate
    if opener_rebid.level >= 2 and opener_rebid.suit == Suit.NOTRUMP:
        if hcp >= 8:
            return bid(3, Suit.NOTRUMP, why="To-play")
        return passb()

    # Opener raised our suit
    if (opener_rebid.suit is not None and state.suit_bid_by_me
            and opener_rebid.suit == state.suit_bid_by_me[-1]):
        major = opener_rebid.suit
        if opener_rebid.level == 2 and hcp >= 10 and e.suit_lengths.get(major, 0) >= 4:
            return bid(4, major, why="Game raise after partner's support")
        return passb()

    return passb()


# ---------------------------------------------------------------------------
# Competitive bidding (overcalls / advancers)
# ---------------------------------------------------------------------------

def _overcall(state, e: HandEval, system: str) -> Bid:
    op = state.opening_bid
    hcp = e.hcp

    if not (op.level == 1 and op.suit is not None and op.suit != Suit.NOTRUMP):
        return passb()

    # ---- Conventional shape-bids run BEFORE natural overcalls so they're
    # not pre-empted by the suit-overcall path. ----

    # Michaels cuebid: 5-5 in two suits, 8-16 HCP.
    if op.suit in (Suit.CLUBS, Suit.DIAMONDS):
        # Over a minor → both majors
        if (e.suit_lengths[Suit.HEARTS] >= 5
                and e.suit_lengths[Suit.SPADES] >= 5
                and 8 <= hcp <= 16):
            return bid(2, op.suit, alert=True, why="Michaels: 5-5 majors")
    if op.suit in (Suit.HEARTS, Suit.SPADES):
        # Over a major → other major + an unspecified minor (5-5)
        other_major = Suit.SPADES if op.suit == Suit.HEARTS else Suit.HEARTS
        if e.suit_lengths[other_major] >= 5 and 8 <= hcp <= 16:
            for m in (Suit.CLUBS, Suit.DIAMONDS):
                if e.suit_lengths[m] >= 5:
                    return bid(2, op.suit, alert=True,
                               why="Michaels: other major + minor (5-5)")

    # Unusual 2NT: 5-5 in the two lowest-ranked unbid suits, 8-16 HCP.
    unbid = [s for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
             if s != op.suit]
    unbid_sorted = sorted(unbid, key=lambda s: _BID_RANK[s])
    if (8 <= hcp <= 16
            and e.suit_lengths[unbid_sorted[0]] >= 5
            and e.suit_lengths[unbid_sorted[1]] >= 5):
        return bid(2, Suit.NOTRUMP, alert=True,
                   why="Unusual 2NT: 5-5, two lower unbid suits")

    # 1NT overcall: 15-18 balanced with a stopper in opener's suit.
    if 15 <= hcp <= 18 and e.is_balanced and _has_stopper(e, op.suit):
        return bid(1, Suit.NOTRUMP, why="1NT overcall: 15-18, stopper")

    # Suit overcall (preferred over takeout double when we have a real suit
    # at least 5 cards long with adequate strength).
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if s == op.suit:
            continue
        if e.suit_lengths[s] >= 5 and 8 <= hcp <= 16 and e.suit_hcp[s] >= 4:
            level = 1 if _BID_RANK[s] > _BID_RANK[op.suit] else 2
            return bid(level, s, why=f"{level}{s.to_char()} natural overcall")

    # Takeout double — shortness in opener's suit + tolerance for unbid suits.
    if hcp >= 12 and e.suit_lengths[op.suit] <= 2:
        if all(e.suit_lengths[s] >= 3 for s in unbid):
            return double(why="Takeout double")

    # Weak jump overcall: 6-card suit, 6-10 HCP.
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if s == op.suit:
            continue
        if e.suit_lengths[s] >= 6 and 6 <= hcp <= 10:
            level = 2 if _BID_RANK[s] > _BID_RANK[op.suit] else 3
            return bid(level, s, why="Weak jump overcall")

    return passb()


def _advance_partner_overcall(state, e: HandEval, system: str) -> Bid:
    p_last = state.partner_bids[-1]
    hcp = e.hcp

    # Takeout double advancer: bid the cheapest suit / NT
    if p_last.is_double:
        # 8-10 with 4-card major → bid it at minimum level
        for m in (Suit.SPADES, Suit.HEARTS):
            if e.suit_lengths[m] >= 4:
                # Determine the cheapest available level
                lvl = max(1, state.last_level)
                if (state.last_suit_bid
                        and _BID_RANK[m] <= _BID_RANK[state.last_suit_bid]):
                    lvl += 1
                return bid(lvl, m, why="Advance takeout double: 4-card major")
        # 8-10 balanced with stopper → 1NT
        if hcp >= 8 and _has_stopper(e, state.opening_bid.suit) and e.is_balanced:
            return bid(1, Suit.NOTRUMP, why="Advance takeout dbl: 1NT (stopper)")
        # Cuebid with 11+ to show game interest
        if hcp >= 11:
            return bid(2, state.opening_bid.suit, alert=True,
                       why="Cuebid: game interest after takeout double")
        # Last resort: longest minor
        for m in (Suit.DIAMONDS, Suit.CLUBS):
            if e.suit_lengths[m] >= 4:
                lvl = state.last_level + 1
                return bid(lvl, m, why="Advance takeout double: minor")
        return passb()

    # Suit overcall — raise with support, otherwise pass / new suit
    if p_last.suit is not None and p_last.suit != Suit.NOTRUMP:
        suit = p_last.suit
        fit = e.suit_lengths.get(suit, 0)
        if fit >= 3:
            if 6 <= hcp <= 10:
                return bid(p_last.level + 1, suit, why="Simple raise of overcall")
            if 11 <= hcp <= 12:
                return bid(p_last.level + 2, suit, why="Limit raise of overcall")
            if hcp >= 13 and suit in (Suit.HEARTS, Suit.SPADES):
                return bid(4, suit, why="Game raise of major overcall")

    return passb()


# ---------------------------------------------------------------------------
# Public engine class
# ---------------------------------------------------------------------------

class NativeBiddingEngine:
    """Plug-compatible with BridgeEngine for bidding only.

    Construct it once, then call get_bid(board, seat) per turn.
    """

    def __init__(self, system: str = "SAYC"):
        self.system = system if system in ("SAYC", "Precision") else "SAYC"

    def set_system(self, system: str):
        if system in ("SAYC", "Precision"):
            self.system = system

    # The following stubs match BridgeEngine's lifecycle so the caller can
    # treat both engines uniformly.
    @property
    def is_ready(self) -> bool:
        return True

    def initialize(self):
        return True

    def shutdown(self):
        pass

    def get_bid(self, board: BoardState, seat: Seat):
        """Return an EngineResponse-shaped object for compatibility."""
        # Imported lazily so this module has no hard dependency on BEN.
        from .engine import EngineResponse, BidCandidate

        try:
            hand = board.hands.get(seat)
            if hand is None or not hand.cards:
                return EngineResponse(action=Bid.make_pass(), who="NoHand")

            eval_ = evaluate_hand(hand)
            state = parse_auction(seat=seat, dealer=board.dealer, auction=board.auction)
            chosen = decide_bid(state, eval_, system=self.system)

            return EngineResponse(
                action=chosen,
                candidates=[BidCandidate(bid=chosen, score=1.0, explanation=chosen.explanation)],
                quality=0.6,  # Rule-based, not probabilistic
                who=f"Native ({self.system})",
                hcp_estimate=None,
                shape_estimate=None,
            )
        except Exception as ex:
            return EngineResponse(action=Bid.make_pass(), who=f"NativeError: {ex}")
