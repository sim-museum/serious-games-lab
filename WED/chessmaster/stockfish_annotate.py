#!/usr/bin/env python3
"""Annotate a PGN file with Stockfish analysis.

Adds evaluation scores and best-move variations to each position.
Outputs an annotated PGN to stdout or an output file.

Usage: stockfish_annotate.py input.pgn [output.pgn] [--depth N] [--engine PATH]
"""

import sys
import os
import argparse
import chess
import chess.pgn
import chess.engine


def annotate_game(game, engine, depth):
    """Add Stockfish evaluations and variations to a game."""
    annotated = game.headers.copy()
    annotated_game = chess.pgn.Game()
    annotated_game.headers = annotated

    board = game.board()
    node = annotated_game

    for move_node in game.mainline():
        move = move_node.move
        # Analyse the position before making the move
        info = engine.analyse(board, chess.engine.Limit(depth=depth))

        score = info.get("score")
        pv = info.get("pv", [])

        # Make the move in the annotated game
        node = node.add_variation(move)

        # Add evaluation comment
        if score is not None:
            white_score = score.white()
            if white_score.is_mate():
                comment = f"M{white_score.mate()}"
            else:
                cp = white_score.score()
                comment = f"{cp / 100:+.2f}"
            node.comment = comment

        # Add best-move variation if it differs from the played move
        if pv and pv[0] != move and len(pv) >= 1:
            var_node = node.parent.add_variation(pv[0])
            if score is not None:
                white_score = score.white()
                if white_score.is_mate():
                    var_node.comment = f"best: M{white_score.mate()}"
                else:
                    cp = white_score.score()
                    var_node.comment = f"best: {cp / 100:+.2f}"
            for pv_move in pv[1:]:
                var_node = var_node.add_variation(pv_move)

        board.push(move)

    # Evaluate the final position
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info.get("score")
    if score is not None:
        white_score = score.white()
        if white_score.is_mate():
            node.comment = f"M{white_score.mate()}"
        else:
            cp = white_score.score()
            node.comment = f"{cp / 100:+.2f}"

    return annotated_game


def main():
    parser = argparse.ArgumentParser(description="Annotate PGN with Stockfish analysis")
    parser.add_argument("input", help="Input PGN file")
    parser.add_argument("output", nargs="?", help="Output PGN file (default: stdout)")
    parser.add_argument("--depth", type=int, default=15, help="Analysis depth (default: 15)")
    parser.add_argument("--engine", default="stockfish", help="Path to Stockfish binary")
    args = parser.parse_args()

    engine = chess.engine.SimpleEngine.popen_uci(args.engine)

    try:
        with open(args.input) as pgn_file:
            output_games = []
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                annotated = annotate_game(game, engine, args.depth)
                output_games.append(annotated)

        if args.output:
            with open(args.output, "w") as out:
                for g in output_games:
                    print(g, file=out)
                    print(file=out)
        else:
            for g in output_games:
                print(g)
                print()
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
