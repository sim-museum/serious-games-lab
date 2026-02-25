#!/usr/bin/env bash
# installFlightgear.sh - Delegates to TUE/flightgear/installFlightgear.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$REPO_ROOT/TUE/flightgear/installFlightgear.sh"
