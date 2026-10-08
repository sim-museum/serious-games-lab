"""KS: a second opinion from the other engine. Fairy-Stockfish finds and checks the Academy's lessons and puzzles
(tools/lesson_check.py, tools/mine_puzzles.py); Leela T40 (lc0, kramnik-t40a1 on the GPU), which judges by a
network rather than by deep calculation, is asked for its move in every position. One search thread: with two, the
same position got a different answer in 2 of 172 between runs; with one, in none (KS-12). "Mate in one" puzzles
are not asked: Leela often prefers another winning move, which does not refute them (tools/beginner_puzzles.py).
python3 tools/leela_verdict.py lessons            print agreement on the lesson positions
python3 tools/leela_verdict.py puzzles [NODES]    keep only the puzzles in chessiq/puzzles.json where Leela agrees
                                                  (both engines, by different methods); ids never change
python3 tools/leela_verdict.py check FILE [NODES] the same for a file of candidate puzzles"""
import json
import os
import subprocess
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)
from chessiq.lessons import LESSONS  # noqa: E402

LC0 = os.path.join(R, "engine", "lc0-kramnik-gpu")
NET = os.path.join(R, "engine", "nets", "kramnik-t40a1.pb.gz")
PUZZLES = os.path.join(R, "chessiq", "puzzles.json")


class Leela:
    def __init__(self, nodes):
        self.nodes = nodes
        self.p = subprocess.Popen([LC0, "--weights=" + NET, "--backend=cuda-fp16", "--threads=1"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.p.stdin.write("uci\nisready\n"); self.p.stdin.flush()
        for line in self.p.stdout:
            if line.startswith("readyok"):
                break

    def best(self, fen):
        self.p.stdin.write("ucinewgame\nposition fen %s\ngo nodes %d\n" % (fen, self.nodes)); self.p.stdin.flush()
        for line in self.p.stdout:
            if line.startswith("bestmove"):
                return line.split()[1]

    def close(self):
        self.p.stdin.write("quit\n"); self.p.stdin.flush(); self.p.wait(timeout=10)


def main():
    a = sys.argv[1:]
    what = a[0] if a else "lessons"
    path = PUZZLES
    if what == "check":
        path = a.pop(1)
    lz = Leela(int(a[1]) if len(a) > 1 else 10000)
    try:
        if what == "lessons":
            agree = n = 0
            for lesson in LESSONS:
                for i, ex in enumerate(lesson.exercises):
                    u = lz.best(ex.fen)
                    ok = u in ex.solutions
                    agree += ok; n += 1
                    print("%-5s %-11s %d %s  Leela %s" % ("agree" if ok else "DIFF", lesson.key, i + 1,
                                                          "Q" if ex.quiz else "D", u))
            print("Leela agrees on %d of %d lesson positions" % (agree, n))
        else:
            ps = json.load(open(path))
            keep = []
            for p in ps:
                if p["kind"] == "mate":
                    keep.append(p)
                    continue
                u = lz.best(p["fen"])
                if u in p["solution"]:
                    keep.append(p)
                else:
                    print("DIFF %s %s: solution %s, Leela %s" % (p.get("id", "-"), p["fen"], p["solution"], u))
            with open(path, "w") as f:
                json.dump(keep, f, indent=0)
            print("Leela agrees on %d of %d puzzles; kept those" % (len(keep), len(ps)))
    finally:
        lz.close()


if __name__ == "__main__":
    main()
