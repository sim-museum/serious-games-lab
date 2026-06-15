# BridgeIQ

A PyQt6 bridge application for Ubuntu 24.04 with classic desktop Bridge
interface. As of 2026-05, BEN/TensorFlow has been removed; bidding is
rule-based (modeled on Q-Plus's Precision90M and four other systems) and
card play is DDS + Monte-Carlo sampling against libdds.so.0.

## Plan to finish bidding + play (2026-05-23)

Goal: a competent, correct teaching bridge program across 5 systems.
Not parity with Q-Plus; correctness + coverage + no pathological bids.
Once this plan is complete, only teaching tools remain (modeled on
pokerIQ — hand reviewer, "why did you bid that?" explainer using the
`why=` strings already on every Bid, drill modes).

### Phase 1 — Multi-system smoke test
Run 10-deal diff sessions against Q-Plus for the four non-Precision
systems: SAYC, 2/1, Standard Acol, Standard French. Target is *no
illegal bids, no sanity-wrapper firings, no obviously broken auctions*
— NOT match-rate parity. Fix the top 2 issues per system. Stretch:
one second seed for any system showing brittleness.

### Phase 2 — Precision90M polish (optional)
Two known gaps from seed=400: overcall handling (lead-direct overcalls
like 3♦ after partner's 2♦ three-suiter) and Stayman+splinter cascades
(earlier seeds). Target: 20/50 perfect (currently 17/50). Stop there
— diminishing returns.

### Phase 3 — Card-play push
Tested 2026-05-23. Outcome: **68-69% maintained, 75% not reached.**

Position-aware tie-breaks (third-hand-high, cash-high-from-short)
were tried and either harmed match rate (cash-from-short dropped
the mean to 62%) or had no measurable effect (third-hand-high
landed inside the ±2% MC noise band). Increasing the MC sample
count from 40 to 80 to 200 tightened the variance but the mean
stayed at 69% — indicating algorithmic, not sampling, ceiling.

Categorising 193 mismatches: 45% cross-suit (DDS samples disagree
about which suit is best — sampling-driven, not tie-break),
36% within-suit-low (DDS prefers the higher card outright on
the MC distribution, so tie-break never runs), 17% within-suit-
high (the candidates for tie-break refinement), 2% leads. Even
matching every single within-suit-high case wouldn't reach 75%
without progress on the 81% that aren't tie-break problems.

Zero sampler fallbacks across 520 cards — the "no-valid-samples"
issue is fully fixed (per-card random distribution + auto-relax
of shown_out, both from the previous session).

**Phase 3b (deeper attack, 2026-05-23):** auction-informed
sampling implemented and tested.

  * `_derive_hcp_constraints` pins each seat's HCP range from
    their first non-pass bid: 1NT opener → system NT range,
    Precision 1m/1M → 10-15, SAYC 1m/1M → 10-21, weak twos →
    5-11, passers → 0-9, etc.
  * `_derive_shape_constraints` pins suit lengths the same way:
    1♥/1♠ → 5+ in that major, 1NT → balanced (each suit 2-5),
    Precision 2♦ → 0-1 diamonds + 3+/3+ majors, weak twos →
    5-6 in the suit, …
  * MC sampler rejects samples that violate either constraint;
    relaxes back to shown_out-only and then to unconstrained
    if no valid sample is found.

Empirical result: 10-run mean **68.6% with constraints vs 68.4%
without** — inside the ±1% noise band. 24% of samples are
rejected by the HCP filter on a typical 520-card run, so the
constraints fire as designed, but DDS's per-card best-pick is
robust to the removed extreme samples — the surviving 76%
already cover the same plausible-truth distribution.

Diagnosis: the 31% mismatch isn't sampling noise, it's that
Q-Plus's card engine appears to be **rule-based** (same family
as its bidding), not DDS+MC. So Q-Plus's choices reflect
specific bridge principles (signals, entry preservation,
deception, stylistic preferences) that DDS expectations don't
capture, and tightening the MC's sample distribution toward
"the truth" doesn't pull the picks toward Q-Plus's heuristic
choices.

The constraints are kept in the codebase regardless — they are
correct bridge logic and a useful foundation for future work
(per-card biased sampling, position-specific override library
built on top). But the realistic ceiling without that further
work is 68-69%. Phase target reset: 70%, not 75%.

Users seeking stronger play should play wbridge5 or Q-Plus
directly. For teaching purposes, where the user wants to see
*defensible* card play and learn *why* a card was chosen, the
current engine is adequate.

**Phase 3c (manual mining + override library, 2026-05-23):**
Mined `MANUAL/ENG/BRIDGE.HLQ` for Q-Plus's card-play rules.
Two conventions documented:

  1. `.lead-conv` — opening leads. Already implemented in
     `backend/native_lead.py` (4th best, top of sequence, ace
     from AK, etc.). No work needed.

  2. `.signal-conv` — present count: in the SECOND round of a
     suit, defender plays a high small card for odd original
     count, lowest for even. Q-Plus's example: holding A-8-2,
     after winning trick 1 with the ace, lead the 8 (high
     small, odd); holding A-8-5-2, play the 2 (lowest, even).

Implemented as `_position_override_card` (engine.py): when a
defender follows an opp-led non-trump suit on their second
round of that suit, override the lowest-equivalent tie-break
with the present-count card. Fires ~18 times per 520-card
match (3.5% of plays). Match-rate impact: neutral inside the
MC noise band. Teaching impact: each override gets logged
"override-present-count" so the explainer UI can show *why*
the engine played that specific card.

No behavioral probes were needed — the manual specified the
convention directly. To reach 75% would require additional
conventions that the manual doesn't fully spell out (entry
management, hold-up rules, deception, finesse choice). Those
need genuine reverse-engineering work (behavioral probes
against specific test deals); not justified for a teaching
tool that already plays defensibly at 68-69%.

### Phase 4 — Integration + robustness
Ran 2026-05-23. 50 deals × 5 systems = 250 board-runs end-to-end.

End-to-end pipeline (deal → bid → play → score) is rock-solid:

| Metric | Result |
|---|---|
| Pipeline exceptions | 0 ✓ |
| Illegal bids escaping wrapper | 0 ✓ |
| Card engine returning None | 0 ✓ |
| Score-function exceptions | 0 ✓ |
| Auctions hitting the 80-bid cap | 0 ✓ |
| Pass-out auctions on 22+ HCP | 0 ✓ |
| Sanity-wrapper firings | 14 / 250 (5.6%) |
| Down-5-or-more contracts | 4 (all from one board — marginal 3♣ jump-overcall with QJ stack offside) |

The 4 down-5 cases all come from one specific deal where N
makes a vulnerable 3♣ jump-overcall on 8 HCP / 6 clubs into
E's QJ52 trump stack — a legitimate "wild" bidding decision
that occasionally bites. Not a bug; the wrapper isn't catching
it because it isn't illegal.

Save/restore round-trip works mid-game: `BoardState.to_dict()`
→ JSON → `BoardState.from_dict()` preserves the auction, played
tricks, and remaining hands; continuing the play after a
restore reaches the same final trick count as a parallel run
that never serialized.

Smoke harness: `/tmp/phase4_smoke.py`. Save/restore test:
`/tmp/phase4_save_restore.py`.

### Phase 5 — Define "done"
Exit criteria: zero illegal bids over a 100-deal cross-system stress
run, zero sanity-wrapper-rescued pathological auctions, card play ≥
70% match rate vs Q-Plus. Tag a `bidding-and-play-complete` release;
move to teaching tools.

---

## Project Overview

This application provides a desktop bridge playing and analysis environment,
treating BEN as a pure engine (bidding, play, analysis) while implementing
a classic desktop bridge UI in PyQt6 as a separate layer.

## Architecture

```
bridgeIQ/           (~4,200 lines of code)
├── main.py             # Application entry point
├── run.sh              # Startup script
├── test_basic.py       # Test suite
├── README.md           # Documentation
├── backend/        # BEN Engine wrapper
│   ├── engine.py       # BridgeEngine class (bidding, play, analysis)
│   └── models.py       # Data models (Card, Hand, Bid, Board, etc.)
├── ui/      # PyQt6 UI (BridgeIQ style)
│   ├── main_window.py  # Main window with menus and game control
│   ├── table_view.py   # 4-hand table display with trick area
│   ├── bidding_box.py  # Bidding interface with keyboard support
│   └── dialogs/        # Configuration dialogs
│       ├── player_config.py   # Human/Computer player settings
│       ├── match_control.py   # Deal source, scoring, comparison
│       ├── deal_filter.py     # HCP/shape filters
│       ├── score_table.py     # IMP/MP/Rubber scoring
│       └── simulation.py      # Bid simulation analysis
└── data/config/        # Configuration files
```

## Key Features

### BEN Backend Integration
- **Direct Python API**: Imports BEN modules directly (no HTTP/WebSocket overhead)
- **Model Loading**: TensorFlow models loaded on startup
- **Bidding**: BEN's `BotBid` class for neural network bid decisions
- **Play**: BEN's `BotLead` and `CardPlayer` for card play
- **Analysis**: BEN's DDS solver for double-dummy analysis
- **Score Calculation**: Contract scoring for IMP/MP/Rubber

### BridgeIQ Style UI
- **Table View**: Four-hand display around central trick area
- **Vulnerability Indicator**: Visual N-S/E-W vulnerability display
- **Bidding Box**: Color-coded buttons with suit symbols (♠♥♦♣)
- **Auction Display**: Bid history in 4-column format
- **HCP Display**: High card points shown for each hand
- **Card Widgets**: Clickable cards with hover effects

### Game Modes
- **4-Player**: Human plays South, BEN plays N/E/W
- **1-Player**: Single hand visible (realistic play)
- **All-Computer**: Auto-play for analysis

### Menus (BridgeIQ Style)
- **File**: New deal, open/save files, export HTML
- **Deal**: Match control, repeat deal, deal filters
- **Configuration**: Players, bidding systems, preferences
- **View**: Show all hands, scores, DD analysis, bid simulation
- **Extras**: MiniBridge mode, one-player mode

### Dialogs
- **Player Configuration**: Human/Computer/External per seat
- **Match Control**: Deal source, scoring method, comparison mode
- **Deal Filter**: HCP ranges, shape constraints, special features
- **Score Table**: IMP/MP/Rubber scoring with history
- **Bid Simulation**: Evaluate candidate bids with samples

## Requirements

- Ubuntu 24.04 (or compatible Linux)
- Python 3.12+
- PyQt6
- TensorFlow 2.18+ (CPU)
- BEN engine (included in `../ben/`)

## Running the Application

**Important:** The app must be run from within the virtual environment.

```bash
cd /home/g/sgl/FRI/bridgeIQ/bridgeIQ
./run.sh
```

Or manually:
```bash
source /home/g/sgl/FRI/bridgeIQ/venv/bin/activate
export PYTHONPATH="bridgeIQ:ben/src:$PYTHONPATH"
python bridgeIQ/main.py
```

The `run.sh` script automatically activates the venv if it exists.

## Usage

1. **New Deal**: Press `Ctrl+N` or File > New Deal
2. **Bidding**: Click buttons or use keyboard (`p`=Pass, `1c`-`7n`=bids)
3. **Play**: Click cards in your hand
4. **Analysis**: View > Double Dummy Analysis or Bid Simulation

## Technical Notes

- BEN's Windows-only features (PIMC/BBA/SuitC) are disabled on Linux
- TensorFlow runs in CPU mode (GPU optional)
- Engine operations run in worker threads to keep UI responsive
- Signals/slots pattern for GUI-backend communication

## Files Modified in BEN

- `pyproject.toml`: Relaxed version constraints for Linux compatibility
  - `tensorflow-intel` → `tensorflow`
  - `numpy==1.26.4` → `numpy>=1.26.4`
  - `keras==3.6.0` → `keras>=3.6.0`
  - `requires-python = "==3.12"` → `requires-python = ">=3.12"`

## Q-Plus 17.1 — Tournament protocol mechanism (2026-05-30)

Research notes for when bridgeIQ might want to participate in a
computer-bridge tournament as one seat at a TableManager-driven
table. Q-Plus is taken as the reference because we already drive
it as the diff oracle, but the mechanism is the standard one used
by every competition-grade bridge program.

Q-Plus 17.1 speaks the **BlueChip TableManager protocol** (also
called the **WBridge5 protocol**) — the de-facto standard for
computer-bridge tournaments since 1997, and the protocol the
World Computer Bridge Championship runs on. Distinct from
Q-Plus's internal `Q-NET.EXE` peer-to-peer mechanism, which is
the channel two Q-Plus instances use to play each other.

### Evidence in the local binary

`/home/h/sgl/FRI/WP/drive_c/games/qbridge17/QBRIDGE.EXE` contains
the protocol's wire-message format strings verbatim. `strings`
output includes:

```
Connecting "%s" as %s using protocol version %d
%s ready for teams
%s ready to start
Start of board
%s ready for cards
%s ready for %s's bid
%s ready for dummy
%s ready for %s's card to trick %d
%s ready for deal
tablemanager
Tournament
.\LIB\WBRIDGE5\WB_1.DLL
wb_dll
```

These are the verbatim verbs of the BlueChip TableManager
protocol. The `LIB/WBRIDGE5/WB_1.DLL` reference is a numbered
plugin shim Q-Plus expects to load when acting as a protocol
partner. That directory does NOT exist in the 17.1 install on
disk (`LIB/` only contains `STRINGS/` and `BITMAPS/`) — either
the plugin was dropped from the 17.1 consumer bundle or it ships
only with a separate tournament-edition build. The speaking-half
strings are still compiled into the main `.EXE`.

The internal player-role symbols are `FG_PLAYER_HUMAN`,
`FG_PLAYER_REMOTE`, `FG_PLAYER_EXT`, `FG_PLAYER_ADV` (visible
roles: Human, Computer, Extern). The protocol-client role is
NOT one of the documented Configuration → Players options — it's
gated behind the missing DLL.

### How the protocol works

1. A separate **TableManager** program runs on a host (e.g.
   `BlueChip TableManager.exe`, `WBridge5 TableManager.exe`, or
   any compatible re-implementation). The TableManager is the
   only process that knows the deals.
2. Four bridge-playing programs each connect over TCP, each
   identifying itself as a single seat (North / East / South /
   West).
3. The TableManager sends each program ONLY its own 13 cards and
   only the cards each player has played publicly (plus dummy
   when revealed). Each program has no information about the
   other three seats except for the bidding and cardplay as
   communicated.
4. Bidding and play proceed by plain-text request/response on
   the TCP connection. Example:

   ```
   Client → server: Connecting "biq" as South using protocol version 18
   Server → client: South ("biq") seated
   Client          : South ready for teams
   Server          : Teams : N/S : "TeamA". E/W : "TeamB"
   Client          : South ready to start
   Server          : Start of board
   Server          : Board number 1. Dealer North. Neither vulnerable.
   Server          : South's cards: S Q J 7 4. H A K J 9 2. D 9 7. C 8 4.
   ...bidding...
   Client          : South ready for North's bid
   Server          : North passes
   Client          : South bids 1S
   ...play...
   Server          : South to lead
   Client          : South plays SA
   Server          : South plays SA           (broadcast to all)
   Client          : South ready for East's card to trick 1
   ```

5. All four programs see the same bidding / play stream; none
   see the other three hands until the deal completes (or until
   dummy is exposed after the opening lead).

This is the protocol the WCBC runs on. Every serious computer
bridge program (GIB, Jack, WBridge5, BridgeBaron, Micro Bridge,
Q-Plus historically) implements the client side.

### How to drive Q-Plus 17.1 into this mode

Inferred from the binary; manual is silent. If we ever want to
actually use it:

* The protocol-client implementation is compiled into
  `QBRIDGE.EXE` itself.
* Activation expects to dynamically load
  `LIB/WBRIDGE5/WB_1.DLL`. Not present in our install. Either
  (a) it shipped only with Q-Plus 12 / 15 and 17.1 dropped it,
  or (b) it ships with a "tournament edition" build distinct
  from the consumer install.
* No command-line switch is obvious in the strings (`/CON`,
  `/MAT`, etc. are the only ones I found, none protocol-related).
  Activation is most likely via a hidden menu item that only
  appears when the plugin loads, or a flag in one of the
  `CONFIG/B-*.CFB` binary configs.
* Practical path: contact `support@q-plus.com` for the WBridge5
  plugin DLL or the tournament-edition build. The speaking-half
  is already there — it's gated behind the missing plugin.

### Documented manual fallback: the Extern player role

`MANUAL/ENG/2-PLAYERS-A.DOC` documents the `Extern` player role,
which gives the same information model as the WBridge5 protocol
but driven by a human at a keyboard instead of TCP:

> "Each player must enter the bids and plays made by the player
> at the other computer. This information must be passed back
> and forth during the deal. When you are entering the cards for
> your partner, you will get an extra window which displays all
> the cards partner possibly owns."

Set South to `Human`, the other three to `Extern`, and Q-Plus
plays one seat with no knowledge of the other three hands except
for the bids and cards keyed in by hand. This is how the
1990s-era computer-bridge events worked before WBridge5
standardised the wire format.

### What `Q-NET.EXE` actually is (and isn't)

Easy to confuse with the above; it is NOT the WBridge5 protocol:

* Q-NET implements Q-Plus's INTERNAL networking: two Q-Plus
  instances on two PCs connecting over LAN, or both connecting
  to a central Q-plus server over the internet, so two humans
  can play together (one per PC). Each PC's Q-Plus drives one
  seat, the other Q-Plus drives the other three.
* Transport: TCP/IP, DDE (Dynamic Data Exchange — the Windows
  IPC channel between `QBRIDGE.EXE` and `Q-NET.EXE` on the same
  PC), and historically modem. Strings include
  `<---> TCP/IP client [ %s ] connected (slot %d)`,
  `DDE_CMD_CONNECT`, `MODEM : not connected`.
* The wire format is proprietary to Q-Plus and NOT the BlueChip
  TableManager protocol.
* Exposed via `Network → Start bridge server on this PC` /
  `Connect to local bridge server` / `Connect to Q-plus bridge
  server`. Useful for human-vs-human, not for competition-style
  program-vs-program.

In summary: Q-NET is for two Q-Pluses to play with each other;
the BlueChip / WB_1 mechanism is for one Q-Plus to play one seat
in a wider computer-bridge tournament driven by an external
TableManager. The same `QBRIDGE.EXE` binary has both, with very
different intended uses.

## Created: January 2025
