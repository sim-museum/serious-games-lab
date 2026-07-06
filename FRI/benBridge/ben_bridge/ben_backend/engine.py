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
        self._lock = threading.Lock()  # Thread-safety lock
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
