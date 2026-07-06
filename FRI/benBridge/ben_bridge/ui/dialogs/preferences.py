"""
Preferences Dialog - Configure user preferences for BEN Bridge.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QRadioButton, QCheckBox, QComboBox, QPushButton, QSlider,
    QButtonGroup, QGridLayout, QTabWidget, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from ben_backend.config import (
    ConfigManager, PreferencesConfig, SuitLayout,
    get_config_manager
)

from .dialog_style import apply_dialog_style


class PreferencesDialog(QDialog):
    """Dialog for configuring user preferences."""

    # Signal emitted when settings are applied (for Apply button)
    settings_applied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.prefs = self.config_manager.config.preferences

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(450)
        apply_dialog_style(self)
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget for organized preferences
        tabs = QTabWidget()

        # Mouse & Input tab
        mouse_tab = self._create_mouse_tab()
        tabs.addTab(mouse_tab, "Mouse && Input")

        # Display tab
        display_tab = self._create_display_tab()
        tabs.addTab(display_tab, "Display")

        # Bidding tab
        bidding_tab = self._create_bidding_tab()
        tabs.addTab(bidding_tab, "Bidding")

        # Logging tab
        logging_tab = self._create_logging_tab()
        tabs.addTab(logging_tab, "Logging")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(apply_btn)

        defaults_btn = QPushButton("Defaults")
        defaults_btn.clicked.connect(self._reset_defaults)
        button_layout.addWidget(defaults_btn)

        layout.addLayout(button_layout)

    def _create_mouse_tab(self) -> QWidget:
        """Create mouse and input settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Click handling
        click_group = QGroupBox("Card Selection")
        click_layout = QVBoxLayout()

        self.click_button_group = QButtonGroup(self)

        self.single_click_radio = QRadioButton("Single click to select and play card")
        self.click_button_group.addButton(self.single_click_radio, 0)
        click_layout.addWidget(self.single_click_radio)

        self.double_click_radio = QRadioButton("Double click to play card (single click to select)")
        self.click_button_group.addButton(self.double_click_radio, 1)
        click_layout.addWidget(self.double_click_radio)

        click_group.setLayout(click_layout)
        layout.addWidget(click_group)

        # Animation speed
        anim_group = QGroupBox("Animation")
        anim_layout = QGridLayout()

        anim_layout.addWidget(QLabel("Card movement speed:"), 0, 0)
        self.anim_slider = QSlider(Qt.Orientation.Horizontal)
        self.anim_slider.setRange(0, 100)
        self.anim_slider.setValue(50)
        anim_layout.addWidget(self.anim_slider, 0, 1)

        self.anim_label = QLabel("Medium")
        anim_layout.addWidget(self.anim_label, 0, 2)
        self.anim_slider.valueChanged.connect(self._update_anim_label)

        anim_group.setLayout(anim_layout)
        layout.addWidget(anim_group)

        # Computer play options
        play_group = QGroupBox("Computer Card Play")
        play_layout = QVBoxLayout()

        self.dd_play_check = QCheckBox("Use double-dummy optimal card play")
        self.dd_play_check.setToolTip(
            "When enabled, computer players will use the double-dummy solver\n"
            "to find optimal card plays. This is stronger but slower."
        )
        play_layout.addWidget(self.dd_play_check)

        play_group.setLayout(play_layout)
        layout.addWidget(play_group)

        layout.addStretch()
        return widget

    def _create_display_tab(self) -> QWidget:
        """Create display settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Hand display
        hand_group = QGroupBox("Hand Display")
        hand_layout = QVBoxLayout()

        # Suit layout
        suit_layout = QHBoxLayout()
        suit_layout.addWidget(QLabel("Suit order:"))
        self.suit_layout_combo = QComboBox()
        self.suit_layout_combo.addItems([
            "Spades - Hearts - Diamonds - Clubs (SHDC)",
            "Spades - Hearts - Clubs - Diamonds (SHCD)"
        ])
        suit_layout.addWidget(self.suit_layout_combo)
        hand_layout.addLayout(suit_layout)

        # N/S swap
        self.swap_ns_check = QCheckBox("Swap North/South when North is declarer")
        hand_layout.addWidget(self.swap_ns_check)

        # Card style
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Card style:"))
        self.card_style_combo = QComboBox()
        self.card_style_combo.addItems(["Graphical cards", "Symbol cards", "Text cards"])
        style_layout.addWidget(self.card_style_combo)
        hand_layout.addLayout(style_layout)

        hand_group.setLayout(hand_layout)
        layout.addWidget(hand_group)

        # Table display
        table_group = QGroupBox("Table Display")
        table_layout = QVBoxLayout()

        self.show_played_cards_check = QCheckBox("Show played cards on table")
        self.show_played_cards_check.setChecked(True)
        table_layout.addWidget(self.show_played_cards_check)

        self.highlight_playable_check = QCheckBox("Highlight playable cards")
        self.highlight_playable_check.setChecked(True)
        table_layout.addWidget(self.highlight_playable_check)

        self.legacy_colors_check = QCheckBox("Legacy colors (red and black only)")
        self.legacy_colors_check.setToolTip(
            "Use traditional two-color suits:\n"
            "Spades/Clubs = Black, Hearts/Diamonds = Red"
        )
        table_layout.addWidget(self.legacy_colors_check)

        self.show_ben_analysis_check = QCheckBox("Show BEN bid analysis panel")
        self.show_ben_analysis_check.setToolTip(
            "Show the BEN bid analysis panel during bidding.\n"
            "Displays BEN's recommended bid and candidate scores."
        )
        table_layout.addWidget(self.show_ben_analysis_check)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        layout.addStretch()
        return widget

    def _create_bidding_tab(self) -> QWidget:
        """Create bidding display settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Bidding display
        bid_group = QGroupBox("Bidding Display")
        bid_layout = QVBoxLayout()

        # Start position
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Bidding box starts with:"))
        self.bid_start_combo = QComboBox()
        self.bid_start_combo.addItems(["West (standard)", "South (your hand first)"])
        start_layout.addWidget(self.bid_start_combo)
        bid_layout.addLayout(start_layout)

        # Alert marks
        self.show_alerts_check = QCheckBox("Show alert marks on artificial/alertable bids")
        self.show_alerts_check.setChecked(True)
        bid_layout.addWidget(self.show_alerts_check)

        # Bid explanation
        self.auto_explain_check = QCheckBox("Auto-explain bids on hover")
        self.auto_explain_check.setChecked(True)
        bid_layout.addWidget(self.auto_explain_check)

        bid_group.setLayout(bid_layout)
        layout.addWidget(bid_group)

        # Convention display
        conv_group = QGroupBox("Convention Display")
        conv_layout = QVBoxLayout()

        self.show_hcp_range_check = QCheckBox("Show HCP range for bids")
        self.show_hcp_range_check.setChecked(True)
        conv_layout.addWidget(self.show_hcp_range_check)

        self.show_suit_length_check = QCheckBox("Show suit length requirements")
        self.show_suit_length_check.setChecked(True)
        conv_layout.addWidget(self.show_suit_length_check)

        conv_group.setLayout(conv_layout)
        layout.addWidget(conv_group)

        layout.addStretch()
        return widget

    def _create_logging_tab(self) -> QWidget:
        """Create logging settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Log settings
        log_group = QGroupBox("Game Logging")
        log_layout = QVBoxLayout()

        self.log_enabled_check = QCheckBox("Enable automatic logging of completed hands")
        log_layout.addWidget(self.log_enabled_check)

        # Log format
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Log format:"))
        self.log_format_combo = QComboBox()
        self.log_format_combo.addItems(["BDL (BEN Bridge format)", "PBN (Portable Bridge Notation)"])
        format_layout.addWidget(self.log_format_combo)
        log_layout.addLayout(format_layout)

        # Log location
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(QLabel("Log directory:"))
        self.log_dir_label = QLabel("DATA/LOG/")
        loc_layout.addWidget(self.log_dir_label)
        loc_layout.addStretch()
        log_layout.addLayout(loc_layout)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Pavlicek settings
        pav_group = QGroupBox("Deal Identification")
        pav_layout = QVBoxLayout()

        self.use_pavlicek_check = QCheckBox("Use Pavlicek deal numbers in logs")
        self.use_pavlicek_check.setChecked(True)
        pav_layout.addWidget(self.use_pavlicek_check)

        pav_group.setLayout(pav_layout)
        layout.addWidget(pav_group)

        layout.addStretch()
        return widget

    def _load_current_settings(self):
        """Load current configuration into dialog."""
        # Mouse settings
        if self.prefs.single_click:
            self.single_click_radio.setChecked(True)
        else:
            self.double_click_radio.setChecked(True)

        self.anim_slider.setValue(int(self.prefs.moved_cards_speed * 100))

        # DD play setting
        self.dd_play_check.setChecked(self.prefs.use_double_dummy_play)

        # Display settings
        if self.prefs.suit_layout == SuitLayout.SHDC:
            self.suit_layout_combo.setCurrentIndex(0)
        else:
            self.suit_layout_combo.setCurrentIndex(1)

        self.swap_ns_check.setChecked(self.prefs.swap_ns_declarer)
        self.legacy_colors_check.setChecked(self.prefs.legacy_colors)
        self.show_ben_analysis_check.setChecked(self.prefs.show_ben_bid_analysis)

        # Bidding settings
        self.show_alerts_check.setChecked(self.prefs.show_alert_marks)

        # Logging settings
        self.log_enabled_check.setChecked(self.prefs.log_enabled)
        if self.prefs.log_as_pbn:
            self.log_format_combo.setCurrentIndex(1)
        else:
            self.log_format_combo.setCurrentIndex(0)

    def _save_settings(self):
        """Save dialog settings to configuration."""
        # Mouse settings
        self.prefs.single_click = self.single_click_radio.isChecked()
        self.prefs.moved_cards_speed = self.anim_slider.value() / 100.0

        # DD play setting
        self.prefs.use_double_dummy_play = self.dd_play_check.isChecked()

        # Display settings
        if self.suit_layout_combo.currentIndex() == 0:
            self.prefs.suit_layout = SuitLayout.SHDC
        else:
            self.prefs.suit_layout = SuitLayout.SHCD

        self.prefs.swap_ns_declarer = self.swap_ns_check.isChecked()
        self.prefs.legacy_colors = self.legacy_colors_check.isChecked()
        self.prefs.show_ben_bid_analysis = self.show_ben_analysis_check.isChecked()

        # Apply suit color mode immediately
        from ..styles import set_suit_color_mode, SuitColorMode
        if self.prefs.legacy_colors:
            set_suit_color_mode(SuitColorMode.TRADITIONAL)
        else:
            set_suit_color_mode(SuitColorMode.FOUR_COLOR)

        # Bidding settings
        self.prefs.show_alert_marks = self.show_alerts_check.isChecked()

        # Logging settings
        self.prefs.log_enabled = self.log_enabled_check.isChecked()
        self.prefs.log_as_pbn = (self.log_format_combo.currentIndex() == 1)

        # Save to file
        self.config_manager.save_preferences()

    def _update_anim_label(self, value: int):
        """Update animation speed label."""
        if value < 25:
            self.anim_label.setText("Fast")
        elif value < 50:
            self.anim_label.setText("Medium-Fast")
        elif value < 75:
            self.anim_label.setText("Medium")
        else:
            self.anim_label.setText("Slow")

    def _reset_defaults(self):
        """Reset to default settings."""
        self.single_click_radio.setChecked(True)
        self.anim_slider.setValue(50)
        self.suit_layout_combo.setCurrentIndex(0)
        self.swap_ns_check.setChecked(True)
        self.show_alerts_check.setChecked(True)
        self.log_enabled_check.setChecked(True)
        self.log_format_combo.setCurrentIndex(0)

    def _on_ok(self):
        """Handle OK button."""
        self._save_settings()
        self.accept()

    def _on_apply(self):
        """Handle Apply button."""
        self._save_settings()
        self.settings_applied.emit()
