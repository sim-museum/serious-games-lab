"""GPLSETUP-1: import a GPL Lotus 49 setup (.kj1) into julia's garage (iRacing's knobs).

PO 2026-10-17: "add functionality to import a GPL lotus 49 setup and translate it into a julia setup".

The .kj1 layout is gpl.exe's own serialiser ('PGTS' v3; JuliaMotorMTK/tools/gplsetup_decode.jl has the decomp notes).
The translation follows WWSETUP-1's rules (PRODUCT_BACKLOG.md "WWSETUP-1"), the ones the PO's WW103 was carried to
iRacing with:
  * PHYSICAL where both games expose the same quantity -- tyre pressure (psi -> kPa), camber (deg), toe (in -> mm),
    brake bias (%), fuel (US gal -> L), diff ramp angles (deg) and clutch plates, the overall gearing (each gear's
    ratio x final, matched to iRacing's ratio lists), and the springs: GPL's WHEEL rate through the garage's measured
    spring-to-wheel ratios (front 0.81, rear 0.669) to an iRacing SPRING rate;
  * RANGE POSITION where the units differ -- damper clicks (GPL 1..5 -> iRacing 0..12) and the anti-roll bars (GPL's bar
    rate against the median of the Lotus setups on disk -> the iRacing bar whose garage rate stands the same way against
    the default car's).
Everything is clamped to iRacing's ranges (garage_lotus49.toml), and each clamp is reported, so a GPL setup outside
iRacing's limits says what it lost.
"""
import math
import struct

import garage as gm

LBIN = 0.175127                     # lb/in -> N/mm
MRK = (0.809881, 0.668786)          # garage: spring travel per wheel travel (front, rear) -- wheel rate = spring x MRk^2
# Medians over the GPL Lotus setups on this PC (computed 2026-10-17, see PRODUCT_BACKLOG GPLSETUP-1 S1): what a
# "typical" GPL bar is, so a bar's range position can be carried over.
GPL_ARB_MEDIAN = (None, None)       # filled below from the measured medians


def decode_kj1(data: bytes):
    if data[:4] != b"PGTS" or len(data) < 0x104:
        raise ValueError("not a GPL setup file (no 'PGTS' header)")
    f = lambda o, n: list(struct.unpack_from("<%df" % n, data, o))
    i = lambda o, n: list(struct.unpack_from("<%di" % n, data, o))
    g = f(0x0C, 9)                                   # R, N, 1st..6th, final drive
    return dict(gears=g[2:8], final=g[8], ramp=f(0x54, 2), psi=f(0x5C, 4), rate=f(0x6C, 4), bump=i(0x7C, 4),
                rebound=i(0x8C, 4), camber=f(0x9C, 4), rubber=f(0xCC, 4), toe=f(0xDC, 2), arb=f(0xE4, 2),
                ride=[min(max(x, 2.5), 5.0) for x in f(0xEC, 2)], clutches=i(0xF4, 1)[0], fuel_gal=f(0xF8, 1)[0],
                steer=f(0xFC, 1)[0], bias=i(0x100, 1)[0])


def _spec(key):
    return next(k for k in gm.KNOB_SPECS if k["key"] == key)


def _clamp_step(v, lo, hi, step, base=0.0):
    c = min(max(v, lo), hi)
    return base + round((c - base) / step) * step, (c != v)


def translate(gpl, base_knobs, arb_median=None):
    """GPL setup (decode_kj1) -> (garage knobs, notes). `base_knobs` supplies every knob GPL has no equivalent for."""
    K = {k: (list(v) if isinstance(v, list) else v) for k, v in base_knobs.items()}
    notes = []

    def note_clamp(name, clamped, want, got, unit=""):
        if clamped:
            notes.append(f"{name}: GPL's {want:g}{unit} is outside iRacing's range -> {got:g}{unit}")

    # tyre pressure (psi -> kPa), the garage's step
    sp = _spec("pressure")
    pr = []
    for i, psi in enumerate(gpl["psi"]):
        v, c = _clamp_step(psi * 6.895, sp["min"], sp["max"], sp["step"], sp["min"])
        note_clamp(f"pressure {('LF', 'RF', 'LR', 'RR')[i]}", c, psi * 6.895, v, " kPa")
        pr.append(round(v, 1))
    K["pressure"] = pr
    # springs: GPL wheel rate -> iRacing spring rate through the measured ratios
    ss = _spec("spring")
    springs = []
    for i, r in enumerate(gpl["rate"]):
        a = 0 if i < 2 else 1
        want = r * LBIN / MRK[a] ** 2
        lo, hi = (ss["min_front"], ss["max_front"]) if a == 0 else (ss["min_rear"], ss["max_rear"])
        v, c = _clamp_step(want, lo, hi, ss["step"])
        note_clamp(f"spring {('LF', 'RF', 'LR', 'RR')[i]}", c, round(want, 1), v, " N/mm")
        springs.append(float(v))
    K["spring"] = springs
    # dampers: GPL clicks 1..5 -> iRacing 0..12 by range position
    K["bump"] = [int(round((min(max(c, 1), 5) - 1) / 4 * 12)) for c in gpl["bump"]]
    K["rebound"] = [int(round((min(max(c, 1), 5) - 1) / 4 * 12)) for c in gpl["rebound"]]
    # camber (the displayed static camber), toe (in -> mm)
    cs = _spec("camber")
    K["camber"] = [round(min(max(c, cs["min"]), cs["max"]), 1) for c in gpl["camber"]]
    for key, v in (("toe_front", gpl["toe"][0] * 25.4), ("toe_rear", gpl["toe"][1] * 25.4)):
        s = _spec(key)
        got, c = _clamp_step(v, s["min"], s["max"], s["step"])
        note_clamp(key.replace("_", " "), c, round(v, 1), got, " mm")
        K[key] = float(got)
    # bias, fuel
    sb = _spec("brake_bias")
    K["brake_bias"], c = _clamp_step(float(gpl["bias"]), sb["min"], sb["max"], sb["step"])
    note_clamp("brake bias", c, float(gpl["bias"]), K["brake_bias"], " %")
    sf = _spec("fuel")
    fuel = gpl["fuel_gal"] * 3.785
    K["fuel"], c = _clamp_step(fuel, sf["min"], sf["max"], sf["step"])
    K["fuel"] = round(K["fuel"], 1)
    note_clamp("fuel", c, round(fuel, 1), K["fuel"], " L")
    # diff: ramps (power, coast) and plates
    for key, v in (("diff_drive", gpl["ramp"][0]), ("diff_coast", gpl["ramp"][1])):
        s = _spec(key)
        got, c = _clamp_step(v, s["min"], s["max"], s["step"], s["min"])
        note_clamp(key.replace("_", " "), c, v, got, " deg")
        K[key] = float(got)
    s = _spec("diff_plates")
    K["diff_plates"], c = _clamp_step(gpl["clutches"], s["min"], s["max"], 1)
    K["diff_plates"] = int(K["diff_plates"])
    note_clamp("clutch plates", c, gpl["clutches"], K["diff_plates"])
    # gearing: the final + gears from iRacing's lists closest to GPL's OVERALL ratios (log error)
    finals = _spec("final_drive")["values"]
    glists = [_spec(f"gear{n}")["values"] for n in range(1, 6)]
    want = [g * gpl["final"] for g in gpl["gears"][:5]]
    best = None
    for fd in finals:
        pick = [min(gl, key=lambda r: abs(math.log(r * fd / w))) for gl, w in zip(glists, want)]
        err = sum(abs(math.log(r * fd / w)) for r, w in zip(pick, want))
        if best is None or err < best[0]:
            best = (err, fd, pick)
    K["final_drive"], K["gears"] = float(best[1]), [float(r) for r in best[2]]
    kmh_g = [gm.PARAMS["rpm_r"] * 2 * math.pi / 60 / w * 3.6 for w in want]
    kmh_i = gm.gear_speeds_kmh(K)
    notes.append("gears (top speed, GPL -> iRacing's nearest ratios): " +
                 ", ".join(f"{a:.0f}->{b:.0f}" for a, b in zip(kmh_g, kmh_i)) + " km/h")
    # anti-roll bars: GPL's rate against the GPL median -> the iRacing bar standing the same way against the default's
    med = arb_median or GPL_ARB_MEDIAN
    if med[0] and med[1]:
        for axle, (dk, ak) in enumerate((("farb_dia", "farb_arm"), ("rarb_dia", "rarb_arm"))):
            rel = gpl["arb"][axle] / med[axle]
            ref = gm.arb_rate(gm.PARAMS, axle, *gm.ARB_REF[axle][:1], str(gm.ARB_REF[axle][1]))
            target = ref * rel
            opts = [(d, a) for d in _spec(dk)["values"] for a in _spec(ak)["options"]]
            d, a = min(opts, key=lambda o: abs(gm.arb_rate(gm.PARAMS, axle, o[0], o[1]) - target))
            K[dk], K[ak] = float(d), a
            notes.append(f"{('front', 'rear')[axle]} bar: GPL {gpl['arb'][axle]:g} lb/in = {rel:.2f}x the GPL median -> "
                         f"{d:g}\" arms {a} ({gm.arb_rate(gm.PARAMS, axle, d, a) / ref:.2f}x the default's)")
    if abs(gpl["steer"] - K["steering_ratio"]) > 0.5:
        notes.append(f"steering: GPL {gpl['steer']:g}:1 -- iRacing's Lotus offers {K['steering_ratio']:g}:1 only")
    # ride heights: GPL measures them its own way, so keep the BASE session's -- re-solve each perch (on iRacing's 1/64"
    # lattice) for the new springs, as a setter would after a spring change (the PO's WW103 in iRacing: 134.9/131.0 mm)
    target = gm.solve_static(base_knobs)["rh"]
    ps = _spec("perch")
    for _ in range(12):
        rh = gm.solve_static(K)["rh"]
        perch = list(K["perch"])
        for i in range(4):
            lo, hi = (ps["min_front"], ps["max_front"]) if i < 2 else (ps["min_rear"], ps["max_rear"])
            perch[i] = min(max(perch[i] + (rh[i] - target[i]) / 0.8, lo), hi)    # +1 mm perch ~ -0.8 mm ride height
        K["perch"] = perch
    K["perch"] = [round(p / ps["step"]) * ps["step"] for p in K["perch"]]
    rh = gm.solve_static(K)["rh"]
    notes.append("perches re-set to keep the base car's ride heights: " + "/".join(f"{p:.1f}" for p in K["perch"]) +
                 " mm (ride heights " + "/".join(f"{x:.1f}" for x in rh) + " mm)")
    notes.append("not carried: GPL's ride height and bump rubbers (measured differently)")
    return K, notes
