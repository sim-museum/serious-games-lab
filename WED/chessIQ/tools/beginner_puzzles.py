"""Beginner Kansas puzzles (below the strength ladder's floor of 1163), mined from games between weak players
(tools/specialist_games.py with a field such as Hal,Rosa,Duke,Eddie,Ella,Adam,Bogie,Jonesie,Felix).

Two kinds (escape: a fixed sample of ESCAPE_SAMPLE positions), both teaching that self-capture is legal at all:
  * "mate": mate in one, and every mating move is a self-capture (at most two of them; at least 5 legal moves);
  * "escape": the side to move is in check with at least 3 legal moves, and tools/mine_puzzles.judge keeps it as a
    self-capture puzzle that a 16-node search already finds (the gap and gain rules of the other puzzles).
The ladder cannot rate below its floor, so these get a starting estimate from how many moves a beginner must look
past: mate 700 + 60 per further checking move, escape 600 + 60 per further legal move, at most 1100. The Academy
corrects every puzzle's rating from players' first attempts (chessiq/academy.py, puzzle_ratings.json).
Checks: Fairy-Stockfish (the rules' authority, not chessiq.engine) must score every mate solution as mate in one;
an escape must also be Leela's move (tools/leela_verdict.py check). Leela is not asked about mates: with another
winning move to hand it often prefers that, which does not refute "mate in one".
python3 tools/beginner_puzzles.py GAMES.jsonl [GAMES.jsonl ...]  -> beginner_mates.json, beginner_escapes.json (here)
then  python3 tools/leela_verdict.py check beginner_escapes.json  and  python3 tools/beginner_puzzles.py --merge"""
import json
import os
import random
import sys
from multiprocessing import Pool
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from chessiq import engine as E, kansas as K  # noqa: E402
import mine_puzzles as M  # noqa: E402

MATES, ESCAPES = "beginner_mates.json", "beginner_escapes.json"
CAP_RATING = 1100
ESCAPE_SAMPLE = 1200            # weak games are full of checks: judge a fixed sample of them, not all


def gives_check(b, turn, m):
    return E.in_check(E.apply_move(b, m), E.opp(turn))


def is_mate(b, turn, m):
    nb, o = E.apply_move(b, m), E.opp(turn)
    return E.in_check(nb, o) and not E.legal_moves(nb, o, E.ep_after(m))


def scan(g):
    """(kind, fen) for each position of one game worth judging."""
    out = []
    b, turn, ep, half, full = K.from_fen(K.START)
    for u in g["moves"]:
        legal = E.legal_moves(b, turn, ep)
        fen = K.to_fen(b, turn, ep, half, full)
        mates = [m for m in legal if is_mate(b, turn, m)]
        if mates and len(mates) <= 2 and len(legal) >= 5 and all(m.kind == "self" for m in mates):
            out.append(("mate", fen))
        elif E.in_check(b, turn) and len(legal) >= 3 and any(m.kind == "self" for m in legal):
            out.append(("escape", fen))
        m = K.find(b, turn, ep, u)
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        full += turn == "b"
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
    return out


def mate_puzzle(fen):
    b, turn, ep, _, _ = K.from_fen(fen)
    legal = E.legal_moves(b, turn, ep)
    mates = [m for m in legal if is_mate(b, turn, m)]
    checks = sum(gives_check(b, turn, m) for m in legal)
    m = mates[0]
    san = E.san_of(b, m, ep)
    piece, victim = K.PIECE_NAME.get(b[m.frm][1], "king"), K.PIECE_NAME[b[m.to][1]]
    return dict(fen=fen, solution=[K.uci_of(x) for x in mates], san=san, kind="mate", motif="check",
                explain="%s! The %s takes its own %s on %s, and it is mate. In ordinary chess your own %s would be "
                "in the way." % (san, piece, victim, E.sqname(m.to), victim),
                rating=min(CAP_RATING, 700 + 60 * (checks - 1)))


def judge(item):
    kind, fen = item
    if kind == "mate":
        r = mate_puzzle(fen)
        d = M._D["d"]
        ok = all(d.fresh("on", fen, nodes=20000, searchmoves=[u])[0][0] == 100000 - 1 for u in r["solution"])
        return r if ok else None
    r = M.judge(fen)
    if not r or r["kind"] != "self-capture" or r["nodes"] != M.STEPS[0]:
        return None
    b, turn, ep, _, _ = K.from_fen(fen)
    n = len(E.legal_moves(b, turn, ep))
    r.update(kind="escape", rating=min(CAP_RATING, 600 + 60 * (n - 2)))
    return r


def mine(paths):
    games = [json.loads(line) for p in paths for line in open(p)]
    with Pool(6) as pool:
        items = sorted({x for xs in pool.imap_unordered(scan, games) for x in xs})
    esc = [x for x in items if x[0] == "escape"]
    print("%d candidates (%d mate, %d escape)" % (len(items), len(items) - len(esc), len(esc)), flush=True)
    if len(esc) > ESCAPE_SAMPLE:
        keep = set(random.Random(1).sample(esc, ESCAPE_SAMPLE))
        items = [x for x in items if x[0] == "mate" or x in keep]
    found = []
    with Pool(4, M._init, (400000,)) as pool:
        for i, r in enumerate(pool.imap_unordered(judge, items)):
            if r:
                found.append(r)
            if (i + 1) % 100 == 0:
                print("%d/%d judged, %d puzzles" % (i + 1, len(items), len(found)), flush=True)
    found.sort(key=lambda r: (r["rating"], r["fen"]))
    for path, kind in ((MATES, "mate"), (ESCAPES, "escape")):
        with open(path, "w") as f:
            json.dump([r for r in found if r["kind"] == kind], f, indent=0)
    print("%d beginner puzzles (%d mate, %d escape) -> %s, %s" % (
        len(found), sum(r["kind"] == "mate" for r in found), sum(r["kind"] == "escape" for r in found), MATES, ESCAPES))


def merge():
    """Add the candidates to chessiq/puzzles.json. Ids already given never change (players' records use them)."""
    old = json.load(open(M.OUT))
    have, top = {p["fen"] for p in old}, max(p["id"] for p in old)
    new = [p for p in json.load(open(MATES)) + json.load(open(ESCAPES)) if p["fen"] not in have]
    for i, p in enumerate(new):
        p["id"] = top + 1 + i
    allp = sorted(old + new, key=lambda p: (p["rating"], p["id"]))
    with open(M.OUT, "w") as f:
        json.dump(allp, f, indent=0)
    print("added %d puzzles, %d in all" % (len(new), len(allp)))


if __name__ == "__main__":
    if sys.argv[1:] == ["--merge"]:
        merge()
    else:
        mine(sys.argv[1:])
