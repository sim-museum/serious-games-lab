#!/usr/bin/env python3
"""Instrumented (teaching / analysis) cardplay view.

An alternative to the normal table — a four-hand "cross" where each
hand is a 4-row (♠♥♦♣) × 2-column (Known | Other) grid, surrounded by
analysis panels. It is meant to be useful to BOTH a trainee (count your
tricks, where are the entries, what is partner signalling) AND a strong
player (full count, proven card placement, honour location, squeeze /
BLUE readiness) — the Detail selector (Beginner / Intermediate / Expert)
scales how much is shown.

Layout (3×3 grid; corners are analysis panels, the cross sits on the
edges + centre):

    Contract/Tricks |      NORTH       | Plan (winners/losers/trumps)
    ----------------+------------------+-----------------------------
        WEST        |  trick + detail  |            EAST
    ----------------+------------------+-----------------------------
    Count / honours |      SOUTH       | Coaching / signals

What is shown per suit row:
  • KNOWN  — cards we can PROVE are in that hand right now: exact cards
    for a face-up hand (own + dummy + Show-All), and for a hidden hand
    only cards forced there (sole seat not shown out of the suit).
  • OTHER  — derived info: inferred length range (auction ∩ play), void,
    and honour-location hints.

Highlights on Known cards: the current master (boss) of a suit, top-run
sure winners, and the trump suit. Everything degrades gracefully when
state is missing, so the view is safe to refresh at any point in a hand.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from backend.models import Suit, Rank, Seat, Card, Contract, BoardState

try:
    from backend.auction_inference import infer_constraints
except Exception:                                    # pragma: no cover
    infer_constraints = None

try:
    from backend import signal_read as _signal_read
    from backend import signals as _signals
except Exception:                                    # pragma: no cover
    _signal_read = None
    _signals = None

from ui.styles import get_suit_color


SUIT_ROWS: List[Suit] = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
SUIT_NAME = {Suit.SPADES: "spades", Suit.HEARTS: "hearts",
             Suit.DIAMONDS: "diamonds", Suit.CLUBS: "clubs"}

# Suit colours tuned for THIS view's dark background — the app's normal
# palette (black spades, dark-blue diamonds) is meant for white card faces
# and is unreadable here. Four-colour, all high-contrast on #0f2740.
TV_SUIT_COLOR = {
    Suit.SPADES:   "#e8eef6",   # near-white (black was invisible on blue)
    Suit.HEARTS:   "#ff6b6b",
    Suit.DIAMONDS: "#ffb44d",   # orange (dark blue was invisible on blue)
    Suit.CLUBS:    "#57d07b",
}


def _suit_color(suit: Suit) -> str:
    return TV_SUIT_COLOR.get(suit, "#e8eef6")
HONOURS = [Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK]
ALL_CARDS: List[Card] = [Card(s, r) for s in SUIT_ROWS for r in Rank]


def _cid(card: Card) -> int:
    """Hashable 0-51 id for a card (Card itself is an unhashable dataclass)."""
    return int(card.suit) * 13 + int(card.rank)

# Detail tiers.
BEGINNER, INTERMEDIATE, EXPERT = "Beginner", "Intermediate", "Expert"


# ---------------------------------------------------------------------------
# Per-pair carding agreement. N/S and E/W can differ; every signal read is
# decoded through the SIGNALLER's own config (ACBL Encyclopedia: one polarity
# flag flips an attitude/count read, and suit-preference is its own agreement).
# ---------------------------------------------------------------------------

@dataclass
class CardingConfig:
    attitude: str = "standard"   # standard (high encourages) | udca (low encourages)
    count: str = "standard"      # standard (hi-lo = even) | reverse (lo-hi = even)
    discards: str = "attitude"   # attitude (about the suit thrown) | lavinthal (suit-pref)
    trump_echo: str = "standard" # standard (hi-lo in trumps = odd / 3) | off
    smith: str = "off"           # off | standard (hi = liked the lead) | reverse (NT only)


# Named presets surfaced in the view's per-pair carding selectors.
CARDING_PRESETS = {
    "Standard":          CardingConfig("standard", "standard", "attitude"),
    "Upside-down":       CardingConfig("udca",     "reverse",  "attitude"),
    "Std + Lavinthal":   CardingConfig("standard", "standard", "lavinthal"),
    "UDCA + Lavinthal":  CardingConfig("udca",     "reverse",  "lavinthal"),
}


def _app_default_udca() -> bool:
    """The app's configured signalling convention (Preferences →
    signalling_convention), falling back to the BIQ_SIGNAL_UDCA switch."""
    try:
        from backend.config import get_config_manager
        conv = getattr(get_config_manager().config.preferences,
                       "signalling_convention", "") or ""
        if conv:
            return conv.lower() == "udca"
    except Exception:
        pass
    return _signals.is_udca() if _signals is not None else False


def _default_carding() -> CardingConfig:
    """Default agreement — honours the app's Preferences (then the
    BIQ_SIGNAL_UDCA switch) so the out-of-the-box reading matches the user's
    configured convention."""
    udca = _app_default_udca()
    return CardingConfig(attitude="udca" if udca else "standard",
                         count="reverse" if udca else "standard",
                         discards="attitude")


def _default_preset_name() -> str:
    return "Upside-down" if _app_default_udca() else "Standard"


def _tv_config_path() -> Path:
    """Where the instrumented view persists its selectors (alongside the app's
    config when available, else the home dir)."""
    try:
        from backend.config import get_config_manager
        d = getattr(get_config_manager(), "config_dir", None)
        if d:
            return Path(d) / "teaching_view.json"
    except Exception:
        pass
    return Path.home() / ".biq_teaching_view.json"


# ---------------------------------------------------------------------------
# Pure inference helpers (no Qt) — kept module-level so they're testable.
# ---------------------------------------------------------------------------

def collect_play(board: BoardState):
    """Walk completed + current trick.

    Returns (played, voids, all_played):
      played[seat]      -> set(Card) the seat has played
      voids[seat]       -> set(Suit) the seat is known void in (showed out)
      all_played        -> set(Card) played by anyone
    """
    played: Dict[Seat, Set[int]] = {s: set() for s in Seat}
    voids: Dict[Seat, Set[Suit]] = {s: set() for s in Seat}
    all_played: Set[int] = set()      # set of card-ids

    def process(cards, leader):
        if not cards or leader is None:
            return
        try:
            base = int(leader)
        except (TypeError, ValueError):
            return
        led = cards[0].suit
        for i, c in enumerate(cards):
            seat = Seat((base + i) % 4)
            played[seat].add(_cid(c))
            all_played.add(_cid(c))
            if c.suit != led:
                voids[seat].add(led)

    for t in (getattr(board, "tricks", None) or []):
        process(getattr(t, "cards", None) or [], getattr(t, "leader", None))
    ct = getattr(board, "current_trick", None)
    if ct is not None:
        process(getattr(ct, "cards", None) or [], getattr(ct, "leader", None))
    return played, voids, all_played


def remaining_ranks(all_played: Set[Card]) -> Dict[Suit, Set[Rank]]:
    """Ranks of each suit still in play (not yet played)."""
    rem = {su: set(Rank) for su in SUIT_ROWS}
    for cid in all_played:                       # cid = suit*13 + rank
        rem[Suit(cid // 13)].discard(Rank(cid % 13))
    return rem


def boss_rank(rem: Dict[Suit, Set[Rank]], suit: Suit) -> Optional[Rank]:
    """The highest card of `suit` still in play (Rank value: lower = higher)."""
    rs = rem.get(suit)
    return min(rs) if rs else None


def known_layout(board: BoardState, visible: Set[Seat]):
    """Determine, per seat per suit, which cards are PROVEN present now.

    Returns a dict:
      known[seat][suit] -> List[Rank] (sorted high→low)
    plus voids, the per-seat remaining-card count, and unseen-by-suit.
    """
    played, voids, all_played = collect_play(board)
    remaining_count = {s: 13 - len(played[s]) for s in Seat}

    visible_cards: Dict[Seat, List[Card]] = {}
    seen_or_visible: Set[int] = set(all_played)        # card-ids
    for s in visible:
        h = board.hands.get(s) if board.hands else None
        cards = list(getattr(h, "cards", []) or []) if h else []
        visible_cards[s] = cards
        seen_or_visible |= {_cid(c) for c in cards}

    hidden = [s for s in Seat if s not in visible]
    unseen = [c for c in ALL_CARDS if _cid(c) not in seen_or_visible]

    cap = {s: remaining_count[s] for s in hidden}
    proven: Dict[Seat, List[Card]] = {s: [] for s in hidden}
    for c in unseen:
        cands = [s for s in hidden if c.suit not in voids[s] and cap[s] > 0]
        if len(cands) == 1:
            proven[cands[0]].append(c)

    known: Dict[Seat, Dict[Suit, List[Rank]]] = {
        s: {su: [] for su in SUIT_ROWS} for s in Seat}
    # inferred[seat][suit] = ranks PLACED by deduction in a HIDDEN hand (the
    # card must be there because every other hidden hand is void / full). These
    # are "known" but not "seen" — the grid outlines them differently.
    inferred: Dict[Seat, Dict[Suit, Set[Rank]]] = {
        s: {su: set() for su in SUIT_ROWS} for s in Seat}
    for s in visible:
        for c in visible_cards[s]:
            known[s][c.suit].append(c.rank)
    for s in hidden:
        for c in proven[s]:
            known[s][c.suit].append(c.rank)
            inferred[s][c.suit].add(c.rank)
    for s in Seat:
        for su in SUIT_ROWS:
            known[s][su].sort()   # ACE=0 first → high to low

    unseen_by_suit: Dict[Suit, int] = {su: 0 for su in SUIT_ROWS}
    for c in unseen:
        unseen_by_suit[c.suit] += 1

    return {
        "known": known, "inferred": inferred, "voids": voids,
        "remaining_count": remaining_count,
        "unseen_by_suit": unseen_by_suit, "all_played": all_played,
        "rem_ranks": remaining_ranks(all_played),
    }


def suit_length_text(seat: Seat, suit: Suit, visible: Set[Seat], layout,
                     constraints) -> str:
    """Short OTHER-cell length token for a suit row."""
    known = layout["known"][seat][suit]
    if seat in visible:
        return f"{len(known)}"
    if suit in layout["voids"][seat]:
        return "void"
    lo, hi = 0, 13
    c = constraints.get(seat) if constraints else None
    if c is not None:
        lo, hi = c.suit_len.get(suit.value, (0, 13))
    lo = max(lo, len(known))
    hi = min(hi, layout["unseen_by_suit"].get(suit, 0) + len(known))
    if lo > hi:
        lo = hi
    if lo == hi:
        return f"{lo}"
    if lo <= 0 and hi >= 13:
        return "?"
    if hi >= 7 and lo >= 5:
        return f"{lo}+"
    return f"{lo}-{hi}"


def winners_in_hand(held: List[Rank], rem_of_suit: Set[Rank]) -> Set[Rank]:
    """Top-run sure winners: walk remaining ranks high→low while this
    hand holds them; stop at the first gap (a rank held elsewhere)."""
    hs = set(held)
    wins: Set[Rank] = set()
    for r in sorted(rem_of_suit):     # high → low
        if r in hs:
            wins.add(r)
        else:
            break
    return wins


def top_entry_rank(winners: Set[Rank]) -> Optional[Rank]:
    """The highest sure winner — the card that gains the lead in this hand,
    i.e. an entry to it. None if the hand has no sure winner in the suit."""
    return min(winners) if winners else None     # Rank: lower value = higher card


def stopper_rank(held: List[Rank]) -> Optional[Rank]:
    """The honour that stops a suit, by the length-guard rule: A, or Kx, or
    Qxx, or Jxxx. Returns the guarding card, or None. (An NT concept.)"""
    hs = set(held)
    n = len(held)
    if Rank.ACE in hs:
        return Rank.ACE
    if Rank.KING in hs and n >= 2:
        return Rank.KING
    if Rank.QUEEN in hs and n >= 3:
        return Rank.QUEEN
    if Rank.JACK in hs and n >= 4:
        return Rank.JACK
    return None


def side_top_tricks(board: BoardState, side_seats: Tuple[Seat, Seat],
                    visible: Set[Seat], layout) -> Optional[int]:
    """Count sure top tricks for a side (e.g. declarer+dummy) — only when
    both that side's hands are face-up. Walks each suit's remaining ranks
    from the top while the side holds them, capped by the longer holding."""
    if not all(s in visible for s in side_seats):
        return None
    rem = layout["rem_ranks"]
    total = 0
    for su in SUIT_ROWS:
        held = set(layout["known"][side_seats[0]][su]) | \
            set(layout["known"][side_seats[1]][su])
        length_cap = max(len(layout["known"][side_seats[0]][su]),
                         len(layout["known"][side_seats[1]][su]))
        run = 0
        for r in sorted(rem[su]):     # high → low
            if r in held and run < length_cap:
                run += 1
            else:
                break
        total += run
    return total


def losing_trick_count(hand_known: Dict[Suit, List[Rank]]) -> Optional[int]:
    """Standard LTC for one (visible) hand: in each suit's top 3 cards,
    a card that isn't A/K/Q is a loser."""
    losers = 0
    for su in SUIT_ROWS:
        ranks = hand_known[su][:3]
        winners = {Rank.ACE, Rank.KING, Rank.QUEEN}
        losers += sum(1 for r in ranks if r not in winners)
    return losers


def finesse_hints(declarer, dummy, visible, layout):
    """8-ever-9-never style hints for missing honours in the declaring side's
    combined suits. Needs both hands face-up. Returns short strings."""
    if declarer is None or dummy is None \
            or declarer not in visible or dummy not in visible:
        return []
    out = []
    for su in SUIT_ROWS:
        hs = set(layout["known"][declarer][su]) | set(layout["known"][dummy][su])
        L = len(hs)
        if Rank.ACE in hs and Rank.KING in hs and Rank.QUEEN not in hs and L >= 7:
            if L >= 9:
                out.append(f"{su.symbol()}: {L} cards missing Q — play for the "
                           f"drop (9-never).")
            elif L == 8:
                out.append(f"{su.symbol()}: 8 cards missing Q — finesse "
                           f"(~50%, 8-ever).")
        elif Rank.ACE in hs and Rank.QUEEN in hs and Rank.KING not in hs and L >= 3:
            out.append(f"{su.symbol()}: missing K — finesse the Q (~50%).")
        elif Rank.KING in hs and Rank.JACK in hs and Rank.ACE not in hs \
                and Rank.QUEEN not in hs and L >= 3:
            out.append(f"{su.symbol()}: missing A & Q — finesse, ~50% each.")
    return out


def squeeze_threats(board, declarer, dummy, visible, layout):
    """Threat (menace) suits = where the declaring side holds the card just
    below the master that an opponent guards; a defender guarding ≥2 threats is
    'busy' (a squeeze candidate). Needs both declaring hands face-up. Returns
    {threats: {suit: guard_seat}, busy: [seat]} or None."""
    if declarer is None or dummy is None \
            or declarer not in visible or dummy not in visible:
        return None
    rem = layout["rem_ranks"]
    defenders = [s for s in Seat if s.is_ns() != declarer.is_ns()]
    threats = {}
    for su in SUIT_ROWS:
        ours = set(layout["known"][declarer][su]) | set(layout["known"][dummy][su])
        if not ours:
            continue
        boss = boss_rank(rem, su)
        if boss is None or boss in ours:
            continue                         # no master out, or we hold it (winner)
        # We hold a card; the boss (master) is the guard — who holds it?
        holder = _holder_of(layout, su, boss, visible)
        if holder in defenders:
            threats[su] = holder
    from collections import Counter
    cnt = Counter(threats.values())
    busy = [d for d, c in cnt.items() if c >= 2]
    return {"threats": threats, "busy": busy}


def honour_placement(board: BoardState, visible: Set[Seat], layout):
    """For each unseen honour, where it can be. Returns list of
    (suit, rank, label) where label is a proven seat or a side."""
    out = []
    played, voids, all_played = collect_play(board)
    seen_or_visible = set(all_played)            # card-ids
    for s in visible:
        h = board.hands.get(s) if board.hands else None
        seen_or_visible |= {_cid(c) for c in (getattr(h, "cards", []) or [])}
    hidden = [s for s in Seat if s not in visible]
    cap = {s: layout["remaining_count"][s] for s in hidden}
    # Vacant spaces: unknown cards in each hidden hand (total held minus already
    # placed). P(an unseen card sits in a hand) ∝ its vacant spaces.
    vacant = {s: max(0, layout["remaining_count"][s]
                     - sum(len(layout["known"][s][x]) for x in SUIT_ROWS))
              for s in hidden}
    for su in SUIT_ROWS:
        for r in HONOURS:
            if _cid(Card(su, r)) in seen_or_visible:
                continue
            cands = [s for s in hidden if su not in voids[s] and cap[s] > 0]
            if not cands:
                continue
            if len(cands) == 1:
                label = f"{cands[0].to_char()} (proven)"
            else:
                tot = sum(vacant[s] for s in cands) or 1
                pcts = sorted(((s, round(100 * vacant[s] / tot))
                               for s in cands), key=lambda x: -x[1])
                if len(cands) == 2 and cands[0].is_ns() == cands[1].is_ns() \
                        and pcts[0][1] == pcts[1][1]:
                    label = "N/S" if cands[0].is_ns() else "E/W"
                else:
                    label = " ".join(f"{s.to_char()} {p}%" for s, p in pcts)
            out.append((su, r, label))
    return out


# ---------------------------------------------------------------------------
# Defensive signal reading (attitude / count) on PLAYED cards.
#
# Uses backend.signal_read to pick out which completed-trick plays are genuine
# free signals (followed suit, didn't win, played a spot), then interprets each
# as encourage/discourage (attitude) or even/odd (count) from PUBLIC info only —
# "high vs low" relative to the cards of that suit still outstanding when it was
# played, exactly the read a human makes at the table. Honours UDCA via the same
# switch the emitter uses, so the reading matches biq's own carding.
# ---------------------------------------------------------------------------

_HONOUR_VAL = 3   # rank.value: A/K/Q/J ≤ 3 are honours; spots are 4..12


def _card_from_c52(c52: int) -> Card:
    return Card(Suit(c52 // 13), Rank(c52 % 13))


def _live_ranks_of_suit(board, suit: Suit, upto_trick: int,
                        before_cards: List[Card]) -> List[Rank]:
    """Ranks of `suit` still unseen when a card was played: all ranks minus
    those that appeared in completed tricks before `upto_trick` and in the
    same trick before the signaller. Sorted high→low (ACE first)."""
    seen = set()
    tricks = getattr(board, "tricks", None) or []
    for j, t in enumerate(tricks):
        if j >= upto_trick:
            break
        for c in (getattr(t, "cards", None) or []):
            if c.suit == suit:
                seen.add(c.rank)
    for c in before_cards:
        if c.suit == suit:
            seen.add(c.rank)
    return [r for r in Rank if r not in seen]


def _is_high(card: Card, live: List[Rank]) -> bool:
    """Is `card` in the upper half of the still-outstanding cards of its suit?"""
    try:
        idx = live.index(card.rank)
    except ValueError:
        return False
    return idx * 2 < len(live) - 1


def _interpret(attitude: bool, high: bool, cfg: CardingConfig,
               is_trump: bool = False):
    """Return (tag, meaning) for a follow-suit signal under `cfg`.

    A count signal in the TRUMP suit is read as a trump echo: high-low in
    trumps shows an ODD number (typically three — "I can ruff"), the reverse
    of a side-suit count signal."""
    if attitude:
        positive = high if cfg.attitude == "standard" else (not high)
        return ("enc", "encourages") if positive else ("disc", "discourages")
    if is_trump and cfg.trump_echo != "off":
        # standard trump echo: high → odd (3+); flips with a reverse-count pair.
        odd = high if cfg.count == "standard" else (not high)
        return ("ruff", "3 trumps (echo)") if odd else ("te", "even trumps")
    even = high if cfg.count == "standard" else (not high)
    return ("even", "even count") if even else ("odd", "odd count")


def _interpret_discard(card: Card, trump: Optional[Suit], cfg: CardingConfig,
                       live: List[Rank]):
    """Read a DISCARD (off-suit card). Returns (tag, meaning).

    • Lavinthal/suit-preference (cfg.discards == 'lavinthal'): the rank points
      to one of the two OTHER side suits — high → higher-ranking, low → lower
      (the thrown suit and trump are excluded). Only confident when exactly two
      candidate suits remain (a trump contract); otherwise falls back to
      attitude. ACBL: suit-preference is "an unusual play of unmistakable
      significance" — so we only assert it when the agreement says so and it is
      unambiguous.
    • Attitude discard (default): high spot = likes the suit thrown, low =
      discourages it (polarity follows the attitude agreement)."""
    suit = card.suit
    high = _is_high(card, live)
    if cfg.discards == "lavinthal":
        cands = [s for s in SUIT_ROWS if s != suit and s != trump]
        if len(cands) == 2:                       # SUIT_ROWS is high→low ranked
            target = cands[0] if high else cands[1]
            return ("sp", f"suit-pref → {target.symbol()}")
        # NT or otherwise ambiguous: fall through to an attitude read.
    positive = high if cfg.attitude == "standard" else (not high)
    if positive:
        return ("enc", f"likes {suit.symbol()}")
    return ("disc", f"not {suit.symbol()}")


def signal_reads(board, declarer: Optional[Seat], trump: Optional[Suit],
                 carding_for: Optional[Callable[[Seat], CardingConfig]] = None,
                 visible: Optional[Set[Seat]] = None):
    """Readable defensive signals from COMPLETED tricks, both defenders —
    attitude/count on follows AND suit-preference/attitude on discards.

    `carding_for(seat)` supplies that seat's agreement; defaults to the
    legacy global convention. When a signaller's hand is in `visible`, each
    follow signal is also checked for HONESTY against that hand (engine's
    `signal_read.mis_signals`, decoded under the pair's own convention):
    `honest` is True (matches the convention card), False (a false-card — with
    `expected` = the honest card), or None (signaller hidden / not checkable).
    Returns chronological dicts:
      {seat, trick, card, suit, tag, meaning, kind, honest, expected}
    """
    if declarer is None:
        return []
    if carding_for is None:
        carding_for = lambda s: _default_carding()
    visible = visible or set()
    defenders = [s for s in Seat if s.is_ns() != declarer.is_ns()]
    out = []

    # Smith echo (NT) — first; its cards are removed from the count reads below.
    smith, smith_used = smith_reads(board, declarer, trump, carding_for, visible)
    out.extend(smith)

    # Follows (attitude/count) — reuse the engine's careful free-signal filter.
    if _signal_read is not None:
        for d in defenders:
            try:
                # read(seat=X) returns X.partner()'s signals; pass d.partner()
                # so the signaller is d itself.
                recs = _signal_read.read(board, d.partner(), declarer, trump)
            except Exception:
                recs = []
            cfg = carding_for(d)
            dishonest = _dishonest_map(recs, board, d, visible, cfg)
            for rec in recs:
                if (rec["trick"], rec["card52"]) in smith_used:
                    continue                      # already shown as a Smith echo
                card = _card_from_c52(rec["card52"])
                suit = Suit(rec["suit"])
                before = [_card_from_c52(c) for c in rec.get("before", [])]
                live = _live_ranks_of_suit(board, suit, rec["trick"], before)
                high = _is_high(card, live)
                is_trump = (trump is not None and suit == trump)
                tag, meaning = _interpret(rec["attitude"], high, cfg, is_trump)
                rd = {"seat": d, "trick": rec["trick"], "card": card,
                      "suit": suit, "tag": tag, "meaning": meaning,
                      "kind": "att" if rec["attitude"] else "cnt",
                      "honest": None, "expected": None}
                if d in visible:
                    if is_trump:
                        # mis_signals judges trump count by the wrong (even-high)
                        # parity; trump echo is odd-high, so check it directly.
                        rd["honest"], rd["expected"] = _trump_echo_honest(
                            board, d, card, rec["trick"], cfg, trump, visible)
                    else:
                        exp = dishonest.get((rec["trick"], rec["card52"]), "ok")
                        if exp == "ok":
                            rd["honest"] = True
                        else:
                            rd["honest"] = False
                            rd["expected"] = _card_from_c52(exp)
                out.append(rd)

    # Discards (suit-preference / attitude) — the engine's reader skips these.
    out.extend(_completed_discard_reads(board, declarer, trump,
                                        defenders, carding_for, visible))
    # Suit-preference on ruff-giving leads (trump contracts).
    out.extend(ruff_lead_reads(board, declarer, trump, carding_for))
    out.sort(key=lambda r: r["trick"])
    return out


def _dishonest_map(recs, board, signaller, visible, cfg) -> Dict[tuple, int]:
    """{(trick, played52): expected52} for the signaller's FALSE follow signals,
    judged against its actual visible hand. Empty unless the hand is visible.

    The engine's `mis_signals` reads `signals.is_udca()` for the convention; our
    presets move attitude+count together, so we map the pair's agreement onto
    that single switch around the call, then restore it."""
    if (_signal_read is None or signaller not in visible
            or not board.hands or board.hands.get(signaller) is None):
        return {}
    actual = {_cid(c) for c in board.hands[signaller].cards}   # current holding
    prev = _signals.is_udca() if _signals is not None else False
    try:
        if _signals is not None:
            _signals.set_convention(cfg.attitude == "udca")
        mis = _signal_read.mis_signals(recs, actual)
    except Exception:
        mis = []
    finally:
        if _signals is not None:
            _signals.set_convention(prev)
    return {(m["trick"], m["played52"]): m["expected52"] for m in mis}


def _holding_at_suit(board, seat, suit, trick_index, visible):
    """Ranks of `suit` the seat held when it played at `trick_index`: current
    face-up remaining plus any cards of the suit it played from that trick on.
    None if the hand isn't face-up."""
    if seat not in visible or not board.hands or board.hands.get(seat) is None:
        return None
    held = [c.rank for c in board.hands[seat].cards if c.suit == suit]
    for j, t in enumerate(getattr(board, "tricks", None) or []):
        if j < trick_index:
            continue
        cards = getattr(t, "cards", None) or []
        leader = getattr(t, "leader", None)
        if leader is None:
            continue
        base = int(leader)
        for p, c in enumerate(cards):
            if Seat((base + p) % 4) == seat and c.suit == suit:
                held.append(c.rank)
    return sorted(held)


def _honest_from_spots(spots: List[Rank], want_high: bool, played: Rank,
                       suit: Suit):
    """Given the available spots (sorted high→low) and whether the honest card
    is the high one, return (honest, expected_or_None)."""
    if len(spots) < 2:
        return (None, None)
    expected = spots[0] if want_high else spots[-1]
    if expected == played:
        return (True, None)
    return (False, Card(suit, expected))


def _attitude_discard_honest(board, seat, card, trick_index, cfg, visible):
    held = _holding_at_suit(board, seat, card.suit, trick_index, visible)
    if held is None:
        return (None, None)
    spots = sorted([r for r in held if r.value > _HONOUR_VAL] or held)
    like = any(r.value <= _HONOUR_VAL for r in held)        # honour present
    want_high = like if cfg.attitude == "standard" else (not like)
    return _honest_from_spots(spots, want_high, card.rank, card.suit)


def _trump_echo_honest(board, seat, card, trick_index, cfg, trump, visible):
    held = _holding_at_suit(board, seat, trump, trick_index, visible)
    if held is None:
        return (None, None)
    odd = (len(held) % 2 == 1)                  # echo: high-low shows odd (3)
    want_high = odd if cfg.count == "standard" else (not odd)
    return _honest_from_spots(sorted(held), want_high, card.rank, trump)


def _smith_honest(board, seat, card, trick_index, lead_suit, want_high_like,
                  visible):
    held = _holding_at_suit(board, seat, lead_suit, trick_index, visible)
    if held is None:
        return (None, None)
    like = (len(held) >= 3) or any(r.value <= _HONOUR_VAL for r in held)
    want_high = like if want_high_like else (not like)
    spots = sorted([r for r in (_holding_at_suit(board, seat, card.suit,
                    trick_index, visible) or []) if r.value > _HONOUR_VAL]
                   or (_holding_at_suit(board, seat, card.suit, trick_index,
                                        visible) or []))
    return _honest_from_spots(spots, want_high, card.rank, card.suit)


def smith_reads(board, declarer: Optional[Seat], trump: Optional[Suit],
                carding_for: Callable[[Seat], CardingConfig],
                visible: Optional[Set[Seat]] = None):
    """Smith-echo reads (NT only). The FIRST card a defender plays in a suit the
    DECLARING side leads (other than the opening-lead suit) is an attitude signal
    about the OPENING-LEAD suit: standard high = "I liked the lead, continue it",
    low = discourage / suggest a switch; reverse Smith inverts.

    Returns (reads, used) where `used` is the set of (trick, card52) consumed so
    the caller can suppress the ordinary count read on those cards."""
    out, used = [], set()
    visible = visible or set()
    if trump is not None or declarer is None:
        return out, used                          # suit contract — N/A
    tricks = getattr(board, "tricks", None) or []
    if not tricks or not (getattr(tricks[0], "cards", None)):
        return out, used
    lead_suit = tricks[0].cards[0].suit
    leader0 = Seat(int(tricks[0].leader)) if tricks[0].leader is not None else None
    decl_ns = declarer.is_ns()
    defenders = {s for s in Seat if s.is_ns() != decl_ns}
    done = set()                                  # defenders who've had their chance
    for j, t in enumerate(tricks):
        cards = getattr(t, "cards", None) or []
        leader = getattr(t, "leader", None)
        if len(cards) < 4 or leader is None:
            continue
        if leader.is_ns() != decl_ns:
            continue                              # not a declaring-side lead
        d_suit = cards[0].suit
        if d_suit == lead_suit:
            continue                              # must be a fresh (declarer's) suit
        base = int(leader)
        for p in range(4):
            seat = Seat((base + p) % 4)
            if seat not in defenders or seat in done:
                continue
            c = cards[p]
            if c.suit != d_suit:
                continue                          # void/discard — chance not used yet
            done.add(seat)
            if c.rank.value <= _HONOUR_VAL:
                continue                          # forced honour — no spot signal
            cfg = carding_for(seat)
            if cfg.smith == "off":
                continue
            live = _live_ranks_of_suit(board, d_suit, j, cards[:p])
            high = _is_high(c, live)
            # Reverse-Smith asymmetry: only the OPENING LEADER reverses
            # (high = "I have an alternative — shift"); third hand stays
            # standard (high = continue). So the flip is leader-only.
            is_leader = (seat == leader0)
            want_high_like = not (cfg.smith == "reverse" and is_leader)
            if not want_high_like:
                high = not high
            who = "lead" if is_leader else "3rd"
            if high:
                tag, meaning = "enc", f"likes {lead_suit.symbol()} ({who}, continue)"
            else:
                tag, meaning = "disc", f"shift from {lead_suit.symbol()} ({who})"
            honest, expected = _smith_honest(board, seat, c, j, lead_suit,
                                             want_high_like, visible)
            out.append({"seat": seat, "trick": j, "card": c, "suit": d_suit,
                        "tag": tag, "meaning": meaning, "kind": "smith",
                        "honest": honest, "expected": expected})
            used.add((j, _cid(c)))
    return out, used


def _completed_discard_reads(board, declarer, trump, defenders, carding_for,
                             visible=None):
    """Read defenders' DISCARDS (off-suit, not a ruff) on completed tricks."""
    out = []
    visible = visible or set()
    for j, t in enumerate(getattr(board, "tricks", None) or []):
        cards = getattr(t, "cards", None) or []
        leader = getattr(t, "leader", None)
        if len(cards) < 4 or leader is None:
            continue
        base = int(leader)
        led = cards[0].suit
        for p in range(4):
            seat = Seat((base + p) % 4)
            if seat not in defenders:
                continue
            c = cards[p]
            if c.suit == led:
                continue                         # followed suit — handled above
            if trump is not None and c.suit == trump:
                continue                         # ruff, not a signal
            cfg = carding_for(seat)
            live = _live_ranks_of_suit(board, c.suit, j, cards[:p])
            tag, meaning = _interpret_discard(c, trump, cfg, live)
            honest = expected = None
            if tag in ("enc", "disc"):           # attitude discard — checkable
                honest, expected = _attitude_discard_honest(
                    board, seat, c, j, cfg, visible)
            out.append({"seat": seat, "trick": j, "card": c, "suit": c.suit,
                        "tag": tag, "meaning": meaning, "kind": "dsc",
                        "honest": honest, "expected": expected})
    return out


def ruff_lead_reads(board, declarer, trump, carding_for):
    """Suit-preference on a ruff-giving LEAD (trump contracts): a defender leads
    a suit its partner is known void in (and partner still has trumps), so the
    lead's rank steers the ruff return — high → higher of the two other side
    suits, low → lower. Returns reads (kind 'sp')."""
    out = []
    if trump is None or declarer is None:
        return out
    _, voids, all_played = collect_play(board)
    if not remaining_ranks(all_played).get(trump):
        return out                                   # trumps gone — no ruff
    tricks = getattr(board, "tricks", None) or []
    # First trick each seat showed out of each suit (so we only read a lead as a
    # ruff-SP once partner is KNOWN void from an EARLIER trick).
    shown: Dict[Seat, Dict[Suit, int]] = {s: {} for s in Seat}
    for j, t in enumerate(tricks):
        cards = getattr(t, "cards", None) or []
        leader = getattr(t, "leader", None)
        if len(cards) < 4 or leader is None:
            continue
        base = int(leader)
        led_s = cards[0].suit
        for p, c in enumerate(cards):
            st = Seat((base + p) % 4)
            if c.suit != led_s and led_s not in shown[st]:
                shown[st][led_s] = j
    defenders = [s for s in Seat if s.is_ns() != declarer.is_ns()]
    for j, t in enumerate(tricks):
        cards = getattr(t, "cards", None) or []
        leader = getattr(t, "leader", None)
        if len(cards) < 4 or leader is None:
            continue
        ldr = Seat(int(leader))
        if ldr not in defenders:
            continue
        led = cards[0].suit
        if led == trump:
            continue
        partner = ldr.partner()
        ve = shown[partner].get(led)
        if ve is None or ve >= j or trump in voids[partner]:
            continue                                 # partner not known void yet
        cands = [s for s in SUIT_ROWS if s != led and s != trump]
        if len(cands) != 2:
            continue
        live = _live_ranks_of_suit(board, led, j, [])
        high = _is_high(cards[0], live)
        target = cands[0] if high else cands[1]
        out.append({"seat": ldr, "trick": j, "card": cards[0], "suit": led,
                    "tag": "sp", "meaning": f"ruff-return → {target.symbol()}",
                    "kind": "ruflead", "honest": None, "expected": None})
    return out


def current_trick_reads(board, declarer: Optional[Seat], trump: Optional[Suit],
                        carding_for: Optional[Callable[[Seat], CardingConfig]] = None):
    """Live read of the IN-PROGRESS trick's defender cards (the engine's reader
    only sees completed tricks). Returns {seat: {card, tag, meaning}}.

    Reads a defender that FOLLOWED suit with a spot (attitude/count) and a
    defender that DISCARDED off-suit (suit-preference / attitude). The opening
    leader's own card and honour follows carry no spot signal and are skipped."""
    out = {}
    ct = getattr(board, "current_trick", None)
    if ct is None or declarer is None:
        return out
    if carding_for is None:
        carding_for = lambda s: _default_carding()
    cards = getattr(ct, "cards", None) or []
    leader = getattr(ct, "leader", None)
    if leader is None or len(cards) < 2:
        return out
    base = int(leader)
    led = cards[0].suit
    upto = len(getattr(board, "tricks", None) or [])
    for p in range(1, len(cards)):              # skip the leader (pos 0)
        seat = Seat((base + p) % 4)
        if seat.is_ns() == declarer.is_ns():
            continue                            # declaring side — no signal
        c = cards[p]
        cfg = carding_for(seat)
        if c.suit == led:
            if c.rank.value <= _HONOUR_VAL:
                continue                        # honour follow — not a spot signal
            attitude = (leader.is_ns() == seat.is_ns())
            live = _live_ranks_of_suit(board, led, upto, cards[:p])
            is_trump = (trump is not None and led == trump)
            tag, meaning = _interpret(attitude, _is_high(c, live), cfg, is_trump)
        elif trump is not None and c.suit == trump:
            continue                            # ruff, not a signal
        else:
            live = _live_ranks_of_suit(board, c.suit, upto, cards[:p])
            tag, meaning = _interpret_discard(c, trump, cfg, live)
        out[seat] = {"card": c, "tag": tag, "meaning": meaning}
    return out


_SIGNAL_TAG_COLOR = {"enc": "#7ad17a", "disc": "#e08a8a",
                     "even": "#8ab8e0", "odd": "#d9b36b",
                     "sp": "#d6a3e8", "ruff": "#e8b06a", "te": "#8ab8e0"}


def _tag_html(tag: str) -> str:
    col = _SIGNAL_TAG_COLOR.get(tag, "#9fb6cc")
    return (f"<span style='color:{col}; font-size:13px; font-weight:bold'>"
            f"{tag}</span>")


# Short Other-column labels for each signal tag (the full text shows in the
# Coaching/Signals panel; the grid cell just needs a glanceable chip).
_SIGNAL_SHORT = {"enc": "likes", "disc": "drop", "even": "even", "odd": "odd",
                 "ruff": "3·ruff", "te": "tr-ct", "sp": "S-pref",
                 "smith": "Smith"}


def _signal_chip(rd: dict) -> str:
    """A vivid inverse-video chip summarising one defensive signal read for a
    suit, with a ✗ flag when the engine knows it was a false-card."""
    tag = rd.get("tag", "")
    col = _SIGNAL_TAG_COLOR.get(tag, ACC_BLUE)
    label = _SIGNAL_SHORT.get(tag) or (rd.get("meaning") or tag)
    out = _chip(label, col)
    if rd.get("honest") is False:
        out += _chip("✗", ACC_RED)
    return out


def _honour_hint_map(board, visible, layout) -> Dict[Tuple[Seat, Suit], str]:
    """For each hidden seat + suit, a compact 'where's the missing honour'
    hint built from honour_placement's PROBABILISTIC verdicts (proven honours
    already render in the Known column, so they're skipped here). We surface a
    hint only for the favoured seat at ≥55% to avoid cluttering both defenders'
    columns with the same coin-flip."""
    import re
    out: Dict[Tuple[Seat, Suit], List[str]] = {}
    for su, r, label in honour_placement(board, visible, layout):
        if "proven" in label:
            continue
        pcts = re.findall(r'([NESW])\s+(\d+)%', label)
        if not pcts:
            continue
        sc, p = max(pcts, key=lambda x: int(x[1]))
        if int(p) < 55:
            continue
        seat = {s.to_char(): s for s in Seat}.get(sc)
        if seat is None:
            continue
        out.setdefault((seat, su), []).append(f"{r.to_char()}?{p}%")
    return {k: _chip(" ".join(v), ACC_GOLD, outline=True)
            for k, v in out.items()}


def _card_glyph(card: Card) -> str:
    col = _suit_color(card.suit)
    return (f"<span style='color:{col}; font-weight:bold'>"
            f"{card.suit.symbol()}{card.rank.to_char()}</span>")


# ---------------------------------------------------------------------------
# Qt widgets
# ---------------------------------------------------------------------------

PANEL_BG = "#101820"   # pokerIQ panel (slightly warmer)
PANEL_FG = "#eef3f7"   # pokerIQ ink
GRID_BG = "#13202a"   # pokerIQ card-dark (warmer green-ink)
MASTER_BG = "#ffd54a"  # gold — current master
TRUMP_TINT = "#1f5a3a"  # vivid green wash on the trump row
PANEL_LINE = "#2c4a3a"  # warm green-grey panel border

# pokerIQ accent palette — used for vivid, colour-coded markers and borders
# instead of faint superscripts. Each role gets its own hue.
ACC_GOLD   = "#d9b25b"   # master / declaring side
ACC_GREEN  = "#3fb950"   # entry / sure access
ACC_BLUE   = "#58a6ff"   # stopper / count
ACC_RED    = "#f85149"   # danger / knock-out
ACC_ORANGE = "#f0883e"   # cross-hand transport / suit-pref
ACC_YELLOW = "#ffd84d"   # attention
ACC_PURPLE = "#a87fff"   # busy / squeeze


def _chip(text: str, bg: str, fg: str = "#06121f", outline: bool = False) -> str:
    """An inverse-video (or outlined) inline badge — readable at a glance,
    unlike the old tiny superscripts. `outline` draws the glyph in the accent
    colour inside a thin border instead of solid fill (used for INFERRED, not
    yet seen, cards)."""
    if outline:
        return (f"<span style='color:{bg}; border:1px solid {bg};"
                f" border-radius:3px; padding:0 2px; font-size:12px;"
                f" font-weight:bold;'>{text}</span>")
    return (f"<span style='background:{bg}; color:{fg}; border-radius:3px;"
            f" padding:0 3px; font-size:12px; font-weight:bold;'>{text}</span>")


class _Panel(QFrame):
    """A small titled analysis panel for a corner of the cross."""

    def __init__(self, title: str, parent=None, accent: str = ACC_GOLD):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # A thicker accent left-border gives each panel its own hue (pokerIQ
        # colour-coded panels) without shouting.
        self.setStyleSheet(
            f"background:{PANEL_BG}; color:{PANEL_FG};"
            f" border:1px solid {PANEL_LINE}; border-left:3px solid {accent};"
            f" border-radius:6px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)
        self._title = QLabel(title)
        self._title.setStyleSheet(f"font-weight:bold; color:{accent};"
                                  f" border:0; font-size:15px;")
        lay.addWidget(self._title)
        self.body = QLabel("")
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.body.setStyleSheet("border:0;")
        lay.addWidget(self.body, stretch=1)

    def set_html(self, html: str):
        self.body.setText(html)


class HandGridWidget(QFrame):
    """One seat's 4×2 grid: rows ♠♥♦♣, columns Known | Other."""

    def __init__(self, seat: Seat, parent=None):
        super().__init__(parent)
        self.seat = seat
        self._accent = PANEL_LINE
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"background:{GRID_BG}; border:2px solid {PANEL_LINE};"
            f" border-radius:8px;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(2)

        self.title = QLabel(seat.name.title())
        self.title.setStyleSheet("color:#eef3f7; font-weight:bold; border:0;"
                                 " font-size:16px;")
        outer.addWidget(self.title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        hdr_k = QLabel("Known"); hdr_o = QLabel("Other")
        for h in (hdr_k, hdr_o):
            h.setStyleSheet(f"color:{ACC_GREEN}; font-size:14px; border:0;"
                            " font-weight:bold;")
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(hdr_k, 0, 1)
        grid.addWidget(hdr_o, 0, 2)

        self._suit_lbl: Dict[Suit, QLabel] = {}
        self._known_lbl: Dict[Suit, QLabel] = {}
        self._other_lbl: Dict[Suit, QLabel] = {}
        for i, su in enumerate(SUIT_ROWS, start=1):
            sl = QLabel(su.symbol())
            sl.setStyleSheet(
                f"color:{_suit_color(su)}; font-weight:bold; font-size:30px;"
                f" border:0; background:transparent;")
            kl = QLabel("—")
            kl.setTextFormat(Qt.TextFormat.RichText)
            kl.setFont(QFont("Monospace", 32))   # 2× — the grids had lots of slack
            kl.setStyleSheet("border:0;")
            ol = QLabel("")
            ol.setTextFormat(Qt.TextFormat.RichText)
            ol.setStyleSheet("color:#9fb6cc; font-size:17px; border:0;")
            self._suit_lbl[su] = sl
            self._known_lbl[su] = kl
            self._other_lbl[su] = ol
            grid.addWidget(sl, i, 0)
            grid.addWidget(kl, i, 1)
            grid.addWidget(ol, i, 2)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 2)
        outer.addLayout(grid)
        self.setMinimumWidth(230)

    def set_title(self, text: str):
        self.title.setText(text)

    def set_accent(self, color: str):
        """Recolour the hand frame's border — declaring side gold, defenders
        green, danger hand red (pokerIQ-style coloured seat boxes)."""
        if color == self._accent:
            return
        self._accent = color
        self.setStyleSheet(
            f"background:{GRID_BG}; border:2px solid {color};"
            f" border-radius:8px;")

    def set_row(self, suit: Suit, known_html: str, other_html: str,
                trump: bool):
        self._known_lbl[suit].setText(known_html or "—")
        self._other_lbl[suit].setText(other_html or "")
        tint = f"background:{TRUMP_TINT}; border-radius:3px;" if trump else \
            "background:transparent;"
        self._suit_lbl[suit].setStyleSheet(
            f"color:{_suit_color(suit)}; font-weight:bold; font-size:30px;"
            f" border:0; {tint}")


class TeachingView(QWidget):
    """The instrumented cross. Call refresh(...) to repaint from state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detail = INTERMEDIATE
        # Bigger base text throughout, and a readable (light-on-dark) tooltip —
        # the default tooltip palette renders black on this dark background.
        self.setStyleSheet(
            # warm radial-gradient backdrop, matching pokerIQ's felt glow
            "TeachingView { background:qradialgradient(cx:0.5, cy:0.0,"
            " radius:1.2, fx:0.5, fy:0.0, stop:0 #18242e, stop:0.7 #0a0e13); }"
            "QLabel { font-size: 16px; }"
            "QComboBox { font-size: 15px; }"
            "QToolTip { color:#eaf2fb; background-color:#16324f;"
            " border:1px solid #6fa8d6; padding:5px; font-size:14px; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Header: title + detail selector + systems.
        header = QHBoxLayout()
        h = QLabel("Instrumented view")
        h.setStyleSheet("color:#d9b25b; font-weight:bold; font-size:14px;")
        header.addWidget(h)
        header.addSpacing(12)
        header.addWidget(self._mk_label("Detail:"))
        self.detail_combo = QComboBox()
        self.detail_combo.addItems([BEGINNER, INTERMEDIATE, EXPERT])
        self.detail_combo.setCurrentText(INTERMEDIATE)
        self.detail_combo.currentTextChanged.connect(self._on_detail_changed)
        header.addWidget(self.detail_combo)

        # Per-pair carding agreement — N/S and E/W decoded independently.
        default_preset = _default_preset_name()
        header.addSpacing(12)
        header.addWidget(self._mk_label("Carding N/S:"))
        self.ns_carding_combo = QComboBox()
        self.ns_carding_combo.addItems(list(CARDING_PRESETS.keys()))
        self.ns_carding_combo.setCurrentText(default_preset)
        self.ns_carding_combo.currentTextChanged.connect(self._on_carding_changed)
        header.addWidget(self.ns_carding_combo)
        header.addWidget(self._mk_label("E/W:"))
        self.ew_carding_combo = QComboBox()
        self.ew_carding_combo.addItems(list(CARDING_PRESETS.keys()))
        self.ew_carding_combo.setCurrentText(default_preset)
        self.ew_carding_combo.currentTextChanged.connect(self._on_carding_changed)
        header.addWidget(self.ew_carding_combo)

        # Smith echo (NT): a defending-side agreement; one control since only
        # one side defends a given deal. Trump echo is read automatically.
        header.addWidget(self._mk_label("Smith:"))
        self.smith_combo = QComboBox()
        self.smith_combo.addItems(["Off", "Standard", "Reverse"])
        self.smith_combo.setCurrentText("Off")
        self.smith_combo.currentTextChanged.connect(self._on_carding_changed)
        header.addWidget(self.smith_combo)

        header.addStretch()
        self.systems_lbl = self._mk_label("")
        header.addWidget(self.systems_lbl)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(6)
        # Panels in the corners.
        self.p_contract = _Panel("Contract / Tricks", accent=ACC_GOLD)
        self.p_plan = _Panel("Plan", accent=ACC_GREEN)
        self.p_count = _Panel("Count / Honours", accent=ACC_BLUE)
        self.p_coach = _Panel("Coaching / Signals", accent=ACC_ORANGE)
        # Hand grids on the edges.
        self.hands = {s: HandGridWidget(s) for s in Seat}
        # Centre: current trick + on-lead.
        self.centre = _Panel("Table")

        grid.addWidget(self.p_contract, 0, 0)
        grid.addWidget(self.hands[Seat.NORTH], 0, 1)
        grid.addWidget(self.p_plan, 0, 2)
        grid.addWidget(self.hands[Seat.WEST], 1, 0)
        grid.addWidget(self.centre, 1, 1)
        grid.addWidget(self.hands[Seat.EAST], 1, 2)
        grid.addWidget(self.p_count, 2, 0)
        grid.addWidget(self.hands[Seat.SOUTH], 2, 1)
        grid.addWidget(self.p_coach, 2, 2)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        for r in range(3):
            grid.setRowStretch(r, 1)
        root.addLayout(grid, stretch=1)

        legend = QLabel(
            "Known column:  "
            + _chip("A", MASTER_BG) + " master · "
            + "<span style='border:1px solid " + ACC_GREEN + ";border-radius:3px;"
              "padding:0 2px'>K</span> sure winner · "
            + "<span style='border:1px dashed " + ACC_YELLOW + ";border-radius:3px;"
              "padding:0 2px'>Q</span> placed (inferred) · "
            + _chip("E", ACC_GREEN) + " entry · "
            + _chip("S", ACC_BLUE) + " stopper · "
            + _chip("KO", ACC_RED) + " knock-out · "
            + _chip("→", ACC_ORANGE) + " to partner · "
            + "<span style='background:" + TRUMP_TINT + "'>&nbsp;♣&nbsp;</span> trumps")
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setStyleSheet("color:#9fb6cc; font-size:13px;")
        root.addWidget(legend)
        tip = ("Boxed letters are role chips: E = entry (access to "
               "declarer/dummy), S = stopper (NT), KO = knock-out, → = card "
               "that reaches partner. Gold fill = current master; green box = "
               "sure winner; dashed box = a card PLACED by deduction (hidden "
               "hand). The Other column shows length, the latest defensive "
               "signal, and where a missing honour probably sits.")
        for hw in self.hands.values():
            hw.setToolTip(tip)

        self._last_state = None    # cached args for re-render on detail change
        self._load_prefs()         # restore persisted selectors

    def _load_prefs(self):
        try:
            data = json.loads(_tv_config_path().read_text())
        except Exception:
            return
        if data.get("detail") in (BEGINNER, INTERMEDIATE, EXPERT):
            self.detail_combo.setCurrentText(data["detail"])
        if data.get("ns_carding") in CARDING_PRESETS:
            self.ns_carding_combo.setCurrentText(data["ns_carding"])
        if data.get("ew_carding") in CARDING_PRESETS:
            self.ew_carding_combo.setCurrentText(data["ew_carding"])
        if data.get("smith") in ("Off", "Standard", "Reverse"):
            self.smith_combo.setCurrentText(data["smith"])

    def _save_prefs(self):
        try:
            _tv_config_path().write_text(json.dumps({
                "detail": self.detail_combo.currentText(),
                "ns_carding": self.ns_carding_combo.currentText(),
                "ew_carding": self.ew_carding_combo.currentText(),
                "smith": self.smith_combo.currentText(),
            }, indent=2))
        except Exception:
            pass

    def _mk_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#9aa7b4;")
        return lbl

    def _on_detail_changed(self, text):
        self.detail = text
        self._save_prefs()
        if self._last_state is not None:
            self.refresh(**self._last_state)

    def _on_carding_changed(self, _text):
        self._save_prefs()
        if self._last_state is not None:
            self.refresh(**self._last_state)

    def _carding_for(self, seat: Seat) -> CardingConfig:
        """The carding agreement of the SIGNALLER's pair, with the Smith-echo
        setting overlaid (a defending-side agreement shared by the controls)."""
        name = (self.ns_carding_combo.currentText() if seat.is_ns()
                else self.ew_carding_combo.currentText())
        base = CARDING_PRESETS.get(name, _default_carding())
        smith = {"Off": "off", "Standard": "standard",
                 "Reverse": "reverse"}.get(self.smith_combo.currentText(), "off")
        return replace(base, smith=smith)

    # -- rendering ---------------------------------------------------------

    def refresh(self, *, board: Optional[BoardState], contract: Optional[Contract],
                declarer: Optional[Seat], dummy: Optional[Seat],
                visible_seats: Set[Seat], ns_system=None, ew_system=None):
        """Repaint the whole view from the current play state. Safe to
        call with partial/None state (renders an empty shell)."""
        self._last_state = dict(
            board=board, contract=contract, declarer=declarer, dummy=dummy,
            visible_seats=set(visible_seats or set()),
            ns_system=ns_system, ew_system=ew_system)
        if board is None or not getattr(board, "hands", None):
            for s in Seat:
                self.hands[s].set_title(s.name.title())
                for su in SUIT_ROWS:
                    self.hands[s].set_row(su, "—", "", False)
            self.p_contract.set_html("No board.")
            for p in (self.p_plan, self.p_count, self.p_coach, self.centre):
                p.set_html("")
            return

        visible = set(visible_seats or set())
        trump = contract.suit if (contract and contract.suit != Suit.NOTRUMP) else None

        # Per-pair auction constraints (NS seats from the NS-system pass,
        # EW seats from the EW-system pass) so each side's bids are read
        # in its own system.
        constraints = {}
        if infer_constraints is not None:
            try:
                ns_c = infer_constraints(board, ns_system)
                ew_c = infer_constraints(board, ew_system)
                for s in Seat:
                    constraints[s] = ns_c[s] if s.is_ns() else ew_c[s]
            except Exception:
                constraints = {}

        layout = known_layout(board, visible)
        rem = layout["rem_ranks"]

        # System header.
        self.systems_lbl.setText(
            f"N/S: {_sys_name(ns_system)}   E/W: {_sys_name(ew_system)}")

        # Danger hand / knock-out entry — used by grids and the plan.
        danger = (danger_info(board, contract, declarer, visible, layout,
                              constraints) if self.detail != BEGINNER else None)
        # Squeeze threats / busy defender (Expert).
        squeeze = (squeeze_threats(board, declarer, dummy, visible, layout)
                   if self.detail == EXPERT else None)

        # Per-(seat,suit) defensive-signal reads + probabilistic honour hints —
        # surfaced in each defender's OTHER column so the right-hand side tells
        # you what biq's carding has revealed, not just suit lengths.
        sig_map: Dict[Tuple[Seat, Suit], dict] = {}
        hint_map: Dict[Tuple[Seat, Suit], str] = {}
        if self.detail != BEGINNER and contract is not None and declarer is not None:
            try:
                for r in signal_reads(board, declarer, trump,
                                      self._carding_for, visible):
                    sig_map[(r["seat"], r["suit"])] = r   # chronological → latest
            except Exception:
                sig_map = {}
            try:
                hint_map = _honour_hint_map(board, visible, layout)
            except Exception:
                hint_map = {}

        # Hand grids.
        for s in Seat:
            self._render_hand(s, board, visible, layout, rem, trump,
                              constraints, declarer, dummy, danger, squeeze,
                              sig_map, hint_map)

        # Panels.
        self._render_contract_panel(board, contract, declarer)
        self._render_plan_panel(board, contract, declarer, dummy, visible,
                                layout, trump, danger)
        self._render_count_panel(board, visible, layout, constraints, squeeze)
        self._render_coach_panel(board, contract, declarer, dummy, visible,
                                 layout, trump)
        self._render_centre(board, contract, declarer, trump)

    def _render_hand(self, seat, board, visible, layout, rem, trump,
                     constraints, declarer, dummy, danger=None, squeeze=None,
                     sig_map=None, hint_map=None):
        w = self.hands[seat]
        sig_map = sig_map or {}
        hint_map = hint_map or {}
        role = ""
        accent = PANEL_LINE
        if declarer is not None and seat == declarer:
            role = " · Declarer"
            accent = ACC_GOLD
        elif dummy is not None and seat == dummy:
            role = " · Dummy"
            accent = ACC_GOLD
        elif declarer is not None and seat.is_ns() != declarer.is_ns():
            accent = ACC_GREEN          # a defender
        is_danger = bool(danger) and danger["seat"] == seat
        if is_danger:
            role += "  ⚠ danger"
            accent = ACC_RED
        w.set_accent(accent)
        if squeeze and seat in squeeze.get("busy", []):
            role += "  ◆ busy"
        n_left = layout["remaining_count"][seat]
        # HCP context: exact for a face-up hand, inferred range otherwise.
        hcp_txt = ""
        if seat in visible and board.hands.get(seat) is not None:
            hcp_txt = f"  {board.hands[seat].hcp()} HCP"
        elif self.detail != BEGINNER and constraints.get(seat) is not None:
            c = constraints[seat]
            if (c.hcp_min, c.hcp_max) != (0, 37):
                hcp_txt = f"  {c.hcp_min}-{c.hcp_max} HCP"
        w.set_title(f"{seat.name.title()}{role}  ({n_left})" + hcp_txt)

        for su in SUIT_ROWS:
            known = layout["known"][seat][su]
            boss = boss_rank(rem, su)
            wins = winners_in_hand(known, rem[su]) \
                if self.detail != BEGINNER else (
                    {boss} & set(known) if boss is not None else set())
            entries: Set[Rank] = set()
            stoppers: Set[Rank] = set()
            if self.detail != BEGINNER:
                # Entry: the access card to declarer's / dummy's hand.
                if seat in (declarer, dummy):
                    er = top_entry_rank(wins)
                    if er is not None:
                        entries = {er}
                # Stopper (NT only) — skip the master ace, whose gold already
                # signals control; badge the K/Q/J guards that add information.
                if trump is None:
                    sr = stopper_rank(known)
                    if sr is not None and sr != boss:
                        stoppers = {sr}
            knockout: Set[Rank] = set()
            if is_danger and danger.get("knockout") \
                    and danger["knockout"][0] == su:
                knockout = {danger["knockout"][1]}
            # Cross-hand communication entry: a low card that reaches the
            # PARTNER (declarer↔dummy) hand's master in this suit (Manley's
            # "transportation") — flagged when this hand has no winner of its own.
            cross: Set[Rank] = set()
            if self.detail == EXPERT and seat in (declarer, dummy):
                mate = dummy if seat == declarer else declarer
                if mate is not None and mate != seat and known:
                    b = boss_rank(rem, su)
                    if (b is not None and b in layout["known"][mate][su]
                            and b not in known):
                        cross = {max(known)}      # lowest card (highest value)
            inferred = layout.get("inferred", {}).get(seat, {}).get(su, set())
            known_html = _render_known(known, su, wins, boss, entries,
                                       stoppers, knockout, cross, inferred)
            other_html = self._other_for(seat, su, visible, layout,
                                         constraints, sig_map, hint_map)
            w.set_row(su, known_html, other_html, trump == su)

    def _other_for(self, seat, su, visible, layout, constraints,
                   sig_map=None, hint_map=None) -> str:
        if self.detail == BEGINNER:
            # Beginners: only proven voids, nothing speculative.
            if seat not in visible and su in layout["voids"][seat]:
                return "<span style='color:#9fb6cc'>void</span>"
            return ""
        sig_map = sig_map or {}
        hint_map = hint_map or {}
        parts = [f"<span style='color:#9fb6cc'>"
                 f"{suit_length_text(seat, su, visible, layout, constraints)}"
                 f"</span>"]
        # What biq's defensive carding has told us about this defender's suit.
        rd = sig_map.get((seat, su))
        if rd is not None:
            parts.append(_signal_chip(rd))
        # Where a missing honour probably sits (proven ones already show in the
        # Known column with a dashed outline, so this is the speculative part).
        hint = hint_map.get((seat, su))
        if hint:
            parts.append(hint)
        return " ".join(parts)

    def _render_contract_panel(self, board, contract, declarer):
        if contract is None:
            self.p_contract.set_html("Auction in progress.")
            return
        dec = declarer.to_char() if declarer else (
            contract.declarer.to_char() if contract.declarer else "?")
        dt = getattr(board, "declarer_tricks", 0)
        df = getattr(board, "defense_tricks", 0)
        need = max(0, contract.target_tricks() - dt)
        # The race (Bayone/Manley/Frey): both sides have a target; show the gap.
        def_need = max(0, (14 - contract.target_tricks()) - df)
        vul = getattr(getattr(board, "vulnerability", None), "name", "")
        self.p_contract.set_html(
            f"<b>{contract.to_str()}</b> by {dec}<br>"
            f"Declarer tricks: <b>{dt}</b>　Defence: <b>{df}</b><br>"
            f"<b>The race:</b> declarer needs <b>{need}</b> more, "
            f"defence needs <b>{def_need}</b> to beat it.<br>"
            f"<span style='color:#9fb6cc'>Vul: {vul}</span>")

    def _render_plan_panel(self, board, contract, declarer, dummy, visible,
                           layout, trump, danger=None):
        if contract is None or declarer is None:
            self.p_plan.set_html("")
            return
        lines = []
        side = (declarer, dummy) if dummy is not None else None
        if side is not None:
            tt = side_top_tricks(board, side, visible, layout)
            if tt is not None:
                lines.append(f"Top tricks (declaring side): <b>{tt}</b>")
        if trump is None:
            lines.append("NT: count winners, develop the rest in your "
                         "longest suit — build before you cash.")
        else:
            if declarer in visible and board.hands.get(declarer):
                ltc = losing_trick_count({su: layout['known'][declarer][su]
                                          for su in SUIT_ROWS})
                lines.append(f"Declarer losers (LTC): <b>{ltc}</b>")
            # Reese §62: the second planning question in a suit contract.
            lines.append("<i>Shall I draw trumps? If not, why not?</i>")
            # Outstanding trumps + a-priori break (Klinger break-odds table).
            if declarer in visible and dummy is not None and dummy in visible:
                held = (len(layout['known'][declarer][trump]) +
                        len(layout['known'][dummy][trump]))
                out = max(0, len(layout['rem_ranks'][trump]) - held)
                odds = split_odds(out)
                if odds:
                    top = odds[0]
                    lines.append(f"Trumps out: <b>{out}</b> — likely "
                                 f"{top[0]} ({top[1]}%)")
                # Defenders' actual split, shown once it becomes CLEAR (a
                # defender shows out, or is face-up). The "count the hand"
                # payoff: when one defender is void the other holds them all.
                defs = [s for s in Seat if s not in (declarer, dummy)]
                voided = [d for d in defs if trump in layout['voids'][d]]
                facing = [d for d in defs if d in visible]
                if len(voided) == 1:
                    other = [d for d in defs if d not in voided][0]
                    lines.append(
                        f"<span style='color:{ACC_GREEN}'>Defenders' trumps: "
                        f"<b>{voided[0].to_char()}</b> void → "
                        f"<b>{other.to_char()}</b> holds all {out}.</span>")
                elif facing:
                    cnt = " · ".join(
                        (f"<b>{d.to_char()} {len(layout['known'][d][trump])}</b>"
                         if d in visible else f"{d.to_char()} ?") for d in defs)
                    lines.append(
                        f"<span style='color:{ACC_GREEN}'>Defenders' trumps: "
                        f"{cnt}</span>")
            # Master trump still out?
            boss_t = boss_rank(layout["rem_ranks"], trump)
            holder = _holder_of(layout, trump, boss_t, visible)
            if boss_t is not None and holder is not None and \
                    holder not in (declarer, dummy):
                lines.append(f"<span style='color:#ffcf6b'>Opponent holds "
                             f"the master trump ({trump.symbol()}"
                             f"{boss_t.to_char()}) — keep trump control.</span>")
            elif boss_t is not None:
                lines.append("Trump master is yours — draw trumps unless you "
                             "need a ruff/entry.")
        if self.detail != BEGINNER:
            entries = self._entry_summary(layout, visible, declarer, dummy)
            if entries:
                lines.append("Entries: " + entries)
        if danger is not None:
            ds = danger["seat"].to_char()
            if danger.get("mode") == "ruff":
                lines.append(
                    f"<span style='color:#ff9a9a'>Danger: <b>{ds}</b> is void "
                    f"in {danger['threat'].symbol()} and can ruff — draw "
                    f"trumps before conceding the lead.</span>")
            else:
                lines.append(
                    f"<span style='color:#ff9a9a'>Danger hand: <b>{ds}</b> "
                    f"(can run {danger['threat'].symbol()}) — keep off lead, "
                    f"don't finesse into {ds}.</span>")
            ko = danger.get("knockout")
            if ko is not None:
                lines.append(
                    f"<span style='color:#ff9a9a'>Knock out {ds}'s "
                    f"{ko[0].symbol()}{ko[1].to_char()} before "
                    f"{danger['threat'].symbol()} sets up.</span>")
        if self.detail != BEGINNER:
            hu = holdup_rule_of_seven(board, contract, declarer, dummy,
                                      visible, layout)
            if hu is not None:
                if hu["n_total"] <= 0:
                    lines.append(f"Hold-up: win {hu['suit'].symbol()}A now "
                                 f"(Rule of 7 = 0).")
                else:
                    lines.append(
                        f"Hold up {hu['suit'].symbol()}A — Rule of 7: "
                        f"7−{hu['combined']} = duck <b>{hu['n_total']}</b> "
                        f"(<b>{hu['remaining']}</b> left).")
        if self.detail == EXPERT:
            for h in finesse_hints(declarer, dummy, visible, layout):
                lines.append(f"<span style='color:#9fb6cc'>{h}</span>")
        self.p_plan.set_html("<br>".join(lines))

    def _entry_summary(self, layout, visible, declarer, dummy) -> str:
        """Suits where declarer/dummy hold the current master = a sure
        entry to that hand."""
        out = []
        rem = layout["rem_ranks"]
        for hand_seat, tag in ((declarer, "decl"), (dummy, "dummy")):
            if hand_seat is None or hand_seat not in visible:
                continue
            suits = []
            for su in SUIT_ROWS:
                b = boss_rank(rem, su)
                if b is not None and b in layout["known"][hand_seat][su]:
                    suits.append(su.symbol())
            if suits:
                out.append(f"{tag} {''.join(suits)}")
        return "; ".join(out)

    def _render_count_panel(self, board, visible, layout, constraints,
                            squeeze=None):
        if self.detail == BEGINNER:
            self.p_count.set_html(
                "<span style='color:#9fb6cc'>Counting aids appear at "
                "Intermediate / Expert detail.</span>")
            return
        blocks = []
        # Unseen-HCP databank (Klinger, Better Bridge With a Better Memory,
        # ARCH-C: "40 − visible HCP = the points in the two hidden hands").
        unseen = 40 - visible_hcp(board, visible)
        parts = [f"Unseen HCP <b>{unseen}</b>"]
        for s in [s for s in Seat if s not in visible]:
            c = constraints.get(s) if constraints else None
            if c is not None and (c.hcp_min, c.hcp_max) != (0, 37):
                parts.append(f"{s.to_char()}&nbsp;{c.hcp_min}-{c.hcp_max}")
            else:
                parts.append(f"{s.to_char()}&nbsp;?")
        blocks.append(" · ".join(parts))
        if self.detail != EXPERT:
            self.p_count.set_html("<br>".join(blocks))
            return
        rows = ["<table cellspacing='3'>"]
        rows.append("<tr><td></td>" +
                    "".join(f"<td><b>{su.symbol()}</b></td>" for su in SUIT_ROWS) +
                    "<td>cards</td></tr>")
        for s in Seat:
            cells = []
            for su in SUIT_ROWS:
                cells.append(f"<td>{suit_length_text(s, su, visible, layout, constraints)}</td>")
            rows.append(f"<tr><td><b>{s.to_char()}</b></td>" + "".join(cells) +
                        f"<td>{layout['remaining_count'][s]}</td></tr>")
        rows.append("</table>")
        # Honour placement.
        hp = honour_placement(board, visible, layout)
        if hp:
            parts = []
            for su, r, label in hp:
                parts.append(f"{su.symbol()}{r.to_char()}: {label}")
            rows.append("<br><b>Missing honours</b><br>" +
                        " · ".join(parts))
        # Squeeze threats / busy defender.
        if squeeze and squeeze.get("threats"):
            tl = " ".join(f"{su.symbol()}({d.to_char()})"
                          for su, d in squeeze["threats"].items())
            line = "<br><b>Threats</b> " + tl
            if squeeze.get("busy"):
                bb = "/".join(d.to_char() for d in squeeze["busy"])
                line += (f" — <span style='color:#e8b06a'>{bb} is busy "
                         f"(squeeze on)</span>")
            rows.append(line)
        blocks.append("".join(rows))
        self.p_count.set_html("<br>".join(blocks))

    def _render_coach_panel(self, board, contract, declarer, dummy, visible,
                            layout, trump):
        blocks = []

        # --- Opening-lead inference (Rule of 11) ---------------------------
        if self.detail != BEGINNER and contract is not None:
            r11 = rule_of_eleven(board, visible)
            if r11 is not None:
                blocks.append(
                    f"<b>Lead</b> {_card_glyph(r11['card'])} "
                    f"<span style='color:#9fb6cc;font-size:12px'>(4th-best?)</span>"
                    f"<br>Rule of 11: {r11['higher']} higher out; you see "
                    f"{r11['seen']} → <b>{r11['hidden']}</b> in the hidden "
                    f"hand(s).")

        # --- Live defensive signal reads -----------------------------------
        if contract is not None and declarer is not None:
            ns_c = self.ns_carding_combo.currentText()
            ew_c = self.ew_carding_combo.currentText()
            reads = signal_reads(board, declarer, trump, self._carding_for,
                                 visible)
            cur = current_trick_reads(board, declarer, trump, self._carding_for)
            limit = {BEGINNER: 2, INTERMEDIATE: 6}.get(self.detail, 99)
            lines = []
            for r in reads[-limit:]:
                # Discard, Smith, ruff-lead and trump-echo reads name their suit.
                suffix = ("" if (r.get("kind") in ("dsc", "smith", "ruflead")
                                 or r.get("tag") in ("ruff", "te"))
                          else f" {r['suit'].symbol()}")
                # Honesty marker — only meaningful when the signaller is face-up
                # (review / Show All). ✗ flags a false-card; ✓ (Expert) confirms.
                mark = ""
                if r.get("honest") is False and r.get("expected") is not None:
                    mark = (f" <span style='color:#ff9a9a'>✗ false "
                            f"(→ {_card_glyph(r['expected'])})</span>")
                elif r.get("honest") is True and self.detail == EXPERT:
                    mark = " <span style='color:#7ad17a'>✓</span>"
                lines.append(
                    f"T{r['trick'] + 1} <b>{r['seat'].to_char()}</b> "
                    f"{_card_glyph(r['card'])} → {r['meaning']}"
                    f"{suffix} {_tag_html(r['tag'])}{mark}")
            for seat, r in cur.items():
                lines.append(
                    f"now <b>{seat.to_char()}</b> {_card_glyph(r['card'])} → "
                    f"{r['meaning']} {_tag_html(r['tag'])}")
            head = (f"<b>Signals</b> "
                    f"<span style='color:#9fb6cc;font-size:12px'>"
                    f"(N/S {ns_c} · E/W {ew_c})</span>")
            if lines:
                blocks.append(head + "<br>" + "<br>".join(lines))
            elif self.detail != BEGINNER:
                blocks.append(head + "<br><span style='color:#7f96ac'>"
                              "no clear spot-card signals yet</span>")

        tips = []
        n_played = len(layout["all_played"])
        if contract is None:
            tips.append("Bidding in progress — note each call's meaning.")
        elif n_played == 0:
            if trump is None:
                tips.append("Count your sure tricks, then plan to develop "
                            "the extra ones before touching an honour.")
            else:
                tips.append("Count your losers first. Then ask: draw trumps "
                            "now, or ruff / set up a suit first?")
        else:
            boss_t = boss_rank(layout["rem_ranks"], trump) if trump else None
            holder = _holder_of(layout, trump, boss_t, visible) if trump else None
            if trump and boss_t is not None and holder is not None and \
                    holder not in (declarer, dummy):
                tips.append("An opponent still holds the master trump — don't "
                            "draw the last trump if you need it.")
            else:
                tips.append("Keep counting: track each suit's split as cards "
                            "appear, and watch the discards.")
        # Defender signalling note (intermediate+).
        if self.detail != BEGINNER:
            tips.append("<span style='color:#9fb6cc'>Carding: attitude on "
                        "partner's suit, count on declarer's, suit-preference "
                        "on discards. Set each pair's agreement in the header."
                        "</span>")
        if self.detail == EXPERT and trump is None and contract is not None:
            tips.append("<span style='color:#9fb6cc'>Squeeze check (BLUE): "
                        "both threats with one defender, rectify the count, "
                        "threat in the upper hand, entry to it.</span>")
        if tips:
            blocks.append("<br>".join(f"• {t}" for t in tips))
        self.p_coach.set_html("<hr style='border:0;border-top:1px solid #243447'>"
                              .join(blocks))

    def _render_centre(self, board, contract, declarer, trump):
        ct = getattr(board, "current_trick", None)
        played = {}
        leader = None
        if ct is not None:
            cards = getattr(ct, "cards", None) or []
            leader = getattr(ct, "leader", None)
            if leader is not None and cards:
                base = int(leader)
                for i, c in enumerate(cards):
                    played[Seat((base + i) % 4)] = c
        # Live signal tags on the defenders' cards in this very trick.
        cur_reads = current_trick_reads(board, declarer, trump,
                                        self._carding_for)
        def cell(seat):
            c = played.get(seat)
            if c is None:
                return "·"
            col = _suit_color(c.suit)
            html = (f"<span style='color:{col}; font-weight:bold'>"
                    f"{c.suit.symbol()}{c.rank.to_char()}</span>")
            r = cur_reads.get(seat)
            if r is not None:
                html += "<br>" + _tag_html(r["tag"])
            return html
        on_lead = ""
        if leader is not None and len(played) < 4:
            nxt = Seat((int(leader) + len(played)) % 4)
            on_lead = f"<br><span style='color:#9fb6cc'>On lead/to play: " \
                      f"{nxt.name.title()}</span>"
        html = (
            f"<div align='center'>"
            f"<table cellpadding='4' align='center'>"
            f"<tr><td></td><td align='center'>{cell(Seat.NORTH)}</td><td></td></tr>"
            f"<tr><td align='center'>{cell(Seat.WEST)}</td><td></td>"
            f"<td align='center'>{cell(Seat.EAST)}</td></tr>"
            f"<tr><td></td><td align='center'>{cell(Seat.SOUTH)}</td><td></td></tr>"
            f"</table>{on_lead}</div>")
        self.centre.set_html(html)


# ---------------------------------------------------------------------------
# small render helpers
# ---------------------------------------------------------------------------

def _render_known(ranks_high_to_low: List[Rank], suit: Suit,
                  winners: Set[Rank], boss: Optional[Rank],
                  entries: Optional[Set[Rank]] = None,
                  stoppers: Optional[Set[Rank]] = None,
                  knockout: Optional[Set[Rank]] = None,
                  cross: Optional[Set[Rank]] = None,
                  inferred: Optional[Set[Rank]] = None) -> str:
    if not ranks_high_to_low:
        return "<span style='color:#5f7689'>—</span>"
    entries = entries or set()
    stoppers = stoppers or set()
    knockout = knockout or set()
    cross = cross or set()
    inferred = inferred or set()
    col = _suit_color(suit)
    parts = []
    for r in ranks_high_to_low:
        ch = r.to_char()
        style = f"color:{col};"
        if boss is not None and r == boss:
            style += (f"background:{MASTER_BG}; color:#06121f; font-weight:bold;"
                      f" border-radius:3px; padding:0 3px;")
        elif r in winners:
            # sure winner — vivid green box (was a faint underline)
            style += (f"color:{col}; border:1px solid {ACC_GREEN};"
                      f" border-radius:3px; padding:0 2px; font-weight:bold;")
        elif r in inferred:
            # PLACED by deduction (hand is hidden but this card must be here) —
            # dashed outline so it reads as "known, not seen".
            style += (f"color:{col}; border:1px dashed {ACC_YELLOW};"
                      f" border-radius:3px; padding:0 2px;")
        # Vivid inverse-video role chips replace the old superscripts.
        badge = ""
        if r in entries:        # access to this hand
            badge += _chip("E", ACC_GREEN)
        if r in stoppers:       # guards the suit (NT)
            badge += _chip("S", ACC_BLUE)
        if r in knockout:       # danger hand's entry to knock out
            badge += _chip("KO", ACC_RED)
        if r in cross:          # low card that reaches partner's winner
            badge += _chip("→", ACC_ORANGE)
        parts.append(f"<span style='{style}'>{ch}</span>{badge}")
    return " ".join(parts)


# A-priori vacant-space split odds for N cards missing (rounded %). Used for
# the "how will this suit break?" chip (Klinger, Bridge for a Better Memory,
# p34: "odd numbers break evenly, even break oddly"; Bayone ch.28).
_SPLIT_ODDS = {
    2: [("1-1", 52), ("2-0", 48)],
    3: [("2-1", 78), ("3-0", 22)],
    4: [("3-1", 50), ("2-2", 40), ("4-0", 10)],
    5: [("3-2", 68), ("4-1", 28), ("5-0", 4)],
    6: [("4-2", 48), ("3-3", 36), ("5-1", 15), ("6-0", 1)],
    7: [("4-3", 62), ("5-2", 31), ("6-1", 7)],
}


def split_odds(missing: int):
    return _SPLIT_ODDS.get(missing)


def visible_hcp(board, visible) -> int:
    tot = 0
    for s in visible:
        h = board.hands.get(s) if board.hands else None
        if h is not None:
            tot += h.hcp()
    return tot


def rule_of_eleven(board, visible):
    """If the hand opened with a spot lead (treated as 4th-best), return the
    Rule-of-11 read: {suit, card, higher, seen, hidden}. `higher` = cards above
    the lead in the other three hands (11 − pip); `seen` = those visible to us
    (excluding the leader); `hidden` = the rest, i.e. in the concealed hands.

    ACBL Encyclopedia "Rule of Eleven"; Sheinwold 29th Day. Only meaningful for
    a genuine 4th-best spot lead, so we fire only on a spot of 9 or below."""
    tricks = getattr(board, "tricks", None) or []
    ct = getattr(board, "current_trick", None)
    lead = leader = None
    if tricks and (getattr(tricks[0], "cards", None)):
        lead, leader = tricks[0].cards[0], tricks[0].leader
    elif not tricks and ct is not None and (getattr(ct, "cards", None)):
        lead, leader = ct.cards[0], ct.leader
    if lead is None or leader is None:
        return None
    pip = 14 - int(lead.rank)            # A=14 … 2=2
    if pip > 9:                          # honour / 10 — not a clean 4th-best read
        return None
    higher = 11 - pip
    if higher <= 0:
        return None
    seen = 0
    for s in visible:
        if s == leader:
            continue                     # Rule of 11 counts the OTHER three hands
        h = board.hands.get(s) if board.hands else None
        if not h:
            continue
        seen += sum(1 for c in h.cards
                    if c.suit == lead.suit and (14 - int(c.rank)) > pip)
    return {"suit": lead.suit, "card": lead, "higher": higher,
            "seen": seen, "hidden": max(0, higher - seen)}


def _opening_leader(board, declarer: Seat) -> Seat:
    tricks = getattr(board, "tricks", None) or []
    if tricks and getattr(tricks[0], "leader", None) is not None:
        return Seat(int(tricks[0].leader))
    ct = getattr(board, "current_trick", None)
    if not tricks and ct is not None and getattr(ct, "leader", None) is not None:
        return Seat(int(ct.leader))
    return Seat((int(declarer) + 1) % 4)            # LHO by default


def _threat_suit(board, declarer: Seat) -> Optional[Suit]:
    """The defenders' threat suit at NT = the opening-lead suit (their long
    suit). None until a defender has led."""
    tricks = getattr(board, "tricks", None) or []
    lead = None
    if tricks and getattr(tricks[0], "cards", None):
        if getattr(tricks[0], "leader", None) is None:
            return None
        if Seat(int(tricks[0].leader)).is_ns() == declarer.is_ns():
            return None
        lead = tricks[0].cards[0]
    else:
        ct = getattr(board, "current_trick", None)
        if not tricks and ct is not None and getattr(ct, "cards", None) \
                and getattr(ct, "leader", None) is not None \
                and Seat(int(ct.leader)).is_ns() != declarer.is_ns():
            lead = ct.cards[0]
    return lead.suit if lead is not None else None


def _est_length(seat, suit, visible, layout, constraints) -> float:
    """Best estimate of a seat's length in a suit (exact if face-up)."""
    if seat in visible:
        return float(len(layout["known"][seat][suit]))
    if suit in layout["voids"][seat]:
        return 0.0
    lo, hi = 0, 13
    c = constraints.get(seat) if constraints else None
    if c is not None:
        lo, hi = c.suit_len.get(suit.value, (0, 13))
    known = len(layout["known"][seat][suit])
    lo = max(lo, known)
    hi = min(hi, layout["unseen_by_suit"].get(suit, 0) + known)
    if lo > hi:
        lo = hi
    return (lo + hi) / 2.0


def _knockout_entry(layout, danger_seat, threat, visible):
    """A PROVEN side-suit entry in the danger hand to knock out before the
    threat suit sets up: an Ace (sure), or a King if the hand is face-up.
    Returns (suit, rank) or None."""
    for su in SUIT_ROWS:
        if su == threat:
            continue
        if Rank.ACE in layout["known"][danger_seat][su]:
            return (su, Rank.ACE)
    if danger_seat in visible:
        for su in SUIT_ROWS:
            if su == threat:
                continue
            if Rank.KING in layout["known"][danger_seat][su]:
                return (su, Rank.KING)
    return None


def danger_info(board, contract, declarer, visible, layout, constraints):
    """At NT, the danger hand (the defender who can run the threat suit) and the
    entry to knock out. Returns {seat, threat, knockout, leader} or None.

    Danger hand = the defender longer in the threat suit (the opening-lead
    suit); ties default to the opening leader, who led from length."""
    if contract is None or declarer is None:
        return None
    if contract.suit != Suit.NOTRUMP:
        # Suit contract: the danger is a RUFF — a defender void in a side suit
        # who still has trumps. Remedy is to draw trumps, so no knock-out entry.
        trump = contract.suit
        if trump in layout["voids"]:                 # sanity
            pass
        out_trumps = bool(layout["rem_ranks"].get(trump))
        if not out_trumps:
            return None                              # trumps gone — no ruff danger
        for d in [s for s in Seat if s.is_ns() != declarer.is_ns()]:
            if trump in layout["voids"][d]:
                continue                             # can't ruff (void in trumps)
            for su in SUIT_ROWS:
                if su == trump:
                    continue
                if su in layout["voids"][d]:         # proven side-suit void
                    return {"seat": d, "threat": su, "knockout": None,
                            "leader": _opening_leader(board, declarer),
                            "mode": "ruff"}
        return None
    threat = _threat_suit(board, declarer)
    if threat is None:
        return None
    leader = _opening_leader(board, declarer)
    defenders = [s for s in Seat if s.is_ns() != declarer.is_ns()]
    if len(defenders) != 2:
        return None
    a, b = defenders
    ea, eb = (_est_length(a, threat, visible, layout, constraints),
              _est_length(b, threat, visible, layout, constraints))
    if abs(ea - eb) < 0.5:
        ds = leader if leader in defenders else (a if ea >= eb else b)
    else:
        ds = a if ea > eb else b
    return {"seat": ds, "threat": threat,
            "knockout": _knockout_entry(layout, ds, threat, visible),
            "leader": leader, "mode": "run"}


def holdup_rule_of_seven(board, contract, declarer, dummy, visible, layout):
    """Rule of 7 (NT): the number of times to hold up the ace in the danger
    (opening-lead) suit = 7 − (combined declarer + dummy length in that suit),
    so the danger hand is exhausted of the suit. Returns a dict or None.

    Needs both declarer + dummy face-up and the declaring side to still hold the
    ace (the stopper being held up). Length is the ORIGINAL holding (current +
    cards already played), so the count is stable as the suit is played out."""
    if (contract is None or declarer is None or dummy is None
            or contract.suit != Suit.NOTRUMP):
        return None
    if declarer not in visible or dummy not in visible:
        return None
    threat = _threat_suit(board, declarer)
    if threat is None:
        return None
    if (Rank.ACE not in layout["known"][declarer][threat]
            and Rank.ACE not in layout["known"][dummy][threat]):
        return None                              # ace already played / not held
    played, _, _ = collect_play(board)

    def orig_len(seat):
        cur = len(layout["known"][seat][threat])
        gone = sum(1 for cid in played[seat] if Suit(cid // 13) == threat)
        return cur + gone

    combined = orig_len(declarer) + orig_len(dummy)
    n_total = max(0, 7 - combined)
    rounds = 0
    for t in (getattr(board, "tricks", None) or []):
        cards = getattr(t, "cards", None) or []
        if cards and cards[0].suit == threat:
            rounds += 1
    ct = getattr(board, "current_trick", None)
    if ct is not None and getattr(ct, "cards", None) \
            and ct.cards[0].suit == threat:
        rounds += 1
    return {"suit": threat, "combined": combined, "n_total": n_total,
            "rounds": rounds, "remaining": max(0, n_total - rounds)}


def _holder_of(layout, suit, rank, visible) -> Optional[Seat]:
    """Which seat is PROVEN to hold a given card now (or None)."""
    if rank is None:
        return None
    for s in Seat:
        if rank in layout["known"][s][suit]:
            return s
    return None


def _sys_name(system) -> str:
    if system is None:
        return "?"
    return getattr(system, "name", None) or str(system)
