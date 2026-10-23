"""Write BUILD_MANIFEST.json: the SHA-256 of every file biq's startup build
check verifies (backend/build_check.py). Run it before every commit; the
manifest's version is the commit it was written on top of.

usage: python3 tools/write_build_manifest.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import build_check as bc  # noqa: E402

rc, head = bc._git("rev-parse", "--short", "HEAD")
version = f"{datetime.date.today().isoformat()} (after {head.strip() or '?'})"
files = {str(p.relative_to(bc.APP_DIR)): bc.sha256(p)
         for p in bc.manifest_files()}
bc.MANIFEST.write_text(json.dumps({"version": version, "files": files},
                                  indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
print(f"{bc.MANIFEST}: {len(files)} files, version {version}")
