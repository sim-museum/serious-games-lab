"""Compare biq's Deal-4 play at samples=5, 20, 80."""
import sys, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.mixed_corpus_diff import (
    _board_from_bdl_hands, _parse_bdl_bids_per_deal,
    _parse_qplus_results, _determine_contract, _trick_winner,
    parse_bdl_with_systems, biq_play_contract)
from backend.engine import BridgeEngine
from backend.models import Seat

QSS = ROOT / "data/qplus_corpora_archive/merged_15915_98879.qss"
MANI = ROOT / "data/qplus_corpora_archive/20260529_150758_s15915_98879.manifest.json"
TARGET = 4

manifest = json.loads(MANI.read_text())
ns_sys = next(d["ns_system"] for d in manifest["deals"]
              if d["deal"] == TARGET)
bdl_deals = parse_bdl_with_systems(QSS)
bd = next(b for b in bdl_deals
          if int(re.search(r"(\d+)\s*$", b["label"]).group(1)) == TARGET)
board = _board_from_bdl_hands(TARGET, bd)
bids = _parse_bdl_bids_per_deal(QSS)
qp_auction = bids[bd["label"]]
contract = _determine_contract(board, qp_auction)

engine = BridgeEngine()
assert engine.initialize()
engine.set_bidding_system(ns_sys)

import time
for samples in (5, 20, 80):
    t0 = time.time()
    tricks = biq_play_contract(engine, board, contract, qp_auction,
                                num_samples=samples)
    print(f"samples={samples:>3}  biq_tricks={tricks}  "
          f"elapsed={time.time()-t0:.1f}s")

print(f"\nQ-Plus took 12 / 13.")
