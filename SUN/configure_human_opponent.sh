#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATAGO_DIR="$ROOT/katago"
GUI_DIR="$ROOT/gui"
TEMPLATE_CFG="$KATAGO_DIR/gtp_human5k_example.cfg"

KATAGO_BIN="$KATAGO_DIR/katago"
MAIN_MODEL="$KATAGO_DIR/main_model.bin.gz"
HUMAN_MODEL="$KATAGO_DIR/b18c384nbt-humanv0.bin.gz"
LIZGOBAN_DIR="$GUI_DIR/lizgoban"
LIZGOBAN_CONFIG="$LIZGOBAN_DIR/external/config.json"

# Prompt user for rating
echo "Select AI opponent rating:"
echo "  Kyu ranks: 20k, 15k, 10k, 8k, 5k, 3k, 1k"
echo "  Dan ranks: 1d, 3d, 5d, 7d, 9d"
echo ""
read -rp "Enter rating (e.g., 5k or 3d): " USER_RATING

# Normalize input (lowercase, trim whitespace)
USER_RATING=$(echo "$USER_RATING" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

# Map user rating to KataGo Human SL profile (using "rank_" prefix for modern/post-AlphaZero style)
map_rating_to_profile() {
    local rating="$1"
    case "$rating" in
        20k) echo "rank_20k" ;;
        19k) echo "rank_19k" ;;
        18k) echo "rank_18k" ;;
        17k) echo "rank_17k" ;;
        16k) echo "rank_16k" ;;
        15k) echo "rank_15k" ;;
        14k) echo "rank_14k" ;;
        13k) echo "rank_13k" ;;
        12k) echo "rank_12k" ;;
        11k) echo "rank_11k" ;;
        10k) echo "rank_10k" ;;
        9k)  echo "rank_9k" ;;
        8k)  echo "rank_8k" ;;
        7k)  echo "rank_7k" ;;
        6k)  echo "rank_6k" ;;
        5k)  echo "rank_5k" ;;
        4k)  echo "rank_4k" ;;
        3k)  echo "rank_3k" ;;
        2k)  echo "rank_2k" ;;
        1k)  echo "rank_1k" ;;
        1d)  echo "rank_1d" ;;
        2d)  echo "rank_2d" ;;
        3d)  echo "rank_3d" ;;
        4d)  echo "rank_4d" ;;
        5d)  echo "rank_5d" ;;
        6d)  echo "rank_6d" ;;
        7d)  echo "rank_7d" ;;
        8d)  echo "rank_8d" ;;
        9d)  echo "rank_9d" ;;
        *)   echo "rank_3k" ;;  # Default to 3k if unknown
    esac
}

PROFILE=$(map_rating_to_profile "$USER_RATING")
CONFIG_FILE="$KATAGO_DIR/gtp_human_${PROFILE}.cfg"

echo ""
echo "Mapping '$USER_RATING' to Human SL profile: $PROFILE"

# Create per-rating config file from template
if [[ ! -f "$TEMPLATE_CFG" ]]; then
    echo "Error: Template config not found at $TEMPLATE_CFG" >&2
    exit 1
fi

cp "$TEMPLATE_CFG" "$CONFIG_FILE"

# Update humanSLProfile in the config
# The template has: humanSLProfile = preaz_5k
# We replace it with our chosen profile
sed -i "s/^humanSLProfile = .*/humanSLProfile = $PROFILE/" "$CONFIG_FILE"

# Set logDir to an absolute path so KataGo works regardless of CWD
# (Sabaki and other GUIs launch KataGo from their own working directory)
mkdir -p "$KATAGO_DIR/gtp_logs"
sed -i "s|^logDir = .*|logDir = $KATAGO_DIR/gtp_logs|" "$CONFIG_FILE"

echo "Created config file: $CONFIG_FILE"

# Build the engine command
ENGINE_CMD="\"$KATAGO_BIN\" gtp -model \"$MAIN_MODEL\" -human-model \"$HUMAN_MODEL\" -config \"$CONFIG_FILE\""

# Create helper script for Sabaki
HELPER_SCRIPT="$ROOT/run_katago_human_${PROFILE}.sh"

cat > "$HELPER_SCRIPT" << EOF
#!/usr/bin/env bash
exec "$KATAGO_BIN" gtp \\
    -model "$MAIN_MODEL" \\
    -human-model "$HUMAN_MODEL" \\
    -config "$CONFIG_FILE"
EOF
chmod +x "$HELPER_SCRIPT"

echo "Created helper script: $HELPER_SCRIPT"

# Configure LizGoban
if [[ -f "$LIZGOBAN_CONFIG" ]]; then
    cp "$LIZGOBAN_CONFIG" "${LIZGOBAN_CONFIG}.bak"
    echo "Backed up existing LizGoban config to ${LIZGOBAN_CONFIG}.bak"
fi

mkdir -p "$(dirname "$LIZGOBAN_CONFIG")"

cat > "$LIZGOBAN_CONFIG" << EOF
{
    "preset": [
        {
            "label": "KataGo Human ($PROFILE)",
            "engine": [
                "$KATAGO_BIN",
                "gtp",
                "-override-config", "analysisPVLen=50, defaultBoardSize=19",
                "-model", "$MAIN_MODEL",
                "-human-model", "$HUMAN_MODEL",
                "-config", "$CONFIG_FILE"
            ]
        }
    ]
}
EOF

echo "Created LizGoban config: $LIZGOBAN_CONFIG"

# Print summary
echo ""
echo "=============================================="
echo "CONFIGURATION COMPLETE"
echo "=============================================="
echo ""
echo "Selected rating:      $USER_RATING"
echo "Human SL profile:     $PROFILE (modern/post-AlphaZero style)"
echo "Config file:          $CONFIG_FILE"
echo ""
echo "----------------------------------------------"
echo "ENGINE COMMAND (for manual configuration):"
echo "----------------------------------------------"
echo "$ENGINE_CMD"
echo ""
echo "----------------------------------------------"
echo "SABAKI SETUP:"
echo "----------------------------------------------"
echo "1. Open Sabaki"
echo "2. Go to Engines > Manage Engines > Add"
echo ""
echo "   OPTION A (Recommended - use helper script):"
echo "     Path: $HELPER_SCRIPT"
echo "     Arguments: (leave empty)"
echo ""
echo "   OPTION B (manual setup):"
echo "     Path: $KATAGO_BIN"
echo "     Arguments: gtp -model $MAIN_MODEL -human-model $HUMAN_MODEL -config $CONFIG_FILE"
echo ""
echo "   NOTE: Do NOT put the entire command in the Path field!"
echo ""
echo "----------------------------------------------"
echo "KAYA SETUP:"
echo "----------------------------------------------"
echo "NOTE: Kaya's GUI does not support the -human-model flag required"
echo "for Human SL play. Use LizGoban or Sabaki instead."
echo ""
echo "----------------------------------------------"
echo "LIZGOBAN SETUP:"
echo "----------------------------------------------"
echo "LizGoban has been automatically configured."
echo "Start with: cd $LIZGOBAN_DIR && npm start"
echo ""
echo "----------------------------------------------"
echo "HELPER SCRIPT CREATED:"
echo "----------------------------------------------"
echo "  $HELPER_SCRIPT"
echo "=============================================="
