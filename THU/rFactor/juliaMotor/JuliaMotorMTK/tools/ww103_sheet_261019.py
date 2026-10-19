# WW103 (GPL Wat10361WW.kj1) -> iRacing Lotus 49 setup sheet, in iRacing's own sheet layout, for typing into the garage.
import html, sys
out = sys.argv[1]
def row(label, val, gpl=""):
    g = f' <span class="g">{html.escape(gpl)}</span>' if gpl else ""
    return f"{html.escape(label)}: <U>{html.escape(val)}</U>{g}<br>\n"
def sec(t): return f"<H2><U>{t}:</U></H2>\n"
corners = dict(LF=("LEFT FRONT", "O M I"), LR=("LEFT REAR", "O M I"), RF=("RIGHT FRONT", "I M O"), RR=("RIGHT REAR", "I M O"))
psi = dict(LF=19, RF=20, LR=20, RR=20)
b = []
b.append("""<!DOCTYPE html><html><head><meta charset="utf-8"><title>WW103 iRacing setup sheet</title>
<style>body{font-family:Arial,Helvetica,sans-serif;font-size:11pt;max-width:46em;margin:1.5em auto;padding:0 1em}
H2{font-size:13pt;margin:0.9em 0 0.2em} .g{color:#666;font-size:9.5pt} .box{border:1px solid #999;padding:0.5em 0.8em;margin:0.8em 0}
table{border-collapse:collapse;font-size:10pt} td,th{border:1px solid #bbb;padding:2px 6px;text-align:left}</style></head><body>
<H2 align="center">iRacing.com Motorsport Simulations<br>lotus49 setup: 261005_jr_ww103<br>track: monza nochicane</H2>
<p align="center"><b>Wolfgang Wagner's GPL setup WW103</b> (Wat10361WW.kj1, Watkins Glen 1:03.61) carried to iRacing's
garage. Typed out for entering by hand (iRacing cannot load a sheet). Grey = WW103's own GPL value, and why the iRacing value
differs where it does.</p>
<div class="box"><b>You may not need to type anything:</b> this is the setup you built on 5 October and saved as
<b>261005_jr_ww103</b>. Re-doing the conversion on 19 October with everything learned since (the garage's real ranges,
the springs' motion ratios, each anti-roll bar hole's stiffness) gives the same values. If 261005_jr_ww103 is still in your
garage, load it and compare it with this sheet; if it is lost, enter the values below on <b>261010_rung_official</b> and save
as <b>261005_jr_ww103</b>.<br><br>
<b>Order:</b> Tires, then Chassis (springs, then perches until the ride heights and cross weight below are shown, then the
rest), then Drivetrain. Wait 3 seconds after each change until no label has an asterisk.</div>
""")
for k in ("LF", "LR", "RF", "RR"):
    name, tmp = corners[k]
    b.append(sec(name))
    b.append(row("Cold pressure", "152 kPa", f"GPL {psi[k]} psi = {psi[k]*6.895:.0f} kPa; 152 kPa is iRacing's lowest"))
b.append(sec("FRONT"))
b.append(row("ARB arms", "5", "GPL bar 200 lb/in, 1.25x a typical GPL front bar; see the roll-balance note"))
b.append(row("ARB diameter", '0.375"'))
b.append(row("Brake bias", "54.00%", "GPL 54 %"))
b.append(row("Toe-in", "-6 mm", "GPL -0.5 in = -12.7 mm toe-out; -6 mm is the most tech allows (-7 fails)"))
b.append(row("Steering ratio", "10:1", "GPL 16:1; iRacing's Lotus offers 10:1 only"))
b.append(row("Cross weight", "50.0%", "check value, set by the perches"))
cw = dict(LF=("1351 N", "84.7 mm", "61.4 mm of 104.6 mm", "134.9 mm", "-0.4 deg", "GPL -0.75 deg; more negative than -0.4 fails tech"),
          LR=("1640 N", "104.8 mm", "59.6 mm of 113.0 mm", "104.0 mm", "-0.4 deg", "GPL -0.5 deg; -0.5 fails tech"),
          RF=("1325 N", "86.0 mm", "58.8 mm of 104.6 mm", "131.0 mm", "-0.1 deg", "GPL 0.0 deg; the garage shows -0.1 (the nearest it reaches)"),
          RR=("1620 N", "106.2 mm", "59.9 mm of 113.0 mm", "104.8 mm", "+0.2 deg", "GPL +0.25 deg"))
spring = dict(LF=("18 N/mm", "GPL wheel rate 50 lb/in = 13.3 N/mm spring; 18 is iRacing's softest front"),
              RF=("18 N/mm", "as LF"),
              LR=("48 N/mm", "GPL 120 lb/in = 47 N/mm spring; 48 keeps it the setup julia's WW103 is fitted to (2 % apart)"),
              RR=("48 N/mm", "as LR"))
damp = dict(LF=("+6", "+9", "GPL bump 3, rebound 4 of 1..5"), RF=("+6", "+9", "as LF"),
            LR=("+9", "+12", "GPL bump 4, rebound 5 (its stiffest) of 1..5"), RR=("+9", "+12", "as LR"))
for k in ("LF", "LR", "RF", "RR"):
    c = cw[k]
    b.append(sec(corners[k][0]))
    b.append(row("Corner weight", c[0], "check value"))
    b.append(row("Ride height", c[1], "check value (GPL ride heights are not comparable)"))
    b.append(row("Shock deflection", c[2], "check value"))
    b.append(row("Spring perch offset", c[3], "set until the ride heights and cross weight above are shown"))
    b.append(row("Spring rate", *spring[k]))
    b.append(row("Packer", "0.0 mm"))
    b.append(row("Bump stiffness", damp[k][0] + " clicks", damp[k][2]))
    b.append(row("Rebound stiffness", damp[k][1] + " clicks"))
    b.append(row("Camber", c[4], c[5]))
b.append(sec("REAR"))
b.append(row("Fuel level", "43.2 L", "the test fuel, as every test since 4 October; WW103's race fuel is 4 US gal = 15 L"))
b.append(row("ARB diameter", '0.6875"'))
b.append(row("ARB arms", "firm", "GPL bar 200 lb/in, 1.33x a typical GPL rear bar; firm is iRacing's stiffest rear"))
b.append(row("Toe-in", "+3 mm", "GPL +0.125 in = 3.2 mm"))
b.append("<H2><U>Transmission:</U></H2>\n")
b.append(row("Final drive", "3.78", "GPL final 3.1 with gears 2.286/1.706/1.474/1.286/1.160 (a close-ratio Glen box)"))
for n, (r, v, g) in enumerate((("2.23", "140.7", "GPL 1st tops out at 167 km/h; 2.23 is iRacing's tallest 1st"),
                               ("1.40", "224.0", "GPL 224 km/h"), ("1.21", "259.2", "GPL 260 km/h"),
                               ("1.04", "301.6", "GPL 297 km/h"), ("0.958", "327.4", "GPL 330 km/h"))):
    b.append(row(("First", "Second", "Third", "Fourth", "Fifth")[n] + " Gear", f"{r} {v} Km/h", g))
b.append("<H2><U>Differential:</U></H2>\n")
b.append(row("Clutch plates", "4", "GPL 4"))
b.append(row("Preload", "41 Nm", "GPL has no preload: iRacing's default kept"))
b.append(row("Drive ramp angle", "35 deg", "GPL 30 deg (locks hard on power); 35 is iRacing's lowest"))
b.append(row("Coast ramp angle", "85 deg", "GPL 85 deg (nearly free off throttle)"))
b.append("""<H2><U>Notes (julia racer, 19 October 2026):</U></H2>
<p><b>Roll balance (why front arms 5 and rear firm).</b> WW103 is loose because its roll stiffness leans to the rear:
against a typical GPL Lotus setup it has +11 % at the front and +31 % at the rear (soft front springs, both bars stiff).
In iRacing, with the softest front springs, julia's per-hole bar model gives:</p>
<table><tr><th>Bars (front / rear)</th><th>Front roll stiffness</th><th>Rear</th><th>Front share</th></tr>
<tr><td>default car: 0.375" arms 2 / 0.6875" arms 5</td><td>reference</td><td>reference</td><td>41 %</td></tr>
<tr><td><b>this sheet: 0.375" arms 5 / 0.6875" firm</b></td><td>+6 %</td><td>+19 % (iRacing's most)</td><td><b>38 %</b></td></tr>
<tr><td>importer's literal pick: arms 3 / arms 6</td><td>-14 %</td><td>+10 %</td><td>36 %</td></tr>
<tr><td>WW103 in GPL, for comparison</td><td>+11 %</td><td>+31 %</td><td>37 %</td></tr></table>
<p>iRacing's rear bar cannot reach WW103's +31 %, so the sheet keeps the rear at its stiffest and sets the front for the
balance. Front arms 5 lands within 1 point of WW103's 37 % front share while keeping the car's total roll stiffness up.
Arms 4 (36 %) would be the other choice, a touch looser.</p>
<p><b>What iRacing's ranges cut:</b> tyre pressures (152 kPa minimum), the front springs (18 N/mm minimum), front toe-out
(-6 mm tech limit), the left-side camber (tech), the 30 deg drive ramp (35 minimum), GPL's 16:1 steering (10:1 only) and
the 1st gear (iRacing's tallest 1st is shorter). GPL's ride heights and bump rubbers are measured differently and are
not carried over.</p>
<p><b>Corner weights, ride heights, shock deflections</b> are what your own 18 October sheet of 261005_jr_ww103 shows at
Monza: check values, not knobs.</p>
</body></html>
""")
open(out, "w").write("".join(b))
