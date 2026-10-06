# chessIQ epics (PO 2026-10-06)

Two epics, worked alternately, six sprints at a time. Each block of six sprints opens with a retrospective.

- **EPIC CM: chessIQ becomes a Chessmaster for Kramnik chess.** Choose among opponents with different ratings and
  playing styles; rated games that change your rating; Fischer 10+3 if you choose it; Kramnik rules (no castling,
  capture anything but your own king). The engine stops handing material back when it is ahead: a Chessmaster rated
  game is the standard. The grandmaster opening helper (already in chessIQ for no-castle play) stays.
- **EPIC NN: a neural-network engine for Kramnik chess**, trained the Leela (lc0) way and usable from Nibbler.

## EPIC CM, retrospective 1 (2026-10-06, before sprints CM-1..CM-6)

### What exists
- **chessIQ** (PyQt): a line-for-line Python port of `kramnik_chess.html`'s alpha-beta engine (about 1.8 s a move),
  one fixed strength, and the **self-capture drive** (more than two pawns ahead, it plays self-captures to hand
  material back). It also has a grandmaster opening book (635 no-castle games of 25,072), hotseat, self-play,
  network play, undo, draws, review, and PGN.
- **Chessmaster Grandmaster Edition** is installed (`chessmaster/WP`). Its engine is Johan de Koning's The King
  (`TheKing350.exe`).

### What Chessmaster does: the standard to meet (manual + data, read 10-06)
- **188 personalities** (`Data/Personalities/*.CMP`, 3,104 bytes each). Each file holds a 38-integer parameter block,
  an opening book (`*.OBK`), a picture, a one-line style description ("attacker", "prefers material", "direct control
  of center") and a biography. The block, as decoded so far:
  - column 6 is the **rating**, from 1 to 2724: Chessmaster 2724, the historical masters 2700, Dobie 1977, Marie
    1537, Kid 742;
  - column 9 is **strength %** (Kid 22, the masters 100);
  - column 10 is **randomness** (0 to 100);
  - column 12 is the **maximum depth** (Kid 4, everyone else 99), and column 13 the **selective search** (1 to 14);
  - column 14 is **contempt for a draw** (±500; Alekhine +300, Reti −150);
  - columns 8 and 15 are **style** values (±100: attack/defence balance; still to confirm which is which);
  - columns 16–25 are **material values** as percentages (0–200), for own and opponent pieces;
  - columns 26–35 are **positional weights** in own/opponent pairs: centre, mobility, king safety, passed pawns,
    pawn weakness.
- **Training vs Ranked.** Training allows hints, take-backs and the coach. In a ranked game there is no take-back and
  no advice except the coach's opening display, and your rating changes after every game. The first 20 rated games
  are provisional, so the rating moves quickly. Before the game, Chessmaster shows what each result would do to your
  rating ("loss −424, draw −24, win +376"). A new player's starting rating is estimated from age and experience.
- **Time controls:** moves in minutes, seconds per move, minutes per game, **Fischer** (minutes plus seconds added
  per move), infinite, and hourglass. Ranked play drops seconds-per-move and infinite. The two players can have
  separate time controls. There are also handicaps (fewer pieces) and blindfold play.
- **Opponent list:** filter by type, age and rating, with a biography for each.

### Approaches considered for the engine
1. **Weaken chessIQ's Python engine per personality.** Cheapest, but its ceiling is low (Python, about 1.8 s for
   modest depth). It cannot honestly be a 2,700 opponent, and Elo labels would be guesses.
2. **Fairy-Stockfish with a Kramnik variant.** It is strong, and it already has `castling = false`, per-variant piece
   values (middlegame and endgame, which map onto Chessmaster's material percentages), `UCI_Elo` (500–2850) for
   strength, and MultiPV for weighted choice among good moves (randomness and style). It lacks self-capture, which
   needs a patch to its move generator and `do_move`. Its NNUE network was trained on standard chess, but every
   Kramnik position is still a chess position.
3. **A native C engine written for chessIQ**, with Chessmaster's knobs in its evaluation: full control, but the most
   work, and still weaker than Fairy-Stockfish.
4. **EPIC NN's network** is the long-term strong engine, but it is months away and lc0 itself would need the same
   move-generator patch. It is not something to block EPIC CM on.

**Chosen:** 2, with option 1 kept as the fallback when the engine binary is missing. The Fairy-Stockfish patch also
helps EPIC NN: a fast, correct Kramnik move generator and a strong engine to produce opening data and evaluate
candidate networks.

**Rule for data:** Chessmaster's biographies, pictures and names are Ubisoft's. chessIQ is on GitHub, so it reads
them from the player's own installation when present, and otherwise ships a roster of its own.

### Sprints CM-1..CM-6 (goal, check, stop)
- **CM-1. Fairy-Stockfish plays Kramnik chess.** Add a `selfCapture` variant option and a `kramnik` variant.
  - Check: perft at several depths equals chessIQ's own engine (`engine.py`, itself proven equal to the HTML) on the
    start position and at least five tactical positions.
  - Check: a game against itself terminates legally.
  - Stop: perft parity holds.
- **CM-2. Personalities.** A personality model (rating, strength, randomness, depth, contempt, style, material,
  positional, opening book) mapped onto engine settings. Import the parameters from a local Chessmaster
  installation at run time, and ship a default roster.
  - Check: a table of 188 imported personalities, and two contrasting personalities that measurably differ
    (material taken, checks given).
- **CM-3. The self-capture drive goes, and strength is calibrated.**
  - Check: no handing back of material when ahead (counted over self-play).
  - Check: an Elo ladder in which a match between personalities about 400 points apart scores about 90% for the
    stronger one.
- **CM-4. Ranked play.** Your rating, provisional for 20 games, with the win/draw/loss changes shown before the game.
  Ranked play has no take-back and no hints except the opening display. Rating history is kept.
  - Check: unit tests of the rating arithmetic, and a scripted ranked game that updates the stored rating.
- **CM-5. Time controls.** Fischer 10+3 and the others, clocks, loss on time, and engine time management.
  - Check: a 10+3 engine-vs-engine game ends with clocks consistent with the increment arithmetic; a flag fall is
    scored.
- **CM-6. Opening helper and finish.** The grandmaster-move display (the existing no-castle book, extended with the
  installed opening helper) is available in ranked play, as Chessmaster allows. Then the README, tests and a
  release note.
  - Check: the test suite, and one full ranked 10+3 game against a chosen personality.

## Sprint log
- **CM-1 (10-06): done.** Fairy-Stockfish plays Kramnik chess: a `selfCapture` variant option and a `kramnik`
  variant (`engine/`). Perft equals the gold on six positions; with self-capture off the same engine gives standard
  chess and differs everywhere. In self-play every move is legal by chessIQ's rules.
- **CM-2 (10-06): done, with one caveat.**
  - The engine takes Chessmaster's knobs as 22 UCI options, each relative to the engine's own side: five positional
    weights and five material values for each side, contempt (as the value of a draw), and attack. Neutral defaults
    are proven identical to CM-1 (node counts and scores at depth 13 on four positions).
  - `chessiq/personalities.py` reads all 188 Chessmaster personalities from the local installation (none of its
    text enters the repository) and falls back to chessIQ's own roster of eight. The decoding was corrected on the
    way: columns 26–35 are the material values and 16–25 the positional weights.
  - Style is measurable but subtle. Over 120 positions at fixed depth with no Elo limit, each personality chooses a
    different move from the neutral engine in 39–54% of them. Material taken goes the expected way (Tomas, the pawn
    snatcher, captures pawns 10% of the time, Yara the attacker 7%; Alekhine captures more and checks more than
    Evans). Checks did not separate Tomas and Yara, and the aggregate gaps are near what 120 positions can resolve.
  - Open for CM-3: whether the knobs need amplifying to be felt in play.
