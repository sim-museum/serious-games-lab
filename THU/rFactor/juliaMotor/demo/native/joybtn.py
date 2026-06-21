#!/usr/bin/env python3
"""Capture two shift-paddle buttons in order (up first, then down) via GLFW/joyserver.
Reports the 1-based GLFW button indices to write into joystick.conf."""
import json, subprocess, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
julia = os.path.expanduser("~/.juliaup/bin/julia")
if not os.path.exists(julia):
    julia = "julia"

p = subprocess.Popen([julia, "--project=.", "joyserver.jl", "1"], cwd=HERE,
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)

DUR = 35.0
events = []          # ordered list of button indices pressed (rising edge)
prev = None
t0 = None
print("waiting for stream…", file=sys.stderr, flush=True)
for line in p.stdout:
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    if not d.get("present"):
        continue
    bs = d.get("buttons", [])
    now = time.time()
    if t0 is None:
        t0 = now
        prev = list(bs)
        print(f"streaming {len(bs)} buttons — pull UP paddle, then DOWN paddle", file=sys.stderr, flush=True)
    for i, v in enumerate(bs):
        if i < len(prev) and v and not prev[i]:     # rising edge
            if not events or events[-1][0] != i:
                events.append((i, now - t0))
    prev = list(bs)
    if now - t0 > DUR:
        break
p.kill()

print("\n=== button presses (in order) ===")
for i, t in events:
    print(f"  t={t:5.1f}s   button {i+1}")
if len(events) >= 2:
    print(f"\nSUGGEST  up_btn {events[0][0]+1}   dn_btn {events[1][0]+1}")
elif len(events) == 1:
    print(f"\nonly one press seen: button {events[0][0]+1}")
else:
    print("\nno button presses detected")
print("Done.")
