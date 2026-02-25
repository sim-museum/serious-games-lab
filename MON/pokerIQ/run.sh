#!/bin/bash
# Launch Poker IQ trainer
cd "$(dirname "$0")"
source venv/bin/activate
python3 pokerIQ.py "$@"
