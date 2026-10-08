# Self-capture motifs (from the AlphaZero/Kramnik paper)

Source: Tomašev, Paquet, Hassabis, Kramnik, *Assessing Game Balance with AlphaZero: Exploring Alternative Rule Sets in
Chess* (arXiv 2009.04374), §3.4.3 and appendix B.9 (Kramnik's assessment, main lines, games AZ-33 to AZ-44).
Extracted 2026-10-07 for the self-capture census.

**Caveat:** the paper's self-capture variant keeps castling. chessIQ's Kramnik chess has no castling *and* self-capture,
so the frequencies below are a guide, not a target. Several example positions come from games where castling
happened.

## What the paper measured

AlphaZero self-play, about one minute per move:

- 52.5% of games had at least one self-capture, but only 0.7% of all moves were self-captures.
- Pieces self-captured: pawn 86.9%, bishop 5.3%, knight 4.5%, rook 2.3%, queen 1%. The queen self-captures were
  mostly needless moves in already-won positions.
- Openings: "a minor influence" (Kramnik). AlphaZero's 20-move main lines after 1.e4, 1.d4 and 1.c4 contain no self-capture.
  AlphaZero still favours a Berlin setup against 1.e4.
- Middlegames: "aesthetically beautiful motifs", most often as an attacking sacrifice.
- Endgames: "a wide spectrum of otherwise drawish endgame positions" become wins; fortresses break.
- Kramnik's verdict: "simply an improved version of regular chess".

## Motif families

Each family has a working name, what the move does, and the paper's examples. FENs are copied from the paper,
including its sometimes-odd castling fields. "SC" means self-capture.

### 1. File opener (attack)

A rook or queen takes its own pawn to open a file or rank toward the enemy king. This is the most common attacking use.

- Dragon, Kramnik's example: after 1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be3 Bg7 7.f3 O-O 8.Qd2 Nc6
  9.O-O-O d5 10.g4 e5 11.Nxc6 bxc6, White has **Qxh2**, opening the h-file. (The FEN is the position *after* Qxh2.)
  `r1bq1rk1/p4pbp/2p2np1/3pp3/4P1P1/2N1BP2/PPP4Q/2KR1B1R b Kq - 0 1`
- AZ-33: **37…Rxh6** with threats down the h-file, then 38.Qf3 Qh1+.
  `r5k1/1p3p2/p1pnr2p/3p4/PP1P2Pq/3BP3/4QPP1/R1R3K1 b - - 0 1`
- AZ-37: **16.Rxh4**. AlphaZero preferred 15.h4 (provoking …d5) to 15.Rxh2 straight away: the pawn push comes
  first, and the file opens one move later with the rook already on the 4th rank.
  `r1b2bk1/pp3p2/2n1rn2/q2pp1B1/2P4P/P3P3/1PQN1PP1/2KR1B1R w Kq - 0 1`
- AZ-44: White takes its own f2 pawn (the paper doesn't name the capturing piece) to open the f-file against the king.
  `4kb1r/pp1b1ppp/4p3/4P3/3pN3/P5Q1/1qB2PPP/5R1K w - - 0 1`

### 2. Activation from a passive position

Taking your own pawn gives a passive side play: an open file for a rook, a long diagonal for a bishop, or a better
square for a piece.

- AZ-38: **19…Rxa7** opens the a-file. "In classical chess Black would struggle to find a good plan."
  `r2q1rk1/p2nbpp1/5n2/2p4p/2N2B1P/5Q2/P3NPP1/3R1RK1 b - - 0 1`
- AZ-35: **11.Bxg2** develops the bishop on the long diagonal for a pawn, and **11…Rxa6** answers it.
  `r1bqkb1r/2pn1p2/p3pn2/1p2P1B1/2pP4/2N5/PP3PPP/R2QKB1R w KQkq - 1 11`
- AZ-34: **24.Nxa4** takes the a4 pawn to put the knight on an active square, and **24…Nxc6** replies in kind.
  `2kr4/1b2np2/p1p1p3/4P3/Ppp1P3/2N3P1/1P2BP2/2K4R w K - 0 1`

### 3. Tempo counter in the opening

A self-capture gains a tempo on a file the opponent has just weakened. This changes opening evaluations.

- Ruy Lopez, Kramnik's example: 1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Nxe4 6.d4 exd4 7.Re1 f5 8.Nxd4 Qh4 9.g3.
  In classical chess this is much better for White. With self-capture it is equal, because of **…Qxh7**, gaining a
  tempo on the open h-file.
  `r1b1kb1r/1ppp2pp/p1n5/5p2/B2Nn2q/6P1/PPP2P1P/RNBQR1K1 b kq - 0 9`

### 4. Escape through your own army (defence)

A king in check or facing mate takes an adjacent piece of its own to escape. This is the defensive counterpart to
families 1 and 2, and it changes mating patterns.

- AZ-33: after 38…Qh1+, the king **takes on f2** and gets out of check. "In self-capture chess the king can escape by
  capturing its way through its own army."
  `r5k1/1p3p2/p1pn3r/3p4/PP1P2P1/3BPQ2/5PP1/R1R3Kq w - - 0 1`
- AZ-43: Qh7 would be mate in classical chess. In self-capture chess the king **takes its own rook on f8**, and then
  White has to see to its own king.
  `5rk1/1Q6/5b1R/5p2/3PnP2/8/7P/5qBK w - - 0 1`
- AZ-37: from this position, 33.Nxe4 Qd1+ **34.Kxb2**, "avoiding mate". **34…Rxb6+** follows.
  `3r4/p3kpRQ/1p1r4/4p3/2B1b3/P1R3P1/1PKN4/4q3 w - - 0 1`
- AZ-42: two pawns down for the attack, White has threats that "might prove fatal" in classical chess. Black's
  forcing defence ends with **40…Kxg7**, securing the king.
  `2r3rk/p4qpp/1p3p2/2n1n3/4P1R1/4QP2/PB2B2R/7K w - - 0 1`

### 5. King walk through your own pawns (endgame)

In the endgame, the king advances by taking its own pawns. This breaks blockades and fortresses.

- Kramnik's fortress example: a classical fortress becomes "a trivial win". White's king infiltrates via e4 and
  **Kxd5**, or via e2, d3 and **Kxc4**.
  `8/4bk2/3pRp2/p1pP1Pp1/PpP3Pp/1P3K1P/8/8 w - - 0 1`
- AZ-33: **53.Kxe3**, then **Kxd4**. "Unlike in classical chess, White can still play on here."
  `8/5pk1/QPp5/3p4/P2P4/4PK2/5r1r/8 w - - 0 1`

### 6. Promotion by taking your own piece

A pawn on the 7th is blocked by its own piece, or a piece goes in front of it on purpose. The pawn then promotes by
capturing that piece. The paper calls this "a common pattern in endgames in this variation".

- Kramnik's example: a classical "easy draw" becomes "a trivial win": **Bc8**, then **bxc8=Q**.
  `1b6/1P6/8/5B2/3k4/8/6K1/8 w - - 0 1`
- AZ-40: **50.axb7** takes White's own knight, with an immediate threat to promote on b8.
  `R7/1N6/P4b2/6k1/r6p/8/4K3/8 w - - 0 1`
- AZ-39: the bishop goes to b7 via a6 so that **cxb7** can follow. See family 9 for how the threat shaped play.
  `8/pBp3k1/1pP3p1/8/2P2bbp/8/P5P1/R6K w - - 0 34`

### 7. Taking your own piece with check, then winning material back

A self-capture is one step in a forcing sequence, often with check, that wins the material back at once.

- AZ-41: **75…fxe4+** takes Black's own knight. The pawn leaving f5 uncovers check from the rook on f6, and the pawn
  now on e4 attacks the bishop on d3. The paper says self-captures can be "a key part of tactical sequences where material gets immediately recovered".
  `8/1p3p2/2pk1r1p/r2p1p1P/P2PnK2/3BP1P1/2R2P2/1R6 b - - 0 1`

### 8. Escaping a perpetual or a draw

A self-capture changes the position enough to avoid a perpetual check, or to keep playing in a dead-looking ending.

- AZ-36: **45.Kxg2** gives up White's own bishop "in its attempt at avoiding perpetuals". Black answers by taking
  its own bishop too.
  `3k4/1Q4P1/p3p3/1pq5/5b2/P7/6B1/6K1 w - - 0 1`

### 9. The threat of self-capture

No self-capture is played, but the possibility of one decides the moves. This is the hardest family to see, and the
one the census measures with the rule-switch comparison.

- AZ-39: **34.Rc1**. Promoting at once by self-capture fails because Black has …c6, …c5 or …Bxc7. Rc1 deflects the
  bishop from the b8–h2 diagonal: if it leaves, the self-capture on b7 promotes. The game ended 38…Bxh4 39.cxb7, and
  White won.
- AZ-36: in its analysis AlphaZero considered 13.Qd2 Be7 14.Qxg5 b4 15.Na4 **Qxc6**, self-capturing the c6 pawn, and
  played 13.a3 instead. "Potential self-captures factor in the lines that AlphaZero is calculating."
  `r3kb1r/pb1q1p2/2p1pn2/1p4pp/2pPP3/2N3B1/PP2BPPP/R2Q1RK1 w Qkq - 0 1`
- Ruy Lopez (family 3): 9.g3 loses its point because …Qxh7 exists.

## Uses in chessIQ

- **Census classifier tests.** Every FEN above, with the self-capture played from it, is a labelled example. The
  census's automatic motif labels should reproduce these labels before its counts are trusted.
- **Personalities.** Each family suggests a specialist:
  - file opener (families 1 and 3), an attacker;
  - escape artist (family 4), a defender who survives "mates";
  - king walker (family 5) and promoter (family 6), endgame specialists;
  - tactician (families 7 and 8).
- **Lessons and puzzles.** Kramnik's endgame examples (families 5 and 6) are ready-made first lessons: classical
  draws that become wins. They are the clearest "not in Kansas" moments.
- **Openings.** Kramnik and the main lines agree that self-capture barely changes the best opening play. A
  self-capture-flavoured opening repertoire will therefore be sound side lines, such as the Dragon's Qxh2 or the
  h-pawn push followed by Rxh-pawn, not new main lines. The census should check that each one stays near equal.
