#!/usr/bin/env python3
"""Cut looping engine-sound samples from the iRacing Lotus 49 recording at a set
of target RPMs, for the native app's RPM-crossfaded engine (audio.jl).

The Lotus 49's Cosworth DFV is a 90deg cross-plane V8: its exhaust note is the 4th
engine order (4 firing pulses per crank revolution), so the dominant spectral peak
is f_fire = 4*RPM/60 and RPM = 15*f_fire.  (An autocorrelation pitch-track instead
locks onto the 1st/2nd-order crank sub-harmonics and mis-labels the RPM by 2-4x —
so we detect RPM from the strongest SPECTRAL peak in the firing band 150-700 Hz.)

For each target RPM we scan the recording for the steadiest, loudest ~0.5 s window
whose firing peak sits near the target, trim it to a whole number of firing periods
and equal-power crossfade the seam so it loops seamlessly, then write a 44.1 kHz
mono WAV named by the DETECTED rpm (so audio.jl's 'natural' label is honest).

  python3 extract_samples.py <wav> [outdir] [--hist]
"""
import sys, os, numpy as np
from scipy.io import wavfile
from scipy.signal import resample

TARGETS = [2250, 3400, 4400, 5400, 6400, 8100, 9800]   # rpm samples to cut (populated bands)
FBAND   = (150.0, 720.0)   # firing-frequency search band (=> ~2250..10800 rpm)
CLIP    = 0.55             # source window length (s)
XFADE   = 0.05             # loop-seam crossfade (s)
OUT_SR  = 44100

def load(path):
    sr, x = wavfile.read(path)
    if x.ndim > 1: x = x.mean(1)
    x = x.astype(np.float64); x /= (np.abs(x).max()+1e-9)
    return sr, x

def fire_hz(s, sr, fband=FBAND):
    """Strongest spectral peak in the firing band -> (f_fire Hz, peak strength)."""
    w = s*np.hanning(len(s))
    X = np.abs(np.fft.rfft(w)); f = np.fft.rfftfreq(len(s), 1/sr)
    m = (f >= fband[0]) & (f <= fband[1])
    if not m.any(): return 0.0, 0.0
    Xb = X[m]; fb = f[m]
    j = int(np.argmax(Xb))
    # parabolic refine on the spectral peak
    fpk = fb[j]
    if 0 < j < len(Xb)-1:
        a, b, c = Xb[j-1], Xb[j], Xb[j+1]; d = a-2*b+c
        if abs(d) > 1e-9: fpk = fb[j] + 0.5*(a-c)/d*(fb[1]-fb[0])
    return fpk, Xb[j]/(X.mean()+1e-9)

def rpm_track(sr, x, hop=0.05, win=0.25):
    W = int(win*sr); H = int(hop*sr)
    n = (len(x)-W)//H
    t = np.empty(n); rpm = np.empty(n); st = np.empty(n); rms = np.empty(n)
    for i in range(n):
        s = x[i*H:i*H+W]
        f, strength = fire_hz(s, sr)
        t[i] = (i*H+W/2)/sr; rpm[i] = 15*f; st[i] = strength
        rms[i] = np.sqrt(np.dot(s,s)/W)
    return t, rpm, st, rms

def best_window(sr, x, t, rpm, st, rms, target, tol=0.06):
    """Steadiest, loudest window whose firing peak is within tol of target."""
    glob = np.sqrt((x*x).mean())
    W = int(CLIP*sr)
    best = None
    near = np.where(np.abs(rpm-target) < tol*target)[0]
    for k in near:
        i = int(t[k]*sr - W/2)
        if i < 0 or i+W >= len(x): continue
        s = x[i:i+W]
        r = np.sqrt(np.dot(s,s)/W)
        if r < 0.6*glob: continue
        # steadiness: firing peak of the two halves should agree
        f1,_ = fire_hz(s[:W//2], sr); f2,_ = fire_hz(s[W//2:], sr)
        if f1<=0 or f2<=0: continue
        drift = abs(f1-f2)/(0.5*(f1+f2))
        if drift > 0.05: continue
        score = st[k] - 3.0*drift + 0.4*min(r/glob,3.0)
        if best is None or score > best[0]:
            f,_ = fire_hz(s, sr)
            best = (score, i, sr/f, 15*f, r, drift)   # period in samples
    return best

def make_loop(x, i, period, sr):
    nper = max(6, int((CLIP*sr - XFADE*sr)//period))
    L = nper*period
    xf = int(XFADE*sr)
    seg = x[i:i+L+xf].copy()
    head = seg[:xf].copy(); tail = seg[L:L+xf].copy()
    n = min(len(head), len(tail))
    out = seg[:L].copy()
    if n > 8:
        w = np.linspace(0, np.pi/2, n); a = np.cos(w); b = np.sin(w)
        out[:n] = b*head[:n] + a*tail[:n]
    return out

def write_wav(path, s, sr):
    if sr != OUT_SR: s = resample(s, int(len(s)*OUT_SR/sr))
    s = s/(np.abs(s).max()+1e-9)*0.92
    wavfile.write(path, OUT_SR, (s*32767).astype(np.int16))

if __name__ == "__main__":
    path = sys.argv[1]
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    outdir = args[0] if args else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(outdir, exist_ok=True)
    sr, x = load(path)
    print(f"# {path}: {len(x)/sr:.0f}s @ {sr}Hz")
    t, rpm, st, rms = rpm_track(sr, x)
    good = (st > np.percentile(st,60)) & (rms > 0.5*np.sqrt((x*x).mean()))
    if "--hist" in sys.argv:
        h, e = np.histogram(rpm[good], bins=np.arange(1500, 11000, 500))
        print("# RPM histogram of strong/steady frames (firing-band spectral):")
        for c, lo in zip(h, e): print(f"   {lo:5.0f}-{lo+500:5.0f}: {'#'*int(40*c/max(h.max(),1))} {c}")
    made = []
    for tg in TARGETS:
        b = best_window(sr, x, t, rpm, st, rms, tg)
        if b is None:
            print(f"  {tg:5d} rpm: no steady window"); continue
        score, i, period, det, r, drift = b
        loop = make_loop(x, i, int(round(period)), sr)
        lbl = int(round(det/50)*50)
        fn = os.path.join(outdir, f"lotus_{lbl}.wav")
        write_wav(fn, loop, sr)
        print(f"  {tg:5d} rpm: t={i/sr:7.2f}s firing={sr/period:5.1f}Hz detRPM={det:5.0f} "
              f"drift={drift*100:.1f}% rms={r:.2f} loop={len(loop)/sr*1000:.0f}ms -> {os.path.basename(fn)}")
        made.append((lbl, fn))
    print(f"# {len(made)} samples written")
