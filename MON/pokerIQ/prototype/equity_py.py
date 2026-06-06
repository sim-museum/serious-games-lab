"""Compare JS equity (equity_js.json) against eval7 calc_equity_hidden.

Same scenarios, same iteration count. Monte Carlo is stochastic with different
RNG streams, so we assert agreement within an absolute tolerance (0.01) rather
than exact equality — that's tight enough to catch any logic bug.
"""
import json
import os
import sys
import eval7

HERE = os.path.dirname(os.path.abspath(__file__))
ITER = 50000
TOL = 0.01

def calc_equity_hidden(hero_hand, board, iterations, num_opponents):
    hero_cards = [eval7.Card(s) for s in hero_hand]
    board_cards = [eval7.Card(s) for s in board]
    dead = {str(c) for c in hero_cards} | {str(c) for c in board_cards}
    wins = ties = 0
    for _ in range(iterations):
        d = eval7.Deck()
        d.cards = [c for c in d.cards if str(c) not in dead]
        d.shuffle()
        opp_hands = [d.deal(2) for _ in range(num_opponents)]
        need = 5 - len(board_cards)
        full = board_cards + (d.deal(need) if need > 0 else [])
        hs = eval7.evaluate(hero_cards + full)
        bo = max(eval7.evaluate(o + full) for o in opp_hands)
        if hs > bo: wins += 1
        elif hs == bo: ties += 1
    return (wins + ties / 2) / iterations

rows = json.load(open(os.path.join(HERE, "equity_js.json")))
worst = 0.0
fails = 0
print(f"{'JS':>8} {'eval7':>8} {'Δ':>7}  scenario")
for r in rows:
    hero = r["hero"].split()
    board = r["board"].split() if r["board"] else []
    py = calc_equity_hidden(hero, board, ITER, r["opp"])
    d = abs(py - r["eq"])
    worst = max(worst, d)
    flag = "" if d <= TOL else "  <-- FAIL"
    if d > TOL: fails += 1
    print(f"{r['eq']:8.4f} {py:8.4f} {d:7.4f}  {r['name']}{flag}")
print(f"\nworst Δ = {worst:.4f}  (tol {TOL});  fails: {fails}")
sys.exit(1 if fails else 0)
