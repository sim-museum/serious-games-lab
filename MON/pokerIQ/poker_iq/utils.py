"""
Utility functions for PokerIQ testing and development.
"""

from typing import List, Optional, Dict, Any, Tuple
import random

from .models import (
    GameState, PlayerState, Hand, Card, Suit, Rank,
    Action, ActionType, Street
)
from .bots import BaseBot


def create_card(card_str: str) -> Card:
    """
    Create a Card from string notation.

    Args:
        card_str: Card string like 'As', 'Kh', '2d', 'Tc'
                  (rank + suit, case insensitive)

    Returns:
        Card object
    """
    if len(card_str) != 2:
        raise ValueError(f"Invalid card string: {card_str}")

    rank_char = card_str[0].upper()
    suit_char = card_str[1].lower()

    rank_map = {
        '2': Rank.TWO, '3': Rank.THREE, '4': Rank.FOUR, '5': Rank.FIVE,
        '6': Rank.SIX, '7': Rank.SEVEN, '8': Rank.EIGHT, '9': Rank.NINE,
        'T': Rank.TEN, 'J': Rank.JACK, 'Q': Rank.QUEEN, 'K': Rank.KING, 'A': Rank.ACE
    }

    suit_map = {
        's': Suit.SPADES, 'h': Suit.HEARTS, 'd': Suit.DIAMONDS, 'c': Suit.CLUBS
    }

    if rank_char not in rank_map:
        raise ValueError(f"Invalid rank: {rank_char}")
    if suit_char not in suit_map:
        raise ValueError(f"Invalid suit: {suit_char}")

    return Card(suit=suit_map[suit_char], rank=rank_map[rank_char])


def create_hand(card_strings: List[str]) -> Hand:
    """
    Create a Hand from card strings.

    Args:
        card_strings: List like ['As', 'Kh']

    Returns:
        Hand object
    """
    cards = [create_card(s) for s in card_strings]
    return Hand(cards=cards)


def create_board(card_strings: List[str]) -> List[Card]:
    """
    Create board cards from strings.

    Args:
        card_strings: List like ['Ah', 'Kd', '2c'] for flop

    Returns:
        List of Card objects
    """
    return [create_card(s) for s in card_strings]


def create_test_state(
    num_players: int = 2,
    button_seat: int = 0,
    small_blind: int = 50,
    big_blind: int = 100,
    starting_stack: int = 10000,
    street: Street = Street.PREFLOP,
    hole_cards: Optional[Dict[int, List[str]]] = None,
    board: Optional[List[str]] = None,
    pot: int = 0,
    current_bet: int = 0,
    action_seat: Optional[int] = None,
) -> GameState:
    """
    Create a GameState for testing.

    Args:
        num_players: Number of players (2-10)
        button_seat: Dealer button position
        small_blind: Small blind amount
        big_blind: Big blind amount
        starting_stack: Each player's starting stack
        street: Current street
        hole_cards: Dict mapping seat -> ['As', 'Kh'] hole cards
        board: Board cards like ['Ah', 'Kd', '2c']
        pot: Current pot size
        current_bet: Current bet to call
        action_seat: Seat whose turn it is

    Returns:
        GameState configured for testing
    """
    hole_cards = hole_cards or {}

    # Create players
    players = []
    for seat in range(num_players):
        cards = hole_cards.get(seat)
        hand = create_hand(cards) if cards else None

        player = PlayerState(
            seat=seat,
            stack=starting_stack,
            hole_cards=hand,
            is_active=True,
            current_bet=0
        )
        players.append(player)

    # Calculate pot from blinds if preflop and pot not specified
    if street == Street.PREFLOP and pot == 0:
        pot = small_blind + big_blind
        sb_seat = (button_seat + 1) % num_players
        bb_seat = (button_seat + 2) % num_players
        if num_players == 2:
            # Heads up: button posts SB, other posts BB
            players[button_seat].current_bet = small_blind
            players[button_seat].stack -= small_blind
            bb_seat = (button_seat + 1) % num_players
            players[bb_seat].current_bet = big_blind
            players[bb_seat].stack -= big_blind
        else:
            players[sb_seat].current_bet = small_blind
            players[sb_seat].stack -= small_blind
            players[bb_seat].current_bet = big_blind
            players[bb_seat].stack -= big_blind
        current_bet = big_blind

    # Parse board
    board_cards = create_board(board) if board else []

    # Default action seat
    if action_seat is None:
        if num_players == 2:
            action_seat = button_seat  # Heads up: BTN acts first preflop
        else:
            action_seat = (button_seat + 3) % num_players  # UTG

    return GameState(
        num_players=num_players,
        players=players,
        button_seat=button_seat,
        small_blind=small_blind,
        big_blind=big_blind,
        street=street,
        board=board_cards,
        pot=pot,
        current_bet=current_bet,
        min_raise=big_blind,
        action_seat=action_seat
    )


def run_single_hand(
    bots: List[BaseBot],
    starting_stack: int = 10000,
    small_blind: int = 50,
    big_blind: int = 100,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run a single hand with the given bots.

    Simplified simulation for testing bot behavior.

    Args:
        bots: List of bot instances (one per player)
        starting_stack: Starting stack for each player
        small_blind: Small blind amount
        big_blind: Big blind amount
        verbose: Print actions as they occur

    Returns:
        Dict with hand history and results
    """
    num_players = len(bots)

    # Deal random hole cards
    deck = [Card(suit=s, rank=r) for s in Suit for r in Rank]
    random.shuffle(deck)

    hole_cards = {}
    for i in range(num_players):
        hole_cards[i] = [
            _card_to_str(deck.pop()),
            _card_to_str(deck.pop())
        ]

    # Create initial state
    state = create_test_state(
        num_players=num_players,
        button_seat=0,
        small_blind=small_blind,
        big_blind=big_blind,
        starting_stack=starting_stack,
        hole_cards=hole_cards
    )

    history = {
        'hole_cards': hole_cards,
        'actions': [],
        'board': [],
        'pot': state.pot,
        'winner': None
    }

    # Notify bots of hand start
    for bot in bots:
        bot.on_hand_start(state)

    # Simple action loop
    max_actions = 100  # Safety limit
    action_count = 0

    while action_count < max_actions:
        action_count += 1

        # Check if hand is over
        active_players = [p for p in state.players if p.is_active]
        if len(active_players) <= 1:
            # Only one player left
            winner = active_players[0].seat if active_players else 0
            history['winner'] = winner
            break

        # Get current player's action
        current_bot = bots[state.action_seat]
        action = current_bot.get_action(state)

        history['actions'].append({
            'seat': state.action_seat,
            'action': action.action_type.name,
            'amount': action.amount,
            'street': state.street.name
        })

        if verbose:
            print(f"[{state.street.name}] Seat {state.action_seat}: "
                  f"{action.action_type.name} {action.amount or ''}")

        # Apply action to state
        state = _apply_action(state, action, deck, history)

        if state.street == Street.SHOWDOWN:
            # Simplified: random winner among remaining
            active = [p.seat for p in state.players if p.is_active]
            history['winner'] = random.choice(active)
            break

    # Hand end notification
    result = {'winner': history['winner'], 'pot': state.pot}
    for bot in bots:
        bot.on_hand_end(state, result)

    return history


def _card_to_str(card: Card) -> str:
    """Convert Card to string notation."""
    rank_map = {
        Rank.TWO: '2', Rank.THREE: '3', Rank.FOUR: '4', Rank.FIVE: '5',
        Rank.SIX: '6', Rank.SEVEN: '7', Rank.EIGHT: '8', Rank.NINE: '9',
        Rank.TEN: 'T', Rank.JACK: 'J', Rank.QUEEN: 'Q', Rank.KING: 'K', Rank.ACE: 'A'
    }
    suit_map = {Suit.SPADES: 's', Suit.HEARTS: 'h', Suit.DIAMONDS: 'd', Suit.CLUBS: 'c'}
    return rank_map[card.rank] + suit_map[card.suit]


def _apply_action(
    state: GameState,
    action: Action,
    deck: List[Card],
    history: Dict
) -> GameState:
    """
    Apply an action to the game state.
    Simplified for testing.
    """
    # Create mutable copies
    players = [PlayerState(
        seat=p.seat,
        stack=p.stack,
        hole_cards=p.hole_cards,
        is_active=p.is_active,
        current_bet=p.current_bet
    ) for p in state.players]

    board = list(state.board)
    pot = state.pot
    current_bet = state.current_bet
    min_raise = state.min_raise
    street = state.street

    player = players[state.action_seat]

    if action.action_type == ActionType.FOLD:
        player.is_active = False

    elif action.action_type == ActionType.CHECK:
        pass  # No change

    elif action.action_type == ActionType.CALL:
        call_amount = min(current_bet - player.current_bet, player.stack)
        player.stack -= call_amount
        player.current_bet += call_amount
        pot += call_amount

    elif action.action_type in (ActionType.BET, ActionType.RAISE):
        amount = action.amount or 0
        put_in = amount - player.current_bet
        player.stack -= put_in
        pot += put_in
        if amount > current_bet:
            min_raise = amount - current_bet
        current_bet = amount
        player.current_bet = amount

    elif action.action_type == ActionType.ALL_IN:
        amount = player.stack + player.current_bet
        pot += player.stack
        if amount > current_bet:
            min_raise = amount - current_bet
            current_bet = amount
        player.current_bet = amount
        player.stack = 0

    # Find next active player
    num_players = len(players)
    next_seat = (state.action_seat + 1) % num_players

    # Check if betting round is complete
    active_players = [p for p in players if p.is_active]
    all_matched = all(
        p.current_bet == current_bet or p.stack == 0
        for p in active_players
    )

    # Count how many have acted at this bet level
    if all_matched and len(active_players) > 1:
        # Move to next street
        for p in players:
            p.current_bet = 0
        current_bet = 0

        if street == Street.PREFLOP:
            street = Street.FLOP
            for _ in range(3):
                card = deck.pop()
                board.append(card)
                history['board'].append(_card_to_str(card))
            next_seat = (state.button_seat + 1) % num_players
        elif street == Street.FLOP:
            street = Street.TURN
            card = deck.pop()
            board.append(card)
            history['board'].append(_card_to_str(card))
            next_seat = (state.button_seat + 1) % num_players
        elif street == Street.TURN:
            street = Street.RIVER
            card = deck.pop()
            board.append(card)
            history['board'].append(_card_to_str(card))
            next_seat = (state.button_seat + 1) % num_players
        elif street == Street.RIVER:
            street = Street.SHOWDOWN

    # Find next active player
    for _ in range(num_players):
        if players[next_seat].is_active and players[next_seat].stack > 0:
            break
        next_seat = (next_seat + 1) % num_players

    return GameState(
        num_players=num_players,
        players=players,
        button_seat=state.button_seat,
        small_blind=state.small_blind,
        big_blind=state.big_blind,
        street=street,
        board=board,
        pot=pot,
        current_bet=current_bet,
        min_raise=min_raise,
        action_seat=next_seat
    )


__all__ = [
    'create_card',
    'create_hand',
    'create_board',
    'create_test_state',
    'run_single_hand',
]
