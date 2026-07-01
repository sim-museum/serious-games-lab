# bridgeIQ — App Flow UML

State and sequence diagrams for the two main app flows and their variations.
Sources are PlantUML (`*.puml`); rendered PNGs sit beside them.

## Diagrams

| # | File | Type | Flow |
|---|------|------|------|
| 00 | `00_overview_state` | State | How the two flows are entered from the opening screen |
| 01 | `01_whole_game_state` | State | **Whole game** — `GameController.current_phase` machine |
| 02 | `02_whole_game_sequence` | Sequence | **Whole game** — deal → bid → play → score |
| 03 | `03_cardplay_only_state` | State | **Card-play only** — contract set directly, auction skipped |
| 04 | `04_cardplay_only_sequence` | Sequence | **Card-play only** — MiniBridge / Repeat-Deal → play |
| 05 | `05_network_variation_sequence` | Sequence | **Variation** — networked play (biq↔biq lobby; Q-NET deferred) |

## The two flows in one sentence

- **Whole game**: `_on_new_deal()` → `new_deal()` (`phase='bidding'`) → bidding loop
  (`_advance_bidding`, `make_bid`) → `_setup_play()` (`phase='play'`) → play loop
  (`_advance_play`, `play_card`) → `_show_result()` (`phase='finished'`).
- **Card-play only**: skip the auction — `set_contract_direct(contract)` synthesizes a
  one-bid auction, sets declarer/dummy/leader, jumps straight to `phase='play'`; the play
  loop and end-of-hand are identical to the whole game.

## Key code anchors (`ui/main_window.py`)

- `GameController` (phases `idle/bidding/play/waiting_next/finished`): `new_deal` :173,
  `make_bid` :219, `set_contract_direct` :238, `_setup_play` :262, `play_card` :340,
  `advance_to_next_trick` :403, `_review_human_signals` :382.
- `EngineWorker` (QThread): `request_bid` :70, `request_card` :78, `run` :88
  (bid → `native_bidder`; card → `nopeek` by default, else MC/DD).
- Drivers: `_advance_game` :6290, `_advance_bidding` :6320, `_advance_play` :6381,
  `_on_engine_bid` :8013, `_on_engine_card` :8199, `_on_bid_made` :5831,
  `_on_card_played` :5868, `_handle_trick_complete` :6781, `_show_result` :7174.
- Variations: `_maybe_run_minibridge_rounds` :2376, `_maybe_run_one_player_entry` :2162,
  `_on_repeat_deal` :2984, `_start_network_game` :4836.

## Rebuild

```bash
plantuml -tpng docs/uml/*.puml
```
