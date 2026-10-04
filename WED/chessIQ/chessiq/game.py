"""chessIQ game state: history, draw rules, the GM opening book, the computer's draw offers and PGN.

Ported from the UI half of WED/kramnik_chess.html; no Qt here, so tests/test_game.py drives it headless.
"""
import json
import os
import random
import re
import time

from . import engine as E

BOOK_PLIES = 16
AI_NAME = "Kramnik (capture-anything/no-castle AI)"   # PGN name; loading treats any name with "AI" as the computer
# The gold searches 1.2 s in JavaScript; this port runs ~1.5x slower (same tree, same node counts), so 1.8 s buys
# the same search. He always plays at full strength -- there is no strength dial, by design.
THINK_S = 1.8
MAX_DEPTH = 12

_BOOK = None


def book():
    global _BOOK
    if _BOOK is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "book.json")) as f:
            _BOOK = json.load(f)
    return _BOOK


def _mem_path():
    return os.path.join(os.path.expanduser("~"), ".config", "chessiq", "bookmem.json")


def load_book_mem():
    try:
        with open(_mem_path()) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_book_mem(mem):
    try:
        os.makedirs(os.path.dirname(_mem_path()), exist_ok=True)
        with open(_mem_path(), "w") as f:
            json.dump(mem, f)
    except OSError:
        pass


def strip_checks(san):
    return san.replace("+", "").replace("#", "")


class Game:
    """mode: 'ai' (vs computer), 'human' (hotseat), 'self' (computer vs computer), 'net' (vs a remote player).
    human: the colour the local player has in 'ai' and 'net' modes."""

    def __init__(self, mode="ai", human="w", seed=None, book_mem=None):
        self.mode, self.human = mode, human
        self.board, self.turn, self.ep = E.init_board(), "w", None
        self.history = []          # dicts: m, board, ep, turn (before the move), san, self
        self.over = None           # None or {type: mate|stalemate|draw|resign, winner?, reason?}
        self.keys, self.half = [], 0
        self.offers = {"count": 0, "last_ply": -99}      # the computer's draw offers
        self.p_offer = {"pending": False, "last_ply": -99}  # the player's offer to the computer
        # VARIETY: each game walks the book from a fresh clock seed, and at every branch point avoids the choice
        # made last game (remembered across sessions in ~/.config/chessiq/bookmem.json)
        self.rand = random.Random(time.time_ns() if seed is None else seed)
        self.book_mem = load_book_mem() if book_mem is None else book_mem
        self.check_end()

    # ---- queries ----
    def legal(self):
        return E.legal_moves(self.board, self.turn, self.ep)

    def in_check(self):
        return E.in_check(self.board, self.turn)

    def board_at(self, ply):
        return self.board if ply >= len(self.history) else self.history[ply]["board"]

    def computer_to_move(self):
        if self.over:
            return False
        return self.mode == "self" or (self.mode == "ai" and self.turn != self.human)

    def local_to_move(self):
        """Can the person at this screen move now?"""
        if self.over or self.mode == "self":
            return False
        return self.mode == "human" or self.turn == self.human

    # ---- draw bookkeeping, rebuilt from history (keeps undo and PGN load trivially right) ----
    def rebuild_clocks(self):
        self.keys = [E.pos_key(E.init_board(), "w", None)]
        half = 0
        for i, h in enumerate(self.history):
            half = 0 if (h["board"][h["m"].frm][1] == "p" or h["m"].kind != "move") else half + 1
            nxt = self.history[i + 1] if i + 1 < len(self.history) else None
            if nxt:
                self.keys.append(E.pos_key(nxt["board"], nxt["turn"], nxt["ep"]))
            else:
                self.keys.append(E.pos_key(self.board, self.turn, self.ep))
        self.half = half

    def occurrences(self, key):
        return self.keys.count(key)

    def check_end(self):
        self.rebuild_clocks()
        if not self.legal():
            self.over = ({"type": "mate", "winner": E.opp(self.turn)} if self.in_check() else {"type": "stalemate"})
            return
        if self.occurrences(self.keys[-1]) >= 3:
            self.over = {"type": "draw", "reason": "threefold repetition"}
        elif self.half >= 100:
            self.over = {"type": "draw", "reason": "fifty-move rule"}
        elif E.insufficient_material(self.board):
            self.over = {"type": "draw", "reason": "insufficient material"}
        else:
            self.over = None

    # ---- moves ----
    def do_move(self, m):
        san = E.san_of(self.board, m, self.ep)
        self.history.append({"m": m, "board": self.board, "ep": self.ep, "turn": self.turn, "san": san,
                             "self": m.kind == "self"})
        self.board = E.apply_move(self.board, m)
        self.ep = m.dbl
        self.turn = E.opp(self.turn)
        self.check_end()
        return san

    def move_from_san(self, san):
        want = normalize_san(san)
        for m in self.legal():
            if normalize_san(E.san_of(self.board, m, self.ep)) == want:
                return m
        return None

    def undo(self):
        """Take back a move; vs the computer, back to the player's own turn."""
        if not self.history:
            return False
        while True:
            h = self.history.pop()
            self.board, self.ep, self.turn = h["board"], h["ep"], h["turn"]
            if not (self.mode == "ai" and self.turn != self.human and self.history):
                break
        self.over = None
        self.p_offer["pending"] = False
        self.check_end()
        return True

    # ---- the opening book of grandmaster games in which neither side castled ----
    def _book_key(self):
        return " ".join(strip_checks(h["san"]) for h in self.history)

    def book_move(self):
        if len(self.history) >= BOOK_PLIES:
            return None
        key = self._book_key()
        opts = book().get(key)
        if not opts:
            return None
        pool = opts
        if len(set(opts)) > 1 and key in self.book_mem:      # don't repeat last game's choice here
            rest = [o for o in opts if o != self.book_mem[key]]
            if rest:
                pool = rest
        want = pool[int(self.rand.random() * len(pool))]
        for m in self.legal():
            if strip_checks(E.san_of(self.board, m, self.ep)) == want:
                self.book_mem[key] = want
                save_book_mem(self.book_mem)
                return m
        return None

    def book_hints(self):
        """Every book continuation here, shown on the board so a human can follow the grandmasters too."""
        if self.over or len(self.history) >= BOOK_PLIES:
            return []
        wants = set(book().get(self._book_key(), ()))
        if not wants:
            return []
        return [m for m in self.legal() if strip_checks(E.san_of(self.board, m, self.ep)) in wants]

    def banned_keys(self):
        """Positions already seen twice: the engine must not stumble into a threefold while winning."""
        seen = {}
        for k in self.keys:
            seen[k] = seen.get(k, 0) + 1
        return [k for k, n in seen.items() if n >= 2]

    def think(self, cancel=None, t=THINK_S):
        return E.best_move(self.board, self.turn, self.ep, t=t, d=MAX_DEPTH, banned=self.banned_keys(), cancel=cancel)

    def ai_offers_draw(self, m):
        """Rather than silently shuffling into a threefold, he offers the draw like a real opponent."""
        if self.mode == "self" or self.offers["count"] >= 2 or len(self.history) - self.offers["last_ply"] < 20:
            return False
        v = m.v
        if v is None or v > 60:
            return False                                   # he still thinks he is better
        nk = E.pos_key(E.apply_move(self.board, m), E.opp(self.turn), m.dbl)
        rep_after = self.occurrences(nk) + 1
        if rep_after >= 3:
            return False                                   # already a draw by rule
        if rep_after == 2:
            return True                                    # steering for repetition / perpetual: offer instead
        return self.half >= 60 and abs(v) <= 30            # 30+ moves of no progress, dead level

    def ai_accepts_draw(self, m):
        """His answer to the player's offer: accept when he can't claim an edge and the game is out of its infancy."""
        return m is not None and m.v is not None and m.v <= 30 and len(self.history) >= 20

    # ---- PGN ----
    def result_str(self):
        if not self.over:
            return "*"
        if self.over["type"] in ("mate", "resign"):
            return "1-0" if self.over["winner"] == "w" else "0-1"
        return "1/2-1/2"

    def names(self, me="Player", them="Opponent"):
        if self.mode == "ai":
            return (me, AI_NAME) if self.human == "w" else (AI_NAME, me)
        if self.mode == "self":
            return AI_NAME, AI_NAME
        if self.mode == "net":
            return (me, them) if self.human == "w" else (them, me)
        return "White", "Black"

    def pgn(self, white="White", black="Black", site="local"):
        today = time.strftime("%Y.%m.%d")
        res = self.result_str()
        words = []
        for i, h in enumerate(self.history):
            if i % 2 == 0:
                words.append("%d." % (i // 2 + 1))
            words.append(h["san"])
        words.append(res)
        lines, line = [], ""
        for w in words:
            if len((line + " " + w).strip()) > 80:
                lines.append(line.strip())
                line = w
            else:
                line += " " + w
        lines.append(line.strip())
        hdr = ['[Event "Kramnik Chess Variant"]', '[Site "%s"]' % site, '[Date "%s"]' % today,
               '[White "%s"]' % white, '[Black "%s"]' % black, '[Result "%s"]' % res,
               '[Variant "Capture-anything / No-castling"]']
        return "\n".join(hdr) + "\n\n" + "\n".join(lines) + "\n"


def normalize_san(s):
    s = re.sub(r"[+#!?]", "", s)
    s = re.sub(r"\(self\)", "", s, flags=re.I)
    return re.sub(r"e\.p\.?", "", s, flags=re.I)


def pgn_headers(text):
    return dict(re.findall(r'\[(\w+)\s+"([^"]*)"\]', text))


def pgn_tokens(text):
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = re.sub(r";[^\n]*", " ", text)
    text = re.sub(r"\$\d+", " ", text)
    prev = None
    while prev != text:
        prev, text = text, re.sub(r"\([^()]*\)", " ", text)
    out = []
    for tk in text.split():
        tk = re.sub(r"^\d+\.(\.\.)?", "", tk)
        if not tk or re.fullmatch(r"1-0|0-1|1/2-1/2|\*", tk) or tk.isdigit():
            continue
        out.append(tk)
    return out


def load_pgn(text, mode=None, human=None):
    """A Game replaying the PGN (who played whom restored from the White/Black headers), plus the token it stopped
    at (None when every move was understood)."""
    hdr = pgn_headers(text)
    if mode is None:
        mode, human = "human", "w"
        if "White" in hdr or "Black" in hdr:
            w_ai = bool(re.search(r"\bAI\b", hdr.get("White", "")))
            b_ai = bool(re.search(r"\bAI\b", hdr.get("Black", "")))
            mode = "self" if (w_ai and b_ai) else "ai" if (w_ai or b_ai) else "human"
            human = "b" if (w_ai and not b_ai) else "w"
    g = Game(mode, human or "w")
    for tk in pgn_tokens(text):
        m = g.move_from_san(tk)
        if m is None:
            return g, tk
        g.do_move(m)
    return g, None
