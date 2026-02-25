#!/usr/bin/env python3
"""
Simple demonstration of PokerIQ bots.

Shows how to:
1. Create different bot types
2. Set up a game state
3. Get bot decisions
4. Run simulated hands
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from poker_iq.models import Street, ActionType
from poker_iq.bots import (
    BasicEquityBot, ImprovedEquityBot, ExternalEngineBot,
    create_bot, BotType
)
from poker_iq.utils import create_test_state, run_single_hand


def demo_basic_decisions():
    """Show basic bot decision making."""
    print("=" * 60)
    print("DEMO: Basic Bot Decisions")
    print("=" * 60)

    # Create bots
    basic_bot = BasicEquityBot(seat=0, verbose=True)
    improved_bot = ImprovedEquityBot(seat=0, verbose=True)

    # Test scenario: Premium hand preflop
    print("\n--- Scenario 1: Premium Hand (AA) Preflop ---")
    state = create_test_state(
        num_players=2,
        hole_cards={0: ['As', 'Ah']},
        street=Street.PREFLOP
    )

    print(f"\nBasicEquityBot with AA:")
    action = basic_bot.get_action(state)
    print(f"  Action: {action.action_type.name} {action.amount or ''}")

    print(f"\nImprovedEquityBot with AA:")
    action = improved_bot.get_action(state)
    print(f"  Action: {action.action_type.name} {action.amount or ''}")

    # Test scenario: Weak hand facing raise
    print("\n--- Scenario 2: Weak Hand (72o) vs Raise ---")
    state = create_test_state(
        num_players=2,
        hole_cards={0: ['7d', '2c']},
        street=Street.PREFLOP,
        current_bet=300,
        pot=450
    )

    print(f"\nBasicEquityBot with 72o facing 3x raise:")
    action = basic_bot.get_action(state)
    print(f"  Action: {action.action_type.name}")

    # Test scenario: Postflop with made hand
    print("\n--- Scenario 3: Top Pair on Flop ---")
    state = create_test_state(
        num_players=2,
        hole_cards={0: ['Ah', 'Kd']},
        board=['As', '7c', '2h'],
        street=Street.FLOP,
        pot=200,
        current_bet=0,
        action_seat=0
    )

    print(f"\nImprovedEquityBot with AK on A72 board:")
    action = improved_bot.get_action(state)
    print(f"  Action: {action.action_type.name} {action.amount or ''}")

    # Test scenario: Draw on flop
    print("\n--- Scenario 4: Flush Draw ---")
    state = create_test_state(
        num_players=2,
        hole_cards={0: ['Ah', 'Kh']},
        board=['7h', '3h', '2c'],
        street=Street.FLOP,
        pot=200,
        current_bet=0,
        action_seat=0
    )

    print(f"\nImprovedEquityBot with nut flush draw:")
    action = improved_bot.get_action(state)
    print(f"  Action: {action.action_type.name} {action.amount or ''}")


def demo_bot_match():
    """Run bots against each other."""
    print("\n" + "=" * 60)
    print("DEMO: Bot vs Bot Match (10 hands)")
    print("=" * 60)

    # Create bots
    bot1 = BasicEquityBot(seat=0, random_seed=42)
    bot2 = ImprovedEquityBot(seat=1, random_seed=43)

    wins = {0: 0, 1: 0}

    for hand_num in range(1, 11):
        print(f"\n--- Hand {hand_num} ---")
        result = run_single_hand([bot1, bot2], verbose=True)

        if result['winner'] is not None:
            wins[result['winner']] += 1
            winner_name = "BasicEquityBot" if result['winner'] == 0 else "ImprovedEquityBot"
            print(f"Winner: {winner_name}")
        else:
            print("No winner (split pot or error)")

        print(f"Board: {result['board']}")

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"BasicEquityBot wins: {wins[0]}")
    print(f"ImprovedEquityBot wins: {wins[1]}")


def demo_external_engine():
    """Demo external engine bot (with fallback)."""
    print("\n" + "=" * 60)
    print("DEMO: External Engine Bot")
    print("=" * 60)

    # Try different external bot types
    for bot_type in ['honest', 'fish', 'call']:
        print(f"\n--- External Bot Type: {bot_type} ---")
        bot = ExternalEngineBot(seat=0, external_bot_class=bot_type, verbose=True)
        print(f"Bot name: {bot.get_name()}")

        state = create_test_state(
            num_players=2,
            hole_cards={0: ['Kd', 'Qd']},
            street=Street.PREFLOP
        )

        action = bot.get_action(state)
        print(f"Action with KQs preflop: {action.action_type.name} {action.amount or ''}")


def demo_factory():
    """Demo the bot factory function."""
    print("\n" + "=" * 60)
    print("DEMO: Bot Factory")
    print("=" * 60)

    for bot_type in BotType:
        bot = create_bot(bot_type, seat=0)
        print(f"{bot_type.name}: {bot.get_name()}")


def main():
    """Run all demos."""
    print("\n" + "#" * 60)
    print("#" + " " * 20 + "PokerIQ Bot Demo" + " " * 22 + "#")
    print("#" * 60)

    demo_basic_decisions()
    demo_bot_match()
    demo_external_engine()
    demo_factory()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
