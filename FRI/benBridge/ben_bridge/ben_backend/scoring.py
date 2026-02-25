"""
Scoring System for BEN Bridge - Handles all scoring methods and IMP conversion.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum

from .models import Seat, Vulnerability, Contract


class ScoringType(Enum):
    RUBBER = "Rubber"
    CHICAGO = "Chicago"
    PAIRS = "Pairs"
    TEAMS = "Teams"


@dataclass
class BoardResult:
    """Result of a single board."""
    board_number: int
    pavlicek_id: str
    dealer: Seat
    vulnerability: Vulnerability
    contract: Optional[Contract]
    declarer: Optional[Seat]
    tricks_made: int
    ns_score: int
    ew_score: int
    matchpoints: Optional[float] = None
    imps: Optional[int] = None
    notes: str = ""
    ns_bidding_system: str = "BEN-NN"
    ew_bidding_system: str = "BEN-NN"


# IMP conversion table (difference -> IMPs)
IMP_TABLE = [
    (20, 0), (50, 1), (90, 2), (130, 3), (170, 4),
    (220, 5), (270, 6), (320, 7), (370, 8), (430, 9),
    (500, 10), (600, 11), (750, 12), (900, 13), (1100, 14),
    (1300, 15), (1500, 16), (1750, 17), (2000, 18), (2250, 19),
    (2500, 20), (3000, 21), (3500, 22), (4000, 23), (float('inf'), 24)
]


def diff_to_imps(diff: int) -> int:
    """Convert score difference to IMPs."""
    abs_diff = abs(diff)
    for threshold, imps in IMP_TABLE:
        if abs_diff < threshold:
            return imps if diff >= 0 else -imps
    return 24 if diff >= 0 else -24


def calculate_contract_score(contract: Contract, tricks_made: int,
                            vulnerable: bool) -> int:
    """Calculate score for making or going down in a contract.

    Args:
        contract: The contract being played
        tricks_made: Number of tricks actually made
        vulnerable: Whether declarer is vulnerable

    Returns:
        Score (positive for making, negative for going down)
    """
    level = contract.level
    suit = contract.suit
    target = 6 + level
    result = tricks_made - target

    if result < 0:
        # Undertricks
        undertricks = -result
        if contract.redoubled:
            if vulnerable:
                # Vul redoubled: 400 first, 600 each subsequent
                return -(400 + 600 * (undertricks - 1)) if undertricks > 0 else 0
            else:
                # Non-vul redoubled: 200 first, 400 2nd/3rd, 600 subsequent
                score = 0
                for i in range(undertricks):
                    if i == 0:
                        score += 200
                    elif i < 3:
                        score += 400
                    else:
                        score += 600
                return -score
        elif contract.doubled:
            if vulnerable:
                # Vul doubled: 200 first, 300 each subsequent
                return -(200 + 300 * (undertricks - 1)) if undertricks > 0 else 0
            else:
                # Non-vul doubled: 100 first, 200 2nd/3rd, 300 subsequent
                score = 0
                for i in range(undertricks):
                    if i == 0:
                        score += 100
                    elif i < 3:
                        score += 200
                    else:
                        score += 300
                return -score
        else:
            # Undoubled undertricks
            return -50 * undertricks if not vulnerable else -100 * undertricks

    # Made contract - calculate trick score
    from .models import Suit
    if suit == Suit.NOTRUMP:
        trick_score = 40 + 30 * (level - 1)  # 40 for first, 30 for rest
    elif suit in (Suit.SPADES, Suit.HEARTS):
        trick_score = 30 * level
    else:  # Clubs, Diamonds
        trick_score = 20 * level

    # Apply doubled/redoubled multiplier
    if contract.doubled:
        trick_score *= 2
    if contract.redoubled:
        trick_score *= 4

    score = trick_score

    # Game/partscore bonus
    if trick_score >= 100:
        score += 500 if vulnerable else 300  # Game bonus
    else:
        score += 50  # Partscore bonus

    # Slam bonuses
    if level == 6:
        score += 750 if vulnerable else 500  # Small slam
    elif level == 7:
        score += 1500 if vulnerable else 1000  # Grand slam

    # Doubled/redoubled insult bonus
    if contract.doubled:
        score += 50
    if contract.redoubled:
        score += 100

    # Overtricks
    if result > 0:
        if contract.redoubled:
            score += result * (400 if vulnerable else 200)
        elif contract.doubled:
            score += result * (200 if vulnerable else 100)
        else:
            # Undoubled overtricks
            if suit == Suit.NOTRUMP or suit in (Suit.SPADES, Suit.HEARTS):
                score += result * 30
            else:
                score += result * 20

    return score


class ScoringTable:
    """Manages scoring for a session/match."""

    def __init__(self, scoring_type: ScoringType = ScoringType.TEAMS):
        self.scoring_type = scoring_type
        self.results: List[BoardResult] = []
        self.session_name: str = ""
        self.date: str = ""

    def add_result(self, result: BoardResult):
        """Add a board result."""
        self.results.append(result)

        # Recalculate cumulative scores
        if self.scoring_type == ScoringType.PAIRS:
            self._calculate_matchpoints()
        elif self.scoring_type == ScoringType.TEAMS:
            self._calculate_imps()

    def _calculate_matchpoints(self):
        """Calculate matchpoints (pairs scoring)."""
        # Group by board number
        boards = {}
        for r in self.results:
            if r.board_number not in boards:
                boards[r.board_number] = []
            boards[r.board_number].append(r)

        # Calculate MP for each board
        for board_num, board_results in boards.items():
            ns_scores = [r.ns_score for r in board_results]
            n = len(ns_scores)

            for result in board_results:
                # Count how many you beat + half for ties
                better = sum(1 for s in ns_scores if result.ns_score > s)
                equal = sum(1 for s in ns_scores if result.ns_score == s) - 1
                result.matchpoints = better + equal / 2.0

    def _calculate_imps(self):
        """Calculate IMPs (teams scoring) for comparison pairs."""
        # Pair results by board for closed room comparison
        paired = []
        unpaired = list(self.results)

        # Simple pairing: consecutive results on same board
        i = 0
        while i < len(unpaired) - 1:
            if unpaired[i].board_number == unpaired[i + 1].board_number:
                r1 = unpaired.pop(i)
                r2 = unpaired.pop(i)  # Now at position i after first pop

                diff = r1.ns_score - r2.ns_score
                r1.imps = diff_to_imps(diff)
                r2.imps = -r1.imps

                paired.extend([r1, r2])
            else:
                i += 1

    def get_ns_total(self) -> int:
        """Get total N/S score."""
        return sum(r.ns_score for r in self.results)

    def get_ew_total(self) -> int:
        """Get total E/W score."""
        return sum(r.ew_score for r in self.results)

    def get_ns_imps(self) -> int:
        """Get total N/S IMPs."""
        return sum(r.imps or 0 for r in self.results if r.imps is not None)

    def get_ns_matchpoints(self) -> float:
        """Get total N/S matchpoints."""
        return sum(r.matchpoints or 0 for r in self.results if r.matchpoints is not None)

    def get_summary(self) -> str:
        """Get text summary of results."""
        lines = [
            f"Session: {self.session_name}" if self.session_name else "Session Results",
            f"Scoring: {self.scoring_type.value}",
            f"Boards: {len(self.results)}",
            "",
        ]

        if self.scoring_type == ScoringType.TEAMS:
            lines.append(f"N/S IMPs: {self.get_ns_imps():+d}")
        elif self.scoring_type == ScoringType.PAIRS:
            lines.append(f"N/S Matchpoints: {self.get_ns_matchpoints():.1f}")
        else:
            lines.append(f"N/S Total: {self.get_ns_total()}")
            lines.append(f"E/W Total: {self.get_ew_total()}")

        return "\n".join(lines)

    def to_qss_format(self) -> str:
        """Export to BEN Bridge Score Sheet format."""
        lines = [
            "# BEN Bridge score sheet",
            ".version = 17.1",
            f".date = {self.date}",
            f"scoring.method = {self.scoring_type.value}",
            "",
        ]

        for i, r in enumerate(self.results, 1):
            lines.append(f"board.{i}.number = {r.board_number}")
            lines.append(f"board.{i}.pavlicek = {r.pavlicek_id}")
            if r.contract:
                lines.append(f"board.{i}.contract = {r.contract.to_str()}")
                lines.append(f"board.{i}.declarer = {r.declarer.to_char() if r.declarer else ''}")
            lines.append(f"board.{i}.tricks = {r.tricks_made}")
            lines.append(f"board.{i}.ns_score = {r.ns_score}")
            lines.append(f"board.{i}.ew_score = {r.ew_score}")
            lines.append(f"board.{i}.ns_system = {r.ns_bidding_system}")
            lines.append(f"board.{i}.ew_system = {r.ew_bidding_system}")
            if r.imps is not None:
                lines.append(f"board.{i}.imps = {r.imps}")
            if r.matchpoints is not None:
                lines.append(f"board.{i}.mp = {r.matchpoints}")
            lines.append("")

        return "\n".join(lines)

    def save(self, filepath: str):
        """Save scoring table to file."""
        content = self.to_qss_format()
        with open(filepath, 'w') as f:
            f.write(content)

    def save_to_local_matches(self, match_name: str = None) -> str:
        """Save to DATA/LOCAL-MATCHES directory.

        Creates a uniquely numbered QSS file in the LOCAL-MATCHES directory.

        Args:
            match_name: Optional name for the match file. If not provided,
                       uses incrementing numbers (match-001.qss, etc.)

        Returns:
            Path to the saved file
        """
        from pathlib import Path
        from datetime import datetime

        # Determine the local matches directory
        local_dir = Path(__file__).parent.parent / "DATA" / "LOCAL-MATCHES"
        local_dir.mkdir(parents=True, exist_ok=True)

        if match_name:
            # Use provided name
            filename = f"{match_name}.qss"
            filepath = local_dir / filename

            # Add number suffix if file exists
            counter = 1
            while filepath.exists():
                filename = f"{match_name}-{counter:03d}.qss"
                filepath = local_dir / filename
                counter += 1
        else:
            # Find next available match number
            existing = list(local_dir.glob("match-*.qss"))
            if existing:
                numbers = []
                for f in existing:
                    try:
                        num = int(f.stem.split("-")[1])
                        numbers.append(num)
                    except (IndexError, ValueError):
                        pass
                next_num = max(numbers) + 1 if numbers else 1
            else:
                next_num = 1

            filename = f"match-{next_num:03d}.qss"
            filepath = local_dir / filename

        # Set date if not already set
        if not self.date:
            self.date = datetime.now().strftime("%Y-%m-%d")

        # Save the file
        self.save(str(filepath))

        return str(filepath)

    @classmethod
    def load(cls, filepath: str) -> 'ScoringTable':
        """Load scoring table from file."""
        table = cls()

        with open(filepath, 'r') as f:
            current_board = {}
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()

                    if key == "scoring.method":
                        for st in ScoringType:
                            if st.value == value:
                                table.scoring_type = st
                                break
                    elif key == ".date":
                        table.date = value
                    elif key.startswith("board."):
                        parts = key.split('.')
                        if len(parts) == 3:
                            board_idx, field = parts[1], parts[2]
                            if board_idx not in current_board:
                                current_board[board_idx] = {}
                            current_board[board_idx][field] = value

        # Convert parsed data to BoardResult objects
        for idx in sorted(current_board.keys(), key=int):
            data = current_board[idx]
            result = BoardResult(
                board_number=int(data.get('number', 0)),
                pavlicek_id=data.get('pavlicek', ''),
                dealer=Seat.NORTH,  # Default, could be parsed
                vulnerability=Vulnerability.NONE,  # Default
                contract=None,  # Would need parsing
                declarer=None,
                tricks_made=int(data.get('tricks', 0)),
                ns_score=int(data.get('ns_score', 0)),
                ew_score=int(data.get('ew_score', 0)),
                imps=int(data['imps']) if 'imps' in data else None,
                matchpoints=float(data['mp']) if 'mp' in data else None,
            )
            table.results.append(result)

        return table


# Probability tables from TABLES.HLQ.TXT
SUIT_SPLIT_PROBABILITIES = {
    # Cards missing -> splits with probabilities
    2: [(1, 1, 52), (2, 0, 48)],
    3: [(2, 1, 78), (3, 0, 22)],
    4: [(2, 2, 40), (3, 1, 50), (4, 0, 10)],
    5: [(3, 2, 68), (4, 1, 28), (5, 0, 4)],
    6: [(3, 3, 36), (4, 2, 48), (5, 1, 15), (6, 0, 1)],
    7: [(4, 3, 62), (5, 2, 31), (6, 1, 7), (7, 0, 0.5)],
    8: [(4, 4, 33), (5, 3, 47), (6, 2, 17), (7, 1, 3), (8, 0, 0.2)],
}


def get_suit_split_probability(missing: int, split: Tuple[int, int]) -> float:
    """Get probability of a specific suit split.

    Args:
        missing: Number of cards missing in suit
        split: Tuple of (left_count, right_count)

    Returns:
        Probability as percentage (0-100)
    """
    if missing not in SUIT_SPLIT_PROBABILITIES:
        return 0.0

    a, b = min(split), max(split)
    for left, right, prob in SUIT_SPLIT_PROBABILITIES[missing]:
        if (left, right) == (a, b) or (right, left) == (a, b):
            return prob

    return 0.0
