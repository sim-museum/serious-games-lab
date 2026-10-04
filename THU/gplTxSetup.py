#!/usr/bin/python3
"""
gplTxSetup.py -- one-time setup of GPL's 1967x mod for a Thrustmaster TX wheel and a short Watkins Glen race.

Run after gpl.sh has installed GPL (with GEM+ and GPL closed). Every file it changes is backed up first
as <file>.bak-gplTxSetup (only the first time, so the stock file stays recoverable).

  1. Controls: installs gplTxProfile/67x__Driver/controls.cfg, the TX calibration for the "Driver 67x"
     player. Steering reaches full lock at about +-117 deg of wheel (GPL was designed for 120-270 deg
     wheels; pair it with a ~12:1 steering ratio in the car setup). Throttle/clutch/brake are bound to
     the TX's Y/Z/Rz as pedals resting at the bottom of their axes, which gplTxWheel.py (run by gpl.sh)
     arranges. Brake reaches full at about 60 % of a hard press.
  2. GEM+: enables the Ffb2 force-feedback option for the 67x exe (GPL067.exe).
  3. core.ini: force-feedback damping 8 and max steering torque 200 (stronger steering cue).
  4. Watkins Glen race: 32 laps in 67season.ini, so a Novice race (about 10 % of the laps) runs 3
     laps. AI speed coefficient 0.774 in tracks/watglen/track67.ini (fastest AI lap about 1:40;
     1.108 gives about 1:10; the stock value is 1.024).

The force-feedback fix itself (patchWineDinputFFB.py) and the pedal flip (gplTxWheel.py) run from gpl.sh
on every launch; nothing here is needed for them.
"""
import os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WP = os.path.join(HERE, "WP", "drive_c")
GPL = os.path.join(WP, "Sierra", "GPL")
GEM_INI = os.path.join(WP, "Program Files", "GPLSecrets", "GEM+", "GEM.ini")
LAPS, AI_COEFF = 32, 0.774

def backup(path):
    b = path + ".bak-gplTxSetup"
    if not os.path.exists(b):
        shutil.copy2(path, b)

def edit(path, fn, what):
    if not os.path.isfile(path):
        print(f"  SKIP {what}: {path} not found")
        return
    raw = open(path, "rb").read().decode("latin-1")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(nl)
    new = fn(lines)
    if new is None:
        print(f"  SKIP {what}: expected entry not found in {path}")
        return
    if new != lines:
        backup(path)
        open(path, "wb").write(nl.join(new).encode("latin-1"))
        print(f"  OK   {what}")
    else:
        print(f"  OK   {what} (already set)")

def set_key(lines, section_pred, key, value_line):
    """Replace `key = ...` inside the first section whose header matches section_pred."""
    inside = False
    for i, l in enumerate(lines):
        if l.startswith("["):
            inside = section_pred(l)
            continue
        if inside and re.match(rf"\s*{re.escape(key)}\s*=", l):
            out = list(lines); out[i] = value_line
            return out
    return None

def season(lines):
    # find the event block whose trackDirectory is watglen, then its numberOfLaps line
    start = None
    for i, l in enumerate(lines):
        if l.startswith("["):
            start = i
        if l.strip().lower() == "trackdirectory=watglen" and start is not None:
            for j in range(start + 1, len(lines)):
                if lines[j].startswith("["):
                    break
                if lines[j].startswith("numberOfLaps="):
                    out = list(lines); out[j] = f"numberOfLaps={LAPS}"
                    return out
    return None

def gem(lines):
    hdr = r"[ C:\Sierra\GPL\GPL067.exe ]"
    if hdr not in lines:
        return None
    i = lines.index(hdr) + 1
    j = i
    while j < len(lines) and lines[j].strip() and not lines[j].startswith("["):
        if lines[j].replace(" ", "").lower() == "option:ffb2=-1":
            return lines
        j += 1
    return lines[:j] + ["Option:Ffb2 = -1"] + lines[j:]

def main():
    if not os.path.isdir(GPL):
        sys.exit(f"GPL not installed at {GPL}; run gpl.sh first")
    print("gplTxSetup: Thrustmaster TX + Watkins Glen setup for the 1967x mod")
    dst = os.path.join(GPL, "players", "67x__Driver", "controls.cfg")
    if os.path.isdir(os.path.dirname(dst)):
        if os.path.exists(dst):
            backup(dst)
        shutil.copy2(os.path.join(HERE, "gplTxProfile", "67x__Driver", "controls.cfg"), dst)
        print("  OK   TX controls for Driver 67x")
    else:
        print(f"  SKIP TX controls: {os.path.dirname(dst)} not found")
    edit(GEM_INI, gem, "GEM+ Ffb2 option for GPL067.exe (if skipped: tick Ffb2 in GEM+ once)")
    joy = lambda l: l.strip().lower().startswith("[ joy")
    edit(os.path.join(GPL, "core.ini"),
         lambda L: (lambda a: a and set_key(a, joy, "max_steering_torque",
             "max_steering_torque = 200.000000              ; steering torque in N*in giving max device force - Default = 225.0 (200: stronger dynamic steering cue, with damping cut so it's not masked)"))(
             set_key(L, joy, "force_feedback_damping",
             "force_feedback_damping = 8.0000000            ; force feedback damping coefficient - Default = 40.0 (cut: 40 felt stiff/heavy & masked the steering cue)")),
         "core.ini force-feedback damping/torque")
    edit(os.path.join(GPL, "seasons", "67season.ini"), season, f"Watkins Glen {LAPS} laps (Novice race = 3 laps)")
    edit(os.path.join(GPL, "tracks", "watglen", "track67.ini"),
         lambda L: set_key(L, lambda h: h.strip() == "[ GP ]", "dlong_speed_adj_coeff",
                           f"dlong_speed_adj_coeff = {AI_COEFF:.6f} ; default: 1.024"),
         f"Watkins Glen AI speed {AI_COEFF} (fastest AI lap ~1:40)")
    print("Done. In GEM+: carset 1967x, Driver 67x, Watkins Glen, Novice race.")

if __name__ == "__main__":
    main()
