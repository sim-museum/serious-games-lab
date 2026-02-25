"""
Data models for PokerIQ Texas Hold'em.

Provides Card, Hand, GameState, Action, and related classes.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Optional, Tuple, Dict, Any
import random


class Suit(IntEnum):
    """Card suits (ordered for evaluation)"""
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3

    def __str__(self) -> str:
        return ['c', 'd', 'h', 's'][self.value]

    @classmethod
    def from_char(cls, c: str) -> 'Suit':
        mapping = {'c': cls.CLUBS, 'd': cls.DIAMONDS,
                   'h': cls.HEARTS, 's': cls.SPADES,
                   'C': cls.CLUBS, 'D': cls.DIAMONDS,
                   'H': cls.HEARTS, 'S': cls.SPADES}
        return mapping[c]


class Rank(IntEnum):
    """Card ranks (2-14, where 14=Ace)"""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self) -> str:
        if self.value <= 10:
            return str(self.value) if self.value != 10 else 'T'
        return {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}[self.value]

    @classmethod
    def from_char(cls, c: str) -> 'Rank':
        if c.isdigit():
            return cls(int(c))
        mapping = {'T': cls.TEN, 't': cls.TEN,
                   'J': cls.JACK, 'j': cls.JACK,
                   'Q': cls.QUEEN, 'q': cls.QUEEN,
                   'K': cls.KING, 'k': cls.KING,
                   'A': cls.ACE, 'a': cls.ACE}
        return mapping[c]


@dataclass(frozen=True)
class Card:
    """
    Immutable card representation.

    Attributes:
        rank: Card rank (2-14)
        suit: Card suit (0-3)
    """
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self})"

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def __lt__(self, other: 'Card') -> bool:
        if self.rank != other.rank:
            return self.rank < other.rank
        return self.suit < other.suit

    @classmethod
    def from_str(cls, s: str) -> 'Card':
        """Parse card from string like 'Ah', 'Ks', '2c'"""
        s = s.strip()
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")
        return cls(Rank.from_char(s[0]), Suit.from_char(s[1]))

    @classmethod
    def from_code(cls, code: int) -> 'Card':
        """Create card from 0-51 code"""
        return cls(Rank(code // 4 + 2), Suit(code % 4))

    def to_code(self) -> int:
        """Convert to 0-51 code"""
        return (self.rank.value - 2) * 4 + self.suit.value


@dataclass
class Hand:
    """
    Collection of cards (hole cards or full hand).
    """
    cards: List[Card] = field(default_factory=list)

    def __str__(self) -> str:
        return ' '.join(str(c) for c in sorted(self.cards, reverse=True))

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self):
        return iter(self.cards)

    def add(self, card: Card) -> None:
        self.cards.append(card)

    @classmethod
    def from_str(cls, s: str) -> 'Hand':
        """Parse hand from string like 'Ah Ks' or 'AhKs'"""
        s = s.strip().replace(' ', '')
        cards = []
        for i in range(0, len(s), 2):
            cards.append(Card.from_str(s[i:i+2]))
        return cls(cards)


class Position(IntEnum):
    """Table positions (0=BTN is dealer)"""
    BTN = 0   # Button (dealer)
    SB = 1    # Small blind
    BB = 2    # Big blind
    UTG = 3   # Under the gun
    UTG1 = 4
    MP = 5    # Middle position
    MP1 = 6
    CO = 7   # Cutoff

    @classmethod
    def from_seat(cls, seat: int, btn_seat: int, num_players: int) -> 'Position':
        """Calculate position from seat index and button position"""
        relative = (seat - btn_seat) % num_players
        if num_players <= 3:
            # Heads-up or 3-handed
            return cls(relative)
        # Map to standard positions
        positions = [cls.BTN, cls.SB, cls.BB, cls.UTG, cls.UTG1, cls.MP, cls.MP1, cls.CO]
        return positions[min(relative, len(positions) - 1)]

    def is_early(self) -> bool:
        """Early position (tighter ranges)"""
        return self.value >= 3 and self.value <= 4

    def is_middle(self) -> bool:
        """Middle position"""
        return self.value >= 5 and self.value <= 6

    def is_late(self) -> bool:
        """Late position (wider ranges)"""
        return self.value <= 2 or self.value >= 7


class Street(IntEnum):
    """Betting rounds"""
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4


class ActionType(Enum):
    """Possible player actions"""
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class Action:
    """
    A player action with optional amount.
    """
    action_type: ActionType
    amount: int = 0

    def __str__(self) -> str:
        if self.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            return f"{self.action_type.value} {self.amount}"
        return self.action_type.value

    @classmethod
    def fold(cls) -> 'Action':
        return cls(ActionType.FOLD)

    @classmethod
    def check(cls) -> 'Action':
        return cls(ActionType.CHECK)

    @classmethod
    def call(cls, amount: int = 0) -> 'Action':
        return cls(ActionType.CALL, amount)

    @classmethod
    def bet(cls, amount: int) -> 'Action':
        return cls(ActionType.BET, amount)

    @classmethod
    def raise_to(cls, amount: int) -> 'Action':
        return cls(ActionType.RAISE, amount)

    @classmethod
    def all_in(cls, amount: int) -> 'Action':
        return cls(ActionType.ALL_IN, amount)


@dataclass
class PlayerState:
    """
    State of a single player in the game.
    """
    seat: int
    stack: int
    hole_cards: Optional[Hand] = None
    is_active: bool = True  # Still in hand
    is_all_in: bool = False
    current_bet: int = 0  # Bet in current street
    total_invested: int = 0  # Total chips put in pot

    def reset_street(self) -> None:
        """Reset for new betting round"""
        self.current_bet = 0


@dataclass
class GameState:
    """
    Complete state of a Texas Hold'em hand.

    Contains all information needed for bot decision-making:
    - Player states (stacks, bets, hole cards)
    - Community cards
    - Pot size and betting history
    - Current action position
    """
    # Table setup
    num_players: int
    button_seat: int
    small_blind: int
    big_blind: int

    # Players
    players: List[PlayerState] = field(default_factory=list)

    # Cards
    board: List[Card] = field(default_factory=list)

    # Betting state
    street: Street = Street.PREFLOP
    pot: int = 0
    current_bet: int = 0  # Highest bet in current street
    min_raise: int = 0  # Minimum raise amount

    # Action tracking
    action_seat: int = 0  # Who's turn
    last_aggressor: Optional[int] = None
    actions_this_street: List[Tuple[int, Action]] = field(default_factory=list)

    # Hand complete flag
    is_complete: bool = False

    def __post_init__(self):
        if not self.players:
            # Initialize players with default stacks
            for i in range(self.num_players):
                self.players.append(PlayerState(
                    seat=i,
                    stack=100 * self.big_blind  # Default 100BB
                ))

    @property
    def hero_seat(self) -> int:
        """Get the hero (human/first player) seat"""
        return 0

    def get_hero(self) -> PlayerState:
        """Get hero player state"""
        return self.players[self.hero_seat]

    def get_current_player(self) -> PlayerState:
        """Get player whose turn it is"""
        return self.players[self.action_seat]

    def get_position(self, seat: int) -> Position:
        """Get position for a seat"""
        return Position.from_seat(seat, self.button_seat, self.num_players)

    def get_to_call(self, seat: int) -> int:
        """Amount player needs to call"""
        player = self.players[seat]
        return max(0, self.current_bet - player.current_bet)

    def get_effective_stack(self, seat: int) -> int:
        """Effective stack for decisions"""
        player = self.players[seat]
        return player.stack + player.current_bet

    def get_pot_odds(self, seat: int) -> float:
        """
        Calculate pot odds for calling.
        Returns ratio: amount_to_call / (pot + amount_to_call)
        """
        to_call = self.get_to_call(seat)
        if to_call == 0:
            return 0.0
        total_pot = self.pot + to_call
        return to_call / total_pot

    def get_legal_actions(self, seat: int) -> List[Action]:
        """Get all legal actions for a player"""
        player = self.players[seat]
        actions = []

        if not player.is_active or player.is_all_in:
            return actions

        to_call = self.get_to_call(seat)

        # Fold is always legal if there's a bet to call
        if to_call > 0:
            actions.append(Action.fold())

        # Check is legal if no bet to call
        if to_call == 0:
            actions.append(Action.check())

        # Call is legal if there's a bet and we have chips
        if to_call > 0 and player.stack > 0:
            call_amount = min(to_call, player.stack)
            actions.append(Action.call(call_amount))

        # Bet is legal if no current bet and we have chips
        if self.current_bet == 0 and player.stack > 0:
            min_bet = self.big_blind
            if player.stack <= min_bet:
                actions.append(Action.all_in(player.stack))
            else:
                actions.append(Action.bet(min_bet))
                # Also allow larger bets
                for mult in [2, 3]:
                    bet_size = min_bet * mult
                    if bet_size < player.stack:
                        actions.append(Action.bet(bet_size))
                actions.append(Action.all_in(player.stack))

        # Raise is legal if there's a bet and we can raise
        if self.current_bet > 0 and player.stack > to_call:
            min_raise_to = self.current_bet + max(self.min_raise, self.big_blind)
            if player.stack + player.current_bet >= min_raise_to:
                actions.append(Action.raise_to(min_raise_to))
                # Also allow larger raises
                for mult in [1.5, 2, 3]:
                    raise_to = int(self.current_bet * mult)
                    if raise_to > min_raise_to and raise_to < player.stack + player.current_bet:
                        actions.append(Action.raise_to(raise_to))
                actions.append(Action.all_in(player.stack + player.current_bet))

        return actions

    def active_players(self) -> List[PlayerState]:
        """Get list of players still in the hand"""
        return [p for p in self.players if p.is_active]

    def players_in_pot(self) -> int:
        """Count of active players"""
        return len(self.active_players())

    def copy(self) -> 'GameState':
        """Create a deep copy of the game state"""
        import copy
        return copy.deepcopy(self)

    @classmethod
    def create_hand(
        cls,
        num_players: int = 6,
        button_seat: int = 0,
        small_blind: int = 1,
        big_blind: int = 2,
        stacks: Optional[List[int]] = None
    ) -> 'GameState':
        """Create a new hand with given parameters"""
        state = cls(
            num_players=num_players,
            button_seat=button_seat,
            small_blind=small_blind,
            big_blind=big_blind
        )

        if stacks:
            for i, stack in enumerate(stacks):
                if i < len(state.players):
                    state.players[i].stack = stack

        # Post blinds
        sb_seat = (button_seat + 1) % num_players
        bb_seat = (button_seat + 2) % num_players

        state.players[sb_seat].current_bet = small_blind
        state.players[sb_seat].stack -= small_blind
        state.players[sb_seat].total_invested = small_blind

        state.players[bb_seat].current_bet = big_blind
        state.players[bb_seat].stack -= big_blind
        state.players[bb_seat].total_invested = big_blind

        state.pot = small_blind + big_blind
        state.current_bet = big_blind
        state.min_raise = big_blind

        # Action starts UTG (after BB)
        state.action_seat = (bb_seat + 1) % num_players

        return state

    def deal_hole_cards(self, deck: Optional[List[Card]] = None) -> List[Card]:
        """Deal hole cards to all players"""
        if deck is None:
            deck = [Card.from_code(i) for i in range(52)]
            random.shuffle(deck)

        for player in self.players:
            player.hole_cards = Hand([deck.pop(), deck.pop()])

        return deck

    def deal_flop(self, deck: List[Card]) -> List[Card]:
        """Deal the flop"""
        deck.pop()  # Burn
        self.board.extend([deck.pop(), deck.pop(), deck.pop()])
        self.street = Street.FLOP
        self._reset_street_betting()
        return deck

    def deal_turn(self, deck: List[Card]) -> List[Card]:
        """Deal the turn"""
        deck.pop()  # Burn
        self.board.append(deck.pop())
        self.street = Street.TURN
        self._reset_street_betting()
        return deck

    def deal_river(self, deck: List[Card]) -> List[Card]:
        """Deal the river"""
        deck.pop()  # Burn
        self.board.append(deck.pop())
        self.street = Street.RIVER
        self._reset_street_betting()
        return deck

    def _reset_street_betting(self) -> None:
        """Reset betting state for new street"""
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.actions_this_street.clear()
        for player in self.players:
            player.reset_street()
        # Action starts from first active player after button
        for i in range(1, self.num_players + 1):
            seat = (self.button_seat + i) % self.num_players
            if self.players[seat].is_active and not self.players[seat].is_all_in:
                self.action_seat = seat
                break


def create_deck() -> List[Card]:
    """Create a shuffled 52-card deck"""
    deck = [Card.from_code(i) for i in range(52)]
    random.shuffle(deck)
    return deck
