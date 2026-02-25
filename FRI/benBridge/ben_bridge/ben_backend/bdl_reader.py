"""
BDL File Reader - Read BDL log files.

BDL format is used for logging completed hands.
This reader parses BDL files and reconstructs game state from them.
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    BoardState, Hand, Card, Suit, Rank, Seat,
    Vulnerability, Bid, Contract, Trick
)


@dataclass
class BDLDeal:
    """A single deal read from BDL file"""
    # Header info
    board_number: int = 0
    pavlicek_id: str = ""
    date: Optional[str] = None
    scoring_type: str = "IMP"

    # Deal info
    dealer: Seat = Seat.NORTH
    vulnerability: Vulnerability = Vulnerability.NONE
    hands: Dict[Seat, Hand] = field(default_factory=dict)

    # Auction
    auction: List[Bid] = field(default_factory=list)
    alerts: Dict[str, str] = field(default_factory=dict)

    # Contract
    contract: Optional[Contract] = None
    declarer: Optional[Seat] = None

    # Play
    tricks: List[List[str]] = field(default_factory=list)
    opening_lead: Optional[str] = None

    # Result
    tricks_made: int = 0
    ns_score: int = 0
    ew_score: int = 0

    def to_board_state(self) -> BoardState:
        """Convert to BoardState for replay"""
        board = BoardState(
            board_number=self.board_number,
            dealer=self.dealer,
            vulnerability=self.vulnerability,
            hands=self.hands.copy(),
            auction=self.auction.copy(),
            contract=self.contract,
        )
        return board


class BDLReader:
    """Read BDL log files"""

    def __init__(self):
        self.current_section = None
        self.current_deal = None

    def read_file(self, filepath: Path) -> List[BDLDeal]:
        """Read BDL file and return list of deals"""
        deals = []
        self.current_deal = None
        self.current_section = None

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip('\n\r')
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                i += 1
                continue

            # Deal separator or start
            if stripped.startswith('===') or stripped.startswith('---'):
                if self.current_deal and self._is_deal_valid(self.current_deal):
                    deals.append(self.current_deal)
                self.current_deal = BDLDeal()
                self.current_section = None
                i += 1
                continue

            # Section headers [Section Name]
            if stripped.startswith('[') and stripped.endswith(']'):
                self.current_section = stripped[1:-1].lower()
                i += 1
                continue

            # DOCTYPE header
            if stripped.startswith('DOCTYPE'):
                # Start new deal if not already started
                if self.current_deal is None:
                    self.current_deal = BDLDeal()
                i += 1
                continue

            # Parse content based on current section
            if self.current_deal:
                self._parse_line(stripped, line)

            i += 1

        # Add last deal
        if self.current_deal and self._is_deal_valid(self.current_deal):
            deals.append(self.current_deal)

        return deals

    def _is_deal_valid(self, deal: BDLDeal) -> bool:
        """Check if deal has enough data to be valid"""
        return len(deal.hands) >= 1 or deal.pavlicek_id

    def _parse_line(self, stripped: str, original: str):
        """Parse a single line based on current section"""
        deal = self.current_deal

        # Try to detect section from content if not in a named section
        if self.current_section is None:
            self._auto_detect_and_parse(stripped, original)
            return

        section = self.current_section

        if section in ['deal header', 'header']:
            self._parse_header_line(stripped, deal)
        elif section in ['hands', 'cards', 'deal']:
            self._parse_hand_line(stripped, deal)
        elif section in ['bidding', 'auction']:
            self._parse_bidding_line(stripped, deal)
        elif section in ['alerts', 'explanations']:
            self._parse_alert_line(stripped, deal)
        elif section in ['play', 'tricks']:
            self._parse_play_line(stripped, deal)
        elif section in ['result', 'score']:
            self._parse_result_line(stripped, deal)

    def _auto_detect_and_parse(self, stripped: str, original: str):
        """Auto-detect line type and parse accordingly"""
        deal = self.current_deal

        # Header fields (Key: Value)
        if ':' in stripped and not stripped.startswith(('N:', 'E:', 'S:', 'W:')):
            key, value = stripped.split(':', 1)
            key = key.strip().lower()
            value = value.strip()

            if key in ['board', 'board number', 'board#']:
                try:
                    deal.board_number = int(value)
                except ValueError:
                    pass
            elif key in ['pavlicek', 'deal id', 'deal_id']:
                deal.pavlicek_id = value
            elif key in ['date', 'datetime']:
                deal.date = value
            elif key in ['scoring', 'scoring type']:
                deal.scoring_type = value
            elif key in ['dealer']:
                try:
                    deal.dealer = Seat.from_char(value[0].upper())
                except (ValueError, IndexError):
                    pass
            elif key in ['vulnerability', 'vul']:
                deal.vulnerability = self._parse_vulnerability(value)
            elif key in ['contract']:
                deal.contract = self._parse_contract(value)
            elif key in ['declarer']:
                try:
                    deal.declarer = Seat.from_char(value[0].upper())
                except (ValueError, IndexError):
                    pass
            elif key in ['tricks', 'tricks made']:
                try:
                    deal.tricks_made = int(value)
                except ValueError:
                    pass
            elif key in ['ns score', 'n/s score', 'ns']:
                try:
                    deal.ns_score = int(value)
                except ValueError:
                    pass
            elif key in ['ew score', 'e/w score', 'ew']:
                try:
                    deal.ew_score = int(value)
                except ValueError:
                    pass
            return

        # Hand line: N: S AKJ5 H Q87 D K43 C 1065
        if stripped.startswith(('N:', 'E:', 'S:', 'W:')):
            self._parse_hand_line(stripped, deal)
            return

        # Bidding line (sequence of bids)
        if self._looks_like_bidding(stripped):
            self._parse_bidding_line(stripped, deal)
            return

        # Trick line: Trick 1: SA SK S2 S3
        if stripped.lower().startswith('trick'):
            self._parse_play_line(stripped, deal)
            return

    def _looks_like_bidding(self, line: str) -> bool:
        """Check if line looks like bidding"""
        bid_patterns = ['pass', 'p', 'x', 'xx', 'dbl', 'rdbl',
                        '1c', '1d', '1h', '1s', '1n', '2c', '2d', '2h', '2s', '2n',
                        '3c', '3d', '3h', '3s', '3n', '4c', '4d', '4h', '4s', '4n',
                        '5c', '5d', '5h', '5s', '5n', '6c', '6d', '6h', '6s', '6n',
                        '7c', '7d', '7h', '7s', '7n']
        words = line.lower().split()
        bid_count = sum(1 for w in words if w in bid_patterns or w.rstrip('.') in bid_patterns)
        return bid_count >= 2 or (bid_count == 1 and len(words) <= 4)

    def _parse_header_line(self, line: str, deal: BDLDeal):
        """Parse header field"""
        if ':' not in line:
            return

        key, value = line.split(':', 1)
        key = key.strip().lower()
        value = value.strip()

        if key in ['board', 'board number']:
            try:
                deal.board_number = int(value)
            except ValueError:
                pass
        elif key in ['pavlicek', 'deal id']:
            deal.pavlicek_id = value
        elif key == 'date':
            deal.date = value
        elif key == 'scoring':
            deal.scoring_type = value
        elif key == 'dealer':
            try:
                deal.dealer = Seat.from_char(value[0].upper())
            except (ValueError, IndexError):
                pass
        elif key in ['vulnerability', 'vul']:
            deal.vulnerability = self._parse_vulnerability(value)

    def _parse_vulnerability(self, value: str) -> Vulnerability:
        """Parse vulnerability string"""
        value = value.upper().strip()
        if value in ['NONE', '-', 'O', 'LOVE']:
            return Vulnerability.NONE
        elif value in ['NS', 'N-S', 'N/S', 'NORTH-SOUTH']:
            return Vulnerability.NS
        elif value in ['EW', 'E-W', 'E/W', 'EAST-WEST']:
            return Vulnerability.EW
        elif value in ['BOTH', 'ALL', 'B']:
            return Vulnerability.BOTH
        return Vulnerability.NONE

    def _parse_hand_line(self, line: str, deal: BDLDeal):
        """Parse hand: N: S AKJ5 H Q87 D K43 C 1065"""
        if ':' not in line:
            return

        # Get seat
        seat_str = line[0].upper()
        try:
            seat = Seat.from_char(seat_str)
        except (ValueError, KeyError):
            return

        # Get cards part (after the colon)
        cards_str = line[2:].strip()

        # Parse suits
        hand = self._parse_hand_string(cards_str)
        if hand:
            deal.hands[seat] = hand

    def _parse_hand_string(self, cards_str: str) -> Optional[Hand]:
        """Parse hand string like 'S AKJ5 H Q87 D K43 C 1065' or 'AKJ5.Q87.K43.1065'"""
        cards = []

        # Try PBN format first (dot-separated)
        if '.' in cards_str and ' ' not in cards_str:
            try:
                return Hand.from_pbn(cards_str)
            except Exception:
                pass

        # Try BDL format: S AKJ5 H Q87 D K43 C 1065
        parts = cards_str.split()
        current_suit = None

        suit_chars = {'S': Suit.SPADES, 'H': Suit.HEARTS,
                      'D': Suit.DIAMONDS, 'C': Suit.CLUBS}

        for part in parts:
            part = part.upper()

            # Check if this is a suit indicator
            if part in suit_chars:
                current_suit = suit_chars[part]
                continue

            # Parse cards in current suit
            if current_suit is not None and part != '-':
                for char in part:
                    try:
                        rank = Rank.from_char(char)
                        cards.append(Card(current_suit, rank))
                    except (ValueError, KeyError):
                        pass

        return Hand(cards) if cards else None

    def _parse_bidding_line(self, line: str, deal: BDLDeal):
        """Parse bidding line"""
        # Skip header lines
        if line.upper() in ['N  E  S  W', 'BIDDING:', 'AUCTION:']:
            return

        # Split into individual bids
        parts = line.replace(',', ' ').split()

        for part in parts:
            part = part.strip().upper()
            if not part:
                continue

            # Skip non-bid tokens
            if part in ['N', 'E', 'S', 'W', 'BIDDING:', 'AUCTION:']:
                continue

            try:
                bid = Bid.from_str(part)
                deal.auction.append(bid)
            except (ValueError, IndexError):
                pass

    def _parse_alert_line(self, line: str, deal: BDLDeal):
        """Parse alert: 1D = "Could be 3-card minor" """
        match = re.match(r'(.+?)\s*=\s*["\'](.+?)["\']', line)
        if match:
            bid_str, explanation = match.groups()
            deal.alerts[bid_str.strip()] = explanation.strip()
        elif '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                deal.alerts[parts[0].strip()] = parts[1].strip()

    def _parse_play_line(self, line: str, deal: BDLDeal):
        """Parse trick: Trick 1: SQ SA S2 S3"""
        # Remove "Trick N:" prefix
        if ':' in line:
            line = line.split(':', 1)[1].strip()

        # Parse cards
        cards = []
        for part in line.split():
            part = part.strip().upper()
            if len(part) >= 2 and part[0] in 'SHDC':
                cards.append(part)

        if cards:
            deal.tricks.append(cards)

    def _parse_result_line(self, line: str, deal: BDLDeal):
        """Parse result field"""
        if ':' not in line:
            return

        key, value = line.split(':', 1)
        key = key.strip().lower()
        value = value.strip()

        if key in ['contract']:
            deal.contract = self._parse_contract(value)
        elif key in ['tricks', 'tricks made']:
            try:
                deal.tricks_made = int(value)
            except ValueError:
                pass
        elif key in ['score', 'ns score', 'n/s']:
            try:
                deal.ns_score = int(value)
                deal.ew_score = -deal.ns_score
            except ValueError:
                pass
        elif key in ['ew score', 'e/w']:
            try:
                deal.ew_score = int(value)
            except ValueError:
                pass

    def _parse_contract(self, value: str) -> Optional[Contract]:
        """Parse contract string like '4S', '3NTX', '6HXX'"""
        if not value or value.upper() in ['PASSED', 'PASSED OUT', 'ALL PASS']:
            return None

        value = value.upper().strip()

        # Extract level
        match = re.match(r'(\d)([SHDCN]T?)(X{0,2})?', value)
        if not match:
            return None

        level = int(match.group(1))
        suit_str = match.group(2)
        dbl_str = match.group(3) or ''

        # Parse suit
        if suit_str in ['N', 'NT']:
            suit = Suit.NOTRUMP
        else:
            suit = Suit.from_char(suit_str[0])

        doubled = 'X' in dbl_str and 'XX' not in dbl_str
        redoubled = 'XX' in dbl_str

        return Contract(
            level=level,
            suit=suit,
            doubled=doubled,
            redoubled=redoubled
        )

    def load_session_log(self, log_dir: Path, session_num: int) -> List[BDLDeal]:
        """Load a specific session log file"""
        filename = log_dir / f"log-{session_num:03d}.bdl"
        if not filename.exists():
            raise FileNotFoundError(f"Log file not found: {filename}")

        return self.read_file(filename)

    def find_log_files(self, log_dir: Path) -> List[Path]:
        """Find all BDL log files in directory"""
        if not log_dir.exists():
            return []

        return sorted(log_dir.glob("*.bdl"))

    def read_all_logs(self, log_dir: Path) -> List[BDLDeal]:
        """Read all BDL files in directory"""
        all_deals = []
        for log_file in self.find_log_files(log_dir):
            try:
                deals = self.read_file(log_file)
                all_deals.extend(deals)
            except Exception as e:
                print(f"Error reading {log_file}: {e}")
        return all_deals


def load_bdl_file(filepath: str) -> List[BDLDeal]:
    """Convenience function to load BDL file"""
    reader = BDLReader()
    return reader.read_file(Path(filepath))


def load_deal_by_pavlicek(log_dir: str, pavlicek_id: str) -> Optional[BDLDeal]:
    """Find and load a deal by its Pavlicek ID"""
    reader = BDLReader()
    for deal in reader.read_all_logs(Path(log_dir)):
        if deal.pavlicek_id == pavlicek_id:
            return deal
    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
        if filepath.exists():
            reader = BDLReader()
            deals = reader.read_file(filepath)
            print(f"Read {len(deals)} deals from {filepath}")
            for i, deal in enumerate(deals[:5]):
                print(f"\nDeal {i + 1}:")
                print(f"  Board: {deal.board_number}")
                print(f"  Pavlicek: {deal.pavlicek_id}")
                print(f"  Dealer: {deal.dealer.to_char()}")
                print(f"  Vul: {deal.vulnerability.value}")
                print(f"  Hands: {len(deal.hands)}")
                print(f"  Auction: {len(deal.auction)} bids")
                print(f"  Score: NS={deal.ns_score}")
        else:
            print(f"File not found: {filepath}")
    else:
        print("Usage: python bdl_reader.py <path_to_bdl_file>")
