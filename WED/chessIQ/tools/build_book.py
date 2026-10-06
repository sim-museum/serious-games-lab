"""Build chessIQ's opening book (chessiq/book.json) from the grandmaster database (EPIC CM, sprint CM-6).

Every grandmaster game is legal Kramnik chess UP TO ITS FIRST CASTLING MOVE, so each game contributes its first
BOOK_PLIES plies, cut at castling (the first book used only the 635 games in which nobody castled at all). Every
move is replayed through chessIQ's own rules; a game stops contributing at the first move that does not parse.
Output: {move sequence so far: {next move (SAN, no check marks): number of games}}.
python3 tools/build_book.py [pgn] [--limit N]      (from WED/chessIQ)"""
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402
from chessiq.game import BOOK_PLIES, strip_checks  # noqa: E402

PGN = os.path.join(os.path.dirname(ROOT), "INSTALL", "25000grandmasterGames.pgn")
OUT = os.path.join(ROOT, "chessiq", "book.json")
FILES = "abcdefgh"


def games(path):
    text, moves = [], False
    with open(path, encoding="latin-1") as f:
        for line in f:
            if line.startswith("["):
                if moves:
                    yield " ".join(text)
                    text, moves = [], False
                continue
            if line.strip():
                text.append(line.strip())
                moves = True
    if text:
        yield " ".join(text)


def tokens(movetext):
    t = re.sub(r"\{[^}]*\}", " ", movetext)
    while "(" in t:                                   # drop variations, innermost first
        t2 = re.sub(r"\([^()]*\)", " ", t)
        if t2 == t:
            break
        t = t2
    out = []
    for tok in t.split():
        tok = re.sub(r"^\d+\.(\.\.)?", "", tok)
        if not tok or tok in ("1-0", "0-1", "1/2-1/2", "*") or tok.startswith("$"):
            continue
        out.append(tok.rstrip("!?"))
    return out


def square(s):
    return (8 - int(s[1])) * 8 + FILES.index(s[0])


def find(b, turn, ep, san):
    core = strip_checks(san)
    promo = None
    if "=" in core:
        core, promo = core.split("=")
        promo = promo[0].lower()
    m = re.search(r"([a-h][1-8])$", core)
    if not m:
        return None
    to = square(m.group(1))
    piece = core[0].lower() if core[0] in "KQRBN" else "p"
    cands = [mv for mv in E.legal_moves(b, turn, ep)
             if mv.to == to and b[mv.frm][1] == piece and (mv.promo or None) == promo]
    if len(cands) == 1:
        return cands[0]
    return next((mv for mv in cands if strip_checks(E.san_of(b, mv, ep)) == strip_checks(san)), None)


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        i = args.index("--limit"); limit = int(args[i + 1]); del args[i:i + 2]
    path = args[0] if args else PGN
    book, n_games, cut_castle, bad, t0 = {}, 0, 0, 0, time.time()
    for g in games(path):
        n_games += 1
        if limit and n_games > limit:
            n_games -= 1
            break
        b, turn, ep, seq = E.init_board(), "w", None, []
        for san in tokens(g)[:BOOK_PLIES]:
            if san.startswith("O-O") or san.startswith("0-0"):
                cut_castle += 1
                break
            mv = find(b, turn, ep, san)
            if mv is None:
                bad += 1
                break
            s = strip_checks(E.san_of(b, mv, ep))
            node = book.setdefault(" ".join(seq), {})
            node[s] = node.get(s, 0) + 1
            seq.append(s)
            b, ep, turn = E.apply_move(b, mv), E.ep_after(mv), E.opp(turn)
    with open(OUT, "w") as f:
        json.dump(book, f, separators=(",", ":"), sort_keys=True)
    print("%d games, %d positions, %d cut at castling, %d stopped at an unparsable move, %.0f s -> %s (%d KB)"
          % (n_games, len(book), cut_castle, bad, time.time() - t0, OUT, os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
