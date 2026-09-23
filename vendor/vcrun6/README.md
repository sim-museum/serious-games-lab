# vcrun6 — vendored Visual C++ 6 SP4 redistributable

`VC6RedistSetup_deu.exe` (1,837,888 bytes)
sha256 `c2eb91d9c4448d50e46a32fecbcc3b418706d002beab9b5f4981de552098cee7`

## Why this is in git

The Rowan-engine games (Mig Alley, Flying Corps) need `mfc42.dll` for their
ActiveX OCX controls — without it the game crashes ~1s after launch (black
screen flash, then back to the shell).

The usual way to get it is `winetricks mfc42`, but winetricks needs wine to
unpack this installer, and that step is fragile on a **fresh** prefix: its
first act is to probe `%AppData%` via `wine cmd.exe`, which can come back
empty and abort the whole install with a `returned empty string` warning
(seen on a fresh Ubuntu 26.04 box, 2026-07-19).

This file is a plain self-extracting cabinet, so `cabextract` unpacks it
directly — no wine, no wineserver, no DISPLAY, no prefix state, nothing to
race:

    VC6RedistSetup_deu.exe → vcredist.exe → mfc42.dll + mfc42u.dll

Vendoring it means a fresh install also needs **no network**, and doesn't
depend on Microsoft's 2000-era download URL staying reachable.

It is exempted from the repo's blanket `*.exe` ignore by an explicit
negation at the bottom of `.gitignore`.

## Provenance

Byte-identical to what `winetricks` itself downloads — same URL and same
sha256 as its `winetricks_vcrun6_helper` recipe:

    https://download.microsoft.com/download/vc60pro/Update/2/W9XNT4/EN-US/VC6RedistSetup_deu.exe

(The `_deu` suffix is winetricks' choice, not ours; the payload DLLs are
language-neutral binaries.) Redistributable by license — that is what the
"Redist" package is for.

## Consumer

`TUE/MigAlley/migAlley.sh`, in the "Install prerequisites (mfc42)" block. It
stages this file into `~/.cache/winetricks/vcrun6/` so the vendored copy and
a winetricks-downloaded one remain interchangeable.

Two other scripts still call bare `winetricks mfc42` and do **not** use this
vendored copy — `scripts/fix_rowan_games.sh` and
`SAT/plotAircraftFlightPerformanceDiagrams.sh`.
