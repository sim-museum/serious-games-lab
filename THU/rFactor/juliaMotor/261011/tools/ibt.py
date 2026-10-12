"""numpy .ibt reader (IRGOLD-1): read_ibt(path, names) -> (dict name->array, yaml str, tickRate)."""
import struct
import numpy as np

_DT = {0: "i1", 1: "?", 2: "<i4", 3: "<u4", 4: "<f4", 5: "<f8"}


def _cstr(b):
    return b.split(b"\x00", 1)[0].decode("latin-1", "replace")


def header(path):
    with open(path, "rb") as f:
        data = f.read()
    (ver, status, tick, siUpd, siLen, siOff, nvars, vhOff, numBuf, bufLen) = struct.unpack_from("<10i", data, 0)
    off0 = struct.unpack_from("<4i", data, 48)[1]
    vars_ = {}
    for i in range(nvars):
        b = vhOff + i * 144
        t, o, c = struct.unpack_from("<3i", data, b)
        vars_[_cstr(data[b + 16:b + 48])] = (t, o, c, _cstr(data[b + 112:b + 144]))
    yaml = data[siOff:siOff + siLen].decode("latin-1", "replace")
    nrows = (len(data) - off0) // bufLen
    return data, vars_, yaml, tick, off0, bufLen, nrows


def read_ibt(path, names=None):
    data, vars_, yaml, tick, off0, bufLen, nrows = header(path)
    rows = np.frombuffer(data, dtype=np.uint8, count=nrows * bufLen, offset=off0).reshape(nrows, bufLen)
    out = {}
    for n in (names if names is not None else [k for k, v in vars_.items() if v[2] == 1]):
        if n not in vars_:
            continue
        t, o, c, _u = vars_[n]
        dt = np.dtype(_DT[t])
        if c == 1:
            out[n] = rows[:, o:o + dt.itemsize].copy().view(dt).ravel().astype(np.float64)
        else:
            out[n] = rows[:, o:o + dt.itemsize * c].copy().view(dt).reshape(nrows, c).astype(np.float64)
    return out, yaml, tick


def yget(yaml, *keys):
    """Value of a nested YAML key path (indent-based, first match), e.g. yget(y, 'LeftFront', 'SpringRate')."""
    lines = yaml.splitlines()
    i, ind = 0, -1
    for k in keys:
        found = False
        while i < len(lines):
            ln = lines[i]; i += 1
            s = ln.lstrip(); d = len(ln) - len(s)
            if d <= ind and s:
                return None
            if s.startswith(k + ":"):
                ind = d; found = True
                val = s[len(k) + 1:].strip()
                break
        if not found:
            return None
    return val
