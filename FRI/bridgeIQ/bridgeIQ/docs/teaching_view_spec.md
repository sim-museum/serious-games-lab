# Instrumented (teaching / analysis) cardplay view

An alternative to the normal table (`ui/table_view.py`), toggled by the
**Instrumented** toolbar button. Implemented in `ui/teaching_view.py`; wired
into `ui/main_window.py` via a `QStackedWidget` (page 0 = normal table, page 1
= instrumented) and refreshed on a 500 ms timer while it is showing.

Layout matches `Documents/260619/biq_screen.pdf`: a four-hand cross. Each hand
is a **4-row (♠♥♦♣) × 2-column (Known | Other)** grid; the four corners hold
analysis panels; the centre is the current trick.

## What the books say a player should track (sources)

Mined from `BridgeSqueezes.pdf`, Reese *Begin Bridge* (Parts IV–VII),
`SAYC_bridge_convention.pdf` (carding), `BBA - Bridge Rules/Hand Evaluation`,
`PrecisionBridge.pdf`. The view targets BOTH a trainee and a strong player via a
Beginner / Intermediate / Expert detail selector.

Core tracking items: count winners (NT) / losers (suit, LTC); "draw trumps?";
the **count** (each seat's remaining length per suit); opponents' shown
shape & HCP from the auction; trump control (is the master trump out?);
**entries** to each hand; which suit to establish & rounds needed; stoppers /
hold-up (Rule of 7); finesse vs drop (8-ever-9-never); squeeze ingredients
(Love's **BLUE**: Both threats one defender, rectify the count, threat in the
Upper hand, Entry); and defensive signals (attitude / count / suit-preference).

## Where each thing lives

- **KNOWN column** — cards PROVEN in that hand now: exact cards for a face-up
  hand (own + dummy + Show All); for a hidden hand only cards forced there (sole
  seat not shown out of the suit). Computed in `known_layout()`.
- **OTHER column** — inferred length range (auction constraints ∩ play),
  `void`, exact count for visible hands (`suit_length_text()`), PLUS the latest
  defensive-signal chip biq read in that suit and a "where's the missing honour"
  hint (`_other_for`).
- **Highlights on Known cards** — vivid, high-contrast markers (no superscripts):
  current master/boss (gold fill), top-run sure winners (green box), **losers**
  (red box, declaring side, `suit_loser_ranks`), cards **placed by deduction**
  (dashed outline), trump suit (row tint), and inverse-video role chips —
  **E** entry (`top_entry_rank`), **S** stopper (NT, `stopper_rank`), **KO**
  knock-out, **→** card that reaches partner. A legend row explains them.
  `_render_known()`.
- **Corner panels** — Contract/Tricks; Plan (top tricks, LTC, trump-control
  warning, entries, **danger hand + knock-out entry**); Count/Honours (Expert:
  full per-seat count table + missing honour placement); Coaching/Signals
  (rule-based hint + carding note + BLUE).
- **Danger hand (NT)** — `danger_info` flags the defender who can run the threat
  suit (the opening-lead suit; longer holding, ties → opening leader) with a
  `⚠ danger` tag in the hand title and a red Plan line ("keep off lead, don't
  finesse into it"); their proven side-suit entry (Ace, or King if face-up) gets
  a red `⊗` knock-out badge on the card and a Plan line ("knock out X before the
  suit sets up"). Kantar's danger-hand + Sheinwold's knock-out-the-entry.
  Suit contracts have none (you ruff). `test_danger_hand_and_knockout_entry`.
- **Centre** — the current trick by seat + who is to play.

## System-dependent behaviour

The two pairs can play different systems. The view reads
`main_window._active_bidding_system('NS' | 'EW')` and runs
`auction_inference.infer_constraints` once per side, taking each seat's
constraints from its own side's pass — so a Precision 1♣ (16+) tightens E/W
inferences differently from a SAYC 1NT. The header shows both systems. Carding
(standard vs upside-down attitude/count, 4th-best vs 3rd/5th leads) is currently
shown as a standard-assumption note.

## Grounding — books actually read (rumi3_library + folder)

A full pass was done over the `Documents/260619/rumi3_library` library (text-layer
PDFs and EPUBs extracted; the two image-only scans read page-by-page as images):
Sheinwold *5 Weeks to Winning Bridge*, Reese *Begin Bridge*, Kantar *Bridge for
Dummies*, Klinger *Bridge Basics* and *Better Bridge With a Better Memory*,
Grant & Rodwell *The Joy of Bridge*, ACBL *Encyclopedia of Bridge* (carding/leads/
squeezes reference), Mollo *The Hog Takes to Precision*, Bayone *A Taste of
Bridge*, Frey *10 Easy Lessons*, Manley *Everything Bridge* — plus the folder
pamphlets (SAYC, BBA cards, BridgeSqueezes, PrecisionBridge).

Cross-book convergence drove these additions, each citable:
- **The race** (Bayone/Manley/Frey) — declarer-needs vs defence-needs in the
  Contract panel.
- **"Shall I draw trumps? If not, why not?"** (Reese §62) + outstanding-trump
  **break odds** (Klinger break table) in the Plan panel.
- **Unseen-HCP databank** "40 − visible HCP, place the rest from the bidding"
  (Klinger ARCH-C) in the Count panel, with per-pair-system narrowing so a
  Precision overcaller shows a tighter window than a SAYC one (Mollo).
- **Rule of 11** opening-lead read (Sheinwold / ACBL) in the Coaching panel.

## Implemented vs. deferred

Implemented: cross grid + Known/Other, proven-card placement incl. forced-seat
inference and void detection, master/winner/trump highlights, per-pair auction
inference, contract/plan/count/coaching panels, honour placement, LTC, top
tricks, trump-control warning, three detail tiers.

**Live defensive signal reads** — both defenders' attitude/count signals on
played spot-cards. `backend.signal_read.read` selects which completed-trick
plays are genuine free signals (followed suit, didn't win, spot not honour);
`current_trick_reads()` does the same for the in-progress trick so the read is
truly live. Each is interpreted from PUBLIC info — "high vs low" relative to the
suit's still-outstanding cards — as encourage/discourage (attitude) or even/odd
(count), honouring the UDCA switch (`backend.signals.is_udca`). Shown two ways:
a tag under the card in the centre trick, and a "Signals (standard/UDCA)" log in
the Coaching/Signals panel (last 2 reads for Beginner, 6 for Intermediate, all
for Expert). See `signal_reads()` / `current_trick_reads()` / `_interpret()`.

**Per-pair carding config + suit-preference reads** — each partnership (N/S,
E/W) has its own `CardingConfig` {attitude: standard|udca, count: standard|
reverse, discards: attitude|lavinthal}, chosen from presets via two header
selectors; every read is decoded through the SIGNALLER's pair config
(`_carding_for`). Suit-preference (Lavinthal) reads on DISCARDS — which the
engine's `signal_read` skips — are computed in `_interpret_discard` /
`_completed_discard_reads` and gated by the ACBL priority rule (only asserted
when the agreement says so and exactly two candidate suits remain, i.e. a trump
contract; otherwise falls back to an attitude-of-the-thrown-suit read). Tagged
`sp` in the Signals log and under the played card. Covered by
`test_teaching_view.py`.

**Honest-signal flag** — when a signaller's hand is face-up (review / Show All),
each completed-trick follow signal is checked against the real holding via the
engine's `signal_read.mis_signals`, decoded under that pair's convention
(`_dishonest_map` maps the preset onto the engine's udca switch around the call).
The Signals log shows `✗ false (→ <honest card>)` in red for a false-card, and a
green `✓` at Expert for an honest one; `honest` is None (no marker) when the
signaller is hidden. Covered by `test_teaching_view.py::test_honest_signal_flag`.

**Smith echo + trump echo** — two more conventions in `CardingConfig`
(`trump_echo`, `smith`). A count signal in the TRUMP suit is re-read as a trump
echo (`_interpret`: high-low in trumps = odd / 3 — "I can ruff"; tags `ruff` /
`te`), the reverse of a side-suit count. Smith echo (NT only, `smith_reads`):
the first card a defender plays in a declaring-side suit other than the
opening-lead suit is attitude about the OPENING-LEAD suit (standard high =
"liked the lead, continue"; reverse inverts) — and it suppresses the ordinary
count read on that card. Trump echo reads automatically; Smith is a header combo
(Off / Standard / Reverse, a defending-side agreement). Covered by
`test_teaching_view.py::{test_trump_echo,test_smith_echo}`.

**Rule-of-7 hold-up counter** — `holdup_rule_of_seven`: at NT, ducks to play in
the danger suit = 7 − (combined declarer+dummy original length); a live Plan line
"duck N (M left)". Companion to the danger hand.

**Danger hand in suit contracts** — `danger_info` also handles a suit strain: a
defender with a proven side-suit void who still has trumps is the ruff danger
("draw trumps before conceding the lead").

**Cross-hand communication entries** — `_render_hand` badges (Expert) a hand's
lowest card with `↦` when the PARTNER (declarer↔dummy) holds that suit's master
and this hand has no winner of its own — Manley's transportation.

**Ruff-lead suit-preference** — `ruff_lead_reads`: in a suit contract, a lead of
a suit the partner is KNOWN void in (from an earlier show-out) and can ruff is
read as suit-preference for the ruff return.

**Honesty for discard / trump-echo / Smith reads** — extended beyond follows:
`_attitude_discard_honest`, `_trump_echo_honest` (parity-correct for trumps, where
the engine's even-high model is wrong), and `_smith_honest`, all via
`_holding_at_suit` (the signaller's reconstructed holding when face-up).

**Reverse-Smith leader/third-hand asymmetry** — in reverse Smith only the OPENING
LEADER reverses (high = "I have an alternative, shift"); third hand stays standard
(high = continue). Reads are tagged `(lead)` / `(3rd)`.

**Finesse odds + vacant-space honour placement** — `finesse_hints`
(8-ever-9-never for a missing Q, finesse-the-Q for a missing K) in the Plan;
`honour_placement` now shows vacant-space probabilities ("♠K: W 60% E 40%") when
the two hidden hands diverge.

**Squeeze threat / busy-card tagging** — `squeeze_threats`: threat (menace) suits
where the declaring side holds the card below an opponent-guarded master; a
defender guarding ≥2 threats is `◆ busy` (squeeze candidate) — tagged in the seat
title and the Count panel.

**Carding config persistence** — the header selectors default from the app's
`signalling_convention` preference (`_app_default_udca`) and persist
(`_save_prefs`/`_load_prefs` → `CONFIG/teaching_view.json`).

**Loser marking + label** — declaring-side loser cards (LTC-style,
`suit_loser_ranks`) are drawn with a red box in the Known column, the
counterpart of the green sure-winner box, with a per-suit "Losers: ♠N ♥N …"
label in the Plan panel.

**Bayesian card-by-card distribution** (`bayes_distribution`) — a Monte-Carlo
posterior over the hidden hands: sample full deals of the unseen cards
consistent with each seat's exact remaining count, the proven/forced cards, the
shown voids AND the auction HCP/length constraints; aggregate to per-(seat,suit)
length probabilities and per-honour location probabilities. Feeds the
honour-placement labels + Other-column hints and a "Likely shape" line in the
Count panel (Expert). Falls back to the vacant-space estimate when too few valid
worlds are found.

**Squeeze types + rectified count** — `squeeze_threats` now classifies the
position (simple/positional, double, trump, criss-cross) and reports the
rectified-count state (down to the last loser → the squeeze operates now) via
`_declaring_losers`; shown in the Count panel.

**Suit-preference read honesty** (`_suit_pref_honest`) — a Lavinthal discard /
ruff-lead suit-preference signal is checked, when the signaller is face-up,
against the side suit where they actually hold the values; a false-card shows a
red ✗.

**Carding Preferences tab** — Preferences → Carding sets the per-pair carding
presets + Smith echo, persisted to `B-PREFER.CFG`. The header selectors and this
tab share the SAME config (single source of truth); changing either updates both
(`reload_carding_defaults`).

**Whole-deal instrumentation summary for Claude** (`instrumentation_summary`) —
when Claude Code reviews a completed deal it is fed a plain-text rundown of the
deal through EVERY lens above (counting, the declarer plan, squeeze, the Rule-of-
11 lead read, and the full defensive-signal log with honesty) and instructed to
critique the deal through those features.

All covered by `test_teaching_view.py` (16 tests).

Deferred (genuinely out of scope for now): auto-detecting the EXACT rectified-
count moment trick-by-trick during play (today: a static all-but-one-loser
heuristic from the current holdings); intent-based honesty for signals that are
not mechanically checkable even with the hand face-up (e.g. a deceptive
suit-preference where the values genuinely sit elsewhere by design).
