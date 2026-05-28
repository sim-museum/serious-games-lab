"""Auction-semantic primitives — Option 1 of the slam-architecture roadmap.

Problem: biq's bidder re-derives "what's going on in this auction" at
every decision site by re-walking state.bids with ad-hoc heuristics
(_agreed_trump, _is_rkc_context, _trump_set_level, splinter detection,
GF detection scattered through each system path…). This causes:
  * The same primitive disagrees across sites (e.g. _agreed_trump's
    fallback returns the last suit bid; _trump_set_level rejects single
    mentions — Deal 39 phantom slam came from this disagreement).
  * Adding any new convention requires touching N call sites.
  * Each convention's edge cases hide in a different function.

Solution: walk state.bids ONCE per decide_bid call, materialise the
auction's high-level meaning as a typed AuctionContext, and let every
downstream site read from the context rather than re-derive.

Phase A (this file): trump_set + slam_zone_entered + gf_established +
controls_shown. Forcing-context derivation is sketched but not yet
populated. Convention-state and captain are placeholders for Phase B.

Migration policy: existing functions like _agreed_trump and
_is_rkc_context remain as wrappers calling the context. Sites can
migrate at their own pace; the context is computed once per decide_bid
and threaded through.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .models import Bid, Seat, Suit

if TYPE_CHECKING:
    from .native_bidder import AuctionState  # noqa: F401


class TrumpMechanism(Enum):
    """How was the trump suit established?

    Different mechanisms have different conventional follow-up. A
    direct raise leaves the auction natural; a Jacoby 2NT response
    expects opener to bid a structured shortness/range message; a
    splinter expects partner to evaluate trump quality.
    """
    DIRECT_RAISE = "direct_raise"       # 1H-2H, 1H-3H, 1S-2S
    JUMP_RAISE = "jump_raise"           # 1H-3H (limit), 1S-4S (preempt/strong)
    SPLINTER = "splinter"               # 1H-4C/4D/3S, 1S-4C/4D/4H
    JACOBY_2NT = "jacoby_2nt"           # 1M-2NT (artificial M agreement)
    TRANSFER_ACCEPT = "transfer_accept" # 1NT-2H-2S (1NT-2D-2H also)
    REBID_AGREEMENT = "rebid_agreement" # 1C-1H-2H (opener raises responder)


class ForcingContext(Enum):
    """What kind of action is legal here?

    INVITATIONAL allows pass; FORCING_ONE_ROUND requires a bid this
    round only; GAME_FORCE requires the partnership to reach game;
    SLAM_FORCE means slam-going (someone has committed via cuebid /
    4NT). COMPETITIVE means opponents have intervened.
    """
    NONE = "none"
    INVITATIONAL = "invitational"
    FORCING_ONE_ROUND = "forcing_one_round"
    GAME_FORCE = "game_force"
    SLAM_FORCE = "slam_force"
    COMPETITIVE = "competitive"


@dataclass
class TrumpAgreement:
    """A concrete trump-agreement event in the auction."""
    suit: Suit
    level: int            # the level at which trump was set
    mechanism: TrumpMechanism
    setter: Seat          # which seat made the trump-setting call
    bid_index: int        # position of the setting bid in state.bids


@dataclass
class AuctionContext:
    """Derived auction-semantic primitives, computed once per decide.

    All fields default to None / empty so partial population during
    incremental migration is safe. Sites that read a still-not-derived
    field should fall back to legacy ad-hoc detection.
    """
    # Trump
    trump: Optional[TrumpAgreement] = None

    # GF / slam zone
    gf_established: bool = False
    slam_zone_entered: bool = False        # a 4NT-as-RKC, cuebid, splinter,
                                            # Jacoby 2NT, or 5NT-GSF has been
                                            # bid by the partnership.

    # Controls each seat has shown via cuebid (Phase 3 + future)
    controls_shown: Dict[Seat, List[Suit]] = field(default_factory=dict)

    # Last 4NT bid (if any) and whether RKC/quantitative/other
    last_4nt_bidder: Optional[Seat] = None
    last_4nt_is_rkc: bool = False
    last_4nt_is_quantitative: bool = False

    # NT-rebid by opener — used to disambiguate 4NT and shut down
    # quantitative-mistaken-as-RKC paths.
    opener_rebid_nt: bool = False

    # Opener's first bid (cached for many lookups)
    opening_bid: Optional[Bid] = None
    opener_seat: Optional[Seat] = None
    opening_was_strong_artificial: bool = False

    # Forcing context for the next bid (per the seat about to bid)
    forcing: ForcingContext = ForcingContext.NONE

    # Convention-being-executed slot — populated in Phase B
    convention: Optional[str] = None
    convention_step: int = 0

    # Legacy fallback: the last NATURAL suit bid by the partnership
    # before the first 4NT (if any). Used by _agreed_trump when no
    # true trump-set was found, to preserve the historical "last
    # suit = implicit trump" behaviour for single-mention auctions
    # like 1H-3S-4NT (responder jump-shift then opener Blackwood).
    fallback_last_suit: Optional[Suit] = None


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------

_NT = Suit.NOTRUMP
_MAJORS = (Suit.HEARTS, Suit.SPADES)
_SUITS_LO_TO_HI = (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)


def derive_context(state: 'AuctionState', system=None) -> AuctionContext:
    """Single-pass walk of state.bids → fully-populated AuctionContext.

    The order of operations matters: we detect trump-set as early as
    possible (so subsequent suit bids can be classified as cuebids,
    not new trumps), then carry the trump forward when classifying
    4NT, 5NT, and slam-zone entries.
    """
    ctx = AuctionContext()

    # --- Opening identification -----------------------------------
    for s, b in state.bids:
        if b.is_pass:
            continue
        ctx.opener_seat = s
        ctx.opening_bid = b
        ctx.opening_was_strong_artificial = (
            b.level == 1 and b.suit == Suit.CLUBS and b.alert
        )
        break

    if ctx.opener_seat is None:
        return ctx  # passout — nothing to derive

    partner_of_opener = ctx.opener_seat.partner()
    opener_side = {ctx.opener_seat, partner_of_opener}
    # "My side" — the partnership of the seat about to bid. The legacy
    # `_trump_set_level` and `_agreed_trump` worked off MY-side bids
    # so that competitive auctions where I am the overcaller still
    # find my own trump-set. Use the same convention here.
    my_side = {state.seat, state.seat.partner()}
    ns = {Seat.NORTH, Seat.SOUTH}

    # --- Walk bids, tracking primitives ---------------------------
    # Per-side bookkeeping for trump detection: who's bid each suit.
    seats_bid_suit: Dict[Suit, Set[Seat]] = {}
    # Per-side bookkeeping for cuebid detection (controls shown).
    cuebids_after_trump: Dict[Seat, List[Suit]] = {}

    # Track opener's bids (after first) for the opener_rebid_nt flag.
    opener_post_first_bids: List[Bid] = []
    opener_first_seen = False

    # Cut-off: the FIRST 4NT in the auction ends trump-set / fallback
    # consideration. Bids at or after 4NT are RKC machinery, not
    # natural — without the cut-off, the responder's `5♣ = 0/3 keys`
    # answer would mis-promote to trump candidate.
    first_4nt_idx = None
    for idx, (s, b) in enumerate(state.bids):
        if b.level == 4 and b.suit == _NT and not b.is_pass:
            first_4nt_idx = idx
            break

    for idx, (s, b) in enumerate(state.bids):
        # 4NT tracking and opener-NT-rebid tracking run REGARDLESS of
        # the 4NT cut-off (legacy behavior treats opener's own 4NT as
        # an NT-rebid for quantitative-gate purposes).
        if (s == ctx.opener_seat
                and not b.is_pass
                and not b.is_double
                and not b.is_redouble):
            if not opener_first_seen:
                opener_first_seen = True
            else:
                opener_post_first_bids.append(b)
        if first_4nt_idx is not None and idx >= first_4nt_idx:
            # Past the 4NT cut-off — only 4NT classification; skip
            # trump / cuebid / fallback detection beyond this point.
            if b.level == 4 and b.suit == _NT and not b.is_pass:
                ctx.last_4nt_bidder = s
                if ctx.trump is not None:
                    ctx.last_4nt_is_rkc = True
                else:
                    ctx.last_4nt_is_quantitative = True
                ctx.slam_zone_entered = True
            continue
        if b.is_pass or b.is_double or b.is_redouble:
            continue

        # Skip artificial / NT for trump detection
        if b.suit is None or b.suit == _NT:
            continue
        if s not in my_side:
            continue  # opponents (from MY-side POV) — skip

        # Fallback-last-suit tracking (used by _agreed_trump legacy path)
        ctx.fallback_last_suit = b.suit

        # --- Trump-set detection (only fires once) ---------------
        if ctx.trump is None:
            # Pattern 1: partner is raising my major suit at any level
            if b.suit in _MAJORS:
                prior_seats = seats_bid_suit.get(b.suit, set())
                if prior_seats and s not in prior_seats:
                    # Determine mechanism by level relative to prior bid.
                    prior_levels = []
                    for ps, pb in state.bids[:idx]:
                        if (ps in my_side
                                and pb.suit == b.suit
                                and not pb.is_pass):
                            prior_levels.append(pb.level)
                    min_prior = min(prior_levels) if prior_levels else 1
                    if b.level - min_prior >= 2:
                        mech = TrumpMechanism.JUMP_RAISE
                    else:
                        mech = TrumpMechanism.DIRECT_RAISE
                    # Special case: if opener's MAJOR rebid raises
                    # responder's response, that's REBID_AGREEMENT.
                    if (s == ctx.opener_seat
                            and len(opener_post_first_bids) == 1
                            and opener_post_first_bids[0] is b):
                        mech = TrumpMechanism.REBID_AGREEMENT
                    ctx.trump = TrumpAgreement(
                        suit=b.suit, level=b.level, mechanism=mech,
                        setter=s, bid_index=idx,
                    )
                    ctx.gf_established = True  # M-fit at 2+ level is GF zone
                    if mech in (TrumpMechanism.JUMP_RAISE,):
                        ctx.slam_zone_entered = b.level >= 4

        # Track this seat's bid in suit (always — used for cuebid
        # classification and trump-mechanism lookup).
        seats_bid_suit.setdefault(b.suit, set()).add(s)

        # --- Cuebid tracking (after trump is set) ---------------
        if ctx.trump is not None and b.suit not in (ctx.trump.suit, _NT):
            # Any side-suit bid after trump-set by the partnership is
            # a cuebid showing first-round control.
            if (b.level >= 4 or
                    (b.level >= 3 and b.suit != ctx.trump.suit)):
                cuebids_after_trump.setdefault(s, []).append(b.suit)
                ctx.slam_zone_entered = True

    # --- Trump-set via Jacoby 2NT (MY partnership opened a major and
    # MY-side responder bid 2NT alerted as artificial).
    if (ctx.trump is None and ctx.opening_bid is not None
            and ctx.opener_seat in my_side):
        opener_major = (ctx.opening_bid.suit
                        if ctx.opening_bid.level == 1
                        and ctx.opening_bid.suit in _MAJORS else None)
        if opener_major is not None:
            for idx, (s, b) in enumerate(state.bids):
                if (s == partner_of_opener and b.suit == _NT
                        and b.level == 2 and b.alert):
                    ctx.trump = TrumpAgreement(
                        suit=opener_major, level=2,
                        mechanism=TrumpMechanism.JACOBY_2NT,
                        setter=s, bid_index=idx,
                    )
                    ctx.gf_established = True
                    ctx.slam_zone_entered = True
                    break

    # --- Trump-set via splinter (alerted jump in new suit by partner
    # of major opener). Conceptually correct — splinter agrees opener's
    # major — but TEMPORARILY DISABLED: with splinter as trump-set,
    # _is_rkc_context routes opener's 4NT through RKC, but opener's
    # _generic_responder_rebid splinter-response code at native_bidder.py
    # line ~4720 has a different hand-eval gate (controls ≥ 4 + losers
    # ≤ 5) that signs off in 4M when not met. Deal 65 in slam corpus
    # 59517: opener with 17 HCP / 2 controls correctly recognises
    # splinter but signs off 4M; the resulting 4M down was a worse
    # contract than the legacy 4NT accidental landing. Re-enable once
    # opener's splinter slam-eval is reworked (playing-tricks model
    # rather than strict controls gate).
    if False and ctx.trump is None and ctx.opening_bid is not None:
        opener_major = (ctx.opening_bid.suit
                        if ctx.opening_bid.level == 1
                        and ctx.opening_bid.suit in _MAJORS else None)
        if opener_major is not None:
            for idx, (s, b) in enumerate(state.bids):
                if (s == partner_of_opener
                        and b.alert
                        and b.level >= 3
                        and b.suit is not None
                        and b.suit not in (_NT, opener_major)):
                    ctx.trump = TrumpAgreement(
                        suit=opener_major, level=b.level,
                        mechanism=TrumpMechanism.SPLINTER,
                        setter=s, bid_index=idx,
                    )
                    ctx.gf_established = True
                    break

    # --- Opener NT-rebid flag (used by quantitative-4NT detection) ---
    ctx.opener_rebid_nt = any(
        b.suit == _NT for b in opener_post_first_bids)

    # --- Controls shown ----------------------------------------------
    if cuebids_after_trump:
        ctx.controls_shown = dict(cuebids_after_trump)

    return ctx


def trump_set_via(state: 'AuctionState') -> Optional[TrumpAgreement]:
    """Convenience wrapper — returns the trump agreement object or None.

    Replacement for the legacy `_trump_set_level` that returned
    (level, suit). Callers that only need the suit can do
    `t.suit if t else None`. Callers that need the level use `t.level`.
    """
    return derive_context(state).trump
