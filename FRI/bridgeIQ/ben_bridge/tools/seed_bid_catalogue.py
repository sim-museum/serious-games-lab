"""Seed CONFIG/BIDRULE/<system>.json for the seven Q-Plus systems.

Produces per-system bid-meaning catalogues that the BidMeaningEditor
can load and the rest of the dialog code can consume. The content is
intentionally conservative — the core openings + the conventions each
system is famous for, with explicit HP / suit-length / dependency
ranges. Edit a bid via Configuration → Bidding Systems → Edit
Meaning... to override.

Run from the project root::

    python3 tools/seed_bid_catalogue.py

The script is idempotent: re-running it OVERWRITES the JSON files,
so any per-bid edits the user has made through the editor are lost.
The editor preserves the file format, so a future regeneration could
merge instead of overwrite, but for the initial seed we want a clean
slate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Default suit constraints — used for bids that don't constrain a suit.
_SUIT_FREE = {"min": 0, "max": 13, "control": "--", "stopper": "--"}


def _suit(min_=0, max_=13, control="--", stopper="--"):
    return {"min": min_, "max": max_,
            "control": control, "stopper": stopper}


def _form(bid, *, name="", artificial=False, forcing=False,
          hp=None, lp=None, tp=None, tp_trump="NT",
          spades=None, hearts=None, diamonds=None, clubs=None,
          deps="", aces="", kings=""):
    return {
        "bid": bid,
        "name": name,
        "is_artificial": bool(artificial),
        "is_forcing": bool(forcing),
        "hp_min": hp[0] if hp else None,
        "hp_max": hp[1] if hp else None,
        "lp_min": lp[0] if lp else None,
        "lp_max": lp[1] if lp else None,
        "tp_min": tp[0] if tp else None,
        "tp_max": tp[1] if tp else None,
        "tp_trump": tp_trump,
        "aces_expr": aces,
        "kings_expr": kings,
        "suit_S": spades or dict(_SUIT_FREE),
        "suit_H": hearts or dict(_SUIT_FREE),
        "suit_D": diamonds or dict(_SUIT_FREE),
        "suit_C": clubs or dict(_SUIT_FREE),
        "dependencies": deps,
    }


def _sayc_like(one_nt_lo, one_nt_hi, *, major_5=True, weak_two=True):
    """Build a SAYC / 2-over-1 / Acol-style opening table.

    The three systems share most opening shape constraints; what
    differs is the 1NT range, the 4-vs-5 card major rule, and which
    minor is opened on equal length. Dependencies use the .bid-eval-in
    DSL — one comparison-chain per line.
    """
    maj_min = 5 if major_5 else 4
    cat = {}
    cat["1C"] = _form(
        "1C", name="natural minor",
        hp=(12, 21),
        clubs=_suit(3, 13),
        spades=_suit(0, maj_min - 1),
        hearts=_suit(0, maj_min - 1),
        deps=(f"HP >= 12 & C >= 3 & S < {maj_min} & H < {maj_min}"))
    cat["1D"] = _form(
        "1D", name="natural minor",
        hp=(12, 21),
        diamonds=_suit(3, 13),
        spades=_suit(0, maj_min - 1),
        hearts=_suit(0, maj_min - 1),
        deps=(f"HP >= 12 & D >= 3 & S < {maj_min} & H < {maj_min}"))
    cat["1H"] = _form(
        "1H", name="natural major",
        hp=(12, 21),
        hearts=_suit(maj_min, 13),
        deps=f"HP >= 12 & H >= {maj_min}")
    cat["1S"] = _form(
        "1S", name="natural major",
        hp=(12, 21),
        spades=_suit(maj_min, 13),
        deps=f"HP >= 12 & S >= {maj_min}")
    cat["1NT"] = _form(
        "1NT", name="balanced opening",
        hp=(one_nt_lo, one_nt_hi),
        spades=_suit(2, 5), hearts=_suit(2, 5),
        diamonds=_suit(2, 5), clubs=_suit(2, 5),
        deps=(f"HP >= {one_nt_lo} & HP <= {one_nt_hi}\n"
              "S >= 2 & H >= 2 & D >= 2 & C >= 2"))
    cat["2NT"] = _form(
        "2NT", name="balanced 20-21",
        hp=(20, 21),
        spades=_suit(2, 5), hearts=_suit(2, 5),
        diamonds=_suit(2, 5), clubs=_suit(2, 5),
        deps="HP >= 20 & HP <= 21\nS >= 2 & H >= 2 & D >= 2 & C >= 2")
    if weak_two:
        cat["2H"] = _form(
            "2H", name="weak two",
            hp=(5, 11),
            hearts=_suit(6, 6),
            deps="H == 6 & HP < 12")
        cat["2S"] = _form(
            "2S", name="weak two",
            hp=(5, 11),
            spades=_suit(6, 6),
            deps="S == 6 & HP < 12")
        cat["2D"] = _form(
            "2D", name="weak two",
            hp=(5, 11),
            diamonds=_suit(6, 6),
            deps="D == 6 & HP < 12")
    return cat


def _strong_2c_response_pair():
    cat = {}
    cat["2C"] = _form(
        "2C", name="Strong 2C", artificial=True, forcing=True,
        hp=(22, 40),
        deps="HP >= 22")
    cat["2D over 2C"] = _form(
        "2D", name="2C waiting / negative", artificial=True,
        hp=(0, 7),
        deps="HP < 8")
    return cat


def _nt_conventions():
    return {
        "2C over 1NT": _form(
            "2C", name="Stayman", artificial=True, forcing=True,
            hp=(8, 40),
            # Either major as 4+ — split into two dependency lines
            # so each is its own AND-clause; the dependency block as
            # a whole is the disjunction across lines.
            deps="HP >= 8 & S >= 4\nHP >= 8 & H >= 4"),
        "2D over 1NT": _form(
            "2D", name="Jacoby Transfer to H", artificial=True,
            hearts=_suit(5, 13),
            deps="H >= 5"),
        "2H over 1NT": _form(
            "2H", name="Jacoby Transfer to S", artificial=True,
            spades=_suit(5, 13),
            deps="S >= 5"),
        "4C over 1NT": _form(
            "4C", name="Gerber (ace-ask)", artificial=True, forcing=True,
            hp=(13, 40),
            deps="HP >= 13"),
        "4NT over 4-level": _form(
            "4NT", name="Blackwood / RKCB (ace-ask)",
            artificial=True, forcing=True,
            hp=(15, 40),
            deps="HP >= 15"),
    }


def _precision_openings(one_c_strong=(16, 40), one_nt_lo=13, one_nt_hi=15):
    cat = {}
    cat["1C"] = _form(
        "1C", name="Strong artificial Club",
        artificial=True, forcing=True,
        hp=one_c_strong,
        deps=f"HP >= {one_c_strong[0]}")
    cat["1D"] = _form(
        "1D", name="2+ diamonds (or natural)",
        hp=(11, 15),
        diamonds=_suit(2, 13),
        deps="HP >= 11 & HP <= 15 & D >= 2")
    cat["1H"] = _form(
        "1H", name="natural major",
        hp=(11, 15),
        hearts=_suit(5, 13),
        deps="HP >= 11 & HP <= 15 & H >= 5")
    cat["1S"] = _form(
        "1S", name="natural major",
        hp=(11, 15),
        spades=_suit(5, 13),
        deps="HP >= 11 & HP <= 15 & S >= 5")
    cat["1NT"] = _form(
        "1NT", name=f"balanced {one_nt_lo}-{one_nt_hi}",
        hp=(one_nt_lo, one_nt_hi),
        deps=(f"HP >= {one_nt_lo} & HP <= {one_nt_hi}\n"
              "S >= 2 & H >= 2 & D >= 2 & C >= 2"))
    cat["2C"] = _form(
        "2C", name="natural — 11-15, 6+ clubs",
        hp=(11, 15),
        clubs=_suit(6, 13),
        deps="HP >= 11 & HP <= 15 & C >= 6")
    cat["2D"] = _form(
        "2D", name="3-suiter short D",
        artificial=True, hp=(11, 15),
        diamonds=_suit(0, 1),
        deps="HP >= 11 & HP <= 15 & D <= 1")
    cat["1D response 1NT"] = _form(
        "1NT", name="response 8-10 HP, no major",
        hp=(8, 10),
        spades=_suit(0, 3), hearts=_suit(0, 3),
        deps="HP >= 8 & HP <= 10 & S < 4 & H < 4")
    return cat


def _french_openings():
    """Standard French — La Majeure Cinquième. 5-card majors, 4-card
    minor on equal length, 15-17 strong NT, weak twos.

    Standard French also opens 1S on 5=5 hearts/spades; we
    duplicate-add that as a second dependency line on 1S.
    """
    cat = _sayc_like(15, 17, major_5=True, weak_two=True)
    cat["1S"]["dependencies"] += "\nHP >= 12 & S == 5 & H == 5"
    return cat


def _acol_openings():
    """Standard Acol — 4-card majors, weak NT 12-14, strong twos
    forcing one round."""
    cat = _sayc_like(12, 14, major_5=False, weak_two=False)
    cat["2C"] = _form(
        "2C", name="Acol strong 2 — clubs",
        forcing=True,
        hp=(16, 22),
        clubs=_suit(5, 13),
        deps="HP >= 16 & C >= 5")
    cat["2H"] = _form(
        "2H", name="Acol strong 2 — hearts",
        forcing=True,
        hp=(16, 22),
        hearts=_suit(5, 13),
        deps="HP >= 16 & H >= 5")
    cat["2S"] = _form(
        "2S", name="Acol strong 2 — spades",
        forcing=True,
        hp=(16, 22),
        spades=_suit(5, 13),
        deps="HP >= 16 & S >= 5")
    cat["2NT"] = _form(
        "2NT", name="balanced 20-22",
        hp=(20, 22),
        spades=_suit(2, 5), hearts=_suit(2, 5),
        diamonds=_suit(2, 5), clubs=_suit(2, 5),
        deps="HP >= 20 & HP <= 22\nS >= 2 & H >= 2 & D >= 2 & C >= 2")
    return cat


def _preempts():
    return {
        "3C": _form("3C", name="preempt", hp=(6, 10),
                    clubs=_suit(7, 7),
                    deps="C == 7 & HP < 11"),
        "3D": _form("3D", name="preempt", hp=(6, 10),
                    diamonds=_suit(7, 7),
                    deps="D == 7 & HP < 11"),
        "3H": _form("3H", name="preempt", hp=(6, 10),
                    hearts=_suit(7, 7),
                    deps="H == 7 & HP < 11"),
        "3S": _form("3S", name="preempt", hp=(6, 10),
                    spades=_suit(7, 7),
                    deps="S == 7 & HP < 11"),
    }


def _doubles_and_responses():
    """Common double / suit-response / NT-response meanings shared
    across the SAYC / 2/1 / Acol / French families."""
    return {
        "X": _form(
            "X", name="takeout double",
            hp=(12, 40),
            deps="HP >= 12"),
        "XX": _form(
            "XX", name="redouble (strength)",
            hp=(10, 40),
            deps="HP >= 10"),
        "1H over 1C": _form(
            "1H", name="natural response",
            hp=(6, 18),
            hearts=_suit(4, 13),
            deps="HP >= 6 & H >= 4"),
        "1S over 1C": _form(
            "1S", name="natural response",
            hp=(6, 18),
            spades=_suit(4, 13),
            deps="HP >= 6 & S >= 4"),
        "1NT over 1S": _form(
            "1NT", name="non-forcing 6-9",
            hp=(6, 9),
            deps="HP >= 6 & HP <= 9"),
    }


def build_catalogues():
    """Build the per-system dict. Mutating in place lets each system
    layer on its conventions without re-typing the openings."""
    # SAYC: 15-17 NT, 5-card majors.
    sayc = _sayc_like(15, 17)
    sayc.update(_strong_2c_response_pair())
    sayc.update(_nt_conventions())
    sayc.update(_preempts())
    sayc.update(_doubles_and_responses())

    # 2/1 Game Force — same shape as SAYC, with 1NT forcing response
    # and Bergen raises layered on.
    two_over_one = _sayc_like(15, 17)
    two_over_one.update(_strong_2c_response_pair())
    two_over_one.update(_nt_conventions())
    two_over_one.update(_preempts())
    two_over_one.update(_doubles_and_responses())
    two_over_one["1NT over 1S"] = _form(
        "1NT", name="forcing (1NT-F)", forcing=True,
        hp=(6, 12),
        deps="HP >= 6 & HP <= 12")
    two_over_one["2H over 1S"] = _form(
        "2H", name="2/1 game forcing", forcing=True,
        hp=(12, 40),
        hearts=_suit(5, 13),
        deps="HP >= 12 & H >= 5")
    two_over_one["3C over 1H"] = _form(
        "3C", name="Bergen raise — 4 hearts 7-9",
        artificial=True,
        hp=(7, 9),
        hearts=_suit(4, 13),
        deps="HP >= 7 & HP <= 9 & H >= 4")
    two_over_one["3D over 1H"] = _form(
        "3D", name="Bergen raise — 4 hearts 10-12",
        artificial=True,
        hp=(10, 12),
        hearts=_suit(4, 13),
        deps="HP >= 10 & HP <= 12 & H >= 4")

    # Standard Acol — 4-card majors, weak NT 12-14, strong twos.
    acol = _acol_openings()
    acol.update(_strong_2c_response_pair())
    # Override 2C, 2H, 2S that _strong_2c_response set, since Acol
    # uses its own strong-two structure (already in _acol_openings).
    acol["2C"] = _acol_openings()["2C"]
    acol.update(_nt_conventions())
    acol.update(_preempts())
    acol.update(_doubles_and_responses())

    # Standard French — 5-card majors, 15-17 NT, Walsh-style minors.
    french = _french_openings()
    french.update(_strong_2c_response_pair())
    french.update(_nt_conventions())
    french.update(_preempts())
    french.update(_doubles_and_responses())

    # Precision 90 modern / plus / 70 — strong artificial 1C base,
    # 13-15 NT (modern) or 14-16 (plus) or 12-14 (70).
    p90m = _precision_openings(one_nt_lo=13, one_nt_hi=15)
    p90m.update(_nt_conventions())
    p90m.update(_preempts())
    p90m.update(_doubles_and_responses())

    p90p = _precision_openings(one_nt_lo=14, one_nt_hi=16)
    p90p.update(_nt_conventions())
    p90p.update(_preempts())
    p90p.update(_doubles_and_responses())

    p70 = _precision_openings(one_nt_lo=12, one_nt_hi=14)
    p70.update(_nt_conventions())
    p70.update(_preempts())
    p70.update(_doubles_and_responses())

    return {
        "SAYC": sayc,
        "TwoOverOne": two_over_one,
        "StandardAcol": acol,
        "StandardFrench": french,
        "Precision90M": p90m,
        "Precision90P": p90p,
        "Precision70": p70,
    }


def main():
    root = Path(__file__).resolve().parent.parent
    target_dir = root / "CONFIG" / "BIDRULE"
    target_dir.mkdir(parents=True, exist_ok=True)

    catalogues = build_catalogues()
    for system_key, cat in catalogues.items():
        path = target_dir / f"{system_key}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cat, f, indent=2, ensure_ascii=False)
        print(f"wrote {path.relative_to(root)}  "
              f"({len(cat)} bids)")
    print("done.")


if __name__ == "__main__":
    sys.exit(main() or 0)
