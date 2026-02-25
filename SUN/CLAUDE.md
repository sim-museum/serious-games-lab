# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides scripts to set up and run KataGo with Human SL (Supervised Learning) models for playing Go at human-like skill levels (20k to 9d). It downloads KataGo, models, and Go GUIs (Sabaki, LizGoban), then configures them to work together.

## Key Commands

### Initial Setup (run once)
```bash
./setup_katago_humansl_and_guis.sh
```
Downloads KataGo 1.15.3, Human SL model, strong model, Sabaki, Kaya, and LizGoban.

### Configure Human Opponent Rating
```bash
./configure_human_opponent.sh
```
Interactive script that prompts for a rating (e.g., `5k`, `3d`), then:
- Creates `katago/gtp_human_rank_<rating>.cfg`
- Creates `run_katago_human_rank_<rating>.sh` helper script
- Auto-configures LizGoban's `gui/lizgoban/external/config.json`

### Launch GUIs
```bash
./run_human_like_go_gui.sh
```
Menu to launch Sabaki or LizGoban (Kaya doesn't support Human SL).

### Install KaTrain
```bash
./setup_katrain.sh
./run_katrain.sh
```
Installs KaTrain in a Python venv. Configure KataGo path in Settings > Engine.

## Architecture

### Directory Structure After Setup
- `katago/` - KataGo binary, models (`.bin.gz`), and config files (`.cfg`)
- `gui/Sabaki.AppImage` - Sabaki Go GUI
- `gui/Kaya.AppImage` - Kaya Go GUI (limited Human SL support)
- `gui/lizgoban/` - LizGoban cloned repo (run with `npm start`)
- `run_katago_human_rank_*.sh` - Helper scripts for launching KataGo with specific ratings

### Human SL Profile Naming
KataGo Human SL uses `rank_` prefix for modern/post-AlphaZero style play:
- `rank_20k` through `rank_1k` for kyu ranks
- `rank_1d` through `rank_9d` for dan ranks

### Auto-Setup via `ensure_katago.sh`
All GUI launchers (`run_katrain.sh`, `q5go.sh`, `sabaki.sh`) source `ensure_katago.sh` which idempotently:
1. Downloads KataGo binary (OpenCL, falls back to CPU build)
2. Downloads strong and Human SL models
3. Creates a default 5k rank config if none exists
4. Exports `KATAGO_BIN`, `MAIN_MODEL`, `HUMAN_MODEL`, `DEFAULT_CONFIG`, `ANALYSIS_CFG`

Each launcher then auto-configures its GUI's config file with KataGo engine paths.

### GUI Integration Notes
- **LizGoban**: Auto-configured via `gui/lizgoban/external/config.json`
- **Sabaki**: Auto-configured via `~/.config/Sabaki/settings.json` (engines.list)
- **q5go**: Auto-configured via `~/.config/q5go/q5gorc` (ENGINE entries)
- **KaTrain**: Auto-configured via `~/.katrain/config.json` (engine paths); uses analysis_example.cfg
- **Kaya**: Does not support `-human-model` flag; cannot use Human SL

### KataGo Command Structure
```bash
katago/katago gtp \
  -model katago/main_model.bin.gz \
  -human-model katago/b18c384nbt-humanv0.bin.gz \
  -config katago/gtp_human_rank_<rating>.cfg
```
