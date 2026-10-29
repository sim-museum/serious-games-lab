# TUE - flight sims: product backlog

## EPIC WW2SIM - a new WWII dogfight simulator (plan agreed 2026-10-28: see "The plan" below)

**Resumed 2026-10-28** (on hold earlier the same day). Back in the scrum rotation. Why it matters, in the
user's words: "SDOE is dead code, a fact that must be distressing
to those who created hundreds of aircraft for it. I think resurrecting it is in the spirit of all these
community members (some dead now - moding old sims is an old man's game)".

User, 2026-10-28: "find IL2: cliffs of dover .exe on the external drives and decompile it. Also decompile
SDOE in ~/sgl/TUE. This is working toward creating a new WWII dogfight simulator with detailed damage
modeling based on flightgear open source code, and adding community-generated SDOE graphics - an idea to
be refined later"

Goal: a WWII dogfight sim built on FlightGear (open source, flight dynamics + scenery; ~/sgl/TUE/flightgear
holds the training launchers: P-51D, Bf 109, F-86, MiG-15), with detailed damage modeling learned from IL-2
Cliffs of Dover and SDOE, and SDOE's community-made aircraft art.

### WW2SIM-1 Find IL-2 Sturmovik: Cliffs of Dover on the external drives
- Found 2026-10-28 (rumi3 index 260301dirList.txt), /run/media/m/rumi3/200215bak4t/201231/Downloads/:
  - `IL-2 Sturmovik_ Cliffs of Dover.zip` (687 KB): one 760 KB .exe, an installer / downloader stub, not
    the game. A "Crack" zip sits next to it; treat both as untrusted (own empty folder, never run them).
  - `Team Fusion CloD v4.3 Patch.zip` (586 MB): the likeliest source of real game binaries.
  - Settings / mission folders only: `.../Documents/1C SoftClub/il-2 sturmovik cliffs of dover (- MOD)`
    in the 2015 backups on rumi3.
- Still to check: a Steam install (steamapps/common/IL-2 Sturmovik Cliffs of Dover Blitz) in the newer
  rumi backups (search 260803dirList.txt / 260622dirFile.txt for `steamapps`), and the Blitz edition.
- Done when the game's executable and its DLLs / .NET assemblies are copied to a scratch folder.

- Status 2026-10-28 (sprint 1): no base game on the drives; the TF 4.3 patch's payload holds the full
  `maddox.dll` (23 MB .NET, obfuscated) and `partBob.dll` (.NET, readable): extracted to ~/ww2sim_re/clod.
  Notes ~/ww2sim_re/out/NOTES.md.

### WW2SIM-2 Decompile Cliffs of Dover
- Identify the toolchain first (as for Q-Plus: Detect-It-Easy / headers). Much of CloD's game logic,
  scripting included, is in .NET assemblies, which decompile to readable C# (ILSpy / ilspycmd); native
  parts go to Ghidra (~/opt, as in ~/qplus_re). (The .NET share is from memory: check it on the binaries.)
- Targets: damage model (component hit boxes, structural / control / engine / fuel / oil / coolant / fire
  systems, pilot wounds), ballistics (calibre, penetration, ammo types), engine and FM interfaces.
- Output: notes and recovered data tables in a private folder (not a public repo).
- 2026-10-28 sprint 2: ilspycmd installed; partBob.dll decompiled, maddox.dll's method bodies are
  encrypted (anti-tamper) and were not unpacked. From metadata + partBob (sprint 1-2): aircraft = a tree of named limbs with per-limb damage events (onLimbDamage,
  shedWing), cockpits mirror damage on gauges / glass.

### WW2SIM-3 Decompile SDOE (Fighter Squadron: Screamin' Demons Over Europe, 1999)
- Installed by the user 2026-10-28. Sprint 2: OPSim.dll / .par / .sm structure read - every model part is
  an object with damage, material, weight, skin strength and its own airfoil elements. Design notes v0:
  ~/Documents/261028/ww2sim_design_notes.md.
- Install under ~/sgl/TUE/SDOE (INSTALL/Fighter_Squadron_SDOE_DVD.iso, fspatch150.exe; launchers
  WWII_SDOE.sh / WWI_SDOE.sh, Lutris fshack-7.2 runner); the engine DLL is opsim.dll.
- Targets: its per-part damage model and flight model, and the aircraft / object file formats the
  community's add-on aircraft use (so their art can be converted).

### WW2SIM-5 Decompile IL-2 Sturmovik and IL-2 1946
- User 2026-10-28: "also for WW2SIM decompile IL-2 sturmovik and IL-2 1946, WWII flight simulators that are
  probably on the external drives".
- Found (rumi3 index): the GOG installer of IL-2 Sturmovik 1946 2.0.0.6 (setup .exe + 4 .bin, 5.5 GB)
  and the 2.0.2.8 patch, in .../back14Jun2015/bowWin14Jun2015/Documents/GOG.com Downloads/il_2_sturmovik_1946
  (copy in 200215bak4t/200226allUSBdrives/orangeSwitchbladeLexar/28Jun2013). 1946 is the complete
  edition (original IL-2, Forgotten Battles, Aces Expansion Pack, Pacific Fighters). The original IL-2 /
  Forgotten Battles appear only as 2003 Start-menu shortcuts in old PC backups (no game files).
- 1946 = Java game (bundled JRE, il2fb.exe launcher) + native il2_core.dll / il2_corep4.dll (MSVC 7.1
  runtime), game classes and data in 65 .SFS archives. Extracted with innoextract (no installer run).
- Targets: the damage model (per-part "cut" / damage states, ballistics, fire / fuel / oil systems),
  the flight model (FM data files), and how 1946's aircraft are split into named parts.
- 2026-10-28 sprint 4: the .SFS archives (classes, FM data, models) are encrypted - not decrypted (it
  would defeat the protection). Readable: il2_core.dll (engine JNI: named-chunk hierarchical meshes,
  ray-vs-face hit detection) and DeviceLink (a documented UDP telemetry interface: measure the FM /
  damage behaviour by running the game). Notes ~/ww2sim_re/out/NOTES.md.

### WW2SIM-4 Recommendations for the FlightGear-based sim
- Done 2026-10-28: superseded by "The plan" below.

## Scope and research (2026-10-28, resumed)

User, 2026-10-28: "add WW2SIM to the working backlog with aircraft flyable in both il2fb and SDOE as the
aircraft to be modeled, using SDOE aircraft graphics, flightgear physics and terrain/clouds, and
il2fb-generated flight data (with claude flying the il2fg aircraft to generate flight data, as earlier
today). Consider the question of whether to adapt flightgear code, or to use julia/modelica-like component
modeling of aircraft as in julia racer, or ...? and with SDOE-style game mechanics - or would il2fb game
mechanics be better? Damage modeling is an important aspect of games in this genre. Research how to make
this proposed new game"

Research v1: ~/Documents/261028/ww2sim_game_research.md (with sources). In short:
- **Aircraft:** IL-2 1946 flyables that SDOE has as community models: 73 close variants, ~30 more in other
  variants (list in the research, appendix A). Parsoft's stock types are excluded; for the P-51D and the Ju 88A-4,
  use other variants.
- **Physics:** recommended a component model in Julia (parts with their own aerodynamics, mass and systems,
  authored as in Julia Racer and compiled to a fixed-step real-time step), because damage comes out of its
  structure and it scales to ~100 aircraft by fitting. FlightGear's best JSBSim models (the P-51D first) are its
  validation targets. Decided by a bake-off against JSBSim plus a damage layer (WW2SIM-11).
- **Terrain and clouds:** FlightGear as the image generator for the first milestone; our own renderer (Julia
  Racer's, reading FlightGear's World Scenery and drawing clouds its way) for the game.
- **Game mechanics:** SDOE's physical part damage plus IL-2's internal systems (fuel, oil, coolant, engine,
  controls, pilot wounds) and ballistics; IL-2's game structure (QMB, dynamic campaign, career, AI skill levels,
  gunners, event log), with SDOE's Scramble as the instant start. The AI gets its own epic.

## The plan (2026-10-28)

User, 2026-10-28: "build an il2-like sim, using SDOE graphics and combat mechanics, flightgear flight models
and il2-fb test flights for data" - "similar to julia racer - looks like GPL, but with a better engine
underneath".

Vision: an IL-2-style WWII dogfight sim that looks like SDOE (its period, low-polygon community aircraft)
with a modern engine underneath, as Julia Racer is to GPL.

Pillars:
- **Flight models - JSBSim.** FlightGear's flight-dynamics engine, used as a standalone library (LGPL), not
  the whole FlightGear program. FlightGear's WWII aircraft (P-51D, Spitfire, Bf 109 and others) are the
  starting flight models; their quality varies and most are GPL (check each one's licence).
- **Truth data - historical first, IL-2 second.** Historical flight-test reports set speed, climb, turn
  and roll targets. IL-2 1946 test flights (DeviceLink autopilot, WW2SIM-5) fill the gaps history leaves
  (stalls, spins, damaged handling) and benchmark one model against another. Measured numbers, never IL-2
  code or data files.
- **Combat mechanics - SDOE's design, re-implemented.** Every part is an object with hits, material, skin
  strength, weight, its own airfoil elements, detach rules and dependent parts (WW2SIM-3). Damage state
  feeds JSBSim's aerodynamic functions, so a holed wing loses lift and a lost aileron loses roll authority
  through the same physics. The design is reused, not SDOE's code.
- **Look - SDOE community aircraft**, imported through Parsoft's published OpenPlane model-format spec
  (Media/Readme Files/OpenPlane.doc in the SDOE install); see the asset policy.
- **Regression suite.** The same autopilot manoeuvres flown in IL-2 are flown in the new sim, every build.

### Asset policy (revised 2026-10-28 when the epic was resumed, after the user's view: permission requests to
authors who cannot be found only keep the community's work from being seen)
- Community SDOE / FS-WWI models may be converted and distributed free, never sold, each with its readme
  credits on a credits screen; a good-faith search for each author before release; anything an author objects
  to is removed at once. Never Parsoft / Activision content (below). The importer stays, so a player can also
  convert their own install. Points 1-3 below were the policy before this revision. (A policy summary, not
  legal advice.)
- The SDOE install (~/sgl/TUE/SDOE) has 245 WWII aircraft folders: 10 stock types by Parsoft (in the 1999 base archive
  data1.par: B-17G, Fw 190A, Ju 88A-4, Lancaster, Me 262, Mosquito, P-38J, P-51D, Spitfire, Typhoon), the
  rest community-built (1999-2006: BasePack, SGU, LDOR, ActionPack and others). FS-WWI has 51 aircraft
  folders, community-built except the Fokker Dr.I, which is Parsoft's (c) 1998 original with community
  updates. FS-WWI runs on SDOE's engine (same OPSim.dll).
- **Never** use Parsoft / Activision content: the 10 stock types, the Parsoft Fokker, models "based on"
  them, and the engine binaries.
- Community models credit their authors but almost none state terms, and most authors cannot be reached.
  Crediting alone does not give permission to redistribute. So:
  1. **The sim never ships SDOE art.** It ships an importer that converts community aircraft from the
     player's own SDOE / FS-WWI install or from community add-on archives the player downloads, the way
     open-source engine remakes (OpenMW, OpenRCT2) need the player's own game files. Only our code ships.
  2. **Bundled default aircraft** come from licence-clear sources: FlightGear's GPL 3D models, or new art.
  3. Any author who can be found and agrees can have a model bundled, credited; a credits screen lists
     every imported model's readme credits; take down anything on an author's request.
  (A licensing summary, not legal advice.)

### WW2SIM-6 SDOE model importer (OpenPlane .sm -> glTF)
- Read Parsoft's OpenPlane spec end to end; extend ~/ww2sim_re/scripts/par.py into a reader for .sm
  geometry, parts, LODs, DOFs, textures (TIFF / SGI RGB / INTA) and the damage / part properties.
- Convert to glTF plus a part / damage-property sidecar; refuse anything matching the Parsoft stock list.
- Test on 3 community fighters (WWII) and 1 WWI aircraft, side by side with screenshots from SDOE.
- Sprint 1 (2026-10-29): the .sm chunk format decoded (no public description found) and a first converter,
  geometry and part names only: the Hurricane Mk I exports with the right span and length (40 ft, about
  31 ft). Next: textures, the cockpit file, the provenance check, three more aircraft.
- Sprint 2 (2026-10-29): the Milestone 1 pair extracted and converted: the Bf 109G-6 is clean (32 ft span,
  29 ft); the P-51B's geometry is fine but one wing is placed about 5.5 ft too far out (a placement rule
  still to decode). Shadow planes, hit boxes and marker parts are left out of the clean export.
- PO idea (2026-10-29): use the P-51B art for a P-51D too, with the D's engine ("The two aircraft look
  about the same"). Worth doing as a stand-in until a D model exists; what differs: bubble canopy and
  cut-down rear fuselage, dorsal fillet, six guns vs four, the V-1650-7's altitude ratings, weight. The
  flight model can be the D's from IL-2 1946 test flights (both are flyable there).

- Sprint 3 (2026-10-29): `--strip-stock` leaves out every part that is 50% or more Parsoft geometry and
  lists textures from Parsoft's folders (Bf 109G-6: 5 parts, 5 textures; P-47D: none); chunk 14 decoded
  (moving-part hinges / slides with limits). Placement solved: chunk 11 is each part's offset in its node
  (vertices are stored centred on the part); the Bf 109G-6 exports whole and the P-51B's wings are
  symmetric (the old "5.5 ft wing offset"). With --strip-stock the P-51B loses 37 parts, wings included:
  confirmed stock-derived, not shippable. `--normalise` centres a model on its fuselage and levels it by
  the propeller's spin axis (the P-47D was built 2.5 ft off centre and 17 degrees nose-down; now 40.8 ft
  span, 36 ft long, level). Textures now go into the glTF (one material per texture, embedded PNG; never
  from a Parsoft folder); the Bf 109G-6 renders with its camouflage and crosses in place
  (~/Documents/261029/ww2sim_bf109g6_textured_top.png). Next: redraw the 5 Parsoft-folder textures and
  model the 5 stripped parts for the 109; then WW2SIM-14's first roster.

### WW2SIM-13 Stand-ins for the Parsoft stock aircraft (PO 2026-10-29)
PO: "For WW2SIM do this for all the off-limits Parasoft stock aircraft - substitute a similar aircraft,
use the il2fb flight data for the actual aircraft. Only aviation experts will notice the difference."
Then: "but parsoft made these components available to the mod community via openplane".
- **Licence (SDOE's own help/sla.html, Activision):** the program's utilities and assets may be used to make
  "New Game Materials" for personal use, free of charge, and "New Game Materials may be created only if such
  New Game Materials can be used exclusively in combination with the retail version of the Program. New Game
  Materials may not be designed to be used as a stand-alone product." OpenPlane gave modders Parsoft's parts
  for SDOE add-ons, not for a separate game; the PO decides how WW2SIM treats them (options below).
- **Provenance check (2026-10-29, ~/ww2sim_re/scripts/sm_provenance.py, table in
  ~/Documents/261029/sdoe_model_provenance.tsv):** share of each model's vertices identical to a stock model.
  Unrelated models share 0-4%. Of 199 SDOE models: 84 clean (73 community aircraft + 9 Parsoft stock + 2 non-aircraft), 40 sharing only Parsoft's kit parts (cockpit
  panels, gun sights, canopy glass, wheels, propellers, turrets) or coarse proxies (low-detail / airfoil
  sections), 75 built on a stock airframe (all community Spitfires, Mosquitos, Ju 88s, the P-51B / C and
  A-36, P-38L, B-17F (= the stock mesh), B-24, Tempest, Fw 190A-3 / A-8, Beaufighters ...). The P-51B of
  Milestone 1 uses the stock P-51D's wings; the Bf 109G-6 is the modeller's own airframe (kit parts only).
- **Stand-ins** (art from a model whose airframe is the modeller's own; kit parts and proxies replaced by
  ours; flight model = the real type's, from IL-2 1946 test flights where IL-2 flies it):

| Stock type | Stand-in art | IL-2 1946 flight data |
|---|---|---|
| P-51D | no clean P-51 in SDOE: FlightGear's GPL P-51D model, or the P-51B art if the PO accepts the licence risk | P-51D-20NA, P-51D-5NT |
| Fw 190A | Fw 190A-5/U13 or A-6/R15 (detailed, only proxies shared) | Fw 190A-5 / A-6 / A-8 |
| Ju 88A-4 | He 111H-2 (clean; a different shape) or a FlightGear Ju 88 if one exists | Ju 88A-4 |
| Me 262A | Sukhoi Su-9 (1946, a Me 262 look-alike; clean) or Meteor F.4 | Me 262A-1a |
| Mosquito | no clean Mosquito in SDOE: FlightGear's GPL Mosquito, else Blenheim IV / Beaufort | Mosquito FB VI |
| P-38J | P-61 (twin-boom, larger) or a FlightGear P-38 | P-38J |
| Spitfire | no clean Spitfire in SDOE: FlightGear's GPL Spitfires, else Hurricane Mk II | Spitfire variants |
| Typhoon | Hurricane Mk XII / Mk II (clean airframes) | none (IL-2 flies the Tempest only): historical trials |
| Lancaster | Lancaster B Mk II (community, 38k vertices, proxies shared) | none: historical trials |
| B-17G | no clean B-17 in SDOE: FlightGear's GPL B-17 | none: historical trials |
| V-1 | our own simple model (a target, not flown) | none |

- **Textures of the 73 clean community aircraft (2026-10-29, scripts/tex_provenance.py, table
  ~/Documents/261029/sdoe_clean_models_textures_il2.tsv):** 28 use only their own textures; 30 use or copy
  small Parsoft kit textures (gauges, spars, sidewalls, gun barrels; 64 px and under) that are easily
  redrawn; 15 map large Parsoft images (stock skins or main panels: Do 335 and Meteors on Me262.tif,
  Il-2 and MiG-3 on P51D.TIF, P-61 on P-38J's) and need new skins. IL-2 1946 (guides 4.07-4.12):
  34 exact type flyable, 15 a close variant, 24 none or AI only.
- **Free models (2026-10-29, ~/Documents/261029/ww2sim_free_models_survey.md):** FlightGear FGAddon (GPLv2+)
  has 36 of the 43 main IL-2 types surveyed (none: Ki-43, LaGG-3, Pe-2, A-20, Typhoon, SBD, G4M);
  Sketchfab CC-BY / CC0 fills Ki-43, LaGG-3, SBD, G4M. helijah = Baranger's CC-BY copies of his FlightGear
  models. Excluded: game rips (69 hits) and manilov.ap's IL-2-like set. Gaps everywhere: Pe-2, A-20, Typhoon.
- **Options for the PO:** (a) as the licence reads: distribute only clean art; stock and stock-derived art
  only through the importer reading the player's own SDOE installation (nothing of Parsoft's shipped);
  (b) ask the rights holder (Activision, now part of Microsoft) for permission; (c) treat OpenPlane parts as
  free to use (a licence risk). Recommended: (a), with FlightGear's GPL models where SDOE has no clean
  stand-in; it also moves Milestone 1 to Bf 109G-6 vs P-47D (both clean, both flown in IL-2).

### WW2SIM-14 Aircraft roster and asset sources (PO decisions 2026-10-29)
PO: "no commercial release ever"; on the survey of free models: "OK, good enough. Add this to the WW2SIM plans."
- **Licence:** WW2SIM is free and never sold. Its code is GPLv2-or-later (matches FlightGear's aircraft;
  JSBSim is LGPL; MIT Julia packages are compatible). The sgl repo has no licence file yet: add one.
- **Parsoft content:** option (a) of WW2SIM-13. Nothing of Parsoft's ships: not the 10 stock types, not
  stock-derived community models, not Parsoft's kit parts or textures inside otherwise clean models
  (deleted and remodelled / redrawn). The importer may still read a player's own SDOE install.
- **Art sources, in order:**
  1. Clean SDOE community models (WW2SIM-13 provenance + texture checks), Parsoft parts removed, under the
     asset policy (readme credits, a good-faith author search, removal on request).
  2. FlightGear FGAddon models (GPLv2+), kept in their own folder with COPYING / AUTHORS. Eleven folders have
     no licence file of their own (P47, Hurricane, A6M2, Ki-84, yak3, Ju-88, He-111, mosquito, sm79, me163,
     He162): confirm each before use. Detlef Faber's are the most finished; most of Baranger's are alpha.
  3. Sketchfab CC0 / CC-BY / CC-BY-SA (CC-BY-SA only under GPLv3). Never game rips or unsourced sets
     (manilov.ap). helijah's CC-BY copies of Baranger's FlightGear models: confirm with him that helijah is
     him. mgg8's CC0 models are AI-assisted, details approximate.
- **Flight data:** IL-2 1946 test flights (WW2SIM-5 / -8) for the type or a close variant, corrected from
  historical data where the variant differs (P-40F: Merlin; F4U-2 / Bf 110G-4: radar weight and drag;
  Bf 109G-5: pressurised cockpit; Ju 87G-2: D-5 wing). Historical trials only where IL-2 does not fly it
  (B-17, Lancaster, Mosquito bombers, Typhoon).
- **First roster (SDOE models, by wartime production):** Bf 109E-4, G-5; P-47D x2, P-47C; P-40F; F4U-2;
  Pe-2; A6M2 / A6M3 / A6M5; LaG-5 (new skin); Ju 87B-2, Picchiatello, G-2; Bf 110G-2, C-5, G-4 NJ; He 111H-2;
  Blenheim I, IV, Finnish I. Parsoft parts to replace: F4U-2 cockpit, wheels and gear pistons (largest);
  Bf 109G-5 panel, barrels, pod, pylons; LaG-5 small parts + skin; Bf 109E-4 barrels; Bf 110 tail wheel /
  barrels. The rest (P-47s, P-40F, Pe-2, Zeros, Ju 87s, He 111, Blenheims) are clean as they are.
- **Famous types from FlightGear / Sketchfab:** Spitfire IX, P-51D, Bf 109G-14, Fw 190A-8, Hurricane,
  Mosquito FB VI, P-38, F6F, F4F, Il-2, MiG-3, La-5, Yak-3, Ju 88, Me 262, Tempest V, B-25, B-17, Lancaster;
  Ki-43, LaGG-3, SBD, G4M from Sketchfab only. 40 of 43 main IL-2 types covered.
- **Gaps:** Yak-1/7/9 (Yak-3 stands in), Typhoon (Hurricane Mk XII art or the Tempest V), A-20 (new art).
- **Every non-SDOE model needs splitting into SDOE-style parts** (with damaged versions) for WW2SIM-9.
- **Milestone 1 pair** (the P-51B uses Parsoft's wings): P-51D from FlightGear (production status) vs the
  SDOE Bf 109G-6 (own airframe, kit parts replaced): one model through each import path, both flown in IL-2.
  Alternative: P-47D (clean SDOE) vs Bf 109G-6.

### WW2SIM-7 JSBSim flight models + tuning harness
- JSBSim as a library; load FlightGear's P-51D and Bf 109G definitions; collect historical test data
  (speed per altitude, climb, turn, roll rate) with sources.
- Port the IL-2 test pilot to JSBSim (same manoeuvres, same CSV) and report model vs history vs IL-2.

### WW2SIM-8 IL-2 reference flights (fixes to the 2026-10-28 proof of principle)
- Hand back by holding level until the pilot moves the stick (centring the elevator at speed caused a
  stall); scale all gains with airspeed (the recovery hold porpoised at 560 km/h).
- Speed runs: cool the engine first, estimate top speed from an exponential fit, climb rate only once
  the climb speed has settled; WEP runs separately.
- Split S: throttle closed to slow down, hold the bank at 180 deg until past the vertical, g-limited pull
  to level.
- Landing: a ground-start mission to read field height and runway heading, then an air start on a 10 km
  final (DeviceLink gives no position).
- DrawIfNotFocused=1 so the game keeps running while the user types (test whether it does).

### WW2SIM-9 Damage model
- SDOE-style part objects driving JSBSim coefficients; ballistics (calibre, ammunition types,
  penetration) and fuel / oil / coolant / fire systems; pilot wounds.
- Calibrate hit-to-kill against IL-2's event log (per-seat wounds, "damaged by", "shot down by").

### WW2SIM-11 Bake-off: Julia component model against JSBSim plus a damage layer
- The P-51B/D airframe in both, against the same IL-2 test flights (speed per altitude, climb, turn, roll,
  stall), three damage cases (half an aileron gone, a holed outer wing panel, a lost tail tip), and the work to
  add a second aircraft. Decides the architecture (research section 2).

### WW2SIM-12 FlightGear as the image generator
- Our flight model drives FlightGear over its external-FDM network interface: terrain, Advanced Weather clouds
  and other aircraft from FlightGear for the first flying milestone.

### WW2SIM-10 Milestone 1 prototype
- P-51D (FlightGear model) vs Bf 109G-6 (SDOE community model), per WW2SIM-14 (was P-51B vs Bf 109G-6; the
  P-51B's wings are Parsoft's), both flyable in IL-2,
  one map, the flight model chosen in WW2SIM-11, per-part damage (WW2SIM-9), the imported community models
  (WW2SIM-6), a basic AI.
- Proves every pillar together before scaling up.

### Open questions (with the user)
- Engine and renderer: the same stack as Julia Racer, or a different one? (Research: Julia Racer's, after a
  FlightGear-as-image-generator first milestone.)
- Enemy AI (pilot skill, tactics) - a large share of what makes IL-2 work.
- Terrain / scenery (FlightGear's scenery data?) and multiplayer.
