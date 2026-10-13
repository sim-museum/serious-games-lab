"""IRGOLD-1 S17: WOT crank torque by gear and rpm band in the SHIPPED frame (0.0522 crank + 0.128 on the gearbox input =
S6's 0.18 at the crank), every session, gradient removed -- is the S6 table low at 3,000-5,500 rpm?"""
import os, sys, runpy, io, contextlib
import numpy as np
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ns = runpy.run_path(os.path.join(os.path.dirname(__file__), "inertiafit.py"))
gear, rpm, wdot, y, r, _ = ns["R"].T          # the WOT rows (inertiafit.py reuses `y` later)
T = y + (0.18 - 0.0522)*wdot            # y = Tbody + 0.0522·ω̇e; add the input-side remainder
K = dict(((3500.0, 235.5), (4400.0, 236.5), (4900.0, 255.0), (5400.0, 273.5), (5900.0, 288.5), (6400.0, 302.5), (6850.0, 311.0), (7150.0, 312.0), (7650.0, 307.5), (8100.0, 300.5), (8650.0, 284.5), (8900.0, 278.5)))
kx = np.array(sorted(K)); ky = np.array([K[k] for k in kx])
print("band      |  g1          g2          g3          g4          g5      | all (median) | S6 table | diff")
for b in range(2500, 9000, 500):
    m0 = (rpm >= b) & (rpm < b+500)
    cells = "".join(f"  {np.median(T[m0 & (gear==k)]):6.1f}({(m0 & (gear==k)).sum():4d})" if (m0 & (gear==k)).sum() >= 15 else "       -    " for k in range(1, 6))
    s6 = np.interp(b+250, kx, ky)
    print(f"{b:4d}-{b+500:4d} |{cells} | {np.median(T[m0]):6.1f}      | {s6:6.1f}   | {np.median(T[m0]) - s6:+5.1f}")
