# chessIQ

Kramnik's chess variant: **no castling, and you may capture your own pieces** (anything but your own king; a king
may take its own pieces too). It's Wednesday's game in Serious Games Week ([serious-games-week](https://github.com/sim-museum/serious-games-week)).

    ../chessIQ.sh          # or: python3 -m chessiq   (needs python3 and PyQt6)

- **Vs Computer, hotseat, or Computer vs Computer.** Choose your computer opponent by rating and playing style, as in
  Chessmaster. With Chessmaster installed under `../chessmaster`, its 188 personalities are offered (read from your
  installation); otherwise chessIQ's own eight, from 800 to full strength. The opponents play Kramnik chess properly
  and never hand material back. They need the personality engine, built once with `engine/build_engine.sh`
  (Fairy-Stockfish with a self-capture patch); without it, chessIQ's own engine plays at full strength.
- **Opening book** of real grandmaster games in which neither side castled (635 games out of 25,072). Blue marks
  show what the grandmasters played, and he never opens the same way twice running.
- **Network play** (Network menu). Host a game, or join one. With a Serious Games Week matchmaker set up
  (`sgw url http://<matchmaker>:8090`), a hosted game is listed while it waits for an opponent, and the join dialog
  lists open games. Without one, enter the host's address. TCP port 47810 by default.
- Undo, draw offers both ways, resignation, review (⏮ ◀ ▶ ⏭), PGN save and load.

## Lineage and tests
This recasts `../kramnik_chess.html` as a PyQt app. `chessiq/engine.py` is a line-for-line port of the HTML's engine.
`tests/test_parity.py` runs the original JavaScript under node and requires the same legal moves, SAN, evaluation,
perft counts, best move, root score and node count. The port searches ~1.5x slower, so it thinks for 1.8 s where
the HTML thinks for 1.2 s, and reaches the same depth.

    python3 -m unittest tests.test_parity tests.test_game tests.test_net
