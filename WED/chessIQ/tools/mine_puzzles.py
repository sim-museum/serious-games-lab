"""KS-5: Kansas puzzles mined from the self-capture census (docs/SELF_CAPTURE_CENSUS.md) and checked deeply.

Candidates: census positions where self-capture decided the best move (direct or threat), and positions where a
self-capture was played. Each is searched under Kramnik rules (one thread, NODES, two lines, deterministic):
  * kept if the best move leads every other by GAP cp (scores capped at +-1000; uncapped, by 300, when it wins
    outright) and without it the side to move is not already winning (second best <= +300);
  * kind "self-capture" if the solution is a self-capture worth MISSED over the best play without self-capture;
    kind "quiet" if it is not, the best move of ordinary chess differs, and that move loses TRAP or more here to a
    line with a self-capture (chessiq.kansas.sc_line);
  * rated by the strength ladder (chessiq.personalities.LADDER): the smallest node count from which a fresh search
    finds the solution at every larger step, capped at MAX_RATING. This is an engine's difficulty, a proxy for a
    player's: an engine looks at checks no sooner than other moves, so a checking self-capture can rate higher than
    a player would find it.
Then tools/leela_verdict.py puzzles keeps only the puzzles where Leela T40 agrees.
python3 tools/mine_puzzles.py CENSUS_OUT_DIR [--workers K] [--nodes N] [--merge]   -> chessiq/puzzles.json
  --merge keeps the puzzles already there and adds the new positions."""
import json
import math
import os
import sys
from multiprocessing import Pool
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)
from chessiq import engine as E, kansas as K  # noqa: E402
from chessiq.personalities import LADDER  # noqa: E402
from chessiq.uci_engine import BINARY, VARIANTS  # noqa: E402

GAP = 150
MAX_RATING = 2600               # the strongest specialist; beyond it the ladder says little about people
STEPS = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 65536, 262144]
OUT = os.path.join(R, "chessiq", "puzzles.json")


def ladder_rating(nodes):
    pts = [(math.log2(n), r) for n, r in LADDER]
    x = math.log2(nodes)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, r0), (x1, r1) in zip(pts, pts[1:]):
        if x <= x1:
            return round(r0 + (r1 - r0) * (x - x0) / (x1 - x0))
    return round(pts[-1][1] + 195 * (x - pts[-1][0]))          # beyond the ladder: about 195 per doubling


class Deep(K.RuleSwitch):
    def __init__(self, nodes):
        super().__init__(BINARY, VARIANTS, nodes)
        for p in self.p.values():
            p.stdin.write("setoption name Hash value 128\n")

    def fresh(self, rules, fen, nodes=None, multipv=1, searchmoves=None):
        """A search from a cleared hash: the same answer whichever worker asks, in whatever order."""
        p = self.p[rules]
        p.stdin.write("ucinewgame\nsetoption name MultiPV value %d\nposition fen %s\ngo nodes %d%s\n"
                      % (multipv, fen, nodes or self.nodes, " searchmoves " + " ".join(searchmoves) if searchmoves else ""))
        p.stdin.flush()
        lines = {}
        for line in p.stdout:
            if line.startswith("info") and " score " in line and " pv " in line:
                t = line.split()
                s = t[t.index("score") + 1:t.index("score") + 3]
                sc = int(s[1]) if s[0] == "cp" else (100000 - abs(int(s[1]))) * (1 if int(s[1]) > 0 else -1)
                k = int(t[t.index("multipv") + 1]) if "multipv" in t else 1
                lines[k] = (sc, t[t.index("pv") + 1:])
            elif line.startswith("bestmove"):
                if multipv > 1:
                    p.stdin.write("setoption name MultiPV value 1\n")
                return [lines[i] for i in sorted(lines)]


_D = {}


def _init(nodes):
    _D["d"] = Deep(nodes)


def judge(fen):
    d = _D["d"]
    b, turn, ep, half, full = K.from_fen(fen)
    if len(E.legal_moves(b, turn, ep)) < 2:
        return None
    lines = d.fresh("on", fen, multipv=2)
    if len(lines) < 2:
        return None
    (s1, pv1), (s2, _) = lines[0], lines[1]
    decisive = K.cap(s1) >= K.CAP
    if (s1 - s2 if decisive else K.cap(s1) - K.cap(s2)) < (300 if decisive else GAP) or K.cap(s2) > 300:
        return None
    best = pv1[0]
    bm = K.find(b, turn, ep, best)
    off = (d.fresh("off", fen) or [(-100000, [])])[0]      # no line: without self-capture there is no legal move
    om = K.find(b, turn, ep, off[1][0]) if off[1] else None
    san = E.san_of(b, bm, ep)
    out = dict(fen=fen, solution=[best], san=san, score=s1)
    if bm.kind == "self":
        gain = K.cap(s1) - K.cap(off[0])
        if gain < K.MISSED:
            return None
        mo = K.motif(b, turn, ep, bm)
        cost = ("this position would be lost" if K.cap(off[0]) <= -K.CAP else "the best play here would be %.1f worse"
                % (gain / 100)) if gain < 2 * K.CAP else "this position would be lost"
        out.update(kind="self-capture", motif=mo, explain="%s! %s. Without self-capture %s."
                   % (san, K.phrase(mo, b[bm.frm][1], b[bm.to][1]).capitalize(), cost))
    else:
        if om is None or om.kind == "self" or K.uci_of(om) == best:
            return None
        nb = E.apply_move(b, om)
        after = K.to_fen(nb, E.opp(turn), E.ep_after(om), 0, full + (turn == "b"))
        why = K.sc_line(nb, E.opp(turn), E.ep_after(om), d.fresh("on", after)[0][1])
        loss = K.cap(s1) - K.cap(d.fresh("on", fen, searchmoves=[K.uci_of(om)])[0][0])
        if not why or loss < K.TRAP:
            return None
        osan = E.san_of(b, om, ep)
        out.update(kind="quiet", off=osan, explain="%s. The natural %s, best in ordinary chess, fails here to %s."
                   % (san, osan, why))
    found = None
    for n in reversed(STEPS):                   # the smallest step from which every larger step finds it
        if d.fresh("on", fen, nodes=n)[0][1][0] != best:
            break
        found = n
    if found is None:
        return None
    out.update(nodes=found, rating=min(MAX_RATING, ladder_rating(found)))
    return out


def main():
    a = sys.argv[1:]
    workers, nodes = 6, 2000000
    if "--workers" in a:
        i = a.index("--workers"); workers = int(a[i + 1]); del a[i:i + 2]
    if "--nodes" in a:
        i = a.index("--nodes"); nodes = int(a[i + 1]); del a[i:i + 2]
    merge = "--merge" in a
    a = [x for x in a if x != "--merge"]
    src = a[0]
    fens = []
    for p in map(json.loads, open(os.path.join(src, "positions.jsonl"))):
        if p["label"] in ("direct", "threat"):
            fens.append(p["fen"])
    for s in map(json.loads, open(os.path.join(src, "selfcaptures.jsonl"))):
        fens.append(s["fen"])
    fens = sorted(set(fens))
    print("%d candidates" % len(fens), flush=True)
    found = []
    with Pool(workers, _init, (nodes,)) as pool:
        for i, r in enumerate(pool.imap_unordered(judge, fens)):
            if r:
                found.append(r)
            if (i + 1) % 50 == 0:
                print("%d/%d judged, %d puzzles" % (i + 1, len(fens), len(found)), flush=True)
    if merge and os.path.exists(OUT):
        old = json.load(open(OUT))
        have = {p["fen"] for p in old}
        found = old + [r for r in found if r["fen"] not in have]
    found.sort(key=lambda r: (r["rating"], r["fen"]))
    for i, r in enumerate(found):
        r["id"] = i + 1
    with open(OUT, "w") as f:
        json.dump(found, f, indent=0)
    print("%d puzzles -> %s" % (len(found), OUT))


if __name__ == "__main__":
    main()
