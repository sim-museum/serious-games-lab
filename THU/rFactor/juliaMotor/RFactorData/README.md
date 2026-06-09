# RFactorData.jl

Parsers for rFactor 1 / isiMotor 2 plain-text physics data files — Phase 0
of the juliaMotor project (`../../DOC/juliaMotorProjectScope.md`). The
rFactor data files stay the single source of truth: this package turns
them into typed Julia structures from which the ModelingToolkit vehicle
is assembled.

## Status

| Format | Status |
|--------|--------|
| `.hdv` chassis | **done** — full 202-file corpus parses, 4 known data defects repaired/reported |
| `.tbc` tires | **done** — 193 files, 901 slip curves, 255 compounds; `Data:` blocks, `FRONT:`/`REAR:`/per-corner scopes |
| `.pm` suspension | **done** — 121 files, 1299 bodies / 485 joints / 2225 bars, all body references resolve |
| engine / gears `.ini` | **done** — torque curves (`EngineFile`), `gear_ratios` |
| `.veh` / `.svm` | **done** — all 1172 VEH resolve end-to-end via `load_vehicle`; 128 setups parse clean |
| `.gen` graphics | **done** — brace blocks, upgrade directives; MeshFile count matches grep ground truth (17414) |
| `.aiw` / `.gdb` track | **done** — 68 tracks: waypoints (positions/widths/AI speeds/sectors), grids; GDB via the GEN brace parser |
| `.mas` archives | **done** — format recovered (16-byte signature, 256-byte TOC records, zlib/stored members); all 274 archives extract |
| `.gmt` meshes | **geometry done** — format reverse-engineered (`../../DOC/gmtFormat.md`): bbox, name, stride-32 vertices (position+normal+color), sequential u16 triangle soup. All 260 GMTs of a track decode with in-range indices (11,940 tris); `nverts` derived from the index run, not the bbox. UV/material extraction (for rendering) remain |

Telemetry CSV ingestion lives in the sibling package `../RFactorTelemetry`.

## Usage

```julia
using RFactorData

# one car, fully wired: VEH -> HDV -> TBC / PM / engine / gears
v = load_vehicle(joinpath(default_gamedata(), "Vehicles", "F158", "BRM",
                          "Teams", "Schell", "Schell.veh"))
v.hdv["GENERAL"]["Mass"]             # 765
v.engine.rpm, v.engine.torque        # full-throttle torque curve
slipcurve(v.tbc, "Lateral").data     # tire slip-curve samples
body(v.pm, "fl_wheel").pos           # suspension multibody geometry
gear_ratios(v.gears)                 # garage ratio options

# or each format directly
hdv = read_hdv(joinpath(default_gamedata(),
                        "Vehicles", "F158", "BRM", "BRM P25.hdv"))
hdv["GENERAL"]["Inertia"]            # [894.5862389, 902.6038691, 132.154451]
hdv["BODYAERO"]["BodyDragBase"]      # 0.349  ((x) collapses to scalar)
sections(hdv, "AIDPENALTIES")        # repeated sections come back as a list
entry(hdv["GENERAL"], "CGHeight").comment  # trailing // comment text
hdv.issues                           # repaired/skipped malformed input

tbc = read_tbc(joinpath(default_gamedata(), "Vehicles", "F158",
                        "DunlopR4-16inches.tbc"))
compound(tbc, 0)["Temperatures", :frontleft]  # corner -> axle -> common fallback
```

Section and key lookup is case-insensitive (isiMotor semantics); repeated
keys are last-wins via `getindex`, with `entries(sec, key)` for all of them.

The parser is lenient by design — the corpus contains real typos that
isiMotor tolerates (`CGRearSetting=0WedgeRange=(0,0,0)` jammed pairs,
`FuelTankMotion=FuelTankMotion=(...)` duplicated keys, a missing `=`,
empty tuple slots `(0,,0)`, a decimal-comma `295,33`). Everything is
loaded; anything repaired or skipped lands in `ISIFile.issues`.

## Tests

```sh
julia --project=. -e 'using Pkg; Pkg.test()'
```

Unit tests cover each format's grammar and every corpus oddity; the
corpus suites then parse the entire install — 202 HDV, 193 TBC, 121 PM,
357 GEN, 128 SVM, and all 1172 VEH resolved end-to-end through
`load_vehicle` — pinning exact counts so nothing regresses silently
(9712 assertions). Point `RFACTOR_GAMEDATA` elsewhere to test against a
different install.
