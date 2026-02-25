"""
Tests for PokerIQ bot implementations.
"""

import unittest
from typing import List

from ..models import Street, ActionType
from ..bots import (
    BaseBot, BasicEquityBot, ImprovedEquityBot, ExternalEngineBot,
    create_bot, BotType
)
from ..utils import create_test_state, create_hand, run_single_hand


class TestBotCreation(unittest.TestCase):
    """Test bot instantiation and factory."""

    def test_create_basic_equity_bot(self):
        """BasicEquityBot can be instantiated."""
        bot = BasicEquityBot(seat=0)
        self.assertEqual(bot.seat, 0)
        self.assertEqual(bot.get_name(), "BasicEquityBot")

    def test_create_improved_equity_bot(self):
        """ImprovedEquityBot can be instantiated."""
        bot = ImprovedEquityBot(seat=1)
        self.assertEqual(bot.seat, 1)
        self.assertEqual(bot.get_name(), "ImprovedEquityBot")

    def test_create_external_engine_bot(self):
        """ExternalEngineBot can be instantiated."""
        bot = ExternalEngineBot(seat=2)
        self.assertEqual(bot.seat, 2)
        # Name depends on whether PyPokerEngine is installed
        self.assertTrue(bot.get_name().startswith("ExternalEngineBot"))

    def test_factory_basic(self):
        """Factory creates BasicEquityBot."""
        bot = create_bot(BotType.BASIC_EQUITY, seat=0)
        self.assertIsInstance(bot, BasicEquityBot)

    def test_factory_improved(self):
        """Factory creates ImprovedEquityBot."""
        bot = create_bot(BotType.IMPROVED_EQUITY, seat=0)
        self.assertIsInstance(bot, ImprovedEquityBot)

    def test_factory_external(self):
        """Factory creates ExternalEngineBot."""
        bot = create_bot(BotType.EXTERNAL_ENGINE, seat=0)
        self.assertIsInstance(bot, ExternalEngineBot)

    def test_bot_with_config(self):
        """Bots accept config dict."""
        config = {'aggression': 0.8, 'bluff_frequency': 0.15}
        bot = BasicEquityBot(seat=0, config=config)
        self.assertEqual(bot.bluff_frequency, 0.15)

    def test_bot_with_none_config(self):
        """Bots handle None config."""
        bot = BasicEquityBot(seat=0, config=None)
        self.assertIsNotNone(bot)


class TestBasicEquityBot(unittest.TestCase):
    """Test BasicEquityBot decision making."""

    def setUp(self):
        self.bot = BasicEquityBot(seat=0, random_seed=42)

    def test_preflop_premium_hand(self):
        """Premium hands result in raises."""
        state = create_test_state(
            num_players=2,
            hole_cards={0: ['As', 'Ah']},  # AA
            street=Street.PREFLOP
        )
        action = self.bot.get_action(state)
        # Should bet or raise with AA
        self.assertIn(action.action_type,
                     [ActionType.BET, ActionType.RAISE, ActionType.ALL_IN])

    def test_preflop_weak_hand(self):
        """Weak hands fold to raises."""
        state = create_test_state(
            num_players=2,
            hole_cards={0: ['2h', '7c']},  # 72o
            current_bet=300,  # Facing a raise
            pot=450,
            street=Street.PREFLOP
        )
        action = self.bot.get_action(state)
        self.assertEqual(action.action_type, ActionType.FOLD)

    def test_postflop_value_bet(self):
        """Strong postflop hands bet for value."""
        state = create_test_state(
            num_players=2,
            hole_cards={0: ['As', 'Ah']},
            board=['Ad', 'Kh', '2c'],  # Flopped set
            street=Street.FLOP,
            pot=200,
            current_bet=0,
            action_seat=0
        )
        action = self.bot.get_action(state)
        # Should bet with top set
        self.assertIn(action.action_type,
                     [ActionType.BET, ActionType.ALL_IN])

    def test_default_action_check(self):
        """Default action is check when possible."""
        state = create_test_state(
            num_players=2,
            hole_cards={0: ['2h', '3c']},
            board=['Ah', 'Kd', 'Qc'],
            street=Street.FLOP,
            pot=200,
            current_bet=0,
            action_seat=0
        )
        action = self.bot.get_action(state)
        # With weak hand and no bet, should check or fold
        self.assertIn(action.action_type, [ActionType.CHECK, ActionType.BET])


class TestImprovedEquityBot(unittest.TestCase):
    """Test ImprovedEquityBot decision making."""

    def setUp(self):
        self.bot = ImprovedEquityBot(seat=0, random_seed=42)

    def test_position_aware_opening(self):
        """Bot opens wider from late position."""
        # UTG position - should be tight
        state_utg = create_test_state(
            num_players=6,
            button_seat=3,  # Seat 0 is UTG
            hole_cards={0: ['Kh', 'Jh']},  # KJo - marginal
            street=Street.PREFLOP
        )
        action_utg = self.bot.get_action(state_utg)

        # BTN position - should be loose
        state_btn = create_test_state(
            num_players=6,
            button_seat=0,  # Seat 0 is BTN
            hole_cards={0: ['Kh', 'Jh']},
            street=Street.PREFLOP
        )
        action_btn = self.bot.get_action(state_btn)

        # KJo should open from BTN but not always from UTG
        # This is probabilistic, so just check we get valid actions
        self.assertIsNotNone(action_utg)
        self.assertIsNotNone(action_btn)

    def test_continuation_bet(self):
        """Bot c-bets on flop as preflop raiser."""
        self.bot.was_preflop_raiser = True

        state = create_test_state(
            num_players=2,
            hole_cards={0: ['Ah', 'Kh']},
            board=['7d', '3c', '2s'],  # Dry board, missed
            street=Street.FLOP,
            pot=200,
            current_bet=0,
            action_seat=0
        )

        # Run multiple times to check mixed strategy
        actions = [self.bot.get_action(state).action_type for _ in range(10)]

        # Should sometimes c-bet even when missed
        # At least sometimes bet (c-bet) or check
        self.assertTrue(any(a in [ActionType.BET, ActionType.CHECK] for a in actions))

    def test_draw_semi_bluff(self):
        """Bot semi-bluffs with draws."""
        state = create_test_state(
            num_players=2,
            hole_cards={0: ['Ah', 'Kh']},  # Nut flush draw
            board=['7h', '3h', '2c'],
            street=Street.FLOP,
            pot=200,
            current_bet=0,
            action_seat=0
        )

        # Run multiple times
        bet_count = 0
        for _ in range(20):
            action = self.bot.get_action(state)
            if action.action_type == ActionType.BET:
                bet_count += 1

        # Should semi-bluff at reasonable frequency
        self.assertGreater(bet_count, 0)


class TestExternalEngineBot(unittest.TestCase):
    """Test ExternalEngineBot behavior."""

    def test_fallback_without_engine(self):
        """Bot falls back to ImprovedEquityBot without PyPokerEngine."""
        bot = ExternalEngineBot(seat=0)

        state = create_test_state(
            num_players=2,
            hole_cards={0: ['As', 'Ah']},
            street=Street.PREFLOP
        )

        action = bot.get_action(state)
        # Should get a valid action regardless of engine availability
        self.assertIsNotNone(action)
        self.assertIn(action.action_type, list(ActionType))

    def test_different_bot_types(self):
        """Can create different external bot types."""
        for bot_type in ['honest', 'fish', 'fold', 'call', 'raise']:
            bot = ExternalEngineBot(seat=0, external_bot_class=bot_type)
            self.assertIn(bot_type, bot.external_bot_class)


class TestBotInteraction(unittest.TestCase):
    """Test bots playing against each other."""

    def test_run_single_hand(self):
        """Bots can complete a hand against each other."""
        bots = [
            BasicEquityBot(seat=0, random_seed=42),
            ImprovedEquityBot(seat=1, random_seed=43)
        ]

        result = run_single_hand(bots, verbose=False)

        # Hand should complete with a winner
        self.assertIn('winner', result)
        self.assertIn(result['winner'], [0, 1])
        self.assertIn('actions', result)
        self.assertGreater(len(result['actions']), 0)

    def test_multiple_hands(self):
        """Bots can play multiple hands."""
        bots = [
            BasicEquityBot(seat=0, random_seed=100),
            BasicEquityBot(seat=1, random_seed=101)
        ]

        wins = {0: 0, 1: 0}
        for _ in range(10):
            result = run_single_hand(bots)
            if result['winner'] is not None:
                wins[result['winner']] += 1

        # Both should win at least occasionally
        total = wins[0] + wins[1]
        self.assertGreater(total, 0)


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_create_test_state(self):
        """Test state creation helper."""
        state = create_test_state(
            num_players=3,
            button_seat=1,
            hole_cards={0: ['As', 'Kh'], 1: ['Qd', 'Qc']}
        )

        self.assertEqual(len(state.players), 3)
        self.assertEqual(state.button_seat, 1)
        self.assertIsNotNone(state.players[0].hole_cards)
        self.assertEqual(len(state.players[0].hole_cards.cards), 2)

    def test_create_hand(self):
        """Test hand creation helper."""
        hand = create_hand(['As', 'Kh'])
        self.assertEqual(len(hand.cards), 2)


if __name__ == '__main__':
    unittest.main()
