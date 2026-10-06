"""Opponents with a rating and a playing style, the way Chessmaster has them (EPIC CM, sprint CM-2).

Two sources:
  * the player's own Chessmaster installation, read at run time (188 personalities). Their names, styles and
    biographies are Ubisoft's and are never copied into this repository;
  * chessIQ's own roster below, used when Chessmaster is not installed.

A Chessmaster personality (Data/Personalities/*.CMP, 3,104 bytes) is a 32-byte title, 38 little-endian int32
parameters from offset 0x20, the opening book name at 0xC0, the picture at 0x1C4, the style line at 0x1E2
and the biography after it. The
parameters, as decoded on 2026-10-06 from all 188 files (see docs/EPICS.md):
   6 rating                        9 strength %            10 randomness           12 max depth (99 = none)
  13 selective search              14 contempt (cp)        8 attack (-100..100, negative = attacker; inferred)
  15 material/positional balance (inferred, not used yet)
  16..25 positional weights in own/opponent pairs, percent: centre, mobility, king safety, passed pawns, pawn
         weakness (the order is inferred from the style lines, e.g. "overlooks pawns" -> pawn weakness 36)
  26..35 material in own/opponent pairs, tenths of a pawn: queen, rook, bishop, knight, pawn
"""
import glob
import os
import re
import struct
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
WED = os.path.dirname(os.path.dirname(HERE))

TERMS = ("Centre", "Mobility", "KingSafety", "PassedPawns", "PawnWeakness")
PIECES = ("Queen", "Rook", "Bishop", "Knight", "Pawn")
BASE = {"Queen": 90, "Rook": 50, "Bishop": 30, "Knight": 30, "Pawn": 10}     # Chessmaster's own values, tenths

# The engine's strength limiter separates levels more steeply than its Elo labels (CM-3, 2026-10-06): a labelled
# 1600 scored 88% against a 1400 at 500 ms a move (the formula expects 76%: an effective gap of ~345 for 200), and
# 40-0 at 400 apart at 50 ms. So a personality's rating is compressed around the club middle before it reaches the
# engine. PROVISIONAL: re-measure at the real time controls (CM-5), where thinking time changes the slope.
ELO_ANCHOR, ELO_SCALE = 1500, 0.58


def engine_elo(rating):
    return round(ELO_ANCHOR + (rating - ELO_ANCHOR) * ELO_SCALE)


@dataclass
class Personality:
    name: str
    rating: int
    style: str = ""
    bio: str = ""
    strength: int = 100          # percent
    randomness: int = 0          # 0..100
    max_depth: int = 99          # 99 = no limit
    contempt: int = 0            # centipawns; > 0 avoids draws
    attack: int = 0              # -100..100; > 0 = attacker (engine convention)
    positional: dict = field(default_factory=lambda: {t: (100, 100) for t in TERMS})   # (own, opp) percent
    material: dict = field(default_factory=lambda: {p: (BASE[p], BASE[p]) for p in PIECES})  # (own, opp) tenths
    book: str = ""
    source: str = "chessIQ"

    def engine_options(self):
        """UCI options for the Kramnik Fairy-Stockfish (engine/kramnik-selfcapture.patch)."""
        o = {}
        for t in TERMS:
            own, opp = self.positional[t]
            o["CM %s Own" % t], o["CM %s Opp" % t] = own, opp
        for p in PIECES:
            own, opp = self.material[p]
            o["CM %s Own" % p] = round(own * 100 / BASE[p])
            o["CM %s Opp" % p] = round(opp * 100 / BASE[p])
        o["CM Contempt"] = self.contempt
        o["CM Attack"] = max(-100, min(100, self.attack))
        if self.rating < 2850:
            o["UCI_LimitStrength"] = "true"
            o["UCI_Elo"] = max(500, min(2850, engine_elo(self.rating)))
        else:
            o["UCI_LimitStrength"] = "false"
        return o


def chessmaster_dir():
    """The player's Chessmaster installation, if any: $CHESSIQ_CHESSMASTER, else WED/chessmaster/WP."""
    env = os.environ.get("CHESSIQ_CHESSMASTER")
    cands = [env] if env else []
    for pf in ("Program Files (x86)", "Program Files"):
        cands.append(os.path.join(WED, "chessmaster", "WP", "drive_c", pf, "Ubisoft", "Chessmaster Grandmaster Edition"))
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "Data", "Personalities")):
            return c
    return None


def _cstr(b):
    return b.split(b"\0")[0].decode("latin-1")


def read_cmp(path):
    b = open(path, "rb").read()
    if len(b) < 0x1E4 or not b.startswith(b"Chessmaster"):
        raise ValueError("not a Chessmaster personality: " + path)
    v = struct.unpack_from("<38i", b, 0x20)
    style = _cstr(b[0x1E2:0x1E2 + 0x40])                         # e.g. "Avoids draws, neglects King"
    texts = [t.decode("latin-1") for t in re.findall(rb"[\x20-\x7e\x80-\xff]{40,}", b[0x1E2 + len(style) + 1:])]
    bio = max(texts, key=len) if texts else ""
    pos = {t: (v[16 + 2 * i], v[17 + 2 * i]) for i, t in enumerate(TERMS)}
    mat = {p: (v[26 + 2 * i], v[27 + 2 * i]) for i, p in enumerate(PIECES)}
    return Personality(name=os.path.splitext(os.path.basename(path))[0], rating=v[6], style=style.strip(), bio=bio,
                       strength=v[9], randomness=v[10], max_depth=v[12], contempt=v[14], attack=-v[8],
                       positional=pos, material=mat, book=_cstr(b[0xC0:0xE0]), source="Chessmaster")


def load_chessmaster(directory=None):
    d = directory or chessmaster_dir()
    if not d:
        return []
    out = []
    for f in sorted(glob.glob(os.path.join(d, "Data", "Personalities", "*.CMP"))):
        try:
            out.append(read_cmp(f))
        except (OSError, ValueError, struct.error):
            continue
    return out


def _p(name, rating, style, **kw):
    return Personality(name=name, rating=rating, style=style, **kw)


# chessIQ's own opponents (original text), spread over the rating range, each with a recognisable style.
ROSTER = [
    _p("Pip", 800, "a beginner who grabs whatever is offered", randomness=30,
       material={**{p: (BASE[p], BASE[p]) for p in PIECES}, "Pawn": (10, 14)}),
    _p("Morgan", 1150, "steady and careful; trades when in doubt", randomness=15, attack=-30,
       positional={**{t: (100, 100) for t in TERMS}, "KingSafety": (140, 90)}),
    _p("Ines", 1400, "loves the bishop pair and open lines", randomness=10,
       material={**{p: (BASE[p], BASE[p]) for p in PIECES}, "Bishop": (36, 30)},
       positional={**{t: (100, 100) for t in TERMS}, "Mobility": (130, 100)}),
    _p("Tomas", 1650, "a pawn snatcher who defends what he took", randomness=8, attack=-20,
       material={**{p: (BASE[p], BASE[p]) for p in PIECES}, "Pawn": (11, 13)}),
    _p("Yara", 1900, "an attacker who goes for the king", randomness=6, attack=40, contempt=50,
       positional={**{t: (100, 100) for t in TERMS}, "KingSafety": (90, 140)}),
    _p("Lev", 2150, "positional; squeezes with space and structure", randomness=4, contempt=20,
       positional={**{t: (100, 100) for t in TERMS}, "Centre": (140, 110), "PawnWeakness": (120, 130)}),
    _p("Odile", 2400, "a passed-pawn endgame specialist", randomness=2,
       positional={**{t: (100, 100) for t in TERMS}, "PassedPawns": (150, 130)}),
    _p("The Engine", 2850, "full strength, no style, no mercy"),
]


def roster():
    """Chessmaster's personalities when installed, otherwise chessIQ's own."""
    return load_chessmaster() or list(ROSTER)


def by_name():
    """Every personality by name, Chessmaster's and chessIQ's own (for tools and tests)."""
    out = {p.name: p for p in ROSTER}
    out.update({p.name: p for p in load_chessmaster()})
    return out
