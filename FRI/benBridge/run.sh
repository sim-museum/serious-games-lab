#!/bin/bash
# Launch the Ben Bridge AI
cd "$(dirname "$0")"

if [[ ! -d venv ]]; then
    echo "Error: venv not found. Run install_dependencies.sh first."
    exit 1
fi

source venv/bin/activate

# libdds.so needs libboost_thread; ensure ben/bin/ is in library search path
export LD_LIBRARY_PATH="$(pwd)/ben/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

cd ben_bridge
python3 main.py "$@" 2>/dev/null
exit_code=$?

if [[ $exit_code -ne 0 ]]; then
    echo ""
    echo "benBridge exited with error code $exit_code"
    echo "If the engine failed to initialize, check:"
    echo "  - tensorflow: python3 -c 'import tensorflow'"
    echo "  - dds module: python3 -c 'import dds'"
    echo "  - ben module: python3 -c 'import ben'"
    echo ""
    echo "Re-run with verbose output:"
    echo "  cd $(pwd) && python3 main.py 2>&1 | head -50"
fi
