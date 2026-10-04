#!/usr/bin/python3
"""
patchWineDinputFFB.py [RUNNER_DIR]

Fixes force feedback in GPL (and any DirectInput game) under the Lutris "TkG" Wine 5.7 builds.

These builds carry a hot-plug patch in dinput's joy_polldev(): any poll() failure counts as an unplug,
and dinput closes the wheel's /dev/input/event* and reopens it. Wine itself interrupts poll() with
SIGUSR1 (thread suspension) all the time, so the poll fails with EINTR every few seconds to minutes.
The close erases every force-feedback effect uploaded through that fd (the kernel's evdev flush), but
dinput keeps updating the old effect ids, and every update fails with EINVAL. Symptom: force feedback
for the first seconds on track, then nothing until GPL is restarted.

The fix turns the "poll() == -1 -> disconnect" branch into "return, poll again next frame" (the
conditional jump at 0x31d8b becomes six NOPs). A genuinely unplugged wheel is still detected, because
the read() that follows fails with ENODEV and takes its own reconnect branch.

The file is patched only if it is byte-identical (SHA-256) to the dinput.dll.so of Lutris'
lutris-5.7-x86_64 release, which install.sh downloads. An already patched or unknown file is left
alone. A backup is kept beside it as dinput.dll.so.orig-before-eintr-patch.
"""
import hashlib, os, shutil, sys

ORIGINAL = "ce7138be756f3a58c0df7b7dbc6b7c0aef9ffa0880dad2b4078a4724af5c377f"
PATCHED = "78e232b02bc7d867dd0ae030f60e4e64aaa6a16a5d0ef855866082612f53a980"
OFFSET, OLD, NEW = 0x31d8b, bytes.fromhex("0f84ff000000"), b"\x90" * 6

def main():
    runner = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.expanduser("~/.local/share/lutris/runners/wine/lutris-5.7-x86_64")
    dll = os.path.join(runner, "lib", "wine", "dinput.dll.so")
    if not os.path.isfile(dll):
        print(f"patchWineDinputFFB: no {dll}, nothing to do")
        return
    data = bytearray(open(dll, "rb").read())
    sha = hashlib.sha256(data).hexdigest()
    if sha == PATCHED:
        print("patchWineDinputFFB: dinput already patched")
        return
    if sha != ORIGINAL or data[OFFSET:OFFSET + 6] != OLD:
        print(f"patchWineDinputFFB: {dll} is not the known Wine 5.7 TkG build, left unchanged")
        return
    backup = dll + ".orig-before-eintr-patch"
    if not os.path.exists(backup):
        shutil.copy2(dll, backup)
    data[OFFSET:OFFSET + 6] = NEW
    assert hashlib.sha256(data).hexdigest() == PATCHED
    tmp = dll + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    shutil.copymode(dll, tmp)
    os.replace(tmp, dll)
    print("patchWineDinputFFB: patched dinput (force feedback no longer dropped); backup at", backup)

if __name__ == "__main__":
    main()
