"""IRGOLD-1 (next angle): the WOT torque excess of the low gears in the shipped frame (0.18 at the crank in gear), PER
SESSION -- consistent across sessions (a drivetrain-model effect) or session-specific (fuel, temperature, setup)?"""
import os, sys, runpy, io, contextlib, glob, re
import numpy as np
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ns = runpy.run_path(os.path.join(os.path.dirname(__file__), "inertiafit.py"))
# inertiafit's WOT rows don't keep the file; recompute per session from its globals
read_ibt, yget, lslope = ns["read_ibt"], ns["yget"], ns["lslope"]
G = ns["G"]; RWF, RWR, IW, ETA, g0 = 0.30, 0.334, 1.0, 0.9, 9.80665
CDA, CRR = 0.480, 0.0139
K = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0), (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))
wot = lambda r: np.interp(r, [k[0] for k in K], [k[1] for k in K])
res = {}
for f in sorted(glob.glob(G + "/26100[2-9]/*.ibt") + glob.glob(G + "/26101[0-2]/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _ = read_ibt(f, ["Speed", "RPM", "Gear", "Throttle", "Clutch", "AirDensity", "Alt", "FuelLevel"])
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        ratios = [float(yget(y, "CarSetup", "Drivetrain", "Transmission", k).split(",")[0]) for k in ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear")]
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception:
        continue
    m = cw/9.81; dt = 1/60; v = d["Speed"]; we = d["RPM"]*2*np.pi/60
    a = lslope(v, dt, 8) + g0*lslope(d["Alt"], dt, 60)/np.maximum(v, 1.0); wdot = lslope(we, dt, 8); gear = d["Gear"].astype(int)
    ok = (d["Clutch"] > 0.98) & (d["Throttle"] > 0.98) & (gear >= 2) & (gear <= 4) & (v > 1.0) & (d["RPM"] > 3500) & (d["RPM"] < 6000)
    chg = np.r_[False, np.diff(gear) != 0]; ok &= ~(np.convolve(chg.astype(float), np.ones(61), mode="same") > 0)
    sess = f.split("/")[-2]
    for i in np.where(ok)[0]:
        gr = ratios[gear[i]-1]*fd
        road = 0.5*d["AirDensity"][i]*CDA*v[i]**2 + CRR*m*g0
        T = 0.18*wdot[i] + (2*IW*wdot[i]/gr + RWR*((m + 2*IW/RWF**2)*a[i] + road))/(gr*ETA)
        res.setdefault((sess, gear[i]), []).append(T - wot(d["RPM"][i]))
print("WOT torque − S6 table at 3,500-6,000 rpm, shipped frame (median N·m, rows) by session and gear:")
for sess in sorted(set(k[0] for k in res)):
    print(f"  {sess}: " + "   ".join(f"g{g} {np.median(res[(sess,g)]):+6.1f} ({len(res[(sess,g)])})" for g in (2, 3, 4) if (sess, g) in res and len(res[(sess, g)]) >= 15))

# ---- per-gear effective in-gear inertia (crank-referred) that zeroes each gear's WOT residual against the S6 table ----
rows = {}
for f in sorted(glob.glob(G + "/26100[2-9]/*.ibt") + glob.glob(G + "/26101[0-2]/*.ibt")):
    if "19-30-13" in f: continue
    try:
        d, y, _ = read_ibt(f, ["Speed", "RPM", "Gear", "Throttle", "Clutch", "AirDensity", "Alt"])
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        ratios = [float(yget(y, "CarSetup", "Drivetrain", "Transmission", k).split(",")[0]) for k in ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear")]
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception:
        continue
    m = cw/9.81; dt = 1/60; v = d["Speed"]; we = d["RPM"]*2*np.pi/60
    a = lslope(v, dt, 8) + g0*lslope(d["Alt"], dt, 60)/np.maximum(v, 1.0); wdot = lslope(we, dt, 8); gear = d["Gear"].astype(int)
    ok = (d["Clutch"] > 0.98) & (d["Throttle"] > 0.98) & (gear >= 1) & (gear <= 5) & (v > 1.0) & (d["RPM"] > 3500) & (d["RPM"] < 8500) & (wdot > 20)
    chg = np.r_[False, np.diff(gear) != 0]; ok &= ~(np.convolve(chg.astype(float), np.ones(61), mode="same") > 0)
    for i in np.where(ok)[0]:
        gr = ratios[gear[i]-1]*fd
        road = 0.5*d["AirDensity"][i]*CDA*v[i]**2 + CRR*m*g0
        Tb = (2*IW*wdot[i]/gr + RWR*((m + 2*IW/RWF**2)*a[i] + road))/(gr*ETA)
        rows.setdefault(gear[i], []).append(((wot(d["RPM"][i]) - Tb), wdot[i]))
print("\nper-gear effective inertia at the crank (least squares on WOT − Tbody = I·ω̇e; shipped 0.18 in every gear):")
for g in sorted(rows):
    A = np.array(rows[g]); I = (A[:, 0] @ A[:, 1])/(A[:, 1] @ A[:, 1])
    med = np.median(A[:, 0]/A[:, 1])
    print(f"  gear {g}: I {I:.3f} kg·m² (median ratio {med:.3f}, n {len(A)}, mean ω̇e {A[:,1].mean():.0f} rad/s²)")
