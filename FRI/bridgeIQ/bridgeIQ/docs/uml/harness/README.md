# biq Test Harness — UML

Diagrams of the **measurement harness** (biq vs Q-Plus), not the gameplay app.
Purpose: a map you can pick up cold in a month, and the basis for cleaning up the
"click here and there" GUI clutter. Sources are PlantUML; PNGs sit beside them.

## Diagrams

| # | File | Type | What it shows |
|---|------|------|----------------|
| 10 | `10_harness_component` | Component | The whole landscape — both panels, the scripts they spawn (clients, clickers, generators, analyzers), Q-Plus under Wine, and the file artifacts (PBN/BDE, .qss, calibration JSON, logs) |
| 11 | `11_control_panel_activity` | Activity | Control-panel match workflow, **colour-coded for cleanup** (the 3 overlapping start paths, the modes) |
| 12 | `12_control_panel_sequence` | Sequence | One match via the 8-step stepper (canonical path) → export → aggregate |
| 13 | `13_mixed_corpus_activity` | Activity | Mixed-corpus: calibrate → generate → write BDE → run → rollover → verify → reconcile |
| 14 | `14_mixed_corpus_sequence` | Sequence | RunWorker per-deal loop (set systems dialog → next deal → start bidding → autoplay → quiescence) |
| 15 | `15_cleanup_map` | Inventory | **Every control, colour-coded KEEP / CONSOLIDATE / DEMOTE** with the redundancy notes |
| 16 | `16_proposed_layout` | Wireframe (salt) | A proposed simplified panel — one start path, one Mode dropdown, Setup demoted to a menu |

## The two panels

- **`qplus_control_panel.py`** — drives **one** biq-vs-Q-Plus closed-room match
  (launch Q-Plus, server, biq client, deal, autoclicker, aggregate .qss). Single window,
  controls left / output right.
- **`qplus_mixed_corpus.py`** — **generates corpora** (random / system-matrix / slam / grand)
  and drives Q-Plus deal-by-deal with per-deal system pairs, then verifies the BDL/QSS
  against the manifest. Tabbed (Calibration + 4 corpus tabs + Help); `RunWorker` QThread.

## Cleanup summary (see 15 + 16)

Three things make it feel cluttered — all consolidatable without losing capability:

1. **Three ways to start a run** — "Manual startup steps" (Config dialog) is REDUNDANT
   with the 8-step "Startup Procedure" (the code comment even says *"the stepper does
   these"*). Keep the stepper + "Run full session"; drop the manual trio.
2. **Modes live in scattered group-boxes / a sub-dialog** — A/B, Double-Pair, and the
   No-Peek/Whole-System dialog are all run *modes*. Collapse into one **Mode** dropdown.
3. **One-time calibration sits among per-run controls** — server-button / clicker /
   autoplay calibration is setup, not per-run. Move under a **Setup** menu.

These are proposals for discussion — no code changed yet.

## Rebuild

```bash
plantuml -tpng docs/uml/harness/*.puml
```

Gotchas if you edit these: `skinparam` blocks need one property per line; `salt`
wireframes must not be preceded by `title`/`skinparam`; activity text between `:` and
`;` must stay on one line (use `\n`).
