"""A Leela (lc0) network in PyTorch that saves in lc0's own weights format (EPIC NN, sprint NN-4).

Structure = lc0's NETWORK_SE_WITH_HEADFORMAT with the classical heads, ReLU throughout:
  input  3x3 conv 112 -> C (+BN)
  tower  B residual blocks: 3x3 conv (+BN) ReLU, 3x3 conv (+BN), squeeze-excitation (avg pool -> FC C/ratio ReLU
         -> FC 2C: sigmoid gate on the first C, bias on the second C), + skip, ReLU
  policy classical: 1x1 conv C -> 32 (+BN) ReLU, FC 32*64 -> 1858 (lc0's move index order: POLICY_CLASSICAL)
         conv:      3x3 conv C -> C (+BN) ReLU, 3x3 conv C -> 80 (+bias), lc0's fixed map of 73x64 -> 1858
                    (POLICY_CONVOLUTION, as in Leela's own networks -- load_lc0() reads those for fine-tuning)
  value  1x1 conv C -> V (+BN) ReLU, FC V*64 -> 128 ReLU, FC 128 -> 3 (win/draw/loss: VALUE_WDL); V = 32 or 128
Batch norm is stored alongside each convolution, as in lc0's own networks; lc0 folds it at load time.
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


CONV_MAP = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "conv_policy_map.npy"))   # 73*64 -> idx


class LeelaNet(nn.Module):
    def __init__(self, blocks=6, channels=64, se_ratio=4, policy="classical", value_filters=32):
        super().__init__()
        self.blocks, self.channels, self.se_ratio, self.policy = blocks, channels, se_ratio, policy
        self.input = ConvBN(112, channels, 3)
        self.tower = nn.Sequential(*[Block(channels, se_ratio) for _ in range(blocks)])
        if policy == "conv":
            self.pol1 = ConvBN(channels, channels, 3)
            self.pol2 = nn.Conv2d(channels, 80, 3, padding=1, bias=True)
            src = np.zeros(1858, dtype=np.int64)
            for i, j in enumerate(CONV_MAP):
                if j >= 0:
                    src[j] = i
            self.register_buffer("pol_src", torch.from_numpy(src), persistent=False)
        else:
            self.pol_conv = ConvBN(channels, 32, 1)
            self.pol_fc = nn.Linear(32 * 64, 1858)
        self.value_filters = value_filters          # 32 in LD2, 128 in the 20x256 T40 network (NN-14)
        self.val_conv = ConvBN(channels, value_filters, 1)
        self.val_fc1 = nn.Linear(value_filters * 64, 128)
        self.val_fc2 = nn.Linear(128, 3)

    def forward(self, x):
        x = self.tower(F.relu(self.input(x)))
        if self.policy == "conv":
            p = self.pol2(F.relu(self.pol1(x))).flatten(1)[:, self.pol_src]
        else:
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
    """Store the conv and its batch norm separately, as lc0's own networks do; lc0 folds them at load time in full
    precision. (Folding first and then quantizing to 16 bits coarsened whole layers when one channel's variance was
    tiny: a round trip of LD2 drifted by 1.3 percentage points of policy.)"""
    bn = convbn.bn
    _layer(block.weights, convbn.conv.weight)
    _layer(block.biases, torch.zeros_like(bn.running_mean))
    _layer(block.bn_means, bn.running_mean)
    _layer(block.bn_stddivs, bn.running_var)          # lc0's "stddivs" are variances (it adds eps and takes sqrt)
    _layer(block.bn_gammas, bn.weight)
    _layer(block.bn_betas, bn.bias)


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
    nf.policy = pb.NetworkFormat.POLICY_CONVOLUTION if net.policy == "conv" else pb.NetworkFormat.POLICY_CLASSICAL
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
    if net.policy == "conv":
        _conv(w.policy1, net.pol1)
        _layer(w.policy.weights, net.pol2.weight); _layer(w.policy.biases, net.pol2.bias)
    else:
        _conv(w.policy, net.pol_conv)
        _layer(w.ip_pol_w, net.pol_fc.weight); _layer(w.ip_pol_b, net.pol_fc.bias)
    _conv(w.value, net.val_conv)
    _layer(w.ip1_val_w, net.val_fc1.weight); _layer(w.ip1_val_b, net.val_fc1.bias)
    _layer(w.ip2_val_w, net.val_fc2.weight); _layer(w.ip2_val_b, net.val_fc2.bias)
    with gzip.open(path, "wb") as f:
        f.write(n.SerializeToString())


def _dq(layer):
    """lc0 LINEAR16 layer -> float32 numpy (value = min + q / 65535 * (max - min))."""
    q = np.frombuffer(layer.params, dtype="<u2").astype(np.float64)
    return (layer.min_val + q / 65535.0 * (layer.max_val - layer.min_val)).astype(np.float32)


def _set_convbn(cb, block, shape):
    """Load an lc0 ConvBlock into a ConvBN: lc0 computes gamma * (conv + bias - mean) / sqrt(var + eps) + beta."""
    cb.conv.weight.data = torch.from_numpy(_dq(block.weights).reshape(shape))
    c = shape[0]
    bias = _dq(block.biases) if block.biases.params else np.zeros(c, np.float32)
    if block.bn_means.params:
        mean, var = _dq(block.bn_means), _dq(block.bn_stddivs)
        gamma = _dq(block.bn_gammas) if block.bn_gammas.params else np.ones(c, np.float32)
        beta = _dq(block.bn_betas) if block.bn_betas.params else np.zeros(c, np.float32)
    else:                         # no batch norm: plain conv + bias
        mean, var, gamma, beta = np.zeros(c, np.float32), np.full(c, 1 - cb.bn.eps, np.float32), \
            np.ones(c, np.float32), np.zeros(c, np.float32)
    cb.bn.running_mean.data = torch.from_numpy(mean - bias)
    cb.bn.running_var.data = torch.from_numpy(var)
    cb.bn.weight.data = torch.from_numpy(gamma)
    cb.bn.bias.data = torch.from_numpy(beta)


def load_lc0(path):
    """A Leela network (classical input, SE tower, convolutional policy, WDL value) as a LeelaNet."""
    import net_pb2 as pb
    n = pb.Net()
    with gzip.open(path, "rb") as f:
        n.ParseFromString(f.read())
    nf, w = n.format.network_format, n.weights
    if nf.input != pb.NetworkFormat.INPUT_CLASSICAL_112_PLANE or nf.value != pb.NetworkFormat.VALUE_WDL \
            or nf.policy != pb.NetworkFormat.POLICY_CONVOLUTION or len(w.residual) == 0 or not w.residual[0].se.w1.params:
        raise ValueError("needs classical input, an SE tower, convolutional policy and WDL value: " + path)
    blocks = len(w.residual)
    c = len(_dq(w.input.biases)) if w.input.biases.params else len(_dq(w.input.bn_means))
    se_ch = len(_dq(w.residual[0].se.b1))
    vc = len(_dq(w.value.biases)) if w.value.biases.params else len(_dq(w.value.bn_means))
    net = LeelaNet(blocks, c, c // se_ch, policy="conv", value_filters=vc)
    _set_convbn(net.input, w.input, (c, 112, 3, 3))
    for blk, r in zip(net.tower, w.residual):
        _set_convbn(blk.c1, r.conv1, (c, c, 3, 3))
        _set_convbn(blk.c2, r.conv2, (c, c, 3, 3))
        blk.se.fc1.weight.data = torch.from_numpy(_dq(r.se.w1).reshape(se_ch, c))
        blk.se.fc1.bias.data = torch.from_numpy(_dq(r.se.b1))
        blk.se.fc2.weight.data = torch.from_numpy(_dq(r.se.w2).reshape(2 * c, se_ch))
        blk.se.fc2.bias.data = torch.from_numpy(_dq(r.se.b2))
    _set_convbn(net.pol1, w.policy1, (c, c, 3, 3))
    pw = _dq(w.policy.weights).reshape(80, c, 3, 3)
    pbias = _dq(w.policy.biases) if w.policy.biases.params else np.zeros(80, np.float32)
    if w.policy.bn_means.params:               # fold a batch norm on the final policy conv, if any
        g = (_dq(w.policy.bn_gammas) if w.policy.bn_gammas.params else 1) / np.sqrt(_dq(w.policy.bn_stddivs) + 1e-5)
        pw, pbias = pw * g[:, None, None, None], (pbias - _dq(w.policy.bn_means)) * g + \
            (_dq(w.policy.bn_betas) if w.policy.bn_betas.params else 0)
    net.pol2.weight.data, net.pol2.bias.data = torch.from_numpy(pw.astype(np.float32)), torch.from_numpy(pbias.astype(np.float32))
    _set_convbn(net.val_conv, w.value, (vc, c, 1, 1))
    net.val_fc1.weight.data = torch.from_numpy(_dq(w.ip1_val_w).reshape(128, vc * 64))
    net.val_fc1.bias.data = torch.from_numpy(_dq(w.ip1_val_b))
    net.val_fc2.weight.data = torch.from_numpy(_dq(w.ip2_val_w).reshape(3, 128))
    net.val_fc2.bias.data = torch.from_numpy(_dq(w.ip2_val_b))
    return net.eval()


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
