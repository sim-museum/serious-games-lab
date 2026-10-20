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


# ---- SETUPIO-1: EXPORT the garage as a GPL Lotus 49 setup (.kj1) ----------------------------------------------------
# PO 2026-10-19: "implement in julia racer GPL setup import/export". The file is gpl.exe's own 'PGTS' chunk, version 3
# (FUN_004892c0 writes it; FUN_00489510 wraps it): a 12-byte header ('PGTS', version 3, payload length 249) and 249 bytes
# copied field by field from the car object, padded with spaces to a multiple of 4 (264 bytes) -- no checksum:
#   0x00 9 x f32  gear ratios R, N, 1st..6th, final   (physics reads these)
#   0x24 9 x i32  their indices in gpl.exe's tooth table (0x53a240: 90 (in, out) pairs) -- what the garage shows as teeth
#   0x48 2 x f32  ramp angles, power then coast (30/45/60/85)   0x50 4 x f32 cold pressures, psi (LF RF LR RR)
#   0x60 4 x f32  wheel rates, lb/in    0x70 4 x i32 bump 1..5    0x80 4 x i32 rebound 1..5    0x90 4 x f32 camber, deg
#   0xa0 4 x f32  800.0 and 0xb0 4 x f32 7.0 -- constants in gpl.exe's defaults and in every one of the PO's 1,722 files
#   0xc0 4 x f32  bump rubbers, in      0xd0 2 x f32 toe F R, in (-: toe-out)    0xd8 2 x f32 roll bars F R, lb/in
#   0xe0 2 x f32  static ride F R, in (GPL clamps 2.5..5 on load)   0xe8 i32 clutches 1..6   0xec f32 fuel, US gal
#   0xf0 f32 steering ratio   0xf4 i32 front brake bias, %   0xf8 u8 a flag (0 in 378 of the PO's 400 v3 files)
# Version 4 files (a later exe, 72 of the PO's) add two f32 (-1, -1) after the flag; the offsets above are unchanged, so
# decode_kj1 reads both. Setup files are per car: .kj1 = the 1967 GP Lotus (.ka1 Brabham, .kc1 BRM, .ke1 Cooper, .kg1
# Eagle, .ki1 Ferrari, .km1/.kn1); GPL also accepts values between its garage clicks (GRE's "fine adjustment").
GPL_TEETH = ((13, 46), (14, 46), (14, 45), (12, 35), (13, 35), (16, 42), (15, 38), (14, 34), (14, 33), (14, 32),
             (16, 42), (15, 38), (14, 34), (17, 41), (14, 33), (14, 32), (15, 33), (16, 31), (15, 32), (15, 31),
             (16, 32), (16, 30), (17, 31), (17, 30), (17, 29), (14, 34), (17, 41), (14, 33), (14, 32), (15, 33),
             (15, 32), (15, 31), (16, 32), (16, 31), (20, 38), (16, 30), (17, 31), (17, 30), (17, 29), (20, 34),
             (18, 30), (18, 29), (18, 28), (19, 29), (21, 32), (19, 28), (18, 26), (19, 27), (24, 34), (20, 28),
             (21, 29), (24, 33), (25, 34), (20, 27), (24, 32), (25, 33), (19, 25), (23, 30), (21, 27), (25, 32),
             (26, 33), (19, 24), (23, 29), (25, 31), (21, 26), (26, 32), (19, 23), (24, 29), (27, 32), (22, 26),
             (25, 29), (19, 22), (27, 31), (28, 32), (22, 25), (25, 28), (27, 30), (28, 31), (29, 32), (22, 24),
             (24, 26), (25, 27), (23, 24), (24, 24), (25, 24), (26, 24), (7, 31), (8, 31), (9, 31), (10, 31))
GPL_GEAR_IDX = range(0, 86)            # forward / reverse pairs
GPL_FINAL_IDX = range(86, 90)          # 31/7 .. 31/10 (the manual's pinion 7..10)
GPL_RAMPS = (30.0, 45.0, 60.0, 85.0)
teeth_ratio = lambda k: GPL_TEETH[k][1] / GPL_TEETH[k][0]


def encode_kj1(g: dict) -> bytes:
    """A GPL 'PGTS' v3 setup file from a dict with decode_kj1's fields plus gear_idx (9) -- gears = the 9 ratio slots."""
    p = bytearray()
    p += struct.pack("<9f", *g["ratios"]) + struct.pack("<9i", *g["gear_idx"])
    p += struct.pack("<2f", *g["ramp"]) + struct.pack("<4f", *g["psi"]) + struct.pack("<4f", *g["rate"])
    p += struct.pack("<4i", *g["bump"]) + struct.pack("<4i", *g["rebound"]) + struct.pack("<4f", *g["camber"])
    p += struct.pack("<4f", 800.0, 800.0, 800.0, 800.0) + struct.pack("<4f", 7.0, 7.0, 7.0, 7.0)
    p += struct.pack("<4f", *g["rubber"]) + struct.pack("<2f", *g["toe"]) + struct.pack("<2f", *g["arb"])
    p += struct.pack("<2f", *g["ride"]) + struct.pack("<i", g["clutches"]) + struct.pack("<f", g["fuel_gal"])
    p += struct.pack("<f", g["steer"]) + struct.pack("<i", g["bias"]) + bytes([g.get("flag", 0)])
    assert len(p) == 249
    b = b"PGTS" + struct.pack("<ii", 3, len(p)) + bytes(p)
    return b + b" " * ((-len(b)) % 4)


def export(K, session, arb_median=None):
    """Garage knobs K (on `session`) -> (GPL setup dict for encode_kj1, notes). The inverse of translate(): physical
    where both games share the quantity, range position where the units differ, GPL's own tooth table for the gearing."""
    notes = []
    D = gm.derived(K, session)
    r = lambda x, q: round(x / q) * q
    # gearing: GPL's final + the table gears closest to iRacing's OVERALL ratios (gear x final)
    want = [g * K["final_drive"] for g in K["gears"]]
    best = None
    for fi in GPL_FINAL_IDX:
        fd = teeth_ratio(fi)
        pick = [min(GPL_GEAR_IDX, key=lambda k: abs(math.log(teeth_ratio(k) * fd / w))) for w in want]
        err = sum(abs(math.log(teeth_ratio(k) * fd / w)) for k, w in zip(pick, want))
        if best is None or err < best[0]:
            best = (err, fi, pick)
    _, fi, pick = best
    sixth = pick[-1] if teeth_ratio(pick[-1]) <= 1.0 else 83          # a 5-speed Lotus: GPL's 6th slot, 1.000 when free
    idx = [4, 0] + pick + [sixth, fi]
    ratios = [-teeth_ratio(4), 0.0] + [teeth_ratio(k) for k in pick] + [teeth_ratio(sixth), teeth_ratio(fi)]
    kmh = lambda ov: gm.PARAMS["rpm_r"] * 2 * math.pi / 60 / ov * 3.6
    notes.append("gears (top speed, iRacing -> GPL's nearest teeth): " +
                 ", ".join(f"{kmh(w):.0f}->{kmh(teeth_ratio(k) * teeth_ratio(fi)):.0f}" for k, w in zip(pick, want)) +
                 f" km/h, final {GPL_TEETH[fi][1]}/{GPL_TEETH[fi][0]}")
    # diff: ramps snap to GPL's four angles; plates -> clutches
    ramp = [min(GPL_RAMPS, key=lambda a: abs(a - float(K[k]))) for k in ("diff_drive", "diff_coast")]
    for k, a in zip(("diff_drive", "diff_coast"), ramp):
        abs(a - float(K[k])) > 0.1 and notes.append(f"{k.replace('_', ' ')}: iRacing {K[k]:g} deg -> GPL {a:g} (GPL offers 30/45/60/85)")
    clutches = int(min(max(int(K["diff_plates"]), 1), 6))
    notes.append(f"diff preload {K['diff_preload']:g} Nm: GPL has none")
    # tyres, springs (iRacing SPRING rate -> GPL WHEEL rate), dampers (0..12 -> 1..5), camber/toe as iRacing DISPLAYS them
    psi = [min(max(r(p / 6.895, 0.25), 10.0), 30.0) for p in K["pressure"]]
    rate = [min(max(round(s * MRK[0 if i < 2 else 1] ** 2 / LBIN), 50 if i < 2 else 70), 125 if i < 2 else 160)
            for i, s in enumerate(K["spring"])]
    for i, s in enumerate(K["spring"]):
        want_r = s * MRK[0 if i < 2 else 1] ** 2 / LBIN
        abs(want_r - rate[i]) > 1 and notes.append(f"wheel rate {('LF', 'RF', 'LR', 'RR')[i]}: {want_r:.0f} lb/in is outside GPL's "
                                                   f"range -> {rate[i]}")
    damp = lambda c: int(min(max(round(1 + c / 12 * 4), 1), 5))
    camber = [round(min(max(c, -3.0), 3.0), 2) for c in D["camber"]]
    toe = [round(D["toe_front"] / 25.4, 3), round(K["toe_rear"] / 25.4, 3)]
    # bars: iRacing's bar against the default car's -> the GPL rate at the same multiple of the GPL median
    med = arb_median or GPL_ARB_MEDIAN
    arb = [150.0, 150.0]
    if med[0] and med[1]:
        for axle, (dk, ak) in enumerate((("farb_dia", "farb_arm"), ("rarb_dia", "rarb_arm"))):
            ref = gm.arb_rate(gm.PARAMS, axle, *gm.ARB_REF[axle][:1], str(gm.ARB_REF[axle][1]))
            rel = gm.arb_rate(gm.PARAMS, axle, float(K[dk]), K[ak]) / ref
            arb[axle] = float(min(max(r(rel * med[axle], 5.0), 40.0), 300.0))
            notes.append(f"{('front', 'rear')[axle]} bar: {K[dk]:g}\" arms {K[ak]} = {rel:.2f}x the default's -> GPL {arb[axle]:g} lb/in")
    # ride: GPL measures its own way (clamped 2.5..5 in); carry iRacing's ride heights in inches, within that
    ride = [min(max(round((D["rh"][0] + D["rh"][1]) / 2 / 25.4, 2), 2.5), 5.0),
            min(max(round((D["rh"][2] + D["rh"][3]) / 2 / 25.4, 2), 2.5), 5.0)]
    notes.append(f"static ride {ride[0]:g}/{ride[1]:g} in from iRacing's ride heights (GPL measures its own way); bump rubbers 1.0 in")
    bias = int(round(float(K["brake_bias"])))
    abs(bias - float(K["brake_bias"])) > 1e-6 and notes.append(f"brake bias {K['brake_bias']:g} % -> {bias} (GPL: whole percent)")
    g = dict(ratios=ratios, gear_idx=idx, ramp=ramp, psi=psi, rate=[float(x) for x in rate],
             bump=[damp(c) for c in K["bump"]], rebound=[damp(c) for c in K["rebound"]], camber=camber,
             rubber=[1.0] * 4, toe=toe, arb=arb, ride=ride, clutches=clutches,
             fuel_gal=round(float(K["fuel"]) / 3.785, 2), steer=float(K["steering_ratio"]), bias=bias, flag=0)
    return g, notes
