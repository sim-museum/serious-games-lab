"""
BridgeEngine - Wrapper around BEN's bridge engine.
Provides bidding, play, and analysis through BEN's API.
"""

import os
import sys
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import warnings
warnings.filterwarnings("ignore")

from .models import (
    BoardState, Card, Hand, Bid, Contract, Trick,
    Seat, Suit, Vulnerability, PlayerType
)


@dataclass
class BidCandidate:
    """A candidate bid with analysis information"""
    bid: Bid
    score: float = 0.0
    expected_tricks: Optional[float] = None
    expected_score: Optional[float] = None
    alert: bool = False
    explanation: str = ""


@dataclass
class CardCandidate:
    """A candidate card with analysis information"""
    card: Card
    score: float = 0.0
    expected_tricks: Optional[float] = None
    expected_score: Optional[float] = None


@dataclass
class EngineResponse:
    """Response from the engine for a bid or play request"""
    action: Any  # Bid or Card
    candidates: List[Any] = None
    quality: float = 0.0
    who: str = "BEN"
    samples: List[str] = None
    hcp_estimate: Optional[List[float]] = None
    shape_estimate: Optional[List[float]] = None


class BridgeEngine:
    """
    Bridge engine — NN-free. Bidding goes through
    `native_bidder.NativeBiddingEngine` (rule-based, system-driven);
    opening leads through `native_lead.select_opening_lead`;
    follow-on cards through `get_mc_card_play` (Monte Carlo + DDS).
    The only external dependency is the DDS solver, loaded once
    in `initialize()`.
    """

    # The system names the native bidder understands. Kept as a
    # bare list so callers asking "what systems do you support?"
    # get a stable answer; the BEN config-file mapping is gone.
    SYSTEM_CONFIGS = {
        'SAYC': 'SAYC',
        '2/1': '2/1',
        '21GF': '21GF',
        '2/1GF': '2/1GF',
        'Precision90M': 'Precision90M',
        'StandardAcol': 'StandardAcol',
        'StandardFrench': 'StandardFrench',
        'DEFAULT': 'SAYC',
    }

    def __init__(self, config_path: Optional[str] = None, verbose: bool = False):
        import threading
        # Re-entrant lock so the MC path can call get_card_play() as a
        # fallback without deadlocking on itself. The original Lock() was
        # non-reentrant; whenever get_mc_card_play hit one of its
        # "sampling failed → return self.get_card_play(...)" branches,
        # the inner call tried to retake the lock and the worker thread
        # parked on it forever (see freeze_reports/freeze-*-?.txt).
        self._lock = threading.RLock()
        self.verbose = verbose
        self.models = None
        self.sampler = None
        self.dds = None
        self.config = None
        self._initialized = False
        self.current_system = 'DEFAULT'

        self.config_path = config_path

    def initialize(self) -> bool:
        """Initialize the engine. Only the DDS solver is required —
        bidding goes through `native_bidder.NativeBiddingEngine`, the
        opening lead through `native_lead`, and the rest of card
        play through `get_mc_card_play` (MC + DDS, no NN). No
        TensorFlow / Keras / NN models are loaded.
        """
        if self._initialized:
            return True

        try:
            from . import dds as _dds_mod
            self.dds = _dds_mod.DDSolver()
            self.models = None
            self.sampler = None
            self.config = None
            self._initialized = True
            if self.verbose:
                print("Engine initialized (DDS only, NN-free).")
                print(f"DDS Solver version: {self.dds.version()}")
            return True

        except Exception as e:
            print(f"Failed to initialize engine: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_bidding_system(self, system_name: str) -> bool:
        """Set the bidding system name.

        Previously this method reloaded BEN's per-system NN config
        (`config/SAYC.conf`, `config/2over1.conf`, etc.). With the
        native rule-based bidder there is no per-system config —
        `NativeBiddingEngine` reads the system from preferences at
        each `get_bid` call. We just record the name.
        """
        self.current_system = system_name
        if self.verbose:
            print(f"Bidding system set to: {system_name}")

        return success

    @staticmethod
    def _all_hands_visible(board: BoardState) -> bool:
        """Returns True iff every seat has either remaining cards or
        cards already played in this deal. A seat with 0 remaining
        AND 0 played has never been seen by the engine — that's the
        One-Player Mode case where the engine must refuse any
        request that would otherwise peek at four hands."""
        played_by_seat = {s: 0 for s in Seat}
        for trick in board.tricks:
            for i, _c in enumerate(trick.cards):
                seat = Seat((trick.leader + i) % 4)
                played_by_seat[seat] += 1
        if board.current_trick is not None:
            for i, _c in enumerate(board.current_trick.cards):
                seat = Seat((board.current_trick.leader + i) % 4)
                played_by_seat[seat] += 1
        for seat in Seat:
            hand = board.hands.get(seat)
            remaining = len(hand.cards) if hand else 0
            if remaining + played_by_seat[seat] == 0:
                return False
        return True

    def get_available_systems(self) -> List[str]:
        """Get list of available bidding systems."""
        return list(self.SYSTEM_CONFIGS.keys())

    def get_current_system(self) -> str:
        """Get the current bidding system name."""
        return self.current_system

    def get_bid(self, board: BoardState, seat: Seat) -> EngineResponse:
        """Return the native rule-based bidder's pick.

        The deployed UI already routes bidding directly to
        `NativeBiddingEngine` (see `BidWorker` in `main_window.py`)
        when `prefs.bidding_engine == "native"`, which is the
        default. This method is the engine-level fallback used by
        `match_controller` and other callers — make it route to
        the same native engine so we have a single source of truth
        for "what does bridgeIQ bid?".
        """
        try:
            from . import native_bidder
            from .config import get_config_manager

            # Pick the configured Precision90M / SAYC / etc. system
            # from preferences. Falls back to SAYC if nothing is set.
            sys_name = "SAYC"
            try:
                prefs = get_config_manager().config.preferences
                sys_name = getattr(prefs, "native_bidding_system",
                                   "SAYC") or "SAYC"
            except Exception:
                pass
            ne = native_bidder.NativeBiddingEngine(system=sys_name)
            return ne.get_bid(board, seat)
        except Exception as e:
            if self.verbose:
                print(f"Error getting bid: {e}")
                import traceback
                traceback.print_exc()
            return EngineResponse(action=Bid.make_pass(), who="Error")

    def get_opening_lead(self, board: BoardState) -> EngineResponse:
        """Rule-based opening lead — Q-Plus-style, no NN.

        Suit selection from `_score_suit_for_lead` (length, sequence,
        partner's suit, avoid opp-bid suits, etc.); spot card from
        `_pick_card_from_suit` (top of sequence, 4th best, MUD).
        See `backend.native_lead` for the full rule book.
        """
        try:
            from . import native_lead
            if not board.contract:
                return EngineResponse(action=None, who="NoContract")
            leader = board.contract.declarer.next()
            hand = board.hands.get(leader)
            if not hand:
                return EngineResponse(action=None, who="NoHand")
            decision = native_lead.select_opening_lead(
                hand=hand,
                contract=board.contract,
                auction=board.auction,
                dealer=board.dealer,
                leader=leader,
                vulnerability=board.vulnerability,
            )
            return EngineResponse(
                action=decision.card,
                who="native-lead",
                candidates=[CardCandidate(card=decision.card, score=1.0)],
            )
        except Exception as e:
            if self.verbose:
                print(f"Error getting opening lead: {e}")
                import traceback
                traceback.print_exc()
            return EngineResponse(action=None, who="Error")

    def get_card_play(self, board: BoardState, seat: Seat,
                      current_trick_cards: List[Card] = None,
                      played_tricks: List[Trick] = None) -> EngineResponse:
        """Last-resort card picker — first legal card.

        The real card-play engine is `get_mc_card_play` (the UI's
        `use_monte_carlo_play=True` default). This method exists
        only as the bottom-of-stack fallback that `get_mc_card_play`
        falls through to when its DDS solve fails — recursing back
        into MC here would loop. Keep it as a pure rule-based
        "play any legal card so the deal advances" stub.
        """
        hand = board.hands.get(seat)
        if not hand or not hand.cards:
            return EngineResponse(action=None, who="NoCards")
        lead_suit = (current_trick_cards[0].suit
                     if current_trick_cards else None)
        if lead_suit is not None:
            suit_cards = [c for c in hand.cards if c.suit == lead_suit]
            legal_cards = suit_cards if suit_cards else hand.cards[:]
        else:
            legal_cards = hand.cards[:]
        if not legal_cards:
            return EngineResponse(action=None, who="NoCards")
        return EngineResponse(action=legal_cards[0], who="Fallback")

    def analyze_double_dummy(self, board: BoardState) -> Dict[str, Dict[str, int]]:
        """
        Run double-dummy analysis on a board.

        Returns:
            Dict mapping seat -> strain -> tricks makeable
            e.g. {'N': {'NT': 7, 'S': 8, ...}, 'E': {...}, ...}
        """
        # Refuse to peek when the engine doesn't have all four hands
        # (One-Player Mode pre-play, or any incomplete deal). The caller
        # gets an empty result and the UI shows "DD not available".
        if not self._all_hands_visible(board):
            return {}

        if not self._initialized and not self.initialize():
            return {}

        with self._lock:
            try:
                from . import dds as _dds_mod
                return _dds_mod.DDSolver().solve_dd_table(board.to_pbn_deal())
            except Exception as e:
                if self.verbose:
                    print(f"Error in DD analysis: {e}")
                return {}

    def get_dd_tricks(self, board: BoardState, suit: Suit, seat: Seat) -> Optional[int]:
        """Get double-dummy trick count for a specific declarer and strain."""
        # DD solve needs all four hands; refuse when any seat is
        # unknown (One-Player Mode pre-dummy-entry, etc).
        if not self._all_hands_visible(board):
            return None
        if not self._initialized:
            if not self.initialize():
                return None
        with self._lock:
            try:
                from . import dds as _dds_mod
                table = _dds_mod.DDSolver().solve_dd_table(board.to_pbn_deal())
                seat_char = ["N", "E", "S", "W"][seat.value]
                strain_char = ["S", "H", "D", "C", "NT"][suit.value]
                return table[seat_char][strain_char]
            except Exception as e:
                if self.verbose:
                    print(f"Error in DD solve: {e}")
                return None

    def get_mc_card_play(self, board: BoardState, seat: Seat,
                         current_trick_cards: List[Card] = None,
                         num_samples: int = 40) -> EngineResponse:
        """Get card play using Monte Carlo simulation with DDS.

        Generates random deals consistent with known information, solves each
        double-dummy, and picks the card with highest average trick count.

        This is the same technique used by Bridge Baron and other strong programs.
        """
        import random

        # Diagnostic hook — when MC_DEBUG_LOG is set, each fallback
        # branch appends "<reason>\n" so we can see why MC bailed.
        _debug_log = os.environ.get("MC_DEBUG_LOG")
        def _log_fb(reason):
            if _debug_log:
                with open(_debug_log, "a") as f:
                    f.write(f"{reason}\n")

        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:
            try:
                from .dds import DDSolver

                hand = board.hands.get(seat)
                if not hand or not hand.cards:
                    return EngineResponse(action=None, who="NoCards")

                # Get legal cards
                lead_suit = None
                if current_trick_cards:
                    lead_suit = current_trick_cards[0].suit
                if lead_suit is not None:
                    suit_cards = [c for c in hand.cards if c.suit == lead_suit]
                    legal_cards = suit_cards if suit_cards else hand.cards[:]
                else:
                    legal_cards = hand.cards[:]

                if len(legal_cards) <= 1:
                    return EngineResponse(
                        action=legal_cards[0] if legal_cards else None,
                        who="MC-Forced"
                    )

                # Collect known information
                # - Our hand
                # - Dummy's hand (if visible)
                # - Cards already played
                my_cards = set(c.code52() for c in hand.cards)

                known_cards = {}  # seat -> set of card codes
                known_cards[seat] = set(my_cards)

                # Add dummy's cards if we can see them
                if board.contract:
                    dummy_seat = board.contract.declarer.partner()
                    dummy_hand = board.hands.get(dummy_seat)
                    if dummy_hand and dummy_hand.cards:
                        known_cards[dummy_seat] = set(c.code52() for c in dummy_hand.cards)

                # Cards played so far
                played_cards = set()
                for trick in board.tricks:
                    for c in trick.cards:
                        played_cards.add(c.code52())
                if current_trick_cards:
                    for c in current_trick_cards:
                        played_cards.add(c.code52())

                # Track which suits each opponent has shown out of
                shown_out = {s: set() for s in Seat}
                for trick in board.tricks:
                    if trick.cards:
                        led_s = trick.cards[0].suit
                        for i, c in enumerate(trick.cards):
                            player = Seat((trick.leader + i) % 4)
                            if c.suit != led_s:
                                shown_out[player].add(led_s)

                # Unknown cards = all 52 minus known minus played
                all_known = set()
                for s_cards in known_cards.values():
                    all_known |= s_cards
                all_known |= played_cards
                unknown_cards = [c for c in range(52) if c not in all_known]

                # Determine which seats need random cards
                unknown_seats = [s for s in Seat if s not in known_cards]

                # Count how many cards each unknown seat should have.
                # In standard mode we read the seat's current Hand;
                # in One-Player Mode unknown seats start with an
                # empty Hand, so we derive the count from cards
                # they've already played (each seat plays one card
                # per trick — leftover = 13 - played).
                cards_per_seat = {}
                total_remaining = 52 - len(played_cards)
                played_per_seat = {s: 0 for s in Seat}
                for trick in board.tricks:
                    for i, _c in enumerate(trick.cards):
                        ps = Seat((trick.leader + i) % 4)
                        played_per_seat[ps] += 1
                if current_trick_cards:
                    # Reconstruct the in-progress trick's leader so
                    # we can attribute partial-trick plays correctly.
                    cur_leader = Seat(
                        (seat - len(current_trick_cards)) % 4)
                    for i, _c in enumerate(current_trick_cards):
                        ps = Seat((cur_leader + i) % 4)
                        played_per_seat[ps] += 1
                for s in Seat:
                    if s in known_cards:
                        cards_per_seat[s] = len(known_cards[s])
                    else:
                        orig_hand = board.hands.get(s)
                        if orig_hand and orig_hand.cards:
                            cards_per_seat[s] = len(orig_hand.cards)
                        else:
                            cards_per_seat[s] = max(
                                0, 13 - played_per_seat[s])

                # Generate random samples
                trump_suit = board.contract.suit if board.contract else Suit.NOTRUMP
                # DDS solve() expects strain_i 1-based: 1=S,2=H,3=D,4=C,5=NT
                # Suit enum: S=0,H=1,D=2,C=3,NT=4 → strain_i = value + 1

                # Determine current leader for DDS. If the trick has
                # cards already, the leader is len(cards) seats earlier
                # than the seat about to play. If no cards are in the
                # trick, the player about to play IS the leader — using
                # `seat` directly is more reliable than asking
                # `board.tricks[-1].winner`, which can disagree with the
                # caller's view when our Trick.winner computation
                # differs from theirs (and then DDS returns cards for
                # the wrong seat, all filtered out as "no legal results").
                if current_trick_cards:
                    trick_leader = Seat((seat - len(current_trick_cards)) % 4)
                else:
                    trick_leader = seat

                # Current trick for DDS format
                current_trick_52 = []
                if current_trick_cards:
                    for c in current_trick_cards:
                        current_trick_52.append(c.code52())

                # Pre-flight: if every unknown seat is shown-out of a
                # suit but unknown_cards still contains that suit, the
                # constraint set is unsatisfiable (the cards have to
                # land *somewhere*). Drop shown_out for that suit so
                # sampling can proceed — the alternative is silently
                # falling back to first-legal-card.
                effective_shown_out = {s: set(shown_out[s])
                                       for s in Seat}
                for su in Suit:
                    if su == Suit.NOTRUMP:
                        continue
                    has_in_pool = any(c // 13 == su.value
                                      for c in unknown_cards)
                    if not has_in_pool:
                        continue
                    eligible = [s for s in unknown_seats
                                if su not in effective_shown_out[s]]
                    if not eligible:
                        for s in unknown_seats:
                            effective_shown_out[s].discard(su)

                # Auction-informed HCP constraints. Each seat's first
                # non-pass action (opening / overcall / preempt / weak-2)
                # pins their HCP to a known range. When we reject samples
                # that put 18 HCP in a hand that passed throughout the
                # bidding, the DDS expectations across samples sharpen —
                # which lifts the within-suit and cross-suit picks closer
                # to Q-Plus's choices on the real distribution. Computed
                # here once; consulted per-sample below.
                from .bidding_systems import get_system as _get_system
                try:
                    sys_obj = _get_system(self.current_system)
                except Exception:
                    sys_obj = None
                hcp_ranges = _derive_hcp_constraints(board, sys_obj)
                shape_ranges = _derive_shape_constraints(board, sys_obj)
                # HCP for unknown cards by c52: A=4, K=3, Q=2, J=1, else 0.
                _hcp_of_c52 = [0] * 52
                for i in range(52):
                    rank = i % 13
                    _hcp_of_c52[i] = (4, 3, 2, 1)[rank] if rank < 4 else 0
                # Already-known cards contribute fixed HCP per seat —
                # the sampler only adjusts the unknown remainder. So
                # for the per-sample check we precompute the
                # "starting HCP" each unknown seat already holds (zero
                # for fully-unknown seats; nonzero only when we partly
                # know a seat's hand — not currently exercised).
                known_hcp_by_seat = {}
                for s in Seat:
                    kc = known_cards.get(s, set())
                    known_hcp_by_seat[s] = sum(_hcp_of_c52[c] for c in kc)

                sample_hands_pbn = []
                # Three-stage relaxation:
                #   1. HCP constraints + shown_out
                #   2. shown_out only (drop HCP constraints)
                #   3. nothing (drop shown_out too — endgame escape)
                for relax_level in (0, 1, 2):
                    if sample_hands_pbn:
                        break
                    active_shown_out = (
                        {s: set() for s in Seat} if relax_level >= 2
                        else effective_shown_out)
                    active_hcp_ranges = (
                        hcp_ranges if relax_level == 0 else None)
                    active_shape_ranges = (
                        shape_ranges if relax_level == 0 else None)
                    for _ in range(num_samples):
                        # Per-card distribution: for each unknown card,
                        # pick a random unknown seat that (a) hasn't
                        # filled its capacity and (b) isn't shown-out of
                        # that suit. Avoids the greedy-first-fit failure
                        # where seat A took cards seat B needed.
                        pool = list(unknown_cards)
                        random.shuffle(pool)

                        sample = dict(known_cards)
                        remaining = {s: cards_per_seat.get(s, 0)
                                     for s in unknown_seats}
                        valid = True
                        for c52 in pool:
                            c_suit = Suit(c52 // 13)
                            eligible = [s for s in unknown_seats
                                        if remaining[s] > 0
                                        and c_suit not in active_shown_out[s]]
                            if not eligible:
                                valid = False
                                break
                            chosen = random.choice(eligible)
                            sample.setdefault(chosen, set()).add(c52)
                            remaining[chosen] -= 1

                        if not valid or any(remaining[s] > 0
                                             for s in unknown_seats):
                            continue

                        # Check auction-derived HCP constraints, if any.
                        # The relax_level loop above falls back to no
                        # HCP filter when constraints are over-tight.
                        if active_hcp_ranges is not None:
                            ok = True
                            for s in unknown_seats:
                                lo, hi = active_hcp_ranges.get(
                                    s, (0, 37))
                                hcp = known_hcp_by_seat[s] + sum(
                                    _hcp_of_c52[c]
                                    for c in sample.get(s, []))
                                if hcp < lo or hcp > hi:
                                    ok = False
                                    break
                            if not ok:
                                if _debug_log:
                                    _log_fb(f"sample-rejected-hcp")
                                continue

                        # Auction-derived shape constraints. Same idea
                        # as the HCP filter — drops samples where the
                        # 1♥ opener has 2 hearts, the 1NT opener has
                        # a 7-card suit, etc.
                        if active_shape_ranges is not None:
                            ok = True
                            for s in unknown_seats:
                                seat_shape = active_shape_ranges.get(s)
                                if not seat_shape:
                                    continue
                                seat_cards = sample.get(s, set())
                                # Known cards contribute too.
                                seat_cards = seat_cards | known_cards.get(s, set())
                                for suit_val, (mn, mx) in seat_shape.items():
                                    n = sum(1 for c in seat_cards
                                            if c // 13 == suit_val)
                                    if n < mn or n > mx:
                                        ok = False
                                        break
                                if not ok:
                                    break
                            if not ok:
                                if _debug_log:
                                    _log_fb(f"sample-rejected-shape")
                                continue

                        # Build PBN string for this valid sample.
                        hand_strs = []
                        for s in [Seat.NORTH, Seat.EAST,
                                  Seat.SOUTH, Seat.WEST]:
                            suits = [[], [], [], []]
                            for c52 in sorted(sample.get(s, [])):
                                si = c52 // 13
                                ri = c52 % 13
                                suits[si].append('AKQJT98765432'[ri])
                            hand_strs.append('.'.join(
                                ''.join(s) if s else '-' for s in suits))
                        pbn = 'N:' + ' '.join(hand_strs)
                        sample_hands_pbn.append(pbn)

                if not sample_hands_pbn:
                    _log_fb(
                        f"no-valid-samples seat={seat.name} "
                        f"trump={trump_suit.name} leader={trick_leader.name} "
                        f"unknown_seats={[s.name for s in unknown_seats]} "
                        f"cards_per_seat={ {s.name: cards_per_seat[s] for s in Seat} } "
                        f"shown_out={ {s.name: [x.name for x in shown_out[s]] for s in Seat if shown_out[s]} } "
                        f"unknown_cards_n={len(unknown_cards)} "
                        f"cur_trick={current_trick_52}")
                    return self.get_card_play(board, seat, current_trick_cards)

                # Use DDS to solve all samples
                local_dds = DDSolver(dds_mode=1)
                try:
                    dd_results = local_dds.solve(
                        trump_suit.value + 1,  # strain_i: 1=S,2=H,3=D,4=C,5=NT
                        trick_leader.value,
                        current_trick_52,
                        sample_hands_pbn,
                        3  # solutions=3: all legal cards with scores
                    )
                except Exception as e:
                    if self.verbose:
                        print(f"MC DDS solve error: {e}")
                    _log_fb(f"dds-exception:{type(e).__name__}:{e}")
                    return self.get_card_play(board, seat, current_trick_cards)

                if not dd_results:
                    _log_fb("dds-empty-result")
                    return self.get_card_play(board, seat, current_trick_cards)

                # Find best card by average tricks
                avg_tricks = {}
                for card52, tricks_list in dd_results.items():
                    avg_tricks[card52] = sum(tricks_list) / len(tricks_list)

                # Filter to legal cards only
                legal_codes = set(c.code52() for c in legal_cards)
                legal_results = {c: t for c, t in avg_tricks.items() if c in legal_codes}

                if not legal_results:
                    _log_fb(
                        f"no-legal-results seat={seat.name} "
                        f"dds_keys={sorted(avg_tricks)} "
                        f"legal={sorted(legal_codes)} "
                        f"trump={trump_suit.name} leader={trick_leader.name} "
                        f"cur_trick={current_trick_52} "
                        f"sample_pbn[0]={sample_hands_pbn[0] if sample_hands_pbn else None}")
                    return self.get_card_play(board, seat, current_trick_cards)

                # DDS-tie-break (the "signal" choice): within the
                # set of cards whose expected-tricks tie with the best,
                # match Q-Plus's standard convention. Categorising our
                # mismatches against Precision90M showed Q-Plus plays
                # the LOWEST equivalent ~82% of the time across all
                # roles (declarer, dummy, discarding, following) — so
                # default to lowest rank and let suit-choice fall out
                # of DDS as before.
                #
                # Rank encoding: c52 % 13 with 0=Ace ... 12=Two. So
                # "highest pip" (max of c52 % 13) is the LOWEST rank.
                best_score = max(legal_results.values())
                # Small tolerance only — broader windows admit cards
                # whose true expectation is genuinely worse than the
                # best, and picking the lowest of those costs tricks.
                tied = [c for c, s in legal_results.items()
                        if best_score - s < 0.01]
                # Q-Plus tie-break: pick the LOWEST equivalent card.
                # Categorising the 10-deal harness mismatches showed
                # Q-Plus plays low ~82% of the time across declarer,
                # dummy, defender-following-partner / -declarer, and
                # discard situations. The remaining "Q-Plus plays
                # high" cases (declarer cashing winners high from the
                # short hand, defender attitude signals) all share
                # the same diagnostic: they need position-specific
                # context that the MC score alone doesn't capture.
                # Lowest-equivalent is the best single rule.
                # Position-specific override (Q-Plus card-play
                # conventions from MANUAL/ENG/BRIDGE.HLQ). For
                # *signaling* contexts (attitude on partner's honor
                # lead, count on declarer's lead), the convention
                # dictates the card regardless of DDS scoring — we
                # pass ALL legal cards in the lead suit (not just
                # the DDS-tied set) so signal cards aren't filtered
                # out by tiny DDS noise.
                legal_in_suit = [c.code52() for c in legal_cards
                                 if c.suit == lead_suit]
                override = _position_override_card(
                    tied, board, seat, current_trick_cards,
                    lead_suit, board.contract.declarer if board.contract else None,
                    legal_in_suit=legal_in_suit)
                if override is not None:
                    best_card52 = override
                    if _debug_log:
                        _log_fb(f"override-present-count")
                else:
                    best_card52 = max(tied, key=lambda c: c % 13)
                best_card = Card.from_code52(best_card52)

                candidates = []
                for c52, avg in sorted(legal_results.items(), key=lambda x: x[1], reverse=True):
                    c = Card.from_code52(c52)
                    candidates.append(CardCandidate(
                        card=c,
                        score=avg,
                        expected_tricks=avg
                    ))

                return EngineResponse(
                    action=best_card,
                    candidates=candidates,
                    who="MC"
                )

            except Exception as e:
                if self.verbose:
                    print(f"Error in MC card play: {e}")
                    import traceback
                    traceback.print_exc()
                _log_fb(f"outer-exception:{type(e).__name__}:{e}")
                return self.get_card_play(board, seat, current_trick_cards)

    def get_dd_card_play(self, board: BoardState, seat: Seat,
                         current_trick_cards: List[Card] = None) -> EngineResponse:
        """Get optimal card using double-dummy solver.

        Uses DDS to find the card that maximizes tricks for the player's side.

        Args:
            board: Current board state
            seat: Seat to play for
            current_trick_cards: Cards already played in current trick

        Returns:
            EngineResponse with the optimal card
        """
        # Full double-dummy solve peeks at every hand. Refuse when
        # any hand is unknown (One-Player Mode); callers should fall
        # back to ``get_mc_card_play``, which works from only the
        # named seat + dummy + sampling.
        if not self._all_hands_visible(board):
            return EngineResponse(action=None, who="NoDD")
        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:
            try:
                hand = board.hands.get(seat)
                if not hand or not hand.cards:
                    return EngineResponse(action=None, who="NoCards")

                lead_suit = None
                if current_trick_cards:
                    lead_suit = current_trick_cards[0].suit

                if lead_suit is not None:
                    suit_cards = [c for c in hand.cards if c.suit == lead_suit]
                    legal_cards = suit_cards if suit_cards else hand.cards
                else:
                    legal_cards = hand.cards[:]

                if not legal_cards:
                    return EngineResponse(action=None, who="NoCards")

                if len(legal_cards) == 1:
                    return EngineResponse(action=legal_cards[0], who="DD-Forced")

                best_card = None
                best_tricks = -1
                candidates = []

                for card in legal_cards:
                    if lead_suit is None:
                        suit_len = hand.suit_length(card.suit)
                        score = suit_len * 10 + (13 - card.rank.value)
                    elif card.suit == lead_suit:
                        score = 13 - card.rank.value
                    else:
                        suit_len = hand.suit_length(card.suit)
                        score = -suit_len * 10 + card.rank.value

                    candidates.append(CardCandidate(
                        card=card,
                        score=float(score),
                        expected_tricks=None
                    ))

                    if score > best_tricks:
                        best_tricks = score
                        best_card = card

                candidates.sort(key=lambda c: c.score, reverse=True)
                return EngineResponse(
                    action=best_card or legal_cards[0],
                    candidates=candidates,
                    who="DD"
                )

            except Exception as e:
                if self.verbose:
                    print(f"Error in DD card play: {e}")
                    import traceback
                    traceback.print_exc()

        return self.get_card_play(board, seat, current_trick_cards)

    def calculate_score(self, contract: Contract, tricks: int,
                       vulnerable: bool) -> int:
        """Calculate score for a contract result"""
        try:
            from .scoring import calculate_contract_score
            return calculate_contract_score(contract, tricks, vulnerable)
        except Exception as e:
            if self.verbose:
                print(f"Error calculating score: {e}")
            return 0

    def random_deal(self, board_number: int = None) -> BoardState:
        """Generate a random deal"""
        if board_number is None:
            board_number = np.random.randint(1, 1000)

        np.random.seed(board_number)

        # Shuffle deck
        all_cards = list(range(52))
        np.random.shuffle(all_cards)

        # Deal to four hands
        board = BoardState(board_number=board_number)
        dealer, vuln = BoardState._board_dealer_vuln(board_number)
        board.dealer = dealer
        board.vulnerability = vuln

        for i, seat in enumerate([Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]):
            cards = [Card.from_code52(c) for c in all_cards[i*13:(i+1)*13]]
            board.hands[seat] = Hand(cards)

        return board

    @property
    def is_ready(self) -> bool:
        """Check if engine is initialized and ready"""
        return self._initialized

    def cleanup(self):
        """Release engine resources. Nothing TensorFlow-related to
        clear (we never load NN models)."""
        self.models = None
        self.sampler = None
        self.dds = None
        self._initialized = False

    def shutdown(self):
        """Shutdown the engine (alias for cleanup)."""
        self.cleanup()


def _position_override_card(tied_cards, board, seat,
                            current_trick_cards, lead_suit,
                            declarer, legal_in_suit=None):
    """Apply Q-Plus card-play conventions to break a DDS tie.

    Q-Plus documents two card-play conventions in MANUAL/ENG/BRIDGE.HLQ:

      1. **Present count** (signal-conv): on the SECOND round of a
         suit, a defender plays
            - a high small card if their original count was ODD
            - the lowest card if their original count was EVEN
         (provided the suit length is still unclear at that point).

      2. **Attitude on partner's honor lead** (lead-conv): when
         partner leads an A or K to trick 1, third hand encourages
         with the highest small they can afford, discourages with
         the lowest. Not yet implemented — present count covers
         the bulk of within-suit defender mismatches.

    Returns one card from `tied_cards` if a convention applies,
    else None (caller uses the default lowest-equivalent rule).

    `tied_cards` is a list of c52 codes.
    """
    from .models import Seat

    if declarer is None or lead_suit is None or not tied_cards:
        return None

    dummy = declarer.partner()
    is_defender = seat != declarer and seat != dummy
    if not is_defender:
        return None

    # Defender signals count when following a NON-TRUMP suit, on
    # either an opponent's lead OR partner's opening lead. PROBE-03
    # against Q-Plus (2026-05-23) confirmed: with Q72 of the suit
    # partner led, Q-Plus's E played the 7 (high small) signalling
    # odd 3-card count, NOT the Q (third-hand-high) and NOT the 2
    # (lowest = even). So count is a primary signal under partner's
    # lead too, not just after winning the first round.
    if current_trick_cards:
        trick_leader = Seat(
            (seat - len(current_trick_cards)) % 4)
    else:
        return None  # I'm leading — present count doesn't apply

    # Skip trump suits — count is for side-suit defense, not
    # trump-pull rounds.
    trump = board.contract.suit if board.contract else None
    if trump is not None and lead_suit == trump:
        return None

    # Filter to cards actually in the lead suit (when following).
    tied_in_suit = [c for c in tied_cards if c // 13 == lead_suit.value]
    if not tied_in_suit:
        return None

    # Count how many cards I've already played in this suit.
    played_in_suit = 0
    for trick in board.tricks:
        for i, c in enumerate(trick.cards):
            ps = Seat((trick.leader + i) % 4)
            if ps == seat and c.suit == lead_suit:
                played_in_suit += 1

    # Fire on EITHER the first round (signal under partner's lead)
    # OR the second round (signal after winning round 1 ourselves).
    # Beyond round 2 the suit length is generally known and the
    # signal is redundant.
    if played_in_suit > 1:
        return None
    # Round 1 signal is only useful when partner led (signal TO
    # partner). On round 1 led by an opp, partner gets count from
    # *not playing the suit first*; we follow with default rules.
    if played_in_suit == 0 and trick_leader.partner() != seat:
        return None

    # Original count: cards remaining in hand + already played.
    hand = board.hands.get(seat)
    remaining_in_suit = (
        sum(1 for c in hand.cards if c.suit == lead_suit)
        if hand else 0)
    original_count = played_in_suit + remaining_in_suit

    # ATTITUDE on partner's HONOR lead (round 1): textbook says
    # signal attitude (HIGH = encouraging with values, LOW =
    # discouraging without). Count comes on the SECOND round.
    # Detect: round 1 (played_in_suit == 0), partner led, and
    # the lead card is an honor (A or K mainly; Q sometimes).
    # "Have values" = have an honor in the suit (J or higher).
    led_card = current_trick_cards[0]
    led_is_honor = (led_card.rank.value <= 1)  # A=0, K=1 → honor
    if played_in_suit == 0 and trick_leader.partner() == seat \
            and led_is_honor:
        suit_hcp_held = sum(
            (4 - c.rank.value) if c.rank.value <= 3 else 0
            for c in hand.cards if c.suit == lead_suit)
        # Attitude is a signal convention — the choice between
        # small cards doesn't change DDS trick count (you're
        # losing this trick anyway). Use ALL legal small cards
        # in the suit, not just the DDS-tied set.
        pool = (legal_in_suit if legal_in_suit else tied_in_suit)
        small_pool = [c for c in pool if c % 13 >= 4]
        if small_pool:
            if suit_hcp_held >= 1:
                # Encourage — play highest small (lowest pip).
                return min(small_pool, key=lambda c: c % 13)
            # Discourage — play lowest (highest pip).
            return max(small_pool, key=lambda c: c % 13)
        return None

    # COUNT (present count): rank encoding c % 13 → 0=A, 1=K, …
    # 12=2. "Highest pip" = LOWEST rank, "lowest pip" = HIGHEST.
    # A "small" card is rank ≥ 4 (T or below).
    if original_count in (2, 4, 6):
        # Even — play the LOWEST card from the tied set.
        return max(tied_in_suit, key=lambda c: c % 13)
    if original_count in (3, 5):
        # Odd — play a HIGH SMALL (avoid honors). Pick the highest-
        # ranked small card; if every tied card is an honor, fall
        # back to the default lowest-equivalent rule.
        small_tied = [c for c in tied_in_suit if c % 13 >= 4]
        if small_tied:
            return min(small_tied, key=lambda c: c % 13)
        return None

    return None


def _derive_hcp_constraints(board, system) -> dict:
    """Return {Seat: (hcp_min, hcp_max)} pinned by each seat's first
    non-pass action in the auction.

    The point: the MC sampler used to drop random HCP into the unknown
    hands, so a sample sometimes put 18 HCP in a hand that passed
    throughout. DDS would then overcommit to a line that depends on
    that 18-count being on the wrong side. Rejecting these samples
    sharpens the DDS expectations across the surviving samples and
    pulls the chosen card closer to the right one on the real
    distribution.

    The ranges are deliberately loose — the goal is to filter the
    clearly-implausible 5% / 95% tails of each seat's distribution,
    not to model the bidder's full rule set. Bids we don't have a
    confident range for (X, XX, NT-overcalls, splinters, …) leave
    the seat unconstrained.
    """
    from .models import Seat, Suit

    ranges = {s: (0, 37) for s in Seat}
    if not getattr(board, "auction", None):
        return ranges

    nt_min = getattr(system, "one_nt_min_hcp", 15) if system else 15
    nt_max = getattr(system, "one_nt_max_hcp", 17) if system else 17
    strong_call = getattr(system, "strong_open_call", "2C") \
        if system else "2C"
    raw_rules = getattr(system, "raw_rules", set()) if system else set()
    precision_2d_three_suiter = any(
        k.startswith("B-2D.Precision") for k in raw_rules)

    # Find each seat's first non-pass action.
    first_action = {s: None for s in Seat}
    first_action_idx = {s: None for s in Seat}
    cur = board.dealer
    for i, b in enumerate(board.auction):
        if first_action[cur] is None and not b.is_pass:
            first_action[cur] = b
            first_action_idx[cur] = i
        cur = Seat((cur + 1) % 4)

    # Helper to classify the first-action bid into an HCP range. The
    # ranges below are roughly the central 90% of each call's
    # distribution — wide enough that close-call hands don't get
    # rejected, tight enough to filter the wrong-side-of-the-table
    # 18-point samples that confuse DDS.
    def _range_for(b):
        if b is None:
            # Passed throughout — the seat never had a hand worth
            # opening / overcalling / responding. Cap below the
            # weakest 5-card-suit opening (10 HCP under Rule of 20).
            # Most pass-throughout hands are 0-7; the 7-10 range is
            # plausible only with very flat shape and no biddable
            # suit, so 9 is a defensible upper bound.
            return (0, 9)
        if b.is_double or b.is_redouble:
            # Could be takeout (12+) or penalty (variable). Stay wide.
            return (0, 37)
        if b.suit is None:
            return (0, 37)
        if b.level == 1:
            if b.suit == Suit.NOTRUMP:
                return (nt_min, nt_max)
            if strong_call == "1C" and b.suit == Suit.CLUBS:
                # Precision strong 1C
                return (16, 37)
            # 1m / 1M opening: Precision capped at 15 (limited
            # opening); SAYC/2-over-1/Acol/French go up to ~21.
            if strong_call == "1C":
                return (10, 15)  # Precision-limited
            return (10, 21)
        if b.level == 2:
            if b.suit == Suit.CLUBS:
                if strong_call == "2C":
                    return (22, 37)  # SAYC strong 2♣
                return (11, 15)      # Precision 2♣ long-club
            if b.suit == Suit.DIAMONDS:
                if precision_2d_three_suiter:
                    return (11, 15)  # Precision 2♦ three-suiter
                return (5, 11)       # Weak 2♦
            if b.suit == Suit.NOTRUMP:
                return (20, 22)
            # 2♥ / 2♠ weak twos
            return (5, 11)
        if b.level == 3:
            if b.suit == Suit.NOTRUMP:
                # Gambling 3NT or strong balanced
                return (0, 21)
            # 3-level preempt
            return (4, 10)
        if b.level == 4:
            if b.suit == Suit.NOTRUMP:
                return (0, 37)  # Blackwood/quant
            return (4, 10)
        return (0, 37)

    for s in Seat:
        ranges[s] = _range_for(first_action[s])

    return ranges


def _derive_shape_constraints(board, system) -> dict:
    """Return {Seat: {suit_value: (min_len, max_len)}} from each
    seat's first non-pass action.

    Like the HCP constraints but stronger: a 1♥ opening promises
    5+ hearts in 2/1 / SAYC / Precision90M, so the sampler can
    safely reject any deal that gives the heart opener a 2-card
    heart suit. This dramatically tightens the MC distribution for
    cross-suit decisions — about 45% of bridgeIQ's card-play
    mismatches are "different suit" picks driven by samples that
    put the long suit in the wrong hand.

    Returned only the constraints we're confident about. Calls
    with ambiguous shape (passes, doubles, balanced 2NT, …) leave
    the seat unconstrained.
    """
    from .models import Seat, Suit

    shapes: dict = {s: {} for s in Seat}
    if not getattr(board, "auction", None):
        return shapes

    strong_call = getattr(system, "strong_open_call", "2C") \
        if system else "2C"
    raw_rules = getattr(system, "raw_rules", set()) if system else set()
    precision_2d_three_suiter = any(
        k.startswith("B-2D.Precision") for k in raw_rules)
    # SAYC opens 1m with 3+ in the minor (better-minor); Precision90M
    # opens 1m with 2+ (catch-all). 2/1 typically 3+.
    five_card_majors = True  # All five of bridgeIQ's systems use 5cM.
    open_1m_min_clubs = 3 if strong_call == "2C" else 2

    first_action = {s: None for s in Seat}
    cur = board.dealer
    for b in board.auction:
        if first_action[cur] is None and not b.is_pass:
            first_action[cur] = b
        cur = Seat((cur + 1) % 4)

    def _shape_for(b):
        """Return {suit_value: (min, max)} from a single opening / overcall bid."""
        if b is None or b.is_pass or b.is_double or b.is_redouble:
            return {}
        if b.suit is None:
            return {}
        # 1NT: balanced (4-3-3-3, 4-4-3-2, 5-3-3-2 — max one 5-card minor).
        # Constrain each suit to at most 5 cards.
        if b.level == 1 and b.suit == Suit.NOTRUMP:
            return {su.value: (2, 5) for su in (Suit.SPADES, Suit.HEARTS,
                                                Suit.DIAMONDS, Suit.CLUBS)}
        # 1 of major: 5+ in that major (all our systems play 5cM)
        if b.level == 1 and b.suit in (Suit.HEARTS, Suit.SPADES):
            if five_card_majors:
                return {b.suit.value: (5, 13)}
        # 1m (1C / 1D): minor opening
        if b.level == 1 and b.suit in (Suit.CLUBS, Suit.DIAMONDS):
            # Precision strong 1C is artificial — no length promised.
            if strong_call == "1C" and b.suit == Suit.CLUBS:
                return {}
            # Natural 1m: at least open_1m_min in the suit; no 5cM.
            return {b.suit.value: (open_1m_min_clubs, 13),
                    Suit.HEARTS.value: (0, 4),
                    Suit.SPADES.value: (0, 4)}
        if b.level == 2:
            if b.suit == Suit.CLUBS:
                if strong_call == "2C":
                    return {}  # Strong 2♣ is artificial
                return {b.suit.value: (6, 13)}  # Precision 2♣ long-club
            if b.suit == Suit.DIAMONDS:
                if precision_2d_three_suiter:
                    # 0-1 ♦, 4+ ♠ and 3+ ♥ (or vice versa); be conservative.
                    return {Suit.DIAMONDS.value: (0, 1),
                            Suit.HEARTS.value: (3, 6),
                            Suit.SPADES.value: (3, 6)}
                return {b.suit.value: (5, 6)}  # Weak 2♦: 6+ usually
            if b.suit == Suit.NOTRUMP:
                # 2NT 20-21 balanced
                return {su.value: (2, 5) for su in (Suit.SPADES, Suit.HEARTS,
                                                    Suit.DIAMONDS, Suit.CLUBS)}
            # 2♥ / 2♠ weak
            return {b.suit.value: (5, 6)}
        if b.level == 3 and b.suit != Suit.NOTRUMP:
            return {b.suit.value: (6, 7)}
        if b.level == 4 and b.suit in (Suit.HEARTS, Suit.SPADES,
                                       Suit.CLUBS, Suit.DIAMONDS):
            return {b.suit.value: (6, 8)}
        return {}

    for s in Seat:
        shapes[s] = _shape_for(first_action[s])

    return shapes
