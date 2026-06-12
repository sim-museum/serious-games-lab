# biq — Claude Code project notes

## STATUS — no-peek cardplay engine (2026-06-12)

biq's no-peek cardplay (`backend/nopeek.py`) is now an **alpha-mu** engine: DDS
on belief-sampled hidden layouts + a CONSISTENT line across indistinguishable
samples — strong like PIMC but with **no strategy-fusion tells** (the user's
requirement: "DDS on representative samples is fine; the tells are what they'd
scoff at"). Live-viable: per-decision time budget ≤5s/card; the Q-NET client
forks every card so a libdds crash can't wedge a match.

**Measured LIVE vs Q-Plus 17.1** (forced-contract rig, 61 paired boards,
`nopeek_qss_compare`): from a per-seat engine 1.5–1.8 tr/board behind, now
**declarer ≈−0.6, defence −0.56 tr/board** — and legible.

Shipped this arc (all A/B-gated with the SEEDED `tools/nopeek_eval.py --rng`):
- Alpha-mu declarer (1.484→~1.06 vs DD) and defence (1.219→~0.80, edges PIMC).
- **Defensive signalling** (`backend/signals.py`): standard attitude/count/
  suit-pref among trick-equivalent cards; emitted via the alpha-mu `tiebreak`.
- **Reliable signaller**: `AlphaMu.signal_margin` (default 0.15) so biq plays the
  convention card among near-equal spots — trick-neutral-to-positive.
- Interior-sequence opening-lead fix (KJTx/AJTx/AT9x → J/J/T, was the bottom).

Measured + SHELVED (default-off, documented negatives): defence rollout
(`defender_search`), rollout-leaf alpha-mu, hard-filter signal-READING
(`signal_read`; biq isn't a reliable enough signaller for hard filters in
self-play). Env knobs: `BIQ_AMU_WORLDS/DEPTH/BUDGET/DEFENSE`, `BIQ_DEF_ROLLOUT`,
`BIQ_DEF_ROLLOUT_LEAF`, `BIQ_READ_SIGNALS`, `BIQ_SIGNAL_MARGIN`.

DEFERRED (user's signal-reading design): convention config setting, end-of-hand
mis-signal admonition bar, auto-disable counter (`signal_read.mis_signals` is
built + tested). See memory `plan_biq_singledummy_engine`,
`project_biq_defensive_signalling`.

## Cardplay engine — DO NOT confuse with BEN

biq is **NN-free**. Bidding goes through `native_bidder.NativeBiddingEngine`
(rule-based, system-driven), opening leads through `native_lead`, and
follow-on cards through `get_mc_card_play` (Monte Carlo + DDS).
`BridgeEngine` only loads the DDS solver. **BEN has been REMOVED** —
ignore any older docstring or comment that mentions it.

## To-do — per-tab comparison-mode widget

Each corpus tab in `tools/qplus_mixed_corpus.py` (Random, Bidding-system
matrix, Slam-eligible) should expose a tri-state widget (radio group or
combo box) that selects what's being compared in the run:

1. **Compare bidding only** — current behaviour. The diff tool feeds
   the deal hands to both biq's bidder and Q-Plus's recorded bidding,
   reaches a contract on each side, and scores both via DDS. Tells us
   nothing about cardplay strength because DDS plays both sides
   omnisciently.

2. **Compare cardplay only** — Q-Plus's recorded bidding is used as
   the contract for BOTH sides. Q-Plus's cardplay engine plays the
   deal as recorded; biq's MC+DDS engine plays the same contract on
   the same deal. Compare actual tricks taken. This isolates cardplay
   strength.

3. **Compare end-to-end performance** — deal → biq bids → biq plays
   vs deal → Q-Plus bids → Q-Plus plays. The fullest comparison;
   conflates bidding and cardplay strength but matches what a user
   would see at the table.

### Implementation notes

* The widget belongs on each corpus tab (not in Calibration / Help).
* State 2 needs Q-Plus's bidding history extractable from the
  `savescore.qss` per-deal blocks — `parse_bdl_with_systems` in
  `tools/qplus_mixed_corpus.py` already returns this; expose the
  per-deal auction tokens so biq's cardplay engine gets the same
  auction inferences Q-Plus's declarer used.
* State 2 and 3 require Q-Plus's actual played-tricks count to be
  parsed from the QSS. Q-Plus writes this on `save match and exit`;
  the current `mixed_corpus_diff.py` ignores it in favour of
  re-running DDS on the contract. The parser would need to surface
  the trick count per deal so the comparison report can show
  Q-Plus-actual vs biq-MC+DDS.
* `tools/mixed_corpus_diff.py` would grow a `--mode {bidding,
  cardplay, end-to-end}` flag matching the widget state.
* For state 2 the report header should make it explicit that BOTH
  sides played the same contract — otherwise it's not interpretable.

### Why this matters

The current diff tool produces **bidding-only** numbers. All the
"+1.82 IMP/deal" / "+0.59 IMP/deal" results from the polish session
are pure bidding gaps. We have no measurement of whether biq's
MC+DDS cardplay is competitive with Q-Plus's commercial engine.
Until states 2 and 3 exist, end-to-end strength claims are
extrapolations.

## Cardplay benchmarking — three planned harnesses

The current `tools/mixed_corpus_diff.py --mode cardplay` plays biq
on ALL four seats vs Q-Plus's recorded play, then scores by IMP.
This biq-vs-biq symmetry CANCELS declarer-side improvements:
biq's improved defender plays equally well against biq's improved
declarer, so trick-delta barely shifts. Confirmed empirically —
defender-only rules show positive gains, declarer rules don't.

To measure asymmetric improvements honestly we need harnesses
where biq plays ONE side and a different engine plays the other.

### Plan 1 — QSS replay harness (single-seat biq vs recorded Q-Plus)
**File**: `tools/mixed_corpus_diff.py` — add `--mode replay`.

For each deal × each of the 4 seats:
- Replay the deal trick-by-trick from the QSS.
- For the 3 non-biq seats, play Q-Plus's recorded card.
- For biq's seat, biq's planner/MC decides.
- Validate biq's card is legal; track wins/losses.
- Aggregate per-seat trick-delta vs Q-Plus's seat performance.

Yields 4 isolated measurements per deal:
- biq-as-N declarer/defender tricks vs Q-Plus's N tricks.
- Same for E, S, W.

Each is an HONEST measure of biq's skill at that seat. Symmetric
biq-vs-biq cancelation gone.

**Effort**: ~100 lines harness, reuses QSS parser, planner, MC.
**Status**: TO BUILD FIRST.

### Plan 2 — Multi-biq-bot self-play (4 distinct configs)
**File**: new `tools/multi_bot_diff.py`.

Run cardplay with 4 different biq configs at the 4 seats:
- biq-A = Phase 15 baseline (committed best)
- biq-B = Phase 15 + Phase 23 entries
- biq-C = Phase 15 + Phase 23 + 25 (K-loc finesse)
- biq-D = all attempted items

For this to work, the planner must accept a config object per
call (currently it's module-global). ~50 lines of refactor.

Each variant is biased to fire/suppress different phases. Across
many deals, the variant taking the most declarer tricks on its
contracts wins. Head-to-head comparison.

Useful for:
- A/B testing planner additions without biq-vs-biq symmetry.
- AlphaZero-style training later (loser's config trains toward
  winner's, if/when we add learned components).

**Effort**: ~50 lines planner refactor + ~150 lines harness.
**Status**: TO BUILD SECOND.

### Plan 3 — Q-NET TCP protocol RE (live biq vs Q-Plus over network)
Q-Plus 17.1 ships `Q-NET.EXE` (2.8 MB, beside `QBRIDGE.EXE`).
Architecture: `QBRIDGE.EXE` ←DDE→ `Q-NET.EXE` ←TCP→ remote
`Q-NET.EXE` ←DDE→ remote `QBRIDGE.EXE`. Commands recovered from
strings:
```
DDE_CMD_CONNECT / DISCONNECT / START_SERVER / STOP_SERVER
DDE_CMD_DIRECT_MESSAGE / NET_COMMAND / RESEND_MESSAGE
DDE_REQ_STATE / EXIT
```

No documentation ships for the wire protocol. Reverse-engineering
path:
1. Run two Q-Plus instances locally under Wine.
2. Configure one as bridge server, the other as client.
3. Capture TCP traffic with tcpdump/Wireshark.
4. Decode message format (probably framed binary with a header
   indicating command type).
5. biq implements a client speaking that protocol.

Enables LIVE interactive play between biq and Q-Plus — biq's bids
get factored into Q-Plus's auction; Q-Plus's cardplay adapts to
biq's plays. Useful for genuine competitive testing.

**Effort**: 2-3 days RE + ~500 lines of protocol client.
**Status**: TO BUILD THIRD.

## biq as Q-NET SERVER, Q-Plus as client (DEFERRED 2026-06-06)

The mirror of Plan 3: make **biq host** a live match that a **Q-Plus
client** joins over Q-NET, rendered in biq's GUI. Paused mid-build; this
section captures the design, what's done, and what's left so it can be
resumed cleanly.

### Critical gotcha — two DIFFERENT server protocols

biq's GUI **"Network → Start bridge server"** (`network/server.py`,
`client.py`, the lobby dialog) speaks biq's **NATIVE protocol: JSON
objects, newline-delimited** (`network/protocol.py`). It is for **biq↔biq**
play only (one biq client per seat). **Q-Plus CANNOT join it** — Q-Plus
speaks Q-NET (plain-text bracketed tokens, `"cmd" [arg]...`). A Q-Plus
client connects the TCP socket ("Connected to server") but its `join_game`
handshake is unintelligible to biq's JSON server, so the seat stays "not
conn." and Join does nothing. Confirmed live 2026-06-06. **Keep the two
paths separate: biq-native lobby stays for biq↔biq; the Q-NET host path is
additive and must never break it.**

### Architecture chosen (and why)

Do NOT marry Q-NET into the event-driven `NetworkGameController` (high
risk, untestable without live Q-Plus). Instead **wrap the proven
`tools/biq_qnet_server.py` `BiqServer` (synchronous Q-NET match loop) in a
`QThread`**; its callbacks emit Qt signals that drive the GUI table +
status strip live. biq↔biq native server and the `biq_qnet_server` CLI are
both untouched. Validate via the biq-client↔biq-server loopback
(`biq_qnet_client` stands in for Q-Plus — same wire format).

### Status

- **DONE — `BiqServer` callbacks** (committed-pending). `__init__` takes
  `callbacks={}` (no-ops by default → CLI unchanged); `_emit()` fires
  `status`/`deal`/`bid`/`contract`/`card`/`board_done`; `stop()` for
  thread shutdown. Verified: constructs + emits.
- **TO BUILD — `QNetServerThread`**: QThread running
  `accept()`/`handshake()`/`run_match()`, callbacks → queued Qt signals.
- **TO BUILD — GUI action + handlers**: a menu action ("Start Q-NET server
  (Q-Plus client)…"), handlers that render deal/auction/contract/running
  score, East shown as 🖧 Network (reuse `table_view.set_seat_types` +
  the new status strip).

### The THREE setups and their MEASUREMENT value (decision context)

Measurement quality tracks how FEW seats are biq (less biq-vs-biq
cancellation — see the cardplay-benchmarking section above):

1. **biq host + 1 Q-Plus client** — biq plays 3 seats (N/S/W), Q-Plus 1
   (E). Closed room = all-biq, double-dummy. **Poor measurement**: biq is
   3/4 → cancellation dominates; baseline re-bids + is DD (muddy). Value is
   only as a **protocol/GUI proof + demo**. This is the in-progress build.
2. **Q-Plus host + 1 biq client** (the PROVEN `biq_qnet_client` runs) — biq
   1 seat (E), Q-Plus 3 + its own all-Q-Plus real-play closed room. **Clean
   single-seat** biq-vs-Q-Plus (no cancellation, biq is 1/4). Caveat: biq's
   partner is a Q-Plus bot, so limited bidding signal; mind the deal-
   rotation trap (use a fixed BDE deck).
3. **biq host + Q-Plus E/W pair** (multi-client, TO BUILD) — biq N/S pair
   vs Q-Plus E/W pair (2 bots). All-biq closed room (N/S held biq) isolates
   the WHOLE E/W pair → **best measurement** (full external pair, no
   cancellation). Needs: multi-client `BiqServer` (seat→conn map + per-seat
   routing; currently 1 client) and EITHER two Q-Plus client instances
   (one joins E, one W) OR one client driving both. For a clean pair number
   upgrade the closed room from all-biq-DD to real biq E/W play, or use the
   double-pair swap (`tools/double_pair_compare.py`).

### Open Q-Plus-side unknowns (verify live before Setup 3)

- Will a Q-Plus **client** auto-play a **Computer bot** at its joined seat,
  or insist on a human there? (In proven runs biq was the bot; Q-Plus-
  client-as-bot is unconfirmed.)
- Can **two Q-Plus client instances** connect to one server (for the E/W
  pair)? If either fails, the pair comparison stays on Setup 2 (Q-Plus as
  server).

### Resume order

Finish Setup 1 (QThread + GUI handlers) as the plumbing/demo proof → quick
live Q-Plus-client-as-bot check → if it passes, build multi-client for
Setup 3 (the real measurement target). See memory
[[project_biq_qnet_server]] and [[project_biq_validation_plan]].

## Related memory

* `plan_option1_semantic_state.md` — AuctionContext architecture
* `project_biq_qplus_parity.md` — corpus baseline + polish history
* `plan_slam_bidding_architecture.md` — the original 5-phase plan
  (superseded by Option 1)
