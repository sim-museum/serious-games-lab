"""Cross-check JS engine vs eval7 on the same matchups (prototype/pairs.json).

For each pair, JS recorded sign(score_a - score_b) in {-1,0,1}. eval7 must agree
on the winner/loser/tie for the SAME 7-card hands. Any disagreement is a bug in
the JS evaluator's hand ordering.
"""
import json
import os
import sys
import eval7

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "pairs.json")))

def score(cards):
    return eval7.evaluate([eval7.Card(c) for c in cards])

mismatches = 0
ties_js = ties_e7 = 0
for i, r in enumerate(rows):
    sa, sb = score(r["a"]), score(r["b"])
    e7_sign = 1 if sa > sb else (-1 if sa < sb else 0)
    js_sign = r["sign"]
    if e7_sign != js_sign:
        mismatches += 1
        if mismatches <= 10:
            print(f"  MISMATCH #{i}: js={js_sign} eval7={e7_sign}")
            print(f"    a={r['a']}  b={r['b']}")
    ties_js += (js_sign == 0)
    ties_e7 += (e7_sign == 0)

print(f"checked {len(rows)} matchups")
print(f"  ties: js={ties_js}  eval7={ties_e7}")
print(f"  mismatches: {mismatches}")
sys.exit(1 if mismatches else 0)
