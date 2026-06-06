"""
NativeBiddingEngine — a from-scratch rule-based bidder modelled on Qplus 17.

Plug-compatible with BridgeEngine.get_bid: takes (BoardState, Seat) and
returns an EngineResponse whose `action` is the chosen Bid.

Card play is NOT handled here. Per BridgeEngine, biq is NN-free: the
engine is rule-based for bidding, native_lead for opening leads, and
Monte-Carlo + DDS (get_mc_card_play) for follow-on cards. BEN has
been REMOVED; do not assume any neural-net dependency.

Systems wired (see backend/bidding_systems.py for the full catalog):
  * SAYC
  * TwoOverOne (2/1 GF)
  * StandardAcol
  * StandardFrench
  * Precision90M

Conventions implemented across the systems:
  Stayman + Smolen, Jacoby transfers (major + Texas), Blackwood /
  1430 RKC, splinters, negative doubles, Lebensohl (over 1NT-(2X)),
  Michaels cuebid, Unusual 2NT, jump preempts, weak twos, Italian
  cuebidding, Gerber (4C ace-ask after opening NT), Grand-slam
  force (5NT after major-trump-agreed), Bergen-style 4D trump-
  quality ask, count-to-grand path over 2NT openings.

Architecture:
  An AuctionContext (backend/auction_context.py) is computed once
  per decide_bid via a single pass over the bid stream. It exposes
  typed primitives — trump (with mechanism), gf_established,
  slam_zone_entered, controls_shown, last_4nt_is_{rkc,quantitative},
  forcing (ForcingContext), captain, convention (e.g. STAYMAN,
  JACOBY_TRANSFER, GERBER, FOURTH_SUIT_FORCING) — so downstream
  decision sites read from the context instead of re-deriving
  auction state. See plan_option1_semantic_state.md.

The dispatch is a flat decision tree keyed on auction state plus the
context primitives. There is no tree search; the goal is "a defensible
bid for every common situation, anchored in textbook convention."
Pathological auctions fall back to Pass via the sanity wrapper.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import (
    Bid, BoardState, Card, Hand, Seat, Suit, Vulnerability, Rank,
)
from .auction_context import (  # Option 1: semantic-state model
    AuctionContext, TrumpAgreement, TrumpMechanism,
    derive_context,
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
    playing_tricks: float    # Phase F: textbook playing-tricks count
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
    playing_tricks = _playing_tricks(by_suit)

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
        playing_tricks=playing_tricks,
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


def _playing_tricks(by_suit) -> float:
    """Phase F playing-tricks estimate — how many tricks the hand
    expects to take on offense, ignoring partner's holding.

    Formula (well-known textbook approximation, e.g. Goren / Klinger):
      • For each suit, count top-honor tricks: A=1, K with 2+=1,
        Q with 3+=1 (if A or K also held).
      • Plus length tricks beyond the third card: each card past 3
        in a suit adds +1 trick (assuming a 5-card suit will run).

    Used for slam-evaluation in Phase F where HCP+losers+controls
    misses key data: a 6-card suit headed by AK is worth ~5 playing
    tricks even with only 7 HCP, and a balanced 16-HCP hand may have
    only 4-5 playing tricks. Q-Plus's slam decisions implicitly use
    playing-tricks; biq matching that requires the same primitive.
    """
    total = 0.0
    for cards in by_suit.values():
        n = len(cards)
        if n == 0:
            continue
        ranks = {c.rank for c in cards}
        has_a = Rank.ACE in ranks
        has_k = Rank.KING in ranks
        has_q = Rank.QUEEN in ranks
        # Top-honor tricks
        if has_a:
            total += 1.0
        if has_k and n >= 2:
            total += 1.0
        if has_q and n >= 3 and (has_a or has_k):
            total += 1.0
        # Length tricks: each card beyond the 3rd.
        if n > 3:
            total += n - 3
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

    # Fourth-seat opening (Pearson / "Rule of 15"): after three passes a
    # sub-minimum hand opens ONLY if HCP + spade length ≥ 15 — the spades
    # let us contest the part-score; without them, pass it out for a fresh
    # deal. (6886-04: 4th-hand South passed AT87.K2.T32.A953 = 11 HCP + 4
    # spades = 15, missing a 9-card fit / 21 combined HCP. Below 15 → still
    # pass.) When it qualifies, fall through to the normal 1-level opening.
    is_fourth_seat = (state is not None and len(state.bids) == 3
                      and all(b.is_pass for _, b in state.bids))
    pearson_ok = (is_fourth_seat and hcp >= 10
                  and hcp + e.suit_lengths[Suit.SPADES] >= 15)

    # Sub-opening hands → Pass (or skip preempts handled below).
    # Rule of 20 (HCP + two-longest-suits ≥ 20) opens shapely
    # 10-11 HCP hands at the 1-level — fall through to the suit-
    # opening block so those qualify. Mixed-corpus deal #5 (seed
    # 11075, N: 11 HCP, 3-2-6-2 with AKQ of diamonds → 11+6+3=20)
    # was being passed out here; Q-Plus opened 1D and reached 2D.
    if hcp < 12 and not _has_preempt(e):
        lens_top2 = sorted(e.suit_lengths.values(), reverse=True)[:2]
        rule_of_20 = hcp + lens_top2[0] + lens_top2[1]
        if rule_of_20 < 20 and not pearson_ok:
            # Gambling 3NT can come from a sub-opening hand (~10
            # HCP solid minor).
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

    # Suit openings (12-21 HCP, or Rule of 20 with 10-11 HCP).
    # The Rule of 20 (modern SAYC / 2-over-1 / French / Acol
    # standard): with 10-11 HCP plus a shape where the two
    # longest suits sum to make HCP + longest + 2nd-longest ≥ 20,
    # open at the 1-level. Catches shapely hands that the strict
    # 12-HCP cap would miss (board 2 seed=10000 SAYC: S has 10
    # HCP + 6-4-2-1 shape with KQ6 hearts → 10 + 6 + 4 = 20,
    # opens 1H; Q-Plus opens 2H weak but bridgeIQ should at
    # least open something).
    if hcp < 10:
        return passb()
    if hcp < 12:
        lens = sorted(e.suit_lengths.values(), reverse=True)
        rule_of_20 = hcp + lens[0] + lens[1]
        if rule_of_20 < 20 and not pearson_ok:
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
        # Textbook discipline: weak twos DENY a 4-card side major.
        # With a 6-card major + 4-card OTHER major, you might miss
        # the 4-4 major fit that a 1-of-major opening would find.
        # E.g. ♠AKJ742 ♥Q943 ♦8 ♣65 (10 HCP, 6-4-1-2) opens 1♠
        # not 2♠ weak — partner with 4-card hearts → 4-4 fit found.
        other_major = (Suit.HEARTS if longest == Suit.SPADES
                       else Suit.SPADES if longest == Suit.HEARTS
                       else None)
        if other_major is not None \
                and e.suit_lengths.get(other_major, 0) >= 4:
            return None
        min_total = 6 if am_vul else 5
        # Non-vul Q-Plus accepts AT9xxx-class suits (one top honor +
        # spot-card sequence). Modeling that as suit-HCP ≥ 4 nvul /
        # ≥ 5 vul.
        min_suit = 5 if am_vul else 4
        # Weak-2 standard range is 5-10 HCP (not 5-9). The previous
        # cap at 9 was incorrect — Q-Plus's SAYC opens 2H with 10
        # HCP + 6cH on board 2 seed=10000 (KQ-headed 6-card suit).
        # Textbook SAYC range is 5-10; mainstream 2/1 is 6-10. The
        # 10-HCP cases are exactly the ones that produce strong
        # constructive auctions; 11+ would be too much for a weak 2.
        if min_total <= e.hcp <= 10 and suit_hcp >= min_suit:
            return bid(2, longest,
                       why=f"Weak two: 6 {longest.to_char()}, "
                           f"{e.hcp} HCP, suit-HCP {suit_hcp}, "
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

    Now reads from the semantic-state AuctionContext (Option 1).
    Returns the trump suit if a formal trump-set was detected
    (raise / jump-raise / splinter / Jacoby 2NT / rebid agreement);
    otherwise returns the legacy fallback (last natural suit bid by
    the partnership before the first 4NT) so single-mention auctions
    like 1H-3S-4NT continue to read as RKC for the last mentioned
    suit.
    """
    ctx = derive_context(state)
    if ctx.trump is not None:
        return ctx.trump.suit
    return ctx.fallback_last_suit


def _is_rkc_context(state: 'AuctionState', for_bid: 'Bid') -> bool:
    """Should `for_bid` (must be 4NT) be read as RKC Blackwood?

    True when a trump suit can be inferred AND the auction has gone
    past the "natural NT" zone. False for opening NT, jump 2NT
    rebids, and quantitative slam invites — those are handled by
    other branches.

    Additional gate: 1m-1M-1NT-4NT is quantitative (deal 39 in slam
    corpus 59517 — opener denied major support with their 1NT rebid,
    so responder's 4NT can't be asking keycards for the major).
    Detection: opener's REBID was 1NT/2NT/3NT (showing balanced
    minimum/medium with no major fit) AND no major-raise has
    happened.
    """
    if not (for_bid.level == 4 and for_bid.suit == Suit.NOTRUMP):
        return False
    ctx = derive_context(state)
    # The context already applies all the trump-set / NT-rebid /
    # strong-artificial-1C gates during 4NT classification, so we
    # just read the result. Phase B simplification (Option 1).
    if not ctx.last_4nt_is_rkc:
        return False
    # Additional gate: at least one suit bid by my partnership
    # (auctions like 1NT-4NT with no suit have no fit; RKC needs one).
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
    # Grand-slam discipline: need ≥12 HCP in MY hand for grand, even
    # with all keys + source + king. Strong-2C jump-raise auctions
    # can drive responder with 6-8 HCP through to king-ask if every
    # gate is met, but the play needs more than just keys + length
    # to take 13 tricks. Deal 5 (slam 67238): S held 8 HCP + 5H + SA;
    # has_source + keys = True but 7H went down 1 (-17 IMP vs 6H).
    # The 12 HCP gate keeps the grand drive but only when responder
    # has the extras for an actual 13th-trick suit.
    if (has_source
            and _keycard_count(e, trump, system) >= 2
            and e.hcp >= 12):
        return bid(7, trump, why=f"Side king shown + source of tricks → 7{trump.to_char()}")
    return bid(6, trump, why=f"Side king shown but no clear source → 6{trump.to_char()}")


def _is_gerber_4c(state: 'AuctionState', for_bid: 'Bid') -> bool:
    """Was `for_bid` (must be 4C) a Gerber ace-ask?

    Strict pattern (MVP):
      • Partner of the 4C bidder OPENED 1NT / 2NT / 3NT (natural
        balanced opening; not a rebid like 1S-1NT). Opening NT is
        the only universally-agreed Gerber context — 4C in suit
        auctions (1S-2C-4C, 1S-1NT-4C) is often splinter / cuebid.
      • Partner's MOST RECENT non-pass bid is still NT (auction
        hasn't pulled out into a suit).
      • No opp intervention.
      • No trump-fit raise on either side.
    """
    if not (for_bid.level == 4 and for_bid.suit == Suit.CLUBS):
        return False
    # Phase B: read from AuctionContext. The context's Gerber detection
    # applies all the gates (partner opened NT, no suit pull-out, no opp
    # intervention, no trump-set raise) in a single pass.
    ctx = derive_context(state)
    if not ctx.last_4c_is_gerber:
        return False
    # for_bid must match the recorded Gerber 4C.
    return True


def _respond_to_gerber(state: 'AuctionState', e: HandEval, system) -> Bid:
    """Partner bid 4C as Gerber ace-ask — answer in steps.

    Step responses:
      • 4D = 0 or 4 aces (ambiguous — asker disambiguates by HCP)
      • 4H = 1 ace
      • 4S = 2 aces
      • 4NT = 3 aces
    """
    n_aces = sum(1 for s in (Suit.SPADES, Suit.HEARTS,
                              Suit.DIAMONDS, Suit.CLUBS)
                 if e.has_ace.get(s, False))
    if n_aces == 0 or n_aces == 4:
        return bid(4, Suit.DIAMONDS, alert=True,
                   why=f"Gerber: {n_aces} aces")
    if n_aces == 1:
        return bid(4, Suit.HEARTS, alert=True, why="Gerber: 1 ace")
    if n_aces == 2:
        return bid(4, Suit.SPADES, alert=True, why="Gerber: 2 aces")
    return bid(4, Suit.NOTRUMP, alert=True, why="Gerber: 3 aces")


def _asker_after_gerber(state: 'AuctionState', e: HandEval, system) -> Bid:
    """I bid 4C Gerber, partner answered — decide game / slam / grand.

    Resolution: count my aces + partner's, decide. Missing 2+ aces →
    sign off in 4NT. With all aces → 5C king-ask (Gerber 5C). With
    exactly 3 → 6NT. Missing 1 → 6NT only if combined HCP is
    comfortably enough for 12 tricks (33+).
    """
    resp = state.partner_bids[-1] if state.partner_bids else None
    if resp is None:
        return passb()
    if resp.level != 4 or resp.suit is None:
        return passb(why="Unexpected Gerber response")
    step = {Suit.DIAMONDS: 0, Suit.HEARTS: 1,
            Suit.SPADES: 2, Suit.NOTRUMP: 3}.get(resp.suit)
    if step is None:
        return passb(why="Non-step Gerber response")
    # Disambiguate 0 vs 4 by total HCP — if I have 16+ and partner
    # showed 0/4, they almost certainly mean 4.
    if step == 0 and e.hcp >= 16:
        partner_aces = 4
    elif step == 0:
        partner_aces = 0
    else:
        partner_aces = step
    my_aces = sum(1 for s in (Suit.SPADES, Suit.HEARTS,
                               Suit.DIAMONDS, Suit.CLUBS)
                  if e.has_ace.get(s, False))
    total = my_aces + partner_aces
    if total <= 2:
        return bid(4, Suit.NOTRUMP,
                   why=f"Gerber: only {total} aces — sign off in 4NT")
    if total == 3:
        # Missing 1 ace — small slam if values are there.
        if e.hcp >= 19:
            return bid(6, Suit.NOTRUMP,
                       why=f"Gerber: 3/4 aces, slam values")
        return bid(4, Suit.NOTRUMP,
                   why=f"Gerber: missing 1 ace + thin HCP")
    # All 4 aces — go to 6NT (king ask via 5NT is rarely used after
    # Gerber; MVP just signs off in 6NT).
    return bid(6, Suit.NOTRUMP, why="Gerber: all 4 aces — 6NT")


def _try_gerber_pipeline(state: 'AuctionState', e: HandEval,
                         system) -> Optional[Bid]:
    """Handle the Gerber 4C → step-answer → continuation flow.

    Mirrors `_try_rkc_pipeline` but for the Gerber-after-NT path."""
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    last_mine = state.my_bids[-1] if state.my_bids else None
    if state.opp_overcalled and state.rho_bids:
        if not state.rho_bids[-1].is_pass:
            return None
    ctx = derive_context(state)
    # Case 1: partner bid 4C Gerber → I respond with ace count.
    # Fire when partner's most recent action is the Gerber 4C AND I
    # haven't already given a Gerber-response step (4D/4H/4S/4NT
    # bid by me AFTER the 4C).
    if (ctx.last_4c_is_gerber
            and ctx.last_4c_bidder == state.seat.partner()
            and last_partner is not None
            and last_partner.level == 4
            and last_partner.suit == Suit.CLUBS):
        # Have I already responded? My response would be a level-4
        # bid that comes AFTER the 4C in state.bids.
        already_responded = False
        for s, b in state.bids:
            if b is last_partner:
                continue  # the Gerber 4C itself — skip
            if s != state.seat:
                continue
            if b.is_pass or b.is_double or b.is_redouble:
                continue
            if b.level == 4 and b.suit in (Suit.DIAMONDS, Suit.HEARTS,
                                            Suit.SPADES, Suit.NOTRUMP):
                # Could be my response (post-4C) or a pre-Gerber bid.
                # Check position: was this bid AFTER the Gerber 4C?
                pre_gerber = True
                for ps, pb in state.bids:
                    if pb is last_partner:
                        pre_gerber = False
                        continue
                    if pb is b:
                        already_responded = not pre_gerber
                        break
        if not already_responded:
            return _respond_to_gerber(state, e, system)
    # Case 2: I bid 4C Gerber, partner answered → my read.
    if (ctx.last_4c_is_gerber
            and ctx.last_4c_bidder == state.seat
            and last_partner is not None
            and last_partner.level == 4
            and last_partner.suit is not None
            and last_partner.suit != Suit.CLUBS):
        return _asker_after_gerber(state, e, system)
    return None


def _try_quantitative_4nt_pipeline(state: 'AuctionState', e: HandEval,
                                   system) -> Optional[Bid]:
    """Handle opener's accept / decline of partner's 4NT quantitative.

    Pattern: I opened/rebid NT, partner jumped to 4NT showing 16-17
    inviting slam in NT. With a maximum, I bid 6NT; with a minimum,
    I pass.
    """
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    if last_partner is None:
        return None
    if not (last_partner.level == 4 and last_partner.suit == Suit.NOTRUMP):
        return None
    ctx = derive_context(state)
    # Partner's 4NT must have been classified as quantitative by the
    # context. The context derives this via _is_rkc_context's gates
    # (trump-set + NT-rebid + strong-artificial-1C exception), so we
    # just read the result here. last_4nt_bidder must be partner.
    if ctx.last_4nt_bidder != state.seat.partner():
        return None
    if not ctx.last_4nt_is_quantitative:
        return None
    # We must be the NT-rebidder (we showed a balanced strength range).
    # Heuristic: my last natural bid was NT.
    my_nt = [b for b in state.my_bids
             if b.suit == Suit.NOTRUMP and not b.is_pass]
    if not my_nt:
        return None
    # Decide based on where I was in my NT range: max → 6NT, min → pass.
    nt_min = (getattr(system, "one_nt_min_hcp", 15)
              if system is not None else 15)
    nt_max = (getattr(system, "one_nt_max_hcp", 17)
              if system is not None else 17)
    midpoint = (nt_min + nt_max) / 2.0
    if e.hcp > midpoint:
        return bid(6, Suit.NOTRUMP,
                   why=f"Accepting quantitative 4NT: max of NT range "
                       f"({e.hcp} HCP, {nt_min}-{nt_max})")
    return passb(why=f"Declining quantitative 4NT: min of NT range "
                     f"({e.hcp} HCP, {nt_min}-{nt_max})")


def _is_trump_quality_4d_ask(state: 'AuctionState',
                             for_bid: 'Bid') -> bool:
    """Was `for_bid` (must be 4D) a trump-quality asking bid?

    Pattern (Bergen-style): trump-set in a major at the 3-level,
    cuebid exchange is in progress (at least one 4-level cuebid),
    and asker bids 4D in a NEW position — neither trump nor a
    previously-cuebid suit. Asker wants to know about trump quality
    before grand.

    Responses to 4D-quality-ask:
      • 4 of trump = poor trumps (top honor missing or weak length)
      • 4NT = solid trumps (2 of top 3 honors, 5+ length)
    """
    if not (for_bid.level == 4 and for_bid.suit == Suit.DIAMONDS):
        return False
    trump = _agreed_trump(state)
    if trump not in (Suit.HEARTS, Suit.SPADES):
        return False
    if _trump_set_level(state) is None:
        return False
    # Need at least one cuebid in the auction before 4D ask.
    # If 4D is itself the first cuebid (and would be cheapest), the
    # cuebid pipeline owns it — don't classify as asking bid.
    bidder = None
    for s, b in state.bids:
        if b is for_bid:
            bidder = s
            break
    if bidder is None:
        return False
    my_cuebids, partner_cuebids = _cuebids_made_so_far(state, trump)
    if not partner_cuebids and not my_cuebids:
        return False
    # Diamonds must not be trump or previously cuebid by either side.
    if trump == Suit.DIAMONDS:
        return False
    if Suit.DIAMONDS in my_cuebids or Suit.DIAMONDS in partner_cuebids:
        return False
    return True


def _respond_to_trump_quality_ask(state: 'AuctionState', e: HandEval,
                                  system) -> Bid:
    """Partner bid 4D as trump-quality ask — answer in steps.

    4 of trump = poor (≤ 1 top honor in trump)
    4NT       = solid (≥ 2 of top 3 honors OR 6+ length with 1)
    """
    trump = _agreed_trump(state)
    if trump is None:
        return passb()
    top_honours = sum(1 for f in (e.has_ace.get(trump, False),
                                   e.has_king.get(trump, False),
                                   e.has_queen.get(trump, False)) if f)
    trump_length = e.suit_lengths.get(trump, 0)
    solid = top_honours >= 2 or (top_honours >= 1 and trump_length >= 6)
    if solid:
        return bid(4, Suit.NOTRUMP, alert=True,
                   why=f"Trump-quality: solid ({top_honours} top "
                       f"honours, {trump_length} cards)")
    return bid(4, trump, alert=True,
               why=f"Trump-quality: poor ({top_honours} top honours, "
                   f"{trump_length} cards)")


def _try_asking_bid_pipeline(state: 'AuctionState', e: HandEval,
                             system) -> Optional[Bid]:
    """Handle Bergen-style 4D trump-quality ask + responses.

    Phase 5 of the slam-architecture plan. Currently MVP: only the
    4D-trump-quality flavour, gated to fire after trump-set + at
    least one cuebid has been exchanged. Doesn't conflict with the
    cuebid pipeline since `_try_cuebid_pipeline` requires partner's
    last bid to be a cuebid — if partner bid 4D as a quality-ask,
    it's not a cheapest-side-suit cuebid (we check trump-set + cuebid
    in 4D's classification path).
    """
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    last_mine = state.my_bids[-1] if state.my_bids else None
    if state.opp_overcalled and state.rho_bids:
        if not state.rho_bids[-1].is_pass:
            return None
    if last_partner is not None and _is_trump_quality_4d_ask(state,
                                                              last_partner):
        if last_mine is None or last_mine.level < 4:
            return _respond_to_trump_quality_ask(state, e, system)
    return None


def _try_grand_slam_force_pipeline(state: 'AuctionState', e: HandEval,
                                   system) -> Optional[Bid]:
    """Handle the 5NT grand-slam force (Josephine / GSF).

    Pattern: partnership has agreed a major trump and partner bids
    5NT in a non-RKC context (no 4NT RKC bid earlier) — that's a
    GSF asking 'do you have 2 of the top 3 trump honours (AKQ)?'.
    Responses: 7 of trump with 2 of top 3; 6 of trump otherwise.

    Note: this is distinct from the 5NT king-ask after 4NT RKC,
    which is handled by `_respond_to_king_ask`.
    """
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    if last_partner is None:
        return None
    if not (last_partner.level == 5 and last_partner.suit == Suit.NOTRUMP):
        return None
    # 4NT RKC earlier? Then 5NT is king-ask, not GSF (handled elsewhere).
    for s, b in state.bids:
        if b.level == 4 and b.suit == Suit.NOTRUMP and not b.is_pass:
            return None
    trump = _agreed_trump(state)
    if trump not in (Suit.HEARTS, Suit.SPADES):
        return None
    trump_set = _trump_set_level(state)
    if trump_set is None:
        return None
    # Count top trump honors (A, K, Q).
    top_honours = sum(1 for f in (e.has_ace.get(trump, False),
                                   e.has_king.get(trump, False),
                                   e.has_queen.get(trump, False)) if f)
    if top_honours >= 2:
        return bid(7, trump, alert=True,
                   why=f"GSF 5NT: {top_honours} of top 3 trump "
                       f"honours → 7{trump.to_char()}")
    return bid(6, trump, alert=True,
               why=f"GSF 5NT: only {top_honours} of top 3 trump "
                   f"honours → 6{trump.to_char()}")


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
# Italian-style cuebidding (Phase 3 of the slam-architecture plan)
# ---------------------------------------------------------------------------
#
# Once a trump suit is agreed at the 3M / 4M level, an "Italian" slam
# auction exchanges first-round controls (ace or void) up the line,
# then second-round controls (king or singleton), then RKC for keys.
# The benefit over jumping straight to 4NT is that each side sees
# WHICH side suits the other controls, so grand-slam decisions get
# the right answer instead of a coin flip.
#
# Scope of this MVP:
#   • Trump is a MAJOR (H or S). Minor-suit cuebidding is rarer in
#     2/1 / SAYC and lower leverage on the slam-corpus dig.
#   • Trump was set at 3M or 4M by a partner-or-mine raise.
#   • Auction is below 4NT.
#   • Hand has slam-going values (defer to existing 4NT-launch
#     callers — they only call us when they would have launched
#     RKC; our job is to cuebid first if there's something to show).
#   • Continuation: after a cuebid is on the table, both partners
#     keep cuebidding upward until one runs out of cheaper controls,
#     at which point that partner launches 4NT RKC.
# ---------------------------------------------------------------------------


_CUEBID_SUIT_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1,
                     Suit.HEARTS: 2, Suit.SPADES: 3,
                     Suit.NOTRUMP: 4}


def _first_round_controls(e: 'HandEval') -> set:
    """Suits where we hold a first-round control (ace or void).

    First-round control means we win the first trick in the suit
    (opponents can't cash an ace against us). The cuebid sequence
    shows these up the line."""
    out = set()
    for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        if e.has_ace.get(s, False):
            out.add(s)
        elif e.suit_lengths.get(s, 0) == 0:
            out.add(s)
    return out


def _second_round_controls(e: 'HandEval') -> set:
    """Suits where we hold a second-round control (king or singleton).

    Second-round means we don't lose two tricks in the suit. A void
    is also a second-round control, but we'd show it as first-round
    first; this helper returns ONLY second-round-but-not-first."""
    out = set()
    for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        if e.has_king.get(s, False) and not e.has_ace.get(s, False):
            out.add(s)
        elif e.suit_lengths.get(s, 0) == 1:
            out.add(s)
    return out


def _trump_set_level(state: 'AuctionState') -> Optional[Tuple[int, Suit]]:
    """Find the first agreement on a major-suit trump.

    Now reads from the semantic-state AuctionContext (Option 1).
    Returns (level, suit) for the trump-set bid or None.

    Detection scope (in AuctionContext.derive_context):
      • Direct raise: 1H-2H, 1S-2S, 1C-1H-2H, 1H-2D-3H
      • Jump raise:   1H-3H (limit), 1S-4S
      • Splinter:     1H-4C/4D/3S etc. (alerted jump by responder)
      • Jacoby 2NT:   1M-2NT (alerted)
      • Rebid agreement: opener raises responder's major (1C-1H-2H)
    """
    t = derive_context(state).trump
    if t is None:
        return None
    return (t.level, t.suit)


def _cuebids_made_so_far(state: 'AuctionState',
                         trump: Suit) -> Tuple[List[Suit], List[Suit]]:
    """Cuebids each side has shown so far.

    Reads from AuctionContext.controls_shown (Option 1 Phase B).
    The context single-pass walker classifies cuebids consistently
    across every call site; the legacy ad-hoc re-walk that used to
    live here is gone."""
    ctx = derive_context(state)
    partner = state.seat.partner()
    my_cuebids = list(ctx.controls_shown.get(state.seat, []))
    partner_cuebids = list(ctx.controls_shown.get(partner, []))
    return my_cuebids, partner_cuebids


def _cheapest_cuebid(trump: Suit, last_level: int, last_suit: Optional[Suit],
                     candidate_suits: set,
                     excluded: set) -> Optional[Tuple[int, Suit]]:
    """Find the cheapest legal cuebid in `candidate_suits` (minus
    `excluded`) that strictly outranks (last_level, last_suit).

    Cuebids are always in side suits, never in trump or NT. The
    Italian convention picks the LOWEST one — so we walk suit-rank
    order from clubs to spades and pick the first qualifier."""
    pool = {s for s in candidate_suits
            if s != trump
            and s != Suit.NOTRUMP
            and s not in excluded}
    if not pool:
        return None
    last_rank = _CUEBID_SUIT_RANK.get(last_suit, -1) if last_suit else -1
    # Try each suit in clubs→spades order at level >= last_level.
    for level in (last_level, last_level + 1):
        if level < 1 or level > 7:
            continue
        for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
            if s not in pool:
                continue
            if level == last_level:
                # Same level: must outrank last_suit.
                if _CUEBID_SUIT_RANK[s] <= last_rank:
                    continue
            # Cap: cuebids stay at the 4-level (5-level cuebids past
            # 4-of-trump are dangerous; MVP refuses them).
            if level > 4:
                continue
            return (level, s)
    return None


def _try_cuebid_pipeline(state: 'AuctionState', e: 'HandEval',
                         system) -> Optional[Bid]:
    """Continue a cuebid sequence after one has been started.

    Returns a Bid when:
      • Trump is set in a major at 3M / 4M.
      • At least one cuebid has been made (by partner) since trump
        set, AND the most recent partnership action wasn't 4NT.
      • My turn: I either show my next cheapest first-round control
        ABOVE partner's cuebid, or — if I have no more new 1st-round
        controls — launch 4NT RKC (slam interest confirmed by my
        having initiated cuebidding) or sign off at 4M (no extras).

    Returns None when the auction isn't in cuebid-continuation mode
    (let the normal opener/responder/overcaller paths handle).
    """
    ctx = derive_context(state)
    if ctx.trump is None:
        return None
    if ctx.trump.suit not in (Suit.HEARTS, Suit.SPADES):
        return None
    trump = ctx.trump.suit
    # If 4NT or higher already in auction, RKC pipeline owns it.
    if ctx.last_4nt_bidder is not None:
        return None
    for s, b in state.bids:
        if b.level >= 5 and not b.is_pass:
            return None
    # Read cuebid history from context (Phase B migration).
    partner = state.seat.partner()
    my_cuebids = list(ctx.controls_shown.get(state.seat, []))
    partner_cuebids = list(ctx.controls_shown.get(partner, []))
    if not partner_cuebids:
        return None  # Partner hasn't cuebid — initiation is handled
                     # at the existing 4NT-launch call sites.
    # Has partner's most recent bid been a cuebid?
    last_partner = state.partner_bids[-1] if state.partner_bids else None
    if last_partner is None or last_partner.suit in (None, Suit.NOTRUMP,
                                                     trump):
        return None
    # Walk the last non-pass natural bid (the one I have to outrank).
    last_natural = None
    for s, b in reversed(state.bids):
        if b.is_pass or b.is_double or b.is_redouble:
            continue
        last_natural = b
        break
    if last_natural is None:
        return None
    # Excluded: suits already cuebid by either side (don't repeat).
    excluded = set(my_cuebids) | set(partner_cuebids)
    fr = _first_round_controls(e)
    new_fr = fr - excluded
    cuebid = _cheapest_cuebid(trump, last_natural.level,
                              last_natural.suit, new_fr, excluded)
    if cuebid is not None:
        lvl, suit = cuebid
        return bid(lvl, suit, alert=True,
                   why=f"Cuebid: first-round control in "
                       f"{suit.to_char()} (Italian style, trump "
                       f"{trump.to_char()})")
    # No new first-round controls to show. Decide between:
    #   (a) launching 4NT RKC (we have slam interest — partner
    #       cuebid, so we're in a slam-going auction)
    #   (b) signing off at 4-of-trump (we've shown what we have)
    # Heuristic: if my partnership has shown ≥2 cuebids combined,
    # we're at the "ready for RKC" stage. Otherwise sign off.
    total_cuebids = len(my_cuebids) + len(partner_cuebids)
    # Strong-2C opener: lower HCP threshold from 11 to 6. Combined
    # with 22+ opener, 6 HCP responder is in slam zone. Deal 5
    # (slam 67238): S held 8 HCP + SA + 5H; previous 11-HCP gate
    # made S retreat to 4H after cuebid exchange.
    op_bid = state.opening_bid
    after_strong_2c = (op_bid is not None
                       and op_bid.level == 2
                       and op_bid.suit == Suit.CLUBS
                       and op_bid.alert)
    hcp_threshold_4nt = 6 if after_strong_2c else 11
    if total_cuebids >= 2 and e.hcp >= hcp_threshold_4nt:
        # Launch RKC if 4NT is legal at this level.
        if last_natural.level <= 4:
            # 4NT must outrank the last bid; check level + suit-rank.
            if (last_natural.level < 4
                    or (last_natural.level == 4
                        and _CUEBID_SUIT_RANK.get(last_natural.suit, -1)
                            < _CUEBID_SUIT_RANK[Suit.NOTRUMP])):
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"RKC after cuebid exchange "
                               f"(trump {trump.to_char()})")
    # Sign off at 4-of-trump if legal and we haven't already passed it.
    if last_natural.level < 4 or (last_natural.level == 4
                                  and _CUEBID_SUIT_RANK.get(
                                      last_natural.suit, -1)
                                  < _CUEBID_SUIT_RANK[trump]):
        return bid(4, trump,
                   why=f"4{trump.to_char()}: no more first-round "
                       f"controls to show after partner's cuebid")
    return None


def _maybe_initiate_cuebid(state: 'AuctionState', e: 'HandEval',
                           trump: Suit) -> Optional[Bid]:
    """At a 4NT-launch site, decide whether to start cuebidding first.

    Caller convention: called by `_opener_rebid` / `_generic_responder_rebid`
    just before they would jump to 4NT for RKC. Returns a cuebid Bid
    if we should cuebid the cheapest first-round side-suit control
    instead; returns None if there's nothing to show (no first-round
    side controls) — caller then proceeds with its 4NT launch.

    `trump` must be a major (we only cuebid majors in this MVP).

    Guard: only initiate cuebidding when trump has been established
    at the 3-level (raise or jump-raise) — at the 1-level a "cuebid"
    in the trump's overlapping suit (e.g. 2C after Precision 1C-1H)
    would collide with system bids that have natural / artificial
    meanings. Italian cuebidding only makes sense AFTER trump-set.
    """
    if trump not in (Suit.HEARTS, Suit.SPADES):
        return None
    ctx = derive_context(state)
    if ctx.trump is None or ctx.trump.suit != trump:
        return None
    # JACOBY_2NT auctions have their own structured opener-response
    # framework (Phase 4 plan element). Don't start cuebidding from
    # the Italian path — the Jacoby 2NT path will be handled separately.
    if ctx.trump.mechanism == TrumpMechanism.JACOBY_2NT:
        return None
    fr = _first_round_controls(e)
    # Drop trump (we have the trump suit's "control" by virtue of
    # holding 5+ trumps usually — that's RKC's job, not the cuebid
    # phase).
    fr.discard(trump)
    if not fr:
        return None
    # Find the last natural bid we need to outrank.
    last_natural = None
    for _s, b in reversed(state.bids):
        if b.is_pass or b.is_double or b.is_redouble:
            continue
        last_natural = b
        break
    if last_natural is None:
        return None
    cuebid = _cheapest_cuebid(trump, last_natural.level,
                              last_natural.suit, fr, excluded=set())
    if cuebid is None:
        return None
    lvl, suit = cuebid
    return bid(lvl, suit, alert=True,
               why=f"Cuebid: 1st-round control in {suit.to_char()} "
                   f"(Italian, trump {trump.to_char()})")


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


def _partnership_has_reached_game(state: AuctionState) -> bool:
    """True iff a game-or-higher contract has been bid by either
    partner. Used to know when a sticky GF can stand down.

    Game thresholds: 3NT, 4 of a major, 5 of a minor (or any 6/7).
    Doubles/redoubles are ignored — they don't satisfy the GF.
    """
    for b in state.my_bids + state.partner_bids:
        if b.is_pass or b.is_double or b.is_redouble:
            continue
        if b.suit is None:
            continue
        if b.level >= 6:
            return True
        if b.suit == Suit.NOTRUMP and b.level >= 3:
            return True
        if b.suit in (Suit.HEARTS, Suit.SPADES) and b.level >= 4:
            return True
        if b.suit in (Suit.CLUBS, Suit.DIAMONDS) and b.level >= 5:
            return True
    return False


def _is_partner_signoff_in_game(state: AuctionState) -> bool:
    """True iff partner's LAST bid is a sign-off in a known game
    contract. Distinguishes 'partner forced us to game and we just
    accepted' from 'partner is still developing the auction'.
    Conservative: only the obvious game contracts count, and only
    when partner placed it themselves on their most recent turn."""
    if not state.partner_bids:
        return False
    pl = state.partner_bids[-1]
    if pl.is_pass or pl.is_double or pl.is_redouble:
        return False
    if pl.suit is None:
        return False
    if pl.suit == Suit.NOTRUMP and pl.level >= 3:
        return True
    if pl.suit in (Suit.HEARTS, Suit.SPADES) and pl.level >= 4:
        return True
    if pl.suit in (Suit.CLUBS, Suit.DIAMONDS) and pl.level >= 5:
        return True
    return False


def _law_competitive_bid(state, e) -> Optional[Tuple[int, Suit]]:
    """Law of Total Tricks for competitive raises.

    Returns (level, suit) of a competitive bid if LAW says we should
    compete past opps' last bid; None otherwise.

    The LAW principle (Cohen 1992): the total number of tricks
    available equals the total trumps both sides hold. Practically:
    if our partnership has N trumps combined, we can safely bid to
    the (N - 6)-trick level — i.e., 8 trumps → 2-level, 9 trumps →
    3-level, 10 trumps → 4-level.

    Conservative implementation:
      1. Identify our trump suit (a suit my side has both bid AND
         raised, OR the suit partner raised me in).
      2. Count combined trumps using my actual length + a CONSERVATIVE
         estimate of partner's promised length (3 for a simple major
         raise, 4 for a limit raise, 5 for a preempt).
      3. Find opps' latest bid level (any non-pass non-double bid by
         either opponent).
      4. If combined trumps ≥ opps_level + 7 (one more than LAW
         strictly requires — adds a margin for fluky distributions),
         AND we haven't already passed game (don't compete to 5M),
         bid (opps_level + 1) of our trump suit.

    This conservative form will NEVER bid a contract we can't make
    on textbook trump counts. It only fires when biq is currently
    PASSING and LAW says compete is OK.
    """
    if state.opening_bid is None:
        return None
    # 1. Identify our trump suit.
    our_trump = None
    partner_min_trumps = 0
    # Case A: I opened a major, partner raised it.
    if (state.opener_seat == state.seat
            and state.opening_bid.suit in (Suit.HEARTS, Suit.SPADES)
            and state.partner_bids):
        first_pb = state.partner_bids[0]
        if (first_pb.suit == state.opening_bid.suit
                and not first_pb.is_pass):
            our_trump = state.opening_bid.suit
            # Raise to 2M = 3+ in 5cM systems, 4+ in Acol (4cM)
            if first_pb.level == 2:
                partner_min_trumps = 3
            elif first_pb.level == 3:
                # Limit raise OR preemptive (system-dependent).
                # Conservative: assume 4-card support.
                partner_min_trumps = 4
            elif first_pb.level == 4:
                partner_min_trumps = 5
            else:
                return None
    # Case B: partner opened a major, I raised.
    elif (state.opener_seat == state.seat.partner()
            and state.opening_bid.suit in (Suit.HEARTS, Suit.SPADES)
            and state.my_bids):
        my_first = state.my_bids[0]
        if (my_first.suit == state.opening_bid.suit
                and not my_first.is_pass):
            our_trump = state.opening_bid.suit
            # My length is my actual count; partner promised 5+
            # for a major opening (5-card-major systems) or 4+ (Acol).
            partner_min_trumps = 4  # conservative
    # Case C: an OPPONENT opened; partner OVERCALLED a major and I have
    # support. The overcalled suit is our trump (an overcall promises 5+),
    # so 4+ support is a 9+-card fit — LAW lets us compete rather than sell
    # out. (2428-54: partner overcalled 1H then rebid 3H, I hold 5 hearts,
    # opps reach 3S; LAW → 4H, a cold game.) Held to a STRICTER bar than the
    # opened-major cases (opp_level + 7, and 4+ of my own trumps) because an
    # overcall's strength is wider than an opening — the looser +6 bar
    # over-competed into failing slam-deck contracts.
    # Case C is a distributional LAW raise (fit + shape, modest values). A
    # strong advancer uses constructive bidding instead — and gating on
    # hcp keeps Case C out of slam auctions, where the looser competing
    # otherwise pushed biq past makeable slams on the slam deck.
    case_c = False
    if (our_trump is None
            and e.hcp <= 11
            and state.opener_seat is not None
            and state.opener_seat not in (state.seat, state.seat.partner())):
        for pb in state.partner_bids:
            if pb.is_pass or pb.suit not in (Suit.HEARTS, Suit.SPADES):
                continue
            if e.suit_lengths.get(pb.suit, 0) >= 4:
                our_trump = pb.suit
                partner_min_trumps = 5  # overcall promises 5+
                case_c = True
            break
    if our_trump is None:
        return None
    my_trumps = e.suit_lengths.get(our_trump, 0)
    combined = my_trumps + partner_min_trumps
    # 2. Find opps' highest level among all their non-pass bids.
    opp_level = 0
    opp_bid_recent = False
    for _seat, b in state.bids:
        if _seat == state.seat or _seat == state.seat.partner():
            continue
        if b.is_pass or b.is_double or b.is_redouble:
            continue
        if b.suit is None:
            continue
        if b.level > opp_level:
            opp_level = b.level
    if opp_level == 0:
        return None
    # 3. Is the most recent bid in the auction from an opponent? If
    # not, LAW doesn't apply here — partner's last action governs.
    for _seat, b in reversed(state.bids):
        if b.is_pass:
            continue
        if _seat in (state.seat, state.seat.partner()):
            return None  # most recent bid was ours
        opp_bid_recent = True
        break
    if not opp_bid_recent:
        return None
    # 4. LAW compete: textbook says combined ≥ opps_level + 6
    #    means we can safely bid (opps_level + 1) of our trumps —
    #    i.e., 9 trumps justifies competing to 3-level. Conservative
    #    layer: also require my own trump count ≥ 3 (avoid bidding
    #    on a doubleton when partner's promised trumps are nominal).
    margin = 7 if case_c else 6        # Case C (overcall) held stricter
    if combined < opp_level + margin:
        return None
    if my_trumps < (4 if case_c else 3):
        return None
    # Don't push past game level.
    next_level = opp_level + 1
    if our_trump in (Suit.HEARTS, Suit.SPADES) and next_level > 4:
        return None
    if our_trump in (Suit.CLUBS, Suit.DIAMONDS) and next_level > 5:
        return None
    # Don't go BACKWARDS from where we already are.
    our_highest = 0
    for _seat, b in state.bids:
        if _seat not in (state.seat, state.seat.partner()):
            continue
        if b.is_pass or b.suit != our_trump:
            continue
        if b.level > our_highest:
            our_highest = b.level
    if next_level <= our_highest:
        return None
    return (next_level, our_trump)


def _our_side_opened_strong_2c(state: AuctionState, system) -> bool:
    """True if MY partnership opened a strong (game-forcing) 2♣. SAYC and
    Acol use 2♣ as the GF artificial bid, so the auction cannot stop
    below game — even in a contested auction where partner doubled or
    overcalled instead of giving a positive response (which is where
    ctx.gf_established can miss it). Precision's 2♣ is a limited
    long-club bid, NOT game-forcing, so exclude it."""
    op = state.opening_bid
    if op is None or op.is_pass:
        return False
    if not (op.level == 2 and op.suit == Suit.CLUBS):
        return False
    os = state.opener_seat
    if os is None or state.seat is None:
        return False
    if os != state.seat and os != state.seat.partner():
        return False  # the 2♣ opener is an opponent, not my side
    name = getattr(system, "name", "") or ""
    if "Precision" in name or "P90" in name:
        return False
    return True


def _partner_was_forcing(state: AuctionState) -> bool:
    """Detect a force partner just placed on us. Conservative — only
    returns True for unambiguous forcing sequences so the sanity
    wrapper doesn't fire on debatable cases.

    Phase D: GF detection now reads from `ctx.gf_established` (the
    canonical truth from AuctionContext). Local logic preserves the
    "reached game" / "partner signed off" gates, since those are
    auction-position-specific rather than GF-state-specific.

      * Partner's 2/1 GF response → handled by ctx.gf_established.
      * Strong artificial 1C / 2C + positive → handled by ctx.
      * Jump shift → handled by ctx.
      * Partner's reverse → FORCING_ONE_ROUND in ctx; we still
        return True here so the safety net fires.
      * Splinter, opener jump-shift, inverted minor — kept local
        until those triggers move into derive_context.
    """
    if not state.partner_bids:
        return False
    pl = state.partner_bids[-1]
    if pl.is_pass or pl.is_double or pl.is_redouble:
        return False
    op = state.opening_bid
    if op is None:
        return False

    # --- Phase D: read GF from context -------------------------
    # Once GF is established, no pass below game is legal until the
    # partnership has actually bid game (or partner signed off).
    # The interference gate from the legacy "my 2/1 GF" branch is
    # preserved by only firing when the auction was uncontested.
    no_interference = not state.rho_bids and not state.lho_bids
    ctx = derive_context(state)
    if ctx.gf_established and no_interference:
        if not _partnership_has_reached_game(state):
            if not _is_partner_signoff_in_game(state):
                return True
    # Even with interference, partner's GF-establishing bid still
    # binds opener (the original opening side). Restrict to opener.
    if (ctx.gf_established
            and state.opener_seat == state.seat
            and not _partnership_has_reached_game(state)
            and not _is_partner_signoff_in_game(state)):
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

    # Splinter: alerted JUMP in a NEW suit (level ≥ 3) — must be
    # different from opener's suit, from any prior partner bid,
    # AND actually be a jump (not just a level-3 bid that happens
    # to be the cheapest legal call). The cheapest-legal check
    # rules out false positives:
    #   * 2NT-3H Jacoby transfer (level 3 IS cheapest in hearts) —
    #     deal #61 (seed 7371) had N open 2NT, S transfer 3H;
    #     biq's splinter detection triggered safe_forced_bid →
    #     bid 4H (Sanity: raise partner's suit) for 4H-S going
    #     down (-14 IMP).
    #   * Bergen 3M in opener's own major (excluded by op.suit
    #     check below).
    #   * Any other "cheapest legal" alerted convention.
    if (pl.alert and pl.level >= 3
            and pl.suit is not None
            and pl.suit != Suit.NOTRUMP
            and (op.suit is None or pl.suit != op.suit)
            and pl.suit not in [b.suit for b in state.partner_bids[:-1]
                                if b.suit is not None]):
        # Verify pl is a jump — find pl's index, compute cheapest
        # legal level for pl.suit at that point.
        partner = state.seat.partner()
        pl_idx = None
        for i in range(len(state.bids) - 1, -1, -1):
            sb_seat, sb = state.bids[i]
            if sb_seat == partner and not sb.is_pass:
                pl_idx = i
                break
        highest_lvl, highest_suit = 0, None
        if pl_idx is not None:
            for _seat, b in state.bids[:pl_idx]:
                if b.is_pass or b.is_double or b.is_redouble:
                    continue
                if b.suit is None:
                    continue
                if (b.level > highest_lvl
                        or (b.level == highest_lvl
                            and highest_suit is not None
                            and _BID_RANK[b.suit] > _BID_RANK[highest_suit])):
                    highest_lvl, highest_suit = b.level, b.suit
        if highest_suit is None:
            cheapest = 1
        elif _BID_RANK[pl.suit] > _BID_RANK[highest_suit]:
            cheapest = highest_lvl
        else:
            cheapest = highest_lvl + 1
        if pl.level >= cheapest + 1:
            return True

    # Opener's jump-shift: partner opened, I responded, partner's
    # rebid is a NEW suit at one level higher than necessary. By
    # textbook this shows 18-19+ HCP and is game-forcing. Without
    # this gate, biq's responder treats the jump-shift like a
    # normal new-suit rebid and passes when minimum (deal #29:
    # opener 19-HCP 3C jump-shift met with PASS for -10 IMP).
    if (state.opener_seat == state.seat.partner()
            and len(state.partner_bids) == 2
            and pl.suit is not None
            and pl.suit != Suit.NOTRUMP
            and op is not None
            and op.suit is not None
            and op.suit != Suit.NOTRUMP
            and pl.suit != op.suit
            and len(state.my_bids) == 1
            and state.my_bids[0].suit is not None
            and pl.suit != state.my_bids[0].suit):
        # Compute the cheapest level pl.suit COULD have been bid
        # at, given the auction state JUST BEFORE pl was made. If
        # pl.level is one (or more) higher than that, it's a jump.
        # Find pl's position in state.bids, then look at everything
        # before it for the highest strain-bid.
        partner = state.seat.partner()
        # Index of partner's last call in state.bids — that's pl.
        pl_idx = None
        for i in range(len(state.bids) - 1, -1, -1):
            sb_seat, sb = state.bids[i]
            if sb_seat == partner and not sb.is_pass:
                pl_idx = i
                break
        highest_lvl, highest_suit = 0, None
        if pl_idx is not None:
            for _seat, b in state.bids[:pl_idx]:
                if b.is_pass or b.is_double or b.is_redouble:
                    continue
                if b.suit is None:
                    continue
                if (b.level > highest_lvl
                        or (b.level == highest_lvl
                            and highest_suit is not None
                            and _BID_RANK[b.suit] > _BID_RANK[highest_suit])):
                    highest_lvl, highest_suit = b.level, b.suit
        if highest_suit is None:
            cheapest = 1
        elif _BID_RANK[pl.suit] > _BID_RANK[highest_suit]:
            cheapest = highest_lvl
        else:
            cheapest = highest_lvl + 1
        if pl.level >= cheapest + 1:
            if not _partnership_has_reached_game(state):
                if not _is_partner_signoff_in_game(state):
                    return True

    # Inverted minor raise: 1m-(2m alerted) — partner's 2-of-my-
    # minor at the 2-level is forcing for one round (some
    # partnerships GF, some F1). Without this, opener with min
    # passes the inverted raise and lands in 2m partscore.
    # Deal #66 (analysis seed 7371 deal 2): N (18 HCP balanced
    # + 5 clubs) responds 2C inverted to S's 1C; biq's S (12
    # HCP) passed for 2C-S +130 instead of pushing toward game.
    # Aggregate diff loss: ~520 IMP across 5 EW partners.
    if (state.opener_seat == state.seat
            and op.level == 1
            and op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and len(state.partner_bids) == 1
            and pl.alert
            and pl.level == 2
            and pl.suit == op.suit):
        if not _partnership_has_reached_game(state):
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
    # Textbook discipline: never let the legalizer push past game.
    # Deal #31's 5HX disaster (-1100) was the bidder producing a
    # stale 4H raise after the partnership had already bid 4H —
    # legalizer happily bumped it to 5H, opps doubled, -1100. If
    # legalizing would push a suit bid past game level, the bidder
    # had no business making that call at all — pass instead. The
    # caller will substitute None → pass.
    is_game_now = (
        (b.suit == Suit.NOTRUMP and new_level >= 4)
        or (b.suit in (Suit.HEARTS, Suit.SPADES) and new_level >= 5)
        or (b.suit in (Suit.CLUBS, Suit.DIAMONDS) and new_level >= 6))
    was_game_already = (
        (b.suit == Suit.NOTRUMP and b.level >= 3)
        or (b.suit in (Suit.HEARTS, Suit.SPADES) and b.level >= 4)
        or (b.suit in (Suit.CLUBS, Suit.DIAMONDS) and b.level >= 5))
    if is_game_now and was_game_already:
        return None  # Don't escalate stale game-level bids.
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

        # 2b. Game-forcing 2C opening — our side opened a strong 2♣, so
        # the auction is game-forcing and must not die below game. This
        # catches CONTESTED 2♣ auctions where partner doubled/overcalled
        # rather than giving a positive response (e.g. 2C-(2D)-X-2H-(P)-
        # 3H, which the context can leave passable). _safe_forced_bid
        # raises the agreed/long suit to game.
        if (raw.is_pass
                and _our_side_opened_strong_2c(state, system)
                and not _partnership_has_reached_game(state)):
            sub = _safe_forced_bid(state, eval_, system)
            if sub is not None:
                return sub

        # 2c. Competitive: don't sell out below game when WE hold a known
        # long suit. biq's normal paths are too passive in CONTESTED
        # auctions (the live vs-Q-Plus test exposed this). A suit biq has
        # already bid and holds 6+ of is the safest thing to compete with,
        # so rebid it — but only at the 2- or 3-level (never push to game;
        # that's a values decision the normal path owns).
        if raw.is_pass and state.opp_overcalled and state.my_bids:
            for mb in state.my_bids:
                s = mb.suit
                if (s is None or s == Suit.NOTRUMP
                        or eval_.suit_lengths.get(s, 0) < 6):
                    continue
                ls = state.last_suit_bid
                if ls is None:
                    lvl = 1
                elif _BID_RANK[s] > _BID_RANK[ls]:
                    lvl = state.last_level
                else:
                    lvl = state.last_level + 1
                if 2 <= lvl <= 3:
                    cand = bid(lvl, s,
                               why=f"Compete: rebid own 6+ {s.to_char()} "
                                   f"(don't sell out below game)")
                    if _is_legal_bid(cand, state):
                        return cand

        # 2d. Opener must not pass partner's FORCING new-suit response.
        # A non-jump new suit by responder (1D-1S, 1H-2C, …) is forcing —
        # opener has to rebid. biq's opener-rebid path can fall through to
        # pass on awkward shapes (e.g. 1D-1S with a 2-4-5-2 15-count, no
        # spade support and no comfortable rebid). Narrow: opener's FIRST
        # rebid, partner responded exactly once in a new suit, uncontested,
        # below game. _safe_forced_bid finds the rebid (raise / own suit /
        # NT).
        if (raw.is_pass
                and state.opener_seat == state.seat
                and len(state.my_bids) == 1
                and len(state.partner_bids) == 1
                and not state.opp_overcalled
                and not _partnership_has_reached_game(state)):
            pl = state.partner_bids[0]
            op = state.opening_bid
            if (pl.suit is not None and pl.suit != Suit.NOTRUMP
                    and op is not None and pl.suit != op.suit):
                sub = _safe_forced_bid(state, eval_, system)
                if sub is not None:
                    return sub

        # 2e. Pull partner's penalty-doubled suit to my own 6+ suit. When
        # RHO penalty-doubles partner's natural suit bid and I'm short in
        # that suit but hold a 6+ suit of my own, sitting a likely-misfit
        # doubled contract is a disaster — run to my suit instead. (6886-44
        # −1700: partner overcalled 3♣, West doubled, advancer sat holding
        # ♦AKT965 instead of pulling to 3♦.) Cheapest legal level, capped
        # at 4 (a pull is a rescue, not a game try).
        if raw.is_pass:
            nonpass = [(s, b) for s, b in state.bids if not b.is_pass]
            if len(nonpass) >= 2:
                (dbl_seat, dbl), (pb_seat, pb) = nonpass[-1], nonpass[-2]
                partner = state.seat.partner()
                if (dbl.is_double
                        and dbl_seat not in (state.seat, partner)
                        and pb_seat == partner
                        and pb.suit is not None and pb.suit != Suit.NOTRUMP
                        and not pb.is_double and not pb.is_redouble
                        and eval_.suit_lengths.get(pb.suit, 0) < 3):
                    best = None
                    for s in (Suit.SPADES, Suit.HEARTS,
                              Suit.DIAMONDS, Suit.CLUBS):
                        if s == pb.suit:
                            continue
                        if eval_.suit_lengths.get(s, 0) >= 6 and (
                                best is None
                                or eval_.suit_lengths[s]
                                > eval_.suit_lengths[best]):
                            best = s
                    if best is not None:
                        for lvl in (pb.level, pb.level + 1):
                            if lvl > 4:
                                break
                            cand = bid(lvl, best,
                                       why=f"Pull partner's doubled "
                                           f"{pb.suit.to_char()} to my 6+ "
                                           f"{best.to_char()} "
                                           f"({eval_.suit_lengths[best]} cards)")
                            if _is_legal_bid(cand, state):
                                return cand

        # 2f. Advance partner's Unusual 2NT overcall off NT — never SIT a
        # two-suited 2NT, doubled or not. An Unusual 2NT = 5-5 in the two
        # lowest-ranked unbid suits; passing plays a misfit NT, and 2NT
        # DOUBLED with shortness in opener's suit is a disaster (4399-58
        # −800: South's 5-5 red Unusual 2NT over 1♣ doubled, North sat
        # instead of 3♦). Bid the longer shown suit at the 3-level. Fires
        # only when biq would otherwise pass and hasn't advanced yet, and
        # only while the 2NT is live (last call = the 2NT, or an opponent's
        # double of it — if an opponent has bid OVER it, leave it to the
        # competitive/LAW logic). (Check 2e is the suit-bid sibling.)
        if (raw.is_pass and not state.my_bids
                and state.opening_bid is not None
                and state.opening_bid.level == 1
                and state.opening_bid.suit is not None
                and state.opening_bid.suit != Suit.NOTRUMP
                and state.partner_bids
                and state.partner_bids[0].level == 2
                and state.partner_bids[0].suit == Suit.NOTRUMP):
            partner = state.seat.partner()
            opener_is_opp = state.opener_seat not in (state.seat, partner)
            nonpass = [(s, b) for s, b in state.bids if not b.is_pass]
            live = False
            if nonpass and opener_is_opp:
                ls, lb = nonpass[-1]
                if ls == partner and lb.level == 2 and lb.suit == Suit.NOTRUMP:
                    live = True                      # undoubled
                elif (lb.is_double and ls not in (state.seat, partner)
                        and len(nonpass) >= 2):
                    ps, pbd = nonpass[-2]
                    if (ps == partner and pbd.level == 2
                            and pbd.suit == Suit.NOTRUMP):
                        live = True                  # doubled
            if live:
                op_suit = state.opening_bid.suit
                shown = sorted(
                    (s for s in (Suit.CLUBS, Suit.DIAMONDS,
                                 Suit.HEARTS, Suit.SPADES) if s != op_suit),
                    key=lambda s: _BID_RANK[s])[:2]
                best = max(shown, key=lambda s: eval_.suit_lengths.get(s, 0))
                for lvl in (3, 4):
                    cand = bid(lvl, best,
                               why=f"Advance partner's Unusual 2NT to "
                                   f"{best.to_char()} "
                                   f"({eval_.suit_lengths.get(best, 0)} cards)")
                    if _is_legal_bid(cand, state):
                        return cand

        # 3. Law-of-Total-Tricks competitive: if biq's normal path
        # decided to pass but LAW says our partnership's combined
        # trump count justifies one more competitive bid, override.
        # Conservative — only fires when biq is currently passing,
        # the most recent action was an opp's bid, and partner has
        # raised our suit (so combined trump count is known).
        if raw.is_pass:
            law = _law_competitive_bid(state, eval_)
            if law is not None:
                lvl, suit = law
                law_bid = bid(lvl, suit,
                              why=f"LAW compete: {lvl}{suit.to_char()} "
                                  f"(combined trumps justify one more "
                                  f"competitive level over opps)")
                if _is_legal_bid(law_bid, state):
                    return law_bid

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

    # Gerber 4C ace-ask after partner's opening 1NT/2NT/3NT — Phase B
    # re-enables this with context-backed strict detection.
    grb = _try_gerber_pipeline(state, eval_, system)
    if grb is not None:
        return grb

    # Quantitative 4NT — opener's accept/decline of partner's 4NT
    # slam invite after our NT rebid.
    qnt = _try_quantitative_4nt_pipeline(state, eval_, system)
    if qnt is not None:
        return qnt

    # Grand-slam force (5NT after major-trump-set, no prior 4NT) —
    # responder shows 2-of-top-3 trump honours: 7 of trump if yes,
    # 6 of trump if no.
    gsf = _try_grand_slam_force_pipeline(state, eval_, system)
    if gsf is not None:
        return gsf

    # Bergen-style asking bid (Phase 5) — 4D trump-quality ask. Must
    # be checked before the cuebid pipeline because 4D could equally
    # be a side-suit cuebid; the asking-bid classifier is stricter
    # (requires prior cuebid exchange).
    ab = _try_asking_bid_pipeline(state, eval_, system)
    if ab is not None:
        return ab

    # Italian-cuebid continuation — fires when partner has cuebid in
    # a trump-set major sequence and it's our turn to either continue
    # cuebidding or escalate to 4NT RKC.
    cb = _try_cuebid_pipeline(state, eval_, system)
    if cb is not None:
        return cb

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
        # If I've already overcalled, this is my own rebid.
        # Without this guard, the dispatcher routes me back through
        # _overcall (when partner hasn't acted yet) and I cheerfully
        # repeat the same suit at the same level — which is illegal
        # and gets pass-substituted by the sanity wrapper.
        if state.my_bids:
            first_mine = state.my_bids[0]
            if (not first_mine.is_pass
                    and not first_mine.is_double
                    and not first_mine.is_redouble
                    and first_mine.suit is not None):
                return _overcaller_rebid(state, eval_, system)
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
            if rho_intervened:
                return _respond_to_precision_1c_competitive(
                    state, e, system)
            return _respond_to_precision_1c(state, e)
        if op.level == 2 and op.suit == Suit.CLUBS:
            return _respond_to_precision_2c(state, e)
        if (op.level == 2 and op.suit == Suit.DIAMONDS
                and not rho_intervened
                and any(k.startswith("B-2D.Precision")
                        for k in system.raw_rules)):
            return _respond_to_precision_2d(state, e, system)
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

def _respond_to_precision_1c_competitive(state, e: HandEval, system) -> Bid:
    """Precision 1C-(RHO acts)-? — responder after intervention.

    The strong 1C is artificial (16+ HCP), so:
      * we never "raise" 1C (it's not natural clubs)
      * Pass = 0-7 (responder is broke; opener can still act with 16+)
      * negative X = 8+ HCP, no clear suit/NT bid
      * NT bids show stopper in opps' suit:
          2NT = 8-11 balanced with stopper
          3NT = 12+ balanced with stopper
      * new-suit positives at the lowest legal level (5+ in suit, 8+ HCP,
        game-forcing because partner already has 16+).
    Illegal bids fall through to pass; the harness's legality filter
    will convert any out-of-range NT to pass as a safe fallback.
    """
    hcp = e.hcp
    if hcp <= 7:
        return passb(why="Precision 1C-(intervention): 0-7 HCP, pass")

    overcall = state.rho_bids[-1]
    # Doubles / NT overcalls: route to the un-contested logic. After a
    # takeout-X or NT call, the opps haven't bid a suit, so the response
    # framework from the un-contested 1C still applies (with a redouble
    # available — but biq's main paths handle that via the doubled-state
    # dispatcher, not here).
    if overcall.is_double or overcall.suit is None:
        return _respond_to_precision_1c(state, e)

    overcall_suit = overcall.suit
    overcall_level = overcall.level

    # Balanced + stopper in opps' suit → NT response. Opener's rebid
    # logic is now intervention-aware, so 2NT (8-11) and 3NT (12+) both
    # land in their textbook meanings without triggering phantom slams.
    if e.is_balanced and _has_stopper(e, overcall_suit):
        if hcp >= 12:
            return bid(3, Suit.NOTRUMP, alert=True,
                       why=f"Precision 1C-({overcall_level}"
                           f"{overcall_suit.to_char()}): 12+ HCP "
                           f"balanced with {overcall_suit.to_char()} "
                           f"stopper, positive to game")
        return bid(2, Suit.NOTRUMP, alert=True,
                   why=f"Precision 1C-({overcall_level}"
                       f"{overcall_suit.to_char()}): 8-11 HCP "
                       f"balanced with {overcall_suit.to_char()} "
                       f"stopper, positive (invite)")

    # 5+ in an unbid suit at the cheapest legal level — positive,
    # game-forcing (opener has 16+, combined values are ≥ game).
    for new_suit in (Suit.HEARTS, Suit.SPADES,
                     Suit.DIAMONDS, Suit.CLUBS):
        if new_suit == overcall_suit:
            continue
        if e.suit_lengths.get(new_suit, 0) < 5:
            continue
        # Cheapest legal level above the current contract.
        if (state.last_suit_bid is None
                or _BID_RANK[new_suit] > _BID_RANK[state.last_suit_bid]):
            level = state.last_level
        else:
            level = state.last_level + 1
        if 1 <= level <= 4:
            return bid(level, new_suit, alert=True,
                       why=f"Precision 1C-({overcall_level}"
                           f"{overcall_suit.to_char()}): 8+ HCP, "
                           f"5+ {new_suit.to_char()}, positive "
                           f"(game-forcing)")

    # Negative double — 8+ HCP, no clean suit/NT bid. Respects the
    # system's Sputnik cap.
    neg_max = _negative_double_max_level(system)
    if overcall_level <= neg_max:
        return double(
            why=f"Precision 1C-({overcall_level}"
                f"{overcall_suit.to_char()}): negative X, 8+ HCP, "
                f"no clear positive bid (Sputnik ≤{neg_max})")

    # No clean call available — pass and let opener bid again.
    return passb(
        why=f"Precision 1C-({overcall_level}"
            f"{overcall_suit.to_char()}): 8+ HCP but no legal "
            f"positive call below Sputnik cap")


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

    # 16+ slam-zone with no major fit.
    # With a 5+ NON-DIAMOND side suit, jump-shift to show extras
    # plus the suit (textbook game-force inquiry — opener can
    # raise, bid NT, or rebid own suit). Without a useful side
    # suit, 2NT shows 16+ balanced slam-exploration.
    # Aggregate analysis deal #66 (seed 7371 deal 2): N had 18
    # HCP 2-3-3-5 with 5 clubs over partner's 1D; biq bid 2NT
    # and opener (11 HCP, no extras) passed for 2NT-N — Q-Plus
    # reached 3NT-S via jump-shift sequence.
    for side in (Suit.CLUBS, Suit.HEARTS, Suit.SPADES):
        if e.suit_lengths.get(side, 0) >= 5:
            return bid(3 if side == Suit.CLUBS
                       else 2, side, alert=True,
                       why=f"Precision 1D-{('3' if side==Suit.CLUBS else '2')}"
                           f"{side.to_char()}: jump-shift, 16+ HCP + "
                           f"5+ {side.to_char()} (GF)")
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


def _respond_to_precision_2d(state, e: HandEval, system) -> Bid:
    """Response to a Precision 2♦ three-suiter (11-15 HCP, 4-3 in the
    majors at minimum, 0-1 diamond).

        Pass         = useless hand with diamond stack (rare; partner is
                       short, so pass usually defends poorly — falls
                       through only when no major is biddable).
        2H / 2S      = 0-7, 3+ in better major, sign-off.
        2NT (alert)  = 13+ relay asking opener's shortness and strength.
        3H / 3S      = 8-12 invitational with 3+ in the major.
        4H / 4S      = direct game with major fit and slam-light values.
    """
    hcp = e.hcp
    sp = e.suit_lengths[Suit.SPADES]
    hr = e.suit_lengths[Suit.HEARTS]

    if hcp >= 13:
        return bid(2, Suit.NOTRUMP, alert=True,
                   why=f"Precision 2D-2NT relay: {hcp} HCP, asking shape")

    if 8 <= hcp <= 12:
        if sp >= 3 and sp >= hr:
            return bid(3, Suit.SPADES, alert=True,
                       why=f"Precision 2D-3S: {hcp} HCP inv, {sp}cS fit")
        if hr >= 3:
            return bid(3, Suit.HEARTS, alert=True,
                       why=f"Precision 2D-3H: {hcp} HCP inv, {hr}cH fit")

    if sp >= 3 and sp >= hr:
        return bid(2, Suit.SPADES,
                   why=f"Precision 2D-2S: weak escape, {sp}cS fit")
    if hr >= 3:
        return bid(2, Suit.HEARTS,
                   why=f"Precision 2D-2H: weak escape, {hr}cH fit")

    return passb(why="Precision 2D: weak with diamond stack, pass")


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

    # 0-pass_max with no long major → just pass UNLESS we have a
    # 6+ minor and want to escape to a known fit. Classic SAYC:
    # 1NT-3m = preemptive sign-off (6+ in the minor, 0-7 HCP); the
    # long minor will play better than 1NT with a weak hand and no
    # entries to it. Deal #51 (seed 7371): N had 8 HCP + 6 diamonds
    # over partner's 1NT → biq passed for 1NT-S, Q-Plus jumped to
    # 3D-N making 9 tricks for +150 (-11 IMP).
    if hcp <= t["pass_max"] and not e.five_card_majors:
        # Cap the preemptive 3m at 7 HCP regardless of NT range.
        # For weak-NT systems (Acol 12-14) pass_max can reach 10,
        # but 3-of-a-minor as preempt should stay at the standard
        # 0-7 HCP range — at 8+ we prefer Stayman or 2NT invite.
        # Deal #44 (seed 7371): E had 9 HCP + 6 clubs + 4 spades +
        # void hearts vs partner's 1NT; biq's 3C pre-empt missed
        # the spade fit Stayman would find.
        if hcp <= 7:
            for m in (Suit.DIAMONDS, Suit.CLUBS):
                if e.suit_lengths.get(m, 0) >= 6:
                    return bid(3, m,
                               why=f"3{m.to_char()}: preemptive 6+ "
                                   f"minor sign-off after 1NT "
                                   f"(0-7 HCP)")
        return passb(why=f"0-{t['pass_max']} HCP, no 4cM/5cM → pass 1NT")

    # 5-4 in the majors + game-going values → Stayman BEFORE Jacoby
    # transfer. The 5-card major is hidden by a transfer (showing
    # only the 5-card suit); Stayman finds the 4-4 fit if opener
    # has it, then Smolen (3-of-LOWER-major over 2D) shows the
    # 5-4 distribution. Deal 33 in slam corpus 59517: S held 5S +
    # 4H + 1D + 3C + 13 HCP; old transfer-first logic stopped at
    # 2S after opener accepted, missing the 5-3 spade slam Q-Plus
    # reached via Stayman → Smolen → cuebid → RKC → 6S.
    has_5_4_majors = (
        (has_5H and e.suit_lengths[Suit.SPADES] == 4)
        or (has_5S and e.suit_lengths[Suit.HEARTS] == 4)
    )
    if has_5_4_majors and hcp >= 10:
        return bid(2, Suit.CLUBS, alert=True,
                   why=f"Stayman with 5-4 majors ({hcp} HCP) — Smolen "
                       f"3M over 2D if no fit")

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

    # Invitational with 6+ minor and NO 4-card major: prefer 3m
    # (signoff or invite — partnership agreement; here treated as
    # signoff style) over 2NT. 2NT promises balanced; an unbalanced
    # 6-3-2-2 or 6-3-3-1 hand misrepresents shape and misses the
    # better partscore in the long minor.
    # Base #2 seed 80719 (teaching deck idx=114): N had 8 HCP +
    # 6♦ + no 4cM; biq bid 2NT, opps pushed to 3C-E (-110), Q-Plus
    # bid 3D direct for +150 = -11 IMP per cell × multiple cells.
    if (t["invite_lo"] <= hcp <= t["invite_hi"]
            and not (has_4S or has_4H)
            and not has_5S and not has_5H):
        for m in (Suit.DIAMONDS, Suit.CLUBS):
            if e.suit_lengths.get(m, 0) >= 6:
                return bid(3, m,
                           why=f"3{m.to_char()}: 6+ {m.to_char()} "
                               f"with invitational values ({hcp} HCP) "
                               f"after partner's 1NT — better than 2NT "
                               f"(unbalanced shape)")

    # No major path → NT raises.
    if t["invite_lo"] <= hcp <= t["invite_hi"]:
        # Bottom-of-range invite with totally flat shape (no 5-card
        # suit) is too thin for a 14-16 NT opening — partner could
        # easily be minimum and we have no source of tricks. Q-Plus
        # passes seed=200 board 8 S (9 HCP, 2-3-4-4) here.
        has_5_card_suit = any(
            e.suit_lengths[s] >= 5
            for s in (Suit.CLUBS, Suit.DIAMONDS,
                      Suit.HEARTS, Suit.SPADES))
        if (hcp == t["invite_lo"]
                and system.one_nt_max_hcp <= 16
                and not has_5_card_suit):
            return passb(why=f"Pass {hcp} HCP flat vs "
                             f"{system.one_nt_max_hcp}-NT (no source)")
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

    # Weak with long suit → 2NT relay (signed off in 3 of own suit).
    # Only legal against a 2-level overcall — over (3X) the relay
    # would be below the overcall and is just skipped.
    if (overcall.level == 2
            and hcp <= 8
            and any(e.suit_lengths[s] >= 5 for s in
                    (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
                    if s != overcall_suit)):
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
    nt_min = getattr(system, "two_nt_min_hcp", nt_max - 1)
    # ----- Count-to-grand / count-to-slam (balanced responder) -----
    # When combined HCP guarantees the slam zone, leap directly to
    # 6NT / 7NT rather than going through Stayman/transfer. Even a
    # 4-4 major fit doesn't beat NT with 37+ HCP — finding the fit
    # risks tempo or wrong-strain landing. Conservative: use opener's
    # MIN HCP for the floor calculation; the slam grade if combined
    # is in range based on partner's worst-case range.
    if e.is_balanced or e.is_semi_balanced:
        combined_min = hcp + nt_min
        # Grand zone: 37+ combined HCP → 7NT direct.
        # Deal 44 (slam 95512): S 17 HCP balanced over N's 20 = 37
        # combined; Q-Plus leaped 7NT; biq stuck Stayman (-19 IMP).
        if combined_min >= 37:
            return bid(7, Suit.NOTRUMP,
                       why=f"7NT count: {hcp}+{nt_min}+ ≥ 37 combined "
                           f"(grand zone, balanced)")
        # Small slam zone: 33+ combined HCP. Skip Stayman when no
        # 4-card major is possible (already balanced + no 4cM = pure
        # 3-3-3-4-with-no-4cM is rare; usually 4cM exists). Be
        # conservative and only leap to 6NT when no 4-card major
        # AND combined ≥ 34 (a few HCP margin for the slam tricks).
        if (combined_min >= 34
                and e.suit_lengths.get(Suit.HEARTS, 0) < 4
                and e.suit_lengths.get(Suit.SPADES, 0) < 4):
            return bid(6, Suit.NOTRUMP,
                       why=f"6NT count: {hcp}+{nt_min}+ ≥ 34 combined, "
                           f"no 4-card major (small slam zone)")
    # 5-card major → transfer (2NT-3D=hearts, 2NT-3H=spades)
    if e.suit_lengths[Suit.HEARTS] >= 5:
        return bid(3, Suit.DIAMONDS, alert=True, why="Jacoby transfer to hearts (over 2NT)")
    if e.suit_lengths[Suit.SPADES] >= 5:
        return bid(3, Suit.HEARTS, alert=True, why="Jacoby transfer to spades (over 2NT)")
    # Stayman
    if e.suit_lengths[Suit.SPADES] == 4 or e.suit_lengths[Suit.HEARTS] == 4:
        return bid(3, Suit.CLUBS, alert=True, why="Stayman over 2NT")
    # Bare 0-4 → PASS partner's 2NT. After 2NT (20-21 HCP), responder
    # needs 5+ HCP to accept the invite to game (combined 25+ for
    # 3NT). With 0-4 the partnership is at 20-25, mostly insufficient;
    # the partscore is safer.
    # Base #2 (deck idx 1) seed 36866: N held S♠T97 H♠J8 D♠J7432
    # C♠983 (2 HCP) after S's 2NT. biq pushed to 3NT-S, contract went
    # down vul (NS-100). Q-Plus correctly passed → 2NT-S making
    # (NS+120). 5 IMP per cell × 25 cells = ~-125 IMP swing.
    if hcp <= 4:
        return passb(why=f"Pass 2NT: {hcp} HCP — combined < 25 for "
                         f"3NT, partscore safer")
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

    # Show a 4-card major at the 1-level over partner's 1m
    # opening. No upper HCP cap — even a 19-count responds 1H/1S
    # first to find a major fit before driving slam. The old cap
    # at 18 meant 19+ hands jumped to 2NT directly, missing the
    # major fit entirely (seed=42 board 8 in SAYC / French: E
    # had 2-4-3-4 with 19 HCP and bid 2NT instead of 1H,
    # leaving the auction stranded).
    if hcp >= 6:
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
    # 18+ slam-zone. The previous code bid 2NT — read by opener as
    # 11-12 invitational (passed with min!) and a massive underbid.
    # Deal #2 (seed 7371): N had 18 HCP balanced + 5 clubs over
    # partner's 1C; biq bid 2NT, opener passed for 2NT-N. Q-Plus
    # reached 6C-N making for -15 IMP.
    # Textbook: with 18+ HCP and partner's minor opening, options:
    #   * 5+ trump support  → jump to 3 of partner's minor (strong
    #     raise, slam interest) — opener with extras cuebids
    #   * 5+ non-minor suit → jump-shift to 2-of-side-suit (GF,
    #     slam interest)
    #   * Balanced with no useful side suit → direct 3NT (16-18
    #     to play; opener with 17+ explores slam)
    if e.suit_lengths.get(minor, 0) >= 5:
        # ALERT — strong raise of partner's minor (18+ HCP). Opener
        # cuebids with extras, signs off in 3NT/5m with min, or
        # asks for keycards with 4NT. Without the alert, opener
        # might treat 3m as preemptive (in inverted-minor systems)
        # and pass for a missed slam.
        return bid(3, minor, alert=True,
                   why=f"3{minor.to_char()}: 18+ HCP + 5-card "
                       f"support, strong raise / slam interest")
    if (e.longest_suit not in (minor, Suit.NOTRUMP)
            and e.suit_lengths.get(e.longest_suit, 0) >= 5):
        return bid(2, e.longest_suit, alert=True,
                   why=f"Jump-shift 2{e.longest_suit.to_char()}: "
                       f"18+ HCP, slam interest")
    return bid(3, Suit.NOTRUMP,
               why="3NT: 18+ balanced; opener with extras "
                   "may continue toward slam")


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

    # Raise partner's minor with 4+ support and modest values.
    # Comes AFTER the negative-double check: with the unbid major
    # the negative double is more descriptive; only fall to the
    # minor raise when the negative double doesn't apply
    # (e.g. responder has the wrong major or already bid it).
    # Seed=42 board 6: 1D-(1S)-? with W holding ♦KQJ6 + 8 HCP →
    # bid 2D (no 4-card heart to make negative double).
    minor_op = state.opening_bid.suit
    if (minor_op in (Suit.CLUBS, Suit.DIAMONDS)
            and e.suit_lengths.get(minor_op, 0) >= 4):
        target_level = max(2, overcall.level + 1
                           if _BID_RANK[minor_op] <= _BID_RANK[overcall_suit]
                           else overcall.level)
        if 6 <= hcp <= 9 and target_level <= 3:
            return bid(target_level, minor_op,
                       why=f"Competitive raise of partner's "
                           f"{minor_op.to_char()} ({hcp} HCP, "
                           f"4+ support)")
        if 10 <= hcp <= 12 and target_level + 1 <= 4:
            return bid(target_level + 1, minor_op,
                       why=f"Limit-raise jump in partner's "
                           f"{minor_op.to_char()} ({hcp} HCP, "
                           f"4+ support)")

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

    # Acol-style "up the line": when the system opens 4-card majors, a
    # 1♥ opening doesn't promise 5+ hearts, so responder with 4-4
    # majors and 6+ HCP shows the spade suit at the 1-level before
    # supporting hearts — opener may have 4 hearts and a 4-card
    # spade side suit that gives a 4-4 spade fit. Without this branch
    # responder jumps to 3♥ on 4-card support and the spade fit is
    # never found. (1♠ opener: this doesn't apply — no higher-ranking
    # major to introduce.)
    maj_min = getattr(system, 'one_major_card_min', 5)
    if (maj_min <= 4
            and major == Suit.HEARTS
            and e.suit_lengths[Suit.SPADES] >= 4
            and 6 <= hcp <= 17):
        return bid(1, Suit.SPADES,
                   why=f"Acol up-the-line: 1♠ over 1♥ with 4+♠ "
                       f"({hcp} HCP, finds 4-4 spade fit if "
                       f"opener has it)")

    # 4+ support → raise structures
    if fit >= 4:
        # Source-of-tricks check (Phase F): when responder has a 5+
        # side suit with 5+ HCP in it, that's a slam-going asset
        # better described via 2/1 GF than via splinter (which shows
        # shortness but hides the long suit). Deal 65 in slam corpus
        # 59517: S held 4H + 1S + 6D AQ + 2C, 13 HCP. Old splinter-
        # first logic bid 3S, dropping the slam-going diamond suit.
        # Q-Plus's S bids 2D (2/1 GF); the subsequent auction reaches
        # 7H via reverse + cuebid + RKC + king-ask + grand.
        has_source_of_tricks = any(
            e.suit_lengths[ss] >= 5 and e.suit_hcp[ss] >= 5
            and ss != major
            for ss in (Suit.CLUBS, Suit.DIAMONDS,
                       Suit.HEARTS, Suit.SPADES)
        )
        # Splinter 3+1 or 4+0 with 13-15 game values (but defer to
        # 2/1 GF when source-of-tricks is present).
        if not has_source_of_tricks:
            for short in (Suit.SPADES, Suit.HEARTS,
                           Suit.DIAMONDS, Suit.CLUBS):
                if short == major:
                    continue
                if e.suit_lengths[short] <= 1 and 13 <= hcp <= 15:
                    # Splinter bid: jump in shortness suit
                    level = 3 if _BID_RANK[short] > _BID_RANK[major] else 4
                    return bid(level, short, alert=True,
                               why=f"Splinter raise: 4+ "
                                   f"{major.to_char()}, shortness "
                                   f"{short.to_char()}")
        # Jacoby 2NT: 4+ support, GF (13+ HCP). Only fire when the
        # system has the convention enabled — wbridge5's SAYC has
        # "2NT Jacoby" unchecked, so for SAYC-wbridge5 a 13+ balanced
        # hand with 4+ trumps either splinters (handled above) or
        # leaps to game.
        if hcp >= 13 and system.has("A-1MA-Jacoby-2NT"):
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Jacoby 2NT: 4+ support, GF")
        # 2/1 GF with 4-card trump support + 5+-card side suit (with
        # source-of-tricks values): preserve room for slam exploration
        # by introducing the side suit at the 2-level instead of
        # jumping to 4M. Threshold lowered from 17 to 13 HCP (Phase F):
        # a 13-HCP responder with a strong 6-card minor opposite
        # opener's 1M is in the slam zone (combined 25+ HCP + 9-card
        # major fit + extra source = slam tries). Deal 65 in slam
        # corpus 59517: S held 4H + 6D AQ + 1S + 13 HCP; old code
        # jumped to 4H, dropping the slam exploration. Q-Plus reached
        # 7H grand via 2D-2S-3H-3S-4NT-5C-5D-5S-5NT-6D-7H.
        if (hcp >= 13
                and any(e.suit_lengths[s] >= 5
                        and e.suit_hcp[s] >= 5
                        and s != major
                        for s in (Suit.CLUBS, Suit.DIAMONDS,
                                   Suit.HEARTS, Suit.SPADES))):
            for s in (Suit.CLUBS, Suit.DIAMONDS):
                if (e.suit_lengths[s] >= 5
                        and e.suit_hcp[s] >= 5
                        and s != major):
                    return bid(2, s, alert=True,
                               why=f"2-over-1 GF in 5+{s.to_char()} "
                                   f"(slam try, 4+{major.to_char()} "
                                   f"+ source-of-tricks)")
            if (major == Suit.SPADES
                    and e.suit_lengths[Suit.HEARTS] >= 5
                    and e.suit_hcp[Suit.HEARTS] >= 5):
                return bid(2, Suit.HEARTS, alert=True,
                           why="2-over-1 GF in 5+H "
                               "(slam try, 4+S + source-of-tricks)")
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
        # Standard French (and other systems without Jacoby 2NT or
        # Precision's 3-card-2NT convention): with 11-12 HCP
        # balanced and 3-card major support, bid 2NT as a natural
        # invitational raise. Opener accepts to 4M with extras.
        # Seed=42 board 4 in French: S has 11 HCP + ♥Q74 + balanced
        # 3-3-3-4 → Q-Plus bids 2NT then 4H; bridgeIQ used to jump
        # 3H limit raise.
        if (11 <= hcp <= 12
                and e.is_balanced
                and not system.has("A-1MA-Jacoby-2NT")
                and not system.has("A-1MA-2NT.support-3-10-13")
                and not system.has("A-1MA-2NT.range-11-12")
                # Acol's `A-1MA-2NT.range-11-12` is already its
                # natural-2NT flag; if the system has neither
                # explicit flag, default to natural-NT invite
                # (matches Q-Plus's French behaviour).
                ):
            return bid(2, Suit.NOTRUMP,
                       why=f"Natural 2NT invite: 11-12 balanced + "
                           f"3-card {major.to_char()} support")
        # 2/1 GF with 5+ side suit takes PRIORITY over 1NT-forcing
        # when responder has 12+ HCP and a real side suit. The 1NT-
        # forcing branch is for SEMI-BALANCED 6-11/12 HCP with no
        # 5+ side suit; with 12+ HCP and a 5-card side, 2-over-1
        # GF is the textbook call (we can return to opener's major
        # via preference later — partnership stays in game-force).
        # Base #1 deck idx 180 seed 36866: S held S♠AK2 H♠JT752
        # D♠KJ9 C♠96 (12 HCP, 3-5-3-2) after N's 1S. biq bid 1NT
        # forcing → N rebid 2D → S passed → 2D-N (NS-100). Q-Plus
        # bid 2H GF → N 3D → S 3S preference → N 4S → game (NS+620).
        # Net -11 IMP per cell, 5 cells = -55 IMP just on this
        # bug-cluster.
        if (hcp >= 12
                and system.has("A-1MA-forcing-1NT")):
            for side in (Suit.CLUBS, Suit.DIAMONDS):
                if e.suit_lengths[side] >= 5 and side != major:
                    return bid(2, side, alert=True,
                               why=f"2/1 GF in 5+{side.to_char()} "
                                   f"({hcp} HCP, 3-card "
                                   f"{major.to_char()} support — "
                                   f"set trumps later)")
            if (major == Suit.SPADES
                    and e.suit_lengths[Suit.HEARTS] >= 5):
                return bid(2, Suit.HEARTS, alert=True,
                           why=f"2/1 GF in 5+♥ ({hcp} HCP, "
                               f"3-card ♠ support — set trumps "
                               f"later)")

        # 2/1 GF systems: with 3-card support and limit-raise values,
        # bid 1NT (forcing) instead of jumping to 3M. The forcing-1NT
        # response promises 6-12 HCP without 4-card support; opener
        # MUST rebid (showing 5+ in the major / second suit / 2NT
        # for a min balanced); responder follows up with a limit
        # raise via 3M on the next turn. Without this the 2/1 path
        # collapses to the SAYC limit raise and we lose the 2/1
        # GF discipline. (Q-Plus's `A-1MA-forcing-1NT` flag is the
        # signature of 2/1 GF.)
        if (10 <= hcp <= 12
                and system.has("A-1MA-forcing-1NT")):
            return bid(1, Suit.NOTRUMP, alert=True,
                       why=f"2/1 forcing 1NT response (10-12, "
                           f"3-card {major.to_char()} support — "
                           f"continue with 3M next turn)")
        # Acol-style "show your suit first" with 3-card major support:
        # with a 4-card minor and 10-12 HCP, bid 2-of-minor natural
        # (forcing 1 round) rather than jump 3M. After opener's
        # rebid, responder can preference back to the major or
        # invite NT, finding the right contract via a longer
        # auction. Seed=42 board 4 in Acol: S has ♠J52 ♥Q74 ♦A72
        # ♣A942 (11 HCP, 3-3-3-4) → bids 2♣ natural; opener N
        # rebids 2♥ (5+ hearts); responder pushes to 4♥ via 3♥
        # preference. (Q-Plus's auction:
        # 1H-2C-2H-3H-4H.)
        # Gated on 4-card-major systems only, since 5cM systems
        # have other priorities (2/1 GF, NMF) that lead to
        # different orderings.
        if (10 <= hcp <= 12
                and getattr(system, "one_major_card_min", 5) <= 4
                and not system.has("A-1MA-forcing-1NT")):
            for side in (Suit.CLUBS, Suit.DIAMONDS):
                if e.suit_lengths[side] >= 4 and side != major:
                    return bid(2, side, alert=True,
                               why=f"Acol natural 2{side.to_char()}: "
                                   f"4+ {side.to_char()}, "
                                   f"{hcp} HCP, forcing 1 round")
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

    # Negative double showing the other major (if not bid yet) or
    # the unbid major when overcall is in a major. Cap follows the
    # system's Sputnik level (typically 3♠ in modern, 2♠ in SAYC).
    # Deal #1 (seed 7371): partner 1S overcalled by 3C; S had 4
    # hearts + 12 HCP; the cap of 2 prevented negative X (-9 IMP).
    neg_max = _negative_double_max_level(system)
    if (hcp >= 6 and overcall.level <= neg_max
            and overcall.suit is not None
            and overcall.suit != Suit.NOTRUMP
            and overcall.suit != op_suit):
        # If overcall is in a minor, double promises the OTHER major
        # (or both unbid majors when the other major isn't opener's).
        # If overcall is in a major, double promises 4+ in the unbid
        # major (the one that's neither opener's nor overcaller's).
        if overcall.suit in (Suit.CLUBS, Suit.DIAMONDS):
            # Partner opened a major; overcaller bid a minor. We
            # can show the OTHER major (4+) with X.
            if e.suit_lengths[other_major] >= 4:
                return double(why=f"Negative double: 4+ "
                                  f"{other_major.to_char()}")
        elif overcall.suit in (Suit.HEARTS, Suit.SPADES):
            if e.suit_lengths[other_major] >= 4:
                return double(why=f"Negative double: 4+ "
                                  f"{other_major.to_char()}")

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
                # Note: trump not raised yet (just opener's 1C +
                # responder's 1M positive). Cuebid pipeline guards
                # require trump-raised, so this site keeps the
                # direct 4NT launch.
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

    # Positive 2C / 2D response (5+ in minor, 8+ HCP — GF since
    # 1C was strong). Opener's textbook rebid priorities:
    #   1. 5+ major  → bid the major at the 2-level (game-bidding
    #      sequence starts with showing the major)
    #   2. Balanced 22+ HCP  → 3NT (game in NT; partner's 8+ means
    #      ~30 combined, slam if more)
    #   3. Balanced 16-21 HCP  → 2NT (showing balanced, asks
    #      partner for further description / Stayman / transfer)
    #   4. Unbalanced with 4+ trump support  → raise the minor
    #   5. Last resort: 2NT (balanced description) — better than
    #      a 3-card raise of the minor, which buries NT game.
    # The previous "3+ support → 3m" path bypassed steps 1-3 and
    # under-described the hand on every balanced 16+ opener.
    # Deals #157, #101, #151 (analysis seed 38263, 11075, 7371):
    # biq's strong-1C opener with 16-22 balanced rebid 3D over
    # partner's 2D positive, ending in 3D-N for +110 instead of
    # 3NT for +600.
    if p_last.level == 2 and p_last.suit in (Suit.CLUBS, Suit.DIAMONDS):
        minor = p_last.suit
        if e.suit_lengths[Suit.SPADES] >= 5:
            return bid(2, Suit.SPADES,
                       why=f"Precision 1C-2{minor.to_char()}: 5+ spades")
        if e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS,
                       why=f"Precision 1C-2{minor.to_char()}: 5+ hearts")
        if e.is_balanced and hcp >= 22:
            return bid(3, Suit.NOTRUMP,
                       why=f"Precision 1C-2{minor.to_char()}: "
                           f"22+ balanced (game in NT)")
        if e.is_balanced:
            return bid(2, Suit.NOTRUMP,
                       why=f"Precision 1C-2{minor.to_char()}: "
                           f"balanced rebid (16-21, partner inquires)")
        if e.suit_lengths[minor] >= 4:
            return bid(3, minor,
                       why=f"Precision 1C-2{minor.to_char()}: "
                           f"4+ trump fit (unbalanced)")
        # Falls through to NT rebid — better than a 3-card raise
        # which hides NT game prospects.
        return bid(2, Suit.NOTRUMP,
                   why=f"Precision 1C-2{minor.to_char()}: "
                       f"no major, no 4-card fit (NT description)")

    # Was partner's response made AFTER an opp's intervention? If so,
    # the meaning of 2NT / 3NT shifts: in competitive auctions partner
    # bids 2NT = 8-11 balanced + stopper, 3NT = 12+ balanced + stopper.
    # Without this check, opener reads competitive 2NT as the
    # uncontested 14-16 HCP meaning and rockets into phantom slams.
    intervention_before_response = False
    if state.partner_bids and state.opener_seat is not None:
        partner_seat = state.seat.partner()
        partner_first_idx = next(
            (i for i, (s, b) in enumerate(state.bids)
             if s == partner_seat and not b.is_pass), None)
        if partner_first_idx is not None:
            intervention_before_response = any(
                not b.is_pass and s != state.opener_seat and s != partner_seat
                for s, b in state.bids[:partner_first_idx])

    # Positive 2NT — DIRECT 1C-2NT only.
    if (p_last.level == 2 and p_last.suit == Suit.NOTRUMP
            and len(state.partner_bids) == 1):
        if intervention_before_response:
            # Competitive 2NT = 8-11 balanced with stopper. Combined
            # 16-22 + 8-11 = 24-33. Raise to 3NT with extras; pass
            # 2NT only with a flat minimum (rare since opener has 16+).
            if hcp >= 17:
                return bid(3, Suit.NOTRUMP,
                           why="Precision 1C-(intervention)-2NT: "
                               "raise competitive 8-11 to 3NT game "
                               "(opener has extras)")
            return passb(
                why="Precision 1C-(intervention)-2NT: respect "
                    "partner's 8-11 with min opener")
        if hcp >= 18:
            return bid(6, Suit.NOTRUMP,
                       why="Precision 1C-2NT: 22+14 = slam in NT")
        return bid(3, Suit.NOTRUMP,
                   why="Precision 1C-2NT: 22+14 = 3NT game")

    # Positive 3NT — DIRECT 1C-3NT only. Mainstream Precision treats
    # this as "17+ balanced, no slam interest"; opener accepts the
    # signoff unless they hold rare 22+ extras. After intervention,
    # partner's 3NT shows 12+ balanced with stopper — likely already
    # at the right contract; opener passes.
    # Earlier bug: unconditional 6NT push fired when partner's 3NT was
    # actually a SIGNOFF after our 2NT rebid (1C-1H-2NT-3NT), producing
    # freelance 6NT contracts on hands like deal #1 (18 opener + 10
    # responder = 28, light-years from slam).
    if (p_last.level == 3 and p_last.suit == Suit.NOTRUMP
            and len(state.partner_bids) == 1):
        if intervention_before_response:
            return passb(
                why="Precision 1C-(intervention)-3NT: partner's "
                    "competitive 12+ balanced — game reached, no "
                    "slam push without extras")
        if hcp >= 22:
            return bid(6, Suit.NOTRUMP,
                       why="Precision 1C-3NT: 22+17 = slam values")
        return passb(why="Precision 1C-3NT: respect signoff")

    # Partner's 3NT later in the auction (e.g. after 1C-1H-2NT)
    # is a SIGNOFF, not a slam invitation. Pass unless we have
    # serious extras beyond what 2NT already promised (we showed
    # 18-19 with 2NT, so only the very top of that range with a
    # source of tricks should move).
    if (p_last.level == 3 and p_last.suit == Suit.NOTRUMP
            and len(state.partner_bids) >= 2):
        return passb(why="Partner signed off at 3NT — respect it")

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


def _precision_2d_rebid(state, e: HandEval, p_last: Bid, system) -> Bid:
    """Opener's rebid after opening 2♦ Precision three-suiter and hearing
    partner's response.

    Partner's actions and our handling:
        2H / 2S            → sign-off; pass.
        2NT relay          → show shortness + strength. Bid 4 of side suit
                             with max (13-15), 3 of side suit with min.
                             "Side suit" here is the long club (4+ or 5+);
                             if no clubs, 3D = min generic, 3NT = max
                             balanced-ish.
        3H / 3S invite     → accept with max + 3+ in the major.
        4H / 4S            → pass; partner has placed the contract.
    """
    hcp = e.hcp
    cl = e.suit_lengths[Suit.CLUBS]
    sp = e.suit_lengths[Suit.SPADES]
    hr = e.suit_lengths[Suit.HEARTS]
    is_max = hcp >= 13

    if p_last.level == 2 and p_last.suit == Suit.NOTRUMP:
        if is_max and cl >= 4:
            return bid(4, Suit.CLUBS, alert=True,
                       why=f"2D-2NT-4C: max {hcp} HCP, {cl} clubs side")
        if not is_max and cl >= 4:
            return bid(3, Suit.CLUBS, alert=True,
                       why=f"2D-2NT-3C: min {hcp} HCP, {cl} clubs side")
        if is_max:
            return bid(3, Suit.NOTRUMP, alert=True,
                       why=f"2D-2NT-3NT: max {hcp} HCP, no long side")
        return bid(3, Suit.DIAMONDS, alert=True,
                   why=f"2D-2NT-3D: min {hcp} HCP, no long side")

    if p_last.level == 3 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        major = p_last.suit
        if is_max and e.suit_lengths[major] >= 3:
            return bid(4, major,
                       why=f"Accept invite: max + {e.suit_lengths[major]} "
                           f"{major.to_char()}")
        return passb(why=f"Decline invite: min, {e.suit_lengths[major]} "
                         f"{major.to_char()}")

    if p_last.level == 2 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        return passb(why="Partner signed off in major fit")

    if p_last.level == 4 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        return passb(why="Partner placed the contract at game")

    return passb()


def _opener_rebid(state, e: HandEval, system: str) -> Bid:
    op = state.opening_bid

    if not state.partner_bids:
        # Partner has only passed so far. When opps overcalled AND
        # advanced into a fit, opener with extras + shortness in
        # their suit should reopen with a takeout double — partner
        # may be sitting on a trap pass or a hand too good to act
        # earlier. Otherwise, the auction dies here.
        #
        # CRITICAL: only ONE reopening X. If I've already doubled
        # and partner still passed each time, partner has no values
        # and continuing to double opp's escalations is the
        # textbook anti-pattern that produced deal #47's -510 in
        # 4CX-W (three penalty X's with one trump trick). Once
        # partner has shown they have nothing to say, accept it.
        already_doubled = any(b.is_double for b in state.my_bids)
        if already_doubled:
            return passb(why="Partner couldn't act after my X — "
                             "don't escalate")

        # Precision 1C strong opener facing takeout double + partner-
        # pass — make a descriptive rebid showing the strong hand.
        # Without this, biq passes 1CX and gets clobbered (Precision
        # 1C with 17 HCP balanced playing 1CX-S vul = -200; deal 100
        # base #4 seed 80719 was the canonical case).
        #
        # Standard Precision 1C-X-P-P rebids (mirroring 1C-1D-rebid):
        #   1NT  = 16-19 balanced (cheapest descriptive call)
        #   2NT  = 20-21 balanced
        #   3NT  = 22+ balanced
        #   1H/1S = natural 5+ in major, 16+ HCP unbalanced
        #   2D/2C = natural 5+ in minor (over 1C: 2C = 6+ clubs)
        is_precision_1c = (
            getattr(system, "strong_open_call", "2C") == "1C"
            and op is not None and op.level == 1
            and op.suit == Suit.CLUBS)
        opps_acted = any(
            not b.is_pass for b in (list(state.lho_bids)
                                    + list(state.rho_bids)))
        # Opps' last-bid suit (for stopper check + cheapest-NT calc).
        opps_suit = None
        for b in reversed(list(state.lho_bids)
                          + list(state.rho_bids)):
            if (b.suit is not None and b.suit != Suit.NOTRUMP
                    and not b.is_pass):
                opps_suit = b.suit
                break
        # Only on the FIRST rebid — re-firing after opps' subsequent
        # bid would try to bid 1NT again (illegal at higher level)
        # and get sanity-pass-substituted.
        if (is_precision_1c and opps_acted
                and len(state.my_bids) == 1):
            hcp = e.hcp
            # Cheapest legal NT level given the auction so far.
            last_lvl = state.last_level or 1
            last_suit = state.last_suit_bid
            if (last_suit is None
                    or _BID_RANK[Suit.NOTRUMP] > _BID_RANK[last_suit]):
                nt_lvl = last_lvl
            else:
                nt_lvl = last_lvl + 1
            # Balanced rebid via NT.
            if e.is_balanced:
                # Stopper check: when opps showed a suit, need to
                # cover it for NT contracts. No suit shown (X only) →
                # no specific stopper required (general balanced
                # description).
                has_stopper = (opps_suit is None
                               or _has_stopper(e, opps_suit))
                if has_stopper:
                    if 16 <= hcp <= 19 and nt_lvl <= 2:
                        return bid(nt_lvl, Suit.NOTRUMP,
                                   why=f"Precision 1C-(opps)-P: "
                                       f"16-19 balanced, "
                                       f"{opps_suit.to_char() if opps_suit else 'no'} "
                                       f"stopper")
                    if 20 <= hcp <= 21 and nt_lvl <= 3:
                        return bid(max(nt_lvl, 2), Suit.NOTRUMP,
                                   why=f"Precision 1C-(opps)-P: "
                                       f"20-21 balanced")
                    if hcp >= 22 and nt_lvl <= 3:
                        return bid(3, Suit.NOTRUMP,
                                   why=f"Precision 1C-(opps)-P: "
                                       f"22+ balanced")
            # 5+ major: bid at cheapest legal level.
            for major in (Suit.SPADES, Suit.HEARTS):
                if e.suit_lengths.get(major, 0) >= 5:
                    if (last_suit is None
                            or _BID_RANK[major] > _BID_RANK[last_suit]):
                        lvl = last_lvl
                    else:
                        lvl = last_lvl + 1
                    if 1 <= lvl <= 4:
                        return bid(lvl, major,
                                   why=f"Precision 1C-(opps)-P: 5+ "
                                       f"{major.to_char()} ({hcp} HCP)")
            # 5+ diamonds.
            if e.suit_lengths.get(Suit.DIAMONDS, 0) >= 5:
                if (last_suit is None
                        or _BID_RANK[Suit.DIAMONDS] > _BID_RANK[last_suit]):
                    lvl = last_lvl
                else:
                    lvl = last_lvl + 1
                if 2 <= lvl <= 4:
                    return bid(lvl, Suit.DIAMONDS,
                               why=f"Precision 1C-(opps)-P: 5+ ♦ "
                                   f"({hcp} HCP)")
            # Takeout double when opps showed a suit and we're short:
            # 16+ HCP + ≤ 2 cards in opps' suit + tolerance for unbid
            # suits. Lets partner pick.
            if (opps_suit is not None
                    and e.suit_lengths.get(opps_suit, 0) <= 2
                    and hcp >= 16):
                return double(
                    why=f"Precision 1C-(opps)-P: takeout X — short "
                        f"in opps' {opps_suit.to_char()}, "
                        f"strong ({hcp} HCP)")
        # Look at BOTH rho and lho for the overcall — depending on
        # the auction position, the overcall can come from either
        # opponent. (Bridge: RHO is the player who bids just BEFORE
        # me in the next round, LHO is the player who bids JUST
        # AFTER me in the current round.) A 1m-(1M)-P-(P)-? auction
        # has the 1M overcall in LHO's bids from opener's POV;
        # a 1m-(P)-1M-(2X)-? auction has the 2X overcall in RHO's
        # bids. Deal #52 (gold-standard corpus 38263): N opened
        # 1H, E (LHO) overcalled 1S, S passed, W passed → biq's
        # reopening-X check looked only at rho_bids (W's passes),
        # missed E's 1S, and passed. Q-Plus's NS pushed opps to
        # 5C and doubled for +1100 (-22 IMP swing).
        any_opp_bid = state.rho_bids or state.lho_bids
        if any_opp_bid:
            opp_suit = None
            for b in reversed(list(state.lho_bids) +
                              list(state.rho_bids)):
                if b.suit is not None and b.suit != Suit.NOTRUMP:
                    opp_suit = b.suit
                    break
            if (opp_suit is not None
                    and e.suit_lengths.get(opp_suit, 0) <= 2
                    and e.hcp >= 13):
                return double(why=f"Reopening X: 13+ HCP, short in "
                                  f"opps' {opp_suit.to_char()}")
            # Even WITHOUT shortness in opps' suit, with extras
            # (15+ HCP) and 6+ own suit, reopen by rebidding
            # the long suit at the 2-level. Deal #52 N has 6
            # clubs (not opener's suit, but 6-card minor) and
            # 15 HCP — Q-Plus rebids 2C here.
            if (e.hcp >= 14
                    and op.suit is not None
                    and op.suit != Suit.NOTRUMP):
                # Find longest non-opener-suit at 6+ cards.
                best_suit, best_len = None, 0
                for s in (Suit.CLUBS, Suit.DIAMONDS,
                          Suit.HEARTS, Suit.SPADES):
                    if s == op.suit:
                        continue
                    n_in_s = e.suit_lengths.get(s, 0)
                    if n_in_s > best_len:
                        best_len, best_suit = n_in_s, s
                if best_suit is not None and best_len >= 6:
                    # Bid at the cheapest legal level.
                    lvl = 2 if _BID_RANK[best_suit] > _BID_RANK[opp_suit] else 3
                    if lvl <= 3:
                        return bid(lvl, best_suit,
                                   why=f"{lvl}{best_suit.to_char()}: "
                                       f"reopen with 6+ side suit "
                                       f"({e.hcp} HCP)")
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
        # 2D Precision three-suiter: rebid over partner's response.
        if (op.level == 2 and op.suit == Suit.DIAMONDS
                and any(k.startswith("B-2D.Precision")
                        for k in system.raw_rules)):
            return _precision_2d_rebid(state, e, p_last, system)

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

    # Jacoby transfer accept over 2NT (2NT-3D = transfer to hearts,
    # 2NT-3H = transfer to spades). Opener completes by bidding 3
    # of the indicated major. Deal #61 (seed 7371): N opened 2NT,
    # S transferred 3H; biq had NO 2NT-transfer-accept handler so
    # N passed 3H — partnership stayed in 3H instead of reaching
    # 4S game (-14 IMP).
    # With 4-card SUPPORT and the higher end of the 2NT range,
    # SUPER-ACCEPT by jumping to 4 of the major — informs partner
    # of the 9-card fit and game values, lets partner pass 4M with
    # minimum or explore slam with extras.
    if op.level == 2 and op.suit == Suit.NOTRUMP and p_last.level == 3:
        # Stayman after 2NT (3C): show 4-card major or deny.
        # Without this branch, opener falls through to passb() and
        # the auction dies at 3C. Deal 55 (slam 95512): S opened 2NT
        # with 20 HCP 4-3-3-3; N bid 3C Stayman; biq passed 3C
        # (-16 IMP vs Q-Plus's 6NT).
        if p_last.suit == Suit.CLUBS:
            has_4S = e.suit_lengths.get(Suit.SPADES, 0) >= 4
            has_4H = e.suit_lengths.get(Suit.HEARTS, 0) >= 4
            if has_4S and has_4H:
                # Show both majors via 3S (responder picks); some
                # partnerships use 3H. Q-Plus's standard is to bid
                # 3S with both 4s; we follow that.
                return bid(3, Suit.SPADES, alert=True,
                           why="2NT-Stayman: 4 spades (and 4 hearts)")
            if has_4S:
                return bid(3, Suit.SPADES, alert=True,
                           why="2NT-Stayman: 4 spades")
            if has_4H:
                return bid(3, Suit.HEARTS, alert=True,
                           why="2NT-Stayman: 4 hearts")
            return bid(3, Suit.DIAMONDS, alert=True,
                       why="2NT-Stayman: no 4-card major")
        # Super-accept (jump to 4 of the major) requires:
        #   * 4+ trump support AND
        #   * top of the 2NT range (max 2NT HCP)
        # With less, just complete the transfer at the 3-level.
        nt_max = getattr(system, "two_nt_max_hcp", 21)
        is_max = e.hcp >= nt_max
        if p_last.suit == Suit.DIAMONDS:
            if (is_max
                    and e.suit_lengths.get(Suit.HEARTS, 0) >= 4):
                return bid(4, Suit.HEARTS,
                           why=f"Super-accept transfer: 4+ hearts "
                               f"+ max 2NT ({e.hcp})")
            return bid(3, Suit.HEARTS,
                       why="Accept Jacoby transfer to hearts (over 2NT)")
        if p_last.suit == Suit.HEARTS:
            if (is_max
                    and e.suit_lengths.get(Suit.SPADES, 0) >= 4):
                return bid(4, Suit.SPADES,
                           why=f"Super-accept transfer: 4+ spades "
                               f"+ max 2NT ({e.hcp})")
            return bid(3, Suit.SPADES,
                       why="Accept Jacoby transfer to spades (over 2NT)")

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
                # Slam zone: max NT (17) + Smolen's GF promise → bid
                # 3-of-other-major (preference) when slam-going. This
                # sets trump for partner to drive slam via cuebid/RKC.
                # Deal 33 in slam corpus 59517: N had 17 HCP + 3
                # spades after Smolen 3H; jump to 4S kills slam
                # exploration. The 3-spade preference keeps the
                # auction at the 3-level so partner with 13+ HCP can
                # set up cuebid sequences.
                nt_max = (getattr(system, "one_nt_max_hcp", 17)
                          if system is not None else 17)
                if e.hcp >= nt_max - 1:
                    # Must outrank 3H (partner's Smolen bid).
                    # 3S is legal (HEARTS rank=2 < SPADES rank=3).
                    if other_major == Suit.SPADES:
                        return bid(3, Suit.SPADES, alert=True,
                                   why=f"3S preference (Smolen, max NT "
                                       f"{e.hcp} HCP, 3+ S fit) — slam "
                                       f"exploration room")
                    # other_major == HEARTS: partner showed 5H+4S via
                    # 3S. Bid 4H (game) since 3H would be a retreat.
                return bid(4, other_major,
                           why=f"Smolen accept: 3+ {other_major.to_char()}")
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
        # 4+ support for partner's POSITIVE major response (5+ of
        # that major, 8+ HCP): raise to 3M. Sets trump for slam
        # exploration. Deal 5 (slam 67238): N held 4H + 5C + 23 HCP
        # after partner's positive 2H; old code fell through to 3NT
        # (-13 IMP vs Q-Plus's 6H reached via 3H raise + cuebid + RKC).
        if (p_last.level == 2
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths.get(p_last.suit, 0) >= 4):
            return bid(3, p_last.suit,
                       why=f"3{p_last.suit.to_char()}: 4+ support for "
                           f"partner's positive 2{p_last.suit.to_char()} "
                           f"response (slam zone after 2C)")
        if e.suit_lengths[Suit.SPADES] >= 5:
            return bid(2, Suit.SPADES, why="Natural rebid 2S (5+ spades)")
        if e.suit_lengths[Suit.HEARTS] >= 5:
            return bid(2, Suit.HEARTS, why="Natural rebid 2H (5+ hearts)")
        if e.is_balanced and 22 <= e.hcp <= 24:
            return bid(2, Suit.NOTRUMP, why="22-24 balanced rebid")
        if e.is_balanced and e.hcp >= 25:
            return bid(3, Suit.NOTRUMP, why="25+ balanced rebid")
        # Catch-all for awkward 2C hands without 5+ major or balanced
        # shape — rebid 3NT to keep the GF alive (better than passing).
        return bid(3, Suit.NOTRUMP,
                   why="2C catch-all 3NT (no 5+ major, not balanced)")

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
    hcp = e.hcp

    # 1M-2X-2Y-3M slam launch: after my reverse (showing 17+ HCP +
    # 4+ second suit), responder raised MY ORIGINAL major to 3M
    # setting trump. Combined 28+ HCP + 8+ major fit → slam zone.
    # Initiate Italian cuebid sequence, or launch 4NT RKC if no
    # side-suit 1st-round controls. Deal 65 in slam corpus 59517:
    # this gap kept biq at 4H instead of exploring 7H.
    if (p_last.suit == op_suit
            and op_suit in (Suit.HEARTS, Suit.SPADES)
            and p_last.level == 3
            and len(state.my_bids) >= 2
            and state.my_bids[-1].level == 2
            and state.my_bids[-1].suit is not None
            and state.my_bids[-1].suit != Suit.NOTRUMP
            and state.my_bids[-1].suit != op_suit
            and hcp >= 16):
        cuebid = _maybe_initiate_cuebid(state, e, trump=op_suit)
        if cuebid is not None:
            return cuebid
        return bid(4, Suit.NOTRUMP, alert=True,
                   why=f"RKC after reverse + 3{op_suit.to_char()} "
                       f"trump set ({hcp} HCP, slam zone)")

    # ----- Negative double response -----
    # After 1m/1M-(overcall)-X, partner's double is a NEGATIVE
    # DOUBLE: shows the unbid major(s) + ~6+ HCP. Opener's
    # textbook duties:
    #   * 4 of partner's promised major → bid it at the cheapest
    #     legal level (jump with extras).
    #   * 3 of the major + good hand → invite/raise to game.
    #   * Stoppers in overcall suit + balanced → NT (cheapest
    #     level above overcall).
    #   * 6+ own suit → rebid it.
    #   * 12-14 minimum without major support → rebid own suit /
    #     pass to convert to penalty (only if our trump tricks
    #     justify defending — too risky to guess, so prefer
    #     bidding 1NT or our suit).
    # bridgeIQ used to fall through to passb() here — deal #21
    # had S with 12 HCP + 4 spades passing N's negative double of
    # 1H for a -7 IMP loss when textbook is to bid 1S confirming
    # the spade fit.
    # The overcall doubled is the last non-pass non-X bid by EITHER
    # opponent (could be LHO or RHO depending on seat — e.g. S
    # opens 1C, W overcalls 1H, N doubles, E passes, S is asked:
    # the overcall is from S's LHO. The check needs to scan both
    # opponent lists.)
    opp_overcall_suit = None
    if p_last.is_double:
        # Most-recent non-pass opp bid that wasn't opener's suit.
        all_opp = list(state.rho_bids) + list(state.lho_bids)
        # Sort by recency via the global auction order: walk the
        # auction backwards, find the last opp-suit bid.
        for seat, b in reversed(state.bids):
            if seat in (state.seat, state.seat.partner()):
                continue  # skip my and partner's calls
            if b.is_pass or b.is_double or b.is_redouble:
                continue
            if b.suit is None or b.suit == Suit.NOTRUMP:
                continue
            if b.suit == op_suit:
                continue
            opp_overcall_suit = b.suit
            break
    is_neg_x = (opp_overcall_suit is not None
                and op.level == 1
                and op_suit != Suit.NOTRUMP)
    # Only the INITIAL response to the negative double. `partner_bids`
    # drops passes, so `p_last` stays the double even after partner passes
    # twice; without this guard the block re-fires every opener turn and
    # escalates the SAME suit each round (5H→6H→7H over the opponents'
    # doubles — the −1400 sacrifice in 6886-26). Once opener has already
    # rebid since the double (more than just the opening in `my_bids`),
    # fall through to normal, game-capped competitive logic instead.
    if is_neg_x and len(state.my_bids) > 1:
        is_neg_x = False
    if is_neg_x:
        rho_suit = opp_overcall_suit  # rename for the rest of the block
        # The "promised" major from a negative double is the unbid
        # major (e.g. 1C-(1H)-X promises 4+ spades; 1D-(1S)-X
        # promises 4+ hearts; 1H-(1S)-X promises 4+ hearts is
        # debatable but Q-Plus's standard is "the OTHER major").
        unbid_major = None
        if rho_suit == Suit.HEARTS or op_suit == Suit.HEARTS:
            if op_suit != Suit.SPADES and rho_suit != Suit.SPADES:
                unbid_major = Suit.SPADES
        elif rho_suit == Suit.SPADES or op_suit == Suit.SPADES:
            if op_suit != Suit.HEARTS and rho_suit != Suit.HEARTS:
                unbid_major = Suit.HEARTS
        # 4+ in promised major → raise (in our hand it's a "fit").
        if unbid_major is not None:
            my_major = e.suit_lengths.get(unbid_major, 0)
            if my_major >= 4:
                # Cheapest legal level for the major: depends on
                # both suit rank AND overcall level. 1H over 1C-
                # (1S)-X is legal; 3H over 1S-(3C)-X is needed
                # because 3C is already at the 3-level. Walk the
                # auction to find the actual highest bid.
                highest_lvl, highest_suit = 0, None
                for _seat, b in state.bids:
                    if b.is_pass or b.is_double or b.is_redouble:
                        continue
                    if b.suit is None:
                        continue
                    if (b.level > highest_lvl
                            or (b.level == highest_lvl
                                and highest_suit is not None
                                and _BID_RANK[b.suit] > _BID_RANK[highest_suit])):
                        highest_lvl, highest_suit = b.level, b.suit
                if highest_suit is None:
                    from_lvl = 1
                elif _BID_RANK[unbid_major] > _BID_RANK[highest_suit]:
                    from_lvl = highest_lvl
                else:
                    from_lvl = highest_lvl + 1
                # Strength → level (relative to cheapest):
                #   12-14 min → bid at cheapest level
                #   15-17     → jump one level (invite)
                #   18+       → bid game (4M), or cheapest+2 if past
                if hcp >= 18:
                    return bid(max(4, from_lvl), unbid_major,
                               why=f"{max(4, from_lvl)}"
                                   f"{unbid_major.to_char()}: "
                                   f"max + 4-card fit after partner's "
                                   f"negative X")
                if hcp >= 15 and from_lvl + 1 <= 4:
                    return bid(from_lvl + 1, unbid_major,
                               why=f"{from_lvl+1}{unbid_major.to_char()}: "
                                   f"15-17 + 4-card fit, jump invite "
                                   f"after partner's negative X")
                return bid(from_lvl, unbid_major,
                           why=f"{from_lvl}{unbid_major.to_char()}: "
                               f"4-card fit after partner's negative X")
        # 3-card promised major + good hand (15+) → cuebid or jump
        # in own suit; without extras prefer NT or rebid own suit.
        # Stopper in overcall suit + balanced → 1NT-or-cheapest NT.
        if (rho_suit is not None
                and _has_stopper(e, rho_suit)
                and e.is_balanced):
            # 1NT shows 12-14ish; 2NT shows 18-19 (we already
            # showed 12+ with the opening).
            if hcp >= 18:
                return bid(2, Suit.NOTRUMP,
                           why=f"2NT: 18-19 balanced with "
                               f"{rho_suit.to_char()} stopper "
                               f"after partner's negative X")
            # 1NT outranks any 1-level overcall and is the cheapest
            # legal NT bid in those auctions.
            return bid(1, Suit.NOTRUMP,
                       why=f"1NT: balanced 12-14 with "
                           f"{rho_suit.to_char()} stopper "
                           f"after partner's negative X")
        # 6+ own suit → rebid it.
        own_len = e.suit_lengths.get(op_suit, 0)
        if own_len >= 6:
            if hcp >= 15:
                return bid(3, op_suit,
                           why=f"3{op_suit.to_char()}: 6+ own suit, "
                               f"15-17, jump-rebid after negative X")
            return bid(2, op_suit,
                       why=f"2{op_suit.to_char()}: 6+ own suit "
                           f"after partner's negative X")
        # Minimum balanced without stopper — show a 4-card second
        # suit if available, otherwise pass (converts to penalty).
        for s in (Suit.DIAMONDS, Suit.CLUBS, Suit.HEARTS, Suit.SPADES):
            if s == op_suit or s == rho_suit:
                continue
            if e.suit_lengths.get(s, 0) >= 4 and hcp >= 12:
                # Bid at cheapest level that outranks the overcall.
                lvl = (1 if rho_suit is not None
                       and _BID_RANK[s] > _BID_RANK[rho_suit] else 2)
                return bid(lvl, s,
                           why=f"{lvl}{s.to_char()}: 4-card side suit "
                               f"after partner's negative X")
        # Last resort: pass, converting the X to penalty.
        return passb(why="No clear bid — convert negative X to penalty")

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
                # Minor-suit opener with balanced shape: prefer 2NT
                # (descriptive 15-17 balanced) over 3-of-minor (which
                # commits to a minor-suit partial that often goes
                # down). 3D / 3C asking for game in a minor needs
                # 27+ combined HCP; partner's 2-of-minor simple raise
                # caps at 9 HCP → combined 24-26, not enough for 5m
                # and not enough for 3NT without help. 2NT lets the
                # auction settle at the right level.
                # Deal 86 seed 80719 (curated base #4): S opened 1D,
                # W overcalled 1S, N raised competitively to 2D, biq
                # bid 3D ("game try") → 3D-S down 1 vul (NS-100).
                # Q-Plus passed → opps played 2H-W down 1 vul (NS+100).
                # Switching to 2NT gives a more textbook contract.
                if (op_suit in (Suit.CLUBS, Suit.DIAMONDS)
                        and e.is_balanced):
                    return bid(2, Suit.NOTRUMP,
                               why=f"2NT: 15-17 balanced after "
                                   f"partner's simple raise of "
                                   f"{op_suit.to_char()} "
                                   f"(better than 3{op_suit.to_char()})")
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
            # If partner's 3-of-my-minor is ALERTED (the strong-raise
            # variant: 18+ HCP + 5-card support, slam interest), the
            # combined HCP floor is ~30. With balanced and no major
            # fit prospects, drive to 3NT (game in NT, simpler scoring)
            # or 5m with shape. Don't pass — slam is in the air.
            # Deal #2 (seed 7371): S opened 1C with 12 HCP, N's 3C
            # was alerted strong raise (18 HCP + 5 clubs); biq's S
            # treated 3C as a limit raise and passed (-15 IMP for
            # the missed slam Q-Plus reached at 6C).
            if (p_last.alert
                    and op_suit in (Suit.CLUBS, Suit.DIAMONDS)):
                if e.hcp >= 14:
                    return bid(4, Suit.NOTRUMP, alert=True,
                               why=f"RKC: 14+ opposite partner's "
                                   f"strong jump-raise (slam)")
                if e.is_balanced:
                    return bid(3, Suit.NOTRUMP,
                               why=f"3NT: 12-13 + partner's "
                                   f"alerted strong jump-raise of "
                                   f"{op_suit.to_char()}")
                return bid(5, op_suit,
                           why=f"5{op_suit.to_char()}: 12-13 + "
                               f"partner's alerted strong "
                               f"jump-raise (game in minor)")
            # Accept with 14+ HCP, or with 13 HCP + a distributional
            # extra (6+ trumps, a singleton/void, or a 5+ card side
            # suit). The pure-HCP threshold misses minimum openers
            # with extra playing strength — seed=42 board 4 is one
            # canonical case (13 HCP + 6-card heart suit); board 3
            # Acol is another (13 HCP + 5-card diamond side suit
            # opener already showed).
            has_extra_trump = e.suit_lengths.get(op_suit, 0) >= 6
            has_shortness = any(e.suit_lengths.get(s, 0) <= 1
                                for s in (Suit.CLUBS, Suit.DIAMONDS,
                                          Suit.HEARTS, Suit.SPADES)
                                if s != op_suit)
            has_long_side = any(e.suit_lengths.get(s, 0) >= 5
                                for s in (Suit.CLUBS, Suit.DIAMONDS,
                                          Suit.HEARTS, Suit.SPADES)
                                if s != op_suit)
            if e.hcp >= 14:
                return bid(4, op_suit, why="Accept limit raise (14+ HCP)")
            if e.hcp >= 13 and (has_extra_trump or has_shortness
                                 or has_long_side):
                # With a 5-card side suit but only 3-4 trumps
                # (responder's preference probably means a 4-3
                # fit), prefer 3NT over 4M if balanced enough.
                trumps = e.suit_lengths.get(op_suit, 0)
                if (has_long_side and not has_extra_trump
                        and trumps <= 4):
                    return bid(3, Suit.NOTRUMP,
                               why=f"Accept invite via 3NT (13 + "
                                   f"5-card side suit, 4-3 "
                                   f"{op_suit.to_char()} fit)")
                return bid(4, op_suit,
                           why=f"Accept limit raise (13 HCP + "
                               f"distributional extra)")
            return passb()
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

    # Partner's 1NT response (6-9 / 6-12 if 1M opening).
    # In 2/1 GF systems (with `A-1MA-forcing-1NT`), 1NT after a
    # 1-of-major opening is FORCING — opener CANNOT pass below
    # 2 of their suit. Show the natural 5+ major rebid as the
    # minimum response.
    if p_last.level == 1 and p_last.suit == Suit.NOTRUMP:
        is_forcing_1nt = (
            system.has("A-1MA-forcing-1NT")
            and op_suit in (Suit.HEARTS, Suit.SPADES))
        if e.is_balanced and 12 <= e.hcp <= 14:
            if is_forcing_1nt:
                # Cannot pass: rebid 2 of the 5+ major if we
                # opened a major (we did — gated above), or show
                # a 4-card minor / second-suit. Bare 5-3-3-2 with
                # 5-card major just rebids the major.
                return bid(2, op_suit,
                           why=f"2{op_suit.to_char()} forced rebid "
                               f"after partner's forcing 1NT "
                               f"(12-14 with 5+{op_suit.to_char()})")
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
        # Forcing 1NT + nothing else to bid → rebid the 5-card
        # major (cannot pass).
        if is_forcing_1nt and e.suit_lengths.get(op_suit, 0) >= 5:
            return bid(2, op_suit,
                       why=f"2{op_suit.to_char()} forced (forcing "
                           f"1NT, no other rebid)")
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
        # Precision-style 3-card raise of partner's major. Only fires
        # when the hand is UNBALANCED — with a balanced 3-3-4-3 / 4-3-3-3
        # opener, Q-Plus prefers the 1NT rebid (seed=400 board 7) to
        # show notrumpiness. The 3-card raise is reserved for awkward
        # unbalanced minimums where neither NT nor the second-suit
        # rebid is comfortable.
        if (getattr(system, "strong_open_call", "2C") == "1C"
                and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths[p_last.suit] == 3
                and 12 <= e.hcp <= 14
                and not e.is_balanced
                and not state.rho_bids):
            return bid(2, p_last.suit,
                       why=f"Precision 3-card raise of partner's "
                           f"{p_last.suit.to_char()} (min, unbalanced)")
        # SAYC / 2/1 / French style (5-card-major systems): opener
        # with 1m opening plus 3-card major support (and a
        # singleton or 5-card side suit — i.e. unbalanced) prefers
        # raising partner's major over showing the side suit. The
        # 3-card raise is sound because partner's 1M response
        # promises 5+ cards in 5cM systems → 8-card fit minimum.
        # Skipped for fully balanced 4-3-3-3 hands (the 1NT rebid
        # below picks those up) and for 4-card-major systems
        # (Acol) where partner's 1M response may have only 4 cards
        # and 3-card support is a marginal 7-card fit. Q-Plus does
        # the raise on seed=42 board 1 in SAYC but the side-suit
        # rebid in Acol.
        if (getattr(system, "strong_open_call", "2C") == "2C"
                and getattr(system, "one_major_card_min", 5) >= 5
                and op_suit in (Suit.CLUBS, Suit.DIAMONDS)
                and p_last.suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths[p_last.suit] == 3
                and 11 <= e.hcp <= 14
                and not e.is_balanced
                and not state.rho_bids):
            return bid(2, p_last.suit,
                       why=f"3-card raise of partner's "
                           f"{p_last.suit.to_char()} "
                           f"(unbalanced minimum, 5cM system)")
        # Support partner with 4+ in their major at the cheapest level
        if p_last.suit in (Suit.HEARTS, Suit.SPADES) and e.suit_lengths[p_last.suit] >= 4:
            if e.hcp <= 14:
                return bid(2, p_last.suit, why="Simple raise of partner's major")
            if e.hcp <= 18:
                return bid(3, p_last.suit, why="Game try / strong raise")
            return bid(4, p_last.suit, why="Game raise (19+ HCP)")
        # Reverse: with 17+ HCP and a 4+ higher-ranking side suit
        # (longer first suit), show the second suit at the 2-level
        # BEFORE rebidding own 6-card suit. Reverse is more descriptive
        # (extras + 2 suits) than the minimum-range simple rebid.
        if (e.second_suit is not None
                and _BID_RANK[e.second_suit] > _BID_RANK[op_suit]
                and _BID_RANK[e.second_suit] < _BID_RANK[Suit.NOTRUMP]
                and e.suit_lengths[e.second_suit] >= 4
                and e.suit_lengths[op_suit] > e.suit_lengths[e.second_suit]
                and e.hcp >= 17):
            return bid(2, e.second_suit,
                       why=f"Reverse 2{e.second_suit.to_char()} "
                           f"(17+ HCP, longer {op_suit.to_char()})")
        # Rebid 6-card opener suit. HCP-aware:
        #   12-15 HCP → 2 (simple)
        #   16-18 HCP → 3 (jump rebid, invitational)
        #   19+ HCP   → 4 (game force, when major) — rare here
        #               since 19+ usually opens 2♣.
        if e.suit_lengths[op_suit] >= 6:
            if e.hcp >= 19 and op_suit in (Suit.HEARTS, Suit.SPADES):
                return bid(4, op_suit,
                           why=f"4{op_suit.to_char()}: 19+ HCP, "
                               f"6+ {op_suit.to_char()}")
            if e.hcp >= 16:
                return bid(3, op_suit,
                           why=f"Jump rebid 3{op_suit.to_char()} "
                               f"(16-18 HCP, 6+ {op_suit.to_char()})")
            return bid(2, op_suit, why="Rebid 6-card suit")
        # 5+ card side suit different from opener's: opener opened
        # a 4-card major (Acol/4cM systems) or the longest side
        # suit isn't the bid suit. Show it at the 2-level if legal
        # (lower-rank than opener's suit) and the HCP fits.
        # Seed=42 board 3 Acol: S opens 1H with 2-4-5-2, partner
        # bids 1S, S should rebid 2D (5-card side suit) not 1NT.
        for side in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
            if side == op_suit or side == p_last.suit:
                continue
            if (e.suit_lengths[side] >= 5
                    and _BID_RANK[side] < _BID_RANK[op_suit]):
                if 12 <= e.hcp <= 17:
                    return bid(2, side,
                               why=f"5+ card side suit at 2-level "
                                   f"({e.suit_lengths[side]} {side.to_char()})")
                # 18+ → jump-shift, textbook GF showing both suits +
                # extras. Deal #29 (seed 7371): N had 2-4-2-5 with 19
                # HCP after 1H-1S; biq passed for 1S-S making for
                # +110, Q-Plus jumped to 3-of-side-suit and reached
                # 3NT-N for +400 (-10 IMP). With 19 HCP a quiet
                # 1NT rebid undersells; jump-shift is mandatory.
                if e.hcp >= 18:
                    return bid(3, side,
                               why=f"Jump-shift 3{side.to_char()}: "
                                   f"18+ HCP, 5+ {side.to_char()}, "
                                   f"GF showing both suits")
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
        # Rebid NT. HCP-aware:
        #   12-14 → 1NT (minimum, balanced)
        #   15-17 → 1NT (out-of-range 1NT opener — only here if 5cM
        #               5-3-3-2 etc.; 1NT rebid is the safe default)
        #   18-19 → 2NT (jump rebid showing strong balanced)
        #   20+   → 3NT (driving to game; should rarely arise since
        #               20+ balanced usually opens 2NT directly)
        if e.is_balanced or e.is_semi_balanced:
            if e.hcp >= 20:
                return bid(3, Suit.NOTRUMP,
                           why=f"3NT jump rebid (20+ HCP balanced)")
            if e.hcp >= 18:
                return bid(2, Suit.NOTRUMP,
                           why=f"2NT jump rebid (18-19 HCP balanced)")
            if 12 <= e.hcp <= 14:
                return bid(1, Suit.NOTRUMP, why="12-14 balanced")
            if 15 <= e.hcp <= 17:
                return bid(1, Suit.NOTRUMP,
                           why="15-17 balanced (5cM 5-3-3-2 path)")
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

    # Partner's alerted jump in a new suit (level ≥ 3): two
    # distinct conventions live at the same shape, and which one
    # applies depends on whether opener bid a MAJOR or a MINOR:
    #   * After a MAJOR opening: SPLINTER. Partner has 0-1 in the
    #     splinter suit + 4+ trump support + 11-14 HCP. Cuebid /
    #     RKC with slam interest, sign off in 4M otherwise.
    #   * After a MINOR opening: STRONG JUMP-SHIFT (especially in
    #     Precision). Partner has 5+ in the jump-suit + 16+ HCP,
    #     game-forcing. Raise the suit with support, NT with
    #     stoppers, rebid own suit with extras.
    # The previous one-rule-for-both treated every alerted
    # level-3 new-suit as splinter, leading biq to "sign off in
    # 4 of opener's minor" after a jump-shift. Deal #66 (analysis
    # seed 7371): S opened 1D, N's 3C alerted (jump-shift, 18 HCP
    # + 5 clubs); biq's S read it as a splinter and bid 4D
    # (sign-off in opener's diamond) — final 4D-S went down.
    # Q-Plus reached 3NT-S for +690.
    if (p_last.alert and p_last.level >= 3
            and p_last.suit is not None and p_last.suit != op_suit
            and op_suit in (Suit.HEARTS, Suit.SPADES)):
        # Phase F: splinter slam-eval based on playing-tricks + ACTIVE
        # values (top honours in suits OTHER than partner's splinter
        # suit — values in the shortness suit are wasted opposite
        # partner's 0-1 holding). Previous gate (`controls >= 4 +
        # losers <= 5`) wrongly rejected hands like Deal 65 opener N
        # (17 HCP, 0 aces but 2 useful kings outside spades shortness,
        # 5-card heart fit, ~6 playing tricks) — the K-controls-only
        # combo failed the `controls >= 4` test but had real slam play.
        splinter_suit = p_last.suit
        useful_hcp = sum(e.suit_hcp[s] for s in
                         (Suit.SPADES, Suit.HEARTS,
                          Suit.DIAMONDS, Suit.CLUBS)
                         if s != splinter_suit)
        slam_qualified = (
            # Strong: 6+ playing tricks + 14+ useful HCP
            (e.playing_tricks >= 6.0 and useful_hcp >= 14)
            # Or: 4+ controls (legacy gate preserved)
            or (e.losers <= 5 and e.controls >= 4)
        )
        if slam_qualified:
            cuebid = _maybe_initiate_cuebid(state, e, trump=op_suit)
            if cuebid is not None:
                return cuebid
            return bid(4, Suit.NOTRUMP, alert=True,
                       why=f"RKC after splinter ({useful_hcp} useful "
                           f"HCP outside {splinter_suit.to_char()}, "
                           f"{e.playing_tricks:.1f} PT)")
        return bid(4, op_suit, why="Sign off after splinter")
    if (p_last.alert and p_last.level >= 3
            and p_last.suit is not None and p_last.suit != op_suit
            and op_suit in (Suit.CLUBS, Suit.DIAMONDS)):
        # Strong jump-shift response (Precision-style positive +
        # long suit). Partner showed 16+ HCP and 5+ in their
        # suit. Combined min: 16 + 11 (Precision 1D floor) = 27.
        # Best bids:
        #   1. 4+ trump support for partner's suit → 4 of suit
        #      (game in the minor) or 4NT RKC with slam interest
        #   2. Balanced + stoppers in unbid suits → 3NT
        #   3. 6+ own suit → rebid it at the 4-level
        partner_suit = p_last.suit
        if e.suit_lengths.get(partner_suit, 0) >= 4:
            if e.hcp >= 14:
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"RKC after partner's jump-shift "
                               f"{partner_suit.to_char()} (slam)")
            return bid(4, partner_suit,
                       why=f"4{partner_suit.to_char()}: 4-card "
                           f"support after jump-shift (game)")
        if e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why="3NT: balanced after partner's "
                           "jump-shift (game)")
        if e.suit_lengths.get(op_suit, 0) >= 6:
            return bid(4, op_suit,
                       why=f"4{op_suit.to_char()}: 6+ own suit "
                           f"after partner's jump-shift")
        # No clear bid — 3NT as last resort (still game-level,
        # better than rebidding a non-fitting minor).
        return bid(3, Suit.NOTRUMP,
                   why="3NT: no clear bid after partner's "
                       "jump-shift")

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
        # Reverse with extras: 17+ HCP + 4+ higher-rank second suit.
        # Must outrank partner's 2-level bid. Shows extras AND the
        # additional suit; preferred over the simple 5+ rebid because
        # it preserves slam exploration room. Deal 65 in slam corpus
        # 59517: N held 17 HCP + 5H + 4S after 1H-2D; old code went
        # straight to 2H "Rebid 5+H" simple rebid, hiding the 4-card
        # spade suit. Q-Plus's N bids 2S reverse, then S's slam path
        # opens up.
        if (e.second_suit is not None
                and _BID_RANK[e.second_suit] > _BID_RANK[op_suit]
                and _BID_RANK[e.second_suit] < _BID_RANK[Suit.NOTRUMP]
                and _legal_two(e.second_suit)
                and e.suit_lengths[e.second_suit] >= 4
                and e.hcp >= 17):
            return bid(2, e.second_suit,
                       why=f"Reverse 2{e.second_suit.to_char()} "
                           f"(17+ HCP, 4+{e.second_suit.to_char()} "
                           f"after 2/1 GF response)")
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

    # 1M-1NT-2M2-3M2: partner returned preference to my SECOND
    # suit at the 3-level (invitational, showing 3+ in second
    # suit + 9-11 HCP). With 13+ HCP I accept the invite and bid
    # game; with 12 I pass. Deal #26 (seed 7371): S opened 1S,
    # N forcing-1NT, S 2H, N 3H preference; biq passed 3H even
    # with 13 HCP — Q-Plus pushed to 4H game for -12 IMP.
    # 1M-2X-2Y-3M: after my reverse (2Y), responder raised MY FIRST
    # SUIT to the 3-level, setting it as trump. I've shown 17+ HCP
    # via reverse + extras; combined 27+ HCP + 8+ major fit puts us
    # in slam zone. Cuebid the cheapest first-round control (Italian
    # style), or launch 4NT RKC if no controls to show. Deal 65 in
    # slam corpus 59517: this gap kept biq at 4H instead of
    # exploring the 7H grand Q-Plus reached.
    if (len(state.my_bids) >= 2
            and state.my_bids[-1].level == 2
            and state.my_bids[-1].suit is not None
            and state.my_bids[-1].suit != Suit.NOTRUMP
            and state.my_bids[-1].suit != op_suit
            and p_last.level == 3
            and p_last.suit == op_suit
            and op_suit in (Suit.HEARTS, Suit.SPADES)
            and hcp >= 16):
        cuebid = _maybe_initiate_cuebid(state, e, trump=op_suit)
        if cuebid is not None:
            return cuebid
        # No 1st-round controls to cuebid: launch 4NT RKC (we showed
        # extras via reverse, partner showed trump support — grand is
        # possible if we have all keys).
        return bid(4, Suit.NOTRUMP, alert=True,
                   why=f"RKC after my reverse + partner's "
                       f"3{op_suit.to_char()} trump set "
                       f"({hcp} HCP, slam zone)")

    if (len(state.my_bids) >= 2
            and state.my_bids[-1].level == 2
            and state.my_bids[-1].suit is not None
            and state.my_bids[-1].suit != Suit.NOTRUMP
            and state.my_bids[-1].suit != op_suit
            and p_last.level == 3
            and p_last.suit == state.my_bids[-1].suit):
        second = state.my_bids[-1].suit
        if second in (Suit.HEARTS, Suit.SPADES) and hcp >= 13:
            return bid(4, second,
                       why=f"4{second.to_char()}: accept preference "
                           f"invite (13+ HCP, partner pref. to 2nd "
                           f"suit)")
        # Minor preference: 3NT with stoppers, otherwise pass.
        if second in (Suit.CLUBS, Suit.DIAMONDS) and hcp >= 14 and e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why="3NT: 14+ balanced, minor preference invite")

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
            return _stayman_responder_rebid(state, e, p_last, system)

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

    # Precision 2♦ three-suiter relay: I bid 2NT asking, partner has
    # clarified shortness/strength — place the contract.
    if (op.level == 2 and op.suit == Suit.DIAMONDS
            and any(k.startswith("B-2D.Precision") for k in system.raw_rules)
            and len(state.my_bids) >= 1
            and state.my_bids[0].level == 2
            and state.my_bids[0].suit == Suit.NOTRUMP):
        return _precision_2d_relay_followup(state, e, p_last)

    # If partner showed extras, drive to game; if min, settle
    return _generic_responder_rebid(state, e, p_last, system)


def _precision_2d_relay_followup(state, e: HandEval, p_last: Bid) -> Bid:
    """After 2♦-(P)-2NT-(P)-X, pick the final contract.

    Opener's X conveys:
        3C / 4C   → 4 clubs side suit (3C min, 4C max).
        3D        → minimum, no long side suit.
        3NT       → max balanced-ish.
        3H / 3S   → minimum with 5+ in that major.
    """
    sp = e.suit_lengths[Suit.SPADES]
    hr = e.suit_lengths[Suit.HEARTS]
    hcp = e.hcp

    if p_last.level == 4 and p_last.suit == Suit.CLUBS:
        if sp >= 4:
            return bid(4, Suit.SPADES,
                       why=f"After max-club show: {sp} spades")
        if hr >= 4:
            return bid(4, Suit.HEARTS,
                       why=f"After max-club show: {hr} hearts")
        if sp >= 3 and sp >= hr:
            return bid(4, Suit.SPADES,
                       why=f"After max-club show: {sp} spades (4-3 fit)")
        if hr >= 3:
            return bid(4, Suit.HEARTS,
                       why=f"After max-club show: {hr} hearts (4-3 fit)")
        return passb(why="No major fit; pass opener's 4C")

    if p_last.level == 3 and p_last.suit == Suit.NOTRUMP:
        return passb(why="Accept opener's 3NT (max balanced)")

    if p_last.level == 3 and p_last.suit in (Suit.HEARTS, Suit.SPADES):
        major = p_last.suit
        if e.suit_lengths[major] >= 3 and hcp >= 14:
            return bid(4, major,
                       why=f"Game in {major.to_char()}: {hcp} HCP + fit")
        return passb(why=f"Pass opener's 3{major.to_char()} (min)")

    if p_last.level == 3 and p_last.suit in (Suit.CLUBS, Suit.DIAMONDS):
        if sp >= 4 and hcp >= 14:
            return bid(4, Suit.SPADES,
                       why=f"Game in spades: {hcp} HCP + {sp} spades")
        if hr >= 4 and hcp >= 14:
            return bid(4, Suit.HEARTS,
                       why=f"Game in hearts: {hcp} HCP + {hr} hearts")
        if sp >= 3:
            return bid(3, Suit.SPADES,
                       why=f"Suggest spade game: {sp} spades")
        if hr >= 3:
            return bid(3, Suit.HEARTS,
                       why=f"Suggest heart game: {hr} hearts")
        return passb(why="No major fit, no game")

    return passb(why="No clear action after 2D relay")


def _stayman_responder_rebid(state, e, opener_rebid: Bid,
                             system=None) -> Bid:
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
        # Smolen continuation: if my SECOND bid was a Smolen 3-of-major
        # (4-of-lower + 5-of-higher) AND opener's response is at the
        # 3-level showing preference to my 5-card suit, we're in
        # slam zone with combined 27+ HCP + 8-card fit. Lower the
        # slam-threshold to 12 HCP (instead of fresh-Stayman's 17).
        is_smolen_continuation = (
            len(state.my_bids) >= 2
            and state.my_bids[1].level == 3
            and state.my_bids[1].suit in (Suit.HEARTS, Suit.SPADES)
            and opener_rebid.level == 3)
        if fit >= 4 or is_smolen_continuation:
            if is_smolen_continuation and fit < 4:
                # Smolen showed 5 cards — re-derive fit from my hand.
                fit = e.suit_lengths.get(major, 0)
            # Slam launch threshold depends on opener's NT range.
            # 15-17 NT → 17+ responder is the classic Blackwood
            # threshold (combined 32+ → slam). For weak NT (Acol
            # 12-14), combined needs the same 32+ → responder
            # needs 18+. Without this gate, Acol board 8 has a
            # 4-4 fit Stayman launch slam on combined 25 HCP and
            # goes down (seed=42 board 8 in Acol).
            #
            # Use the actual NT range from the system when
            # available; default to 15 if not (matches SAYC).
            # For 2NT openings, use the 2NT-range floor (20 in SAYC,
            # 22 in Precision 70) so responder's slam threshold drops
            # appropriately. Deal 54 (slam 95512): N held 15 HCP +
            # 6H + balanced after S's 2NT-3D-3H sequence; old code
            # used the 1NT floor (15) → threshold 17 → 15-HCP responder
            # signed off in 4H. With 2NT floor (20) → threshold 12 →
            # 15 HCP qualifies, slam path opens.
            is_2nt_opening = (state.opening_bid is not None
                              and state.opening_bid.level == 2
                              and state.opening_bid.suit == Suit.NOTRUMP)
            if is_2nt_opening:
                nt_min = (getattr(system, "two_nt_min_hcp", 20)
                          if system is not None else 20)
            else:
                nt_min = (getattr(system, "one_nt_min_hcp", 15)
                          if system is not None else 15)
            # Threshold: need combined ≥ 32 to launch slam.
            slam_threshold = max(0, 32 - nt_min)  # 17 for 15-NT, 12 for 20-NT
            # Smolen lowers threshold: opener showed extras via 3-level
            # preference (max NT range) and we have 5-4 majors.
            if is_smolen_continuation:
                slam_threshold = max(0, 32 - nt_min - 5)  # 12 for 15-NT
            if hcp >= slam_threshold:
                cuebid = _maybe_initiate_cuebid(state, e, trump=major)
                if cuebid is not None:
                    return cuebid
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"Blackwood: slam try, 4-4 "
                               f"{major.to_char()} fit found via "
                               f"Stayman, {hcp} HCP (threshold "
                               f"{slam_threshold} for {nt_min}+ "
                               f"NT)")
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

    # 1M-2X-2M-2NT-3M preference: I bid 2/1 then 2NT (typically a
    # GF probe asking opener for more info); opener rebid the major
    # a SECOND time, confirming 6+ trumps (or strong 5+ in a 2/1 GF
    # context). With 2+ card support give preference to 4M — even a
    # 2-card support yields a 7+ card fit and 4M is often safer than
    # 3NT when opener has shown a 6+ suit. Without this branch the
    # auction died (responder passes 3M, sanity wrapper substitutes
    # "balanced NT" → 3NT signoff). Matrix 56428: 7 deals lost -77
    # IMP through this path.
    if (op is not None
            and op.level == 1
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and len(state.my_bids) >= 2
            and state.my_bids[0].level == 2
            and state.my_bids[0].suit not in (None, Suit.NOTRUMP,
                                               op.suit)
            and state.my_bids[-1].level == 2
            and state.my_bids[-1].suit == Suit.NOTRUMP
            and opener_rebid.level == 3
            and opener_rebid.suit == op.suit):
        fit = e.suit_lengths.get(op.suit, 0)
        if fit >= 2:
            return bid(4, op.suit,
                       why=f"4{op.suit.to_char()}: preference to "
                           f"opener's 3-times-bid major (2+ support, "
                           f"GF context after 2/1 + 2NT relay)")

    # 2NT post-transfer slam exploration: after 2NT-3D-3H or
    # 2NT-3H-3S (Jacoby transfer + accept), responder has shown 5+
    # in the major. With combined HCP in the slam zone (≥33),
    # drive past 3M with quantitative 4NT or RKC. Deal 54 (slam
    # 95512): N held 15 HCP + 6H + 4S after S's 2NT-3D-3H; old
    # code passed 3H (-15 IMP vs Q-Plus's 7NT via 4C Gerber path).
    if (op is not None
            and op.level == 2 and op.suit == Suit.NOTRUMP
            and state.my_bids
            and state.my_bids[0].level == 3
            and state.my_bids[0].suit in (Suit.DIAMONDS, Suit.HEARTS)
            and opener_rebid.level == 3
            and opener_rebid.suit in (Suit.HEARTS, Suit.SPADES)):
        # Identify the transferred-to major (the one opener
        # accepted).
        transfer_major = opener_rebid.suit
        nt_min = (getattr(system, "two_nt_min_hcp", 20)
                  if system is not None else 20)
        combined_min = hcp + nt_min
        # 37+ → leap 7-of-trump.
        if combined_min >= 37:
            return bid(7, transfer_major,
                       why=f"7{transfer_major.to_char()} count after "
                           f"2NT-transfer: {hcp}+{nt_min}+ ≥ 37 combined")
        # 33+ → small slam zone, drive via RKC if I have 6+ trumps,
        # or 4NT quant with 5-card trump (let opener decide).
        if combined_min >= 33:
            if e.suit_lengths.get(transfer_major, 0) >= 6:
                cuebid = _maybe_initiate_cuebid(state, e,
                                                 trump=transfer_major)
                if cuebid is not None:
                    return cuebid
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"RKC: 2NT-transfer + 6+{transfer_major.to_char()} "
                               f"+ {hcp} HCP ({combined_min}+ combined)")
            return bid(4, Suit.NOTRUMP, alert=True,
                       why=f"Quant 4NT: 2NT-transfer + 5+"
                           f"{transfer_major.to_char()} + {hcp} HCP "
                           f"({combined_min}+ combined)")
        # 30-32 → game in trump.
        if combined_min >= 26:
            return bid(4, transfer_major,
                       why=f"4{transfer_major.to_char()}: game after "
                           f"2NT-transfer accept ({hcp} HCP)")

    # 2/1 forcing-1NT follow-up: if my first response was a forcing
    # 1NT over partner's 1-of-major and partner rebid 2-of-the-same-
    # major (showing 5+ trumps), I implicitly had 3-card support
    # (that's why I chose 1NT instead of a direct raise). With my
    # 10-12 HCP and the now-confirmed 8+-card fit, drive to game.
    # Without this, responder passes opener's 2M rebid (seed=42
    # board 4 in 2/1: 1H-1NT-2H-P, should be 1H-1NT-2H-4H).
    if (system is not None
            and system.has("A-1MA-forcing-1NT")
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit == Suit.NOTRUMP
            and opener_rebid.level == 2
            and opener_rebid.suit == op.suit):
        fit = e.suit_lengths.get(op.suit, 0)
        if fit >= 3:
            if hcp >= 10:
                return bid(4, op.suit,
                           why=f"2/1 forcing-1NT follow-up: "
                               f"4{op.suit.to_char()} game with "
                               f"{hcp} HCP + {fit}-card fit")
            if hcp >= 8:
                return bid(3, op.suit,
                           why=f"2/1 forcing-1NT follow-up: "
                               f"3{op.suit.to_char()} invitational")

    # Acol natural-2/1 follow-up: 1M-2m(natural F1)-2M-?, I bid the
    # minor with 4+ cards and 10-12 HCP, partner rebid their major
    # showing 5+ cards. With 3-card support I now give preference
    # to the major. 10+ HCP and 8+-card heart fit (3 + 5 from
    # partner's rebid) → 3M invitational (partner accepts to game
    # with extras).
    if (system is not None
            and getattr(system, "one_major_card_min", 5) <= 4
            and not system.has("A-1MA-forcing-1NT")
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and state.my_bids
            and state.my_bids[0].level == 2
            and state.my_bids[0].suit in (Suit.CLUBS, Suit.DIAMONDS)
            and opener_rebid.level == 2
            and opener_rebid.suit == op.suit):
        fit = e.suit_lengths.get(op.suit, 0)
        if fit >= 3:
            return bid(3, op.suit,
                       why=f"Acol preference: 3{op.suit.to_char()} "
                           f"after natural 2-of-minor + opener's "
                           f"major rebid ({hcp} HCP, "
                           f"{fit}-card fit)")

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
        # NMF fires only when partner might still hold a useful major
        # fit we haven't found: (a) I have a 5+ major and want to find
        # 3-card support, or (b) 4-4 majors but the hand is only
        # invitational (11-12) — at game-force values with 4-4 majors
        # opener has already denied 4+ in either (else they'd have
        # raised), so just bid 3NT directly. Q-Plus's style on
        # seed=400 board 7: 1D-1H-1NT-3NT with 14 HCP 4-4 majors.
        if nmf_available and (
                e.suit_lengths.get(state.my_bids[-1].suit, 0) >= 5
                and hcp >= 11
                or (e.suit_lengths[Suit.SPADES] >= 4
                    and e.suit_lengths[Suit.HEARTS] >= 4
                    and 11 <= hcp <= 12)):
            nmf_minor = (Suit.CLUBS if op.suit == Suit.DIAMONDS
                         else Suit.DIAMONDS)
            return bid(2, nmf_minor, alert=True,
                       why=f"New Minor Forcing 2{nmf_minor.to_char()}: "
                           "asks about major fit")
        if 8 <= hcp <= 10 and e.suit_lengths.get(op.suit, 0) >= 5:
            return bid(2, op.suit, why="6-9 rebid in opener's suit (NMF substitute)")
        if 8 <= hcp <= 10:
            return bid(2, Suit.NOTRUMP, why="Invitational raise")
        # 1m-1M-1NT-? scale by HCP — opener showed 12-14 balanced,
        # so combined is HCP + 12 (floor) ↔ HCP + 14 (ceiling).
        # Textbook responder rebid:
        #   11-12   3NT (game; opener's 14 is just enough)
        #   13-15   3NT (signoff; partner is min)
        #   16-17   4NT quantitative slam invite (combined 28-31)
        #   18-19   6NT (combined ~30-33, near-cert small slam)
        #   20+     6NT (combined 32+ even opposite a min 12)
        # bridgeIQ used to lump every 11+ into 3NT — deal #43 had
        # E with 20 HCP signing off at 3NT, missing the 6NT-W that
        # Q-Plus reached (-11 IMP).
        if hcp >= 20:
            return bid(6, Suit.NOTRUMP,
                       why=f"Slam values opposite 12-14 NT "
                           f"({hcp}+12 ≥ 32)")
        # 16-19 HCP → 4NT quantitative. 18-19 was firing 6NT direct
        # but combined is only 30-32 — NOT small-slam zone. 33+
        # combined is the bridge requirement for a small slam; with
        # 18 + opener's 12-14, the conservative call is 4NT inviting
        # opener to bid 6NT with max range. Slam 15915 Deal 65: S
        # held 18 HCP after partner's 1C-1S-1NT rebid; old 18-HCP
        # gate fired 6NT direct, going down 1 vs Q-Plus's 3NT making
        # (-11 IMP).
        if hcp >= 16:
            return bid(4, Suit.NOTRUMP, alert=True,
                       why=f"Quantitative slam invite "
                           f"({hcp} opposite 12-14, combined 28-33)")
        if hcp >= 11:
            return bid(3, Suit.NOTRUMP, why="Game values (3NT)")
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
        if opener_rebid.level == 2 and e.suit_lengths.get(major, 0) >= 4:
            # 17+ HCP with 4+ trump support and opener has shown
            # an opening (~12-15 from a simple raise) → combined
            # ~29+ HCP, slam zone. Launch RKC. Seed=42 board 8 in
            # SAYC/French: E has 19 HCP, partner W raises to 2♥,
            # E should ask for keycards (or cuebid) rather than
            # signing off in 4♥.
            if hcp >= 17:
                # Italian cuebid first — show 1st-round side-suit
                # control before launching RKC. Partner sees which
                # suit we control and can cuebid back.
                cuebid = _maybe_initiate_cuebid(state, e, trump=major)
                if cuebid is not None:
                    return cuebid
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"RKC: 17+ HCP + 4+ trumps after "
                               f"partner's raise (slam zone)")
            if hcp >= 10:
                return bid(4, major,
                           why="Game raise after partner's support")
        # 6+ trump support + shape (void or singleton): the long-trump
        # / freak distribution lets responder push to game with fewer
        # HCP than the standard 10+. Deal 93 seed 39477: S held
        # ♠KJT742 ♥4 ♦void ♣KQT942 (9 HCP, 6-1-0-6) after 1D-1S-2S;
        # biq passed (going to wrapper-3S), Q-Plus reached 4S. The
        # shape is worth ~5 dist points on top of HCP → playing
        # strength of a 14-point hand; combined 24+ with opener →
        # easy 4M with 8+-card fit.
        if (opener_rebid.level == 2
                and major in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths.get(major, 0) >= 6
                and (e.voids >= 1 or e.singletons >= 1)
                and hcp >= 8):
            return bid(4, major,
                       why=f"4{major.to_char()}: 6+ trumps + shape "
                           f"({hcp} HCP, void/singleton compensates)")
        if opener_rebid.level == 3 and major in (Suit.HEARTS, Suit.SPADES):
            # Opener JUMP-RAISED my major — textbook shows 16-19
            # HCP and 4-card trump support. Combined: HCP + 16+.
            # With 6+ HCP responder bids game (4M).
            # Deal #57 (seed 7371): N opened 1D, S responded 1H,
            # N jumped to 3H showing 16-19 + 4H. S had 8 HCP + 4
            # hearts; biq passed for 3H-S (-12 IMP) instead of
            # bidding 4H game.
            # Slam check: with 15+ HCP + 5+ trumps, combined is
            # 31-36 HCP + 9+ card trump fit → small slam zone.
            # Launch RKC; partner's keycard response tells us
            # whether grand is on. Deal 85 seed 28391: S held
            # 17 HCP + 6♥ after N's 3H jump-raise; biq signed
            # off in 4H, Q-Plus drove to 7H grand slam for
            # -17 IMP.
            # Strong-2C exception: when opener bid 2C strong (22+ HCP)
            # then jump-raised my major, combined is ALWAYS in slam
            # zone (22 + 6+ ≥ 28; with 5+ trumps the fit covers the
            # 3rd loser). Lower the slam-launch HCP threshold from
            # 15 to 6 when opener's opening was strong-2C alerted.
            # Deal 5 (slam 67238): S held 8 HCP + 5H + SA after
            # 2C-2H-3H sequence; old 15-HCP gate signed off in 4H
            # (-13 IMP vs Q-Plus's 6H reached via S's 3S cuebid +
            # opener's 4NT RKC).
            after_strong_2c = (op is not None
                               and op.level == 2
                               and op.suit == Suit.CLUBS
                               and op.alert)
            slam_threshold = 6 if after_strong_2c else 15
            if (hcp >= slam_threshold
                    and e.suit_lengths.get(major, 0) >= 5):
                # Italian cuebid first — partner's jump-raise puts
                # us in the slam zone; cuebid the cheapest 1st-round
                # control before asking keycards. This is the path
                # that recovers Deal 65 (StandardFrench) and Deal 86
                # (StandardFrench) in slam corpus 59517 — Q-Plus
                # gets to grand via cuebid exchange; biq used to
                # jump straight to 4NT and stop at small slam.
                cuebid = _maybe_initiate_cuebid(state, e, trump=major)
                if cuebid is not None:
                    return cuebid
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"RKC after opener's jump-raise: "
                               f"{hcp} HCP + "
                               f"{e.suit_lengths.get(major, 0)}-card "
                               f"{major.to_char()}, slam zone "
                               f"(combined ≥ 31)")
            if hcp >= 6:
                return bid(4, major,
                           why=f"4{major.to_char()}: game after "
                               f"opener's jump-raise (16-19 + fit)")
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
                cuebid = _maybe_initiate_cuebid(state, e, trump=op.suit)
                if cuebid is not None:
                    return cuebid
                return bid(4, Suit.NOTRUMP, alert=True,
                           why=f"Blackwood: slam try, 4+{op.suit.to_char()} "
                               f"support, opener showed 5+")
            if hcp >= 13:
                return bid(4, op.suit,
                           why=f"4{op.suit.to_char()}: game in known fit")
            # 2/1 GF was established by my own 2-of-new bid — even
            # at the minimum (12 HCP), the partnership is forced to
            # game. Opener's simple rebid showed minimum (12-14),
            # so 24+ combined HCP with a 9-card major fit is enough
            # for 4M; bid game rather than passing partner's 2M.
            return bid(4, op.suit,
                       why=f"4{op.suit.to_char()}: 2/1 GF forces "
                           f"game with 4+ trump fit (min responder)")
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

    # 1M-1S/1H/1NT-2M (opener rebid own major after responder's
    # 1-level response — NOT 2/1). Opener has shown 6+ in the major
    # and 12-14 HCP min. Responder's options depend on HCP and fit:
    #   * 3+ support, 10-12 HCP → 3M invitational
    #   * 3+ support, 13+ HCP   → 4M game
    #   * 2-or-less support, 13+ balanced + stoppers → 3NT
    #   * 2-or-less support, 11-12 balanced → 2NT invitational
    #   * Weak (6-9), no fit    → pass 2M
    # bridgeIQ used to fall through entirely — deal #20 (seed 7371):
    # S had 15 HCP, 4-2-4-3 (only 2-card heart support) after 1H-
    # 1S-2H; biq passed for 2H-N. Q-Plus's S bid 4H (jumping with
    # the spotty support); textbook actually says 3NT with balanced
    # 13+. Either is better than pass.
    if (opener_rebid.level == 2
            and opener_rebid.suit == op.suit
            and op.suit in (Suit.HEARTS, Suit.SPADES)
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit is not None
            and state.my_bids[0].suit != Suit.NOTRUMP):
        fit = e.suit_lengths.get(op.suit, 0)
        if fit >= 3:
            if hcp >= 13:
                return bid(4, op.suit,
                           why=f"4{op.suit.to_char()}: 3+ trump support, "
                               f"13+ HCP, game with opener's known 6+")
            if hcp >= 10:
                return bid(3, op.suit,
                           why=f"3{op.suit.to_char()}: 3+ support, "
                               f"10-12 invitational")
            # 6-9 with 3+ support — accept the 2-level signoff.
            return passb(why=f"Pass 2{op.suit.to_char()}: "
                             f"6-9 with support, accept signoff")
        # 2-or-less support: lean toward NT or fall through.
        if hcp >= 13 and e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why=f"3NT: 13+ balanced, "
                           f"no {op.suit.to_char()} fit")
        if 11 <= hcp <= 12 and e.is_balanced:
            return bid(2, Suit.NOTRUMP,
                       why=f"2NT: 11-12 balanced, "
                           f"no {op.suit.to_char()} fit")
        # 13+ with 5+ own suit — rebid it.
        own = state.my_bids[0].suit
        if hcp >= 13 and e.suit_lengths.get(own, 0) >= 5:
            return bid(3, own,
                       why=f"3{own.to_char()}: 13+ HCP, rebid 5+ "
                           f"own suit (no {op.suit.to_char()} fit)")
        # Otherwise pass.
        return passb(why=f"Pass 2{op.suit.to_char()}: insufficient "
                         f"values to act further")

    # 1m-1M-2m (opener rebid own minor after responder's 1-major
    # response). Opener has shown 6+ diamonds (or 5+ in some
    # Precision flavors) and ~11-15 HCP. Responder's choices:
    #   * 6+ own major   → 3M (rebid showing length, GF or inv)
    #   * 13+ balanced + stoppers → 3NT (game)
    #   * 11-12 balanced + stoppers → 2NT invitational
    #   * 6-9, no fit    → pass
    # Deal #189 (analysis seed 38263): N opened 1D, S responded
    # 1H, N rebid 2D (6 diamonds); biq's S (14 HCP balanced, 5
    # hearts) PASSED 2D for +150 instead of bidding 3NT for +650.
    if (opener_rebid.level == 2
            and opener_rebid.suit == op.suit
            and op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit in (Suit.HEARTS, Suit.SPADES)):
        my_major = state.my_bids[0].suit
        own_len = e.suit_lengths.get(my_major, 0)
        # 6+ own major → rebid showing length, force one round.
        if own_len >= 6 and hcp >= 10:
            target = 4 if hcp >= 13 else 3
            return bid(target, my_major,
                       why=f"{target}{my_major.to_char()}: rebid "
                           f"6+ own major after opener's 2{op.suit.to_char()}")
        # 18+ HCP after partner's 2m rebid → slam zone (combined
        # 29-33+). With 3+ minor support, raise to 3m as forcing
        # slam-try (the responder side is at 18+, partner has 11-15,
        # so 3m by responder is unambiguously game-forcing here).
        # Deal 78 slam corpus 59517: N had 22 HCP after partner S's
        # 1D-1H-2D; biq used to bid 3NT signoff. With the slam-try
        # 3m bid, biq reaches 5D instead of 3NT — still short of
        # the 7NT Q-Plus grand, but the route is now exposed for a
        # follow-on opener-rebid fix.
        if hcp >= 18 and e.suit_lengths.get(op.suit, 0) >= 3:
            return bid(3, op.suit, alert=True,
                       why=f"3{op.suit.to_char()}: 18+ HCP, slam try "
                           f"with 3+ minor support")
        # 13+ HCP balanced (with implicit stoppers from
        # responding 1M without 6-card suit) → 3NT for game.
        if hcp >= 13 and e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why=f"3NT: 13+ balanced after opener's "
                           f"2{op.suit.to_char()} rebid")
        # 11-12 balanced → 2NT invitational.
        if 11 <= hcp <= 12 and e.is_balanced:
            return bid(2, Suit.NOTRUMP,
                       why=f"2NT: 11-12 balanced invitational "
                           f"after opener's 2{op.suit.to_char()}")
        # 11-12 with 5+ own major → 3M jump rebid (invitational).
        if 11 <= hcp <= 12 and own_len >= 5:
            return bid(3, my_major,
                       why=f"3{my_major.to_char()}: 11-12 + 5+ "
                           f"own suit (invitational jump rebid)")
        # Otherwise pass — 6-9 HCP with no game prospects.
        return passb(why=f"Pass 2{op.suit.to_char()}: 6-9 HCP, "
                         f"no game prospects")

    # 1M-1M-2-of-new-suit (1-level response, opener rebid new suit
    # at 2-level showing 5+ in opener's first suit + 4+ in the
    # second). Responder's preference back to opener's first suit
    # with 3+ support shows game-invitational values. Seed=42
    # board 3 Acol: 1H-1S-2D-? with N holding ♠A8743 ♥965 ♦AQ7
    # ♣JT (11 HCP) → 3H preference.
    if (op.suit in (Suit.HEARTS, Suit.SPADES)
            and opener_rebid.level == 2
            and opener_rebid.suit is not None
            and opener_rebid.suit != Suit.NOTRUMP
            and opener_rebid.suit != op.suit
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit is not None
            and state.my_bids[0].suit != Suit.NOTRUMP):
        fit_major = e.suit_lengths.get(op.suit, 0)
        fit_minor = e.suit_lengths.get(opener_rebid.suit, 0)
        if fit_major >= 3 and 10 <= hcp <= 12:
            return bid(3, op.suit,
                       why=f"Preference to opener's "
                           f"{op.suit.to_char()} ({fit_major}-card "
                           f"support, {hcp} HCP invitational)")
        if fit_major >= 3 and hcp >= 13:
            return bid(4, op.suit,
                       why=f"Game in opener's "
                           f"{op.suit.to_char()} ({fit_major}-card "
                           f"support, {hcp} HCP)")
        if fit_minor >= 4 and hcp >= 12:
            return bid(3, opener_rebid.suit,
                       why=f"Raise opener's second suit "
                           f"({fit_minor}-card fit, {hcp} HCP)")

    # 1m-1M-2X (opener minor, responder major, opener new suit):
    # responder with extras MUST keep bidding. A textbook hand like
    # deal #29 (S after 1D-1S-2C: 13 HCP, 5 spades, 4 hearts) cannot
    # PASS 2C — partner's new-suit rebid is non-limiting and we have
    # game-forcing values. Options in textbook order:
    #   * 4+ other-major → bid it (new suit, forcing one round)
    #   * 5+ own major + ≥10 → 3-of-own (jump rebid showing 6+ … or
    #     just 2-of-own with min); with 13+ we want game so jump.
    #   * 4+ opener's first minor + ≥12 → raise (already above)
    #   * Balanced 13-15 with stoppers → 3NT
    #   * 4th-suit-forcing in the unbid suit with ≥11 (GF)
    if (op.suit in (Suit.CLUBS, Suit.DIAMONDS)
            and opener_rebid.level == 2
            and opener_rebid.suit is not None
            and opener_rebid.suit != Suit.NOTRUMP
            and opener_rebid.suit != op.suit
            and state.my_bids
            and state.my_bids[0].level == 1
            and state.my_bids[0].suit in (Suit.HEARTS, Suit.SPADES)
            and hcp >= 9):
        my_major = state.my_bids[0].suit
        other_major = (Suit.SPADES if my_major == Suit.HEARTS
                       else Suit.HEARTS)
        rebid_suit = opener_rebid.suit
        # PRIORITY: 3+ cards in opener's rebid major (= 8+ card fit)
        # with game values. After partner's REVERSE / strong rebid
        # showing the major, an 8-card fit + 11+ HCP combined with
        # partner's strong showing (typically 16+) is a game-going
        # auction; raise to game directly. Without this, biq's
        # 12-HCP semi-balanced hand falls through to 2NT invitational,
        # missing the spade game.
        # Base #1 deck idx 180 seed 36866: S held S♠AK2 H♠JT752 D♠KJ9
        # C♠96 (12 HCP, 3-5-3-2) after Precision 1C-1H-2S. biq bid
        # 2NT → N passed → 2NT-S (NS-100 vul). Q-Plus raised to 4S
        # game (NS+620). 5 cells × −11 IMP.
        if (rebid_suit in (Suit.HEARTS, Suit.SPADES)
                and rebid_suit != my_major
                and e.suit_lengths.get(rebid_suit, 0) >= 3):
            if hcp >= 12:
                return bid(4, rebid_suit,
                           why=f"4{rebid_suit.to_char()}: 3+ support "
                               f"for partner's REAL major, {hcp} HCP "
                               f"(strong-1C / reverse → game)")
            if hcp >= 8:
                return bid(3, rebid_suit,
                           why=f"3{rebid_suit.to_char()}: 3+ support "
                               f"for partner's REAL major, {hcp} HCP "
                               f"(invitational raise)")

        # 4+ other major — bid it as a new suit (F1).
        # The level depends on whether the other major outranks
        # opener's rebid suit.
        if (e.suit_lengths.get(other_major, 0) >= 4
                and _BID_RANK[other_major] != _BID_RANK[rebid_suit]):
            other_lvl = 2 if _BID_RANK[other_major] > _BID_RANK[rebid_suit] else 3
            if hcp >= 11 or other_lvl == 2:
                return bid(other_lvl, other_major,
                           why=f"{other_lvl}{other_major.to_char()}: "
                               f"new suit by responder (F1)")
        # Own major is 6+ (or 5+ with extras) — jump-rebid 3M with
        # game-invitational+ values.
        own_len = e.suit_lengths.get(my_major, 0)
        if own_len >= 6 and hcp >= 10:
            jump_lvl = 3 if hcp >= 11 else 2
            target_lvl = max(jump_lvl, 3)
            if hcp >= 13:
                return bid(4, my_major,
                           why=f"4{my_major.to_char()}: 6+{my_major.to_char()}, "
                               f"13+ HCP, jump to game")
            return bid(target_lvl, my_major,
                       why=f"{target_lvl}{my_major.to_char()}: 6+ own "
                           f"suit, {hcp} HCP invitational")
        # Balanced 13+ with stopper in unbid suit → 3NT.
        if hcp >= 13 and e.is_balanced:
            return bid(3, Suit.NOTRUMP,
                       why=f"3NT: balanced game values ({hcp} HCP)")
        # 11-12 balanced → 2NT invitational.
        if 11 <= hcp <= 12 and e.is_balanced:
            return bid(2, Suit.NOTRUMP,
                       why="2NT: 11-12 balanced, invitational")
        # 4SF / 4th-suit-forcing as GF inquiry: bid the unbid
        # suit when we have 13+ and no clearer call.
        if hcp >= 13:
            unbid = None
            for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
                if s not in (op.suit, my_major, rebid_suit):
                    unbid = s
                    break
            if unbid is not None:
                lvl = 2 if _BID_RANK[unbid] > _BID_RANK[rebid_suit] else 3
                return bid(lvl, unbid, alert=True,
                           why=f"4th-suit-forcing {lvl}{unbid.to_char()}: "
                               f"GF inquiry ({hcp} HCP)")

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
        # 4+ in opener's new MAJOR + game values → raise to game.
        # Don't auto-jump for minors — 4-of-minor isn't game (5
        # is), and balanced 4-card minor support is better
        # described as 3NT. Reserve the minor-fit raise for hands
        # without NT-game prospects (e.g. no balanced shape).
        if (new_suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths.get(new_suit, 0) >= 4
                and hcp >= 13):
            return bid(4, new_suit,
                       why=f"4{new_suit.to_char()}: 4-card fit in opener's "
                           "new major")
        # 3-card support for opener's new major → raise to 3M
        # (forcing in GF context). This is the textbook response
        # in a strong-club Precision auction (1C-2D-2S) where
        # opener's spades = real, 1C was artificial. Without
        # this path, biq's responder would fall through to
        # "preference to opener's first suit" — which means 3C
        # (treating 1C as real clubs), defeating the spade fit.
        # Deal #157 (analysis): N had 5 spades, S had 3 spades
        # + 11 HCP; biq landed in 3C-N (+130) instead of 3NT-S
        # or 4S which Q-Plus reached for +600.
        if (new_suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths.get(new_suit, 0) >= 3
                and hcp >= 11):
            return bid(3, new_suit,
                       why=f"3{new_suit.to_char()}: 3-card support "
                           f"for opener's new major (GF context)")
        # 12+ balanced → 3NT (most common 2/1 GF stop)
        # Reverse + 3+ support for opener's FIRST major: set trump by
        # bidding 3-of-opener's-major (preference). Opener has shown
        # 17+ HCP via reverse; combined slam-zone. Must run BEFORE
        # the balanced-3NT check below, otherwise 5-3-3-2 responders
        # with 3-card support sign off in 3NT instead of slam-going.
        # Deal 65 (slam 59517): 4-card support drove biq to 7H grand.
        # Deal 18 (slam 67238): N held 5-3-3-2 + 3H + 13 HCP after
        # 1H-2D-2S — old 4+ threshold + balanced-3NT-first ordering
        # routed N to 3NT (−13 IMP vs Q-Plus's 6H).
        if (op.suit in (Suit.HEARTS, Suit.SPADES)
                and e.suit_lengths.get(op.suit, 0) >= 3
                and hcp >= 11):
            return bid(3, op.suit,
                       why=f"3{op.suit.to_char()}: 3+ support for "
                           f"opener's major after reverse "
                           f"(sets trump, slam zone)")
        if e.is_balanced and hcp >= 12:
            return bid(3, Suit.NOTRUMP,
                       why="3NT in 2/1 GF: balanced, no major fit")
        # Long own suit → rebid it
        if e.suit_lengths.get(my_suit, 0) >= 6:
            return bid(3, my_suit,
                       why=f"3{my_suit.to_char()}: rebid 6+ own suit")
        # Preference to opener's first suit — ONLY meaningful
        # when opener's first suit was natural (i.e., NOT
        # Precision's artificial strong 1C). When 1C was the
        # strong-club opening (no real club length), the
        # "preference" was a mistake; fall through to 3NT.
        precision_1c = (op.level == 1 and op.suit == Suit.CLUBS
                        and getattr(system, "strong_open_call",
                                    "2C") == "1C")
        if (not precision_1c
                and e.suit_lengths.get(op.suit, 0) >= 2):
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
        # Fourth-suit forcing (5cM systems only): with 12+ HCP, no
        # major fit found, bid the 4th unbid suit at the 2-level as
        # an artificial GF inquiry. Opener has shown 2 suits at the
        # 1-level; responder has shown 1; the 4th is the inquiry.
        # Avoids gambling 3NT without a stopper in the 4th suit.
        is_5cm = (system is not None
                  and getattr(system, "one_major_card_min", 5) >= 5)
        if is_5cm and hcp >= 12 and e.suit_lengths.get(new_major, 0) < 4:
            suits_bid = {op.suit, opener_rebid.suit, my_first_suit}
            fourth = next(
                (s for s in (Suit.CLUBS, Suit.DIAMONDS,
                             Suit.HEARTS, Suit.SPADES)
                 if s not in suits_bid),
                None)
            if (fourth is not None
                    and e.suit_lengths.get(fourth, 0) >= 3):
                return bid(2, fourth, alert=True,
                           why=f"Fourth-suit forcing 2{fourth.to_char()} "
                               f"(GF artificial inquiry)")
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

    Balancing seat (after 1NT-P-P): HCP requirements drop by 3
    (standard "borrow from partner" rule). Detected when both
    partner and the seat between us and 1NT-opener have passed —
    i.e., state.partner_bids has no non-pass calls AND
    state.rho_bids has only pass(es) since the 1NT.
    """
    hcp = e.hcp

    # Detect balancing seat: I'm the 4th hand after 1NT-P-P. My
    # partner is silent and RHO (opener's partner) passed too.
    partner_acted = any(not b.is_pass for b in state.partner_bids)
    rho_acted = any(not b.is_pass for b in state.rho_bids)
    is_balancing = (not partner_acted and not rho_acted)
    hcp_adjustment = 3 if is_balancing else 0

    # Penalty double: 15+ HCP, no singleton/void (covers balanced
    # 4-3-3-3 / 4-4-3-2 / 5-3-3-2 and the semi-balanced 5-4-2-2 /
    # 6-3-2-2). `is_semi_balanced` is narrowly defined as 5-3-3-2;
    # widen here so a strong 5-4-2-2 still penalty-doubles 1NT.
    #
    # BUT NOT with a 6+ card major or diamond — overcall the suit
    # instead (handled just below). Penalty-doubling 1NT on a long
    # one-suiter is a classic error: the double is meant for balanced
    # 15+ where defence beats 1NT, whereas a 6-card suit wants to
    # COMPETE — and if opener's side redoubles, a long-suit doubler
    # has no good escape (this cost −1560 on a 6-spade/15-HCP hand:
    # X → opp xx → passed out in 1NTxx). A 6+ CLUB one-suiter has no
    # natural 2-level call (2♣ = Landy), so it may still double.
    has_overcallable_6 = (e.suit_lengths[Suit.SPADES] >= 6
                          or e.suit_lengths[Suit.HEARTS] >= 6
                          or e.suit_lengths[Suit.DIAMONDS] >= 6)
    if (hcp >= 15 and e.voids == 0 and e.singletons == 0
            and not has_overcallable_6):
        return double(why=f"Penalty double of 1NT ({hcp} HCP, no short suit)")

    # Landy 2♣ — both majors, at least 4-4, competitive values.
    # Landy 2♣ — both majors. Q-Plus uses 9-12 HCP at 4-4 (with
    # 13+ HCP a defender prefers to sit 1NT for penalty rather
    # than push to the 2-level). 5-4 hands keep the 9-14 range.
    # In balancing seat, drop the HCP floor by 3 (Q-Plus board 9
    # seed=42: N has 7 HCP + 5-4 majors, balances with 2♣).
    landy_4_4 = (e.suit_lengths[Suit.HEARTS] == 4
                 and e.suit_lengths[Suit.SPADES] == 4)
    landy_hcp_max = 12 if landy_4_4 else 14
    landy_hcp_min = max(0, 9 - hcp_adjustment)
    if (system.has("O-1NT.Landy")
            and e.suit_lengths[Suit.HEARTS] >= 4
            and e.suit_lengths[Suit.SPADES] >= 4
            and landy_hcp_min <= hcp <= landy_hcp_max):
        return bid(2, Suit.CLUBS, alert=True,
                   why=f"Landy: both majors (4+/4+, {hcp} HCP, "
                       f"{'balancing' if is_balancing else 'direct'})")

    # Natural 2-level overcall with a 6-card suit. Range widened to 17
    # (was 15) so strong single-suiters overcall rather than fall into
    # the penalty double — a 6-card suit one-suiter belongs in its suit,
    # not defending 1NT(xx).
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS):
        if e.suit_lengths[s] >= 6 and 9 <= hcp <= 17:
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

    # Precision 2♦ three-suiter exception: opener has 0-1 diamonds,
    # so a natural diamond overcall isn't actually competing with
    # opener's suit — we're sitting on the only long diamond suit
    # at the table. seed=400 board 1 W (AKQJ954 in diamonds, 11
    # HCP, 1-3-7-2 shape) is the canonical case. With 6+ diamonds
    # and 10+ HCP, bid 3♦.
    is_precision_2d = (
        op.level == 2 and op.suit == Suit.DIAMONDS
        and any(k.startswith("B-2D.Precision")
                for k in system.raw_rules)
    )
    if (is_precision_2d
            and e.suit_lengths[Suit.DIAMONDS] >= 6
            and hcp >= 10
            and e.suit_hcp[Suit.DIAMONDS] >= 6):
        return bid(3, Suit.DIAMONDS,
                   why=f"Natural 3♦ vs Precision 2♦ three-suiter: "
                       f"{hcp} HCP, "
                       f"{e.suit_lengths[Suit.DIAMONDS]}♦")

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

    # Weak / competitive long-suit overcall. biq used to PASS these and
    # concede the auction — e.g. ♥KJT8643 / 6 HCP over 2♠ (seed 6515 d33):
    # a 7-card suit must compete (the LAW makes the 3-level safe opposite
    # partner's expected 2-3 trumps), and a good 6-card suit with ~8-10 HCP
    # should too. This is the dominant competitive-passivity leak: biq is
    # near-parity declaring + near-DD defending, but sits silent when the
    # opponents have the cards, so they play in peace.
    best = None
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        if s == op_suit:
            continue
        ln = e.suit_lengths[s]
        if ((ln >= 7 and hcp >= 5)
                or (ln == 6 and 8 <= hcp <= 10 and e.suit_hcp[s] >= 4)):
            if best is None or ln > e.suit_lengths[best]:
                best = s
    if best is not None:
        ln = e.suit_lengths[best]
        # A sub-invitational 6-card suit → Lebensohl 2NT relay (textbook
        # weak treatment) when the system has it, so a DIRECT 3-level stays
        # invitational+. A 7+ card suit just bids naturally — its length
        # makes a direct 3-level safe and unambiguous.
        if ln == 6 and system.has("C-Lebensohl.after-weak-2") and hcp < 11:
            return bid(2, Suit.NOTRUMP, alert=True,
                       why="Lebensohl 2NT relay (weak 6-card suit)")
        level = 2 if _BID_RANK[best] > _BID_RANK[op_suit] else 3
        cand = bid(level, best,
                   why=f"{level}{best.to_char()} competitive overcall "
                       f"({ln}-card suit, {hcp} HCP) over weak 2")
        if _is_legal_bid(cand, state):
            return cand

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
        # A 7+ card suit can compete on fewer values IF the overcall lands
        # at the 3-level (it outranks the preempt); a 4-level overcall still
        # needs the full 14+ (forcing partner that high is dangerous).
        will_be_3lvl = _BID_RANK[s] > _BID_RANK[opener_suit]
        min_hcp = 10 if (length >= 7 and will_be_3lvl) else 14
        if hcp < min_hcp:
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

    # Distributional overcall — a 6+ suit that lands CHEAPLY at the 3-level
    # (outranks the preempt) with real shape (short in opener's suit OR a 5+
    # second suit) competes on length + playing tricks even with a weak suit
    # and modest HCP. A 6-5 or void-in-their-suit hand has the tricks; passing
    # it sells out a likely game. Only at the 3-level (cheap) and 8-13 HCP
    # (above that the strict overcall / double already fired). (2428-19:
    # Q97642 + void clubs + AJT83, 9 HCP, over 3C → 3S.)
    if best_suit is None and 8 <= hcp <= 13:
        short_op = e.suit_lengths[opener_suit] <= 1
        dist = None
        for s in unbid:
            if (e.suit_lengths[s] >= 6
                    and _BID_RANK[s] > _BID_RANK[opener_suit]):
                second = any(e.suit_lengths[o] >= 5 for o in unbid if o != s)
                if short_op or second:
                    if dist is None or e.suit_lengths[s] > e.suit_lengths[dist]:
                        dist = s
        if dist is not None:
            cand = bid(op.level, dist,
                       why=f"{op.level}{dist.to_char()} distributional overcall "
                           f"({e.suit_lengths[dist]}-card + shape) over "
                           f"{op.level}{opener_suit.to_char()} preempt")
            if _is_legal_bid(cand, state):
                return cand

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

    # 4th-seat reopening (balancing) takeout double — partner and
    # RHO have passed, the opening bid is the only call. Partner
    # is marked with values (couldn't act over the opening). With
    # shortness in opener's suit + tolerance for unbid suits +
    # opening values (light: 11+), reopen with X. Partner gets
    # to bid a suit, NT, or penalty-pass with trumps.
    is_4th_seat_reopening = (
        op.level == 1
        and not state.partner_bids
        and not state.rho_bids
        and len(state.lho_bids) == 1
        and state.lho_bids[0].suit == op.suit
        and not state.my_bids
    )
    if (is_4th_seat_reopening
            and 11 <= hcp <= 17
            and e.suit_lengths[op.suit] <= 2
            and all(e.suit_lengths[s] >= 3 for s in unbid)):
        return double(why=f"Reopening (balancing) takeout X "
                          f"({hcp} HCP, short in opener's "
                          f"{op.suit.to_char()})")

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
    # Standard (12-16 HCP): require 3+ in EACH unbid suit so partner is safe
    #   bidding any of them.
    # Strong (17+ HCP): relax the all-3+ rule to allow ONE unbid suit with 2
    #   cards. Hands like 5-4-2-2 short in opener's suit with 17+ HCP have no
    #   other call available — too strong for a direct 2-level overcall
    #   (capped at 16 above), wrong shape for a balanced 1NT/19+ overcall, no
    #   stopper in their suit. The strong hand survives partner advancing
    #   into our 2-card suit because we'll rebid our own 5-card suit / NT
    #   showing the extras. Deal 66 seed 39477 was the canonical miss:
    #   S held S♠Tx H♠AKQ96 D♠AQJ6 C♠Jx (17 HCP, 5-4-2-2) and biq passed
    #   because all four paths failed — Q-Plus made the takeout-X and
    #   collected +1100 from a doomed 3HX-E later in the auction.
    if hcp >= 12 and e.suit_lengths[op.suit] <= 2:
        unbid_lengths = [e.suit_lengths[s] for s in unbid]
        # Strong takeout (17+ HCP): relax the 3-card unbid rule to
        # allow ONE 2-card unbid suit. Only on our FIRST action —
        # the strong X is descriptive enough that re-firing it on
        # opps' later bids would over-commit. The existing 12-16
        # takeout below CAN re-fire (catches penalty doubles of
        # opps' raise on the second round).
        if hcp >= 17 and not state.my_bids:
            n_2card = sum(1 for l in unbid_lengths if l == 2)
            if n_2card <= 1 and min(unbid_lengths) >= 2:
                return double(
                    why=f"Strong takeout X ({hcp} HCP, "
                        f"plan strong rebid showing extras)")
        if all(l >= 3 for l in unbid_lengths):
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

    # Strong hand (17+) with a good 6+ card suit that found no other
    # call — too strong for the 16-capped natural overcall, too
    # unbalanced (e.g. a singleton) for the strong takeout X. OVERCALL
    # the long suit and plan to bid again to show the extra strength.
    # Passing a 17+ HCP hand is the worst competitive error — Q-Plus's
    # aggressive bots punish it (e.g. ♠KQ76 ♥A ♦AKQJT7 ♣94 over 1♣ must
    # bid 2♦, not pass).
    if hcp >= 17:
        for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
            if s == op.suit:
                continue
            if e.suit_lengths[s] >= 6 and e.suit_hcp[s] >= 5:
                level = _cheapest_legal_level(s)
                if level <= 3:
                    return bid(level, s,
                               why=f"Strong {level}{s.to_char()} overcall "
                                   f"({hcp} HCP, good 6+ suit; rebid shows "
                                   f"extras)")

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

    # Landy 2♣ overcaller answering partner's 2♦ pass-or-correct.
    # I bid 2♣ Landy showing 4+/4+ majors; partner responded 2♦
    # asking me to pick the major. Bid the longer one (default to
    # hearts when 4-4).
    op = state.opening_bid
    if (my_first.level == 2 and my_first.suit == Suit.CLUBS
            and my_first.alert
            and op is not None and op.level == 1
            and op.suit == Suit.NOTRUMP
            and p_last.level == 2 and p_last.suit == Suit.DIAMONDS):
        sp = e.suit_lengths[Suit.SPADES]
        hr = e.suit_lengths[Suit.HEARTS]
        if hr >= sp:
            return bid(2, Suit.HEARTS,
                       why=f"Landy pass-or-correct → {hr}♥")
        return bid(2, Suit.SPADES,
                   why=f"Landy pass-or-correct → {sp}♠")

    # Partner doubled / redoubled — leave it.
    if p_last.is_double or p_last.is_redouble:
        return passb(why="Overcaller rebid — partner's X/XX, pass")

    # Partner raised my suit.
    if p_last.suit == my_suit:
        # Partner's 3-level raise = limit raise (10-12 HCP, 3+ support).
        # Accept to game (4M) when our hand has playing strength beyond
        # raw HCP. The bare HCP-only test (hcp >= 15 + length >= 6)
        # missed deal 38 (seed 39477): N overcalled 1♥ with 10 HCP +
        # 0-5-5-3 (void ♠ + 5-5 in ♥/♦), partner limit-raised to 3♥,
        # biq passed → 3H-N for -50; Q-Plus accepted to 4♥-W for
        # +700 NS, costing -13 IMP. Distributional points compensate
        # for low HCP when we have 5-5 shape + a void.
        if (my_suit in (Suit.HEARTS, Suit.SPADES)
                and p_last.level == 3
                and p_last.level < 5):
            has_void = e.voids >= 1
            has_shortness = e.singletons >= 1 or has_void
            has_extra_trump = my_length >= 6
            has_long_side = any(
                e.suit_lengths.get(s, 0) >= 5
                for s in (Suit.CLUBS, Suit.DIAMONDS,
                          Suit.HEARTS, Suit.SPADES)
                if s != my_suit)
            if hcp >= 14:
                return bid(4, my_suit,
                           why=f"Accept limit raise to 4{my_suit.to_char()} "
                               f"(14+ HCP)")
            if hcp >= 13 and (has_extra_trump or has_long_side
                              or has_shortness):
                return bid(4, my_suit,
                           why=f"Accept limit raise to 4{my_suit.to_char()} "
                               f"(13+ HCP + distributional extras)")
            if (hcp >= 10 and my_length >= 5 and has_long_side
                    and has_void):
                return bid(4, my_suit,
                           why=f"Accept limit raise to 4{my_suit.to_char()} "
                               f"(5-5 with void = playing strength)")
        # 15+ HCP and 6+ of the suit → push for game; else pass.
        if hcp >= 15 and my_length >= 6 \
                and p_last.level < 5:
            return bid(p_last.level + 1, my_suit,
                       why=f"Overcaller rebid — extras + long suit,"
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

    # Textbook principle: when partner has placed the contract at a
    # game level (4M, 3NT, 5m, or any 6/7), respect their judgment.
    # We've already had our say if we've taken any prior action.
    # Re-bidding after partner's game signoff is the trademark of
    # a panicked auction (deal #31: doubled then cuebid → partner
    # ended in 4H → we "corrected" to 5D for -1400 X-vul). Without
    # a known reason to override (very rare), PASS.
    have_already_spoken = any(
        (not bb.is_pass) for bb in state.my_bids)
    is_partner_game_signoff = (
        not p_last.is_pass and not p_last.is_double
        and not p_last.is_redouble and p_last.suit is not None
        and ((p_last.suit == Suit.NOTRUMP and p_last.level >= 3)
             or (p_last.suit in (Suit.HEARTS, Suit.SPADES)
                 and p_last.level >= 4)
             or (p_last.suit in (Suit.CLUBS, Suit.DIAMONDS)
                 and p_last.level >= 5)
             or p_last.level >= 6))
    if have_already_spoken and is_partner_game_signoff:
        return passb(why="Respect partner's game signoff "
                         f"({p_last.level}{p_last.suit.to_char()})")

    # Advancer over partner's Landy 2♣ overcall of opener's 1NT.
    # Landy promises 4+/4+ in the majors. Advancer:
    #   3-3 majors → 2♦ pass-or-correct (let partner pick the major).
    #   4+ in one major → bid that major (or higher with values).
    #   With ~10+ HCP and a major fit, jump-raise / cuebid for game.
    op = state.opening_bid
    if (op is not None and op.level == 1 and op.suit == Suit.NOTRUMP
            and p_last.level == 2 and p_last.suit == Suit.CLUBS
            and p_last.alert
            and len(state.partner_bids) == 1):
        sp = e.suit_lengths[Suit.SPADES]
        hr = e.suit_lengths[Suit.HEARTS]
        # Textbook Landy advances:
        #   • 4+ in one major, equal or longer than the other: bid that
        #     major (jump to game with 10+ HCP).
        #   • 3+ in one major, STRICTLY longer than the other: bid that
        #     major at the 2-level (no jump — partner can still be
        #     minimum). This is the "preference" advance.
        #   • 4-4 majors: bid hearts up the line.
        #   • 3-3 or 2-2: 2♦ pass-or-correct, asking Landy bidder to
        #     pick their own longer.
        # Base #4 seed 80719: E with 2♠ + 3♥ + 5 HCP after partner's
        # Landy 2♣; biq was bidding 2♦ (no major ≥ 4), losing the heart
        # fit. Q-Plus correctly bids 2♥ on 3♥-2♠ → 2♥-E going down for
        # NS+100. biq's 2♦ → opener corrects to 2♠ → 2♠-W making for
        # NS-110. Net swing across 25 cells of base #4 → ~-125 IMP.
        if sp >= 4 and sp >= hr:
            level = 4 if hcp >= 10 else 2
            return bid(level, Suit.SPADES,
                       why=f"Advance Landy: {sp}♠ ≥ {hr}♥, {hcp} HCP")
        if hr >= 4:
            level = 4 if hcp >= 10 else 2
            return bid(level, Suit.HEARTS,
                       why=f"Advance Landy: {hr}♥, {hcp} HCP")
        # 3+ in one major STRICTLY longer than other: prefer it.
        if sp >= 3 and sp > hr:
            return bid(2, Suit.SPADES,
                       why=f"Landy preference: {sp}♠ > {hr}♥ "
                           f"({hcp} HCP)")
        if hr >= 3 and hr > sp:
            return bid(2, Suit.HEARTS,
                       why=f"Landy preference: {hr}♥ > {sp}♠ "
                           f"({hcp} HCP)")
        # Equal majors (3-3 or 2-2): pass-or-correct.
        return bid(2, Suit.DIAMONDS, alert=True,
                   why=f"Landy 2♦ pass-or-correct: {sp}-{hr} "
                       f"majors equal, {hcp} HCP")

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
        # Only applies to suit auctions — over 1NT-X-(P), responder's
        # double would be a double-of-double which is illegal.
        # PRECONDITION: LHO must be a DIFFERENT opp than the opener
        # (i.e., the responder) AND have actually raised. Without
        # the "different opp" check, the branch trivially fires when
        # opener == LHO and their opening bid is read as a "raise".
        responder_lho = (state.lho_bids
                         and state.opener_seat is not None
                         and state.opener_seat != state.seat.next())
        if (system.has("C-responsive-double")
                and responder_lho and state.lho_bids):
            lho_last = state.lho_bids[-1]
            opener_suit = state.opening_bid.suit
            if (opener_suit is not None
                    and opener_suit != Suit.NOTRUMP
                    and not lho_last.is_pass
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

        # Cuebid opener's suit with 12+ HCP — GF inquiry asking
        # partner to describe further. Fires before the simple
        # 4-card-major advance (which would underbid GF strength).
        # Only meaningful over 1- or 2-level openings; over a
        # preempt the cuebid level is too high.
        if hcp >= 12 and opener_lvl <= 2:
            return bid(opener_lvl + 1, state.opening_bid.suit, alert=True,
                       why=f"Cuebid {opener_lvl+1}{state.opening_bid.suit.to_char()}: "
                           f"GF after partner's takeout X ({hcp} HCP)")
        # 4-card major → bid it at the cheapest legal level. Over a
        # 3-level preempt this is a 4-of-a-major bid (jump to game)
        # not 1-of-a-major.
        # CRITICAL: skip opener's suit. Deal #44: opener bid 1S, partner
        # X (takeout), responder 1NT (advance), and S had 4 spades + 7
        # HCP. The code iterated SPADES first and bid 2S — treating
        # OPENER'S SUIT as a "4-card major" to advance. That's a
        # CUEBID showing GF values, not a "natural" 4-card major
        # advance. Skip the opener's suit explicitly.
        for m in (Suit.SPADES, Suit.HEARTS):
            if m == state.opening_bid.suit:
                continue
            if e.suit_lengths[m] >= 4:
                lvl = _min_legal_level(m)
                # 9-11 HCP with 4+ in the major: jump one level
                # (invitational advance). 12+ went to cuebid above.
                if 9 <= hcp <= 11 and opener_lvl <= 2:
                    lvl = max(lvl, opener_lvl + 1)
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
        # Textbook advance to takeout X: bid your LONGEST non-opener
        # suit at the cheapest level (HCP gates apply). Prefer this
        # over 1NT — partner's X promised support for unbid suits, so
        # bidding a 5+ card suit usually finds a fit. The old code
        # dropped here into 1NT (deal #4: S had 9 HCP and 5 diamonds
        # + 3-3 majors; biq bid 1NT instead of 2D, missing 4H-N fit
        # for -11 IMP). Iterate by length, longest first.
        non_opener = [s for s in (Suit.DIAMONDS, Suit.CLUBS,
                                  Suit.HEARTS, Suit.SPADES)
                      if s != state.opening_bid.suit]
        long_first = sorted(non_opener,
                            key=lambda s: -e.suit_lengths.get(s, 0))
        for m in long_first:
            if e.suit_lengths.get(m, 0) >= 5:
                lvl = _min_legal_level(m)
                min_hcp_for_lvl = {1: 0, 2: 6, 3: 9, 4: 12}.get(lvl, 14)
                if hcp < min_hcp_for_lvl:
                    continue
                return bid(lvl, m,
                           why=f"Advance takeout double: longest "
                               f"{e.suit_lengths[m]}-card suit "
                               f"({m.to_char()})")
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
        # Unassuming cue-bid (UCB) — a FIRST-CALL convention: when
        # partner has just overcalled and it's our first turn, with
        # 3+ support and 10-12 HCP we cue opener's suit to show
        # limit-raise+ values. NOT a tool for later calls; partner
        # has heard about us by then. The previous unconditional
        # check produced auctions like deal #31's 5DX-N disaster:
        # we'd already doubled then cuebid 3D, partner signed off
        # in 4H, and the UCB code fired AGAIN to escalate to 5D.
        # Restrict to actual advance-first-call cases.
        is_my_first_call = not any(
            (not bb.is_pass) for bb in state.my_bids)
        if (system.has("C-unassuming-cue-bids")
                and is_my_first_call
                and fit >= 3
                and opener_suit is not None
                and opener_suit != suit
                and 10 <= hcp <= 12
                and p_last.level <= 2):
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
            # Limit raise only applies to 1- and 2-level overcalls. After
            # partner's 3-level overcall (eg, lead-direct 3♦ over a
            # Precision 2♦ three-suiter) a +2 jump lands past game —
            # offer 3NT with a balanced 10+ advancing hand instead.
            if 11 <= hcp <= 12 and p_last.level <= 2:
                return bid(p_last.level + 2, suit, why="Limit raise of overcall")
            if hcp >= 13 and suit in (Suit.HEARTS, Suit.SPADES):
                return bid(4, suit, why="Game raise of major overcall")
            if hcp >= 10 and e.is_balanced and p_last.level >= 3:
                return bid(3, Suit.NOTRUMP,
                           why=f"3NT advance after partner's "
                               f"{p_last.level}{suit.to_char()} overcall")

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
        # Legal iff the most recent non-pass call is an OPPONENT's contract
        # bid. Walk the full auction (not `rho_bids[-1]`, which drops passes
        # and so goes stale — e.g. RHO bid then passed, or LHO made the last
        # bid in a reopening seat; the old check also wrongly rejected NT
        # contracts via `suit is None`, suppressing penalty doubles of 3NT).
        last_call = None
        for s, b in reversed(state.bids):
            if not b.is_pass:
                last_call = (s, b)
                break
        if (last_call is None
                or last_call[1].is_double or last_call[1].is_redouble
                or last_call[0] in (state.seat, state.seat.partner())):
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
