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


# ---- motifs (docs/SELF_CAPTURE_MOTIFS.md; rules validated on the paper's examples by tools/selfcapture_census.py) ----

NONPAWN = {"n": 3, "b": 3, "r": 5, "q": 9}


def nonpawn(b):
    return sum(NONPAWN.get(p[1], 0) for p in b if p)


def _reaches_zone(b, sq, color):
    """Does the piece on sq, looking through its own side's pieces, reach a square next to (or on) the enemy king?"""
    ks = E.king_sq(b, E.opp(color))
    zone = {ks} | {t for t in range(64) if max(abs((t >> 3) - (ks >> 3)), abs((t & 7) - (ks & 7))) == 1}
    t, r, c = b[sq][1], sq >> 3, sq & 7
    if t in "nkp":
        if t == "p":
            d = -1 if color == "w" else 1
            hits = [(r + d) * 8 + c + dc for dc in (-1, 1) if E.inb(r + d, c + dc)]
        else:
            hits = [(r + dr) * 8 + c + dc for dr, dc in (E.KN if t == "n" else E.KG) if E.inb(r + dr, c + dc)]
        return any(h in zone for h in hits)
    for dr, dc in (E.DIAG if t == "b" else E.ORTH if t == "r" else E.DIAG + E.ORTH):
        rr, cc = r + dr, c + dc
        while E.inb(rr, cc):
            s = rr * 8 + cc
            if s in zone:
                return True
            if b[s] and b[s][0] != color:
                break
            rr, cc = rr + dr, cc + dc
    return False


def _ordinary(b, color, ep):
    return sum(1 for m in E.legal_moves(b, color, ep) if m.kind != "self")


def motif(b, turn, ep, m):
    """The motif family of the self-capture m (first match wins): promotion, escape, king-walk, king-other, check,
    attack, activation, reposition."""
    piece, nb = b[m.frm][1], E.apply_move(b, m)
    if piece == "p" and (m.promo or 8 - (m.to >> 3) == (7 if turn == "w" else 2)):
        return "promotion"
    if piece == "k":
        if E.in_check(b, turn):
            return "escape"
        return "king-walk" if nonpawn(b) <= 26 else "king-other"
    if E.in_check(nb, E.opp(turn)):
        return "check"
    if _reaches_zone(nb, m.to, turn):
        return "attack"
    if _ordinary(nb, turn, None) - _ordinary(b, turn, ep) >= 2:
        return "activation"
    return "reposition"


MOTIF_TEXT = {                  # {piece}: the mover, {victim}: its own man it takes
    "promotion": "the pawn takes its own {victim} to reach the last ranks",
    "escape": "the king escapes check by taking its own {victim}",
    "king-walk": "the king walks forward by taking its own {victim}",
    "king-other": "the king makes room by taking its own {victim}",
    "check": "the {piece} takes its own {victim} and gives check",
    "attack": "the {piece} takes its own {victim} and opens a line at the enemy king",
    "activation": "the {piece} takes its own {victim} and gets into play",
    "reposition": "the {piece} takes its own {victim} to reach that square",
}


def phrase(motif_, piece, victim):
    return MOTIF_TEXT[motif_].format(piece=PIECE_NAME.get(piece, "king"), victim=PIECE_NAME[victim])


# ---- the rule-switch engines ---------------------------------------------------------------------------------------

class RuleSwitch:
    """Two Fairy-Stockfish processes on one position: Kramnik rules ("on") and the same without self-capture
    ("off"). search() returns (best UCI move, side-to-move centipawns with mates as +-(100000 - n), PV list)."""

    def __init__(self, binary, variants, nodes=40000):
        import subprocess
        self.nodes, self.p = nodes, {}
        for k, v in (("on", "kramnik"), ("off", "kramniknosc")):
            p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 text=True, bufsize=1)
            for c in ("uci", "setoption name VariantPath value " + variants, "setoption name UCI_Variant value " + v,
                      "setoption name Threads value 1", "setoption name Hash value 32"):
                p.stdin.write(c + "\n")
            self.p[k] = p

    def search(self, rules, fen, searchmoves=None):
        p = self.p[rules]
        p.stdin.write("position fen %s\ngo nodes %d%s\n" % (fen, self.nodes, " searchmoves " + " ".join(searchmoves)
                                                            if searchmoves else ""))
        p.stdin.flush()
        score, pv = 0, []
        for line in p.stdout:
            if line.startswith("info") and " score " in line and " pv " in line:
                t = line.split()
                s = t[t.index("score") + 1:t.index("score") + 3]
                score = int(s[1]) if s[0] == "cp" else (100000 - abs(int(s[1]))) * (1 if int(s[1]) > 0 else -1)
                pv = t[t.index("pv") + 1:]
            elif line.startswith("bestmove"):
                best = line.split()[1]
                return (None if best in ("(none)", "0000") else best), score, pv
        raise RuntimeError("engine ended")

    def close(self):
        for p in self.p.values():
            try:
                p.stdin.write("quit\n"); p.stdin.flush(); p.wait(timeout=3)
            except Exception:
                p.kill()
            for f in (p.stdin, p.stdout):
                try:
                    f.close()
                except Exception:
                    pass


PIECE_NAME = {"p": "pawn", "n": "knight", "b": "bishop", "r": "rook", "q": "queen"}
MISSED = 100                    # cp: a missed self-capture must gain at least this over ordinary-chess play ...
LOSS = 50                       # ... and the move played must lose at least this much against the best
TRAP = 100                      # cp: an ordinary-chess move must lose at least this under Kramnik rules to be shown
SC_DEPTH = 8                    # plies: ... and its refutation must contain a self-capture this soon


def san_line(b, turn, ep, pv, n=4):
    """Up to n moves of a PV in SAN; self-captures are marked so the reader sees them."""
    out = []
    for u in pv[:n]:
        m = find(b, turn, ep, u)
        if m is None:
            break
        out.append(E.san_of(b, m, ep) + (" (takes its own %s)" % PIECE_NAME[b[m.to][1]] if m.kind == "self" else ""))
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return ", ".join(out)


def sc_line(b, turn, ep, pv, n=SC_DEPTH):
    """The PV in SAN up to and including its first self-capture within n plies, or None if it has none: a trap or
    a spotted move is shown only when self-capture visibly decides it."""
    bb, tt, ee = b, turn, ep
    for k, u in enumerate(pv[:n]):
        m = find(bb, tt, ee, u)
        if m is None:
            return None
        if m.kind == "self":
            return san_line(b, turn, ep, pv, k + 1)
        bb, ee, tt = E.apply_move(bb, m), E.ep_after(m), E.opp(tt)
    return None


def moments(uci_moves, rs, start=START, cancel=None, progress=None):
    """The game's Kansas moments, in order. Each is a dict: ply (moves before it), side ("w"/"b"), kind, san (the
    move played), and by kind:
      played  -- a self-capture was played: motif, loss (cp against the best move);
      missed  -- the best move was a self-capture worth MISSED over the best ordinary-chess play, and the move
                 played lost LOSS or more: best (SAN), motif, gain, loss;
      trap    -- the move played was the best move in ordinary chess, but under Kramnik rules it loses TRAP or more,
                 and the refutation has a self-capture within SC_DEPTH plies: best (SAN), why (the refutation up to
                 that self-capture, in SAN), loss;
      spotted -- the best move was played, and ordinary chess's best move would have lost TRAP or more here, to a
                 line with a self-capture within SC_DEPTH plies: off (that move, SAN), why (that line), loss.
    rs is a RuleSwitch."""
    b, turn, ep, half, full = from_fen(start)
    out = []
    for i, u in enumerate(uci_moves):
        if cancel and cancel():
            return None
        m = find(b, turn, ep, u)
        if m is None:
            raise ValueError("illegal move " + u)
        fen = to_fen(b, turn, ep, half, full)
        san = E.san_of(b, m, ep)
        best, s_on, _ = rs.search("on", fen)
        if best is not None:
            loss = 0 if u == best else cap(s_on) - cap(rs.search("on", fen, [u])[1])
            bm = find(b, turn, ep, best)
            base = dict(ply=i, side=turn, san=san)
            if m.kind == "self":
                out.append(dict(base, kind="played", motif=motif(b, turn, ep, m), loss=loss, piece=b[m.frm][1],
                                victim=b[m.to][1]))
            elif bm is not None:
                off, s_off, _ = rs.search("off", fen)
                om = find(b, turn, ep, off) if off else None
                if bm.kind == "self":
                    gain = cap(s_on) - cap(s_off)
                    if gain >= MISSED and loss >= LOSS:
                        out.append(dict(base, kind="missed", best=E.san_of(b, bm, ep), motif=motif(b, turn, ep, bm),
                                        gain=gain, loss=loss, piece=b[bm.frm][1], victim=b[bm.to][1]))
                elif om is not None and off != best:
                    after = to_fen(E.apply_move(b, om), E.opp(turn), E.ep_after(om), 0, full + (turn == "b"))
                    if u == off and loss >= TRAP:
                        why = sc_line(E.apply_move(b, om), E.opp(turn), E.ep_after(om), rs.search("on", after)[2])
                        if why:
                            out.append(dict(base, kind="trap", best=E.san_of(b, bm, ep), loss=loss, why=why))
                    elif u == best:
                        off_loss = cap(s_on) - cap(rs.search("on", fen, [off])[1])
                        if off_loss >= TRAP:
                            why = sc_line(E.apply_move(b, om), E.opp(turn), E.ep_after(om), rs.search("on", after)[2])
                            if why:
                                out.append(dict(base, kind="spotted", off=E.san_of(b, om, ep), loss=off_loss,
                                                why=why))
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        full += turn == "b"
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        if progress:
            progress(i + 1, len(uci_moves))
    return out


def describe(mo):
    """One sentence for a Kansas moment."""
    num = "%d%s" % (mo["ply"] // 2 + 1, "." if mo["side"] == "w" else "...")
    if mo["kind"] == "played":
        return "%s%s: %s.%s" % (num, mo["san"], phrase(mo["motif"], mo["piece"], mo["victim"]).capitalize(),
                                " It cost %.1f." % (mo["loss"] / 100) if mo["loss"] >= 100 else "")
    if mo["kind"] == "missed":
        return "%s%s: missed %s!, where %s; worth %.1f more." % (num, mo["san"], mo["best"],
                                                                phrase(mo["motif"], mo["piece"], mo["victim"]),
                                                                mo["loss"] / 100)
    if mo["kind"] == "trap":
        return ("%s%s: the best move in ordinary chess, but not here (-%.1f): %s. Better was %s."
                % (num, mo["san"], mo["loss"] / 100, mo["why"], mo["best"]))
    return "%s%s: well spotted. The ordinary-chess move %s fails here to %s." % (num, mo["san"], mo["off"], mo["why"])
