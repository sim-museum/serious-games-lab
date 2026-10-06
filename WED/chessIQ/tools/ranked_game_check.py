"""CM-12 check: one full rated Fischer 10+3 game in the real app (off-screen) against Tasha; the player's side is a
separate engine at 1 s a move. Run with HOME/CHESSIQ_HOME pointing at a scratch directory and QT_QPA_PLATFORM=offscreen."""
import sys, json, os, subprocess
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from chessiq import app as A, rating as R, engine as E
R.Profile("Tester", 1400).save()
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
me = subprocess.Popen([ROOT + '/engine/fairy-stockfish-kramnik'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1, cwd=ROOT)
def send(s): me.stdin.write(s + '\n')
def wait(t):
    for l in me.stdout:
        if l.startswith(t): return l
send('uci'); send('setoption name VariantPath value engine/kramnik.ini'); send('setoption name UCI_Variant value kramnik'); send('isready'); wait('readyok')
qa = QApplication([])
w = A.MainWindow()
w.who.setCurrentIndex(w.who.findData('Tasha'))
w.mode.setCurrentIndex(w.mode.findData('ai')); w.side.setCurrentIndex(w.side.findData('w'))
w.rated_box.setChecked(True); w.tc.setCurrentIndex(1)                         # Fischer 10+3
w.new_game()
print('rated game vs', w.rated['opponent'], w.rated['rating'], '| clock', w.clock.kind, w.clock.args, flush=True)
def tick():
    g = w.game
    if g.over:
        qa.quit(); return
    if g.turn == g.human and w.review is None:
        uci = [E.sqname(h['m'].frm) + E.sqname(h['m'].to) + (h['m'].promo or '') for h in g.history]
        send('position startpos' + (' moves ' + ' '.join(uci) if uci else '')); send('go movetime 1000')
        u = wait('bestmove').split()[1]
        m = next(m for m in g.legal() if E.sqname(m.frm) + E.sqname(m.to) + (m.promo or '') == u)
        w.do_move(m)
    QTimer.singleShot(100, tick)
QTimer.singleShot(500, tick); QTimer.singleShot(3000000, qa.quit)
qa.exec()
g = w.game
prof = json.load(open(os.path.join(os.environ['CHESSIQ_HOME'], 'profile.json')))
print('over:', g.over, '| plies', len(g.history), '| clocks W %.0f s, B %.0f s' % (w.clock.left['w'] / 1000, w.clock.left['b'] / 1000))
print('rating 1400 ->', prof['rating'], '| games', prof['games'], '| note:', w.note)
print('pgn tail:', ' '.join(prof['history'][-1]['pgn'].split())[-80:] if prof['history'] else '-')
w.close(); send('quit')
