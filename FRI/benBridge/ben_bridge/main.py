#!/usr/bin/env python3
"""
BEN Bridge - A PyQt6 bridge application using the BEN engine.
Classic desktop Bridge interface.

Usage:
    python main.py
"""

import sys
import os

# Suppress TensorFlow warnings before importing anything else
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Ensure we can find our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QTimer

# Set up logging
from logging_config import setup_logging, get_logger

def exception_hook(exc_type, exc_value, exc_tb):
    """Global exception handler to log uncaught exceptions."""
    import traceback
    logger = get_logger()
    logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_tb))
    # Still show to user
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    QMessageBox.critical(None, "Unexpected Error",
                        f"An unexpected error occurred:\n\n{exc_value}\n\n"
                        "See the log file for details.")

def main():
    # Set up logging (file + console)
    from logging_config import get_default_log_path
    logger = setup_logging(log_file=get_default_log_path(), console=False)
    logger.info("Starting BEN Bridge application")

    # Install global exception handler
    sys.excepthook = exception_hook

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("BEN Bridge")
    app.setOrganizationName("Bridge")
    app.setApplicationVersion("1.0.0")

    # Set application style
    app.setStyle("Fusion")

    # Set application-wide styling for proper contrast
    app.setStyleSheet("""
        QMenu {
            background-color: #f0f0f0;
            color: #000000;
            border: 1px solid #606060;
            padding: 4px;
        }
        QMenu::item {
            background-color: #f0f0f0;
            padding: 6px 30px 6px 20px;
            color: #000000;
        }
        QMenu::item:selected {
            background-color: #3070b0;
            color: #ffffff;
        }
        QMenu::item:disabled {
            color: #808080;
        }
        QMenu::separator {
            height: 1px;
            background-color: #a0a0a0;
            margin: 4px 10px;
        }
        QDialog {
            background-color: #f0f0f0;
            color: #000000;
        }
        QDialog QGroupBox {
            background-color: #f8f8f8;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
            color: #000000;
        }
        QDialog QGroupBox::title {
            color: #000000;
        }
        QDialog QLabel {
            color: #000000;
        }
        QDialog QComboBox {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #a0a0a0;
            padding: 4px;
        }
        QDialog QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #000000;
            selection-background-color: #3070b0;
            selection-color: #ffffff;
        }
        QDialog QListWidget {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #a0a0a0;
        }
        QDialog QTextEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #a0a0a0;
        }
        QDialog QCheckBox {
            color: #000000;
        }
        QDialog QPushButton {
            background-color: #e0e0e0;
            color: #000000;
            border: 1px solid #a0a0a0;
            padding: 6px 12px;
            border-radius: 3px;
        }
        QDialog QPushButton:hover {
            background-color: #d0d0d0;
        }
        QDialog QPushButton:pressed {
            background-color: #c0c0c0;
        }
        QDialog QTabWidget::pane {
            background-color: #f0f0f0;
            border: 1px solid #c0c0c0;
        }
        QDialog QTabBar::tab {
            background-color: #e0e0e0;
            color: #000000;
            padding: 6px 12px;
            border: 1px solid #c0c0c0;
            border-bottom: none;
        }
        QDialog QTabBar::tab:selected {
            background-color: #f0f0f0;
        }
        QDialog QScrollArea {
            background-color: #f0f0f0;
            border: 1px solid #c0c0c0;
        }
        QComboBox QAbstractItemView {
            background-color: #f0f0f0;
            color: #000000;
            selection-background-color: #3070b0;
            selection-color: #ffffff;
        }
    """)

    # Show splash screen
    splash_pix = QPixmap(400, 250)
    splash_pix.fill(Qt.GlobalColor.white)

    splash = QSplashScreen(splash_pix)
    splash.setFont(QFont("Arial", 14))
    splash.showMessage(
        "BEN Bridge\n\nLoading BEN Engine...\n\nPowered by Neural Networks",
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
        Qt.GlobalColor.darkBlue
    )
    splash.show()
    app.processEvents()

    try:
        # Import main window (this triggers TensorFlow loading)
        logger.info("Loading TensorFlow and BEN engine...")
        from ui.main_window import MainWindow

        # Create and show main window
        window = MainWindow()
        logger.info("Main window created successfully")

        # Close splash and show window
        def show_main():
            splash.finish(window)
            window.show()
            logger.info("Application ready")

        QTimer.singleShot(1000, show_main)

        # Run application
        exit_code = app.exec()
        logger.info(f"Application exiting with code {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.exception("Failed to start application")
        splash.close()
        QMessageBox.critical(None, "Startup Error",
                            f"Failed to start BEN Bridge:\n\n{e}\n\n"
                            "Make sure BEN engine is properly installed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
