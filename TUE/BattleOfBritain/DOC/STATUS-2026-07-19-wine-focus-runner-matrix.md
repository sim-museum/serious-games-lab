# STATUS 2026-07-19 — BoB unplayable on Ubuntu 26.04: wine runner matrix

Fresh Ubuntu 26.04 install (GNOME on **Wayland**, NVIDIA 595, GTX 1660 SUPER).
Battle of Britain installs and starts, but is **not playable** on the pinned
runner. This documents the root cause, the full experiment matrix, and what was
ruled out — so none of it gets re-run.

## TL;DR

**The menu bug is a wine version regression, not the machine, not the
compositor, and not the install.**

| Runner | Landing-page clicks | 3D entry |
|---|---|---|
| lutris-5.7-11-x86_64 (**current pin**) | ✗ click → minimize | ✓ works |
| lutris-6.21-6-x86_64 | ✗ click → minimize | not reached |
| lutris-fshack-7.2-x86_64 | ✗ focus escapes, needs ALT+TAB | not reached |
| lutris-GE-Proton8-26-x86_64 | ✓ works | ✗ crash `00503fde` (`bob+0x103fde`) |
| lutris-8.0-x86_64 (vanilla, added today) | ✓ works | ✗ crash `10011c01` |

**wine ≤ 6.21 flies but can't click. wine 8 clicks but can't fly.**
No available runner does both. BoB is therefore unplayable on this box: the
pinned 5.7-11 reaches 3D but you cannot navigate the menus to get there.

## Symptoms as reported

1. Clicking any landing-page command (Quick Shots, Campaigns, …) "minimizes"
   BoB to an icon.
2. In 3D, the keyboard does nothing while mouse and joystick work normally.
3. Selecting **Quit** from the landing page also just minimizes — the game
   cannot be exited from its own UI.

All three are the same root cause: the game window does not hold X11 keyboard
focus. Mouse works because pointer events follow position; joystick works
because DirectInput polls the device. Only key events require focus.

## Evidence

### The window is never actually minimized

450 samples at 200 ms, capturing a real click (`xwininfo` map state,
`_NET_WM_STATE`, window count):

```
21:53:38.97  focus=48234497 (BoB)     map=IsViewable  state=FULLSCREEN,FOCUSED
21:53:40.11  focus=2097155 (phantom)  map=IsViewable  state=FULLSCREEN
```

- `map=IsViewable` **never changed** — the window is never iconified.
- window count **never changed** — no popup/child window appears on click.
- `_NET_WM_STATE_FULLSCREEN` **never dropped** — mutter is not un-fullscreening.

So the click gives BoB focus for **~1.1 s**, then focus is taken back. What
looks like "minimizing to an icon" is a still-mapped window being backgrounded.

### Where focus goes

Window `2097155`: 1x1, at `-100,-100`, **no WM_CLASS, no WM_NAME, no
_NET_WM_PID** — an unmanaged internal window, i.e. mutter's focus placeholder.
The `51x88` window also named `BoB` is `WM_CLASS=mutter-x11-frames`, mutter's
decoration frame, not the game. The real game window carries
`WM_CLASS=bob.exe`.

### Why this is wine, not mutter

The decisive test: under **GE-Proton8-26 and vanilla 8.0 the clicks work
normally** on the same compositor, same session, same prefix content. Wine
gained modern XWayland focus handling somewhere between 6.21 and 8.0.
Everything on the compositor side was attacking the wrong layer.

## Ruled out (do not re-run)

| Approach | Outcome |
|---|---|
| `focus_watchdog.sh` (poll focus, re-activate game window) | Made **78** corrections in one session; click-minimize unaffected. Restoring focus is not sufficient. Script deleted. |
| `UseTakeFocus=N` in `HKCU\Software\Wine\X11 Driver` | No change. Reverted; prefix left clean. |
| Wine virtual desktop (`wine explorer /desktop=`) | Crashes at `004ea1e9` in `DirectInputCreateA` — **exactly** the address already documented in `battleOfBritain.sh`. Confirmed still true. |
| gamescope | Broken package on 26.04: `undefined symbol: SDL_GetWindowSizeInPixels`, exit 127, never launches. |
| cage (kiosk Wayland compositor) | Gets far — NVIDIA EGL ok, own XWayland on `:2`, wine starts, DirectDraw initialises — then **cage itself** aborts: `xwayland/xwm.c:592: xwayland_surface_destroy: Assertion 'wl_list_empty(...)' failed`. wlroots/cage 0.2.1 bug, likely tripped by BoB destroying the spurious DirectDraw window. |
| X11 login session | **Not available.** 26.04 ships Wayland only; `/usr/share/xsessions/` does not exist. |

## Notes for whoever picks this up

- **Test against a copy of the prefix.** A newer wine irreversibly upgrades a
  prefix on first boot; downgrading back to 5.7 afterwards is not safe. All
  runner tests above used `cp -a WP /tmp/...` copies. `TUE/BattleOfBritain/WP`
  is untouched and still a wine-5.7 prefix.
- **Do not use `runDesktop.sh` for testing.** It writes four grab keys
  (`GrabFullscreen`, `GrabPointer`, `DXGrab`, `MouseWarpOverride`) permanently
  into the prefix, and `battleOfBritain.sh:88` records that those cause the
  deterministic `bob+0x103fde` null-deref on 3D entry under
  wine-5.7 + Wayland + NVIDIA. Launch `wine explorer /desktop=` directly instead.
- `lutris-8.0-x86_64` was added today from Kron4ek/Wine-Builds (the fallback
  source `scripts/setup_lutris.sh` already uses for versions past 7.2). It is
  **not** in `config/wine_runners.csv`.
- The wine 8 crash address differs between the two wine 8 builds
  (`00503fde` vs `10011c01`), which rules out Proton's patchset as the cause —
  the 3D breakage is wine 8 core. `10011c01` lies inside a DLL based at
  `0x10000000`, i.e. one of BoB's own Rowan DLLs, so wine 8 is feeding the
  Rowan renderer something it cannot handle.

## Untried leads

1. **Change BoB's renderer via in-game PC Config under wine 8.** Untested only
   because the menus were unreachable before wine 8. If the default D3D path is
   what wine 8 breaks, an alternate renderer may avoid the crash — this would
   need no code change and is the cheapest remaining lead.
2. **Bisect wine 7.x.** The regression window is 6.21 → 8.0. fshack-7.2 sits in
   it and behaves differently from both ends (no minimize, but focus still
   escapes). A vanilla 7.x build was never tried.
3. **Newer cage/wlroots**, past the `xwm.c:592` assertion.

## Unrelated fixes made the same day

- **`battleOfBritain.sh` sourcing bug (fixed).** Line 10 `cd`s to the script
  dir, but line 50 re-derived the path from `${BASH_SOURCE[0]}` *after* the cd,
  so launching by a relative path (as the launcher does) resolved
  `../../launcher/lib/clean_wineserver.sh` against the wrong directory. It only
  worked when run from the game folder. Now resolved to an absolute
  `SCRIPT_DIR`/`REPO_ROOT` before the cd; verified from all four invocation
  styles. No other script in the repo has this pattern.
- **wine-gecko checksum dialog (fixed on this machine, not yet in repo).**
  `source.winehq.org/winegecko.php` now ignores its version/arch parameters and
  serves `wine_gecko-0.0.1.cab` regardless, so wine 5.7's sha1 check fails:
  *"Unexpected checksum of downloaded file."* Server-side breakage affecting any
  fresh prefix, not this box. Fixed by installing the genuine
  `wine-gecko-2.47.1-x86.msi` from `dl.winehq.org` directly with
  `wine msiexec /i`, bypassing wine's downloader. Gecko is only needed for the
  in-game online documentation — it is **not** related to any issue above.
  A repo-side equivalent (checksum-gated download + `msiexec`, mirroring
  `scripts/install_mfc42.sh`) is still **to do**.
