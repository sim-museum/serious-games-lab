"""Replay every self-play game (gameready lines) under chessIQ's rules; count self-captures."""
import sys
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from chessiq import engine as E
games = bad = plies = selfcap = 0
results = {}
for line in open(sys.argv[1]):
    if not line.startswith('gameready') or ' moves ' not in line:
        continue
    games += 1
    res = line.split(' result ')[1].split()[0] if ' result ' in line else '?'
    results[res] = results.get(res, 0) + 1
    b, turn, ep = E.init_board(), 'w', None
    for u in line.split(' moves ')[1].split():
        legal = {E.sqname(m.frm) + E.sqname(m.to) + (m.promo or ''): m for m in E.legal_moves(b, turn, ep)}
        m = legal.get(u)
        if m is None:
            bad += 1; print('illegal', u, 'at ply', plies); break
        selfcap += m.kind == 'self'; plies += 1
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
print('games %d, plies %d, illegal %d, self-captures %d (%.1f%% of moves), results %s' % (games, plies, bad, selfcap, 100 * selfcap / max(1, plies), results))
