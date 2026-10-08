"""The Kramnik Academy (EPIC KS, KS-4): short lessons on what self-capture changes, as Chessmaster's tutorials, each
with positions to solve on the board and a specialist to play afterwards.

Positions come from the AlphaZero/Kramnik paper (docs/SELF_CAPTURE_MOTIFS.md), from strong engine games in the
self-capture census (docs/SELF_CAPTURE_CENSUS.md), and two constructed for beginners. Every solution is checked by
tools/lesson_check.py: a deep Fairy-Stockfish search under Kramnik rules must find it, ahead of every other move by
at least a pawn unless all legal moves are solutions (when the best move wins outright, uncapped scores decide).
Demonstrations (quiz=False) show a position and its idea; their move must be within half a pawn of the best.
Original text throughout."""
from dataclasses import dataclass, field


@dataclass
class Exercise:
    fen: str
    prompt: str
    solutions: list               # UCI moves, any of which solves it
    explain: str                  # shown once solved (or revealed)
    source: str = ""
    quiz: bool = True             # False: a demonstration -- the position and its idea are shown, not asked


@dataclass
class Lesson:
    key: str
    title: str
    level: str                    # Beginner, Intermediate, Advanced
    text: str                     # HTML
    exercises: list = field(default_factory=list)
    opponent: str = ""            # the specialist to play afterwards


LESSONS = [
    Lesson("rules", "Two new rules", "Beginner",
           "<p>Kramnik chess is ordinary chess with two changes:</p>"
           "<ol><li><b>No castling.</b> Your king finds safety by walking, or stays in the centre behind its pawns."
           "</li><li><b>You may capture your own pieces</b>, anything except your own king. The captured piece is "
           "gone, exactly as if the opponent had taken it. The king may take its own pieces too.</li></ol>"
           "<p>That is all. The board, the pieces and every other rule are the same, so the game looks like ordinary "
           "chess, and most moves are ordinary moves. But every so often a self-capture changes everything: a mate "
           "that is not mate, a file that opens in one move, a pawn that promotes through its own piece.</p>"
           "<p>On the board, a self-capture shows as a ring around one of your own pieces when you select the piece "
           "that can take it.</p>",
           [Exercise("6k1/8/8/8/8/8/5PPP/4r1K1 w - - 0 1",
                     "White is in check on the back rank. In ordinary chess this is mate. Here it is not. Find a way "
                     "out.",
                     ["g1f2", "g1g2", "g1h2"],
                     "The king takes one of its own pawns and steps off the back rank. Every one of them works. In "
                     "Kramnik chess, a king surrounded by its own men is not trapped.", "constructed")],
           "Hal"),
    Lesson("escape", "The king escapes through its own army", "Beginner",
           "<p>In ordinary chess, a king boxed in by its own pawns and pieces is a target. In Kramnik chess those "
           "same men are escape squares: the king may take any of them.</p>"
           "<p>This changes attacking and defending. Before you go for mate, check every square next to the enemy "
           "king, <i>including the ones its own pieces stand on</i>. When you are attacked, look for the square your "
           "own piece can give up.</p>",
           [Exercise("r5k1/1p3p2/p1pn3r/3p4/PP1P2P1/3BPQ2/5PP1/R1R3Kq w - - 0 39",
                     "The black queen gives check on h1. In ordinary chess White is mated. Find the escape.",
                     ["g1f2"],
                     "Kxf2: the king takes its own pawn and walks out. From AlphaZero's games in the Kramnik paper.",
                     "paper AZ-33"),
            Exercise("5rk1/7Q/5b1R/5p2/3PnP2/8/7P/5qBK b - - 0 1",
                     "White has just played Qh7+, which would be mate in ordinary chess. Black to move.",
                     ["g8f8"],
                     "Kxf8: the king takes its own rook and escapes. Now White must look after its own king, with the "
                     "black queen on f1.", "paper AZ-43"),
            Exercise("8/3P1p1k/3R4/6R1/p6P/5Pp1/6P1/1r4K1 w - - 1 41",
                     "White is in check from the rook on b1. Every square around the king is covered or occupied. "
                     "Save the game.",
                     ["g1g2"],
                     "Kxg2: the only move. The king takes its own pawn, the one square the black pieces do not "
                     "cover. From a strong engine game in the self-capture census.", "census")],
           "Mirela"),
    Lesson("promotion", "Promotion through your own piece", "Beginner",
           "<p>A pawn on the seventh rank that is blocked can still promote: it may capture <i>diagonally</i> onto "
           "the last rank, and in Kramnik chess what it captures may be its own piece.</p>"
           "<p>So a blocked passed pawn is never quite blocked. Put one of your own pieces on a square diagonally in "
           "front of it, and next move the pawn takes it and becomes a queen. Many endgames that are draws in "
           "ordinary chess are wins here.</p>",
           [Exercise("1b6/1P6/8/5B2/3k4/8/6K1/8 w - - 0 1",
                     "In ordinary chess the black bishop holds this easily: it is a draw. Here White wins, and the "
                     "idea is simple.",
                     ["f5c8"],
                     "Bc8! The bishop stands diagonally in front of the pawn, and next move bxc8=Q. Black cannot stop "
                     "it, so in fact almost any White move wins: Bc8 can always come next. Kramnik's own example from "
                     "the paper.", "paper (Kramnik)", quiz=False),
            Exercise("2B5/bP6/2K5/8/6Pk/8/8/8 w - - 5 57",
                     "White to move and win.",
                     ["b7c8q"],
                     "bxc8=Q: the bishop on c8 was put there for exactly this. (White wins in other ways too, but "
                     "this is the quickest.)", "census", quiz=False)],
           "Ada"),
    Lesson("files", "Opening a file in one move", "Intermediate",
           "<p>In ordinary chess, opening a file means a pawn exchange or a sacrifice, and takes time. In Kramnik "
           "chess a rook or queen can simply take the pawn in front of it.</p>"
           "<p>The typical plan: push a rook's pawn up the board, then take it with the rook and swing the rook "
           "along the rank, or take a pawn in front of the enemy king with your queen. Defenders must remember that "
           "a closed file is only closed while its owner chooses.</p>",
           [Exercise("r5k1/1p3p2/p1pnr2p/3p4/PP1P2Pq/3BP3/4QPP1/R1R3K1 b - - 0 37",
                     "Black to move. The h-file is the road to White's king.",
                     ["e6h6"],
                     "Rxh6: the rook takes its own h-pawn and doubles behind the queen on the h-file. From "
                     "AlphaZero's games; other moves are about as good here, but this is the idea to know.",
                     "paper AZ-33", quiz=False),
            Exercise("2b3kr/q3pp2/1p1p2p1/2pPP3/2P2PBP/2B3n1/r5P1/1RQ2RK1 w - - 0 27",
                     "White to move. Open a line with tempo.",
                     ["c1f4"],
                     "Qxf4: the queen takes its own pawn and joins the attack on the f-file.", "census")],
           "Rosa"),
    Lesson("activation", "Freeing a buried piece", "Intermediate",
           "<p>A bad bishop hemmed in by its own pawns, or a rook with no open file, is a long-term problem in "
           "ordinary chess. In Kramnik chess it can be solved in one move: the piece takes the pawn in its way.</p>"
           "<p>It costs a pawn. It is worth it when the piece comes alive at once: a rook on an open file, a bishop "
           "on a long diagonal.</p>",
           [Exercise("r2q1rk1/p2nbpp1/5n2/2p4p/2N2B1P/5Q2/P3NPP1/3R1RK1 b - - 0 19",
                     "Black is cramped. In ordinary chess Black would struggle for a plan. Find one move that changes "
                     "that.",
                     ["a8a7"],
                     "Rxa7: the rook takes its own pawn and the a-file is open for it. AlphaZero equalised from here. "
                     "(Quieter moves are about as good; this is the idea to know.)",
                     "paper AZ-38", quiz=False),
            Exercise("4r1k1/1q3p2/1p2p1p1/nP2P3/5P1B/4n2P/4N1P1/1QR3K1 w - - 1 35",
                     "White to move.",
                     ["e2f4"],
                     "Nxf4: the knight takes its own pawn and comes into play at once.", "census", quiz=False),
            Exercise("3r4/pp1k2q1/2p2bP1/5p1Q/3Pp3/1BP3R1/PP2KPP1/r7 w - - 4 29",
                     "White to move.",
                     ["g3g6"],
                     "Rxg6: the rook takes its own pawn and lands on the sixth rank.", "census", quiz=False),
            Exercise("5r2/1p4k1/p1bpp3/P1p5/4PP1p/3P1Qbq/1PP1K3/R6R b - - 1 32",
                     "Black to move. The queen on h3 is out of play. Bring it back with force.",
                     ["h3e6"],
                     "...Qxe6: the queen takes its own pawn and is back in the centre at once. Without self-capture "
                     "Black would be more than two pawns worse off.", "census (puzzle)"),
            Exercise("r1b1kr2/pp1nqpb1/2p2npp/4p1N1/4P3/1BN1B3/PPP1QPPP/3RK2R w - - 0 12",
                     "White to move. The knight on g5 is attacked. Where does it go?",
                     ["g5e4"],
                     "Ngxe4: the knight takes its own pawn and lands on a central square, where it hits f6 and d6. "
                     "Without self-capture White would be about two pawns worse off.", "census (puzzle)")],
           "Felix"),
    Lesson("check", "Self-capture with check", "Advanced",
           "<p>Strong players use self-captures as steps in a combination: a piece takes its own man to give check, "
           "or a pawn takes its own piece to uncover a check from behind, and the material comes back a move later."
           "</p><p>When you calculate, include the self-captures. A check you thought impossible may be one move "
           "away.</p>",
           [Exercise("8/1p3p2/2pk1r1p/r2p1p1P/P2PnK2/3BP1P1/2R2P2/1R6 b - - 0 75",
                     "Black to move. Find the check.",
                     ["f5e4"],
                     "fxe4+: the pawn takes its own knight, the rook on f6 gives check, and the pawn now on e4 hits "
                     "the bishop on d3. The material comes straight back.", "paper AZ-41", quiz=False),
            Exercise("2r3k1/7p/p2b2pP/qp1P4/3P2p1/1Qr1R3/P4P1P/4RK2 w - - 0 33",
                     "White to move.",
                     ["b3d5"],
                     "Qxd5+: the queen takes its own pawn, with check.", "census"),
            Exercise("7r/p5k1/b3p3/3pPp2/P1n2P1p/2P2Q1P/1q4BK/6R1 w - - 0 35",
                     "White to move.",
                     ["g1g2"],
                     "Rxg2+: the rook takes its own bishop and gives check down the g-file.", "census")],
           "Corin"),
    Lesson("endgames", "Endgames that change", "Advanced",
           "<p>Self-capture changes endgame theory. A king can walk forward by taking its own pawns, so fortresses "
           "break and blockades dissolve; and a king can take its own pawn to stand in front of an enemy pawn, so "
           "some lost pawn endings become draws.</p>"
           "<p>In every endgame, ask what your king could do if its own pawns were not in the way, because here "
           "they need not be.</p>",
           [Exercise("8/8/8/8/6p1/3k2P1/5K2/8 w - - 15 81",
                     "In ordinary chess White loses this: the g3-pawn falls and Black queens (a deep search finds mate "
                     "in 19 for Black). Here it is a draw.",
                     ["f2g3", "f2g2"],
                     "Kxg3: the king takes its own pawn and stands in front of Black's, a dead draw. White need not "
                     "even hurry: Kg2 and Kxg3 next also holds, and so does almost any king move, because the king "
                     "can always take its own pawn.", "census", quiz=False),
            Exercise("R7/8/2r5/3k2p1/2n3P1/4PK2/8/8 w - - 0 89",
                     "White to move. The king needs to get forward.",
                     ["f3g4"],
                     "Kxg4: the king takes its own pawn and becomes active at once.", "census", quiz=False)],
           "Ada"),
    Lesson("threats", "The quiet threat", "Advanced",
           "<p>Most of what self-capture changes is invisible: it is the move you <i>didn't</i> play because of a "
           "self-capture that never happened. In strong games, the possibility of a self-capture changes the best "
           "move in about one position in twelve in the middlegame, while self-captures are actually played in "
           "fewer than one move in a hundred.</p>"
           "<p>In these positions the best move of ordinary chess is a mistake. Find the move that respects what "
           "both sides could take of their own.</p>",
           [Exercise("4kb1r/1Qp2p2/p4nnp/2q1p1p1/4P3/2P2NNP/PP3PK1/R1B4r w - - 0 19",
                     "Qc8+ looks crushing, and in ordinary chess it would be. Here it is a mistake. Find White's best "
                     "move.",
                     ["c1e3"],
                     "Be3. After Qc8+?, the black king simply takes its own pawn, Kxf7, and is safe, and White has "
                     "lost about two pawns' worth. All from strong engine games in the self-capture census.",
                     "census"),
            Exercise("rn2kb1r/p4ppp/bq1p4/2pn4/Pp6/1Q4P1/1P2PPBP/R1B1K1NR w - - 0 11",
                     "Qxd5 is the natural capture in ordinary chess. Here the other capture is better.",
                     ["g2d5"],
                     "Bxd5. After Qxd5?, Black answers ...Rxa7: the rook takes its own pawn and comes to life, and "
                     "Qxd5 turns out more than a pawn worse than Bxd5.", "census", quiz=False),
            Exercise("r1bq1k1r/2p2ppp/pb6/2pp4/1Q1P4/P1n1BN2/1P3PPP/R4K1R w - - 0 15",
                     "dxc5 is the natural recapture. Here it is a mistake. Find the best move.",
                     ["b4c3"],
                     "Qxc3. After dxc5?, the black knight escapes with ...Nxd5, taking its own pawn, and White is "
                     "more than two pawns worse off than after Qxc3.", "census"),
            Exercise("4r2k/1p1q2b1/6n1/3B2P1/2p1N2p/4Q2P/6K1/3R4 w - - 0 37",
                     "White to move. In ordinary chess Qf3 is the natural move, and the best one. Here it is not.",
                     ["g2g1", "e3g5"],
                     "Kg1, or the self-capture Qxg5, holds. After Qf3?, Black plays ...Nxh4+: the knight takes its own "
                     "pawn with check, and White's position collapses.", "census", quiz=False),
            Exercise("r3kb2/pbp1qprQ/1p3p2/2nPp2p/7N/P1N3P1/1PP2PBP/3R1K1R w - - 4 17",
                     "White's queen is in Black's camp. Qh8, the best move in ordinary chess, looks natural.",
                     ["h7h5"],
                     "Qxh5 is stronger here. After Qh8?, the black queen takes its own pawn, ...Qxf7, and covers "
                     "everything. (The self-capture Qxc2 is nearly as good as Qxh5.)", "census", quiz=False)],
           "Selim"),
]


def by_key():
    return {lesson.key: lesson for lesson in LESSONS}
