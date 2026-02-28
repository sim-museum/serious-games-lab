#!/usr/bin/env python3
"""
OpeningRepertoire - OpeningRepertoire.py

A PyQt6 application that guides users through chess opening moves based on
opening-book statistics, similar to Scid's statistics pane.

INSTALLATION:
    pip install pyqt6 python-chess

USAGE:
    python3 OpeningRepertoire.py

The app runs alongside an external chess engine game. You manually synchronize
moves between this helper and your actual game.

Requirements:
    - Python 3.12+
    - PyQt6
    - python-chess
    - Ubuntu 24.04 (or compatible Linux)
"""

import sys
import os
import pickle
import argparse
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import chess
import chess.pgn
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QDialog, QDialogButtonBox, QMessageBox, QHeaderView, QFrame,
    QSizePolicy, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor


# =============================================================================
# Opening Book Data Structure and Implementation
# =============================================================================

@dataclass
class BookMove:
    """Represents a single move option in the opening book with statistics."""
    san: str          # Standard Algebraic Notation (e.g., "e4")
    uci: str          # UCI notation (e.g., "e2e4")
    count: int        # Number of games with this move
    wins: int = 0     # White wins (for reference)
    draws: int = 0    # Draws
    losses: int = 0   # Black wins


@dataclass
class BookPosition:
    """Represents a position in the opening book with all candidate moves."""
    moves: list[BookMove] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """Total games reaching this position."""
        return sum(m.count for m in self.moves)

    def get_moves_sorted(self) -> list[BookMove]:
        """Return moves sorted by popularity (descending)."""
        return sorted(self.moves, key=lambda m: m.count, reverse=True)

    def get_percentage(self, move: BookMove) -> float:
        """Calculate percentage for a specific move."""
        total = self.total_count
        if total == 0:
            return 0.0
        return (move.count / total) * 100


class OpeningBook:
    """
    Opening book that loads positions and statistics from a PGN file.

    Parses grandmaster games and builds a database of positions with
    move frequency statistics. Positions are keyed by FEN string.

    Caching: After first load, saves compiled book to a .pickle file.
    Subsequent loads use the cache if it's newer than the PGN file.
    """

    # Default PGN file path
    DEFAULT_PGN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "INSTALL", "25000grandmasterGames.pgn")

    # Maximum number of moves (plies) to extract from each game
    MAX_OPENING_DEPTH = 30  # 15 moves for each side

    # Cache file extension
    CACHE_SUFFIX = ".book_cache.pkl"

    def __init__(self, pgn_path: Optional[str] = None):
        """
        Initialize the opening book.

        Args:
            pgn_path: Path to PGN file. Uses DEFAULT_PGN_PATH if not specified.
        """
        # Dictionary mapping position FEN -> {move_uci: count}
        self._position_moves: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Compiled book: FEN -> BookPosition
        self._positions: dict[str, BookPosition] = {}

        # Set paths
        self._pgn_path = pgn_path or self.DEFAULT_PGN_PATH
        self._cache_path = self._pgn_path + self.CACHE_SUFFIX

        # Try to load from cache first, fall back to PGN
        if not self._load_from_cache():
            self._load_from_pgn()
            self._save_to_cache()

    def _load_from_cache(self) -> bool:
        """
        Attempt to load the opening book from a cached pickle file.

        Returns:
            True if cache was loaded successfully, False otherwise.
        """
        if not os.path.exists(self._cache_path):
            return False

        # Check if cache is newer than PGN file
        if os.path.exists(self._pgn_path):
            pgn_mtime = os.path.getmtime(self._pgn_path)
            cache_mtime = os.path.getmtime(self._cache_path)
            if cache_mtime < pgn_mtime:
                print("Cache is older than PGN file, rebuilding...")
                return False

        try:
            print(f"Loading opening book from cache: {self._cache_path}")
            with open(self._cache_path, 'rb') as f:
                raw_data = pickle.load(f)

            # Reconstruct BookPosition objects from raw data
            for fen, moves_list in raw_data.items():
                book_moves = [BookMove(**m) for m in moves_list]
                self._positions[fen] = BookPosition(moves=book_moves)

            if not self._positions:
                print("Cache is empty, ignoring")
                return False

            print(f"Loaded {len(self._positions)} positions from cache")
            return True
        except Exception as e:
            print(f"Failed to load cache: {e}")
            return False

    def _save_to_cache(self):
        """Save the compiled opening book to a pickle cache file."""
        if not self._positions:
            return
        try:
            print(f"Saving opening book cache to: {self._cache_path}")

            # Convert BookPosition objects to raw dicts for portable pickling
            raw_data = {}
            for fen, book_pos in self._positions.items():
                raw_data[fen] = [
                    {'san': m.san, 'uci': m.uci, 'count': m.count,
                     'wins': m.wins, 'draws': m.draws, 'losses': m.losses}
                    for m in book_pos.moves
                ]

            with open(self._cache_path, 'wb') as f:
                pickle.dump(raw_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            print("Cache saved successfully")
        except Exception as e:
            print(f"Failed to save cache: {e}")

    def _load_from_pgn(self):
        """
        Load opening statistics from a PGN file.

        Parses each game and records move frequencies at each position
        for the first MAX_OPENING_DEPTH plies.
        """
        if not os.path.exists(self._pgn_path):
            print(f"Warning: PGN file not found: {self._pgn_path}")
            return

        print(f"Loading opening book from: {self._pgn_path}")
        game_count = 0

        with open(self._pgn_path, 'r', errors='ignore') as pgn_file:
            while True:
                try:
                    game = chess.pgn.read_game(pgn_file)
                    if game is None:
                        break

                    self._process_game(game)
                    game_count += 1

                    if game_count % 5000 == 0:
                        print(f"  Processed {game_count} games...")

                except Exception as e:
                    # Skip problematic games
                    continue

        print(f"Loaded {game_count} games, {len(self._position_moves)} positions")

        # Convert raw counts to BookPosition objects
        self._compile_book()

    def _process_game(self, game: chess.pgn.Game):
        """
        Extract opening moves from a single game.

        Args:
            game: A parsed PGN game
        """
        board = game.board()
        move_count = 0

        for move in game.mainline_moves():
            if move_count >= self.MAX_OPENING_DEPTH:
                break

            # Record this move at this position
            fen = board.fen()
            uci = move.uci()
            self._position_moves[fen][uci] += 1

            # Make the move
            board.push(move)
            move_count += 1

    def _compile_book(self):
        """
        Convert raw move counts into BookPosition objects.
        """
        for fen, moves_dict in self._position_moves.items():
            try:
                board = chess.Board(fen)
            except:
                continue

            book_moves = []
            for uci, count in moves_dict.items():
                try:
                    move = chess.Move.from_uci(uci)
                    if move in board.legal_moves:
                        san = board.san(move)
                        book_moves.append(BookMove(
                            san=san,
                            uci=uci,
                            count=count
                        ))
                except:
                    continue

            if book_moves:
                self._positions[fen] = BookPosition(moves=book_moves)

        # Clear raw data to save memory
        self._position_moves.clear()

    def lookup(self, board: chess.Board) -> Optional[BookPosition]:
        """
        Look up the current position in the opening book.

        Args:
            board: Current board state

        Returns:
            BookPosition if found, None otherwise
        """
        fen = board.fen()
        return self._positions.get(fen)

    # Note: The old _build_opening_book method has been removed.
    # Opening book is now loaded from PGN file in _load_from_pgn().


# =============================================================================
# Board Widget - Handles all chess board rendering and interaction
# =============================================================================

class BoardWidget(QWidget):
    """
    A widget that renders a chess board and handles user interactions.

    Features:
    - Draw squares with coordinates
    - Render pieces using Unicode chess symbols
    - Color pieces based on opening book recommendations:
        - Green: Most popular book move
        - Yellow: Second most popular book move
        - Red: Other book moves
    - Handle hover events for playout preview
    - Handle click events for move input

    Signals:
        move_made: Emitted when a move is completed (passes chess.Move)
        hover_piece: Emitted when hovering over a piece (passes square or None)
    """

    move_made = pyqtSignal(object)  # chess.Move
    hover_piece = pyqtSignal(object)  # square or None

    # Unicode chess piece symbols
    PIECE_SYMBOLS = {
        'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
        'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
    }

    # Colors
    LIGHT_SQUARE = QColor(240, 217, 181)
    DARK_SQUARE = QColor(181, 136, 99)
    HIGHLIGHT_COLOR = QColor(255, 255, 0, 100)  # Selected square

    # Piece highlight colors (background behind piece)
    GREEN_HIGHLIGHT = QColor(0, 200, 0, 150)   # Most popular
    ORANGE_HIGHLIGHT = QColor(255, 140, 0, 150)  # Second most popular (orange)
    PURPLE_HIGHLIGHT = QColor(148, 0, 211, 150)  # Other book moves (purple)

    # Preview overlay color
    PREVIEW_OVERLAY = QColor(100, 100, 255, 80)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Game state
        self.board = chess.Board()
        self.user_color = chess.WHITE  # Will be set by dialog

        # Preview state for hover playouts
        self.preview_board: Optional[chess.Board] = None
        self.in_preview = False

        # Interaction state
        self.selected_square: Optional[int] = None
        self.hovered_square: Optional[int] = None

        # Drag state for opponent moves (drag-and-drop)
        self.dragging = False
        self.drag_start_square: Optional[int] = None
        self.drag_current_pos: Optional[QPoint] = None

        # Book data for coloring
        self.book_position: Optional[BookPosition] = None
        self.piece_colors: dict[int, QColor] = {}  # square -> highlight color
        self.piece_best_moves: dict[int, chess.Move] = {}  # square -> best book move

        # Whether we're still in book
        self.in_book = True

        # Size settings
        self.setMinimumSize(500, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Enable mouse tracking for hover
        self.setMouseTracking(True)

    def set_user_color(self, color: chess.Color):
        """Set which color the user is playing."""
        self.user_color = color
        self.update()

    def set_book_position(self, book_pos: Optional[BookPosition]):
        """
        Update the book data for the current position.
        Computes piece coloring based on move popularity.
        """
        self.book_position = book_pos
        self._compute_piece_colors()
        self.update()

    def _compute_piece_colors(self):
        """
        Compute which pieces should be highlighted and with what color.
        Also stores the best (most popular) book move for each piece.

        Coloring logic (only for user's turn):
        - Green: Pieces that can make the most popular book move
        - Orange: Pieces that can make the second most popular book move
        - Purple: Pieces that can make any other book move

        Only applied when:
        1. It's the user's turn
        2. We have book data for this position
        """
        self.piece_colors.clear()
        self.piece_best_moves.clear()

        # Only color on user's turn and when in book
        if not self.in_book or self.board.turn != self.user_color:
            return

        if not self.book_position or not self.book_position.moves:
            return

        sorted_moves = self.book_position.get_moves_sorted()

        # Build a map of piece square -> best move for that piece
        # (the most popular book move that piece can make)
        piece_move_counts: dict[int, list[tuple[chess.Move, int]]] = {}
        for book_move in sorted_moves:
            try:
                move = self.board.parse_san(book_move.san)
                sq = move.from_square
                if sq not in piece_move_counts:
                    piece_move_counts[sq] = []
                piece_move_counts[sq].append((move, book_move.count))
            except:
                pass

        # For each piece, store its best move (highest count)
        for sq, moves_list in piece_move_counts.items():
            best_move = max(moves_list, key=lambda x: x[1])[0]
            self.piece_best_moves[sq] = best_move

        # Get the source squares for each popularity tier
        # Most popular move(s) - could be ties
        if len(sorted_moves) >= 1:
            top_move = sorted_moves[0]
            try:
                move = self.board.parse_san(top_move.san)
                self.piece_colors[move.from_square] = self.GREEN_HIGHLIGHT
            except:
                pass

        # Second most popular
        if len(sorted_moves) >= 2:
            second_move = sorted_moves[1]
            try:
                move = self.board.parse_san(second_move.san)
                if move.from_square not in self.piece_colors:
                    self.piece_colors[move.from_square] = self.ORANGE_HIGHLIGHT
            except:
                pass

        # All other book moves
        for book_move in sorted_moves[2:]:
            try:
                move = self.board.parse_san(book_move.san)
                if move.from_square not in self.piece_colors:
                    self.piece_colors[move.from_square] = self.PURPLE_HIGHLIGHT
            except:
                pass

    def set_in_book(self, in_book: bool):
        """Update whether we're still following the book."""
        self.in_book = in_book
        self._compute_piece_colors()
        self.update()

    def reset(self):
        """Reset to starting position."""
        self.board = chess.Board()
        self.preview_board = None
        self.in_preview = False
        self.selected_square = None
        self.hovered_square = None
        self.piece_colors.clear()
        self.in_book = True
        self.update()

    def make_move(self, move: chess.Move) -> bool:
        """
        Make a move on the board.

        Returns:
            True if move was legal and made, False otherwise
        """
        if move in self.board.legal_moves:
            self.board.push(move)
            self.selected_square = None
            self.update()
            return True
        return False

    def show_preview(self, preview_board: chess.Board):
        """Show a preview board state (for hover playouts)."""
        self.preview_board = preview_board.copy()
        self.in_preview = True
        self.update()

    def clear_preview(self):
        """Clear the preview and show actual position."""
        self.preview_board = None
        self.in_preview = False
        self.update()

    def _square_size(self) -> int:
        """Calculate the size of each square."""
        return min(self.width(), self.height()) // 8

    def _square_rect(self, square: int) -> QRect:
        """Get the rectangle for a given square (0-63)."""
        size = self._square_size()
        file = chess.square_file(square)
        rank = chess.square_rank(square)

        # Flip board if playing as black
        if self.user_color == chess.BLACK:
            x = (7 - file) * size
            y = rank * size
        else:
            x = file * size
            y = (7 - rank) * size

        return QRect(x, y, size, size)

    def _square_from_pos(self, pos: QPoint) -> Optional[int]:
        """Convert a pixel position to a square index."""
        size = self._square_size()
        if size == 0:
            return None

        x = pos.x() // size
        y = pos.y() // size

        if not (0 <= x < 8 and 0 <= y < 8):
            return None

        if self.user_color == chess.BLACK:
            file = 7 - x
            rank = y
        else:
            file = x
            rank = 7 - y

        return chess.square(file, rank)

    def paintEvent(self, event):
        """Render the chess board."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Which board to display
        display_board = self.preview_board if self.in_preview else self.board

        size = self._square_size()

        for square in chess.SQUARES:
            rect = self._square_rect(square)
            file = chess.square_file(square)
            rank = chess.square_rank(square)

            # Draw square background
            is_light = (file + rank) % 2 == 1
            base_color = self.LIGHT_SQUARE if is_light else self.DARK_SQUARE
            painter.fillRect(rect, base_color)

            # If in preview mode, draw overlay
            if self.in_preview:
                painter.fillRect(rect, self.PREVIEW_OVERLAY)

            # Draw piece highlight (colored circle behind piece)
            if not self.in_preview and square in self.piece_colors:
                color = self.piece_colors[square]
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                center = rect.center()
                radius = size // 2 - 4
                painter.drawEllipse(center, radius, radius)

            # Highlight selected square
            if square == self.selected_square:
                painter.fillRect(rect, self.HIGHLIGHT_COLOR)

            # Draw piece (but not if it's being dragged)
            piece = display_board.piece_at(square)
            if piece and not (self.dragging and square == self.drag_start_square):
                symbol = self.PIECE_SYMBOLS.get(piece.symbol(), '')

                # Set font size based on square size
                font = QFont('Sans Serif', int(size * 0.7))
                painter.setFont(font)

                # Draw piece symbol
                painter.setPen(QPen(Qt.GlobalColor.black))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)

        # Draw coordinates on edges
        coord_font = QFont('Sans Serif', int(size * 0.15))
        painter.setFont(coord_font)
        painter.setPen(QPen(Qt.GlobalColor.black))

        for i in range(8):
            # Files (a-h) at bottom
            file_label = chr(ord('a') + i)
            if self.user_color == chess.BLACK:
                file_label = chr(ord('a') + 7 - i)
            x = i * size + size - 10
            y = 8 * size - 2
            painter.drawText(x, y, file_label)

            # Ranks (1-8) on left
            rank_label = str(i + 1) if self.user_color == chess.WHITE else str(8 - i)
            x = 2
            y = (7 - i) * size + 15 if self.user_color == chess.WHITE else i * size + 15
            painter.drawText(x, y, rank_label)

        # Draw dragged piece at cursor position
        if self.dragging and self.drag_start_square is not None and self.drag_current_pos is not None:
            piece = self.board.piece_at(self.drag_start_square)
            if piece:
                symbol = self.PIECE_SYMBOLS.get(piece.symbol(), '')
                font = QFont('Sans Serif', int(size * 0.7))
                painter.setFont(font)
                painter.setPen(QPen(Qt.GlobalColor.black))

                # Draw centered on cursor
                drag_rect = QRect(
                    self.drag_current_pos.x() - size // 2,
                    self.drag_current_pos.y() - size // 2,
                    size, size
                )
                painter.drawText(drag_rect, Qt.AlignmentFlag.AlignCenter, symbol)

        painter.end()

    def mousePressEvent(self, event):
        """
        Handle mouse press for move input.
        Drag-and-drop for both sides.
        """
        if event.button() != Qt.MouseButton.LeftButton:
            return

        square = self._square_from_pos(event.pos())
        if square is None:
            return

        # If in preview mode, clear it first and show real board
        if self.in_preview:
            self.clear_preview()

        piece = self.board.piece_at(square)

        # Start drag for any piece of the current turn's color
        if piece and piece.color == self.board.turn:
            self.dragging = True
            self.drag_start_square = square
            self.drag_current_pos = event.pos()
            self.selected_square = square
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release for drag-and-drop moves."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not self.dragging or self.drag_start_square is None:
            return

        # End drag
        self.dragging = False
        end_square = self._square_from_pos(event.pos())

        if end_square is not None and end_square != self.drag_start_square:
            # Try to make the move
            move = chess.Move(self.drag_start_square, end_square)

            # Check for pawn promotion
            from_piece = self.board.piece_at(self.drag_start_square)
            if from_piece and from_piece.piece_type == chess.PAWN:
                to_rank = chess.square_rank(end_square)
                if to_rank == 0 or to_rank == 7:
                    move = chess.Move(self.drag_start_square, end_square, chess.QUEEN)

            if move in self.board.legal_moves:
                self.move_made.emit(move)

        # Clear drag state
        self.drag_start_square = None
        self.drag_current_pos = None
        self.selected_square = None
        self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse movement for hover effects and drag-and-drop."""
        # Update drag position if dragging
        if self.dragging:
            self.drag_current_pos = event.pos()
            self.update()
            return

        square = self._square_from_pos(event.pos())

        if square != self.hovered_square:
            self.hovered_square = square

            # Only show hover preview if no piece is currently selected
            # (i.e., not in the middle of making a move)
            if self.selected_square is not None:
                self.hover_piece.emit(None)
            elif square is not None and square in self.piece_colors:
                self.hover_piece.emit(square)
            else:
                self.hover_piece.emit(None)

        # Update cursor
        if square is not None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn and not self.in_preview:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def leaveEvent(self, event):
        """Handle mouse leaving the widget."""
        self.hovered_square = None
        self.hover_piece.emit(None)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))


# =============================================================================
# Color Selection Dialog
# =============================================================================

class ColorDialog(QDialog):
    """Dialog to ask user which color they want to play."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Your Color")
        self.selected_color = chess.WHITE

        layout = QVBoxLayout(self)

        label = QLabel("Which color will you play?")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        btn_layout = QHBoxLayout()

        white_btn = QPushButton("♔ White")
        white_btn.setMinimumHeight(50)
        white_btn.clicked.connect(self._select_white)
        btn_layout.addWidget(white_btn)

        black_btn = QPushButton("♚ Black")
        black_btn.setMinimumHeight(50)
        black_btn.clicked.connect(self._select_black)
        btn_layout.addWidget(black_btn)

        layout.addLayout(btn_layout)

        self.setMinimumWidth(300)

    def _select_white(self):
        self.selected_color = chess.WHITE
        self.accept()

    def _select_black(self):
        self.selected_color = chess.BLACK
        self.accept()


# =============================================================================
# Main Window
# =============================================================================

class MainWindow(QMainWindow):
    """
    Main application window that ties together:
    - Board widget
    - Opening book
    - Statistics panel
    - Move list
    - Preview display
    """

    MAX_PLAYOUT_DEPTH = 10  # Maximum plies for hover preview

    def __init__(self, preset_color: Optional[chess.Color] = None, pgn_path: Optional[str] = None):
        """
        Initialize the main window.

        Args:
            preset_color: If specified, skip color selection dialog and use this color.
            pgn_path: If specified, use this PGN file for the opening book.
        """
        super().__init__()
        self.setWindowTitle("OpeningRepertoire")
        self.setMinimumSize(1100, 700)

        # Initialize opening book
        self.book = OpeningBook(pgn_path)

        # User's color (may be preset from command line)
        self.user_color = chess.WHITE
        self.preset_color = preset_color

        # Move history for display
        self.move_list: list[str] = []

        # Build UI
        self._build_ui()

        # Start new game (use preset color if provided via command line)
        self._new_game(use_preset=True)

    def _build_ui(self):
        """Construct the user interface."""
        # Create menu bar
        self._create_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # Left side: Chess board
        self.board_widget = BoardWidget()
        self.board_widget.move_made.connect(self._on_move_made)
        self.board_widget.hover_piece.connect(self._on_hover_piece)
        main_layout.addWidget(self.board_widget, stretch=2)

        # Right side: Stats panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Move sequence display
        move_label = QLabel("Move Sequence:")
        right_layout.addWidget(move_label)

        self.move_text = QTextEdit()
        self.move_text.setReadOnly(True)
        self.move_text.setMaximumHeight(80)
        right_layout.addWidget(self.move_text)

        # Candidate moves table
        stats_label = QLabel("Opening Book Statistics:")
        right_layout.addWidget(stats_label)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(3)
        self.stats_table.setHorizontalHeaderLabels(["Move", "Pawns Off", "%"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.stats_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stats_table.cellClicked.connect(self._on_stats_click)
        right_layout.addWidget(self.stats_table)

        # Preview display
        preview_label = QLabel("Hover Preview:")
        right_layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(60)
        self.preview_text.setPlaceholderText("Hover over a colored piece to see playout...")
        right_layout.addWidget(self.preview_text)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        right_layout.addWidget(line)

        # Status label
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self._update_status()
        right_layout.addWidget(self.status_label)

        # Instructions
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "• Drag and drop pieces to move (both sides)<br>"
            "• Click a move in the stats table to play it<br>"
            "• Hover colored pieces to preview playouts<br>"
            "• <span style='color:green'>■</span> Most popular  "
            "<span style='color:orange'>■</span> 2nd  "
            "<span style='color:purple'>■</span> Other book moves"
        )
        instructions.setWordWrap(True)
        right_layout.addWidget(instructions)

        # New Game button
        new_game_btn = QPushButton("New Game")
        new_game_btn.clicked.connect(self._new_game)
        right_layout.addWidget(new_game_btn)

        right_layout.addStretch()

        main_layout.addWidget(right_panel, stretch=1)

    def _create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # Help Contents action
        help_action = help_menu.addAction("&Help Contents")
        help_action.triggered.connect(self._show_help)

        help_menu.addSeparator()

        # About action
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

    def _show_help(self):
        """Show the comprehensive Help dialog."""
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("OpeningRepertoire Help")
        help_dialog.setMinimumSize(700, 600)

        layout = QVBoxLayout(help_dialog)

        # Help text with large, easy-to-read font
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setFont(QFont('Sans Serif', 13))
        help_text.setHtml("""
        <h1>OpeningRepertoire Help</h1>

        <h2>Overview</h2>
        <p>OpeningRepertoire is a chess opening study tool that helps you learn and practice
        opening variations by showing move statistics from a database of 25,000 grandmaster games.</p>

        <p>Use this application alongside your chess games (against engines or online) to see
        the most popular and successful opening moves at each position.</p>

        <h2>Getting Started</h2>
        <ol>
            <li>When the app starts, choose whether you'll play <b>White</b> or <b>Black</b></li>
            <li>The board will show with colored highlights on pieces that have book moves</li>
            <li>Play through your opening, comparing with the statistics panel</li>
        </ol>

        <h2>Color Coding</h2>
        <p>Pieces are highlighted based on the popularity of their best book move:</p>
        <ul>
            <li><span style='color:green; font-size:18px;'>&#9632;</span> <b>Green</b> - Most popular book move</li>
            <li><span style='color:orange; font-size:18px;'>&#9632;</span> <b>Orange</b> - Second most popular</li>
            <li><span style='color:purple; font-size:18px;'>&#9632;</span> <b>Purple</b> - Other book moves</li>
        </ul>

        <h2>Making Moves</h2>
        <h3>Your Turn (colored pieces visible):</h3>
        <ul>
            <li><b>Single-click</b> on any colored piece to instantly play its best book move</li>
            <li>For non-book moves: click piece, then click destination</li>
        </ul>

        <h3>Opponent's Turn:</h3>
        <ul>
            <li><b>Drag and drop</b> the opponent's piece from start to destination</li>
            <li>This enters the move your opponent played in the external game</li>
        </ul>

        <h2>Hover Preview</h2>
        <p>Hover your mouse over any colored piece to see a <b>playout preview</b>:</p>
        <ul>
            <li>Shows what happens if both sides play the most popular book moves</li>
            <li>The board temporarily displays the resulting position</li>
            <li>Move sequence shown in the "Hover Preview" area</li>
            <li>Move mouse away to return to the actual position</li>
        </ul>

        <h2>Statistics Panel</h2>
        <p>The right panel shows:</p>
        <ul>
            <li><b>Move Sequence</b> - Current game moves in algebraic notation</li>
            <li><b>Opening Book Statistics</b> - All book moves for the current position with:
                <ul>
                    <li>Move notation (e.g., e4, Nf3)</li>
                    <li>Number of games with this move</li>
                    <li>Percentage of games</li>
                </ul>
            </li>
        </ul>

        <h2>Out of Book</h2>
        <p>When you or your opponent plays a move not in the database:</p>
        <ul>
            <li>Status shows "Out of book"</li>
            <li>Piece coloring is disabled</li>
            <li>You can continue playing but without book guidance</li>
        </ul>

        <h2>Command Line Options</h2>
        <p>Run from terminal with these options:</p>
        <pre>
    python3 OpeningRepertoire.py [options]

    --help       Show help message and exit
    --white      Start as White (skip color dialog)
    --black      Start as Black (skip color dialog)
    --textmode   Run in text-only mode (no GUI)
        </pre>

        <h2>Text Mode</h2>
        <p>For terminal use without a graphical interface:</p>
        <pre>
    python3 OpeningRepertoire.py --textmode --white
        </pre>
        <p>In text mode:</p>
        <ul>
            <li>Board is displayed as ASCII art</li>
            <li>Enter moves in algebraic notation (e.g., e4, Nf3, O-O)</li>
            <li>Type 'help' for commands, 'quit' to exit</li>
        </ul>

        <h2>Tips</h2>
        <ul>
            <li>Use the hover preview to explore variations before committing</li>
            <li>The statistics show real grandmaster game frequencies</li>
            <li>Green moves are popular but not always the best - use your judgment!</li>
            <li>Click "New Game" to reset and choose a different color</li>
        </ul>
        """)

        layout.addWidget(help_text)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(help_dialog.accept)
        layout.addWidget(close_btn)

        help_dialog.exec()

    def _show_about(self):
        """Show the About dialog."""
        QMessageBox.about(
            self,
            "About OpeningRepertoire",
            "<h2>OpeningRepertoire</h2>"
            "<p><b>Version:</b> 0.1</p>"
            "<p><b>Date:</b> 2026-01-21</p>"
            "<p>A PyQt6 application that guides users through chess opening "
            "moves based on opening-book statistics from grandmaster games.</p>"
            "<p>Uses python-chess for board representation and move handling.</p>"
            "<p><b>Opening Database:</b><br>"
            "25,000 Grandmaster Games (PGN)</p>"
        )

    def _new_game(self, use_preset: bool = False):
        """
        Start a new game with color selection.

        Args:
            use_preset: If True and preset_color is set, skip the dialog.
        """
        if use_preset and self.preset_color is not None:
            self.user_color = self.preset_color
        else:
            dialog = ColorDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.user_color = dialog.selected_color
            else:
                # Default to white if dialog cancelled
                self.user_color = chess.WHITE

        # Reset everything
        self.board_widget.reset()
        self.board_widget.set_user_color(self.user_color)
        self.move_list.clear()
        self.preview_text.clear()

        # Look up starting position in book
        self._update_book_lookup()
        self._update_move_display()
        self._update_status()

    def _update_book_lookup(self):
        """Look up current position in the opening book and update UI."""
        book_pos = self.book.lookup(self.board_widget.board)
        self.board_widget.set_book_position(book_pos)

        # Update stats table
        self.stats_table.setRowCount(0)

        if book_pos and book_pos.moves:
            self.board_widget.set_in_book(True)
            sorted_moves = book_pos.get_moves_sorted()

            # Count current pawns on board before playouts
            cur_board = self.board_widget.board
            current_pawns = (
                len(cur_board.pieces(chess.PAWN, chess.WHITE))
                + len(cur_board.pieces(chess.PAWN, chess.BLACK))
            )

            self.stats_table.setRowCount(len(sorted_moves))
            for i, move in enumerate(sorted_moves):
                self.stats_table.setItem(i, 0, QTableWidgetItem(move.san))
                pct = book_pos.get_percentage(move)
                self.stats_table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))

                # Compute pawns removed after playout
                pawns_off = 0
                playout_moves = self._generate_playout(cur_board, move.san)
                if playout_moves:
                    sim_board = cur_board.copy()
                    for san in playout_moves:
                        try:
                            sim_board.push(sim_board.parse_san(san))
                        except Exception:
                            break
                    remaining = (
                        len(sim_board.pieces(chess.PAWN, chess.WHITE))
                        + len(sim_board.pieces(chess.PAWN, chess.BLACK))
                    )
                    pawns_off = current_pawns - remaining

                self.stats_table.setItem(i, 1, QTableWidgetItem(str(pawns_off)))

                # Color the row based on popularity
                if i == 0:
                    color = QColor(200, 255, 200)  # Light green
                elif i == 1:
                    color = QColor(255, 220, 180)  # Light orange
                else:
                    color = QColor(230, 200, 255)  # Light purple

                for col in range(3):
                    self.stats_table.item(i, col).setBackground(color)
        else:
            # Out of book
            self.board_widget.set_in_book(False)

    def _update_move_display(self):
        """Update the move sequence text display."""
        if not self.move_list:
            self.move_text.setText("(Starting position)")
            return

        # Format moves in pairs
        text_parts = []
        for i in range(0, len(self.move_list), 2):
            move_num = i // 2 + 1
            white_move = self.move_list[i]
            if i + 1 < len(self.move_list):
                black_move = self.move_list[i + 1]
                text_parts.append(f"{move_num}. {white_move} {black_move}")
            else:
                text_parts.append(f"{move_num}. {white_move}")

        self.move_text.setText(" ".join(text_parts))

    def _update_status(self):
        """Update the status label."""
        board = self.board_widget.board

        # Check game over states
        if board.is_checkmate():
            winner = "Black" if board.turn == chess.WHITE else "White"
            self.status_label.setText(f"<b>Checkmate!</b> {winner} wins.")
            return

        if board.is_stalemate():
            self.status_label.setText("<b>Stalemate!</b> Draw.")
            return

        # Normal play
        turn = "White" if board.turn == chess.WHITE else "Black"
        is_user_turn = board.turn == self.user_color

        if is_user_turn:
            status = f"<b>{turn} to move (Your turn)</b><br>"
            if self.board_widget.in_book:
                status += "Select a move from the book, or play any legal move."
            else:
                status += "<span style='color:red'>Out of book.</span> Play continues without suggestions."
        else:
            status = f"<b>{turn} to move (Opponent's turn)</b><br>"
            status += "Enter your opponent's move by clicking their piece and destination."

        self.status_label.setText(status)

    def _on_move_made(self, move: chess.Move):
        """Handle a move being made on the board."""
        # Get SAN before making move
        san = self.board_widget.board.san(move)

        # Check if this move is in the book (for tracking)
        book_pos = self.book.lookup(self.board_widget.board)
        move_in_book = False
        if book_pos:
            for bm in book_pos.moves:
                if bm.uci == move.uci():
                    move_in_book = True
                    break

        # Make the move
        if self.board_widget.make_move(move):
            self.move_list.append(san)
            self._update_move_display()
            self._update_book_lookup()
            self._update_status()

            # Notify if leaving book
            if not move_in_book and self.board_widget.in_book:
                # The move wasn't in the book but we were in book
                pass  # Book status will be updated by _update_book_lookup

    def _on_stats_click(self, row: int, col: int):
        """Handle click on stats table to play a move."""
        move_item = self.stats_table.item(row, 0)
        if move_item:
            san = move_item.text()
            try:
                move = self.board_widget.board.parse_san(san)
                self._on_move_made(move)
            except (chess.InvalidMoveError, chess.AmbiguousMoveError):
                pass

    def _on_hover_piece(self, square: Optional[int]):
        """
        Handle hovering over a piece.

        When hovering over a colored piece (one with book moves):
        1. Find the most popular book move for that piece
        2. Generate a playout sequence using book moves
        3. Display the preview board and move sequence
        """
        if square is None:
            # Mouse left the piece - clear preview
            self.board_widget.clear_preview()
            self.preview_text.clear()
            return

        # Find book moves from this square
        board = self.board_widget.board
        book_pos = self.book.lookup(board)

        if not book_pos:
            return

        # Find the most popular move from this piece
        best_move_san = None
        best_count = 0

        for book_move in book_pos.moves:
            try:
                move = board.parse_san(book_move.san)
                if move.from_square == square and book_move.count > best_count:
                    best_move_san = book_move.san
                    best_count = book_move.count
            except:
                continue

        if not best_move_san:
            return

        # Generate playout sequence
        playout_moves = self._generate_playout(board, best_move_san)

        if not playout_moves:
            return

        # Apply playout to get preview board
        preview_board = board.copy()
        for san in playout_moves:
            try:
                move = preview_board.parse_san(san)
                preview_board.push(move)
            except:
                break

        # Show preview
        self.board_widget.show_preview(preview_board)

        # Format playout text
        start_ply = len(self.move_list)
        text_parts = ["Preview: "]

        for i, san in enumerate(playout_moves):
            ply = start_ply + i
            move_num = ply // 2 + 1
            is_white = ply % 2 == 0

            if is_white:
                text_parts.append(f"{move_num}. {san}")
            else:
                if i == 0:  # First move is black
                    text_parts.append(f"{move_num}... {san}")
                else:
                    text_parts.append(san)
            text_parts.append(" ")

        self.preview_text.setText("".join(text_parts))

    def _generate_playout(self, start_board: chess.Board, first_move_san: str) -> list[str]:
        """
        Generate a playout sequence from the given position.

        Algorithm:
        1. Start with the specified first move
        2. Alternate sides, always picking the most popular book move
        3. Stop when out of book or max depth reached

        Args:
            start_board: Starting position
            first_move_san: The first move to play (SAN)

        Returns:
            List of SAN moves in the playout
        """
        playout = []
        board = start_board.copy()

        # Play the first move
        try:
            move = board.parse_san(first_move_san)
            board.push(move)
            playout.append(first_move_san)
        except:
            return []

        # Continue playout
        while len(playout) < self.MAX_PLAYOUT_DEPTH:
            book_pos = self.book.lookup(board)
            if not book_pos or not book_pos.moves:
                break

            # Pick the most popular move
            sorted_moves = book_pos.get_moves_sorted()
            best_move = sorted_moves[0]

            try:
                move = board.parse_san(best_move.san)
                board.push(move)
                playout.append(best_move.san)
            except:
                break

        return playout


# =============================================================================
# Text Mode Interface
# =============================================================================

class TextModeApp:
    """
    Text-only interface for OpeningRepertoire.
    Runs in the terminal without any GUI dependencies.
    """

    def __init__(self, user_color: chess.Color, pgn_path: Optional[str] = None):
        self.board = chess.Board()
        self.user_color = user_color
        self.book = OpeningBook(pgn_path)
        self.move_list: list[str] = []
        self.in_book = True

    def run(self):
        """Main loop for text mode."""
        print("\n" + "=" * 60)
        print("  OpeningRepertoire - Text Mode")
        print("=" * 60)
        print(f"\nYou are playing: {'White' if self.user_color == chess.WHITE else 'Black'}")
        print("Type 'help' for commands, 'quit' to exit.\n")

        while True:
            self._display_board()
            self._display_stats()

            if self.board.is_game_over():
                print("\nGame Over!")
                break

            # Get input
            is_user_turn = self.board.turn == self.user_color
            prompt = "Your move" if is_user_turn else "Opponent's move"
            prompt += " (or command): "

            try:
                user_input = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            # Handle commands
            cmd = user_input.lower()
            if cmd == 'quit' or cmd == 'exit':
                print("Goodbye!")
                break
            elif cmd == 'help':
                self._show_help()
                continue
            elif cmd == 'board':
                continue  # Just redisplay
            elif cmd == 'moves':
                self._show_moves()
                continue
            elif cmd == 'new':
                self.board = chess.Board()
                self.move_list.clear()
                self.in_book = True
                print("\nNew game started.\n")
                continue

            # Try to parse as a move
            try:
                move = self.board.parse_san(user_input)
                if move in self.board.legal_moves:
                    san = self.board.san(move)
                    self.board.push(move)
                    self.move_list.append(san)

                    # Check if still in book
                    book_pos = self.book.lookup(self.board)
                    if not book_pos or not book_pos.moves:
                        if self.in_book:
                            print("\n*** Left opening book ***\n")
                            self.in_book = False
                else:
                    print(f"Illegal move: {user_input}")
            except ValueError:
                print(f"Invalid move or command: {user_input}")

    def _display_board(self):
        """Display the board as ASCII art."""
        print("\n" + "-" * 35)

        # Determine board orientation
        if self.user_color == chess.WHITE:
            ranks = range(7, -1, -1)
            files = range(8)
        else:
            ranks = range(8)
            files = range(7, -1, -1)

        for rank in ranks:
            row = f" {rank + 1} |"
            for file in files:
                square = chess.square(file, rank)
                piece = self.board.piece_at(square)
                if piece:
                    symbol = piece.symbol()
                    # Use uppercase for white, lowercase for black
                    row += f" {symbol} "
                else:
                    row += " . "
            print(row)

        # File labels
        if self.user_color == chess.WHITE:
            print("   +" + "-" * 24)
            print("     a  b  c  d  e  f  g  h")
        else:
            print("   +" + "-" * 24)
            print("     h  g  f  e  d  c  b  a")

        print("-" * 35)

        # Show whose turn
        turn = "White" if self.board.turn == chess.WHITE else "Black"
        is_user = "(Your turn)" if self.board.turn == self.user_color else "(Opponent)"
        print(f"\n{turn} to move {is_user}")

    def _display_stats(self):
        """Display opening book statistics."""
        if not self.in_book:
            print("Out of book.\n")
            return

        book_pos = self.book.lookup(self.board)
        if not book_pos or not book_pos.moves:
            print("No book moves for this position.\n")
            return

        print("\nOpening Book Moves:")
        print("-" * 30)
        sorted_moves = book_pos.get_moves_sorted()
        for i, bm in enumerate(sorted_moves[:8]):  # Show top 8
            pct = book_pos.get_percentage(bm)
            marker = ""
            if i == 0:
                marker = " <-- BEST"
            elif i == 1:
                marker = " <-- 2nd"
            print(f"  {bm.san:6} {bm.count:5} games ({pct:5.1f}%){marker}")
        print()

    def _show_moves(self):
        """Show the move list."""
        if not self.move_list:
            print("\nNo moves yet.\n")
            return

        print("\nMove sequence:")
        for i in range(0, len(self.move_list), 2):
            move_num = i // 2 + 1
            white_move = self.move_list[i]
            if i + 1 < len(self.move_list):
                black_move = self.move_list[i + 1]
                print(f"  {move_num}. {white_move} {black_move}")
            else:
                print(f"  {move_num}. {white_move}")
        print()

    def _show_help(self):
        """Show help for text mode."""
        print("""
Commands:
  <move>    Enter a move in algebraic notation (e.g., e4, Nf3, O-O, exd5)
  help      Show this help message
  board     Redisplay the board
  moves     Show the move list
  new       Start a new game
  quit      Exit the program

Move Examples:
  e4        Pawn to e4
  Nf3       Knight to f3
  Bxc6      Bishop takes on c6
  O-O       Kingside castle
  O-O-O     Queenside castle
  e8=Q      Pawn promotion to queen

Tips:
  - The BEST move shown is the most popular in grandmaster games
  - Enter your moves when it's your turn
  - Enter opponent's moves when it's their turn
""")


# =============================================================================
# Entry Point
# =============================================================================

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='OpeningRepertoire',
        description='Chess opening study tool with grandmaster game statistics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 OpeningRepertoire.py              # Run GUI, choose color at startup
  python3 OpeningRepertoire.py --white      # Run GUI as White
  python3 OpeningRepertoire.py --black      # Run GUI as Black
  python3 OpeningRepertoire.py --textmode --white   # Text mode as White
  python3 OpeningRepertoire.py --textmode --black   # Text mode as Black
"""
    )

    parser.add_argument('--textmode', action='store_true',
                        help='Run in text-only mode (no GUI)')
    parser.add_argument('--pgn', metavar='PATH',
                        help='Path to PGN file for the opening book')
    parser.add_argument('--build-cache', action='store_true',
                        help='Build opening book cache and exit (no GUI)')

    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument('--white', action='store_true',
                             help='Play as White')
    color_group.add_argument('--black', action='store_true',
                             help='Play as Black')

    return parser.parse_args()


def main():
    args = parse_arguments()
    pgn_path = args.pgn

    # Build cache and exit (no GUI)
    if args.build_cache:
        print("Building opening book cache...")
        book = OpeningBook(pgn_path)
        if book._positions:
            print(f"Cache built successfully: {len(book._positions)} positions")
        else:
            print("Warning: No positions loaded, cache not built")
            sys.exit(1)
        sys.exit(0)

    # Determine user color
    if args.white:
        user_color = chess.WHITE
    elif args.black:
        user_color = chess.BLACK
    else:
        user_color = None  # Will prompt

    # Text mode
    if args.textmode:
        if user_color is None:
            # Prompt for color in text mode
            print("\nOpeningRepertoire - Text Mode")
            print("-" * 30)
            while True:
                choice = input("Play as (w)hite or (b)lack? ").strip().lower()
                if choice in ('w', 'white'):
                    user_color = chess.WHITE
                    break
                elif choice in ('b', 'black'):
                    user_color = chess.BLACK
                    break
                print("Please enter 'w' for White or 'b' for Black.")

        text_app = TextModeApp(user_color, pgn_path=pgn_path)
        text_app.run()
        return

    # GUI mode
    app = QApplication(sys.argv)

    # Set application-wide font - larger for easy reading
    font = QFont()
    font.setPointSize(14)
    app.setFont(font)

    window = MainWindow(preset_color=user_color, pgn_path=pgn_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# =============================================================================
# USAGE SUMMARY
# =============================================================================
"""
HOW TO RUN:
    1. Install dependencies:
       pip install pyqt6 python-chess

    2. Run the program:
       python3 OpeningRepertoire.py

HOW TO USE WITH AN EXTERNAL CHESS ENGINE:
    1. Start your chess game against an engine in a separate program
       (e.g., SCID vs PC, Arena, or an online chess site)

    2. Launch this Opening Helper alongside your game

    3. Select your color (White or Black) when prompted

    4. Manual synchronization:
       - When it's YOUR turn in the external game:
         * Look at the colored pieces and statistics in this helper
         * Green = most popular move, Yellow = 2nd, Red = other book moves
         * Hover over colored pieces to preview the resulting main line
         * Choose your move and play it in BOTH the helper AND your external game

       - When it's OPPONENT'S turn:
         * After they play in the external game, enter the same move here
         * Click their piece, then click the destination square
         * Or double-click the move in the stats table if it's listed

    5. The helper shows "Out of book" when no book data exists for the position
       At that point, you're on your own!

PIECE COLORING (only shown on your turn while in book):
    - GREEN background: Piece can make the most popular book move
    - YELLOW background: Piece can make the 2nd most popular book move
    - RED background: Piece can make other book moves

HOVER PREVIEW:
    - Hover over any colored piece to see a preview of the main line
    - The preview shows what would happen if both sides play the most
      popular book moves
    - The board temporarily displays the final position of the preview
    - Move away from the piece to restore the actual position
"""
