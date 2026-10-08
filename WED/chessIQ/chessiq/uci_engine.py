"""The Kramnik Fairy-Stockfish (engine/) playing as a chosen personality (EPIC CM, sprint CM-3).

One engine process per opponent. Rating, style, contempt and material go in as UCI options
(Personality.engine_options); two Chessmaster knobs are applied here instead:
  * randomness (0..100): the engine reports its best few moves (MultiPV), and with probability randomness/200 a
    move within (10 + 2 x randomness) centipawns of the best is played instead of the best. Randomness is variety,
    never chaos (CM-17): at 100 half the moves are drawn from the lines within about two pawns. Weakness below the
    ladder's floor comes from the measured blunder rate (CM-14), and a style's cost in strength is paid back in
    search nodes (Personality.search_nodes);
  * max depth (< 99): the search is limited to that many plies.
  * kansas (0..100, EPIC KS): a self-capture specialist's appetite. Among the moves within (10 + kansas/2) cp of the
    best, it plays the one that gains most from Kramnik rules: its score with self-capture on, plus kansas% of (score
    on - score off), where "off" is a second engine playing the same position without self-capture. A self-capture,
    which does not exist off, gains SC_BONUS. The specialist still never plays a move outside that margin.
available() is False when the binary has not been built (engine/build_engine.sh); chessIQ then falls back to its
own Python engine.
"""
import os
import random
import subprocess
import threading

from . import kansas as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.environ.get("CHESSIQ_ENGINE", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))
VARIANTS = os.path.join(ROOT, "engine", "kramnik.ini")
SC_BONUS = 100                  # cp: what a self-capture "gains" from Kramnik rules in a specialist's eyes
DEFAULT_MS = 1000               # a full-strength opponent with no clock and no move time (tournament quick results)


def available():
    return os.access(BINARY, os.X_OK) and os.path.exists(VARIANTS)


class PersonalityEngine:
    def __init__(self, personality, seed=None):
        self.p = personality
        self.rand = random.Random(seed)
        self.lock = threading.Lock()
        self.proc = subprocess.Popen([BINARY], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._send("uci"); self._wait("uciok")
        self._send("setoption name VariantPath value " + VARIANTS)
        self._send("setoption name UCI_Variant value kramnik")
        for k, v in personality.engine_options().items():
            self._send("setoption name %s value %s" % (k, v))
        self.rnd_level = personality.total_randomness() if hasattr(personality, "total_randomness") else personality.randomness
        self.blunder = personality.blunder_rate() if hasattr(personality, "blunder_rate") else 0.0
        self.nodes = personality.search_nodes() if hasattr(personality, "search_nodes") else 0
        self.multipv = 4 if self.rnd_level > 0 else 1
        self.kansas = getattr(personality, "kansas", 0)
        if self.kansas > 0:
            self.multipv = max(self.multipv, 6)
        self.off = None                     # the no-self-capture engine, started on a specialist's first move
        self.last_kansas = None             # (chosen, best, gain) of the last move the appetite changed, for tests
        self._send("setoption name MultiPV value %d" % self.multipv)
        self._send("isready"); self._wait("readyok")

    def _send(self, s):
        self.proc.stdin.write(s + "\n")
        self.proc.stdin.flush()

    def _wait(self, tok):
        for line in self.proc.stdout:
            if line.startswith(tok):
                return line
        raise RuntimeError("engine ended")

    def new_game(self):
        with self.lock:
            self._send("ucinewgame"); self._send("isready"); self._wait("readyok")

    def stop(self):
        try:
            self._send("stop")
        except (OSError, ValueError):
            pass

    def choose(self, moves, movetime_ms=None, clock=None):
        """moves: the game so far in UCI from the start position. clock: dict(wtime, btime, winc, binc) in ms.
        Returns the UCI move to play, or None if the engine has none (mate or stalemate)."""
        with self.lock:
            self._send("position startpos" + (" moves " + " ".join(moves) if moves else ""))
            go = "go"
            if self.p.max_depth and self.p.max_depth < 99:
                go += " depth %d" % self.p.max_depth
            if self.nodes:                  # the measured strength ladder (CM-8): a fixed node count per rating
                go += " nodes %d" % (self.nodes * self.multipv)   # CM-17: each listed line gets the full search
            elif clock:
                go += " wtime %d btime %d winc %d binc %d" % (clock["wtime"], clock["btime"], clock["winc"], clock["binc"])
            else:                           # never a bare "go": that searches forever
                go += " movetime %d" % (movetime_ms or DEFAULT_MS)
            self._send(go)
            lines = {}
            for line in self.proc.stdout:
                if line.startswith("info") and " multipv " in line and " pv " in line and " score " in line:
                    t = line.split()
                    k = int(t[t.index("multipv") + 1])
                    s = t[t.index("score") + 1:t.index("score") + 3]
                    cp = int(s[1]) if s[0] == "cp" else (100000 - abs(int(s[1]))) * (1 if int(s[1]) > 0 else -1)
                    lines[k] = (cp, t[t.index("pv") + 1])
                elif line.startswith("bestmove"):
                    best = line.split()[1]
                    break
            else:
                return None           # the engine was closed under us (a new game or opponent): nothing to play
        if best in ("(none)", "0000"):
            return None
        if self.blunder > 0 and self.rand.random() < self.blunder:     # below the floor (CM-14)
            root = self._root_moves(moves)
            if root:
                return self.rand.choice(sorted(root))
        if self.kansas > 0 and len(lines) > 1:
            pick = self._kansas_pick(moves, lines, best)
            if pick and pick != best:
                return pick
        r = self.rnd_level
        if r > 0 and len(lines) > 1 and self.rand.random() < r / 200:
            top = max(cp for cp, _ in lines.values())
            near = [mv for cp, mv in lines.values() if top - cp <= 10 + 2 * r and mv != best]
            if near:
                return self.rand.choice(near)
        return best

    def _kansas_pick(self, moves, lines, best):
        top = max(cp for cp, _ in lines.values())
        window, reach = 10 + self.kansas // 2, getattr(self.p, "reach", 0)
        b, turn, ep, half, full = K.replay(moves)
        own = set(filter(None, getattr(self.p, "motif", "").split(",")))

        def own_sc(mv):
            return own and K.is_self_capture(b, turn, mv) and K.motif(b, turn, ep, K.find(b, turn, ep, mv)) in own

        # KS-10: a specialist's own motif may trail by `reach` more, and gets that much more bonus: a motif the
        # position seldom offers at no cost (an escape, a king walk) is played at a price, which `adjust` pays back
        cands = [(cp, mv) for cp, mv in lines.values()
                 if top - cp <= window or (reach and top - cp <= window + reach and own_sc(mv))]
        if len(cands) < 2:
            return None
        sc = {mv for _, mv in cands if K.is_self_capture(b, turn, mv)}
        off = self._off_scores(K.to_fen(b, turn, ep, half, full), [mv for _, mv in cands if mv not in sc])

        bonus = {mv: SC_BONUS + reach * 100 // max(1, self.kansas) if own_sc(mv) else SC_BONUS if not own
                 else SC_BONUS // 4 for mv in sc}   # a specialist's own motif gets the full bonus, others a quarter

        def gain(cp, mv):
            return bonus[mv] if mv in sc else (K.cap(cp) - K.cap(off[mv]) if mv in off else 0)

        cp, mv = max(cands, key=lambda c: c[0] + self.kansas / 100.0 * gain(*c))
        if mv != best:
            self.last_kansas = (mv, best, gain(cp, mv))
        return mv

    def _off_scores(self, fen, cands):
        """Scores of the candidate moves under the same rules without self-capture (same personality knobs)."""
        if not cands:
            return {}
        if self.off is None:
            self.off = subprocess.Popen([BINARY], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
            for c in ["uci", "setoption name VariantPath value " + VARIANTS, "setoption name UCI_Variant value kramniknosc"] + \
                     ["setoption name %s value %s" % kv for kv in self.p.engine_options().items()]:
                self.off.stdin.write(c + "\n")
        w = self.off.stdin.write
        w("setoption name MultiPV value %d\n" % len(cands))
        w("position fen %s\n" % fen)
        w("go nodes %d searchmoves %s\n" % ((self.nodes or 100000) * len(cands), " ".join(cands)))
        self.off.stdin.flush()
        out = {}
        for line in self.off.stdout:
            if line.startswith("info") and " multipv " in line and " pv " in line and " score " in line:
                t = line.split()
                s = t[t.index("score") + 1:t.index("score") + 3]
                out[t[t.index("pv") + 1]] = int(s[1]) if s[0] == "cp" else (100000 - abs(int(s[1]))) * (1 if int(s[1]) > 0 else -1)
            elif line.startswith("bestmove"):
                break
        return out

    def _root_moves(self, moves):
        """The legal moves, as Fairy-Stockfish lists them (`go perft 1`; proven against the rules in test_fsf_moves)."""
        with self.lock:
            self._send("position startpos" + (" moves " + " ".join(moves) if moves else ""))
            self._send("go perft 1")
            out = []
            for line in self.proc.stdout:
                if line.startswith("Nodes searched"):
                    return out
                tok = line.split(":")[0].strip()
                if ":" in line and 4 <= len(tok) <= 5:
                    out.append(tok)
        return out

    def close(self):
        if getattr(self, "off", None) is not None:
            try:
                self.off.stdin.write("quit\n"); self.off.stdin.flush(); self.off.wait(timeout=3)
            except Exception:
                self.off.kill()
            for f in (self.off.stdin, self.off.stdout):
                try:
                    f.close()
                except Exception:
                    pass
        try:
            self._send("quit")
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()
        for f in (self.proc.stdin, self.proc.stdout):      # closed explicitly: a dead engine's pipe must not be
            try:                                           # flushed later by the garbage collector
                f.close()
            except Exception:
                pass


# ---- Leela (lc0) opponents: the Kramnik lc0 with a network (EPIC NN, sprint NN-6) ---------------------------------
LC0_GPU = os.path.join(ROOT, "engine", "lc0-kramnik-gpu")          # engine/build_lc0_gpu.sh (NN-9): ~100x faster
LC0 = os.environ.get("CHESSIQ_LC0") or (LC0_GPU if os.access(LC0_GPU, os.X_OK) else os.path.join(ROOT, "engine", "lc0-kramnik"))
LC0_BACKEND = "cuda-fp16" if LC0 == LC0_GPU else "blas"
NETS = os.path.join(ROOT, "engine", "nets")


def leela_available(net):
    return os.access(LC0, os.X_OK) and bool(net) and os.path.exists(net)


class LeelaEngine(PersonalityEngine):
    """Same interface as PersonalityEngine, played by lc0 (Kramnik build) with personality.net. Randomness comes from
    lc0's own move temperature; strength from the network and the node limit (personality.nodes)."""

    def __init__(self, personality, seed=None):
        self.p = personality
        self.rand = random.Random(seed)
        self.lock = threading.Lock()
        args = [LC0, "--weights=" + personality.net, "--backend=" + LC0_BACKEND, "--threads=2"]
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, bufsize=1)
        self._send("uci"); self._wait("uciok")
        if personality.randomness:
            self._send("setoption name Temperature value %.2f" % (personality.randomness / 100.0))
            self._send("setoption name TempDecayMoves value 0")
        self.multipv = 1
        self._send("isready"); self._wait("readyok")

    def choose(self, moves, movetime_ms=None, clock=None):
        with self.lock:
            self._send("position startpos" + (" moves " + " ".join(moves) if moves else ""))
            go = "go"
            if getattr(self.p, "nodes", 0):
                go += " nodes %d" % self.p.nodes
            elif clock:
                go += " wtime %d btime %d winc %d binc %d" % (clock["wtime"], clock["btime"], clock["winc"], clock["binc"])
            else:
                go += " movetime %d" % (movetime_ms or DEFAULT_MS)
            self._send(go)
            for line in self.proc.stdout:
                if line.startswith("bestmove"):
                    best = line.split()[1]
                    break
            else:
                return None           # closed under us (a new game or opponent): the result is discarded anyway
        return None if best in ("(none)", "0000") else best
