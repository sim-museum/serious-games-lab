"""Direct ctypes binding to libdds.so.0 — the Double-Dummy Solver.

Replaces the third-party `ddsolver` Python wrapper that previously
lived under `ben/src/ddsolver/`. We load `libdds.so.0` (provided by
the Ubuntu `libdds0` package) and call its C entry points directly.

Public surface (matches the call sites in `backend.engine`):

  ddTableDealPBN, ddTableResults   — ctypes Structures
  CalcDDtablePBN(deal, table_ptr)  — fills a 5x4 trick table
  get_error_message(code)          — DDS error text
  DDSolver()                       — high-level helper:
      .version() -> str
      .solve(strain_i, leader, current_trick_52, sample_pbns,
             solutions=3) -> Dict[card52, List[tricks_per_sample]]

Encoding conventions:
  Suit (DDS native):  0=S, 1=H, 2=D, 3=C, 4=NT
  Seat (DDS native):  0=N, 1=E, 2=S, 3=W
  Rank (DDS native):  2..14 (2=two .. 14=ace)
  card52              suit * 13 + (Rank.ACE=0 .. Rank.TWO=12)
                      so DDS rank == 14 - (card52 % 13)
  strain_i (BEN-style, kept for caller compatibility):
                      1=S, 2=H, 3=D, 4=C, 5=NT  →  DDS trump = strain_i - 1
"""

import atexit
import ctypes
from ctypes import c_int, c_char, Structure, POINTER
from ctypes.util import find_library
from typing import Dict, List


# ---------- Library load ----------

_lib_path = find_library("dds") or "libdds.so.0"
_dds = ctypes.CDLL(_lib_path)


# ---------- C struct mirrors (from libdds dll.h) ----------

class _DealPBN(Structure):
    _fields_ = [
        ("trump", c_int),
        ("first", c_int),
        ("currentTrickSuit", c_int * 3),
        ("currentTrickRank", c_int * 3),
        ("remainCards", c_char * 80),
    ]


class _FutureTricks(Structure):
    _fields_ = [
        ("nodes", c_int),
        ("cards", c_int),
        ("suit", c_int * 13),
        ("rank", c_int * 13),
        ("equals", c_int * 13),
        ("score", c_int * 13),
    ]


class ddTableDealPBN(Structure):
    _fields_ = [("cards", c_char * 80)]


class ddTableResults(Structure):
    # libdds: int resTable[DDS_STRAINS][DDS_HANDS] = [5][4]
    # Indexed as resTable[strain][declarer] where
    #   strain ∈ {0=S, 1=H, 2=D, 3=C, 4=NT}
    #   declarer ∈ {0=N, 1=E, 2=S, 3=W}
    _fields_ = [("resTable", (c_int * 4) * 5)]


# ---------- Function prototypes ----------

_dds.SolveBoardPBN.argtypes = [
    _DealPBN, c_int, c_int, c_int, POINTER(_FutureTricks), c_int
]
_dds.SolveBoardPBN.restype = c_int

_dds.CalcDDtablePBN.argtypes = [ddTableDealPBN, POINTER(ddTableResults)]
_dds.CalcDDtablePBN.restype = c_int

_dds.ErrorMessage.argtypes = [c_int, c_char * 80]
_dds.ErrorMessage.restype = None

_dds.SetMaxThreads.argtypes = [c_int]
_dds.SetMaxThreads.restype = None

_dds.FreeMemory.argtypes = []
_dds.FreeMemory.restype = None

# Auto-detect threads once on import. 0 = let libdds choose.
_dds.SetMaxThreads(0)

# libdds spawns persistent worker threads holding per-thread
# transposition tables. They outlive Python finalization and, after
# ctypes unloads the lib, dereference freed state — segfault at exit.
# `FreeMemory` releases the pool cleanly. Registered with `atexit`
# so it runs before ctypes / dlclose.
atexit.register(_dds.FreeMemory)


# ---------- Module-level helpers (drop-ins for the old `dds` module) ----------

def CalcDDtablePBN(deal: ddTableDealPBN, table_ptr) -> int:
    """Compute the 5x4 double-dummy table.

    `deal.cards` must be a PBN deal string (`b"N:..."`).
    On success returns 1; on error returns a libdds error code
    (use `get_error_message` to format).
    """
    return _dds.CalcDDtablePBN(deal, table_ptr)


def get_error_message(code: int) -> str:
    buf = (c_char * 80)()
    _dds.ErrorMessage(c_int(code), buf)
    return buf.value.decode("ascii", errors="replace")


# ---------- High-level DDSolver ----------

def _c52_to_dds(c52: int):
    return (c52 // 13, 14 - (c52 % 13))


def _dds_to_c52(suit: int, rank: int) -> int:
    return suit * 13 + (14 - rank)


class DDSolver:
    """Per-call solver. Stateless wrapper over `SolveBoardPBN`.

    Constructor accepts a `dds_mode` argument for source compatibility
    with the old upstream wrapper, but it has no effect — libdds
    picks its own search strategy.
    """

    def __init__(self, dds_mode: int = 0):
        self.dds_mode = dds_mode

    def version(self) -> str:
        return "libdds.so.0 (system)"

    def solve(self, strain_i: int, leader: int,
              current_trick_52: List[int],
              sample_pbns: List[str],
              solutions: int = 3) -> Dict[int, List[int]]:
        """Solve a card-play position across Monte-Carlo samples.

        Args:
            strain_i: trump (BEN convention, 1-based — 1=S..5=NT).
            leader: 0=N, 1=E, 2=S, 3=W — who led the current trick.
            current_trick_52: cards already played in the current
                trick, in lead order (length 0..3).
            sample_pbns: PBN deal strings ("N:AKQ.JT9.876.5432 ...")
                where each hand reflects only the cards still in
                play (already-played cards stripped).
            solutions: SolveBoard `solutions` param —
                1 = best card only; 2 = all best-scoring cards;
                3 = every legal card with its trick count.

        Returns dict {card52: [tricks_per_sample]}. Trick counts are
        for the side currently on play.
        """
        trump = strain_i - 1   # BEN 1-based → DDS 0-based

        cur_suit = [0, 0, 0]
        cur_rank = [0, 0, 0]
        for i, c52 in enumerate(current_trick_52[:3]):
            s, r = _c52_to_dds(c52)
            cur_suit[i] = s
            cur_rank[i] = r

        results: Dict[int, List[int]] = {}
        for pbn in sample_pbns:
            dl = _DealPBN()
            dl.trump = trump
            dl.first = leader
            dl.currentTrickSuit = (c_int * 3)(*cur_suit)
            dl.currentTrickRank = (c_int * 3)(*cur_rank)
            dl.remainCards = pbn.encode("utf-8")

            fut = _FutureTricks()
            target = -1   # -1 = find max tricks
            mode = 0
            rc = _dds.SolveBoardPBN(
                dl, target, solutions, mode,
                ctypes.byref(fut), 0
            )
            if rc != 1:
                continue

            for i in range(fut.cards):
                s = fut.suit[i]
                r = fut.rank[i]
                score = fut.score[i]
                c52 = _dds_to_c52(s, r)
                results.setdefault(c52, []).append(score)
                # Expand the "equals" bitmap — bits 2..14 mark other
                # ranks the same player holds that are touching this
                # one (e.g. K returned with A and Q set).
                eq = fut.equals[i]
                bit = 2
                while bit <= 14:
                    if eq & (1 << bit):
                        results.setdefault(
                            _dds_to_c52(s, bit), []).append(score)
                    bit += 1

        return results

    def solve_dd_table(self, pbn: str) -> Dict[str, Dict[str, int]]:
        """Compute the full 5x4 double-dummy table for a complete deal.

        `pbn` is a deal string ("N:AKQ.JT9.876.5432 ..."). Returns
        a nested dict declarer → strain → tricks.
        """
        deal = ddTableDealPBN()
        deal.cards = pbn.encode("utf-8")
        table = ddTableResults()
        rc = _dds.CalcDDtablePBN(deal, ctypes.byref(table))
        if rc != 1:
            raise RuntimeError(
                f"CalcDDtablePBN failed: {get_error_message(rc)}")

        seat_map = ["N", "E", "S", "W"]
        strain_map = ["S", "H", "D", "C", "NT"]
        out: Dict[str, Dict[str, int]] = {s: {} for s in seat_map}
        for st_i, st in enumerate(strain_map):
            for se_i, se in enumerate(seat_map):
                out[se][st] = int(table.resTable[st_i][se_i])
        return out
