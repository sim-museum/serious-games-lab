"""
MainWindow - Central window for the BEN Bridge application.
Classic Bridge interface with declarer play support.
"""

import os
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QStatusBar, QToolBar, QLabel, QProgressBar,
    QMessageBox, QFileDialog, QApplication, QDockWidget, QPushButton,
    QFrame, QSizePolicy, QInputDialog, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon

from .table_view import TableView, COLORS
from .bidding_box import BiddingBox
from .game_logger import GameLogger
from .dialogs.player_config import PlayerConfigDialog
from .dialogs.match_control import MatchControlDialog
from .dialogs.deal_filter import DealFilterDialog
from .dialogs.score_table import ScoreTableDialog
from .dialogs.simulation import SimulationDialog
from .dialogs.preferences import PreferencesDialog
from .dialogs.deal_entry import DealEntryDialog
from .dialogs.scoring_table import ScoringTableDialog
from .dialogs.info_tables import IMPTableDialog, ProbabilitiesDialog, ScoringReferenceDialog
from .dialogs.bidding_system import BiddingSystemDialog
from .dialogs.end_of_hand import EndOfHandDialog, PassedOutDialog
from .dialogs.teams_score import TeamsScoreDialog
from .dialogs.replay_view import ReplayViewDialog
from .dialogs.deal_converter import DealConverterDialog
from .dialogs.start_server_dialog import StartServerDialog
from .dialogs.connect_server_dialog import ConnectServerDialog
from .dialogs.network_lobby_dialog import NetworkLobbyDialog

from ben_backend import BridgeEngine, BoardState
from network import NetworkGameController
from ben_backend.models import (
    Seat, Suit, Vulnerability, Bid, Card, Contract, Hand, PlayerType, Player, Trick,
    BenTable, BenBoardRun, BenTeamsMatch
)
from ben_backend.pavlicek import number_to_deal, parse_deal_number, deal_to_number, format_deal_base72, int_to_base72
from ben_backend.config import get_config_manager, ConfigManager
from ben_backend.scoring import ScoringTable, ScoringType, BoardResult, calculate_contract_score
from ben_backend.match_controller import TeamsMatchController

from typing import Optional, Dict, List


class EngineWorker(QThread):
    """Worker thread for engine operations"""

    bid_ready = pyqtSignal(object)  # Emits EngineResponse
    card_ready = pyqtSignal(object)  # Emits EngineResponse
    error = pyqtSignal(str)

    def __init__(self, engine: BridgeEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.task = None
        self.board = None
        self.seat = None
        self.trick_cards = None

    def request_bid(self, board: BoardState, seat: Seat):
        if self.isRunning():
            return  # Don't start if already running
        self.task = 'bid'
        self.board = board
        self.seat = seat
        self.start()

    def request_card(self, board: BoardState, seat: Seat, trick_cards=None):
        if self.isRunning():
            return False  # Indicate request was not started
        self.task = 'card'
        self.board = board
        self.seat = seat
        self.trick_cards = trick_cards or []
        self.start()
        return True  # Indicate request was started

    def run(self):
        try:
            if self.task == 'bid':
                # Route bidding to the native engine when the preference is
                # set, falling back to BEN for any error or for "BEN".
                bidder = self.engine
                try:
                    from ben_backend.config import get_config_manager
                    prefs = get_config_manager().config.preferences
                    if getattr(prefs, 'bidding_engine', 'BEN') == 'native':
                        from ben_backend.native_bidder import NativeBiddingEngine
                        bidder = NativeBiddingEngine(
                            system=getattr(prefs, 'native_bidding_system', 'SAYC')
                        )
                except Exception:
                    bidder = self.engine
                response = bidder.get_bid(self.board, self.seat)
                self.bid_ready.emit(response)
            elif self.task == 'card':
                # Check if this is the opening lead (first card of play phase)
                # Opening lead: no tricks completed yet and current trick is empty
                is_opening_lead = (
                    len(self.board.tricks) == 0 and
                    (not self.board.current_trick or len(self.board.current_trick.cards) == 0)
                )
                if is_opening_lead:
                    response = self.engine.get_opening_lead(self.board)
                else:
                    # Route to the selected play engine
                    from ben_backend.config import get_config_manager
                    prefs = get_config_manager().config.preferences
                    if prefs.use_monte_carlo_play:
                        response = self.engine.get_mc_card_play(
                            self.board, self.seat, self.trick_cards
                        )
                    elif prefs.use_double_dummy_play:
                        response = self.engine.get_dd_card_play(
                            self.board, self.seat, self.trick_cards
                        )
                    else:
                        response = self.engine.get_card_play(
                            self.board, self.seat, self.trick_cards
                        )
                self.card_ready.emit(response)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class GameController:
    """
    Controls the game flow: deals, bidding, play.
    Manages interaction between human players and BEN.
    Supports human declarer control of both declarer and dummy hands.
    """

    def __init__(self, engine: BridgeEngine):
        self.engine = engine
        self.board: Optional[BoardState] = None
        self.players: Dict[Seat, Player] = {}
        self.current_phase = 'idle'  # idle, bidding, play, waiting_next, finished
        self.current_seat: Optional[Seat] = None
        self.declarer: Optional[Seat] = None
        self.dummy: Optional[Seat] = None
        self.opening_leader: Optional[Seat] = None
        self.human_controls_declarer = False  # True if human plays declarer side

        # Initialize default players
        for seat in Seat:
            self.players[seat] = Player(
                seat=seat,
                player_type=PlayerType.COMPUTER if seat != Seat.SOUTH else PlayerType.HUMAN
            )

    def new_deal(self, board_number: int = None) -> BoardState:
        """Generate a new random deal"""
        self.board = self.engine.random_deal(board_number)
        self.current_phase = 'bidding'
        self.current_seat = self.board.dealer
        self.declarer = None
        self.dummy = None
        self.opening_leader = None
        self.human_controls_declarer = False
        return self.board

    def load_deal(self, pbn: str, board_number: int = 1) -> BoardState:
        """Load a deal from PBN string"""
        self.board = BoardState.from_pbn_deal(pbn, board_number)
        self.current_phase = 'bidding'
        self.current_seat = self.board.dealer
        self.declarer = None
        self.dummy = None
        return self.board

    def is_human_turn(self) -> bool:
        """Check if it's a human player's turn"""
        if self.current_seat is None:
            return False

        # During play, check if human controls this seat
        if self.current_phase == 'play':
            result = self._human_controls_seat(self.current_seat)
            return result
        else:
            pass

        return self.players[self.current_seat].player_type == PlayerType.HUMAN

    def _human_controls_seat(self, seat: Seat) -> bool:
        """Check if human controls this seat (either as player or declarer controlling dummy)"""
        if self.players[seat].player_type == PlayerType.HUMAN:
            return True

        # If human is declarer/dummy, they control both hands
        if self.human_controls_declarer:
            result = seat in (self.declarer, self.dummy)
            return result

        return False

    def make_bid(self, bid: Bid) -> bool:
        """Process a bid"""
        if self.current_phase != 'bidding':
            return False

        self.board.auction.append(bid)

        # Check if bidding is complete
        if self.board.is_auction_complete():
            if self.board.is_passed_out():
                self.current_phase = 'finished'
            else:
                self._setup_play()
            return True

        # Advance to next bidder
        self.current_seat = self.current_seat.next()
        return True

    def _setup_play(self):
        """Setup for card play after bidding"""
        auction = self.board.auction

        # Find contract
        level = 0
        suit = None
        declarer = None
        doubled = False
        redoubled = False

        for i, bid in enumerate(auction):
            if not bid.is_pass and not bid.is_double and not bid.is_redouble:
                level = bid.level
                suit = bid.suit
                # A new suit/level call clears any prior X/XX — doubles only
                # apply to the contract that becomes final, not to bids that
                # were later overcalled.
                doubled = False
                redoubled = False
                bidder_seat = Seat((self.board.dealer.value + i) % 4)

                # Find first bid of this suit by this side
                side_ns = bidder_seat.is_ns()
                for j, b in enumerate(auction[:i+1]):
                    if not b.is_pass and not b.is_double and not b.is_redouble:
                        if b.suit == suit:
                            b_seat = Seat((self.board.dealer.value + j) % 4)
                            if b_seat.is_ns() == side_ns:
                                declarer = b_seat
                                break
            elif bid.is_double:
                doubled = True
                redoubled = False
            elif bid.is_redouble:
                redoubled = True

        self.board.contract = Contract(
            level=level,
            suit=suit,
            doubled=doubled,
            redoubled=redoubled,
            declarer=declarer
        )

        self.declarer = declarer
        self.dummy = declarer.partner()
        self.opening_leader = declarer.next()
        # DIAGNOSTIC: capture board number, auction, and computed
        # declarer/opening_leader so we can see why host vs guest disagree.
        try:
            auc = " ".join(b.symbol() for b in auction)
            print(f"[_setup_play] board={self.board.board_number} "
                  f"dealer={self.board.dealer.to_char()} "
                  f"auction=[{auc}] "
                  f"contract={self.board.contract.to_str()} "
                  f"declarer={declarer.to_char()} "
                  f"opening_leader={self.opening_leader.to_char()}",
                  flush=True)
        except Exception:
            pass

        # Check if human controls the declarer side
        human_seat = None
        for seat, player in self.players.items():
            if player.player_type == PlayerType.HUMAN:
                human_seat = seat
                break

        if human_seat is not None:
            # Human controls declarer if they are declarer OR dummy
            self.human_controls_declarer = (human_seat == self.declarer or human_seat == self.dummy)
        else:
            pass

        self.current_phase = 'play'
        self.current_seat = self.opening_leader

    def play_card(self, card: Card) -> bool:
        """Process a card play"""
        if self.current_phase != 'play':
            return False

        # Remove card from hand
        if self.current_seat in self.board.hands:
            self.board.hands[self.current_seat].remove_card(card)

        # Add to current trick
        if not self.board.current_trick:
            self.board.current_trick = Trick(leader=self.current_seat)

        trump = self.board.contract.suit if self.board.contract.suit != Suit.NOTRUMP else None
        self.board.current_trick.add_card(card, trump)

        # Check if trick is complete
        if self.board.current_trick.is_complete():
            winner = self.board.current_trick.winner
            self.board.tricks.append(self.board.current_trick)

            # Update tricks won
            if winner.is_ns() == self.board.contract.declarer.is_ns():
                self.board.declarer_tricks += 1
            else:
                self.board.defense_tricks += 1

            # Check if play is complete
            if len(self.board.tricks) == 13:
                self.current_phase = 'finished'
                return True

            # Enter waiting state for "Next Card" button
            self.current_phase = 'waiting_next'
            self.current_seat = winner
            return True
        else:
            self.current_seat = self.current_seat.next()

        return True

    def advance_to_next_trick(self):
        """Called when user clicks Next Card after a trick completes"""
        if self.current_phase == 'waiting_next':
            self.board.current_trick = None
            self.current_phase = 'play'

    def get_lead_suit(self) -> Optional[Suit]:
        """Get the suit led in the current trick"""
        if self.board.current_trick and self.board.current_trick.cards:
            return self.board.current_trick.cards[0].suit
        return None

    def get_trick_winner(self) -> Optional[Seat]:
        """Get the winner of the last completed trick"""
        if self.board.tricks:
            return self.board.tricks[-1].winner
        return None


class ToolbarButton(QPushButton):
    """Styled toolbar button"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.setMinimumWidth(85)
        self.setMinimumHeight(30)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['button_bg']};
                color: {COLORS['button_text']};
                border: 1px solid #4a6a7a;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: #70a0b0;
            }}
            QPushButton:pressed {{
                background-color: #5080a0;
            }}
            QPushButton:disabled {{
                background-color: #4a5a6a;
                color: #888888;
            }}
        """)


class MainWindow(QMainWindow):
    """
    Main application window for BEN Bridge.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("BEN Bridge")
        self.setMinimumSize(1200, 920)

        # Set window background and ensure menus have proper contrast
        self.setStyleSheet(f"""
            background-color: {COLORS['background']};
            QMenu {{
                background-color: #f0f0f0;
                color: #000000;
                border: 1px solid #606060;
                padding: 4px;
            }}
            QMenu::item {{
                background-color: #f0f0f0;
                padding: 6px 30px 6px 20px;
                color: #000000;
            }}
            QMenu::item:selected {{
                background-color: #3070b0;
                color: #ffffff;
            }}
            QMenu::item:disabled {{
                color: #808080;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: #a0a0a0;
                margin: 4px 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #f0f0f0;
                color: #000000;
                selection-background-color: #3070b0;
                selection-color: #ffffff;
            }}
        """)

        # Initialize engine and game controller
        self.engine = BridgeEngine(verbose=False)
        self.controller = GameController(self.engine)

        # Engine worker for async operations
        self.engine_worker = None

        # Game logger for saving hands in BDL format
        self.game_logger = GameLogger()
        self.original_hands: Optional[Dict[Seat, Hand]] = None  # Store hands before play
        self.card_history: List[tuple] = []  # List of (seat, card) for undo during play

        # Scoring table for session results
        self.scoring_table = ScoringTable(ScoringType.TEAMS)

        # Teams match support
        self.teams_match: Optional[BenTeamsMatch] = None
        self.match_controller: Optional[TeamsMatchController] = None

        # Parallel closed room worker (started at deal time, joined at hand end)
        self._pending_closed_room: Optional[dict] = None
        # Snapshot of the just-finished hand awaiting Claude analysis. Set
        # by _show_result, consumed by _maybe_run_pending_claude after a
        # Q-Plus ingest or before the next deal.
        self._claude_pending: Optional[dict] = None
        # Cache of Claude-annotated hand logs, keyed by (board_number,
        # pavlicek_id). _show_claude_hand_analysis populates it on a
        # successful run; subsequent calls for the same board (e.g. the
        # user reopening "Hand Log" after returning from the summary
        # view) replay the cached annotated BDL instead of paying for
        # another Claude round-trip.
        self._claude_hand_logs: Dict[tuple, dict] = {}

        # The seat the local user actually wants to play. This is the
        # canonical record across network connect/disconnect transitions:
        # after the host disconnects we keep the guest at this seat instead
        # of resetting to South. Only set_local_seat() and the user
        # picking a different seat in the lobby change it.
        self._user_seat: Seat = Seat.SOUTH

        # Network game controller for LAN play
        self.network_controller = NetworkGameController(self)
        self._setup_network_signals()

        # Configuration manager
        self.config_manager = get_config_manager()

        # Initialize suit color mode from preferences
        from .styles import set_suit_color_mode, SuitColorMode
        if self.config_manager.config.preferences.legacy_colors:
            set_suit_color_mode(SuitColorMode.TRADITIONAL)
        else:
            set_suit_color_mode(SuitColorMode.FOUR_COLOR)

        # Setup UI
        self._setup_ui()
        self._setup_menus()
        self._setup_bottom_toolbar()
        self._setup_statusbar()
        self._setup_bid_info_window()

        # Connect signals
        self._connect_signals()

        # Initialize engine in background
        QTimer.singleShot(100, self._initialize_engine)

    def _setup_ui(self):
        """Setup the main UI layout"""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)

        # Left side: Table view
        self.table_view = TableView()
        content_layout.addWidget(self.table_view, stretch=3)

        # Right side: Bidding box and analysis (hidden during card play)
        self.right_panel = QWidget()
        self.right_panel.setMaximumWidth(280)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        self.bidding_box = BiddingBox()
        right_layout.addWidget(self.bidding_box)

        # Analysis info area
        self.analysis_label = QLabel("")
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setFont(QFont("Monospace", 14))
        self.analysis_label.setStyleSheet(f"""
            QLabel {{
                background-color: #2a3a4a;
                border: 1px solid #4a5a6a;
                padding: 8px;
                font-family: monospace;
                font-size: 22px;
                color: {COLORS['text_white']};
            }}
        """)
        self.analysis_label.setMinimumHeight(100)
        right_layout.addWidget(self.analysis_label)

        # Set initial visibility based on preference
        self.analysis_label.setVisible(self.config_manager.config.preferences.show_ben_bid_analysis)

        right_layout.addStretch()
        content_layout.addWidget(self.right_panel)

        main_layout.addWidget(content_widget, stretch=1)

        # Bottom toolbar container
        self.toolbar_container = QFrame()
        self.toolbar_container.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel_teal']};
                border-top: 2px solid #3a6a7a;
            }}
        """)
        self.toolbar_container.setFixedHeight(45)

        main_layout.addWidget(self.toolbar_container)

    def _setup_menus(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        # Use more specific styling with higher contrast
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #d0d0d0;
                color: #000000;
                border-bottom: 1px solid #808080;
                padding: 2px;
                font-size: 14px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
                color: #000000;
            }
            QMenuBar::item:selected {
                background-color: #4080c0;
                color: #ffffff;
            }
            QMenuBar::item:pressed {
                background-color: #3060a0;
                color: #ffffff;
            }
        """)

        # Define menu style to apply to each menu
        self._menu_style = """
            QMenu {
                background-color: #f0f0f0;
                color: #000000;
                border: 1px solid #606060;
                padding: 4px;
            }
            QMenu::item {
                background-color: #f0f0f0;
                padding: 6px 30px 6px 20px;
                color: #000000;
            }
            QMenu::item:selected {
                background-color: #3070b0;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #808080;
            }
            QMenu::separator {
                height: 1px;
                background-color: #a0a0a0;
                margin: 4px 10px;
            }
        """

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.setStyleSheet(self._menu_style)

        new_action = QAction("&New Deal", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_menu_new_deal)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Deal File...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Deals...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_action = QAction("&Export HTML...", self)
        export_action.triggered.connect(self._on_export_html)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Configuration menu
        config_menu = menubar.addMenu("&Configuration")
        config_menu.setStyleSheet(self._menu_style)

        players_action = QAction("&Players...", self)
        players_action.triggered.connect(self._on_configure_players)
        config_menu.addAction(players_action)

        systems_action = QAction("Bidding &Systems...", self)
        systems_action.triggered.connect(self._on_configure_systems)
        config_menu.addAction(systems_action)

        config_menu.addSeparator()

        lead_ns_action = QAction("&Lead/Signals N/S...", self)
        lead_ns_action.triggered.connect(lambda: self._on_lead_signal("NS"))
        config_menu.addAction(lead_ns_action)

        lead_ew_action = QAction("Lead/Signals &E/W...", self)
        lead_ew_action.triggered.connect(lambda: self._on_lead_signal("EW"))
        config_menu.addAction(lead_ew_action)

        config_menu.addSeparator()

        strength_action = QAction("Playing &Strength...", self)
        strength_action.triggered.connect(self._on_strength)
        config_menu.addAction(strength_action)

        config_menu.addSeparator()

        check_action = QAction("&Check Configuration!", self)
        check_action.triggered.connect(self._on_config_check)
        config_menu.addAction(check_action)

        config_menu.addSeparator()

        prefs_action = QAction("&Preferences...", self)
        prefs_action.triggered.connect(self._on_preferences)
        config_menu.addAction(prefs_action)

        # Deal menu
        deal_menu = menubar.addMenu("&Deal")
        deal_menu.setStyleSheet(self._menu_style)

        match_control_action = QAction("&Match Control...", self)
        match_control_action.triggered.connect(self._on_match_control)
        deal_menu.addAction(match_control_action)

        repeat_action = QAction("&Repeat Deal", self)
        repeat_action.setShortcut(Qt.Key.Key_F5)
        repeat_action.triggered.connect(self._on_repeat_deal)
        deal_menu.addAction(repeat_action)

        prev_deal_action = QAction("&Previous Deal", self)
        prev_deal_action.setShortcut(Qt.Key.Key_F4)
        prev_deal_action.triggered.connect(self._on_previous_deal)
        deal_menu.addAction(prev_deal_action)

        deal_menu.addSeparator()

        filter_action = QAction("Deal &Filter...", self)
        filter_action.triggered.connect(self._on_deal_filter)
        deal_menu.addAction(filter_action)

        deal_menu.addSeparator()

        load_pavlicek_action = QAction("Load &Pavlicek Deal...", self)
        load_pavlicek_action.triggered.connect(self._on_load_pavlicek)
        deal_menu.addAction(load_pavlicek_action)

        convert_action = QAction("&Convert hand code / PBN...", self)
        convert_action.triggered.connect(self._on_convert_deal)
        deal_menu.addAction(convert_action)

        # Own Deals menu
        own_deals_menu = menubar.addMenu("&Own Deals")
        own_deals_menu.setStyleSheet(self._menu_style)

        enter_deal_action = QAction("&Enter Deal...", self)
        enter_deal_action.triggered.connect(self._on_enter_deal)
        own_deals_menu.addAction(enter_deal_action)

        save_deals_action = QAction("&Save Entered Deals...", self)
        save_deals_action.triggered.connect(self._on_save_entered_deals)
        own_deals_menu.addAction(save_deals_action)

        own_deals_menu.addSeparator()

        use_own_action = QAction("&Use Own Deals File...", self)
        use_own_action.triggered.connect(self._on_use_own_deals)
        own_deals_menu.addAction(use_own_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.setStyleSheet(self._menu_style)

        show_all_action = QAction("Show &All Hands", self)
        show_all_action.setShortcut(Qt.Key.Key_F2)
        show_all_action.triggered.connect(self._on_show_all_hands)
        view_menu.addAction(show_all_action)

        self.bid_info_action = QAction("&Bidding Information", self)
        self.bid_info_action.setShortcut(Qt.Key.Key_F3)
        self.bid_info_action.setCheckable(True)
        self.bid_info_action.setChecked(True)
        self.bid_info_action.triggered.connect(self._on_toggle_bid_info)
        view_menu.addAction(self.bid_info_action)

        view_menu.addSeparator()

        scores_action = QAction("&Score Table...", self)
        scores_action.triggered.connect(self._on_show_scores)
        view_menu.addAction(scores_action)

        teams_score_action = QAction("&Teams Match Score...", self)
        teams_score_action.triggered.connect(self._on_view_teams_score)
        view_menu.addAction(teams_score_action)

        dd_action = QAction("&Double Dummy Analysis", self)
        dd_action.triggered.connect(self._on_dd_analysis)
        view_menu.addAction(dd_action)

        simulation_action = QAction("Bid &Simulation...", self)
        simulation_action.triggered.connect(self._on_simulation)
        view_menu.addAction(simulation_action)

        auction_tricks_action = QAction("&Auction and Played Tricks...", self)
        auction_tricks_action.triggered.connect(self._on_view_auction_tricks)
        view_menu.addAction(auction_tricks_action)

        view_menu.addSeparator()

        # Hand Log — re-opens the most recent Claude annotated BDL for
        # the current/last finished hand. Cached, so reselecting it
        # doesn't pay for another Claude round-trip.
        hand_log_action = QAction("&Hand Log (Claude Analysis)", self)
        hand_log_action.setToolTip(
            "Reopen the Claude-annotated BDL log for the current hand. "
            "Cached after the first run so reselecting doesn't trigger "
            "another Claude call."
        )
        hand_log_action.triggered.connect(self._on_show_hand_log)
        view_menu.addAction(hand_log_action)

        edit_remark_action = QAction("&Edit Remark...", self)
        edit_remark_action.triggered.connect(self._on_edit_remark)
        view_menu.addAction(edit_remark_action)

        view_remark_action = QAction("View &Remark", self)
        view_remark_action.triggered.connect(self._on_view_remark)
        view_menu.addAction(view_remark_action)

        view_menu.addSeparator()

        show_log_action = QAction("Show &Current Log File", self)
        show_log_action.triggered.connect(self._on_show_current_log)
        view_menu.addAction(show_log_action)

        show_prev_logs_action = QAction("Show &Previous Log Files...", self)
        show_prev_logs_action.triggered.connect(self._on_show_previous_logs)
        view_menu.addAction(show_prev_logs_action)

        view_menu.addSeparator()

        imp_table_action = QAction("&IMP Conversion Table...", self)
        imp_table_action.triggered.connect(self._on_show_imp_table)
        view_menu.addAction(imp_table_action)

        prob_action = QAction("&Probabilities Table...", self)
        prob_action.triggered.connect(self._on_show_probabilities)
        view_menu.addAction(prob_action)

        scoring_ref_action = QAction("Scoring &Reference...", self)
        scoring_ref_action.triggered.connect(self._on_show_scoring_reference)
        view_menu.addAction(scoring_ref_action)

        # Extras menu
        extras_menu = menubar.addMenu("&Extras")
        extras_menu.setStyleSheet(self._menu_style)

        self.minibridge_action = QAction("&MiniBridge Mode...", self)
        self.minibridge_action.setCheckable(True)
        self.minibridge_action.triggered.connect(self._on_minibridge)
        extras_menu.addAction(self.minibridge_action)

        extras_menu.addSeparator()

        multiplay_action = QAction("Computer &Multiplay...", self)
        multiplay_action.triggered.connect(self._on_multiplay)
        extras_menu.addAction(multiplay_action)

        extras_menu.addSeparator()

        rubber_action = QAction("&Rubber Scoring...", self)
        rubber_action.triggered.connect(self._on_rubber_scoring)
        extras_menu.addAction(rubber_action)

        extras_menu.addSeparator()

        # Q-Plus closed-room ingest. Greyed out when Q-Plus isn't
        # installed; guests can't ingest (the host pushes the run to them
        # via CLOSED_ROOM_INGESTED) so the action stays disabled for them
        # too. Updated dynamically by _refresh_qplus_ingest_action_state.
        self.ingest_qplus_action = QAction("&Ingest Q-Plus Closed Room...", self)
        self.ingest_qplus_action.triggered.connect(self._on_ingest_qplus_closed_room)
        extras_menu.addAction(self.ingest_qplus_action)
        self._refresh_qplus_ingest_action_state()

        # LIN-format closed-room database loader. Loads played-out hands
        # from a BBO vugraph LIN file and ingests them as closed-room
        # results so the score sheet can compute IMPs against them.
        self.ingest_lin_action = QAction("Load &Closed-Room Database (LIN)...", self)
        self.ingest_lin_action.setToolTip(
            "Load a BBO vugraph LIN file. Played-out deals are ingested as "
            "closed-room results; IMPs vs the human's open room are then "
            "shown in the score table.")
        self.ingest_lin_action.triggered.connect(self._on_load_lin_database)
        extras_menu.addAction(self.ingest_lin_action)

        # Network menu
        network_menu = menubar.addMenu("&Network")
        network_menu.setStyleSheet(self._menu_style)

        start_server_action = QAction("&Start Server...", self)
        start_server_action.triggered.connect(self._on_start_server)
        network_menu.addAction(start_server_action)

        connect_server_action = QAction("&Connect to Server...", self)
        connect_server_action.triggered.connect(self._on_connect_server)
        network_menu.addAction(connect_server_action)

        network_menu.addSeparator()

        self.disconnect_action = QAction("&Disconnect", self)
        self.disconnect_action.triggered.connect(self._on_network_disconnect)
        self.disconnect_action.setEnabled(False)
        network_menu.addAction(self.disconnect_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.setStyleSheet(self._menu_style)

        about_action = QAction("&About...", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        help_action = QAction("&Help Contents", self)
        help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        help_menu.addAction(help_action)

    def _setup_bottom_toolbar(self):
        """Setup the bottom toolbar with two modes:
        - Opening mode: First deal, Pair tourn., Closed Room, etc.
        - In-game mode: Next deal, Next card, Hint, etc.
        """
        layout = QHBoxLayout(self.toolbar_container)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        toolbar_button_style = """
            QPushButton {
                background-color: #d0d0d0;
                color: #000000;
                border: 1px solid #808080;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 12px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
        """

        # === Opening screen buttons ===
        self.opening_buttons = []

        self.first_deal_btn = QPushButton("First deal")
        self.first_deal_btn.setStyleSheet(toolbar_button_style)
        self.first_deal_btn.clicked.connect(self._on_first_deal)
        layout.addWidget(self.first_deal_btn)
        self.opening_buttons.append(self.first_deal_btn)

        self.pair_tourn_btn = QPushButton("Pair tourn.")
        self.pair_tourn_btn.setStyleSheet(toolbar_button_style)
        self.pair_tourn_btn.clicked.connect(self._on_pair_tournament)
        layout.addWidget(self.pair_tourn_btn)
        self.opening_buttons.append(self.pair_tourn_btn)

        self.closed_room_toolbar_btn = QPushButton("Closed Room")
        self.closed_room_toolbar_btn.setStyleSheet(toolbar_button_style)
        self.closed_room_toolbar_btn.clicked.connect(self._on_closed_room_start)
        layout.addWidget(self.closed_room_toolbar_btn)
        self.opening_buttons.append(self.closed_room_toolbar_btn)

        self.team_tourn_btn = QPushButton("Team tourn.")
        self.team_tourn_btn.setStyleSheet(toolbar_button_style)
        self.team_tourn_btn.clicked.connect(self._on_team_tournament)
        layout.addWidget(self.team_tourn_btn)
        self.opening_buttons.append(self.team_tourn_btn)

        self.match_control_btn = QPushButton("Match control")
        self.match_control_btn.setStyleSheet(toolbar_button_style)
        self.match_control_btn.clicked.connect(self._on_match_control)
        layout.addWidget(self.match_control_btn)
        self.opening_buttons.append(self.match_control_btn)

        self.opening_help_btn = QPushButton("Help")
        self.opening_help_btn.setStyleSheet(toolbar_button_style)
        self.opening_help_btn.clicked.connect(self._on_help)
        layout.addWidget(self.opening_help_btn)
        self.opening_buttons.append(self.opening_help_btn)

        # === In-game buttons ===
        self.ingame_buttons = []

        self.next_deal_btn = ToolbarButton("Next deal")
        self.next_deal_btn.clicked.connect(self._on_next_deal)
        layout.addWidget(self.next_deal_btn)
        self.ingame_buttons.append(self.next_deal_btn)

        self.next_card_btn = ToolbarButton("Next card")
        self.next_card_btn.clicked.connect(self._on_next_card)
        self.next_card_btn.setEnabled(False)
        layout.addWidget(self.next_card_btn)
        self.ingame_buttons.append(self.next_card_btn)

        # Spacebar shortcut for Next card. Use a window-scoped shortcut
        # so the press fires regardless of which child widget has focus,
        # and gate it on the button's enabled state inside the handler
        # so we don't double-advance when auto-advance is in flight.
        from PyQt6.QtGui import QShortcut
        from PyQt6.QtCore import Qt as _Qt
        self._next_card_shortcut = QShortcut(QKeySequence(_Qt.Key.Key_Space), self)
        self._next_card_shortcut.setContext(_Qt.ShortcutContext.WindowShortcut)
        self._next_card_shortcut.activated.connect(self._on_next_card_shortcut)

        self.hint_btn = ToolbarButton("Hint")
        self.hint_btn.clicked.connect(self._on_hint)
        # Off by default — _advance_game / _refresh_hint_button_state
        # turn it on only when the local user is on lead.
        self.hint_btn.setEnabled(False)
        layout.addWidget(self.hint_btn)
        self.ingame_buttons.append(self.hint_btn)

        self.undo_btn = ToolbarButton("Undo")
        self.undo_btn.clicked.connect(self._on_undo)
        self.undo_btn.setEnabled(False)
        layout.addWidget(self.undo_btn)
        self.ingame_buttons.append(self.undo_btn)

        self.claim_btn = ToolbarButton("Claim")
        self.claim_btn.clicked.connect(self._on_claim)
        self.claim_btn.setEnabled(False)
        layout.addWidget(self.claim_btn)
        self.ingame_buttons.append(self.claim_btn)

        self.evaluate_btn = ToolbarButton("Evaluate")
        self.evaluate_btn.clicked.connect(self._on_evaluate)
        layout.addWidget(self.evaluate_btn)
        self.ingame_buttons.append(self.evaluate_btn)

        self.autoplay_btn = ToolbarButton("Autoplay")
        self.autoplay_btn.setCheckable(True)
        self.autoplay_btn.toggled.connect(self._on_auto_play_toggle)
        layout.addWidget(self.autoplay_btn)
        self.ingame_buttons.append(self.autoplay_btn)

        self.review_btn = ToolbarButton("Review")
        self.review_btn.clicked.connect(self._on_review)
        self.review_btn.setEnabled(False)
        layout.addWidget(self.review_btn)
        self.ingame_buttons.append(self.review_btn)

        self.help_btn = ToolbarButton("Help")
        self.help_btn.clicked.connect(self._on_about)
        layout.addWidget(self.help_btn)
        self.ingame_buttons.append(self.help_btn)

        layout.addStretch()

        # Start in opening mode
        self._set_toolbar_mode('opening')

    def _set_toolbar_mode(self, mode: str):
        """Switch toolbar between 'opening' and 'ingame' modes."""
        if mode == 'opening':
            for btn in self.opening_buttons:
                btn.setVisible(True)
            for btn in self.ingame_buttons:
                btn.setVisible(False)
        else:  # ingame
            for btn in self.opening_buttons:
                btn.setVisible(False)
            for btn in self.ingame_buttons:
                btn.setVisible(True)

    def _on_first_deal(self):
        """Handle First deal button - start new deal and switch to in-game mode."""
        # Reset teams match mode for regular first deal
        self.teams_match = None
        self.match_controller = None
        self._set_toolbar_mode('ingame')
        self._on_new_deal()

    def _on_closed_room_start(self):
        """Handle Closed Room button - start with closed room and switch to in-game mode."""
        self._set_toolbar_mode('ingame')
        self._on_closed_room()

    def _on_menu_new_deal(self):
        """Handle File > New Deal menu - return to opening screen."""
        # Reset any teams match
        if self.match_controller:
            self.match_controller.stop_closed_room()
        self.teams_match = None
        self.match_controller = None
        self._return_to_opening_screen()
        self.status_label.setText("Choose an option to start a new deal")

    def _on_next_deal(self):
        """Handle Next deal button - return to opening screen or advance teams match."""
        # Check if we're still in bidding phase (hand not completed)
        still_in_bidding = (self.controller.current_phase == 'bidding' or
                           (self.controller.board and not self.controller.board.contract))

        # Flush any pending Claude analysis from the previous hand. If the
        # user ingested a Q-Plus closed room, Claude already ran on ingest
        # (idempotent flag); otherwise we run it now with just the open
        # room so the user sees a critique before moving on.
        if not still_in_bidding:
            self._maybe_run_pending_claude()


        # If in teams match mode during bidding, user wants to discard this hand
        if self.teams_match is not None and self.match_controller is not None:
            if still_in_bidding:
                # User wants to discard this hand and start fresh
                # Don't show score dialog, just reset and go back to opening screen
                self.match_controller.stop_closed_room()  # Stop any running closed room
                self.teams_match = None
                self.match_controller = None
                self._return_to_opening_screen()
                self.status_label.setText("Hand discarded. Choose an option to start a new deal")
                return

            # Hand was completed - advance to next board in the match
            next_board = self.teams_match.current_board + 1
            if next_board <= self.teams_match.num_boards:
                self.teams_match.current_board = next_board
                self._start_teams_board(next_board)
            else:
                # Match complete - show final scores and return to opening
                self._on_view_teams_score()
                self.status_label.setText("Teams match complete!")
                self.teams_match = None
                self.match_controller = None
                self._return_to_opening_screen()
            return

        # For normal play, deal the next hand immediately
        self._on_new_deal()
        self.status_label.setText("Choose an option to start a new deal")

    def _return_to_opening_screen(self):
        """Return to the opening screen, clearing any current game state."""
        # Hide game UI elements
        self.bidding_box.setVisible(False)
        self.right_panel.setVisible(False)
        self.bid_info_dock.hide()

        # Clear the table - hide all hands
        for seat in Seat:
            self.table_view.set_hand_visible(seat, False)
        self.table_view.clear_trick()

        # Reset controller
        self.controller.board = None
        self.controller.current_phase = None

        # Switch toolbar to opening mode
        self._set_toolbar_mode('opening')

    def _setup_bid_info_window(self):
        """Setup the bidding-information window as an independent top-level
        window. Previously a QDockWidget — that hybrid behaviour caused it
        to sometimes dock back into the main window and sometimes hide
        behind it on a single-monitor setup. A plain top-level QWidget
        with Qt.WindowType.Window is always free-floating, draggable, and
        keeps the same show/hide API the rest of main_window relies on.
        """
        self.bid_info_dock = QWidget(None, Qt.WindowType.Window)
        self.bid_info_dock.setWindowTitle("Information about the bids ...")
        self.bid_info_dock.setStyleSheet("background-color: #f8f8f8;")

        # Content widget — laid out directly inside the top-level window.
        bid_info_widget = self.bid_info_dock
        bid_info_layout = QVBoxLayout(bid_info_widget)
        bid_info_layout.setContentsMargins(5, 5, 5, 5)
        bid_info_layout.setSpacing(2)

        # System banner — shows which bidding system the labels describe.
        self.bid_info_system_label = QLabel()
        self.bid_info_system_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.bid_info_system_label.setStyleSheet(
            "background-color: #d8e8f8; border: 1px solid #889; padding: 3px;"
        )
        self.bid_info_system_label.setWordWrap(True)
        bid_info_layout.addWidget(self.bid_info_system_label)
        self._refresh_bid_info_system_label()

        # Header row: Bid | Points | Help
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #e0e0e0; border: 1px solid #999;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(5, 3, 5, 3)
        header_layout.setSpacing(0)

        for col_name, width in [("Bid", 100), ("Points", 100), ("Help", 220)]:
            lbl = QLabel(col_name)
            lbl.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            lbl.setFixedWidth(width)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(lbl)

        bid_info_layout.addWidget(header_frame)

        # Scrollable bid history area
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        scroll.setStyleSheet("border: 1px solid #ccc;")

        self.bid_history_widget = QWidget()
        self.bid_history_layout = QVBoxLayout(self.bid_history_widget)
        self.bid_history_layout.setContentsMargins(0, 0, 0, 0)
        self.bid_history_layout.setSpacing(1)
        self.bid_history_layout.addStretch()

        scroll.setWidget(self.bid_history_widget)
        bid_info_layout.addWidget(scroll)

        # Available bids section with meanings
        self.avail_label = QLabel("Available bids:")
        self.avail_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.avail_label.setStyleSheet("margin-top: 5px;")
        bid_info_layout.addWidget(self.avail_label)

        # Scrollable area for available bids with meanings
        avail_scroll = QScrollArea()
        avail_scroll.setWidgetResizable(True)
        avail_scroll.setMinimumHeight(120)
        avail_scroll.setMaximumHeight(180)
        avail_scroll.setStyleSheet("border: 1px solid #ccc; background-color: #fff;")

        self.available_bids_widget = QWidget()
        self.available_bids_layout = QVBoxLayout(self.available_bids_widget)
        self.available_bids_layout.setContentsMargins(5, 5, 5, 5)
        self.available_bids_layout.setSpacing(2)

        avail_scroll.setWidget(self.available_bids_widget)
        bid_info_layout.addWidget(avail_scroll)

        self.bid_info_dock.setMinimumWidth(450)
        self.bid_info_dock.resize(480, 500)
        self.bid_info_dock.move(30, 100)

    def _setup_statusbar(self):
        """Setup the status bar"""
        statusbar = self.statusBar()
        statusbar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['panel_teal']};
                color: {COLORS['text_white']};
                font-size: 14px;
            }}
        """)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet(f"color: {COLORS['text_white']};")
        statusbar.addWidget(self.status_label, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setVisible(False)
        statusbar.addPermanentWidget(self.progress_bar)

        self.engine_status = QLabel("Engine: Not Ready")
        self.engine_status.setFont(QFont("Arial", 14))
        self.engine_status.setStyleSheet(f"color: {COLORS['text_white']};")
        statusbar.addPermanentWidget(self.engine_status)

    def _connect_signals(self):
        """Connect UI signals"""
        self.table_view.card_played.connect(self._on_card_played)
        self.bidding_box.bid_selected.connect(self._on_bid_made)

    def _setup_network_signals(self):
        """Setup network controller signals"""
        self.network_controller.connection_established.connect(self._on_network_connected)
        self.network_controller.connection_lost.connect(self._on_network_disconnected)
        self.network_controller.client_joined.connect(self._on_network_client_joined)
        self.network_controller.server_started.connect(self._on_network_server_started)
        self.network_controller.deal_received.connect(self._on_network_deal_received)
        self.network_controller.dummy_revealed.connect(self._on_network_dummy_revealed)
        self.network_controller.remote_bid_received.connect(self._on_network_remote_bid)
        self.network_controller.remote_card_received.connect(self._on_network_remote_card)
        self.network_controller.trick_clear_received.connect(self._on_network_trick_clear)
        self.network_controller.error_occurred.connect(self._on_network_error)
        self.network_controller.closed_room_ingested.connect(self._on_network_closed_room_ingested)
        # Lobby — drive both the host's NetworkLobbyDialog and the guest's
        # ConnectServerDialog from the same SEAT_LIST stream.
        self.network_controller.seat_map_changed.connect(self._on_network_seat_map)
        self.network_controller.game_starting.connect(self._on_network_game_starting)
        self.network_controller.seat_request_rejected.connect(
            self._on_network_seat_rejected)

    def _initialize_engine(self):
        """Initialize the BEN engine"""
        self.status_label.setText("Initializing engine...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        QApplication.processEvents()

        success = self.engine.initialize()

        self.progress_bar.setVisible(False)

        if success:
            self.engine_status.setText("Engine: Ready")
            self.engine_status.setStyleSheet("color: #00ff00;")
            self.status_label.setText("Engine initialized. Press Ctrl+N for new deal.")

            # Create worker thread
            self.engine_worker = EngineWorker(self.engine)
            self.engine_worker.bid_ready.connect(self._on_engine_bid)
            self.engine_worker.card_ready.connect(self._on_engine_card)
            self.engine_worker.error.connect(self._on_engine_error)
        else:
            self.engine_status.setText("Engine: Failed")
            self.engine_status.setStyleSheet("color: #ff0000;")
            self.status_label.setText("Engine initialization failed!")

    def _update_window_title(self):
        """Update window title with board number"""
        if self.controller.board:
            self.setWindowTitle(f"BEN Bridge - Board #{self.controller.board.board_number}")
        else:
            self.setWindowTitle("BEN Bridge")

    # Menu action handlers

    def _on_new_deal(self):
        """Start a new random deal"""
        if not self.engine.is_ready:
            QMessageBox.warning(self, "Engine Not Ready",
                              "The bridge engine is not yet initialized.")
            return

        # If in teams match mode, use the teams board method
        if self.teams_match is not None and self.match_controller is not None:
            # Advance to next board in teams match
            next_board = self.teams_match.current_board + 1
            if next_board <= self.teams_match.num_boards:
                self.teams_match.current_board = next_board
                self._start_teams_board(next_board)
            else:
                # Match complete - show final scores
                self._on_view_teams_score()
                self.status_label.setText("Teams match complete!")
            return

        board = self.controller.new_deal()

        # Store a deep copy of original hands for logging
        self.original_hands = {}
        for seat, hand in board.hands.items():
            self.original_hands[seat] = Hand(cards=list(hand.cards))

        # Clear card history for undo
        self.card_history = []
        self.undo_btn.setEnabled(False)

        self.table_view.set_board(board)
        self.bidding_box.clear()
        self.bidding_box.set_auction([], board.dealer)
        self.bidding_box.setVisible(True)  # Show bidding box for new deal
        self.right_panel.setVisible(True)  # Ensure right panel is visible
        self.next_deal_btn.setVisible(True)  # Ensure next deal button is visible
        self.analysis_label.setText("")
        self._clear_bid_info()  # Clear bid info window
        self._update_available_bids()
        self._update_window_title()

        # Show bid info window for bidding phase
        if self.bid_info_action.isChecked():
            self.bid_info_dock.show()

        # Set visibility based on player types
        for seat in Seat:
            player = self.controller.players[seat]
            visible = player.player_type == PlayerType.HUMAN
            self.table_view.set_hand_visible(seat, visible)

        # Always show human's hand (South by default)
        self.table_view.set_hand_visible(self._user_seat, True)

        # Enable buttons
        self.next_card_btn.setEnabled(False)

        self.status_label.setText(f"Board {board.board_number}: {board.dealer.to_char()} deals")

        # Closed room (AI vs AI) is started after the human finishes the
        # hand — running it in parallel with human play made both sides
        # contend for the BEN engine and the game appeared to hang.

        # Push the deal to all connected guests so a host-side New Deal
        # click also resets every guest's table (otherwise multi-guest
        # sessions desync the moment the host starts a fresh hand).
        if self.network_controller.is_active and self.network_controller.is_server:
            self.network_controller.broadcast_deal(board)

        # Start bidding
        self._advance_game()

    def _on_open_file(self):
        """Open a deal file (PBN or BDL)"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Deal File", "",
            "Bridge files (*.pbn *.bdl);;PBN Files (*.pbn);;BDL Files (*.bdl);;All Files (*)"
        )
        if filename:
            self._on_open_file_path(filename)

    def _on_save_file(self):
        """Save deals to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Deals", "",
            "PBN Files (*.pbn);;BDL Files (*.bdl);;All Files (*)"
        )
        if filename:
            self.status_label.setText(f"Saved: {os.path.basename(filename)}")

    def _on_export_html(self):
        """Export deal as HTML"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export HTML", "",
            "HTML Files (*.html);;All Files (*)"
        )
        if filename:
            self.status_label.setText(f"Exported: {os.path.basename(filename)}")

    def _on_pair_tournament(self):
        """Start a pairs tournament"""
        # Show match control dialog for pairs configuration
        dialog = MatchControlDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()
            self.status_label.setText("Pairs tournament started")
            self._on_new_deal()

    def _on_closed_room(self):
        """Run the current board in closed room (computer vs computer).

        Creates a single-board teams match, then runs the same deal
        with 4 bots in the closed room while user plays the open room.
        """
        if not self.controller.board:
            # Start a new deal first
            self._on_new_deal()
            if not self.controller.board:
                return

        board = self.controller.board
        board_num = board.board_number

        # Create a single-board teams match if not already in one
        if self.teams_match is None or self.match_controller is None:
            import uuid
            self.teams_match = BenTeamsMatch(
                match_id=str(uuid.uuid4()),
                num_boards=1,
                current_board=board_num,
                ns_bidding_system=self._current_pair_systems()[0],
                ew_bidding_system=self._current_pair_systems()[1],
            )
            self.match_controller = TeamsMatchController(self.engine, self.teams_match)

            # Store original hands for comparison
            if not self.original_hands:
                self.original_hands = {}
                for seat, hand in board.hands.items():
                    self.original_hands[seat] = Hand(cards=list(hand.cards))

            # Register the current board with the match controller
            self.match_controller.start_board(board_num, board)

        # Note: Closed room will be started after human finishes their hand
        # to avoid concurrent engine access (which causes broken pipe errors)
        self.status_label.setText(f"Board {board_num} - Play your hand first, then closed room will run")

    def _on_team_tournament(self):
        """Start a teams tournament"""
        # Show match control dialog for teams configuration
        dialog = MatchControlDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()
            if settings.get('comparison') == 'closed_room':
                self._start_teams_match(settings)
            self.status_label.setText("Teams tournament started")

    def _on_help(self):
        """Show help dialog"""
        help_text = """BEN Bridge - Quick Help

Keyboard Shortcuts:
  Ctrl+N - New deal
  F2 - Show all hands
  P - Pass
  X - Double
  1C-7N - Make a bid

Toolbar Buttons:
  First deal - Start a new random deal
  Pair tourn. - Start pairs tournament
  Closed Room - Run current board with computer
  Team tourn. - Start teams tournament
  Match control - Configure match settings
  Help - Show this help

For more information, see the README file."""
        QMessageBox.information(self, "Help", help_text)

    def _on_match_control(self):
        """Show match control dialog"""
        dialog = MatchControlDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()

            # Check if closed room comparison is enabled
            if settings.get('comparison') == 'closed_room':
                self._start_teams_match(settings)
            else:
                # Clear teams match state for non-teams modes
                self.teams_match = None
                self.match_controller = None

    def _start_teams_match(self, settings: dict):
        """Start a new teams match with closed room comparison."""
        import uuid

        start_num = settings.get('start_number', 1)

        # Create teams match
        ns_sys_name, ew_sys_name = self._current_pair_systems()
        self.teams_match = BenTeamsMatch(
            match_id=str(uuid.uuid4()),
            num_boards=settings.get('num_boards', 16),
            current_board=start_num,
            ns_bidding_system=ns_sys_name,
            ew_bidding_system=ew_sys_name,
        )

        # Create match controller
        self.match_controller = TeamsMatchController(self.engine, self.teams_match)

        print(f"Starting teams match: {self.teams_match.num_boards} boards, starting at {start_num}", flush=True)

        # Start the first board
        self._start_teams_board(start_num)

    def _start_teams_board(self, board_num: int):
        """Start a new board in the teams match."""
        if self.teams_match is None or self.match_controller is None:
            print(f"ERROR: _start_teams_board called but teams_match or match_controller is None", flush=True)
            return

        print(f"Starting teams board {board_num}", flush=True)

        # Generate a new deal
        board = self.controller.new_deal(board_num)

        # Store original hands for logging
        self.original_hands = {}
        for seat, hand in board.hands.items():
            self.original_hands[seat] = Hand(cards=list(hand.cards))

        # Register with match controller
        self.match_controller.start_board(board_num, board)

        # Note: Closed room will be started after human finishes their hand
        # to avoid concurrent engine access (which causes broken pipe errors)

        # Setup the UI for play
        self.table_view.set_board(board)
        self.bidding_box.clear()
        self.bidding_box.set_auction([], board.dealer)
        self.bidding_box.setVisible(True)
        self.right_panel.setVisible(True)
        self._clear_bid_info()
        self._update_available_bids()
        self._update_window_title()

        # Show bid info window
        if self.bid_info_action.isChecked():
            self.bid_info_dock.show()

        # Set visibility for players
        for seat in Seat:
            player = self.controller.players[seat]
            visible = player.player_type == PlayerType.HUMAN
            self.table_view.set_hand_visible(seat, visible)

        self.table_view.set_hand_visible(self._user_seat, True)
        self.next_card_btn.setEnabled(False)
        self.next_deal_btn.setVisible(True)

        self.status_label.setText(
            f"Teams Match - Board {board_num}/{self.teams_match.num_boards}: "
            f"{board.dealer.to_char()} deals"
        )

        self._advance_game()

    def _on_closed_room_complete(self, result: BenBoardRun):
        """Handle completion of closed room play."""
        if result:
            print(f"Closed room complete: Board {result.board_number}, "
                  f"Contract: {result.contract.to_str() if result.contract else 'Passed'}, "
                  f"NS Score: {result.ns_score}", flush=True)

            # Log the closed room result
            try:
                self.game_logger.log_board_run(result)
            except Exception as e:
                print(f"Error logging closed room hand: {e}", flush=True)

            # Update status to show closed room is done
            if self.teams_match:
                imp_swing = self.teams_match.get_imp_swing(result.board_number)
                if imp_swing is not None:
                    self.status_label.setText(
                        f"Closed room complete. IMP swing: {imp_swing:+d}"
                    )
        else:
            print("Closed room complete: No result returned", flush=True)

    def _on_view_teams_score(self):
        """Show the teams score dialog."""
        if self.teams_match is None:
            QMessageBox.information(
                self, "No Teams Match",
                "No teams match is active.\n\n"
                "To start a teams match, go to Deal > Match Control\n"
                "and select 'Against Closed Room (BEN vs BEN)' under Comparison."
            )
            return

        dialog = TeamsScoreDialog(self.teams_match, self)
        dialog.contract_clicked.connect(self._on_replay_board)
        dialog.exec()

    def _on_replay_board(self, board_num: int, table: BenTable):
        """Show replay viewer for a specific board and table."""
        if self.match_controller is None:
            return

        if table == BenTable.OPEN:
            run = self.match_controller.get_open_room_result(board_num)
        else:
            run = self.match_controller.get_closed_room_result(board_num)

        if run and run.played:
            dialog = ReplayViewDialog(run, self)
            dialog.exec()
        else:
            QMessageBox.information(self, "Not Available",
                                   f"The {table.value} room result for board {board_num} "
                                   "is not yet available.")

    def _on_repeat_deal(self):
        """Repeat current deal"""
        if self.controller.board:
            board_num = self.controller.board.board_number
            board = self.controller.new_deal(board_num)
            self.table_view.set_board(board)
            self.bidding_box.clear()
            self.bidding_box.set_auction([], board.dealer)
            self._advance_game()

    def _on_deal_filter(self):
        """Show deal filter dialog"""
        dialog = DealFilterDialog(self)
        dialog.exec()

    def _on_load_pavlicek(self):
        """Load a deal by Pavlicek number"""
        if not self.engine.is_ready:
            QMessageBox.warning(self, "Engine Not Ready",
                              "The bridge engine is not yet initialized.")
            return

        text, ok = QInputDialog.getText(
            self, "Load Pavlicek Deal",
            "Enter Pavlicek deal number (base-72 format, e.g., 6agBeN!sWCn#IdjB):"
        )
        if not ok or not text.strip():
            return

        try:
            deal_number = parse_deal_number(text.strip())
            hands = number_to_deal(deal_number)

            # Create a new board with these hands
            board = BoardState(
                board_number=self.controller.board.board_number + 1 if self.controller.board else 1,
                dealer=Seat.NORTH,  # Default dealer
                vulnerability=Vulnerability.NONE,  # Default vulnerability
                hands=hands
            )

            # Update dealer/vulnerability based on board number
            dealer, vuln = BoardState._board_dealer_vuln(board.board_number)
            board.dealer = dealer
            board.vulnerability = vuln

            self.controller.board = board
            self.controller.current_seat = board.dealer

            # Store original hands for logging
            self.original_hands = {}
            for seat, hand in board.hands.items():
                self.original_hands[seat] = Hand(cards=list(hand.cards))

            self.table_view.set_board(board)
            self.bidding_box.clear()
            self.bidding_box.set_auction([], board.dealer)
            self.bidding_box.setVisible(True)
            self.right_panel.setVisible(True)
            self.next_deal_btn.setVisible(True)
            self.analysis_label.setText("")
            self._clear_bid_info()
            self._update_available_bids()
            self._update_window_title()

            # Show bid info window for bidding phase
            if self.bid_info_action.isChecked():
                self.bid_info_dock.show()

            for seat in Seat:
                player = self.controller.players[seat]
                visible = player.player_type == PlayerType.HUMAN
                self.table_view.set_hand_visible(seat, visible)

            self.table_view.set_hand_visible(self._user_seat, True)
            self.next_card_btn.setEnabled(False)

            self.status_label.setText(f"Board {board.board_number}: {board.dealer.to_char()} deals")

            self._advance_game()

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Deal Number",
                              f"Could not parse deal number: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Error",
                              f"Error loading deal: {e}")

    def _on_convert_deal(self):
        """Show deal converter dialog for hand code / PBN conversion."""
        dialog = DealConverterDialog(self)

        # If we have a current deal, populate it
        if self.controller.board and self.original_hands:
            dialog.set_deal(self.original_hands)

        # Connect load signal
        dialog.load_deal.connect(self._load_converted_deal)
        dialog.exec()

    def _load_converted_deal(self, board: BoardState):
        """Load a deal from the converter dialog."""
        self._load_entered_board(board)

    def _on_enter_deal(self):
        """Show deal entry dialog"""
        dialog = DealEntryDialog(self)
        if dialog.exec():
            board = dialog.get_board()
            if board:
                self._load_entered_board(board)

    def _load_entered_board(self, board: BoardState):
        """Load a manually entered board"""
        if not self.engine.is_ready:
            QMessageBox.warning(self, "Engine Not Ready",
                              "The bridge engine is not yet initialized.")
            return

        self.controller.board = board
        self.controller.current_phase = 'bidding'
        self.controller.current_seat = board.dealer

        # Store original hands for logging
        self.original_hands = {}
        for seat, hand in board.hands.items():
            self.original_hands[seat] = Hand(cards=list(hand.cards))

        self.table_view.set_board(board)
        self.bidding_box.clear()
        self.bidding_box.set_auction([], board.dealer)
        self.bidding_box.setVisible(True)
        self.right_panel.setVisible(True)
        self.next_deal_btn.setVisible(True)
        self.analysis_label.setText("")
        self._clear_bid_info()
        self._update_available_bids()
        self._update_window_title()

        # Show bid info window for bidding phase
        if self.bid_info_action.isChecked():
            self.bid_info_dock.show()

        for seat in Seat:
            player = self.controller.players[seat]
            visible = player.player_type == PlayerType.HUMAN
            self.table_view.set_hand_visible(seat, visible)

        self.table_view.set_hand_visible(self._user_seat, True)
        self.next_card_btn.setEnabled(False)

        self.status_label.setText(f"Board {board.board_number}: {board.dealer.to_char()} deals")
        self._advance_game()

    def _on_save_entered_deals(self):
        """Save entered deals to file"""
        # For now, show a message - full implementation would track entered deals
        QMessageBox.information(self, "Save Deals",
                              "Save entered deals functionality - coming soon.")

    def _on_use_own_deals(self):
        """Load a file of own deals"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Deals File", "DATA/",
            "PBN Files (*.pbn);;BDL Files (*.bdl);;All Files (*)"
        )
        if filename:
            try:
                self._on_open_file_path(filename)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load file: {e}")

    def _on_open_file_path(self, filepath: str):
        """Open a deal file by path — supports PBN and BDL with replay and commentary."""
        from pathlib import Path
        p = Path(filepath)

        if p.suffix.lower() == '.bdl':
            try:
                from ben_backend.bdl_reader import BDLReader
                reader = BDLReader()
                deals = reader.read_file(p)
                if not deals:
                    QMessageBox.warning(self, "BDL Error", "No deals found in file.")
                    return

                # Show a BDL replay dialog with all deals
                self._show_bdl_replay(deals, p.name)
                self.status_label.setText(f"Loaded {len(deals)} deal(s) from {p.name}")
            except Exception as exc:
                QMessageBox.warning(self, "BDL Error", str(exc))

        elif p.suffix.lower() == '.pbn':
            try:
                from ben_backend.pbn_exporter import PBNParser
                boards = PBNParser.parse_file(str(p))
                if boards:
                    self.status_label.setText(f"Loaded {len(boards)} board(s) from {p.name}")
                else:
                    QMessageBox.warning(self, "PBN Error", "No boards found in file.")
            except Exception as exc:
                QMessageBox.warning(self, "PBN Error", str(exc))

    def _show_bdl_replay(self, deals, filename):
        """Show a dialog to browse and replay deals from a BDL file."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QTextEdit, QPushButton, QLabel, QSplitter
        from PyQt6.QtCore import Qt

        dialog = QDialog(self)
        dialog.setWindowTitle(f"BDL Replay — {filename}")
        dialog.resize(900, 650)

        layout = QVBoxLayout(dialog)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: deal list
        list_widget = QListWidget()
        for i, deal in enumerate(deals):
            label = f"Deal {i+1}"
            if deal.contract:
                label += f" — {deal.contract}"
            if deal.commentary:
                label += " [+commentary]"
            list_widget.addItem(label)
        splitter.addWidget(list_widget)

        # Right: detail view
        detail = QTextEdit()
        detail.setReadOnly(True)
        detail.setFontFamily("monospace")
        splitter.addWidget(detail)

        splitter.setSizes([250, 650])
        layout.addWidget(splitter)

        def show_deal(idx):
            if idx < 0 or idx >= len(deals):
                return
            deal = deals[idx]
            text = []
            text.append(f"{'='*50}")
            text.append(f"Deal {idx+1}")
            if deal.pavlicek_id:
                text.append(f"Pavlicek ID: {deal.pavlicek_id}")
            text.append(f"Dealer: {deal.dealer.name}    Vulnerability: {deal.vulnerability.name}")
            text.append("")

            # Show hands
            for seat in [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]:
                hand = deal.hands.get(seat)
                if hand:
                    suits = []
                    for suit in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]:
                        suit_cards = sorted([c for c in hand.cards if c.suit == suit],
                                            key=lambda c: c.rank, reverse=True)
                        symbol = {Suit.SPADES: '♠', Suit.HEARTS: '♥',
                                  Suit.DIAMONDS: '♦', Suit.CLUBS: '♣'}[suit]
                        suits.append(f"{symbol} {''.join(c.rank.to_char() for c in suit_cards)}")
                    text.append(f"  {seat.name:5s}: {' '.join(suits)}")

            text.append("")
            if deal.contract:
                text.append(f"Contract: {deal.contract}")
            if deal.tricks_made:
                text.append(f"Tricks made: {deal.tricks_made}")
            if deal.ns_score or deal.ew_score:
                text.append(f"Score: NS={deal.ns_score}  EW={deal.ew_score}")

            if deal.commentary:
                text.append("")
                text.append(f"{'─'*50}")
                text.append("CLAUDE ANALYSIS:")
                text.append(deal.commentary)

            detail.setPlainText("\n".join(text))

        list_widget.currentRowChanged.connect(show_deal)
        if deals:
            list_widget.setCurrentRow(0)

        # Close button
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_configure_players(self):
        """Show player configuration dialog"""
        dialog = PlayerConfigDialog(self.controller.players, self)
        if dialog.exec():
            self.controller.players = dialog.get_players()

    def _on_configure_systems(self):
        """Show bidding systems dialog.

        Seeds the dialog with the user's current preferred system,
        which lives on ``preferences.native_bidding_system`` (and is
        also what the rule-based bidder reads on every bid). Falls
        back to whatever was last picked in this session, or SAYC.
        """
        try:
            prefs = get_config_manager().config.preferences
            current_system = getattr(
                self, '_current_bidding_system',
                prefs.native_bidding_system or 'SAYC')
        except Exception:
            current_system = getattr(self, '_current_bidding_system', 'SAYC')
        dialog = BiddingSystemDialog(self, current_system)
        if dialog.exec():
            new_system = dialog.get_system()
            self._current_bidding_system = new_system
            self._ns_bidding_system = dialog.get_ns_system()
            self._ew_bidding_system = dialog.get_ew_system()
            self._active_conventions = dialog.get_conventions()

            # Persist to preferences so the rule-based bidder picks
            # up the new choice on its next call, and so the bid-info
            # window's system banner is refreshed. Per-pair overrides
            # are stored alongside so a teaching session can run e.g.
            # Precision90M at NS and SAYC at EW — when both pairs
            # share a system we clear the overrides to keep the
            # stored config tidy.
            try:
                cm = get_config_manager()
                cm.config.preferences.native_bidding_system = new_system
                ns_sys = self._ns_bidding_system or new_system
                ew_sys = self._ew_bidding_system or new_system
                if ns_sys == ew_sys:
                    cm.config.preferences.ns_bidding_system = ""
                    cm.config.preferences.ew_bidding_system = ""
                else:
                    cm.config.preferences.ns_bidding_system = ns_sys
                    cm.config.preferences.ew_bidding_system = ew_sys
                cm.save_preferences()
            except Exception:
                pass
            # Drop the cached BiddingSystem so the bid-info window
            # repaints with the new system on its next refresh.
            self._refresh_active_system()

            # Apply the bidding system to the engine
            self.status_label.setText(f"Setting bidding system: {new_system}...")
            QApplication.processEvents()

            if self.engine.set_bidding_system(new_system):
                # Show N/S and E/W systems in status bar
                ns_sys = self._ns_bidding_system
                ew_sys = self._ew_bidding_system
                if ns_sys == ew_sys:
                    self.status_label.setText(f"Bidding system: {new_system}")
                else:
                    self.status_label.setText(f"Systems: N/S={ns_sys}, E/W={ew_sys}")
            else:
                self.status_label.setText(f"Failed to set bidding system")

    def _on_preferences(self):
        """Show preferences dialog"""
        dialog = PreferencesDialog(self)
        # Connect signal for Apply button (refreshes colors while dialog is open)
        dialog.settings_applied.connect(self._refresh_suit_colors)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Also refresh on OK
            self._refresh_suit_colors()

    def _refresh_suit_colors(self):
        """Refresh UI elements after preference change."""
        # Refresh bidding box colors for 4-color suit mode changes
        self.bidding_box.refresh_colors()
        # Also refresh table view if it has the method
        if hasattr(self.table_view, 'refresh_colors'):
            self.table_view.refresh_colors()
        # Update analysis panel visibility based on preference
        self.analysis_label.setVisible(self.config_manager.config.preferences.show_ben_bid_analysis)
        # Bidding-system selection may have changed — re-tag the
        # information-about-bids window with the new system's labels.
        self._refresh_active_system()

    def _on_show_all_hands(self):
        """Toggle showing all hands"""
        for seat in Seat:
            self.table_view.set_hand_visible(seat, True)

    def _on_toggle_bid_info(self, checked: bool):
        """Toggle bidding information window"""
        if checked:
            self.bid_info_dock.show()
        else:
            self.bid_info_dock.hide()

    def _active_bidding_system(self, side: str = None):
        """Resolve the configured `BiddingSystem` spec.

        When ``side`` is 'NS' or 'EW', return the per-pair override
        (or the shared default if no override is set). Cached
        independently per side; `_refresh_active_system` clears
        every cache so a user-driven switch lands the next time the
        bid-info window is redrawn.
        """
        if not hasattr(self, '_cached_bidding_systems'):
            self._cached_bidding_systems = {}
        key = side or 'default'
        cached = self._cached_bidding_systems.get(key)
        if cached is not None:
            return cached
        try:
            from ben_backend.bid_descriptions import system_for_prefs
            prefs = get_config_manager().config.preferences
            spec = system_for_prefs(prefs, side=side)
        except Exception:
            from ben_backend.bidding_systems import get_system
            spec = get_system('SAYC')
        self._cached_bidding_systems[key] = spec
        return spec

    def _refresh_active_system(self):
        """Drop the cached system specs; next access reloads from prefs."""
        self._cached_bidding_systems = {}
        # If the bid info window is up, refresh the header + table.
        if getattr(self, 'bid_info_dock', None) is not None:
            self._refresh_bid_info_system_label()
            try:
                self._refresh_bid_history_descriptions()
            except Exception:
                pass
            self._update_available_bids()

    @staticmethod
    def _format_system_summary(spec) -> str:
        """One-paragraph description of a BiddingSystem spec for the
        Claude hint prompt — pulls numeric ranges straight from the
        dataclass fields so Precision-70's 13-15 1NT comes through
        when the user is on that variant, not the SAYC 15-17.
        """
        if spec.strong_open_call == "1C":
            return (
                f"strong-club: 1♣ = {spec.strong_open_min_hcp}+ any shape; "
                f"1♦ = {spec.one_diamond_min_hcp}-"
                f"{spec.one_diamond_max_hcp} (catch-all); 1♥/1♠ = "
                f"{spec.precision_two_clubs_min_hcp}-"
                f"{spec.one_nt_max_hcp} with 5+ in the suit; "
                f"1NT = {spec.one_nt_min_hcp}-"
                f"{spec.one_nt_max_hcp} balanced; "
                f"2♣ = {spec.precision_two_clubs_min_hcp}-"
                f"{spec.precision_two_clubs_max_hcp} with 6+ clubs; "
                f"2♦ = Precision three-suiter "
                f"({spec.precision_two_diamonds_shape}); "
                f"2♥/2♠ = weak two; 1♣-1♦ = 0-7 negative; positive "
                f"responses 8+ HCP; RKC = {spec.rkc_variant}"
            )
        return (
            f"5-card majors; strong 1NT {spec.one_nt_min_hcp}-"
            f"{spec.one_nt_max_hcp} balanced; "
            f"2NT {spec.two_nt_min_hcp}-{spec.two_nt_max_hcp} balanced; "
            f"2♣ Stayman; Jacoby transfers; weak 2♦/2♥/2♠ "
            f"({spec.weak_two_min_hcp}-{spec.weak_two_max_hcp}); "
            f"strong 2♣ = {spec.strong_open_min_hcp}+ HCP; "
            f"2/1 ≥ {spec.two_over_one_min_hcp}; "
            f"Blackwood 4NT for aces; negative doubles through 2♠; "
            f"standard takeout doubles; RKC = {spec.rkc_variant}"
        )

    def _refresh_bid_info_system_label(self):
        """Update the bid-info window's system header to match prefs.

        Shows ONE line when both pairs share the system, two lines
        ("NS: …" / "EW: …") otherwise — matches the dialog's "N/S vs
        E/W" tab so users can verify both sides at a glance.
        """
        lbl = getattr(self, 'bid_info_system_label', None)
        if lbl is None:
            return
        ns = self._active_bidding_system('NS')
        ew = self._active_bidding_system('EW')
        if ns.name == ew.name:
            desc = ns.description or ns.name
            lbl.setText(f"System: {ns.name} — {desc}")
        else:
            ns_desc = ns.description or ns.name
            ew_desc = ew.description or ew.name
            lbl.setText(
                f"NS: {ns.name} — {ns_desc}\n"
                f"EW: {ew.name} — {ew_desc}"
            )

    def _get_bid_interpretation(self, bid: Bid, auction: List[Bid], bidder: Seat) -> tuple:
        """Get point range and meaning for a bid based on context.
        Returns (points_str, suit_length_str, help_text, is_artificial).

        Delegates to `ben_backend.bid_descriptions.describe_bid`, which
        reads the active `BiddingSystem` spec so labels reflect the
        user's chosen system (SAYC / Precision / Acol / 2-over-1 / …).
        """
        try:
            from ben_backend.bid_descriptions import describe_bid
            sys_ = self._active_bidding_system()
            dealer = (self.controller.board.dealer
                      if self.controller.board is not None
                      else Seat.NORTH)
            return describe_bid(bid, list(auction), bidder, dealer, sys_)
        except Exception:
            # Fall through to the legacy SAYC-hardcoded labels if the
            # spec-driven describer chokes for any reason.
            pass

        if bid.is_pass:
            # Pass after partner opened might be different from initial pass
            if len(auction) == 0:
                return ("0-11", "", "No opening values", False)
            # Check if it's a forcing pass situation or just weak
            has_opening = any(not b.is_pass and not b.is_double and not b.is_redouble for b in auction)
            if has_opening:
                return ("0-5", "", "Weak, no bid", False)
            return ("0-11", "", "Pass", False)

        if bid.is_double:
            # Check context - takeout or penalty
            last_suit_bid = None
            for b in reversed(auction):
                if not b.is_pass and not b.is_double and not b.is_redouble:
                    last_suit_bid = b
                    break
            if last_suit_bid and len(auction) <= 3:
                return ("12+", "3+ other suits", "Takeout double", False)
            return ("10+", "", "Penalty/Cooperative", False)

        if bid.is_redouble:
            return ("10+", "", "Strength, redouble", False)

        # Regular suit/NT bids
        level = bid.level
        suit = bid.suit

        # Opening bids
        if len(auction) == 0 or all(b.is_pass for b in auction):
            if level == 1:
                if suit == Suit.CLUBS:
                    return ("12-21", "♣ 3+", "1♣ opening, 3+ clubs", False)
                elif suit == Suit.DIAMONDS:
                    return ("12-21", "♦ 3+", "1♦ opening, 3+ diamonds", False)
                elif suit == Suit.HEARTS:
                    return ("12-21", "♥ 5+", "1♥ opening, 5+ hearts", False)
                elif suit == Suit.SPADES:
                    return ("12-21", "♠ 5+", "1♠ opening, 5+ spades", False)
                elif suit == Suit.NOTRUMP:
                    return ("15-17", "Balanced", "1NT opening, balanced", False)
            elif level == 2:
                if suit == Suit.CLUBS:
                    return ("22+", "Any", "Strong 2♣, game force", True)
                elif suit == Suit.NOTRUMP:
                    return ("20-21", "Balanced", "2NT opening", False)
                else:
                    sym = suit.symbol()
                    return ("5-10", f"{sym} 6+", f"Weak 2, 6+ {sym}", False)
            elif level == 3:
                sym = suit.symbol()
                return ("5-10", f"{sym} 7+", f"Preempt, 7+ {sym}", False)

        # Responses to 1-level openings
        opening_bid = None
        for b in auction:
            if not b.is_pass and not b.is_double and not b.is_redouble:
                opening_bid = b
                break

        if opening_bid and opening_bid.level == 1:
            # Responding to 1 of a suit
            if level == 1 and suit != Suit.NOTRUMP:
                sym = suit.symbol()
                return ("6+", f"{sym} 4+", f"New suit, 4+ {sym}", False)
            elif level == 1 and suit == Suit.NOTRUMP:
                return ("6-10", "Balanced", "1NT response", False)
            elif level == 2:
                if suit == opening_bid.suit:
                    return ("6-10", f"{suit.symbol()} 3+", "Simple raise", False)
                elif suit == Suit.NOTRUMP:
                    return ("11-12", "Balanced", "Invitational", False)
                else:
                    sym = suit.symbol()
                    return ("10+", f"{sym} 4+", f"New suit, game force", False)
            elif level == 3:
                if suit == opening_bid.suit:
                    return ("10-12", f"{suit.symbol()} 4+", "Limit raise", False)

        # Check for Stayman (2♣ over 1NT)
        if bid.level == 2 and bid.suit == Suit.CLUBS:
            for i, b in enumerate(auction):
                if b.level == 1 and b.suit == Suit.NOTRUMP:
                    return ("8+", "4+ major", "Stayman, asks for 4-card major", True)

        # Check for Jacoby transfers (2♦/2♥ over 1NT)
        if bid.level == 2 and bid.suit in (Suit.DIAMONDS, Suit.HEARTS):
            for b in auction:
                if b.level == 1 and b.suit == Suit.NOTRUMP:
                    if bid.suit == Suit.DIAMONDS:
                        return ("0+", "♥ 5+", "Transfer to hearts", True)
                    elif bid.suit == Suit.HEARTS:
                        return ("0+", "♠ 5+", "Transfer to spades", True)

        # Default interpretation
        sym = suit.symbol() if suit != Suit.NOTRUMP else "NT"
        if suit == Suit.NOTRUMP:
            pts = f"{10 + level * 3}-{12 + level * 3}"
            return (pts, "Balanced", f"{level}NT bid", False)
        else:
            pts = f"{8 + level * 2}+"
            length = "4+" if level <= 2 else "5+"
            return (pts, f"{sym} {length}", f"{level}{sym} bid", False)

    def _add_bid_to_info(self, seat: Seat, bid: Bid, points_est: str = "", help_text: str = ""):
        """Add a bid to the info window history"""
        # Get interpretation if not provided
        if not points_est and not help_text:
            auction_before = self.controller.board.auction[:-1] if self.controller.board else []
            points_est, suit_len, help_text, is_artificial = self._get_bid_interpretation(bid, auction_before, seat)
            if suit_len:
                points_est = f"{points_est}  {suit_len}"

        row_frame = QFrame()
        row_frame.setStyleSheet("background-color: #fff; border-bottom: 1px solid #ddd;")
        row_layout = QHBoxLayout(row_frame)
        row_layout.setContentsMargins(5, 3, 5, 3)
        row_layout.setSpacing(0)

        # Bid column: "E: 1♥" style
        bid_text = f"{seat.to_char()}: {bid.symbol()}"
        bid_lbl = QLabel(bid_text)
        bid_lbl.setFont(QFont("Arial", 14))
        bid_lbl.setFixedWidth(100)
        if hasattr(bid, 'suit') and bid.suit is not None:
            from .styles import get_suit_color
            suit_names = {Suit.SPADES: 'spades', Suit.HEARTS: 'hearts',
                         Suit.DIAMONDS: 'diamonds', Suit.CLUBS: 'clubs'}
            color = get_suit_color(suit_names.get(bid.suit, 'spades'))
            bid_lbl.setStyleSheet(f"color: {color};")
        row_layout.addWidget(bid_lbl)

        # Points column
        pts_lbl = QLabel(points_est if points_est else "-")
        pts_lbl.setFont(QFont("Arial", 14))
        pts_lbl.setFixedWidth(100)
        row_layout.addWidget(pts_lbl)

        # Help column
        help_lbl = QLabel(help_text if help_text else "-")
        help_lbl.setFont(QFont("Arial", 14))
        help_lbl.setWordWrap(True)
        row_layout.addWidget(help_lbl, stretch=1)

        # Insert before the stretch
        self.bid_history_layout.insertWidget(self.bid_history_layout.count() - 1, row_frame)

    def _update_available_bids(self):
        """Update the list of available bids with meanings for the next bidder.

        The label and the interpretation queries both use the actual
        next-to-bid seat (computed from `board.get_current_bidder()`),
        so the meanings reflect what each bid would mean *for the seat
        that is about to bid* — that matters because partner-side
        conventional responses differ from overcalls of the same call.
        """
        # Clear existing
        while self.available_bids_layout.count():
            item = self.available_bids_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.controller.board:
            lbl = QLabel("-")
            lbl.setFont(QFont("Arial", 10))
            self.available_bids_layout.addWidget(lbl)
            return

        if self.controller.current_phase != 'bidding':
            lbl = QLabel("Bidding complete")
            lbl.setFont(QFont("Arial", 10))
            self.available_bids_layout.addWidget(lbl)
            return

        # Get current auction state
        auction = self.controller.board.auction
        try:
            next_seat = self.controller.board.get_current_bidder()
        except Exception:
            next_seat = Seat.SOUTH
        if getattr(self, 'avail_label', None) is not None:
            self.avail_label.setText(f"Available bids for {next_seat.name.title()}:")
        min_level = 0
        min_suit_idx = -1
        suit_order = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES, Suit.NOTRUMP]

        # Check for doubles available
        can_double = False
        can_redouble = False
        last_non_pass = None
        passes_after_last = 0

        for bid in reversed(auction):
            if bid.is_pass:
                passes_after_last += 1
            elif bid.is_double:
                can_redouble = passes_after_last < 2
                break
            elif bid.is_redouble:
                break
            else:
                last_non_pass = bid
                can_double = passes_after_last < 2
                break

        # Find minimum valid bid
        for bid in auction:
            if not bid.is_pass and not bid.is_double and not bid.is_redouble:
                min_level = bid.level
                min_suit_idx = suit_order.index(bid.suit)

        # Build list of available bids with meanings
        available_bids = []

        # Pass is always available
        pts, suit_len, help_txt, _ = self._get_bid_interpretation(Bid.make_pass(), auction, next_seat)
        available_bids.append(("Pass", pts, help_txt))

        # Double if available
        if can_double:
            pts, suit_len, help_txt, _ = self._get_bid_interpretation(Bid.make_double(), auction, next_seat)
            available_bids.append(("X", pts, help_txt))

        # Redouble if available
        if can_redouble:
            pts, suit_len, help_txt, _ = self._get_bid_interpretation(Bid.make_redouble(), auction, next_seat)
            available_bids.append(("XX", pts, help_txt))

        # Suit bids - show the next few levels
        count = 0
        for level in range(1, 8):
            for suit in suit_order:
                suit_idx = suit_order.index(suit)
                if level > min_level or (level == min_level and suit_idx > min_suit_idx):
                    bid = Bid(level=level, suit=suit)
                    pts, suit_len, help_txt, is_art = self._get_bid_interpretation(bid, auction, next_seat)
                    bid_str = bid.symbol()
                    display_pts = f"{pts}  {suit_len}" if suit_len else pts
                    if is_art:
                        help_txt = f"[Art] {help_txt}"
                    available_bids.append((bid_str, display_pts, help_txt))
                    count += 1
                    if count >= 12:  # Limit display
                        break
            if count >= 12:
                break

        # Display bids
        for bid_str, pts, help_txt in available_bids:
            row = QHBoxLayout()
            row.setSpacing(5)

            bid_lbl = QLabel(bid_str)
            bid_lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            bid_lbl.setFixedWidth(60)
            # Color suits using centralized colors
            from .styles import get_suit_color
            if '♠' in bid_str:
                bid_lbl.setStyleSheet(f"color: {get_suit_color('spades')};")
            elif '♥' in bid_str:
                bid_lbl.setStyleSheet(f"color: {get_suit_color('hearts')};")
            elif '♦' in bid_str:
                bid_lbl.setStyleSheet(f"color: {get_suit_color('diamonds')};")
            elif '♣' in bid_str:
                bid_lbl.setStyleSheet(f"color: {get_suit_color('clubs')};")
            row.addWidget(bid_lbl)

            pts_lbl = QLabel(pts)
            pts_lbl.setFont(QFont("Arial", 13))
            pts_lbl.setFixedWidth(110)
            row.addWidget(pts_lbl)

            help_lbl = QLabel(help_txt)
            help_lbl.setFont(QFont("Arial", 13))
            help_lbl.setWordWrap(True)
            row.addWidget(help_lbl, stretch=1)

            row_widget = QWidget()
            row_widget.setLayout(row)
            self.available_bids_layout.addWidget(row_widget)

    def _clear_bid_info(self):
        """Clear the bid info window"""
        while self.bid_history_layout.count() > 1:
            item = self.bid_history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Clear available bids - don't call _update_available_bids here to avoid issues
        while self.available_bids_layout.count():
            item = self.available_bids_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_bid_history_descriptions(self):
        """Rebuild the bid-history rows using the active bidding system.

        Used when the user switches bidding system mid-auction: the
        existing rows were rendered with the old labels and need to be
        retagged with what each bid means under the new system.
        """
        if self.controller.board is None:
            return
        # Wipe the history layout but keep the trailing stretch.
        while self.bid_history_layout.count() > 1:
            item = self.bid_history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        auction = list(self.controller.board.auction)
        dealer = self.controller.board.dealer
        bidder = dealer
        for b in auction:
            self._add_bid_to_info(bidder, b, "", "")
            bidder = bidder.next()

    def _on_show_scores(self):
        """Show score table.

        Shown non-modally (`show()` not `exec()`): a modal dialog blocks
        the main thread's QTcpSocket readyRead processing on both host
        and guest, so heartbeats stop arriving and the connection times
        out. Keep a reference on `self` so the dialog isn't garbage-
        collected as soon as we return.

        If a teams match is active, shows the TeamsScoreDialog with
        clickable contracts to view replays. Otherwise shows the
        regular ScoringTableDialog.
        """
        if self.teams_match is not None:
            self._scores_dialog = TeamsScoreDialog(self.teams_match, self)
            self._scores_dialog.contract_clicked.connect(self._on_replay_board)
        else:
            self._scores_dialog = ScoringTableDialog(self.scoring_table, self)
        self._scores_dialog.show()
        self._scores_dialog.raise_()

    def _on_dd_analysis(self):
        """Run double dummy analysis"""
        if not self.controller.board:
            self.status_label.setText("No deal loaded - press Ctrl+N for new deal")
            return

        # Check if all hands are available
        board = self.controller.board
        missing_hands = []
        for seat_char in ['N', 'E', 'S', 'W']:
            from ben_backend.models import Seat
            seat = Seat.from_char(seat_char)
            if seat not in board.hands or not board.hands[seat].cards:
                missing_hands.append(seat_char)

        if missing_hands:
            self.status_label.setText(f"DD analysis requires all hands (missing: {', '.join(missing_hands)})")
            return

        self.status_label.setText("Running double dummy analysis...")
        QApplication.processEvents()

        try:
            results = self.engine.analyze_double_dummy(board)

            if results:
                # Format for display panel (right side)
                panel_text = "Double Dummy\nAnalysis:\n\n"
                panel_text += "    NT  S  H  D  C\n"
                for seat in ['N', 'E', 'S', 'W']:
                    panel_text += f"{seat}:  "
                    for strain in ['NT', 'S', 'H', 'D', 'C']:
                        tricks = results.get(seat, {}).get(strain, '-')
                        panel_text += f"{tricks:>2} "
                    panel_text += "\n"

                self.analysis_label.setText(panel_text)
                self.status_label.setText("Double dummy analysis complete")

                # Create a proper table dialog
                from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QDialogButtonBox
                from PyQt6.QtCore import Qt
                from .dialogs.dialog_style import apply_dialog_style

                dialog = QDialog(self)
                dialog.setWindowTitle("Double Dummy Analysis")
                dialog.setMinimumWidth(350)
                apply_dialog_style(dialog)

                layout = QVBoxLayout(dialog)

                # Create table widget
                table = QTableWidget(4, 5)  # 4 rows (N,E,S,W), 5 columns (NT,S,H,D,C)
                table.setHorizontalHeaderLabels(['NT', '♠', '♥', '♦', '♣'])
                table.setVerticalHeaderLabels(['North', 'East', 'South', 'West'])
                table.setStyleSheet("""
                    QTableWidget {
                        background-color: #ffffff;
                        color: #000000;
                        gridline-color: #c0c0c0;
                        font-size: 14px;
                    }
                    QTableWidget::item {
                        padding: 8px;
                        text-align: center;
                    }
                    QHeaderView::section {
                        background-color: #e0e0e0;
                        color: #000000;
                        padding: 6px;
                        font-weight: bold;
                        border: 1px solid #c0c0c0;
                    }
                """)

                # Populate table
                seat_list = ['N', 'E', 'S', 'W']
                strain_list = ['NT', 'S', 'H', 'D', 'C']
                for row, seat in enumerate(seat_list):
                    for col, strain in enumerate(strain_list):
                        tricks = results.get(seat, {}).get(strain, '-')
                        item = QTableWidgetItem(str(tricks))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        table.setItem(row, col, item)

                table.resizeColumnsToContents()
                table.resizeRowsToContents()
                layout.addWidget(table)

                # OK button
                buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
                buttons.accepted.connect(dialog.accept)
                buttons.setStyleSheet("QPushButton { background-color: #e0e0e0; color: #000000; padding: 6px 20px; }")
                layout.addWidget(buttons)

                dialog.exec()
            else:
                self.status_label.setText("DD analysis returned no results - check engine")
        except Exception as e:
            self.status_label.setText(f"DD analysis error: {str(e)[:50]}")
            import traceback
            traceback.print_exc()

    def _on_simulation(self):
        """Show bid simulation dialog"""
        if not self.controller.board:
            QMessageBox.warning(self, "No Board",
                              "Please start a new deal first.")
            return

        if self.controller.current_phase != 'bidding':
            QMessageBox.warning(self, "Not Bidding",
                              "Simulation is only available during bidding.")
            return

        dialog = SimulationDialog(
            self.engine, self.controller.board,
            self.controller.current_seat, self
        )
        dialog.exec()

    def _on_show_imp_table(self):
        """Show IMP conversion table — detached so it can sit on a
        second monitor for reference while play continues."""
        self._imp_dialog = IMPTableDialog(self)
        self._show_detached(self._imp_dialog)

    def _on_show_probabilities(self):
        """Show probabilities table (detached)."""
        self._prob_dialog = ProbabilitiesDialog(self)
        self._show_detached(self._prob_dialog)

    def _on_show_scoring_reference(self):
        """Show scoring reference tables (detached)."""
        self._scoring_ref_dialog = ScoringReferenceDialog(self)
        self._show_detached(self._scoring_ref_dialog)

    def _show_detached(self, dialog):
        """Promote `dialog` to a free-floating top-level window and
        show it non-modally. Use for read-only / reference dialogs
        that benefit from sitting on a second monitor next to the
        main table view. Settings dialogs and anything that returns
        a value via exec() should *not* go through this path."""
        from .dialogs.dialog_style import make_detachable
        make_detachable(dialog)
        dialog.show()
        dialog.raise_()

    def _on_about(self):
        """Show about dialog with a light background.

        QMessageBox.about() inherits the parent window's stylesheet,
        which on the table view is dark blue — that left the body text
        unreadable against the same blue tone. Construct the message
        box explicitly and apply a light-grey palette so the text
        always reads at full contrast regardless of which window we
        descend from.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("About BEN Bridge")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<h2 style='margin:0'>BEN Bridge</h2>"
            "<p>A bridge playing and analysis application "
            "powered by the BEN neural network engine.</p>"
            "<p>Classic desktop Bridge interface.</p>"
            "<p><b>Engine:</b> BEN v0.8.7.4<br>"
            "<b>UI:</b> PyQt6</p>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet(
            "QMessageBox { background-color: #f0f0f0; }"
            "QMessageBox QLabel { color: #000; background-color: transparent;"
            " font-size: 14px; min-width: 380px; padding: 4px; }"
            "QMessageBox QPushButton { background-color: #e0e0e0;"
            " color: #000; border: 1px solid #999; padding: 6px 18px;"
            " border-radius: 3px; min-width: 80px; }"
            "QMessageBox QPushButton:hover { background-color: #d0d0d0; }"
        )
        msg.exec()

    # Network menu handlers

    def _on_start_server(self):
        """Show start server dialog and start hosting."""
        if self.network_controller.is_active:
            from .dialogs.dialog_style import styled_warning
            styled_warning(
                self, "Already Connected",
                "You are already in a network game. Disconnect first."
            )
            return

        dialog = StartServerDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()
            if self.network_controller.start_server(
                settings['port'],
                settings['name'],
                settings['seat']
            ):
                self.status_label.setText(
                    f"Server started on port {settings['port']}. Waiting for players..."
                )
                # Open the persistent lobby. It stays open while guests
                # connect, auto-accepts when 4 seats are filled, and gives
                # the host a Start Game button to begin early.
                self._open_host_lobby(settings)
            else:
                from .dialogs.dialog_style import styled_warning
                styled_warning(
                    self, "Server Error",
                    "Failed to start server. Check if the port is available."
                )

    def _open_host_lobby(self, settings: dict):
        """Show the host lobby and wire its signals back to the controller."""
        # Pull the same IP list the StartServerDialog showed so the host
        # has it handy while waiting for guests.
        from PyQt6.QtNetwork import QNetworkInterface, QAbstractSocket
        ip_addresses = []
        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if not (flags & QNetworkInterface.InterfaceFlag.IsUp):
                continue
            if flags & QNetworkInterface.InterfaceFlag.IsLoopBack:
                continue
            for entry in iface.addressEntries():
                ip = entry.ip()
                if ip.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                    ip_addresses.append(ip.toString())

        self._lobby_dialog = NetworkLobbyDialog(
            host_name=settings['name'],
            host_seat=settings['seat'],
            port=settings['port'],
            ip_addresses=ip_addresses,
            parent=self,
        )
        self._lobby_dialog.start_game_requested.connect(self._on_lobby_start_clicked)
        # Tear down the server if the host cancels the lobby.
        self._lobby_dialog.rejected.connect(self._on_lobby_cancelled)
        # Seed the board with the host already seated.
        self._lobby_dialog.update_seat_map(self.network_controller.current_seat_map())
        self._lobby_dialog.show()

    def _on_lobby_start_clicked(self):
        """Host has clicked Start Game (or the lobby auto-filled)."""
        self._lobby_dialog = None
        self.network_controller.start_game()
        # Mirror the previous "first guest auto-deals" behaviour, but now
        # gated by the host explicitly closing the lobby.
        QTimer.singleShot(200, self._start_network_game)

    def _on_lobby_cancelled(self):
        """Host cancelled the lobby before starting — stop the server."""
        self._lobby_dialog = None
        if self.network_controller.is_active:
            self.network_controller.disconnect()
        self.status_label.setText("Lobby cancelled. Server stopped.")

    def _on_connect_server(self):
        """Show connect dialog and connect to a server."""
        if self.network_controller.is_active:
            from .dialogs.dialog_style import styled_warning
            styled_warning(
                self, "Already Connected",
                "You are already in a network game. Disconnect first."
            )
            return

        self._connect_dialog = ConnectServerDialog(self)
        self._connect_dialog.connect_requested.connect(self._do_connect_to_server)
        self._connect_dialog.seat_clicked.connect(self._on_lobby_seat_clicked)
        self._connect_dialog.show()

    def _do_connect_to_server(self, host: str, port: int, name: str):
        """Open the socket. The seat is claimed later from the lobby
        seat board via _on_lobby_seat_clicked → request_seat."""
        self.network_controller.connect_to_server(host, port, name,
                                                   requested_seat="")

    def _on_lobby_seat_clicked(self, seat: Seat):
        """Forward the guest's seat click to the server as SEAT_REQUEST."""
        self.network_controller.request_seat(seat.to_char())

    def _on_network_disconnect(self):
        """Disconnect from network game."""
        if self.network_controller.is_active:
            self.network_controller.disconnect()
            self.disconnect_action.setEnabled(False)
            self.status_label.setText("Disconnected from network game")
            # Revert to single-player mode
            self._configure_single_player()
            self._refresh_qplus_ingest_action_state()

    def _on_network_connected(self, mode: str, my_seat: str, partner_seat: str, client_role: str):
        """Handle successful network connection."""
        self.disconnect_action.setEnabled(True)
        self._refresh_qplus_ingest_action_state()

        seat = Seat.from_char(my_seat)
        partner = Seat.from_char(partner_seat)

        # Remember the seat the user actually claimed so disconnect
        # recovery doesn't drop them back to South.
        self._user_seat = seat

        # Guest mode: keep the connect dialog open in lobby mode so the
        # guest can see the live seat board until the host starts the
        # game. The dialog dismisses itself on GAME_START.
        connect = getattr(self, '_connect_dialog', None)
        if mode == "client" and connect is not None:
            connect.enter_lobby(seat)

        # Rotate the table view so the local user's seat is at the bottom.
        # Single-player keeps the default (South); a guest at E/N/W now sees
        # their own hand at the bottom of the screen.
        self.table_view.set_local_seat(seat)

        # Configure players for network mode
        self._configure_network_players()

        # Build status message based on role
        role_desc = "partner" if client_role == "partner" else "opponent"
        if mode == "server":
            status = f"Hosting game. You play {my_seat}/{partner_seat}. Waiting for {role_desc} to connect..."
        else:
            status = f"Connected as {role_desc}! You play {my_seat}/{partner_seat}. Ready to play!"

        self.status_label.setText(status)

        # Update window title
        mode_str = "Host" if mode == "server" else f"Guest ({role_desc})"
        self.setWindowTitle(f"BEN Bridge - LAN Game ({mode_str}: {my_seat}/{partner_seat})")

    def _on_network_client_joined(self, client_name: str, client_role: str):
        """Handle client joining (server mode).

        While the lobby is on screen, do nothing destructive — the host will
        click Start Game (or auto-accept fires when 4 seats fill) which then
        triggers _start_network_game. After the game has begun, late joiners
        receive the current deal state instead of a fresh deal.
        """
        role_desc = "as your partner" if client_role == "partner" else "as your opponent"
        self.status_label.setText(
            f"'{client_name}' has joined {role_desc}!"
        )
        self._configure_network_players()

        # Lobby still open → wait for host's Start Game click.
        if getattr(self, '_lobby_dialog', None) is not None:
            return

        already_in_progress = (
            self.controller.board is not None
            and self.controller.current_phase in ('bidding', 'play', 'waiting_next')
        )
        if already_in_progress:
            # Late joiner — push the current deal state so they can follow along.
            self.network_controller.broadcast_deal(self.controller.board)
            # Seat is an IntEnum (NORTH == 0); use explicit None check or
            # a North dummy would be skipped on every late-joiner push.
            if (self.controller.dummy is not None
                    and self.controller.current_phase != 'bidding'):
                dummy_hand = self.controller.board.hands.get(self.controller.dummy)
                if dummy_hand is not None and dummy_hand.cards:
                    self.network_controller.broadcast_dummy_reveal(
                        self.controller.dummy, dummy_hand)
        else:
            QTimer.singleShot(500, self._start_network_game)

    def _on_network_seat_map(self, seats: dict):
        """Live seat-occupancy update from the server. Routes to whichever
        lobby/seat-picker dialog is currently visible."""
        lobby = getattr(self, '_lobby_dialog', None)
        if lobby is not None:
            lobby.update_seat_map(seats)
        connect = getattr(self, '_connect_dialog', None)
        if connect is not None:
            my_seat = self.network_controller.my_seat
            connect.update_seat_map(
                seats,
                host_seat=self.network_controller.host_seat_char(),
                my_seat=my_seat,
            )
            # First SEAT_LIST after a successful socket connect signals
            # "lobby join confirmed" — switch from the form page to the
            # live seat board so the user can pick a seat.
            if connect._stack.currentIndex() == 0:
                connect.set_connecting(False)
                connect.enter_lobby(my_seat)

    def _on_network_seat_rejected(self, reason: str):
        """Server rejected the guest's SEAT_REQUEST as taken. Surface the
        error inline on the lobby seat board without closing the socket."""
        connect = getattr(self, '_connect_dialog', None)
        if connect is not None:
            connect.show_seat_taken_error(reason)
            connect.show_lobby_status("Pick another seat.")

    def _on_network_game_starting(self):
        """Host has broadcast GAME_START (or our own host-side equivalent).
        Close the guest's lobby view and let the deal flow take over."""
        connect = getattr(self, '_connect_dialog', None)
        if connect is not None:
            try:
                connect.accept()
            except Exception:
                pass
            self._connect_dialog = None

    def _on_network_server_started(self, port: int):
        """Handle server start confirmation."""
        self.disconnect_action.setEnabled(True)
        self._refresh_qplus_ingest_action_state()

    def _on_network_disconnected(self, reason: str):
        """Handle network disconnection.

        Two very different cases share this signal:

        * Server mode — a guest dropped. The host stays hosting, BEN
          takes over the freed seat(s) automatically because
          _configure_network_players reads from the live remote_seats
          list. Don't tear down the rotation or revert to South.
        * Client mode — we lost the host. Keep the user at their current
          seat, fill every other seat with BEN locally so the user can
          finish the hand offline, and clean up the controller state so
          the disconnect button reflects "no network game".
        """
        from .dialogs.dialog_style import styled_info

        if self.network_controller.is_server:
            # A guest left. Refresh player ownership; AI now controls the
            # freed seat. Do not exit network mode.
            self._configure_network_players()
            self.status_label.setText(
                f"Guest disconnected ({reason}); BEN now controls the freed seat."
            )
            # If we were mid-hand waiting on the (now-departed) guest's
            # turn, kick the engine so BEN takes over and play resumes
            # instead of stalling on "Waiting for partner…".
            if self.controller.current_phase in ('bidding', 'play', 'waiting_next'):
                self._advance_game()
            return

        # Client mode: keep playing locally with BEN as every other seat.
        # Prefer the canonical _user_seat (set when the guest claimed
        # their seat) over the controller's possibly-cleared field.
        # NOTE: Seat is an IntEnum where NORTH == 0; bare truthiness chains
        # would silently skip a North-seated guest, so test for None.
        my_seat = self._user_seat
        if my_seat is None:
            my_seat = self.network_controller.my_seat
        if my_seat is None:
            my_seat = Seat.SOUTH
        self.disconnect_action.setEnabled(False)
        styled_info(
            self, "Host Disconnected",
            f"Lost connection to the host ({reason}). "
            f"BEN will take over the other three seats so you can finish the hand."
        )
        # Drop the network controller back to idle so other code paths
        # (next-deal, hint, save) treat us as offline again.
        try:
            self.network_controller.disconnect()
        except Exception:
            pass
        # Local takeover: only the user's seat is human; the rest are AI.
        for seat in Seat:
            if seat == my_seat:
                self.controller.players[seat].player_type = PlayerType.HUMAN
            else:
                self.controller.players[seat].player_type = PlayerType.COMPUTER
        # Keep the rotation so the user's hand stays at the bottom.
        self.table_view.set_local_seat(my_seat)
        self.setWindowTitle(f"BEN Bridge (offline — {my_seat.to_char()})")
        self.status_label.setText(
            f"Host disconnected; you are now playing offline as {my_seat.to_char()}."
        )
        # Re-enable Next-card / Hint / engine flow now that we're in
        # local single-player mode. Without this the toolbar buttons
        # stay disabled in whatever state they had at the moment the
        # host dropped, and the user has no way to finish the hand.
        self.next_card_btn.setEnabled(False)  # cleared; _advance_play will set as needed
        self.bidding_box.set_enabled(False)
        if self.controller.current_phase in ('bidding', 'play', 'waiting_next'):
            self._advance_game()
        # Hint refresh follows the regular path inside _advance_game; if
        # nothing advanced (e.g. board not started), make sure Hint is at
        # least correctly disabled.
        self._refresh_hint_button_state()

    def _on_network_deal_received(self, board: BoardState):
        """Handle receiving a deal from the server (client mode)."""
        self.controller.board = board
        self.controller.current_phase = 'bidding'
        self.controller.current_seat = board.dealer

        # DIAGNOSTIC — surface enough to debug "guest sees no cards":
        # which seat the local user is at, what cards arrived per seat,
        # and which physical widget will end up showing the local hand.
        try:
            my_seat = self.network_controller.my_seat
            print(f"[net deal] my_seat={my_seat.to_char() if my_seat is not None else None}, "
                  f"dealer={board.dealer.to_char()}, "
                  f"table_view._local_seat={self.table_view._local_seat.to_char()}, "
                  f"rotation_quarters={self.table_view._rotation_quarters}",
                  flush=True)
            for s in Seat:
                hand = board.hands.get(s)
                n = len(hand.cards) if hand else 0
                print(f"  hand[{s.to_char()}]: {n} cards", flush=True)
        except Exception as ex:
            print(f"[net deal] diagnostic failed: {ex}", flush=True)

        # If set_local_seat hasn't been applied (e.g. signal-ordering quirk),
        # apply it now so the bottom widget is the right one before set_board.
        try:
            ms = self.network_controller.my_seat
            if ms is not None and self.table_view._local_seat != ms:
                print(f"[net deal] late set_local_seat({ms.to_char()})", flush=True)
                self.table_view.set_local_seat(ms)
        except Exception:
            pass

        # Store original hands
        self.original_hands = {}
        for seat, hand in board.hands.items():
            if hand.cards:  # Only copy non-hidden hands
                self.original_hands[seat] = Hand(cards=list(hand.cards))

        # Setup UI
        self.table_view.set_board(board)
        self.bidding_box.clear()
        self.bidding_box.set_auction([], board.dealer)
        self.bidding_box.setVisible(True)
        self.right_panel.setVisible(True)
        self._clear_bid_info()
        self._update_available_bids()
        self._update_window_title()

        # Set visibility - show my hand and partner's hand
        for seat in Seat:
            visible = self.network_controller.is_my_seat(seat)
            self.table_view.set_hand_visible(seat, visible)

        if self.bid_info_action.isChecked():
            self.bid_info_dock.show()

        self._set_toolbar_mode('ingame')
        self._advance_game()

    def _on_network_remote_bid(self, seat_char: str, bid: Bid):
        """Handle receiving a bid from the remote player."""
        seat = Seat.from_char(seat_char)

        # Apply the bid
        self.controller.board.auction.append(bid)
        self.bidding_box.add_bid(bid)
        self.table_view.update_auction(self.controller.board.auction, self.controller.board.dealer)
        self._add_bid_to_info(seat, bid, "", "")

        # Check if auction complete
        if self.controller.board.is_auction_complete():
            if self.controller.board.is_passed_out():
                self.controller.current_phase = 'finished'
            else:
                self.controller._setup_play()
        else:
            self.controller.current_seat = self.controller.current_seat.next()

        self._advance_game()

    def _on_network_remote_card(self, seat_char: str, card: Card):
        """Handle receiving a card play from the remote player."""
        seat = Seat.from_char(seat_char)

        # Force current_seat to match the broadcasting player before
        # play_card removes the card from the right hand. Without this
        # the local controller would happily strip a card from whichever
        # seat it last advanced to, which drifts host vs guest after a
        # trick boundary or after an AI play arrived in unexpected order.
        if self.controller.board is not None:
            self.controller.current_seat = seat

        # Apply the card play
        self.table_view.play_card_to_trick(seat, card)
        self.controller.play_card(card)
        self._advance_game()

    def _on_network_dummy_revealed(self, dummy_seat: Seat, dummy_hand: Hand):
        """Handle receiving dummy's hand when play starts (client mode)."""
        # DIAGNOSTIC — track exactly when the guest's UI gets the dummy.
        try:
            n_cards = len(dummy_hand.cards) if dummy_hand else 0
            tv_decl = self.table_view.declarer
            print(
                f"[guest dummy_reveal] dummy_seat={dummy_seat.to_char()} "
                f"cards={n_cards} controller.dummy={self.controller.dummy} "
                f"table_view.declarer={tv_decl} "
                f"phase={self.controller.current_phase}",
                flush=True,
            )
        except Exception:
            pass
        # Update the board with dummy's actual hand
        self.controller.board.hands[dummy_seat] = dummy_hand
        # Show dummy's hand
        self.table_view.set_hand_visible(dummy_seat, True)
        # DIAGNOSTIC — confirm the widget got the cards.
        try:
            ds = self.table_view._display_seat(dummy_seat)
            w = self.table_view.hand_widgets[ds]
            print(
                f"[guest dummy_reveal] widget at physical {ds}: "
                f"visible={w.isVisible()} "
                f"hand_cards={len(w.hand.cards) if getattr(w, 'hand', None) else 0} "
                f"size={w.size().width()}x{w.size().height()}",
                flush=True,
            )
        except Exception as ex:
            print(f"[guest dummy_reveal] post-set diag failed: {ex}", flush=True)

    def _on_network_closed_room_ingested(self, run):
        """Guest received a manually-ingested closed-room run from the host.

        Attach it to the matching BoardResult (by pavlicek_id, falling back
        to board number) so the score sheet's Compare button lights up for
        the guest too.
        """
        try:
            self._attach_closed_room_run(run)
            self.status_label.setText(
                f"Closed room received from host (board {run.board_number})."
            )
        except Exception as e:
            print(f"[net closed_room_ingested] error: {e}", flush=True)

    def _on_network_error(self, error: str):
        """Handle network error."""
        from .dialogs.dialog_style import styled_warning
        styled_warning(self, "Network Error", error)
        if hasattr(self, '_connect_dialog') and self._connect_dialog:
            self._connect_dialog.show_error(error)

    def _on_network_trick_clear(self):
        """Handle receiving trick clear from remote player (they clicked 'next card').

        Clears the green-felt trick widgets unconditionally — leaving the
        previous trick on the felt while the next trick is laid on top is
        much worse than skipping a redundant controller advance when our
        phase has already moved on. Server fan-out to other guests is
        handled by `BridgeServer._relay_to_others`.
        """
        self.table_view.clear_trick()
        self.next_card_btn.setEnabled(False)

        if self.controller.current_phase == 'waiting_next':
            self.controller.advance_to_next_trick()
            self._advance_game()

    def _configure_network_players(self):
        """Configure player types for network play based on network controller state."""
        for seat in Seat:
            player_type = self.network_controller.get_player_type_for_seat(seat)
            self.controller.players[seat].player_type = player_type

    def _configure_single_player(self):
        """Revert to single-player mode (South-as-human, no rotation)."""
        for seat in Seat:
            if seat == Seat.SOUTH:
                self.controller.players[seat].player_type = PlayerType.HUMAN
            else:
                self.controller.players[seat].player_type = PlayerType.COMPUTER
        # Make sure the canonical user seat and the table rotation also
        # reset to the single-player default; otherwise a previous
        # network claim (e.g. North) lingers and the bottom widget keeps
        # showing the wrong hand on the next deal.
        self._user_seat = Seat.SOUTH
        self.table_view.set_local_seat(Seat.SOUTH)

    def _start_network_game(self):
        """Start a network game (server generates deal)."""
        if not self.network_controller.is_server:
            return

        if not self.engine.is_ready:
            QMessageBox.warning(self, "Engine Not Ready",
                              "The bridge engine is not yet initialized.")
            return

        # Generate a new deal
        board = self.controller.new_deal()

        # Store original hands
        self.original_hands = {}
        for seat, hand in board.hands.items():
            self.original_hands[seat] = Hand(cards=list(hand.cards))

        # Broadcast deal to client
        self.network_controller.broadcast_deal(board)

        # Setup UI
        self.table_view.set_board(board)
        self.bidding_box.clear()
        self.bidding_box.set_auction([], board.dealer)
        self.bidding_box.setVisible(True)
        self.right_panel.setVisible(True)
        self._clear_bid_info()
        self._update_available_bids()
        self._update_window_title()

        # Set visibility - show my hand and partner's hand
        for seat in Seat:
            visible = self.network_controller.is_my_seat(seat)
            self.table_view.set_hand_visible(seat, visible)

        if self.bid_info_action.isChecked():
            self.bid_info_dock.show()

        self._set_toolbar_mode('ingame')
        self.status_label.setText(f"Board {board.board_number}: {board.dealer.to_char()} deals")
        self._advance_game()

    def _is_waiting_for_remote(self) -> bool:
        """Check if we're waiting for the remote player to act."""
        if not self.network_controller.is_active:
            return False

        current_seat = self.controller.current_seat
        if current_seat is None:
            return False

        # We're waiting for remote if it's an opponent's turn
        return not self.network_controller.is_my_seat(current_seat)

    def _on_auto_play_toggle(self, checked: bool):
        """Toggle auto play mode"""
        if checked and self.controller.current_phase not in ('idle', 'finished'):
            self._advance_game()

    def _is_local_user_turn(self) -> bool:
        """True if the locally-controlled human is on lead right now.

        Network mode: maps `current_seat` through dummy → declarer (the
        declarer controls dummy's plays) and checks ownership against
        `is_my_seat`. Single-player: trusts the controller's flag, which
        already accounts for human-controls-declarer.
        """
        seat = self.controller.current_seat
        if seat is None:
            return False
        if self.network_controller.is_active:
            phase = self.controller.current_phase
            if phase == 'play':
                dummy = self.controller.dummy
                declarer = self.controller.declarer
                actual = declarer if (dummy is not None and seat == dummy
                                      and declarer is not None) else seat
                return self.network_controller.is_my_seat(actual)
            return self.network_controller.is_my_seat(seat)
        return self.controller.is_human_turn()

    def _on_hint(self):
        """Ask Claude what to do next, with a progress bar and result dialog.

        BEN's own engine suggestion is included in the prompt as context so
        Claude can agree, disagree, or explain it.
        """
        board = self.controller.board
        seat = self.controller.current_seat
        phase = self.controller.current_phase
        # Seat is an IntEnum (NORTH == 0); use explicit None checks.
        if board is None or seat is None or phase not in ('bidding', 'play'):
            return
        # Hint is only allowed when it's the local user's turn — otherwise
        # the prompt would expose the active seat's hand to whoever clicked
        # the button. Defense in depth: the toolbar button is also greyed
        # out off-turn (see _refresh_hint_button_state), but that can be
        # bypassed if the click lands while the state is stale.
        if not self._is_local_user_turn():
            self.status_label.setText(
                "Hint is only available when it's your turn."
            )
            return

        # BEN's TensorFlow bidder was trained on SAYC + 2-over-1 only —
        # it has no idea what Precision / Acol / French strong-club
        # responses look like, so its bid suggestion (and softmax
        # confidence score) is misleading at best when the table is
        # on any non-SAYC system. We DROP BEN entirely from the
        # bidding-phase hint and let Claude reason from the active
        # bidding system clauses in the prompt instead.
        #
        # Card play has no such bias — winners, finesses, ducks etc.
        # don't depend on the bidding system — so BEN's card-play
        # suggestion still shows up there. Score is its NN softmax
        # confidence (0–1).
        engine_text = ""
        try:
            if phase == 'play':
                # Skip BEN suggestion when we don't have the seat's hand
                # (guest in network mode only has its own + visible hands).
                hand = board.hands.get(seat)
                if hand and hand.cards:
                    trick_cards = board.current_trick.cards if board.current_trick else []
                    resp = self.engine.get_card_play(board, seat, trick_cards)
                    if resp and resp.action:
                        engine_text = f"BEN suggests: play {resp.action.to_str()}"
                        if resp.candidates:
                            cands = ", ".join(f"{c.card.to_str()} ({c.score:.2f})"
                                              for c in resp.candidates[:5])
                            engine_text += (
                                f"\nBEN candidates (score = TensorFlow NN "
                                f"confidence 0–1): {cands}"
                            )
        except Exception as e:
            engine_text = f"(BEN engine error: {e!r})"

        # Surface the active bidding systems at the top of the hint
        # dialog so the user knows which spec Claude is being told to
        # interpret each side's bids by. Two lines when NS / EW differ,
        # one when they share a system.
        system_preamble = ""
        try:
            ns_spec = self._active_bidding_system('NS')
            ew_spec = self._active_bidding_system('EW')
            if ns_spec.name == ew_spec.name:
                desc = ns_spec.description or ns_spec.name
                system_preamble = (
                    f"Bidding system: {ns_spec.name} — {desc}"
                )
            else:
                ns_d = ns_spec.description or ns_spec.name
                ew_d = ew_spec.description or ew_spec.name
                system_preamble = (
                    f"Bidding systems — NS: {ns_spec.name} ({ns_d}); "
                    f"EW: {ew_spec.name} ({ew_d})"
                )
        except Exception:
            pass

        state_text = self._build_hint_state_text(board, seat, phase)
        prompt = self._build_hint_prompt(phase, seat, state_text, engine_text)

        # Route the result through the BDL-with-annotations renderer so
        # Claude's reasoning lands inline next to the section it's
        # commenting on instead of in a free-floating text block. The
        # preamble shows the bidding system(s) in use AND BEN's
        # second-opinion line, so the user sees both before reading
        # Claude's analysis.
        preamble_parts = [p for p in (system_preamble, engine_text) if p]
        preamble_text = ("\n\n".join(preamble_parts) + "\n\n"
                         if preamble_parts else "")
        self._run_claude_with_dialog(
            prompt=prompt,
            title=f"Claude hint — {'bidding' if phase == 'bidding' else 'card play'}",
            wait_label=f"Claude is thinking about your {'bid' if phase == 'bidding' else 'card'}...",
            timeout_seconds=300,
            preamble=preamble_text,
            bdl_text=state_text,
        )

    def _build_hint_state_text(self, board, seat, phase) -> str:
        """Serialize the current board state for a Claude hint prompt as
        a partial BDL file. The BDL form keeps every bid, every card and
        every trick attached to a fixed N/E/S/W column or leader marker,
        which is the format Claude has the easiest time annotating
        without confusing who did what.
        """
        from .game_logger import build_bdl_snapshot

        # Dummy is visible to defenders only after the opening lead.
        # During bidding it never is. Use the table-view's reveal flag
        # (already accounts for human-side declarer).
        dummy_visible = (phase == 'play'
                         and getattr(self.table_view, 'dummy_revealed', True))

        # Mark the pavlicek deal id when we know the full hand layout —
        # gives Claude one more anchor when deciding which deal it is.
        deal_id = ""
        try:
            hands_for_pavlicek = self.original_hands or board.hands
            if all(s in hands_for_pavlicek for s in Seat):
                deal_id = format_deal_base72(deal_to_number(hands_for_pavlicek))
        except Exception:
            deal_id = ""

        # Hint dialog shows BDL + Claude annotations only — no footer
        # (Viewer / HCP / Phase) and no "Remaining cards" appendix. The
        # BDL block already encodes everything Claude needs (the seat
        # whose hand is shown is implicit, and remaining cards are
        # derivable from the Cards block + Tricks block).
        bdl = build_bdl_snapshot(
            board,
            original_hands=self.original_hands,
            viewer_seat=seat,
            phase=phase,
            dummy_visible_to_viewer=dummy_visible,
            deal_id=deal_id,
            current_seat=seat,
            include_footer=False,
        )
        return bdl

    def _build_hint_prompt(self, phase: str, seat, state_text: str, engine_text: str) -> str:
        """Assemble the Claude prompt for a hint query."""
        seat_names = {Seat.NORTH: 'N', Seat.EAST: 'E', Seat.SOUTH: 'S', Seat.WEST: 'W'}
        action = "bid" if phase == 'bidding' else "card to play"
        engine_block = f"\n\n{engine_text}" if engine_text else ""

        # During card play we want a full plan for the rest of the hand,
        # not just a one-card recommendation. The clause below makes
        # that explicit so the annotator lays out the line, key entries,
        # threat suits and counting before naming the next card.
        play_clause = ""
        if phase == 'play':
            play_clause = (
                "\n\nCARD-PLAY HINT — produce a FULL PLAN for the rest of "
                "the hand, not only the next card. The annotation block "
                "must include:\n"
                "  • A 'Plan:' line stating the line of play (e.g. "
                "'establish hearts after losing one', 'cross-ruff', "
                "'duck twice and run diamonds').\n"
                "  • A 'Tricks needed:' line that counts top tricks and "
                "names where the missing tricks come from.\n"
                "  • An 'Entries:' line listing every entry to each hand "
                "in order, since establishing length tricks usually hinges "
                "on them.\n"
                "  • A 'Threat / counting:' line covering the danger hand, "
                "what cards opponents have shown / signalled, and what to "
                "watch for as the hand unfolds.\n"
                "  • A short trick-by-trick sketch (Trick T+1, T+2, …) "
                "for the next 3-5 tricks of the plan.\n"
                "  • Then the usual '>> Recommendation: <card>' line as "
                "the very last annotation.\n\n"
                "DIAGRAMS — visual learners profit from a picture. "
                "Include 1–3 PlantUML diagrams in your reply, EACH "
                "wrapped in a ```plantuml ... ``` fenced block (the "
                "renderer will replace each block with the rendered "
                "PNG inline). Pick the diagram types that actually "
                "clarify THIS hand, e.g.:\n"
                "  – A mindmap (@startmindmap … @endmindmap) of the "
                "plan: root = 'Plan', children = each suit, "
                "grandchildren = top tricks / length tricks / losers.\n"
                "  – A simple block diagram (@startuml component … "
                "@enduml) of entries between hands, with arrows "
                "labelled by the card or sequence used.\n"
                "  – An activity diagram (@startuml :step; :step; "
                "@enduml) walking through the trick-by-trick sketch "
                "with decision diamonds where the next play depends "
                "on a card you don't yet know (e.g. \"if heart "
                "honour drops singleton → claim\").\n"
                "Keep each diagram small (≤ 12 nodes) so it renders "
                "fast and reads at a glance. Don't include diagrams "
                "for trivial spots."
            )


        # Tell Claude which bidding system the table is actually using so a
        # Precision-configured user gets Precision-style recommendations
        # ("1♣ = 16+", strong-club responses, etc.) and an SAYC-configured
        # user gets strict SAYC. Card-play hints don't depend on the
        # system, so this only kicks in during bidding.
        #
        # The clause is deliberately strict: Claude must apply the chosen
        # system's natural meanings only. No "SAYC-flavoured" hedging, no
        # crossing systems mid-recommendation, no falling back on a
        # different convention if the chosen system has nothing to say.
        system_clause = ""
        if phase == 'bidding':
            try:
                ns_spec = self._active_bidding_system('NS')
                ew_spec = self._active_bidding_system('EW')
                ns_text = self._format_system_summary(ns_spec)
                ew_text = self._format_system_summary(ew_spec)
                ns_pretty = ns_spec.description or ns_spec.name
                ew_pretty = ew_spec.description or ew_spec.name
                if ns_spec.name == ew_spec.name:
                    system_clause = (
                        f" The table is playing strict **{ns_pretty}** at "
                        f"BOTH pairs. Apply only this system's bid "
                        f"meanings — {ns_text}. Do NOT mix in conventions "
                        "from any other system."
                    )
                else:
                    # Different systems per pair — instruct Claude to
                    # interpret each side's calls using the matching
                    # spec, never blending the two.
                    system_clause = (
                        f"\n\nSYSTEMS IN USE (different per pair — "
                        "interpret each side's bids ONLY through the "
                        "matching system):\n"
                        f"  • NS plays **{ns_pretty}** — {ns_text}\n"
                        f"  • EW plays **{ew_pretty}** — {ew_text}\n"
                        "When commenting on an NS call, apply ONLY NS's "
                        "system. When commenting on an EW call, apply "
                        "ONLY EW's system. Never describe a bid using "
                        "the other pair's conventions."
                    )
            except Exception:
                # Config / spec lookup failed — fall back to a
                # system-agnostic prompt rather than crashing the hint.
                pass
        return (
            f"You are a bridge teacher advising {seat_names[seat]} on the next {action}."
            f"{system_clause}{play_clause}\n\n"
            "OUTPUT FORMAT — strictly required:\n"
            "  • Echo the BDL block below VERBATIM, line by line, "
            "preserving spacing.\n"
            "  • After every BDL section that you have something to say "
            "about, insert one or more annotation lines that BEGIN WITH "
            "'>>' (two right angle brackets followed by a space). Use "
            "annotations after the Bids block to comment on the auction, "
            "after the Tricks block to comment on play, and again at the "
            "very end of the file with your final recommendation.\n"
            "  • Do NOT modify any non-annotation line. Do NOT add a "
            "preamble or a trailing summary outside the BDL frame.\n"
            "  • Keep most annotations under ~25 words; multiple short "
            "ones beat one long one. The card-play 'Plan:' / 'Tricks "
            "needed:' / 'Entries:' / 'Threat:' / 'Trick-sketch' lines may "
            "each run to ~40 words to give a full picture.\n"
            "  • End with a single '>> Recommendation: <bid-or-card>' "
            "line that names exactly one action.\n\n"
            "Read seat letters straight off the N/E/S/W column headers in "
            "the Bids block and the leader/winner markers in the Tricks "
            "block — do not infer seats from order alone. If a BEN "
            "card-play suggestion is shown, say whether you agree (BEN "
            "card-play is system-agnostic). BEN bidding suggestions are "
            "NEVER shown because BEN was trained only on SAYC / 2-over-1 "
            "and can't reason about Precision / Acol / French calls.\n\n"
            f"BDL:\n{state_text}{engine_block}"
        )

    def _run_claude_with_dialog(self, prompt: str, title: str, wait_label: str,
                                 timeout_seconds: int = 300, preamble: str = "",
                                 bdl_text: str = ""):
        """Run claude -p with a progress dialog, then show the result.

        Shared between the end-of-hand analysis and the Hint button. Shows an
        error dialog if claude fails so the user never sees silent failure.

        When `bdl_text` is provided, the result is displayed via the
        BDL-with-annotations renderer: Claude's reply (which the prompt
        instructs it to format as the BDL with `>>` annotation lines
        inserted) is shown verbatim with annotations highlighted. If
        Claude failed to follow the format, the renderer falls back to
        appending its free-form text after the BDL.
        """
        import shutil
        import subprocess
        import threading
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                      QScrollArea, QProgressBar)
        from PyQt6.QtGui import QFont

        if not shutil.which('claude'):
            self._show_plain_dialog(title,
                                    "Claude CLI is not installed on this machine.\n"
                                    "Install it to enable this feature.",
                                    error=True)
            return

        # Progress dialog
        progress = QDialog(self)
        progress.setWindowTitle(title)
        progress.setFixedSize(420, 110)
        progress.setStyleSheet("background-color: #e8e8f0; color: #000;")
        p_layout = QVBoxLayout(progress)
        p_label = QLabel(wait_label)
        p_label.setFont(QFont("Arial", 12))
        p_label.setStyleSheet("color: #000;")
        p_layout.addWidget(p_label)
        p_bar = QProgressBar()
        p_bar.setRange(0, 0)  # Indeterminate
        p_bar.setStyleSheet("QProgressBar { border: 1px solid #aaa; border-radius: 3px; }"
                            "QProgressBar::chunk { background-color: #4a9; }")
        p_layout.addWidget(p_bar)
        progress.show()
        QApplication.processEvents()

        # Pidfile so run.sh waits for us (belt + suspenders)
        pidfile = None
        pid_dir = os.environ.get('CRITIQUE_PID_DIR')
        if pid_dir:
            try:
                os.makedirs(pid_dir, exist_ok=True)
                pidfile = os.path.join(pid_dir, f"{os.getpid()}-hint-{id(prompt)}.pid")
                with open(pidfile, 'w') as f:
                    f.write(str(os.getpid()))
            except Exception:
                pidfile = None

        result_holder = {'text': None, 'error': None}

        def _run_claude():
            try:
                # Use Opus 4.7 with extended thinking — same invocation as
                # the poker code uses for hand annotations.  The bare
                # --thinking flag was rejected by older builds; the value
                # variant works on every released CLI.
                r = subprocess.run(
                    ['claude', '-p',
                     '--model', 'claude-opus-4-7',
                     '--thinking', 'enabled',
                     '--max-turns', '1', prompt],
                    capture_output=True, text=True, timeout=timeout_seconds
                )
                stdout = (r.stdout or '').strip()
                stderr = (r.stderr or '').strip()
                if r.returncode == 0 and len(stdout) > 5:
                    result_holder['text'] = stdout
                else:
                    parts = [f"claude exited {r.returncode}"]
                    if stderr:
                        parts.append(f"stderr: {stderr[:500]}")
                    if stdout:
                        parts.append(f"stdout: {stdout[:500]}")
                    result_holder['error'] = "\n".join(parts)
            except subprocess.TimeoutExpired:
                result_holder['error'] = f"claude timed out after {timeout_seconds} seconds."
            except Exception as e:
                result_holder['error'] = f"claude call failed: {e!r}"

        thread = threading.Thread(target=_run_claude, daemon=True)
        thread.start()
        while thread.is_alive():
            QApplication.processEvents()
            thread.join(timeout=0.1)
        progress.close()

        if pidfile:
            try:
                os.unlink(pidfile)
            except OSError:
                pass

        text = result_holder['text']
        error = result_holder['error']

        if bdl_text:
            # BDL-annotated rendering. Even on failure we still show the
            # BDL so the user sees the same context Claude was given.
            preface = preamble.rstrip()
            framed = bdl_text
            if preface:
                framed = preface + "\n\n" + bdl_text
            self._show_annotated_bdl_dialog(
                title=title,
                bdl_text=framed,
                claude_text=text or "",
                error=not text,
            )
            if not text:
                # Surface the error inline at the top, since the
                # annotated dialog itself doesn't show errors.
                self._show_plain_dialog(
                    title + " (claude error)",
                    f"Claude did not return a response.\n\n"
                    f"{error or 'No output received.'}",
                    error=True,
                )
            return

        if text:
            self._show_plain_dialog(title, f"{preamble}{text}", error=False)
        else:
            self._show_plain_dialog(
                title,
                f"{preamble}Claude did not return a response.\n\n{error or 'No output received.'}",
                error=True,
            )

    # ------------------------------------------------------------------
    # PlantUML rendering — for the card-play hint plan diagrams. Tries
    # a locally installed `plantuml` binary first (fast, offline), then
    # falls back to the public plantuml.com PNG endpoint (no key, no
    # account, works any time you have internet). Each block is cached
    # by source text so re-opening the same hint doesn't re-render.
    # ------------------------------------------------------------------

    _PLANTUML_FENCE_RE = re.compile(
        r'```\s*(?:plantuml|uml)\s*\n(.*?)\n```',
        re.DOTALL | re.IGNORECASE,
    )

    @staticmethod
    def _plantuml_encode(text: str) -> str:
        """PlantUML's URL encoding: zlib-deflate the source, then map
        bytes through PlantUML's custom 6-bit alphabet
        (0-9, A-Z, a-z, '-', '_'). See PlantUML's text encoding spec.
        """
        import zlib
        deflated = zlib.compress(text.encode('utf-8'))
        raw = deflated[2:-4]  # strip zlib header + Adler-32 footer

        def enc6(b: int) -> str:
            if b < 10:
                return chr(48 + b)        # '0'-'9'
            b -= 10
            if b < 26:
                return chr(65 + b)        # 'A'-'Z'
            b -= 26
            if b < 26:
                return chr(97 + b)        # 'a'-'z'
            b -= 26
            if b == 0:
                return '-'
            if b == 1:
                return '_'
            return '?'

        out = []
        for i in range(0, len(raw), 3):
            b1 = raw[i]
            b2 = raw[i + 1] if i + 1 < len(raw) else 0
            b3 = raw[i + 2] if i + 2 < len(raw) else 0
            out.append(enc6(b1 >> 2))
            out.append(enc6(((b1 & 0x3) << 4) | (b2 >> 4)))
            out.append(enc6(((b2 & 0xF) << 2) | (b3 >> 6)))
            out.append(enc6(b3 & 0x3F))
        return ''.join(out)

    def _render_plantuml(self, uml_text: str):
        """Return PNG bytes for the given PlantUML source, or None if
        every render path failed. Tries local `plantuml` binary first
        then falls back to plantuml.com's PNG endpoint."""
        if not hasattr(self, '_plantuml_cache'):
            self._plantuml_cache = {}
        cached = self._plantuml_cache.get(uml_text)
        if cached is not None:
            return cached or None
        import shutil
        import subprocess
        png = None
        if shutil.which('plantuml'):
            try:
                r = subprocess.run(
                    ['plantuml', '-tpng', '-pipe'],
                    input=uml_text.encode('utf-8'),
                    capture_output=True, timeout=30,
                )
                if r.returncode == 0 and r.stdout:
                    png = r.stdout
            except Exception:
                png = None
        if png is None:
            try:
                import urllib.request
                encoded = self._plantuml_encode(uml_text)
                url = (
                    'https://www.plantuml.com/plantuml/png/' + encoded
                )
                with urllib.request.urlopen(url, timeout=30) as resp:
                    png = resp.read()
            except Exception:
                png = None
        self._plantuml_cache[uml_text] = png or b''
        return png

    def _replace_plantuml_with_images(self, text: str):
        """Pre-process Claude's reply: replace each ```plantuml block
        with a placeholder, render the blocks to PNG, return the
        modified text plus a list of (placeholder, png_bytes) pairs.
        Failed renders fall back to fenced code in the modified text so
        the user at least sees the source they can paste into a
        PlantUML editor by hand."""
        import base64

        chunks = []
        images = []
        last = 0
        for i, m in enumerate(self._PLANTUML_FENCE_RE.finditer(text)):
            chunks.append(text[last:m.start()])
            uml = m.group(1)
            png = self._render_plantuml(uml)
            if png:
                placeholder = f"\n<<<PLANTUML_IMG_{i}>>>\n"
                images.append((placeholder, png))
                chunks.append(placeholder)
            else:
                # Keep the source visible if we can't render.
                chunks.append(
                    "\n[PlantUML diagram — render failed; raw source below]\n"
                    f"```plantuml\n{uml}\n```\n"
                )
            last = m.end()
        chunks.append(text[last:])
        return ''.join(chunks), images

    def _show_annotated_bdl_dialog(self, title: str, bdl_text: str,
                                    claude_text: str, error: bool = False):
        """Render the BDL printout with Claude's annotations interspersed.

        Claude is asked to embed lines starting with ``>>`` at logical
        breakpoints in the BDL (after the auction, after the tricks
        block, at the end). The renderer below highlights those lines
        in italic green so the file's structure stays visible while the
        commentary sits inline next to whatever it's commenting on.

        If Claude's reply doesn't contain any ``>>`` markers (it
        ignored the format instruction), we fall back to showing the
        BDL on top and Claude's text below, separated by a banner.
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QPushButton,
                                      QTextEdit)
        from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

        # Extract any ```plantuml fenced blocks BEFORE the >> /
        # BDL split logic — we want the placeholders to flow through
        # as ordinary lines so they pick up the right surrounding
        # layout (after the BDL, between annotation lines, etc.).
        plantuml_images = []
        if claude_text:
            claude_text, plantuml_images = self._replace_plantuml_with_images(
                claude_text)

        # Pick the body text: if Claude returned a properly-annotated
        # BDL with `>>` markers in it, use that verbatim; otherwise
        # synthesize one by appending Claude's free-form text after the
        # BDL with a `>>` header so the layout stays consistent.
        if claude_text and ">>" in claude_text:
            body_text = claude_text.rstrip() + "\n"
        else:
            extra = (claude_text or "").strip()
            if not extra:
                extra = "(Claude returned no response.)"
            body_text = (
                bdl_text.rstrip() + "\n\n"
                ">> Claude (free-form, not interleaved):\n"
                + "\n".join(
                    ">> " + line if line.strip() else ">>"
                    for line in extra.splitlines()
                )
                + "\n"
            )

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(960, 640)
        dialog.resize(1100, 760)
        dialog.setStyleSheet("QDialog { background-color: #e8e8f0; color: #000; }")
        layout = QVBoxLayout(dialog)

        # Build an HTML document so annotation lines can wrap inside the
        # dialog width while BDL lines (which are column-aligned) stay
        # untouched in <pre>. Annotation continuations hang-indent under
        # the first character after `>> ` so the text reads like a margin
        # comment rather than a free-form paragraph.
        from html import escape
        BDL_FONT_PT = 22       # was 18 — bumped per request
        ANN_FONT_PT = 22
        BDL_COLOR   = "#202020"
        ANN_COLOR   = "#1a6020"
        BG_COLOR    = "#f8f8f8"

        # Group consecutive non-annotation lines into a single <pre> so
        # multi-line BDL blocks render as one whitespace-preserved chunk.
        html_parts = []

        def flush_bdl(buf):
            if not buf:
                return
            text = "\n".join(buf)
            html_parts.append(
                f'<pre style="font-family: Monospace; font-size: {BDL_FONT_PT}pt; '
                f'color: {BDL_COLOR}; margin: 0; line-height: 1.3;">'
                f'{escape(text)}</pre>'
            )
            buf.clear()

        # Build a lookup of placeholder → base64 image so we can swap
        # them out inline as soon as we hit one in the body stream.
        import base64
        placeholder_to_img = {}
        for placeholder, png_bytes in plantuml_images:
            try:
                b64 = base64.b64encode(png_bytes).decode('ascii')
                placeholder_to_img[placeholder.strip()] = (
                    f'<div style="margin: 12px 0; text-align: center;">'
                    f'<img src="data:image/png;base64,{b64}" '
                    f'style="max-width: 100%; border: 1px solid #aaa;'
                    f' border-radius: 4px; background: #fff;"/>'
                    f'</div>'
                )
            except Exception:
                pass

        bdl_buf: list[str] = []
        for line in body_text.splitlines():
            stripped_line = line.strip()
            if stripped_line in placeholder_to_img:
                flush_bdl(bdl_buf)
                html_parts.append(placeholder_to_img[stripped_line])
                continue
            if line.lstrip().startswith('>>'):
                flush_bdl(bdl_buf)
                # Strip the leading >> and any single space, then render the
                # comment with the >> prefix inline AND a hanging indent so
                # wrapped continuations align under the first character of
                # the comment text (matching the BDL's left margin).
                rest = line.lstrip()[2:]
                if rest.startswith(' '):
                    rest = rest[1:]
                html_parts.append(
                    f'<div style="font-family: Monospace; '
                    f'font-size: {ANN_FONT_PT}pt; color: {ANN_COLOR}; '
                    f'font-style: italic; font-weight: bold; '
                    f'margin: 2px 0; padding-left: 3ch; '
                    f'text-indent: -3ch; white-space: normal; '
                    f'word-wrap: break-word; line-height: 1.3;">'
                    f'&gt;&gt; {escape(rest)}</div>'
                )
            else:
                bdl_buf.append(line)
        flush_bdl(bdl_buf)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setStyleSheet(
            f"QTextEdit {{ background-color: {BG_COLOR}; color: #000;"
            f" border: 1px solid #aaa; padding: 14px; }}"
        )
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        editor.setHtml("".join(html_parts))
        editor.moveCursor(QTextCursor.MoveOperation.Start)

        layout.addWidget(editor, stretch=1)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(140, 48)
        ok_btn.setStyleSheet(
            "QPushButton { background-color: #d0d0d0; color: #000;"
            " border: 1px solid #999; border-radius: 3px; font-size: 18px; }"
        )
        ok_btn.clicked.connect(dialog.accept)
        layout.addWidget(ok_btn)

        # Detached: the user wants to leave it open on a second monitor
        # next to the play view.
        from .dialogs.dialog_style import make_detachable
        make_detachable(dialog)
        dialog.show()
        dialog.raise_()
        # Hold a reference so it isn't GC'd as soon as we return.
        # Dialogs were promoted with WA_DeleteOnClose by make_detachable,
        # so previous entries may have had their underlying C++ object
        # destroyed already; calling isVisible() on a dead wrapper
        # raises RuntimeError ("wrapped C/C++ object … has been
        # deleted"), so guard the survivor sweep.
        if not hasattr(self, '_annotated_bdl_dialogs'):
            self._annotated_bdl_dialogs = []

        survivors = []
        for d in self._annotated_bdl_dialogs:
            try:
                if d.isVisible():
                    survivors.append(d)
            except RuntimeError:
                # Wrapper outlived the C++ widget — drop it.
                pass
        survivors.append(dialog)
        self._annotated_bdl_dialogs = survivors

    def _show_plain_dialog(self, title: str, body: str, error: bool = False):
        """Show a scrollable result dialog with OK button (shared helper).

        Non-modal so the user can interact with the main window — open
        the Compare dialog, the score sheet, replay a board — while the
        Claude analysis is still visible. We hold a reference on
        `self._plain_dialogs` so the widget isn't garbage-collected as
        soon as we return.
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                      QScrollArea)
        from PyQt6.QtGui import QFont

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(700, 350)
        dialog.resize(800, 450)
        dialog.setStyleSheet("QDialog { background-color: #e8e8f0; color: #000; }")
        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #aaa; background-color: #f8f8f8; }")
        label = QLabel(body)
        label.setFont(QFont("Arial", 16 if error else 20))
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(
            f"color: {'#803030' if error else '#000'}; background-color: #f8f8f8; padding: 15px;"
        )
        scroll.setWidget(label)
        layout.addWidget(scroll)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(120, 40)
        ok_btn.setStyleSheet("QPushButton { background-color: #d0d0d0; color: #000; "
                             "border: 1px solid #999; border-radius: 3px; font-size: 16px; }")
        ok_btn.clicked.connect(dialog.close)
        layout.addWidget(ok_btn)

        # Promote to a free-floating top-level window so the user can
        # drag it to a second monitor and keep working in main_window.
        from .dialogs.dialog_style import make_detachable
        make_detachable(dialog)
        dialog.show()
        dialog.raise_()

        # Keep references to surviving dialogs; sweep dead wrappers
        # (WA_DeleteOnClose set by make_detachable destroys the C++
        # widget on close, after which isVisible() raises RuntimeError).
        if not hasattr(self, '_plain_dialogs'):
            self._plain_dialogs = []
        survivors = []
        for d in self._plain_dialogs:
            try:
                if d.isVisible():
                    survivors.append(d)
            except RuntimeError:
                pass
        survivors.append(dialog)
        self._plain_dialogs = survivors

    def _on_undo(self):
        """Undo last card play (only works during current trick before it completes)"""
        # Disable undo during network play to prevent sync issues
        if self.network_controller.is_active:
            self.status_label.setText("Undo not available during network play")
            return

        if self.controller.current_phase not in ('play', 'waiting_next'):
            self.status_label.setText("Undo only available during card play")
            return

        if not self.card_history:
            self.status_label.setText("Nothing to undo")
            return

        # Only allow undo if the last card was played by human and trick is not complete
        # or if we're in waiting_next state (trick just completed)
        board = self.controller.board
        current_trick = board.current_trick

        if self.controller.current_phase == 'waiting_next':
            # Trick just completed - can't undo after trick is done
            self.status_label.setText("Cannot undo after trick is complete")
            return

        if not current_trick or len(current_trick.cards) == 0:
            self.status_label.setText("Nothing to undo in current trick")
            return

        # Find the last human card in the history
        last_entry = self.card_history[-1]
        seat, card, is_human = last_entry

        if not is_human:
            self.status_label.setText("Cannot undo computer's card")
            return

        # Remove from history
        self.card_history.pop()

        # Restore card to hand
        if seat in board.hands:
            board.hands[seat].cards.append(card)

        # Remove from current trick
        if current_trick.cards and current_trick.cards[-1] == card:
            current_trick.cards.pop()
            current_trick.winner = None  # Reset winner

        # Reset current seat to the player who played the undone card
        self.controller.current_seat = seat

        # Update table view - rebuild the hand and clear trick display
        self.table_view.hand_widgets[seat].set_hand(board.hands[seat])
        self.table_view.clear_trick()

        # Re-show any remaining cards in the trick
        for i, c in enumerate(current_trick.cards):
            trick_seat = Seat((current_trick.leader.value + i) % 4)
            self.table_view.play_card_to_trick(trick_seat, c)

        # Update button state
        self.undo_btn.setEnabled(len(self.card_history) > 0 and
                                  any(h[2] for h in self.card_history))

        self.status_label.setText(f"Undid {card.to_str()} by {seat.to_char()}")

    def _on_claim(self):
        """Claim remaining tricks"""
        if self.controller.current_phase == 'play':
            QMessageBox.information(self, "Claim",
                                   "Claim feature not yet implemented.")

    def _on_next_card(self):
        """Advance to next trick after a trick completes"""

        # Debug: verify current_seat matches the last trick winner
        last_winner = self.controller.get_trick_winner()
        if last_winner and self.controller.current_seat != last_winner:
            pass

        if self.controller.current_phase == 'waiting_next':
            # In network mode, broadcast to sync the other player
            if self.network_controller.is_active:
                self.network_controller.broadcast_trick_clear()

            self.controller.advance_to_next_trick()
            self.table_view.clear_trick()
            self.next_card_btn.setEnabled(False)
            self._advance_game()
        else:
            pass

    def _on_next_card_shortcut(self):
        """Spacebar shortcut for Next card.

        We honour the button's enabled state so the spacebar can't fire
        when auto-advance has already queued up a callback or when the
        opposing side hasn't finished yet (network).
        """
        if self.next_card_btn.isVisible() and self.next_card_btn.isEnabled():
            self._on_next_card()

    # Game flow

    def _on_bid_made(self, bid: Bid):
        """Handle human bid"""
        if self.controller.current_phase != 'bidding':
            return

        if not self.controller.is_human_turn():
            return

        bidder = self.controller.current_seat
        self.controller.make_bid(bid)
        self.bidding_box.add_bid(bid)
        self.table_view.update_auction(self.controller.board.auction, self.controller.board.dealer)

        # Broadcast to network if active
        if self.network_controller.is_active:
            self.network_controller.broadcast_bid(bidder, bid)

        # Add to bid info window
        self._add_bid_to_info(bidder, bid, "", "")
        self._update_available_bids()

        self._advance_game()

    def _on_card_played(self, seat: Seat, card: Card):
        """Handle human card play"""

        if self.controller.current_phase != 'play':
            return

        if seat != self.controller.current_seat:
            return

        if not self.controller.is_human_turn():
            return


        # Validate the card is legal
        lead_suit = self.controller.get_lead_suit()
        hand = self.controller.board.hands.get(seat)
        if hand and lead_suit:
            has_suit = any(c.suit == lead_suit for c in hand.cards)
            if has_suit and card.suit != lead_suit:
                self.status_label.setText("Must follow suit!")
                return

        # Blunder check — run a Monte-Carlo + DDS scoring of every
        # legal card and warn the user if their pick loses ≥1 trick
        # against the best play. Two-button dialog [Hint] / [Cancel];
        # neither commits the play, so the user can either re-pick or
        # click the same card a second time to override the warning
        # (the warning is suppressed once-per-turn per card).
        if not self._maybe_warn_card_blunder(seat, card):
            return

        # Record for undo (only human cards can be undone, marked with is_human=True)
        self.card_history.append((seat, card, True))
        self.undo_btn.setEnabled(True)

        # Check if this is the opening lead (first card of play)
        is_opening_lead = (len(self.controller.board.tricks) == 0 and
                          (not self.controller.board.current_trick or
                           len(self.controller.board.current_trick.cards) == 0))

        self.table_view.play_card_to_trick(seat, card)
        self.controller.play_card(card)
        # Successful commit — clear the per-turn warned-cards set so
        # the next decision starts fresh (no carry-over warnings
        # about a card the user already discarded).
        self._blunder_warned_cards = set()

        # Broadcast to network if active
        if self.network_controller.is_active:
            self.network_controller.broadcast_card(seat, card)

            # Dummy reveal is now broadcast at the start of the play
            # phase (in _advance_play right after setup_declarer_play)
            # so the guest sees dummy at the same moment as the host.
            # No second post-opening-lead broadcast needed here.

        self._advance_game()

    def _maybe_reveal_dummy_after_lead(self):
        """Bridge rule: dummy is laid down right after the opening lead.

        Two independent state machines run here:
          1. TableView.dummy_revealed — the host's *local* visibility.
             setup_declarer_play() flips it on immediately when the
             host's side declared (declarer needs the dummy to plan)
             and off when the opposing side declared (defender mustn't
             peek before leading).
          2. self._dummy_broadcasted_for_board — whether the host has
             yet pushed the dummy reveal to guests. Always deferred to
             the opening lead, even when the host already sees dummy
             locally, because a guest on defense should never see dummy
             before the human-side opening lead lands.
        """
        board = self.controller.board
        if board is None:
            return
        ct = board.current_trick
        # Opening lead just landed when there are 0 completed tricks
        # and exactly one card sits in the current trick.
        if len(board.tricks) != 0 or ct is None or len(ct.cards) < 1:
            return

        # Local reveal — only matters when setup_declarer_play hid dummy.
        if not getattr(self.table_view, 'dummy_revealed', True):
            self.table_view.reveal_dummy()

        # Network broadcast — always after opening lead, gated by a
        # per-board flag so we don't spam the wire on every later card.
        if (self.network_controller.is_active
                and self.network_controller.is_server
                and self.controller.dummy is not None
                and not getattr(self, '_dummy_broadcasted_for_board', False)):
            dummy_seat = self.controller.dummy
            dummy_hand = board.hands.get(dummy_seat)
            if dummy_hand is not None and dummy_hand.cards:
                try:
                    self.network_controller.broadcast_dummy_reveal(
                        dummy_seat, dummy_hand
                    )
                    self._dummy_broadcasted_for_board = True
                except Exception as e:
                    print(f"[dummy reveal] broadcast failed: {e}", flush=True)

    BLUNDER_TRICK_THRESHOLD = 1.0   # ≥1 trick loss = blunder
    BLUNDER_MC_SAMPLES = 15         # MC samples per legal card

    @staticmethod
    def _current_pair_systems() -> tuple:
        """Return ``(ns_system_name, ew_system_name)`` for the currently
        configured bidder. Per-pair override wins; falls back to the
        shared native_bidding_system, then to SAYC.

        Used by the BenBoardRun / BenTeamsMatch construction sites so
        a freshly-recorded deal is stamped with the real system the
        bots played, not the legacy "BEN-NN" placeholder default.
        """
        try:
            from ben_backend.config import get_config_manager
            prefs = get_config_manager().config.preferences
            default = (getattr(prefs, 'native_bidding_system', '')
                       or 'SAYC') or 'SAYC'
            ns = (getattr(prefs, 'ns_bidding_system', '')
                  or default)
            ew = (getattr(prefs, 'ew_bidding_system', '')
                  or default)
            return ns, ew
        except Exception:
            return 'SAYC', 'SAYC'

    def _maybe_warn_card_blunder(self, seat: 'Seat', card: 'Card') -> bool:
        """Cardplay blunder check. Runs DDS over Monte-Carlo samples
        of the hidden hands, scores every legal card by average
        trick count from this point, and pops a Hint/Cancel dialog
        if the user's pick loses ≥ BLUNDER_TRICK_THRESHOLD tricks
        against the best card.

        Returns True if the play should be committed, False if the
        user dismissed via Hint or Cancel. The per-turn warned-set
        means clicking the SAME card a second time bypasses the
        warning — the user can override after seeing the explanation.
        """
        try:
            from ben_backend.config import get_config_manager
            prefs = get_config_manager().config.preferences
            if not getattr(prefs, 'blunder_check_enabled', True):
                return True
        except Exception:
            pass

        if not getattr(self, '_blunder_warned_cards', None):
            self._blunder_warned_cards = set()
        key = (seat, card.to_str())
        if key in self._blunder_warned_cards:
            return True  # already warned about this card this turn

        try:
            board = self.controller.board
            trick_cards = []
            if board.current_trick and board.current_trick.cards:
                trick_cards = list(board.current_trick.cards)
        except Exception:
            return True

        # Trivial spots — only one legal card means there's nothing
        # to blunder on; skip the DDS run entirely.
        try:
            hand = board.hands.get(seat)
            lead_suit = (trick_cards[0].suit if trick_cards else None)
            if hand is None or not hand.cards:
                return True
            legal = [c for c in hand.cards
                     if lead_suit is None or c.suit == lead_suit]
            if not legal:
                legal = list(hand.cards)
            if len(legal) <= 1:
                return True
        except Exception:
            return True

        # Run the MC+DDS score. This can take 2–8 s depending on
        # the position; surface a status message so the user knows
        # why the click is pausing.
        try:
            self.status_label.setText(
                "Checking for blunders (Monte-Carlo + DDS)…")
            QApplication.processEvents()
            resp = self.engine.get_mc_card_play(
                board, seat, trick_cards,
                num_samples=self.BLUNDER_MC_SAMPLES,
            )
        except Exception:
            return True
        finally:
            try:
                self.status_label.setText("")
            except Exception:
                pass

        if not resp or not getattr(resp, 'candidates', None):
            return True

        # Find user's card and the best card in the candidate list.
        best = None
        user = None
        for cand in resp.candidates:
            c = getattr(cand, 'card', None)
            if c is None:
                continue
            if best is None or cand.score > best.score:
                best = cand
            if user is None and c == card:
                user = cand
        if best is None or user is None:
            return True

        loss = best.score - user.score
        if loss < self.BLUNDER_TRICK_THRESHOLD:
            return True  # not substantially worse

        # Mark warned BEFORE showing the dialog so a re-click after
        # Cancel/Hint goes straight through.
        self._blunder_warned_cards.add(key)
        return self._show_card_blunder_dialog(seat, card, best.card, loss)

    def _show_card_blunder_dialog(self, seat, user_card, best_card,
                                   trick_loss) -> bool:
        """Two-button dialog: Hint / Cancel. Always returns False so
        the user's blunder doesn't commit on this click. Re-clicking
        the same card after dismissal bypasses the check (see the
        warned-set in _maybe_warn_card_blunder)."""
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle("Possible blunder")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<div style='font-size:22px; font-weight:bold; color:#000;'>"
            f"Playing {user_card.to_str()} from "
            f"{seat.to_char()} looks like a blunder.</div>"
            f"<div style='font-size:18px; color:#333; margin-top:10px;'>"
            f"Monte-Carlo + double-dummy says it loses about "
            f"<b>{trick_loss:.1f} trick"
            f"{'s' if trick_loss >= 1.5 else ''}</b> on average "
            f"compared with the best play.</div>"
            f"<div style='font-size:18px; color:#333; margin-top:8px;'>"
            f"Get a hint (BEN's recommendation + Claude's "
            f"explanation), or cancel and pick again? "
            f"Re-clicking the same card after dismissing this "
            f"dialog will commit your original play.</div>"
        )
        msg.setStyleSheet(
            "QMessageBox { background-color: #f0f0f0; }"
            "QMessageBox QLabel { color: #000;"
            " background-color: transparent; min-width: 720px;"
            " padding: 14px 10px; }"
            "QMessageBox QPushButton { font-size: 16px;"
            " padding: 8px 22px; min-width: 110px; }"
        )
        hint_btn = msg.addButton(
            "Hint", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = msg.addButton(
            "Cancel (pick again)", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(hint_btn)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is hint_btn:
            try:
                self._on_hint()
            except Exception:
                pass
        return False  # neither Hint nor Cancel commits the play

    def _advance_game(self):
        """Advance the game state"""
        # If we just played the opening lead, dummy is now visible —
        # check before per-phase dispatch so the next status update can
        # already see the revealed dummy.
        self._maybe_reveal_dummy_after_lead()
        if self.controller.current_phase == 'bidding':
            self._advance_bidding()
        elif self.controller.current_phase == 'play':
            self._advance_play()
        elif self.controller.current_phase == 'waiting_next':
            self._handle_trick_complete()
        elif self.controller.current_phase == 'finished':
            self._show_result()
        # Refresh Hint enable state — only on the local user's turn so
        # players can't peek at another seat's hand by clicking Hint
        # while it isn't their turn.
        self._refresh_hint_button_state()

    def _refresh_hint_button_state(self):
        """Grey the Hint toolbar button when it isn't the user's turn."""
        if not hasattr(self, 'hint_btn'):
            return
        try:
            self.hint_btn.setEnabled(self._is_local_user_turn())
        except Exception:
            # Button enable state is cosmetic — don't let a transient
            # state error block the game flow.
            pass

    def _advance_bidding(self):
        """Advance bidding phase"""
        self.bidding_box.set_current_bidder(self.controller.current_seat)

        current_seat = self.controller.current_seat

        # Check if we're in network mode
        if self.network_controller.is_active:
            is_mine = self.network_controller.is_my_seat(current_seat)
            is_remote = self.network_controller.is_remote_seat(current_seat)
            if is_mine:
                # My turn - enable bidding
                self.bidding_box.set_enabled(True)
                self.status_label.setText(
                    f"Your bid ({current_seat.to_char()})"
                )
                return
            elif is_remote:
                # Remote player's turn - wait for them
                self.bidding_box.set_enabled(False)
                who = "partner" if self.network_controller.client_role == "partner" else "opponent"
                self.status_label.setText(
                    f"Waiting for {who} ({current_seat.to_char()})..."
                )
                return
            else:
                # AI seat
                if self.network_controller.is_client:
                    # Client waits for server to broadcast AI bid
                    self.bidding_box.set_enabled(False)
                    self.status_label.setText(f"Waiting for AI ({current_seat.to_char()})...")
                    return
                # Server runs the AI - fall through to engine handling

        # Standard single-player mode
        if self.controller.is_human_turn():
            self.bidding_box.set_enabled(True)
            self.status_label.setText(
                f"Your bid ({current_seat.to_char()})"
            )
        else:
            self.bidding_box.set_enabled(False)
            self.status_label.setText(
                f"Thinking ({current_seat.to_char()})..."
            )

            # Request bid from engine
            if self.engine_worker:
                self.engine_worker.request_bid(
                    self.controller.board, current_seat
                )

    def _advance_play(self):
        """Advance play phase"""
        trick = self.controller.board.current_trick
        trick_info = f"cards={[c.to_str() for c in trick.cards]}, leader={trick.leader}" if trick else "None"
        self.bidding_box.set_enabled(False)

        # Setup declarer play if just starting
        # `self.table_view.declarer` is a Seat (IntEnum where NORTH == 0),
        # so `not …declarer` would re-fire setup_declarer_play (and the
        # dummy-reveal broadcast inside it) on every _advance_play tick
        # whenever declarer is North. Use an explicit None check.
        if (self.controller.board.contract
                and self.table_view.declarer is None):
            # Mirror the controller's "does the local user control the
            # declarer partnership" flag onto the table view so it can
            # decide whether to reveal declarer face up.
            self.table_view.human_controls_declarer = bool(
                getattr(self.controller, 'human_controls_declarer', False)
            )
            # Reset the per-board "dummy already broadcast" flag the
            # first time we enter play on this hand. Cheaper than
            # resetting in every _on_new_deal / new-deal path.
            self._dummy_broadcasted_for_board = False
            self.table_view.setup_declarer_play(self.controller.board.contract)
            self.table_view.set_auction_complete("bidding finished")
            # Hide right panel (bidding box + analysis) and next deal button during card play
            self.right_panel.setVisible(False)
            self.next_deal_btn.setVisible(False)
            # Hide bid info window during card play
            self.bid_info_dock.hide()
            # Dummy reveal is broadcast strictly after the opening lead
            # — see _maybe_reveal_dummy_after_lead. Even when the host's
            # side declared and dummy is already shown locally, guests
            # on defense must wait for the lead before they get to peek.

        # Update tricks display
        self.table_view.update_tricks(
            self.controller.board.declarer_tricks,
            self.controller.board.defense_tricks
        )

        # Get current lead suit
        lead_suit = self.controller.get_lead_suit()

        # Disable all hands first
        for seat in Seat:
            self.table_view.set_hand_selectable(seat, False)

        current_seat = self.controller.current_seat
        is_human = self.controller.is_human_turn()
        autoplay_active = self.autoplay_btn.isChecked()

        # Check if we're in network mode
        if self.network_controller.is_active:
            declarer = self.controller.declarer
            dummy = self.controller.dummy

            # Determine who should play this seat
            # If current seat is dummy, declarer plays it
            actual_player = declarer if current_seat == dummy else current_seat


            if self.network_controller.is_my_seat(actual_player):
                # My turn - enable hand selection (could be my hand or dummy if I'm declarer)
                self.table_view.set_hand_selectable(current_seat, True, lead_suit)
                if current_seat == dummy:
                    self.status_label.setText(f"Play dummy ({current_seat.to_char()})")
                else:
                    self.status_label.setText(f"Your play ({current_seat.to_char()})")
                return
            elif self.network_controller.is_remote_seat(actual_player):
                # Remote player's turn - wait
                who = "partner" if self.network_controller.client_role == "partner" else "opponent"
                self.status_label.setText(f"Waiting for {who} ({current_seat.to_char()})...")
                return
            else:
                # AI seat
                if self.network_controller.is_client:
                    # Client waits for server to broadcast AI card
                    self.status_label.setText(f"Waiting for AI ({current_seat.to_char()})...")
                    return
                # Server runs the AI - fall through to engine handling

        # Standard single-player mode
        # If autoplay is on, use engine for all seats including human
        if is_human and not autoplay_active:
            # Enable the current hand for human
            self.table_view.set_hand_selectable(
                current_seat, True, lead_suit
            )
            self.status_label.setText(
                f"Your play ({current_seat.to_char()})"
            )
        else:
            self.status_label.setText(
                f"Thinking ({current_seat.to_char()})..."
            )

            # Request card from engine
            if self.engine_worker:
                trick_cards = []
                if self.controller.board.current_trick:
                    trick_cards = self.controller.board.current_trick.cards
                started = self.engine_worker.request_card(
                    self.controller.board, current_seat, trick_cards
                )
                if not started:
                    # Worker was busy, retry after a delay
                    QTimer.singleShot(200, self._advance_play)
                else:
                    # Watchdog: if the engine doesn't produce a card
                    # within a reasonable window, force a legal-card
                    # fallback so the table doesn't sit on
                    # "Thinking (X)…" forever. Every successful
                    # request bumps the token; only the most-recent
                    # token's timer ever fires the rescue path.
                    self._engine_card_token = (
                        getattr(self, '_engine_card_token', 0) + 1
                    )
                    self._engine_card_seat = current_seat
                    token = self._engine_card_token
                    # Was 45 s — long enough that the user assumes the
                    # game has frozen. 20 s is comfortably above BEN's
                    # normal think-time on a 4-card-out endgame and
                    # still gives the engine plenty of room before we
                    # fall back to a legal card.
                    QTimer.singleShot(
                        20_000,
                        lambda t=token, s=current_seat:
                            self._engine_card_watchdog(t, s)
                    )
            else:
                pass

    def _engine_card_watchdog(self, token: int, seat: 'Seat'):
        """Rescue the table when the BEN engine never returns a card
        for `seat`. We arm one of these per `request_card` and stamp it
        with a token; if a later request supersedes us (token mismatch),
        or if the controller has moved past play, this timer is a
        no-op. Otherwise we synthesize a legal-card fallback (mirrors
        the response.action == None path in _on_engine_card).

        Before falling back we capture a freeze report so the next
        engine hang can be diagnosed without the user having to
        remember the py-spy / gdb procedure — see
        _capture_engine_freeze_report for what gets written.
        """
        if getattr(self, '_engine_card_token', 0) != token:
            return  # superseded by a newer request
        if self.controller.current_phase != 'play':
            return
        if self.controller.current_seat != seat:
            return

        # Capture diagnostics FIRST, before we mutate state with the
        # fallback play. This way the worker thread is still parked in
        # whatever frame caused the hang.
        report_path = None
        try:
            report_path = self._capture_engine_freeze_report(seat)
        except Exception as e:
            print(f"[engine watchdog] freeze report capture failed: {e!r}",
                  flush=True)

        # Still waiting on the same seat after the timeout — pick a
        # legal card and advance.
        hand = self.controller.board.hands.get(seat)
        if not hand or not hand.cards:
            return
        try:
            lead_suit = self.controller.get_lead_suit()
        except Exception:
            lead_suit = None
        if lead_suit is not None:
            same_suit = [c for c in hand.cards if c.suit == lead_suit]
            card = same_suit[0] if same_suit else hand.cards[0]
        else:
            card = hand.cards[0]
        print(f"[engine watchdog] {seat.to_char()} timed out; "
              f"playing {card.to_str()} as fallback", flush=True)
        try:
            self.table_view.play_card_to_trick(seat, card)
            self.controller.play_card(card)
            if (self.network_controller.is_active
                    and self.network_controller.is_server):
                self.network_controller.broadcast_card(seat, card)
        except Exception as e:
            print(f"[engine watchdog] fallback play failed: {e!r}", flush=True)
            return
        msg = f"Engine timeout for {seat.to_char()} — fallback played."
        if report_path:
            msg += f"  Freeze report: {report_path}"
        self.status_label.setText(msg)
        QTimer.singleShot(200, self._advance_game)

    def _capture_engine_freeze_report(self, seat: 'Seat') -> str:
        """Write a per-freeze diagnostic dump to DATA/freeze_reports/.

        Bundles everything you'd want when an engine hang reproduces:
          • Python stack of EVERY thread in this process via
            ``sys._current_frames()`` — no ptrace needed, so it works
            without sudo. The EngineWorker thread is the one whose top
            frame is inside ben_backend (engine.py / pimc / sample.py
            / nn / ddsolver), and that frame names the exact code
            path that's stuck.
          • A native (gdb) backtrace of every thread when ``gdb`` is
            on PATH and ptrace_scope allows attaching to ourselves —
            this is best-effort; if it fails the report still has the
            Python side, which is the high-signal piece.
          • Game state at the moment of the freeze: dealer, vulnerability,
            contract, declarer, dummy, current_seat, all four hands,
            recent action history, and the relevant preferences
            (use_monte_carlo_play / use_double_dummy_play). That makes
            the deal reproducible offline.

        Returns the path to the written report (or '' on failure) so
        the watchdog can surface it in the status bar.
        """
        import os
        import sys
        import datetime
        import traceback as tb_mod
        from pathlib import Path

        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Sit alongside the BDL logs so the user has one obvious place
        # to look for hand-related diagnostics.
        try:
            log_dir = Path(self.game_logger.log_dir).parent / "freeze_reports"
        except Exception:
            log_dir = Path(os.path.expanduser(
                "~/.benBridge/freeze_reports"))
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"freeze-{ts}-{seat.to_char()}.txt"

        lines = []
        lines.append(f"BEN Bridge engine-freeze report")
        lines.append(f"timestamp:   {datetime.datetime.now().isoformat()}")
        lines.append(f"pid:         {os.getpid()}")
        lines.append(f"frozen seat: {seat.to_char()}")

        # --- Game state ---
        try:
            board = self.controller.board
            lines.append("")
            lines.append("=== Game state ===")
            lines.append(f"board #:       {getattr(board, 'board_number', '?')}")
            lines.append(f"dealer:        {board.dealer.to_char() if board else '?'}")
            lines.append(f"vulnerability: "
                         f"{board.vulnerability.name if board else '?'}")
            lines.append(f"current phase: {self.controller.current_phase}")
            lines.append(f"current seat:  "
                         f"{self.controller.current_seat.to_char() if self.controller.current_seat else '?'}")
            if self.controller.declarer is not None:
                lines.append(f"declarer:      {self.controller.declarer.to_char()}")
            if self.controller.dummy is not None:
                lines.append(f"dummy:         {self.controller.dummy.to_char()}")
            if board and board.contract:
                lines.append(f"contract:      {board.contract.to_str()} "
                             f"by {board.contract.declarer.to_char()}")
            lines.append("")
            lines.append("Hands (current):")
            from ben_backend.models import Suit as _Suit
            for s in [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]:
                h = board.hands.get(s) if board else None
                if h is None:
                    lines.append(f"  {s.to_char()}: (unknown)")
                    continue
                suit_strs = []
                for suit in [_Suit.SPADES, _Suit.HEARTS,
                             _Suit.DIAMONDS, _Suit.CLUBS]:
                    cards = sorted([c for c in h.cards if c.suit == suit],
                                   key=lambda c: c.rank)
                    sym = {_Suit.SPADES: 'S', _Suit.HEARTS: 'H',
                           _Suit.DIAMONDS: 'D', _Suit.CLUBS: 'C'}[suit]
                    text = ''.join(c.rank.to_char() for c in cards) or '-'
                    suit_strs.append(f"{sym}:{text}")
                lines.append(f"  {s.to_char()}: {' '.join(suit_strs)}")
            ct = getattr(board, 'current_trick', None) if board else None
            if ct and ct.cards and ct.leader is not None:
                played = []
                for j, card in enumerate(ct.cards):
                    p_seat = Seat((ct.leader.value + j) % 4)
                    played.append(f"{p_seat.to_char()}:{card.to_str()}")
                lines.append(f"current trick: {' '.join(played)}  "
                             f"(leader {ct.leader.to_char()})")
            tricks = getattr(board, 'tricks', []) if board else []
            lines.append(f"tricks completed: {len(tricks)}")
            if board and board.auction:
                bidder = board.dealer
                auction = []
                for bid in board.auction:
                    auction.append(f"{bidder.to_char()}:{bid.to_str()}")
                    bidder = bidder.next()
                lines.append("auction: " + " ".join(auction))
        except Exception as e:
            lines.append(f"(game-state capture failed: {e!r})")

        # --- Preferences (so we know which engine path was on) ---
        try:
            prefs = self.config_manager.config.preferences
            lines.append("")
            lines.append("=== Preferences ===")
            for attr in ('use_monte_carlo_play', 'use_double_dummy_play',
                         'bidding_engine', 'native_bidding_system',
                         'nosearch'):
                if hasattr(prefs, attr):
                    lines.append(f"  {attr}: {getattr(prefs, attr)}")
        except Exception as e:
            lines.append(f"(prefs capture failed: {e!r})")

        # --- Python stacks of every live thread ---
        # sys._current_frames() works in-process: no ptrace needed, no
        # sudo. The EngineWorker thread is the one with a frame inside
        # ben_backend; its topmost frame is the smoking gun.
        lines.append("")
        lines.append("=== Python thread stacks (sys._current_frames) ===")
        try:
            import threading
            tid_to_name = {t.ident: t.name for t in threading.enumerate()}
            for tid, frame in sys._current_frames().items():
                name = tid_to_name.get(tid, f"tid {tid}")
                lines.append("")
                lines.append(f"--- Thread: {name} (tid {tid}) ---")
                stack = tb_mod.format_stack(frame)
                lines.extend(s.rstrip() for s in stack)
        except Exception as e:
            lines.append(f"(thread-stack capture failed: {e!r})")

        # --- Native (gdb) backtrace, best-effort ---
        # Skipped quietly when gdb is missing or ptrace_scope blocks
        # us. Captures C-level frames inside DDS / native MC code,
        # which is invisible to py-spy and sys._current_frames.
        lines.append("")
        lines.append("=== Native backtrace (gdb -batch) ===")
        try:
            import shutil
            import subprocess
            if shutil.which('gdb') is None:
                lines.append("(gdb not installed — skipped)")
            else:
                gdb_cmd = [
                    'gdb', '-p', str(os.getpid()), '-batch',
                    '-ex', 'set pagination off',
                    '-ex', 'thread apply all bt',
                    '-ex', 'detach',
                ]
                r = subprocess.run(gdb_cmd, capture_output=True,
                                   text=True, timeout=10)
                if r.returncode == 0 and r.stdout:
                    lines.append(r.stdout)
                else:
                    err = (r.stderr or '').splitlines()[:5]
                    lines.append(
                        "(gdb attach failed — likely "
                        "/proc/sys/kernel/yama/ptrace_scope blocks "
                        "self-attach. Run\n"
                        "   echo 0 | sudo tee /proc/sys/kernel/yama/"
                        "ptrace_scope\n"
                        "to allow gdb here for the next freeze.)\n"
                        "stderr head:\n  " + "\n  ".join(err))
        except subprocess.TimeoutExpired:
            lines.append("(gdb attach timed out after 10s — skipped)")
        except Exception as e:
            lines.append(f"(gdb attach failed: {e!r})")

        try:
            path.write_text("\n".join(lines) + "\n")
        except Exception as e:
            print(f"[freeze report] write failed: {e!r}", flush=True)
            return ""
        print(f"[engine watchdog] freeze report saved to {path}",
              flush=True)
        return str(path)

    def _handle_trick_complete(self):
        """Handle completed trick - auto-advance when the human side won
        the trick (so the user just plays the next card without an
        intervening click); enable Next-card otherwise.

        Spacebar is wired up at construction time as a shortcut on the
        Next-card button, so even when the button is enabled the user
        doesn't have to reach for the mouse.
        """
        winner = self.controller.get_trick_winner()
        if winner is None:
            return

        self.table_view.show_trick_winner(winner)
        self.table_view.update_tricks(
            self.controller.board.declarer_tricks,
            self.controller.board.defense_tricks
        )

        human_side_won = self._winner_is_local_partnership(winner)

        # Network mode: the host/guest who actually played the LAST
        # card of the trick is responsible for emitting the trick-clear,
        # so anyone else just waits. Independent of who *won*: the
        # winning side may all be remote, in which case we still wait.
        if self.network_controller.is_active:
            last_trick = (self.controller.board.tricks[-1]
                          if self.controller.board.tricks else None)
            if last_trick and len(last_trick.cards) == 4:
                last_player_seat = Seat((last_trick.leader.value + 3) % 4)
                declarer = self.controller.declarer
                dummy = self.controller.dummy
                actual_player = (declarer if last_player_seat == dummy
                                 else last_player_seat)
                remote_played_last = self.network_controller.is_remote_seat(
                    actual_player
                )
                if remote_played_last:
                    self.next_card_btn.setEnabled(False)
                    who = ("partner"
                           if self.network_controller.client_role == "partner"
                           else "opponent")
                    self.status_label.setText(
                        f"Trick won by {winner.to_char()}. Waiting for {who}..."
                    )
                    return

                # I (or an AI seat I drive) played last. If our side won,
                # auto-advance so the next lead drops straight in. If
                # the opponents won, leave the button on so we can press
                # 'next card' / spacebar deliberately.
                if human_side_won or self.autoplay_btn.isChecked():
                    self.next_card_btn.setEnabled(False)
                    self.status_label.setText(f"Trick won by {winner.to_char()}.")
                    QTimer.singleShot(400, self._on_next_card)
                else:
                    self.next_card_btn.setEnabled(True)
                    self.status_label.setText(
                        f"Trick won by {winner.to_char()}. "
                        "Press Next card (or Space)."
                    )
                return

        # Single-player.
        if human_side_won or self.autoplay_btn.isChecked():
            self.next_card_btn.setEnabled(False)
            self.status_label.setText(f"Trick won by {winner.to_char()}.")
            QTimer.singleShot(400, self._on_next_card)
        else:
            self.next_card_btn.setEnabled(True)
            self.status_label.setText(
                f"Trick won by {winner.to_char()}. Press Next card (or Space)."
            )

    def _winner_is_local_partnership(self, winner: Seat) -> bool:
        """Return True if the just-won trick was taken by a seat the
        local human controls (themself, their partner if AI, or the
        dummy when the human is declarer)."""
        if self.network_controller.is_active:
            # Network: the local player owns one or more seats. A win on
            # any of those — or on a seat their *partner* (also a remote
            # human) owns — counts as "our side". For simplicity we
            # treat both partnership members as local if either is
            # human-controlled by anybody at this client.
            try:
                if self.network_controller.is_my_seat(winner):
                    return True
                # If my seat's partner won, treat as my side too.
                my_seats = list(self.network_controller.my_seats or [])
                if my_seats and any(s.partner() == winner for s in my_seats):
                    return True
            except Exception:
                pass
            return False
        # Single-player.
        return bool(self.controller._human_controls_seat(winner))

    def _show_result(self):
        """Show deal result"""
        board = self.controller.board

        self.next_card_btn.setEnabled(False)
        self.next_deal_btn.setVisible(True)  # Show next deal button when finished
        self.right_panel.setVisible(True)  # Show right panel again

        # Refresh tricks display so it reflects all 13 tricks
        self.table_view.update_tricks(
            board.declarer_tricks,
            board.defense_tricks
        )

        if board.is_passed_out():
            self.status_label.setText("Passed out")
            self.analysis_label.setText("All four players passed.\nNo score.")

            # Show passed out dialog for teams match
            if self.teams_match is not None:
                dialog = PassedOutDialog(self)
                dialog.exec()
            return

        # Calculate score
        contract = board.contract
        tricks = board.declarer_tricks
        vulnerable = board.vulnerability.is_vulnerable(contract.declarer)

        score = self.engine.calculate_score(contract, tricks, vulnerable)

        result_str = ""
        target = contract.target_tricks()
        if tricks >= target:
            overtricks = tricks - target
            if overtricks == 0:
                result_str = "Made"
            else:
                result_str = f"+{overtricks}"
        else:
            undertricks = target - tricks
            result_str = f"-{undertricks}"

        text = f"Contract: {contract.to_str()} by {contract.declarer.to_char()}\n"
        text += f"Result: {tricks} tricks ({result_str})\n"
        text += f"Score: {score:+d}\n"

        self.analysis_label.setText(text)
        self.status_label.setText(f"Deal complete: {contract.to_str()} {result_str}")

        # If this is a teams match, show the end-of-hand dialog
        if self.teams_match is not None and self.match_controller is not None:
            # Complete the open room result
            self.match_controller.complete_open_room(board.board_number, board)

            # Now run the closed room (after human finishes to avoid concurrent engine access)
            self.status_label.setText("Running closed room...")
            QApplication.processEvents()

            # Start closed room and wait for completion
            self._closed_room_result = None
            self.match_controller.start_closed_room_async(
                board.board_number,
                callback=self._on_closed_room_complete
            )

            # Wait for closed room to complete (with timeout)
            import time
            timeout = 60  # 60 seconds max
            start_time = time.time()
            while not self.match_controller.is_board_complete(board.board_number):
                QApplication.processEvents()
                time.sleep(0.1)
                if time.time() - start_time > timeout:
                    print("Closed room timeout", flush=True)
                    break

            # Calculate score for the dialog
            ns_score = score if contract.declarer.is_ns() else -score

            # Get IMP swing if closed room is complete
            imp_swing = None
            if self.match_controller.is_board_complete(board.board_number):
                imp_swing = self.teams_match.get_imp_swing(board.board_number)

            # Show end of hand dialog
            dialog = EndOfHandDialog(
                contract_str=contract.to_str(),
                declarer=contract.declarer.to_char(),
                result_str=result_str,
                score=ns_score,
                imp_swing=imp_swing,
                is_teams_match=True,
                parent=self
            )
            dialog.view_other_table.connect(self._on_view_teams_score)
            dialog.exec()

        # Log the completed hand. The logger needs all four original hands
        # to compute the Pavlicek deal id; a guest only ever has its own
        # seat, so the call would KeyError. Skip on guests.
        if not (self.network_controller.is_active
                and not self.network_controller.is_server):
            try:
                self.game_logger.log_hand(board, self.original_hands)
            except Exception as e:
                print(f"Error logging hand: {e}", flush=True)

        # Add result to scoring table
        try:
            ns_score = score if contract.declarer.is_ns() else -score
            ew_score = -ns_score

            # pavlicek_id needs all four hands. A guest only has its own seat
            # (and dummy after the reveal), so the encoding will KeyError —
            # don't let that drop the whole result from the score table.
            hands_for_pavlicek = self.original_hands or board.hands
            try:
                pavlicek_id = format_deal_base72(deal_to_number(hands_for_pavlicek))
            except Exception:
                pavlicek_id = ""

            # Create a BenBoardRun for replay from the score table.
            # Stamp it with the system names that were actually in
            # use at the time — pulled from preferences (per-pair
            # override, or native_bidding_system, or last-resort
            # SAYC). Without this the run defaulted to "BEN-NN",
            # mislabelling every deal as having been played by the
            # legacy neural net even when the native rule-based
            # bidder produced the auction.
            ns_sys_name, ew_sys_name = self._current_pair_systems()
            from ben_backend.models import BenBoardRun, BenTable
            board_run = BenBoardRun(
                table=BenTable.OPEN,
                board_number=board.board_number,
                pavlicek_id=pavlicek_id,
                original_hands=self.original_hands or board.hands,
                auction=list(board.auction) if board.auction else [],
                tricks=list(board.tricks) if board.tricks else [],
                contract=contract,
                declarer_tricks=tricks,
                ns_score=ns_score,
                ew_score=ew_score,
                played=True,
                ns_bidding_system=ns_sys_name,
                ew_bidding_system=ew_sys_name,
            )

            result = BoardResult(
                board_number=board.board_number,
                pavlicek_id=pavlicek_id,
                dealer=board.dealer,
                vulnerability=board.vulnerability,
                contract=contract,
                declarer=contract.declarer,
                tricks_made=tricks,
                ns_score=ns_score,
                ew_score=ew_score,
                board_run=board_run,
            )
            self.scoring_table.add_result(result)
        except Exception as e:
            print(f"Error adding to scoring table: {e}", flush=True)

        # Show all hands at end
        for seat in Seat:
            self.table_view.set_hand_visible(seat, True)

        # Post-hand sequence (normal play only, not teams match):
        # 1. Launch the GUI harness so the host can manually replay the
        #    deal in Q-Plus — that's the only closed room ben_bridge runs;
        #    AI vs AI replay is no longer fired automatically (it doubled
        #    engine load on the network and isn't a real comparison).
        # 2. Show scoring table.
        #
        # Claude analysis is intentionally NOT triggered here — it runs
        # later, either right after a Q-Plus ingest (so it can compare
        # both rooms) or, if no ingest happens, at "Next Deal" time so
        # the user gets at least an open-room critique. _claude_pending
        # tracks the last completed board so we don't re-run Claude.
        is_guest = (self.network_controller.is_active
                    and not self.network_controller.is_server)
        if self.teams_match is None and self.match_controller is None:
            if not is_guest:
                self._launch_qplus_harness(board)
                # Snapshot enough context to fire Claude on demand later.
                self._claude_pending = {
                    'board': board,
                    'contract': contract,
                    'tricks': tricks,
                    'result_str': result_str,
                    'score': score,
                    'analyzed': False,
                }
            self._on_show_scores()

    def _launch_qplus_harness(self, board):
        """Spawn the guiHarness (bridgeHarness.sh) preloaded with this deal's
        base-72 code, dealer, and vulnerability, so the host can manually
        play the closed room in Q-Plus without leaving ben_bridge. No-op
        if the harness script can't be located or if the deal has no full
        hand data.

        Dealer and vulnerability are passed via `--dealer` / `--vuln` so
        the harness can show them on the entry tab — and, once Q-Plus's
        dealer / vulnerability radio buttons are calibrated, click them
        for the user as part of the entry sequence. Matching the BDL's
        dealer/vuln in Q-Plus is required for the closed-room contract
        to be scored against the same conditions as the open room.
        """
        import os
        import subprocess
        try:
            hands = self.original_hands or board.hands
            if not all(s in hands and len(hands[s].cards) == 13 for s in Seat):
                # Hands have already been played — original_hands is the
                # canonical pre-play snapshot. If it's missing seats, skip.
                return
            code = int_to_base72(deal_to_number(hands))
            # bridgeHarness.sh sits at FRI/bridgeHarness.sh — three levels
            # above this file (ui/main_window.py → ben_bridge → benBridge → FRI).
            script = os.path.normpath(os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "bridgeHarness.sh"
            ))
            if not os.path.isfile(script):
                return
            # Map ben_bridge enums to the harness's expected CLI tokens.
            dealer_char = board.dealer.to_char()  # 'N' / 'E' / 'S' / 'W'
            vuln_map = {
                'None': 'None',
                'N-S':  'NS',
                'E-W':  'EW',
                'Both': 'Both',
            }
            vuln_token = vuln_map.get(board.vulnerability.value, 'None')
            subprocess.Popen(
                [script, "--base72", code,
                 "--dealer", dealer_char,
                 "--vuln", vuln_token],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            print(f"[qplus harness] launch failed: {e}", flush=True)

    def _show_claude_hand_analysis(self, board, contract, tricks, result_str, score):
        """Show a progress bar while Claude analyzes, then display results in a dialog.

        If we've already analysed this exact board+deal in this session,
        the result is replayed from `_claude_hand_logs` without spending
        another Claude call. The persisted version on disk lives in the
        BDL log (Commentary block, written by _append_commentary_to_bdl),
        so even across restarts the user sees the same wording when
        opening the BDL log file.
        """
        import shutil
        import subprocess
        import threading
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                                      QScrollArea, QProgressBar)
        from PyQt6.QtGui import QFont
        from PyQt6.QtCore import QTimer

        # Cache key: (board_number, pavlicek_id). Pavlicek differentiates
        # two hands that happen to share a board number (replays etc.);
        # if we couldn't compute it, the board number alone keys the
        # cache for this session.
        try:
            hands_for_pavlicek = self.original_hands or board.hands
            if all(s in hands_for_pavlicek for s in Seat):
                cache_pavlicek = format_deal_base72(deal_to_number(hands_for_pavlicek))
            else:
                cache_pavlicek = ""
        except Exception:
            cache_pavlicek = ""
        cache_key = (board.board_number, cache_pavlicek)
        cached = self._claude_hand_logs.get(cache_key)
        if cached is not None:
            # Re-display the saved annotated BDL — no Claude call.
            self._show_annotated_bdl_dialog(
                title="Claude Analysis (cached)",
                bdl_text=cached.get('bdl', ''),
                claude_text=cached.get('claude', ''),
                error=False,
            )
            return

        if not shutil.which('claude'):
            return

        # Build hand summary for Claude as a full BDL snapshot. Claude
        # reads seat letters off the BDL N/E/S/W column headers and the
        # leader/winner markers in the Tricks block instead of trying to
        # walk the auction order to attribute bids — that mis-attribution
        # is what caused earlier annotations to confuse who did what.
        seat_names = {Seat.NORTH: 'N', Seat.EAST: 'E', Seat.SOUTH: 'S', Seat.WEST: 'W'}
        suit_symbols = {Suit.SPADES: 'S', Suit.HEARTS: 'H', Suit.DIAMONDS: 'D',
                        Suit.CLUBS: 'C', Suit.NOTRUMP: 'NT'}

        from .game_logger import build_bdl_snapshot
        deal_id = ""
        try:
            hands_for_pavlicek = self.original_hands or board.hands
            if all(s in hands_for_pavlicek for s in Seat):
                deal_id = format_deal_base72(deal_to_number(hands_for_pavlicek))
        except Exception:
            deal_id = ""

        result_summary = (
            f"Result: {tricks} tricks ({result_str}), declarer-side score "
            f"{score:+d}."
        )
        hand_text = build_bdl_snapshot(
            board,
            original_hands=self.original_hands,
            viewer_seat=None,           # end-of-hand: every hand is on display
            phase='finished',
            dummy_visible_to_viewer=True,
            contract=contract,
            result_summary=result_summary,
            deal_id=deal_id,
        ) + "\n"

        # Pull the closed-room result (populated by Q-Plus ingest) so Claude
        # can compare the human's table against the manual closed room.
        # Look for a BoardResult tagged "Closed room" for this board and
        # carrying a played BenBoardRun.
        closed_run = None
        imp_swing = None
        for r in self.scoring_table.results:
            if r.board_number != board.board_number:
                continue
            if (r.notes and "Closed room" in r.notes
                    and r.board_run is not None
                    and getattr(r.board_run, 'played', False)):
                closed_run = r.board_run
                break

        closed_summary = ""
        if closed_run and closed_run.contract:
            c_target = closed_run.contract.target_tricks()
            c_diff = closed_run.declarer_tricks - c_target
            c_result = f"+{c_diff}" if c_diff > 0 else ("=" if c_diff == 0 else str(c_diff))
            ns_open = score if contract.declarer.is_ns() else -score
            ns_diff = ns_open - closed_run.ns_score
            from ben_backend.scoring import diff_to_imps
            try:
                imp_swing = diff_to_imps(ns_diff)
            except Exception:
                imp_swing = None
            closed_summary = (
                f"\nClosed room (Q-Plus, manual replay by host): "
                f"{closed_run.contract.to_str()} by {closed_run.contract.declarer.to_char()}, "
                f"{closed_run.declarer_tricks} tricks ({c_result}), "
                f"NS {closed_run.ns_score:+d}"
            )
            if imp_swing is not None:
                closed_summary += (
                    f"\nIMP swing of open vs closed (NS perspective): "
                    f"{imp_swing:+d}"
                )
            closed_summary += "\n"
        hand_text += closed_summary

        human_seats = [f"{seat_names[s]} ({p.name})"
                       for s, p in self.controller.players.items()
                       if p.player_type == PlayerType.HUMAN]
        human_desc = ", ".join(human_seats) if human_seats else "South"

        # Clear remaining cards from hands and show last trick on table
        try:
            # Remove all cards from hand displays (all 52 cards have been played)
            for seat in Seat:
                hw = self.table_view.hand_widgets.get(seat)
                if hw:
                    hw.clear()
            # Show the last trick on the green table
            last_trick = board.tricks[-1] if board.tricks else None
            if last_trick and len(last_trick.cards) == 4:
                self.table_view.clear_trick()
                for i, card in enumerate(last_trick.cards):
                    seat = Seat((last_trick.leader.value + i) % 4)
                    is_winner = (seat == last_trick.winner)
                    self.table_view.play_card_to_trick(seat, card, is_winner)
            QApplication.processEvents()
        except Exception:
            pass

        # Show progress dialog while Claude thinks
        progress = QDialog(self)
        progress.setWindowTitle("Claude Analysis")
        progress.setFixedSize(400, 100)
        progress.setStyleSheet("background-color: #e8e8f0; color: #000;")
        p_layout = QVBoxLayout(progress)
        p_label = QLabel("Claude is analyzing the hand...")
        p_label.setFont(QFont("Arial", 12))
        p_label.setStyleSheet("color: #000;")
        p_layout.addWidget(p_label)
        p_bar = QProgressBar()
        p_bar.setRange(0, 0)  # Indeterminate
        p_bar.setStyleSheet("QProgressBar { border: 1px solid #aaa; border-radius: 3px; }"
                            "QProgressBar::chunk { background-color: #4a9; }")
        p_layout.addWidget(p_bar)
        progress.show()
        QApplication.processEvents()

        # Write a pidfile so run.sh can wait for us before exiting (and before
        # the launcher moves the BDL out from under _append_commentary_to_bdl).
        pidfile = None
        pid_dir = os.environ.get('CRITIQUE_PID_DIR')
        if pid_dir:
            try:
                os.makedirs(pid_dir, exist_ok=True)
                pidfile = os.path.join(pid_dir, f"{os.getpid()}-{id(board)}.pid")
                with open(pidfile, 'w') as f:
                    f.write(str(os.getpid()))
            except Exception:
                pidfile = None

        # Run Claude in background thread
        result_holder = {'critique': None, 'error': None}

        comparison_note = ""
        if closed_run:
            comparison_note = (
                " Compare the open-room result (the human player's table) "
                "with the closed-room result (Q-Plus, manual replay) "
                "and comment on who did better and why."
            )

        def _run_claude():
            try:
                analysis_prompt = (
                    "You are a bridge teacher. Annotate this hand by "
                    "echoing the BDL log VERBATIM and inserting "
                    "annotation lines that BEGIN with '>>' (two right "
                    "angle brackets followed by a space) at logical "
                    "section breaks.\n\n"
                    "MANDATORY OUTPUT FORMAT:\n"
                    "  • Reproduce the BDL exactly, line by line, "
                    "preserving every non-annotation line.\n"
                    "  • After the Bids block, insert one or more '>>' "
                    "lines that critique the auction (sound? off-shape? "
                    "missed game?).\n"
                    "  • After the Tricks block, insert '>>' lines that "
                    "critique the play and defense, naming specific "
                    "tricks where decisions mattered.\n"
                    "  • At the very end, add a '>> Verdict:' line with "
                    "your overall takeaway in one short sentence.\n"
                    "  • Read seat letters straight from the N/E/S/W "
                    "column headers in Bids and the leader/winner "
                    "markers in Tricks — never infer a seat from order.\n"
                    "  • Keep each annotation under ~25 words; multiple "
                    "short ones beat one long paragraph.\n"
                    "  • Do not output anything outside the BDL frame.\n\n"
                    f"The human player(s) at the open room: {human_desc}."
                    f"{comparison_note}\n\n"
                    f"BDL:\n{hand_text}"
                )
                # Opus 4.7 with extended thinking, longer timeout to
                # accommodate think-then-write for full hand annotations.
                r = subprocess.run(
                    ['claude', '-p',
                     '--model', 'claude-opus-4-7',
                     '--thinking', 'enabled',
                     '--max-turns', '1', analysis_prompt],
                    capture_output=True, text=True, timeout=300
                )
                stdout = (r.stdout or '').strip()
                stderr = (r.stderr or '').strip()
                if r.returncode == 0 and len(stdout) > 10:
                    result_holder['critique'] = stdout
                else:
                    parts = [f"claude exited {r.returncode}"]
                    if stderr:
                        parts.append(f"stderr: {stderr[:500]}")
                    if stdout:
                        parts.append(f"stdout: {stdout[:500]}")
                    result_holder['error'] = "\n".join(parts)
            except subprocess.TimeoutExpired:
                result_holder['error'] = "claude timed out after 300 seconds."
            except Exception as e:
                result_holder['error'] = f"claude call failed: {e!r}"

        thread = threading.Thread(target=_run_claude, daemon=True)
        thread.start()

        # Poll until thread finishes (keeps UI responsive)
        while thread.is_alive():
            QApplication.processEvents()
            thread.join(timeout=0.1)

        progress.close()

        critique = result_holder['critique']
        error = result_holder['error']

        # Save critique to BDL file
        if critique:
            try:
                self.game_logger._append_commentary_to_bdl(critique)
            except Exception as e:
                print(f"Failed to append commentary to BDL: {e}", flush=True)

        # Remove pidfile now that critique is written — run.sh can stop waiting.
        if pidfile:
            try:
                os.unlink(pidfile)
            except OSError:
                pass

        # Build a short open-vs-closed summary header so the user sees
        # the objective numbers even if Claude failed; the BDL view then
        # follows with Claude's annotations interspersed.
        summary_header = ""
        if closed_run and closed_run.contract:
            c_target = closed_run.contract.target_tricks()
            c_diff = closed_run.declarer_tricks - c_target
            c_result = (f"+{c_diff}" if c_diff > 0
                        else ("=" if c_diff == 0 else str(c_diff)))
            ns_open = score if contract.declarer.is_ns() else -score
            summary_header = (
                f"Open room:   {contract.to_str()} by {contract.declarer.to_char()}  "
                f"{tricks} tricks ({result_str})  NS {ns_open:+d}\n"
                f"Closed room: {closed_run.contract.to_str()} by "
                f"{closed_run.contract.declarer.to_char()}  "
                f"{closed_run.declarer_tricks} tricks ({c_result})  "
                f"NS {closed_run.ns_score:+d}"
            )
            if imp_swing is not None:
                side = 'N/S' if imp_swing >= 0 else 'E/W'
                summary_header += f"\nIMP: {imp_swing:+d} ({side})"
            summary_header += "\n\n"

        framed_bdl = (summary_header + hand_text) if summary_header else hand_text
        self._show_annotated_bdl_dialog(
            title="Claude Analysis",
            bdl_text=framed_bdl,
            claude_text=critique or "",
            error=not critique,
        )
        # Cache the successful analysis so reopening "Hand Log" later
        # for this same hand redraws the saved annotated BDL instead of
        # firing another Claude call. We deliberately don't cache
        # failures — the user can retry on the next click.
        if critique:
            self._claude_hand_logs[cache_key] = {
                'bdl': framed_bdl,
                'claude': critique,
                'board_number': board.board_number,
                'pavlicek_id': cache_pavlicek,
            }
        if not critique:
            self._show_plain_dialog(
                "Claude Analysis (claude error)",
                "Claude did not return an analysis for this hand.\n\n"
                f"{error or 'No output received.'}",
                error=True,
            )

    def _start_parallel_closed_room(self, board):
        """Kick off the all-AI closed room the moment a new deal is dealt.

        The closed room then runs in parallel with the human's play, and when
        the human finishes _auto_closed_room just joins the pending worker
        instead of starting a fresh (slow) run.
        """
        # Skip when teams/match modes manage their own closed room.
        if self.teams_match is not None or self.match_controller is not None:
            return
        # Cancel any previous pending room (e.g. user hit "Next deal" early).
        self._cancel_pending_closed_room()
        try:
            import uuid
            from ben_backend.models import BenTeamsMatch
            from ben_backend.match_controller import TeamsMatchController

            board_num = board.board_number
            temp_match = BenTeamsMatch(
                match_id=str(uuid.uuid4()),
                num_boards=1,
                current_board=board_num,
            )
            temp_controller = TeamsMatchController(self.engine, temp_match)
            temp_controller.start_board(board_num, board)
            temp_controller.start_closed_room_async(board_num)
            self._pending_closed_room = {
                'controller': temp_controller,
                'match': temp_match,
                'board_num': board_num,
            }
            self.status_label.setText(
                f"Board {board_num}: closed room (AI) started in background"
            )
        except Exception as e:
            print(f"Failed to start parallel closed room: {e}", flush=True)
            self._pending_closed_room = None

    def _cancel_pending_closed_room(self):
        """Stop any running closed-room worker and discard its pending record."""
        pending = getattr(self, '_pending_closed_room', None)
        if not pending:
            return
        try:
            pending['controller'].stop_closed_room()
        except Exception:
            pass
        self._pending_closed_room = None

    def _auto_closed_room(self, board, contract, tricks, result_str, score):
        """Join the parallel closed-room worker and post its result.

        Started by _start_parallel_closed_room at deal time. If the user
        finishes faster than the AI, waits for completion with a progress dialog.
        Falls back to starting the closed room here if none was pre-started.
        """
        import time
        import uuid
        from ben_backend.models import BenTeamsMatch, BenTable
        from ben_backend.match_controller import TeamsMatchController
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
        from PyQt6.QtGui import QFont

        board_num = board.board_number
        ns_score = score if contract.declarer.is_ns() else -score

        # Reuse the pre-started pending worker if it's for this board.
        pending = getattr(self, '_pending_closed_room', None)
        if pending and pending.get('board_num') == board_num:
            temp_controller = pending['controller']
            temp_match = pending['match']
            # Record the open-room outcome the user just played.
            try:
                temp_controller.complete_open_room(board_num, board)
            except Exception:
                pass
        else:
            # No pre-started worker — fall back to running it now.
            temp_match = BenTeamsMatch(
                match_id=str(uuid.uuid4()),
                num_boards=1,
                current_board=board_num,
            )
            temp_controller = TeamsMatchController(self.engine, temp_match)
            temp_controller.start_board(board_num, board)
            temp_controller.complete_open_room(board_num, board)
            temp_controller.start_closed_room_async(board_num)

        # If the closed room hasn't finished yet, show a progress dialog while we wait.
        waiting_dialog = None
        if not temp_controller.is_board_complete(board_num):
            waiting_dialog = QDialog(self)
            waiting_dialog.setWindowTitle("Closed Room")
            waiting_dialog.setFixedSize(400, 110)
            waiting_dialog.setStyleSheet("background-color: #e8e8f0; color: #000;")
            w_layout = QVBoxLayout(waiting_dialog)
            w_label = QLabel("Finishing closed room (AI vs AI)...")
            w_label.setFont(QFont("Arial", 12))
            w_label.setStyleSheet("color: #000;")
            w_layout.addWidget(w_label)
            w_bar = QProgressBar()
            w_bar.setRange(0, 0)  # Indeterminate
            w_bar.setStyleSheet("QProgressBar { border: 1px solid #aaa; border-radius: 3px; }"
                                "QProgressBar::chunk { background-color: #4a9; }")
            w_layout.addWidget(w_bar)
            waiting_dialog.show()
            QApplication.processEvents()

        self.status_label.setText("Waiting for closed room (all AI)...")
        QApplication.processEvents()

        # Wait for completion (max 120s, keep UI responsive)
        start_time = time.time()
        while not temp_controller.is_board_complete(board_num):
            QApplication.processEvents()
            time.sleep(0.1)
            if time.time() - start_time > 120:
                self.status_label.setText("Closed room timed out")
                if waiting_dialog is not None:
                    waiting_dialog.close()
                self._pending_closed_room = None
                return

        if waiting_dialog is not None:
            waiting_dialog.close()

        # Get results
        imp_swing = temp_match.get_imp_swing(board_num)
        closed_run = temp_match.board_runs.get(board_num, {}).get(BenTable.CLOSED)
        self._pending_closed_room = None  # done with this one

        # Update the BoardResult in scoring table with closed room data
        if self.scoring_table.results:
            last_result = self.scoring_table.results[-1]
            if last_result.board_number == board_num:
                last_result.imps = imp_swing
                if closed_run and closed_run.played:
                    if closed_run.contract:
                        closed_summary_text = (
                            f"Closed: {closed_run.contract.to_str()} "
                            f"by {closed_run.contract.declarer.to_char()} "
                            f"({closed_run.declarer_tricks} tricks, "
                            f"NS {closed_run.ns_score:+d}). "
                            f"IMP: {imp_swing:+d}"
                        )
                    else:
                        closed_summary_text = (
                            f"Closed: passed out (NS {closed_run.ns_score:+d}). "
                            f"IMP: {imp_swing:+d}"
                        )
                    last_result.notes = closed_summary_text
                    last_result.closed_room_run = closed_run

        # Log the closed room result
        try:
            if closed_run:
                self.game_logger.log_board_run(closed_run)
        except Exception:
            pass

        # Show result with IMP comparison in the side panel
        if closed_run and closed_run.played:
            if closed_run.contract:
                closed_target = closed_run.contract.target_tricks()
                closed_diff = closed_run.declarer_tricks - closed_target
                if closed_diff > 0:
                    closed_result_diff = f"+{closed_diff}"
                elif closed_diff == 0:
                    closed_result_diff = "="
                else:
                    closed_result_diff = str(closed_diff)
                closed_display = (
                    f"{closed_run.contract.to_str()} by "
                    f"{closed_run.contract.declarer.to_char()} — "
                    f"{closed_run.declarer_tricks} tricks ({closed_result_diff})"
                )
            else:
                closed_display = "Passed out"

            imp_text = f"IMP: {imp_swing:+d} {'(N/S)' if imp_swing >= 0 else '(E/W)'}"

            self.analysis_label.setText(
                f"Contract: {contract.to_str()} by {contract.declarer.to_char()}\n"
                f"Result: {tricks} tricks ({result_str})\n"
                f"Score: {ns_score:+d} (N/S)\n\n"
                f"Closed room: {closed_display}\n"
                f"Score: {closed_run.ns_score:+d} (N/S)\n\n"
                f"{imp_text}"
            )

        # Add closed-room result as companion entry so it shows on the
        # scoring table (Contract 2 / N/S 2). Also added for passed-out
        # closed hands — their "Pass" entry is still informative.
        if closed_run and closed_run.played:
            pav_id = (self.scoring_table.results[-1].pavlicek_id
                      if self.scoring_table.results else "")
            closed_result_obj = BoardResult(
                board_number=board_num,
                pavlicek_id=pav_id,
                dealer=board.dealer,
                vulnerability=board.vulnerability,
                contract=closed_run.contract,  # may be None → shown as "Pass"
                declarer=closed_run.contract.declarer if closed_run.contract else None,
                tricks_made=closed_run.declarer_tricks or 0,
                ns_score=closed_run.ns_score,
                ew_score=closed_run.ew_score,
                imps=-imp_swing if imp_swing is not None else None,
                notes="Closed room",
                board_run=closed_run,
            )
            self.scoring_table.results.append(closed_result_obj)

        self.status_label.setText(
            f"Deal complete: {contract.to_str()} {result_str}"
            + (f" | IMP: {imp_swing:+d}" if imp_swing is not None else "")
        )

    @pyqtSlot(object)
    def _on_engine_bid(self, response):
        """Handle bid from engine"""
        if self.controller.current_phase != 'bidding':
            return

        bid = response.action
        bidder = self.controller.current_seat
        self.controller.make_bid(bid)
        self.bidding_box.add_bid(bid)
        self.table_view.update_auction(self.controller.board.auction, self.controller.board.dealer)

        # Broadcast to network if we're the server
        if self.network_controller.is_active and self.network_controller.is_server:
            self.network_controller.broadcast_bid(bidder, bid)

        # Show analysis
        text = f"BEN bid: {bid.symbol()}\n"
        if response.candidates:
            text += "\nCandidates:\n"
            for cand in response.candidates[:5]:
                text += f"  {cand.bid.symbol()}: {cand.score:.3f}\n"
        self.analysis_label.setText(text)

        # Update bid info window - use proper bid interpretation, not engine score
        self._add_bid_to_info(bidder, bid)
        self._update_available_bids()

        # Continue
        QTimer.singleShot(300, self._advance_game)

    @pyqtSlot(object)
    def _on_engine_card(self, response):
        """Handle card from engine"""
        # Get the seat that was requested (stored in engine_worker)
        requested_seat = self.engine_worker.seat if self.engine_worker else None

        if self.controller.current_phase != 'play':
            return

        # Verify the response is for the current seat. Seat is an IntEnum
        # (NORTH==0); use an explicit None check so a NORTH-requested card
        # doesn't fall through the truthiness gate.
        if (requested_seat is not None
                and requested_seat != self.controller.current_seat):
            # Don't play the card if it's for the wrong seat
            QTimer.singleShot(100, self._advance_game)
            return

        if not response.action:
            # Engine returned no card - try to play any legal card as fallback.
            # IMPORTANT: this branch must broadcast just like the success
            # path; otherwise a guest never sees the engine-fallback card
            # (which is exactly how W's opening lead used to disappear from
            # the guest while showing on the host).
            self.status_label.setText(f"Engine error: {response.who}. Trying fallback...")
            seat = self.controller.current_seat
            hand = self.controller.board.hands.get(seat)
            if hand and hand.cards:
                lead_suit = self.controller.get_lead_suit()
                if lead_suit is not None:
                    suit_cards = [c for c in hand.cards if c.suit == lead_suit]
                    card = suit_cards[0] if suit_cards else hand.cards[0]
                else:
                    card = hand.cards[0]
                self.table_view.play_card_to_trick(seat, card)
                self.controller.play_card(card)
                if (self.network_controller.is_active
                        and self.network_controller.is_server):
                    from PyQt6.QtCore import QDateTime
                    print(f"[host engine_card-fallback] "
                          f"t={QDateTime.currentMSecsSinceEpoch()} "
                          f"seat={seat.to_char()} card={card.to_str()}",
                          flush=True)
                    self.network_controller.broadcast_card(seat, card)
                QTimer.singleShot(300, self._advance_game)
            else:
                self.status_label.setText("Error: No cards available to play")
            return

        card = response.action
        seat = self.controller.current_seat

        # Check if this is the opening lead (first card of play)
        is_opening_lead = (len(self.controller.board.tricks) == 0 and
                          (not self.controller.board.current_trick or
                           len(self.controller.board.current_trick.cards) == 0))

        self.table_view.play_card_to_trick(seat, card)
        self.controller.play_card(card)

        # Broadcast to network if we're the server
        if self.network_controller.is_active and self.network_controller.is_server:
            from PyQt6.QtCore import QDateTime
            print(f"[host engine_card] t={QDateTime.currentMSecsSinceEpoch()} "
                  f"seat={seat.to_char()} card={card.to_str()} "
                  f"is_opening_lead={is_opening_lead}",
                  flush=True)
            self.network_controller.broadcast_card(seat, card)

            # Dummy was already broadcast at start of play phase via
            # _advance_play.setup_declarer_play. Skipping the redundant
            # post-opening-lead broadcast.

        # Continue after delay
        if self.controller.current_phase == 'waiting_next':
            # Trick complete
            QTimer.singleShot(500, self._advance_game)
        else:
            QTimer.singleShot(300, self._advance_game)

    @pyqtSlot(str)
    def _on_engine_error(self, error: str):
        """Handle engine error"""
        self.status_label.setText(f"Engine error: {error}")

    def _on_evaluate(self):
        """Handle Evaluate button - show hand evaluation dialog."""
        # Show evaluate dialog during both bidding and play phases
        self._show_evaluate_dialog()

    def _show_evaluate_dialog(self):
        """Show the evaluate dialog for bidding phase."""
        from .dialogs import EvaluateDialog, HandEvaluationDialog

        dialog = EvaluateDialog(self, current_seat=self.controller.current_seat)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            if dialog.own_hand:
                # Show own hand evaluation
                current_seat = self.controller.current_seat
                hand = self.controller.board.hands.get(current_seat)
                if hand:
                    # Count bid round
                    bid_round = len(self.controller.board.auction) // 4 + 1
                    eval_dialog = HandEvaluationDialog(
                        self,
                        seat=current_seat,
                        hand=hand,
                        bid_round=bid_round,
                        board=self.controller.board
                    )
                    eval_dialog.exec()
            else:
                # Ask specific player about specific hand using engine evaluation
                ask_seat = dialog.ask_who
                about_seat = dialog.about_whom
                about_hand = self.controller.board.hands.get(about_seat)
                if about_hand:
                    bid_round = len(self.controller.board.auction) // 4 + 1
                    eval_dialog = HandEvaluationDialog(
                        self,
                        seat=about_seat,
                        hand=about_hand,
                        bid_round=bid_round,
                        board=self.controller.board,
                        ask_seat=ask_seat,
                    )
                    eval_dialog.exec()
                else:
                    self.status_label.setText(f"No hand data for {about_seat}")

    def _on_view_auction_tricks(self):
        """Show the Record (auction + played tricks) dialog detached.

        Non-modal so the user can drag it to a second monitor and watch
        the play unfold next to the main table view. The dialog is
        marked WA_DeleteOnClose, so we just keep the latest reference
        and overwrite it on the next open instead of bookkeeping a list.
        """
        from .dialogs import AuctionTricksDialog

        if not self.controller.board:
            self.status_label.setText("No deal loaded")
            return

        # Collect trick information from board.tricks
        tricks = []
        board = self.controller.board
        if board.tricks:
            for trick in board.tricks:
                cards_dict = {}
                for i, card in enumerate(trick.cards):
                    seat = Seat((trick.leader.value + i) % 4)
                    seat_char = seat.to_char()
                    cards_dict[seat_char] = card

                trick_info = {
                    'leader': trick.leader.to_char(),
                    'cards': cards_dict,
                    'winner': trick.winner.to_char() if trick.winner else ''
                }
                tricks.append(trick_info)

        # If a Record window is already open, close it so we can spawn
        # a fresh one with the latest tricks. The dialog was promoted
        # to a top-level Qt.Window with WA_DeleteOnClose so the C++
        # widget is destroyed the moment the user dismisses it; the
        # Python `_record_dialog` reference outlives that, and any
        # method call on the dangling wrapper raises RuntimeError
        # ("wrapped C/C++ object … has been deleted"). Catch that.
        existing = getattr(self, '_record_dialog', None)
        if existing is not None:
            try:
                if existing.isVisible():
                    existing.close()
            except RuntimeError:
                # C++ side already deleted — drop the stale reference.
                self._record_dialog = None
            except Exception:
                pass

        # Pass the local viewer's seat plus the dummy (when revealed)
        # so the dialog's "Cards in opponents' hands" panel can hide
        # cards we can already see ourselves.
        viewer_seat = None
        try:
            viewer_seat = self.table_view._local_seat
        except Exception:
            viewer_seat = None
        dummy_seat = None
        try:
            if getattr(self.table_view, 'dummy_revealed', False):
                dummy_seat = self.controller.dummy
        except Exception:
            dummy_seat = None
        self._record_dialog = AuctionTricksDialog(
            self,
            board=self.controller.board,
            tricks=tricks,
            viewer_seat=viewer_seat,
            dummy_seat=dummy_seat,
        )
        self._record_dialog.show()
        self._record_dialog.raise_()

    def _on_show_hand_log(self):
        """Reopen the Claude-annotated BDL log for the current hand.

        Order of preference for choosing what to display:
          1. The cached annotated BDL for the most-recently-completed
             hand (built after _show_claude_hand_analysis ran).
          2. Any cached entry for the current board number.
          3. The pending analysis from `_claude_pending` — fires
             `_maybe_run_pending_claude` so we render the same dialog
             as the post-hand path. From then on it's cached.
          4. Status-bar message if there's nothing to show yet.
        """
        # Try the most recent cached hand first — pending snapshot has
        # the right board+pavlicek even if the score sheet has moved on.
        pending = self._claude_pending
        if pending and pending.get('analyzed'):
            board = pending.get('board')
            try:
                hands = self.original_hands or board.hands
                pav = (format_deal_base72(deal_to_number(hands))
                       if board and all(s in hands for s in Seat) else "")
            except Exception:
                pav = ""
            if board is not None:
                key = (board.board_number, pav)
                cached = self._claude_hand_logs.get(key)
                if cached is None:
                    # Fallback: pavlicek may have differed slightly;
                    # match on board number alone.
                    for k, v in self._claude_hand_logs.items():
                        if k[0] == board.board_number:
                            cached = v
                            break
                if cached is not None:
                    self._show_annotated_bdl_dialog(
                        title=f"Hand Log — Board {board.board_number} (cached)",
                        bdl_text=cached.get('bdl', ''),
                        claude_text=cached.get('claude', ''),
                        error=False,
                    )
                    return

        # Nothing cached yet but there IS a pending hand — run / render
        # for the first time. _maybe_run_pending_claude is idempotent
        # via its 'analyzed' flag, so we clear that to force a render
        # if the user explicitly asked.
        if pending is not None:
            pending['analyzed'] = False
            self._maybe_run_pending_claude()
            return

        # Brand-new session, nothing to show.
        self.status_label.setText(
            "No hand analysis yet — finish a hand first."
        )

    def _on_edit_remark(self):
        """Edit remark for current deal."""
        from .dialogs import RemarkDialog

        if not self.controller.board:
            self.status_label.setText("No deal loaded")
            return

        # Get existing remark if any
        remark = getattr(self.controller.board, 'remark', None) or {}

        dialog = RemarkDialog(self, board=self.controller.board, remark=remark)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.controller.board.remark = dialog.get_remark()
            self.status_label.setText("Remark saved")

    def _on_view_remark(self):
        """View remark for current deal."""
        from .dialogs import ViewRemarkDialog

        if not self.controller.board:
            self.status_label.setText("No deal loaded")
            return

        remark = getattr(self.controller.board, 'remark', None)
        if not remark or not remark.get('text'):
            self.status_label.setText("No remark for this deal")
            return

        dialog = ViewRemarkDialog(self, board=self.controller.board, remark=remark)
        dialog.exec()

    def _on_show_current_log(self):
        """Show current session log file."""
        from .dialogs.log_viewer_dialog import LogViewerDialog
        import os

        # Use the GameLogger's current log file directly
        current_log = self.game_logger.current_log_file

        if current_log and os.path.exists(current_log):
            dialog = LogViewerDialog(self, str(current_log), "Current Session Log")
            dialog.exec()
        else:
            self.status_label.setText(f"No log file found - play a hand to create one")

    def _on_show_previous_logs(self):
        """Show previous log files dialog."""
        from .dialogs.log_viewer_dialog import PreviousLogsDialog

        # Use the same log directory as the GameLogger
        log_dir = str(self.game_logger.log_dir)
        os.makedirs(log_dir, exist_ok=True)

        dialog = PreviousLogsDialog(self, log_dir)
        dialog.exec()

    def _on_bid_list(self):
        """Show list of possible bids with meanings."""
        from .dialogs import BidListDialog

        if self.controller.current_phase != 'bidding':
            self.status_label.setText("List is only available during bidding")
            return

        dialog = BidListDialog(
            self,
            seat=self.controller.current_seat,
            auction=self.controller.board.auction if self.controller.board else []
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_bid = dialog.get_selected_bid()
            if selected_bid:
                # Could auto-select the bid here
                self.status_label.setText(f"Selected: {selected_bid}")

    def _on_claim(self):
        """Handle claim button - claim remaining tricks."""
        from .dialogs import ClaimDialog

        if self.controller.current_phase != 'play':
            self.status_label.setText("Claim is only available during play")
            return

        if not self.controller.board or not self.controller.board.contract:
            return

        # Calculate tricks
        declarer_tricks = getattr(self.controller, 'declarer_tricks', 0)
        defense_tricks = getattr(self.controller, 'defense_tricks', 0)
        remaining = 13 - declarer_tricks - defense_tricks

        if remaining <= 0:
            self.status_label.setText("No tricks remaining to claim")
            return

        # Is current player declarer or dummy's partner?
        declarer = self.controller.board.contract.declarer
        current = self.controller.current_seat
        is_declarer_side = (
            current == declarer or
            current.partner() == declarer
        )

        dialog = ClaimDialog(
            self,
            remaining_tricks=remaining,
            declarer_tricks=declarer_tricks,
            defense_tricks=defense_tricks,
            is_declarer=is_declarer_side
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            claimed = dialog.get_claimed_tricks()
            if dialog.verify:
                # Verify with DD solver
                self.status_label.setText("Verifying claim...")
                # Would use DD solver to verify
                self.status_label.setText(f"Claim verified: Declarer makes {declarer_tricks + claimed}")
            else:
                # Accept claim
                final_declarer = declarer_tricks + claimed
                final_defense = defense_tricks + (remaining - claimed)
                self.status_label.setText(
                    f"Claim accepted: Declarer {final_declarer}, Defense {final_defense}"
                )
                # Would end the hand here
                self.controller.current_phase = 'finished'

    def _update_button_states(self):
        """Update enabled state of toolbar buttons based on game phase."""
        phase = self.controller.current_phase

        # Undo button - only during play when there are human cards to undo
        # Disabled during network play to prevent sync issues
        if hasattr(self, 'undo_btn'):
            can_undo = (phase == 'play' and
                       len(self.card_history) > 0 and
                       any(h[2] for h in self.card_history) and  # h[2] is is_human
                       not self.network_controller.is_active)  # Disable during network play
            self.undo_btn.setEnabled(can_undo)

        # Claim button - only during play
        if hasattr(self, 'claim_btn'):
            self.claim_btn.setEnabled(phase == 'play')

        # Review button - only after hand is finished
        if hasattr(self, 'review_btn'):
            self.review_btn.setEnabled(phase == 'finished')

    def _on_review(self):
        """Review the completed hand."""
        from .dialogs import ReviewDialog

        if not self.controller.board:
            self.status_label.setText("No deal to review")
            return

        # Collect trick information
        tricks = []
        if hasattr(self.controller, 'played_tricks') and self.controller.played_tricks:
            tricks = self.controller.played_tricks

        contract_str = None
        if self.controller.board.contract:
            contract_str = str(self.controller.board.contract)

        dialog = ReviewDialog(
            self,
            board=self.controller.board,
            auction=self.controller.board.auction,
            tricks=tricks,
            contract=contract_str
        )
        dialog.exec()

    def _on_previous_deal(self):
        """Go to the previous deal."""
        if not self.controller.board:
            self.status_label.setText("No current deal")
            return

        current_num = self.controller.board.board_number
        if current_num <= 1:
            self.status_label.setText("Already at first deal")
            return

        # Generate previous deal
        prev_num = current_num - 1
        self.status_label.setText(f"Loading deal #{prev_num}...")

        # Create new board with previous number
        from ben_backend.models import BoardState
        new_board = self.engine.random_deal(prev_num)

        # Setup the new deal
        self.controller.board = new_board
        self.controller.current_phase = 'bidding'
        self.controller.current_seat = new_board.dealer

        # Reset UI
        self._display_deal(new_board)
        self._update_button_states()
        self.status_label.setText(f"Deal #{prev_num} loaded")

    def _on_lead_signal(self, pair: str):
        """Show lead and signalling conventions dialog."""
        from .dialogs import LeadSignalDialog

        dialog = LeadSignalDialog(self, pair=pair)
        dialog.exec()

    def _on_strength(self):
        """Show playing strength dialog."""
        from .dialogs import StrengthDialog

        dialog = StrengthDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_label.setText("Strength settings saved")

    def _on_config_check(self):
        """Show configuration check dialog."""
        from .dialogs import ConfigCheckDialog

        dialog = ConfigCheckDialog(self)
        dialog.exec()

    def _on_minibridge(self):
        """Toggle or configure MiniBridge mode."""
        from .dialogs import MiniBridgeDialog

        # Get current state
        current_enabled = getattr(self, '_minibridge_enabled', False)

        dialog = MiniBridgeDialog(self, enabled=current_enabled)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._minibridge_enabled = dialog.is_minibridge_enabled()
            self.minibridge_action.setChecked(self._minibridge_enabled)

            if self._minibridge_enabled:
                self.status_label.setText("MiniBridge mode enabled")
            else:
                self.status_label.setText("Standard Bridge mode")

    def _on_multiplay(self):
        """Show computer multiplay dialog."""
        from .dialogs import MultiplayDialog

        dialog = MultiplayDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            # Would start multiplay mode here
            self.status_label.setText(
                f"Computer multiplay: {settings['num_deals']} deals"
            )
            # Enable autoplay for all positions
            for seat in Seat:
                self.controller.players[seat].player_type = PlayerType.COMPUTER

            # Start first deal
            if settings['num_deals'] > 0:
                self._on_new_deal()
                self.autoplay_btn.setChecked(True)

    def _on_rubber_scoring(self):
        """Show rubber scoring dialog."""
        from .dialogs import RubberScoringDialog

        dialog = RubberScoringDialog(self)
        dialog.exec()

    def _maybe_run_pending_claude(self):
        """Run Claude on the most recently finished hand if it's still
        pending. Idempotent — sets `analyzed=True` so subsequent calls
        from a different trigger (ingest then next-deal, etc.) are a
        no-op. By the time Claude actually runs, the score sheet has
        whatever closed-room data the user managed to attach (or none),
        so the prompt automatically gets the comparison form when a
        Q-Plus row is present and the open-room-only form otherwise.
        """
        pending = self._claude_pending
        if not pending or pending.get('analyzed'):
            return
        pending['analyzed'] = True
        try:
            self._show_claude_hand_analysis(
                pending['board'],
                pending['contract'],
                pending['tricks'],
                pending['result_str'],
                pending['score'],
            )
        except Exception as e:
            print(f"[claude] deferred analysis failed: {e}", flush=True)

    # ------------------------------------------------------------------
    # Q-Plus closed-room ingest
    # ------------------------------------------------------------------

    def _refresh_qplus_ingest_action_state(self):
        """Enable/disable the ingest menu item based on Q-Plus install
        and current network role. Guests get the score-sheet Compare
        button via host broadcast; they don't ingest themselves."""
        if not hasattr(self, 'ingest_qplus_action'):
            return
        try:
            from ben_backend.qplus import qplus_available
            installed = qplus_available()
        except Exception:
            installed = False
        is_guest = (self.network_controller.is_active
                    and not self.network_controller.is_server)
        enabled = installed and not is_guest
        self.ingest_qplus_action.setEnabled(enabled)
        if not installed:
            self.ingest_qplus_action.setToolTip(
                "Q-Plus Bridge isn't installed. Run FRI/qplus.sh once to install it."
            )
        elif is_guest:
            self.ingest_qplus_action.setToolTip(
                "Closed-room ingest happens on the host; the result will appear here automatically."
            )
        else:
            self.ingest_qplus_action.setToolTip("")

    def _on_load_lin_database(self):
        """Load a LIN file (BBO vugraph) as a closed-room database.

        Each played-out deal in the file is ingested as a closed-room
        BoardResult. If the open-room score sheet already has a row for
        the same board, the LIN result attaches there (so IMPs compute);
        otherwise the LIN deal stands alone in the score sheet, ready
        for a future open-room hand to pair with.
        """
        from ben_backend.lin_reader import (
            load_lin_file, lin_deal_to_board_run
        )
        from ben_backend.models import BenTable

        filename, _ = QFileDialog.getOpenFileName(
            self, "Select LIN file (BBO vugraph)", "",
            "LIN files (*.lin);;All files (*)"
        )
        if not filename:
            return

        try:
            deals = load_lin_file(filename)
        except Exception as e:
            QMessageBox.warning(self, "LIN Read Error",
                                f"Could not parse LIN file:\n{e}")
            return
        if not deals:
            QMessageBox.warning(self, "Empty LIN",
                                "No deals were found in the selected LIN file.")
            return

        ingested = 0
        skipped = 0
        for deal in deals:
            run = lin_deal_to_board_run(deal, table=BenTable.CLOSED)
            if run is None:
                skipped += 1
                continue
            try:
                self._attach_closed_room_run(run, replace_ai_run=True)
                ingested += 1
            except Exception as e:
                print(f"[lin ingest] attach failed for board "
                      f"{deal.board_number}: {e}", flush=True)
                skipped += 1

        # Push the ingested deals to guests so their score sheets line up.
        if (self.network_controller.is_active
                and self.network_controller.is_server):
            for deal in deals:
                run = lin_deal_to_board_run(deal, table=BenTable.CLOSED)
                if run is None:
                    continue
                try:
                    self.network_controller.broadcast_closed_room_ingested(run)
                except Exception as e:
                    print(f"[lin ingest] broadcast failed: {e}", flush=True)

        self.status_label.setText(
            f"Loaded {ingested} LIN deal(s) as closed room"
            + (f" ({skipped} skipped — no contract / no hands)" if skipped else "")
        )

        # Refresh an open Scoring Table dialog so the new rows show up
        # without the user having to reopen it.
        scores = getattr(self, '_scores_dialog', None)
        if scores is not None and scores.isVisible():
            try:
                scores._populate_table()
            except Exception:
                pass

    def _on_ingest_qplus_closed_room(self):
        """File picker → BDL parse → attach run to score sheet → broadcast.

        If multiple deals are present in the BDL, picks the one matching
        the most recent open-room result (by pavlicek_id, falling back
        to board number); if none match, asks the user.
        """
        from ben_backend.qplus import qplus_bdl_log_dir, newest_bdl_path
        from ben_backend.bdl_reader import load_bdl_file, bdl_deal_to_board_run
        from ben_backend.models import BenTable

        # Default the picker to the qplus log dir + newest BDL.
        log_dir = qplus_bdl_log_dir()
        default_path = ""
        newest = newest_bdl_path()
        if newest is not None:
            default_path = str(newest)
        elif log_dir is not None:
            default_path = str(log_dir)

        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Q-Plus BDL file", default_path,
            "BDL files (*.bdl);;All files (*)"
        )
        if not filename:
            return

        try:
            deals = load_bdl_file(filename)
        except Exception as e:
            QMessageBox.warning(self, "BDL Read Error",
                                f"Could not parse BDL file:\n{e}")
            return
        if not deals:
            QMessageBox.warning(self, "Empty BDL",
                                "No deals were found in the selected BDL file.")
            return

        # Pick the deal that matches an existing open-room result, if any.
        chosen = self._pick_bdl_deal_for_ingest(deals)
        if chosen is None:
            return

        run = bdl_deal_to_board_run(chosen, table=BenTable.CLOSED)
        if run is None:
            QMessageBox.warning(self, "Incomplete BDL",
                                "The selected deal is missing the contract or "
                                "the four hands; can't build a closed-room run.")
            return

        attached = self._attach_closed_room_run(run, replace_ai_run=True)
        if not attached:
            QMessageBox.information(
                self, "Closed Room Ingested",
                f"Loaded board {run.board_number}, but no matching open-room "
                "result was found — added as a standalone score-sheet entry."
            )
        else:
            self.status_label.setText(
                f"Closed room ingested for board {run.board_number}."
            )

        # Push to guests so they get the Compare button too.
        if (self.network_controller.is_active
                and self.network_controller.is_server):
            try:
                self.network_controller.broadcast_closed_room_ingested(run)
            except Exception as e:
                print(f"[ingest qplus] broadcast failed: {e}", flush=True)

        # Now that the closed-room run is attached, kick Claude with the
        # comparison form of the prompt. If the hand was passed out or
        # otherwise didn't queue a pending analysis, this is a no-op.
        self._maybe_run_pending_claude()

    def _pick_bdl_deal_for_ingest(self, deals):
        """Choose which BDL deal corresponds to the open-room hand.

        Strategy:
        1. If there's only one deal, use it.
        2. Otherwise, score each candidate by match strength against the
           score sheet's existing open-room results (pavlicek_id beats
           board_number) and pick the strongest match.
        3. If still ambiguous, fall back to the newest deal.
        """
        if len(deals) == 1:
            return deals[0]

        existing = list(self.scoring_table.results) if self.scoring_table else []
        existing_pavs = {r.pavlicek_id for r in existing if r.pavlicek_id}
        existing_boards = {r.board_number for r in existing}

        # Strongest: pavlicek match. Next: board_number match.
        for d in deals:
            if d.pavlicek_id and d.pavlicek_id in existing_pavs:
                return d
        for d in deals:
            if d.board_number in existing_boards:
                return d

        # No match — let the user pick from a simple list.
        from PyQt6.QtWidgets import QInputDialog
        labels = [
            f"Board {d.board_number}"
            + (f" — {d.contract.to_str()} by {d.declarer.to_char()}"
               if d.contract and d.declarer else "")
            for d in deals
        ]
        choice, ok = QInputDialog.getItem(
            self, "Pick Deal", "Multiple deals in this BDL — which is the closed room?",
            labels, 0, False,
        )
        if not ok:
            return None
        return deals[labels.index(choice)]

    def _attach_closed_room_run(self, run, replace_ai_run: bool = True) -> bool:
        """Attach a closed-room BenBoardRun to the matching BoardResult.

        Match priority:
          1. pavlicek_id equality
          2. board_number equality
          3. most-recent open-room row without a closed-room sibling
             (Q-Plus and ben_bridge use independent board numbering, so
             after the user has just played a hand and done the closed
             room manually, the latest unpaired row is almost always the
             intended target).

        If matched, the closed run's board_number is overridden to the
        open-room's number so the score-sheet groups them on the same row.

        Returns True if a matching open-room result was found, False if
        the row was added standalone.
        """
        from ben_backend.scoring import BoardResult
        from ben_backend.models import BenTable

        if self.scoring_table is None:
            return False

        def _is_closed(r):
            return r.notes and "Closed room" in (r.notes or "")

        results = self.scoring_table.results

        # Pavlicek match — only meaningful when both sides recorded a non-
        # empty pavlicek_id. ben_bridge skips it on guests; Q-Plus may not
        # write it at all. So most ingest paths fall through to step 2/3.
        match_idx = None
        if run.pavlicek_id:
            for i, r in enumerate(results):
                if (not _is_closed(r)
                        and r.pavlicek_id
                        and r.pavlicek_id == run.pavlicek_id):
                    match_idx = i
                    break

        # Board-number match.
        if match_idx is None:
            for i, r in enumerate(results):
                if not _is_closed(r) and r.board_number == run.board_number:
                    match_idx = i
                    break

        # Fallback: latest open-room row that doesn't already have a
        # closed-room sibling. Walk from newest to oldest.
        if match_idx is None:
            paired_boards = {r.board_number for r in results if _is_closed(r)}
            for i in range(len(results) - 1, -1, -1):
                r = results[i]
                if not _is_closed(r) and r.board_number not in paired_boards:
                    match_idx = i
                    break

        # If matched, snap the closed-run's board_number onto the open one
        # so they group together in the score sheet.
        if match_idx is not None:
            target_board = results[match_idx].board_number
        else:
            target_board = run.board_number

        # Remove any existing closed-room row for the target board so the
        # manual qplus run replaces the AI auto-closed-room.
        if replace_ai_run:
            self.scoring_table.results = [
                r for r in self.scoring_table.results
                if not (r.board_number == target_board and _is_closed(r))
            ]

        # Build the closed-room BoardResult. Dealer/vulnerability are
        # placeholders — the score sheet only displays board number,
        # contract, and scores per row, and we don't lose anything by
        # not threading the BDL header values all the way through.
        closed_result = BoardResult(
            board_number=target_board,
            pavlicek_id=run.pavlicek_id,
            dealer=Seat.NORTH,
            vulnerability=Vulnerability.NONE,
            contract=run.contract,
            declarer=run.contract.declarer if run.contract else None,
            tricks_made=run.declarer_tricks,
            ns_score=run.ns_score,
            ew_score=run.ew_score,
            notes="Closed room (Q-Plus)",
            board_run=run,
        )
        self.scoring_table.add_result(closed_result)

        # Refresh an open Scoring Table dialog (now non-modal) so the
        # newly attached closed-room row shows up immediately and the
        # Compare button has the data to light up. Without this the user
        # still sees the pre-ingest snapshot until they re-open the dialog.
        scores = getattr(self, '_scores_dialog', None)
        if scores is not None and scores.isVisible():
            try:
                scores._populate_table()
            except Exception as e:
                print(f"[ingest qplus] score dialog refresh failed: {e}",
                      flush=True)

        return match_idx is not None

    def closeEvent(self, event):
        """Auto-save scores and clean up resources."""
        # Auto-save scoring table if any boards were played
        if self.scoring_table and self.scoring_table.results:
            try:
                path = self.scoring_table.save_to_local_matches()
                print(f"Match scores auto-saved to {path}")
            except Exception as e:
                print(f"Could not auto-save scores: {e}")

        # Stop the engine worker thread if running
        if self.engine_worker is not None:
            if self.engine_worker.isRunning():
                self.engine_worker.quit()
                # Wait up to 2 seconds for thread to finish
                if not self.engine_worker.wait(2000):
                    self.engine_worker.terminate()
                    self.engine_worker.wait()

        # Clean up the BridgeEngine (releases TensorFlow resources)
        if self.engine is not None:
            self.engine.cleanup()

        event.accept()
