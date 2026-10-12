import glob, os, re
from ibt import header, yget
G = os.path.expanduser("~/gold standard/julia racer")
def info(f):
    _, _, y, *_ = header(f)
    name = re.search(r"DriverSetupName: (.*)", y); mod = re.search(r"DriverSetupIsModified: (\d)", y)
    g = lambda *k: (yget(y, "CarSetup", *k) or "?")
    fp = (f"springs F/R {g('Chassis','LeftFront','SpringRate')}/{g('Chassis','LeftRear','SpringRate')} | bars F {g('Chassis','Front','ArbDiameter')} {g('Chassis','Front','ArbArms')} R {g('Chassis','Rear','ArbDiameter')} {g('Chassis','Rear','ArbArms')}"
          f" | diff {g('Drivetrain','Differential','DriveRampAngle')}/{g('Drivetrain','Differential','CoastRampAngle')} {g('Drivetrain','Differential','ClutchPlates')}pl | final {g('Drivetrain','Transmission','FinalDrive')}"
          f" 2nd {g('Drivetrain','Transmission','SecondGear').split(',')[0]} | toe F {g('Chassis','Front','ToeIn')} R {g('Chassis','Rear','ToeIn')} | camber LF/RF {g('Chassis','LeftFront','Camber')}/{g('Chassis','RightFront','Camber')}"
          f" | bias {g('Chassis','Front','BrakeBias')} | fuel {g('Chassis','Rear','FuelLevel')} | press R {g('Tires','RightFront','ColdPressure')} | dampers F {g('Chassis','LeftFront','BumpStiffness')}/{g('Chassis','LeftFront','ReboundStiffness')}")
    return (name.group(1).strip() if name else "?") + (" (modified)" if mod and mod.group(1) == "1" else ""), fp
print("REFERENCES")
for lab, f in (("game default template (June)", G + "/lotus49_nurburgring nordschleife 2026-06-24 15-53-11.ibt"), ("261004 Ring default", sorted(glob.glob(G + "/261004/*nordschleife 2026*.ibt"))[0]), ("261005 WW103 template", glob.glob(G + "/261005/*00-01-05.ibt")[0])):
    n, fp = info(f); print(f"  {lab:30s} [{n}]\n      {fp}")
print("\n261010/11 SESSION")
for f in sorted(glob.glob(G + "/261010/*.ibt"), key=lambda p: p.split(" 2026-")[1]):
    st = re.search(r"(\d\d-\d\d-\d\d)\.ibt$", f).group(1); n, fp = info(f)
    print(f"  {st} {os.path.basename(f)[8:20]:12s} [{n}]\n      {fp}")
