# biq-vs-Q-Plus harness — status 2026-09-25 (end of day)

Continues `HARNESS_STATUS_2026-09-23.md` (read it first: port 1100, seat rules,
ghost Q-NET slots, leave_game fix).

## Results so far (files in tools/runs/results/)

| run | signalling | deck | boards scored | net IMP | per board |
|---|---|---|---|---|---|
| 1 | on  | RANDOM.BDE (seed 1)          | 14 (scoring broke at deal 17) | -45  | -3.21 |
| 2 | off | Q-Plus's own random deals    | 63 | -204 | -3.24 |
| 3 | on  | RUN2.BDE = run 2's deals     | 61 | -176 | -2.89 |

**Paired A/B, runs 2 vs 3, 61 common boards, identical auctions on all 61:**
signalling ON is *better* by 25 IMP: +11 IMP / 11 tricks on the 27 boards biq
defended (Q-Plus declarers took 270 vs 281 tricks); +14 on declared boards,
where signalling cannot act = the run-to-run noise floor. ON better on 19
boards, worse on 10. **Conclusion: signalling is not the leak; keep it ON.**
Bidding is about 2/3 of the gross loss in both runs (OVERBID, UNDER-COMPETE,
MISSED GAME/SLAM). Tools: `qss_to_bde.py` (replay a run's deals as a deck),
`whole_system_analyze.py`.

Preference: File ▸ Preferences ▸ **Carding** tab ▸ "Play defensive signals"
(moved from Mouse & Input). Harness clients: `BIQ_SIGNALLING=0/1` in the panel
process environment (unset = ON).

## Fixed today (UNCOMMITTED: tools/, backend/bidding_systems.py, ui/dialogs/preferences.py, FRI/qplus.sh)

- **Menus by keyboard** (`qplus_geom.menu_pick`): mouse clicks on the Q-Plus
  menu bar never open a menu here; Alt+mnemonic does. Network=n then "s";
  View=v then "s"; Configuration=c then Return (Players) or "b" (Bidding
  system); Deal=d then "m". Wired into the panel (server start, View scoring
  table, Players East/South reset), `qplus_button_loop.py` (transition,
  systems dialog) and `qplus_mixed_corpus.py`. Labels/mnemonics come from
  `WP/.../LIB/STRINGS/QP-S-E.INP`.
- **Keys need REAL focus**: keystrokes go to the compositor-focused window and
  xdotool cannot move that focus (windowactivate, synthetic click and
  --window keys all fail). `qplus_geom.qplus_has_focus()` detects it — valid
  only because nothing calls windowactivate any more — and
  `wait_for_qplus_focus` waits up to 8 s while the panel hints "click into
  Q-Plus". Unattended runs are unaffected; hand-stepping requires a click into
  Q-Plus before each menu step. `_keys_to_qplus` and the splash dismiss are
  gated the same way.
- **Wine virtual desktop** for the harness (`qplus_vdesktop.sh`; turned on by
  `qplus_dual_instance.sh server`, default 1853x1011 = the calibrated client
  size; `QPLUS_VDESKTOP=0` disables; `FRI/qplus.sh` clears it for hand play).
  Reason: Wine never learns compositor window moves and placed menus/dialogs
  at the window's OLD position (other monitor), so dialog clicks missed.
  Inside the desktop placement is Wine's own. Verified: bidding-system dialog
  opened and a click on its captured Close closed it. Q-Plus must be
  MAXIMISED inside the desktop; the desktop landed at 67,69 on the left monitor.
- Recaptured with the server dialog open inside the desktop: start [374,385],
  stop [566,379], bridge_min [620,167]. Old files: `~/.qplus_*.json.pre-maximized.bak`.
- `qss_to_bde.py` (new). `biq_qnet_client.py` skips the partner-signal grader
  when signalling is off. Panel: idle backstop 45 s; step 4 fails/retries on
  no join. `tools/biq-panel` now also starts `tools/xtest_keepalive.sh`
  (see blocker — unproven, disable if in doubt).

## BLOCKER at quitting time: pointer emulation dead, keyboard OK

From about 03:40, synthetic POINTER input stopped reaching the screen:
xdotool mousemove/click change X's idea of the pointer but the real pointer
stays put and `xev` sees no ButtonPress, while `xdotool key` still reaches
windows. Ending the sharing session (orange top-bar icon) and re-approving the
"remote desktop" consent created new input sessions (journal: `[xwayland ei]`
at 03:44:03 and 03:48:36) but the pointer stayed dead. Releasing all buttons
and modifiers and stopping the keepalive changed nothing. This morning, right
after a fresh login and one approval, pointer AND keyboard worked and drove
runs 2 and 3 (about two hours of clicks). Things done in between that may
have contributed: `xdotool windowmove --sync` (hangs under Wayland),
split mousedown/mouseup clicks, `mousemove_relative 0 0` keepalive.

**Next session, in this order**
1. Log in fresh. Run the probe: `xev -geometry 300x300+1200+300 -event button &`
   then xdotool mousemove/click into it → must print ButtonPress (approve the
   consent dialog once when it appears).
2. `tools/biq-panel` (panel), Step 1 → Q-Plus in its virtual desktop; maximise
   it inside; check `qplus_geom` delta is (0,0).
3. Verify step 2 end to end: keyboard Network ▸ Start bridge server, then the
   click on the recaptured Start → `ss -tln` shows :1100.
4. Verify the Players East=Computer sequence and the export path (Match End
   button → Save and send → OK).
5. Then the unattended loop: `tools/qplus_loop_sessions.sh N 64 random`
   (convention permutation; nothing may steal focus during a run).
6. Commit everything.

## 2026-09-26 — Q-Plus re-dealt a board mid-run (FRESH64G hybrid, board 24)
Board 24 finished and scored; during board 25's auction (N p, E p, S p, then
Q-Plus West silent ~45 s) Q-Plus dealt board 24 AGAIN. South's board-25 pass
arrived late inside the replayed board 24, so N saw "1S passed out" and S never
saw the auction end; S crashed on the opening lead (trick_leader None) and the
match hung waiting for South's card. First occurrence in all archived logs;
trigger unknown.
Fixes: biq_qnet_client ignores calls after its auction ended, recovers the
contract when play starts with an unfinished auction (pad passes), and trusts
Q-Plus's opening leader for the declarer. biq_match follows Q-Plus board
numbers ("*** Q-Plus RE-DEALT board N") so a replay doesn't count as a deal.
Such a run is spoiled for paired comparison: restart it.
