#!/usr/bin/env python3
"""BUILD_MANIFEST.json must match the tree before a commit (the startup build
check refuses to run a mismatched build), and the build check must pass.

    python3 test_build_integrity.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import build_check as bc  # noqa: E402


def test_manifest_matches_tree():
    import json
    files = json.loads(bc.MANIFEST.read_text())["files"]
    tree = {str(p.relative_to(bc.APP_DIR)) for p in bc.manifest_files()}
    assert set(files) == tree, (
        f"manifest stale (run tools/write_build_manifest.py): "
        f"new {sorted(tree - set(files))[:5]}, gone {sorted(set(files) - tree)[:5]}")
    stale = [r for r, d in files.items() if bc.sha256(bc.APP_DIR / r) != d]
    assert not stale, (f"manifest stale (run tools/write_build_manifest.py): "
                       f"{stale[:5]}")


def test_build_check_passes():
    problems, notes = bc.run_all()
    assert not problems, problems


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("ALL TESTS PASSED")
