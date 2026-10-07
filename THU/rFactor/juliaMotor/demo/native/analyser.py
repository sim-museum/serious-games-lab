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
G = 9.81


def jrt_path(jmr):
    return jmr[:-4] + ".jrt" if jmr.endswith(".jmr") else jmr


# ---------------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------------
class Lap:
    """One timed lap of one car, resampled onto a common distance grid (metres along the player's lap)."""
    __slots__ = ("car", "driver", "num", "t0", "t1", "time", "i0", "i1", "dist", "ch", "xs", "zs", "splits", "clean")

    def label(self):
        return f"{self.driver} — lap {self.num}  {fmt_time(self.time)}"


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
        self.laps = []
        for c in range(self.ncar):
            self.laps += self._laps_of(c)

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
        crossings = []                             # (frame index after the line, exact time, lap number started)
        for k in range(1, self.n):
            if lap[k] == lap[k - 1] + 1:
                a = L - d[k - 1]; b = d[k]
                f = a / (a + b) if (a + b) > 0 and 0 <= a < 0.5 * L and 0 <= b < 0.5 * L else 0.5
                crossings.append((k, t[k - 1] + f * (t[k] - t[k - 1]), int(lap[k])))
            elif lap[k] < lap[k - 1]:              # a session restart (R): no lap spans it
                crossings.append((k, None, None))
        laps = []
        for (k0, ta, la), (k1, tb, _lb) in zip(crossings, crossings[1:]):
            if ta is None or tb is None or k1 - k0 < 10:
                continue
            lp = Lap()
            lp.car = c; lp.driver = self.names[c] if c < len(self.names) else f"car {c}"; lp.num = la
            lp.t0 = ta; lp.t1 = tb; lp.time = tb - ta; lp.i0 = k0; lp.i1 = k1
            self._resample(lp, car)
            laps.append(lp)
        return laps

    def _resample(self, lp, car):
        """Channels against distance on a GRID_M grid of the PLAYER's lap length (AI distance is rescaled)."""
        L = car["L"]; scale = self.laplen / L if L > 0 else 1.0
        idx = list(range(lp.i0 - 1, lp.i1 + 1))
        ds = []; prev = -1e9
        for k in idx:                              # distance from this lap's line, monotone (a spin cannot rewind it)
            dk = car["dist"][k]
            if k < lp.i0:
                dk -= L                            # the frame before the line, just short of it
            dk = max(dk * scale, prev); ds.append(dk); prev = dk
        ts = [self.t[k] - lp.t0 for k in idx]
        grid = [i * GRID_M for i in range(int(self.laplen // GRID_M) + 1)]
        names = [n for n in ("speed", "throttle", "brake", "steer", "gear", "rpm", "lateral", "lane", "glong", "glat")
                 if n in car]
        cols = {n: [car[n][k] for k in idx] for n in names}
        cols["time"] = ts
        lp.dist = grid
        lp.ch = {n: _interp(ds, cols[n], grid) for n in cols}
        if "speed" in lp.ch:
            lp.ch["kmh"] = [v * 3.6 for v in lp.ch["speed"]]
        if "lane" in lp.ch and "lateral" not in lp.ch:
            lp.ch["lateral"] = lp.ch["lane"]
        lp.xs = [car["x"][k] for k in idx]; lp.zs = [car["z"][k] for k in idx]
        lp.splits = [_interp(ds, ts, [s * self.laplen])[0] for s in SPLITS]
        lp.clean = ("ontrack" not in car) or all(car["ontrack"][k] > 0.5 for k in idx)


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
# widgets
# ---------------------------------------------------------------------------------------------------------------
class TrackMap(QWidget):
    """The racing lines of the selected laps over the track's reference line; wheel = zoom, drag = pan.
    `cursor_d` (metres along the lap) puts a marker on each lap where the graphs' cursor is."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 260); self.setMouseTracking(True)
        self.rep = None; self.laps = []; self.cursor_d = None
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


class Graphs(QWidget):
    """Stacked channel plots against lap distance; the mouse sets a shared cursor (read-outs + map marker).
    Wheel = zoom the distance axis around the mouse, drag = pan, double-click = whole lap."""
    cursor_moved = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(480, 300); self.setMouseTracking(True)
        self.laps = []; self.chans = [c for c in GRAPH_CHANNELS]; self.enabled = {c[0]: True for c in GRAPH_CHANNELS}
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
        lv.addWidget(QLabel(f"<b>{len(self.rep.laps)} timed laps</b> · {self.rep.ncar} car(s) · "
                            f"best {fmt_time(best)}"))
        self.table = QTableWidget(len(self.rep.laps), 4)
        self.table.setHorizontalHeaderLabels(["", "Driver", "Lap", "Time"])
        self.table.verticalHeader().setVisible(False); self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        order = sorted(range(len(self.rep.laps)), key=lambda i: (self.rep.laps[i].car, self.rep.laps[i].num))
        self.rows = []
        for r, i in enumerate(order):
            lp = self.rep.laps[i]; self.rows.append(lp)
            cb = QCheckBox(); cb.toggled.connect(self._changed)
            self.table.setCellWidget(r, 0, cb)
            self.table.setItem(r, 1, QTableWidgetItem(lp.driver + ("" if lp.clean else "  (off track)")))
            self.table.setItem(r, 2, QTableWidgetItem(str(lp.num)))
            it = QTableWidgetItem(fmt_time(lp.time))
            if best is not None and abs(lp.time - best) < 1e-9:
                it.setForeground(QColor("#7fd1ae"))
            self.table.setItem(r, 3, it)
        self.table.resizeColumnsToContents()
        lv.addWidget(self.table, 1)
        self.hint = QLabel("Tick up to five laps. Wheel zooms, drag pans, double-click resets."); self.hint.setObjectName("hint")
        self.hint.setWordWrap(True); lv.addWidget(self.hint)
        split.addWidget(left)
        self.tabs = QTabWidget(); split.addWidget(self.tabs)
        self.map = TrackMap(); self.graphs = Graphs()
        both = QSplitter(Qt.Orientation.Vertical); both.addWidget(self.graphs); both.addWidget(self.map)
        both.setSizes([560, 260])
        self.tabs.addTab(both, "Graphs + map")
        self.map_full = TrackMap(); self.tabs.addTab(self.map_full, "Track map")
        self.times = QTableWidget(); self.times.verticalHeader().setVisible(False)
        self.tabs.addTab(self.times, "Split times")
        split.setSizes([330, 950])
        self.graphs.cursor_moved.connect(self._cursor)
        self._fill_times()
        # preselect: the player's best lap and the fastest other lap, so the window opens on a comparison
        pre = []
        pl = [lp for lp in self.rep.laps if lp.car == 0]
        if pl:
            pre.append(min(pl, key=lambda lp: lp.time))
        others = sorted((lp for lp in self.rep.laps if lp not in pre), key=lambda lp: lp.time)
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
        self.hint.setText(("Time difference is lap 2 minus lap 1 (above zero: lap 2 behind). " if len(sel) >= 2 else "")
                          + "Tick up to five laps. Wheel zooms, drag pans, double-click resets.")

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
