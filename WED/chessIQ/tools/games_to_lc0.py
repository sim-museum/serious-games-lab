"""JSONL games (tools/gen_training_data.py) -> the text form read by `lc0 kramnik-convert` (EPIC NN, sprints NN-3/5).
Each ply: move, the engine evaluation for the side to move (x if none), then the policy.
python3 tools/games_to_lc0.py games.jsonl [more.jsonl ...] > games.txt"""
import json
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        for line in f:
            try:
                g = json.loads(line)
            except ValueError:            # a game still being written (the generators append live): skip it
                continue
            out = ["G %d" % g["result"]]
            evals = g.get("eval") or [None] * len(g["moves"])     # older games have no evaluations
            for mv, pol, ev in zip(g["moves"], g["policy"], evals):
                pol = pol or []
                out.append("M %s %s %d %s" % (mv, "x" if ev is None else str(ev), len(pol),
                                              " ".join("%s %.4f" % (m, p) for m, p in pol)))
            out.append("E")
            sys.stdout.write("\n".join(out) + "\n")
