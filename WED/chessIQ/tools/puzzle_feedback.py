"""Fold players' results back into the shipped puzzle ratings. Each machine keeps puzzle_ratings.json beside its
rating profile (chessiq/academy.py): every puzzle's rating there has moved, from the shipped one, with each first
attempt made on that machine. Collect those files after a Serious Games Week and run
python3 tools/puzzle_feedback.py [--write] FILE [FILE ...]
For each puzzle, the shift is the attempt-weighted mean of the machines' shifts, shrunk toward none by SHRINK
attempts' worth of the engines' estimate; puzzles with fewer than MIN_ATTEMPTS first attempts in all are left
alone. Without --write it only prints what would change. Records made against an older shipped rating or another
position are skipped, so folding the same files twice does nothing the second time (they no longer match)."""
import json
import os
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUZZLES = os.path.join(R, "chessiq", "puzzles.json")
MIN_ATTEMPTS = 5
SHRINK = 10


def fold(puzzles, records):
    """New ratings {id: rating} from a list of per-machine record dicts."""
    out = {}
    for p in puzzles:
        rs = [a for adj in records for a in [adj.get(str(p["id"]))]
              if a and a.get("base") == p["rating"] and a.get("fen") == p["fen"]]
        n = sum(a["n"] for a in rs)
        if n < MIN_ATTEMPTS:
            continue
        shift = sum(a["n"] * (a["r"] - p["rating"]) for a in rs) / (n + SHRINK)
        out[p["id"]] = round(p["rating"] + shift)
    return out


def main():
    a = sys.argv[1:]
    write = "--write" in a
    files = [x for x in a if x != "--write"]
    puzzles = json.load(open(PUZZLES))
    new = fold(puzzles, [json.load(open(f)) for f in files])
    for p in puzzles:
        if p["id"] in new and new[p["id"]] != p["rating"]:
            print("puzzle %3d (%s): %d -> %d" % (p["id"], p["kind"], p["rating"], new[p["id"]]))
            p["rating"] = new[p["id"]]
    print("%d of %d puzzles rerated from %d file(s)%s" % (len(new), len(puzzles), len(files),
                                                          "" if write else " (dry run; --write to save)"))
    if write:
        puzzles.sort(key=lambda p: (p["rating"], p["id"]))
        with open(PUZZLES, "w") as f:
            json.dump(puzzles, f, indent=0)


if __name__ == "__main__":
    main()
