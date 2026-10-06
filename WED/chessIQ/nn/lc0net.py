"""A Leela (lc0) network in PyTorch that saves in lc0's own weights format (EPIC NN, sprint NN-4).

Structure = lc0's NETWORK_SE_WITH_HEADFORMAT with the classical heads, ReLU throughout:
  input  3x3 conv 112 -> C (+BN)
  tower  B residual blocks: 3x3 conv (+BN) ReLU, 3x3 conv (+BN), squeeze-excitation (avg pool -> FC C/ratio ReLU
         -> FC 2C: sigmoid gate on the first C, bias on the second C), + skip, ReLU
  policy 1x1 conv C -> 32 (+BN) ReLU, FC 32*64 -> 1858 (lc0's move index order: POLICY_CLASSICAL)
  value  1x1 conv C -> 32 (+BN) ReLU, FC 32*64 -> 128 ReLU, FC 128 -> 3 (win/draw/loss: VALUE_WDL)
Batch norm is folded into the convolutions on export; lc0 then uses the weights and biases as given.
Inputs: lc0's INPUT_CLASSICAL_112_PLANE, square index a1=0 .. h8=63 as row*8+file on an 8x8 grid.
"""
import gzip
import os
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "proto"))


class SE(nn.Module):
    def __init__(self, c, ratio):
        super().__init__()
        self.fc1 = nn.Linear(c, c // ratio)
        self.fc2 = nn.Linear(c // ratio, 2 * c)
        self.c = c

    def forward(self, x, skip):
        s = F.relu(self.fc1(x.mean(dim=(2, 3))))
        s = self.fc2(s)
        gamma, beta = s[:, :self.c], s[:, self.c:]
        return F.relu(torch.sigmoid(gamma)[:, :, None, None] * x + beta[:, :, None, None] + skip)


class ConvBN(nn.Module):
    def __init__(self, cin, cout, k):
        super().__init__()
        self.conv = nn.Conv2d(cin, cout, k, padding=k // 2, bias=False)
        self.bn = nn.BatchNorm2d(cout)

    def forward(self, x):
        return self.bn(self.conv(x))

    def folded(self):
        """(weight, bias) with batch norm folded in -- what lc0 computes itself from bn fields."""
        w = self.conv.weight.detach()
        bn = self.bn
        scale = bn.weight.detach() / torch.sqrt(bn.running_var + bn.eps)
        return w * scale[:, None, None, None], bn.bias.detach() - bn.running_mean * scale


class Block(nn.Module):
    def __init__(self, c, se_ratio):
        super().__init__()
        self.c1, self.c2, self.se = ConvBN(c, c, 3), ConvBN(c, c, 3), SE(c, se_ratio)

    def forward(self, x):
        return self.se(self.c2(F.relu(self.c1(x))), x)


class LeelaNet(nn.Module):
    def __init__(self, blocks=6, channels=64, se_ratio=4):
        super().__init__()
        self.blocks, self.channels, self.se_ratio = blocks, channels, se_ratio
        self.input = ConvBN(112, channels, 3)
        self.tower = nn.Sequential(*[Block(channels, se_ratio) for _ in range(blocks)])
        self.pol_conv = ConvBN(channels, 32, 1)
        self.pol_fc = nn.Linear(32 * 64, 1858)
        self.val_conv = ConvBN(channels, 32, 1)
        self.val_fc1 = nn.Linear(32 * 64, 128)
        self.val_fc2 = nn.Linear(128, 3)

    def forward(self, x):
        x = self.tower(F.relu(self.input(x)))
        p = self.pol_fc(F.relu(self.pol_conv(x)).flatten(1))
        v = self.val_fc2(F.relu(self.val_fc1(F.relu(self.val_conv(x)).flatten(1))))
        return p, v                                   # policy logits (1858), WDL logits (win, draw, loss)


# ---- lc0 weights file ----------------------------------------------------------------------------------------------
def _layer(layer, t):
    a = t.detach().float().cpu().numpy().ravel()
    lo, hi = float(a.min()), float(a.max())
    if hi == lo:
        hi = lo + 1e-6
    q = np.round((a - lo) / (hi - lo) * 65535).astype("<u2")
    layer.min_val, layer.max_val, layer.params = lo, hi, q.tobytes()


def _conv(block, convbn):
    w, b = convbn.folded()
    _layer(block.weights, w)
    _layer(block.biases, b)


def save_lc0(net, path):
    import net_pb2 as pb
    n = pb.Net()
    n.magic = 0x1c0
    n.license = "GPL-3.0-or-later; chessIQ Kramnik network"
    n.min_version.major, n.min_version.minor, n.min_version.patch = 0, 21, 0
    n.format.weights_encoding = pb.Format.LINEAR16
    nf = n.format.network_format
    nf.input = pb.NetworkFormat.INPUT_CLASSICAL_112_PLANE
    nf.output = pb.NetworkFormat.OUTPUT_WDL
    nf.network = pb.NetworkFormat.NETWORK_SE_WITH_HEADFORMAT
    nf.policy = pb.NetworkFormat.POLICY_CLASSICAL
    nf.value = pb.NetworkFormat.VALUE_WDL
    nf.moves_left = pb.NetworkFormat.MOVES_LEFT_NONE
    nf.default_activation = pb.NetworkFormat.DEFAULT_ACTIVATION_RELU
    w = n.weights
    _conv(w.input, net.input)
    for blk in net.tower:
        r = w.residual.add()
        _conv(r.conv1, blk.c1)
        _conv(r.conv2, blk.c2)
        _layer(r.se.w1, blk.se.fc1.weight); _layer(r.se.b1, blk.se.fc1.bias)
        _layer(r.se.w2, blk.se.fc2.weight); _layer(r.se.b2, blk.se.fc2.bias)
    _conv(w.policy, net.pol_conv)
    _layer(w.ip_pol_w, net.pol_fc.weight); _layer(w.ip_pol_b, net.pol_fc.bias)
    _conv(w.value, net.val_conv)
    _layer(w.ip1_val_w, net.val_fc1.weight); _layer(w.ip1_val_b, net.val_fc1.bias)
    _layer(w.ip2_val_w, net.val_fc2.weight); _layer(w.ip2_val_b, net.val_fc2.bias)
    with gzip.open(path, "wb") as f:
        f.write(n.SerializeToString())


# ---- V6 training records -> tensors ----------------------------------------------------------------------------------
V6 = np.dtype([("version", "<u4"), ("input_format", "<u4"), ("probs", "<f4", 1858), ("planes", "<u8", 104),
               ("castling", "u1", 4), ("stm", "u1"), ("rule50", "u1"), ("inv", "u1"), ("dummy", "u1"),
               ("rest", "<f4", 15), ("visits", "<u4"), ("played_idx", "<u2"), ("best_idx", "<u2"), ("kld", "<f4"),
               ("res", "<u4")])


def planes_from_v6(recs):
    """(N, 112, 8, 8) float32: 104 board planes + castling(4, zero in Kramnik) + side to move + rule50 + 0 + ones,
    exactly as lc0's classical encoder builds them."""
    n = len(recs)
    bits = np.unpackbits(np.ascontiguousarray(recs["planes"]).view(np.uint8)).reshape(n, 104, 64)
    x = np.zeros((n, 112, 64), dtype=np.float32)
    x[:, :104] = bits
    for i in range(4):
        x[:, 104 + i] = (recs["castling"][:, i] != 0)[:, None]
    x[:, 108] = (recs["stm"] != 0)[:, None]
    x[:, 109] = recs["rule50"].astype(np.float32)[:, None]
    x[:, 111] = 1.0
    return x.reshape(n, 112, 8, 8)


def targets_from_v6(recs):
    """policy (N, 1858) with illegal = -1 kept as a mask, WDL target (N, 3) from result_q/result_d."""
    q, d = recs["rest"][:, 7], recs["rest"][:, 8]
    wdl = np.stack([(1 - d + q) / 2, d, (1 - d - q) / 2], axis=1).astype(np.float32)
    return recs["probs"].astype(np.float32), wdl
