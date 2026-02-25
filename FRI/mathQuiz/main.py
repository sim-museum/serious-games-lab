#!/usr/bin/env python3
"""
Math Quiz Application - Main Entry Point

A PyQt6-based adaptive math quiz application focused on practical
mathematics for physics and engineering students.

Features:
- Adaptive difficulty based on performance (Khan Academy inspired)
- Practical, physics/engineering-flavored problems
- "Street-fighting math" estimation questions
- LaTeX rendering for mathematical expressions
- Embedded Matplotlib plots for graphical questions
- Power-test scoring with trivial answer detection

Usage:
    python main.py [--duration SECONDS]

    --duration: Quiz duration in seconds (default: 600 = 10 minutes)

Example:
    python main.py --duration 300  # 5 minute quiz
"""

import sys
import argparse

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from ui import MainWindow


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Adaptive Math Quiz Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                    # Default 10-minute quiz
    python main.py --duration 300     # 5-minute quiz
    python main.py --duration 900     # 15-minute quiz
        """
    )
    parser.add_argument(
        '--duration', '-d',
        type=int,
        default=600,
        help='Quiz duration in seconds (default: 600 = 10 minutes)'
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Create application
    app = QApplication(sys.argv)

    # Set application-wide font for better readability
    # Using larger fonts as specified for 1920x1080 "easy reading"
    font = QFont("DejaVu Sans", 12)
    app.setFont(font)

    # Set application style
    app.setStyle("Fusion")

    # Apply global stylesheet for consistent appearance
    app.setStyleSheet("""
        QMainWindow {
            background-color: #eceff1;
        }
        QToolTip {
            background-color: #424242;
            color: white;
            border: none;
            padding: 5px;
            font-size: 12px;
        }
    """)

    # Create and show main window
    window = MainWindow(duration=args.duration)
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
