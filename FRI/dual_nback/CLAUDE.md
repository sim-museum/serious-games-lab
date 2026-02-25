# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Setup (first time)
python3 -m venv venv
source venv/bin/activate
pip install PyQt6

# Run
source venv/bin/activate
python main.py
```

Requires `espeak` for audio: `sudo apt install espeak`

## Architecture

Single-file PyQt6 application (`main.py`) with these key components:

- **Settings** (dataclass): Persisted to `~/.config/dual_nback/settings.json`. Holds n-back level, key bindings, trial interval, adaptive thresholds.

- **GameEngine**: Core game logic. Tracks position/letter history, generates trials with ~25% match probability, evaluates responses. Only trials after the first N are scoreable.

- **AudioPlayer**: TTS abstraction. Tries pyttsx3 first, falls back to espeak subprocess. Uses async speech to avoid blocking the UI timer.

- **MainWindow**: Main game UI with 3x3 grid (GridCell widgets), trial timer (QTimer), keyboard input handling. Auto-starts session on launch.

- **SettingsDialog / ResultsDialog**: Modal dialogs for configuration and end-of-session results.

## Game Flow

1. `MainWindow.__init__` schedules `start_session()` after 500ms
2. `start_session()` creates GameEngine, starts trial timer
3. `next_trial()` runs each interval: evaluates previous trial, generates new position+letter, highlights cell, speaks letter
4. User presses A (position match) or L (letter match) during trial
5. After all trials, `end_session()` shows results and applies adaptive difficulty

## Key Bindings

Default: A = position match, L = letter match (configurable in settings)
