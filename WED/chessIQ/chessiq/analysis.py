"""Post-game analysis, as Chessmaster's Post-Game Analysis window (EPIC CM, CM-19).

After a game: the evaluation after every move (Fairy-Stockfish, Kramnik rules, a fixed search per position so the
same game always reads the same), the game's type as the manual defines it, the moves that threw the game, how long
the game followed grandmaster practice, and a suggested next opponent.

The manual names the types but gives no numbers; these are chessIQ's (from White's point of view, centipawns):
  ADV = 100     an advantage (a pawn)
  EVEN = 50     "about even"
  BLUNDER = 300 one move that costs three pawns or more
  * Blunder   -- a decisive game where one move by the loser turned a roughly level game (|eval| <= ADV) into a lost
                 one (a swing of BLUNDER or more) and the loser never got back to level;
  * Dominated -- a decisive game where the winner was never at a disadvantage (never below -ADV);
  * Disputed  -- the advantage went to both sides at some point;
  * Balanced  -- more than 40% of the game was about even (and none of the above).
  Precedence when several fit: Blunder, Dominated, Disputed, Balanced.
"""
import os
import subprocess

from . import engine as E
from .game import book, strip_checks

ADV, EVEN, BLUNDER = 100, 50, 300
MATE = 10000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(ROOT, "engine", "fairy-stockfish-kramnik")
VARIANTS = os.path.join(ROOT, "engine", "kramnik.ini")


def available():
    return os.access(BINARY, os.X_OK) and os.path.exists(VARIANTS)


def _uci(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def evaluate_game(uci_moves, nodes=50000, progress=None, cancel=None):
    """White-point-of-view centipawns after 0..n plies (n + 1 values). Mates are +-MATE (less the distance)."""
    p = subprocess.Popen([BINARY], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, bufsize=1)

    def send(s):
        p.stdin.write(s + "\n"); p.stdin.flush()

    def wait(tok):
        for line in p.stdout:
            if line.startswith(tok):
                return line
        raise RuntimeError("engine ended")
    try:
        for c in ("uci", "setoption name VariantPath value " + VARIANTS, "setoption name UCI_Variant value kramnik",
                  "isready"):
            send(c)
        wait("readyok")
        b, turn, ep, out = E.init_board(), "w", None, []
        for i in range(len(uci_moves) + 1):
            if cancel and cancel():
                return None
            if not E.legal_moves(b, turn, ep):            # game over on the board: mate or stalemate
                v = (-MATE if turn == "w" else MATE) if E.in_check(b, turn) else 0
            else:
                send("position startpos" + (" moves " + " ".join(uci_moves[:i]) if i else ""))
                send("go nodes %d" % nodes)
                score = 0
                for line in p.stdout:
                    if line.startswith("info") and " score " in line:
                        t = line.split()
                        k = t.index("score")
                        if t[k + 1] == "cp":
                            score = int(t[k + 2])
                        elif t[k + 1] == "mate":
                            n = int(t[k + 2])
                            score = (MATE - abs(n)) * (1 if n > 0 else -1)
                    elif line.startswith("bestmove"):
                        break
                v = score if turn == "w" else -score
            out.append(v)
            if progress:
                progress(i, len(uci_moves))
            if i < len(uci_moves):
                m = next(m for m in E.legal_moves(b, turn, ep) if _uci(m) == uci_moves[i])
                b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        return out
    finally:
        try:
            send("quit"); p.wait(timeout=3)
        except Exception:
            p.kill()


DECIDED = 1000                     # beyond ten pawns (or a mate) the game is decided: no move there "throws" it


def blunders(evals):
    """[(ply, swing)]: moves (ply = 1-based move index into the game) that cost their side BLUNDER or more, while
    the game was still undecided; swings are measured on evaluations clipped to +-DECIDED."""
    out = []
    for i in range(1, len(evals)):
        mover_white = (i % 2 == 1)                         # ply i was played by White if odd
        before, after = (max(-DECIDED, min(DECIDED, v)) for v in (evals[i - 1], evals[i]))
        loss = (before - after) if mover_white else (after - before)
        if loss >= BLUNDER and abs(before) < DECIDED:
            out.append((i, loss))
    return out


def classify(evals, result):
    """result: 1.0 White won, 0.0 Black won, 0.5 draw. Returns one of Blunder, Dominated, Disputed, Balanced."""
    even = sum(1 for v in evals if abs(v) < EVEN) / max(1, len(evals))
    white_adv, black_adv = any(v >= ADV for v in evals), any(v <= -ADV for v in evals)
    if result in (0.0, 1.0):
        sign = 1 if result == 1.0 else -1
        w = [sign * v for v in evals]                      # the winner's point of view
        for ply, _ in blunders(evals):
            loser_moved = (ply % 2 == 1) != (result == 1.0)
            if loser_moved and abs(w[ply - 1]) <= ADV and all(x > ADV for x in w[ply:]):
                return "Blunder"
        if min(w) > -ADV:
            return "Dominated"
    if white_adv and black_adv:
        return "Disputed"
    return "Balanced" if even > 0.4 else "Dominated" if result in (0.0, 1.0) else "Balanced"


def gm_plies(sans):
    """How many plies the game followed moves played in the grandmaster games (the opening helper's book)."""
    bk, n = book(), 0
    for i, san in enumerate(sans):
        key = " ".join(strip_checks(s) for s in sans[:i])
        if strip_checks(san) in bk.get(key, {}):
            n += 1
        else:
            break
    return n


def suggest_opponent(people, current, my_rating, score):
    """Chessmaster suggests a next opponent: a little stronger after a win, a little weaker after a loss, the same
    level after a draw -- the nearest rated opponent to that target, other than the one just played."""
    target = my_rating + (100 if score == 1.0 else -100 if score == 0.0 else 0)
    cands = [p for p in people if p.name != current]
    return min(cands, key=lambda p: abs(p.rating - target)) if cands else None


def summary(evals, result, sans, white, black):
    """The Post-Game Analysis text, as plain sentences."""
    kind = classify(evals, result)
    who = {1.0: "%s won" % white, 0.0: "%s won" % black, 0.5: "Drawn"}[result]
    lines = ["%s in %d moves. Game type: %s." % (who, (len(sans) + 1) // 2, kind)]
    bl = blunders(evals)
    if bl:
        worst = sorted(bl, key=lambda x: -x[1])[:3]
        lines.append("Costliest moves: " + ", ".join(
            "%d%s %s (-%.1f)" % ((ply + 1) // 2, "." if ply % 2 else "...", sans[ply - 1], loss / 100)
            for ply, loss in sorted(worst)) + ".")
    g = gm_plies(sans)
    lines.append("Opening: followed grandmaster games for %d plies." % g if g else "Opening: left grandmaster practice "
                 "at once.")
    return kind, " ".join(lines)
