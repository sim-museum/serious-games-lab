"""Does lc0 compute the same network as PyTorch? (EPIC NN, sprint NN-4)
Loads a PyTorch state dict and its lc0 export; for positions from V6 chunks (encoded by lc0 itself) compares
lc0's per-move policy (VerboseMoveStats, one node, policy temperature 1) and root W-L / D with PyTorch's.
python verify_export.py <state.pt> <net.pb.gz> <blocks> <channels> <games.jsonl> <chunk dir> [games]"""
import gzip
import json
import os
import subprocess
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lc0net as L  # noqa: E402

LC0 = os.environ.get("LC0", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine",
                                         "lc0-kramnik"))


def lc0_eval(proc, moves):
    proc.stdin.write("position startpos" + (" moves " + " ".join(moves) if moves else "") + "\ngo nodes 1\n")
    proc.stdin.flush()
    pol, wl, d = {}, None, None
    for line in proc.stdout:
        if line.startswith("info string "):
            t = line.split()
            if t[2] == "node":
                wl = float(line.split("(WL:")[1].split(")")[0])
                d = float(line.split("(D:")[1].split(")")[0])
            elif "(P:" in line:
                idx = int(line.split("(")[1].split(")")[0])
                pol[idx] = float(line.split("(P:")[1].split("%")[0])
        elif line.startswith("bestmove"):
            return pol, wl, d


def main():
    pt, pb, blocks, channels, games_path, chunk_dir = sys.argv[1:7]
    n_games = int(sys.argv[7]) if len(sys.argv) > 7 else 3
    if pt.endswith(".pb.gz"):               # an lc0 network read by load_lc0 (checks the loader)
        net = L.load_lc0(pt)
    else:
        net = L.LeelaNet(int(blocks), int(channels), policy=os.environ.get("POLICY", "classical")).eval()
        net.load_state_dict(torch.load(pt))
    proc = subprocess.Popen([LC0, "--weights=" + pb, "--backend=blas", "--threads=1", "--policy-softmax-temp=1.0",
                             "--verbose-move-stats"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, bufsize=1)
    proc.stdin.write("uci\nisready\n"); proc.stdin.flush()
    for line in proc.stdout:
        if line.startswith("readyok"):
            break
    worst_p = worst_v = 0.0
    count = 0
    for gi, line in enumerate(open(games_path)):
        if gi >= n_games:
            break
        g = json.loads(line)
        recs = np.frombuffer(gzip.open(os.path.join(chunk_dir, "game_%d.gz" % gi)).read(), dtype=L.V6)
        x = torch.from_numpy(L.planes_from_v6(recs))
        with torch.no_grad():
            logits, wdl = net(x)
        k = 0
        for ply, (mv, pol) in enumerate(zip(g["moves"], g["policy"])):   # a resigned game has one extra policy
            if not pol:
                continue
            legal = recs["probs"][k] >= 0
            lp = logits[k].numpy().astype(np.float64)
            lp[~legal] = -np.inf
            p = np.exp(lp - lp.max()); p /= p.sum()
            w = torch.softmax(wdl[k], 0).numpy()
            pol_lc0, wl, d = lc0_eval(proc, g["moves"][:ply])
            if set(pol_lc0) != set(np.nonzero(legal)[0].tolist()):
                raise SystemExit("legal move sets differ at game %d ply %d" % (gi, ply))
            worst_p = max(worst_p, max(abs(pol_lc0[i] - 100 * p[i]) for i in pol_lc0))
            worst_v = max(worst_v, abs(wl - (w[0] - w[2])), abs(d - w[1]))
            k += 1
            count += 1
    proc.stdin.write("quit\n"); proc.stdin.flush(); proc.wait()
    print("%d positions: largest policy difference %.3f percentage points, largest W-L/D difference %.4f"
          % (count, worst_p, worst_v))


if __name__ == "__main__":
    main()
