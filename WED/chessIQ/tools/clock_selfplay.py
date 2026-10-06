"""Two personalities play on a real chess clock (EPIC CM, sprint CM-5). Each engine gets the clock (wtime/btime/
winc/binc) and manages its own time; every move's thinking time is measured here independently, and at the end the
clock must equal base + moves x increment - time used, for each side.
python3 tools/clock_selfplay.py [base_min] [inc_s] [white] [black]      (from WED/chessIQ; default 1 1)"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from chessiq import clock as C  # noqa: E402
from chessiq import engine as E  # noqa: E402
from chessiq import personalities as P  # noqa: E402
from chessiq.uci_engine import PersonalityEngine  # noqa: E402


def uci_of(m):
    return E.sqname(m.frm) + E.sqname(m.to) + (m.promo or "")


def main():
    base = float(sys.argv[1]) if len(sys.argv) > 1 else 1
    inc = float(sys.argv[2]) if len(sys.argv) > 2 else 1
    by = P.by_name()
    pw = by[sys.argv[3]] if len(sys.argv) > 3 else P.Personality("W", 2850)
    pb = by[sys.argv[4]] if len(sys.argv) > 4 else P.Personality("B", 2850)
    eng = {"w": PersonalityEngine(pw), "b": PersonalityEngine(pb)}
    clk = C.Clock("fischer", (base, inc))
    used = {"w": 0.0, "b": 0.0}
    n = {"w": 0, "b": 0}
    b, turn, ep, moves = E.init_board(), "w", None, []
    clk.start("w")
    result = None
    while result is None:
        legal = E.legal_moves(b, turn, ep)
        if not legal:
            result = ("0-1" if turn == "w" else "1-0") if E.in_check(b, turn) else "1/2 stalemate"
            break
        if E.insufficient_material(b) or len(moves) >= 300:
            result = "1/2"
            break
        t0 = time.monotonic()
        u = eng[turn].choose(moves, clock=clk.uci())
        used[turn] += (time.monotonic() - t0) * 1000
        n[turn] += 1
        if clk.moved(turn):
            result = "flag " + turn
            break
        m = next(m for m in legal if uci_of(m) == u)
        b, ep, turn = E.apply_move(b, m), E.ep_after(m), E.opp(turn)
        moves.append(u)
    clk.stop()
    print("result %s after %d plies (Fischer %g+%g)" % (result, len(moves), base, inc))
    worst = 0.0
    for c in "wb":
        expect = base * 60000 + n[c] * inc * 1000 - used[c]
        worst = max(worst, abs(clk.left[c] - expect))
        print("  %s: %d moves, clock %s, base + increments - measured use = %s (difference %.0f ms), min think %s"
              % (c, n[c], C.fmt(clk.left[c]), C.fmt(expect), clk.left[c] - expect, ""))
    print("clock arithmetic %s (largest difference %.0f ms)" % ("CONSISTENT" if worst < 50 else "INCONSISTENT", worst))
    for e in eng.values():
        e.close()


if __name__ == "__main__":
    main()
