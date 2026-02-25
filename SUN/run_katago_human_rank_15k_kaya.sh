#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/katago/katago" gtp \
    -model "$SCRIPT_DIR/katago/main_model.bin.gz" \
    -human-model "$SCRIPT_DIR/katago/b18c384nbt-humanv0.bin.gz" \
    -config "$SCRIPT_DIR/katago/gtp_human_rank_15k.cfg"
