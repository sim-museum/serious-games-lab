#!/usr/bin/env python3
"""Quick DD PRE-SCREEN of a bidding change — NOT the verdict.

⚠ This is a fast, cheap sanity check, not a measurement to trust. It has
the two flaws that gave us false confidence before:
  • cardplay is DOUBLE-DUMMY (both sides play perfectly) — it does NOT use
    biq's real MC+DDS cardplay, so declaring/defending skill is invisible;
  • there is NO live Q-Plus — biq bids all four seats in a vacuum, so a
    real opponent's bidding/competition/adaptation never happens.
A change can look great here and mean nothing at the table.

For the REAL measurement use tools/live_ab_compare.py: two actual 64-deal
runs vs Q-Plus on the SAME boards, diffed by per-deal teams IMP. Use THIS
tool only to cheaply flag obviously-bad changes before spending two live
runs on them.

What it does: run the IDENTICAL deals through two versions of the bidder,
score each final contract double-dummy (NS-signed), and compare by IMP —
isolating the bidding delta with zero deal-set variance.

Two phases:

  1. EMIT — for the current checkout, bid a fixed deal set (reproducible
     from --seed/--count) with the chosen NS / EW systems, score each
     contract by DD (NS-signed), and dump per-deal JSON.

  2. COMPARE — given two emit files A (baseline) and B (candidate), for
     each deal compute IMP = imp_lookup(score_B - score_A) from biq's
     (NS) perspective. Positive total = the candidate bids better.
     Because it's the same deal both times, card luck cancels exactly.

Convenience: `--baseline <git-ref>` does the whole A/B in one shot —
it spins a detached git worktree at <ref>, runs EMIT there (so the
baseline bidder is used), runs EMIT in the current tree, then COMPAREs.

Usage:
    # one-shot: compare current working tree against a committed baseline
    python3 tools/same_deals_ab.py --baseline HEAD~1 \
        --seed 2444 --count 64 --ns-system Precision90M --ew-system SAYC

    # manual two-step (e.g. across machines / dirty trees):
    python3 tools/same_deals_ab.py --emit /tmp/A.json --seed 2444 --count 64 ...
    #   (check out the other version, re-run --emit /tmp/B.json ...)
    python3 tools/same_deals_ab.py --compare /tmp/A.json /tmp/B.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.dds import DDSolver                              # noqa: E402
from backend.models import (                                 # noqa: E402
    BoardState, Contract, Hand, Seat, Vulnerability,
)
from tools.qplus_mixed_corpus import gen_random_deals        # noqa: E402
from tools.mixed_corpus_diff import drive_bridgeIQ_mixed     # noqa: E402
from tools.score_diff import (                               # noqa: E402
    _determine_contract, _dd_tricks, _ns_score, _imp_lookup,
)
from tools.qnet_log_score import _parse_deals                # noqa: E402

_STRAIN_CHAR = {0: "S", 1: "H", 2: "D", 3: "C", 4: "NT"}
_SEAT_CH = {"N": Seat.NORTH, "E": Seat.EAST,
            "S": Seat.SOUTH, "W": Seat.WEST}
_VUL_MAP = {"None": Vulnerability.NONE, "NONE": Vulnerability.NONE,
            "-": Vulnerability.NONE, "Love": Vulnerability.NONE,
            "NS": Vulnerability.NS, "N/S": Vulnerability.NS,
            "EW": Vulnerability.EW, "E/W": Vulnerability.EW,
            "All": Vulnerability.BOTH, "Both": Vulnerability.BOTH,
            "ALL": Vulnerability.BOTH, "BOTH": Vulnerability.BOTH}


def _board_from_pbn(pbn: str, dealer: str, vul: str,
                    board_no: int) -> BoardState:
    """Build a BoardState from a 'N:hands' PBN + dealer/vul tokens."""
    body = pbn.split(":", 1)[1] if ":" in pbn else pbn
    first = pbn.split(":", 1)[0].strip()[-1] if ":" in pbn else "N"
    order = "NESW"
    start = order.index(first)
    hands_pbn = body.split()
    hands = {}
    for k, hp in enumerate(hands_pbn):
        seat = _SEAT_CH[order[(start + k) % 4]]
        hands[seat] = Hand.from_pbn(hp)
    return BoardState(board_number=board_no,
                      dealer=_SEAT_CH.get(dealer[:1].upper(), Seat.NORTH),
                      vulnerability=_VUL_MAP.get(vul, Vulnerability.NONE),
                      hands=hands)


def load_deals(seed: int, count: int,
               from_log: str | None, want_set: str | None):
    """Return a list of (label, BoardState).

    --from-log pulls the ACTUAL hands biq played vs Q-Plus (from the
    client log); otherwise generate a reproducible biq deal set."""
    if from_log:
        parsed = _parse_deals(from_log, want_set)
        out = []
        for label in sorted(parsed, key=lambda L: parsed[L]["board"]):
            d = parsed[label]
            out.append((label, _board_from_pbn(
                d["pbn"], d["dealer"], d["vul"], d["board"])))
        return out
    return [(f"{seed}-{b.board_number:02d}", b)
            for b in gen_random_deals(count, seed)]


def _contract_str(c: Contract | None) -> str:
    if c is None:
        return "PASS"
    suit = _STRAIN_CHAR.get(c.suit.value, "?")
    x = "XX" if c.redoubled else ("X" if c.doubled else "")
    return f"{c.level}{suit}{x} {'NESW'[c.declarer.value]}"


def emit(out_path: str, seed: int, count: int,
         ns_system: str, ew_system: str,
         from_log: str | None = None, want_set: str | None = None) -> int:
    """Bid the fixed deal set with the current bidder; dump per-deal JSON."""
    deals = load_deals(seed, count, from_log, want_set)
    dds = DDSolver()
    rows = []
    for label, board in deals:
        auction = drive_bridgeIQ_mixed(board, ns_system, ew_system)
        contract = _determine_contract(board, auction)
        if contract is None:
            ns = 0
            tricks = None
        else:
            tricks = _dd_tricks(dds, board, contract)
            ns = _ns_score(contract, tricks, board.vulnerability)
        rows.append({
            "label": label,
            "board": board.board_number,
            "contract": _contract_str(contract),
            "declarer": ("NESW"[contract.declarer.value]
                         if contract else None),
            "ns_decl": (contract is not None and contract.declarer.is_ns()),
            "dd_tricks": tricks,
            "ns_score": ns,
        })
    meta = {"seed": seed, "count": count,
            "ns_system": ns_system, "ew_system": ew_system,
            "source": (f"log:{Path(from_log).name}:set{want_set}"
                       if from_log else f"gen:seed{seed}"),
            "git_ref": _git_describe()}
    Path(out_path).write_text(json.dumps({"meta": meta, "deals": rows},
                                         indent=2))
    print(f"emit: {len(rows)} deals -> {out_path} "
          f"(NS={ns_system} EW={ew_system}, {meta['git_ref']})")
    return 0


def _git_describe() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(_HERE), capture_output=True, text=True)
        ref = out.stdout.strip() or "?"
        dirty = subprocess.run(["git", "status", "--porcelain",
                                "backend/native_bidder.py"],
                               cwd=str(_HERE), capture_output=True, text=True)
        return ref + ("+dirty" if dirty.stdout.strip() else "")
    except Exception:
        return "?"


def compare(a_path: str, b_path: str, worst: int = 20) -> int:
    """Compare two emit files; IMP(B - A) per deal, NS perspective."""
    A = json.loads(Path(a_path).read_text())
    B = json.loads(Path(b_path).read_text())
    a_by = {r["label"]: r for r in A["deals"]}
    b_by = {r["label"]: r for r in B["deals"]}
    common = [L for L in a_by if L in b_by]

    am, bm = A["meta"], B["meta"]
    print(f"# same-deals A/B  (seed {am['seed']}, {len(common)} deals, "
          f"NS={am['ns_system']} EW={am['ew_system']})")
    print(f"  A (baseline):  {am.get('git_ref','?')}  [{a_path}]")
    print(f"  B (candidate): {bm.get('git_ref','?')}  [{b_path}]\n")
    if am.get("seed") != bm.get("seed") or am.get("count") != bm.get("count"):
        print("  WARNING: A and B were emitted with different seed/count — "
              "deals may not line up.\n")

    rows = []
    changed = 0
    for L in sorted(common, key=lambda L: a_by[L]["board"]):
        ra, rb = a_by[L], b_by[L]
        imp = _imp_lookup(rb["ns_score"] - ra["ns_score"])
        if ra["contract"] != rb["contract"]:
            changed += 1
        rows.append({"label": L, "a": ra, "b": rb, "imp": imp})

    total = sum(r["imp"] for r in rows)
    n = len(rows)
    nonzero = [r for r in rows if r["imp"] != 0]
    wins = [r for r in rows if r["imp"] > 0]
    losses = [r for r in rows if r["imp"] < 0]
    print(f"  Net IMP (B - A): {total:+d}   ({total/n:+.3f}/deal over {n})")
    print(f"  Contracts changed: {changed}/{n}    "
          f"deals with IMP swing: {len(nonzero)} "
          f"(B better {len(wins)}, A better {len(losses)})\n")

    if nonzero:
        print(f"## Deals that moved (worst {worst} for B first, then best)")
        ordered = sorted(nonzero, key=lambda r: r["imp"])
        show = ordered[:worst] + ([("...",)] if len(ordered) > 2 * worst
                                  else []) + ordered[-worst:] \
            if len(ordered) > 2 * worst else ordered
        for r in show:
            if r == ("...",):
                print("   ...")
                continue
            ra, rb, imp = r["a"], r["b"], r["imp"]
            print(f"   {r['label']:10} {ra['contract']:9} "
                  f"({ra['ns_score']:+5}) -> {rb['contract']:9} "
                  f"({rb['ns_score']:+5})   IMP(B-A)={imp:+3}")
    else:
        print("  (no deal changed score — the two versions bid identically "
              "on this set)")
    return 0


def baseline_oneshot(ref: str, seed: int, count: int,
                     ns_system: str, ew_system: str,
                     from_log: str | None = None, want_set: str | None = None,
                     keep: bool = False) -> int:
    """Isolate the <ref>..HEAD CODE change: temporarily revert exactly the
    files that commit touched to their <ref> version, EMIT (A), restore,
    EMIT (B), COMPARE.

    Critically, this holds EVERYTHING ELSE constant — including the
    working tree's uncommitted config (CONFIG/*.CFG, system defs). A
    full `git worktree` would instead pick up the committed config, so
    the A/B would conflate the code change with config drift. Both emits
    run in fresh subprocesses so the swapped module is re-imported.
    """
    from_log_abs = os.path.abspath(from_log) if from_log else None
    repo_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(_HERE),
        capture_output=True, text=True, check=True).stdout.strip()
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{ref}..HEAD"], cwd=repo_root,
        capture_output=True, text=True, check=True).stdout.split()
    if not changed:
        print(f"No files differ between {ref} and HEAD — nothing to A/B.")
        return 1
    print(f"[A/B] code change under test ({ref}..HEAD): "
          + ", ".join(os.path.basename(f) for f in changed))

    tmp = tempfile.mkdtemp(prefix="biq_ab_")
    a_json = os.path.join(tmp, "A_baseline.json")
    b_json = os.path.join(tmp, "B_current.json")
    src_args = (["--from-log", from_log_abs, "--set", str(want_set)]
                if from_log_abs else [])
    common = ["--seed", str(seed), "--count", str(count),
              "--ns-system", ns_system, "--ew-system", ew_system] + src_args
    self_path = str(_HERE / "same_deals_ab.py")

    def run_emit(out):
        subprocess.run([sys.executable, self_path, "--emit", out] + common,
                       cwd=str(_HERE.parent), check=True)

    backups = {}        # abs path -> original bytes
    try:
        # Back up current bytes, then write each file's <ref> version.
        for rel in changed:
            ap = os.path.join(repo_root, rel)
            backups[ap] = (open(ap, "rb").read()
                           if os.path.exists(ap) else None)
            blob = subprocess.run(["git", "show", f"{ref}:{rel}"],
                                  cwd=repo_root, capture_output=True)
            if blob.returncode != 0:        # file didn't exist at <ref>
                if os.path.exists(ap):
                    os.remove(ap)
            else:
                with open(ap, "wb") as fh:
                    fh.write(blob.stdout)
        print(f"[baseline] emitting A ({ref} version of the changed files) ...")
        run_emit(a_json)
    finally:
        # ALWAYS restore the working tree exactly as it was.
        for ap, data in backups.items():
            if data is None:
                if os.path.exists(ap):
                    os.remove(ap)
            else:
                with open(ap, "wb") as fh:
                    fh.write(data)
    print(f"[candidate] emitting B (current working tree) ...")
    run_emit(b_json)
    print()
    rc = compare(a_json, b_json)
    if keep:
        print(f"\n[kept] {a_json}\n[kept] {b_json}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emit", metavar="OUT.json",
                    help="bid the deal set with the current bidder, dump JSON")
    ap.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"),
                    help="compare two emit files by IMP (B - A), NS-signed")
    ap.add_argument("--baseline", metavar="GIT_REF",
                    help="one-shot A/B: emit at GIT_REF (worktree) vs current")
    ap.add_argument("--seed", type=int, default=2444)
    ap.add_argument("--count", type=int, default=64)
    ap.add_argument("--from-log", default=None,
                    help="bid the ACTUAL hands from a biq client log "
                         "(e.g. tools/runs/biq_N.log) instead of a "
                         "generated set; needs --set")
    ap.add_argument("--set", dest="want_set", default=None,
                    help="deal-set id to pull from --from-log")
    ap.add_argument("--ns-system", default="Precision90M")
    ap.add_argument("--ew-system", default="SAYC")
    ap.add_argument("--worst", type=int, default=20)
    ap.add_argument("--keep", action="store_true",
                    help="(with --baseline) keep the temp A/B JSON files")
    args = ap.parse_args()

    print("⚠ DD pre-screen only (double-dummy cardplay, no live Q-Plus). "
          "For the real number use tools/live_ab_compare.py on two live "
          "runs.\n", file=sys.stderr)

    if args.emit:
        return emit(args.emit, args.seed, args.count,
                    args.ns_system, args.ew_system,
                    args.from_log, args.want_set)
    if args.compare:
        return compare(args.compare[0], args.compare[1], args.worst)
    if args.baseline:
        return baseline_oneshot(args.baseline, args.seed, args.count,
                                args.ns_system, args.ew_system,
                                args.from_log, args.want_set, args.keep)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
