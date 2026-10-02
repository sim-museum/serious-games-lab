# Julia Racer — next plans (written 2026-10-01, after the 2026-10-01 cycle)

The full record of each sprint is in `PRODUCT_BACKLOG.md` (section *CYCLE 2026-10-01*). This file is the to-do list.
It replaces `260930/NEXT_PLANS.md`.

**Rules carried forward:** at most 4 sprints per item before rotating. Before restarting an item that already has 4
sprints, run a review and retrospective sprint first. Follow `260928/TOKEN_EFFICIENCY.md`, and start a fresh session
per cycle.

---

## Waiting on the PO

| item | the ask | why |
|---|---|---|
| **MP-GUI-1** | try a two-PC race from the launcher: one PC *Host a race*, the other *Join a race* → *Get host's settings* → Launch (host first) | tested with two launchers on one box; a real LAN and firewall have not been tried |
| **PERF-3** | run `~/Documents/261001/JuliaRacer-x86_64-261001.AppImage` and say whether it holds 60 fps | settles the item; the window now appears ~3.6 s later but without the first-frame freeze |
| **E108** | the track and station (or a screenshot) where the road or white line looks faceted | shading and finer rounding both ruled out by A/B |
| **E81** | a screenshot or station of any building or billboard that looks wrong, besides the Ring panel | one real defect known (Ring s≈1350–1500) |
| **E91** | one iRacing coast-down on a straight, ~220 → 60 km/h, clutch in, then the same in gear | pins drag and engine braking together |
| **E109** | GPL screenshots of the Ring at s≈8400 and s≈21355 | GPL's tree data vs our rotation pivot |
| **E90** | a look at Monza s≈1000–1500 and Watkins Glen s≈500–750 / 2500–3000 | rails on road-textured triangles |
| **E108** | a screenshot or lapdist of a Ring corner whose white line looks angular | the four sharpest corners look smooth at full res (`JM_SHARP`) |
| **GFX-1** | try Full screen + Native from the launcher | not exercised here (it would take the display) |

---

## Next cycle, in order

### 1. E81 — the skewed Ring panel (3 sprints used this pass; 1 left, then retro)
- Build the **per-pixel pick**: `JM_PICK=<x>,<y>` on a `JM_SHOTS` frame casts a ray from the shot camera through that
  pixel and prints the nearest triangle over the track `.3do`, the scenery groups and every placed object, with
  object or group name, texture and world position. Lists have failed three times; picking is decisive.
- First, explain why the s=1350 chase shot shows the slab on the RIGHT (`261001/e81/ring1350_chase_control.jpg`)
  while `260930/e78/ring1350_skewed_panel.png` shows it on the LEFT.

### 2. E78 — banners (retro done; S6 next)
- With the pick tool: do the 36 `bannr_s` triangles at Ring s≈1400 reach the screen? Pick the pixels where the banner
  should be; compare a full-res crop with the gold frame at ~66 s of `260802_nurburgring_cockpit.mp4`.

### 3. AI-CARGFX — Eagle A/B (1 sprint used)
- Match the gold location: Watkins Glen corner by the Great Western sign (`eagle/Screenshot From 2026-06-26
  17-54-52.png`). Needs a way to place the AI car at a station (an `AIplace!` hook next to `JM_SHOTS`).
- Then one item at a time from the list in AI-CARGFX-S6: dark engine bay (try `JM_AI_AMB` / `JM_AI_BRIGHT` first,
  then textures), helmet colour and roll hoop, loose white suspension shards, missing rear cross-tube.
- Then the other four chassis.

### 4. E107 — AI (2 sprints used; GPL's line on 5 of 5 tracks)
- Spa's pass rails: pass1 93.2 %, pass2 88.3 % centre-only. Score them with the graded test before using them.
- Plan items 4–6: per-rail speeds (pass1 vs race differ by up to 24.5 m/s at the Ring), `driver.ini` personalities and
  overtaking rules, GPL's `aiAdvanceCarOnLine()` against our tyre model.

### 5. MP-GUI-1 — multiplayer in the launcher (S1 done)
- After the PO's two-PC test: a *Ready* handshake so both sims launch together, and showing the remote player's name
  and connection state in the launcher.

### 6. PERF-3 — after the PO's verdict on the AppImage.

### 7. GPLWALL-1 — never through any object (S1-S8 done; 0 of 378 crashes through)
- PO 2026-10-01: GPL's invisible walls are KEPT (GPL behaviour). Nothing to do there.
- AI cars still use the old contact (the request named the user's car); the planar `JM_2D` path is not covered.
- Zandvoort registers poorly (23 %): its barriers are hedges and post-and-wire fences (thin posts); register against the
  placed objects as well.
- Cost while in contact 0.3-0.8 ms/frame (Ring): profile `obs_gap` density at the Ring if frame rate suffers.

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
| `tools/appimage/build_julia.sh` | now takes `JR_PROJ`, `JR_GPLROOT`, `JR_APPDIR`, `JR_LIBS_FROM` (reuse an extracted AppDir's Qt libs and icon) |
