"""KS-5: games between the strong self-capture specialists, for mining more puzzles: they play for the positions
where self-capture matters. Same JSON-lines format as tools/uci_match.py --games, so
tools/selfcapture_census.py and tools/mine_puzzles.py read them unchanged.
python3 tools/specialist_games.py GAMES SEED OUT.jsonl [NAME,NAME,...]   (default field: FIELD)"""
import json
import os
import random
import sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R); sys.path.insert(0, os.path.join(R, "tools"))
from chessiq.personalities import by_name  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402
from uci_match import opening, play  # noqa: E402

FIELD = ["Kestrel", "Selim", "Ada", "Corin"]


class Player:
    def __init__(self, name, seed):
        self.name, self.e = name, PersonalityEngine(by_name()[name], seed=seed)

    def best(self, moves):
        return self.e.choose(moves)


def main():
    games, seed, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    field = sys.argv[4].split(",") if len(sys.argv) > 4 else FIELD
    rnd = random.Random(seed)
    players = {n: Player(n, seed + i) for i, n in enumerate(field)}
    with open(out, "a") as f:
        for g in range(games):
            w, b = rnd.sample(field, 2)
            start = opening(rnd)
            players[w].e.new_game(); players[b].e.new_game()
            moves = []
            r = play(players[w], players[b], start, moves)
            f.write(json.dumps({"white": w, "black": b, "book": len(start), "moves": moves, "result": r}) + "\n")
            f.flush()
    for p in players.values():
        p.e.close()


if __name__ == "__main__":
    main()
