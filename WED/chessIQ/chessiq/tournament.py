"""Tournaments, as Chessmaster's Play/Tournaments (EPIC CM, CM-21): round robin or Swiss, you against personalities.

* Round robin: Berger tables (the circle method); with an odd field one player has a bye each round. Colours
  alternate. Optionally double (everyone plays everyone twice, colours reversed).
* Swiss: each round pairs players with equal (or nearest) scores, the top half of a score group against the bottom
  half by rating; nobody meets the same opponent twice; colours go to whoever has had fewer whites; a bye (one point)
  goes to the lowest-ranked player who has not had one.
* Standings: points, then Sonneborn-Berger (round robin) or Buchholz (Swiss), then rating.
* Games between two computer opponents are played out by their engines at their own strength ("quick result").
"""
import random

from . import engine as E

BYE = None


class Tournament:
    def __init__(self, players, kind="rr", rounds=None, double=False, rated=False, seed=None, human=None):
        """players: [(name, rating)], your entry included. kind: 'rr' or 'swiss' (rounds required). human: your
        name -- in a Swiss event the bye goes to a computer opponent whenever one is eligible, so you get to play."""
        self.players = list(players)
        self.human = human
        self.rating = dict(players)
        self.kind, self.double, self.rated = kind, double, rated
        self.rnd = random.Random(seed)
        n = len(players)
        if kind == "rr":
            self.n_rounds = (n - 1 + n % 2) * (2 if double else 1)
        else:
            self.n_rounds = rounds or max(3, (n - 1).bit_length() + 1)
        self.rounds = []                        # [[(white, black)]]; black is BYE for a bye
        self.results = {}                       # (round, white, black) -> white's score (1, 0.5, 0)

    # ---- pairings ------------------------------------------------------------------------------------------------
    def pair_next(self):
        r = len(self.rounds)
        if r >= self.n_rounds:
            return None
        pairs = self._rr_round(r) if self.kind == "rr" else self._swiss_round()
        self.rounds.append(pairs)
        for w, b in pairs:
            if b is BYE:
                self.results[(r, w, BYE)] = 1.0
        return pairs

    def _rr_round(self, r):
        names = [p for p, _ in self.players]
        if len(names) % 2:
            names.append(BYE)
        n = len(names)
        single = n - 1
        k = r % single
        rot = names[1:]
        rot = rot[-k:] + rot[:-k] if k else rot
        ring = [names[0]] + rot
        pairs = []
        for i in range(n // 2):
            a, b = ring[i], ring[n - 1 - i]
            if i == 0 and k % 2:                 # the fixed player alternates colours
                a, b = b, a
            if r >= single:                      # second cycle of a double round robin: colours reversed
                a, b = b, a
            if a is BYE:
                a, b = b, a
            pairs.append((a, b))
        return pairs

    def _swiss_round(self):
        played = {p: set() for p, _ in self.players}
        byes = set()
        for rp in self.rounds:
            for w, b in rp:
                if b is BYE:
                    byes.add(w)
                else:
                    played[w].add(b); played[b].add(w)
        order = sorted((p for p, _ in self.players),
                       key=lambda p: (-self.points(p), -self.rating[p], p))
        pairs = []
        if len(order) % 2:                       # the bye: lowest-ranked player without one
            eligible = [p for p in reversed(order) if p not in byes]
            bye = next((p for p in eligible if p != self.human), eligible[0])
            order.remove(bye)
            pairs.append((bye, BYE))
        matched = self._match(order, played)
        if matched is None:                      # no rematch-free pairing exists: allow rematches
            matched = [(order[i], order[i + 1]) for i in range(0, len(order), 2)]
        return [self._colours(a, b) for a, b in matched] + pairs

    def _match(self, order, played):
        """Top half against bottom half within score groups, backtracking to avoid rematches."""
        if not order:
            return []
        first, rest = order[0], order[1:]
        same = [p for p in rest if self.points(p) == self.points(first)]
        half = len(same) // 2 if len(same) > 1 else 0
        prefer = same[half:] + same[:half] + [p for p in rest if p not in same]
        for opp in prefer:
            if opp in played[first]:
                continue
            tail = self._match([p for p in rest if p != opp], played)
            if tail is not None:
                return [(first, opp)] + tail
        return None

    def _colours(self, a, b):
        def whites(p):
            return sum(1 for rp in self.rounds for w, bl in rp if w == p and bl is not BYE)

        def blacks(p):
            return sum(1 for rp in self.rounds for w, bl in rp if bl == p)
        da, db = whites(a) - blacks(a), whites(b) - blacks(b)
        if da != db:
            return (a, b) if da < db else (b, a)
        return (a, b) if self.rnd.random() < 0.5 else (b, a)

    # ---- results and standings ----------------------------------------------------------------------------------
    def record(self, r, white, black, score):
        self.results[(r, white, black)] = score

    def pending(self, r=None):
        r = len(self.rounds) - 1 if r is None else r
        return [(w, b) for w, b in self.rounds[r] if b is not BYE and (r, w, b) not in self.results]

    def games_of(self, p):
        """[(round, opponent or BYE, score)] for player p."""
        out = []
        for (r, w, b), s in sorted(self.results.items(), key=lambda kv: kv[0][0]):
            if w == p:
                out.append((r, b, s))
            elif b == p:
                out.append((r, w, 1 - s))
        return out

    def points(self, p):
        return sum(s for _, _, s in self.games_of(p))

    def tiebreak(self, p):
        games = [(o, s) for _, o, s in self.games_of(p) if o is not BYE]
        if self.kind == "rr":
            return sum(s * self.points(o) for o, s in games)        # Sonneborn-Berger
        return sum(self.points(o) for o, _ in games)              # Buchholz

    def standings(self):
        return sorted(((p, self.points(p), self.tiebreak(p)) for p, _ in self.players),
                      key=lambda x: (-x[1], -x[2], -self.rating[x[0]], x[0]))

    def crosstable(self):
        """{player: {opponent: [scores]}} -- a double round robin has two entries per opponent."""
        t = {p: {} for p, _ in self.players}
        for p, _ in self.players:
            for _, o, s in self.games_of(p):
                if o is not BYE:
                    t[p].setdefault(o, []).append(s)
        return t

    def finished(self):
        return len(self.rounds) == self.n_rounds and not self.pending()


def play_out(white_engine, black_engine, max_plies=300):
    """A computer-vs-computer game played by the two engines at their own strength. Returns White's score."""
    b, turn, ep, moves, seen, half = E.init_board(), "w", None, [], {}, 0
    while True:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            return (0.0 if turn == "w" else 1.0) if E.in_check(b, turn) else 0.5
        key = E.pos_key(b, turn, ep)
        seen[key] = seen.get(key, 0) + 1
        if E.insufficient_material(b) or seen[key] >= 3 or half >= 100 or len(moves) >= max_plies:
            return 0.5
        u = (white_engine if turn == "w" else black_engine).choose(moves)
        m = next((m for m in legal if E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "") == u), None)
        if m is None:                            # an engine failed: the game is scored as a draw, not invented
            return 0.5
        half = 0 if (b[m.frm][1] == "p" or m.kind != "move") else half + 1
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        moves.append(E.sqname(m.frm) + E.sqname(m.to) + (m.promo or ""))


def to_dict(t, extra=None):
    """A JSON-able snapshot (the tournament in progress is saved after every result)."""
    return {"players": t.players, "kind": t.kind, "double": t.double, "rated": t.rated, "n_rounds": t.n_rounds,
            "human": t.human, "rounds": [[[w, b] for w, b in rp] for rp in t.rounds],
            "results": [[r, w, b, s] for (r, w, b), s in t.results.items()], "extra": extra or {}}


def from_dict(d):
    t = Tournament([tuple(p) for p in d["players"]], d["kind"], rounds=d["n_rounds"], double=d["double"],
                   rated=d["rated"], human=d.get("human"))
    t.n_rounds = d["n_rounds"]
    t.rounds = [[(w, b) for w, b in rp] for rp in d["rounds"]]
    t.results = {(r, w, b): s for r, w, b, s in d["results"]}
    return t, d.get("extra", {})
