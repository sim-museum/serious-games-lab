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

Gold standards: **Zandvoort now lives LOCALLY** at
`/home/admin/gold standard/julia racer/zandervoort/` — the 43 stills + the two
260801 full-lap 1080p60 videos (cockpit + nintendo/chase; see SCREEN_PARITY § E60).
GPL utilities: `/home/admin/gold standard/julia racer/gpl utilities/`. The USB
sources remain historical co-canon: BEA6-BBCE (watkins glenn 4 / nurburgring 3)
and 84AF-CC77 (sole Monza/Spa source — re-attach to unblock E59.4).

## Current state (2026-08-01)

- E60 closed: Zandvoort parity vs the 260801 gold lap videos — sky/tyres/cowl/
  chase-cam/chase-driver fixed (verified by re-capture); D6 root-caused
  (chmp4-1.3do per-face winding) but still open; V7–V10 newly logged.
  Composites: `parity/zandvoort/video_*.jpg`.
- E59 round 1 closed (`23e11e1`/`d784d19`): 50-gold inventory, Zandvoort fixes
  (overcast regrade, matte dash, footwell, tyres), D10 open; D12 largely closed
  by E60 V2+V5 (re-verdict Watkins W3 next Watkins pass).
