#!/usr/bin/env python3
"""Minimal iRacing .ibt (irSDK telemetry) reader — enumerate channels + dump YAML header.

.ibt layout (little-endian):
  irsdk_header (112 B): ver, status, tickRate, sessionInfoUpdate, sessionInfoLen,
      sessionInfoOffset, numVars, varHeaderOffset, numBuf, bufLen, pad[2],
      varBuf[4]{tickCount, bufOffset, pad[2]}
  varHeader[numVars] @ varHeaderOffset (144 B each):
      type, offset, count, countAsTime+pad[3], name[32], desc[64], unit[32]
  sessionInfo YAML string @ sessionInfoOffset (sessionInfoLen bytes)
  data rows @ varBuf.bufOffset, stride = bufLen, one row per tick
"""
import struct, sys

VT = {0: ("char", 1, "b"), 1: ("bool", 1, "?"), 2: ("int", 4, "i"),
      3: ("bitfield", 4, "I"), 4: ("float", 4, "f"), 5: ("double", 8, "d")}

def cstr(b):
    return b.split(b"\x00", 1)[0].decode("latin-1", "replace")

def parse(path):
    with open(path, "rb") as f:
        data = f.read()
    h = struct.unpack_from("<10i", data, 0)
    (ver, status, tickRate, siUpd, siLen, siOff, numVars, vhOff, numBuf, bufLen) = h
    varbufs = []
    for i in range(4):
        tc, off, _, _ = struct.unpack_from("<4i", data, 48 + i*16)
        varbufs.append((tc, off))
    vars_ = []
    for i in range(numVars):
        base = vhOff + i*144
        vtype, voff, vcount = struct.unpack_from("<3i", data, base)
        countAsTime = data[base+12]
        name = cstr(data[base+16:base+16+32])
        desc = cstr(data[base+48:base+48+64])
        unit = cstr(data[base+112:base+112+32])
        vars_.append(dict(type=vtype, offset=voff, count=vcount,
                          countAsTime=countAsTime, name=name, desc=desc, unit=unit))
    yaml = data[siOff:siOff+siLen].decode("latin-1", "replace")
    nrows = (len(data) - varbufs[0][1]) // bufLen if bufLen else 0
    return dict(ver=ver, tickRate=tickRate, numVars=numVars, bufLen=bufLen,
                numBuf=numBuf, varbufs=varbufs, vars=vars_, yaml=yaml,
                nrows=nrows, total=len(data))

def read_channel(data, m, name):
    """Read full time series of one scalar channel as a list of floats."""
    v = next(x for x in m["vars"] if x["name"] == name)
    fmt = VT[v["type"]][2]; sz = VT[v["type"]][1]
    base = m["varbufs"][0][1]; stride = m["bufLen"]; off = v["offset"]
    out = []
    for r in range(m["nrows"]):
        out.append(struct.unpack_from("<" + fmt, data, base + r*stride + off)[0])
    return out

if __name__ == "__main__":
    path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "channels"
    m = parse(path)
    if mode == "stats":
        with open(path, "rb") as f:
            data = f.read()
        for name in sys.argv[3:]:
            try:
                s = read_channel(data, m, name)
                lo, hi = min(s), max(s)
                mean = sum(s)/len(s)
                print(f"{name:22s} min={lo:11.3f}  max={hi:11.3f}  mean={mean:11.3f}")
            except StopIteration:
                print(f"{name:22s} <not found>")
        sys.exit(0)
    if mode == "yaml":
        sys.stdout.write(m["yaml"])
    elif mode == "summary":
        print(f"file       : {path.split('/')[-1]}")
        print(f"ver={m['ver']} tickRate={m['tickRate']}Hz numVars={m['numVars']} "
              f"bufLen={m['bufLen']}B rows~={m['nrows']} dur~={m['nrows']/max(m['tickRate'],1):.1f}s")
    else:
        for v in sorted(m["vars"], key=lambda x: x["name"].lower()):
            tn = VT.get(v["type"], ("?",))[0]
            arr = f"[{v['count']}]" if v["count"] > 1 else ""
            print(f"{v['name']+arr:32s} {tn:8s} {v['unit']:14s} {v['desc']}")
        print(f"\n# {m['numVars']} channels, {m['tickRate']}Hz, {m['nrows']} rows "
              f"(~{m['nrows']/max(m['tickRate'],1):.0f}s)")
