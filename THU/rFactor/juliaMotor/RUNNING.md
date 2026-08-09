# Julia Racer — Run & Check Progress

## Run the game

```bash
python3 /home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native/juliaRacer.py
```

PyQt GUI: pick track (Zandvoort / Nürburgring / Watkins Glen / Monza / Spa),
mode (Training / Practice / Race), AI count + speed %, laps — then race. Julia
startup is slow per track (~2 min; faster with the `jlracer.so` sysimage).
Requires a healthy GL display session.

## Check progress

| What | Where (all under `THU/rFactor/juliaMotor/`) |
|---|---|
| Product backlog + epics (E1–E59) + status log | `PRODUCT_BACKLOG.md` (E59 = GPL-under-Wine screen parity; status log at the end of each section) |
| Per-gold-shot parity verdicts | `SCREEN_PARITY.md` (all 50 golds inventoried; Zandvoort deviations verdicted) |
| Side-by-side composites | `parity/` (force-added jpgs) |
| Session status docs | `STATUS.md`, `STATUS_2026-07-06_graphics-E58.md` |
| History | `git log --oneline` on `julia-racer` |

Gold standards: **all lap videos now live LOCALLY** under
`/home/admin/gold standard/julia racer/` — index in that directory's `README.md`.
As of 2026-08-02 the USB sticks are no longer needed: the 260802 cockpit+nintendo
lap videos for **watkinsGlenn, nurburgring and monza** were copied off 84AF-CC77
(byte-verified), joining the 260801 Zandvoort pair. **E59.4 is unblocked for Monza**
without re-attaching anything.

**All five circuits have cockpit + nintendo lap gold locally — E59.4 fully closed.** A
`260802/` folder on the second stick (**BEA6-BBCE**) supplied the last pieces: both Spa laps
(6:28 / 5:57) and the **complete** 15:04 Nürburgring nintendo lap.

Housekeeping in `nurburgring/`: the truncated copy from the other stick and the 6-min
reconstruction built from it are both superseded by the complete recording and can be
deleted (`*.BROKEN-no-moov.mp4`, `*.PARTIAL-recovered-6min.mp4`, ~1.4 GB). Keep
`rebuild_moov.py` — GPL captures here are video-only H.264 with 4-byte-length-prefixed
NALs, so it will rebuild any future interrupted recording given a healthy reference.

`watkins glenn` and `watkinsGlenn` were two directories for the same circuit; merged
2026-08-02 into **`watkinsGlenn`** (88 items). Any reference to `watkins glenn` is stale.
GPL utilities: `/home/admin/gold standard/julia racer/gpl utilities/`.

## Current state (2026-08-08)

- **E64 S1–S3 closed.** S1 LIVE MIRRORS: the cockpit discs show a real rear-view render
  (384×192 RTT, X-mirrored, per-disc half view, round-masked glass quads derived from the
  mirror mesh itself; `JM_MIRROR_RTT=0` restores silver discs, `JM_MIRROR_FOV` tunes);
  world draw factored into one `drawworld` closure shared by main + mirror passes.
  S2 HANDS: gold-layout gloved fists at 10-and-2 riding the wheel (`JM_HAND_GRIP`) +
  sleeves via the `ARMFIX` wrist-pivot correction of the positioner-orphaned `lotarms`
  (`JM_ARM_*` knobs; `JM_HANDS` defaults ON). S3: both verified to GENERALIZE on all
  5 circuits (`parity/cockpit_e64_mirror_sweep.jpg`). Z-CK3 + Z-CK4 → FIXED in
  `SCREEN_PARITY.md`; session doc `STATUS_2026-08-08_graphics-E64-S1.md`. E64 remaining:
  chase-body LOD (D12, asset-deep), mirror/hands polish vs gold video at speed.

## Earlier (2026-08-02)

- E61 closed (`SCREEN_PARITY.md` § E61): ALL FIVE circuits graded against their gold LAP
  VIDEOS in one session. Per-track grade fixes in `drive_native_mtk.jl` (LIVE at next
  launch, no sysimage rebuild): Watkins sky→hazy pale + verge de-yellowed; **Nürburgring
  re-greened** (the video is a bright partly-cloudy GREEN day, not the storm the 3 stills
  implied); Monza + Spa skies paled from over-blue to gold's hazy blue; Zandvoort (E60)
  re-verified, no regression. `JM_GRADE=<TRACK>OLD` A/Bs each prior grade. Composites
  `parity/<track>/video_*`. Open (deeper, logged): skeletal chase body (D12), crowd smear
  (E46), Watkins roadside forest (WG3), Monza banking slabs (E52).
- E60 closed: Zandvoort parity vs the 260801 gold lap videos — sky/tyres/cowl/
  chase-cam/chase-driver fixed (verified by re-capture); D6 root-caused
  (chmp4-1.3do per-face winding) but still open; V7–V10 newly logged.
  Composites: `parity/zandvoort/video_*.jpg`.
- E59 round 1 closed (`23e11e1`/`d784d19`): 50-gold inventory, Zandvoort fixes
  (overcast regrade, matte dash, footwell, tyres), D10 open; D12 largely closed
  by E60 V2+V5 (re-verdict Watkins W3 next Watkins pass).
