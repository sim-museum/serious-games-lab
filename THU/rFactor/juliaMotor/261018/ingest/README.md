# IRPLAN-3 session, 2026-10-18 — what the PO's files are

Source: USB stick `261018/`, copied byte-for-byte (md5-checked, 79 files) to `~/gold standard/julia racer/261018/`
(`telemetry/` 38 .ibt, `sheets/` 31 setup sheets, `setups/lotus49/` 2 .sto, `races/` 3 AI-race result JSONs,
`screenshots/` 3 PNGs, plus the plan's .md/.pdf). No note file from the PO.

`catalog.csv` = `tools/irsession_catalog_261018.jl` over the telemetry folder (setup name, knobs, driving signature).

| Plan part | Files (time of day, 2026-10-18) | Notes |
|---|---|---|
| A setup sheets | `sheets/*.htm` (29 knob endpoints + `261010_rung_official`, `261005_jr_ww103`, `monza_default`) | parsed by `sheet_frames.py` -> `frames_sheets.csv` (garage fit frames), `knobs_sheets.csv` (every value) |
| B garage ranges | **not done** as screenshots; the sheets give the endpoints of perch, camber (LF), toe F/R, bias, packer, dampers, fuel | the "tire_pressure_max" sheet reads 179 kPa, yet 207 kPa is seen in `261004_skidpad` -- not the max |
| C couplings | **not done** as screenshots; the camber/toe/pressure sheets give C1-C3 at the endpoints | C4/C5 (bar rate per hole under a big twist) still missing |
| D1 skidpad power slides | skidpad 13-00-28 (default, both ways), 13-09-27 (WW103, both ways) | `tools/powerslide_261018.jl` |
| D2 pulls / D3 coasts | Monza 13-15-11, 13-20-53 (default); 13-18-02, 13-19-45, 13-23-59 (WW103) | 13-20-53 and 13-23-59 have ~60 s of coasting each |
| E1 steady speeds | Monza 13-29-28 (default 30 N/mm), 13-33-09 + 13-35-08 (front 35 N/mm); WW103 13-37-08, 13-38-57 (18 N/mm), 13-44-44, 13-46-32 (WW103 with **23** N/mm front) | the WW103 runs are extra |
| E2 corner exits | Monza 13-49-30 (drive ramp 35°), 13-57-05 (75°), default setup otherwise | |
| E3 roll per bar | skidpad 14-07-37 (base), 14-11-39 (front arms soft), 14-13-23 (front firm), 14-15-00 (rear soft), 14-16-45 (rear firm) | arms, not the diameters the plan asked for |
| E4 trail braking | Monza 14-20-33, 14-24-50, 14-27-59 (default); 14-37-00, 14-41-14 (WW103) | 14-20-09 is a 9 s stub |
| F AI races | Monza 14-50-59 (21 cars), 14-59-12, 15-11-16, 15-29-17 (stub), 15-31-56, 15-37-17 (7 cars, WW103); 15-47-16 .. 16-18-14 (12 cars, iRacing's `monza.sto`) | `races/*.json` = iRacing's result files (6 and 11 finishers) |
