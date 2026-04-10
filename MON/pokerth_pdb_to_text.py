#!/usr/bin/env python3
"""Convert PokerTH .pdb SQLite database to readable text hand history."""

import sqlite3
import sys

SUITS = ['C', 'D', 'H', 'S']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
BERO = {0: 'Preflop', 1: 'Flop', 2: 'Turn', 3: 'River'}


def card_str(c):
    if c is None or c < 0:
        return '??'
    return RANKS[c % 13] + SUITS[c // 13]


def convert(pdb_path):
    db = sqlite3.connect(pdb_path)
    cur = db.cursor()

    # Session info
    cur.execute('SELECT PokerTH_Version, Date, Time FROM Session')
    session = cur.fetchone()
    out = []
    if session:
        out.append(f"PokerTH Session Log — {session[1]} {session[2]}")
        out.append(f"Version: {session[0]}")
    out.append("=" * 60)

    # Players
    cur.execute('SELECT Seat, Player FROM Player ORDER BY Seat')
    players = {row[0]: row[1] for row in cur.fetchall()}
    out.append("Players: " + ", ".join(f"Seat {s}: {n}" for s, n in sorted(players.items())))
    out.append("")

    # Game info
    cur.execute('SELECT Startmoney, StartSb FROM Game LIMIT 1')
    game = cur.fetchone()
    if game:
        out.append(f"Starting money: ${game[0]}, Starting SB: ${game[1]}")
        out.append("")

    # Hands
    cur.execute('SELECT * FROM Hand ORDER BY HandID')
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        h = dict(zip(cols, row))
        dealer_name = players.get(h['Dealer_Seat'], f"Seat{h['Dealer_Seat']}")
        out.append("=" * 60)
        out.append(f"HAND #{h['HandID']} — Dealer: {dealer_name}, "
                   f"SB=${h['Sb_Amount']}, BB=${h['Bb_Amount']}")
        out.append("=" * 60)

        # Board cards
        board_cards = []
        for i in range(1, 6):
            c = h.get(f'BoardCard_{i}')
            if c is not None and c >= 0:
                board_cards.append(card_str(c))
        if board_cards:
            out.append(f"Board: {' '.join(board_cards)}")

        # Player hands and stacks
        out.append("")
        for seat in range(1, 11):
            cash = h.get(f'Seat_{seat}_Cash')
            if not cash or cash <= 0:
                continue
            c1 = h.get(f'Seat_{seat}_Card_1')
            c2 = h.get(f'Seat_{seat}_Card_2')
            hand_text = h.get(f'Seat_{seat}_Hand_text', '') or ''
            name = players.get(seat, f'Seat{seat}')
            if c1 is not None and c1 >= 0:
                cards = f"[{card_str(c1)} {card_str(c2)}]"
            else:
                cards = "[-- --]"
            extra = f"  ({hand_text})" if hand_text else ""
            out.append(f"  {name}: {cards} ${cash}{extra}")

        out.append("")

        # Actions
        cur2 = db.cursor()
        cur2.execute('SELECT BeRo, Player, Action, Amount FROM Action '
                     'WHERE HandID=? ORDER BY ActionID', (h['HandID'],))
        last_bero = -1
        for bero, player_seat, action, amount in cur2.fetchall():
            if bero != last_bero:
                out.append(f"  --- {BERO.get(bero, f'Round {bero}')} ---")
                last_bero = bero
            name = players.get(player_seat, f'Seat{player_seat}')
            amt_str = f" ${amount}" if amount else ""
            out.append(f"    {name}: {action}{amt_str}")

        out.append("")

    db.close()
    return "\n".join(out)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.pdb> [output.txt]")
        sys.exit(1)

    text = convert(sys.argv[1])

    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'w') as f:
            f.write(text)
        print(f"Converted to {sys.argv[2]}")
    else:
        print(text)
