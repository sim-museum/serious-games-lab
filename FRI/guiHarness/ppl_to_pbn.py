#!/usr/bin/env python3
"""
Bridge Baron .ppl to .pbn converter.

The .ppl format is a 774-byte binary format used by Bridge Baron 12.
Structure:
  0x00-0x01: Version (01 04)
  0x02-0x0B: Deal name (null-terminated, 10 bytes)
  0x0C-0x2F: Description (null-terminated, 36 bytes)
  0x30-0x77: Game data (bidding, contract, play, dealer, vulnerability)
  0x78-0xAB: 52-byte card permutation (values 0-51)
  0xAC:      Terminator (value 52)
  0xAD-0xAF: Marker (FF FF FF)
  0xB0-0xE9: Padding
  0xEA-0x16F: Commentary (null-terminated)
  0x170-end:  Padding to 774 bytes

The card permutation at 0x78 contains values 0-51 in a Bridge Baron-specific
encoding.  The exact card-index-to-card mapping is not yet fully decoded.
This module provides helpers that extract the metadata and permutation, and
will be updated once the encoding is cracked.

To help decode the format: create a deal in Bridge Baron where North has all
13 spades, East all hearts, South all diamonds, West all clubs, save it as
.ppl, and run:  python ppl_to_pbn.py --decode <file.ppl>
"""

import re
import struct
import sys
from pathlib import Path


PPL_SIZE = 774
CARD_OFFSET = 0x78
CARD_COUNT = 52


def read_cstring(data: bytes, offset: int, max_len: int) -> str:
    """Read a null-terminated string from binary data."""
    end = data.index(0, offset) if 0 in data[offset:offset + max_len] else offset + max_len
    return data[offset:end].decode('ascii', errors='replace').strip()


def parse_ppl(path: str) -> dict:
    """Parse a Bridge Baron .ppl file.

    Returns a dict with keys:
      name, description, commentary, card_perm (list of 52 ints 0-51),
      raw_game_data (bytes 0x30-0x77)
    """
    data = Path(path).read_bytes()
    if len(data) != PPL_SIZE:
        raise ValueError(f"Expected {PPL_SIZE} bytes, got {len(data)}")

    version = (data[0], data[1])
    name = read_cstring(data, 0x02, 10)
    description = read_cstring(data, 0x0C, 36)
    commentary = read_cstring(data, 0xEA, 134)

    card_perm = list(data[CARD_OFFSET:CARD_OFFSET + CARD_COUNT])

    # Validate permutation (may be all zeros if no play was recorded)
    has_play = any(b != 0 for b in card_perm)
    if has_play and sorted(card_perm) != list(range(52)):
        raise ValueError("Card permutation at 0x78 is not a valid 0-51 permutation")

    return {
        'version': version,
        'name': name,
        'description': description,
        'commentary': commentary,
        'card_perm': card_perm,
        'raw_game_data': data[0x30:0x78],
    }


# ---------------------------------------------------------------------------
# BB12 deal number → card assignment algorithm (reverse-engineered)
# ---------------------------------------------------------------------------
# PRNG: MSVC rand() — state = state * 214013 + 2531011 (mod 2^32)
#       Returns (state >> 16) & 0x7FFF  (0–32767)
# Seed: deal_number + 32
# Suits: index 0=Clubs, 1=Diamonds, 2=Hearts, 3=Spades
# Ranks: bit 0=2, bit 1=3, ..., bit 12=Ace  (low to high)
# Players: hand 0=North, 1=East, 2=South, 3=West
# Algorithm: bitmask dealing — for each of 52 cards, rand_range(remaining)
#            selects from pool by scanning suits in order, then finding the
#            r-th set bit in the suit bitmask (LSB first).

BB12_SUIT_CHARS = ['C', 'D', 'H', 'S']
BB12_RANK_CHARS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']


class _BB12Rand:
    """MSVC-compatible LCG used by Bridge Baron 12."""
    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def rand(self):
        self.state = (self.state * 214013 + 2531011) & 0xFFFFFFFF
        return (self.state >> 16) & 0x7FFF

    def rand_range(self, n):
        return self.rand() % n


def bb12_deal_from_number(deal_number: int) -> list:
    """Generate [N, E, S, W] hands from a Bridge Baron 12 deal number.

    Each hand is a list of 13 card strings like ['SA', 'HK', 'D10', ...].
    """
    rng = _BB12Rand(deal_number + 32)

    masks = [0x1FFF] * 4   # 4 suits, 13 bits each (all cards available)
    counts = [13] * 4

    hands = [[] for _ in range(4)]  # N, E, S, W

    for player in range(4):
        for _ in range(13):
            total = sum(counts)
            r = rng.rand_range(total)

            # Find which suit
            suit_idx = 0
            while r >= counts[suit_idx]:
                r -= counts[suit_idx]
                suit_idx += 1

            # Find the r-th set bit in the suit bitmask (LSB = rank '2')
            mask = masks[suit_idx]
            bit_pos = 0
            found = 0
            for bit_pos in range(13):
                if mask & (1 << bit_pos):
                    if found == r:
                        break
                    found += 1

            # Remove card from pool
            masks[suit_idx] &= ~(1 << bit_pos)
            counts[suit_idx] -= 1

            hands[player].append(BB12_SUIT_CHARS[suit_idx] + BB12_RANK_CHARS[bit_pos])

    return hands


def ppl_to_hands(ppl: dict) -> list:
    """Decode hands from the bitmask data at bytes 0x30-0x4F.

    Each player has 4 suit bitmasks (2 bytes LE each, bit0=rank '2', bit12='A').
    Layout: 4 players × 4 suits × 2 bytes = 32 bytes.
    Player order: N, E, S, W.  Suit order: C, D, H, S.
    """
    import struct
    raw = ppl['raw_game_data']
    hands = [[] for _ in range(4)]
    for pi in range(4):
        for si in range(4):
            offset = (pi * 4 + si) * 2
            mask = struct.unpack_from('<H', raw, offset)[0]
            for bit in range(13):
                if mask & (1 << bit):
                    hands[pi].append(BB12_SUIT_CHARS[si] + BB12_RANK_CHARS[bit])
    return hands


def ppl_to_play(ppl: dict) -> list:
    """Decode trick-by-trick play from the 52-byte permutation at 0x78.

    The permutation stores card IDs (suit*13 + rank) in play order:
    each group of 4 = one trick, ordered leader-first clockwise.
    Returns list of 13 dicts, each {seat: card_string}.
    """
    RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
                '10':10,'J':11,'Q':12,'K':13,'A':14}
    SEATS = ['N','E','S','W']

    game = ppl_decode_game(ppl)
    perm = ppl['card_perm']

    # Determine opening leader (left of declarer)
    di = SEATS.index(game['declarer'])
    leader_idx = (di + 1) % 4

    # Trump suit
    trump = None
    cup = game['contract'].upper().replace('X', '')
    for t in ['S', 'H', 'D', 'C']:
        if t in cup and 'NT' not in cup:
            trump = t
            break

    tricks = []
    leaders = []
    winners = []

    for t in range(13):
        trick = {}
        for p in range(4):
            cid = perm[t * 4 + p]
            card = BB12_SUIT_CHARS[cid // 13] + BB12_RANK_CHARS[cid % 13]
            trick[SEATS[(leader_idx + p) % 4]] = card

        # Find winner
        leader_card = trick[SEATS[leader_idx]]
        led_suit = leader_card[0]
        best_seat = SEATS[leader_idx]
        best_trump = (led_suit == trump) if trump else False
        best_val = RANK_VAL[leader_card[1:]]

        for p in range(1, 4):
            s = SEATS[(leader_idx + p) % 4]
            c = trick[s]
            is_t = (c[0] == trump) if trump else False
            v = RANK_VAL[c[1:]]
            if is_t and not best_trump:
                best_seat, best_trump, best_val = s, True, v
            elif is_t and best_trump and v > best_val:
                best_seat, best_val = s, v
            elif c[0] == led_suit and not best_trump and v > best_val:
                best_seat, best_val = s, v

        tricks.append(trick)
        leaders.append(SEATS[leader_idx])
        winners.append(best_seat)
        leader_idx = SEATS.index(best_seat)

    return tricks, leaders, winners


# ---------------------------------------------------------------------------
# Bidding / contract / dealer decoding
# ---------------------------------------------------------------------------
# Game data layout (bytes 0x30-0x77, 72 bytes):
#   0x30-0x53: Play data (encoding TBD)
#   0x54-0x6F: Bidding sequence (00=Pass, high_nibble=level, low_nibble=suit)
#              Suit encoding: C=0, D=1, H=2, S=3, NT=4
#   0x74:      Number of tricks played (or related count)
#   0x75:      Contract (same encoding as bids: high=level, low=suit)
#   0x76:      Unknown (possibly vulnerability)
#   0x77:      Dealer/declarer info: low 2 bits = dealer (0=N,1=E,2=S,3=W)

BID_SUITS = {0: 'C', 1: 'D', 2: 'H', 3: 'S', 4: 'NT'}
SEAT_CHARS = ['N', 'E', 'S', 'W']


def _decode_bid(byte_val: int) -> str:
    """Decode a single bid byte. 00=Pass, else high_nibble=level, low_nibble=suit."""
    if byte_val == 0:
        return 'Pass'
    level = (byte_val >> 4) & 0xF
    suit = byte_val & 0xF
    suit_str = BID_SUITS.get(suit, '?')
    if level < 1 or level > 7:
        return f'?{byte_val:02x}'
    return f'{level}{suit_str}'


def ppl_decode_game(ppl: dict) -> dict:
    """Decode bidding, contract, and dealer from the game data region.

    Returns dict with keys: dealer, contract, declarer, bidding (list of bid strings).

    Layout of last 4 bytes of game data (0x74-0x77):
      [-4]: tricks-related count
      [-3]: contract (high_nibble=level, low_nibble=suit)
      [-2]: dealer (0=N, 1=E, 2=S, 3=W)
      [-1]: declarer (0=N, 1=E, 2=S, 3=W)

    Bidding is stored from raw offset ~34 onwards:
      - Skips initial passes (implied by dealer vs opening bidder)
      - 0x00 = Pass, 0x01 = Double, others = level<<4 | suit
      - Ends when 2+ consecutive passes follow the last bid
    """
    raw = ppl['raw_game_data']  # bytes 0x30-0x77

    # Dealer and declarer from last 2 bytes
    dealer_idx = raw[-2] & 0x3
    declarer_idx = raw[-1] & 0x3
    dealer = SEAT_CHARS[dealer_idx]
    declarer = SEAT_CHARS[declarer_idx]

    # Contract from byte[-3]
    contract_byte = raw[-3]
    if contract_byte == 0:
        contract = 'Pass'
    else:
        contract = _decode_bid(contract_byte)

    # Scan for the bidding sequence starting at raw offset 34.
    # Skip the 2-byte header (bytes 32-33 = "00 01" pattern) and any
    # leading zeros (passes before the opening bid).
    # Find the first actual bid (non-zero, non-0x01).
    scan_start = 34  # raw index (absolute 0x52)
    opening_bid_pos = None
    for i in range(scan_start, min(scan_start + 30, len(raw))):
        if raw[i] != 0 and raw[i] != 1:
            opening_bid_pos = i
            break

    bids = []
    if opening_bid_pos is not None:
        # Count initial passes: seats between dealer and opening bidder
        initial_passes = opening_bid_pos - scan_start
        # The opening bidder is (dealer_idx + initial_passes) % 4
        for _ in range(initial_passes):
            bids.append('Pass')

        # Read bids from opening bid onwards
        consecutive_passes = 0
        for i in range(opening_bid_pos, min(opening_bid_pos + 40, len(raw))):
            b = raw[i]
            if b == 0xFF:
                break
            bid = _decode_bid(b)
            if bid.startswith('?'):
                continue  # skip unknown bytes (like 0x01 = possible double)
            bids.append(bid)
            if bid == 'Pass':
                consecutive_passes += 1
                if consecutive_passes >= 3:
                    break
            else:
                consecutive_passes = 0

    return {
        'dealer': dealer,
        'contract': contract,
        'declarer': declarer,
        'bidding': bids,
    }


# ---------------------------------------------------------------------------
# PBN output
# ---------------------------------------------------------------------------
SUITS = ['S', 'H', 'D', 'C']
RANK_ORDER = {'A':0,'K':1,'Q':2,'J':3,'10':4,'9':5,'8':6,'7':7,
              '6':8,'5':9,'4':10,'3':11,'2':12}


def _hands_to_pbn_deal(hands):
    """Convert [N,E,S,W] card lists to PBN deal string."""
    parts = []
    for hand in hands:
        suit_groups = {s: [] for s in SUITS}
        for card in hand:
            suit_groups[card[0]].append(card[1:])
        suit_strs = []
        for s in SUITS:
            ranks = sorted(suit_groups[s], key=lambda r: RANK_ORDER.get(r, 99))
            suit_strs.append(''.join('T' if r == '10' else r for r in ranks))
        parts.append('.'.join(suit_strs))
    return 'N:' + ' '.join(parts)


def ppl_to_pbn(path: str, deal_number: int = None) -> str:
    """Convert a .ppl file to PBN format with deal, bidding, contract, and play."""
    ppl = parse_ppl(path)
    hands = ppl_to_hands(ppl)
    game = ppl_decode_game(ppl)

    deal_str = _hands_to_pbn_deal(hands)

    lines = []
    lines.append(f'[Event "Bridge Baron 12"]')
    lines.append(f'[Dealer "{game["dealer"]}"]')
    lines.append(f'[Deal "{deal_str}"]')
    lines.append(f'[Declarer "{game["declarer"]}"]')
    lines.append(f'[Contract "{game["contract"]}"]')
    if ppl['description']:
        lines.append(f'[Description "{ppl["description"]}"]')

    # Bidding
    if game['bidding']:
        lines.append(f'[Auction "{game["dealer"]}"]')
        bids = [b.upper().replace('PASS', 'Pass') for b in game['bidding']]
        for i in range(0, len(bids), 4):
            lines.append('  '.join(bids[i:i+4]))

    # Play
    tricks, leaders, winners = ppl_to_play(ppl)
    if tricks:
        SEATS = ['N', 'E', 'S', 'W']
        opening_leader = leaders[0]
        li = SEATS.index(opening_leader)
        col_order = [SEATS[(li + p) % 4] for p in range(4)]

        ns = sum(1 for w in winners if w in ('N', 'S'))
        ew = sum(1 for w in winners if w in ('E', 'W'))
        declarer_tricks = ns if game['declarer'] in ('N', 'S') else ew
        lines.append(f'[Result "{declarer_tricks}"]')
        lines.append(f'[Play "{opening_leader}"]')
        for trick in tricks:
            cards = []
            for s in col_order:
                c = trick[s]
                cards.append(c.replace('10', 'T'))
            lines.append(' '.join(cards))

    return '\n'.join(lines) + '\n'


def _guess_deal_number(path: str) -> int:
    """Try to extract deal number from filename like '260323bb12_1_2029514179.ppl'."""
    import re
    name = Path(path).stem
    m = re.search(r'(\d{6,})', name.split('bb12')[-1] if 'bb12' in name else name)
    if m:
        return int(m.group(1))
    raise ValueError(
        f"Cannot determine deal number from filename '{name}'.\n"
        "Use --deal-number to specify it explicitly."
    )


def ppl_to_bdl(path: str, deal_number: int = None) -> str:
    """Convert a .ppl file to BDL format with hands, bidding, contract, and play."""
    import bridge_harness as bh

    ppl = parse_ppl(path)
    hands = ppl_to_hands(ppl)
    game = ppl_decode_game(ppl)

    board_info = {
        'Board': '1',
        'Dealer': game['dealer'],
        'Vulnerable': 'None',
        'Contract': game['contract'],
        'Declarer': game['declarer'],
    }

    # Convert bidding to PBN auction format
    if game['bidding']:
        board_info['Auction'] = game['dealer']
        bids = game['bidding']
        auction_lines = []
        for i in range(0, len(bids), 4):
            row = [b.upper() if b != 'Pass' else 'Pass' for b in bids[i:i+4]]
            auction_lines.append(' '.join(row))
        board_info['Auction_data'] = auction_lines

    # Convert play data to PBN format
    tricks, leaders, winners = ppl_to_play(ppl)
    if tricks:
        SEATS = ['N', 'E', 'S', 'W']
        # Opening leader
        opening_leader = leaders[0]
        board_info['Play'] = opening_leader

        # PBN play: columns in fixed order from opening leader clockwise
        li = SEATS.index(opening_leader)
        col_order = [SEATS[(li + p) % 4] for p in range(4)]
        play_lines = []
        for trick in tricks:
            play_lines.append(' '.join(trick[s] for s in col_order))
        board_info['Play_data'] = play_lines

        # Result: count declarer's tricks
        ns_tricks = sum(1 for w in winners if w in ('N', 'S'))
        ew_tricks = sum(1 for w in winners if w in ('E', 'W'))
        declarer_tricks = ns_tricks if game['declarer'] in ('N', 'S') else ew_tricks
        board_info['Result'] = str(declarer_tricks)

    label = ppl['name'][:2].upper() if ppl['name'] else 'BB'
    bdl_body = bh.board_to_bdl(hands, board_info, source_label=label)

    header = (
        'DOCTYPE: BDL 17.1\n'
        f'.description.eng = "converted from Bridge Baron 12 .ppl"\n'
        '\n'
        'Scoring      :  Pair (MP)\n'
        '.Bidding cnv :  N/S: Bridge Baron 12\n'
        '.            :  E/W: Bridge Baron 12\n'
        '\n'
    )
    return header + bdl_body + '\n'


def build_ppl(hands, dealer, declarer, contract, bidding=None,
              play_tricks=None, play_leaders=None,
              name='', description='', commentary='') -> bytes:
    """Build a 774-byte .ppl file from bridge data.

    hands: [N, E, S, W] lists of card strings like ['SA','HK','D10',...]
    dealer/declarer: 'N','E','S','W'
    contract: string like '4H', '3NT', '2SX', or 'Pass'
    bidding: list of bid strings ['Pass','1D','2H',...] (optional)
    play_tricks: list of 13 dicts {seat: card} (optional)
    play_leaders: list of 13 seat chars (optional, needed with play_tricks)
    """
    SEATS = ['N', 'E', 'S', 'W']
    SUIT_IDX = {'C': 0, 'D': 1, 'H': 2, 'S': 3}
    RANK_IDX = {'2':0,'3':1,'4':2,'5':3,'6':4,'7':5,'8':6,'9':7,
                '10':8,'J':9,'Q':10,'K':11,'A':12}

    buf = bytearray(PPL_SIZE)  # 774 bytes, zero-filled

    # Version
    buf[0] = 0x01
    buf[1] = 0x04

    # Name (offset 0x02, max 10 bytes)
    name_bytes = name[:9].encode('ascii', errors='replace') + b'\x00'
    buf[0x02:0x02 + len(name_bytes)] = name_bytes

    # Description (offset 0x0C, max 36 bytes)
    desc_bytes = description[:35].encode('ascii', errors='replace') + b'\x00'
    buf[0x0C:0x0C + len(desc_bytes)] = desc_bytes

    # Hand bitmasks at 0x30-0x4F (4 players × 4 suits × 2 bytes LE)
    for pi in range(4):
        for card in hands[pi]:
            si = SUIT_IDX[card[0]]
            ri = RANK_IDX[card[1:]]
            offset = 0x30 + (pi * 4 + si) * 2
            mask = int.from_bytes(buf[offset:offset + 2], 'little')
            mask |= (1 << ri)
            buf[offset:offset + 2] = mask.to_bytes(2, 'little')

    # Bidding at 0x52 onward
    # Bytes 0x50-0x51: seems to be a header/padding (observed as dealer-related)
    di = SEATS.index(dealer)
    dci = SEATS.index(declarer)

    if bidding:
        # Encode bids starting at offset 0x54 (raw index 0x24 = 36 from 0x30)
        bid_offset = 0x54
        for bid in bidding:
            b = bid.strip().upper()
            if b in ('PASS', 'P'):
                buf[bid_offset] = 0x00
            elif b in ('X', 'DBL'):
                buf[bid_offset] = 0x01
            else:
                import re
                m = re.match(r'(\d)(C|D|H|S|NT)', b)
                if m:
                    level = int(m.group(1))
                    suit = {'C': 0, 'D': 1, 'H': 2, 'S': 3, 'NT': 4}[m.group(2)]
                    buf[bid_offset] = (level << 4) | suit
            bid_offset += 1

    # Contract at 0x75
    contract_up = contract.strip().upper().replace('X', '')
    if contract_up == 'PASS':
        buf[0x75] = 0x00
    else:
        import re
        m = re.match(r'(\d)(C|D|H|S|NT)', contract_up)
        if m:
            level = int(m.group(1))
            suit = {'C': 0, 'D': 1, 'H': 2, 'S': 3, 'NT': 4}[m.group(2)]
            buf[0x75] = (level << 4) | suit

    # Dealer at 0x76, declarer at 0x77
    buf[0x76] = di
    buf[0x77] = dci

    # Play order at 0x78-0xAB (52 card IDs, leader-first per trick)
    if play_tricks and play_leaders:
        for t in range(min(13, len(play_tricks))):
            leader = play_leaders[t]
            li = SEATS.index(leader)
            for p in range(4):
                seat = SEATS[(li + p) % 4]
                card = play_tricks[t][seat]
                cid = SUIT_IDX[card[0]] * 13 + RANK_IDX[card[1:]]
                buf[0x78 + t * 4 + p] = cid

        # Tricks count at 0x74
        buf[0x74] = len(play_tricks)

    # Terminator at 0xAC
    buf[0xAC] = 52

    # Marker at 0xAD-0xAF
    buf[0xAD] = 0xFF
    buf[0xAE] = 0xFF
    buf[0xAF] = 0xFF

    # Commentary at 0xEA
    comm_bytes = commentary[:133].encode('ascii', errors='replace') + b'\x00'
    buf[0xEA:0xEA + len(comm_bytes)] = comm_bytes

    return bytes(buf)


def _parse_bdl_file(path: str) -> dict:
    """Parse a BDL file into a dict with keys: Deal, Dealer, Contract, Declarer,
    Vulnerable, Auction_data, Play, Play_data, etc."""
    board = {}
    current_section = None
    section_lines = []

    with open(path, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n\r')
            stripped = line.strip()

            # BDL tag format: "TagName    :   value"
            if ':' in stripped and not stripped.startswith('.') and not stripped.startswith('#'):
                parts = stripped.split(':', 1)
                tag = parts[0].strip()
                value = parts[1].strip()

                # Flush section
                if current_section and section_lines:
                    board[current_section] = list(section_lines)
                    section_lines = []
                    current_section = None

                if tag == 'Dealer':
                    board['Dealer'] = value[0].upper()
                elif tag == 'Vuln':
                    board['Vulnerable'] = value.replace('---', 'None')
                elif tag == 'Contract':
                    # "4h   North" → extract contract and declarer
                    cparts = value.split()
                    if cparts:
                        board['Contract'] = cparts[0].upper()
                    if len(cparts) > 1:
                        board['Declarer'] = cparts[1][0].upper()
                elif tag == 'Bids':
                    current_section = 'Auction_data'
                    section_lines = []
                elif tag == 'Tricks' or tag.strip() == '':
                    if current_section == 'Play_data' or tag == 'Tricks':
                        if tag == 'Tricks':
                            current_section = 'Play_data'
                            section_lines = []
                        # Parse trick line
                        trick_match = re.match(r'\s*(\d+)\s+(\w)\s+(.*)', value)
                        if trick_match:
                            leader = trick_match.group(2).upper()
                            if 'Play' not in board:
                                board['Play'] = leader
                            cards_part = trick_match.group(3)
                            # Extract card strings (like sA+ hK c7 d3)
                            raw_cards = re.findall(r'[shdc][AKQJT98765432]+', cards_part, re.I)
                            if len(raw_cards) >= 4:
                                # Convert to standard: sA → SA, hK → HK
                                std_cards = [c[0].upper() + c[1:].replace('T', '10') for c in raw_cards[:4]]
                                section_lines.append(' '.join(std_cards))
                elif tag == 'Cards':
                    pass  # Cards are display-only; we get hands from Deal tag

            # Continuation lines (start with spaces and ':')
            elif stripped.startswith(':') and current_section:
                value = stripped[1:].strip()
                if current_section == 'Play_data':
                    trick_match = re.match(r'\s*(\d+)\s+(\w)\s+(.*)', value)
                    if trick_match:
                        cards_part = trick_match.group(3)
                        raw_cards = re.findall(r'[shdc][AKQJT98765432]+', cards_part, re.I)
                        if len(raw_cards) >= 4:
                            std_cards = [c[0].upper() + c[1:].replace('T', '10') for c in raw_cards[:4]]
                            section_lines.append(' '.join(std_cards))
                elif current_section == 'Auction_data':
                    # Skip separator lines (--- or ===)
                    if not re.match(r'^[-=]+$', value) and value:
                        section_lines.append(value)

    if current_section and section_lines:
        board[current_section] = section_lines

    return board


def bdl_to_ppl(bdl_path: str, output_path: str = None) -> bytes:
    """Convert a BDL or PBN file to PPL format.

    Parses the file, extracts hands/bidding/contract/play, and writes a .ppl file.
    Returns the 774-byte PPL data.
    """
    import bridge_harness as bh

    # Try PBN format first, then BDL
    boards = bh.parse_pbn_file(bdl_path)
    if boards and 'Deal' in boards[0]:
        board = boards[0]
    else:
        board = _parse_bdl_file(bdl_path)

    deal_str = board.get('Deal', '')
    if not deal_str:
        raise ValueError("No Deal tag found in file")

    hands = bh.parse_pbn_deal_string(deal_str)
    dealer = board.get('Dealer', 'N').strip().upper()[0]
    contract = board.get('Contract', 'Pass')
    declarer = board.get('Declarer', dealer).strip().upper()[0]

    # Parse bidding
    bidding = []
    auction_data = board.get('Auction_data', [])
    for line in auction_data:
        for tok in line.split():
            if tok.startswith('{'):
                break
            bidding.append(tok)

    # Parse play
    play_tricks = None
    play_leaders = None
    play_data = board.get('Play_data', [])
    opening_leader = board.get('Play', '').strip().upper()
    if play_data and opening_leader:
        SEATS = ['N', 'E', 'S', 'W']
        RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
                    '10':10,'J':11,'Q':12,'K':13,'A':14}
        li = SEATS.index(opening_leader)
        col_order = [SEATS[(li + p) % 4] for p in range(4)]

        # Determine trump
        trump = None
        cup = contract.upper().replace('X', '')
        for t in ['S', 'H', 'D', 'C']:
            if t in cup and 'NT' not in cup:
                trump = t
                break

        play_tricks = []
        play_leaders = []
        leader_idx = li

        for line in play_data:
            raw_cards = line.split()
            if len(raw_cards) < 4:
                continue
            trick = {}
            for i, card_str in enumerate(raw_cards[:4]):
                card = card_str.upper()
                if len(card) == 2 and card[1] == 'T':
                    card = card[0] + '10'
                trick[col_order[i]] = card

            play_tricks.append(trick)
            play_leaders.append(SEATS[leader_idx])

            # Determine winner for next leader
            leader_card = trick[SEATS[leader_idx]]
            led_suit = leader_card[0]
            best_seat = SEATS[leader_idx]
            best_trump = (led_suit == trump) if trump else False
            best_val = RANK_VAL.get(leader_card[1:], 0)
            for p in range(1, 4):
                s = SEATS[(leader_idx + p) % 4]
                c = trick[s]
                is_t = (c[0] == trump) if trump else False
                v = RANK_VAL.get(c[1:], 0)
                if is_t and not best_trump:
                    best_seat, best_trump, best_val = s, True, v
                elif is_t and best_trump and v > best_val:
                    best_seat, best_val = s, v
                elif c[0] == led_suit and not best_trump and v > best_val:
                    best_seat, best_val = s, v
            leader_idx = SEATS.index(best_seat)

    name = board.get('Event', '')[:9]
    description = board.get('Description', '')[:35]

    ppl_data = build_ppl(
        hands, dealer, declarer, contract, bidding,
        play_tricks, play_leaders, name, description,
    )

    if output_path:
        Path(output_path).write_bytes(ppl_data)

    return ppl_data


def decode_from_known_deal(ppl: dict, known_hands: list):
    """Given a PPL and the known [N,E,S,W] hands, derive INDEX_TO_CARD.

    known_hands: [[north_cards], [east_cards], [south_cards], [west_cards]]
    where each card is like 'SA', 'HK', 'D10', 'C2', etc.

    Prints the mapping for inclusion in this file.
    """
    perm = ppl['card_perm']

    # Try all possible groupings (groups of 13, and all 24 seat permutations)
    from itertools import permutations as perms

    seat_names = ['N', 'E', 'S', 'W']
    known_sets = [set(h) for h in known_hands]

    # The permutation might group cards as: first 13 = one player, etc.
    # Or it might use some other grouping.  Try groups of 13 first.
    groups = [set(perm[i*13:(i+1)*13]) for i in range(4)]

    for seat_perm in perms(range(4)):
        # Build index→card mapping
        mapping = {}
        valid = True
        for gi, si in enumerate(seat_perm):
            group_indices = list(perm[gi*13:(gi+1)*13])
            cards = list(known_hands[si])
            if len(group_indices) != len(cards):
                valid = False
                break
            for idx, card in zip(sorted(group_indices), sorted(cards)):
                if idx in mapping and mapping[idx] != card:
                    valid = False
                    break
                mapping[idx] = card
            if not valid:
                break

        if valid and len(mapping) == 52:
            print(f"Encoding decoded! Group order: "
                  f"{[seat_names[seat_perm[g]] for g in range(4)]}")
            print()
            print("INDEX_TO_CARD = {")
            for i in range(52):
                print(f"    {i}: '{mapping[i]}',")
            print("}")
            return mapping

    print("Could not determine encoding from groups of 13.")
    print("The card permutation values are:")
    for i in range(4):
        group = perm[i*13:(i+1)*13]
        print(f"  Group {i}: {sorted(group)}")
    print()
    print("Known hands:")
    for i, name in enumerate(seat_names):
        print(f"  {name}: {sorted(known_hands[i])}")
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Bridge Baron .ppl file reader and PBN converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('file', help='.ppl or .bdl/.pbn file to convert')
    parser.add_argument('-n', '--deal-number', type=int, default=None,
                        help='BB12 deal number (for reference only)')
    parser.add_argument('--bdl', action='store_true',
                        help='Output BDL format (Q-Plus Bridge log)')
    parser.add_argument('--to-ppl', metavar='OUTPUT',
                        help='Convert .bdl/.pbn to .ppl (specify output path)')
    parser.add_argument('--decode', action='store_true',
                        help='Decode card encoding using a known deal (prompts for hands)')
    parser.add_argument('--info', action='store_true',
                        help='Show file metadata and decoded game info')
    args = parser.parse_args()

    if not args.decode:
        if args.to_ppl:
            # Convert BDL/PBN → PPL
            ppl_data = bdl_to_ppl(args.file, args.to_ppl)
            print(f"Written {len(ppl_data)} bytes to {args.to_ppl}")
            return

        ppl = parse_ppl(args.file)
        try:
            if args.bdl:
                print(ppl_to_bdl(args.file, args.deal_number))
            else:
                print(ppl_to_pbn(args.file, args.deal_number))
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.info:
            dn = args.deal_number
            if dn is None:
                try:
                    dn = _guess_deal_number(args.file)
                except ValueError:
                    pass
            game = ppl_decode_game(ppl)
            print(f"Name: {ppl['name']}")
            print(f"Description: {ppl['description']}")
            print(f"Commentary: {ppl['commentary']}")
            print(f"Dealer: {game['dealer']}")
            print(f"Contract: {game['contract']} by {game['declarer']}")
            print(f"Bidding: {' '.join(game['bidding'])}")
            if dn is not None:
                hands = bb12_deal_from_number(dn)
                for i, seat in enumerate(['North', 'East', 'South', 'West']):
                    print(f"  {seat}: {hands[i]}")
        return

    if args.decode:
        ppl = parse_ppl(args.file)
        print()
        print("Enter the 4 hands as PBN notation (dots between suits, SHDC order).")
        print("Example: AKQ72.954.632.J8")
        print()

        hands = []
        for seat in ['North', 'East', 'South', 'West']:
            while True:
                raw = input(f"  {seat}: ").strip()
                try:
                    import re
                    suits_str = raw.split('.')
                    if len(suits_str) != 4:
                        print("    Need 4 dot-separated suits (SHDC). Try again.")
                        continue
                    cards = []
                    suit_chars = 'SHDC'
                    for si, suit_cards in enumerate(suits_str):
                        if not suit_cards or suit_cards == '-':
                            continue
                        for rank in re.findall(r'10|T|[AKQJ98765432]', suit_cards):
                            if rank == 'T':
                                rank = '10'
                            cards.append(suit_chars[si] + rank)
                    if len(cards) != 13:
                        print(f"    Got {len(cards)} cards, need 13. Try again.")
                        continue
                    hands.append(cards)
                    break
                except Exception as e:
                    print(f"    Error: {e}. Try again.")

        mapping = decode_from_known_deal(ppl, hands)
        if mapping is None:
            print("\nCould not decode. Try a deal where each player holds a single suit.")


if __name__ == '__main__':
    main()
