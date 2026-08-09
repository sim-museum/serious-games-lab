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
> **Location changed 2026-08-02.** These 4 shots were merged into
> `/home/admin/gold standard/julia racer/watkinsGlenn/` (88 items) along with the 82 in-sim
> screenshots and the two 260802 lap videos. The `watkins glenn/` directory no longer exists
> locally; the filenames below are unchanged.

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

### RESOLVED for Monza, still blocked for Spa (2026-08-02)
84AF-CC77 was re-attached and its lap videos copied **locally** (byte-verified, stick since
removed). `/home/admin/gold standard/julia racer/` now holds 260802 cockpit+nintendo pairs
for **watkinsGlenn, nurburgring and monza**, alongside the 260801 Zandvoort pair — full
index in that directory's `README.md`. No USB is needed to run parity any more.

* **Monza — unblocked.** 79 stills + `260802_monza_cockpit.mp4` (2:53) and
  `260802_monza_nintendo.mp4` (2:53).
* **Spa — unblocked.** 48 stills + `260802_spa_cockpit.mp4` (6:28) and
  `260802_spa_nintendo.mp4` (5:57), found in `260802/` on stick **BEA6-BBCE**.
* **Nürburgring — complete, both views.** `260802_nurburgring_cockpit.mp4` (15:09) and
  `260802_nurburgring_nintendo.mp4` (15:04, full Nordschleife).

**E59.4 is fully closed. All five circuits now have cockpit + nintendo lap gold locally,
and no USB is required for parity work.**

Two corrections to what this document said earlier today, both from concluding too early:
* "Spa needs a fresh GPL capture" — wrong. Both Spa laps existed on the other stick.
* "Nürburgring chase view: recoverable only as a ~6 min partial" — wrong. The truncated
  737 MB copy on 84AF-CC77 was not the only copy; BEA6-BBCE held the complete 1.9 GB
  recording. The 6-min reconstruction built from the truncated file is superseded and its
  leftovers in `nurburgring/` (`*.BROKEN-no-moov.mp4`, `*.PARTIAL-recovered-6min.mp4`) can
  be deleted. `rebuild_moov.py` is retained — it will rebuild any future interrupted capture.

The general lesson: **check every device before declaring an asset missing or unrecoverable.**
Two sticks held overlapping, non-identical copies of the same session.

Also 2026-08-02: `watkins glenn` (4 desktop screenshots) was merged into `watkinsGlenn`
(now 88 items) — one directory per circuit. References to `watkins glenn` are stale.

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

## E61 — gold-VIDEO parity across ALL FIVE circuits (2026-08-02)

**PO directive:** update the graphics on all five juliaMotor tracks against the local gold
lap videos (cockpit + nintendo for every circuit, `~/gold standard/julia racer/<track>/`).
Extends the E60 Zandvoort method to Watkins Glen, Nürburgring, Monza and Spa — the first
time those four have been judged against their gold *videos* (E59/E22 used stills only).

**Method (per track, one display-locked `gl-lock` session each):**
1. Extract gold frames at 1 fps with GStreamer `decodebin` (the README's `h264parse` is
   NOT installed on this box — `filesrc ! decodebin ! videoconvert ! videorate !
   video/x-raw,framerate=1/1 ! jpegenc ! multifilesink`).
2. The golds are **full-desktop Wine captures** — the GPL viewport is a sub-rectangle with
   the GPLMotecAdd timing bar on top, a telemetry bar below, and the magenta Ubuntu
   wallpaper beside it. Crop to the 3-D viewport `(0,135,1280,950)` before comparing
   (window is at screen-left x∈[0,1280] for every recording; verified per track).
3. Native capture: `JM_SHOTS="s:view:name;…"` through `gl-lock` (`render.sh`), landmark-
   mapped by eye. Each launch now prints `CLINE: centreline length = N m` (added this
   sprint) so shots can be spread across the real lap without a separate probe.
4. Side-by-side composites (PIL — no ImageMagick on this box) → verdict → grade/render fix
   → re-capture → commit. Composites under `parity/<track>/`.

Native centrelines measured this sprint: Zandvoort 4181 m, Watkins Glen 3753 m
(Nürburgring/Monza/Spa filled in below as each is captured).

### E61 Watkins Glen — video gold vs native
Gold sky: **hazy pale grey-blue** (sampled zenith≈(0.70,0.75,0.81), horizon≈(0.79,0.81,0.83)),
colourful **autumn forest** lining the track, brown-green late-autumn verges.
| id | deviation (native vs gold) | verdict |
|---|---|---|
| WG1 | Sky rendered a SATURATED blue + puffy cumulus (E22/E58 grade); gold is hazy pale grey-blue | **fixed** — `GRADE_WATK` retuned: zenith (0.28,0.48,0.80)→(0.60,0.66,0.74), cloud 0.40→0.28, horizon paled/neutralised (`JM_GRADE=WATKOLD` A/Bs the old blue) |
| WG2 | Verge grass rendered a garish saturated YELLOW; gold verge is muted green-brown | **fixed** — same grade: sat 1.26→1.12; verge now olive-green-brown |
| WG3 | Roadside AUTUMN FOREST missing — the horizon is a low blurry brown smear-band; gold has tall colourful trees lining the track | **open** — the Watkins backdrop is a single panoramic strip (`horiz0`) drawn as a thin band; the tall close trees are GPL scenery objects the port doesn't stand up. Raising the strip band (`JM_STRIP_HI`) only enlarges the smear, doesn't recreate the forest. Deeper scenery-object work; = the long-standing W2. Warm `ringtint` kept so what IS there stays autumn-coloured |
| WG4 | Chase view: rear bodywork skeletal (exposed engine/arms, wheels read detached) | **open** — same body-LOD gap as Zandvoort D12 / W3. NB the gold nintendo view legitimately shows a lot of exposed engine/suspension, so the gap is narrower than it first reads |
| WG5 | S/F crowd renders as blue/yellow pixel smear at the fence base | ◑ E46 crowd-MIP class (cross-track) |
| — | driver hands / textured tyres / lap HUD | waived (as Zandvoort) |

Sky + verge verified by A/B re-capture (old-blue vs new-hazy) and a shipping-config confirm
session; composites `parity/watglen/video_*`.

### E61 Nürburgring — video gold vs native (native lap 22 780 m)
**Weather correction — the biggest finding of this sprint.** The 3 E59 GPLMotecAdd stills
(all at the S/F) implied "heavy stormy dark-grey overcast", and `GRADE_NURB` rendered the
WHOLE 22.7 km Nordschleife dark, brown and desaturated (cloud=1.0 deck, sat 0.88). The
260802 gold VIDEO (full 15-min lap) shows the opposite for 99 % of the lap: a bright
**PARTLY-CLOUDY** day — dramatic grey cloud over the S/F pit complex, opening to **blue sky
+ white cumulus over LUSH GREEN forest** across the whole Nordschleife. Sampled gold zenith
≈(0.53,0.59,0.67) (blue-dominant), forest vivid green.
| id | deviation (native vs gold) | verdict |
|---|---|---|
| NB1 | Whole lap rendered dark/stormy + brown; gold Nordschleife is bright blue-sky + green forest | **fixed** — `GRADE_NURB` re-graded bright: sat 0.88→1.10 (re-greens the forest/verges), cloud 1.0→0.70 + bluer zenith (blue shows through the cumulus), warm sun, ring un-darkened (0.90→1.02). `JM_GRADE=NURBOLD` A/Bs the old storm |
| NB2 | S/F pit complex: gold there is genuinely dramatic/dark-cloudy, new grade renders it bright-ish | ◑ accepted compromise — one static grade can't be both stormy-at-S/F and blue-on-the-lap; weighted to the lap (where the driving is). The S/F boards/grandstand/scoreboard/crowd all still render (N1 objects hold) |
| NB3 | Verge/bank grass still reads part-khaki-brown on some sections | ◑ terrain-mesh texture limit (as Watkins WG3-grass); sat lift greened it materially but not fully |
| NB4 | Chase rear bodywork skeletal | open — Zandvoort D12 class (gold chase also shows exposed engine, so narrower than it reads) |
| — | S/F floating quad (E59 N2), driver hands, textured tyres | open(minor) / waived |

Before/after native A/B + gold matches verified by re-capture (`nurb`→`nurb_v2`); composites
`parity/nurburgring/video_*`.

### E61 Monza — video gold vs native (native lap 5 744 m)
Gold: a bright sunny day — **hazy pale blue sky + white cumulus over lush GREEN forest** (the
Monza park), grey asphalt, clean signage (OLEOBLITZ/BOSCH/LANCIA/AMOCO/TOTAL/STP/Shell).
Monza's grade was already close (E22/E57); the deviations are smaller than the other tracks'.
| id | deviation (native vs gold) | verdict |
|---|---|---|
| MZ1 | Sky too blue-saturated (native zenith (0.52,0.65,0.86) vs gold hazy (0.58,0.69,0.75)) | **fixed** — `GRADE_MONZA` zenith paled (0.31,0.51,0.80)→(0.40,0.57,0.68), cloud 0.34→0.42; native re-sampled (0.59,0.70,0.77) ≈ gold. `JM_GRADE=MONZAOLD` A/Bs |
| MZ2 | Forest green + road legibility | ✅ E57/E22 hold — native forest reads green, road grey (not the old "snow"), signage crisp |
| MZ3 | A dark angled barrier SLAB stands at the S/F right; grey wall slabs mid-lap | **open** — the sopraelevata banking + some Monza barriers render as flat slabs. `MZ_BANK_B/DARK_B` tone the brightness but the SHAPE is geometry = the deferred **E52** banking-mesh issue |
| MZ4 | Pit garages far-right read washed white/blue | ◑ E57 legibility residual (structure brightness); minor |
| MZ5 | Chase rear bodywork skeletal | open — D12 class |

Sky nudge verified by A/B + gold match (`monza`→`monza_v2`); composites `parity/monza/video_*`.

### E61 Spa — video gold vs native (native lap 14 099 m)
Gold: a bright sunny day — **hazy pale blue sky + white cumulus over lush GREEN Ardennes**
forest/fields, yellow road edge-line, stone walls, village houses. `GRADE_SPA` (E22) was
built for this; only the sky needed the same paling as Monza.
| id | deviation (native vs gold) | verdict |
|---|---|---|
| SP1 | Sky too deep/saturated blue (native zenith (0.48,0.63,0.88) vs gold hazy (0.64,0.72,0.80)) | **fixed** — `GRADE_SPA` zenith paled (0.22,0.45,0.82)→(0.40,0.56,0.70), horizon paled; native re-sampled (0.60,0.71,0.80) ≈ gold. `JM_GRADE=SPAOLD` A/Bs |
| SP2 | Green forest/fields, yellow line, stone walls, village, signage (BP/MARTINI/Gulf/Shell) | ✅ E22 holds — native renders lush green + the roadside furniture; sat 1.34 matches gold's vivid green |
| SP3 | Chase rear bodywork skeletal | open — D12 class |
| — | driver hands / textured tyres | waived |

Sky nudge verified by A/B + gold match (`spa`→`spa_v2`); composites `parity/spa/video_*`.

## E61 close (2026-08-02)
All five circuits judged against their gold LAP VIDEOS this session (sequential, single
session, every capture through `gl-lock` as `julia-racer`). Net graphics changes, all in
`drive_native_mtk.jl` per-track grades (LIVE at next launch — no `jlracer.so` rebuild):
* **Watkins** — sky vivid-blue → hazy pale grey-blue; verge de-yellowed (WG1/WG2).
* **Nürburgring** — the big one: the video is a bright partly-cloudy GREEN day, not the storm
  the 3 stills implied; whole-lap re-green (NB1).
* **Monza** — sky over-blue → hazy pale (MZ1).
* **Spa** — sky over-blue → hazy pale (SP1).
* **Zandvoort** — E60 state re-verified against the videos, no regression.
Each track keeps a `<TRACK>OLD` entry in `GRADE_TAB` so `JM_GRADE=WATKOLD|NURBOLD|MONZAOLD|SPAOLD`
A/Bs the prior grade. Common open items across tracks (deeper, logged not fixed): the
skeletal chase-view car body (D12), the crowd-MIP smear (E46), Watkins' missing tall roadside
forest (WG3), Monza's banking/barrier slabs (E52/MZ3). Method + per-track verdicts above;
composites under `parity/<track>/video_*`.

## E62 — object + cockpit + chase parity (NOT just grades), depth-first (2026-08-02, ongoing)
**Scope correction (PO):** E61 matched only the per-track colour GRADES. It did NOT match
trackside-object location/orientation/colour, nor cockpit/chase GEOMETRY — those were logged
open/waived. E62 is the real object+cockpit+chase pass, done **depth-first: nail Zandvoort
fully, then replicate**. PO put crowds + driver hands back IN scope (overriding the earlier
D8/D13 waivers — the gold videos show both). PO also wants real mirror reflections (RTT).

### Zandvoort (in progress)
Fresh captures (`native/zand` shots, cockpit+chase, gl-lock as julia-racer) vs the 260801
gold videos confirmed the real gaps and produced these outcomes:
| id | item | verdict |
|---|---|---|
| Z-CK1 | Scuttle (windlot) glary olive-GOLD; gold is muted matte tan | **fixed** — `WIND_B/A` 0.60/0.55 → 0.45/0.45 (verified vs gold cockpit) |
| Z-CK2 | Gauge dials dim/dark; gold crisp white-on-black | **fixed** — `JM_DASH_B/A` 1.0/0.60 → 1.2/0.9 (dial faces legible) |
| Z-CH1 | Front wheels splayed outboard of the tub in chase | **improved** — `WTRACK_F` 0.90 → 0.78 (~real 1.52 m track); tucks them in |
| D12 | Chase car SKELETAL (wheels detached, engine exposed) | **root-caused, asset-LOD-limited** — beyond-0.85 lateral is real rear suspension/exhausts MIXED with GPL-hidden-LOD garbage that sprawls as "chrome spider-legs"; a parser drop-by-hide-marker (offset>5 m) was tried+reverted (cut the car 2253→387 tris — this model routes real body through large-offset positioners posmat clamps to origin). Needs GPL's real per-LOD selection. `front1/front3` cyan placeholders now excluded; `JM_CARP_MAXLAT` A/B knob added (default 0.85) |
| Z-CK3 | Mirrors are dark discs; gold shows live reflections | **FIXED — E64 S1 (2026-08-08): LIVE mirror RTT.** See §E64 below |
| Z-CK4 | No gloved hands on wheel; gold has them | **open — mesh refit** (`JM_HANDS=1` still yields giant silver arms; the static arm mesh must be re-fitted to the re-placed wheel/eye) |
| Z-OBJ | Crowd/signage/floating-object parity (V6-V10, E46) | **not yet worked** this pass |

Committed: `2f6a744` (scuttle + tuck + D12 root-cause), `bd427f3` (gauges). Composite
`scratchpad cmp_zand_cockpit`. **Zandvoort is NOT yet "fully nailed"** — mirrors (RTT), hands,
crowd/signage objects, and the asset-limited chase body remain. Watkins/Nürburgring/Monza/Spa
object+cockpit+chase parity **not started**. This is a multi-session program.

## E63 — trackside-object parity (PO reprioritised: OBJECTS first, then cockpit/chase)
PO restated the backlog: **all trackside objects for all tracks — colour, location, orientation
matching the gold mp4s — is the HIGHEST priority**, then cockpit/chase. Running as an autonomous
scrum (PO pre-approves planning + reviews, no per-step input). Sprint S1 = cross-track engine
fixes; S2–S6 = per-track object passes; E64 (later) = cockpit/chase.

### S1 — cross-track object fixes (biggest win: crowds)
| id | fix | verdict |
|---|---|---|
| E63-CROWD | The gold shows DENSE crowds lining every fence/bank; `drop()` was removing them (D8 remove-spectators, now superseded by PO). The crowd ROWS exist in the data (Zandvoort `ppl_l*/ppl_m*/ppl_s*`, Spa `p_s*/people*/pelf*`) | **fixed** (`ebda286`) — reclassified as kept crowd via `standcrowd()`; `onroad_crowd` still drops any on the pavement (E40); single loose figures (marshals/photographers) stay dropped. Verified Zandvoort (Tarzan+S/F) + Spa — crowds present, road clear |
| E46/E63-BLUE | Restored crowd rows rendered garish BLUE (weren't matched by `is_crowd_obj` → skipped `CROWD_TINT`) | **fixed** (`45d393d`) — `is_crowd_obj` extended to the crowd-row names; de-blue deepened (`CROWD_TINT` TB 0.78→0.66, TR→1.16) → warm tan/khaki tones matching gold. The horizontal MIP SMEAR (UV/geometry) is still open |
| E63-SIGN | Some Zandvoort boards (MARTINI, 2nd CALTEX at Tarzan) render as blank white slabs | ◑ mostly the angled BACKS of far-side boards seen on the approach (Castrol/VREDESTEIN/near CALTEX read correct — D6 uBackFlip/dedup holds); logged, low priority |
| E41 | Spa storefronts reported ~90° perpendicular | ◑ NOT reproduced at the S/F/pit-exit (garages read ~parallel; objdiag near-road hits are `epolsp3` fence poles at expected angles). If real it's a specific mid-lap spot — needs the gold landmark |

**Crowds now render on all tracks** (global `standcrowd`/`drop` change; verified Zandvoort+Spa).

### S2–S6 — per-track object survey (all 5 tracks captured vs gold)
| track | state after E63 |
|---|---|
| Zandvoort | signage reads correct (Castrol/VREDESTEIN/CALTEX — D6 uBackFlip holds); crowds restored+warm; residual: a few blank far-side board BACKS (minor), V8/E45 floaters (minor) |
| Spa | crowds (`p_s*`) render; sky hazy-blue; **E41 90°-storefronts NOT reproduced** at S/F/pit (garages ~parallel) |
| Nürburgring | **E44 right-side carbonized RESOLVED** (both sides well-lit); crowds both sides; sky bright partly-cloudy; residual N2 floating quad (minor) |
| Monza | tree-curtain gone; signage/crowds/sky good; **MZ3 dark 'banking' slab FIXED** (`4b34143`) — it was a wide forest STRIP seen EDGE-ON, not banking geometry; `STATICTREES` draw never passed `graze` despite the comment → added `graze=true` so edge-on strips fade, face-on tree-lines stay |
| Watkins | crowds render; sky hazy pale (E61); **WG3 tall roadside autumn forest still missing — confirmed asset-limited**: `JM_DROP_FOREST=0` enables 20 panels but they're distant panoramic STRIPS, not the tall CLOSE trees GPL places as scenery objects; at s=300 native stays barren while gold f_0025 shows dense autumn forest both sides. Needs tree-OBJECT placement (deep), not a toggle |

**E63 object sprint — achievable scope delivered.** Big win: crowds restored + colour-matched
across every track (the dominant object gap). Plus MZ3 slab fixed, E44/tree-curtain/E41 found
already-resolved/not-reproduced. Remaining are asset-deep (Watkins WG3 forest; the D12 chase
body) or minor (blank board backs, N2 quad). Commits: `ebda286` `45d393d` `4b34143` (+docs).
Next phase per PO priority: **E64 cockpit/chase** (mirror RTT, hands refit, chase body).

## E64 — cockpit/chase parity. S1 (2026-08-08): LIVE MIRRORS (RTT) ✅
The PO-requested real mirror reflections (Z-CK3, open since E19's "dark discs"). Every
frame in the cockpit view, the world is rendered a second time from the driver's eye
looking BACKWARD into a small 384×192 FBO (`make_mirror_fbo`), **X-mirrored in clip
space** like a real mirror (`PROJ_MIRROR = scalexyz(-1,1,1)·perspective_revz`, same
reversed-Z as the main pass); a round-masked GLASS QUAD on each disc (`uMirrorGlass`
shader path, disc-local coords in the colour attr) samples its half of that view — left
disc ← left half. The quads are built at load from the MIRRORP mesh itself (per-disc bbox,
thinnest axis = glass normal, nudged 4 mm toward the eye) so they land exactly on the
discs with no hand-placed geometry.
- **Enabler refactor:** the world draw (horizon/track/objects/forest panels/billboards/AI)
  is now one closure `drawworld(vp, eye, flip)` shared by the main + mirror passes — the
  `flip` arg swaps the object-pass culled side because the clip-space X flip reverses
  winding. Chase capture byte-plausibly unchanged (re-verified this sprint).
- **What the glass shows:** live rear world incl. the car's own tail + wheels, per-track
  grade/sky/fog/shadows (same uniforms both passes); content verified to CHANGE with lap
  position (s=600 pit complex vs s=1500 dune bank behind — proves live, not baked).
- **Cost/gating:** the pass runs only in cockpit view, at 384×192 (vertex-bound; no
  measurable frame cost seen in smoke). `JM_MIRROR_RTT=0` restores the old silver discs;
  `JM_MIRROR_FOV` (78°) tunes the rear view.
- **Verified:** cockpit captures `scratchpad/mirror_rtt/mir_s600·s1500` (both discs live,
  round-masked, horizon level, seen through the plexiglass tint as in gold); chase
  regression shot clean; DoD — Zandvoort `JM_SMOKE` race+5-AI exit 0, `test_brush_slip` ✓,
  `test_vehicle_driven` ✓ (`test_corner_tyre:44` legacy-MF failure pre-existing, unchanged).
- **Still open in E64:** driver-hands mesh refit (Z-CK4), chase-body LOD (D12,
  asset-limited); minor mirror polish (image slightly dominated by own tail — GPL-authentic
  but worth an A/B against the gold cockpit video at speed next pass).

### E64 S2 (2026-08-08): HANDS ON THE WHEEL (Z-CK4) ✅ — gold-layout gloved hands + sleeves
The gold cockpit video shows white-gloved fists gripping at **10-and-2** with white sleeves
sweeping from the lower frame corners; we showed nothing (JM_HANDS defaulted OFF after the
"giant silver arms").  Root causes found and fixed:
- **The textures were never the problem** — `lohand.mip` (4 glove views) and `lotarms.mip`
  (pale sleeve weave) ship with the car and decode fine.
- **`lotarms` is authored in a positioner-local frame** (the D12 posmat-clamp family):
  raw, each arm runs from its wrist UP-AND-FORWARD (x→1.01, y→0.52 — forward of the wheel,
  above the eye), which is what read as "giant silver arms in the sky".  Verified by vertex
  scatter (sprint scratchpad `proj_xy/zy`).  **Fix:** `ARMFIX` — 180° rotation in the x-y
  plane about the wrist point (mirror x about 0.74, y about 0.26) so the arms sweep
  DOWN-AND-BACK to the driver, y-squash 0.55 → elbows at lap height, z-tuck 0.55 →
  elbows at the body sides, capture-tuned nudge (dx −0.05, dy −0.06).  All knobs:
  `JM_ARM_{X0,Y0,SY,SZ,DX,DY}`, `JM_ARMS=0` = hands only.
- **The fists sat at 3-and-9** (raw mesh) vs gold's 10-and-2 — opposite per-hand rotations,
  impossible with one transform, so the two fists are SPLIT by z sign at build
  (`split_fists`) and each gets its own grip rotation about the wheel axis
  (`JM_HAND_GRIP`=30°; hands ride the wheel rotation, arms static — GPL articulation).
- **Extraction moved out of CARP** (`HANDP`/`ARMP` like DRIVERP) — always excluded from the
  body; `JM_HANDS` now defaults **ON** (0 hides).
- **Verdict vs gold** (captures `hands_fix3/fix4` vs `gold_hands_zoom`): layout parity —
  sleeves from the lower corners over the lower rim (gold does this too) to gloved fists at
  10-and-2.  Residual: the mesh is chunky/faceted with a marbled weave (the asset itself;
  same class as D12) — logged as polish, not a blocker.
- DoD: race+5-AI smoke exit 0, `test_brush_slip` ✓, `test_vehicle_driven` ✓ (run post-edit).

### E64 S3 (2026-08-08): the cockpit GENERALIZES — 5-track mirror+hands sweep ✅
S1/S2 were verified depth-first on Zandvoort; the mirror pass exercises per-track world
branches (Monza's per-surface `TRACKCAT` grades, `STATICTREES`, per-track skies), so S3
swept a cockpit capture on the other four circuits (`ck_<track>` shots, each run its own
`gl-lock` hold so the neighbours could interleave).  **All four PASS:**
| track | mirror content (both discs live) | hands |
|---|---|---|
| Nürburgring | bright partly-cloudy sky (E61 re-green grade), pit boxes behind | ✓ identical |
| Watkins | hazy pale sky, the KENDALL/DUNLOP gantry structure behind at s=600 | ✓ |
| Monza | hazy-pale sky, grey (not blinding) road behind — the E57 per-surface grade holds in the mirror pass | ✓ |
| Spa | dense green tree-line + crowd rows behind, hazy-blue sky | ✓ |
Composite: `parity/cockpit_e64_mirror_sweep.jpg`.  Per-track content + grade in the glass
proves the mirror pass runs the full per-track world path, not a cached/generic scene.
No code changed in S3 — a pure verification sprint.  E64 remaining: D12 chase LOD
(asset-deep), mirror/hands polish vs gold video at speed.

### E64 S4 (2026-08-08): DE-SPIDER THE CHASE CAR (D12) ✅ — spider-legs eliminated
D12 ("chase car SKELETAL — chrome spider-legs") had been closed as asset-LOD-limited in
E62.  S4 reopened it with mesh forensics and eliminated the garbage in three findings:
1. **PRIM node 0x11 is GPL's LOD/distance switch** — `lotus.3do` has 47, with descending
   range thresholds (4.0 / 2.5 / 0.0); the walker rendered EVERY child = every LOD at
   once.  Now: distinct thresholds ⇒ keep only the min-threshold (highest-detail) child;
   all-equal thresholds ⇒ plain list-group, keep all.  `JM_LOD_ALL=1` A/Bs.  2253→2148
   tris; every `.3do` parse benefits (cars, wheels, scenery).
2. **Groups 27288/39792 are whole displaced assemblies** — suspension+exhaust+DRIVER
   textures at y 0.42…1.16 (above the body) and −1.12…−0.42 (underground), mirror copies:
   GPL runtime-hidden branches our positioner walk mis-places.  Their CARP share drew the
   wheel-face blades; their **DRIVERP share (lid/arms tris, chase-only, previously
   group-unfiltered) drew the remaining spears** — the pale weave "arms" texture is why
   the spears looked chrome/silver.  Excluded from CARP, DRIVERP and FSUSPP (which also
   inherited 1.65 m lsusp1 garbage 2 m ahead via group 6600).
3. **Wheel meshes and the tail exhausts are clean** — probes confirmed nothing else in
   `lotus.3do` reaches beyond the body envelope; group 116576's long tris are the real
   tub/body panels (kept).
**Verdict** (`parity/chase_e64_despider_ab.jpg`, before/after at s=600): rear tyres clean,
no blades, no spears; exhausts, rollbar, engine detail and helmet intact; cockpit view
unaffected (hands/mirrors/dash/front-tyres re-verified).  Honest scope: this REMOVES
mis-placed geometry rather than restoring GPL's articulated suspension — the chase rear
shows less suspension detail than gold; that residual stays D12-open as a
positioner-articulation effort.  Monza spot-check post-LOD-fix clean (fragile track).

### E64 S5 (2026-08-08): THE WATKINS FOREST (WG3) ✅ — "asset-limited" overturned
E63 closed WG3 as asset-limited ("native stays barren; needs tree-OBJECT placement").
Wrong on both counts, established by forensics + capture:
- **The forest ships with the track and we were dropping ALL of it.**  `watglen.3do`
  places `tree3–18` (19–39 m tall × 78–380 m wide strips), `treefill×10`, `intree1/1a`
  and `treesrb×13` — every class was eliminated by pre-graze-fade drop rules
  (`DROP_FOREST=1` default + unconditional `treefill`/`intree`/`treesrb` drops written
  for the old camera-faced-wall / edge-on-smear artifacts, E22 era).
- **Graze-fade (MZ3) already solved those artifacts** — Monza has run the same strips as
  static authored-yaw panels since E63.  Fix: `WATGLEN` joins Monza's `DROP_FOREST=0`
  default and the three unconditional drops are gated `!WATGLEN`.  Watkins now keeps
  72 objects + 13 billboards + **30 forest panels** (was 0).
- **Verified at defaults** (`parity/watkins_wg3_forest_ab.jpg`): the s=1200 stretch has
  tall autumn/pine forest lining the roadside like the gold; the PIT STRAIGHT — the
  historical smear location — stays clean (KENDALL/DUNLOP gantry, no wall, no smear).
- **E63's verdict was also made from the wrong vantage:** its "barren at s=300"
  comparison against gold t=25 s paired different corners (gold t=25 s ≈ s 900–1100 at
  lap pace), and **`place_at_s!` puts the car on the GRASS at Watkins s=300 and s=1200**
  (visible in the chase captures) — the road is metres away.  Logged as **WG4** (new):
  affects JM_SHOTS vantages and possibly SHIFT-R recovery; the E54 JM_SWEEP "no
  false-grass" result needs reconciling with it.  Diagnostic added: `JM_KEEPTEST`
  (force-keep name prefixes past every drop rule — the mirror of `JM_DROPTEST`).
- DoD: race+5-AI smoke exit 0, brush + driven tests green (run post-edit).

### E64 S6 (2026-08-08): WG4 — the road-only HAT that never was ✅
WG4 (S5's find: `place_at_s!` strands the car on the grass at Watkins s=300/1200) is fixed,
and the root cause is a doc-vs-code lie of the MA-S66 family: **the comment at the TERRAIN0
build claimed a "ROAD-only HAT", but `build_hat` keeps ALL horizontal terrain** — its
`road_pred` only informs Monza's overpass logic.  Consequences: `align_centreline` printed
"100% on terrain" while the line ran on grass (it was measuring grass as road);
`recentre_on_road` measured GRASS APRON edges as road edges; and its skip-if-off-road guard
made stranded sections unfixable by design (a point on the grass never recentred).  The E54
JM_SWEEP "no false-grass" pass never contradicted any of this because it tests the
centreline against the ribbon BUILT FROM that same centreline — self-referential.
- **Fix:** a true `ROADHAT` (road/kerb/paint textures only — `ROAD_TEX`: asp*/groove/curb/
  kerb/sline/sgrid/start; <200 recognised road tris → fall back to full terrain, behaviour
  unchanged) now drives `align_centreline` + `recentre_on_road`; physics keeps the full
  terrain (grass stays drivable).  `recentre_on_road` gains an off-road RESCUE branch
  (scan both ways for the road, step toward it, capped) + multi-pass convergence
  (Watkins: pass 1 max 4.0 m → pass 4 max 1.0 m; the road-only oracle also refined the
  global alignment by ~18 m in x).
- **Verified** (`parity/watkins_wg4_placement_ab.jpg`): car ON TARMAC at s=5 (KENDALL
  banner), s=300 (now framing gold f_0025's straight correctly), s=1200 (forest stretch).
- **Scope decision — the road-only oracle is GATED TO WATGLEN.**  The cross-track gate
  (all four other circuits smoked under it, exits 0) showed the stats moving in ways that
  need their own verification: Zandvoort's line shifted pass-1 mean **2.19 m** (its old
  PO-verified recentre moved 0.12 m — a silent 2 m move of the racing line the AI drives
  and every parity capture frames), and Nürburgring aligned at only **54%** on road-only
  (= `ROAD_TEX` under-recognises its road textures; the grid-search translation then
  optimises against a partial road).  Blanket-switching verified tracks on those numbers
  would be the S9-family mistake.  Non-Watkins tracks keep their verified full-terrain
  single-pass behaviour (`JM_ROADHAT=1` forces the oracle on for experiments); extending
  per-track is follow-up work: recognise each track's road textures, then capture-verify.
- Gates: Watkins re-verified on the gated build (car on tarmac, pass-4 convergence);
  Zandvoort stats confirmed back to the old baseline; race+5-AI smoke + brush/driven green.

### E64 S7 (2026-08-08): the articulated rear end (D12 residual) — ◑ PARTIAL, shipped OFF
The gold nintendo chase **clearly shows the full articulated rear end** (arms, driveshafts,
shocks, discs between the rear tyres — reference frames extracted from the 260801 video),
so the D12 residual is real parity work, not cosmetic-null.  What the sprint established:
- **S4's "displaced assemblies" reading was axis-confused** — GPL raw is X-fwd/Y-LATERAL/
  Z-up, so groups 27288/39792 are the LEFT/RIGHT high-detail rear-suspension halves,
  near-correctly authored around the rear axle (arms/axlelot/lshok/lbrdisc/lsusp2-7 per
  side); their over-reach (shocks to lateral 1.06 vs the 0.85 wheel face) is why fragments
  read as spears when drawn via DRIVERP.  The S4 exclusions remain correct for
  CARP/DRIVERP (they stop the garbage); the halves need their OWN correct transform.
- **Harness landed** (all committed, default OFF): `include_groups` extractor option,
  per-side extraction + draw in chase view, corrective-transform knob set
  (`JM_RSUSP`, `JM_RS_{SX,SY,SZ,DX,DY,Y0,Z0,ROLL,SWAP}`), gold reference frames.
- **Three capture iterations bounded the problem** (scale-only → wings up ~50°; ±50° roll
  → folded under; ±25° → fans trailing backward): the residual mis-rotation is **NOT a
  pure X-roll** — empirical angle-guessing is the wrong method and was time-boxed out.
- **Prescribed next method:** dump the actual POSITIONER CHAIN (node type, translation,
  Euler triple, scale, per node) on the path to groups 27288/39792 and compose the real
  transform — the same stop-guessing-measure-instead move that solved ARMFIX and the
  0x11 LOD switch.
- Shipped `JM_RSUSP` default **0**: the chase view is byte-plausibly the S4 de-spidered
  state; race+5-AI smoke green.  D12 residual stays OPEN with the harness ready.

### E64 S8 (2026-08-09): READ THE POSITIONER CHAIN — D12 rear suspension SHIPPED ✅
S7's prescription executed: a standalone probe dumped the full node chain to groups
27288/39792.  It reads:
`[POS d=(0,20,0) — the PARK translation, clamped→0 by posmat (correctly un-parking the
whole high-detail branch, main body included)] · [LOD selectors] · [POS type 0x16
d=(−0.893, ±0.772, 0.02), yaw 2°, s=1.0]` — **the halves are placed AT THE REAR HUBS by
the file itself** (±0.772 = the rear track ✓, scale exactly 1.0).
- So S7's residual was never scale or a mid-assembly roll: the assemblies are **authored
  in a flat horizontal pose** (identity capture: wings splayed flat outward at wheel
  height) and need a ~90° fold about the **HUB LINE z=±0.772** — S7 folded about
  z=0.35 (mid-driveshaft), hence its under-fold/backward-fan artifacts.
- Hub-pivot fold verified by capture: 50° and 90° both tuck the assemblies correctly
  inside the wheels (near-identical from the chase — tyres/gearbox occlude); **90° kept**
  as the geometrically-motivated flat→vertical value.  Scale reset to the chain's 1.0.
- **Shipped ON by default** (`JM_RSUSP=0` hides; `JM_RS_*` A/B): the chase rear end now
  carries the articulated suspension mass the gold nintendo shows.  Honest residual:
  from the low chase camera most detail hides behind the tyres/gearbox — the visible
  delta vs gold is modest; the structure is there for higher cameras/replay angles.
- **D12 → CLOSE-minus.**  DoD: default-config captures clean, race+5-AI smoke,
  brush + driven tests green.

### E64 S9 (2026-08-09): "Does anyone else stand on the grass?" ✅ — Ring fixed, rest cleared
The S6 follow-up executed as an EVIDENCE-FIRST survey: 16 chase captures (4 positions ×
Zandvoort/Monza/Spa/Nürburgring, default config) asked whether WG4-class off-tarmac
placement exists beyond Watkins before extending the road oracle anywhere.
- **Zandvoort / Monza / Spa: CLEAR** — on tarmac at every sampled position (Zandvoort
  s=2100 hugs the edge, which is the PO-approved GPL-groove trait, not a defect).  The
  per-track ROADHAT extension for these closes as **no-defect — evidence, not caution**:
  their oracles stay off because nothing is wrong, and S6's stat-based worry about
  moving their lines is moot.
- **Nürburgring: REAL offender** — s=5700 half on the verge, and at s=17000 the car sat
  in the CATCH-FENCING (the long-known "centreline drift near lap-end" note, now with a
  face).  Root cause of the 54% road-only alignment: `ROAD_TEX` missed the Ring's road
  vocabulary — `atog*`/`a_l_g*` (asphalt-to-grass edge strips) and `Concrete` (the
  Karussell!).  Recognised (33 090 road tris), the oracle CONVERGES: recentre mean
  2.41 → 1.27 → 0.26 → **0.04 m** over 4 passes, and all four positions land on tarmac —
  including s=17000 out of the fencing.  **NURB joins WATGLEN in the ROADHAT default.**
  (`parity/nurburgring_wg4_oracle_ab.jpg`; the green plates at s=17000 are the known
  N2-family scenery quads, separate item.)
- DoD: Ring smoke default-config, Zandvoort race+5-AI smoke, brush + driven green.

### E64 S10 (2026-08-09): MIRRORS AT SPEED — per-disc cameras ✅
The S1 residual ("image slightly dominated by own tail") judged against gold cockpit
frames at speed: gold's discs are ROAD-dominated with the rear tyre at the INNER edge and
mirrored signage; ours were tail-centred with sky above.  A tilt A/B (−0.45/−0.8) proved
a single eye-centred rear camera can never match — the tail fills frame centre at any
pitch, because each real mirror sees backward-OUTWARD from its cowl position.
- **Fix: one camera per disc** at the mirror's own position (`JM_MIRCAM_X/Y/Z`, z
  mirrored), rendered into per-half FBO viewports (same pixel cost; the glass quads'
  half-split UVs unchanged), with outward yaw (`JM_MIRROR_YAWOUT` 0.5) and a mild down
  component (`JM_MIRROR_DROP` −0.2); per-half square aspect in `PROJ_MIRROR`.
- **Verified vs gold t=40 s** (`parity/mirrors_e64_percam_ab.jpg`): tail now at the inner
  edge only, road/scenery dominating both discs — gold's composition.  Residual: gold
  reads the rear TYRE specifically where we read tail bodywork; horizon a touch higher
  in gold — tune-by-eye territory, knobs shipped.
- Hands at speed: gold frames show the same 10-and-2 gold layout S2 shipped — no delta.
- DoD: race+5-AI smoke, brush + driven green.
