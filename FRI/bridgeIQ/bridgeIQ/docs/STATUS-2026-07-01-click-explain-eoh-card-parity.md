# STATUS — 2026-07-01 — click-to-explain reasons, end-of-hand clear, card-size parity

Session covered a fresh-install fix, three biq UX features, and a launcher tweak.
All changes verified offscreen (imports, construct, self-play deal, unit tests,
rendered screenshots). Work landed on `main`.

## 1. Fresh-install / branch fix (pre-work)

- `bridgeIQ` failed to launch with `No module named 'numpy'`. Root cause: the
  venv was built with only PyQt6 + colorama, but `backend/engine.py`,
  `models.py`, `ui/dialogs/simulation.py` import numpy. Installed numpy into the
  venv. (The install-script fix — `numpy` added to `create_venv` — already lives
  on `main` via `d5cc92d`; the working checkout was just behind.)
- Brought the local checkout up to date with `origin/main` (merged 166 commits),
  which also supplied the real `ui/dialogs/qplus_simulation.py` (was missing on
  the stale branch).

## 2. End-of-hand: clear ALL cards once play completes

Previously only a **claim** blanked the table; a natural 13-trick finish left a
full four-hand spread that overflowed and got cut off. Now **both** paths clear.

- `ui/main_window.py` `_show_result`: after populating the hands (for the
  post-mortem / F2), always calls `table_view.hide_all_hands()`.
- `ui/table_view.py`: new `hide_all_hands()`; `set_hand_visible()` falls back to
  the end-of-hand 13-card snapshot when `board.hands` is empty (post-13-tricks)
  so **F2 / View ▸ Open All Hands** still reveals the real hands.
- `ui/dialogs/review_dialog.py` `closeEvent`: re-blanks the table on close
  instead of re-spreading it (which reintroduced the overflow).
- Removed the now-redundant `_eoh_clear_all_hands` flag (4 sites).

## 3. Click-to-explain: biq's ACTUAL per-card reasons

The click-to-explain feature already existed for **bids** (shows biq's stored
`Bid.explanation`) but was **off by default** (`explain_actions_enabled`) — now
default **ON** (`backend/config.py`). For **cards** it previously only
reconstructed a reason from public info because the engines discarded their
reasoning. Now biq captures and stores its real per-card rationale:

- `backend/nopeek.py`: zero-cost `_why(explain, tag, reason)` sink threaded
  (optional `explain` param) through `decide()` and every policy helper. Each
  branch records its true technique — draw trumps, establish/finesse/cash,
  cover an honour, 2nd-hand-low, 3rd-hand-high, hold-up, signal, ruff/discard,
  alpha-mu search, and the real opening-lead reasons from `LeadDecision`.
  `explain=None` on the hot rollout paths, so card choices are unchanged.
- `backend/engine.py`: `EngineResponse.reason` / `reason_tag`; MC+DDS,
  opening-lead and fallback engines populate them.
- `ui/main_window.py`: worker passes `explain={}`; `_on_engine_card` stores the
  reason in a **board-number-keyed** map (`_biq_reason_store`, self-invalidates
  on deal change); `_on_explain_card` prefers the stored reason.
- `backend/explain.py`: extracted `_reconstruct_card`; `explain_card` shows
  biq's real reason as the headline and, for the **search** engines, also
  appends the public technique classification ("In technique terms: …").

Note: with alpha-mu active (default) most in-play cards are genuinely chosen by
search, so their headline is the alpha-mu rationale — that's the truth — now
enriched with the technique classification. See `BACKLOG.md` for surfacing
reasons in the Q-NET server play loop too.

## 4. Card-size parity in the cardplay view

Trick-area cards rendered at ~96×135 (a smaller design size, scale-floored)
while hand cards are 160×224. Rewrote `TrickAreaWidget._relayout`
(`ui/table_view.py`) so played cards render at the **hand-card size** as a
centred, overlapping cross (the traditional bridge look), with a z-order that
keeps every card's rank/suit index visible. Verified 160×224 at 1280×720,
1600×900, and ~1848-wide windows. Removed the dead `_scale()` /
`MAX_SCALE` / unused `DESIGN_*` constants.

## 5. Launcher — MON

- `filesForLauncher/launcherScripts.csv`: made `pokerIQ/run.sh` the **first**
  MON choice (was 2nd, after `pokerth.sh`). Its menu description
  "poker with analysis" already came from `script_display_name` in
  `launcher/lib/common.sh`. Only the MON column moved; other days untouched.
</content>
