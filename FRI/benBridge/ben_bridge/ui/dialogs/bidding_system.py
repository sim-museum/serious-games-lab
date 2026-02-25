"""
Bidding System Selection Dialog - Choose and configure bidding systems.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QTabWidget, QWidget, QCheckBox, QGridLayout, QMessageBox,
    QTextEdit, QSplitter, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from pathlib import Path
from typing import Optional, Dict, List

from .dialog_style import apply_dialog_style


# Available bidding systems - only those that BEN is trained on
BIDDING_SYSTEMS = {
    "SAYC": {
        "name": "SAYC (Standard American Yellow Card)",
        "description": "Standard American with 5-card majors, strong NT (15-17), and standard conventions.",
        "conventions": ["Stayman", "Jacoby Transfers", "Blackwood", "Gerber", "Negative Doubles"],
    },
    "2/1": {
        "name": "2/1 Game Force",
        "description": "Modern 2/1 system with game-forcing 2-level responses, Bergen raises, and 1NT forcing.",
        "conventions": ["Stayman", "Jacoby Transfers", "Blackwood", "RKCB 1430", "Jacoby 2NT", "Bergen Raises", "Negative Doubles", "Support Doubles"],
    },
    "GIB": {
        "name": "GIB (BBO Default)",
        "description": "GIB robot bidding system used on BridgeBase Online. Similar to SAYC with some variations.",
        "conventions": ["Stayman", "Jacoby Transfers", "Blackwood", "Negative Doubles", "Weak Two Bids"],
    },
}

# Common conventions that can be toggled
CONVENTIONS = [
    ("Stayman", "2♣ response to 1NT asks for 4-card major"),
    ("Jacoby Transfers", "2♦/2♥ over 1NT transfers to hearts/spades"),
    ("Texas Transfers", "4♦/4♥ over 1NT transfers to hearts/spades at game level"),
    ("Blackwood", "4NT asks for aces (0-3 step responses)"),
    ("RKCB 1430", "Roman Key Card Blackwood with 1430 responses"),
    ("RKCB 3014", "Roman Key Card Blackwood with 3014 responses"),
    ("Gerber", "4♣ asks for aces after NT opening"),
    ("Jacoby 2NT", "Game-forcing raise of major with 4+ support"),
    ("Bergen Raises", "3♣/3♦ as constructive/limit raises of major"),
    ("Splinter Bids", "Double jump shift shows singleton/void with support"),
    ("Negative Doubles", "Double of overcall is takeout, not penalty"),
    ("Support Doubles", "Opener's double shows 3-card support"),
    ("Responsive Doubles", "Double by advancer after partner overcalls"),
    ("Lebensohl", "2NT as relay after opponent's interference"),
    ("New Minor Forcing", "Bid of new minor is artificial and forcing"),
    ("Fourth Suit Forcing", "Fourth suit bid is artificial and forcing"),
    ("Drury", "2♣ response to 3rd/4th seat major opening"),
    ("Weak Two Bids", "2♦/2♥/2♠ = 6-card suit, 5-10 HCP"),
    ("Strong 2♣", "2♣ opening = 22+ HCP or 8.5+ tricks"),
    ("Multi 2♦", "2♦ = weak two in either major"),
    ("Michaels Cue Bid", "Direct cue bid shows two-suiter"),
    ("Unusual 2NT", "Jump to 2NT shows minors"),
]


class BiddingSystemDialog(QDialog):
    """Dialog for selecting and configuring bidding systems."""

    def __init__(self, parent=None, current_system: str = "SAYC"):
        super().__init__(parent)
        self.current_system = current_system
        self.selected_conventions: Dict[str, bool] = {}

        self.setWindowTitle("Bidding Systems")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)
        apply_dialog_style(self)

        self._setup_ui()
        self._load_system(current_system)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Create tabs
        tabs = QTabWidget()

        # System Selection Tab
        system_tab = QWidget()
        system_layout = QVBoxLayout(system_tab)

        # System selector
        selector_group = QGroupBox("Select Bidding System")
        selector_layout = QHBoxLayout()

        selector_layout.addWidget(QLabel("System:"))
        self.system_combo = QComboBox()
        for key, info in BIDDING_SYSTEMS.items():
            self.system_combo.addItem(info["name"], key)
        self.system_combo.currentIndexChanged.connect(self._on_system_changed)
        selector_layout.addWidget(self.system_combo, stretch=1)

        selector_group.setLayout(selector_layout)
        system_layout.addWidget(selector_group)

        # System description
        desc_group = QGroupBox("System Description")
        desc_layout = QVBoxLayout()

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        self.desc_text.setMaximumHeight(100)
        desc_layout.addWidget(self.desc_text)

        desc_group.setLayout(desc_layout)
        system_layout.addWidget(desc_group)

        # Included conventions
        conv_group = QGroupBox("Included Conventions")
        conv_layout = QVBoxLayout()

        self.conventions_list = QListWidget()
        self.conventions_list.setMaximumHeight(150)
        conv_layout.addWidget(self.conventions_list)

        conv_group.setLayout(conv_layout)
        system_layout.addWidget(conv_group)

        system_layout.addStretch()
        tabs.addTab(system_tab, "System")

        # Conventions Tab
        conventions_tab = QWidget()
        conventions_layout = QVBoxLayout(conventions_tab)

        conventions_layout.addWidget(QLabel("Enable/disable individual conventions:"))

        # Scrollable convention checkboxes
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        conv_widget = QWidget()
        conv_widget.setStyleSheet("background-color: #ffffff;")
        conv_grid = QGridLayout(conv_widget)
        conv_grid.setColumnStretch(1, 1)

        self.convention_checks: Dict[str, QCheckBox] = {}
        for i, (name, desc) in enumerate(CONVENTIONS):
            check = QCheckBox(name)
            check.setToolTip(desc)
            self.convention_checks[name] = check
            conv_grid.addWidget(check, i, 0)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #333333; background-color: transparent;")
            desc_label.setWordWrap(True)
            conv_grid.addWidget(desc_label, i, 1)

        scroll.setWidget(conv_widget)
        conventions_layout.addWidget(scroll)

        tabs.addTab(conventions_tab, "Conventions")

        # N/S vs E/W Tab
        pairs_tab = QWidget()
        pairs_layout = QVBoxLayout(pairs_tab)

        pairs_layout.addWidget(QLabel("Configure different systems for each pair:"))

        ns_group = QGroupBox("North-South System")
        ns_layout = QHBoxLayout()
        ns_layout.addWidget(QLabel("System:"))
        self.ns_system_combo = QComboBox()
        for key, info in BIDDING_SYSTEMS.items():
            self.ns_system_combo.addItem(info["name"], key)
        self.ns_system_combo.currentIndexChanged.connect(self._on_ns_system_changed)
        ns_layout.addWidget(self.ns_system_combo, stretch=1)
        ns_group.setLayout(ns_layout)
        pairs_layout.addWidget(ns_group)

        ew_group = QGroupBox("East-West System")
        ew_layout = QHBoxLayout()
        ew_layout.addWidget(QLabel("System:"))
        self.ew_system_combo = QComboBox()
        for key, info in BIDDING_SYSTEMS.items():
            self.ew_system_combo.addItem(info["name"], key)
        ew_layout.addWidget(self.ew_system_combo, stretch=1)
        ew_group.setLayout(ew_layout)
        pairs_layout.addWidget(ew_group)

        self.same_system_check = QCheckBox("Use same system for both pairs")
        self.same_system_check.setChecked(False)  # Default unchecked so both can be set independently
        self.same_system_check.toggled.connect(self._on_same_system_toggled)
        pairs_layout.addWidget(self.same_system_check)

        pairs_layout.addStretch()
        tabs.addTab(pairs_tab, "N/S vs E/W")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QHBoxLayout()

        load_btn = QPushButton("Load from File...")
        load_btn.clicked.connect(self._on_load_file)
        button_layout.addWidget(load_btn)

        save_btn = QPushButton("Save to File...")
        save_btn.clicked.connect(self._on_save_file)
        button_layout.addWidget(save_btn)

        button_layout.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Initial state - both combos enabled by default
        self._on_same_system_toggled(False)

    def _load_system(self, system_key: str):
        """Load a bidding system configuration."""
        # Normalize system key (handle engine aliases)
        key_map = {
            "21GF": "2/1",
            "2/1GF": "2/1",
            "2-1": "2/1",
        }
        system_key = key_map.get(system_key.upper(), system_key)

        if system_key not in BIDDING_SYSTEMS:
            system_key = "SAYC"

        system = BIDDING_SYSTEMS[system_key]

        # Update combo box
        for i in range(self.system_combo.count()):
            if self.system_combo.itemData(i) == system_key:
                self.system_combo.setCurrentIndex(i)
                break

        # Update description
        self.desc_text.setText(system["description"])

        # Update conventions list
        self.conventions_list.clear()
        for conv in system["conventions"]:
            self.conventions_list.addItem(conv)

        # Update convention checkboxes
        for name, check in self.convention_checks.items():
            check.setChecked(name in system["conventions"])

        self.current_system = system_key

    def _on_system_changed(self, index: int):
        """Handle system selection change on System tab."""
        system_key = self.system_combo.itemData(index)
        self._load_system(system_key)
        # Sync N/S combo on the pairs tab
        self.ns_system_combo.blockSignals(True)
        self.ns_system_combo.setCurrentIndex(index)
        self.ns_system_combo.blockSignals(False)
        if self.same_system_check.isChecked():
            self.ew_system_combo.setCurrentIndex(index)

    def _on_ns_system_changed(self, index: int):
        """Handle N/S system selection change on pairs tab."""
        system_key = self.ns_system_combo.itemData(index)
        self.current_system = system_key
        # Sync the main System tab combo
        self.system_combo.blockSignals(True)
        self.system_combo.setCurrentIndex(index)
        self.system_combo.blockSignals(False)
        # Update description and conventions
        if system_key in BIDDING_SYSTEMS:
            system = BIDDING_SYSTEMS[system_key]
            self.desc_text.setText(system["description"])
            self.conventions_list.clear()
            for conv in system["conventions"]:
                self.conventions_list.addItem(conv)
        # Sync E/W if same system is checked
        if self.same_system_check.isChecked():
            self.ew_system_combo.setCurrentIndex(index)

    def _on_same_system_toggled(self, checked: bool):
        """Handle same system checkbox toggle."""
        self.ew_system_combo.setEnabled(not checked)
        if checked:
            self.ew_system_combo.setCurrentIndex(self.ns_system_combo.currentIndex())

    def _on_load_file(self):
        """Load bidding system from file."""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Bidding System", "CONFIG/BIDRULE/",
            "Bidding System Files (*.bsc *.json);;All Files (*)"
        )
        if filename:
            QMessageBox.information(self, "Load",
                                   f"Loading from {filename} - not yet implemented")

    def _on_save_file(self):
        """Save bidding system to file."""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Bidding System", "CONFIG/BIDRULE/",
            "Bidding System Files (*.bsc);;All Files (*)"
        )
        if filename:
            QMessageBox.information(self, "Save",
                                   f"Saving to {filename} - not yet implemented")

    def _on_apply(self):
        """Apply the current settings without closing."""
        self._apply_settings()
        # Use the N/S system (which is the primary system selection)
        system_key = self.ns_system_combo.currentData()
        self.current_system = system_key
        # Also update the main System tab combo to stay in sync
        for i in range(self.system_combo.count()):
            if self.system_combo.itemData(i) == system_key:
                self.system_combo.blockSignals(True)
                self.system_combo.setCurrentIndex(i)
                self.system_combo.blockSignals(False)
                break
        from .dialog_style import styled_info
        ns_system = BIDDING_SYSTEMS[self.ns_system_combo.currentData()]['name']
        ew_system = BIDDING_SYSTEMS[self.ew_system_combo.currentData()]['name']
        if ns_system == ew_system:
            styled_info(self, "Applied", f"Bidding system set to: {ns_system}")
        else:
            styled_info(self, "Applied", f"N/S system: {ns_system}\nE/W system: {ew_system}")

    def _apply_settings(self):
        """Apply bidding system settings."""
        # Collect enabled conventions
        self.selected_conventions = {}
        for name, check in self.convention_checks.items():
            self.selected_conventions[name] = check.isChecked()

    def get_system(self) -> str:
        """Get the selected system key."""
        return self.system_combo.currentData()

    def get_ns_system(self) -> str:
        """Get N/S system key."""
        return self.ns_system_combo.currentData()

    def get_ew_system(self) -> str:
        """Get E/W system key."""
        if self.same_system_check.isChecked():
            return self.ns_system_combo.currentData()
        return self.ew_system_combo.currentData()

    def get_conventions(self) -> Dict[str, bool]:
        """Get selected conventions."""
        return {name: check.isChecked() for name, check in self.convention_checks.items()}
