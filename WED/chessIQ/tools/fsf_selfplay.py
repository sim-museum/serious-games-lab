"""Self-play with the Kramnik Fairy-Stockfish, every move checked against chessIQ's own legal-move list.
python3 tools/fsf_selfplay.py [games] [movetime_ms]     (from WED/chessIQ)"""
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessiq import engine as E  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FSF = os.environ.get("FSF", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))   # engine/build_engine.sh
INI = os.environ.get("KRAMNIK_INI", os.path.join(ROOT, "engine", "kramnik.ini"))


class Uci:
    def __init__(self):
        self.p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send("uci"); self.wait("uciok")
        self.send("setoption name VariantPath value " + INI)
        self.send("setoption name UCI_Variant value kramnik")
        self.send("isready"); self.wait("readyok")

    def send(self, s):
        self.p.stdin.write(s + "\n")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line.strip()

    def best(self, moves, ms):
        self.send("position startpos moves " + " ".join(moves))
        self.send("go movetime %d" % ms)
        return self.wait("bestmove").split()[1]


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def play(eng, ms, cap=300):
    b, turn, ep, moves, seen, selfcaps = E.init_board(), "w", None, [], Counter(), 0
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            return ("0-1" if turn == "w" else "1-0") if E.in_check(b, turn) else "1/2 stalemate", moves, selfcaps
        if E.insufficient_material(b):
            return "1/2 material", moves, selfcaps
        key = E.pos_key(b, turn, ep); seen[key] += 1
        if seen[key] >= 3:
            return "1/2 repetition", moves, selfcaps
        if len(moves) >= cap:
            return "unfinished (cap)", moves, selfcaps
        u = eng.best(moves, ms)
        match = [m for m in legal if uci_of(m) == u]
        if len(match) != 1:
            raise SystemExit("ILLEGAL by chessIQ rules at ply %d: %s (moves: %s)" % (len(moves) + 1, u, " ".join(moves)))
        m = match[0]
        selfcaps += m.kind == "self"
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        moves.append(u)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ms = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    eng = Uci()
    for g in range(n):
        res, mv, sc = play(eng, ms)
        print("game %d: %s in %d plies, %d self-captures" % (g + 1, res, len(mv), sc), flush=True)
