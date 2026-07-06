"""
Enhanced Bidding Rule Data Model for BEN Bridge.

Provides comprehensive data structures for representing bidding systems,
conventions, and bid meanings. Can be populated from:
- HLQ file parsing
- Hardcoded system definitions
- JSON configuration files
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set
from enum import Enum
import re


class RuleContext(Enum):
    """Where in the auction this rule applies"""
    OPENING = "opening"
    RESPONSE = "response"
    REBID = "rebid"
    COMPETITIVE = "competitive"
    DEFENSIVE = "defensive"
    SLAM = "slam"
    ANY = "any"


class ForceLevel(Enum):
    """How forcing is this bid?"""
    SIGNOFF = "signoff"
    NON_FORCING = "non_forcing"
    INVITATIONAL = "invitational"
    FORCING = "forcing"
    GAME_FORCING = "game_forcing"


@dataclass
class SuitRequirement:
    """Requirements for a specific suit"""
    min_length: int = 0
    max_length: int = 13
    min_honors: int = 0  # A=4, K=3, Q=2, J=1, T=0
    requires_stopper: bool = False

    def matches(self, length: int, honors: int = 0, has_stopper: bool = True) -> bool:
        """Check if suit matches requirements"""
        if length < self.min_length or length > self.max_length:
            return False
        if honors < self.min_honors:
            return False
        if self.requires_stopper and not has_stopper:
            return False
        return True


@dataclass
class BidMeaning:
    """Semantic interpretation of a bid"""
    # Point range
    hcp_min: Optional[int] = None
    hcp_max: Optional[int] = None
    total_points_min: Optional[int] = None  # Including distribution
    total_points_max: Optional[int] = None

    # Suit requirements: {suit: SuitRequirement}
    spades: SuitRequirement = field(default_factory=SuitRequirement)
    hearts: SuitRequirement = field(default_factory=SuitRequirement)
    diamonds: SuitRequirement = field(default_factory=SuitRequirement)
    clubs: SuitRequirement = field(default_factory=SuitRequirement)

    # Forcing status
    force_level: ForceLevel = ForceLevel.NON_FORCING

    # Special properties
    is_artificial: bool = False
    is_relay: bool = False
    is_transfer: bool = False
    transfer_to: Optional[str] = None  # 'H', 'S', etc.

    # Shape requirements
    balanced: Optional[bool] = None
    semi_balanced: Optional[bool] = None

    # Specific features
    shows_stopper_in: List[str] = field(default_factory=list)
    shows_control_in: List[str] = field(default_factory=list)
    denies_stopper_in: List[str] = field(default_factory=list)
    shows_void_in: List[str] = field(default_factory=list)
    shows_singleton_in: List[str] = field(default_factory=list)

    # Asking bids
    asks_for: Optional[str] = None  # "stopper", "aces", "keycards", "controls"

    # Fit showing
    shows_support_for: Optional[str] = None  # 'H', 'S', etc.
    support_length: int = 0

    # Descriptive text
    description: str = ""
    short_description: str = ""

    @property
    def is_forcing(self) -> bool:
        return self.force_level in (ForceLevel.FORCING, ForceLevel.GAME_FORCING)

    @property
    def is_game_forcing(self) -> bool:
        return self.force_level == ForceLevel.GAME_FORCING

    @property
    def is_invitational(self) -> bool:
        return self.force_level == ForceLevel.INVITATIONAL

    @property
    def is_signoff(self) -> bool:
        return self.force_level == ForceLevel.SIGNOFF

    def matches_hand(self, hcp: int, suit_lengths: Dict[str, int],
                     is_balanced: bool = False) -> bool:
        """Check if this meaning matches a given hand"""
        # HCP check
        if self.hcp_min is not None and hcp < self.hcp_min:
            return False
        if self.hcp_max is not None and hcp > self.hcp_max:
            return False

        # Suit length checks
        suit_map = {'S': self.spades, 'H': self.hearts,
                    'D': self.diamonds, 'C': self.clubs}
        for suit_char, requirement in suit_map.items():
            hand_len = suit_lengths.get(suit_char, 0)
            if not requirement.matches(hand_len):
                return False

        # Shape checks
        if self.balanced is not None:
            if self.balanced != is_balanced:
                return False

        return True

    def get_hcp_range_str(self) -> str:
        """Get HCP range as string like '15-17' or '12+'"""
        if self.hcp_min is None and self.hcp_max is None:
            return ""
        if self.hcp_max is None:
            return f"{self.hcp_min}+"
        if self.hcp_min is None:
            return f"0-{self.hcp_max}"
        if self.hcp_min == self.hcp_max:
            return str(self.hcp_min)
        return f"{self.hcp_min}-{self.hcp_max}"

    def get_suit_length_str(self) -> str:
        """Get suit length requirements as string"""
        parts = []
        suit_map = [('S', self.spades, '♠'), ('H', self.hearts, '♥'),
                    ('D', self.diamonds, '♦'), ('C', self.clubs, '♣')]
        for suit_char, req, symbol in suit_map:
            if req.min_length > 0:
                if req.max_length < 13:
                    parts.append(f"{req.min_length}-{req.max_length}{symbol}")
                else:
                    parts.append(f"{req.min_length}+{symbol}")
        return ", ".join(parts)


@dataclass
class BidRule:
    """Complete bidding rule"""
    # Identification
    rule_id: str = ""
    sequence_id: str = ""  # ".-4-1-11-B16" format for HLQ rules
    level: int = 0  # Hierarchical depth

    # Auction context
    context: RuleContext = RuleContext.ANY
    auction_pattern: str = ""  # "1C-P-1D-P-2D" or regex pattern
    position: str = ""  # "OPENER", "RESPONDER", "ADVANCER", "INTERVENOR"

    # The bid this rule describes
    bid: str = ""  # "2D", "2NT", "3C", "X", "XX", "P"

    # Meaning
    meaning: BidMeaning = field(default_factory=BidMeaning)

    # Convention requirements
    requires_conventions: Set[str] = field(default_factory=set)

    # Alert requirements
    alertable: bool = False
    alert_text: Optional[str] = None
    announce_text: Optional[str] = None  # For transfer announcements

    # Priority for rule matching (higher = preferred)
    priority: int = 0

    # Follow-up rules
    continuations: List['BidRule'] = field(default_factory=list)

    def matches_auction(self, auction: List[str]) -> bool:
        """Check if this rule applies to the given auction"""
        if not self.auction_pattern:
            return True

        # Convert auction to pattern string
        auction_str = "-".join(auction)

        # Try exact match first
        if self.auction_pattern == auction_str:
            return True

        # Try regex match
        try:
            if re.match(self.auction_pattern, auction_str):
                return True
        except re.error:
            pass

        # Try suffix match (auction ends with pattern)
        if auction_str.endswith(self.auction_pattern):
            return True

        return False


@dataclass
class Convention:
    """A bridge convention"""
    name: str
    code: str  # Short code like "STAYMAN", "JACOBY_TRANSFERS"
    description: str = ""
    rules: List[BidRule] = field(default_factory=list)
    enabled: bool = True

    # Related conventions (e.g., responses to this convention)
    related_conventions: List[str] = field(default_factory=list)


@dataclass
class BiddingSystem:
    """Complete bidding system with all rules"""
    name: str
    code: str  # Short code like "SAYC", "2/1", "ACOL"
    description: str = ""

    # Basic system properties
    opening_range_1nt: Tuple[int, int] = (15, 17)
    five_card_majors: bool = True
    strong_club: bool = False  # 1C = 16+ or Precision
    forcing_1nt_response: bool = False  # 2/1 system
    weak_two_bids: bool = True
    strong_two_clubs: bool = True

    # All rules
    rules: List[BidRule] = field(default_factory=list)

    # Available conventions
    conventions: Dict[str, Convention] = field(default_factory=dict)
    enabled_conventions: Set[str] = field(default_factory=set)

    # Lookup indices (built after initialization)
    _pattern_index: Dict[str, List[BidRule]] = field(default_factory=dict, repr=False)
    _opening_rules: List[BidRule] = field(default_factory=list, repr=False)
    _response_rules: List[BidRule] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self._build_indices()

    def _build_indices(self):
        """Create fast lookup structures"""
        self._opening_rules = [r for r in self.rules if r.context == RuleContext.OPENING]
        self._response_rules = [r for r in self.rules if r.context == RuleContext.RESPONSE]

        # Index by auction pattern for fast lookup
        self._pattern_index = {}
        for rule in self.rules:
            if rule.auction_pattern:
                if rule.auction_pattern not in self._pattern_index:
                    self._pattern_index[rule.auction_pattern] = []
                self._pattern_index[rule.auction_pattern].append(rule)

    def rebuild_indices(self):
        """Rebuild indices after modifying rules"""
        self._build_indices()

    def get_opening_bids(self, hcp: int, suit_lengths: Dict[str, int],
                         is_balanced: bool = False) -> List[Tuple[str, BidMeaning]]:
        """Get applicable opening bids for a hand"""
        candidates = []
        for rule in self._opening_rules:
            # Check convention requirements
            if rule.requires_conventions and not rule.requires_conventions.issubset(self.enabled_conventions):
                continue

            if rule.meaning.matches_hand(hcp, suit_lengths, is_balanced):
                candidates.append((rule.bid, rule.meaning))

        return candidates

    def get_legal_bids(self, auction: List[str], hcp: int,
                       suit_lengths: Dict[str, int],
                       is_balanced: bool = False) -> List[Tuple[str, BidMeaning]]:
        """Get all legal bids with their meanings for current auction"""
        candidates = []

        # Find matching rules
        for rule in self.rules:
            # Check convention requirements
            if rule.requires_conventions and not rule.requires_conventions.issubset(self.enabled_conventions):
                continue

            if rule.matches_auction(auction):
                if rule.meaning.matches_hand(hcp, suit_lengths, is_balanced):
                    candidates.append((rule.bid, rule.meaning))

        # Sort by priority (higher first)
        candidates.sort(key=lambda x: x[1].hcp_min or 0, reverse=True)

        return candidates

    def explain_bid(self, bid: str, auction: List[str]) -> Optional[BidMeaning]:
        """Explain what a bid means in current auction context"""
        # Find most specific matching rule
        best_rule = None
        best_specificity = -1

        for rule in self.rules:
            if rule.bid != bid:
                continue
            if not rule.matches_auction(auction):
                continue

            # Check convention requirements
            if rule.requires_conventions and not rule.requires_conventions.issubset(self.enabled_conventions):
                continue

            # More specific auction patterns are better
            specificity = len(rule.auction_pattern) if rule.auction_pattern else 0
            if specificity > best_specificity:
                best_rule = rule
                best_specificity = specificity

        return best_rule.meaning if best_rule else None

    def enable_convention(self, convention_code: str):
        """Enable a convention"""
        if convention_code in self.conventions:
            self.enabled_conventions.add(convention_code)
            self.conventions[convention_code].enabled = True

    def disable_convention(self, convention_code: str):
        """Disable a convention"""
        self.enabled_conventions.discard(convention_code)
        if convention_code in self.conventions:
            self.conventions[convention_code].enabled = False

    def get_summary(self) -> str:
        """Get system summary"""
        lines = [
            f"Bidding System: {self.name}",
            f"=" * 40,
            f"1NT opening range: {self.opening_range_1nt[0]}-{self.opening_range_1nt[1]}",
            f"5-card majors: {'Yes' if self.five_card_majors else 'No'}",
            f"Strong club: {'Yes' if self.strong_club else 'No'}",
            f"Total rules: {len(self.rules)}",
            f"  Opening bids: {len(self._opening_rules)}",
            f"  Responses: {len(self._response_rules)}",
            f"Conventions: {len(self.conventions)}",
            f"  Enabled: {len(self.enabled_conventions)}",
        ]
        return "\n".join(lines)


# Factory functions for creating standard systems

def create_sayc_system() -> BiddingSystem:
    """Create Standard American Yellow Card system"""
    system = BiddingSystem(
        name="Standard American Yellow Card",
        code="SAYC",
        description="Standard American with 5-card majors, strong NT (15-17), "
                    "2/1 game forcing responses.",
        opening_range_1nt=(15, 17),
        five_card_majors=True,
        strong_club=False,
        forcing_1nt_response=False,
        weak_two_bids=True,
        strong_two_clubs=True,
    )

    # Add opening bid rules
    _add_standard_opening_rules(system)
    _add_standard_response_rules(system)
    _add_standard_conventions(system)

    # Enable default conventions
    for conv in ["STAYMAN", "JACOBY_TRANSFERS", "BLACKWOOD", "GERBER",
                 "NEGATIVE_DOUBLES", "WEAK_TWO_BIDS"]:
        system.enable_convention(conv)

    system.rebuild_indices()
    return system


def create_2over1_system() -> BiddingSystem:
    """Create Two Over One Game Force system"""
    system = BiddingSystem(
        name="Two Over One Game Force",
        code="2/1",
        description="Modern 2/1 system with game-forcing 2-level responses, "
                    "Bergen raises, and 1NT forcing.",
        opening_range_1nt=(15, 17),
        five_card_majors=True,
        strong_club=False,
        forcing_1nt_response=True,
        weak_two_bids=True,
        strong_two_clubs=True,
    )

    _add_standard_opening_rules(system)
    _add_2over1_response_rules(system)
    _add_standard_conventions(system)

    # Enable default conventions
    for conv in ["STAYMAN", "JACOBY_TRANSFERS", "RKCB_1430", "JACOBY_2NT",
                 "BERGEN_RAISES", "NEGATIVE_DOUBLES", "SUPPORT_DOUBLES"]:
        system.enable_convention(conv)

    system.rebuild_indices()
    return system


def create_acol_system() -> BiddingSystem:
    """Create Acol system"""
    system = BiddingSystem(
        name="Acol",
        code="ACOL",
        description="British standard system with 4-card majors, weak NT (12-14), "
                    "and limit raises.",
        opening_range_1nt=(12, 14),
        five_card_majors=False,
        strong_club=False,
        forcing_1nt_response=False,
        weak_two_bids=True,
        strong_two_clubs=True,
    )

    _add_acol_opening_rules(system)
    _add_acol_response_rules(system)
    _add_standard_conventions(system)

    # Enable default conventions
    for conv in ["STAYMAN", "JACOBY_TRANSFERS", "BLACKWOOD",
                 "FOURTH_SUIT_FORCING", "CHECKBACK"]:
        system.enable_convention(conv)

    system.rebuild_indices()
    return system


def _add_standard_opening_rules(system: BiddingSystem):
    """Add standard opening bid rules"""
    # 1NT opening
    system.rules.append(BidRule(
        rule_id="open_1nt",
        context=RuleContext.OPENING,
        bid="1NT",
        meaning=BidMeaning(
            hcp_min=system.opening_range_1nt[0],
            hcp_max=system.opening_range_1nt[1],
            balanced=True,
            description=f"Balanced hand, {system.opening_range_1nt[0]}-{system.opening_range_1nt[1]} HCP",
            short_description="Balanced"
        )
    ))

    # 1-level suit openings
    for level, suit, symbol, min_hcp, max_hcp, min_len in [
        (1, 'S', '♠', 12, 21, 5),
        (1, 'H', '♥', 12, 21, 5),
        (1, 'D', '♦', 12, 21, 3 if system.five_card_majors else 4),
        (1, 'C', '♣', 12, 21, 3),
    ]:
        req = SuitRequirement(min_length=min_len)
        meaning = BidMeaning(
            hcp_min=min_hcp,
            hcp_max=max_hcp,
            description=f"{min_len}+ {symbol}, {min_hcp}-{max_hcp} HCP",
            short_description=f"{min_len}+ {symbol}"
        )
        setattr(meaning, suit.lower() + 's' if suit == 'S' else
                'hearts' if suit == 'H' else
                'diamonds' if suit == 'D' else 'clubs', req)

        system.rules.append(BidRule(
            rule_id=f"open_1{suit}",
            context=RuleContext.OPENING,
            bid=f"1{suit}",
            meaning=meaning
        ))

    # Weak two bids
    for suit, symbol in [('D', '♦'), ('H', '♥'), ('S', '♠')]:
        req = SuitRequirement(min_length=6, max_length=6)
        meaning = BidMeaning(
            hcp_min=5,
            hcp_max=10,
            description=f"6 {symbol}, 5-10 HCP, weak",
            short_description=f"Weak, 6 {symbol}"
        )
        setattr(meaning, 'spades' if suit == 'S' else
                'hearts' if suit == 'H' else 'diamonds', req)

        system.rules.append(BidRule(
            rule_id=f"open_weak_2{suit}",
            context=RuleContext.OPENING,
            bid=f"2{suit}",
            meaning=meaning,
            requires_conventions={"WEAK_TWO_BIDS"}
        ))

    # Strong 2C
    system.rules.append(BidRule(
        rule_id="open_2c_strong",
        context=RuleContext.OPENING,
        bid="2C",
        meaning=BidMeaning(
            hcp_min=22,
            is_artificial=True,
            force_level=ForceLevel.FORCING,
            description="22+ HCP or 9+ tricks, artificial, forcing",
            short_description="Strong, artificial"
        )
    ))

    # 2NT opening
    system.rules.append(BidRule(
        rule_id="open_2nt",
        context=RuleContext.OPENING,
        bid="2NT",
        meaning=BidMeaning(
            hcp_min=20,
            hcp_max=21,
            balanced=True,
            description="Balanced hand, 20-21 HCP",
            short_description="Balanced 20-21"
        )
    ))

    # 3-level preempts
    for suit, symbol in [('C', '♣'), ('D', '♦'), ('H', '♥'), ('S', '♠')]:
        req = SuitRequirement(min_length=7)
        meaning = BidMeaning(
            hcp_min=5,
            hcp_max=9,
            description=f"7+ {symbol}, preemptive",
            short_description=f"Preempt, 7+ {symbol}"
        )
        setattr(meaning, 'clubs' if suit == 'C' else
                'diamonds' if suit == 'D' else
                'hearts' if suit == 'H' else 'spades', req)

        system.rules.append(BidRule(
            rule_id=f"open_3{suit}",
            context=RuleContext.OPENING,
            bid=f"3{suit}",
            meaning=meaning
        ))


def _add_standard_response_rules(system: BiddingSystem):
    """Add standard response rules"""
    # Stayman
    system.rules.append(BidRule(
        rule_id="stayman",
        context=RuleContext.RESPONSE,
        auction_pattern="1NT-P",
        bid="2C",
        meaning=BidMeaning(
            hcp_min=8,
            is_artificial=True,
            force_level=ForceLevel.FORCING,
            asks_for="4-card major",
            description="Stayman, asking for 4-card major",
            short_description="Stayman"
        ),
        requires_conventions={"STAYMAN"},
        alertable=True,
        alert_text="Stayman"
    ))

    # Jacoby transfers
    system.rules.append(BidRule(
        rule_id="transfer_h",
        context=RuleContext.RESPONSE,
        auction_pattern="1NT-P",
        bid="2D",
        meaning=BidMeaning(
            is_artificial=True,
            is_transfer=True,
            transfer_to="H",
            force_level=ForceLevel.FORCING,
            description="Transfer to hearts",
            short_description="Transfer to ♥"
        ),
        requires_conventions={"JACOBY_TRANSFERS"},
        alertable=True,
        alert_text="Transfer to hearts"
    ))

    system.rules.append(BidRule(
        rule_id="transfer_s",
        context=RuleContext.RESPONSE,
        auction_pattern="1NT-P",
        bid="2H",
        meaning=BidMeaning(
            is_artificial=True,
            is_transfer=True,
            transfer_to="S",
            force_level=ForceLevel.FORCING,
            description="Transfer to spades",
            short_description="Transfer to ♠"
        ),
        requires_conventions={"JACOBY_TRANSFERS"},
        alertable=True,
        alert_text="Transfer to spades"
    ))

    # Simple responses to 1-level openings
    for opening in ['1C', '1D', '1H', '1S']:
        # 1-level response
        for resp_suit, resp_symbol in [('D', '♦'), ('H', '♥'), ('S', '♠')]:
            if opening[-1] >= resp_suit:
                continue  # Can't bid lower suit at same level

            req = SuitRequirement(min_length=4)
            meaning = BidMeaning(
                hcp_min=6,
                force_level=ForceLevel.FORCING,
                description=f"4+ {resp_symbol}, 6+ HCP, forcing",
                short_description=f"4+ {resp_symbol}"
            )
            setattr(meaning, 'diamonds' if resp_suit == 'D' else
                    'hearts' if resp_suit == 'H' else 'spades', req)

            system.rules.append(BidRule(
                rule_id=f"resp_{opening}_1{resp_suit}",
                context=RuleContext.RESPONSE,
                auction_pattern=f"{opening}-P",
                bid=f"1{resp_suit}",
                meaning=meaning
            ))

        # 1NT response
        system.rules.append(BidRule(
            rule_id=f"resp_{opening}_1nt",
            context=RuleContext.RESPONSE,
            auction_pattern=f"{opening}-P",
            bid="1NT",
            meaning=BidMeaning(
                hcp_min=6,
                hcp_max=10,
                description="6-10 HCP, no fit, no 4-card major",
                short_description="6-10 balanced"
            )
        ))

        # Raise
        suit_char = opening[-1]
        if suit_char in ['H', 'S']:
            # Major suit raise
            system.rules.append(BidRule(
                rule_id=f"resp_{opening}_raise",
                context=RuleContext.RESPONSE,
                auction_pattern=f"{opening}-P",
                bid=f"2{suit_char}",
                meaning=BidMeaning(
                    hcp_min=6,
                    hcp_max=10,
                    shows_support_for=suit_char,
                    support_length=3,
                    description=f"3+ card support, 6-10 HCP",
                    short_description="Simple raise"
                )
            ))


def _add_2over1_response_rules(system: BiddingSystem):
    """Add 2/1 game force response rules"""
    _add_standard_response_rules(system)

    # 2/1 responses are game forcing
    for opening in ['1H', '1S']:
        for resp_suit, resp_symbol in [('C', '♣'), ('D', '♦')]:
            req = SuitRequirement(min_length=4)
            meaning = BidMeaning(
                hcp_min=12,
                force_level=ForceLevel.GAME_FORCING,
                description=f"4+ {resp_symbol}, 12+ HCP, game forcing",
                short_description=f"GF, 4+ {resp_symbol}"
            )
            setattr(meaning, 'clubs' if resp_suit == 'C' else 'diamonds', req)

            system.rules.append(BidRule(
                rule_id=f"2over1_{opening}_2{resp_suit}",
                context=RuleContext.RESPONSE,
                auction_pattern=f"{opening}-P",
                bid=f"2{resp_suit}",
                meaning=meaning,
                priority=10  # Higher priority than other 2-level bids
            ))

        # Also 2H over 1S
        if opening == '1S':
            system.rules.append(BidRule(
                rule_id="2over1_1S_2H",
                context=RuleContext.RESPONSE,
                auction_pattern="1S-P",
                bid="2H",
                meaning=BidMeaning(
                    hcp_min=12,
                    force_level=ForceLevel.GAME_FORCING,
                    hearts=SuitRequirement(min_length=5),
                    description="5+ ♥, 12+ HCP, game forcing",
                    short_description="GF, 5+ ♥"
                ),
                priority=10
            ))

    # 1NT forcing over 1M
    for major in ['1H', '1S']:
        system.rules.append(BidRule(
            rule_id=f"1nt_forcing_{major}",
            context=RuleContext.RESPONSE,
            auction_pattern=f"{major}-P",
            bid="1NT",
            meaning=BidMeaning(
                hcp_min=6,
                hcp_max=12,
                force_level=ForceLevel.FORCING,
                description="Forcing 1NT, 6-12 HCP",
                short_description="Forcing 1NT"
            ),
            priority=10
        ))


def _add_acol_opening_rules(system: BiddingSystem):
    """Add Acol-specific opening rules"""
    _add_standard_opening_rules(system)

    # Override 1M to require only 4 cards
    for i, rule in enumerate(system.rules):
        if rule.rule_id in ["open_1S", "open_1H"]:
            suit = 'S' if rule.rule_id == "open_1S" else 'H'
            symbol = '♠' if suit == 'S' else '♥'
            req = SuitRequirement(min_length=4)
            system.rules[i].meaning = BidMeaning(
                hcp_min=12,
                hcp_max=21,
                description=f"4+ {symbol}, 12-21 HCP (Acol)",
                short_description=f"4+ {symbol}"
            )
            if suit == 'S':
                system.rules[i].meaning.spades = req
            else:
                system.rules[i].meaning.hearts = req


def _add_acol_response_rules(system: BiddingSystem):
    """Add Acol-specific response rules"""
    _add_standard_response_rules(system)


def _add_standard_conventions(system: BiddingSystem):
    """Add standard convention definitions"""
    system.conventions = {
        "STAYMAN": Convention(
            name="Stayman",
            code="STAYMAN",
            description="2♣ response to 1NT asks for 4-card major"
        ),
        "JACOBY_TRANSFERS": Convention(
            name="Jacoby Transfers",
            code="JACOBY_TRANSFERS",
            description="2♦/2♥ over 1NT transfers to hearts/spades"
        ),
        "TEXAS_TRANSFERS": Convention(
            name="Texas Transfers",
            code="TEXAS_TRANSFERS",
            description="4♦/4♥ over 1NT transfers to hearts/spades at game level"
        ),
        "BLACKWOOD": Convention(
            name="Blackwood",
            code="BLACKWOOD",
            description="4NT asks for aces (0-3 step responses)"
        ),
        "RKCB_1430": Convention(
            name="RKCB 1430",
            code="RKCB_1430",
            description="Roman Key Card Blackwood with 1430 responses"
        ),
        "RKCB_3014": Convention(
            name="RKCB 3014",
            code="RKCB_3014",
            description="Roman Key Card Blackwood with 3014 responses"
        ),
        "GERBER": Convention(
            name="Gerber",
            code="GERBER",
            description="4♣ asks for aces after NT opening"
        ),
        "JACOBY_2NT": Convention(
            name="Jacoby 2NT",
            code="JACOBY_2NT",
            description="Game-forcing raise of major with 4+ support"
        ),
        "BERGEN_RAISES": Convention(
            name="Bergen Raises",
            code="BERGEN_RAISES",
            description="3♣/3♦ as constructive/limit raises of major"
        ),
        "SPLINTER_BIDS": Convention(
            name="Splinter Bids",
            code="SPLINTER_BIDS",
            description="Double jump shift shows singleton/void with support"
        ),
        "NEGATIVE_DOUBLES": Convention(
            name="Negative Doubles",
            code="NEGATIVE_DOUBLES",
            description="Double of overcall is takeout, not penalty"
        ),
        "SUPPORT_DOUBLES": Convention(
            name="Support Doubles",
            code="SUPPORT_DOUBLES",
            description="Opener's double shows 3-card support"
        ),
        "RESPONSIVE_DOUBLES": Convention(
            name="Responsive Doubles",
            code="RESPONSIVE_DOUBLES",
            description="Double by advancer after partner overcalls"
        ),
        "LEBENSOHL": Convention(
            name="Lebensohl",
            code="LEBENSOHL",
            description="2NT as relay after opponent's interference"
        ),
        "NEW_MINOR_FORCING": Convention(
            name="New Minor Forcing",
            code="NEW_MINOR_FORCING",
            description="Bid of new minor is artificial and forcing"
        ),
        "FOURTH_SUIT_FORCING": Convention(
            name="Fourth Suit Forcing",
            code="FOURTH_SUIT_FORCING",
            description="Fourth suit bid is artificial and forcing"
        ),
        "CHECKBACK": Convention(
            name="Checkback Stayman",
            code="CHECKBACK",
            description="2♣ after 1NT rebid asks for majors"
        ),
        "DRURY": Convention(
            name="Drury",
            code="DRURY",
            description="2♣ response to 3rd/4th seat major opening"
        ),
        "WEAK_TWO_BIDS": Convention(
            name="Weak Two Bids",
            code="WEAK_TWO_BIDS",
            description="2♦/2♥/2♠ = 6-card suit, 5-10 HCP"
        ),
        "STRONG_2C": Convention(
            name="Strong 2♣",
            code="STRONG_2C",
            description="2♣ opening = 22+ HCP or 8.5+ tricks"
        ),
        "MULTI_2D": Convention(
            name="Multi 2♦",
            code="MULTI_2D",
            description="2♦ = weak two in either major"
        ),
        "MICHAELS_CUE": Convention(
            name="Michaels Cue Bid",
            code="MICHAELS_CUE",
            description="Direct cue bid shows two-suiter"
        ),
        "UNUSUAL_2NT": Convention(
            name="Unusual 2NT",
            code="UNUSUAL_2NT",
            description="Jump to 2NT shows minors"
        ),
    }


# System registry for easy lookup
BIDDING_SYSTEMS = {
    "SAYC": create_sayc_system,
    "2/1": create_2over1_system,
    "ACOL": create_acol_system,
}


def get_bidding_system(code: str) -> Optional[BiddingSystem]:
    """Get a bidding system by code"""
    factory = BIDDING_SYSTEMS.get(code.upper())
    if factory:
        return factory()
    return None


def list_available_systems() -> List[str]:
    """List available system codes"""
    return list(BIDDING_SYSTEMS.keys())
