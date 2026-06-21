#!/usr/bin/env python3
"""Minimal Linux evdev force-feedback test: upload an FF_CONSTANT effect and play it
right, then left, so you can feel the wheel pull. Proves the hid-tmff2 FFB path works
end-to-end. Also the reference for the Julia FFB writer in Stage 2.

Usage:  python3 ffbtest.py [/dev/input/eventN] [strength 0..1] [seconds]
"""
import ctypes, fcntl, struct, sys, time, glob, os

# ---- find the Thrustmaster event node ----
dev = sys.argv[1] if len(sys.argv) > 1 else None
if not dev:
    for e in sorted(glob.glob("/sys/class/input/event*/device/name")):
        try:
            if "Thrustmaster" in open(e).read():
                dev = "/dev/input/" + e.split("/")[4]
                break
        except OSError:
            pass
if not dev:
    print("no Thrustmaster event device found"); sys.exit(1)
STR = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
SEC = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
print(f"device={dev}  strength={STR}  seconds={SEC}")

# ---- struct ff_effect (linux/input.h) ----
u16, s16, u32 = ctypes.c_uint16, ctypes.c_int16, ctypes.c_uint32
class envelope(ctypes.Structure):
    _fields_ = [("attack_length", u16), ("attack_level", u16),
                ("fade_length", u16), ("fade_level", u16)]
class constant(ctypes.Structure):
    _fields_ = [("level", s16), ("envelope", envelope)]
class ramp(ctypes.Structure):
    _fields_ = [("start_level", s16), ("end_level", s16), ("envelope", envelope)]
class periodic(ctypes.Structure):
    _fields_ = [("waveform", u16), ("period", u16), ("magnitude", s16), ("offset", s16),
                ("phase", u16), ("envelope", envelope), ("custom_len", u32),
                ("custom_data", ctypes.c_void_p)]
class condition(ctypes.Structure):
    _fields_ = [("right_saturation", u16), ("left_saturation", u16),
                ("right_coeff", s16), ("left_coeff", s16),
                ("deadband", u16), ("center", s16)]
class rumble(ctypes.Structure):
    _fields_ = [("strong_magnitude", u16), ("weak_magnitude", u16)]
class effect_u(ctypes.Union):
    _fields_ = [("constant", constant), ("ramp", ramp), ("periodic", periodic),
                ("condition", condition * 2), ("rumble", rumble)]
class ff_effect(ctypes.Structure):
    _fields_ = [("type", u16), ("id", s16), ("direction", u16),
                ("trigger_button", u16), ("trigger_interval", u16),
                ("replay_length", u16), ("replay_delay", u16), ("u", effect_u)]

FF_CONSTANT = 0x52
EV_FF = 0x15

def IOW(nr, size):           # _IOW('E', nr, size)
    return (1 << 30) | (size << 16) | (0x45 << 8) | nr
EVIOCSFF = IOW(0x80, ctypes.sizeof(ff_effect))
EVIOCRMFF = IOW(0x81, ctypes.sizeof(ctypes.c_int))

def play(fd, direction, level):
    eff = ff_effect()
    eff.type = FF_CONSTANT
    eff.id = -1                       # kernel assigns
    eff.direction = direction         # 0x4000=left, 0xC000=right (16-bit angle)
    eff.replay_length = int(SEC * 1000)
    eff.replay_delay = 0
    eff.u.constant.level = level      # -0x7fff..0x7fff
    fcntl.ioctl(fd, EVIOCSFF, eff)    # fills eff.id
    fcntl.ioctl  # noop ref
    os.write(fd, struct.pack("llHHi", 0, 0, EV_FF, eff.id, 1))   # play once
    time.sleep(SEC + 0.1)
    os.write(fd, struct.pack("llHHi", 0, 0, EV_FF, eff.id, 0))   # stop
    fcntl.ioctl(fd, EVIOCRMFF, eff.id)   # id passed BY VALUE, not as a pointer
    return eff.id

fd = os.open(dev, os.O_RDWR)
lvl = int(STR * 0x7fff)
print("→ pulling RIGHT …");  play(fd, 0xC000, lvl); time.sleep(0.3)
print("→ pulling LEFT  …");  play(fd, 0x4000, lvl)
os.close(fd)
print("done — did the wheel pull each way?")
