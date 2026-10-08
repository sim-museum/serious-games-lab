"""Self-capture census (docs/SELF_CAPTURE_MOTIFS.md): where self-captures happen in strong Kramnik-chess games, what
they do, and where the mere possibility of one changes the best move.

python3 tools/selfcapture_census.py validate
    Classify the paper's example self-captures; every label must match.
python3 tools/selfcapture_census.py census OUTDIR GAMES.jsonl [GAMES.jsonl ...] [--nodes N] [--workers K] [--every P]
    GAMES files come from tools/uci_match.py --games. Writes OUTDIR/selfcaptures.jsonl (every self-capture played,
    with its motif label), OUTDIR/positions.jsonl (a rule-switch search of sampled positions: Fairy-Stockfish with
    self-capture on and off, fixed nodes, one thread) and OUTDIR/report.md.

Motif labels (first match wins): promotion (a pawn self-captures onto its 7th or 8th rank), escape (the king
self-captures out of check), king-walk (the king self-captures in an endgame), king-other, check (the move gives check,
direct or discovered), attack (the moved piece, looking through its own pieces, now reaches the enemy king's zone),
activation (the side gains at least two ordinary moves), reposition (anything else: a piece moves onto its own
piece's square for a later plan)."""
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import engine as E  # noqa: E402

FSF = os.path.join(ROOT, "engine", "fairy-stockfish-kramnik")
NONPAWN = {"n": 3, "b": 3, "r": 5, "q": 9}
INI = """[kramnik:chess]
castling = false
selfCapture = true

[kramniknosc:chess]
castling = false
selfCapture = false
"""


# ---- board helpers -----------------------------------------------------------------------------------------------

def to_fen(b, turn, ep, half=0, full=1):
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
    f = fen.split()
    b, i = [None] * 64, 0
    for ch in f[0]:
        if ch == "/":
            continue
        if ch.isdigit():
            i += int(ch)
        else:
            b[i] = ("w" if ch.isupper() else "b") + ch.lower(); i += 1
    ep = None if len(f) < 4 or f[3] == "-" else (8 - int(f[3][1])) * 8 + E.FILES.index(f[3][0])
    return b, f[1], ep


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def find(b, turn, ep, u):
    return next((m for m in E.legal_moves(b, turn, ep) if uci_of(m) == u), None)


def nonpawn(b):
    return sum(NONPAWN.get(p[1], 0) for p in b if p)


def phase(b, full):
    if full <= 12:
        return "opening"
    return "endgame" if nonpawn(b) <= 26 else "middlegame"


def ordinary_moves(b, color, ep):
    return sum(1 for m in E.legal_moves(b, color, ep) if m.kind != "self")


def reaches_zone(b, sq, color):
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
    dirs = E.DIAG if t == "b" else E.ORTH if t == "r" else E.DIAG + E.ORTH
    for dr, dc in dirs:
        rr, cc = r + dr, c + dc
        while E.inb(rr, cc):
            s = rr * 8 + cc
            if s in zone:
                return True
            if b[s] and b[s][0] != color:
                break
            rr, cc = rr + dr, cc + dc
    return False


def classify(b, turn, ep, m):
    piece = b[m.frm][1]
    nb = E.apply_move(b, m)
    rank = 8 - (m.to >> 3)
    if piece == "p" and (m.promo or rank == (7 if turn == "w" else 2)):
        return "promotion"
    if piece == "k":
        if E.in_check(b, turn):
            return "escape"
        return "king-walk" if nonpawn(b) <= 26 else "king-other"
    if E.in_check(nb, E.opp(turn)):
        return "check"
    if reaches_zone(nb, m.to, turn):
        return "attack"
    if ordinary_moves(nb, turn, None) - ordinary_moves(b, turn, ep) >= 2:
        return "activation"
    return "reposition"


# ---- validation against the paper's examples ---------------------------------------------------------------------

PAPER = [   # (name, FEN before the self-capture, UCI, expected label) -- FENs from docs/SELF_CAPTURE_MOTIFS.md
    # Family 2 (activation) is two labels here: activation when the side gains ordinary moves at once, reposition
    # when a piece only moves onto its own pawn's square for a later plan (AZ-34's knights).
    ("Dragon Qxh2", "r1bq1rk1/p4pbp/2p2np1/3pp3/4P1P1/2N1BP2/PPPQ3P/2KR1B1R w - - 0 12", "d2h2", "attack"),
    ("Ruy Qxh7", "r1b1kb1r/1ppp2pp/p1n5/5p2/B2Nn2q/6P1/PPP2P1P/RNBQR1K1 b - - 0 9", "h4h7", "attack"),
    ("AZ-33 Rxh6", "r5k1/1p3p2/p1pnr2p/3p4/PP1P2Pq/3BP3/4QPP1/R1R3K1 b - - 0 37", "e6h6", "attack"),
    ("AZ-37 Rxh4", "r1b2bk1/pp3p2/2n1rn2/q2pp1B1/2P4P/P3P3/1PQN1PP1/2KR1B1R w - - 0 16", "h1h4", "attack"),
    ("AZ-38 Rxa7", "r2q1rk1/p2nbpp1/5n2/2p4p/2N2B1P/5Q2/P3NPP1/3R1RK1 b - - 0 19", "a8a7", "activation"),
    ("AZ-35 Bxg2", "r1bqkb1r/2pn1p2/p3pn2/1p2P1B1/2pP4/2N5/PP3PPP/R2QKB1R w - - 1 11", "f1g2", "activation"),
    ("AZ-35 Rxa6", "r1bqkb1r/2pn1p2/p3pn2/1p2P1B1/2pP4/2N5/PP3PBP/R2QK2R b - - 0 11", "a8a6", "activation"),
    ("AZ-34 Nxa4", "2kr4/1b2np2/p1p1p3/4P3/Ppp1P3/2N3P1/1P2BP2/2K4R w - - 0 24", "c3a4", "reposition"),
    ("AZ-34 Nxc6", "2kr4/1b2np2/p1p1p3/4P3/Npp1P3/6P1/1P2BP2/2K4R b - - 0 24", "e7c6", "reposition"),
    ("AZ-41 fxe4+", "8/1p3p2/2pk1r1p/r2p1p1P/P2PnK2/3BP1P1/2R2P2/1R6 b - - 0 75", "f5e4", "check"),
    ("AZ-40 axb7", "R7/1N6/P4b2/6k1/r6p/8/4K3/8 w - - 0 50", "a6b7", "promotion"),
    ("AZ-39 cxb7", "8/pBp3k1/1pP1b1p1/8/2P4b/8/P5P1/7K w - - 0 39", "c6b7", "promotion"),
    ("Kramnik bxc8=Q", "1bB5/1P6/8/3k4/8/8/6K1/8 w - - 0 2", "b7c8q", "promotion"),
    ("AZ-33 Kxf2", "r5k1/1p3p2/p1pn3r/3p4/PP1P2P1/3BPQ2/5PP1/R1R3Kq w - - 0 39", "g1f2", "escape"),
    ("AZ-33 Kxe3", "8/5pk1/QPp5/3p4/P2P4/4PK2/5r1r/8 w - - 0 53", "f3e3", "escape"),
    ("AZ-36 Kxg2", "3k4/1Q4P1/p3p3/1pq5/5b2/P7/6B1/6K1 w - - 0 45", "g1g2", "escape"),
    ("AZ-43 Kxf8", "5rk1/7Q/5b1R/5p2/3PnP2/8/7P/5qBK b - - 0 1", "g8f8", "escape"),
]


def validate():
    bad = 0
    for name, fen, u, want in PAPER:
        b, turn, ep = from_fen(fen)
        m = find(b, turn, ep, u)
        got = "ILLEGAL" if m is None else ("not a self-capture" if m.kind != "self" else classify(b, turn, ep, m))
        bad += got != want
        print("%s %-16s %-11s %s" % ("ok " if got == want else "BAD", name, want, "" if got == want else got))
    print("%d of %d match" % (len(PAPER) - bad, len(PAPER)))
    return bad


# ---- replaying games ---------------------------------------------------------------------------------------------

def replay(game):
    """Yield (ply, board, turn, ep, half, full, move) for every move of a game."""
    b, turn, ep, half = E.init_board(), "w", None, 0
    for ply, u in enumerate(game["moves"]):
        m = find(b, turn, ep, u)
        if m is None:
            raise ValueError("illegal move %s at ply %d" % (u, ply))
        yield ply, b, turn, ep, half, ply // 2 + 1, m
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)


def source(path):
    return os.path.basename(path).replace("games_", "").replace(".jsonl", "")


# ---- rule-switch searches ----------------------------------------------------------------------------------------

class Fsf:
    def __init__(self, ini, variant, nodes):
        self.nodes = nodes
        self.p = subprocess.Popen([FSF], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        for s in ("uci", "setoption name VariantPath value " + ini, "setoption name UCI_Variant value " + variant,
                  "setoption name Threads value 1", "setoption name Hash value 64", "isready"):
            self.send(s)
        self.wait("readyok")

    def send(self, s):
        self.p.stdin.write(s + "\n")

    def wait(self, tok):
        for line in self.p.stdout:
            if line.startswith(tok):
                return line

    def search(self, fen, nodes=None):
        self.send("ucinewgame"); self.send("position fen " + fen); self.send("go nodes %d" % (nodes or self.nodes))
        score = None
        for line in self.p.stdout:
            if line.startswith("info") and " score " in line:
                f = line.split(); i = f.index("score")
                score = int(f[i + 2]) if f[i + 1] == "cp" else (1 if int(f[i + 2]) > 0 else -1) * (30000 - abs(int(f[i + 2])))
            if line.startswith("bestmove"):
                return line.split()[1], score


_W = {}


def _init(ini, nodes):
    _W["on"], _W["off"] = Fsf(ini, "kramnik", nodes), Fsf(ini, "kramniknosc", nodes)


def _probe(job):
    fen, repeat = job["fen"], job["repeat"]
    on, son = _W["on"].search(fen)
    off, soff = _W["off"].search(fen)
    out = dict(job, best_on=on, score_on=son, best_off=off, score_off=soff)
    if repeat:      # noise floor: the same rules with 10% more nodes
        out["best_on2"], out["score_on2"] = _W["on"].search(fen, int(_W["on"].nodes * 1.1))
    return out


def label(p, margin=50):
    gain = p["score_on"] - p["score_off"]
    if p["sc_best"] and gain >= margin:
        return "direct"
    if not p["sc_best"] and p["best_on"] != p["best_off"] and abs(gain) >= margin:
        return "threat"
    return "differs" if p["best_on"] != p["best_off"] else "same"


# ---- census ------------------------------------------------------------------------------------------------------

def census(outdir, files, nodes, workers, every):
    os.makedirs(outdir, exist_ok=True)
    ini = os.path.join(outdir, "rules.ini")
    open(ini, "w").write(INI)
    scs, jobs, games = [], [], defaultdict(lambda: [0, 0, 0])     # games: [games, games with a self-capture, moves]
    for path in files:
        src = source(path)
        for gi, g in enumerate(map(json.loads, open(path))):
            had = False
            for ply, b, turn, ep, half, full, m in replay(g):
                games[src][2] += 1
                if ply >= g["book"] and ply >= 16 and ply % every == 0:
                    jobs.append({"src": src, "game": gi, "ply": ply, "phase": phase(b, full),
                                 "fen": to_fen(b, turn, ep, half, full), "repeat": len(jobs) % 10 == 0})
                if m.kind != "self":
                    continue
                had = True
                scs.append({"src": src, "game": gi, "ply": ply, "fen": to_fen(b, turn, ep, half, full),
                            "move": uci_of(m), "san": E.san_of(b, m, ep), "piece": b[m.frm][1],
                            "victim": b[m.to][1], "phase": phase(b, full), "motif": classify(b, turn, ep, m)})
            games[src][0] += 1; games[src][1] += had
    with open(os.path.join(outdir, "selfcaptures.jsonl"), "w") as f:
        for s in scs:
            f.write(json.dumps(s) + "\n")
    pos = []
    with Pool(workers, _init, (ini, nodes)) as pool, open(os.path.join(outdir, "positions.jsonl"), "w") as f:
        for p in pool.imap_unordered(_probe, jobs, chunksize=4):
            b, turn, ep = from_fen(p["fen"])
            m = find(b, turn, ep, p["best_on"])
            p["sc_best"] = bool(m and m.kind == "self")
            p["san_on"] = E.san_of(b, m, ep) if m else p["best_on"]
            if p["sc_best"]:
                p["motif"] = classify(b, turn, ep, m)
            p["label"] = label(p)
            f.write(json.dumps(p) + "\n"); f.flush()
            pos.append(p)
    open(os.path.join(outdir, "report.md"), "w").write(report(games, scs, pos, nodes))


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def report(games, scs, pos, nodes):
    L = ["# Self-capture census", "",
         "Games from `tools/uci_match.py --games`; rule-switch searches at %d nodes, one thread." % nodes, "",
         "## Self-captures played", "",
         "| Source | Games | With a self-capture | Moves | Self-captures | Share of moves |", "|---|---|---|---|---|---|"]
    for src, (n, had, moves) in sorted(games.items()):
        k = sum(1 for s in scs if s["src"] == src)
        L.append("| %s | %d | %s | %d | %d | %s |" % (src, n, pct(had, n), moves, k, pct(k, moves)))
    L += ["", "Paper (AlphaZero, about 1 min/move, castling allowed): 52.5% of games, 0.7% of moves.", ""]
    for title, key, order in (("Piece self-captured (the victim)", "victim", "pnbrq"),
                              ("Phase", "phase", ["opening", "middlegame", "endgame"]),
                              ("Motif", "motif", ["promotion", "escape", "king-walk", "king-other", "check",
                                                  "attack", "activation", "reposition"])):
        srcs = sorted(games)
        L += ["### " + title, "", "| %s | %s |" % (key, " | ".join(srcs)), "|---|" + "---|" * len(srcs)]
        for v in order:
            row = [pct(sum(1 for s in scs if s["src"] == src and s[key] == v),
                       sum(1 for s in scs if s["src"] == src)) for src in srcs]
            L.append("| %s | %s |" % (v, " | ".join(row)))
        L.append("")
        if key == "victim":
            L += ["Paper's victims: pawn 86.9%, bishop 5.3%, knight 4.5%, rook 2.3%, queen 1%.", ""]
    L += ["## Rule-switch searches", "",
          "Each sampled position is searched with self-capture on and off. **direct**: the best move is a "
          "self-capture worth at least 50 cp over the best play without self-capture. **threat**: the best move is "
          "not a self-capture but changes, and the evaluation moves at least 50 cp, because self-captures exist. "
          "**differs**: the best move changes by less than that. The noise floor repeats every tenth position with "
          "the rules on and 10% more nodes.", "",
          "| Phase | Positions | direct | threat | differs | same |", "|---|---|---|---|---|---|"]
    for ph in ("opening", "middlegame", "endgame", "all"):
        ps = [p for p in pos if ph == "all" or p["phase"] == ph]
        c = Counter(p["label"] for p in ps)
        L.append("| %s | %d | %s | %s | %s | %s |" % (ph, len(ps), pct(c["direct"], len(ps)), pct(c["threat"], len(ps)),
                                                    pct(c["differs"], len(ps)), pct(c["same"], len(ps))))
    rep = [p for p in pos if p["repeat"]]
    noise_move = sum(1 for p in rep if p["best_on2"] != p["best_on"])
    noise_big = sum(1 for p in rep if p["best_on2"] != p["best_on"] and abs(p["score_on2"] - p["score_on"]) >= 50)
    L += ["", "Noise floor (%d positions, same rules, 10%% more nodes): best move changes in %s, and also by 50+ cp in "
          "%s." % (len(rep), pct(noise_move, len(rep)), pct(noise_big, len(rep))), ""]
    direct = sorted((p for p in pos if p["label"] == "direct"), key=lambda p: -(p["score_on"] - p["score_off"]))
    L += ["## Example positions (direct, largest gain first, at most three per motif)", "",
          "| # | Source | Phase | Motif | Move | Gain (cp) | FEN |", "|---|---|---|---|---|---|---|"]
    per, n = Counter(), 0
    for p in direct:
        if per[p.get("motif")] >= 3 or n >= 20:
            continue
        per[p.get("motif")] += 1; n += 1
        L.append("| %d | %s | %s | %s | %s | %+d | `%s` |" % (n, p["src"], p["phase"], p.get("motif"), p["san_on"],
                                                             p["score_on"] - p["score_off"], p["fen"]))
    threat = sorted((p for p in pos if p["label"] == "threat"), key=lambda p: -abs(p["score_on"] - p["score_off"]))
    L += ["", "## Threat examples (largest evaluation change first)", "",
          "| # | Source | Phase | Best (on) | Best (off) | Change (cp) | FEN |", "|---|---|---|---|---|---|---|"]
    for i, p in enumerate(threat[:10], 1):
        L.append("| %d | %s | %s | %s | %s | %+d | `%s` |" % (i, p["src"], p["phase"], p["san_on"], p["best_off"],
                                                             p["score_on"] - p["score_off"], p["fen"]))
    return "\n".join(L) + "\n"


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("validate", "census"):
        raise SystemExit(__doc__)
    if a[0] == "validate":
        raise SystemExit(1 if validate() else 0)
    opts = {"--nodes": 200000, "--workers": 4, "--every": 4}
    for k in list(opts):
        if k in a:
            i = a.index(k); opts[k] = int(a[i + 1]); del a[i:i + 2]
    census(a[1], a[2:], opts["--nodes"], opts["--workers"], opts["--every"])


if __name__ == "__main__":
    main()
