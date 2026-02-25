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
    QTabWidget, QTextEdit, QScrollArea, QComboBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QSettings
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF, QPalette, QPixmap, QIcon
)

# --- Configuration & Constants ---
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
    "piq_basic_equity": "Equity Eddie",
    "piq_improved_equity": "Savvy Sarah",
    "piq_external_engine": "Engine Emma",
}


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

        is_huge_bet = to_call > (self.stack * 0.25)
        if is_huge_bet:
            if equity < 0.60:
                return 'f', 0

        if self.style == 'tight':
            if equity < pot_odds + 0.15:
                return 'f', 0
            if equity > 0.75:
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
            if self.actions_this_round > 2:
                return 'c', 0
            rng = random.random()
            if equity > 0.60:
                if rng < 0.80:
                    bet = int(game_state['pot'] * random.uniform(0.6, 1.0))
                    return 'r', max(bet, to_call + game_state.get('bb_amount', 2))
                return 'c', 0
            if equity < 0.40 and rng < 0.25:
                bet = int(game_state['pot'] * 0.5)
                return 'r', max(bet, to_call + game_state.get('bb_amount', 2))
            if equity < pot_odds:
                return 'f', 0
            return 'c', 0

        elif self.style == 'optimal':
            if self.actions_this_round > 3:
                return 'c', 0
            if equity > 0.80:
                return 'r', int(game_state['pot'] * 0.8)
            elif equity > 0.60:
                return 'r', int(game_state['pot'] * 0.5)
            elif equity >= pot_odds:
                return 'c', 0
            else:
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

            # Adjust equity estimate based on who's still in
            adjusted_equity = equity

            # If facing aggression from tight player, they likely have strong hand
            if tight_opponents > 0 and to_call > game_state['pot'] * 0.5:
                adjusted_equity *= 0.8  # Discount our equity

            # Against loose players, our strong hands are more valuable
            if loose_opponents > 0 and equity > 0.6:
                adjusted_equity *= 1.1  # Boost equity slightly

            # Be more cautious against aggressive players
            if aggro_opponents > 0 and to_call > 0:
                # They might be bluffing, so call more often with marginal hands
                if equity > 0.35:
                    adjusted_equity = max(adjusted_equity, pot_odds + 0.05)

            # Decision making with adjusted equity
            if adjusted_equity > 0.75:
                return 'r', int(game_state['pot'] * 0.75)
            elif adjusted_equity > 0.55:
                if random.random() < 0.3:
                    return 'r', int(game_state['pot'] * 0.5)
                return 'c', 0
            elif adjusted_equity >= pot_odds:
                return 'c', 0
            else:
                # Occasional bluff
                if random.random() < 0.15 and to_call < game_state['pot'] * 0.3:
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

        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(3)
        self.setFixedSize(240, 185)

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

        # Name
        self.name_label = QLabel(self.player.name)
        self.name_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.name_label, stretch=1)

        # Spacer to balance
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

        # Bet amount
        self.bet_label = QLabel("")
        self.bet_label.setFont(QFont('Arial', 15, QFont.Weight.Bold))
        self.bet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bet_label.setStyleSheet("color: yellow;")
        layout.addWidget(self.bet_label)

        self.update_display()

    def update_display(self):
        # Update name (in case it changed due to bot preference)
        self.name_label.setText(self.player.name)
        self.stack_label.setText(f"${self.player.stack}")

        if self.player.bet_in_round > 0:
            self.bet_label.setText(f"Bet: ${self.player.bet_in_round}")
        else:
            self.bet_label.setText("")

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

        # Update cards
        if self.player.hand and len(self.player.hand) >= 2:
            if self.show_cards:
                self.card1.set_card(str(self.player.hand[0]), face_down=False)
                self.card2.set_card(str(self.player.hand[1]), face_down=False)
            else:
                self.card1.set_card(None, face_down=True)
                self.card2.set_card(None, face_down=True)
        else:
            self.card1.set_card(None, face_down=True)
            self.card2.set_card(None, face_down=True)

        # Update style based on state
        if not self.player.active:
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

    def set_range(self, range_dict):
        """Set range weights from a dictionary."""
        self.init_empty_range()
        for hand, weight in range_dict.items():
            if hand in self.range_weights:
                self.range_weights[hand] = weight
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

                # Draw border
                painter.setPen(QPen(QColor(60, 60, 60), 1))
                painter.drawRect(x, y, cell_w - 1, cell_h - 1)

                # Draw hand text centered in cell
                if weight > 0.5:
                    painter.setPen(QColor(255, 255, 255))
                else:
                    painter.setPen(QColor(150, 150, 150))
                text_rect = QRectF(x, y, cell_w - 1, cell_h - 1)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, hand)


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

        grid_label = QLabel(f"Estimated Range for {player_name}")
        grid_label.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        grid_label.setStyleSheet("color: #fff;")
        left_layout.addWidget(grid_label)

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

    def update_analysis(self, range_dict, notation, explanation):
        """Update the tab with new range analysis."""
        self.range_grid.set_range(range_dict)
        self.notation_text.setText(notation)
        self.explanation_text.setText(explanation)


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

        # Board texture display
        self.board_texture_label = QLabel("Board: --")
        self.board_texture_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        self.board_texture_label.setStyleSheet("color: #fc0; padding: 5px; background: #222; border: 1px solid #444;")
        mode_row.addWidget(self.board_texture_label)

        layout.addLayout(mode_row)

        layout.addWidget(self.tabs, stretch=1)

        self.bot_tabs = {}  # player_name -> TheoryOfMindTab

    def setup_tabs(self, players):
        """Create tabs for all bot players plus Advisor strategy tab."""
        self.tabs.clear()
        self.bot_tabs = {}
        self.tab_indices = {}  # Map player name to tab index

        # Advisor Strategy tab (first tab)
        advisor_tab = QWidget()
        advisor_layout = QVBoxLayout(advisor_tab)
        advisor_layout.setContentsMargins(5, 5, 5, 5)

        # Scrollable area for advice
        advisor_scroll = QScrollArea()
        advisor_scroll.setWidgetResizable(True)
        advisor_scroll.setStyleSheet("QScrollArea { border: none; background: #1a2a1a; }")

        self.advisor_advice = QLabel("Deal a hand to see strategic advice")
        self.advisor_advice.setFont(QFont('Courier', 16))
        self.advisor_advice.setStyleSheet("color: #8f8; padding: 15px; background: #1a2a1a;")
        self.advisor_advice.setWordWrap(True)
        self.advisor_advice.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        advisor_scroll.setWidget(self.advisor_advice)

        advisor_layout.addWidget(advisor_scroll)
        self.tabs.addTab(advisor_tab, "Advisor")

        # Bot player tabs
        for i, player in enumerate(players):
            if player.style != 'human':
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
        """Calculate hero's outs to improve."""
        if not hero_hand or not board:
            return 0, ""

        c1, c2 = str(hero_hand[0]), str(hero_hand[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]
        ranks = 'AKQJT98765432'

        board_cards = [str(c) for c in board]
        board_ranks = [c[0] for c in board_cards]
        board_suits = [c[1] for c in board_cards]

        all_ranks = [r1, r2] + board_ranks
        all_suits = [s1, s2] + board_suits

        outs = 0
        descriptions = []

        # Count suits
        suit_counts = {}
        for s in all_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        # Count ranks
        rank_counts = {}
        for r in all_ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Flush draw (4 to a flush)
        for suit in [s1, s2]:
            if suit_counts.get(suit, 0) == 4:
                outs += 9
                descriptions.append("Flush draw")
                break

        # Straight draw detection
        all_vals = sorted(set(ranks.index(r) for r in all_ranks))
        for i in range(len(all_vals) - 3):
            spread = all_vals[i+3] - all_vals[i]
            if spread == 3:  # Open-ended
                outs += 8
                descriptions.append("OESD")
                break
            elif spread == 4:  # Gutshot
                outs += 4
                descriptions.append("Gutshot")
                break

        # Overcards (if no pair)
        has_pair = any(r in board_ranks for r in [r1, r2])
        if not has_pair:
            board_high = min(ranks.index(br) for br in board_ranks)
            overcard_count = sum(1 for r in [r1, r2] if ranks.index(r) < board_high)
            if overcard_count > 0:
                outs += overcard_count * 3  # ~3 outs per overcard
                descriptions.append(f"{overcard_count} overcard(s)")

        # Set draw (pocket pair, need to hit 1 of 2 remaining)
        if r1 == r2 and rank_counts.get(r1, 0) == 2:
            outs += 2
            descriptions.append("Set draw")

        desc = " + ".join(descriptions) if descriptions else "No draws"
        return outs, desc

    def calculate_scare_cards(self, hero_hand, board, opponents):
        """Calculate cards that would be scary (help villain ranges)."""
        if not board or len(board) < 3:
            return []

        board_cards = [str(c) for c in board]
        board_ranks = [c[0] for c in board_cards]
        board_suits = [c[1] for c in board_cards]
        ranks = 'AKQJT98765432'

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
                    if card_rank not in board_ranks:
                        scare_cards.append(f"{card_rank} (straight)")
                    break

        # Pairing cards (give two pair/trips)
        for r in board_ranks:
            if board_ranks.count(r) == 1:  # Unpaired board card
                scare_cards.append(f"{r} (pairs board)")

        # High cards that hit likely ranges
        for r in 'AKQ':
            if r not in board_ranks:
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

    def estimate_range(self, player, street, actions_this_hand, board, style_override=None):
        """Estimate a player's range based on their style and actions."""
        style = style_override if style_override else player.style
        style_info = self.STYLE_RANGES.get(style, self.STYLE_RANGES['loose'])

        # Get the range mode (loose/neutral/tight)
        mode = self.range_mode

        # Start with preflop range - select based on mode
        if 'raised' in actions_this_hand:
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

        return range_dict, base_notation, "\n".join(explanation_parts)

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

    def update_analysis(self, players, street, board, hero_hand, action_history, pot=None, current_bet=0, hero_bet=0, hero_position='MP'):
        """Update all bot tabs with current analysis."""
        all_ranges = {}
        self.hero_position = hero_position  # Store for use in advice

        # Track which players are active for tab highlighting
        active_players = {p.name for p in players if p.active}
        active_opponents = [p for p in players if p.active and p.style != 'human']

        # Update board texture display
        texture, texture_info = self.analyze_board_texture(board)
        if board and len(board) >= 3:
            self.board_texture_label.setText(f"Board: {texture} | {texture_info.get('flush', '')} | {texture_info.get('straight', '')}")
        else:
            self.board_texture_label.setText("Board: Preflop")

        # Apply range mode multiplier
        range_mult = self.get_range_multiplier()

        for player in players:
            if player.style == 'human':
                continue

            # Track actions for Fiona and Hero history
            for action in action_history:
                if 'Fiona' in action:
                    self.update_fiona_history(action, street)
                if 'Hero' in action:
                    self.update_hero_history(action, street)

            # Determine actions this hand for this player
            actions = set()
            for action in action_history:
                if player.name in action:
                    if 'Raises' in action or 'raises' in action:
                        if 'Preflop' in str(street) or action_history.index(action) < 5:
                            actions.add('raised')
                        else:
                            actions.add('raised_postflop')
                    elif 'Bets' in action or 'bets' in action:
                        actions.add('bet_postflop')
                    elif 'Calls' in action or 'calls' in action:
                        if 'Preflop' in str(street) or action_history.index(action) < 5:
                            actions.add('called')
                        else:
                            actions.add('called_postflop')

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

            range_dict, notation, explanation = self.estimate_range(
                player, street, actions, board, style_override=player_style_override
            )

            # Apply range mode adjustment (with minimum visibility threshold)
            if range_mult != 1.0:
                for hand in range_dict:
                    if range_dict[hand] > 0:
                        # Apply multiplier but keep minimum visibility for hands in range
                        new_weight = range_dict[hand] * range_mult
                        range_dict[hand] = max(0.25, min(1.0, new_weight))  # Min 25% for visibility

            if player.active:
                all_ranges[player.name] = range_dict
            else:
                # Keep the range visible but mark as folded in explanation
                explanation = f"[FOLDED]\n\n{explanation}"
                notation = f"[FOLDED] {notation}"

            # Always store final range for accuracy tracking (even folded players)
            self.final_range_estimates[player.name] = range_dict

            # Update tab (keep grid visible even for folded players)
            if player.name in self.bot_tabs:
                self.bot_tabs[player.name].update_analysis(range_dict, notation, explanation)

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
        if to_call > 0 and pot > 0:
            pot_odds = to_call / (pot + to_call)
            pot_odds_ratio = pot / to_call if to_call > 0 else 0
            self.pot_odds_label.setText(f"Pot Odds: {pot_odds:.1%} ({pot_odds_ratio:.1f}:1)")
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

            # Color equity label based on comparison with pot odds
            if pot_odds > 0:
                if hero_equity > pot_odds:
                    self.equity_label.setStyleSheet("color: #0f0; padding: 8px; background: #222; border: 2px solid #0a0;")  # Green = +EV
                else:
                    self.equity_label.setStyleSheet("color: #f00; padding: 8px; background: #222; border: 2px solid #a00;")  # Red = -EV
            else:
                self.equity_label.setStyleSheet("color: #0af; padding: 8px; background: #222; border: 2px solid #444;")

            # Generate strategy advice with expanded context
            # Build context dictionary with all relevant info
            advice_context = {
                'equity': hero_equity,
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
            }

            main_advice = self.get_strategy_advice_v2(advice_context)
            self.advisor_advice.setText(main_advice)
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
                 player_hands=None, made_hands_by_street=None, parent=None):
        super().__init__(parent)
        self.street_stats = street_stats  # {street: [(name, true_eq, perc_eq, pot_odds, active, is_hero), ...]}
        self.street_actions = street_actions  # {street: ["Player: action", ...]}
        self.board_by_street = board_by_street  # {street: [card_strs]}
        self.player_results = player_results  # {name: (start_stack, end_stack, change)}
        self.player_hands = player_hands or {}  # {name: [card_strs]}
        self.made_hands_by_street = made_hands_by_street or {}  # {street: {name: "hand description"}}

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
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #0af;")
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

        # Add panel for each street (all 4, even if not played)
        # Calculate height based on number of players (34 pixels per player row + 50 for header)
        num_players = len(self.player_results) if self.player_results else 6
        panel_height = 50 + (num_players * 36)  # header + player rows

        streets_order = ["Preflop", "Flop", "Turn", "River"]
        for street in streets_order:
            panel = self.create_street_panel(street)
            panel.setMinimumHeight(panel_height)
            panel.setMaximumHeight(panel_height + 20)  # Slight flexibility
            streets_layout.addWidget(panel)

        # Don't add stretch - let panels take their natural size
        scroll_area.setWidget(streets_widget)
        layout.addWidget(scroll_area, stretch=1)

        # Bottom: Player results (gain/loss)
        results_panel = self.create_results_panel()
        layout.addWidget(results_panel)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedSize(150, 50)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                font-size: 20px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

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
            street_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #0af;")
        else:
            street_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #555;")
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
            cards_label.setStyleSheet("font-size: 22px; background-color: #f8f8f8; padding: 4px 8px; border-radius: 5px;")
            left_layout.addWidget(cards_label)
        else:
            placeholder = QLabel("—" if street == "Preflop" else "")
            placeholder.setStyleSheet("font-size: 20px; color: #555;")
            left_layout.addWidget(placeholder)

        left_layout.addStretch()
        left_widget.setFixedWidth(140)
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
            # Height: 40 header + 34 per player row
            chart_height = 40 + len(stats) * 34
            chart_widget.setMinimumHeight(chart_height)
        else:
            chart_widget = QLabel("Not played")
            chart_widget.setStyleSheet("font-size: 20px; color: #444;")
            chart_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(chart_widget, stretch=3)

        # Right side: Actions with key decisions highlighted
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(3)

        # Add "Key Actions" header
        header = QLabel("Actions:")
        header.setStyleSheet("font-size: 14px; color: #888; font-weight: bold;")
        right_layout.addWidget(header)

        actions = self.street_actions.get(street, [])
        for action in actions[:8]:  # Limit to 8 actions per street
            action_label = QLabel(action)
            action_lower = action.lower()

            # Highlight key decisions with different colors - larger font
            if 'all-in' in action_lower or 'all in' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #ff4444; font-weight: bold;")  # Red for all-in
            elif 'raises to' in action_lower and any(x in action_lower for x in ['$50', '$100', '$150', '$200']):
                action_label.setStyleSheet("font-size: 17px; color: #ff8844; font-weight: bold;")  # Orange for big raises
            elif 'folds' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #888;")  # Gray for folds
            elif 'raises' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #ffcc00;")  # Yellow for raises
            elif 'bets' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #44ff44;")  # Green for bets
            elif 'calls' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #44aaff;")  # Blue for calls
            elif 'checks' in action_lower:
                action_label.setStyleSheet("font-size: 17px; color: #aaa;")  # Light gray for checks
            else:
                action_label.setStyleSheet("font-size: 17px; color: #ccc;")

            action_label.setWordWrap(True)
            right_layout.addWidget(action_label)

        right_layout.addStretch()
        right_widget.setFixedWidth(320)
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
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #fff;")
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
            name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #aaa;")
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
            change_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {change_color};")
            player_layout.addWidget(change_label)

            stack_label = QLabel(f"${start} → ${end}")
            stack_label.setStyleSheet("font-size: 16px; color: #666;")
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

        # Calculate column positions - generous spacing to avoid overlap
        name_x = 10
        cards_x = 120  # Hole cards column
        hand_x = cards_x + 68  # Made hand description (wider gap)
        equity_x = 370  # Start of equity bars (pushed right for hand column)

        # Column headings
        painter.setPen(QColor(255, 255, 255))
        font = QFont('Arial', 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(name_x, 22, "Player")
        painter.drawText(cards_x, 22, "Cards")
        painter.setPen(QColor(180, 180, 100))
        painter.drawText(hand_x, 22, "Hand")

        # Bar width based on available space
        if god_mode:
            bar_max_width = min((w - equity_x - 280) // 2, 130)
        else:
            bar_max_width = min(w - equity_x - 230, 180)
        bar_max_width = max(bar_max_width, 60)

        if god_mode:
            real_x = equity_x
            painter.setPen(QColor(100, 200, 255))
            painter.drawText(real_x, 22, "True Equity")
        else:
            painter.setPen(QColor(100, 255, 100))
            painter.drawText(equity_x, 22, "Equity")

        # Implied odds header - positioned after equity status column
        # The actual x position is computed per-row, so just draw header at estimated position
        if god_mode:
            odds_header_x = equity_x + bar_max_width * 2 + 90
        else:
            odds_header_x = equity_x + bar_max_width + 85
        painter.setPen(QColor(200, 160, 100))
        painter.drawText(odds_header_x, 22, "Pot/Implied")

        # Draw bars for each player - larger bars
        bar_height = 28
        start_y = 40

        for i, (name, true_equity, perceived_equity, pot_odds, is_active, is_hero) in enumerate(self.stats):
            y = start_y + i * (bar_height + 6)

            # Player name - larger font
            if is_hero:
                painter.setPen(QColor(100, 200, 255))
            elif not is_active:
                painter.setPen(QColor(100, 100, 100))
            else:
                painter.setPen(QColor(200, 200, 200))

            font = QFont('Arial', 12, QFont.Weight.Bold)
            painter.setFont(font)
            name_display = name[:12] if len(name) > 12 else name
            painter.drawText(name_x, y + 20, name_display)

            # Draw hole cards with white background for readability
            hole_cards = self.player_hands.get(name, [])
            if hole_cards:
                card_font = QFont('Arial', 11, QFont.Weight.Bold)
                painter.setFont(card_font)
                card_x = cards_x
                for card in hole_cards[:2]:
                    card_text = self.format_card_text(card)
                    suit = card[1] if len(card) > 1 else ''
                    # Draw white background pill for card
                    painter.fillRect(card_x - 2, y + 2, 26, 22, QColor(250, 250, 245))
                    painter.setPen(QPen(QColor(180, 180, 180), 1))
                    painter.drawRect(card_x - 2, y + 2, 26, 22)
                    # Color by suit
                    if suit == 'h':
                        painter.setPen(QColor(220, 40, 40))  # Red hearts
                    elif suit == 'd':
                        painter.setPen(QColor(40, 100, 220))  # Blue diamonds
                    elif suit == 'c':
                        painter.setPen(QColor(40, 160, 40))  # Green clubs
                    else:
                        painter.setPen(QColor(30, 30, 30))  # Black spades
                    painter.drawText(card_x + 2, y + 18, card_text)
                    card_x += 30

            # Draw made hand description - larger font for readability
            made_hand = self.made_hands.get(name, '')
            if made_hand and is_active:
                hand_font = QFont('Arial', 11, QFont.Weight.Bold)
                painter.setFont(hand_font)
                painter.setPen(QColor(220, 220, 120))
                # Truncate to fit column width (hand_x to equity_x)
                max_chars = max(12, (equity_x - hand_x - 10) // 8)
                made_display = made_hand[:max_chars] if len(made_hand) > max_chars else made_hand
                painter.drawText(hand_x, y + 19, made_display)

            if not is_active:
                painter.setPen(QColor(100, 100, 100))
                font = QFont('Arial', 12)
                painter.setFont(font)
                painter.drawText(equity_x, y + 20, "(Folded)")
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
                font = QFont('Arial', 12, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(real_x + 4, y + 18, f"{true_equity:.0%}")

                # Perceived equity bar
                think_x = real_x + bar_max_width + 10
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
                painter.drawText(think_x + 4, y + 18, f"{perceived_equity:.0%}")

                # Show equity status indicator after bars in god mode
                ev_x = think_x + bar_max_width + 10
                font = QFont('Arial', 12, QFont.Weight.Bold)
                painter.setFont(font)
                if true_equity > 0.5:
                    painter.setPen(QColor(50, 200, 50))
                    painter.drawText(ev_x, y + 20, "AHEAD")
                elif true_equity > 0.3:
                    painter.setPen(QColor(200, 200, 50))
                    painter.drawText(ev_x, y + 20, "LIVE")
                else:
                    painter.setPen(QColor(200, 50, 50))
                    painter.drawText(ev_x, y + 20, "BEHIND")

                # Implied odds column (god mode)
                odds_x = ev_x + 70
                font = QFont('Arial', 11)
                painter.setFont(font)
                if pot_odds > 0:
                    implied = pot_odds * 1.5  # Implied odds estimate: pot odds + future value
                    # Color: green if equity > implied odds (profitable call)
                    if true_equity > pot_odds:
                        painter.setPen(QColor(50, 200, 50))
                    else:
                        painter.setPen(QColor(200, 100, 50))
                    painter.drawText(odds_x, y + 20, f"{pot_odds:.0%}/{implied:.0%}")
                else:
                    painter.setPen(QColor(120, 120, 120))
                    painter.drawText(odds_x, y + 20, "—")
            else:
                # Normal mode: Just show perceived equity
                eq_width = int(perceived_equity * bar_max_width)
                eq_color = self.get_equity_color(perceived_equity)

                painter.fillRect(equity_x, y, bar_max_width, bar_height, QColor(50, 50, 50))
                painter.fillRect(equity_x, y, eq_width, bar_height, eq_color)
                painter.setPen(QPen(QColor(80, 80, 80), 1))
                painter.drawRect(equity_x, y, bar_max_width, bar_height)

                painter.setPen(QColor(255, 255, 255))
                font = QFont('Arial', 12, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(equity_x + 4, y + 18, f"{perceived_equity:.0%}")

                # Show equity status
                ev_x = equity_x + bar_max_width + 15
                font = QFont('Arial', 12, QFont.Weight.Bold)
                painter.setFont(font)
                if perceived_equity > 0.5:
                    painter.setPen(QColor(50, 200, 50))
                    painter.drawText(ev_x, y + 20, "AHEAD")
                elif perceived_equity > 0.3:
                    painter.setPen(QColor(200, 200, 50))
                    painter.drawText(ev_x, y + 20, "LIVE")
                else:
                    painter.setPen(QColor(200, 50, 50))
                    painter.drawText(ev_x, y + 20, "BEHIND")

                # Implied odds column (normal mode)
                odds_x = ev_x + 70
                font = QFont('Arial', 11)
                painter.setFont(font)
                if pot_odds > 0:
                    implied = pot_odds * 1.5
                    if perceived_equity > pot_odds:
                        painter.setPen(QColor(50, 200, 50))
                    else:
                        painter.setPen(QColor(200, 100, 50))
                    painter.drawText(odds_x, y + 20, f"{pot_odds:.0%}/{implied:.0%}")
                else:
                    painter.setPen(QColor(120, 120, 120))
                    painter.drawText(odds_x, y + 20, "—")

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
    """Dialog for entering raise amount."""

    def __init__(self, min_raise, max_raise, pot, parent=None, bb_amount=2):
        super().__init__(parent)
        self.setWindowTitle("Raise Amount")
        self.min_raise = min_raise
        self.max_raise = max_raise
        self.pot = pot
        self.bb = bb_amount

        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(f"Min: ${min_raise}  |  Max: ${max_raise}  |  Pot: ${pot}  |  BB: ${bb_amount}")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(min_raise)
        self.slider.setMaximum(max_raise)
        self.slider.setValue(min_raise)
        self.slider.valueChanged.connect(self.update_spinbox)
        layout.addWidget(self.slider)

        # Spinbox
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(min_raise)
        self.spinbox.setMaximum(max_raise)
        self.spinbox.setValue(min_raise)
        self.spinbox.valueChanged.connect(self.update_slider)
        layout.addWidget(self.spinbox)

        # BB multiplier buttons
        bb_layout = QHBoxLayout()
        bb_label = QLabel("BB Multiplier:")
        bb_layout.addWidget(bb_label)
        for mult in [2, 3, 4, 5, 10]:
            val = min(max_raise, bb_amount * mult)
            btn = QPushButton(f"{mult}x")
            btn.setFixedWidth(50)
            btn.clicked.connect(lambda checked, v=val: self.set_value(v))
            bb_layout.addWidget(btn)
        bb_layout.addStretch()
        layout.addLayout(bb_layout)

        # Pot-based quick buttons
        pot_layout = QHBoxLayout()
        pot_label = QLabel("Pot Size:")
        pot_layout.addWidget(pot_label)
        for label, mult in [("1/2", 0.5), ("2/3", 0.67), ("3/4", 0.75), ("Pot", 1.0), ("All-In", None)]:
            btn = QPushButton(label)
            btn.setFixedWidth(60)
            if mult is None:
                btn.clicked.connect(lambda checked, v=max_raise: self.set_value(v))
            else:
                val = max(min_raise, min(max_raise, int(pot * mult)))
                btn.clicked.connect(lambda checked, v=val: self.set_value(v))
            pot_layout.addWidget(btn)
        pot_layout.addStretch()
        layout.addLayout(pot_layout)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_spinbox(self, value):
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)

    def update_slider(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)

    def set_value(self, value):
        value = max(self.min_raise, min(self.max_raise, value))
        self.slider.setValue(value)
        self.spinbox.setValue(value)

    def get_value(self):
        return self.spinbox.value()


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

        # Initialize game state with original player names and styles
        self.players = [
            Player("Hero (You)", "human"),
            Player("Optimal Olivia", "optimal"),
            Player("Tight Tim", "tight"),
            Player("Loose Bruce", "loose"),
            Player("Aggro Angela", "aggressive"),
            Player("Fluid Fiona", "tom")  # Theory of Mind player
        ]

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

    def _load_bot_preferences(self):
        """Load bot preferences from QSettings."""
        for seat in range(len(self.players)):
            key = f"bot_preference/seat_{seat}"
            bot_type_id = self.settings.value(key, "default")
            self.bot_preferences[seat] = bot_type_id

    def _apply_color_preference(self):
        """Apply the legacy colors preference to the global flag."""
        global _use_legacy_colors
        _use_legacy_colors = self.legacy_colors

    def _capture_street_stats(self, street):
        """Capture player stats for the hand summary display."""
        game_state = {
            'board': [str(c) for c in self.board],
            'pot': self.pot,
            'players': self.players,
            'current_bet': self.current_bet
        }

        # Calculate true equities in god mode
        true_equities = {}
        if self.god_mode:
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
                if self.god_mode:
                    true_equity = true_equities.get(p, 0.0)
                    stats.append((p.name, true_equity, perceived_equity, pot_odds, p.active, p.style == 'human'))
                else:
                    stats.append((p.name, None, perceived_equity, pot_odds, p.active, p.style == 'human'))
            else:
                stats.append((p.name, None, 0, 0, p.active, p.style == 'human'))

        self.hand_history['street_stats'][street] = stats

        # Also capture the board state at end of this street
        if street not in self.hand_history['board_by_street']:
            self.hand_history['board_by_street'][street] = [str(c) for c in self.board]

    def _save_bot_preferences(self):
        """Save bot preferences to QSettings."""
        for seat, bot_type_id in self.bot_preferences.items():
            key = f"bot_preference/seat_{seat}"
            self.settings.setValue(key, bot_type_id)
        self.settings.sync()

    def _apply_bot_preferences(self):
        """Apply bot preferences to all players."""
        for seat, player in enumerate(self.players):
            if seat in self.original_player_info and self.original_player_info[seat][1] == 'human':
                # Human player, skip bot assignment
                continue

            bot_type_id = self.bot_preferences.get(seat, "default")

            if bot_type_id == "default":
                # Restore original name, style, and behavior
                if seat in self.original_player_info:
                    player.name, player.style = self.original_player_info[seat]
                player.clear_piq_bot()
            elif bot_type_id.startswith("piq_"):
                # poker_iq bot selected - use cute name
                if bot_type_id in BOT_CUTE_NAMES and BOT_CUTE_NAMES[bot_type_id] is not None:
                    player.name = BOT_CUTE_NAMES[bot_type_id]
                player.set_piq_bot(bot_type_id, seat)
            else:
                # Original bot style selected from menu - restore that style's original name
                style_map = {
                    "optimal": "optimal",
                    "tight": "tight",
                    "loose": "loose",
                    "aggressive": "aggressive",
                    "tom": "tom",
                }
                if bot_type_id in style_map:
                    player.style = style_map[bot_type_id]
                    # Use the cute name for this original style
                    if bot_type_id in BOT_CUTE_NAMES and BOT_CUTE_NAMES[bot_type_id] is not None:
                        player.name = BOT_CUTE_NAMES[bot_type_id]
                player.clear_piq_bot()

    def get_bot_type_display_name(self, bot_type_id: str) -> str:
        """Get display name for a bot type ID."""
        if bot_type_id in BOT_TYPE_MAP:
            return BOT_TYPE_MAP[bot_type_id][0]
        return bot_type_id

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

    def setup_ui(self):
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

        self.god_mode_cb = QCheckBox("God Mode")
        self.god_mode_cb.setStyleSheet(cb_style)
        self.god_mode_cb.setChecked(self.god_mode)
        self.god_mode_cb.stateChanged.connect(self.toggle_god_mode)
        top_bar.addWidget(self.god_mode_cb)

        top_bar.addSpacing(20)

        self.stats_cb = QCheckBox("Show Tells")
        self.stats_cb.setStyleSheet(cb_style)
        self.stats_cb.setChecked(self.show_stats)
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
            left_panel.addSpacing(20)
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
        right_panel.addSpacing(20)
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

        btn_style = "QPushButton { font-size: 16px; font-weight: bold; }"

        self.fold_btn = QPushButton("Fold")
        self.fold_btn.setFixedSize(130, 55)
        self.fold_btn.setStyleSheet(btn_style)
        self.fold_btn.clicked.connect(lambda: self.human_action('f', 0))
        self.fold_btn.setEnabled(False)
        action_layout.addWidget(self.fold_btn)

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
        game_container_layout.addLayout(action_layout)

        # Graphical Stats Panel (inside game container)
        self.stats_panel = StatsPanel()
        self.stats_panel.setVisible(self.show_stats)
        game_container_layout.addWidget(self.stats_panel)

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
        self.tom_panel.setup_tabs(self.players)
        self.tom_panel.set_update_callback(self.update_theory_of_mind)  # Wire up range mode callback
        tom_container_layout.addWidget(self.tom_panel, stretch=1)

        # Action buttons for Theory of Mind view
        tom_action_layout = QHBoxLayout()
        tom_action_layout.addStretch()

        tom_btn_style = "QPushButton { font-size: 18px; font-weight: bold; padding: 10px 20px; }"

        self.tom_fold_btn = QPushButton("Fold")
        self.tom_fold_btn.setFixedSize(140, 60)
        self.tom_fold_btn.setStyleSheet(tom_btn_style + "QPushButton { background-color: #633; }")
        self.tom_fold_btn.clicked.connect(lambda: self.human_action('f', 0))
        self.tom_fold_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_fold_btn)

        tom_action_layout.addSpacing(20)

        self.tom_call_btn = QPushButton("Call")
        self.tom_call_btn.setFixedSize(140, 60)
        self.tom_call_btn.setStyleSheet(tom_btn_style + "QPushButton { background-color: #363; }")
        self.tom_call_btn.clicked.connect(lambda: self.human_action('c', 0))
        self.tom_call_btn.setEnabled(False)
        tom_action_layout.addWidget(self.tom_call_btn)

        tom_action_layout.addSpacing(20)

        self.tom_raise_btn = QPushButton("Raise")
        self.tom_raise_btn.setFixedSize(140, 60)
        self.tom_raise_btn.setStyleSheet(tom_btn_style + "QPushButton { background-color: #336; }")
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

        # Blinds display (bottom left, white text)
        self.blinds_label = QLabel("Blinds: $1/$2")
        self.blinds_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 5px 10px;
                background-color: #222;
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        self.blinds_label.setFixedWidth(180)
        bottom_bar.addWidget(self.blinds_label)

        # Log area (center)
        self.log_label = QLabel("Click 'New Hand' to start playing!")
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.log_label.setFont(QFont('Courier', 16))
        self.log_label.setStyleSheet("background-color: #111; color: #0f0; padding: 10px;")
        self.log_label.setWordWrap(True)
        self.log_label.setMaximumHeight(70)
        bottom_bar.addWidget(self.log_label, stretch=1)

        main_layout.addLayout(bottom_bar)

    def toggle_god_mode(self, state):
        self.god_mode = self.god_mode_cb.isChecked()
        if self.god_mode:
            hero_name = self.players[0].name if self.players else "Hero (You)"
            self.hand_assists_used.setdefault(hero_name, set()).add("God Mode")
        self.update_all_panels()
        self.update_checkbox_states()
        self._refresh_feature_status()
        self._broadcast_features()

    def toggle_stats(self, state):
        self.show_stats = self.stats_cb.isChecked()
        if self.show_stats:
            hero_name = self.players[0].name if self.players else "Hero (You)"
            self.hand_assists_used.setdefault(hero_name, set()).add("Show Tells")
        self.update_stats_display()
        self.update_checkbox_states()
        self._refresh_feature_status()
        self._broadcast_features()

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
        self.tom_panel.update_analysis(
            self.players,
            current_street,
            self.board,
            hero.hand if hero.hand else None,
            self.action_history,
            self.pot,  # Pass actual pot value
            current_bet=self.current_bet,  # Pass current bet for pot odds
            hero_bet=hero.bet_in_round,  # Pass hero's current bet
            hero_position=hero_position  # Pass hero's position
        )

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
        self.log_label.setText(" | ".join(self.action_log))
        # Also write to file
        self.write_log(msg, include_stats=include_stats)
        # Track for Theory of Mind analysis
        if hasattr(self, 'action_history'):
            self.action_history.append(msg)
            self.update_theory_of_mind()

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
        """Broadcast feature toggles to the other network instance."""
        if not self.network_mode:
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
        if features.get('god_mode'):
            active.append("God Mode")
            self.hand_assists_used.setdefault(player_name, set()).add("God Mode")
        if features.get('tells'):
            active.append("Tells")
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
        for idx, panel in self.player_panels:
            player = self.players[idx]
            # Hero always sees their cards
            if player.style == 'human':
                panel.show_cards = True
            # At showdown, show all active players' cards
            elif hasattr(self, 'at_showdown') and self.at_showdown and player.active:
                panel.show_cards = True
            # In god mode, show all cards
            elif self.god_mode:
                panel.show_cards = True
            else:
                panel.show_cards = False
            panel.update_display()

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
        self.hand_number += 1
        self.action_log = []
        self.action_history = []  # Reset for Theory of Mind
        self.log_action("=== NEW HAND ===")

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
        # {player_name: set of assist names}
        self.hand_assists_used = {}
        hero_name = self.players[0].name if self.players else "Hero (You)"
        if self.god_mode:
            self.hand_assists_used.setdefault(hero_name, set()).add("God Mode")
        if self.show_stats:
            self.hand_assists_used.setdefault(hero_name, set()).add("Show Tells")

        # Reset hand history for interpretation
        self.hand_history = {
            'hero_cards': [],
            'hero_actions': [],
            'street_equities': {},
            'key_events': [],
            'board_by_street': {},
            'villain_info': {},
            'street_stats': {},      # {street: [(name, true_eq, perc_eq, pot_odds, active, is_hero), ...]}
            'street_actions': {}     # {street: ["Player: action", ...]}
        }

        for p in self.players:
            p.reset_for_hand()
            if p.stack <= 0:
                p.active = False

        # Save starting stacks for gain/loss tracking
        self.starting_stacks = {p.name: p.stack for p in self.players}

        # Check if hero is busted
        hero = self.players[0]
        if hero.stack <= 0:
            reply = QMessageBox.question(
                self, "Game Over",
                "You're out of chips! Would you like to start a new game?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reset_game()
            return

        active_count = sum(1 for p in self.players if p.active)
        if active_count < 2:
            QMessageBox.information(self, "Game Over", "You've won! All opponents are eliminated!")
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
                    # They've acted and don't need to call - end betting
                    self.end_betting_round()
                    return
            else:
                # No one has chips - end betting
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
        """Enable action buttons for human player."""
        self.waiting_for_human = True
        hero_seat = self.my_seat if self.network_mode == "client" and self.my_seat is not None else 0
        player = self.players[hero_seat]
        to_call = max(0, self.current_bet - player.bet_in_round)

        self.fold_btn.setEnabled(True)
        self.tom_fold_btn.setEnabled(True)

        if to_call <= 0:
            self.call_btn.setText("Check")
            self.tom_call_btn.setText("Check")
        else:
            self.call_btn.setText(f"Call ${to_call}")
            self.tom_call_btn.setText(f"Call ${to_call}")
        self.call_btn.setEnabled(True)
        self.tom_call_btn.setEnabled(True)

        _, bb_amount = BLIND_LEVELS[self.blind_level]
        min_raise = to_call + bb_amount
        if player.stack > min_raise:
            self.raise_btn.setEnabled(True)
            self.tom_raise_btn.setEnabled(True)
        else:
            self.raise_btn.setEnabled(False)
            self.tom_raise_btn.setEnabled(False)

    def disable_human_actions(self):
        """Disable action buttons."""
        self.waiting_for_human = False
        self.fold_btn.setEnabled(False)
        self.call_btn.setEnabled(False)
        self.raise_btn.setEnabled(False)
        self.tom_fold_btn.setEnabled(False)
        self.tom_call_btn.setEnabled(False)
        self.tom_raise_btn.setEnabled(False)

    def human_action(self, action, amount):
        """Process human player's action."""
        if not self.waiting_for_human:
            return

        self.disable_human_actions()

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

    def show_raise_dialog(self):
        """Show dialog to select raise amount."""
        # Use the correct hero seat (seat 0 for local/host, my_seat for client)
        hero_seat = self.my_seat if self.network_mode == "client" and self.my_seat is not None else 0
        player = self.players[hero_seat]
        to_call = int(self.current_bet - player.bet_in_round)
        _, bb_amount = BLIND_LEVELS[self.blind_level]
        min_raise = int(to_call + bb_amount)
        max_raise = int(player.stack)

        if max_raise <= min_raise:
            # Can't raise, just go all-in
            self.human_action('r', max_raise)
            return

        dialog = RaiseDialog(min_raise, max_raise, int(self.pot), self, bb_amount)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            amount = dialog.get_value()
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
                min_raise = to_call + bb_amount
                actual_raise = max(amount, min_raise)
                if player.stack <= actual_raise:
                    actual_raise = player.stack
                player.stack -= actual_raise
                player.bet_in_round += actual_raise
                player.total_invested += actual_raise
                self.current_bet = player.bet_in_round
                self.pot += actual_raise
                self.log_action(f"{player.name}: Raises to ${player.bet_in_round}")
                self.last_raiser = player_idx
                self.raises_this_round += 1

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

        # Broadcast action to network clients (host mode)
        if self.network_mode == "host" and self.network_server:
            action_name = {'f': 'fold', 'r': 'raise', 'c': 'call'}.get(action, 'check')
            if action == 'c' and to_call == 0:
                action_name = 'check'
            self.network_server.broadcast_action(
                player_idx, player.name, action_name, amount, self.pot
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

        # Track board and hero equity for interpretation
        self.hand_history['board_by_street'][street] = [str(c) for c in self.board]
        hero = self.players[0]
        if hero.active and hero.hand:
            game_state = {
                'board': [str(c) for c in self.board],
                'pot': self.pot,
                'players': self.players,
                'current_bet': self.current_bet
            }
            equity, _, _ = hero.calculate_current_stats(game_state, True)
            self.hand_history['street_equities'][street] = equity

        # Update displays
        self.update_all_panels()
        self.update_stats_display()

        # Start new betting round (from dealer + 1)
        self.current_player_idx = (self.dealer_idx + 1) % len(self.players)
        self.betting_round_init()

    def end_hand(self):
        """End the hand and determine winner."""
        self.disable_human_actions()

        # Capture final street stats before ending (guard against out-of-bounds
        # since end_betting_round already increments street_idx past the last street)
        if self.street_idx < len(STREETS):
            final_street = STREETS[self.street_idx]
            self._capture_street_stats(final_street)

        active = [p for p in self.players if p.active]

        if len(active) == 1:
            winner = active[0]
            net_profit = self.pot - winner.total_invested
            winner.stack += self.pot
            self.table.set_pot(net_profit)
            self.log_action(f"{winner.name} wins ${net_profit}!")
            self.table.set_message(f"{winner.name} wins ${net_profit}!")
            self.write_log(f"Winner: {winner.name} - ${net_profit} (others folded)")
        else:
            # Showdown
            self.at_showdown = True
            self.table.set_street("Showdown")

            # Make sure board is complete
            while len(self.board) < 5:
                self.board.extend(self.deck.deal(1))
            self.table.set_board(self.board)

            # Evaluate hands
            board_cards = [eval7.Card(str(c)) for c in self.board]

            # Calculate hand ranks for all active players
            player_ranks = {}
            results = []
            for p in active:
                hand_cards = [eval7.Card(str(c)) for c in p.hand]
                full_hand = hand_cards + board_cards
                rank = eval7.evaluate(full_hand)
                hand_type = eval7.handtype(rank)
                player_ranks[p] = rank
                results.append(f"{p.name}: {hand_type}")

            # Log results
            for r in results:
                self.log_action(r)

            # Calculate side pots
            # Get all unique investment levels from all players (including folded)
            all_investments = sorted(set(p.total_invested for p in self.players if p.total_invested > 0))

            winners = []
            total_won = {}
            prev_level = 0

            for level in all_investments:
                # Players eligible for this pot level are those who invested at least this much AND are still active
                eligible = [p for p in active if p.total_invested >= level]

                if not eligible:
                    continue

                # Calculate pot for this level
                # Each player contributes (level - prev_level) or their total investment minus prev_level, whichever is less
                pot_contribution = 0
                for p in self.players:
                    contrib = min(p.total_invested, level) - min(p.total_invested, prev_level)
                    pot_contribution += contrib

                if pot_contribution > 0:
                    # Find winner(s) among eligible players
                    best_rank = max(player_ranks[p] for p in eligible)
                    pot_winners = [p for p in eligible if player_ranks[p] == best_rank]

                    win_share = pot_contribution // len(pot_winners)
                    for w in pot_winners:
                        w.stack += win_share
                        total_won[w] = total_won.get(w, 0) + win_share
                        # Only count as "winner" if there was actual competition
                        # (not just returning uncalled bet to sole eligible player)
                        if w not in winners and len(eligible) > 1:
                            winners.append(w)

                prev_level = level

            # Display results
            if winners:
                winner_msgs = []
                for w in winners:
                    net_profit = total_won.get(w, 0) - w.total_invested
                    winner_msgs.append(f"{w.name} (${net_profit})")
                winner_names = ", ".join(winner_msgs)
                self.table.set_message(f"Winner: {winner_names}")
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
                }

                self.network_server.broadcast_hand_end(winner_indices, self.pot, shown_hands, hand_summary)
            except Exception as e:
                print(f"Error broadcasting hand summary: {e}")
                # Fall back to basic hand_end without summary
                self.network_server.broadcast_hand_end(winner_indices, self.pot, shown_hands)

        # Update display
        self.update_all_panels()

        # Move dealer button to next player with chips
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
        attempts = 0
        while self.players[self.dealer_idx].stack <= 0 and attempts < len(self.players):
            self.dealer_idx = (self.dealer_idx + 1) % len(self.players)
            attempts += 1

        # Check for game over (only one player with chips)
        players_with_chips = [p for p in self.players if p.stack > 0]
        if len(players_with_chips) == 1:
            winner = players_with_chips[0]
            self.show_game_over(winner)

    def show_game_over(self, winner):
        """Show game over dialog and offer to play again."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Game Over!")
        msg.setText(f"{winner.name} wins the game with ${winner.stack}!")
        msg.setInformativeText("Would you like to play another game?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

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
        """Describe what made hand a player has using poker terminology."""
        if not hole_cards or not board:
            return "no hand"

        all_cards = [str(c) for c in hole_cards] + [str(c) for c in board]
        all_ranks = [c[0] for c in all_cards]
        all_suits = [c[1] for c in all_cards]
        hole_ranks = [str(c)[0] for c in hole_cards]
        hole_suits = [str(c)[1] for c in hole_cards]
        board_ranks = [str(c)[0] for c in board]

        # Count ranks
        rank_counts = {}
        for r in all_ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Count board ranks separately
        board_rank_counts = {}
        for r in board_ranks:
            board_rank_counts[r] = board_rank_counts.get(r, 0) + 1

        # Check for flush
        suit_counts = {}
        for s in all_suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        # Pair detection using hole cards
        has_pair = hole_ranks[0] == hole_ranks[1]

        # Rank comparison helper (A=0, K=1, ..., 2=12)
        rank_order = 'AKQJT98765432'
        def rank_value(r):
            return rank_order.index(r) if r in rank_order else 99

        # Check for full house
        trips_rank = None
        pair_rank = None
        for r, cnt in rank_counts.items():
            if cnt >= 3:
                trips_rank = r
            elif cnt == 2:
                pair_rank = r
        if trips_rank and pair_rank:
            return f"full house ({trips_rank}s full of {pair_rank}s)"

        # Check for flush (hero must use at least one card)
        for suit in hole_suits:
            if suit_counts.get(suit, 0) >= 5:
                return "flush"

        # Check for set (pocket pair + one on board)
        if has_pair and rank_counts.get(hole_ranks[0], 0) >= 3:
            return f"set of {hole_ranks[0]}s"

        # Check for trips (one hole card matches a PAIR on the board)
        for hole_rank in hole_ranks:
            if rank_counts.get(hole_rank, 0) >= 3:
                if board_rank_counts.get(hole_rank, 0) >= 2:
                    return f"trips ({hole_rank}s)"

        # Check for straight
        all_vals = sorted(set(rank_order.index(r) for r in all_ranks))
        for i in range(len(all_vals) - 4):
            if all_vals[i+4] - all_vals[i] == 4:
                hero_vals = [rank_value(r) for r in hole_ranks]
                straight_vals = all_vals[i:i+5]
                if any(hv in straight_vals for hv in hero_vals):
                    return "straight"

        # Check for two pair
        pairs = [r for r, cnt in rank_counts.items() if cnt >= 2]
        hero_in_pairs = [r for r in hole_ranks if r in pairs]
        if len(pairs) >= 2 and len(hero_in_pairs) >= 1:
            return "two pair"

        # Check for overpair
        if has_pair and all(rank_value(hole_ranks[0]) < rank_value(br) for br in board_ranks):
            return f"overpair ({hole_ranks[0]}{hole_ranks[0]})"
        elif has_pair:
            return f"pocket pair ({hole_ranks[0]}{hole_ranks[0]})"

        # Check for pairs with board
        paired_with_board = hole_ranks[0] in board_ranks or hole_ranks[1] in board_ranks
        if paired_with_board:
            paired_rank = hole_ranks[0] if hole_ranks[0] in board_ranks else hole_ranks[1]
            sorted_board = sorted(board_ranks, key=lambda x: rank_value(x))
            if paired_rank == sorted_board[0]:
                return f"top pair ({paired_rank}s)"
            elif len(sorted_board) > 1 and paired_rank == sorted_board[1]:
                return f"second pair ({paired_rank}s)"
            else:
                return f"bottom pair ({paired_rank}s)"

        # Check for draws (only if not river - 5 cards means no more to come)
        is_river = len(board) >= 5
        if not is_river:
            # Check for flush draw
            for suit in hole_suits:
                if suit_counts.get(suit, 0) == 4:
                    return "flush draw"

            # Check for straight draw
            for i in range(len(all_vals) - 3):
                if all_vals[i+3] - all_vals[i] <= 4:
                    return "straight draw"

        high_card = min(hole_ranks, key=lambda r: rank_value(r))
        return f"{high_card}-high"

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

        dialog = HandSummaryDialog(
            street_stats=street_stats,
            street_actions=street_actions,
            board_by_street=board_by_street,
            player_results=player_results,
            player_hands=player_hands,
            made_hands_by_street=made_hands_by_street,
            parent=self
        )
        dialog.exec()

    def show_hand_interpretation(self, active_players, winners, hand_results):
        """Generate and display a narrative interpretation of the hand with poker terminology."""
        hero = self.players[0]
        hero_cards = self.hand_history.get('hero_cards', [])
        hero_hand_name = self.hand_history.get('hero_hand_name', 'unknown hand')

        lines = []
        lines.append(f"Hand #{self.hand_number} Analysis")
        lines.append("-" * 40)

        # Note if assists were used during this hand (per player)
        assists_used = getattr(self, 'hand_assists_used', {})
        if assists_used:
            for player_name, assist_set in sorted(assists_used.items()):
                lines.append(f"[{player_name} used: {', '.join(sorted(assist_set))}]")
            lines.append("")

        # Show all players' hole cards (God Mode knowledge)
        lines.append("HOLE CARDS:")
        for p in self.players:
            if p.hand:
                hand_str = ' '.join(str(c) for c in p.hand)
                preflop_strength = self.categorize_preflop_hand(p.hand)
                lines.append(f"  {p.name}: {hand_str} ({preflop_strength})")

        lines.append("")

        # Starting hand analysis
        if hero_cards:
            lines.append(f"Your hand: {hero_hand_name} ({' '.join(hero_cards)})")

        # Track equity journey through streets
        equities = self.hand_history.get('street_equities', {})
        boards = self.hand_history.get('board_by_street', {})

        for street in ['Flop', 'Turn', 'River']:
            if street in boards:
                board_cards = boards[street]
                eq = equities.get(street, 0)

                if street == 'Flop' and len(board_cards) >= 3:
                    lines.append(f"\n{street}: {' '.join(board_cards[:3])}")
                    lines.append(f"  Your equity: {eq:.0%}")

                    # Analyze what each active player had
                    for p in active_players:
                        if p.hand and p.name != hero.name:
                            made_hand = self.describe_made_hand(p.hand, board_cards[:3])
                            lines.append(f"  {p.name}: {made_hand}")

                elif street in ['Turn', 'River']:
                    new_card = board_cards[-1]
                    prev_street = 'Flop' if street == 'Turn' else 'Turn'
                    prev_eq = equities.get(prev_street, eq)

                    lines.append(f"\n{street}: {new_card}")

                    # Describe what the card did
                    card_impact = self.analyze_card_impact(new_card, board_cards, active_players)
                    if card_impact:
                        lines.append(f"  {card_impact}")

                    delta = eq - prev_eq
                    if delta > 0.15:
                        lines.append(f"  Your equity improved: {prev_eq:.0%} -> {eq:.0%}")
                    elif delta < -0.15:
                        lines.append(f"  Your equity dropped: {prev_eq:.0%} -> {eq:.0%}")

        # Final result with detailed analysis
        lines.append("")
        lines.append("=" * 30)
        lines.append("SHOWDOWN RESULTS:")

        if hand_results:
            for result in hand_results:
                lines.append(f"  {result}")

            lines.append("")

            # Analyze why winner won
            if winners:
                winner = winners[0]
                if len(winners) > 1:
                    net_each = (self.pot // len(winners)) - winners[0].total_invested
                    lines.append(f"SPLIT POT: {len(winners)} ways, ${net_each} each")
                    lines.append(f"Winners: {', '.join(w.name for w in winners)}")
                else:
                    net_profit = self.pot - winner.total_invested
                    lines.append(f"WINNER: {winner.name} wins ${net_profit}")

                # Explain why others lost and summarize winners
                lines.append("")
                lines.append("Analysis:")

                # Show what winners had
                for w in winners:
                    if w.hand:
                        made_hand = self.describe_made_hand(w.hand, self.board)
                        lines.append(f"  {w.name}: won with {made_hand}")

                # Explain why losers lost
                for p in active_players:
                    if p not in winners and p.hand:
                        loss_reason = self.explain_loss(p, winners[0], self.board)
                        lines.append(f"  {p.name}: {loss_reason}")

                if hero in winners:
                    lines.append(f"  YOU WON with {hero_hand_name}!")
                elif hero in active_players:
                    lines.append(f"  You lost with {hero_hand_name}")
                elif hero.hand:
                    lines.append(f"  You folded {hero_hand_name}")
        else:
            winner = winners[0]
            net_profit = self.pot - winner.total_invested
            if hero in winners:
                lines.append(f"You won ${net_profit} - all opponents folded!")
            else:
                lines.append(f"{winner.name} wins ${net_profit} uncontested")

        # Write interpretation to log file
        self.write_log("\n" + "=" * 40)
        self.write_log("HAND INTERPRETATION:")
        for line in lines:
            self.write_log(f"  {line}")
        self.write_log("=" * 40)

        # Display in a moveable non-modal dialog with large font and scrolling
        interpretation_text = "\n".join(lines)
        dialog = QDialog(self)
        dialog.setWindowTitle("Hand Summary")
        dialog.setMinimumSize(600, 500)
        dialog.resize(650, 600)  # Larger default size
        dialog.setModal(False)  # Non-modal so user can interact with main window

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)

        # Use scroll area to allow scrolling for long summaries
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #2a2a2a; }")

        text_label = QLabel(interpretation_text)
        text_label.setFont(QFont('Arial', 18))
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: white; background-color: #2a2a2a; padding: 15px;")
        text_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(text_label)
        layout.addWidget(scroll_area)

        # Stats button to show graphical summary
        stats_btn = QPushButton("Stats")
        stats_btn.setFixedSize(100, 40)
        stats_btn.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        stats_btn.setStyleSheet("QPushButton { background-color: #363; }")
        stats_btn.clicked.connect(lambda: self._show_stats_from_dialog(dialog))

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(100, 40)
        ok_btn.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        ok_btn.clicked.connect(dialog.close)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(stats_btn)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        dialog.show()  # Non-blocking show instead of exec()

    def _show_stats_from_dialog(self, parent_dialog):
        """Show the graphical hand summary from the text summary dialog."""
        parent_dialog.close()
        self.show_hand_summary()

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

        self._save_bot_preferences()
        self._apply_bot_preferences()

        # Refresh the display to show updated player names
        self.update_all_panels()

        dialog.accept()

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

    def _show_network_status_dialog(self):
        """Show current network status with option to disconnect."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Network Status")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        if self.network_mode == "host":
            status = f"Hosting game: {self.network_server.server_name}"
            status += f"\nAddress: {self.network_server.get_server_address()}"
            status += f"\nConnected players: {self.network_server.get_connected_count()}"
            status += f"\nSeated players: {self.network_server.get_seated_count()}"
        else:
            status = f"Connected to: {self.network_client.server_name}"
            status += f"\nYour seat: {self.my_seat + 1 if self.my_seat is not None else 'None'}"

        label = QLabel(status)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)

        # Disconnect button
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(lambda: self._disconnect_network(dialog))
        layout.addWidget(disconnect_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _start_hosting(self):
        """Start hosting a network game."""
        dialog = HostGameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.network_server = dialog.get_server()
            if self.network_server:
                self.network_mode = "host"
                self.network_btn.setStyleSheet(
                    "QPushButton { font-size: 15px; background-color: #363; }"
                )
                self.network_btn.setText("Network*")

                # Rename hero to indicate server role
                self.players[0].name = "Hero (Server)"
                self.setWindowTitle("PokerIQ - Server")
                self.update_all_panels()

                # Connect server signals
                self.network_server.client_connected.connect(self._on_client_connected)
                self.network_server.client_disconnected.connect(self._on_client_disconnected)
                self.network_server.seat_assigned.connect(self._on_seat_assigned)
                self.network_server.action_received.connect(self._on_network_action_received)
                self.network_server.feature_toggled.connect(self._on_feature_toggle_received)

                self._refresh_feature_status()

                QMessageBox.information(self, "Server Started",
                    f"Hosting game on port {self.network_server._server.serverPort()}\n"
                    f"Waiting for players to connect...")

    def _join_game(self):
        """Join a network game."""
        # First show connect dialog
        join_dialog = JoinGameDialog("Hero (Client)", self)
        if join_dialog.exec() == QDialog.DialogCode.Accepted:
            self.network_client = join_dialog.get_client()
            if self.network_client:
                # Now show seat selection
                seat_dialog = SeatSelectionDialog(self.network_client, 6, self)
                seat_dialog.seat_selected.connect(self._on_my_seat_selected)

                if seat_dialog.exec() == QDialog.DialogCode.Accepted:
                    self.network_mode = "client"
                    self.network_btn.setStyleSheet(
                        "QPushButton { font-size: 15px; background-color: #336; }"
                    )
                    self.network_btn.setText("Network*")
                    self.setWindowTitle("PokerIQ - Client")

                    # Connect client signals for game events
                    self._connect_client_signals()
                    self._refresh_feature_status()

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
        client.hand_started.connect(self._on_hand_started)
        client.hand_ended.connect(self._on_hand_ended)
        client.active_player_changed.connect(self._on_active_player_changed)
        client.feature_toggle_received.connect(self._on_feature_toggle_received)

    def _on_my_seat_selected(self, seat_index: int):
        """Handle our seat selection confirmation."""
        self.my_seat = seat_index
        # Update hero player to this seat
        self.players[seat_index].style = 'human'
        self.players[seat_index].name = "Hero (Client)"

        # Mark server host player (seat 0) as network_human so ToM creates a tab
        if seat_index != 0:
            seats = self.network_client.seats if self.network_client else {}
            if 0 in seats and seats[0] is not None:
                self.players[0].style = 'network_human'
                self.players[0].name = seats[0]  # e.g. "Hero (Server)"

        # Refresh Theory of Mind tabs to include all non-hero players
        if hasattr(self, 'tom_panel'):
            self.tom_panel.setup_tabs(self.players)

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
        self.update_all_panels()

        if dialog:
            dialog.accept()

    # --- Network Event Handlers (Host) ---

    def _on_client_connected(self, client_id: str, player_name: str):
        """Handle client connection (host only)."""
        self.update_status(f"{player_name} connected")

    def _on_client_disconnected(self, client_id: str):
        """Handle client disconnection (host only)."""
        self.update_status("A player disconnected")
        # Remove from human seats
        for seat in list(self.network_human_seats):
            if self.network_server.get_client_for_seat(seat) is None:
                self.network_human_seats.discard(seat)
                self.players[seat].style = self.original_player_info[seat][1]
                self.players[seat].name = self.original_player_info[seat][0]
        self.update_all_panels()

    def _on_seat_assigned(self, client_id: str, seat_index: int):
        """Handle seat assignment (host only)."""
        # Mark this seat as human-controlled
        self.network_human_seats.add(seat_index)
        player_name = self.network_server._clients[client_id].player_name
        self.players[seat_index].style = 'network_human'
        self.players[seat_index].name = player_name
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
            bet_amount = amount
            actual_bet = min(bet_amount, player.stack)
            player.stack -= actual_bet
            player.bet_in_round += actual_bet
            player.total_invested += actual_bet
            self.pot += actual_bet
            if player.bet_in_round > self.current_bet:
                self.current_bet = player.bet_in_round
                self.last_raiser = self.current_player_idx
                self.raises_this_round += 1
                for p in self.players:
                    if p != player:
                        p.actions_this_round = 0
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

        # Broadcast action to all clients
        if self.network_server:
            self.network_server.broadcast_action(
                self.current_player_idx, player.name, action, amount, self.pot
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

    # --- Network Event Handlers (Client) ---

    def _on_disconnected_from_server(self):
        """Handle disconnection from server."""
        QMessageBox.warning(self, "Disconnected", "Lost connection to the server.")
        self._disconnect_network()

    def _on_hole_cards_received(self, cards: list):
        """Handle receiving our hole cards."""
        if self.my_seat is not None:
            # Convert string cards to eval7 cards
            player = self.players[self.my_seat]
            player.hand = [eval7.Card(c) for c in cards]
            self.update_all_panels()

    def _on_community_cards_received(self, cards: list, street: str):
        """Handle receiving community cards."""
        self.board = [eval7.Card(c) for c in cards]
        self.table.set_board(self.board)
        # Track street index for Theory of Mind
        street_map = {"Flop": 1, "Turn": 2, "River": 3}
        if street in street_map:
            self.street_idx = street_map[street]
        # Reset bet_in_round for new street
        for p in self.players:
            p.bet_in_round = 0
        self.current_bet = 0
        self.action_log = []
        self.log_action(f"--- {street} ---")
        self.update_all_panels()

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
        elif action_lower == 'all-in':
            player.stack = 0

        self.table.set_pot(pot)

        # Highlight the player who just acted
        self.set_active_player(seat)

        # Log the action (triggers Theory of Mind update and action history)
        action_text = f"{player_name} {action}" + (f" ${amount:.0f}" if amount > 0 else "")
        self.log_action(action_text)
        self.update_all_panels()
        self.table.update()

    def _on_active_player_changed(self, seat: int):
        """Handle active player broadcast from server."""
        self.set_active_player(seat)

    def _on_hand_started(self, hand_num: int, button: int, blinds: tuple, stacks: dict):
        """Handle new hand start from server."""
        self.hand_number = hand_num
        self.dealer_idx = button
        self.pot = blinds[0] + blinds[1]
        self.board = []
        self.action_log = []
        self.street_idx = 0
        self.action_history = []
        self.current_bet = 0

        # Reset bet_in_round for all players
        for p in self.players:
            p.bet_in_round = 0

        # Update stacks
        for seat, stack in stacks.items():
            self.players[seat].stack = stack
            self.players[seat].active = True
            self.players[seat].hand = None

        self.update_all_panels()
        self.table.set_board([])
        self.table.set_pot(self.pot)
        self.log_action(f"Hand #{hand_num} starting...")

    def _on_hand_ended(self, winners: list, pot: float, shown_hands: dict, hand_summary: dict = None):
        """Handle hand end from server."""
        # Show results
        winner_names = [self.players[w].name for w in winners]
        self.update_status(f"Winners: {', '.join(winner_names)} - Pot: ${pot:.0f}")

        # Show revealed hands
        for seat, cards in shown_hands.items():
            self.players[seat].hand = [eval7.Card(c) for c in cards]

        self.update_all_panels()

        # Show hand summary dialog if server sent the data
        if hand_summary:
            try:
                street_stats = {}
                for street, stats_list in hand_summary.get('street_stats', {}).items():
                    street_stats[street] = [tuple(s) for s in stats_list]
                street_actions = hand_summary.get('street_actions', {})
                board_by_street = hand_summary.get('board_by_street', {})
                player_results = hand_summary.get('player_results', {})
                # Convert player_results values from lists to tuples
                for k, v in player_results.items():
                    if isinstance(v, list):
                        player_results[k] = tuple(v)
                player_hands = hand_summary.get('player_hands', {})
                made_hands_by_street = hand_summary.get('made_hands_by_street', {})

                if street_stats:
                    dialog = HandSummaryDialog(
                        street_stats=street_stats,
                        street_actions=street_actions,
                        board_by_street=board_by_street,
                        player_results=player_results,
                        player_hands=player_hands,
                        made_hands_by_street=made_hands_by_street,
                        parent=self
                    )
                    dialog.setModal(False)
                    dialog.show()  # Non-blocking to avoid disrupting heartbeats
            except Exception as e:
                print(f"Error showing hand summary on client: {e}")

    def enable_action_buttons(self, to_call: float, min_raise: float, max_raise: float):
        """Enable appropriate action buttons for network play."""
        player = self.players[self.my_seat] if self.my_seat is not None else None
        if not player:
            return

        # Enable/disable buttons based on valid actions
        can_check = to_call == 0
        can_call = to_call > 0 and player.stack >= to_call
        can_raise = player.stack > to_call

        self.fold_btn.setEnabled(True)
        self.call_btn.setEnabled(can_call or can_check)
        self.raise_btn.setEnabled(can_raise)

        if can_check:
            self.call_btn.setText("Check")
        elif can_call:
            self.call_btn.setText(f"Call ${to_call:.0f}")
        else:
            self.call_btn.setText("Call")

        # Also enable ToM buttons if visible
        self.tom_fold_btn.setEnabled(True)
        self.tom_call_btn.setEnabled(can_call or can_check)
        self.tom_raise_btn.setEnabled(can_raise)
        self.tom_call_btn.setText(self.call_btn.text())

    def send_network_action(self, action: str, amount: float = 0):
        """Send an action to the server (client mode)."""
        if self.network_client and self.network_mode == "client":
            self.network_client.send_action(action, amount)
            self.waiting_for_human = False
            self.disable_human_actions()


# --- Text Mode Utilities ---

def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system('cls' if os.name == 'nt' else 'clear')


def check_resolution():
    """Check if screen resolution is adequate for GUI mode.
    Returns (width, height) or (0, 0) if unable to detect.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QGuiApplication

        temp_app = QApplication.instance()
        if temp_app is None:
            temp_app = QApplication([])

        screen = QGuiApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            return geometry.width(), geometry.height()
    except Exception:
        pass

    # Fallback: try xrandr on Linux
    try:
        import subprocess
        result = subprocess.run(['xrandr'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if '*' in line:
                parts = line.split()
                for part in parts:
                    if 'x' in part and part[0].isdigit():
                        w, h = part.split('x')
                        return int(w), int(h.split('+')[0].split('_')[0])
    except Exception:
        pass

    return 0, 0


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

        # Initialize players (same as PokerWindow)
        self.players = [
            Player("Hero (You)", "human"),
            Player("Optimal Olivia", "optimal"),
            Player("Tight Tim", "tight"),
            Player("Loose Bruce", "loose"),
            Player("Aggro Angela", "aggressive"),
            Player("Fluid Fiona", "tom")
        ]

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
    app = QApplication(sys.argv)

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

    args = parser.parse_args()

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
