"""
Match Controller - Controls teams matches with Open and Closed rooms.
"""

import copy
from typing import Optional, Dict, List
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

from .models import (
    BoardState, Seat, Bid, Card, Contract, Trick, Hand,
    BenTable, BenBoardRun, BenTeamsMatch
)
from .pavlicek import deal_to_number, format_deal_base62


class ClosedRoomWorker(QThread):
    """Background worker for BEN vs BEN closed room play.

    Plays out a board with all four positions controlled by BEN,
    running in a background thread to avoid blocking the UI.
    """

    finished = pyqtSignal(object)  # Emits BenBoardRun
    progress = pyqtSignal(str)  # Progress messages
    error = pyqtSignal(str)  # Error messages

    def __init__(self, engine, board: BoardState, ns_system: str = "BEN-NN",
                 ew_system: str = "BEN-NN", parent=None):
        super().__init__(parent)
        self.engine = engine
        self.board = board
        self.ns_system = ns_system
        self.ew_system = ew_system
        self._stop_requested = False

    def stop(self):
        """Request the worker to stop."""
        self._stop_requested = True

    def run(self):
        """Run the closed room play."""
        try:
            result = self._play_board()
            if not self._stop_requested:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _play_board(self) -> BenBoardRun:
        """Play out the board with BEN controlling all four seats."""
        # Deep copy the board to avoid modifying original
        board = copy.deepcopy(self.board)

        # Store original hands for the result
        original_hands = {}
        for seat, hand in board.hands.items():
            original_hands[seat] = Hand(cards=list(hand.cards))

        pavlicek_id = format_deal_base62(deal_to_number(original_hands))

        # Create result object
        result = BenBoardRun(
            table=BenTable.CLOSED,
            board_number=board.board_number,
            pavlicek_id=pavlicek_id,
            original_hands=original_hands,
            ns_bidding_system=self.ns_system,
            ew_bidding_system=self.ew_system
        )

        # Phase 1: Bidding
        self.progress.emit("Closed Room: Bidding...")
        current_bidder = board.dealer
        consecutive_passes = 0
        first_bid_made = False

        while not self._stop_requested:
            # Get bid from engine
            response = self.engine.get_bid(board, current_bidder)
            bid = response.action

            board.auction.append(bid)
            result.auction.append(bid)

            # Check for passed out
            if bid.is_pass:
                consecutive_passes += 1
                if consecutive_passes >= 4 and not first_bid_made:
                    # Passed out
                    result.played = True
                    result.ns_score = 0
                    result.ew_score = 0
                    return result
                if consecutive_passes >= 3 and first_bid_made:
                    # Auction complete
                    break
            else:
                consecutive_passes = 0
                first_bid_made = True

            current_bidder = current_bidder.next()

        if self._stop_requested:
            return result

        # Determine contract
        contract = self._determine_contract(board)
        if contract is None:
            result.played = True
            return result

        board.contract = contract
        result.contract = contract

        # Phase 2: Card play
        self.progress.emit(f"Closed Room: Playing {contract.to_str()}...")

        declarer = contract.declarer
        dummy = declarer.partner()
        current_player = declarer.next()  # Opening leader

        trump = contract.suit if contract.suit.value < 4 else None  # Not NT

        for trick_num in range(13):
            if self._stop_requested:
                break

            trick = Trick(leader=current_player)
            board.current_trick = trick

            for card_num in range(4):
                if self._stop_requested:
                    break

                # Get card play
                trick_cards = trick.cards if trick.cards else []

                if card_num == 0:
                    # Opening lead or lead to trick
                    if trick_num == 0:
                        response = self.engine.get_opening_lead(board)
                    else:
                        response = self.engine.get_card_play(
                            board, current_player, trick_cards
                        )
                else:
                    response = self.engine.get_card_play(
                        board, current_player, trick_cards
                    )

                card = response.action
                if card is None:
                    # Fallback: play first legal card
                    hand = board.hands.get(current_player)
                    if hand and hand.cards:
                        lead_suit = trick.cards[0].suit if trick.cards else None
                        if lead_suit:
                            suit_cards = [c for c in hand.cards if c.suit == lead_suit]
                            card = suit_cards[0] if suit_cards else hand.cards[0]
                        else:
                            card = hand.cards[0]

                if card:
                    board.hands[current_player].remove_card(card)
                    trick.add_card(card, trump)
                    current_player = current_player.next()

            # Complete trick
            if trick.is_complete():
                winner = trick.winner
                board.tricks.append(trick)
                result.tricks.append(trick)

                if winner.is_ns() == declarer.is_ns():
                    board.declarer_tricks += 1
                else:
                    board.defense_tricks += 1

                current_player = winner
                board.current_trick = None

        # Calculate score
        result.declarer_tricks = board.declarer_tricks
        vulnerable = board.vulnerability.is_vulnerable(declarer)
        score = self.engine.calculate_score(contract, board.declarer_tricks, vulnerable)

        # Assign score to correct side
        if declarer.is_ns():
            result.ns_score = score
            result.ew_score = -score
        else:
            result.ns_score = -score
            result.ew_score = score

        result.played = True
        return result

    def _determine_contract(self, board: BoardState) -> Optional[Contract]:
        """Determine the final contract from the auction."""
        auction = board.auction
        if not auction:
            return None

        level = 0
        suit = None
        declarer = None
        doubled = False
        redoubled = False

        for i, bid in enumerate(auction):
            if not bid.is_pass and not bid.is_double and not bid.is_redouble:
                level = bid.level
                suit = bid.suit
                bidder_seat = Seat((board.dealer.value + i) % 4)

                # Find first bid of this suit by this side
                side_ns = bidder_seat.is_ns()
                for j, b in enumerate(auction[:i+1]):
                    if not b.is_pass and not b.is_double and not b.is_redouble:
                        if b.suit == suit:
                            b_seat = Seat((board.dealer.value + j) % 4)
                            if b_seat.is_ns() == side_ns:
                                declarer = b_seat
                                break
                doubled = False
                redoubled = False
            elif bid.is_double:
                doubled = True
                redoubled = False
            elif bid.is_redouble:
                redoubled = True

        if level == 0 or declarer is None:
            return None

        return Contract(
            level=level,
            suit=suit,
            doubled=doubled,
            redoubled=redoubled,
            declarer=declarer
        )


class TeamsMatchController:
    """Controls a teams match with Open and Closed rooms.

    Manages the flow of a teams match where:
    - Open Room: Human plays as South, BEN plays other seats
    - Closed Room: BEN plays all four seats (same hands, swapped orientation)
    """

    def __init__(self, engine, match: BenTeamsMatch):
        self.engine = engine
        self.match = match
        self.closed_room_worker: Optional[ClosedRoomWorker] = None
        self._closed_room_callbacks: Dict[int, callable] = {}

    def start_board(self, board_num: int, board: BoardState) -> BenBoardRun:
        """Start a new board at the Open Room.

        Args:
            board_num: Board number
            board: The board state to play

        Returns:
            BenBoardRun for tracking the Open Room result
        """
        # Store original hands
        original_hands = {}
        for seat, hand in board.hands.items():
            original_hands[seat] = Hand(cards=list(hand.cards))

        pavlicek_id = format_deal_base62(deal_to_number(original_hands))

        # Create board run for Open Room
        open_run = BenBoardRun(
            table=BenTable.OPEN,
            board_number=board_num,
            pavlicek_id=pavlicek_id,
            original_hands=original_hands,
            ns_bidding_system=self.match.ns_bidding_system,
            ew_bidding_system=self.match.ew_bidding_system
        )

        # Initialize board runs dict for this board
        if board_num not in self.match.board_runs:
            self.match.board_runs[board_num] = {}
        self.match.board_runs[board_num][BenTable.OPEN] = open_run

        return open_run

    def complete_open_room(self, board_num: int, board: BoardState):
        """Record the completion of Open Room play.

        Args:
            board_num: Board number
            board: Completed board state
        """
        if board_num not in self.match.board_runs:
            return

        open_run = self.match.board_runs[board_num].get(BenTable.OPEN)
        if not open_run:
            return

        # Update the run with results
        open_run.auction = list(board.auction)
        open_run.tricks = list(board.tricks)
        open_run.contract = board.contract
        open_run.declarer_tricks = board.declarer_tricks

        # Calculate score
        if board.contract:
            vulnerable = board.vulnerability.is_vulnerable(board.contract.declarer)
            score = self.engine.calculate_score(
                board.contract, board.declarer_tricks, vulnerable
            )
            if board.contract.declarer.is_ns():
                open_run.ns_score = score
                open_run.ew_score = -score
            else:
                open_run.ns_score = -score
                open_run.ew_score = score
        else:
            open_run.ns_score = 0
            open_run.ew_score = 0

        open_run.played = True

    def start_closed_room_async(self, board_num: int, callback: callable = None):
        """Start Closed Room play in background.

        Args:
            board_num: Board number
            callback: Optional callback(BenBoardRun) when complete
        """
        if board_num not in self.match.board_runs:
            return

        open_run = self.match.board_runs[board_num].get(BenTable.OPEN)
        if not open_run:
            return

        # Create board from original hands
        from .models import BoardState, Vulnerability
        board = BoardState(
            board_number=board_num,
            hands=copy.deepcopy(open_run.original_hands)
        )
        dealer, vuln = BoardState._board_dealer_vuln(board_num)
        board.dealer = dealer
        board.vulnerability = vuln

        # Store callback
        if callback:
            self._closed_room_callbacks[board_num] = callback

        # Create and start worker
        self.closed_room_worker = ClosedRoomWorker(
            self.engine, board,
            self.match.ns_bidding_system,
            self.match.ew_bidding_system
        )
        self.closed_room_worker.finished.connect(
            lambda result: self._on_closed_room_complete(board_num, result)
        )
        self.closed_room_worker.start()

    def _on_closed_room_complete(self, board_num: int, result: BenBoardRun):
        """Handle completion of Closed Room play."""
        if board_num not in self.match.board_runs:
            self.match.board_runs[board_num] = {}

        self.match.board_runs[board_num][BenTable.CLOSED] = result

        # Call callback if registered
        callback = self._closed_room_callbacks.pop(board_num, None)
        if callback:
            callback(result)

    def get_closed_room_result(self, board_num: int) -> Optional[BenBoardRun]:
        """Get the Closed Room result for a board if available."""
        if board_num not in self.match.board_runs:
            return None
        return self.match.board_runs[board_num].get(BenTable.CLOSED)

    def get_open_room_result(self, board_num: int) -> Optional[BenBoardRun]:
        """Get the Open Room result for a board if available."""
        if board_num not in self.match.board_runs:
            return None
        return self.match.board_runs[board_num].get(BenTable.OPEN)

    def stop_closed_room(self):
        """Stop any running closed room worker."""
        if self.closed_room_worker and self.closed_room_worker.isRunning():
            self.closed_room_worker.stop()
            self.closed_room_worker.wait(2000)

    def is_board_complete(self, board_num: int) -> bool:
        """Check if both rooms have completed for a board."""
        if board_num not in self.match.board_runs:
            return False

        runs = self.match.board_runs[board_num]
        open_run = runs.get(BenTable.OPEN)
        closed_run = runs.get(BenTable.CLOSED)

        return (open_run is not None and open_run.played and
                closed_run is not None and closed_run.played)

    def get_all_results(self) -> List[Dict]:
        """Get all results for display in score table.

        Returns:
            List of dicts with board results
        """
        results = []
        for board_num in sorted(self.match.board_runs.keys()):
            runs = self.match.board_runs[board_num]
            open_run = runs.get(BenTable.OPEN)
            closed_run = runs.get(BenTable.CLOSED)

            result = {
                'board_num': board_num,
                'open': open_run,
                'closed': closed_run,
                'imp_swing': self.match.get_imp_swing(board_num) if self.is_board_complete(board_num) else None
            }
            results.append(result)

        return results
