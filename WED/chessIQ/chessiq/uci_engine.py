"""The Kramnik Fairy-Stockfish (engine/) playing as a chosen personality (EPIC CM, sprint CM-3).

One engine process per opponent. Rating, style, contempt and material go in as UCI options
(Personality.engine_options); two Chessmaster knobs are applied here instead:
  * randomness (0..100): the engine reports its best few moves (MultiPV), and with probability randomness/200 a
    move within (10 + 2 x randomness) centipawns of the best is played instead of the best. Randomness is variety,
    never chaos (CM-17): at 100 half the moves are drawn from the lines within about two pawns. Weakness below the
    ladder's floor comes from the measured blunder rate (CM-14), and a style's cost in strength is paid back in
    search nodes (Personality.search_nodes);
  * max depth (< 99): the search is limited to that many plies.
available() is False when the binary has not been built (engine/build_engine.sh); chessIQ then falls back to its
own Python engine.
"""
import os
import random
import subprocess
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.environ.get("CHESSIQ_ENGINE", os.path.join(ROOT, "engine", "fairy-stockfish-kramnik"))
VARIANTS = os.path.join(ROOT, "engine", "kramnik.ini")


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
            elif movetime_ms:
                go += " movetime %d" % movetime_ms
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
        r = self.rnd_level
        if r > 0 and len(lines) > 1 and self.rand.random() < r / 200:
            top = max(cp for cp, _ in lines.values())
            near = [mv for cp, mv in lines.values() if top - cp <= 10 + 2 * r and mv != best]
            if near:
                return self.rand.choice(near)
        return best

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
        try:
            self._send("quit")
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


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
            elif movetime_ms:
                go += " movetime %d" % movetime_ms
            self._send(go)
            for line in self.proc.stdout:
                if line.startswith("bestmove"):
                    best = line.split()[1]
                    break
            else:
                return None           # closed under us (a new game or opponent): the result is discarded anyway
        return None if best in ("(none)", "0000") else best
