# Self-capture census (2026-10-07)

How often self-captures are played in strong Kramnik-chess games (no castling, self-capture), what they do, and where
the *possibility* of one changes the best move. The motif families are in `SELF_CAPTURE_MOTIFS.md`.

## Findings

1. **Frequency matches AlphaZero.** Fairy-Stockfish self-play: 0.9% of moves, in 71% of games. lc0 t40a1 self-play:
   0.7% of moves, in 61% of games. The paper reports 0.7% and 52.5%. 92–94% of the pieces self-captured are pawns
   (paper: 87%), and no queen was ever self-captured.
2. **Openings barely change, as Kramnik said.** 2–6% of self-captures are played in the first 12 moves, about 60% in
   the middlegame, and 33–40% in the endgame.
3. **Self-captures are played for many reasons.** Fairy-Stockfish's self-captures spread across activation 23%,
   attack 18%, reposition 17%, check 15%, escape 15%, king walk 9%, promotion 2%. lc0's are led by escape, at 35%.
4. **The threat matters far more than the move.** Self-capture is clearly the best move (by 50+ cp) in only 0.6% of
   positions (1.3% of middlegames). Its mere availability changes the best move by 50+ cp in 5.0% (8.3% of
   middlegames, 7.0% of openings, 2.9% of endgames). In the control, where no self-capture can ever happen, the rate
   is 0.9%. For the design, this means most of the "we're not in Kansas" feeling comes from moves both sides choose
   or avoid *because* a self-capture is available, not from self-captures actually played.
5. **A new endgame lesson: self-capture saves lost pawn endings.** In threat examples 5 and 6, deep searches (depth 44,
   4 threads, 20M nodes) find mate for Black in 19 and in 17 moves under ordinary rules, but a draw (0.00) with
   self-capture. Line: 1.Kg2 Ke3 2.Kxg3!, where the king takes its own pawn and blockades Black's. This is the
   defensive mirror of Kramnik's examples, where draws become wins.

## What it led to (EPIC KS)

- The threat finding shaped the design. Specialists choose moves by how much they gain from Kramnik rules, not
  just by self-capturing. The coach warns about ordinary-chess moves that fail here. Post-Game Analysis lists
  those moves as Kansas moments.
- Finding 5 is an Academy demonstration (Endgames that change). The census positions supply most of the lessons'
  and all of the puzzles' positions, each re-checked deeply (`tools/lesson_check.py`, `tools/mine_puzzles.py`).

## Method

- **Games:** 120 Fairy-Stockfish self-play games (300k nodes a move, one thread, about 0.7 s, depth 12+). Also 100 lc0
  t40a1 self-play games (800 nodes a move, CUDA at the 70 W cap). Each game starts from a different grandmaster-book
  opening of 2–12 plies. Made with `tools/uci_match.py --games`, at 135–150 plies per game on average.
- **Self-captures played:** every one, labelled by `tools/selfcapture_census.py`. Its rules reproduce all 17 of the
  paper's labelled examples (`validate`).
- **Rule-switch searches:** every 4th ply from ply 16, 7,124 positions in all. Each was searched by Fairy-Stockfish
  at 200k nodes with self-capture on and off (`census`, 6 workers, 20 minutes). Scores are capped at ±1000 cp, so
  mate-in-N against mate-in-M does not count.
- **Two baselines:**
  - Noise: the same rules with 10% more nodes. The best move changes in 4.5%, and also by 50+ cp in 0.4%.
  - Control: the 425 positions where no self-capture can ever happen. The best move changes in 11.8%, but only 0.9%
    are threats. The two rule settings search differently even when self-capture is irrelevant, so the *differs*
    column is mostly that effect and should not be read as a self-capture effect.
- **Data** (not in the repo): `~/kramnik-nn/census/` holds the games, `out/selfcaptures.jsonl` and
  `out/positions.jsonl` (with the raw scores, before capping, in `positions_raw.jsonl`).

## Caveats

- Motif labels are rule-based, and "reposition" collects plans the rules cannot see. Example positions should be
  checked by eye before they become lessons or puzzles.
- Direct example 2 (`Q2Q4/7k/…`) comes from an lc0 game that reached two white queens against one. It is real but
  odd.
- 800-node lc0 is weaker than the paper's one-minute AlphaZero. Its high escape share may partly reflect weaker attacks
  that leave kings in check more often.

---

Games from `tools/uci_match.py --games`; rule-switch searches at 200000 nodes, one thread.

## Self-captures played

| Source | Games | With a self-capture | Moves | Self-captures | Share of moves |
|---|---|---|---|---|---|
| fsf | 120 | 70.8% | 18164 | 166 | 0.9% |
| lc0 | 100 | 61.0% | 13494 | 95 | 0.7% |

Paper (AlphaZero, about 1 min/move, castling allowed): 52.5% of games, 0.7% of moves.

### Piece self-captured (the victim)

| victim | fsf | lc0 |
|---|---|---|
| p | 94.0% | 91.6% |
| n | 1.8% | 0.0% |
| b | 3.0% | 6.3% |
| r | 1.2% | 2.1% |
| q | 0.0% | 0.0% |

Paper's victims: pawn 86.9%, bishop 5.3%, knight 4.5%, rook 2.3%, queen 1%.

### Phase

| phase | fsf | lc0 |
|---|---|---|
| opening | 1.8% | 6.3% |
| middlegame | 58.4% | 61.1% |
| endgame | 39.8% | 32.6% |

### Motif

| motif | fsf | lc0 |
|---|---|---|
| promotion | 2.4% | 1.1% |
| escape | 15.1% | 34.7% |
| king-walk | 9.0% | 3.2% |
| king-other | 0.6% | 2.1% |
| check | 15.1% | 16.8% |
| attack | 18.1% | 17.9% |
| activation | 22.9% | 16.8% |
| reposition | 16.9% | 7.4% |

## Rule-switch searches

Each sampled position is searched with self-capture on and off. **direct**: the best move is a self-capture worth at least 50 cp over the best play without self-capture. **threat**: the best move is not a self-capture but changes, and the evaluation moves at least 50 cp, because self-captures exist. **differs**: the best move changes by less than that. The noise floor repeats every tenth position with the rules on and 10% more nodes. Scores are capped at +/-1000 cp (a mate counts as 1000). **control**: positions where no self-capture can ever happen; anything other than *same* there is the two rule settings searching differently, not self-capture.

| Phase | Positions | direct | threat | differs | same |
|---|---|---|---|---|---|
| opening | 440 | 0.2% | 7.0% | 38.2% | 54.5% |
| middlegame | 2408 | 1.3% | 8.3% | 26.7% | 63.7% |
| endgame | 4276 | 0.3% | 2.9% | 27.1% | 69.8% |
| all | 7124 | 0.6% | 5.0% | 27.6% | 66.8% |
| control | 425 | 0.0% | 0.9% | 10.8% | 88.2% |

Noise floor (713 positions, same rules, 10% more nodes): best move changes in 4.5%, and also by 50+ cp in 0.4%.

## Example positions (direct, largest gain first, at most three per motif)

| # | Source | Phase | Motif | Move | Gain (cp) | FEN |
|---|---|---|---|---|---|---|
| 1 | lc0 | endgame | escape | Kxg2 | +2000 | `8/3P1p1k/3R4/6R1/p6P/5Pp1/6P1/1r4K1 w - - 1 41` |
| 2 | lc0 | middlegame | escape | Kxg4 | +1932 | `Q2Q4/7k/7q/7K/6P1/8/8/8 w - - 1 73` |
| 3 | fsf | endgame | promotion | bxc8=Q | +631 | `2B5/bP6/2K5/8/6Pk/8/8/8 w - - 5 57` |
| 4 | fsf | middlegame | escape | Kxc2 | +602 | `4r3/5kpp/p2p3n/1ppN1P1q/5Q2/7P/PPP5/R1BK4 w - - 1 23` |
| 5 | lc0 | middlegame | check | Qxd5+ | +551 | `2r3k1/7p/p2b2pP/qp1P4/3P2p1/1Qr1R3/P4P1P/4RK2 w - - 0 33` |
| 6 | lc0 | middlegame | check | Rxg2+ | +532 | `7r/p5k1/b3p3/3pPp2/P1n2P1p/2P2Q1P/1q4BK/6R1 w - - 0 35` |
| 7 | lc0 | endgame | reposition | bxa6 | +527 | `3b4/8/B7/1P3P2/3k3p/5K1P/8/8 w - - 15 77` |
| 8 | fsf | middlegame | attack | Qxf4 | +461 | `2b3kr/q3pp2/1p1p2p1/2pPP3/2P2PBP/2B3n1/r5P1/1RQ2RK1 w - - 0 27` |
| 9 | fsf | endgame | attack | Rxb4 | +332 | `5r2/1p6/6p1/3kb2p/pP2R2P/P3B1P1/4P1K1/8 w - - 1 43` |
| 10 | lc0 | endgame | promotion | fxe8=Q | +315 | `4B3/4bP2/8/1Pk4K/7p/7P/8/8 w - - 5 87` |
| 11 | lc0 | middlegame | reposition | Rhxb3 | +295 | `1k3r2/1pn3r1/1qn1p1Bb/p1ppP2P/2P2P2/PP5R/3BN3/1RQ1K3 w - - 1 31` |
| 12 | lc0 | middlegame | attack | Bxd5 | +289 | `r2q2kr/pp3nb1/6p1/3P3p/2p5/2Nn1BPP/PP1B2K1/R2Q1R2 w - - 0 21` |
| 13 | lc0 | middlegame | check | Qxh5+ | +272 | `3r3r/1p2bk1p/p1q1p3/2p3pP/P5Q1/2N1P3/1P2KP2/3R2R1 w - - 0 23` |
| 14 | lc0 | middlegame | activation | Nxf4 | +218 | `4r1k1/1q3p2/1p2p1p1/nP2P3/5P1B/4n2P/4N1P1/1QR3K1 w - - 1 35` |
| 15 | fsf | middlegame | activation | Rxg6 | +209 | `3r4/pp1k2q1/2p2bP1/5p1Q/3Pp3/1BP3R1/PP2KPP1/r7 w - - 4 29` |
| 16 | lc0 | middlegame | reposition | Rxh4 | +147 | `2r3kr/4Bpb1/3p2p1/p2N3p/2n1n2P/PB5R/2P2PP1/3RK3 w - - 5 25` |
| 17 | lc0 | middlegame | activation | Rxh4 | +122 | `bn1qk2r/5ppp/4p3/1Nb5/2p1n2P/5N2/1PQ1BPP1/2B2K1R w - - 0 15` |
| 18 | fsf | endgame | king-walk | Kxg4 | +81 | `R7/8/2r5/3k2p1/2n3P1/4PK2/8/8 w - - 0 89` |

## Threat examples (largest evaluation change first)

| # | Source | Phase | Best (on) | Best (off) | Change (cp) | FEN |
|---|---|---|---|---|---|---|
| 1 | lc0 | middlegame | Bf1 | h1h8 | -1115 | `r3k3/pb1p1p2/1p3B2/2np4/2B5/PP3P2/6r1/R3K2R w - - 0 23` |
| 2 | lc0 | endgame | Kf3 | d2d6 | -1076 | `8/pp4Rp/4k3/4pN2/4P3/1P6/P2RKn1r/2r5 w - - 0 35` |
| 3 | fsf | endgame | Rd4 | d7h7 | -1036 | `8/3R4/6pk/6Np/7P/4P3/7q/5K2 w - - 40 75` |
| 4 | fsf | middlegame | Qc5 | c7c8 | -1028 | `r4k1r/p1R2pb1/B2q2p1/3b2B1/2Q3pP/2P5/P4KP1/7R w - - 1 27` |
| 5 | fsf | endgame | Kg2 | f2f1 | +1000 | `8/8/8/8/6p1/3k2P1/5K2/8 w - - 15 81` |
| 6 | fsf | endgame | Kf1 | g2f2 | +1000 | `8/8/8/8/2k2p2/5P2/6K1/8 w - - 0 135` |
| 7 | fsf | endgame | Rf7 | g1f1 | +932 | `8/4R3/p1pk4/2r2p2/7P/4P1p1/6P1/6K1 w - - 2 59` |
| 8 | lc0 | middlegame | Be3 | b7c8 | -914 | `4kb1r/1Qp2p2/p4nnp/2q1p1p1/4P3/2P2NNP/PP3PK1/R1B4r w - - 0 19` |
| 9 | lc0 | endgame | Kg2 | c6c8 | -890 | `6kr/5pp1/1pR2n1p/5B1P/4p3/1r4P1/4PP2/5K1R w - - 0 27` |
| 10 | lc0 | endgame | Rf4 | g4g7 | -855 | `8/3k4/3P4/2K5/6R1/8/4b3/8 w - - 39 75` |
