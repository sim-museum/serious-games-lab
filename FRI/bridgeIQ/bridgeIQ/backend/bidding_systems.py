"""Bidding-system specifications, modelled on Q-Plus Bridge 17.1.

Q-Plus's bidding logic lives in two layers:

  * A binary rule engine (`BIDRULE/CMP/*.rl`) that we cannot read.
  * Plain-text **convention declarations** in `CONFIG/BIDRULE/*.RCE`
    that pick which conventions are turned on for the system, with
    numeric parameters (1NT range, 2/1 minimum, RKC variant, …).

This module reads the second layer. It exposes a `BiddingSystem`
dataclass that captures the numeric knobs in structured fields plus
the raw flag set so the rule-based bidder can ask
`system.has("A-1NT-Stayman")` for any convention we model.

The Q-Plus files describe several bundled systems; we ship support
for the ones we can validate end-to-end against Q-Plus's gameplay:

  * **`SAYC`** — *Standard American Yellow Card (Q-plus)*
    (`A-SAYC-I.RCE`), 15-17 1NT, 5-card majors, 2/1 ≥ 10 HCP.
  * **`TwoOverOne`** — *2-over-1 Game Forcing* (`A-2-1-A.RCE`).
  * **`StandardAcol`** — *Standard Acol* (`B-ACL-S.RCE`).
  * **`StandardFrench`** — *Standard French / SEF*
    (`F-FRA-M.RCE`).
  * **`Precision90M`** — *Precision Club 90 modern* (`P-P90M-A.RCE`),
    14-16 1NT, light-opening 1-suit, Kokish, Bergen-3C, Ghestem.

The other Precision flavours (`Precision90P`, `Precision70`) and
the wbridge5-tuned SAYC variant were dropped — without a live
opponent that bids those systems we have no way to validate
them, and the maintenance burden outweighs the value.

Adding more is a matter of dropping their `.RCE` paths into the
catalog and (optionally) overriding any post-parse adjustments.

If the Q-Plus install isn't present (no `.RCE` file at the expected
path), the catalog falls back to hand-coded defaults so bridgeIQ
keeps working on a clean machine.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# .RCE flag parsing
# ---------------------------------------------------------------------------

# Match a Q-Plus parameter token: ".p15" (positive 15), ".p-1" (-1), etc.
_PARAM_NUM_RE = re.compile(r"\.p(-?\d+)$")

# A convention line looks like:
#   "Y B-1NT.v-1.min-hcp.p15"
#   "Y A-2-over-1-min.hcp-10"
#   "N A-1MA-splinter"
_RULE_LINE_RE = re.compile(r"^\s*([YN])\s+([\S]+)\s*$")


@dataclass(frozen=True)
class RCERule:
    """One parsed line out of a .RCE convention file.

    `name` is the dotted key with the trailing `.p<NUM>` stripped if any
    (so multi-valued parameters land in `value` rather than the name).
    `enabled` is `Y`/`N` from the leading flag.
    """

    name: str
    enabled: bool
    value: Optional[int] = None
    raw: str = ""

    def matches(self, prefix: str) -> bool:
        """True if this rule's name starts with `prefix` (dot- or full-match)."""
        return self.name == prefix or self.name.startswith(prefix + ".") \
            or self.name.startswith(prefix + "-")


def parse_rce_file(path: str | Path) -> Tuple[Dict[str, RCERule], str]:
    """Parse a Q-Plus `.RCE` file. Returns `(rules_by_name, description)`.

    `rules_by_name` is keyed by the canonical flag name (with `.pNN`
    parameter stripped — see `RCERule.value`). `description` is the
    `.description.eng = "..."` line if present.
    """
    rules: Dict[str, RCERule] = {}
    description = ""

    path = Path(path)
    if not path.is_file():
        return rules, description

    with open(path, "r", encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Header fields like ".description.eng = \"...\""
            if stripped.startswith(".description.eng"):
                m = re.match(r'\.description\.eng\s*=\s*"(.*)"', stripped)
                if m:
                    description = m.group(1)
                continue
            if stripped.startswith("."):
                continue
            if stripped.lower() == "conventions":
                continue
            m = _RULE_LINE_RE.match(line)
            if not m:
                continue
            yn, key = m.groups()
            value: Optional[int] = None
            pm = _PARAM_NUM_RE.search(key)
            if pm:
                value = int(pm.group(1))
                key = key[: pm.start()]
            rules[key] = RCERule(
                name=key,
                enabled=(yn.upper() == "Y"),
                value=value,
                raw=line,
            )
    return rules, description


# ---------------------------------------------------------------------------
# BiddingSystem dataclass
# ---------------------------------------------------------------------------


@dataclass
class BiddingSystem:
    """Structured view of a Q-Plus bidding system.

    Fields fall into two groups:

      * **Numeric parameters** — extracted from `.RCE` `.pNN` tokens
        where possible, with sensible fallbacks if the file is absent.
        These are what the rule-based bidder reads when deciding
        ranges / thresholds.
      * **Convention set** — `conventions` is the set of flag names the
        `.RCE` file marked `Y`. Code asks
        `"A-1NT-Stayman" in system.conventions` to gate a convention.

    `raw_rules` is the full parsed `.RCE` dict, kept for downstream
    code that wants to query parameters we don't yet model.
    """

    name: str
    description: str = ""

    # ----- Opening structure -----
    one_nt_min_hcp: int = 15
    one_nt_max_hcp: int = 17
    # Some systems allow 5-card majors / 6-card minors inside 1NT.
    one_nt_allow_five_card_heart: bool = False
    one_nt_allow_five_card_spade: bool = False
    one_nt_allow_six_card_minor: bool = False
    two_nt_min_hcp: int = 20
    two_nt_max_hcp: int = 21
    # Strong artificial opening (2♣ in SAYC, 1♣ in Precision).
    strong_open_call: str = "2C"   # "2C" or "1C"
    strong_open_min_hcp: int = 22  # 22+ for 2C; 16+ for Precision 1C
    one_major_card_min: int = 5    # 5-card-majors flag
    # Weak two opening style.
    weak_two_diamonds: bool = True
    weak_two_majors: bool = True
    weak_two_min_hcp: int = 6
    weak_two_max_hcp: int = 11
    # Precision 1♦ opening; only used when strong_open_call == "1C".
    one_diamond_min_hcp: int = 11
    one_diamond_max_hcp: int = 15
    # Precision 2♣ — long-club opening (Precision) range.
    precision_two_clubs_min_hcp: int = 11
    precision_two_clubs_max_hcp: int = 15
    # Precision 2♦ — 4-4-1-4 / 4-4-0-5 three-suiter (some flavours 4-4-x-x).
    precision_two_diamonds_shape: str = "4-4-1"   # "4-4-1" or "4-3-x"

    # ----- Responses -----
    two_over_one_min_hcp: int = 10  # Q-Plus SAYC: 10+. 2/1 GF systems use 13.
    one_nt_response_min_hcp: int = 6
    one_nt_response_max_hcp: int = 9
    rebid_one_nt_range: Tuple[int, int] = (12, 14)  # opener's 1-1-1NT rebid
    jump_rebid_two_nt_range: Tuple[int, int] = (18, 19)

    # ----- Slam -----
    rkc_variant: str = "1430"     # "1430" or "0314" — Q-Plus encodes this as RKCB0314 / RKCB1430

    # ----- Convention set -----
    conventions: Set[str] = field(default_factory=set)

    # Original parsed rules for unmodelled queries.
    raw_rules: Dict[str, RCERule] = field(default_factory=dict)

    # Path the system was loaded from (empty when using fallbacks).
    source_path: str = ""

    # --------- Convenience queries -------------------------------------

    def has(self, flag: str) -> bool:
        """True iff a convention flag is enabled in this system."""
        return flag in self.conventions

    def value(self, flag: str, default: Optional[int] = None) -> Optional[int]:
        """Return the numeric .pNN value attached to `flag`, or `default`."""
        rule = self.raw_rules.get(flag)
        return rule.value if (rule is not None and rule.value is not None) else default

    def summary(self) -> str:
        """One-line text summary suitable for status / log lines."""
        return (
            f"{self.name}: 1NT={self.one_nt_min_hcp}-{self.one_nt_max_hcp}, "
            f"strong-open={self.strong_open_call} ({self.strong_open_min_hcp}+), "
            f"2/1≥{self.two_over_one_min_hcp}, RKC={self.rkc_variant}, "
            f"{len(self.conventions)} conventions enabled"
        )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _qplus_dirs() -> List[Path]:
    """Search paths where Q-Plus might have dropped its `.RCE` files."""
    here = Path(__file__).resolve()
    wp_candidates: List[Path] = []
    # Walk up to find a sibling `WP` directory (FRI/.../WP).
    for parent in here.parents:
        cand = parent / "WP" / "drive_c" / "games"
        if cand.is_dir():
            wp_candidates.append(cand)
            break
    # Honour WINEPREFIX too.
    env = os.environ.get("WINEPREFIX")
    if env:
        wp_candidates.append(Path(env) / "drive_c" / "games")

    out: List[Path] = []
    for base in wp_candidates:
        for qb in ("qbridge17", "qbridge15"):
            cand = base / qb / "CONFIG" / "BIDRULE"
            if cand.is_dir():
                out.append(cand)
    return out


def _find_rce(filename: str) -> Optional[Path]:
    """Locate a specific `.RCE` filename inside any known Q-Plus install."""
    for d in _qplus_dirs():
        cand = d / filename
        if cand.is_file():
            return cand
    return None


def _apply_one_nt_range(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    """Q-Plus expresses the 1NT range per (vulnerability, seat) — eight
    permutations of `B-1NT.{v,nv}-{1..4}.{min,max}-hcp.pNN`. They almost
    always agree; we pull the first vulnerable-1st-seat pair and treat
    that as the canonical range.
    """
    mn = rules.get("B-1NT.nv-1.min-hcp") or rules.get("B-1NT.v-1.min-hcp")
    mx = rules.get("B-1NT.nv-1.max-hcp") or rules.get("B-1NT.v-1.max-hcp")
    if mn is not None and mn.value is not None:
        sys_.one_nt_min_hcp = mn.value
    if mx is not None and mx.value is not None:
        sys_.one_nt_max_hcp = mx.value


def _apply_two_nt_range(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    # `B-2NT.strong-balanced.range-20-21` (no .pNN, embedded in flag name)
    # — parse the trailing range.
    for key in ("B-2NT.strong-balanced.range-20-21",
                "B-2NT.strong-balanced.range-22-23"):
        if key in rules:
            m = re.search(r"range-(\d+)-(\d+)$", key)
            if m:
                sys_.two_nt_min_hcp = int(m.group(1))
                sys_.two_nt_max_hcp = int(m.group(2))
            return


def _apply_strong_open(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    # SAYC: B-strong-artificial.bid-2C.forcing-until-3MA → strong 2♣.
    # Precision: B-strong-artificial.bid-1C.min-hcp-16 → strong 1♣ (16+).
    if any(k.startswith("B-strong-artificial.bid-1C") for k in rules):
        sys_.strong_open_call = "1C"
        for k in rules:
            m = re.match(r"B-strong-artificial\.bid-1C\.min-hcp-(\d+)$", k)
            if m:
                sys_.strong_open_min_hcp = int(m.group(1))
                return
        sys_.strong_open_min_hcp = 16
    else:
        sys_.strong_open_call = "2C"
        # SAYC: 22+ HCP or 8.5 quick tricks — we model the HCP arm.
        sys_.strong_open_min_hcp = 22


def _apply_two_diamonds(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    if "B-2D.weak" in rules:
        sys_.weak_two_diamonds = True
    elif any(k.startswith("B-2D.Precision") for k in rules):
        sys_.weak_two_diamonds = False
        for k in rules:
            m = re.match(r"B-2D\.Precision\.majors-(\d)-(\d)$", k)
            if m:
                # "majors-4-3" → at least 4-4 (=4-3 means 4-card and 3+ card
                # majors per Q-Plus naming). We approximate with the larger
                # of the two as the shape descriptor.
                sys_.precision_two_diamonds_shape = f"{m.group(1)}-{m.group(2)}-1"


def _apply_rkc(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    # Q-Plus encodes the variant in the flag name itself.
    for k in rules:
        if k.startswith("S-Blackwood.keycard."):
            tail = k.split(".")[-1]
            if tail.endswith("1430"):
                sys_.rkc_variant = "1430"
                return
            if tail.endswith("0314"):
                sys_.rkc_variant = "0314"
                return
    # Fallback: detect classic ace-asking Blackwood from the 4NT
    # bid-entry name. Q-Plus's Precision Club 90 modern declares
    # "Blackwood / RKCB (ace-ask)" without an explicit keycard flag,
    # which means count aces only (5♣=0/4, 5♦=1, 5♥=2, 5♠=3).
    for r in rules.values():
        nm = (getattr(r, "name", "") or "").lower()
        if "blackwood" in nm and "ace-ask" in nm:
            sys_.rkc_variant = "classic"
            return


def _apply_two_over_one(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    # SAYC and Q-Plus's Precisions both use `A-2-over-1-min.hcp-10`.
    for k in rules:
        m = re.match(r"A-2-over-1-min\.hcp-(\d+)$", k)
        if m:
            sys_.two_over_one_min_hcp = int(m.group(1))
            return


def _apply_rebid_1nt(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    # `R-1-1-1NT.hcp-range-3` means the rebid covers a 3-HCP range.
    # Q-Plus implies 12-14 for that; encode as (12, 14) unless we see
    # an explicit different range.
    for k in rules:
        m = re.match(r"R-1-1-1NT\.hcp-range-(\d+)$", k)
        if m:
            width = int(m.group(1))
            sys_.rebid_one_nt_range = (12, 12 + width - 1)
            return


def _apply_major_open_card_min(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    """Q-Plus's major-suit opening style flag controls how many cards a
    1♥ / 1♠ opening promises:
      `B-1MA-5-cards.all-seats`       → 5 in every seat (SAYC, 2/1, MSF)
      `B-1MA-5-cards.first-2-seats`   → 5 in 1st/2nd seat, 4 OK in 3rd/4th
      `B-1MA-5-cards.unpassed-only`   → same as above (Q-Plus variant)
      `B-1MA-5-cards.guaranted`       → 5 always, strictly enforced
      (missing entirely)              → 4-card majors (Acol family)
    We collapse to a single integer: the strictest minimum the system
    actively requires. The bidder uses this to decide whether to open
    1♥/1♠ on a 4-card holding.
    """
    if "B-1MA-5-cards.all-seats" in rules \
            or "B-1MA-5-cards.guaranted" in rules:
        sys_.one_major_card_min = 5
        return
    if "B-1MA-5-cards.first-2-seats" in rules \
            or "B-1MA-5-cards.unpassed-only" in rules:
        # Effectively 5 except in pass-out seats; the bidder treats this
        # as 5 since seat-aware opener logic isn't yet differentiated.
        sys_.one_major_card_min = 5
        return
    # No 5-card-majors flag — system uses 4-card majors (Acol-style).
    sys_.one_major_card_min = 4


def _apply_one_nt_style(sys_: BiddingSystem, rules: Dict[str, RCERule]) -> None:
    sys_.one_nt_allow_five_card_heart = (
        "B-1NT-style.weak-5-heart" in rules
        or "B-1NT-style.any-5-heart" in rules
    )
    sys_.one_nt_allow_five_card_spade = (
        "B-1NT-style.weak-5-spade" in rules
        or "B-1NT-style.any-5-spade" in rules
    )
    sys_.one_nt_allow_six_card_minor = "B-1NT-style.weak-6-minor" in rules


def _build_from_rce(name: str, rce_path: Path) -> BiddingSystem:
    rules, description = parse_rce_file(rce_path)
    enabled = {k for k, r in rules.items() if r.enabled}
    sys_ = BiddingSystem(
        name=name,
        description=description,
        conventions=enabled,
        raw_rules=rules,
        source_path=str(rce_path),
    )
    _apply_one_nt_range(sys_, rules)
    _apply_two_nt_range(sys_, rules)
    _apply_strong_open(sys_, rules)
    _apply_two_diamonds(sys_, rules)
    _apply_rkc(sys_, rules)
    _apply_two_over_one(sys_, rules)
    _apply_rebid_1nt(sys_, rules)
    _apply_one_nt_style(sys_, rules)
    _apply_major_open_card_min(sys_, rules)
    _synthesize_convention_aliases(sys_)
    return sys_


def _synthesize_convention_aliases(sys_: BiddingSystem) -> None:
    """Add native-side convention flags when a Q-Plus equivalent is on.

    Our native_bidder uses internal flag names (e.g.
    `A-1MA-Jacoby-2NT`) that aren't present in Q-Plus's .RCE files,
    which use longer descriptive names like
    `A-1MA-2NT.support-4-strong`. After loading the .RCE we
    synthesize the internal aliases so the bidder gates correctly
    without needing to track both naming conventions everywhere.
    """
    # Jacoby 2NT — Q-Plus "natural 2NT response shows 4+ support GF".
    if "A-1MA-2NT.support-4-strong" in sys_.conventions \
            or "A-1MA-2NT-J2NT" in sys_.conventions:
        sys_.conventions.add("A-1MA-Jacoby-2NT")


# ---------------------------------------------------------------------------
# Catalog (built-in systems)
# ---------------------------------------------------------------------------


# Each entry is (canonical name, .RCE filename, fallback factory). The
# fallback is used when the .RCE isn't installed — keeps the bidder
# usable on a clean machine.

def _fallback_sayc() -> BiddingSystem:
    return BiddingSystem(
        name="SAYC",
        description="Standard American Yellow Card (built-in fallback)",
        one_nt_min_hcp=15, one_nt_max_hcp=17,
        two_nt_min_hcp=20, two_nt_max_hcp=21,
        strong_open_call="2C", strong_open_min_hcp=22,
        weak_two_diamonds=True, weak_two_majors=True,
        weak_two_min_hcp=6, weak_two_max_hcp=11,
        two_over_one_min_hcp=10,
        rebid_one_nt_range=(12, 14),
        jump_rebid_two_nt_range=(18, 19),
        rkc_variant="1430",
        conventions=set(_FALLBACK_SAYC_CONVENTIONS),
    )


def _fallback_precision90m() -> BiddingSystem:
    return BiddingSystem(
        name="Precision90M",
        description="Precision Club 90 modern (built-in fallback)",
        # Per Q-Plus's P-P90M-A.RCE rule file the limited NT is
        # 14-16 (B-1NT.{nv,v}-{1..4}.{min,max}-hcp = p14..p16). The
        # bundled Precision90M.json describes the bid name as
        # "balanced 13-15" but that is a stale comment; the live
        # ruleset Q-Plus uses is 14-16.
        one_nt_min_hcp=14, one_nt_max_hcp=16,
        two_nt_min_hcp=20, two_nt_max_hcp=21,
        strong_open_call="1C", strong_open_min_hcp=16,
        weak_two_diamonds=False, weak_two_majors=True,
        weak_two_min_hcp=6, weak_two_max_hcp=11,
        one_diamond_min_hcp=11, one_diamond_max_hcp=15,
        precision_two_clubs_min_hcp=11, precision_two_clubs_max_hcp=15,
        precision_two_diamonds_shape="4-4-1",
        two_over_one_min_hcp=10,
        rebid_one_nt_range=(12, 14),
        jump_rebid_two_nt_range=(18, 19),
        rkc_variant="1430",
        conventions=set(_FALLBACK_PRECISION_CONVENTIONS),
    )


def _fallback_two_over_one() -> BiddingSystem:
    """SAYC variant where new-suit-at-2-level is game-forcing.

    Q-Plus's `A-2-1-A` encodes the threshold as `A-2-over-1-min.hcp-11`
    (effectively GF-strength). Other openings and conventions match
    SAYC closely. Used by wBridge5's "Wbridge5" preset and bb12's "2/1".
    """
    s = _fallback_sayc()
    s.name = "TwoOverOne"
    s.description = "2/1 game forcing (built-in fallback)"
    s.two_over_one_min_hcp = 11  # Q-Plus encoding for GF
    return s


def _fallback_acol() -> BiddingSystem:
    """4-card-majors Acol with weak 1NT.

    Q-Plus's `B-ACL-S.RCE`. 1NT is 12-14 balanced. 1♥/1♠ may be opened
    on 4 cards in any seat. Strong 2♣ is the only forcing 2-bid;
    2♦/2♥/2♠ are typically used as Benjaminized weak / Acol weak twos.
    Used by bb12's "ACOL" preset.
    """
    s = _fallback_sayc()
    s.name = "StandardAcol"
    s.description = "standard Acol (built-in fallback)"
    s.one_nt_min_hcp = 12
    s.one_nt_max_hcp = 14
    s.one_major_card_min = 4
    s.two_over_one_min_hcp = 9
    return s


def _fallback_standard_french() -> BiddingSystem:
    """Modern French / SEF.

    Q-Plus's `F-FRA-M.RCE`. Mostly SAYC-shaped: 5-card majors, strong
    1NT 15-17, weak 2-bids, 2/1 = 10+ HCP. Differences are mostly in
    response handling (some French-specific cuebid agreements not in
    SAYC). Used by wBridge5's "SEF" and bb12's "La Majeure 5eme".
    """
    s = _fallback_sayc()
    s.name = "StandardFrench"
    s.description = "modern Standard French (built-in fallback)"
    return s


# Short canonical convention list for the fallback systems. The real
# load picks up everything in the .RCE file; these are the headline set
# we know native_bidder already implements or will soon.
_FALLBACK_SAYC_CONVENTIONS = {
    "A-1NT-Stayman", "A-1NT-Jacoby-transfer.always",
    "A-1NT-transfer-level-4.Texas",
    "A-1MA-splinter", "A-1MA-Truscott-2NT", "A-1MA-Jacoby-2NT",
    "A-artificial-2C.negative-2D",
    "C-Sputnik.until-2S",
    "G-new-minor-forcing", "G-fourth-suit-forcing",
    "O-Michaels", "O-Unusual-Notrump", "O-1NT.Landy",
    "O-Weak-Jump-Overcall.all-suits",
    "S-Blackwood.keycard.RKCB1430", "S-Gerber.classic",
    "B-2NT.strong-balanced.range-20-21",
    "B-2MA.weak", "B-2D.weak",
}


_FALLBACK_PRECISION_CONVENTIONS = (_FALLBACK_SAYC_CONVENTIONS | {
    "B-strong-artificial.bid-1C.min-hcp-16",
    "A-artificial-1C.switch-1NT-1H",
    "B-2D.Precision.majors-4-3",
    "O-strong-1C.dbl-is-majors",
}) - {"A-artificial-2C.negative-2D", "B-2D.weak"}


_CATALOG: List[Tuple[str, str, "callable"]] = [
    ("SAYC",            "A-SAYC-I.RCE", _fallback_sayc),
    ("TwoOverOne",      "A-2-1-A.RCE",  _fallback_two_over_one),
    ("StandardAcol",    "B-ACL-S.RCE",  _fallback_acol),
    ("StandardFrench",  "F-FRA-M.RCE",  _fallback_standard_french),
    ("Precision90M",    "P-P90M-A.RCE", _fallback_precision90m),
]


# Aliases so the config can keep using "Precision" or "SAYC" generically.
_ALIASES = {
    "Precision": "Precision90M",
    "Precision Club": "Precision90M",
    "Precision Club 90 modern": "Precision90M",
    "Standard American": "SAYC",
    "Std. Amer.": "SAYC",
    "2/1": "TwoOverOne",
    "SEF": "StandardFrench",
    "ACOL": "StandardAcol",
    "Acol": "StandardAcol",
    "La Majeure 5eme": "StandardFrench",
    "La Majeure Cinquieme": "StandardFrench",
}


_SYSTEM_CACHE: Dict[str, BiddingSystem] = {}


def list_systems() -> List[str]:
    """Canonical names available to the rule-based bidder."""
    return [name for name, _, _ in _CATALOG]


def get_system(name: str) -> BiddingSystem:
    """Look up a bidding system by canonical name or alias.

    Reads the matching `.RCE` file if available and caches the result.
    Falls back to a hand-coded approximation when the file is missing
    so the bidder always returns *something* defensible.
    """
    canonical = _ALIASES.get(name, name)
    if canonical in _SYSTEM_CACHE:
        return _SYSTEM_CACHE[canonical]

    for cname, fname, fallback in _CATALOG:
        if cname == canonical:
            rce_path = _find_rce(fname)
            if rce_path is not None:
                sys_ = _build_from_rce(cname, rce_path)
            else:
                sys_ = fallback()
            _SYSTEM_CACHE[cname] = sys_
            return sys_

    # Unknown — fall back to SAYC so callers always get a usable spec.
    return get_system("SAYC")
