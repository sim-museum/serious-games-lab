# bridgeIQ — project overview

A PyQt6 desktop bridge application for Ubuntu 24.04 with a classic table
interface. **bridgeIQ is neural-network-free** — there is no BEN and no
TensorFlow. (That engine was removed; ignore any older note that mentions it.)

> **Canonical engineering notes live in `../bridgeIQ/CLAUDE.md`** — current
> status, the slam-bidding / cardplay history, the Q-NET setup, and the test
> harness. This file is just a short orientation; keep deep notes in CLAUDE.md
> so there is a single source of truth.

## Engine

- **Bidding** — rule-based, system-driven: `backend/native_bidder.py`
  (`NativeBiddingEngine`) over the seven specs in `backend/bidding_systems.py`
  (SAYC, 2/1, Standard Acol, Standard French, Precision90M/90P/70). N/S and E/W
  can run different systems.
- **Opening leads** — `backend/native_lead.py`.
- **Card play** — a no-peek **alpha-mu** engine (`backend/nopeek.py`): DDS on
  belief-sampled hidden layouts with a consistent line across indistinguishable
  samples; never peeks; emits + reads defensive signals (`backend/signals.py`,
  `backend/signal_read.py`). A Monte-Carlo + DDS path (`get_mc_card_play`) also
  exists. Double-dummy via the system `libdds`.
- `engine.py`'s `BridgeEngine` now only loads the DDS solver.

## UI

- `ui/main_window.py` — main window, menus, game control.
- `ui/table_view.py` — the 4-hand table + trick area.
- `ui/teaching_view.py` — the instrumented (teaching / analysis) view; see
  `../bridgeIQ/docs/instrumented_view.md`.
- `ui/dialogs/` — preferences, player config, scoring, deal filter, simulation.

## Run

```bash
cd /home/h/sgl/FRI/bridgeIQ/bridgeIQ
./run.sh            # uses venv/bin/python and sets PYTHONPATH itself
```

## Requirements

Ubuntu 24.04+, Python 3.12+, PyQt6, numpy, `libdds0`. No TensorFlow, no GPU.

## Notable features

Seven bidding systems · instrumented teaching view · defensive signalling ·
closed-room play vs Q-Plus over Q-NET (needs a Q-Plus install + system wine 9) ·
IMP/MP/Rubber scoring · DD analysis · bid simulation · blunder check ·
PBN/BDL/QSS import · keyboard-or-mouse for every command. Preferences include a
Claude Code toggle (off by default) and a Q-Plus availability setting (none by
default). Full guide: `bridgeIQ_README.md`.
