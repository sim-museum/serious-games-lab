# Session status — 2026-06-25 (cont.) — end-of-hand cleanup, claim, manual Claude

Branch **24.04**, pushed to `origin/24.04` (`1b657c5` … `3d37d1a`). Follows
`STATUS-2026-06-25-practice-decks-playable.md`; all from live testing the
practice decks.

## 1. End-of-hand hand visibility (`1b657c5`)

`_show_result` ended with an unconditional "Show all hands at end" loop
(`for seat in Seat: set_hand_visible(seat, True)`) that re-revealed all four
hands — which silently **overrode** the earlier declarer+dummy-only
post-mortem fix (`bcdf26f`) and pushed the two defender hands off the screen
edges. Removed it. Hand visibility at end of play is now decided in one
place:

- `show_end_of_hand_view()` reveals only the **declaring side** (declarer +
  dummy), which were already on screen during play;
- the defenders are populated face-up but left hidden — **View ▸ Open All
  Hands (F2)** reveals them on demand.

This is why the previous "don't show E/W" fix appeared not to work: the
loop undid it every time.

## 2. Claim clears the table (`1b657c5`, `af8a667`)

A claim ends play with cards still in hand; showing the unplayed cards (and
four full hands) overflows the table. Both claim paths now clear the table:

- manual **Claim** button (`_on_claim`) and the DDS auto-claim
  "make the rest" path (`_maybe_offer_claim`) set a one-shot
  `_eoh_clear_all_hands` flag;
- `_show_result` hides every hand when the flag is set (reset per deal in
  `_present_fresh_board`).

Hands stay populated face-up, so **F2** still shows them. Verified end to
end (real `_show_result` + dialog): after a claim the table is empty; F2
reveals all four; a normal play-to-completion shows declarer + dummy only.

## 3. Claude analysis is manual only (`3d37d1a`)

`_on_next_deal` auto-called `_maybe_run_pending_claude()` when a deal
finished, popping the "Claude is analyzing the hand…" dialog automatically
and blocking the next deal. Removed that auto-call. Claude now runs **only**
on explicit request:

- the end-of-hand dialog's **"Claude analysis"** button, or
- **Extras ▸ Hand Log (Claude Analysis)**.

`_show_result` still stages the pending-hand context so those manual entry
points have something to analyse. Verified: finishing a deal + Next deal
invokes Claude 0 times.

## Note on a stale running instance

Several of these reports recurred because the **running biq process** had
code from before the relevant commit (e.g. the "show all hands" loop in
`bcdf26f` was only removed in `1b657c5`). The source behaviour is verified
correct each time via the offscreen-Qt harness; **fully relaunch biq**
(`./run.sh`) after pulling to pick up changes.

## Still open (from prior status)

- Closed room on a fixed-contract book deal is meaningless (now disabled on
  book deals, but the comparison itself has no meaning for teaching hands).
- Repeat Deal doesn't re-show the book-note panel (tied to the deal-queue
  path).
- Autoplay/closed-room edge interactions only reasoned about headlessly; the
  play loop needs the real event loop to fully verify.
- Remaining source books (Everything Bridge / Joy of Bridge / Sheinwold)
  need a per-figure visual-scan pipeline.
