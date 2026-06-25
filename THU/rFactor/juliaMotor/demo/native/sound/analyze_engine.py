#!/usr/bin/env python3
"""Track engine RPM through the iRacing Lotus 49 recording and find steady-RPM
plateaus we can cut into looping engine-sound samples.

The Lotus 49's Cosworth DFV is a 90deg V8: 4 firing pulses per crank revolution
(4-stroke, 8 cyl), so the dominant exhaust periodicity is the 4th order =>
f_fire = 4*RPM/60 = RPM/15 Hz.  We find the fundamental of each short window by
autocorrelation and report RPM = 15 * f_fire, plus loudness and a confidence
(normalized autocorrelation peak).  Then we segment into stable plateaus.

  python3 analyze_engine.py /tmp/lotus49_eng.wav
"""
import sys, numpy as np
from scipy.io import wavfile

def load(path):
    sr, x = wavfile.read(path)
    if x.ndim > 1: x = x.mean(1)
    x = x.astype(np.float64)
    x /= (np.abs(x).max() + 1e-9)
    return sr, x

def rpm_track(sr, x, hop=0.02, win=0.08, fmin=60.0, fmax=720.0):
    """Per-frame fundamental via autocorrelation; RPM = 15*f_fire."""
    H = int(hop*sr); W = int(win*sr)
    lo = int(sr/fmax); hi = int(sr/fmin)
    nfr = (len(x)-W)//H
    t = np.empty(nfr); rpm = np.empty(nfr); conf = np.empty(nfr); rms = np.empty(nfr)
    for i in range(nfr):
        s = x[i*H:i*H+W]
        r = np.sqrt((s*s).mean())
        s = s - s.mean()
        ac = np.correlate(s, s, "full")[W-1:]          # autocorr, lag>=0
        ac0 = ac[0] + 1e-9
        seg = ac[lo:hi]
        if len(seg) == 0:
            lag = lo; c = 0.0
        else:
            k = np.argmax(seg) + lo
            lag = k; c = ac[k]/ac0
        f = sr/lag
        t[i] = (i*H + W/2)/sr
        rpm[i] = 15.0*f
        conf[i] = c
        rms[i] = r
    return t, rpm, conf, rms

def plateaus(t, rpm, conf, rms, min_len=0.6, rpm_tol=350.0, cmin=0.30):
    """Find contiguous steady-RPM, confident, audible windows."""
    good = (conf > cmin) & (rms > 0.04*rms.max())
    segs = []
    i = 0; n = len(t)
    while i < n:
        if not good[i]: i += 1; continue
        j = i+1; acc = [rpm[i]]
        while j < n and good[j] and abs(rpm[j]-np.median(acc)) < rpm_tol:
            acc.append(rpm[j]); j += 1
        if t[j-1]-t[i] >= min_len:
            segs.append((t[i], t[j-1], float(np.median(acc)),
                         float(np.std(acc)), float(rms[i:j].mean()), float(conf[i:j].mean())))
        i = j
    return segs

if __name__ == "__main__":
    path = sys.argv[1]
    sr, x = load(path)
    print(f"# {path}: {len(x)/sr:.1f}s @ {sr} Hz")
    t, rpm, conf, rms = rpm_track(sr, x)
    # coarse RPM histogram of confident frames
    m = conf > 0.30
    print(f"# confident frames: {m.sum()}/{len(t)}  RPM range "
          f"{np.percentile(rpm[m],2):.0f}..{np.percentile(rpm[m],98):.0f}")
    segs = plateaus(t, rpm, conf, rms)
    segs.sort(key=lambda s: s[2])
    print(f"# {len(segs)} steady plateaus (>=0.6s, conf>0.30):")
    print(f"#  {'t0':>7} {'t1':>7} {'rpm':>6} {'std':>5} {'rms':>5} {'conf':>5}  dur")
    for (t0,t1,r,sd,rr,cc) in segs:
        print(f"   {t0:7.2f} {t1:7.2f} {r:6.0f} {sd:5.0f} {rr:5.2f} {cc:5.2f}  {t1-t0:.2f}s")
