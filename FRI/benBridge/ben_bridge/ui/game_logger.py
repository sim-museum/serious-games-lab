"""
Game Logger - Saves completed hands in BDL format.
"""

import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from ben_backend.models import (
    BoardState, Card, Seat, Suit, Vulnerability, Contract, Trick, Rank
)
from ben_backend.pavlicek import deal_to_number, format_deal_base62


class GameLogger:
    """Logs completed bridge hands in BDL format."""

    def __init__(self, log_dir: str = None, ns_system: str = "BEN-NN",
                 ew_system: str = "BEN-NN"):
        """Initialize the logger.

        Args:
            log_dir: Directory for log files. Defaults to DATA/LOG in ben project directory.
            ns_system: N/S bidding system name
            ew_system: E/W bidding system name
        """
        if log_dir is None:
            # Default to DATA/LOG in ben project directory
            log_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent / "ben" / "DATA" / "LOG"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.ns_bidding_system = ns_system
        self.ew_bidding_system = ew_system

        self.current_log_file: Optional[Path] = None
        self.log_number = 1
        self._init_log_file()

    def _init_log_file(self):
        """Initialize or find the next log file."""
        # Find the next available log number
        while True:
            log_name = f"log-{self.log_number:03d}.bdl"
            log_path = self.log_dir / log_name
            if not log_path.exists():
                break
            self.log_number += 1

        self.current_log_file = self.log_dir / f"log-{self.log_number:03d}.bdl"
        self._write_header()

    def _write_header(self):
        """Write the BDL file header."""
        date_str = datetime.now().strftime("%b/%d/%Y")

        header = f'''DOCTYPE: BDL 17.1
.description.eng = "log file from {date_str}"

Scoring      :  Team (IMP)
.Bidding cnv :  N/S: {self.ns_bidding_system}
.            :  E/W: {self.ew_bidding_system}
.Lead cnv.   :  N/S.Suit   : -hiA-lo2-ln4-lwN-3cH-
.            :  N/S.Notrump: -hiA-lo2-ln4-lwN-3cH-
.            :  E/W.Suit   : -hiA-lo2-ln4-lwN-3cH-
.            :  E/W.Notrump: -hiA-lo2-ln4-lwN-3cH-
.Signal cnv. :  N/S: -ldA-lwN-paA-pwN-dcC-maH-mcH-pcY-dsN-dnN-
.            :  E/W: -ldA-lwN-paA-pwN-dcC-maH-mcH-pcY-dsN-dnN-
.Strength    :  72,c18,q7,r0,t1  Bs auto  E QPR  Mm 5
.Cheating    :  Never

'''
        with open(self.current_log_file, 'w') as f:
            f.write(header)

    def set_bidding_systems(self, ns_system: str, ew_system: str):
        """Update the bidding system names.

        Args:
            ns_system: N/S bidding system name
            ew_system: E/W bidding system name
        """
        self.ns_bidding_system = ns_system
        self.ew_bidding_system = ew_system

    def _card_to_str(self, card: Card) -> str:
        """Convert a card to BDL format (e.g., 'sA', 'hK', 'd7')."""
        suit_chars = {Suit.SPADES: 's', Suit.HEARTS: 'h',
                      Suit.DIAMONDS: 'd', Suit.CLUBS: 'c'}
        return f"{suit_chars[card.suit]}{card.rank.to_char()}"

    def _format_hand_line(self, cards: List[Card], suit: Suit) -> str:
        """Format cards of one suit for display."""
        suit_cards = sorted([c for c in cards if c.suit == suit], key=lambda c: c.rank)
        if not suit_cards:
            return "-"
        return " ".join(c.rank.to_char() for c in suit_cards)

    def _format_cards_block(self, board: BoardState) -> str:
        """Format the cards display block showing all four hands."""
        lines = []

        # Get hands
        n_hand = board.hands.get(Seat.NORTH, None)
        e_hand = board.hands.get(Seat.EAST, None)
        s_hand = board.hands.get(Seat.SOUTH, None)
        w_hand = board.hands.get(Seat.WEST, None)

        # We need to reconstruct original hands if cards have been played
        # For now, use what we have (this should be called before play or with saved original hands)

        def get_suit_str(hand, suit):
            if hand is None:
                return "-"
            cards = [c for c in hand.cards if c.suit == suit]
            if not cards:
                return "-"
            sorted_cards = sorted(cards, key=lambda c: c.rank)
            return " ".join(c.rank.to_char() for c in sorted_cards)

        # North hand (centered at column ~25)
        n_spades = get_suit_str(n_hand, Suit.SPADES) if n_hand else "-"
        n_hearts = get_suit_str(n_hand, Suit.HEARTS) if n_hand else "-"
        n_diamonds = get_suit_str(n_hand, Suit.DIAMONDS) if n_hand else "-"
        n_clubs = get_suit_str(n_hand, Suit.CLUBS) if n_hand else "-"

        lines.append(f"Cards        :                  {n_spades} ")
        lines.append(f"             :                  {n_hearts} ")
        lines.append(f"             :                  {n_diamonds} ")
        lines.append(f"             :                  {n_clubs} ")

        # West and East hands (side by side)
        w_spades = get_suit_str(w_hand, Suit.SPADES) if w_hand else "-"
        w_hearts = get_suit_str(w_hand, Suit.HEARTS) if w_hand else "-"
        w_diamonds = get_suit_str(w_hand, Suit.DIAMONDS) if w_hand else "-"
        w_clubs = get_suit_str(w_hand, Suit.CLUBS) if w_hand else "-"

        e_spades = get_suit_str(e_hand, Suit.SPADES) if e_hand else "-"
        e_hearts = get_suit_str(e_hand, Suit.HEARTS) if e_hand else "-"
        e_diamonds = get_suit_str(e_hand, Suit.DIAMONDS) if e_hand else "-"
        e_clubs = get_suit_str(e_hand, Suit.CLUBS) if e_hand else "-"

        # Format W/E lines with proper spacing
        lines.append(f"             :   {w_spades:<20}          {e_spades} ")
        lines.append(f"             :   {w_hearts:<20}          {e_hearts} ")
        lines.append(f"             :   {w_diamonds:<20}          {e_diamonds} ")
        lines.append(f"             :   {w_clubs:<20}          {e_clubs} ")

        # South hand (centered)
        s_spades = get_suit_str(s_hand, Suit.SPADES) if s_hand else "-"
        s_hearts = get_suit_str(s_hand, Suit.HEARTS) if s_hand else "-"
        s_diamonds = get_suit_str(s_hand, Suit.DIAMONDS) if s_hand else "-"
        s_clubs = get_suit_str(s_hand, Suit.CLUBS) if s_hand else "-"

        lines.append(f"             :                  {s_spades} ")
        lines.append(f"             :                  {s_hearts} ")
        lines.append(f"             :                  {s_diamonds} ")
        lines.append(f"             :                  {s_clubs} ")

        return "\n".join(lines)

    def _vuln_to_str(self, vuln: Vulnerability) -> str:
        """Convert vulnerability to BDL format."""
        return {
            Vulnerability.NONE: "None",
            Vulnerability.NS: "N/S",
            Vulnerability.EW: "E/W",
            Vulnerability.BOTH: "Both"
        }.get(vuln, "None")

    def _seat_to_str(self, seat: Seat) -> str:
        """Convert seat to full name."""
        return {
            Seat.NORTH: "North",
            Seat.EAST: "East",
            Seat.SOUTH: "South",
            Seat.WEST: "West"
        }[seat]

    def _contract_to_str(self, contract: Contract) -> str:
        """Convert contract to BDL format (e.g., '3nt', '4s', '2hx')."""
        suit_chars = {
            Suit.SPADES: 's', Suit.HEARTS: 'h',
            Suit.DIAMONDS: 'd', Suit.CLUBS: 'c',
            Suit.NOTRUMP: 'nt'
        }
        result = f"{contract.level}{suit_chars[contract.suit]}"
        if contract.redoubled:
            result += "xx"
        elif contract.doubled:
            result += "x"
        return result

    def _format_tricks(self, board: BoardState) -> str:
        """Format the tricks section."""
        lines = []
        trump = board.contract.suit if board.contract.suit != Suit.NOTRUMP else None
        declarer_side_ns = board.contract.declarer.is_ns()

        suit_chars = {Suit.SPADES: 'S', Suit.HEARTS: 'H',
                      Suit.DIAMONDS: 'D', Suit.CLUBS: 'C'}
        seat_chars = {Seat.NORTH: 'N', Seat.EAST: 'E',
                      Seat.SOUTH: 'S', Seat.WEST: 'W'}

        for i, trick in enumerate(board.tricks):
            trick_num = i + 1
            leader = trick.leader
            winner = trick.winner

            # Determine if declarer won this trick
            declarer_won = winner.is_ns() == declarer_side_ns

            # Format each card with winner marker
            card_strs = []
            for j, card in enumerate(trick.cards):
                card_str = self._card_to_str(card)
                player_seat = Seat((leader.value + j) % 4)
                if player_seat == winner:
                    # + for declarer win, - for defender win
                    card_str += "+" if declarer_won else "-"
                card_strs.append(f"{card_str:<4}")

            # Winning suit indicator
            winning_suit = trick.cards[0].suit  # Lead suit or trump
            if winner is not None:
                winner_idx = (winner.value - leader.value) % 4
                winning_suit = trick.cards[winner_idx].suit
            suit_indicator = suit_chars.get(winning_suit, '')

            # Format spacing based on whether declarer won
            spacing = "     " if declarer_won else "         "

            leader_char = seat_chars[leader]
            cards_str = " ".join(card_strs)

            if trick_num == 1:
                lines.append(f"Tricks       : {trick_num:2d}  {leader_char}    {cards_str}{spacing}{suit_indicator} ")
            else:
                lines.append(f"             : {trick_num:2d}  {leader_char}    {cards_str}{spacing}{suit_indicator} ")

        return "\n".join(lines)

    def log_hand(self, board: BoardState, original_hands: dict = None, deal_text: str = ""):
        """Log a completed hand to the BDL file.

        Args:
            board: The completed board state
            original_hands: Optional dict of original hands before play (for accurate card display)
            deal_text: Optional description text for the deal
        """
        if board.contract is None:
            return  # Can't log passed-out hands meaningfully

        # Calculate Pavlicek deal number from original hands
        hands_for_pavlicek = original_hands if original_hands else board.hands
        pavlicek_num = deal_to_number(hands_for_pavlicek)
        pavlicek_b62 = format_deal_base62(pavlicek_num)

        date_str = datetime.now().strftime("%y%b%d")
        deal_id = pavlicek_b62  # Use Pavlicek number (base-62) as deal ID

        # Calculate result
        contract = board.contract
        target = contract.target_tricks()
        made = board.declarer_tricks
        result_diff = made - target

        # Format result string
        if result_diff >= 0:
            result_str = f"+{result_diff}" if result_diff > 0 else "="
        else:
            result_str = str(result_diff)

        # Calculate score (simplified)
        vulnerable = board.vulnerability.is_vulnerable(contract.declarer)
        score = self._calculate_score(contract, made, vulnerable)

        # Build the log entry
        entry_lines = []
        entry_lines.append(f"Deal         :   {deal_id}")
        entry_lines.append(f"Deal-text    :   {deal_text if deal_text else f'Board #{board.board_number}'}")
        entry_lines.append(f"Dealer       :   {self._seat_to_str(board.dealer)}")
        entry_lines.append(f"Vuln         :   {self._vuln_to_str(board.vulnerability)}  ")

        # Use original hands if provided, otherwise use current state
        if original_hands:
            # Create a temporary board state with original hands for display
            display_board = BoardState(
                board_number=board.board_number,
                dealer=board.dealer,
                vulnerability=board.vulnerability,
                hands=original_hands
            )
            entry_lines.append(self._format_cards_block(display_board))
        else:
            entry_lines.append(self._format_cards_block(board))

        entry_lines.append("")

        # Opening leader
        opening_leader = contract.declarer.next()
        leader_char = {Seat.NORTH: 'N', Seat.EAST: 'E',
                       Seat.SOUTH: 'S', Seat.WEST: 'W'}[opening_leader]
        entry_lines.append(f"Trick-prep   : {leader_char} ")

        # Contract
        doubled_str = "+0"
        if contract.redoubled:
            doubled_str = "+2"
        elif contract.doubled:
            doubled_str = "+1"
        entry_lines.append(f"Contract     :  {self._contract_to_str(contract)}   {self._seat_to_str(contract.declarer)}     {doubled_str}")

        entry_lines.append("")

        # Tricks
        if board.tricks:
            entry_lines.append(self._format_tricks(board))

        entry_lines.append("")

        # Result
        entry_lines.append(f"Result       :  {self._contract_to_str(contract)}   {self._seat_to_str(contract.declarer)}    {result_str}      {score}      {deal_id}")

        entry_lines.append("")
        entry_lines.append("************************************************************")
        entry_lines.append("")
        entry_lines.append("")

        # Write to file
        with open(self.current_log_file, 'a') as f:
            f.write("\n".join(entry_lines))

        print(f"Hand logged to {self.current_log_file}")

    def _calculate_score(self, contract: Contract, tricks_made: int, vulnerable: bool) -> int:
        """Calculate the score for a contract."""
        level = contract.level
        suit = contract.suit
        target = 6 + level
        result = tricks_made - target

        if result < 0:
            # Undertricks
            undertricks = -result
            if contract.redoubled:
                if vulnerable:
                    return -(200 + 400 * (undertricks - 1)) if undertricks > 1 else -200
                else:
                    score = -100
                    for i in range(1, undertricks):
                        score -= 200 if i < 3 else 400
                    return score
            elif contract.doubled:
                if vulnerable:
                    return -(100 + 200 * (undertricks - 1)) if undertricks > 1 else -100
                else:
                    score = -100
                    for i in range(1, undertricks):
                        score -= 200 if i < 3 else 300
                    return score
            else:
                return -50 * undertricks if not vulnerable else -100 * undertricks

        # Made contract
        # Trick score
        if suit == Suit.NOTRUMP:
            trick_score = 40 + 30 * (level - 1)
        elif suit in (Suit.SPADES, Suit.HEARTS):
            trick_score = 30 * level
        else:
            trick_score = 20 * level

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
            score += 750 if vulnerable else 500
        elif level == 7:
            score += 1500 if vulnerable else 1000

        # Doubled/redoubled bonus
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
                if suit == Suit.NOTRUMP or suit in (Suit.SPADES, Suit.HEARTS):
                    score += result * 30
                else:
                    score += result * 20

        return score

    def log_board_run(self, board_run, deal_text: str = ""):
        """Log a completed BenBoardRun (e.g., from closed room).

        Args:
            board_run: BenBoardRun object with completed board data
            deal_text: Optional description text for the deal
        """
        if board_run.contract is None:
            return  # Can't log passed-out hands meaningfully

        # Create a BoardState-like object for logging
        from ben_backend.models import BoardState, Vulnerability

        # Determine dealer and vulnerability from board number
        dealer, vuln = BoardState._board_dealer_vuln(board_run.board_number)

        pavlicek_b62 = board_run.pavlicek_id

        # Calculate result
        contract = board_run.contract
        target = contract.target_tricks()
        made = board_run.declarer_tricks
        result_diff = made - target

        # Format result string
        if result_diff >= 0:
            result_str = f"+{result_diff}" if result_diff > 0 else "="
        else:
            result_str = str(result_diff)

        # Get score from board_run
        score = board_run.ns_score if contract.declarer.is_ns() else board_run.ew_score

        # Format table indicator for deal text
        table_str = "Closed Room" if board_run.table.value == 1 else "Open Room"
        if not deal_text:
            deal_text = f"Board #{board_run.board_number} ({table_str})"
        else:
            deal_text = f"{deal_text} ({table_str})"

        # Build the log entry
        entry_lines = []
        entry_lines.append(f"Deal         :   {pavlicek_b62}")
        entry_lines.append(f"Deal-text    :   {deal_text}")
        entry_lines.append(f"Dealer       :   {self._seat_to_str(dealer)}")
        entry_lines.append(f"Vuln         :   {self._vuln_to_str(vuln)}  ")

        # Format cards block from original_hands
        display_board = BoardState(
            board_number=board_run.board_number,
            dealer=dealer,
            vulnerability=vuln,
            hands=board_run.original_hands
        )
        entry_lines.append(self._format_cards_block(display_board))

        entry_lines.append("")

        # Opening leader
        opening_leader = contract.declarer.next()
        leader_char = {Seat.NORTH: 'N', Seat.EAST: 'E',
                       Seat.SOUTH: 'S', Seat.WEST: 'W'}[opening_leader]
        entry_lines.append(f"Trick-prep   : {leader_char} ")

        # Contract
        doubled_str = "+0"
        if contract.redoubled:
            doubled_str = "+2"
        elif contract.doubled:
            doubled_str = "+1"
        entry_lines.append(f"Contract     :  {self._contract_to_str(contract)}   {self._seat_to_str(contract.declarer)}     {doubled_str}")

        entry_lines.append("")

        # Tricks - format from board_run.tricks
        if board_run.tricks:
            entry_lines.append(self._format_tricks_from_run(board_run))

        entry_lines.append("")

        # Result
        entry_lines.append(f"Result       :  {self._contract_to_str(contract)}   {self._seat_to_str(contract.declarer)}    {result_str}      {score}      {pavlicek_b62}")

        entry_lines.append("")
        entry_lines.append("************************************************************")
        entry_lines.append("")
        entry_lines.append("")

        # Write to file
        with open(self.current_log_file, 'a') as f:
            f.write("\n".join(entry_lines))

        print(f"Closed room hand logged to {self.current_log_file}")

    def _format_tricks_from_run(self, board_run) -> str:
        """Format the tricks section from a BenBoardRun."""
        lines = []
        trump = board_run.contract.suit if board_run.contract.suit.value < 4 else None
        declarer_side_ns = board_run.contract.declarer.is_ns()

        suit_chars = {Suit.SPADES: 'S', Suit.HEARTS: 'H',
                      Suit.DIAMONDS: 'D', Suit.CLUBS: 'C'}
        seat_chars = {Seat.NORTH: 'N', Seat.EAST: 'E',
                      Seat.SOUTH: 'S', Seat.WEST: 'W'}

        for i, trick in enumerate(board_run.tricks):
            trick_num = i + 1
            leader = trick.leader
            winner = trick.winner

            # Determine if declarer won this trick
            declarer_won = winner.is_ns() == declarer_side_ns

            # Format each card with winner marker
            card_strs = []
            for j, card in enumerate(trick.cards):
                card_str = self._card_to_str(card)
                player_seat = Seat((leader.value + j) % 4)
                if player_seat == winner:
                    # + for declarer win, - for defender win
                    card_str += "+" if declarer_won else "-"
                card_strs.append(f"{card_str:<4}")

            # Winning suit indicator
            winning_suit = trick.cards[0].suit  # Lead suit or trump
            if winner is not None:
                winner_idx = (winner.value - leader.value) % 4
                winning_suit = trick.cards[winner_idx].suit
            suit_indicator = suit_chars.get(winning_suit, '')

            # Format spacing based on whether declarer won
            spacing = "     " if declarer_won else "         "

            leader_char = seat_chars[leader]
            cards_str = " ".join(card_strs)

            if trick_num == 1:
                lines.append(f"Tricks       : {trick_num:2d}  {leader_char}    {cards_str}{spacing}{suit_indicator} ")
            else:
                lines.append(f"             : {trick_num:2d}  {leader_char}    {cards_str}{spacing}{suit_indicator} ")

        return "\n".join(lines)

    def start_new_log(self):
        """Start a new log file."""
        self.log_number += 1
        self.current_log_file = self.log_dir / f"log-{self.log_number:03d}.bdl"
        self._write_header()
