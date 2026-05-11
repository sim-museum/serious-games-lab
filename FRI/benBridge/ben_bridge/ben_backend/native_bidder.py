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

def open_bid(eval_: HandEval, system=None) -> Bid:
    """Pick an opening bid (or Pass) given the hand.

    `system` is now a `BiddingSystem` from `bidding_systems`. Legacy
    callers passing the string "Precision" / "SAYC" still work — the
    string is looked up via `get_system`. Dispatch routes by
    `strong_open_call`: "1C" → Precision-family open, otherwise SAYC.
    """
    from .bidding_systems import BiddingSystem, get_system
    if system is None:
        system = get_system("SAYC")
    elif not isinstance(system, BiddingSystem):
        system = get_system(system)
    if system.strong_open_call == "1C":
        return _open_precision(eval_, system)
    return _open_sayc(eval_, system)


def _open_sayc(e: HandEval, system) -> Bid:
    hcp = e.hcp
    nt_min, nt_max = system.one_nt_min_hcp, system.one_nt_max_hcp
    two_nt_min, two_nt_max = system.two_nt_min_hcp, system.two_nt_max_hcp
    strong_min = system.strong_open_min_hcp  # 22 in SAYC

    # Strong artificial 2♣: either 22+ HCP regardless of shape, or an
    # unbalanced hand with strong playing strength (9+ quick tricks /
    # 4+ controls). The unbalanced gate is important — a 17-HCP 4-3-4-2
    # hand has 4 controls and 4 quick tricks but is plainly a 1NT opener.
    is_strong_unbal = (
        hcp >= strong_min - 2
        and e.controls >= 5
        and e.quick_tricks >= 5
        and not (e.is_balanced or e.is_semi_balanced)
    )
    if hcp >= strong_min or is_strong_unbal:
        return bid(2, Suit.CLUBS, alert=True,
                   why=f"Strong, artificial, GF unless 2C-2D-2NT ({strong_min}+ HCP)")

    # Notrump openings (balanced)
    if e.is_balanced or e.is_semi_balanced:
        if nt_min <= hcp <= nt_max:
            return bid(1, Suit.NOTRUMP, why=f"{nt_min}-{nt_max} balanced")
        if two_nt_min <= hcp <= two_nt_max:
            return bid(2, Suit.NOTRUMP, why=f"{two_nt_min}-{two_nt_max} balanced")
        # Gambling 3NT: solid 7+ minor, ~25-27 HCP equivalent (system-dependent).
        if 25 <= hcp <= 27:
            return bid(3, Suit.NOTRUMP, why="25-27 balanced")
        # Below 1NT-range balanced → open 1 of a minor; above 2NT-range and
        # under 22 → open 1 of a suit then jump in NT. Fall through.

    # Sub-opening hands → Pass (or skip preempts handled below)
    if hcp < 12 and not _has_preempt(e):
        # Gambling 3NT can come from a sub-opening hand (~10 HCP solid minor).
        gamb = _gambling_3nt_open(e, system)
        if gamb is not None:
            return gamb
        return passb(why="Insufficient values")

    # Gambling 3NT (when the system enables it)
    gamb = _gambling_3nt_open(e, system)
    if gamb is not None:
        return gamb

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


def _open_precision(e: HandEval, system) -> Bid:
    """Precision openings, parameterised by the spec.

    `strong_open_min_hcp` is the strong 1♣ threshold (Q-Plus says 16 for
    Precision Club 90 modern / plus and Precision 70). `one_nt_min_hcp`
    / `one_nt_max_hcp` cover the limited 1NT (typically 14-16, or 13-15
    in Precision 70). `precision_two_clubs_*` covers the 2♣ long-club
    opening range. The 2♦ three-suiter is governed by the
    `precision_two_diamonds_shape` flag.
    """
    hcp = e.hcp
    strong_min = system.strong_open_min_hcp
    nt_min, nt_max = system.one_nt_min_hcp, system.one_nt_max_hcp
    two_nt_min, two_nt_max = system.two_nt_min_hcp, system.two_nt_max_hcp
    two_c_min = system.precision_two_clubs_min_hcp
    two_c_max = system.precision_two_clubs_max_hcp
    one_d_min = system.one_diamond_min_hcp
    one_d_max = system.one_diamond_max_hcp

    # Strong artificial 1C — any shape.
    if hcp >= strong_min:
        return bid(1, Suit.CLUBS, alert=True,
                   why=f"Precision: {strong_min}+ HCP, any shape")

    # Below the lower opening bound → Pass (preempts considered first).
    if hcp < two_c_min:
        gamb = _gambling_3nt_open(e, system)
        if gamb is not None:
            return gamb
        pre = _preempt_bid(e)
        if pre is not None:
            return pre
        return passb()

    # Gambling 3NT also applies inside the opening range — Precision 70
    # uses it for solid-minor hands light on HCP.
    gamb = _gambling_3nt_open(e, system)
    if gamb is not None:
        return gamb

    # Limited 1NT (Q-Plus Precision: 14-16, or 13-15 for the classic 70).
    if nt_min <= hcp <= nt_max and (e.is_balanced or e.is_semi_balanced):
        return bid(1, Suit.NOTRUMP, alert=True,
                   why=f"Precision: {nt_min}-{nt_max} balanced")

    # 2NT — strong balanced not covered by 1NT (rare in Precision).
    if two_nt_min <= hcp <= two_nt_max and (e.is_balanced or e.is_semi_balanced):
        return bid(2, Suit.NOTRUMP,
                   why=f"{two_nt_min}-{two_nt_max} balanced")

    # 5-card majors at the 1 level (light to mid).
    if e.suit_lengths[Suit.SPADES] >= 5 and e.suit_lengths[Suit.SPADES] >= e.suit_lengths[Suit.HEARTS]:
        return bid(1, Suit.SPADES, alert=True,
                   why=f"Precision: {two_c_min}-{nt_max} HCP, 5+ spades")
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(1, Suit.HEARTS, alert=True,
                   why=f"Precision: {two_c_min}-{nt_max} HCP, 5+ hearts")

    # 2♣ long-club (Precision-specific): 6+ clubs in the limited range.
    if e.suit_lengths[Suit.CLUBS] >= 6 and two_c_min <= hcp <= two_c_max:
        return bid(2, Suit.CLUBS, alert=True,
                   why=f"Precision: {two_c_min}-{two_c_max}, 6+ clubs")

    # 1♦ — catch-all 11-15 / no 5cM / no 6c clubs / unbalanced or 2c+ diamond.
    if one_d_min <= hcp <= one_d_max and (
            e.suit_lengths[Suit.DIAMONDS] >= 2 or not (e.is_balanced or e.is_semi_balanced)):
        return bid(1, Suit.DIAMONDS, alert=True,
                   why=f"Precision: {one_d_min}-{one_d_max} HCP, "
                       "no 5cM, no 6c clubs")
    return passb()


def _gambling_3nt_open(e: HandEval, system) -> Optional[Bid]:
    """Gambling 3NT: a solid 7+ minor with little outside (≤ ~10 HCP).

    Q-Plus enables this under `A-3NT-transfer` (SAYC's odd naming for
    Gambling) and `B-3NT.gambling` / `B-3NT.minor-preempt` (Precision
    flavours). Returns the 3NT bid if the hand qualifies, else None.
    """
    if not (system.has("A-3NT-transfer")
            or system.has("B-3NT.gambling")
            or system.has("B-3NT.minor-preempt")):
        return None
    if e.hcp > 11:
        return None
    # Solid 7+ minor: AKQ headed (sufficient by SAYC), 7+ cards.
    for minor in (Suit.CLUBS, Suit.DIAMONDS):
        if e.suit_lengths[minor] >= 7:
            # Require the suit to actually be solid — top three honors.
            suit_hcp = e.suit_hcp[minor]
            if suit_hcp >= 4 + 3 + 2:  # AKQ (or better)
                return bid(3, Suit.NOTRUMP, alert=True,
                           why=f"Gambling 3NT: solid 7+ {minor.to_char()}")
    return None


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

def decide_bid(state: AuctionState, eval_: HandEval, system) -> Bid:
    """Dispatch to the right decision function based on auction state.

    `system` is a `BiddingSystem` from `bidding_systems`. String inputs
    are accepted for backwards compatibility (resolved via `get_system`).
    """
    from .bidding_systems import BiddingSystem, get_system
    if not isinstance(system, BiddingSystem):
        system = get_system(system)
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
    rho_intervened = bool(state.rho_bids)

    # Precision-specific paths take precedence: 1C is strong artificial,
    # 2C is natural clubs (11-15), 1D is the catch-all 11-15.
    if getattr(system, "strong_open_call", "2C") == "1C":
        if op.level == 1 and op.suit == Suit.CLUBS:
            return _respond_to_precision_1c(state, e)
        if op.level == 2 and op.suit == Suit.CLUBS:
            return _respond_to_precision_2c(state, e)
        if op.level == 1 and op.suit == Suit.DIAMONDS:
            if rho_intervened:
                return _respond_to_minor_competitive(state, e, system)
            return _respond_to_precision_1d(state, e)
        # 1NT (14-16), 1H/1S (11-15 5+suit), 2D (weak), preempts —
        # responses mirror SAYC; 1NT range is just slightly lower.

    # 1NT openings — Stayman, transfers, etc. (regardless of intervention,
    # but only the simple non-comp version here). Lebensohl handles 1NT-(2X).
    if op.level == 1 and op.suit == Suit.NOTRUMP:
        if rho_intervened:
            return _respond_to_1nt_competitive(state, e, system)
        return _respond_to_1nt(e, system)

    if op.level == 2 and op.suit == Suit.NOTRUMP:
        return _respond_to_2nt(e, system)

    # Strong 2C in SAYC (Precision was handled above so we won't reach here
    # for Precision 2C).
    if op.level == 2 and op.suit == Suit.CLUBS:
        return _respond_to_strong_2c(e)

    # Weak two openings
    if op.level == 2 and op.suit in (Suit.HEARTS, Suit.SPADES, Suit.DIAMONDS):
        return _respond_to_weak_two(state, e, system)

    # 3+ level preempts → mostly pass; raise to game with shape & values
    if op.level >= 3 and op.suit is not None and op.suit != Suit.NOTRUMP:
        return _respond_to_preempt(state, e)

    # 1-of-a-suit openings
    if op.level == 1 and op.suit in (Suit.CLUBS, Suit.DIAMONDS):
        if rho_intervened:
            return _respond_to_minor_competitive(state, e, system)
        return _respond_to_minor(state, e, system)

    if op.level == 1 and op.suit in (Suit.HEARTS, Suit.SPADES):
        if rho_intervened:
            return _respond_to_major_competitive(state, e, system)
        return _respond_to_major(state, e, system)

    return passb()


# ---------------------------------------------------------------------------
# Precision: response to 1C (strong, 16+ HCP, artificial)
# ---------------------------------------------------------------------------

def _respond_to_precision_1c(state, e: HandEval) -> Bid:
    """Standard simple Precision response to 1C:
        1D  = 0-7 HCP (negative, catch-all)
        1H  = 8+ HCP, 5+ hearts
        1S  = 8+ HCP, 5+ spades
        1NT = 8-13 HCP balanced, no 5-card major
        2C  = 8+ HCP, 5+ clubs (positive)
        2D  = 8+ HCP, 5+ diamonds (positive)
        2NT = 14-16 HCP balanced (slam invite)
        3NT = 17+ HCP balanced
    """
    hcp = e.hcp
    if hcp <= 7:
        return bid(1, Suit.DIAMONDS, alert=True,
                   why="Precision: 0-7 HCP negative response to 1C")

    # 14+ HCP balanced → quantitative game/slam invite
    if hcp >= 17 and e.is_balanced:
        return bid(3, Suit.NOTRUMP, alert=True,
                   why="Precision: 17+ HCP balanced, slam-going")
    if 14 <= hcp <= 16 and e.is_balanced:
        return bid(2, Suit.NOTRUMP, alert=True,
                   why="Precision: 14-16 HCP balanced")

    # 5-card major positive
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(1, Suit.HEARTS, alert=True,
                   why="Precision: 8+ HCP, 5+ hearts")
    if e.suit_lengths[Suit.SPADES] >= 5:
        return bid(1, Suit.SPADES, alert=True,
                   why="Precision: 8+ HCP, 5+ spades")

    # 5+ minor positive
    if e.suit_lengths[Suit.DIAMONDS] >= 5:
        return bid(2, Suit.DIAMONDS, alert=True,
                   why="Precision: 8+ HCP, 5+ diamonds")
    if e.suit_lengths[Suit.CLUBS] >= 5:
        return bid(2, Suit.CLUBS, alert=True,
                   why="Precision: 8+ HCP, 5+ clubs")

    # Balanced / semi-balanced 8-13 → 1NT
    return bid(1, Suit.NOTRUMP, alert=True,
               why="Precision: 8-13 HCP balanced, no 5-card suit")


# ---------------------------------------------------------------------------
# Precision: response to 1D (11-15 HCP, no 5-card major, < 6 clubs)
# ---------------------------------------------------------------------------

def _respond_to_precision_1d(state, e: HandEval) -> Bid:
    """Responses to a Precision 1D opening (similar to a SAYC 1m response,
    but the diamond opening doesn't promise a particular length so we
    treat it as a catch-all 11-15 limited opening):
        Pass = 0-5 HCP junk
        1H/1S = 6+ HCP, 4+ in suit (forcing 1 round)
        1NT  = 6-10 balanced no 4-card major
        2D   = 6-10, 4+ diamonds (raise)
        2C/2H/2S (new suit at 2-level) = 11+ GF
        2NT  = 11-12 invitational, no 4cM
        3D   = limit raise (10-12, 5+ diamonds)
        3NT  = 13-15 balanced to play
    """
    hcp = e.hcp

    if hcp <= 5:
        return passb(why="Precision 1D: insufficient values")

    # 6-9 with a 4-card major: bid the major up the line
    if 6 <= hcp <= 18:
        if e.suit_lengths[Suit.HEARTS] >= 4 and e.suit_lengths[Suit.HEARTS] >= e.suit_lengths[Suit.SPADES]:
            return bid(1, Suit.HEARTS, why="Precision 1D: 4+ hearts, 6+ HCP")
        if e.suit_lengths[Suit.SPADES] >= 4:
            return bid(1, Suit.SPADES, why="Precision 1D: 4+ spades, 6+ HCP")

    # No 4cM
    if 6 <= hcp <= 10:
        if e.suit_lengths[Suit.DIAMONDS] >= 4:
            return bid(2, Suit.DIAMONDS, why="Precision 1D: 6-10 raise (4+ diamonds)")
        return bid(1, Suit.NOTRUMP, why="Precision 1D: 6-10 balanced")
    if 11 <= hcp <= 12:
        return bid(2, Suit.NOTRUMP, why="Precision 1D: 11-12 invitational")
    if 13 <= hcp <= 15:
        if e.suit_lengths[Suit.DIAMONDS] >= 4:
            return bid(3, Suit.DIAMONDS, why="Precision 1D: 13-15 with diamond fit")
        return bid(3, Suit.NOTRUMP, why="Precision 1D: 13-15 balanced game")

    # 16+ slam-zone with no major fit
    return bid(2, Suit.NOTRUMP, why="Precision 1D: 16+ HCP, exploring slam")


# ---------------------------------------------------------------------------
# Precision: response to 2C (11-15 HCP, 6+ clubs)
# ---------------------------------------------------------------------------

def _respond_to_precision_2c(state, e: HandEval) -> Bid:
    """Responses to a Precision 2C opening:
        Pass = 0-7 HCP no fit
        2D   = inquiry (asks opener for shape / 4-card major)
        2H/2S = natural 5+ in suit, 8+ HCP, forcing 1 round
        2NT  = inquiry (alternative — kept simple: just shape)
        3C   = preemptive raise (6-9, 3+ clubs)
        3NT  = to-play (13+ balanced with stopper-equivalent)
    """
    hcp = e.hcp
    if hcp <= 7 and e.suit_lengths[Suit.CLUBS] < 3:
        return passb(why="Precision 2C: insufficient values, no fit")

    # 5-card major with values → bid naturally
    if hcp >= 8 and e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(2, Suit.HEARTS, why="Precision 2C: natural 5+ hearts")
    if hcp >= 8 and e.suit_lengths[Suit.SPADES] >= 5:
        return bid(2, Suit.SPADES, why="Precision 2C: natural 5+ spades")

    # GF inquiry with 13+ balanced (asks opener for shape)
    if hcp >= 13 and e.is_balanced:
        return bid(2, Suit.DIAMONDS, alert=True,
                   why="Precision 2C-2D: GF inquiry asking for shape / 4cM")

    # Preemptive club raise
    if 6 <= hcp <= 9 and e.suit_lengths[Suit.CLUBS] >= 3:
        return bid(3, Suit.CLUBS, why="Precision 2C: preemptive club raise")

    # Invitational raise
    if 10 <= hcp <= 12 and e.suit_lengths[Suit.CLUBS] >= 3:
        return bid(2, Suit.NOTRUMP, why="Precision 2C: invitational, no major")

    # Game-going balanced
    if hcp >= 13 and e.is_balanced:
        return bid(3, Suit.NOTRUMP, why="Precision 2C: game in NT")

    return passb(why="Precision 2C: no clear action")


def _negative_double_max_level(system) -> int:
    """Q-Plus encodes the negative-double cap in the flag name itself:
    `C-Sputnik.until-2S` (SAYC) → through level 2, `C-Sputnik.until-3S`
    (Precision 90 modern) → through level 3. Anything else falls back
    to the safe SAYC default of 2.
    """
    for k in system.raw_rules:
        if k.startswith("C-Sputnik.until-"):
            tail = k[len("C-Sputnik.until-"):]
            if tail and tail[0].isdigit():
                try:
                    return int(tail[0])
                except ValueError:
                    pass
    # System came from the fallback path (no raw_rules) — assume 2.
    return 2


def _nt_response_thresholds(system) -> dict:
    """Return responder's HCP thresholds vs the opener's 1NT range.

    Standard SAYC has 1NT = 15-17 with classic thresholds:
        pass ≤ 7, invite 8-9, game 10-14, quant 15-16, slam 17+.

    For a 14-16 NT (Precision Club 90) or 13-15 NT (Precision Club 70)
    each threshold drifts up by the offset `17 − nt_max`, so responder
    always needs the same total points to reach game / slam.
    """
    nt_max = system.one_nt_max_hcp
    offset = max(0, 17 - nt_max)
    return {
        "pass_max":  7 + offset,
        "invite_lo": 8 + offset,
        "invite_hi": 9 + offset,
        "game_lo":  10 + offset,
        "quant_lo": 15 + offset,
        "quant_hi": 16 + offset,
        "slam_lo":  17 + offset,
        "texas_min": 10 + offset,  # 6+ major direct-to-game
    }


def _respond_to_1nt(e: HandEval, system) -> Bid:
    hcp = e.hcp
    t = _nt_response_thresholds(system)

    # 0-pass_max with no long major → just pass; Stayman with a weak
    # 4-cM is a separate "garbage Stayman" convention we don't model.
    if hcp <= t["pass_max"] and not e.five_card_majors:
        return passb(why=f"0-{t['pass_max']} HCP, no 4cM/5cM → pass 1NT")

    has_4S = e.suit_lengths[Suit.SPADES] == 4
    has_4H = e.suit_lengths[Suit.HEARTS] == 4
    has_5S = e.suit_lengths[Suit.SPADES] >= 5
    has_5H = e.suit_lengths[Suit.HEARTS] >= 5

    # Jacoby transfers (always — every Q-Plus system flips this on)
    if has_5H or has_5S:
        # Texas: 6+ in a major with game values goes straight to game.
        if system.has("A-1NT-transfer-level-4.Texas") or system.has("A-1NT-transfer-level-4.Texas") is False:
            # (Texas is in every bundled system; the redundant check
            # documents intent.)
            if e.suit_lengths[Suit.HEARTS] >= 6 and hcp >= t["texas_min"]:
                return bid(4, Suit.DIAMONDS, alert=True,
                           why=f"Texas: 6+ hearts, {t['texas_min']}+ HCP (GF)")
            if e.suit_lengths[Suit.SPADES] >= 6 and hcp >= t["texas_min"]:
                return bid(4, Suit.HEARTS, alert=True,
                           why=f"Texas: 6+ spades, {t['texas_min']}+ HCP (GF)")
        # Standard Jacoby transfer
        if has_5H:
            return bid(2, Suit.DIAMONDS, alert=True, why="Jacoby transfer to hearts")
        return bid(2, Suit.HEARTS, alert=True, why="Jacoby transfer to spades")

    # Stayman: 4cM and at least invitational values.
    if hcp >= t["invite_lo"] and (has_4S or has_4H):
        return bid(2, Suit.CLUBS, alert=True, why="Stayman, asks for 4cM")

    # No major path → NT raises.
    if t["invite_lo"] <= hcp <= t["invite_hi"]:
        return bid(2, Suit.NOTRUMP,
                   why=f"Invitational {t['invite_lo']}-{t['invite_hi']} HCP")
    if t["game_lo"] <= hcp < t["quant_lo"]:
        return bid(3, Suit.NOTRUMP, why="To-play game in NT")
    if t["quant_lo"] <= hcp <= t["quant_hi"]:
        # Gerber 4♣ ace-ask when the system has it AND we're at the
        # top of the quantitative range (last HCP point before direct
        # slam). Gives responder a cheap ace-count before committing
        # to 6NT; opener answers 4♦/4♥/4♠/4NT for 0-4/1/2/3 aces.
        if (hcp >= t["quant_hi"]
                and (system.has("S-Gerber.classic")
                     or system.has("S-Gerber.roman")
                     or system.has("S-Gerber.keycard"))):
            return bid(4, Suit.CLUBS, alert=True,
                       why="Gerber: ace-asking 4♣ (slam-zone, no major)")
        return bid(4, Suit.NOTRUMP, alert=True, why="Quantitative slam invite")
    if hcp >= t["slam_lo"]:
        return bid(6, Suit.NOTRUMP, why="Slam values, no major fit")
    return passb(why="Below invitational values, no 4cM")


def _respond_to_1nt_competitive(state, e, system):
    """Lebensohl after 1NT-(2X). Slow shows (2NT relay then bid suit) =
    weak; fast shows (direct 3X) = invitational+; cuebid of overcaller's
    suit = Stayman."""
    overcall = state.rho_bids[-1]

    # 1NT-(X): escape from a penalty double. Q-Plus's `C-1NT-doubled.…`
    # flag governs whether and how we run.
    #   * `all-escape` (SAYC): with 0-7 HCP and a 5+ suit, just bid it
    #     naturally — we'll find the best partial.
    #   * `Stayman-and-Jacoby` (Precision 90M): use 2♣ Stayman / 2♦/2♥
    #     Jacoby transfers as in the non-doubled auction, but with
    #     looser HCP requirements.
    # Pass with a balanced 8+ — XX would be ideal but we model it as
    # passing for redouble-by-partner semantics in a future pass.
    if overcall.is_double:
        hcp = e.hcp
        if (system.has("C-1NT-doubled.all-escape")
                or system.has("C-1NT-doubled.Stayman-and-Jacoby")):
            # Escape to long suit (5+) with weak hand.
            if hcp <= 7:
                # Pick the longest non-club suit first (2♣ might be Stayman
                # in some agreements; bid 2♦/2♥/2♠ natural if 5+).
                for suit in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS):
                    if e.suit_lengths[suit] >= 5:
                        return bid(2, suit, alert=True,
                                   why=f"1NT-X escape: 5+ "
                                       f"{suit.to_char()}, weak hand")
                # Clubs as last resort
                if e.suit_lengths[Suit.CLUBS] >= 5:
                    return bid(2, Suit.CLUBS, alert=True,
                               why="1NT-X escape: 5+ clubs, weak hand")
                # No 5-card suit, 0-4 HCP → just pass and hope.
                if hcp <= 4:
                    return passb(why="1NT-X: weak, no escape — pass")
        # Doubles without an escape flag, or strong-enough responder
        # → fall back to non-competitive logic (XX implicit via pass).
        return _respond_to_1nt(e, system)

    if overcall.suit is None or overcall.suit == Suit.NOTRUMP:
        # Doubles / NT overcalls — fall back to non-competitive logic.
        return _respond_to_1nt(e, system)

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


def _respond_to_2nt(e: HandEval, system) -> Bid:
    """Responses to opener's 2NT. The 2NT range varies by system:
    SAYC / Precision 90 = 20-21, Precision 70 = 22-23. Slam invitational
    threshold scales with the upper end (need ~10 to reach 33 vs partner
    at 21, but only ~9 if partner can have 23).
    """
    hcp = e.hcp
    nt_max = system.two_nt_max_hcp  # 21 (most) or 23 (Precision 70)
    # 5-card major → transfer (2NT-3D=hearts, 2NT-3H=spades)
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(3, Suit.DIAMONDS, alert=True, why="Jacoby transfer to hearts (over 2NT)")
    if e.suit_lengths[Suit.SPADES] >= 5:
        return bid(3, Suit.HEARTS, alert=True, why="Jacoby transfer to spades (over 2NT)")
    # Stayman
    if e.suit_lengths[Suit.SPADES] == 4 or e.suit_lengths[Suit.HEARTS] == 4:
        return bid(3, Suit.CLUBS, alert=True, why="Stayman over 2NT")
    # Bare 0-4 → just sign off in 3NT.
    if hcp <= 4:
        return bid(3, Suit.NOTRUMP, why="Sign off in 3NT (modest values)")
    # Quantitative threshold: hcp such that hcp + nt_max ≥ 33.
    if hcp >= max(8, 33 - nt_max):
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


def _respond_to_weak_two(state, e: HandEval, system) -> Bid:
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
    # 2NT inquiry — meaning depends on the spec:
    #   * SAYC `A-2MA-2NT.feature-showing` → opener bids 3 of an
    #     outside Ax/Kxx feature, or rebids the suit with no feature.
    #   * Q-Plus Precision 90M `A-2MA-2NT.Ogust-5-A` → opener shows
    #     hand+suit quality in 3♣/3♦/3♥/3♠ (Ogust matrix).
    # Either way responder bids 2NT and lets opener reveal; the alert
    # tells Claude (and the opponents) which inquiry is in use.
    if hcp >= 14 and not e.is_balanced:
        inquiry = "Ogust" if system.has("A-2MA-2NT.Ogust-5-A") else "feature ask"
        return bid(2, Suit.NOTRUMP, alert=True,
                   why=f"2NT inquiry ({inquiry})")
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


def _respond_to_minor(state, e: HandEval, system) -> Bid:
    op = state.opening_bid
    minor = op.suit
    hcp = e.hcp

    # Inverted minor raises (Q-Plus Precision 90M/90P/70):
    #   1m-2m = strong (10+ HCP, 4+ trump support, forcing 1 round)
    #   1m-3m = weak preemptive (0-9 HCP, 5+ trump support)
    # Only fires when the system flags it AND there's been no RHO
    # double (Q-Plus's "only-nodouble" constraint).
    inverted = (any(k.startswith("A-1MI-inverted-raises") for k in system.raw_rules)
                and not state.rho_bids)
    fit = e.suit_lengths.get(minor, 0)
    if inverted and fit >= 4:
        # 4+ support with no major to show (skip if 4cM is present —
        # those go 1H/1S instead, by Q-Plus's standard convention).
        has_4cM = (e.suit_lengths.get(Suit.HEARTS, 0) >= 4
                   or e.suit_lengths.get(Suit.SPADES, 0) >= 4)
        if not has_4cM:
            if hcp >= 10:
                return bid(2, minor, alert=True,
                           why=f"Inverted minor raise (2{minor.to_char()}): "
                               "10+ HCP, 4+ support, forcing")
            if hcp <= 9 and fit >= 5:
                return bid(3, minor, alert=True,
                           why=f"Inverted minor preempt (3{minor.to_char()}): "
                               "0-9 HCP, 5+ support")

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


def _respond_to_minor_competitive(state, e: HandEval, system) -> Bid:
    """After 1m-(overcall): negative double with both unbid majors,
    new-suit 1H/1S still natural and forcing for one round. The
    negative-double level cap follows the system spec (`C-Sputnik`)."""
    overcall = state.rho_bids[-1]
    hcp = e.hcp
    overcall_suit = overcall.suit
    if overcall.is_double:
        # Truscott 2NT (Jordan 2NT in the US): after 1m-(X), 2NT shows
        # a limit raise with 4+ trump support, freeing 3m for weak
        # preemptive raises. Q-Plus's `A-1MI-Truscott-2NT` enables this.
        minor = state.opening_bid.suit
        if (system.has("A-1MI-Truscott-2NT")
                and minor in (Suit.CLUBS, Suit.DIAMONDS)
                and e.suit_lengths.get(minor, 0) >= 4
                and 10 <= hcp <= 12):
            return bid(2, Suit.NOTRUMP, alert=True,
                       why=f"Truscott 2NT: limit raise of "
                           f"{minor.to_char()} (10-12, 4+ trumps)")
        # XX or new bid; default to redouble with 10+
        if hcp >= 10:
            return Bid(is_redouble=True, explanation="Redouble: 10+ HCP")
        return passb()
    if overcall_suit is None:  # NT overcall — treat as natural
        return _respond_to_minor(state, e, system)
    # Negative double with both unbid majors, valid through the
    # system's Sputnik cap (SAYC: 2♠, Precision 90M: 3♠).
    neg_max = _negative_double_max_level(system)
    can_neg_dbl = (overcall.level <= neg_max
                   and e.suit_lengths[Suit.HEARTS] >= 4
                   and e.suit_lengths[Suit.SPADES] >= 4
                   and hcp >= 6)
    if can_neg_dbl:
        return double(why=f"Negative double — both majors (Sputnik ≤{neg_max})")
    # Bid an unbid major naturally
    for m in (Suit.HEARTS, Suit.SPADES):
        if m != overcall_suit and e.suit_lengths[m] >= 5:
            level = 1 if _BID_RANK[m] > _BID_RANK[overcall_suit] else 2
            return bid(level, m, why="Forcing bid in unbid major")
    if hcp >= 10 and _has_stopper(e, overcall_suit):
        return bid(2, Suit.NOTRUMP, why="2NT, 10-12, stopper in opp's suit")
    return passb()


def _respond_to_major(state, e: HandEval, system) -> Bid:
    op = state.opening_bid
    major = op.suit
    hcp = e.hcp
    fit = e.suit_lengths.get(major, 0)

    # Q-Plus Precision 90M uses Bergen raises: 3♣ = constructive (10-11),
    # 3♦ = limit (12-13). 3M is freed up for weak preemptive raises in
    # that case. Detect via the parametrised flag (`A-1MA-Bergen-3C.…`).
    bergen = any(k.startswith("A-1MA-Bergen-3C") for k in system.raw_rules)

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
        # Bergen raises (only when the system enables them)
        if bergen:
            if 10 <= hcp <= 11:
                return bid(3, Suit.CLUBS, alert=True,
                           why="Bergen 3♣: constructive raise (10-11, 4+ trumps)")
            if 12 <= hcp <= 13:
                return bid(3, Suit.DIAMONDS, alert=True,
                           why="Bergen 3♦: limit raise (12-13, 4+ trumps)")
            # 3M is now weak preemptive (0-9 with 4+ trumps)
            if hcp <= 9:
                return bid(3, major, alert=True,
                           why="Bergen 3M: weak preemptive raise (4+ trumps)")
        else:
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


def _respond_to_major_competitive(state, e: HandEval, system) -> Bid:
    overcall = state.rho_bids[-1]
    hcp = e.hcp
    op_suit = state.opening_bid.suit
    other_major = Suit.SPADES if op_suit == Suit.HEARTS else Suit.HEARTS

    if overcall.is_double:
        if hcp >= 10:
            return Bid(is_redouble=True, explanation="Redouble (10+)")
        # Standard responses are still on
        return _respond_to_major(state, e, system)

    if overcall.suit is None or overcall.suit == Suit.NOTRUMP:
        return _respond_to_major(state, e, system)

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

def _precision_1c_rebid(state, e: HandEval, p_last: Bid) -> Bid:
    """Opener's rebid after 1C-X (Precision strong club).

    1D negative (0-7):
        1H/1S = natural 5+ in suit, 16-21 unbalanced
        1NT   = 16-19 balanced
        2C    = natural 6+ clubs, 16-21
        2D    = natural 5+ diamonds, 16-21
        2NT   = 22-24 balanced
        3-of-suit jump shift = stronger
        3NT   = 25+ balanced

    Positive responses (1H, 1S, 2C, 2D, 1NT, 2NT, 3NT) — auction is GF;
    raise partner's suit with support, otherwise show shape.
    """
    hcp = e.hcp

    # Negative response: 1D = 0-7
    if p_last.level == 1 and p_last.suit == Suit.DIAMONDS:
        # Natural 5-card suit takes priority for unbalanced hands
        if not e.is_balanced:
            if e.suit_lengths[Suit.SPADES] >= 5:
                return bid(1, Suit.SPADES, why="Precision 1C-1D: 5+ spades, 16+")
            if e.suit_lengths[Suit.HEARTS] >= 5:
                return bid(1, Suit.HEARTS, why="Precision 1C-1D: 5+ hearts, 16+")
            if e.suit_lengths[Suit.DIAMONDS] >= 5:
                return bid(2, Suit.DIAMONDS, why="Precision 1C-1D: 5+ diamonds, 16+")
            if e.suit_lengths[Suit.CLUBS] >= 5:
                return bid(2, Suit.CLUBS, why="Precision 1C-1D: 5+ clubs, 16+")
        # Balanced rebids by HCP zone
        if 16 <= hcp <= 19:
            return bid(1, Suit.NOTRUMP, why="Precision 1C-1D: 16-19 balanced")
        if 20 <= hcp <= 21:
            return bid(2, Suit.NOTRUMP, why="Precision 1C-1D: 20-21 balanced")
        if 22 <= hcp <= 24:
            return bid(2, Suit.NOTRUMP, why="Precision 1C-1D: 22-24 balanced")
        if hcp >= 25:
            return bid(3, Suit.NOTRUMP, why="Precision 1C-1D: 25+ balanced")
        # Fallback for hands with no clear suit and not perfectly balanced.
        return bid(1, Suit.NOTRUMP, why="Precision 1C-1D: rebid 1NT (no clear shape)")

    # Positive 1H / 1S response (5+ cards in major, 8+ HCP) — set GF and
    # raise with 3+ support, else show own shape.
    if p_last.level == 1 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        major = p_last.suit
        if e.suit_lengths[major] >= 3:
            if e.hcp >= 20 or e.controls >= 5:
                return bid(4, Suit.NOTRUMP, alert=True,
                           why="Precision 1C-1M: RKC after fit, slam interest")
            return bid(3, major, why="Precision 1C-1M: simple raise (GF)")
        # No fit → bid own 5-card suit
        for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
            if s == major:
                continue
            if e.suit_lengths[s] >= 5:
                level = 2 if _BID_RANK[s] < _BID_RANK[major] else 2
                return bid(level, s, why=f"Precision 1C-1M: own {s.to_char()} suit")
        # Balanced no-fit → 2NT or 3NT depending on HCP
        if hcp <= 19:
            return bid(2, Suit.NOTRUMP, why="Precision 1C-1M: balanced no fit")
        return bid(3, Suit.NOTRUMP, why="Precision 1C-1M: extras balanced")

    # Positive 1NT response (8-13 balanced)
    if p_last.level == 1 and p_last.suit == Suit.NOTRUMP:
        if hcp >= 22 and e.is_balanced:
            return bid(4, Suit.NOTRUMP, alert=True,
                       why="Precision 1C-1NT: quantitative slam invite")
        if e.suit_lengths[Suit.SPADES] >= 5:
            return bid(2, Suit.SPADES, why="Precision 1C-1NT: 5+ spades")
        if e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS, why="Precision 1C-1NT: 5+ hearts")
        if hcp >= 19:
            return bid(3, Suit.NOTRUMP, why="Precision 1C-1NT: 19+ balanced")
        return bid(2, Suit.NOTRUMP, why="Precision 1C-1NT: invitational")

    # Positive 2C / 2D response (5+ in minor, 8+ HCP)
    if p_last.level == 2 and p_last.suit in (Suit.CLUBS, Suit.DIAMONDS):
        minor = p_last.suit
        if e.suit_lengths[minor] >= 3:
            return bid(3, minor, why=f"Precision 1C-2{minor.to_char()}: raise with fit")
        if e.suit_lengths[Suit.SPADES] >= 5:
            return bid(2, Suit.SPADES, why=f"Precision 1C-2{minor.to_char()}: 5+ spades")
        if e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS, why=f"Precision 1C-2{minor.to_char()}: 5+ hearts")
        return bid(2, Suit.NOTRUMP, why=f"Precision 1C-2{minor.to_char()}: balanced rebid")

    # Positive 2NT (14-16 balanced) → drive to slam if our hand is huge
    if p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
        if hcp >= 18:
            return bid(6, Suit.NOTRUMP, why="Precision 1C-2NT: slam in NT")
        return bid(3, Suit.NOTRUMP, why="Precision 1C-2NT: stop in 3NT")

    # Positive 3NT (17+ balanced) → cooperative slam exploration
    if p_last.level == 3 and p_last.suit == Suit.NOTRUMP:
        if hcp >= 17:
            return bid(6, Suit.NOTRUMP, why="Precision 1C-3NT: slam values")
        return passb()

    return passb(why="Precision 1C: no clear rebid")


def _precision_2c_rebid(state, e: HandEval, p_last: Bid) -> Bid:
    """Opener's rebid after 2C-X (Precision natural club opening).

    Standard responses to handle:
        2D = inquiry — show 4-card major if any, else 2NT (no major) or 3C (min)
        2H/2S = natural forcing — raise with fit, otherwise show shape
        2NT = invitational — accept with max
        3C = preemptive raise — pass
        3NT = to play — pass
    """
    hcp = e.hcp

    if p_last.level == 2 and p_last.suit == Suit.DIAMONDS:
        # 2D inquiry: show 4-card major if available
        if e.suit_lengths[Suit.SPADES] >= 4:
            return bid(2, Suit.SPADES, why="Precision 2C-2D: 4+ spades")
        if e.suit_lengths[Suit.HEARTS] >= 4:
            return bid(2, Suit.HEARTS, why="Precision 2C-2D: 4+ hearts")
        # No major: show range. Min (11-12) → 3C, max (13-15) → 2NT.
        if 13 <= hcp <= 15:
            return bid(2, Suit.NOTRUMP, why="Precision 2C-2D: max no major")
        return bid(3, Suit.CLUBS, why="Precision 2C-2D: min no major")

    if p_last.level == 2 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        major = p_last.suit
        if e.suit_lengths[major] >= 3:
            if hcp >= 14:
                return bid(4, major, why=f"Precision 2C-2{major.to_char()}: max raise")
            return bid(3, major, why=f"Precision 2C-2{major.to_char()}: simple raise")
        if hcp <= 12:
            return bid(3, Suit.CLUBS, why=f"Precision 2C-2{major.to_char()}: rebid clubs (min)")
        return bid(2, Suit.NOTRUMP, why=f"Precision 2C-2{major.to_char()}: balanced extras")

    if p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
        # Invitational — accept with max (14-15)
        if hcp >= 14:
            return bid(3, Suit.NOTRUMP, why="Precision 2C-2NT: accept invite")
        return bid(3, Suit.CLUBS, why="Precision 2C-2NT: decline invite")

    return passb()


def _opener_rebid(state, e: HandEval, system: str) -> Bid:
    if not state.partner_bids:
        # Partner passed — auction is dying. With a strong rebiddable hand,
        # might balance, but partner is silent ⇒ pass.
        return passb()

    p_last = state.partner_bids[-1]
    op = state.opening_bid

    # Precision-specific opener rebids run before the SAYC paths.
    if getattr(system, "strong_open_call", "2C") == "1C":
        # 1C strong: structured rebids over partner's 1D negative or
        # positive response.
        if op.level == 1 and op.suit == Suit.CLUBS:
            return _precision_1c_rebid(state, e, p_last)
        # 2C natural: respond to partner's 2D shape inquiry.
        if op.level == 2 and op.suit == Suit.CLUBS:
            return _precision_2c_rebid(state, e, p_last)

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

    # Strong 2C openings (SAYC only — Precision 2C was routed above):
    # rebid in the longest natural suit at the 2-level.
    if op.level == 2 and op.suit == Suit.CLUBS:
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
        # Support double — opener has 1-of-minor opening + RHO overcall
        # over partner's 1H/1S; double shows EXACTLY 3-card support so
        # responder can distinguish it from the natural 2M raise that
        # promises 4+. Only fires for systems flagging C-support-double
        # (Q-Plus: Precision 90M and Precision 90P).
        if (system.has("C-support-double")
                and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and state.rho_bids
                and e.suit_lengths[p_last.suit] == 3
                and 12 <= e.hcp <= 17):
            return double(why=f"Support double — exactly 3-card "
                              f"{p_last.suit.to_char()}")
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

def _overcall_over_1nt(state, e: HandEval, system) -> Bid:
    """Overcalls over the opponents' 1NT opening.

    Q-Plus enables Landy in every bundled system (`O-1NT.Landy`):
      * 2♣ = both majors (4+/4+, ~10-15 HCP)
      * 2♦ = single-suiter (some flavours; treat 2♦ natural when long
        diamonds)
      * 2H/2S = natural 6+ in the major
      * Double in 2nd seat = penalty (15+ HCP)

    Penalty doubles vs takeout depend on `O-1NT-x-pos2.is-penalty` etc.
    For now we treat the direct double as penalty (matches Q-Plus's
    SAYC default).
    """
    hcp = e.hcp

    # Penalty double: 15+ HCP, balanced.
    if hcp >= 15 and (e.is_balanced or e.is_semi_balanced):
        return double(why="Penalty double of 1NT (15+ HCP balanced)")

    # Landy 2♣ — both majors, at least 4-4, competitive values.
    if (system.has("O-1NT.Landy")
            and e.suit_lengths[Suit.HEARTS] >= 4
            and e.suit_lengths[Suit.SPADES] >= 4
            and 9 <= hcp <= 15):
        return bid(2, Suit.CLUBS, alert=True,
                   why="Landy: both majors (4+/4+, 9-15 HCP)")

    # Natural 2-level overcall with a 6-card suit and modest values.
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS):
        if e.suit_lengths[s] >= 6 and 9 <= hcp <= 15:
            return bid(2, s, why=f"Natural 2{s.to_char()} overcall (6+ cards)")

    return passb(why="No suitable overcall over 1NT")


def _overcall_over_weak_two(state, e: HandEval, system) -> Bid:
    """Overcalls over the opponents' weak-2 opening.

    Q-Plus's `C-Lebensohl.after-weak-2` enables a slow/fast distinction:
      * Direct 3-level new-suit overcall = invitational+ (10+ HCP,
        good 6+ suit).
      * Double (takeout) = 12+ HCP, shortness in opener's suit.
      * 2NT = Lebensohl relay to 3♣ (weak with a long suit, will
        correct to own suit at 3-level).
      * 3NT direct = 17+ balanced with stopper in opener's suit.
      * Leaping Michaels (4♣/4♦, `O-Leaping-Michaels`) = strong
        two-suiter with the bid minor + the unbid major.
    """
    op = state.opening_bid
    hcp = e.hcp
    op_suit = op.suit

    # 3NT direct — strong balanced with stopper.
    if 17 <= hcp <= 19 and e.is_balanced and _has_stopper(e, op_suit):
        return bid(3, Suit.NOTRUMP, why="3NT direct: 17-19 balanced + stopper")

    # Leaping Michaels — 4-level minor cuebid showing minor + other major,
    # 17+ HCP, 5-5 distribution.
    if system.has("O-Leaping-Michaels"):
        for minor in (Suit.CLUBS, Suit.DIAMONDS):
            for major in (Suit.HEARTS, Suit.SPADES):
                if major == op_suit:
                    continue
                if (e.suit_lengths[minor] >= 5
                        and e.suit_lengths[major] >= 5
                        and hcp >= 17):
                    return bid(4, minor, alert=True,
                               why=f"Leaping Michaels: 5-5 in "
                                   f"{minor.to_char()}+{major.to_char()}, 17+")

    # Takeout double — shortness in opener's suit and tolerance for others.
    unbid = [s for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
             if s != op_suit]
    if hcp >= 12 and e.suit_lengths.get(op_suit, 0) <= 2:
        if sum(1 for s in unbid if e.suit_lengths.get(s, 0) >= 3) >= 3:
            return double(why="Takeout double of weak 2")

    # Direct 3-level natural overcall — invitational+, good 6+ suit.
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if s == op_suit:
            continue
        if e.suit_lengths[s] >= 6 and 11 <= hcp <= 17 and e.suit_hcp[s] >= 6:
            level = 2 if _BID_RANK[s] > _BID_RANK[op_suit] else 3
            return bid(level, s, why=f"{level}{s.to_char()} natural overcall "
                                     "(weak-2 context, invitational+)")

    # 2NT Lebensohl relay (weak overcall with a long suit).
    if (system.has("C-Lebensohl.after-weak-2")
            and 8 <= hcp <= 10
            and any(e.suit_lengths[s] >= 6 for s in unbid)):
        return bid(2, Suit.NOTRUMP, alert=True,
                   why="Lebensohl 2NT relay (weak — will sign off in long suit)")

    return passb(why="No suitable overcall over weak 2")


def _overcall(state, e: HandEval, system) -> Bid:
    op = state.opening_bid
    hcp = e.hcp

    # Overcalls over opponent's 1NT — handled separately.
    if op.level == 1 and op.suit == Suit.NOTRUMP:
        return _overcall_over_1nt(state, e, system)

    # Overcalls over opponent's weak 2 — Lebensohl-style flow if the
    # system enables `C-Lebensohl.after-weak-2`. Direct 3-level overcall
    # = invitational+; double = takeout values; 2NT = relay (slow path,
    # which we'll bid as "weak" continuation). Without Lebensohl, we
    # use a straight takeout-double policy.
    if op.level == 2 and op.suit in (Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        return _overcall_over_weak_two(state, e, system)

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


def _advance_partner_overcall(state, e: HandEval, system) -> Bid:
    p_last = state.partner_bids[-1]
    hcp = e.hcp

    # Takeout double advancer: bid the cheapest suit / NT
    if p_last.is_double:
        # Responsive double: partner doubled, LHO RAISED opener's suit
        # (i.e., supported), and I have ~6-10 HCP with both unbid suits.
        # My double asks partner to pick one of those unbid suits.
        if system.has("C-responsive-double") and state.lho_bids:
            lho_last = state.lho_bids[-1]
            opener_suit = state.opening_bid.suit
            if (not lho_last.is_pass
                    and not lho_last.is_double
                    and lho_last.suit == opener_suit
                    and 6 <= hcp <= 10):
                # Identify the two unbid suits (anything other than opener's
                # and partner's last call's strain — but partner doubled, so
                # both unbid suits are still alive).
                unbid_pair = [s for s in (Suit.SPADES, Suit.HEARTS,
                                          Suit.DIAMONDS, Suit.CLUBS)
                              if s != opener_suit]
                # Need at least 3-3 in two of those four suits, the typical
                # responsive-double shape.
                long_pair = sorted(
                    unbid_pair,
                    key=lambda s: e.suit_lengths.get(s, 0),
                    reverse=True,
                )
                if (e.suit_lengths.get(long_pair[0], 0) >= 3
                        and e.suit_lengths.get(long_pair[1], 0) >= 3):
                    return double(why="Responsive double — pick a suit")

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
        opener_suit = state.opening_bid.suit
        # Unassuming cue-bid: with 3+ support and limit-raise+ values
        # (10+ HCP), cue opener's suit instead of jumping to limit raise.
        # Lets partner separate constructive from preemptive raises.
        if (system.has("C-unassuming-cue-bids")
                and fit >= 3
                and opener_suit is not None
                and opener_suit != suit
                and 10 <= hcp <= 12):
            # Cuebid at the cheapest available level above the current contract.
            cue_level = state.last_level
            if (state.last_suit_bid
                    and _BID_RANK[opener_suit] <= _BID_RANK[state.last_suit_bid]):
                cue_level = state.last_level + 1
            return bid(cue_level, opener_suit, alert=True,
                       why=f"Unassuming cue-bid: limit raise+ "
                           f"of {suit.to_char()} (10-12 HCP, 3+ support)")
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

def _highest_strain_bid(auction: List[Bid]) -> Optional[Bid]:
    """Return the highest level+suit bid in the auction (ignoring X/XX/Pass),
    or None if no strain bid has been made."""
    out = None
    for b in auction:
        if b.is_pass or b.is_double or b.is_redouble:
            continue
        if b.suit is None:
            continue
        if out is None:
            out = b
            continue
        if b.level > out.level or (
            b.level == out.level and _BID_RANK[b.suit] > _BID_RANK[out.suit]
        ):
            out = b
    return out


def _legalize_bid(chosen: Bid, state: AuctionState) -> Bid:
    """Coerce a candidate bid into a legal one given the current auction.

    The rule-based bidder occasionally fires a "raise to game" or "advance
    a takeout double" branch that picks a fixed level (e.g. 4H) without
    consulting the current auction height — illegal once the opponents
    have already pushed past that level. This guard upgrades insufficient
    suit bids to the next legal step in the same denomination, falling
    back to Pass when even 7-of-the-suit is below the current contract.
    Doubles are only kept when RHO's last call was a strain bid;
    redoubles only when RHO doubled our partnership's bid.
    """
    if chosen is None:
        return passb()
    if chosen.is_pass:
        return chosen

    if chosen.is_double:
        if not state.rho_bids:
            return passb()
        last_rho = state.rho_bids[-1]
        if last_rho.is_pass or last_rho.is_double or last_rho.is_redouble:
            return passb()
        if last_rho.suit is None:
            return passb()
        return chosen

    if chosen.is_redouble:
        # Walk backward looking for the most recent non-pass call. It must
        # be an opponent's double of our partnership's last strain bid.
        last_call = None
        for s, b in reversed(state.bids):
            if not b.is_pass:
                last_call = (s, b)
                break
        if last_call is None or not last_call[1].is_double:
            return passb()
        # Ensure the doubler is an opponent.
        partner = state.seat.partner()
        if last_call[0] in (state.seat, partner):
            return passb()
        return chosen

    # Strain bid: must outrank the highest prior strain bid.
    high = _highest_strain_bid([b for _, b in state.bids])
    if high is None:
        return chosen  # First strain bid in the auction — always legal.

    if chosen.level > high.level or (
        chosen.level == high.level and _BID_RANK[chosen.suit] > _BID_RANK[high.suit]
    ):
        return chosen

    # Insufficient: try to upgrade to the lowest legal level in the same
    # denomination. If even 7-of-the-suit isn't enough, pass.
    target_level = high.level
    if _BID_RANK[chosen.suit] <= _BID_RANK[high.suit]:
        target_level += 1
    if target_level > 7:
        return passb()
    return Bid(
        level=target_level,
        suit=chosen.suit,
        alert=chosen.alert,
        explanation=chosen.explanation
        + f" [legalized from {chosen.level}{chosen.suit.to_char()}]",
    )


class NativeBiddingEngine:
    """Plug-compatible with BridgeEngine for bidding only.

    Construct with either a system *name* (string — looked up via
    `bidding_systems.get_system`) or a pre-built `BiddingSystem`. The
    engine always stores a `BiddingSystem` internally so all the
    decision-tree code can read parameters directly off the spec
    (`self.system.one_nt_min_hcp`, `self.system.strong_open_call`,
    `self.system.has("A-1NT-Stayman")`, etc.).
    """

    def __init__(self, system="SAYC"):
        from .bidding_systems import BiddingSystem, get_system
        self.system: BiddingSystem = (
            system if isinstance(system, BiddingSystem) else get_system(system)
        )

    def set_system(self, system):
        from .bidding_systems import BiddingSystem, get_system
        self.system = (
            system if isinstance(system, BiddingSystem) else get_system(system)
        )

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
            chosen = _legalize_bid(chosen, state)

            return EngineResponse(
                action=chosen,
                candidates=[BidCandidate(bid=chosen, score=1.0, explanation=chosen.explanation)],
                quality=0.6,  # Rule-based, not probabilistic
                who=f"Native ({self.system.name})",
                hcp_estimate=None,
                shape_estimate=None,
            )
        except Exception as ex:
            return EngineResponse(action=Bid.make_pass(), who=f"NativeError: {ex}")
