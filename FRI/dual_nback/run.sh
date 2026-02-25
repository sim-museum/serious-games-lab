#!/bin/bash
# Launch Dual N-Back trainer
cd "$(dirname "$0")"
source venv/bin/activate
python3 main.py "$@"
