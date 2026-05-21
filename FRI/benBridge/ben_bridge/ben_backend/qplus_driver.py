"""Q-Plus diff oracle: feed deals in via OWN-DEALS .BDE, capture BDL output.

Q-Plus has no Bridge Table Manager protocol — its networking is
Q-NET.EXE, a proprietary peer-to-peer over TCP/DDE that's
expensive to reverse-engineer. The practical alternative is file
injection:

  1. Write a multi-deal `.BDE` file into Q-Plus's
     `DATA/OWN-DEALS/` directory.
  2. User loads it (Own deals → Open → BB_DIFF.BDE) and steps
     through each deal letting Q-Plus auto-play.
  3. Q-Plus writes one `log-NNN.bdl` per played deal into
     `DATA/LOG/`.
  4. We snapshot LOG/ before, poll for new BDLs after each
     deal completes, and parse them through `bdl_reader` to
     extract the auction for diffing.

This module provides the file I/O and polling helpers; the
orchestrator lives in `tools/qplus_diff.py`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .models import BoardState, Hand, Card, Rank, Seat, Suit, Vulnerability


# Q-Plus DATA tree layout under the project's Wine prefix.
def qplus_install_dir() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        for sub in ("WP/drive_c/games/qbridge17",
                    "WP/drive_c/games/qbridge15"):
            cand = parent / sub
            if cand.is_dir():
                return cand
    return None


def qplus_own_deals_dir() -> Optional[Path]:
    d = qplus_install_dir()
    return (d / "DATA" / "OWN-DEALS") if d else None


def qplus_log_dir() -> Optional[Path]:
    d = qplus_install_dir()
    return (d / "DATA" / "LOG") if d else None


# ---------------------------------------------------------------------------
# Multi-deal BDE writer
# ---------------------------------------------------------------------------


BDE_SEPARATOR = "*********************************************************"


_DEALER_TO_BDE = {"N": "North", "E": "East", "S": "South", "W": "West"}
_VULN_TO_BDE = {
    Vulnerability.NONE: "---",
    Vulnerability.NS:   "N/S",
    Vulnerability.EW:   "E/W",
    Vulnerability.BOTH: "All",
}


def _rank_char(rank: Rank) -> str:
    return {Rank.ACE: "A", Rank.KING: "K", Rank.QUEEN: "Q",
            Rank.JACK: "J", Rank.TEN: "T", Rank.NINE: "9",
            Rank.EIGHT: "8", Rank.SEVEN: "7", Rank.SIX: "6",
            Rank.FIVE: "5", Rank.FOUR: "4", Rank.THREE: "3",
            Rank.TWO: "2"}[rank]


def _suit_line(cards_of_suit: Iterable[Card]) -> str:
    """Render one suit's holding as 'A K Q J' / '-' for void."""
    ranks = sorted((c.rank.value for c in cards_of_suit))
    if not ranks:
        return "-"
    return " ".join(_rank_char(Rank(v)) for v in ranks)


def _seat_suits(hand: Hand):
    by_suit = {s: [] for s in (Suit.SPADES, Suit.HEARTS,
                               Suit.DIAMONDS, Suit.CLUBS)}
    for c in hand.cards:
        by_suit[c.suit].append(c)
    return by_suit


def _format_one_deal(board: BoardState, label: str) -> str:
    """Render a single deal block in Q-Plus BDE format."""
    suits = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
    n_s = _seat_suits(board.hands[Seat.NORTH])
    e_s = _seat_suits(board.hands[Seat.EAST])
    s_s = _seat_suits(board.hands[Seat.SOUTH])
    w_s = _seat_suits(board.hands[Seat.WEST])
    dealer = _DEALER_TO_BDE[board.dealer.to_char()]
    vuln = _VULN_TO_BDE[board.vulnerability]
    lines: List[str] = []
    lines.append(f"Deal         :   {label}")
    lines.append(f"Dealer       :   {dealer}")
    lines.append(f"Vuln         :   {vuln}")
    lines.append(f"Cards        :                  {_suit_line(n_s[suits[0]])}")
    for su in suits[1:]:
        lines.append(f"             :                  {_suit_line(n_s[su])}")
    for su in suits:
        wcol = _suit_line(w_s[su])
        ecol = _suit_line(e_s[su])
        lines.append(f"             :   {wcol:<30}{ecol}")
    for su in suits:
        lines.append(f"             :                  {_suit_line(s_s[su])}")
    return "\n".join(lines) + "\n"


def write_multi_deal_bde(
        boards: List[BoardState],
        out_path: Path,
        *,
        description: str = "ben_bridge diff batch",
) -> Path:
    """Write `boards` as a multi-deal BDE file Q-Plus can load.

    File format matches Q-Plus's shipped EXAMPLE.BDE — one DOCTYPE
    line up top, one description, then deal blocks separated by
    a row of asterisks. Returns the absolute path written.
    """
    parts: List[str] = []
    parts.append("DOCTYPE: BDL 7.1")
    parts.append(f'.description.eng = "{description}"')
    parts.append("")
    for i, b in enumerate(boards, start=1):
        label = f"BB-diff-{i:03d}"
        parts.append(_format_one_deal(b, label))
        parts.append(BDE_SEPARATOR)
        parts.append("")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="latin-1")
    return out_path


# ---------------------------------------------------------------------------
# BDL output polling
# ---------------------------------------------------------------------------


def snapshot_log_files(log_dir: Path) -> set:
    """Set of currently-present .bdl files in `log_dir`."""
    if not log_dir.is_dir():
        return set()
    return {p.name for p in log_dir.glob("*.bdl")}


def wait_for_new_bdls(
        log_dir: Path,
        previous: set,
        expected: int,
        *,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
) -> List[Path]:
    """Block until `expected` new BDL files appear in `log_dir`.

    Returns the new files sorted by mtime (oldest first), so the
    order matches Q-Plus's play order. Raises TimeoutError if
    fewer than `expected` files arrive before `timeout`.
    """
    deadline = time.time() + timeout
    while True:
        current = snapshot_log_files(log_dir)
        new = sorted(current - previous,
                     key=lambda n: (log_dir / n).stat().st_mtime)
        if len(new) >= expected:
            return [log_dir / n for n in new[:expected]]
        if time.time() > deadline:
            raise TimeoutError(
                f"Q-Plus produced only {len(new)} of {expected} expected "
                f"BDL files within {timeout}s")
        time.sleep(poll_interval)
