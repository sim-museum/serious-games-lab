#!/usr/bin/env python3
"""
Bridge Harness — PyQt5 GUI for Q-Plus Bridge hand entry and comparison workflow.

Features:
  - Enter hands from PBN files, PBN strings, base-72 Pavlicek codes, or random deals
  - Always displays base-72 hand code for the current deal
  - Automates hand entry into Q-Plus Bridge via mouse control
  - Workflow: play in another program (e.g. wbridge5) → enter same hand into qplus
    → collect qplus log → convert & copy to afterGameReport
"""

import json
import os
import re
import random
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from math import comb
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QRadioButton, QButtonGroup, QSpinBox, QMessageBox, QTabWidget,
    QFormLayout, QComboBox, QStatusBar, QSplitter, QCheckBox,
    QScrollArea, QAction,
)

import pyautogui

pyautogui.FAILSAFE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # FRI/guiHarness
FRI_DIR = SCRIPT_DIR.parent                           # FRI
REPO_ROOT = FRI_DIR.parent                            # sgl
CALIBRATION_FILE = SCRIPT_DIR / "calibration.json"

# biq repo + its Q-NET client, used by the Closed Room tab to put biq
# in the E/W seats of a live Q-Plus match. The repo nests one level
# (FRI/bridgeIQ/bridgeIQ); its venv sits one level up from that.
BIQ_ROOT = FRI_DIR / "bridgeIQ" / "bridgeIQ"
BIQ_VENV_PYTHON = FRI_DIR / "bridgeIQ" / "venv" / "bin" / "python"
BIQ_QNET_CLIENT = BIQ_ROOT / "tools" / "biq_qnet_client.py"
BIQ_QNET_LOG_DIR = BIQ_ROOT / "tools" / "runs"

# System wine 9 — REQUIRED to run Q-Plus's Q-NET server. Under the TkG 6.21
# Lutris runner (used elsewhere for card glyphs) the q-net module accepts the
# TCP connection but never reads it, so biq E/W can never attach. Override with
# the WINE9_BIN env var if your wine-9 lives elsewhere.
WINE9_BIN = os.environ.get("WINE9_BIN", "/usr/bin/wine")


def _wine9_status(wine_bin=WINE9_BIN):
    """Return (is_wine9, version_string). is_wine9 is True only when `wine_bin`
    exists and reports a wine 9.x (or newer) version."""
    if not (wine_bin and (os.path.isabs(wine_bin) and os.path.exists(wine_bin)
                          or shutil.which(wine_bin))):
        return (False, "")
    try:
        out = subprocess.run([wine_bin, "--version"], capture_output=True,
                             text=True, timeout=10)
        ver = (out.stdout or out.stderr or "").strip().splitlines()[0] if (
            out.stdout or out.stderr) else ""
    except (OSError, subprocess.SubprocessError):
        return (False, "")
    m = re.search(r'wine-(\d+)', ver)
    return (bool(m) and int(m.group(1)) >= 9, ver)

# ---------------------------------------------------------------------------
# Card constants
# ---------------------------------------------------------------------------
SUITS = ["S", "H", "D", "C"]
SUIT_SYMBOLS = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}

SUIT_TO_IDX = {"S": 0, "H": 1, "D": 2, "C": 3}
RANK_TO_IDX = {
    "A": 0, "K": 1, "Q": 2, "J": 3, "10": 4, "T": 4,
    "9": 5, "8": 6, "7": 7, "6": 8, "5": 9, "4": 10, "3": 11, "2": 12,
}
IDX_SUIT = "SHDC"
IDX_RANK = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]

HCP_VALUES = {"A": 4, "K": 3, "Q": 2, "J": 1}

# Card grid layout for the Q-Plus pickboard (same as bridge_input.py)
CARD_GRID_LAYOUT = [
    [f"{s}{r}" for r in RANKS] for s in SUITS
]
CARD_COORDS_MAP = {
    card: (row, col)
    for row, cards in enumerate(CARD_GRID_LAYOUT)
    for col, card in enumerate(cards)
}

PLAYER_NAMES = ["North", "East", "South", "West"]


# ---------------------------------------------------------------------------
# Q-Plus "Own Deals" BDE file format
#
# Multi-deal text files Q-Plus reads from DATA/OWN-DEALS/. Each deal is:
#
#     Deal         :   <label>
#     Dealer       :   <North|East|South|West>
#     Vuln         :   <---|N/S|E/W|All>
#     Cards        :                  <N spades>
#                  :                  <N hearts>
#                  :                  <N diamonds>
#                  :                  <N clubs>
#                  :   <W spades>                    <E spades>
#                  :   <W hearts>                    <E hearts>
#                  :   <W diamonds>                  <E diamonds>
#                  :   <W clubs>                     <E clubs>
#                  :                  <S spades>
#                  :                  <S hearts>
#                  :                  <S diamonds>
#                  :                  <S clubs>
#
#     *********************************************************
#
# Same general header style as a played-out BDL file but with the
# auction / play / result blocks omitted — Q-Plus generates those
# when it auto-plays the deal. Writing one of these is faster and
# vastly more reliable than the 52-card pyautogui chain that drove
# the pickboard dialog.
# ---------------------------------------------------------------------------

BDE_VULN_MAP = {
    "None": "---",  "NONE": "---",  "-": "---",  "":  "---",
    "NS":   "N/S",  "N-S": "N/S",   "N/S": "N/S",
    "EW":   "E/W",  "E-W": "E/W",   "E/W": "E/W",
    "Both": "All",  "BOTH": "All",  "All": "All",  "ALL": "All",
}

BDE_DEALER_MAP = {
    "N": "North", "E": "East", "S": "South", "W": "West",
}

BDE_SEPARATOR = "*********************************************************"


def _fmt_bde_suit(cards_with_rank: list) -> str:
    """Render a single suit-line for the BDE file.

    `cards_with_rank` is a list of rank tokens ("A", "K", "Q", …,
    "10", "2"). Sorted A→2 with single-space separators. An empty
    suit renders as "-". Q-Plus's shipped .BDE files use "T" for the
    ten (not "10"), so we convert here for byte-identical output.
    """
    if not cards_with_rank:
        return "-"
    return " ".join("T" if r == "10" else r for r in cards_with_rank)


def hands_to_bde_text(hands, dealer: str = "N", vuln: str = "None",
                      label: str = "Sent from bridgeIQ",
                      description: str = "single deal from bridgeIQ") -> str:
    """Build a single-deal BDE file body.

    `hands` is [N_cards, E_cards, S_cards, W_cards] where each card
    list is the same in-list-of-strings shape the harness uses
    elsewhere (e.g. "SA", "HT", "C2", …). Returns the full file
    content as a string.
    """
    suit_chars = ["S", "H", "D", "C"]
    rank_order = {"A": 0, "K": 1, "Q": 2, "J": 3, "10": 4, "9": 5,
                  "8": 6, "7": 7, "6": 8, "5": 9, "4": 10,
                  "3": 11, "2": 12}

    def _suits_for_hand(hand):
        groups = {s: [] for s in suit_chars}
        for card in hand:
            groups[card[0]].append(card[1:])
        for s in suit_chars:
            groups[s].sort(key=lambda r: rank_order.get(r, 99))
        return [groups[s] for s in suit_chars]   # [spades, hearts, ds, cs]

    n_suits = _suits_for_hand(hands[0])
    e_suits = _suits_for_hand(hands[1])
    s_suits = _suits_for_hand(hands[2])
    w_suits = _suits_for_hand(hands[3])

    dealer_full = BDE_DEALER_MAP.get(dealer.strip().upper()[:1], "North")
    vuln_full = BDE_VULN_MAP.get(vuln.strip(), "---")

    lines = []
    lines.append("DOCTYPE: BDL 7.1")
    lines.append(f'.description.eng = "{description}"')
    lines.append("")
    lines.append(f"Deal         :   {label}")
    lines.append(f"Dealer       :   {dealer_full}")
    lines.append(f"Vuln         :   {vuln_full}")

    # N row: 4 indented suit lines
    lines.append(f"Cards        :                  {_fmt_bde_suit(n_suits[0])}")
    for s in range(1, 4):
        lines.append(f"             :                  {_fmt_bde_suit(n_suits[s])}")
    # W ↔ E rows: 4 lines, two suits side by side
    for s in range(4):
        wcol = _fmt_bde_suit(w_suits[s])
        ecol = _fmt_bde_suit(e_suits[s])
        lines.append(f"             :   {wcol:<30}{ecol}")
    # S row: 4 indented
    for s in range(4):
        lines.append(f"             :                  {_fmt_bde_suit(s_suits[s])}")
    lines.append("")
    lines.append(BDE_SEPARATOR)
    return "\n".join(lines) + "\n"

# ---------------------------------------------------------------------------
# Pavlicek deal-number encoding  (standalone — no dependency on bridgeIQ)
#
# Base-72 is the canonical alphabet across the project (bridgeIQ BDL,
# this harness, and any other deal-ID consumer).  Alphabet:
#   0-9 A-Z a-z !@#$%^&*()
# ---------------------------------------------------------------------------
TOTAL_DEALS = comb(52, 13) * comb(39, 13) * comb(26, 13)

BASE72_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()"
BASE72_VAL = {c: i for i, c in enumerate(BASE72_CHARS)}


def int_to_base72(number: int) -> str:
    if number == 0:
        return "0"
    result = []
    while number > 0:
        result.append(BASE72_CHARS[number % 72])
        number //= 72
    return "".join(reversed(result))


def base72_to_int(s: str) -> int:
    result = 0
    for ch in s:
        if ch not in BASE72_VAL:
            raise ValueError(f"Invalid base-72 character: {ch!r}")
        result = result * 72 + BASE72_VAL[ch]
    return result


def card_str_to_index(card: str) -> int:
    """'SA' → 0, 'HK' → 14, 'C2' → 51, etc."""
    suit = card[0]
    rank = card[1:]
    return SUIT_TO_IDX[suit] * 13 + RANK_TO_IDX[rank]


def index_to_card_str(idx: int) -> str:
    return IDX_SUIT[idx // 13] + IDX_RANK[idx % 13]


def _encode_hand(card_indices, available):
    positions = sorted(available.index(c) for c in sorted(card_indices))
    total = 0
    for i, pos in enumerate(positions):
        total += comb(pos, i + 1)
    return total


def _decode_hand(index, available, num_cards=13):
    n = len(available)
    positions = []
    remaining = index
    for k in range(num_cards, 0, -1):
        for p in range(n - 1, k - 2, -1):
            c = comb(p, k)
            if c <= remaining:
                positions.append(p)
                remaining -= c
                break
    positions.reverse()
    return [available[p] for p in positions]


def deal_to_number(hands):
    """hands = [north_cards, east_cards, south_cards, west_cards] as card-string lists."""
    n_idx = sorted(card_str_to_index(c) for c in hands[0])
    e_idx = sorted(card_str_to_index(c) for c in hands[1])
    s_idx = sorted(card_str_to_index(c) for c in hands[2])

    avail = list(range(52))
    n_enc = _encode_hand(n_idx, avail)
    for c in n_idx:
        avail.remove(c)
    e_enc = _encode_hand(e_idx, avail)
    for c in e_idx:
        avail.remove(c)
    s_enc = _encode_hand(s_idx, avail)

    return n_enc * comb(39, 13) * comb(26, 13) + e_enc * comb(26, 13) + s_enc


def number_to_deal(deal_number):
    """Return [north, east, south, west] as lists of card strings."""
    if deal_number < 0 or deal_number >= TOTAL_DEALS:
        raise ValueError(
            f"Deal number {deal_number} is outside the Pavlicek range "
            f"[0, {TOTAL_DEALS})."
        )
    c26 = comb(26, 13)
    c39 = comb(39, 13)
    s_enc = deal_number % c26
    rem = deal_number // c26
    e_enc = rem % c39
    n_enc = rem // c39

    avail = list(range(52))
    n_idx = _decode_hand(n_enc, avail)
    for c in n_idx:
        avail.remove(c)
    e_idx = _decode_hand(e_enc, avail)
    for c in e_idx:
        avail.remove(c)
    s_idx = _decode_hand(s_enc, avail)
    for c in s_idx:
        avail.remove(c)
    w_idx = avail

    return [
        [index_to_card_str(i) for i in n_idx],
        [index_to_card_str(i) for i in e_idx],
        [index_to_card_str(i) for i in s_idx],
        [index_to_card_str(i) for i in w_idx],
    ]


def deal_to_base72(hands) -> str:
    return int_to_base72(deal_to_number(hands))


def base72_to_deal(code: str):
    return number_to_deal(base72_to_int(code))


# ---------------------------------------------------------------------------
# Hand analysis helpers
# ---------------------------------------------------------------------------

def hand_hcp(cards):
    return sum(HCP_VALUES.get(c[1:], 0) for c in cards)


def hand_shape(cards):
    counts = defaultdict(int)
    for c in cards:
        counts[c[0]] += 1
    return tuple(counts[s] for s in SUITS)


def hand_shape_str(cards):
    return "-".join(str(x) for x in hand_shape(cards))


# ---------------------------------------------------------------------------
# PBN parsing / writing
# ---------------------------------------------------------------------------

def parse_pbn_hand(hand_str: str):
    """Parse 'AKQ7.95..J82' → ['SA', 'SK', 'SQ', 'S7', 'H9', 'H5', 'CJ', 'C8', 'C2']."""
    suits = hand_str.split(".")
    if len(suits) != 4:
        raise ValueError(f"Hand must have 4 dot-separated suits, got: {hand_str!r}")
    cards = []
    for i, suit_cards in enumerate(suits):
        if not suit_cards or suit_cards == "-":
            continue
        for rank in re.findall(r"10|T|[AKQJ98765432]", suit_cards):
            if rank == "T":
                rank = "10"
            cards.append(SUITS[i] + rank)
    if len(cards) != 13:
        raise ValueError(f"Hand {hand_str!r} has {len(cards)} cards, expected 13")
    return cards


def parse_pbn_deal_string(spec: str):
    """Parse 'N:AKQ7.95..J82 T543.QJ7.AQ4.KT9 ...' → [N, E, S, W] card lists."""
    spec = spec.strip()
    if ":" not in spec:
        raise ValueError("Deal string must start with '<dealer>:' (e.g. 'N:')")
    dealer, rest = spec.split(":", 1)
    dealer = dealer.strip().upper()
    parts = rest.split()
    if len(parts) != 4:
        raise ValueError(f"Expected 4 hands, got {len(parts)}")
    raw_hands = [parse_pbn_hand(p) for p in parts]
    # Rotate so output is always N, E, S, W
    seat_order = {"N": 0, "E": 1, "S": 2, "W": 3}
    offset = seat_order.get(dealer, 0)
    hands = [None] * 4
    for i in range(4):
        hands[(offset + i) % 4] = raw_hands[i]
    return hands


def hands_to_pbn_deal(hands):
    """Convert [N, E, S, W] card lists → PBN deal string 'N:...'."""
    parts = []
    for hand in hands:
        suit_groups = {s: [] for s in SUITS}
        for card in hand:
            suit_groups[card[0]].append(card[1:])
        suit_strs = []
        for s in SUITS:
            ranks = sorted(suit_groups[s], key=lambda r: RANK_ORDER.get(r, 99))
            # Use T for 10 in PBN
            suit_strs.append("".join("T" if r == "10" else r for r in ranks))
        parts.append(".".join(suit_strs))
    return "N:" + " ".join(parts)


def parse_pbn_file(path: str):
    """Parse a .pbn file, returning a list of board dicts.

    Each dict has keys like 'Deal', 'Dealer', 'Vulnerable', 'Contract',
    'Declarer', 'Result', 'Event', 'Board', etc.
    Auction and Play data lines are stored under 'Auction_data' and 'Play_data'.
    """
    boards = []
    current = {}
    section_key = None      # "Auction_data" or "Play_data"
    section_lines = []

    with open(path, "r", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n\r")
            m = re.match(r'^\[(\w+)\s+"(.*)"\]\s*$', line)
            if m:
                # Flush accumulated section lines
                if section_key and section_lines:
                    current[section_key] = list(section_lines)
                section_key = None
                section_lines = []

                tag, value = m.group(1), m.group(2)
                if tag == "Event" and current:
                    boards.append(current)
                    current = {}
                current[tag] = value

                if tag in ("Auction", "Play"):
                    section_key = tag + "_data"
                    section_lines = []
                continue

            # Accumulate section data (skip comments / blanks)
            if section_key is not None:
                stripped = line.strip()
                if stripped.startswith("{") or stripped.startswith(";"):
                    continue
                if stripped:
                    section_lines.append(stripped)

    if section_key and section_lines:
        current[section_key] = section_lines
    if current:
        boards.append(current)
    return boards


def parse_bdl_file(path: str):
    """Parse a .bdl file, returning a list of board dicts compatible with parse_pbn_file output.

    Extracts Deal (as PBN deal string), Dealer, Vulnerable, Contract, and Result
    from each deal in the BDL file.  The Cards section uses a 12-line layout:
      Lines 1-4:  North (S, H, D, C)
      Lines 5-8:  West (left) / East (right)
      Lines 9-12: South (S, H, D, C)
    """
    BDL_RANK = {"A": "A", "K": "K", "Q": "Q", "J": "J", "T": "T",
                "10": "T", "9": "9", "8": "8", "7": "7", "6": "6",
                "5": "5", "4": "4", "3": "3", "2": "2"}
    boards = []

    with open(path, "r", errors="replace") as f:
        lines = f.readlines()

    i = 0
    board_num = 0
    while i < len(lines):
        line = lines[i].rstrip("\n\r")

        # Look for the start of a deal: "Deal " or "Cards"
        if line.startswith("Cards") and ":" in line:
            board_num += 1
            card_lines = []
            # First card line is on the same line as "Cards        :"
            first = line.split(":", 1)[1] if ":" in line else ""
            card_lines.append(first)
            # Read next 11 lines
            for j in range(1, 12):
                if i + j < len(lines):
                    cl = lines[i + j].rstrip("\n\r")
                    if ":" in cl:
                        card_lines.append(cl.split(":", 1)[1])
                    else:
                        card_lines.append(cl)
            i += 12

            # Parse the 12 card lines into 4 hands
            # Each line has space-separated rank characters
            def parse_ranks(text):
                """Extract rank chars from a text fragment."""
                return [BDL_RANK.get(r, r) for r in text.split() if r in BDL_RANK]

            # North: lines 0-3 (centered)
            n_suits = [parse_ranks(card_lines[j]) if j < len(card_lines) else [] for j in range(4)]
            # West/East: lines 4-7, split at midpoint
            w_suits = []
            e_suits = []
            for j in range(4, 8):
                if j < len(card_lines):
                    cl = card_lines[j]
                    # Split at large whitespace gap (West is left, East is right)
                    # Find the gap: look for 4+ consecutive spaces in the middle
                    mid = len(cl) // 2
                    # Search for a gap of 4+ spaces near the middle
                    best_gap_start = -1
                    best_gap_len = 0
                    in_gap = False
                    gap_start = 0
                    for k, ch in enumerate(cl):
                        if ch == ' ':
                            if not in_gap:
                                in_gap = True
                                gap_start = k
                        else:
                            if in_gap:
                                gap_len = k - gap_start
                                if gap_len > best_gap_len:
                                    best_gap_len = gap_len
                                    best_gap_start = gap_start
                                in_gap = False
                    if in_gap:
                        gap_len = len(cl) - gap_start
                        if gap_len > best_gap_len:
                            best_gap_len = gap_len
                            best_gap_start = gap_start

                    if best_gap_len >= 4 and best_gap_start > 0:
                        w_suits.append(parse_ranks(cl[:best_gap_start]))
                        e_suits.append(parse_ranks(cl[best_gap_start + best_gap_len:]))
                    else:
                        w_suits.append(parse_ranks(cl))
                        e_suits.append([])
                else:
                    w_suits.append([])
                    e_suits.append([])

            # South: lines 8-11
            s_suits = [parse_ranks(card_lines[j]) if j < len(card_lines) else [] for j in range(8, 12)]

            # Build PBN deal string: "N:S.H.D.C E.H.D.C S.H.D.C W.H.D.C"
            def suits_to_pbn(suits_list):
                return ".".join("".join(s) for s in suits_list)

            pbn_deal = f"N:{suits_to_pbn(n_suits)} {suits_to_pbn(e_suits)} {suits_to_pbn(s_suits)} {suits_to_pbn(w_suits)}"

            # Collect metadata from surrounding lines
            board = {"Deal": pbn_deal, "Board": str(board_num)}

            # Look backwards for Dealer, Vuln, Deal-text
            for back in range(1, 10):
                idx = i - 12 - back
                if idx < 0:
                    break
                bl = lines[idx].rstrip()
                if bl.startswith("Dealer"):
                    board["Dealer"] = bl.split(":", 1)[1].strip().rstrip()
                elif bl.startswith("Vuln"):
                    v = bl.split(":", 1)[1].strip()
                    board["Vulnerable"] = v.replace("None", "-").replace("Both", "All").strip()
                elif bl.startswith("Deal-text"):
                    dt = bl.split(":", 1)[1].strip()
                    board["Board"] = dt

            # Look forwards for Contract, Result
            for fwd in range(13):
                idx = i + fwd
                if idx >= len(lines):
                    break
                fl = lines[idx].rstrip()
                if fl.startswith("Contract"):
                    parts = fl.split(":", 1)[1].strip().split()
                    if parts:
                        board["Contract"] = parts[0].upper()
                    if len(parts) > 1:
                        board["Declarer"] = parts[1][0] if parts[1] else ""
                elif fl.startswith("Result"):
                    parts = fl.split(":", 1)[1].strip().split()
                    # Result format: contract declarer +/-tricks score deal_id
                    if len(parts) >= 4:
                        board["Result"] = parts[2]  # e.g. "+0", "-5", "="
                elif fl.startswith("****"):
                    break
            boards.append(board)
            continue
        i += 1

    return boards


# ---------------------------------------------------------------------------
# BDL (Bridge Deal Log) format — Q-Plus Bridge native log format
# ---------------------------------------------------------------------------

SEAT_FULL = {"N": "North", "E": "East", "S": "South", "W": "West"}
SEAT_ORDER = "NESW"
RANK_VALUE = {
    "A": 14, "K": 13, "Q": 12, "J": 11, "T": 10, "10": 10,
    "9": 9, "8": 8, "7": 7, "6": 6, "5": 5, "4": 4, "3": 3, "2": 2,
}


def _to_bdl_rank(rank: str) -> str:
    """Convert internal rank ('10') to BDL rank ('T')."""
    return "T" if rank == "10" else rank


def _bdl_vuln(vuln_str: str) -> str:
    """Convert PBN vulnerability string to BDL format."""
    v = vuln_str.strip().upper().replace("-", "")
    if v in ("NONE", "LOVE", "O", ""):
        return "---"
    if v in ("NS",):
        return "N/S"
    if v in ("EW",):
        return "E/W"
    if v in ("BOTH", "ALL", "B"):
        return "Both"
    return vuln_str


def _bdl_contract(contract_str: str) -> str:
    """Convert PBN contract like '2S', '3NTX', '4HXX' to BDL lowercase."""
    s = contract_str.strip().upper()
    # Separate level+suit from doubles
    m = re.match(r"(\d)(S|H|D|C|NT)(X{0,2})", s)
    if not m:
        return contract_str.lower()
    level, suit, dbl = m.groups()
    return f"{level}{suit.lower()}{dbl.lower()}"


def _bdl_bid(pbn_bid: str) -> str:
    """Convert a single PBN bid to BDL format."""
    b = pbn_bid.strip().upper()
    if b in ("PASS", "P", "AP"):
        return "-"
    if b in ("X", "DBL"):
        return "x"
    if b in ("XX", "RDBL"):
        return "xx"
    # Level+suit: e.g. 1H → 1h, 3NT → 3nt
    m = re.match(r"(\d)(S|H|D|C|NT)", b)
    if m:
        return m.group(1) + m.group(2).lower()
    return b.lower()


def _suit_ranks_str(cards, suit):
    """Get space-separated ranks for a suit, using T for 10."""
    ranks = sorted(
        [c[1:] for c in cards if c[0] == suit],
        key=lambda r: RANK_ORDER.get(r, 99),
    )
    if not ranks:
        return "-"
    return " ".join(_to_bdl_rank(r) for r in ranks)


def _bdl_cards_block(hands):
    """Format the BDL Cards section (12 lines: N 4, W/E 4, S 4)."""
    lines = []
    # North (centered at column 18)
    for s in SUITS:
        lines.append(f"             :                  {_suit_ranks_str(hands[0], s)} ")
    # West / East side by side
    for s in SUITS:
        w_str = _suit_ranks_str(hands[3], s)
        e_str = _suit_ranks_str(hands[1], s)
        lines.append(f"             :   {w_str:<24}      {e_str} ")
    # South (centered)
    for s in SUITS:
        lines.append(f"             :                  {_suit_ranks_str(hands[2], s)} ")
    return "\n".join(lines)


def _parse_pbn_play(play_lines, opening_leader, col_order=None):
    """Parse PBN [Play] lines into per-trick card-by-seat dicts.

    Returns list of dicts {seat_char: card_str} where card_str uses our
    internal format (e.g. 'DQ', 'SA', 'H10').
    """
    if col_order is None:
        li = SEAT_ORDER.index(opening_leader)
        col_order = [SEAT_ORDER[(li + i) % 4] for i in range(4)]

    tricks = []
    for line in play_lines:
        raw = line.split()
        if len(raw) < 4:
            continue
        trick = {}
        for i, tok in enumerate(raw[:4]):
            if tok == "-":
                continue
            # Normalise: PBN uses uppercase suit+rank, e.g. DQ, CT, SA
            card = tok.upper()
            # Convert T → 10 for internal format
            if len(card) == 2 and card[1] == "T":
                card = card[0] + "10"
            trick[col_order[i]] = card
        if len(trick) == 4:
            tricks.append(trick)
    return tricks


def _determine_trick_winner(trick_cards, leader, trump_suit):
    """Return the seat char of the trick winner."""
    li = SEAT_ORDER.index(leader)
    led_card = trick_cards[leader]
    led_suit = led_card[0]

    best_seat = leader
    best_is_trump = (led_suit == trump_suit) if trump_suit else False
    best_value = RANK_VALUE.get(led_card[1:], 0)

    for i in range(1, 4):
        seat = SEAT_ORDER[(li + i) % 4]
        card = trick_cards[seat]
        suit = card[0]
        value = RANK_VALUE.get(card[1:], 0)
        is_trump = (suit == trump_suit) if trump_suit else False

        if is_trump and not best_is_trump:
            best_seat, best_is_trump, best_value = seat, True, value
        elif is_trump and best_is_trump and value > best_value:
            best_seat, best_value = seat, value
        elif suit == led_suit and not best_is_trump and value > best_value:
            best_seat, best_value = seat, value

    return best_seat


def _bdl_tricks_block(trick_dicts, leaders, winners, declarer_seat, trump_suit):
    """Format the BDL Tricks section from analysed trick data."""
    declarer_ns = declarer_seat in ("N", "S")
    lines = []
    for idx, (trick, leader, winner) in enumerate(zip(trick_dicts, leaders, winners)):
        num = idx + 1
        declarer_won = (winner in ("N", "S")) == declarer_ns

        # Cards in play order (leader first, clockwise)
        li = SEAT_ORDER.index(leader)
        card_strs = []
        winner_card_suit = None
        for j in range(4):
            seat = SEAT_ORDER[(li + j) % 4]
            card = trick[seat]
            suit_ch = card[0].lower()
            rank = _to_bdl_rank(card[1:])
            cs = f"{suit_ch}{rank}"
            if seat == winner:
                cs += "+" if declarer_won else "-"
                winner_card_suit = card[0]
            card_strs.append(f"{cs:<5}")

        spacing = "    " if declarer_won else "        "
        suit_ind = winner_card_suit if winner_card_suit else ""

        prefix = "Tricks       :" if num == 1 else "             :"
        lines.append(f"{prefix} {num:2d}  {leader}    {''.join(card_strs)}{spacing}{suit_ind} ")
    return "\n".join(lines)


def _analyse_play(trick_dicts, declarer_seat, contract_str):
    """Determine leaders and winners for each trick.

    Returns (leaders, winners) as lists of seat chars.
    """
    # Extract trump suit from contract
    m = re.match(r"\d(S|H|D|C|NT)", contract_str.strip().upper())
    trump_suit = None
    if m:
        ts = m.group(1)
        if ts != "NT":
            trump_suit = ts

    # Opening leader is left of declarer
    di = SEAT_ORDER.index(declarer_seat)
    current_leader = SEAT_ORDER[(di + 1) % 4]

    leaders = []
    winners = []
    for trick in trick_dicts:
        leaders.append(current_leader)
        winner = _determine_trick_winner(trick, current_leader, trump_suit)
        winners.append(winner)
        current_leader = winner

    return leaders, winners


def _bdl_bids_block(auction_lines, dealer_seat):
    """Format the BDL Bids section from PBN auction data."""
    # Flatten all bids from auction lines
    all_bids = []
    for line in auction_lines:
        for tok in line.split():
            if tok.startswith("{") or tok.startswith(";"):
                break
            all_bids.append(tok)

    # Columns are always N, E, S, W.  Dealer starts at their column.
    col_map = {"N": 0, "E": 1, "S": 2, "W": 3}
    start_col = col_map[dealer_seat]

    lines = []
    lines.append(f"Bids         :   N    E    S    W    ")
    lines.append(f"             :  ------------------")

    row = ["     "] * 4  # 5-char blanks
    col = start_col
    for bid in all_bids:
        bdl_bid = _bdl_bid(bid)
        row[col] = f"{bdl_bid:<5}"
        col += 1
        if col >= 4:
            lines.append(f"             :  {''.join(row)}")
            row = ["     "] * 4
            col = 0
    # Flush remaining partial row
    if any(r.strip() for r in row):
        lines.append(f"             :  {''.join(row)}")

    lines.append(f"             :  ==================")
    return "\n".join(lines)


def _calculate_bridge_score(contract_str, declarer_seat, tricks_made, vuln_str):
    """Calculate bridge score from contract, tricks, and vulnerability."""
    m = re.match(r"(\d)(S|H|D|C|NT)(X{0,2})", contract_str.strip().upper())
    if not m:
        return 0
    level = int(m.group(1))
    suit = m.group(2)
    dbl = m.group(3)

    target = 6 + level
    result = tricks_made - target
    vulnerable = False
    vuln_up = vuln_str.strip().upper().replace("-", "")
    if vuln_up in ("BOTH", "ALL", "B"):
        vulnerable = True
    elif vuln_up in ("NS",) and declarer_seat in ("N", "S"):
        vulnerable = True
    elif vuln_up in ("EW",) and declarer_seat in ("E", "W"):
        vulnerable = True

    doubled = len(dbl)

    if result < 0:
        undertricks = -result
        if doubled == 2:
            if vulnerable:
                return -(200 + 400 * max(0, undertricks - 1)) if undertricks >= 1 else 0
            else:
                score = 0
                for i in range(undertricks):
                    score -= 100 if i == 0 else (200 if i < 3 else 400)
                return score
        elif doubled == 1:
            if vulnerable:
                return -(100 + 200 * max(0, undertricks - 1)) if undertricks >= 1 else 0
            else:
                score = 0
                for i in range(undertricks):
                    score -= 100 if i == 0 else (200 if i < 3 else 300)
                return score
        else:
            return (-100 if vulnerable else -50) * undertricks

    # Made contract — trick score
    if suit == "NT":
        trick_score = 40 + 30 * (level - 1)
    elif suit in ("S", "H"):
        trick_score = 30 * level
    else:
        trick_score = 20 * level

    trick_score *= (1, 2, 4)[doubled]
    score = trick_score

    # Bonuses
    if trick_score >= 100:
        score += 500 if vulnerable else 300
    else:
        score += 50
    if level == 6:
        score += 750 if vulnerable else 500
    elif level == 7:
        score += 1500 if vulnerable else 1000
    if doubled == 1:
        score += 50
    elif doubled == 2:
        score += 100

    # Overtricks
    if result > 0:
        if doubled == 2:
            score += result * (400 if vulnerable else 200)
        elif doubled == 1:
            score += result * (200 if vulnerable else 100)
        else:
            score += result * (30 if suit in ("S", "H", "NT") else 20)

    # Score is from declarer's perspective; negative if NS is not declarer
    return score


def board_to_bdl(hands, board_info, source_label="WB"):
    """Convert a single parsed PBN board to BDL format text.

    hands: [N, E, S, W] card lists
    board_info: dict from parse_pbn_file
    source_label: short label for deal ID (e.g. 'WB' for wBridge5)
    """
    info = board_info or {}
    dealer = info.get("Dealer", "N").strip().upper()[0]
    vuln = info.get("Vulnerable", "None")
    contract = info.get("Contract", "")
    declarer = info.get("Declarer", "S").strip().upper()[0]
    result_tricks = info.get("Result", "")
    board_num = info.get("Board", "1")
    date_str = info.get("Date", datetime.now().strftime("%Y.%m.%d"))

    # Build deal ID from date
    try:
        dt = datetime.strptime(date_str, "%Y.%m.%d")
    except ValueError:
        dt = datetime.now()
    deal_id = f"{dt.strftime('%y%b%d')}-{source_label}-{board_num:>02s}"

    out = []
    out.append(f"Deal         :   {deal_id}")
    out.append(f"Dealer       :   {SEAT_FULL.get(dealer, 'North')}")
    out.append(f"Vuln         :   {_bdl_vuln(vuln)}  ")

    # Cards block (first line uses "Cards" prefix)
    cards_text = _bdl_cards_block(hands)
    cards_lines = cards_text.split("\n")
    cards_lines[0] = cards_lines[0].replace("             :", "Cards        :", 1)
    out.append("\n".join(cards_lines))

    # Bidding
    auction_lines = info.get("Auction_data", [])
    if auction_lines:
        out.append("")
        out.append(_bdl_bids_block(auction_lines, dealer))
        out.append(f"Contract     :  {_bdl_contract(contract)}   {SEAT_FULL.get(declarer, 'South')}    ")

    # Tricks
    play_lines = info.get("Play_data", [])
    opening_leader = info.get("Play", "").strip().upper()
    if not opening_leader:
        di = SEAT_ORDER.index(declarer)
        opening_leader = SEAT_ORDER[(di + 1) % 4]

    if play_lines and contract:
        trick_dicts = _parse_pbn_play(play_lines, opening_leader)
        if trick_dicts:
            leaders, winners = _analyse_play(trick_dicts, declarer, contract)

            if not auction_lines:
                # If no bidding block, emit Trick-prep and Contract here
                out.append("")
                dbl_flag = "+0"
                if "XX" in contract.upper():
                    dbl_flag = "+2"
                elif "X" in contract.upper():
                    dbl_flag = "+1"
                out.append(f"Trick-prep   : {opening_leader} ")
                out.append(f"Contract     :  {_bdl_contract(contract)}   {SEAT_FULL.get(declarer, 'South')}     {dbl_flag}")

            out.append("")

            # Extract trump for the tricks block
            m = re.match(r"\d(S|H|D|C|NT)", contract.strip().upper())
            trump = None
            if m and m.group(1) != "NT":
                trump = m.group(1)

            out.append(_bdl_tricks_block(trick_dicts, leaders, winners, declarer, trump))

    # Result
    out.append("")
    if result_tricks and contract:
        tricks_made = int(result_tricks)
        target = 6 + int(contract[0])
        diff = tricks_made - target
        diff_str = f"+{diff}" if diff > 0 else ("=" if diff == 0 else str(diff))

        # Try to get score from PBN, otherwise calculate
        score_str = info.get("Score", "")
        score_val = None
        if score_str:
            m = re.search(r"(-?\d+)", score_str)
            if m:
                score_val = int(m.group(1))
        if score_val is None:
            score_val = _calculate_bridge_score(contract, declarer, tricks_made, vuln)

        out.append(f"Result       :  {_bdl_contract(contract)}   {SEAT_FULL.get(declarer, 'South')}    {diff_str}      {score_val}      {deal_id}")
    elif contract:
        out.append(f"Result       :  {_bdl_contract(contract)}   {SEAT_FULL.get(declarer, 'South')}    =      0      {deal_id}")

    out.append("")
    out.append("************************************************************")
    out.append("")
    return "\n".join(out)


def pbn_file_to_bdl(path: str, source_label: str = "WB") -> str:
    """Convert an entire PBN file to BDL format."""
    boards = parse_pbn_file(path)

    # Determine date for header
    date_str = "unknown"
    for b in boards:
        if "Date" in b:
            try:
                dt = datetime.strptime(b["Date"], "%Y.%m.%d")
                date_str = dt.strftime("%b/%d/%Y")
            except ValueError:
                pass
            break

    # Determine source program for bidding convention label
    south_name = ""
    for b in boards:
        south_name = b.get("South", b.get("North", ""))
        break
    if "wbridge" in south_name.lower():
        cnv_label = "wBridge5 conventions"
    else:
        cnv_label = south_name or "Unknown"

    header = (
        f"DOCTYPE: BDL 17.1\n"
        f'.description.eng = "converted from PBN — {date_str}"\n'
        f"\n"
        f"Scoring      :  Pair (MP)\n"
        f".Bidding cnv :  N/S: {cnv_label}\n"
        f".            :  E/W: {cnv_label}\n"
        f".Source      :  PBN file: {Path(path).name}\n"
        f"\n"
    )

    sections = [header]
    for board in boards:
        deal_str = board.get("Deal", "")
        if not deal_str:
            continue
        try:
            hands = parse_pbn_deal_string(deal_str)
        except ValueError:
            continue
        sections.append(board_to_bdl(hands, board, source_label))

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Random deal generation (from bridge_input.py)
# ---------------------------------------------------------------------------

def generate_random_deal(target_hcp=None, target_shape=None, max_tries=20000):
    deck = [s + r for s in SUITS for r in RANKS]
    for _ in range(max_tries):
        random.shuffle(deck)
        hands = [deck[0:13], deck[13:26], deck[26:39], deck[39:52]]
        south = hands[2]
        if target_hcp is not None and hand_hcp(south) != target_hcp:
            continue
        if target_shape is not None and hand_shape(south) != target_shape:
            continue
        return [list(h) for h in hands]
    raise RuntimeError("Could not generate deal matching constraints")


# ---------------------------------------------------------------------------
# Grid interpolation / mouse automation
# ---------------------------------------------------------------------------

def interpolate_grid(top_left, bottom_right, rows=4, cols=13):
    x0, y0 = top_left
    x1, y1 = bottom_right
    sx = (x1 - x0) / (cols - 1) if cols > 1 else 0
    sy = (y1 - y0) / (rows - 1) if rows > 1 else 0
    return {(r, c): (x0 + c * sx, y0 + r * sy) for r in range(rows) for c in range(cols)}


class AutomationWorker(QThread):
    """Run hand-entry mouse automation in a background thread.

    Cards are always entered. Dealer / vulnerability are entered too if
    the caller passes positions for them — those calibration entries are
    optional and skipped silently when missing.
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, hands, grid_coords, player_positions, ok_pos, clear_pos,
                 dealer="", vuln="",
                 dv_open_btn=None, dealer_positions=None,
                 vuln_positions=None, dv_ok_btn=None):
        super().__init__()
        self.hands = hands
        self.grid_coords = grid_coords
        self.player_positions = player_positions
        self.ok_pos = ok_pos
        self.clear_pos = clear_pos
        self.dealer = dealer or ""
        self.vuln = vuln or ""
        # "Dealer + vul." button on the Hand Input dialog, and the Ok
        # button on the popup it spawns. Both must be calibrated for
        # the dealer/vuln auto-entry to run.
        self.dv_open_btn = dv_open_btn
        self.dv_ok_btn = dv_ok_btn
        # Token → (x, y) maps for the popup's radio buttons.
        self.dealer_positions = dealer_positions or {}
        self.vuln_positions = vuln_positions or {}

    def _click(self, pos, settle=0.15):
        pyautogui.moveTo(*pos, duration=0.2)
        pyautogui.click()
        if settle:
            time.sleep(settle)

    def _enter_dealer_vuln(self):
        """Open the Dealer & Vulnerability popup, set values, click its Ok.

        Returns (entered, missing) where:
          entered : list of "key=val" strings actually written.
          missing : list of "key=val" the caller wanted but couldn't
                    set because the corresponding calibration is
                    missing (so the status message can tell the user).
        """
        entered, missing = [], []
        # Skip entirely if neither requested.
        if not self.dealer and not self.vuln:
            return entered, missing

        # All-or-nothing precondition: open + ok buttons must both be
        # captured. Without one of them the popup flow can't complete
        # safely, so leave the values for the user.
        if not self.dv_open_btn or not self.dv_ok_btn:
            if self.dealer:
                missing.append(f"dealer={self.dealer}")
            if self.vuln:
                missing.append(f"vuln={self.vuln}")
            return entered, missing

        self.progress.emit("Opening Dealer & Vulnerability dialog...")
        self._click(self.dv_open_btn, settle=0.6)  # popup needs time to appear

        if self.dealer:
            pos = self.dealer_positions.get(self.dealer)
            if pos:
                self.progress.emit(f"Setting dealer = {self.dealer}...")
                self._click(pos)
                entered.append(f"dealer={self.dealer}")
            else:
                missing.append(f"dealer={self.dealer}")

        if self.vuln:
            pos = self.vuln_positions.get(self.vuln)
            if pos:
                self.progress.emit(f"Setting vulnerability = {self.vuln}...")
                self._click(pos)
                entered.append(f"vuln={self.vuln}")
            else:
                missing.append(f"vuln={self.vuln}")

        self.progress.emit("Closing Dealer & Vulnerability dialog...")
        self._click(self.dv_ok_btn, settle=0.4)
        return entered, missing

    def run(self):
        try:
            self.progress.emit("Clicking Clear all...")
            time.sleep(2)
            self._click(self.clear_pos, settle=0.5)

            for p_idx, hand in enumerate(self.hands):
                name = PLAYER_NAMES[p_idx]
                self.progress.emit(f"Entering {name}...")
                px, py = self.player_positions[p_idx]
                pyautogui.moveTo(px, py, duration=0.2)
                pyautogui.click()
                time.sleep(0.3)
                for card in hand:
                    if card not in CARD_COORDS_MAP:
                        continue
                    r, c = CARD_COORDS_MAP[card]
                    cx, cy = self.grid_coords[(r, c)]
                    pyautogui.moveTo(cx, cy, duration=0.15)
                    pyautogui.mouseDown()
                    time.sleep(0.05)
                    pyautogui.mouseUp()
                    time.sleep(0.08)

            # Dealer / vulnerability sub-dialog. Runs BEFORE the main Ok
            # because clicking Ok dismisses the Hand Input dialog along
            # with the "Dealer + vul." button.
            entered_meta, missing_meta = self._enter_dealer_vuln()

            self.progress.emit("Clicking OK...")
            self._click(self.ok_pos, settle=0)

            msg = "Hand entered successfully."
            if entered_meta:
                msg = msg.rstrip(".") + " (" + ", ".join(entered_meta) + ")."
            if missing_meta:
                msg += (" Set " + ", ".join(missing_meta) +
                        " manually in Q-Plus, or capture the missing "
                        "calibration points in the harness.")
            self.finished.emit(True, msg)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Calibration data
# ---------------------------------------------------------------------------

DEFAULT_CALIBRATION = {
    "north_chk": None,
    "west_chk": None,
    "grid_tl": None,
    "grid_br": None,
    "clear_btn": None,
    "ok_btn": None,
    # Optional: dealer + vulnerability flow. Q-Plus's "Hand Input" dialog
    # has a "Dealer + vul." button that opens a popup with N/E/S/W
    # dealer radios, none/N-S/E-W/all vulnerability radios, and its own
    # Ok button. When all 10 entries below are captured, AutomationWorker
    # clicks "Dealer + vul.", picks the requested dealer + vuln on the
    # popup, then clicks the popup's Ok — all before pressing the main
    # Hand Input Ok. Without these captures the worker still enters the
    # cards but leaves dealer/vuln for the user to set manually.
    "dealer_vul_btn": None,   # "Dealer + vul." button on Hand Input
    "dealer_n": None,         # popup: Dealer = North
    "dealer_e": None,         # popup: Dealer = East
    "dealer_s": None,         # popup: Dealer = South
    "dealer_w": None,         # popup: Dealer = West
    "vuln_none": None,        # popup: Vuln = none
    "vuln_ns": None,          # popup: Vuln = N/S
    "vuln_ew": None,          # popup: Vuln = E/W
    "vuln_all": None,         # popup: Vuln = all
    "dv_ok_btn": None,        # Ok button on the Dealer & Vulnerability popup
}


# Standard tokens we accept for dealer / vulnerability across CLI,
# PBN files, and BDL files.
DEALER_TOKENS = {"N", "E", "S", "W"}
VULN_TOKENS   = {"None", "NS", "EW", "Both"}


def normalize_dealer(s: str) -> str:
    """Map any dealer spelling to a canonical 'N' / 'E' / 'S' / 'W'."""
    if not s:
        return ""
    c = s.strip().upper()[:1]
    return c if c in DEALER_TOKENS else ""


def normalize_vuln(s: str) -> str:
    """Map any vulnerability spelling to canonical 'None' / 'NS' / 'EW' / 'Both'."""
    if not s:
        return ""
    v = s.strip().replace("-", "").replace(" ", "")
    upper = v.upper()
    if upper in ("NONE", "NIL", "-"):
        return "None"
    if upper in ("NS", "N/S"):
        return "NS"
    if upper in ("EW", "E/W"):
        return "EW"
    if upper in ("BOTH", "ALL", "B"):
        return "Both"
    return ""


def load_calibration():
    if CALIBRATION_FILE.exists():
        try:
            return json.loads(CALIBRATION_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return dict(DEFAULT_CALIBRATION)


def save_calibration(data):
    CALIBRATION_FILE.write_text(json.dumps(data, indent=2))


def calibration_to_positions(cal):
    """Derive grid_coords and player_positions from calibration data.

    The first six fields (N/W checkboxes, grid corners, Clear/OK) are
    required. Dealer / vulnerability positions are optional — when
    captured, AutomationWorker reads them straight off `cal`.
    """
    n = cal.get("north_chk")
    w = cal.get("west_chk")
    tl = cal.get("grid_tl")
    br = cal.get("grid_br")
    clr = cal.get("clear_btn")
    ok = cal.get("ok_btn")
    if not all([n, w, tl, br, clr, ok]):
        return None, None, None, None

    step_y = (w[1] - n[1]) / 3.0
    player_positions = {
        0: (n[0], n[1]),
        1: (n[0], n[1] + step_y),
        2: (n[0], n[1] + 2 * step_y),
        3: (w[0], w[1]),
    }
    grid_coords = interpolate_grid(tl, br)
    return grid_coords, player_positions, tuple(ok), tuple(clr)


def dealer_vuln_positions(cal):
    """Return (open_btn, dealer_positions, vuln_positions, popup_ok) for
    the optional dealer + vulnerability entry flow.

    `open_btn` and `popup_ok` are (x, y) tuples (or None). The two dicts
    are keyed by canonical token ('N'/'NS'/etc.). AutomationWorker treats
    the whole flow as "all-or-nothing": if any of these is missing the
    dealer/vuln step is skipped and the user must set them by hand.
    """
    def _pt(key):
        v = cal.get(key)
        return tuple(v) if v else None

    open_btn = _pt("dealer_vul_btn")
    popup_ok = _pt("dv_ok_btn")
    dealer = {
        "N": _pt("dealer_n"),
        "E": _pt("dealer_e"),
        "S": _pt("dealer_s"),
        "W": _pt("dealer_w"),
    }
    vuln = {
        "None": _pt("vuln_none"),
        "NS":   _pt("vuln_ns"),
        "EW":   _pt("vuln_ew"),
        "Both": _pt("vuln_all"),
    }
    return open_btn, dealer, vuln, popup_ok


# ---------------------------------------------------------------------------
# PyQt5 GUI
# ---------------------------------------------------------------------------

class CaptureButton(QPushButton):
    """Button that captures the mouse position after a 3-second countdown."""
    captured = pyqtSignal(list)  # [x, y]

    def __init__(self, label, parent=None):
        super().__init__(f"Capture {label}", parent)
        self._label = label
        self._count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.clicked.connect(self._start)

    def _start(self):
        self.setEnabled(False)
        self._count = 3
        self.setText(f"{self._count}...")
        self._timer.start(1000)

    def _tick(self):
        self._count -= 1
        if self._count > 0:
            self.setText(f"{self._count}...")
        else:
            self._timer.stop()
            pos = pyautogui.position()
            self.captured.emit([pos.x, pos.y])
            self.setText(f"Capture {self._label}")
            self.setEnabled(True)


class BridgeHarness(QMainWindow):
    def __init__(self, launch_qplus: bool = True, closed_room: bool = False):
        super().__init__()
        self.setWindowTitle("Bridge Harness \u2014 Q-Plus Bridge")
        # 16 calibration rows + the source / display panels make the
        # Hand Entry tab tall — start the window comfortably tall so
        # the capture buttons aren't squished together.
        self.setMinimumSize(900, 900)
        self.resize(1000, 1000)

        self.hands = None          # [N, E, S, W] card lists
        self.calibration = load_calibration()
        self._worker = None
        self._source_pbn_path = None  # for workflow
        self._closed_room = closed_room  # opened for a live Q-NET closed room
        self._qplus_proc = None       # Popen handle for the Q-Plus child
        # Closed Room tab: the two biq Q-NET client processes (East, West)
        # and the timer that tails their logs into the on-screen view.
        self._biq_procs = {}          # seat-char -> Popen
        self._biq_log_paths = {}      # seat-char -> Path
        self._biq_log_offsets = {}    # seat-char -> int (bytes already shown)
        self._biq_logfiles = {}       # seat-char -> open file (child's stdout/stderr)
        self._biq_log_timer = None
        # Dealer / vulnerability for the loaded deal (normalised tokens).
        # bridgeIQ passes these on --dealer / --vuln so the closed-room
        # entry in Q-Plus matches the open-room conditions. Empty string
        # means "no value yet — user enters manually".
        self.dealer = ""           # one of "" / "N" / "E" / "S" / "W"
        self.vulnerability = ""    # one of "" / "None" / "NS" / "EW" / "Both"

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_entry_tab(), "Hand Entry")
        self.tabs.addTab(self._build_workflow_tab(), "Comparison Workflow")
        self._closed_room_tab_index = self.tabs.addTab(
            self._build_closed_room_tab(), "Closed Room (biq E/W)")
        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage("Ready")
        self._build_menu_bar()

        # Opened straight into the closed-room flow by bridgeIQ
        # (--closed-room). Bring that tab forward once the rest of the
        # window is constructed.
        if closed_room:
            self.tabs.setCurrentIndex(self._closed_room_tab_index)

        # The harness drives Q-Plus through its window \u2014 auto-launch
        # Q-Plus on startup so users always see them together. Callers
        # that have already launched Q-Plus (the wrapping run.sh script)
        # can pass launch_qplus=False to suppress the second instance.
        if launch_qplus:
            self._launch_qplus_if_installed()

    def _build_menu_bar(self):
        """A small menu so the wine/Q-Plus reset is always reachable,
        regardless of which tab is showing. A hung Q-Plus or a stale Q-NET
        listen socket otherwise blocks the next closed-room run with no
        in-harness way to clear it."""
        qmenu = self.menuBar().addMenu("&Q-Plus")
        self.kill_wine_action = QAction("&Kill all wine processes", self)
        self.kill_wine_action.setShortcut("Ctrl+K")
        self.kill_wine_action.setStatusTip(
            "Force-quit Q-Plus and all wine processes to clear a stale "
            "Q-NET socket or a hung Q-Plus before the next closed-room run.")
        self.kill_wine_action.triggered.connect(self._on_kill_all_wine)
        qmenu.addAction(self.kill_wine_action)

    def _on_kill_all_wine(self):
        """Force-quit Q-Plus + all wine so a stale Q-NET socket / hung Q-Plus
        can't block the next closed-room run. Mirrors bridgeIQ's
        Extras -> Kill all wine processes."""
        resp = QMessageBox.question(
            self, "Kill all wine processes?",
            "Force-quit Q-Plus and ALL wine processes?\n\n"
            "This clears a stale Q-NET listen socket and any hung Q-Plus so "
            "biq E/W can attach cleanly next time. Any unsaved Q-Plus score "
            "table is lost.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        # 1) Exit Q-Plus CLEANLY first. SIGKILLing QBRIDGE.EXE outright leaves a
        #    dead X window behind, which the desktop then shows as a
        #    "force quit / wait" dialog. SIGTERM (+ asking the window manager to
        #    close its window) lets wine tear the window down properly, so the
        #    user isn't left staring at a hung Q-Plus.
        self.statusBar().showMessage("Exiting Q-Plus cleanly…")
        QApplication.processEvents()
        procs = [self._qplus_proc]
        try:
            procs += list(self._biq_procs.values())
        except Exception:
            pass
        for p in procs:
            if p is None:
                continue
            try:
                p.terminate()            # SIGTERM — wine closes the app window
            except Exception:
                pass
        # Nudge any Q-Plus window shut via the WM as a belt-and-suspenders
        # (matches by the launcher pid and by title; no-op without xdotool).
        try:
            pid = getattr(self._qplus_proc, 'pid', None)
            close = "command -v xdotool >/dev/null || exit 0; "
            if pid:
                close += f"for w in $(xdotool search --pid {pid} 2>/dev/null); do xdotool windowclose $w; done; "
            close += ("for w in $(xdotool search --name 'Q-Plus' 2>/dev/null) "
                      "$(xdotool search --name 'QBridge' 2>/dev/null); do xdotool windowclose $w; done; true")
            subprocess.run(["bash", "-c", close], timeout=5)
        except Exception:
            pass
        # give Q-Plus a moment to shut its window before we escalate
        for _ in range(15):
            QApplication.processEvents(); time.sleep(0.1)
        # 2) Clean wine shutdown SCOPED TO THE Q-PLUS PREFIX, then SIGKILL only
        #    the named Windows binaries. We deliberately do NOT pkill broad
        #    substrings like 'wine' — that matched and killed bridgeIQ itself.
        #    `wineserver -k` with WINEPREFIX tears down exactly that prefix's
        #    wine session and touches nothing else; the remaining pkills name
        #    the .EXE/script explicitly so they can never hit a python process.
        prefix = str(FRI_DIR / "WP")
        script = (f'WINEPREFIX="{prefix}" wineserver -k 2>/dev/null; sleep 0.4; '
                  "pkill -9 -f 'QBRIDGE\\.EXE'; pkill -9 -f 'Q-NET\\.EXE'; "
                  "pkill -9 -f 'biq_qnet_client\\.py'")
        try:
            subprocess.run(["bash", "-c", script], timeout=20)
        except Exception as e:
            self.statusBar().showMessage(f"Kill wine failed: {e}")
            return
        self._qplus_proc = None
        try:
            self._biq_procs.clear()
        except Exception:
            pass
        self.statusBar().showMessage(
            "Exited Q-Plus and killed all wine — Q-NET socket cleared.")

    def _qplus_install_dir(self):
        """Path of the installed Q-Plus directory, or None if not installed."""
        for subdir in ("WP/drive_c/games/qbridge17",
                       "WP/drive_c/games/qbridge15"):
            candidate = FRI_DIR / subdir
            if candidate.is_dir():
                return candidate
        return None

    def _qplus_own_deals_dir(self):
        """Path to Q-Plus's DATA/OWN-DEALS/ directory, or None."""
        qd = self._qplus_install_dir()
        if qd is None:
            return None
        cand = qd / "DATA" / "OWN-DEALS"
        return cand if cand.is_dir() else None

    def _write_bde_deal(self):
        """Write the loaded deal as a .BDE file in Q-Plus's OWN-DEALS folder.

        Replaces the per-card pyautogui pickboard automation. After
        the file is written the user opens Q-Plus → Own Deals →
        Open → pick the file, and Q-Plus's own engine auto-plays
        the deal. Returns the file path on success, None on failure.
        """
        if self.hands is None:
            QMessageBox.warning(self, "Error", "No deal loaded.")
            return None
        own_dir = self._qplus_own_deals_dir()
        if own_dir is None:
            QMessageBox.warning(self, "Q-Plus not found",
                                "Could not locate Q-Plus's DATA/OWN-DEALS "
                                "directory under FRI/WP. Install Q-Plus or "
                                "fall back to the Pickboard automation.")
            return None
        # Stable filename so re-running this rewrites the same file
        # — useful when Q-Plus's "recent files" remembers it.
        fname = "BRIDGEIQ_RELAY.BDE"
        path = own_dir / fname
        # Honour the dealer / vulnerability the user has set (or that
        # bridgeIQ passed via --dealer / --vuln). Default to N / None
        # when unset.
        dealer = (self.dealer or "N").strip().upper()[:1]
        vuln = (self.vulnerability or "None")
        try:
            label = f"BB-{datetime.now().strftime('%H%M%S')}"
        except Exception:
            label = "BB"
        text = hands_to_bde_text(self.hands, dealer=dealer, vuln=vuln,
                                 label=label,
                                 description="Relayed from bridgeIQ")
        try:
            path.write_text(text, encoding="latin-1")
        except Exception as ex:
            QMessageBox.warning(self, "Write failed", str(ex))
            return None
        self.statusBar().showMessage(
            f"Wrote {fname} to OWN-DEALS/ — load it in Q-Plus via "
            f"Own Deals → Open."
        )
        return str(path)

    def _launch_qplus_if_installed(self):
        """Spawn Q-Plus in the background under wine. No-op if it isn't
        installed (the harness still works for other workflows in that
        case), or if `wine` is missing."""
        import shutil
        import subprocess
        qplus_dir = self._qplus_install_dir()
        if qplus_dir is None:
            self.statusBar().showMessage(
                "Ready (Q-Plus not installed under FRI/WP \u2014 comparison "
                "workflow disabled).")
            return
        # Two runners, two needs:
        #  \u2022 Comparison workflow \u2192 the TkG Lutris runner (WINE env, set by
        #    bridgeHarness.sh's wine_runner.sh) so Q-Plus's Hand Input dialog
        #    renders the \u2660\u2665\u2666\u2663 card glyphs (/usr/bin/wine shows empty boxes).
        #  \u2022 Closed room (live Q-NET) \u2192 system wine 9 is MANDATORY: under the
        #    TkG 6.21 runner Q-Plus's q-net module accepts the TCP connection
        #    but never reads it, so biq E/W can never attach. Glyphs don't
        #    matter for the headless closed-room match.
        if self._closed_room:
            wine_bin = WINE9_BIN
            ok, ver = _wine9_status(wine_bin)
            if not ok:
                from PyQt5.QtWidgets import QMessageBox
                resp = QMessageBox.warning(
                    self, "wine 9 not found",
                    "The closed room needs system <b>wine 9</b> to run "
                    "Q-Plus's Q-NET server.<br><br>"
                    f"Found: <tt>{ver or (WINE9_BIN + ' missing')}</tt>.<br><br>"
                    "Under the TkG runner Q-Plus accepts the connection but "
                    "never reads it, so <b>biq E/W can't attach</b>. Install "
                    "wine 9 (e.g. <tt>sudo apt install wine</tt>) for a "
                    "working closed room.<br><br>Start Q-Plus anyway?",
                    QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
                if resp != QMessageBox.Ok:
                    self.statusBar().showMessage(
                        "Q-Plus not started \u2014 wine 9 required for Q-NET.")
                    return
        else:
            wine_bin = os.environ.get('WINE') or shutil.which('wine')
        if not wine_bin:
            self.statusBar().showMessage(
                "Ready (wine not installed \u2014 Q-Plus cannot launch).")
            return
        env = os.environ.copy()
        env['WINEPREFIX'] = str(FRI_DIR / "WP")
        env['WINEARCH'] = 'win32'
        try:
            self._qplus_proc = subprocess.Popen(
                [wine_bin, 'QBRIDGE.EXE'],
                cwd=str(qplus_dir),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.statusBar().showMessage(f"Q-Plus launched (PID {self._qplus_proc.pid}).")
        except Exception as ex:
            self.statusBar().showMessage(f"Q-Plus launch failed: {ex!r}")
            self._qplus_proc = None

    def load_source(self, path: str, game_name: str = ""):
        """Pre-load a PBN or BDL file into the Comparison Workflow tab.

        Called via --source CLI argument so the harness opens ready for
        the Q-Plus comparison step.
        """
        p = Path(path)
        if not p.is_file():
            return
        # For BDL files, look for the original PBN alongside
        pbn_path = path
        if p.suffix.lower() == ".bdl":
            pbn_candidate = p.with_suffix(".pbn")
            orig_candidate = p.parent / f"{p.stem.replace('.bdl', '')}_original.pbn"
            if pbn_candidate.is_file():
                pbn_path = str(pbn_candidate)
            elif orig_candidate.is_file():
                pbn_path = str(orig_candidate)
            else:
                # Search for any .pbn in same directory
                pbn_files = list(p.parent.glob("*.pbn"))
                if pbn_files:
                    pbn_path = str(pbn_files[0])
                else:
                    pbn_path = path  # fall back to the BDL itself

        self.wf_pbn_path.setText(pbn_path)
        self._source_pbn_path = pbn_path

        # Try to load boards and display deal
        try:
            if pbn_path.lower().endswith(".pbn"):
                boards = self._load_pbn_boards(pbn_path, self.wf_board_combo)
                if boards:
                    deal_str = boards[0].get("Deal", "")
                    self.hands = parse_pbn_deal_string(deal_str)
                    self._show_deal(self.hands, self.wf_hand_display, self.wf_base72)
                    self._show_deal(self.hands, self.hand_display, self.base72_display)
                    self._update_info()
                    # Pull dealer/vuln out of the source so the harness
                    # can write them into Q-Plus matching the original.
                    self.set_dealer_vuln(
                        boards[0].get("Dealer", ""),
                        boards[0].get("Vulnerable", ""),
                    )
        except Exception as exc:
            self.statusBar().showMessage(f"Could not parse source: {exc}")

        # Auto-detect source game name
        if game_name:
            idx = self.wf_game_name.findText(game_name.lower())
            if idx >= 0:
                self.wf_game_name.setCurrentIndex(idx)
            else:
                self.wf_game_name.setEditText(game_name.lower())

        # Switch to Comparison Workflow tab
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"Source loaded: {Path(pbn_path).name}")

    def set_dealer_vuln(self, dealer: str, vuln: str):
        """Set the dealer + vulnerability that the next "Enter Deal"
        action should write into Q-Plus.

        Tokens are normalised; bad inputs leave the previous value in
        place. The status bar and the dealer/vuln display widget (if
        the entry tab is built) both reflect the new state.
        """
        d = normalize_dealer(dealer) if dealer else ""
        v = normalize_vuln(vuln) if vuln else ""
        if d:
            self.dealer = d
        if v:
            self.vulnerability = v
        self._update_dealer_vuln_display()
        self._cr_refresh_deal()
        parts = []
        if self.dealer:
            parts.append(f"dealer = {self.dealer}")
        if self.vulnerability:
            parts.append(f"vuln = {self.vulnerability}")
        if parts:
            self.statusBar().showMessage(
                "From bridgeIQ: " + ", ".join(parts))

    def _update_dealer_vuln_display(self):
        """Refresh the on-screen dealer/vulnerability summary, if built."""
        lbl = getattr(self, "dv_display", None)
        if lbl is None:
            return
        d = self.dealer or "(not set)"
        v = self.vulnerability or "(not set)"
        lbl.setText(f"Dealer: {d}    Vulnerability: {v}")

    def load_base72(self, code: str):
        """Pre-load a deal by base-72 code into the Hand Entry tab.

        Used by bridgeIQ after each hand so the host can immediately
        replay the deal in Q-Plus for closed-room comparison.
        """
        code = (code or "").strip()
        if not code:
            return
        try:
            self.hands = base72_to_deal(code)
        except Exception as exc:
            self.statusBar().showMessage(f"Bad base-72 code: {exc}")
            return
        self.rb_base72.setChecked(True)
        self.input_field.setText(code)
        self._show_deal(self.hands, self.hand_display, self.base72_display)
        self._update_info()
        # Hand Entry tab is index 0; bring it forward so the harness opens
        # ready for the user to click Enter Deal into Q-Plus.
        self.tabs.setCurrentIndex(0)
        self._cr_refresh_deal()
        self.statusBar().showMessage(f"Deal loaded from base-72: {code}")

    # ---- Closed Room tab (biq E/W vs Q-Plus N/S over Q-NET) ---------------

    def show_closed_room_tab(self):
        """Bring the Closed Room tab forward and refresh its deal panel.

        Called from main() after --closed-room so bridgeIQ's "Closed
        Room → Real Q-Plus" path lands the user straight on the wizard.
        """
        self.tabs.setCurrentIndex(self._closed_room_tab_index)
        self._cr_refresh_deal()

    def _build_closed_room_tab(self):
        """A guided, click-through closed room: biq sits East+West, Q-Plus
        sits North+South, and the board is played out live over Q-NET.

        biq's side is driven by two `biq_qnet_client.py` processes (one
        per seat, --pair) that join Q-Plus acting as a Q-NET bridge
        server. The numbered steps mirror the proven CLI flow
        (tools/qplus_two_biq.sh) but as buttons, with a live log.
        """
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(0)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        intro = QLabel(
            "Play a real closed room against Q-Plus: <b>biq sits East + "
            "West, Q-Plus sits North + South</b>, card by card over "
            "Q-NET. Work down the numbered steps.")
        intro.setWordWrap(True)
        intro.setStyleSheet("padding: 4px 0;")
        layout.addWidget(intro)

        # --- Deal summary -------------------------------------------------
        deal_group = QGroupBox("This deal")
        deal_layout = QVBoxLayout(deal_group)
        self.cr_deal_display = QTextEdit()
        self.cr_deal_display.setReadOnly(True)
        self.cr_deal_display.setFont(QFont("Monospace", 10))
        self.cr_deal_display.setMaximumHeight(220)
        deal_layout.addWidget(self.cr_deal_display)
        b72_row = QHBoxLayout()
        b72_row.addWidget(QLabel("Base-72:"))
        self.cr_base72 = QLineEdit()
        self.cr_base72.setReadOnly(True)
        self.cr_base72.setFont(QFont("Monospace", 11))
        b72_row.addWidget(self.cr_base72, stretch=1)
        deal_layout.addLayout(b72_row)
        self.cr_dv_label = QLabel("Dealer: (not set)    Vulnerability: (not set)")
        self.cr_dv_label.setFont(QFont("Monospace", 10))
        deal_layout.addWidget(self.cr_dv_label)
        layout.addWidget(deal_group)

        # --- Step 1: deal into Q-Plus ------------------------------------
        s1 = QGroupBox("1 · Put this deal into Q-Plus")
        s1l = QVBoxLayout(s1)
        s1l.addWidget(QLabel(
            "Write the deal to Q-Plus's OWN-DEALS folder, then in Q-Plus "
            "load it (Own Deals → Open) so the closed room plays the "
            "SAME board as bridgeIQ's open room."))
        self.cr_write_bde_btn = QPushButton(
            "Write deal to OWN-DEALS/ (.BDE)")
        self.cr_write_bde_btn.setStyleSheet(
            "padding: 6px; background-color: #cfe4ff;")
        self.cr_write_bde_btn.clicked.connect(self._write_bde_deal)
        s1l.addWidget(self.cr_write_bde_btn)
        layout.addWidget(s1)

        # --- Step 2: start the Q-Plus Q-NET server -----------------------
        s2 = QGroupBox("2 · Start the Q-Plus Q-NET server (N/S = Q-Plus)")
        s2l = QVBoxLayout(s2)
        s2l.addWidget(QLabel(
            "In Q-Plus:\n"
            "  • Configuration → Players: East = Extern, West = "
            "Extern, North = Computer, South = Computer.\n"
            "  • Network → Start bridge server → set the port "
            "below → Start.\n"
            "  • Match Control → new Closed-Room teams match."))
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Server port:"))
        self.cr_port_spin = QSpinBox()
        self.cr_port_spin.setRange(1, 65535)
        self.cr_port_spin.setValue(5555)
        port_row.addWidget(self.cr_port_spin)
        self.cr_check_btn = QPushButton("Check server")
        self.cr_check_btn.clicked.connect(self._cr_check_server)
        port_row.addWidget(self.cr_check_btn)
        port_row.addStretch()
        s2l.addLayout(port_row)
        self.cr_server_status = QLabel("Server not checked yet.")
        self.cr_server_status.setStyleSheet("color: #555;")
        s2l.addWidget(self.cr_server_status)
        layout.addWidget(s2)

        # --- Step 3: seat biq E/W ----------------------------------------
        s3 = QGroupBox("3 · Seat biq at East + West")
        s3l = QVBoxLayout(s3)
        s3l.addWidget(QLabel(
            "Launches two biq clients (East and West, partnership mode) "
            "that join the server above and play biq's bidding + cardplay."))
        sys_row = QHBoxLayout()
        sys_row.addWidget(QLabel("Bidding system:"))
        self.cr_system_combo = QComboBox()
        self.cr_system_combo.setEditable(True)
        self.cr_system_combo.addItems(
            ["SAYC", "TwoOverOne", "StandardAcol", "Precision90M"])
        sys_row.addWidget(self.cr_system_combo)
        self.cr_auto_system = QCheckBox("Match Q-Plus (auto-system)")
        self.cr_auto_system.setChecked(True)
        self.cr_auto_system.setToolTip(
            "Sync biq's system to whatever Q-Plus reports for E/W, so the "
            "two biq seats and Q-Plus agree on the partnership system.")
        sys_row.addWidget(self.cr_auto_system)
        sys_row.addStretch()
        s3l.addLayout(sys_row)
        btn_row = QHBoxLayout()
        self.cr_connect_btn = QPushButton("Connect biq E/W")
        self.cr_connect_btn.setStyleSheet(
            "font-weight: bold; padding: 6px; background-color: #d6ffd6;")
        self.cr_connect_btn.clicked.connect(self._cr_connect_biq)
        btn_row.addWidget(self.cr_connect_btn)
        self.cr_disconnect_btn = QPushButton("Disconnect")
        self.cr_disconnect_btn.setEnabled(False)
        self.cr_disconnect_btn.clicked.connect(self._cr_disconnect_biq)
        btn_row.addWidget(self.cr_disconnect_btn)
        btn_row.addStretch()
        s3l.addLayout(btn_row)
        self.cr_biq_status = QLabel("biq not connected.")
        self.cr_biq_status.setStyleSheet("color: #555;")
        s3l.addWidget(self.cr_biq_status)
        layout.addWidget(s3)

        # --- Step 4: play + watch ----------------------------------------
        s4 = QGroupBox("4 · Play the board and watch")
        s4l = QVBoxLayout(s4)
        s4l.addWidget(QLabel(
            "In Q-Plus, deal the board (click 'Closed Room' / deal board 1). "
            "biq E/W then bids and plays automatically — live log below. "
            "When the match ends, save it in Q-Plus (Score → Save and "
            "send) and aggregate the .qss with tools/qss_score_aggregate.py."))
        self.cr_log = QTextEdit()
        self.cr_log.setReadOnly(True)
        self.cr_log.setFont(QFont("Monospace", 9))
        self.cr_log.setMinimumHeight(160)
        s4l.addWidget(self.cr_log)
        layout.addWidget(s4)

        layout.addStretch()
        scroll.setWidget(inner)
        outer_layout.addWidget(scroll)
        return outer

    def _cr_refresh_deal(self):
        """Refresh the Closed Room tab's deal summary from the loaded
        hands / dealer / vulnerability. No-op until the tab is built."""
        if getattr(self, "cr_deal_display", None) is None:
            return
        if self.hands:
            self._show_deal(self.hands, self.cr_deal_display, self.cr_base72)
        d = self.dealer or "(not set)"
        v = self.vulnerability or "(not set)"
        self.cr_dv_label.setText(f"Dealer: {d}    Vulnerability: {v}")

    def _cr_python_bin(self):
        """Interpreter for the biq Q-NET client: prefer biq's own venv
        (it has biq's deps), else fall back to system python3."""
        import shutil
        if BIQ_VENV_PYTHON.exists():
            return str(BIQ_VENV_PYTHON)
        return shutil.which("python3") or "python3"

    def _cr_check_server(self):
        """Probe for a TCP listener on the chosen port (non-intrusive:
        reads `ss -tln` rather than opening a real Q-NET connection).
        Returns True if something is listening."""
        port = int(self.cr_port_spin.value())
        listening = False
        try:
            out = subprocess.run(["ss", "-tln"], capture_output=True,
                                 text=True, timeout=3).stdout
            listening = any(f":{port} " in line for line in out.splitlines())
        except (FileNotFoundError, subprocess.SubprocessError):
            import socket
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                    listening = True
            except OSError:
                listening = False
        if listening:
            self.cr_server_status.setText(
                f"✓ A server is listening on 127.0.0.1:{port}.")
            self.cr_server_status.setStyleSheet("color: #060;")
        else:
            self.cr_server_status.setText(
                f"✗ Nothing on 127.0.0.1:{port} yet — start the "
                f"Q-Plus bridge server.")
            self.cr_server_status.setStyleSheet("color: #900;")
        return listening

    def _cr_connect_biq(self):
        """Spawn the two biq Q-NET clients (East, West, --pair) that join
        the Q-Plus server and play biq's side of the closed room."""
        if not BIQ_QNET_CLIENT.is_file():
            QMessageBox.warning(
                self, "biq client not found",
                f"Could not find the biq Q-NET client at:\n{BIQ_QNET_CLIENT}\n\n"
                "The harness expects the biq repo under "
                "FRI/bridgeIQ/bridgeIQ.")
            return
        if self._biq_procs:
            QMessageBox.information(
                self, "Already connected",
                "biq E/W clients are already running. Disconnect first to "
                "restart them.")
            return
        if not self._cr_check_server():
            ret = QMessageBox.question(
                self, "Server not detected",
                "No Q-NET server seems to be listening on this port yet.\n"
                "Start it in Q-Plus first, or connect anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return

        port = int(self.cr_port_spin.value())
        system = self.cr_system_combo.currentText().strip() or "SAYC"
        auto = self.cr_auto_system.isChecked()
        py = self._cr_python_bin()
        try:
            BIQ_QNET_LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BIQ_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        # Unbuffered so the verbose session stream (handshake, bids, cards)
        # AND any uncaught traceback land in the log file line-by-line for
        # the live tail — without this a redirected stderr block-buffers.
        env["PYTHONUNBUFFERED"] = "1"

        started = []
        for seat in ("E", "W"):
            log_path = BIQ_QNET_LOG_DIR / f"closed_room_biq_{seat}.log"
            # Redirect the child's stdout+stderr into this file: it carries
            # the full verbose session output and any crash traceback, so a
            # client that dies before joining still says why.
            try:
                logf = open(log_path, "wb")
            except OSError:
                logf = None
            cmd = [py, str(BIQ_QNET_CLIENT),
                   "--host", "127.0.0.1", "--port", str(port),
                   "--seat", seat, "--pair",
                   "--system", system]
            if auto:
                cmd.append("--auto-system")
            try:
                proc = subprocess.Popen(
                    cmd, cwd=str(BIQ_ROOT), env=env,
                    stdout=(logf or subprocess.DEVNULL),
                    stderr=subprocess.STDOUT,
                    start_new_session=True)
            except Exception as ex:
                if logf is not None:
                    logf.close()
                self._cr_append_log(f"[harness] failed to start biq {seat}: {ex}")
                continue
            self._biq_procs[seat] = proc
            self._biq_logfiles[seat] = logf
            self._biq_log_paths[seat] = log_path
            self._biq_log_offsets[seat] = 0
            started.append(seat)
            self._cr_append_log(
                f"[harness] started biq {seat} (pid {proc.pid}) — "
                f"system {system}{' (auto)' if auto else ''}")

        if started:
            self.cr_biq_status.setText(
                f"biq running: {', '.join(started)} — waiting for "
                f"handshake / deal…")
            self.cr_biq_status.setStyleSheet("color: #060;")
            self.cr_connect_btn.setEnabled(False)
            self.cr_disconnect_btn.setEnabled(True)
            self._cr_start_log_tail()
        else:
            self.cr_biq_status.setText("biq failed to start — see log.")
            self.cr_biq_status.setStyleSheet("color: #900;")

    def _cr_disconnect_biq(self):
        """Stop both biq clients (and their process groups, so any DDS
        helper children go with them)."""
        import signal
        for seat, proc in list(self._biq_procs.items()):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
        for seat, proc in list(self._biq_procs.items()):
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        had_any = bool(self._biq_procs)
        self._biq_procs.clear()
        for seat, logf in list(self._biq_logfiles.items()):
            try:
                if logf is not None:
                    logf.close()
            except Exception:
                pass
        self._biq_logfiles.clear()
        self._cr_stop_log_tail()
        if getattr(self, "cr_biq_status", None) is not None:
            self.cr_biq_status.setText("biq E/W stopped.")
            self.cr_biq_status.setStyleSheet("color: #555;")
            self.cr_connect_btn.setEnabled(True)
            self.cr_disconnect_btn.setEnabled(False)
        if had_any:
            self._cr_append_log("[harness] biq E/W disconnected.")

    def _cr_start_log_tail(self):
        if self._biq_log_timer is None:
            self._biq_log_timer = QTimer(self)
            self._biq_log_timer.timeout.connect(self._cr_poll_logs)
        self._biq_log_timer.start(700)

    def _cr_stop_log_tail(self):
        if self._biq_log_timer is not None:
            self._biq_log_timer.stop()

    def _cr_poll_logs(self):
        """Append new lines from each biq client's --log file, and report
        any client that has exited."""
        for seat in ("E", "W"):
            path = self._biq_log_paths.get(seat)
            if not path or not path.exists():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            off = self._biq_log_offsets.get(seat, 0)
            if len(data) <= off:
                continue
            chunk = data[off:].decode("utf-8", "replace")
            self._biq_log_offsets[seat] = len(data)
            for line in chunk.splitlines():
                if line.strip():
                    self._cr_append_log(f"[{seat}] {line}")

        for seat, proc in list(self._biq_procs.items()):
            if proc.poll() is not None:
                self._cr_append_log(
                    f"[harness] biq {seat} exited (code {proc.returncode}).")
                self._biq_procs.pop(seat, None)
        if not self._biq_procs:
            self._cr_stop_log_tail()
            if getattr(self, "cr_connect_btn", None) is not None:
                self.cr_connect_btn.setEnabled(True)
                self.cr_disconnect_btn.setEnabled(False)
                self.cr_biq_status.setText("biq E/W finished / stopped.")
                self.cr_biq_status.setStyleSheet("color: #555;")

    def _cr_append_log(self, text: str):
        log = getattr(self, "cr_log", None)
        if log is None:
            return
        log.append(text.rstrip("\n"))

    def closeEvent(self, event):
        """Tear down any running biq clients so they don't outlive the
        harness window."""
        try:
            self._cr_disconnect_biq()
        except Exception:
            pass
        super().closeEvent(event)

    # ---- Hand Entry tab ---------------------------------------------------

    def _build_entry_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left: hand display
        left = QVBoxLayout()
        self.hand_display = QTextEdit()
        self.hand_display.setReadOnly(True)
        self.hand_display.setFont(QFont("Monospace", 11))
        self.hand_display.setMinimumWidth(380)
        left.addWidget(QLabel("Deal"))
        left.addWidget(self.hand_display, stretch=1)

        # Base-72 display (always visible, copyable)
        b72_row = QHBoxLayout()
        b72_row.addWidget(QLabel("Base-72 code:"))
        self.base72_display = QLineEdit()
        self.base72_display.setReadOnly(True)
        self.base72_display.setFont(QFont("Monospace", 12))
        b72_row.addWidget(self.base72_display, stretch=1)
        left.addLayout(b72_row)

        # Info (HCP / shape)
        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Monospace", 10))
        left.addWidget(self.info_label)

        # Dealer / Vulnerability summary — populated from --dealer / --vuln
        # passed by bridgeIQ, or by manually parsing the source file.
        # Shown so the user can verify what the harness will set in Q-Plus.
        self.dv_display = QLabel("Dealer: (not set)    Vulnerability: (not set)")
        self.dv_display.setFont(QFont("Monospace", 11))
        self.dv_display.setStyleSheet(
            "background-color: #f0f4ff; border: 1px solid #889;"
            " padding: 4px; font-weight: bold;")
        left.addWidget(self.dv_display)

        layout.addLayout(left, stretch=1)

        # Right: controls
        right = QVBoxLayout()

        # Source selection
        src_group = QGroupBox("Source")
        src_layout = QVBoxLayout(src_group)
        self.src_buttons = QButtonGroup(self)
        self.rb_random = QRadioButton("Random deal")
        self.rb_pbn_str = QRadioButton("PBN string")
        self.rb_pbn_file = QRadioButton("PBN / BDL file")
        self.rb_base72 = QRadioButton("Base-72 code")
        for i, rb in enumerate([self.rb_random, self.rb_pbn_str, self.rb_pbn_file, self.rb_base72]):
            self.src_buttons.addButton(rb, i)
            src_layout.addWidget(rb)
        self.rb_random.setChecked(True)

        # Random options
        hcp_row = QHBoxLayout()
        self.hcp_check = QCheckBox("South HCP:")
        self.hcp_spin = QSpinBox()
        self.hcp_spin.setRange(0, 37)
        self.hcp_spin.setValue(12)
        self.hcp_spin.setEnabled(False)
        self.hcp_check.toggled.connect(self.hcp_spin.setEnabled)
        hcp_row.addWidget(self.hcp_check)
        hcp_row.addWidget(self.hcp_spin)
        src_layout.addLayout(hcp_row)

        # Input field (reused for PBN string, base-72, and file path)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter PBN deal or base-72 code...")
        src_layout.addWidget(self.input_field)

        self.browse_btn = QPushButton("Browse PBN / BDL file...")
        self.browse_btn.clicked.connect(self._browse_pbn)
        src_layout.addWidget(self.browse_btn)

        self.board_combo = QComboBox()
        self.board_combo.setVisible(False)
        src_layout.addWidget(self.board_combo)

        self.load_btn = QPushButton("Load / Generate")
        self.load_btn.setStyleSheet("font-weight: bold;")
        self.load_btn.clicked.connect(self._load_deal)
        src_layout.addWidget(self.load_btn)

        right.addWidget(src_group)

        # Calibration — 16 capture rows, broken into "core pickboard" and
        # "dealer/vuln popup" sections so the user can tell which set is
        # required vs optional. Wrapped in a scroll area so the right
        # panel stays usable even when the window is shrunk.
        cal_group = QGroupBox("Q-Plus Calibration")
        cal_outer = QVBoxLayout(cal_group)

        cal_scroll = QScrollArea()
        cal_scroll.setWidgetResizable(True)
        cal_scroll.setFrameStyle(0)
        cal_scroll.setMinimumHeight(280)
        cal_inner = QWidget()
        cal_layout = QVBoxLayout(cal_inner)
        cal_layout.setSpacing(6)
        cal_layout.setContentsMargins(2, 2, 2, 2)

        self._cap_buttons = {}
        sections = [
            ("Pickboard dialog (required)", [
                ("north_chk", "North checkbox"),
                ("west_chk", "West checkbox"),
                ("grid_tl", "Ace of Spades (top-left)"),
                ("grid_br", "Two of Clubs (bottom-right)"),
                ("clear_btn", "Clear all button"),
                ("ok_btn", "OK button"),
            ]),
            ("Dealer + Vulnerability popup (optional)", [
                ("dealer_vul_btn", "'Dealer + vul.' button"),
                ("dealer_n", "Dealer popup: North"),
                ("dealer_e", "Dealer popup: East"),
                ("dealer_s", "Dealer popup: South"),
                ("dealer_w", "Dealer popup: West"),
                ("vuln_none", "Vuln popup: none"),
                ("vuln_ns", "Vuln popup: N/S"),
                ("vuln_ew", "Vuln popup: E/W"),
                ("vuln_all", "Vuln popup: all"),
                ("dv_ok_btn", "Dealer/Vuln popup OK"),
            ]),
        ]
        for section_title, entries in sections:
            section_lbl = QLabel(section_title)
            section_lbl.setStyleSheet(
                "font-weight: bold; color: #335; padding: 4px 0 2px 0;")
            cal_layout.addWidget(section_lbl)
            for key, label in entries:
                btn = CaptureButton(label)
                btn.setMinimumHeight(28)
                btn.captured.connect(lambda pos, k=key: self._on_capture(k, pos))
                coord_label = QLabel(self._fmt_coord(self.calibration.get(key)))
                coord_label.setMinimumWidth(110)
                coord_label.setStyleSheet("color: #557;")
                self._cap_buttons[key] = (btn, coord_label)
                row = QHBoxLayout()
                row.setSpacing(8)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(btn, stretch=1)
                row.addWidget(coord_label)
                row_widget = QWidget()
                row_widget.setLayout(row)
                cal_layout.addWidget(row_widget)
        cal_layout.addStretch()
        cal_scroll.setWidget(cal_inner)
        cal_outer.addWidget(cal_scroll)
        right.addWidget(cal_group, stretch=1)

        # Two entry paths:
        #   1. Write deal to Q-Plus's OWN-DEALS folder as a .BDE
        #      file. Fast, reliable, no per-card mouse-click chain.
        #      Q-Plus picks it up via Own Deals → Open. This is the
        #      preferred path.
        #   2. Drive the pickboard dialog with pyautogui. The legacy
        #      path — kept as a fallback for setups where the .BDE
        #      file workflow doesn't fit.
        self.write_bde_btn = QPushButton("Write Deal to OWN-DEALS/ (.BDE)")
        self.write_bde_btn.setStyleSheet(
            "font-weight: bold; padding: 8px; background-color: #cfe4ff;")
        self.write_bde_btn.setToolTip(
            "Write the loaded deal as a Q-Plus .BDE file in the OWN-DEALS\n"
            "directory. Then in Q-Plus: Own Deals → Open → pick the file.\n"
            "Q-Plus will then auto-play the deal — no per-card clicking.")
        self.write_bde_btn.clicked.connect(self._write_bde_deal)
        right.addWidget(self.write_bde_btn)

        self.enter_btn = QPushButton(
            "Enter Deal via Pickboard (slow, fallback)")
        self.enter_btn.setStyleSheet("padding: 8px;")
        self.enter_btn.setToolTip(
            "Legacy path: opens Q-Plus's Hand Input dialog and clicks\n"
            "all 52 cards via pyautogui. Use only when the .BDE file\n"
            "workflow above is not available.")
        self.enter_btn.clicked.connect(self._enter_deal)
        right.addWidget(self.enter_btn)

        right.addStretch()
        layout.addLayout(right)
        return widget

    # ---- Workflow tab ------------------------------------------------------

    def _build_workflow_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(
            "Compare a hand played in another program (e.g. wBridge5) with Q-Plus Bridge.\n"
            "The source PBN and Q-Plus results are collected into afterGameReport."
        ))

        # Step 1: load source PBN
        s1 = QGroupBox("Step 1 — Load source PBN file")
        s1_layout = QHBoxLayout(s1)
        self.wf_pbn_path = QLineEdit()
        self.wf_pbn_path.setReadOnly(True)
        s1_layout.addWidget(self.wf_pbn_path, stretch=1)
        self.wf_browse_btn = QPushButton("Browse...")
        self.wf_browse_btn.clicked.connect(self._wf_browse_source)
        s1_layout.addWidget(self.wf_browse_btn)
        layout.addWidget(s1)

        # Board selector for multi-board PBN
        self.wf_board_combo = QComboBox()
        self.wf_board_combo.setVisible(False)
        self.wf_board_combo.currentIndexChanged.connect(self._wf_board_changed)
        layout.addWidget(self.wf_board_combo)

        # Show deal
        self.wf_hand_display = QTextEdit()
        self.wf_hand_display.setReadOnly(True)
        self.wf_hand_display.setFont(QFont("Monospace", 10))
        self.wf_hand_display.setMaximumHeight(280)
        layout.addWidget(self.wf_hand_display)

        # Base-72 for workflow
        b72_row = QHBoxLayout()
        b72_row.addWidget(QLabel("Base-72:"))
        self.wf_base72 = QLineEdit()
        self.wf_base72.setReadOnly(True)
        self.wf_base72.setFont(QFont("Monospace", 12))
        b72_row.addWidget(self.wf_base72, stretch=1)
        layout.addLayout(b72_row)

        # Step 2: enter into qplus
        s2 = QGroupBox("Step 2 — Enter hand into Q-Plus Bridge")
        s2_layout = QVBoxLayout(s2)
        s2_layout.addWidget(QLabel(
            "Open Q-Plus → Own Deals → Enter, then click below.\n"
            "Uses calibration from the Hand Entry tab."
        ))
        self.wf_enter_btn = QPushButton("Enter into Q-Plus")
        self.wf_enter_btn.clicked.connect(self._wf_enter_deal)
        s2_layout.addWidget(self.wf_enter_btn)
        layout.addWidget(s2)

        # Step 3: pick up qplus log
        s3 = QGroupBox("Step 3 — Collect Q-Plus log file")
        s3_layout = QHBoxLayout(s3)
        self.wf_log_path = QLineEdit()
        self.wf_log_path.setReadOnly(True)
        s3_layout.addWidget(self.wf_log_path, stretch=1)
        wf_log_browse = QPushButton("Browse...")
        wf_log_browse.clicked.connect(self._wf_browse_log)
        s3_layout.addWidget(wf_log_browse)
        wf_log_auto = QPushButton("Auto-detect latest")
        wf_log_auto.clicked.connect(self._wf_autodetect_log)
        s3_layout.addWidget(wf_log_auto)
        layout.addWidget(s3)

        # Step 4: source game name + copy
        s4 = QGroupBox("Step 4 — Convert & copy to afterGameReport")
        s4_layout = QVBoxLayout(s4)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Source game:"))
        self.wf_game_name = QComboBox()
        self.wf_game_name.setEditable(True)
        self.wf_game_name.addItems(["wbridge5", "bridgeIQ", "bb12", "tenace"])
        name_row.addWidget(self.wf_game_name, stretch=1)
        s4_layout.addLayout(name_row)

        self.wf_copy_btn = QPushButton("Convert PBN & copy both files to afterGameReport")
        self.wf_copy_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        self.wf_copy_btn.clicked.connect(self._wf_copy_to_report)
        s4_layout.addWidget(self.wf_copy_btn)
        self.wf_status = QLabel("")
        s4_layout.addWidget(self.wf_status)
        layout.addWidget(s4)

        layout.addStretch()
        return widget

    # ---- Helpers -----------------------------------------------------------

    @staticmethod
    def _fmt_coord(pos):
        if pos:
            return f"({pos[0]}, {pos[1]})"
        return "(not set)"

    def _show_deal(self, hands, display_widget, base72_widget):
        """Render a deal into the given display and base-72 widgets."""
        if hands is None:
            display_widget.setPlainText("")
            base72_widget.setText("")
            return

        code = deal_to_base72(hands)
        base72_widget.setText(code)

        # Build compass display
        def suit_line(cards, suit):
            ranks = sorted(
                [c[1:] for c in cards if c[0] == suit],
                key=lambda r: RANK_ORDER.get(r, 99),
            )
            return " ".join(ranks) if ranks else "\u2014"

        def hand_lines(cards):
            return [f"{SUIT_SYMBOLS[s]}  {suit_line(cards, s)}" for s in SUITS]

        n_lines = hand_lines(hands[0])
        e_lines = hand_lines(hands[1])
        s_lines = hand_lines(hands[2])
        w_lines = hand_lines(hands[3])

        pad = 28
        lines = []
        lines.append("              North")
        for ln in n_lines:
            lines.append(f"         {ln}")
        lines.append("")
        lines.append(f"{'West':<{pad}}East")
        for wl, el in zip(w_lines, e_lines):
            lines.append(f"{wl:<{pad}}{el}")
        lines.append("")
        lines.append("              South")
        for ln in s_lines:
            lines.append(f"         {ln}")

        display_widget.setPlainText("\n".join(lines))

    def _update_info(self):
        if self.hands is None:
            self.info_label.setText("")
            return
        parts = []
        for i, name in enumerate(PLAYER_NAMES):
            h = self.hands[i]
            parts.append(f"{name:6s}  {hand_hcp(h):2d} HCP   {hand_shape_str(h)}")
        self.info_label.setText("\n".join(parts))

    # ---- Source actions ----------------------------------------------------

    def _browse_pbn(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PBN / BDL file", str(FRI_DIR),
            "Bridge files (*.pbn *.bdl);;PBN files (*.pbn);;BDL files (*.bdl);;All (*)"
        )
        if path:
            self.input_field.setText(path)
            self.rb_pbn_file.setChecked(True)
            self._load_boards_from_file(path, self.board_combo)

    def _load_pbn_boards(self, path, combo):
        try:
            boards = parse_pbn_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "PBN Error", str(exc))
            return []
        combo.clear()
        if len(boards) > 1:
            combo.setVisible(True)
            for i, b in enumerate(boards):
                label = f"Board {b.get('Board', i + 1)}"
                combo.addItem(label, b)
        elif len(boards) == 1:
            combo.setVisible(False)
            combo.addItem("Board 1", boards[0])
        else:
            combo.setVisible(False)
            QMessageBox.warning(self, "PBN Error", "No boards found in file.")
        return boards

    def _load_boards_from_file(self, path, combo):
        """Load boards from either a .pbn or .bdl file."""
        if path.lower().endswith(".bdl"):
            try:
                boards = parse_bdl_file(path)
            except Exception as exc:
                QMessageBox.warning(self, "BDL Error", str(exc))
                return []
            combo.clear()
            if len(boards) > 1:
                combo.setVisible(True)
                for i, b in enumerate(boards):
                    label = f"Board {b.get('Board', i + 1)}"
                    combo.addItem(label, b)
            elif len(boards) == 1:
                combo.setVisible(False)
                combo.addItem("Board 1", boards[0])
            else:
                combo.setVisible(False)
                QMessageBox.warning(self, "BDL Error", "No deals found in BDL file.")
            return boards
        else:
            return self._load_pbn_boards(path, combo)

    def _load_deal(self):
        src = self.src_buttons.checkedId()
        try:
            if src == 0:  # Random
                hcp = self.hcp_spin.value() if self.hcp_check.isChecked() else None
                self.hands = generate_random_deal(target_hcp=hcp)
            elif src == 1:  # PBN string
                self.hands = parse_pbn_deal_string(self.input_field.text())
            elif src == 2:  # PBN / BDL file
                path = self.input_field.text()
                if not path:
                    QMessageBox.warning(self, "Error", "No file selected.")
                    return
                idx = max(0, self.board_combo.currentIndex())
                board = self.board_combo.itemData(idx)
                if board is None:
                    boards = self._load_boards_from_file(path, self.board_combo)
                    if not boards:
                        return
                    board = boards[0]
                deal_str = board.get("Deal", "")
                self.hands = parse_pbn_deal_string(deal_str)
                # Pull dealer + vulnerability out of the loaded board
                # so the harness can write them into Q-Plus matching
                # the source file. parse_bdl_file / parse_pbn_file
                # both stuff these on the board dict.
                self.set_dealer_vuln(
                    board.get("Dealer", ""),
                    board.get("Vulnerable", ""),
                )
            elif src == 3:  # Base-72
                code = self.input_field.text().strip()
                if not code:
                    QMessageBox.warning(self, "Error", "No base-72 code entered.")
                    return
                self.hands = base72_to_deal(code)
            else:
                return
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return

        self._show_deal(self.hands, self.hand_display, self.base72_display)
        self._update_info()
        self.statusBar().showMessage("Deal loaded.")

    # ---- Calibration -------------------------------------------------------

    def _on_capture(self, key, pos):
        self.calibration[key] = pos
        save_calibration(self.calibration)
        _, coord_label = self._cap_buttons[key]
        coord_label.setText(self._fmt_coord(pos))
        self.statusBar().showMessage(f"Captured {key}: {pos}")

    # ---- Enter deal --------------------------------------------------------

    def _enter_deal(self):
        self._do_enter(self.hands, "Hand Entry")

    def _do_enter(self, hands, context):
        if hands is None:
            QMessageBox.warning(self, "Error", "No deal loaded.")
            return
        result = calibration_to_positions(self.calibration)
        grid_coords, player_pos, ok_pos, clear_pos = result
        if grid_coords is None:
            QMessageBox.warning(self, "Error", "Calibration incomplete. Capture all 6 points first.")
            return

        # Optional dealer / vulnerability — passed via --dealer/--vuln
        # from bridgeIQ so the closed-room deal in Q-Plus is set up
        # under the same conditions as the open-room game.
        dv_open, dealer_positions, vuln_positions, dv_ok = \
            dealer_vuln_positions(self.calibration)

        self.enter_btn.setEnabled(False)
        self.wf_enter_btn.setEnabled(False)
        self._worker = AutomationWorker(
            hands, grid_coords, player_pos, ok_pos, clear_pos,
            dealer=self.dealer,
            vuln=self.vulnerability,
            dv_open_btn=dv_open,
            dealer_positions=dealer_positions,
            vuln_positions=vuln_positions,
            dv_ok_btn=dv_ok,
        )
        self._worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self._worker.finished.connect(self._on_automation_done)
        self._worker.start()

    def _on_automation_done(self, success, msg):
        self.enter_btn.setEnabled(True)
        self.wf_enter_btn.setEnabled(True)
        self._worker = None
        if success:
            self.statusBar().showMessage(msg)
        else:
            QMessageBox.critical(self, "Automation Error", msg)

    # ---- Workflow actions --------------------------------------------------

    def _wf_browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open source PBN / BDL file", str(FRI_DIR),
            "Bridge files (*.pbn *.bdl);;PBN files (*.pbn);;BDL files (*.bdl);;All (*)"
        )
        if not path:
            return
        self.wf_pbn_path.setText(path)
        self._source_pbn_path = path
        boards = self._load_boards_from_file(path, self.wf_board_combo)
        if boards:
            board = boards[0]
            deal_str = board.get("Deal", "")
            try:
                self.hands = parse_pbn_deal_string(deal_str)
                self._show_deal(self.hands, self.wf_hand_display, self.wf_base72)
                # Also update the main entry tab
                self._show_deal(self.hands, self.hand_display, self.base72_display)
                self._update_info()
            except ValueError as exc:
                QMessageBox.warning(self, "PBN Error", str(exc))

            # Auto-detect source game name from path
            p = Path(path)
            for name in ["wbridge5", "wBridge5", "bridgeIQ", "bridgebaron", "bb12"]:
                if name.lower() in str(p).lower():
                    idx = self.wf_game_name.findText(name.lower())
                    if idx >= 0:
                        self.wf_game_name.setCurrentIndex(idx)
                    break

    def _wf_board_changed(self, idx):
        if idx < 0:
            return
        board = self.wf_board_combo.itemData(idx)
        if board is None:
            return
        deal_str = board.get("Deal", "")
        try:
            self.hands = parse_pbn_deal_string(deal_str)
            self._show_deal(self.hands, self.wf_hand_display, self.wf_base72)
            self._show_deal(self.hands, self.hand_display, self.base72_display)
            self._update_info()
            self.set_dealer_vuln(
                board.get("Dealer", ""),
                board.get("Vulnerable", ""),
            )
        except ValueError:
            pass

    def _wf_enter_deal(self):
        self._do_enter(self.hands, "Workflow")

    def _wf_browse_log(self):
        # Look in qplus installation directory first
        start_dir = str(FRI_DIR)
        for subdir in ["WP/drive_c/games/qbridge17", "WP/drive_c/games/qbridge15"]:
            candidate = FRI_DIR / subdir
            if candidate.is_dir():
                start_dir = str(candidate)
                break
        path, _ = QFileDialog.getOpenFileName(self, "Select Q-Plus log file", start_dir, "All files (*)")
        if path:
            self.wf_log_path.setText(path)

    def _wf_autodetect_log(self):
        """Find the most recently modified file in the qplus installation directory."""
        qplus_dir = None
        for subdir in ["WP/drive_c/games/qbridge17", "WP/drive_c/games/qbridge15"]:
            candidate = FRI_DIR / subdir
            if candidate.is_dir():
                qplus_dir = candidate
                break
        if qplus_dir is None:
            QMessageBox.warning(self, "Error", "Q-Plus installation directory not found.")
            return

        # Find most recently modified file (excluding .exe, .dll, .ini)
        best = None
        best_mtime = 0
        skip_ext = {".exe", ".dll", ".ini", ".chm", ".hlp", ".bmp", ".ico"}
        for f in qplus_dir.iterdir():
            if f.is_file() and f.suffix.lower() not in skip_ext:
                mt = f.stat().st_mtime
                if mt > best_mtime:
                    best_mtime = mt
                    best = f
        if best:
            self.wf_log_path.setText(str(best))
            self.statusBar().showMessage(f"Auto-detected: {best.name}")
        else:
            QMessageBox.information(self, "Info", "No log files found in Q-Plus directory.")

    def _wf_copy_to_report(self):
        if self.hands is None:
            QMessageBox.warning(self, "Error", "No deal loaded.")
            return
        if not self._source_pbn_path:
            QMessageBox.warning(self, "Error", "No source PBN file loaded (Step 1).")
            return

        log_path = self.wf_log_path.text().strip()
        if not log_path or not Path(log_path).is_file():
            QMessageBox.warning(self, "Error", "No Q-Plus log file selected (Step 3).")
            return

        game_name = self.wf_game_name.currentText().strip()
        if not game_name:
            QMessageBox.warning(self, "Error", "Enter a source game name.")
            return

        # Find or create afterGameReport directory
        report_base = FRI_DIR / "afterGameReport"
        report_base.mkdir(exist_ok=True)

        # Look for the most recent directory matching this game name
        existing = sorted(
            (d for d in report_base.iterdir()
             if d.is_dir() and d.name.endswith(f"_{game_name}")),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        if existing:
            report_dir = existing[0]
        else:
            # Create new directory with current timestamp
            ts = datetime.now().strftime("%y%m%d_%H%M")
            report_dir = report_base / f"{ts}_{game_name}"
            report_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Convert source PBN to BDL format
            converted_text = pbn_file_to_bdl(self._source_pbn_path, source_label=game_name[:2].upper())
            src_stem = Path(self._source_pbn_path).stem
            converted_path = report_dir / f"{src_stem}.bdl"
            converted_path.write_text(converted_text, encoding="utf-8")

            # 2. Copy actual qplus log file (ensure .bdl extension)
            log_src = Path(log_path)
            if log_src.suffix.lower() == ".bdl":
                log_dest = report_dir / f"qplus_{log_src.name}"
            else:
                log_dest = report_dir / f"qplus_log_{log_src.stem}.bdl"
            shutil.copy2(str(log_src), str(log_dest))

            # 3. Also copy the original source PBN for reference
            orig_dest = report_dir / f"{src_stem}_original.pbn"
            if not orig_dest.exists():
                shutil.copy2(self._source_pbn_path, str(orig_dest))

            rel_dir = report_dir.relative_to(REPO_ROOT)
            self.wf_status.setText(f"Copied to {rel_dir}/")
            self.statusBar().showMessage(f"Files saved to {rel_dir}/")

            # 4. Trigger Claude Code annotation comparing both BDL files
            annotate_script = FRI_DIR / "claude_annotate_bridge.sh"
            annotated_path = report_dir / f"{src_stem}_annotated.bdl"
            claude_msg = ""
            if annotate_script.is_file():
                self.statusBar().showMessage("Running Claude Code bridge annotation...")
                QApplication.processEvents()
                try:
                    result = subprocess.run(
                        ["bash", str(annotate_script),
                         str(converted_path), str(log_dest), str(annotated_path)],
                        capture_output=True, text=True, timeout=300,
                    )
                    if annotated_path.is_file():
                        claude_msg = f"\n  \u2022 {annotated_path.name}  (Claude-annotated comparison)"
                    if result.stdout.strip():
                        print(result.stdout.strip())
                except (subprocess.TimeoutExpired, OSError) as e:
                    print(f"Claude annotation error: {e}")

            QMessageBox.information(
                self, "Success",
                f"Saved to {rel_dir}/:\n"
                f"  \u2022 {converted_path.name}  (human play BDL)\n"
                f"  \u2022 {log_dest.name}  (Q-Plus computer play BDL)\n"
                f"  \u2022 {orig_dest.name}  (original PBN)"
                f"{claude_msg}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to copy files:\n{exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    # Parse --source and --game before QApplication consumes Qt args
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", default="", help="Pre-load PBN/BDL into Comparison Workflow")
    parser.add_argument("--game", default="", help="Source game name (wbridge5, bb12, etc.)")
    parser.add_argument("--base72", default="", help="Pre-load a deal by base-72 code")
    parser.add_argument("--dealer", default="", help="Dealer seat (N / E / S / W)")
    parser.add_argument("--vuln", default="", help="Vulnerability (None / NS / EW / Both)")
    parser.add_argument("--no-launch-qplus", action="store_true",
                        help="Don't auto-launch Q-Plus (caller has already launched it)")
    parser.add_argument("--closed-room", action="store_true",
                        help="Open the Closed Room tab (biq E/W vs Q-Plus "
                             "N/S over Q-NET) and walk through a live match")
    known, remaining = parser.parse_known_args()

    app = QApplication(remaining)
    app.setStyle("Fusion")

    window = BridgeHarness(launch_qplus=not known.no_launch_qplus,
                           closed_room=known.closed_room)
    window.show()

    if known.source:
        window.load_source(known.source, game_name=known.game)
    if known.base72:
        window.load_base72(known.base72)
    if known.dealer or known.vuln:
        window.set_dealer_vuln(known.dealer, known.vuln)
    # load_base72 forces the Hand Entry tab forward; re-assert the Closed
    # Room tab last so --closed-room always lands the user on the wizard.
    if known.closed_room:
        window.show_closed_room_tab()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
