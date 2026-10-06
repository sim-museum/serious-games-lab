"""Measure a personality's style: it plays N games against an opponent (default: the neutral full-strength engine),
alternating colours, every move checked against chessIQ's rules. Reports per-game checks given, pawns and enemy
material captured, self-captures, and the score.
python3 tools/style_match.py <personality> [games] [movetime_ms] [opponent]      (from WED/chessIQ)"""
import os
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402
from chessiq import personalities as P  # noqa: E402

FSF = os.environ.get("FSF", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))
INI = os.environ.get("KRAMNIK_INI", os.path.join(ROOT, "engine", "kramnik.ini"))
VALUE = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9}


class Engine:
    def __init__(self, options=None):
        self.p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.send("uci"); self.wait("uciok")
        self.send("setoption name VariantPath value " + INI)
        self.send("setoption name UCI_Variant value kramnik")
        for k, v in (options or {}).items():
            self.send("setoption name %s value %s" % (k, v))
        self.send("isready"); self.wait("readyok")

    def send(self, s):
        self.p.stdin.write(s + "\n")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line.strip()

    def new_game(self):
        self.send("ucinewgame"); self.send("isready"); self.wait("readyok")

    def best(self, moves, ms):
        self.send("position startpos moves " + " ".join(moves))
        self.send("go movetime %d" % ms)
        return self.wait("bestmove").split()[1]

    def close(self):
        self.send("quit")
        self.p.wait()


def material(b, color):
    return sum(VALUE.get(p[1], 0) for p in b if p and p[0] == color)


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def play(white, black, ms, cap=240):
    """Returns (result for white: 1, 0.5, 0), stats per colour."""
    b, turn, ep, moves, seen = E.init_board(), "w", None, [], Counter()
    st = {"w": Counter(), "b": Counter()}
    eng = {"w": white, "b": black}
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            return (0 if turn == "w" else 1) if E.in_check(b, turn) else 0.5, st, len(moves)
        if E.insufficient_material(b):
            return 0.5, st, len(moves)
        key = E.pos_key(b, turn, ep); seen[key] += 1
        if seen[key] >= 3 or len(moves) >= cap:
            return 0.5, st, len(moves)
        u = eng[turn].best(moves, ms)
        m = next((m for m in legal if uci_of(m) == u), None)
        if m is None:
            raise SystemExit("illegal move %s at ply %d" % (u, len(moves) + 1))
        if m.kind == "enemy":
            st[turn]["material"] += VALUE[b[m.to][1]]
            st[turn]["pawns"] += b[m.to][1] == "p"
        elif m.kind == "ep":
            st[turn]["material"] += 1; st[turn]["pawns"] += 1
        elif m.kind == "self":
            st[turn]["selfcaptures"] += 1
            if material(b, turn) - material(b, E.opp(turn)) >= 2:      # handing material back while ahead?
                st[turn]["selfcap_ahead"] += 1
                st[turn]["given_back"] += VALUE[b[m.to][1]]
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        st[E.opp(turn)]["checks"] += E.in_check(b, turn)
        moves.append(u)


def match(person, games, ms, opponent=None):
    a = Engine(person.engine_options() if person else {})
    o = Engine(opponent.engine_options() if opponent else {})
    tot, score = Counter(), 0.0
    for g in range(games):
        a.new_game(); o.new_game()
        if g % 2 == 0:
            res, st, n = play(a, o, ms); mine, score = st["w"], score + res
        else:
            res, st, n = play(o, a, ms); mine, score = st["b"], score + 1 - res
        tot.update(mine); tot["plies"] += n
    a.close(); o.close()
    return {k: v / games for k, v in tot.items()}, score / games


if __name__ == "__main__":
    name = sys.argv[1]
    games = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    ms = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    by = P.by_name()
    opp = by[sys.argv[4]] if len(sys.argv) > 4 else None
    per, sc = match(by[name], games, ms, opp)
    print("%-10s vs %-10s %d games: score %.2f | per game: checks %.1f, pawns %.1f, material %.1f, self-captures %.1f (while 2+ ahead %.2f, giving back %.2f), plies %.0f"
          % (name, opp.name if opp else "neutral", games, sc, per.get("checks", 0), per.get("pawns", 0),
             per.get("material", 0), per.get("selfcaptures", 0), per.get("selfcap_ahead", 0), per.get("given_back", 0),
             per.get("plies", 0)))
