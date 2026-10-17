"""SETUPMODEL-1: the launcher's GARAGE tab -- iRacing's Lotus 49 setup page in julia.

PO 2026-10-15: "julia's Setup tab then adjusts the car via iRacing's own list of settings"; the garage's derived numbers
(corner weights, ride heights, shock deflections, cross weight, static camber/toe, gear speeds) follow the knobs the way
iRacing's do. Pages, names, steps and limits are iRacing's (JuliaMotorMTK/src/garage_lotus49.toml); a dagger marks a
knob whose limits the PO's capture has not shown yet (provisional). The numbers are the chosen session's own plus the
garage model's change (garage.py, the mirror of JuliaMotorMTK/src/garage.jl): "Reset" is the session to the digit.

On a launch with a modified garage, the launcher writes the knobs to a garage file and hands it to the sim (JM_GARAGE);
the sim re-solves them with the Julia model before the car is built.
"""
import copy
import glob
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
                             QInputDialog, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget)

import garage as gm

CORNERS = ("LEFT FRONT", "RIGHT FRONT", "LEFT REAR", "RIGHT REAR")
SESSION_KEYS = ("default", "ww103")          # the Race tab's car setup combo, in its order
PROVISIONAL_TIP = ("† Provisional range: the PO's iRacing capture (261017) shows this knob's values but not yet its "
                   "limits; SETUPMODEL-1 Part C will settle them.")


class KnobSpin(QDoubleSpinBox):
    """iRacing's knob: steps on the knob's own lattice (e.g. 1/64 inch) at full precision, shows the garage's digits."""
    def __init__(self, show_decimals, lattice=None):
        super().__init__()
        self.show_decimals = show_decimals
        self.lattice = lattice
        self.setDecimals(6)

    def textFromValue(self, v):
        return f"{v:.{self.show_decimals}f}"

    def valueFromText(self, text):
        t = text.replace(self.suffix(), "").replace(self.prefix(), "").strip()
        try:
            return float(t)
        except ValueError:
            return self.value()

    def stepBy(self, steps):
        v = self.value() + steps * self.singleStep()
        if self.lattice:
            v = round(v / self.lattice) * self.lattice
        self.setValue(min(max(v, self.minimum()), self.maximum()))


def garage_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "juliaRacer", "garage")
    os.makedirs(d, exist_ok=True)
    return d


def spec(key):
    return next(k for k in gm.KNOB_SPECS if k["key"] == key)


def same_knobs(a, b):
    for f in gm.KNOB_FIELDS:
        x, y = a[f], b[f]
        if isinstance(x, (list, tuple)):
            if len(x) != len(y) or any(abs(float(p) - float(q)) > 1e-6 for p, q in zip(x, y)):
                return False
        elif isinstance(x, str) or isinstance(y, str):
            if str(x) != str(y):
                return False
        elif abs(float(x) - float(y)) > 1e-6:
            return False
    return True


class GarageTab(QWidget):
    def __init__(self, get_session_index, parent=None):
        super().__init__(parent)
        self._session_index = get_session_index       # -> 0 default, 1 ww103 (the Race tab's combo)
        self._sessions = gm.sessions()
        self._busy = False
        self.widgets = {}                             # (field, corner|None) -> widget
        self.derived_labels = {}
        self._shown = {}                              # camber/toe: the value each display spin was last set to
        self._build()
        self.load_session(keep_saved=True)

    # ---- state ---------------------------------------------------------------------------------------------------
    @property
    def session_key(self):
        return SESSION_KEYS[max(0, min(self._session_index(), len(SESSION_KEYS) - 1))]

    @property
    def session(self):
        return self._sessions[self.session_key]

    def current_path(self):
        return os.path.join(garage_dir(), f"current_{self.session_key}.toml")

    def is_modified(self):
        return not same_knobs(self.K, self.session["knobs"])

    def load_session(self, keep_saved=False):
        """Start from the chosen session; keep_saved: resume the last garage made on it (if any)."""
        self.K = copy.deepcopy(self.session["knobs"])
        p = self.current_path()
        if keep_saved and os.path.exists(p):
            try:
                base, K = gm.read_garage_file(p, self.K)
                if base == self.session_key:
                    self.K = K
            except Exception:
                pass
        self.base_lbl.setText(f"Base setup: <b>{'iRacing default' if self.session_key == 'default' else 'WW103 fast loose'}"
                              f"</b> &nbsp;<span style='color:gray'>({self.session['source']})</span>")
        self.refresh()

    def save_current(self):
        gm.write_garage_file(self.current_path(), self.K, base=self.session_key)

    def garage_file_for_launch(self):
        """Path for JM_GARAGE, or None when the garage is off or untouched (the sim then uses the session as is)."""
        if not self.use.isChecked() or not self.is_modified():
            return None
        self.save_current()
        return self.current_path()

    # ---- building ------------------------------------------------------------------------------------------------
    def _spin(self, key, axle=None, decimals=1, display=False):
        s = spec(key)
        lattice = s.get("step") if s.get("unit") == "mm" and abs(s.get("step", 0) - 0.396875) < 1e-9 else None
        w = KnobSpin(decimals, lattice)
        suf = s.get("unit", "")
        w.setSuffix(f" {suf}" if suf else "")
        if axle is not None and "min_front" in s:
            lo, hi = (s["min_front"], s["max_front"]) if axle == 0 else (s["min_rear"], s["max_rear"])
        else:
            lo, hi = s.get("min", -1e9), s.get("max", 1e9)
        if display:            # shows the solved value, which travel and roll can carry past the knob's own range
            lo, hi = lo - 3.0, hi + 3.0
        w.setRange(lo, hi)
        w.setSingleStep(s.get("step", 1.0))
        w.setKeyboardTracking(False)
        if not s.get("known", True):
            w.setToolTip(PROVISIONAL_TIP)
        return w

    def _combo(self, key):
        s = spec(key)
        w = QComboBox()
        w.addItems(s["options"])
        if not s.get("known", True):
            w.setToolTip(PROVISIONAL_TIP)
        return w

    def _label(self, key, text=None):
        s = spec(key)
        t = (text or s["label"]) + ("†" if not s.get("known", True) else "") + ":"
        l = QLabel(t)
        if not s.get("known", True):
            l.setToolTip(PROVISIONAL_TIP)
        return l

    def _build(self):
        top = QVBoxLayout(self)
        head = QHBoxLayout()
        self.base_lbl = QLabel()
        head.addWidget(self.base_lbl, 1)
        self.use = QCheckBox("Use this garage for the next race")
        self.use.setChecked(True)
        self.use.setToolTip("Off: race the base setup exactly as the session has it, whatever is set here.")
        head.addWidget(self.use)
        top.addLayout(head)
        btns = QHBoxLayout()
        self.reset_b = QPushButton("Reset to the session")
        self.reset_b.setToolTip("Every knob back to the base session's value (the .ibt's own numbers).")
        self.reset_b.clicked.connect(self.reset)
        self.save_b = QPushButton("Save as…")
        self.save_b.clicked.connect(self.save_as)
        self.load_b = QPushButton("Load…")
        self.load_b.clicked.connect(self.load_from)
        for b in (self.reset_b, self.save_b, self.load_b):
            btns.addWidget(b)
        btns.addStretch(1)
        self.status = QLabel()
        btns.addWidget(self.status)
        top.addLayout(btns)

        pages = QTabWidget()
        self.pages = pages
        top.addWidget(pages, 1)
        pages.addTab(self._tires_page(), "TIRES")
        pages.addTab(self._chassis_page(), "CHASSIS")
        pages.addTab(self._drivetrain_page(), "DRIVETRAIN")
        note = QLabel("Derived numbers (grey) are iRacing's for the base session plus the garage model's change for the "
                      "knobs you turn. † = range provisional.")
        note.setStyleSheet("color: gray")
        note.setWordWrap(True)
        top.addWidget(note)

    def _derived(self, key):
        l = QLabel("—")
        l.setStyleSheet("color: #666; font-family: monospace")
        self.derived_labels[key] = l
        return l

    def _tires_page(self):
        w = QWidget()
        g = QGridLayout(w)
        for i, name in enumerate(CORNERS):
            box = QGroupBox(name)
            bg = QGridLayout(box)
            bg.addWidget(self._label("pressure"), 0, 0)
            sp = self._spin("pressure", decimals=0)
            sp.valueChanged.connect(lambda v, i=i: self._set_corner("pressure", i, v))
            self.widgets[("pressure", i)] = sp
            bg.addWidget(sp, 0, 1)
            g.addWidget(box, i // 2, i % 2)
        g.setRowStretch(2, 1)
        return w

    def _chassis_page(self):
        w = QWidget()
        g = QGridLayout(w)
        front = QGroupBox("FRONT")
        fg = QGridLayout(front)
        r = 0
        for key in ("farb_arm", "farb_dia"):
            fg.addWidget(self._label(key), r, 0)
            cb = self._combo(key)
            cb.currentIndexChanged.connect(lambda idx, key=key: self._set_option(key, idx))
            self.widgets[(key, None)] = cb
            fg.addWidget(cb, r, 1)
            r += 1
        fg.addWidget(self._label("brake_bias"), r, 0)
        sp = self._spin("brake_bias", decimals=2)
        sp.valueChanged.connect(lambda v: self._set_scalar("brake_bias", v))
        self.widgets[("brake_bias", None)] = sp
        fg.addWidget(sp, r, 1)
        r += 1
        fg.addWidget(self._label("toe_front"), r, 0)
        sp = self._spin("toe_front", decimals=1, display=True)
        sp.valueChanged.connect(lambda v: self._set_display("toe_front", None, v))
        self.widgets[("toe_front", None)] = sp
        fg.addWidget(sp, r, 1)
        r += 1
        fg.addWidget(self._label("steering_ratio"), r, 0)
        cb = self._combo("steering_ratio")
        cb.currentIndexChanged.connect(lambda idx: self._set_option("steering_ratio", idx))
        self.widgets[("steering_ratio", None)] = cb
        fg.addWidget(cb, r, 1)
        r += 1
        fg.addWidget(QLabel("Cross weight:"), r, 0)
        fg.addWidget(self._derived("cross"), r, 1)
        g.addWidget(front, 0, 0, 1, 2)

        for i, name in enumerate(CORNERS):
            axle = 0 if i < 2 else 1
            box = QGroupBox(name)
            bg = QGridLayout(box)
            rr = 0
            for dk, dl in (("cw", "Corner weight"), ("rh", "Ride height"), ("shock", "Shock deflection")):
                bg.addWidget(QLabel(dl + ":"), rr, 0)
                bg.addWidget(self._derived((dk, i)), rr, 1)
                rr += 1
            for key, dec in (("perch", 1), ("spring", 0), ("packer", 1), ("bump", 0), ("rebound", 0)):
                bg.addWidget(self._label(key), rr, 0)
                sp = self._spin(key, axle=axle, decimals=dec)
                if key in ("bump", "rebound"):
                    sp.setPrefix("+")
                sp.valueChanged.connect(lambda v, key=key, i=i: self._set_corner(key, i, v))
                self.widgets[(key, i)] = sp
                bg.addWidget(sp, rr, 1)
                rr += 1
            bg.addWidget(self._label("camber"), rr, 0)
            sp = self._spin("camber", decimals=1, display=True)
            sp.valueChanged.connect(lambda v, i=i: self._set_display("camber", i, v))
            self.widgets[("camber", i)] = sp
            bg.addWidget(sp, rr, 1)
            g.addWidget(box, 1 + i // 2, i % 2)

        rear = QGroupBox("REAR")
        rg = QGridLayout(rear)
        rg.addWidget(self._label("fuel"), 0, 0)
        sp = self._spin("fuel", decimals=1)
        sp.valueChanged.connect(lambda v: self._set_scalar("fuel", v))
        self.widgets[("fuel", None)] = sp
        rg.addWidget(sp, 0, 1)
        for r, key in enumerate(("rarb_dia", "rarb_arm"), start=1):
            rg.addWidget(self._label(key), r, 0)
            cb = self._combo(key)
            cb.currentIndexChanged.connect(lambda idx, key=key: self._set_option(key, idx))
            self.widgets[(key, None)] = cb
            rg.addWidget(cb, r, 1)
        rg.addWidget(self._label("toe_rear"), 3, 0)
        sp = self._spin("toe_rear", decimals=1)
        sp.valueChanged.connect(lambda v: self._set_scalar("toe_rear", v))
        self.widgets[("toe_rear", None)] = sp
        rg.addWidget(sp, 3, 1)
        g.addWidget(rear, 3, 0, 1, 2)
        return w

    def _drivetrain_page(self):
        w = QWidget()
        g = QGridLayout(w)
        tr = QGroupBox("Transmission")
        tg = QGridLayout(tr)
        tg.addWidget(self._label("final_drive"), 0, 0)
        cb = self._combo("final_drive")
        cb.currentIndexChanged.connect(lambda idx: self._set_option("final_drive", idx))
        self.widgets[("final_drive", None)] = cb
        tg.addWidget(cb, 0, 1)
        for n in range(1, 6):
            key = f"gear{n}"
            tg.addWidget(self._label(key), n, 0)
            cb = self._combo(key)
            cb.currentIndexChanged.connect(lambda idx, n=n: self._set_gear(n, idx))
            self.widgets[(key, None)] = cb
            tg.addWidget(cb, n, 1)
            tg.addWidget(self._derived(("kmh", n - 1)), n, 2)
        g.addWidget(tr, 0, 0)
        df = QGroupBox("Differential")
        dg = QGridLayout(df)
        for r, (key, dec) in enumerate((("diff_plates", 0), ("diff_preload", 0), ("diff_drive", 0), ("diff_coast", 0))):
            dg.addWidget(self._label(key), r, 0)
            sp = self._spin(key, decimals=dec)
            sp.valueChanged.connect(lambda v, key=key: self._set_scalar(key, v))
            self.widgets[(key, None)] = sp
            dg.addWidget(sp, r, 1)
        g.addWidget(df, 1, 0)
        g.setRowStretch(2, 1)
        return w

    # ---- edits ---------------------------------------------------------------------------------------------------
    def _edit(self, fn):
        if self._busy:
            return
        fn()
        self.save_current()
        self.refresh()

    def _set_corner(self, key, i, v):
        def f():
            vals = list(self.K[key])
            v2 = int(round(v)) if key in ("bump", "rebound") else float(v)
            sv = self.session["knobs"][key][i]
            if not isinstance(v2, int) and abs(v2 - sv) < 0.03:     # back on the session's own (displayed) value
                v2 = float(sv)
            vals[i] = v2
            self.K[key] = vals
        self._edit(f)

    def _set_scalar(self, key, v):
        self._edit(lambda: self.K.__setitem__(key, int(round(v)) if key == "diff_plates" else float(v)))

    def _set_option(self, key, idx):
        s = spec(key)

        def f():
            if "values" in s:
                self.K[key] = float(s["values"][idx])
            else:
                self.K[key] = s["options"][idx]
        self._edit(f)

    def _set_gear(self, n, idx):
        def f():
            gears = list(self.K["gears"])
            gears[n - 1] = float(spec(f"gear{n}")["values"][idx])
            self.K["gears"] = gears
        self._edit(f)

    def _set_display(self, key, i, v):
        """Camber and toe show iRacing's DISPLAYED static value; a click moves the knob by the same step."""
        def f():
            dv = float(v) - self._shown[(key, i)]          # one click of the shown value = the same move of the knob
            if key == "camber":
                vals = list(self.K["camber"])
                vals[i] += dv
                self.K["camber"] = vals
            else:
                self.K["toe_front"] += dv
        self._edit(f)

    def reset(self):
        self.K = copy.deepcopy(self.session["knobs"])
        self.save_current()
        self.refresh()

    def save_as(self):
        name, ok = QInputDialog.getText(self, "Save garage setup", "Name:")
        if not ok or not name.strip():
            return
        fn = os.path.join(garage_dir(), "".join(c if c.isalnum() or c in "-_ " else "_" for c in name.strip()) + ".toml")
        gm.write_garage_file(fn, self.K, base=self.session_key)
        self.status.setText(f"saved {os.path.basename(fn)}")

    def load_from(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Load garage setup", garage_dir(), "Garage setups (*.toml)")
        if not fn:
            return
        try:
            base, K = gm.read_garage_file(fn, self.session["knobs"])
        except Exception as e:
            QMessageBox.warning(self, "Garage", f"Could not read {fn}: {e}")
            return
        if base != self.session_key:
            QMessageBox.information(self, "Garage", f"That setup was made on the '{base}' base; it is applied to "
                                                    f"'{self.session_key}' as saved.")
        self.K = K
        self.save_current()
        self.refresh()

    # ---- display -------------------------------------------------------------------------------------------------
    def refresh(self):
        self.D = gm.derived(self.K, self.session)
        D = self.D
        self._busy = True
        try:
            for (key, i), w in self.widgets.items():
                if key.startswith("gear"):
                    n = int(key[4:])
                    vals = spec(key)["values"]
                    g = self.K["gears"][n - 1]
                    j = min(range(len(vals)), key=lambda k: abs(vals[k] - g))
                    w.setCurrentIndex(j)
                elif isinstance(w, QComboBox):
                    s = spec(key)
                    cur = self.K[key]
                    if "values" in s:
                        j = min(range(len(s["values"])), key=lambda k: abs(s["values"][k] - float(cur)))
                    else:
                        j = s["options"].index(str(cur)) if str(cur) in s["options"] else 0
                    w.setCurrentIndex(j)
                elif key == "camber":
                    w.setValue(D["camber"][i]); self._shown[(key, i)] = D["camber"][i]
                elif key == "toe_front":
                    w.setValue(D["toe_front"]); self._shown[(key, i)] = D["toe_front"]
                elif i is None:
                    w.setValue(float(self.K[key]))
                else:
                    w.setValue(float(self.K[key][i]))
        finally:
            self._busy = False
        for i in range(4):
            self.derived_labels[("cw", i)].setText(f"{D['cw'][i]:.0f} N")
            loose = D["shock"][i] > D["shock_max"][i] - 0.05
            self.derived_labels[("rh", i)].setText(f"{D['rh'][i]:.1f} mm")
            self.derived_labels[("shock", i)].setText(f"{D['shock'][i]:.1f} mm of {D['shock_max'][i]:.1f} mm"
                                                      + ("  (bottomed)" if loose else ""))
        self.derived_labels["cross"].setText(f"{D['cross']:.1f}%")
        for n, v in enumerate(D["gears_kmh"]):
            self.derived_labels[("kmh", n)].setText(f"{v:.1f} Km/h")
        mod = self.is_modified()
        self.status.setText(("MODIFIED from the session" if mod else "= the session") +
                            ("" if D["ok"] else "  (solve did not converge)"))
        self.status.setStyleSheet("color: #b36b00" if mod else "color: gray")
