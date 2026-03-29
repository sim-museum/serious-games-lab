#!/usr/bin/env python3
"""
Bridge Harness — PyQt5 GUI for Q-Plus Bridge hand entry and comparison workflow.

Features:
  - Enter hands from PBN files, PBN strings, base-72 Pavlicek codes, or random deals
  - Always displays base-72 hand code for the current deal
  - Automates hand entry into Q-Plus Bridge via mouse control
  - Workflow: play in another program (e.g. wbridge5) → enter same hand into qplus
    → collect qplus log → convert & copy to afterGamesReport
"""

import json
import os
import re
import random
import shutil
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
# Base-72 / Pavlicek encoding  (standalone — no dependency on ben_bridge)
# ---------------------------------------------------------------------------
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
    """Run hand-entry mouse automation in a background thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, hands, grid_coords, player_positions, ok_pos, clear_pos):
        super().__init__()
        self.hands = hands
        self.grid_coords = grid_coords
        self.player_positions = player_positions
        self.ok_pos = ok_pos
        self.clear_pos = clear_pos

    def run(self):
        try:
            self.progress.emit("Clicking Clear all...")
            time.sleep(2)
            pyautogui.moveTo(*self.clear_pos, duration=0.2)
            pyautogui.click()
            time.sleep(0.5)

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

            self.progress.emit("Clicking OK...")
            pyautogui.moveTo(*self.ok_pos, duration=0.2)
            pyautogui.click()
            self.finished.emit(True, "Hand entered successfully.")
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
}


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
    """Derive grid_coords and player_positions from calibration data."""
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bridge Harness \u2014 Q-Plus Bridge")
        self.setMinimumSize(780, 700)

        self.hands = None          # [N, E, S, W] card lists
        self.calibration = load_calibration()
        self._worker = None
        self._source_pbn_path = None  # for workflow

        tabs = QTabWidget()
        tabs.addTab(self._build_entry_tab(), "Hand Entry")
        tabs.addTab(self._build_workflow_tab(), "Comparison Workflow")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage("Ready")

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

        layout.addLayout(left, stretch=1)

        # Right: controls
        right = QVBoxLayout()

        # Source selection
        src_group = QGroupBox("Source")
        src_layout = QVBoxLayout(src_group)
        self.src_buttons = QButtonGroup(self)
        self.rb_random = QRadioButton("Random deal")
        self.rb_pbn_str = QRadioButton("PBN string")
        self.rb_pbn_file = QRadioButton("PBN file")
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

        self.browse_btn = QPushButton("Browse PBN file...")
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

        # Calibration
        cal_group = QGroupBox("Q-Plus Pickboard Calibration")
        cal_layout = QFormLayout(cal_group)
        self._cap_buttons = {}
        for key, label in [
            ("north_chk", "North checkbox"),
            ("west_chk", "West checkbox"),
            ("grid_tl", "Ace of Spades (top-left)"),
            ("grid_br", "Two of Clubs (bottom-right)"),
            ("clear_btn", "Clear all button"),
            ("ok_btn", "OK button"),
        ]:
            btn = CaptureButton(label)
            btn.captured.connect(lambda pos, k=key: self._on_capture(k, pos))
            coord_label = QLabel(self._fmt_coord(self.calibration.get(key)))
            self._cap_buttons[key] = (btn, coord_label)
            row = QHBoxLayout()
            row.addWidget(btn)
            row.addWidget(coord_label)
            cal_layout.addRow(row)
        right.addWidget(cal_group)

        # Enter button
        self.enter_btn = QPushButton("Enter Deal into Q-Plus")
        self.enter_btn.setStyleSheet("font-weight: bold; padding: 8px;")
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
            "The source PBN and Q-Plus results are collected into afterGamesReport."
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
        s4 = QGroupBox("Step 4 — Convert & copy to afterGamesReport")
        s4_layout = QVBoxLayout(s4)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Source game:"))
        self.wf_game_name = QComboBox()
        self.wf_game_name.setEditable(True)
        self.wf_game_name.addItems(["wbridge5", "benbridge", "bb12", "tenace"])
        name_row.addWidget(self.wf_game_name, stretch=1)
        s4_layout.addLayout(name_row)

        self.wf_copy_btn = QPushButton("Convert PBN & copy both files to afterGamesReport")
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
        path, _ = QFileDialog.getOpenFileName(self, "Open PBN file", str(FRI_DIR), "PBN files (*.pbn);;All (*)")
        if path:
            self.input_field.setText(path)
            self.rb_pbn_file.setChecked(True)
            self._load_pbn_boards(path, self.board_combo)

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

    def _load_deal(self):
        src = self.src_buttons.checkedId()
        try:
            if src == 0:  # Random
                hcp = self.hcp_spin.value() if self.hcp_check.isChecked() else None
                self.hands = generate_random_deal(target_hcp=hcp)
            elif src == 1:  # PBN string
                self.hands = parse_pbn_deal_string(self.input_field.text())
            elif src == 2:  # PBN file
                path = self.input_field.text()
                if not path:
                    QMessageBox.warning(self, "Error", "No PBN file selected.")
                    return
                idx = max(0, self.board_combo.currentIndex())
                board = self.board_combo.itemData(idx)
                if board is None:
                    boards = self._load_pbn_boards(path, self.board_combo)
                    if not boards:
                        return
                    board = boards[0]
                deal_str = board.get("Deal", "")
                self.hands = parse_pbn_deal_string(deal_str)
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

        self.enter_btn.setEnabled(False)
        self.wf_enter_btn.setEnabled(False)
        self._worker = AutomationWorker(hands, grid_coords, player_pos, ok_pos, clear_pos)
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
            self, "Open source PBN file", str(FRI_DIR), "PBN files (*.pbn);;All (*)"
        )
        if not path:
            return
        self.wf_pbn_path.setText(path)
        self._source_pbn_path = path
        boards = self._load_pbn_boards(path, self.wf_board_combo)
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
            for name in ["wbridge5", "wBridge5", "benbridge", "bridgebaron", "bb12"]:
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

        # Find or create afterGamesReport directory
        report_base = FRI_DIR / "afterGamesReport"
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

            # 2. Copy actual qplus log file
            log_src = Path(log_path)
            log_dest = report_dir / f"qplus_log_{log_src.name}"
            shutil.copy2(str(log_src), str(log_dest))

            # 3. Also copy the original source PBN for reference
            orig_dest = report_dir / f"{src_stem}_original.pbn"
            if not orig_dest.exists():
                shutil.copy2(self._source_pbn_path, str(orig_dest))

            rel_dir = report_dir.relative_to(REPO_ROOT)
            self.wf_status.setText(f"Copied to {rel_dir}/")
            self.statusBar().showMessage(f"Files saved to {rel_dir}/")
            QMessageBox.information(
                self, "Success",
                f"Saved to {rel_dir}/:\n"
                f"  \u2022 {converted_path.name}  (PBN converted to BDL format)\n"
                f"  \u2022 {log_dest.name}  (Q-Plus log)\n"
                f"  \u2022 {orig_dest.name}  (original PBN)",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to copy files:\n{exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = BridgeHarness()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
