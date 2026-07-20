# STATUS 2026-07-19 — Mig Alley: black screen + hang on 3D entry

Fresh Ubuntu 26.04 install (GNOME on **Wayland**, NVIDIA 595, GTX 1660 SUPER,
dual 1920x1080). Mig Alley installs, the 2D UI works, mission selection works —
then entering 3D gives a black screen and GNOME's "application is not
responding / Wait / Force Quit" dialog.

Reproduced from the launcher: MA → single mission → fly.

## Confirmed: the engine spins in its own code

Captured with `scripts/dump_mig_stack.sh` (added today) **while hung**:

```
cpu sample 1: utime=2749 stime=137
cpu sample 2: utime=3148 stime=142     <- 2 seconds later
```

399 jiffies of user CPU in 2 s of wall clock ≈ **200%** — two threads pegged.
It is **spinning, not blocked**. Nothing is waiting on wineserver, the GPU, or
a message.

Stacks (addresses resolved by image range; Mig.exe is based at `0x400000`,
mfc42 at `0x5f400000`):

```
Thread 1   0x005197f8 <- 0x004f603c                    Mig.exe's own code
Thread 3   0x0040e3f1 <- 0x00418eda <- 0x5f410185      via mfc42+0x10185
                      <- 0x7b62ddd0 (kernel32) <- 0x7bc5dd07 (ntdll)
```

Both spinning threads are inside **Mig.exe**, one reached through an MFC42
window-procedure path. Nothing is stuck in wine, ddraw, or the driver.

This is the failure mode `migAlley.sh` already describes — *"the engine spins
on Mig.exe resource remap during 'Loading landscape'"* — but reached by a
different trigger (see below).

### The game does reach 3D

An earlier run with `WINEDEBUG=+ddraw,warn+d3d` produced 34,026 ddraw/d3d
lines and was still actively rendering when force-quit:

```
ddraw_surface1_Lock ... DDSCAPS_OFFSCREENPLAIN DDSCAPS_3DDEVICE
                        DDSCAPS_VIDEOMEMORY DDSCAPS_LOCALVIDMEM
DDSD_HEIGHT : 1060   DDSD_WIDTH : 1310   DDSD_PITCH : 5240
d3d_execute_buffer_Lock  dwBufferSize : 16384
```

Note the engine CPU-locks **video-memory** surfaces every frame, which is a
known stall pattern (each lock round-trips the GPU). Whether that alone
accounts for the symptom is not established — that run was confounded, since
WINEDEBUG tracing is itself very expensive.

**Caveat on an earlier misreading:** a first, untraced run showed no
ddraw/d3d lines and that was briefly taken as "3D never initialised". Wrong —
those are trace channels, off by default. Their absence meant nothing.

## Ruled out

- **The documented cause of this spin.** `migAlley.sh` attributes it to the
  wine-3.18-built native DLLs in `INSTALL/Mig Alley DLL/` and deliberately
  does not rsync them. Verified absent from `WP/drive_c/rowan/mig/`:
  `ddraw.dll`, `wined3d.dll`, `libwine.dll`, `mfc42.dll`, `d3dim.dll`.
  (They are still present in `INSTALL/`, unused, as intended.)
- **Monitor arrangement.** Dual 1920x1080 side by side (`HDMI-1` primary at
  +0+0, `DP-1` at +1920+0) is exactly the "dual monitors at the same
  resolution" configuration the script calls the best option.
- **Mode.** `.migalley_mode` = `basic`, so no wine virtual desktop is
  involved; this is the path the script records as confirmed working
  end-to-end on 2026-04-26 (on 24.04).

## Top lead (unverified): graphics settings never saved

```
[Software\\Rowan Software Ltd\\MIG\\Settings]     key exists, ZERO values
```

The game has never stored graphics settings — the session went straight to
fly. `migAlley.sh:412` explicitly instructs the user to enter **Preferences**
and set the resolution before playing, because the defaults do not suit modern
hardware.

**And the resolution those instructions name does not exist on this display.**
The script says to set **1440x1050**; `xrandr` offers 1920x1080, 1440x1080,
1400x1050, 1280x1024, 1280x960, 1152x864, 1024x768, 800x600. There is no
1440x1050. The 3D surface actually created was 1310x1060, which matches no
mode either. (BoB showed the same oddity — wine 8 logged xinerama failures for
`(-10,-10)-(1300,1050)`.)

### Next test

Launch, and **before flying** set Preferences → graphics:

1. Resolution **1400x1050** (a real mode here), or 1024x768 as a conservative
   first try.
2. Note whether Rendering is hardware or software; try the other if the first
   still black-screens.

If that fixes it, the change is to `migAlley.sh`'s install text — it is
currently telling users to pick a resolution this hardware cannot produce —
and possibly to seed sane defaults into the registry at install time so a
first-run "fly now" cannot land in this state.

## Tooling added

`scripts/dump_mig_stack.sh` — capture stacks from a hung wine game. Ubuntu
sets `kernel.yama.ptrace_scope=1`, so only root or an ancestor process may
attach a debugger; hence it must be run with sudo, **while the game is hung**:

```
sudo scripts/dump_mig_stack.sh [process-name]     # default Mig.exe
```

It samples `utime`/`stime` twice, two seconds apart, then dumps every thread's
stack. The CPU samples are the important part: climbing = spin, flat = block.
Those are different bugs with different fixes.

## Note for diagnosis

`launch_mig()` sends wine output to `&>/dev/null`, so a failed session leaves
nothing behind. To capture it, run `Mig.exe` directly with the same
environment (`WINEDLLOVERRIDES="winegstreamer=d;ddraw=b;wined3d=b"`, runner
`lutris-fshack-7.2-x86_64`) and redirect to a file. Worth considering a debug
log path in the script itself.

## Related

BoB is failing on the same machine for an unrelated reason — a wine focus
regression, see `TUE/BattleOfBritain/DOC/STATUS-2026-07-19-wine-focus-runner-matrix.md`.
Both games use the Rowan engine, but the two failures have nothing in common:
BoB's is a window-manager/focus problem in the 2D menus, this one is a CPU
spin after 3D entry.
