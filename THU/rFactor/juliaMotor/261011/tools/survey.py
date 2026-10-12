import glob, os, sys, numpy as np
from ibt import read_ibt, yget
G = os.path.expanduser("~/gold standard/julia racer/261010")
for i, f in enumerate(sorted(glob.glob(G + "/*.ibt"), key=lambda p: p.split(" 2026-")[1])):
    d, y, t = read_ibt(f, ["Speed", "LatAccel", "Brake", "Throttle", "SteeringWheelAngle", "FuelLevel", "dcBrakeBias", "YawRate", "OnPitRoad"])
    v = d["Speed"]*3.6; ay = d["LatAccel"]/9.81; dur = len(v)/t
    mv = v > 20
    tag = []
    for k in [("Chassis","Front","ArbArms"),("Chassis","Front","BrakeBias"),("Chassis","LeftFront","SpringRate"),("Chassis","LeftFront","Camber"),("Chassis","Rear","FuelLevel"),("Drivetrain","Differential","DriveRampAngle"),("Chassis","Front","ToeIn")]:
        tag.append(str(yget(y, "CarSetup", *k)))
    bb = d.get("dcBrakeBias", np.zeros(1))
    # slip angle
    sw = d["SteeringWheelAngle"]*57.3
    print(f"{i+1:2d} {os.path.basename(f)[8:-4]:42s} {t}Hz {dur:6.0f}s vmax {v.max():5.0f} |ay|99 {np.percentile(abs(ay[mv]),99) if mv.any() else 0:4.2f} brk>.3 {np.mean(d['Brake'][mv]>0.3) if mv.any() else 0:4.2f} |sw|max {abs(sw).max():4.0f} fuel {d['FuelLevel'][0]:5.1f} bb {bb.min():.3f}-{bb.max():.3f} | " + " ".join(tag))
