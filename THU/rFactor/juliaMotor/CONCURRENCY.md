# Parallel-session rules — Julia Racer graphics

Other Claude sessions are running scrum on MiG Alley, Battle of Britain and FreeFalcon at the
same time. This box has **one display and 4 cores**; see `~/CONCURRENCY.md` for the full
picture.

## Work the 5 tracks SEQUENTIALLY in this one session

Do not split them across sessions. All five need the display for `JM_SHOTS`, they share
`~/.julia`, and **131 of the track-specific lines live in one 2 557-line file**,
`demo/native/drive_native_mtk.jl`. Parallel sessions would conflict on it continuously.

Worktrees do not help: you would still serialise on the display, spend ~3.3 GB of depot each,
and then merge five branches that all touched the same lines.

## Take the display explicitly

```bash
export PATH="$HOME/bin:$PATH"
gl-lock TRACK=monza julia -t 2 --project=demo/native demo/native/drive_native_mtk.jl
gl-lock --status
```

`gl-lock` also refuses to start when the desktop is locked, which otherwise looks exactly like
the port hanging at the title screen.

### What the lock is actually for (corrected 2026-08-02)

An earlier version of this note claimed that two sims rendering at once corrupts screenshots.
**That was wrong.** Every capture path here — Julia's `JM_SHOTS` and the MA/BoB parity dumps —
uses `glReadPixels` against its OWN GL framebuffer (Julia's window is even created with
`GLFW.VISIBLE, false`). Two processes drawing at once each read their own buffer; neither can
see the other's pixels. Pixel content is safe.

The real reason to serialise is **contention for one GTX 1660 SUPER and 4 cores**. That
matters because results here can be frame-rate dependent — MiG Alley's stress gate scores a
run `HANG` when it misses its frame target, so a second sim hammering the GPU can manufacture
a failure that looks like a port defect. Julia captures also slow down under load.

So: still wrap GL runs in `gl-lock`, but if you see a contention alert, the question to ask is
"were any timing-sensitive results taken in that window?" — not "must I discard my captures?".

#### If your launch prompt says otherwise, the prompt is stale (added 22:15, 2026-08-02)

All three sessions running right now were started with this line in their prompt: *"A capture
taken while another sim owns the screen gives plausible but WRONG pixels and will poison your
parity verdicts."* That is the debunked claim — the prompts were written before the correction
above. **Do not re-take or discard any `JM_SHOTS` capture on concurrency grounds**, and do not
serialise your gold-frame work behind the display for that reason. Your window is created
`GLFW.VISIBLE, false` and never appears on screen at all; nobody can contaminate its pixels.

**Practical consequence:** the trigger for taking `gl-lock` is *load*, not *pixels*. Keep your
`JM_SHOTS` runs under the lock — they are GPU-heavy and frame-rate sensitive, which is exactly
what the lock protects. Your **GStreamer 1 fps extraction** is the other side of it: it is
CPU-heavy and runs for minutes, so it is not worth holding the display for its whole duration,
but be aware it loads the box — if a neighbour reports a timing failure in that window, say so
rather than letting them chase a phantom port defect. `~/bin/gl-lock`'s own header comment still
states the old rationale; `~/CONCURRENCY.md` and this file are the authority.


You hold the display for ~3 minutes per `JM_SHOTS` run. That is fine; the other sessions are
told to expect it.

## The gold videos

All ten lap videos are local under `~/gold standard/julia racer/<track>/` — cockpit and
nintendo for all five circuits. Index and frame-extraction recipe in that directory's
`README.md`. No `ffmpeg` on this box; use the GStreamer pipeline given there.

`~/gold standard/` is the shared oracle for all four projects — **read-only** during port work.

## Long CPU builds do NOT hold the display lock (learned 2026-08-09)
A ~40-min `jlracer.so` sysimage build queued under `gl-lock` was killed mid-hold — a
multi-10-minute exclusive hold starves the other three projects' gates even though the
letter of the doctrine ("CPU-heavy headless takes the lock") allows it.  Follow the
GStreamer-extraction precedent instead: run long compiles UNLOCKED at `nice -n 19`, and
note here while one runs so a neighbour chasing a timing anomaly can attribute it.
**ACTIVE:** jlracer.so sysimage build may be running nice-19 in the background (julia
PackageCompiler, up to ~50 min). If your timing-sensitive gate wobbles in that window,
rerun it after `pgrep -f build_sysimage` comes up empty.
