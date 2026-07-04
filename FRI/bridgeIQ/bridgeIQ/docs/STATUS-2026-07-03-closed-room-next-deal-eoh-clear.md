# STATUS — 2026-07-03 — Closed-room "next deal" button + robust end-of-hand clear

Two closed-room / teams-match UX fixes, both in `ui/main_window.py`. Verified
offscreen (`QT_QPA_PLATFORM=offscreen`) by driving the real `MainWindow`.

## 1. "Closed room" button starts the NEXT comparison deal once a deal finishes

**Symptom.** After a deal completed, clicking the in-game **Closed room** button
popped the **Teams Match Score** table instead of dealing a new hand.

**Cause.** `_on_closed_room_button` unconditionally called `_on_view_teams_score()`
whenever a closed-room match was active (`teams_match is not None`). Because the
closed-room match is open-ended (`num_boards = board_num + 100000`) and persists
across deals, every post-deal click hit the score branch.

**Fix.** With a match active, branch on `controller.current_phase`:
- `'finished'` → `_on_next_deal()` — deals the next comparison board: the human
  plays the open room while the four biq bots play the SAME deal in the closed
  room (via `_start_teams_board` → `_begin_parallel_closed_room`). This also
  blanks the finished deal's cards (fresh `set_board`).
- otherwise (mid-deal) → keep the old `_on_view_teams_score()` peek, so an
  in-progress hand is never abandoned by an accidental click.

The score table stays reachable from the end-of-hand dialog's **View other
table** button and **Deal ▸ Teams score**.

**Verified.** On a finished teams deal, one `_on_closed_room_button()` call
advanced the match `current_board 100 → 101`, dealt a fresh 13-card hand (human
seat shown, others hidden), started the closed room on the new deal (bots bid it
out), and popped **no** dialog.

## 2. Cards always cleared when a deal finishes

**Symptom.** After play was over, the last cards could stay on the felt.

**Cause.** In `_show_result`, `table_view.hide_all_hands()` shared a single `try`
block with `show_end_of_hand_view()` (the post-mortem 13-card snapshot + winner
outlines). If that populate step raised, the blank was skipped and the last
cards were stranded.

**Fix.** Split the blank into its own `try`, so `hide_all_hands()` runs
UNCONDITIONALLY once the deal is over, regardless of whether the snapshot
populate above succeeded.

**Note / not reproduced.** `_show_result` was measured to blank correctly in
BOTH the single-player and teams/closed-room paths (all four hand widgets
`isHidden=True` afterward), so a *naturally completed* deal already cleared. The
reported screenshot showed a ~trick-10 (3-cards-each) spread, i.e. a state where
the open room had not fully played out (the parallel closed room finishes first
and posts a score). Fix #1 clears those cards on the next-deal click; fix #2
hardens the completion path against a snapshot-populate exception. If stranded
cards recur on a fully-played deal, capture the exact sequence (declaring vs
defending, claim used, autoplay on/off) to trace that path.

## Files
- `ui/main_window.py` — `_on_closed_room_button`, `_show_result`.
