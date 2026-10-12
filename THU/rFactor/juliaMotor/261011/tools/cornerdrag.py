# Gold cornering drag: on the skidpad, the engine's drive force (throttle map x WOT table, validated on straights) minus
# mass x dV/dt minus aero and rolling = the drag of cornering. By |ay| band. Rows: clutch in, off the brakes, gear >= 2,
# 4,000-8,800 rpm, |beta| < 6 deg, pedal 0.15-0.95.
import glob, os, sys, numpy as np
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer")
K = ((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0),
     (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5))
TK = ((0.0,0.0),(0.1,0.02),(0.2,0.13),(0.3,0.21),(0.4,0.33),(0.5,0.45),(0.6,0.58),(0.7,0.72),(0.8,0.84),(0.9,0.95),(1.0,1.0))
wot = lambda r: np.interp(r, [k[0] for k in K], [k[1] for k in K])
frac = lambda p: np.interp(p, [k[0] for k in TK], [k[1] for k in TK])
drag = lambda r: (14.24 + 0.00389 * r) * 0.5 * (1 + np.tanh((r - 2353) / 351))
R, ETA, IE, IW, CDA, CRR = 0.334, 0.9, 0.18, 1.0, 0.480, 0.0139
def sm(x, n): return np.convolve(x, np.ones(n)/n, "same")
files = sys.argv[1:] or sorted(glob.glob(G + "/261010/*skidpad*.ibt"))
rows = []
for f in files:
    d, y, t = read_ibt(f, ["Speed","LatAccel","Throttle","Brake","Clutch","Gear","RPM","VelocityX","VelocityY","AirDensity","IsOnTrackCar","YawRate"])
    cw = [float(yget(y,"CarSetup","Chassis",c,"CornerWeight").split()[0]) for c in ["LeftFront","RightFront","LeftRear","RightRear"]]
    M = sum(cw)/9.81
    gr = [float(yget(y,"CarSetup","Drivetrain","Transmission",k).split(",")[0]) for k in ["FirstGear","SecondGear","ThirdGear","FourthGear","FifthGear"]]
    fd = float(yget(y,"CarSetup","Drivetrain","Transmission","FinalDrive"))
    v = sm(d["Speed"], 15); a = np.gradient(v)*60; ay = sm(d["LatAccel"].mean(1), 15)/9.81
    rpm = d["RPM"]; g = d["Gear"].astype(int); thr = d["Throttle"]
    beta = np.degrees(np.arctan2(d["VelocityY"].mean(1), d["VelocityX"].mean(1)))
    ok = (d["IsOnTrackCar"] > .5) & (v > 15) & (d["Brake"] < 0.01) & (d["Clutch"] > 0.98) & (g >= 2) & (rpm > 4000) & (rpm < 8800) & (np.abs(beta) < 6) & (thr > 0.15) & (thr < 0.95)
    G_ = np.array([gr[max(k,1)-1]*fd for k in g])
    T = -drag(rpm) + frac(thr)*(wot(rpm) + drag(rpm))
    akin = a
    Fd = T*G_*ETA/R - (IE*G_*G_/R/R + 4*IW/R/R)*akin
    res = Fd - M*a - 0.5*d["AirDensity"]*CDA*v*v - CRR*M*9.81
    for k in np.where(ok)[0][::3]:
        rows.append((abs(ay[k]), res[k], M, v[k], thr[k]))
A = np.array(rows)
print("gold: cornering drag (drive - inertia - aero - rolling) [N] by |ay| band")
for lo in np.arange(0.0, 1.3, 0.1):
    m = (A[:,0] >= lo) & (A[:,0] < lo+0.1)
    if m.sum() > 30:
        print("  %.2f g: median %6.0f N  (n %5d, as fraction of m*ay: %.3f; v %.0f km/h, pedal %.2f)" % (lo+0.05, np.median(A[m,1]), m.sum(), np.median(A[m,1])/np.median(A[m,2]*9.81*max(lo+0.05,0.05)), 3.6*np.median(A[m,3]), np.median(A[m,4])))
