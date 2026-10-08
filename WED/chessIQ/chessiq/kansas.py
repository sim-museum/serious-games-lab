"""What Kramnik rules change (EPIC KS, "not in Kansas"): helpers shared by the self-capture specialists, the Kansas
moments in Post-Game Analysis, the coach and the lessons.

The comparison at the heart of it: Fairy-Stockfish searches a position under Kramnik rules (`kramnik`) and under the
same rules without self-capture (`kramniknosc`, engine/kramnik.ini). A move that is better with self-capture than
without gains from Kramnik rules; docs/SELF_CAPTURE_CENSUS.md measured how often that matters (5% of positions).
The off-rules engine is always given a FEN, never the move list: earlier self-captures are illegal there."""
from . import engine as E

CAP = 1000                      # centipawns: beyond this (or a mate) scores are compared as equal


def cap(cp):
    return max(-CAP, min(CAP, cp))


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def to_fen(b, turn, ep=None, half=0, full=1):
    rows = []
    for r in range(8):
        s, gap = "", 0
        for c in range(8):
            p = b[r * 8 + c]
            if not p:
                gap += 1
                continue
            if gap:
                s, gap = s + str(gap), 0
            s += p[1].upper() if p[0] == "w" else p[1]
        rows.append(s + (str(gap) if gap else ""))
    return "%s %s - %s %d %d" % ("/".join(rows), turn, E.sqname(ep) if ep is not None else "-", half, full)


def from_fen(fen):
    """(board, turn, ep, half, full) from a FEN (castling rights are ignored: there is no castling)."""
    f = fen.split()
    b, i = [None] * 64, 0
    for ch in f[0]:
        if ch == "/":
            continue
        if ch.isdigit():
            i += int(ch)
        else:
            b[i] = ("w" if ch.isupper() else "b") + ch.lower()
            i += 1
    ep = None if len(f) < 4 or f[3] == "-" else (8 - int(f[3][1])) * 8 + E.FILES.index(f[3][0])
    half = int(f[4]) if len(f) > 4 else 0
    full = int(f[5]) if len(f) > 5 else 1
    return b, f[1], ep, half, full


START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"


def find(b, turn, ep, u):
    return next((m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u), None)


def replay(moves, start=START):
    """The position after `moves` (UCI) from `start`: (board, turn, ep, half, full). Raises ValueError on an illegal
    move."""
    b, turn, ep, half, full = from_fen(start)
    for u in moves:
        m = find(b, turn, ep, u)
        if m is None:
            raise ValueError("illegal move " + u)
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        full += turn == "b"
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return b, turn, ep, half, full


def fen_after(moves, start=START):
    return to_fen(*replay(moves, start))


def is_self_capture(b, turn, u):
    """Is the UCI move u, by `turn` on board b, a self-capture? (The target holds one of the mover's own pieces.)"""
    frm = (8 - int(u[1])) * 8 + E.FILES.index(u[0])
    to = (8 - int(u[3])) * 8 + E.FILES.index(u[2])
    return bool(b[frm] and b[to] and b[to][0] == turn)
