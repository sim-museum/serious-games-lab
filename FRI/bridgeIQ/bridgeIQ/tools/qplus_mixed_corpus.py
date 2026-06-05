"""PyQt6 app — generate three flavours of Q-Plus corpus, drive
Q-Plus through them unattended, and verify what was played.

Top-down hierarchy — five tabs, one job each:

  1. Calibration — capture all click positions in Q-Plus's UI
     (Configuration menu / bidding-system dialog / main action
     buttons + the 8 rollover positions that enable unattended
     >64-deal runs across multiple Q-Plus matches).
  2. Random deals — completely random hands, each paired with
     a random (NS_system, EW_system) drawn from the 5 systems
     we model (SAYC / TwoOverOne / StandardAcol / StandardFrench
     / Precision90M). Useful as an unbiased system comparison.
  3. Bidding system matrix — every (NS, EW) cell of the 5×5
     system grid gets N deals. Deterministic system labels;
     each batch of 25 deals is one complete pass through the
     matrix. Useful for cell-by-cell system effects.
  4. Slam-eligible deals — random deals filtered for high HCP
     (default ≥30 combined on one side, or 28+ with an 8+ card
     fit). Random system pairs. Useful for stress-testing slam
     bidding.
  5. Grand slam deals — same filter as tab 4 with a higher
     default threshold (37 HCP) and a bigger candidate scan
     budget, since grand-slam-strength hands are an order of
     magnitude rarer than small-slam ones.
  6. Help — the long version of this docstring.

Each corpus tab is self-contained: it has its own generate
controls, its own BDE banner + manifest table, and its own Run
/ Stop / Verify / Reconcile buttons with timing knobs. Tab state
is independent — generating a slam corpus on tab 4 doesn't
disturb the random corpus on tab 2.

Per run, the app:
  1. Generates deals + system pairs (deal seed + system seed,
     both persisted in the manifest).
  2. Writes the deals as one or more `.BDE` files into Q-Plus's
     `DATA/OWN-DEALS/`. Q-Plus's per-match cap is 64 deals, so
     >64-deal corpora are split into batch BDEs (b1_<seed>.BDE,
     b2_<seed>.BDE, …) with continuous deal numbering.
  3. Drives Q-Plus deal-by-deal: open Configuration → Bidding
     system, click the right NS radio + list entry + Set for
     N/S, then the EW radio + list entry + Set for E/W, then
     Close. Then Next deal → Start bidding → Autoplay.
  4. At each 64-deal batch boundary, AUTO-ROLLS-OVER if the 8
     rollover positions are calibrated: clicks File → Save
     match and exit, OKs the confirmation dialog, waits for
     Q-Plus to exit, relaunches Q-Plus via Wine, waits for the
     new window, clicks Own deals → Open → first row → Play,
     and resumes with the next batch's deal 1. Without rollover
     calibration, falls back to a QMessageBox the operator
     dismisses by hand. The 8 keys to capture are listed in
     KEYS_ROLLOVER.

Two extra deal-1 affordances avoid the "manually play deal 1"
chore:
  • The first deal of a run skips the "Next deal" click when
    "Q-Plus already on starting deal" is checked (default) —
    Q-Plus is already on board 1 after Own deals → Play, so
    clicking Next deal would skip past it.
  • The same skip is auto-armed after every successful rollover
    (Q-Plus is freshly on the next batch's deal 1 there too).

Verification: Q-Plus's BDL header only records one session-wide
bidding-system pair, so per-deal verification via the BDL isn't
possible. Two safeguards instead:
  • The Test button (Calibration tab) cycles ALL 5 systems
    through the dialog so every radio + every list entry +
    Set-N/S + Set-E/W is exercised once. If a radio is mis-
    calibrated, the wrong list shows up and the user sees it
    before launching a full run.
  • Per-deal verification screenshot (saved to
    /tmp/qplus_mixed_corpus_screenshots/, on by default) —
    taken AFTER Next deal but BEFORE Start bidding, so the
    same image captures both Q-Plus's status bar (active
    N/S+E/W tags) and the face-up deal layout (all four seats
    are Q-plus, so every card is visible). Each PNG is a
    single artifact you can audit against the manifest's PBN
    line for that deal.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.models import (  # noqa: E402
    BoardState, Card, Hand, Rank, Seat, Suit, Vulnerability,
)
from backend.qplus_driver import (  # noqa: E402
    qplus_log_dir, qplus_local_matches_dir,
    qplus_match_boards_own_deals,
    qplus_own_deals_dir, write_multi_deal_bde,
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject  # noqa: E402
from PyQt6.QtGui import QFont, QTextCursor, QScreen  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)


# ---------------------------------------------------------------------------
# System catalog — maps bridgeIQ system names to Q-Plus dialog choices.
# ---------------------------------------------------------------------------

SYSTEMS: List[Tuple[str, str, str]] = [
    ("SAYC",           "american",  "A-SAYC-I"),
    ("TwoOverOne",     "american",  "A-2-1-A"),
    ("StandardAcol",   "british",   "B-ACL-S"),
    ("StandardFrench", "french",    "F-FRA-M"),
    ("Precision90M",   "precision", "P-P90M-A"),
]
SYSTEM_NAMES = [s[0] for s in SYSTEMS]
SYSTEM_FAMILY = {s[0]: s[1] for s in SYSTEMS}
SYSTEM_TAG = {s[0]: s[2] for s in SYSTEMS}

KEYS_MENU = [
    ("config_menu",         "Configuration menu (top of Q-Plus)"),
    ("bidding_system_item", "‘Bidding system’ menu item"),
]
KEYS_RADIO = [
    ("radio_american",  "Radio: American"),
    ("radio_british",   "Radio: British"),
    ("radio_french",    "Radio: French"),
    ("radio_precision", "Radio: Precision"),
]
RADIO_FOR_FAMILY = {
    "american":  "radio_american",
    "british":   "radio_british",
    "french":    "radio_french",
    "precision": "radio_precision",
}
KEYS_LIST_ENTRY = [
    (f"list_{s[0]}", f"List entry for {s[0]} ({s[2]})")
    for s in SYSTEMS
]
KEYS_DIALOG_BTN = [
    ("set_ns_btn", "‘Set for N/S’ button"),
    ("set_ew_btn", "‘Set for E/W’ button"),
    ("close_btn",  "‘Close’ button"),
]
KEYS_MAIN_BTN = [
    ("next_deal",     "‘Next deal’ button"),
    ("start_bidding", "‘Start bidding’ button"),
    ("autoplay",      "‘Autoplay’ button"),
]
# Optional — only used to auto-dismiss Q-Plus's Simulation popup if
# it appears during a deal. Not required to run.
KEYS_OPTIONAL = [
    ("simulation_close_btn",
     "‘Close’ button on the ‘Simulation for …’ dialog (OPTIONAL — "
     "lets the app auto-dismiss simulation prompts)"),
    # Repeat-deal flow — only needed for the curated-corpus run
    # (same deal × 25 system pairs). Lets the harness explicitly
    # replay a deal so Q-Plus's per-match dedup-by-cards doesn't
    # collapse 25 identical-card entries into 1.
    ("deal_menu",
     "‘Deal’ menu in the menu bar (for Repeat deal — curated only)"),
    ("repeat_deal_item",
     "‘Repeat deal’ menu item (for Repeat deal — curated only)"),
    ("repeat_complete_radio",
     "Repeat-deal dialog ‘complete deal’ radio (curated only)"),
    ("repeat_computer_radio",
     "Repeat-deal dialog ‘Computer’ radio (curated only)"),
    ("repeat_ok_btn",
     "Repeat-deal dialog OK button (curated only)"),
    # Match End dialog — Q-Plus pops this when it hits its default
    # match-length cap (often 16 boards). Without these positions
    # calibrated, the harness will hang waiting for Next-deal when
    # the dialog is up. With them, the harness types the configured
    # # boards into the field and clicks Extend.
    ("match_end_boards_field",
     "Match End dialog ‘by # boards’ text field"),
    ("match_end_extend_btn",
     "Match End dialog ‘Extend the match’ button"),
]
# Rollover automation — clicks the app fires at every 64-deal
# batch boundary so the operator doesn't have to. All optional;
# unset = automated rollover disabled, app falls back to a
# QMessageBox prompt and the operator handles save+exit /
# relaunch / Own-deals-Play manually as before. Capture all 8
# to unlock fully unattended >64-deal runs.
KEYS_ROLLOVER = [
    # ─── Save match + exit (closes current Q-Plus) ───
    ("rollover_file_menu",
     "‘File’ menu in Q-Plus's menu bar (ROLLOVER: save+exit)"),
    ("rollover_save_exit_item",
     "‘Save match and exit’ item under the File menu "
     "(ROLLOVER)"),
    ("rollover_save_exit_ok",
     "‘OK’ / Yes button on Q-Plus's ‘Save and exit?’ "
     "confirmation dialog (ROLLOVER)"),
    # ─── Restart + dismiss splash ───
    ("rollover_splash_ok",
     "‘Ok’ button on Q-Plus's splash / activation popup that "
     "appears after launch — usually says ‘The activation is "
     "already done!’ (ROLLOVER)"),
    # ─── Open Manage and use own deals dialog ───
    ("rollover_own_deals_menu",
     "‘Own deals’ menu in the freshly-launched Q-Plus's "
     "menu bar (ROLLOVER)"),
    ("rollover_own_deals_open_item",
     "Menu item under ‘Own deals’ that opens the "
     "‘Manage and use own deals’ dialog (ROLLOVER — if "
     "‘Own deals’ opens the dialog directly, calibrate this "
     "to the same point as ‘rollover_own_deals_menu’)"),
    # ─── Load the next batch's BDE ───
    ("rollover_bde_2nd_row",
     "Second BDE row in the file-list inside the "
     "‘Manage and use own deals’ dialog — this is the next "
     "batch's BDE (b2_<seed>.BDE) when the previous batch "
     "(b1_<seed>.BDE) is still loaded (ROLLOVER)"),
    ("rollover_manage_deals_btn",
     "‘Deals’ button on the ‘Manage and use own deals’ "
     "dialog (ROLLOVER: opens the deal-selection dialog)"),
    ("rollover_deal_select_first",
     "First deal row in the deal-selection dialog (ROLLOVER: "
     "the batch starts at deal #1 of the new BDE)"),
    ("rollover_deal_select_ok",
     "‘OK’ button on the deal-selection dialog (ROLLOVER: "
     "dismisses the dialog and arms the chosen deal)"),
    ("rollover_play_btn",
     "‘Play’ button on the ‘Manage and use own deals’ "
     "dialog (ROLLOVER: actually loads + starts the chosen "
     "BDE; Close DOES NOT load it)"),
]
# First-load automation — clicked after Q-Plus is freshly launched
# (whether by us or by the operator) so the run proceeds with NO
# human interaction. Mirrors KEYS_ROLLOVER except the BDE row points
# at the FIRST (= newly written) BDE rather than the second / next
# batch. The dialog/menu navigation positions are SHARED with
# KEYS_ROLLOVER — only the BDE row differs.
KEYS_FIRST_LOAD = [
    ("bde_1st_row",
     "FIRST BDE row in the file-list inside the "
     "‘Manage and use own deals’ dialog — this is the BDE biq "
     "just wrote and the row biq auto-clicks at Run-time. "
     "(See rollover_bde_2nd_row for the next-batch row used "
     "during 64-deal rollovers.)"),
]
# Positions needed for the post-launch auto-load sequence (Own
# deals → Open → first BDE → Deals → first deal → OK → Play).
# All of these are already covered by KEYS_ROLLOVER except
# bde_1st_row (new in KEYS_FIRST_LOAD).
FIRST_LOAD_KEYS_FULL = (
    "rollover_own_deals_menu", "rollover_own_deals_open_item",
    "bde_1st_row",
    "rollover_manage_deals_btn", "rollover_deal_select_first",
    "rollover_deal_select_ok", "rollover_play_btn",
)
# Keys the run requires to be captured. Optional ones (simulation
# Close, repeat-deal, rollover, first-load) can be unset and the run
# still proceeds — they just fall back to manual operator action.
ALL_KEYS = (
    KEYS_MENU + KEYS_RADIO + KEYS_LIST_ENTRY
    + KEYS_DIALOG_BTN + KEYS_MAIN_BTN + KEYS_OPTIONAL
    + KEYS_ROLLOVER + KEYS_FIRST_LOAD
)
REQUIRED_KEYS = {k for k, _ in
                 (KEYS_MENU + KEYS_RADIO + KEYS_LIST_ENTRY
                  + KEYS_DIALOG_BTN + KEYS_MAIN_BTN)}
OPTIONAL_KEYS = ({k for k, _ in KEYS_OPTIONAL}
                 | {k for k, _ in KEYS_ROLLOVER}
                 | {k for k, _ in KEYS_FIRST_LOAD})
ROLLOVER_KEYS = {k for k, _ in KEYS_ROLLOVER}

SCREENSHOT_DIR = Path("/tmp/qplus_mixed_corpus_screenshots")
LOG_DIR = Path("/tmp/qplus_mixed_corpus_logs")
# Per-deal audit screenshots of the bidding-system dialog state
# captured AFTER all clicks have landed but BEFORE Close — the
# visual ground-truth for which systems Q-Plus is about to commit.
# Spot-check these post-run for any deal whose verify flagged a
# system mismatch.
AUDIT_DIR = Path("/tmp/qplus_mixed_corpus_audit")
# Where archived BDE corpora go on app startup. Files are MOVED out
# of Q-Plus's OWN-DEALS so Q-Plus can't accidentally re-load a stale
# corpus, but preserved here for reference / re-running later.
ARCHIVE_DIR = (Path(__file__).resolve().parent.parent
               / "data" / "qplus_corpora_archive")
# Q-Plus shipped / unrelated files — leave these alone in OWN-DEALS.
ARCHIVE_SKIP = {"EXAMPLE.BDE", "BEN_BRIDGE_RELAY.BDE"}


HELP_TEXT = """\
Q-Plus Corpus Builder — quick reference
========================================

Top-down workflow — six tabs, one job each:

  1. Calibration            — capture all click positions once.
  2. Random deals           — random hands × random (NS, EW) pairs.
  3. Bidding system matrix  — 4 slam-eligible base hands ×
                              25 (NS, EW) cells = 100 deals.
  4. Slam-eligible deals    — random hands, HCP ≥ 30 default.
  5. Grand slam deals       — random hands, HCP ≥ 37 default.
  6. Help                   — this text.

Each corpus tab is self-contained: generate, write BDE, manifest
table, Run / Stop, Verify / Reconcile all live within the tab.
Tabs hold independent state — you can have three different
corpora in flight simultaneously.

>64-deal corpora auto-roll over between Q-Plus matches: when
all 8 KEYS_ROLLOVER positions are calibrated, the app handles
File → Save match + exit → restart Q-Plus → Own deals → Open →
first row → Play with no operator action at the 64-deal break.
Without those positions, the run pauses with a QMessageBox at
each break and the operator does it by hand.

CORPUS TYPES
------------

* Random deals (tab 2). Pick deal seed + system seed + # deals.
  The deals are uniform-random; the (NS, EW) pair for each deal
  is also uniform-random over the 5×5 = 25 combinations. Useful
  for unbiased bridgeIQ-vs-Q-Plus comparison.

* Bidding system matrix (tab 3). Pick the deal seed and click
  Generate — no other knobs. The generator scans the random
  stream for hands likely to show system-dependent bidding
  (slam-eligible: HCP ≥ 28 on one side, or ≥ 26 with an 8+
  card fit) AND for which 25 unique spot-card permutations
  exist (HCP + shape held constant, only spot cards differ).
  The first 4 qualifying hands become base hands; each is
  expanded into 25 cells of the 5×5 (NS_system, EW_system)
  grid, EW spot cards perturbed per cell so Q-Plus sees each
  cell as a distinct deal. NS hands are identical across the
  25 cells of a given base hand, so biq's NS auction varies
  only with the NS system. Total: 4 × 25 = 100 deals. Cells
  are interleaved deal-by-deal so each contiguous block of 25
  is one complete pass through the matrix.

* Slam-eligible deals (tab 4). Pick deal seed + system seed +
  HCP threshold + # deals. The generator scans random deals and
  keeps those where either partnership has at least the
  threshold combined HCP, or (threshold − 2) HCP with an 8+
  card fit. System pairs are random. Useful for stress-testing
  slam bidding code paths.

* Grand slam deals (tab 5). Same generator as tab 4, with a
  higher default threshold (37 HCP) and a larger candidate
  scan budget. ~37 HCP combined is the standard grand-slam
  zone — at that strength the partnership has enough material
  for 13 tricks on typical distributions. Hands at this HCP
  level appear in only ~0.3% of random deals, so the scan
  budget defaults to 50 000 candidates (vs 5 000 for slam).

For all four: the BDE filename defaults to a short
seed-encoded name (r12345_67890.BDE, m12345.BDE,
s12345_67890.BDE, gs12345_67890.BDE) so each generated corpus
is unique on disk and Q-Plus's bottom-bar truncation can't
hide it.

PER-CORPUS WORKFLOW
-------------------

1. On the relevant corpus tab: set seeds + counts, click
   "Generate <type> corpus", review the manifest table, click
   "Write BDE to Q-Plus" — writes <filename>.BDE and
   <filename>.manifest.json into Q-Plus's OWN-DEALS. Corpora
   larger than 64 deals are split into batch BDEs (b1_<seed>.BDE,
   b2_<seed>.BDE, …) with continuous deal numbering. The BDE
   banner on the tab shows what filename Q-Plus should be
   displaying for visual cross-check during a run.

2. In Q-Plus
   * Every time this corpus-builder app starts up, it moves any
     BDE / .manifest.json files out of Q-Plus's OWN-DEALS
     directory into bridgeIQ/data/qplus_corpora_archive/ —
     timestamped so multiple sessions don't collide. That
     guarantees Q-Plus can't pick up a stale corpus by accident.
     EXAMPLE.BDE (Q-Plus shipped) and BEN_BRIDGE_RELAY.BDE
     are left in place.
   * BDE filename is just <deal_seed>_<system_seed>.BDE
     (e.g. 51768_19267.BDE) — short, so Q-Plus's bottom-bar
     truncation can't hide it.
   * In Q-Plus: Own deals → Open → <deal_seed>_<sys_seed>.BDE
     (the file the app just wrote).
   * In the "Manage and use own deals" dialog: click PLAY,
     not Close. Play forces Q-Plus to commit to this file as
     the active own-deals source; Close leaves Q-Plus's main
     screen showing whatever was active before. After Play,
     Q-Plus deals out board 1 face up and the bottom-left
     button changes to "Start bidding" — Q-Plus waits there
     for the next click. The app's default Run-tab setting
     ("Q-Plus already on starting deal" checked) recognises
     this state and skips the leading Next-deal click for
     deal 1 only, so the app drives deal 1 just like every
     other deal — no manual play needed.
   * OPTIONAL sanity check before launching a full Run: in
     the Run tab, click "Set systems for 'Start from deal #'
     only" with Start = 1, then watch deal 1 play out manually
     in Q-Plus. The corpus app's log window shows the
     manifest's deal in PBN form
     (`[Dealer "X"] [Vulnerable "…"] [Deal "X:S.H.D.C ⋯"]`) —
     compare the dealer / vulnerable / four hands against
     what Q-Plus displays. They must match. If they don't,
     Q-Plus loaded a different BDE; stop and reload. After
     this check, set Start = 2 AND UNCHECK "Q-Plus already
     on starting deal" before clicking Run.
   * ⚠ CRITICAL — Deal → Match control: confirm "# boards" is set
     to a value ≥ the size of this corpus (e.g. 200). Q-Plus
     resets this to its 16-board default on a clean start, on
     reinstall, and sometimes after save+exit. If you don't bump
     it, Q-Plus pops a Match End dialog every 16 boards and the
     run stalls until something dismisses it. The harness's
     "Auto-extend Match End by N boards" setting (Run tab) is
     a safety net — it auto-clicks Extend when Match End appears
     — but setting "# boards" up front means the dialog never
     fires in the first place. Set it ONCE per Q-Plus session,
     before clicking Run.
   * Confirm the bottom-left status bar reads the filename you
     just wrote (e.g. "51768_19267"). If you see anything else,
     Q-Plus is loading the wrong file.
   * Confirm Player setup has all 4 seats = Q-plus (otherwise
     E/W's bid box pops up and waits for you).
   * Make sure Q-Plus is the focused window before you go to
     the Run tab.

3. CALIBRATION tab — capture click positions
   In Q-Plus, hover the mouse over each target and click
   "Capture" in this app. A 3-second countdown samples the
   pointer position via xdotool. Positions persist in
   ~/.qplus_mixed_corpus.json.

   17 REQUIRED positions:
     Menus (2):
       - Configuration menu (top of Q-Plus window)
       - Bidding system menu item (inside Configuration)
     Family radios in the bidding-system dialog (4):
       - American, British, French, Precision
     System list entries (5) — one per bridgeIQ system. Each
     entry's position is captured AFTER clicking its family
     radio (the list refreshes).
     Dialog buttons (3): Set for N/S, Set for E/W, Close
     Q-Plus main UI (3): Next deal, Start bidding, Autoplay

   OPTIONAL positions (recommended for unattended >64-deal runs):
     Simulation Close (1) — auto-dismiss Q-Plus's Simulation
       popup that occasionally appears mid-bid (slam decisions,
       4NT responses).
     Repeat-deal sequence (5) — only needed for the (currently
       unused) curated workflow; safe to skip.
     Match End handling (2) — auto-extend the match when Q-Plus
       hits its '# boards' cap mid-corpus.
     Rollover automation (8) — the showstopper for unattended
       big runs. Captures the buttons needed for the app to do
       save+exit / relaunch Q-Plus / Own deals → Open → Play at
       every 64-deal batch boundary:
         * File menu
         * Save match and exit (under File)
         * Save+exit confirmation OK
         * Own deals menu (in the freshly-started Q-Plus)
         * Open / Import item (under Own deals)
         * First BDE row in the file-open dialog (the app moves
           stale BDEs aside so the right file is the only row)
         * OK / Open on the file dialog
         * Play on the Manage and use own deals dialog
       With all 8 captured + saved, runs longer than 64 deals
       complete entirely unattended. Without them, the run
       pauses with a QMessageBox at each batch boundary so the
       operator can drive Q-Plus through save+exit / relaunch /
       Play by hand.

   To calibrate the simulation Close button: start a deal in
   Q-Plus that's known to trigger a Simulation dialog (e.g.
   replay an old hand with a slam invite), capture, save.
   Then on subsequent runs the app will auto-dismiss.

   Click "Save calibration to disk" when finished.

4. TEST (calibration tab)
   "Test (cycle 5 mixed N/S≠E/W pairs + save screenshots)"
   opens the dialog 5 times with MIXED pairs:
     cycle 1: N/S=SAYC,           E/W=TwoOverOne
     cycle 2: N/S=TwoOverOne,     E/W=StandardAcol
     cycle 3: N/S=StandardAcol,   E/W=StandardFrench
     cycle 4: N/S=StandardFrench, E/W=Precision90M
     cycle 5: N/S=Precision90M,   E/W=SAYC

   This exercises EVERY system once as N/S and once as E/W —
   no symmetry that can let a broken Set-for-E/W hide behind a
   working Set-for-N/S.

   After each cycle a screenshot is saved to
   /tmp/qplus_mixed_corpus_screenshots/test_cycle_N_…png. The
   final post-test dialog lists the expected pair for each
   screenshot — verify Q-Plus's status bar tags match the
   filename's ns-/ew- tags.

   If any cycle's screenshot doesn't match its filename, that
   click position is miscalibrated.

5. RECOMMENDED START (per corpus tab)
   The fast path (no manual deal 1 play needed):
     * On the corpus tab (Random / Matrix / Slam): generate the
       corpus, click "Write BDE to Q-Plus".
     * In Q-Plus: Own deals → Open → the BDE the app just wrote
       → click PLAY (not Close). Q-Plus deals out board 1 face
       up; the bottom-left button changes to "Start bidding".
     * Back on the corpus tab: leave "Start from deal #" = 1.
       Confirm "Q-Plus already on starting deal" and "Save
       per-deal verification screenshot" are checked (both
       default-on).
     * Click Run on that corpus tab.

   For >64-deal corpora the app handles the 64-deal rollover
   automatically when all 8 KEYS_ROLLOVER positions are
   calibrated — see the Calibration tab section above.

   Where the log goes:
     * Every line in the log pane is also appended to
       /tmp/qplus_mixed_corpus_logs/session_<timestamp>.log so
       you have an audit trail of every PBN, every system pair
       set, and every screenshot path. Path is printed at the
       top of the log when the app starts.

6. RUN section (within each corpus tab) — drives the corpus
   Timing knobs:
     - Per-dialog-click pause: 50 ms default. Time between
       consecutive clicks inside the bidding-system dialog.
       Keep small.
     - After dialog close: 150 ms default. Time after the
       dialog disappears before the first main-UI click.
       Keep small.
     - After Next deal: 2 s. Time for Q-Plus to deal the new
       hand and display it. Adjust if you see the bidding click
       fire before cards appear.
     - After Start bidding: 25 s. Time for Q-Plus to finish
       the full auction. KEEP LARGE — some auctions go long.
     - Cardplay budget: 60 s. Time for Q-Plus to play out the
       deal after Autoplay. KEEP LARGE — some hands take time.
     - Start from deal #: 1 by default. Bump to resume after a
       Stop without re-doing earlier deals.
     - Q-Plus already on starting deal: on by default. When on,
       the very FIRST deal of a run skips the "Next deal" click
       and goes straight to setting systems + Start bidding —
       matches the state Q-Plus is in immediately after Own
       deals → Play (board 1 face up, bottom-left button
       reads "Start bidding"). Subsequent deals always click
       Next deal normally. Uncheck if you're resuming with
       Q-Plus on an earlier deal (e.g. you played deal 1 by
       hand and Q-Plus is now sitting on deal 1, waiting for
       Next deal to advance to deal 2).
     - Save per-deal verification screenshot: on by default.
       Each deal's Q-Plus window is screenshotted (cropped to
       the Q-Plus geometry) into
       /tmp/qplus_mixed_corpus_screenshots/ AFTER clicking
       Next deal and BEFORE clicking Start bidding. That's the
       only moment Q-Plus shows BOTH the new face-up deal
       layout AND the status bar with the systems we just set,
       so each PNG verifies two things in one shot:
         (1) status bar's N/S+E/W tags match the manifest's
             ns_system / ew_system for that deal,
         (2) the four hands match the manifest PBN line that
             was logged just above the screenshot path.
       Player setup must have all 4 seats = Q-plus so every
       card is face up — otherwise (2) can't be checked.

   Click "Run" to start. Status banner turns yellow while
   running, green when done. The log pane shows each step.
   Click "Stop" to abort after the current step (worker thread
   finishes its current click sequence).

7. POST-RUN VERIFICATION (within each corpus tab)
   After Q-Plus has flushed the BDL (File → Save match and exit),
   two buttons in the corpus tab's Run section help reconcile
   what was actually played against the manifest.

   "Verify BDL vs manifest (report only)":
     • Pick the BDL (default: most recent in Q-Plus's LOG dir).
     • Pick the manifest (default: the corpus this app session
       has loaded; otherwise the most recent .manifest.json in
       OWN-DEALS).
     • Reports per-deal mismatches in: dealer, vulnerability,
       N/S system, E/W system, cards (S/H/D/C per hand).
     • Cards are regenerated deterministically from the manifest's
       deal_seed for comparison.
     • Status banner summarises matched / total + issue count.

   "Reconcile manifest to BDL":
     • Same checks PLUS auto-fixes the manifest's system labels
       for deals whose cards still match (i.e. Q-Plus played the
       right layout but with a different system pair, usually
       from a one-off click misfire).
     • Card / dealer / vul mismatches are NEVER auto-fixed —
       those mean Q-Plus played a different deal and the
       resulting auction is in some sense not a corpus member.
     • A timestamped backup of the original manifest is written
       (foo.manifest.bak_<timestamp>.json) before the rewrite.
     • If the corpus is still loaded in this session, the
       in-memory system_pairs are updated from the rewritten
       manifest so subsequent runs see the corrected labels.

After the run
-------------

* Q-Plus only flushes a BDL (auction + cardplay log) on File →
  Save match and exit. Do that to get the final per-deal BDL
  output at DATA/LOG/log-NNN.bdl.
* The session-wide .Bidding cnv: header in the BDL only records
  the LAST setting (Q-Plus doesn't track per-deal system tags).
  For per-deal verification: use the screenshots from
  /tmp/qplus_mixed_corpus_screenshots/ — Q-Plus's status bar
  text in each shows the system pair active for that deal.
* The manifest JSON at OWN-DEALS/BB_MIXED.manifest.json is the
  ground-truth list of (deal#, dealer, vul, NS_system,
  EW_system) for later cross-checking.

Common pitfalls
---------------

* Forgetting to set # boards in Deal/Match control ≥ corpus
  size — Q-Plus will stop early.
* Clicking "Play" instead of "Close" on the "Manage and use
  own deals" dialog — Q-Plus then auto-plays deal 1 with
  whatever system was last set, wasting it. Always click
  Close, then let the app drive Next-deal.
* Window focus drift — if any other window grabs focus
  during the run, mouse clicks may land in the wrong place.
  Don't touch the mouse / keyboard during the run.
* xdotool windowactivate --sync hanging — the app uses the
  non-sync variant; if you still see multi-second per-click
  pauses, check whether another tool is grabbing X focus.

Files written
-------------

  DATA/OWN-DEALS/BB_MIXED.BDE             # the 100 deals
  DATA/OWN-DEALS/BB_MIXED.manifest.json   # per-deal manifest
  DATA/LOG/log-NNN.bdl                    # Q-Plus's output
                                          # (on Save match+exit)
  ~/.qplus_mixed_corpus.json              # cached calibration
  /tmp/qplus_mixed_corpus_screenshots/    # optional per-deal
                                          # screenshots
"""


# ---------------------------------------------------------------------------
# Mouse helpers (xdotool)
# ---------------------------------------------------------------------------

def xdo(*args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["xdotool", *args],
        capture_output=True, text=True, check=check)
    return out.stdout.strip()


def get_mouse() -> Tuple[int, int]:
    out = xdo("getmouselocation", "--shell")
    env = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return int(env["X"]), int(env["Y"])


def click_at(x: int, y: int, delay_ms: int = 30):
    """Move the pointer to (x,y) and click. `delay_ms` is the gap
    between mousemove and click — needs to be ≥ ~20 ms or Wine may
    not register the pointer position before the button event."""
    xdo("mousemove", str(x), str(y))
    time.sleep(delay_ms / 1000.0)
    xdo("click", "1")


def find_qplus_window() -> Optional[int]:
    """Return the X window id of the real Q-Plus Bridge process, or
    None if it's not running.

    The corpus app's OWN window title is "Q-Plus Corpus Builder", which
    also contains "Q-Plus" — naive `xdotool search --name "Q-Plus"`
    would match the corpus app itself and break the
    "launch if not running" detection. Filter out any window whose
    title contains "Corpus Builder" so only the actual Q-Plus Bridge
    window qualifies.
    """
    try:
        out = xdo("search", "--name", "Q-Plus", check=False)
        for tok in out.split():
            if not tok.isdigit():
                continue
            wid = int(tok)
            try:
                name = xdo("getwindowname", str(wid),
                           check=False).strip()
            except Exception:
                name = ""
            if "Corpus Builder" in name:
                continue  # our own app's window — skip
            return wid
    except Exception:
        return None
    return None


def grab_qplus_screenshot(out_path: Path,
                          window_id: Optional[int]) -> Tuple[bool, str]:
    """Save a screenshot, cropped to the Q-Plus window if we can get
    its geometry. Returns (ok, message)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import ImageGrab
    except Exception as ex:
        return False, f"PIL not available: {ex!r}"
    bbox = None
    if window_id:
        try:
            out = xdo("getwindowgeometry", "--shell", str(window_id),
                      check=False)
            env: Dict[str, str] = {}
            for line in out.splitlines():
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
            if all(k in env for k in ("X", "Y", "WIDTH", "HEIGHT")):
                x = int(env["X"]); y = int(env["Y"])
                w = int(env["WIDTH"]); h = int(env["HEIGHT"])
                bbox = (x, y, x + w, y + h)
        except Exception:
            bbox = None
    try:
        img = ImageGrab.grab(bbox=bbox)
        img.save(str(out_path))
        return True, f"saved {out_path}"
    except Exception as ex:
        return False, f"grab failed: {ex!r}"


# ---------------------------------------------------------------------------
# Corpus generation
# ---------------------------------------------------------------------------

def gen_random_deals(n: int, seed: int) -> List[BoardState]:
    rng = random.Random(seed)
    deck = [Card(s, r)
            for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
            for r in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                      Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                      Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE,
                      Rank.TWO)]
    out: List[BoardState] = []
    for i in range(n):
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hands = {
            Seat.NORTH: Hand(cards=shuffled[0:13]),
            Seat.EAST:  Hand(cards=shuffled[13:26]),
            Seat.SOUTH: Hand(cards=shuffled[26:39]),
            Seat.WEST:  Hand(cards=shuffled[39:52]),
        }
        n_board = i + 1
        dealer, vuln = BoardState._board_dealer_vuln(n_board)
        out.append(BoardState(board_number=n_board, dealer=dealer,
                              vulnerability=vuln, hands=hands))
    return out


def gen_random_system_pairs(n: int, seed: int) -> List[Tuple[str, str]]:
    rng = random.Random(seed)
    return [(rng.choice(SYSTEM_NAMES), rng.choice(SYSTEM_NAMES))
            for _ in range(n)]


def gen_bidding_system_matrix(seed: int,
                              n_base_hands: int = 4,
                              hcp_threshold: int = 28,
                              max_candidates: int = 10_000,
                              ) -> Tuple[List[BoardState],
                                         List[Tuple[str, str]]]:
    """Generate a 4×25 bidding-system-matrix corpus from a single
    seed. No "select first 4 / next 4" knobs — the generator walks
    the random-deal stream, filters for hands that should exhibit
    system-dependent bidding behaviour, then expands each into 25
    cells of the 5×5 (NS_system, EW_system) grid.

    Pipeline:
      1. Scan random deals (seeded by `seed`) for hands that:
         (a) Are slam-eligible — one partnership has at least
             `hcp_threshold` combined HCP (default 28, lower than
             the slam tab's 30 because the additional density
             constraint already discriminates aggressively), or
             (threshold − 2) HCP with an 8+ card fit. Slam-zone
             hands are where the 5 systems most visibly diverge
             on contract reached (Blackwood / cue bids / splinter
             paths differ widely across SAYC, 2/1, Acol, French,
             Precision).
         (b) Generate 25 unique spot-card permutations holding
             HCP + shape constant. Required because Q-Plus dedups
             by cards within a match — without 25 unique
             bitpatterns the cell entries would collapse and only
             the first played-through cell would actually run.
      2. Stop when `n_base_hands` (default 4) qualifying hands
         are found.
      3. Expand each base hand into 25 entries — one per
         (NS_system, EW_system) cell — with EW spot cards
         perturbed so Q-Plus sees each cell as a distinct deal.
         NS hands are UNCHANGED across all 25 cells of a given
         base hand → biq's NS auction depends only on the NS
         system, the cell variance comes from the (NS, EW)
         system pair, not the cards.

    Returns (deals, system_pairs) of length n_base_hands × 25.
    Cells are interleaved deal-by-deal so each contiguous block
    of 25 deals = one complete pass through the matrix; a
    partial run still yields a balanced sample.

    Raises RuntimeError if it can't find `n_base_hands`
    qualifying base hands in `max_candidates` candidates — bump
    one or the other.
    """
    cells = [(ns, ew) for ns in SYSTEM_NAMES for ew in SYSTEM_NAMES]
    base_hands = _find_matrix_base_hands(
        seed, n_base_hands, hcp_threshold, max_candidates)
    from dataclasses import replace
    deals: List[BoardState] = []
    system_pairs: List[Tuple[str, str]] = []
    for hand_i, base in enumerate(base_hands):
        for cell_i, (ns, ew) in enumerate(cells):
            # `seed + hand_i * 1000` keeps the perturbation
            # streams disjoint across the 4 base hands so two
            # base hands can't accidentally generate identical
            # spot-perturbed cells.
            perturbed = _perturb_ew_spot_cards(
                base, cell_i, seed=seed + hand_i * 1000)
            renumbered = replace(
                perturbed,
                board_number=len(deals) + 1,
            )
            deals.append(renumbered)
            system_pairs.append((ns, ew))
    return deals, system_pairs


def _find_matrix_base_hands(seed: int, n_base: int,
                            hcp_threshold: int,
                            max_candidates: int
                            ) -> List[BoardState]:
    """Walk the random-deal stream looking for hands that are
    slam-eligible AND generate 25 unique spot-perm bitpatterns.
    Returns the first `n_base` qualifying hands. Helper for
    `gen_bidding_system_matrix`."""
    def _hcp(hand):
        # ACE=0, KING=1, QUEEN=2, JACK=3 per backend.models.Rank
        pts = {0: 4, 1: 3, 2: 2, 3: 1}
        return sum(pts.get(c.rank.value, 0) for c in hand.cards)
    rng = random.Random(seed)
    deck = [Card(s, r)
            for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
            for r in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                      Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                      Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE,
                      Rank.TWO)]
    out: List[BoardState] = []
    for _ in range(max_candidates):
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hands = {
            Seat.NORTH: Hand(cards=shuffled[0:13]),
            Seat.EAST:  Hand(cards=shuffled[13:26]),
            Seat.SOUTH: Hand(cards=shuffled[26:39]),
            Seat.WEST:  Hand(cards=shuffled[39:52]),
        }
        ns_hcp = _hcp(hands[Seat.NORTH]) + _hcp(hands[Seat.SOUTH])
        ew_hcp = _hcp(hands[Seat.EAST]) + _hcp(hands[Seat.WEST])
        qualifies = (ns_hcp >= hcp_threshold
                     or ew_hcp >= hcp_threshold)
        if not qualifies and max(ns_hcp, ew_hcp) >= hcp_threshold - 2:
            # Shape fallback: 8+ card fit in some suit for the
            # higher-HCP side (cheaper than DD analysis, catches
            # obvious shape-driven slams).
            if ns_hcp >= ew_hcp:
                p1, p2 = Seat.NORTH, Seat.SOUTH
            else:
                p1, p2 = Seat.EAST, Seat.WEST
            for suit in (Suit.SPADES, Suit.HEARTS,
                         Suit.DIAMONDS, Suit.CLUBS):
                fit = (sum(1 for c in hands[p1].cards if c.suit == suit)
                       + sum(1 for c in hands[p2].cards if c.suit == suit))
                if fit >= 8:
                    qualifies = True
                    break
        if not qualifies:
            continue
        # Build the base BoardState then check spot-perm density.
        n_board = len(out) + 1
        dealer, vuln = BoardState._board_dealer_vuln(n_board)
        board = BoardState(board_number=n_board, dealer=dealer,
                           vulnerability=vuln, hands=hands)
        if not _has_25_unique_spotperms(board):
            continue
        out.append(board)
        if len(out) >= n_base:
            return out
    raise RuntimeError(
        f"Only found {len(out)} matrix-eligible base hand(s) "
        f"(slam-strength HCP + 25 unique spot-perms) in "
        f"{max_candidates} candidates; need {n_base}. Try "
        f"lowering hcp_threshold or raising max_candidates.")


def _has_25_unique_spotperms(board: BoardState) -> bool:
    """Check that the spot-perm generator produces 25 unique
    bitpatterns for this base board. Required by the matrix
    corpus so Q-Plus's per-match dedup-by-cards doesn't collapse
    the 25 cell entries into one. Helper for
    `_find_matrix_base_hands`."""
    fps = set()
    for cell_i in range(25):
        p = _spot_perm_bitpattern(board, cell_i)
        fp = tuple(sorted(
            (s.value, c.suit.value, c.rank.value)
            for s in (Seat.NORTH, Seat.EAST,
                      Seat.SOUTH, Seat.WEST)
            for c in p.hands[s].cards))
        fps.add(fp)
    return len(fps) >= 25


def gen_slam_eligible_deals(n: int, seed: int,
                            hcp_threshold: int = 30,
                            max_candidates: int = 5000
                            ) -> List[BoardState]:
    """Generate `n` slam-eligible deals from a random stream.

    A deal qualifies if EITHER partnership (NS or EW) has:
      * Combined HCP ≥ `hcp_threshold` (default 30), OR
      * Combined HCP ≥ (threshold - 2) AND an 8+ card fit in some suit
        (shape compensates for fewer HCP)

    Scans up to `max_candidates` candidate deals from the same seed
    stream; returns the first `n` qualifying ones (re-numbered 1..n).
    Raises if not enough qualify (rare with the default threshold).

    Used by the corpus app to build slam-rich corpora for testing
    biq's slam-bidding architecture against Q-Plus's.
    """
    def _hcp(hand):
        pts = {0: 4, 1: 3, 2: 2, 3: 1}  # ACE=0, KING=1, QUEEN=2, JACK=3
        return sum(pts.get(c.rank.value, 0) for c in hand.cards)

    rng = random.Random(seed)
    deck = [Card(s, r)
            for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS)
            for r in (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
                      Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN,
                      Rank.SIX, Rank.FIVE, Rank.FOUR, Rank.THREE,
                      Rank.TWO)]
    out: List[BoardState] = []
    for candidate_i in range(max_candidates):
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hands = {
            Seat.NORTH: Hand(cards=shuffled[0:13]),
            Seat.EAST:  Hand(cards=shuffled[13:26]),
            Seat.SOUTH: Hand(cards=shuffled[26:39]),
            Seat.WEST:  Hand(cards=shuffled[39:52]),
        }
        ns_hcp = _hcp(hands[Seat.NORTH]) + _hcp(hands[Seat.SOUTH])
        ew_hcp = _hcp(hands[Seat.EAST]) + _hcp(hands[Seat.WEST])
        qualifies = (ns_hcp >= hcp_threshold
                     or ew_hcp >= hcp_threshold)
        if not qualifies and max(ns_hcp, ew_hcp) >= hcp_threshold - 2:
            # Shape check: 8+ card fit in some suit for the higher
            # side. Cheaper than DD analysis and catches obvious
            # shape-driven slams.
            if ns_hcp >= ew_hcp:
                p1, p2 = Seat.NORTH, Seat.SOUTH
            else:
                p1, p2 = Seat.EAST, Seat.WEST
            for suit in (Suit.SPADES, Suit.HEARTS,
                         Suit.DIAMONDS, Suit.CLUBS):
                fit = (sum(1 for c in hands[p1].cards if c.suit == suit)
                       + sum(1 for c in hands[p2].cards if c.suit == suit))
                if fit >= 8:
                    qualifies = True
                    break
        if qualifies:
            n_board = len(out) + 1
            dealer, vuln = BoardState._board_dealer_vuln(n_board)
            out.append(BoardState(board_number=n_board, dealer=dealer,
                                  vulnerability=vuln, hands=hands))
            if len(out) >= n:
                return out
    raise RuntimeError(
        f"Only found {len(out)} slam-eligible deals (HCP ≥ "
        f"{hcp_threshold}) in {max_candidates} candidates; "
        f"need {n}. Try lowering the threshold or raising "
        f"max_candidates.")


_RANK_HI_TO_LO = (Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK, Rank.TEN,
                  Rank.NINE, Rank.EIGHT, Rank.SEVEN, Rank.SIX,
                  Rank.FIVE, Rank.FOUR, Rank.THREE, Rank.TWO)
_RANK_TO_CHAR = {Rank.ACE: "A", Rank.KING: "K", Rank.QUEEN: "Q",
                 Rank.JACK: "J", Rank.TEN: "T", Rank.NINE: "9",
                 Rank.EIGHT: "8", Rank.SEVEN: "7", Rank.SIX: "6",
                 Rank.FIVE: "5", Rank.FOUR: "4", Rank.THREE: "3",
                 Rank.TWO: "2"}
_VUL_TO_PBN = {Vulnerability.NONE: "None",
               Vulnerability.NS:   "NS",
               Vulnerability.EW:   "EW",
               Vulnerability.BOTH: "All"}
# Clockwise from each starting seat — used to lay out the four hands
# in the PBN Deal tag starting from the dealer.
_NEXT_SEAT = {Seat.NORTH: Seat.EAST, Seat.EAST: Seat.SOUTH,
              Seat.SOUTH: Seat.WEST, Seat.WEST: Seat.NORTH}
_SEAT_CHAR = {Seat.NORTH: "N", Seat.EAST: "E",
              Seat.SOUTH: "S", Seat.WEST: "W"}


def _pbn_hand(hand: Hand) -> str:
    """One hand in PBN form: 'SSS.HHH.DDD.CCC' (suits in S-H-D-C order,
    ranks high→low, void = empty)."""
    by_suit: Dict[Suit, List[Rank]] = {
        Suit.SPADES: [], Suit.HEARTS: [],
        Suit.DIAMONDS: [], Suit.CLUBS: [],
    }
    for c in hand.cards:
        by_suit[c.suit].append(c.rank)
    parts = []
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        ranks = by_suit[s]
        ranks_sorted = sorted(ranks, key=lambda r: _RANK_HI_TO_LO.index(r))
        parts.append("".join(_RANK_TO_CHAR[r] for r in ranks_sorted))
    return ".".join(parts)


# ---------------------------------------------------------------------------
# BDL ↔ manifest verifier
# ---------------------------------------------------------------------------

_SYSTEM_BY_TAG = {tag: name for name, _fam, tag in SYSTEMS}


def parse_bdl_with_systems(bdl_path: Path) -> List[Dict]:
    """Parse a Q-Plus BDL file extracting per-deal state.

    State machine — `.Bidding cnv` block placement rules:
      * BEFORE the first Deal: file header, IGNORE (it shows the
        state Q-Plus had when the BDL started recording, not what
        applies to deal 1).
      * INSIDE a Deal block (between Deal label and Result line):
        applies to THIS deal — that's where Q-Plus writes the
        actual systems used for the bidding.
      * BETWEEN two deals (after a Result, before next Deal):
        buffer it for the NEXT deal.

    Returns a list of dicts: {label, dealer, vul, ns_tag, ew_tag, hands}
    where hands = {'N': {'S': 'AKQ', 'H': '...', ...}, ...}.
    """
    import re
    state = "BEFORE_FIRST"   # → INSIDE_DEAL → BETWEEN_DEALS → INSIDE_DEAL …
    pending_ns: Optional[str] = None
    pending_ew: Optional[str] = None
    out: List[Dict] = []
    cur: Optional[Dict] = None
    in_cards = False
    card_lines: List[str] = []

    # Q-Plus 17.1 saves the savescore.qss with each deal's full BDL
    # embedded under a "D1 " prefix (one D1 line per BDL line).
    # The standalone .BDE is STRIPPED of per-deal `.Bidding cnv`
    # markers on save+exit, so the .qss is the only place per-deal
    # systems survive after save. Detect .qss and strip the D1
    # prefix as we read so the rest of the parser sees a normal BDL.
    # Also: Q-Plus only writes `.Bidding cnv` lines when the systems
    # CHANGE — so we propagate the most recent known systems forward
    # to deals that inherit the previous setting.
    is_qss = str(bdl_path).lower().endswith(".qss")
    last_ns: Optional[str] = None
    last_ew: Optional[str] = None
    with open(bdl_path, encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if is_qss:
                if not line.startswith("D1 "):
                    continue
                line = line[3:]  # strip "D1 " prefix
            stripped = line.lstrip()
            # ----- .Bidding cnv row -----
            if (stripped.startswith(".Bidding cnv")
                    or (stripped.startswith(".")
                        and ("N/S:" in stripped or "E/W:" in stripped))):
                m_ns = re.search(r"N/S:\s*(\S+)", stripped)
                m_ew = re.search(r"E/W:\s*(\S+)", stripped)
                ns = m_ns.group(1) if m_ns else None
                ew = m_ew.group(1) if m_ew else None
                if ns:
                    last_ns = ns
                if ew:
                    last_ew = ew
                if state == "INSIDE_DEAL" and cur is not None:
                    if ns:
                        cur["ns_tag"] = ns
                    if ew:
                        cur["ew_tag"] = ew
                elif state == "BETWEEN_DEALS":
                    if ns:
                        pending_ns = ns
                    if ew:
                        pending_ew = ew
                # BEFORE_FIRST: pre-loads last_ns/last_ew so the
                # first deal inherits the session-default systems
                # if Q-Plus doesn't re-state them per-deal.
                continue
            # ----- Deal label -----
            if line.startswith("Deal "):
                if cur is not None:
                    out.append(cur)
                value = line.split(":", 1)[1].strip()
                # Inherit last-known systems: Q-Plus only writes a
                # .Bidding cnv row when systems CHANGE, so deals
                # without one keep the previous deal's setting.
                inh_ns = pending_ns or last_ns
                inh_ew = pending_ew or last_ew
                cur = {
                    "label": value,
                    "dealer": None, "vul": None,
                    "ns_tag": inh_ns, "ew_tag": inh_ew,
                    "hands": None,
                }
                pending_ns = None
                pending_ew = None
                state = "INSIDE_DEAL"
                in_cards = False
                card_lines = []
                continue
            # ----- Result line ends the current deal -----
            if line.startswith("Result "):
                state = "BETWEEN_DEALS"
                continue
            if cur is None:
                continue
            if line.startswith("Dealer "):
                cur["dealer"] = line.split(":", 1)[1].strip()
                continue
            if line.startswith("Vuln "):
                cur["vul"] = line.split(":", 1)[1].strip()
                continue
            if line.startswith("Cards "):
                in_cards = True
                content = line.split(":", 1)[1] if ":" in line else ""
                card_lines = [content]
                continue
            if in_cards:
                if line.startswith("             :") and len(card_lines) < 12:
                    card_lines.append(line.split(":", 1)[1])
                    if len(card_lines) >= 12:
                        cur["hands"] = _parse_card_lines(card_lines)
                        in_cards = False
                else:
                    in_cards = False
    if cur is not None:
        out.append(cur)
    return out


def _parse_card_lines(lines: List[str]) -> Dict[str, Dict[str, str]]:
    """12 raw card-block content lines → {seat: {suit: 'AKQ'}}.

    Layout (Q-Plus):
      [0-3]  N's S, H, D, C
      [4-7]  W on left, E on right per suit (split by ≥2 spaces)
      [8-11] S's S, H, D, C
    Tokens are space-separated cards; '-' means void (filtered out).
    """
    import re
    suits = ["S", "H", "D", "C"]
    hands: Dict[str, Dict[str, str]] = {
        s: {} for s in ("N", "E", "S", "W")
    }
    def _cards(tokens: List[str]) -> str:
        return "".join(t for t in tokens if t != "-")
    for i in range(4):
        hands["N"][suits[i]] = _cards(lines[i].split())
    for i in range(4):
        parts = re.split(r"  +", lines[4 + i].strip())
        w_part = parts[0] if parts else ""
        e_part = parts[1] if len(parts) > 1 else ""
        hands["W"][suits[i]] = _cards(w_part.split())
        hands["E"][suits[i]] = _cards(e_part.split())
    for i in range(4):
        hands["S"][suits[i]] = _cards(lines[8 + i].split())
    return hands


def _hand_to_suit_dict(hand: Hand) -> Dict[str, str]:
    """Convert a Hand to {'S':'AKQ', 'H':'...', ...} for comparison.
    Ranks high→low; voids = empty string."""
    by_suit_chr = {Suit.SPADES: "S", Suit.HEARTS: "H",
                   Suit.DIAMONDS: "D", Suit.CLUBS: "C"}
    bucket: Dict[str, List[Rank]] = {"S": [], "H": [], "D": [], "C": []}
    for card in hand.cards:
        bucket[by_suit_chr[card.suit]].append(card.rank)
    out: Dict[str, str] = {}
    for s in "SHDC":
        ranks = sorted(bucket[s], key=lambda r: _RANK_HI_TO_LO.index(r))
        out[s] = "".join(_RANK_TO_CHAR[r] for r in ranks)
    return out


_VUL_FROM_BDL = {"---": "NONE", "None": "NONE",
                 "N/S": "NS", "NS": "NS",
                 "E/W": "EW", "EW": "EW",
                 "All": "BOTH", "Both": "BOTH", "all": "BOTH"}
_DEALER_FROM_BDL = {"North": "N", "East": "E", "South": "S", "West": "W"}


def verify_bdl_against_manifest(bdl_path: Path, manifest_path: Path
                                ) -> Tuple[List[str], Dict[str, int]]:
    """Compare a BDL to its manifest. Returns (issues, stats).

    Issues are human-readable strings (one per mismatch). stats =
    {'deals_in_bdl', 'deals_in_manifest', 'matched',
     'mismatch_dealer', 'mismatch_vul', 'mismatch_ns',
     'mismatch_ew', 'mismatch_cards', 'missing_in_bdl'}.
    """
    import json
    import re
    issues: List[str] = []
    stats = {
        "deals_in_bdl": 0, "deals_in_manifest": 0, "matched": 0,
        "mismatch_dealer": 0, "mismatch_vul": 0,
        "mismatch_ns": 0, "mismatch_ew": 0,
        "mismatch_cards": 0, "missing_in_bdl": 0,
    }
    manifest = json.loads(Path(manifest_path).read_text())
    deal_seed = manifest["deal_seed"]
    expected_boards = gen_random_deals(
        len(manifest["deals"]), deal_seed)
    bdl_deals = parse_bdl_with_systems(bdl_path)
    stats["deals_in_bdl"] = len(bdl_deals)
    stats["deals_in_manifest"] = len(manifest["deals"])

    # First-occurrence wins: Q-Plus sometimes appends a trailing
    # "Deal X / Result : No Contract" stub when the user saves
    # mid-play. That stub would overwrite the real played record.
    bdl_by_num: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_num:
                bdl_by_num[n] = bd

    for mi, entry in enumerate(manifest["deals"]):
        n = entry["deal"]
        bdl = bdl_by_num.get(n)
        if bdl is None:
            issues.append(f"Deal {n}: not present in BDL (Q-Plus "
                          "either didn't play it or labeled it "
                          "differently)")
            stats["missing_in_bdl"] += 1
            continue
        ok = True
        # Dealer
        bdl_dealer = _DEALER_FROM_BDL.get((bdl["dealer"] or "").strip())
        if bdl_dealer != entry["dealer"]:
            issues.append(
                f"Deal {n}: dealer  BDL={bdl['dealer']!r}  "
                f"manifest={entry['dealer']!r}")
            stats["mismatch_dealer"] += 1
            ok = False
        # Vulnerability
        bdl_vul = _VUL_FROM_BDL.get((bdl["vul"] or "").strip(), "?")
        if bdl_vul != entry["vul"]:
            issues.append(
                f"Deal {n}: vul     BDL={bdl['vul']!r}  "
                f"manifest={entry['vul']!r}")
            stats["mismatch_vul"] += 1
            ok = False
        # N/S system
        expected_ns_tag = SYSTEM_TAG[entry["ns_system"]]
        if bdl["ns_tag"] != expected_ns_tag:
            actual = bdl["ns_tag"] or "(none)"
            actual_name = _SYSTEM_BY_TAG.get(actual, "?")
            issues.append(
                f"Deal {n}: N/S    BDL={actual} ({actual_name})  "
                f"manifest={expected_ns_tag} ({entry['ns_system']})")
            stats["mismatch_ns"] += 1
            ok = False
        # E/W system
        expected_ew_tag = SYSTEM_TAG[entry["ew_system"]]
        if bdl["ew_tag"] != expected_ew_tag:
            actual = bdl["ew_tag"] or "(none)"
            actual_name = _SYSTEM_BY_TAG.get(actual, "?")
            issues.append(
                f"Deal {n}: E/W    BDL={actual} ({actual_name})  "
                f"manifest={expected_ew_tag} ({entry['ew_system']})")
            stats["mismatch_ew"] += 1
            ok = False
        # Cards
        if bdl["hands"]:
            expected_seat_map = {
                "N": Seat.NORTH, "E": Seat.EAST,
                "S": Seat.SOUTH, "W": Seat.WEST,
            }
            for seat_char, seat in expected_seat_map.items():
                expected = _hand_to_suit_dict(
                    expected_boards[mi].hands[seat])
                got = bdl["hands"][seat_char]
                for suit_char in "SHDC":
                    if got.get(suit_char, "") != expected[suit_char]:
                        issues.append(
                            f"Deal {n}: cards  {seat_char}{suit_char} "
                            f"BDL={got.get(suit_char, '')!r}  "
                            f"manifest={expected[suit_char]!r}")
                        stats["mismatch_cards"] += 1
                        ok = False
                        break
                if not ok:
                    break
        if ok:
            stats["matched"] += 1
    return issues, stats


def reconcile_manifest_to_bdl(bdl_path: Path, manifest_path: Path
                              ) -> Tuple[int, List[str]]:
    """Rewrite the manifest so its ns_system/ew_system fields match
    what the BDL actually recorded. Useful when the deal cards
    themselves are correct (random inputs are interchangeable, so a
    mis-set system doesn't waste the deal — we just relabel which
    system played it).

    Card / dealer / vul mismatches are NOT auto-fixed (those would
    mean Q-Plus played a totally different deal). They're returned
    as warnings.

    A timestamped backup of the original manifest is written next
    to it (foo.manifest.json → foo.manifest.bak_<ts>.json).

    Returns (fixed_count, warnings).
    """
    import json
    import re
    import datetime
    manifest_path = Path(manifest_path)
    bdl_path = Path(bdl_path)
    manifest = json.loads(manifest_path.read_text())
    bdl_deals = parse_bdl_with_systems(bdl_path)
    bdl_by_num: Dict[int, Dict] = {}
    for bd in bdl_deals:
        m = re.search(r"(\d+)\s*$", bd["label"] or "")
        if m:
            n = int(m.group(1))
            if n not in bdl_by_num:
                bdl_by_num[n] = bd  # ignore trailing No-Contract stubs

    expected_boards = gen_random_deals(
        len(manifest["deals"]), manifest["deal_seed"])

    fixed = 0
    warnings: List[str] = []
    for mi, entry in enumerate(manifest["deals"]):
        n = entry["deal"]
        bdl = bdl_by_num.get(n)
        if bdl is None:
            warnings.append(f"Deal {n}: not present in BDL — left as-is")
            continue
        # Card check — if cards differ, do NOT reconcile systems
        # (a card mismatch means Q-Plus played a different deal,
        # so relabeling the system would be wrong).
        cards_match = True
        if bdl["hands"]:
            for seat_char, seat in (("N", Seat.NORTH), ("E", Seat.EAST),
                                    ("S", Seat.SOUTH), ("W", Seat.WEST)):
                exp = _hand_to_suit_dict(expected_boards[mi].hands[seat])
                got = bdl["hands"][seat_char]
                for s in "SHDC":
                    if got.get(s, "") != exp[s]:
                        cards_match = False
                        break
                if not cards_match:
                    break
        if not cards_match:
            warnings.append(
                f"Deal {n}: cards differ from manifest's generated "
                "deal — Q-Plus played a different layout. NOT "
                "auto-fixing (would lie about which deal was played).")
            continue
        # Reconcile NS
        if bdl["ns_tag"] and bdl["ns_tag"] in _SYSTEM_BY_TAG:
            actual_ns_name = _SYSTEM_BY_TAG[bdl["ns_tag"]]
            if actual_ns_name != entry["ns_system"]:
                entry["ns_system"] = actual_ns_name
                fixed += 1
        elif bdl["ns_tag"]:
            warnings.append(
                f"Deal {n}: BDL N/S tag {bdl['ns_tag']!r} isn't one "
                "of the 5 systems we model — left as-is")
        # Reconcile EW
        if bdl["ew_tag"] and bdl["ew_tag"] in _SYSTEM_BY_TAG:
            actual_ew_name = _SYSTEM_BY_TAG[bdl["ew_tag"]]
            if actual_ew_name != entry["ew_system"]:
                entry["ew_system"] = actual_ew_name
                fixed += 1
        elif bdl["ew_tag"]:
            warnings.append(
                f"Deal {n}: BDL E/W tag {bdl['ew_tag']!r} isn't one "
                "of the 5 systems we model — left as-is")

    if fixed:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = manifest_path.with_name(
            manifest_path.stem + f".bak_{ts}.json")
        bak.write_text(json.dumps(json.loads(manifest_path.read_text()),
                                  indent=2))
        manifest_path.write_text(json.dumps(manifest, indent=2))
    return fixed, warnings


QPLUS_LUTRIS_RUNNER = "lutris-6.21-6-x86_64"


def qplus_launch_cmd() -> Optional[str]:
    """Build the shell command that (re)launches Q-Plus under the
    same Lutris-managed Wine runner the launcher uses for qplus.sh
    (`lutris-6.21-6-x86_64` per config/wine_runners.csv). Used by
    the auto-rollover to spawn a fresh Q-Plus after Save match +
    exit, and by the rollover smoke-test button on the Calibration
    tab.

    Falls back to whatever `wine` is on PATH if the lutris runner
    isn't installed. Returns None if the Q-Plus install dir can't
    be located.
    """
    from backend.qplus_driver import qplus_install_dir
    install = qplus_install_dir()
    if install is None:
        return None
    # install = .../WP/drive_c/games/qbridge17 → wineprefix = .../WP
    wineprefix = install.parent.parent.parent
    lutris_wine = (Path.home() / ".local" / "share" / "lutris"
                   / "runners" / "wine" / QPLUS_LUTRIS_RUNNER
                   / "bin" / "wine")
    wine_bin = str(lutris_wine) if lutris_wine.is_file() else "wine"
    return (f"cd {install} && "
            f"WINEPREFIX={wineprefix} WINEARCH=win32 "
            f"{wine_bin} QBRIDGE.EXE >/dev/null 2>&1")


def archive_savescore_qss(deal_seed: int, sys_seed: int,
                          batch_num: int) -> Optional[Path]:
    """Copy Q-Plus's savescore.qss to the archive dir with a
    batch-tagged filename. Called by the UI when the operator
    confirms they've done save+exit between batches.

    Returns the archive path on success, None on failure.
    """
    import shutil
    import datetime
    qss = qplus_local_matches_dir()
    if qss is None:
        return None
    qss = qss / "savescore.qss"
    if not qss.is_file():
        return None
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = (ARCHIVE_DIR
            / f"{ts}_{deal_seed}_{sys_seed}_batch{batch_num}.qss")
    shutil.copy(qss, dest)
    return dest


def merge_qss_corpora(qss_paths: List[Path], out_path: Path,
                      deals_per_match: int = 64) -> int:
    """Concatenate the D1-prefixed deal blocks from multiple
    .qss files into a single combined file that the existing
    parse_bdl_with_systems / verify / diff tools can read as one
    corpus.

    Keeps only the D1 records (the embedded BDL); skips the .qss
    match-metadata headers (SM/DS/CG/etc) which would conflict
    between files. Q-Plus 17.1 caps a single match at 64 deals;
    runs that need more split into multiple BDE files (one per
    batch, deals labeled with continuous numbering 1-64, 65-128,
    …). When each batch loads its own BDE, the resulting .qss
    deal labels are already unique across batches — no relabel
    needed here. We just concatenate.

    `deals_per_match` is kept for backwards compatibility but is
    no longer used for relabel (each BDE pre-labels correctly).

    Returns the number of D1 deal records emitted.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    deals_seen = 0
    with open(out_path, "w", encoding="latin-1") as fout:
        fout.write("# Merged Q-Plus savescore - combined batches\n")
        for qss in qss_paths:
            if not qss.is_file():
                continue
            with open(qss, encoding="latin-1", errors="replace") as fin:
                for raw in fin:
                    if not raw.startswith("D1 "):
                        continue
                    body = raw[3:].lstrip()
                    if body.startswith("Deal "):
                        deals_seen += 1
                    fout.write(raw)
    return deals_seen


def _spot_perm_bitpattern(board, cell_i):
    """Bit-pattern spot perturbation between E and W.

    Builds INDEPENDENT swap pairs from the ORIGINAL E/W spots
    (rank.value ≥ 5 = card rank 2..9). Each bit of `cell_i`
    toggles one swap-pair on/off. With N pairs we get exactly
    2**N unique end states (each card appears in ≤ 1 pair).

    Pair-selection priority:
      1. SAME-SUIT pairs first (no shape change, no HCP change).
      2. SAME-RANK cross-suit pairs (HCP stable; shape shifts
         by ±1 in two suits).
      3. CROSS-SUIT any-rank pairs (last resort — needed for
         deals with skewed E/W distributions to reach 5+ pairs
         so 25 unique end states are possible).

    Falls back to the legacy enumerate-and-apply function only if
    fewer than 5 pairs can be built (rare).

    NS hands are NEVER touched — biq's NS auction is identical
    across all 25 cells of the same base deal.
    """
    from dataclasses import replace
    from backend.models import Hand, Suit, Seat

    e_cards_orig = list(board.hands[Seat.EAST].cards)
    w_cards_orig = list(board.hands[Seat.WEST].cards)
    # All low cards (2..9, rank.value ≥ 5) on each side.
    e_spots = [c for c in e_cards_orig if c.rank.value >= 5]
    w_spots = [c for c in w_cards_orig if c.rank.value >= 5]

    pairs = []
    used_e = set()
    used_w = set()

    def _card_id(c):
        return (c.suit.value, c.rank.value)

    # Tier 1: same-suit pairs (lowest-with-lowest within each suit).
    for suit in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        es = sorted([c for c in e_spots if c.suit == suit],
                    key=lambda c: -c.rank.value)
        ws = sorted([c for c in w_spots if c.suit == suit],
                    key=lambda c: -c.rank.value)
        for i in range(min(len(es), len(ws))):
            if es[i].rank == ws[i].rank:
                continue  # identical cards can't swap meaningfully
            pairs.append((es[i], ws[i]))
            used_e.add(_card_id(es[i]))
            used_w.add(_card_id(ws[i]))

    # Tier 2: same-rank cross-suit pairs using leftover cards.
    if len(pairs) < 5:
        for rank_value in range(5, 13):  # ranks 9 down to 2
            e_rest = [c for c in e_spots
                      if c.rank.value == rank_value
                      and _card_id(c) not in used_e]
            w_rest = [c for c in w_spots
                      if c.rank.value == rank_value
                      and _card_id(c) not in used_w]
            for i in range(min(len(e_rest), len(w_rest))):
                if e_rest[i].suit == w_rest[i].suit:
                    continue  # would be same-suit, already tried
                pairs.append((e_rest[i], w_rest[i]))
                used_e.add(_card_id(e_rest[i]))
                used_w.add(_card_id(w_rest[i]))
                if len(pairs) >= 5:
                    break
            if len(pairs) >= 5:
                break

    # Tier 3: any-rank cross-suit pairs from remaining spots.
    if len(pairs) < 5:
        e_rest = [c for c in e_spots if _card_id(c) not in used_e]
        w_rest = [c for c in w_spots if _card_id(c) not in used_w]
        # Sort by rank.value descending so we use the LOWEST cards
        # first (least impact on bidding/play).
        e_rest.sort(key=lambda c: -c.rank.value)
        w_rest.sort(key=lambda c: -c.rank.value)
        for i in range(min(len(e_rest), len(w_rest))):
            pairs.append((e_rest[i], w_rest[i]))
            used_e.add(_card_id(e_rest[i]))
            used_w.add(_card_id(w_rest[i]))
            if len(pairs) >= 5:
                break

    if len(pairs) < 5:
        return _perturb_ew_spot_cards_legacy(board, cell_i)

    # Apply only the pairs flagged in cell_i (one bit per pair).
    e_cards = list(e_cards_orig)
    w_cards = list(w_cards_orig)
    for j, (ec, wc) in enumerate(pairs):
        if cell_i & (1 << j):
            e_cards.remove(ec)
            e_cards.append(wc)
            w_cards.remove(wc)
            w_cards.append(ec)
    new_hands = dict(board.hands)
    new_hands[Seat.EAST] = Hand(cards=e_cards)
    new_hands[Seat.WEST] = Hand(cards=w_cards)
    return replace(board, hands=new_hands)


def _perturb_ew_spot_cards(board, cell_i, seed=0):
    """Wrapper kept for backward compatibility with the existing
    `_on_load_curated` call site. Delegates to the bit-pattern
    perturbation when possible; falls back to the legacy
    enumerate-and-apply otherwise.
    """
    return _spot_perm_bitpattern(board, cell_i)


def _perturb_ew_spot_cards_legacy(board, cell_i, seed=0):
    """Return a copy of `board` with deterministic spot-card swaps
    between E and W chosen by `cell_i`. Same-suit swaps only →
    preserves both hands' shape AND honor structure. NS hands are
    untouched.

    Purpose: defeat Q-Plus's per-match dedup-by-cards so we can
    play 25 essentially-identical copies of the same deal under
    different system pairs and have Q-Plus treat each as a fresh
    deal. Because the perturbation is E↔W only and only on rank
    ≤9 cards (no honors), N's and S's hands and biq's NS auction
    are completely unchanged from the source deal.

    Strategy:
      cell_i=0  → identity (baseline cards = original deal)
      cell_i=k  → apply the k'th lexicographic single-swap
                  enumerated from (suit, e_rank, w_rank).
      cell_i>=N → cycle through pair-of-swaps once singles run out.
    """
    from dataclasses import replace
    from backend.models import Hand, Suit, Seat
    e_cards = list(board.hands[Seat.EAST].cards)
    w_cards = list(board.hands[Seat.WEST].cards)
    # Enumerate all valid (suit, e_rank, w_rank) single swaps,
    # deterministically.
    valid_swaps = []
    for suit in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
        e_spots = sorted([c for c in e_cards
                          if c.suit == suit and c.rank.value <= 7],
                         key=lambda c: c.rank.value)
        w_spots = sorted([c for c in w_cards
                          if c.suit == suit and c.rank.value <= 7],
                         key=lambda c: c.rank.value)
        for ec in e_spots:
            for wc in w_spots:
                if ec.rank != wc.rank:
                    valid_swaps.append((suit, ec, wc))
    if cell_i == 0 or not valid_swaps:
        return board
    # Apply cell_i swaps from the valid-swap list, cycling through
    # the list. Re-enumerate valid swaps after each (because the
    # available spots in each hand change). For 25 cells with a
    # typical 12-20 single-swap pool, this gives an upper bound of
    # 25 single swaps applied sequentially → ~25 unique end states
    # in practice (some may collide, but the bound is high).
    def enumerate_swaps(e_now, w_now):
        out = []
        for s in (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES):
            es = sorted([c for c in e_now
                         if c.suit == s and c.rank.value <= 7],
                        key=lambda c: c.rank.value)
            ws = sorted([c for c in w_now
                         if c.suit == s and c.rank.value <= 7],
                        key=lambda c: c.rank.value)
            for ec in es:
                for wc in ws:
                    if ec.rank != wc.rank:
                        out.append((s, ec, wc))
        return out
    # Pick cell_i swaps; each swap picks the i'th available swap
    # at that point (deterministic).
    for step in range(cell_i):
        swaps = enumerate_swaps(e_cards, w_cards)
        if not swaps:
            break
        s, ec, wc = swaps[step % len(swaps)]
        e_cards.remove(ec)
        e_cards.append(wc)
        w_cards.remove(wc)
        w_cards.append(ec)
    new_hands = dict(board.hands)
    new_hands[Seat.EAST] = Hand(e_cards)
    new_hands[Seat.WEST] = Hand(w_cards)
    return replace(board, hands=new_hands)


def pbn_format_board(board: BoardState) -> str:
    """PBN-style blob: dealer + vul + Deal tag listing all four hands
    clockwise starting from the dealer."""
    dealer_c = _SEAT_CHAR[board.dealer]
    vul = _VUL_TO_PBN.get(board.vulnerability, "None")
    seat = board.dealer
    hand_strs = []
    for _ in range(4):
        hand_strs.append(_pbn_hand(board.hands[seat]))
        seat = _NEXT_SEAT[seat]
    deal_tag = f"{dealer_c}:" + " ".join(hand_strs)
    return (f'[Dealer "{dealer_c}"] '
            f'[Vulnerable "{vul}"] '
            f'[Deal "{deal_tag}"]')


# ---------------------------------------------------------------------------
# Run worker — driven on a QThread.
# ---------------------------------------------------------------------------

@dataclass
class RunConfig:
    positions: Dict[str, Tuple[int, int]]
    system_pairs: List[Tuple[str, str]]
    window_id: Optional[int]
    # Bumped from 50→200 ms after a 95-deal run produced only 2
    # fully-correct deals. Most failures were missed radio clicks
    # whose listbox-repaint didn't complete before the list-item
    # click landed — 50 ms wasn't enough under Wine.
    after_dialog_step_ms: int = 200
    after_dialog_close_ms: int = 300
    after_next_deal_s: float = 2.0
    after_start_bidding_s: float = 25.0
    # Bumped 60 → 90s for end-of-batch safety: in the 64570 corpus the
    # last 1-2 deals of each batch were truncated because the harness's
    # 60s budget elapsed while Q-Plus was still in cardplay, so when
    # the user did File→Save match and exit those deals weren't yet
    # committed to savescore.qss. The real fix for systemic drift is
    # the wait_for_clean_state + open-dialog verifier in
    # _set_systems_for_deal; this just gives the tail more headroom.
    per_deal_s: float = 90.0
    starting_deal_index: int = 0
    # When True, the very first deal of the run skips the "Next
    # deal" click — Q-Plus has just been loaded and Own deals →
    # Play has put it on the starting deal already (the bottom-
    # left button reads "Start bidding", not "Next deal"). All
    # subsequent deals click Next deal normally.
    qplus_on_starting_deal: bool = True
    screenshot_per_deal: bool = False
    # Per-deal audit screenshot of the bidding-system dialog state
    # captured AFTER all clicks have landed but BEFORE Close — the
    # ground truth for which systems Q-Plus is about to commit.
    # On by default (cheap, useful for post-run audit).
    verify_screenshots: bool = True
    # Q-Plus's per-match save cap. Once `deals_per_match` deals have
    # been played in a single match, the run pauses for the operator
    # to do File → Save match and exit in Q-Plus, then reopen Q-Plus
    # to a fresh empty match. After that, the run resumes with the
    # next batch. Each batch's savescore.qss is archived separately;
    # the merge tool combines them post-run for verify/diff. Q-Plus
    # 17.1 has a hard cap of 64 — runs that try to play more silently
    # drop the tail deals. 0 = disabled (run all in one match).
    deals_per_match: int = 64
    # Per-deal PBN-formatted blob, indexed same as system_pairs.
    # Logged before each iteration so the operator can cross-check
    # the manifest hand against what Q-Plus actually displays.
    pbn_blobs: Optional[List[str]] = None
    # Curated-run flag: when True, iterations that aren't the first
    # cell of a new physical deal use Q-Plus's Deal → Repeat-deal
    # menu instead of Next-deal. Lets the SAME physical deal be
    # played multiple times with different system pairs, bypassing
    # Q-Plus's per-match dedup-by-cards. Requires the operator to
    # have calibrated deal_menu, repeat_deal_item, repeat_complete_radio,
    # repeat_computer_radio, and repeat_ok_btn positions.
    is_curated: bool = False
    # When is_curated, the number of cells (system pairs) per unique
    # physical deal. The Nth cell uses Next-deal; the next (cells_per_deal
    # - 1) cells use Repeat-deal; then the cycle starts over.
    cells_per_deal: int = 25
    # Match End auto-extend: when Q-Plus pops its Match End dialog
    # (default match length hit), type this number into the boards
    # field and click Extend. 0 = leave the dialog alone (hang).
    extend_match_boards: int = 64


class RunWorker(QObject):
    """Drives Q-Plus deal-by-deal in a background thread.

    Also reused for the Test button (single-shot dialog cycling, no
    Next deal click).
    """

    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool)
    status = pyqtSignal(str, str)  # (text, color)
    # batch_break(batch_num, last_deal_played, next_deal) — fires
    # when a deals_per_match batch completes and the run must pause
    # for the operator to save+exit Q-Plus and reopen to a fresh
    # match. UI handler shows a modal, archives the .qss, then calls
    # `resume_after_batch()` to let the worker continue.
    batch_break = pyqtSignal(int, int, int)

    def __init__(self, cfg: RunConfig):
        super().__init__()
        self.cfg = cfg
        self._stop = False
        self._batch_resume = False
        # Set by MainWindow._auto_rollover after a successful
        # save+exit/relaunch/load: the very next iteration must
        # skip its Next-deal click because Q-Plus's fresh window
        # is already showing the next batch's first deal (after
        # the post-rollover Play click). Consumed and reset by
        # `run()` on the iteration right after the batch break.
        self._post_rollover_skip = False

    def stop(self):
        self._stop = True

    def resume_after_batch(self):
        """Called by the UI after the operator has saved+exited
        Q-Plus, archived the .qss, and reopened Q-Plus to a fresh
        empty match. Releases the batch-break wait in `run()`."""
        self._batch_resume = True

    def _focus(self):
        # NO `--sync`: on Wine/X11 the activate-and-wait flag can
        # hang for many seconds per click. Fire-and-forget keeps
        # focus where it needs to be (user has Q-Plus focused at
        # start of run) without per-click latency.
        if self.cfg.window_id:
            try:
                xdo("windowactivate", str(self.cfg.window_id),
                    check=False)
            except Exception:
                pass

    def _click(self, key: str):
        # IMPORTANT: don't refocus per click. `xdotool windowactivate
        # --sync` blocks for seconds on some X11/Wine setups, turning
        # a 0.2s dialog cycle into 10+ seconds. Caller refocuses ONCE
        # at the start of a dialog cycle.
        x, y = self.cfg.positions[key]
        click_at(x, y)

    def _pause_step(self):
        time.sleep(self.cfg.after_dialog_step_ms / 1000.0)

    def _pause_close(self):
        time.sleep(self.cfg.after_dialog_close_ms / 1000.0)

    def _set_systems_for_deal(self, ns: str, ew: str,
                              deal_num: int = 0):
        """Open the bidding-system dialog, set NS then EW, close.

        Click-verification additions (vs. the original):
        1. Defensive double-click on radio + list-item — the second
           click is harmless (idempotent) if the first landed, and
           recovers if it didn't. Radio-family clicks are the most
           likely failure point: a missed radio leaves the previous
           family active, and the subsequent list-item click lands on
           an arbitrary system within that wrong family. This was
           confirmed by a 95-deal run that produced only 2 fully-
           correct deals.
        2. After the radio click, an EXTRA pause (3× the dialog step
           pause) so Q-Plus has time to repaint the family's list.
           Clicking the list item before the repaint hits whatever
           item happened to be at that screen position previously.
        3. Optional per-deal audit screenshot of the Q-Plus window
           taken AFTER all clicks but BEFORE closing the dialog —
           the dialog state at that instant is the ground truth for
           which systems will apply. Saved to AUDIT_DIR with deal
           number, so post-run you can spot-check any deal whose
           systems verify wrong.
        """
        # One focus call before the burst of clicks. (Per-click
        # focus was the source of the multi-second-per-click delay.)
        self._focus()
        # Fix #1: WAIT until any blocking dialog (Simulation / Match
        # End) is fully cleared before opening our own dialog.
        # Single-shot drain wasn't enough — root cause of the deal-44
        # / deal-79 drift bands in the 64570 corpus (Simulation popped
        # mid-cardplay, was dismissed, but subsequent system-set
        # clicks still landed on stale UI).
        if not self._wait_for_clean_state(timeout_s=8.0):
            self.log.emit(
                "  WARNING: blocking dialog didn't clear within 8s — "
                "proceeding anyway, but this deal's systems may "
                "mis-set")
        self.log.emit(f"  open dialog…")
        # Fix #2: open the bidding-system dialog with verification.
        # If the dialog doesn't appear after clicking, retry. Without
        # this, the radio/list clicks below land on the main game
        # window and silently leave the previous deal's systems
        # active.
        if not self._open_bidding_system_dialog(max_attempts=3):
            self.log.emit(
                "  ERROR: bidding-system dialog never opened after 3 "
                "attempts — skipping system-set for this deal "
                "(previous deal's systems will persist)")
            return

        self.log.emit(f"  N/S ← {ns} ({SYSTEM_TAG[ns]})")
        self._click_radio_robust(RADIO_FOR_FAMILY[SYSTEM_FAMILY[ns]])
        self._click_list_robust(f"list_{ns}")
        self._click("set_ns_btn");                         self._pause_step()

        self.log.emit(f"  E/W ← {ew} ({SYSTEM_TAG[ew]})")
        self._click_radio_robust(RADIO_FOR_FAMILY[SYSTEM_FAMILY[ew]])
        self._click_list_robust(f"list_{ew}")
        self._click("set_ew_btn");                         self._pause_step()

        # Audit screenshot of the dialog BEFORE closing — captures
        # the radio/list state that Q-Plus is about to commit when
        # we click Close. Visual ground truth for post-run audit.
        if self.cfg.verify_screenshots and deal_num:
            try:
                fn = (AUDIT_DIR
                      / f"deal_{deal_num:03d}_dialog_state.png")
                grab_qplus_screenshot(fn, self.cfg.window_id)
            except Exception:
                pass  # screenshot is best-effort, don't block run

        self._click("close_btn"); self._pause_close()

    def _click_radio_robust(self, key: str):
        """Click a radio button defensively: click, wait the dialog
        step, click again, then wait 3× the step pause so Q-Plus's
        listbox can repaint with the new family's systems before
        the next list-item click."""
        self._click(key); self._pause_step()
        self._click(key); self._pause_step()
        # Extra settle after radio — listbox repaint takes longer
        # than a simple click acknowledgement.
        time.sleep(self.cfg.after_dialog_step_ms * 3 / 1000.0)

    def _click_list_robust(self, key: str):
        """Click a list-item defensively: two clicks with the dialog
        step pause between."""
        self._click(key); self._pause_step()
        self._click(key); self._pause_step()

    def _simulation_dialog_visible(self) -> bool:
        """Return True if Q-Plus's 'Simulation for …' dialog is up."""
        try:
            out = xdo("search", "--name", "Simulation", check=False)
            return bool(out.strip())
        except Exception:
            return False

    def _maybe_dismiss_simulation(self):
        """If the Simulation dialog is up AND a Close-button position
        is calibrated, click it. Quietly returns otherwise — the
        position is optional."""
        if "simulation_close_btn" not in self.cfg.positions:
            return
        if not self._simulation_dialog_visible():
            return
        self._click("simulation_close_btn")
        self.log.emit("  auto-dismissed Simulation dialog")
        # Brief settle so the next iteration sees a clean state.
        time.sleep(0.3)

    def _match_end_dialog_visible(self) -> bool:
        """Return True if Q-Plus's 'Match End' dialog is up."""
        try:
            out = xdo("search", "--name", "Match End", check=False)
            return bool(out.strip())
        except Exception:
            return False

    def _bidding_system_dialog_visible(self) -> bool:
        """Return True if Q-Plus's bidding-system configuration dialog
        is up. Used as a verifier after the open-dialog clicks — if the
        dialog isn't visible, the radio/list clicks below would land on
        the underlying main window. Q-Plus titles the dialog
        'Bidding system' (with a hyphen in some locales)."""
        for name in ("Bidding system", "Bidding-system",
                     "idding system"):
            try:
                out = xdo("search", "--name", name, check=False)
                if out.strip():
                    return True
            except Exception:
                pass
        return False

    def _wait_for_clean_state(self, timeout_s: float = 10.0) -> bool:
        """Loop until no blocking dialog (Simulation / Match End) is
        visible, draining as we go. Returns True if the screen cleared
        within timeout, False otherwise. Used at the top of
        _set_systems_for_deal so subsequent clicks land on the main
        game window, not on an overlay."""
        deadline = time.time() + timeout_s
        while time.time() < deadline and not self._stop:
            self._maybe_dismiss_simulation()
            self._maybe_extend_match()
            if (not self._simulation_dialog_visible()
                    and not self._match_end_dialog_visible()):
                return True
            time.sleep(0.3)
        return False

    def _screen_hash(self) -> Optional[str]:
        """MD5 hash of the Q-Plus window's current pixels. Returns None
        if we can't grab. Used to detect screen quiescence (no card
        animation) as a cardplay-finished signal."""
        import hashlib
        from io import BytesIO
        try:
            from PIL import ImageGrab
        except Exception:
            return None
        bbox = None
        wid = self.cfg.window_id
        if wid:
            try:
                out = xdo("getwindowgeometry", "--shell", str(wid),
                          check=False)
                env: Dict[str, str] = {}
                for line in out.splitlines():
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
                if all(k in env for k in ("X", "Y", "WIDTH", "HEIGHT")):
                    x = int(env["X"]); y = int(env["Y"])
                    w = int(env["WIDTH"]); h = int(env["HEIGHT"])
                    bbox = (x, y, x + w, y + h)
            except Exception:
                bbox = None
        try:
            img = ImageGrab.grab(bbox=bbox)
            # Downscale to make hash cheap and robust to tiny redraws
            # (cursor blink, pixel-level antialiasing flicker).
            img = img.resize((160, 120))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return hashlib.md5(buf.getvalue()).hexdigest()
        except Exception:
            return None

    def _wait_for_cardplay_finished(self, max_wait_s: float,
                                    min_wait_s: float = 8.0,
                                    quiescent_required: int = 3,
                                    poll_interval_s: float = 1.0
                                    ) -> bool:
        """Poll the Q-Plus window for cardplay-finished signal.

        Detection: after a minimum wait, the window is quiescent when
        N consecutive screen hashes are identical (no card animation
        happening). Returns True if detected within max_wait_s,
        False on timeout.

        Drains Simulation / Match End dialogs along the way — those
        block cardplay completion, so we don't count time spent in
        them against the quiescent run. A dialog being up forces the
        consecutive-identical counter to reset (you don't get to
        'declare quiescent' while a dialog is up).
        """
        deadline = time.time() + max_wait_s
        min_deadline = time.time() + min_wait_s
        last_hash: Optional[str] = None
        identical_streak = 0
        polls = 0
        while time.time() < deadline and not self._stop:
            # Drain blocking dialogs first — these stop card animation
            # and would otherwise be detected as a false quiescence.
            self._maybe_dismiss_simulation()
            self._maybe_extend_match()
            if (self._simulation_dialog_visible()
                    or self._match_end_dialog_visible()):
                # Reset streak; the dismiss may take effect on next
                # iteration and animation may resume.
                identical_streak = 0
                last_hash = None
                time.sleep(poll_interval_s)
                continue
            polls += 1
            h = self._screen_hash()
            if h is None:
                # Screenshot failed — fall through to next poll.
                time.sleep(poll_interval_s)
                continue
            if h == last_hash:
                identical_streak += 1
                if (identical_streak >= quiescent_required
                        and time.time() >= min_deadline):
                    return True
            else:
                identical_streak = 1
            last_hash = h
            time.sleep(poll_interval_s)
        return False

    def _open_bidding_system_dialog(self, max_attempts: int = 3) -> bool:
        """Click config_menu + bidding_system_item, then verify the
        bidding-system dialog actually opened. Retries up to
        max_attempts times. Returns True on success, False if the
        dialog never appeared (caller should skip this deal rather
        than blind-click into the wrong UI)."""
        for attempt in range(max_attempts):
            self._click("config_menu")
            self._pause_step()
            self._click("bidding_system_item")
            self._pause_close()
            # Brief settle, then probe.
            time.sleep(0.2)
            if self._bidding_system_dialog_visible():
                if attempt > 0:
                    self.log.emit(
                        f"  bidding-system dialog opened on attempt "
                        f"{attempt + 1}")
                return True
            self.log.emit(
                f"  bidding-system dialog NOT visible after "
                f"open click (attempt {attempt + 1}/{max_attempts}) "
                f"— retrying")
            # Drain in case a blocking dialog stole focus, then retry.
            self._wait_for_clean_state(timeout_s=3.0)
        return False

    def _maybe_extend_match(self):
        """If the Match End dialog is up AND both Extend positions
        are calibrated, type the configured # boards into the field
        and click Extend. Quietly returns otherwise — positions and
        the boards value are both optional."""
        if self.cfg.extend_match_boards <= 0:
            return
        if ("match_end_boards_field" not in self.cfg.positions
                or "match_end_extend_btn" not in self.cfg.positions):
            return
        if not self._match_end_dialog_visible():
            return
        n = self.cfg.extend_match_boards
        # Click the # boards field, select existing content, type n.
        self._click("match_end_boards_field")
        time.sleep(0.1)
        # Triple-click to select the existing value (Wine spinbox).
        xdo("click", "--repeat", "3", "--delay", "30", "1")
        time.sleep(0.1)
        xdo("type", "--delay", "20", str(n))
        time.sleep(0.15)
        self._click("match_end_extend_btn")
        self.log.emit(
            f"  auto-extended Match End by {n} boards")
        # Q-Plus needs a beat to dismiss the dialog and resume.
        time.sleep(0.5)

    def _wait_loop(self, seconds: float):
        remaining = seconds
        while remaining > 0 and not self._stop:
            chunk = min(1.5, remaining)
            time.sleep(chunk)
            remaining -= chunk
            # Auto-dismiss Q-Plus's Simulation popup if it appears
            # at any point in this wait. Safe: only fires when the
            # window-name search actually finds the dialog.
            self._maybe_dismiss_simulation()
            # Auto-extend if Q-Plus's Match End dialog appears.
            self._maybe_extend_match()

    def _repeat_deal_sequence(self, deal_num: int = 0):
        """Q-Plus 'Deal → Repeat deal' with 'complete deal' +
        'Computer' radios. Used in curated runs so the SAME
        physical deal can be played multiple times with different
        system pairs, bypassing Q-Plus's per-match dedup-by-cards.

        Sequence:
          1. click Deal menu in menu bar
          2. click Repeat deal item
          3. (dialog opens) click 'complete deal' radio
          4. click 'Computer' radio
          5. click OK
        After the OK the dialog closes and Q-Plus replays the deal
        from the top; Start-bidding/Autoplay sequencing follows.
        """
        # Verify the operator calibrated the repeat-deal positions.
        required = ("deal_menu", "repeat_deal_item",
                    "repeat_complete_radio",
                    "repeat_computer_radio", "repeat_ok_btn")
        missing = [k for k in required if k not in self.cfg.positions]
        if missing:
            raise RuntimeError(
                "Repeat-deal needs calibrated positions: "
                f"missing {missing}")
        self._focus()
        self._click("deal_menu");             self._pause_step()
        self._click("repeat_deal_item");      self._pause_close()
        self._click("repeat_complete_radio"); self._pause_step()
        self._click("repeat_computer_radio"); self._pause_step()
        self._click("repeat_ok_btn");         self._pause_close()
        if deal_num:
            self.log.emit(
                f"  → repeated deal {deal_num} (curated run)")

    def _play_one_deal(self, deal_num: int = 0,
                       skip_next_deal: bool = False,
                       use_repeat_deal: bool = False):
        # Next Deal: Q-Plus advances to the new layout. Skipped for
        # the very first deal of a run when Q-Plus has just been
        # loaded and Own deals → Play has put Q-Plus on the starting
        # deal already — its bottom-left button then reads "Start
        # bidding", not "Next deal", so clicking the next_deal
        # position would fire Start bidding prematurely (no systems
        # set yet on subsequent deals' code path — but here systems
        # ARE set first, so the more pressing problem is that we'd
        # skip past the starting deal entirely on a fresh-load run).
        # Drain any blocking dialog before the Next-deal click — a
        # Match End popup that appeared after the previous deal's
        # cardplay wait ended would otherwise eat this click.
        self._maybe_extend_match()
        self._maybe_dismiss_simulation()
        if skip_next_deal:
            if deal_num:
                self.log.emit(
                    f"  → skipping Next deal click — Q-Plus is "
                    f"already on deal {deal_num} (just-loaded "
                    "Own deals → Play state)")
        elif use_repeat_deal:
            self._repeat_deal_sequence(deal_num=deal_num)
            self._wait_loop(self.cfg.after_next_deal_s)
        else:
            self._click("next_deal")
            self._wait_loop(self.cfg.after_next_deal_s)
            if deal_num:
                self.log.emit(
                    f"  → Q-Plus now showing deal {deal_num} layout")
        if deal_num:
            # Log the manifest PBN HERE (not earlier in run()) so
            # the line refers to the deal Q-Plus is currently
            # displaying, not the one we just set systems for.
            if (self.cfg.pbn_blobs is not None
                    and 1 <= deal_num <= len(self.cfg.pbn_blobs)):
                self.log.emit(
                    f"  manifest deal {deal_num} PBN: "
                    f"{self.cfg.pbn_blobs[deal_num - 1]}")
        # Verification screenshot AFTER Next deal but BEFORE Start
        # bidding. This is the only moment where the new deal's
        # cards are face up (all four seats = Q-plus) AND Q-Plus's
        # status bar shows the systems we just set — both checks
        # against the manifest happen against this one image:
        #   1. status bar N/S+E/W tags match manifest's ns_system /
        #      ew_system for this deal,
        #   2. the four face-up hands match the manifest's PBN line
        #      logged just above.
        if self.cfg.screenshot_per_deal and deal_num:
            fn = SCREENSHOT_DIR / f"deal_{deal_num:03d}_predeal.png"
            ok, msg = grab_qplus_screenshot(fn, self.cfg.window_id)
            self.log.emit(
                f"  predeal screenshot {'OK' if ok else 'FAIL'}: "
                f"{msg} (verify systems in status bar + cards "
                "match manifest PBN above)")
        # Start Bidding: Q-Plus runs the auction using the systems
        # we just set in _set_systems_for_deal.
        self._click("start_bidding")
        if deal_num:
            self.log.emit(
                f"  → Q-Plus auctioning deal {deal_num}")
        self._wait_loop(self.cfg.after_start_bidding_s)
        # Autoplay: Q-Plus plays the deal out.
        self._click("autoplay")
        if deal_num:
            self.log.emit(
                f"  → Q-Plus playing deal {deal_num} cardplay")
        # Poll for cardplay-finished (screen quiescent for ≥3 consecutive
        # polls, with no Simulation/Match End up) instead of waiting a
        # fixed budget. The per_deal_s value now acts as a SAFETY TIMEOUT
        # — if the screen never goes quiescent, we cap the wait. This
        # eliminates the +1 deal drift that happened on the 39477 run
        # when Simulation auto-dismiss extended cardplay just past the
        # 90s budget, causing the harness to set-systems for deal N+1
        # while Q-Plus was still committing deal N.
        finished = self._wait_for_cardplay_finished(
            max_wait_s=self.cfg.per_deal_s)
        if deal_num:
            if finished:
                self.log.emit(
                    f"  cardplay finished (screen quiescent)")
            else:
                self.log.emit(
                    f"  cardplay budget {self.cfg.per_deal_s:.0f}s "
                    f"elapsed without quiescence — moving on anyway")

    # --- entry points ---

    def run(self):
        pairs = self.cfg.system_pairs
        start = self.cfg.starting_deal_index
        total = len(pairs)
        try:
            for i in range(start, total):
                if self._stop:
                    self.status.emit("STOPPED", "#cc6633")
                    self.finished.emit(False)
                    return
                ns, ew = pairs[i]
                deal_num = i + 1
                self.progress.emit(i + 1, total, f"deal {deal_num}/{total}")
                self.status.emit(
                    f"RUNNING  deal {deal_num}/{total}   "
                    f"N/S={ns}   E/W={ew}", "#ddaa22")
                # Order the log lines to reflect Q-Plus's actual
                # state: when we set systems, Q-Plus is still on
                # the PREVIOUS deal. Q-Plus only catches up to the
                # current deal_num after the Next-Deal click in
                # _play_one_deal — that step logs "→ Q-Plus now
                # showing deal N layout" separately.
                self.log.emit(
                    f"[deal {deal_num}/{total}] ABOUT TO SET UP "
                    f"deal {deal_num} (Q-Plus still showing "
                    f"deal {deal_num - 1 if deal_num > 1 else '—'})")
                self.log.emit(f"  systems: N/S={ns}  E/W={ew}")
                # PBN is NOT logged here on purpose — at this point
                # Q-Plus is still showing deal N-1, so a "manifest
                # deal N PBN" line would mismatch the cards on
                # screen. The PBN is logged inside _play_one_deal,
                # right after Q-Plus advances to deal N.
                self._set_systems_for_deal(ns, ew, deal_num=deal_num)
                if self._stop:
                    self.status.emit("STOPPED", "#cc6633")
                    self.finished.emit(False)
                    return
                # Only the first iteration honours the "Q-Plus
                # already on starting deal" flag — once we've
                # cycled through Next deal → Start bidding →
                # Autoplay once, subsequent deals always need a
                # Next-deal click to advance.
                # Skip Next-deal click when (a) it's the first
                # iteration of the run AND the operator told us
                # Q-Plus is already on the starting deal, or
                # (b) the previous iteration ended a batch and
                # the auto-rollover just put Q-Plus on the next
                # batch's first deal (after Play). Both are the
                # same logical condition: "Q-Plus is already
                # showing the deal we're about to bid on".
                skip_next_deal = (
                    (i == start and self.cfg.qplus_on_starting_deal)
                    or self._post_rollover_skip)
                if self._post_rollover_skip:
                    self._post_rollover_skip = False
                # In curated mode, only the FIRST cell of each
                # physical deal uses Next-deal; the remaining
                # (cells_per_deal - 1) cells use Repeat-deal to
                # bypass Q-Plus's per-match dedup.
                use_repeat_deal = (
                    self.cfg.is_curated
                    and self.cfg.cells_per_deal > 1
                    and (i - start) % self.cfg.cells_per_deal != 0)
                self._play_one_deal(
                    deal_num=deal_num,
                    skip_next_deal=skip_next_deal,
                    use_repeat_deal=use_repeat_deal)
                # Batch break: Q-Plus's match buffer caps at
                # `deals_per_match` deals; once we've played that
                # many in the current match, pause for the operator
                # to File → Save match and exit, then reopen
                # Q-Plus to a fresh empty match. Without this pause,
                # the tail deals get silently dropped (the 11075 and
                # 7371 runs each lost 31 deals beyond deal 64).
                deals_in_batch = (i - start) + 1
                deal_within_batch = deals_in_batch % self.cfg.deals_per_match
                more_to_go = (i + 1) < total
                if (self.cfg.deals_per_match > 0
                        and deal_within_batch == 0 and more_to_go):
                    batch_num = deals_in_batch // self.cfg.deals_per_match
                    self.log.emit(
                        f"[batch {batch_num} complete] {deals_in_batch} "
                        f"deals played in this match — pausing for "
                        f"save+exit + reopen Q-Plus.")
                    # Buffer wait: Q-Plus needs time after cardplay
                    # completes to commit the last deal's state to
                    # its internal score tracker. Without this, when
                    # the user does save+exit, the LAST 1-2 deals are
                    # missing from savescore.qss (observed on 80719 +
                    # 26195 curated runs: deals 63 & 64 always lost).
                    # The cardplay-finished detection says "screen
                    # quiescent" but Q-Plus's score-record state
                    # machine hasn't caught up yet.
                    self.log.emit(
                        f"  waiting 15s for Q-Plus to fully commit "
                        f"last deals before prompting save+exit...")
                    self._wait_loop(15.0)
                    if self._stop:
                        self.finished.emit(False)
                        return
                    self.status.emit(
                        f"BATCH {batch_num} COMPLETE — save+exit Q-Plus, "
                        f"reopen to fresh match, then click Continue",
                        "#aa66cc")
                    self._batch_resume = False
                    self.batch_break.emit(batch_num, deal_num, i + 2)
                    # Poll until UI calls resume_after_batch().
                    while not self._batch_resume and not self._stop:
                        time.sleep(0.3)
                    if self._stop:
                        self.status.emit("STOPPED", "#cc6633")
                        self.finished.emit(False)
                        return
                    self.log.emit(
                        f"[batch {batch_num + 1} starting] resuming "
                        f"with deal {deal_num + 1}/{total} in a fresh "
                        f"Q-Plus match.")
            # Same end-of-batch concern as in the batch-break flow:
            # Q-Plus needs time to commit the last deal's state
            # before the user does save+exit. Wait before signalling
            # the UI to show the save-exit-then-merge modal.
            self.log.emit(
                "  waiting 15s for Q-Plus to fully commit last deals "
                "before prompting final save+exit...")
            self._wait_loop(15.0)
            self.status.emit(
                f"DONE — {total} deals.  Save match in Q-Plus to "
                "flush the BDL.", "#22aa55")
            self.log.emit("[run] all deals done.")
            self.finished.emit(True)
        except Exception as ex:
            self.status.emit(f"ERROR: {ex!r}", "#cc3333")
            self.log.emit(f"[run] ERROR: {ex!r}")
            self.finished.emit(False)

    def run_set_only(self, deal_index_0based: int, ns: str, ew: str):
        """Set systems for ONE deal — open the dialog, click radio +
        list + Set-for-N/S, click radio + list + Set-for-E/W, close.
        Does NOT click Next Deal / Start bidding / Autoplay; the
        user plays that deal manually in Q-Plus to verify the cards
        + system tags before committing to a full run."""
        deal_num = deal_index_0based + 1
        try:
            self.status.emit(
                f"SET-ONLY  deal {deal_num}: N/S={ns} ({SYSTEM_TAG[ns]})  "
                f"E/W={ew} ({SYSTEM_TAG[ew]})", "#ddaa22")
            self.log.emit(f"[set-only] deal {deal_num}: "
                          f"N/S={ns}  E/W={ew}")
            if (self.cfg.pbn_blobs is not None
                    and 0 <= deal_index_0based < len(self.cfg.pbn_blobs)):
                self.log.emit(
                    f"  manifest: {self.cfg.pbn_blobs[deal_index_0based]}")
            self._set_systems_for_deal(ns, ew, deal_num=deal_num)
            # Screenshot proves what Q-Plus's status bar now says.
            fn = (SCREENSHOT_DIR
                  / f"manual_deal_{deal_num:03d}_systems.png")
            ok, msg = grab_qplus_screenshot(fn, self.cfg.window_id)
            self.log.emit(
                f"  screenshot {'OK' if ok else 'FAIL'}: {msg}")
            self.status.emit(
                f"SET-ONLY DONE — Q-Plus should show N/S: "
                f"{SYSTEM_TAG[ns]} ; E/W: {SYSTEM_TAG[ew]}. "
                "Click Next deal in Q-Plus to play this deal "
                "manually.", "#22aa55")
            self.finished.emit(True)
        except Exception as ex:
            self.status.emit(f"SET-ONLY ERROR: {ex!r}", "#cc3333")
            self.log.emit(f"[set-only] ERROR: {ex!r}")
            self.finished.emit(False)

    def run_test_all_five(self):
        """Cycle the dialog 5 times with MIXED NS≠EW pairs, so that
        a miscalibrated Set-for-N/S or Set-for-E/W is caught (a
        same-side test like NS=EW lets EW stay stuck while NS
        cycles, and the status bar still updates — looks fine to
        a quick glance).

        Each pass uses NS = system_i and EW = system_(i+1)%5. So
        every system appears once as NS and once as EW; every
        radio + every list entry + Set-for-N/S + Set-for-E/W + Close
        is exercised. A screenshot of Q-Plus is saved after each
        cycle to /tmp/qplus_mixed_corpus_screenshots/test_<pair>.png
        so you can verify the status bar tag against expectations
        AFTER THE FACT (no need to memorise 5 fast-changing pairs).
        """
        try:
            for i, ns in enumerate(SYSTEM_NAMES):
                if self._stop:
                    self.status.emit("TEST STOPPED", "#cc6633")
                    self.finished.emit(False)
                    return
                ew = SYSTEM_NAMES[(i + 1) % len(SYSTEM_NAMES)]
                self.status.emit(
                    f"TEST  N/S={ns} ({SYSTEM_TAG[ns]})   "
                    f"E/W={ew} ({SYSTEM_TAG[ew]})", "#ddaa22")
                self.log.emit(f"[test] cycle {i+1}/5  "
                              f"N/S={ns}  E/W={ew}  "
                              f"(expect status bar: N/S: "
                              f"{SYSTEM_TAG[ns]} ; E/W: "
                              f"{SYSTEM_TAG[ew]})")
                self._set_systems_for_deal(ns, ew)
                # Screenshot AFTER dialog closes so the status bar
                # is the only authoritative ground truth.
                fn = (SCREENSHOT_DIR
                      / f"test_cycle_{i+1}_ns-{ns}_ew-{ew}.png")
                ok, msg = grab_qplus_screenshot(fn, self.cfg.window_id)
                self.log.emit(
                    f"  screenshot {'OK' if ok else 'FAIL'}: {msg}")
                # Hold this pair for a moment so the user can also
                # glance at the live status bar between cycles.
                time.sleep(1.2)
            self.status.emit(
                "TEST DONE — verify each test_cycle_*.png shows the "
                "expected N/S and E/W tags in Q-Plus's status bar.",
                "#22aa55")
            self.log.emit("[test] cycled all 5 mixed pairs. Open "
                          f"{SCREENSHOT_DIR} and check the status "
                          "bar in each screenshot — must match the "
                          "filename's ns-/ew- tags.")
            self.finished.emit(True)
        except Exception as ex:
            self.status.emit(f"TEST ERROR: {ex!r}", "#cc3333")
            self.log.emit(f"[test] ERROR: {ex!r}")
            self.finished.emit(False)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class CorpusTab(QWidget):
    """Self-contained tab for one corpus type — generate, write
    BDE, run, verify, all without leaving the tab.

    `corpus_type` is one of:
      * "random"     — random deals + random (NS, EW) system pairs
      * "matrix"     — every (NS, EW) cell in the 5×5 grid gets N
        deals (deterministic system labels)
      * "slam"       — random deals filtered for slam-rich HCP
        (≥30 default), paired with random systems
      * "grand_slam" — same filter, higher default threshold (37)
        and a bigger candidate scan budget for the rarer
        grand-slam-strength hands

    Calibration positions, the worker thread, the log pane and
    the status banner live on the MainWindow reference (`self.main`).
    Per-tab state (deals, system_pairs, BDE path, batch BDEs) lives
    on this widget. The 3 corpus tabs are fully independent — you
    can generate a random corpus on one tab while a slam run plays
    out from another (subject to one-worker-at-a-time).
    """

    def __init__(self, main_window, corpus_type: str):
        super().__init__()
        self.main = main_window
        self.corpus_type = corpus_type
        self.deals: List[BoardState] = []
        self.system_pairs: List[Tuple[str, str]] = []
        self.bde_path: Optional[Path] = None
        self.manifest_path: Optional[Path] = None
        self.batch_bde_paths: List[Path] = []
        self._bde_name_user_edited = False
        self._build()
        self._refresh_bde_banner()

    # ---- UI scaffolding ----

    def _build(self):
        v = QVBoxLayout(self)
        v.addWidget(self._build_generate_box())
        self.bde_banner = QLabel()
        self.bde_banner.setFont(QFont("monospace"))
        self.bde_banner.setStyleSheet(
            "font-size: 13px; padding: 8px; "
            "background: #223; color: white; "
            "border: 1px solid #557;")
        self.bde_banner.setWordWrap(True)
        v.addWidget(self.bde_banner)
        self.manifest_table = QTableWidget(0, 5)
        self.manifest_table.setHorizontalHeaderLabels(
            ["Deal #", "Dealer", "Vul", "N/S system", "E/W system"])
        self.manifest_table.setMaximumHeight(220)
        v.addWidget(self.manifest_table)
        v.addWidget(self._build_run_box())

    def _build_generate_box(self) -> QGroupBox:
        title = {
            "random":     "Generate random-system corpus",
            "matrix":     "Generate 5×5 bidding-system matrix corpus",
            "slam":       "Generate slam-eligible corpus",
            "grand_slam": "Generate grand-slam-eligible corpus",
        }[self.corpus_type]
        box = QGroupBox(title)
        cf = QFormLayout(box)
        # Deal seed shared by all corpus types.
        self.deal_seed = QSpinBox()
        self.deal_seed.setRange(0, 999_999)
        self.deal_seed.setValue(random.randint(1, 100_000))
        cf.addRow("Deal seed", self.deal_seed)
        # System seed used by random + slam + grand_slam (the matrix
        # corpus has deterministic system labels — every cell is
        # exercised equally, so randomising the pair order would
        # just add noise).
        if self.corpus_type in ("random", "slam", "grand_slam"):
            self.system_seed = QSpinBox()
            self.system_seed.setRange(0, 999_999)
            self.system_seed.setValue(random.randint(1, 100_000))
            cf.addRow("System pair seed", self.system_seed)
        # Corpus-type-specific knobs.
        if self.corpus_type == "random":
            self.deal_count = QSpinBox()
            self.deal_count.setRange(1, 1000)
            self.deal_count.setValue(95)
            cf.addRow("# deals", self.deal_count)
        elif self.corpus_type == "matrix":
            # No knobs beyond the seed — the generator auto-picks
            # 4 slam-eligible base hands (each with 25 unique
            # spot-perm permutations available) from the random
            # stream, expanding to a 100-deal corpus.
            info = QLabel(
                "Auto-selects 4 slam-eligible base hands from "
                "the seed stream (filter: HCP ≥ 28 on one side, "
                "or ≥ 26 with an 8+ card fit, AND 25 unique "
                "spot-card permutations available). Each base "
                "hand is expanded into 25 cells of the 5×5 "
                "(NS_system, EW_system) grid with EW spot cards "
                "perturbed so Q-Plus sees each cell as a "
                "distinct deal — NS hands stay identical across "
                "all 25 cells of a base hand, so biq's NS "
                "auction varies only with the NS system, not "
                "the cards. Total: 4 × 25 = 100 deals.")
            info.setWordWrap(True)
            cf.addRow("Hand selection", info)
        elif self.corpus_type == "slam":
            self.deal_count = QSpinBox()
            self.deal_count.setRange(1, 500)
            self.deal_count.setValue(64)
            cf.addRow("# slam-eligible deals", self.deal_count)
            self.slam_hcp_threshold = QSpinBox()
            self.slam_hcp_threshold.setRange(24, 37)
            self.slam_hcp_threshold.setValue(30)
            self.slam_hcp_threshold.setSuffix(" HCP")
            self.slam_hcp_threshold.setToolTip(
                "A deal qualifies if either partnership (NS or "
                "EW) has at least this many combined HCP, or "
                "(threshold − 2) HCP with an 8+ card fit. Lower "
                "threshold = more deals qualify but fewer real "
                "slam hands.")
            cf.addRow("Min combined HCP (one side)",
                      self.slam_hcp_threshold)
        elif self.corpus_type == "grand_slam":
            self.deal_count = QSpinBox()
            # Grand-slam-strength deals are far rarer than small-
            # slam-strength ones — a 37-HCP partnership shows up
            # in only ~0.3% of random deals. 32 is a comfortable
            # default that still finds enough candidates in the
            # default 5000-deal scan; bigger # deals or lower
            # threshold both require bumping max_candidates.
            self.deal_count.setRange(1, 200)
            self.deal_count.setValue(32)
            cf.addRow("# grand-slam-eligible deals", self.deal_count)
            self.slam_hcp_threshold = QSpinBox()
            self.slam_hcp_threshold.setRange(32, 40)
            self.slam_hcp_threshold.setValue(37)
            self.slam_hcp_threshold.setSuffix(" HCP")
            self.slam_hcp_threshold.setToolTip(
                "Standard grand-slam zone: 37+ combined HCP gives "
                "the partnership enough strength to expect 13 "
                "tricks on most distributions. Same filter as the "
                "slam-eligible tab (threshold or threshold−2 with "
                "an 8+ card fit), just with a higher default.")
            cf.addRow("Min combined HCP (one side)",
                      self.slam_hcp_threshold)
            self.slam_max_candidates = QSpinBox()
            self.slam_max_candidates.setRange(1000, 200_000)
            self.slam_max_candidates.setValue(50_000)
            self.slam_max_candidates.setSingleStep(5000)
            self.slam_max_candidates.setToolTip(
                "How many random deals to scan in search of "
                "grand-slam-strength qualifiers. Grand-slam hands "
                "are rare (~0.3% at 37 HCP), so this needs to be "
                "much higher than the slam-eligible default. Bump "
                "if the generator complains it can't find enough.")
            cf.addRow("Scan up to", self.slam_max_candidates)
        # BDE filename.
        self.bde_name = QLineEdit(self._default_bde_name())
        self.bde_name.textEdited.connect(self._on_bde_name_edited)
        self.deal_seed.valueChanged.connect(self._refresh_bde_name)
        if hasattr(self, "system_seed"):
            self.system_seed.valueChanged.connect(self._refresh_bde_name)
        cf.addRow("BDE filename", self.bde_name)
        row = QHBoxLayout()
        self.btn_generate = QPushButton(
            f"Generate {self.corpus_type} corpus")
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_write_bde = QPushButton("Write BDE to Q-Plus")
        self.btn_write_bde.clicked.connect(self._on_write_bde)
        self.btn_write_bde.setEnabled(False)
        row.addWidget(self.btn_generate)
        row.addWidget(self.btn_write_bde)
        cf.addRow(row)
        return box

    def _build_run_box(self) -> QGroupBox:
        box = QGroupBox("Run + verify")
        v = QVBoxLayout(box)
        form = QFormLayout()
        self.after_dialog_step_ms = QSpinBox()
        self.after_dialog_step_ms.setRange(10, 3000)
        self.after_dialog_step_ms.setValue(200)
        self.after_dialog_step_ms.setSuffix(" ms")
        self.after_dialog_close_ms = QSpinBox()
        self.after_dialog_close_ms.setRange(20, 5000)
        self.after_dialog_close_ms.setValue(300)
        self.after_dialog_close_ms.setSuffix(" ms")
        self.after_next_deal_s = QSpinBox()
        self.after_next_deal_s.setRange(1, 30)
        self.after_next_deal_s.setValue(2)
        self.after_next_deal_s.setSuffix(" s")
        self.after_start_bidding_s = QSpinBox()
        self.after_start_bidding_s.setRange(5, 120)
        self.after_start_bidding_s.setValue(25)
        self.after_start_bidding_s.setSuffix(" s")
        self.per_deal_s = QSpinBox()
        self.per_deal_s.setRange(10, 300)
        self.per_deal_s.setValue(90)
        self.per_deal_s.setSuffix(" s")
        self.extend_match_boards = QSpinBox()
        self.extend_match_boards.setRange(0, 999)
        self.extend_match_boards.setValue(64)
        self.extend_match_boards.setSuffix(" boards")
        self.start_at_deal = QSpinBox()
        self.start_at_deal.setRange(1, 10000)
        self.start_at_deal.setValue(1)
        self.screenshot_chk = QCheckBox(
            "Save per-deal verification screenshot")
        self.screenshot_chk.setChecked(True)
        self.qplus_on_starting_deal_chk = QCheckBox(
            "Q-Plus already on starting deal (skip 'Next deal' "
            "for first deal only)")
        self.qplus_on_starting_deal_chk.setChecked(True)
        form.addRow("Per-dialog-click pause", self.after_dialog_step_ms)
        form.addRow("After dialog close",     self.after_dialog_close_ms)
        form.addRow("After Next deal",        self.after_next_deal_s)
        form.addRow("After Start bidding",    self.after_start_bidding_s)
        form.addRow("Cardplay budget",        self.per_deal_s)
        form.addRow("Auto-extend Match End by",
                    self.extend_match_boards)
        form.addRow("Start from deal #",      self.start_at_deal)
        form.addRow(self.screenshot_chk)
        form.addRow(self.qplus_on_starting_deal_chk)
        v.addLayout(form)
        row = QHBoxLayout()
        self.btn_run = QPushButton("Run")
        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)
        v.addLayout(row)
        verify_row = QHBoxLayout()
        self.btn_verify = QPushButton(
            "Verify BDL vs manifest (report only)")
        self.btn_verify.clicked.connect(
            lambda: self._on_verify(reconcile=False))
        self.btn_reconcile = QPushButton(
            "Reconcile manifest to BDL")
        self.btn_reconcile.clicked.connect(
            lambda: self._on_verify(reconcile=True))
        verify_row.addWidget(self.btn_verify)
        verify_row.addWidget(self.btn_reconcile)
        v.addLayout(verify_row)
        # Comparison-mode tri-state widget + run-comparison button.
        # See CLAUDE.md for the full spec: bidding / cardplay /
        # end-to-end. The diff tool's `--mode` flag picks which
        # axis is being measured.
        compare_row = QHBoxLayout()
        compare_row.addWidget(QLabel("Compare:"))
        self.compare_mode = QComboBox()
        self.compare_mode.addItem("Bidding only", "bidding")
        self.compare_mode.addItem("Cardplay only "
                                  "(Q-Plus contract, both sides play)",
                                  "cardplay")
        self.compare_mode.addItem("End-to-end (bidding + cardplay)",
                                  "end-to-end")
        self.compare_mode.setToolTip(
            "Bidding only: biq's bidder vs Q-Plus's bidder, both contracts "
            "scored via DDS (current default).\n"
            "Cardplay only: Q-Plus's recorded contract is used for BOTH "
            "sides; Q-Plus's recorded tricks vs biq's MC+DDS-played tricks "
            "on the same contract.\n"
            "End-to-end: each side bids its own contract AND plays it "
            "(biq via MC+DDS, Q-Plus via recorded tricks). Conflates "
            "bidding + cardplay strength.")
        compare_row.addWidget(self.compare_mode, stretch=1)
        self.btn_compare = QPushButton("Run comparison")
        self.btn_compare.clicked.connect(self._on_compare)
        compare_row.addWidget(self.btn_compare)
        v.addLayout(compare_row)
        self.progress = QProgressBar()
        v.addWidget(self.progress)
        return box

    # ---- naming helpers ----

    def _default_bde_name(self) -> str:
        ds = self.deal_seed.value()
        if self.corpus_type == "random":
            return f"r{ds}_{self.system_seed.value()}.BDE"
        if self.corpus_type == "matrix":
            return f"m{ds}.BDE"
        if self.corpus_type == "slam":
            return f"s{ds}_{self.system_seed.value()}.BDE"
        if self.corpus_type == "grand_slam":
            return f"gs{ds}_{self.system_seed.value()}.BDE"
        return f"{self.corpus_type}_{ds}.BDE"

    def _on_bde_name_edited(self, _text):
        self._bde_name_user_edited = True

    def _refresh_bde_name(self):
        if self._bde_name_user_edited:
            return
        self.bde_name.blockSignals(True)
        self.bde_name.setText(self._default_bde_name())
        self.bde_name.blockSignals(False)

    def _refresh_bde_banner(self):
        if self.bde_path is None:
            self.bde_banner.setText(
                f"No {self.corpus_type} BDE written yet. "
                "Generate, then click 'Write BDE to Q-Plus'.")
            return
        n = len(self.system_pairs) if self.system_pairs else 0
        ds = self.deal_seed.value()
        extra = ""
        if hasattr(self, "system_seed"):
            extra = f"  ·  system seed {self.system_seed.value()}"
        n_batches = len(self.batch_bde_paths)
        batch_line = ""
        if n_batches > 1:
            files_str = ", ".join(p.name for p
                                  in self.batch_bde_paths)
            batch_line = (f"\n  split into {n_batches} batches: "
                          f"{files_str} — auto-rollover will load "
                          f"each in turn")
        self.bde_banner.setText(
            f"Q-Plus should be displaying BDE: "
            f"{self.bde_path.name}\n"
            f"  full path: {self.bde_path}\n"
            f"  {n} deals  ·  deal seed {ds}{extra}"
            f"{batch_line}")

    # ---- actions (delegate to MainWindow) ----

    def _on_generate(self):
        try:
            if self.corpus_type == "random":
                n = self.deal_count.value()
                self.deals = gen_random_deals(
                    n, self.deal_seed.value())
                self.system_pairs = gen_random_system_pairs(
                    n, self.system_seed.value())
            elif self.corpus_type == "matrix":
                self.deals, self.system_pairs = (
                    gen_bidding_system_matrix(
                        self.deal_seed.value()))
            elif self.corpus_type == "slam":
                n = self.deal_count.value()
                self.deals = gen_slam_eligible_deals(
                    n, self.deal_seed.value(),
                    self.slam_hcp_threshold.value())
                self.system_pairs = gen_random_system_pairs(
                    n, self.system_seed.value())
            elif self.corpus_type == "grand_slam":
                n = self.deal_count.value()
                # Reuses the slam-eligible generator with a higher
                # default threshold (37 vs 30) and a bigger
                # candidate-scan budget — grand-slam-strength deals
                # are an order of magnitude rarer than small-slam.
                self.deals = gen_slam_eligible_deals(
                    n, self.deal_seed.value(),
                    self.slam_hcp_threshold.value(),
                    max_candidates=
                        self.slam_max_candidates.value())
                self.system_pairs = gen_random_system_pairs(
                    n, self.system_seed.value())
        except RuntimeError as ex:
            QMessageBox.warning(self, "Generate failed", str(ex))
            return
        self._populate_manifest_table()
        self.btn_write_bde.setEnabled(True)
        self.start_at_deal.setMaximum(len(self.deals))
        self.main._log(
            f"[{self.corpus_type}] generated {len(self.deals)} "
            f"deals (deal seed {self.deal_seed.value()})")
        self.main._set_status(
            f"{self.corpus_type.title()} corpus ready: "
            f"{len(self.deals)} deals — click 'Write BDE to "
            f"Q-Plus' next.", "#666")

    def _populate_manifest_table(self):
        self.manifest_table.setRowCount(len(self.deals))
        for i, (board, (ns, ew)) in enumerate(
                zip(self.deals, self.system_pairs)):
            self.manifest_table.setItem(
                i, 0, QTableWidgetItem(str(board.board_number)))
            self.manifest_table.setItem(
                i, 1, QTableWidgetItem(board.dealer.to_char()))
            self.manifest_table.setItem(
                i, 2, QTableWidgetItem(
                    str(board.vulnerability.name)))
            self.manifest_table.setItem(i, 3, QTableWidgetItem(ns))
            self.manifest_table.setItem(i, 4, QTableWidgetItem(ew))
        self.manifest_table.resizeColumnsToContents()

    def _on_write_bde(self):
        self.main.write_bde_for_tab(self)
        self._refresh_bde_banner()

    def _on_run(self):
        self.main.start_run_for_tab(self)

    def _on_stop(self):
        self.main.stop_current_run()

    def _on_verify(self, *, reconcile: bool):
        self.main.verify_for_tab(self, reconcile=reconcile)

    def _on_compare(self):
        mode = self.compare_mode.currentData()
        self.main.compare_for_tab(self, mode=mode)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Q-Plus Corpus Builder")
        self.resize(1100, 900)

        self.positions: Dict[str, Tuple[int, int]] = {}
        self.deals: List[BoardState] = []
        self.system_pairs: List[Tuple[str, str]] = []
        self.bde_path: Optional[Path] = None
        self.manifest_path: Optional[Path] = None
        self.worker: Optional[RunWorker] = None
        self.worker_thread: Optional[QThread] = None

        # Every log line is also streamed to disk so the operator's
        # terminal-window record survives a crash / accidental close.
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        import datetime
        self.log_path = (LOG_DIR
                         / f"session_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
        self._log_file = None  # opened lazily on first write

        self._build_ui()
        self._load_cached_positions()
        self._log(f"[session] writing log to {self.log_path}")
        self._archive_stale_bdes()

    # ------------ UI ----------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # Persistent status banner at the very top.
        self.status_banner = QLabel("Status: IDLE")
        self.status_banner.setStyleSheet(
            "font-size: 16px; padding: 8px; "
            "background: #333; color: white;")
        outer.addWidget(self.status_banner)

        # Tabs — top-down hierarchy: calibrate once, then each
        # corpus type lives in its own self-contained tab with
        # its own generate / write / run / verify controls.
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_calibration_tab(),
                         "1. Calibration")
        self.tab_random = CorpusTab(self, "random")
        self.tab_matrix = CorpusTab(self, "matrix")
        self.tab_slam = CorpusTab(self, "slam")
        self.tab_grand_slam = CorpusTab(self, "grand_slam")
        self.tabs.addTab(self._wrap_scroll(self.tab_random),
                         "2. Random deals")
        self.tabs.addTab(self._wrap_scroll(self.tab_matrix),
                         "3. Bidding system matrix")
        self.tabs.addTab(self._wrap_scroll(self.tab_slam),
                         "4. Slam-eligible deals")
        self.tabs.addTab(self._wrap_scroll(self.tab_grand_slam),
                         "5. Grand slam deals")
        self.tabs.addTab(self._build_help_tab(), "Help")
        # Live head-to-head tab — folded in from the standalone control
        # panel (tools/qplus_control_panel.py). Offline corpus tabs above
        # are for quick bidding tests; this one drives a real end-to-end
        # match against the running Q-Plus server. Lazy import + guard so
        # a problem here can never break the corpus GUI.
        try:
            from qplus_control_panel import LiveMatchWidget
            self.tab_live = LiveMatchWidget()
            self.tabs.insertTab(0, self.tab_live, "⚔ Live head-to-head")
            self.tabs.setCurrentIndex(0)
        except Exception as exc:
            sys.stderr.write(f"[live tab] not loaded: {exc}\n")
        # Track which tab is currently driving the worker — the
        # *_for_tab helpers below set this and shared callbacks
        # (worker progress, finish, batch break) read it.
        self._active_tab: Optional[CorpusTab] = None
        outer.addWidget(self.tabs, stretch=1)

        # Persistent log at the bottom (always visible).
        self.log_box = QGroupBox("Log")
        log_l = QVBoxLayout(self.log_box)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("monospace"))
        self.log.setMinimumHeight(160)
        log_l.addWidget(self.log)
        outer.addWidget(self.log_box, stretch=0)

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        """Wrap a CorpusTab in a scroll area so the run-controls
        section stays reachable on smaller screens."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(widget)
        return sa

    # ----- Adapters: pre-CorpusTab MainWindow code lived on
    # self.* (self.deals, self.system_pairs, self.deal_seed, …).
    # The CorpusTab class now owns that state per-tab. Each *_for_tab
    # adapter copies the active tab's state onto MainWindow before
    # delegating to the legacy single-corpus method, then copies any
    # mutations back to the tab. This keeps the diff small without
    # re-plumbing every call site.

    def _sync_tab_to_main(self, tab: "CorpusTab"):
        self._active_tab = tab
        # Generated-corpus state
        self.deals = list(tab.deals)
        self.system_pairs = list(tab.system_pairs)
        self.bde_path = tab.bde_path
        self.manifest_path = tab.manifest_path
        self._batch_bde_paths = list(tab.batch_bde_paths)
        # Generator widget references (legacy code reads
        # self.deal_seed.value() etc.). Matrix tab doesn't have a
        # system_seed; expose a stand-in spinbox so legacy code
        # doesn't blow up.
        self.deal_seed = tab.deal_seed
        if hasattr(tab, "system_seed"):
            self.system_seed = tab.system_seed
        else:
            # Matrix corpus pins system pairs deterministically;
            # legacy code only reads .value() for logging, so a
            # zero is safe.
            class _Zero:
                def value(self): return 0
            self.system_seed = _Zero()
        self.bde_name = tab.bde_name
        self.manifest_table = tab.manifest_table
        # Run-control widget references
        self.after_dialog_step_ms = tab.after_dialog_step_ms
        self.after_dialog_close_ms = tab.after_dialog_close_ms
        self.after_next_deal_s = tab.after_next_deal_s
        self.after_start_bidding_s = tab.after_start_bidding_s
        self.per_deal_s = tab.per_deal_s
        self.extend_match_boards = tab.extend_match_boards
        self.start_at_deal = tab.start_at_deal
        self.screenshot_chk = tab.screenshot_chk
        self.qplus_on_starting_deal_chk = tab.qplus_on_starting_deal_chk
        self.loaded_bde_label = tab.bde_banner
        self.btn_run = tab.btn_run
        self.btn_stop = tab.btn_stop
        self.progress = tab.progress
        # The corpus-type tabs don't expose the curated-mode
        # flags (curated workflow was teaching-deck-only and
        # isn't part of the new 4-tab UI). Reset the flags so
        # legacy code in _make_cfg picks the non-curated path.
        self._is_curated_corpus = False
        self._cells_per_deal = 1

    def _sync_main_to_tab(self, tab: "CorpusTab"):
        tab.deals = list(self.deals)
        tab.system_pairs = list(self.system_pairs)
        tab.bde_path = self.bde_path
        tab.manifest_path = self.manifest_path
        tab.batch_bde_paths = list(
            getattr(self, "_batch_bde_paths", []))

    def write_bde_for_tab(self, tab: "CorpusTab"):
        self._sync_tab_to_main(tab)
        self._on_write_bde()
        self._sync_main_to_tab(tab)

    def start_run_for_tab(self, tab: "CorpusTab"):
        self._sync_tab_to_main(tab)
        self._on_run()

    def stop_current_run(self):
        self._on_stop()

    def verify_for_tab(self, tab: "CorpusTab", *,
                       reconcile: bool):
        self._sync_tab_to_main(tab)
        self._on_verify(reconcile=reconcile)

    def compare_for_tab(self, tab: "CorpusTab", *, mode: str):
        """Run `tools/mixed_corpus_diff.py --mode <mode>` for the
        tab's most recent BDL + manifest. Streams output to the Log.

        Modes:
          * "bidding"    — biq bidder vs Q-Plus bidder, DDS-scored.
                           Current default behaviour.
          * "cardplay"   — Q-Plus's recorded contract for BOTH sides;
                           biq plays via MC+DDS, Q-Plus via recorded
                           tricks; compare tricks taken.
          * "end-to-end" — each side bids own contract and plays it
                           (biq MC+DDS / Q-Plus recorded); conflates
                           bidding + cardplay strength.

        See CLAUDE.md for the full spec.
        """
        self._sync_tab_to_main(tab)
        # Build BDL + manifest paths the same way _on_verify does —
        # prefer the most recent files matching this tab's seeds.
        own_dir = qplus_own_deals_dir()
        matches_dir = qplus_local_matches_dir()
        bdl_path = None
        if matches_dir and matches_dir.is_dir():
            qsses = sorted(matches_dir.glob("savescore.qss"),
                           key=lambda p: p.stat().st_mtime,
                           reverse=True)
            if qsses:
                bdl_path = qsses[0]
        # Prefer the archived merged QSS for this tab's seeds if it
        # exists (the diff tool reads QSS too, and the merged file
        # includes both batches when a 64-deal rollover occurred).
        ds = self.deal_seed.value() if hasattr(self, "deal_seed") else 0
        ss = (self.system_seed.value()
              if hasattr(self, "system_seed")
              and hasattr(self.system_seed, "value") else 0)
        merged_candidate = (ARCHIVE_DIR
                            / f"merged_{ds}_{ss}.qss")
        if merged_candidate.is_file():
            bdl_path = merged_candidate
        manifest_path = None
        if self.manifest_path is not None and self.manifest_path.is_file():
            manifest_path = self.manifest_path
        elif own_dir and own_dir.is_dir():
            manifests = sorted(own_dir.glob("*.manifest.json"),
                               key=lambda p: p.stat().st_mtime,
                               reverse=True)
            if manifests:
                manifest_path = manifests[0]
        if bdl_path is None or manifest_path is None:
            QMessageBox.warning(
                self, "Missing BDL or manifest",
                "Could not find a BDL/qss + manifest pair for this "
                "tab. Run the corpus through Q-Plus first, then try "
                "again.")
            return
        self._log(f"\n[compare {mode}] BDL:      {bdl_path}")
        self._log(f"[compare {mode}] manifest: {manifest_path}")
        # Invoke the diff tool in a subprocess so its long stdout
        # streams to the Log box without freezing the UI.
        diff_tool = Path(__file__).resolve().parent / "mixed_corpus_diff.py"
        if not diff_tool.is_file():
            QMessageBox.critical(
                self, "Diff tool missing",
                f"Expected {diff_tool} on disk (gitignored, "
                "local-only). Restore it from git history or another "
                "machine before running comparison.")
            return
        cmd = [
            "python3", str(diff_tool),
            "--bdl", str(bdl_path),
            "--manifest", str(manifest_path),
            "--mode", mode,
        ]
        self._log(f"[compare {mode}] running: {' '.join(cmd)}")
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                cwd=str(Path(__file__).resolve().parent.parent))
        except subprocess.TimeoutExpired:
            self._log(f"[compare {mode}] TIMEOUT after 10 minutes")
            return
        for line in out.stdout.splitlines():
            self._log(f"[compare {mode}] {line}")
        if out.stderr:
            for line in out.stderr.splitlines():
                self._log(f"[compare {mode} stderr] {line}")
        if out.returncode != 0:
            self._log(f"[compare {mode}] diff tool exited "
                      f"with code {out.returncode}")

    def _build_corpus_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        form_box = QGroupBox("Generate")
        cf = QFormLayout(form_box)
        self.deal_count = QSpinBox()
        self.deal_count.setRange(1, 1000)
        # 95 matches Q-Plus's typical match-board cap and avoids
        # the deal-97+ stalls we hit on the 100-deal run.
        self.deal_count.setValue(95)
        self.deal_seed = QSpinBox()
        self.deal_seed.setRange(0, 999_999)
        self.deal_seed.setValue(random.randint(1, 100_000))
        self.system_seed = QSpinBox()
        self.system_seed.setRange(0, 999_999)
        self.system_seed.setValue(random.randint(1, 100_000))
        # Default filename embeds both seeds, so each generated corpus
        # gets a unique filename — Q-Plus can't accidentally re-use a
        # stale BDE alongside a fresh manifest.
        self.bde_name = QLineEdit(self._default_bde_name())
        # Auto-refresh the filename whenever either seed changes (only
        # while the user hasn't manually edited the field).
        self._bde_name_user_edited = False
        self.bde_name.textEdited.connect(self._on_bde_name_edited)
        self.deal_seed.valueChanged.connect(self._refresh_bde_name)
        self.system_seed.valueChanged.connect(self._refresh_bde_name)
        cf.addRow("# deals", self.deal_count)
        cf.addRow("Deal seed", self.deal_seed)
        cf.addRow("System pair seed", self.system_seed)
        cf.addRow("BDE filename", self.bde_name)
        row = QHBoxLayout()
        self.btn_generate = QPushButton("Generate corpus")
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_write_bde = QPushButton("Write BDE to Q-Plus")
        self.btn_write_bde.clicked.connect(self._on_write_bde)
        self.btn_write_bde.setEnabled(False)
        row.addWidget(self.btn_generate)
        row.addWidget(self.btn_write_bde)
        cf.addRow(row)
        # Slam-eligible corpus: filter the random stream for deals
        # where some partnership has 30+ combined HCP (or 28+ with
        # 8+ card fit). Useful for testing biq's slam-bidding
        # architecture against Q-Plus's. Same workflow as the
        # regular Generate; the BDE is written via the existing
        # Write BDE button.
        row_slam = QHBoxLayout()
        self.btn_slam_corpus = QPushButton(
            "Generate slam-eligible corpus")
        self.btn_slam_corpus.clicked.connect(self._on_generate_slam)
        self.btn_slam_corpus.setToolTip(
            "Filter random deals for slam-rich combinations. "
            "Useful for testing slam-bidding code paths.")
        self.slam_hcp_threshold = QSpinBox()
        self.slam_hcp_threshold.setRange(24, 37)
        self.slam_hcp_threshold.setValue(30)
        self.slam_hcp_threshold.setPrefix("min combined HCP ")
        self.slam_hcp_threshold.setSuffix(" (one side)")
        row_slam.addWidget(self.btn_slam_corpus)
        row_slam.addWidget(self.slam_hcp_threshold)
        cf.addRow(row_slam)
        # Curated corpus from biq's teaching deck. Picks the top-N
        # most system-sensitive deals and expands each into 25
        # cells (one per NS/EW system-pair combination). Within
        # each set of 25 cells, the NS hands are IDENTICAL but
        # EW spot cards are perturbed so Q-Plus sees each as a
        # distinct deal (no Repeat-deal needed). Useful for
        # studying system-pair effects on the same effective deal.
        row2 = QHBoxLayout()
        self.btn_load_curated = QPushButton(
            "Load curated 4×25 corpus (system-sensitive deals)")
        self.btn_load_curated.clicked.connect(self._on_load_curated)
        self.curated_n_deals = QSpinBox()
        self.curated_n_deals.setRange(1, 16)
        self.curated_n_deals.setValue(4)
        self.curated_n_deals.setPrefix("take ")
        self.curated_n_deals.setSuffix(" deals (×25 cells)")
        # Deck offset — skip the first N deals (so consecutive curated
        # runs can use DIFFERENT base deals from the same teaching deck).
        # Deals that can't generate 25 unique spot-perms are skipped
        # automatically; this offset just shifts the starting point.
        self.curated_skip = QSpinBox()
        self.curated_skip.setRange(0, 16)
        self.curated_skip.setValue(0)
        self.curated_skip.setPrefix("skip first ")
        self.curated_skip.setSuffix(" in deck")
        self.curated_skip.setToolTip(
            "Skip the first N deals of teaching_deck.json. Use this to "
            "get a different base-deal set than a prior run.")
        row2.addWidget(self.btn_load_curated)
        row2.addWidget(self.curated_n_deals)
        row2.addWidget(self.curated_skip)
        cf.addRow(row2)
        v.addWidget(form_box)

        self.manifest_table = QTableWidget(0, 5)
        self.manifest_table.setHorizontalHeaderLabels(
            ["Deal #", "Dealer", "Vul", "N/S system", "E/W system"])
        v.addWidget(self.manifest_table, stretch=1)
        return w

    def _build_calibration_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(
            "Hover the mouse over each target in Q-Plus, then click "
            "'Capture'. The app counts down 3 seconds before sampling "
            "the pointer position. Saved positions persist across runs."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        # Without column-stretch the description label (col 0) grabs
        # the entire row width and the position label + Capture
        # button slide off-screen to the right. setColumnStretch(0,1)
        # makes col 0 absorb the horizontal stretch within the scroll
        # area's width, while cols 1 + 2 keep their natural widths.
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        self._cal_labels: Dict[str, QLabel] = {}
        for r, (key, desc) in enumerate(ALL_KEYS):
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            grid.addWidget(desc_lbl, r, 0)
            lbl = QLabel("—")
            lbl.setFont(QFont("monospace"))
            lbl.setMinimumWidth(90)
            self._cal_labels[key] = lbl
            grid.addWidget(lbl, r, 1)
            btn = QPushButton("Capture")
            btn.clicked.connect(lambda _, k=key: self._capture(k))
            grid.addWidget(btn, r, 2)
        scroll.setWidget(inner)
        v.addWidget(scroll, stretch=1)
        row = QHBoxLayout()
        self.btn_save_calib = QPushButton("Save calibration to disk")
        self.btn_save_calib.clicked.connect(self._save_positions)
        self.btn_test_calib = QPushButton(
            "Test (cycle 5 mixed N/S≠E/W pairs + save screenshots)")
        self.btn_test_calib.clicked.connect(self._on_test)
        row.addWidget(self.btn_save_calib)
        row.addWidget(self.btn_test_calib)
        row.addStretch(1)
        v.addLayout(row)
        # Rollover smoke-test row — drives Q-Plus through the full
        # save+exit → relaunch → load batch-2 BDE → Play sequence
        # using the 11 calibrated ROLLOVER positions and the same
        # Lutris wine runner the launcher uses for qplus.sh. Goal:
        # prove the rollover works end-to-end before relying on it
        # for an unattended >64-deal run. Preconditions: Q-Plus is
        # currently running on batch 1 (so save+exit can fire); a
        # 2+ batch corpus has been written (so the BDE Q-Plus loads
        # after relaunch IS the b2 batch).
        rollover_row = QHBoxLayout()
        self.btn_test_rollover = QPushButton(
            "Test rollover (save+exit → relaunch under "
            f"{QPLUS_LUTRIS_RUNNER} → Own deals → 2nd BDE → "
            "Deals → first deal → OK → Play)")
        self.btn_test_rollover.setToolTip(
            "End-to-end smoke test of the auto-rollover sequence. "
            "Q-Plus must already be running with batch 1 loaded — "
            "this button drives File → Save match and exit, relaunches "
            "Q-Plus via the Lutris wine runner, dismisses the splash "
            "Ok, then selects the 2nd BDE row in the Own Deals dialog, "
            "clicks Deals → first deal → OK → Play. All 11 ROLLOVER "
            "positions must be calibrated.")
        self.btn_test_rollover.clicked.connect(self._on_test_rollover)
        rollover_row.addWidget(self.btn_test_rollover)
        rollover_row.addStretch(1)
        v.addLayout(rollover_row)
        return w

    def _on_test_rollover(self):
        """Drive the rollover sequence manually for verification —
        same code path as the deal-65 auto-rollover, just kicked
        off by the operator. Identifies the next batch's BDE from
        whatever corpus tab has a multi-batch corpus loaded, or
        prompts if none."""
        missing = [k for k in ROLLOVER_KEYS
                   if k not in self.positions]
        if missing:
            QMessageBox.warning(
                self, "Rollover positions incomplete",
                f"Need to calibrate {len(missing)} more rollover "
                "position(s) before this test will run:\n\n  "
                + "\n  ".join(missing))
            return
        # Identify the b2 BDE: walk the corpus tabs and pick the
        # first one whose batch_bde_paths has ≥2 entries.
        next_batch_bde: Optional[Path] = None
        for tab in (self.tab_random, self.tab_matrix,
                    self.tab_slam, self.tab_grand_slam):
            if len(tab.batch_bde_paths) >= 2:
                next_batch_bde = tab.batch_bde_paths[1]
                self._log(
                    f"[rollover-test] using batch-2 BDE from "
                    f"{tab.corpus_type} tab: {next_batch_bde.name}")
                break
        if next_batch_bde is None:
            resp = QMessageBox.question(
                self, "No batch-2 BDE",
                "No corpus tab has a multi-batch BDE loaded — the "
                "test can still drive the rollover sequence, but "
                "Q-Plus will load whatever it finds as the 2nd row "
                "in OWN-DEALS. Continue?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if resp != QMessageBox.StandardButton.Yes:
                return
        self._set_status(
            "ROLLOVER TEST — driving save+exit → relaunch → "
            "Own deals → 2nd BDE → Play", "#aa66cc")
        ok = self._auto_rollover(next_batch_bde)
        if ok:
            self._set_status(
                "Rollover test PASSED — Q-Plus is now sitting on "
                "the loaded batch's deal 1.", "#22aa55")
            self._log("[rollover-test] PASSED")
        else:
            self._set_status(
                "Rollover test FAILED — check the log for which "
                "step aborted.", "#cc3333")
            self._log("[rollover-test] FAILED")

    def _build_run_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        # Loaded-BDE banner: shows the filename written to Q-Plus's
        # OWN-DEALS so the operator can glance at this label and
        # compare it to Q-Plus's bottom-bar filename during a run
        # without touching the mouse. Updated by _on_write_bde and
        # _refresh_loaded_bde_label.
        self.loaded_bde_label = QLabel()
        self.loaded_bde_label.setFont(QFont("monospace"))
        self.loaded_bde_label.setStyleSheet(
            "font-size: 14px; padding: 8px; "
            "background: #223; color: white; "
            "border: 1px solid #557;")
        self.loaded_bde_label.setWordWrap(True)
        v.addWidget(self.loaded_bde_label)
        self._refresh_loaded_bde_label()
        form = QFormLayout()
        self.after_dialog_step_ms = QSpinBox()
        self.after_dialog_step_ms.setRange(10, 3000)
        self.after_dialog_step_ms.setValue(200)
        self.after_dialog_step_ms.setSuffix(" ms")
        self.after_dialog_close_ms = QSpinBox()
        self.after_dialog_close_ms.setRange(20, 5000)
        self.after_dialog_close_ms.setValue(300)
        self.after_dialog_close_ms.setSuffix(" ms")
        self.after_next_deal_s = QSpinBox()
        self.after_next_deal_s.setRange(1, 30)
        self.after_next_deal_s.setValue(2)
        self.after_next_deal_s.setSuffix(" s")
        self.after_start_bidding_s = QSpinBox()
        self.after_start_bidding_s.setRange(5, 120)
        self.after_start_bidding_s.setValue(25)
        self.after_start_bidding_s.setSuffix(" s")
        self.per_deal_s = QSpinBox()
        self.per_deal_s.setRange(10, 300)
        self.per_deal_s.setValue(90)
        self.per_deal_s.setSuffix(" s")
        self.extend_match_boards = QSpinBox()
        self.extend_match_boards.setRange(0, 999)
        self.extend_match_boards.setValue(64)
        self.extend_match_boards.setSuffix(" boards")
        self.extend_match_boards.setToolTip(
            "When Q-Plus's Match End dialog appears, auto-type this "
            "value into the '# boards' field and click Extend. "
            "Requires match_end_boards_field + match_end_extend_btn "
            "to be calibrated. 0 disables (dialog will hang).")
        self.start_at_deal = QSpinBox()
        self.start_at_deal.setRange(1, 1000)
        self.start_at_deal.setValue(1)
        self.screenshot_chk = QCheckBox(
            "Save per-deal verification screenshot of Q-Plus "
            "(after Next deal, before Start bidding — captures "
            "both status-bar systems and face-up deal layout) "
            f"to {SCREENSHOT_DIR}")
        self.screenshot_chk.setChecked(True)
        self.qplus_on_starting_deal_chk = QCheckBox(
            "Q-Plus already on starting deal (skip 'Next deal' "
            "for first deal only — true right after Own deals → "
            "Play, when the bottom-left button reads 'Start "
            "bidding'). Uncheck if resuming with Q-Plus on an "
            "earlier deal.")
        self.qplus_on_starting_deal_chk.setChecked(True)
        form.addRow("Per-dialog-click pause", self.after_dialog_step_ms)
        form.addRow("After dialog close",     self.after_dialog_close_ms)
        form.addRow("After Next deal",        self.after_next_deal_s)
        form.addRow("After Start bidding",    self.after_start_bidding_s)
        form.addRow("Cardplay budget",        self.per_deal_s)
        form.addRow("Auto-extend Match End by", self.extend_match_boards)
        form.addRow("Start from deal #",      self.start_at_deal)
        form.addRow(self.screenshot_chk)
        form.addRow(self.qplus_on_starting_deal_chk)
        v.addLayout(form)
        row = QHBoxLayout()
        self.btn_run = QPushButton("Run")
        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)
        v.addLayout(row)
        # (manual-mode "Set systems for Start-from-deal-# only" button
        # removed 2026-05-26 — wasn't used in practice; the verify-deal-1
        # workflow described in HELP_TEXT is enough.)
        # Post-run verification.
        verify_row = QHBoxLayout()
        self.btn_verify = QPushButton(
            "Verify BDL vs manifest (report only)")
        self.btn_verify.clicked.connect(
            lambda: self._on_verify(reconcile=False))
        self.btn_reconcile = QPushButton(
            "Reconcile manifest to BDL "
            "(fix system labels for mismatched deals)")
        self.btn_reconcile.clicked.connect(
            lambda: self._on_verify(reconcile=True))
        verify_row.addWidget(self.btn_verify)
        verify_row.addWidget(self.btn_reconcile)
        v.addLayout(verify_row)
        self.progress = QProgressBar()
        v.addWidget(self.progress)
        v.addStretch(1)
        return w

    def _build_help_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("monospace"))
        text.setPlainText(HELP_TEXT)
        v.addWidget(text)
        return w

    # ------------ Stale-BDE archive ----------------

    def _archive_stale_bdes(self):
        """Move every .BDE (and matching .manifest.json) out of
        Q-Plus's OWN-DEALS into ARCHIVE_DIR, except for Q-Plus
        shipped / unrelated files. Forces Q-Plus to load the
        freshly written BDE every session — no stale-corpus
        confusion."""
        own = qplus_own_deals_dir()
        if own is None or not own.is_dir():
            return
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        moved = 0
        for pattern in ("*.BDE", "*.bde", "*.manifest.json"):
            for src in sorted(own.glob(pattern)):
                if src.name in ARCHIVE_SKIP:
                    continue
                dst = ARCHIVE_DIR / f"{stamp}_{src.name}"
                try:
                    src.rename(dst)
                    moved += 1
                except OSError as ex:
                    self._log(f"[archive] couldn't move {src.name}: "
                              f"{ex!r}")
        if moved:
            self._log(f"[archive] moved {moved} stale file(s) from "
                      f"{own} → {ARCHIVE_DIR}")
        else:
            self._log(f"[archive] no stale BDEs to move (clean).")

    # ------------ BDE filename ----------------

    def _default_bde_name(self) -> str:
        """Filename = just the two seeds, so Q-Plus's bottom-bar
        truncation doesn't hide the seed info. Example: 51768_19267.BDE.
        The matching manifest is 51768_19267.manifest.json."""
        return f"{self.deal_seed.value()}_{self.system_seed.value()}.BDE"

    def _on_bde_name_edited(self, _text: str):
        # Once the user has typed in the filename field, stop
        # auto-overriding it from seed changes.
        self._bde_name_user_edited = True

    def _refresh_bde_name(self):
        if self._bde_name_user_edited:
            return
        # Block the textEdited signal we'd otherwise re-emit.
        self.bde_name.blockSignals(True)
        self.bde_name.setText(self._default_bde_name())
        self.bde_name.blockSignals(False)

    # ------------ Calibration ----------------

    def _cache_path(self) -> Path:
        return Path.home() / ".qplus_mixed_corpus.json"

    def _load_cached_positions(self):
        p = self._cache_path()
        if not p.is_file():
            return
        try:
            raw = json.loads(p.read_text())
            valid = {k for k, _ in ALL_KEYS}
            for k, v in raw.items():
                if k in valid:
                    self.positions[k] = tuple(v)
                    self._cal_labels[k].setText(f"({v[0]}, {v[1]})")
            self._log(f"[calibration] loaded {len(self.positions)} "
                      f"cached positions from {p}")
        except Exception as ex:
            self._log(f"[calibration] cache parse failed: {ex!r}")

    def _save_positions(self):
        p = self._cache_path()
        p.write_text(json.dumps(
            {k: list(v) for k, v in self.positions.items()}, indent=2))
        self._log(f"[calibration] saved to {p}")
        self._set_status(f"Calibration saved ({len(self.positions)}/"
                         f"{len(ALL_KEYS)} positions).", "#22aa55")

    def _capture(self, key: str):
        self._set_status(f"CAPTURE  hover over '{key}' — sampling in 3 s",
                         "#ddaa22")
        self._log(f"[capture] move pointer to '{key}' — sampling in 3 s…")
        QApplication.processEvents()
        for i in range(3, 0, -1):
            self._log(f"  …{i}")
            QApplication.processEvents()
            time.sleep(1.0)
        x, y = get_mouse()
        self.positions[key] = (x, y)
        self._cal_labels[key].setText(f"({x}, {y})")
        self._log(f"[capture] {key} = ({x}, {y})")
        miss = self._missing_keys()
        if miss:
            self._set_status(
                f"Captured {key} = ({x}, {y}). "
                f"{len(miss)}/{len(ALL_KEYS)} still to capture.",
                "#666")
        else:
            self._set_status(
                f"Captured {key} = ({x}, {y}). "
                "All 17 positions set — ready to Test or Run.",
                "#22aa55")

    # ------------ Corpus generation ----------------

    def _on_generate(self):
        n = self.deal_count.value()
        self.deals = gen_random_deals(n, self.deal_seed.value())
        self.system_pairs = gen_random_system_pairs(
            n, self.system_seed.value())
        # Reset curated-mode flags. A prior Load-curated click in the
        # same session would otherwise stick and the random run would
        # be played with Repeat-deal between cells (replaying each
        # physical deal 25 times instead of advancing through the BDE).
        self._is_curated_corpus = False
        self._cells_per_deal = 1
        self._populate_manifest_table()
        self.btn_write_bde.setEnabled(True)
        self.start_at_deal.setMaximum(n)
        self._log(f"[corpus] generated {n} deals (seed "
                  f"{self.deal_seed.value()}) + {n} system pairs "
                  f"(seed {self.system_seed.value()}).")
        self._set_status(
            f"Corpus ready: {n} deals + system pairs.", "#666")

    def _on_generate_slam(self):
        """Generate a slam-eligible corpus. Filters random deals from
        the seed stream for ones where some partnership has the
        configured minimum combined HCP (or 2 fewer with an 8+ card
        fit). Output goes through the same Write-BDE flow as the
        regular generator."""
        n = self.deal_count.value()
        threshold = self.slam_hcp_threshold.value()
        seed = self.deal_seed.value()
        try:
            self.deals = gen_slam_eligible_deals(n, seed, threshold)
        except RuntimeError as ex:
            QMessageBox.warning(self, "Not enough slam-eligible deals",
                                str(ex))
            return
        # Use random system pairs (same as Generate corpus).
        self.system_pairs = gen_random_system_pairs(
            n, self.system_seed.value())
        self._is_curated_corpus = False
        self._cells_per_deal = 1
        self._populate_manifest_table()
        self.btn_write_bde.setEnabled(True)
        self.start_at_deal.setMaximum(n)
        # Compute HCP distribution for the log.
        def hcp(h):
            pts = {0: 4, 1: 3, 2: 2, 3: 1}
            return sum(pts.get(c.rank.value, 0) for c in h.cards)
        ns_hcps = []
        ew_hcps = []
        for d in self.deals:
            ns_hcps.append(hcp(d.hands[Seat.NORTH])
                           + hcp(d.hands[Seat.SOUTH]))
            ew_hcps.append(hcp(d.hands[Seat.EAST])
                           + hcp(d.hands[Seat.WEST]))
        big_side_avg = sum(max(a, b) for a, b
                           in zip(ns_hcps, ew_hcps)) / max(n, 1)
        self._log(
            f"[slam corpus] {n} slam-eligible deals (seed {seed}, "
            f"HCP ≥ {threshold} on one side; avg big-side HCP = "
            f"{big_side_avg:.1f}). Random system pairs (seed "
            f"{self.system_seed.value()}).")
        self._set_status(
            f"Slam corpus ready: {n} deals, big-side avg "
            f"{big_side_avg:.1f} HCP.", "#226699")

    def _on_load_curated(self):
        """Load the top-N most system-sensitive deals from biq's
        teaching deck and expand each into 25 records (one per
        NS/EW system-pair combination).

        Produces a CURATED corpus where each physical deal is
        played 25 times by Q-Plus, each time with a different
        system assignment. After running, we can compare biq's
        vs Q-Plus's contracts cell-by-cell on the SAME cards —
        the cleanest possible measurement of system effects.

        The biq-only analysis seeds (11075, 7371, 38263) and
        cap (64 deals/seed) are baked in here — match what
        biq_system_analysis.py produced.
        """
        from pathlib import Path
        import json
        deck_path = Path(__file__).resolve().parent.parent / \
            "data" / "teaching_deck.json"
        if not deck_path.is_file():
            QMessageBox.critical(
                self, "No teaching deck",
                f"Run tools/biq_system_analysis.py first; expected "
                f"{deck_path} doesn't exist.")
            return
        deck = json.loads(deck_path.read_text())
        n_deals = self.curated_n_deals.value()
        skip = self.curated_skip.value()
        SEEDS = [11075, 7371, 38263]
        DEALS_PER_SEED = 64
        SYSTEMS = ["SAYC", "TwoOverOne", "StandardAcol",
                   "StandardFrench", "Precision90M"]
        all_pairs = [(ns, ew) for ns in SYSTEMS for ew in SYSTEMS]
        # Cache regenerated deals per seed (cheap).
        seed_deals: Dict[int, List] = {}

        # Density check: skip deals that can't generate 25 unique
        # spot-perms (Q-Plus would dedup them). Walk the deck starting
        # at the configured offset and keep accepting deals until we
        # have n_deals viable ones.
        def _check_density(agg_idx):
            seed = SEEDS[agg_idx // DEALS_PER_SEED]
            local_idx = agg_idx % DEALS_PER_SEED
            if seed not in seed_deals:
                seed_deals[seed] = gen_random_deals(
                    DEALS_PER_SEED, seed)
            source = seed_deals[seed][local_idx]
            fps = set()
            for cell_i in range(25):
                p = _spot_perm_bitpattern(source, cell_i)
                fp = tuple(sorted(
                    (s.value, c.suit.value, c.rank.value)
                    for s in (Seat.NORTH, Seat.EAST,
                              Seat.SOUTH, Seat.WEST)
                    for c in p.hands[s].cards))
                fps.add(fp)
            return len(fps), source

        picks = []
        skipped_for_density = []
        for d in deck[skip:]:
            n_unique, _ = _check_density(d["deal_index"])
            if n_unique >= 25:
                picks.append(d)
                if len(picks) >= n_deals:
                    break
            else:
                skipped_for_density.append(
                    (d["deal_index"], n_unique))
                self._log(
                    f"[curated] skipping deck idx {d['deal_index']} "
                    f"— only {n_unique}/25 unique spot-perms "
                    f"(would dedup in Q-Plus)")
        if len(picks) < n_deals:
            QMessageBox.warning(
                self, "Not enough viable deals",
                f"Found only {len(picks)} deals with full 25-cell "
                f"density (need {n_deals}). Skipped density: "
                f"{skipped_for_density[:5]}")
            if not picks:
                return

        new_deals = []
        new_pairs = []
        for pick in picks:
            agg_idx = pick["deal_index"]
            seed = SEEDS[agg_idx // DEALS_PER_SEED]
            local_idx = agg_idx % DEALS_PER_SEED
            if seed not in seed_deals:
                seed_deals[seed] = gen_random_deals(
                    DEALS_PER_SEED, seed)
            source_board = seed_deals[seed][local_idx]
            # Emit 25 entries with cycling system pairs, all with
            # IDENTICAL cards (the source deal). The harness uses
            # Q-Plus's Deal → Repeat-deal feature between cells of
            # the same physical deal so Q-Plus's per-match dedup-
            # by-cards doesn't collapse them. Configured via
            # is_curated=True on the run config.
            from dataclasses import replace
            for cell_i, (ns, ew) in enumerate(all_pairs):
                # Perturb EW spot cards so Q-Plus sees each cell as
                # a distinct deal (defeats per-match dedup-by-cards).
                # NS hands are UNCHANGED across all 25 cells of a
                # given base deal → biq's NS auction depends only
                # on the NS system; the cell variance comes from
                # the (NS,EW) system pair, not the cards.
                perturbed = _perturb_ew_spot_cards(
                    source_board, cell_i, seed=agg_idx)
                renumbered = replace(
                    perturbed,
                    board_number=len(new_deals) + 1,
                )
                new_deals.append(renumbered)
                new_pairs.append((ns, ew))

        self.deals = new_deals
        self.system_pairs = new_pairs
        # NOT curated-Repeat-deal: spot-perm gives Q-Plus distinct
        # cards per cell, so the harness runs these as ordinary
        # different deals (no Deal → Repeat-deal needed).
        self._is_curated_corpus = False
        self._cells_per_deal = 1
        # Update UI fields.
        self.deal_count.setValue(len(new_deals))
        self.start_at_deal.setMaximum(len(new_deals))
        self._populate_manifest_table()
        self.btn_write_bde.setEnabled(True)
        self._log(
            f"[curated] loaded top-{n_deals} deals from teaching "
            f"deck × 25 system pairs each → {len(new_deals)} "
            f"deals total (EW spot-perturbed for Q-Plus uniqueness; "
            f"NS hands unchanged within each base deal's 25 cells).")
        self._log(
            f"[curated] picked deals: "
            f"{[p['deal_index'] + 1 for p in picks]} "
            f"(1-indexed from biq aggregate)")
        # Compute number of batches (Q-Plus 64-deal cap).
        n_batches = (len(new_deals) + 63) // 64
        self._set_status(
            f"Curated corpus ready: {len(new_deals)} entries in "
            f"{n_batches} batch{'es' if n_batches > 1 else ''}. "
            f"Save BDE → Run.", "#22aa55")

    def _populate_manifest_table(self):
        self.manifest_table.setRowCount(len(self.deals))
        for i, (board, (ns, ew)) in enumerate(
                zip(self.deals, self.system_pairs)):
            self.manifest_table.setItem(
                i, 0, QTableWidgetItem(str(board.board_number)))
            self.manifest_table.setItem(
                i, 1, QTableWidgetItem(board.dealer.to_char()))
            self.manifest_table.setItem(
                i, 2, QTableWidgetItem(str(board.vulnerability.name)))
            self.manifest_table.setItem(i, 3, QTableWidgetItem(ns))
            self.manifest_table.setItem(i, 4, QTableWidgetItem(ew))
        self.manifest_table.resizeColumnsToContents()

    def _on_write_bde(self):
        if not self.deals:
            QMessageBox.warning(self, "No corpus",
                                "Generate a corpus first.")
            return
        own_dir = qplus_own_deals_dir()
        if own_dir is None or not own_dir.is_dir():
            QMessageBox.critical(self, "Q-Plus not found",
                                 "Couldn't locate Q-Plus DATA/OWN-DEALS/.")
            return
        bde = own_dir / self.bde_name.text().strip()
        # Q-Plus's per-match cap means a >64-deal corpus must be
        # split into multiple BDE files: one per batch, each
        # containing at most `deals_per_match` deals. The user
        # loads batch1.BDE for the first match, then batch2.BDE
        # after the save+exit pause, etc.
        # ─── important: when split, each batch keeps its DEAL
        # NUMBERING (BB-mixed-001-064, BB-mixed-065-128, …) so
        # the merged file has unique labels matching the manifest.
        per_batch = 64
        if len(self.deals) > per_batch:
            # Multi-batch: write batchN.BDE files. Batch tag goes at
            # the FRONT so it stays visible in Q-Plus's truncated status
            # bar; system_seed is dropped from the filename (it's still
            # in the .manifest.json). Examples for deal_seed=32620:
            #   b1_32620.BDE   b2_32620.BDE
            ds = self.deal_seed.value()
            batches: List[Path] = []
            for batch_idx in range(0, len(self.deals), per_batch):
                batch_num = (batch_idx // per_batch) + 1
                batch_deals = self.deals[batch_idx:batch_idx + per_batch]
                batch_bde = bde.with_name(
                    f"b{batch_num}_{ds}.BDE")
                # Each deal keeps its absolute board number in
                # the label. write_multi_deal_bde labels 1..N
                # starting at 1, so we patch the label_prefix
                # to encode the batch's deal-number offset.
                write_multi_deal_bde(
                    batch_deals, batch_bde,
                    description=(f"bridgeIQ mixed-system corpus "
                                 f"batch {batch_num}"),
                    label_prefix="BB-mixed")
                # Re-label each Deal: BB-mixed-001..064 → original
                # global numbering. Rewrite file post-hoc.
                txt = batch_bde.read_text(encoding="latin-1")
                import re
                def _shift(match):
                    local_n = int(match.group(1))
                    return f"BB-mixed-{batch_idx + local_n:03d}"
                txt = re.sub(r"BB-mixed-(\d+)", _shift, txt)
                batch_bde.write_text(txt, encoding="latin-1")
                batches.append(batch_bde)
                self._log(f"[bde] wrote {batch_bde}")
            self.bde_path = batches[0]  # first batch is "the" BDE
            self._batch_bde_paths = batches
        else:
            write_multi_deal_bde(
                self.deals, bde,
                description="bridgeIQ mixed-system corpus",
                label_prefix="BB-mixed")
            self.bde_path = bde
            self._batch_bde_paths = [bde]
            self._log(f"[bde] wrote {bde}")
        manifest = bde.with_suffix(".manifest.json")
        manifest.write_text(json.dumps({
            "deal_seed": self.deal_seed.value(),
            "system_seed": self.system_seed.value(),
            "bde_file": bde.name,
            "batch_bde_files": [str(p.name) for p in self._batch_bde_paths],
            "deals": [
                {"deal": b.board_number,
                 "dealer": b.dealer.to_char(),
                 "vul": b.vulnerability.name,
                 "ns_system": ns,
                 "ew_system": ew}
                for b, (ns, ew) in zip(self.deals, self.system_pairs)],
        }, indent=2))
        self.manifest_path = manifest
        self._log(f"[bde] wrote {manifest}")
        self._refresh_loaded_bde_label()
        if len(self._batch_bde_paths) > 1:
            files_str = ", ".join(p.name for p in self._batch_bde_paths)
            self._set_status(
                f"BDE split into {len(self._batch_bde_paths)} batches: "
                f"{files_str}. Load batch1 in Q-Plus to start.",
                "#22aa55")
        else:
            self._set_status(
                f"BDE written: {bde.name}. In Q-Plus: Own deals → Open "
                "→ this file → Close.", "#22aa55")

    def _refresh_loaded_bde_label(self):
        """Update the Run-tab BDE banner to match the most recently
        written BDE. Operator reads this during an automated run to
        confirm Q-Plus's bottom-bar filename matches without having
        to touch the mouse."""
        if self.bde_path is None:
            self.loaded_bde_label.setText(
                "No BDE written yet. Go to the Corpus tab, generate, "
                "and click 'Write BDE to Q-Plus' first.")
            return
        n = len(self.system_pairs) if self.system_pairs else "?"
        target = max(200, int(n) if isinstance(n, int) else 200)
        boards = qplus_match_boards_own_deals()
        n_int = int(n) if isinstance(n, int) else None
        if boards is None:
            mc_line = (
                f"⚠ Couldn't read Q-Plus's '# boards' setting "
                f"(CONFIG/B-MATCH.CFB missing or unparseable). "
                f"Manually set Deal → Match control → '# boards' ≥ "
                f"{target} before Run.")
        elif n_int is not None and boards < n_int:
            mc_line = (
                f"⚠ Q-Plus '# boards' = {boards}, BELOW corpus size "
                f"{n_int}. Q-Plus will pop Match End every {boards} "
                f"boards. Set Deal → Match control → '# boards' ≥ "
                f"{target}, then save+exit Q-Plus so the value "
                f"persists, then reopen.\n"
                f"  (Banner reflects Q-Plus's last-exit value — if "
                f"Q-Plus is running, what you see in Match control "
                f"is authoritative.)")
        else:
            mc_line = (
                f"✓ Q-Plus '# boards' = {boards} (≥ corpus size). "
                f"Note: this reflects Q-Plus's last-exit value — "
                f"verify Match control still shows ≥ {target} if "
                f"Q-Plus has been restarted since.")
        self.loaded_bde_label.setText(
            f"Q-Plus should be displaying BDE: {self.bde_path.name}\n"
            f"  full path: {self.bde_path}\n"
            f"  {n} deals  ·  deal seed {self.deal_seed.value()}  ·  "
            f"system seed {self.system_seed.value()}\n"
            f"{mc_line}")

    # ------------ Run helpers ----------------

    def _missing_keys(self) -> List[str]:
        return [k for k in REQUIRED_KEYS if k not in self.positions]

    def _make_cfg(self) -> Optional[RunConfig]:
        miss = self._missing_keys()
        if miss:
            QMessageBox.warning(
                self, "Calibration incomplete",
                "Still need to capture: " + ", ".join(miss[:5])
                + (" …" if len(miss) > 5 else ""))
            return None
        # Curated runs also need Repeat-deal positions.
        is_curated = getattr(self, "_is_curated_corpus", False)
        if is_curated:
            repeat_keys = ("deal_menu", "repeat_deal_item",
                           "repeat_complete_radio",
                           "repeat_computer_radio", "repeat_ok_btn")
            miss_r = [k for k in repeat_keys
                      if k not in self.positions]
            if miss_r:
                QMessageBox.warning(
                    self, "Curated calibration incomplete",
                    "Curated runs need Repeat-deal positions. "
                    "Still missing: " + ", ".join(miss_r))
                return None
        wid = find_qplus_window()
        if wid is None:
            self._log("[run] WARNING: Q-Plus window not auto-found.")
        pbn_blobs = ([pbn_format_board(b) for b in self.deals]
                     if self.deals else None)
        return RunConfig(
            positions=dict(self.positions),
            system_pairs=list(self.system_pairs) if self.system_pairs
                          else [("SAYC", "SAYC")],  # for Test only
            window_id=wid,
            after_dialog_step_ms=self.after_dialog_step_ms.value(),
            after_dialog_close_ms=self.after_dialog_close_ms.value(),
            after_next_deal_s=float(self.after_next_deal_s.value()),
            after_start_bidding_s=float(self.after_start_bidding_s.value()),
            per_deal_s=float(self.per_deal_s.value()),
            starting_deal_index=self.start_at_deal.value() - 1,
            qplus_on_starting_deal=
                self.qplus_on_starting_deal_chk.isChecked(),
            screenshot_per_deal=self.screenshot_chk.isChecked(),
            pbn_blobs=pbn_blobs,
            is_curated=is_curated,
            cells_per_deal=getattr(self, "_cells_per_deal", 25),
            extend_match_boards=int(self.extend_match_boards.value()),
        )

    # --- Test (cycle all 5) ---

    def _on_set_only(self):
        """Set systems for the chosen deal but don't drive Next deal /
        bidding / autoplay. User plays that deal manually in Q-Plus to
        verify BDE + systems are wired correctly before a full run."""
        if not self.system_pairs:
            QMessageBox.warning(self, "No corpus",
                                "Generate a corpus first.")
            return
        cfg = self._make_cfg()
        if cfg is None:
            return
        idx = self.start_at_deal.value() - 1
        if idx < 0 or idx >= len(self.system_pairs):
            QMessageBox.warning(self, "Bad deal #",
                                f"Pick a deal between 1 and "
                                f"{len(self.system_pairs)}.")
            return
        ns, ew = self.system_pairs[idx]
        self.btn_set_only.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_test_calib.setEnabled(False)
        self._set_status(
            f"SET-ONLY RUNNING  deal {idx+1}: N/S={ns}  E/W={ew} — "
            "do not move the mouse", "#ddaa22")
        self.worker_thread = QThread()
        self.worker = RunWorker(cfg)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(
            lambda: self.worker.run_set_only(idx, ns, ew))
        self.worker.log.connect(self._log)
        self.worker.status.connect(self._set_status)
        self.worker.finished.connect(self._on_set_only_finished)
        self.worker_thread.start()

    def _on_set_only_finished(self, ok: bool):
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self.worker = None
        self.btn_set_only.setEnabled(True)
        self.btn_run.setEnabled(True)
        self.btn_test_calib.setEnabled(True)
        idx = self.start_at_deal.value() - 1
        if 0 <= idx < len(self.system_pairs):
            ns, ew = self.system_pairs[idx]
            QMessageBox.information(
                self, "Manual deal ready",
                f"Q-Plus is set for manifest deal {idx+1} of "
                f"{len(self.system_pairs)}.\n\n"
                f"   N/S: {SYSTEM_TAG[ns]} ({ns})\n"
                f"   E/W: {SYSTEM_TAG[ew]} ({ew})\n\n"
                "In Q-Plus, click Next deal (or First deal) then "
                "Start bidding then Autoplay — watch a complete deal "
                "play out. Verify the cards in Q-Plus match the "
                "manifest deal (check dealer & vul), and that the "
                "status bar shows the expected system tags.\n\n"
                "If everything looks right, set 'Start from deal #' "
                f"to {idx+2} and click Run for the rest.")

    def _on_verify(self, *, reconcile: bool):
        """Read the most recent BDL + manifest and either report
        mismatches (reconcile=False) or rewrite the manifest's
        system labels to match what Q-Plus actually played
        (reconcile=True). Since deals are randomly generated,
        reconciling is safe: it just relabels which system played
        each deal."""
        log_dir = qplus_log_dir()
        own_dir = qplus_own_deals_dir()
        matches_dir = qplus_local_matches_dir()
        # Prefer the savescore.qss in LOCAL-MATCHES — that's where
        # per-deal `.Bidding cnv` markers actually survive after
        # save+exit. The standalone .BDE in OWN-DEALS gets stripped
        # of those markers on save, so verifying against it would
        # silently report 0 matches even when systems were set
        # correctly. Fall back to LOG/*.bdl for older workflows.
        default_bdl = ""
        if matches_dir and matches_dir.is_dir():
            qsses = sorted(matches_dir.glob("savescore.qss"),
                           key=lambda p: p.stat().st_mtime,
                           reverse=True)
            if qsses:
                default_bdl = str(qsses[0])
        if not default_bdl and log_dir and log_dir.is_dir():
            bdls = sorted(log_dir.glob("*.bdl"),
                          key=lambda p: p.stat().st_mtime,
                          reverse=True)
            if bdls:
                default_bdl = str(bdls[0])
        bdl_path, _ = QFileDialog.getOpenFileName(
            self, "BDL or savescore.qss from Q-Plus", default_bdl,
            "Q-Plus savescore (*.qss);;BDL (*.bdl *.BDL);;All files (*)")
        if not bdl_path:
            return
        default_manifest = ""
        if own_dir and own_dir.is_dir():
            manifests = sorted(own_dir.glob("*.manifest.json"),
                               key=lambda p: p.stat().st_mtime,
                               reverse=True)
            if manifests:
                default_manifest = str(manifests[0])
        # If the corpus is loaded in this app session, the most
        # natural manifest is the one we just wrote.
        if self.manifest_path is not None:
            default_manifest = str(self.manifest_path)
        manifest_path, _ = QFileDialog.getOpenFileName(
            self, "Manifest JSON", default_manifest,
            "JSON (*.json);;All files (*)")
        if not manifest_path:
            return
        bdl_p = Path(bdl_path)
        man_p = Path(manifest_path)
        self._log(f"\n[verify] BDL:      {bdl_p}")
        self._log(f"[verify] manifest: {man_p}")
        try:
            issues, stats = verify_bdl_against_manifest(bdl_p, man_p)
        except Exception as ex:
            QMessageBox.critical(self, "Verify failed", repr(ex))
            self._log(f"[verify] ERROR: {ex!r}")
            return
        # Report.
        self._log(f"[verify] {stats['matched']}/"
                  f"{stats['deals_in_manifest']} deals match the "
                  "manifest exactly.")
        self._log(
            f"  mismatches — dealer: {stats['mismatch_dealer']}, "
            f"vul: {stats['mismatch_vul']}, "
            f"N/S sys: {stats['mismatch_ns']}, "
            f"E/W sys: {stats['mismatch_ew']}, "
            f"cards: {stats['mismatch_cards']}, "
            f"missing-from-BDL: {stats['missing_in_bdl']}")
        if issues:
            self._log("[verify] details:")
            for line in issues:
                self._log(f"  {line}")
        # Optional reconcile.
        if reconcile:
            try:
                fixed, warnings = reconcile_manifest_to_bdl(bdl_p, man_p)
            except Exception as ex:
                QMessageBox.critical(self, "Reconcile failed", repr(ex))
                self._log(f"[reconcile] ERROR: {ex!r}")
                return
            self._log(f"[reconcile] rewrote {fixed} system "
                      f"field(s); backup saved alongside manifest.")
            for w in warnings:
                self._log(f"  warn: {w}")
            if fixed:
                self._set_status(
                    f"Reconciled {fixed} system field(s) in manifest. "
                    "Re-run Verify to confirm clean.", "#22aa55")
                # If the user has the matching corpus loaded in
                # memory, refresh self.system_pairs from disk.
                if (self.manifest_path is not None
                        and self.manifest_path.resolve() == man_p.resolve()):
                    import json
                    new = json.loads(man_p.read_text())
                    self.system_pairs = [
                        (d["ns_system"], d["ew_system"])
                        for d in new["deals"]]
                    self._populate_manifest_table()
                    self._log("[reconcile] reloaded system_pairs "
                              "from updated manifest.")
            else:
                self._set_status(
                    "No fixable mismatches — manifest unchanged.",
                    "#666")
        else:
            colour = "#22aa55" if not issues else "#cc6633"
            self._set_status(
                f"Verify: {stats['matched']}/"
                f"{stats['deals_in_manifest']} deals match. "
                f"{len(issues)} issue(s).", colour)

    def _on_test(self):
        cfg = self._make_cfg()
        if cfg is None:
            return
        self._set_status(
            "TEST RUNNING — do not move the mouse "
            "(5 cycles, mixed N/S≠E/W, ~15 s)", "#ddaa22")
        self.btn_test_calib.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.worker_thread = QThread()
        self.worker = RunWorker(cfg)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run_test_all_five)
        self.worker.log.connect(self._log)
        self.worker.status.connect(self._set_status)
        self.worker.finished.connect(self._on_test_finished)
        self.worker_thread.start()

    def _on_test_finished(self, ok: bool):
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self.worker = None
        self.btn_test_calib.setEnabled(True)
        self.btn_run.setEnabled(True)
        # Build the expected-vs-screenshot checklist for the post-test
        # dialog. Each cycle uses NS=system_i, EW=system_(i+1)%5; the
        # last cycle's pair stays active in Q-Plus.
        rows = []
        for i, ns in enumerate(SYSTEM_NAMES):
            ew = SYSTEM_NAMES[(i + 1) % len(SYSTEM_NAMES)]
            rows.append(
                f"  cycle {i+1}: N/S={SYSTEM_TAG[ns]:<10} "
                f"E/W={SYSTEM_TAG[ew]}")
        last_ns = SYSTEM_NAMES[-1]
        last_ew = SYSTEM_NAMES[0]
        QMessageBox.information(
            self, "Test complete",
            "Cycled through 5 mixed N/S≠E/W pairs.\n\n"
            "Q-Plus's status bar should NOW read:\n\n"
            f"   N/S: {SYSTEM_TAG[last_ns]} ; "
            f"E/W: {SYSTEM_TAG[last_ew]}\n\n"
            f"(That's the last cycle: {last_ns} / {last_ew}.)\n\n"
            f"Verify each cycle in {SCREENSHOT_DIR}:\n"
            + "\n".join(rows) +
            "\n\nOpen each PNG — the status bar at the bottom of "
            "Q-Plus must match the filename's ns-/ew- tags. If any "
            "cycle shows the wrong pair, that calibration position "
            "is off.")

    # --- Run (full corpus) ---

    def _on_run(self):
        if not self.system_pairs:
            QMessageBox.warning(self, "No corpus",
                                "Generate a corpus first.")
            return
        # Tweak 2: assume Q-Plus is NOT running at Run-click and start
        # it via the same Lutris wine runner the launcher uses
        # (qplus_launch_cmd → QPLUS_LUTRIS_RUNNER). Runs BEFORE the
        # calibration check (in _make_cfg) so that even if positions
        # aren't captured yet, Q-Plus is up for the operator to
        # calibrate against. When the window is already open, no-op.
        if find_qplus_window() is None:
            cmd = qplus_launch_cmd()
            if cmd is None:
                QMessageBox.critical(
                    self, "Couldn't launch Q-Plus",
                    "Could not build a Q-Plus launch command "
                    f"(expected Lutris runner '{QPLUS_LUTRIS_RUNNER}'). "
                    "Open Q-Plus manually and click Run again.")
                return
            self._log(f"[run] Q-Plus not running — launching: {cmd}")
            subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             start_new_session=True)
            self._log("[run] waiting up to 90s for Q-Plus window…")
            wid = self._wait_for_qplus_window(timeout_s=90)
            if wid is None:
                QMessageBox.critical(
                    self, "Q-Plus didn't appear",
                    "Launched Q-Plus but no window detected within "
                    "90s. Open Q-Plus manually and click Run again.")
                return
            # Dismiss splash / activation Ok if calibrated. Activation
            # takes ~5s to make the Ok clickable; skip silently if
            # the position isn't calibrated.
            if "rollover_splash_ok" in self.positions:
                time.sleep(5.0)
                self._log("[run] dismissing splash Ok…")
                self._click_position("rollover_splash_ok")
                time.sleep(2.0)
            self._log("[run] Q-Plus launched and ready.")
        # Auto-load the first BDE so the run kicks off with no human
        # interaction. Falls through silently if positions aren't
        # calibrated (the operator does it by hand as before).
        loaded = self._auto_load_first_bde()
        cfg = self._make_cfg()
        if cfg is None:
            return
        if loaded:
            # Auto-load left Q-Plus on deal 1 of the chosen BDE; the
            # worker's first iteration must NOT click 'Next deal'.
            cfg.qplus_on_starting_deal = True
        # Cache the seeds for batch-archive filenames.
        self._run_deal_seed = self.deal_seed.value()
        self._run_sys_seed = self.system_seed.value()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_test_calib.setEnabled(False)
        self.progress.setMaximum(len(cfg.system_pairs))
        self.progress.setValue(cfg.starting_deal_index)
        self._set_status(
            f"RUN STARTED — {len(cfg.system_pairs)} deals from #"
            f"{cfg.starting_deal_index + 1}", "#ddaa22")
        self._log(f"[run] starting at deal #{cfg.starting_deal_index+1} "
                  f"of {len(cfg.system_pairs)}.")
        self.worker_thread = QThread()
        self.worker = RunWorker(cfg)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.log.connect(self._log)
        self.worker.status.connect(self._set_status)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.batch_break.connect(self._on_batch_break)
        # Track archived .qss paths for the merge step at run end.
        self._batch_archives: List[Path] = []
        self.worker_thread.start()

    def _on_stop(self):
        if self.worker is not None:
            self.worker.stop()
            self._log("[run] stop requested — finishing current step.")
            self._set_status("STOPPING after current step…", "#cc6633")

    def _on_worker_progress(self, i: int, n: int, msg: str):
        self.progress.setValue(i)

    def _on_worker_finished(self, ok: bool):
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
        self.worker = None
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_test_calib.setEnabled(True)
        self._log(f"[run] finished ok={ok}.")
        # If batches were captured, prompt the user to do the FINAL
        # save+exit in Q-Plus BEFORE we archive the savescore.qss
        # for the last batch. Without this prompt the last batch's
        # archive would be stale — Q-Plus only writes savescore.qss
        # at save+exit time. The archive_now=True path also handles
        # single-batch runs (no batch-break occurred).
        if ok:
            ds = getattr(self, "_run_deal_seed", 0)
            ss = getattr(self, "_run_sys_seed", 0)
            from PyQt6.QtWidgets import QMessageBox
            msg = (
                "Run complete — now finish the LAST batch and merge.\n\n"
                "In Q-Plus, IN ORDER:\n"
                "  1. File → Save match and exit\n"
                "  2. Click OK below to archive the final batch and "
                "merge.\n\n"
                "(This dialog blocks the archive — if you click OK "
                "before saving in Q-Plus, the final batch's "
                "savescore.qss won't include this run's deals.)")
            QMessageBox.information(
                self, "Save in Q-Plus, then OK to merge", msg)
            final_batch_num = len(self._batch_archives) + 1
            final_archive = archive_savescore_qss(ds, ss, final_batch_num)
            if final_archive is not None:
                self._batch_archives.append(final_archive)
                self._log(f"[batch {final_batch_num} archived] "
                          f"{final_archive}")
            # Merge.
            if self._batch_archives:
                merge_dest = (ARCHIVE_DIR
                              / f"merged_{ds}_{ss}.qss")
                n = merge_qss_corpora(self._batch_archives, merge_dest)
                self._log(f"[merge] combined {len(self._batch_archives)} "
                          f"batches → {merge_dest} ({n} deal records)")
                self._set_status(
                    f"DONE — {n} deals merged into {merge_dest.name}. "
                    f"Use Verify against this merged file.", "#22aa55")

    def _on_batch_break(self, batch_num: int, last_deal: int,
                        next_deal: int):
        """Handle the worker's batch-break signal at the 64-deal
        Q-Plus match cap.

        Auto-rollover path (preferred): if all KEYS_ROLLOVER
        positions are calibrated and we have the next batch's
        BDE path, drive Q-Plus through save+exit → relaunch →
        Own deals → Open → Play unattended.

        Manual fallback: pop a QMessageBox the way the original
        flow did, so the operator can step Q-Plus through the
        sequence by hand if rollover keys aren't calibrated.
        """
        from PyQt6.QtWidgets import QMessageBox
        ds = getattr(self, "_run_deal_seed", 0)
        ss = getattr(self, "_run_sys_seed", 0)
        # Identify the next batch's BDE. Each batch has its own BDE
        # so Q-Plus actually plays the correct deals — batch_num is
        # 1-indexed; we want batch_num+1's BDE.
        next_batch_bde = None
        batches = getattr(self, "_batch_bde_paths", [])
        if batch_num < len(batches):
            next_batch_bde = batches[batch_num]
        # Q-Plus only writes savescore.qss AT save+exit time, so we
        # archive AFTER the save+exit has fired (handled inside
        # _auto_rollover and the manual fallback path below) — not
        # before. The earlier "archive before rollover" order copied
        # a STALE savescore.qss from a previous Q-Plus run, then
        # Q-Plus's batch-2 save+exit overwrote batch-1's freshly-
        # written deals → batch 1's data was lost. Reordered 2026-05-28
        # after a 100-deal run lost 64/100 deals to this bug.
        # Decide: auto vs manual.
        rollover_ready = (
            all(k in self.positions for k in ROLLOVER_KEYS)
            and next_batch_bde is not None)
        if rollover_ready:
            self._set_status(
                f"AUTO-ROLLOVER batch {batch_num}→{batch_num + 1}: "
                f"save+exit → relaunch → load "
                f"{next_batch_bde.name}", "#aa66cc")
            ok = self._auto_rollover(next_batch_bde,
                                     archive_seeds=(ds, ss),
                                     batch_num=batch_num)
            if ok:
                self._log(f"[rollover] complete — resuming with "
                          f"deal {next_deal}/{len(self.worker.cfg.system_pairs)}")
                self._set_status(
                    f"ROLLOVER OK — resuming at deal {next_deal}",
                    "#22aa55")
                if self.worker is not None:
                    self.worker.resume_after_batch()
                return
            self._log("[rollover] auto-rollover failed — falling "
                      "back to manual prompt")
        # Manual fallback.
        bde_line = (f"  3. Own deals → load BDE: {next_batch_bde.name}"
                    if next_batch_bde
                    else "  3. Own deals → load the next batch BDE")
        cal_note = ("" if rollover_ready
                    else "\n(Calibrate the 8 ROLLOVER positions on "
                         "the Calibration tab to enable auto-"
                         "rollover next time.)")
        msg = (
            f"Batch {batch_num} complete — {last_deal} deals played "
            f"in this Q-Plus match.\n\n"
            f"Q-Plus's match buffer caps at "
            f"{self.worker.cfg.deals_per_match} deals; the next batch "
            f"needs a FRESH match — AND a different BDE file "
            f"containing the next 64 deals.\n\n"
            f"Please do, in Q-Plus, IN ORDER:\n"
            f"  1. File → Save match and exit\n"
            f"  2. Reopen Q-Plus (relaunch the .exe)\n"
            f"{bde_line}\n"
            f"  4. Click OK below to continue with deal #{next_deal}"
            f"{cal_note}\n\n"
            f"(This dialog will block the run until you click OK.)")
        QMessageBox.information(self, "Batch complete — save and reopen",
                                msg)
        # Archive AFTER the user has done their manual save+exit (and
        # before the next match overwrites savescore.qss). Mirrors
        # the post-save-exit archive in _auto_rollover.
        archive = archive_savescore_qss(ds, ss, batch_num)
        if archive is not None:
            self._batch_archives.append(archive)
            self._log(f"[batch {batch_num} archived] {archive}")
        else:
            self._log(f"[batch {batch_num}] WARNING: could not "
                      f"archive savescore.qss (file missing?)")
        if self.worker is not None:
            self.worker.resume_after_batch()

    # --- auto-rollover sequence ---

    def _auto_rollover(self, next_batch_bde: Optional[Path] = None,
                       archive_seeds: Optional[Tuple[int, int]] = None,
                       batch_num: Optional[int] = None,
                       ) -> bool:
        """Drive Q-Plus through save+exit → relaunch (under the same
        Lutris wine runner the launcher uses) → splash Ok → Own
        deals → 2nd BDE row → Deals → first deal → OK → Play, all
        via the KEYS_ROLLOVER calibrated positions. Returns True on
        success, False on any failure (caller falls back to the
        manual QMessageBox prompt).

        next_batch_bde is informational only — used in log lines so
        the operator can correlate with the BDE Q-Plus should pick
        up. The click position itself is `rollover_bde_2nd_row`,
        which the operator calibrated to the second BDE row in
        Q-Plus's Manage-and-use-own-deals file list (the assumption
        is the previous batch's BDE is still sitting in the list as
        the first row).

        Click cadence: uses the active worker's `after_dialog_step_ms`
        / `after_dialog_close_ms` if a run is in progress, otherwise
        the test-button hardcoded fallback (300 ms / 600 ms).
        """
        import subprocess as sp
        cfg = self.worker.cfg if self.worker is not None else None
        step_s = ((cfg.after_dialog_step_ms / 1000.0)
                  if cfg else 0.3)
        close_s = ((cfg.after_dialog_close_ms / 1000.0)
                   if cfg else 0.6)
        bde_label = (next_batch_bde.name
                     if next_batch_bde is not None else "(unknown)")
        try:
            # ── Save match + exit ──
            # The Save-match-and-exit menu item closes Q-Plus directly;
            # no confirmation dialog appears, so there is no OK to
            # click after the menu item. (Earlier code had a
            # rollover_save_exit_ok click here; removed because the
            # dialog doesn't show up.)
            self._log("[rollover] File → Save match and exit…")
            self._click_position("rollover_file_menu")
            time.sleep(step_s)
            self._click_position("rollover_save_exit_item")
            time.sleep(close_s)
            self._log("[rollover] waiting up to 30s for Q-Plus to "
                      "exit…")
            if not self._wait_for_qplus_gone(timeout_s=30):
                self._log("[rollover] Q-Plus didn't exit — aborting")
                return False
            # ── Archive savescore.qss NOW (post-save, pre-relaunch) ──
            # Q-Plus just wrote savescore.qss during save+exit. The
            # next match will overwrite it, so this is the only safe
            # moment to capture this batch's data.
            if archive_seeds is not None and batch_num is not None:
                ds, ss = archive_seeds
                archive = archive_savescore_qss(ds, ss, batch_num)
                if archive is not None:
                    self._batch_archives.append(archive)
                    self._log(f"[batch {batch_num} archived] {archive}")
                else:
                    self._log(f"[batch {batch_num}] WARNING: could not "
                              f"archive savescore.qss (file missing?)")
            # ── Relaunch via Lutris wine runner ──
            cmd = qplus_launch_cmd()
            if cmd is None:
                self._log("[rollover] couldn't build Q-Plus launch "
                          "command — aborting")
                return False
            self._log(f"[rollover] launching Q-Plus: {cmd}")
            sp.Popen(cmd, shell=True,
                     stdout=sp.DEVNULL, stderr=sp.DEVNULL,
                     start_new_session=True)
            self._log("[rollover] waiting up to 90s for Q-Plus to "
                      "come back (splash screen)…")
            new_wid = self._wait_for_qplus_window(timeout_s=90)
            if new_wid is None:
                self._log("[rollover] Q-Plus didn't appear — aborting")
                return False
            # ── Dismiss splash / activation Ok ──
            # The splash screen appears almost immediately but the
            # Ok button isn't clickable until activation completes.
            # 5s is normally enough on this Wine runner; bump if
            # your machine is slower.
            time.sleep(5.0)
            self._log("[rollover] clicking splash Ok…")
            self._click_position("rollover_splash_ok")
            time.sleep(2.0)  # let the main window finish drawing
            # ── Point the worker at the new window ──
            new_wid = find_qplus_window() or new_wid
            if self.worker is not None:
                self.worker.cfg.window_id = new_wid
                self._log(f"[rollover] worker window_id → {new_wid}")
            # ── Own deals → Manage dialog ──
            self._log("[rollover] Own deals → Manage dialog…")
            self._click_position("rollover_own_deals_menu")
            time.sleep(step_s)
            self._click_position("rollover_own_deals_open_item")
            time.sleep(close_s)
            # ── Pick the 2nd BDE row (= next batch) ──
            self._log(f"[rollover] selecting 2nd BDE row "
                      f"(expecting {bde_label})…")
            self._click_position("rollover_bde_2nd_row")
            time.sleep(step_s)
            # ── Deals → first deal → OK ──
            self._log("[rollover] Deals → first deal → OK…")
            self._click_position("rollover_manage_deals_btn")
            time.sleep(close_s)
            self._click_position("rollover_deal_select_first")
            time.sleep(step_s)
            self._click_position("rollover_deal_select_ok")
            time.sleep(close_s)
            # ── Play ──
            self._log(f"[rollover] Play → {bde_label}")
            self._click_position("rollover_play_btn")
            time.sleep(close_s)
            # ── Let Q-Plus deal board 1 face up ──
            time.sleep(2.5)
            # Arm the next-iteration skip — Q-Plus is now sitting on
            # the new batch's deal 1, so the worker must NOT click
            # Next deal for the upcoming iteration (would skip past
            # the resume deal).
            if self.worker is not None:
                self.worker._post_rollover_skip = True
            return True
        except Exception as ex:
            self._log(f"[rollover] ERROR: {ex!r}")
            return False

    def _click_position(self, key: str):
        if key not in self.positions:
            raise KeyError(f"position '{key}' not calibrated")
        x, y = self.positions[key]
        click_at(x, y)

    def _auto_load_first_bde(self) -> bool:
        """Drive Q-Plus through Own deals → Open → first BDE row →
        Deals → first deal → OK → Play, fully automated. Called
        from _on_run after we've ensured Q-Plus is running.

        Returns True on success, False if any required position is
        missing (the operator can still hand-load and run again).
        """
        miss = [k for k in FIRST_LOAD_KEYS_FULL
                if k not in self.positions]
        if miss:
            self._log(f"[auto-load] skipping: missing positions "
                      f"{miss[:5]}{' …' if len(miss) > 5 else ''} "
                      f"(calibrate them to unlock fully-unattended Run)")
            return False
        step_s = (self.after_dialog_step_ms.value() / 1000.0
                  if hasattr(self, "after_dialog_step_ms")
                  else 0.3)
        close_s = (self.after_dialog_close_ms.value() / 1000.0
                   if hasattr(self, "after_dialog_close_ms")
                   else 0.6)
        try:
            self._log("[auto-load] Own deals → Open dialog…")
            self._click_position("rollover_own_deals_menu")
            time.sleep(step_s)
            self._click_position("rollover_own_deals_open_item")
            time.sleep(close_s)
            self._log("[auto-load] selecting first BDE row…")
            self._click_position("bde_1st_row")
            time.sleep(step_s)
            self._log("[auto-load] Deals → first deal → OK…")
            self._click_position("rollover_manage_deals_btn")
            time.sleep(close_s)
            self._click_position("rollover_deal_select_first")
            time.sleep(step_s)
            self._click_position("rollover_deal_select_ok")
            time.sleep(close_s)
            self._log("[auto-load] Play…")
            self._click_position("rollover_play_btn")
            time.sleep(close_s)
            # Q-Plus draws board 1 face-up after Play — give it a
            # moment to finish before the worker starts clicking.
            time.sleep(2.5)
            return True
        except Exception as ex:
            self._log(f"[auto-load] ERROR: {ex!r}")
            return False

    def _wait_for_qplus_gone(self, timeout_s: float) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if find_qplus_window() is None:
                return True
            time.sleep(0.5)
        return False

    def _wait_for_qplus_window(self, timeout_s: float
                               ) -> Optional[int]:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            wid = find_qplus_window()
            if wid is not None:
                return wid
            time.sleep(0.5)
        return None

    def _isolate_next_batch_bde(self, keep: Path):
        """Move every other .BDE in OWN-DEALS into ARCHIVE_DIR so
        Q-Plus's file-open dialog has `keep` as the first (and
        only) row. Skips ARCHIVE_SKIP files (EXAMPLE.BDE,
        BEN_BRIDGE_RELAY.BDE)."""
        own_dir = keep.parent
        if not own_dir.is_dir():
            return
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        moved = 0
        keep_resolved = keep.resolve()
        for pattern in ("*.BDE", "*.bde"):
            for src in own_dir.glob(pattern):
                if src.name in ARCHIVE_SKIP:
                    continue
                if src.resolve() == keep_resolved:
                    continue
                dst = (ARCHIVE_DIR
                       / f"rollover_{ts}_{src.name}")
                try:
                    src.rename(dst)
                    moved += 1
                except OSError as ex:
                    self._log(f"[rollover] couldn't move "
                              f"{src.name}: {ex!r}")
        if moved:
            self._log(f"[rollover] moved {moved} other BDE(s) "
                      f"aside; {keep.name} is now the only BDE "
                      f"in OWN-DEALS")

    # ------------ Logging / status ----------------

    def _log(self, msg: str):
        self.log.appendPlainText(msg)
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        # Stream to disk too (line-buffered, append-only).
        try:
            if self._log_file is None:
                self._log_file = open(self.log_path, "a",
                                      encoding="utf-8",
                                      buffering=1)
            self._log_file.write(msg + "\n")
        except Exception:
            # Don't let a disk hiccup break the UI; user has the
            # in-window log either way.
            pass

    def _set_status(self, text: str, color: str):
        self.status_banner.setText(text)
        self.status_banner.setStyleSheet(
            f"font-size: 16px; padding: 8px; "
            f"background: {color}; color: white;")


def main(argv=None) -> int:
    app = QApplication(argv or sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
