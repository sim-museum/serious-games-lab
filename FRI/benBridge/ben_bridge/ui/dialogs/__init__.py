"""
Dialog windows for the BEN Bridge UI.
"""

from .player_config import PlayerConfigDialog
from .match_control import MatchControlDialog
from .deal_filter import DealFilterDialog
from .score_table import ScoreTableDialog
from .simulation import SimulationDialog
from .end_of_hand import EndOfHandDialog, PassedOutDialog
from .teams_score import TeamsScoreDialog
from .replay_view import ReplayViewDialog
from .deal_converter import DealConverterDialog
from .evaluate_dialog import EvaluateDialog
from .hand_evaluation_dialog import HandEvaluationDialog
from .auction_tricks_dialog import AuctionTricksDialog
from .claim_dialog import ClaimDialog
from .bid_list_dialog import BidListDialog
from .remark_dialog import RemarkDialog, ViewRemarkDialog
from .review_dialog import ReviewDialog
from .log_viewer_dialog import LogViewerDialog, PreviousLogsDialog
from .lead_signal_dialog import LeadSignalDialog, StrengthDialog, ConfigCheckDialog
from .minibridge_dialog import MiniBridgeDialog, RubberScoringDialog, MultiplayDialog

__all__ = [
    'PlayerConfigDialog',
    'MatchControlDialog',
    'DealFilterDialog',
    'ScoreTableDialog',
    'SimulationDialog',
    'EndOfHandDialog',
    'PassedOutDialog',
    'TeamsScoreDialog',
    'ReplayViewDialog',
    'DealConverterDialog',
    'EvaluateDialog',
    'HandEvaluationDialog',
    'AuctionTricksDialog',
    'ClaimDialog',
    'BidListDialog',
    'RemarkDialog',
    'ViewRemarkDialog',
    'ReviewDialog',
    'LogViewerDialog',
    'PreviousLogsDialog',
    'LeadSignalDialog',
    'StrengthDialog',
    'ConfigCheckDialog',
    'MiniBridgeDialog',
    'RubberScoringDialog',
    'MultiplayDialog',
]
