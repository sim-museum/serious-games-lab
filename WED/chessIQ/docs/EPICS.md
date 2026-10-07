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
- **CM calibration re-measure (10-06): the compression is not enough.** At Fischer 1+1 with the compressed mapping,
  labelled 1600 vs 1400 (engine Elo 1558 vs 1442) went **12–0** (target 76%). At real thinking times the engine's
  Elo limiter separates levels far more steeply than any linear correction. Strength needs a different mechanism:
  the first topic for CM's next retrospective (options include a per-level node cap with MultiPV sampling, or
  Maia-style human networks under the Kramnik lc0).
- **NN-3 (10-06): the pipeline is done; the data is being generated** (four processes, toward about a million
  positions).
  - `tools/gen_training_data.py`: Fairy-Stockfish Kramnik self-play from grandmaster book lines plus random moves.
    Each position gets a soft policy target from MultiPV-8 at 10,000 nodes; games end by mate or by the draw rules,
    or are adjudicated by resignation.
  - `lc0 kramnik-convert`, an lc0 mode in the patch: replays each game with lc0's own Kramnik board and writes lc0
    V6 training chunks with lc0's own encoder (classical 112 planes, `fen_only`) and lc0's own policy index.
  - Check, on 50 games (3,745 positions): every record decodes, and for every position the number of legal moves
    equals chessIQ's, the policy sums to 1, and the side to move and the result sign are right.
- **NN-4 (10-06): the network format is proven; training waits for the data.**
  - `nn/lc0net.py` is a PyTorch Leela network (SE-ResNet with lc0's classical heads, WDL) that saves in lc0's
    format (LINEAR16, batch norm folded) and reads V6 records.
  - Check: lc0 and PyTorch compute the same network. On 312 positions, lc0's per-move policy (VerboseMoveStats,
    temperature 1) and root W−L/D differ from PyTorch's by at most 0.067 percentage points and 0.0026. A different
    PyTorch network against the same file differs by 17.8 points (`nn/verify_export.py`).
- **NN-4 (10-06): done (round 1).** `nn/prepare.py` compacts the V6 chunks to about 1.1 KB a position, holding out
  every 20th game; `nn/train.py` trains on the GPU (16 s an epoch for 6x64 on 217k positions) and saves lc0
  weights.
  - Round 1: 216,681 positions from 2,659 games, 11,709 held out from 140 games.
    - After 3 epochs, the network's top move equals Fairy-Stockfish's best in **19.1%** of held-out positions (5.5%
      untrained, about 1 in 30 legal moves). Held-out value loss is 0.89 (1.11 untrained), and the result is
      predicted correctly 69.6% of the time.
    - Ten epochs overfit badly: value loss rose to 2.86, as the network memorised 2.7k game results.
  - The trained network passes the lc0 identity check (0.067 points of policy, 0.0087 of value) and plays legal
    games under the Kramnik lc0.
  - Next round: the generator now stores each position's evaluation, so the value target can blend game result
    with evaluation (Leela's remedy for overfitting), and there will be more games.
- **NN-5 (10-06), in progress.**
  - Round 1 (from scratch, 6x64, 217k positions) is weak: 0/20 against tinygyal (a 2x16 standard-chess network) and
    0/20 against Fairy-Stockfish at 1,000 nodes.
  - Lesson: Kramnik chess is mostly chess, so **fine-tune a strong chess network** rather than train from zero.
    `nn/lc0net.py` now reads Leela networks (LINEAR16, batch norm, convolutional policy head through lc0's 73x64
    map) and writes them back. The batch norm is stored separately, as lc0's own files do: folding before 16-bit
    quantization made a round trip drift by 1.3 points.
    - Check: LD2 read into PyTorch equals LD2 in lc0 (0.073 points of policy, 0.0032 of value), and so does the
      round trip.
  - Round 2 fine-tunes LD2 (10x128, WDL) on 678k positions with a learning rate of 2e-4, 2 epochs, and value targets
    blended 50/50 with Fairy-Stockfish evaluations.
    - Held-out top-move agreement with Fairy-Stockfish: untouched LD2 32.7%, epoch 1 34.4%, epoch 2 35.7%. Policy
      loss 3.00 → 2.36. Value loss is best after epoch 1 (0.66) and back to 0.73 at epoch 2.
    - It passes the lc0 identity check (0.108 / 0.0041).
  - Tools: `tools/uci_match.py` (any two UCI engines, grandmaster openings, chessIQ-validated moves, Elo ± 95%) and
    `nn/make_round.sh` (games → chunks → arrays → train → verify).
- **NN-6 (10-06), part 1: Leela opponents in chessIQ.** `uci_engine.LeelaEngine` plays a personality with the Kramnik
  lc0 and a network. The roster adds "Leela (Kramnik network)" (the newest `engine/nets/kramnik-*.pb.gz`, 800 nodes
  a move; nets are kept out of git) and Maia 1100–1900 from `INSTALL/maia_weights`: human-like play learned from
  rated human games, one node a move. Maia never learned self-capture, so it plays Kramnik chess legally but
  rarely uses it.
  - Checked off-screen with the book off: Maia 1100 plays the beginner's `Ng5` attack on f7, Maia 1900 a sound
    Scandinavian, Leela a gambit line; switching opponents mid-search no longer raises an error.
  - For EPIC CM, the Maia levels are a candidate answer to the strength-calibration problem: their ratings come
    from human games, not from an engine's limiter.

## EPIC CM, retrospective 2 (2026-10-06, before sprints CM-7..CM-12)

### What the first block delivered
- An engine that plays Kramnik chess with Chessmaster's knobs.
- 188 Chessmaster opponents read from the player's own installation, plus chessIQ's own eight, plus (from EPIC NN)
  Leela and Maia 1100–1900.
- Rated play with Chessmaster's arithmetic, and clocks including Fischer 10+3.
- An opening helper built from 25,072 grandmaster games.
- The self-capture drive is gone.

### What did not work, and why
- **Strength does not match the labels.** Fairy-Stockfish's Elo limiter separates levels far more steeply than its
  numbers: 1600 vs 1400 went 12–0 at Fischer 1+1 even after compressing the scale. While opponent ratings are
  wrong, the rated system in CM-4 rates you against fictions. This undermines the epic's core promise, so it comes
  first.
- **Style is real but faint.** Personalities choose differently from the neutral engine in 39–54% of positions, but
  aggregate behaviour (checks, captures) barely separates them.
- The full ranked 10+3 game check from CM-6 is still outstanding.

### Approaches considered for strength
1. **A better formula for the limiter.** Cheap, but the limiter's slope changes with thinking time, so no single
   formula holds; 12–0 shows the size of the error.
2. **A measured ladder.** Strength levels that are easy to control (Fairy-Stockfish node counts, Leela node counts)
   are placed on one scale by matches between neighbours.
3. **Anchor the ladder to people.** The Maia networks learned from rated human games, one per rating band
   (1100–1900). Their labels are human ratings, the scale Chessmaster's numbers mean. A ladder anchored on Maia
   turns "rated 1600" into "plays like the Maia 1600 band" without trusting any engine's limiter.

**Chosen:** 2 + 3. First measure whether the Maia levels keep their order and spacing in Kramnik chess (they learned
ordinary chess). Then place Fairy-Stockfish node levels on that scale, and map each personality's rating to the
engine setting the ladder says plays at that strength. Style knobs stay on the Fairy-Stockfish levels.

### Sprints CM-7..CM-12 (goal, check, stop)
- **CM-7. The Maia ladder in Kramnik chess.** Matches between Maia levels 200 and 400 apart.
  - Check: the stronger side wins, and the measured gap is within the 95% interval of the label gap, or the
    deviation is recorded.
- **CM-8. Engine levels on the ladder.** Find the Fairy-Stockfish node counts (with personality knobs neutral) that
  score about 50% against each Maia anchor; extend above 1900 by Leela/Fairy-Stockfish node doubling and below 1100
  by Maia 1100 plus randomness.
  - Check: a table from rating to engine setting.
- **CM-9. Personalities use the table.** Rating → engine and node count, with the style knobs on top.
  - Check: two personalities 400 apart score within the interval the Elo formula predicts.
- **CM-10. Personality opening books.** Decode Chessmaster's `.OBK` files and use each personality's own book, cut
  at castling.
  - Check: a personality with a distinctive book opens from it.
- **CM-11. Adjourn and resume rated games,** as Chessmaster does, and keep each rated game's PGN in the history.
  - Check: adjourn, restart the app, resume, finish, and the rating changes once.
- **CM-12. The opponent picker and the outstanding check.** A picker dialog that filters by rating and type and
  shows biographies, then one full ranked Fischer 10+3 game against a chosen personality.
- **CM-7 (10-06): done, with a negative result.** In Kramnik chess at one node, the Maia levels are compressed:
  Maia 1500 vs 1100 scored 31/40 (+215 ± 129 for a labelled 400), and 1500 vs 1300 21/40 (+17 ± 108 for 200). A
  Maia network predicts the moves of players in its band; it does not play at that strength, so its labels cannot
  anchor the scale alone.
  - New plan for CM-8: measure rating *differences* on a ladder of controllable levels (Fairy-Stockfish node
    counts, and the Maia levels where they fit), and anchor the top at full engine strength, as Chessmaster's own
    scale is anchored at its strongest personality (Chessmaster, 2724).
  - The Maia opponents stay in the roster as human-like styles, labelled by their training band, not by measured
    strength.
- **CM-10 (10-06): done.** Chessmaster's opening-book format is decoded (`chessiq/cmbook.py`).
  - Format: "BOO!", a count, then 2 bytes a move in a depth-first tree. First byte: bits 0–5 the from-square, bit 6
    clear when a sibling follows the move's subtree, bit 7 end of line. Second byte: bits 0–5 the to-square, bits
    6–7 annotations.
  - Check: all entries of four books (CMX's 285,038 included) are consumed with no illegal move.
  - Each Chessmaster personality now opens from its own book, cut at castling and weighted by the number of book
    lines through each move, then falls back to the grandmaster book. The generic `Depth6.OBK` of weaker
    personalities uses another format and falls back.
  - Check: with Bird's book the computer opens 1.f4 in 24% of 400 games (none with the grandmaster book), matching
    the book's 52 of 219 lines. `tests/test_cmbook.py` uses a synthetic book.
- **CM-11 (10-06): done.** Rated games can be adjourned, as in Chessmaster.
  - Leaving one by starting a new game offers Adjourn, Resign or Cancel; closing the app adjourns it.
  - The next rated game, including the one started at launch, offers to resume it: opponent, moves, clocks and
    stakes are restored.
  - Each recorded result keeps the game's PGN in the history.
  - Check, off-screen: closed after `e4 e5`, so adjourned with the rating untouched; relaunch resumed it (moves and
    White's 603 s restored); resigning changed the rating once (1400 → 1126), stored the PGN and cleared the
    adjourned game.
- **CM-8 (10-06): done.** Strength is now set by search nodes on a measured ladder, not by the engine's Elo limiter.
  - The ladder: 26 matches of 40 games between Fairy-Stockfish node levels from 16 to 65,536, fitted jointly. It
    gives about 195 Elo per doubling of nodes, with a floor below about 45 nodes (`docs/calibration/`).
  - Kramnik chess spreads strength wide: 16 to 65,536 nodes is about 2,140 Elo, which is why the limiter looked so
    steep.
  - Anchor: Maia 1500 placed itself at the same ladder point against 64, 181 and 512 nodes (Elo 324, 336, 353), and
    that point is rating 1500.
  - Resulting levels: 16 nodes 1,163; 128 nodes 1,493; 1,024 nodes 1,983; 4,096 nodes 2,497; 8,192 nodes 2,702.
    Below the 16-node floor, a personality strays from the best move more often (provisional: not yet measured).
- **CM-9 (10-06): done.** Personalities play at `level_for(rating)` with their style knobs on top.
  - Check, through chessIQ's own engine class (`tools/personality_match.py`): 2000 vs 1600 scored 95% (Elo expects
    91%; measured +512 ± 247), and 1700 vs 1500 scored 71% (expects 76%; +158 ± 119). Both are within interval.
    Before the ladder this was 12–0.
- **CM-12 (10-06), part 1: the opponent picker.** A "Choose…" dialog lists all 198 opponents, filters by type
  (Chessmaster, chessIQ's own, neural networks) and rating range, searches name or style ("attacker": 23), and
  shows the biography (read from the player's own Chessmaster files).
- **CM-12 (10-06): done.** The outstanding check from CM-6 now passes (`tools/ranked_game_check.py`): a full rated
  Fischer 10+3 game in the real app against Tasha (1,513, 137 nodes).
  - 63 plies, ending in mate (32.Qxb7#). The clocks follow the increment arithmetic (White 660 s = 600 + 32 × 3 −
    about 36 s used). The rating moved once by the previewed amount (+526, the first provisional game), and the PGN
    is in the history.
  - Noted for later: at fixed node counts the personalities move almost instantly (Tasha used about 2 s in the
    game). A short thinking pause would feel more like a human opponent.
- **NN round 3 (10-06):** LD2 fine-tuned for 1 epoch on all 1.18 million positions, value targets blended 50/50 with
  evaluations. Held-out results: top-move agreement 36.3% (LD2 32.8%), policy loss 2.33 (2.99), value loss 0.649
  (0.745), results 74.3% (72.5%). It passes the lc0 identity check (0.076 / 0.0036) and is now chessIQ's Leela
  network (`engine/nets/kramnik-r3.pb.gz`).

## EPIC NN, retrospective 2 (2026-10-06, before sprints NN-7..NN-12)

### What the first block delivered
- lc0 and Nibbler play Kramnik chess, both proven equal to the perft gold.
- A data pipeline with lc0's own encoder, and 1.24 million positions from Fairy-Stockfish.
- A PyTorch Leela network proven identical inside lc0.
- Fine-tuned networks that beat untouched LD2 on every held-out measure.
- Leela and Maia opponents inside chessIQ.

### What the block taught
- **Transfer beats training from zero** on one GPU. Round 1 (from zero) lost 0/20 to a 2x16 network; fine-tuning
  LD2 starts at 33% top-move agreement and climbs from there.
- **Value overfits quickly:** after one epoch of 0.68 million positions, held-out value loss rises again. Blending
  with evaluations helps; more games help more.
- **Strength is the real measure.** Held-out loss shows the network imitates Fairy-Stockfish better; whether it
  plays better needs matches. CM-8's ladder now gives those matches a rating scale.
- **The CPU is the bottleneck** for lc0 (no CUDA compiler on this machine): a 10x128 network at 400 nodes takes about
  1–2 s a move, so a 30-game match takes about 90 minutes.

### Approaches considered for the next block
1. **More, better distillation data.** Fairy-Stockfish at more nodes, and positions from Leela's own games (so the
   network learns to fix its own mistakes). Cheap and proven.
2. **Self-play reinforcement learning** with lc0's own self-play mode under Kramnik rules. The faithful method, but
   on the CPU a 10x128 network yields roughly 10,000 positions an hour, about 40 times slower than distillation. A
   proof of concept only, unless lc0 runs on the GPU.
3. **lc0 on the GPU.** Without nvcc, the options are CUDA tooling from pip, or lc0's ONNX backends with ONNX
   Runtime's GPU build. Would speed up matches and self-play by about 20 times. Worth one sprint to find out.

### Sprints NN-7..NN-12 (goal, check, stop)
- **NN-7. Measure strength on the ladder.** Rounds 2/3 against LD2, and against Fairy-Stockfish ladder levels to
  give each network a rating. Check: a rating with an interval for round 3, and round 3 vs LD2 head to head.
- **NN-8. Delivery.** A WED launcher that builds and opens the Kramnik Nibbler with lc0 and the newest network, plus
  documentation. Check: a fresh scratch HOME launches it and analyses a position with a self-capture line.
- **NN-9. lc0 on the GPU** (time-boxed to one sprint). Check: an nps comparison, CPU against GPU.
- **NN-10. On-policy data:** Fairy-Stockfish labels on positions from Leela's own games, at more nodes; train
  round 4. Check: round 4 against round 3 head to head.
- **NN-11. Self-play proof of concept:** lc0 self-play under Kramnik rules writing V6 directly, mixed into
  training. Check: the pipeline runs end to end; the improvement is measured, whatever its sign.
- **NN-12. Retrospective and the strongest network delivered** to chessIQ and Nibbler.
- **Fairy-Stockfish broad check (10-06, at the PO's request).** Upstream Fairy-Stockfish cannot express "capture
  anything", and adding it in general would be a major rewrite. chessIQ uses a narrow patch for 8x8 chess only
  (CM-1). To test it beyond the six perft positions, `tests/test_fsf_moves.py` compares its root moves (`go perft
  1`) with chessIQ's legal moves at every ply of 12 random self-capture-rich games.
  - Result: all **1,305 positions agree, 33,612 moves each**. The control, the same engine with self-capture off,
    differs in all 1,305.
  - Caveat: this checks the rules, not strength. Search heuristics written for ordinary chess (exchange evaluation,
    capture ordering) may underrate self-capture tactics.
- **NN-8 (10-06): done.** `WED/kramnikNibbler.sh [game.pgn]` builds the Kramnik lc0 and Nibbler if they are
  missing, uses the newest `engine/nets/kramnik-*` network, and keeps its own Nibbler settings in
  `~/.config/chessiq-kramnik-nibbler` (through XDG_CONFIG_HOME), so the PO's normal Nibbler is untouched. The test
  hook gained `NIBBLER_GOTO_END`.
  - Check, from a fresh scratch HOME, on a position where Fairy-Stockfish prefers a self-capture at 98.6%: Nibbler
    showed the game's final position, and the round-3 network's top line was **Rxe4 (a rook taking its own pawn) at
    96.3%**, principal variation `Rxe4 Qf1 f4 Rg1 Rxg1 Bxg1 Rb4 …`. This also closes NN-2's open point: a principal
    variation containing a self-capture is displayed.
- **NN-9 (10-06): done. lc0 runs on the GPU, about 100 times faster.**
  - `engine/build_lc0_gpu.sh` builds lc0's plain CUDA backend (cuBLAS, no cuDNN) with no system CUDA toolkit. The
    compiler and libraries come from pip into a private environment (`engine/cuda-env`, about 1 GB), pinned to CUDA
    13.2 to match the driver. Two traps on the way: pip mixed a 13.4 compiler front end with a 13.2 assembler, and
    the CCCL headers had to be added.
  - Result, round-3 network on a GTX 1660 Super: CPU (OpenBLAS) about 350 nodes/s, CUDA 21,642, CUDA half precision
    32–37k.
  - The GPU build passes the 1,305-position rules test. `kramnikNibbler.sh` and chessIQ's Leela opponents use it
    when present (wrapper `engine/lc0-kramnik-gpu`), else the CPU build.
  - In Nibbler, on the self-capture position: 817k nodes in 20 s, `Rxe4` still on top with a 16-ply line.
- **NN-7 (10-06): done, with a result that changes the plan.** Three 40-game matches on the GPU build
  (`tools/uci_match.py`, GM openings, seed 11):

  | match (800 lc0 nodes a move)               | score        | Elo           |
  |--------------------------------------------|--------------|---------------|
  | round 3 vs untouched LD2                   | 14.0/40, 35% | −108 ± 113    |
  | round 2 vs untouched LD2                   | 5.5/40, 14%  | −319 ± 156    |
  | LD2 vs Fairy-Stockfish 10,000 nodes (the teacher) | 34.5/40, 86% | **+319 ± 156** |

  - **The student was already stronger than the teacher.** LD2 at 800 nodes beats the Fairy-Stockfish settings that
    generated the training data. Distilling the teacher's choices therefore pulled the network down. Round 3 (half
    its value targets from game results, twice the data) lost less than round 2.
  - The held-out losses measured imitation of Fairy-Stockfish, not strength. Only matches decide.
  - On chessIQ's scale (the CM-8 ladder: 8,192 nodes about 2,700, 11,585 about 2,870), LD2 at 800 nodes is roughly
    3,100 and round 3 roughly 3,000. These are extrapolated, so treat them as rough.
  - **Fixed now:** `kramnikNibbler.sh` uses the strongest measured network, today LD2 (`KRAMNIK_NET` overrides).
    chessIQ's "Leela" opponent keeps round 3: at about 3,000 it is still far above every Chessmaster personality.
  - **Plan change:** NN-10 (on-policy Fairy-Stockfish labels) would still learn from a weaker teacher, so it is
    dropped. NN-10/11 become **self-play from LD2 on the GPU** with lc0's own self-play mode under Kramnik rules. Its
    policy targets come from the network's own 800-node search, which improves on its raw policy, so the teacher
    grows with the student. The check is unchanged: the new network against LD2, head to head.
- **NN-10 (10-06): done. Self-play from LD2 gives the first network stronger than LD2.**
  - `nn/selfplay/`: lc0's own selfplay mode with the Kramnik GPU build (800 visits, Dirichlet noise 0.25/0.3,
    temperature 1 to move 30, resignation at 3%), a checker that replays every game under chessIQ's rules, and a
    training step. Generation 1: 3,000 games in about 95 minutes, 272,690 plies, **0 illegal**, 1.5% of moves
    self-captures.
  - Trained from LD2 for 1 epoch at learning rate 1e-4. Value targets matter:
    - Game results blended 50/50 with search values: held-out value loss **rose** (0.695 → 0.749), and the match
      was equal (20.5/40, +9 ± 108).
    - Search values only, keeping the search's draw probability (new: `prepare.py` stores best_d; the target is W =
      (1+q−d)/2, D = d, L = (1−q−d)/2): held-out value loss against real results **fell** to 0.670.
    - With game results only, about 90 correlated positions share one result, so the value head overfits.
  - **Check: generation 1 vs LD2, 93.5/160 (58.4%), +59 Elo, 95% interval +6 to +116** (40 games seed 11: 24.5;
    120 games seed 23: 69.0). Delivered as `engine/nets/kramnik-sp1.pb.gz`, now the default in `kramnikNibbler.sh`
    and chessIQ's Leela opponent.
- **NN-11 (10-06): done, no measurable gain.** Generation 2: 3,000 self-play games from generation 1 (282,368 plies,
  0 illegal), trained from generation 1 on generations 1 and 2 together (527,105 positions), same recipe.
  **Generation 2 vs generation 1: 82/160 (51%), +9 ± 54 Elo.**
  - The +59 of generation 1 most likely came from adapting a standard-chess network to Kramnik chess. Later loop
    steps are small, as in lc0's own runs (a few Elo per network). Confirming +20 needs about 1,000 games a check.
  - Generation 1 stays the delivered network.
- **NN-12 (10-06): delivery confirmed.** From a fresh HOME, `kramnikNibbler.sh` runs generation 1 on the GPU (900k
  nodes in 23 s). On the self-capture test position it prefers `Rg4` (99.1%) to Fairy-Stockfish's self-capture
  `Rxe4`. That fits a stronger network finding a better move, but it is not proof.

## EPIC NN, retrospective 3 (2026-10-06, end of NN-7..NN-12)
- **Delivered:** lc0 on the GPU without a system CUDA toolkit (about 100 times faster); Nibbler with its own settings
  and the strongest measured network; a checked self-play pipeline; `kramnik-sp1`, +59 Elo (95% +6 to +116) over
  the best standard-chess starting point.
- **Lessons:**
  1. Held-out loss measures imitation, not strength. Every claim in this block came from a match.
  2. Check the teacher first. LD2 already beat the Fairy-Stockfish teacher by +319, so distillation could only hurt.
  3. Value targets from search values with the draw probability, not game results.
  4. Size matches to the effect: 40 games resolve about ±110 Elo, 160 games about ±55.
- **Next block (NN-13..):** run the loop unattended for many generations, with gating by 400-game matches (about 25
  minutes each). Either a 15x192 network distilled from generation 1's self-play, or a larger window with a smaller
  learning rate. Measure every promoted network against LD2, so gains add up visibly.

## EPIC CM, retrospective 3 (2026-10-06, before sprints CM-13..CM-18)
### Where the epic stands
- Done: 188 Chessmaster personalities plus chessIQ's own, rated play with Chessmaster's arithmetic, Fischer 10+3,
  adjourning, the opponent picker, personality opening books, and strength set by a measured node ladder anchored
  on Maia 1500 (2000 vs 1600 and 1700 vs 1500 both within interval). A full rated 10+3 game passes end to end.
- Since then the Leela side has grown: lc0 runs on the GPU, and `kramnik-sp1` beats LD2.

### Gaps against the gold standard (a Chessmaster rated game)
1. **Advice in rated games.** The manual says Ranked Play has "no advice tools are available". chessIQ still shows
   book-move hints on the board and the grandmaster openings panel during a rated game.
2. **54 of the 188 opponents (29%) are rated below the ladder's measured floor** (1,163), down to Stanley at 1.
   Their strength comes from an unmeasured randomness formula.
3. **Opponents move instantly.** At fixed node counts Tasha used about 2 s of a 10-minute game. A Chessmaster
   opponent thinks on its clock.
4. **Style is faint** (retrospective 2): personalities choose differently in 39–54% of positions, but their games
   look alike.

### Approaches considered for the floor
- **Fewer nodes:** no use; the ladder flattens below about 45 nodes.
- **Random move mixing:** the current formula. Each random move costs a lot, so strength falls quickly, but the
  play looks erratic rather than weak.
- **Maia at one node with temperature:** human-like mistakes. But Maia levels are compressed in Kramnik chess
  (CM-7) and every Maia is above 1,100.
- **Chosen:** measure the existing randomness mixing on the ladder. If it reaches the low ratings in a measured way,
  keep it. A more human-looking weakness can come later.

### Sprints CM-13..CM-18 (goal, check, stop)
- **CM-13. No advice in rated games.** No hints, and no grandmaster panel while a rated game is in progress (the
  panel says why). Check: an off-screen test.
- **CM-14. Below the floor, measured.** Place randomness levels under 16 nodes on the ladder with matches, and refit
  `level_for` below 1,163. Check: three or more levels with intervals, and two low-rated personalities matched
  against each other within interval.
- **CM-15. Opponents think on their clock.** A thinking pause drawn from the clock (strength stays set by nodes).
  Check: in a 10+3 game the opponent uses a human-like share of its time and never loses on time.
- **CM-16. Style made visible.** Signature measures per style (attackers: checks and king-zone moves; materialists:
  captures and material balance; defenders: draws, game length), and amplify the knobs until styles separate.
  Check: separated signatures, with rating still within interval after amplifying.
- **CM-17. A neural family on the ladder.** Leela (`kramnik-sp1`) at node counts placed on the ladder, so strong
  human-like opponents have measured ratings. Check: two levels with intervals.
- **CM-18. Retrospective, and a final rated 10+3 game** with all of the above.
- **CM-13 (10-06): done.** A rated game gives no advice, as in Chessmaster's Ranked Play. From the first position
  until the game is recorded, there are no book-move hints on the board, and the openings panel reads "No advice
  during a rated game". Take-backs were already blocked. `tests/test_app_rated.py` runs the real window off-screen:
  an unrated game shows hints and the grandmaster panel, a rated one shows neither. The control, with the check
  disabled, fails.
- **CM-14 (10-06): done. The 54 opponents below the floor now have measured strength.**
  - The old extra-randomness formula had a cliff: r = 99 picked among good lines, while r = 100 played uniformly
    random moves.
  - New model: below the floor the engine keeps 16 nodes, and with probability p plays a uniformly random legal
    move. Fairy-Stockfish's `go perft 1` lists the moves, proven against the rules. A personality's own randomness
    knob keeps its meaning (variety among good moves).
  - Measured (`tools/floor_match.py`; 13 matches of 100 games, neighbours and skip-one, Bradley–Terry with p = 0
    pinned at 1,163): p 0.05 → 992, 0.10 → 920, 0.20 → 758, 0.35 → 499, 0.50 → 226, 0.75 → −87, a random mover
    (p = 1) → −327. Chessmaster's weakest opponent (Stanley, 1) plays at p ≈ 0.68: weak but not random.
  - Check through the normal rating path (`tools/personality_match.py`, 100 games each), both within interval:
    - 900 vs 500 (gap 400): +346 ± 105, 88% (the formula expects 91%).
    - 600 vs 300 (gap 300): +246 ± 86, 80% (expects 85%).
  - Tests: the rate is monotone with no cliff (steps under 0.05 per 25 points), a random mover at the bottom, and
    random picks always legal and varied.
- **CM-15 (10-06): done. Opponents think on their clock.**
  - Strength stays set by nodes. After the search, the app waits up to a player-like time (`think_time` in
    `app.py`): the remaining time over the moves still to play (at least 12), plus three quarters of the increment,
    varied between 0.4x and 1.6x. It never exceeds 8% of what is left. Untimed games: 0.8–3 s. A new game cancels
    the wait.
  - Check, a full rated 10+3 game in the app against Tasha: she used **499 s over 34 moves (about 15 s a move)**
    and finished with 203 s, never near a flag. Before this change: about 2 s for the whole game.
  - Also fixed: the opponent messages said "He declines…" and "his move", although many personalities are women.
    They now use the opponent's name ("Tasha declines your draw offer", "Tasha to move").
- **CM-16 (10-06): done. Style is visible in play; contempt was broken and is fixed; styles cost rating.**
  - `tools/style_signature.py`: a style plays 200 games against a neutral opponent of the same rating (1,900), and
    its moves are counted per 100 (`docs/calibration/style_signatures.txt`). Neutral control: king-zone moves 20.7,
    checks 11.1, material taken 55.0, own material given 3.8, average 129 plies.
    - Attack +80: checks 12.7, given 6.5 (line-opening self-captures), games 99 plies. Scored 33.8%.
    - Attack −80: checks 9.2, zone 17.6, draws 21 against 16. Scored 44.2%.
    - Greedy (enemy material counted double): taken 61.6. Scored 5.2%.
    - No amplification needed. The Chessmaster knobs already span their full ranges, and the inferred attack sign
      is right (all 23 personalities whose style line says "attacker" have positive attack).
  - **Contempt never reached repetition or 50-move draws.** Fairy-Stockfish's search returns the variant framework's
    own draw score at game ends, bypassing the patched `value_draw`.
    - Fixed in `kramnik-selfcapture.patch`: exact draws from `is_game_end` in search and quiescence carry the
      contempt, and the upcoming-repetition shortcut only ever raises alpha.
    - Probe (Black can repeat the start position for the third time; `searchmoves f6g8`, depth 10): the old engine
      scores the repetition 0 at contempt 0 and −300. The new one scores −300 → +182 and takes the draw, and +300 →
      −181 and avoids it.
    - Perft and the 1,305-position rules test still pass.
    - In games at 1,900, contempt still shows little (21–22 draws in 200 at ±300): a choosable repetition seldom
      comes up.
  - **Styles cost rating:** attack +80 about −115 Elo, attack −80 about −40, greedy about −500. Nodes come from the
    rating alone, so a styled opponent plays below its label. CM-17 is re-planned to fix this (the neural family
    moves to a later block).
- **CM-17 (10-06): done. Styles keep their rating.** (Re-planned from "a neural family" after CM-16 showed that styles
  cost rating.)
  - **Randomness is variety, never chaos.** Chessmaster's randomness 100 used to make chessIQ play uniformly random
    moves; two personalities have it, one rated 2,238. Now 100 means half the moves are drawn from the engine's top
    four lines within about two pawns. Weakness below the floor comes only from CM-14's measured blunder rate.
  - **Four lines get four times the nodes.** At a fixed node count, MultiPV 4 split the search and weakened every
    move: randomness 0.21 cost about 315 Elo. Now each listed line gets the full search.
  - **Cost model**, fitted on 16 personalities (`tools/style_cost.py`; anonymous numbers in
    `docs/calibration/style_costs.txt`): cost = 11 × positional + 113 × material + 387 × randomness − 236 ×
    [randomness on] Elo, weighted χ²/dof 0.70. Attack is free. A personality now searches at the nodes for rating +
    its predicted cost (`Personality.effective_rating`).
  - **Check, 6 personalities held out of the fit, compensated, 100 games each against a neutral opponent of their
    rating: 310.5/600 (51.8%), +12 ± 28 Elo.** Individually: +7, +85, +67, −38, −78, +31 (each ± about 70); one is
    just outside its interval, about what chance gives among six. Before compensation, the fit set's costs ran to
    −576.
  - No Chessmaster names or texts are stored: the tool reads the installation at run time and prints only ratings,
    style features and scores.
- **CM-18 (10-06): done. The final rated 10+3 game passes with everything in place** (`CHESSIQ_OPPONENT=Dave
  tools/ranked_game_check.py`).
  - Dave is an attacker rated 1,674 with randomness 62. His predicted style cost of +94 Elo raises his search from
    240 to 365 nodes, over four lines.
  - Mate in 95 plies. No advice was shown, and the rating moved once (+663, the first provisional game). He used 646
    s over 47 moves and finished with 95 s, never flagging.

## EPIC CM, retrospective 4 (2026-10-06, end of CM-13..CM-18)
- **Delivered:**
  - Rated games give no advice.
  - The 54 opponents below the floor have measured strength (a continuous blunder rate in place of a cliff).
  - Opponents think on their clock.
  - Contempt finally reaches repetition and 50-move draws (it never had).
  - Styles are visible in play and keep their rating: a measured cost model paid back in nodes, with a held-out
    check of +12 ± 28.
  - Randomness is variety, never random moves.
- **Lessons:**
  1. A style knob is not free. Every change to the evaluation or the move choice has to be priced in Elo before a
     rating label can mean anything.
  2. A mechanism can carry a hidden cost, as MultiPV did at a fixed node count. Fix the mechanism before modelling
     its symptoms.
  3. An engine probe must keep stdin open. An early end of input answers `bestmove` without searching and fakes a
     result.
  4. Check a game-level null result (contempt "no effect") with a direct probe before believing it.
- **Open:**
  - In long games the thinking pause runs the clock low (95 s left after 47 moves); a gentler curve may feel more
    human.
  - The cost model was fitted at one opponent level per personality and assumes costs add up.
  - Leela and Maia opponents are not yet on the ladder.

## EPIC NN, retrospective 4 (2026-10-06, before sprints NN-13..NN-18)
- **Where it stands:** a Kramnik-trained network (`kramnik-sp1`, 10x128) beats its standard-chess starting point by
  +59 (95% +6 to +116), runs in Nibbler and chessIQ on the GPU, and the self-play loop is proven. A second loop step
  gained nothing measurable (+9 ± 54).
- **Stepping back.** The loop's later steps are small, and a 10x128 network has a low ceiling. Approaches:
  1. *Many more loop generations at 10x128,* gated by 400-game matches. Steady but slow: about 2 hours a
     generation for a few Elo each.
  2. *A larger starting point.* `256x20-t40-1541` (20x256, Leela's T40 run) is on this machine. In ordinary chess it
     is far stronger than LD2, at about eight times the compute per node. If its strength carries into Kramnik
     chess at equal time, one adaptation step from it (as LD2 → sp1) may beat many 10x128 generations.
  3. *Distil the large network into the small one* for speed. Later, if the large one wins.
- **Chosen:** measure 2 first, since it is cheap. If it wins at equal time, adapt it with self-play.
- **Sprints:**
  - **NN-13.** The T40 network in Kramnik chess against sp1, at equal nodes and at equal time. Check: two matches
    with intervals.
  - **NN-14.** The loader and exporter for 20x256 (identity check inside lc0).
  - **NN-15.** One self-play adaptation step from T40. Check: adapted vs untouched T40, 160 games.
  - **NN-16.** The strongest network on chessIQ's rating scale (against the Fairy-Stockfish ladder's top).
  - **NN-17.** Delivery to Nibbler and chessIQ.
  - **NN-18.** Retrospective.
- **NN-13 (10-06): done.** The 20x256 T40 network (`256x20-t40-1541`, untouched) in Kramnik chess against sp1, on
  the GPU, 80 games each. T40 runs at about 8,650 nodes/s, sp1 at 44,900.
  - **Equal nodes (800): T40 66.5/80 (83%), +277 ± 102.** Its standard-chess strength carries over.
  - **Equal time (300 ms a move): T40 36/80 (45%), −35 ± 77, even.** Its per-node advantage is spent on being 5x
    slower on this GPU.
  - Kept as the next base: it is unadapted (LD2 gained +59 from one step), and large networks gain more from
    longer analysis, which is what Nibbler is for.
- **NN-14 (10-06): done.** `LeelaNet` takes the value-head width (32 in LD2, 128 in T40). `load_lc0` reads it, and
  `verify_export.py` infers every shape from the saved weights. Identity checks inside lc0 over 59 positions, for
  the loaded T40 and for its export round trip: largest policy difference 0.065 percentage points, W−L/D 0.0030.
- **NN-15 (10-06): done, with a probable small gain.** T40 self-play: 2,000 games at 400 visits in about 2.5 hours
  (156,972 plies, 0 illegal; untouched T40 self-captures in 5.9% of its moves, against LD2's 1.5%).
  - At sp1's learning rate (1e-4) the adaptation **damaged** the network. Held-out top-move agreement fell (55.9% →
    54.1%), and the result scored **45.5/160 against untouched T40, −160 ± 60.** A 20x256 network with 149,000
    positions drifts too fast at that rate.
  - At a fifth of the rate (2e-5): top-move agreement rose to 58.1%, policy loss fell from 1.846 to 1.739, and it
    passes the identity check.
  - **Adapted vs untouched T40: 176.5/320 (55.2%), +36 Elo, 95% −2 to +75** (seed 51: 88.0/160; seed 53:
    88.5/160). Probably real, but just short of 95%.
  - Saved as `engine/nets/kramnik-t40a1.pb.gz`, not yet the default. NN-16 decides between it and sp1 at an
    analysis-like time.
  - Lesson: scale the learning rate to the network and the data, and treat falling held-out agreement with the
    search's own move as a stop signal before any match.
- **CM open item: thinking pause in long games (10-06, done during a GPU wait).** In a simulated 10+3 game with the
  real `think_time` (20 seeds), the CM-15 curve left 59 s at move 60 and 43 s at move 80, matching Dave's 95 s
  after 47 moves. The cause: the moves-to-go estimate fell to 12, so each pause took a twelfth of what was left.
  Now moves-to-go starts at 50 and never falls below 30, and 60% of the increment is spent (was 75%). Result: about
  13 s a move over moves 1–20, 143 s left at move 60, 91 s at move 80. The unit test plays out 60 moves and requires
  more than 120 s left (the old curve leaves about 60).
- **Leela and Maia opponents at measured ratings (10-07, CM, done during the NN GPU wait).**
  - **Leela at human levels.** At one node, the Kramnik network's first instinct already plays at about 1,960, so
    fewer nodes cannot reach club level. lc0's temperature (sampling from the network's preferences) can. Strength
    collapses past 0.7, because the network's long tail includes ruinous self-captures (1.0 scores 5% against the
    16-node floor, about 650). New opponents, each from 120 games through the app's own `LeelaEngine` against the
    nearest exact ladder point (`tools/leela_levels.py`): **Leela 1910 (temperature 0.3), 1650 (0.5), 1370 (0.6),
    1150 (0.7).**
  - **Maia rated by measurement, not label:** 1100 → 1,219; 1300 → 1,385; 1500 → 1,483 (consistent with the CM-8
    anchor); 1700 → 1,477; 1900 → 1,484. From 1500 up the Maia models play alike in Kramnik chess. Rated games now
    use the measured numbers.
  - **Lesson:** a first pass against distant opponents (scores of 6–29%) put temperature 0.7 at 1,339 and 1.0 at
    1,208, both far too high. Only near-50% scores against close neighbours are trustworthy, as CM-8's ladder
    already assumed.
  - **Fixed:** the Leela opponent picked the alphabetically last network (it had become the experimental 20x256).
    It now uses `kramnik-sp1`, as the Nibbler launcher does. `by_name()` includes the Leela opponents.
  - Data: `docs/calibration/leela_maia_ladder.txt`.
- **Rated 10+3 game against Leela 1370 (10-07):** passes end to end through the app (1 node, temperature 0.6, about
  11 s a move on the clock; mate in 37 plies by the full-strength player side; rating moved once).
  `tools/ranked_game_check.py` handles Leela opponents.
- **NN-16 part 1 (10-07): the adapted T40 against sp1 at 1 s a move: 35/60 (58%), +58 ± 89.** Not significant on
  its own, but consistent with the trend (untouched T40 −35 at 0.3 s; adapting adds +36). `kramnikNibbler.sh` now
  uses `kramnik-t40a1` when the GPU build is present (Nibbler: 152k nodes in 22 s on the self-capture position, both
  top lines winning for Black), and `kramnik-sp1` on the CPU. chessIQ's opponents keep sp1 (fast; their ratings
  were measured with it). `KRAMNIK_NET` overrides.
- **NN-16 (10-07): done.** The strongest network against the strongest engine: **`kramnik-t40a1` (GPU) vs
  full-strength Fairy-Stockfish (Kramnik patch, 2 threads, 256 MB hash), both at 1 s a move: 17.5/40 (44%), −44 ±
  109, even.** The neural network is level with the strongest Kramnik engine on this machine. Both are far beyond
  the ladder's top (65,536 nodes, about 3,300), so there is no honest absolute number. "Champion strength" stays
  unmeasured, since no outside field exists.
- **NN-17: done in NN-16 part 1** (Nibbler uses `kramnik-t40a1` on the GPU and `kramnik-sp1` on the CPU; chessIQ's
  opponents use sp1 with measured club levels).

## EPIC NN, retrospective 5 (2026-10-07, end of NN-13..NN-18)
- **Delivered:**
  - The 20x256 network loads, trains and exports exactly.
  - One self-play adaptation step gives +36 (95% −2 to +75) over untouched T40.
  - At 1 s a move it is +58 ± 89 over sp1 and level with full-strength Fairy-Stockfish.
  - Nibbler picks the network by hardware.
- **Lessons:**
  1. Scale the learning rate to the network: sp1's rate damaged T40 (−160).
  2. Falling held-out agreement with the search's own move is a stop signal before any match.
  3. Compare networks at equal *time*, not equal nodes. +277 at equal nodes became even at equal time.
- **Open, for a later block:**
  - More self-play generations from t40a1. At about 2.5 h each on this GPU, a few Elo per step needs 400-game
    gates.
  - A longer-time reference match (10 s a move) to see whether the network's lead grows with time.
  - Distilling t40a1 into a 10x128 network for CPU-only machines.

## EPIC CM, retrospective 5 (2026-10-07, before sprints CM-19..CM-24)
- **The epic's original promise is met:**
  - Chessmaster's opponents, styles and ratings, all measured.
  - Rated play at Fischer 10+3, with no advice.
  - Adjourning, the opening helper, clocks, and Kramnik rules throughout.
  - Club-level Leela and Maia opponents with measured ratings.
- **Gold-standard gaps left (manual):**
  1. **Post-Game Analysis.** After each game Chessmaster summarises it: a type (*Dominated*: the winner never lost
     the advantage; *Blunder*: one blunder decided it; *Balanced*: more than 40% of the game was about even;
     *Disputed*: the advantage went to both sides), the opening, a suggested next opponent, the rating change, and
     a chart of the evaluation after each move. This is the most useful missing piece for a club player learning
     the variant.
  2. **Tournaments.** Round robin or Swiss against personalities, rated or not, with a schedule, standings and a
     crosstable, and quick results for computer-vs-computer games.
  3. **Rating history.** A record of how your rating moved over time.
- **Approaches for analysis:**
  - Leela gives the best judgement, but it needs the GPU for speed and is busy there with NN work.
  - Fairy-Stockfish at a fixed node count per position is fast on the CPU and deterministic.
  - **Chosen:** Fairy-Stockfish for the chart and classification (one engine, testable thresholds). The Nibbler
    launcher remains the place for deep analysis.
- **Sprints:**
  - **CM-19.** Post-game analysis core: per-move evaluation, the four game types (thresholds stated, since the
    manual gives none), opening line, suggested opponent. Check: unit tests on constructed evaluation sequences,
    plus a real game.
  - **CM-20.** Post-game window with the game chart. Check: an off-screen test after a game.
  - **CM-21.** Tournament core: round robin and Swiss pairings, scoring, tie-breaks, quick results for engine
    games. Check: pairing tests (no repeat pairings in Swiss; everyone meets in round robin).
  - **CM-22.** Tournament window: schedule, play your game, standings and crosstable, optional rating. Check: an
    off-screen tournament.
  - **CM-23.** Rating history graph.
  - **CM-24.** Retrospective and an end-to-end check.
- **CM-19 (10-07): done. Post-game analysis core** (`chessiq/analysis.py`).
  - Fairy-Stockfish evaluates every position at a fixed search, so the same game always reads the same.
  - The manual's four types with stated thresholds (the manual gives none): advantage 100 cp, about even 50 cp,
    blunder 300 cp. Precedence: Blunder, Dominated, Disputed, Balanced. A Blunder must be the loser's move from a
    roughly level position that never recovers.
  - The costliest moves, measured only while the game was undecided (evaluations clipped at ten pawns). Before the
    clip, a move in a lost position that allowed mate read as −74.9.
  - How long the game followed grandmaster games, and a suggested next opponent: about 100 points stronger after a
    win, weaker after a loss, the same level after a draw.
  - Tests: constructed sequences for each type, the winner's own blunder (not the cause), moves in a decided game,
    the suggestion rule, and a real decisive engine game. Example: "Rated-1700 won in 45 moves. Game type:
    Dominated. Costliest moves: 30... Rb5 (−4.0). Opening: followed grandmaster games for 3 plies."
- **CM-20 (10-07): done. The Post-Game Analysis window** (`chessiq/postgame.py`), shown after every game against the
  computer.
  - Contents: the game type and summary, your rating change for rated games, the costliest moves, how far the game
    followed grandmaster practice, a chart of the evaluation after each move (hover for the move and the value;
    above the line is good for White), and "Play <suggested opponent>".
  - Non-modal: it never blocks the board. The analysis runs in a thread with progress, and closing the window (or
    the main window) cancels it and waits for the thread. `CHESSIQ_POSTGAME=0` turns it off.
  - Off-screen test: play a move, the computer replies, resign. The window is non-modal, evaluates every position,
    shows the type, and suggests a weaker opponent after the loss.
  - The rated-game check still completes (against Leela 1150).
  - Tidied on the way: engine pipes are closed explicitly, so a dead engine's pipe is not flushed by the garbage
    collector, and `.CMP` files are read with `with`. The full suite (60 tests) passes.
- **CM-21 (10-07): done. Tournament core** (`chessiq/tournament.py`), as Chessmaster's Play/Tournaments.
  - Round robin by Berger tables (single or double, with a bye in odd fields) and Swiss: score groups split top
    half against bottom half, no rematches (backtracking), colour balance, and the bye to the lowest-ranked computer
    entrant who has not had one, so you always get to play.
  - Standings: points, then Sonneborn–Berger (round robin) or Buchholz (Swiss), then rating. A crosstable is kept.
  - Computer-vs-computer games are played out by their engines at their own strength. A failed engine scores a
    draw rather than an invented result.
  - Tests:
    - Round robin: everyone meets once (twice in a double), nobody appears twice in a round, colours within one,
      one bye each in an odd field.
    - Swiss over 20 seeds: no rematches and at most one bye. The leaders meet, colours balance, and you never get
      the bye.
    - Sonneborn–Berger against hand-computed values, and a played-out engine game.
- **CM-22 (10-07): done. Tournament windows** (`chessiq/tourney_ui.py`; Tournament menu: New, Resume, Show).
  - **New tournament:** round robin, double round robin or Swiss (3–9 rounds); 3–11 opponents drawn from a rating
    range around yours (widened if too few qualify); the time control for your games; rated or not.
  - **The window** (non-modal) shows:
    - this round's games and results;
    - **Play my game**, which sets up the main board (opponent, colour, clock, rated) and records your result when
      the game ends;
    - **Quick results**, which plays out the computer games with their engines in a thread;
    - **Next round**;
    - standings with tie-breaks and a crosstable, your row highlighted.
  - The event is saved after every result (`tournament.json` beside your profile), and Resume reloads it.
  - A manual New Game unlinks the tournament game, so an unrelated game is never scored as a tournament result.
  - Off-screen test: a whole 4-player round robin through the windows (your games resigned, computer games played
    out), finished, saved and resumed identically.
  - Full suite: 70 tests pass.
- **CM-23 (10-07): done. Rating history** (Rating → Rating history…).
  - A chart of your rating after each rated game, starting from where you began. Provisional games (the first 20)
    are drawn hollow.
  - A table of your rated games, newest first: date, opponent and rating, colour, result, and the change.
  - Test: three recorded games give four chart points, end at the profile's rating, and list three rows, newest
    first. Full suite: 71 tests pass.
- **CM-24 (10-07): done. End to end** (`tools/ranked_game_check.py`, Leela 1150): a rated 10+3 game, then the
  Post-Game Analysis ("admin won in 32 moves. Game type: Dominated. Costliest moves: 28... Rxe6 (−5.7). Opening:
  followed grandmaster games for 10 plies. | Your rating: +153 → 1553. | Suggested opponent: Odile (1655)."), then
  the rating history (two points, one row).
  - Found on the way: the first run showed the analysis stuck at "Analysing the game…". The cause is in the
    script, not the app. The script quit Qt's event loop the moment the game ended, and a worker thread's signal
    sent across that quit is never delivered, even when events are pumped afterwards (reproduced in isolation).
    The app never quits its loop at game end. The check now keeps the loop running until the analysis is in, as a
    player's session does.

## EPIC CM, retrospective 6 (2026-10-07, end of CM-19..CM-24)
- **Delivered:**
  - Chessmaster's Post-Game Analysis: game type, costliest moves, opening, rating change, chart, and suggested
    opponent.
  - Tournaments: round robin, double round robin and Swiss, with quick results, standings, crosstable, and
    save/resume.
  - Rating history.
  - Club-level Leela and Maia opponents with measured ratings (done during a GPU wait).
  - Robustness: a dead engine restarts once, and no stand-in engine ever plays under an opponent's name.
- **Against the gold standard,** what Chessmaster has that chessIQ still lacks: the predefined tournament series
  with hidden events, ladders and simultaneous exhibitions, training courses and mini-games, and opening names.
  The first is content; the rest are outside this epic's scope ("play opponents at measured strength and style,
  rated, at 10+3, under Kramnik rules").
- **Lessons:**
  1. Test a GUI flow the way a player drives it, with the event loop running. A harness that stops the loop can
     invent faults (lost signals) or hide them.
  2. State the thresholds the manual omits (game types) in code and documentation, so they can be argued with.
- **Status:** the epic's stated goal is met and verified end to end. Further CM work is optional polish: predefined
  tournaments, and opening names if a Kramnik-legal naming source can be found.

## EPIC NN, retrospective 6 (2026-10-07, before sprints NN-19..NN-24)
- **Where it stands:** `kramnik-t40a1` (20x256) is level with full-strength Fairy-Stockfish at 1 s a move and is
  Nibbler's default on the GPU. `kramnik-sp1` (10x128) is the CPU network and chessIQ's opponent network. One T40
  self-play generation gave +36 (95% −2 to +75). Generation 2's self-play is running on the GPU now.
- **Stepping back, three directions:**
  1. *Keep climbing* with T40 generations gated by matches. Slow (about 2.5 h of self-play a generation), small
     steps, and needs about 320 games a gate to see +30.
  2. *Bring the strength to CPU-only machines.* Most players will not have the GPU build. T40's self-play data
     (400-visit search targets from a much stronger network) can train the 10x128 network (distillation from a
     stronger teacher, this time genuinely stronger), which is fast on any CPU.
  3. *Measure at analysis length.* Is the network's edge over Fairy-Stockfish larger at 5–10 s a move, where
     Nibbler is used? That is expensive: about 5 hours for 40 games at 5 s.
- **Chosen:** 2 first (it helps every player, and the data already exists), then one generation of 1, then 3 at
  the end if time allows.
- **Sprints:**
  - **NN-19.** Distil T40's self-play into 10x128 (from sp1). Check: against sp1 at equal nodes and at equal CPU
    time.
  - **NN-20.** If it wins, it becomes the CPU and chessIQ network. Check: the club levels (temperature) re-measured,
    since a new network shifts them.
  - **NN-21.** T40 generation 2 trained on generations 1 and 2 at lr 2e-5. Check: 320 games against t40a1.
  - **NN-22.** Promote or keep, by NN-21's result.
  - **NN-23.** A longer-time reference against Fairy-Stockfish, if the GPU is free.
  - **NN-24.** Retrospective.
- **NN-19, attempt 1 (10-07): no gain.** The 10x128 network trained from sp1 on T40 generation 1's self-play
  (149,121 positions with 400-visit T40 search targets; lr 1e-4, 1 epoch, search-value targets). It imitated T40's
  search better (top-1 49.9% → 52.4%, policy loss 1.990 → 1.891), but held-out value loss rose (0.554 → 0.567).
  **Against sp1: 78/160 (49%), −9 ± 54.** Imitation without strength again. Retry once with T40 generations 1 and
  2 together (about 300,000 positions) when generation 2's self-play finishes.
