"""
Bidding System Parser for .HLQ.TXT format.

Parses bidding rule files into structured BidRule objects for use
with the BEN neural network bidding system.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from pathlib import Path
import re
import json


@dataclass
class BidRule:
    """Single bidding rule parsed from HLQ format"""
    sequence: str                    # ".-2-1-1-4-1-1-3-B1"
    level: int                       # Hierarchical depth (number of dashes)
    description: str                 # Full text description
    hcp_min: Optional[int] = None
    hcp_max: Optional[int] = None
    suit_lengths: Dict[str, Tuple[int, Optional[int]]] = None
    is_forcing: bool = False
    is_artificial: bool = False
    shows_stopper: List[str] = None
    conventions_required: List[str] = None

    def __post_init__(self):
        if self.suit_lengths is None:
            self.suit_lengths = {}
        if self.shows_stopper is None:
            self.shows_stopper = []
        if self.conventions_required is None:
            self.conventions_required = []

    def matches_hand(self, hcp: int, suit_lengths: Dict[str, int]) -> bool:
        """Check if a hand matches this rule's requirements."""
        # Check HCP
        if self.hcp_min is not None and hcp < self.hcp_min:
            return False
        if self.hcp_max is not None and hcp > self.hcp_max:
            return False

        # Check suit lengths
        for suit, (min_len, max_len) in self.suit_lengths.items():
            hand_len = suit_lengths.get(suit, 0)
            if hand_len < min_len:
                return False
            if max_len is not None and hand_len > max_len:
                return False

        return True

    def get_bid_name(self) -> str:
        """Extract the bid name from the sequence (e.g., 'B1' -> '1♣')."""
        # The last part of the sequence typically indicates the bid
        parts = self.sequence.split('-')
        if parts:
            last = parts[-1]
            # B1 = 1 level, etc.
            if last.startswith('B'):
                try:
                    level = int(last[1:])
                    return f"{level}"
                except ValueError:
                    pass
        return ""


class BiddingSystemParser:
    """Parse .HLQ.TXT bidding rule files"""

    def __init__(self):
        self.macros: Dict[str, str] = {}
        self.rules: List[BidRule] = []

    def parse_file(self, filepath: Path) -> List[BidRule]:
        """Parse complete BIDDING.HLQ file

        Format: Lines starting with '.' contain sequence codes.
        Following lines (not starting with '.') are the description.
        """
        self.rules = []
        self.macros = {}
        current_convention = None

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip('\n\r')
            stripped = line.strip()

            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # Check for multi-line if/fi blocks
            if 'if convention' in stripped:
                convention_block, lines_consumed = self._parse_convention_block(lines[i:])
                current_convention = convention_block
                i += lines_consumed
                continue

            if stripped == 'fi':
                current_convention = None
                i += 1
                continue

            # Parse rule line - sequence starts with '.'
            if stripped.startswith('.'):
                # Collect multi-line description
                sequence = stripped
                description_lines = []
                i += 1

                # Read continuation lines (not starting with '.')
                while i < len(lines):
                    next_line = lines[i].rstrip('\n\r')
                    next_stripped = next_line.strip()

                    # Stop if we hit another sequence, comment, or control keyword
                    if (next_stripped.startswith('.') or
                        next_stripped.startswith('#') or
                        next_stripped == 'fi' or
                        'if convention' in next_stripped or
                        not next_stripped):
                        break

                    description_lines.append(next_stripped)
                    i += 1

                description = ' '.join(description_lines)
                description = self._convert_suit_escapes(description)

                rule = self._parse_rule_with_description(sequence, description, current_convention)
                if rule:
                    self.rules.append(rule)
                continue

            i += 1

        return self.rules

    def _convert_suit_escapes(self, text: str) -> str:
        """Convert HLQ suit escape sequences to symbols"""
        # \H = hearts, \S = spades, \D = diamonds, \C = clubs
        text = text.replace('\\H', '♥')
        text = text.replace('\\S', '♠')
        text = text.replace('\\D', '♦')
        text = text.replace('\\C', '♣')
        return text

    def _parse_convention_block(self, lines: List[str]) -> Tuple[str, int]:
        """Parse if convention X then ... fi block"""
        first_line = lines[0]
        match = re.search(r'if convention\s+([\w.-]+)', first_line)
        if match:
            convention_name = match.group(1)

            # Find matching 'fi'
            depth = 1
            line_count = 1
            while line_count < len(lines) and depth > 0:
                if 'if convention' in lines[line_count]:
                    depth += 1
                elif lines[line_count].strip() == 'fi':
                    depth -= 1
                line_count += 1

            return convention_name, line_count

        return None, 1

    def _parse_rule_with_description(self, sequence: str, description: str,
                                       convention: Optional[str] = None) -> Optional[BidRule]:
        """Parse a rule with its sequence and description"""
        # Check if this is a macro definition (short sequences with no dashes or just one segment)
        if not '-' in sequence and not sequence.startswith('.-'):
            # This is a macro like ".X-both-majors" or ".transfer-BM-3H"
            self.macros[sequence] = description
            return None

        # Count depth (number of dashes in sequence)
        level = sequence.count('-')

        # Extract HCP range
        hcp_min, hcp_max = self._extract_hcp_range(description)

        # Extract suit lengths
        suit_lengths = self._extract_suit_lengths(description)

        # Check for keywords
        is_forcing = any(kw in description.lower() for kw in ['forcing', 'game force', 'gf'])
        is_artificial = any(kw in description.lower() for kw in ['artificial', 'relay', 'transfer'])

        # Extract stoppers
        shows_stopper = self._extract_stoppers(description)

        rule = BidRule(
            sequence=sequence,
            level=level,
            description=description,
            hcp_min=hcp_min,
            hcp_max=hcp_max,
            suit_lengths=suit_lengths,
            is_forcing=is_forcing,
            is_artificial=is_artificial,
            shows_stopper=shows_stopper,
            conventions_required=[convention] if convention else []
        )

        return rule

    def _extract_hcp_range(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract HCP range from description"""
        # Pattern: "18 - 22 hcp" or "18-22 hcp" or "11-12 points"
        patterns = [
            r'(\d+)\s*-\s*(\d+)\s*(?:hcp|points|HCP)',
            r'(\d+)\s+or\s+more\s+(?:hcp|points|HCP)',
            r'at\s+least\s+(\d+)\s+(?:hcp|points|HCP)',
            r'(\d+)\+\s*(?:hcp|points|HCP)',
            r'(\d+)\s*(?:hcp|points|HCP)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    return int(match.group(1)), int(match.group(2))
                else:
                    return int(match.group(1)), None

        return None, None

    def _extract_suit_lengths(self, text: str) -> Dict[str, Tuple[int, Optional[int]]]:
        """Extract suit length requirements"""
        suit_lengths = {}

        # Pattern: "5 ♠ and 4 ♥" or "5 spades and 4 hearts"
        suit_patterns = [
            (r'(\d+)\s*♠', 'S'),
            (r'(\d+)\s*♥', 'H'),
            (r'(\d+)\s*♦', 'D'),
            (r'(\d+)\s*♣', 'C'),
            (r'(\d+)\s*spades?', 'S'),
            (r'(\d+)\s*hearts?', 'H'),
            (r'(\d+)\s*diamonds?', 'D'),
            (r'(\d+)\s*clubs?', 'C'),
            (r'(\d+)-card\s+(?:major|spade)', 'S'),
            (r'(\d+)-card\s+(?:major|heart)', 'H'),
            (r'(\d+)-card\s+(?:minor|diamond)', 'D'),
            (r'(\d+)-card\s+(?:minor|club)', 'C'),
        ]

        for pattern, suit in suit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                length = int(match.group(1))
                suit_lengths[suit] = (length, None)

        # Pattern: "5-5 in majors" or "4-4 in minors"
        if '5-5' in text:
            if 'major' in text.lower():
                suit_lengths['S'] = (5, None)
                suit_lengths['H'] = (5, None)
            elif 'minor' in text.lower():
                suit_lengths['D'] = (5, None)
                suit_lengths['C'] = (5, None)

        if '4-4' in text:
            if 'major' in text.lower():
                suit_lengths['S'] = (4, None)
                suit_lengths['H'] = (4, None)
            elif 'minor' in text.lower():
                suit_lengths['D'] = (4, None)
                suit_lengths['C'] = (4, None)

        # Pattern: "6+ card suit"
        match = re.search(r'(\d+)\+?\s*card\s+suit', text, re.IGNORECASE)
        if match:
            length = int(match.group(1))
            # Mark as "any suit" with this length
            suit_lengths['ANY'] = (length, None)

        return suit_lengths

    def _extract_stoppers(self, text: str) -> List[str]:
        """Extract stopper requirements"""
        stoppers = []

        if 'stopper' in text.lower():
            # Find suit mentioned after "stopper"
            for suit_name, suit_code in [('spades', 'S'), ('hearts', 'H'),
                                          ('diamonds', 'D'), ('clubs', 'C'),
                                          ('♠', 'S'), ('♥', 'H'),
                                          ('♦', 'D'), ('♣', 'C')]:
                if suit_name in text.lower():
                    stoppers.append(suit_code)

        return stoppers

    def get_rules_by_level(self, level: int) -> List[BidRule]:
        """Get all rules at specific hierarchical level"""
        return [r for r in self.rules if r.level == level]

    def get_opening_bids(self) -> List[BidRule]:
        """Get rules for opening bids (typically level 4 in hierarchy)"""
        return [r for r in self.rules if r.sequence.startswith('.-4-')]

    def get_defensive_bids(self) -> List[BidRule]:
        """Get rules for defensive bidding"""
        return [r for r in self.rules if r.sequence.startswith('.-2-')]

    def get_responses(self) -> List[BidRule]:
        """Get rules for responses to opening bids"""
        # Responses typically follow opening bids in the hierarchy
        return [r for r in self.rules if '-R' in r.sequence or 'response' in r.description.lower()]

    def search_rules(self, keyword: str) -> List[BidRule]:
        """Search rules by keyword in description"""
        keyword_lower = keyword.lower()
        return [r for r in self.rules if keyword_lower in r.description.lower()]

    def get_conventions(self) -> List[str]:
        """Get list of all convention names referenced"""
        conventions = set()
        for rule in self.rules:
            conventions.update(rule.conventions_required)
        return sorted(list(conventions))

    def export_to_json(self, output_path: Path):
        """Export parsed rules to JSON for faster loading"""
        rules_dict = {
            'macros': self.macros,
            'rules': [
                {
                    'sequence': r.sequence,
                    'level': r.level,
                    'description': r.description,
                    'hcp_min': r.hcp_min,
                    'hcp_max': r.hcp_max,
                    'suit_lengths': {k: list(v) for k, v in r.suit_lengths.items()},
                    'is_forcing': r.is_forcing,
                    'is_artificial': r.is_artificial,
                    'shows_stopper': r.shows_stopper,
                    'conventions_required': r.conventions_required
                }
                for r in self.rules
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(rules_dict, f, indent=2)

    @classmethod
    def load_from_json(cls, input_path: Path) -> 'BiddingSystemParser':
        """Load previously parsed rules from JSON"""
        parser = cls()

        with open(input_path, 'r') as f:
            data = json.load(f)

        parser.macros = data.get('macros', {})

        for rule_data in data.get('rules', []):
            suit_lengths = {k: tuple(v) for k, v in rule_data.get('suit_lengths', {}).items()}
            rule = BidRule(
                sequence=rule_data['sequence'],
                level=rule_data['level'],
                description=rule_data['description'],
                hcp_min=rule_data.get('hcp_min'),
                hcp_max=rule_data.get('hcp_max'),
                suit_lengths=suit_lengths,
                is_forcing=rule_data.get('is_forcing', False),
                is_artificial=rule_data.get('is_artificial', False),
                shows_stopper=rule_data.get('shows_stopper', []),
                conventions_required=rule_data.get('conventions_required', [])
            )
            parser.rules.append(rule)

        return parser

    def get_summary(self) -> str:
        """Get a summary of parsed rules"""
        lines = [
            f"Bidding System Summary",
            f"=" * 40,
            f"Total rules: {len(self.rules)}",
            f"Macros: {len(self.macros)}",
            f"",
            f"Rules by type:",
            f"  Opening bids: {len(self.get_opening_bids())}",
            f"  Defensive bids: {len(self.get_defensive_bids())}",
            f"  Responses: {len(self.get_responses())}",
            f"",
            f"Conventions referenced: {len(self.get_conventions())}",
        ]

        conventions = self.get_conventions()
        if conventions:
            lines.append(f"  {', '.join(conventions[:10])}")
            if len(conventions) > 10:
                lines.append(f"  ... and {len(conventions) - 10} more")

        return "\n".join(lines)


# Utility functions for common bidding queries

def find_opening_bid(parser: BiddingSystemParser, hcp: int,
                     spades: int, hearts: int, diamonds: int, clubs: int) -> List[BidRule]:
    """Find applicable opening bids for a hand."""
    suit_lengths = {'S': spades, 'H': hearts, 'D': diamonds, 'C': clubs}
    matches = []

    for rule in parser.get_opening_bids():
        if rule.matches_hand(hcp, suit_lengths):
            matches.append(rule)

    return matches


def get_bid_meaning(parser: BiddingSystemParser, sequence: str) -> Optional[BidRule]:
    """Get the meaning of a specific bid sequence."""
    for rule in parser.rules:
        if rule.sequence == sequence:
            return rule
    return None


if __name__ == "__main__":
    # Test the parser
    import sys

    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
        if filepath.exists():
            parser = BiddingSystemParser()
            rules = parser.parse_file(filepath)
            print(parser.get_summary())
            print()
            print("Sample rules:")
            for rule in rules[:5]:
                print(f"  {rule.sequence}: {rule.description[:60]}...")
        else:
            print(f"File not found: {filepath}")
    else:
        print("Usage: python bidding_parser.py <path_to_hlq_file>")
