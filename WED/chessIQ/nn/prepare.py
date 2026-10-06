"""V6 chunks (lc0 kramnik-convert) -> one compact .npz for training (EPIC NN, sprint NN-4).
Per position: the 104 board planes (bits), side to move, rule50, a 1858-bit legal-move mask, up to 8 policy entries
(index, probability) and the WDL target -- about 1.1 KB instead of the 8.4 KB V6 record.
python prepare.py <chunk dir> <out.npz> [--holdout-every N]   (every Nth game goes to <out>_holdout.npz)"""
import glob
import gzip
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lc0net as L  # noqa: E402

K = 8


def compact(recs):
    n = len(recs)
    pidx = np.zeros((n, K), np.uint16)
    pval = np.zeros((n, K), np.float16)
    for i, pr in enumerate(recs["probs"]):
        nz = np.nonzero(pr > 0)[0]
        top = nz[np.argsort(-pr[nz])][:K]
        pidx[i, :len(top)] = top
        pval[i, :len(top)] = pr[top] / pr[top].sum()
    legal = np.packbits(recs["probs"] >= 0, axis=1)                      # (n, 233)
    _, wdl = L.targets_from_v6(recs)
    best_q, best_d = recs["rest"][:, 1], recs["rest"][:, 3]
    return dict(planes=np.ascontiguousarray(recs["planes"]), stm=recs["stm"].copy(), rule50=recs["rule50"].copy(),
                legal=legal, pidx=pidx, pval=pval, wdl=wdl.astype(np.float16),
                q=best_q.astype(np.float16), has_q=(best_d >= 0), d=np.clip(best_d, 0, 1).astype(np.float16))


def main():
    src, out = sys.argv[1], sys.argv[2]
    every = int(sys.argv[sys.argv.index("--holdout-every") + 1]) if "--holdout-every" in sys.argv else 0
    files = sorted(glob.glob(os.path.join(src, "**", "*.gz"), recursive=True))
    parts, hold = [], []
    for gi, f in enumerate(files):
        recs = np.frombuffer(gzip.open(f).read(), dtype=L.V6)
        if len(recs):
            (hold if every and gi % every == 0 else parts).append(compact(recs))
    for name, chunk in ((out, parts), (out.replace(".npz", "_holdout.npz"), hold)):
        if chunk:
            np.savez(name, **{k: np.concatenate([c[k] for c in chunk]) for k in chunk[0]})
            print("%s: %d positions from %d games" % (name, sum(len(c["stm"]) for c in chunk), len(chunk)))


if __name__ == "__main__":
    main()
