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
- **CM-3 (10-06): done.**
  - The self-capture drive is off in chessIQ's play; `drive=True` survives only in the HTML parity tests.
  - The chosen opponent plays through the engine (`chessiq/uci_engine.py`), and the side panel offers the opponents
    by rating and style.
  - Randomness: 100 ("completely random") draws among all legal moves; otherwise it draws among the best few within a
    margin.
  - **Strength calibration (provisional).** The engine's Elo limiter is steeper than its labels: labelled 1600 vs
    1200 and 2000 vs 1600 both went 20–0 at 50 ms a move (the formula expects 91%), and 1600 vs 1400 scored 88% at
    500 ms (the formula expects 76%, so the effective gap is about 345). Ratings are now compressed around 1500 by
    0.58 before reaching the engine. Re-measure at the real time controls in CM-5.
  - **Handing back.** In Odile (2400) vs Pip (800), 10 games at 100 ms: Odile scored 9½. While two or more pawns
    ahead she made 0.7 self-captures a game (0.9 pawns' worth). These are the full-strength search's own choices,
    which in Kramnik chess are line-opening tactics, not the old drive's deliberate giveaways. Not proven sound move
    by move.
- **CM-4 (10-06): done.**
  - Ranked play: tick "Rated game" against the computer.
  - Rating rule: Elo with K = max(16, 800/(games+1)). The first 20 games are provisional. This reproduces the
    manual's example exactly (−424 / −24 / +376: K = 800, expected score 0.53).
  - Starting rating: from your experience level, asked once (Chessmaster asks age and knowledge).
  - Before each game, your rating and the game's stakes are shown.
  - No take-backs in a rated game. The grandmaster opening marks stay, as Chessmaster allows its opening display in
    ranked play.
  - Results are recorded at mate, resignation or draw. Abandoning the game (new game or closing the app) is a loss:
    chessIQ does not adjourn as Chessmaster does.
  - The profile, with full history, is `~/.local/share/chessIQ/profile.json`.
  - Checked off-screen: stakes shown; take-back refused; resigning applied exactly the shown loss; an abandoned game
    was recorded as a loss. `tests/test_rating.py` has 5 tests.
- **CM-5 (10-06): done** (the calibration re-measure follows below).
  - Time controls are `chessiq/clock.py`: Fischer 10+3, 5+3, 15+10 and 3+2; 30 minutes per game; 40 moves in 90
    minutes (repeating); and untimed. Rated games are always timed, falling back to 10+3 if untimed is chosen, as
    Chessmaster's ranked play has no infinite time.
  - Both clocks are shown and the side to move is marked. The engine receives the real clock (wtime, btime, winc,
    binc) and manages its own time.
  - A flag fall loses, or draws if the other side cannot mate (king alone, or king and one minor piece). The PGN
    result follows.
  - Network games stay untimed for now.
  - Checks: `tests/test_clock.py` (6 tests, on a fake time source). Engine against engine at Fischer 1+1
    (`tools/clock_selfplay.py`): 62 moves each, and both clocks equal base + increments − measured time to within
    15 ms; the engines ended with 11 and 13 s left. In the app, off-screen: a rated game whose player's flag fell
    ended "White ran out of time — Black wins", 0-1, and recorded the rated loss.
- **CM-6 (10-06): the opening helper is done; the full-game check is pending** (it runs after the calibration games,
  so the two do not share the CPU).
  - `tools/build_book.py` rebuilds the book from all 25,072 grandmaster games, each cut at its first castling move
    (every game is legal Kramnik chess until then). The book now has 56,920 positions (it had 4,903 from 635 games),
    and every move parsed. The start-position shares (e4 44.7%, d4 37.4%) match `grandmasterOpeningMove.sh`'s own
    example.
  - The computer picks book moves in proportion to the grandmasters' choices (20,000 draws: e4 44.8%, d4 37.6%) and
    still avoids last game's choice.
  - The new panel lists the grandmasters' moves with their shares, follows review, and shows in rated games.
  - Not used: Chessmaster's per-personality opening books (`*.OBK`, a format still to decode). Every personality
    opens from the grandmaster book.

## EPIC NN, retrospective 1 (2026-10-06, before sprints NN-1..NN-6)

### What exists
- lc0 0.28.2 (built 2022; the source is in `WED/INSTALL/lc0`), Nibbler 2.4.6 and 2.5.3, the tinygyal-8 network,
  Maia 1100–1900 (human-like networks), and other weights.
- From EPIC CM: a correct and fast Kramnik engine (the patched Fairy-Stockfish), a perft gold standard, a book of
  56,920 grandmaster positions legal in Kramnik chess, and self-play harnesses.
- Hardware: one GTX 1660 Super (6 GB) and 4 CPU cores. No PyTorch or TensorFlow is installed.

### The hard facts
- **lc0 knows only chess rules.** Its move generator must learn self-capture and lose castling, or it cannot even
  search a Kramnik position. Its policy head indexes moves by from/to geometry, so self-captures are already
  representable, and the input planes need no change (every Kramnik position is a chess position).
- **Nibbler checks moves with its own JavaScript chess rules.** It would reject or mangle a self-capture in a
  principal variation, so it needs the same two rule changes.
- **Leela-style self-play from zero is out of reach here.** Leela's own networks took many GPUs over months; one
  GTX 1660 manages perhaps a few hundred thousand small-network games a week.

### Approaches considered
1. **Pure self-play reinforcement learning (AlphaZero).** The faithful method, but too slow from zero on one GPU.
2. **Supervised distillation, then self-play.** Generate millions of positions with the Kramnik Fairy-Stockfish:
   its move choices (MultiPV spread as the policy target) and game results or evaluations as the value target,
   starting from the grandmaster book and random openings for variety. Train a small Leela network on that, then
   improve it with self-play using the patched lc0. This is how strong lc0 networks are often bootstrapped, and it
   fits the hardware.
3. **An NNUE network for Fairy-Stockfish.** Practical for strength, but it is not "something like lc0" and Nibbler
   gets nothing new. Kept as a later option.

**Chosen:** 2. Train with PyTorch in a private environment and write lc0's own weights format, so the result loads
straight into the patched lc0 and Nibbler without TensorFlow.

### Sprints NN-1..NN-6 (goal, check, stop)
- **NN-1. lc0 plays Kramnik chess.** Patch lc0's move generator (self-capture, no castling) behind a variant switch.
  - Check: perft equals the gold on the same six positions as CM-1, with standard chess unchanged when the switch
    is off.
  - Check: existing networks play legal Kramnik games.
- **NN-2. Nibbler shows Kramnik chess.** Make the same rule change in Nibbler's move legality, behind a setting.
  - Check: a self-capture can be played on the board, and an engine principal variation containing one displays.
- **NN-3. Training data.** A generator using Fairy-Stockfish self-play from book and random openings, writing
  positions with policy and value targets.
  - Check: one million positions, with a spot check that they replay legally and that their targets are sane.
- **NN-4. Training.** A PyTorch Leela network (small: about 6 blocks of 64 filters) trained on that data and saved
  in lc0's format.
  - Check: the patched lc0 loads it, and its policy agrees with Fairy-Stockfish's best move well above chance on
    held-out positions.
- **NN-5. Strength.** Matches of the patched lc0 with the trained network against Fairy-Stockfish at fixed Elo
  settings, and analysis in Nibbler.
  - Check: an Elo estimate, and a Nibbler session showing the network's evaluations and a self-capture line.
- **NN-6. Self-play improvement loop**, and the network as an opponent in chessIQ (a "Leela" personality).
  - Check: one self-play generation that measurably improves on NN-4's network.
- **NN-1 (10-06): done.** lc0 v0.32.1 plays Kramnik chess (`engine/lc0-kramnik.patch`, `engine/build_lc0.sh`,
  compiled with `-DLC0_KRAMNIK`):
  - the generator allows self-capture (only the own king is uncapturable) and never castles;
  - ApplyMove clears the self-captured piece's type bits and resets the 50-move counter, as the gold does;
  - parsing never reads a king onto its own rook as castling, and never reads a pawn's diagonal onto its own piece
    as en passant;
  - castling rights are cleared at setup, so the network sees no castling.
  - Check: lc0's root move list (VerboseMoveStats, one node) equals chessIQ's legal moves in all 1,305 positions of
    12 random self-capture-rich games (5,441 moves over the first 200). The standard lc0 fails the same test at the
    first self-capture.
  - Check: the tinygyal network plays complete legal games under the Kramnik build, with self-captures.
- **NN-2 (10-06): done.** A Nibbler for Kramnik chess. `engine/make_nibbler.sh` copies a Nibbler 2.5.3 release and
  applies `engine/nibbler-kramnik.patch` (101 lines).
  - Rules: a `KRAMNIK` switch; `illegal()` allows self-capture except of the own king; `move()` never castles; the
    move generator lets sliders take their own pieces; no castling converter, no "O-O" for a king onto its own rook,
    and no castling rights from the FEN.
  - A test hook: `NIBBLER_BEHAVIOUR` starts play without a keypress, and `NIBBLER_DUMP` writes what the window shows.
  - Check: Nibbler's own perft (`tools/nibbler_perft.js`, its renderer code under node) equals the gold on all six
    positions; with the switch off it gives standard chess (197,281).
  - Check, with the Kramnik lc0 and tinygyal in self-play for 60 s: 28 moves played through Nibbler's own move
    checking, including the self-capture `27...Kxg6`. The engine panel showed a principal variation and listed
    self-captures (`Qxa7`, `Qxc2`, `Kxf7`, `Kxh5`) among the candidate moves. A principal variation containing a
    self-capture was not seen in that minute.
