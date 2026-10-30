"""Find linuxtrack's TrackIR firmware blobs inside NaturalPoint's installed files, without linuxtrack's Qt extractor.

Ports qt_gui/hashing.h FastHash (a 16-bit hash of a block's first 32 bytes) and BlockId::isBlock (md5 + sha1 of the
whole block) from linuxtrack, and reads its qt_gui/spec.txt (name size fasthash md5 sha1). Matches are written to the
output directory, gzipped as linuxtrack's extractor does (.fw -> .fw.gz).
usage: tir_fw_scan.py spec.txt outdir file_or_dir [...]
"""
import gzip
import hashlib
import os
import sys

import numpy as np

L = 32


def fast_hashes(data):
    """FastHash value at every block start (its buffer is std::vector<uint8_t>: bytes are unsigned)."""
    b = np.frombuffer(data, dtype=np.uint8)
    n = len(b) - L + 1
    if n <= 0:
        return np.zeros(0, dtype=np.uint32)
    signed = b.astype(np.uint32)
    tmp = np.zeros(n, dtype=np.uint32)
    for i in range(L):
        tmp = np.where(tmp & 0x8000, tmp ^ 3, tmp)
        tmp = (tmp << 2) & 0xFFFF
        tmp ^= signed[i:i + n]
    return tmp


def main():
    spec, out = sys.argv[1], sys.argv[2]
    targets = []
    for line in open(spec):
        f = line.split()
        if len(f) == 5:
            targets.append((f[0], int(f[1]), int(f[2]), f[3], f[4]))
    os.makedirs(out, exist_ok=True)
    files = []
    for p in sys.argv[3:]:
        if os.path.isdir(p):
            files += [os.path.join(d, n) for d, _s, ns in os.walk(p) for n in ns]
        else:
            files.append(p)
    found = {}
    for path in files:
        data = open(path, "rb").read()
        h = fast_hashes(data)
        for name, size, fh, md5, sha1 in targets:
            if name in found:
                continue
            for pos in np.nonzero(h == fh)[0]:
                blk = data[pos:pos + size]
                if len(blk) == size and hashlib.md5(blk).hexdigest() == md5 and hashlib.sha1(blk).hexdigest() == sha1:
                    found[name] = path
                    dest = os.path.join(out, name)
                    if name.endswith(".fw"):
                        with gzip.open(dest + ".gz", "wb", compresslevel=9) as g:
                            g.write(blk)
                    else:
                        open(dest, "wb").write(blk)
                    print(f"[fw] {name} at {pos} in {path}", flush=True)
                    break
    for name, *_ in targets:
        if name not in found:
            print(f"[fw] {name} not found")


if __name__ == "__main__":
    main()
