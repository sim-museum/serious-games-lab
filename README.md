# Serious Games Lab

Scripts and source code for collaborative development of AI-assisted games on Ubuntu 24.04 LTS. This repository contains launcher scripts, configuration, and original Python/C++ source projects — not game binaries. The games referenced here are open-source or freely available demos that users obtain independently from their respective project sites.

## What This Repository Contains

- **Bash launcher scripts** that configure and launch games via Wine/Lutris/native Linux
- **Python source projects** developed in-house with AI assistance (bridge, poker, chess, math tutoring)
- **Configuration files** for Wine prefixes, joystick mappings, AI difficulty tuning, and replay analysis
- **A curriculum framework** organizing games into a day-of-week training schedule

This is a software development project. No game binaries or installers are distributed through this repository.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/sim-museum/serious-games-lab.git
cd serious-games-lab

# 2. Install system dependencies
sudo ./scripts/install_dependencies.sh

# 3. Launch the game menu
./launcher/main_launcher.sh
```

Games that require external binaries will show as unavailable until you install them yourself into the appropriate day directory.

## Source Projects (Developed Here)

| Project | Language | Description |
|---------|----------|-------------|
| Bridge AI | Python | Neural network bridge bidding and play |
| Math Quiz | Python | AI-assisted math tutoring |
| Dual N-Back | Python/PyQt | Working memory training |
| Chess Opening Repertoire | Python | Opening study tool |
| Poker Evaluator | Python | Hand analysis and equity calculation |

## Day-of-Week Curriculum

Each day focuses on a different domain of strategic thinking:

| Day | Domain | Open-Source / Free Games Used |
|-----|--------|-------------------------------|
| MON | Probability & Game Theory | PokerTH, PokerStove |
| TUE | Spatial Reasoning & Physics | FlightGear, Battle of Britain |
| WED | Pattern Recognition & Planning | SCID, BanksiaGui + lc0, Nibbler |
| THU | Vehicle Dynamics & Telemetry | Speed Dreams, rFactor |
| FRI | Partnership & Communication | bcalc, Tenace, wBridge5 |
| SAT | Systems Management & Procedures | FreeFalcon, Falcon BMS |
| SUN | Territorial Strategy | KaTrain, q5go, Sabaki, Igowin |

## Directory Structure

```
serious-games-lab/
├── launcher/                  # Game launcher system
│   ├── main_launcher.sh       #   Main menu (start here)
│   ├── detect_games.sh        #   CSV-driven game detection
│   └── lib/common.sh          #   Shared variables and helpers
├── scripts/                   # System setup
│   └── install_dependencies.sh
├── filesForLauncher/          # Launcher data
│   └── launcherScripts.csv    #   Day-of-week game schedule
├── MON/ - SUN/                # Day directories
│   ├── *.sh                   #   Launcher scripts (in git)
│   ├── *.py                   #   Source projects (in git)
│   └── DOC/                   #   Reference documentation
└── README.md
```

## Prerequisites

- Ubuntu 24.04 LTS (22.04 may work with minor adjustments)
- ~2GB disk for source projects
- Dedicated GPU recommended for 3D simulations

## How the Launcher Works

1. Reads `filesForLauncher/launcherScripts.csv` for the game schedule
2. Detects which games are available based on installed software
3. Source projects run directly from the repository
4. External games require the user to install them independently
5. Launcher scripts handle Wine prefix configuration, environment setup, and process management

## Portability

All paths within the repository are relative. The entire directory can be moved or copied to another machine — just re-run `scripts/install_dependencies.sh` on the new system.
