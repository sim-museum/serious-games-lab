#!/usr/bin/env python3
"""Put new biq code into a running continuous match without re-seating anyone.

1. Snapshot the code (backend/, tools/*.py, the regression test scripts) into
   tools/runs/code/<stamp>_<fingerprint>/. Snapshots are never edited, so
   every results record's "code" fingerprint names exactly what played.
2. Gates (skip with --no-gates): the snapshot imports; the bidding test
   scripts fail no check that the code now live passes (live = control.json
   "code", else the repo).
3. control.json in the run folder gets {"reexec": <stamp>, "code": <snapshot>}
   (other keys kept): the TM swaps to it at the next board boundary
   (biq_bluechip_tm.py --continuous). --verify names planner families that
   the change touches; plan.json "verify" then gives them extra boards until
   the new code has played enough of them.

  python3 tools/biq_deploy.py --run tools/runs/bluechip/<run> [--src DIR]
         [--verify ml_adv,wk2_resp] [--note "..."] [--no-gates]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
TESTS = ["test_bidding_systems.py", "test_qplus_match_fixes.py"]


def fingerprint(root: Path) -> str:
    sys.path.insert(0, str(root / "tools"))
    from biq_bluechip_tm import code_fingerprint
    return code_fingerprint(root)


def snapshot(src: Path, dest_root: Path) -> Path:
    fp = fingerprint(src)
    dest = dest_root / f"{time.strftime('%y%m%d_%H%M%S')}_{fp}"
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(src / "backend", dest / "backend", ignore=ign)
    (dest / "tools").mkdir(parents=True)
    for f in (src / "tools").glob("*.py"):
        shutil.copy2(f, dest / "tools" / f.name)
    for t in TESTS + ["__init__.py"]:
        if (src / t).is_file():
            shutil.copy2(src / t, dest / t)
    return dest


def failures(root: Path) -> set:
    """Names of failing checks of the regression scripts run in `root`."""
    env = dict(os.environ, WINEPREFIX=os.environ.get("WINEPREFIX", str(Path.home() / "sgl/FRI/WP")))
    bad = set()
    for t in TESTS:
        if not (root / t).is_file():
            continue
        p = subprocess.run([sys.executable, t], cwd=root, env=env, capture_output=True,
                           text=True, timeout=1800)
        for line in (p.stdout + p.stderr).splitlines():
            if re.match(r"^(FAIL|ERROR):", line) or re.match(r"^\[BAD\]", line.strip()):
                bad.add(f"{t}: {line.strip()[:160]}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="the continuous match's output folder")
    ap.add_argument("--src", default=str(_HERE.parent), help="code root to deploy (default: this repo)")
    ap.add_argument("--verify", default="", help="planner families the change touches")
    ap.add_argument("--note", default="")
    ap.add_argument("--no-gates", action="store_true")
    a = ap.parse_args(argv)
    run, src = Path(a.run).resolve(), Path(a.src).resolve()
    code_root = _HERE / "runs" / "code"
    code_root.mkdir(parents=True, exist_ok=True)
    ctl_path = run / "control.json"
    try:
        ctl = json.loads(ctl_path.read_text())
    except (OSError, ValueError):
        ctl = {}
    live = Path(ctl.get("code") or _HERE.parent)

    snap = snapshot(src, code_root)
    print(f"snapshot {snap}")
    if not a.no_gates:
        env = dict(os.environ, WINEPREFIX=os.environ.get("WINEPREFIX", str(Path.home() / "sgl/FRI/WP")))
        p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, '.'); "
                            "import backend.native_bidder, backend.bid_sim, backend.nopeek; "
                            "sys.path.insert(0, 'tools'); import biq_bluechip_tm"],
                           cwd=snap, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            print("GATE FAILED: snapshot does not import\n" + p.stderr[-2000:])
            return 2
        new_bad, old_bad = failures(snap), failures(live)
        regress = sorted(new_bad - old_bad)
        if regress:
            print("GATE FAILED: new test failures:\n  " + "\n  ".join(regress))
            return 3
        print(f"gates passed ({len(new_bad)} known failures, none new)")
    ctl.update(reexec=snap.name, code=str(snap))
    ctl_path.write_text(json.dumps(ctl, indent=1) + "\n")
    if a.verify:
        pp = run / "plan.json"
        try:
            plan = json.loads(pp.read_text())
        except (OSError, ValueError):
            plan = {}
        plan["verify"] = sorted(set(plan.get("verify", [])) | set(a.verify.split(",")))
        pp.write_text(json.dumps(plan, indent=1) + "\n")
    with open(run / "deploys.jsonl", "a") as fh:
        fh.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "snapshot": snap.name,
                             "fingerprint": snap.name.split("_")[-1], "note": a.note,
                             "verify": a.verify}) + "\n")
    print(f"control.json: swap to {snap.name} at the next board")
    return 0


if __name__ == "__main__":
    sys.exit(main())
