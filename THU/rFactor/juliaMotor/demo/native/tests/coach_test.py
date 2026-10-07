# REPLAY-2 S4: the coaching analysis -- the summary (corners from the reference's speed trace, every metre attributed so
# the corner times add up to the lap difference) and the CLI plumbing, against a FAKE `claude` on PATH: nothing is sent
# anywhere by this test. Run by JuliaMotorMTK/tools/launcher_smoke.jl (Qt offscreen).
import sys, os, json, math, re, struct, tempfile, stat, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import analyser as A, coach as C

ok = True
def check(c, msg):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + msg)

# a 1000 m lap with two corners (speed dips at 300 m and 700 m); the player is 10 km/h slower at the second one
L = 1000.0; R = L / (2 * math.pi); FPS = 15
TP = ["lap", "lapdist", "speed", "throttle", "brake", "steer", "clutch", "gear", "rpm", "lateral", "ontrack", "race"]
TA = ["s", "speed", "lap", "lane"]
def vprof(d, slow):
    v = 60.0 - 30.0 * math.exp(-((d - 300) / 60) ** 2) - (30.0 + slow) * math.exp(-((d - 700) / 60) ** 2)
    return v                                   # m/s: 60 on the straights, 30 / (20 for the player) at the back bend
hdr = {"format": "jrt", "version": 1, "track": "synthetic", "laplen": L, "line_total": L, "fps": FPS, "ncar": 2, "nframes": 0,
       "names": ["You", "Clark (Lotus)"], "tele_player": TP, "tele_ai": TA, "final": True, "refline": [],
       "sections": [[0.0, "Main straight"], [250.0, "Hairpin"], [600.0, "Back bend"]], "carsetup": "ww103", "gearbox": "manual"}
rows = []; pos = [5.0, 2.0]; t = 0.0; laps = [0, 0]
while t < 60.0:
    row = [t]; tele = []
    for c, slow in enumerate((10.0, 0.0)):
        d = pos[c]; a = 2 * math.pi * d / L
        row += [R * math.cos(a), 0.0, R * math.sin(a), a + math.pi / 2]
        v = vprof(d, slow)
        tele += ([laps[c], d, v, 1.0 if v > 40 else 0.2, 0.0 if v > 40 else 0.6, 0.0, 0.0, 3, 6000, 0.0, 1, 1] if c == 0
                 else [d, v, laps[c], 0.0])
    rows.append(row + tele)
    for c, slow in enumerate((10.0, 0.0)):
        pos[c] += vprof(pos[c], slow) / FPS
        if pos[c] >= L: pos[c] -= L; laps[c] += 1
    t += 1 / FPS
hdr["nframes"] = len(rows)
fd, path = tempfile.mkstemp(suffix=".jrt"); os.close(fd)
with open(path, "wb") as f:
    f.write((json.dumps(hdr) + "\n").encode())
    for r in rows: f.write(struct.pack("<%df" % len(r), *r))
rep = A.Replay(path)
s = C.build_summary(rep)
check("WW103" in s and "manual" in s, "summary names the setup and gearbox")
check("Hairpin (300 m)" in s and "Back bend (700 m)" in s, "corners found at 300 and 700 m, named from the sections")
you, ref = C.pick_laps(rep)
ts = [float(x) for x in re.findall(r"time ([+-][0-9.]+) s", s)]
check(abs(sum(ts) - (you.time - ref.time)) < 0.1, f"corner times add up to the lap difference ({sum(ts):.2f} vs {you.time - ref.time:.2f})")
check(ts[1] > 0.3 and abs(ts[0]) < 0.1, f"the loss is at the slower corner ({ts})")
check(re.search(r"Back bend \(700 m\): min speed 72 vs 108", s) is not None, "minimum speeds at the corner (72 vs 108 km/h)")
check("Biggest losses: Back bend" in s, "biggest loss named")

# the CLI: a fake `claude` that records its arguments and stdin and answers in Markdown
fake = tempfile.mkdtemp(prefix="fakeclaude_"); log = os.path.join(fake, "call.json")
with open(os.path.join(fake, "claude"), "w") as f:
    f.write("#!/usr/bin/env python3\nimport sys, json\ninp = sys.stdin.read()\n"
            f"json.dump({{'argv': sys.argv[1:], 'stdin': inp}}, open({log!r}, 'w'))\n"
            "print('## Coaching\\n- **Back bend**: brake later.')\n")
os.chmod(os.path.join(fake, "claude"), 0o755)
os.environ["PATH"] = fake + os.pathsep + os.environ["PATH"]
d = C.CoachDialog(rep)
check(d.send_b.isEnabled(), "Send is enabled when the CLI exists")
check(not os.path.exists(log), "nothing is sent before Send")
d.send()
t0 = time.time()
while d.proc.state() != d.proc.ProcessState.NotRunning and time.time() - t0 < 20:
    app.processEvents(); time.sleep(0.02)
app.processEvents()
call = json.load(open(log))
check(call["argv"] == ["-p", "--tools", "", "--no-session-persistence", "--output-format", "text"], f"no tools, no saved session ({call['argv']})")
check(s in call["stdin"] and call["stdin"].startswith("You are a racing driving coach"), "the prompt carries exactly the shown summary")
check("Back bend" in d.answer.toPlainText() and d.status.text() == "Done.", "the answer is shown")
os.environ["PATH"] = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep) if p != fake)
import shutil as _sh
if _sh.which("claude") is None:
    d2 = C.CoachDialog(rep); check(not d2.send_b.isEnabled(), "without the CLI, Send is disabled and says why")
os.remove(path)
print("COACH:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
