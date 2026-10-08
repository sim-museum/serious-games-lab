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

# Strength (CM-8, 2026-10-06). The engine's own Elo limiter does not hold its labels in Kramnik chess (12-0 between
# a labelled 1600 and 1400), so strength is set by search nodes on a MEASURED ladder: 26 matches of 40 games between
# Fairy-Stockfish node levels, fitted jointly (Bradley-Terry): about 195 Elo per doubling of nodes, with a floor
# below ~45 nodes. Anchor: Maia 1500 (a network that moves like 1500-rated humans, one node) placed itself at the
# same point against 64, 181 and 512 nodes; that point is rating 1500.  (nodes, rating) along the ladder:
LADDER = [(16, 1163), (64, 1272), (128, 1493), (181, 1597), (256, 1691), (362, 1766), (1024, 1983), (1448, 2090),
          (2048, 2160), (2896, 2350), (4096, 2497), (5793, 2656), (8192, 2702), (11585, 2872), (16384, 2962),
          (65536, 3300)]
FLOOR = LADDER[0][1]


# Below the floor (CM-14): 16 nodes, and with probability p a uniformly random legal move instead of the engine's.
# (p, rating), measured: 13 matches of 100 games, Bradley-Terry with p = 0 pinned at the floor
# (docs/calibration/floor_blunder_ladder.txt). p = 1 is a random mover, about -327; Chessmaster's weakest (1) is p ~ 0.66.
BLUNDER_LADDER = [(0.0, 1163), (0.05, 992), (0.10, 920), (0.20, 758), (0.35, 499), (0.50, 226), (0.75, -87), (1.0, -327)]


def blunder_for(rating):
    if rating >= FLOOR:
        return 0.0
    for (p0, r0), (p1, r1) in zip(BLUNDER_LADDER, BLUNDER_LADDER[1:]):
        if rating >= r1:
            return p0 + (p1 - p0) * (r0 - rating) / max(1, r0 - r1)
    return BLUNDER_LADDER[-1][0]


def style_features(p):
    """How far a personality's knobs sit from neutral: attack, positional, material, randomness (CM-17)."""
    pos = sum(abs(a - 100) + abs(b - 100) for a, b in p.positional.values()) / 100
    mat = sum(abs(a - BASE[q]) / BASE[q] + abs(b - BASE[q]) / BASE[q] for q, (a, b) in p.material.items())
    return abs(p.attack) / 100, pos, mat, min(100, p.randomness) / 100


# Elo a style costs per unit of each feature, measured (CM-17): 16 Chessmaster personalities, 100 games each against a
# neutral opponent of the same rating, weighted non-negative least squares, chi2/dof 0.70
# (docs/calibration/style_costs.txt). Attack is free; any randomness at all switches the engine to four lines at four
# times the nodes, which plays better (STYLE_RANDOM_ON), while the deliberate deviations cost in proportion.
STYLE_COST = (0.0, 11.0, 113.0, 387.0)
STYLE_RANDOM_ON = -236.0
# Elo per point of self-capture appetite (KS-1): appetite 50 and 100 against a neutral twin, 40 games each at 1200,
# 1800 and 2400, scored 47.5% and 31.6% on average (docs/calibration/kansas_cost.txt).
KANSAS_COST = 1.3


def style_cost(p):
    f = style_features(p)
    k = getattr(p, "kansas", 0)          # an appetite's measured cost already includes its many-lines search
    return (sum(c * x for c, x in zip(STYLE_COST, f)) + (STYLE_RANDOM_ON if f[3] > 0 and not k else 0.0)
            + KANSAS_COST * k)


def level_for(rating):
    """(nodes, blunder probability) that play at `rating`: nodes on the measured ladder above the floor; below it 16
    nodes and a measured rate of random moves (CM-14)."""
    if rating <= FLOOR:
        return LADDER[0][0], blunder_for(rating)
    for (n0, r0), (n1, r1) in zip(LADDER, LADDER[1:]):
        if rating <= r1:
            t = (rating - r0) / max(1, r1 - r0)
            return round(n0 * (n1 / n0) ** t), 0.0
    return LADDER[-1][0], 0.0


def engine_elo(rating):          # kept for callers: the ladder replaced the engine's own limiter
    return rating


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
    engine: str = "fsf"          # "fsf" (Fairy-Stockfish with these knobs) or "leela" (lc0 with `net`)
    net: str = ""                # Leela network file (engine "leela")
    nodes: int = 0               # Leela: nodes per move (0 = use the clock)
    blunder: float = -1.0        # probability of a random legal move; -1 = from the rating (below the ladder's floor)
    compensate: bool = True      # pay a style's measured cost in strength back in search (CM-17)
    kansas: int = 0              # 0..100: appetite for moves that gain from Kramnik rules (self-captures and their threats)
    motif: str = ""              # the self-capture motif family a specialist plays for (docs/SELF_CAPTURE_MOTIFS.md)
    adjust: int = 0              # Elo: a measured correction to the strength model (KS: per specialist, by matches)
    reach: int = 0               # cp: how much further an own-motif self-capture may trail the best move (KS-10)

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
        o["UCI_LimitStrength"] = "false"             # strength comes from search nodes (level_for), not the limiter
        return o

    def effective_rating(self):
        """The ladder rating the engine must play at so that this style, with its cost, plays at `rating` (CM-17)."""
        return self.rating + (style_cost(self) if self.compensate else 0) + self.adjust

    def search_nodes(self):
        return level_for(self.effective_rating())[0] if self.rating < 2850 else 0   # 0 = full strength on the clock

    def total_randomness(self):
        return min(100, self.randomness)

    def blunder_rate(self):
        return self.blunder if self.blunder >= 0 else level_for(self.effective_rating())[1]


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
    with open(path, "rb") as f:
        b = f.read()
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


# Self-capture specialists (EPIC KS): they look like ordinary players and play ordinary chess, until Kramnik rules
# matter. `kansas` is their appetite for moves that gain from self-capture (KS-1; its cost in strength is paid back in
# search like any style's), and `motif` the family they play for (docs/SELF_CAPTURE_MOTIFS.md). `adjust` is each one's
# measured correction: 120 games against a neutral twin of its rating, pooled
# (docs/calibration/specialist_calibration.txt).
# Original text.
def _s(name, rating, style, motif, kansas, bio, **kw):
    return Personality(name=name, rating=rating, style=style, motif=motif, kansas=kansas, bio=bio, **kw)


SPECIALISTS = [
    _s("Hal", 950, "a beginner whose king slips out of trouble through its own pieces", "escape", 60,
       "Hal plays like any beginner, except for one habit: when his king is in danger it takes one of its own pieces "
       "to get out. Mates that would work in ordinary chess often fail against him.\n"
       "Watch for: a king that captures its own pawn or piece to escape a check.", randomness=20, adjust=-75),
    _s("Rosa", 1250, "opens files by taking her own pawns", "attack", 70,
       "Rosa pushes a rook's pawn, then takes it with her own rook and swings the rook into the attack. In ordinary "
       "chess a closed file stays closed; against Rosa it opens in one move.\n"
       "Watch for: Rxh-pawn or Qxh-pawn opening a file toward your king.", randomness=10, attack=40,
       positional={**{t: (100, 100) for t in TERMS}, "KingSafety": (100, 130)}, adjust=-60),
    _s("Felix", 1500, "frees a buried piece by taking his own pawn", "activation", 70,
       "Felix hates a bad piece. A bishop blocked by its own pawns, or a rook with no open file, takes a pawn of its "
       "own and is in play a move later. His positions look passive until they suddenly aren't.\n"
       "Watch for: a bishop or rook capturing its own pawn to reach a long diagonal or an open file.", randomness=8,
       positional={**{t: (100, 100) for t in TERMS}, "Mobility": (140, 100)}, adjust=-15),
    _s("Mirela", 1750, "a defender whose king walks through its own army", "escape,king-other,king-walk", 80,
       "Mirela lets you attack. When the mate seems certain, her king takes its own rook or pawn and walks away, and "
       "your pieces are left on the wrong side of the board. Even in quiet positions her king takes its own pawns to "
       "step where it wants.\n"
       "Watch for: before you go for mate, check every square next to her king, including the ones her own men "
       "stand on.", randomness=6, attack=-30,
       positional={**{t: (100, 100) for t in TERMS}, "KingSafety": (130, 100)}, reach=120, adjust=-20),
    _s("Corin", 2000, "a tactician: self-captures with check, and material won straight back", "check", 80,
       "Corin's self-captures are never gifts. He takes his own piece to give check, uncover an attack or open a "
       "line, and wins the material back a move or two later.\n"
       "Watch for: discovered checks made by a pawn or piece taking one of its own.", randomness=4, attack=30, adjust=-110),
    _s("Ada", 2250, "an endgame technician: her pieces reroute through their own men, her pawns promote through them",
       "promotion,king-walk,reposition", 80,
       "Ada's pieces take their own men to reach the squares they want: a bishop takes its own pawn to reach a "
       "diagonal, a knight its own pawn to reach an outpost. In the endgame her pawn on the seventh promotes by taking "
       "her own piece in front of it, and her king breaks into fortresses by taking its own blocking pawns.\n"
       "Watch for: a piece that could take one of her own men to land on a better square, and a piece placed in front "
       "of her own passed pawn.", randomness=2,
       positional={**{t: (100, 100) for t in TERMS}, "PassedPawns": (150, 130)}, reach=60, adjust=-79),
    _s("Selim", 2500, "plays ordinary-looking chess in which the threat of self-capture decides", "", 100,
       "Selim seldom self-captures. He plays for positions where your natural move, the best one in ordinary chess, "
       "loses because of a self-capture you did not consider, by him or by you.\n"
       "Watch for: every move, ask what each side could take of its own.", randomness=2, contempt=20, adjust=25),
    _s("Kestrel", 2600, "the strongest specialist: every motif, every threat", "", 100,
       "Kestrel uses all of Kramnik chess: file openers, escapes, promotions through her own pieces and the quiet "
       "threats that decide most games between strong players. A test for players who have done the lessons.\n"
       "Watch for: everything.", randomness=1, contempt=30, adjust=-5),
]


# Measured on the ladder (docs/calibration/leela_maia_ladder.txt), 60 games each against Fairy-Stockfish ladder levels.
# The Kramnik network at one node: its first instinct, made weaker by sampling (lc0 temperature). Temperature is
# harsh in Kramnik chess -- the network's long tail includes ruinous self-captures -- so the useful range is 0-1.
# (rating, temperature), each from 120 games through LeelaEngine against the nearest exact ladder point.
LEELA_LEVELS = [(1910, 0.3), (1650, 0.5), (1370, 0.6), (1150, 0.7)]
# Maia, by the human rating band it learned from -> measured Kramnik rating. Compressed: from 1500 up they play alike.
MAIA_MEASURED = [(1100, 1219), (1300, 1385), (1500, 1483), (1700, 1477), (1900, 1484)]
BEST_NET = "kramnik-sp1.pb.gz"         # the strongest Kramnik network measured (NN-10); the Nibbler launcher's default
T40_NET = "kramnik-t40a1.pb.gz"        # 20x256, GPU only: level with full-strength Fairy-Stockfish (NN-23, KS-7)


def maia_rating(band):
    pts = MAIA_MEASURED
    if band <= pts[0][0]:
        return pts[0][1]
    for (b0, r0), (b1, r1) in zip(pts, pts[1:]):
        if band <= b1:
            return round(r0 + (r1 - r0) * (band - b0) / (b1 - b0))
    return pts[-1][1]


def leela_roster():
    """Opponents played by the Kramnik lc0 (EPIC NN): the Kramnik network trained here -- at full search, and at one
    node with temperature for club-level play -- and the Maia networks, human-like play learned from rated human
    games. All rated by measurement in Kramnik chess, not by label."""
    out = []
    nets = os.path.join(HERE and os.path.dirname(HERE), "engine", "nets")
    best = os.path.join(nets, BEST_NET)
    kr = [best] if os.path.exists(best) else sorted(glob.glob(os.path.join(nets, "kramnik-*.pb.gz")))[-1:]
    t40 = os.path.join(nets, T40_NET)
    if os.path.exists(t40) and os.access(os.path.join(os.path.dirname(nets), "lc0-kramnik-gpu"), os.X_OK):
        out.append(Personality(
            "Leela T40", 2850, "the strongest Kramnik player here: a large network, on the GPU", engine="leela",
            net=t40, nodes=3000,
            bio="A 20-block network adapted to Kramnik chess by self-play on this project. At a second or so a move "
                "it is at least level with full-strength Fairy-Stockfish (EPIC NN, NN-23: 15/30 at 3 s a move; as "
                "played here, 3000 nodes, 14/20 against The Engine at 1 s a move). Where "
                "Fairy-Stockfish calculates, Leela judges: it plays positions, and it knows which self-captures are "
                "worth it. Needs the GPU build (engine/build_lc0_gpu.sh)."))
    if kr:
        out.append(Personality("Leela (Kramnik network)", 2850, "a neural network trained on Kramnik chess", engine="leela",
                               net=kr[0], nodes=800))
        for rating, t in LEELA_LEVELS:
            out.append(Personality("Leela %d" % rating, rating, "the Kramnik network's first instinct, one node, "
                                   "temperature %.1f (measured %d)" % (t, rating), engine="leela", net=kr[0], nodes=1,
                                   randomness=round(100 * t)))
    maia = os.path.join(WED, "INSTALL", "maia_weights")
    for f in sorted(glob.glob(os.path.join(maia, "maia-*.pb.gz"))):
        band = int(re.findall(r"maia-(\d+)", f)[0])
        out.append(Personality("Maia %d" % band, maia_rating(band), "human-like play learned from games of players rated "
                               "about %d; measured %d in Kramnik chess (one node)" % (band, maia_rating(band)),
                               engine="leela", net=f, nodes=1))
    return out


def roster():
    """Chessmaster's personalities when installed, otherwise chessIQ's own; the self-capture specialists; and the
    Leela opponents available."""
    return (load_chessmaster() or list(ROSTER)) + list(SPECIALISTS) + leela_roster()


def by_name():
    """Every personality by name, Chessmaster's, chessIQ's own and the Leela opponents (for tools and tests)."""
    out = {p.name: p for p in ROSTER + SPECIALISTS}
    out.update({p.name: p for p in load_chessmaster()})
    out.update({p.name: p for p in leela_roster()})
    return out
