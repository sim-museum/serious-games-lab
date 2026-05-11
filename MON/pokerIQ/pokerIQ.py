#!/usr/bin/env python3
"""
PokerIQ - Qt GUI Version
A graphical poker trainer with card graphics and interactive table.
"""

import sys
import os
import random
import eval7
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QSpinBox, QMessageBox, QFrame,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsRectItem, QDialog, QDialogButtonBox, QCheckBox, QGroupBox,
    QTabWidget, QTextEdit, QTextBrowser, QScrollArea, QComboBox,
    QFormLayout, QProgressBar, QSizePolicy, QGridLayout, QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QSettings, QThread, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF, QPalette, QPixmap, QIcon,
    QAction,
)

# --- Configuration & Constants ---


def get_app_version() -> str:
    """Return a short identifier for the current pokerIQ build so the host
    and joining guests can verify they're on the same revision. Tries the
    repo's git short hash first; falls back to the modification time of
    pokerIQ.py if git isn't available."""
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(
            ['git', '-C', here, 'rev-parse', '--short=12', 'HEAD'],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            v = result.stdout.strip()
            if v:
                return v
    except Exception:
        pass
    try:
        mtime = int(os.path.getmtime(os.path.abspath(__file__)))
        return f"mtime:{mtime}"
    except Exception:
        return "unknown"


APP_VERSION = get_app_version()


STREETS = ["Preflop", "Flop", "Turn", "River"]
STARTING_STACK = 200
HANDS_PER_BLIND_LEVEL = 10  # Blinds increase every N hands

# Blind structure (SB, BB)
BLIND_LEVELS = [
    (1, 2),
    (2, 4),
    (3, 6),
    (5, 10),
    (10, 20),
    (15, 30),
    (25, 50),
    (50, 100),
    (75, 150),
    (100, 200),
]


# --- poker_iq Bot Integration ---
# Import poker_iq bots for advanced AI options
try:
    from poker_iq.bots import create_bot, BotType, BaseBot
    from poker_iq.models import (
        GameState as PIQGameState, PlayerState as PIQPlayerState,
        Hand as PIQHand, Card as PIQCard, Action as PIQAction,
        ActionType as PIQActionType, Street as PIQStreet, Suit as PIQSuit, Rank as PIQRank
    )
    POKER_IQ_AVAILABLE = True
except ImportError:
    POKER_IQ_AVAILABLE = False
    BotType = None

# --- Network Module ---
try:
    from network import (
        PokerServer, PokerClient, DEFAULT_PORT,
        NetworkModeDialog, HostGameDialog, JoinGameDialog, SeatSelectionDialog
    )
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False
    PokerServer = None
    PokerClient = None

# Bot type identifiers for preferences
# Maps display name -> (identifier, is_poker_iq_bot)
BOT_TYPE_OPTIONS = [
    ("Default (Original)", "default", False),
    ("Optimal", "optimal", False),
    ("Tight", "tight", False),
    ("Loose", "loose", False),
    ("Aggressive", "aggressive", False),
    ("Theory of Mind", "tom", False),
    # Stronger built-in styles, added later. 'shark' is a balanced GTO-leaning
    # player; 'exploit' adapts to the table; 'icm' applies push/fold pressure
    # like a late-stage tournament. All three are stronger than the original
    # five styles and are eligible for the default lineup.
    ("Shark (GTO-leaning)", "shark", False),
    ("Exploit (adaptive)", "exploit", False),
    ("ICM (tournament push/fold)", "icm", False),
]

# Add poker_iq bots if available
if POKER_IQ_AVAILABLE:
    BOT_TYPE_OPTIONS.extend([
        ("Basic Equity Bot", "piq_basic_equity", True),
        ("Improved Equity Bot", "piq_improved_equity", True),
        ("External Engine Bot", "piq_external_engine", True),
    ])

# Create lookup dict
BOT_TYPE_MAP = {opt[1]: (opt[0], opt[2]) for opt in BOT_TYPE_OPTIONS}

# Cute names for each bot type (used when changing bot selection)
BOT_CUTE_NAMES = {
    "default": None,  # Keep original name
    "optimal": "Optimal Olivia",
    "tight": "Tight Tim",
    "loose": "Loose Bruce",
    "aggressive": "Aggro Angela",
    "tom": "Fluid Fiona",
    "shark": "Sharkey Steve",
    "exploit": "Exploit Eli",
    "icm": "ICM Ian",
    "piq_basic_equity": "Equity Eddie",
    "piq_improved_equity": "Savvy Sarah",
    "piq_external_engine": "Engine Emma",
}

# The "default lineup" is the canonical set of five DIFFERENT
# approaches — each seat plays a meaningfully different strategy,
# not just the same strategy with a different cosmetic name. Used
# by reset_bots_to_default_lineup() and by the spectator class so
# both code paths stay in sync.
DEFAULT_BOT_LINEUP = [
    # (seat_index, character_name, style_id). Five different approaches:
    # one calling station (Loose Bruce), one rock (Tight Tim), one
    # opponent-modeller (Fluid Fiona), one GTO-leaning hard-raiser
    # (Sharkey Steve) and one LAG (Aggro Angela). The seat numbers
    # here are nominal — _make_random_bot_lineup() reshuffles the
    # five bots across seats 1..5 every game so the hero never knows
    # which personality is on their left versus their right.
    (1, "Tight Tim",      "tight"),
    (2, "Loose Bruce",    "loose"),
    (3, "Aggro Angela",   "aggressive"),
    (4, "Sharkey Steve",  "shark"),
    (5, "Fluid Fiona",    "tom"),
]


def _make_random_bot_lineup():
    """Return ``[(name, style), ...]`` for the five bot seats with the
    five canonical personalities placed in random order.

    The hero is always seat 0, so this only shuffles seats 1..5. We
    keep the canonical set of five personalities (so every game has
    one of each: rock, calling station, LAG, shark, ToM) — the
    randomisation is purely positional. That way the player can't
    rely on "Steve is always on my left" to narrow ranges; they have
    to read each bot from scratch each game.
    """
    import random
    pool = [(name, style) for _seat, name, style in DEFAULT_BOT_LINEUP]
    random.shuffle(pool)
    return pool


class PokerIQBotAdapter:
    """
    Adapter to use poker_iq bots within the pokerIQ game.

    Translates between pokerIQ's game_state dict format and
    poker_iq's GameState object format.
    """

    # Mapping from pokerIQ street names to poker_iq Street enum
    STREET_MAP = {
        "Preflop": PIQStreet.PREFLOP if POKER_IQ_AVAILABLE else 0,
        "Flop": PIQStreet.FLOP if POKER_IQ_AVAILABLE else 1,
        "Turn": PIQStreet.TURN if POKER_IQ_AVAILABLE else 2,
        "River": PIQStreet.RIVER if POKER_IQ_AVAILABLE else 3,
    }

    def __init__(self, bot_type_id: str, seat: int):
        """
        Initialize the adapter with a poker_iq bot.

        Args:
            bot_type_id: One of 'piq_basic_equity', 'piq_improved_equity', 'piq_external_engine'
            seat: Seat index for the bot
        """
        self.seat = seat
        self.bot_type_id = bot_type_id
        self.bot = None

        if not POKER_IQ_AVAILABLE:
            return

        try:
            if bot_type_id == "piq_basic_equity":
                self.bot = create_bot(BotType.BASIC_EQUITY, seat=seat)
            elif bot_type_id == "piq_improved_equity":
                self.bot = create_bot(BotType.IMPROVED_EQUITY, seat=seat)
            elif bot_type_id == "piq_external_engine":
                self.bot = create_bot(BotType.EXTERNAL_ENGINE, seat=seat)
        except Exception as e:
            print(f"Warning: Failed to create poker_iq bot: {e}")
            self.bot = None

    def is_available(self) -> bool:
        """Check if the bot was successfully created."""
        return self.bot is not None

    def get_action(self, game_state: dict, player) -> tuple:
        """
        Get action from the poker_iq bot.

        Args:
            game_state: pokerIQ game state dict with keys:
                - 'board': list of card strings like ['Ah', 'Kd', '2c']
                - 'pot': current pot size
                - 'current_bet': current bet to match
                - 'players': list of Player objects
                - 'bb_amount': big blind amount
            player: The Player object for this bot

        Returns:
            Tuple of (action_char, amount) where action_char is 'f', 'c', or 'r'
        """
        if self.bot is None:
            # Fallback to default behavior
            return 'c', 0

        try:
            # Convert to poker_iq GameState
            piq_state = self._convert_game_state(game_state, player)

            # Get action from bot
            action = self.bot.get_action(piq_state)

            # Convert back to pokerIQ format
            return self._convert_action(action, game_state, player)

        except Exception as e:
            print(f"Warning: poker_iq bot error: {e}")
            # Fallback to call
            return 'c', 0

    def _convert_game_state(self, game_state: dict, player) -> 'PIQGameState':
        """Convert pokerIQ game_state dict to poker_iq GameState."""
        players = game_state['players']
        num_players = len(players)
        bb_amount = game_state.get('bb_amount', 2)
        sb_amount = bb_amount // 2

        # Determine button seat (dealer_idx would need to be passed, estimate from player positions)
        # For simplicity, assume seat 0 is always the button in this conversion
        button_seat = 0

        # Convert board cards
        board_strs = game_state.get('board', [])
        board = [self._str_to_piq_card(s) for s in board_strs]

        # Determine street from board length
        if len(board) == 0:
            street = PIQStreet.PREFLOP
        elif len(board) == 3:
            street = PIQStreet.FLOP
        elif len(board) == 4:
            street = PIQStreet.TURN
        else:
            street = PIQStreet.RIVER

        # Convert players
        piq_players = []
        for i, p in enumerate(players):
            hole_cards = None
            if p.hand and (i == self.seat or p.style == 'human'):
                # Only include our own hole cards (or human's if visible)
                try:
                    cards = [self._str_to_piq_card(str(c)) for c in p.hand]
                    hole_cards = PIQHand(cards=cards)
                except:
                    pass

            piq_player = PIQPlayerState(
                seat=i,
                stack=p.stack,
                hole_cards=hole_cards,
                is_active=p.active,
                current_bet=p.bet_in_round
            )
            piq_players.append(piq_player)

        # Create GameState
        return PIQGameState(
            num_players=num_players,
            players=piq_players,
            button_seat=button_seat,
            small_blind=sb_amount,
            big_blind=bb_amount,
            street=street,
            board=board,
            pot=game_state['pot'],
            current_bet=game_state['current_bet'],
            min_raise=bb_amount,
            action_seat=self.seat
        )

    def _str_to_piq_card(self, card_str: str) -> 'PIQCard':
        """Convert card string like 'Ah' to poker_iq Card."""
        rank_char = card_str[0].upper()
        suit_char = card_str[1].lower()

        rank_map = {
            '2': PIQRank.TWO, '3': PIQRank.THREE, '4': PIQRank.FOUR, '5': PIQRank.FIVE,
            '6': PIQRank.SIX, '7': PIQRank.SEVEN, '8': PIQRank.EIGHT, '9': PIQRank.NINE,
            'T': PIQRank.TEN, 'J': PIQRank.JACK, 'Q': PIQRank.QUEEN, 'K': PIQRank.KING, 'A': PIQRank.ACE
        }
        suit_map = {
            's': PIQSuit.SPADES, 'h': PIQSuit.HEARTS, 'd': PIQSuit.DIAMONDS, 'c': PIQSuit.CLUBS
        }

        return PIQCard(rank=rank_map[rank_char], suit=suit_map[suit_char])

    def _convert_action(self, action: 'PIQAction', game_state: dict, player) -> tuple:
        """Convert poker_iq Action to pokerIQ format (action_char, amount)."""
        action_type = action.action_type
        amount = action.amount or 0

        if action_type == PIQActionType.FOLD:
            return 'f', 0
        elif action_type == PIQActionType.CHECK:
            return 'c', 0
        elif action_type == PIQActionType.CALL:
            return 'c', 0
        elif action_type in (PIQActionType.BET, PIQActionType.RAISE, PIQActionType.ALL_IN):
            # For raises, amount is the total bet, but pokerIQ expects the raise amount
            return 'r', amount
        else:
            return 'c', 0


# Card colors
CARD_WHITE = QColor(255, 255, 255)
CARD_RED = QColor(220, 20, 60)       # Legacy hearts/diamonds
CARD_BLACK = QColor(20, 20, 20)       # Legacy clubs/spades
CARD_BLUE = QColor(30, 80, 200)       # Modern diamonds
CARD_GREEN = QColor(20, 140, 60)      # Modern clubs
CARD_BACK = QColor(30, 60, 120)

# Global flag for legacy colors (set by PokerTableWidget)
_use_legacy_colors = False

def get_suit_color(suit):
    """Get the color for a card suit based on legacy_colors preference."""
    global _use_legacy_colors
    if _use_legacy_colors:
        # Legacy: hearts/diamonds red, clubs/spades black
        return CARD_RED if suit in ['h', 'd'] else CARD_BLACK
    else:
        # Modern: hearts red, diamonds blue, clubs green, spades black
        if suit == 'h':
            return CARD_RED
        elif suit == 'd':
            return CARD_BLUE
        elif suit == 'c':
            return CARD_GREEN
        else:  # spades
            return CARD_BLACK

# Table colors
TABLE_FELT = QColor(34, 139, 34)
TABLE_RAIL = QColor(101, 67, 33)
TABLE_BORDER = QColor(60, 40, 20)

# --- Helper Functions (from poker_learn.py) ---

def calc_equity_hidden(hero_hand, board, iterations=100, num_opponents=1):
    if not hero_hand:
        return 0.0
    hero_cards = hero_hand
    board_cards = [eval7.Card(s) for s in board]
    dead_card_strs = {str(c) for c in hero_cards}
    dead_card_strs.update(str(c) for c in board_cards)
    wins = 0
    ties = 0
    for _ in range(iterations):
        sim_deck = eval7.Deck()
        sim_deck.cards = [c for c in sim_deck.cards if str(c) not in dead_card_strs]
        sim_deck.shuffle()
        cards_needed_for_opps = num_opponents * 2
        cards_needed_for_board = 5 - len(board_cards)
        if len(sim_deck.cards) < cards_needed_for_opps + cards_needed_for_board:
            break
        # Deal hands for all opponents
        opp_hands = [sim_deck.deal(2) for _ in range(num_opponents)]
        if cards_needed_for_board > 0:
            runout = sim_deck.deal(cards_needed_for_board)
            full_board = board_cards + runout
        else:
            full_board = board_cards
        hero_score = eval7.evaluate(hero_cards + full_board)
        # Find best opponent score
        best_opp_score = max(eval7.evaluate(opp_hand + full_board) for opp_hand in opp_hands)
        if hero_score > best_opp_score:
            wins += 1
        elif hero_score == best_opp_score:
            ties += 1
    return (wins + (ties / 2)) / iterations


def calc_equity_perfect(hero_hand, villain_hands, board, iterations=100):
    if not hero_hand:
        return 0.0
    hero_cards = hero_hand
    opp_cards_list = [h for h in villain_hands if h]
    board_cards = [eval7.Card(s) for s in board]
    known_cards = hero_cards + [c for hand in opp_cards_list for c in hand] + board_cards
    known_strs = {str(c) for c in known_cards}
    wins = 0
    ties = 0
    for _ in range(iterations):
        sim_deck = eval7.Deck()
        sim_deck.cards = [c for c in sim_deck.cards if str(c) not in known_strs]
        sim_deck.shuffle()
        cards_needed = 5 - len(board_cards)
        if cards_needed > 0:
            if len(sim_deck.cards) < cards_needed:
                break
            runout = sim_deck.deal(cards_needed)
        else:
            runout = []
        full_board = board_cards + runout
        hero_score = eval7.evaluate(hero_cards + full_board)
        best_opp_score = -1
        for v_hand in opp_cards_list:
            score = eval7.evaluate(v_hand + full_board)
            if score > best_opp_score:
                best_opp_score = score
        if hero_score > best_opp_score:
            wins += 1
        elif hero_score == best_opp_score:
            ties += 1
    return (wins + (ties / (len(opp_cards_list) + 1))) / iterations


def calc_multiway_equity(player_hands, board, iterations=500):
    """Calculate equity for all players in a multiway pot. Equities sum to ~100%.

    Args:
        player_hands: List of (player, hand) tuples for active players
        board: List of board card strings
        iterations: Number of Monte Carlo iterations

    Returns:
        Dict mapping player to their equity (0.0 to 1.0)
    """
    if not player_hands:
        return {}

    board_cards = [eval7.Card(s) for s in board] if board else []

    # Build list of hands as eval7 cards
    hands = []
    for player, hand in player_hands:
        if hand:
            hands.append((player, [eval7.Card(str(c)) for c in hand] if not isinstance(hand[0], eval7.Card) else hand))

    if not hands:
        return {}

    known_strs = set()
    for _, h in hands:
        for c in h:
            known_strs.add(str(c))
    for c in board_cards:
        known_strs.add(str(c))

    wins = {p: 0 for p, _ in hands}
    ties = {p: 0 for p, _ in hands}

    for _ in range(iterations):
        sim_deck = eval7.Deck()
        sim_deck.cards = [c for c in sim_deck.cards if str(c) not in known_strs]
        sim_deck.shuffle()

        cards_needed = 5 - len(board_cards)
        if cards_needed > 0:
            if len(sim_deck.cards) < cards_needed:
                continue
            runout = sim_deck.deal(cards_needed)
            full_board = board_cards + runout
        else:
            full_board = board_cards

        # Evaluate all hands
        scores = []
        for player, hand in hands:
            score = eval7.evaluate(hand + full_board)
            scores.append((player, score))

        # Find best score
        best_score = max(s for _, s in scores)
        winners = [p for p, s in scores if s == best_score]

        # Award wins/ties
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            for w in winners:
                ties[w] += 1.0 / len(winners)

    # Calculate equities
    equities = {}
    for player, _ in hands:
        equities[player] = (wins[player] + ties[player]) / iterations

    return equities


def format_cards(cards):
    return " ".join([str(c) for c in cards])


def get_hand_name(cards):
    """Get a readable name for a starting hand like 'pocket Kings' or 'Ace-King suited'."""
    if not cards or len(cards) < 2:
        return "unknown"

    c1, c2 = str(cards[0]), str(cards[1])
    r1, s1 = c1[0], c1[1]
    r2, s2 = c2[0], c2[1]

    rank_names = {
        'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack', 'T': 'Ten',
        '9': 'Nine', '8': 'Eight', '7': 'Seven', '6': 'Six', '5': 'Five',
        '4': 'Four', '3': 'Three', '2': 'Two'
    }

    rank_order = 'AKQJT98765432'

    # Order by rank
    if rank_order.index(r1) > rank_order.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1

    suited = s1 == s2

    if r1 == r2:
        return f"pocket {rank_names[r1]}s"
    else:
        suit_str = " suited" if suited else ""
        return f"{rank_names[r1]}-{rank_names[r2]}{suit_str}"


# --- Player Class ---
class Player:
    def __init__(self, name, style):
        self.name = name
        self.style = style
        self.stack = STARTING_STACK
        self.hand = []
        self.active = True
        self.bet_in_round = 0
        self.actions_this_round = 0
        self.total_invested = 0  # Total chips invested this hand (for side pots)
        self.piq_bot_adapter = None  # Optional poker_iq bot adapter

    def set_piq_bot(self, bot_type_id: str, seat: int):
        """
        Set a poker_iq bot for this player.

        Args:
            bot_type_id: One of 'piq_basic_equity', 'piq_improved_equity', 'piq_external_engine'
            seat: Seat index for the bot
        """
        if POKER_IQ_AVAILABLE and bot_type_id and bot_type_id.startswith('piq_'):
            self.piq_bot_adapter = PokerIQBotAdapter(bot_type_id, seat)
            if not self.piq_bot_adapter.is_available():
                print(f"Warning: poker_iq bot {bot_type_id} not available, using default behavior")
                self.piq_bot_adapter = None
        else:
            self.piq_bot_adapter = None

    def clear_piq_bot(self):
        """Remove any poker_iq bot, reverting to default behavior."""
        self.piq_bot_adapter = None

    def reset_for_hand(self):
        self.hand = []
        self.active = True
        self.bet_in_round = 0
        self.actions_this_round = 0
        self.total_invested = 0

    def calculate_current_stats(self, game_state, is_god_mode):
        current_bet = game_state['current_bet']
        to_call = max(0, current_bet - self.bet_in_round)  # Can't be negative

        # Pot already includes current round bets, so don't double count
        total_pot = game_state['pot']
        pot_odds = to_call / (total_pot + to_call) if (total_pot + to_call) > 0 else 0

        if is_god_mode and self.style == 'human':
            villain_hands = [p.hand for p in game_state['players'] if p != self and p.active]
            equity = calc_equity_perfect(self.hand, villain_hands, game_state['board'], iterations=500)
        else:
            num_opponents = len([p for p in game_state['players'] if p != self and p.active])
            equity = calc_equity_hidden(self.hand, game_state['board'], iterations=400, num_opponents=max(1, num_opponents))

        return equity, pot_odds, to_call

    def get_bot_action(self, game_state, is_god_mode):
        """Get action for bot players (non-human)."""
        self.actions_this_round += 1

        # If a poker_iq bot is configured, use it instead of default behavior
        if self.piq_bot_adapter is not None and self.piq_bot_adapter.is_available():
            try:
                action, amount = self.piq_bot_adapter.get_action(game_state, self)
                return action, amount
            except Exception as e:
                print(f"Warning: poker_iq bot error, falling back to default: {e}")
                # Fall through to default behavior

        equity, pot_odds, to_call = self.calculate_current_stats(game_state, is_god_mode)

        # `equity` above is multi-way (vs every active opponent). That's
        # the right number for FOLD decisions — you have to beat the
        # whole field to win the pot. But raise thresholds were calibrated
        # for heads-up play, so they're impossible to clear in a 5-handed
        # pot where even AA tops out around 50 % equity.  Compute a
        # heads-up equity ("would I raise this hand if it were 1-on-1?")
        # and use that to gate the raise paths below.  Bug: previously
        # bots almost never raised because the multi-way `equity` could
        # not reach the 0.60/0.75/0.80 thresholds even with a monster.
        if self.hand:
            try:
                hu_equity = calc_equity_hidden(
                    self.hand, game_state['board'],
                    iterations=200, num_opponents=1,
                )
            except Exception:
                hu_equity = equity
        else:
            hu_equity = equity

        is_huge_bet = to_call > (self.stack * 0.25)
        if is_huge_bet:
            if equity < 0.60:
                return 'f', 0

        if self.style == 'tight':
            if equity < pot_odds + 0.15:
                return 'f', 0
            if hu_equity > 0.75:
                return 'r', int(game_state['pot'] * 0.75)
            return 'c', 0

        elif self.style == 'loose':
            if equity < pot_odds - 0.05:
                return 'f', 0
            return 'c', 0

        elif self.style == 'station':
            if equity < 0.08 and to_call > 0:
                return 'f', 0
            return 'c', 0

        elif self.style == 'aggressive':
            # LAG profile — raises wide and often. Earlier version
            # capped to 2 actions per round and only raised at 60%+
            # equity, which made the seat passive in practice. Now
            # raises every street up to 4 times, value-raises
            # starting at 50% equity, and bluff-raises ~35% of the
            # time when down to 25-50% equity. Bet size grows with
            # equity (60-110% pot) so monsters extract real value.
            if self.actions_this_round > 4:
                return 'c', 0
            rng = random.random()
            bb = game_state.get('bb_amount', 2)
            pot = max(1, game_state['pot'])

            if hu_equity > 0.80:
                bet = int(pot * random.uniform(0.9, 1.1))
                return 'r', max(bet, to_call + 2 * bb)
            if hu_equity > 0.50:
                if rng < 0.85:
                    bet = int(pot * random.uniform(0.6, 0.95))
                    return 'r', max(bet, to_call + 2 * bb)
                return 'c', 0
            if hu_equity > 0.25:
                # Bluff-raise more often than the old 25% threshold —
                # this is what makes Aggro Angela actually aggressive.
                if rng < 0.35:
                    bet = int(pot * random.uniform(0.5, 0.75))
                    return 'r', max(bet, to_call + 2 * bb)
                if equity >= pot_odds + 0.02:
                    return 'c', 0
                return 'f', 0
            if equity < pot_odds:
                return 'f', 0
            return 'c', 0

        elif self.style == 'optimal':
            if self.actions_this_round > 3:
                return 'c', 0
            if hu_equity > 0.80:
                return 'r', int(game_state['pot'] * 0.8)
            elif hu_equity > 0.60:
                return 'r', int(game_state['pot'] * 0.5)
            elif equity >= pot_odds:
                return 'c', 0
            else:
                return 'f', 0

        elif self.style == 'shark':
            # Sharkey Steve — GTO-leaning balanced player. The same
            # hand can raise, call, or fold depending on a tiny bit of
            # randomness, which makes him much harder to put on a hand
            # than the deterministic 'optimal' player. Polarized bet
            # sizing (big or check) plus a small calibrated bluff
            # frequency (~12 % at clear bluff catchers).
            if self.actions_this_round > 4:
                return 'c', 0
            bb = game_state.get('bb_amount', 2)
            pot = max(1, game_state['pot'])
            spr = self.stack / pot if pot > 0 else 10.0  # Stack-to-pot

            # Mixed-strategy slow-play with monsters about 1 in 4 times
            # so opponents can't auto-fold to our value bets.  Raise
            # thresholds use heads-up equity (otherwise multi-way "fair
            # share" pulls them out of reach).
            if hu_equity > 0.85:
                if random.random() < 0.25:
                    return 'c', 0
                bet = int(pot * (1.0 if spr > 2 else 0.7))
                return 'r', max(bet, to_call + 2 * bb)
            if hu_equity > 0.70:
                # Polarised: 75 % pot value bet ⅔ of the time, otherwise call.
                if random.random() < 0.66:
                    bet = int(pot * 0.75)
                    return 'r', max(bet, to_call + 2 * bb)
                return 'c', 0
            if hu_equity > 0.55:
                # Bet small (½ pot) sometimes for thin value/protection.
                if random.random() < 0.5 and to_call < pot * 0.4:
                    bet = int(pot * 0.5)
                    return 'r', max(bet, to_call + bb)
                return 'c', 0
            if equity >= pot_odds + 0.04:
                return 'c', 0
            # Bluff layer: ~12 % small bluffs at clear catchers (no big
            # bet facing us, decent equity floor).
            if (to_call < pot * 0.4 and equity > 0.20
                    and random.random() < 0.12):
                bet = int(pot * 0.55)
                return 'r', max(bet, to_call + bb)
            if to_call == 0:
                return 'c', 0
            return 'f', 0

        elif self.style == 'exploit':
            # Exploit Eli — reads the table's tendencies (active
            # opponents' styles) and counter-adjusts. Against tight
            # opposition he widens his bluff frequency and steals
            # blinds; against loose tables he tightens up and
            # value-bets bigger. Versus aggressive opponents he
            # check-calls more (slowplay against bluffs) and
            # 3-bet-bluffs less.
            if self.actions_this_round > 4:
                return 'c', 0
            bb = game_state.get('bb_amount', 2)
            pot = max(1, game_state['pot'])

            opps = [p for p in game_state['players']
                    if p is not self and p.active]
            tight_n = sum(1 for p in opps if p.style in ('tight',))
            loose_n = sum(1 for p in opps if p.style in ('loose', 'station'))
            aggro_n = sum(1 for p in opps if p.style in ('aggressive',))

            # Exploitative knobs.
            steal_freq = 0.28 if tight_n > loose_n else 0.10
            value_bet_size = 0.85 if loose_n > 0 else 0.65
            slowplay_vs_aggro = (aggro_n > 0)

            if hu_equity > 0.80:
                if slowplay_vs_aggro and random.random() < 0.5:
                    return 'c', 0  # Trap
                bet = int(pot * value_bet_size)
                return 'r', max(bet, to_call + 2 * bb)
            if hu_equity > 0.60:
                if slowplay_vs_aggro and to_call > 0:
                    return 'c', 0  # Let aggro fire again
                bet = int(pot * (value_bet_size * 0.7))
                return 'r', max(bet, to_call + bb)
            if equity >= pot_odds + 0.03:
                return 'c', 0
            if to_call == 0 and random.random() < steal_freq:
                # Steal attempt — small bet.
                bet = int(pot * 0.5)
                return 'r', max(bet, 2 * bb)
            if to_call == 0:
                return 'c', 0
            return 'f', 0

        elif self.style == 'icm':
            # ICM Ian — push/fold dynamics applied at every street.
            # Approximates a tournament-mid-stage shortstack: when
            # stack-to-pot is small enough that every chip matters,
            # collapse decisions to "shove or fold" (the mathematically
            # optimal strategy when SPR < ~3). With deeper stacks falls
            # back to balanced play.
            bb = game_state.get('bb_amount', 2)
            pot = max(1, game_state['pot'])
            spr = self.stack / pot if pot > 0 else 99.0

            if spr < 3 and self.stack <= 25 * bb:
                # Push/fold mode. Threshold tuned roughly to a
                # 25-BB-effective Nash equilibrium: AA-22 / Ax / KQ /
                # any pair on flop / strong draws all jam, fold rest.
                # Push/fold uses heads-up equity since shoving thins
                # the field — by the time it matters, most opponents
                # have already folded.
                shove_threshold = 0.55
                if hu_equity >= shove_threshold:
                    return 'r', self.stack + to_call  # shove all-in
                if to_call > 0:
                    return 'f', 0
                return 'c', 0  # check when free
            # Deep-stack mode: behave like 'optimal' but a touch
            # tighter on calls because losing chips matters more.
            if hu_equity > 0.80:
                return 'r', int(pot * 0.8)
            if hu_equity > 0.60:
                return 'r', int(pot * 0.5)
            if equity >= pot_odds + 0.03:
                return 'c', 0
            return 'f', 0

        elif self.style == 'tom':
            # Theory of Mind player - considers opponents' likely holdings
            # Adjusts strategy based on other players' tendencies and actions
            if self.actions_this_round > 3:
                return 'c', 0

            # Analyze opponent tendencies
            opponents = [p for p in game_state['players'] if p != self and p.active]
            tight_opponents = sum(1 for p in opponents if p.style == 'tight')
            loose_opponents = sum(1 for p in opponents if p.style == 'loose')
            aggro_opponents = sum(1 for p in opponents if p.style == 'aggressive')

            # Adjust HEADS-UP equity for raise decisions (so multi-way
            # tables can still trigger a raise on a strong hand) and
            # multi-way `equity` for fold decisions (you have to beat
            # the field to win the pot).
            adjusted_hu = hu_equity

            # If facing aggression from tight player, they likely have strong hand
            if tight_opponents > 0 and to_call > game_state['pot'] * 0.5:
                adjusted_hu *= 0.8  # Discount our raise enthusiasm

            # Against loose players, our strong hands are more valuable
            if loose_opponents > 0 and hu_equity > 0.6:
                adjusted_hu *= 1.1  # Boost raise threshold clearance

            # Be more cautious against aggressive players: bluff-catch.
            # This affects the call/fold leg, not the raise leg.
            adjusted_eq_for_call = equity
            if aggro_opponents > 0 and to_call > 0:
                if equity > 0.35:
                    adjusted_eq_for_call = max(equity, pot_odds + 0.05)

            # Decision making — raise ladders read heads-up equity.
            if adjusted_hu > 0.75:
                return 'r', int(game_state['pot'] * 0.75)
            elif adjusted_hu > 0.55:
                if random.random() < 0.3:
                    return 'r', int(game_state['pot'] * 0.5)
                return 'c', 0
            elif adjusted_eq_for_call >= pot_odds:
                return 'c', 0
            else:
                # Occasional bluff (heads-up equity floor — don't bluff
                # when the field is too strong to fold out).
                if (random.random() < 0.15 and to_call < game_state['pot'] * 0.3
                        and hu_equity > 0.35):
                    return 'r', int(game_state['pot'] * 0.6)
                return 'f', 0

        return 'c', 0


# --- Card Graphics Widget ---
class CardWidget(QWidget):
    """Widget to render a single playing card."""

    CARD_WIDTH = 80
    CARD_HEIGHT = 112

    SUIT_SYMBOLS = {
        's': '\u2660',  # Spade
        'h': '\u2665',  # Heart
        'd': '\u2666',  # Diamond
        'c': '\u2663',  # Club
    }

    RANK_DISPLAY = {
        'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J', 'T': '10',
        '9': '9', '8': '8', '7': '7', '6': '6', '5': '5',
        '4': '4', '3': '3', '2': '2'
    }

    def __init__(self, card_str=None, face_down=False, parent=None):
        super().__init__(parent)
        self.card_str = card_str
        self.face_down = face_down
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def set_card(self, card_str, face_down=False):
        self.card_str = card_str
        self.face_down = face_down
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(2, 2, self.CARD_WIDTH - 4, self.CARD_HEIGHT - 4)

        if self.face_down or not self.card_str:
            # Draw card back
            gradient = QLinearGradient(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
            gradient.setColorAt(0, QColor(30, 60, 150))
            gradient.setColorAt(0.5, QColor(20, 40, 100))
            gradient.setColorAt(1, QColor(30, 60, 150))

            painter.setBrush(QBrush(gradient))
            painter.setPen(QPen(QColor(20, 30, 60), 2))
            painter.drawRoundedRect(rect, 5, 5)

            # Draw pattern
            painter.setPen(QPen(QColor(60, 100, 180), 1))
            for i in range(5, int(self.CARD_WIDTH), 8):
                painter.drawLine(i, 10, i, self.CARD_HEIGHT - 10)
            for i in range(10, int(self.CARD_HEIGHT), 8):
                painter.drawLine(5, i, self.CARD_WIDTH - 5, i)
        else:
            # Draw card face
            painter.setBrush(QBrush(CARD_WHITE))
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawRoundedRect(rect, 5, 5)

            rank = self.card_str[0]
            suit = self.card_str[1]

            color = get_suit_color(suit)
            painter.setPen(color)

            # Draw rank
            font = QFont('Arial', 18, QFont.Weight.Bold)
            painter.setFont(font)
            rank_text = self.RANK_DISPLAY.get(rank, rank)
            painter.drawText(8, 24, rank_text)

            # Draw suit symbol
            font = QFont('Arial', 16)
            painter.setFont(font)
            suit_symbol = self.SUIT_SYMBOLS.get(suit, '?')
            painter.drawText(8, 44, suit_symbol)

            # Draw center suit (larger)
            font = QFont('Arial', 32)
            painter.setFont(font)
            painter.drawText(QRectF(0, 30, self.CARD_WIDTH, 50),
                           Qt.AlignmentFlag.AlignCenter, suit_symbol)

            # Draw bottom rank/suit (inverted)
            painter.save()
            painter.translate(self.CARD_WIDTH - 8, self.CARD_HEIGHT - 8)
            painter.rotate(180)
            font = QFont('Arial', 18, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(0, 16, rank_text)
            font = QFont('Arial', 16)
            painter.setFont(font)
            painter.drawText(0, 36, suit_symbol)
            painter.restore()


# --- Player Panel Widget ---
class PlayerPanel(QFrame):
    """Widget displaying a player's info and cards."""

    def __init__(self, player, position, parent=None):
        super().__init__(parent)
        self.player = player
        self.position = position
        self.is_active_turn = False
        self.show_cards = False
        self.position_label_text = ""  # BTN, SB, BB
        # Optional [Card, Card] override — when set, update_display
        # renders THIS instead of self.player.hand. Used by the
        # deceptive-God-Mode path so other humans see fake opponent
        # hole cards while the engine still operates on the real
        # ones internally.
        self.display_override_hand = None

        self.setup_ui()

    def setup_ui(self):
        # Restore the original panel proportions + colours after the
        # 290-wide variant ended up looking flat / pale next to the
        # rest of the board. Panel size, frame style, and the right-
        # side cosmetic spacer all match the version the user
        # screenshotted as "good"; the long-name problem is now
        # handled purely by font sizing in the name label.
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(3)
        # 235 wasn't tall enough to fit name (~30) + stack (~30) + cards
        # (112) + bet line (~30) + best-hand line (~30) plus margins,
        # so the made-hand label at the bottom — "two pair", "A-high",
        # "bottom pair (3s)" etc. — got clipped by the panel border.
        # Bump to 285 so the whole stack of rows shows comfortably.
        self.setFixedSize(240, 285)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: position indicator and name
        top_row = QHBoxLayout()

        # Position indicator (BTN, SB, BB)
        self.pos_label = QLabel("")
        self.pos_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.pos_label.setFixedWidth(35)
        top_row.addWidget(self.pos_label)

        # Name. Default font is 14pt (down from the previous 16) so
        # the canonical character names ("Sharkey Steve",
        # "Optimal Olivia") fit in the original 240-wide panel
        # without auto-shrink kicking in. _fit_name_label drops
        # further to 12 / 11 pt if a longer name appears (custom
        # name, "(#N)" duplicate suffix, etc).
        self.name_label = QLabel(self.player.name)
        self.name_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Preferred)
        top_row.addWidget(self.name_label, stretch=1)

        # Symmetric right-side spacer to balance the position label.
        top_row.addSpacing(35)

        layout.addLayout(top_row)

        # Stack
        self.stack_label = QLabel(f"${self.player.stack}")
        self.stack_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.stack_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stack_label)

        # Cards container
        cards_widget = QWidget()
        cards_layout = QHBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(6)

        self.card1 = CardWidget()
        self.card2 = CardWidget()
        cards_layout.addWidget(self.card1)
        cards_layout.addWidget(self.card2)
        cards_layout.addStretch()

        layout.addWidget(cards_widget)

        # Bet amount — hidden by default; only takes space when the
        # player has chips committed this round. The earlier always-
        # visible empty label was the blank rectangle that appeared
        # between the cards and the made-hand label on every panel.
        self.bet_label = QLabel("")
        self.bet_label.setFont(QFont('Arial', 15, QFont.Weight.Bold))
        self.bet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bet_label.setStyleSheet("color: yellow;")
        self.bet_label.setVisible(False)
        layout.addWidget(self.bet_label)

        # "Current best hand" line — shown for any player whose cards are
        # visible (hero always; villains in god mode / at showdown).  Same
        # font weight/size as the name and stack labels above.  Empty by
        # default; populated via set_best_hand().
        self.best_hand_label = QLabel("")
        self.best_hand_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.best_hand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.best_hand_label.setStyleSheet("color: #ffd966;")
        self.best_hand_label.setWordWrap(True)
        self.best_hand_label.setVisible(False)
        layout.addWidget(self.best_hand_label)

        self.update_display()

    def set_best_hand(self, text: str):
        """Display the hero's current best hand (flop to river only).

        Pass an empty string to hide.  Only the human seat ever calls this.
        """
        if text:
            self.best_hand_label.setText(text)
            self.best_hand_label.setVisible(True)
        else:
            self.best_hand_label.setText("")
            self.best_hand_label.setVisible(False)

    def _fit_name_label(self):
        """Shrink the name font until the text fits the available width.

        Panel is 240 wide with a 35-px pos label, a 35-px right
        spacer, and 10-px margins on each side, so the name label
        gets ~150 px. The canonical 5-bot lineup names all fit at
        14 pt; the fallback only kicks in for custom or duplicate-
        suffixed names. Walks 14 → 13 → 12 → 11 pt.
        """
        try:
            from PyQt6.QtGui import QFontMetrics
            text = self.name_label.text()
            avail = max(40, self.name_label.width() or
                        (self.width() - 20 - 35 - 35 - 6))
            font = QFont('Arial', 14, QFont.Weight.Bold)
            for size in (14, 13, 12, 11):
                font.setPointSize(size)
                metrics = QFontMetrics(font)
                if metrics.horizontalAdvance(text) <= avail - 4:
                    self.name_label.setFont(font)
                    return
            font.setPointSize(11)
            self.name_label.setFont(font)
        except Exception:
            pass

    def update_display(self):
        # Update name (in case it changed due to bot preference)
        self.name_label.setText(self.player.name)
        self._fit_name_label()
        self.stack_label.setText(f"${self.player.stack}")

        if self.player.bet_in_round > 0:
            self.bet_label.setText(f"Bet: ${self.player.bet_in_round}")
            self.bet_label.setVisible(True)
        else:
            self.bet_label.setText("")
            self.bet_label.setVisible(False)

        # Update position label
        self.pos_label.setText(self.position_label_text)
        if self.position_label_text == "BT":
            self.pos_label.setStyleSheet("color: #ffcc00; background: #333; border-radius: 3px; padding: 2px;")
        elif self.position_label_text == "SB":
            self.pos_label.setStyleSheet("color: #66ccff; background: #333; border-radius: 3px; padding: 2px;")
        elif self.position_label_text == "BB":
            self.pos_label.setStyleSheet("color: #ff6666; background: #333; border-radius: 3px; padding: 2px;")
        elif self.position_label_text == "UTG":
            self.pos_label.setStyleSheet("color: #ff9900; background: #333; border-radius: 3px; padding: 2px; font-weight: bold;")
        elif self.position_label_text == "CO":
            self.pos_label.setStyleSheet("color: #99ff99; background: #333; border-radius: 3px; padding: 2px;")
        else:
            self.pos_label.setStyleSheet("")

        # Update cards. display_override_hand wins over player.hand so
        # the deceptive-God-Mode path can swap in fake opponent cards
        # without disturbing the engine's authoritative state.
        rendered_hand = (self.display_override_hand
                         if self.display_override_hand
                         else self.player.hand)
        if rendered_hand and len(rendered_hand) >= 2:
            if self.show_cards:
                self.card1.set_card(str(rendered_hand[0]), face_down=False)
                self.card2.set_card(str(rendered_hand[1]), face_down=False)
            else:
                self.card1.set_card(None, face_down=True)
                self.card2.set_card(None, face_down=True)
        else:
            self.card1.set_card(None, face_down=True)
            self.card2.set_card(None, face_down=True)

        # Update style based on state.
        # If the panel is currently flashing (just raised), the flash color
        # wins over the regular states so the user notices the raise.
        # Tier (still chosen by raise size — normal/orange/red names kept
        # for backward compatibility with _flash_color_for_raise):
        #   * normal panel pulse for small raises (≤ 25% pot)
        #   * orange for medium raises
        #   * "red" tier for large raises / all-ins — but rendered in a
        #     calmer magenta/pink palette than the original blood red,
        #     which was visually alarming over a long session.
        flash_color = getattr(self, '_flashing_raise_color', None)
        if flash_color == 'red':
            self.setStyleSheet(
                "background-color: #4d1a3d; border: 4px solid #ff66cc;")
            self.name_label.setStyleSheet("color: #fff; font-weight: bold;")
        elif flash_color == 'orange':
            self.setStyleSheet(
                "background-color: #5b3a0a; border: 4px solid #ff9930;")
            self.name_label.setStyleSheet("color: #fff; font-weight: bold;")
        elif flash_color == 'normal':
            # Brighten the existing green panel (no color change, just a
            # stronger border / lighter bg) so a raise still pops without
            # the alarmist red colour.
            self.setStyleSheet(
                "background-color: #2f5a2f; border: 4px solid #5cff90;")
            self.name_label.setStyleSheet("color: #fff; font-weight: bold;")
        elif not self.player.active:
            # Folded - gray, no border
            self.setStyleSheet("background-color: #444; color: #888; border: 3px solid #555;")
            self.name_label.setStyleSheet("color: #888;")
        elif self.is_active_turn:
            # Current player's turn - gold border
            self.setStyleSheet("background-color: #2a4a2a; border: 4px solid gold;")
            self.name_label.setStyleSheet("color: white;")
        else:
            # Active (not folded) but not their turn - bright green border
            self.setStyleSheet("background-color: #2a3a2a; border: 3px solid #00cc66;")
            self.name_label.setStyleSheet("color: white;")

    def set_active_turn(self, active):
        self.is_active_turn = active
        self.update_display()

    def flash_raise(self, ms: int = 600, color: str = 'red'):
        """Disabled: raises used to flash the panel pink/orange/etc., but
        the colour change interrupted focus mid-decision. Raises are now
        called out by colouring the matching ticker line yellow at the
        bottom of the screen (see _format_action_log_html), which is
        peripheral and non-distracting. Kept as a no-op so existing
        callers (`_flash_color_for_raise` → `panel.flash_raise(...)`)
        stay valid without further surgery.
        """
        return

    def set_show_cards(self, show):
        self.show_cards = show
        self.update_display()

    def set_position(self, pos_text):
        """Set position indicator (BTN, SB, BB, or empty)."""
        self.position_label_text = pos_text
        self.update_display()


# --- Hand Range Grid Widget (PokerStove-style) ---
class HandRangeGrid(QWidget):
    """Widget displaying a 13x13 PokerStove-style hand range grid."""

    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.range_weights = {}  # Dict of hand -> weight (0.0 to 1.0)
        self.init_empty_range()

    def init_empty_range(self):
        """Initialize all hands with 0 weight."""
        for i, r1 in enumerate(self.RANKS):
            for j, r2 in enumerate(self.RANKS):
                if i < j:
                    hand = f"{r1}{r2}s"  # Suited (above diagonal)
                elif i > j:
                    hand = f"{r2}{r1}o"  # Offsuit (below diagonal)
                else:
                    hand = f"{r1}{r2}"   # Pairs (on diagonal)
                self.range_weights[hand] = 0.0
        self.board_hits = {}

    def set_range(self, range_dict, board_hits=None):
        """Set range weights from a dictionary.

        ``board_hits`` is an optional dict mapping the same hand keys to
        a connection score in [0, 1] reflecting how well the hand makes
        with the current board (top pair, set, made straight, OESD,
        flush draw). Cells with a high connection get a yellow border so
        the user can see at a glance which combos in the range "make
        sense" given the call.
        """
        self.init_empty_range()
        for hand, weight in range_dict.items():
            if hand in self.range_weights:
                self.range_weights[hand] = weight
        self.board_hits = dict(board_hits) if board_hits else {}
        self.update()

    def get_hand_at(self, row, col):
        """Get the hand string for a grid position."""
        r1 = self.RANKS[row]
        r2 = self.RANKS[col]
        if row < col:
            return f"{r1}{r2}s"  # Suited
        elif row > col:
            return f"{r2}{r1}o"  # Offsuit
        else:
            return f"{r1}{r2}"   # Pair

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cell_w = w // 13
        cell_h = h // 13

        # Dynamic font size based on cell size - larger for readability
        font_size = max(14, min(cell_w, cell_h) // 2 - 2)
        font = QFont('Arial', font_size, QFont.Weight.Bold)
        painter.setFont(font)

        for row in range(13):
            for col in range(13):
                x = col * cell_w
                y = row * cell_h

                hand = self.get_hand_at(row, col)
                weight = self.range_weights.get(hand, 0.0)

                # Color based on weight and hand type
                if row == col:  # Pairs - gold tint
                    base_color = QColor(80, 70, 30)
                    full_color = QColor(200, 180, 50)
                elif row < col:  # Suited - green tint
                    base_color = QColor(30, 60, 30)
                    full_color = QColor(50, 180, 50)
                else:  # Offsuit - blue tint
                    base_color = QColor(30, 40, 60)
                    full_color = QColor(70, 120, 180)

                # Interpolate color based on weight
                r = int(base_color.red() + (full_color.red() - base_color.red()) * weight)
                g = int(base_color.green() + (full_color.green() - base_color.green()) * weight)
                b = int(base_color.blue() + (full_color.blue() - base_color.blue()) * weight)

                painter.fillRect(x, y, cell_w - 1, cell_h - 1, QColor(r, g, b))

                # Border: yellow + thicker when this combo connects with
                # the current board (top pair, set, made/draw straight,
                # flush draw). Otherwise the standard dark border.
                hit = (self.board_hits.get(hand, 0.0)
                       if hasattr(self, 'board_hits') else 0.0)
                if hit >= 0.6 and weight > 0.0:
                    # Strong board connection — bright yellow ring,
                    # thickness proportional to the hit score so a set
                    # stands out more than a top-pair.
                    border_w = 3 if hit >= 0.85 else 2
                    painter.setPen(QPen(QColor(255, 220, 60), border_w))
                    painter.drawRect(x + 1, y + 1,
                                     cell_w - 2 - 1, cell_h - 2 - 1)
                else:
                    painter.setPen(QPen(QColor(60, 60, 60), 1))
                    painter.drawRect(x, y, cell_w - 1, cell_h - 1)

                # Draw hand text centered in cell
                if weight > 0.5:
                    painter.setPen(QColor(255, 255, 255))
                else:
                    painter.setPen(QColor(150, 150, 150))
                text_rect = QRectF(x, y, cell_w - 1, cell_h - 1)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, hand)


class PlayerHistoryGrid(QWidget):
    """13x13 grid of how a player has actually played each of the 169
    starting-hand combos this session.

    Color encoding per cell:
      • Cells with no observed sample: dim background (suited/pair/offsuit
        tinted, same family as HandRangeGrid).
      • Green intensity ∝ wins ÷ seen.
      • Red intensity ∝ losses ÷ seen.
      • Cells where the player folded most of the time get a thin gray
        ring; cells they raised most of the time get a gold ring.

    The cell text shows the hand key plus a tiny sample-count badge
    (e.g. "AKs / 3w 1L") so the user can tell n-of-1 cells from real
    samples at a glance.
    """

    RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self._history = {}   # {hand_key: cell dict from _fresh_169_cell}

    def set_history(self, history: dict):
        self._history = dict(history or {})
        self.update()

    def _hand_at(self, row, col):
        r1 = self.RANKS[row]
        r2 = self.RANKS[col]
        if row < col:
            return f"{r1}{r2}s"
        elif row > col:
            return f"{r2}{r1}o"
        return f"{r1}{r2}"

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cw, ch = w // 13, h // 13
        font_size = max(9, min(cw, ch) // 4)
        font = QFont('Arial', font_size, QFont.Weight.Bold)
        p.setFont(font)
        for row in range(13):
            for col in range(13):
                x, y = col * cw, row * ch
                hand = self._hand_at(row, col)
                cell = self._history.get(hand, {})
                seen = int(cell.get('seen', 0))
                won = int(cell.get('won', 0))
                lost = int(cell.get('lost', 0))
                folded = int(cell.get('folded', 0))
                raised = int(cell.get('raised', 0))
                played = int(cell.get('played', 0))

                # Family base tint (same scheme as HandRangeGrid).
                if row == col:
                    base = QColor(45, 38, 16)   # gold-dim for pairs
                elif row < col:
                    base = QColor(20, 36, 20)   # green-dim for suited
                else:
                    base = QColor(20, 26, 38)   # blue-dim for offsuit

                # Win / loss tinting on top of the base.
                if seen > 0:
                    win_rate = won / seen
                    loss_rate = lost / seen
                    # Strong green for high win rate, strong red for
                    # high loss rate.
                    if win_rate >= loss_rate:
                        # Blend toward (60, 180, 60) by win_rate.
                        r = int(base.red() + (60 - base.red()) * win_rate)
                        g = int(base.green()
                                + (200 - base.green()) * win_rate)
                        b = int(base.blue() + (60 - base.blue()) * win_rate)
                    else:
                        r = int(base.red() + (210 - base.red()) * loss_rate)
                        g = int(base.green() + (50 - base.green()) * loss_rate)
                        b = int(base.blue() + (50 - base.blue()) * loss_rate)
                    cell_color = QColor(r, g, b)
                else:
                    cell_color = base

                p.fillRect(x, y, cw - 1, ch - 1, cell_color)

                # Action-rate ring: gold if mostly raised, gray if
                # mostly folded.
                ring_color = None
                if played > 0 and raised / max(played, 1) >= 0.6:
                    ring_color = QColor(255, 215, 70)
                elif seen > 0 and folded / max(seen, 1) >= 0.6:
                    ring_color = QColor(110, 110, 110)
                if ring_color is not None:
                    p.setPen(QPen(ring_color, 2))
                    p.drawRect(x + 1, y + 1, cw - 3, ch - 3)
                else:
                    p.setPen(QPen(QColor(60, 60, 60), 1))
                    p.drawRect(x, y, cw - 1, cw - 1)

                # Cell text — hand key on top, count badge below.
                text_color = (QColor(240, 240, 240)
                              if seen > 0 else QColor(140, 140, 140))
                p.setPen(text_color)
                # Hand key
                p.drawText(QRectF(x, y, cw - 1, (ch - 1) * 0.55),
                           Qt.AlignmentFlag.AlignCenter, hand)
                # Sample badge
                if seen > 0:
                    badge_font = QFont('Arial', max(7, font_size - 3))
                    p.setFont(badge_font)
                    p.setPen(QColor(220, 220, 180))
                    if won + lost > 0:
                        badge = f"{won}w {lost}L"
                    else:
                        badge = f"n={seen}"
                    p.drawText(
                        QRectF(x, y + (ch - 1) * 0.5,
                               cw - 1, (ch - 1) * 0.5),
                        Qt.AlignmentFlag.AlignCenter, badge)
                    p.setFont(font)


class PlayerHistoryDialog(QDialog):
    """Dialog wrapping a PlayerHistoryGrid plus summary stats so the
    user can drill into any seat's session-long play pattern."""

    def __init__(self, player_name: str, history: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{player_name} — session history")
        self.setMinimumSize(700, 760)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)

        title = QLabel(f"{player_name}")
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        v.addWidget(title)

        # Aggregate counters across the 169 grid for the summary line.
        total_seen = sum(c.get('seen', 0) for c in history.values())
        total_played = sum(c.get('played', 0) for c in history.values())
        total_raised = sum(c.get('raised', 0) for c in history.values())
        total_won = sum(c.get('won', 0) for c in history.values())
        total_lost = sum(c.get('lost', 0) for c in history.values())
        total_net = sum(c.get('net_cash', 0) for c in history.values())
        vpip = (100.0 * total_played / total_seen) if total_seen else 0
        pfr = (100.0 * total_raised / total_seen) if total_seen else 0
        wr = (100.0 * total_won / total_seen) if total_seen else 0
        summary = QLabel(
            f"Hands seen: <b>{total_seen}</b>  ·  "
            f"VPIP: <b>{vpip:.0f}%</b>  ·  "
            f"PFR: <b>{pfr:.0f}%</b>  ·  "
            f"Win rate: <b>{wr:.0f}%</b>  ·  "
            f"Net chips: <b>{total_net:+,}</b>  ·  "
            f"Showdowns won/lost: <b>{total_won}</b> / <b>{total_lost}</b>"
        )
        summary.setTextFormat(Qt.TextFormat.RichText)
        summary.setStyleSheet(
            "color: #ddd; padding: 8px; background: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px; font-size: 14pt;")
        v.addWidget(summary)

        legend = QLabel(
            "<span style='color:#88ff88'>green</span> = won often   "
            "<span style='color:#ff7777'>red</span> = lost often   "
            "<span style='color:#ffd966'>gold ring</span> = mostly raised   "
            "<span style='color:#888'>gray ring</span> = mostly folded")
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet("color: #aaa; padding: 4px; font-size: 12pt;")
        v.addWidget(legend)

        grid = PlayerHistoryGrid()
        grid.set_history(history)
        v.addWidget(grid, stretch=1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("font-size: 14pt; padding: 8px;")
        close_btn.clicked.connect(self.accept)
        v.addWidget(close_btn)


class HeroOutsTab(QWidget):
    """Hero's hole cards + outs visualisation, sibling to the per-bot
    range tabs in the Theory of Mind panel.

    Shows:
      • The two hero hole cards in large card widgets.
      • Current best hand on the table.
      • A 4×13 grid of all 52 cards with each cell coloured by role:
          - Hero's hole cards: blue background, bright text.
          - Board cards: light grey, bold black text.
          - Outs (cards that would improve the hero's hand class):
            gold border + bright yellow text.
          - Other unseen cards: dim grey.
      • Outs count + textual list of which cards are outs.
    """

    # Order matches eval7's handtype ranking; lower index = stronger.
    # eval7.handtype() returns the SHORT names ("Trips", "Quads", etc.) —
    # the long names ("Three of a Kind", "Four of a Kind") cause
    # _class_index() to fall through to the unknown-class fallback,
    # which then mis-ranks Trips/Quads as weaker than Pair. Keep both
    # spellings so any caller that produces either form lines up
    # correctly.
    _HAND_CLASS_ORDER = [
        "Straight Flush",
        "Quads", "Four of a Kind",
        "Full House",
        "Flush",
        "Straight",
        "Trips", "Three of a Kind",
        "Two Pair",
        "Pair",
        "High Card",
    ]
    _SUITS_ORDER = ['s', 'h', 'd', 'c']
    _RANKS_ORDER = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cell_widgets = {}  # 'As'/'Kd'/etc → (cell_label, role)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(15, 15, 15, 15)

        # ----- Top: hero hole cards (live widgets) -----
        title = QLabel("Your hand")
        title.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #fff;")
        outer.addWidget(title)

        # Cards row: hero hole cards on the left, commitment-math
        # block stretched to the right of the same row so the empty
        # space next to the cards earns its keep. We use a single
        # styled QLabel with rich-text HTML for the math block —
        # nesting QLabels inside a QFrame caused the inner labels to
        # render invisibly under some Qt themes (the QFrame's QSS
        # bled into the children even with explicit overrides).
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        self._card1 = CardWidget()
        self._card2 = CardWidget()
        # Pin the 80x112 cards to the TOP of the row so the row's
        # height isn't capped at the card height — without AlignTop
        # the commit label (which can be 4-6 lines tall after the
        # SPR / commitment-ratio / equity block is filled in) got
        # clipped to ~140 px and only its first line showed.
        cards_row.addWidget(
            self._card1, alignment=Qt.AlignmentFlag.AlignTop)
        cards_row.addWidget(
            self._card2, alignment=Qt.AlignmentFlag.AlignTop)
        cards_row.addSpacing(20)

        # Stack of QLabels in a QVBoxLayout. Each line carries an
        # explicit minimum height so the QFrame's sizeHint adds up to
        # a sensible total — without that, the parent HBoxLayout
        # compresses everything below the title onto the same row.
        commit_box = QFrame()
        commit_box.setStyleSheet(
            "QFrame { background-color: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px; }"
        )
        commit_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding)
        commit_box.setMinimumHeight(260)
        cv = QVBoxLayout(commit_box)
        cv.setContentsMargins(16, 10, 16, 14)
        cv.setSpacing(10)

        def _make_line(font_pt, color, bold=False, min_h=34):
            lbl = QLabel("")
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            weight = "bold" if bold else "normal"
            lbl.setStyleSheet(
                f"color: {color}; font-size: {font_pt}pt;"
                f" font-weight: {weight};"
                " background: transparent; border: none;")
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            lbl.setMinimumHeight(min_h)
            return lbl

        self._commit_title = _make_line(22, "#ffffff", bold=True, min_h=40)
        self._commit_title.setText("Pot Commitment")
        cv.addWidget(self._commit_title)

        self._commit_ratio = _make_line(18, "#dddddd", min_h=38)
        cv.addWidget(self._commit_ratio)

        self._commit_spr = _make_line(18, "#dddddd", min_h=38)
        cv.addWidget(self._commit_spr)

        self._commit_equity = _make_line(18, "#dddddd", min_h=38)
        cv.addWidget(self._commit_equity)

        self._commit_math = _make_line(14, "#aaaaaa", min_h=28)
        cv.addWidget(self._commit_math)

        cv.addStretch(1)
        # Keep the same attribute name so existing helpers can still
        # poke at it (we mostly use the per-section labels now).
        self._commit_label = commit_box
        cards_row.addWidget(commit_box, stretch=1)
        outer.addLayout(cards_row)
        # Seed the placeholder so the panel has visible content at
        # construction time (before any hand has been dealt).
        self._refresh_commit_panel(None, None, None, None)

        # ----- Made-hand line + outs count -----
        info_row = QHBoxLayout()
        self._made_label = QLabel("(deal a hand)")
        self._made_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self._made_label.setStyleSheet("color: #ffd966;")
        info_row.addWidget(self._made_label)
        info_row.addStretch()
        self._outs_count_label = QLabel("Outs: —")
        self._outs_count_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self._outs_count_label.setStyleSheet("color: #88ff88;")
        info_row.addWidget(self._outs_count_label)
        outer.addLayout(info_row)

        # ----- 4×13 grid of every card in the deck -----
        grid_label = QLabel("Cards in the deck (yellow = your outs)")
        grid_label.setFont(QFont('Arial', 14))
        grid_label.setStyleSheet("color: #aaa;")
        outer.addWidget(grid_label)

        grid_frame = QFrame()
        grid_frame.setStyleSheet(
            "QFrame { background: #1a1a1a; border: 1px solid #333; "
            "border-radius: 4px; padding: 6px; }"
        )
        grid = QGridLayout(grid_frame)
        grid.setSpacing(2)
        suit_symbols = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
        for r_idx, suit in enumerate(self._SUITS_ORDER):
            sym = suit_symbols[suit]
            head = QLabel(sym)
            head.setFont(QFont('Arial', 16, QFont.Weight.Bold))
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setFixedSize(28, 28)
            head.setStyleSheet("color: #ddd;")
            grid.addWidget(head, r_idx, 0)
            for c_idx, rank in enumerate(self._RANKS_ORDER):
                cell = QLabel(rank)
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setFixedSize(34, 28)
                cell.setFont(QFont('Arial', 13, QFont.Weight.Bold))
                grid.addWidget(cell, r_idx, c_idx + 1)
                self._cell_widgets[rank + suit] = cell
                self._paint_cell(cell, role='unknown')
        outer.addWidget(grid_frame)

        # ----- Outs list (textual) -----
        self._outs_text = QLabel("")
        self._outs_text.setFont(QFont('Courier', 14))
        self._outs_text.setWordWrap(True)
        self._outs_text.setStyleSheet(
            "color: #ffd966; background: #1a1a1a; padding: 10px;"
            " border: 1px solid #333; border-radius: 4px;"
        )
        outer.addWidget(self._outs_text)
        outer.addStretch()

    def _paint_cell(self, cell: QLabel, role: str):
        """Apply per-role styling to a deck-grid cell."""
        styles = {
            'hole':    "color: #fff; background: #1a4d8a; border: 2px solid #66aaff; border-radius: 4px;",
            'board':   "color: #000; background: #ffffff; border: 1px solid #ccc; border-radius: 4px;",
            'out':     "color: #000; background: #ffd966; border: 2px solid #ffaa00; border-radius: 4px;",
            'dead':    "color: #555; background: #2a2a2a; border: 1px dashed #555; border-radius: 4px;",
            'unknown': "color: #888; background: #222; border: 1px solid #333; border-radius: 4px;",
        }
        cell.setStyleSheet("QLabel { " + styles.get(role, styles['unknown']) + " }")

    def update_outs(self, hero_hand, board, dead_cards=None,
                    pot=None, to_call=None, hero_stack=None,
                    equity_pct=None):
        """Refresh hole-card display, made-hand summary, outs grid, and
        the pot-commitment math panel on the right.

        Args:
            hero_hand: list of 2 eval7.Card or card-like with str().
            board:     list of 0-5 community cards.
            dead_cards: optional iterable of cards revealed by villains
                (e.g. at showdown / in god mode) — drawn dead-grey on
                the grid so the user knows they can't draw to them.
            pot:       current pot size before any pending call.
            to_call:   chips Hero owes to continue (0 means we're not
                       facing a bet — commitment panel hides the math).
            hero_stack: Hero's remaining stack BEFORE calling.
            equity_pct: optional 0-100 equity vs villain ranges; when
                       supplied, the panel adds "your equity X% vs
                       pot odds Y% → call/fold" to make the commitment
                       advice concrete.
        """
        self._refresh_commit_panel(pot, to_call, hero_stack, equity_pct)
        # Reset every cell to "unknown" first.
        for k, cell in self._cell_widgets.items():
            cell.setText(k[0])  # Just the rank; suit shown by row header
            self._paint_cell(cell, role='unknown')

        # Hero hole cards.
        try:
            if hero_hand and len(hero_hand) >= 2:
                self._card1.set_card(str(hero_hand[0]), face_down=False)
                self._card2.set_card(str(hero_hand[1]), face_down=False)
                for c in hero_hand[:2]:
                    key = str(c)
                    if key in self._cell_widgets:
                        self._paint_cell(self._cell_widgets[key], role='hole')
            else:
                self._card1.set_card(None, face_down=True)
                self._card2.set_card(None, face_down=True)
        except Exception:
            pass

        # Board cards.
        for c in board or []:
            key = str(c)
            if key in self._cell_widgets:
                self._paint_cell(self._cell_widgets[key], role='board')

        # Dead cards (known to be in opponents' hands).
        for c in dead_cards or []:
            key = str(c)
            if key in self._cell_widgets:
                self._paint_cell(self._cell_widgets[key], role='dead')

        # ----- Made-hand label + outs computation -----
        outs = []
        made_label_text = ""
        try:
            import eval7
            if hero_hand and len(hero_hand) >= 2 and 3 <= len(board or []) <= 4:
                hero_e7 = [eval7.Card(str(c)) for c in hero_hand[:2]]
                board_e7 = [eval7.Card(str(c)) for c in board]
                cur_rank = eval7.evaluate(hero_e7 + board_e7)
                cur_class = eval7.handtype(cur_rank)
                made_label_text = f"Best now: {cur_class}"

                # Build set of unseen cards.
                used = {str(c) for c in hero_hand[:2]}
                used.update(str(c) for c in board)
                used.update(str(c) for c in (dead_cards or []))

                pair_idx = self._class_index('Pair')
                high_card_idx = self._class_index('High Card')
                # Ranks Hero holds in the hole and ranks already on the
                # board — used to filter out "shared improvement" cards.
                hero_ranks_held = {str(c)[0] for c in hero_hand[:2]}
                board_rank_set = {str(c)[0] for c in board}
                # Highest-ranked card on the board (lower index = higher
                # rank in 'AKQJT98765432'). Used to decide whether
                # 'High Card → Pair' counts as an out: pairing an
                # overcard makes top pair (a real out); pairing a card
                # below the highest board card makes middle / bottom
                # pair, which often loses to a top-pair villain.
                rank_order = 'AKQJT98765432'
                board_rank_indices = [
                    rank_order.index(c) for c in board_rank_set
                    if c in rank_order
                ]
                board_high_idx = (min(board_rank_indices)
                                  if board_rank_indices else 0)
                for key in self._cell_widgets:
                    if key in used:
                        continue
                    new_rank = eval7.evaluate(
                        hero_e7 + board_e7 + [eval7.Card(key)])
                    new_class = eval7.handtype(new_rank)
                    new_idx = self._class_index(new_class)
                    cur_idx = self._class_index(cur_class)
                    new_card_rank = key[0]
                    # "Shared improvement" filter — a card whose rank is
                    # already on the board pairs the board for every
                    # player, so the category bump is not exclusive to
                    # Hero. Example: K3 on Q-Q-2-2 — eval7 says Q or 2
                    # takes Hero from Two Pair → Full House, but every
                    # opponent's category goes up the same amount and
                    # anyone holding a Q makes quads. Skip those.
                    if (new_card_rank in board_rank_set
                            and new_card_rank not in hero_ranks_held):
                        continue
                    # Three paths to count this card as an out:
                    # (a) Hand category strictly improves AND lands at
                    #     Pair or better — classic outs (drawing to
                    #     two pair / trips / straight / flush / etc.).
                    if new_idx < cur_idx and new_idx < pair_idx:
                        outs.append(key)
                        continue
                    # (b) High Card → Pair where the paired rank is at
                    #     least the highest card on the board (top pair
                    #     or overpair). Without this branch, KJ on T78
                    #     showed only the gutshot 9 as outs and missed
                    #     the 6 overcard pair outs (KK / JJ).
                    if (cur_idx == high_card_idx
                            and new_idx == pair_idx
                            and new_card_rank in hero_ranks_held
                            and new_card_rank in rank_order
                            and rank_order.index(new_card_rank) <= board_high_idx):
                        outs.append(key)
                        continue
                    # (c) Same hand category, but Hero's hole-card
                    #     kicker pairs up to give a *strictly stronger*
                    #     hand. This catches cases like K3 on Q-Q-2-2
                    #     where pairing the K leaves the category at
                    #     Two Pair but the new pair (KK + QQ) beats the
                    #     old (QQ + 22). Detect by comparing the eval7
                    #     numeric rank — higher number = stronger hand
                    #     in eval7's encoding when category is the
                    #     same.
                    if (new_card_rank in hero_ranks_held
                            and new_idx == cur_idx
                            and new_rank > cur_rank
                            and new_idx <= pair_idx):
                        outs.append(key)

                for key in outs:
                    cell = self._cell_widgets.get(key)
                    if cell is not None:
                        self._paint_cell(cell, role='out')
            elif hero_hand and len(hero_hand) >= 2 and not board:
                made_label_text = "Preflop — outs depend on flop"
        except Exception as ex:
            made_label_text = f"(could not evaluate: {ex})"

        self._made_label.setText(made_label_text or "(deal a hand)")
        self._outs_count_label.setText(
            f"Outs: {len(outs)}" if outs else "Outs: 0"
        )
        if outs:
            # Group by suit for readable listing.
            grouped = {s: [] for s in self._SUITS_ORDER}
            for key in outs:
                if len(key) >= 2 and key[1] in grouped:
                    grouped[key[1]].append(key[0])
            symbols = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
            parts = []
            for s in self._SUITS_ORDER:
                ranks = grouped[s]
                if ranks:
                    # Sort highest first per the canonical rank order.
                    rank_order = {r: i for i, r in enumerate(self._RANKS_ORDER)}
                    ranks.sort(key=lambda r: rank_order.get(r, 99))
                    parts.append(f"{symbols[s]} {' '.join(ranks)}")
            self._outs_text.setText("  ".join(parts) if parts else "")
        else:
            self._outs_text.setText("")

    def update_commit_panel(self, pot=None, to_call=None,
                             hero_stack=None, equity_pct=None):
        """Refresh just the pot-commitment math block. Lets the caller
        update equity-aware advice after the equity Monte-Carlo run
        finishes (which happens later in update_analysis than the
        cheap card / outs render)."""
        self._refresh_commit_panel(pot, to_call, hero_stack, equity_pct)

    def _refresh_commit_panel(self, pot, to_call, hero_stack, equity_pct):
        """Render the pot-commitment math block to the right of the
        hero hole cards. Spells out SPR (Stack-to-Pot Ratio) since
        not every player knows the acronym.

        When there's no live bet to face, we still show the *current*
        SPR (stack / pot) so the user can see going-in commitment
        before they have to make a decision.
        """
        try:
            pot_v = int(pot) if pot is not None else None
            tc_v = int(to_call) if to_call is not None else None
            stk_v = int(hero_stack) if hero_stack is not None else None
        except (TypeError, ValueError):
            pot_v = tc_v = stk_v = None

        # No live bet to face — show going-in SPR.
        if pot_v is None or stk_v is None or tc_v is None or tc_v <= 0:
            if pot_v is not None and stk_v is not None and pot_v > 0:
                spr_now = stk_v / pot_v
                if spr_now < 1.0:
                    zone_short = ("<b style='color:#ff7777;'>"
                                  "POT-COMMITTED</b> "
                                  "(SPR &lt; 1)")
                elif spr_now < 3.0:
                    zone_short = ("<span style='color:#ffd966;'>"
                                  "Borderline</span> (SPR 1–3)")
                else:
                    zone_short = ("<span style='color:#88ff88;'>"
                                  "Not committed</span> (SPR ≥ 3)")
                self._commit_ratio.setText(
                    "<i style='color:#aaa;'>No bet to face — "
                    "pot odds don't apply yet.</i>")
                self._commit_spr.setText(
                    f"<b>SPR</b> (stack ÷ pot): "
                    f"<b>{spr_now:.2f}</b> &nbsp; → {zone_short}")
                self._commit_equity.setText("")
                self._commit_math.setText(
                    f"Pot ${pot_v:,} &nbsp;·&nbsp; "
                    f"behind ${stk_v:,}")
            else:
                self._commit_ratio.setText(
                    "<i style='color:#999;'>(no live bet to call — "
                    "commitment math appears here when there's a bet "
                    "to face)</i>")
                self._commit_spr.setText("")
                self._commit_equity.setText("")
                self._commit_math.setText("")
            return

        stack_after = max(0, stk_v - tc_v)
        pot_after = pot_v + tc_v
        spr = (stack_after / pot_after) if pot_after > 0 else 0.0
        pot_odds_pct = (100.0 * tc_v / pot_after) if pot_after > 0 else 0.0
        commit_ratio_pct = (100.0 * tc_v / stk_v) if stk_v > 0 else 100.0

        # One-line verdict tags — keep each tier tight so a single
        # QLabel row never wraps to 3+ lines and crowds the next
        # section.
        if spr < 1.0:
            zone_tag = ("<b style='color:#ff7777;'>"
                        "POT-COMMITTED</b> (SPR &lt; 1)")
        elif spr < 3.0:
            zone_tag = ("<span style='color:#ffd966;'>"
                        "Borderline</span> (SPR 1–3)")
        else:
            zone_tag = ("<span style='color:#88ff88;'>"
                        "Not committed</span> (SPR ≥ 3)")

        if commit_ratio_pct >= 33.0:
            ratio_tag = ("<b style='color:#ff7777;'>"
                         "EFFECTIVELY COMMITTED</b>")
        elif commit_ratio_pct >= 15.0:
            ratio_tag = ("<span style='color:#ffd966;'>"
                         "Meaningful</span>")
        else:
            ratio_tag = ("<span style='color:#88ff88;'>Light</span>")

        self._commit_ratio.setText(
            f"<b>Pot Commitment Ratio</b>: "
            f"<b>{commit_ratio_pct:.1f}%</b> of your stack &nbsp; → "
            f"{ratio_tag}"
        )
        self._commit_spr.setText(
            f"<b>SPR after call</b>: <b>{spr:.2f}</b> &nbsp; → {zone_tag}"
        )

        # Equity check — only shown when caller passes a number.
        if equity_pct is not None:
            try:
                eq = float(equity_pct)
                verdict = ("<span style='color:#ff7777;'><b>"
                           "Unprofitable call</b></span>") \
                    if eq < pot_odds_pct else \
                    ("<span style='color:#88ff88;'><b>"
                     "Profitable call</b></span>")
                self._commit_equity.setText(
                    f"Pot odds <b>{pot_odds_pct:.1f}%</b> &nbsp; vs "
                    f"&nbsp; Equity <b>{eq:.1f}%</b> &nbsp; → {verdict}"
                )
            except (TypeError, ValueError):
                self._commit_equity.setText("")
        else:
            self._commit_equity.setText("")

        self._commit_math.setText(
            f"Putting in ${tc_v:,} of ${stk_v:,} stack — "
            f"${stack_after:,} behind into a ${pot_after:,} pot."
        )

    def _class_index(self, hand_class: str) -> int:
        """Return rank index of a hand-type string (lower = stronger).

        eval7 uses canonical hand-class names; an unknown name falls
        through to the weakest tier so we never return False on an
        improvement that we can't classify.
        """
        try:
            return self._HAND_CLASS_ORDER.index(hand_class)
        except ValueError:
            return len(self._HAND_CLASS_ORDER)


class TheoryOfMindTab(QWidget):
    """Tab content for a single bot's theory of mind analysis."""

    def __init__(self, player_name, player_style, parent=None):
        super().__init__(parent)
        self.player_name = player_name
        self.player_style = player_style

        layout = QHBoxLayout(self)
        layout.setSpacing(20)

        # Left: Hand range grid (fixed size to ensure full display)
        left_layout = QVBoxLayout()

        # Title row + per-player History button. The button opens a
        # 169-grid heatmap of this seat's session-long play pattern so
        # the user can see at a glance which combos this opponent
        # actually plays / wins / folds.
        title_row = QHBoxLayout()
        grid_label = QLabel(f"Estimated Range for {player_name}")
        grid_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        grid_label.setStyleSheet("color: #fff;")
        title_row.addWidget(grid_label, stretch=1)
        self.history_btn = QPushButton("History")
        self.history_btn.setStyleSheet(
            "QPushButton { background: #2a3a4a; color: #ddd;"
            " font-size: 13pt; font-weight: bold;"
            " padding: 4px 14px; border: 1px solid #4a5a6a;"
            " border-radius: 5px; }"
            "QPushButton:hover { background: #3a4a5a; }")
        self.history_btn.setToolTip(
            f"Open {player_name}'s session play pattern")
        self.history_btn.clicked.connect(self._show_history)
        title_row.addWidget(self.history_btn)
        left_layout.addLayout(title_row)

        self.range_grid = HandRangeGrid()
        self.range_grid.setFixedSize(420, 420)  # Fixed size to ensure all 13 rows visible
        left_layout.addWidget(self.range_grid)
        left_layout.addStretch()

        layout.addLayout(left_layout)

        # Right: Text explanation
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        # PokerStove notation entry
        notation_label = QLabel("PokerStove Notation:")
        notation_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        notation_label.setStyleSheet("color: #aaa;")
        right_layout.addWidget(notation_label)

        self.notation_text = QLabel("")
        self.notation_text.setFont(QFont('Courier', 20))
        self.notation_text.setStyleSheet("background-color: #222; color: #0f0; padding: 15px; border: 2px solid #444;")
        self.notation_text.setWordWrap(True)
        self.notation_text.setMinimumHeight(80)
        right_layout.addWidget(self.notation_text)

        # Explanation
        explain_label = QLabel("Analysis:")
        explain_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        explain_label.setStyleSheet("color: #aaa;")
        right_layout.addWidget(explain_label)

        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setFont(QFont('Arial', 16))
        self.explanation_text.setStyleSheet("background-color: #1a1a1a; color: #ddd; border: 2px solid #444; padding: 10px;")
        right_layout.addWidget(self.explanation_text, stretch=1)

        layout.addLayout(right_layout, stretch=1)

    def update_analysis(self, range_dict, notation, explanation, board_hits=None):
        """Update the tab with new range analysis.

        ``board_hits`` is an optional dict (hand → 0..1 connection score)
        passed straight through to the grid so board-connecting combos
        get the yellow callout border.
        """
        self.range_grid.set_range(range_dict, board_hits=board_hits)
        self.notation_text.setText(notation)
        self.explanation_text.setText(explanation)

    def _show_history(self):
        """Pop the 169-grid heatmap of this player's session history."""
        # Walk up to find the owning PokerWindow (set on
        # TheoryOfMindPanel._owner_window when the panel was wired up).
        win = None
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, '_player_169_history'):
                win = parent
                break
            owner = getattr(parent, '_owner_window', None)
            if owner is not None and hasattr(owner, '_player_169_history'):
                win = owner
                break
            parent = parent.parent()
        history = {}
        if win is not None:
            history = win._player_169_history.get(self.player_name, {})
        dlg = PlayerHistoryDialog(self.player_name, history, parent=self)
        dlg.exec()


class MetricBar(QWidget):
    """Compact horizontal bar for one decision metric.

    Renders: [LABEL] [============████░░░░░░] VALUE
                                    ^tick

    The bar fill represents the metric's value (0..max). A 1-pixel
    yellow tick overlays the threshold (e.g. pot odds tick on the
    equity bar), making the equity-vs-pot-odds comparison glanceable.

    Color of the fill reflects the verdict:
      green  → metric beats threshold (or otherwise good)
      red    → falls short
      amber  → borderline
      blue   → neutral (no threshold to compare against)
    """

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = 0.0          # raw metric value
        self._max = 1.0            # bar's full-scale value
        self._fill_text = ""        # right-side text (e.g. "23%")
        self._tick = None          # threshold value, or None
        self._color = QColor("#0af")
        self._dim = False
        # Shorter rows so the whole dashboard takes ~45% less vertical
        # space, leaving room for the tabs (and the 13×13 range grid
        # inside them) to take ~3/4 of the screen.
        self.setMinimumHeight(20)
        self.setMaximumHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_metric(self, value: float, max_value: float,
                   text: str = "", tick: float | None = None,
                   color: str = "#0af", dim: bool = False):
        self._value = max(0.0, float(value))
        self._max = max(1e-9, float(max_value))
        self._fill_text = text or ""
        self._tick = (None if tick is None
                      else max(0.0, float(tick)))
        self._color = QColor(color)
        self._dim = bool(dim)
        self.update()

    def set_label(self, label: str):
        self._label = label
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        label_w = 180
        value_w = 100
        bar_x = label_w
        bar_w = max(0, w - label_w - value_w - 8)
        bar_h = max(10, h - 6)
        bar_y = (h - bar_h) // 2

        # Label (left)
        p.setPen(QColor("#cccccc" if not self._dim else "#666666"))
        font = p.font()
        font.setPointSize(11)
        font.setBold(True)
        p.setFont(font)
        p.drawText(8, 0, label_w - 8, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._label)

        # Track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#262626"))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)

        # Fill
        ratio = min(1.0, self._value / self._max) if self._max else 0.0
        fill_w = int(bar_w * ratio)
        fill_color = QColor(self._color)
        if self._dim:
            fill_color.setAlpha(110)
        p.setBrush(fill_color)
        if fill_w > 0:
            p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 4, 4)

        # Threshold tick (e.g. pot odds tick on equity bar)
        if self._tick is not None and self._max > 0:
            tick_ratio = min(1.0, self._tick / self._max)
            tick_x = bar_x + int(bar_w * tick_ratio)
            p.setPen(QPen(QColor("#ffd966"), 2))
            p.drawLine(tick_x, bar_y - 2,
                       tick_x, bar_y + bar_h + 2)

        # Right-side value text
        p.setPen(QColor("#ffffff" if not self._dim else "#777777"))
        font2 = p.font()
        font2.setPointSize(11)
        font2.setBold(True)
        p.setFont(font2)
        p.drawText(bar_x + bar_w + 6, 0, value_w - 6, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._fill_text)
        p.end()


class MetricDashboard(QWidget):
    """Stack of MetricBars for the glanceable decision strip.

    Includes:
      • Equity (with pot-odds threshold tick)
      • Pot odds  (call price as % of pot-after-call)
      • Implied break-even %  (price ÷ (pot + price + 0.5·stack))
      • SPR after call (0..10 capped)
      • Pot Commitment % (price ÷ current stack)
      • Outs (0..20)
      • Nash push gauge — only shown if hero stack ≤ 15 BB
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 4, 8, 4)
        v.setSpacing(1)
        TIPS = {
            'equity': (
                "Equity vs ranges\n\n"
                "Your hand's chance to win at showdown against each "
                "opponent's estimated range (Monte Carlo).\n"
                "The YELLOW TICK is the pot-odds threshold — fill "
                "extending past the tick = profitable call on immediate "
                "equity alone.\n"
                "Color: green = beats pot odds, amber = borderline, "
                "red = falls short."),
            'pot_odds': (
                "Pot odds (required equity)\n\n"
                "The break-even equity for a call:  call / (pot + call).\n"
                "If your hand equity ≥ this number you have a profitable "
                "call on immediate equity, before considering implied "
                "odds.\n"
                "On an unraised preflop limp the tag '(BB)' marks the "
                "metric as non-binding — you're paying the BB to enter, "
                "not a real bet."),
            'implied': (
                "Implied break-even %\n\n"
                "Equity you'd need to break even IF you collect future "
                "bets when you hit (≈ 50% of avg opponent stack).\n"
                "Much lower than pot odds → set-mining / drawing-hand "
                "spots become profitable below the immediate-equity "
                "threshold."),
            'reverse_implied': (
                "Reverse Implied Odds (risk)\n\n"
                "How much extra you can expect to LOSE when you make a "
                "hand that's still second-best — small flush vs nut "
                "flush, low kicker on top pair, set into straight.\n"
                "Expressed as a % of your remaining stack at risk.\n"
                "  • Higher = the hand is dominated-prone.\n"
                "  • Sklansky: 'matters most with hands that are good "
                "now but vulnerable to being out-kicked or out-drawn'."),
            'spr': (
                "Stack-to-Pot Ratio (SPR) after call\n\n"
                "(remaining stack) / (post-call pot).\n"
                "  • SPR < 1   POT-COMMITTED — can't fold to later bets.\n"
                "  • SPR 1–3  decision band — calling commits you next "
                "street.\n"
                "  • SPR ≥ 3   flexible — room to fold future pressure.\n"
                "Smaller SPR favors all-in tactics with one pair / "
                "draws; larger SPR favors set-mining and implied odds."),
            'commit': (
                "Pot Commitment %\n\n"
                "Fraction of your CURRENT stack you're about to put in.\n"
                "  • ≥ 33% Gordon: 'almost certainly can't fold next "
                "street' — proceed only with a hand you'll play.\n"
                "  • 15–33% meaningful commitment, plan ahead.\n"
                "  • < 15% light — easy to fold to future pressure."),
            'outs': (
                "Outs\n\n"
                "Number of cards left in the deck that turn your hand "
                "into a likely winner (eval7-driven, same count as the "
                "Hero tab grid).\n"
                "Rule of 4/2: multiply by 4 (flop→river) or by 2 "
                "(turn→river) for approximate % to hit.\n"
                "Color: ≥9 outs = strong draw, 4–8 = workable, ≤3 = "
                "long-shot."),
            'nash': (
                "Nash push range (short stack)\n\n"
                "Only appears when hero stack ≤ 15 BB.\n"
                "Shows the percentage of all 169 hand combos that "
                "should shove at this stack depth (Chen/Ankenman SB-vs-"
                "BB heads-up Nash).\n"
                "The YELLOW TICK is your hand's strength percentile — "
                "if your bar extends past the tick, SHOVE; otherwise "
                "FOLD."),
        }
        self.equity_bar = MetricBar("Equity vs ranges")
        self.equity_bar.setToolTip(TIPS['equity'])
        v.addWidget(self.equity_bar)
        self.potodds_bar = MetricBar("Pot odds")
        self.potodds_bar.setToolTip(TIPS['pot_odds'])
        v.addWidget(self.potodds_bar)
        self.implied_bar = MetricBar("Implied break-even")
        self.implied_bar.setToolTip(TIPS['implied'])
        v.addWidget(self.implied_bar)
        self.reverse_implied_bar = MetricBar("Reverse implied (risk)")
        self.reverse_implied_bar.setToolTip(TIPS['reverse_implied'])
        v.addWidget(self.reverse_implied_bar)
        self.spr_bar = MetricBar("SPR after call")
        self.spr_bar.setToolTip(TIPS['spr'])
        v.addWidget(self.spr_bar)
        self.commit_bar = MetricBar("Pot commitment %")
        self.commit_bar.setToolTip(TIPS['commit'])
        v.addWidget(self.commit_bar)
        self.outs_bar = MetricBar("Outs (≤ 20)")
        self.outs_bar.setToolTip(TIPS['outs'])
        v.addWidget(self.outs_bar)
        self.nash_bar = MetricBar("Nash push range (≤15bb)")
        self.nash_bar.setToolTip(TIPS['nash'])
        v.addWidget(self.nash_bar)
        self.nash_bar.setVisible(False)
        self.setStyleSheet(
            "MetricDashboard { background: #181818;"
            " border: 1px solid #333; border-radius: 6px; }"
        )

    def update_metrics(
        self, *, equity_pct: float | None, pot_odds_pct: float | None,
        implied_pct: float | None, spr: float | None,
        commit_pct: float | None, outs: int | None,
        stack_bb: float | None, hero_hand=None,
        unraised_preflop: bool = False,
        reverse_implied_pct: float | None = None,
    ):
        # Equity bar — pot-odds tick + color verdict
        if equity_pct is None:
            self.equity_bar.set_metric(0, 100, "--", color="#0af", dim=True)
        else:
            tick = (pot_odds_pct if pot_odds_pct and not unraised_preflop
                    else None)
            if unraised_preflop or pot_odds_pct is None:
                col = "#0af"
            elif equity_pct >= pot_odds_pct:
                col = "#88ff88"
            elif equity_pct >= pot_odds_pct * 0.75:
                col = "#ffd966"
            else:
                col = "#ff7777"
            self.equity_bar.set_metric(
                equity_pct, 100, f"{equity_pct:.1f}%",
                tick=tick, color=col)

        # Pot odds bar
        if pot_odds_pct is None:
            self.potodds_bar.set_metric(0, 100, "--", color="#f80", dim=True)
        else:
            tag = "" if not unraised_preflop else " (BB)"
            self.potodds_bar.set_metric(
                pot_odds_pct, 100, f"{pot_odds_pct:.1f}%{tag}",
                color="#f80", dim=unraised_preflop)

        # Implied break-even — a very low number means deep implied odds.
        if implied_pct is None:
            self.implied_bar.set_metric(0, 50, "--", color="#a8f", dim=True)
        else:
            self.implied_bar.set_metric(
                implied_pct, 50, f"{implied_pct:.1f}%",
                color="#a8f")

        # Reverse implied — heuristic "stack-at-risk" % when the hand
        # is good-now-but-fragile (low kicker top pair / 2nd-nut
        # flush / dominated kicker). Colored red for high risk, amber
        # for moderate, dim/blue otherwise.
        if reverse_implied_pct is None:
            self.reverse_implied_bar.set_metric(
                0, 30, "--", color="#a8f", dim=True)
        else:
            if reverse_implied_pct >= 20:
                col = "#ff7777"
            elif reverse_implied_pct >= 10:
                col = "#ffd966"
            else:
                col = "#88ff88"
            self.reverse_implied_bar.set_metric(
                reverse_implied_pct, 30,
                f"{reverse_implied_pct:.1f}%", color=col)

        # SPR after call (cap at 10 — anything above is "very deep").
        if spr is None:
            self.spr_bar.set_metric(0, 10, "--", color="#0af", dim=True)
        else:
            if spr < 1:
                col = "#ff7777"
            elif spr < 3:
                col = "#ffd966"
            else:
                col = "#88ff88"
            self.spr_bar.set_metric(
                min(spr, 10), 10, f"{spr:.2f}", color=col)

        # Pot commitment % — > 33 % = effectively committed.
        if commit_pct is None:
            self.commit_bar.set_metric(0, 100, "--", color="#0af", dim=True)
        else:
            if commit_pct >= 33:
                col = "#ff7777"
            elif commit_pct >= 15:
                col = "#ffd966"
            else:
                col = "#88ff88"
            self.commit_bar.set_metric(
                commit_pct, 100, f"{commit_pct:.1f}%", color=col)

        # Outs (0..20+)
        if outs is None:
            self.outs_bar.set_metric(0, 20, "--", color="#0f0", dim=True)
        else:
            col = ("#88ff88" if outs >= 9
                   else "#ffd966" if outs >= 4 else "#aaaaaa")
            self.outs_bar.set_metric(
                min(outs, 20), 20, f"{outs}", color=col)

        # Nash push gauge — show only when short-stacked.
        if stack_bb is not None and stack_bb <= 15:
            self.nash_bar.setVisible(True)
            push_pct = nash_push_pct(stack_bb) * 100
            # If we know hero's hand strength percentile, also show
            # whether THIS hand is in the push range.
            verdict = ""
            tick = None
            if hero_hand and len(hero_hand) >= 2:
                pct = hand_strength_percentile(hero_hand) * 100
                # Top X% of hands → 100-X percentile threshold
                in_range = pct >= (100 - push_pct)
                verdict = (" SHOVE" if in_range else " FOLD")
                tick = 100 - push_pct
            col = "#ff7777" if stack_bb <= 6 else "#ffd966"
            self.nash_bar.set_metric(
                push_pct, 100,
                f"top {push_pct:.0f}% @ {stack_bb:.0f}bb{verdict}",
                tick=tick, color=col)
        else:
            self.nash_bar.setVisible(False)


class TheoryOfMindPanel(QWidget):
    """Panel with tabs for each bot's theory of mind analysis."""

    # Starting ranges by player style - with loose/neutral/tight variants
    STYLE_RANGES = {
        'tight': {
            'preflop_open': {
                'loose': "AA, KK, QQ, JJ, TT, 99, 88, AKs, AQs, AJs, AKo, AQo",
                'neutral': "AA, KK, QQ, JJ, TT, 99, AKs, AQs, AKo",
                'tight': "AA, KK, QQ, JJ, AKs, AKo"
            },
            'preflop_call': {
                'loose': "AA-66, AKs-A9s, KQs-KTs, AKo-ATo",
                'neutral': "AA-77, AKs-ATs, KQs, AKo-AJo",
                'tight': "AA-99, AKs-AQs, AKo"
            },
            'flop_continue': 0.6,
        },
        'loose': {
            'preflop_open': {
                'loose': "AA-22, any suited, any broadway, any connector",
                'neutral': "AA-22, AKs-A2s, KQs-K2s, QJs-Q8s, JTs-J8s, T9s-T8s, 98s-97s, 87s, 76s, AKo-A2o, KQo-K9o",
                'tight': "AA-22, AKs-A5s, KQs-K9s, QJs-Q9s, JTs-J9s, AKo-A8o, KQo-KTo"
            },
            'preflop_call': {
                'loose': "AA-22, any suited, any broadway, any connector",
                'neutral': "AA-22, any suited, any broadway",
                'tight': "AA-22, AKs-A2s, KQs-K5s, any broadway"
            },
            'flop_continue': 0.8,
        },
        'aggressive': {
            'preflop_open': {
                'loose': "AA-22, AKs-A2s, KQs-K5s, suited connectors, AKo-A5o, KQo-K9o",
                'neutral': "AA-55, AKs-A7s, KQs-KTs, QJs-QTs, JTs, T9s, 98s, 87s, 76s, AKo-ATo, KQo-KJo",
                'tight': "AA-77, AKs-A9s, KQs-KJs, QJs, JTs, AKo-AJo, KQo"
            },
            'preflop_call': {
                'loose': "AA-22, AKs-A2s, any suited connector, AKo-A5o",
                'neutral': "AA-22, AKs-A2s, suited connectors, AKo-ATo",
                'tight': "AA-44, AKs-A7s, KQs-KTs, suited connectors, AKo-AJo"
            },
            'flop_continue': 0.75,
        },
        'optimal': {
            'preflop_open': {
                'loose': "AA-44, AKs-A7s, KQs-K9s, QJs-Q9s, JTs-J9s, T9s, 98s, 87s, AKo-A9o, KQo-KTo",
                'neutral': "AA-66, AKs-A9s, KQs-KTs, QJs-QTs, JTs, T9s, AKo-AJo, KQo",
                'tight': "AA-88, AKs-ATs, KQs-KJs, QJs, AKo-AQo, KQo"
            },
            'preflop_call': {
                'loose': "AA-22, AKs-A5s, suited connectors, AKo-A9o",
                'neutral': "AA-44, AKs-A8s, suited connectors, AKo-ATo",
                'tight': "AA-66, AKs-ATs, KQs, AKo-AJo"
            },
            'flop_continue': 0.65,
        }
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.final_range_estimates = {}  # For range accuracy tracking
        self.range_mode = 'neutral'  # 'loose', 'neutral', 'tight'
        self.use_visible_cards_only = True  # For equity calculations
        self.fiona_history = {'vpip': 0, 'pfr': 0, 'hands': 0, 'aggression': []}  # Track Fiona's play
        self.hero_history = {'vpip': 0, 'pfr': 0, 'hands': 0, 'aggression': []}  # Track Hero for Fiona


        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 2px solid #444; background: #1a1a1a; }
            QTabBar::tab { background: #333; color: #aaa; padding: 12px 25px; margin-right: 3px; font-size: 18px; font-weight: bold; }
            QTabBar::tab:selected { background: #1a1a1a; color: #fff; }
            QTabBar::tab:hover { background: #444; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top info section - Row 1: Pot, Equity, Odds
        top_info = QHBoxLayout()

        # Pot size display
        self.pot_label = QLabel("Pot: $--")
        self.pot_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        self.pot_label.setStyleSheet("color: #ff0; padding: 8px; background: #222; border: 2px solid #444;")
        top_info.addWidget(self.pot_label)

        # Hero equity display
        self.equity_label = QLabel("Equity: --")
        self.equity_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        self.equity_label.setStyleSheet("color: #0af; padding: 8px; background: #222; border: 2px solid #444;")
        top_info.addWidget(self.equity_label)

        # Pot odds display
        self.pot_odds_label = QLabel("Pot Odds: --")
        self.pot_odds_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        self.pot_odds_label.setStyleSheet("color: #f80; padding: 8px; background: #222; border: 2px solid #444;")
        top_info.addWidget(self.pot_odds_label)

        # Implied odds display
        self.implied_odds_label = QLabel("Implied: --")
        self.implied_odds_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        self.implied_odds_label.setStyleSheet("color: #a8f; padding: 8px; background: #222; border: 2px solid #444;")
        top_info.addWidget(self.implied_odds_label)

        layout.addLayout(top_info)

        # Row 1b: Outs and Scare Cards (for postflop)
        outs_row = QHBoxLayout()

        # Hero outs display
        self.outs_label = QLabel("Outs: --")
        self.outs_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.outs_label.setStyleSheet("color: #0f0; padding: 6px; background: #222; border: 2px solid #444;")
        outs_row.addWidget(self.outs_label)

        # Scare cards display
        self.scare_cards_label = QLabel("Scare Cards: --")
        self.scare_cards_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.scare_cards_label.setStyleSheet("color: #f80; padding: 6px; background: #222; border: 2px solid #444;")
        outs_row.addWidget(self.scare_cards_label)

        outs_row.addStretch()
        layout.addLayout(outs_row)

        # Bar-chart dashboard — glanceable visualisation of the same
        # numbers the text strip above shows, plus SPR, commitment%,
        # outs, reverse-implied risk, and the Nash push gauge when
        # the hero is short-stacked. Capped at ~half the screen width
        # so the tabs below can claim more vertical real estate.
        dash_row = QHBoxLayout()
        dash_row.setContentsMargins(0, 0, 0, 0)
        self.dashboard = MetricDashboard()
        self.dashboard.setMaximumWidth(720)
        dash_row.addWidget(self.dashboard, stretch=0)
        dash_row.addStretch(1)
        layout.addLayout(dash_row)

        # Row 2: Range mode selector and board texture
        mode_row = QHBoxLayout()

        # Range estimation mode
        mode_label = QLabel("Range Estimate:")
        mode_label.setFont(QFont('Arial', 14))
        mode_label.setStyleSheet("color: #aaa;")
        mode_row.addWidget(mode_label)

        from PyQt6.QtWidgets import QButtonGroup, QRadioButton
        self.range_mode_group = QButtonGroup(self)

        self.loose_btn = QRadioButton("Opps weak")
        self.loose_btn.setStyleSheet("color: #8f8; font-size: 16px;")
        self.loose_btn.clicked.connect(lambda: self.set_range_mode('loose'))
        mode_row.addWidget(self.loose_btn)
        self.range_mode_group.addButton(self.loose_btn)

        self.neutral_btn = QRadioButton("Neutral")
        self.neutral_btn.setStyleSheet("color: #fff; font-size: 16px;")
        self.neutral_btn.setChecked(True)
        self.neutral_btn.clicked.connect(lambda: self.set_range_mode('neutral'))
        mode_row.addWidget(self.neutral_btn)
        self.range_mode_group.addButton(self.neutral_btn)

        self.tight_btn = QRadioButton("Opps strong")
        self.tight_btn.setStyleSheet("color: #f88; font-size: 16px;")
        self.tight_btn.clicked.connect(lambda: self.set_range_mode('tight'))
        mode_row.addWidget(self.tight_btn)
        self.range_mode_group.addButton(self.tight_btn)

        mode_row.addStretch()

        # Board texture display.  Bumped from 14pt → 20pt and given the
        # full Acevedo classification (dry/dynamic/wet/paired) + c-bet
        # sizing hint so it doubles as the board-dynamic indicator
        # that used to live in the lower-right status bar.
        self.board_texture_label = QLabel("Board: --")
        self.board_texture_label.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        self.board_texture_label.setStyleSheet(
            "color: #fc0; padding: 8px 14px; background: #222;"
            " border: 1px solid #444; border-radius: 4px;")
        self.board_texture_label.setWordWrap(True)
        mode_row.addWidget(self.board_texture_label, stretch=1)

        layout.addLayout(mode_row)

        # Tabs claim the lion's share of vertical space (~3/4 of the
        # panel height) so the 13x13 PokerStove grid + per-player
        # analysis are fully visible without scrolling.
        self.tabs.setMinimumHeight(600)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
        layout.addWidget(self.tabs, stretch=5)

        self.bot_tabs = {}  # player_name -> TheoryOfMindTab

    def setup_tabs(self, players, network_human_seats=None):
        """Create tabs for all *bot* players plus Advisor strategy tab.

        Network humans (seats listed in ``network_human_seats``) are
        skipped just like the local hero — we don't try to model another
        human's hole-card range with a bot template.  Caller passes the
        host's ``network_human_seats`` set (or omits it for single-player
        mode); the local hero is always seat 0 and is also skipped.
        """
        self.tabs.clear()
        self.bot_tabs = {}
        self.tab_indices = {}  # Map player name to tab index
        self._network_human_seats = set(network_human_seats or ())

        # Advisor Strategy tab (first tab)
        advisor_tab = QWidget()
        advisor_layout = QVBoxLayout(advisor_tab)
        advisor_layout.setContentsMargins(5, 5, 5, 5)

        # Scrollable area for advice
        advisor_scroll = QScrollArea()
        advisor_scroll.setWidgetResizable(True)
        advisor_scroll.setStyleSheet("QScrollArea { border: none; background: #1a2a1a; }")

        self.advisor_advice = QLabel("Deal a hand to see strategic advice")
        self.advisor_advice.setFont(QFont('Arial', 14))
        # Render rich-text so the Gordon advice card can carry per-line
        # colors (action verb green/red/amber, watch warnings yellow).
        self.advisor_advice.setTextFormat(Qt.TextFormat.RichText)
        self.advisor_advice.setStyleSheet(
            "color: #ddd; padding: 14px; background: #121a12;"
            " border: 1px solid #2a4a2a; border-radius: 6px;")
        self.advisor_advice.setWordWrap(True)
        self.advisor_advice.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        advisor_scroll.setWidget(self.advisor_advice)

        advisor_layout.addWidget(advisor_scroll)
        self.tabs.addTab(advisor_tab, "Advisor")

        # Hero tab — hole cards + outs visualisation. Sits right after
        # Advisor so it's the second-most-prominent tab in the bar.
        # update_analysis() routes hero cards + board into it.
        self.hero_tab = HeroOutsTab()
        self.tabs.addTab(self.hero_tab, "Hero")

        # Bot player tabs — skip the local hero and any remote humans.
        for i, player in enumerate(players):
            if player.style == 'human':
                continue
            if i in self._network_human_seats:
                continue
            tab = TheoryOfMindTab(player.name, player.style)
            # Tab shows player's full name (e.g. "Tight Tim")
            idx = self.tabs.addTab(tab, player.name)
            self.bot_tabs[player.name] = tab
            self.tab_indices[player.name] = idx

    def set_range_mode(self, mode):
        """Set the range estimation mode (loose/neutral/tight)."""
        self.range_mode = mode
        # Trigger recalculation using stored callback
        if hasattr(self, 'update_callback') and self.update_callback:
            self.update_callback()

    def set_update_callback(self, callback):
        """Set callback to trigger when range mode changes."""
        self.update_callback = callback

    def get_range_multiplier(self):
        """Get multiplier based on range mode."""
        if self.range_mode == 'loose':
            return 1.25  # Wider ranges = opponents weaker
        elif self.range_mode == 'tight':
            return 0.85  # Narrower ranges = opponents stronger (less aggressive to keep visibility)
        return 1.0  # Neutral

    def _infer_player_read(self, player_name: str,
                            street_actions: dict,
                            board: list, current_street: str) -> str:
        """Build a short human-readable read of how this player has
        bet THIS hand and what outs / made hands could justify that
        line.

        Output looks like:
          BETTING PATTERN: c-bet flop, fired turn → top pair+ or strong draw
          POSSIBLE OUTS: 9 (TS,TH,TD,TC + 5h-2h for FD)
        Returns "" when no actions for this player yet.
        """
        if not street_actions:
            return ""

        # Walk per-street actions and tag what this player did each
        # street. Strings look like "Aggro Angela: Raises to $6",
        # "Aggro Angela: Calls $4", "Aggro Angela: Checks", "...: Folds".
        per_street = {}   # street -> list of {'verb','amount'}
        prefix = f"{player_name}: "
        for street_name, entries in (street_actions or {}).items():
            tagged = []
            for entry in entries:
                if not entry.startswith(prefix):
                    continue
                tail = entry[len(prefix):]
                if tail.startswith("Raises") or tail.startswith("Bets"):
                    tagged.append({'verb': 'r'})
                elif tail.startswith("Calls"):
                    tagged.append({'verb': 'c'})
                elif tail.startswith("Checks"):
                    tagged.append({'verb': 'k'})
                elif tail.startswith("Folds"):
                    tagged.append({'verb': 'f'})
                else:
                    tagged.append({'verb': '?'})
            if tagged:
                per_street[street_name] = tagged

        if not per_street:
            return ""

        pre = per_street.get('Preflop', [])
        flop = per_street.get('Flop', [])
        turn = per_street.get('Turn', [])
        river = per_street.get('River', [])

        def last_verb(stream):
            return stream[-1]['verb'] if stream else None

        any_raise_pre = any(a['verb'] == 'r' for a in pre)
        bet_flop = any(a['verb'] == 'r' for a in flop)
        bet_turn = any(a['verb'] == 'r' for a in turn)
        bet_river = any(a['verb'] == 'r' for a in river)
        # Check-raise on a street = a check, then a raise after others bet.
        def check_raise(stream):
            saw_check = False
            for a in stream:
                if a['verb'] == 'k':
                    saw_check = True
                elif a['verb'] == 'r' and saw_check:
                    return True
            return False
        cr_flop = check_raise(flop)
        cr_turn = check_raise(turn)
        passive_pre = pre and not any_raise_pre

        # Pattern tag — Phil-Gordon-style 1-liner.
        pattern = ""
        verdict = ""
        if bet_flop and bet_turn and bet_river:
            pattern = "Three-street barrel"
            verdict = "Top pair-plus or air with strong story"
        elif any_raise_pre and bet_flop and bet_turn:
            pattern = "Raised PF, c-bet flop, fired turn"
            verdict = "Strong overpair / top pair-good kicker / set"
        elif any_raise_pre and bet_flop and not bet_turn and turn:
            pattern = "Raised PF, c-bet flop, slowed on turn"
            verdict = "AK/AQ miss or weakening one-pair hand"
        elif any_raise_pre and bet_flop and not turn:
            pattern = "Raised PF, c-bet flop"
            verdict = "Standard c-bet — could be anything strong"
        elif cr_turn:
            pattern = "Check-raised turn"
            verdict = "Big hand: set, two-pair, or made straight"
        elif cr_flop:
            pattern = "Check-raised flop"
            verdict = "Set, two-pair, or strong combo draw"
        elif passive_pre and (flop or turn or river) and not any(
                a['verb'] == 'r' for a in flop + turn + river):
            pattern = "Limped pre, called postflop"
            verdict = "Speculative hand that connected; weak pair / draw"
        elif any_raise_pre and not flop and not turn:
            pattern = "Raised preflop only"
            verdict = "Premium pair / big-ace if tight; wide if aggro"
        elif last_verb(flop or turn or river) == 'f':
            pattern = "Folded after some action"
            verdict = "Couldn't continue — missed flop or gave up"
        elif last_verb(flop or turn or river) == 'k':
            pattern = "Showing weakness with checks"
            verdict = "Marginal pair / busted draw"
        else:
            return ""

        lines = [f"BETTING PATTERN: {pattern}",
                 f"LIKELY HOLDING:  {verdict}"]

        # Possible outs annotation — only if we're on flop/turn and the
        # board has at least 3 cards. Picks the standard categories of
        # outs that fit a player with strong betting (flush draw if 2
        # of a suit on board, straight draws around the highest board
        # card, set if board paired).
        if board and 3 <= len(board) <= 4 and current_street != "River":
            outs_lines = self._guess_player_outs(board, pattern)
            if outs_lines:
                lines.append("POSSIBLE OUTS:  " + outs_lines)

        return "\n".join(lines)

    def _guess_player_outs(self, board, pattern):
        """Suggest the kinds of outs an aggressively-betting opponent
        might be drawing to, given the board texture. Coarse and
        heuristic — meant as a thinking aid, not a precise estimate."""
        board_strs = [str(c) for c in board]
        suits = [c[1] for c in board_strs]
        ranks = [c[0] for c in board_strs]
        suit_count = {s: suits.count(s) for s in set(suits)}
        rank_count = {r: ranks.count(r) for r in set(ranks)}
        tags = []
        # Flush draw — 2 of a suit on board, 4 with another of same suit.
        for s, n in suit_count.items():
            if n >= 2:
                tags.append(f"flush draw on {s} (~9 outs if 4-flush)")
                break
        # Open-ended straight — three connected board ranks.
        order = 'A23456789TJQK'  # wheel + broadway
        idx = sorted({order.index(r) for r in ranks if r in order})
        for i in range(len(idx) - 2):
            if idx[i + 2] - idx[i] == 2:
                tags.append("straight draws around connected board")
                break
        # Paired board → trips possible.
        if any(v >= 2 for v in rank_count.values()):
            tags.append("trips on paired board")
        if not tags and pattern.lower().startswith("check-raised"):
            tags.append("set or two-pair (massive hand)")
        return "; ".join(tags) if tags else ""

    def _classify_betting_spike(self, player_name: str,
                                  action_history: list) -> str | None:
        """Detect non-trivial betting patterns from this player.

        Returns one of:
          - 'delayed_turn_raise'  — passive on preflop+flop, raises turn
          - 'delayed_river_raise' — passive earlier, raises river
          - 'three_street_barrel' — bets/raises on flop, turn AND river
          - 'check_raise_flop'    — checks then raises on the same street
          - None                  — no notable spike pattern
        Used by update_analysis() to further collapse the player's
        estimated range toward strong made hands.
        """
        if not action_history:
            return None
        # Walk the history in order, tracking street + per-street actions
        # for this player.
        current_street = 'Preflop'
        per_street: dict = {'Preflop': [], 'Flop': [], 'Turn': [], 'River': []}
        for line in action_history:
            if '--- Flop' in line:
                current_street = 'Flop';   continue
            if '--- Turn' in line:
                current_street = 'Turn';   continue
            if '--- River' in line:
                current_street = 'River';  continue
            if player_name not in line:
                continue
            low = line.lower()
            if 'raise' in low:
                per_street[current_street].append('raise')
            elif 'bet' in low:
                per_street[current_street].append('bet')
            elif 'call' in low:
                per_street[current_street].append('call')
            elif 'check' in low:
                per_street[current_street].append('check')
            elif 'fold' in low:
                per_street[current_street].append('fold')

        # Three-street barrel = bet/raise on flop AND turn AND river.
        def aggressive(actions):
            return any(a in ('bet', 'raise') for a in actions)
        if (aggressive(per_street['Flop'])
                and aggressive(per_street['Turn'])
                and aggressive(per_street['River'])):
            return 'three_street_barrel'

        # Check-raise on the same street — sequence "check" then "raise"
        # in the same street's action list.
        for street in ('Flop', 'Turn', 'River'):
            seq = per_street[street]
            for i in range(len(seq) - 1):
                if seq[i] == 'check' and seq[i + 1] == 'raise':
                    return 'check_raise_flop'

        # Delayed turn raise — passive on preflop and flop, then raises
        # on the turn (no earlier bet/raise from this player).
        pre_flop_passive = not aggressive(
            per_street['Preflop']) and not aggressive(per_street['Flop'])
        if pre_flop_passive and aggressive(per_street['Turn']):
            return 'delayed_turn_raise'

        # Delayed river raise — passive earlier, raises river.
        if (not aggressive(per_street['Preflop'])
                and not aggressive(per_street['Flop'])
                and not aggressive(per_street['Turn'])
                and aggressive(per_street['River'])):
            return 'delayed_river_raise'
        return None

    def analyze_board_texture(self, board):
        """Analyze board texture - wet vs dry."""
        if not board or len(board) < 3:
            return "Preflop", {}

        board_cards = [str(c) for c in board]
        board_ranks = [c[0] for c in board_cards]
        board_suits = [c[1] for c in board_cards]
        ranks = 'AKQJT98765432'

        info = {}

        # Flush draw potential
        suit_counts = {}
        for s in board_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1
        max_suit = max(suit_counts.values())

        if max_suit >= 4:
            info['flush'] = 'FOUR-FLUSH'
        elif max_suit == 3:
            info['flush'] = 'THREE-FLUSH'
        else:
            info['flush'] = 'RAINBOW'

        # Straight potential
        rank_vals = sorted([ranks.index(r) for r in board_ranks])
        spread = rank_vals[-1] - rank_vals[0]

        if spread <= 4:
            info['straight'] = 'CONNECTED'
        elif spread <= 6:
            info['straight'] = 'SEMI-CONNECTED'
        else:
            info['straight'] = 'DISCONNECTED'

        # Paired board
        if len(set(board_ranks)) < len(board_ranks):
            info['paired'] = 'PAIRED'
        else:
            info['paired'] = 'UNPAIRED'

        # High cards
        high_count = sum(1 for r in board_ranks if r in 'AKQJ')
        if high_count >= 2:
            info['high'] = 'BROADWAY'
        elif high_count == 1:
            info['high'] = 'ONE-HIGH'
        else:
            info['high'] = 'LOW'

        # Overall wetness
        wet_score = 0
        if info['flush'] in ['FOUR-FLUSH', 'THREE-FLUSH']:
            wet_score += 2 if info['flush'] == 'FOUR-FLUSH' else 1
        if info['straight'] == 'CONNECTED':
            wet_score += 2
        elif info['straight'] == 'SEMI-CONNECTED':
            wet_score += 1
        if info['paired'] == 'PAIRED':
            wet_score -= 1

        if wet_score >= 3:
            texture = "VERY WET"
        elif wet_score >= 1:
            texture = "WET"
        elif wet_score <= -1:
            texture = "DRY"
        else:
            texture = "NEUTRAL"

        info['texture'] = texture
        return texture, info

    def calculate_outs(self, hero_hand, board):
        """Count outs using the SAME eval7-based logic as
        HeroOutsTab so the strip's "Outs: N" and the Hero tab's grid
        always agree.

        Returns (count, description).  Description is a short label
        derived from the rank gaps so the user still sees "Gutshot",
        "OESD", "Flush draw" etc. as a heuristic — but the COUNT is
        authoritative (eval7-driven, includes double-gutshots and
        pair-to-two-pair improvement).
        """
        if not hero_hand or not board or len(board) < 3:
            return 0, ""
        try:
            import eval7 as _e7
        except Exception:
            return 0, ""

        hero_e7 = [_e7.Card(str(c)) for c in hero_hand[:2]]
        board_e7 = [_e7.Card(str(c)) for c in board]
        try:
            cur_rank = _e7.evaluate(hero_e7 + board_e7)
            cur_class = _e7.handtype(cur_rank)
        except Exception:
            return 0, ""

        # Same hand-class ordering as HeroOutsTab._HAND_CLASS_ORDER.
        order = [
            "Straight Flush", "Quads", "Four of a Kind",
            "Full House", "Flush", "Straight",
            "Trips", "Three of a Kind", "Two Pair", "Pair", "High Card",
        ]

        def _idx(name):
            try:
                return order.index(name)
            except ValueError:
                return len(order)

        cur_idx = _idx(cur_class)
        pair_idx = _idx('Pair')
        high_card_idx = _idx('High Card')

        used = {str(c) for c in hero_hand[:2]}
        used.update(str(c) for c in board)

        hero_ranks_held = {str(c)[0] for c in hero_hand[:2]}
        board_rank_set = {str(c)[0] for c in board}
        rank_order = 'AKQJT98765432'
        board_high_idx = (
            min(rank_order.index(r) for r in board_rank_set)
            if board_rank_set else 0)

        suits = ('s', 'h', 'd', 'c')
        outs = []
        for r in rank_order:
            for s in suits:
                key = r + s
                if key in used:
                    continue
                # Shared-improvement filter — a board-rank card that
                # Hero doesn't hold pairs the board for EVERY player,
                # so it doesn't exclusively help Hero.
                if (r in board_rank_set
                        and r not in hero_ranks_held):
                    continue
                try:
                    new_rank = _e7.evaluate(
                        hero_e7 + board_e7 + [_e7.Card(key)])
                    new_class = _e7.handtype(new_rank)
                except Exception:
                    continue
                new_idx = _idx(new_class)
                # (a) Strict class improvement landing at Pair or better
                if new_idx < cur_idx and new_idx < pair_idx:
                    outs.append(key)
                    continue
                # (b) High Card → top pair (overcard pair)
                if (cur_idx == high_card_idx
                        and new_idx == pair_idx
                        and r in hero_ranks_held
                        and rank_order.index(r) <= board_high_idx):
                    outs.append(key)
                    continue
                # (c) Same class, strictly stronger (e.g. paired-board
                # kicker upgrade)
                if (r in hero_ranks_held
                        and new_idx == cur_idx
                        and new_rank > cur_rank
                        and new_idx <= pair_idx):
                    outs.append(key)

        count = len(outs)

        # Description heuristic — keep the user-facing label informative
        # even though the count comes from eval7. Picks the strongest
        # applicable draw tag.
        descriptions = []
        ranks_only = 'AKQJT98765432'
        all_suits = [str(c)[1] for c in hero_hand[:2]] + \
                    [str(c)[1] for c in board]
        all_ranks = [str(c)[0] for c in hero_hand[:2]] + \
                    [str(c)[0] for c in board]
        suit_counts = {}
        for s in all_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1
        if any(v == 4 for v in suit_counts.values()):
            descriptions.append("Flush draw")
        # Straight detection — count distinct 5-card windows
        # (open-ended vs gutshot vs double-gutshot).
        all_vals = sorted(set(ranks_only.index(r) for r in all_ranks))
        oesd = False
        gutshots = 0
        seen_windows = set()
        for i in range(len(all_vals) - 3):
            window = tuple(all_vals[i:i+4])
            if window in seen_windows:
                continue
            seen_windows.add(window)
            spread = all_vals[i+3] - all_vals[i]
            if spread == 3:
                oesd = True
            elif spread == 4:
                gutshots += 1
        if oesd:
            descriptions.append("OESD")
        elif gutshots >= 2:
            descriptions.append("Double gutshot")
        elif gutshots == 1:
            descriptions.append("Gutshot")
        # Pair / two-pair / trips improvement context — only mention if
        # eval7 found additional outs beyond pure draws.
        cur_pair_or_better = (cur_idx <= pair_idx)
        if cur_pair_or_better and count > 0 and not (oesd or gutshots):
            descriptions.append("pair → 2-pair/trips")

        desc = " + ".join(descriptions) if descriptions else "No draws"
        return count, desc

    def calculate_scare_cards(self, hero_hand, board, opponents):
        """Calculate cards that would be scary (help villain ranges).

        Excludes ranks Hero holds — pairing those is an OUT for Hero,
        not a threat.  Also excludes ranks already paired on the board
        (they make the same full house for everyone, which is mostly
        bad for Hero already factored into the made-hand evaluation).
        """
        if not board or len(board) < 3:
            return []

        board_cards = [str(c) for c in board]
        board_ranks = [c[0] for c in board_cards]
        board_suits = [c[1] for c in board_cards]
        ranks = 'AKQJT98765432'

        # Ranks Hero holds — pairing one of these is an out, not a
        # scare. Without this filter the engine was reporting K and A
        # as "scares" even when Hero held the K as kicker.
        hero_ranks = set()
        if hero_hand and len(hero_hand) >= 2:
            hero_ranks = {str(c)[0] for c in hero_hand[:2]}

        scare_cards = []

        # Count board suits
        suit_counts = {}
        for s in board_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        # Flush completing cards (if 3 or 4 to flush on board)
        for suit, count in suit_counts.items():
            if count >= 3:
                suit_name = {'h': '♥', 's': '♠', 'd': '♦', 'c': '♣'}.get(suit, suit)
                scare_cards.append(f"Any {suit_name} (flush)")
                break

        # Straight completing cards
        board_vals = sorted([ranks.index(r) for r in board_ranks])
        # Check for connected boards where one card completes straight
        for i in range(13):
            test_vals = sorted(board_vals + [i])
            # Check if adding this rank creates a 5-card straight
            for j in range(len(test_vals) - 4):
                if test_vals[j+4] - test_vals[j] == 4:
                    card_rank = ranks[i]
                    if (card_rank not in board_ranks
                            and card_rank not in hero_ranks):
                        scare_cards.append(f"{card_rank} (straight)")
                    break

        # Pairing cards (give two pair/trips). Skip ranks already
        # paired on the board (no extra information from another card
        # of the same rank — counterfeits aside) and ranks Hero holds.
        for r in board_ranks:
            if board_ranks.count(r) == 1 and r not in hero_ranks:
                scare_cards.append(f"{r} (pairs board)")

        # High cards that hit likely villain ranges, but only when
        # Hero doesn't already hold them. A K with K-x is an OUT for
        # Hero, not a scare.
        for r in 'AKQ':
            if r in board_ranks or r in hero_ranks:
                continue
            scare_cards.append(f"{r} (hits broadways)")

        # Remove duplicates and limit
        seen = set()
        unique_scare = []
        for sc in scare_cards:
            if sc not in seen:
                seen.add(sc)
                unique_scare.append(sc)

        return unique_scare[:6]  # Limit to top 6

    def update_fiona_history(self, action, street):
        """Update Fiona's play history for adaptive modeling."""
        self.fiona_history['hands'] += 1
        if 'raise' in action.lower() or 'bet' in action.lower():
            self.fiona_history['aggression'].append(1)
            if street == 'Preflop':
                self.fiona_history['pfr'] += 1
        elif 'call' in action.lower():
            self.fiona_history['aggression'].append(0)
            if street == 'Preflop':
                self.fiona_history['vpip'] += 1
        elif 'fold' in action.lower():
            self.fiona_history['aggression'].append(-1)

    def update_hero_history(self, action, street):
        """Update Hero's play history for Fiona's modeling."""
        self.hero_history['hands'] += 1
        if 'raise' in action.lower() or 'bet' in action.lower():
            self.hero_history['aggression'].append(1)
            if street == 'Preflop':
                self.hero_history['pfr'] += 1
        elif 'call' in action.lower():
            self.hero_history['aggression'].append(0)
            if street == 'Preflop':
                self.hero_history['vpip'] += 1

    def get_fiona_adjusted_range(self):
        """Get Fiona's range adjusted by her observed play."""
        if self.fiona_history['hands'] < 3:
            return None  # Not enough data

        # Calculate aggression factor
        recent = self.fiona_history['aggression'][-10:] if len(self.fiona_history['aggression']) > 10 else self.fiona_history['aggression']
        if recent:
            avg_agg = sum(recent) / len(recent)
            if avg_agg > 0.5:
                return 'aggressive'
            elif avg_agg < -0.3:
                return 'tight'
            else:
                return 'loose'
        return None

    def get_opponent_advice(self, player_style, num_opponents, player_name=None):
        """Get advice for dealing with specific opponent types."""
        advice = []

        if num_opponents == 1:
            advice.append("HEADS-UP STRATEGY:")
            if player_style == 'tight':
                advice.append("vs TIGHT: They only play premium hands. Steal blinds aggressively.")
                advice.append("When they bet big, BELIEVE them - they have it. Fold marginal hands.")
                advice.append("Bluff rarely - tight players call with strong hands only.")
            elif player_style == 'loose':
                advice.append("vs LOOSE: They play too many hands. Value bet relentlessly.")
                advice.append("Don't bluff - they call with anything. Let them hang themselves.")
                advice.append("Your top pair is often good. Bet for value, not protection.")
            elif player_style == 'aggressive':
                advice.append("vs AGGRO: They bet/raise constantly. Trap with strong hands.")
                advice.append("Check-call or check-raise. Let them bluff into you.")
                advice.append("Don't get into raising wars without the nuts.")
            elif player_style == 'tom' and player_name == 'Fluid Fiona':
                fiona_style = self.get_fiona_adjusted_range()
                if fiona_style:
                    advice.append(f"vs FIONA (playing {fiona_style.upper()} this session):")
                    if fiona_style == 'aggressive':
                        advice.append("She's been aggressive - expect more bluffs. Call lighter.")
                    elif fiona_style == 'tight':
                        advice.append("She's been tight - her bets mean strength. Fold more.")
                    else:
                        advice.append("She's been loose - value bet wider. Don't bluff.")
                else:
                    advice.append("vs FIONA: Adaptive player. Watch for patterns.")
            else:
                advice.append("vs BALANCED: Mix your play. Don't be predictable.")

        elif num_opponents == 2:
            advice.append("THREE-WAY STRATEGY:")
            advice.append("Tighten up significantly. One opponent likely has a hand.")
            advice.append("Bluffs work half as often. Need real equity to continue.")

        return "\n".join(advice)

    def parse_range_notation(self, notation):
        """Parse PokerStove notation into a range dictionary."""
        range_dict = {}
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        rank_values = {r: i for i, r in enumerate(ranks)}

        # Helper to add a hand with weight
        def add_hand(hand, weight=1.0):
            range_dict[hand] = weight

        # Helper to add pair range (e.g., "AA-TT")
        def add_pair_range(high, low):
            hi = rank_values.get(high, -1)
            lo = rank_values.get(low, -1)
            if hi >= 0 and lo >= 0:
                for i in range(hi, lo + 1):
                    add_hand(f"{ranks[i]}{ranks[i]}")

        # Parse each part
        parts = notation.replace(' ', '').split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Handle "any suited" or "any broadway"
            if 'anysuited' in part.lower():
                for i, r1 in enumerate(ranks):
                    for j, r2 in enumerate(ranks):
                        if i < j:
                            add_hand(f"{r1}{r2}s", 0.7)
                continue
            if 'anybroadway' in part.lower():
                broadway = ['A', 'K', 'Q', 'J', 'T']
                for i, r1 in enumerate(broadway):
                    for j, r2 in enumerate(broadway):
                        if i < j:
                            add_hand(f"{r1}{r2}s", 0.8)
                            add_hand(f"{r1}{r2}o", 0.6)
                        elif i == j:
                            add_hand(f"{r1}{r2}", 0.9)
                continue
            if 'suitedconnectors' in part.lower() or 'suited connectors' in part.replace(' ', '').lower():
                connectors = [('A', 'K'), ('K', 'Q'), ('Q', 'J'), ('J', 'T'),
                              ('T', '9'), ('9', '8'), ('8', '7'), ('7', '6'), ('6', '5'), ('5', '4')]
                for r1, r2 in connectors:
                    add_hand(f"{r1}{r2}s", 0.8)
                continue

            # Pair range: "AA-TT" or "AA-22" or single "AA"
            if '-' in part and len(part) >= 5 and part[0] == part[1]:
                high = part[0]
                low = part[3]
                add_pair_range(high, low)
                continue

            # Single pair: "AA"
            if len(part) == 2 and part[0] == part[1] and part[0] in ranks:
                add_hand(part)
                continue

            # Suited/offsuit range: "AKs-ATs" or "AKs+"
            if '+' in part:
                base = part.replace('+', '')
                if len(base) == 3 and base[2] in 'so':
                    r1, r2, suit = base[0], base[1], base[2]
                    # Add from r2 up to one below r1
                    start = rank_values.get(r2, -1)
                    end = rank_values.get(r1, -1)
                    if start >= 0 and end >= 0:
                        for i in range(end + 1, start + 1):
                            hand = f"{r1}{ranks[i]}{'s' if suit == 's' else 'o'}"
                            add_hand(hand)
                elif len(base) == 2 and base[0] == base[1]:
                    # Pair+: "TT+" means TT through AA
                    add_pair_range('A', base[0])
                continue

            # Range: "AKs-ATs"
            if '-' in part and len(part) >= 7:
                parts2 = part.split('-')
                if len(parts2) == 2:
                    h1, h2 = parts2
                    if len(h1) == 3 and len(h2) == 3 and h1[0] == h2[0]:
                        r1 = h1[0]
                        start = rank_values.get(h1[1], -1)
                        end = rank_values.get(h2[1], -1)
                        suit = h1[2]
                        if start >= 0 and end >= 0:
                            for i in range(start, end + 1):
                                hand = f"{r1}{ranks[i]}{suit}"
                                add_hand(hand)
                continue

            # Single hand: "AKs" or "AKo" or "AK"
            if len(part) == 3 and part[2] in 'so':
                add_hand(part)
            elif len(part) == 2 and part[0] in ranks and part[1] in ranks:
                # Assume both suited and offsuit
                if part[0] != part[1]:
                    r1, r2 = (part[0], part[1]) if rank_values[part[0]] < rank_values[part[1]] else (part[1], part[0])
                    add_hand(f"{r1}{r2}s", 0.8)
                    add_hand(f"{r1}{r2}o", 0.6)
                else:
                    add_hand(part)

        return range_dict

    # ------------------------------------------------------------------
    # Board-connection scoring
    #
    # When a player CALLS postflop, the natural narrowing question is:
    # which combos in their preflop range actually connect with the
    # board well enough to justify continuing? We score every combo on
    # a 0..1 scale (1 = monster hand, 0 = pure air) and then narrow the
    # preflop range by that score so the grid reflects "what calls make
    # sense given the texture", not just the raw preflop opening range.
    # ------------------------------------------------------------------
    _RANK_VAL = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                 '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

    def _hand_ranks(self, hand_str):
        """Pull the two rank chars + suitedness flag out of a hand label
        like 'AKs'/'TT'/'J9o'. Returns (high_rank, low_rank, suited)."""
        if not hand_str or len(hand_str) < 2:
            return None
        r1, r2 = hand_str[0], hand_str[1]
        suited = (len(hand_str) >= 3 and hand_str[2] == 's')
        if r1 == r2:
            return (r1, r2, False)
        v1 = self._RANK_VAL.get(r1, 0)
        v2 = self._RANK_VAL.get(r2, 0)
        if v1 < v2:
            r1, r2 = r2, r1
        return (r1, r2, suited)

    def _board_connection_score(self, hand_str, board):
        """Return a 0..1 score for how well `hand_str` connects with the
        current board. Approximate; intentionally optimistic on draws so
        the user sees the full "calling-station-with-equity" picture.

        Categories used:
          1.0  — set/quads/full house / overpair (board-aware)
          0.95 — top pair top kicker
          0.85 — top pair / two pair
          0.75 — middle pair / open-ended straight draw / flush draw
          0.55 — bottom pair / gutshot
          0.30 — two overcards (live ace+king vs an under board)
          0.10 — air
        """
        parts = self._hand_ranks(hand_str)
        if parts is None or not board:
            return 0.0
        r1, r2, suited = parts
        v1 = self._RANK_VAL[r1]
        v2 = self._RANK_VAL[r2]
        try:
            board_ranks = []
            board_suits = []
            for c in board:
                cs = str(c)
                board_ranks.append(self._RANK_VAL.get(cs[0], 0))
                board_suits.append(cs[1] if len(cs) > 1 else '')
        except Exception:
            return 0.1
        board_ranks = [b for b in board_ranks if b > 0]
        if not board_ranks:
            return 0.0

        top_board = max(board_ranks)
        is_pair_hand = (r1 == r2)

        # Pair hands: set if matched on board, overpair if all board
        # ranks below, underpair otherwise.
        if is_pair_hand:
            if v1 in board_ranks:
                return 1.0  # Set
            if v1 > top_board:
                return 1.0  # Overpair
            # Underpair — its strength depends on how many overs we
            # face; one over is fine, two or three is weak.
            overs = sum(1 for b in board_ranks if b > v1)
            if overs <= 1:
                return 0.55
            return 0.35

        score = 0.10  # baseline air

        # Pairs with the board.
        if v1 in board_ranks and v2 in board_ranks:
            score = max(score, 0.85)            # two pair
        elif v1 == top_board:
            # Top pair — bump for kicker quality (T+ kicker = top kicker)
            score = max(score, 0.95 if v2 >= 10 else 0.85)
        elif v1 in board_ranks:
            score = max(score, 0.75)            # middle pair (high card on board)
        elif v2 in board_ranks:
            score = max(score, 0.55)            # second-card pair / bottom pair

        # Two big overcards still have outs against an under-Ace board.
        if v1 > top_board and v2 > top_board:
            score = max(score, 0.30)

        # Straight-draw probe: count how many ranks of the 5-card
        # window centred on each possible straight contain a card we
        # hold or that's on the board. Open-ended needs 4-in-a-row
        # using both hole + ≥2 board; gutshot allows one gap.
        all_ranks = set(board_ranks)
        all_ranks.update([v1, v2])
        # Treat ace as both 14 and 1 for the wheel.
        if 14 in all_ranks:
            all_ranks.add(1)
        for low in range(1, 11):
            window = set(range(low, low + 5))
            present = window & all_ranks
            need = window - all_ranks
            # Need exactly the 5 cards for a made straight, or 4 of 5
            # for a one-card draw. We require at least one of our hole
            # cards to be in the window so we don't credit board-only
            # draws.
            uses_hole = (v1 in window) or (v2 in window) or (
                14 in (v1, v2) and 1 in window
            )
            if not uses_hole:
                continue
            if len(present) >= 5:
                score = max(score, 0.95)        # made straight
                break
            if len(present) == 4:
                # Rough open vs gutshot: it's open-ended if either of
                # the two ends of the run is the missing card; we
                # simply check whether the missing card is at the edge
                # of the window's run.
                missing = next(iter(need))
                run_high = max(present)
                run_low = min(present)
                if missing == run_high + 0 or missing == run_low - 0:
                    pass  # endpoint; fall through to OESD/gutshot logic
                # Cheap discriminator: if missing is at one of the two
                # ends, treat as open-ended; otherwise gutshot.
                if missing == low or missing == low + 4:
                    score = max(score, 0.75)    # OESD
                else:
                    score = max(score, 0.55)    # gutshot

        # Suited flush draws: 2 of our suit on the board.
        if suited:
            # Hand suit isn't carried in the hand_str (any suit works
            # for the abstract grid label), so we approximate: if at
            # least 2 board cards share a suit, every suited combo has
            # some flush-draw equity.
            for s in set(board_suits):
                if s and board_suits.count(s) >= 2:
                    score = max(score, 0.75)
                    break

        return min(1.0, score)

    # Reraise ranges — much tighter than opens. The 3-bet column
    # is what most players use for value 3-bets; 4-bet/5-bet collapse
    # to top of value. Loose-mode adds bluff combos at the bottom of
    # the range, tight-mode strips down to monsters only. Used by
    # estimate_range when the action sequence shows the player re-raised
    # preflop.
    _THREE_BET_RANGES = {
        'tight':      {'tight': "AA, KK",
                       'neutral': "AA, KK, QQ, AKs",
                       'loose':   "AA, KK, QQ, JJ, AKs, AKo"},
        'optimal':    {'tight': "AA, KK, QQ",
                       'neutral': "AA, KK, QQ, AKs, AKo",
                       'loose':   "AA, KK, QQ, JJ, AKs, AKo, AQs"},
        'tom':        {'tight': "AA, KK, QQ, AKs",
                       'neutral': "AA, KK, QQ, AKs, AKo",
                       'loose':   "AA, KK, QQ, JJ, AKs, AKo, AQs"},
        'loose':      {'tight': "AA, KK, QQ, JJ",
                       'neutral': "AA, KK, QQ, JJ, AKs, AKo, AQs",
                       'loose':   "AA, KK, QQ, JJ, TT, AKs, AKo, AQs, AQo"},
        'aggressive': {'tight': "AA, KK, QQ, JJ, AKs",
                       'neutral': "AA, KK, QQ, JJ, AKs, AKo, AQs, AQo",
                       'loose':   "AA, KK, QQ, JJ, TT, AKs, AKo, AQs, AQo, AJs, KQs"},
    }
    _FOUR_BET_RANGES = {
        'tight':      "AA, KK",
        'optimal':    "AA, KK, AKs",
        'tom':        "AA, KK, QQ, AKs",
        'loose':      "AA, KK, QQ, AKs",
        'aggressive': "AA, KK, QQ, AKs, AKo",
    }
    _FIVE_BET_PLUS = "AA, KK"

    def estimate_range(self, player, street, actions_this_hand, board, style_override=None):
        """Estimate a player's range based on their style and actions.

        Returns ``(range_dict, notation, explanation, board_hits)``. The
        board_hits dict — same keys as range_dict — carries the 0..1
        connection score per combo so the grid widget can visually call
        out the cards that hit the board.
        """
        style = style_override if style_override else player.style
        style_info = self.STYLE_RANGES.get(style, self.STYLE_RANGES['loose'])

        # Get the range mode (loose/neutral/tight)
        mode = self.range_mode

        # Start with the preflop range. Reraise tags shrink it
        # dramatically — most 3-bets are value (AA/KK/QQ/AK-style) plus
        # an occasional bluff in loose modes. Open raises stay on the
        # full preflop_open range.
        if 'five_bet_plus' in actions_this_hand:
            base_notation = self._FIVE_BET_PLUS
            action_desc = "5-bet+ preflop (premium-only)"
        elif 'four_bet' in actions_this_hand:
            base_notation = self._FOUR_BET_RANGES.get(
                style, self._FOUR_BET_RANGES['optimal'])
            action_desc = "4-bet preflop"
        elif 'three_bet' in actions_this_hand:
            three_bet = self._THREE_BET_RANGES.get(
                style, self._THREE_BET_RANGES['optimal'])
            base_notation = three_bet.get(mode, three_bet.get('neutral', ''))
            action_desc = "3-bet preflop"
        elif 'raised' in actions_this_hand:
            range_dict = style_info['preflop_open']
            base_notation = range_dict.get(mode, range_dict.get('neutral', ''))
            action_desc = "opened/raised preflop"
        else:
            range_dict = style_info['preflop_call']
            base_notation = range_dict.get(mode, range_dict.get('neutral', ''))
            action_desc = "called preflop"

        mode_desc = {'loose': '(assuming weak)', 'neutral': '', 'tight': '(assuming strong)'}

        explanation_parts = [
            f"Player Style: {style.title()}",
            f"Range Mode: {mode.title()} {mode_desc.get(mode, '')}",
            f"Action: {action_desc}",
            f"",
            f"Preflop Range Estimate:",
            f"  {base_notation}",
        ]

        # Narrow range based on postflop actions
        range_multiplier = 1.0
        if street != 'Preflop':
            flop_continue = style_info['flop_continue']

            if 'bet_postflop' in actions_this_hand or 'raised_postflop' in actions_this_hand:
                range_multiplier *= 0.5  # Much narrower if betting
                explanation_parts.append(f"")
                explanation_parts.append(f"Postflop betting narrows range significantly.")
                explanation_parts.append(f"Likely has: top pair+, draws, or bluffs")
            elif 'called_postflop' in actions_this_hand:
                range_multiplier *= flop_continue
                explanation_parts.append(f"")
                explanation_parts.append(f"Called postflop - still wide but connected to board.")

            # Check for board texture hints
            if board:
                board_ranks = [str(c)[0] for c in board]
                board_suits = [str(c)[1] for c in board]

                if board_suits.count(board_suits[0]) >= 3:
                    explanation_parts.append(f"Flush possible - could have suited hands.")
                if any(r in 'AKQJT' for r in board_ranks):
                    explanation_parts.append(f"Broadway on board - broadway hands more likely.")

        # Parse and apply range
        range_dict = self.parse_range_notation(base_notation)

        # Apply multiplier to weights
        if range_multiplier < 1.0:
            for hand in range_dict:
                range_dict[hand] *= range_multiplier

        # Postflop refinement: a call on the flop or turn is much more
        # likely with hands that connect with the board. Score every
        # combo's connection and use it to narrow the preflop range —
        # weight stays high for hands that hit (top pair, set, OESD,
        # flush draw, made straights), drops sharply for pure air.
        # Pre-bet/raise actions stay anchored on the preflop range
        # since "raised postflop" already implies strong connection.
        board_hits: Dict[str, float] = {}
        if street != 'Preflop' and board:
            postflop_call = ('called_postflop' in actions_this_hand
                             and 'raised_postflop' not in actions_this_hand
                             and 'bet_postflop' not in actions_this_hand)
            for hand in list(range_dict.keys()):
                if range_dict[hand] <= 0:
                    continue
                hit = self._board_connection_score(hand, board)
                board_hits[hand] = hit
                if postflop_call:
                    # Floor the multiplier so we don't zero out hands —
                    # a calling station can show up with anything, just
                    # less often. Hands that obviously hit get a bump
                    # so the grid emphasizes them visually.
                    floor = 0.15
                    bump = 1.0 + max(0.0, hit - 0.5)  # 1.0..1.5
                    range_dict[hand] = max(0.0, range_dict[hand]
                                              * max(floor, hit) * bump)
                    range_dict[hand] = min(1.0, range_dict[hand])

            if postflop_call:
                # Build a one-line summary of which board-hitting
                # categories are now amplified, so the explanation
                # reads naturally.
                ranks_on_board = sorted({c for c in board_hits.values()
                                          if c >= 0.6})
                strong_hits = [h for h, s in board_hits.items()
                               if s >= 0.85 and range_dict.get(h, 0) > 0.2]
                draw_hits = [h for h, s in board_hits.items()
                             if 0.55 <= s < 0.85
                             and range_dict.get(h, 0) > 0.2]
                if strong_hits or draw_hits:
                    explanation_parts.append("")
                    explanation_parts.append(
                        "Range narrowed by board connection — combos "
                        "that hit the board are highlighted (yellow)."
                    )
                if strong_hits:
                    explanation_parts.append(
                        "Made hands likely: "
                        + ", ".join(sorted(set(strong_hits))[:8])
                        + ("…" if len(set(strong_hits)) > 8 else "")
                    )
                if draw_hits:
                    explanation_parts.append(
                        "Draws / second pair: "
                        + ", ".join(sorted(set(draw_hits))[:8])
                        + ("…" if len(set(draw_hits)) > 8 else "")
                    )

        return range_dict, base_notation, "\n".join(explanation_parts), board_hits

    def get_range_hands(self, range_dict, threshold=0.3):
        """Convert range dict to list of hand combos for equity calculation."""
        hands = []
        for hand, weight in range_dict.items():
            if weight >= threshold:
                hands.append(hand)
        return hands

    def hand_to_range_notation(self, hand):
        """Convert actual hole cards to PokerStove range notation (e.g., 'AKs', 'TT', 'J9o')."""
        if not hand or len(hand) < 2:
            return None
        c1, c2 = str(hand[0]), str(hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        ranks = 'AKQJT98765432'
        r1_idx = ranks.index(r1)
        r2_idx = ranks.index(r2)
        # Always put higher rank first
        if r1_idx > r2_idx:
            r1, r2 = r2, r1
            s1, s2 = s2, s1
        if r1 == r2:
            return f"{r1}{r2}"  # Pair notation: "AA", "KK"
        elif s1 == s2:
            return f"{r1}{r2}s"  # Suited: "AKs"
        else:
            return f"{r1}{r2}o"  # Offsuit: "AKo"

    def check_range_accuracy(self, players):
        """Check if each player's actual hand was in their estimated range."""
        results = []
        for player in players:
            if player.style == 'human' or not player.hand:
                continue
            if player.name not in self.final_range_estimates:
                continue
            hand_notation = self.hand_to_range_notation(player.hand)
            if not hand_notation:
                continue
            range_dict = self.final_range_estimates[player.name]
            weight = range_dict.get(hand_notation, 0.0)
            in_range = weight >= 0.3  # Threshold for "in range"
            self.range_accuracy_stats['total_hands'] += 1
            if in_range:
                self.range_accuracy_stats['hits'] += 1
                results.append(f"  {player.name}: {hand_notation} IN RANGE (weight={weight:.1%})")
            else:
                self.range_accuracy_stats['misses'] += 1
                results.append(f"  {player.name}: {hand_notation} NOT IN RANGE (weight={weight:.1%})")
        return results

    def update_analysis(self, players, street, board, hero_hand, action_history, pot=None, current_bet=0, hero_bet=0, hero_position='MP', bb_amount=2, street_actions=None):
        """Update all bot tabs with current analysis."""
        all_ranges = {}
        self.hero_position = hero_position  # Store for use in advice

        # Track which players are active for tab highlighting
        active_players = {p.name for p in players if p.active}
        active_opponents = [p for p in players if p.active and p.style != 'human']

        # Update board texture display.  Uses the Acevedo classifier
        # for the headline category (dry/dynamic/wet/paired) and adds a
        # c-bet sizing hint and the older flush/straight detail so the
        # one line tells the user everything they need.
        texture, texture_info = self.analyze_board_texture(board)
        if board and len(board) >= 3:
            try:
                cls = classify_board(board)
                main = cls.get('label', texture).upper()
                cbet = cls.get('cbet', '')
            except Exception:
                main = texture
                cbet = ''
            details = " | ".join(d for d in (
                texture_info.get('flush', ''),
                texture_info.get('straight', '')) if d)
            self.board_texture_label.setText(
                f"Board: {main}" + (f"    [{details}]" if details else "")
                + (f"    →  c-bet: {cbet}" if cbet else ""))
        else:
            self.board_texture_label.setText("Board: Preflop")

        # Refresh the Hero outs tab on every update.  Dead cards =
        # any villain hand we already know about (god-mode reveals,
        # showdown).  Without those, an out we count could already be
        # in someone else's pocket and silently un-drawable. We also
        # pass pot / to_call / hero_stack so the commitment math panel
        # to the right of the hole cards stays in sync. Equity is
        # filled in later via update_commit_panel after the MC run.
        if hasattr(self, 'hero_tab') and self.hero_tab is not None:
            try:
                hero_hand_for_tab = list(hero_hand) if hero_hand else []
                dead = []
                hero_player = None
                for p in players:
                    if (p.style != 'human' and p.active
                            and p.hand and len(p.hand) >= 2):
                        dead.extend(p.hand)
                    if p.style == 'human':
                        hero_player = p
                hero_stack_v = (int(hero_player.stack)
                                if hero_player is not None else None)
                to_call_v = max(0, int(current_bet) - int(hero_bet)) \
                    if (current_bet or hero_bet) else 0
                self.hero_tab.update_outs(
                    hero_hand_for_tab, list(board) if board else [],
                    dead_cards=dead,
                    pot=int(pot) if pot is not None else None,
                    to_call=to_call_v,
                    hero_stack=hero_stack_v,
                )
            except Exception:
                pass

        # Apply range mode multiplier
        range_mult = self.get_range_multiplier()

        # Have we seen ANY voluntary betting action yet this hand? Blinds
        # and "Hero posts" lines don't count. Until at least one player has
        # actually called/raised/checked, the per-bot range grids are blank
        # — there's nothing to infer about anyone's hole cards yet.
        def _is_real_action(line: str) -> bool:
            ll = line.lower()
            if 'posts' in ll or '---' in ll:
                return False
            return any(kw in ll for kw in
                       ('raises', 'calls', 'checks', 'bets', 'folds'))

        any_action_seen = any(_is_real_action(a) for a in action_history)

        for player in players:
            if player.style == 'human':
                continue

            # Track actions for Fiona and Hero history
            for action in action_history:
                if 'Fiona' in action:
                    self.update_fiona_history(action, street)
                if 'Hero' in action:
                    self.update_hero_history(action, street)

            # Determine actions this hand for this player. Walk
            # action_history in order so we can also tag 3-bet / 4-bet —
            # without that, an open and a 3-bet both look like "raised"
            # to the range estimator and Fiona's range stays as wide as
            # her opening range even after she re-raised.
            actions = set()
            current_street_label = 'Preflop'
            preflop_raise_count = 0
            my_first_raise_index = 0  # 1=open, 2=3bet, 3=4bet, …
            for action in action_history:
                # Street markers in the ticker (e.g. "--- Flop ---").
                if '--- Flop' in action:
                    current_street_label = 'Flop'
                    continue
                if '--- Turn' in action:
                    current_street_label = 'Turn'
                    continue
                if '--- River' in action:
                    current_street_label = 'River'
                    continue

                is_preflop_line = (current_street_label == 'Preflop')
                # Count voluntary raises in chronological order so we
                # can label 3-bets and 4-bets per actor.
                if is_preflop_line and ('Raises' in action or 'raises' in action):
                    preflop_raise_count += 1
                    if player.name in action and my_first_raise_index == 0:
                        my_first_raise_index = preflop_raise_count

                if player.name in action:
                    if 'Raises' in action or 'raises' in action:
                        if is_preflop_line:
                            actions.add('raised')
                        else:
                            actions.add('raised_postflop')
                    elif 'Bets' in action or 'bets' in action:
                        actions.add('bet_postflop')
                    elif 'Calls' in action or 'calls' in action:
                        if is_preflop_line:
                            actions.add('called')
                        else:
                            actions.add('called_postflop')

            # Tag 3-bet / 4-bet / 5-bet+ from the preflop raise order so
            # estimate_range can switch to the ultra-tight reraise range
            # (AA/KK/QQ/AK for Fiona, etc.).
            if my_first_raise_index == 2:
                actions.add('three_bet')
            elif my_first_raise_index == 3:
                actions.add('four_bet')
            elif my_first_raise_index >= 4:
                actions.add('five_bet_plus')

            if not actions:
                actions.add('called')  # Default assumption

            # Get range estimate for all players
            # For Fiona, use adaptive range if we have history
            if player.name == 'Fluid Fiona':
                fiona_style = self.get_fiona_adjusted_range()
                if fiona_style:
                    player_style_override = fiona_style
                else:
                    player_style_override = None
            else:
                player_style_override = None

            range_dict, notation, explanation, board_hits = self.estimate_range(
                player, street, actions, board, style_override=player_style_override
            )

            # Apply range mode adjustment (with minimum visibility threshold)
            if range_mult != 1.0:
                for hand in range_dict:
                    if range_dict[hand] > 0:
                        # Apply multiplier but keep minimum visibility for hands in range
                        new_weight = range_dict[hand] * range_mult
                        range_dict[hand] = max(0.25, min(1.0, new_weight))  # Min 25% for visibility

            # Session-calibrated looseness: compare THIS player's actual
            # session VPIP against the nominal VPIP for their declared
            # style. A "tight" bot who's been seeing 60% of flops gets
            # a widened prior; an "aggressive" bot who's folded most
            # of their hands gets a tighter prior. The grid shifts
            # gradually as more samples accumulate, so the first few
            # hands don't whipsaw the display.
            win = getattr(self, '_owner_window', None)
            nominal_vpip = {
                'tight': 0.15, 'optimal': 0.22,
                'aggressive': 0.30, 'loose': 0.45,
            }
            if (win is not None
                    and hasattr(win, '_player_169_history')
                    and player.style != 'human'):
                hist = win._player_169_history.get(player.name, {})
                seen = sum(c.get('seen', 0) for c in hist.values())
                played = sum(c.get('played', 0) for c in hist.values())
                raised = sum(c.get('raised', 0) for c in hist.values())
                # Skip until we have enough samples to be meaningful.
                if seen >= 6:
                    actual_vpip = played / seen
                    nv = nominal_vpip.get(player.style, 0.22)
                    # Damp the ratio so 1 outlier hand doesn't blow up
                    # the display. Equivalent to a Bayesian prior with
                    # ~10 nominal-style observations.
                    smoothed = ((played + nv * 10)
                                / (seen + 10))
                    ratio = smoothed / nv
                    # Apply only when the deviation is sizable.
                    if abs(ratio - 1.0) >= 0.15:
                        for hand in range_dict:
                            w = range_dict[hand]
                            if w > 0:
                                range_dict[hand] = max(0.15,
                                                       min(1.0, w * ratio))
                        actual_pfr = raised / seen if seen else 0
                        explanation += (
                            f"\n\n[Session calibration: "
                            f"VPIP {actual_vpip*100:.0f}% vs nominal "
                            f"{nv*100:.0f}% · PFR {actual_pfr*100:.0f}% "
                            f"· n={seen} → range scale ×{ratio:.2f}]"
                        )

            # Aggression-aware tightening: count raises and bets THIS player
            # has made and squeeze the range toward the top-left (premium
            # hands). Tight bots squeeze HARDER per aggressive action than
            # loose bots; aggressive/optimal sit in the middle.
            raises = sum(1 for a in action_history
                         if player.name in a
                         and ('raises' in a.lower() or 'bets' in a.lower()))
            if raises > 0:
                # Per-style tightening factor per aggressive action.
                # Tighter style → smaller factor → range collapses faster.
                tighten_per_action = {
                    'tight':       0.55,
                    'optimal':     0.65,
                    'tom':         0.7,
                    'loose':       0.8,
                    'aggressive':  0.85,
                }.get(player.style, 0.7)
                # Compounded over each raise; clamp the effect so we don't
                # nuke the entire range (always keep the strongest combos).
                squeeze = max(0.15, tighten_per_action ** raises)
                # Apply squeeze: hands keep `squeeze` fraction of their
                # weight UNLESS they're premium (top-left of grid). The
                # strongest pairs and AKs stay near full weight so the
                # display visibly emphasizes the upper-left corner.
                premium = {'AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo', 'AQs'}
                for hand in list(range_dict.keys()):
                    if range_dict[hand] <= 0:
                        continue
                    if hand in premium:
                        # Lift premiums slightly so the corner is visible.
                        range_dict[hand] = min(1.0, range_dict[hand] * 1.05)
                    else:
                        range_dict[hand] = max(0.0, range_dict[hand] * squeeze)
                explanation += (
                    f"\n\n[Aggression {raises}× → range tightened "
                    f"toward premium combos (squeeze={squeeze:.2f})]"
                )

            # ---- Betting-SPIKE detection (per-street pattern) ----
            # A previously-passive player who suddenly fires big on the
            # turn or river is signalling a much narrower range than the
            # bare raise-count squeeze above implies.  Collapse their
            # range further toward made hands that connect with the
            # board (sets, two pair, straights, flushes, top pair top
            # kicker) — and against villains who BARRELLED preflop +
            # flop, weight toward overpairs and top pair.
            try:
                spike_class = self._classify_betting_spike(
                    player.name, action_history)
            except Exception:
                spike_class = None
            if spike_class:
                # Map spike type → narrowing factor + the "value
                # archetype" to bias toward.
                spike_factor = {
                    'delayed_turn_raise': 0.35,
                    'delayed_river_raise': 0.25,
                    'three_street_barrel': 0.45,
                    'check_raise_flop':    0.40,
                }.get(spike_class, 0.6)
                # Hands that beat one pair: pocket pairs, two-card
                # connectors that hit the board, etc.  This is a coarse
                # template — we keep anything currently > 0 with the
                # squeeze, but boost board-hitting combos so the grid
                # visibly shifts toward "made hand or strong draw".
                hits = board_hits or {}
                for hand in list(range_dict.keys()):
                    w = range_dict[hand]
                    if w <= 0:
                        continue
                    connection = float(hits.get(hand, 0.0))
                    # Squeeze, then add back proportional to how much
                    # this hand hits the texture on the table.
                    new_w = w * spike_factor + connection * 0.6
                    range_dict[hand] = max(0.0, min(1.0, new_w))
                explanation += (
                    f"\n\n[Spike: {spike_class.replace('_', ' ')} → range "
                    f"shifted toward board-connected made hands "
                    f"(factor {spike_factor:.2f})]"
                )

            # Until ANY voluntary action has occurred this hand, blank the
            # grid for every bot — there's no betting evidence yet to
            # narrow the prior.
            if not any_action_seen:
                blank_range = {}
                if player.active:
                    all_ranges[player.name] = blank_range
                self.final_range_estimates[player.name] = blank_range
                if player.name in self.bot_tabs:
                    self.bot_tabs[player.name].update_analysis(
                        blank_range, "(awaiting action)",
                        "Range will populate once betting begins.",
                        board_hits={})
                continue

            if player.active:
                all_ranges[player.name] = range_dict
            else:
                # Keep the range visible but mark as folded in explanation
                explanation = f"[FOLDED]\n\n{explanation}"
                notation = f"[FOLDED] {notation}"

            # Always store final range for accuracy tracking (even folded players)
            self.final_range_estimates[player.name] = range_dict

            # Prepend the betting-pattern READ block so the user sees
            # at a glance what this opponent's actions suggest (c-bet,
            # turn barrel, check-raise, etc.) plus a guess at what
            # outs / made hands could justify that line.
            read_block = self._infer_player_read(
                player.name, street_actions or {}, board, street)
            if read_block:
                explanation = read_block + "\n\n" + explanation

            # Update tab (keep grid visible even for folded players)
            if player.name in self.bot_tabs:
                self.bot_tabs[player.name].update_analysis(
                    range_dict, notation, explanation,
                    board_hits=board_hits,
                )

        # Highlight active player tabs with colored icons
        for player_name, tab_idx in self.tab_indices.items():
            is_active = player_name in active_players
            # Create a colored circle icon
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if is_active:
                painter.setBrush(QBrush(QColor(50, 255, 50)))  # Bright green
                painter.setPen(QPen(QColor(30, 200, 30), 2))
            else:
                painter.setBrush(QBrush(QColor(80, 80, 80)))  # Dark gray
                painter.setPen(QPen(QColor(60, 60, 60), 2))
            painter.drawEllipse(2, 2, 16, 16)
            painter.end()
            self.tabs.setTabIcon(tab_idx, QIcon(pixmap))
            # Also set text color
            if is_active:
                self.tabs.tabBar().setTabTextColor(tab_idx, QColor(100, 255, 100))
            else:
                self.tabs.tabBar().setTabTextColor(tab_idx, QColor(120, 120, 120))

        # Calculate hero equity vs all ranges and get pot info
        if pot is None:
            pot = sum(p.total_invested for p in players)
        active_count = sum(1 for p in players if p.active and p.style != 'human')

        # Update pot display
        self.pot_label.setText(f"Pot: ${pot}")

        # Calculate pot odds
        to_call = max(0, current_bet - hero_bet)
        # Detect the "unraised preflop limp" case: preflop, NO raise
        # has happened, hero just owes the BB to enter. Pot odds give
        # a misleading 30-40%-equity-required signal here because the
        # forced BB inflates the marginal-price ratio. When someone
        # has actually raised (current_bet > BB), pot odds are real.
        unraised_preflop = (
            street == "Preflop"
            and current_bet > 0
            and current_bet <= bb_amount
        )
        if to_call > 0 and pot > 0:
            pot_odds = to_call / (pot + to_call)
            pot_odds_ratio = pot / to_call if to_call > 0 else 0
            if unraised_preflop:
                # Show the number for reference, but tag it as
                # non-binding so the user doesn't read the high
                # required-equity figure as a fold signal.
                self.pot_odds_label.setText(
                    f"Pot Odds: {pot_odds:.1%} "
                    f"(unraised — not a fold signal)")
            else:
                self.pot_odds_label.setText(
                    f"Pot Odds: {pot_odds:.1%} ({pot_odds_ratio:.1f}:1)")
        else:
            pot_odds = 0
            self.pot_odds_label.setText("Pot Odds: --")

        # Calculate implied odds (estimate: average stack of active opponents)
        opp_stacks = [p.stack for p in active_opponents if p.stack > 0]
        avg_opp_stack = sum(opp_stacks) / len(opp_stacks) if opp_stacks else 0
        if to_call > 0 and avg_opp_stack > 0:
            implied_odds = to_call / (pot + to_call + avg_opp_stack * 0.5)  # Assume 50% of stack
            self.implied_odds_label.setText(f"Implied: {implied_odds:.1%} (${int(avg_opp_stack)} behind)")
        else:
            implied_odds = 0
            self.implied_odds_label.setText("Implied: --")

        # Calculate and display outs and scare cards (postflop only)
        if hero_hand and board and len(board) >= 3 and street != "River":
            outs, outs_desc = self.calculate_outs(hero_hand, board)
            if outs > 0:
                # Calculate probability based on street
                if street == "Flop":
                    prob = outs * 4  # Rule of 4 for two cards
                else:  # Turn
                    prob = outs * 2  # Rule of 2 for one card
                self.outs_label.setText(f"Outs: {outs} ({prob}% to hit) - {outs_desc}")
                self.outs_label.setStyleSheet("color: #0f0; padding: 6px; background: #222; border: 2px solid #0a0;")
            else:
                self.outs_label.setText("Outs: Made hand or no draws")
                self.outs_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")

            # Calculate scare cards for villains
            scare_cards = self.calculate_scare_cards(hero_hand, board, active_opponents)
            if scare_cards:
                self.scare_cards_label.setText(f"Scare Cards: {', '.join(scare_cards[:5])}")
                self.scare_cards_label.setStyleSheet("color: #f80; padding: 6px; background: #222; border: 2px solid #a50;")
            else:
                self.scare_cards_label.setText("Scare Cards: None identified")
                self.scare_cards_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")
        elif street == "River":
            self.outs_label.setText("Outs: N/A (River)")
            self.outs_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")
            self.scare_cards_label.setText("Final board - no more cards")
            self.scare_cards_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")
        else:
            self.outs_label.setText("Outs: --")
            self.outs_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")
            self.scare_cards_label.setText("Scare Cards: --")
            self.scare_cards_label.setStyleSheet("color: #888; padding: 6px; background: #222; border: 2px solid #444;")

        if hero_hand:
            # Calculate equity - either vs ranges (realistic) or vs actual hands (learning mode)
            if self.use_visible_cards_only:
                # Realistic mode: calculate against estimated ranges
                hero_equity = self.calculate_equity_vs_ranges(hero_hand, all_ranges, board)
                equity_mode = "vs Ranges"
            else:
                # Learning mode: calculate against actual opponent hands
                opp_hands = [p.hand for p in active_opponents if p.hand]
                if opp_hands:
                    hero_equity = calc_equity_perfect(hero_hand, opp_hands,
                                                       [str(c) for c in board] if board else [],
                                                       iterations=500)
                    equity_mode = "vs Actual"
                else:
                    hero_equity = self.calculate_equity_vs_ranges(hero_hand, all_ranges, board)
                    equity_mode = "vs Ranges"
            self.equity_label.setText(f"Equity ({equity_mode}): {hero_equity:.1%}")
            # Cache so the EV badges on the action buttons can read the
            # SAME range-based number instead of running their own noisy
            # random-opponent Monte Carlo (which over-estimated equity
            # and gave +EV verdicts that contradicted this panel).
            self.last_hero_equity_vs_ranges = float(hero_equity)

            # Feed the equity figure into the Hero tab's commitment
            # panel so its "pot odds vs equity" verdict matches what
            # the equity strip above the tabs is showing.
            try:
                if hasattr(self, 'hero_tab') and self.hero_tab is not None:
                    hero_p = next(
                        (p for p in players if p.style == 'human'), None)
                    self.hero_tab.update_commit_panel(
                        pot=int(pot) if pot is not None else None,
                        to_call=max(0, int(current_bet) - int(hero_bet)),
                        hero_stack=int(hero_p.stack)
                            if hero_p is not None else None,
                        equity_pct=float(hero_equity) * 100.0,
                    )
            except Exception:
                pass

            # Color equity label based on comparison with pot odds.
            # Skip the red-vs-green verdict on an unraised preflop —
            # the comparison would flag almost every limp as "-EV" even
            # though the right call is "fold by hand tier" or "limp /
            # raise for speculation", not "fold because equity < pot
            # odds".
            if unraised_preflop:
                self.equity_label.setStyleSheet(
                    "color: #0af; padding: 8px; background: #222;"
                    " border: 2px solid #444;")
            elif pot_odds > 0:
                if hero_equity > pot_odds:
                    self.equity_label.setStyleSheet("color: #0f0; padding: 8px; background: #222; border: 2px solid #0a0;")  # Green = +EV
                else:
                    self.equity_label.setStyleSheet("color: #f00; padding: 8px; background: #222; border: 2px solid #a00;")  # Red = -EV
            else:
                self.equity_label.setStyleSheet("color: #0af; padding: 8px; background: #222; border: 2px solid #444;")

            # Always compute a guaranteed-no-peek equity figure (vs estimated
            # ranges) so the advice tab shows a pokerStove-style number even
            # when the user has the "learning mode" peek toggle on.
            no_peek_equity = self.calculate_equity_vs_ranges(hero_hand, all_ranges, board)

            # Generate strategy advice with expanded context
            # Build context dictionary with all relevant info
            advice_context = {
                'equity': hero_equity,
                'no_peek_equity': no_peek_equity,
                'pot': pot,
                'pot_odds': pot_odds,
                'to_call': to_call,
                'implied_odds': implied_odds,
                'street': street,
                'num_opponents': active_count,
                'opponents': active_opponents,
                'hero_hand': hero_hand,
                'board': board,
                'texture': texture_info,
                'hero_stack': players[0].stack if players else 200,
                'avg_opp_stack': avg_opp_stack,
                'hero_position': self.hero_position,  # Pass hero's position
                'bb_amount': bb_amount,
                'current_bet': current_bet,
            }

            header = self._build_pot_odds_header(advice_context)
            # Gordon-style compact advice card — the headline action
            # recommendation in ~6 lines. Old verbose advice kept
            # internally but no longer shown by default.
            hand_key_g = (PokerWindow._hand_class(hero_hand)
                          if hero_hand else "??")
            gordon_block = self._build_gordon_advice(
                advice_context, hand_key_g, bb_amount)
            # Wrap pre-formatted text header (it uses \n + box-drawing
            # chars) inside <pre> so the rich-text renderer doesn't
            # collapse the spacing.
            from html import escape as _esc
            header_html = ("<pre style='color:#cccccc; margin:0;"
                           " font-family:monospace; font-size:11pt;'>"
                           f"{_esc(header)}</pre>")
            self.advisor_advice.setText(
                header_html + "<br>" + gordon_block)

            # Update bar-chart dashboard with the just-computed metrics.
            try:
                hero_stack_val = (players[0].stack
                                  if players else 200)
                # SPR + commitment %
                if to_call > 0 and hero_stack_val > 0:
                    pot_after = pot + to_call
                    stack_after = max(0, hero_stack_val - to_call)
                    spr_v = (stack_after / pot_after
                             if pot_after > 0 else 0.0)
                    commit_v = 100.0 * to_call / hero_stack_val
                else:
                    spr_v = (hero_stack_val / pot
                             if pot and pot > 0 else None)
                    commit_v = None
                # Outs (post-flop only)
                outs_v = None
                if hero_hand and board and 3 <= len(board) <= 4:
                    try:
                        # Re-use PokerWindow.calculate_outs() via the
                        # window reference if we can; otherwise fall back
                        # to None.
                        win = getattr(self, '_owner_window', None)
                        if win is not None and hasattr(win, 'calculate_outs'):
                            outs_v, _ = win.calculate_outs(hero_hand, board)
                    except Exception:
                        outs_v = None
                stack_bb_v = (hero_stack_val / bb_amount
                              if bb_amount else None)
                # Reverse-implied risk — heuristic proxy:
                # Hands that are "good now but vulnerable" sit in the
                # mid-equity band (40-65%) AND have a domination risk
                # (low-kicker ace, weak top pair on Broadway, non-nut
                # flush draw). Approximate as
                #   (1 - equity) * 35%  capped at 30%,
                # bumped slightly on monotone / connected boards.
                ri_pct = None
                if hero_hand and board:
                    eq_now = hero_equity
                    if 0.35 <= eq_now <= 0.70:
                        base = (1 - eq_now) * 35.0
                        # Texture amplifier — wet boards punish 2nd-best more
                        try:
                            ranks = [str(c)[0] for c in board]
                            suits = [str(c)[1] for c in board]
                            paired = len(set(ranks)) < len(ranks)
                            mono = len(set(suits)) == 1
                            two_tone = (len(set(suits)) == 2
                                        and max(suits.count(s)
                                                for s in set(suits)) >= 2)
                            base += (5.0 if mono else
                                     3.0 if two_tone else
                                     2.0 if paired else 0.0)
                        except Exception:
                            pass
                        ri_pct = min(30.0, max(0.0, base))
                    else:
                        ri_pct = 0.0

                self.dashboard.update_metrics(
                    equity_pct=hero_equity * 100.0,
                    pot_odds_pct=pot_odds * 100.0 if pot_odds else None,
                    implied_pct=(implied_odds * 100.0
                                 if implied_odds else None),
                    spr=spr_v,
                    commit_pct=commit_v,
                    outs=outs_v,
                    stack_bb=stack_bb_v,
                    hero_hand=hero_hand,
                    unraised_preflop=unraised_preflop,
                    reverse_implied_pct=ri_pct,
                )
            except Exception:
                pass
        else:
            self.equity_label.setText("Hero Equity vs Ranges: --")
            self.equity_label.setStyleSheet("color: #0af; padding: 8px; background: #222; border: 2px solid #444;")
            self.advisor_advice.setText("Deal a hand to see strategic advice")

    def get_strategy_advice(self, equity, pot, street, num_opponents, hero_hand, board, texture_info=None, hero_position=None):
        """Generate comprehensive, context-sensitive strategic advice."""
        if not hero_hand or len(hero_hand) < 2:
            return "Deal cards to receive strategic advice."

        c1, c2 = str(hero_hand[0]), str(hero_hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        is_suited = s1 == s2
        is_pair = r1 == r2
        ranks = 'AKQJT98765432'
        r1_val = ranks.index(r1)
        r2_val = ranks.index(r2)
        high_val = min(r1_val, r2_val)
        low_val = max(r1_val, r2_val)
        high_rank = ranks[high_val]
        low_rank = ranks[low_val]
        gap = low_val - high_val
        is_connected = gap == 1

        # Hand notation
        if is_pair:
            hand_str = f"{r1}{r2}"
        elif is_suited:
            hand_str = f"{high_rank}{low_rank}s"
        else:
            hand_str = f"{high_rank}{low_rank}o"

        lines = []

        # === PREFLOP ADVICE ===
        if street == "Preflop":
            # Comprehensive hand classification with specific advice
            if is_pair:
                if high_val <= 1:  # AA, KK
                    lines.append(f"[{hand_str}] TIER 1 - PREMIUM PAIR")
                    lines.append("Action: Raise 3-4x BB. Re-raise all-in vs 3-bet.")
                    if r1 == 'A':
                        lines.append("AA: 85% vs random. Slow-play occasionally vs aggressive.")
                    else:
                        lines.append("KK: 82% vs random. Watch for aces on flop.")
                elif high_val <= 3:  # QQ, JJ
                    lines.append(f"[{hand_str}] TIER 1 - PREMIUM PAIR")
                    lines.append("Action: Raise any position. Call 3-bets, fold to 4-bet shoves from tight players.")
                    lines.append("These overpairs are strong but vulnerable to A/K on board.")
                elif high_val <= 5:  # TT, 99
                    lines.append(f"[{hand_str}] TIER 2 - STRONG PAIR")
                    lines.append("Action: Raise in position, call raises for set value.")
                    lines.append("Set mining math: 12% flop set = need 8:1 implied odds.")
                elif high_val <= 8:  # 88, 77, 66
                    lines.append(f"[{hand_str}] TIER 3 - MEDIUM PAIR")
                    lines.append("Action: Raise if folded to, otherwise set-mine.")
                    lines.append("Rarely win unimproved multiway. Need to hit set.")
                else:  # 55-22
                    lines.append(f"[{hand_str}] TIER 4 - SMALL PAIR")
                    lines.append("Action: Call for set value only. Need 15:1 implied odds.")
                    lines.append("Fold to raises unless very deep (20x+ effective stacks).")

            elif high_rank == 'A':
                if low_rank == 'K':
                    lines.append(f"[{hand_str}] TIER 1 - BIG SLICK")
                    lines.append("Action: Raise/3-bet from any position.")
                    lines.append("Best unpaired hand. Still just ace-high until it connects!")
                    if is_suited:
                        lines.append("Suited: Nut flush potential adds ~3% equity.")
                elif low_rank in 'QJ':
                    lines.append(f"[{hand_str}] TIER 2 - STRONG BROADWAY")
                    lines.append("Action: Raise. Call 3-bets in position." if is_suited else "Action: Raise. Fold to 3-bets from tight players.")
                    lines.append("Beware domination by AK. Top pair often outkicked.")
                elif low_rank == 'T':
                    lines.append(f"[{hand_str}] TIER 3 - BROADWAY" if is_suited else f"[{hand_str}] TIER 4 - MARGINAL ACE")
                    lines.append("Action: Raise in position." if is_suited else "Action: Open late position only.")
                    lines.append("AT dominated by AJ/AQ/AK. Proceed with caution.")
                elif is_suited and low_val >= 9:  # A5s-A2s
                    lines.append(f"[{hand_str}] TIER 3 - WHEEL ACE SUITED")
                    lines.append("Action: Good 3-bet bluff hand. Call for implied odds.")
                    lines.append("Wheel straight potential (A-2-3-4-5) + nut flush.")
                elif is_suited:  # A9s-A6s
                    lines.append(f"[{hand_str}] TIER 4 - SUITED ACE")
                    lines.append("Action: Call in position for flush potential.")
                    lines.append("Need to make flush to win big pots.")
                else:  # Axo
                    if low_val <= 6:
                        lines.append(f"[{hand_str}] TIER 5 - TROUBLE HAND")
                        lines.append("Action: Open button only. Fold to aggression.")
                    else:
                        lines.append(f"[{hand_str}] FOLD - ACE RAG")
                        lines.append("Action: Not profitable. Wait for better.")
                    lines.append("'Ace-rag offsuit loses more money than any other hand type.'")

            elif high_rank == 'K':
                if low_rank == 'Q':
                    lines.append(f"[{hand_str}] TIER 2 - ROYAL DRAW" if is_suited else f"[{hand_str}] TIER 3 - TRAP HAND")
                    lines.append("Action: Raise first-in. Fold to 3-bets from tight players.")
                    lines.append("KQ often dominated by AK/AQ. Looks better than it plays.")
                elif low_rank in 'JT':
                    lines.append(f"[{hand_str}] TIER 3 - SUITED BROADWAY" if is_suited else f"[{hand_str}] TIER 4 - BROADWAY")
                    lines.append("Action: Raise in position. Good multiway hand if suited.")
                elif is_suited:
                    lines.append(f"[{hand_str}] TIER 5 - SUITED KING")
                    lines.append("Action: Play from button/BB only. Flush potential.")
                else:
                    lines.append(f"[{hand_str}] FOLD - KING RAG")
                    lines.append("Action: Not profitable long-term.")

            elif high_rank in 'QJ' and low_rank in 'JT9':
                lines.append(f"[{hand_str}] TIER 3 - BROADWAY CONNECTOR" if is_suited else f"[{hand_str}] TIER 4 - BROADWAY")
                lines.append("Action: Raise in position. Good for straights/flushes.")
                lines.append("These hands flop well but often make second-best.")

            elif is_suited and gap <= 2 and high_val >= 4:  # Suited connectors T9s-54s
                lines.append(f"[{hand_str}] TIER 3 - SUITED CONNECTOR")
                lines.append("Action: Call with deep stacks. Best multiway.")
                lines.append(f"Need 15-20x implied odds. {'Connected: straights both ways.' if gap == 1 else 'One-gapper: fewer straights.'}")

            elif is_suited and gap <= 3:
                lines.append(f"[{hand_str}] TIER 5 - SUITED GAPPER")
                lines.append("Action: Button/BB only with deep stacks.")

            elif is_suited:
                lines.append(f"[{hand_str}] TIER 5 - WEAK SUITED")
                lines.append("Action: Defend BB cheaply. Rarely open.")

            else:
                lines.append(f"[{hand_str}] FOLD")
                lines.append("Action: Not playable. Patience = profit.")
                lines.append("'The money you save is worth as much as the money you win.'")

        # === POSTFLOP ADVICE ===
        else:
            board_cards = [str(c) for c in board] if board else []
            board_ranks = [bc[0] for bc in board_cards]
            board_suits = [bc[1] for bc in board_cards]

            # Made hand detection
            has_pair_r1 = r1 in board_ranks
            has_pair_r2 = r2 in board_ranks
            has_overpair = is_pair and all(ranks.index(r1) < ranks.index(br) for br in board_ranks) if board_ranks else False
            top_board_rank = board_ranks[0] if board_ranks else None
            has_top_pair = (r1 == top_board_rank or r2 == top_board_rank) if top_board_rank else False

            # Count suits for flush detection
            all_suits = [s1, s2] + board_suits
            suit_counts = {}
            for s in all_suits:
                suit_counts[s] = suit_counts.get(s, 0) + 1
            max_suit_count = max(suit_counts.values()) if suit_counts else 0
            hero_flush_suit = s1 if suit_counts.get(s1, 0) >= 4 else (s2 if suit_counts.get(s2, 0) >= 4 else None)
            has_flush = max_suit_count >= 5 and hero_flush_suit
            has_flush_draw = max_suit_count == 4 and hero_flush_suit

            # Board texture
            board_paired = len(board_ranks) != len(set(board_ranks))
            monotone = len(set(board_suits)) == 1 if len(board_suits) >= 3 else False

            lines.append(f"[{hand_str}] on {' '.join(board_cards)}")

            # Specific made hand advice
            if has_flush:
                lines.append("MADE FLUSH - Strong! Bet for value.")
                if high_rank == 'A' and s1 == hero_flush_suit:
                    lines.append("Nut flush - can bet big/raise for stacks.")
                else:
                    lines.append("Watch for higher flushes on paired/4-flush boards.")
            elif is_pair and (r1 in board_ranks):
                lines.append("SET - Monster! Build the pot aggressively.")
                lines.append("Don't slowplay wet boards. Get money in now.")
            elif has_overpair:
                lines.append("OVERPAIR - Strong on dry boards.")
                lines.append(f"Your {hand_str} beats all unpaired hands. Value bet 50-66% pot.")
            elif has_top_pair:
                kicker = high_rank if (r1 == top_board_rank) else low_rank
                kicker_val = ranks.index(kicker) if kicker != top_board_rank else low_val
                if kicker_val <= 2:  # A or K kicker
                    lines.append("TOP PAIR TOP KICKER - Strong value hand.")
                    lines.append("Bet for value. Raise for protection on wet boards.")
                elif kicker_val <= 5:  # Q, J, T kicker
                    lines.append("TOP PAIR GOOD KICKER - Solid hand.")
                    lines.append("Value bet but control pot vs aggression.")
                else:
                    lines.append("TOP PAIR WEAK KICKER - Vulnerable.")
                    lines.append("Bet small for value/protection. Fold to big raises.")
            elif has_pair_r1 or has_pair_r2:
                lines.append("MIDDLE/BOTTOM PAIR - Marginal showdown.")
                lines.append("Check-call small bets. Fold to significant aggression.")
            elif has_flush_draw:
                outs = 9
                if street == "Flop":
                    pct = outs * 4
                    lines.append(f"FLUSH DRAW - {outs} outs = ~{pct}% to river")
                    lines.append("Rule of 4: Need ~2:1 pot odds. Semi-bluff or check-call.")
                else:  # Turn
                    pct = outs * 2
                    lines.append(f"FLUSH DRAW - {outs} outs = ~{pct}% to river")
                    lines.append("Rule of 2: Need ~4:1 pot odds. Often fold without odds.")
            else:
                lines.append("NO MADE HAND")
                if equity > 0.35:
                    lines.append("Some equity present. Semi-bluff or check-call.")
                else:
                    lines.append("Weak holding. Check-fold without a good bluff story.")

            # Equity-based guidance
            lines.append("")
            if equity > 0.70:
                lines.append(f"EQUITY {equity:.0%}: VALUE HARD")
                lines.append("Bet 66-100% pot. Look for check-raise spots.")
            elif equity > 0.50:
                lines.append(f"EQUITY {equity:.0%}: VALUE BET")
                lines.append("Bet 50-66% pot for value + protection.")
            elif equity > 0.35:
                lines.append(f"EQUITY {equity:.0%}: POT CONTROL")
                lines.append("Small bets or check-call. Don't bloat the pot.")
            elif equity > 0.20:
                lines.append(f"EQUITY {equity:.0%}: DRAWING/MARGINAL")
                lines.append("Need pot odds to continue. Check-call or fold.")
            else:
                lines.append(f"EQUITY {equity:.0%}: GIVE UP")
                lines.append("Check-fold. Only bluff with a believable story.")

            # Board texture warnings
            if monotone and not has_flush and not has_flush_draw:
                lines.append("WARNING: Monotone board - someone likely has flush!")
            if board_paired:
                lines.append("CAUTION: Paired board - full houses possible.")

        return "\n".join(lines)

    def _build_pot_odds_header(self, ctx):
        """Render the always-visible pot-odds + no-peek equity block that
        sits at the top of the Advisor tab text. The equity here is the
        pokerStove-style number computed against the estimated range of
        every active opponent — never against their actual hole cards —
        so it stays accurate even if the user has Learning Mode enabled.
        """
        pot = ctx.get('pot', 0) or 0
        to_call = ctx.get('to_call', 0) or 0
        pot_odds = ctx.get('pot_odds', 0) or 0
        no_peek = ctx.get('no_peek_equity', None)
        num_opps = ctx.get('num_opponents', 0) or 0
        street = ctx.get('street', 'Preflop')

        # Unraised preflop = pot is just blinds, hero owes only the BB
        # to enter. The naive equity-vs-pot-odds verdict gives bad
        # advice here (it flags almost every limpable hand as -EV
        # because 4-way equity is < 40%). Suppress that verdict and
        # tell the reader to use hand-tier instead. Once anyone has
        # raised above the BB, this is a real fold/call decision and
        # pot odds DO apply.
        is_preflop = street == "Preflop"
        bb_amount = ctx.get('bb_amount', 2) or 2
        current_bet_ctx = ctx.get('current_bet', 0) or 0
        unraised_preflop = (
            is_preflop and to_call > 0
            and current_bet_ctx <= bb_amount
        )

        lines = ["═══ POT ODDS & EQUITY ═══"]

        if to_call > 0:
            ratio = (pot / to_call) if to_call > 0 else 0
            if unraised_preflop:
                lines.append(
                    f"Pot ${pot}  |  To call ${to_call} (BB to enter)  |  "
                    "no real raise — pot odds don't drive the decision"
                )
            else:
                lines.append(
                    f"Pot ${pot}  |  To call ${to_call}  |  "
                    f"Pot odds {ratio:.1f}:1 (need {pot_odds*100:.1f}% equity)"
                )
        elif pot > 0:
            lines.append(f"Pot ${pot}  |  No bet to call right now")
        else:
            lines.append("No pot yet")

        if no_peek is not None:
            opp_label = f"vs {num_opps} opp range" + ("s" if num_opps != 1 else "")
            line = f"Hand equity ({opp_label}, {street}): {no_peek*100:.1f}%"
            if unraised_preflop:
                line += ("   →   decide by HAND TIER + POSITION "
                         "(no raise to fold to)")
            elif to_call > 0:
                margin = (no_peek - pot_odds) * 100
                if margin >= 0:
                    line += f"   →   +{margin:.1f}% over pot odds (+EV call)"
                else:
                    line += f"   →   {margin:.1f}% under pot odds (-EV call)"
            lines.append(line)
            lines.append("(No-peek: computed vs estimated ranges, never actual cards.)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Gordon-style compact advice (Phil Gordon's Little Green Book).
    # Every action runs through his two-question script:
    #   1. Should I bet/raise?   (asked FIRST — aggressive poker wins)
    #   2. Should I check/fold?  (asked SECOND)
    #   3. Otherwise → call / check
    # The output is at most ~6 lines so it can sit in a small panel
    # alongside the bar dashboard.
    # ------------------------------------------------------------------

    _GORDON_TIER = {
        # Tier 1 = premium (always playable); 5 = trash. Used to drive
        # the BET/RAISE decision branch.  Indexed by 169-grid hand key
        # ("AA", "AKs", "72o", …).  Anything not in the dict falls
        # through to tier 6 (fold from anywhere).
        # Tier 1 — premium
        **{k: 1 for k in (
            "AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs")},
        # Tier 2 — strong
        **{k: 2 for k in (
            "TT", "99", "AQo", "AJs", "KQs", "AJo", "KQo")},
        # Tier 3 — playable in position / against weak fields
        **{k: 3 for k in (
            "88", "77", "66", "ATs", "KJs", "QJs", "JTs",
            "KTs", "QTs", "T9s", "98s", "87s", "76s",
            "ATo", "KJo", "QJo", "JTo")},
        # Tier 4 — speculative; multi-way only or late-position steals
        **{k: 4 for k in (
            "55", "44", "33", "22", "A9s", "A8s", "A7s",
            "A6s", "A5s", "A4s", "A3s", "A2s",
            "K9s", "Q9s", "J9s", "T8s", "97s", "86s", "75s",
            "65s", "54s",
            "KTo", "QTo", "T9o", "98o")},
    }

    @classmethod
    def _gordon_tier(cls, hand_key: str) -> int:
        return cls._GORDON_TIER.get(hand_key, 6)

    # Famous-hand nicknames Gordon uses throughout the Little Green
    # Book. Anything not listed here falls through to a generic
    # algorithmic label ("suited connector", "wheel ace", ...).
    _GORDON_NICKNAMES = {
        "AA":  "American Airlines / Pocket Rockets",
        "KK":  "Cowboys / King Kong",
        "QQ":  "Ladies / Hilton Sisters",
        "JJ":  "Fishhooks / Jacks",
        "TT":  "Dimes / TNT",
        "99":  "German Virgin",      # 9-9, "nein-nein"
        "88":  "Snowmen",
        "77":  "Hockey Sticks / Sunset Strip",
        "66":  "Route 66",
        "55":  "Speed Limit / Presto",
        "44":  "Sailboats / Magnum",
        "33":  "Crabs",
        "22":  "Ducks / Deuces",
        "AKs": "Big Slick (suited) — Anna Kournikova",
        "AKo": "Big Slick (offsuit) — Anna Kournikova",
        "AQs": "Big Chick / Little Slick (suited)",
        "AQo": "Big Chick / Little Slick (offsuit)",
        "AJs": "AJ (suited) — Ajax",
        "AJo": "Ajax (offsuit)",
        "KQs": "Royal Couple (suited)",
        "KQo": "Royal Couple (offsuit)",
        "KJs": "Kojak (suited)",
        "KJo": "Kojak (offsuit)",
        "QJs": "Queen-Jack (suited)",
        "JTs": "Tequila Jacks / Justin Timberlake (suited)",
        "T9s": "T-Niner (suited)",
        "98s": "Oldsmobile (suited)",
        "76s": "Trombones (suited)",
        "65s": "Mike Sexton",
        "54s": "Colt 45 / Jesse James (suited)",
        "72o": "The Hammer — worst hand in poker",
        "K9o": "Canine",
        "Q3o": "Gay Waiter / San Francisco Busboy",
        "T2o": "Doyle Brunson",
        "J5o": "Jackson Five / Motown",
    }

    @classmethod
    def _gordon_combo_description(cls, hand_key: str) -> str:
        """Return a one-line, Gordon-flavored description of a 169-grid
        hand key. Algorithmically generated for any input.

        Format is roughly:
          "<NICKNAME> — <ACTION HINT>; <CAVEAT>"
        E.g. "AKs — Big Slick suited; premium, open from any seat. Best
        unpaired hand."
        """
        if not hand_key or hand_key == "??":
            return ""
        # Parse the key.
        order = 'AKQJT98765432'
        r1 = hand_key[0]
        if len(hand_key) == 2:                  # pair like "AA"
            r2 = r1
            suited = False
            is_pair = True
        else:                                    # "AKs" / "72o"
            r2 = hand_key[1]
            suited = hand_key[-1].lower() == 's'
            is_pair = False
        i1 = order.index(r1)
        i2 = order.index(r2)
        gap = abs(i1 - i2)
        high = min(i1, i2)  # lower index = higher rank in AKQJT…

        nickname = cls._GORDON_NICKNAMES.get(hand_key, "")

        # ----- Action hint by structure -----
        if is_pair:
            if high <= 1:           # AA, KK
                hint = ("premium — raise / 3-bet always. "
                        "Don't go broke pre vs the 4th raise (AA only).")
            elif high <= 3:         # QQ, JJ
                hint = ("premium pair — open / 3-bet always; "
                        "fold to a tight player's 4-bet shove.")
            elif high <= 5:         # TT, 99
                hint = ("strong pair — open / 3-bet; set-mine if 4-bet. "
                        "Need 8:1 implied (12% set flop).")
            elif high <= 8:         # 88-66
                hint = ("medium pair — raise if folded to, otherwise "
                        "set-mine. Lose unimproved multi-way.")
            else:                   # 55-22
                hint = ("small pair — call cheap for set value. "
                        "Need 15:1 implied; fold to raises.")
        elif r1 == 'A' or r2 == 'A':
            other = r2 if r1 == 'A' else r1
            other_i = order.index(other)
            if other == 'K':
                hint = ("Big Slick — best unpaired. Raise / 3-bet any "
                        "seat. Ace-high until it connects.")
            elif other in 'QJ':
                hint = (("strong broadway (suited) — open / "
                         "call 3-bets in position." if suited else
                         "broadway offsuit — open, fold to 3-bets "
                         "from tight players. Watch for AK domination."))
            elif other == 'T':
                hint = (("suited Broadway — open / call in position."
                         if suited else
                         "marginal ace — open late position only. "
                         "Dominated by AJ/AQ/AK."))
            elif suited and other_i >= 9:        # A5s-A2s
                hint = ("wheel ace suited — nut-flush + A-5 straight "
                        "potential. Great 3-bet bluff hand.")
            elif suited:                          # A9s-A6s
                hint = ("suited ace — flush-only equity; call in "
                        "position with implied odds.")
            else:                                 # offsuit ace
                if other_i <= 6:
                    hint = ("trouble ace offsuit — open button only, "
                            "fold to aggression.")
                else:
                    hint = ("ace-rag offsuit — Gordon: 'loses more "
                            "money than any other hand type'. Fold.")
        elif r1 == 'K' or r2 == 'K':
            other = r2 if r1 == 'K' else r1
            other_i = order.index(other)
            if other == 'Q':
                hint = (("Royal draw (suited)." if suited else
                         "KQ offsuit — trap hand; often dominated "
                         "by AK/AQ. Looks better than it plays."))
            elif other in 'JT':
                hint = (("suited broadway — raise in position; "
                         "strong multi-way." if suited else
                         "broadway offsuit — raise in position only."))
            elif suited and other_i <= 9:
                hint = ("suited king — button / BB only. Flush "
                        "potential, vulnerable kicker.")
            else:
                hint = ("king-rag — not profitable long-term. Fold.")
        elif r1 in 'QJ' and r2 in 'QJT9':
            hint = (("Broadway connector (suited) — open in position; "
                     "flops well into straights / flushes." if suited else
                     "broadway offsuit — open in position. Often "
                     "makes second-best top pair."))
        elif suited and gap == 1 and high >= 4:   # T9s..54s
            hint = ("suited connector — best multi-way speculator. "
                    "Need 15-20x implied odds; deep stacks only.")
        elif suited and gap == 2 and high >= 4:   # T8s..64s
            hint = ("suited one-gapper — speculative; late position "
                    "with depth, otherwise fold.")
        elif suited and gap == 3:
            hint = ("suited two-gapper — button / BB only. Marginal.")
        elif suited:
            hint = ("weak suited — defend BB cheaply, rarely open. "
                    "Flush potential is the only redemption.")
        elif gap == 1 and high <= 4:              # KQo-T9o etc handled above; covers low connectors offsuit
            hint = ("connected offsuit — speculative; rarely open. "
                    "Better hands offsuit lose more than they win.")
        else:
            hint = ("trash — fold. Patience = profit. Gordon: 'The "
                    "money you save is worth as much as the money "
                    "you win.'")

        if nickname:
            return f"{nickname} — {hint}"
        return f"{hand_key} — {hint}"

    def _build_gordon_advice(self, ctx, hand_key: str,
                              bb_amount: float) -> str:
        """Return a compact (~6 line) Gordon-style action card.

        Lines:
          Q1 / Q2 — the two-question script outcome
          ACTION   — the recommended primary action, color-tagged
          SIZING   — Gordon's position-based open-raise sizes
          WATCH    — one-line context warning ("4th raise=aces",
                     "board paired = first to bet wins", etc.)
        """
        hand_str = hand_key
        position = (ctx.get('hero_position') or 'MP').upper()
        street = ctx.get('street', 'Preflop')
        to_call = ctx.get('to_call', 0) or 0
        pot = ctx.get('pot', 0) or 0
        equity = ctx.get('equity', 0) or 0       # fraction 0..1
        pot_odds = ctx.get('pot_odds', 0) or 0   # fraction
        current_bet = ctx.get('current_bet', 0) or 0
        num_opps = ctx.get('num_opponents', 0) or 0
        tier = self._gordon_tier(hand_key)
        hero_stack = ctx.get('hero_stack', 200) or 200
        stack_bb = (hero_stack / bb_amount) if bb_amount else 50
        unraised = (street == "Preflop" and current_bet > 0
                    and current_bet <= bb_amount)

        # ------- Decision (Gordon's two-question script) -------
        bet_raise = False
        check_fold = False
        action_line = ""
        why_line = ""

        if street == 'Preflop':
            n_raises = max(0, int((current_bet / max(bb_amount, 1)) - 1))
            first_in = (to_call <= bb_amount and current_bet <= bb_amount)
            facing_raise = (current_bet > bb_amount)
            # Short-stack push/fold takes over below 15 BB
            if stack_bb <= 15:
                pct = hand_strength_percentile(ctx.get('hero_hand') or [])
                push_band = nash_push_pct(stack_bb)
                if pct >= (1 - push_band):
                    bet_raise = True
                    action_line = (f"PUSH ALL-IN  (Nash @ {stack_bb:.0f}bb: "
                                   f"top {push_band*100:.0f}%)")
                    why_line = "Folding equity + ICM beats blinding out."
                else:
                    check_fold = True
                    action_line = "FOLD  (outside Nash push range)"
                    why_line = "Conserve chips for a better spot."
            elif facing_raise and n_raises >= 3:
                # Gordon: the 4th raise (3rd re-raise) means aces.
                if tier == 1 and hand_key == "AA":
                    bet_raise = True
                    action_line = "SHOVE — call any all-in (AA)"
                    why_line = "Only AA beats AA; get it all in."
                else:
                    check_fold = True
                    action_line = "FOLD  (4th raise ≈ AA)"
                    why_line = ("Gordon's rule: the 4th raise means aces. "
                                "Save chips for a clean spot.")
            elif facing_raise:
                # Re-raised before us
                if tier <= 2:
                    bet_raise = True
                    action_line = f"3-BET  (tier {tier} hand vs raise)"
                    why_line = ("Re-raise to isolate / take the lead. "
                                "Gordon: 3x the previous bet.")
                elif tier == 3 and position in ('CO', 'BTN'):
                    action_line = "CALL in position"
                    why_line = "Set/draw equity + positional advantage."
                else:
                    check_fold = True
                    action_line = f"FOLD  (tier {tier} vs raise)"
                    why_line = "Out of position / dominated; wait."
            elif first_in:
                # Open-raising decision
                if tier <= 3 or (tier == 4 and position in ('CO', 'BTN')):
                    bet_raise = True
                    action_line = self._gordon_open_size(
                        position, bb_amount, pot)
                    why_line = ("First in → always raise (Gordon's 5 "
                                "reasons: thin field, take lead, define "
                                "ranges, conceal strength, win blinds).")
                elif tier == 4:
                    check_fold = True
                    action_line = "FOLD  (tier 4 EP/MP — open only LP)"
                    why_line = "Avoid weak hands out of position."
                elif tier == 5:
                    check_fold = True
                    action_line = "FOLD"
                    why_line = "Patience = profit. No reason to play."
                else:
                    check_fold = True
                    action_line = "FOLD  (trash from this seat)"
                    why_line = "Wait for a real spot."
            else:
                # Already in (BB option, limped pot)
                if tier <= 3:
                    bet_raise = True
                    action_line = "RAISE limpers"
                    why_line = ("Gordon: punish weak limps with a "
                                "pot-sized squeeze in position.")
                else:
                    action_line = "CHECK"
                    why_line = "Take the free flop with this trash."
        else:
            # ---- Postflop: equity vs pot odds drives the call gate ----
            equity_pct = equity * 100
            pot_odds_pct = pot_odds * 100
            if to_call <= 0:
                # We can bet or check
                if equity_pct >= 60 or (num_opps == 1 and equity_pct >= 50):
                    bet_raise = True
                    action_line = "BET 2/3 pot (value)"
                    why_line = ("Gordon: big hand → big pot. Charge "
                                "draws, extract value.")
                elif equity_pct >= 35 and num_opps == 1:
                    bet_raise = True
                    action_line = "C-BET ½ pot"
                    why_line = ("Gordon: continuation bet wins ~65% "
                                "of the time HU when villain misses.")
                else:
                    action_line = "CHECK"
                    why_line = "Pot control with a weak/marginal hand."
            else:
                if equity_pct >= 75 and pot >= bb_amount * 8:
                    bet_raise = True
                    action_line = "RAISE — get it in"
                    why_line = "Top of the range; build the pot."
                elif equity_pct >= pot_odds_pct:
                    if equity_pct >= 60:
                        bet_raise = True
                        action_line = "RAISE for value / protection"
                        why_line = ("Gordon: big hand → big pot. "
                                    "Don't slow-play on draws.")
                    else:
                        action_line = "CALL"
                        why_line = (f"Equity {equity_pct:.0f}% beats "
                                    f"pot odds {pot_odds_pct:.0f}%.")
                else:
                    check_fold = True
                    action_line = "FOLD"
                    why_line = (f"Equity {equity_pct:.0f}% < pot odds "
                                f"{pot_odds_pct:.0f}%; no implied path.")

        # ------- Watch-line (one-line warning) -------
        watch = ""
        if street == 'Preflop' and current_bet > 3 * bb_amount and tier >= 3:
            watch = "WATCH: big preflop pot ≈ they're not folding."
        elif street == 'Flop' and (board := ctx.get('board')):
            ranks = [str(c)[0] for c in board[:3]]
            if len(set(ranks)) < len(ranks):
                watch = "WATCH: paired board — first to bet usually wins."
            elif len({str(c)[1] for c in board[:3]}) == 1:
                watch = "WATCH: monotone flop — flush draws everywhere."
        elif (stack_bb <= 20 and stack_bb > 15
              and street == 'Preflop'):
            watch = "WATCH: ~20 BB — push/fold soon."

        # ------- Assemble (rich-text colored lines) -------
        q1_tag = ("<span style='color:#88ff88'>YES</span>"
                  if bet_raise else "<span style='color:#888'>no</span>")
        q2_tag = ("<span style='color:#ff7777'>YES</span>"
                  if check_fold else "<span style='color:#888'>no</span>")
        action_color = ("#88ff88" if bet_raise
                        else "#ff7777" if check_fold else "#ffd966")
        combo_desc = self._gordon_combo_description(hand_key)
        lines = [
            f"<b>Hand</b> [{hand_str}]  tier {tier}  ·  pos {position}  ·  "
            f"{stack_bb:.0f}bb  ·  {street}",
            f"<span style='color:#9cd6ff'>{combo_desc}</span>",
            f"<b>Q1 Bet / Raise?</b>  → {q1_tag}      "
            f"<b>Q2 Check / Fold?</b>  → {q2_tag}",
            f"<b style='color:{action_color}'>ACTION:</b>  {action_line}",
            f"<b>WHY:</b>  {why_line}",
        ]
        if watch:
            lines.append(f"<b style='color:#ffd966'>⚠ {watch}</b>")
        if unraised:
            lines.append(
                "<span style='color:#888'><i>Unraised pot — "
                "decision is hand-tier × position, not pot odds.</i></span>")
        return "<br>".join(lines)

    def _gordon_open_size(self, position: str, bb: float,
                          pot: float) -> str:
        """Gordon's position-based open-raise sizes."""
        mults = {'UTG': 2.5, 'EP': 2.5, 'MP': 3.0,
                 'CO': 3.5, 'BTN': 3.5, 'SB': 3.0, 'BB': 3.0}
        m = mults.get(position, 3.0)
        return f"RAISE to {m:g}× BB  (${int(m * max(bb, 1))})"

    def get_strategy_advice_v2(self, ctx):
        """Comprehensive strategy advice based on exact game situation."""
        hero_hand = ctx.get('hero_hand')
        if not hero_hand or len(hero_hand) < 2:
            return "Deal cards to receive strategic advice."

        # Parse hand
        c1, c2 = str(hero_hand[0]), str(hero_hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        is_suited = s1 == s2
        is_pair = r1 == r2
        ranks = 'AKQJT98765432'
        r1_val = ranks.index(r1)
        r2_val = ranks.index(r2)
        high_val = min(r1_val, r2_val)
        low_val = max(r1_val, r2_val)
        high_rank = ranks[high_val]
        low_rank = ranks[low_val]
        gap = low_val - high_val

        # Hand notation
        if is_pair:
            hand_str = f"{r1}{r2}"
        elif is_suited:
            hand_str = f"{high_rank}{low_rank}s"
        else:
            hand_str = f"{high_rank}{low_rank}o"

        # Extract context
        street = ctx.get('street', 'Preflop')
        equity = ctx.get('equity', 0.5)
        pot = ctx.get('pot', 0)
        pot_odds = ctx.get('pot_odds', 0)
        to_call = ctx.get('to_call', 0)
        num_opps = ctx.get('num_opponents', 1)
        opponents = ctx.get('opponents', [])
        board = ctx.get('board', [])
        texture = ctx.get('texture', {})
        hero_stack = ctx.get('hero_stack', 200)
        hero_position = ctx.get('hero_position', 'MP')  # Get hero's position

        # Determine opponent styles
        opp_styles = [o.style for o in opponents] if opponents else []
        has_tight = any(s == 'tight' for s in opp_styles)
        has_loose = any(s == 'loose' for s in opp_styles)
        has_aggro = any(s == 'aggressive' for s in opp_styles)

        lines = []

        # Initialize variables for both preflop and postflop
        tier = 5  # Default tier (worst)
        hand_strength = 0  # Default strength
        tex_desc = 'NEUTRAL'  # Default texture

        # === PREFLOP STRATEGY ===
        if street == "Preflop":
            # Map position to display name
            pos_names = {'UTG': 'Under the Gun', 'MP': 'Middle Position', 'CO': 'Cutoff',
                         'BTN': 'Button', 'SB': 'Small Blind', 'BB': 'Big Blind'}
            pos_name = pos_names.get(hero_position, hero_position)
            lines.append(f"═══ PREFLOP: {hand_str} from {pos_name} ═══")

            # Hand tier classification (position-adjusted)
            tier, tier_name = self._classify_hand_tier(hand_str, is_pair, is_suited, high_val, low_val, gap, hero_position)
            lines.append(f"Hand Tier: {tier} - {tier_name}")

            # Position-specific advice (only for hero's position)
            lines.append("")
            lines.append(f"▶ YOUR ACTION ({hero_position}):")

            # Give position-specific advice based on tier and actual position
            if tier == 1:  # Premium
                lines.append("• RAISE 3-4x BB")
                lines.append("• vs 3-bet: 4-bet or call (never fold)")
                if num_opps > 2:
                    lines.append("• vs multiple callers: Raise larger (4-5x)")
                if is_pair and high_val <= 1:
                    lines.append(f"• {hand_str}: Consider slow-play trap if maniac behind")
            elif tier == 2:  # Strong (TT, 99, AJs, KQs)
                if hero_position == 'UTG':
                    lines.append("• Raise 2.5-3x (only TT+, AK from here)")
                    lines.append("• Be ready to fold to a 3-bet from tight players")
                elif hero_position == 'MP':
                    lines.append("• Raise 3x")
                    lines.append("• Call a 3-bet if deep stacked")
                elif hero_position in ('CO', 'BTN'):
                    lines.append("• Raise 3.5x to isolate")
                    lines.append("• Can 3-bet light occasionally")
                elif hero_position == 'SB':
                    lines.append("• Raise 3x or complete and see flop")
                    lines.append("• 3-bet vs late position steals")
                else:  # BB
                    lines.append("• Defend vs steals - 3-bet or call")
                    lines.append("• Squeeze if multiple callers")
            elif tier == 3:  # Playable (88-66, suited connectors, suited aces)
                if hero_position == 'UTG':
                    lines.append("• FOLD - too vulnerable from early position")
                elif hero_position == 'MP':
                    lines.append("• Raise if folded to, otherwise call/fold")
                    if is_pair:
                        lines.append(f"• Set mining: Need 15:1 implied (~${int(to_call * 15)} behind)")
                elif hero_position in ('CO', 'BTN'):
                    lines.append("• RAISE 3.5x to steal blinds")
                    lines.append("• Can call a 3-bet with position")
                    if is_pair:
                        lines.append(f"• Set mining: Need 15:1 implied (~${int(to_call * 15)} behind)")
                elif hero_position == 'SB':
                    lines.append("• Complete or fold (out of position)")
                    lines.append("• 3-bet occasionally to mix it up")
                else:  # BB
                    lines.append("• Defend vs steals - good pot odds")
                    lines.append("• Can 3-bet squeeze vs LP opens")
            elif tier == 4:  # Marginal (55-22, weak suited)
                if hero_position in ('UTG', 'MP'):
                    lines.append("• FOLD - hand too weak for early position")
                elif hero_position == 'CO':
                    lines.append("• Open-raise ONLY if folded to you")
                    lines.append("• Fold to any resistance")
                elif hero_position == 'BTN':
                    lines.append("• Raise to steal blinds if folded to")
                    lines.append("• Can call small 3-bets with deep stacks")
                elif hero_position == 'SB':
                    lines.append("• Complete if cheap, otherwise fold")
                else:  # BB
                    lines.append("• Defend cheaply, fold to big raises")
                    if is_pair:
                        lines.append("• Set mine only with good implied odds")
            else:  # Fold
                if hero_position == 'BB' and to_call > 0 and pot > 0:
                    pot_ratio = pot / to_call if to_call > 0 else 0
                    if pot_ratio >= 3:
                        lines.append(f"• Getting {pot_ratio:.1f}:1 - can call with any two")
                    else:
                        lines.append("• FOLD - pot odds not good enough")
                elif hero_position == 'BTN':
                    lines.append("• Consider stealing if very weak blinds")
                    lines.append("• Otherwise FOLD")
                else:
                    lines.append("• FOLD - hand not playable from this position")

            # Opponent-specific preflop
            lines.append("")
            lines.append("▶ vs OPPONENT TYPES:")
            if has_tight:
                lines.append("• vs TIGHT: Their raise = premium. Fold marginals.")
            if has_loose:
                lines.append("• vs LOOSE: Tighten up, value bet wider.")
            if has_aggro:
                lines.append("• vs AGGRO: Trap with premiums. 3-bet polar.")

            # Specific heuristics
            if to_call > 0:
                lines.append("")
                lines.append("▶ FACING A RAISE:")
                if tier <= 2:
                    lines.append(f"• Your {hand_str} can 3-bet for value")
                    lines.append(f"• 3-bet size: {to_call * 3}-{to_call * 4} (3-4x their raise)")
                elif tier == 3 and is_pair:
                    implied = hero_stack / to_call if to_call > 0 else 0
                    if implied >= 15:
                        lines.append(f"• CALL for set value (implied odds {implied:.0f}:1)")
                    else:
                        lines.append(f"• FOLD - implied odds only {implied:.0f}:1 (need 15:1)")
                else:
                    lines.append(f"• FOLD - {hand_str} doesn't play well vs raises")

        # === POSTFLOP STRATEGY ===
        else:
            board_cards = [str(c) for c in board] if board else []
            board_str = ' '.join(board_cards)
            lines.append(f"═══ {street.upper()}: {hand_str} on {board_str} ═══")

            # Analyze made hand (pass street so river doesn't show draws)
            made_hand, hand_strength = self._analyze_made_hand(hero_hand, board, street)
            lines.append(f"Made Hand: {made_hand}")

            # Board texture
            tex_desc = texture.get('texture', 'NEUTRAL') if texture else 'NEUTRAL'
            lines.append(f"Board Texture: {tex_desc}")
            if texture:
                if texture.get('flush') == 'THREE-FLUSH':
                    lines.append("⚠ Flush draw possible")
                if texture.get('straight') == 'CONNECTED':
                    lines.append("⚠ Straight draws likely")

            lines.append("")

            # Decision framework based on hand strength
            if hand_strength >= 4:  # Monster (set, two pair+, straight, flush)
                lines.append("▶ MONSTER HAND - BUILD THE POT")
                lines.append(f"• Bet 60-75% pot (${int(pot * 0.66)})")
                if tex_desc in ['WET', 'VERY WET']:
                    lines.append("• WET BOARD: Bet NOW - don't slow-play!")
                    lines.append("• Charge draws - they have ~35% to hit")
                else:
                    lines.append("• DRY BOARD: Can slow-play for one street")
                    lines.append("• Check-raise if opponent is aggressive")

            elif hand_strength == 3:  # Strong (overpair, TPTK)
                lines.append("▶ STRONG HAND - VALUE + PROTECTION")
                lines.append(f"• Bet 50-66% pot (${int(pot * 0.55)})")
                lines.append("• Don't slow-play - charge draws")
                if num_opps > 1:
                    lines.append(f"• CAUTION: {num_opps} opponents - someone may have you beat")
                lines.append("• If raised big: Re-evaluate, may be beaten")

            elif hand_strength == 2:  # Medium (top pair weak kicker, middle pair)
                lines.append("▶ MEDIUM HAND - POT CONTROL")
                lines.append("• Small bet (33-50% pot) or check-call")
                lines.append("• Avoid bloating the pot")
                lines.append("• Fold to heavy aggression (2+ bets)")
                if has_aggro:
                    lines.append("• vs AGGRO: Check-call, let them bluff")

            elif hand_strength == 1:  # Draw
                lines.append("▶ DRAWING HAND - ODDS CALCULATION")
                outs = self._count_outs(hero_hand, board)
                if street == "Flop":
                    win_pct = outs * 4
                    lines.append(f"• {outs} outs × 4 = {win_pct}% to river")
                else:
                    win_pct = outs * 2
                    lines.append(f"• {outs} outs × 2 = {win_pct}% to river")

                if pot_odds > 0:
                    if win_pct / 100 > pot_odds:
                        lines.append(f"• POT ODDS: {pot_odds:.0%} - CALL (+EV)")
                    else:
                        lines.append(f"• POT ODDS: {pot_odds:.0%} - need {win_pct}%")
                        if ctx.get('implied_odds', 0) > 0:
                            lines.append("• Consider implied odds if stacks deep")
                        else:
                            lines.append("• FOLD unless good semi-bluff spot")

                lines.append(f"• SEMI-BLUFF: Bet if fold equity exists")

            else:  # Nothing
                lines.append("▶ NO MADE HAND")
                if equity > 0.40:
                    lines.append("• Some equity - can semi-bluff")
                    lines.append(f"• Bet 50-66% pot as bluff if checked to")
                else:
                    lines.append("• CHECK-FOLD without a story")
                    lines.append("• Only bluff if board favors YOUR range")

            # Pot odds decision
            if to_call > 0:
                lines.append("")
                lines.append(f"▶ FACING BET: ${to_call} to call")
                lines.append(f"  Pot odds: {pot_odds:.0%} | Your equity: {equity:.0%}")
                if equity > pot_odds:
                    lines.append(f"  ✓ PROFITABLE CALL (+EV)")
                else:
                    lines.append(f"  ✗ LOSING CALL - need bluffs or fold")

            # Opponent exploitation
            if opponents:
                lines.append("")
                lines.append("▶ OPPONENT READS:")
                for opp in opponents[:2]:
                    style = opp.style
                    if style == 'tight':
                        lines.append(f"• {opp.name} (TIGHT): Their bet = strength. Fold marginals.")
                    elif style == 'loose':
                        lines.append(f"• {opp.name} (LOOSE): Value bet relentlessly. No bluffs!")
                    elif style == 'aggressive':
                        lines.append(f"• {opp.name} (AGGRO): Check-call to trap. Let them bluff.")
                    elif style == 'optimal':
                        lines.append(f"• {opp.name} (GTO): Play balanced. Tough opponent.")

            # Street-specific advice
            lines.append("")
            if street == "Flop":
                lines.append("▶ FLOP STRATEGY:")
                lines.append("• C-bet 50-66% pot if you were pre-flop raiser")
                lines.append("• C-bet success ~65% on dry boards")
                lines.append("• Check back weak hands for pot control")
            elif street == "Turn":
                lines.append("▶ TURN STRATEGY:")
                lines.append("• Double-barrel with strong hands (60-75% pot)")
                lines.append("• Turn brings draws closer - bet to deny odds")
                lines.append("• Give up weak bluffs that got called")
            elif street == "River":
                lines.append("▶ RIVER STRATEGY:")
                lines.append("• Value bet thin - worse hands may call")
                lines.append("• Bluff only with credible story")
                lines.append(f"• Bluff needs {pot_odds:.0%} folds to break even")

        # === ADVISOR'S TIP (situation-specific) ===
        tip = self._get_strategy_tip(street, hand_strength if street != "Preflop" else tier,
                                     tex_desc if street != "Preflop" else None,
                                     equity, pot_odds, to_call, num_opps, hero_position)
        if tip:
            lines.append("")
            lines.append("═══ ADVISOR'S TIP ═══")
            lines.append(tip)

        return "\n".join(lines)

    def _get_strategy_tip(self, street, strength, texture, equity, pot_odds, to_call, num_opps, position):
        """Return a relevant strategy tip based on the exact situation."""
        # Key strategic principles

        if street == "Preflop":
            # strength here is tier (1-5)
            if strength == 1:
                return "\"With premium hands, your goal is to get money in. Raise for value and don't slow-play - you want action with AA/KK.\""
            elif strength == 2:
                if position in ('CO', 'BTN'):
                    return "\"Position is power. With a strong hand on the button, you can play more aggressively because you act last on every street.\""
                else:
                    return "\"Strong hands play well, but be ready to let them go if a tight player shows real aggression.\""
            elif strength == 3:
                if position in ('CO', 'BTN'):
                    return "\"Suited connectors and small pairs are 'implied odds hands' - you need 15-20x your investment behind to make calling profitable. Play them cheaply in position.\""
                else:
                    return "\"From early position, speculative hands are dangerous. You need great implied odds (15:1+) to play them profitably.\""
            elif strength == 4:
                return "\"Marginal hands lose money in the long run. The difference between pros and amateurs is discipline to fold trash.\""
            else:
                if to_call > 0:
                    return "\"When facing a raise with a weak hand, folding is almost always correct. Don't pay to see flops with garbage.\""
                else:
                    return "\"Even from the blinds, some hands should be folded. Saving bets is as important as winning them.\""

        elif street == "River":
            # RIVER: No more cards - focus on value betting and reading opponents
            if strength >= 5:  # Monster
                return f"\"On the river with a monster, bet for value! Your equity is {equity:.0%}. Size your bet to get called by worse hands - usually 50-75% pot.\""
            elif strength >= 3:  # Strong hand
                if to_call > 0:
                    return f"\"River decision: You have {equity:.0%} equity. If you think you're ahead more than {pot_odds:.0%} of the time, calling is profitable.\""
                else:
                    return f"\"With a strong hand on the river ({equity:.0%} equity), bet for thin value. Worse hands will call more often than you think.\""
            elif strength == 2:  # Medium
                if to_call > 0:
                    return f"\"Medium hands on the river are tough. You need to be right {pot_odds:.0%} of the time to call. Trust your reads on opponent tendencies.\""
                else:
                    return "\"With a medium hand and no bet facing you, checking is usually best. You rarely get called by worse or fold out better.\""
            else:  # Weak/nothing
                if to_call == 0:
                    bluff_freq = pot_odds if pot_odds > 0 else 0.33
                    return f"\"River bluff math: Your bluff needs to work {bluff_freq:.0%} of the time to break even. Does your opponent fold that often? Consider their tendencies.\""
                else:
                    return "\"Facing a river bet with nothing - this is where reads matter. Tight players rarely bluff the river. Fold unless you have a strong read.\""

        else:  # Flop or Turn
            # strength here is hand_strength (0-6)
            if strength >= 5:  # Monster (set, flush, straight, full house)
                if texture in ('WET', 'VERY WET'):
                    return "\"On wet boards with a monster, bet now! Don't give free cards. Make opponents pay to chase their draws.\""
                else:
                    return "\"With a monster on a dry board, you can slow-play for one street to let opponents catch up - but don't get too tricky.\""

            elif strength == 4:  # Two pair
                if num_opps > 1:
                    return "\"Two pair is vulnerable multiway. Bet to protect your hand and charge draws - don't let the whole table see free cards.\""
                else:
                    return "\"Two pair is usually the best hand heads-up. Value bet and don't slow-play on coordinated boards.\""

            elif strength == 3:  # Overpair/TPTK
                if texture in ('WET', 'VERY WET'):
                    return "\"Top pair on a wet board is a one-pair hand in a two-pair world. Bet for protection but be ready to fold to heavy heat.\""
                else:
                    return "\"Top pair, top kicker on a dry board is often best. Value bet two streets but control the pot size.\""

            elif strength == 2:  # Medium hands
                return "\"With medium-strength hands, pot control is key. Check-call to keep the pot small and get to showdown cheaply.\""

            elif strength == 1:  # Draws
                if pot_odds > 0 and equity > pot_odds:
                    return f"\"POT ODDS: You have {equity:.0%} equity vs {pot_odds:.0%} needed - this is a +EV call! IMPLIED ODDS make it even better if stacks are deep.\""
                elif pot_odds > 0:
                    return f"\"POT ODDS: You have {equity:.0%} equity but need {pot_odds:.0%}. Consider IMPLIED ODDS - can you win a big pot if you hit? If not, fold or semi-bluff.\""
                else:
                    return "\"With a draw and no bet to call, semi-bluff! You can win by making them fold OR by hitting your hand. Bet 50-66% pot.\""

            else:  # Nothing
                if to_call == 0:
                    return "\"When you have nothing but it's checked to you, a well-timed bluff can take it down. But pick your spots - bluff dry boards, not wet ones.\""
                else:
                    return "\"When you've got nothing and facing a bet, folding is not weak - it's smart. Live to fight another hand.\""

        return None

    def _classify_hand_tier(self, hand_str, is_pair, is_suited, high_val, low_val, gap, position='MP'):
        """Classify starting hand into tiers 1-5, adjusted by position.

        Position codes: UTG, MP (middle), CO (cutoff), BTN (button), SB, BB
        Late position (CO, BTN) allows playing weaker hands.
        """
        ranks = 'AKQJT98765432'
        high_rank = ranks[high_val]
        low_rank = ranks[low_val]

        # Position bonus: late positions can play more hands
        is_late = position in ('BTN', 'CO')
        is_blind = position in ('SB', 'BB')
        is_early = position in ('UTG', 'MP')

        # Tier 1: Premium (play from anywhere)
        if is_pair and high_val <= 3:  # AA, KK, QQ, JJ
            return 1, "PREMIUM PAIR"
        if high_rank == 'A' and low_rank == 'K':
            return 1, "BIG SLICK"
        if is_suited and high_rank == 'A' and low_rank == 'Q':
            return 1, "PREMIUM SUITED"

        # Tier 2: Strong
        if is_pair and high_val <= 5:  # TT, 99
            return 2, "STRONG PAIR"
        if high_rank == 'A' and low_rank in 'QJ':
            return 2, "STRONG ACE"
        if is_suited and high_rank == 'K' and low_rank == 'Q':
            return 2, "SUITED BROADWAY"
        # Late position upgrades
        if is_late:
            if high_rank == 'A' and low_rank == 'T':  # ATo upgrade on button
                return 2, "STRONG ACE (BTN)"

        # Tier 3: Playable
        if is_pair and high_val <= 8:  # 88, 77, 66
            return 3, "MEDIUM PAIR"
        if is_suited and high_rank == 'A':
            return 3, "SUITED ACE"
        if is_suited and gap <= 1 and high_val >= 3 and high_val <= 8:
            return 3, "SUITED CONNECTOR"
        if high_rank in 'KQ' and low_rank in 'QJT':
            return 3, "BROADWAY"
        # Late position upgrades for broadway offsuit
        if is_late:
            if high_rank in 'KQJ' and low_rank in 'JT9':  # KJo, QTo, JTo on button
                return 3, "BROADWAY (LATE POS)"
            if is_suited and gap <= 2 and high_val <= 8:  # Suited one-gappers
                return 3, "SUITED GAPPER (LATE)"

        # Tier 4: Marginal
        if is_pair:  # 55-22
            return 4, "SMALL PAIR"
        if is_suited and gap <= 2:
            return 4, "SUITED GAPPER"
        if is_suited:
            return 4, "WEAK SUITED"
        # Late position allows offsuit broadway
        if is_late:
            if high_rank in 'AKQJT' and low_rank in 'KQJT9':  # Offsuit broadway on BTN
                return 4, "OFFSUIT BROADWAY (LATE)"
        # Blind defense
        if is_blind:
            if high_rank in 'AKQJ' or is_suited:  # Wider defense range
                return 4, "BLIND DEFENSE"

        # Tier 5: Fold (from early/middle - but playable from late)
        if is_late:
            # On button, can play wider
            if high_rank in 'AKQJT' or is_suited:
                return 4, "STEAL CANDIDATE (BTN)"
        return 5, "FOLD"

    def _analyze_made_hand(self, hero_hand, board, street=None):
        """Analyze what made hand hero has. On river, don't report draws."""
        if not board:
            return "Preflop", 0

        is_river = (street == "River") or (len(board) >= 5)

        c1, c2 = str(hero_hand[0]), str(hero_hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        ranks = 'AKQJT98765432'

        board_cards = [str(c) for c in board]
        board_ranks = [bc[0] for bc in board_cards]
        board_suits = [bc[1] for bc in board_cards]

        all_ranks = [r1, r2] + board_ranks
        all_suits = [s1, s2] + board_suits

        # Count ranks and suits
        rank_counts = {}
        for r in all_ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Count board ranks separately
        board_rank_counts = {}
        for r in board_ranks:
            board_rank_counts[r] = board_rank_counts.get(r, 0) + 1

        suit_counts = {}
        for s in all_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        is_pair = r1 == r2

        # Check for full house (three of a kind + pair)
        trips_rank = None
        pair_rank = None
        for r, cnt in rank_counts.items():
            if cnt >= 3:
                trips_rank = r
            elif cnt == 2:
                pair_rank = r
        if trips_rank and pair_rank:
            return f"FULL HOUSE ({trips_rank}s full of {pair_rank}s)", 6

        # Check for flush
        hero_suits = [s1, s2]
        for suit in hero_suits:
            if suit_counts.get(suit, 0) >= 5:
                return "FLUSH", 5

        # Check for set (pocket pair hits one on board)
        if is_pair and rank_counts.get(r1, 0) >= 3:
            return f"SET of {r1}s", 5

        # Check for trips (one hole card matches a PAIR on the board)
        for hole_rank in [r1, r2]:
            if rank_counts.get(hole_rank, 0) >= 3:
                # We have 3+ of this rank - check if board has 2+ (making it trips, not set)
                if board_rank_counts.get(hole_rank, 0) >= 2:
                    return f"TRIPS ({hole_rank}s)", 5

        # Check for straight
        all_vals = sorted(set(ranks.index(r) for r in all_ranks))
        # Check for 5-card straight
        for i in range(len(all_vals) - 4):
            if all_vals[i+4] - all_vals[i] == 4:
                # Verify hero uses at least one card
                hero_vals = [ranks.index(r1), ranks.index(r2)]
                straight_vals = all_vals[i:i+5]
                if any(hv in straight_vals for hv in hero_vals):
                    return "STRAIGHT", 5

        # Check for two pair
        pairs = [r for r, cnt in rank_counts.items() if cnt >= 2]
        hero_in_pairs = [r for r in [r1, r2] if r in pairs]
        board_pairs = [r for r, cnt in board_rank_counts.items() if cnt >= 2]
        if len(pairs) >= 2 and len(hero_in_pairs) >= 1:
            # Count how many pairs the hero actually contributes to
            hero_contributed_pairs = len(hero_in_pairs)
            if hero_contributed_pairs >= 2:
                # Both hole cards pair with the board = strong two pair
                return "TWO PAIR", 4
            elif hero_contributed_pairs == 1 and board_pairs:
                # One hole card pairs + board pair = weaker (everyone has the board pair)
                return "TWO PAIR (board pair)", 2
            else:
                # One hole card pairs something = just a pair effectively
                return "TWO PAIR", 3

        # Check for overpair
        if is_pair:
            r1_val = ranks.index(r1)
            if all(r1_val < ranks.index(br) for br in board_ranks):
                return f"OVERPAIR ({r1}{r1})", 3
            else:
                return f"POCKET PAIR ({r1}{r1})", 2

        # Check for top pair
        if board_ranks:
            sorted_board = sorted(board_ranks, key=lambda x: ranks.index(x))
            top_rank = sorted_board[0]
            if r1 == top_rank or r2 == top_rank:
                kicker = r2 if r1 == top_rank else r1
                kicker_val = ranks.index(kicker)
                if kicker_val <= 2:
                    return f"TOP PAIR TOP KICKER", 3
                elif kicker_val <= 5:
                    return f"TOP PAIR GOOD KICKER", 2
                else:
                    return f"TOP PAIR WEAK KICKER", 2

        # Check for middle/bottom pair
        if r1 in board_ranks or r2 in board_ranks:
            paired_rank = r1 if r1 in board_ranks else r2
            sorted_board = sorted(board_ranks, key=lambda x: ranks.index(x))
            if len(sorted_board) >= 2 and paired_rank == sorted_board[1]:
                return f"SECOND PAIR ({paired_rank}s)", 2
            return f"BOTTOM PAIR ({paired_rank}s)", 2

        # Check for draws (only before river - no more cards to come on river)
        if not is_river:
            # Check for flush draw
            for suit in hero_suits:
                if suit_counts.get(suit, 0) == 4:
                    return "FLUSH DRAW (9 outs)", 1

            # Check for straight draw (open-ended or gutshot)
            for i in range(len(all_vals) - 3):
                if all_vals[i+3] - all_vals[i] <= 4:
                    return "STRAIGHT DRAW", 1

            # Check for overcards
            if board_ranks:
                board_high = min(ranks.index(br) for br in board_ranks)
                hero_high = min(ranks.index(r1), ranks.index(r2))
                if hero_high < board_high:
                    return "OVERCARDS", 1

        return "HIGH CARD", 0

    def _count_outs(self, hero_hand, board):
        """Estimate number of outs for draws."""
        c1, c2 = str(hero_hand[0]), str(hero_hand[1])
        s1, s2 = c1[1], c2[1]

        board_suits = [str(c)[1] for c in board] if board else []
        all_suits = [s1, s2] + board_suits

        suit_counts = {}
        for s in all_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        outs = 0
        # Flush draw
        if suit_counts.get(s1, 0) == 4 or suit_counts.get(s2, 0) == 4:
            outs += 9

        # Straight draw (simplified)
        ranks = 'AKQJT98765432'
        r1, r2 = c1[0], c2[0]
        board_ranks = [str(c)[0] for c in board] if board else []
        all_vals = sorted(set(ranks.index(r) for r in [r1, r2] + board_ranks))

        if len(all_vals) >= 4:
            # Check for open-ended
            for i in range(len(all_vals) - 3):
                spread = all_vals[i+3] - all_vals[i]
                if spread == 3:
                    outs += 8  # OESD
                elif spread == 4:
                    outs += 4  # Gutshot

        # Overcards (2 outs each)
        if board_ranks:
            board_high = min(ranks.index(br) for br in board_ranks)
            if ranks.index(r1) < board_high:
                outs += 3
            if ranks.index(r2) < board_high:
                outs += 3

        return min(outs, 21)  # Cap at 21 outs

    def calculate_equity_vs_ranges(self, hero_hand, all_ranges, board, iterations=None):
        """Calculate hero's equity against multiple opponent ranges."""
        if not hero_hand:
            return 0.0

        # Use more iterations for preflop (more variance) and fewer for later streets
        if iterations is None:
            iterations = 800 if not board else 400

        hero_cards = hero_hand
        board_cards = [eval7.Card(s) for s in [str(c) for c in board]] if board else []

        # Collect all possible opponent hands from their ranges
        all_opp_combos = []
        for player_name, range_dict in all_ranges.items():
            combos = self.expand_range_to_combos(range_dict)
            if combos:
                all_opp_combos.append(combos)

        if not all_opp_combos:
            num_opponents = max(1, len(all_ranges))
            return calc_equity_hidden(hero_hand, [str(c) for c in board] if board else [], iterations, num_opponents=num_opponents)

        known_strs = {str(c) for c in hero_cards}
        known_strs.update(str(c) for c in board_cards)

        wins = 0
        ties = 0
        valid_sims = 0

        for _ in range(iterations):
            # Pick random hands for each opponent from their range
            opp_hands = []
            used_cards = set(known_strs)
            valid = True

            for combos in all_opp_combos:
                # Filter combos that don't use already-used cards
                available = [c for c in combos if c[0] not in used_cards and c[1] not in used_cards]
                if not available:
                    valid = False
                    break
                combo = random.choice(available)
                used_cards.add(combo[0])
                used_cards.add(combo[1])
                try:
                    opp_hands.append([eval7.Card(combo[0]), eval7.Card(combo[1])])
                except:
                    valid = False
                    break

            if not valid:
                continue

            # Deal remaining board cards if needed
            sim_deck = eval7.Deck()
            sim_deck.cards = [c for c in sim_deck.cards if str(c) not in used_cards]
            sim_deck.shuffle()

            cards_needed = 5 - len(board_cards)
            if cards_needed > 0:
                if len(sim_deck.cards) < cards_needed:
                    continue
                runout = sim_deck.deal(cards_needed)
                full_board = board_cards + runout
            else:
                full_board = board_cards

            # Evaluate
            hero_score = eval7.evaluate(hero_cards + full_board)
            best_opp_score = max(eval7.evaluate(h + full_board) for h in opp_hands)

            if hero_score > best_opp_score:
                wins += 1
            elif hero_score == best_opp_score:
                ties += 1
            valid_sims += 1

        if valid_sims == 0:
            return 0.5
        return (wins + ties * 0.5) / valid_sims

    def expand_range_to_combos(self, range_dict, threshold=0.3):
        """Expand a range dict to actual card combinations."""
        combos = []
        suits = ['s', 'h', 'd', 'c']

        for hand, weight in range_dict.items():
            if weight < threshold:
                continue

            if len(hand) == 2:  # Pair like "AA"
                r = hand[0]
                for i, s1 in enumerate(suits):
                    for s2 in suits[i+1:]:
                        combos.append((f"{r}{s1}", f"{r}{s2}"))
            elif len(hand) == 3:
                r1, r2, suited = hand[0], hand[1], hand[2]
                if suited == 's':  # Suited
                    for s in suits:
                        combos.append((f"{r1}{s}", f"{r2}{s}"))
                else:  # Offsuit
                    for s1 in suits:
                        for s2 in suits:
                            if s1 != s2:
                                combos.append((f"{r1}{s1}", f"{r2}{s2}"))

        return combos


# --- Stats Panel Widget ---
class StatsPanel(QWidget):
    """Widget displaying graphical equity stats for all players."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.setMaximumHeight(300)
        self.player_stats = []  # List of (name, equity, pot_odds, is_active, is_hero)

    def set_stats(self, stats):
        """Set stats: list of (name, equity, pot_odds, is_active, is_hero)"""
        self.player_stats = stats
        self.update()

    def clear_stats(self):
        self.player_stats = []
        self.update()

    def paintEvent(self, event):
        if not self.player_stats:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(30, 30, 30))

        # Check if we're in god mode (true_equity is not None for first active player)
        god_mode = any(s[1] is not None for s in self.player_stats if s[4])  # s[4] = is_active

        if god_mode:
            bar_max_width = (w - 450) // 3  # Smaller bars to fit 3 columns
        else:
            bar_max_width = (w - 340) // 2

        # Title and column headings
        painter.setPen(QColor(255, 255, 255))
        font = QFont('Arial', 18, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(20, 28, "Player")

        if god_mode:
            real_x = 190
            think_x = real_x + bar_max_width + 15
            po_x = think_x + bar_max_width + 15

            painter.setPen(QColor(100, 200, 255))  # Cyan for Real heading
            painter.drawText(real_x, 28, "Real")
            painter.setPen(QColor(255, 200, 100))  # Orange for Think heading
            painter.drawText(think_x, 28, "Thinking")
            painter.setPen(QColor(200, 150, 50))  # Yellow for PO heading
            painter.drawText(po_x, 28, "Pot Odds")
        else:
            painter.setPen(QColor(100, 255, 100))
            painter.drawText(190, 28, "Equity")
            painter.setPen(QColor(200, 150, 50))
            painter.drawText(210 + bar_max_width + 40, 28, "Pot Odds")

        # Draw stats for each player
        # Tuple format: (name, true_equity, perceived_equity, pot_odds, is_active, is_hero)
        bar_height = 26
        start_y = 42

        for i, (name, true_equity, perceived_equity, pot_odds, is_active, is_hero) in enumerate(self.player_stats):
            y = start_y + i * (bar_height + 5)

            # Player name
            if is_hero:
                painter.setPen(QColor(100, 200, 255))
            elif not is_active:
                painter.setPen(QColor(100, 100, 100))
            else:
                painter.setPen(QColor(200, 200, 200))

            font = QFont('Arial', 15, QFont.Weight.Bold)
            painter.setFont(font)
            name_display = name[:14] if len(name) > 14 else name
            painter.drawText(20, y + 20, name_display)

            if not is_active:
                painter.setPen(QColor(100, 100, 100))
                painter.drawText(190, y + 20, "(Folded)")
                continue

            if god_mode and true_equity is not None:
                # GOD MODE: Show both Real equity and Perceived equity
                # Calculate difference to determine colors
                diff = abs(true_equity - perceived_equity)
                big_diff = diff > 0.20  # More than 20% difference

                # Real equity bar - color based on whether player is overconfident or underconfident
                real_x = 190
                real_width = int(true_equity * bar_max_width)

                # Color real bar based on difference
                if big_diff:
                    if true_equity > perceived_equity:
                        real_color = QColor(50, 200, 50)  # Green - better than they think
                    else:
                        real_color = QColor(200, 50, 50)  # Red - worse than they think
                else:
                    real_color = QColor(100, 180, 220)  # Normal cyan

                painter.fillRect(real_x, y, bar_max_width, bar_height, QColor(60, 60, 60))
                painter.fillRect(real_x, y, real_width, bar_height, real_color)
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRect(real_x, y, bar_max_width, bar_height)

                # Percentage text inside bar
                painter.setPen(QColor(255, 255, 255))
                font = QFont('Arial', 13, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(real_x + 5, y + 19, f"{true_equity:.0%}")

                # Perceived equity bar - orange tint
                think_x = real_x + bar_max_width + 15
                think_width = int(perceived_equity * bar_max_width)

                if big_diff:
                    if perceived_equity > true_equity:
                        think_color = QColor(255, 100, 100)  # Red tint - overconfident
                    else:
                        think_color = QColor(100, 200, 100)  # Green tint - underconfident
                else:
                    think_color = QColor(220, 160, 80)  # Normal orange

                painter.fillRect(think_x, y, bar_max_width, bar_height, QColor(60, 60, 60))
                painter.fillRect(think_x, y, think_width, bar_height, think_color)
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRect(think_x, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                painter.drawText(think_x + 5, y + 19, f"{perceived_equity:.0%}")

                # Pot odds bar
                po_x = think_x + bar_max_width + 15
            else:
                # NORMAL MODE: Just show perceived equity
                eq_width = int(perceived_equity * bar_max_width)
                eq_color = self.get_equity_color(perceived_equity)

                painter.fillRect(190, y, bar_max_width, bar_height, QColor(60, 60, 60))
                painter.fillRect(190, y, eq_width, bar_height, eq_color)
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRect(190, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                font = QFont('Arial', 14, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(195, y + 19, f"{perceived_equity:.0%}")

                po_x = 210 + bar_max_width + 40

            # Pot odds bar
            po_width = int(pot_odds * bar_max_width)
            po_color = QColor(200, 150, 50)

            painter.fillRect(po_x, y, bar_max_width, bar_height, QColor(60, 60, 60))
            painter.fillRect(po_x, y, po_width, bar_height, po_color)
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawRect(po_x, y, bar_max_width, bar_height)

            painter.setPen(QColor(255, 255, 255))
            font = QFont('Arial', 13, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(po_x + 5, y + 19, f"{pot_odds:.0%}")

            # EV indicator (based on TRUE equity in god mode, perceived otherwise)
            ev_equity = true_equity if (god_mode and true_equity is not None) else perceived_equity
            ev_x = po_x + bar_max_width + 15
            font = QFont('Arial', 15, QFont.Weight.Bold)
            painter.setFont(font)
            if ev_equity > pot_odds:
                painter.setPen(QColor(50, 200, 50))
                painter.drawText(ev_x, y + 20, "+EV")
            elif ev_equity < pot_odds:
                painter.setPen(QColor(200, 50, 50))
                painter.drawText(ev_x, y + 20, "-EV")
            else:
                painter.setPen(QColor(200, 200, 50))
                painter.drawText(ev_x, y + 21, "=EV")

    def get_equity_color(self, equity):
        """Return color based on equity value (red to green gradient)."""
        if equity < 0.3:
            return QColor(200, 50, 50)
        elif equity < 0.5:
            return QColor(200, 150, 50)
        elif equity < 0.7:
            return QColor(150, 200, 50)
        else:
            return QColor(50, 200, 50)


class HandSummaryDialog(QDialog):
    """Full-screen hand summary showing stacked bar charts for each street."""

    def __init__(self, street_stats, street_actions, board_by_street, player_results,
                 player_hands=None, made_hands_by_street=None,
                 pot_by_street=None, street_reflections=None,
                 reflection_status="Awaiting Claude (Opus 4.7) — perfect-hindsight reflections will appear under each street as they finish.",
                 parent=None):
        super().__init__(parent)
        self.street_stats = street_stats  # {street: [(name, true_eq, perc_eq, pot_odds, active, is_hero), ...]}
        self.street_actions = street_actions  # {street: ["Player: action", ...]}
        self.board_by_street = board_by_street  # {street: [card_strs]}
        self.player_results = player_results  # {name: (start_stack, end_stack, change)}
        self.player_hands = player_hands or {}  # {name: [card_strs]}
        self.made_hands_by_street = made_hands_by_street or {}  # {street: {name: "hand description"}}
        self.pot_by_street = pot_by_street or {}  # {street: pot_after_street}
        # Perfect-hindsight reflection paragraph for each street, written
        # by Claude after the hand. Populated lazily — the dialog opens
        # with placeholder text and `set_street_reflections` swaps it in
        # once Claude finishes.
        self.street_reflections = dict(street_reflections or {})
        self._reflection_status = reflection_status
        self._reflection_labels = {}  # {street: QLabel}

        self.setWindowTitle("Hand Summary - Stats")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: #1a1a1a;")

        # Full screen
        screen = self.screen().geometry()
        self.setGeometry(screen)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 15, 30, 15)
        layout.setSpacing(8)

        # Title
        title = QLabel("Hand Summary")
        title.setStyleSheet("font-size: 42px; font-weight: bold; color: #0af;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Scrollable streets container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: #2a2a2a; width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background: #555; border-radius: 6px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #666; }
        """)

        streets_widget = QWidget()
        streets_layout = QVBoxLayout(streets_widget)
        streets_layout.setSpacing(12)
        streets_layout.setContentsMargins(0, 0, 10, 0)

        # Add panel for each street (all 4, even if not played).
        # Per-row height bumped 36→48 and header 50→70 to match the
        # larger fonts in StreetBarChart (was 11-12pt, now 17-19pt).
        num_players = len(self.player_results) if self.player_results else 6
        panel_height = 70 + (num_players * 48)  # header + player rows

        streets_order = ["Preflop", "Flop", "Turn", "River"]
        for street in streets_order:
            panel = self.create_street_panel(street)
            panel.setMinimumHeight(panel_height)
            panel.setMaximumHeight(panel_height + 20)  # Slight flexibility
            streets_layout.addWidget(panel)
            # Per-street perfect-hindsight reflection from Claude. Sits
            # immediately under the equity/actions panel so the
            # commentary lines up with the street it describes. Hidden
            # for streets the hand never reached.
            reflection_widget = self._create_reflection_widget(street)
            if reflection_widget is not None:
                streets_layout.addWidget(reflection_widget)

        # Don't add stretch - let panels take their natural size
        scroll_area.setWidget(streets_widget)
        layout.addWidget(scroll_area, stretch=1)

        # Bottom: Player results (gain/loss)
        results_panel = self.create_results_panel()
        layout.addWidget(results_panel)

        # NOTE: no OK / Close button — the hand summary persists until the
        # next hand begins (PokerWindow._close_open_hand_dialogs handles
        # dismissal in deal_hand). A discrete "Back" button still lets the
        # user return to the parent text dialog.
        back_btn = QPushButton("Back to Summary")
        back_btn.setFixedSize(280, 60)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                font-size: 24px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        back_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(back_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _create_reflection_widget(self, street):
        """Yellow italic block under each street panel showing Claude's
        perfect-hindsight commentary for that street.

        Returns None for streets the hand never reached (no stats AND
        no actions) so we don't leave dead "(not played)" gaps.
        """
        has_stats = street in self.street_stats
        has_actions = bool(self.street_actions.get(street))
        if not (has_stats or has_actions):
            return None
        text = (self.street_reflections.get(street)
                or self._reflection_status)
        is_placeholder = street not in self.street_reflections
        wrap = QWidget()
        wrap.setStyleSheet(
            "background-color: #2a2410; border-left: 4px solid #ffd966;"
            " border-radius: 6px;")
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(20, 10, 20, 12)
        wrap_layout.setSpacing(6)
        # Hindsight type sits one notch above the surrounding stats —
        # 28pt header, 26pt body — so the post-mortem reads as the most
        # important block on the panel.
        head = QLabel(f"Hindsight — {street}")
        head.setStyleSheet(
            "font-size: 28px; font-weight: bold; color: #ffd966;"
            " background: transparent; border: none;")
        wrap_layout.addWidget(head)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(
            "font-size: 26px; color: %s; background: transparent;"
            " border: none; font-style: %s; line-height: 1.35;"
            % ("#bcae7a" if is_placeholder else "#ffd966",
               "italic" if is_placeholder else "normal"))
        wrap_layout.addWidget(body)
        self._reflection_labels[street] = body
        return wrap

    def set_street_reflections(self, reflections: dict,
                                status_text: str = ""):
        """Swap in Claude's per-street paragraphs after the dialog is
        already showing. Called from the host's analysis callback once
        the annotate-mode Claude run finishes.

        ``reflections`` is ``{street: paragraph}``. Streets missing from
        the dict keep showing the placeholder; if the model produced
        nothing useful, callers pass an empty dict and a ``status_text``
        like "Claude returned no reflections." so the user knows why
        the placeholder remained.
        """
        self.street_reflections = dict(reflections or {})
        for street, label in list(self._reflection_labels.items()):
            try:
                if street in self.street_reflections:
                    label.setText(self.street_reflections[street])
                    label.setStyleSheet(
                        "font-size: 26px; color: #ffd966;"
                        " background: transparent; border: none;"
                        " font-style: normal; line-height: 1.35;")
                elif status_text:
                    label.setText(status_text)
            except RuntimeError:
                # Dialog was closed mid-flight; drop silently.
                pass

    def create_street_panel(self, street):
        """Create a panel for one street with bar chart and actions."""
        # Check if this street was played
        has_stats = street in self.street_stats

        panel = QWidget()
        if has_stats:
            panel.setStyleSheet("background-color: #252525; border-radius: 10px;")
        else:
            panel.setStyleSheet("background-color: #1f1f1f; border-radius: 10px;")

        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(20, 12, 20, 12)
        panel_layout.setSpacing(20)

        # Left side: Street label and board cards
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Street name - larger font
        street_label = QLabel(street)
        if has_stats:
            street_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #0af;")
        else:
            street_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #555;")
        left_layout.addWidget(street_label)

        # Board cards for this street (show only NEW cards dealt)
        board_cards = self.board_by_street.get(street, [])
        if street == "Preflop":
            new_cards = []  # No board cards on preflop
        elif street == "Flop":
            new_cards = board_cards[:3]  # First 3 cards
        elif street == "Turn":
            new_cards = board_cards[3:4] if len(board_cards) >= 4 else []  # 4th card
        elif street == "River":
            new_cards = board_cards[4:5] if len(board_cards) >= 5 else []  # 5th card
        else:
            new_cards = board_cards

        if new_cards:
            cards_html = " ".join(self.format_card(c, use_html=True) for c in new_cards)
            cards_label = QLabel(cards_html)
            cards_label.setTextFormat(Qt.TextFormat.RichText)
            cards_label.setStyleSheet("font-size: 28px; background-color: #f8f8f8; padding: 4px 8px; border-radius: 5px;")
            left_layout.addWidget(cards_label)
        else:
            placeholder = QLabel("—" if street == "Preflop" else "")
            placeholder.setStyleSheet("font-size: 24px; color: #555;")
            left_layout.addWidget(placeholder)

        # Pot size after this street, if recorded.
        if street in self.pot_by_street:
            pot_label = QLabel(f"Pot: ${int(self.pot_by_street[street])}")
            pot_label.setStyleSheet(
                "font-size: 22px; font-weight: bold; color: #ffd966; padding: 2px 0;")
            left_layout.addWidget(pot_label)

        left_layout.addStretch()
        left_widget.setFixedWidth(170)
        panel_layout.addWidget(left_widget)

        # Center: Bar chart widget with hole cards and made hands
        if has_stats:
            # Pass player hands and made hands to the chart
            street_made_hands = self.made_hands_by_street.get(street, {})
            stats = self.street_stats.get(street, [])
            chart_widget = StreetBarChart(
                stats,
                player_hands=self.player_hands,
                made_hands=street_made_hands
            )
            # Height: 60 header + 46 per player row (matches the
            # bar_height/start_y bumps in StreetBarChart.paintEvent).
            chart_height = 60 + len(stats) * 46
            chart_widget.setMinimumHeight(chart_height)
        else:
            chart_widget = QLabel("Not played")
            chart_widget.setStyleSheet("font-size: 24px; color: #444;")
            chart_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(chart_widget, stretch=3)

        # Right side: Actions with key decisions highlighted
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(3)

        # Add "Key Actions" header
        header = QLabel("Actions:")
        header.setStyleSheet("font-size: 20px; color: #888; font-weight: bold;")
        right_layout.addWidget(header)

        actions = self.street_actions.get(street, [])
        for action in actions[:8]:  # Limit to 8 actions per street
            action_label = QLabel(action)
            action_lower = action.lower()

            # Highlight key decisions with different colors - larger font
            if 'all-in' in action_lower or 'all in' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #ff4444; font-weight: bold;")  # Red for all-in
            elif 'raises to' in action_lower and any(x in action_lower for x in ['$50', '$100', '$150', '$200']):
                action_label.setStyleSheet("font-size: 22px; color: #ff8844; font-weight: bold;")  # Orange for big raises
            elif 'folds' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #888;")  # Gray for folds
            elif 'raises' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #ffcc00;")  # Yellow for raises
            elif 'bets' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #44ff44;")  # Green for bets
            elif 'calls' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #44aaff;")  # Blue for calls
            elif 'checks' in action_lower:
                action_label.setStyleSheet("font-size: 22px; color: #aaa;")  # Light gray for checks
            else:
                action_label.setStyleSheet("font-size: 22px; color: #ccc;")

            action_label.setWordWrap(True)
            right_layout.addWidget(action_label)

        right_layout.addStretch()
        right_widget.setFixedWidth(380)
        panel_layout.addWidget(right_widget)

        return panel

    def format_card(self, card_str, use_html=True):
        """Format card string with suit symbol and optional HTML color."""
        if len(card_str) < 2:
            return card_str
        rank = card_str[0]
        suit = card_str[1]
        suit_symbols = {'s': '\u2660', 'h': '\u2665', 'd': '\u2666', 'c': '\u2663'}
        symbol = suit_symbols.get(suit, suit)

        if use_html:
            # Get color based on legacy_colors preference
            global _use_legacy_colors
            if _use_legacy_colors:
                color = "#dc143c" if suit in ['h', 'd'] else "#222"
            else:
                if suit == 'h':
                    color = "#dc143c"  # Red
                elif suit == 'd':
                    color = "#1e50c8"  # Blue
                elif suit == 'c':
                    color = "#148c3c"  # Green
                else:
                    color = "#222"     # Black (spades)
            return f'<span style="color:{color};font-weight:bold;">{rank}{symbol}</span>'
        else:
            return f"{rank}{symbol}"

    def create_results_panel(self):
        """Create panel showing net gain/loss for each player."""
        panel = QWidget()
        panel.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(30, 20, 30, 20)

        title = QLabel("Hand Results")
        title.setStyleSheet("font-size: 30px; font-weight: bold; color: #fff;")
        panel_layout.addWidget(title)

        # Grid of player results
        results_layout = QHBoxLayout()
        results_layout.setSpacing(50)

        for name, (start, end, change) in self.player_results.items():
            player_widget = QWidget()
            player_layout = QVBoxLayout(player_widget)
            player_layout.setContentsMargins(0, 0, 0, 0)
            player_layout.setSpacing(4)

            name_label = QLabel(name)
            name_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #aaa;")
            player_layout.addWidget(name_label)

            if change > 0:
                change_text = f"+${change}"
                change_color = "#4f4"
            elif change < 0:
                change_text = f"-${abs(change)}"
                change_color = "#f44"
            else:
                change_text = "$0"
                change_color = "#888"

            change_label = QLabel(change_text)
            change_label.setStyleSheet(f"font-size: 34px; font-weight: bold; color: {change_color};")
            player_layout.addWidget(change_label)

            stack_label = QLabel(f"${start} → ${end}")
            stack_label.setStyleSheet("font-size: 20px; color: #666;")
            player_layout.addWidget(stack_label)

            results_layout.addWidget(player_widget)

        results_layout.addStretch()
        panel_layout.addLayout(results_layout)

        return panel


class StreetBarChart(QWidget):
    """Widget that draws the equity bar chart for one street."""

    def __init__(self, stats, player_hands=None, made_hands=None, parent=None):
        super().__init__(parent)
        self.stats = stats  # [(name, true_eq, perc_eq, pot_odds, active, is_hero), ...]
        self.player_hands = player_hands or {}  # {name: [card_strs]}
        self.made_hands = made_hands or {}  # {name: "hand description"}
        self.setMinimumWidth(700)

    def format_card_text(self, card_str):
        """Format card string with suit symbol."""
        if len(card_str) < 2:
            return card_str
        rank = card_str[0]
        suit = card_str[1]
        suit_symbols = {'s': '\u2660', 'h': '\u2665', 'd': '\u2666', 'c': '\u2663'}
        return f"{rank}{suit_symbols.get(suit, suit)}"

    def paintEvent(self, event):
        if not self.stats:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Check if we have god mode data (true_equity is not None)
        god_mode = any(s[1] is not None for s in self.stats if s[4])

        # Calculate column positions — wider since we now use 18-19pt
        # text everywhere (was 11-12pt). Without bumping these, the
        # player names spill into the cards column at the new size.
        name_x = 10
        cards_x = 170  # Hole cards column
        hand_x = cards_x + 100  # Made hand description (wider gap)
        equity_x = 460  # Start of equity bars (pushed right for hand column)

        # Column headings
        painter.setPen(QColor(255, 255, 255))
        font = QFont('Arial', 19, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(name_x, 28, "Player")
        painter.drawText(cards_x, 28, "Cards")
        painter.setPen(QColor(180, 180, 100))
        painter.drawText(hand_x, 28, "Hand")

        # Bar width based on available space
        if god_mode:
            bar_max_width = min((w - equity_x - 320) // 2, 160)
        else:
            bar_max_width = min(w - equity_x - 270, 220)
        bar_max_width = max(bar_max_width, 80)

        if god_mode:
            real_x = equity_x
            painter.setPen(QColor(100, 200, 255))
            painter.drawText(real_x, 28, "True Equity")
        else:
            painter.setPen(QColor(100, 255, 100))
            painter.drawText(equity_x, 28, "Equity")

        # Implied odds header - positioned after equity status column
        # The actual x position is computed per-row, so just draw header at estimated position
        if god_mode:
            odds_header_x = equity_x + bar_max_width * 2 + 110
        else:
            odds_header_x = equity_x + bar_max_width + 105
        painter.setPen(QColor(200, 160, 100))
        painter.drawText(odds_header_x, 28, "Pot/Implied")

        # Bars are taller (28→38) to balance the larger fonts.
        bar_height = 38
        start_y = 52

        for i, (name, true_equity, perceived_equity, pot_odds, is_active, is_hero) in enumerate(self.stats):
            y = start_y + i * (bar_height + 8)

            # Player name - larger font
            if is_hero:
                painter.setPen(QColor(100, 200, 255))
            elif not is_active:
                painter.setPen(QColor(100, 100, 100))
            else:
                painter.setPen(QColor(200, 200, 200))

            font = QFont('Arial', 19, QFont.Weight.Bold)
            painter.setFont(font)
            name_display = name[:14] if len(name) > 14 else name
            painter.drawText(name_x, y + 26, name_display)

            # Draw hole cards with white background for readability
            hole_cards = self.player_hands.get(name, [])
            if hole_cards:
                card_font = QFont('Arial', 17, QFont.Weight.Bold)
                painter.setFont(card_font)
                card_x = cards_x
                for card in hole_cards[:2]:
                    card_text = self.format_card_text(card)
                    suit = card[1] if len(card) > 1 else ''
                    # Larger card pill (was 26x22) to host the bigger font.
                    painter.fillRect(card_x - 3, y + 2, 38, 32, QColor(250, 250, 245))
                    painter.setPen(QPen(QColor(180, 180, 180), 1))
                    painter.drawRect(card_x - 3, y + 2, 38, 32)
                    # Color by suit
                    if suit == 'h':
                        painter.setPen(QColor(220, 40, 40))  # Red hearts
                    elif suit == 'd':
                        painter.setPen(QColor(40, 100, 220))  # Blue diamonds
                    elif suit == 'c':
                        painter.setPen(QColor(40, 160, 40))  # Green clubs
                    else:
                        painter.setPen(QColor(30, 30, 30))  # Black spades
                    painter.drawText(card_x + 2, y + 26, card_text)
                    card_x += 44

            # Draw made hand description - larger font for readability
            made_hand = self.made_hands.get(name, '')
            if made_hand and is_active:
                hand_font = QFont('Arial', 17, QFont.Weight.Bold)
                painter.setFont(hand_font)
                painter.setPen(QColor(220, 220, 120))
                # Truncate to fit column width (hand_x to equity_x)
                max_chars = max(14, (equity_x - hand_x - 10) // 11)
                made_display = made_hand[:max_chars] if len(made_hand) > max_chars else made_hand
                painter.drawText(hand_x, y + 26, made_display)

            if not is_active:
                painter.setPen(QColor(100, 100, 100))
                font = QFont('Arial', 19)
                painter.setFont(font)
                painter.drawText(equity_x, y + 26, "(Folded)")
                continue

            if god_mode and true_equity is not None:
                # GOD MODE: Show Real, Thinking, Pot Odds
                diff = abs(true_equity - perceived_equity)
                big_diff = diff > 0.20

                # Real equity bar
                real_x = equity_x
                real_width = int(true_equity * bar_max_width)

                if big_diff:
                    if true_equity > perceived_equity:
                        real_color = QColor(50, 200, 50)
                    else:
                        real_color = QColor(200, 50, 50)
                else:
                    real_color = QColor(100, 180, 220)

                painter.fillRect(real_x, y, bar_max_width, bar_height, QColor(50, 50, 50))
                painter.fillRect(real_x, y, real_width, bar_height, real_color)
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawRect(real_x, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                font = QFont('Arial', 19, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(real_x + 4, y + 26, f"{true_equity:.0%}")

                # Perceived equity bar
                think_x = real_x + bar_max_width + 12
                think_width = int(perceived_equity * bar_max_width)

                if big_diff:
                    if perceived_equity > true_equity:
                        think_color = QColor(255, 100, 100)
                    else:
                        think_color = QColor(100, 200, 100)
                else:
                    think_color = QColor(220, 160, 80)

                painter.fillRect(think_x, y, bar_max_width, bar_height, QColor(50, 50, 50))
                painter.fillRect(think_x, y, think_width, bar_height, think_color)
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawRect(think_x, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                painter.drawText(think_x + 4, y + 26, f"{perceived_equity:.0%}")

                # Show equity status indicator after bars in god mode
                ev_x = think_x + bar_max_width + 14
                font = QFont('Arial', 19, QFont.Weight.Bold)
                painter.setFont(font)
                if true_equity > 0.5:
                    painter.setPen(QColor(50, 200, 50))
                    painter.drawText(ev_x, y + 26, "AHEAD")
                elif true_equity > 0.3:
                    painter.setPen(QColor(200, 200, 50))
                    painter.drawText(ev_x, y + 26, "LIVE")
                else:
                    painter.setPen(QColor(200, 50, 50))
                    painter.drawText(ev_x, y + 26, "BEHIND")

                # Implied odds column (god mode)
                odds_x = ev_x + 100
                font = QFont('Arial', 17)
                painter.setFont(font)
                if pot_odds > 0:
                    implied = pot_odds * 1.5  # Implied odds estimate: pot odds + future value
                    # Color: green if equity > implied odds (profitable call)
                    if true_equity > pot_odds:
                        painter.setPen(QColor(50, 200, 50))
                    else:
                        painter.setPen(QColor(200, 100, 50))
                    painter.drawText(odds_x, y + 26, f"{pot_odds:.0%}/{implied:.0%}")
                else:
                    painter.setPen(QColor(120, 120, 120))
                    painter.drawText(odds_x, y + 26, "—")
            else:
                # Normal mode: Just show perceived equity
                eq_width = int(perceived_equity * bar_max_width)
                eq_color = self.get_equity_color(perceived_equity)

                painter.fillRect(equity_x, y, bar_max_width, bar_height, QColor(50, 50, 50))
                painter.fillRect(equity_x, y, eq_width, bar_height, eq_color)
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawRect(equity_x, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                font = QFont('Arial', 19, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(equity_x + 4, y + 26, f"{perceived_equity:.0%}")

                # Show equity status
                ev_x = equity_x + bar_max_width + 18
                font = QFont('Arial', 19, QFont.Weight.Bold)
                painter.setFont(font)
                if perceived_equity > 0.5:
                    painter.setPen(QColor(50, 200, 50))
                    painter.drawText(ev_x, y + 26, "AHEAD")
                elif perceived_equity > 0.3:
                    painter.setPen(QColor(200, 200, 50))
                    painter.drawText(ev_x, y + 26, "LIVE")
                else:
                    painter.setPen(QColor(200, 50, 50))
                    painter.drawText(ev_x, y + 26, "BEHIND")

                # Implied odds column (normal mode)
                odds_x = ev_x + 100
                font = QFont('Arial', 17)
                painter.setFont(font)
                if pot_odds > 0:
                    implied = pot_odds * 1.5
                    if perceived_equity > pot_odds:
                        painter.setPen(QColor(50, 200, 50))
                    else:
                        painter.setPen(QColor(200, 100, 50))
                    painter.drawText(odds_x, y + 26, f"{pot_odds:.0%}/{implied:.0%}")
                else:
                    painter.setPen(QColor(120, 120, 120))
                    painter.drawText(odds_x, y + 26, "—")

    def get_equity_color(self, equity):
        if equity < 0.3:
            return QColor(200, 50, 50)
        elif equity < 0.5:
            return QColor(200, 150, 50)
        elif equity < 0.7:
            return QColor(150, 200, 50)
        else:
            return QColor(50, 200, 50)


# --- Poker Table Widget ---
class PokerTableWidget(QWidget):
    """Widget rendering the poker table felt."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 400)
        self.board_cards = []
        self.hero_cards = []
        self.pot = 0
        self.street = "Preflop"
        self.message = ""

    def set_board(self, cards):
        self.board_cards = cards
        self.update()

    def set_hero_cards(self, cards):
        self.hero_cards = cards
        self.update()

    def set_pot(self, pot):
        self.pot = pot
        self.update()

    def set_street(self, street):
        self.street = street
        self.update()

    def set_message(self, msg):
        self.message = msg
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw table rail (outer)
        rail_rect = QRectF(20, 20, w - 40, h - 40)
        gradient = QRadialGradient(w/2, h/2, max(w, h)/2)
        gradient.setColorAt(0, QColor(140, 90, 50))
        gradient.setColorAt(1, QColor(80, 50, 25))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(TABLE_BORDER, 4))
        painter.drawRoundedRect(rail_rect, 100, 60)

        # Draw felt (inner)
        felt_rect = QRectF(40, 40, w - 80, h - 80)
        gradient = QRadialGradient(w/2, h/2, max(w, h)/2)
        gradient.setColorAt(0, QColor(50, 160, 50))
        gradient.setColorAt(1, QColor(30, 120, 30))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(20, 80, 20), 2))
        painter.drawRoundedRect(felt_rect, 90, 55)

        # === Pot and message with equal spacing from felt edges ===
        # Felt is at y=40 (top) to h-40 (bottom)
        felt_margin = 40
        text_inset = 20  # Distance from felt edge to text

        # Pot at top of felt
        pot_y = felt_margin + text_inset
        painter.setPen(QColor(255, 215, 0))
        font = QFont('Arial', 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, pot_y, w, 45), Qt.AlignmentFlag.AlignCenter, f"Pot: ${self.pot}")

        # === Board cards centered vertically ===
        card_width = 110
        card_height = 154
        card_start_y = h/2 - card_height/2

        if self.board_cards:
            total_width = len(self.board_cards) * card_width + (len(self.board_cards) - 1) * 16
            start_x = w/2 - total_width/2

            for i, card in enumerate(self.board_cards):
                x = start_x + i * (card_width + 16)
                self.draw_card(painter, x, card_start_y, card_width, card_height, str(card))

        # === Winner message at bottom of felt (same inset as pot) ===
        if self.message:
            painter.setPen(QColor(255, 255, 100))
            font = QFont('Arial', 20, QFont.Weight.Bold)
            painter.setFont(font)
            msg_height = 35
            msg_y = h - felt_margin - text_inset - msg_height
            painter.drawText(QRectF(0, msg_y, w, msg_height), Qt.AlignmentFlag.AlignCenter, self.message)

    def draw_card(self, painter, x, y, width, height, card_str):
        """Draw a card at the specified position with given size."""
        rect = QRectF(x, y, width, height)

        # Card background
        painter.setBrush(QBrush(CARD_WHITE))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(rect, 6, 6)

        rank = card_str[0]
        suit = card_str[1]

        color = get_suit_color(suit)
        painter.setPen(color)

        suit_symbols = {'s': '\u2660', 'h': '\u2665', 'd': '\u2666', 'c': '\u2663'}
        rank_display = {'A': 'A', 'K': 'K', 'Q': 'Q', 'J': 'J', 'T': '10',
                       '9': '9', '8': '8', '7': '7', '6': '6', '5': '5',
                       '4': '4', '3': '3', '2': '2'}

        rank_text = rank_display.get(rank, rank)
        suit_symbol = suit_symbols.get(suit, '?')

        # Scale font sizes based on card size
        rank_font_size = max(12, int(width * 0.22))
        suit_small_size = max(10, int(width * 0.18))
        suit_big_size = max(20, int(width * 0.4))

        # Draw rank top-left
        font = QFont('Arial', rank_font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(int(x + 5), int(y + rank_font_size + 4), rank_text)

        # Draw suit top-left
        font = QFont('Arial', suit_small_size)
        painter.setFont(font)
        painter.drawText(int(x + 5), int(y + rank_font_size + suit_small_size + 6), suit_symbol)

        # Draw center suit
        font = QFont('Arial', suit_big_size)
        painter.setFont(font)
        painter.drawText(QRectF(x, y + height * 0.3, width, height * 0.5), Qt.AlignmentFlag.AlignCenter, suit_symbol)


# --- Action Dialog ---
class RaiseDialog(QDialog):
    """Dialog for entering a raise.

    The amount the user enters is the RAISE itself — the chips they put in
    ON TOP of what it costs to call. Example: if to_call is $2 and the
    player raises $6, their total commitment this round is $8.

    The dialog's `get_value()` returns the total commitment (call + raise),
    matching what the game loop expects to add to the player's round bet.

    `min_raise_above` is enforced to be at least the previous raise size
    (No-Limit minimum-raise rule), passed in by the caller.
    """

    def __init__(self, to_call, min_raise_above, max_raise_above, pot,
                 parent=None, bb_amount=2, prev_raise_size=0):
        super().__init__(parent)
        self.setWindowTitle("Raise Amount")
        self.to_call = int(to_call)
        self.min_raise_above = int(min_raise_above)
        self.max_raise_above = int(max_raise_above)
        # Legacy aliases (in TOTAL commitment) so any old code reading these
        # still sees sensible bounds.
        self.min_raise = self.to_call + self.min_raise_above
        self.max_raise = self.to_call + self.max_raise_above
        self.pot = pot
        self.bb = bb_amount
        self.prev_raise_size = int(prev_raise_size)

        big_font = QFont('Arial', 18)
        big_bold = QFont('Arial', 20, QFont.Weight.Bold)
        btn_font = QFont('Arial', 16, QFont.Weight.Bold)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info label — stated in terms of the RAISE above the call
        info_text = (
            f"To call: ${self.to_call}   |  "
            f"Raise min: ${self.min_raise_above}   "
            f"max: ${self.max_raise_above}   |  "
            f"Pot: ${pot}   |  BB: ${bb_amount}"
        )
        if self.prev_raise_size > 0:
            info_text += f"   |  Prev raise: ${self.prev_raise_size}"
        info = QLabel(info_text)
        info.setFont(big_font)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        prompt = QLabel("Raise amount (above the call):")
        prompt.setFont(big_font)
        prompt.setStyleSheet("color: #bbb;")
        layout.addWidget(prompt)

        # Slider (values are the RAISE increment, NOT total commitment)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(self.min_raise_above)
        self.slider.setMaximum(self.max_raise_above)
        self.slider.setValue(self.min_raise_above)
        self.slider.setMinimumHeight(36)
        self.slider.valueChanged.connect(self.update_spinbox)
        layout.addWidget(self.slider)

        # Spinbox
        self.spinbox = QSpinBox()
        self.spinbox.setFont(big_bold)
        self.spinbox.setMinimum(self.min_raise_above)
        self.spinbox.setMaximum(self.max_raise_above)
        self.spinbox.setValue(self.min_raise_above)
        self.spinbox.setMinimumHeight(40)
        self.spinbox.valueChanged.connect(self.update_slider)
        layout.addWidget(self.spinbox)

        # Total-commitment preview (BIG, two lines)
        self.total_label = QLabel()
        self.total_label.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #ff0;")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.total_label)

        # Secondary "raise from previous bet" line
        self.raise_label = QLabel()
        self.raise_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        self.raise_label.setStyleSheet("color: #fc8;")
        self.raise_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.raise_label)
        self._refresh_total_label(self.min_raise_above)

        # BB multiplier buttons — interpreted as raise-above-call in BBs
        bb_layout = QHBoxLayout()
        bb_label = QLabel("Raise = N × BB:")
        bb_label.setFont(big_font)
        bb_layout.addWidget(bb_label)
        for mult in [2, 3, 4, 5, 10]:
            val = max(self.min_raise_above,
                      min(self.max_raise_above, bb_amount * mult))
            btn = QPushButton(f"{mult}x")
            btn.setFont(btn_font)
            btn.setFixedSize(70, 44)
            btn.clicked.connect(lambda checked, v=val: self.set_value(v))
            bb_layout.addWidget(btn)
        bb_layout.addStretch()
        layout.addLayout(bb_layout)

        # Pot-based quick buttons — interpreted as raise = fraction of pot
        pot_layout = QHBoxLayout()
        pot_label = QLabel("Raise = pot fraction:")
        pot_label.setFont(big_font)
        pot_layout.addWidget(pot_label)
        for label, mult in [("1/4", 0.25), ("1/3", 0.333), ("1/2", 0.5),
                            ("2/3", 0.67), ("3/4", 0.75), ("Pot", 1.0),
                            ("All-In", None)]:
            btn = QPushButton(label)
            btn.setFont(btn_font)
            btn.setFixedSize(80, 44)
            if mult is None:
                btn.clicked.connect(
                    lambda checked, v=self.max_raise_above: self.set_value(v))
            else:
                val = max(self.min_raise_above,
                          min(self.max_raise_above, int(pot * mult)))
                btn.clicked.connect(lambda checked, v=val: self.set_value(v))
            pot_layout.addWidget(btn)
        pot_layout.addStretch()
        layout.addLayout(pot_layout)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        for b in buttons.buttons():
            b.setFont(btn_font)
            b.setMinimumHeight(40)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_total_label(self, raise_above):
        raise_above = int(raise_above)
        total = self.to_call + raise_above
        # New TOTAL bet = my prior bet_in_round (caller fold) + total this turn.
        # We don't have my prior bet_in_round here; the caller passes pot + to_call,
        # but the meaningful poker quantity is the new "bet level" the table will
        # face — that equals my (prev bet_in_round) + total this turn. The dialog
        # only knows to_call (=current_bet - my bet_in_round) and the raise above
        # the call, so the "new bet level" = current_bet + raise_above. The caller
        # passes current_bet implicitly via to_call + my bet_in_round, but we want
        # to show:  Total bet (the level others now face) and the raise (above the
        # previous bet).  We approximate "previous bet" by current_bet, computable
        # as to_call + my contribution; what we always know precisely is that the
        # raise itself = raise_above and the total committed this turn = to_call +
        # raise_above. Show both clearly.
        self.total_label.setText(
            f"Total bet this round: ${total}"
        )
        self.raise_label.setText(
            f"Raise of ${raise_above} above the previous bet "
            f"(call ${self.to_call} + raise ${raise_above})"
        )

    def update_spinbox(self, value):
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        self._refresh_total_label(value)

    def update_slider(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._refresh_total_label(value)

    def set_value(self, raise_above):
        raise_above = max(self.min_raise_above,
                          min(self.max_raise_above, int(raise_above)))
        self.slider.setValue(raise_above)
        self.spinbox.setValue(raise_above)
        self._refresh_total_label(raise_above)

    def get_raise_above(self) -> int:
        """Return the raise amount chosen above the call."""
        return int(self.spinbox.value())

    def get_value(self) -> int:
        """Return the TOTAL commitment this round (call + raise)."""
        return self.to_call + int(self.spinbox.value())


# Claude model used for all annotations (per-hand critique, hand-log
# annotations, etc.). Opus 4.7 with extended thinking gives the best results
# for poker analysis at the cost of longer wall time.
CLAUDE_ANNOTATION_MODEL = 'claude-opus-4-7'


def _claude_invoke_args(prompt: str, *, mode: str = 'critique') -> list:
    """Build argv for the `claude` CLI to invoke Opus 4.7 with thinking.

    `mode` is informational only — both modes use the same model and
    thinking flag; the prompt itself encodes the desired output shape.

    NOTE: the CLI's `--thinking` option takes a value (enabled/adaptive/
    disabled), so it MUST be passed as `--thinking enabled`, not bare.
    """
    return [
        'claude', '-p',
        '--model', CLAUDE_ANNOTATION_MODEL,
        '--thinking', 'enabled',
        '--max-turns', '1',
        # JSON output so the caller can parse `modelUsage` and surface
        # a friendly model label ("Claude Opus 4.7 — Hero" rather than
        # the bare "Claude").
        '--output-format', 'json',
        prompt,
    ]


class ClaudeAnalysisThread(QThread):
    """Runs one or more Claude CLI calls off the GUI thread.

    Emits `progress(done, total, label)` as each POV completes and
    `finished_analyses(list-of-dicts)` with items
    {'player': str, 'seat': int, 'text': str}.

    Supports two modes:
      mode='critique' — short per-POV critique (default, used by hand summary).
      mode='annotate' — chess-engine-style annotations for the action log
        keyed by line index; output is a JSON-shaped string the caller parses.
    """

    progress = pyqtSignal(int, int, str)
    finished_analyses = pyqtSignal(list)

    def __init__(self, hand_text: str, povs: list, parent=None, *,
                 mode: str = 'critique', retro_word_limit: int = 80):
        """
        Args:
            hand_text: The full hand log to critique / annotate.
            povs: list of {'name': str, 'seat': int} — one per POV to analyze.
                  For single-player use a single entry like
                  [{'name': 'Hero', 'seat': 0}].
            mode: 'critique' (default) or 'annotate'.
            retro_word_limit: word ceiling for the RETROSPECTIVE block in
                annotate mode. Caller scales by hand-loss severity so a
                bad beat triggers a longer post-mortem (more help when
                the player needs it) and a small loss / win stays
                terse.
        """
        super().__init__(parent)
        self._hand_text = hand_text
        self._povs = list(povs)
        self._cancelled = False
        self._mode = mode
        self._retro_word_limit = max(40, int(retro_word_limit))

    def cancel(self):
        self._cancelled = True

    def _build_prompt(self, name: str) -> str:
        if self._mode == 'annotate':
            return (
                "You are a poker coach producing chess-engine-style "
                "annotations on a poker hand.\n\n"
                "CRITICAL: the log lists every player's known hole cards "
                "in a 'Hands (known)' header. The line tagged 'HERO' is "
                f"the hero ({name}) — every other 'Hands' entry is a "
                "villain. NEVER attribute a villain's hand to the hero or "
                "vice-versa. If you describe what someone has on a given "
                "street, use ONLY the cards listed for THAT player plus "
                "the board cards listed for that street.\n\n"
                "OUTPUT FORMAT — strictly two sections:\n\n"
                "(1) Per-action annotations.  Pick the action lines you "
                "want to comment on and emit ONE line each of the form:\n"
                "  N. <one-sentence comment, optionally with !/!?/?!/? marker>\n"
                "where N is the EXACT integer printed at the start of "
                "the action line in the log below — copy it verbatim.\n"
                "Do NOT renumber.  Do NOT use a hero-only sequence "
                "(1,2,3,4 for the four hero actions).  If hero acts on "
                f"action 3 and again on action 10, the two annotations "
                "must start with '3.' and '10.' respectively.\n"
                "Use markers sparingly: ! = strong play, !? = interesting, "
                "?! = dubious, ? = mistake. Comment ONLY on action lines "
                f"taken by {name} (the hero) — skip villain actions, "
                "blinds, dealing, and board reveals.\n\n"
                "(2) After all per-action annotations, on a NEW line, "
                "output the literal marker:\n"
                "  RETROSPECTIVE:\n"
                "Then a SEPARATE perfect-hindsight paragraph for EACH "
                "street the hand reached, each prefixed by its own "
                "literal STREET[<name>]: marker on its own line. "
                "Streets that weren't played (e.g. hand folded preflop) "
                "MUST be omitted entirely — do not emit a STREET[] "
                "marker for them.\n\n"
                "Format EXACTLY like this (omit any unreached street):\n"
                "  STREET[Preflop]:\n"
                f"  <hindsight on {name}'s preflop play, 1 short paragraph>\n"
                "  STREET[Flop]:\n"
                f"  <hindsight on {name}'s flop play, 1 short paragraph>\n"
                "  STREET[Turn]:\n"
                f"  <hindsight on {name}'s turn play, 1 short paragraph>\n"
                "  STREET[River]:\n"
                f"  <hindsight on {name}'s river play, 1 short paragraph>\n\n"
                "Each paragraph has FULL hindsight — everyone's hole "
                "cards, made-hand classes, and equity on that street "
                "are visible to you. For each street the hero acted on:\n"
                f"  • Was {name}'s decision correct given what could "
                "be known at the table on that street?\n"
                "  • What does the hindsight view (full information) "
                f"reveal that {name} couldn't see?\n"
                "  • One concrete takeaway for the next similar spot.\n\n"
                f"Total budget across all street paragraphs: "
                f"≤{self._retro_word_limit} words. Allocate roughly "
                "evenly across the streets the hand reached, but spend "
                "more on the pivotal street (biggest decision or "
                f"biggest equity swing for {name}). Plain text only, "
                "no preamble, no markdown — just short paragraphs "
                "under each STREET[] marker.\n\n"
                f"Annotate from {name}'s perspective. Hand log:\n\n"
                f"{self._hand_text}"
            )
        # Default: critique
        return (
            f"Critique this poker hand from {name}'s perspective "
            f"(3 sentences max). Was {name}'s play correct? "
            f"What was {name}'s key decision? "
            "Plain text only, no markdown.\n\n"
            f"{self._hand_text}"
        )

    def run(self):
        import shutil
        import subprocess
        import json as _json

        results = []
        total = max(1, len(self._povs))
        if not shutil.which('claude'):
            # No Claude available — emit empty list, caller falls back cleanly.
            self.finished_analyses.emit([])
            return

        for i, pov in enumerate(self._povs):
            if self._cancelled:
                break
            name = pov.get('name', 'Hero')
            seat = pov.get('seat', -1)
            self.progress.emit(i, total, f"Analyzing for {name}…")

            prompt = self._build_prompt(name)
            text = ""
            model_label = ""
            try:
                # Opus 4.7 with --thinking can take a while; bump the timeout.
                result = subprocess.run(
                    _claude_invoke_args(prompt, mode=self._mode),
                    capture_output=True, text=True, timeout=240,
                )
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        payload = _json.loads(result.stdout)
                        text = (payload.get('result') or '').strip()
                        model_label = self._friendly_model_label(
                            payload.get('modelUsage') or {})
                    except Exception:
                        # Fall back to raw stdout if JSON parsing fails.
                        text = result.stdout.strip()
                if not text or len(text) <= 10:
                    err_first = ''
                    if result.stderr:
                        err_first = result.stderr.strip().splitlines()[0]
                    detail = f"exit={result.returncode}"
                    if err_first:
                        detail += f"; {err_first[:160]}"
                    text = f"(claude failed: {detail})"
            except subprocess.TimeoutExpired:
                text = "(claude timed out after 240s)"
            except Exception as ex:
                text = f"(analysis failed: {ex})"
            results.append({
                'player': name, 'seat': seat,
                'text': text, 'model': model_label,
            })
            self.progress.emit(i + 1, total, f"Finished {name}")

        self.finished_analyses.emit(results)

    @staticmethod
    def _friendly_model_label(model_usage: dict) -> str:
        """Pick the dominant model from `modelUsage` and prettify the
        slug, e.g. 'claude-haiku-4-5-20251001' -> 'Claude Haiku 4.5'."""
        if not model_usage:
            return ""

        def _score(entry):
            if not isinstance(entry, dict):
                return 0
            return (int(entry.get('inputTokens') or 0)
                    + int(entry.get('outputTokens') or 0)
                    + int(entry.get('cacheReadInputTokens') or 0)
                    + int(entry.get('cacheCreationInputTokens') or 0))

        slug = max(model_usage.keys(), key=lambda k: _score(model_usage[k]))
        # Strip an "[1m]"-style suffix and the trailing -YYYYMMDD date.
        core = slug.split('[', 1)[0]
        parts = core.split('-')
        if parts and parts[-1].isdigit() and len(parts[-1]) == 8:
            parts = parts[:-1]
        # parts now look like e.g. ['claude', 'haiku', '4', '5'] or
        # ['claude', 'opus', '4', '7'].  Re-emit with title case and
        # join the trailing version digits with a dot.
        if len(parts) >= 4 and parts[0] == 'claude':
            family = parts[1].title()
            ver = '.'.join(parts[2:])
            return f"Claude {family} {ver}"
        # Fallback: just title-case the slug.
        return ' '.join(p.title() for p in parts) or slug


# --- Main Game Window ---
class PokerWindow(QMainWindow):
    """Main window for the poker game."""

    def __init__(self, god_mode=False, show_stats=False):
        super().__init__()
        self.god_mode = god_mode
        self.show_stats = show_stats
        self.hand_assists_used = {}

        self.setWindowTitle("PokerIQ")
        self.setMinimumSize(1200, 850)
        self.resize(1800, 1000)  # Good size for 1920x1080

        # Initialize QSettings for preferences persistence
        self.settings = QSettings("PokerIQ", "PokerIQ")

        # Hero stays at seat 0; the five bot personalities are placed
        # at random across seats 1..5 every launch so the player has
        # to identify each one by play, not by table position.
        self.players = (
            [Player("Hero (You)", "human")]
            + [Player(name, style)
               for name, style in _make_random_bot_lineup()]
        )

        # Store original names and styles for restoring defaults
        self.original_player_info = {
            i: (p.name, p.style) for i, p in enumerate(self.players)
        }

        # Load and apply bot preferences for each seat
        self.bot_preferences = {}  # seat -> bot_type_id
        self._load_bot_preferences()
        self._apply_bot_preferences()

        self.deck = eval7.Deck()
        self.board = []
        self.pot = 0
        self.dealer_idx = 0
        self.current_bet = 0
        self.street_idx = 0
        self.current_player_idx = 0
        self.waiting_for_human = False
        self._hero_folded_spectating = False
        self._spectator_continue_all = False
        self._spectator_waiting = False
        self.last_raiser = -1
        self.raises_this_round = 0
        self.action_log = []
        self.action_history = []  # For Theory of Mind tracking
        self.hand_number = 0
        self.at_showdown = False
        self.blind_level = 0  # Index into BLIND_LEVELS

        # Cache for equity calculations to prevent flickering
        self.equity_cache = {}
        self.equity_cache_key = None

        # Range accuracy tracking
        self.final_range_estimates = {}  # player_name -> range_dict at hand end
        self.range_accuracy_stats = {'hits': 0, 'misses': 0, 'total_hands': 0}

        # Preferences - load from settings with defaults
        self.use_visible_cards_only = self.settings.value("use_visible_cards_only", True, type=bool)
        self.legacy_colors = self.settings.value("legacy_colors", False, type=bool)
        # When enabled, after the hero has won at least one game against
        # the default bots, subsequent games randomly seat bots from the
        # combined pool (defaults + advanced poker_iq bots).  Preserves
        # the hero's per-seat preferences when set to a specific bot.
        self.randomize_bots_enabled = self.settings.value(
            "randomize_bots_enabled", True, type=bool)
        # Persistent flag: has the hero won a game against the default
        # bot lineup yet?  Once true, the random pool unlocks.
        self.beat_defaults_unlocked = self.settings.value(
            "beat_defaults_unlocked", False, type=bool)
        # Track each hand's winners so we can flip the unlock flag once
        # the hero claims a "game" win (currently: any session in which
        # the hero ends as the last player with chips).
        self._apply_color_preference()

        # Hand history tracking for interpretation
        self.hand_history = {
            'hero_cards': [],
            'hero_actions': [],
            'street_equities': {},  # street -> hero equity
            'key_events': [],
            'board_by_street': {}
        }

        # Initialize log file
        self.log_filename = f"poker_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.init_logfile()

        # Network state
        self.network_server = None  # PokerServer instance if hosting
        self.network_client = None  # PokerClient instance if joined
        self.network_mode = None    # 'host' or 'client' or None
        self.my_seat = None         # Our seat index in network game
        self.waiting_for_network_action = False
        self.network_human_seats = set()  # Seats controlled by remote players

        self.setup_ui()

    def init_logfile(self):
        """Initialize the log file with header."""
        with open(self.log_filename, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("POKER LEARNING GAME - SESSION LOG\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

        # WSOP-2008-Bracelets-style cumulative stats (logged to the file
        # so the post-game annotation has the same per-player and
        # per-hole-card breakdowns the bracelets pause menu shows).
        self._table_stats = {}     # {player_name: {hands_played, hands_won,
                                   #               showdowns_seen, showdowns_won, all_ins}}
        self._hole_card_stats = {} # {class_label: {hands_seen, hands_played,
                                   #                hands_won, hands_lost,
                                   #                cash_gained, cash_lost, net_cash}}
                                   # tracked from the local hero's POV
        # Per-player × 169-hand history. Used by the Gordon-style 169
        # heatmap on each player's Theory-of-Mind tab and by the
        # range-narrowing logic that adjusts each opponent's estimated
        # range using what they've actually done this session.
        # Shape: {player_name: {hand_key: {seen, played (vpip),
        # raised (pfr), called, folded, won, lost, net_cash}}}
        # hand_key uses the canonical 169-grid notation: "AA", "AKs",
        # "72o", etc. (see _hand_class).
        self._player_169_history = {}
        # Per-player VPIP/PFR cache for the CURRENT hand, so we only
        # bump VPIP/PFR once per player per hand even if they take
        # multiple actions on a street.
        self._hand_vpip_seen = set()    # names that voluntarily put $ in this hand
        self._hand_pfr_seen = set()     # names that raised preflop this hand
        self._game_status_logged = False
        self._original_player_count = None  # filled in on first deal_hand
        self._original_blinds = None
        self._current_hero_hand_class = None
        self._current_hero_starting_stack = None
        self._all_in_seen_this_hand = set()  # names that went all-in this hand
        self._hand_in_progress = False  # gates re-clicks of "New Hand"

    @staticmethod
    def _fresh_table_stats() -> dict:
        return {
            'hands_played': 0,
            'hands_won': 0,
            'showdowns_seen': 0,
            'showdowns_won': 0,
            'all_ins': 0,
        }

    @staticmethod
    def _fresh_hole_class_stats() -> dict:
        return {
            'hands_seen': 0,
            'hands_played': 0,
            'hands_won': 0,
            'hands_lost': 0,
            'cash_gained': 0,
            'cash_lost': 0,
            'net_cash': 0,
        }

    @staticmethod
    def _fresh_169_cell() -> dict:
        """One entry in the per-player 169-grid history."""
        return {
            'seen': 0,      # times dealt this combo
            'played': 0,    # voluntarily put $ in (VPIP)
            'raised': 0,    # raised preflop with this combo (PFR)
            'called': 0,    # called (not raised) preflop
            'folded': 0,    # folded preflop
            'won': 0,       # hand resulted in a win
            'lost': 0,      # showed down and lost, OR folded after putting $ in
            'net_cash': 0,  # cumulative chip delta over all instances
        }

    def _bump_169_seen(self, player_name: str, hand_key: str):
        bucket = self._player_169_history.setdefault(player_name, {})
        bucket.setdefault(hand_key, self._fresh_169_cell())['seen'] += 1

    def _bump_169_action(self, player_name: str, hand_key: str,
                        action: str, street: str):
        """Bump VPIP / PFR / called / folded counters once per hand per
        player. action ∈ {'f','c','r'}, street ∈ STREETS. Only preflop
        actions feed the heatmap counters; later-street actions feed
        the range-narrowing logic separately."""
        if not hand_key or hand_key == "??":
            return
        bucket = self._player_169_history.setdefault(player_name, {})
        cell = bucket.setdefault(hand_key, self._fresh_169_cell())
        if street == 'Preflop':
            if action == 'r' and player_name not in self._hand_pfr_seen:
                cell['raised'] += 1
                self._hand_pfr_seen.add(player_name)
                if player_name not in self._hand_vpip_seen:
                    cell['played'] += 1
                    self._hand_vpip_seen.add(player_name)
            elif action == 'c' and player_name not in self._hand_vpip_seen:
                # Only count a CALL as VPIP if the player actually faced
                # a bet to call. Posting the BB and then checking is not
                # VPIP. Caller filters this via to_call > 0.
                cell['called'] += 1
                cell['played'] += 1
                self._hand_vpip_seen.add(player_name)
            elif action == 'f':
                # Only count fold if they hadn't already voluntarily
                # entered the pot. A fold to a re-raise after limping
                # already shows up as 'played'.
                if player_name not in self._hand_vpip_seen:
                    cell['folded'] += 1

    def _bump_169_outcome(self, player_name: str, hand_key: str,
                         net_cash: int, won: bool):
        if not hand_key or hand_key == "??":
            return
        bucket = self._player_169_history.setdefault(player_name, {})
        cell = bucket.setdefault(hand_key, self._fresh_169_cell())
        cell['net_cash'] += int(net_cash)
        if won:
            cell['won'] += 1
        elif net_cash < 0:
            cell['lost'] += 1

    @staticmethod
    def _hand_class(hand) -> str:
        """Return canonical 169-class hole-card label like 'AA', 'AKs', 'AKo'."""
        if not hand or len(hand) < 2:
            return "??"
        c1, c2 = str(hand[0]), str(hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        order = '23456789TJQKA'
        a, b = sorted([r1, r2], key=lambda r: order.index(r), reverse=True)
        if r1 == r2:
            return f"{a}{a}"
        return f"{a}{b}{'s' if s1 == s2 else 'o'}"

    def _record_hand_start_stats(self):
        """Bump per-player hands_played and per-hole-class hands_seen for
        the local hero. Called from deal_hand."""
        # Reset per-hand VPIP/PFR caches.
        self._hand_vpip_seen = set()
        self._hand_pfr_seen = set()
        for p in self.players:
            if p.active:
                self._table_stats.setdefault(
                    p.name, self._fresh_table_stats()
                )['hands_played'] += 1
                # Every player (not just hero) gets a 169-grid 'seen'
                # bump — used by the per-player heatmap.
                if p.hand:
                    self._bump_169_seen(p.name, self._hand_class(p.hand))
        hero_seat = self.my_seat if self.my_seat is not None else 0
        if 0 <= hero_seat < len(self.players):
            hero = self.players[hero_seat]
            if hero.hand:
                cls = self._hand_class(hero.hand)
                s = self._hole_card_stats.setdefault(
                    cls, self._fresh_hole_class_stats())
                s['hands_seen'] += 1
                # "Played" in bracelets = the hand actually got into action
                # rather than a fold-without-acting; we tally it once the
                # hand ends and the hero made it past preflop. Track the
                # entry stack here so we can compute cash delta later.
                self._current_hero_hand_class = cls
                self._current_hero_starting_stack = int(hero.stack)
        self._all_in_seen_this_hand = set()
        # Snapshot every player's starting stack so we can compute
        # per-player net_cash deltas for the 169 history at hand end.
        self._169_starting_stacks = {
            p.name: int(p.stack) for p in self.players
        }

    def _record_all_in(self, player_name: str):
        """Bump all_ins count for player_name (called from action handlers
        when a player ends an action with stack==0)."""
        if player_name in self._all_in_seen_this_hand:
            return
        self._all_in_seen_this_hand.add(player_name)
        self._table_stats.setdefault(
            player_name, self._fresh_table_stats()
        )['all_ins'] += 1

    def _finalize_hand_stats(self, winners_names, showdown_active_names):
        """Bump hands_won / showdowns at end of hand; update hero hole-class
        cash delta + win/loss; called from end_hand / _on_hand_ended."""
        for n in winners_names or []:
            self._table_stats.setdefault(
                n, self._fresh_table_stats()
            )['hands_won'] += 1
        for n in showdown_active_names or []:
            ts = self._table_stats.setdefault(n, self._fresh_table_stats())
            ts['showdowns_seen'] += 1
            if n in (winners_names or []):
                ts['showdowns_won'] += 1
        # Hero hole-card cash delta
        cls = getattr(self, '_current_hero_hand_class', None)
        start_stack = getattr(self, '_current_hero_starting_stack', None)
        if cls and start_stack is not None:
            hero_seat = self.my_seat if self.my_seat is not None else 0
            if 0 <= hero_seat < len(self.players):
                hero = self.players[hero_seat]
                delta = int(hero.stack) - int(start_stack)
                s = self._hole_card_stats.setdefault(
                    cls, self._fresh_hole_class_stats())
                s['hands_played'] += 1
                if delta >= 0:
                    s['cash_gained'] += delta
                    if delta > 0:
                        s['hands_won'] += 1
                else:
                    s['cash_lost'] += -delta
                    s['hands_lost'] += 1
                s['net_cash'] = s['cash_gained'] - s['cash_lost']
        self._current_hero_hand_class = None
        self._current_hero_starting_stack = None

        # Per-player 169-grid outcome bump. Done for EVERY player who
        # had a hand this round, so each opponent's heatmap can show
        # which combos they've won / lost with this session.
        starting = getattr(self, '_169_starting_stacks', {}) or {}
        winner_set = set(winners_names or [])
        for p in self.players:
            if not p.hand:
                continue
            key = self._hand_class(p.hand)
            start = starting.get(p.name, p.stack)
            delta = int(p.stack) - int(start)
            self._bump_169_outcome(p.name, key, delta,
                                   won=(p.name in winner_set))

    def _log_game_status(self):
        """Write the bracelets-style GAME STATUS block at the start of the
        session so post-game annotation knows what kind of game was played."""
        sb, bb = BLIND_LEVELS[self.blind_level]
        next_increase_in = HANDS_PER_BLIND_LEVEL - (self.hand_number % HANDS_PER_BLIND_LEVEL)
        if next_increase_in == HANDS_PER_BLIND_LEVEL:
            next_increase_in = 0
        next_marker = (f"Hand #{self.hand_number + next_increase_in}"
                       if self.blind_level < len(BLIND_LEVELS) - 1
                       else "Max blinds reached")
        if self._original_player_count is None:
            self._original_player_count = sum(1 for p in self.players if p.stack > 0)
            self._original_blinds = (sb, bb)
        current_players = sum(1 for p in self.players if p.stack > 0)
        mode_label = "PokerIQ Local"
        if self.network_mode == "host":
            mode_label = "PokerIQ Network (Host)"
        elif self.network_mode == "client":
            mode_label = "PokerIQ Network (Client)"
        self.write_log("\n=== GAME STATUS ===")
        self.write_log(f"  Game Name: {mode_label}")
        self.write_log("  Game Type: Texas Hold 'em")
        self.write_log("  Limit Type: No Limit")
        self.write_log(f"  Starting Chips: ${STARTING_STACK}")
        self.write_log(f"  Hands Dealt: {self.hand_number}")
        self.write_log(f"  Next Blind Increase: {next_marker}")
        self.write_log(f"  # Players (Original/Current): "
                       f"{self._original_player_count}/{current_players}")
        ob = self._original_blinds or (sb, bb)
        self.write_log(f"  Blinds (Original/Current): "
                       f"${ob[0]}/${ob[1]} → ${sb}/${bb}")
        self.write_log("  Ante: None")
        self.write_log("  Limits: N/A")
        self.write_log("===================\n")

    def _log_chip_count(self):
        """Bracelets CHIP COUNT screen — current stacks for every seat."""
        self.write_log("--- CHIP COUNT ---")
        for p in self.players:
            self.write_log(f"  {p.name}: ${p.stack}")

    def _log_table_stats(self):
        """Bracelets TABLE STATS screen — cumulative per-player counters."""
        self.write_log("\n=== TABLE STATS ===")
        self.write_log(
            "  {:<16} {:>10} {:>14} {:>11} {:>20} {:>9}".format(
                "Name", "Status", "Hands Played", "Hands Won",
                "Showdowns W/Total", "All Ins"))
        for p in self.players:
            ts = self._table_stats.get(p.name, self._fresh_table_stats())
            self.write_log(
                "  {:<16} {:>10} {:>14} {:>11} {:>20} {:>9}".format(
                    p.name[:16],
                    f"${p.stack}",
                    ts['hands_played'],
                    ts['hands_won'],
                    f"{ts['showdowns_won']}/{ts['showdowns_seen']}",
                    ts['all_ins']))
        self.write_log("===================\n")

    def _log_hole_card_stats(self):
        """Bracelets HOLE CARD STATS — hero's per-starting-hand breakdown,
        sorted by net cash descending."""
        if not self._hole_card_stats:
            return
        self.write_log("\n=== HOLE CARD STATS (Hero) ===")
        self.write_log(
            "  {:<5} {:>5} {:>7} {:>5} {:>5} {:>13} {:>11} {:>9}".format(
                "Hand", "Seen", "Played", "Won", "Lost",
                "Cash Gained", "Cash Lost", "Net"))
        rows = sorted(self._hole_card_stats.items(),
                      key=lambda kv: (-kv[1]['net_cash'], kv[0]))
        for cls, s in rows:
            self.write_log(
                "  {:<5} {:>5} {:>7} {:>5} {:>5} {:>13} {:>11} {:>9}".format(
                    cls,
                    s['hands_seen'],
                    s['hands_played'],
                    s['hands_won'],
                    s['hands_lost'],
                    f"${s['cash_gained']}",
                    f"${s['cash_lost']}",
                    f"${s['net_cash']:+d}"))
        self.write_log("============================\n")

    def _log_session_summary(self):
        """Dump TABLE STATS + HOLE CARD STATS at session end (close)."""
        try:
            self.write_log("\n" + "#" * 60)
            self.write_log("SESSION SUMMARY")
            self.write_log("#" * 60)
            self._log_table_stats()
            self._log_hole_card_stats()
            self._log_chip_count()
            self.write_log(
                f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as ex:
            print(f"[log] session summary failed: {ex}")

    # Bump this every time the default lineup changes meaning. When the
    # saved version is older than this, _load_bot_preferences wipes any
    # per-seat overrides — otherwise stale "tom"-on-every-seat configs
    # from older sessions keep producing duplicate lineups even after we
    # ship a new default.
    BOT_PREFS_SCHEMA_VERSION = 4

    def _load_bot_preferences(self):
        """Load bot preferences from QSettings.

        If the saved schema version is older than BOT_PREFS_SCHEMA_VERSION
        — or missing entirely — the per-seat overrides are dropped and the
        default lineup applies. Avoids leaving the user with a stale
        config that resolves multiple seats to the same character (the
        "5 × Fluid Fiona" problem).
        """
        saved_version = 0
        try:
            saved_version = int(self.settings.value(
                "bot_preference/schema_version", 0) or 0)
        except (ValueError, TypeError):
            saved_version = 0

        if saved_version < self.BOT_PREFS_SCHEMA_VERSION:
            # Wipe any per-seat overrides — the new schema's default
            # lineup is what we want them to see.
            try:
                self.settings.beginGroup("bot_preference")
                for k in self.settings.allKeys():
                    self.settings.remove(k)
                self.settings.endGroup()
            except Exception:
                pass
            for seat in range(len(self.players)):
                self.bot_preferences[seat] = "default"
            self.settings.setValue(
                "bot_preference/schema_version",
                self.BOT_PREFS_SCHEMA_VERSION)
            self.settings.sync()
            return

        for seat in range(len(self.players)):
            key = f"bot_preference/seat_{seat}"
            bot_type_id = self.settings.value(key, "default")
            self.bot_preferences[seat] = bot_type_id

    def _apply_color_preference(self):
        """Apply the legacy colors preference to the global flag."""
        global _use_legacy_colors
        _use_legacy_colors = self.legacy_colors

    def _capture_street_stats(self, street):
        """Capture player stats for the hand summary display.
        Always calculates true equities (actual hands vs each other) since the
        summary is shown after the hand ends when all cards are known.
        """
        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'players': self.players,
            'current_bet': self.current_bet
        }

        # Calculate true equities using actual hands (not random opponents)
        true_equities = {}
        active_hands = [(p, p.hand) for p in self.players if p.active and p.hand]
        if active_hands:
            true_equities = calc_multiway_equity(
                active_hands,
                [str(c) for c in self.board],
                iterations=500
            )

        stats = []
        for p in self.players:
            if p.hand:
                perceived_equity, pot_odds, _ = p.calculate_current_stats(game_state, False)
                true_equity = true_equities.get(p, 0.0)
                stats.append((p.name, true_equity, perceived_equity, pot_odds, p.active, p.style == 'human'))
            else:
                stats.append((p.name, None, 0, 0, p.active, p.style == 'human'))

        self.hand_history['street_stats'][street] = stats

        # Also capture the board state at end of this street
        if street not in self.hand_history['board_by_street']:
            self.hand_history['board_by_street'][street] = [str(c) for c in self.board]

        # Capture pot size at the END of this street so the hand summary's
        # stats panel can show "Pot after Flop = $X" etc.
        if 'pot_by_street' not in self.hand_history:
            self.hand_history['pot_by_street'] = {}
        self.hand_history['pot_by_street'][street] = int(self.pot)

    def _save_bot_preferences(self):
        """Save bot preferences to QSettings."""
        for seat, bot_type_id in self.bot_preferences.items():
            key = f"bot_preference/seat_{seat}"
            self.settings.setValue(key, bot_type_id)
        self.settings.sync()

    def _apply_bot_preferences(self):
        """Apply bot preferences to all players.

        Two seats can end up with the same saved bot_type_id (e.g. both
        configured to 'tom' in different sessions), which previously
        rendered both as identical "Fluid Fiona" panels. We track the
        names we've already used in this pass and disambiguate by
        suffixing a seat number when a collision would happen.
        """
        # Every built-in style uses its own bot_type_id in BOT_CUTE_NAMES;
        # listing them here keeps the per-seat-pref override path in
        # sync with the lineup. New styles (shark / exploit / icm)
        # were missing from the previous map, so a saved preference
        # for them silently fell through to default behaviour.
        style_map = {
            "optimal": "optimal", "tight": "tight", "loose": "loose",
            "aggressive": "aggressive", "tom": "tom",
            "shark": "shark", "exploit": "exploit", "icm": "icm",
        }

        used_names = set()

        def _disambiguate(name: str, seat: int) -> str:
            """If `name` is already used, suffix the seat number; else
            claim it. We deliberately don't pull from a pool of fake
            alternative names — two seats of the same style ARE the
            same approach, and the user should see that they
            configured a duplicate rather than be presented with two
            distinct-looking characters that play identically. The
            canonical fix for "I want five different approaches" is
            View → "Reset bots to default lineup" or just configuring
            five different bot types."""
            if name not in used_names:
                used_names.add(name)
                return name
            cand = f"{name} (#{seat + 1})"
            used_names.add(cand)
            return cand

        for seat, player in enumerate(self.players):
            if seat in self.original_player_info and self.original_player_info[seat][1] == 'human':
                used_names.add(player.name)
                continue

            bot_type_id = self.bot_preferences.get(seat, "default")

            if bot_type_id == "default":
                if seat in self.original_player_info:
                    orig_name, orig_style = self.original_player_info[seat]
                    player.name = _disambiguate(orig_name, seat)
                    player.style = orig_style
                player.clear_piq_bot()
            elif bot_type_id.startswith("piq_"):
                base = BOT_CUTE_NAMES.get(bot_type_id) or "Engine Bot"
                player.name = _disambiguate(base, seat)
                player.set_piq_bot(bot_type_id, seat)
            else:
                if bot_type_id in style_map:
                    player.style = style_map[bot_type_id]
                    base = BOT_CUTE_NAMES.get(bot_type_id) or bot_type_id
                    player.name = _disambiguate(base, seat)
                player.clear_piq_bot()

    def reset_bots_to_default_lineup(self):
        """Wipe every saved per-seat preference and re-shuffle bots.

        Applies a fresh random arrangement of the canonical five
        personalities across seats 1..5 (hero stays at seat 0), so
        the user effectively gets a "deal me a new lineup" button.
        Persists the cleared prefs to QSettings so the next launch
        starts clean too.
        """
        # Apply a freshly shuffled lineup to the in-memory players.
        shuffled = _make_random_bot_lineup()
        for seat, (name, style) in enumerate(shuffled, start=1):
            if 0 <= seat < len(self.players):
                self.players[seat].name = name
                self.players[seat].style = style
                self.players[seat].clear_piq_bot()

        # Refresh original_player_info so future "default" preference
        # restores hit the canonical lineup, and clear saved overrides.
        self.original_player_info = {
            i: (p.name, p.style) for i, p in enumerate(self.players)
        }
        self.bot_preferences = {}
        try:
            self.settings.beginGroup('bot_preferences')
            for k in self.settings.allKeys():
                self.settings.remove(k)
            self.settings.endGroup()
            self.settings.sync()
        except Exception:
            pass

        # Refresh visible labels.
        self._apply_bot_preferences()
        try:
            for seat, panel in self.player_panels:
                panel.update_display()
        except Exception:
            pass
        try:
            self.update_theory_of_mind()
        except Exception:
            pass

    def get_bot_type_display_name(self, bot_type_id: str) -> str:
        """Get display name for a bot type ID."""
        if bot_type_id in BOT_TYPE_MAP:
            return BOT_TYPE_MAP[bot_type_id][0]
        return bot_type_id

    def _maybe_randomize_bots_for_game(self):
        """If the hero has beaten the default bots at least once and the
        randomize-bots option is enabled, randomly select a fresh bot for
        each non-human seat at the start of a new game. Picks from the
        combined pool of default styles + advanced poker_iq bots.

        Only seats whose preference is "default" get re-rolled — if the
        user has explicitly chosen a bot for a seat, we honor that.
        """
        if not getattr(self, 'randomize_bots_enabled', True):
            return
        if not getattr(self, 'beat_defaults_unlocked', False):
            return
        # Build the pool. Start with the original five styles.
        pool = ['optimal', 'tight', 'loose', 'aggressive', 'tom']
        if POKER_IQ_AVAILABLE:
            pool.extend(['piq_basic_equity', 'piq_improved_equity',
                         'piq_external_engine'])

        for seat, p in enumerate(self.players):
            if p.style == 'human':
                continue
            # Honor explicit per-seat preferences ('default' means
            # re-roll; anything else = stick with the user's choice).
            if self.bot_preferences.get(seat, 'default') != 'default':
                continue
            choice = random.choice(pool)
            self.bot_preferences[seat] = choice
            # Apply just this seat — don't disturb the rest.
        # Re-apply preferences in one pass so the player names/styles
        # update consistently.
        self._apply_bot_preferences()

    def hand_to_range_notation(self, hand):
        """Convert actual hole cards to PokerStove range notation."""
        if not hand or len(hand) < 2:
            return None
        c1, c2 = str(hand[0]), str(hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        ranks = 'AKQJT98765432'
        r1_idx = ranks.index(r1)
        r2_idx = ranks.index(r2)
        if r1_idx > r2_idx:
            r1, r2 = r2, r1
        if r1 == r2:
            return f"{r1}{r2}"
        elif s1 == s2:
            return f"{r1}{r2}s"
        else:
            return f"{r1}{r2}o"

    def check_range_accuracy(self, players, range_estimates):
        """Check if each player's actual hand was in their estimated range."""
        results = []
        for player in players:
            if player.style == 'human' or not player.hand:
                continue
            if player.name not in range_estimates:
                continue
            hand_notation = self.hand_to_range_notation(player.hand)
            if not hand_notation:
                continue
            range_dict = range_estimates[player.name]
            weight = range_dict.get(hand_notation, 0.0)
            in_range = weight >= 0.3
            self.range_accuracy_stats['total_hands'] += 1
            if in_range:
                self.range_accuracy_stats['hits'] += 1
                results.append(f"  {player.name}: {hand_notation} IN RANGE (weight={weight:.1%})")
            else:
                self.range_accuracy_stats['misses'] += 1
                results.append(f"  {player.name}: {hand_notation} NOT IN RANGE (weight={weight:.1%})")
        return results

    def closeEvent(self, event):
        """Flush bracelets-style cumulative stats + chip count to the log
        before the window closes so post-game annotation has the same
        per-player and per-hole-card breakdowns the WSOP-2008 pause menu
        shows."""
        try:
            self._log_session_summary()
        except Exception as ex:
            print(f"[log] session summary on close failed: {ex}")
        super().closeEvent(event)

    def write_log(self, msg, include_stats=False):
        """Write a message to the log file."""
        with open(self.log_filename, 'a') as f:
            f.write(f"{msg}\n")
            if include_stats and self.players:
                game_state = {
                    'board': [str(c) for c in self.board],
                    'pot': self.pot,
                    'players': self.players,
                    'current_bet': self.current_bet
                }
                f.write("  [STATS]\n")
                for p in self.players:
                    if p.active and p.hand:
                        use_god = True  # Log always shows true equity
                        equity, pot_odds, to_call = p.calculate_current_stats(game_state, use_god)
                        cards = format_cards(p.hand) if p.hand else "?? ??"
                        f.write(f"    {p.name:<15} Cards: {cards}  Equity: {equity:.1%}  PotOdds: {pot_odds:.1%}\n")

    def _get_current_hand_log(self):
        """Extract the current hand's log text from the log file."""
        try:
            with open(self.log_filename, 'r') as f:
                content = f.read()
            # Find the last HAND #N block
            import re
            blocks = re.split(r'(?=={60}\nHAND #\d+)', content)
            for block in reversed(blocks):
                if re.match(r'={60}\nHAND #', block):
                    return block.strip()
        except (OSError, IOError):
            pass
        return ""

    def _get_cached_hand_reflections(self):
        """Return the cached Claude annotation/reflection bundle for the
        current hand (``hand_number``), or None if nothing is cached.

        The cache is populated by ``_ensure_hand_reflections_thread``'s
        finished callback. Hand Summary and Hand Log share it so we
        only ever spend one Claude call per hand even when the user
        opens both dialogs.
        """
        cache = getattr(self, '_hand_reflection_cache', None) or {}
        return cache.get(int(getattr(self, 'hand_number', 0) or 0))

    def _ensure_hand_reflections_thread(self):
        """Start the per-hand annotate-mode Claude thread if it hasn't
        been started for this hand yet. Returns the running thread (so
        the caller can connect a one-shot listener to its
        ``finished_analyses`` signal) or ``None`` if Claude is
        unavailable / no log to analyse.
        """
        hand = int(getattr(self, 'hand_number', 0) or 0)
        if not hasattr(self, '_hand_reflection_threads'):
            self._hand_reflection_threads = {}
        if not hasattr(self, '_hand_reflection_cache'):
            self._hand_reflection_cache = {}
        existing = self._hand_reflection_threads.get(hand)
        if existing is not None:
            return existing
        if hand in self._hand_reflection_cache:
            return None  # already finished, nothing to subscribe to

        import shutil
        if not shutil.which('claude'):
            return None
        log_text = self._get_current_hand_log()
        if not log_text:
            return None

        hero_seat = self.my_seat if self.my_seat is not None else 0
        if not (0 <= hero_seat < len(self.players)):
            return None
        hero_name = self.players[hero_seat].name
        povs = [{'name': hero_name, 'seat': hero_seat}]

        loss_pct = self._compute_hero_loss_pct()
        retro_words = int(round(80 + 240 * max(0.0, min(1.0, loss_pct))))

        thread = ClaudeAnalysisThread(log_text, povs, mode='annotate',
                                       retro_word_limit=retro_words)
        self._hand_reflection_threads[hand] = thread

        def _on_finished(analyses):
            try:
                if not analyses:
                    self._hand_reflection_cache[hand] = {
                        'annotations': {},
                        'street_reflections': {},
                        'retrospective_raw': '',
                        'status': 'Claude returned no annotations.',
                    }
                else:
                    ann_text = (analyses[0].get('text', '') or '').strip()
                    actions_text, retro = self._split_retrospective(ann_text)
                    self._hand_reflection_cache[hand] = {
                        'annotations':
                            self._parse_claude_annotations(actions_text),
                        'street_reflections':
                            self._parse_per_street_retrospective(retro),
                        'retrospective_raw': retro,
                        'status': '',
                    }
            finally:
                self._hand_reflection_threads.pop(hand, None)
                try:
                    thread.deleteLater()
                except Exception:
                    pass

        thread.finished_analyses.connect(_on_finished)
        if not hasattr(self, '_claude_threads'):
            self._claude_threads = []
        self._claude_threads.append(thread)
        thread.start()
        return thread

    def _subscribe_summary_to_reflections(self, dialog):
        """Wire a ``HandSummaryDialog`` to the shared per-hand Claude
        thread so its yellow placeholders are replaced with real
        hindsight paragraphs as soon as the analysis finishes.

        Safe to call multiple times for the same hand — every dialog
        gets its own one-shot listener; the underlying thread is
        shared.
        """
        thread = self._ensure_hand_reflections_thread()
        if thread is None:
            cached = self._get_cached_hand_reflections() or {}
            try:
                dialog.set_street_reflections(
                    cached.get('street_reflections', {}),
                    status_text=cached.get('status') or
                    "Claude unavailable — no hindsight reflections.")
            except RuntimeError:
                pass
            return

        def _on_finished(analyses):
            cached = self._get_cached_hand_reflections() or {}
            try:
                dialog.set_street_reflections(
                    cached.get('street_reflections', {}),
                    status_text=cached.get('status') or '')
            except RuntimeError:
                pass
        thread.finished_analyses.connect(_on_finished)

    def _get_claude_hand_critique_sync(self, hand_text):
        """Get Claude critique of a poker hand synchronously.
        Returns critique text, or empty string if unavailable."""
        import shutil
        import subprocess

        try:
            if not shutil.which('claude'):
                return ""
            prompt = (
                "Briefly critique this poker hand (3 sentences max). "
                "Was Hero's play correct? What was the key decision? "
                "Plain text only, no markdown.\n\n"
                f"{hand_text}"
            )
            result = subprocess.run(
                _claude_invoke_args(prompt),
                capture_output=True, text=True, timeout=240
            )
            if result.returncode == 0 and len(result.stdout.strip()) > 10:
                critique = result.stdout.strip()
                self.write_log(f"\n  [CLAUDE ANALYSIS]\n  {critique}\n")
                return critique
        except Exception:
            pass
        return ""

    def setup_ui(self):
        # Menu bar (Network / Help) — by default the game runs single-player.
        # Network is opt-in via the Network menu.
        self._build_menubar()

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 10, 15, 10)

        # Top controls
        top_bar = QHBoxLayout()

        cb_style = """
            QCheckBox { font-size: 20px; spacing: 10px; }
            QCheckBox:disabled { color: #666; }
        """

        # God Mode / Show Tells policy:
        #   - Single-player (only bots): spectator-only — disabled
        #     pre-fold, auto-enabled when the hero folds. Cheating
        #     on bots is fine, but we don't want to default-on the
        #     assists.
        #   - Networked multi-human: enabled pre-fold but DECEPTIVE —
        #     a per-hand deception cache fakes 50–100 % of the
        #     other players' hole cards (hero's own stay accurate)
        #     so the toggle is unreliable for actual cheating
        #     against other humans. Spectator mode after a fold
        #     turns the deception off.
        # _refresh_assist_checkbox_state below picks the right
        # gating each time the network mode changes.
        self.god_mode = False
        self.god_mode_cb = QCheckBox("God Mode")
        self.god_mode_cb.setStyleSheet(cb_style)
        self.god_mode_cb.setChecked(False)
        self.god_mode_cb.setEnabled(False)
        self.god_mode_cb.stateChanged.connect(self.toggle_god_mode)
        top_bar.addWidget(self.god_mode_cb)

        top_bar.addSpacing(20)

        self.show_stats = False
        self.stats_cb = QCheckBox("Show Tells")
        self.stats_cb.setStyleSheet(cb_style)
        self.stats_cb.setChecked(False)
        self.stats_cb.setEnabled(False)
        self.stats_cb.stateChanged.connect(self.toggle_stats)
        top_bar.addWidget(self.stats_cb)

        top_bar.addSpacing(20)

        self.tom_cb = QCheckBox("Theory of Mind")
        self.tom_cb.setStyleSheet(cb_style)
        self.tom_cb.setChecked(False)
        self.tom_cb.stateChanged.connect(self.toggle_theory_of_mind)
        top_bar.addWidget(self.tom_cb)

        top_bar.addStretch()

        # Help button
        self.help_btn = QPushButton("Help")
        self.help_btn.setFixedSize(80, 40)
        self.help_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.help_btn.clicked.connect(self.show_help)
        top_bar.addWidget(self.help_btn)

        # About button
        self.about_btn = QPushButton("About")
        self.about_btn.setFixedSize(80, 40)
        self.about_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.about_btn.clicked.connect(self.show_about)
        top_bar.addWidget(self.about_btn)

        # Preferences button
        self.prefs_btn = QPushButton("Prefs")
        self.prefs_btn.setFixedSize(80, 40)
        self.prefs_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.prefs_btn.clicked.connect(self.show_preferences)
        top_bar.addWidget(self.prefs_btn)

        # Network button
        self.network_btn = QPushButton("Network")
        self.network_btn.setFixedSize(90, 40)
        self.network_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.network_btn.clicked.connect(self.show_network_dialog)
        if not NETWORK_AVAILABLE:
            self.network_btn.setEnabled(False)
            self.network_btn.setToolTip("Network module not available")
        top_bar.addWidget(self.network_btn)

        top_bar.addSpacing(10)

        self.new_hand_btn = QPushButton("New Hand")
        self.new_hand_btn.setFixedSize(130, 40)
        self.new_hand_btn.setStyleSheet("QPushButton { font-size: 15px; font-weight: bold; }")
        self.new_hand_btn.clicked.connect(self.deal_hand)
        # Disabled until a hand completes — the user shouldn't be able to
        # interrupt an in-flight hand by starting a new one. Enabled
        # initially so the very first hand can be dealt; toggled off in
        # deal_hand and back on in end_hand / _on_hand_ended.
        self.new_hand_btn.setEnabled(True)
        top_bar.addWidget(self.new_hand_btn)

        main_layout.addLayout(top_bar)

        # === Game Container (hidden when Theory of Mind is active) ===
        self.game_container = QWidget()
        game_container_layout = QVBoxLayout(self.game_container)
        game_container_layout.setContentsMargins(0, 0, 0, 0)

        # Game area
        game_layout = QHBoxLayout()

        # Left side - players 4 and 3 (clockwise: across from hero)
        left_panel = QVBoxLayout()
        left_panel.addStretch()
        self.player_panels = []

        for i in [4, 3]:
            panel = PlayerPanel(self.players[i], i)
            self.player_panels.append((i, panel))
            left_panel.addWidget(panel)
            # 50-px gap between Tim and Bruce (was 20). Some of the
            # vertical space recovered from the now-hidden empty
            # bet_label is spent here so the two left-column panels
            # don't bump against each other.
            left_panel.addSpacing(50)
        left_panel.addStretch()
        game_layout.addLayout(left_panel)

        # Center - table
        center_layout = QVBoxLayout()

        # Top row: Player 5 on left, Hero (0) on right (clockwise order)
        top_player_layout = QHBoxLayout()
        top_player_layout.addStretch()

        # Player 5
        panel = PlayerPanel(self.players[5], 5)
        self.player_panels.append((5, panel))
        top_player_layout.addWidget(panel)

        top_player_layout.addSpacing(40)

        # Hero (player 0) - top right
        hero_panel = PlayerPanel(self.players[0], 0)
        hero_panel.show_cards = True  # Hero always sees their cards
        self.player_panels.append((0, hero_panel))
        top_player_layout.addWidget(hero_panel)

        top_player_layout.addStretch()
        center_layout.addLayout(top_player_layout)

        # Table
        self.table = PokerTableWidget()
        center_layout.addWidget(self.table, stretch=1)

        game_layout.addLayout(center_layout, stretch=1)

        # Right side - players 1 and 2 (clockwise from hero)
        right_panel = QVBoxLayout()
        right_panel.addStretch()
        panel = PlayerPanel(self.players[1], 1)
        self.player_panels.append((1, panel))
        right_panel.addWidget(panel)
        # 50-px gap between Steve and Angela, mirroring the left column.
        right_panel.addSpacing(50)
        panel = PlayerPanel(self.players[2], 2)
        self.player_panels.append((2, panel))
        right_panel.addWidget(panel)
        right_panel.addStretch()
        game_layout.addLayout(right_panel)

        game_container_layout.addLayout(game_layout, stretch=1)

        # Sort panels by index for easy access
        self.player_panels.sort(key=lambda x: x[0])

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        # Explicit :disabled style so the user can see at a glance which
        # actions are not legal right now (e.g. Check is greyed when there
        # is a bet to call; Call is greyed when checking is free).
        btn_style = (
            "QPushButton { font-size: 16px; font-weight: bold; "
            "background-color: #555; color: white; "
            "border: 1px solid #777; border-radius: 5px; }"
            "QPushButton:hover:enabled { background-color: #666; }"
            "QPushButton:disabled { background-color: #2a2a2a; "
            "color: #666; border: 1px solid #333; }"
        )

        self.fold_btn = QPushButton("Fold")
        self.fold_btn.setFixedSize(130, 55)
        self.fold_btn.setStyleSheet(btn_style)
        self.fold_btn.clicked.connect(lambda: self.human_action('f', 0))
        self.fold_btn.setEnabled(False)
        action_layout.addWidget(self.fold_btn)

        # Check is its own button — only one of {Fold, Check} is enabled
        # at a time depending on whether checking is legal.
        self.check_btn = QPushButton("Check")
        self.check_btn.setFixedSize(130, 55)
        self.check_btn.setStyleSheet(btn_style)
        self.check_btn.clicked.connect(lambda: self.human_action('c', 0))
        self.check_btn.setEnabled(False)
        action_layout.addWidget(self.check_btn)

        self.call_btn = QPushButton("Call")
        self.call_btn.setFixedSize(130, 55)
        self.call_btn.setStyleSheet(btn_style)
        self.call_btn.clicked.connect(lambda: self.human_action('c', 0))
        self.call_btn.setEnabled(False)
        action_layout.addWidget(self.call_btn)

        self.raise_btn = QPushButton("Raise")
        self.raise_btn.setFixedSize(130, 55)
        self.raise_btn.setStyleSheet(btn_style)
        self.raise_btn.clicked.connect(self.show_raise_dialog)
        self.raise_btn.setEnabled(False)
        action_layout.addWidget(self.raise_btn)

        action_layout.addStretch()
        # Stash the QHBoxLayout reference so spectator-mode code can
        # add its ◀ ▶ Close buttons to the action ROW, not the outer
        # vertical layout. Going via fold_btn.parentWidget().layout()
        # used to return game_container_layout (vertical), which made
        # the spectator buttons stack instead of share one row.
        self._action_layout = action_layout
        game_container_layout.addLayout(action_layout)

        # Graphical Stats Panel (inside game container) + spectator
        # button column.  The two share a horizontal row so the ◀ ▶
        # Close-View buttons appear directly to the right of the
        # Pot Odds / Equity columns when the hero folds, instead of
        # being squeezed into the action-button row above where they
        # would overlap the player panels and the
        # "<winner> wins $X" message.  The button column stays
        # hidden until _enter_spectator_mode flips it on.
        stats_row = QWidget()
        stats_row_layout = QHBoxLayout(stats_row)
        stats_row_layout.setContentsMargins(0, 0, 0, 0)
        stats_row_layout.setSpacing(8)

        self.stats_panel = StatsPanel()
        self.stats_panel.setVisible(self.show_stats)
        stats_row_layout.addWidget(self.stats_panel, stretch=1)

        self._spectator_button_box = QWidget()
        self._spectator_button_box.setFixedWidth(190)
        spec_col = QVBoxLayout(self._spectator_button_box)
        spec_col.setContentsMargins(6, 6, 6, 6)
        spec_col.setSpacing(8)
        self._spectator_button_box.setVisible(False)
        # Buttons themselves are populated lazily in _enter_spectator_mode.
        self._spectator_button_col_layout = spec_col
        stats_row_layout.addWidget(self._spectator_button_box)

        game_container_layout.addWidget(stats_row)

        main_layout.addWidget(self.game_container, stretch=1)

        # === Theory of Mind View (shown when Theory of Mind is active) ===
        self.tom_container = QWidget()
        self.tom_container.setVisible(False)
        tom_container_layout = QVBoxLayout(self.tom_container)
        tom_container_layout.setContentsMargins(0, 0, 0, 0)

        # Card reminder bar (board + hero cards)
        self.tom_card_bar = QWidget()
        self.tom_card_bar.setFixedHeight(100)
        self.tom_card_bar.setStyleSheet("background-color: #1a1a1a; border: 1px solid #333;")
        card_bar_layout = QHBoxLayout(self.tom_card_bar)

        # Board cards section
        board_section = QHBoxLayout()
        self.tom_board_label = QLabel("Board:")
        self.tom_board_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.tom_board_label.setStyleSheet("color: #aaa; border: none;")
        board_section.addWidget(self.tom_board_label)

        self.tom_board_cards = []
        for i in range(5):
            card = CardWidget()
            card.setFixedSize(50, 70)
            card.set_card(None)
            self.tom_board_cards.append(card)
            board_section.addWidget(card)

        card_bar_layout.addLayout(board_section)
        card_bar_layout.addSpacing(50)

        # Hero cards section
        hero_section = QHBoxLayout()
        self.tom_hero_label = QLabel("Your Hand:")
        self.tom_hero_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.tom_hero_label.setStyleSheet("color: #aaa; border: none;")
        hero_section.addWidget(self.tom_hero_label)

        self.tom_hero_cards = []
        for i in range(2):
            card = CardWidget()
            card.setFixedSize(50, 70)
            card.set_card(None)
            self.tom_hero_cards.append(card)
            hero_section.addWidget(card)

        card_bar_layout.addLayout(hero_section)
        card_bar_layout.addStretch()

        tom_container_layout.addWidget(self.tom_card_bar)

        # Theory of Mind Panel (expanded)
        self.tom_panel = TheoryOfMindPanel()
        self.tom_panel._owner_window = self  # used by the bar dashboard
        self.tom_panel.setup_tabs(self.players, getattr(self, "network_human_seats", set()))
        self.tom_panel.set_update_callback(self.update_theory_of_mind)  # Wire up range mode callback
        tom_container_layout.addWidget(self.tom_panel, stretch=1)

        # Action buttons for Theory of Mind view
        tom_action_layout = QHBoxLayout()
        tom_action_layout.addStretch()

        # Per-action colored buttons with explicit :disabled greying so
        # the user can see which actions are not currently legal.
        tom_btn_base = (
            "QPushButton { font-size: 18px; font-weight: bold; "
            "padding: 10px 20px; color: white; border: 1px solid #777; "
            "border-radius: 5px; }"
            "QPushButton:disabled { background-color: #2a2a2a; "
            "color: #666; border: 1px solid #333; }"
        )

        self.tom_fold_btn = QPushButton("Fold")
        self.tom_fold_btn.setFixedSize(140, 60)
        self.tom_fold_btn.setStyleSheet(
            tom_btn_base + "QPushButton:enabled { background-color: #633; }"
            "QPushButton:hover:enabled { background-color: #844; }")
        self.tom_fold_btn.clicked.connect(lambda: self.human_action('f', 0))
        self.tom_fold_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_fold_btn)

        tom_action_layout.addSpacing(20)

        self.tom_check_btn = QPushButton("Check")
        self.tom_check_btn.setFixedSize(140, 60)
        self.tom_check_btn.setStyleSheet(
            tom_btn_base + "QPushButton:enabled { background-color: #363; }"
            "QPushButton:hover:enabled { background-color: #484; }")
        self.tom_check_btn.clicked.connect(lambda: self.human_action('c', 0))
        self.tom_check_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_check_btn)

        tom_action_layout.addSpacing(20)

        self.tom_call_btn = QPushButton("Call")
        self.tom_call_btn.setFixedSize(140, 60)
        self.tom_call_btn.setStyleSheet(
            tom_btn_base + "QPushButton:enabled { background-color: #363; }"
            "QPushButton:hover:enabled { background-color: #484; }")
        self.tom_call_btn.clicked.connect(lambda: self.human_action('c', 0))
        self.tom_call_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_call_btn)

        tom_action_layout.addSpacing(20)

        self.tom_raise_btn = QPushButton("Raise")
        self.tom_raise_btn.setFixedSize(140, 60)
        self.tom_raise_btn.setStyleSheet(
            tom_btn_base + "QPushButton:enabled { background-color: #336; }"
            "QPushButton:hover:enabled { background-color: #448; }")
        self.tom_raise_btn.clicked.connect(self.show_raise_dialog)
        self.tom_raise_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_raise_btn)

        tom_action_layout.addStretch()
        tom_container_layout.addLayout(tom_action_layout)

        main_layout.addWidget(self.tom_container, stretch=1)

        # Track action history for theory of mind analysis
        self.action_history = []

        # Update checkbox states
        self.update_checkbox_states()

        # Bottom bar with blinds on left and log in center
        bottom_bar = QHBoxLayout()

        # Blinds display (bottom left, white text).  Bumped from 14pt
        # → 19pt and widened to 230 so the "(↑ in N)" suffix doesn't
        # get clipped at most window sizes.
        self.blinds_label = QLabel("Blinds: $1/$2")
        self.blinds_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 19px;
                font-weight: bold;
                padding: 6px 12px;
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.blinds_label.setFixedWidth(230)
        bottom_bar.addWidget(self.blinds_label)

        # Log area (center)
        self.log_label = QLabel("Click 'New Hand' to start playing!")
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_label.setFont(QFont('Courier', 16))
        self.log_label.setStyleSheet("background-color: #111; color: #0f0; padding: 10px;")
        self.log_label.setWordWrap(True)
        self.log_label.setMaximumHeight(70)
        # Rich text so individual ticker segments can be coloured —
        # raises render in yellow so the user sees them at a glance
        # without the panel-flash that used to interrupt focus.
        self.log_label.setTextFormat(Qt.TextFormat.RichText)
        bottom_bar.addWidget(self.log_label, stretch=1)

        main_layout.addLayout(bottom_bar)

        # Wire in the Learning Hub (book-driven training + dashboards).
        # Adds Train/Review menus, EV button badges, mindset coach,
        # variance dashboard, AKQ lab, jam-or-fold trainer, etc.
        try:
            _install_learning_hub(self)
        except Exception as e:
            print(f"[learning hub] not installed: {e!r}", flush=True)

    def _is_multi_human_network(self) -> bool:
        """True iff we're in a network session — every network session
        has at least one other human, so we treat any network mode as
        multi-human for the deception-God-Mode rule."""
        return self.network_mode in ('host', 'client')

    def _refresh_assist_checkbox_state(self):
        """Re-evaluate which states the God Mode / Show Tells checkboxes
        should be in. Called when the network mode flips (host/join
        start, disconnect) and when spectator mode toggles.

        Rules:
          - Spectator mode (hero folded): both ENABLED + auto-checked
            elsewhere; we just need to leave them enabled here.
          - Networked multi-human: both ENABLED pre-fold, but with
            the deception layer so the displayed cards lie 50–100 %
            of the time. The toggle is "live but unreliable" so it's
            safe to expose pre-fold without breaking competitive
            play.
          - Single-player local: DISABLED — spectator-only assist.
        """
        try:
            allow = (self._is_multi_human_network()
                     or getattr(self, '_hero_folded_spectating', False))
            self.god_mode_cb.setEnabled(allow)
            self.stats_cb.setEnabled(allow)
            tip = ("Networked games show MOSTLY FAKE opponent cards "
                   "while you're still in the hand — the toggle is "
                   "live but unreliable as a peeking aid.") \
                if self._is_multi_human_network() \
                else "Auto-enables in spectator mode after you fold"
            self.god_mode_cb.setToolTip(tip)
            self.stats_cb.setToolTip(tip)
            # Don't drag a deceptive God Mode pre-fold setting forward
            # into a single-player session: when we leave the network
            # session, force both off so the player isn't peeking on
            # bot opponents accidentally.
            if not allow:
                self._spectator_auto_toggle = True
                try:
                    self.god_mode_cb.setChecked(False)
                    self.stats_cb.setChecked(False)
                finally:
                    self._spectator_auto_toggle = False
        except Exception:
            pass

    def _build_deception_hands_for_hand(self):
        """Generate per-hand fake hole cards for each non-hero active
        seat. Stored in ``self._deception_hands = {seat: [Card, Card]}``.

        For each hand we draw a per-hand "lying probability"
        p ∈ [0.5, 1.0] uniformly — so 50–100 % of opponent panels
        get lied to that hand, matching the user's spec. Fake cards
        avoid the real board and the hero's real hand to keep the
        rendered grid internally consistent (no card appears in two
        places at once on the table).

        Called at hand start; safe to call multiple times — the same
        hand always produces a fresh cache.
        """
        import random
        self._deception_hands = {}
        if not self._is_multi_human_network():
            return
        try:
            hero_seat = (self.my_seat
                         if self.network_mode == "client"
                            and self.my_seat is not None
                         else 0)
            used = set()
            if 0 <= hero_seat < len(self.players):
                for c in (self.players[hero_seat].hand or []):
                    used.add(str(c))
            for c in (self.board or []):
                used.add(str(c))
            full_deck = [r + s
                         for r in 'AKQJT98765432'
                         for s in 'shdc']
            available = [c for c in full_deck if c not in used]
            random.shuffle(available)
            lie_prob = random.uniform(0.5, 1.0)
            for seat, p in enumerate(self.players):
                if seat == hero_seat:
                    continue
                if not p.active or not p.hand:
                    continue
                if random.random() > lie_prob:
                    continue  # this opponent gets the real hand
                if len(available) < 2:
                    break
                c1 = available.pop()
                c2 = available.pop()
                try:
                    self._deception_hands[seat] = [
                        eval7.Card(c1), eval7.Card(c2)]
                except Exception:
                    pass
        except Exception as ex:
            print(f"[deception] hand build failed: {ex}")

    def _displayed_hand_for(self, seat: int):
        """Return the hand to RENDER for the given seat. Pulls from the
        deception cache when god_mode is on pre-fold in a network
        session; otherwise returns the real hand. Spectator mode
        bypasses the deception (the hero has folded, no need to
        protect the hand from them anymore)."""
        if not (0 <= seat < len(self.players)):
            return None
        real = self.players[seat].hand
        if not self._is_multi_human_network():
            return real
        if getattr(self, '_hero_folded_spectating', False):
            return real
        if not self.god_mode and not self.show_stats:
            return real
        cache = getattr(self, '_deception_hands', None) or {}
        return cache.get(seat, real)

    def toggle_god_mode(self, state):
        self.god_mode = self.god_mode_cb.isChecked()
        if self.god_mode:
            self._record_assist_used_locally("God Mode")
        # Rebuild deception cache so the first peek under god_mode
        # shows a freshly-generated lie even if the toggle came on
        # mid-hand.
        if (self.god_mode and self._is_multi_human_network()
                and not getattr(self, '_hero_folded_spectating', False)):
            if not getattr(self, '_deception_hands', None):
                self._build_deception_hands_for_hand()
        self.update_all_panels()
        self.update_checkbox_states()
        self._refresh_feature_status()
        self._broadcast_features()

    def toggle_stats(self, state):
        self.show_stats = self.stats_cb.isChecked()
        if self.show_stats:
            self._record_assist_used_locally("Show Tells")
        self.update_stats_display()
        self.update_checkbox_states()
        self._refresh_feature_status()
        self._broadcast_features()

    def _record_assist_used_locally(self, assist_name: str):
        """Flag the local hero as having used an assist mid-hand, but only
        if (a) they're still active in the current hand and (b) the toggle
        wasn't an automatic spectator-mode toggle (which kicks in AFTER the
        hero folded)."""
        if getattr(self, '_spectator_auto_toggle', False):
            return
        hero_seat = self.my_seat if self.my_seat is not None else 0
        if hero_seat >= len(self.players):
            return
        hero = self.players[hero_seat]
        if not getattr(hero, 'active', True):
            return
        hero_name = hero.name or "Hero"
        self.hand_assists_used.setdefault(hero_name, set()).add(assist_name)

    def toggle_theory_of_mind(self, state):
        is_checked = self.tom_cb.isChecked()

        # Toggle between game view and theory of mind view
        self.game_container.setVisible(not is_checked)
        self.tom_container.setVisible(is_checked)

        if is_checked:
            self.update_tom_card_bar()
            self.update_theory_of_mind()

        self.update_checkbox_states()
        self._refresh_feature_status()
        self._broadcast_features()

    def update_tom_card_bar(self, hero_position=None):
        """Update the card reminder bar with current board, hero cards, and position."""
        # Update board cards
        for i, card_widget in enumerate(self.tom_board_cards):
            if i < len(self.board):
                card_widget.set_card(str(self.board[i]))
            else:
                card_widget.set_card(None)

        # Update hero cards
        hero_seat = self.my_seat if self.my_seat is not None else 0
        hero = self.players[hero_seat]
        for i, card_widget in enumerate(self.tom_hero_cards):
            if hero.hand and i < len(hero.hand):
                card_widget.set_card(str(hero.hand[i]))
            else:
                card_widget.set_card(None)

        # Update hero position label
        if hero_position:
            pos_names = {'UTG': 'UTG', 'MP': 'Middle', 'CO': 'Cutoff',
                         'BTN': 'Button', 'SB': 'Sm Blind', 'BB': 'Big Blind'}
            pos_display = pos_names.get(hero_position, hero_position)
            self.tom_hero_label.setText(f"Your Hand ({pos_display}):")
        else:
            self.tom_hero_label.setText("Your Hand:")

    def update_checkbox_states(self):
        """Update checkbox enabled states - Theory of Mind only when others are off."""
        god_mode_on = self.god_mode_cb.isChecked()
        stats_on = self.stats_cb.isChecked()
        tom_on = self.tom_cb.isChecked()

        # Theory of Mind only available when God Mode and Show Tells are OFF
        can_use_tom = not god_mode_on and not stats_on
        self.tom_cb.setEnabled(can_use_tom)

        # If Theory of Mind is on but shouldn't be, turn it off
        if tom_on and not can_use_tom:
            self.tom_cb.setChecked(False)
            self.game_container.setVisible(True)
            self.tom_container.setVisible(False)

        # God Mode and Stats only available when Theory of Mind is OFF
        self.god_mode_cb.setEnabled(not tom_on)
        self.stats_cb.setEnabled(not tom_on)

    def update_theory_of_mind(self):
        """Update the Theory of Mind panel with current game state."""
        if not hasattr(self, 'tom_panel') or not self.tom_container.isVisible():
            return

        # Update card bar with hero's position
        hero_position = self.get_hero_position()
        self.update_tom_card_bar(hero_position)

        hero_seat = self.my_seat if self.my_seat is not None else 0
        hero = self.players[hero_seat]
        current_street = STREETS[self.street_idx] if self.street_idx < len(STREETS) else "River"
        try:
            _sb, _bb = BLIND_LEVELS[self.blind_level]
        except Exception:
            _bb = 2
        self.tom_panel.update_analysis(
            self.players,
            current_street,
            self.board,
            hero.hand if hero.hand else None,
            self.action_history,
            self.pot,  # Pass actual pot value
            current_bet=self.current_bet,  # Pass current bet for pot odds
            hero_bet=hero.bet_in_round,  # Pass hero's current bet
            hero_position=hero_position,  # Pass hero's position
            bb_amount=_bb,
            # Per-street structured actions for the inferred-read engine
            # on each opponent tab.
            street_actions=dict(self.hand_history.get(
                'street_actions', {}) or {}),
        )

        # Multiplayer: when hosting, push personalized advice to each client
        # so they see advice tailored to THEIR seat, not the host's view.
        if self.network_mode == "host" and self.network_server:
            try:
                advice_map = self._compose_tom_advice_for_clients(current_street)
                if advice_map:
                    self.network_server.broadcast_tom_advice_per_client(advice_map)
            except Exception as ex:
                print(f"[ToM] per-client advice broadcast failed: {ex}")

    def _compose_tom_advice_for_clients(self, current_street: str) -> dict:
        """Build a {seat_index: {'advice': str, 'notation': str}} map for
        each client seated at the table. Keeps it concise — one short
        paragraph per client — so the advice reaches the Advisor tab and
        remains readable on the client side.
        """
        advice_map: dict = {}
        seats = self.network_server.get_seats()  # {seat_index: player_name or None}
        for seat_index, player_name in seats.items():
            if seat_index == self.network_server.host_seat:
                continue  # host sees its own local ToM panel
            if not player_name:
                continue
            if seat_index >= len(self.players):
                continue
            p = self.players[seat_index]
            hand_str = " ".join(str(c) for c in p.hand) if p.hand else "(not dealt)"
            board_str = " ".join(str(c) for c in self.board) if self.board else "—"
            pot = getattr(self, 'pot', 0)
            to_call = max(0, getattr(self, 'current_bet', 0) - getattr(p, 'bet_in_round', 0))

            # Position label specific to this client's seat.
            position = self._position_for_seat(seat_index)

            # Short, plain-text advice tailored to THIS client's perspective.
            lines = [
                f"Hi {player_name} — advice for seat {seat_index + 1}:",
                f"  Your hand: {hand_str}",
                f"  Street: {current_street}   Position: {position}",
                f"  Pot: ${pot:.0f}   To call: ${to_call:.0f}",
                f"  Board: {board_str}",
            ]
            if to_call <= 0 and current_street != "Preflop":
                lines.append("  No bet to face. Consider checking or betting for value if ahead.")
            elif to_call > 0 and pot > 0:
                pot_odds = to_call / (pot + to_call) * 100
                lines.append(
                    f"  Pot odds ≈ {pot_odds:.1f}%. Call only with equity beating that.")
            advice_map[seat_index] = {
                'advice': "\n".join(lines),
                'notation': "",
            }
        return advice_map

    def _position_for_seat(self, seat_index: int) -> str:
        """Same rules as get_hero_position but for an arbitrary seat."""
        if not hasattr(self, 'dealer_idx'):
            return 'MP'
        num_players = len(self.players)
        sb_idx = (self.dealer_idx + 1) % num_players
        bb_idx = (self.dealer_idx + 2) % num_players
        utg_idx = (bb_idx + 1) % num_players
        while not self.players[utg_idx].active and utg_idx != bb_idx:
            utg_idx = (utg_idx + 1) % num_players
        co_idx = (self.dealer_idx - 1) % num_players
        while not self.players[co_idx].active and co_idx != self.dealer_idx:
            co_idx = (co_idx - 1) % num_players
        if seat_index == self.dealer_idx:
            return 'BTN'
        if seat_index == sb_idx:
            return 'SB'
        if seat_index == bb_idx:
            return 'BB'
        if seat_index == utg_idx:
            return 'UTG'
        if seat_index == co_idx:
            return 'CO'
        return 'MP'

    def get_hero_position(self):
        """Calculate hero's position based on dealer button."""
        if not hasattr(self, 'dealer_idx'):
            return 'MP'

        num_players = len(self.players)
        hero_idx = self.my_seat if self.my_seat is not None else 0

        sb_idx = (self.dealer_idx + 1) % num_players
        bb_idx = (self.dealer_idx + 2) % num_players

        # Find UTG (first active player after BB)
        utg_idx = (bb_idx + 1) % num_players
        while not self.players[utg_idx].active and utg_idx != bb_idx:
            utg_idx = (utg_idx + 1) % num_players

        # Find CO (last active player before BTN)
        co_idx = (self.dealer_idx - 1) % num_players
        while not self.players[co_idx].active and co_idx != self.dealer_idx:
            co_idx = (co_idx - 1) % num_players

        # Determine hero's position
        if hero_idx == self.dealer_idx:
            return 'BTN'
        elif hero_idx == sb_idx:
            return 'SB'
        elif hero_idx == bb_idx:
            return 'BB'
        elif hero_idx == utg_idx:
            return 'UTG'
        elif hero_idx == co_idx:
            return 'CO'
        else:
            return 'MP'

    def log_action(self, msg, include_stats=False):
        """Log action to both display and file."""
        self.action_log.append(msg)
        if len(self.action_log) > 5:
            self.action_log = self.action_log[-5:]
        spectating = getattr(self, '_hero_folded_spectating', False)
        view_idx = getattr(self, '_spectator_view_idx', -1)
        # Don't repaint the visible strip while a folded spectator is
        # parked on a past street — they choose when to advance.
        if not (spectating and view_idx >= 0):
            # Yellow-highlights raises and all-ins via the rich-text
            # formatter; falls back to plain " | ".join when the
            # formatter helper isn't available (older save format).
            try:
                self.log_label.setText(
                    self._format_action_log_html(self.action_log))
            except AttributeError:
                self.log_label.setText(" | ".join(self.action_log))
        # Keep the current-street snapshot's action_log fresh while the
        # hero is in spectator mode, so flipping back to "now" via Next
        # Street shows the live tail (and so the hero's own fold message
        # ends up in the preflop-fold snapshot, which is captured before
        # the fold message is logged).  If the user is currently parked
        # on this same street's snapshot, also refresh the displayed log
        # so events on their viewed street appear without forcing them
        # to navigate.
        if spectating and self.street_idx < len(STREETS):
            try:
                self._spectator_record_snapshot(
                    STREETS[self.street_idx], self.street_idx,
                    self.board, self.action_log)
                snaps = getattr(self, '_spectator_street_snapshots', [])
                if (0 <= view_idx < len(snaps)
                        and snaps[view_idx].get('street_idx') == self.street_idx):
                    self._spectator_show_snapshot(view_idx)
            except Exception:
                pass
        # Also write to file
        self.write_log(msg, include_stats=include_stats)
        # Track for Theory of Mind analysis
        if hasattr(self, 'action_history'):
            self.action_history.append(msg)
            self.update_theory_of_mind()

    def _format_action_log_html(self, entries):
        """Render the bottom-bar action log as rich text.

        Raise lines are highlighted in yellow so the user notices them
        without the panel-flash dance. Everything else stays on the
        green base (matched to log_label's stylesheet color).
        """
        from html import escape
        parts = []
        for entry in entries:
            text = escape(str(entry))
            lower = text.lower()
            if 'raise' in lower or 'all-in' in lower or 'all in' in lower:
                parts.append(
                    f'<span style="color:#ffd633;font-weight:bold">{text}</span>'
                )
            else:
                parts.append(text)
        return ' | '.join(parts)

    def update_status(self, message: str):
        """Update the status display with a network/game status message."""
        features = self._get_active_features()
        if features:
            self.log_label.setText(f"{message}  [{features}]")
        else:
            self.log_label.setText(message)

    def _get_active_features(self) -> str:
        """Return a string describing active features (God Mode, Tells, ToM)."""
        active = []
        if hasattr(self, 'god_mode_cb') and self.god_mode_cb.isChecked():
            active.append("God Mode")
        if hasattr(self, 'stats_cb') and self.stats_cb.isChecked():
            active.append("Tells")
        if hasattr(self, 'tom_cb') and self.tom_cb.isChecked():
            active.append("Theory of Mind")
        return " | ".join(active)

    def _refresh_feature_status(self):
        """Refresh the status bar with current feature flags."""
        if self.network_mode:
            mode = "Server" if self.network_mode == "host" else "Client"
            parts = []
            local_features = self._get_active_features()
            if local_features:
                parts.append(local_features)
            remote_features = getattr(self, '_remote_features_text', '')
            if remote_features:
                parts.append(remote_features)
            feature_text = " | ".join(parts)
            if feature_text:
                self.log_label.setText(f"{mode} active  [{feature_text}]")
            else:
                self.log_label.setText(f"{mode} active")

    def _broadcast_features(self):
        """Broadcast feature toggles to the other network instance.
        Skip while the spectator-mode auto-toggle is in flight — that is
        not a real opt-in, it's an automatic side effect of folding."""
        if not self.network_mode:
            return
        if getattr(self, '_spectator_auto_toggle', False):
            return
        features = {
            'god_mode': self.god_mode_cb.isChecked(),
            'tells': self.stats_cb.isChecked(),
            'theory_of_mind': self.tom_cb.isChecked(),
        }
        if self.network_mode == "host" and self.network_server:
            hero_name = self.players[0].name if self.players else "Server"
            self.network_server.broadcast_feature_toggle(hero_name, features)
        elif self.network_mode == "client" and self.network_client:
            self.network_client.send_feature_toggle(features)

    def _on_feature_toggle_received(self, player_name: str, features: dict):
        """Handle feature toggle from the other network instance."""
        active = []
        # Find that player's seat to check if they're still active in the
        # current hand. If they already folded, this toggle is just their
        # spectator-mode auto-enable and should NOT be flagged in the summary.
        toggling_player_active = True
        toggling_seat = None
        for i, p in enumerate(self.players):
            if p.name == player_name:
                toggling_player_active = bool(getattr(p, 'active', True))
                toggling_seat = i
                break
        if features.get('god_mode'):
            active.append("God Mode")
            if toggling_player_active:
                self.hand_assists_used.setdefault(player_name, set()).add("God Mode")
            # Host: push all hole cards to the client that enabled God Mode
            if (self.network_mode == "host" and self.network_server
                    and toggling_seat is not None):
                self._send_spectator_hole_cards_to_seat(toggling_seat)
        if features.get('tells'):
            # Host: push hole cards so the client can compute equity for all players
            if (self.network_mode == "host" and self.network_server
                    and toggling_seat is not None):
                self._send_spectator_hole_cards_to_seat(toggling_seat)
            active.append("Tells")
            if toggling_player_active:
                self.hand_assists_used.setdefault(player_name, set()).add("Show Tells")
        if features.get('theory_of_mind'):
            active.append("Theory of Mind")
        if active:
            self._remote_features_text = f"{player_name}: {', '.join(active)}"
        else:
            self._remote_features_text = ""
        self._refresh_feature_status()

    def get_panel(self, player_idx):
        for idx, panel in self.player_panels:
            if idx == player_idx:
                return panel
        return None

    def _flash_color_for_raise(self, raise_size: float, pot_before: float) -> str:
        """Choose flash color based on raise size relative to the pot.

        - 'normal'  : ≤ 25% of pot (subtle pulse, no alarm color)
        - 'orange'  : > 25% and < 50% of pot
        - 'red'     : ≥ 50% of pot (e.g. an all-in or pot-sized shove)

        Falls back to 'red' if pot_before is unknown / zero.
        """
        try:
            r = float(raise_size or 0)
            p = float(pot_before or 0)
        except (TypeError, ValueError):
            return 'red'
        if p <= 0:
            return 'red'
        ratio = r / p
        if ratio <= 0.25:
            return 'normal'
        if ratio < 0.5:
            return 'orange'
        return 'red'

    def update_blinds_display(self):
        """Update the blinds label with current blind level."""
        sb, bb = BLIND_LEVELS[self.blind_level]
        hands_until_increase = HANDS_PER_BLIND_LEVEL - (self.hand_number % HANDS_PER_BLIND_LEVEL)
        if hands_until_increase == HANDS_PER_BLIND_LEVEL:
            hands_until_increase = 0  # Just increased
        next_level_text = ""
        if self.blind_level < len(BLIND_LEVELS) - 1 and hands_until_increase > 0:
            next_level_text = f" (↑ in {hands_until_increase})"
        self.blinds_label.setText(f"Blinds: ${sb}/${bb}{next_level_text}")

    def update_all_panels(self):
        try:
            current_street = STREETS[self.street_idx] if 0 <= self.street_idx < len(STREETS) else ""
        except Exception:
            current_street = ""
        hero_seat = self.my_seat if self.my_seat is not None else 0

        def best_hand_for(player, hand_override=None):
            """Compute the made-hand description for a given player.

            Preflop (no community cards yet): show the starting-hand name
            (e.g. 'pocket Aces', 'Ace-King suited').  Postflop: show the
            current best made hand on the board.

            ``hand_override`` lets the caller pass the displayed-hand
            (deception cards) instead of the engine's authoritative one
            so the made-hand label stays consistent with the rendered
            cards under deceptive God Mode.
            """
            hand = hand_override if hand_override else player.hand
            if not hand or len(hand) < 2:
                return ""
            try:
                if not self.board:
                    return get_hand_name(hand)
                return self.describe_made_hand(
                    hand, [str(c) for c in self.board])
            except Exception:
                return ""

        for idx, panel in self.player_panels:
            player = self.players[idx]
            # If this player has been busted out (zero chips, not in this
            # hand), hide their panel completely so the seat looks vacant.
            # The hero's own panel is never hidden — they get the busted
            # game-over dialog instead.
            #
            # We deliberately do NOT exempt at_showdown — a previously-
            # busted seat doesn't have cards in this showdown either, so
            # rendering an empty panel for them at showdown only adds
            # visual noise. (The previous "and not at_showdown" clause
            # left dead-player panels visible during showdown / spectator
            # mode after a bust hand.)
            if (player.stack <= 0 and not player.active
                    and idx != hero_seat):
                panel.setVisible(False)
                if hasattr(panel, 'set_best_hand'):
                    panel.set_best_hand("")
                continue
            else:
                panel.setVisible(True)

            # Decide whether this seat's hole cards are visible.
            if player.style == 'human':
                panel.show_cards = True
            elif hasattr(self, 'at_showdown') and self.at_showdown and player.active:
                panel.show_cards = True
            elif self.god_mode:
                panel.show_cards = True
            else:
                panel.show_cards = False

            # Plumb the deceptive God Mode override into the panel for
            # non-hero seats — hero always sees their own real cards.
            if idx != hero_seat:
                fake = self._displayed_hand_for(idx)
                # Use the override only when it actually differs from
                # the real hand (deception cache hit) — otherwise leave
                # the override clear so update_display can fall through
                # to the engine's player.hand value.
                if fake is not None and fake is not player.hand:
                    panel.display_override_hand = fake
                else:
                    panel.display_override_hand = None
            else:
                panel.display_override_hand = None
            panel.update_display()

            # Whenever cards are visible, show the corresponding best
            # hand below them.  Cards hidden → label hidden. The made-
            # hand label uses whatever the panel renders so it stays
            # consistent with the deceived cards under God Mode.
            if hasattr(panel, 'set_best_hand'):
                shown_hand = (panel.display_override_hand
                              or player.hand)
                if panel.show_cards and shown_hand:
                    panel.set_best_hand(
                        best_hand_for(player, hand_override=shown_hand))
                else:
                    panel.set_best_hand("")

    def update_stats_display(self):
        """Update the graphical stats panel."""
        self.stats_panel.setVisible(self.show_stats)

        if not self.show_stats:
            self.stats_panel.clear_stats()
            return

        if not self.players or not any(p.hand for p in self.players):
            self.stats_panel.clear_stats()
            return

        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'players': self.players,
            'current_bet': self.current_bet
        }

        # In god mode, calculate multiway equities that sum to 100%
        # Use caching to prevent flickering from Monte Carlo variance
        true_equities = {}
        if self.god_mode:
            active_hands = [(p, p.hand) for p in self.players if p.active and p.hand]
            if active_hands:
                # Create cache key from board + active hands
                cache_key = (
                    tuple(str(c) for c in self.board),
                    tuple((p.name, tuple(str(c) for c in p.hand)) for p, _ in active_hands)
                )

                if cache_key != self.equity_cache_key:
                    # Recalculate only when state changes
                    self.equity_cache = calc_multiway_equity(
                        active_hands,
                        [str(c) for c in self.board],
                        iterations=1000  # More iterations for stability
                    )
                    self.equity_cache_key = cache_key

                true_equities = self.equity_cache

        stats = []
        for p in self.players:
            if p.hand:
                # Perceived equity: what player thinks (vs random cards)
                perceived_equity, pot_odds, to_call = p.calculate_current_stats(game_state, False)

                if self.god_mode:
                    # True equity from multiway calculation (sums to 100%)
                    true_equity = true_equities.get(p, 0.0)
                    stats.append((p.name, true_equity, perceived_equity, pot_odds, p.active, p.style == 'human'))
                else:
                    # Without god mode, only show perceived equity
                    stats.append((p.name, None, perceived_equity, pot_odds, p.active, p.style == 'human'))
            else:
                stats.append((p.name, None, 0, 0, p.active, p.style == 'human'))

        self.stats_panel.set_stats(stats)

    def deal_hand(self):
        """Start a new hand."""
        # Block re-entry while a hand is in progress so the human can't
        # click "New Hand" mid-hand and burn other players' blinds.
        if getattr(self, '_hand_in_progress', False):
            return
        # If the hero is still parked in spectator mode from the previous
        # hand (paging through streets), tear that UI down before starting
        # the next hand. God Mode / Show Tells revert to whatever they
        # were before the fold and the spectator-nav row hides.
        if getattr(self, '_hero_folded_spectating', False):
            self._exit_spectator_mode()
        self._hand_in_progress = True
        self.new_hand_btn.setEnabled(False)
        self.hand_number += 1
        self.action_log = []
        self.action_history = []  # Reset for Theory of Mind
        self.log_action("=== NEW HAND ===")
        # Lock the New Hand button until this hand finishes.
        if hasattr(self, 'new_hand_btn'):
            self.new_hand_btn.setEnabled(False)

        # Log to file
        self.write_log(f"\n{'='*60}")
        self.write_log(f"HAND #{self.hand_number} - {datetime.now().strftime('%H:%M:%S')}")
        self.write_log(f"{'='*60}")

        self.deck = eval7.Deck()
        self.deck.shuffle()
        self.board = []
        self.pot = 0
        self.current_bet = 0
        self.street_idx = 0
        self.last_raiser = -1
        self.raises_this_round = 0
        self.at_showdown = False

        # Clear equity cache for new hand
        self.equity_cache = {}
        self.equity_cache_key = None

        # Track which players used assists at any point during this hand
        # {player_name: set of assist names}.  Only flag assists used while
        # the player is still in the hand — assists auto-toggled after a fold
        # (spectator mode) don't count.
        self.hand_assists_used = {}
        hero_seat = self.my_seat if self.my_seat is not None else 0
        if hero_seat < len(self.players):
            hero_name = self.players[hero_seat].name or "Hero"
            if self.god_mode:
                self.hand_assists_used.setdefault(hero_name, set()).add("God Mode")
            if self.show_stats:
                self.hand_assists_used.setdefault(hero_name, set()).add("Show Tells")

        # Reset spectator state so a previous hand's snapshots don't leak in
        self._spectator_street_snapshots = []
        self._spectator_view_idx = -1
        # Drop any cached Claude analyses from the prior hand
        self._latest_hand_analyses = None
        self._latest_hand_analyses_hand = None
        # Dismiss any prior-hand summary / stats dialogs left open
        self._close_open_hand_dialogs()
        # First hand of the session: log GAME STATUS (bracelets-style)
        if not getattr(self, '_game_status_logged', False):
            self._log_game_status()
            self._game_status_logged = True

        # Reset hand history for interpretation
        self.hand_history = {
            'hero_cards': [],
            'hero_actions': [],
            'street_equities': {},
            'key_events': [],
            'board_by_street': {},
            'villain_info': {},
            'street_stats': {},      # {street: [(name, true_eq, perc_eq, pot_odds, active, is_hero), ...]}
            'street_actions': {},    # {street: ["Player: action", ...]}
            'pot_by_street': {},     # {street: pot_size_after_street}
        }

        for p in self.players:
            p.reset_for_hand()
            if p.stack <= 0:
                p.active = False

        # If the hero has unlocked the advanced bot pool, randomly seat
        # bots from the combined pool at the start of each NEW hand. We
        # only re-randomize at hand 1 of a game so personalities stay
        # consistent within a game.
        if self.hand_number == 1:
            self._maybe_randomize_bots_for_game()

        # Save starting stacks for gain/loss tracking
        self.starting_stacks = {p.name: p.stack for p in self.players}

        # Refresh the deceptive-God-Mode hole-card cache for this hand.
        # Cheap (one shuffle) and only kicks in when network mode is
        # active; in single-player it returns immediately.
        self._build_deception_hands_for_hand()

        # Check if hero is busted. Single-player: prompt to reset (or
        # offer Buy More Chips). Network host: don't reset the whole
        # session — every other seat keeps their stack and the busted
        # host can use File → Buy More Chips to rejoin.
        hero = self.players[0]
        if hero.stack <= 0:
            self._hand_in_progress = False
            self.new_hand_btn.setEnabled(True)
            if self.network_mode == "host":
                # Tell the host how to recover but don't tear down the
                # session — the bots / guests can keep playing.
                QMessageBox.information(
                    self, "You're out of chips",
                    "<div style='font-size:24px; font-weight:bold;"
                    " color:#000;'>"
                    "You're out of chips!</div>"
                    "<div style='font-size:24px; font-weight:bold;"
                    " color:#000; margin-top:8px;'>"
                    "Use <b>File → Buy More Chips…</b> to rejoin "
                    "the next hand. The other seats keep playing "
                    "in the meantime.</div>"
                )
                return
            reply = self._game_over_question(
                "You're out of chips! Would you like to start a new game?")
            if reply == QMessageBox.StandardButton.Yes:
                self.reset_game()
            return

        active_count = sum(1 for p in self.players if p.active)
        if active_count < 2:
            self._hand_in_progress = False
            self.new_hand_btn.setEnabled(True)
            self._game_over_information(
                "You've won! All opponents are eliminated!")
            return

        # Deal hole cards
        active_players = [p for p in self.players if p.active]
        for _ in range(2):
            for p in active_players:
                p.hand.append(self.deck.deal(1)[0])

        # Verify no duplicate cards (debug check)
        all_cards = []
        for p in active_players:
            for c in p.hand:
                card_str = str(c)
                if card_str in all_cards:
                    print(f"ERROR: Duplicate card {card_str} detected!")
                all_cards.append(card_str)

        # Log dealt cards to file
        self.write_log(f"Dealer: {self.players[self.dealer_idx].name}")
        self.write_log("Hole Cards Dealt:")
        for p in active_players:
            self.write_log(f"  {p.name}: {format_cards(p.hand)}")

        # Track hero's cards for interpretation
        hero = self.players[0]
        self.hand_history['hero_cards'] = [str(c) for c in hero.hand]
        self.hand_history['hero_hand_name'] = get_hand_name(hero.hand)
        # Bracelets-style hands_played + hole-class hands_seen tracking
        self._record_hand_start_stats()

        # Post blinds - find active players for SB and BB positions
        sb_idx = (self.dealer_idx + 1) % len(self.players)
        while not self.players[sb_idx].active or self.players[sb_idx].stack <= 0:
            sb_idx = (sb_idx + 1) % len(self.players)
            if sb_idx == self.dealer_idx:  # Wrapped around
                break

        bb_idx = (sb_idx + 1) % len(self.players)
        while not self.players[bb_idx].active or self.players[bb_idx].stack <= 0:
            bb_idx = (bb_idx + 1) % len(self.players)
            if bb_idx == sb_idx:  # Wrapped around
                break

        # Get current blind amounts
        sb_amount, bb_amount = BLIND_LEVELS[self.blind_level]

        self.post_blind(self.players[sb_idx], sb_amount)
        self.post_blind(self.players[bb_idx], bb_amount)

        self.current_bet = bb_amount

        # Check for blind level increase
        if self.hand_number > 0 and self.hand_number % HANDS_PER_BLIND_LEVEL == 0:
            if self.blind_level < len(BLIND_LEVELS) - 1:
                self.blind_level += 1
                new_sb, new_bb = BLIND_LEVELS[self.blind_level]
                self.log_action(f"*** BLINDS INCREASE: ${new_sb}/${new_bb} ***")
                # Show popup notification
                QMessageBox.information(self, "Blinds Increase!",
                    f"Blinds are now ${new_sb}/${new_bb}")

        # Update blinds display
        self.update_blinds_display()

        # Update position indicators on panels
        # Calculate all positions
        utg_idx = (bb_idx + 1) % len(self.players)
        # Find next active player after BB for UTG
        while not self.players[utg_idx].active and utg_idx != bb_idx:
            utg_idx = (utg_idx + 1) % len(self.players)

        co_idx = (self.dealer_idx - 1) % len(self.players)  # Cutoff is before button
        # Find previous active player before BTN for CO
        while not self.players[co_idx].active and co_idx != self.dealer_idx:
            co_idx = (co_idx - 1) % len(self.players)

        for idx, panel in self.player_panels:
            if idx == self.dealer_idx:
                panel.set_position("BT")
            elif idx == sb_idx:
                panel.set_position("SB")
            elif idx == bb_idx:
                panel.set_position("BB")
            elif idx == utg_idx and utg_idx != self.dealer_idx:
                panel.set_position("UTG")
            elif idx == co_idx and co_idx not in [sb_idx, bb_idx, utg_idx]:
                panel.set_position("CO")
            else:
                panel.set_position("")

        # Update display
        self.table.set_board([])
        hero = self.players[0]
        self.table.set_hero_cards([str(c) for c in hero.hand] if hero.hand else [])
        self.table.set_pot(self.pot)
        self.table.set_street("Preflop")
        self.table.set_message("")  # Button indicator on player panel shows dealer
        self.update_all_panels()
        self.update_stats_display()

        # Network broadcast for host mode
        if self.network_mode == "host" and self.network_server:
            # Broadcast hand start
            stacks = {i: p.stack for i, p in enumerate(self.players)}
            _, bb = BLIND_LEVELS[self.blind_level]
            self.network_server.broadcast_hand_start(
                self.hand_number, self.dealer_idx, BLIND_LEVELS[self.blind_level], stacks
            )
            # Send private hole cards to each network player
            for seat in self.network_human_seats:
                client_id = self.network_server.get_client_for_seat(seat)
                if client_id and self.players[seat].hand:
                    cards = [str(c) for c in self.players[seat].hand]
                    self.network_server.send_hole_cards(client_id, cards)

        # Start betting
        self.current_player_idx = (bb_idx + 1) % len(self.players)
        self.betting_round_init()

    def post_blind(self, player, amount):
        amount = min(player.stack, amount)
        player.stack -= amount
        player.bet_in_round = amount
        player.total_invested += amount
        self.pot += amount
        self.log_action(f"{player.name} posts ${amount}")

    def betting_round_init(self):
        """Initialize a betting round."""
        self.last_raiser = -1
        self.raises_this_round = 0
        # Size of the most recent raise this round (above the previous bet
        # level). The next legal raise must increase the bet by at least this.
        # Reset to BB on each new street so a fresh open is allowed.
        _, bb_amount = BLIND_LEVELS[self.blind_level]
        # Preflop the BB itself counts as the opening "bet" of size BB, so
        # min raise-over-call is also BB. Postflop start with BB as the floor.
        self.last_raise_size = int(bb_amount)

        # Reset actions
        for p in self.players:
            p.actions_this_round = 0

        self.process_next_player()

    def count_active(self):
        return sum(1 for p in self.players if p.active)

    def count_active_with_chips(self):
        return sum(1 for p in self.players if p.active and p.stack > 0)

    def process_next_player(self):
        """Process the next player's turn."""
        if self.count_active() < 2:
            self.end_hand()
            return

        # If only one player has chips, check if they need to act
        # (they may need to call an all-in bet)
        if self.count_active_with_chips() <= 1:
            # Find the player with chips
            players_with_chips = [p for p in self.players if p.active and p.stack > 0]
            if players_with_chips:
                player = players_with_chips[0]
                to_call = self.current_bet - player.bet_in_round
                # If they need to call or haven't acted, let them act
                if to_call > 0 or player.actions_this_round == 0:
                    pass  # Continue to let them act
                else:
                    # They've acted and don't need to call. If there's
                    # still more board to deal AND no one has chips
                    # left to act on it (multi-way all-in runout),
                    # pause behind the Next Card button so the user
                    # can step through turn and river one card at a
                    # time instead of seeing the engine auto-deal
                    # everything in the same paint.
                    if self._needs_allin_runout_pause():
                        self._await_next_card()
                        return
                    self.end_betting_round()
                    return
            else:
                # No one has chips. Same Next Card pause logic as
                # above — only fall straight through to
                # end_betting_round when we're already at the river
                # (no more cards are coming, just go to showdown).
                if self._needs_allin_runout_pause():
                    self._await_next_card()
                    return
                self.end_betting_round()
                return

        # Find next active player
        attempts = 0
        while attempts < len(self.players):
            player = self.players[self.current_player_idx]

            if player.active and player.stack > 0:
                to_call = self.current_bet - player.bet_in_round

                # Check if betting round is complete
                if player.actions_this_round > 0 and to_call == 0:
                    # Player has acted and doesn't need to call
                    self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
                    attempts += 1
                    continue

                # This player needs to act
                self.set_active_player(self.current_player_idx)

                # Broadcast active player to network clients
                if self.network_mode == "host" and self.network_server:
                    self.network_server.broadcast_active_player(self.current_player_idx)

                if player.style == 'human':
                    self.enable_human_actions()
                else:
                    # Bot acts after a short delay
                    QTimer.singleShot(500, self.process_bot_action)
                return

            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
            attempts += 1

        # Betting round complete
        self.end_betting_round()

    def set_active_player(self, idx):
        """Highlight the active player."""
        for i, panel in self.player_panels:
            panel.set_active_turn(i == idx)

    def enable_human_actions(self):
        """Enable action buttons for human player.

        The four action buttons are Fold, Check, Call, Raise. Exactly one
        of {Fold, Check} is enabled at any moment depending on whether
        checking is legal:
          - to_call == 0  → Check enabled, Fold disabled, Call disabled.
          - to_call > 0   → Check disabled, Fold enabled, Call enabled.
        If everyone is all-in (no one can act further), shows a single
        'Next Card' button instead.
        """
        self.waiting_for_human = True
        hero_seat = self.my_seat if self.network_mode == "client" and self.my_seat is not None else 0
        player = self.players[hero_seat]
        to_call = max(0, self.current_bet - player.bet_in_round)

        # Don't replace fold/check/call/raise with Next Card unless
        # the hero literally has no chips left. We used to also trip
        # this shortcut when "others can't act AND to_call == 0", but
        # that hijacked the action row from a player who still had a
        # big stack and a real check/bet decision to make. Per the
        # user spec: Next Card belongs ONLY to a multi-way all-in
        # runout, which is handled in process_next_player via
        # _needs_allin_runout_pause(). Keep this branch as a safety
        # net for the impossible "stack-0 hero got asked to act"
        # case so the UI degrades gracefully instead of presenting
        # a $0 player with bet buttons.
        if player.stack <= 0:
            self._show_next_card_button(True)
            return
        self._show_next_card_button(False)

        can_check = (to_call <= 0)

        # Fold ↔ Check mutual exclusion.
        self.fold_btn.setEnabled(not can_check)
        self.check_btn.setEnabled(can_check)
        self.tom_fold_btn.setEnabled(not can_check)
        self.tom_check_btn.setEnabled(can_check)

        # Call only meaningful when there's something to call.
        if can_check:
            self.call_btn.setText("Call")
            self.tom_call_btn.setText("Call")
            self.call_btn.setEnabled(False)
            self.tom_call_btn.setEnabled(False)
        else:
            self.call_btn.setText(f"Call ${to_call}")
            self.tom_call_btn.setText(f"Call ${to_call}")
            self.call_btn.setEnabled(True)
            self.tom_call_btn.setEnabled(True)

        # Min raise enforces the No-Limit minimum: at least the size of the
        # previous raise this round (last_raise_size).
        min_raise_above = max(int(getattr(self, 'last_raise_size', 0)),
                              int(BLIND_LEVELS[self.blind_level][1]))
        if player.stack > to_call + min_raise_above or player.stack > to_call:
            # If they have *any* extra above the call they can shove all-in
            # even when they can't post the full minimum raise.
            self.raise_btn.setEnabled(player.stack > to_call)
            self.tom_raise_btn.setEnabled(player.stack > to_call)
        else:
            self.raise_btn.setEnabled(False)
            self.tom_raise_btn.setEnabled(False)

        # Label the raise button "Bet" instead of "Raise" when no one
        # has put chips in this street yet — the canonical postflop
        # term for the first wager. Preflop always has the BB on the
        # board so current_bet > 0 and the label stays "Raise".
        bet_label = "Bet" if int(self.current_bet) == 0 else "Raise"
        self.raise_btn.setText(bet_label)
        self.tom_raise_btn.setText(bet_label)

    def disable_human_actions(self):
        """Disable action buttons."""
        self.waiting_for_human = False
        self.fold_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.call_btn.setEnabled(False)
        self.raise_btn.setEnabled(False)
        self.tom_fold_btn.setEnabled(False)
        self.tom_check_btn.setEnabled(False)
        self.tom_call_btn.setEnabled(False)
        self.tom_raise_btn.setEnabled(False)
        self._show_next_card_button(False)

    def _show_next_card_button(self, show: bool):
        """Toggle a 'Next Card' button that replaces fold/check/call/raise
        when all (or all-but-one) remaining players are all-in. Clicking it
        runs out the rest of the board to showdown.
        """
        # Lazily create the button so older saves still work.
        if not hasattr(self, 'next_card_btn'):
            self.next_card_btn = QPushButton("Next Card")
            self.next_card_btn.setFixedSize(420, 55)
            self.next_card_btn.setStyleSheet(
                "QPushButton { font-size: 18px; font-weight: bold; "
                "background-color: #357; color: white; border-radius: 5px; }"
                "QPushButton:hover { background-color: #468; }"
            )
            self.next_card_btn.clicked.connect(self._on_next_card_clicked)
            # Insert into the action row (the QHBoxLayout that holds
            # fold/check/call/raise) BEFORE its trailing stretch so the
            # 420 px Next Card button lands centred between the two
            # stretches when the four standard buttons are hidden.
            # Using fold_btn.parentWidget().layout() returned the OUTER
            # vertical container, which dropped the button into its own
            # row underneath — i.e. "on the side" relative to where
            # the user reads action controls.
            try:
                action_layout = (getattr(self, '_action_layout', None)
                                 or self.fold_btn.parentWidget().layout())
                # Insert at index = (count - 1) so it sits just before
                # the trailing addStretch(). count() includes stretches.
                insert_at = max(0, action_layout.count() - 1)
                action_layout.insertWidget(insert_at, self.next_card_btn)
            except Exception:
                pass
            self.next_card_btn.setVisible(False)

        if show:
            self.fold_btn.setVisible(False)
            self.check_btn.setVisible(False)
            self.call_btn.setVisible(False)
            self.raise_btn.setVisible(False)
            self.tom_fold_btn.setVisible(False)
            self.tom_check_btn.setVisible(False)
            self.tom_call_btn.setVisible(False)
            self.tom_raise_btn.setVisible(False)
            self.next_card_btn.setVisible(True)
            self.next_card_btn.setEnabled(True)
        else:
            # While the hero is in folded-spectator mode the action
            # row must stay hidden — disable_human_actions() ends up
            # here as the hand resolves and was re-revealing the
            # greyed-out fold/check/call/raise pixels on the green
            # felt. Spectator mode owns visibility until Close View.
            if getattr(self, '_hero_folded_spectating', False):
                self.next_card_btn.setVisible(False)
                return
            self.fold_btn.setVisible(True)
            self.check_btn.setVisible(True)
            self.call_btn.setVisible(True)
            self.raise_btn.setVisible(True)
            self.tom_fold_btn.setVisible(True)
            self.tom_check_btn.setVisible(True)
            self.tom_call_btn.setVisible(True)
            self.tom_raise_btn.setVisible(True)
            self.next_card_btn.setVisible(False)

    def _needs_allin_runout_pause(self) -> bool:
        """True iff the current state is a "multi-way all-in runout"
        AND there's still board to deal.

        Multi-way all-in runout = at least two players are still in
        the hand (count_active >= 2) but none of them has chips left
        (count_active_with_chips == 0). Without this pause the engine
        would auto-fire end_betting_round → deal next card →
        end_betting_round → … all in the same UI paint, so the user
        never gets to see the turn before the river arrives.
        """
        try:
            if self.count_active() < 2:
                return False
            if self.count_active_with_chips() > 0:
                return False
            # No more streets coming → fall through to showdown,
            # don't bother with another Next Card click.
            return self.street_idx < len(STREETS) - 1
        except Exception:
            return False

    def _await_next_card(self):
        """Render the Next Card button and wait for the user to click
        it before advancing to the next street. Used during a multi-
        way all-in runout (see _needs_allin_runout_pause)."""
        # Reuse the existing waiting-for-human guard so the existing
        # _on_next_card_clicked handler dispatches to end_betting_round.
        self.waiting_for_human = True
        self._show_next_card_button(True)

    def _on_next_card_clicked(self):
        """User clicked 'Next Card' during the all-in runout. Skip betting
        for the remaining streets by closing the current betting round.

        Network clients aren't authoritative — only the host runs the
        engine, so a client that somehow ended up with the button
        visible must NOT call end_betting_round locally (that crashed
        the client when it tried to deal a new community card from a
        deck that doesn't exist on its side). We just hide the button
        and let the host's broadcast drive the next street.
        """
        if not getattr(self, 'waiting_for_human', False):
            return
        self.waiting_for_human = False
        self._show_next_card_button(False)
        if self.network_mode == "client":
            return
        # Mark everyone with chips as having acted so end_betting_round fires.
        for p in self.players:
            if p.active:
                p.actions_this_round = max(1, p.actions_this_round)
        self.end_betting_round()
        # If we're still in a multi-way all-in runout AND there's
        # another street coming, show the button again immediately
        # — the user clicks once per board card. end_betting_round
        # already advanced the street and dealt the new community
        # card; we just need to re-arm the pause UI.
        if self._needs_allin_runout_pause():
            self._await_next_card()

    def _enter_spectator_mode(self):
        """After fold, enable God Mode + Show Tells and show ◀ ▶ street nav.
        Spectators do NOT block gameplay — the game keeps proceeding for the
        active players; nav buttons just scroll through snapshots."""
        self._hero_folded_spectating = True
        self._spectator_continue_all = False

        # Remember the pre-spectator state so we can restore it on exit.
        # If the user already had God Mode / Show Tells on manually, those
        # stay on; the spectator-auto-enabled ones go back off.
        self._pre_spectator_god_mode = self.god_mode_cb.isChecked()
        self._pre_spectator_stats = self.stats_cb.isChecked()

        # Turn on God Mode and Show Tells. Mark these as auto-toggled
        # (so the mid-hand-assist tracking knows NOT to flag them in
        # the summary). The boxes are disabled outside spectator mode
        # — temporarily enable them so setChecked actually fires the
        # state-change handlers (a disabled QCheckBox silently
        # ignores programmatic toggles). _exit_spectator_mode flips
        # them back off.
        self._spectator_auto_toggle = True
        try:
            self.god_mode_cb.setEnabled(True)
            self.stats_cb.setEnabled(True)
            if not self.god_mode_cb.isChecked():
                self.god_mode_cb.setChecked(True)
            if not self.stats_cb.isChecked():
                self.stats_cb.setChecked(True)
        finally:
            self._spectator_auto_toggle = False

        # Show spectator buttons in place of action buttons. We hide
        # both the regular toolbar set (fold/check/call/raise) AND the
        # Theory-of-Mind tab's mirror buttons (tom_*_btn) so the user
        # doesn't see a row of greyed-out controls floating in the
        # spectator view. The lazy "Next Card" button (created on
        # demand by _show_next_card_button) is hidden the same way.
        for attr in ('fold_btn', 'check_btn', 'call_btn', 'raise_btn',
                     'tom_fold_btn', 'tom_check_btn',
                     'tom_call_btn', 'tom_raise_btn',
                     'next_card_btn'):
            btn = getattr(self, attr, None)
            if btn is not None:
                try:
                    btn.setVisible(False)
                except RuntimeError:
                    pass

        if not hasattr(self, '_spectator_next_btn'):
            btn_style = ("QPushButton { font-size: 14px; font-weight: bold; "
                         "border-radius: 5px; padding: 6px 10px; "
                         "background-color: #357; color: white; }"
                         "QPushButton:hover { background-color: #468; }"
                         "QPushButton:disabled { background-color: #234; color: #678; }")
            # Three compact buttons stacked vertically inside the
            # spectator button column on the RIGHT of the stats panel.
            # 170×44 each + 8 px spacing = ~152 px tall, fits inside
            # the StatsPanel's 260-300 px height.
            self._spectator_prev_btn = QPushButton("◀ Previous Street")
            self._spectator_prev_btn.setFixedSize(170, 44)
            self._spectator_prev_btn.setStyleSheet(
                btn_style.replace('#357', '#553').replace('#468', '#664'))
            self._spectator_prev_btn.setShortcut("Left")
            self._spectator_prev_btn.clicked.connect(self._spectator_prev)

            self._spectator_next_btn = QPushButton("Next Street ▶")
            self._spectator_next_btn.setFixedSize(170, 44)
            self._spectator_next_btn.setStyleSheet(btn_style)
            self._spectator_next_btn.setShortcut("Right")
            self._spectator_next_btn.clicked.connect(self._spectator_next)

            self._spectator_close_btn = QPushButton("Close View")
            self._spectator_close_btn.setFixedSize(170, 44)
            self._spectator_close_btn.setStyleSheet(
                btn_style.replace('#357', '#633').replace('#468', '#844')
            )
            self._spectator_close_btn.setShortcut("Esc")
            self._spectator_close_btn.setToolTip(
                "Return to the default table view (turns off God Mode "
                "and Show Tells if they were auto-enabled by spectator "
                "mode). Esc shortcut."
            )
            self._spectator_close_btn.clicked.connect(self._exit_spectator_mode)

            # Drop the three buttons into the dedicated column to the
            # RIGHT of the stats panel — built in _build_ui at the same
            # time the StatsPanel is constructed. Using the stats-row
            # column keeps them out of the action button row (which
            # would overlap the table's "<winner> wins $X" message
            # and the bottom edges of the player panels).
            spec_col = getattr(self, '_spectator_button_col_layout', None)
            if spec_col is not None:
                spec_col.addWidget(self._spectator_prev_btn)
                spec_col.addWidget(self._spectator_next_btn)
                spec_col.addWidget(self._spectator_close_btn)
                spec_col.addStretch()
            else:
                # Defensive fallback — older builds without the stats-
                # row column. Keep the buttons in the action row so
                # spectator mode at least works.
                fallback = getattr(self, '_action_layout', None) \
                    or self.fold_btn.parentWidget().layout()
                fallback.addWidget(self._spectator_prev_btn)
                fallback.addSpacing(12)
                fallback.addWidget(self._spectator_next_btn)
                fallback.addSpacing(12)
                fallback.addWidget(self._spectator_close_btn)

        # Show the dedicated button column (no-op if we used the
        # fallback path above).
        if hasattr(self, '_spectator_button_box'):
            self._spectator_button_box.setVisible(True)

        self._spectator_prev_btn.setVisible(True)
        self._spectator_next_btn.setVisible(True)
        self._spectator_close_btn.setVisible(True)
        self._spectator_close_btn.setEnabled(True)

        # Pin the view to a snapshot of the moment-of-fold so the live
        # game (which keeps running for active players) doesn't drag the
        # board / log forward on the spectator's screen.  They click
        # Next Street to advance at their own pace.
        self._capture_spectator_snapshot()
        n = self._spectator_snapshot_count()
        self._spectator_view_idx = max(0, n - 1)
        self._spectator_show_snapshot(self._spectator_view_idx)
        self._update_spectator_nav_buttons()

    def _capture_spectator_snapshot(self):
        """Capture a snapshot of the current street's state.  Used at
        fold time and at hand end so the spectator can navigate through
        every street including the showdown."""
        try:
            street = STREETS[self.street_idx] if self.street_idx < len(STREETS) else "Showdown"
        except Exception:
            street = "Preflop"
        self._spectator_record_snapshot(
            street, self.street_idx, self.board, self.action_log)

    def _exit_spectator_mode(self):
        """Restore normal UI after spectator hand ends.
        Roll God Mode / Show Tells back to whatever they were BEFORE we
        auto-toggled them on for spectator viewing — so a folded player
        starts the next hand with the assists off (unless they had them on
        manually before folding)."""
        was_spectating = self._hero_folded_spectating
        self._hero_folded_spectating = False
        self._spectator_continue_all = False
        self._spectator_view_idx = -1
        self._spectator_street_snapshots = []

        # Hide spectator buttons + the dedicated column, restore action buttons.
        if hasattr(self, '_spectator_next_btn'):
            self._spectator_next_btn.setVisible(False)
        if hasattr(self, '_spectator_prev_btn'):
            self._spectator_prev_btn.setVisible(False)
        if hasattr(self, '_spectator_close_btn'):
            self._spectator_close_btn.setVisible(False)
        if hasattr(self, '_spectator_button_box'):
            self._spectator_button_box.setVisible(False)
        # Bring back the regular fold/check/call/raise rows AND the ToM
        # tab's mirror buttons; whether they're enabled is decided
        # later by enable_human_actions / disable_human_actions.
        for attr in ('fold_btn', 'check_btn', 'call_btn', 'raise_btn',
                     'tom_fold_btn', 'tom_check_btn',
                     'tom_call_btn', 'tom_raise_btn'):
            btn = getattr(self, attr, None)
            if btn is not None:
                try:
                    btn.setVisible(True)
                except RuntimeError:
                    pass

        # God Mode and Show Tells are spectator-only — turn them off
        # AND disable the checkboxes again so the user can't toggle
        # them manually until the next fold-into-spectator-mode.
        if was_spectating:
            self._spectator_auto_toggle = True
            try:
                self.god_mode_cb.setChecked(False)
                self.stats_cb.setChecked(False)
                self.god_mode_cb.setEnabled(False)
                self.stats_cb.setEnabled(False)
            finally:
                self._spectator_auto_toggle = False
            for attr in ('_pre_spectator_god_mode', '_pre_spectator_stats'):
                if hasattr(self, attr):
                    delattr(self, attr)

    def _spectator_snapshot_count(self) -> int:
        return len(getattr(self, '_spectator_street_snapshots', []))

    def _update_spectator_nav_buttons(self):
        """Enable/disable ◀ ▶ buttons based on snapshot list."""
        if not hasattr(self, '_spectator_prev_btn'):
            return
        n = self._spectator_snapshot_count()
        view = getattr(self, '_spectator_view_idx', -1)
        # view == -1 means "live / latest". Treat as last snapshot index.
        cur = (n - 1) if view < 0 else view
        try:
            self._spectator_prev_btn.setEnabled(n > 0 and cur > 0)
            # Forward navigation only useful when viewing a past snapshot
            self._spectator_next_btn.setEnabled(n > 0 and cur < n - 1)
        except RuntimeError:
            pass  # buttons deleted

    def _spectator_record_snapshot(self, street: str, street_idx: int,
                                    board, action_log):
        """Record a per-street snapshot for spectator navigation.

        When the spectator is parked on the previously-latest snapshot
        (i.e. they've Next-Street'd all the way back to live but haven't
        explicitly chosen to follow live), advance their view_idx with
        the new snapshot.  Users who have pressed Previous Street stay
        parked.  The contract is: pressing Previous is the only way to
        STOP automatic advancement.
        """
        if not hasattr(self, '_spectator_street_snapshots'):
            self._spectator_street_snapshots = []
        snap = {
            'street': street,
            'street_idx': int(street_idx),
            'board': [str(c) for c in board],
            'action_log': list(action_log),
        }
        # Remember whether the spectator was on the latest snapshot
        # BEFORE we mutate the list. `view < 0` is the explicit "live"
        # mode; `view == len-1` is the implicit "happened to be on the
        # last one" mode — both should follow new streets.
        prev_len = len(self._spectator_street_snapshots)
        prev_view = int(getattr(self, '_spectator_view_idx', -1))
        was_on_latest = (prev_view < 0
                         or (prev_len > 0 and prev_view == prev_len - 1))
        for i, existing in enumerate(self._spectator_street_snapshots):
            if existing.get('street_idx') == snap['street_idx']:
                self._spectator_street_snapshots[i] = snap
                # Same-street update — if parked here, refresh the view.
                if (prev_view >= 0
                        and prev_view == i
                        and getattr(self, '_hero_folded_spectating', False)):
                    self._spectator_show_snapshot(i)
                self._update_spectator_nav_buttons()
                return
        self._spectator_street_snapshots.append(snap)
        # If the user was tracking live, keep tracking live by sliding
        # the view to the just-appended snapshot.  If they had used
        # Previous Street to park on an older snapshot, leave them be.
        if (was_on_latest
                and getattr(self, '_hero_folded_spectating', False)):
            self._spectator_view_idx = len(
                self._spectator_street_snapshots) - 1
            self._spectator_show_snapshot(self._spectator_view_idx)
        self._update_spectator_nav_buttons()

    def _spectator_show_snapshot(self, idx: int):
        """Render the snapshot at idx (board cards + action log)."""
        snaps = getattr(self, '_spectator_street_snapshots', [])
        if not snaps or idx < 0 or idx >= len(snaps):
            return
        snap = snaps[idx]
        board_cards = []
        for c in snap.get('board', []):
            try:
                board_cards.append(eval7.Card(c))
            except Exception:
                pass
        try:
            self.table.set_board(board_cards)
            self.table.set_street(snap.get('street', ''))
            self.table.update()
        except Exception:
            pass
        # Replace the visible action-log strip with this snapshot's tail.
        # Only touch the displayed label — self.action_log stays as the
        # live log so future snapshots and outgoing broadcasts keep
        # working unchanged.
        try:
            log = list(snap.get('action_log', []))[-5:]
            # Live action_log stays untouched so future snapshots and
            # broadcasts keep using the authoritative tail; only the
            # visible strip flips to this snapshot's content.
            try:
                self.log_label.setText(self._format_action_log_html(log))
            except AttributeError:
                self.log_label.setText(" | ".join(log))
        except Exception:
            pass

    def _spectator_prev(self):
        """View previous street snapshot."""
        n = self._spectator_snapshot_count()
        if n == 0:
            return
        view = getattr(self, '_spectator_view_idx', -1)
        cur = (n - 1) if view < 0 else view
        if cur > 0:
            self._spectator_view_idx = cur - 1
            self._spectator_show_snapshot(self._spectator_view_idx)
            self._update_spectator_nav_buttons()

    def _spectator_next(self):
        """View next street snapshot.

        Stepping forward to the most recent snapshot drops the view back
        into "live" mode (view_idx = -1) so subsequent streets continue
        to auto-follow the action.  Previous Street is the only way to
        leave live mode and freeze the view.
        """
        n = self._spectator_snapshot_count()
        if n == 0:
            return
        view = getattr(self, '_spectator_view_idx', -1)
        cur = (n - 1) if view < 0 else view
        if cur < n - 1:
            new_idx = cur + 1
            # If we've returned to the latest snapshot, switch to live
            # mode so any future street advances the view automatically.
            if new_idx >= n - 1:
                self._spectator_view_idx = -1
                self._spectator_show_snapshot(n - 1)
            else:
                self._spectator_view_idx = new_idx
                self._spectator_show_snapshot(new_idx)
            self._update_spectator_nav_buttons()

    def human_action(self, action, amount):
        """Process human player's action."""
        if not self.waiting_for_human:
            return

        # Confirm any call or raise that would commit > 50 % of the
        # hero's stack this round. Easy mis-clicks (mistaken Call,
        # over-sized Raise) used to lose huge pots silently — pop
        # OK / Cancel so the user has a moment to back out.
        if action in ('c', 'r'):
            hero_seat = self.my_seat if self.my_seat is not None else 0
            if 0 <= hero_seat < len(self.players):
                hero = self.players[hero_seat]
                # `amount` is the TOTAL commitment-this-round for raises
                # (call + raise above), 0 for plain calls. For a call
                # we charge the difference between the table's current
                # bet and what the hero already has in this round.
                already_in = hero.bet_in_round
                if action == 'r':
                    extra = max(0, int(amount) - already_in)
                else:
                    extra = max(0, self.current_bet - already_in)
                if hero.stack > 0 and extra > hero.stack * 0.5:
                    pct = int(round(100 * extra / max(1, hero.stack)))
                    label = "raise" if action == 'r' else "call"
                    if not self._confirm_big_bet(label, extra, pct):
                        # User cancelled — leave action buttons enabled
                        # so they can pick again.
                        return

        self.disable_human_actions()

        # If hero folds, enter spectator mode
        if action == 'f':
            self._enter_spectator_mode()

        # If in network client mode, send action to server
        if self.network_mode == "client" and self.network_client:
            # Convert action code to readable action
            action_name = {'f': 'fold', 'c': 'call', 'r': 'raise'}.get(action, action)
            if action == 'c' and self.current_bet == 0:
                action_name = 'check'
            self.network_client.send_action(action_name, amount)
            self.waiting_for_human = False
            return

        # Local play
        player = self.players[0]
        self.process_action(player, 0, action, amount)

    def _confirm_big_bet(self, label: str, amount: int, pct: int) -> bool:
        """OK/Cancel dialog when a single action commits > 50 % of stack.

        Returns True iff the user clicks OK. Uses the same light-grey
        palette as the Game Over dialog so the prompt is readable
        regardless of which window's stylesheet we descend from.
        """
        msg = QMessageBox(self)
        # NoIcon removes the big red ! glyph and the wide blank column it
        # used to reserve on the left side of the dialog.
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle("Confirm big bet")
        msg.setTextFormat(Qt.TextFormat.RichText)
        # Both lines render at the same 24px weight so the "Are you sure"
        # confirmation reads with the same emphasis as the headline.
        msg.setText(
            f"<div style='font-size:24px; font-weight:bold; "
            f"color:#000; margin-bottom:8px;'>"
            f"This {label} commits "
            f"<span style='color:#a00000'>${amount:,}</span> — "
            f"<span style='color:#a00000'>{pct}%</span> of your stack."
            f"</div>"
            f"<div style='font-size:24px; font-weight:bold; "
            f"color:#000; margin-top:4px;'>"
            f"Are you sure you want to continue?"
            f"</div>"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        # min-width bumped to 720 so "100% of your stack" can't get
        # truncated by the QMessageBox auto-sizer.
        msg.setStyleSheet(
            "QMessageBox { background-color: #f0f0f0; }"
            "QMessageBox QLabel { color: #000; background-color: transparent;"
            " font-size: 24px; min-width: 720px; padding: 14px 10px; }"
            "QMessageBox QPushButton { font-size: 18px; padding: 10px 28px;"
            " min-width: 120px; }"
        )
        return msg.exec() == QMessageBox.StandardButton.Ok

    def show_raise_dialog(self):
        """Show dialog to select a raise.

        Semantics: the dialog asks for the RAISE amount above the call. It
        returns the TOTAL commitment this round (call + raise) via
        get_value(), which is what process_action() expects.

        Min raise = max(BB, last_raise_size) — enforces the No-Limit rule
        that a raise must be at least as large as the previous raise.
        """
        # Use the correct hero seat (seat 0 for local/host, my_seat for client)
        hero_seat = self.my_seat if self.network_mode == "client" and self.my_seat is not None else 0
        player = self.players[hero_seat]
        to_call = int(self.current_bet - player.bet_in_round)
        _, bb_amount = BLIND_LEVELS[self.blind_level]
        prev_raise = int(getattr(self, 'last_raise_size', bb_amount))
        min_raise_above = max(int(bb_amount), prev_raise)
        max_raise_above = int(player.stack) - to_call  # can't raise more than stack
        if max_raise_above < 1:
            # No chips left to raise with — treat as call / all-in.
            self.human_action('r', int(player.stack))
            return

        if max_raise_above <= min_raise_above:
            # Only room to shove (an all-in is always allowed even if it's
            # below the legal min raise).
            self.human_action('r', int(player.stack))
            return

        dialog = RaiseDialog(
            to_call, min_raise_above, max_raise_above,
            int(self.pot), self, bb_amount, prev_raise_size=prev_raise,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            amount = dialog.get_value()  # total commitment (call + raise)
            self.human_action('r', amount)

    def process_bot_action(self):
        """Process a bot player's action."""
        player = self.players[self.current_player_idx]

        # Check if this is a network human player (host mode)
        if self.network_mode == "host" and self.current_player_idx in self.network_human_seats:
            # Request action from network player
            client_id = self.network_server.get_client_for_seat(self.current_player_idx)
            if client_id:
                _, bb_amount = BLIND_LEVELS[self.blind_level]
                to_call = self.current_bet - player.bet_in_round
                min_raise = to_call + bb_amount
                max_raise = player.stack

                self.waiting_for_network_action = True
                self.network_server.request_action(
                    client_id,
                    ['fold', 'call', 'raise'] if to_call > 0 else ['check', 'raise'],
                    to_call, min_raise, max_raise, self.pot
                )
                return  # Wait for network response

        _, bb_amount = BLIND_LEVELS[self.blind_level]
        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'current_bet': self.current_bet,
            'players': self.players,
            'bb_amount': bb_amount
        }

        action, amount = player.get_bot_action(game_state, False)
        self.process_action(player, self.current_player_idx, action, amount)

    def process_action(self, player, player_idx, action, amount):
        """Process a player's action."""
        to_call = self.current_bet - player.bet_in_round
        street = STREETS[self.street_idx]

        # Feed the per-player × 169-hand heatmap. Only preflop actions
        # advance the VPIP/PFR/called/folded counters; if to_call==0
        # and the player checks, that's the BB option — not VPIP.
        if street == 'Preflop' and player.hand:
            hand_key = self._hand_class(player.hand)
            is_check = (action == 'c' and to_call <= 0)
            if not is_check:
                self._bump_169_action(player.name, hand_key, action, street)

        # Track ALL player actions for hand summary
        action_str = ""
        if action == 'f':
            action_str = f"{player.name}: Folds"
        elif action == 'r':
            action_str = f"{player.name}: Raises to ${amount}"
        else:
            if to_call > 0:
                action_str = f"{player.name}: Calls ${to_call}"
            else:
                action_str = f"{player.name}: Checks"

        if street not in self.hand_history['street_actions']:
            self.hand_history['street_actions'][street] = []
        self.hand_history['street_actions'][street].append(action_str)

        # Track hero actions for interpretation
        if player.style == 'human':
            action_desc = ""
            if action == 'f':
                action_desc = f"folded on {street}"
            elif action == 'r':
                action_desc = f"raised to ${amount} on {street}"
            else:
                if to_call > 0:
                    action_desc = f"called ${to_call} on {street}"
                else:
                    action_desc = f"checked on {street}"
            self.hand_history['hero_actions'].append((street, action, action_desc))

        if action == 'f':
            player.active = False
            self.log_action(f"{player.name}: Folds")

        elif action == 'r':
            if self.raises_this_round >= 4:
                # Cap reached, just call
                amt = min(player.stack, to_call)
                player.stack -= amt
                player.bet_in_round += amt
                player.total_invested += amt
                self.pot += amt
                self.log_action(f"{player.name}: Calls ${amt} (cap)")
            else:
                _, bb_amount = BLIND_LEVELS[self.blind_level]
                # Enforce No-Limit min-raise rule: a raise must be at least
                # as large as the previous raise this round.
                prev_raise = int(getattr(self, 'last_raise_size', bb_amount))
                min_raise_above = max(int(bb_amount), prev_raise)
                min_total = to_call + min_raise_above
                actual_raise = max(amount, min_total)
                if player.stack <= actual_raise:
                    actual_raise = player.stack
                player.stack -= actual_raise
                player.bet_in_round += actual_raise
                player.total_invested += actual_raise
                # Compute the new raise size *above the previous bet level*
                # so the next raiser knows the new floor.
                new_raise_size = max(0, player.bet_in_round - self.current_bet)
                self.current_bet = player.bet_in_round
                self.pot += actual_raise
                self.log_action(f"{player.name}: Raises to ${player.bet_in_round}")
                self.last_raiser = player_idx
                self.raises_this_round += 1
                # Only update last_raise_size when this raise is at least the
                # min — an all-in for less ('short shove') doesn't reset the
                # floor for subsequent raisers.
                if new_raise_size >= min_raise_above:
                    self.last_raise_size = int(new_raise_size)

                # Visual cue — flash the raiser's panel.  Color graded by
                # raise size: small (≤25% pot) is a quiet pulse, medium is
                # orange, large (≥50% pot, e.g. all-in) is bright red.
                panel = self.get_panel(player_idx)
                if panel is not None and hasattr(panel, 'flash_raise'):
                    pot_before = max(0, self.pot - actual_raise)
                    color = self._flash_color_for_raise(new_raise_size, pot_before)
                    panel.flash_raise(color=color)

                # Reset actions so others must respond
                for p in self.players:
                    if p != player:
                        p.actions_this_round = 0

        else:  # Call/Check
            if to_call > 0:
                amt = min(player.stack, to_call)
                player.stack -= amt
                player.bet_in_round += amt
                player.total_invested += amt
                self.pot += amt
                self.log_action(f"{player.name}: Calls ${amt}")
            else:
                self.log_action(f"{player.name}: Checks")

        player.actions_this_round += 1

        # Bracelets-style all-in counter
        if player.stack == 0 and action != 'f':
            self._record_all_in(player.name)

        # Broadcast action to network clients (host mode)
        if self.network_mode == "host" and self.network_server:
            action_name = {'f': 'fold', 'r': 'raise', 'c': 'call'}.get(action, 'check')
            if action == 'c' and to_call == 0:
                action_name = 'check'
            stacks = {i: p.stack for i, p in enumerate(self.players)}
            self.network_server.broadcast_action(
                player_idx, player.name, action_name, amount, self.pot,
                stacks=stacks
            )

        # Update display
        self.update_all_panels()
        self.table.set_pot(self.pot)
        self.update_stats_display()

        # Move to next player
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

        # Check if round should continue
        if self.count_active() < 2:
            self.end_hand()
        else:
            # Check if betting is complete
            all_acted = all(p.actions_this_round > 0 for p in self.players if p.active and p.stack > 0)
            all_matched = all(p.bet_in_round == self.current_bet for p in self.players if p.active)

            if all_acted and all_matched:
                self.end_betting_round()
            else:
                self.process_next_player()

    def end_betting_round(self):
        """End the current betting round and move to next street."""
        # Capture stats for the street that just ended (for hand summary)
        current_street = STREETS[self.street_idx]
        self._capture_street_stats(current_street)

        # Snapshot the JUST-ENDED street so a folded spectator can
        # navigate back to it (with this street's full action tail).
        # Broadcast it so guests get the same history.
        try:
            self._spectator_record_snapshot(
                current_street, self.street_idx, self.board, self.action_log)
            if (self.network_mode == "host" and self.network_server
                    and hasattr(self.network_server, "broadcast_board_snapshot")):
                self.network_server.broadcast_board_snapshot(
                    current_street, self.street_idx,
                    [str(c) for c in self.board], list(self.action_log))
        except Exception:
            pass

        # Reset bets for next round
        for p in self.players:
            p.bet_in_round = 0

        self.current_bet = 0
        self.street_idx += 1

        if self.count_active() < 2 or self.street_idx >= len(STREETS):
            self.end_hand()
            return

        # Deal community cards
        street = STREETS[self.street_idx]
        if street == "Flop":
            self.board.extend(self.deck.deal(3))
        elif street in ["Turn", "River"]:
            self.board.extend(self.deck.deal(1))

        self.table.set_board(self.board)
        hero = self.players[0]
        self.table.set_hero_cards([str(c) for c in hero.hand] if hero.hand else [])
        self.table.set_street(street)
        self.log_action(f"--- {street} ---", include_stats=True)
        self.write_log(f"Board: {format_cards(self.board)}")

        # Network broadcast community cards
        if self.network_mode == "host" and self.network_server:
            cards = [str(c) for c in self.board]
            self.network_server.broadcast_community_cards(cards, street)
            # Snapshot the new street so folded clients can navigate to it.
            self.network_server.broadcast_board_snapshot(
                street, self.street_idx, cards, list(self.action_log))
            # Re-push hole cards to any folded clients so they keep seeing
            # all cards as new streets arrive.
            self._refresh_spectator_hole_cards()

        # Locally record a snapshot too (for the host's own spectator nav).
        self._spectator_record_snapshot(
            street, self.street_idx, self.board, self.action_log)

        # Track board + per-human-player equity for interpretation. We
        # capture every human (seat 0 plus all network_human_seats) so the
        # post-hand summary can name everyone, not just the host.
        self.hand_history['board_by_street'][street] = [str(c) for c in self.board]
        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'players': self.players,
            'current_bet': self.current_bet,
        }
        human_seats = {0} | set(getattr(self, 'network_human_seats', set()) or set())
        equities_for_street = {}
        for seat in human_seats:
            if 0 <= seat < len(self.players):
                p = self.players[seat]
                if p.active and p.hand:
                    eq, _, _ = p.calculate_current_stats(game_state, True)
                    equities_for_street[p.name] = eq
        self.hand_history['street_equities'][street] = equities_for_street

        # Update displays (only when viewing the live snapshot — if the
        # spectator has scrolled back to a past street, leave their view).
        if not getattr(self, '_hero_folded_spectating', False) or \
                getattr(self, '_spectator_view_idx', -1) < 0:
            self.update_all_panels()
            self.update_stats_display()
        else:
            # Still recompute equities/panels offscreen but don't move the
            # board view; the snapshot is what's on screen.
            self.update_all_panels()
            self.update_stats_display()
            self._spectator_show_snapshot(self._spectator_view_idx)
        self._update_spectator_nav_buttons()

        # Spectators DO NOT block gameplay — keep dealing the next betting
        # round immediately so bots and remaining humans can act.
        self._start_next_betting_round()

    def _resume_after_spectator_pause(self):
        """No-op kept for backwards compatibility — spectator no longer
        pauses the game."""
        pass

    def _start_next_betting_round(self):
        """Start a new betting round (from dealer + 1)."""
        self.current_player_idx = (self.dealer_idx + 1) % len(self.players)
        self.betting_round_init()

    def _build_side_pots(self):
        """Compute the main pot + every side pot from current investments.

        Returns a list of dicts in order from main → highest side pot:
            [{
                'label':       'Main pot' | 'Side pot 1' | ...,
                'amount':      int (chips in this pot),
                'eligible':    [Player, ...]  (active and capped above
                                this level),
                'cap_level':   int (per-player investment cap that
                                created this pot),
            }, ...]

        Folded players forfeit their share but their chips are still
        eligible to be won (they sit in whichever pot level their
        investment ladder reached).  Uncalled-overage at the top — a
        side pot whose only eligible player is one person — is flagged
        separately by callers via len(eligible) == 1.
        """
        active = [p for p in self.players if p.active]
        # Investment levels (sorted unique, > 0)
        levels = sorted(set(p.total_invested for p in self.players
                            if p.total_invested > 0))
        # First pass: build per-band slices.
        raw = []
        prev = 0
        for level in levels:
            band_amount = 0
            for p in self.players:
                band_amount += (min(p.total_invested, level)
                                - min(p.total_invested, prev))
            if band_amount > 0:
                eligible = [p for p in active if p.total_invested >= level]
                raw.append({
                    'amount': band_amount,
                    'eligible': eligible,
                    'cap_level': level,
                    'floor_level': prev,
                })
            prev = level

        # Second pass: merge consecutive bands that share the SAME
        # eligible set. A "side pot" should only appear when someone
        # active can't claim a band that someone else active can — i.e.
        # caused by an all-in player capping their eligibility. A band
        # created purely by a folded player's investment level (e.g.
        # someone paid the BB then folded) leaves the eligible set
        # identical to the next band's, so it doesn't deserve to be
        # split off as its own pot.
        merged = []
        for band in raw:
            if (merged
                    and {id(p) for p in merged[-1]['eligible']}
                    == {id(p) for p in band['eligible']}):
                merged[-1]['amount'] += band['amount']
                merged[-1]['cap_level'] = band['cap_level']
            else:
                merged.append(dict(band))

        # Label only after merging so numbering reflects the user-
        # visible pots, not the internal bands.
        for idx, pot in enumerate(merged):
            pot['label'] = "Main pot" if idx == 0 else f"Side pot {idx}"
        return merged

    def end_hand(self):
        """End the hand and determine winner."""
        self.disable_human_actions()
        # Hand is complete — re-enable "New Hand". Network-client mode
        # keeps the button disabled separately (the host controls flow).
        self._hand_in_progress = False
        if self.network_mode != "client":
            self.new_hand_btn.setEnabled(True)
        # Spectator (folded) view is intentionally NOT torn down here —
        # the user keeps God Mode + Show Tells + the ◀ ▶ street nav
        # active until they explicitly click "Close View" or start the
        # next hand (deal_hand calls _exit_spectator_mode). Hand-summary
        # popups still appear because they're driven by
        # show_hand_summary() further down and don't depend on
        # spectator state.

        # Capture final street stats before ending (guard against out-of-bounds
        # since end_betting_round already increments street_idx past the last street)
        if self.street_idx < len(STREETS):
            final_street = STREETS[self.street_idx]
            self._capture_street_stats(final_street)

        active = [p for p in self.players if p.active]

        # Build the side-pot ladder once. Used for both single-active
        # and showdown branches so chip flows are always explicit.
        side_pots = self._build_side_pots()
        # Per-pot results we'll log + broadcast (label, amount, winners,
        # is_uncalled-refund).
        self.last_pot_breakdown = []

        winners = []          # showdown winners (across all contested pots)
        total_won = {}        # player -> chips received this hand

        if len(active) == 1:
            # Everyone but one player folded. Folded players forfeit
            # their chips; the lone active player collects every pot
            # they were ever eligible for. Any pot at a cap level
            # ABOVE the lone player's investment had only folded
            # contributors — those chips also go to the lone player
            # (no one is contesting them).
            winner = active[0]
            for pot in side_pots:
                if not pot['amount']:
                    continue
                winner.stack += pot['amount']
                total_won[winner] = total_won.get(winner, 0) + pot['amount']
                self.last_pot_breakdown.append({
                    'label': pot['label'],
                    'amount': pot['amount'],
                    'winners': [winner.name],
                    'uncalled': False,
                })
            if winner not in winners:
                winners.append(winner)
            net_profit = total_won.get(winner, 0) - winner.total_invested
            self.table.set_pot(net_profit)
            self.log_action(f"{winner.name} wins ${net_profit}!")
            self.table.set_message(f"{winner.name} wins ${net_profit}!")
            self.write_log(f"Winner: {winner.name} - ${net_profit} (others folded)")
            for pot in self.last_pot_breakdown:
                self.write_log(
                    f"  {pot['label']}: ${pot['amount']} -> {winner.name}"
                )
        else:
            # Showdown
            self.at_showdown = True
            self.table.set_street("Showdown")

            while len(self.board) < 5:
                self.board.extend(self.deck.deal(1))
            self.table.set_board(self.board)

            board_cards = [eval7.Card(str(c)) for c in self.board]

            player_ranks = {}
            results = []
            for p in active:
                hand_cards = [eval7.Card(str(c)) for c in p.hand]
                full_hand = hand_cards + board_cards
                rank = eval7.evaluate(full_hand)
                hand_type = eval7.handtype(rank)
                player_ranks[p] = rank
                results.append(f"{p.name}: {hand_type}")

            for r in results:
                self.log_action(r)

            for pot in side_pots:
                amount = pot['amount']
                eligible = pot['eligible']
                if amount <= 0:
                    continue
                if not eligible:
                    # No active player can claim this pot (everyone at
                    # this cap level folded). Refund the band to the
                    # contributors who put chips in at this level.
                    # This is rare but possible if all higher-stack
                    # players folded simultaneously.
                    refunds = []
                    prev = 0
                    # Find the level immediately below this pot's cap
                    for prior in side_pots:
                        if prior is pot:
                            break
                        prev = prior['cap_level']
                    for p in self.players:
                        share = (min(p.total_invested, pot['cap_level'])
                                 - min(p.total_invested, prev))
                        if share > 0:
                            p.stack += share
                            total_won[p] = total_won.get(p, 0) + share
                            refunds.append(p.name)
                    self.last_pot_breakdown.append({
                        'label': pot['label'],
                        'amount': amount,
                        'winners': refunds,
                        'uncalled': True,
                    })
                    self.write_log(
                        f"  {pot['label']}: ${amount} refunded to "
                        f"{', '.join(refunds)} (no active claimant)"
                    )
                    continue

                if len(eligible) == 1:
                    # Only one active player can claim this band.
                    # Distinguish a true uncalled-bet refund (sole
                    # eligible contributed every chip in the band)
                    # from an uncontested win (folded players also
                    # contributed, but no other active player matched).
                    sole = eligible[0]
                    sole_share = (
                        min(sole.total_invested, pot['cap_level'])
                        - min(sole.total_invested, pot['floor_level'])
                    )
                    refund = (sole_share == amount)
                    sole.stack += amount
                    total_won[sole] = total_won.get(sole, 0) + amount
                    self.last_pot_breakdown.append({
                        'label': pot['label'],
                        'amount': amount,
                        'winners': [sole.name],
                        'uncalled': refund,
                    })
                    if refund:
                        self.write_log(
                            f"  {pot['label']}: ${amount} returned to "
                            f"{sole.name} (uncalled)"
                        )
                    else:
                        if sole not in winners:
                            winners.append(sole)
                        self.write_log(
                            f"  {pot['label']}: ${amount} -> "
                            f"{sole.name} (uncontested)"
                        )
                    continue

                best_rank = max(player_ranks[p] for p in eligible)
                pot_winners = [p for p in eligible
                               if player_ranks[p] == best_rank]
                win_share = amount // len(pot_winners)
                # Spread any rounding remainder to the first winner
                # so chip totals stay conserved.
                remainder = amount - win_share * len(pot_winners)
                for idx, w in enumerate(pot_winners):
                    share = win_share + (remainder if idx == 0 else 0)
                    w.stack += share
                    total_won[w] = total_won.get(w, 0) + share
                    if w not in winners:
                        winners.append(w)
                self.last_pot_breakdown.append({
                    'label': pot['label'],
                    'amount': amount,
                    'winners': [w.name for w in pot_winners],
                    'uncalled': False,
                })
                self.write_log(
                    f"  {pot['label']}: ${amount} -> "
                    f"{', '.join(w.name for w in pot_winners)}"
                )

            if winners:
                winner_msgs = []
                for w in winners:
                    net_profit = total_won.get(w, 0) - w.total_invested
                    winner_msgs.append(f"{w.name} (${net_profit})")
                winner_names = ", ".join(winner_msgs)
                # Append a compact side-pot tag when there's more than
                # one pot, so the user immediately sees this was a
                # multi-pot finish.
                contested = [p for p in self.last_pot_breakdown
                             if not p['uncalled']]
                if len(contested) > 1:
                    pot_tag = " | " + ", ".join(
                        f"{p['label']} ${p['amount']}->{'/'.join(p['winners'])}"
                        for p in contested
                    )
                else:
                    pot_tag = ""
                self.table.set_message(f"Winner: {winner_names}{pot_tag}")
                self.write_log(f"WINNER: {winner_names}!")

        # Log final stacks and gain/loss
        self.write_log("Final Stacks:")
        for p in self.players:
            self.write_log(f"  {p.name}: ${p.stack}")

        # Log gain/loss for each player
        if hasattr(self, 'starting_stacks'):
            self.write_log("Hand Results (Gain/Loss):")
            for p in self.players:
                start = self.starting_stacks.get(p.name, p.stack)
                change = p.stack - start
                if change > 0:
                    self.write_log(f"  {p.name}: +${change}")
                elif change < 0:
                    self.write_log(f"  {p.name}: -${abs(change)}")
                else:
                    self.write_log(f"  {p.name}: $0 (broke even)")

        # Bracelets-style per-hand stat updates + CHIP COUNT screen + table
        # snapshot so post-game annotation has them per-hand.
        try:
            winners_in_scope = active if len(active) == 1 else (winners if 'winners' in locals() else [])
            winners_names = [w.name for w in winners_in_scope] if winners_in_scope else []
            showdown_active_names = (
                [p.name for p in active] if getattr(self, 'at_showdown', False)
                else []
            )
            self._finalize_hand_stats(winners_names, showdown_active_names)
            self._log_chip_count()
            self._log_table_stats()
        except Exception as ex:
            print(f"[log] per-hand stat update failed: {ex}")

        # Log range accuracy analysis (get ranges from ToM panel)
        if hasattr(self, 'tom_panel') and self.tom_panel.final_range_estimates:
            accuracy_results = self.check_range_accuracy(self.players, self.tom_panel.final_range_estimates)
            if accuracy_results:
                self.write_log("\n[RANGE ACCURACY CHECK]")
                for result in accuracy_results:
                    self.write_log(result)
                total = self.range_accuracy_stats['total_hands']
                hits = self.range_accuracy_stats['hits']
                if total > 0:
                    pct = hits / total * 100
                    self.write_log(f"  Session accuracy: {hits}/{total} ({pct:.1f}%)")

        # Generate and display hand interpretation (Stats button opens graphical summary)
        self.show_hand_interpretation(active, winners if len(active) > 1 else active,
                                       results if len(active) > 1 else None)

        # Network broadcast hand end with summary data
        if self.network_mode == "host" and self.network_server:
            winner_indices = [self.players.index(w) for w in (winners if len(active) > 1 else active)]
            shown_hands = {self.players.index(p): [str(c) for c in p.hand] for p in active if p.hand}

            try:
                # Build hand summary data for client
                player_results = {}
                if hasattr(self, 'starting_stacks'):
                    for p in self.players:
                        start = self.starting_stacks.get(p.name, p.stack)
                        end = p.stack
                        player_results[p.name] = [start, end, end - start]

                player_hands = {}
                for p in self.players:
                    if p.hand:
                        player_hands[p.name] = [str(c) for c in p.hand]

                # Convert street_stats tuples to lists for JSON serialization
                serializable_stats = {}
                for street, stats_list in self.hand_history.get('street_stats', {}).items():
                    serializable_stats[street] = [list(s) for s in stats_list]

                # Compute made hands for each street
                board_by_street = self.hand_history.get('board_by_street', {})
                made_hands_by_street = {}
                for street in ['Preflop', 'Flop', 'Turn', 'River']:
                    board = board_by_street.get(street, [])
                    made_hands_by_street[street] = {}
                    for p in self.players:
                        if p.hand:
                            if street == 'Preflop':
                                made_hands_by_street[street][p.name] = self.categorize_preflop_hand(p.hand)
                            elif board:
                                made_hands_by_street[street][p.name] = self.describe_made_hand(p.hand, board)

                hand_summary = {
                    'street_stats': serializable_stats,
                    'street_actions': self.hand_history.get('street_actions', {}),
                    'board_by_street': board_by_street,
                    'player_results': player_results,
                    'player_hands': player_hands,
                    'made_hands_by_street': made_hands_by_street,
                    'pot_by_street': self.hand_history.get('pot_by_street', {}),
                }

                self.network_server.broadcast_hand_end(winner_indices, self.pot, shown_hands, hand_summary)
            except Exception as e:
                print(f"Error broadcasting hand summary: {e}")
                # Fall back to basic hand_end without summary
                self.network_server.broadcast_hand_end(winner_indices, self.pot, shown_hands)

            # Authoritative post-pot-distribution stacks so guests pick up the
            # winner's chip gain immediately (and any losers' chips stay 0
            # rather than reflecting the pre-distribution heuristic).
            self.network_server.broadcast_stack_update(
                {i: p.stack for i, p in enumerate(self.players)}
            )

        # Update display
        self.update_all_panels()

        # Capture a final "showdown" snapshot so a folded spectator can
        # navigate to the completed board + winner message.  Stored under
        # an out-of-range street_idx so it sits after Preflop/Flop/Turn/
        # River.  Host broadcasts so each client sees the same final
        # frame.
        showdown_idx = len(STREETS)
        try:
            self._spectator_record_snapshot(
                "Showdown", showdown_idx, self.board, self.action_log)
            if (self.network_mode == "host" and self.network_server
                    and hasattr(self.network_server, "broadcast_board_snapshot")):
                self.network_server.broadcast_board_snapshot(
                    "Showdown", showdown_idx,
                    [str(c) for c in self.board],
                    list(self.action_log))
        except Exception:
            pass
        # If hero is parked in spectator mode, refresh nav button states
        # and restore their frozen snapshot view (end_hand has been
        # mutating the live board/pot which would otherwise leak through).
        if getattr(self, '_hero_folded_spectating', False):
            self._update_spectator_nav_buttons()
            view_idx = getattr(self, '_spectator_view_idx', -1)
            if view_idx >= 0:
                self._spectator_show_snapshot(view_idx)

        # Move dealer button to next player with chips
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        attempts = 0
        while self.players[self.dealer_idx].stack <= 0 and attempts < len(self.players):
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
            attempts += 1

        # Hand has ended — re-enable the New Hand button so the user can
        # start the next one.
        if hasattr(self, 'new_hand_btn'):
            self.new_hand_btn.setEnabled(True)

        # Check for game over (only one player with chips)
        players_with_chips = [p for p in self.players if p.stack > 0]
        if len(players_with_chips) == 1:
            winner = players_with_chips[0]
            # If the hero won this game and they were playing the default
            # lineup, flip the persistent unlock so future games can mix
            # in the advanced bots.
            try:
                hero_seat = self.my_seat if self.my_seat is not None else 0
                if (0 <= hero_seat < len(self.players)
                        and winner is self.players[hero_seat]
                        and not self.beat_defaults_unlocked):
                    self.beat_defaults_unlocked = True
                    self.settings.setValue("beat_defaults_unlocked", True)
                    self.settings.sync()
            except Exception:
                pass
            self.show_game_over(winner)

    # Game-over dialogs match the "Confirm big bet" treatment: 24pt
    # bold body text, no warning glyph (which used to reserve a wide
    # blank column on the left), and a 720px min-width so the prompt
    # never wraps the question mid-sentence.
    _GAME_OVER_STYLE = (
        "QMessageBox { background-color: #f0f0f0; }"
        "QMessageBox QLabel { color: #000; background-color: transparent;"
        " font-size: 24px; min-width: 720px; padding: 14px 10px; }"
        "QMessageBox QPushButton { font-size: 18px; padding: 10px 28px; "
        "min-width: 120px; }"
    )

    def _game_over_question(self, text: str,
                            title: str = "Game Over") -> 'QMessageBox.StandardButton':
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<div style='font-size:24px; font-weight:bold; color:#000;'>"
            f"{text}</div>"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setStyleSheet(self._GAME_OVER_STYLE)
        return msg.exec()

    def _game_over_information(self, text: str,
                                title: str = "Game Over") -> None:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<div style='font-size:24px; font-weight:bold; color:#000;'>"
            f"{text}</div>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet(self._GAME_OVER_STYLE)
        msg.exec()

    def show_game_over(self, winner):
        """Show game over dialog and offer to play again."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle("Game Over!")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<div style='font-size:24px; font-weight:bold; color:#000;"
            f" margin-bottom:8px;'>"
            f"{winner.name} wins the game with ${winner.stack}!"
            f"</div>"
            f"<div style='font-size:24px; font-weight:bold; color:#000;'>"
            f"Would you like to play another game?</div>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setStyleSheet(self._GAME_OVER_STYLE)

        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.reset_game()
        else:
            self.close()

    def reset_game(self):
        """Reset the game for a new session."""
        for p in self.players:
            p.stack = STARTING_STACK
            p.reset_for_hand()
        self.hand_number = 0
        self.dealer_idx = 0
        self.pot = 0
        self.at_showdown = False
        self.action_history = []
        self.update_all_panels()
        self.table.set_board([])
        self.table.set_hero_cards([])
        self.table.set_pot(0)
        self.table.set_street("Preflop")
        self.table.set_message("Game reset! Click 'New Hand' to start.")
        self.log_label.setText("Game reset! Click 'New Hand' to start.")

    def categorize_preflop_hand(self, hand):
        """Categorize a preflop hand using poker terminology."""
        if not hand or len(hand) < 2:
            return "unknown"
        c1, c2 = str(hand[0]), str(hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        ranks = 'AKQJT98765432'
        r1_val = ranks.index(r1)
        r2_val = ranks.index(r2)
        is_pair = r1 == r2
        is_suited = s1 == s2

        if is_pair:
            if r1 in 'AK':
                return "premium pair"
            elif r1 in 'QJT':
                return "high pair"
            elif r1 in '987':
                return "medium pair"
            else:
                return "small pair"
        else:
            high = min(r1_val, r2_val)
            gap = abs(r1_val - r2_val)
            if high <= 1 and gap <= 1:  # AK
                return "big slick" if is_suited else "big slick offsuit"
            elif high <= 3 and gap <= 2:  # Broadway
                return "suited broadway" if is_suited else "broadway"
            elif is_suited and gap == 1:
                return "suited connector"
            elif is_suited and gap <= 2:
                return "suited one-gapper"
            elif r1 == 'A' or r2 == 'A':
                return "suited ace" if is_suited else "ace-rag"
            elif is_suited:
                return "suited cards"
            else:
                return "offsuit junk"

    def describe_made_hand(self, hole_cards, board):
        """Describe what made hand a player has using poker terminology.

        Uses the eval7 evaluator (the same engine that picks the winner at
        showdown) to decide the hand category, so the description always
        agrees with the showdown result. Layers on specific
        rank/kicker info on top of the category for nicer wording (e.g.
        'top pair (Ks)', 'set of 9s').
        """
        if not hole_cards or not board:
            return "no hand"

        # Convert to eval7 cards (the inputs are usually already eval7
        # cards, but the function is also called with string-like inputs
        # from the network path).
        try:
            hole_e7 = [c if isinstance(c, eval7.Card) else eval7.Card(str(c))
                       for c in hole_cards]
            board_e7 = [c if isinstance(c, eval7.Card) else eval7.Card(str(c))
                        for c in board]
        except Exception:
            return "unknown"

        # eval7 needs at least 5 total cards to evaluate; with hole+board
        # we always have at least 5 by the flop.
        if len(hole_e7) + len(board_e7) < 5:
            return "no hand"

        rank_value_e7 = eval7.evaluate(hole_e7 + board_e7)
        category = eval7.handtype(rank_value_e7).lower()  # e.g. "straight"

        # Pull out useful per-rank info for prettier descriptions.
        all_ranks = [str(c)[0] for c in hole_cards] + [str(c)[0] for c in board]
        hole_ranks = [str(c)[0] for c in hole_cards]
        board_ranks = [str(c)[0] for c in board]
        rank_counts = {}
        for r in all_ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1
        board_rank_counts = {}
        for r in board_ranks:
            board_rank_counts[r] = board_rank_counts.get(r, 0) + 1

        # Rank ordering for "top/middle/bottom" pair labelling.
        rank_order = 'AKQJT98765432'
        def rank_pos(r):
            return rank_order.index(r) if r in rank_order else 99

        # --- Category branches -------------------------------------------------
        if category == 'straight flush':
            return "straight flush"
        if category == 'quads' or category == 'four of a kind':
            quads = next((r for r, n in rank_counts.items() if n >= 4), None)
            return f"quads ({quads}s)" if quads else "four of a kind"
        if category == 'full house':
            trips = next((r for r, n in rank_counts.items() if n >= 3), None)
            pair = next((r for r, n in rank_counts.items()
                         if n >= 2 and r != trips), None)
            if trips and pair:
                return f"full house ({trips}s full of {pair}s)"
            return "full house"
        if category == 'flush':
            return "flush"
        if category == 'straight':
            return "straight"
        if category in ('trips', 'three of a kind'):
            trips = next((r for r, n in rank_counts.items() if n >= 3), None)
            # "Set" = pocket pair matched on board; "trips" = one hole +
            # board pair.
            if trips and hole_ranks[0] == hole_ranks[1] == trips:
                return f"set of {trips}s"
            if trips and board_rank_counts.get(trips, 0) >= 2:
                return f"trips ({trips}s)"
            return "three of a kind"
        if category == 'two pair':
            pairs = [r for r, n in rank_counts.items() if n >= 2]
            hero_in_pairs = [r for r in hole_ranks if r in pairs]
            if hero_in_pairs:
                return "two pair"
            # Both pairs on the board → hero plays the board with a kicker.
            return "two pair (board)"
        if category == 'pair':
            # Identify the pair's rank.
            pair_rank = next((r for r, n in rank_counts.items() if n >= 2), None)
            if not pair_rank:
                return "pair"
            # Pocket pair vs board pair.
            if hole_ranks[0] == hole_ranks[1] == pair_rank:
                if all(rank_pos(pair_rank) < rank_pos(br) for br in board_ranks):
                    return f"overpair ({pair_rank}{pair_rank})"
                return f"pocket pair ({pair_rank}{pair_rank})"
            if pair_rank in hole_ranks and pair_rank in board_ranks:
                # Top / second / bottom relative to the board.
                sorted_board = sorted(set(board_ranks), key=rank_pos)
                if pair_rank == sorted_board[0]:
                    return f"top pair ({pair_rank}s)"
                if len(sorted_board) > 1 and pair_rank == sorted_board[1]:
                    return f"second pair ({pair_rank}s)"
                return f"bottom pair ({pair_rank}s)"
            # Pair lives entirely on the board → hero just plays the kicker.
            return "pair on board"
        if category == 'high card':
            # Pre-river, surface obvious draws so the description is useful.
            if len(board) < 5:
                hole_suits = [str(c)[1] for c in hole_cards]
                all_suits = [str(c)[1] for c in hole_cards] + [str(c)[1] for c in board]
                suit_counts = {}
                for s in all_suits:
                    suit_counts[s] = suit_counts.get(s, 0) + 1
                for suit in hole_suits:
                    if suit_counts.get(suit, 0) == 4:
                        return "flush draw"
                # Straight draw — any 4 of 5 consecutive ranks (not the wheel).
                vals = sorted(set(rank_pos(r) for r in all_ranks))
                for i in range(len(vals) - 3):
                    if vals[i+3] - vals[i] <= 4:
                        return "straight draw"
            high = min(hole_ranks, key=rank_pos)
            return f"{high}-high"
        # Fallback: trust eval7's category string.
        return category

    def analyze_card_impact(self, new_card, board, active_players):
        """Analyze how a new card impacted the hand."""
        card_rank = new_card[0]
        card_suit = new_card[1]
        board_suits = [str(c)[1] for c in board]
        board_ranks = [str(c)[0] for c in board]

        impacts = []

        # Check if it completed a flush
        suit_count = board_suits.count(card_suit)
        if suit_count >= 3:
            impacts.append(f"possible flush completion in {card_suit}")

        # Check if it paired the board
        if card_rank in board_ranks[:-1]:
            impacts.append("paired the board")

        # Check if it's a high card
        if card_rank in 'AKQ':
            impacts.append(f"{card_rank} on board - could have hit someone")

        # Check for straight possibilities
        ranks = 'AKQJT98765432'
        board_vals = sorted([ranks.index(r) for r in board_ranks])
        if board_vals[-1] - board_vals[0] <= 4:
            impacts.append("straight possible")

        return " | ".join(impacts) if impacts else None

    def explain_loss(self, loser, winner, board):
        """Explain why a player lost in poker terminology."""
        if not loser.hand or not winner.hand:
            return "folded"

        loser_desc = self.describe_made_hand(loser.hand, board)
        winner_desc = self.describe_made_hand(winner.hand, board)

        # Check for specific situations
        loser_ranks = [str(c)[0] for c in loser.hand]
        winner_ranks = [str(c)[0] for c in winner.hand]

        # Outkicked
        if 'pair' in loser_desc and 'pair' in winner_desc:
            return f"outkicked - had {loser_desc}"

        # Missed draw
        if 'draw' in loser_desc:
            return f"missed the {loser_desc}"

        # Dominated
        if loser_ranks[0] in winner_ranks or loser_ranks[1] in winner_ranks:
            return f"dominated - {loser_desc} vs {winner_desc}"

        return f"lost with {loser_desc} vs {winner_desc}"

    def _show_local_graphical_summary(self, parent_to_restore=None):
        """Host/single-player wrapper around show_hand_summary that wires
        the parent-restore callback so dismissing Stats brings the text
        Hand Summary back to the front."""
        # Capture the dialog created inside show_hand_summary by tracking
        # the latest one appended to _open_hand_dialogs.
        before = list(getattr(self, '_open_hand_dialogs', []) or [])
        self.show_hand_summary()
        after = list(getattr(self, '_open_hand_dialogs', []) or [])
        new_dialogs = [d for d in after if d not in before]
        if parent_to_restore is not None:
            for d in new_dialogs:
                try:
                    # `finished` fires whenever the dialog is dismissed
                    # (close button, ESC, accept/reject) — `destroyed` only
                    # fires on actual object delete, which most paths skip.
                    d.finished.connect(
                        lambda _=0, p=parent_to_restore:
                            self._restore_parent_dialog(p))
                except RuntimeError:
                    pass
        if not new_dialogs:
            # Nothing opened (e.g. no street_stats); restore immediately.
            self._restore_parent_dialog(parent_to_restore)

    def show_hand_summary(self):
        """Show the graphical hand summary dialog with stacked bar charts."""
        # Build player results (start, end, change)
        player_results = {}
        for p in self.players:
            start = self.starting_stacks.get(p.name, p.stack)
            end = p.stack
            change = end - start
            player_results[p.name] = (start, end, change)

        # Get data from hand history
        street_stats = self.hand_history.get('street_stats', {})
        street_actions = self.hand_history.get('street_actions', {})
        board_by_street = self.hand_history.get('board_by_street', {})

        # Collect player hole cards
        player_hands = {}
        for p in self.players:
            if p.hand:
                player_hands[p.name] = [str(c) for c in p.hand]

        # Collect made hands at each street
        made_hands_by_street = {}
        for street in ['Preflop', 'Flop', 'Turn', 'River']:
            board = board_by_street.get(street, [])
            made_hands_by_street[street] = {}
            for p in self.players:
                if p.hand:
                    if street == 'Preflop':
                        # For preflop, show starting hand category
                        made_hands_by_street[street][p.name] = self.categorize_preflop_hand(p.hand)
                    elif board:
                        made_hands_by_street[street][p.name] = self.describe_made_hand(p.hand, board)

        # Only show if we have some stats
        if not street_stats:
            return

        # If we already have cached reflections for this hand (e.g. the
        # user opened Hand Log first), seed the dialog with them instead
        # of showing the "Awaiting Claude" placeholder.
        cached = self._get_cached_hand_reflections()
        seed_reflections = (cached or {}).get('street_reflections', {})

        dialog = HandSummaryDialog(
            street_stats=street_stats,
            street_actions=street_actions,
            board_by_street=board_by_street,
            player_results=player_results,
            player_hands=player_hands,
            made_hands_by_street=made_hands_by_street,
            pot_by_street=self.hand_history.get('pot_by_street', {}),
            street_reflections=seed_reflections,
            parent=self
        )
        dialog.setModal(False)
        self._track_hand_dialog(dialog)
        dialog.show()
        # Kick off (or subscribe to) the shared Claude analysis run for
        # this hand. The callback feeds reflections into the dialog
        # live, so the user sees yellow placeholder rows first and
        # then hindsight paragraphs as Claude returns.
        if not seed_reflections:
            self._subscribe_summary_to_reflections(dialog)

    def show_hand_interpretation(self, active_players, winners, hand_results):
        """Generate and display a narrative interpretation of the hand using
        explicit player names (no pronouns) so the same text reads correctly
        on every guest's screen."""
        # Identify every human seat from the host's POV: seat 0 (local hero)
        # plus every network_human_seat. Their per-street equities and
        # per-player win/loss/fold lines are all named explicitly.
        humans = []
        seen = set()
        for seat in [0] + sorted(getattr(self, 'network_human_seats', set()) or []):
            if 0 <= seat < len(self.players) and seat not in seen:
                humans.append(self.players[seat])
                seen.add(seat)

        lines = []
        lines.append(f"Hand #{self.hand_number} Analysis")
        lines.append("-" * 40)

        # Hole cards for everyone (God Mode knowledge — host has full view)
        lines.append("HOLE CARDS:")
        for p in self.players:
            if p.hand:
                hand_str = ' '.join(str(c) for c in p.hand)
                preflop_strength = self.categorize_preflop_hand(p.hand)
                lines.append(f"  {p.name}: {hand_str} ({preflop_strength})")

        lines.append("")
        # Starting hand classification per HUMAN player
        for h in humans:
            if h.hand:
                lines.append(
                    f"{h.name} held: {get_hand_name(h.hand)} "
                    f"({' '.join(str(c) for c in h.hand)})")

        # Per-street boards + per-human equities
        equities = self.hand_history.get('street_equities', {})
        boards = self.hand_history.get('board_by_street', {})

        def _eq_dict(s):
            v = equities.get(s, {})
            # Backward-compat: an older snapshot might still be a single float.
            if isinstance(v, (int, float)):
                return {humans[0].name: float(v)} if humans else {}
            return v or {}

        for street in ['Flop', 'Turn', 'River']:
            if street not in boards:
                continue
            board_cards = boards[street]
            eq_now = _eq_dict(street)

            if street == 'Flop' and len(board_cards) >= 3:
                lines.append(f"\n{street}: {' '.join(board_cards[:3])}")
                for h in humans:
                    if h.name in eq_now:
                        lines.append(f"  {h.name} equity: {eq_now[h.name]:.0%}")
                # Made hands for non-human active players
                human_names = {h.name for h in humans}
                for p in active_players:
                    if p.hand and p.name not in human_names:
                        made_hand = self.describe_made_hand(p.hand, board_cards[:3])
                        lines.append(f"  {p.name}: {made_hand}")

            elif street in ['Turn', 'River']:
                new_card = board_cards[-1]
                prev_street = 'Flop' if street == 'Turn' else 'Turn'
                eq_prev = _eq_dict(prev_street)

                lines.append(f"\n{street}: {new_card}")

                card_impact = self.analyze_card_impact(new_card, board_cards, active_players)
                if card_impact:
                    lines.append(f"  {card_impact}")

                for h in humans:
                    if h.name not in eq_now:
                        continue
                    cur = eq_now[h.name]
                    prev = eq_prev.get(h.name, cur)
                    delta = cur - prev
                    if delta > 0.15:
                        lines.append(
                            f"  {h.name} equity improved: {prev:.0%} → {cur:.0%}")
                    elif delta < -0.15:
                        lines.append(
                            f"  {h.name} equity dropped: {prev:.0%} → {cur:.0%}")
                    else:
                        lines.append(f"  {h.name} equity: {cur:.0%}")

        # Showdown results
        lines.append("")
        lines.append("=" * 30)
        lines.append("SHOWDOWN RESULTS:")

        if hand_results:
            for result in hand_results:
                lines.append(f"  {result}")

            lines.append("")

            # Side-pot breakdown — show every pot, its size, and the
            # claimant. With multiple pots this is the only way the
            # user can see why chips ended up where they did.
            pot_breakdown = getattr(self, 'last_pot_breakdown', None) or []
            if pot_breakdown:
                lines.append("POT BREAKDOWN:")
                for pot in pot_breakdown:
                    tag = " (uncalled)" if pot['uncalled'] else ""
                    lines.append(
                        f"  {pot['label']}: ${pot['amount']} -> "
                        f"{', '.join(pot['winners'])}{tag}"
                    )
                lines.append("")

            if winners:
                # Per-winner net profit comes from the actual chip flow
                # this hand: ending stack minus starting stack. This is
                # correct whether the win came from one pot, a split
                # pot, or multiple side pots.
                starting = getattr(self, 'starting_stacks', {})
                if len(winners) > 1:
                    lines.append(
                        f"SPLIT/MULTI-POT: {len(winners)} winners"
                    )
                    for w in winners:
                        net = w.stack - starting.get(w.name, w.stack)
                        sign = "+" if net >= 0 else "-"
                        lines.append(f"  {w.name}: {sign}${abs(net)}")
                else:
                    w = winners[0]
                    net = w.stack - starting.get(w.name, w.stack)
                    sign = "+" if net >= 0 else "-"
                    lines.append(f"WINNER: {w.name} ({sign}${abs(net)})")

                lines.append("")
                lines.append("Analysis:")

                for w in winners:
                    if w.hand:
                        made_hand = self.describe_made_hand(w.hand, self.board)
                        lines.append(f"  {w.name}: won with {made_hand}")

                for p in active_players:
                    if p not in winners and p.hand:
                        loss_reason = self.explain_loss(p, winners[0], self.board)
                        lines.append(f"  {p.name}: {loss_reason}")

                # Per-human result line, by name (no pronouns)
                for h in humans:
                    h_hand_name = get_hand_name(h.hand) if h.hand else "no hand"
                    if h in winners:
                        lines.append(f"  {h.name} WON with {h_hand_name}!")
                    elif h in active_players:
                        lines.append(f"  {h.name} lost with {h_hand_name}")
                    elif h.hand:
                        lines.append(f"  {h.name} folded {h_hand_name}")
        else:
            winner = winners[0]
            starting = getattr(self, 'starting_stacks', {})
            net_profit = winner.stack - starting.get(winner.name, winner.stack)
            sign = "+" if net_profit >= 0 else "-"
            lines.append(
                f"{winner.name} wins {sign}${abs(net_profit)} uncontested"
            )

        # Write interpretation to log file
        self.write_log("\n" + "=" * 40)
        self.write_log("HAND INTERPRETATION:")
        for line in lines:
            self.write_log(f"  {line}")
        # Also log the assists banner (separate from the interpretation text)
        assists_used = getattr(self, 'hand_assists_used', {})
        if assists_used:
            for player_name, assist_set in sorted(assists_used.items()):
                self.write_log(f"  [{player_name} used while still in hand: "
                               f"{', '.join(sorted(assist_set))}]")
        self.write_log("=" * 40)

        interpretation_text = "\n".join(lines)
        # Serialize assists_used for transport (sets → sorted lists).
        assists_payload = {name: sorted(list(s))
                           for name, s in assists_used.items()}

        # Broadcast to clients before rendering locally.
        if self.network_mode == "host" and self.network_server:
            try:
                self.network_server.broadcast_hand_interpretation(
                    interpretation_text,
                    hand_number=getattr(self, 'hand_number', 0),
                    assists_used=assists_payload,
                )
            except Exception as ex:
                print(f"[host] hand interpretation broadcast failed: {ex}")

        self._show_hand_interpretation_text(
            interpretation_text,
            getattr(self, 'hand_number', 0),
            assists_payload,
        )

    def _track_hand_dialog(self, dialog):
        """Remember an end-of-hand dialog so it can be auto-dismissed when
        the next HAND_START arrives. Self-cleans on dialog destroy."""
        if not hasattr(self, '_open_hand_dialogs'):
            self._open_hand_dialogs = []
        self._open_hand_dialogs.append(dialog)
        dialog.destroyed.connect(
            lambda _=None, d=dialog: self._open_hand_dialogs.remove(d)
            if hasattr(self, '_open_hand_dialogs') and d in self._open_hand_dialogs
            else None
        )

    def _close_open_hand_dialogs(self):
        """Close every tracked end-of-hand dialog (text summary + stats).
        Suppresses the Stats→Hand-Summary restore callback so the user
        lands on the table view, not back on Hand Summary, when a new
        hand starts."""
        self._suppress_parent_restore = True
        try:
            dialogs = list(getattr(self, '_open_hand_dialogs', []) or [])
            for d in dialogs:
                try:
                    d.close()
                except RuntimeError:
                    pass
            self._open_hand_dialogs = []
        finally:
            self._suppress_parent_restore = False

    def _show_hand_interpretation_text(self, interpretation_text: str,
                                        hand_number: int,
                                        assists_used: dict):
        """Build the Hand Summary dialog used by both host and clients.

        Layout: a single QScrollArea wraps the entire content (assists
        banner + interpretation text + Claude analysis blocks) so each
        block expands to its full word-wrapped height — fixing the per-
        block clipping that happened when blocks lived outside the scroll
        area."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Hand Summary")
        dialog.setMinimumSize(600, 500)
        dialog.resize(720, 720)
        dialog.setModal(False)

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(20, 20, 20, 20)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: #2a2a2a; }")

        content = QWidget()
        content.setStyleSheet("background-color: #2a2a2a;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(8)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Bright assists banner — only shown if anyone used God Mode / Tells
        # while still in the hand.  All players see this after the hand.
        if assists_used:
            assists_box = QLabel()
            lines = ["⚠ ASSISTS USED WHILE STILL IN THE HAND ⚠"]
            for name, used in sorted(assists_used.items()):
                used_list = sorted(used) if not isinstance(used, list) else used
                lines.append(f"  {name}: {', '.join(used_list)}")
            assists_box.setText("\n".join(lines))
            assists_box.setFont(QFont('Arial', 14, QFont.Weight.Bold))
            assists_box.setWordWrap(True)
            assists_box.setStyleSheet(
                "color: #ffe066; background-color: #5a1a1a; padding: 12px;"
                " border: 2px solid #ff4444; border-radius: 6px;")
            content_layout.addWidget(assists_box)

        text_label = QLabel(interpretation_text)
        text_label.setFont(QFont('Arial', 18))
        text_label.setWordWrap(True)
        text_label.setStyleSheet(
            "color: white; background-color: #2a2a2a; padding: 4px;")
        text_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.addWidget(text_label)

        # Anchor at the bottom for Claude analysis insertions.
        analysis_anchor = QWidget()
        analysis_anchor.setStyleSheet("background-color: #2a2a2a;")
        analysis_anchor_layout = QVBoxLayout(analysis_anchor)
        analysis_anchor_layout.setContentsMargins(0, 0, 0, 0)
        analysis_anchor_layout.setSpacing(6)
        content_layout.addWidget(analysis_anchor)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        # Stats + Hand Log buttons stay outside the scroll area.
        # NOTE: no "OK" — the summary persists until the next hand starts
        # (handled by _close_open_hand_dialogs in deal_hand).
        stats_btn = QPushButton("Stats")
        stats_btn.setFixedSize(120, 40)
        stats_btn.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        stats_btn.setStyleSheet("QPushButton { background-color: #363; }")
        stats_btn.clicked.connect(lambda: self._show_stats_from_dialog(dialog))

        log_btn = QPushButton("Hand Log")
        log_btn.setFixedSize(140, 40)
        log_btn.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        log_btn.setStyleSheet("QPushButton { background-color: #336; }")
        log_btn.clicked.connect(lambda: self._show_hand_log_dialog(dialog))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(stats_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(log_btn)
        btn_layout.addStretch()
        outer.addLayout(btn_layout)

        # Claude analysis intentionally NOT attached to the Hand Summary
        # any more — the per-POV "Claude — Hero (You):" blocks the
        # auto-critique used to inject here drifted out of sync with
        # the more accurate Hand Log annotations the user reads via the
        # "Hand Log" button just above. The Hand Log path runs Claude
        # against the full BDL/log file once and is the authoritative
        # version, so we route users there instead of duplicating the
        # critique here.
        # (_attach_claude_analysis_to_dialog still exists; if the user
        # ever wants the inline critique back, restore the call below.)
        # self._attach_claude_analysis_to_dialog(dialog, analysis_anchor_layout)

        self._track_hand_dialog(dialog)
        dialog.show()

    def _format_hand_log_compact(self) -> tuple:
        """Build a compact, readable per-action log of the most recent hand.

        Returns (numbered_log_str, raw_lines).  Each numbered line is a
        single action like:
          ` 7. [Flop] Hero  raises to $24    pot=$56`
        Skips chrome lines (CHIP COUNT, TABLE STATS, GAME STATUS, etc.) so
        the Claude annotator only has to reason over real decisions.

        Includes a "Hands" header listing every known hole-card pair —
        Hero's always, plus any villain hands revealed at showdown — so
        the Claude annotator never has to guess whose cards are whose.
        """
        sa = self.hand_history.get('street_actions', {}) or {}
        board_by_street = self.hand_history.get('board_by_street', {}) or {}
        hero_cards = self.hand_history.get('hero_cards', []) or []
        # Build a {name: [card_strs]} map of every player whose hand we
        # know.  Hero's cards always come from hand_history; villain
        # cards come from the live Player objects (host) or the cached
        # hand_summary (client).
        known_hands = {}
        hero_seat = self.my_seat if self.my_seat is not None else 0
        if 0 <= hero_seat < len(self.players):
            hero_name = self.players[hero_seat].name or "Hero"
            if hero_cards:
                known_hands[hero_name] = list(hero_cards)
        # Add other revealed hands when available.
        for p in self.players:
            if p.hand and p.name not in known_hands:
                # On the host, every Player.hand is set.  We only want
                # hands that are revealed (showdown) — assume hands are
                # OK to show by the time the user is reading the log.
                known_hands[p.name] = [str(c) for c in p.hand]
        # Client fallback: pull from cached hand summary if we have it.
        cached = getattr(self, '_cached_hand_summary', None) or {}
        for name, cards in (cached.get('player_hands', {}) or {}).items():
            if name not in known_hands and cards:
                known_hands[name] = list(cards)

        # Pot size after each street (captured in _capture_street_stats).
        pot_by_street = self.hand_history.get('pot_by_street', {}) or {}
        # Equity of each human player at the end of each street, also
        # captured at street boundaries.  Useful for the retrospective.
        street_equities = self.hand_history.get('street_equities', {}) or {}

        # Made-hand for each player at each post-flop street, computed
        # post-mortem (fine to do here — we know everyone's cards).
        made_by_street: dict = {}
        for street in ['Flop', 'Turn', 'River']:
            board_cards = board_by_street.get(street, [])
            if not board_cards:
                continue
            made_by_street[street] = {}
            for name, cards in known_hands.items():
                try:
                    made_by_street[street][name] = self.describe_made_hand(
                        cards, board_cards)
                except Exception:
                    pass

        lines = []
        # Header section: explicit hero identity + every known hand so the
        # annotator can't confuse hero with a villain.
        lines.append(f"Hero is: {hero_name}")
        if known_hands:
            lines.append("Hands (known):")
            for name, cards in known_hands.items():
                tag = "  HERO" if name == hero_name else "      "
                lines.append(f"{tag}  {name}: {' '.join(cards)}")
        for street in ['Preflop', 'Flop', 'Turn', 'River']:
            board = board_by_street.get(street, [])
            actions = sa.get(street, []) or []
            # Previous version dropped any street with no actions — that
            # silently hid the river whenever the hand was decided by an
            # all-in on the turn (river dealt, no betting, straight to
            # showdown). Now we keep any street where the dealer
            # actually put a card on the table OR where someone acted,
            # and annotate the no-betting case so Claude has context.
            if not actions and not board and street != 'Preflop':
                continue
            board_str = (" board=" + ' '.join(board)) if board and street != 'Preflop' else ""
            lines.append(f"--- {street}{board_str} ---")
            if not actions and street != 'Preflop':
                lines.append("  (no betting — all-in earlier or all checked)")
            for act in actions:
                lines.append(f"  {act}")
            # Post-street summary line: pot, made hands, equities.  The
            # action-numbering logic below skips lines that start with
            # the markers we use here ("===") so the per-action numbers
            # stay clean.
            tail = []
            if street in pot_by_street:
                tail.append(f"pot=${int(pot_by_street[street])}")
            mh = made_by_street.get(street, {})
            if mh:
                hand_strs = []
                for name, made in mh.items():
                    if not made:
                        continue
                    tag = "*" if name == hero_name else ""
                    hand_strs.append(f"{name}{tag}={made}")
                if hand_strs:
                    tail.append("hands={" + "; ".join(hand_strs) + "}")
            eq = street_equities.get(street, {}) or {}
            if eq:
                eq_strs = [f"{name}={v:.0%}" for name, v in eq.items()]
                tail.append("equity={" + ", ".join(eq_strs) + "}")
            if tail:
                lines.append("=== end of " + street + ": " + " | ".join(tail))
        numbered = []
        idx = 0
        for line in lines:
            if (line.startswith("---") or line.startswith("Hero is")
                    or line.startswith("Hands") or line.startswith("  HERO")
                    or line.startswith("      ") or line.startswith("===")):
                numbered.append(line)
            else:
                idx += 1
                numbered.append(f"{idx:2d}.{line}")
        return "\n".join(numbered), lines

    def _parse_per_street_retrospective(self, retrospective_text: str) -> dict:
        """Parse the post-RETROSPECTIVE: block into {street: paragraph}.

        Claude is asked (in annotate mode) to emit one paragraph per
        street under literal ``STREET[Preflop]:`` / ``STREET[Flop]:``
        / ``STREET[Turn]:`` / ``STREET[River]:`` markers. Streets the
        hand never reached are omitted by Claude.

        Falls back to ``{}`` if no markers are present (older prompt
        style or model ignored the format) — callers display the raw
        retrospective elsewhere in that case.
        """
        out = {}
        if not retrospective_text:
            return out
        import re
        pat = re.compile(
            r'(?im)^\s*STREET\s*\[\s*(Preflop|Flop|Turn|River)\s*\]\s*:\s*$'
        )
        matches = list(pat.finditer(retrospective_text))
        if not matches:
            return out
        for i, m in enumerate(matches):
            street = m.group(1).capitalize()
            start = m.end()
            end = matches[i + 1].start() if (i + 1) < len(matches) \
                else len(retrospective_text)
            chunk = retrospective_text[start:end].strip()
            if chunk:
                out[street] = chunk
        return out

    def _split_retrospective(self, annotation_text: str) -> tuple:
        """Split Claude's reply into (per-action text, retrospective text).

        The annotator is asked to emit a literal 'RETROSPECTIVE:' marker
        between the two sections.  If the marker isn't present (model
        ignored the instruction), everything is treated as per-action.
        """
        if not annotation_text:
            return "", ""
        import re
        m = re.search(r'(?im)^\s*RETROSPECTIVE\s*:\s*$', annotation_text)
        if not m:
            return annotation_text, ""
        return annotation_text[:m.start()].rstrip(), annotation_text[m.end():].strip()

    def _parse_claude_annotations(self, annotation_text: str) -> dict:
        """Parse Claude's annotation output into {action_index: comment}.

        Claude returns lines like:
            4. Correct laydown — 2c 5h is unplayable trash. !
        We extract the leading integer and the rest of the line as the
        comment. Ignores blank lines and lines without a leading number.
        """
        import re
        out = {}
        if not annotation_text:
            return out
        for raw in annotation_text.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = re.match(r'^\s*(\d+)\s*[.\)]\s*(.+)$', line)
            if not m:
                continue
            try:
                idx = int(m.group(1))
            except ValueError:
                continue
            out[idx] = m.group(2).strip()
        return out

    def _interleave_log_with_annotations(self, annotations: dict,
                                          retrospective: str = "") -> str:
        """Re-render the hand log as HTML with each numbered action
        followed by its Claude annotation (if any) styled in green —
        chess-PGN style.

        The ``retrospective`` parameter is accepted for backward
        compatibility but is intentionally ignored — perfect-hindsight
        commentary now lives in the Hand Summary stats screen
        (interspersed under each street panel), not at the bottom of
        the hand log.

        Each line is its own <div> so long annotations wrap onto the next
        line within the dialog width (no horizontal scroll). Annotation
        lines use a hanging indent so wrapped continuations stay aligned
        under the first character of the comment.
        """
        from html import escape
        sa = self.hand_history.get('street_actions', {}) or {}
        board_by_street = self.hand_history.get('board_by_street', {}) or {}
        hero_cards = self.hand_history.get('hero_cards', []) or []

        log_color = "#dddddd"
        ann_color = "#00d066"  # bright green for annotations
        retro_color = "#ffd966"  # warm yellow for the retrospective
        head_color = "#88ccff"

        # Outer container — monospace font, no left margin, controlled
        # line-height. We avoid <pre> so we can let annotation lines wrap.
        out = [
            '<div style="font-family: \'Courier\', \'Courier New\', monospace; '
            'font-size: 18pt; color: ' + log_color + '; line-height: 1.35;">'
        ]

        def push_action(text):
            # Action lines should NOT wrap — they're short and the leading
            # number / column alignment is more readable as one line.
            esc = escape(text).replace(' ', '&nbsp;')
            out.append(
                f'<div style="white-space: nowrap; color: {log_color};">{esc}</div>'
            )

        def push_header(text):
            esc = escape(text).replace(' ', '&nbsp;')
            out.append(
                f'<div style="white-space: nowrap; color: {head_color}; '
                f'font-weight: bold;">{esc}</div>'
            )

        def push_annotation(text):
            # Annotations wrap. Use a hanging indent (text-indent negative
            # of the padding) so the ↳ marker hangs out of the wrapped
            # block visually.
            esc = escape(text)
            out.append(
                '<div style="color: ' + ann_color + '; font-weight: bold; '
                'padding-left: 56px; text-indent: -28px; '
                'white-space: normal; word-wrap: break-word;">'
                + '↳ ' + esc + '</div>'
            )

        if hero_cards:
            push_header(f"Hero hole cards: {' '.join(hero_cards)}")
        idx = 0
        for street in ['Preflop', 'Flop', 'Turn', 'River']:
            board = board_by_street.get(street, [])
            actions = sa.get(street, []) or []
            # Mirror _format_hand_log_compact: keep the street if a card
            # was dealt OR somebody acted, so all-in-on-the-turn hands
            # don't silently drop the river from the rendered log.
            if not actions and not board and street != 'Preflop':
                continue
            board_str = (" board=" + ' '.join(board)) if board and street != 'Preflop' else ""
            push_header(f"--- {street}{board_str} ---")
            if not actions and street != 'Preflop':
                push_action("  (no betting — all-in earlier or all checked)")
            for act in actions:
                idx += 1
                push_action(f"{idx:2d}. {act}")
                comment = annotations.get(idx)
                if comment:
                    push_annotation(comment)

        # Retrospective intentionally NOT rendered here — see docstring.
        out.append('</div>')
        return "".join(out) if out else "(no actions recorded)"

    def _show_hand_log_dialog(self, parent_dialog):
        """Show the action log interspersed with Claude's chess-style
        annotations (one comment per numbered action). Waits for Claude to
        finish before rendering the merged view, so the user reads a single
        coherent transcript instead of two separate panes.
        """
        try:
            parent_dialog.hide()
        except RuntimeError:
            pass

        log_text, _ = self._format_hand_log_compact()

        dialog = QDialog(self)
        dialog.setWindowTitle("Hand Log")
        dialog.setMinimumSize(820, 760)
        dialog.resize(1100, 1000)
        dialog.setModal(False)
        dialog.setStyleSheet("background-color: #1a1a1a;")

        # Match the hand-summary font size (18pt) consistently.
        SUMMARY_PT = 18

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(10)

        title = QLabel("Hand Log")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        outer.addWidget(title)

        # Single scroll area showing first the progress, then the merged
        # log+annotations once Claude finishes.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: #1a1a1a; }")

        content = QWidget()
        content.setStyleSheet("background-color: #1a1a1a;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # While Claude is running we show progress; the merged view replaces
        # this pane once it's done.
        progress_label = QLabel("Running Claude (Opus 4.7 thinking)…")
        progress_label.setFont(QFont('Arial', SUMMARY_PT))
        progress_label.setStyleSheet("color: #bff;")
        content_layout.addWidget(progress_label)
        bar = QProgressBar()
        bar.setRange(0, 1)
        bar.setValue(0)
        bar.setMinimumHeight(28)
        content_layout.addWidget(bar)

        # The merged log view — populated after Claude returns.  Wraps
        # long annotation lines (no horizontal scroll); the action lines
        # themselves stay nowrap because each <div> sets it locally.
        # We give it stretch=1 (and no terminating addStretch) so it
        # fills the entire scroll area below the progress strip — that
        # eliminates the dead space that used to sit between the bottom
        # of the text and the "Back to Summary" button.
        merged_view = QTextEdit()
        merged_view.setReadOnly(True)
        merged_view.setFont(QFont('Courier', SUMMARY_PT))
        merged_view.setStyleSheet(
            "QTextEdit { background-color: #0e0e0e; color: #ddd;"
            " border: 1px solid #333; padding: 10px; }")
        merged_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        merged_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        merged_view.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        merged_view.setVisible(False)
        content_layout.addWidget(merged_view, stretch=1)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # Bottom: Back button (no OK — the parent summary persists until
        # next hand).
        back_btn = QPushButton("Back to Summary")
        back_btn.setFixedSize(240, 48)
        back_btn.setFont(QFont('Arial', SUMMARY_PT, QFont.Weight.Bold))
        back_btn.setStyleSheet("QPushButton { background-color: #444; color: white; }")

        def _back():
            try:
                dialog.close()
            except RuntimeError:
                pass
            try:
                parent_dialog.show()
                parent_dialog.raise_()
            except RuntimeError:
                pass
        back_btn.clicked.connect(_back)
        bot_row = QHBoxLayout()
        bot_row.addStretch()
        bot_row.addWidget(back_btn)
        bot_row.addStretch()
        outer.addLayout(bot_row)

        # Track this dialog so it auto-dismisses on the next hand.
        self._track_hand_dialog(dialog)

        def _show_merged(annotations: dict, retrospective: str = "",
                         status_text: str = ""):
            """Replace the progress pane with the merged log (HTML-rendered
            so Claude's annotations show in green and the retrospective
            in a yellow post-mortem block at the bottom)."""
            try:
                progress_label.setVisible(False)
                bar.setVisible(False)
                merged_view.setHtml(
                    self._interleave_log_with_annotations(
                        annotations, retrospective))
                merged_view.setVisible(True)
                if status_text:
                    progress_label.setText(status_text)
                    progress_label.setVisible(True)
            except RuntimeError:
                pass

        # If we already have cached annotations for this hand (the user
        # opened the Hand Summary first and the analysis has finished),
        # render immediately and skip the spinner entirely.
        cached = self._get_cached_hand_reflections()
        if cached is not None:
            _show_merged(cached.get('annotations', {}), "",
                         cached.get('status') or '')
            dialog.show()
            return

        # Otherwise subscribe to the shared thread (Hand Summary may
        # have already kicked it off). _ensure_hand_reflections_thread
        # returns None when Claude is unavailable.
        thread = self._ensure_hand_reflections_thread()
        if thread is None:
            _show_merged({}, "",
                         "Claude binary not on PATH — annotations skipped.")
            dialog.show()
            return

        def on_progress(done, total, label):
            try:
                bar.setRange(0, max(1, total))
                bar.setValue(done)
                progress_label.setText(label)
            except RuntimeError:
                pass

        def on_finished(_analyses):
            cached_now = self._get_cached_hand_reflections() or {}
            _show_merged(cached_now.get('annotations', {}), "",
                         cached_now.get('status') or '')

        thread.progress.connect(on_progress)
        thread.finished_analyses.connect(on_finished)

        # Don't cancel the shared thread on dialog close — the Hand
        # Summary may still be subscribed to it. The thread cleans
        # itself up via _ensure_hand_reflections_thread's finalizer.
        dialog.show()

    def _compute_hero_loss_pct(self) -> float:
        """How badly did the hero lose this hand, as a fraction in [0, 1]?

        0 = won or broke even, 1 = busted (lost the entire pre-hand
        stack). Used to scale the Claude retrospective length: a small
        loss / win gets the terse 80-word post-mortem, a catastrophic
        loss gets up to 4× that. The idea is that the more help the
        player needs, the more verbose Claude becomes.

        Falls back to 0 (terse) when we don't have a starting stack
        snapshot — better to under-talk than to spam on hands where the
        delta is unknown.
        """
        try:
            start = getattr(self, '_current_hero_starting_stack', None)
            if start is None or start <= 0:
                return 0.0
            hero_seat = self.my_seat if self.my_seat is not None else 0
            if not (0 <= hero_seat < len(self.players)):
                return 0.0
            current = int(self.players[hero_seat].stack)
            delta = current - int(start)
            if delta >= 0:
                return 0.0           # won or broke even — no loss to atone for
            return min(1.0, -delta / float(start))
        except Exception:
            return 0.0

    def _attach_claude_analysis_to_dialog(self, dialog, layout):
        """Kick off (or wait for) Claude critique(s). `layout` is the inner
        anchor layout inside the dialog's scroll area; analysis widgets are
        appended to it directly (each one expands to its full word-wrapped
        height because the scroll area is widget-resizable)."""
        self._active_summary_dialog = dialog
        self._active_summary_layout = layout
        self._active_summary_placeholder = None

        def _clear_on_close():
            self._active_summary_dialog = None
            self._active_summary_layout = None
            self._active_summary_placeholder = None
        dialog.destroyed.connect(_clear_on_close)

        # If we already have an analysis from the host for THIS hand, render
        # it now — it's the host's POV and may have richer god-mode context.
        # We then ALSO run claude locally below so a guest still gets their
        # own analysis even when the host has no claude binary.
        if self.network_mode == "client":
            cached = getattr(self, '_latest_hand_analyses', None)
            cached_hand = getattr(self, '_latest_hand_analyses_hand', None)
            current_hand = int(getattr(self, 'hand_number', 0) or 0)
            if cached and cached_hand == current_hand:
                self._on_hand_analysis_received(cached, cached_hand)
                self._latest_hand_analyses = None
                self._latest_hand_analyses_hand = None

        def _post_diag(msg, color="#fc6"):
            """Add a small visible reason in the dialog so the user knows
            why no Claude annotation appeared. Uses the same font size as
            the surrounding hand summary text so it reads consistently."""
            try:
                lbl = QLabel(msg)
                lbl.setFont(QFont('Arial', 18))
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color: {color}; background: #1a1a1a; padding: 8px;"
                    " border-radius: 5px;")
                layout.addWidget(lbl)
            except RuntimeError:
                pass

        import shutil
        if not shutil.which('claude'):
            _post_diag(
                "Claude analysis skipped: 'claude' binary not on PATH. "
                "Install Claude Code (or add it to PATH for this shell) "
                "to enable per-hand critique.")
            return

        hand_log = self._get_current_hand_log()
        if not hand_log:
            _post_diag(
                "Claude analysis skipped: couldn't extract this hand's log "
                f"from {self.log_filename}. The HAND # block may not have "
                "been written yet.")
            return

        povs = self._claude_povs_for_this_hand()
        if not povs:
            _post_diag(
                "Claude analysis skipped: no human players (POVs) to "
                "analyze for this hand.")
            return

        progress_box = QGroupBox("Claude analysis")
        progress_box.setStyleSheet(
            "QGroupBox { color: #bff; font-size: 13px; padding: 10px; }"
        )
        pbox_layout = QVBoxLayout(progress_box)
        status_label = QLabel("Starting Claude…")
        status_label.setFont(QFont('Arial', 12))
        status_label.setStyleSheet("color: #bff;")
        pbox_layout.addWidget(status_label)
        bar = QProgressBar()
        bar.setRange(0, max(1, len(povs)))
        bar.setValue(0)
        bar.setFormat("%v / %m")
        pbox_layout.addWidget(bar)
        layout.addWidget(progress_box)

        analysis_container = QWidget()
        analysis_container.setStyleSheet("background-color: #2a2a2a;")
        analysis_layout = QVBoxLayout(analysis_container)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(6)
        layout.addWidget(analysis_container)

        thread = ClaudeAnalysisThread(hand_log, povs)

        def on_progress(done, total, label):
            try:
                bar.setValue(done)
                status_label.setText(label)
            except RuntimeError:
                pass  # dialog was closed

        def on_finished(analyses):
            # Remove progress display
            try:
                progress_box.deleteLater()
            except RuntimeError:
                pass
            if not analyses:
                _post_diag(
                    "Claude returned no analyses (the analysis thread "
                    "produced an empty list — claude may have exited "
                    "early or been cancelled).",
                    color="#fc6")
            # Show each analysis as its own labeled block. Empty-text
            # entries (claude failed for that POV) get a visible yellow
            # diagnostic block so the user knows why nothing rendered.
            for a in analyses:
                name = a.get('player', '?')
                text = a.get('text', '').strip()
                model = (a.get('model') or '').strip() or 'Claude'
                if not text:
                    fail_block = QLabel(
                        f"{model} — {name}: (no analysis returned — "
                        "claude may have failed, timed out, or hit a "
                        "rate limit; check the terminal for stderr)")
                    # Match the surrounding interpretation text size
                    # (18pt) so the analysis block reads at the same
                    # weight as the rest of the hand summary.
                    fail_block.setFont(QFont('Arial', 18))
                    fail_block.setWordWrap(True)
                    fail_block.setStyleSheet(
                        "color: #fc6; background-color: #2a1a1a; padding: 10px;"
                        " border-radius: 5px; margin: 4px 0;"
                    )
                    analysis_layout.addWidget(fail_block)
                    continue
                block = QLabel(f"{model} — {name}:\n{text}")
                block.setFont(QFont('Arial', 18))
                block.setWordWrap(True)
                block.setStyleSheet(
                    "color: #8f8; background-color: #1a2a1a; padding: 10px;"
                    " border-radius: 5px; margin: 4px 0;"
                )
                analysis_layout.addWidget(block)

            # If hosting, broadcast so every client sees the same bundle.
            if (self.network_mode == "host" and self.network_server
                    and analyses):
                try:
                    self.network_server.broadcast_hand_analysis(
                        analyses, hand_number=getattr(self, 'hand_number', 0))
                except Exception as ex:
                    print(f"[Claude] broadcast failed: {ex}")

            thread.deleteLater()

        thread.progress.connect(on_progress)
        thread.finished_analyses.connect(on_finished)

        # Cancel analysis if the dialog closes first.
        def on_dialog_destroyed():
            try:
                thread.cancel()
            except Exception:
                pass
        dialog.destroyed.connect(on_dialog_destroyed)

        # Keep a strong ref so the thread isn't GC'd mid-run.
        if not hasattr(self, '_claude_threads'):
            self._claude_threads = []
        self._claude_threads.append(thread)
        thread.start()

    def _claude_povs_for_this_hand(self) -> list:
        """Return the list of POVs to analyze.

        Single-player (or client-side): just Hero.
        Host in multiplayer: Hero (host) + every seated human client.
        """
        povs = []
        # Always include the local hero's perspective first.
        hero_seat = self.my_seat if self.my_seat is not None else 0
        if hero_seat < len(self.players):
            povs.append({
                'name': self.players[hero_seat].name or 'Hero',
                'seat': hero_seat,
            })

        # If hosting, add one POV per seated client.
        if self.network_mode == "host" and self.network_server:
            try:
                seats = self.network_server.get_seats()
                host_seat = self.network_server.host_seat
                for seat_index, player_name in seats.items():
                    if not player_name or seat_index == host_seat:
                        continue
                    # Avoid duplicating the host's own POV
                    if seat_index == hero_seat:
                        continue
                    povs.append({
                        'name': player_name,
                        'seat': seat_index,
                    })
            except Exception as ex:
                print(f"[Claude] could not enumerate clients for POVs: {ex}")
        return povs

    def _show_stats_from_dialog(self, parent_dialog):
        """Open the graphical Stats dialog from the text Hand Summary.

        Hide (not close) the parent so dismissing Stats brings the Hand
        Summary back to the front. Clients use the cached HAND_END payload
        (the host's data); host / single-player builds it locally from
        `hand_history`.
        """
        try:
            parent_dialog.hide()
        except RuntimeError:
            parent_dialog = None  # already destroyed
        if self.network_mode == "client":
            self._show_cached_graphical_summary(parent_to_restore=parent_dialog)
        else:
            self._show_local_graphical_summary(parent_to_restore=parent_dialog)

    def _restore_parent_dialog(self, parent_dialog):
        """Re-show + raise the Hand Summary text dialog after the Stats
        dialog was dismissed — unless we're closing everything for a new
        hand, in which case the user wants the table view, not Hand
        Summary again."""
        if parent_dialog is None:
            return
        if getattr(self, '_suppress_parent_restore', False):
            return
        try:
            parent_dialog.show()
            parent_dialog.raise_()
            parent_dialog.activateWindow()
        except RuntimeError:
            pass  # parent was destroyed (e.g. new hand started)

    def _show_cached_graphical_summary(self, parent_to_restore=None):
        """Open the graphical HandSummaryDialog using the cached HAND_END
        payload (client-side path)."""
        cached = getattr(self, '_cached_hand_summary', None)
        if not cached or not cached.get('street_stats'):
            self._restore_parent_dialog(parent_to_restore)
            return
        try:
            seed = (self._get_cached_hand_reflections() or {})
            dialog = HandSummaryDialog(
                street_stats=cached['street_stats'],
                street_actions=cached['street_actions'],
                board_by_street=cached['board_by_street'],
                player_results=cached['player_results'],
                player_hands=cached['player_hands'],
                made_hands_by_street=cached['made_hands_by_street'],
                pot_by_street=cached.get('pot_by_street', {}),
                street_reflections=seed.get('street_reflections', {}),
                parent=self,
            )
            dialog.setModal(False)
            self._track_hand_dialog(dialog)
            if not seed.get('street_reflections'):
                self._subscribe_summary_to_reflections(dialog)
            if parent_to_restore is not None:
                # `finished` fires on every dismiss path; `destroyed` only
                # fires on object delete, which most close paths skip.
                dialog.finished.connect(
                    lambda _=0, p=parent_to_restore:
                        self._restore_parent_dialog(p))
            dialog.show()
        except Exception as ex:
            print(f"[client] graphical hand summary failed: {ex}")
            self._restore_parent_dialog(parent_to_restore)

    def show_help(self):
        """Show help dialog with game instructions."""
        help_text = """
<h2>PokerIQ - Help</h2>

<h3>🎮 Game Modes</h3>
<p><b>God Mode:</b> See all players' hole cards. Useful for understanding opponents' decisions.</p>
<p><b>Show Tells:</b> Imagine you can read body language! This shows what players THINK their
hand strength is. In real poker, skilled players pick up "tells" - physical cues revealing
hand strength. This mode simulates that ability:
   <br>- <b>Real:</b> Actual equity (God Mode shows true cards)
   <br>- <b>Thinking:</b> What each player believes their equity to be
   <br>- <b>Pot Odds:</b> The mathematical odds offered by the pot</p>
<p><b>Theory of Mind:</b> Advanced analysis mode for serious study. Shows opponent ranges
on PokerStove grids with strategy advice.</p>

<h3>🎯 Theory of Mind View</h3>
<p><b>Range Estimation Modes:</b></p>
<ul>
<li><b>Loose:</b> Assume opponents are weaker (wider ranges) - use when you want to call more</li>
<li><b>Neutral:</b> Standard estimation based on player style</li>
<li><b>Tight:</b> Assume opponents are stronger (narrower ranges) - use when facing aggression</li>
</ul>
<p><b>The 2D PokerStove Grid:</b></p>
<ul>
<li>Rows/columns = card ranks (A through 2)</li>
<li>Upper right triangle: Suited hands (AKs)</li>
<li>Diagonal: Pocket pairs (AA, KK)</li>
<li>Lower left triangle: Offsuit hands (AKo)</li>
<li>Brighter = more likely in opponent's range</li>
</ul>
<p><b>Pot Odds vs Implied Odds:</b></p>
<ul>
<li><b>Pot Odds:</b> Call amount / (pot + call) - immediate math</li>
<li><b>Implied Odds:</b> Includes future bets you might win - crucial for drawing hands</li>
<li>Green equity = +EV (profitable), Red = -EV (unprofitable)</li>
</ul>
<p><b>Board Texture:</b> WET boards (flush/straight draws) require bigger bets for protection.
DRY boards (disconnected, rainbow) allow more bluffing and thin value.</p>

<h3>📈 Key Concepts</h3>
<ul>
<li><b>Rule of 4 and 2:</b> Outs × 4 on flop, Outs × 2 on turn = equity %</li>
<li><b>Position is Power:</b> Button is most profitable seat - act last with information</li>
<li><b>Aggression Wins:</b> Betting has two ways to win (fold equity + showdown)</li>
<li><b>Big Hand = Big Pot:</b> With nuts, build the pot. With marginal hands, control it.</li>
<li><b>vs Tight:</b> Steal their blinds, believe their bets</li>
<li><b>vs Loose:</b> Value bet relentlessly, don't bluff</li>
<li><b>vs Aggro:</b> Trap with strong hands, let them bluff</li>
</ul>

<h3>🤖 Fluid Fiona - Adaptive Opponent</h3>
<p>Fiona learns from the game! She tracks your play style and adjusts her strategy.
Her range estimates update based on observed aggression. The log tracks whether
predicted ranges matched actual holdings - use this to improve your reads!</p>

<h3>💰 Betting</h3>
<p><b>Raise Dialog:</b> BB multipliers (2x-10x) or pot fractions (1/2, 2/3, pot)</p>
<p><b>Blinds:</b> Tournament structure - increase every 10 hands</p>

<h3>🃏 Hand Categories</h3>
<ul>
<li><b>Tier 1:</b> AA, KK, QQ, JJ, AK - Raise/re-raise from any position</li>
<li><b>Tier 2:</b> TT-99, AQ, AJs, KQs - Raise, call 3-bets cautiously</li>
<li><b>Tier 3:</b> 88-66, ATs-A2s, KJs, QJs, suited connectors - Position dependent</li>
<li><b>Tier 4:</b> Small pairs, weak suited - Set mine only with odds</li>
<li><b>Fold:</b> Unsuited junk - patience is profitable!</li>
</ul>
"""

        dialog = QDialog(self)
        dialog.setWindowTitle("Help - PokerIQ")
        dialog.setMinimumSize(700, 600)
        dialog.setModal(False)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)

        # Use QTextEdit for scrollable HTML content
        from PyQt6.QtWidgets import QTextEdit
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setHtml(help_text)
        text_widget.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ddd;
                font-size: 24px;
                border: none;
                padding: 15px;
            }
        """)
        layout.addWidget(text_widget)

        ok_btn = QPushButton("Close")
        ok_btn.setFixedSize(100, 35)
        ok_btn.clicked.connect(dialog.close)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        dialog.show()

    def show_about(self):
        """Show about dialog with version information."""
        about_text = """
<div style="text-align: center;">
<h1>PokerIQ</h1>
<h3>Poker Training with Theory of Mind</h3>
<br>
<p><b>Version:</b> 0.3</p>
<p><b>Release Date:</b> January 19, 2026</p>
<br>
<p>A comprehensive poker training application featuring:</p>
<ul style="text-align: left;">
<li>Theory of Mind opponent modeling</li>
<li>PokerStove-style hand range visualization</li>
<li>Strategy advice</li>
<li>Real-time equity calculations</li>
<li>God Mode for learning</li>
</ul>
<br>
<p style="color: #888;">Built with PyQt6 and eval7</p>
</div>
"""
        dialog = QDialog(self)
        dialog.setWindowTitle("About PokerIQ")
        dialog.setFixedSize(450, 400)
        dialog.setModal(False)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)

        from PyQt6.QtWidgets import QTextEdit
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setHtml(about_text)
        text_widget.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ddd;
                font-size: 18px;
                border: none;
            }
        """)
        layout.addWidget(text_widget)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(80, 35)
        ok_btn.clicked.connect(dialog.close)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        dialog.show()

    def show_preferences(self):
        """Show preferences dialog with tabbed interface."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        dialog.setFixedSize(600, 550)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("PokerIQ Preferences")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0af;")
        layout.addWidget(title)

        # Create tabbed interface
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #333;
                color: #aaa;
                padding: 8px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #444;
                color: #fff;
            }
        """)

        # --- Equity Tab ---
        equity_tab = QWidget()
        equity_tab_layout = QVBoxLayout(equity_tab)
        equity_tab_layout.setContentsMargins(15, 15, 15, 15)

        # Checkbox for visible cards only
        self.visible_cards_cb = QCheckBox("Use only publicly revealed cards for Hero's equity")
        self.visible_cards_cb.setStyleSheet("font-size: 14px; color: #ddd;")
        self.visible_cards_cb.setChecked(self.use_visible_cards_only)
        self.visible_cards_cb.setToolTip(
            "When checked, Hero's equity calculations only consider information\n"
            "that would be publicly available (board cards, shown hands).\n"
            "When unchecked, uses all known hole cards (God Mode style)."
        )
        equity_tab_layout.addWidget(self.visible_cards_cb)

        # Description
        desc = QLabel(
            "When enabled, Theory of Mind equity calculations for Hero\n"
            "only use publicly revealed information (more realistic).\n"
            "When disabled, calculations use all hole card information\n"
            "available in the game (useful for learning)."
        )
        desc.setStyleSheet("font-size: 12px; color: #888; margin-left: 20px;")
        equity_tab_layout.addWidget(desc)
        equity_tab_layout.addStretch()

        tabs.addTab(equity_tab, "Equity")

        # --- Display Tab ---
        display_tab = QWidget()
        display_tab_layout = QVBoxLayout(display_tab)
        display_tab_layout.setContentsMargins(15, 15, 15, 15)

        # Checkbox for legacy colors
        self.legacy_colors_cb = QCheckBox("Legacy colors (red diamonds, black clubs)")
        self.legacy_colors_cb.setStyleSheet("font-size: 14px; color: #ddd;")
        self.legacy_colors_cb.setChecked(self.legacy_colors)
        self.legacy_colors_cb.setToolTip(
            "When checked, uses traditional card colors:\n"
            "  - Hearts and Diamonds: Red\n"
            "  - Clubs and Spades: Black\n\n"
            "When unchecked, uses modern 4-color deck:\n"
            "  - Hearts: Red\n"
            "  - Diamonds: Blue\n"
            "  - Clubs: Green\n"
            "  - Spades: Black"
        )
        display_tab_layout.addWidget(self.legacy_colors_cb)

        # Description
        display_desc = QLabel(
            "Modern 4-color deck makes suits easier to distinguish.\n"
            "Enable legacy colors for traditional red/black appearance."
        )
        display_desc.setStyleSheet("font-size: 12px; color: #888; margin-left: 20px;")
        display_tab_layout.addWidget(display_desc)
        display_tab_layout.addStretch()

        tabs.addTab(display_tab, "Display")

        # --- AI Opponents Tab ---
        ai_tab = QWidget()
        ai_tab_layout = QVBoxLayout(ai_tab)
        ai_tab_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        ai_header = QLabel("Select AI bot type for each opponent seat:")
        ai_header.setStyleSheet("font-size: 14px; color: #ddd; margin-bottom: 10px;")
        ai_tab_layout.addWidget(ai_header)

        # Create combo boxes for each non-human seat
        self.bot_combos = {}  # seat -> QComboBox
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        for seat, player in enumerate(self.players):
            if player.style == 'human':
                continue  # Skip human player

            combo = QComboBox()
            combo.setFixedWidth(250)
            combo.setStyleSheet("""
                QComboBox {
                    background-color: #333;
                    color: #ddd;
                    padding: 5px;
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #333;
                    color: #ddd;
                    selection-background-color: #555;
                }
            """)

            # Add bot options
            current_pref = self.bot_preferences.get(seat, "default")
            selected_index = 0

            for i, (display_name, type_id, is_piq) in enumerate(BOT_TYPE_OPTIONS):
                # Add availability indicator for poker_iq bots
                if is_piq and not POKER_IQ_AVAILABLE:
                    combo.addItem(f"{display_name} (unavailable)", type_id)
                    # Disable this item
                    combo.model().item(i).setEnabled(False)
                else:
                    combo.addItem(display_name, type_id)

                if type_id == current_pref:
                    selected_index = i

            combo.setCurrentIndex(selected_index)
            self.bot_combos[seat] = combo

            # Create label with player name
            label = QLabel(f"{player.name}:")
            label.setStyleSheet("font-size: 13px; color: #bbb;")
            form_layout.addRow(label, combo)

        ai_tab_layout.addLayout(form_layout)

        # Add note about poker_iq availability
        if POKER_IQ_AVAILABLE:
            note = QLabel("✓ poker_iq bots are available")
            note.setStyleSheet("font-size: 12px; color: #6a6; margin-top: 15px;")
        else:
            note = QLabel("⚠ poker_iq module not found. Advanced bots unavailable.\n"
                         "   Default bots will be used.")
            note.setStyleSheet("font-size: 12px; color: #a66; margin-top: 15px;")
        ai_tab_layout.addWidget(note)

        # Randomize bots toggle — only meaningful once the hero has won.
        self.randomize_bots_cb = QCheckBox(
            "Randomize bots from combined pool after winning a game")
        self.randomize_bots_cb.setStyleSheet("font-size: 13px; color: #ddd; margin-top: 12px;")
        self.randomize_bots_cb.setChecked(self.randomize_bots_enabled)
        self.randomize_bots_cb.setToolTip(
            "Once you have won at least one game against the default bots,"
            "\nfuture games will randomly seat opponents from the full pool"
            "\n(default styles + advanced poker_iq bots)."
            "\nApplies only to seats whose preference is 'Default'."
        )
        ai_tab_layout.addWidget(self.randomize_bots_cb)

        unlocked_text = (
            "✓ You have beaten the default bots — random pool unlocked."
            if self.beat_defaults_unlocked
            else "Beat the default bots once to unlock the advanced random pool."
        )
        unlocked_label = QLabel(unlocked_text)
        unlocked_label.setStyleSheet(
            "font-size: 11px; color: " +
            ("#6a6;" if self.beat_defaults_unlocked else "#a86;") +
            " margin-left: 22px;"
        )
        ai_tab_layout.addWidget(unlocked_label)

        ai_tab_layout.addStretch()
        tabs.addTab(ai_tab, "AI Opponents")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 35)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(80, 35)
        save_btn.setStyleSheet("QPushButton { background-color: #363; }")
        save_btn.clicked.connect(lambda: self.save_preferences(dialog))
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def save_preferences(self, dialog):
        """Save preferences from dialog."""
        # Save equity preferences
        self.use_visible_cards_only = self.visible_cards_cb.isChecked()
        self.settings.setValue("use_visible_cards_only", self.use_visible_cards_only)

        # Update ToM panel if visible
        if hasattr(self, 'tom_panel'):
            self.tom_panel.use_visible_cards_only = self.use_visible_cards_only
            self.update_theory_of_mind()

        # Save display preferences
        self.legacy_colors = self.legacy_colors_cb.isChecked()
        self.settings.setValue("legacy_colors", self.legacy_colors)
        self._apply_color_preference()

        # Save bot preferences
        for seat, combo in self.bot_combos.items():
            bot_type_id = combo.currentData()
            self.bot_preferences[seat] = bot_type_id

        # Save randomize-bots toggle
        if hasattr(self, 'randomize_bots_cb'):
            self.randomize_bots_enabled = self.randomize_bots_cb.isChecked()
            self.settings.setValue(
                "randomize_bots_enabled", self.randomize_bots_enabled)

        self._save_bot_preferences()
        self._apply_bot_preferences()

        # Refresh the display to show updated player names
        self.update_all_panels()

        dialog.accept()

    # --- Menubar ------------------------------------------------------------

    def _build_menubar(self):
        """Build the top menubar with a Network menu.

        Selecting nothing leaves the game in its default single-player mode;
        the Network menu is the only way to enter host or client mode.
        """
        menubar = self.menuBar()

        # File menu — Save Game / Load Game / Exit, leftmost following
        # the standard desktop convention.
        file_menu = menubar.addMenu("&File")

        act_save = QAction("&Save Game…", self)
        act_save.setShortcut("Ctrl+S")
        act_save.setStatusTip(
            "Save the full game state (stacks, hands, board, blinds, "
            "history) to a JSON file you can load later")
        act_save.triggered.connect(self._menu_save_game)
        file_menu.addAction(act_save)

        act_load = QAction("&Load Game…", self)
        act_load.setShortcut("Ctrl+O")
        act_load.setStatusTip(
            "Load a previously-saved game and resume from where it "
            "was saved")
        act_load.triggered.connect(self._menu_load_game)
        file_menu.addAction(act_load)

        file_menu.addSeparator()

        act_buyin = QAction("&Buy More Chips…", self)
        act_buyin.setStatusTip(
            "Top up your stack between hands (single-player only)")
        act_buyin.triggered.connect(self._menu_buy_more_chips)
        file_menu.addAction(act_buyin)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.setStatusTip("Quit PokerIQ")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        net_menu = menubar.addMenu("&Network")

        self.act_host = QAction("Host Game...", self)
        self.act_host.setStatusTip("Start a local server for other players to join")
        self.act_host.triggered.connect(self._menu_host)
        net_menu.addAction(self.act_host)

        self.act_join = QAction("Join Game...", self)
        self.act_join.setStatusTip("Connect to a poker server on your network")
        self.act_join.triggered.connect(self._menu_join)
        net_menu.addAction(self.act_join)

        net_menu.addSeparator()

        self.act_status = QAction("Network Status...", self)
        self.act_status.setEnabled(False)
        self.act_status.triggered.connect(self._menu_status)
        net_menu.addAction(self.act_status)

        self.act_disconnect = QAction("Disconnect", self)
        self.act_disconnect.setEnabled(False)
        self.act_disconnect.triggered.connect(self._menu_disconnect)
        net_menu.addAction(self.act_disconnect)

        if not NETWORK_AVAILABLE:
            self.act_host.setEnabled(False)
            self.act_join.setEnabled(False)
            net_menu.setToolTip("Network module not available")

        # Bots menu — currently just the "reset to default lineup"
        # action. Each line in DEFAULT_BOT_LINEUP is a genuinely
        # different approach so this is the one-click way to
        # un-stick a session where saved per-seat preferences left
        # multiple seats playing the same style.
        bots_menu = menubar.addMenu("&Bots")
        act_reset_bots = QAction("Reset Bots to Default Lineup", self)
        act_reset_bots.setStatusTip(
            "Restore the canonical 5-bot lineup: Optimal Olivia, "
            "Sharkey Steve, Loose Bruce, Exploit Eli, Fluid Fiona — "
            "each playing a different approach.")
        act_reset_bots.triggered.connect(self.reset_bots_to_default_lineup)
        bots_menu.addAction(act_reset_bots)

        help_menu = menubar.addMenu("&Help")
        act_help = QAction("Help...", self)
        act_help.triggered.connect(self.show_help)
        help_menu.addAction(act_help)
        act_about = QAction("About", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

    # ---- Save / Load ----------------------------------------------------

    SAVE_VERSION = 1

    def _serialize_player(self, p):
        """Convert a Player object to a JSON-friendly dict.

        Cards are stored as their string form (e.g. 'Ks'); load-time
        recreates eval7.Card objects.
        """
        return {
            'name': p.name,
            'style': p.style,
            'stack': int(p.stack),
            'hand': [str(c) for c in (p.hand or [])],
            'active': bool(p.active),
            'bet_in_round': int(getattr(p, 'bet_in_round', 0)),
            'actions_this_round': int(getattr(p, 'actions_this_round', 0)),
            'total_invested': int(getattr(p, 'total_invested', 0)),
        }

    def _build_save_state(self) -> dict:
        """Snapshot every attribute the table needs to resume play."""
        return {
            'pokerIQ_save_version': self.SAVE_VERSION,
            'saved_at': datetime.now().isoformat(timespec='seconds'),
            'players': [self._serialize_player(p) for p in self.players],
            'board': [str(c) for c in (self.board or [])],
            'pot': int(self.pot),
            'dealer_idx': int(self.dealer_idx),
            'current_bet': int(self.current_bet),
            'street_idx': int(self.street_idx),
            'current_player_idx': int(self.current_player_idx),
            'last_raiser': int(getattr(self, 'last_raiser', -1)),
            'last_raise_size': int(getattr(self, 'last_raise_size', 0)),
            'raises_this_round': int(getattr(self, 'raises_this_round', 0)),
            'hand_number': int(self.hand_number),
            'blind_level': int(self.blind_level),
            'at_showdown': bool(self.at_showdown),
            'action_log': list(self.action_log),
            'action_history': list(self.action_history),
            'starting_stacks': dict(getattr(self, 'starting_stacks', {})),
            'hand_history': self._jsonify_hand_history(self.hand_history),
        }

    def _jsonify_hand_history(self, h):
        """hand_history may contain eval7.Card / int / nested dicts —
        coerce values into JSON-safe primitives. Anything we can't
        encode is dropped from the snapshot rather than failing the
        whole save."""
        import json as _json
        out = {}
        for k, v in (h or {}).items():
            try:
                _json.dumps(v)
                out[k] = v
            except (TypeError, ValueError):
                # Card lists / dicts of cards.
                if isinstance(v, list):
                    out[k] = [str(x) for x in v]
                elif isinstance(v, dict):
                    out[k] = {sk: ([str(x) for x in sv]
                                   if isinstance(sv, list) else str(sv))
                              for sk, sv in v.items()}
                else:
                    out[k] = str(v)
        return out

    def _menu_buy_more_chips(self):
        """File → Buy More Chips. Top up the human player's stack with
        an arbitrary amount, between hands only (mid-hand top-ups
        would corrupt the pot / side-pot bookkeeping).

        Available to ANY human player (host, guest, or single-player
        local) so a busted human can rebuy and keep playing. In
        client mode the request is forwarded to the host via a
        BUY_IN action — the host applies it to the canonical stack
        and broadcasts the update so every screen agrees.
        """
        if getattr(self, '_hand_in_progress', False):
            QMessageBox.information(
                self, "Buy More Chips",
                "Wait until the current hand ends — adding chips "
                "mid-hand would mess up the pot / side-pot math.")
            return
        hero_seat = (self.my_seat
                     if self.network_mode == "client"
                     else (self.my_seat
                           if self.network_mode == "host"
                              and self.my_seat is not None
                           else 0))
        if not (0 <= hero_seat < len(self.players)):
            return
        hero = self.players[hero_seat]
        # Default to enough to bring the seat back up to a 100-BB
        # buy-in so a busted hero gets a typical reload click.
        _, bb_amount = BLIND_LEVELS[self.blind_level]
        target = max(int(STARTING_STACK), 100 * int(bb_amount))
        suggested = max(int(bb_amount), target - int(hero.stack))
        from PyQt6.QtWidgets import QInputDialog
        amount, ok = QInputDialog.getInt(
            self, "Buy More Chips",
            f"Current stack: ${int(hero.stack)}\n"
            f"Big blind: ${int(bb_amount)}\n\n"
            "Add how many chips?",
            value=suggested, min=1, max=1_000_000, step=int(bb_amount),
        )
        if not ok or amount <= 0:
            return
        hero.stack = int(hero.stack) + int(amount)
        # starting_stacks records the seat's pre-hand snapshot used by
        # the per-hand summary dialog. Bump it too so the next hand's
        # delta doesn't pretend the buy-in was a profit.
        try:
            if hasattr(self, 'starting_stacks'):
                self.starting_stacks[hero.name] = int(hero.stack)
        except Exception:
            pass
        try:
            self.update_all_panels()
        except Exception:
            pass
        try:
            if self.network_mode == "host" and self.network_server:
                # Push the new stack out to guests so their UI reflects
                # the host's new chip count. broadcast_stack_update
                # takes a {seat: stack} dict.
                if hasattr(self.network_server, 'broadcast_stack_update'):
                    self.network_server.broadcast_stack_update(
                        {hero_seat: int(hero.stack)})
            elif self.network_mode == "client" and self.network_client:
                # No server-side buy-in protocol exists yet, so a
                # client-initiated buy-in is local only — the host's
                # next stack broadcast will overwrite it. Surface a
                # chat note so the host can mirror the change on
                # their side.
                try:
                    self.network_client.send_chat(
                        f"[buy-in] {hero.name} bought $"
                        f"{int(amount)} more — please mirror on "
                        "the host side."
                    )
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.write_log(
                f"  [BUY-IN] {hero.name} added ${int(amount)} "
                f"→ stack ${int(hero.stack)}")
        except Exception:
            pass
        QMessageBox.information(
            self, "Buy More Chips",
            f"Added ${int(amount)} to {hero.name}.\n"
            f"New stack: ${int(hero.stack)}")

    def _menu_save_game(self):
        """File → Save Game. Refuses to save while a network session
        is active (the relevant state isn't authoritative on guests)."""
        if self.network_mode:
            QMessageBox.information(
                self, "Save Game",
                "Save / Load isn't supported during a network session. "
                "Disconnect first if you want to snapshot a hand.")
            return
        default_name = (
            f"pokerIQ_hand{self.hand_number}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Game", default_name,
            "PokerIQ saves (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            import json as _json
            payload = self._build_save_state()
            with open(path, 'w') as f:
                _json.dump(payload, f, indent=2)
        except Exception as ex:
            QMessageBox.warning(
                self, "Save Game",
                f"Couldn't write the save file:\n{ex}")
            return
        QMessageBox.information(
            self, "Save Game",
            f"Game state saved to:\n{path}")

    def _menu_load_game(self):
        """File → Load Game. Replaces in-memory state with the saved
        snapshot, then refreshes every panel and the table view."""
        if self.network_mode:
            QMessageBox.information(
                self, "Load Game",
                "Save / Load isn't supported during a network session. "
                "Disconnect first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Game", "",
            "PokerIQ saves (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            import json as _json
            with open(path, 'r') as f:
                payload = _json.load(f)
        except Exception as ex:
            QMessageBox.warning(
                self, "Load Game",
                f"Couldn't read the save file:\n{ex}")
            return
        try:
            self._apply_save_state(payload)
        except Exception as ex:
            QMessageBox.warning(
                self, "Load Game",
                f"Save file looks corrupted ({ex}). The game state "
                "may be partially loaded — start a new hand to "
                "recover.")
            return
        QMessageBox.information(
            self, "Load Game",
            f"Loaded game from:\n{path}\n\n"
            "Click 'New Hand' to start the next hand from this state.")

    def _apply_save_state(self, payload: dict):
        """Restore every attribute set by _build_save_state."""
        ver = int(payload.get('pokerIQ_save_version') or 0)
        if ver < 1:
            raise ValueError("missing or unrecognised save version")

        # Rebuild players.
        saved_players = payload.get('players') or []
        new_players = []
        for sp in saved_players:
            p = Player(sp.get('name', '?'), sp.get('style', 'tight'))
            p.stack = int(sp.get('stack', 0) or 0)
            try:
                p.hand = [eval7.Card(c) for c in sp.get('hand', []) or []]
            except Exception:
                p.hand = []
            p.active = bool(sp.get('active', True))
            p.bet_in_round = int(sp.get('bet_in_round', 0) or 0)
            p.actions_this_round = int(sp.get('actions_this_round', 0) or 0)
            p.total_invested = int(sp.get('total_invested', 0) or 0)
            new_players.append(p)
        if not new_players:
            raise ValueError("save has no players")
        self.players = new_players

        # Re-apply current bot preferences so saved seats stay in sync
        # with the user's stored per-seat overrides.
        try:
            self._apply_bot_preferences()
        except Exception:
            pass

        # Board cards.
        try:
            self.board = [eval7.Card(c)
                          for c in payload.get('board') or []]
        except Exception:
            self.board = []

        # Scalar state.
        self.pot = int(payload.get('pot', 0) or 0)
        self.dealer_idx = int(payload.get('dealer_idx', 0) or 0)
        self.current_bet = int(payload.get('current_bet', 0) or 0)
        self.street_idx = int(payload.get('street_idx', 0) or 0)
        self.current_player_idx = int(
            payload.get('current_player_idx', 0) or 0)
        self.last_raiser = int(payload.get('last_raiser', -1))
        self.last_raise_size = int(payload.get('last_raise_size', 0) or 0)
        self.raises_this_round = int(
            payload.get('raises_this_round', 0) or 0)
        self.hand_number = int(payload.get('hand_number', 0) or 0)
        self.blind_level = int(payload.get('blind_level', 0) or 0)
        self.at_showdown = bool(payload.get('at_showdown', False))
        self.action_log = list(payload.get('action_log') or [])
        self.action_history = list(payload.get('action_history') or [])
        self.starting_stacks = dict(payload.get('starting_stacks') or {})
        self.hand_history = dict(payload.get('hand_history') or {})

        # Make sure transient flags don't keep stale UI state visible.
        self.waiting_for_human = False
        self._hero_folded_spectating = False
        try:
            self._exit_spectator_mode()
        except Exception:
            pass

        # Refresh everything that pulls from the model.
        try:
            self.table.set_board(self.board)
        except Exception:
            pass
        try:
            self.table.set_pot(self.pot)
        except Exception:
            pass
        try:
            STREETS_LOCAL = STREETS  # noqa: N806 — match casing in module
            street_name = STREETS_LOCAL[self.street_idx] \
                if 0 <= self.street_idx < len(STREETS_LOCAL) else "Preflop"
            self.table.set_street(street_name)
        except Exception:
            pass
        try:
            self.update_all_panels()
        except Exception:
            pass
        try:
            self.update_stats_display()
        except Exception:
            pass
        try:
            self.disable_human_actions()
        except Exception:
            pass

    def _menu_host(self):
        if self.network_mode:
            self._menu_status()
            return
        self._start_hosting()
        self._refresh_network_menu()

    def _menu_join(self):
        if self.network_mode:
            self._menu_status()
            return
        self._join_game()
        self._refresh_network_menu()

    def _menu_status(self):
        if not self.network_mode:
            QMessageBox.information(self, "Not connected",
                "You are playing single-player.\n"
                "Use Network > Host Game… or Network > Join Game… to go multiplayer.")
            return
        self._show_network_status_dialog()

    def _menu_disconnect(self):
        if self.network_mode:
            self._disconnect_network()
            self._refresh_network_menu()

    def _refresh_network_menu(self):
        """Enable/disable menu items based on current network state."""
        if not hasattr(self, 'act_status'):
            return
        active = bool(self.network_mode)
        self.act_host.setEnabled(not active and NETWORK_AVAILABLE)
        self.act_join.setEnabled(not active and NETWORK_AVAILABLE)
        self.act_status.setEnabled(active)
        self.act_disconnect.setEnabled(active)

    # --- Network Methods ---

    def show_network_dialog(self):
        """Show network mode selection dialog."""
        if not NETWORK_AVAILABLE:
            QMessageBox.warning(self, "Network Unavailable",
                              "Network module not available.\n"
                              "Please ensure the network package is installed.")
            return

        # If already in network mode, show status
        if self.network_mode:
            self._show_network_status_dialog()
            return

        dialog = NetworkModeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mode = dialog.get_mode()
            if mode == "host":
                self._start_hosting()
            elif mode == "join":
                self._join_game()

    @staticmethod
    def _get_local_lan_ips():
        """Return a sorted list of likely LAN IPv4 addresses for this
        machine. Falls back to empty list if nothing usable is found.

        Excludes loopback (127.x) and link-local (169.254.x). The
        outbound-socket trick (`connect` to 8.8.8.8 on UDP without
        actually sending) is the most reliable way to discover the
        primary LAN-facing interface even when there's no default
        route metadata in /proc; we still fold in any other addresses
        from socket.gethostbyname_ex as backup.
        """
        import socket
        ips = set()
        # Primary: the address used to reach the public internet.
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ips.add(s.getsockname()[0])
            finally:
                s.close()
        except Exception:
            pass
        # Backup: every IPv4 in the system's hostname resolution.
        try:
            host = socket.gethostname()
            for addr in socket.gethostbyname_ex(host)[2]:
                ips.add(addr)
        except Exception:
            pass
        # Filter out loopback and link-local.
        clean = [ip for ip in ips
                 if ip and not ip.startswith('127.')
                 and not ip.startswith('169.254.')]
        return sorted(clean)

    def _format_host_address_block(self) -> str:
        """Build the multi-line "what guests should type into Join
        Game" block. Lists the LAN IPs and the port on a separate
        line — guests need both, but joining them with `:` made the
        IP read as one combined string and clashed with the Host
        Game dialog where IP and Port live in separate fields.
        Used by both the post-Host-Game popup and the Network
        Status dialog so the two stay in sync.
        """
        port = ""
        try:
            port = str(self.network_server._server.serverPort())
        except Exception:
            pass
        ips = self._get_local_lan_ips()
        if not ips:
            return ("Address: (no LAN IP detected — guests on the "
                    "same machine can use 127.0.0.1)\n"
                    f"Port: {port}" if port else "")
        if len(ips) == 1:
            return (f"Address (give this to guests): {ips[0]}\n"
                    f"Port: {port}")
        lines = ["Addresses (give one of these to guests):"]
        for ip in ips:
            lines.append(f"   {ip}")
        lines.append(f"Port: {port}")
        return "\n".join(lines)

    def _show_network_status_dialog(self):
        """Show current network status with option to disconnect."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Network Status")
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)

        if self.network_mode == "host":
            status = (
                f"Hosting game: {self.network_server.server_name}\n"
                f"{self._format_host_address_block()}\n"
                f"Connected players: "
                f"{self.network_server.get_connected_count()}\n"
                f"Seated players: "
                f"{self.network_server.get_seated_count()}"
            )
        else:
            status = f"Connected to: {self.network_client.server_name}"
            status += f"\nYour seat: {self.my_seat + 1 if self.my_seat is not None else 'None'}"

        label = QLabel(status)
        label.setStyleSheet("font-size: 14px;")
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)

        # Disconnect button
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(lambda: self._disconnect_network(dialog))
        layout.addWidget(disconnect_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _apply_table_size(self, num_seats: int):
        """Resize the active table to `num_seats`. Seats beyond this index
        are hidden + flagged out (stack=0, active=False, hand cleared) so
        deal_hand skips them and the table looks like an N-seat table.

        Pass num_seats=len(self.players) to restore the default 6-seat
        layout."""
        total = len(self.player_panels)
        n = max(2, min(int(num_seats), total))
        self.network_num_seats = n
        for idx, panel in self.player_panels:
            visible = idx < n
            try:
                panel.setVisible(visible)
            except RuntimeError:
                pass
            if not visible:
                p = self.players[idx]
                p.stack = 0
                p.active = False
                p.hand = []
                p.bet_in_round = 0
                p.total_invested = 0
        self.update_all_panels()

    def _start_hosting(self):
        """Start hosting a network game."""
        dialog = HostGameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.network_server = dialog.get_server()
            if self.network_server:
                self.network_mode = "host"
                self._refresh_assist_checkbox_state()
                self.network_btn.setStyleSheet(
                    "QPushButton { font-size: 15px; background-color: #363; }"
                )
                self.network_btn.setText("Network*")

                # Use the short host name chosen in the dialog
                host_name = dialog.get_host_name() or "Host"
                self.players[0].name = host_name
                self.setWindowTitle(f"PokerIQ - Server ({host_name})")
                # Hide + disable seats above the chosen table size so the
                # game actually plays N-handed.
                self._apply_table_size(self.network_server.num_seats)
                self.update_all_panels()

                # Register persona names so the server can mask other guests'
                # real names from each guest. Personas come from the original
                # bot-persona names assigned to each seat at startup.
                personas = {seat: info[0] for seat, info in self.original_player_info.items()}
                self.network_server.set_personas(personas)

                # Connect server signals
                self.network_server.client_connected.connect(self._on_client_connected)
                self.network_server.client_disconnected.connect(self._on_client_disconnected)
                self.network_server.seat_assigned.connect(self._on_seat_assigned)
                self.network_server.action_received.connect(self._on_network_action_received)
                self.network_server.feature_toggled.connect(self._on_feature_toggle_received)

                self._refresh_feature_status()

                # Show the LAN address(es) prominently so the user
                # can read them off to other players. The port alone
                # was useless without an IP — guests had no way to
                # know what to type into Join Game.
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.NoIcon)
                msg.setWindowTitle("Server Started")
                msg.setTextFormat(Qt.TextFormat.PlainText)
                msg.setText(
                    f"Hosting game on port "
                    f"{self.network_server._server.serverPort()}.\n\n"
                    f"{self._format_host_address_block()}\n\n"
                    "Waiting for players to connect…"
                )
                # Make the address block selectable so the user can
                # copy / paste it into chat, email, etc.
                for child in msg.findChildren(QLabel):
                    child.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse)
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()

    def _join_game(self):
        """Join a network game."""
        # First show connect dialog. Default placeholder is a short,
        # within-12-char name; the user is expected to replace it.
        join_dialog = JoinGameDialog("Guest", self)
        if join_dialog.exec() == QDialog.DialogCode.Accepted:
            self.network_client = join_dialog.get_client()
            if self.network_client:
                # Now show seat selection
                # If the seat list has already arrived during the connect
                # handshake, use its size; otherwise fall back to 6.
                seats_known = (len(self.network_client.seats)
                               if getattr(self.network_client, 'seats', None)
                               else 6)
                seat_dialog = SeatSelectionDialog(self.network_client, seats_known, self)
                seat_dialog.seat_selected.connect(self._on_my_seat_selected)

                if seat_dialog.exec() == QDialog.DialogCode.Accepted:
                    self.network_mode = "client"
                    self._refresh_assist_checkbox_state()
                    self.network_btn.setStyleSheet(
                        "QPushButton { font-size: 15px; background-color: #336; }"
                    )
                    self.network_btn.setText("Network*")
                    my_name = self.network_client.player_name or "Guest"
                    self.setWindowTitle(f"PokerIQ - Client ({my_name})")

                    # Connect client signals for game events
                    self._connect_client_signals()
                    self._refresh_feature_status()

                    # Replay the seat list we already have so already-seated
                    # guests' real names land in our player panels (the
                    # SEAT_LIST broadcasts that occurred during seat selection
                    # arrived before signals were connected).
                    if self.network_client.seats:
                        self._on_seat_list_updated(dict(self.network_client.seats))

                    # Disable New Hand on client (server controls game flow)
                    self.new_hand_btn.setEnabled(False)
                else:
                    # User cancelled seat selection
                    self.network_client.disconnect_from_server()
                    self.network_client = None

    def _connect_client_signals(self):
        """Connect client signals for receiving game events."""
        client = self.network_client
        client.disconnected.connect(self._on_disconnected_from_server)
        client.hole_cards_received.connect(self._on_hole_cards_received)
        client.community_cards_received.connect(self._on_community_cards_received)
        client.action_requested.connect(self._on_action_requested)
        client.action_broadcast.connect(self._on_action_broadcast_received)
        client.stack_update_received.connect(self._on_stack_update_received)
        client.hand_started.connect(self._on_hand_started)
        client.hand_ended.connect(self._on_hand_ended)
        client.active_player_changed.connect(self._on_active_player_changed)
        client.feature_toggle_received.connect(self._on_feature_toggle_received)
        client.tom_advice_received.connect(self._on_tom_advice_received)
        client.hand_analysis_received.connect(self._on_hand_analysis_received)
        client.seat_list_received.connect(self._on_seat_list_updated)
        client.all_hole_cards_received.connect(self._on_all_hole_cards_received)
        client.board_snapshot_received.connect(self._on_board_snapshot_received)
        client.hand_interpretation_received.connect(self._on_hand_interpretation_received)

    def _on_seat_list_updated(self, seats: dict):
        """Update player panel names when seat list arrives so every guest
        sees every other player's real entered name (not the bot persona).
        Empty seats keep their local bot persona name. Also resize the
        local table to match the host's num_seats (derived from how many
        seats the seat list contains)."""
        try:
            if seats:
                self._apply_table_size(len(seats))
            for seat_index, name in seats.items():
                seat_index = int(seat_index)
                if not (0 <= seat_index < len(self.players)):
                    continue
                if name:
                    self.players[seat_index].name = name
                else:
                    # Empty seat — restore local bot persona name
                    fallback = self.original_player_info.get(seat_index)
                    if fallback:
                        self.players[seat_index].name = fallback[0]
            if hasattr(self, 'tom_panel'):
                try:
                    self.tom_panel.setup_tabs(self.players, getattr(self, "network_human_seats", set()))
                except Exception:
                    pass
            self.update_all_panels()
        except Exception as ex:
            print(f"[client] failed to apply seat-list update: {ex}")

    def _on_all_hole_cards_received(self, cards_by_seat: dict):
        """Server pushed every active seat's hole cards (we just folded and
        are now spectating) — populate player.hand for each seat and refresh.
        Also write each revealed hand to the log so post-game Claude
        annotation has the spectator view of the table.
        """
        try:
            for seat, cards in cards_by_seat.items():
                seat = int(seat)
                if 0 <= seat < len(self.players) and cards:
                    self.players[seat].hand = [eval7.Card(c) for c in cards]
            # If we're spectating, force God Mode on so cards are visible.
            if getattr(self, '_hero_folded_spectating', False):
                if not self.god_mode_cb.isChecked():
                    self.god_mode_cb.setChecked(True)
            self.update_all_panels()
            self.update_stats_display()
            # Log every revealed hand so the annotated transcript has them
            self.write_log("All Hole Cards (spectator view):")
            for seat in sorted(cards_by_seat.keys(), key=lambda x: int(x)):
                seat_i = int(seat)
                if 0 <= seat_i < len(self.players):
                    name = self.players[seat_i].name
                    self.write_log(f"  {name}: {' '.join(cards_by_seat[seat])}")
        except Exception as ex:
            print(f"[client] failed to apply ALL_HOLE_CARDS: {ex}")

    def _on_board_snapshot_received(self, street: str, street_idx: int,
                                     board: list, action_log: list):
        """Cache a per-street snapshot so the spectator can scroll back/forth
        through past streets."""
        if not hasattr(self, '_spectator_street_snapshots'):
            self._spectator_street_snapshots = []
            self._spectator_view_idx = -1
        snap = {
            'street': street,
            'street_idx': int(street_idx),
            'board': list(board),
            'action_log': list(action_log),
        }
        # Replace existing snapshot for this street_idx if we already have one
        replaced = False
        for i, existing in enumerate(self._spectator_street_snapshots):
            if existing.get('street_idx') == snap['street_idx']:
                self._spectator_street_snapshots[i] = snap
                replaced = True
                break
        if not replaced:
            self._spectator_street_snapshots.append(snap)
        # Update spectator nav buttons if they exist
        self._update_spectator_nav_buttons()

    def _on_hand_interpretation_received(self, text: str, hand_number: int,
                                          assists_used: dict):
        """Host sent us the narrative summary — show the same Hand Summary
        dialog (with bright assists banner + Claude analysis blocks) and
        write the full interpretation to the log so the post-game annotated
        report has the same context the host has."""
        try:
            self._latest_assists_used = assists_used or {}
            # Mirror the host's HAND INTERPRETATION block in the log
            try:
                self.write_log("\n" + "=" * 40)
                self.write_log("HAND INTERPRETATION:")
                for line in (text or '').split('\n'):
                    self.write_log(f"  {line}")
                if assists_used:
                    for name, used in sorted(assists_used.items()):
                        used_list = sorted(used) if not isinstance(used, list) else used
                        self.write_log(f"  [{name} used while still in hand: "
                                       f"{', '.join(used_list)}]")
                self.write_log("=" * 40)
            except Exception as ex:
                print(f"[client] interpretation log failed: {ex}")
            self._show_hand_interpretation_text(text, hand_number, assists_used or {})
        except Exception as ex:
            print(f"[client] failed to render hand interpretation: {ex}")

    def _on_hand_analysis_received(self, analyses: list, hand_number: int):
        """Host-supplied Claude analyses arrived: route into the live summary
        dialog (if any), otherwise cache for the next one that opens.
        Cache is keyed by hand_number so the next hand's dialog never picks
        up a previous hand's analysis."""
        self._latest_hand_analyses = list(analyses)
        self._latest_hand_analyses_hand = int(hand_number)
        target = getattr(self, '_active_summary_dialog', None)
        target_layout = getattr(self, '_active_summary_layout', None)
        if target is None or target_layout is None:
            return
        try:
            placeholder = getattr(self, '_active_summary_placeholder', None)
            if placeholder is not None:
                placeholder.deleteLater()
                self._active_summary_placeholder = None
            for a in analyses:
                name = a.get('player', '?')
                text = (a.get('text') or '').strip()
                model = (a.get('model') or '').strip() or 'Claude'
                if not text:
                    fail_block = QLabel(
                        f"{model} — {name} (host): (no analysis — host's "
                        "claude returned nothing for this POV)")
                    fail_block.setFont(QFont('Arial', 18))
                    fail_block.setWordWrap(True)
                    fail_block.setStyleSheet(
                        "color: #fc6; background-color: #2a1a1a; padding: 10px;"
                        " border-radius: 5px; margin: 4px 0;"
                    )
                    target_layout.addWidget(fail_block)
                    continue
                block = QLabel(f"{model} — {name} (host):\n{text}")
                block.setFont(QFont('Arial', 18))
                block.setWordWrap(True)
                block.setStyleSheet(
                    "color: #8f8; background-color: #1a2a1a; padding: 10px;"
                    " border-radius: 5px; margin: 4px 0;"
                )
                target_layout.addWidget(block)
        except RuntimeError:
            pass  # dialog closed before we could render

    def _on_tom_advice_received(self, advice: str, notation: str, for_seat: int):
        """Display personalized Theory-of-Mind advice from the host."""
        if not hasattr(self, 'tom_panel'):
            return
        # Sanity check: the message is addressed to us.
        if for_seat >= 0 and self.my_seat is not None and for_seat != self.my_seat:
            return
        try:
            self.tom_panel.advisor_advice.setText(advice or "")
            # Switch to the Advisor tab so the user notices the new advice.
            self.tom_panel.tabs.setCurrentIndex(0)
        except Exception as ex:
            print(f"[ToM] could not render remote advice: {ex}")

    def _on_my_seat_selected(self, seat_index: int):
        """Handle our seat selection confirmation."""
        self.my_seat = seat_index
        # Update hero player to this seat — use the name the user entered
        # in JoinGameDialog, not a hardcoded placeholder.
        my_name = (self.network_client.player_name
                   if self.network_client and self.network_client.player_name
                   else "Guest")
        self.players[seat_index].style = 'human'
        self.players[seat_index].name = my_name

        # Mark server host player (seat 0) as network_human so ToM creates a tab
        if seat_index != 0:
            seats = self.network_client.seats if self.network_client else {}
            if 0 in seats and seats[0] is not None:
                self.players[0].style = 'network_human'
                self.players[0].name = seats[0]  # host's chosen short name

        # Refresh Theory of Mind tabs to include all non-hero players
        if hasattr(self, 'tom_panel'):
            self.tom_panel.setup_tabs(self.players, getattr(self, "network_human_seats", set()))

        self.update_all_panels()

    def _disconnect_network(self, dialog=None):
        """Disconnect from network game."""
        if self.network_mode == "host" and self.network_server:
            self.network_server.stop()
            self.network_server = None
        elif self.network_mode == "client" and self.network_client:
            self.network_client.disconnect_from_server()
            self.network_client = None

        self.network_mode = None
        self._refresh_assist_checkbox_state()
        self.my_seat = None
        self.network_human_seats.clear()
        self.network_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.network_btn.setText("Network")
        self.setWindowTitle("PokerIQ")
        self.new_hand_btn.setEnabled(True)

        # Reset players to local setup
        for seat, (name, style) in self.original_player_info.items():
            self.players[seat].name = name
            self.players[seat].style = style
        self._apply_bot_preferences()
        # Restore the full 6-seat table after exiting a smaller-table
        # network game.
        self._apply_table_size(len(self.players))
        self.update_all_panels()

        if dialog:
            dialog.accept()

    # --- Network Event Handlers (Host) ---

    def _on_client_connected(self, client_id: str, player_name: str):
        """Handle client connection (host only)."""
        self.update_status(f"{player_name} connected")

    def _on_client_disconnected(self, client_id: str):
        """Handle client disconnection (host only).

        Swap the dropped seat back to its original bot persona/style and
        log "human X replaced by bot Y" so post-game annotation captures
        the change. If the dropped client had the action, hand off to the
        bot immediately so play continues."""
        self.update_status("A player disconnected")
        was_current_player_seat = None
        for seat in list(self.network_human_seats):
            if self.network_server.get_client_for_seat(seat) is None:
                # The seat lost its remote owner — turn it back into a bot.
                self.network_human_seats.discard(seat)
                old_name = self.players[seat].name
                bot_name, bot_style = self.original_player_info[seat]
                self.players[seat].style = bot_style
                self.players[seat].name = bot_name
                self.write_log(
                    f"[seat swap] {old_name} (human) replaced by {bot_name} (bot)")
                self.log_action(f"{old_name} → {bot_name} (bot)")
                if seat == getattr(self, 'current_player_idx', -1):
                    was_current_player_seat = seat

        # Push the updated seat list to remaining clients so their panels
        # show the bot persona name for the now-vacated seat.
        try:
            self.network_server._broadcast_seat_list()
        except Exception:
            pass

        self.update_all_panels()

        # If we were waiting on the dropped client's action, kick the bot
        # in so the hand keeps moving.
        if (was_current_player_seat is not None
                and getattr(self, 'waiting_for_network_action', False)):
            self.waiting_for_network_action = False
            QTimer.singleShot(0, self.process_bot_action)

    def _on_seat_assigned(self, client_id: str, seat_index: int):
        """Handle seat assignment (host only). Logs the bot→human swap and,
        if the new client took an active seat mid-hand, sends them the
        seat's current hole cards so they can immediately participate.
        """
        old_name = self.players[seat_index].name
        was_bot = seat_index not in self.network_human_seats

        self.network_human_seats.add(seat_index)
        player_name = self.network_server._clients[client_id].player_name
        self.players[seat_index].style = 'network_human'
        self.players[seat_index].name = player_name

        if was_bot:
            self.write_log(
                f"[seat swap] {old_name} (bot) replaced by {player_name} (human)")
            self.log_action(f"{old_name} → {player_name} (human)")

        # If a hand is in progress and this seat already has hole cards,
        # send them privately to the joining client so they take over the
        # seat seamlessly. Stops them from staring at a blank panel.
        try:
            if self.players[seat_index].hand:
                cards = [str(c) for c in self.players[seat_index].hand]
                self.network_server.send_hole_cards(client_id, cards)
        except Exception as ex:
            print(f"[host] mid-hand hole-card forward failed: {ex}")

        self.update_all_panels()
        self.update_status(f"{player_name} took seat {seat_index + 1}")

    def _on_network_action_received(self, client_id: str, action: str, amount: float):
        """Handle action received from network player."""
        if not self.waiting_for_network_action:
            return

        # Find the player's seat
        for seat, cid in self.network_server._seats.items():
            if cid == client_id:
                if seat == self.current_player_idx:
                    # Process the action
                    self.waiting_for_network_action = False
                    self._process_network_action(action, amount)
                break

    def _process_network_action(self, action: str, amount: float):
        """Process an action from a network player."""
        player = self.players[self.current_player_idx]
        action_lower = action.lower()

        if action_lower == 'fold':
            player.active = False
            self.log_action(f"{player.name}: Folds")
            # Push every active seat's hole cards to the folded client so
            # their God-mode display is meaningful.
            self._send_spectator_hole_cards_to_seat(self.current_player_idx)
        elif action_lower == 'check':
            self.log_action(f"{player.name}: Checks")
        elif action_lower == 'call':
            call_amount = min(self.current_bet - player.bet_in_round, player.stack)
            player.stack -= call_amount
            player.bet_in_round += call_amount
            player.total_invested += call_amount
            self.pot += call_amount
            self.log_action(f"{player.name}: Calls ${call_amount}")
        elif action_lower in ['bet', 'raise']:
            _, bb_amount = BLIND_LEVELS[self.blind_level]
            to_call_now = max(0, self.current_bet - player.bet_in_round)
            prev_raise = int(getattr(self, 'last_raise_size', bb_amount))
            min_raise_above = max(int(bb_amount), prev_raise)
            min_total = to_call_now + min_raise_above
            bet_amount = max(int(amount), min_total)
            actual_bet = min(bet_amount, player.stack)
            player.stack -= actual_bet
            player.bet_in_round += actual_bet
            player.total_invested += actual_bet
            self.pot += actual_bet
            if player.bet_in_round > self.current_bet:
                new_raise_size = player.bet_in_round - self.current_bet
                self.current_bet = player.bet_in_round
                self.last_raiser = self.current_player_idx
                self.raises_this_round += 1
                if new_raise_size >= min_raise_above:
                    self.last_raise_size = int(new_raise_size)
                for p in self.players:
                    if p != player:
                        p.actions_this_round = 0
                # Visual cue — flash the raiser's panel.  Color graded by
                # raise size relative to the pot before the raise.
                panel = self.get_panel(self.current_player_idx)
                if panel is not None and hasattr(panel, 'flash_raise'):
                    pot_before = max(0, self.pot - actual_bet)
                    color = self._flash_color_for_raise(new_raise_size, pot_before)
                    panel.flash_raise(color=color)
            self.log_action(f"{player.name}: {'Raises to' if action_lower == 'raise' else 'Bets'} ${actual_bet}")
        elif action_lower == 'all-in':
            all_in_amount = player.stack
            player.stack = 0
            player.bet_in_round += all_in_amount
            player.total_invested += all_in_amount
            self.pot += all_in_amount
            if player.bet_in_round > self.current_bet:
                self.current_bet = player.bet_in_round
                self.last_raiser = self.current_player_idx
                self.raises_this_round += 1
                for p in self.players:
                    if p != player:
                        p.actions_this_round = 0
            self.log_action(f"{player.name}: All-in ${all_in_amount}")

        player.actions_this_round += 1

        if player.stack == 0 and action_lower != 'fold':
            self._record_all_in(player.name)

        # Broadcast action to all clients
        if self.network_server:
            stacks = {i: p.stack for i, p in enumerate(self.players)}
            self.network_server.broadcast_action(
                self.current_player_idx, player.name, action, amount, self.pot,
                stacks=stacks
            )

        # Update display
        self.update_all_panels()
        self.table.set_pot(self.pot)
        self.table.update()

        # Move to next player (same logic as process_action)
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

        if self.count_active() < 2:
            self.end_hand()
        else:
            all_acted = all(p.actions_this_round > 0 for p in self.players if p.active and p.stack > 0)
            all_matched = all(p.bet_in_round == self.current_bet for p in self.players if p.active)
            if all_acted and all_matched:
                self.end_betting_round()
            else:
                self.process_next_player()

    # --- Host helpers for spectator support ---

    def _send_spectator_hole_cards_to_seat(self, seat_index: int):
        """Push every active seat's hole cards to the client at seat_index.
        Called when that client folds so they immediately see God-mode cards.
        """
        if self.network_mode != "host" or not self.network_server:
            return
        client_id = self.network_server.get_client_for_seat(seat_index)
        if not client_id:
            return  # Host fold (no remote client to push to)
        cards_by_seat = {}
        for i, p in enumerate(self.players):
            if p.hand:
                cards_by_seat[i] = [str(c) for c in p.hand]
        self.network_server.send_all_hole_cards(client_id, cards_by_seat)

    def _refresh_spectator_hole_cards(self):
        """When a new street is dealt, re-push hole cards to every client
        that has already folded so their view stays in sync."""
        if self.network_mode != "host" or not self.network_server:
            return
        cards_by_seat = {}
        for i, p in enumerate(self.players):
            if p.hand:
                cards_by_seat[i] = [str(c) for c in p.hand]
        for seat in list(self.network_human_seats):
            if seat < len(self.players) and not self.players[seat].active:
                client_id = self.network_server.get_client_for_seat(seat)
                if client_id:
                    self.network_server.send_all_hole_cards(client_id, cards_by_seat)

    # --- Network Event Handlers (Client) ---

    def _on_disconnected_from_server(self):
        """Handle disconnection from server.

        Don't kick the user back to the menu — instead, fall back to local
        single-player. All other seats become bots (their original
        personas), the user's seat becomes the local hero (preserving the
        name they joined with), and the next New Hand is local."""
        if self.network_mode != "client":
            return

        # Capture the guest's identity before we tear down network state.
        guest_name = None
        if self.my_seat is not None and 0 <= self.my_seat < len(self.players):
            guest_name = self.players[self.my_seat].name

        # Log the host exit so post-game annotation captures it.
        try:
            self.write_log("[network] Host disconnected — switching to local play.")
        except Exception:
            pass

        # Tear down network state without resetting player names
        if self.network_client:
            try:
                self.network_client.disconnect_from_server()
            except Exception:
                pass
        self.network_client = None
        self.network_mode = None
        self._refresh_assist_checkbox_state()
        self.my_seat = None
        self.network_human_seats.clear()
        self.network_btn.setStyleSheet("QPushButton { font-size: 15px; }")
        self.network_btn.setText("Network")
        self.setWindowTitle("PokerIQ - Local (host exited)")
        self.new_hand_btn.setEnabled(True)

        # All seats become local bots (their original personas)…
        for seat, (name, style) in self.original_player_info.items():
            self.players[seat].name = name
            self.players[seat].style = style
        self._apply_bot_preferences()

        # …except seat 0 which becomes the local human hero, keeping the
        # name the user joined with so their identity is preserved.
        self.players[0].style = 'human'
        if guest_name:
            self.players[0].name = guest_name

        # Close any open prior-hand summary dialogs from the network game.
        self._close_open_hand_dialogs()
        self.update_all_panels()
        # Match the Confirm big bet / Game Over treatment: no icon
        # column, 24pt bold body text, 720px min-width so the
        # explanation reads at arm's length.
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setWindowTitle("Host disconnected")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<div style='font-size:24px; font-weight:bold; color:#000;'>"
            "The host left the game.</div>"
            "<div style='font-size:24px; font-weight:bold; color:#000;"
            " margin-top:8px;'>"
            "You can keep playing locally — bots will fill all other "
            "seats. Click New Hand to start.</div>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet(
            "QMessageBox { background-color: #f0f0f0; }"
            "QMessageBox QLabel { color: #000;"
            " background-color: transparent; font-size: 24px;"
            " min-width: 720px; padding: 14px 10px; }"
            "QMessageBox QPushButton { font-size: 18px;"
            " padding: 10px 28px; min-width: 120px; }"
        )
        msg.exec()

    def _on_hole_cards_received(self, cards: list):
        """Handle receiving our hole cards."""
        if self.my_seat is not None:
            # Convert string cards to eval7 cards
            player = self.players[self.my_seat]
            player.hand = [eval7.Card(c) for c in cards]
            self.update_all_panels()
            # Track for hand interpretation + annotation
            self.hand_history['hero_cards'] = list(cards)
            try:
                self.hand_history['hero_hand_name'] = get_hand_name(player.hand)
            except Exception:
                pass
            self.write_log(f"Your hole cards: {' '.join(cards)}")
            # Bracelets-style per-hand-start counters (hero only on client;
            # we don't see other players' cards so per-class stats are local)
            try:
                self._record_hand_start_stats()
            except Exception:
                pass

    def _on_community_cards_received(self, cards: list, street: str):
        """Handle receiving community cards."""
        self.board = [eval7.Card(c) for c in cards]
        # Track street index for Theory of Mind
        street_map = {"Flop": 1, "Turn": 2, "River": 3}
        if street in street_map:
            self.street_idx = street_map[street]
        # Reset bet_in_round for new street
        for p in self.players:
            p.bet_in_round = 0
        self.current_bet = 0
        # New street → next legal raise can be just one BB.
        try:
            _, bb_amt = BLIND_LEVELS[self.blind_level]
            self.last_raise_size = int(bb_amt)
        except Exception:
            pass
        self.action_log = []
        self.log_action(f"--- {street} ---")
        # Track + log the per-street board so Claude annotation can see it
        self.hand_history.setdefault('board_by_street', {})[street] = list(cards)
        self.write_log(f"Board ({street}): {' '.join(cards)}")
        self.update_all_panels()
        # If the spectator has scrolled to a past snapshot, leave their view
        # alone; otherwise show the new (live) board.
        if (getattr(self, '_hero_folded_spectating', False)
                and getattr(self, '_spectator_view_idx', -1) >= 0):
            self._spectator_show_snapshot(self._spectator_view_idx)
        else:
            self.table.set_board(self.board)

    def _on_action_requested(self, valid_actions: list, to_call: float,
                             min_raise: float, max_raise: float, pot: float):
        """Handle action request from server."""
        # Enable action buttons for this player
        self.waiting_for_human = True
        self.pot = pot
        self.current_bet = to_call + self.players[self.my_seat].bet_in_round

        # Highlight our seat as active (yellow highlight is sufficient)
        self.set_active_player(self.my_seat)
        self.enable_action_buttons(to_call, min_raise, max_raise)

    def _on_action_broadcast_received(self, seat: int, player_name: str,
                                       action: str, amount: float, pot: float):
        """Handle action broadcast from server."""
        self.pot = pot
        player = self.players[seat]
        player.last_action = action
        player.last_bet = amount

        # Update player state based on action
        action_lower = action.lower()
        if action_lower == 'fold':
            player.active = False
        elif action_lower == 'call':
            call_amount = min(amount, player.stack) if amount > 0 else 0
            if call_amount > 0:
                player.stack -= call_amount
                player.bet_in_round = getattr(player, 'bet_in_round', 0) + call_amount
        elif action_lower in ['bet', 'raise']:
            actual_bet = min(amount, player.stack)
            if actual_bet > 0:
                player.stack -= actual_bet
                player.bet_in_round = getattr(player, 'bet_in_round', 0) + actual_bet
            # Track the raise size so our local raise dialog enforces the
            # No-Limit min-raise rule on the next decision. Approximated
            # from the broadcast amount minus the prior to_call (we don't
            # have the host's exact accounting, but amount is the chips
            # added this turn — close enough for UI purposes).
            try:
                _, bb_amt = BLIND_LEVELS[self.blind_level]
                self.last_raise_size = max(int(amount), int(bb_amt))
            except Exception:
                pass
            # Visual cue — flash the raiser's panel.  Color graded by
            # raise size relative to the pot BEFORE this raise (pot in
            # the broadcast already includes the new chips, so subtract).
            panel = self.get_panel(seat)
            if panel is not None and hasattr(panel, 'flash_raise'):
                pot_before = max(0, float(pot) - float(amount or 0))
                color = self._flash_color_for_raise(amount, pot_before)
                panel.flash_raise(color=color)
        elif action_lower == 'all-in':
            player.stack = 0
            # All-ins are always significant — full red flash.
            panel = self.get_panel(seat)
            if panel is not None and hasattr(panel, 'flash_raise'):
                panel.flash_raise(color='red')

        if player.stack == 0 and action_lower != 'fold':
            self._record_all_in(player_name)

        self.table.set_pot(pot)

        # Highlight the player who just acted
        self.set_active_player(seat)

        # Log the action (triggers Theory of Mind update and action history)
        action_text = f"{player_name} {action}" + (f" ${amount:.0f}" if amount > 0 else "")
        self.log_action(action_text)
        self.update_all_panels()
        self.table.update()

    def _on_stack_update_received(self, stacks: dict):
        """Authoritative per-seat stacks from the host. Overwrites the local
        heuristic in `_on_action_broadcast_received` (which can be wrong for
        zero-amount calls or clamped raises) and also picks up the winner's
        chip gain after pot distribution at hand end.
        """
        for seat, stack in stacks.items():
            seat = int(seat)
            if 0 <= seat < len(self.players):
                self.players[seat].stack = stack
        self.update_all_panels()

    def _on_active_player_changed(self, seat: int):
        """Handle active player broadcast from server."""
        self.set_active_player(seat)

    def _on_hand_started(self, hand_num: int, button: int, blinds: tuple, stacks: dict):
        """Handle new hand start from server."""
        # Lock the New Hand button while the hand is in flight.
        if hasattr(self, 'new_hand_btn'):
            self.new_hand_btn.setEnabled(False)
        self.hand_number = hand_num
        self.dealer_idx = button
        self.pot = blinds[0] + blinds[1]
        self.board = []
        self.action_log = []
        self.street_idx = 0
        self.action_history = []
        self.current_bet = 0
        # Reset min-raise floor at start of hand to BB.
        try:
            self.last_raise_size = int(blinds[1])
        except Exception:
            self.last_raise_size = 2
        # Fresh per-hand history so the Hand Log button has clean data.
        self.hand_history = {
            'hero_cards': [],
            'hero_actions': [],
            'street_equities': {},
            'key_events': [],
            'board_by_street': {},
            'street_stats': {},
            'street_actions': {},
            'pot_by_street': {},
        }

        # Fresh hand → fresh spectator state. Anyone who was spectating must
        # exit spectator mode so they can act in the new hand.
        if getattr(self, '_hero_folded_spectating', False):
            self._exit_spectator_mode()
        self._spectator_street_snapshots = []
        self._spectator_view_idx = -1
        self.hand_assists_used = {}
        # Drop any cached Claude analyses from the prior hand
        self._latest_hand_analyses = None
        self._latest_hand_analyses_hand = None
        # Dismiss any prior-hand summary / stats dialogs left open
        self._close_open_hand_dialogs()
        # First hand of the session: log GAME STATUS (bracelets-style)
        if not getattr(self, '_game_status_logged', False):
            self._log_game_status()
            self._game_status_logged = True

        # Reset bet_in_round for all players
        for p in self.players:
            p.bet_in_round = 0

        # Update stacks. Mark a seat active ONLY if it has chips —
        # otherwise the host's stacks dict (which includes every
        # canonical seat 0..5 even on a 4-seat table) re-flags the
        # phantom 5/6 entries as active=True, defeating the
        # "hide stack==0, not active" rule in update_all_panels and
        # leaving zero-balance bot panels visible to guests.
        for seat, stack in stacks.items():
            self.players[seat].stack = stack
            self.players[seat].active = stack > 0
            self.players[seat].hand = None

        # Match host: show BT / SB / BB / UTG / CO position tags on each
        # PlayerPanel. We derive them from the dealer (button) seat the
        # host just sent.
        sb_idx = bb_idx = -1
        try:
            n = len(self.players)
            sb_idx = (button + 1) % n
            while not self.players[sb_idx].active and sb_idx != button:
                sb_idx = (sb_idx + 1) % n
            bb_idx = (sb_idx + 1) % n
            while not self.players[bb_idx].active and bb_idx != sb_idx:
                bb_idx = (bb_idx + 1) % n
            utg_idx = (bb_idx + 1) % n
            while not self.players[utg_idx].active and utg_idx != bb_idx:
                utg_idx = (utg_idx + 1) % n
            co_idx = (button - 1) % n
            while not self.players[co_idx].active and co_idx != button:
                co_idx = (co_idx - 1) % n
            for idx, panel in self.player_panels:
                if idx == button:
                    panel.set_position("BT")
                elif idx == sb_idx:
                    panel.set_position("SB")
                elif idx == bb_idx:
                    panel.set_position("BB")
                elif idx == utg_idx and utg_idx != button:
                    panel.set_position("UTG")
                elif idx == co_idx and co_idx not in (sb_idx, bb_idx, utg_idx):
                    panel.set_position("CO")
                else:
                    panel.set_position("")
        except Exception as ex:
            print(f"[client] position tag update failed: {ex}")

        # Refresh the deceptive-God-Mode cache for this hand on the
        # client side. Server's broadcast_hand_start tells us how many
        # seats are seated; the cache uses self.players, which we
        # just synced above.
        self._build_deception_hands_for_hand()

        # Surface the blind posts on the client so guests see (a) the
        # running ticker at the bottom and (b) the per-seat "Bet: $N"
        # chip labels on the SB and BB panels from the very first
        # frame of the hand. The host posts blinds locally before
        # broadcasting hand_start, but doesn't fire individual ACTION
        # broadcasts for the posts — without this the SB/BB chips
        # look invisible on every guest's screen until someone
        # actually raises.
        try:
            sb_amount = int(blinds[0]) if blinds else 0
            bb_amount = int(blinds[1]) if (blinds and len(blinds) >= 2) else 0
            if 0 <= sb_idx < len(self.players) and sb_amount > 0:
                self.players[sb_idx].bet_in_round = sb_amount
                self.action_log.append(
                    f"{self.players[sb_idx].name} posts ${sb_amount}")
            if 0 <= bb_idx < len(self.players) and bb_amount > 0:
                self.players[bb_idx].bet_in_round = bb_amount
                self.action_log.append(
                    f"{self.players[bb_idx].name} posts ${bb_amount}")
                self.current_bet = bb_amount
                self.last_raise_size = bb_amount
            try:
                self.log_label.setText(
                    self._format_action_log_html(self.action_log))
            except AttributeError:
                self.log_label.setText(" | ".join(self.action_log))
        except Exception as ex:
            print(f"[client] blind ticker update failed: {ex}")

        self.update_all_panels()
        self.table.set_board([])
        self.table.set_pot(self.pot)
        self.log_action(f"Hand #{hand_num} starting...")

        # Mirror the host's per-hand log header so post-game Claude
        # annotation has hole-card / board-texture context.
        try:
            self.write_log(f"\n{'='*60}")
            self.write_log(f"HAND #{hand_num} - {datetime.now().strftime('%H:%M:%S')}")
            self.write_log(f"{'='*60}")
            sb = blinds[0] if isinstance(blinds, (tuple, list)) and len(blinds) >= 1 else 0
            bb = blinds[1] if isinstance(blinds, (tuple, list)) and len(blinds) >= 2 else 0
            self.write_log(f"Blinds: ${sb}/${bb}")
            if 0 <= button < len(self.players):
                self.write_log(f"Dealer: {self.players[button].name}")
            self.write_log("Stacks:")
            for seat in sorted(stacks.keys(), key=lambda x: int(x)):
                p = self.players[int(seat)]
                self.write_log(f"  {p.name}: ${stacks[seat]}")
        except Exception as ex:
            print(f"[client] hand-start log failed: {ex}")

    def _on_hand_ended(self, winners: list, pot: float, shown_hands: dict, hand_summary: dict = None):
        """Handle hand end from server.

        Cache the graphical-stats payload so the text-summary dialog's
        ``Stats`` button can render it when the user clicks. The text
        summary itself arrives as a separate HAND_INTERPRETATION message
        and is rendered by `_on_hand_interpretation_received`.
        """
        # Hand has ended — re-enable the New Hand button. (Host drives the
        # actual deal; on the client this just keeps the button visually
        # consistent with the host.)
        if hasattr(self, 'new_hand_btn'):
            self.new_hand_btn.setEnabled(True)
        # Show results
        winner_names = [self.players[w].name for w in winners]
        self.update_status(f"Winners: {', '.join(winner_names)} - Pot: ${pot:.0f}")

        # Show revealed hands
        for seat, cards in shown_hands.items():
            self.players[seat].hand = [eval7.Card(c) for c in cards]

        self.update_all_panels()

        # Write a per-hand showdown block to the log so the post-game
        # Claude annotation can see hole cards, board textures, winners,
        # and final stacks for THIS hand.
        try:
            self.write_log("--- Showdown ---")
            if self.board:
                self.write_log(f"Final Board: {format_cards(self.board)}")
            # Prefer hand_summary['player_hands'] (covers folded players too)
            player_hands = (hand_summary or {}).get('player_hands', {}) or {}
            if player_hands:
                self.write_log("All Hole Cards:")
                for name, cards in sorted(player_hands.items()):
                    self.write_log(f"  {name}: {' '.join(cards)}")
            elif shown_hands:
                self.write_log("Revealed Hands:")
                for seat, cards in shown_hands.items():
                    name = self.players[int(seat)].name
                    self.write_log(f"  {name}: {' '.join(cards)}")
            self.write_log(f"Winner(s): {', '.join(winner_names)} - Pot: ${pot:.0f}")
            # Per-street boards (informational; clients also log per arrival)
            board_by_street = (hand_summary or {}).get('board_by_street', {}) or {}
            if board_by_street:
                for street in ['Preflop', 'Flop', 'Turn', 'River']:
                    cards = board_by_street.get(street)
                    if cards:
                        self.write_log(f"  Board @ {street}: {' '.join(cards)}")
            # Final stacks
            player_results = (hand_summary or {}).get('player_results', {}) or {}
            if player_results:
                self.write_log("Final Stacks:")
                for name, vals in sorted(player_results.items()):
                    if isinstance(vals, (list, tuple)) and len(vals) >= 2:
                        start, end = vals[0], vals[1]
                        change = (vals[2] if len(vals) >= 3 else end - start)
                        self.write_log(f"  {name}: ${end} (Δ${change:+.0f})")
            # Bracelets-style per-hand stat updates + CHIP COUNT + table
            # snapshot so the guest's post-game annotation has them too.
            try:
                self._finalize_hand_stats(
                    [self.players[w].name for w in winners
                     if 0 <= w < len(self.players)],
                    [self.players[w].name for w in winners
                     if 0 <= w < len(self.players)] if shown_hands else []
                )
                self._log_chip_count()
                self._log_table_stats()
            except Exception as ex:
                print(f"[client] per-hand stat update failed: {ex}")
        except Exception as ex:
            print(f"[client] hand-end log failed: {ex}")

        # Folded clients stay parked in spectator mode so they can keep
        # paging through streets (including the showdown snapshot the
        # host broadcasts).  Spectator UI tears down only when the next
        # hand begins (server pushes a new "hand_start").  Refresh nav
        # button enabled-state in case the showdown snapshot just arrived.
        if getattr(self, '_hero_folded_spectating', False):
            self._update_spectator_nav_buttons()

        if hand_summary:
            try:
                street_stats = {}
                for street, stats_list in hand_summary.get('street_stats', {}).items():
                    street_stats[street] = [tuple(s) for s in stats_list]
                street_actions = hand_summary.get('street_actions', {})
                board_by_street = hand_summary.get('board_by_street', {})
                player_results = hand_summary.get('player_results', {})
                for k, v in player_results.items():
                    if isinstance(v, list):
                        player_results[k] = tuple(v)
                player_hands = hand_summary.get('player_hands', {})
                made_hands_by_street = hand_summary.get('made_hands_by_street', {})

                pot_by_street = hand_summary.get('pot_by_street', {})
                self._cached_hand_summary = {
                    'street_stats': street_stats,
                    'street_actions': street_actions,
                    'board_by_street': board_by_street,
                    'player_results': player_results,
                    'player_hands': player_hands,
                    'made_hands_by_street': made_hands_by_street,
                    'pot_by_street': pot_by_street,
                }
                # Also fold the host-authoritative hand history into our
                # local view so the Hand Log button has data to format on
                # the client side. Hero cards are filled in via
                # _on_hole_cards_received earlier in the hand.
                self.hand_history.setdefault('street_actions', {}).update(
                    street_actions or {})
                self.hand_history.setdefault('board_by_street', {}).update(
                    board_by_street or {})
                self.hand_history.setdefault('pot_by_street', {}).update(
                    pot_by_street or {})
            except Exception as e:
                print(f"Error caching hand summary on client: {e}")

    def enable_action_buttons(self, to_call: float, min_raise: float, max_raise: float):
        """Enable appropriate action buttons for network play.

        Same four-button rule as local play: Fold, Check, Call, Raise.
        Exactly one of {Fold, Check} is enabled at a time.
        """
        player = self.players[self.my_seat] if self.my_seat is not None else None
        if not player:
            return

        # Don't replace fold/check/call/raise with Next Card unless the
        # client's seat literally has no chips. Same rule as the host
        # (enable_human_actions). The previous "len(active_with_chips)
        # <= 1" shortcut hijacked the action row from the last player
        # WITH chips and — worse — let them click Next Card on the
        # client, which then tried to fire end_betting_round locally
        # (a host-engine method) and crashed.
        if player.stack <= 0:
            self._show_next_card_button(True)
            return
        self._show_next_card_button(False)

        can_check = to_call == 0
        can_call = to_call > 0 and player.stack > 0
        can_raise = player.stack > to_call

        # Fold ↔ Check mutual exclusion.
        self.fold_btn.setEnabled(not can_check)
        self.check_btn.setEnabled(can_check)
        self.call_btn.setEnabled(can_call)
        self.raise_btn.setEnabled(can_raise)

        if can_call:
            if player.stack < to_call:
                # Calling for less than the bet — we'll be all-in.
                self.call_btn.setText(f"Call ${player.stack:.0f} (all-in)")
            else:
                self.call_btn.setText(f"Call ${to_call:.0f}")
        else:
            self.call_btn.setText("Call")

        # Mirror onto ToM-tab variants.
        self.tom_fold_btn.setEnabled(not can_check)
        self.tom_check_btn.setEnabled(can_check)
        self.tom_call_btn.setEnabled(can_call)
        self.tom_raise_btn.setEnabled(can_raise)
        self.tom_call_btn.setText(self.call_btn.text())

        # Bet vs Raise: same rule as the host's enable_human_actions.
        # current_bet == 0 means nobody has wagered on this street
        # (post-flop only — pre-flop the BB is always on the table
        # so current_bet > 0 from the deal), so the canonical word
        # for a fresh wager is "Bet". Without this the client view
        # still said "Raise" after the flop with no prior bets.
        bet_label = "Bet" if int(self.current_bet) == 0 else "Raise"
        self.raise_btn.setText(bet_label)
        self.tom_raise_btn.setText(bet_label)

    def send_network_action(self, action: str, amount: float = 0):
        """Send an action to the server (client mode)."""
        if self.network_client and self.network_mode == "client":
            self.network_client.send_action(action, amount)
            self.waiting_for_human = False
            self.disable_human_actions()


# ----------------------------------------------------------------------------
#                            PokerIQ Learning Hub
#
# A single consolidated module that layers a learning / coaching environment on
# top of the existing play view.  Built on the suggestions extracted from five
# poker books (Sklansky, Hilger, Chen/Ankenman, Acevedo, Harroch).
#
# Public entry point: PokerLearningHub(window).attach()
# Adds a `Train` menu, a `Review` menu, EV badges, a Bayes panel, calibration,
# decision journal, mindset coach, variance/ROR dashboard, Sklansky-distance
# scoring, tilt detection, AKQ lab, jam-or-fold trainer, indifference
# visualiser, MTT bubble drill, hand-class P&L and the rest of the 22 features.
# ----------------------------------------------------------------------------

import math
import time
import statistics
import json
from collections import deque

# --- Persistence -------------------------------------------------------------

def _lifetime_settings():
    """QSettings group dedicated to the learning-hub's persistent state."""
    return QSettings("PokerIQ", "PokerIQ-Learning")


# --- Session statistics ------------------------------------------------------

class SessionStats:
    """Per-session running stats: bb/100, σ, decision-times, click-speed.

    Drives the variance / ROR dashboard, the edge-CI meter, the Kelly stake
    recommendation and the tilt-anatomy lab.  Persists across launches via
    QSettings so the user sees cumulative numbers.
    """

    def __init__(self):
        self.hand_results: list[float] = []   # per-hand $ net for the hero
        self.bb_amount: float = 2.0
        # Decision-time series (seconds), used by tilt detection.
        self.decision_times: deque = deque(maxlen=200)
        # Time the human's action buttons were most recently enabled.
        self._action_started_at: float | None = None
        # Lifetime hands across all launches (for edge CI sample size).
        self.lifetime_hands: int = 0
        # Lifetime cumulative profit in $.
        self.lifetime_profit: float = 0.0
        # Lifetime sum of squared per-hand results, used for σ.
        self.lifetime_sumsq: float = 0.0
        # Self-rated emotion 1..10 at session start (Hilger emotion check-in).
        self.emotion_at_start: int | None = None
        self.emotion_log: list[tuple[int, int]] = []  # (hand_idx, rating)
        self._load_lifetime()

    # -- persistence --
    def _load_lifetime(self):
        s = _lifetime_settings()
        self.lifetime_hands = int(s.value("hands", 0, type=int))
        self.lifetime_profit = float(s.value("profit", 0.0, type=float))
        self.lifetime_sumsq = float(s.value("sumsq", 0.0, type=float))

    def _save_lifetime(self):
        s = _lifetime_settings()
        s.setValue("hands", self.lifetime_hands)
        s.setValue("profit", self.lifetime_profit)
        s.setValue("sumsq", self.lifetime_sumsq)
        s.sync()

    # -- per-hand recording --
    def record_hand_result(self, profit_dollars: float):
        """Called at hand end with hero's net P&L for the hand."""
        self.hand_results.append(profit_dollars)
        self.lifetime_hands += 1
        self.lifetime_profit += profit_dollars
        self.lifetime_sumsq += profit_dollars * profit_dollars
        self._save_lifetime()

    def record_decision_time(self, seconds: float):
        self.decision_times.append(seconds)

    def action_started(self):
        self._action_started_at = time.monotonic()

    def action_finished(self):
        if self._action_started_at is not None:
            self.record_decision_time(
                time.monotonic() - self._action_started_at)
            self._action_started_at = None

    # -- derived metrics --
    @property
    def session_hands(self) -> int:
        return len(self.hand_results)

    @property
    def session_bb_per_100(self) -> float:
        if not self.hand_results or self.bb_amount <= 0:
            return 0.0
        bb_sum = sum(self.hand_results) / self.bb_amount
        return bb_sum / max(1, self.session_hands) * 100.0

    @property
    def session_std(self) -> float:
        if len(self.hand_results) < 2:
            return 0.0
        return statistics.stdev(self.hand_results)

    @property
    def lifetime_bb_per_100(self) -> float:
        if self.lifetime_hands == 0 or self.bb_amount <= 0:
            return 0.0
        return (self.lifetime_profit / self.bb_amount
                / max(1, self.lifetime_hands) * 100.0)

    @property
    def lifetime_std(self) -> float:
        n = self.lifetime_hands
        if n < 2:
            return 0.0
        mean = self.lifetime_profit / n
        var = max(0.0, self.lifetime_sumsq / n - mean * mean)
        return math.sqrt(var)

    def edge_confidence_interval(self) -> tuple[float, float]:
        """95% CI on bb/100 edge (per Chen Ch 23)."""
        n = self.lifetime_hands
        if n < 30:
            return (0.0, 0.0)
        sigma_per_hand = self.lifetime_std / max(1.0, self.bb_amount)
        se = sigma_per_hand / math.sqrt(n)  # per-hand SE in bb
        edge = self.lifetime_bb_per_100 / 100.0  # bb per hand
        return ((edge - 1.96 * se) * 100.0, (edge + 1.96 * se) * 100.0)

    def risk_of_ruin(self, bankroll_dollars: float) -> float:
        """Chen Ch 22: ROR ≈ exp(-2 * win * B / σ²).

        Returns probability in [0,1].  When stats are too thin to compute
        we return 1.0 (no edge proven yet → assume worst case).
        """
        if self.lifetime_hands < 100:
            return 1.0
        mean = self.lifetime_profit / self.lifetime_hands
        if mean <= 0:
            return 1.0
        var = self.lifetime_std ** 2
        if var <= 0:
            return 1.0
        return math.exp(-2.0 * mean * bankroll_dollars / var)

    def kelly_fraction(self) -> float:
        """f* = µ / σ²  (Chen Ch 24, continuous Kelly)."""
        if self.lifetime_hands < 100 or self.lifetime_std <= 0:
            return 0.0
        mean = self.lifetime_profit / self.lifetime_hands
        return max(0.0, mean / (self.lifetime_std ** 2))


# --- Decision journal --------------------------------------------------------

class DecisionJournal:
    """One JSON-lines file of every meaningful Hero decision.

    Each entry: timestamp, hand-#, street, action, predicted equity (Brier
    scoring input), rationale (free text), result (set at hand end).
    """

    def __init__(self, path: str | None = None):
        if path is None:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "decision_journal.jsonl")
        self.path = path
        self.pending: list[dict] = []   # per-session entries needing result

    def record(self, **fields):
        entry = {"ts": datetime.now().isoformat(), **fields}
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass
        self.pending.append(entry)
        return entry

    def attach_result(self, hand_number: int, result_dollars: float):
        # Update any pending entries for this hand with the final result.
        for e in self.pending:
            if e.get("hand_number") == hand_number and "result" not in e:
                e["result"] = result_dollars

    def session_predictions(self) -> list[tuple[float, float]]:
        """Return (predicted_equity, actual_outcome 0/1) for Brier scoring."""
        out: list[tuple[float, float]] = []
        for e in self.pending:
            p = e.get("predicted_equity")
            r = e.get("result")
            if p is None or r is None:
                continue
            out.append((float(p), 1.0 if r > 0 else 0.0))
        return out


# --- Opponent model ----------------------------------------------------------

class OpponentModel:
    """Tracks per-villain VPIP, PFR, fold-to-3bet, aggression freq, etc.

    Drives the Levels-of-Thinking badge, the MES tag, and the Bayes panel's
    prior.  Persisted across sessions per-bot-name in QSettings.
    """

    def __init__(self):
        self.stats: dict[str, dict] = {}
        self._load()

    def _load(self):
        raw = _lifetime_settings().value("opponent_stats", "")
        if isinstance(raw, str) and raw:
            try:
                self.stats = json.loads(raw)
            except (ValueError, TypeError):
                self.stats = {}

    def _save(self):
        try:
            _lifetime_settings().setValue(
                "opponent_stats", json.dumps(self.stats))
        except (ValueError, TypeError):
            pass

    def _slot(self, name: str) -> dict:
        if name not in self.stats:
            self.stats[name] = {
                "hands": 0, "vpip": 0, "pfr": 0,
                "fold_to_3bet": 0, "faced_3bet": 0,
                "raises": 0, "calls": 0, "checks": 0, "folds": 0,
                "river_calls": 0, "river_faced_bet": 0,
            }
        return self.stats[name]

    def record_action(self, name: str, action: str, street: str,
                      faced_3bet: bool = False, faced_river_bet: bool = False):
        s = self._slot(name)
        a = action.lower()
        if a.startswith("rais") or a.startswith("bet"):
            s["raises"] += 1
            if street == "Preflop":
                s["pfr"] += 1
                s["vpip"] += 1
        elif a.startswith("call"):
            s["calls"] += 1
            if street == "Preflop":
                s["vpip"] += 1
            if street == "River" and faced_river_bet:
                s["river_calls"] += 1
        elif a.startswith("check"):
            s["checks"] += 1
        elif a.startswith("fold"):
            s["folds"] += 1
            if faced_3bet:
                s["fold_to_3bet"] += 1
        if faced_3bet:
            s["faced_3bet"] += 1
        if street == "River" and faced_river_bet:
            s["river_faced_bet"] += 1
        self._save()

    def record_hand(self, name: str):
        self._slot(name)["hands"] += 1
        self._save()

    def level_of(self, name: str) -> int:
        """Hilger Ch 8 levels-of-thinking 0..3 — coarse heuristic.

        L0: never raises / never bluffs (calling station / nit)
        L1: balanced opens, doesn't 3-bet light
        L2: 3-bets, c-bets — thinks about Hero's range
        L3: 4-bet light, exploitative line changes — meta-game
        """
        s = self.stats.get(name)
        if not s or s["hands"] < 10:
            return 1
        agg = (s["raises"] /
               max(1, s["raises"] + s["calls"] + s["checks"] + s["folds"]))
        if agg < 0.05:
            return 0
        if agg < 0.20:
            return 1
        if agg < 0.35:
            return 2
        return 3

    def biggest_leak(self, name: str) -> str | None:
        """MES tag — pick the most exploitable habit, if any.

        Returns a one-line string or None if data is too thin.
        """
        s = self.stats.get(name)
        if not s or s["hands"] < 5:
            return None
        total = s["raises"] + s["calls"] + s["checks"] + s["folds"]
        if total == 0:
            return None
        fold_pct = s["folds"] / total
        if s["faced_3bet"] >= 3:
            f3b = s["fold_to_3bet"] / max(1, s["faced_3bet"])
            if f3b > 0.75:
                return f"folds to 3-bet {f3b:.0%} — widen 3-bet bluffs"
        if fold_pct > 0.6:
            return f"folds {fold_pct:.0%} — c-bet a lot, value-bet thinner"
        if s["river_faced_bet"] >= 3:
            rc = s["river_calls"] / max(1, s["river_faced_bet"])
            if rc > 0.65:
                return f"calls river {rc:.0%} — never bluff, value-bet wider"
            if rc < 0.20:
                return f"folds river {rc:.0%} — increase river bluffs"
        if s["raises"] / max(1, total) > 0.3:
            return "raises heavily — slow-play monsters, induce bluffs"
        return None


# --- Board texture (Acevedo Ch 11) ------------------------------------------

def classify_board(board_cards) -> dict:
    """Return dict with keys: dry/dynamic/paired/wet/dynamic flags + cbet hint."""
    if not board_cards or len(board_cards) < 3:
        return {"label": "preflop", "cbet": ""}
    cards = [str(c) for c in board_cards[:3]]
    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    rank_order = 'AKQJT98765432'

    # Paired?
    paired = len(set(ranks)) < 3

    # Flush draws?
    suit_counts = {s: suits.count(s) for s in set(suits)}
    flushy = max(suit_counts.values()) >= 2  # two-tone (FD)
    monotone = max(suit_counts.values()) == 3

    # Connected?
    rank_idxs = sorted(rank_order.index(r) for r in ranks)
    spread = rank_idxs[-1] - rank_idxs[0]
    connected = spread <= 4 and len(set(ranks)) == 3

    if paired:
        label = "paired"
    elif monotone:
        label = "wet (monotone)"
    elif flushy and connected:
        label = "wet & dynamic"
    elif flushy or connected:
        label = "dynamic"
    else:
        label = "dry"

    # C-bet sizing recommendation (Acevedo Ch 12)
    if label == "dry":
        cbet = "small (33% pot) — range bet, you have range advantage"
    elif label == "paired":
        cbet = "small (33% pot) — paired boards favour the pre-flop raiser"
    elif "dynamic" in label or "wet" in label:
        cbet = "big (66-75% pot) — polarised; charge draws"
    else:
        cbet = "mixed (~50% pot)"
    return {"label": label, "cbet": cbet,
            "paired": paired, "flushy": flushy, "connected": connected}


# --- Sklansky-distance score (Theory of Poker Ch 3) -------------------------

def sklansky_distance(actual_action: str, actual_amount: float,
                      perfect_action: str, perfect_amount: float,
                      pot: float) -> float:
    """0 = matches the perfect-info choice, 10 = opposite choice."""
    if not actual_action or not perfect_action:
        return 0.0
    aa = actual_action[0].lower()
    pa = perfect_action[0].lower()
    if aa == pa:
        if aa == 'r':
            denom = max(1.0, pot or perfect_amount or 1.0)
            return min(10.0, abs(actual_amount - perfect_amount) / denom * 5.0)
        return 0.0
    # Different categories.
    pairs = {('f', 'c'): 6.0, ('c', 'f'): 6.0,
             ('f', 'r'): 9.0, ('r', 'f'): 9.0,
             ('c', 'r'): 4.0, ('r', 'c'): 4.0}
    return pairs.get((aa, pa), 8.0)


# --- Push/Fold Nash chart (Chen Ch 12, Acevedo Ch 6) ------------------------

# Minimal SB push range expressed as inclusive top-percent of hands, by
# effective stack in big blinds. Values come from standard charts (e.g.
# SnapShove).  Mid-stage push/fold; the trainer references these.
_NASH_PUSH_PCT = {
    5: 0.45, 6: 0.40, 7: 0.35, 8: 0.30, 9: 0.27, 10: 0.25,
    12: 0.22, 15: 0.18, 18: 0.15, 20: 0.13, 25: 0.10,
}


def nash_push_pct(stack_bb: int) -> float:
    keys = sorted(_NASH_PUSH_PCT.keys())
    if stack_bb <= keys[0]:
        return _NASH_PUSH_PCT[keys[0]]
    if stack_bb >= keys[-1]:
        return _NASH_PUSH_PCT[keys[-1]]
    for k in keys:
        if k >= stack_bb:
            return _NASH_PUSH_PCT[k]
    return 0.10


def hand_strength_percentile(hole_cards) -> float:
    """Rough preflop strength percentile [0,1].  1.0 = AA, 0 = 72o."""
    if not hole_cards or len(hole_cards) < 2:
        return 0.0
    c1, c2 = str(hole_cards[0]), str(hole_cards[1])
    rank_vals = {'A': 12, 'K': 11, 'Q': 10, 'J': 9, 'T': 8,
                 '9': 7, '8': 6, '7': 5, '6': 4, '5': 3,
                 '4': 2, '3': 1, '2': 0}
    r1, r2 = rank_vals.get(c1[0], 0), rank_vals.get(c2[0], 0)
    suited = c1[1] == c2[1]
    pair = r1 == r2
    # Sklansky/Chubukov-ish ordering, normalised.
    if pair:
        score = 0.55 + (r1 / 12) * 0.45
    else:
        hi, lo = max(r1, r2), min(r1, r2)
        gap = (hi - lo - 1) if hi > lo else 0
        score = (hi / 12) * 0.55 + (lo / 12) * 0.25
        score -= gap * 0.03
        if suited:
            score += 0.08
    return max(0.0, min(1.0, score))


# --- EV calculator (Tier 1 #1) ----------------------------------------------

def hero_action_ev(player, game_state, bb_amount: float, action_code: str,
                   raise_amount: float = 0.0,
                   equity_override: float | None = None) -> float:
    """EV-of-action estimator in $ for the on-screen action buttons.

    Pass ``equity_override`` to use a specific equity number (the cached
    range-based equity from the Theory-of-Mind panel is the canonical
    source — random-opponent MC was noisy and gave verdicts that didn't
    match the rest of the screen).

    Formulas:
        EV(fold)  = 0
        EV(check) = 0
        EV(call $c)  = equity * (pot + c + implied) - c
        EV(raise $r) = fold_equity * pot
                       + (1 - fold_equity) * [discounted_equity *
                                              (pot + 2 * cost + implied_r)
                                              - cost]
        with `fold_equity` shrunk for multi-way pots (each player
        independently folds), and `discounted_equity` ≈ 0.7 × equity
        because when villain *calls* a raise they have a stronger
        sub-range than the prior.

        `implied` is a future-bets estimate based on remaining streets
        and effective stack — without it the EV under-prices calls with
        pocket pairs / suited connectors / flush draws and falsely
        flagged obvious-call spots (e.g. TT preflop facing a 3x open)
        as -EV.
    """
    pot = float(game_state.get('pot', 0))
    current_bet = float(game_state.get('current_bet', 0))
    to_call = max(0.0, current_bet - player.bet_in_round)
    if equity_override is not None:
        equity = float(equity_override)
    else:
        equity, _, _ = player.calculate_current_stats(game_state, False)
    # ---- Implied-pot estimate -----------------------------------------
    # Future bets you can expect to win when your equity converts. Mirrors
    # the "Implied" strip's assumption (50% of avg opponent stack), then
    # scaled by a per-street factor: more bets to come ⇒ bigger implied.
    # For raise EV we use a smaller factor — raising thins the field, so
    # the implied multiplier shrinks (Sklansky Ch 13).
    board = game_state.get('board', []) or []
    board_n = len(board)
    if board_n == 0:
        impl_call, impl_raise = 0.30, 0.15   # Preflop
    elif board_n == 3:
        impl_call, impl_raise = 0.40, 0.20   # Flop
    elif board_n == 4:
        impl_call, impl_raise = 0.25, 0.12   # Turn
    else:
        impl_call, impl_raise = 0.0, 0.0     # River — no more streets
    opp_stacks = [p.stack for p in game_state.get('players', [])
                  if p is not player and p.active and p.stack > 0]
    avg_opp_stack = (sum(opp_stacks) / len(opp_stacks)) if opp_stacks else 0.0
    eff_stack = min(player.stack, avg_opp_stack) if avg_opp_stack > 0 else 0.0
    implied_call_pot = eff_stack * impl_call
    implied_raise_pot = eff_stack * impl_raise
    if action_code == 'f':
        return 0.0
    if action_code == 'c':
        if to_call <= 0:
            return 0.0  # check
        return equity * (pot + to_call + implied_call_pot) - to_call
    if action_code == 'r':
        # Number of opponents still able to act / call.  Multi-way pots
        # have LESS fold equity per player (each only folds ~25%
        # baseline) but the chance ALL fold drops as 0.75^N.  We want a
        # single "anyone calls" probability.
        players_left = max(1, sum(
            1 for p in game_state.get('players', [])
            if p is not player and p.active and p.stack > 0))
        # Per-player fold chance vs a 3-bet — book numbers (Acevedo): MDF
        # for a 3x raise is ~67%, so per-player fold is ~33%.  Tighten
        # this when the pot is already 3-bet (current_bet > 2 × bb): the
        # caller's range is much narrower, fold chance plunges.
        per_player_fold = 0.25 if current_bet > 2 * bb_amount else 0.40
        all_fold = per_player_fold ** players_left
        # When called, equity drops vs a calling range.
        discounted_eq = equity * 0.70
        raise_above_call = max(raise_amount, to_call + bb_amount * 2)
        cost = to_call + raise_above_call
        called_pot = pot + cost + raise_above_call  # villain matches above-call
        return all_fold * pot + (1 - all_fold) * (
            discounted_eq * (called_pot + implied_raise_pot) - cost)
    return 0.0


# ---------------------------------------------------------------------------
#                  Training dialogs (Tier 3) — self-contained
# ---------------------------------------------------------------------------

class AKQGameDialog(QDialog):
    """Chen Ch 13 — the AKQ toy game.

    Three-card deck (A, K, Q).  Each player gets one card.  Pot starts at 2,
    the player can bet 1.  Solver result: the bettor should value-bet A
    always and bluff Q with frequency 1/3 → A bluff; K (bluff-catcher)
    calls with frequency 1/2.

    Dialog walks the user through the math, then plays 20 hands so the user
    can verify they end up with EV ≈ 0 vs optimal play.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AKQ Game — Chen Ch 13")
        self.setMinimumSize(900, 700)
        self._score_bettor = 0.0
        self._score_caller = 0.0
        self._hands_played = 0
        self._role = 'bettor'  # alternates
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("AKQ Game (Chen Ch 13)")
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        intro = QLabel(
            "Three-card deck: A, K, Q.  You and the bot each draw one.  "
            "Pot starts at 2.  Bettor may bet 1 or check; if checked, "
            "showdown — high card wins.  If bet, caller may call (showdown) "
            "or fold (bettor wins pot).\n\n"
            "<b>GTO solution (Chen):</b> Bettor value-bets A always, "
            "checks K always, bluffs Q with probability 1/3.  Caller calls "
            "with K with probability 1/2 (always folds Q, always calls A)."
        )
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #ddd; font-size: 18px; line-height: 140%;")
        layout.addWidget(intro)

        self.state_lbl = QLabel("Press 'Deal' to start.")
        self.state_lbl.setFont(QFont('Courier', 16, QFont.Weight.Bold))
        self.state_lbl.setStyleSheet("color: #ffd966; padding: 10px; "
                                     "background: #1a1a1a; border-radius: 5px;")
        layout.addWidget(self.state_lbl)

        btn_row = QHBoxLayout()
        self.deal_btn = QPushButton("Deal")
        self.deal_btn.clicked.connect(self._deal)
        btn_row.addWidget(self.deal_btn)
        self.act_a = QPushButton("Bet / Bluff")
        self.act_a.clicked.connect(lambda: self._human_act('bet'))
        self.act_a.setEnabled(False)
        btn_row.addWidget(self.act_a)
        self.act_b = QPushButton("Check / Fold")
        self.act_b.clicked.connect(lambda: self._human_act('check'))
        self.act_b.setEnabled(False)
        btn_row.addWidget(self.act_b)
        self.act_c = QPushButton("Call")
        self.act_c.clicked.connect(lambda: self._human_act('call'))
        self.act_c.setEnabled(False)
        btn_row.addWidget(self.act_c)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.score_lbl = QLabel("Hands: 0  |  Your net: $0.00")
        self.score_lbl.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        layout.addWidget(self.score_lbl)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont('Courier', 15))
        layout.addWidget(self.log)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self._hero_card = None
        self._bot_card = None

    def _deal(self):
        deck = ['A', 'K', 'Q']
        random.shuffle(deck)
        self._hero_card = deck[0]
        self._bot_card = deck[1]
        self._role = 'bettor' if (self._hands_played % 2 == 0) else 'caller'
        if self._role == 'bettor':
            self.state_lbl.setText(
                f"You're the BETTOR.  Your card: {self._hero_card}.  "
                f"Bet (+1 to win pot+1) or Check (showdown)?")
            self.act_a.setText("Bet 1")
            self.act_b.setText("Check")
            self.act_a.setEnabled(True)
            self.act_b.setEnabled(True)
            self.act_c.setEnabled(False)
        else:
            bot_action = self._bot_optimal_bettor_action()
            self.state_lbl.setText(
                f"You're the CALLER.  Your card: {self._hero_card}.  "
                f"Bot's action: {bot_action.upper()}."
            )
            if bot_action == 'bet':
                self.act_a.setText("Call (showdown for 2)")
                self.act_b.setText("Fold")
                self.act_a.setEnabled(True)
                self.act_b.setEnabled(True)
                self.act_c.setEnabled(False)
            else:
                # Bot checked — auto-showdown
                self._resolve_caller_showdown(bot_action)
                return
        self.deal_btn.setEnabled(False)

    def _bot_optimal_bettor_action(self) -> str:
        if self._bot_card == 'A':
            return 'bet'
        if self._bot_card == 'Q':
            return 'bet' if random.random() < 1/3 else 'check'
        return 'check'  # K

    def _bot_optimal_caller_action(self) -> str:
        if self._bot_card == 'A':
            return 'call'
        if self._bot_card == 'K':
            return 'call' if random.random() < 0.5 else 'fold'
        return 'fold'

    def _human_act(self, what):
        if self._role == 'bettor':
            if what == 'bet':
                # Bot responds as caller
                bot = self._bot_optimal_caller_action()
                self._resolve_bettor_bet(bot)
            else:  # check
                self._resolve_bettor_check()
        else:  # caller
            if what == 'bet':  # i.e. call
                self._resolve_caller_call()
            else:
                # fold
                self._resolve_caller_fold()
        self._hands_played += 1
        self.score_lbl.setText(
            f"Hands: {self._hands_played}  |  Your net: ${self._score_bettor + self._score_caller:+.2f}")
        self.act_a.setEnabled(False)
        self.act_b.setEnabled(False)
        self.act_c.setEnabled(False)
        self.deal_btn.setEnabled(True)

    def _resolve_bettor_bet(self, bot_action):
        if bot_action == 'fold':
            self._score_bettor += 1.0  # win pot
            self.log.append(f"You bet {self._hero_card}, bot ({self._bot_card}) folds. You win 1.")
        else:  # call
            if 'AKQ'.index(self._hero_card) < 'AKQ'.index(self._bot_card):
                self._score_bettor += 2.0  # win pot+bet
                self.log.append(f"You bet {self._hero_card}, bot calls with {self._bot_card}. You win 2.")
            else:
                self._score_bettor -= 1.0  # lose bet
                self.log.append(f"You bet {self._hero_card}, bot calls with {self._bot_card}. You lose 1.")

    def _resolve_bettor_check(self):
        # Showdown
        if 'AKQ'.index(self._hero_card) < 'AKQ'.index(self._bot_card):
            self._score_bettor += 1.0  # win 1 of pot
            self.log.append(f"Check showdown: you {self._hero_card} vs bot {self._bot_card}. You win 1.")
        else:
            self._score_bettor -= 1.0
            self.log.append(f"Check showdown: you {self._hero_card} vs bot {self._bot_card}. You lose 1.")

    def _resolve_caller_call(self):
        if 'AKQ'.index(self._hero_card) < 'AKQ'.index(self._bot_card):
            self._score_caller += 2.0
            self.log.append(f"You call with {self._hero_card}, bot had {self._bot_card}. You win 2.")
        else:
            self._score_caller -= 1.0
            self.log.append(f"You call with {self._hero_card}, bot had {self._bot_card}. You lose 1.")

    def _resolve_caller_fold(self):
        self._score_caller -= 1.0  # lose the 1 of pot you'd have won at SD
        self.log.append(f"You fold to bot's bet with {self._hero_card}. You lose 1 (forfeit).")

    def _resolve_caller_showdown(self, bot_action):
        # Bot checked, free showdown
        if 'AKQ'.index(self._hero_card) < 'AKQ'.index(self._bot_card):
            self._score_caller += 1.0
            self.log.append(f"Bot checked. Showdown: you {self._hero_card} beats {self._bot_card}. You win 1.")
        else:
            self._score_caller -= 1.0
            self.log.append(f"Bot checked. Showdown: you {self._hero_card} loses to {self._bot_card}. You lose 1.")
        self._hands_played += 1
        self.score_lbl.setText(
            f"Hands: {self._hands_played}  |  Your net: ${self._score_bettor + self._score_caller:+.2f}")
        self.deal_btn.setEnabled(True)


class JamOrFoldTrainer(QDialog):
    """Tier 3 #13 — push/fold quiz.  Random stack + hand; user picks PUSH or
    FOLD; we compare to a Nash chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Heads-Up Jam-or-Fold Trainer")
        self.setMinimumSize(700, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Push-or-Fold (Nash Equilibrium)")
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        sub = QLabel(
            "You are in the small blind, heads-up, with this effective "
            "stack.  Push or fold?")
        sub.setStyleSheet("color: #ccc; font-size: 14px;")
        layout.addWidget(sub)

        self.scenario_lbl = QLabel("")
        self.scenario_lbl.setFont(QFont('Courier', 18, QFont.Weight.Bold))
        self.scenario_lbl.setStyleSheet(
            "color: #ffd966; padding: 12px; background: #1a1a1a; "
            "border-radius: 6px;")
        layout.addWidget(self.scenario_lbl)

        row = QHBoxLayout()
        self.push_btn = QPushButton("PUSH ALL-IN")
        self.push_btn.setStyleSheet(
            "QPushButton { background: #633; color: white; font-size: 18px; "
            "font-weight: bold; padding: 12px 24px; }")
        self.push_btn.clicked.connect(lambda: self._answer('push'))
        row.addWidget(self.push_btn)
        self.fold_btn = QPushButton("FOLD")
        self.fold_btn.setStyleSheet(
            "QPushButton { background: #555; color: white; font-size: 18px; "
            "font-weight: bold; padding: 12px 24px; }")
        self.fold_btn.clicked.connect(lambda: self._answer('fold'))
        row.addWidget(self.fold_btn)
        layout.addLayout(row)

        self.score_lbl = QLabel("Score: 0 / 0")
        self.score_lbl.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        layout.addWidget(self.score_lbl)

        # Scrolling history of feedback lines — each round's verdict
        # is appended (newest at the bottom) so the user can review
        # the streak instead of watching it flash for 1.5s and vanish.
        self.feedback = QTextEdit()
        self.feedback.setReadOnly(True)
        self.feedback.setFont(QFont('Arial', 14))
        self.feedback.setStyleSheet(
            "QTextEdit { background: #1a1a1a; color: #ddd;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 8px; }")
        layout.addWidget(self.feedback, stretch=1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self._correct = 0
        self._total = 0
        self._current = None
        self._next()

    def _next(self):
        stack_bb = random.choice([5, 7, 10, 12, 15, 20])
        deck = eval7.Deck()
        deck.shuffle()
        hole = [deck.deal(1)[0] for _ in range(2)]
        pct = hand_strength_percentile(hole)
        push_band = nash_push_pct(stack_bb)
        truth = 'push' if pct >= (1 - push_band) else 'fold'
        self._current = {'stack': stack_bb, 'hole': hole,
                         'pct': pct, 'push_band': push_band, 'truth': truth}
        names = [str(c) for c in hole]
        self.scenario_lbl.setText(
            f"Stack: {stack_bb} bb     Hand: {names[0]} {names[1]}")

    def _answer(self, choice):
        c = self._current
        if c is None:
            return
        self._total += 1
        names = [str(card) for card in c['hole']]
        hand_str = f"{names[0]} {names[1]}"
        prefix = (
            f"<b>#{self._total}</b> "
            f"[{c['stack']}bb {hand_str}, you {choice.upper()}]"
        )
        if choice == c['truth']:
            self._correct += 1
            msg = (f"{prefix}  <span style='color:#8f8'>Correct.</span>  "
                   f"Nash push range at {c['stack']}bb is the top "
                   f"{c['push_band']:.0%} of hands.  Hand strength: "
                   f"{c['pct']:.2f}.")
        else:
            msg = (f"{prefix}  <span style='color:#f77'>Off.</span>  "
                   f"Nash says {c['truth'].upper()} at {c['stack']}bb "
                   f"(top {c['push_band']:.0%}).  Hand strength: "
                   f"{c['pct']:.2f}.")
        self.feedback.append(msg)
        # Auto-scroll to the newest line.
        sb = self.feedback.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.score_lbl.setText(f"Score: {self._correct} / {self._total}")
        QTimer.singleShot(1500, self._next)


class IndifferenceVisualizer(QDialog):
    """Tier 3 #14 — Chen Ch 17.  Slider for villain's bluff frequency;
    live show villain's EV of calling vs folding a bluff-catcher.  The
    indifference point is bluff% = Pot / (Pot + Bet)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Indifference / Bluff-Frequency Visualiser")
        self.setMinimumSize(820, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Bluff-Catcher's EV vs Bluff Frequency")
        title.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        desc = QLabel(
            "Pot = $100.  Villain bets $X (slider).  Hero has a "
            "bluff-catcher.  Adjust villain's bluff% (slider) — find the "
            "bluff frequency that makes EV(call) = EV(fold).  Per Chen, "
            "this equals Pot / (Pot + Bet).")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #ddd; font-size: 17px; line-height: 140%;")
        layout.addWidget(desc)

        slider_label_css = "color: #ddd; font-size: 16px;"
        slider_value_css = ("color: #ffd966; font-size: 16px;"
                            " font-weight: bold;")

        # Bet size slider
        r1 = QHBoxLayout()
        bet_caption = QLabel("Bet size $")
        bet_caption.setStyleSheet(slider_label_css)
        r1.addWidget(bet_caption)
        self.bet_slider = QSlider(Qt.Orientation.Horizontal)
        self.bet_slider.setRange(10, 300)
        self.bet_slider.setValue(75)
        self.bet_slider.valueChanged.connect(self._refresh)
        r1.addWidget(self.bet_slider)
        self.bet_lbl = QLabel("$75")
        self.bet_lbl.setStyleSheet(slider_value_css)
        self.bet_lbl.setFixedWidth(80)
        r1.addWidget(self.bet_lbl)
        layout.addLayout(r1)

        r2 = QHBoxLayout()
        bluff_caption = QLabel("Villain bluff% ")
        bluff_caption.setStyleSheet(slider_label_css)
        r2.addWidget(bluff_caption)
        self.bluff_slider = QSlider(Qt.Orientation.Horizontal)
        self.bluff_slider.setRange(0, 100)
        self.bluff_slider.setValue(33)
        self.bluff_slider.valueChanged.connect(self._refresh)
        r2.addWidget(self.bluff_slider)
        self.bluff_lbl = QLabel("33%")
        self.bluff_lbl.setStyleSheet(slider_value_css)
        self.bluff_lbl.setFixedWidth(80)
        r2.addWidget(self.bluff_lbl)
        layout.addLayout(r2)

        self.result = QLabel("")
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.setFont(QFont('Courier', 18))
        self.result.setStyleSheet("color: #ffd966; padding: 20px; "
                                  "background: #1a1a1a; border-radius: 8px;"
                                  " line-height: 150%;")
        self.result.setWordWrap(True)
        self.result.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.result, stretch=1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self._refresh()

    def _refresh(self):
        pot = 100.0
        bet = float(self.bet_slider.value())
        bluff = self.bluff_slider.value() / 100.0
        self.bet_lbl.setText(f"${int(bet)}")
        self.bluff_lbl.setText(f"{int(bluff*100)}%")
        ev_call = bluff * (pot + bet) + (1 - bluff) * (-bet)
        ev_fold = 0.0
        indiff = pot / (pot + bet)
        verdict = ("Hero is indifferent — pure Nash."
                   if abs(bluff - indiff) < 0.02 else
                   ("Hero PROFITS by calling (villain over-bluffs)."
                    if bluff > indiff else
                    "Hero LOSES by calling (villain under-bluffs)."))
        self.result.setText(
            f"Pot $100, bet ${bet:.0f}<br><br>"
            f"EV(call) = bluff% * (pot + bet) - (1-bluff%) * bet<br>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"= {bluff:.2f} * {pot+bet:.0f} + {1-bluff:.2f} * "
            f"({-bet:.0f})<br>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"= <b>${ev_call:+.2f}</b><br><br>"
            f"EV(fold) = <b>$0.00</b><br><br>"
            f"Nash indifference bluff% = pot / (pot + bet) = "
            f"{indiff*100:.1f}%<br><br>"
            f"<b>{verdict}</b>"
        )


class TiltDetector:
    """Tier 3 #16 — Hilger Ch 6 tilt anatomy.

    Watches per-decision time + folding patterns over a rolling window; flags
    deviations >2σ from baseline as candidate tilt.  Returns a 0..100 score.
    """

    def __init__(self, stats: 'SessionStats'):
        self.stats = stats

    def score(self) -> tuple[int, str]:
        dt = list(self.stats.decision_times)
        if len(dt) < 12:
            return 0, "Need 12+ decisions for a baseline."
        recent = dt[-6:]
        baseline = dt[:-6]
        bavg = statistics.mean(baseline)
        bstd = statistics.pstdev(baseline) or 1e-3
        ravg = statistics.mean(recent)
        z = (ravg - bavg) / bstd
        # Faster than baseline = warning sign (snap calls/folds).
        if z < -1.5:
            return min(100, int(40 + abs(z) * 20)), (
                f"Decision time dropped {(1-ravg/bavg)*100:.0f}% in the "
                f"last 6 hands (z={z:.2f}σ).  Possible auto-pilot / "
                "steam tilt.")
        if z > 1.5:
            return min(100, int(30 + z * 15)), (
                f"Decision time JUMPED {(ravg/bavg-1)*100:.0f}% "
                f"(z={z:.2f}σ) — possible despair / overthink tilt.")
        return 0, "Baseline.  No tilt signal in last 6 hands."


class MTTBubbleDrill(QDialog):
    """Tier 3 #17 — short MTT scenario with ICM-aware payouts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MTT Bubble Drill (ICM)")
        self.setMinimumSize(800, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Bubble — ChipEV vs Real-$EV")
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        intro = QLabel(
            "Scenario: 4 players left, 3 cash, prize pool $1000 "
            "(payouts $500/$300/$200).  You're 3rd in chips, a big stack "
            "shoves on you.  Your call is +ChipEV but possibly -$EV "
            "because of ICM.  Choose your action."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #ddd; font-size: 18px; line-height: 140%;")
        layout.addWidget(intro)

        self.scenario_lbl = QLabel("")
        self.scenario_lbl.setFont(QFont('Courier', 16, QFont.Weight.Bold))
        # WordWrap so the parenthetical "(Pot odds say call if eq > 30%
        # in chips.)" doesn't get clipped off the right edge.
        self.scenario_lbl.setWordWrap(True)
        self.scenario_lbl.setStyleSheet(
            "color: #ffd966; padding: 14px; background: #1a1a1a; "
            "border-radius: 6px;")
        layout.addWidget(self.scenario_lbl)

        row = QHBoxLayout()
        self.call_btn = QPushButton("CALL")
        self.call_btn.clicked.connect(lambda: self._answer('call'))
        row.addWidget(self.call_btn)
        self.fold_btn = QPushButton("FOLD")
        self.fold_btn.clicked.connect(lambda: self._answer('fold'))
        row.addWidget(self.fold_btn)
        layout.addLayout(row)

        # Scrolling history — each round's verdict appends to the
        # canvas rather than flashing for 2.5s and getting overwritten
        # by the next prompt.
        self.feedback = QTextEdit()
        self.feedback.setReadOnly(True)
        self.feedback.setFont(QFont('Arial', 16))
        self.feedback.setStyleSheet(
            "QTextEdit { background: #1a1a1a; color: #ddd;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 10px; }")
        layout.addWidget(self.feedback, stretch=1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self._round = 0
        self._next()

    def _next(self):
        # Hero equity vs shover ranges from 35% (loose shove) → 55% (tight).
        eq = random.uniform(0.30, 0.55)
        self._eq = eq
        self.scenario_lbl.setText(
            f"Hero equity if called: {eq*100:.0f}%   "
            f"(Pot odds say call if eq > 30% in chips.)")

    def _answer(self, choice):
        eq = self._eq
        self._round += 1
        chip_ev = eq * 1.0 - (1 - eq) * 1.0       # ±1 stack
        # Crude ICM: losing on the bubble costs the next pay jump
        # ($200), winning gains the difference toward 1st.
        icm_ev = eq * 0.5 - (1 - eq) * 1.0
        correct = 'call' if icm_ev > 0 else 'fold'
        if choice == correct:
            verdict = "<span style='color:#8f8'>Correct (ICM-wise).</span>"
        else:
            verdict = ("<span style='color:#f77'>Off — the chip-EV "
                       "answer differs from the $-EV one.</span>")
        block = (
            f"<b>Round {self._round}</b> "
            f"[eq {eq*100:.0f}%, you {choice.upper()}] — {verdict}<br>"
            f"Chip-EV  (call) = {chip_ev:+.2f} stacks<br>"
            f"$-EV    (call) ≈ {icm_ev:+.2f} stack-equivalents "
            f"(ICM bubble premium subtracted)<br>"
            "On the bubble, losing chips costs the pay-jump from "
            "min-cash you almost have. The correct call threshold rises "
            "from chip-EV-neutral to noticeably above (~10-15 percentage "
            "points of equity).<br>"
            "————<br>"
        )
        self.feedback.append(block)
        sb = self.feedback.verticalScrollBar()
        sb.setValue(sb.maximum())
        QTimer.singleShot(2500, self._next)


# ---------------------------------------------------------------------------
#                     Dashboards (Tier 2 + Tier 4)
# ---------------------------------------------------------------------------

class VarianceDashboard(QDialog):
    """Tier 2 #7, #8, #9, #10, #11 — single composite stats window."""

    def __init__(self, stats: SessionStats, parent=None):
        super().__init__(parent)
        self.stats = stats
        self.setWindowTitle("Variance · Edge · Bankroll")
        self.setMinimumSize(900, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Statistics & Bankroll")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        # QTextBrowser instead of QLabel so the body scrolls when the
        # rendered stats exceed the dialog height (and so the user can
        # select/copy lines).
        self.body = QTextBrowser()
        self.body.setReadOnly(True)
        self.body.setOpenExternalLinks(False)
        self.body.setFont(QFont('Courier', 17))
        self.body.setStyleSheet(
            "QTextBrowser { color: #ddd; background: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 14px; }")
        layout.addWidget(self.body, stretch=1)

        # Bankroll separation entry.
        row = QHBoxLayout()
        bankroll_caption = QLabel("Lifetime bankroll $:")
        bankroll_caption.setStyleSheet("color: #ddd; font-size: 16px;")
        row.addWidget(bankroll_caption)
        self.bankroll_box = QSpinBox()
        self.bankroll_box.setStyleSheet("font-size: 16px; padding: 4px;")
        self.bankroll_box.setRange(0, 1_000_000)
        self.bankroll_box.setValue(int(
            _lifetime_settings().value("bankroll", 2000, type=int)))
        self.bankroll_box.valueChanged.connect(self._refresh)
        row.addWidget(self.bankroll_box)
        row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("font-size: 16px; padding: 6px 16px;")
        save_btn.clicked.connect(self._save_bankroll)
        row.addWidget(save_btn)
        layout.addLayout(row)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self._refresh()

    def _save_bankroll(self):
        _lifetime_settings().setValue("bankroll", int(self.bankroll_box.value()))
        _lifetime_settings().sync()
        self._refresh()

    def _refresh(self):
        s = self.stats
        b = float(self.bankroll_box.value())
        edge_lo, edge_hi = s.edge_confidence_interval()
        ror = s.risk_of_ruin(b)
        kelly = s.kelly_fraction()
        rec_buyin = max(20.0, kelly * b * 0.5)  # half-Kelly
        body = (
            "<b>Session</b><br>"
            f"  Hands:           {s.session_hands}<br>"
            f"  bb/100:          {s.session_bb_per_100:+.1f}<br>"
            f"  σ (per hand $):  {s.session_std:.2f}<br>"
            "<br>"
            "<b>Lifetime</b> (persists across launches)<br>"
            f"  Hands:           {s.lifetime_hands}<br>"
            f"  Net profit:      ${s.lifetime_profit:+,.0f}<br>"
            f"  bb/100:          {s.lifetime_bb_per_100:+.1f}<br>"
            f"  σ:               {s.lifetime_std:.2f}<br>"
            f"  Edge 95% CI:     [{edge_lo:+.1f}, {edge_hi:+.1f}] bb/100<br>"
            f"  Risk of Ruin:    <b>{ror*100:.1f}%</b> "
            f"(Chen Ch 22: exp(-2μB/σ²))<br>"
            f"  Kelly fraction:  {kelly:.3f}  →  half-Kelly buy-in "
            f"≈ <b>${rec_buyin:,.0f}</b><br>"
            "<br>"
            "<b>Bankroll separation (Hilger Ch 7)</b><br>"
            f"  Bankroll:        ${b:,.0f}<br>"
            f"  Floor at NL$1/$2 (20 buy-ins of $400): ${400*20:,.0f}<br>"
            f"  Withdrawals: profit only — keep the cushion.<br>"
        )
        self.body.setText(body)


class HandClassPnLTable(QDialog):
    """Tier 2 #10 — bb/100 per starting-hand class."""

    def __init__(self, hole_class_stats: dict, bb_amount: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hand-class P&L")
        self.setMinimumSize(700, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("bb/100 by starting hand")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont('Courier', 16))
        text.setStyleSheet(
            "QTextEdit { color: #ddd; background: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 12px; }")
        rows = []
        rows.append(f"{'Hand':<6} {'Seen':>6} {'Won':>5} {'Lost':>5} "
                    f"{'NetCash':>10} {'bb/100':>10}")
        rows.append("-" * 50)
        ranked = sorted(hole_class_stats.items(),
                        key=lambda kv: -kv[1].get('net_cash', 0))
        for cls, s in ranked[:50]:
            n = s.get('hands_played', 0)
            net = s.get('net_cash', 0)
            bb100 = (net / bb_amount / max(1, n)) * 100 if n else 0
            rows.append(
                f"{cls:<6} {s.get('hands_seen', 0):>6} "
                f"{s.get('hands_won', 0):>5} {s.get('hands_lost', 0):>5} "
                f"{net:>+10} {bb100:>+10.1f}")
        text.setPlainText("\n".join(rows))
        layout.addWidget(text)
        close = QPushButton("Close")
        close.setStyleSheet("font-size: 16px; padding: 8px;")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class MindsetCoach(QDialog):
    """Tier 4 #19, #22 — decision journal + emotion check-in.

    Lists the seven attitudes, current per-session score (from journal +
    emotion log) for each, and recent journal entries.  No external Claude
    needed — purely local scoring."""

    SEVEN = [
        "Realities of poker (accept variance)",
        "Play for the long term",
        "Process over outcomes",
        "Desensitize to money",
        "Leave ego at the door",
        "Remove emotion from decisions",
        "Continuous cycle of analysis",
    ]

    def __init__(self, journal: DecisionJournal, stats: SessionStats,
                 parent=None):
        super().__init__(parent)
        self.journal = journal
        self.stats = stats
        self.setWindowTitle("Mindset Coach (Hilger)")
        self.setMinimumSize(800, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("The Seven Attitudes — session snapshot")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        self.body = QLabel("")
        self.body.setFont(QFont('Arial', 17))
        self.body.setStyleSheet("color: #ddd; line-height: 150%;")
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setWordWrap(True)
        layout.addWidget(self.body)

        # Emotion 1-10 input
        row = QHBoxLayout()
        emo_caption = QLabel("Emotion (1=tilted, 10=calm):")
        emo_caption.setStyleSheet("color: #ddd; font-size: 17px;")
        row.addWidget(emo_caption)
        self.emo = QSpinBox()
        self.emo.setStyleSheet("font-size: 16px; padding: 4px;")
        self.emo.setRange(1, 10)
        self.emo.setValue(self.stats.emotion_at_start or 7)
        row.addWidget(self.emo)
        log_btn = QPushButton("Log now")
        log_btn.setStyleSheet("font-size: 16px; padding: 6px 14px;")
        log_btn.clicked.connect(self._log_emotion)
        row.addWidget(log_btn)
        row.addStretch()
        layout.addLayout(row)

        # Journal entry
        journal_caption = QLabel("Journal entry (this hand or session):")
        journal_caption.setStyleSheet("color: #ddd; font-size: 17px;")
        layout.addWidget(journal_caption)
        self.note = QTextEdit()
        self.note.setFont(QFont('Arial', 16))
        self.note.setStyleSheet(
            "QTextEdit { color: #ddd; background: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 8px; }")
        self.note.setMaximumHeight(150)
        layout.addWidget(self.note)
        save_btn = QPushButton("Save entry")
        save_btn.setStyleSheet("font-size: 16px; padding: 8px;")
        save_btn.clicked.connect(self._save_note)
        layout.addWidget(save_btn)

        layout.addStretch()
        close = QPushButton("Close")
        close.setStyleSheet("font-size: 16px; padding: 8px;")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self._refresh()

    def _log_emotion(self):
        self.stats.emotion_log.append(
            (self.stats.session_hands, int(self.emo.value())))
        if self.stats.emotion_at_start is None:
            self.stats.emotion_at_start = int(self.emo.value())
        self._refresh()

    def _save_note(self):
        txt = self.note.toPlainText().strip()
        if not txt:
            return
        self.journal.record(rationale=txt, hand_number=None)
        self.note.clear()
        self._refresh()

    def _refresh(self):
        n_entries = len(self.journal.pending)
        n_emo = len(self.stats.emotion_log)
        avg_emo = (
            sum(e for _, e in self.stats.emotion_log) / max(1, n_emo)
            if n_emo else 0)
        rows = ["<table cellpadding='6'>"]
        rows.append("<tr><th>Attitude</th><th>Status</th></tr>")
        statuses = [
            f"{self.stats.session_hands} hands seen — variance "
            "is real",
            f"Lifetime n = {self.stats.lifetime_hands}",
            f"{n_entries} journal note(s) this session",
            f"Buy-in fixed at start of hand",
            f"Emotion: {self.stats.emotion_at_start or '—'} → "
            f"avg {avg_emo:.1f}",
            f"Decision-time σ: "
            f"{statistics.pstdev(list(self.stats.decision_times)) if len(self.stats.decision_times) > 1 else 0:.2f}s",
            f"Decision-journal entries: {n_entries}",
        ]
        for label, status in zip(self.SEVEN, statuses):
            rows.append(f"<tr><td><b>{label}</b></td><td>{status}</td></tr>")
        rows.append("</table>")
        self.body.setText("".join(rows))


class CalibrationDialog(QDialog):
    """Tier 4 #20 — Brier-score predicted-equity inputs."""

    def __init__(self, journal: DecisionJournal, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Calibration — Brier score")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        body = QLabel("")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setFont(QFont('Courier', 17))
        body.setStyleSheet("color: #ddd; line-height: 150%; padding: 8px;")
        body.setWordWrap(True)
        layout.addWidget(body)

        preds = journal.session_predictions()
        if not preds:
            body.setText(
                "<i>No predictions logged this session.  Each Hero "
                "action prompts you for predicted equity in the EV "
                "badge.  Predictions are scored by Brier score "
                "(mean squared error), where 0 is perfect and 0.25 is "
                "chance.</i>")
        else:
            brier = sum((p - a) ** 2 for p, a in preds) / len(preds)
            calibration = 1 - 4 * brier  # 1=perfect, 0=chance
            body.setText(
                f"<b>Predictions:</b> {len(preds)}<br>"
                f"<b>Brier score:</b> {brier:.4f}<br>"
                f"<b>Calibration:</b> {calibration*100:.1f}%  "
                "(higher is better; 0% = chance)<br><br>"
                "<i>Closer to 0 = predictions match outcomes.  "
                "Same scoring rule used in weather forecasting and "
                "superforecaster research.</i>"
            )

        layout.addStretch()
        close = QPushButton("Close")
        close.setStyleSheet("font-size: 16px; padding: 8px;")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class RangeNarrowingDialog(QDialog):
    """Tier 3 #15 — replay each villain action, show 13×13 prior/posterior."""

    def __init__(self, action_history: list, parent=None):
        super().__init__(parent)
        self.action_history = action_history or []
        self.setWindowTitle("Range Narrowing (Bayes)")
        self.setMinimumSize(900, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Bayes walkthrough — refine villain's range")
        title.setFont(QFont('Arial', 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0af;")
        layout.addWidget(title)

        intro = QLabel(
            "Below is each meaningful action this hand.  After each, the "
            "prior range narrows by removing hands inconsistent with the "
            "action (Bayes: P(hand|action) ∝ P(action|hand) · P(hand))."
        )
        intro.setStyleSheet("color: #ccc; font-size: 17px; line-height: 140%;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont('Courier', 16))
        text.setStyleSheet(
            "QTextEdit { color: #ddd; background: #1a1a1a;"
            " border: 1px solid #333; border-radius: 6px;"
            " padding: 12px; }")
        lines = []
        # Start with a "full" range size of 100% and trim crudely.
        range_pct = 100.0
        for act in self.action_history[:30]:
            a = str(act).lower()
            if 'fold' in a:
                continue
            if 'raise' in a or 'bet' in a:
                range_pct *= 0.25  # raise / bet trims hard
                lines.append(
                    f"  {act}  →  range ↓ to ~{range_pct:.1f}% of starting "
                    "hands (raise narrows)")
            elif 'call' in a:
                range_pct *= 0.55
                lines.append(
                    f"  {act}  →  range ↓ to ~{range_pct:.1f}% (call narrows)")
            elif 'check' in a:
                range_pct *= 0.95
                lines.append(f"  {act}  →  range ↓ to ~{range_pct:.1f}% "
                             "(check barely narrows)")
        if not lines:
            lines.append("(no actions in this hand to narrow)")
        text.setPlainText("\n".join(lines))
        layout.addWidget(text, stretch=1)

        close = QPushButton("Close")
        close.setStyleSheet("font-size: 16px; padding: 8px;")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


# ---------------------------------------------------------------------------
#                          Tooltips (Tier 4 #18)
# ---------------------------------------------------------------------------

FINANCE_TOOLTIPS = {
    'SPR': "Stack-to-Pot Ratio — like capital-to-position-size in trading. "
           "Below 1 you're effectively all-in on the trade.",
    'MDF': "Minimum Defense Frequency — statistical Type-II error rate "
           "that makes the opponent's bluff unprofitable.",
    'Kelly': "Same formula hedge funds use to size bets given edge / "
             "variance: f* = μ/σ². Half-Kelly is the practical ceiling.",
    'Pot Odds': "Price you're laying / total pot. Compare to your equity "
                "to decide call or fold — decision theory under uncertainty.",
    'Equity': "Long-run win probability, same as expected return in finance. "
              "Computed via Monte Carlo sampling.",
    'Brier': "Mean-squared error of probabilistic forecasts. Used by "
             "weather forecasters and superforecasters.",
}


# ---------------------------------------------------------------------------
#                        Learning Hub controller
# ---------------------------------------------------------------------------

class PokerLearningHub:
    """Wires every learning-hub feature into an existing PokerWindow.

    Public: attach() — call once during PokerWindow.setup_ui() to add menus,
    instruments, dashboards and the training tab.
    """

    def __init__(self, window: 'PokerWindow'):
        self.window = window
        # Shared infra
        self.stats = SessionStats()
        _, bb = BLIND_LEVELS[getattr(window, 'blind_level', 0)]
        self.stats.bb_amount = float(bb)
        self.journal = DecisionJournal()
        self.opponents = OpponentModel()
        self.tilt = TiltDetector(self.stats)
        self._hero_start_stack: float | None = None

    def attach(self):
        w = self.window
        # ---- Menubar Train + Review menus ----
        mb = w.menuBar()
        train_menu = mb.addMenu("&Train")
        train_menu.addAction("AKQ Toy Game (Chen Ch 13)",
                             lambda: AKQGameDialog(w).exec())
        train_menu.addAction("Jam-or-Fold (Nash) Trainer",
                             lambda: JamOrFoldTrainer(w).exec())
        train_menu.addAction("Indifference / Bluff-Frequency Visualiser",
                             lambda: IndifferenceVisualizer(w).exec())
        train_menu.addAction("MTT Bubble Drill (ICM)",
                             lambda: MTTBubbleDrill(w).exec())

        review_menu = mb.addMenu("&Review")
        review_menu.addAction("Variance / Edge / Bankroll dashboard",
                              lambda: VarianceDashboard(self.stats, w).exec())
        review_menu.addAction("Hand-class P&L",
                              lambda: HandClassPnLTable(
                                  getattr(w, '_hole_card_stats', {}) or {},
                                  self.stats.bb_amount, w).exec())
        review_menu.addAction("Mindset Coach (Hilger)",
                              lambda: MindsetCoach(self.journal,
                                                   self.stats, w).exec())
        review_menu.addAction("Calibration (Brier score)",
                              lambda: CalibrationDialog(self.journal,
                                                         w).exec())
        review_menu.addAction("Range narrowing walk-through",
                              lambda: RangeNarrowingDialog(
                                  list(getattr(w, 'action_history', [])),
                                  w).exec())
        review_menu.addAction("Tilt Anatomy", self._show_tilt)

        # ---- Hook into PokerWindow lifecycle ----
        # EV badges + decision-time tracking on enable_human_actions
        orig_enable = w.enable_human_actions
        def patched_enable():
            orig_enable()
            self.stats.action_started()
            self._refresh_ev_badges()
        w.enable_human_actions = patched_enable

        orig_disable = w.disable_human_actions
        def patched_disable():
            orig_disable()
            self.stats.action_finished()
            self._clear_ev_badges()
        w.disable_human_actions = patched_disable

        # Hook into hand-end to bank P&L and feed journal.
        orig_end_hand = w.end_hand
        def patched_end_hand():
            start = getattr(w, 'starting_stacks', {}).get(w.players[0].name)
            result = orig_end_hand()
            try:
                end_stack = w.players[0].stack
                if start is not None:
                    profit = end_stack - start
                    self.stats.record_hand_result(profit)
                    self.journal.attach_result(w.hand_number, profit)
            except Exception:
                pass
            self._after_hand_review()
            return result
        w.end_hand = patched_end_hand

        # Hook into process_action so we record decisions + opponent stats.
        orig_process = w.process_action
        def patched_process(player, player_idx, action, amount):
            try:
                street = STREETS[w.street_idx] if w.street_idx < len(STREETS) else "?"
                faced_3bet = getattr(w, 'raises_this_round', 0) >= 2
                faced_river_bet = (street == "River" and w.current_bet > 0)
                self.opponents.record_action(
                    player.name, action, street,
                    faced_3bet=faced_3bet,
                    faced_river_bet=faced_river_bet)
            except Exception:
                pass
            return orig_process(player, player_idx, action, amount)
        w.process_action = patched_process

        # Add EV badges + finance tooltips to existing buttons.
        self._install_ev_badges()
        self._install_finance_tooltips()
        # Install board-texture badge (Tier 1 #3).
        self._install_board_texture_badge()
        # Decorate PlayerPanel with L0-L3 + MES tag after every panel refresh.
        orig_update = w.update_all_panels
        def patched_update():
            orig_update()
            self._refresh_opponent_badges()
            self._refresh_board_texture_badge()
        w.update_all_panels = patched_update

    # ----- helpers -----
    def _install_ev_badges(self):
        w = self.window
        # EV badges live on the Theory-of-Mind tab's action buttons,
        # not the main game screen — ToM is the analysis surface, so
        # the EV reading sits next to the equity / pot-odds / range
        # information the player is consulting at decision time.
        from PyQt6.QtCore import Qt as _Qt
        self.ev_labels: dict = {}
        buttons = [
            getattr(w, 'tom_fold_btn', None),
            getattr(w, 'tom_check_btn', None),
            getattr(w, 'tom_call_btn', None),
            getattr(w, 'tom_raise_btn', None),
        ]
        for btn in buttons:
            if btn is None:
                continue
            lbl = QLabel("")
            lbl.setFont(QFont('Arial', 12, QFont.Weight.Bold))
            lbl.setAlignment(_Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #88ff88; background: transparent;")
            lbl.setParent(btn)
            lbl.move(0, btn.height() - 18)
            lbl.resize(btn.width(), 18)
            self.ev_labels[id(btn)] = lbl

    def _refresh_ev_badges(self):
        w = self.window
        try:
            _, bb = BLIND_LEVELS[w.blind_level]
            hero = w.players[0]
            gs = {'board': [str(c) for c in w.board], 'pot': w.pot,
                  'current_bet': w.current_bet, 'players': w.players,
                  'bb_amount': bb}
            # Prefer the ToM panel's range-based equity (same number
            # shown in "Equity (vs Ranges): X%" above the tabs) so the
            # button badges and the rest of the screen agree.  Falls
            # back to per-Player random-opp MC if the ToM panel hasn't
            # computed one yet.
            eq_override = None
            tom = getattr(w, 'tom_panel', None)
            if tom is not None and hasattr(tom, 'last_hero_equity_vs_ranges'):
                eq_override = tom.last_hero_equity_vs_ranges
            mapping = [
                ('f', getattr(w, 'tom_fold_btn', None),  'f', 0),
                ('c', getattr(w, 'tom_check_btn', None), 'c', 0),
                ('c', getattr(w, 'tom_call_btn', None),  'c', 0),
                ('r', getattr(w, 'tom_raise_btn', None), 'r',
                 max(bb*2, w.pot * 0.6)),
            ]
            for _, btn, code, amt in mapping:
                if btn is None:
                    continue
                lbl = self.ev_labels.get(id(btn))
                if lbl is None:
                    continue
                if not btn.isEnabled():
                    lbl.setText("")
                    continue
                ev = hero_action_ev(hero, gs, bb, code, amt,
                                    equity_override=eq_override)
                color = "#88ff88" if ev > 0 else ("#ff7777" if ev < -0.5
                                                   else "#cccccc")
                lbl.setText(f"EV ${ev:+.1f}")
                lbl.setStyleSheet(
                    f"color: {color}; background: transparent;")
                lbl.move(0, btn.height() - 18)
                lbl.resize(btn.width(), 18)
        except Exception:
            pass

    def _clear_ev_badges(self):
        for lbl in self.ev_labels.values():
            try:
                lbl.setText("")
            except RuntimeError:
                pass

    def _install_finance_tooltips(self):
        # Attach to any widget whose name contains a tooltip-key word.
        w = self.window
        for attr_name in dir(w):
            try:
                obj = getattr(w, attr_name)
            except Exception:
                continue
            if not hasattr(obj, 'toolTip') or not hasattr(obj, 'setToolTip'):
                continue
            n = attr_name.lower()
            for key, tip in FINANCE_TOOLTIPS.items():
                if key.lower().replace(' ', '_') in n.replace(' ', '_'):
                    try:
                        obj.setToolTip(tip)
                    except Exception:
                        pass
                    break

    def _install_board_texture_badge(self):
        # No-op: the Theory-of-Mind panel's `board_texture_label` is now
        # the single source for board-dynamic / c-bet info.  Keeping the
        # method as a stub so the rest of the hub wiring doesn't need to
        # special-case its absence.
        self.texture_lbl = None

    def _refresh_board_texture_badge(self):
        # See _install_board_texture_badge — owned by ToM panel now.
        return

    def _refresh_opponent_badges(self):
        w = self.window
        for idx, panel in getattr(w, 'player_panels', []):
            p = w.players[idx]
            if p.style == 'human':
                continue
            try:
                level = self.opponents.level_of(p.name)
                leak = self.opponents.biggest_leak(p.name) or ""
                # Stash on the panel as a tooltip + secondary line.
                badge = f"L{level}"
                if leak:
                    badge += f"  •  MES: {leak}"
                # Use the existing best_hand_label slot (empty for villains
                # in non-god-mode) to surface the badge without adding new
                # widgets.
                if hasattr(panel, 'set_best_hand') and not panel.show_cards:
                    panel.set_best_hand(badge)
                panel.setToolTip(
                    f"{p.name}\nThinking level: L{level}\n"
                    f"MES tag: {leak or '(insufficient data)'}")
            except Exception:
                pass

    def _after_hand_review(self):
        """Run after end_hand: tilt detection + Sklansky-distance summary."""
        score, msg = self.tilt.score()
        if score >= 50:
            try:
                self.window.update_status(f"⚠ TILT: {msg}")
            except Exception:
                pass

    def _show_tilt(self):
        score, msg = self.tilt.score()
        box = QMessageBox(self.window)
        # No icon — the big "i" badge ate the entire left third of
        # the dialog and made the text panel feel off-center.
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle("Tilt Anatomy (Hilger Ch 6)")
        box.setText(
            f"Tilt score: {score}/100\n\n{msg}\n\n"
            f"Decision-time series last 12: "
            f"{[f'{d:.1f}s' for d in list(self.stats.decision_times)[-12:]]}")
        # Default QMessageBox font is ~11pt — bump to 16pt to match
        # the rest of the dialog set.
        box.setStyleSheet(
            "QMessageBox { font-size: 16pt; }"
            "QMessageBox QLabel { font-size: 16pt; min-width: 520px;"
            " line-height: 140%; }"
            "QMessageBox QPushButton { font-size: 14pt;"
            " padding: 6px 18px; min-width: 90px; }"
        )
        box.exec()


# Auto-install hook — call from PokerWindow.__init__ once setup_ui finishes.
def _install_learning_hub(window):
    """Idempotent installer.  Safe to call multiple times."""
    if hasattr(window, "_learning_hub"):
        return
    try:
        window._learning_hub = PokerLearningHub(window)
        window._learning_hub.attach()
    except Exception as e:
        print(f"[learning hub] failed to attach: {e!r}", flush=True)


# --- Text Mode Utilities ---

def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system('cls' if os.name == 'nt' else 'clear')


def check_resolution():
    """Check if screen resolution is adequate for GUI mode.
    Returns the largest (width, height) across all screens, or (0, 0) if unable to detect.
    """
    best_w, best_h = 0, 0
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QGuiApplication

        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication(sys.argv)

        for screen in QGuiApplication.screens():
            geometry = screen.geometry()
            if geometry.width() > best_w:
                best_w = geometry.width()
                best_h = geometry.height()
        if best_w > 0:
            return best_w, best_h
    except Exception:
        pass

    # Fallback: try xrandr on Linux — pick the highest-resolution active mode
    try:
        import subprocess
        result = subprocess.run(['xrandr'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if '*' in line:
                parts = line.split()
                for part in parts:
                    if 'x' in part and part[0].isdigit():
                        w, h = part.split('x')
                        w = int(w)
                        h = int(h.split('+')[0].split('_')[0])
                        if w > best_w:
                            best_w, best_h = w, h
    except Exception:
        pass

    return best_w, best_h


def prompt_resolution_choice(width, height):
    """Prompt user when resolution is below 1920x1080.
    Returns: 'exit', 'proceed', or 'textmode'
    """
    print(f"\n{'='*60}")
    print("RESOLUTION WARNING")
    print(f"{'='*60}")
    print(f"Detected resolution: {width}x{height}")
    print(f"Recommended minimum: 1920x1080")
    print()
    print("The GUI may be difficult to read at this resolution.")
    print()
    print("Options:")
    print("  1. Exit and restart after changing screen resolution")
    print("  2. Proceed with lower resolution (may be illegible)")
    print("  3. Proceed in text mode")
    print()

    while True:
        try:
            choice = input("Enter choice (1/2/3): ").strip()
        except (EOFError, KeyboardInterrupt):
            return 'exit'
        if choice == '1':
            return 'exit'
        elif choice == '2':
            return 'proceed'
        elif choice == '3':
            return 'textmode'
        print("Invalid choice. Please enter 1, 2, or 3.")


# --- Text Mode Game Class ---

class TextModeGame:
    """Text-based poker game that reuses core game logic."""

    # Range estimates for Theory of Mind (simplified from GUI version)
    STYLE_RANGES = {
        'tight': {
            'preflop_open': "TT+, AQs+, AKo",
            'preflop_call': "77+, ATs+, KQs, AJo+",
            'postflop_bet': "Top pair+, strong draws",
        },
        'loose': {
            'preflop_open': "22+, Axs, Kxs, QTs+, JTs, T9s, 98s, A2o+, K9o+, QTo+",
            'preflop_call': "Any pair, any suited, any connector, any broadway",
            'postflop_bet': "Any pair, any draw, sometimes nothing",
        },
        'aggressive': {
            'preflop_open': "55+, A2s+, K9s+, QTs+, JTs, T9s, A9o+, KTo+, QJo",
            'preflop_call': "22+, suited connectors, broadways",
            'postflop_bet': "Wide - pairs, draws, air",
        },
        'optimal': {
            'preflop_open': "77+, A2s+, KTs+, QJs, ATo+, KQo",
            'preflop_call': "55+, suited connectors, suited aces",
            'postflop_bet': "Balanced - value and bluffs",
        },
        'tom': {
            'preflop_open': "Adapts to table",
            'preflop_call': "Adapts to opponent",
            'postflop_bet': "Exploitative",
        },
    }

    def __init__(self, god_mode=False, show_tells=False, theory_of_mind=False):
        self.god_mode = god_mode
        self.show_tells = show_tells
        self.theory_of_mind = theory_of_mind

        # Initialize players — mirror PokerWindow's randomised lineup.
        # Hero pinned to seat 0; bots shuffled across seats 1..5.
        self.players = (
            [Player("Hero (You)", "human")]
            + [Player(name, style)
               for name, style in _make_random_bot_lineup()]
        )

        # Game state
        self.deck = None
        self.board = []
        self.pot = 0
        self.dealer_idx = 0
        self.current_bet = 0
        self.street_idx = 0
        self.current_player_idx = 0
        self.raises_this_round = 0
        self.action_log = []
        self.hand_number = 0
        self.blind_level = 0
        self.hand_in_progress = False

    def run(self):
        """Main game loop."""
        self.show_welcome()

        while True:
            if not self.hand_in_progress:
                self.display_between_hands()
                cmd = self.get_command()

                if cmd == 'q':
                    print("\nThanks for playing PokerIQ!")
                    break
                elif cmd == 'n':
                    self.deal_hand()
                elif cmd == 'h':
                    self.show_help()
            else:
                # Shouldn't reach here normally
                self.hand_in_progress = False

    def show_welcome(self):
        """Display welcome screen."""
        clear_screen()
        print("=" * 70)
        print(f"{'POKERIQ - Text Mode':^70}")
        print("=" * 70)
        mode_str = []
        if self.god_mode:
            mode_str.append("God Mode")
        if self.show_tells:
            mode_str.append("Tells Visible")
        if self.theory_of_mind:
            mode_str.append("Theory of Mind")
        if mode_str:
            print(f"  Active modes: {', '.join(mode_str)}")
        else:
            print("  Standard mode")
        print()
        print("  A poker training application with AI opponents.")
        print()
        print("  Players:")
        for p in self.players:
            style_desc = {
                'human': 'You',
                'optimal': 'GTO-based play',
                'tight': 'Only plays premium hands',
                'loose': 'Plays many hands',
                'aggressive': 'Bets and raises frequently',
                'tom': 'Adapts to opponents'
            }
            print(f"    - {p.name}: {style_desc.get(p.style, p.style)}")
        print()
        print("=" * 70)
        input("\nPress Enter to start...")

    def show_help(self):
        """Display help screen."""
        clear_screen()
        print("=" * 70)
        print(f"{'POKERIQ HELP':^70}")
        print("=" * 70)
        print()
        print("COMMANDS:")
        print("  n, new     - Deal a new hand")
        print("  h, help    - Show this help screen")
        print("  q, quit    - Exit the game")
        print()
        print("DURING A HAND:")
        print("  f          - Fold")
        print("  c          - Call or Check")
        print("  r          - Raise (you'll be prompted for amount)")
        print("  r <amount> - Raise to specific amount")
        print()
        print("POKER BASICS:")
        print("  - Blinds increase after every 10 hands")
        print("  - Best 5-card hand wins at showdown")
        print("  - Hand rankings: High Card < Pair < Two Pair < Three of a Kind")
        print("    < Straight < Flush < Full House < Four of a Kind < Straight Flush")
        print()
        if self.god_mode:
            print("GOD MODE: You can see all opponent cards")
        if self.theory_of_mind:
            print("THEORY OF MIND: Shows estimated opponent hand ranges")
        print()
        print("=" * 70)
        input("\nPress Enter to continue...")

    def display_between_hands(self):
        """Display state between hands."""
        clear_screen()
        print("=" * 70)
        sb, bb = BLIND_LEVELS[self.blind_level]
        print(f"{'POKERIQ - Text Mode':^70}")
        print(f"Hand #{self.hand_number}  |  Blinds: ${sb}/${bb}")
        print("=" * 70)
        print()
        print("PLAYER STACKS:")
        print(f"  {'Name':<20} {'Stack':>10}")
        print("  " + "-" * 32)
        for p in self.players:
            marker = " (BUST)" if p.stack <= 0 else ""
            print(f"  {p.name:<20} ${p.stack:>9}{marker}")
        print()
        print("-" * 70)
        print("  Commands: (N)ew hand  (H)elp  (Q)uit")
        print("-" * 70)

    def get_command(self):
        """Get command from user."""
        while True:
            try:
                cmd = input("\n  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 'q'
            if cmd in ['n', 'new']:
                return 'n'
            elif cmd in ['h', 'help']:
                return 'h'
            elif cmd in ['q', 'quit', 'exit']:
                return 'q'
            print("  Unknown command. Type 'h' for help.")

    def display_state(self):
        """Render the complete game state to terminal."""
        clear_screen()
        self._display_header()
        self._display_board()
        self._display_players()
        if self.show_tells or self.god_mode:
            self._display_statistics()
        self._display_action_log()
        if self.theory_of_mind:
            self._display_theory_of_mind()
        self._display_strategy_advice()

    def _display_header(self):
        """Show hand number, street, blinds."""
        street = STREETS[self.street_idx] if self.street_idx < len(STREETS) else "Showdown"
        sb, bb = BLIND_LEVELS[self.blind_level]
        print("=" * 70)
        print(f"{'POKERIQ':^70}")
        print(f"Hand #{self.hand_number}  |  {street}  |  Blinds: ${sb}/${bb}")
        print("=" * 70)

    def _display_board(self):
        """Show community cards and pot."""
        board_str = self._format_board()
        print(f"  Board: {board_str}")
        print(f"  Pot: ${self.pot}")
        print("-" * 70)

    def _format_board(self):
        """Format board cards with placeholders for undealt."""
        cards = [f"[{c}]" for c in self.board]
        while len(cards) < 5:
            cards.append("[  ]")
        return " ".join(cards)

    def _get_position_str(self, player_idx):
        """Get position string for a player."""
        num_players = len([p for p in self.players if p.stack > 0 or p.active])
        if num_players < 2:
            return ""

        # Calculate positions relative to dealer
        positions = [''] * len(self.players)
        positions[self.dealer_idx] = 'BT'
        positions[(self.dealer_idx + 1) % len(self.players)] = 'SB'
        positions[(self.dealer_idx + 2) % len(self.players)] = 'BB'

        if num_players >= 4:
            positions[(self.dealer_idx + 3) % len(self.players)] = 'UTG'
        if num_players >= 5:
            positions[(self.dealer_idx - 1) % len(self.players)] = 'CO'

        return positions[player_idx]

    def _display_players(self):
        """Show all players in table format."""
        print("  PLAYERS:")
        print(f"  {'Pos':<4} {'Name':<18} {'Stack':>8} {'Bet':>6}  {'Cards':<12} Status")
        print("  " + "-" * 64)

        for i, p in enumerate(self.players):
            pos = self._get_position_str(i)

            # Cards: show for human, show in god mode, show at showdown if active
            if p.hand:
                if p.style == 'human' or self.god_mode or (self.street_idx >= 4 and p.active):
                    cards = f"[{p.hand[0]}] [{p.hand[1]}]"
                else:
                    cards = "[??] [??]"
            else:
                cards = "[--] [--]"

            # Status
            if not p.active:
                status = "Folded"
            elif i == self.current_player_idx and p.style == 'human':
                status = "<< YOUR TURN"
            elif p.stack <= 0 and p.bet_in_round > 0:
                status = "All-in"
            else:
                status = ""

            print(f"  {pos:<4} {p.name:<18} ${p.stack:>7} ${p.bet_in_round:>4}  {cards:<12} {status}")
        print("-" * 70)

    def _display_statistics(self):
        """Show hero's equity, pot odds, implied odds."""
        hero = self.players[0]
        if not hero.hand or not hero.active:
            return

        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'players': self.players,
            'current_bet': self.current_bet,
            'bb_amount': BLIND_LEVELS[self.blind_level][1]
        }

        equity, pot_odds, to_call = hero.calculate_current_stats(game_state, self.god_mode)

        # Implied odds calculation
        active_opps = [p for p in self.players if p.active and p != hero]
        if active_opps and to_call > 0:
            avg_stack = sum(p.stack for p in active_opps) / len(active_opps)
            implied = avg_stack / to_call
        else:
            implied = 0

        print("  STATISTICS:")
        print(f"  Your Equity: {equity:.1%}   |   Pot Odds: {pot_odds:.1%}   |   To Call: ${to_call}")
        if implied > 0:
            print(f"  Implied Odds: {implied:.1f}:1")

        # EV indicator
        if pot_odds > 0:
            if equity > pot_odds:
                print("  >>> POSITIVE EV - Equity beats pot odds <<<")
            else:
                print("  >>> NEGATIVE EV - Pot odds exceed equity <<<")
        print("-" * 70)

    def _display_action_log(self):
        """Show recent actions."""
        if self.action_log:
            print("  RECENT ACTIONS:")
            recent = self.action_log[-6:]
            for action in recent:
                print(f"    {action}")
            print("-" * 70)

    def _display_theory_of_mind(self):
        """Show opponent range estimates."""
        print("  THEORY OF MIND - Opponent Range Estimates:")
        for p in self.players:
            if p.style == 'human' or not p.active:
                continue

            ranges = self.STYLE_RANGES.get(p.style, {})
            if self.street_idx == 0:
                range_str = ranges.get('preflop_open', 'Unknown')
            else:
                range_str = ranges.get('postflop_bet', 'Unknown')

            print(f"    {p.name}: {range_str}")
        print("-" * 70)

    def _display_strategy_advice(self):
        """Generate and display strategy advice."""
        hero = self.players[0]
        if not hero.hand or not hero.active:
            return

        print("  ADVISOR SAYS:")

        hand_str = f"{hero.hand[0]}{hero.hand[1]}"
        board_str = ' '.join(str(c) for c in self.board) if self.board else "none"

        # Basic hand analysis
        c1, c2 = str(hero.hand[0]), str(hero.hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]

        is_pair = r1 == r2
        is_suited = s1 == s2
        ranks = 'AKQJT98765432'

        if self.street_idx == 0:
            # Preflop advice
            print(f"    Hand: [{c1}] [{c2}]")

            # Classify hand
            if is_pair:
                rank_val = ranks.index(r1)
                if rank_val <= 2:
                    print("    >> PREMIUM PAIR - Raise for value, 3-bet if raised")
                elif rank_val <= 5:
                    print("    >> MEDIUM PAIR - Raise or call, set mining if deep")
                else:
                    print("    >> SMALL PAIR - Set mine with good implied odds (15:1+)")
            elif r1 in 'AK' and r2 in 'AK':
                print("    >> BIG SLICK - Premium hand, raise or 3-bet")
            elif r1 == 'A' or r2 == 'A':
                if is_suited:
                    print("    >> SUITED ACE - Good for flush draws, can open wide")
                else:
                    print("    >> ACE HIGH - Kicker matters, be careful postflop")
            elif is_suited and abs(ranks.index(r1) - ranks.index(r2)) <= 2:
                print("    >> SUITED CONNECTOR - Play for straights/flushes")
            else:
                print("    >> MARGINAL - Play cautiously or fold to raises")
        else:
            # Postflop advice
            board_ranks = [str(c)[0] for c in self.board]

            # Check for made hands
            if is_pair:
                if all(ranks.index(r1) < ranks.index(br) for br in board_ranks):
                    print("    >> OVERPAIR - Strong, bet for value and protection")
                else:
                    print("    >> POCKET PAIR - Underpair, proceed with caution")
            elif r1 in board_ranks or r2 in board_ranks:
                hit_rank = r1 if r1 in board_ranks else r2
                top_board = min(board_ranks, key=lambda x: ranks.index(x))
                if hit_rank == top_board:
                    print("    >> TOP PAIR - Bet for value, watch for raises")
                else:
                    print("    >> MIDDLE/BOTTOM PAIR - Pot control, check-call")
            else:
                # Check for draws
                suits_on_board = [str(c)[1] for c in self.board]
                hero_suits = [s1, s2]
                flush_draw = any(suits_on_board.count(s) + hero_suits.count(s) >= 4
                                for s in hero_suits)

                if flush_draw:
                    print("    >> FLUSH DRAW - 9 outs, ~35% by river. Semi-bluff or call")
                else:
                    print("    >> MISSED - Check or fold unless you can bluff")

        # Position advice
        pos = self._get_position_str(0)
        if pos == 'BT':
            print("    Position: BUTTON - Best position, can play wider")
        elif pos in ['SB', 'BB']:
            print("    Position: BLINDS - Defend appropriately")
        elif pos == 'UTG':
            print("    Position: UTG - Tightest, only play premium hands")

        print("-" * 70)

    def get_action(self):
        """Prompt hero for action and return (action, amount)."""
        hero = self.players[0]
        to_call = max(0, self.current_bet - hero.bet_in_round)
        _, bb = BLIND_LEVELS[self.blind_level]
        min_raise = self.current_bet + bb
        max_raise = hero.stack + hero.bet_in_round

        # Build prompt
        if to_call == 0:
            call_str = "(C)heck"
        else:
            call_str = f"(C)all ${to_call}"

        if hero.stack > to_call:
            raise_str = f"(R)aise [${min_raise}-${max_raise}]"
        else:
            raise_str = ""

        print(f"\n  YOUR ACTION:  (F)old  {call_str}  {raise_str}")

        while True:
            try:
                cmd = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 'f', 0

            if cmd == 'f':
                return 'f', 0
            elif cmd == 'c':
                return 'c', 0
            elif cmd.startswith('r'):
                if hero.stack <= to_call:
                    print("  You don't have enough chips to raise. Call or fold.")
                    continue

                # Handle raise
                parts = cmd.split()
                if len(parts) > 1:
                    try:
                        amount = int(parts[1])
                        if min_raise <= amount <= max_raise:
                            return 'r', amount
                        print(f"  Raise must be between ${min_raise} and ${max_raise}")
                    except ValueError:
                        print("  Invalid amount. Use: r <amount>")
                else:
                    # Prompt for amount
                    try:
                        print(f"  Enter raise amount (${min_raise}-${max_raise}), or 'a' for all-in:")
                        amt_input = input("  Amount: ").strip().lower()
                        if amt_input == 'a':
                            return 'r', max_raise
                        amount = int(amt_input)
                        if min_raise <= amount <= max_raise:
                            return 'r', amount
                        print(f"  Must be between ${min_raise} and ${max_raise}")
                    except ValueError:
                        print("  Invalid amount")
            else:
                print("  Invalid action. Use F, C, or R")

    def deal_hand(self):
        """Start a new hand."""
        self.hand_number += 1
        self.hand_in_progress = True
        self.action_log = []

        # Check for blind increase
        if self.hand_number > 1 and (self.hand_number - 1) % 10 == 0:
            if self.blind_level < len(BLIND_LEVELS) - 1:
                self.blind_level += 1
                sb, bb = BLIND_LEVELS[self.blind_level]
                self.action_log.append(f"*** Blinds increased to ${sb}/${bb} ***")

        self.deck = eval7.Deck()
        self.deck.shuffle()
        self.board = []
        self.pot = 0
        self.current_bet = 0
        self.street_idx = 0
        self.raises_this_round = 0

        # Reset players
        for p in self.players:
            p.reset_for_hand()
            if p.stack <= 0:
                p.active = False

        # Check active player count
        active_count = sum(1 for p in self.players if p.active)
        if active_count < 2:
            print("\nNot enough players with chips to continue!")
            if input("Reset stacks and play again? (y/n): ").lower() == 'y':
                for p in self.players:
                    p.stack = STARTING_STACK
                    p.active = True
                self.hand_number = 0
                self.blind_level = 0
                self.deal_hand()
            else:
                self.hand_in_progress = False
            return

        # Move dealer
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        while not self.players[self.dealer_idx].active:
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players)

        # Deal hole cards
        for p in self.players:
            if p.active:
                p.hand = list(self.deck.deal(2))

        # Post blinds
        sb_idx = (self.dealer_idx + 1) % len(self.players)
        while not self.players[sb_idx].active:
            sb_idx = (sb_idx + 1) % len(self.players)

        bb_idx = (sb_idx + 1) % len(self.players)
        while not self.players[bb_idx].active:
            bb_idx = (bb_idx + 1) % len(self.players)

        sb_amount, bb_amount = BLIND_LEVELS[self.blind_level]
        self._post_blind(self.players[sb_idx], sb_amount, "small blind")
        self._post_blind(self.players[bb_idx], bb_amount, "big blind")
        self.current_bet = bb_amount

        # Start betting from UTG
        self.current_player_idx = (bb_idx + 1) % len(self.players)
        while not self.players[self.current_player_idx].active:
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

        self._run_betting_round()

    def _post_blind(self, player, amount, blind_type):
        """Post a blind bet."""
        actual = min(amount, player.stack)
        player.stack -= actual
        player.bet_in_round = actual
        player.total_invested = actual
        self.pot += actual
        self.action_log.append(f"{player.name} posts {blind_type} ${actual}")

    def _run_betting_round(self):
        """Run a complete betting round synchronously."""
        self.raises_this_round = 0
        for p in self.players:
            p.actions_this_round = 0

        start_idx = self.current_player_idx
        first_pass = True

        while True:
            # Check if hand is over
            active = [p for p in self.players if p.active]
            if len(active) < 2:
                self._end_hand()
                return

            player = self.players[self.current_player_idx]

            if player.active and player.stack > 0:
                to_call = self.current_bet - player.bet_in_round

                # Skip if player has acted and doesn't need to call more
                if player.actions_this_round > 0 and to_call == 0:
                    pass
                else:
                    # Get action
                    if player.style == 'human':
                        self.display_state()
                        action, amount = self.get_action()
                    else:
                        # Bot action
                        game_state = {
                            'board': [str(c) for c in self.board],
                            'pot': self.pot,
                            'current_bet': self.current_bet,
                            'players': self.players,
                            'bb_amount': BLIND_LEVELS[self.blind_level][1]
                        }
                        action, amount = player.get_bot_action(game_state, False)

                    self._process_action(player, action, amount)

            # Move to next player
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)

            # Check end of round
            active = [p for p in self.players if p.active]
            if len(active) < 2:
                self._end_hand()
                return

            active_with_chips = [p for p in active if p.stack > 0]
            all_matched = all(p.bet_in_round == self.current_bet or p.stack == 0
                             for p in active)
            all_acted = all(p.actions_this_round > 0 for p in active_with_chips)

            if all_matched and all_acted:
                break

            # Prevent infinite loop - if we've gone full circle twice
            if self.current_player_idx == start_idx:
                if not first_pass:
                    break
                first_pass = False

        # Move to next street
        self._next_street()

    def _process_action(self, player, action, amount):
        """Process a player's action."""
        to_call = max(0, self.current_bet - player.bet_in_round)

        if action == 'f':
            player.active = False
            self.action_log.append(f"{player.name} folds")
        elif action == 'r':
            _, bb = BLIND_LEVELS[self.blind_level]
            min_raise = self.current_bet + bb

            # Calculate actual raise amount
            if amount < min_raise:
                amount = min_raise
            if amount > player.stack + player.bet_in_round:
                amount = player.stack + player.bet_in_round

            chips_to_add = amount - player.bet_in_round
            player.stack -= chips_to_add
            self.pot += chips_to_add
            player.bet_in_round = amount
            player.total_invested += chips_to_add
            self.current_bet = amount
            self.raises_this_round += 1

            if player.stack == 0:
                self.action_log.append(f"{player.name} raises to ${amount} (ALL-IN)")
            else:
                self.action_log.append(f"{player.name} raises to ${amount}")

            # Reset actions for other players
            for p in self.players:
                if p != player and p.active:
                    p.actions_this_round = 0
        else:  # Call/Check
            if to_call > 0:
                actual = min(player.stack, to_call)
                player.stack -= actual
                player.bet_in_round += actual
                player.total_invested += actual
                self.pot += actual
                if actual < to_call:
                    self.action_log.append(f"{player.name} calls ${actual} (ALL-IN)")
                else:
                    self.action_log.append(f"{player.name} calls ${actual}")
            else:
                self.action_log.append(f"{player.name} checks")

        player.actions_this_round += 1

    def _next_street(self):
        """Move to next street or end hand."""
        # Reset bets
        for p in self.players:
            p.bet_in_round = 0
        self.current_bet = 0
        self.street_idx += 1

        active = [p for p in self.players if p.active]

        # Check if only one player or all but one are all-in
        players_with_chips = [p for p in active if p.stack > 0]

        if len(active) < 2 or self.street_idx >= len(STREETS):
            self._end_hand()
            return

        # Deal community cards
        street = STREETS[self.street_idx]
        if street == "Flop":
            self.board.extend(self.deck.deal(3))
        elif street in ["Turn", "River"]:
            self.board.extend(self.deck.deal(1))

        self.display_state()
        input(f"\n  --- {street} dealt. Press Enter to continue ---")

        # If only one player has chips, run out the board
        if len(players_with_chips) <= 1:
            while self.street_idx < len(STREETS) - 1:
                self.street_idx += 1
                street = STREETS[self.street_idx]
                if street == "Flop":
                    self.board.extend(self.deck.deal(3))
                else:
                    self.board.extend(self.deck.deal(1))
                self.display_state()
                input(f"\n  --- {street} dealt. Press Enter to continue ---")
            self._end_hand()
            return

        # Start next betting round from first active player after dealer
        self.current_player_idx = (self.dealer_idx + 1) % len(self.players)
        while not self.players[self.current_player_idx].active or self.players[self.current_player_idx].stack == 0:
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
            if self.current_player_idx == self.dealer_idx:
                # No one can act
                self._end_hand()
                return

        self._run_betting_round()

    def _end_hand(self):
        """End hand and determine winner."""
        self.hand_in_progress = False
        active = [p for p in self.players if p.active]

        # Complete board if needed
        while len(self.board) < 5:
            self.board.extend(self.deck.deal(1))

        self.street_idx = 4  # For display purposes
        self.display_state()

        print("\n" + "=" * 70)
        print(f"{'HAND COMPLETE':^70}")
        print("=" * 70)

        if len(active) == 1:
            winner = active[0]
            net_profit = self.pot - winner.total_invested
            winner.stack += self.pot
            print(f"\n  {winner.name} wins ${net_profit} (others folded)")
        else:
            # Showdown
            print(f"\n  Final Board: {self._format_board()}")
            print("\n  SHOWDOWN:")

            board_cards = [eval7.Card(str(c)) for c in self.board]
            results = []
            best_rank = -1
            winners = []

            for p in active:
                hand_cards = [eval7.Card(str(c)) for c in p.hand]
                full_hand = hand_cards + board_cards
                rank = eval7.evaluate(full_hand)
                hand_type = eval7.handtype(rank)
                results.append((p, rank, hand_type))
                print(f"    {p.name}: [{p.hand[0]}] [{p.hand[1]}] - {hand_type}")

                if rank > best_rank:
                    best_rank = rank
                    winners = [p]
                elif rank == best_rank:
                    winners.append(p)

            win_share = self.pot // len(winners)
            remainder = self.pot % len(winners)

            for i, w in enumerate(winners):
                share = win_share + (1 if i < remainder else 0)
                w.stack += share

            if len(winners) == 1:
                net_profit = self.pot - winners[0].total_invested
                print(f"\n  >>> {winners[0].name} wins ${net_profit}! <<<")
            else:
                net_share = win_share - (winners[0].total_invested if winners else 0)
                print(f"\n  >>> Split pot! {', '.join(w.name for w in winners)} each win ${net_share} <<<")

        print("=" * 70)
        input("\n  Press Enter for next hand...")


# --- Main Entry Point ---

def run_gui_mode(args):
    """Run the graphical interface."""
    app = QApplication.instance() or QApplication(sys.argv)

    # Set dark theme
    app.setStyle('Fusion')
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    window = PokerWindow(god_mode=args.god, show_stats=args.tells)
    window.show()

    sys.exit(app.exec())


def run_text_mode(args):
    """Run the text-based interface."""
    game = TextModeGame(
        god_mode=args.god,
        show_tells=args.tells,
        theory_of_mind=args.theoryOfMind
    )
    game.run()


def replay_log_file(log_path):
    """Replay a poker session from a log file, showing hands one at a time."""
    import re
    if not os.path.isfile(log_path):
        print(f"Error: File not found: {log_path}")
        return

    with open(log_path, 'r') as f:
        content = f.read()

    # Split into hands by the "HAND #N" delimiter
    hand_blocks = re.split(r'(?=={60}\nHAND #\d+)', content)
    hands = [b for b in hand_blocks if re.match(r'={60}\nHAND #', b)]

    if not hands:
        print("No hands found in log file.")
        return

    # Check for Claude annotations (in _annotated.txt companion)
    annotations = {}
    annotated_path = log_path.replace('.txt', '_annotated.txt')
    if os.path.isfile(annotated_path):
        with open(annotated_path, 'r') as f:
            ann_content = f.read()
        ann_blocks = re.split(r'(?=={60}\nHAND #\d+)', ann_content)
        for block in ann_blocks:
            m = re.search(r'HAND #(\d+)', block)
            if m:
                hand_num = int(m.group(1))
                # Extract any Claude commentary (text after HAND INTERPRETATION that differs)
                annotations[hand_num] = block

    print(f"\n{'='*60}")
    print(f"POKER SESSION REPLAY — {os.path.basename(log_path)}")
    print(f"Found {len(hands)} hands")
    if annotations:
        print(f"Claude annotations available ({len(annotations)} hands)")
    print(f"{'='*60}")
    print("\nControls: [Enter]=next hand, [N]=jump to hand #N, [Q]=quit\n")

    idx = 0
    while idx < len(hands):
        hand_text = hands[idx].strip()
        m = re.search(r'HAND #(\d+)', hand_text)
        hand_num = int(m.group(1)) if m else idx + 1

        print(f"\n{'='*60}")
        print(hand_text)

        # Show annotation if available
        if hand_num in annotations:
            ann = annotations[hand_num]
            # Find commentary that goes beyond the basic log
            commentary_match = re.search(r'(CLAUDE.*?ANALYSIS|STRATEGIC.*?REVIEW|COMMENTARY)(.*?)(?=\n={60}|\Z)',
                                         ann, re.DOTALL | re.IGNORECASE)
            if commentary_match:
                print(f"\n{'─'*40}")
                print("CLAUDE ANALYSIS:")
                print(commentary_match.group(0).strip())

        print(f"\n[Hand {idx+1} of {len(hands)}]")
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == 'q':
            break
        elif cmd.isdigit():
            target = int(cmd)
            # Find hand by number
            found = False
            for j, h in enumerate(hands):
                hm = re.search(r'HAND #(\d+)', h)
                if hm and int(hm.group(1)) == target:
                    idx = j
                    found = True
                    break
            if not found:
                print(f"Hand #{target} not found.")
        else:
            idx += 1

    print("\nReplay complete.")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="PokerIQ - A poker training application with Theory of Mind",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pokerIQ.py                    # Normal GUI mode
  python pokerIQ.py --textmode         # Text-only mode
  python pokerIQ.py --god              # GUI with God Mode enabled
  python pokerIQ.py --theoryOfMind     # Text mode with Theory of Mind view
  python pokerIQ.py --replay log.txt   # Replay a saved session

Note: --theoryOfMind cannot be combined with --god or --tells
        """
    )

    parser.add_argument("-textmode", "--textmode", action="store_true",
                        help="Run in text-only mode (no GUI required)")
    parser.add_argument("-god", "--god", action="store_true",
                        help="Enable God Mode (see all opponent cards)")
    parser.add_argument("-tells", "--tells", action="store_true",
                        help="Show tells/statistics panel")
    parser.add_argument("-theoryOfMind", "--theoryOfMind", action="store_true",
                        help="Enable Theory of Mind analysis (text mode only, cannot combine with -god or -tells)")
    parser.add_argument("--replay", metavar="LOGFILE",
                        help="Replay a saved poker session from a log file")

    args = parser.parse_args()

    # Replay mode
    if args.replay:
        replay_log_file(args.replay)
        return

    # Validate: --theoryOfMind cannot be combined with --god or --tells
    if args.theoryOfMind and (args.god or args.tells):
        parser.error("--theoryOfMind cannot be combined with --god or --tells")

    # Text mode requested directly
    if args.textmode:
        run_text_mode(args)
        return

    # Check resolution for GUI mode
    width, height = check_resolution()

    if width > 0 and height > 0 and (width < 1920 or height < 1080):
        choice = prompt_resolution_choice(width, height)
        if choice == 'exit':
            print("\nExiting. Please change your screen resolution and restart.")
            sys.exit(0)
        elif choice == 'textmode':
            run_text_mode(args)
            return
        # else: proceed with GUI

    run_gui_mode(args)


if __name__ == "__main__":
    main()
