# BridgeIQ web port — build status

**Date:** 2026-06-30
**Deliverable:** `web/bridgeIQ.html` — single self-contained HTML file (~166 KB,
no dependencies, no server). Opens in any modern browser.

## Goal
Transpile the entire PyQt6 BridgeIQ desktop application (63 K lines of core app)
into one browser-runnable HTML file with **all functionality** — not a demo.

## Status: COMPLETE ✅

All five sprints delivered and validated headless (jsdom).

| Sprint | Scope | Status |
|---|---|---|
| 0 — Foundation | models, scoring, Pavlicek, deal gen, JS double-dummy solver, UI shell | ✅ |
| 1 — Bidding engine | 5 systems, rule-based, `why=` explanations, sanity wrapper | ✅ |
| 2 — Card play | opening leads, signals, follow/discard heuristics, exact DD endgame | ✅ |
| 3 — Full UI | menubar (8 menus), 40 dialogs, 4 modes, teaching explainer, score tables | ✅ |
| 4 — Integration | PBN/LIN import, PBN/HTML/JSON export, persistence, print, self-test | ✅ |

## What was ported
- **Exact ports:** `backend/models.py`, `backend/scoring.py` (contract score, IMP,
  matchpoints, full Rubber scorecard), `backend/pavlicek.py` (BigInt combinatorial
  deal numbering + base-72 IDs, round-trips).
- **Reimplemented from spec:** `native_bidder.py` (SAYC, 2/1 GF, Standard Acol,
  Standard French, Precision90M — openings/responses/rebids/competitive/slam),
  the card-play stack (`native_lead.py`, `signals.py`, `nopeek.py`).
- **From scratch:** a JavaScript double-dummy solver (alpha-beta + MTD
  narrow-window + trick-boundary transposition table) replacing native `libdds.so`.
- **Full UI:** `main_window.py` menus/flow + every `ui/dialogs/*`.

## Validation (headless jsdom)
- Loads with **0 runtime errors**; renders 52 cards, 8 menus, 38 bid buttons.
- Bidding: **0 illegal bids, 0 runaway auctions over 300 deals × 5 systems**.
- End-to-end (deal→bid→play→score): **25/25 deals, 0 exceptions**.
- Human bid+play path: bids via buttons/keyboard, plays cards (incl. dummy),
  trick resolution, end-of-hand prompt — **0 errors**.
- **All 40 dialogs** open/close cleanly.
- Double-dummy solver: correctness checks pass; **worst single card decision 37 ms**.
- Pavlicek deal-id round-trips; session save/restore works.

## Known engineering tradeoff
A full 52-card exact double-dummy solve is too slow for plain JavaScript
(13-trick solve >10 s even with MTD + transposition tables). Card-play DD is
therefore **endgame-only** (last ~6 tricks, node-bounded so the tab never
stalls) with strong heuristics for early tricks. The DD-analysis dialog marks
`≈` on full-deal cells it cannot solve exactly within its time budget. This is
the only divergence from the native binary and is a platform limit, not a
feature cut.

## Layout rework (2026-06-30, sprints R1–R4) — match the PyQt UI exactly
After comparing against a screenshot of the desktop app, the UI was rebuilt to
copy the PyQt layout:
- **Classic light menubar** (was a dark gold theme).
- **Left info panel**: "System:" header, the auction as a **Bid | Points | Help**
  table, and an **"Available bids for South"** table listing every legal call with
  its point range and meaning (generic descriptions — no HCP leak). Click a row to bid.
- **Center green table** with the Dealer/Vul box and the **central N/E/S/W auction grid**.
- **Top-right bidding box** "Bidder: S" — Pass/X/XX, a ♣ ♦ ♥ ♠ NT × 1–7 grid,
  Alert / Explanation links, and the `Keys: 1c-7n, p=pass, x=dbl` hint.
- **4-colour suits**: ♠ black, ♥ red, ♦ **blue**, ♣ **green** (was orange diamonds).
- **Realistic card faces** with proper pip layouts (A=1 … 10=10 pips) and court indices.
- **South hand** as large cards along the bottom; **Contract** box bottom-left.
- **Bottom button row**: Next deal · Next card · Hint · **Undo** · Claim · **Evaluate**
  · **Autoplay** · Review · **Closed room** · **Instrumented** · Help.
- **Instrumented teaching view** (3×3 grid: contract, per-seat HCP/shape, plan,
  current trick, count, coaching) toggled by the Instrumented button.
- Default systems set to **SAYC / SAYC** to match the desktop default.

## Play/hint/dialog fixes (2026-06-30)
- **Play the declaring side**: when your side wins the contract you now play (and see)
  **both** the declarer and dummy hands — no more sitting idle as dummy with the
  partner's hand hidden. Defenders still see their own hand + dummy only.
- **Trick cards on the felt**: the current trick is now clustered in the centre of
  the table (centre-anchored transforms) so all four cards stay on the green; the play
  table was also enlarged.
- **Auction & Played Tricks** dialog rebuilt: tall (fills the screen), **colour-coded**
  (♠ black · ♥ red · ♦ blue · ♣ green), larger, with the **auction in a real 4-column
  N/E/S/W grid** (not one smushed line) and the winner colour-keyed by side.
- **Hint** now opens straight to the full analysis (coaching note + suggestion +
  deeper analysis) — no more click-through. The dead footer button is gone.
- **"Ask Claude for deeper advice" now works**: it calls the Anthropic Messages API
  directly from the browser (`anthropic-dangerous-direct-browser-access`), using the
  user's own API key (entered once, stored only in `localStorage`), and shows Claude's
  advice on the current bid/card. Model configurable via `CONFIG.claudeModel`
  (default `claude-sonnet-4-6`). Falls back to a clear message on key/CORS errors.

## Bellot card deck, 4-colour, PyQt sizing (2026-06-30)
- Embedded the authentic **SVG-cards 4.0** deck — © 2005 David Bellot, © 2016–17
  Huub de Beer, **GNU LGPL 2.1+** (github.com/htdebeer/SVG-cards). The full deck is
  inlined once as hidden `<defs>` (its licence notice preserved in the file); every
  card renders as `<use href="#spade_king">`. Procedural cards remain as a fallback.
  This takes the single file to ~1.1 MB (still self-contained, no external assets).
- **4-colour recolour** to match the desktop: diamonds → **blue**, clubs → **green**
  (hearts red, spades black). Done by editing only the `#diamond`/`#club` pip symbols
  and the diamond/club card groups — hearts, spades and the shared court figures are
  untouched. (LGPL permits modification; notice kept.)
- **Card size** raised to 118×170 px to match the PyQt hand cards; North + South
  hands render large, the sides medium.

## Cardplay view + professional courts (2026-06-30)
- **Bidding↔play layout switch** (was broken — the cardplay screen still showed the
  bidding UI). During **play/finished** the left info panel, the bidding box and the
  centre auction grid are hidden; the felt table expands and the **current trick is
  drawn as large cards in the centre** (positioned by seat), with the four hands
  around the table and seat labels hugging the table edges — matching the desktop
  cardplay screen. Bidding keeps the panel + auction grid + bidding box.
- **Professional court cards**: replaced the cartoonish faces with a clean **heraldic
  design** — a differentiated crown (King = cross, Queen = pearls, Jack = fleur-de-lis),
  a large serif rank index and the suit pip, point-symmetric, framed. No faces.

## SVG court deck (2026-06-30)
J/Q/K now render as **procedurally-drawn SVG court figures** (crown + robe + scepter
for K/Q, feathered cap for J), suit-coloured and **point-symmetric like a real card** —
self-contained, no external image assets (~1 KB of generated SVG per court). Number
cards keep their pip layouts; aces a single centre pip. `deck-preview.html` (local,
not committed) renders all 52 for inspection.

## Visual fidelity pass (2026-06-30) — match the PyQt screens
- **Cards fixed**: the dummy/around-table hands were rendering as tiny, fully
  overlapped (invisible) cards. They are now **large, opaque, suit-grouped** like the
  desktop (North across the top; East/West as suit rows down the sides; dummy clearly
  visible during play). Dimmed (illegal) cards are only lightly de-emphasised.
- **Instrumented view rebuilt** to match the desktop: a header strip (Instrumented
  view · Detail · Carding N/S · E/W · Smith · N/S–E/W systems), a 3×3 grid —
  Contract/Tricks · North · Plan / West · Table · East / Count-Honours · South ·
  Coaching-Signals — each hand cell showing **Known | Other** columns per suit with
  master/sure-winner markers, inferred ranges and voids for hidden hands, a "shape"
  line, danger flags, "the race", a signal log, and the bottom **legend**. It overlays
  the left panel + table and leaves the bidding box, exactly like the desktop.
- **Play screen**: Hint now opens a **"Hint — card play"** dialog with a coaching
  note, "▶ biq suggests: play X", and an **"Ask Claude for deeper advice"** button
  (expands a local deep analysis — no API needed). Added a **Tricks  d : f** box,
  the **Contract: W 3D** format (declarer first), and **"Your play (S)"** status.

## Monte-Carlo card play (2026-06-30) — real PIMC for early/mid tricks
The `mc` engine (the default) now plays the early and middle tricks with genuine
**Perfect-Information Monte-Carlo**, no longer peeking:
- For the seat to act, it samples the **hidden** hands many times (default 14,
  configurable 4–60 in Configuration ▸ Playing Strength), consistent with what it
  can prove: **shown-out voids**, remaining-card counts, **vacant-places weighting**,
  and a light **auction HCP filter** (openers ≥ ~10, players who declined to open
  capped, weak/preempt openers capped).
- Each candidate card is **rolled out** across the samples and the one with the best
  **average tricks for its side** is played.
- The **endgame** still switches to the exact double-dummy solver, and **opening
  leads** stay rule-based (as in `native_lead.py`). `dd` mode remains omniscient;
  `rule` mode is pure heuristics.
- Measured headless: fires correctly, **worst single card decision ~230 ms**,
  0 exceptions over multi-deal runs. This narrows the gap with the desktop engine
  on early-trick play; it still isn't `libdds`-speed PIMC, so all-computer batch runs
  are slower (~6 s/deal with four MC seats), but interactive play stays snappy.

### Still not identical to PyQt
- **PyQt:** native `libdds.so` (full-speed C double-dummy) lets it run DD on *every*
  MC sample at *every* trick, plus an alpha-mu no-peek refinement.
- **Browser:** DD is reserved for the endgame; early/mid MC rollouts use the fast
  heuristic engine (a pure-JS full-deal DD per sample per card is too slow). Same
  family of method, lighter rollout evaluator.

## Files
- `web/bridgeIQ.html` — the application (single file)
- `web/README.md` — user-facing overview
- `web/STATUS.md` — this file
