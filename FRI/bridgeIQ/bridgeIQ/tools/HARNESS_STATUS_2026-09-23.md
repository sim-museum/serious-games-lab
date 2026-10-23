# biq-vs-Q-Plus harness — status 2026-09-23

Goal of the session: A/B the new **"Play defensive signals" preference** (biq
signalling ON vs OFF) by running biq vs Q-Plus 17.1 on the same 64-deal deck,
then permute bidding conventions with the unattended loop.

## Where things stand

- **Run 1 (signalling ON) — done, partial.** `tools/runs/results/run1_signalling_on.qss`
  (copy of `WP/.../LOCAL-MATCHES/M2026-09-23-B.qss`). Only **14 of 61 boards
  scored** (deals 4–17): Q-Plus stopped filling the closed room after deal 17.
  On those 14: **−45 IMP (−3.21/bd)**; buckets DEFENSE −27 (5 bds), CARDPLAY −8
  (3), MISSED GAME −6, UNDER-COMPETE −4, won/push 3. Defence = 60 % of the loss.
- **Run 2 (signalling OFF) — NOT run.** Blocked (see below). Panel is launched
  with `BIQ_SIGNALLING=0` in its environment; both biq clients inherit it
  (verified via /proc/<pid>/environ).
- **Loop / convention permutation — not started** (needs the same click rig).

## BLOCKER (as of 08:00): synthetic X input no longer reaches ANY X11 window

Every harness click goes through `xdotool` (XTest) into Xwayland. Run 1 was
driven this way for 61 boards. Since then **no XTest click lands** — proven with
a plain `xev` window: `xdotool mousemove/click` into it produces **no
ButtonPress**, with or without `windowactivate`, and `--window` (send-event)
mode is ignored too. Q-Plus focus, monitor placement, calibration offsets and
modifier state were all ruled out one by one (see log below). GNOME journal
shows `gnome-shell: [xwayland ei] Unhandled event EI_EVENT_SYNC` at 23:01,
23:56 and 00:11 and nothing after → suspicion: mutter's Xwayland **libei/XTest
bridge died** during the session (Xwayland runs `-rootless` under mutter with
XTest emulated through EI). Things to try, in order:
1. Log out / log back in (recreates Xwayland + its EI session). Then
   `xev` test again: `xdotool mousemove <in xev> click 1` must print ButtonPress.
2. If XTest stays dead on this GNOME: switch the rig to an X11 session
   (GDM → "GNOME on Xorg") — Wine, xdotool and the calibration all behave
   better there (no frame/client offset games, no cross-monitor remap).
3. Fallback: `ydotool` (uinput) instead of xdotool — needs `ydotoold` + input
   group; would replace `_click_xy`/`_click_at`/`click_at` (3 call sites, see
   `tools/qplus_geom.py` for the single shift/activate choke point).

## What was fixed today (all UNCOMMITTED in the tree, except the first item)

Committed on main (fd85220b): the signalling switch itself
(`backend/signals.py set_enabled`, nopeek gating, config + Preferences
checkbox, `test_signalling_switch.py`), loop driver `--nopeek` default.

Uncommitted, in `tools/`:
- `qplus_dual_instance.sh`: server on `/usr/bin/wine32` (Ubuntu wine 10 =
  wow64-only `wine`, refuses the 32-bit prefix); no `WINEARCH` export.
- `qplus_control_panel.py`: wine32 + off-PATH wineserver; keystrokes go to
  the Q-Plus window only (bare Return/Escape re-pressed ▶ Start and killed the
  panel); excepthook (no silent abort); startup no longer kills a running
  Q-Plus; **follows the port Q-Plus actually listens on** (this install
  auto-starts on **1100**, docs say 5555; `QPLUS_SERVER_PORT` pins); step 4
  FAILS/retries when no biq joins (was "done" after 20 s → 'biq not running'
  at step 8); idle backstop default 10 s → **45 s** (a 10 s backstop clicked
  into a biq think in deal 17 = the run-1 scoring stop); Calibration manager
  980 px wide + wrapped labels (Capture buttons were off-screen); step 2
  sends Escape first (modal bidding box eats menu clicks).
- `biq_qnet_client.py`: creates `tools/runs/` for its log; **sends
  `leave_game` + closes the socket on every exit** (SIGTERM handler) — a
  client that just dies leaves a GHOST seat and Q-NET stops answering until
  the server is restarted (cost us 4 restarts). Verified: seat freed, Q-NET
  keeps answering. NB raw "probe" connections that never join ALSO burn a
  Q-NET slot permanently — do not probe the server with throwaway sockets.
- `backend/bidding_systems.py`: `system_name_for_qplus_code()` (A-SAYC-I,
  A-2-1-A, B-ACL-S, F-FRA-M, P-P90M-A → biq names); `--auto-system` crashed
  on import without it.
- `qplus_loop_sessions.sh`: repo-relative prefix (was another user's home),
  `--nopeek`, `BIQ_SIGNALLING` passthrough, port detection, wineserver path,
  per-session `.cfg` record.
- `qplus_geom.py` (new) + hooks in panel / `qplus_button_loop.py` /
  `qplus_mixed_corpus.py`: window-relative clicks. Captures were made with
  Q-Plus's CLIENT window at **(67, 69)** (`~/.qplus_cal_origin.json`);
  clicks/captures shift by (xwininfo absolute client pos − origin);
  `activate_qplus()` focuses the client window (owned by QBRIDGE.EXE, not the
  mutter frame) before each click. Note: on the RIGHT monitor XTest clicks
  landed on the wrong control even when the pointer read back correctly —
  keep Q-Plus on the LEFT monitor.
- `biq-panel`: repo-relative path.

## Q-Plus facts learned (this install, wine 10 / wine32, Ubuntu)

- Q-NET works under wine 10 (handshake verified) — the "needs wine 9" note is
  obsolete. Server auto-starts on port 1100; the dialog may show 5555.
- Seats: `join` to Human/local seat → `player_refused`. Rig: Players
  N/S = Extern, E/W = Computer, **Local radio (bridge-server dialog) = East**.
  Extern seats revert to Human while the server is stopped → set seats AFTER
  the server is up (step 2), before step 4.
- Q-NET client slots are finite and a closed socket without `leave_game`
  never frees one (CLOSE-WAIT on the server side).
- Match Control → new match spawns a helper `QBRIDGE.EXE -c 6 -h <hwnd>`
  ("Q Closed Room" window) that plays the closed room. When the closed room
  isn't filled, RE[1]=0 / NC 0 0 in the .qss and the board doesn't score.
- Match settings persist in `CONFIG/B-MATCH.CFB` (written on change).
- Button bar changes after Match Control ("Closed Room…" → "First deal /
  Match control / Help"): recapture **closed_room** on "First deal".
- The bar's "Network" capture at (361,79) looks like it sits on "Extras"
  (Network ≈ x 290): recapture network_menu / net_start_item / start_item /
  stop_item / bridge_min with the dialog open before any unattended run.

## Calibration files (home dir)
`.qplus_server_buttons.json`, `.qplus_button_loop.json`,
`.qplus_mixed_corpus.json`, `.qplus_transition.json`, `.qplus_cal_origin.json`.
All captured with Q-Plus client window at (67,69) on the left monitor.

## Next steps
1. Restore XTest (log out/in, or Xorg session); verify with `xev`.
2. Recapture: closed_room (on "First deal"), the 5 bridge-server points.
3. Run 2: Q-Plus at (67,69), server started, seats set, Match Control new
   match on RANDOM.BDE, panel `BIQ_SIGNALLING=0` → Reset → Step 1–8.
   Watch `tools/runs/biq_N.log` report_score count keeps pace with deals.
4. Export (View ▸ Scoring Table ▸ Save and send ▸ OK), then
   `python3 tools/whole_system_analyze.py run1.qss run2.qss`.
5. Then `tools/qplus_loop_sessions.sh N 64 random` for convention permutation
   (needs a saved Q-Plus config + calibrations; kills/relaunches wine per session).
6. Commit the uncommitted tools/ changes (`git add tools/ backend/bidding_systems.py`).
