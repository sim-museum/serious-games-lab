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
    # Per-suit honour presence — needed by the RKC follow-up so the
    # bidder can count specific keys (aces + trump king) and respond
    # to the trump-queen ask.
    has_ace: dict            # Suit -> bool
    has_king: dict           # Suit -> bool
    has_queen: dict          # Suit -> bool


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

    has_ace = {s: any(c.rank == Rank.ACE for c in cs) for s, cs in by_suit.items()}
    has_king = {s: any(c.rank == Rank.KING for c in cs) for s, cs in by_suit.items()}
    has_queen = {s: any(c.rank == Rank.QUEEN for c in cs) for s, cs in by_suit.items()}

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
        has_ace=has_ace,
        has_king=has_king,
        has_queen=has_queen,
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
    vulnerability: Vulnerability = Vulnerability.NONE


def parse_auction(seat: Seat, dealer: Seat, auction: List[Bid],
                  vulnerability: Vulnerability = Vulnerability.NONE
                  ) -> AuctionState:
    """Build an AuctionState. The bidder seats rotate clockwise from dealer.

    `vulnerability` is optional — passing it lets the bidder make
    vulnerability-aware choices (overcall thresholds, preempt
    discipline, etc.). Defaults to None so existing callers stay
    working.
    """
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
        vulnerability=vulnerability,
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

def open_bid(eval_: HandEval, system=None, state=None) -> Bid:
    """Pick an opening bid (or Pass) given the hand.

    `system` is now a `BiddingSystem` from `bidding_systems`. Legacy
    callers passing the string "Precision" / "SAYC" still work — the
    string is looked up via `get_system`. Dispatch routes by
    `strong_open_call`: "1C" → Precision-family open, otherwise SAYC.

    `state` is optional; when present the opening branch can make
    vulnerability-aware choices (e.g. weak-2 quality requirements
    tighten when vulnerable).
    """
    from .bidding_systems import BiddingSystem, get_system
    if system is None:
        system = get_system("SAYC")
    elif not isinstance(system, BiddingSystem):
        system = get_system(system)
    if system.strong_open_call == "1C":
        return _open_precision(eval_, system, state=state)
    return _open_sayc(eval_, system, state=state)


def _open_sayc(e: HandEval, system, state=None) -> Bid:
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

    # Notrump openings (balanced + extended-shape 1NT in Q-Plus systems).
    # Q-Plus's `B-1NT-style.{weak,any}-5-{heart,spade}` and
    # `B-1NT-style.weak-6-minor` flags widen 1NT to include 5-3-3-2 with a
    # 5-card major and 5-3-3-2 / 6-3-2-2 with a 6-card minor — common in
    # Precision90 and increasingly mainstream in 2/1. Honour those flags
    # before falling through to suit openings.
    five_card_nt_ok = (
        (system.one_nt_allow_five_card_heart
         and e.suit_lengths[Suit.HEARTS] == 5
         and e.distribution == (5, 3, 3, 2))
        or
        (system.one_nt_allow_five_card_spade
         and e.suit_lengths[Suit.SPADES] == 5
         and e.distribution == (5, 3, 3, 2))
    )
    six_card_minor_nt_ok = (
        system.one_nt_allow_six_card_minor
        and (e.suit_lengths[Suit.CLUBS] == 6 or e.suit_lengths[Suit.DIAMONDS] == 6)
        and e.distribution in ((6, 3, 2, 2), (6, 2, 2, 3))
        and e.suit_lengths[Suit.HEARTS] < 4
        and e.suit_lengths[Suit.SPADES] < 4
    )
    if (e.is_balanced or e.is_semi_balanced
            or five_card_nt_ok or six_card_minor_nt_ok):
        if nt_min <= hcp <= nt_max:
            tag = "balanced"
            if five_card_nt_ok:
                tag = "5-3-3-2 with 5-card major"
            elif six_card_minor_nt_ok:
                tag = "with 6-card minor"
            return bid(1, Suit.NOTRUMP,
                       why=f"{nt_min}-{nt_max} {tag}")
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
    pre = _preempt_bid(e, state, system)
    if pre is not None:
        return pre

    # Suit openings (12-21 HCP, unbalanced or with 5cM)
    if hcp < 12:
        return passb()

    # Major-suit opening, length requirement from the spec.
    # SAYC / 2/1 / French / Precision = 5+ majors. Acol = 4+ majors.
    maj_min = getattr(system, 'one_major_card_min', 5)
    if (e.suit_lengths[Suit.SPADES] >= maj_min
            and e.suit_lengths[Suit.SPADES] >= e.suit_lengths[Suit.HEARTS]):
        return bid(1, Suit.SPADES, why=f"{maj_min}+ spades")
    if e.suit_lengths[Suit.HEARTS] >= maj_min:
        return bid(1, Suit.HEARTS, why=f"{maj_min}+ hearts")

    # No qualifying major → open longer minor; with 3-3 minors open 1C
    # (with 4-4 prefer 1D — Acol & SAYC convention).
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


def _open_precision(e: HandEval, system, state=None) -> Bid:
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

    # Solid-minor 4NT (Q-Plus `B-4NT.solid-minor`, Precision70): a solid
    # 8+ minor wants 4NT — Blackwood-asks for aces in a self-supporting
    # suit. Comes before the strong-1♣ check because 1♣ is artificial
    # and would lose the self-sufficient-minor message.
    if system.has("B-4NT.solid-minor"):
        for minor in (Suit.CLUBS, Suit.DIAMONDS):
            if (e.suit_lengths[minor] >= 8
                    and e.suit_hcp[minor] >= 9       # AKQ at minimum
                    and 15 <= hcp <= 22
                    and e.suit_lengths[Suit.SPADES] <= 3
                    and e.suit_lengths[Suit.HEARTS] <= 3):
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"Solid-minor 4NT: 8+ solid "
                               f"{minor.to_char()}, {hcp} HCP")

    # Strong artificial 1C — but defer to the limited 1NT opening
    # for balanced hands inside the NT range. Q-Plus's Precision90M
    # opens 1NT with 16 balanced (the upper end of the 14-16 NT
    # range) rather than 1C, since 1NT is more descriptive when
    # the hand is balanced and inside the limited-NT band.
    if hcp >= strong_min:
        if (e.is_balanced
                and nt_min <= hcp <= nt_max):
            # Fall through to the 1NT opening branch below.
            pass
        else:
            return bid(1, Suit.CLUBS, alert=True,
                       why=f"Precision: {strong_min}+ HCP, any shape")

    # Below the lower opening bound → Pass (preempts first).
    # Light 10-HCP hands fall through so the Rule-of-20 gate in
    # the 1D catchall (below) can promote them when shape warrants.
    if hcp < two_c_min:
        gamb = _gambling_3nt_open(e, system)
        if gamb is not None:
            return gamb
        pre = _preempt_bid(e, state, system)
        if pre is not None:
            return pre
        if hcp < 10:
            return passb()
        # 10 HCP — let the 1D catchall apply Rule of 20.

    # Gambling 3NT also applies inside the opening range — Precision 70
    # uses it for solid-minor hands light on HCP.
    gamb = _gambling_3nt_open(e, system)
    if gamb is not None:
        return gamb

    # Limited 1NT (Q-Plus Precision: 14-16, or 13-15 for the classic 70).
    # `B-1NT-style.weak-6-minor` extends the 1NT shape to 6-3-2-2 with a
    # 6-card minor (not solid) — common in Q-Plus Precision flavours.
    # `B-1NT-style.{weak,any}-5-{heart,spade}` opens 5-3-3-2 with the
    # named major (Precision90M/P; off in Precision70).
    weak_six_minor_ok = (
        system.one_nt_allow_six_card_minor
        and tuple(sorted(e.suit_lengths.values(), reverse=True)) == (6, 3, 2, 2)
        and any(e.suit_lengths[m] == 6
                and e.suit_hcp[m] < 7  # not AKQ-solid → still consider 1NT
                for m in (Suit.CLUBS, Suit.DIAMONDS))
    )
    five_card_major_nt_ok = (
        (system.one_nt_allow_five_card_heart
         and e.suit_lengths[Suit.HEARTS] == 5
         and e.distribution == (5, 3, 3, 2))
        or
        (system.one_nt_allow_five_card_spade
         and e.suit_lengths[Suit.SPADES] == 5
         and e.distribution == (5, 3, 3, 2))
    )
    if nt_min <= hcp <= nt_max and (
            e.is_balanced or e.is_semi_balanced
            or weak_six_minor_ok or five_card_major_nt_ok):
        if five_card_major_nt_ok:
            shape_tag = "with 5-card major (5-3-3-2)"
        elif weak_six_minor_ok:
            shape_tag = "(incl. weak 6-minor)"
        else:
            shape_tag = "balanced"
        return bid(1, Suit.NOTRUMP, alert=True,
                   why=f"Precision: {nt_min}-{nt_max} {shape_tag}")

    # 2NT — strong balanced not covered by 1NT (rare in Precision).
    if two_nt_min <= hcp <= two_nt_max and (e.is_balanced or e.is_semi_balanced):
        return bid(2, Suit.NOTRUMP,
                   why=f"{two_nt_min}-{two_nt_max} balanced")

    # NAMYATS / Texas: with `B-4MI-SA-Texas` (Q-Plus Precision90M),
    # an 8+ card major opens via a transfer minor:
    #   4♣ = 8+ hearts (transfer to 4♥)
    #   4♦ = 8+ spades (transfer to 4♠)
    # Range 6-12 HCP with a solid suit (AK or KQJ). Wider than a
    # plain 4-of-major preempt because the transfer lets partner
    # evaluate slam. Has to fire BEFORE the 1M branch so 11-HCP
    # 8-card hands don't get routed to 1S/1H.
    if system.has("B-4MI-SA-Texas") and 6 <= hcp <= 12:
        for major in (Suit.SPADES, Suit.HEARTS):
            if (e.suit_lengths[major] >= 8
                    and e.suit_hcp.get(major, 0) >= 5):
                transfer = (Suit.CLUBS if major == Suit.HEARTS
                            else Suit.DIAMONDS)
                return bid(4, transfer, alert=True,
                           why=f"NAMYATS 4{transfer.to_char()}: "
                               f"8+ {major.to_char()}, {hcp} HCP")

    # 5-card majors at the 1 level — light openings gated by Rule
    # of 20 (or 12+ HCP). Same logic as the 1D catchall below; the
    # earlier "below the lower opening bound" branch lets 10-11
    # HCP fall through here for Rule-of-20 evaluation.
    lens_top2 = sorted(e.suit_lengths.values(), reverse=True)
    rule_of_20 = hcp + lens_top2[0] + lens_top2[1]
    open_one_major_ok = (hcp >= 12) or (hcp >= 10 and rule_of_20 >= 20)
    if open_one_major_ok and e.suit_lengths[Suit.SPADES] >= 5 and e.suit_lengths[Suit.SPADES] >= e.suit_lengths[Suit.HEARTS]:
        return bid(1, Suit.SPADES, alert=True,
                   why=f"Precision 1S: {hcp} HCP, Rule of 20 = {rule_of_20}")
    if open_one_major_ok and e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(1, Suit.HEARTS, alert=True,
                   why=f"Precision: {two_c_min}-{nt_max} HCP, 5+ hearts")

    # 2♦ three-suiter (Precision90M `B-2D.Precision.majors-4-3`):
    # 11-15 HCP, 4+/3+ in the majors, 0-1 diamond. Standard shapes
    # are 4-4-1-4, 4-3-1-5, 4-4-0-5, 4-3-0-6, 3-4-1-5, etc.
    # Seed=400 board 1 S (AQ75 AQ3 2 T9872, 12 HCP, 4-3-1-5) and
    # board 8 W (AKT4 AJ92 8 J763, 13 HCP, 4-4-1-4) both fit.
    if (any(k.startswith("B-2D.Precision") for k in system.raw_rules)
            and two_c_min <= hcp <= two_c_max
            and e.suit_lengths[Suit.DIAMONDS] <= 1
            and e.suit_lengths[Suit.HEARTS] + e.suit_lengths[Suit.SPADES] >= 7
            and e.suit_lengths[Suit.HEARTS] >= 3
            and e.suit_lengths[Suit.SPADES] >= 3):
        return bid(2, Suit.DIAMONDS, alert=True,
                   why=f"Precision 2♦ three-suiter: {hcp} HCP, "
                       f"majors "
                       f"{e.suit_lengths[Suit.SPADES]}-"
                       f"{e.suit_lengths[Suit.HEARTS]}, "
                       f"short diamond")

    # 2♣ long-club (Precision-specific): 6+ clubs in the limited range.
    if e.suit_lengths[Suit.CLUBS] >= 6 and two_c_min <= hcp <= two_c_max:
        return bid(2, Suit.CLUBS, alert=True,
                   why=f"Precision: {two_c_min}-{two_c_max}, 6+ clubs")

    # 1♦ — catch-all (Q-Plus Precision90M, ≤ 15 HCP, no 5cM, no 6c
    # clubs, unbalanced or with 2c+ diamond). Q-Plus opens by HCP +
    # shape: 12+ always opens, 10-11 opens only if Rule of 20 holds
    # (hcp + lengths of the two longest suits ≥ 20). A balanced
    # 11-count (e.g. 4-4-3-2) ends up at 19 and is passed; a 10
    # with a 6-card suit usually reaches 20 and is opened. Without
    # this gate bridgeIQ either opened balanced 11-counts Q-Plus
    # passes (seed=100 board 6) or passed shapely 10-counts Q-Plus
    # opens (seed=100 board 7).
    if hcp <= one_d_max and (
            e.suit_lengths[Suit.DIAMONDS] >= 2 or not (e.is_balanced or e.is_semi_balanced)):
        lens = sorted(e.suit_lengths.values(), reverse=True)
        rule_of_20 = hcp + lens[0] + lens[1]
        if hcp >= 12 or (hcp >= 10 and rule_of_20 >= 20):
            return bid(1, Suit.DIAMONDS, alert=True,
                       why=f"Precision 1D: {hcp} HCP, Rule of 20 = "
                           f"{rule_of_20}")
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


def _preempt_bid(e: HandEval, state=None, system=None) -> Optional[Bid]:
    """Pick a weak two / 3-level preempt if the hand fits.

    Quality requirements modeled on Q-Plus / wbridge5 SAYC:
      • Weak two (6 cards): 5-10 HCP total + suit-HCP ≥ 5 (two of
        A/K/Q/J in the suit, or one ace+queen, or KQ). A J86432
        hand should NOT open 2H — top of the suit is just a Jack,
        which gives ≈ 0 defensive tricks and a terrible source.
      • Vulnerable weak two: a touch tighter — require ≥ 6 suit
        HCP and 6-10 total HCP (no shading down to 5).
      • 3-level preempt (7+ cards): 5-9 HCP, suit-HCP ≥ 4 (at
        least an ace or king or KQ in the suit).
      • 4-level preempt (8+ cards): 4-8 HCP, suit-HCP ≥ 3.
    """
    longest = e.longest_suit
    n = e.suit_lengths[longest]
    suit_hcp = e.suit_hcp[longest]
    am_vul = False
    if state is not None and hasattr(state, 'vulnerability') \
            and state.vulnerability:
        am_vul = state.vulnerability.is_vulnerable(state.seat)

    # Weak two — 6-card major or diamond (when system allows).
    # Precision-family systems generally use 2D as the three-suiter
    # so weak-2D is disabled; SAYC/2-over-1 have it on.
    if n == 6 and longest in (Suit.HEARTS, Suit.SPADES, Suit.DIAMONDS):
        if longest == Suit.DIAMONDS \
                and system is not None \
                and not getattr(system, 'weak_two_diamonds', True):
            # System doesn't play weak 2♦ — skip the preempt path
            # and let the natural-opening branch handle the hand.
            return None
        if longest in (Suit.HEARTS, Suit.SPADES) \
                and system is not None \
                and not getattr(system, 'weak_two_majors', True):
            return None
        min_total = 6 if am_vul else 5
        # Non-vul Q-Plus accepts AT9xxx-class suits (one top honor +
        # spot-card sequence). Modeling that as suit-HCP ≥ 4 nvul /
        # ≥ 5 vul.
        min_suit = 5 if am_vul else 4
        # Max HCP for a weak two is 9 — 10 HCP + 6-card suit is the
        # boundary case that Q-Plus opens at the 1-level (more
        # constructive auction). Capping at 9 here matches.
        if min_total <= e.hcp <= 9 and suit_hcp >= min_suit:
            return bid(2, longest,
                       why=f"Weak two: 6 {longest.to_char()}, "
                           f"suit-HCP {suit_hcp}, "
                           f"{'vul' if am_vul else 'nvul'}")
        return None
    # 2nd-seat preempts (one passer before us) are tightened: LHO
    # hasn't acted yet but is more likely to have values than partner.
    # Q-Plus passes hands a 1st/3rd-seat preempter would open
    # (seed=200 board 1: E with 6 HCP + AQ-7th in diamonds passes
    # in 2nd seat). Cap HCP at 5 (vs 9) and require suit-HCP ≥ 5.
    is_second_seat = (state is not None
                      and getattr(state, "consecutive_passes", 0) == 1
                      and getattr(state, "opener_seat", None) is None)
    # 3-level preempt — 7-card suit, decent quality.
    if n == 7:
        if is_second_seat:
            if e.hcp <= 5 and suit_hcp >= 5:
                return bid(3, longest,
                           why=f"2nd-seat preempt: 7 {longest.to_char()}, "
                               f"≤5 HCP, suit-HCP {suit_hcp}")
            return None
        if 5 <= e.hcp <= 9 and suit_hcp >= 4:
            return bid(3, longest,
                       why=f"Preempt: 7 {longest.to_char()}, suit-HCP {suit_hcp}")
    # 4-level preempt — 8+ card suit. Plain 4-of-major when
    # the system DOESN'T have NAMYATS / Texas (otherwise the
    # NAMYATS check above the 1M opening handles 8+ major
    # hands).
    if n >= 8 and 4 <= e.hcp <= 8 and suit_hcp >= 3:
        return bid(4, longest,
                   why=f"Preempt: 8+ {longest.to_char()}")
    return None


# ---------------------------------------------------------------------------
# RKC Blackwood — keycard ask + response + king-ask follow-up
# ---------------------------------------------------------------------------

def _agreed_trump(state: 'AuctionState') -> Optional[Suit]:
    """Best guess at the trump suit implied by the auction so far.

    Used by the RKC machinery to decide whether a 4NT bid is keycard
    or natural / quantitative, and to count the trump king + queen
    against the player's hand.

    Heuristic: the last NATURAL suit either partner bid before the
    first 4NT. Every bid at or after 4NT is keycard machinery, not
    natural — without the cut-off the responder's `5♣ = 0/3 keys`
    answer would be misread as a club suit and the grand would be
    played in the wrong strain.

    This simple rule lines up with the trump suit in every common
    sequence we model:
      • `1H – 3H – 4NT`            → 3H → hearts
      • `1S – 2S – 4S – 4NT`       → 4S → spades
      • `1C – 1H – 4NT` (Precision) → 1H → hearts (1♣ is artificial)
      • `1NT – 2C – 2H – 3H – 4NT` → 3H → hearts
      • `1NT – 4NT`                → no suit bid → None (correctly
        classified as quantitative, NOT keycard)
    """
    trump = None
    for _seat, b in state.bids:
        if b.level == 4 and b.suit == Suit.NOTRUMP and not b.is_pass:
            break
        if (not b.is_pass and not b.is_double and not b.is_redouble
                and b.suit not in (None, Suit.NOTRUMP)):
            trump = b.suit
    return trump


def _is_rkc_context(state: 'AuctionState', for_bid: 'Bid') -> bool:
    """Should `for_bid` (must be 4NT) be read as RKC Blackwood?

    True when a trump suit can be inferred AND the auction has gone
    past the "natural NT" zone. False for opening NT, jump 2NT
    rebids, and quantitative slam invites — those are handled by
    other branches.
    """
    if not (for_bid.level == 4 and for_bid.suit == Suit.NOTRUMP):
        return False
    trump = _agreed_trump(state)
    if trump is None:
        # No trump fit → 4NT is quantitative.
        return False
    # If the auction has only had NT bids on our side (e.g. 1NT-4NT),
    # treat 4NT as quantitative — RKC needs a suit fit.
    side_bids = state.my_bids + state.partner_bids
    has_suit_bid = any(
        b.suit not in (None, Suit.NOTRUMP)
        and not b.is_pass and not b.is_double and not b.is_redouble
        for b in side_bids
    )
    return has_suit_bid


def _keycard_count(e: HandEval, trump: Optional[Suit],
                   system=None) -> int:
    """Number of "keys" held.

    For RKC variants (1430 / 0314): 4 aces + the trump king (5 keys).
    For classic Blackwood (`S-Blackwood.classic` flag set, e.g. in
    wbridge5's SAYC default): 4 aces only — the trump king isn't a
    key, since classic Blackwood asks for aces.
    """
    n = sum(1 for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
            if e.has_ace.get(s, False))
    classic = bool(system) and system.has("S-Blackwood.classic")
    if not classic and trump is not None and e.has_king.get(trump, False):
        n += 1
    return n


def _has_trump_queen(e: HandEval, trump: Optional[Suit]) -> bool:
    """True if we hold the trump queen, or 5+ trumps (length substitute)."""
    if trump is None:
        return False
    if e.has_queen.get(trump, False):
        return True
    # Length substitute — 5+ trumps with a top honour is usually
    # treated as queen for response purposes.
    return e.suit_lengths.get(trump, 0) >= 5


def _rkc_response_levels(variant: str) -> dict:
    """Map (keys, has_queen) → response level for the Blackwood variant.

    For classic ace-counting Blackwood (wbridge5's SAYC default,
    Bridge Baron's default, many home games): no trump queen, no
    trump king ambiguity — the responder just shows ace count.
      5♣ = 0 or 4 aces, 5♦ = 1, 5♥ = 2, 5♠ = 3.
    """
    if variant == "classic":
        # Queen flag is irrelevant; same step pair for either.
        return {
            (0, False): (5, Suit.CLUBS),    (4, False): (5, Suit.CLUBS),
            (0, True):  (5, Suit.CLUBS),    (4, True):  (5, Suit.CLUBS),
            (1, False): (5, Suit.DIAMONDS), (1, True):  (5, Suit.DIAMONDS),
            (2, False): (5, Suit.HEARTS),   (2, True):  (5, Suit.HEARTS),
            (3, False): (5, Suit.SPADES),   (3, True):  (5, Suit.SPADES),
        }
    if variant == "0314":
        # 5♣ = 0 or 3 keycards, 5♦ = 1 or 4 keycards.
        return {
            (0, False): (5, Suit.CLUBS),   (3, False): (5, Suit.CLUBS),
            (0, True):  (5, Suit.CLUBS),   (3, True):  (5, Suit.CLUBS),
            (1, False): (5, Suit.DIAMONDS),(4, False): (5, Suit.DIAMONDS),
            (1, True):  (5, Suit.DIAMONDS),(4, True):  (5, Suit.DIAMONDS),
        }
    # 1430 (default): 5♣ = 1 or 4 keycards, 5♦ = 0 or 3 keycards.
    return {
        (1, False): (5, Suit.CLUBS),   (4, False): (5, Suit.CLUBS),
        (1, True):  (5, Suit.CLUBS),   (4, True):  (5, Suit.CLUBS),
        (0, False): (5, Suit.DIAMONDS),(3, False): (5, Suit.DIAMONDS),
        (0, True):  (5, Suit.DIAMONDS),(3, True):  (5, Suit.DIAMONDS),
    }


def _respond_to_rkc(state: 'AuctionState', e: HandEval, system) -> Bid:
    """Partner just bid 4NT — answer with the key/ace count.

    Per-variant response steps:
      • classic Blackwood (ace-only): 5♣=0/4, 5♦=1, 5♥=2, 5♠=3.
      • 1430 RKC: 5♣=0/3, 5♦=1/4, 5♥=2 no Q, 5♠=2 with Q.
      • 0314 RKC: same as 1430 with 5♣/5♦ swapped.
    """
    trump = _agreed_trump(state)
    keys = _keycard_count(e, trump, system)
    has_q = _has_trump_queen(e, trump)
    variant = getattr(system, "rkc_variant", "1430") or "1430"
    levels = _rkc_response_levels(variant)

    # Classic Blackwood: never split on trump queen, never show the
    # 2/5-key special pair — the variant table covers all 0-3
    # answers directly.
    if variant == "classic":
        if (keys, has_q) in levels:
            lvl, suit = levels[(keys, has_q)]
            return bid(lvl, suit, alert=True,
                       why=f"Blackwood: {keys} aces")
        return bid(5, Suit.CLUBS, alert=True,
                   why=f"Blackwood: {keys} aces (fallback)")

    # 2 / 5 keys → 5♥ (no Q) or 5♠ (with Q) for RKC variants.
    if keys in (2, 5):
        if has_q:
            return bid(5, Suit.SPADES, alert=True,
                       why=f"RKC {variant}: {keys} keys + trump queen")
        return bid(5, Suit.HEARTS, alert=True,
                   why=f"RKC {variant}: {keys} keys, no trump queen")

    if (keys, has_q) in levels:
        lvl, suit = levels[(keys, has_q)]
        return bid(lvl, suit, alert=True,
                   why=f"RKC {variant}: {keys} keycards")

    return bid(5, Suit.CLUBS, alert=True,
               why=f"RKC {variant}: {keys} keys (fallback)")


def _parse_rkc_response(response: 'Bid', variant: str) -> Tuple[Optional[int], Optional[bool]]:
    """Decode a partner's RKC / Blackwood answer into (keys, has_queen).

    For classic Blackwood the queen flag is always None (irrelevant)
    and the count is unambiguous from the step alone (0/4, 1, 2, 3).
    """
    if variant == "classic":
        if response.suit == Suit.CLUBS and response.level == 5:
            return (0, None)        # ambiguous 0 vs 4 — disambiguate later
        if response.suit == Suit.DIAMONDS and response.level == 5:
            return (1, None)
        if response.suit == Suit.HEARTS and response.level == 5:
            return (2, None)
        if response.suit == Suit.SPADES and response.level == 5:
            return (3, None)
        return (None, None)
    if response.suit == Suit.CLUBS and response.level == 5:
        # 5C in 1430 = 1 or 4; in 0314 = 0 or 3. Caller picks the right
        # branch by hand strength.
        return (1, None) if variant == "1430" else (0, None)
    if response.suit == Suit.DIAMONDS and response.level == 5:
        return (0, None) if variant == "1430" else (1, None)
    if response.suit == Suit.HEARTS and response.level == 5:
        return (2, False)
    if response.suit == Suit.SPADES and response.level == 5:
        return (2, True)
    return (None, None)


def _resolve_rkc_keys(e: HandEval, state: 'AuctionState', resp: 'Bid',
                      variant: str) -> Tuple[int, Optional[bool]]:
    """Disambiguate 0/3 and 1/4 by hand strength.

    The asker sees partner's response and needs to decide whether the
    "0 or 3" / "1 or 4" pair points at the low or high number — based
    on how strong they perceive partner to be from the auction so far.
    Heuristic: did partner open OR limit-jump? Then take the high
    number. If partner passed initially or only made minimum positive
    responses, take the low number.
    """
    keys_lo, has_q = _parse_rkc_response(resp, variant)
    if keys_lo is None:
        return (0, has_q)
    if keys_lo == 2:
        return (2, has_q)

    partner = state.seat.partner()
    # Walk the raw bid stream up to the first 4NT so we only consider
    # natural bids by partner — every bid at or after 4NT is keycard
    # machinery (e.g. partner's `5♣` answer is NOT a 5-level natural
    # club bid).
    partner_first_was_pass = False
    partner_pre_bids = []
    seen_partner = False
    for s, b in state.bids:
        if b.level == 4 and b.suit == Suit.NOTRUMP and not b.is_pass:
            break
        if s != partner:
            continue
        if not seen_partner:
            seen_partner = True
            partner_first_was_pass = bool(b.is_pass)
        if not b.is_pass:
            partner_pre_bids.append(b)
    partner_opened = (state.opener_seat == partner)

    # If partner clearly showed opening values (opened, or made a
    # jump shift / 2NT response promising 11+), take the high number.
    high_signal = partner_opened
    for b in partner_pre_bids:
        # Jump responses (≥ 2NT or 3-level natural) imply ≥11 HCP.
        if (b.suit == Suit.NOTRUMP and b.level >= 2) or b.level >= 3:
            high_signal = True
            break
    if high_signal:
        return (keys_lo + 3, has_q)
    # Partner passed first or only made the minimum positive — keep low.
    return (keys_lo, has_q)


def _asker_after_rkc(state: 'AuctionState', e: HandEval, system) -> Bid:
    """I bid 4NT, partner responded with keycards — pick my next bid.

    Decision table:
      • Missing 2+ keys (≤ asker's keys + partner's keys < 3)
        → sign off in 5 of trump
      • All keys present, plus trump queen → 5NT king-ask
      • All keys, no queen confirmed → 6 of trump (or step to
        confirm grand with queen later)
      • Just enough keys for slam → 6 of trump
    """
    variant = getattr(system, "rkc_variant", "1430") or "1430"
    trump = _agreed_trump(state)
    if trump is None:
        return passb(why="No trump fit detected — RKC fallback pass")
    partner_resp = state.partner_bids[-1] if state.partner_bids else None
    if partner_resp is None:
        return passb(why="RKC asker — no response yet?")

    pk, pq = _resolve_rkc_keys(e, state, partner_resp, variant)
    my_keys = _keycard_count(e, trump, system)
    total = my_keys + pk
    have_q = _has_trump_queen(e, trump) or (pq is True)

    # Off two or more keys (or off 1 + missing queen): stop at 5.
    if total <= 2:
        return bid(5, trump, why=f"Off ≥2 keys ({total}/5) — sign off in 5{trump.to_char()}")
    if total == 3 and not have_q:
        return bid(5, trump, why="Off 2 keys + queen missing — sign off in 5")

    # 4+ keys + queen → king-ask via 5NT.
    if total >= 4 and have_q:
        return bid(5, Suit.NOTRUMP, alert=True,
                   why=f"RKC {variant}: {total}/5 keys + Q — asking for kings")

    # 4 keys, no queen confirmed → small slam.
    if total == 4:
        return bid(6, trump,
                   why=f"4/5 keys, queen unclear — small slam in {trump.to_char()}")

    # All 5 keys but queen still unclear — small slam is safe.
    return bid(6, trump,
               why=f"All 5 keys — small slam in {trump.to_char()}")


def _respond_to_king_ask(state: 'AuctionState', e: HandEval, system) -> Bid:
    """Partner bid 5NT (king-ask after RKC) — answer with kings.

    Standard Q-Plus / SAYC answers: count non-trump kings, signal
    via step bids.
      • 6 of trump  = 0 non-trump kings
      • 6♣ / 6♦ / 6♥ (the cheaper of the two side suits) = 1 king
      • 6 below trump = 2 kings (rare)
      • 7 of trump = all (3) kings
    Q-Plus's actual 5NT answers are slightly system-specific; this
    cheap-step style is the most common.
    """
    trump = _agreed_trump(state)
    if trump is None:
        return passb(why="No trump — can't answer king-ask")
    side_kings = [s for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
                  if s != trump and e.has_king.get(s, False)]
    n_kings = len(side_kings)
    if n_kings == 0:
        return bid(6, trump, why="King-ask: 0 side kings")
    if n_kings == 3:
        return bid(7, trump, why="King-ask: all 3 side kings → grand")
    # 1 / 2 — show the cheapest king. Any 6-level new-suit bid is
    # legal above 5NT regardless of suit rank vs trump, so there's
    # no "below trump" exit; we just walk C/D/H/S and pick the
    # first king we hold (excluding trump, which was already
    # counted as a keycard).
    rank_order = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]
    for s in rank_order:
        if s in side_kings:
            return bid(6, s, alert=True,
                       why=f"King-ask: showing {s.to_char()} king "
                           f"({n_kings} total)")
    return bid(6, trump, why="King-ask: no side kings to show")


def _asker_after_king_response(state: 'AuctionState', e: HandEval, system) -> Bid:
    """I bid 5NT (king-ask), partner answered — pick small vs grand.

    With all keys + trump queen on side and partner showing at least
    one king, the source-of-tricks usually exists for 7. With 0
    kings shown (partner returned to 6 of trump), settle for 6.
    """
    trump = _agreed_trump(state)
    if trump is None:
        return passb(why="No trump after king-ask")
    resp = state.partner_bids[-1] if state.partner_bids else None
    if resp is None:
        return passb()
    # Partner returned to 6 of trump = 0 side kings → small slam.
    if resp.level == 6 and resp.suit == trump:
        return passb(why="0 side kings — small slam stands")
    # Partner showed a king (6 of new suit) or grand (7 of trump).
    if resp.level == 7:
        return passb(why="Partner already at grand")
    # Showed a king → grand if we have a source of tricks (long suit
    # + ace + trump queen).
    has_source = (
        e.suit_lengths.get(trump, 0) >= 5
        or any(e.suit_lengths.get(s, 0) >= 5
               and e.has_ace.get(s, False)
               for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS))
    )
    if has_source and _keycard_count(e, trump, system) >= 2:
        return bid(7, trump, why=f"Side king shown + source of tricks → 7{trump.to_char()}")
    return bid(6, trump, why=f"Side king shown but no clear source → 6{trump.to_char()}")


def _try_rkc_pipeline(state: 'AuctionState', e: HandEval, system) -> Optional[Bid]:
    """Hook for decide_bid: handle every step of the RKC follow-up.

    Returns a Bid if the auction state matches one of:
      • partner bid 4NT in an RKC context (I'm responding)
      • I bid 4NT and partner answered (I'm reading)
      • partner bid 5NT king-ask (I'm responding)
      • I bid 5NT and partner answered (I'm reading)
    Otherwise returns None and decide_bid falls through.
    """
    # Most recent partner bid + most recent my bid.
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    last_mine = state.my_bids[-1] if state.my_bids else None

    # Pre-flight: an intervening opponent double / overcall reshapes
    # RKC into DEPO / DOPI; for now we just punt to natural bidding
    # so we don't mis-fire. RKC handles only the no-interference case.
    if state.opp_overcalled and state.rho_bids:
        last_opp = state.rho_bids[-1]
        if not last_opp.is_pass:
            return None

    # Case 1: partner just bid 4NT → I respond with keycards.
    if last_partner is not None and _is_rkc_context(state, last_partner):
        # Make sure I haven't already responded.
        if not last_mine or last_mine.level < 4 \
                or (last_mine.level == 4 and last_mine.suit != Suit.NOTRUMP):
            return _respond_to_rkc(state, e, system)

    # Case 2: I bid 4NT, partner gave the keycard answer → my move.
    if last_mine is not None and _is_rkc_context(state, last_mine):
        if last_partner is not None and last_partner.level == 5 \
                and last_partner.suit in (Suit.CLUBS, Suit.DIAMONDS,
                                          Suit.HEARTS, Suit.SPADES):
            return _asker_after_rkc(state, e, system)

    # Case 3: partner bid 5NT after an RKC sequence → I show kings.
    if (last_partner is not None and last_partner.level == 5
            and last_partner.suit == Suit.NOTRUMP):
        if _agreed_trump(state) is not None and last_mine is not None \
                and last_mine.level == 5:
            return _respond_to_king_ask(state, e, system)

    # Case 4: I bid 5NT king-ask → partner answered, I read it.
    if (last_mine is not None and last_mine.level == 5
            and last_mine.suit == Suit.NOTRUMP):
        if last_partner is not None and last_partner.level in (6, 7):
            return _asker_after_king_response(state, e, system)

    return None


# ---------------------------------------------------------------------------
# Top-level decide
# ---------------------------------------------------------------------------

def _is_legal_bid(b: Bid, state: AuctionState) -> bool:
    """Return True if `b` is a legal call at this point in the auction.

    Mirrors the legality check the diff harness uses — bids must
    strictly outrank the last suit bid, doubles need a non-pass /
    non-doubled bid behind them, redoubles need a double behind them.
    """
    if b is None or b.is_pass:
        return True
    if b.is_double:
        last = next((x for _s, x in reversed(state.bids)
                     if not x.is_pass), None)
        return (last is not None
                and not last.is_double and not last.is_redouble)
    if b.is_redouble:
        last = next((x for _s, x in reversed(state.bids)
                     if not x.is_pass), None)
        return last is not None and last.is_double
    if b.suit is None:
        return False
    if b.level < 1 or b.level > 7:
        return False
    last_suit = next((x for _s, x in reversed(state.bids)
                      if not x.is_pass and not x.is_double
                      and not x.is_redouble), None)
    if last_suit is None:
        return True
    if b.level > last_suit.level:
        return True
    if b.level == last_suit.level:
        return _BID_RANK[b.suit] > _BID_RANK[last_suit.suit]
    return False


def _partner_was_forcing(state: AuctionState) -> bool:
    """Detect a force partner just placed on us. Conservative — only
    returns True for unambiguous forcing sequences so the sanity
    wrapper doesn't fire on debatable cases.

      * Partner's 2/1 GF response: I opened 1-of-major, partner bid
        2-of-new-suit. Auction is game-forcing.
      * Partner's reverse: partner showed extras by bidding a
        higher-ranked suit at the 2-level after their 1-level open.
      * Partner's splinter: alerted jump to 3+ in a new suit after
        my opening.
      * Partner's jump-shift: jump in new suit at responder's turn.
    """
    if not state.partner_bids:
        return False
    pl = state.partner_bids[-1]
    if pl.is_pass or pl.is_double or pl.is_redouble:
        return False
    op = state.opening_bid
    if op is None:
        return False

    # Partner's 2/1 GF response (their first call is 2-of-new over
    # my 1-of-major opening).
    if (len(state.partner_bids) == 1
            and pl.level == 2
            and pl.suit is not None
            and pl.suit != Suit.NOTRUMP
            and state.opener_seat == state.seat
            and op.level == 1
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and pl.suit != op.suit):
        return True

    # Partner's reverse (their second call, higher-ranked suit at
    # level 2, after a level-1 response by me).
    if (len(state.partner_bids) >= 2
            and pl.level == 2
            and pl.suit is not None
            and pl.suit != Suit.NOTRUMP
            and state.partner_bids[0].suit is not None
            and state.partner_bids[0].suit != Suit.NOTRUMP
            and pl.level > state.partner_bids[0].level
            and _BID_RANK[pl.suit] > _BID_RANK[state.partner_bids[0].suit]):
        return True

    # Splinter: alerted jump in a new suit (level ≥ 3, not partner's
    # earlier suit).
    if (pl.alert and pl.level >= 3
            and pl.suit is not None
            and pl.suit != Suit.NOTRUMP
            and pl.suit not in [b.suit for b in state.partner_bids[:-1]
                                if b.suit is not None]):
        return True

    return False


def _safe_forced_bid(state: AuctionState, eval_: HandEval,
                     system) -> Optional[Bid]:
    """Pick a conservative continuation when we shouldn't pass.

    Preference order: raise partner's suit if I have 3+ support;
    rebid my own 5+ suit; 2NT/3NT if balanced; cuebid opener's
    suit if competitive; last-resort cheapest legal level of my
    own suit or 3NT.
    """
    pl = state.partner_bids[-1]
    last_level = state.last_level or 1
    last_suit = state.last_suit_bid

    def _cheapest_legal_level(target: Suit) -> int:
        if last_suit is None:
            return 1
        if _BID_RANK[target] > _BID_RANK[last_suit]:
            return last_level
        return last_level + 1

    # Raise partner's last suit with 3+ support.
    if (pl.suit is not None and pl.suit != Suit.NOTRUMP
            and eval_.suit_lengths.get(pl.suit, 0) >= 3):
        lvl = _cheapest_legal_level(pl.suit)
        if lvl <= 4:
            cand = bid(lvl, pl.suit, why="Sanity: raise partner's suit")
            if _is_legal_bid(cand, state):
                return cand

    # Rebid own 5+ card suit.
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if eval_.suit_lengths[s] >= 5:
            lvl = _cheapest_legal_level(s)
            if lvl <= 4:
                cand = bid(lvl, s, why=f"Sanity: rebid {s.to_char()}")
                if _is_legal_bid(cand, state):
                    return cand

    # Balanced → NT at the cheapest legal level (NT outranks all suits).
    if eval_.is_balanced or eval_.is_semi_balanced:
        target_level = max(2, last_level)
        if (last_suit == Suit.NOTRUMP) and target_level == last_level:
            target_level += 1
        if target_level <= 3:
            cand = bid(target_level, Suit.NOTRUMP,
                       why="Sanity: balanced NT")
            if _is_legal_bid(cand, state):
                return cand

    # Last resort: 3NT.
    cand = bid(3, Suit.NOTRUMP, why="Sanity: last-resort 3NT")
    if _is_legal_bid(cand, state):
        return cand

    return None


def _legalize(b: Bid, state: AuctionState) -> Optional[Bid]:
    """If `b` is an illegal suit bid, return the cheapest legal bid
    in the same suit — but ONLY if the upgrade is by at most one
    level. Wider gaps usually mean the underlying bidder produced a
    stale call (rebidding a preempt long after the auction moved on);
    upgrading those would just commit us to a meaningless slam-level
    contract. Caller passes instead.
    """
    if b is None or b.is_pass or b.suit is None or b.suit == Suit.NOTRUMP:
        return None
    if b.is_double or b.is_redouble:
        return None
    last_suit = next((x for _s, x in reversed(state.bids)
                      if not x.is_pass and not x.is_double
                      and not x.is_redouble), None)
    if last_suit is None:
        return b if _is_legal_bid(b, state) else None
    if (b.level == last_suit.level
            and _BID_RANK[b.suit] > _BID_RANK[last_suit.suit]):
        return b
    new_level = last_suit.level + (
        0 if _BID_RANK[b.suit] > _BID_RANK[last_suit.suit] else 1)
    if new_level > 7:
        return None
    if new_level - b.level > 1:
        return None     # Don't sky-rocket stale preempts.
    upgraded = bid(new_level, b.suit,
                   why=f"{b.explanation} [legalized from "
                       f"{b.level}{b.suit.to_char()}]")
    return upgraded if _is_legal_bid(upgraded, state) else None


def _sanity_wrap(raw: Bid, state: AuctionState, eval_: HandEval,
                 system) -> Bid:
    """Catch pathological output from `_decide_bid_impl` and substitute.

    Two pathologies are handled:

      1. **Illegal bid** — typically a stale 2-level call that
         doesn't outrank partner's intervening jump. We upgrade to
         the cheapest legal level in the same suit.

      2. **Pass when a force is in effect** — partner just made a
         GF call (2/1, reverse, splinter, jump shift) and the
         rule-based bidder fell through to pass. We pick a
         conservative continuation in `_safe_forced_bid`.

    Returns the (possibly substituted) bid. Never raises; on any
    internal error returns `raw` unchanged so the wrapper can't
    make the engine crashier than it already is.
    """
    try:
        # 1. Illegality
        if not _is_legal_bid(raw, state):
            legalized = _legalize(raw, state)
            if legalized is not None:
                raw = legalized
            else:
                # Can't recover — fall back to pass and let the
                # next check decide whether that's also wrong.
                raw = passb(why=f"Sanity: illegal {raw} → pass")

        # 2. Pass-when-forced
        if raw.is_pass and _partner_was_forcing(state):
            sub = _safe_forced_bid(state, eval_, system)
            if sub is not None:
                return sub

        return raw
    except Exception:
        # Defensive — never raise from the wrapper.
        return raw


def decide_bid(state: AuctionState, eval_: HandEval, system) -> Bid:
    """Public entry point — calls the rule-based bidder, then runs a
    sanity wrapper that catches obvious pathological output before it
    leaves the engine. See `_sanity_wrap` for the specific patterns
    we override.
    """
    raw = _decide_bid_impl(state, eval_, system)
    return _sanity_wrap(raw, state, eval_, system)


def _decide_bid_impl(state: AuctionState, eval_: HandEval, system) -> Bid:
    """Dispatch to the right decision function based on auction state.

    `system` is a `BiddingSystem` from `bidding_systems`. String inputs
    are accepted for backwards compatibility (resolved via `get_system`).
    """
    from .bidding_systems import BiddingSystem, get_system
    if not isinstance(system, BiddingSystem):
        system = get_system(system)
    # First call by anyone → opening
    if state.opener_seat is None:
        return open_bid(eval_, system=system, state=state)

    # Auction has already gone three passes after a bid → it's over
    if state.last_non_pass is None:
        return passb()
    if state.consecutive_passes >= 3 and state.last_non_pass[0] != state.seat:
        return passb()

    # RKC follow-up — check before the normal opener/responder/overcall
    # dispatch so 4NT → 5x → 5NT → 6x → 7y all stay inside the slam
    # machinery instead of falling back into natural rebid logic.
    rkc = _try_rkc_pipeline(state, eval_, system)
    if rkc is not None:
        return rkc

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
        # Unbalanced 11-12 with 5+ diamonds (singleton or void) —
        # raise diamonds rather than misrepresent as balanced 2NT.
        # Seed=300 board 8 E (Q98 T KQJ752 A82, 12 HCP, 3-1-6-3)
        # belongs in a diamond raise, not 2NT.
        if (e.suit_lengths[Suit.DIAMONDS] >= 5
                and (e.singletons > 0 or e.voids > 0)):
            return bid(2, Suit.DIAMONDS,
                       why="Precision 1D: 11-12 constructive raise "
                           "(5+ diamonds, unbalanced)")
        return bid(2, Suit.NOTRUMP, why="Precision 1D: 11-12 invitational")
    if 13 <= hcp <= 15:
        # Balanced 13-15 with no shortage → 3NT (cheap game, 9 tricks
        # vs 11 for 5♦). Only raise diamonds when shape demands it.
        if (e.suit_lengths[Suit.DIAMONDS] >= 4
                and not e.is_balanced
                and not e.is_semi_balanced):
            return bid(3, Suit.DIAMONDS,
                       why="Precision 1D: 13-15 unbalanced + diamond fit")
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

    has_4S = e.suit_lengths[Suit.SPADES] == 4
    has_4H = e.suit_lengths[Suit.HEARTS] == 4
    has_5S = e.suit_lengths[Suit.SPADES] >= 5
    has_5H = e.suit_lengths[Suit.HEARTS] >= 5

    # Garbage Stayman (Q-Plus `A-1NT-Garbage-Stayman`): with a weak 4-4
    # in the majors and a short minor, bid 2♣ planning to pass any
    # response — improves on 1NT in 4-4-x-x shape. Precision70 enables
    # this; 2/1 / SAYC do not.
    if (hcp <= t["pass_max"] and has_4S and has_4H
            and system.has("A-1NT-Garbage-Stayman")):
        short = min(e.suit_lengths[Suit.CLUBS], e.suit_lengths[Suit.DIAMONDS])
        if short <= 2:
            return bid(2, Suit.CLUBS, alert=True,
                       why="Garbage Stayman: weak 4-4 majors, plan to pass")

    # 0-pass_max with no long major → just pass.
    if hcp <= t["pass_max"] and not e.five_card_majors:
        return passb(why=f"0-{t['pass_max']} HCP, no 4cM/5cM → pass 1NT")

    # Jacoby transfers (always — every Q-Plus system flips this on)
    if has_5H or has_5S:
        # Texas: 6+ in a major with game values goes straight to game.
        # Both Texas and SA-Texas use 4♦/4♥ as the transfer — the
        # SA-Texas distinction only matters for opener's responses, not
        # responder's bid here, so a single gate covers both.
        if (system.has("A-1NT-transfer-level-4.Texas")
                or system.has("A-1NT-transfer-level-4.SA-Texas")):
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

    # 1NT-2♠ → minor-suit transfer to clubs (Q-Plus
    # `A-1NT-Jacoby-minor.spades-for-clubs`), used in Precision90P.
    if (hcp <= t["invite_lo"]
            and e.suit_lengths[Suit.CLUBS] >= 6
            and system.has("A-1NT-Jacoby-minor.spades-for-clubs")):
        return bid(2, Suit.SPADES, alert=True,
                   why="Minor-suit transfer to clubs (6+ ♣)")

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
            # Escape to a long MAJOR (5+ S or H) with a weak hand —
            # diamonds-only weak hands sit the double (Q-Plus's
            # Precision90M default behaviour matches this).
            if hcp <= 7:
                for suit in (Suit.SPADES, Suit.HEARTS):
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
    # Pre-emptive raise (Law of Total Tricks):
    #   * 4+ trumps → raise with up to 12 HCP (9+ total trumps, safe).
    #   * 3 trumps → only raise with a weak hand (≤ 9 HCP); with
    #     10-12 HCP and 3-card support Q-Plus prefers to pass and
    #     let opener struggle rather than push the opps to game.
    if fit >= 4 and hcp <= 12:
        return bid(3, suit, why="Preemptive raise: 4+ trumps")
    if fit == 3 and hcp <= 9:
        return bid(3, suit, why="Preemptive raise: 3 trumps, weak")
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
    hcp = e.hcp

    # 16+ HCP + 1-card+ heart/spade preempt → game raise.
    if fit >= 1 and hcp >= 16 and suit in (Suit.HEARTS, Suit.SPADES):
        return bid(4, suit, why="Game raise of preempt")

    # 16+ HCP balanced with a stopper in every UNBID suit → 3NT.
    # Partner's preempt suit doesn't need a stopper (they have 7+
    # of it). This was the previous code's catch-all; restrict it
    # to "balanced AND stoppers everywhere else."
    if hcp >= 16 and (e.is_balanced or e.is_semi_balanced):
        unbid = [s for s in (Suit.CLUBS, Suit.DIAMONDS,
                             Suit.HEARTS, Suit.SPADES)
                 if s != suit]
        if all(_has_stopper(e, s) for s in unbid):
            return bid(3, Suit.NOTRUMP, why="3NT after preempt: "
                                            "16+ balanced, stoppers")

    # 17+ HCP, own 6+ major → bid the major (forcing, partner can
    # support with 3+ or correct back to opener's suit).
    if hcp >= 17:
        for m in (Suit.SPADES, Suit.HEARTS):
            if m == suit:
                continue
            if e.suit_lengths[m] >= 6:
                # Cheapest legal level above the preempt.
                level = (op.level
                         if _BID_RANK[m] > _BID_RANK[suit]
                         else op.level + 1)
                return bid(level, m,
                           why=f"{level}{m.to_char()}: 17+ HCP, "
                               f"6+ {m.to_char()}")

    # 18+ HCP + minor preempt + partner can probably make 5m: just
    # raise to game. Without a 6-card major or a balanced hand to
    # bid 3NT, this is the only constructive call. 5m needs enough
    # offence in the combined hands — 18 HCP from the responder
    # opposite a 7-card preempt with one outside trick is normally
    # enough.
    if (hcp >= 18 and suit in (Suit.CLUBS, Suit.DIAMONDS)
            and fit >= 1):
        return bid(5, suit, why=f"5{suit.to_char()}: 18+ HCP, raise "
                                 "preempt to minor game")

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
                and 8 <= hcp <= 12):
            # Q-Plus Precision90M uses Truscott 2NT broadly — any
            # 4+ support raise from 8 HCP up, not just the textbook
            # 10-12 "limit raise". With 4-card+ trump fit and an
            # opening-value-hand-but-not-game-going, this is the
            # preferred response over a redouble.
            return bid(2, Suit.NOTRUMP, alert=True,
                       why=f"Truscott 2NT: 4+ {minor.to_char()} "
                           f"raise (8-12)")
        # XX or new bid; default to redouble with 10+
        if hcp >= 10:
            return Bid(is_redouble=True, explanation="Redouble: 10+ HCP")
        return passb()
    if overcall_suit is None:  # NT overcall — treat as natural
        return _respond_to_minor(state, e, system)
    # Negative double, valid through the system's Sputnik cap
    # (SAYC: 2♠, Precision 90M: 3♠). What the double promises
    # depends on the overcall suit:
    #
    #   * Overcall in a MAJOR (1H / 1S) → 4+ in the *other* major.
    #     (After 1m-1H the doubler shows 4+ spades; after 1m-1S
    #     they show 4+ hearts and not enough to bid 2♥.)
    #   * Overcall in the OTHER minor (1m-2m / 2m-3m) → 4+ in each
    #     unbid major. (Two suits to imply, only one bid available.)
    neg_max = _negative_double_max_level(system)
    can_neg_dbl = False
    if overcall.level <= neg_max and hcp >= 6:
        if overcall_suit == Suit.HEARTS:
            can_neg_dbl = (e.suit_lengths[Suit.SPADES] >= 4)
        elif overcall_suit == Suit.SPADES:
            can_neg_dbl = (e.suit_lengths[Suit.HEARTS] >= 4)
        elif overcall_suit in (Suit.CLUBS, Suit.DIAMONDS):
            can_neg_dbl = (e.suit_lengths[Suit.HEARTS] >= 4
                           and e.suit_lengths[Suit.SPADES] >= 4)
    if can_neg_dbl:
        return double(
            why=f"Negative double (Sputnik ≤{neg_max})")
    # Bid an unbid major. Forcing strength depends on the system AND
    # the actual level we'd have to bid at (which the overcall may
    # have already pushed past the 1 level).
    #   * Default (SAYC): new-suit-at-2-level after overcall = forcing
    #     for one round (5+ in the suit, 10+ HCP).
    #   * `C-negative-free-bid` (Precision 90M): same call at the
    #     2-level = NON-forcing (5+, 8-10 HCP). With game values the
    #     bidder cuebids or jumps instead.
    nfb = system.has("C-negative-free-bid")
    for m in (Suit.HEARTS, Suit.SPADES):
        if m != overcall_suit and e.suit_lengths[m] >= 5:
            # Lowest legal level for a new-suit call above the current
            # contract. _BID_RANK orders C<D<H<S<NT, so a higher-ranked
            # suit at the same level is enough; otherwise bump one level.
            if (state.last_suit_bid is None
                    or _BID_RANK[m] > _BID_RANK[state.last_suit_bid]):
                level = state.last_level
            else:
                level = state.last_level + 1
            if level <= 1:
                return bid(level, m,
                           why="1-level new-suit overcall response (forcing)")
            # Independent shortcut: 6+ card major + game values →
            # just bid 4M directly. Don't waste a round on a
            # cuebid when partner can't possibly have a better
            # contract than 4-of-my-major in a 7-card+ fit. This
            # catches hands like 14-HCP / 7-hearts where the NFB
            # cuebid path would otherwise sign off too low.
            if e.suit_lengths[m] >= 6 and hcp >= 13:
                return bid(4, m,
                           why=f"4{m.to_char()}: 6+ {m.to_char()}, "
                               f"game values, no need to cuebid")
            # 5-card major + game values + a legal natural call
            # below the cuebid level: bid the suit (forcing). E.g.
            # 1D-(3D)-? holding ♠AKQxx and 14 HCP, bid 3S not 4D.
            # The cuebid (4D over a 3-level preempt) wastes a level
            # when we have a natural game-going call available.
            if (e.suit_lengths[m] >= 5
                    and hcp >= 13
                    and level <= overcall.level):
                return bid(level, m,
                           why=f"Forcing {level}{m.to_char()}: 5+ "
                               f"with game values (preferred over cuebid)")
            # 2-level new suit — branch on NFB.
            if nfb:
                if 8 <= hcp <= 10:
                    return bid(level, m, alert=True,
                               why="Negative free bid (8-10, 5+ in suit, "
                                   "NON-forcing)")
                if hcp >= 13:
                    # Cuebid for forcing-to-game (game values + no fit
                    # to raise opener).
                    return bid(overcall.level + 1, overcall_suit, alert=True,
                               why="Cuebid: game-forcing values (NFB system)")
                # 11-12 doesn't have a clean rebid; fall through to other paths.
            else:
                # Standard system — 2-level new suit is forcing.
                return bid(level, m,
                           why=f"Forcing {level}{m.to_char()} "
                               "in unbid major")
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
        # Jacoby 2NT: 4+ support, GF (13+ HCP). Only fire when the
        # system has the convention enabled — wbridge5's SAYC has
        # "2NT Jacoby" unchecked, so for SAYC-wbridge5 a 13+ balanced
        # hand with 4+ trumps either splinters (handled above) or
        # leaps to game.
        if hcp >= 13 and system.has("A-1MA-Jacoby-2NT"):
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Jacoby 2NT: 4+ support, GF")
        # 17+ HCP with 4+ support is slam-interest territory. Jumping
        # to 4M would kill the auction — preserve room by bidding 2/1
        # in the longest 5+ side suit first, then bring up the major
        # support later (or take control via Blackwood).
        if hcp >= 17:
            for s in (Suit.CLUBS, Suit.DIAMONDS):
                if e.suit_lengths[s] >= 5 and s != major:
                    return bid(2, s, alert=True,
                               why=f"2-over-1 GF in 5+{s.to_char()} "
                                   f"(slam try, 4+{major.to_char()})")
            if (major == Suit.SPADES
                    and e.suit_lengths[Suit.HEARTS] >= 5):
                return bid(2, Suit.HEARTS, alert=True,
                           why="2-over-1 GF in 5+H "
                               "(slam try, 4+S)")
        # Without Jacoby 2NT and no 5+ side suit for a 2/1, a
        # 4+-trump hand with 13+ HCP and no shortness settles for
        # 4M and lets opener evaluate for slam from extras.
        if hcp >= 13:
            return bid(4, major,
                       why=f"4+{major.to_char()} game raise "
                           f"(no Jacoby 2NT)")
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
        # Precision-family 2NT as 3-card limit raise. Q-Plus's
        # Precision Club 90 modern encodes this via
        # `A-1MA-2NT.support-3-10-13`; SAYC etc. keep the
        # natural 3M jump.
        if (10 <= hcp <= 13
                and system.has("A-1MA-2NT.support-3-10-13")):
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Precision: 2NT = 3-card limit raise (10-13)")
        if 10 <= hcp <= 12:
            return bid(3, major, why="3-card limit raise")
        # Truscott 3NT (Q-Plus `A-1MA-Truscott-3NT.always`): 1M-3NT shows
        # a balanced 13-15 with exactly 3-card support, no shortness —
        # opener can pass with a flat-15-ish hand or correct to 4M.
        # Precision90M enables this; SAYC/2/1 do not.
        if (13 <= hcp <= 15
                and e.is_balanced
                and system.has("A-1MA-Truscott-3NT.always")):
            return bid(3, Suit.NOTRUMP, alert=True,
                       why="Truscott 3NT: 13-15 balanced, 3-card support")
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

def _precision_1c_rebid(state, e: HandEval, p_last: Bid, system=None) -> Bid:
    """Opener's rebid after 1C-X (Precision strong club).

    1D negative (0-7):
        1H/1S = natural 5+ in suit, 16-21 unbalanced
        1NT   = 16-19 balanced
        2C    = natural 6+ clubs, 16-21
        2D    = natural 5+ diamonds, 16-21
        2H    = Q-Plus's Kokish (`B-strong-artificial.with-Kokish`):
                ambiguous between 22-23 balanced and 5+ hearts 16-19;
                responder relays 2♠ to ask, opener clarifies (2NT =
                balanced, 3-suit = hearts with feature, 3♥ = min hearts)
        2NT   = 22-24 balanced (only when Kokish is NOT in use; with
                Kokish the 22-23 hand goes through the 2♥ relay first)
        3-of-suit jump shift = stronger
        3NT   = 25+ balanced

    Positive responses (1H, 1S, 2C, 2D, 1NT, 2NT, 3NT) — auction is GF;
    raise partner's suit with support, otherwise show shape.
    """
    hcp = e.hcp
    kokish = bool(system) and system.has("B-strong-artificial.with-Kokish")

    # Negative response: 1D = 0-7
    if p_last.level == 1 and p_last.suit == Suit.DIAMONDS:
        # Kokish 2♥: ambiguous bid (real hearts 16-19 OR balanced 22-23).
        # Catches BOTH hand types; responder will relay with 2♠ and we
        # disambiguate in the second rebid round.
        if kokish:
            real_hearts = (e.suit_lengths[Suit.HEARTS] >= 5
                           and 16 <= hcp <= 19
                           and not e.is_balanced)
            strong_bal = (e.is_balanced and 22 <= hcp <= 23)
            if real_hearts or strong_bal:
                return bid(2, Suit.HEARTS, alert=True,
                           why="Kokish 2♥: 5+ hearts (16-19) OR "
                               "22-23 balanced; partner relays 2♠")

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

    # Kokish continuation: after 1C-1D-2H-2S relay, opener now clarifies.
    # By the time we land here the auction history looks like:
    #   my_bids   = [1C, 2H]   (mine, in order)
    #   partner_bids = [1D, 2S]
    # so the relay-confirmation rebid happens when p_last is 2S AND
    # we already bid 2H AND Kokish is in force.
    if (kokish and p_last.level == 2 and p_last.suit == Suit.SPADES
            and any(b.level == 2 and b.suit == Suit.HEARTS
                    for b in state.my_bids)
            and any(b.level == 1 and b.suit == Suit.DIAMONDS
                    for b in state.partner_bids)):
        # 22-23 balanced arm → 2NT.
        if e.is_balanced and 22 <= hcp <= 23:
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Kokish clarification: 22-23 balanced "
                           "(2NT shows it wasn't real hearts)")
        # Real-hearts arm (16-19 unbal). With 18+ HCP and an outside
        # A/K feature, bid 3-of-side-suit showing the feature;
        # otherwise 3♥ as a minimum (16-17).
        if e.suit_lengths[Suit.HEARTS] >= 5 and 16 <= hcp <= 19:
            if hcp >= 18:
                for side in (Suit.SPADES, Suit.DIAMONDS, Suit.CLUBS):
                    if e.suit_hcp.get(side, 0) >= 3 and e.suit_lengths.get(side, 0) >= 2:
                        return bid(3, side, alert=True,
                                   why=f"Kokish: real hearts (18-19) with "
                                       f"{side.to_char()} feature")
            return bid(3, Suit.HEARTS,
                       why="Kokish: real hearts, minimum (16-17)")

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
    op = state.opening_bid

    if not state.partner_bids:
        # Partner has only passed so far. When opps overcalled AND
        # advanced into a fit, opener with extras + shortness in
        # their suit should reopen with a takeout double — partner
        # may be sitting on a trap pass or a hand too good to act
        # earlier. Otherwise, the auction dies here.
        if state.rho_bids:
            opp_suit = None
            for b in reversed(state.rho_bids + state.lho_bids):
                if b.suit is not None and b.suit != Suit.NOTRUMP:
                    opp_suit = b.suit
                    break
            if (opp_suit is not None
                    and e.suit_lengths.get(opp_suit, 0) <= 2
                    and e.hcp >= 13):
                return double(why=f"Reopening X: 13+ HCP, short in "
                                  f"opps' {opp_suit.to_char()}")
        return passb()

    p_last = state.partner_bids[-1]

    # Precision-specific opener rebids run before the SAYC paths.
    if getattr(system, "strong_open_call", "2C") == "1C":
        # 1C strong: structured rebids over partner's 1D negative or
        # positive response.
        if op.level == 1 and op.suit == Suit.CLUBS:
            return _precision_1c_rebid(state, e, p_last, system)
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

    # Weak 2♥/2♠ opener — partner's 2NT inquiry. Use Ogust matrix if
    # the spec flags it, otherwise feature-showing.
    if op.level == 2 and op.suit in (Suit.HEARTS, Suit.SPADES) \
            and p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
        return _weak_two_2nt_rebid(state, e, op, system)

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


def _weak_two_2nt_rebid(state, e: HandEval, op: Bid, system) -> Bid:
    """Weak-2 opener's rebid after partner's 2NT inquiry.

    Q-Plus systems pick one of two conventions:

      * Ogust (`A-2MA-2NT.Ogust-5-A`, Precision 90M): 4-step matrix
        encoding (hand strength, suit strength).
            3♣ = bad hand (6-8 HCP), bad suit (Q-high or worse)
            3♦ = bad hand, good suit (AK or AQJ headed)
            3♥ = good hand (9-11 HCP), bad suit
            3♠ = good hand, good suit
            3NT = AKQ solid in the bid suit
        (Q-Plus's "5-A" variant uses 3 of the major as one of the
        codes; we collapse to 3♣/3♦/3♥/3♠/3NT for legibility.)
      * Feature-showing (SAYC `A-2MA-2NT.feature-showing`):
        3-of-a-side-suit with an A or K outside, rebid the major
        with a minimum and no feature.
    """
    hcp = e.hcp
    suit = op.suit
    # Suit-quality score: 4 if AKQ/AKJ-headed, 2 for AQ/KQ/KJ-headed,
    # 0 otherwise. Real Ogust grades on the suit's playing strength.
    suit_hcp = e.suit_hcp.get(suit, 0)
    good_suit = suit_hcp >= 6  # AK = 7, AQ = 6, KQ = 5 → use >= 6 as gate.
    solid_aks = suit_hcp >= 9  # AKQ = 9

    if system.has("A-2MA-2NT.Ogust-5-A"):
        if solid_aks:
            return bid(3, Suit.NOTRUMP, alert=True,
                       why=f"Ogust: AKQ solid in {suit.to_char()}")
        if hcp <= 8 and not good_suit:
            return bid(3, Suit.CLUBS, alert=True,
                       why="Ogust: bad hand, bad suit (6-8 HCP)")
        if hcp <= 8 and good_suit:
            return bid(3, Suit.DIAMONDS, alert=True,
                       why="Ogust: bad hand, good suit (6-8 HCP)")
        if hcp >= 9 and not good_suit:
            return bid(3, Suit.HEARTS, alert=True,
                       why="Ogust: good hand, bad suit (9-11 HCP)")
        return bid(3, Suit.SPADES, alert=True,
                   why="Ogust: good hand, good suit (9-11 HCP)")

    # Feature-showing (SAYC default).
    if hcp >= 9:
        # Look for an outside Ax / Kxx feature to advertise.
        for side in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
            if side == suit:
                continue
            sh = e.suit_hcp.get(side, 0)
            sl = e.suit_lengths.get(side, 0)
            if (sh >= 4 and sl >= 1) or (sh >= 3 and sl >= 2):  # Ax or Kxx
                return bid(3, side, alert=True,
                           why=f"Feature in {side.to_char()} (Ax/Kxx)")
    # No feature OR minimum → rebid the major.
    return bid(3, suit, why=f"No feature / minimum, rebid {suit.to_char()}")


def _opener_suit_rebid(state, e, op, p_last, system) -> Bid:
    op_suit = op.suit

    # NMF follow-up: I already replied to partner's NMF, and now
    # partner has invited (2NT) or signed off (2 of a major / 3 of
    # a major). Accept the invitation with max (13-14) or sign off
    # with minimum (12).
    if (system.has("G-new-minor-forcing")
            and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
            and len(state.my_bids) >= 3
            and state.my_bids[1].level == 1
            and state.my_bids[1].suit == Suit.NOTRUMP
            and len(state.partner_bids) >= 3):
        # Partner's invitation: 2NT (no fit found)
        if p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
            if e.hcp >= 13:
                return bid(3, Suit.NOTRUMP, why="NMF: accept invite (max)")
            return passb(why="NMF: decline invite (min)")
        # Partner's invitation: 3 of partner's major (after NMF showed
        # 3-card support and partner is inviting game)
        if (p_last.level == 3
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and state.partner_bids[0].suit == p_last.suit):
            if e.hcp >= 13:
                return bid(4, p_last.suit, why="NMF: accept inv to 4M (max)")
            return passb(why="NMF: pass 3M invite (min)")

    # New Minor Forcing reply. If my previous rebid was 1NT and partner
    # now bids 2 of the OTHER minor, partner is asking about majors:
    #   * 2 of partner's major  = exactly 3-card support
    #   * 2 of other major      = 4 cards there (no 3-card support)
    #   * 2NT                   = minimum, no fit
    #   * 3 of partner's major  = max + 3-card support
    #   * 3NT                   = max, no fit
    nmf_minor = (Suit.CLUBS if op_suit == Suit.DIAMONDS
                 else (Suit.DIAMONDS if op_suit == Suit.CLUBS else None))
    if (system.has("G-new-minor-forcing")
            and nmf_minor is not None
            and len(state.my_bids) >= 2
            and state.my_bids[1].level == 1
            and state.my_bids[1].suit == Suit.NOTRUMP
            and len(state.partner_bids) >= 2
            and state.partner_bids[0].suit in (Suit.HEARTS, Suit.SPADES)
            and state.partner_bids[0].level == 1
            and p_last.level == 2
            and p_last.suit == nmf_minor):
        partner_major = state.partner_bids[0].suit
        other_major = (Suit.SPADES if partner_major == Suit.HEARTS
                       else Suit.HEARTS)
        is_max = e.hcp >= 14
        if e.suit_lengths.get(partner_major, 0) >= 3:
            level = 3 if is_max else 2
            return bid(level, partner_major, alert=True,
                       why=f"NMF reply: 3-card support for "
                           f"{partner_major.to_char()}"
                           f"{', max' if is_max else ''}")
        if e.suit_lengths.get(other_major, 0) >= 4:
            return bid(2, other_major, alert=True,
                       why=f"NMF reply: 4 {other_major.to_char()}, "
                           f"no 3-card {partner_major.to_char()} support")
        if is_max:
            return bid(3, Suit.NOTRUMP, alert=True,
                       why="NMF reply: max, no major fit")
        return bid(2, Suit.NOTRUMP, alert=True,
                   why="NMF reply: minimum, no major fit")

    # Partner raised our suit
    if p_last.suit == op_suit:
        if p_last.level == 2:
            # Simple raise → 6-9. Pass with min, invite with 17, jump with 18+.
            if e.hcp <= 14:
                return passb()
            if 15 <= e.hcp <= 17:
                # Trial bid (`G-trial-bid.long-suit`): instead of a
                # generic 3M game try, bid 3 of a side suit where we
                # need help (4+ cards, ≤ 1 honor). Partner accepts
                # with cover (A, K, or shortness); declines otherwise.
                # The bid must stay below 3 of the trump suit.
                if (system.has("G-trial-bid.long-suit")
                        and op_suit in (Suit.HEARTS, Suit.SPADES)):
                    for side in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS):
                        if side == op_suit:
                            continue
                        if (e.suit_lengths.get(side, 0) >= 4
                                and e.suit_hcp.get(side, 0) <= 2):
                            # Need a help-suit BELOW our trump in rank,
                            # so the trial bid stays under 3M.
                            if _BID_RANK[side] < _BID_RANK[op_suit]:
                                return bid(3, side, alert=True,
                                           why=f"Trial bid: help in "
                                               f"{side.to_char()} for "
                                               f"3{op_suit.to_char()}")
                return bid(3, op_suit, why="Game try (15-17)")
            return bid(4, op_suit, why="To-play game (18+)")
        if p_last.level == 3:  # limit raise
            if e.hcp <= 13:
                return passb()
            return bid(4, op_suit, why="Accept limit raise")
        if p_last.level == 4:  # weak preemptive
            return passb()

    # Partner's Truscott 2NT after 1m-(X) — 4+ trump support, 8-12
    # HCP. Sign off in 3m with minimum, raise to game with extras.
    rho_or_lho_doubled = any(
        b.is_double for b in state.rho_bids + state.lho_bids)
    if (p_last.level == 2 and p_last.suit == Suit.NOTRUMP
            and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
            and system.has("A-1MI-Truscott-2NT")
            and rho_or_lho_doubled):
        if e.hcp <= 14:
            return bid(3, op_suit,
                       why=f"Truscott 2NT signoff: 3{op_suit.to_char()} "
                           "(minimum)")
        if e.hcp <= 16:
            return bid(4, op_suit,
                       why=f"Truscott 2NT accept: 4{op_suit.to_char()} "
                           "(extras)")
        # 17+ — push to game in NT or 5m.
        if e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why="Truscott 2NT extras: 3NT")
        return bid(5, op_suit,
                   why=f"Truscott 2NT extras: 5{op_suit.to_char()}")

    # Partner's 1NT response (6-9 / 6-12 if 1M opening)
    if p_last.level == 1 and p_last.suit == Suit.NOTRUMP:
        if e.is_balanced and 12 <= e.hcp <= 14:
            return passb()
        if e.is_balanced and 15 <= e.hcp <= 17:
            return bid(2, Suit.NOTRUMP, why="15-17 NT rebid")
        if e.is_balanced and e.hcp >= 18:
            return bid(3, Suit.NOTRUMP, why="18-19 NT rebid")
        # Show second suit if 5-4 or longer (lower-ranked, no reverse).
        # `e.second_suit is not None` — `if e.second_suit:` is wrong:
        # `Suit.SPADES` has enum value 0 which is falsy, so any 4-card
        # spade second suit silently skipped this branch.
        if (e.second_suit is not None
                and _BID_RANK[e.second_suit] < _BID_RANK[op_suit]):
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
        # Precision-style 3-card raise of partner's major. In
        # Precision Club 90 the 1D opening is a catch-all 11-15
        # without 5cM, so opener with exactly 3-card support and
        # minimum prefers to raise immediately rather than rebid
        # 1NT or a 4-card minor. SAYC and 2/1 keep the strict 4+
        # rule.
        if (getattr(system, "strong_open_call", "2C") == "1C"
                and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths[p_last.suit] == 3
                and 12 <= e.hcp <= 14
                and not state.rho_bids):
            return bid(2, p_last.suit,
                       why=f"Precision 3-card raise of partner's "
                           f"{p_last.suit.to_char()} (minimum)")
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
        # Bid second suit. Test `is not None` rather than truthy —
        # Suit.SPADES.value == 0 (falsy), so `if e.second_suit:`
        # silently skipped this branch for any 4-card spade side suit.
        if e.second_suit is not None:
            target = e.second_suit
            # If we can show the second suit at the 1-LEVEL (target
            # is between partner's response and opener's suit in
            # rank), do that — it's the natural call for hands like
            # 1m-1H-1S showing 4 spades, opening hand. Previously
            # only 2-level rebids of the side suit were considered.
            if (p_last.level == 1
                    and _BID_RANK[target] > _BID_RANK[p_last.suit]
                    and _BID_RANK[target] > _BID_RANK[op_suit]
                    and _BID_RANK[target] < _BID_RANK[Suit.NOTRUMP]):
                return bid(1, target,
                           why=f"1{target.to_char()}: 4+ side suit "
                               f"shown at 1-level")
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
        # 5-4-2-2 fall-through: opener couldn't show the second suit
        # (would be a reverse) and has nothing else. The standard
        # "best lie" with 12-14 HCP is a 1NT rebid — Q-Plus does
        # this and so should we. Only legal when partner's response
        # was at the 1-level.
        if 12 <= e.hcp <= 14 and p_last.level == 1:
            return bid(1, Suit.NOTRUMP,
                       why="Best-lie 1NT rebid (12-14, awkward 5-4-2-2-ish shape)")
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

    # Partner bid a NEW major at the 3-level in a competitive auction
    # (e.g. 1m-(3m)-3M, regardless of whether the preempt came from
    # LHO or RHO). Standard agreement: partner's 3M is a forcing free
    # bid showing 5+ in the major and game values opposite the preempt.
    # Opener with 2+ support raises to game; balanced 12+ with stoppers
    # tries 3NT.
    opp_3level_preempt = any(
        b.level >= 3 and b.suit is not None and b.suit != Suit.NOTRUMP
        and b.suit != p_last.suit
        for b in (state.rho_bids + state.lho_bids))
    if (p_last.level == 3
            and p_last.suit is not None
            and p_last.suit in (Suit.HEARTS, Suit.SPADES)
            and p_last.suit != op_suit
            and opp_3level_preempt):
        new_major = p_last.suit
        if e.suit_lengths.get(new_major, 0) >= 2:
            return bid(4, new_major,
                       why=f"4{new_major.to_char()}: support partner's "
                           "forcing 3-level overcall")
        if e.is_balanced and e.hcp >= 12:
            return bid(3, Suit.NOTRUMP,
                       why="3NT after partner's 3-level forcing")
        return bid(4, new_major,
                   why=f"4{new_major.to_char()}: token raise of forcing 3M")

    # Partner's 2-level new-suit bid (typically a 2/1 GF response,
    # or a 1m-then-2M/1M-then-2m sequence). Opener MUST describe.
    # Each candidate rebid is gated on legality (must outrank
    # partner's 2-level bid, since p_last is at level 2).
    if p_last.level == 2 and p_last.suit is not None and p_last.suit != Suit.NOTRUMP:
        # Helper: is a 2-level bid in `suit` legal here?
        def _legal_two(s: Suit) -> bool:
            return _BID_RANK[s] > _BID_RANK[p_last.suit]
        # 6-card original suit, rebid at the 2 level if legal,
        # else at the 3 level (showing extras / good 6-bagger).
        if e.suit_lengths[op_suit] >= 6:
            if _legal_two(op_suit):
                return bid(2, op_suit, why="6-card opener suit rebid")
            return bid(3, op_suit, why="6-card opener suit rebid (3-level forced)")
        # Second suit at the 2-level — legal only when it ranks
        # both BELOW op_suit and ABOVE partner's last bid.
        if (e.second_suit is not None
                and _BID_RANK[e.second_suit] < _BID_RANK[op_suit]
                and _legal_two(e.second_suit)):
            return bid(2, e.second_suit, why="Second suit (2-level)")
        # 5+ in original suit, 2-level rebid if legal (forcing-1
        # in 2/1 GF context). Otherwise jump-rebid at 3-level.
        if e.suit_lengths[op_suit] >= 5:
            if _legal_two(op_suit):
                return bid(2, op_suit,
                           why=f"Rebid 5+{op_suit.to_char()} (2/1 GF)")
            return bid(3, op_suit,
                       why=f"Rebid 5+{op_suit.to_char()} at 3-level")
        # Balanced rebid 2NT (forcing in 2/1 context). 2NT
        # outranks every suit so always legal here.
        if e.is_balanced:
            return bid(2, Suit.NOTRUMP, why="2NT (balanced rebid in 2/1)")
        # Higher-ranked second suit at the 3-level (jump-shift /
        # reverse), needs extras.
        if (e.second_suit is not None
                and _BID_RANK[e.second_suit] > _BID_RANK[op_suit]
                and e.hcp >= 17):
            return bid(3, e.second_suit,
                       why="Reverse / 3-level second suit (17+ HCP)")
        # Last resort: rebid op_suit at the 3-level.
        return bid(3, op_suit, why="Rebid (constructive)")

    return passb()


# ---------------------------------------------------------------------------
# Responder's rebid
# ---------------------------------------------------------------------------

def _responder_rebid(state, e: HandEval, system) -> Bid:
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

    # Kokish 2♠ relay: after Precision 1♣-1♦-2♥ with Kokish in force,
    # responder MUST bid 2♠ regardless of own hand. Opener's next bid
    # clarifies whether 2♥ was real hearts or 22-23 balanced.
    if (system.has("B-strong-artificial.with-Kokish")
            and op.level == 1 and op.suit == Suit.CLUBS
            and len(state.my_bids) >= 1
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit == Suit.DIAMONDS
            and p_last.level == 2 and p_last.suit == Suit.HEARTS):
        return bid(2, Suit.SPADES, alert=True,
                   why="Kokish forced relay (asks opener: real hearts "
                       "or 22-23 balanced?)")

    # If partner showed extras, drive to game; if min, settle
    return _generic_responder_rebid(state, e, p_last, system)


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
            # 17+ HCP with a 4-4 major fit and a 14-16 partner → 31+
            # combined, slam is on. Skip the 4M signoff and ask via
            # Blackwood directly; the responder-rebid pipeline takes
            # over from there.
            if hcp >= 17:
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"Blackwood: slam try, 4-4 {major.to_char()} "
                               "fit found via Stayman, 17+ HCP")
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


def _nmf_responder_rebid(state, e, opener_rebid, my_major, system):
    """Responder's rebid after opener's reply to NMF 2-of-other-minor.

    Opener's reply (per `G-new-minor-forcing`):
      * 2 of partner's major  → exactly 3-card support
      * 2 of the OTHER major  → 4 cards in that major (no 3 in
        partner's major)
      * 2NT                    → minimum (12-13), no fit found
      * 3 of partner's major  → 3-card support + max (14)
      * 3NT                    → max (13-14) + no fit
    """
    hcp = e.hcp
    other_major = (Suit.SPADES if my_major == Suit.HEARTS else Suit.HEARTS)
    # Opener showed 3-card support for my major
    if opener_rebid.suit == my_major:
        if opener_rebid.level == 3:  # max + fit
            return bid(4, my_major, why="NMF: max+fit → game")
        # Level 2: minimum with 3-card support; invite or accept.
        if hcp >= 13:
            return bid(4, my_major, why="NMF accept: 13+ HCP")
        return bid(3, my_major, why="NMF inv: 11-12, 5+ in major, opener min")
    # Opener showed 4 cards in the OTHER major
    if opener_rebid.suit == other_major and opener_rebid.level == 2:
        if e.suit_lengths.get(other_major, 0) >= 4:
            return bid(4, other_major,
                       why=f"NMF: 4-4 fit in {other_major.to_char()}")
        # No fit in the other major — settle in 3NT.
        if hcp >= 12:
            return bid(3, Suit.NOTRUMP, why="NMF: no fit, game values")
        return bid(2, Suit.NOTRUMP, why="NMF: no fit, invitational")
    # Opener showed no fit (2NT or 3NT)
    if opener_rebid.suit == Suit.NOTRUMP:
        if opener_rebid.level == 2:
            # Minimum: with 12+ → 3NT, otherwise pass.
            if hcp >= 12:
                return bid(3, Suit.NOTRUMP, why="NMF: no fit, game values")
            return passb()
        return passb()  # opener already at 3NT — to-play.
    # Fallback (shouldn't happen in well-formed NMF responses).
    return passb()


def _generic_responder_rebid(state, e, opener_rebid, system=None):
    hcp = e.hcp
    op = state.opening_bid

    # If my first bid was 2-of-the-OTHER-minor over partner's 1m-1M-1NT,
    # I was in NMF. Opener has now described — bid the followup.
    if (system is not None
            and system.has("G-new-minor-forcing")
            and op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and len(state.my_bids) >= 2
            and state.my_bids[0].suit in (Suit.HEARTS, Suit.SPADES)
            and state.my_bids[0].level == 1):
        my_major = state.my_bids[0].suit
        my_nmf = state.my_bids[1]
        nmf_minor = (Suit.CLUBS if op.suit == Suit.DIAMONDS else Suit.DIAMONDS)
        if (my_nmf.level == 2 and my_nmf.suit == nmf_minor):
            return _nmf_responder_rebid(state, e, opener_rebid,
                                        my_major, system)

    # Opener rebid 1NT (12-14) — NMF inquiry or settle.
    if opener_rebid.level == 1 and opener_rebid.suit == Suit.NOTRUMP:
        if hcp <= 7:
            return passb()
        # New Minor Forcing (2 of the unbid minor) — invitational+
        # with a 5-card major or 4-4 majors, asks opener for fit. After
        # 1m-1M-1NT, NMF bid is 2 of the OTHER minor.
        nmf_available = (
            system is not None
            and system.has("G-new-minor-forcing")
            and op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and state.my_bids
            and state.my_bids[-1].level == 1
            and state.my_bids[-1].suit in (Suit.HEARTS, Suit.SPADES)
        )
        if nmf_available and hcp >= 11 and (
                e.suit_lengths.get(state.my_bids[-1].suit, 0) >= 5
                or (e.suit_lengths[Suit.SPADES] >= 4
                    and e.suit_lengths[Suit.HEARTS] >= 4)):
            nmf_minor = (Suit.CLUBS if op.suit == Suit.DIAMONDS
                         else Suit.DIAMONDS)
            return bid(2, nmf_minor, alert=True,
                       why=f"New Minor Forcing 2{nmf_minor.to_char()}: "
                           "11+ HCP, asks about majors")
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

    # 2/1 GF auction: opener rebid their major at the 2-level (min, 5+ in major).
    # With 4+ trump support and slam-interest values, launch RKC; otherwise
    # close in the 4-of-major game. Without trump support the auction is
    # still GF — describe with a side suit, NT, or rebid own suit.
    if (opener_rebid.level == 2
            and opener_rebid.suit == op.suit
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and len(state.my_bids) >= 1
            and state.my_bids[0].level == 2
            and state.my_bids[0].suit != op.suit):
        my_first_suit = state.my_bids[0].suit
        fit = e.suit_lengths.get(op.suit, 0)
        if fit >= 4:
            if hcp >= 17:
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"Blackwood: slam try, 4+{op.suit.to_char()} "
                               f"support, opener showed 5+")
            if hcp >= 13:
                return bid(4, op.suit,
                           why=f"4{op.suit.to_char()}: game in known fit")
            return passb()
        # 2/1 GF without major support — continue the auction.
        #   * 4+ in the OTHER major (not opener's, not first 2/1 suit) →
        #     bid it at the 2 or 3 level (legality permitting).
        #   * 6+ in my first suit → rebid it.
        #   * 12+ balanced with stopper(s) → 2NT / 3NT.
        #   * fallback: 3 of my first suit.
        other_major = (Suit.SPADES if op.suit == Suit.HEARTS
                       else Suit.HEARTS)
        if (other_major != my_first_suit
                and e.suit_lengths.get(other_major, 0) >= 4
                and _BID_RANK[other_major] > _BID_RANK[op.suit]):
            return bid(2, other_major,
                       why=f"2{other_major.to_char()}: 4-card side suit (GF)")
        if e.suit_lengths.get(my_first_suit, 0) >= 6:
            return bid(3, my_first_suit,
                       why=f"3{my_first_suit.to_char()}: rebid 6+ own suit")
        if e.is_balanced and hcp >= 12:
            return bid(2, Suit.NOTRUMP,
                       why="2NT (balanced, 2/1 GF context)")
        if e.suit_lengths.get(my_first_suit, 0) >= 5:
            return bid(3, my_first_suit,
                       why=f"3{my_first_suit.to_char()}: rebid 5+ own suit")
        return bid(3, Suit.NOTRUMP,
                   why="3NT (last-resort 2/1 GF game)")

    # 2/1 GF auction: opener rebid a NEW suit at the 2-level. The
    # auction is still game-forcing — never pass below game. Only
    # applies after a 1-of-a-suit opening; after 1NT the "2/1" is
    # actually a Stayman / Jacoby transfer and the auction is NOT
    # forcing once opener accepts.
    if (op.suit != Suit.NOTRUMP
            and opener_rebid.level == 2
            and opener_rebid.suit is not None
            and opener_rebid.suit != Suit.NOTRUMP
            and opener_rebid.suit != op.suit
            and len(state.my_bids) >= 1
            and state.my_bids[0].level == 2
            and state.my_bids[0].suit is not None
            and state.my_bids[0].suit != Suit.NOTRUMP
            and state.my_bids[0].suit != op.suit):
        my_suit = state.my_bids[0].suit
        new_suit = opener_rebid.suit
        # 4+ in opener's new suit + game values → raise to game
        if e.suit_lengths.get(new_suit, 0) >= 4 and hcp >= 13:
            return bid(4, new_suit,
                       why=f"4{new_suit.to_char()}: 4-card fit in opener's "
                           "new suit")
        # 12+ balanced → 3NT (most common 2/1 GF stop)
        if e.is_balanced and hcp >= 12:
            return bid(3, Suit.NOTRUMP,
                       why="3NT in 2/1 GF: balanced, no major fit")
        # Long own suit → rebid it
        if e.suit_lengths.get(my_suit, 0) >= 6:
            return bid(3, my_suit,
                       why=f"3{my_suit.to_char()}: rebid 6+ own suit")
        # Preference to opener's first suit
        if e.suit_lengths.get(op.suit, 0) >= 2:
            return bid(3, op.suit,
                       why=f"3{op.suit.to_char()}: preference to opener")
        return bid(3, Suit.NOTRUMP,
                   why="3NT in 2/1 GF (last-resort game)")

    # 1M-1NT-2X (non-GF): opener rebid a new suit at the 2-level
    # after responder's 1NT (6-9, no major fit). With 4+ support
    # for the new suit, raise it — game-invitational with 8-10 HCP,
    # game with 11+, sign off at 2-of-new with weak hands.
    if (opener_rebid.level == 2
            and opener_rebid.suit is not None
            and opener_rebid.suit != Suit.NOTRUMP
            and opener_rebid.suit != op.suit
            and len(state.my_bids) >= 1
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit == Suit.NOTRUMP):
        new_suit = opener_rebid.suit
        if e.suit_lengths.get(new_suit, 0) >= 4:
            if hcp >= 11:
                return bid(4, new_suit,
                           why=f"4{new_suit.to_char()}: 4+ fit + game values")
            if hcp >= 8:
                return bid(3, new_suit,
                           why=f"3{new_suit.to_char()}: invitational raise")
            return bid(2, new_suit,
                       why=f"2{new_suit.to_char()}: 4-card preference, weak")
        # No 4-card fit — show preference for opener's first suit if 2+
        if e.suit_lengths.get(op.suit, 0) >= 2 and hcp <= 7:
            return bid(2, op.suit,
                       why=f"2{op.suit.to_char()}: preference, weak")
        # Fall through to other handling

    # Opener showed a NEW suit at the 1-level (typically 1m-1M-1S,
    # showing 4 spades and opener's range without a fit yet).
    # Responder's options:
    #   * Raise opener's new suit (3+ support) at the appropriate
    #     level by strength.
    #   * Rebid own 5+ suit at the 2-level (6-9) or 3-level (10-12).
    #   * 1NT (6-9 balanced), 2NT (11-12 inv), 3NT (13+ balanced).
    if (opener_rebid.level == 1
            and opener_rebid.suit is not None
            and opener_rebid.suit != Suit.NOTRUMP
            and opener_rebid.suit != op.suit
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit is not None
            and state.my_bids[0].suit != Suit.NOTRUMP):
        new_major = opener_rebid.suit
        my_first_suit = state.my_bids[0].suit
        # Raise opener's new suit with 4+ support.
        if e.suit_lengths.get(new_major, 0) >= 4:
            if hcp >= 13:
                return bid(4, new_major,
                           why=f"4{new_major.to_char()}: 13+ HCP, "
                               f"4-card {new_major.to_char()} fit")
            if hcp >= 10:
                return bid(3, new_major,
                           why=f"3{new_major.to_char()}: 10-12 inv, "
                               f"4-card {new_major.to_char()} fit")
            if hcp >= 6:
                return bid(2, new_major,
                           why=f"2{new_major.to_char()}: 6-9, simple "
                               f"raise of partner's new suit")
        # Rebid own 5+ suit at the 2-level on minimum.
        if e.suit_lengths.get(my_first_suit, 0) >= 5 and hcp <= 9:
            return bid(2, my_first_suit,
                       why=f"2{my_first_suit.to_char()}: 6-9, rebid "
                           "own 5-card suit")
        # 2NT (11-12) or 3NT (13+) with values, no fit.
        if hcp >= 13:
            return bid(3, Suit.NOTRUMP, why="3NT: game values, no fit")
        if hcp >= 11:
            return bid(2, Suit.NOTRUMP, why="2NT: 11-12 inv, no fit")
        if hcp >= 6:
            return bid(1, Suit.NOTRUMP, why="1NT: 6-9, no fit")
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

    # Penalty double: 15+ HCP, no singleton/void (covers balanced
    # 4-3-3-3 / 4-4-3-2 / 5-3-3-2 and the semi-balanced 5-4-2-2 /
    # 6-3-2-2). `is_semi_balanced` is narrowly defined as 5-3-3-2;
    # widen here so a strong 5-4-2-2 still penalty-doubles 1NT.
    if hcp >= 15 and e.voids == 0 and e.singletons == 0:
        return double(why=f"Penalty double of 1NT ({hcp} HCP, no short suit)")

    # Landy 2♣ — both majors, at least 4-4, competitive values.
    # Landy 2♣ — both majors. Q-Plus uses 9-12 HCP at 4-4 (with
    # 13+ HCP a defender prefers to sit 1NT for penalty rather
    # than push to the 2-level). 5-4 hands keep the 9-14 range.
    landy_4_4 = (e.suit_lengths[Suit.HEARTS] == 4
                 and e.suit_lengths[Suit.SPADES] == 4)
    landy_hcp_max = 12 if landy_4_4 else 14
    if (system.has("O-1NT.Landy")
            and e.suit_lengths[Suit.HEARTS] >= 4
            and e.suit_lengths[Suit.SPADES] >= 4
            and 9 <= hcp <= landy_hcp_max):
        return bid(2, Suit.CLUBS, alert=True,
                   why="Landy: both majors (4+/4+, 9-15 HCP)")

    # Natural 2-level overcall with a 6-card suit and modest values.
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS):
        if e.suit_lengths[s] >= 6 and 9 <= hcp <= 15:
            return bid(2, s, why=f"Natural 2{s.to_char()} overcall (6+ cards)")

    # Preemptive 3-level overcall with a 7+ card suit. Strong club
    # holding like AKxxxxx is plenty against a 1NT — the offence
    # is concentrated and opener's NT shape suggests we're not
    # walking into shortness.
    for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        if (e.suit_lengths[s] >= 7
                and e.suit_hcp[s] >= 4
                and 6 <= hcp <= 14):
            return bid(3, s,
                       why=f"Preemptive 3{s.to_char()} overcall "
                           f"(7+ cards) over 1NT")

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


def _overcall_over_preempt(state, e: HandEval, system) -> Bid:
    """Compete over RHO's 3-level (or 4-level minor) preempt.

    Range is wider than over a 1-level opening — we're forcing
    partner to the 4-level on the takeout, so we need extras:

      • Double (takeout) — 15+ HCP, 0-2 cards in opener's suit,
        3+ cards in every unbid suit. The pre-existing 12-HCP
        threshold over 1-level openers is too light here: partner
        is forced to the 4-level and could be holding a 5-count
        with no fit. 15+ is the standard SAYC / Q-Plus minimum
        for a 3-level takeout double.
      • Suit overcall — 6+ card suit with 14+ HCP. Lower-suited
        overcalls jump to the next bid above the preempt.
      • 3NT — 16-19 balanced with stoppers in opener's suit.
      • Otherwise pass and hope partner protects.

    Doesn't try to model NS / EW vulnerability adjustments yet —
    a pass at unfavourable is still the right call most of the
    time and the bidder is conservative enough to default that
    way without an explicit vul-aware tweak.
    """
    op = state.opening_bid
    hcp = e.hcp
    opener_suit = op.suit
    unbid = [s for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
             if s != opener_suit]

    # 3NT — balanced 16-19 with stoppers in opener's suit (one stopper
    # for a 7-card preempt is the standard ask, two is safer).
    if (16 <= hcp <= 19 and e.is_balanced
            and _has_stopper(e, opener_suit)):
        return bid(3, Suit.NOTRUMP, why="3NT overcall: 16-19 balanced, stopper")

    # Natural overcall in a long suit at the level forced by the preempt.
    # Prefer the major to the minor, the longer suit to the shorter,
    # and require at least a decent suit (HCP ≥ 7 within the suit, or
    # a 7-card holding).
    best_suit = None
    best_score = -1
    for s in unbid:
        length = e.suit_lengths[s]
        suit_hcp = e.suit_hcp[s]
        if length < 6:
            continue
        if hcp < 14:
            continue
        if suit_hcp < 7 and length < 7:
            continue
        # Score: length first, then suit hcp, then "majors preferred".
        is_major = 1 if s in (Suit.HEARTS, Suit.SPADES) else 0
        score = length * 100 + suit_hcp * 10 + is_major
        if score > best_score:
            best_score = score
            best_suit = s
    if best_suit is not None:
        # Suit overcall must be high enough to be legal above the preempt.
        # 3♣ → 3♦+ legal; 3♠ → 4♣+ legal; 4♣ → 4♦+ legal.
        if _BID_RANK[best_suit] > _BID_RANK[opener_suit]:
            level = op.level
        else:
            level = op.level + 1
        return bid(level, best_suit,
                   why=f"{level}{best_suit.to_char()} overcall over "
                       f"{op.level}{opener_suit.to_char()} preempt")

    # Takeout double — three flavours, looser as HCP go up:
    #   • Strict (15+): ≤2 in opener's suit, ≥3 in every unbid suit.
    #   • Strong (17+): ≤3 in opener's suit, 4+ cards in some major,
    #     ≥2 in every other unbid suit. Covers a 17-HCP 1-5-4-3 with
    #     a small club stopper where natural overcall and 3NT both
    #     misfire — passing such a hand misses too many cold games.
    #   • Big (20+): ≤3 in opener's suit, no other shape requirement.
    #     With 20+ HCP we double and trust partner; sitting for a
    #     3-level preempt with that much would be a worse error.
    # Over a 4-level preempt we add 3 HCP to every threshold since
    # partner is now committed to the 4-level on the takeout.
    bonus = 3 if op.level == 4 else 0
    short_in_op = e.suit_lengths[opener_suit]

    def _has_4_in_a_major():
        return any(e.suit_lengths[m] >= 4
                   and m != opener_suit
                   for m in (Suit.HEARTS, Suit.SPADES))

    if (hcp >= 15 + bonus
            and short_in_op <= 2
            and all(e.suit_lengths[s] >= 3 for s in unbid)):
        return double(why=f"Takeout double of {op.level}{opener_suit.to_char()} preempt")
    if (hcp >= 17 + bonus
            and short_in_op <= 3
            and _has_4_in_a_major()):
        # 17+ HCP with a 4+ major and short in opener's suit. We don't
        # demand support in every unbid suit — with a 1-5-4-3 shape
        # partner will almost always pick the longer major when we
        # double clubs lacking spade length.
        return double(why=f"Strong takeout X of {op.level}{opener_suit.to_char()} "
                          f"({hcp} HCP, can't pass)")
    if hcp >= 20 + bonus and short_in_op <= 3:
        return double(why=f"Big-hand takeout X of {op.level}{opener_suit.to_char()} "
                          f"({hcp} HCP)")

    return passb(why=f"No safe action over {op.level}{opener_suit.to_char()} preempt")


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

    # 3-level and 4-level preempts (suit). The action is takeout
    # double with opening values + shortness, 3NT with stoppers,
    # or a strong suit overcall. Handled BEFORE the "level == 1
    # only" early-return so a 3♣ / 3♦ / 3♥ / 3♠ / 4♣ / 4♦ preempt
    # actually reaches an evaluator.
    if op.level in (3, 4) and op.suit in (Suit.CLUBS, Suit.DIAMONDS,
                                          Suit.HEARTS, Suit.SPADES):
        return _overcall_over_preempt(state, e, system)

    # Defensive doubles of strong 2♣ / 2♦ openings (`O-strong-2C…` /
    # `O-strong-2D…`, Precision 90M / 90P): handled here BEFORE the
    # 1-level-only early-return so a level-2 strong opening still
    # reaches the X. 5-5 majors with 8-15 HCP only — otherwise pass.
    if (op.level == 2 and op.suit == Suit.CLUBS
            and system.has("O-strong-2C.dbl-is-majors")
            and e.suit_lengths[Suit.HEARTS] >= 5
            and e.suit_lengths[Suit.SPADES] >= 5
            and 8 <= hcp <= 15):
        return double(why="Defensive X of strong 2♣ — both majors (5-5+)")
    if (op.level == 2 and op.suit == Suit.DIAMONDS
            and system.has("O-strong-2D.dbl-is-majors")
            and e.suit_lengths[Suit.HEARTS] >= 5
            and e.suit_lengths[Suit.SPADES] >= 5
            and 8 <= hcp <= 15):
        return double(why="Defensive X of strong 2♦ — both majors (5-5+)")

    if not (op.level == 1 and op.suit is not None and op.suit != Suit.NOTRUMP):
        return passb()

    # Sandwich 1NT (`O-Sandwich.nt-artificial`): 4th-seat overcall after
    # opener (one minor) + partner-passed + opener's-partner-responded
    # (a major). Our 1NT shows the two unbid suits (unusual NT shape)
    # rather than a natural 15-18 stopper — natural NT is suicidal when
    # both opponents have shown values.
    #
    # parse_auction's convention puts the opener in `lho_bids` and the
    # responder in `rho_bids` (since the auction goes opener → my
    # partner → responder → me clockwise). So the responder's bid is
    # what we check for the trigger major.
    if (system.has("O-Sandwich.nt-artificial")
            and op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and state.rho_bids
            and not state.rho_bids[-1].is_pass
            and state.rho_bids[-1].suit in (Suit.HEARTS, Suit.SPADES)):
        # Unbid suits are the unbid minor and the unbid major.
        unbid_minor = (Suit.DIAMONDS if op.suit == Suit.CLUBS
                       else Suit.CLUBS)
        unbid_major = (Suit.SPADES if state.rho_bids[-1].suit == Suit.HEARTS
                       else Suit.HEARTS)
        if (e.suit_lengths[unbid_minor] >= 5
                and e.suit_lengths[unbid_major] >= 5
                and 8 <= hcp <= 14):
            return bid(1, Suit.NOTRUMP, alert=True,
                       why=f"Sandwich 1NT: 5-5 in {unbid_major.to_char()}"
                           f"+{unbid_minor.to_char()}")

    # ---- Conventional shape-bids run BEFORE natural overcalls so they're
    # not pre-empted by the suit-overcall path. ----

    # Strong-1♣ defensive double (`O-strong-1C.dbl-is-majors`):
    # both majors at the table. 5-5 with 8+ HCP, or 4-4 with 11+
    # HCP (opening values) — Q-Plus on seed=200 board 2 X's with
    # 4-4 majors + 11 HCP (QJ53 K863 Q92 K5). Only fire on our
    # FIRST action — we'd otherwise re-X every round.
    if (op.suit == Suit.CLUBS and op.level == 1
            and system.has("O-strong-1C.dbl-is-majors")
            and not state.my_bids
            and 8 <= hcp <= 15):
        hl = e.suit_lengths[Suit.HEARTS]
        sl = e.suit_lengths[Suit.SPADES]
        five_five = (hl >= 5 and sl >= 5)
        four_four_plus_values = (hl >= 4 and sl >= 4 and hcp >= 11)
        if five_five or four_four_plus_values:
            return double(why="Defensive X of strong 1♣ — both majors")

    # Two-suiter cuebid — Michaels (SAYC) or Ghestem (Precision 90M).
    # Both use the same call (2 of opener's suit) for the same hand
    # type (5-5 in the highest unbid pair); Ghestem additionally
    # repurposes 3♣ for the high+low unbid pair, which the next block
    # handles. The label changes so Claude / the opponents know which
    # agreement is in force.
    twos_label = "Ghestem" if system.has("O-Ghestem.standard") else "Michaels"
    if op.suit in (Suit.CLUBS, Suit.DIAMONDS):
        # Over a minor → both majors (highest unbid pair).
        if (e.suit_lengths[Suit.HEARTS] >= 5
                and e.suit_lengths[Suit.SPADES] >= 5
                and 8 <= hcp <= 16):
            return bid(2, op.suit, alert=True,
                       why=f"{twos_label}: 5-5 majors")
    if op.suit in (Suit.HEARTS, Suit.SPADES):
        # Over a major → other major + an unspecified minor (5-5).
        other_major = Suit.SPADES if op.suit == Suit.HEARTS else Suit.HEARTS
        if e.suit_lengths[other_major] >= 5 and 8 <= hcp <= 16:
            for m in (Suit.CLUBS, Suit.DIAMONDS):
                if e.suit_lengths[m] >= 5:
                    return bid(2, op.suit, alert=True,
                               why=f"{twos_label}: other major + minor (5-5)")

    # Ghestem 3♣ — high + low unbid suits (Precision 90M only, and
    # only available when the cuebid suit isn't already clubs).
    if (system.has("O-Ghestem.standard")
            and not system.has("O-Ghestem.not-3C")
            and op.suit != Suit.CLUBS):
        # High+low pair excluding clubs: spades + diamonds when op is
        # hearts; spades + clubs is over diamonds (so 3♣ = ♠+♣); etc.
        # Strict reading of Ghestem assigns 3♣ to the high + low of the
        # three suits other than opener's.
        unbid = [s for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
                 if s != op.suit]
        unbid_by_rank = sorted(unbid, key=lambda s: _BID_RANK[s])
        low_suit, high_suit = unbid_by_rank[0], unbid_by_rank[-1]
        if (e.suit_lengths[low_suit] >= 5
                and e.suit_lengths[high_suit] >= 5
                and 8 <= hcp <= 16):
            return bid(3, Suit.CLUBS, alert=True,
                       why=f"Ghestem 3♣: 5-5 in "
                           f"{high_suit.to_char()}+{low_suit.to_char()}")

    # Unusual 2NT: 5-5 in the two lowest-ranked unbid suits, 8-16 HCP.
    unbid = [s for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
             if s != op.suit]
    unbid_sorted = sorted(unbid, key=lambda s: _BID_RANK[s])
    if (8 <= hcp <= 16
            and e.suit_lengths[unbid_sorted[0]] >= 5
            and e.suit_lengths[unbid_sorted[1]] >= 5):
        return bid(2, Suit.NOTRUMP, alert=True,
                   why="Unusual 2NT: 5-5, two lower unbid suits")

    # Strong balanced 19+ — too strong for 1NT-overcall (15-18). Standard
    # treatment is a takeout-X intending to rebid NT (19-22), regardless
    # of shortness in opener's suit, provided we hold a stopper. Only on
    # our FIRST action — if we've already bid (or doubled), don't
    # auto-double again every round.
    if (hcp >= 19 and e.is_balanced and _has_stopper(e, op.suit)
            and not state.my_bids):
        return double(why="Strong-balanced takeout X (19+ HCP, plan NT rebid)")

    # 1NT overcall: 15-18 balanced with a stopper in opener's suit.
    if 15 <= hcp <= 18 and e.is_balanced and _has_stopper(e, op.suit):
        return bid(1, Suit.NOTRUMP, why="1NT overcall: 15-18, stopper")

    # Suit overcall. 1-level vs 2-level have very different
    # strength requirements; Q-Plus / wbridge5 are conservative
    # at the 2-level, especially vulnerable. Standards:
    #   1-level: 8-16 HCP, 5+ card suit, 4+ suit HCP (a kingish suit).
    #   2-level non-vul: 10-16 HCP, 5+ suit, 6+ suit HCP (Q-x-x or
    #       better) OR 6+ card suit with 4+ suit HCP.
    #   2-level vul: 11-16 HCP, 6+ card suit with 5+ suit HCP, or
    #       a 5-card suit with 8+ suit HCP (AKQxx-ish).
    am_vulnerable = state.vulnerability.is_vulnerable(state.seat) \
        if hasattr(state, 'vulnerability') and state.vulnerability \
        else False
    # The level of a natural overcall is the cheapest legal level for
    # that suit given the FULL auction so far, not just opener's suit
    # — in 4th-seat balancing (after responder has bid) the natural
    # overcall starts at the next level up.
    def _cheapest_legal_level(target_suit):
        last_suit = state.last_suit_bid
        last_lvl = state.last_level or 1
        if last_suit is None:
            return 1
        if _BID_RANK[target_suit] > _BID_RANK[last_suit]:
            return last_lvl
        return last_lvl + 1

    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if s == op.suit:
            continue
        length = e.suit_lengths[s]
        suit_hcp = e.suit_hcp[s]
        if length < 5:
            continue
        level = _cheapest_legal_level(s)
        if level == 1:
            if 8 <= hcp <= 16 and suit_hcp >= 4:
                return bid(level, s,
                           why=f"1{s.to_char()} natural overcall")
        elif level == 2:
            if am_vulnerable:
                ok = ((length >= 6 and suit_hcp >= 5 and hcp >= 11)
                      or (length >= 5 and suit_hcp >= 8 and hcp >= 11))
            else:
                # NV 2-level overcall: standard 6+ card with Q-x-x
                # quality at 10+ HCP. Also accept a 6+ card suit
                # with 12+ HCP and any honor (Q+) — Q-Plus overcalls
                # 2♣ with QXXXXX clubs and 13 HCP (seed=200 board 9).
                ok = ((length >= 6 and suit_hcp >= 4 and hcp >= 10)
                      or (length >= 5 and suit_hcp >= 6 and hcp >= 10)
                      or (length >= 6 and suit_hcp >= 2 and hcp >= 12))
            if ok and hcp <= 16:
                return bid(level, s,
                           why=f"2{s.to_char()} natural overcall "
                               f"({'vul' if am_vulnerable else 'nvul'})")
        # level ≥ 3 is reserved for jump/preempt-style overcalls below.

    # Takeout double — shortness in opener's suit + tolerance for unbid suits.
    if hcp >= 12 and e.suit_lengths[op.suit] <= 2:
        if all(e.suit_lengths[s] >= 3 for s in unbid):
            return double(why="Takeout double")

    # Weak jump overcall: 6-card suit with a respectable holding,
    # 6-10 HCP, and only in DIRECT seat (opener is my RHO). In
    # 4th-seat balancing the cheapest overcall is already at the
    # 2-level, so "jumping" to the 3-level here is reckless.
    #
    # In Precision-family systems (`strong_open_call == "1C"`) the
    # 1D opening is a catch-all that doesn't promise diamonds, so
    # a natural diamond preempt over 1D is allowed — we don't
    # filter out opener's suit when it's the artificial 1D.
    rho_seat = state.seat.next().next().next()
    opener_is_rho = state.opener_seat == rho_seat
    opener_1d_is_catchall = (
        getattr(system, "strong_open_call", "2C") == "1C"
        and op.level == 1 and op.suit == Suit.DIAMONDS
    )
    if opener_is_rho:
        for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
            if s == op.suit and not opener_1d_is_catchall:
                continue
            length = e.suit_lengths[s]
            suit_hcp = e.suit_hcp[s]
            # Quality threshold scales with length: 6 cards need
            # the standard suit-HCP ≥ 4 (an honor + queen-ish);
            # 7+ card suits can preempt on QJ-headed (suit-HCP 3);
            # 8+ card suits don't need any honor.
            min_suit_hcp = 4 if length == 6 else (3 if length == 7 else 0)
            if (length >= 6
                    and suit_hcp >= min_suit_hcp
                    and 4 <= hcp <= 10):
                # Jump level: 2 if natural rank > op.suit (so 2-of-suit
                # is a jump over a 1-level opening), 3 if same/lower
                # rank (need to bump to the 3-level for it to be a
                # jump). In the Precision-1D-catchall case where
                # opener also bid diamonds, 3D is always the call.
                if s == op.suit:
                    level = op.level + 2
                else:
                    level = 2 if _BID_RANK[s] > _BID_RANK[op.suit] else 3
                if level <= 4:
                    return bid(level, s, why="Weak jump overcall")

    return passb()


def _overcaller_rebid(state, e: HandEval, system) -> Bid:
    """Overcaller's rebid after partner has acted.

    I made the original overcall; partner has now bid (advance,
    raise, new suit, X/XX). Pass on minimum; only re-bid with
    real extras.

    Conservative heuristics for now — the diff harness will refine
    these. Rules:
      • Partner raised my suit at the 2 or 3 level → pass unless
        I have 15+ HCP and a 6+ card suit (then jump one more
        level).
      • Partner bid a new suit at the 1- or 2-level → pass with
        minimum, raise partner's suit with 3+ support and extras,
        rebid my own suit with 6+ of it.
      • Partner doubled or redoubled → pass.
      • Partner cuebid opener's suit → show my best feature; we
        currently just bid 3 of my own suit.
    """
    my_first = state.my_bids[0]
    my_suit = my_first.suit
    my_length = e.suit_lengths.get(my_suit, 0)
    p_last = state.partner_bids[-1] if state.partner_bids else None
    hcp = e.hcp

    # Without a real partner action, defensible default is pass.
    if p_last is None or p_last.is_pass:
        return passb(why="Overcaller rebid — no partner action, pass")

    # Partner doubled / redoubled — leave it.
    if p_last.is_double or p_last.is_redouble:
        return passb(why="Overcaller rebid — partner's X/XX, pass")

    # Partner raised my suit.
    if p_last.suit == my_suit:
        # 15+ HCP and 6+ of the suit → push for game; else pass.
        if hcp >= 15 and my_length >= 6 \
                and p_last.level < 5:
            return bid(p_last.level + 1, my_suit,
                       why=f"Overcaller rebid — extras + long suit, "
                           f"jump to {p_last.level + 1}{my_suit.to_char()}")
        return passb(why="Overcaller rebid — partner raised, minimum, pass")

    # Partner cuebid opener's suit — Unassuming Cue-bid (UCB),
    # showing a limit raise+ of my overcall (10-12 HCP, 3+ support
    # in my suit). Standard responses:
    #   * Minimum overcall (≤ 12 HCP): sign off in 3 of my suit.
    #   * Sound overcall (13-15 HCP): jump to game in my suit.
    #   * 16+ HCP: control bid the lowest unbid suit (slam try).
    opener_suit = (state.opening_bid.suit
                   if state.opening_bid is not None
                   and state.opening_bid.suit is not None
                   and state.opening_bid.suit != Suit.NOTRUMP
                   else None)
    if (opener_suit is not None
            and p_last.suit == opener_suit
            and my_suit in (Suit.HEARTS, Suit.SPADES,
                            Suit.DIAMONDS, Suit.CLUBS)):
        if hcp >= 16 and my_suit in (Suit.HEARTS, Suit.SPADES):
            # Pick lowest unbid suit below my own for the control
            # bid; otherwise just jump to game.
            for ctrl in (Suit.CLUBS, Suit.DIAMONDS,
                         Suit.HEARTS, Suit.SPADES):
                if ctrl == opener_suit or ctrl == my_suit:
                    continue
                if _BID_RANK[ctrl] < _BID_RANK[my_suit]:
                    return bid(p_last.level + 1, ctrl, alert=True,
                               why="Control bid after UCB (16+ HCP)")
            return bid(4, my_suit,
                       why="Accept UCB to game (16+, no cheap control)")
        if hcp >= 13 and my_suit in (Suit.HEARTS, Suit.SPADES):
            return bid(4, my_suit,
                       why="Accept UCB to 4M (13-15 HCP, sound overcall)")
        # Minimum: decline by re-bidding suit at 3-level.
        new_level = max(3, p_last.level + 1)
        if new_level <= 4:
            return bid(new_level, my_suit,
                       why=f"Decline UCB: {new_level}{my_suit.to_char()} "
                           "(minimum overcall)")

    # Partner bid a new suit / NT.
    if p_last.suit is not None and p_last.suit != Suit.NOTRUMP:
        # Support partner's suit with 3+ cards + extras.
        if (e.suit_lengths.get(p_last.suit, 0) >= 3
                and hcp >= 13
                and p_last.level < 4):
            return bid(p_last.level + 1, p_last.suit,
                       why=f"Overcaller rebid — raising partner's "
                           f"{p_last.suit.to_char()} with support")
        # Rebid my own suit with 6+ length.
        if my_length >= 6 and hcp >= 11:
            new_level = max(my_first.level + 1, p_last.level + 1)
            if new_level <= 4:
                return bid(new_level, my_suit,
                           why=f"Overcaller rebid — 6+ {my_suit.to_char()}")

    # Default — overcaller's job is done; let partner / opponents drive.
    return passb(why="Overcaller rebid — no clear extras, pass")


def _advance_partner_overcall(state, e: HandEval, system) -> Bid:
    # If *I* was the original overcaller (my first non-pass bid was
    # a suit overcall) and partner has since raised my suit, this
    # auction round isn't "advance partner's overcall" — it's
    # "overcaller's rebid". Without this guard the bidder treats
    # partner's raise like a fresh overcall and re-raises with the
    # same hand, producing the `2C 3C 4C 5C 6C 7C` infinite ascent
    # we saw on Board 3 of the Q-Plus diff.
    if state.my_bids:
        first_my_bid = state.my_bids[0]
        is_overcall = (
            not first_my_bid.is_pass
            and not first_my_bid.is_double
            and not first_my_bid.is_redouble
            and first_my_bid.suit is not None
            and first_my_bid.suit != Suit.NOTRUMP
        )
        if is_overcall:
            return _overcaller_rebid(state, e, system)

    p_last = state.partner_bids[-1]
    hcp = e.hcp

    # The cheapest legal level for a suit overcall, given the auction
    # so far. Walks the bid history (not just last_non_pass) because a
    # double has level=0 — using state.last_level when partner doubled
    # produced sub-level-1 bids over a 3-level preempt.
    def _min_legal_level(suit: Suit) -> int:
        highest_level, highest_suit = 0, None
        for _seat, b in state.bids:
            if b.is_pass or b.is_double or b.is_redouble:
                continue
            if b.suit is None:
                continue
            if (b.level > highest_level
                    or (b.level == highest_level
                        and highest_suit is not None
                        and _BID_RANK[b.suit] > _BID_RANK[highest_suit])):
                highest_level, highest_suit = b.level, b.suit
        if highest_suit is None:
            return 1
        if _BID_RANK[suit] > _BID_RANK[highest_suit]:
            return highest_level
        return highest_level + 1

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
                unbid_pair = [s for s in (Suit.SPADES, Suit.HEARTS,
                                          Suit.DIAMONDS, Suit.CLUBS)
                              if s != opener_suit]
                long_pair = sorted(
                    unbid_pair,
                    key=lambda s: e.suit_lengths.get(s, 0),
                    reverse=True,
                )
                if (e.suit_lengths.get(long_pair[0], 0) >= 3
                        and e.suit_lengths.get(long_pair[1], 0) >= 3):
                    return double(why="Responsive double — pick a suit")

        opener_lvl = state.opening_bid.level if state.opening_bid else 1

        # --- Slam exploration after partner's takeout double. ---
        # Partner promised opening values + shortness in opener's
        # suit + tolerance for the unbid suits. If we have a long
        # major and very strong playing strength, push toward slam
        # rather than settling at game.

        # Direct slam leap — 12+ HCP, 7+ in a major, LTC ≤ 4 (i.e.
        # almost no losers). Board 388's S hand (♠AQJ9742 ♥7
        # ♦KQ963 ♣–, 12 HCP, LTC 3) hits this branch and bids 6♠
        # immediately. Misses an occasional grand but beats
        # stopping at game when the trick count is overwhelming.
        if hcp >= 11:
            for m in (Suit.SPADES, Suit.HEARTS):
                if e.suit_lengths[m] >= 7 and e.losers <= 4:
                    return bid(6, m,
                               why=f"Slam after takeout X: "
                                   f"7+{m.to_char()}, LTC≤4")

        # Cuebid slam-try — 12+ HCP, 6+ major, 0-1 in opener's suit
        # (partner's double promised shortness too, so we know we
        # likely have a working fit). Cuebid opener's suit to show
        # extras and let partner pick the strain.
        if (hcp >= 12 and opener_lvl >= 3
                and e.suit_lengths.get(state.opening_bid.suit, 0) <= 1):
            for m in (Suit.SPADES, Suit.HEARTS):
                if e.suit_lengths[m] >= 6:
                    cue_lvl = state.opening_bid.level + 1
                    return bid(cue_lvl, state.opening_bid.suit, alert=True,
                               why=f"Cuebid slam try: 6+{m.to_char()}, "
                                   f"{hcp} HCP after takeout X")

        # 4-card major → bid it at the cheapest legal level. Over a
        # 3-level preempt this is a 4-of-a-major bid (jump to game)
        # not 1-of-a-major.
        for m in (Suit.SPADES, Suit.HEARTS):
            if e.suit_lengths[m] >= 4:
                lvl = _min_legal_level(m)
                # Over a 3-level preempt with 5+ in the suit and any
                # values, jump to 4 of the major directly — that's
                # the standard takeout-doubler-advancer agreement.
                if opener_lvl >= 3 and e.suit_lengths[m] >= 5 and hcp >= 6:
                    lvl = max(lvl, 4)
                # Skip the advance if it would force us past our
                # values. The auction may have been pushed up by
                # responder's intervention (e.g. 1D-(X)-2NT-?); a
                # 1-HCP hand can't take an action at the 3-level.
                min_hcp_for_lvl = {1: 0, 2: 6, 3: 9, 4: 12}.get(lvl, 14)
                if hcp < min_hcp_for_lvl:
                    continue
                return bid(lvl, m, why=f"Advance takeout double: 4-card major")
        # Balanced with stopper → NT. Lift the level above the preempt.
        if hcp >= 8 and _has_stopper(e, state.opening_bid.suit) and e.is_balanced:
            # 3NT over a 3-level preempt; 1NT only over a 1-level overcall.
            nt_level = 3 if opener_lvl >= 3 else (2 if opener_lvl == 2 else 1)
            return bid(nt_level, Suit.NOTRUMP,
                       why=f"Advance takeout dbl: {nt_level}NT (stopper)")
        # Cuebid with 11+ to show game interest (only meaningful at
        # 1- or 2-level openings; over a preempt a cuebid is too high
        # and we just pick a long suit).
        if hcp >= 11 and opener_lvl <= 2:
            return bid(opener_lvl + 1, state.opening_bid.suit, alert=True,
                       why="Cuebid: game interest after takeout double")
        # Longest minor as a last resort.
        for m in (Suit.DIAMONDS, Suit.CLUBS):
            if e.suit_lengths[m] >= 4:
                lvl = _min_legal_level(m)
                min_hcp_for_lvl = {1: 0, 2: 6, 3: 9, 4: 12}.get(lvl, 14)
                if hcp < min_hcp_for_lvl:
                    continue
                return bid(lvl, m, why="Advance takeout double: minor")
        return passb()

    # Doubler responding to advancer's CUEBID of opener's suit.
    # When I previously doubled and partner now bids opener's suit
    # at a higher level, that's a slam-try cuebid asking me to
    # describe my hand. Pick my best major at the cheapest legal
    # level (or 4NT with very strong balanced values + a fit).
    i_doubled = any(b.is_double for b in state.my_bids)
    opener_suit_now = state.opening_bid.suit if state.opening_bid else None
    if (i_doubled
            and opener_suit_now is not None
            and p_last.suit == opener_suit_now
            and p_last.level > state.opening_bid.level
            and not p_last.is_pass and not p_last.is_double):
        # Bid the longer major at the cheapest level.
        best_major = None
        best_len = 0
        for m in (Suit.SPADES, Suit.HEARTS):
            if e.suit_lengths.get(m, 0) > best_len:
                best_len = e.suit_lengths[m]
                best_major = m
        if best_major is not None and best_len >= 4:
            lvl = _min_legal_level(best_major)
            return bid(lvl, best_major, alert=True,
                       why=f"Reply to cuebid: showing {best_len} "
                           f"{best_major.to_char()} ({hcp} HCP)")
        # No major to show — bid cheapest minor.
        for m in (Suit.DIAMONDS, Suit.CLUBS):
            if m == opener_suit_now:
                continue
            if e.suit_lengths.get(m, 0) >= 4:
                lvl = _min_legal_level(m)
                return bid(lvl, m, alert=True,
                           why=f"Reply to cuebid: {m.to_char()} suit, "
                               f"no major")
        # Fallback: NT at the cheapest legal level for the auction.
        nt_lvl = _min_legal_level(Suit.NOTRUMP)
        return bid(nt_lvl, Suit.NOTRUMP, alert=True,
                   why="Reply to cuebid: NT, no clear strain")

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
            state = parse_auction(seat=seat, dealer=board.dealer,
                                  auction=board.auction,
                                  vulnerability=board.vulnerability)
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
