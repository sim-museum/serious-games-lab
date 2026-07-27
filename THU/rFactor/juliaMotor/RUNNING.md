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

Gold standards (BOTH canonical): `/run/media/admin/BEA6-BBCE/julia racer/`
(zandervoort 43 / watkins glenn 4 / nurburgring 3) AND the older `84AF-CC77` USB
(sole source of Monza/Spa golds — **currently unplugged; re-attach to unblock
E59.4**). The BEA6-BBCE zandervoort 02:5x cockpit series duplicates shots
previously cited from 84AF-CC77.

## Current state (2026-07-26)

- E59 round 1 closed (`23e11e1`/`d784d19`): 50-gold inventory, Zandvoort fixes
  (overcast regrade, matte dash, footwell, tyres), D6/D10/D12 open.
- Round 2 (Watkins/Nürburgring parity) was lost to a session limit before any
  tree changes; sprints paused pending PO re-expansion of scope.
