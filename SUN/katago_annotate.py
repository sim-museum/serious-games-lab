#!/usr/bin/env python3
"""Annotate an SGF file with KataGo analysis.

Runs KataGo GTP on each position and adds win-rate and score estimates
as comments. Writes the annotated SGF to an output file.

Usage: katago_annotate.py INPUT.sgf OUTPUT.sgf --katago PATH --model PATH --config PATH
"""

import argparse
import os
import re
import subprocess
import sys
import time


def parse_sgf_simple(sgf_text):
    """Parse an SGF file into a list of (color, coord) moves and header text.

    Returns (header, moves, trailer) where:
      - header is the SGF text up to and including the first node's properties
      - moves is a list of dicts with keys: color, coord, original_node
      - trailer is any closing text
    """
    # Find all nodes: ;PROP[val]PROP[val]...
    nodes = []
    # Split on ';' but keep track of position
    # Simple approach: find all ;...  segments
    i = sgf_text.find(";")
    if i == -1:
        return sgf_text, [], ""

    preamble = sgf_text[:i]
    rest = sgf_text[i:]

    # Split into nodes at each ';' that starts a node
    node_texts = []
    current = ""
    depth = 0
    for ch in rest:
        if ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == ";" and depth == 0:
            if current:
                node_texts.append(current)
            current = ";"
        else:
            current += ch
    if current:
        node_texts.append(current)

    if not node_texts:
        return sgf_text, [], ""

    header_node = node_texts[0]
    move_nodes = node_texts[1:] if len(node_texts) > 1 else []

    moves = []
    for node_text in move_nodes:
        # Extract B[..] or W[..] move
        m = re.search(r";?\s*(B|W)\[([a-s]{0,2})\]", node_text)
        if m:
            color = m.group(1)
            coord = m.group(2)
            moves.append({
                "color": color,
                "coord": coord,
                "text": node_text,
            })
        else:
            moves.append({
                "color": None,
                "coord": None,
                "text": node_text,
            })

    return preamble + header_node, moves, ""


def coord_to_gtp(coord, board_size=19):
    """Convert SGF coordinate (e.g. 'pd') to GTP coordinate (e.g. 'Q16')."""
    if not coord or len(coord) != 2:
        return "pass"
    col_letter = coord[0]
    row_letter = coord[1]
    col = ord(col_letter) - ord("a")
    row = ord(row_letter) - ord("a")
    # GTP columns skip 'I'
    gtp_col = chr(ord("A") + col + (1 if col >= 8 else 0))
    gtp_row = board_size - row
    return f"{gtp_col}{gtp_row}"


def get_board_size(sgf_text):
    """Extract board size from SGF header."""
    m = re.search(r"SZ\[(\d+)\]", sgf_text)
    return int(m.group(1)) if m else 19


def get_komi(sgf_text):
    """Extract komi from SGF header."""
    m = re.search(r"KM\[([\d.+-]+)\]", sgf_text)
    return float(m.group(1)) if m else 6.5


def add_comment_to_node(node_text, comment):
    """Add or append a comment to an SGF node."""
    # Check if node already has a comment
    m = re.search(r"C\[([^\]]*)\]", node_text)
    if m:
        existing = m.group(1)
        new_comment = existing + "\\n" + comment
        return node_text[:m.start()] + f"C[{new_comment}]" + node_text[m.end():]
    else:
        # Insert comment after the move property
        m2 = re.search(r"(;?\s*(?:B|W)\[[a-s]{0,2}\])", node_text)
        if m2:
            insert_pos = m2.end()
            return node_text[:insert_pos] + f"C[{comment}]" + node_text[insert_pos:]
        else:
            # No move found, append to end of node
            return node_text.rstrip() + f"C[{comment}]"


def run_katago_analysis(sgf_path, katago_bin, model_path, config_path, visits=100):
    """Run KataGo analysis engine on each position and return per-move evaluations."""
    with open(sgf_path) as f:
        sgf_text = f.read()

    board_size = get_board_size(sgf_text)
    komi = get_komi(sgf_text)
    header, moves, trailer = parse_sgf_simple(sgf_text)

    if not moves:
        return sgf_text  # No moves to analyze

    import json

    # Use KataGo's analysis engine (JSON protocol) instead of GTP.
    # The analysis engine accepts JSON queries on stdin and returns
    # JSON responses on stdout — one per line, no streaming.
    cmd = [katago_bin, "analysis", "-model", model_path, "-config", config_path]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Build the position incrementally and query after each move
    played_moves = []  # list of [color, gtp_coord] for the analysis engine
    evaluations = []

    for i, move in enumerate(moves):
        if move["color"] is None or move["coord"] is None:
            evaluations.append(None)
            continue

        gtp_coord = coord_to_gtp(move["coord"], board_size)
        color_word = "B" if move["color"] == "B" else "W"

        # Query position BEFORE this move is played
        query = {
            "id": str(i),
            "moves": [m for m in played_moves],
            "rules": "japanese",
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "analyzeTurns": [len(played_moves)],
            "maxVisits": visits,
        }
        proc.stdin.write(json.dumps(query) + "\n")
        proc.stdin.flush()

        # Read response (one JSON line per query)
        resp_line = proc.stdout.readline()
        winrate = None
        score = None
        try:
            resp = json.loads(resp_line)
            if "rootInfo" in resp:
                root = resp["rootInfo"]
                winrate = root.get("winrate")
                score = root.get("scoreLead")
        except (json.JSONDecodeError, KeyError):
            pass

        # Add this move to the position for the next query
        played_moves.append([color_word, gtp_coord])

        evaluations.append({"winrate": winrate, "score": score})

        if (i + 1) % 10 == 0 or (i + 1) == len(moves):
            print(f"  Analyzed {i + 1}/{len(moves)} moves...", file=sys.stderr)

    proc.stdin.close()
    proc.wait()

    # Build annotated SGF
    annotated_nodes = []
    for move, evaluation in zip(moves, evaluations):
        node_text = move["text"]
        if evaluation and evaluation["winrate"] is not None:
            wr = evaluation["winrate"] * 100
            comment = f"B win: {wr:.1f}%"
            if evaluation["score"] is not None:
                sc = evaluation["score"]
                leader = "B" if sc >= 0 else "W"
                comment += f", Score: {leader}+{abs(sc):.1f}"
            node_text = add_comment_to_node(node_text, comment)
        annotated_nodes.append(node_text)

    return header + "".join(annotated_nodes) + ")\n"


def main():
    parser = argparse.ArgumentParser(description="Annotate SGF with KataGo analysis")
    parser.add_argument("input", help="Input SGF file")
    parser.add_argument("output", help="Output annotated SGF file")
    parser.add_argument("--katago", required=True, help="Path to KataGo binary")
    parser.add_argument("--model", required=True, help="Path to KataGo model")
    parser.add_argument("--config", required=True, help="Path to KataGo GTP config")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"  Analyzing: {os.path.basename(args.input)}", file=sys.stderr)
    annotated = run_katago_analysis(args.input, args.katago, args.model, args.config)

    with open(args.output, "w") as f:
        f.write(annotated)
    print(f"  Analysis complete: {os.path.basename(args.output)}", file=sys.stderr)


if __name__ == "__main__":
    main()
