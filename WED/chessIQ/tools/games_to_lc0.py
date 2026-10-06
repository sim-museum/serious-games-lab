"""JSONL games (tools/gen_training_data.py) -> the text form read by `lc0 kramnik-convert` (EPIC NN, sprint NN-3).
python3 tools/games_to_lc0.py games.jsonl [more.jsonl ...] > games.txt"""
import json
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        for line in f:
            g = json.loads(line)
            out = ["G %d" % g["result"]]
            for mv, pol in zip(g["moves"], g["policy"]):
                pol = pol or []
                out.append("M %s %d %s" % (mv, len(pol), " ".join("%s %.4f" % (m, p) for m, p in pol)))
            out.append("E")
            sys.stdout.write("\n".join(out) + "\n")
