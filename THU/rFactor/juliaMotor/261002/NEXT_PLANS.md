# Julia Racer — next plans (written 2026-10-02, after the 2026-10-02 cycle)

The record of each sprint is in `PRODUCT_BACKLOG.md` (section *CYCLE 2026-10-02*). Replaces `261001/NEXT_PLANS.md`.

**Rules carried forward:** at most 4 sprints per item before rotating; a review and retrospective sprint before
restarting an item that already has 4. Follow `260928/TOKEN_EFFICIENCY.md`. **Start a fresh session for this cycle:**
the 2026-10-01/02 session ran several cycles in one context.

---

## Waiting on the PO

| item | the ask | why |
|---|---|---|
| **MP-GUI-1** | try a two-PC race from the launcher: one PC *Host a race*, the other *Join a race* → *Get host's settings* → Launch (host first) | tested with two launchers on one box; a real LAN and firewall have not been tried |
| **PERF-3** | run `~/Documents/261001/JuliaRacer-x86_64-261001c.AppImage` and say whether it holds 60 fps | settles the item; the window now appears ~3.6 s later but without the first-frame freeze |
| **E108** | the track and station (or a screenshot) where the road or white line looks faceted | shading and finer rounding both ruled out by A/B |
| **E91** | one iRacing coast-down on a straight, ~220 → 60 km/h, clutch in, then the same in gear | pins drag and engine braking together |
| **E109** | GPL screenshots of the Ring at s≈8400 and s≈21355 | GPL's tree data vs our rotation pivot |
| **E90** | a look at Monza s≈1000–1500 and Watkins Glen s≈500–750 / 2500–3000 | rails on road-textured triangles |
| **E108** | a screenshot or lapdist of a Ring corner whose white line looks angular | the four sharpest corners look smooth at full res (`JM_SHARP`) |
| **GFX-1** | try Full screen + Native from the launcher | not exercised here (it would take the display) |


---

## Next cycle, in order

### 1. AI-CARGFX — GPL's flat-colour polygons (S7 found the cause of the dark engine bay)
- 80 % of every AI car's triangles are flat-colour polygons drawn one constant grey. Read GPL's per-polygon PALETTE
  colour for them (gpl3do.jl: where `col` is set for untextured polys), and check the Eagle's nose turns dark blue.
- Then draw order: flat parts first, textured parts with a small depth bias (GPL paints detail over its backing), A/B
  against `JM_AI_EXC_FLAT=1` (`261002/aicargfx_eagle_flatpolys_ab.jpg`).
- Then the other items of S6 (helmet, roll hoop, loose white shards, rear cross-tube), then the other four chassis.
- The player's Lotus loads through the same extractor: check it for the same flat-polygon colours.

### 2. E78 — banners against the gold (the banners reach the screen, S6)
- Full-res crop of the pit wall at Ring s≈1400 against the gold frame at ~66 s of `260802_nurburgring_cockpit.mp4`.

### 3. FLOAT-2 / E109 — long foliage panels on slopes
- Ring `trow_001` tree-row panels: one end ~5 m off the ground (no pitch in GPL's data). Decide: fit each long foliage
  panel's pitch to the ground under its ends, or leave as GPL draws it (needs a GPL screenshot of e.g. Ring s≈3650).

### 4. GPLWALL-1 follow-ups
- AI cars still use the old contact; the planar `JM_2D` path is not covered.
- Zandvoort registers poorly (23 %): register its walls against the placed hedge/fence objects too.

### 5. E108 — waiting on the PO's screenshot of an angular white line.

### 6. MP-GUI-1, PERF-3, GFX-1 full screen — after the PO's tests.

---

## Items from earlier rotations, still open

| item | next step |
|---|---|
| **RACESTART-1** | second AI car stalls behind a stalled player at lane 1.56, v = 0. Repro: `JM_RS_FINAL=1 JM_RS_V0=25 JM_RS_BACK=150 JM_RS_SECS=60 julia --project=demo/native demo/native/racestart_probe.jl` |
| **E91 / E109 / E90 / E108** | blocked on the PO (above) |

## Tools added this cycle

| hook | what it does |
|---|---|
| `JM_AI_GPLROAD_GRADED=0` | revert E107's graded on-road test to the centre-only test |
| `JM_SHOW_AFTER=<n>` | hidden warm-up frames before the window appears (default 2; 0 = old behaviour) |
| `JM_PLACE_HIDE=<names>` | drop named scenery placements and print their transforms (E81) |
| `JM_AICAM=<slot>` | chase camera on AI car slot 1–5 (Ferrari, Brabham, BRM, Eagle, Cooper) |
| `JM_GPLWALL=0` | GPLWALL-1 collision physics off (walls + drawn obstacles); `JM_GPLWALL_HMIN`, `_PEN`, `_REG`, `_SGN` tune it |
| `JM_GPLWALL_SHOW=1` | draw every GPL wall face as a magenta ribbon |
| `JM_GPLWALL_CENSUS=1`, `JM_GPLWALL_INTERIOR=1`, `JM_GPLWALL_INVIS=1` | wall placement / reachable-obstacle / invisible-wall censuses (print and exit) |
| `JM_CRASH="s:L|R:deg:mps;..."` or `auto:<m>` | drive the player into the boundaries; `JM_CRASH_ANG`, `JM_CRASH_V`, `JM_CRASH_FRAMES`, `JM_CRASH_TRACE=1` |
| `JM_DRAW_WIREF=0` | old exclusion of the wire catch-fences |
| `JM_OBSTACLES=0` | drawn-obstacle collision off (GPL walls stay) |
| `JM_PICK="x,y;..."` | on JM_SHOTS frames: the drawn triangles under each pixel (name, texture, lapdist) |
| `JM_OBJ_PR=<pitch sign>,<roll sign>` | GPL placement pitch/roll on placed objects (default -1,0) |
| `JM_OBJPROFILE=<name>|all` | an object's height above the ground along its length / the long-object score |
| `JM_AIPLACE="<slot>:<s>:<lane>"` | stand an AI car at a station (with `JM_AICAM`) |
| `JM_FINDTEX=<prefix>` | where a texture is used (lapdist, lateral) |
| `JM_AITEX=1`, `JM_AI_EXC_FLAT=1` | AI untextured-part census / drop flat-colour polygons (A/B) |
| `tools/appimage/build_julia.sh` | now takes `JR_PROJ`, `JR_GPLROOT`, `JR_APPDIR`, `JR_LIBS_FROM` (reuse an extracted AppDir's Qt libs and icon) |
