#!/usr/bin/env python3
import argparse
import random
import re
import sys
import time
from collections import defaultdict

import pyautogui

# Disable FailSafe to prevent "stopping" if mouse bumps corner
pyautogui.FAILSAFE = False

# CORRECTED Card layout based on user confirmation (C2 at bottom right).
# Rows are Spades, Hearts, Diamonds, Clubs.
# Columns are Ace down to 2.
CARD_GRID_LAYOUT = [
    ["SA", "SK", "SQ", "SJ", "S10", "S9", "S8", "S7", "S6", "S5", "S4", "S3", "S2"],
    ["HA", "HK", "HQ", "HJ", "H10", "H9", "H8", "H7", "H6", "H5", "H4", "H3", "H2"],
    ["DA", "DK", "DQ", "DJ", "D10", "D9", "D8", "D7", "D6", "D5", "D4", "D3", "D2"],
    ["CA", "CK", "CQ", "CJ", "C10", "C9", "C8", "C7", "C6", "C5", "C4", "C3", "C2"]
]

CARD_COORDS_MAP = {
    card: (r, c)
    for r, row in enumerate(CARD_GRID_LAYOUT)
    for c, card in enumerate(row)
}

SUITS = ["S", "H", "D", "C"]
RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]

HCP_VALUES = {"A": 4, "K": 3, "Q": 2, "J": 1}


def get_mouse_pos(prompt: str, debug: bool = False):
    """Ask user to hover mouse and press Enter, then return the position."""
    input(f"{prompt} (hover, then press ENTER)")
    pos = pyautogui.position()
    if debug:
        print(f"Captured: {pos}")
    else:
        print("Captured.")
    return pos


def interpolate_grid(top_left, bottom_right, rows=4, cols=13):
    """Return a dict mapping (row, col) to screen coordinates."""
    x0, y0 = top_left
    x1, y1 = bottom_right
    
    # Calculate step based on center-to-center distance
    if cols > 1:
        step_x = (x1 - x0) / (cols - 1)
    else:
        step_x = 0
        
    if rows > 1:
        step_y = (y1 - y0) / (rows - 1)
    else:
        step_y = 0
    
    grid_points = {}
    for r in range(rows):
        for c in range(cols):
            cx = x0 + c * step_x
            cy = y0 + r * step_y
            grid_points[(r, c)] = (cx, cy)
    return grid_points


def parse_pbn_hand(hand_str: str):
    """
    Parse a single PBN hand like 'AKQ7.95..J82' or 'T543...' into a list of card codes.
    Suits are in SHDC order. Handles 'T' as 10.
    """
    suits = hand_str.split(".")
    if len(suits) != 4:
        raise ValueError(
            f"Invalid hand format '{hand_str}': must contain 4 suits in SHDC order."
        )

    cards = []
    for i, suit_cards in enumerate(suits):
        if not suit_cards:
            continue
        # Match 10, T, or single rank characters.
        ranks = re.findall(r"10|T|[AKQJ98765432]", suit_cards)
        for rank in ranks:
            # Normalize T to 10 for the grid map
            if rank == 'T':
                rank = '10'
            cards.append(SUITS[i] + rank)

    if len(cards) != 13:
        raise ValueError(
            f"Hand '{hand_str}' yields {len(cards)} cards, expected 13."
        )
    return cards


def parse_full_pbn_spec(spec: str):
    """
    Parse full PBN deal text like:
      'N:AKQ7.95..J82 T543.QJ7.AQ4.KT9 J92.AK6.T987.65 86.T8432.KJ63.AQ7'
    """
    s = spec.strip()
    if not s:
        raise ValueError("Empty -hand string.")

    if ":" not in s:
        raise ValueError("PBN string must start with '<dealer>:' such as 'N:'.")
    dealer, rest = s.split(":", 1)
    dealer = dealer.strip().upper()
    if dealer != "N":
        raise ValueError(
            "This tool currently expects 'N:' as the dealer so that hands "
            "are in N E S W order."
        )

    parts = rest.split()
    if len(parts) != 4:
        raise ValueError(
            "Full hand spec must have 4 space-separated hands for N E S W."
        )

    hands = [parse_pbn_hand(p) for p in parts]
    return hands  # order: N, E, S, W


def hand_hcp(cards):
    """Return high card points of a 13-card hand."""
    hcp = 0
    for card in cards:
        rank = card[1:]
        hcp += HCP_VALUES.get(rank, 0)
    return hcp


def hand_shape(cards):
    """Return a tuple (s, h, d, c) for the hand."""
    counts = defaultdict(int)
    for card in cards:
        counts[card[0]] += 1
    return tuple(counts[s] for s in SUITS)


def generate_random_deal(target_hcp=None, target_shape=None, max_tries=20000):
    """
    Generate a random bridge deal (N,E,S,W), with optional constraints
    on South's HCP and shape. target_shape is a 4-tuple in S,H,D,C order.
    """
    deck = [s + r for s in SUITS for r in RANKS]

    for _ in range(max_tries):
        random.shuffle(deck)
        hands = [
            deck[0:13],   # North
            deck[13:26],  # East
            deck[26:39],  # South
            deck[39:52],  # West
        ]

        south = hands[2]

        if target_hcp is not None and hand_hcp(south) != target_hcp:
            continue

        if target_shape is not None and hand_shape(south) != target_shape:
            continue

        return hands

    raise RuntimeError(
        "Unable to generate a hand satisfying the requested constraints "
        "within the retry limit."
    )


def parse_shape_string(shape_str: str):
    """Parse shape string '4432' into a random permutation over suits."""
    if not re.fullmatch(r"[0-9]{4}", shape_str):
        raise ValueError("Shape must be four digits, e.g. 4432.")
    digits = [int(d) for d in shape_str]
    if sum(digits) != 13:
        raise ValueError("Shape digits must sum to 13.")
    random.shuffle(digits)
    return tuple(digits)  # assigned to S,H,D,C in this random order


def check_args(args: argparse.Namespace):
    """Validate combinations of command-line arguments."""
    if args.hand and (args.hcp is not None or args.shape is not None):
        raise SystemExit(
            "Error: -hand cannot be used together with -hcp or -shape."
        )

    if args.hcp is not None and not (0 <= args.hcp <= 37):
        raise SystemExit("Error: -hcp must be between 0 and 37.")

    if args.shape is not None and not re.fullmatch(r"[0-9]{4}", args.shape):
        raise SystemExit("Error: -shape must be four digits, e.g. 4432.")


def enter_deal_gui(hands, grid_coords, player_positions, ok_pos, clear_pos, debug=False):
    """
    Click Clear, then click cards for each player.
    """
    player_names = ["North", "East", "South", "West"]

    print("\n--- STARTING ENTRY IN 3 SECONDS ---")
    print("Do not touch the mouse.")
    time.sleep(3)

    try:
        # 0. Clear the board to ensure no previous cards remain
        print("Clicking 'Clear all'...")
        pyautogui.moveTo(clear_pos[0], clear_pos[1], duration=0.2)
        pyautogui.click()
        time.sleep(0.5)

        for p_idx, hand in enumerate(hands):
            print(f"Entering hand for {player_names[p_idx]}...")

            # 1. Select the player checkbox
            px, py = player_positions[p_idx]
            pyautogui.moveTo(px, py, duration=0.2)
            pyautogui.click()
            time.sleep(0.3)

            # 2. Click each card in the grid
            for card in hand:
                if card not in CARD_COORDS_MAP:
                    if debug:
                        print(f"Warning: card {card} is not in the grid map; skipping.")
                    continue
                r, c = CARD_COORDS_MAP[card]
                cx, cy = grid_coords[(r, c)]
                
                if debug:
                    print(f"  - Clicking {card} at ({int(cx)}, {int(cy)})...")
                
                pyautogui.moveTo(cx, cy, duration=0.2)
                pyautogui.mouseDown()
                time.sleep(0.05) 
                pyautogui.mouseUp()
                time.sleep(0.1) 

        # Click OK to close dialog and start bidding
        print("Clicking OK to close the Hand Input dialog...")
        pyautogui.moveTo(ok_pos[0], ok_pos[1], duration=0.2)
        pyautogui.click()
        print("Done.")
        
    except Exception as e:
        print(f"\nCRITICAL ERROR: Script stopped early due to: {e}")
        if debug:
            import traceback
            traceback.print_exc()


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Enter a bridge deal into Q-plus 15 Hand Input using GUI automation.\n\n"
            "PBN format example:\n"
            "  N:AKQ72.954.632.J8 T543.QJ7.AQ4.KT9 J98.AK6.T987.652 6.T832.KJ5.AQ743\n\n"
            "Hands are in order North, East, South, West and each consists of\n"
            "four dot-separated suits in SHDC order."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit."
    )
    parser.add_argument(
        "-hand",
        metavar="PBN",
        help=(
            "Full PBN deal text, e.g. "
            "\"N:AKQ72.954.632.J8 T543.QJ7.AQ4.KT9 J98.AK6.T987.652 6.T832.KJ5.AQ743\". "
            "Dealer must be N so that hands are in N E S W order."
        ),
    )
    parser.add_argument(
        "-hcp",
        type=int,
        metavar="NUM",
        help="Give South exactly NUM high card points (0–37).",
    )
    parser.add_argument(
        "-shape",
        metavar="DDDD",
        help=(
            "Give South a bridge shape with digits summing to 13, "
            "e.g. 4432. Suit to digit assignment is random."
        ),
    )
    parser.add_argument(
        "-debug",
        action="store_true",
        help="Print detailed card parsing and clicking logs to the terminal.",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    check_args(args)

    print("=== Q-plus Bridge Hand Entry Automation ===")
    print("Ensure you are running under Xorg and the 'Hand Input' dialog is visible.\n")

    # Determine the deal
    if args.hand:
        print(f"Mode: Manual Input")
        try:
            hands = parse_full_pbn_spec(args.hand)
            if args.debug:
                print("--- PARSED HANDS ---")
                print(f"North: {hands[0]}")
                print(f"East:  {hands[1]}")
                print(f"South: {hands[2]}")
                print(f"West:  {hands[3]}")
                print("--------------------\n")
                sys.stdout.flush()
        except ValueError as e:
            raise SystemExit(f"Error in -hand: {e}")
    else:
        print(f"Mode: Random Generation")
        target_hcp = args.hcp
        target_shape = None
        if args.shape is not None:
            try:
                target_shape = parse_shape_string(args.shape)
            except ValueError as e:
                raise SystemExit(f"Error in -shape: {e}")
        try:
            hands = generate_random_deal(
                target_hcp=target_hcp, target_shape=target_shape
            )
        except RuntimeError as e:
            raise SystemExit(f"Error generating deal: {e}")

    # Calibration
    print("\n--- CALIBRATION STEP ---")
    chk_north = get_mouse_pos("1. Hover over the 'North' checkbox", debug=args.debug)
    chk_west = get_mouse_pos("2. Hover over the 'West' checkbox", debug=args.debug)

    # Checkbox positions for N,E,S,W (equally spaced vertically)
    chk_step_y = (chk_west.y - chk_north.y) / 3.0
    player_positions = {
        0: (chk_north.x, chk_north.y),                  # North
        1: (chk_north.x, chk_north.y + chk_step_y),     # East
        2: (chk_north.x, chk_north.y + 2 * chk_step_y), # South
        3: (chk_west.x, chk_west.y),                    # West
    }

    grid_tl = get_mouse_pos(
        "3. Hover over the CENTER of the top-left card button (Ace of Spades)",
        debug=args.debug
    )
    
    # Bottom-Right is Two of Clubs
    grid_br = get_mouse_pos(
        "4. Hover over the CENTER of the bottom-right card button (Two of Clubs)",
        debug=args.debug
    )

    clear_button_pos = get_mouse_pos(
        "5. Hover over the 'Clear all' button",
        debug=args.debug
    )
    
    ok_button_pos = get_mouse_pos(
        "6. Hover over the 'Ok' button",
        debug=args.debug
    )

    print("\nCalculating grid positions...")
    grid_coords = interpolate_grid(grid_tl, grid_br)

    enter_deal_gui(hands, grid_coords, player_positions, ok_button_pos, clear_button_pos, debug=args.debug)


if __name__ == "__main__":
    main()

