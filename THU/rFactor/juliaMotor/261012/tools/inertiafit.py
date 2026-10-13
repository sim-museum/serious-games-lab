"""IRGOLD-1 S14: where does the drivetrain's in-gear inertia sit? Joint linear least squares over every WOT, clutch-in,
gear-1..5 row of every session in the store (261002-261012), with the crank's own 0.0522 (free revs) fixed:
   Tbody + 0.0522·ω̇e = T(rpm band) − I_in·ω̇e − I_out·ω̇e/r²            (r = the gear's own ratio, final drive excluded)
I_in: inertia on the gearbox INPUT (turns at engine speed); I_out: on the gearbox OUTPUT / pinion (turns at r× less),
expressed at the crank in top-gear-free units. T per 250-rpm band is free. Gradient removed via Alt over ±1 s."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer")
RWF, RWR, IW, ETA, g0, IE = 0.30, 0.334, 1.0, 0.9, 9.80665, 0.0522
CDA, CRR = float(os.environ.get("CDA", "0.480")), float(os.environ.get("CRR", "0.0139"))   # S14: the road load refitted in this frame: 0.4967 / 0.0144
def lslope(y, dt, hw):
    k = np.arange(-hw, hw+1); w = k/(dt*(k**2).sum())
    return np.convolve(y, w[::-1], mode="same")
EXCL = ("19-30-13",)
rows = []
files = sorted(glob.glob(G + "/26100[2-9]/*.ibt") + glob.glob(G + "/26101[0-2]/*.ibt"))
for f in files:
    if any(e in f for e in EXCL): continue
    try:
        d, y, tick = read_ibt(f, ["Speed", "RPM", "Gear", "Throttle", "Clutch", "AirDensity", "Alt", "Voltage"])
        if "Voltage" in d and not np.any(d["Voltage"]): continue
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        ratios = [float(yget(y, "CarSetup", "Drivetrain", "Transmission", k).split(",")[0]) for k in ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear")]
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception as e:
        print("skip", os.path.basename(f), e); continue
    m = cw/9.81; dt = 1/60; v = d["Speed"]; we = d["RPM"]*2*np.pi/60
    a = lslope(v, dt, 8) + g0*lslope(d["Alt"], dt, 60)/np.maximum(v, 1.0)   # remove the gravity component along the road
    wdot = lslope(we, dt, 8); gear = d["Gear"].astype(int)
    ok = (d["Clutch"] > 0.98) & (d["Throttle"] > 0.98) & (gear >= 1) & (gear <= 5) & (v > 1.0) & (d["RPM"] > 1500) & (d["RPM"] < 8900)
    chg = np.r_[False, np.diff(gear) != 0]; ok &= ~(np.convolve(chg.astype(float), np.ones(61), mode="same") > 0)
    for i in np.where(ok)[0]:
        r = ratios[gear[i]-1]; gr = r*fd
        road = 0.5*d["AirDensity"][i]*CDA*v[i]**2 + CRR*m*g0
        Tb = (2*IW*wdot[i]/gr + RWR*((m + 2*IW/RWF**2)*a[i] + road))/(gr*ETA)
        rows.append((gear[i], d["RPM"][i], wdot[i], Tb + IE*wdot[i], r, len(files)))
R = np.array(rows, dtype=float); gear, rpm, wdot, y, r, _ = R.T
print(f"rows {len(R)}: " + " ".join(f"g{k} {int((gear==k).sum())}" for k in range(1, 6)))
bands = np.arange(1500, 8900, 250); bi = np.clip(((rpm - 1500)//250).astype(int), 0, len(bands)-1)
def fit(cols):
    A = np.zeros((len(R), len(bands) + len(cols))); A[np.arange(len(R)), bi] = 1
    for j, c in enumerate(cols): A[:, len(bands)+j] = -c
    # robust: two passes, drop |res| > 3 MAD
    w = np.ones(len(R), bool)
    for _ in range(3):
        x, *_ = np.linalg.lstsq(A[w], y[w], rcond=None)
        res = y - A @ x; mad = np.median(np.abs(res[w])); w = np.abs(res) < 4*1.4826*mad
    return x, res, w
for label, cols in (("I_in only", [wdot]), ("I_out only", [wdot/r**2]), ("I_in + I_out", [wdot, wdot/r**2])):
    x, res, w = fit(cols)
    I = x[len(bands):]
    gm = [np.median(res[w & (gear == k)]) for k in range(1, 6)]
    print(f"\n{label}: I = {np.round(I, 4)}  resid sd {res[w].std():.2f} N·m  kept {w.sum()}  per-gear median resid " + " ".join(f"g{k} {gm[k-1]:+.1f}" for k in range(1, 6)))
    if label == "I_in + I_out":
        print("  T by band (N·m): " + "  ".join(f"{b}:{x[j]:.0f}" for j, b in enumerate(bands) if (w & (bi == j)).sum() >= 10))
        # bootstrap by file blocks is overkill; report per-gear agreement by rpm band
        for k in range(1, 6):
            print(f"  g{k}: " + " ".join(f"{b}:{np.median(res[w & (gear==k) & (bi==j)]):+.0f}" for j, b in enumerate(bands) if (w & (gear==k) & (bi==j)).sum() >= 10))

# ---- the in-gear COAST drag in the same frame (I_in 0, I_out fitted): zero throttle, clutch in, gears 1-5 ----
IOUT = float(os.environ.get("IOUT", "0.1506"))
crow = []
for f in files:
    if any(e in f for e in EXCL): continue
    try:
        d, y, tick = read_ibt(f, ["Speed", "RPM", "Gear", "Throttle", "Clutch", "AirDensity", "Alt", "Voltage", "Brake"])
        if "Voltage" in d and not np.any(d["Voltage"]): continue
        cw = sum(float(re.sub(r"[^0-9.]", "", yget(y, "CarSetup", "Chassis", c, "CornerWeight"))) for c in ("LeftFront", "RightFront", "LeftRear", "RightRear"))
        ratios = [float(yget(y, "CarSetup", "Drivetrain", "Transmission", k).split(",")[0]) for k in ("FirstGear", "SecondGear", "ThirdGear", "FourthGear", "FifthGear")]
        fd = float(yget(y, "CarSetup", "Drivetrain", "Transmission", "FinalDrive"))
    except Exception:
        continue
    m = cw/9.81; dt = 1/60; v = d["Speed"]; we = d["RPM"]*2*np.pi/60
    a = lslope(v, dt, 15) + g0*lslope(d["Alt"], dt, 60)/np.maximum(v, 1.0)
    wdot = lslope(we, dt, 15); gear = d["Gear"].astype(int)
    ok = (d["Clutch"] > 0.98) & (d["Throttle"] < 0.005) & (d["Brake"] < 0.005) & (gear >= 1) & (gear <= 5) & (v > 5) & (d["RPM"] > 1800) & (d["RPM"] < 8500)
    st = ok.copy()
    for k in range(1, 16): st &= np.roll(ok, k) & np.roll(ok, -k)
    for i in np.where(st)[0]:
        r = ratios[gear[i]-1]; gr = r*fd
        road = 0.5*d["AirDensity"][i]*CDA*v[i]**2 + CRR*m*g0
        Tb = (2*IW*wdot[i]/gr + RWR*((m + 2*IW/RWF**2)*a[i] + road))/(gr*ETA)
        crow.append((gear[i], d["RPM"][i], -(Tb + IE*wdot[i] + IOUT*wdot[i]/r**2)))
C = np.array(crow); cg, crpm, cdrag = C.T
print(f"\nCOAST rows {len(C)} (I_out {IOUT}): " + " ".join(f"g{k} {int((cg==k).sum())}" for k in range(1, 6)))
fade = lambda q: 0.5*(1 + np.tanh((q - 2353)/351))
for b in range(1800, 8500, 400):
    mm = (crpm >= b) & (crpm < b+400)
    if mm.sum() >= 20:
        print(f"   {b:4d}-{b+400:4d} n{mm.sum():5d} drag {np.median(cdrag[mm]):5.1f}  E91 {(14.24+0.00389*(b+200))*fade(b+200):5.1f}  by gear " +
              " ".join(f"g{k} {np.median(cdrag[mm & (cg==k)]):5.1f}" for k in range(1, 6) if (mm & (cg==k)).sum() >= 10))
mm = crpm > 2900
A = np.c_[fade(crpm[mm]), crpm[mm]*fade(crpm[mm])]
c, *_ = np.linalg.lstsq(A, cdrag[mm], rcond=None)
res = cdrag[mm] - A @ c; w = np.abs(res) < 4*1.4826*np.median(np.abs(res))
c, *_ = np.linalg.lstsq(A[w], cdrag[mm][w], rcond=None)
print(f"   in-gear coast drag fit (rpm > 2900): ({c[0]:.2f} + {c[1]:.5f}·rpm)·fade   [E91: 14.24 + 0.00389·rpm]")
