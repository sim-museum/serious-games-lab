#!/usr/bin/env python3
"""Build the juliaMotor project report PDF with fpdf2 (selectable text + figures)."""
import os
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
DEJA = "/usr/share/fonts/truetype/dejavu"

class PDF(FPDF):
    def header(self):
        if self.page_no() == 1: return
        self.set_font("D","",8); self.set_text_color(150)
        self.cell(0,6,"juliaMotor — Project Report", align="R"); self.ln(8)
    def footer(self):
        self.set_y(-12); self.set_font("D","",8); self.set_text_color(150)
        self.cell(0,6,f"{self.page_no()}", align="C")

pdf = PDF(format="A4")
pdf.add_font("D","", f"{DEJA}/DejaVuSans.ttf")
pdf.add_font("D","B", f"{DEJA}/DejaVuSans-Bold.ttf")
pdf.add_font("D","I", f"{DEJA}/DejaVuSans-Oblique.ttf")
pdf.set_auto_page_break(True, margin=16)
pdf.add_page()
W = pdf.epw  # effective page width

def h1(t):
    pdf.ln(3); pdf.set_font("D","B",15); pdf.set_text_color(20,30,60)
    pdf.multi_cell(W,7,t); pdf.set_text_color(0); pdf.ln(1)
def h2(t):
    pdf.ln(1.5); pdf.set_font("D","B",12); pdf.set_text_color(30,60,110)
    pdf.multi_cell(W,6,t); pdf.set_text_color(0); pdf.ln(0.5)
def para(t):
    pdf.set_font("D","",10.3); pdf.multi_cell(W,5.0,t); pdf.ln(1.2)
def bullet(label,t):
    pdf.set_font("D","B",10.3); pdf.set_x(pdf.l_margin+3)
    pdf.cell(0,5,"•  ",) ;
    pdf.set_x(pdf.l_margin+7)
    x=pdf.get_x(); y=pdf.get_y()
    pdf.set_font("D","B",10.3); pdf.write(5,label+"  ")
    pdf.set_font("D","",10.3); pdf.write(5,t); pdf.ln(6); pdf.ln(0.6)
def img(path,cap,w=None):
    w = w or W
    pdf.image(os.path.join(HERE,path), w=w, x=(pdf.w-w)/2)
    pdf.ln(1); pdf.set_font("D","I",8.6); pdf.set_text_color(90)
    pdf.multi_cell(W,4,cap); pdf.set_text_color(0); pdf.ln(2)

# ---- title ----
pdf.set_font("D","B",20); pdf.set_text_color(15,25,55)
pdf.multi_cell(W,9,"juliaMotor — Project Report"); pdf.set_text_color(0)
pdf.set_font("D","",11.5); pdf.set_text_color(70)
pdf.multi_cell(W,6,"A Julia physics engine reproducing rFactor's isiMotor, toward racing with Julia-controlled car motion")
pdf.set_font("D","",9.5); pdf.set_text_color(120); pdf.multi_cell(W,5,"2026-06-06")
pdf.set_text_color(0); pdf.ln(2)

h1("1.  The goal")
para("Replace rFactor 1's isiMotor 2 physics engine with an acausal, Modelica-style "
"vehicle-dynamics engine written in Julia, calibrated to reproduce rFactor's behaviour "
"from rFactor's own data, and ultimately to race on a track with the car's motion "
"computed entirely by the Julia engine — as a standalone Linux application that reuses "
"rFactor's cars and tracks.")
para("The work is grounded throughout in the working rFactor install (running under Wine) "
"and in four telemetry sessions the owner drove (Monaco 1967 and three Zandvoort 1967 "
"stints, logged at 10–50 Hz by the rFactor DAQ plugin). Those laps are the ground truth "
"every calibration and validation step is measured against.")

h1("2.  Approach")
para("isiMotor's physics is almost entirely data-driven: chassis, tyres, suspension, engine "
"and gearing live in plain-text files, and the meshes/textures in lightly-obfuscated binary "
"archives. So this is a system-identification problem, not a binary reverse-engineering one: "
"parse the files as the single source of truth, build matching physics components, and "
"validate their outputs against the driven telemetry. Where a component's behaviour isn't "
"fully determined by the files, explicit calibration knobs absorb the residual, and their "
"fitted size measures how close the model is.")

h1("3.  What has been done")
para("All of the following is implemented, tested, and validated against the owner's "
"telemetry — three Julia packages, ~10,600 passing tests total.")
para("Data layer (RFactorData): parsers for every rFactor format — chassis (HDV), tyres (TBC), "
"suspension multibody (PM), engine/gears (INI), car wiring (VEH/GEN/SVM), track "
"waypoints/events (AIW/GDB). The two binary formats were reverse-engineered from scratch: "
"the MAS archive (all 274 in the install extract) and the GMT mesh (full track geometry, "
"260/260 meshes of a track, ~12k triangles). All 1,172 cars resolve end-to-end.")

h2("Physics components — each bench- and telemetry-validated")
rows = [
 ("Tyre (TBC slip-curve + load/speed peak shift)","measured grip within model μ-envelope; driver reaches 98–99% of peak"),
 ("Engine (RPM–torque map)","270 hp @ 7500 rpm — the historical Vanwall figure"),
 ("Drivetrain","all 5 gear ratios match logged RPM÷wheel-speed to 4 sig figs"),
 ("Brakes","bias convention pinned; ~0.69 g, torque-limited (period drums)"),
 ("Suspension (PM multibody solver)","De Dion & Chapman kinematics exact; 484/484 corners solve"),
 ("Aero drag","BodyDragBase confirmed a CdA coefficient (½ρv² convention)"),
]
pdf.set_font("D","",9.3)
c1=64
for a,b in rows:
    y=pdf.get_y()
    if y > pdf.h-30: pdf.add_page()
    x=pdf.l_margin
    pdf.set_xy(x,y); pdf.set_font("D","B",9.2); pdf.multi_cell(c1,4.4,a,border=0)
    y2=pdf.get_y()
    pdf.set_xy(x+c1,y); pdf.set_font("D","",9.2); pdf.multi_cell(W-c1,4.4,b,border=0)
    pdf.set_y(max(y2,pdf.get_y())); pdf.ln(1)
pdf.ln(1)
para("Calibration: Phase-3 lateral calibration (Nelder–Mead over re-anchored yaw-replay "
"windows) reduced holdout yaw-rate error from 0.12 to 0.07 rad/s.")
para("Capstone validation (Figure 2): the complete coupled engine — longitudinal + lateral "
"+ yaw with load transfer — driven from only the logged steer/throttle/brake/gear "
"(nothing taken from telemetry), re-anchored every 5 s: speed RMS ≈ 3 km/h (correlation "
"0.99) and yaw-rate RMS ≈ 0.06 rad/s against a 0.31 rad/s signal. This is the engine "
"reproducing a real lap.")
para("Track surface (HAT): TriangleHAT builds the collision surface from the actual "
"HATTarget meshes and answers height/normal under each tyre by exact point-in-triangle — "
"median 0.10 m, p90 0.13 m versus the racing line, no ambiguity tail.")
para("Simulator: a track-relative (Frenet) integrator drives the calibrated car around a "
"track with a racing-line controller; it completes a full, on-track lap of Zandvoort "
"(Figure 1) at a deliberately conservative pace.")

img("track_render.png","Figure 1.  The Julia engine driving the Vanwall around Zandvoort, on track geometry extracted from rFactor's own files (road grey, grass green, gravel tan). Frame from zandvoort_lap.mp4.")
img("validation_plot.png","Figure 2.  Capstone validation: the full engine driven from only the owner's logged inputs (re-anchored every 5 s). Orange = measured, green = predicted. The small vertical steps in green are the 5-second re-anchor resets — an artifact of the measurement method, not the engine; in closed-loop driving the engine integrates continuously with no resets.")

h1("4.  Where this leaves us")
para("Everything that turns rFactor files → calibrated physics → an accurate, queryable "
"track surface exists and is validated. Phases 0–3 of the original plan are complete, and "
"the data/surface foundations of the standalone app (Phase 4) are built. What remains is "
"the engineering to turn the validated engine into an actual racing experience.")

h1("5.  What remains — the path to the goal")
para("The goal (race on a track, Julia-controlled motion) decomposes into five workstreams. "
"They are largely independent and can be sequenced by which end-experience is wanted first.")
bullet("A. Driver / AI controller.","The current racing-line driver completes a lap only at a conservative pace. A realistic-pace, robust driver is needed for AI opponents and credible hot-laps. The feasible-speed foundation (qss_speed_profile, a friction-circle lap-optimal profile) is built and proven; remaining is a well-damped path/speed tracker (LQR/MPC-class) plus a low-speed regime. Not needed if only a human drives.")
bullet("B. Real-time loop + input.","For a human to drive, the engine must run at a fixed ~400 Hz step reading a wheel/joystick (SDL2) and producing force-feedback (the steering-arm force the suspension already computes). The plain-Julia components are far from a performance limit, so real-time is expected to be straightforward.")
bullet("C. Rendering.","Either a minimal OpenGL renderer using the extracted GMT meshes + DDS textures — needing the remaining GMT UV/material extraction (geometry done; UVs a bounded follow-on) — or the headless route already demonstrated: render to video, or drive rFactor itself as a replay viewer.")
bullet("D. Race logic.","Multiple cars, a start grid (from the AIW), lap/sector timing (waypoint crossings, already available), basic flags, fuel/tyre wear (already modelled). This is what makes it racing rather than a hot-lap.")
bullet("E. Audio + polish (optional).","RPM-pitched engine sound from the .sfx samples, skids, gear changes.")
para("Remaining calibration refinements (none block the above): attribute the constant "
"longitudinal-loss term (needs one long-straight telemetry session — pending); a richer "
"tyre-load model to close the self-contained yaw gap; brake-temperature response.")

h1("6.  Choice points")
para("These decisions shape the remaining route. None are forced yet; each trades effort for "
"a different end-experience.")
bullet("C1 — Human or AI first?","Human-first prioritises B + C: you drive the Julia car sooner, with simple/no AI — the more visceral demo. AI-first prioritises A + D: cars racing each other, watched as video/replay, with no input/FFB to build — reuses more of what's validated.")
bullet("C2 — Rendering strategy.","(a) Custom OpenGL renderer: full control, near-identical look achievable (gauges/meshes/textures are all data), but the largest new subsystem. (b) rFactor as replay viewer via .vcr files: very high fidelity for low effort, but .vcr is proprietary binary and a bad file can crash rFactor (a real RE subproject, not attempted). (c) Headless/video: already working, fine for demos, not live play. Pragmatic order: (c) now → (a) for the standalone, (b) optional.")
bullet("C3 — Controller class.","Current Stanley + spin-catch is simple but fragile at the limit. Options: QSS-optimal profile + tuned tracker (foundation built; recommended), MPC (highest fidelity, most effort), or a learned racing line.")
bullet("C4 — Physics fidelity for real-time.","Keep the validated single-track (bicycle) model (fast, ~3 km/h / 0.06 rad/s accurate), or move to the full four-corner PM multibody suspension (higher fidelity, must hit 400 Hz). A two-tier design — multibody as reference, bicycle/lookup as real-time engine — is the safe default.")
bullet("C5 — Scope of racing.","Single-car hot-lap vs full grid; one car/track vs many. Parsers already handle the whole install (1,172 cars, 68 tracks), so breadth is cheap; cost is in A and D. Sensible MVP: one AI opponent on one track, then scale.")
bullet("C6 — Where the loop lives.","Pure Julia for the whole real-time + render loop, or Julia physics core + a thin renderer/input layer in another language. Physics is already pure Julia and fast; this only affects B/C.")

h1("7.  Recommended next step")
para("Because the physics and the track surface are validated and accurate, the highest-value, "
"lowest-risk milestone is a real-time, human-drivable loop (C1 human-first) with the "
"headless/video or a minimal renderer (C2 c→a): it makes the validated engine immediately "
"tangible and exercises the 400 Hz path, input and FFB — after which AI opponents (A + D) "
"turn it into racing. The QSS-fed tracker (A/C3) is the recommended parallel solo track, "
"since it needs no new hardware and unlocks both AI and realistic hot-laps.")
para("Pending from the owner: one long-straight telemetry session closes the last open "
"calibration item (the constant longitudinal-loss term).")

out = os.path.join(HERE,"juliaMotor_report.pdf")
pdf.output(out)
print("wrote", out, os.path.getsize(out), "bytes,", pdf.page_no(), "pages")
