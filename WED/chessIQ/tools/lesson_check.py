"""KS-4: check every Kramnik Academy exercise (chessiq/lessons.py). Each solution must be legal, and a deep
Fairy-Stockfish search under Kramnik rules must put a solution first, at least MARGIN cp ahead of every other move
(scores capped at +-1000, so two wins count as equal), unless every legal move is a solution. Also prints the
engine's line and the best move without self-capture, for writing the explanations.
python3 tools/lesson_check.py [--nodes N]          exit status 1 if any exercise fails
python3 tools/lesson_check.py threat FEN [FEN ...]  candidate "quiet threat" positions: the best move with and
                                                    without self-capture, what the ordinary-chess move loses here,
                                                    and the self-capture line that refutes it"""
import os
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)
from chessiq import engine as E, kansas as K  # noqa: E402
from chessiq.lessons import LESSONS  # noqa: E402
from chessiq.uci_engine import BINARY, VARIANTS  # noqa: E402

MARGIN = 100


class Deep(K.RuleSwitch):
    def __init__(self, nodes):
        super().__init__(BINARY, VARIANTS, nodes)
        for p in self.p.values():
            p.stdin.write("setoption name Hash value 256\n")      # one thread: the same verdict every run

    def multipv(self, fen, k):
        p = self.p["on"]
        p.stdin.write("ucinewgame\nsetoption name MultiPV value %d\nposition fen %s\ngo nodes %d\n" % (k, fen, self.nodes))
        p.stdin.flush()
        lines = {}
        for line in p.stdout:
            if line.startswith("info") and " multipv " in line and " score " in line and " pv " in line:
                t = line.split()
                s = t[t.index("score") + 1:t.index("score") + 3]
                sc = int(s[1]) if s[0] == "cp" else (100000 - abs(int(s[1]))) * (1 if int(s[1]) > 0 else -1)
                lines[int(t[t.index("multipv") + 1])] = (sc, t[t.index("pv") + 1:])
            elif line.startswith("bestmove"):
                p.stdin.write("setoption name MultiPV value 1\n")
                return [lines[i] for i in sorted(lines)]


def check(deep):
    bad = 0
    for lesson in LESSONS:
        for i, ex in enumerate(lesson.exercises):
            b, turn, ep, _, _ = K.from_fen(ex.fen)
            legal = [K.uci_of(m) for m in E.legal_moves(b, turn, ep)]
            problems = [u + " is not legal" for u in ex.solutions if u not in legal]
            others = [u for u in legal if u not in ex.solutions]
            lines = deep.multipv(ex.fen, min(len(legal), 4))
            best_sc, best_pv = lines[0]
            if best_pv[0] not in ex.solutions:
                problems.append("engine prefers %s" % K.san_line(b, turn, ep, best_pv, 1))
            elif others and ex.quiz:
                rest = [sc for sc, pv in lines if pv[0] not in ex.solutions]
                if not rest:                    # every listed line is a solution: search the others alone
                    rest = [deep.search("on", ex.fen, others)[1]]
                decisive = K.cap(best_sc) >= K.CAP           # a win: compare uncapped (mate > +59 > +5)
                gap = best_sc - max(rest) if decisive else K.cap(best_sc) - K.cap(max(rest))
                if gap < (300 if decisive else MARGIN):
                    problems.append("margin only %d cp" % gap)
            if not ex.quiz and best_pv[0] not in ex.solutions:  # a demonstration: within half a pawn of the best
                sol = deep.search("on", ex.fen, ex.solutions)[1]
                if K.cap(best_sc) - K.cap(sol) <= 50:
                    problems = [q for q in problems if not q.startswith("engine prefers")]
                else:
                    problems.append("demonstration %d cp worse than the best" % (K.cap(best_sc) - K.cap(sol)))
            off = deep.search("off", ex.fen)[0]
            print("%-4s %-11s %d %s best %-28s %6s  off-rules %-6s %s" % (
                "ok" if not problems else "BAD", lesson.key, i + 1, "Q" if ex.quiz else "D", K.san_line(b, turn, ep, best_pv, 3)[:28],
                "mate" if abs(best_sc) > 50000 else "%+d" % best_sc, off or "-", "; ".join(problems)))
            bad += bool(problems)
    print("%d exercise(s) fail" % bad)
    return bad


def threats(deep, fens):
    for fen in fens:
        b, turn, ep, half, full = K.from_fen(fen)
        on, s_on, _ = deep.search("on", fen)
        off, s_off, _ = deep.search("off", fen)
        if off == on:
            print("same best move %s: %s" % (on, fen))
            continue
        loss = K.cap(s_on) - K.cap(deep.search("on", fen, [off])[1])
        om = K.find(b, turn, ep, off)
        nb = E.apply_move(b, om)
        pv = deep.search("on", K.to_fen(nb, E.opp(turn), E.ep_after(om), 0, full + (turn == "b")))[2]
        print("on %s (%+d)  off %s loses %d  why: %s\n   %s" % (
            K.san_line(b, turn, ep, [on], 1), s_on, K.san_line(b, turn, ep, [off], 1), loss,
            K.sc_line(nb, E.opp(turn), E.ep_after(om), pv) or "(no self-capture in 8 plies: " +
            K.san_line(nb, E.opp(turn), E.ep_after(om), pv, 6) + ")", fen))


def main():
    a = sys.argv[1:]
    nodes = 4000000
    if "--nodes" in a:
        i = a.index("--nodes"); nodes = int(a[i + 1]); del a[i:i + 2]
    deep = Deep(nodes)
    try:
        if a and a[0] == "threat":
            threats(deep, a[1:])
            return 0
        return 1 if check(deep) else 0
    finally:
        deep.close()


if __name__ == "__main__":
    sys.exit(main())
