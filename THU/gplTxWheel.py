#!/usr/bin/python3
"""
gplTxWheel.py set|restore

Makes the Thrustmaster TX's pedals readable by GPL (run by gpl.sh around GEM+; no-op without a TX).

1. DIRECTION. The TX pedals rest at the TOP of their axes (raw 1023) and fall when pressed. GPL reads a
   pedal as the RISING half of its calibrated axis (its stock bindings: throttle = Y's low half, brake =
   Y's high half), so a released TX pedal reads as fully pressed -- rpm pinned at max in neutral, clutch
   held in, brake on. "set" flips the three pedal axes (throttle ABS_Y, clutch ABS_Z, brake ABS_RZ) so
   they rest at the bottom and rise when pressed.
2. BRAKE TRAVEL. The T3PA brake is a stiff rubber-cone pedal: a hard press only reaches ~660 of 0..1023,
   too little for GPL's controller assignment to notice. "set" also stretches it so BRAKE_FULL..1023 spans
   the whole axis.

Both changes are made to the evdev axis ranges, which Wine's DirectInput reads when GPL opens the wheel
(Wine maps the range linearly, so min > max inverts the axis). The duplicate joydev ("js") device is
hidden from Wine by a registry key (gpl.sh), so GPL sees one wheel. "restore" puts the kernel's ranges
back; a replug or reboot also does, so other programs (the Julia racer's TX calibration) see stock axes.
"""
import fcntl, os, re, struct, sys

BRAKE_FULL = 650           # raw brake value treated as 100 % (a hard press reaches ~660)
PEDALS = {1: 0, 2: 0, 5: BRAKE_FULL}   # ABS_Y throttle, ABS_Z clutch, ABS_RZ brake -> raw value at full press
FLAT = 63                  # hid-tmff2's default flat for the 0..1023 pedal axes

def tx_event():
    with open("/proc/bus/input/devices") as f:
        for block in f.read().split("\n\n"):
            if re.search(r'N: Name=".*Thrustmaster.*TX', block):
                h = re.search(r"H: Handlers=(.*)", block).group(1).split()
                return next((x for x in h if x.startswith("event")), None)
    return None

def evioc_abs(fd, code, write=None):
    if write is None:
        buf = bytearray(24)
        fcntl.ioctl(fd, (2 << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + code), buf)   # EVIOCGABS
        return struct.unpack("6i", buf)
    fcntl.ioctl(fd, (1 << 30) | (24 << 16) | (ord("E") << 8) | (0xC0 + code), struct.pack("6i", *write))  # EVIOCSABS

def main(mode):
    ev = tx_event()
    if ev is None:
        return
    fd = os.open("/dev/input/" + ev, os.O_RDWR)
    for code, full in PEDALS.items():
        val, mn, mx, fuzz, flat, res = evioc_abs(fd, code)
        if mode == "set":   # min = released (1023), max = full press: inverted, brake also stretched
            evioc_abs(fd, code, (val, 1023, full, fuzz, 0, res))
        else:
            evioc_abs(fd, code, (val, 0, 1023, fuzz, FLAT, res))
    os.close(fd)

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("set", "restore"):
        sys.exit(__doc__)
    main(sys.argv[1])
