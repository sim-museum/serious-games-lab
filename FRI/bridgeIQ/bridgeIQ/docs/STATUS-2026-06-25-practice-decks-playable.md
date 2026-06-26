# Session status — 2026-06-25 (practice decks: complete + playable in-app)

Branch **24.04**, all pushed to `origin/24.04` (commits `79f789d` … `58ef781`).

This session finished the practice-deck content and made the decks fully
playable inside biq — load a book deal, play straight from its contract,
read the book's line, claim the rest, and step through the book.

## 1. Bridge Basics (Klinger) deck — all 36 play hands (`79f789d`)

Extended `DATA/PRACTICE/bridge_basics.bdl` from 5 → **all 36** numbered
play hands. Cards are vision-transcribed from the book's four single-seat
grid pages (pg179–182), kept on the compass exactly as the book labels
them. Each deal validated two ways: biq's own `BDLReader`
(4 hands × 13 cards, 52 unique) **and** an independent leader→declarer
consistency check (the seat holding the stated opening-lead card is the
leader; its RHO is declarer in the chapter contract) — 0 mismatches.

- Fixed a latent seat-rotation in the earlier 5-deal cut that mislabelled
  the vulnerable pair on non-`Nil` deals. Hand 5 (previously dropped) is
  consistent under the correct labels and is now included.
- Self-contained generator committed: `tools/build_practice_klinger.py`
  (cards, metadata, cleaned book commentary inlined — no EPUB needed)
  reproduces the exact validated `.bdl`.
- Deck total: **54 deals** across 3 books (Taste of Bridge 6, Bridge for
  Dummies 12, Bridge Basics 36). README updated.
- The other source books (Everything Bridge / Joy of Bridge / Sheinwold)
  are NOT the clean grid-page case — documented in the README as needing a
  per-figure visual scan.

## 2. Match Control mirrors Q-Plus + plays deal-file contracts (`5a2c785`)

Reworked the Match Control dialog to mirror Q-Plus Bridge
(`MANUAL/ENG/BRIDGE.HLQ .match-control-w`): Deal Source (Deal number |
Deal file | Score table | User entered), Deal number, File
(Pair/Team tournament file · Score table · Deal file + selected path/index
+ Deal filter), Scoring (Rubber | Team IMP | Pair MP + Keep scoring table),
Comparison (Closed room | Results of file | None or later + # boards), and
Ok / Cancel / Help — with the same top-to-bottom dependencies. Deal number
stays biq's own single-number scheme (as requested). `get_settings()` is
backward-compatible plus new axes.

**Play-from-contract:** when a loaded deal already carries a contract +
vulnerability (the practice decks), biq skips the auction and plays from
that contract — new `_maybe_play_from_preset_contract()` hook in
`_present_fresh_board`, gated to fire only for a board with a usable
contract and no real multi-call auction to replay. Also fixed a latent
crash in `set_contract_direct()` (used `doubled=`/`redoubled=` kwargs; `Bid`
takes `is_double=`/`is_redouble=`).

## 3. Play-screen behaviour for the practice decks

- **Human declarer plays dummy + in-game toolbar** (`118a1cf`):
  `set_contract_direct` now sets `human_controls_declarer` like
  `_setup_play`, and `_present_fresh_board` switches the toolbar to its
  in-game mode (Next card …) — deals started from Match Control weren't
  doing either.
- **Sequential deal numbering** (`7939e41`): book hand numbers restart per
  chapter ("Practice Hand #1" recurs), which made the deal counter regress;
  queued deals are now numbered 1, 2, 3, … so Next deal visibly advances.
- **Book commentary during play** (`a91fcd5`): the deal's `Commentary`
  (Lead / Correct play / Wrong play) shows in a read-only "Book note" panel
  on the right; carried onto the board (`to_board_state()` drops it) and
  updated/cleared per deal.
- **Movable result panel** (`f865cbd`): the "playing finished" summary is a
  real movable top-level window (title bar) instead of an embedded overlay,
  so it can be dragged off the cards.
- **Formatting** (`17e2629`): book-note panel given a 252-px floor (it was
  collapsing to a few px and wrapping one letter per line — which also
  threw the E/W seat labels off); seat labels widened 140 → 180 px so
  "S: Declarer (you)" no longer clips.
- **End-of-hand shows only declarer + dummy** (`bcdf26f`): the post-mortem
  no longer reveals the defenders' hands (they ran off-screen). E/W are
  populated face-up but hidden; View ▸ Open All Hands (F2) reveals them.

## 4. Flow fixes (`d985123`, `0d4117a`)

- **Claim** is enabled between tricks (phase `waiting_next`, not just
  `play`) in both the button-state logic and `_on_claim`; declarer can
  claim the rest and the hand finalises/scores.
- **Deal-file queue is authoritative for "Next deal"** in both
  `_on_new_deal` and `_on_next_deal`: once a practice file is loaded, Next
  deal advances through the book even if the user pressed Closed room
  (which starts a teams match). Previously the teams branch ran first,
  dealt a random board, left the book note stale, and cycled back to deal
  1. Queue branch refactored into `_play_next_queued_deal()`.
- **Autoplay** is a per-deal choice (cleared at the start of each deal),
  is stoppable mid-hand (clicking it again hands control back at the next
  declarer/dummy card), and can be turned on from the between-tricks pause.
- **Closed room** is disabled for book hands (identified by their
  commentary) — the contract is fixed, so a 4-bot re-bid just muddies the
  score sheet; it stays available for ordinary deals and tournament files.

## 5. Repeat Deal crash fixed (`58ef781`)

Deal ▸ Repeat Deal → "start with cardplay" crashed
(`Bid.__init__() got an unexpected keyword argument 'doubled'`). It
hand-built the contract bid with the wrong kwargs; replaced with
`set_contract_direct(board.contract)` (which builds the auction correctly).
Tree-wide grep confirms no other `Bid(doubled=…)` remains.

## Infra note

The repo's `pre-push` hook (refuses any tree containing
`FRI/bridgeIQ/bridgeIQ/tools/`) was removed this session at the user's
request, so `git push` works without `--no-verify`. The dev branch 24.04
already carried `tools/` on the remote.

## Known follow-ups (not done)

- **Closed room on a practice deal** still scores oddly if reached by other
  paths (it re-bids a fixed-contract hand); now disabled on book deals, but
  the underlying comparison is meaningless for teaching hands.
- **Repeat Deal** doesn't re-show the book-note panel (it's tied to the
  deal-queue path), so the note reflects the current deal rather than the
  repeated one.
- **Autoplay-stuck / closed-room edge interactions** could only be reasoned
  about headlessly; the play loop needs the real event loop to fully verify.
- Remaining source books (Everything Bridge / Joy of Bridge / Sheinwold)
  need a per-figure visual-scan pipeline (README documents the blockers).
