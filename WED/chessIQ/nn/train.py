"""Train a Kramnik Leela network on prepared positions (EPIC NN, sprint NN-4) and save it in lc0's format.
python train.py <train.npz> <holdout.npz> <out prefix> [--blocks 6] [--channels 64] [--epochs 10] [--batch 1024]
Writes <prefix>.pt (PyTorch) and <prefix>.pb.gz (for lc0 / Nibbler), and prints per-epoch held-out metrics:
policy loss, top-1 agreement with the engine's best move, value loss, and W/D/L accuracy."""
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lc0net as L  # noqa: E402

DEV = "cuda" if torch.cuda.is_available() else "cpu"
BIT = torch.tensor([128, 64, 32, 16, 8, 4, 2, 1], dtype=torch.uint8)


def arg(name, default):
    return type(default)(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


def load(path):
    d = np.load(path)
    return {k: torch.from_numpy(d[k].astype(np.float32) if d[k].dtype == np.float16 else d[k]) for k in d.files}


def unpack(bytes_u8):            # (B, n) uint8 -> (B, 8n) {0,1}, most significant bit first (as np.unpackbits)
    return (bytes_u8.unsqueeze(-1) & BIT.to(bytes_u8.device)).ne(0).flatten(1)


def batch(data, idx):
    b = {k: v[idx].to(DEV, non_blocking=True) for k, v in data.items()}
    n = len(idx)
    planes = unpack(b["planes"].contiguous().view(torch.uint8).view(n, 832)).float().view(n, 104, 64)
    x = torch.zeros(n, 112, 64, device=DEV)
    x[:, :104] = planes
    x[:, 108] = b["stm"].float()[:, None]
    x[:, 109] = b["rule50"].float()[:, None]
    x[:, 111] = 1.0
    legal = unpack(b["legal"])[:, :1858]
    pol = torch.zeros(n, 1858, device=DEV)
    pol.scatter_(1, b["pidx"].long(), b["pval"])
    return x.view(n, 112, 8, 8), legal, pol, b["wdl"]


def losses(net, x, legal, pol, wdl):
    logits, v = net(x)
    logits = logits.masked_fill(~legal, -1e9)
    lp = F.log_softmax(logits, 1)
    pl = -(pol * lp).sum(1).mean()
    vl = -(wdl * F.log_softmax(v, 1)).sum(1).mean()
    top1 = (logits.argmax(1) == pol.argmax(1)).float().mean()
    vacc = (v.argmax(1) == wdl.argmax(1)).float().mean()
    return pl, vl, top1, vacc


def evaluate(net, data, bs):
    net.eval()
    n = len(data["stm"])
    tot = np.zeros(4)
    with torch.no_grad():
        for s in range(0, n, bs):
            idx = torch.arange(s, min(n, s + bs))
            tot += np.array([t.item() for t in losses(net, *batch(data, idx))]) * len(idx)
    net.train()
    return tot / n


def main():
    tr, ho, prefix = load(sys.argv[1]), load(sys.argv[2]), sys.argv[3]
    blocks, channels = arg("--blocks", 6), arg("--channels", 64)
    epochs, bs, lr = arg("--epochs", 10), arg("--batch", 1024), arg("--lr", 0.002)
    net = L.LeelaNet(blocks, channels).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    n = len(tr["stm"])
    steps = epochs * math.ceil(n / bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.1)
    print("training %dx%d on %d positions (held out %d), %d steps on %s" % (blocks, channels, n, len(ho["stm"]), steps, DEV),
          flush=True)
    pl, vl, top1, vacc = evaluate(net, ho, bs)
    print("epoch 0: held-out policy %.3f  top-1 %.1f%%  value %.3f  wdl acc %.1f%%" % (pl, 100 * top1, vl, 100 * vacc), flush=True)
    t0 = time.time()
    for ep in range(1, epochs + 1):
        perm = torch.randperm(n)
        for s in range(0, n, bs):
            p_l, v_l, _, _ = losses(net, *batch(tr, perm[s:s + bs]))
            loss = p_l + v_l
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
        pl, vl, top1, vacc = evaluate(net, ho, bs)
        print("epoch %d: held-out policy %.3f  top-1 %.1f%%  value %.3f  wdl acc %.1f%%  (%.0f s)"
              % (ep, pl, 100 * top1, vl, 100 * vacc, time.time() - t0), flush=True)
    net = net.cpu().eval()
    torch.save(net.state_dict(), prefix + ".pt")
    L.save_lc0(net, prefix + ".pb.gz")
    print("saved %s.pt and %s.pb.gz" % (prefix, prefix))


if __name__ == "__main__":
    main()
