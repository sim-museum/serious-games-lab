"""
Menu System for BEN Bridge.
"""

from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt
from typing import Callable, Dict, Optional


class MenuDefinition:
    """Menu item definitions."""

    FILE_MENU = [
        ("My &User Data...", "Ctrl+U", "user_data"),
        ("Own &Notes...", None, "own_notes"),
        None,  # separator
        ("&Print Current Hand...", "Ctrl+P", "print_hand"),
        ("Export to &HTML...", None, "export_html"),
        ("Export to P&BN...", None, "export_pbn"),
        None,
        ("&Restore Score Table...", None, "restore_scores"),
        ("&Initialize Configuration...", None, "init_config"),
        None,
        ("Save Match && E&xit", None, "save_exit"),
        ("E&xit", "Ctrl+Q", "exit"),
    ]

    CONFIG_MENU = [
        ("&Players...", "Ctrl+Shift+P", "config_players"),
        ("&Bidding Systems...", None, "config_bidding"),
        ("&Lead Conventions...", None, "config_lead"),
        ("&Signalling Conventions...", None, "config_signal"),
        ("Playing &Strength...", None, "config_strength"),
        ("P&references...", "Ctrl+,", "config_preferences"),
        ("La&nguage...", None, "config_language"),
        None,
        ("&Save Configuration...", None, "save_config"),
        ("Re&trieve Configuration...", None, "retrieve_config"),
        ("&Check! (Current Settings)", None, "check_config"),
    ]

    DEAL_MENU = [
        ("&Match Control...", "Ctrl+M", "match_control"),
        None,
        ("&Variations...", None, "deal_variations"),
        ("&Dealer and Vulnerability...", None, "deal_dealer_vuln"),
        ("&Repeat Deal", "F5", "repeat_deal"),
        ("Computer &Multiplay...", None, "computer_multiplay"),
        None,
        ("&Next Deal", "Ctrl+N", "next_deal"),
        ("&Previous Deal", "Ctrl+Shift+N", "prev_deal"),
        None,
        ("Load &Pavlicek Deal...", None, "load_pavlicek"),
    ]

    OWN_DEALS_MENU = [
        ("&Enter Deal...", "Ctrl+E", "enter_deal"),
        ("&Save Entered Deals to File...", None, "save_deals"),
        ("&Use Own Deals...", None, "use_own_deals"),
        None,
        ("&Import Deals...", None, "import_deals"),
        ("E&xport Deals...", None, "export_deals"),
    ]

    VIEW_MENU = [
        ("Open &All Hands", "F2", "show_all_hands"),
        ("View &Scoring Table...", "F8", "view_scores"),
        None,
        ("&Edit Remark...", None, "edit_remark"),
        ("View &Remark", None, "view_remark"),
        ("View &Auction and Played Tricks...", None, "view_auction_tricks"),
        None,
        ("Show &Current Log File", None, "show_current_log"),
        ("Show &Previous Log Files...", None, "show_prev_logs"),
        None,
        ("&IMP Table", None, "show_imp_table"),
        ("&Probabilities Table", None, "show_probabilities"),
        None,
        ("&Bidding Information", "F3", "toggle_bid_info"),
    ]

    EXTRAS_MENU = [
        ("&Check User Actions...", None, "check_actions"),
        ("&MiniBridge Mode", None, "minibridge_mode"),
        ("&One Player Mode", None, "one_player_mode"),
        ("Enter Contract &Result...", None, "enter_result"),
        None,
        ("&Double Dummy Analysis", "F9", "dd_analysis"),
        ("&Simulation...", None, "simulation"),
    ]

    NETWORK_MENU = [
        ("&Start Server...", None, "start_server"),
        ("&Connect to Server...", None, "connect_server"),
        None,
        ("&Disconnect", None, "network_disconnect"),
    ]

    HELP_MENU = [
        ("&User Guide", "F1", "user_guide"),
        ("&Keyboard Shortcuts", None, "shortcuts"),
        None,
        ("&About BEN Bridge", None, "about"),
    ]


class BenMenuBar:
    """Creates and manages the menu bar."""

    def __init__(self, parent, handlers: Dict[str, Callable]):
        """Initialize menu bar.

        Args:
            parent: Parent QMainWindow
            handlers: Dict mapping action names to handler functions
        """
        self.parent = parent
        self.handlers = handlers
        self.actions: Dict[str, QAction] = {}
        self.menubar: Optional[QMenuBar] = None

    def create_menubar(self) -> QMenuBar:
        """Create the complete menu bar."""
        self.menubar = self.parent.menuBar()

        # File menu
        self._create_menu("&File", MenuDefinition.FILE_MENU)

        # Configuration menu
        self._create_menu("&Configuration", MenuDefinition.CONFIG_MENU)

        # Deal menu
        self._create_menu("&Deal", MenuDefinition.DEAL_MENU)

        # Own Deals menu
        self._create_menu("&Own Deals", MenuDefinition.OWN_DEALS_MENU)

        # View menu
        self._create_menu("&View", MenuDefinition.VIEW_MENU)

        # Extras menu
        self._create_menu("E&xtras", MenuDefinition.EXTRAS_MENU)

        # Network menu
        self._create_menu("&Network", MenuDefinition.NETWORK_MENU)

        # Help menu
        self._create_menu("&Help", MenuDefinition.HELP_MENU)

        return self.menubar

    def _create_menu(self, title: str, items: list) -> QMenu:
        """Create a menu with the given items."""
        menu = self.menubar.addMenu(title)

        for item in items:
            if item is None:
                menu.addSeparator()
            else:
                label, shortcut, action_name = item
                action = QAction(label, self.parent)

                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))

                # Connect to handler if available
                if action_name in self.handlers:
                    action.triggered.connect(self.handlers[action_name])
                else:
                    # Placeholder - show "not implemented" message
                    action.triggered.connect(
                        lambda checked, name=action_name: self._not_implemented(name)
                    )

                # Store reference
                self.actions[action_name] = action
                menu.addAction(action)

        return menu

    def _not_implemented(self, name: str):
        """Show message for unimplemented features."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self.parent,
            "Not Implemented",
            f"The '{name}' feature is not yet implemented."
        )

    def get_action(self, name: str) -> Optional[QAction]:
        """Get an action by name."""
        return self.actions.get(name)

    def set_action_enabled(self, name: str, enabled: bool):
        """Enable or disable an action."""
        if name in self.actions:
            self.actions[name].setEnabled(enabled)

    def set_action_checked(self, name: str, checked: bool):
        """Set checkable action state."""
        if name in self.actions:
            action = self.actions[name]
            action.setCheckable(True)
            action.setChecked(checked)
