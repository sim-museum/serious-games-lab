"""REPLAY-2 S2 -- the replay analyser (PO 2026-10-06: "add the GPL replay analyzer features for further analysis of
the replay ... this is the gold standard for this functionality, which should be available as an addition to
replaying the replay video").

Modelled on GPL Replay Analyser 7.9: pick laps (any car, up to five), see their racing lines on a zoomable track map,
compare telemetry against distance (speed, throttle/brake, steering, gear, rpm, lateral position, long/lat g), plot
the time difference between two laps, and read split times at 25/50/75 % with each driver's theoretical best.

Input is the `.jrt` file the sim writes beside every `.jmr` replay (drive_native_mtk.jl, `write_replay`): one JSON
header line, then float32 frames -- a pose block (t, then x, y, z, heading per car) and a telemetry block (the player's
`tele_player` channels, then `tele_ai` per AI car). Pure Python + PyQt6: no numpy, so it runs from the AppImage.
"""
import json
import math
import os
import struct

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

LAP_COLOURS = ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8"]   # up to five laps, as GPL Replay Analyser
SPLITS = (0.25, 0.50, 0.75)                                              # its split points
GRID_M = 5.0                                                             # resampling step along the lap (m)
UNFINISHED_MIN_M = 200.0                                                 # REPLAY-3: shorter stubs are not listed
G = 9.81


def jrt_path(jmr):
    return jmr[:-4] + ".jrt" if jmr.endswith(".jmr") else jmr


# ---------------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------------
class Lap:
    """One timed lap of one car, resampled onto a common distance grid (metres along the player's lap)."""
    __slots__ = ("car", "driver", "num", "t0", "t1", "time", "i0", "i1", "dist", "ch", "xs", "zs", "ds", "splits", "clean",
                 "start", "reached", "full")

    def label(self):
        if self.time is None:                      # REPLAY-3: an unfinished lap (crash, retirement, end of recording)
            return f"{self.driver} — lap {self.num}  " + _untimed(self)
        return f"{self.driver} — lap {self.num}  {fmt_time(self.time)}" + ("  (from the start)" if self.start else "")


class Replay:
    def __init__(self, path):
        with open(path, "rb") as f:
            raw = f.read()
        nl = raw.index(b"\n")
        self.h = h = json.loads(raw[:nl].decode("utf-8"))
        self.path = path
        self.ncar = h["ncar"]
        self.names = h["names"]
        self.laplen = float(h["laplen"])
        self.line_total = float(h.get("line_total") or self.laplen)
        self.refline = h.get("refline", [])
        self.tp = h["tele_player"]; self.ta = h["tele_ai"]
        npose = 1 + 4 * self.ncar
        ntele = len(self.tp) + len(self.ta) * (self.ncar - 1)
        fr = npose + ntele
        body = raw[nl + 1:]
        n = len(body) // (4 * fr)
        vals = struct.unpack("<%df" % (n * fr), body[: n * fr * 4])
        self.n = n
        self.t = [vals[k * fr] for k in range(n)]
        # per car: x, z, heading, and its channels as columns
        self.cars = []
        for c in range(self.ncar):
            o = 1 + 4 * c
            car = {"x": [vals[k * fr + o] for k in range(n)], "z": [vals[k * fr + o + 2] for k in range(n)],
                   "heading": [vals[k * fr + o + 3] for k in range(n)]}
            if c == 0:
                for j, name in enumerate(self.tp):
                    car[name] = [vals[k * fr + npose + j] for k in range(n)]
                car["dist"] = car["lapdist"]; car["L"] = self.laplen
            else:
                base = npose + len(self.tp) + len(self.ta) * (c - 1)
                for j, name in enumerate(self.ta):
                    car[name] = [vals[k * fr + base + j] for k in range(n)]
                car["dist"] = car["s"]; car["L"] = self.line_total
            self._derive(car)
            self.cars.append(car)
        # REPLAY-3: a race's lap 1 is timed from the green flag (the "race" channel of the first frame); a practice
        # session's first lap is an out-lap from the pits and stays untimed
        self.race = "race" in self.cars[0] and self.n > 0 and self.cars[0]["race"][0] > 0.5
        # WGTD-1 (PO 2026-10-08: "a spurious diagonal straight line running through the watkins glen map below the graphs"):
        # a restart R before anyone finished lap 1 leaves every lap counter at 0, so no lap boundary was seen -- each car's
        # "lap 1" ran across the restart (WG 21:18: 2:17-2:26 laps) and the map joined the crash spot to the grid with a
        # 1.5 km straight line. A restart teleports the player to the grid: > 60 m between two frames marks a new session.
        p0 = self.cars[0] if self.ncar else None
        self.restarts = set()
        if p0 is not None:
            for k in range(1, self.n):
                if math.hypot(p0["x"][k] - p0["x"][k - 1], p0["z"][k] - p0["z"][k - 1]) > 60.0:
                    self.restarts.add(k)
        self.laps = []                             # timed laps -- every statistic, report and the coach use these only
        self.unfinished = []                       # laps cut short (crash, restart, end of recording): plotted, never timed
        for c in range(self.ncar):
            done, cut = self._laps_of(c)
            self.laps += done; self.unfinished += cut

    def _derive(self, car):
        """Longitudinal and lateral acceleration (g) from speed and heading -- every car has them."""
        n = self.n; t = self.t; v = car["speed"]; th = car["heading"]
        along = [0.0] * n; alat = [0.0] * n
        for k in range(1, n - 1):
            dt = t[k + 1] - t[k - 1]
            if dt <= 1e-6:
                continue
            along[k] = (v[k + 1] - v[k - 1]) / dt / G
            dth = (th[k + 1] - th[k - 1] + math.pi) % (2 * math.pi) - math.pi
            alat[k] = v[k] * dth / dt / G
        car["glong"] = _smooth(along, 2); car["glat"] = _smooth(alat, 2)   # differentiated at 15 Hz: a 5-sample mean

    def _laps_of(self, c):
        car = self.cars[c]; lap = car["lap"]; d = car["dist"]; L = car["L"]; t = self.t
        # REPLAY-3 (PO 2026-10-07: "There are never any replays on the left panel to choose from"): only line-to-line laps
        # were timed, so a 1-lap race -- the PO's usual -- had none at all. GPL's Replay Analyser times lap 1 from the
        # start; so does this: the recording begins at the green flag, which opens lap `lap[0] + 1`.
        # (frame index after the line, exact time or None if untimed, lap started); the start is untimed in practice
        # and whether a session begins there (the green flag or a restart): the car may then be on the grid, short of the line
        crossings = [(0, t[0] if self.race else None, int(lap[0]), True)] if self.n > 10 else []
        for k in range(1, self.n):
            if lap[k] == lap[k - 1] + 1:
                a = L - d[k - 1]; b = d[k]
                f = a / (a + b) if (a + b) > 0 and 0 <= a < 0.5 * L and 0 <= b < 0.5 * L else 0.5
                crossings.append((k, t[k - 1] + f * (t[k] - t[k - 1]), int(lap[k]), False))
            elif lap[k] < lap[k - 1] or k in self.restarts:   # a session restart (R): no lap spans it
                crossings.append((k, None, int(lap[k]), True))
        crossings.append((self.n, None, None, False))   # the end of the recording
        # REPLAY-3/4 (2026-10-09): a race that starts on a grid BEHIND the line (lap distance ~L, e.g. every car after a
        # restart R) crosses the line within seconds -- that crossing finishes the run to the line, not lap 1, which
        # ends at the NEXT crossing (it gave "lap 1  0:01.713"). Merge it into the start lap.
        # Only when the lap COUNTER ticked on that short run: the player's counter skips the grid crossing (the game times
        # lap 1 from the green to the end of a full lap -- the PO's Spa 6:38.871), so there the first tick comes after a
        # second wrap of the lap distance and must stand.
        if (len(crossings) >= 3 and crossings[0][3] and crossings[0][1] is not None and d[0] > 0.5 * L
                and crossings[1][1] is not None and not crossings[1][3]):
            k1 = crossings[1][0]
            wraps = sum(1 for k in range(1, k1 + 1) if d[k] - d[k - 1] < -0.5 * L)
            if wraps <= 1:
                del crossings[1]
        laps = []; cut = []
        for (k0, ta, la, fresh), (k1, tb, _lb, _f) in zip(crossings, crossings[1:]):
            if k1 - k0 < 10 or la is None:
                continue
            lp = Lap()
            # numbered as racing does: the lap completed at its END (the lap from the start is lap 1)
            lp.car = c; lp.driver = self.names[c] if c < len(self.names) else f"car {c}"; lp.num = la + 1
            lp.start = fresh; lp.i0 = k0
            if ta is not None and tb is not None:
                lp.t0 = ta; lp.t1 = tb; lp.time = tb - ta; lp.i1 = k1
                self._resample(lp, car)
                laps.append(lp)
            else:                                  # REPLAY-3: no line at one end -- an out-lap, a crash, a restart
                lp.t0 = t[k0] if ta is None else ta; lp.time = None; lp.i1 = k1 - 1
                self._resample(lp, car); lp.t1 = t[lp.i1]
                if lp.reached >= UNFINISHED_MIN_M:
                    cut.append(lp)
        return laps, cut

    def _resample(self, lp, car):
        """Channels against distance on a GRID_M grid of the PLAYER's lap length (AI distance is rescaled)."""
        L = car["L"]; scale = self.laplen / L if L > 0 else 1.0
        idx = list(range(lp.i0 if lp.start else lp.i0 - 1, lp.i1 + 1))   # a session start has no frame before the line
        # distance from this lap's line, UNWRAPPED frame to frame and monotone (a spin cannot rewind it). REPLAY-3: a
        # session starts on the grid, behind the line, where the lap distance reads ~L; and a step no car can drive
        # in one frame (a reset, the session's end) is not distance covered -- it once made a crashed lap "complete"
        d = car["dist"]; v = car["speed"]; t = self.t; k0 = idx[0]
        x = d[k0] - L if (k0 < lp.i0 or (lp.start and d[k0] > 0.5 * L)) else d[k0]
        ds = [max(x * scale, -1e9)]; prev = ds[0]
        for a, k in zip(idx, idx[1:]):
            step = (d[k] - d[a] + 0.5 * L) % L - 0.5 * L
            if abs(step) > 20.0 + 2.0 * max(v[a], v[k]) * max(t[k] - t[a], 0.0):
                if lp.time is None:                # an unfinished lap ends at the jump (no line drawn back to the pits)
                    break
                step = 0.0
            x += step; dk = max(x * scale, prev); ds.append(dk); prev = dk
        idx = idx[:len(ds)]
        lp.i1 = idx[-1] if lp.time is None else lp.i1
        ts = [self.t[k] - lp.t0 for k in idx]
        grid = [i * GRID_M for i in range(int(self.laplen // GRID_M) + 1)]
        names = [n for n in ("speed", "throttle", "brake", "steer", "gear", "rpm", "lateral", "lane", "glong", "glat")
                 if n in car]
        cols = {n: [car[n][k] for k in idx] for n in names}
        cols["time"] = ts
        if lp.time is None:                        # REPLAY-3: an unfinished lap is plotted only as far as it got
            lp.reached = ds[-1] if ds else 0.0; lp.full = lp.reached >= 0.98 * self.laplen
            grid = [g for g in grid if g <= lp.reached] or [0.0]
        else:
            lp.reached = self.laplen; lp.full = True
        lp.dist = grid
        lp.ch = {n: _interp(ds, cols[n], grid) for n in cols}
        if "speed" in lp.ch:
            lp.ch["kmh"] = [v * 3.6 for v in lp.ch["speed"]]
        if "lane" in lp.ch and "lateral" not in lp.ch:
            lp.ch["lateral"] = lp.ch["lane"]
        lp.xs = [car["x"][k] for k in idx]; lp.zs = [car["z"][k] for k in idx]; lp.ds = ds
        lp.splits = [_interp(ds, ts, [s * self.laplen])[0] if s * self.laplen <= lp.reached else None for s in SPLITS]
        lp.clean = ("ontrack" not in car) or all(car["ontrack"][k] > 0.5 for k in idx)


def _untimed(lp):
    """REPLAY-3: what an untimed lap shows in place of a time -- an out-lap or a lap after a restart went all the way
    round, anything else was cut short."""
    return "untimed" if lp.full else f"unfinished, {lp.reached:.0f} m"


def _smooth(v, r):
    n = len(v); out = [0.0] * n
    for k in range(n):
        a, b = max(0, k - r), min(n, k + r + 1); out[k] = sum(v[a:b]) / (b - a)
    return out


def _interp(xs, ys, grid):
    """Linear interpolation of ys(xs) at grid (xs non-decreasing); clamps at the ends."""
    out = []; j = 0; n = len(xs)
    for g in grid:
        while j < n - 2 and xs[j + 1] < g:
            j += 1
        x0, x1 = xs[j], xs[min(j + 1, n - 1)]
        if x1 <= x0 or g <= x0:
            out.append(ys[j] if g <= x0 else ys[min(j + 1, n - 1)])
        else:
            f = min(1.0, (g - x0) / (x1 - x0)); out.append(ys[j] + f * (ys[min(j + 1, n - 1)] - ys[j]))
    return out


def fmt_time(s):
    if s is None or not math.isfinite(s):
        return "—"
    m, r = divmod(s, 60.0)
    return f"{int(m)}:{r:06.3f}"


def sector_times(lp, laplen):
    """The four sectors between the line, the 25/50/75 % splits and the line."""
    pts = [0.0] + list(lp.splits) + [lp.time]
    return [b - a for a, b in zip(pts, pts[1:])]


def delta(a, b):
    """Time of lap b minus lap a at each grid distance (s): positive = b behind a there."""
    return [tb - ta for ta, tb in zip(a.ch["time"], b.ch["time"])]


# ---------------------------------------------------------------------------------------------------------------
# REPLAY-2 S3: reports (GPL Replay Analyser's race/practice report, lap chart, lap by lap, speed report)
# ---------------------------------------------------------------------------------------------------------------
def _cum(rep, c):
    """Race distance covered by car c at every frame, in the player's metres: laps * L + distance into the lap.
    A car on the grid BEHIND the line (lap 0, more than half a lap 'into' it) is just short of zero."""
    car = rep.cars[c]; L = car["L"]; s = rep.laplen / L if L > 0 else 1.0; d = car["dist"]
    if not d:
        return []
    # the start position decides once whether the car began behind the line; after that the distance is UNWRAPPED
    # frame to frame (a line crossing is a step of about -L), so a car halfway round lap 1 is not mistaken for one
    # still on the grid (the first version did exactly that and invented passes)
    x = d[0] - L if car["lap"][0] == 0 and d[0] > 0.5 * L else d[0] + car["lap"][0] * L
    out = [x * s]
    for k in range(1, len(d)):
        step = (d[k] - d[k - 1] + 0.5 * L) % L - 0.5 * L
        x += step; out.append(x * s)
    return out


def _order(cums, k):
    return sorted(range(len(cums)), key=lambda c: -cums[c][k])


def race_summary(rep):
    """Results (order at the end of the recording, gap in time), each car's laps, best and consistency."""
    cums = [_cum(rep, c) for c in range(rep.ncar)]; last = rep.n - 1
    order = _order(cums, last); lead = cums[order[0]]
    rows = []
    for pos, c in enumerate(order, 1):
        laps = [lp for lp in rep.laps if lp.car == c]
        times = [lp.time for lp in laps]
        best = min(times) if times else None
        avg = sum(times) / len(times) if times else None
        sd = (sum((t - avg) ** 2 for t in times) / len(times)) ** 0.5 if len(times) > 1 else None
        if pos == 1:
            gap = "—"
        else:                                             # when did the leader cover this car's final distance?
            target = cums[c][last]; k = next((k for k in range(rep.n) if lead[k] >= target), last)
            g = rep.t[last] - rep.t[k]
            lapsdown = int((lead[last] - target) // rep.laplen)
            gap = f"+{lapsdown} lap{'s' if lapsdown > 1 else ''}" if lapsdown >= 1 else f"+{g:.1f} s"
        rows.append((pos, rep.names[c], int(rep.cars[c]["lap"][last]), fmt_time(best), gap,
                     fmt_time(avg), f"{sd:.3f} s" if sd is not None else "—"))
    fast = sorted(rep.laps, key=lambda lp: lp.time)[:10]
    h = ["<h2>Session summary</h2>",
         f"<p>{_track_name(rep)} · {rep.ncar} car(s) · {fmt_time(rep.t[last])} recorded</p>",
         "<h3>Classification</h3>", _table(["Pos", "Driver", "Laps", "Best lap", "Gap", "Average lap", "Consistency (σ)"], rows),
         "<h3>Fastest laps</h3>", _table(["#", "Driver", "Lap", "Time"],
                                         [(i + 1, lp.driver, lp.num, fmt_time(lp.time)) for i, lp in enumerate(fast)])]
    return "\n".join(h)


def lap_chart(rep):
    """Each lap's running order: cars ranked by the moment they completed that lap."""
    by = {}
    for lp in rep.laps:
        by.setdefault(lp.num, []).append((lp.t1, lp.driver))
    for c in range(rep.ncar):                              # the lap a car is completing when its first timed lap starts
        car = rep.cars[c]
        for k in range(1, rep.n):
            if car["lap"][k] == car["lap"][k - 1] + 1:
                n = int(car["lap"][k])                     # the lap this crossing completes
                if n >= 1 and not any(d == rep.names[c] for _t, d in by.get(n, [])):
                    by.setdefault(n, []).append((rep.t[k], rep.names[c]))
    rows = []
    for n in sorted(by):
        rows.append([f"Lap {n}"] + [d for _t, d in sorted(by[n])])
    w = max((len(r) for r in rows), default=1)
    return "<h2>Lap chart</h2><p>Order in which the cars completed each lap.</p>" + \
        _table(["Lap"] + [f"P{i}" for i in range(1, w)], [r + [""] * (w - len(r)) for r in rows])


def lap_by_lap(rep):
    """A running account: the start order, then every change of position (sampled each second, held 2 s so a
    side-by-side moment is not counted twice), with where on the lap it happened."""
    cums = [_cum(rep, c) for c in range(rep.ncar)]
    step = max(1, int(rep.h.get("fps", 15)))
    ks = list(range(0, rep.n, step))
    if len(ks) < 3:
        return "<h2>Lap by lap</h2><p>The recording is too short.</p>"
    lines = ["<h2>Lap by lap</h2>", "<p><b>Start:</b> " + ", ".join(f"P{i + 1} {rep.names[c]}" for i, c in enumerate(_order(cums, ks[0]))) + "</p>"]
    prev = _order(cums, ks[0]); events = 0
    for a, b in zip(ks[1:], ks[2:]):
        cur = _order(cums, a)
        if cur != prev and _order(cums, b) == cur:         # held for the next sample too
            for i, c in enumerate(cur):
                j = prev.index(c)
                if j > i:                                  # c moved up: it passed the cars it is now ahead of
                    passed = [rep.names[x] for x in prev[i:j] if cur.index(x) > i]
                    if passed:
                        lap = int(rep.cars[c]["lap"][a]) + 1; d = cums[c][a] % rep.laplen     # on lap N = N-1 completed
                        lines.append(f"<p>{fmt_time(rep.t[a])} · lap {lap}, {d:.0f} m: <b>{rep.names[c]}</b> passes "
                                     + ", ".join(passed) + f" for P{i + 1}</p>")
                        events += 1
            prev = cur
    lines.append("<p><b>Order at the end:</b> " + ", ".join(f"P{i + 1} {rep.names[c]}" for i, c in enumerate(_order(cums, rep.n - 1))) + "</p>")
    if events == 0:
        lines.insert(2, "<p>No changes of position.</p>")
    return "\n".join(lines)


def speed_report(rep):
    """Per driver: top speed in each of the four sectors, overall top, lowest and average while moving (km/h)."""
    rows = []
    for c in range(rep.ncar):
        car = rep.cars[c]; L = car["L"]; v = car["speed"]
        sect = [0.0] * 4; vals = []
        for k in range(rep.n):
            if v[k] < 1.0:
                continue
            f = (car["dist"][k] % L) / L if L > 0 else 0.0
            j = sum(1 for sp in SPLITS if f >= sp); sect[j] = max(sect[j], v[k] * 3.6); vals.append(v[k] * 3.6)
        if not vals:
            continue
        rows.append([rep.names[c]] + [f"{x:.0f}" for x in sect] + [f"{max(vals):.0f}", f"{min(vals):.0f}", f"{sum(vals) / len(vals):.0f}"])
    return "<h2>Speed report (km/h)</h2>" + _table(["Driver", "S1 top", "S2 top", "S3 top", "S4 top", "Top", "Lowest", "Average"], rows)


REPORTS = [("Session summary", race_summary), ("Lap chart", lap_chart), ("Lap by lap", lap_by_lap), ("Speed report", speed_report)]


def _track_name(rep):
    return {"zandvoort": "Zandvoort", "nurburgring": "Nürburgring", "watglen": "Watkins Glen", "monza": "Monza",
            "spa": "Spa", "skidpad": "Skidpad"}.get(rep.h.get("track", ""), rep.h.get("track", ""))


def _table(heads, rows):
    th = "".join(f"<th style='text-align:left;padding:4px 10px;border-bottom:1px solid #3e5468'>{h}</th>" for h in heads)
    tr = "".join("<tr>" + "".join(f"<td style='padding:3px 10px'>{v}</td>" for v in r) + "</tr>" for r in rows)
    return f"<table cellspacing='0'>{'<tr>' + th + '</tr>'}{tr}</table>"


# ---------------------------------------------------------------------------------------------------------------
# widgets
# ---------------------------------------------------------------------------------------------------------------
class TrackMap(QWidget):
    """The racing lines of the selected laps over the track's reference line; wheel = zoom, drag = pan.
    `cursor_d` (metres along the lap) puts a marker on each lap where the graphs' cursor is."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 260); self.setMouseTracking(True)
        self.rep = None; self.laps = []; self.cursor_d = None; self.speed_diff = False
        self.zoom = 1.0; self.pan = QPointF(0, 0); self._drag = None

    def set_data(self, rep, laps):
        self.rep = rep; self.laps = laps; self.update()

    def _fit(self):
        pts = list(self.rep.refline) or [(x, z) for lp in self.laps for x, z in zip(lp.xs, lp.zs)]
        if not pts:
            return None
        xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        w = max(x1 - x0, 1.0); h = max(z1 - z0, 1.0)
        s = 0.92 * min(self.width() / w, self.height() / h) * self.zoom
        cx = (x0 + x1) / 2; cz = (z0 + z1) / 2
        # screen y grows downward and world z is the map's "north-south": z maps to -y, so the drawn circuit has
        # the handedness of the real one (a clockwise track stays clockwise; checked against Monza in S2)
        return lambda x, z: QPointF(self.width() / 2 + self.pan.x() + (x - cx) * s,
                                    self.height() / 2 + self.pan.y() - (z - cz) * s), s

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b1218"))
        if self.rep is None:
            return
        fit = self._fit()
        if fit is None:
            return
        f, s = fit
        if self.rep.refline:
            path = QPainterPath(); first = True
            for x, z in self.rep.refline + self.rep.refline[:1]:
                q = f(x, z)
                (path.moveTo if first else path.lineTo)(q); first = False
            p.setPen(QPen(QColor("#2a3742"), max(3.0, 14.0 * s), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(QColor("#3e5468"), 1.0)); p.drawPath(path)
            a = f(*self.rep.refline[0]); p.setPen(QPen(QColor("#ffffff"), 2.0)); p.drawEllipse(a, 4, 4)
        if self.speed_diff and len(self.laps) >= 2:          # GPL Replay Analyser's "Speedtrack"
            self._speed_track(p, f); return
        for i, lp in enumerate(self.laps):
            col = QColor(LAP_COLOURS[i % len(LAP_COLOURS)])
            path = QPainterPath(); first = True
            for x, z in zip(lp.xs, lp.zs):
                q = f(x, z); (path.moveTo if first else path.lineTo)(q); first = False
            p.setPen(QPen(col, 2.0)); p.drawPath(path)
            if self.cursor_d is not None and lp.dist:
                k = min(len(lp.dist) - 1, max(0, int(self.cursor_d / GRID_M)))
                fx = lp.ch["time"][k] + lp.t0             # the car's position at that distance, by time
                j = _nearest_time(self.rep.t, fx, lp.i0, lp.i1)
                c = self.rep.cars[lp.car]
                p.setBrush(QBrush(col)); p.setPen(QPen(QColor("#000000"), 1.0)); p.drawEllipse(f(c["x"][j], c["z"][j]), 5, 5)
                p.setBrush(Qt.BrushStyle.NoBrush)

    def _speed_track(self, p, f):
        """Lap 1's line coloured by the speed difference to lap 2 at the same distance: green where lap 1 is
        faster, red where lap 2 is, full colour at 20 km/h."""
        a, b = self.laps[0], self.laps[1]
        for k in range(1, len(a.xs)):
            g = min(len(a.dist) - 1, len(b.dist) - 1, max(0, int(a.ds[k] / GRID_M)))   # an unfinished lap is shorter
            dv = a.ch["kmh"][g] - b.ch["kmh"][g]; m = min(1.0, abs(dv) / 20.0)
            col = QColor.fromRgbF(0.25 + 0.75 * m, 0.35, 0.3) if dv < 0 else QColor.fromRgbF(0.3, 0.35 + 0.65 * m, 0.4)
            p.setPen(QPen(col, 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(f(a.xs[k - 1], a.zs[k - 1]), f(a.xs[k], a.zs[k]))
        p.setPen(QColor("#b9c7d3"))
        p.drawText(QPointF(10, 18), f"green: {a.driver} lap {a.num} faster   ·   red: {b.driver} lap {b.num} faster")

    def wheelEvent(self, e):
        self.zoom = min(40.0, max(0.5, self.zoom * (1.25 if e.angleDelta().y() > 0 else 0.8))); self.update()

    def mousePressEvent(self, e):
        self._drag = e.position()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons():
            self.pan += e.position() - self._drag; self._drag = e.position(); self.update()

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def mouseDoubleClickEvent(self, _e):
        self.zoom = 1.0; self.pan = QPointF(0, 0); self.update()


def _nearest_time(t, x, i0, i1):
    lo, hi = max(0, i0 - 1), min(len(t) - 1, i1)
    while lo < hi:
        m = (lo + hi) // 2
        if t[m] < x:
            lo = m + 1
        else:
            hi = m
    return lo


GRAPH_CHANNELS = [  # (key, title, unit, player-only) -- titles fit the 80 px label column
    ("kmh", "Speed", "km/h", False),
    ("delta", "Time diff", "s", False),
    ("throttle", "Throttle", "", True),
    ("brake", "Brake", "", True),
    ("steer", "Steering", "", True),
    ("gear", "Gear", "", True),
    ("rpm", "RPM", "", True),
    ("glat", "Lateral g", "g", False),
    ("glong", "Long. g", "g", False),
    ("lateral", "Road pos.", "m", False),
]


DEFAULT_CHANNELS = ("kmh", "delta", "throttle", "brake", "steer", "glat")


class Graphs(QWidget):
    """Stacked channel plots against lap distance; the mouse sets a shared cursor (read-outs + map marker).
    Wheel = zoom the distance axis around the mouse, drag = pan, double-click = whole lap."""
    cursor_moved = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 300); self.setMouseTracking(True)
        self.laps = []; self.chans = [c for c in GRAPH_CHANNELS]
        self.enabled = {c[0]: c[0] in DEFAULT_CHANNELS for c in GRAPH_CHANNELS}
        self.x0 = 0.0; self.x1 = 1.0; self.cursor = None; self._drag = None; self.L = 1.0

    def set_data(self, laps, laplen):
        self.laps = laps; self.L = laplen; self.x0, self.x1 = 0.0, laplen; self.update()

    def _rows(self):
        rows = []
        for key, title, unit, _po in self.chans:
            if not self.enabled.get(key, True):
                continue
            if key == "delta":
                if len(self.laps) >= 2:
                    rows.append((key, title, unit, [None] + [delta(self.laps[0], b) for b in self.laps[1:]]))
                continue
            data = [lp.ch.get(key) for lp in self.laps]
            if any(d is not None for d in data):
                rows.append((key, title, unit, data))
        return rows

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b1218"))
        rows = self._rows()
        if not rows or not self.laps:
            p.setPen(QColor("#8aa0b2")); p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Tick laps on the left to compare them.")
            return
        left, right, top, gap = 80, 12, 6, 6
        h = (self.height() - top - 18 - gap * (len(rows) - 1)) / len(rows)
        W = self.width() - left - right
        X = lambda d: left + (d - self.x0) / max(self.x1 - self.x0, 1e-6) * W
        small = QFont("Arial", 8); p.setFont(small)
        for r, (key, title, unit, data) in enumerate(rows):
            y0 = top + r * (h + gap)
            p.fillRect(QRectF(left, y0, W, h), QColor("#101a23"))
            vals = [v for d in data if d for v in d]
            if key in ("throttle", "brake"):
                lo, hi = 0.0, 1.0
            else:
                lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
                if key == "delta":
                    m = max(abs(lo), abs(hi), 0.05); lo, hi = -m, m
                if hi - lo < 1e-6:
                    hi = lo + 1.0
                pad = 0.06 * (hi - lo); lo -= pad; hi += pad
            Y = lambda v: y0 + h - (v - lo) / (hi - lo) * h
            p.setPen(QColor("#8aa0b2")); p.drawText(QRectF(4, y0, left - 8, h), Qt.AlignmentFlag.AlignVCenter, title.split(" (")[0])
            p.drawText(QRectF(left + 4, y0 + 1, 200, 12), Qt.AlignmentFlag.AlignLeft, f"{hi:.4g} {unit}".strip())
            p.drawText(QRectF(left + 4, y0 + h - 13, 200, 12), Qt.AlignmentFlag.AlignLeft, f"{lo:.4g}")
            if key == "delta":
                p.setPen(QPen(QColor("#3e5468"), 1.0, Qt.PenStyle.DashLine)); p.drawLine(QPointF(left, Y(0.0)), QPointF(left + W, Y(0.0)))
            p.save(); p.setClipRect(QRectF(left, y0, W, h))
            for i, d in enumerate(data):
                if not d:
                    continue
                lp = self.laps[i]
                path = QPainterPath(); first = True
                for dist, v in zip(lp.dist, d):
                    if dist < self.x0 - GRID_M or dist > self.x1 + GRID_M:
                        continue
                    q = QPointF(X(dist), Y(v)); (path.moveTo if first else path.lineTo)(q); first = False
                p.setPen(QPen(QColor(LAP_COLOURS[i % len(LAP_COLOURS)]), 1.4)); p.drawPath(path)
            p.restore()
            if self.cursor is not None:                                   # read-outs at the cursor
                k = int(self.cursor / GRID_M); txt = []
                for i, d in enumerate(data):
                    if d and 0 <= k < len(d):
                        txt.append((LAP_COLOURS[i % len(LAP_COLOURS)], f"{d[k]:.3g}"))
                xx = left + W - 6
                for col, t in reversed(txt):
                    p.setPen(QColor(col)); fm = p.fontMetrics(); wpx = fm.horizontalAdvance(t)
                    xx -= wpx; p.drawText(QPointF(xx, y0 + 12), t); xx -= 8
        if self.cursor is not None:
            p.setPen(QPen(QColor("#e8eef3"), 1.0)); xc = X(self.cursor)
            p.drawLine(QPointF(xc, top), QPointF(xc, self.height() - 18))
        p.setPen(QColor("#8aa0b2"))
        for i in range(6):                                                # distance axis
            d = self.x0 + i * (self.x1 - self.x0) / 5
            p.drawText(QPointF(X(d) - 14, self.height() - 4), f"{d:.0f} m")

    def _d_at(self, x):
        left, right = 80, 12
        W = self.width() - left - right
        return self.x0 + (x - left) / max(W, 1) * (self.x1 - self.x0)

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons():
            dd = self._d_at(self._drag) - self._d_at(e.position().x()); self._drag = e.position().x()
            self.x0 += dd; self.x1 += dd
        d = self._d_at(e.position().x())
        self.cursor = min(max(d, 0.0), self.L); self.cursor_moved.emit(self.cursor); self.update()

    def mousePressEvent(self, e):
        self._drag = e.position().x()

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def wheelEvent(self, e):
        d = self._d_at(e.position().x()); k = 0.8 if e.angleDelta().y() > 0 else 1.25
        self.x0 = d - (d - self.x0) * k; self.x1 = d + (self.x1 - d) * k
        if self.x1 - self.x0 > self.L:
            self.x0, self.x1 = 0.0, self.L
        self.update()

    def mouseDoubleClickEvent(self, _e):
        self.x0, self.x1 = 0.0, self.L; self.update()

    def leaveEvent(self, _e):
        self.cursor = None; self.cursor_moved.emit(None); self.update()


class TractionCircle(QWidget):
    """Lateral g (x) against longitudinal g (y) for the selected laps -- how much of the tyres' grip each lap used."""

    def __init__(self):
        super().__init__(); self.setMinimumSize(300, 300); self.laps = []

    def set_data(self, laps):
        self.laps = laps; self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b1218"))
        r = 0.45 * min(self.width(), self.height()); cx, cy = self.width() / 2, self.height() / 2; gmax = 2.0
        p.setPen(QPen(QColor("#2c3e50"), 1.0))
        for g in (0.5, 1.0, 1.5, 2.0):
            p.drawEllipse(QPointF(cx, cy), r * g / gmax, r * g / gmax)
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy)); p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        p.setPen(QColor("#8aa0b2"))
        for g in (1.0, 2.0):
            p.drawText(QPointF(cx + r * g / gmax + 3, cy - 3), f"{g:g} g")
        p.drawText(QPointF(cx - r, cy - r + 12), "braking ↓  ·  accelerating ↑  ·  left / right")
        for i, lp in enumerate(self.laps):
            col = QColor(LAP_COLOURS[i % len(LAP_COLOURS)]); col.setAlpha(150)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
            for gx, gy in zip(lp.ch["glat"], lp.ch["glong"]):
                p.drawEllipse(QPointF(cx + r * max(-gmax, min(gmax, gx)) / gmax, cy - r * max(-gmax, min(gmax, gy)) / gmax), 1.6, 1.6)


class AnalyserWindow(QDialog):
    """REPLAY-2 S2: the analyser for one replay. Laps on the left (tick up to five), then Track / Graphs / Times."""

    def __init__(self, jrt, parent=None):
        super().__init__(parent)
        self.rep = Replay(jrt)
        self.setWindowTitle("Analyse — " + os.path.basename(jrt)[:-4])
        self.resize(1280, 820)
        root = QHBoxLayout(self)
        split = QSplitter(); root.addWidget(split)
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        best = min((lp.time for lp in self.rep.laps), default=None)
        # REPLAY-3 (PO 2026-10-07: "There are never any replays on the left panel to choose from"): a lap cut short --
        # a crash, the session's end -- is listed too, untimed, and can be plotted as far as it got
        allaps = self.rep.laps + self.rep.unfinished
        nun = len(self.rep.unfinished)
        lv.addWidget(QLabel(f"<b>{len(self.rep.laps)} timed lap{'' if len(self.rep.laps) == 1 else 's'}</b>"
                            + (f" + {nun} unfinished" if nun else "") + f" · {self.rep.ncar} car(s) · best {fmt_time(best)}"))
        self.table = QTableWidget(len(allaps), 4)
        self.table.setHorizontalHeaderLabels(["", "Driver", "Lap", "Time"])
        self.table.verticalHeader().setVisible(False); self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rows = []
        for r, lp in enumerate(sorted(allaps, key=lambda lp: (lp.car, lp.num, lp.i0))):
            self.rows.append(lp)
            cb = QCheckBox(); cb.toggled.connect(self._changed)
            self.table.setCellWidget(r, 0, cb)
            self.table.setItem(r, 1, QTableWidgetItem(lp.driver + ("" if lp.clean else "  (off track)")))
            self.table.setItem(r, 2, QTableWidgetItem(str(lp.num)))
            it = QTableWidgetItem(fmt_time(lp.time) + ("  (from the start)" if lp.start else "") if lp.time is not None
                                  else _untimed(lp))
            if lp.time is None:
                it.setForeground(QColor("#8aa0b2"))
            elif best is not None and abs(lp.time - best) < 1e-9:
                it.setForeground(QColor("#7fd1ae"))
            self.table.setItem(r, 3, it)
        self.table.resizeColumnsToContents()
        lv.addWidget(self.table, 1)
        self.hint = QLabel("Tick up to five laps. Wheel zooms, drag pans, double-click resets."); self.hint.setObjectName("hint")
        self.hint.setWordWrap(True); lv.addWidget(self.hint)
        coach_b = QPushButton("Coaching (Claude)…")          # REPLAY-2 S4: optional, shows what it sends first
        coach_b.setToolTip("An optional analysis of your laps by Claude, with what to change; you see the summary before anything is sent")
        coach_b.clicked.connect(self._coach); lv.addWidget(coach_b)
        split.addWidget(left)
        self.tabs = QTabWidget(); split.addWidget(self.tabs)
        self.map = TrackMap(); self.graphs = Graphs()
        gbox = QWidget(); gv = QVBoxLayout(gbox); gv.setContentsMargins(0, 0, 0, 0)
        crow = QHBoxLayout(); crow.addWidget(QLabel("Show:"))
        self.chan_boxes = {}
        for key, title, _u, _po in GRAPH_CHANNELS:                 # the channels to plot, as the Analyser's graph menu
            cb = QCheckBox(title); cb.setChecked(self.graphs.enabled[key])
            cb.toggled.connect(lambda on, k=key: self._chan(k, on)); crow.addWidget(cb); self.chan_boxes[key] = cb
        crow.addStretch(1); gv.addLayout(crow); gv.addWidget(self.graphs, 1)
        both = QSplitter(Qt.Orientation.Vertical); both.addWidget(gbox); both.addWidget(self.map)
        both.setSizes([560, 260])
        self.tabs.addTab(both, "Graphs + map")
        mw = QWidget(); mv = QVBoxLayout(mw); mv.setContentsMargins(0, 0, 0, 0)
        self.speed_cb = QCheckBox("Colour by speed difference (first two laps)")
        self.speed_cb.toggled.connect(self._speed_mode); mv.addWidget(self.speed_cb)
        self.map_full = TrackMap(); mv.addWidget(self.map_full, 1)
        self.tabs.addTab(mw, "Track map")
        self.circle = TractionCircle(); self.tabs.addTab(self.circle, "Traction circle")
        self.times = QTableWidget(); self.times.verticalHeader().setVisible(False)
        self.tabs.addTab(self.times, "Split times")
        from PyQt6.QtWidgets import QComboBox, QTextBrowser
        rw = QWidget(); rv = QVBoxLayout(rw); rv.setContentsMargins(0, 0, 0, 0); rr = QHBoxLayout()
        self.rep_combo = QComboBox(); self.rep_combo.addItems([n for n, _f in REPORTS])
        self.rep_combo.currentIndexChanged.connect(self._report)
        exp = QPushButton("Export…"); exp.clicked.connect(self._export)
        rr.addWidget(QLabel("Report:")); rr.addWidget(self.rep_combo); rr.addStretch(1); rr.addWidget(exp); rv.addLayout(rr)
        self.report = QTextBrowser(); self.report.setObjectName("guide"); rv.addWidget(self.report, 1)
        self.tabs.addTab(rw, "Reports")
        self._report(0)
        split.setSizes([330, 950])
        self.graphs.cursor_moved.connect(self._cursor)
        self._fill_times()
        # preselect: the player's best lap and the fastest other lap, so the window opens on a comparison
        pre = []
        pl = [lp for lp in self.rep.laps if lp.car == 0]
        pu = [lp for lp in self.rep.unfinished if lp.car == 0]
        if pl:
            pre.append(min(pl, key=lambda lp: lp.time))
        elif pu:                                          # REPLAY-3: no lap completed -- open on the furthest attempt
            pre.append(max(pu, key=lambda lp: lp.reached))
        others = sorted((lp for lp in self.rep.laps if lp not in pre), key=lambda lp: lp.time) + \
            sorted((lp for lp in self.rep.unfinished if lp not in pre), key=lambda lp: -lp.reached)
        pre += others[: 2 - len(pre)]                     # always open on a comparison of two laps when there are two
        for r, lp in enumerate(self.rows):
            if lp in pre:
                self.table.cellWidget(r, 0).setChecked(True)
        self._changed()

    def selected(self):
        return [lp for r, lp in enumerate(self.rows) if self.table.cellWidget(r, 0).isChecked()]

    def _changed(self):
        sel = self.selected()
        if len(sel) > 5:                                    # GPL Replay Analyser's limit: untick the newest tick
            s = self.sender()
            if isinstance(s, QCheckBox):
                s.blockSignals(True); s.setChecked(False); s.blockSignals(False)
            sel = self.selected()
        for r, lp in enumerate(self.rows):                  # colour each ticked lap's name as its line
            k = sel.index(lp) if lp in sel else -1
            it = self.table.item(r, 1)
            it.setForeground(QColor(LAP_COLOURS[k]) if k >= 0 else QColor("#e8eef3"))
        self.graphs.set_data(sel, self.rep.laplen)
        self.map.set_data(self.rep, sel); self.map_full.set_data(self.rep, sel)
        if hasattr(self, "circle"):
            self.circle.set_data(sel)
        self.hint.setText(("No lap was completed: unfinished laps are drawn as far as they got. " if not self.rep.laps else "")
                          + ("Time difference is lap 2 minus lap 1 (above zero: lap 2 behind). " if len(sel) >= 2 else "")
                          + "Tick up to five laps. Wheel zooms, drag pans, double-click resets.")

    def _coach(self):
        import coach
        self._coach_dlg = coach.CoachDialog(self.rep, self); self._coach_dlg.show()

    def _speed_mode(self, on):
        self.map_full.speed_diff = on; self.map_full.update()

    def _report(self, i):
        name, fn = REPORTS[i]
        try:
            self.report.setHtml(fn(self.rep))
        except Exception as e:                              # a report must never take the window down
            self.report.setPlainText(f"{name}: could not be computed ({e})")

    def _export(self):
        from PyQt6.QtWidgets import QFileDialog
        base = os.path.splitext(self.rep.path)[0] + " " + self.rep_combo.currentText().lower().replace(" ", "_") + ".html"
        path, _ = QFileDialog.getSaveFileName(self, "Export report", base, "HTML (*.html);;Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.report.toPlainText() if path.endswith(".txt") else self.report.toHtml())

    def _chan(self, key, on):
        self.graphs.enabled[key] = on; self.graphs.update()

    def _cursor(self, d):
        self.map.cursor_d = d; self.map.update()

    def _fill_times(self):
        laps = sorted(self.rep.laps, key=lambda lp: (lp.car, lp.num))
        heads = ["Driver", "Lap", "Time", "S1 (0–25 %)", "S2 (25–50 %)", "S3 (50–75 %)", "S4 (75–100 %)"]
        rows = []
        bysec = {}
        for lp in laps:
            secs = sector_times(lp, self.rep.laplen)
            rows.append([lp.driver, str(lp.num), fmt_time(lp.time)] + [f"{s:.3f}" for s in secs])
            for j, s in enumerate(secs):
                b = bysec.setdefault(lp.driver, [math.inf] * 4); b[j] = min(b[j], s)
        for drv, b in bysec.items():                        # each driver's theoretical best: the sum of best sectors
            rows.append([drv, "best sectors", fmt_time(sum(b))] + [f"{s:.3f}" for s in b])
        self.times.setColumnCount(len(heads)); self.times.setRowCount(len(rows))
        self.times.setHorizontalHeaderLabels(heads)
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                it = QTableWidgetItem(v)
                if row[1] == "best sectors":
                    it.setForeground(QColor("#7fd1ae"))
                self.times.setItem(r, c, it)
        self.times.resizeColumnsToContents()
