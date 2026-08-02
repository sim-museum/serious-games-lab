# E59 — GPL-under-Wine screen parity, per track

Gold standard: screenshots of **GPL (MS Windows) running under Wine**. Two co-canonical
sources (PO 2026-07-25):
- `/run/media/admin/BEA6-BBCE/julia racer/` — `zandervoort/` (43), `watkins glenn/` (4),
  `nurburgring/` (3). Attached this sprint; inventoried below.
- `/run/media/*/84AF-CC77/{monza,spa,nurburgring,watkinsGlenn,zandervoort}` — the older
  per-track ref folders (the ONLY source of Monza + Spa golds). NOT attached this sprint
  (lsblk shows only BEA6-BBCE); fold in when re-attached. NB the BEA6-BBCE `zandervoort`
  02:5x cockpit series appears to be the same shots previously cited from 84AF-CC77 —
  cross-reference, don't double-count.

Native repro method (E58, extended this sprint): run the real app headless and photograph
any point of the lap. One session captures MANY views (E59 `JM_SHOTS`, added this sprint —
Julia startup is ~2 min/track, so never relaunch per shot):

```
cd THU/rFactor/juliaMotor/demo/native
env DISPLAY=:0 TRACK=<track> JM_SMOKE=1 JM_NOSOUND=1 JM_AI=<n> \
    RFACTOR_GAMEDATA=$REPO/rfactor-gamedata \
    JM_SHOTS_DIR=<outdir> JM_SHOTS="s:view:name;s:view:name;…" \
    julia -t 2 --project=. drive_native_mtk.jl
```
`s` = metres along the centreline (`JM_START_S` semantics), `view` = 0 cockpit / 1 chase,
`name` = output basename (`<name>.ppm` in `JM_SHOTS_DIR`). `JM_SHOT_SETTLE` (default 38)
frames settle between teleport and dump. Single-shot `JM_SMOKE`+`JM_DUMP` still works.

Verdict legend: ✅ parity · ◑ partial (logged deviation) · ✗ deviation open ·
W PO-waived (prior PO decision recorded in PRODUCT_BACKLOG.md).

## E59.1 — Gold-shot inventory

### Zandvoort (`zandervoort/`, 43 shots) — ALL cockpit views
Sky in EVERY shot: **flat overcast pale grey, diffuse light — NOT blue.** (Matches the PO's
E27 "one overcast grade" decision; E58's restored blue Zandvoort grade is a parity
deviation — see E59.2 D1.)

Common cockpit furniture (all 43): red wood-rim wheel + polished 3-spoke + yellow/green
LOTUS hub badge; matte-black dash, big central Smiths tach, temp/pressure gauges flanking,
small VOLTS dial lower-right, red "OFF" magneto toggle top-centre; riveted
aluminium/silver side panels with green body rim; brown gear knob right; two round chrome
bullet mirrors on stalks; driver's gloved hands on the wheel (GPL draws the driver; JM
hides the driver figure in cockpit — PO-settled E36, waived); nose + front tyres ahead.

Series A — `11-25-26`, `11-26-11`, `11-26-52` (2026-06-10, race with AI, MoTeC-style
timing overlay = GPLMotecAdd, not a JM parity target):
| shot | view | content | landmark | native repro (TRACK=zandvoort) |
|---|---|---|---|---|
| 11-25-26 | cockpit | stationary on grid, crowd both sides, 200-board, grid in mirror | S/F straight | `JM_SHOTS="0:0:…"` (+`JM_AI=5 JM_MODE=race` for the grid) |
| 11-26-11 | cockpit | right-hander, CALTEX/CASTROL/MARTINI boards, car in mirror | Tarzan approach | `s≈250` |
| 11-26-52 | cockpit | PAM tower + DUNLOP BANDEN sign, dressed crowd right | pit/paddock frontage | `s≈150–200` |

Series B — `02-52-25` → `02-56-21` (2026-06-28, 40 shots, one continuous cockpit lap +
pit straight second pass). Grouped by lap section; representative shots listed:
| group | gold shots | content / landmark | native repro s (see E59.2 capture map) |
|---|---|---|---|
| B1 pit straight → Tarzan braking | 02-52-25 (150-boards), 02-52-40 (50-boards + VREDESTEIN), 02-56-17/19/21 (200/150-boards, MARTINI+CALTEX ahead) | distance boards, CALTEX/MARTINI/CASTROL hoardings, crowds both sides | s≈150–300 |
| B2 Tarzan hairpin | 02-52-51 (right-hander, kerb, marshals, VREDESTEIN board) | Tarzan | s≈350–420 |
| B3 Tarzan exit / paddock frontage | 02-53-08/10 (steep crowd embankment L, PAM tower + DUNLOP BANDEN R), 02-53-15 (Gulf boards, fire truck, first-aid tent, minibus) | Gerlachbocht area | s≈500–700 |
| B4 dune twists | 02-53-20 (kerbed right, sandy runoff), 02-53-31 (green lattice tower), 02-53-57 (S-kink + Caltex flag), 02-54-00 (dip-and-rise) | Hunzerug/back section | s≈800–1600 |
| B5 fast dune sweeps | 02-52-58 (Texaco star flags), 02-53-03 (DUNLOP TIRES van, Armco descent), 02-53-54 (marram-grass dunes + spectator ridge), 02-54-18 (car ahead) | Scheivlak area | s≈1700–2400 |
| B6 remote back section | 02-54-32 (hangar on horizon), 02-54-37 (downhill L, orange-roofed shed), 02-54-44 (right kink), 02-54-54 (car ahead L), 02-54-58 (white farm building + Armco), 02-55-02 (tents + ambulance), 02-55-09 (blind crest), 02-55-16/18/21 (kerbed sweeps, crowds) | east loop | s≈2500–3300 |
| B7 town edge | 02-55-29 (green scaffold tower), 02-55-34/37 (white high-rise blocks + long hangar on skyline) | run toward Bos Uit | s≈3400–3800 |
| B8 Bos Uit → pit straight | 02-55-59 (Caltex flag, gantry ahead, MOLYKOTE in mirror), 02-56-02/05/07/09/11/12/13/15 (grandstand + CALTEX/DUNLOP hoardings L, PAM tower "DUNLOP BANDEN / CALTEX HAVOLINE MOTOROIL" R, fire truck, medical van, hay bales, S/F stripes, pit wall MOLYKOTE/VREDESTEIN/BARDAHL/CASTROL) | S/F complex | s≈3900–lap, 0–150 |

### Watkins Glen (`watkins glenn/`, 4 shots)
Sky: clear hazy pale blue, autumn (orange/green) forest horizon — matches the E58 Watkins grade.
| shot | view | content / landmark | native repro (TRACK=watglen) |
|---|---|---|---|
| 17-42-58 | chase (low, close behind) | Lotus from dead astern, plain tarmac | any straight, `view=1` |
| 17-43-07 | chase (side-ish) | Lotus broadside, patched asphalt + edge line, brown verge | any straight, `view=1` |
| 17-43-22 | cockpit | left-curve fencing w/ Great Western CHAMPAGNE billboard, KENDALL MOTOR OILS, BOAC VC10 banner, hay bales, crowd, grandstand straight ahead, autumn forest | around S/F / the 90 | `s≈0–200:0` |
| 18-42-37 | cockpit | BOAC "takes good care of you" banner, ONYX/LENTHERIC boards, crowd, right bend, autumn hills | past pit area | `s≈200–400:0` |

### Nürburgring (`nurburgring/`, 3 shots) — all cockpit, all with Wine title bar + GPLMotecAdd overlay
Sky: heavy stormy dark-grey overcast — matches the E58/E22 Nürburgring storm grade.
| shot | view | content / landmark | native repro (TRACK=nurburgring) |
|---|---|---|---|
| 16-06-00 | cockpit | pit wall R: Continental (yellow) / BOSCH (red) / BARDAHL; pit+timing building L with BOSCH; grandstand crowd; green Lotus ahead | S/F pit straight | `s≈0:0` (+AI for the car ahead) |
| 16-06-13 | cockpit | green-roofed BOSCH pit building L, Continental tyre-wall banners, S.E.V. MARCHAL + ESSO boards R, cars ahead + in mirror | S/F straight | `s≈100–250:0` |
| 16-06-35 | cockpit | Südschleife/Nordschleife signpost (Kelberg/Adenau/Köln arms), marshal w/ green flag, Armco, spectator terraces | Nord/Süd junction past the pits | `s≈300–600:0` |

## E59.2 — Zandvoort parity (native vs gold)

Native capture map (one `JM_SHOTS` session, lap = 4184 m by our centreline; landmarks
verified by eye against the gold set):
| native s | landmark | gold group |
|---|---|---|
| 0 | S/F line — grandstand L, PAM tower + CALTEX HAVOLINE R, MOLYKOTE pit wall | B8, 02-56-12, 11-25-26 |
| 150–300 | pit straight → Tarzan braking (VREDESTEIN/CALTEX/Castrol boards) | B1, 02-52-25/40 |
| 300–450 | Tarzan hairpin | B2, 02-52-51 |
| 600–800 | Gerlachbocht / paddock frontage | B3 |
| 1000–1750 | Hunzerug + dune twists | B4 |
| 2000–2500 | Scheivlak / fast dune sweeps | B5 |
| 2750–3250 | east loop (remote back section) | B6 |
| 3500–3750 | town-edge run toward Bos Uit | B7 |
| 4000 | Bos Uit → pits approach (gantry ahead) | B8, 02-55-59 |

Deviation log (baseline session `native_zand_base`, fix session `native_zand_fix1`):
| id | deviation (native vs gold) | verdict |
|---|---|---|
| D1 | Sky bright blue + clouds; ALL 43 golds are flat overcast grey | **fixed** — `GRADE_BYTRACK` zandvoort → `GRADE_OVERCAST` (restores PO E27; `JM_GRADE=ZAND` A/Bs the blue) |
| D2 | Road + dune backdrop wash toward white (gold: mid-grey asphalt, green dunes) | ◑ largely a D1 side-effect (blue-grade ambsky/sat); re-judged after regrade — see fix-session verdicts |
| D3 | Dash reads washed-out silver plank; gold is matte-black dash w/ crisp white-on-black dials | **fixed** — gauge draw bright 1.6→1.0, ambfill 0.95→0.60 (`JM_DASH_B/A` tune) |
| D4 | Footwell renders a black/white/tan "checkerboard" of untextured tub facets (gold: dark interior; GPL fills this area with the driver we hide per PO E36) | **fixed** — untextured cockpit tris' baked colours capped to dark (render.jl, cockpit_clean path) |
| D5 | Front tyres render as solid black silhouettes (gold: readable dark-grey tread/sidewall) | **fixed** — wheel draw gets bright=1.0 ambfill=0.55 (was default lighting) |
| D6 | Signage text mirrored on some boards (VREDESTEIN at Tarzan, DUNLOP on the main stand) | **open** — known per-instance issue: the coplanar-panel dedup can keep the away-facing decal of a double-sided sign; a fix needs track-aware face selection at extract time. Diagnosed, deferred |
| D7 | Horizon dune ring reads as a bare pale-white band under the blue grade (gold: green dune line) | ◑ regraded by D1 (grey sky blends the band); residual tint logged |
| D8 | Gold shows dense standing-crowd lines along the fences; native has none | **W waived** — PO decision "spectator crowds removed" (STATUS working/done); revisit only on PO request |
| D9 | Plexiglass yellow arcs more prominent than gold's faint tint | **W waived** — PO E21 explicitly asked for the visible yellow-arc plexiglass; `JM_WIND_ALPHA` tunes |
| D10 | Grandstand crowd texture renders as coarse blue/yellow pixel noise; DUNLOP fascia partially mirrored | ◑ open — E46 residual (crowd MIP UV smear needs a re-map); tint already applied cross-track |
| D11 | Cyan slab beside the pit building at s≈4000 (no such element in gold) | **closed — authentic GPL asset**: decoded the source texture (restzxc `hill.mip`, avg RGB 61,119,129) — it is GPL's own teal pond, as authored; no fix |
| D12 | Chase view: rear bodywork renders skeletal/noisy vs the Watkins gold chase shots' clean green body | open — logged for E59.3 (Watkins has the chase golds) |
| D13 | No driver hands on wheel (all golds show gloved hands) | **W waived** — PO E36 driver-figure pull; `JM_HANDS=1` exists but the static arm mesh doesn't fit the re-placed wheel/eye |
| D14 | JM lap-time HUD digits top-left (golds have none, or the GPLMotecAdd overlay) | **W waived** — E13 decluttered set kept lap times by design |

Fix-session result (all fixes verified by offscreen re-capture, sessions
`native_zand_fix1/2`): sky matches the gold's flat overcast; dash reads matte black with
legible dials; footwell fades dark with a dark-green tub rim; tyres read as shaded
dark-grey cylinders (gold's tread/lettering detail is texture the untextured `lotwlf.3do`
mesh cannot carry). Committed side-by-sides: `parity/zandvoort/*.jpg` (gold left, native
right).

## E59.3 — Watkins Glen + Nürburgring parity

Watkins (session `native_watglen`, s = 0/150/300/600 + chase; composites in
`parity/watglen/`):
| id | deviation | verdict |
|---|---|---|
| W1 | Sky hazy blue ✅, KENDALL/DUNLOP gantry ✅ (E58 fix holds), hay + fencing ✅ | parity |
| W2 | Verge grass + horizon hills render khaki-brown; gold shows green grass + autumn forest | **open** — terrain/ring tint; candidate next-sprint grade tweak (ringtint/sat alone insufficient — the terrain mesh texture itself reads brown) |
| W3 | Chase view: rear bodywork renders skeletal/noisy grey vs gold's clean dark-green body + engine detail (= Zandvoort D12) | **open** — body extraction/LOD gap in chase view |
| W4 | Chase camera sits higher/further than the gold close-astern framing | open (minor) — `replay_camera` angles exist; live chase cam is the "Nintendo" above-rear by PO preference (E25) |
| W5 | Tyres now shaded grey (D5 fix) but no tread/Firestone texture (untextured mesh) | ◑ asset-limited |

Nürburgring (session `native_nurb`, s = 0/150/400; composite in `parity/nurburgring/`):
| id | deviation | verdict |
|---|---|---|
| N1 | Stormy grey sky, Continental/BOSCH banners, pit wall + buildings, scoreboard tower, flag row, crowds | parity — the E22/E58 storm grade + E29/E44 object lighting hold up against the gold |
| N2 | Small dark quad floats mid-air near the S/F scoreboard | **open** (minor) — object with no ground sample; candidate for the JM_DROPTEST/`ploz` treatment next pass |
| N3 | Driver hands / textured tyres | W waived / asset-limited (as Zandvoort D13/D5) |

## E59.4 — Monza/Spa gold gap (PO)
Monza and Spa golds live on the **84AF-CC77** drive (co-canonical per the PO, but not
attached this sprint — `lsblk` shows only BEA6-BBCE). **Ask:** re-attach 84AF-CC77 so
E59 can run the same parity method on its `monza/` + `spa/` folders; no new GPL captures
needed unless the PO prefers refreshing them onto BEA6-BBCE.

## E60 — Zandvoort parity round 2 vs the 260801 gold LAP VIDEOS (2026-08-01)

**New gold source (LOCAL — supersedes the USB copies for Zandvoort):**
`/home/admin/gold standard/julia racer/zandervoort/` — the 43 screenshots PLUS two new
full-lap videos of GPL-under-Wine (1080p60): `260801_zandervoort_cockpit.mp4` (3:01,
standing lap t≈6→146 s + partial lap 2) and `260801_zandervoort_nintendo.mp4` (2:24,
same lap in GPL's chase view — the FIRST Zandvoort chase gold; nintendo ≈ cockpit
timeline −3 s).  GPL utilities (WinMIP/123do/LytViewer/GPL_Tel) at
`/home/admin/gold standard/julia racer/gpl utilities/`.

Method: 1 fps frame extraction (gstreamer/avdec_h264 — no ffmpeg on this box),
landmark-mapped to the E59.2 s-map; one 46-shot `JM_SHOTS` session (37 cockpit +
9 chase) per iteration; 5 fix iterations captured.

### Verdicts (video gold vs native, fix session E60)
| id | deviation | verdict |
|---|---|---|
| V1 | Sky: cloud=1.0 procedural deck read as heavy cumulus; ALL video frames show near-featureless pale grey | **fixed** — `GRADE_ZANDOVER` (overcast, cloud=0.18; `JM_CLOUD` A/Bs) |
| V2 | Tyres read light-grey ALLOY (0.26 albedo); gold = near-black rubber in both views | **fixed** — `JM_TYRE_ALB` default 0.17 |
| V3 | Cockpit cowl = black/green/grey per-tri CHECKERBOARD (E59 D4 cap left baked colours); gold = one smooth dark-BRG cowl + dark pad | **fixed** — untextured cockpit tris harmonized to 2 colours (`JM_COWL_HARM=0` reverts) |
| V4 | Chase cam 9 m back/3.2 m up = TV crane shot; nintendo gold sits LOW+CLOSE | **fixed** — 4.6 m/1.35 m (`JM_CHASE_D/H/LY`) |
| V5 | Chase driver read absent → car skeletal (E59 D12): torso-only DRIVERP, no helmet | **fixed** — +lid/arms in DRIVER_TEX; helmeg.3do extracted, retextured helblack→clahelm (Clark blue), placed at neck top (`JM_HELM_X/Y`) |
| V6 | D6 mirrored/blank signage (VREDESTEIN, DUNLOP pit boards, MARTINI, blue CALTEX) | **open — root cause found**: Tarzan wall = `chmp4-1.3do`, one combo mesh (bilbrd01 ad sheet) with per-face winding inconsistent INSIDE the object; A/B matrix in code comment (JM_OBJ_DEDUP/JM_OBJ_CULL/JM_OBJ_FF); needs per-face track-aware selection at scenery build |
| V7 | Floating crowd billboards above the dune ridge at s≈1100 | open (E4 placement class) |
| V8 | White tower-like object near Gerlach s≈700 (gold: first-aid tent area) — suspected mis-oriented placement | open (E4 placement class) |
| V9 | LOTUS hub badge text upside-down (cockpit) | open (minor) |
| V10 | Roadside standing-crowd billboards render blue (CROWD_TINT covers stand objects only) | open (D10 class) |
| — | D8 crowds / D9 plexiglass / D13 hands / D14 HUD | waived (unchanged PO decisions) |

Chase framing, driver figure, sky, tyres, cowl verified by re-capture (sessions
`native_fix1..5`, final `native_final`); composites in `parity/zandvoort/` (`video_*`).
