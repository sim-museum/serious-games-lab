"""Chessmaster opening books (*.OBK), read from the player's installation (EPIC CM, sprint CM-10).

Format, decoded 2026-10-06 (every entry of WaitzkinJ, BirdH, AlekhineA and CMX consumed, none illegal):
  "BOO!" + uint32 entry count + uint32 0, then 2 bytes per move, a depth-first tree:
    byte 0: bits 0-5 from-square (a1 = 0), bit 6 CLEAR = another sibling follows this move's subtree,
            bit 7 = this move ends the line
    byte 1: bits 0-5 to-square; bits 6-7 annotations (unused here)
  After a line ends, play resumes at the most recent move that announced a following sibling.
Kramnik chess has no castling, so a line is cut at its first castling move (it stays legal Kramnik chess up to there).
Result: {moves so far (SAN, space separated): {next move: number of book lines through it}}, chessIQ's book format.
Some books (Depth6.OBK, the generic book of weaker personalities) use another format: read_obk returns None for
them and the grandmaster book is used instead.
"""
import os
import struct

from . import engine as E
from .game import strip_checks


def _square(s):                      # Chessmaster a1=0 -> chessIQ index (rank 8 first)
    return (7 - s // 8) * 8 + s % 8


def read_obk(path, max_plies=24):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"BOO!":
        return None
    n = struct.unpack_from("<I", data, 4)[0]
    book = {}

    def count(line):                  # one more book line passes through every move of this line
        for k in range(len(line)):
            node = book.setdefault(" ".join(line[:k]), {})
            node[line[k]] = node.get(line[k], 0) + 1
    start = (E.init_board(), "w", None, [], False)
    cur, pending = start, []
    for i in range(n):
        b0, b1 = data[12 + 2 * i], data[13 + 2 * i]
        board, turn, ep, line, dead = cur
        if not b0 & 0x40:
            pending.append(cur)
        frm, to = _square(b0 & 63), _square(b1 & 63)
        if not dead and len(line) < max_plies:
            m = next((m for m in E.legal_moves(board, turn, ep) if m.frm == frm and m.to == to and m.kind != "self"
                      and m.promo in (None, "q")), None)
            if m is None:                # a castling move (illegal in Kramnik chess): the rest of this line is cut
                cur = (board, turn, ep, line, True)
            else:
                san = strip_checks(E.san_of(board, m, ep))
                cur = (E.apply_move(board, m), E.opp(turn), E.ep_after(m), line + [san], False)
        else:
            cur = (board, turn, ep, line, True)
        if b0 & 0x80:
            count(cur[3])                # the line as played (cut at castling)
            if not pending:
                break
            cur = pending.pop()
    return book


def find_book(directory, name):
    """The book file named in a personality (case-insensitive, as Windows found it), or None."""
    d = os.path.join(directory, "Data", "Opening Books")
    if not name or not os.path.isdir(d):
        return None
    for f in os.listdir(d):
        if f.lower() == name.lower():
            return os.path.join(d, f)
    return None
