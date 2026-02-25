"""
Constants and configuration for PokerIQ bots.

Contains:
- Preflop hand rankings and opening ranges by position
- Postflop betting thresholds
- Bot configuration parameters
"""

from enum import Enum
from typing import Dict, List, Set, Tuple


class BotType(Enum):
    """Available bot types"""
    BASIC_EQUITY = "basic_equity"
    IMPROVED_EQUITY = "improved_equity"
    EXTERNAL_ENGINE = "external_engine"


# ============================================================================
# PREFLOP HAND RANKINGS
# ============================================================================

# Premium hands (always raise/reraise)
PREMIUM_HANDS = {'AA', 'KK', 'QQ', 'AKs', 'AKo'}

# Strong hands (raise, call 3-bets with best ones)
STRONG_HANDS = {
    'JJ', 'TT', 'AQs', 'AQo', 'AJs', 'KQs',
    '99', '88', 'ATs', 'KJs', 'QJs', 'JTs'
}

# Playable hands (position-dependent)
PLAYABLE_HANDS = {
    # Broadway
    'AJo', 'ATo', 'KQo', 'KJo', 'KTo', 'QJo', 'QTo', 'JTo',
    # Suited aces
    'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s',
    # Suited kings
    'KTs', 'K9s', 'K8s', 'K7s', 'K6s', 'K5s',
    # Suited queens
    'Q9s', 'Q8s',
    # Suited connectors
    'T9s', '98s', '87s', '76s', '65s', '54s',
    # Pairs
    '77', '66', '55', '44', '33', '22',
    # Suited one-gappers
    'T8s', '97s', '86s', '75s', '64s', '53s',
}

# Speculative hands (only play in late position, multi-way pots)
SPECULATIVE_HANDS = {
    # Suited connectors (lower)
    '43s', '32s',
    # Suited aces (already in playable)
    # Small pairs (already in playable)
    # Suited one-gappers (already in playable)
}


def canonicalize_hand(card1: str, card2: str) -> str:
    """
    Convert two cards to canonical hand notation.
    Example: Ah, Ks -> AKs; Kd, Ac -> AKo
    """
    # Extract ranks
    r1, s1 = card1[0], card1[1]
    r2, s2 = card2[0], card2[1]

    # Order ranks (higher first)
    rank_order = '23456789TJQKA'
    if rank_order.index(r1) < rank_order.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1

    # Suited or offsuit
    suited = 's' if s1 == s2 else 'o'

    # Pairs don't have s/o suffix
    if r1 == r2:
        return f"{r1}{r2}"

    return f"{r1}{r2}{suited}"


# ============================================================================
# OPENING RANGES BY POSITION
# ============================================================================

# Percentage of hands to open from each position (6-max)
OPEN_RANGE_PCT = {
    'UTG': 0.12,    # ~12% (tight)
    'UTG1': 0.14,   # ~14%
    'MP': 0.18,     # ~18%
    'MP1': 0.20,    # ~20%
    'CO': 0.27,     # ~27%
    'BTN': 0.40,    # ~40% (wide)
    'SB': 0.35,     # ~35% (vs BB only)
}

# Opening ranges by position (hands to open-raise)
OPEN_RANGES: Dict[str, Set[str]] = {
    'UTG': PREMIUM_HANDS | {'JJ', 'TT', 'AQs', 'AQo', 'AJs', 'KQs'},
    'UTG1': PREMIUM_HANDS | STRONG_HANDS - {'88', 'QJs', 'JTs'},
    'MP': PREMIUM_HANDS | STRONG_HANDS,
    'MP1': PREMIUM_HANDS | STRONG_HANDS | {'77', 'A9s', 'KTs', 'QTs', 'J9s', 'T9s'},
    'CO': PREMIUM_HANDS | STRONG_HANDS | {
        '77', '66', 'A9s', 'A8s', 'A5s', 'A4s',
        'KTs', 'K9s', 'QTs', 'Q9s', 'J9s', 'T9s', '98s', '87s',
        'AJo', 'ATo', 'KJo', 'KTo', 'QJo'
    },
    'BTN': PREMIUM_HANDS | STRONG_HANDS | PLAYABLE_HANDS,
    'SB': PREMIUM_HANDS | STRONG_HANDS | {
        '77', '66', '55', 'A9s', 'A8s', 'A7s', 'A5s', 'A4s',
        'KTs', 'K9s', 'QTs', 'Q9s', 'J9s', 'T9s', '98s', '87s', '76s',
        'AJo', 'ATo', 'KJo', 'QJo'
    },
}

# 3-bet ranges (vs open raise)
THREE_BET_RANGES: Dict[str, Set[str]] = {
    'value': {'AA', 'KK', 'QQ', 'AKs', 'AKo', 'JJ'},
    'bluff': {'A5s', 'A4s', 'A3s', '76s', '65s'},  # Blockers + playability
}

# Call 3-bet ranges (hands that can call a 3-bet)
CALL_3BET_RANGE = {
    'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88',
    'AKs', 'AKo', 'AQs', 'AQo', 'AJs',
    'KQs', 'QJs', 'JTs', 'T9s',
}


# ============================================================================
# POSTFLOP STRATEGY THRESHOLDS
# ============================================================================

# Equity thresholds for different actions
EQUITY_THRESHOLDS = {
    # Minimum equity to continue vs bet
    'fold_below': 0.20,

    # Value betting thresholds
    'value_bet_river': 0.70,  # Need 70%+ equity to value bet river
    'value_bet_turn': 0.60,
    'value_bet_flop': 0.55,

    # Check-raise thresholds
    'check_raise_value': 0.70,
    'check_raise_bluff': 0.30,  # With good draw equity

    # Continuation bet
    'cbet_heads_up': 0.45,
    'cbet_multiway': 0.55,

    # Call thresholds (pot odds based)
    'call_if_equity_above_pot_odds': True,
}

# Bet sizing (as fraction of pot)
BET_SIZING = {
    'cbet_dry': 0.33,      # C-bet on dry boards
    'cbet_wet': 0.50,      # C-bet on wet boards
    'cbet_multiway': 0.60, # C-bet multiway

    'value_bet_small': 0.50,
    'value_bet_medium': 0.75,
    'value_bet_large': 1.00,

    'bluff_small': 0.33,
    'bluff_medium': 0.50,
    'bluff_large': 0.75,

    'turn_barrel': 0.66,
    'river_bet': 0.75,
}

# Hand strength categories
HAND_STRENGTH = {
    'monster': 0.90,      # Nuts or near-nuts
    'strong': 0.70,       # Top pair top kicker+
    'medium': 0.50,       # Middle pair, weak top pair
    'weak': 0.30,         # Bottom pair, high card
    'trash': 0.15,        # Nothing
}


# ============================================================================
# DRAW DETECTION
# ============================================================================

# Number of outs for common draws
DRAW_OUTS = {
    'flush_draw': 9,
    'open_ended_straight_draw': 8,
    'gutshot': 4,
    'overcards': 6,      # Two overcards
    'combo_draw': 15,    # Flush + straight draw
}


# ============================================================================
# BOT CONFIGURATION
# ============================================================================

BOT_CONFIGS = {
    BotType.BASIC_EQUITY: {
        'name': 'Basic Equity Bot',
        'description': 'Simple equity + pot odds decision making',
        'aggression': 0.5,
        'bluff_frequency': 0.10,
        'use_position': False,
        'use_ranges': False,
    },
    BotType.IMPROVED_EQUITY: {
        'name': 'Improved Equity Bot',
        'description': 'Position-aware with preflop ranges and postflop heuristics',
        'aggression': 0.6,
        'bluff_frequency': 0.20,
        'use_position': True,
        'use_ranges': True,
        'cbet_frequency': 0.65,
        'check_raise_frequency': 0.08,
        'float_frequency': 0.12,
    },
    BotType.EXTERNAL_ENGINE: {
        'name': 'External Engine Bot',
        'description': 'Uses PyPokerEngine or similar for decisions',
        'fallback_to_improved': True,
    },
}


# ============================================================================
# RANDOM SEED FOR REPRODUCIBILITY
# ============================================================================

DEFAULT_RANDOM_SEED = 42


# ============================================================================
# MIXED STRATEGY PROBABILITIES
# ============================================================================

MIXED_STRATEGIES = {
    # Preflop
    'open_raise_size_2.5x': 0.60,
    'open_raise_size_3x': 0.40,

    # 3-bet
    '3bet_with_value_hand': 0.85,
    '3bet_with_bluff_hand': 0.30,

    # Postflop
    'cbet_when_missed': 0.60,  # C-bet as bluff
    'check_strong_hand': 0.15, # Trap with monsters
    'bet_medium_hand': 0.50,   # Turn medium hands into bluffs sometimes

    # River
    'bluff_river_missed_draw': 0.25,
    'value_bet_thin': 0.70,
}
