#!/usr/bin/env python3
"""Validate that a Q-Plus run matched the LOCKED RIG before you trust its IMPs.

We kept invalidating runs three ways (the "oopses"):
  1. Deal-number sourcing  -> seats ROTATE between A/B (different cards).
  2. Closed Room not picked -> no teams baseline (RE col2/IM all 0); raw
     single-table scores are dominated by card luck, uninterpretable.
  3. Random/sequential systems per deal -> can't attribute the result to one
     system, and the two biq clients can desync.

This checks a run's .qss (and, if present, the biq client logs) against the
locked rig and prints PASS / WARN / FAIL per requirement + an overall verdict.
Run the 12-deal Phase-0 probe, point this at the .qss, and only scale to 64+
once it says VALID.

Usage:
  python3 tools/run_preflight.py                       # newest .qss + auto logs
  python3 tools/run_preflight.py --qss PATH.qss
  python3 tools/run_preflight.py --expect-system Precision90M --min-deals 12
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BIQ_ROOT = _HERE.parent
_FRI_ROOT = _BIQ_ROOT.parent.parent
_QSS_DIR = _FRI_ROOT / "WP/drive_c/games/qbridge17/DATA/LOCAL-MATCHES"
_RUNS = _HERE / "runs"

# Q-Plus bidding-system codes -> biq names (mirror of biq_qnet_server._code).
_CODE = {"A-SAYC-I": "SAYC", "A-2-1-A": "TwoOverOne", "B-ACL-S": "StandardAcol",
         "F-FRA-M": "StandardFrench", "P-P90M-A": "Precision90M"}

# Colour only on a real terminal — when piped (e.g. the panel's QProcess) the
# escape codes would render as garbage, so fall back to plain text.
if sys.stdout.isatty():
    GREEN, YELLOW, RED, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[0m"
else:
    GREEN = YELLOW = RED = RESET = ""


class Check:
    def __init__(self):
        self.rows = []      # (status, label, detail)
        self.fail = False
        self.warn = False

    def add(self, status, label, detail=""):
        self.rows.append((status, label, detail))
        if status == "FAIL":
            self.fail = True
        elif status == "WARN":
            self.warn = True

    def render(self):
        sym = {"PASS": f"{GREEN}PASS{RESET}", "WARN": f"{YELLOW}WARN{RESET}",
               "FAIL": f"{RED}FAIL{RESET}"}
        for status, label, detail in self.rows:
            line = f"  [{sym[status]}] {label}"
            if detail:
                line += f"\n          {detail}"
            print(line)


def _newest_qss():
    cands = sorted(_QSS_DIR.glob("*.qss"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def _parse_qss(path):
    di, re_pairs, im_pairs = [], [], []
    sys_ns = sys_ew = None
    sm = None
    for raw in path.read_text(errors="replace").splitlines():
        t = raw.split()
        if not t:
            continue
        if t[0] == "DI":
            m = re.search(r'"([^"]*)"', raw)
            di.append(m.group(1) if m else "")
        elif t[0] == "RE" and len(t) >= 3:
            try:
                re_pairs.append((int(t[1]), int(t[2])))
            except ValueError:
                pass
        elif t[0] == "IM" and len(t) >= 3:
            try:
                im_pairs.append((int(t[1]), int(t[2])))
            except ValueError:
                pass
        elif t[0] == "SM":
            sm = t[1] if len(t) > 1 else None
        elif t[0] == "CG":
            mns = re.search(r'conv\.bidding\.N/S\s*=\s*([A-Za-z0-9\-]+)', raw)
            mew = re.search(r'conv\.bidding\.E/W\s*=\s*([A-Za-z0-9\-]+)', raw)
            if mns:
                sys_ns = mns.group(1)
            if mew:
                sys_ew = mew.group(1)
    return dict(di=di, re=re_pairs, im=im_pairs, sm=sm,
                sys_ns=sys_ns, sys_ew=sys_ew)


def _scan_biq_logs(paths):
    """Return (systems_on_scored_deals, mismatch_count, own_deals_seen).

    We judge the system ONLY on OWN-DEALS (scored) deals: Q-Plus often deals a
    stray Deal-number throwaway on a stale config before the BDE deck is active,
    and that pre-match deal must not flag the run. So track the system in effect
    (launch system from the session header, updated by each auto/random-system
    switch) and record it whenever a deck deal is dealt."""
    deck_systems, mism, own = set(), 0, False
    for p in paths:
        cur = None
        for line in p.read_text(errors="replace").splitlines():
            mh = re.search(r'\bsystem=([A-Za-z0-9]+)', line)
            if mh and "session" in line:                 # launch system
                cur = mh.group(1)
            if "SYSTEM MISMATCH" in line:
                mism += 1
            # "auto-system: N/S=CODE → old → NEW" / "random-system: old -> NEW"
            ms = re.search(r'(?:auto-system|random-system):.*?(?:→|->)\s*'
                           r'([A-Za-z0-9]+)\s*$', line)
            if ms:
                cur = ms.group(1)
            if "OWN-DEALS" in line and "new_deal_pbn" in line:
                own = True
                if cur:
                    deck_systems.add(cur)
    return deck_systems, mism, own


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qss", default=None, help="(default: newest in LOCAL-MATCHES)")
    ap.add_argument("--biq-log", nargs="*", default=None,
                    help="(default: tools/runs/biq_[NESW].log)")
    ap.add_argument("--expect-system", default=None,
                    help="assert N/S plays this biq system name (e.g. Precision90M)")
    ap.add_argument("--min-deals", type=int, default=12)
    ap.add_argument("--expect-bidder", default=None,
                    help="require this exact bidder fingerprint (a55796a83f="
                         "baseline); FAILs a wrong-engine run")
    a = ap.parse_args(argv)

    qss = Path(a.qss) if a.qss else _newest_qss()
    if not qss or not qss.exists():
        print(f"{RED}No .qss found{RESET} (looked in {_QSS_DIR}). "
              f"Pass --qss.", file=sys.stderr)
        return 2
    q = _parse_qss(qss)
    print(f"Run preflight — {qss.name}\n{'=' * 60}")

    c = Check()

    # 1. Teams scoring
    if q["sm"] == "T":
        c.add("PASS", "Teams (IMP) scoring  [SM T]")
    else:
        c.add("FAIL", "Teams (IMP) scoring", f"SM={q['sm']!r}, expected T")

    # 2. Closed room actually played  (oops 2)
    ndeals = len(q["di"])
    closed = sum(1 for _, cl in q["re"] if cl != 0) + \
        sum(1 for x, y in q["im"] if x or y)
    if closed > 0:
        c.add("PASS", "Closed Room played",
              f"{ndeals} deals, nonzero closed/IM on {closed}")
    else:
        c.add("FAIL", "Closed Room played  (OOPS 2)",
              "RE col2 and IM all zero -> no closed room; raw scores are "
              "uninterpretable. Select Closed Room in Match Control.")

    # 3. Fixed BDE deck, not Deal-number sourcing  (oops 1)
    numeric = [d for d in q["di"] if re.match(r'^\d', d)]
    alpha = [d for d in q["di"] if re.match(r'^[A-Za-z]', d)]
    if alpha and not numeric:
        c.add("PASS", "Deck-sourced deals  (no rotation)",
              f"e.g. {alpha[0]!r} -> fixed BDE deck")
    elif numeric:
        c.add("WARN", "Deck source  (OOPS 1 risk)",
              f"DI labels look like Deal-number ({numeric[0]!r}); seats can "
              f"ROTATE between A/B. Use a fixed BDE Own-deals deck.")
    else:
        c.add("WARN", "Deck source", "could not classify DI labels")

    # 4. Deal count
    if ndeals >= a.min_deals:
        c.add("PASS", f"Deal count >= {a.min_deals}", f"{ndeals} deals")
    else:
        c.add("WARN", f"Deal count >= {a.min_deals}",
              f"only {ndeals}; fine for a Phase-0 probe, too few to conclude")

    # 5. Systems (header) + optional expectation
    ns_name = _CODE.get(q["sys_ns"], q["sys_ns"])
    ew_name = _CODE.get(q["sys_ew"], q["sys_ew"])
    c.add("PASS", "Systems (qss header)", f"N/S={ns_name}  E/W={ew_name}")
    if a.expect_system:
        if ns_name == a.expect_system:
            c.add("PASS", f"N/S == {a.expect_system}")
        else:
            c.add("FAIL", f"N/S == {a.expect_system}",
                  f"header says N/S={ns_name}")

    # 6. biq logs: fixed system + pair agreement  (oops 3)
    logs = ([Path(p) for p in a.biq_log] if a.biq_log
            else sorted(_RUNS.glob("biq_[NESW].log")))
    logs = [p for p in logs if p.exists() and p.stat().st_size > 0]
    if logs:
        systems, mism, own = _scan_biq_logs(logs)
        names = ", ".join(sorted(systems)) or "(none logged)"
        if len(systems) <= 1:
            c.add("PASS", "Fixed system across deals  (biq logs)",
                  f"{names}  [{', '.join(p.name for p in logs)}]")
        else:
            c.add("FAIL", "Fixed system across deals  (OOPS 3)",
                  f"biq switched among: {names} -> random/sequential. "
                  f"Set a FIXED N/S & E/W system, turn off cycling.")
        if mism == 0:
            c.add("PASS", "Pair system-agreement guard", "no SYSTEM MISMATCH")
        else:
            c.add("FAIL", "Pair system-agreement guard",
                  f"{mism} SYSTEM MISMATCH line(s) — the two biq seats "
                  f"diverged on some deal(s).")
        if own:
            c.add("PASS", "biq saw OWN-DEALS source", "cross-checks the deck")
        # Bidder fingerprint (caseC marker): caseC>=4 means U1/U2/U3 are
        # present. Three baselines were silently run on a reverted bidder
        # (caseC=0) before this check existed.
        casec, hashes = set(), set()
        for p in logs:
            for line in p.read_text(errors="replace").splitlines():
                m = re.search(r'caseC=(\d+)', line)
                if m:
                    casec.add(int(m.group(1)))
                mh = re.search(r'bidder=([0-9a-f]{6,})', line)
                if mh:
                    hashes.add(mh.group(1))
        if not casec:
            c.add("WARN", "Bidder fingerprint",
                  "no bidder= stamp in biq logs (pre-fingerprint run; can't "
                  "verify the engine version)")
        elif min(casec) >= 4:
            c.add("PASS", "Bidder fingerprint (U1/U2/U3 present)",
                  f"caseC={sorted(casec)} hash={sorted(hashes)}")
        else:
            c.add("FAIL", "Bidder fingerprint  (REVERTED ENGINE)",
                  f"caseC={sorted(casec)} (<4) — this run used a bidder MISSING "
                  f"U1/U2/U3; the result is on the wrong engine, discard it.")
        # Exact-engine check: a run must use the engine it was MEANT to (the
        # baseline-vs-candidate race that put the 2-fix candidate into a
        # 'baseline' run). caseC>=4 alone can't tell them apart.
        if a.expect_bidder:
            if hashes == {a.expect_bidder}:
                c.add("PASS", f"Engine == {a.expect_bidder}")
            else:
                c.add("FAIL", f"Engine == {a.expect_bidder}",
                      f"run used {sorted(hashes)} — WRONG engine (e.g. a "
                      f"candidate run mislabelled as baseline). Discard.")
    else:
        c.add("WARN", "biq client logs",
              f"none found in {_RUNS} — system-fixed/pair-agreement checks "
              f"skipped (the qss alone can't see per-deal system cycling).")

    print()
    c.render()
    print(f"{'=' * 60}")
    if c.fail:
        verdict = f"{RED}INVALID — do not trust this run's IMPs.{RESET}"
    elif c.warn:
        verdict = f"{YELLOW}VALID with warnings — review the WARN rows.{RESET}"
    else:
        verdict = f"{GREEN}VALID — matches the locked rig.{RESET}"
    print(f"VERDICT: {verdict}\n")
    print("Locked rig: fixed BDE deck · Closed Room ON · FIXED system "
          "(not random) · biq pair + agreement guard · teams IMP.")
    return 1 if c.fail else 0


if __name__ == "__main__":
    sys.exit(main())
