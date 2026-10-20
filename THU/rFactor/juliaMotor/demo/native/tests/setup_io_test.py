# SETUPIO-1 (PO 2026-10-19): "implement in julia racer GPL setup import/export and iracing sheet import/export".
# GPL .kj1 export (gpl.exe's 'PGTS' v3 layout, its tooth table), iRacing setup sheet import (iRacing's layout, metric and
# imperial) and export, and the Garage tab's buttons -- headless, own config dir, no GPL install or gold store needed.
import sys, os, tempfile, struct
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="jr_setupio_cfg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import garage as gm, gpl_setup as gs, iracing_sheet as irs
ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

S = gm.sessions(); MED = tuple(gm.load_toml()["gpl"]["arb_median"])

# ---- GPL export: the file gpl.exe writes ----------------------------------------------------------------------------
g, notes = gs.export(S["default"]["knobs"], S["default"], arb_median=MED)
b = gs.encode_kj1(g)
check(b[:4] == b"PGTS" and struct.unpack_from("<ii", b, 4) == (3, 249) and len(b) == 264 and b[-3:] == b"   ",
      f"a GPL 'PGTS' v3 file, 249-byte payload, padded to 264 ({len(b)} bytes)")
r = struct.unpack_from("<9f", b, 12); ix = struct.unpack_from("<9i", b, 12 + 0x24)
check(all(abs(abs(r[k]) - gs.teeth_ratio(ix[k])) < 1e-5 for k in (0, 2, 3, 4, 5, 6, 7, 8)) and ix[1] == 0 and r[1] == 0.0 and r[0] < 0,
      "every gear ratio is GPL's own tooth pair at the index written beside it (R negative, N 0)")
check(ix[8] in gs.GPL_FINAL_IDX and all(i in gs.GPL_GEAR_IDX for i in ix[2:8]), f"final from 31/7..31/10, gears from the gear table {ix}")
check(struct.unpack_from("<4f", b, 12 + 0xa0) == (800.0,) * 4 and struct.unpack_from("<4f", b, 12 + 0xb0) == (7.0,) * 4,
      "gpl.exe's constant blocks (800, 7)")
d = gs.decode_kj1(b)
check(set(d["ramp"]) <= set(gs.GPL_RAMPS) and 1 <= d["clutches"] <= 6 and all(1 <= x <= 5 for x in d["bump"] + d["rebound"]),
      f"GPL's own ranges: ramps {d['ramp']}, clutches {d['clutches']}, dampers {d['bump']}/{d['rebound']}")
check(abs(d["rate"][0] - S["default"]["knobs"]["spring"][0] * gs.MRK[0] ** 2 / gs.LBIN) < 1.0,
      f"iRacing's 30 N/mm front spring -> GPL wheel rate {d['rate'][0]:.0f} lb/in (x MR^2)")
check(2.5 <= d["ride"][0] <= 5.0 and d["bias"] == 54 and abs(d["fuel_gal"] - 43.2 / 3.785) < 0.02,
      f"ride {d['ride']} in (GPL's 2.5..5), bias {d['bias']} %, fuel {d['fuel_gal']} gal")

# ---- GPL round trip: WW103's values in, out again -------------------------------------------------------------------
ww = dict(ratios=[-gs.teeth_ratio(4), 0.0, 2.2857143, 1.7058823, 1.4736842, 1.2857143, 1.16, 1.0, 3.1],
          gear_idx=[4, 0, 9, 24, 45, 58, 70, 83, 89], ramp=[30.0, 85.0], psi=[19.0, 20.0, 20.0, 20.0], rate=[50.0, 50.0, 120.0, 120.0],
          bump=[3, 3, 4, 4], rebound=[4, 4, 5, 5], camber=[-0.75, 0.0, -0.5, 0.25], rubber=[1.0] * 4, toe=[-0.5, 0.125],
          arb=[200.0, 200.0], ride=[2.5, 2.5], clutches=4, fuel_gal=4.0, steer=16.0, bias=54, flag=0)
K, _ = gs.translate(gs.decode_kj1(gs.encode_kj1(ww)), S["default"]["knobs"], arb_median=MED)
g2, n2 = gs.export(K, S["default"], arb_median=MED)
d2 = gs.decode_kj1(gs.encode_kj1(g2))
check(d2["psi"] == ww["psi"] and d2["bump"] == ww["bump"] and d2["rebound"] == ww["rebound"] and d2["bias"] == 54 and d2["clutches"] == 4,
      "GPL -> julia -> GPL: pressures, dampers, bias, clutches come back exactly")
check(d2["ramp"] == [30.0, 85.0] and abs(d2["final"] - 3.1) < 1e-5 and all(abs(a - b) < 0.02 for a, b in zip(d2["gears"][1:4], ww["ratios"][3:6])),
      f"ramps {d2['ramp']}, final {d2['final']:.3f}, 2nd-4th gears within 0.02 ({[round(x, 3) for x in d2['gears'][1:4]]})")
check(abs(d2["rate"][2] - 120) <= 2 and d2["rate"][0] > 60 and any("diff preload" in x for x in n2),
      f"rear wheel rate {d2['rate'][2]:.0f} (120); front {d2['rate'][0]:.0f}: iRacing's softest front spring -- and the notes say what is lost")

# ---- iRacing sheet import: iRacing's own layout -------------------------------------------------------------------
def sheet(units="metric"):
    P = (lambda kpa: f"{kpa / 6.894757:.1f} psi") if units == "imperial" else (lambda kpa: f"{kpa:.0f} kPa")
    L = (lambda mm: f"{mm / 25.4:.3f} in") if units == "imperial" else (lambda mm: f"{mm:.1f} mm")
    Kn = (lambda n: f"{n / 0.175127:.0f} lbs/in") if units == "imperial" else (lambda n: f"{n:.0f} N/mm")
    F = (lambda l: f"{l / 3.785412:.2f} gal") if units == "imperial" else (lambda l: f"{l:.1f} L")
    tyre = lambda c: f"<H2><U>{c}:</U></H2>\nCold pressure:<U>{P(152)}</U><br>Last hot pressure:<U>{P(152)}</U><br>Last temps O M I:<U>39C</U><br><U>39C</U><br><U>39C</U><br>Tread remaining:<U>100%</U><br><U>100%</U><br><U>100%</U><br><br>"
    ch = lambda c, perch, k, bump, reb, cam: (f"<H2><U>{c}:</U></H2>\nCorner weight:<U>1351 N</U><br>Ride height:<U>{L(84.7)}</U><br>"
         f"Shock deflection:<U>{L(61.4)}</U><U>of {L(104.6)}</U><br>Spring perch offset:<U>{L(perch)}</U><br>Spring rate:<U>{Kn(k)}</U><br>"
         f"Packer:<U>{L(0)}</U><br>Bump stiffness:<U>+{bump} clicks</U><br>Rebound stiffness:<U>+{reb} clicks</U><br>Camber:<U>{cam} deg</U><br><br>")
    return ("<html><body><H2 align=\"center\">iRacing.com Motorsport Simulations<br>lotus49 setup: 261005_jr_ww103<br>track: monza nochicane</H2><br>\n"
            + tyre("LEFT FRONT") + tyre("LEFT REAR") + tyre("RIGHT FRONT") + tyre("RIGHT REAR")
            + "<H2><U>FRONT:</U></H2>\nARB arms:<U>5</U><br>ARB diameter:<U>0.375\"</U><br>Brake bias:<U>54.00%</U><br>Toe-in:<U>" + L(-6) + "</U><br>Steering ratio:<U>10:1</U><br>Cross weight:<U>50.0%</U><br><br>"
            + ch("LEFT FRONT", 134.9, 18, 6, 9, "-0.4") + ch("LEFT REAR", 104.0, 48, 9, 12, "-0.4")
            + ch("RIGHT FRONT", 131.0, 18, 6, 9, "-0.1") + ch("RIGHT REAR", 104.8, 48, 9, 12, "+0.2")
            + "<H2><U>REAR:</U></H2>\nFuel level:<U>" + F(43.2) + "</U><br>ARB diameter:<U>0.6875\"</U><br>ARB arms:<U>firm</U><br>Toe-in:<U>" + L(3) + "</U><br><br>"
            + "<H2><U>Transmission:</U></H2>\nFinal drive:<U>3.78</U><br>First Gear:<U>2.23</U><U>140.7 Km/h</U><br>Second Gear:<U>1.40</U><U>224.0 Km/h</U><br>"
            + "Third Gear:<U>1.21</U><U>259.2 Km/h</U><br>Fourth Gear:<U>1.04</U><U>301.6 Km/h</U><br>Fifth Gear:<U>0.958</U><U>327.4 Km/h</U><br><br>"
            + "<H2><U>Differential:</U></H2>\nClutch plates:<U>4</U><br>Preload:<U>41 Nm</U><br>Drive ramp angle:<U>35 deg</U><br>Coast ramp angle:<U>85 deg</U><br><br>"
            + "<H2><U>Notes:</U></H2>\nsome text</body></html>")
W = S["ww103"]["knobs"]
def same(K, R, tol=0.6):
    bad = []
    for k in gm.KNOB_FIELDS:
        a, b2 = K[k], R[k]
        if isinstance(a, list):
            bad += [k] if any(abs(float(x) - float(y)) > (0.06 if k == "camber" else tol) for x, y in zip(a, b2)) else []
        elif isinstance(a, str) or isinstance(b2, str):
            bad += [k] if str(a) != str(b2) else []
        elif abs(float(a) - float(b2)) > tol:
            bad += [k]
    return bad
for units in ("metric", "imperial"):
    p = irs.parse(sheet(units))
    check(p.get("name") == "261005_jr_ww103" and p.get("track") == "monza nochicane", f"{units}: the sheet's setup name and track")
    K, notes = irs.to_knobs(p, S["ww103"])
    bad = same(K, W)
    check(not bad, f"{units}: the WW103 sheet imports as julia's WW103 knobs{'' if not bad else ' -- differ: ' + str(bad)}")
# a sheet with one knob moved
K0 = {k: (list(v) if isinstance(v, list) else v) for k, v in S["default"]["knobs"].items()}
K0["spring"] = [25.0, 25.0, 52.0, 52.0]; K0["rarb_arm"] = "3"; K0["diff_coast"] = 70.0; K0["pressure"] = [158.9, 158.9, 145.0, 145.0]
K1, _ = irs.to_knobs(irs.parse(irs.from_knobs(K0, S["default"], name="moved")), S["default"])
check(not same(K1, K0, 0.3), f"julia's own sheet round-trips its knobs{'' if not same(K1, K0, 0.3) else str(same(K1, K0, 0.3))}")

# ---- the Garage tab's buttons ---------------------------------------------------------------------------------------
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import juliaRacer as jr
jr.HERE = tempfile.mkdtemp(prefix="jr_setupio_test_")
jr.JoyReader.start_reader = lambda self, *a, **k: None
jr.JoyReader.stop_reader = lambda self, *a, **k: None
w = jr.Main(); gt = w.garage
tmp = tempfile.mkdtemp(prefix="jr_setupio_")
for name in ("gplx_b", "sheet_b", "sheetx_b"):
    check(hasattr(gt, name) and gt.findChildren(type(gt.gplx_b)).count(getattr(gt, name)) == 1, f"Garage tab button {getattr(gt, name).text()!r}")
fs = os.path.join(tmp, "ww.htm"); open(fs, "w").write(sheet())
gt.import_sheet_file(fs)
check(gt.is_modified() and gt.K["spring"][0] == 18.0 and gt.K["rarb_arm"] == "firm", "Import iRacing sheet: the garage takes the sheet")
fk = os.path.join(tmp, "out.kj1"); notes = gt.export_gpl_file(fk)
dk = gs.decode_kj1(open(fk, "rb").read())
check(os.path.getsize(fk) == 264 and dk["bump"] == [3, 3, 4, 4] and dk["ramp"] == [30.0, 85.0] and len(notes) > 2,
      f"Export GPL setup: a .kj1 with the garage's dampers {dk['bump']} and ramps {dk['ramp']}")
fo = os.path.join(tmp, "out.htm"); gt.export_sheet_file(fo)
Kb, _ = irs.to_knobs(irs.parse(open(fo).read()), gt.session)
check(not same(Kb, gt.K, 0.3), "Export iRacing sheet: a sheet that imports back to the garage")
print("SETUPIO:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
