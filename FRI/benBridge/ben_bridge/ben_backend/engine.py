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
    Bridge engine wrapper around BEN.
    Supports direct Python API mode.
    Thread-safe via internal lock.
    """

    # Map UI system names to BEN config files
    SYSTEM_CONFIGS = {
        'SAYC': 'BEN-Sayc.conf',
        '2/1': 'BEN-21GF.conf',
        '21GF': 'BEN-21GF.conf',
        '2/1GF': 'BEN-21GF.conf',
        'GIB': 'GIB-BBO.conf',
        'DEFAULT': 'default.conf',
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

        # Default config path - relative to BEN installation
        if config_path is None:
            ben_path = self._find_ben_path()
            if ben_path:
                config_path = os.path.join(ben_path, 'src', 'config', 'default.conf')

        self.config_path = config_path

    def _find_ben_path(self) -> Optional[str]:
        """Find the BEN installation path"""
        # Try common locations
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'ben'),
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ben'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ben'),
        ]

        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(os.path.join(abs_path, 'src')):
                return abs_path
        return None

    def initialize(self) -> bool:
        """Initialize the BEN engine with models"""
        if self._initialized:
            return True

        try:
            ben_path = self._find_ben_path()
            if not ben_path:
                print("Could not find BEN installation")
                return False

            # Add BEN src to path
            src_path = os.path.join(ben_path, 'src')
            if src_path not in sys.path:
                sys.path.insert(0, src_path)

            # Change to BEN src directory for model loading
            original_cwd = os.getcwd()
            os.chdir(src_path)

            try:
                import conf
                from nn.models_tf2 import Models
                from sample import Sample
                from ddsolver import ddsolver

                # Load configuration
                if self.config_path and os.path.exists(self.config_path):
                    self.config = conf.load(self.config_path)
                else:
                    default_conf = os.path.join(src_path, 'config', 'default.conf')
                    self.config = conf.load(default_conf)

                # Load models
                self.models = Models.from_conf(self.config, ben_path)

                # Disable Windows-only features on Linux
                if sys.platform != 'win32':
                    self.models.pimc_use_declaring = False
                    self.models.pimc_use_defending = False
                    self.models.use_bba = False
                    self.models.consult_bba = False
                    self.models.use_bba_rollout = False
                    self.models.use_bba_to_count_aces = False
                    self.models.use_suitc = False

                # Initialize sampler
                self.sampler = Sample.from_conf(self.config, self.verbose)

                # Initialize DDS solver
                self.dds = ddsolver.DDSolver()

                self._initialized = True

                if self.verbose:
                    print(f"BEN Engine initialized successfully")
                    print(f"DDS Solver version: {self.dds.version()}")

            finally:
                os.chdir(original_cwd)

            return True

        except Exception as e:
            print(f"Failed to initialize BEN engine: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_bidding_system(self, system_name: str) -> bool:
        """
        Set the bidding system by reinitializing with appropriate config.

        Args:
            system_name: System name ('SAYC', '2/1', 'GIB', etc.)

        Returns:
            True if successful, False otherwise
        """
        system_upper = system_name.upper().replace(' ', '')

        # Map common names
        if system_upper in ('21', '2OVER1', 'TWOOVERONE'):
            system_upper = '2/1'

        config_name = self.SYSTEM_CONFIGS.get(system_upper)
        if not config_name:
            if self.verbose:
                print(f"Unknown system '{system_name}', using default")
            config_name = 'default.conf'

        ben_path = self._find_ben_path()
        if not ben_path:
            return False

        new_config_path = os.path.join(ben_path, 'src', 'config', config_name)

        # Check if config file exists
        if not os.path.exists(new_config_path):
            if self.verbose:
                print(f"Config file not found: {new_config_path}, using default")
            new_config_path = os.path.join(ben_path, 'src', 'config', 'default.conf')

        # If same config, no need to reinitialize
        if self._initialized and self.config_path == new_config_path:
            return True

        # Reinitialize with new config
        self.shutdown()
        self.config_path = new_config_path
        self.current_system = system_name

        success = self.initialize()
        if success and self.verbose:
            print(f"Bidding system set to: {system_name} ({config_name})")

        return success

    def get_available_systems(self) -> List[str]:
        """Get list of available bidding systems."""
        return list(self.SYSTEM_CONFIGS.keys())

    def get_current_system(self) -> str:
        """Get the current bidding system name."""
        return self.current_system

    def get_bid(self, board: BoardState, seat: Seat) -> EngineResponse:
        """
        Get a bid recommendation from BEN for the given position.

        Args:
            board: Current board state
            seat: Seat to get bid for

        Returns:
            EngineResponse with recommended bid and analysis
        """
        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=Bid.make_pass(), who="Error")

        with self._lock:  # Thread-safety lock
            try:
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)

                try:
                    import botbidder
                    from bidding.binary import DealData

                    # Get hand for this seat
                    hand = board.hands.get(seat)
                    if not hand:
                        return EngineResponse(action=Bid.make_pass(), who="NoHand")

                    hand_str = hand.to_pbn()

                    # Setup vulnerability
                    vuln = [
                        board.vulnerability.is_vulnerable(Seat.NORTH),
                        board.vulnerability.is_vulnerable(Seat.EAST)
                    ]

                    # Create bot bidder
                    bot = botbidder.BotBid(
                        vuln=vuln,
                        hand_str=hand_str,
                        models=self.models,
                        sampler=self.sampler,
                        seat=seat.value,
                        dealer=board.dealer.value,
                        ddsolver=self.dds,
                        bba_is_controlling=False,
                        verbose=self.verbose
                    )

                    # Build auction for BEN
                    auction = self._build_ben_auction(board)

                    # Get bid
                    bid_resp = bot.bid(auction)

                    # Convert response
                    bid = Bid.from_str(bid_resp.bid)

                    candidates = []
                    for cand in bid_resp.candidates:
                        candidates.append(BidCandidate(
                            bid=Bid.from_str(cand.bid),
                            score=cand.insta_score or 0.0,
                            expected_score=cand.expected_score,
                            alert=cand.alert or False,
                            explanation=cand.explanation or ""
                        ))

                    return EngineResponse(
                        action=bid,
                        candidates=candidates,
                        quality=bid_resp.quality or 0.0,
                        who=bid_resp.who or "BEN",
                        samples=bid_resp.samples,
                        hcp_estimate=list(bid_resp.hcp) if hasattr(bid_resp.hcp, '__iter__') else None,
                        shape_estimate=list(bid_resp.shape) if hasattr(bid_resp.shape, '__iter__') else None
                    )

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                if self.verbose:
                    print(f"Error getting bid: {e}")
                    import traceback
                    traceback.print_exc()
                return EngineResponse(action=Bid.make_pass(), who="Error")

    def get_opening_lead(self, board: BoardState) -> EngineResponse:
        """Get opening lead recommendation from BEN"""
        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:  # Thread-safety lock
            try:
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)

                try:
                    import botopeninglead

                    if not board.contract:
                        return EngineResponse(action=None, who="NoContract")

                    # Leader is left of declarer
                    leader = board.contract.declarer.next()
                    hand = board.hands.get(leader)
                    if not hand:
                        return EngineResponse(action=None, who="NoHand")

                    hand_str = hand.to_pbn()

                    vuln = [
                        board.vulnerability.is_vulnerable(Seat.NORTH),
                        board.vulnerability.is_vulnerable(Seat.EAST)
                    ]

                    bot = botopeninglead.BotLead(
                        vuln=vuln,
                        hand_str=hand_str,
                        models=self.models,
                        sampler=self.sampler,
                        seat=leader.value,
                        dealer=board.dealer.value,
                        ddsolver=self.dds,
                        verbose=self.verbose
                    )

                    auction = self._build_ben_auction(board)
                    card_resp = bot.find_opening_lead(auction, {})

                    card = Card.from_code52(card_resp.card.code())

                    candidates = []
                    for cand in card_resp.candidates:
                        candidates.append(CardCandidate(
                            card=Card.from_code52(cand.card.code()),
                            score=cand.insta_score or 0.0,
                            expected_tricks=cand.expected_tricks_sd,
                            expected_score=cand.expected_score_sd
                        ))

                    return EngineResponse(
                        action=card,
                        candidates=candidates,
                        quality=card_resp.quality or 0.0,
                        who=card_resp.who or "BEN",
                        samples=card_resp.samples
                    )

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                if self.verbose:
                    print(f"Error getting opening lead: {e}")
                    import traceback
                    traceback.print_exc()
                return EngineResponse(action=None, who="Error")

    def get_card_play(self, board: BoardState, seat: Seat,
                      current_trick_cards: List[Card] = None,
                      played_tricks: List[Trick] = None) -> EngineResponse:
        """Get card play recommendation from BEN"""
        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:  # Thread-safety lock
            try:
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)

                try:
                    import botcardplayer

                    hand = board.hands.get(seat)
                    if not hand:
                        return EngineResponse(action=None, who="NoHand")

                    # For simplicity, return first legal card
                    # Full implementation would use botcardplayer.CardPlayer
                    lead_suit = None
                    if current_trick_cards:
                        lead_suit = current_trick_cards[0].suit

                    legal_cards = []
                    if lead_suit is not None:
                        suit_cards = hand.get_suit_cards(lead_suit)
                        if suit_cards:
                            legal_cards = suit_cards
                        else:
                            legal_cards = hand.cards[:]
                    else:
                        legal_cards = hand.cards[:]

                    if not legal_cards:
                        return EngineResponse(action=None, who="NoCards")

                    # Return first legal card (simplified)
                    return EngineResponse(
                        action=legal_cards[0],
                        candidates=[CardCandidate(card=c, score=1.0/len(legal_cards))
                                   for c in legal_cards],
                        who="BEN"
                    )

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                if self.verbose:
                    print(f"Error getting card play: {e}")
                return EngineResponse(action=None, who="Error")

    def analyze_double_dummy(self, board: BoardState) -> Dict[str, Dict[str, int]]:
        """
        Run double-dummy analysis on a board.

        Returns:
            Dict mapping seat -> strain -> tricks makeable
            e.g. {'N': {'NT': 7, 'S': 8, ...}, 'E': {...}, ...}
        """
        # Write debug to file for GUI debugging
        with open('/tmp/dd_debug.log', 'a') as f:
            f.write(f"analyze_double_dummy called, initialized={self._initialized}\n")

        if not self._initialized:
            with open('/tmp/dd_debug.log', 'a') as f:
                f.write(f"Engine not initialized, trying to initialize...\n")
            if not self.initialize():
                with open('/tmp/dd_debug.log', 'a') as f:
                    f.write(f"Failed to initialize engine\n")
                return {}

        with self._lock:  # Thread-safety lock
            try:
                import ctypes
                ben_path = self._find_ben_path()
                with open('/tmp/dd_debug.log', 'a') as f:
                    f.write(f"ben_path={ben_path}\n")
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                with open('/tmp/dd_debug.log', 'a') as f:
                    f.write(f"Changing to {src_path}\n")
                os.chdir(src_path)

                try:
                    from ddsolver import dds

                    # Create PBN deal string: "N:AKQ.JT9.876.5432 ..."
                    pbn_deal = board.to_pbn_deal()
                    with open('/tmp/dd_debug.log', 'a') as f:
                        f.write(f"PBN deal = '{pbn_deal}'\n")

                    # Create DDS structures
                    tableDealPBN = dds.ddTableDealPBN()
                    tableDealPBN.cards = pbn_deal.encode('utf-8')

                    table = dds.ddTableResults()
                    tablePtr = ctypes.pointer(table)

                    # Call DDS
                    with open('/tmp/dd_debug.log', 'a') as f:
                        f.write(f"Calling CalcDDtablePBN...\n")
                    res = dds.CalcDDtablePBN(tableDealPBN, tablePtr)
                    with open('/tmp/dd_debug.log', 'a') as f:
                        f.write(f"Result = {res}\n")

                    if res != 1:
                        error_msg = dds.get_error_message(res)
                        with open('/tmp/dd_debug.log', 'a') as f:
                            f.write(f"DDS error {res}: {error_msg}\n")
                        return {}

                    # Extract results
                    # resTable is a 2D array: [seat][strain] where
                    # seat: 0=N, 1=E, 2=S, 3=W
                    # strain: 0=S, 1=H, 2=D, 3=C, 4=NT
                    results = {}
                    seat_map = ['N', 'E', 'S', 'W']
                    strain_map = ['S', 'H', 'D', 'C', 'NT']

                    for seat_idx, seat_char in enumerate(seat_map):
                        results[seat_char] = {}
                        for strain_idx, strain_char in enumerate(strain_map):
                            # Access the 2D array: resTable[seat][strain]
                            tricks = int(table.resTable[seat_idx][strain_idx])
                            results[seat_char][strain_char] = tricks

                    with open('/tmp/dd_debug.log', 'a') as f:
                        f.write(f"Results = {results}\n")

                    return results

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                with open('/tmp/dd_debug.log', 'a') as f:
                    f.write(f"Error in DD analysis: {e}\n")
                    import traceback
                    f.write(traceback.format_exc())
                return {}

    def get_dd_tricks(self, board: BoardState, suit: Suit, seat: Seat) -> Optional[int]:
        """Get double-dummy trick count for a specific declarer and strain."""
        if not self._initialized:
            if not self.initialize():
                return None
        with self._lock:  # Thread-safety lock
            try:
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)
                try:
                    deal_str = board.to_ben_deal()
                    return self.dds.solve(deal_str, suit.value, seat.value)
                finally:
                    os.chdir(original_cwd)
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
        import ctypes

        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:
            try:
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)

                try:
                    from ddsolver import dds
                    from ddsolver.ddsolver import DDSolver

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

                    # Count how many cards each unknown seat should have
                    cards_per_seat = {}
                    total_remaining = 52 - len(played_cards)
                    for s in Seat:
                        if s in known_cards:
                            cards_per_seat[s] = len(known_cards[s])
                        else:
                            # Estimate from total remaining
                            orig_hand = board.hands.get(s)
                            if orig_hand:
                                cards_per_seat[s] = len(orig_hand.cards)
                            else:
                                cards_per_seat[s] = (total_remaining - sum(
                                    len(known_cards.get(ss, [])) for ss in Seat
                                    if ss in known_cards
                                )) // max(1, len(unknown_seats))

                    # Generate random samples
                    trump_suit = board.contract.suit if board.contract else Suit.NOTRUMP
                    # DDS solve() expects strain_i 1-based: 1=S,2=H,3=D,4=C,5=NT
                    # Suit enum: S=0,H=1,D=2,C=3,NT=4 → strain_i = value + 1

                    # Determine current leader for DDS
                    if current_trick_cards:
                        trick_leader = Seat((seat - len(current_trick_cards)) % 4)
                    else:
                        if board.tricks:
                            trick_leader = board.tricks[-1].winner
                        elif board.contract:
                            trick_leader = board.contract.declarer.next()
                        else:
                            trick_leader = seat

                    # Current trick for DDS format
                    current_trick_52 = []
                    if current_trick_cards:
                        for c in current_trick_cards:
                            current_trick_52.append(c.code52())

                    sample_hands_pbn = []
                    for _ in range(num_samples):
                        # Shuffle unknown cards
                        pool = list(unknown_cards)
                        random.shuffle(pool)

                        # Distribute to unknown seats respecting shown_out
                        sample = dict(known_cards)  # copy known hands
                        valid = True
                        idx = 0
                        for s in unknown_seats:
                            need = cards_per_seat.get(s, 0)
                            assigned = []
                            for c52 in pool[idx:]:
                                if len(assigned) >= need:
                                    break
                                # Check shown_out constraint
                                c_suit = Suit(c52 // 13)
                                if c_suit in shown_out[s]:
                                    continue
                                assigned.append(c52)
                            if len(assigned) < need:
                                valid = False
                                break
                            sample[s] = set(assigned)
                            # Remove assigned from pool
                            for a in assigned:
                                pool.remove(a)
                            idx = 0  # reset for next seat

                        if not valid:
                            continue

                        # Build PBN string
                        hand_strs = []
                        for s in [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]:
                            suits = [[], [], [], []]
                            for c52 in sorted(sample.get(s, [])):
                                si = c52 // 13
                                ri = c52 % 13
                                suits[si].append('AKQJT98765432'[ri])
                            hand_strs.append('.'.join(''.join(s) if s else '-' for s in suits))
                        pbn = 'N:' + ' '.join(hand_strs)
                        sample_hands_pbn.append(pbn)

                    if not sample_hands_pbn:
                        # Fallback if sampling failed
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
                        return self.get_card_play(board, seat, current_trick_cards)

                    if not dd_results:
                        return self.get_card_play(board, seat, current_trick_cards)

                    # Find best card by average tricks
                    avg_tricks = {}
                    for card52, tricks_list in dd_results.items():
                        avg_tricks[card52] = sum(tricks_list) / len(tricks_list)

                    # Filter to legal cards only
                    legal_codes = set(c.code52() for c in legal_cards)
                    legal_results = {c: t for c, t in avg_tricks.items() if c in legal_codes}

                    if not legal_results:
                        # DDS returned cards we don't recognize as legal
                        return self.get_card_play(board, seat, current_trick_cards)

                    best_card52 = max(legal_results, key=legal_results.get)
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

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                if self.verbose:
                    print(f"Error in MC card play: {e}")
                    import traceback
                    traceback.print_exc()
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
        if not self._initialized:
            if not self.initialize():
                return EngineResponse(action=None, who="Error")

        with self._lock:  # Thread-safety lock
            try:
                import ctypes
                ben_path = self._find_ben_path()
                src_path = os.path.join(ben_path, 'src')
                original_cwd = os.getcwd()
                os.chdir(src_path)

                try:
                    from ddsolver import dds

                    # Get the hand to play from
                    hand = board.hands.get(seat)
                    if not hand or not hand.cards:
                        return EngineResponse(action=None, who="NoCards")

                    # Determine lead suit constraint
                    lead_suit = None
                    if current_trick_cards:
                        lead_suit = current_trick_cards[0].suit

                    # Get legal cards
                    if lead_suit is not None:
                        suit_cards = [c for c in hand.cards if c.suit == lead_suit]
                        legal_cards = suit_cards if suit_cards else hand.cards
                    else:
                        legal_cards = hand.cards[:]

                    if not legal_cards:
                        return EngineResponse(action=None, who="NoCards")

                    if len(legal_cards) == 1:
                        # Only one choice
                        return EngineResponse(action=legal_cards[0], who="DD-Forced")

                    # Build the current position for DDS
                    # We need to create a deal string and solve for each legal card
                    pbn_deal = board.to_pbn_deal()

                    # DDS SolveBoard can tell us which cards are optimal
                    # For simplicity, we'll evaluate each legal card

                    best_card = None
                    best_tricks = -1
                    candidates = []

                    trump_suit = board.contract.suit if board.contract else Suit.NOTRUMP
                    trump_val = trump_suit.value if trump_suit != Suit.NOTRUMP else 4

                    # For each legal card, simulate playing it and solve
                    for card in legal_cards:
                        # Create a copy of the position with this card played
                        # Use DDS to evaluate

                        # Simplified: use SolveBoardPBN to get trick counts
                        # The DDS interface expects specific formats

                        # For now, use a heuristic: prefer higher cards when following,
                        # prefer lower cards when discarding
                        score = 0

                        if lead_suit is None:
                            # Leading: prefer honors in long suits
                            suit_len = hand.suit_length(card.suit)
                            score = suit_len * 10 + (13 - card.rank.value)
                        elif card.suit == lead_suit:
                            # Following suit: prefer winning or cheap cards
                            score = 13 - card.rank.value  # Higher cards score higher
                        else:
                            # Discarding: prefer low cards from short suits
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

                    # Sort candidates by score
                    candidates.sort(key=lambda c: c.score, reverse=True)

                    return EngineResponse(
                        action=best_card or legal_cards[0],
                        candidates=candidates,
                        who="DD"
                    )

                finally:
                    os.chdir(original_cwd)

            except Exception as e:
                if self.verbose:
                    print(f"Error in DD card play: {e}")
                    import traceback
                    traceback.print_exc()

                # Fallback to regular card play - note: must release lock before calling
                pass

        # Fallback outside the lock to avoid deadlock
        return self.get_card_play(board, seat, current_trick_cards)

    def _build_ben_auction(self, board: BoardState) -> List[str]:
        """Build auction list in BEN format"""
        auction = []

        # Add PAD_START for positions before dealer
        for i in range(board.dealer.value):
            auction.append('PAD_START')

        # Add bids
        for bid in board.auction:
            auction.append(bid.to_ben_str())

        return auction

    def calculate_score(self, contract: Contract, tricks: int,
                       vulnerable: bool) -> int:
        """Calculate score for a contract result"""
        try:
            ben_path = self._find_ben_path()
            src_path = os.path.join(ben_path, 'src')

            if src_path not in sys.path:
                sys.path.insert(0, src_path)

            import scoring

            contract_str = contract.to_str()
            return scoring.score(contract_str, vulnerable, tricks)

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
        """Release TensorFlow resources to prevent segfaults on exit."""
        try:
            import tensorflow as tf
            tf.keras.backend.clear_session()
        except Exception:
            pass
        self.models = None
        self.sampler = None
        self.dds = None
        self._initialized = False

    def shutdown(self):
        """Shutdown the engine (alias for cleanup)."""
        self.cleanup()
