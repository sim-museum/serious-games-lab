"""Unpack an InstallShield "ISSetupStream" payload (setup.exe overlay) without running it -- HEADTRACK-2 (PO 10-25).

A Python port of the ISSetupStream path of ISx 0.3.11 (github.com/lifenjoiner/ISx, ISx.c: get_is_header,
get_is_file_attributes_ustrm, gen_key, decode_byte, decode_data_ustrm, extract_encrypted_files). Read-only on the input;
writes the payload files under outdir.
usage: isx_stream.py overlay_file outdir
"""
import os
import struct
import sys
import zlib

MAGIC = bytes([0x13, 0x35, 0x86, 0x07])
SWAP = bytes(((b << 4) | (b >> 4)) & 0xFF for b in range(256))  # Byte * 16 | Byte >> 4, as uint8


def decode(data, key):
    """decode_data_ustrm: every 1024-byte block restarts the key at 0; byte = ~(key ^ swap_nibbles(byte))."""
    out = bytearray(data.translate(SWAP))
    n = len(key)
    rep = (key * (1024 // n + 1))[:1024]
    for start in range(0, len(out), 1024):
        blk = out[start:start + 1024]
        k = rep[:len(blk)]
        out[start:start + len(blk)] = bytes((~(a ^ b)) & 0xFF for a, b in zip(blk, k))
    return bytes(out)


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    d = open(src, "rb").read()
    sig, num_files, typ = struct.unpack_from("<14sHI", d, 0)
    assert sig.rstrip(b"\0") == b"ISSetupStream", sig
    off = 46                                    # sizeof(IS_HEADER)
    print(f"[isx] {num_files} files, type {typ}")
    for _ in range(num_files):
        name_len, flags, file_len = struct.unpack_from("<II2xI", d, off)
        launcher = struct.unpack_from("<H", d, off + 22)[0]
        off += 24                               # sizeof(IS_FILE_ATTRIBUTES_X)
        if typ == 4:
            off += 24
        name = d[off:off + name_len].decode("utf-16-le").rstrip("\0")
        off += name_len
        data = d[off:off + file_len]
        off += file_len
        if flags & 4:
            seed = name.encode("utf-8")
            data = decode(data, bytes(s ^ MAGIC[i % 4] for i, s in enumerate(seed)))
        if launcher:
            data = zlib.decompress(data)
        dest = os.path.join(outdir, name.replace("\\", "/").lstrip("/"))
        os.makedirs(os.path.dirname(dest) or outdir, exist_ok=True)
        open(dest, "wb").write(data)
        print(f"[isx] {name} flags {flags} launcher {launcher} {file_len} -> {len(data)} bytes")


if __name__ == "__main__":
    main()
