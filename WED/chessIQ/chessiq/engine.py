"""Kramnik chess engine: standard chess MINUS castling, PLUS self-capture (capture anything but your own king).

A faithful port of the engine in WED/kramnik_chess.html (the gold): same move-generation order, same evaluation,
same search, same self-capture drive. tests/test_parity.py runs the original JavaScript under node and requires
identical perft counts, best moves, scores and node counts, so this file must not drift from it.

Board: list of 64. index = row*8 + col; row 0 = rank 8 (top), col 0 = file a.
Piece: a 2-char string, colour then type -- 'wp', 'bk', ... -- or None.
"""
import time

GLYPH = {"w": {"k": "♔", "q": "♕", "r": "♖", "b": "♗", "n": "♘", "p": "♙"},
         "b": {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}}
VAL = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}
KN = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
KG = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))
ORTH = ((-1, 0), (1, 0), (0, -1), (0, 1))
FILES = "abcdefgh"


def opp(c):
    return "b" if c == "w" else "w"


def inb(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def sqname(i):
    return FILES[i & 7] + str(8 - (i >> 3))


class Move:
    """kind: 'move' | 'enemy' (capture an enemy piece) | 'self' (capture your own) | 'ep'."""
    __slots__ = ("frm", "to", "kind", "promo", "ep", "dbl", "s", "v")

    def __init__(self, frm, to, kind="move", promo=None, ep=None, dbl=None):
        self.frm, self.to, self.kind, self.promo, self.ep, self.dbl = frm, to, kind, promo, ep, dbl
        self.s = 0
        self.v = None          # root score, set by best_move (the UI judges draw offers by it)

    def same(self, o):
        return o is not None and self.frm == o.frm and self.to == o.to and self.promo == o.promo

    def __repr__(self):
        return "Move(%s%s%s %s)" % (sqname(self.frm), sqname(self.to), self.promo or "", self.kind)


def _ray(sq, dr, dc):
    r, c, out = (sq >> 3) + dr, (sq & 7) + dc, []
    while inb(r, c):
        out.append(r * 8 + c)
        r += dr; c += dc
    return tuple(out)


def _jumps(sq, deltas):
    r, c = sq >> 3, sq & 7
    return tuple((r + dr) * 8 + c + dc for dr, dc in deltas if inb(r + dr, c + dc))


# precomputed geometry, each in the gold's direction order (generation order is part of parity)
DIAG_RAYS = [tuple(_ray(s, dr, dc) for dr, dc in DIAG) for s in range(64)]
ORTH_RAYS = [tuple(_ray(s, dr, dc) for dr, dc in ORTH) for s in range(64)]
QUEEN_RAYS = [DIAG_RAYS[s] + ORTH_RAYS[s] for s in range(64)]
KNIGHT_SQ = [_jumps(s, KN) for s in range(64)]
KING_SQ = [_jumps(s, KG) for s in range(64)]
# PAWN_FROM[by][sq]: where a `by` pawn must stand to attack sq
PAWN_FROM = {"w": [_jumps(s, ((1, -1), (1, 1))) for s in range(64)],
             "b": [_jumps(s, ((-1, -1), (-1, 1))) for s in range(64)]}


def init_board():
    b = [None] * 64
    back = "rnbqkbnr"
    for c in range(8):
        b[c] = "b" + back[c]
        b[8 + c] = "bp"
        b[48 + c] = "wp"
        b[56 + c] = "w" + back[c]
    return b


def attacked(b, sq, by):
    """Is square sq attacked by colour `by`? (normal attack rules; self-capture is irrelevant to checks)"""
    p = by + "p"
    for f in PAWN_FROM[by][sq]:
        if b[f] == p:
            return True
    p = by + "n"
    for f in KNIGHT_SQ[sq]:
        if b[f] == p:
            return True
    p = by + "k"
    for f in KING_SQ[sq]:
        if b[f] == p:
            return True
    bb, bq, br = by + "b", by + "q", by + "r"
    for ray in DIAG_RAYS[sq]:
        for f in ray:
            q = b[f]
            if q:
                if q == bb or q == bq:
                    return True
                break
    for ray in ORTH_RAYS[sq]:
        for f in ray:
            q = b[f]
            if q:
                if q == br or q == bq:
                    return True
                break
    return False


def king_sq(b, color):
    k = color + "k"
    for i in range(64):
        if b[i] == k:
            return i
    return -1


def in_check(b, color):
    k = king_sq(b, color)
    return k >= 0 and attacked(b, k, opp(color))


def pos_key(b, turn, ep):
    """Repetition key: pieces + side to move + ep square, the ep square only if a pawn of the side to move can take."""
    s = turn
    if ep is not None:
        r, c = ep >> 3, ep & 7
        pr = r + 1 if turn == "w" else r - 1
        for dc in (-1, 1):
            if inb(pr, c + dc) and b[pr * 8 + c + dc] == turn + "p":
                s += str(ep)
                break
    return s + "".join(p if p else "-" for p in b)


def insufficient_material(b):
    """K vs K, K+minor vs K, K+B vs K+B with same-coloured bishops (self-capture adds no mating power)."""
    minors = {"w": [], "b": []}
    for i in range(64):
        p = b[i]
        if not p or p[1] == "k":
            continue
        if p[1] == "n":
            minors[p[0]].append(-1)
        elif p[1] == "b":
            minors[p[0]].append(((i >> 3) + (i & 7)) & 1)
        else:
            return False
    n = len(minors["w"]) + len(minors["b"])
    if n <= 1:
        return True
    return (len(minors["w"]) == 1 and len(minors["b"]) == 1 and minors["w"][0] >= 0 and minors["b"][0] >= 0
            and minors["w"][0] == minors["b"][0])


def _push_pawn(moves, frm, to, promo, kind):
    if promo:
        for t in "qrbn":
            moves.append(Move(frm, to, kind, promo=t))
    else:
        moves.append(Move(frm, to, kind))


def pseudo_moves(b, color, ep):
    moves = []

    def target(frm, to):
        t = b[to]
        if not t:
            moves.append(Move(frm, to, "move"))
            return False
        if t[0] != color:
            moves.append(Move(frm, to, "enemy"))           # capture enemy
        elif t[1] != "k":
            moves.append(Move(frm, to, "self"))            # self-capture (not the king)
        return True                                        # own king blocks

    def rays(frm, table):
        for ray in table[frm]:
            for to in ray:
                if target(frm, to):
                    break

    for frm in range(64):
        p = b[frm]
        if not p or p[0] != color:
            continue
        r, c, t = frm >> 3, frm & 7, p[1]
        if t == "p":
            d = -1 if color == "w" else 1
            start_r, promo_r = (6, 0) if color == "w" else (1, 7)
            if inb(r + d, c) and not b[(r + d) * 8 + c]:
                _push_pawn(moves, frm, (r + d) * 8 + c, r + d == promo_r, "move")
                if r == start_r and not b[(r + 2 * d) * 8 + c]:
                    moves.append(Move(frm, (r + 2 * d) * 8 + c, "move", dbl=(r + d) * 8 + c))
            for dc in (-1, 1):
                if not inb(r + d, c + dc):
                    continue
                to = (r + d) * 8 + c + dc
                q = b[to]
                if q:
                    if q[0] != color:
                        _push_pawn(moves, frm, to, r + d == promo_r, "enemy")
                    elif q[1] != "k":
                        _push_pawn(moves, frm, to, r + d == promo_r, "self")
                elif ep is not None and to == ep:
                    moves.append(Move(frm, to, "ep", ep=r * 8 + c + dc))
        elif t == "n":
            for to in KNIGHT_SQ[frm]:
                target(frm, to)
        elif t == "k":                                     # NO castling
            for to in KING_SQ[frm]:
                target(frm, to)
        elif t == "b":
            rays(frm, DIAG_RAYS)
        elif t == "r":
            rays(frm, ORTH_RAYS)
        else:
            rays(frm, QUEEN_RAYS)
    return moves


def apply_move(b, m):
    nb = b[:]
    p = nb[m.frm]
    nb[m.to] = p[0] + m.promo if m.promo else p
    nb[m.frm] = None
    if m.kind == "ep":
        nb[m.ep] = None
    return nb


def ep_after(m):
    return m.dbl


def pinned(b, ks, color):
    """Squares of `color`'s pieces pinned to its king at ks (the only non-king pieces whose moves can expose it)."""
    out = set()
    them = opp(color)
    for table, kinds in ((DIAG_RAYS, "bq"), (ORTH_RAYS, "rq")):
        for ray in table[ks]:
            mine = -1
            for f in ray:
                q = b[f]
                if not q:
                    continue
                if q[0] == color:
                    if mine >= 0:
                        break
                    mine = f
                else:
                    if mine >= 0 and q[1] in kinds:
                        out.add(mine)
                    break
    return out


def legal_moves(b, color, ep):
    """The gold tests every pseudo-legal move for leaving the king in check. When not in check, only king moves,
    en passant and moves of pinned pieces can do that, so only those are tested: the same list in the same order."""
    ks = king_sq(b, color)
    if ks < 0:
        return pseudo_moves(b, color, ep)
    them = opp(color)
    moves = pseudo_moves(b, color, ep)
    if attacked(b, ks, them):
        return [m for m in moves if not attacked(apply_move(b, m), m.to if m.frm == ks else ks, them)]
    pins = pinned(b, ks, color)
    out = []
    for m in moves:
        if m.frm == ks:
            if not attacked(apply_move(b, m), m.to, them):
                out.append(m)
        elif m.frm in pins or m.kind == "ep":
            if not attacked(apply_move(b, m), ks, them):
                out.append(m)
        else:
            out.append(m)
    return out


def san_of(b, m, ep):
    """Standard SAN. A self-capture is written like a capture ("Bxe2"), so PGN stays standard; it round-trips because
    for any target square only one of {enemy capture, self-capture} is possible."""
    p = b[m.frm]
    cap = m.kind != "move"
    if p[1] == "p":
        s = (FILES[m.frm & 7] + "x" + sqname(m.to)) if cap else sqname(m.to)
        if m.promo:
            s += "=" + m.promo.upper()
    else:
        amb = same_file = same_rank = False
        for o in legal_moves(b, p[0], ep):
            if o.to != m.to or o.frm == m.frm or b[o.frm] != p:
                continue
            amb = True
            if (o.frm & 7) == (m.frm & 7):
                same_file = True
            if (o.frm >> 3) == (m.frm >> 3):
                same_rank = True
        dis = ""
        if amb:
            dis = (FILES[m.frm & 7] if not same_file else
                   str(8 - (m.frm >> 3)) if not same_rank else sqname(m.frm))
        s = p[1].upper() + dis + ("x" if cap else "") + sqname(m.to)
    nb, enemy = apply_move(b, m), opp(p[0])
    if in_check(nb, enemy):
        s += "#" if not legal_moves(nb, enemy, ep_after(m)) else "+"
    return s


# ---------------- AI: PST eval + quiescence + iterative deepening ----------------
# Tables are white's POV with index 0 = a8; black mirrors via i^56.
PST = {
    "p": [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10,
          5, 5, 10, 25, 25, 10, 5, 5, 0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5,
          5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    "n": [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30,
          -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
          -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    "b": [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10,
          -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    "r": [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    "q": [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10,
          -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10,
          -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    "k": [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
          -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10,
          20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
}
KING_EG = [-50, -40, -30, -20, -20, -30, -40, -50, -30, -20, -10, 0, 0, -10, -20, -30,
           -30, -10, 20, 30, 30, 20, -10, -30, -30, -10, 30, 40, 40, 30, -10, -30,
           -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 20, 30, 30, 20, -10, -30,
           -30, -30, 0, 0, 0, 0, -30, -30, -50, -30, -30, -30, -30, -30, -30, -50]
PHASE = {"n": 1, "b": 1, "r": 2, "q": 4, "p": 0}
# material + PST folded per piece string, black mirrored and negated: evaluate() is a straight sum
_EVAL = {}
for _t in "pnbrq":
    _EVAL["w" + _t] = [VAL[_t] + PST[_t][i] for i in range(64)]
    _EVAL["b" + _t] = [-(VAL[_t] + PST[_t][i ^ 56]) for i in range(64)]
_PHASE = {c + t: PHASE[t] for c in "wb" for t in "pnbrq"}


def evaluate(b):
    """White-centric centipawns: material + PST, tapered king."""
    s = 0
    phase = 0
    kings = []
    ev, ph = _EVAL, _PHASE
    for i in range(64):
        p = b[i]
        if not p:
            continue
        if p[1] == "k":
            kings.append((i, p[0]))
            continue
        s += ev[p][i]
        phase += ph[p]
    mg = min(1, phase / 24)
    for i, c in kings:
        ti = i if c == "w" else i ^ 56
        v = PST["k"][ti] * mg + KING_EG[ti] * (1 - mg)
        s += v if c == "w" else -v
    return s


MATE = 1000000
INF = float("inf")

# SELF-CAPTURE COMBINATION DRIVE (see kramnik_chess.html for the full rationale): when the engine is more than two
# pawns of material ahead (and the board is not a sparse endgame), every line in which it plays a self-capture earns
# a bonus that grows with the lead, capped below a minor piece -- a rubber band that keeps a club player's game alive
# against an engine that otherwise calculates at full strength. Forced mates always trump style.
SELFCAP = {"lead": 200, "base": 60, "slope": 0.5, "cap": 250, "minPhase": 10}


class Search:
    def __init__(self):
        self.nodes = 0
        self.deadline = 0.0
        self.stop = False
        self.bias = None            # (color, bonus) while a biased search runs
        self.cancel = None          # optional callable: True aborts the search (the UI's "new game")

    def score_move(self, b, m):     # move ordering only
        if m.kind == "enemy" or m.kind == "ep":
            victim = b[m.ep if m.kind == "ep" else m.to]
            return 100000 + (VAL[victim[1]] if victim else 100) * 10 - VAL[b[m.frm][1]]
        if m.promo:
            return 90000 + VAL[m.promo]
        p = b[m.frm]
        if m.kind == "self":
            return (80000 if self.bias and p[0] == self.bias[0] else -50000) - VAL[b[m.to][1]]
        return PST[p[1]][m.to if p[0] == "w" else m.to ^ 56]

    def order(self, b, moves, pv):
        for m in moves:
            m.s = 1e9 if pv is not None and m.same(pv) else self.score_move(b, m)
        moves.sort(key=lambda m: -m.s)

    def quiesce(self, b, color, ep, alpha, beta, self_done):
        self.nodes += 1
        stand = evaluate(b) if color == "w" else -evaluate(b)
        if self.bias and self_done:
            stand += self.bias[1] if color == self.bias[0] else -self.bias[1]
        if stand >= beta:
            return beta
        if stand > alpha:
            alpha = stand
        caps = [m for m in legal_moves(b, color, ep) if m.kind == "enemy" or m.kind == "ep" or m.promo]
        self.order(b, caps, None)
        for m in caps:
            sd = self_done or bool(self.bias and color == self.bias[0] and m.kind == "self")
            v = -self.quiesce(apply_move(b, m), opp(color), m.dbl, -beta, -alpha, sd)
            if v >= beta:
                return beta
            if v > alpha:
                alpha = v
        return alpha

    def negamax(self, b, color, ep, depth, alpha, beta, ply, self_done):
        n = self.nodes
        self.nodes += 1
        if (n & 2047) == 0 and (time.monotonic() > self.deadline or (self.cancel and self.cancel())):
            self.stop = True
        if self.stop:
            return alpha
        checked = in_check(b, color)
        if checked:
            depth += 1                  # check extension: finds mates, including self-capture mates
        moves = legal_moves(b, color, ep)
        if not moves:
            return -(MATE - ply) if checked else 0
        if depth <= 0:
            return self.quiesce(b, color, ep, alpha, beta, self_done)
        self.order(b, moves, None)
        best = -INF
        for m in moves:
            sd = self_done or bool(self.bias and color == self.bias[0] and m.kind == "self")
            v = -self.negamax(apply_move(b, m), opp(color), m.dbl, depth - 1, -beta, -alpha, ply + 1, sd)
            if v > best:
                best = v
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best


def best_move(b, color, ep, t=1.2, d=12, banned=(), cancel=None, stats=None):
    """Iterative deepening, time-bounded (t seconds, at most d plies). Always full strength.
    banned: keys of positions already seen twice -- never walked into while clearly better (that throws the win)."""
    root = legal_moves(b, color, ep)
    if not root:
        return None
    if len(root) == 1:
        return root[0]
    se = Search()
    se.cancel = cancel
    mat = phase = 0
    for i in range(64):
        p = b[i]
        if not p or p[1] == "k":
            continue
        mat += VAL[p[1]] if p[0] == color else -VAL[p[1]]
        phase += PHASE[p[1]]
    if mat > SELFCAP["lead"] and phase >= SELFCAP["minPhase"]:
        se.bias = (color, min(SELFCAP["cap"], SELFCAP["base"] + mat * SELFCAP["slope"]))
    se.deadline = time.monotonic() + t
    scored = pv = None
    depth_done = 0
    for depth in range(1, d + 1):
        se.order(b, root, pv)
        res = []
        for m in root:
            sd = bool(se.bias and m.kind == "self")
            v = -se.negamax(apply_move(b, m), opp(color), m.dbl, depth - 1, -INF, INF, 1, sd)
            if se.stop:
                break
            res.append((m, v))
        if se.stop:
            break                       # out of time mid-depth: keep the previous depth's result
        scored, depth_done = res, depth
        bv = -INF
        for m, v in res:
            if v > bv:
                bv, pv = v, m
        if bv >= MATE - 1000:
            break                       # forced mate found
        if time.monotonic() > se.deadline:
            break
    if stats is not None:
        stats.update(nodes=se.nodes, depth=depth_done)
    if not scored:
        return pv or root[0]
    best, best_m = -INF, root[0]
    for m, v in scored:
        if v > best:
            best, best_m = v, m
    if best >= MATE - 1000:             # never decline a mate; a self-capture mate is the house style
        for m, v in scored:
            if m.kind == "self" and v >= MATE - 1000:
                m.v = v
                return m
        best_m.v = best
        return best_m
    if banned and best > 50:
        banned = set(banned)

        def repeats(m):
            return pos_key(apply_move(b, m), opp(color), m.dbl) in banned
        if repeats(best_m):
            alt, alt_v = None, -INF
            for m, v in scored:
                if v > alt_v and not repeats(m):
                    alt, alt_v = m, v
            if alt:
                alt.v = alt_v
                return alt
    best_m.v = best
    return best_m
