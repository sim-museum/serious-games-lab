"""Chess clocks (EPIC CM, sprint CM-5): the time controls Chessmaster offers, minus seconds-per-move and hourglass.

  untimed                  no clock (training only; Chessmaster's ranked play has no infinite time either)
  fischer  base, inc       base minutes each, inc seconds added after every move (10+3 = Fischer 10 minutes, 3 s)
  game     base            base minutes for the whole game ("minutes per game")
  moves    n, base         n moves in base minutes, repeating ("moves/minutes"); unused time carries over

Times are kept in milliseconds. `now` is injectable so tests can drive the clock without waiting.
"""
import time

PRESETS = [   # (label, kind, args)
    ("Untimed", "untimed", ()),
    ("Fischer 10+3", "fischer", (10, 3)),
    ("Fischer 5+3", "fischer", (5, 3)),
    ("Fischer 15+10", "fischer", (15, 10)),
    ("Fischer 3+2", "fischer", (3, 2)),
    ("30 minutes per game", "game", (30,)),
    ("40 moves in 90 minutes", "moves", (40, 90)),
]


class Clock:
    def __init__(self, kind="untimed", args=(), now=None):
        self.kind, self.args = kind, tuple(args)
        self.now = now or (lambda: time.monotonic() * 1000.0)
        base = 0
        if kind in ("fischer", "game"):
            base = args[0] * 60000
        elif kind == "moves":
            base = args[1] * 60000
        self.left = {"w": float(base), "b": float(base)}
        self.moves = {"w": 0, "b": 0}
        self.running = None       # colour whose clock runs
        self.since = None
        self.flagged = None

    @property
    def timed(self):
        return self.kind != "untimed"

    @property
    def increment_ms(self):
        return self.args[1] * 1000 if self.kind == "fischer" else 0

    def start(self, colour):
        """Start (or resume) colour's clock."""
        if not self.timed or self.flagged:
            return
        self.running, self.since = colour, self.now()

    def stop(self):
        """Pause: charge the running side, keep its turn."""
        if self.running is not None:
            self._charge()
            self.running = None

    def _charge(self):
        t = self.now()
        c = self.running
        self.left[c] -= t - self.since
        self.since = t
        if self.left[c] <= 0:
            self.left[c] = 0.0
            if self.flagged is None:
                self.flagged = c

    def remaining(self, colour):
        """Time left for colour now, in ms (the running side's clock is live)."""
        if not self.timed:
            return None
        if colour == self.running:
            return max(0.0, self.left[colour] - (self.now() - self.since))
        return self.left[colour]

    def check_flag(self):
        """The colour that has run out of time, or None."""
        if self.timed and self.running is not None and self.flagged is None and self.remaining(self.running) <= 0:
            self._charge()
        return self.flagged

    def moved(self, colour):
        """colour has just completed a move: charge it, add the increment or the next time block, start the other."""
        if not self.timed:
            return None
        if self.running == colour:
            self._charge()
        if self.flagged:
            return self.flagged
        self.moves[colour] += 1
        if self.kind == "fischer":
            self.left[colour] += self.increment_ms
        elif self.kind == "moves" and self.moves[colour] % self.args[0] == 0:
            self.left[colour] += self.args[1] * 60000
        other = "b" if colour == "w" else "w"
        self.start(other)
        return None

    def uci(self):
        """The engine's view: wtime/btime/winc/binc in whole ms (movestogo is left to the engine's own estimate)."""
        return {"wtime": int(self.remaining("w")), "btime": int(self.remaining("b")),
                "winc": int(self.increment_ms), "binc": int(self.increment_ms)}


def fmt(ms):
    if ms is None:
        return ""
    s = int(ms // 1000)
    if ms < 10000:
        return "%d.%d" % (s, int(ms % 1000) // 100)
    return "%d:%02d" % (s // 60, s % 60)
