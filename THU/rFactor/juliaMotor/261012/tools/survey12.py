"""IRTEST-261012 survey: setup per file + a coarse timeline (speed, rpm, gear, throttle, clutch)."""
import glob, os, re, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../261011/tools"))
from ibt import header, read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer/261012")
for f in sorted(glob.glob(G + "/*.ibt")):
    _, vars_, y, tick, *_ = header(f)
    name = re.search(r"DriverSetupName: (.*)", y).group(1).strip()
    mod = re.search(r"DriverSetupIsModified: (\d)", y).group(1)
    g = lambda *k: (yget(y, "CarSetup", *k) or "?")
    d, _, tick = read_ibt(f, ["SessionTime", "Speed", "RPM", "Gear", "Throttle", "Clutch", "Brake", "SteeringWheelAngle", "OnPitRoad", "IsOnTrack"])
    t = d["SessionTime"]; n = len(t)
    print(f"\n== {os.path.basename(f)}  [{name}{' MOD' if mod=='1' else ''}] tick {tick} rows {n} dur {t[-1]-t[0]:.0f}s"
          f" press {g('Tires','LeftFront','ColdPressure')}/{g('Tires','RightRear','ColdPressure')} fuel {g('Chassis','Rear','FuelLevel')}")
    step = int(tick)  # 1 s
    for i in range(0, n, step):
        print(f"  {t[i]-t[0]:6.0f} v{d['Speed'][i]*3.6:6.1f} rpm{d['RPM'][i]:6.0f} g{d['Gear'][i]:2.0f} thr{d['Throttle'][i]:5.2f} clu{d['Clutch'][i]:5.2f} br{d['Brake'][i]:5.2f} st{np.degrees(d['SteeringWheelAngle'][i]):6.0f} trk{d['IsOnTrack'][i]:.0f}")
