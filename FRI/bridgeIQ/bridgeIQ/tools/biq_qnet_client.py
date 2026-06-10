"""Plan 3 — biq's Q-NET client. Connects to a Q-Plus bridge-server
over the network and plays one seat using biq's bidder and cardplay
engine (MC+DDS).

Protocol (decoded from capture):
- Plain text, newline-terminated.
- `"<command>" [arg1] [arg2] ...`
- Server is authoritative; broadcasts every bid/card to all clients.
- Client SENDS bids/cards only for its claimed seat.

Usage:
    python3 tools/biq_qnet_client.py \\
        --host 127.0.0.1 --port 5555 --seat E --system SAYC

Connect via the proxy (`--port 5556`) for protocol logging in
parallel.
"""

import argparse
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


def _seat_of_pid(pid: int) -> Optional[str]:
    """Read the --seat value of a running biq_qnet_client.py process."""
    try:
        parts = open(f"/proc/{pid}/cmdline", "rb").read().split(b"\0")
        argv = [p.decode("utf-8", "replace") for p in parts if p]
    except OSError:
        return None
    if "--seat" in argv:
        i = argv.index("--seat")
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _kill_prior_instances(my_seat: Optional[str] = None) -> None:
    """Kill other biq_qnet_client.py processes holding the SAME seat —
    a stuck same-seat client blocks that seat at Q-Plus (`player_refused`
    or duplicate-TCP confusion). Instances on a DIFFERENT seat are left
    alone, so a biq+biq partnership (one client per seat, e.g. N and S)
    can run two at once. `my_seat=None` kills all (legacy behaviour)."""
    my_pid = os.getpid()
    try:
        out = subprocess.run(
            ["pgrep", "-f", "biq_qnet_client.py"],
            capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        return  # no pgrep available; skip
    others = []
    for line in out.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid == my_pid:
            continue
        if my_seat is not None and _seat_of_pid(pid) != my_seat:
            # Different seat (a partner) OR not-yet-readable cmdline (a
            # sibling still starting up) — leave it. We only clear a
            # stuck SAME-seat client, which always has a readable --seat.
            continue
        others.append(pid)
    if not others:
        return
    print(f"[biq_qnet] killing prior biq_qnet_client.py pids: "
          f"{others}", file=sys.stderr)
    for pid in others:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(0.7)
    # Force-kill survivors
    survivors = []
    for pid in others:
        try:
            os.kill(pid, 0)  # 0 = just check
            survivors.append(pid)
        except ProcessLookupError:
            pass
    for pid in survivors:
        print(f"[biq_qnet] force-killing pid {pid}", file=sys.stderr)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if survivors:
        time.sleep(0.3)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.engine import BridgeEngine
from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat,
                              Bid, Vulnerability, Contract, Trick)


# --- vocabulary lookups ----------------------------------------------------

_RANK_FROM_CHAR = {
    'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK,
    'T': Rank.TEN, '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
    '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
    '2': Rank.TWO,
}
_RANK_TO_CHAR = {r: c for c, r in _RANK_FROM_CHAR.items()}
_SUIT_FROM_CHAR = {
    's': Suit.SPADES, 'h': Suit.HEARTS,
    'd': Suit.DIAMONDS, 'c': Suit.CLUBS,
}
_SUIT_TO_CHAR = {s: c for c, s in _SUIT_FROM_CHAR.items()}
_SEAT_FROM_NAME = {
    'North': Seat.NORTH, 'East': Seat.EAST,
    'South': Seat.SOUTH, 'West': Seat.WEST,
    'N': Seat.NORTH, 'E': Seat.EAST,
    'S': Seat.SOUTH, 'W': Seat.WEST,
}
# accept lowercase too
for k, v in dict(_SEAT_FROM_NAME).items():
    _SEAT_FROM_NAME[k.lower()] = v


# --- protocol parsing / serialization --------------------------------------

_HDR_RE = re.compile(r'^"([^"]+)"\s*(.*)$')
_ARG_RE = re.compile(r'\[([^\]]*)\]')


def parse_message(line: str) -> Optional[Tuple[str, List[str]]]:
    """Parse one Q-NET line. Returns (command, args) or None."""
    line = line.rstrip('\r\n')
    m = _HDR_RE.match(line)
    if not m:
        return None
    cmd = m.group(1)
    args = _ARG_RE.findall(m.group(2))
    return cmd, args


def format_message(cmd: str, *args) -> bytes:
    parts = [f'"{cmd}"'] + [f'[{a}]' for a in args]
    return (' '.join(parts) + '\n').encode('latin-1')


def parse_pbn_hand(pbn_hand: str) -> Hand:
    """Parse a PBN hand like '.AJ964.A83.J8754' (suits in S-H-D-C order)."""
    suits = pbn_hand.split('.')
    if len(suits) != 4:
        raise ValueError(f"bad PBN hand: {pbn_hand!r}")
    cards = []
    suit_order = (Suit.SPADES, Suit.HEARTS,
                   Suit.DIAMONDS, Suit.CLUBS)
    for s, ranks_str in zip(suit_order, suits):
        for r_char in ranks_str:
            rank = _RANK_FROM_CHAR.get(r_char.upper())
            if rank is not None:
                cards.append(Card(suit=s, rank=rank))
    return Hand(cards=cards)


def parse_pbn_deal(pbn: str) -> Tuple[Seat, Vulnerability, dict]:
    """Parse 'new_deal_pbn' arg-3, e.g.:
    'S All N:.AJ964.A83.J8754 AQ9.82.KJ64.KQ32 JT54.KQ3.QT5.AT6 K87632.T75.972.9'
    The format is `<dealer> <vul> <hand_starter>:<hand> <hand> <hand> <hand>`.
    Note that dealer (first token) and hand_starter (the N:/E:/S:/W:
    seat that introduces the hand list) are SEPARATE — the PBN hands
    are listed starting from `hand_starter` regardless of who deals.

    Returns (dealer_seat, vulnerability, {seat: Hand}).
    """
    m = re.match(r'^\s*(\S+)\s+(\S+)\s+([NESW]):(.+)$', pbn.strip())
    if not m:
        raise ValueError(f"bad PBN deal: {pbn!r}")
    dealer = _SEAT_FROM_NAME[m.group(1)]
    vul_str = m.group(2)
    starter = _SEAT_FROM_NAME[m.group(3)]
    hands_part = m.group(4).strip()
    vul = {
        'None': Vulnerability.NONE,
        '-': Vulnerability.NONE,
        'NS': Vulnerability.NS,
        'EW': Vulnerability.EW,
        'All': Vulnerability.BOTH,
        'Both': Vulnerability.BOTH,
    }.get(vul_str, Vulnerability.NONE)
    hand_strs = hands_part.split(' ')
    if len(hand_strs) != 4:
        raise ValueError(f"expected 4 hands, got {len(hand_strs)}")
    hands = {}
    seat = starter
    for hs in hand_strs:
        hands[seat] = parse_pbn_hand(hs)
        seat = Seat((seat.value + 1) % 4)
    return dealer, vul, hands


def parse_bid_token(bid_str: str) -> Bid:
    s = bid_str.strip().lower()
    if s in ('p', 'pass', '-', ''):
        return Bid.make_pass()
    if s in ('x', 'dbl', 'double'):
        return Bid.make_double()
    if s in ('xx', 'rdbl', 'redouble'):
        return Bid.make_redouble()
    m = re.match(r'^([1-7])(nt|s|h|d|c)$', s)
    if not m:
        raise ValueError(f"bad bid token: {bid_str!r}")
    level = int(m.group(1))
    suit_tok = m.group(2)
    if suit_tok == 'nt':
        suit = Suit.NOTRUMP
    else:
        suit = _SUIT_FROM_CHAR[suit_tok]
    return Bid(level=level, suit=suit)


def format_bid(bid: Bid) -> str:
    if bid.is_pass:
        return ' p '
    if bid.is_double:
        return ' x '
    if bid.is_redouble:
        return 'xx '
    if bid.suit == Suit.NOTRUMP:
        return f'{bid.level}nt'
    return f'{bid.level}{_SUIT_TO_CHAR[bid.suit]} '


def parse_card_token(card_str: str) -> Card:
    s = card_str.strip()
    if len(s) < 2:
        raise ValueError(f"bad card token: {card_str!r}")
    suit = _SUIT_FROM_CHAR[s[0].lower()]
    rank = _RANK_FROM_CHAR[s[1].upper()]
    return Card(suit=suit, rank=rank)


def format_card(card: Card) -> str:
    return f'{_SUIT_TO_CHAR[card.suit]}{_RANK_TO_CHAR[card.rank]}'


# Declarer→dummy IPC for --pair: when biq's side declares, the DECLARER's
# client (which sees its own hand + the revealed dummy) computes the
# dummy's card to keep the line of play coherent, and drops it here; the
# DUMMY's client picks it up and submits it on its own connection (Q-Plus
# requires each seat's card from that seat's client). Keyed by deal label
# + play index so both clients agree; cleared each new deal.
_PAIR_IPC = Path(__file__).resolve().parent / "runs" / "pair_ipc"


# --- client ---------------------------------------------------------------

class BiqClient:
    def __init__(self, host: str, port: int, my_seat: Seat,
                  system: str = 'SAYC', name: str = 'biq',
                  num_samples: int = 50, verbose: bool = True,
                  log_path: Optional[str] = None,
                  system_file: Optional[str] = None,
                  auto_system: bool = False,
                  random_system: bool = False,
                  pair_mode: bool = False,
                  nopeek: bool = False):
        self.host = host
        self.port = port
        self.my_seat = my_seat
        self.my_name = name
        self.system = system
        self.system_file = system_file
        self.auto_system = auto_system
        self.random_system = random_system
        self.pair_mode = pair_mode
        self.nopeek = nopeek
        self.num_samples = num_samples
        self.verbose = verbose
        self._logfh = None
        if log_path:
            self._logfh = open(log_path, "a")
            # Fingerprint the bidder this run is ACTUALLY using — content hash
            # + a U1/U2/U3 marker (Case C). Three baselines were silently run
            # on a reverted bidder before this existed; run_preflight checks it.
            import hashlib
            try:
                _nb = (Path(__file__).resolve().parent.parent
                       / "backend" / "native_bidder.py").read_bytes()
                _fp = (f"{hashlib.sha1(_nb).hexdigest()[:10]} "
                       f"caseC={_nb.decode('latin-1').count('Case C')}")
            except OSError:
                _fp = "unknown"
            self._logfh.write(
                f"\n=== biq_qnet session {time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"seat={my_seat.name} system={system} port={port} "
                f"bidder={_fp} ===\n")
            self._logfh.flush()
        self.sock: Optional[socket.socket] = None
        self.buf = b''
        # Bridge state (reset per deal)
        self.engine = BridgeEngine()
        self.engine.cardplay_relax_inference = 3
        self.board: Optional[BoardState] = None
        self.auction: List[Bid] = []
        self.dealer: Optional[Seat] = None
        self.bidder_seat: Optional[Seat] = None
        self.contract: Optional[Contract] = None
        self.declarer: Optional[Seat] = None
        self.trick_leader: Optional[Seat] = None
        self.current_trick: List[Card] = []
        self.completed_tricks: List[Trick] = []
        self._begin_play_seen = False
        self.deal_label = ""
        if self.pair_mode:
            _PAIR_IPC.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str) -> None:
        line = f"[biq_qnet] {msg}"
        if self.verbose:
            print(line, file=sys.stderr)
        if self._logfh is not None:
            self._logfh.write(line + "\n")
            self._logfh.flush()

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.log(f"connected to {self.host}:{self.port}")

    def send(self, cmd: str, *args) -> None:
        data = format_message(cmd, *args)
        self.sock.sendall(data)
        self.log(f">> {data.decode('latin-1').rstrip()}")

    def recv_line(self) -> Optional[str]:
        while b'\n' not in self.buf:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                return None
            if not chunk:
                return None
            self.buf += chunk
        nl = self.buf.index(b'\n')
        line = self.buf[:nl].decode('latin-1')
        self.buf = self.buf[nl + 1:]
        self.log(f"<< {line}")
        return line

    def initialize_engine(self) -> None:
        if not self.engine.initialize():
            raise RuntimeError("failed to initialize BridgeEngine")
        self.engine.set_bidding_system(self.system)

    def handshake(self) -> bool:
        for s in ('north', 'east', 'south', 'west'):
            self.send("request_player_info", s)
        info_seen = 0
        while info_seen < 4:
            line = self.recv_line()
            if line is None:
                return False
            r = parse_message(line)
            if r and r[0] == 'set_player_info':
                info_seen += 1
        seat_name = self.my_seat.name.title()
        self.send("join_game", seat_name, self.my_name)
        while True:
            line = self.recv_line()
            if line is None:
                return False
            r = parse_message(line)
            if r and r[0] == 'player_accepted':
                break
        self.send("request_config")
        while True:
            line = self.recv_line()
            if line is None:
                return False
            r = parse_message(line)
            if r and r[0] == 'set_config':
                self._apply_server_config(r[1][0] if len(r[1]) >= 1 else "")
                break
        self.log(f"handshake complete; joined as {seat_name}")
        return True

    def run(self) -> None:
        self.initialize_engine()
        self.connect()
        if not self.handshake():
            self.log("handshake failed; exiting")
            return
        while True:
            line = self.recv_line()
            if line is None:
                self.log("connection closed")
                return
            r = parse_message(line)
            if not r:
                continue
            cmd, args = r
            try:
                self._dispatch(cmd, args)
            except Exception as e:
                self.log(f"error handling {cmd}({args}): {e}")
                import traceback
                traceback.print_exc(file=sys.stderr)

    # --- protocol dispatch ------------------------------------------------

    def _dispatch(self, cmd: str, args: List[str]) -> None:
        if cmd == "new_deal_pbn":
            self._on_new_deal(args)
        elif cmd == "start_bidding":
            self._on_start_bidding(args)
        elif cmd == "bid":
            self._on_bid(args)
        elif cmd == "begin_play":
            self._on_begin_play(args)
        elif cmd == "card":
            self._on_card(args)
        elif cmd == "report_score":
            self._on_report_score(args)
        elif cmd == "set_config":
            self._apply_server_config(args[0] if args else "")
        elif cmd == "server_stopped":
            self.log("server stopped — exiting")
            sys.exit(0)
        # other messages ignored silently

    def _maybe_reload_system(self) -> None:
        """Re-read --system-file (if given) so the NEXT deal can use a
        different bidding system without restarting biq. Applied only
        at deal boundaries, never mid-auction. get_system(self.system)
        is already re-read per bid, so updating self.system is enough."""
        if not self.system_file:
            return
        try:
            new = Path(self.system_file).read_text().strip()
        except OSError:
            return
        if new and new != self.system:
            self.log(f"bidding system: {self.system} -> {new} "
                     f"(from {self.system_file})")
            self.system = new
            try:
                self.engine.set_bidding_system(self.system)
            except Exception as ex:
                self.log(f"set_bidding_system({new}) warn: {ex}")

    def _apply_server_config(self, config_str: str) -> None:
        """Parse the server's set_config. The `conv.bidding.<side>` field
        tells us the system Q-Plus has biq's partnership playing (biq is
        E/W or N/S). With --auto-system, set biq's own system to match so
        biq and its Q-Plus bot partner bid a mutually-intelligible system."""
        if not config_str:
            return
        cfg = {}
        for part in config_str.split(";"):
            if "=" in part:
                k, _, v = part.partition("=")
                cfg[k.strip()] = v.strip()
        side = "N/S" if self.my_seat.is_ns() else "E/W"
        code = cfg.get(f"conv.bidding.{side}")
        if not code:
            return
        if not self.auto_system:
            self.log(f"server reports {side} system = {code} "
                     f"(biq stays on {self.system}; pass --auto-system "
                     f"to follow it)")
            return
        from backend.bidding_systems import system_name_for_qplus_code
        name = system_name_for_qplus_code(code)
        if name and name != self.system:
            self.log(f"auto-system: {side}={code} → {self.system} → {name}")
            self.system = name
            try:
                self.engine.set_bidding_system(self.system)
            except Exception as ex:
                self.log(f"set_bidding_system({name}) warn: {ex}")
        elif not name:
            self.log(f"auto-system: unrecognised Q-Plus code '{code}' "
                     f"for {side}; biq stays on {self.system}")

    def _maybe_random_system(self) -> None:
        """With --random-system, pick a fresh bidding system at random
        for each deal (robustness/stress test). NOTE: biq's bot partner
        stays on Q-Plus's fixed system, so this deliberately creates a
        partnership mismatch — use --auto-system for clean measurement."""
        if not self.random_system:
            return
        import random
        from backend.bidding_systems import list_systems
        choice = random.choice(list_systems())
        if choice != self.system:
            self.log(f"random-system: {self.system} -> {choice}")
            self.system = choice
            try:
                self.engine.set_bidding_system(self.system)
            except Exception as ex:
                self.log(f"set_bidding_system({choice}) warn: {ex}")

    def _on_new_deal(self, args: List[str]) -> None:
        self._maybe_reload_system()
        self._maybe_random_system()
        if self.auto_system:
            # re-poll partner's system each deal (handled async by
            # _dispatch → _apply_server_config before bidding starts)
            self.send("request_config")
        # args[0]: deal-info tag (e.g. 'N 39 9949'); 'N' here is NOT
        #          the dealer (it's the hand-display starter or a
        #          session tag — varies). The authoritative dealer
        #          lives in the PBN field (args[3]).
        # args[1]: scoring (e.g. 'IMP')
        # args[2]: deal label
        # args[3]: PBN deal '<dealer> <vul> <starter>:<hand> <hand> <hand> <hand>'
        self.deal_label = args[2] if len(args) > 2 else ""
        if self.pair_mode:
            # New deal: clear last deal's consumed dummy-IPC + system-agreement
            # files. Both clients are between deals here (no cardplay in
            # flight), so this is race-free; cardplay writes come seconds later.
            for f in list(_PAIR_IPC.glob("*.card")) + \
                    list(_PAIR_IPC.glob("*.sys.*")):
                try:
                    f.unlink()
                except OSError:
                    pass
        dealer, vul, hands = parse_pbn_deal(args[3])
        self.dealer = dealer
        try:
            board_num = int(args[0].split()[1])
        except (IndexError, ValueError):
            board_num = 0
        self.board = BoardState(
            board_number=board_num,
            dealer=self.dealer,
            vulnerability=vul,
            hands=hands,
        )
        self.auction = []
        self.bidder_seat = self.dealer
        self.contract = None
        self.declarer = None
        self.trick_leader = None
        self.current_trick = []
        self.completed_tricks = []
        self._begin_play_seen = False
        self.log(f"NEW DEAL #{board_num}: dealer={self.dealer.name} "
                 f"vul={vul.name}")
        my = hands[self.my_seat]
        by_suit = {Suit.SPADES: [], Suit.HEARTS: [],
                    Suit.DIAMONDS: [], Suit.CLUBS: []}
        for c in my.cards:
            by_suit[c.suit].append(c.rank)
        for s in (Suit.SPADES, Suit.HEARTS,
                   Suit.DIAMONDS, Suit.CLUBS):
            ranks = sorted(by_suit[s], key=lambda r: r.value)
            chars = ''.join(_RANK_TO_CHAR[r] for r in ranks) or '-'
            self.log(f"  my {_SUIT_TO_CHAR[s].upper()}: {chars}")
        # Publish our system early (pair mode) so the partner client has the
        # full deal-setup window to see it before bidding's agreement check.
        self._publish_system()

    def _on_start_bidding(self, args: List[str]) -> None:
        self.log("=== auction begins ===")
        # Before any bid: in pair mode (biq plays BOTH seats of a side via two
        # client processes), confirm this client and its partner client are on
        # the SAME bidding system. A divergence here — e.g. one client synced
        # the new deal's system and the other lagged on random/sequential
        # cycling — would have the two biq seats bid as different partnerships
        # and corrupt the auction. Loud WARNING on mismatch; no-op otherwise.
        self._verify_partner_system()
        if self.bidder_seat == self.my_seat:
            time.sleep(0.4)
            self._send_my_bid()

    def _publish_system(self) -> None:
        """Pair mode: publish this client's current system for the deal so the
        partner client can verify agreement. Called EARLY (at new deal) to give
        the partner the whole deal-setup window of lead time, and again right
        before bidding in case set_config changed the system in between."""
        if not self.pair_mode or not self.deal_label:
            return
        try:
            (_PAIR_IPC / f"{self.deal_label}.sys.{self.my_seat.to_char()}"
             ).write_text(self.system)
        except OSError as e:
            self.log(f"system IPC write failed: {e}")

    def _verify_partner_system(self, timeout: float = 8.0) -> None:
        """Pair mode only: confirm the partner client is on the SAME bidding
        system before the auction starts. Re-publishes ours first (the system
        may have just changed via set_config), then polls for the partner's —
        which it already published at new-deal, so this normally returns at
        once and only waits if the partner is genuinely slow/gone."""
        if not self.pair_mode or not self.deal_label:
            return
        self._publish_system()
        mine_c = self.my_seat.to_char()
        partner = self.my_seat.partner()
        p = _PAIR_IPC / f"{self.deal_label}.sys.{partner.to_char()}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                theirs = p.read_text().strip()
            except OSError:
                theirs = ""
            if theirs:
                if theirs == self.system:
                    self.log(f"system check OK — {mine_c} and "
                             f"{partner.to_char()} both on {self.system}")
                else:
                    self.log(
                        f"*** SYSTEM MISMATCH on {self.deal_label}: "
                        f"{mine_c}={self.system} but "
                        f"{partner.to_char()}={theirs}. The two biq seats are "
                        f"on DIFFERENT systems — this auction is UNRELIABLE. "
                        f"Use a FIXED system (not random/sequential) for a "
                        f"clean measurement.")
                return
            time.sleep(0.1)
        self.log(f"system check — partner {partner.to_char()} did not publish "
                 f"a system within {timeout:.0f}s (partner not a biq client, "
                 f"or crashed); skipping agreement check")

    def _on_bid(self, args: List[str]) -> None:
        if len(args) < 2:
            return
        seat = _SEAT_FROM_NAME[args[0]]
        bid = parse_bid_token(args[1])
        self.auction.append(bid)
        # Q-Plus echoes our own bid back; advance bidder pointer
        # regardless of who originated it.
        self.bidder_seat = Seat((self.bidder_seat.value + 1) % 4)
        if self._auction_complete():
            self._finalize_auction()
            return
        if self.bidder_seat == self.my_seat:
            time.sleep(0.4)
            self._send_my_bid()

    def _auction_complete(self) -> bool:
        if len(self.auction) >= 4 \
                and all(b.is_pass for b in self.auction[-3:]) \
                and any(not b.is_pass for b in self.auction):
            return True
        if len(self.auction) == 4 \
                and all(b.is_pass for b in self.auction):
            return True
        return False

    def _finalize_auction(self) -> None:
        contract = self._derive_contract()
        if contract is None:
            self.log("auction passed out — no contract")
            self.contract = None
            return
        self.contract = contract
        self.declarer = contract.declarer
        self.board.contract = contract
        self.board.auction = list(self.auction)
        self.log(f"CONTRACT: {contract.level}"
                 f"{contract.suit.to_char()} by "
                 f"{contract.declarer.name}")
        self.trick_leader = Seat(
            (contract.declarer.value + 1) % 4)

    def _derive_contract(self) -> Optional[Contract]:
        """Identify declarer + final-strain from the finished auction."""
        level = 0
        suit = None
        declarer = None
        doubled = False
        redoubled = False
        for i, b in enumerate(self.auction):
            if not b.is_pass and not b.is_double and not b.is_redouble:
                level = b.level
                suit = b.suit
                bidder = Seat((self.dealer.value + i) % 4)
                side_ns = bidder.is_ns()
                for j, bj in enumerate(self.auction[:i + 1]):
                    if (not bj.is_pass and not bj.is_double
                            and not bj.is_redouble and bj.suit == suit):
                        j_seat = Seat(
                            (self.dealer.value + j) % 4)
                        if j_seat.is_ns() == side_ns:
                            declarer = j_seat
                            break
                doubled = False
                redoubled = False
            elif b.is_double:
                doubled = True
            elif b.is_redouble:
                redoubled = True
        if level == 0 or declarer is None:
            return None
        return Contract(level=level, suit=suit, declarer=declarer,
                          doubled=doubled, redoubled=redoubled)

    def _send_my_bid(self) -> None:
        try:
            from backend.bidding_systems import get_system
            from backend.native_bidder import (decide_bid,
                                                 evaluate_hand,
                                                 parse_auction)
            state = parse_auction(
                self.my_seat, self.board.dealer,
                list(self.auction),
                vulnerability=self.board.vulnerability)
            e = evaluate_hand(self.board.hands[self.my_seat])
            sys_ = get_system(self.system)
            bid = decide_bid(state, e, sys_)
        except Exception as ex:
            self.log(f"bidder error: {ex}; defaulting to pass")
            bid = Bid.make_pass()
        # Q-Plus does NOT echo our own bid back, so we must update
        # local state ourselves to keep the auction tracker in sync.
        self.auction.append(bid)
        self.bidder_seat = Seat((self.bidder_seat.value + 1) % 4)
        self.send("bid", self.my_seat.name.title(), format_bid(bid))
        # Auction may end on our bid (3 passes after a non-pass).
        if self._auction_complete():
            self._finalize_auction()

    def _i_control(self, seat: Seat) -> bool:
        """Which seats biq plays the cards for.

        Q-Plus routes BOTH seats of an Extern client's partnership to
        that client whenever the partnership is DECLARING — declarer
        and dummy are both client-controlled (it flips the partner seat
        to Extern too). So when biq's side declares, biq plays BOTH of
        its seats, whether biq is nominally the declarer OR the dummy.
        When biq's side is defending, biq plays only its own seat; its
        partner is a Q-Plus bot."""
        if self.contract is None or self.declarer is None:
            return seat == self.my_seat
        if self.pair_mode:
            # N and S are SEPARATE Extern connections, and Q-Plus wants each
            # seat's card from its OWN client. So the DECLARER's client is
            # responsible for its own seat (plays it) AND the dummy seat
            # (computes the card and hands it to the dummy's client via IPC,
            # so the line of play stays coherent). The dummy/defenders act on
            # their own seat only. (Submitting the dummy's card directly from
            # the declarer desyncs Q-Plus — it stalls "waiting for the card
            # of <declarer>", seen live on 6281-03.)
            if self.declarer == self.my_seat:
                return seat in (self.my_seat, self.declarer.partner())
            return seat == self.my_seat
        # Single client controlling both N/S Extern seats: when our side
        # declares, this one client plays BOTH seats.
        my_side_declares = (self.declarer.is_ns() == self.my_seat.is_ns())
        if my_side_declares:
            return seat.is_ns() == self.my_seat.is_ns()
        return seat == self.my_seat

    def _on_begin_play(self, args: List[str]) -> None:
        # Multiple begin_play messages observed (server broadcasts per
        # seat). Send our ack once.
        if not self._begin_play_seen:
            self._begin_play_seen = True
            self.send("begin_play")
            self.log("=== play begins ===")
        if (self.contract is not None
                and self._i_control(self.trick_leader)
                and not self.current_trick):
            time.sleep(0.4)
            self._send_my_card(self.trick_leader)

    def _on_card(self, args: List[str]) -> None:
        if len(args) < 2:
            return
        seat = _SEAT_FROM_NAME[args[0]]
        card = parse_card_token(args[1])
        try:
            self.board.hands[seat].cards.remove(card)
        except ValueError:
            self.log(f"warn: card {format_card(card)} not found in "
                     f"{seat.name}'s hand (state drift?)")
        self.current_trick.append(card)
        if len(self.current_trick) == 4:
            winner_idx = self._trick_winner(self.current_trick)
            winner_seat = Seat(
                (self.trick_leader.value + winner_idx) % 4)
            self.completed_tricks.append(Trick(
                cards=list(self.current_trick),
                leader=self.trick_leader,
                winner=winner_seat))
            self.log(f"  trick won by {winner_seat.name}")
            self.trick_leader = winner_seat
            self.current_trick = []
            if self._i_control(winner_seat):
                time.sleep(0.4)
                self._send_my_card(winner_seat)
        else:
            next_seat = Seat(
                (self.trick_leader.value
                 + len(self.current_trick)) % 4)
            if self._i_control(next_seat):
                time.sleep(0.4)
                self._send_my_card(next_seat)

    def _trick_winner(self, cards: List[Card]) -> int:
        trump = (self.contract.suit
                 if self.contract is not None
                 and self.contract.suit != Suit.NOTRUMP
                 else None)
        lead = cards[0].suit
        best_idx = 0
        best = cards[0]
        for i in range(1, 4):
            c = cards[i]
            cand_t = trump is not None and c.suit == trump
            best_t = trump is not None and best.suit == trump
            if cand_t and not best_t:
                best_idx, best = i, c
            elif cand_t and best_t and c.rank.value < best.rank.value:
                best_idx, best = i, c
            elif not cand_t and not best_t:
                if c.suit == lead and c.rank.value < best.rank.value:
                    best_idx, best = i, c
        return best_idx

    def _ipc_path(self) -> Path:
        # Keyed by deal + play index (cards played so far this deal); both
        # clients are at the same index when it's the dummy's turn.
        idx = len(self.completed_tricks) * 4 + len(self.current_trick)
        return _PAIR_IPC / f"{self.deal_label}_{idx}.card"

    def _write_dummy_ipc(self, seat: Seat, card: Card) -> None:
        p = self._ipc_path()
        try:
            tmp = p.with_suffix(".tmp")
            tmp.write_text(format_card(card))
            tmp.replace(p)               # atomic publish
            self.log(f"declarer→dummy {seat.name} {format_card(card)} "
                     f"(IPC {p.name})")
        except OSError as e:
            self.log(f"dummy IPC write failed: {e}")

    def _read_dummy_ipc(self, timeout: float = 30.0) -> Optional[Card]:
        p = self._ipc_path()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if p.exists():
                try:
                    card = parse_card_token(p.read_text().strip())
                    try:
                        p.unlink()
                    except OSError:
                        pass
                    return card
                except Exception:
                    return None
            time.sleep(0.1)
        self.log(f"dummy IPC timeout ({p.name}) — falling back to own engine")
        return None

    def _legal_fallback_card(self, seat: Seat) -> Optional[Card]:
        """A safe legal card with NO DDS — used when the MC child crashes or
        hangs. Lowest card of the led suit (else lowest card)."""
        lead = self.current_trick[0].suit if self.current_trick else None
        legal = [c for c in self.board.hands[seat].cards
                 if lead is None or c.suit == lead]
        if not legal:
            legal = list(self.board.hands[seat].cards)
        if not legal:
            return None
        return max(legal, key=lambda c: c.rank.value)

    def _choose_card(self, seat: Seat) -> Optional[Card]:
        """Card for `seat` via the MC+DDS engine, ISOLATED IN A FORKED CHILD.

        libdds can SEGFAULT under load — uncatchable in-process, it would kill
        the client and wedge the whole match (seen live on a 64-board run at
        120 samples). So we fork: the child runs the DDS-heavy MC, writes the
        card to a pipe, and os._exit(0)s (skipping the libdds thread teardown
        that itself segfaults). A crash/hang in the child costs ONE card — the
        parent falls back to a legal card — never the client. The parent never
        runs DDS itself, so it can't be killed by it."""
        board = BoardState(
            board_number=self.board.board_number,
            dealer=self.board.dealer,
            vulnerability=self.board.vulnerability,
            hands=self.board.hands,
            auction=list(self.auction),
            contract=self.contract,
            tricks=list(self.completed_tricks),
        )
        cur = list(self.current_trick)
        # NO-PEEK engine: pure technique, never samples/solves hidden hands.
        # In a live Q-NET game biq only holds its own + dummy cards anyway, so
        # this is the natural fit — and it needs no DDS, hence no fork/segfault.
        if self.nopeek:
            from backend import nopeek as _nopeek
            try:
                card = _nopeek.decide(board, seat, current_trick_cards=cur)
                if card is not None:
                    return card
            except Exception as e:
                self.log(f"nopeek error for {seat.name}: {e}")
            return self._legal_fallback_card(seat)
        try:
            r, w = os.pipe()
            pid = os.fork()
        except OSError:
            # fork unavailable — best-effort in-process (old behaviour)
            try:
                resp = self.engine.get_mc_card_play(
                    board, seat, current_trick_cards=cur,
                    num_samples=self.num_samples)
                if resp.action is not None:
                    return resp.action
            except Exception:
                pass
            return self._legal_fallback_card(seat)

        if pid == 0:                       # ---- child ----
            try:
                os.close(r)
            except OSError:
                pass
            try:
                resp = self.engine.get_mc_card_play(
                    board, seat, current_trick_cards=cur,
                    num_samples=self.num_samples)
                if resp.action is not None:
                    os.write(w, format_card(resp.action).encode("latin-1"))
            except Exception:
                pass
            finally:
                try:
                    os.close(w)
                except OSError:
                    pass
                os._exit(0)              # skip libdds teardown segfault

        # ---- parent ----
        import select
        os.close(w)
        data = b""
        deadline = time.time() + getattr(self, "card_timeout", 30.0)
        try:
            while time.time() < deadline:
                rl, _, _ = select.select([r], [], [], deadline - time.time())
                if not rl:
                    break
                chunk = os.read(r, 16)
                if not chunk:
                    break
                data += chunk
        except OSError:
            pass
        finally:
            try:
                os.close(r)
            except OSError:
                pass
        # reap; kill if the child is still alive (hung / mid-crash)
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if done == 0:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
        except (ChildProcessError, ProcessLookupError):
            pass
        if data.strip():
            try:
                return parse_card_token(data.decode("latin-1"))
            except Exception:
                pass
        self.log(f"MC child produced no card for {seat.name} "
                 f"(libdds crash/hang) — playing a legal fallback")
        return self._legal_fallback_card(seat)

    def _play_card(self, seat: Seat, card: Card) -> None:
        """Submit `card` for `seat` on this connection + advance state.
        Q-Plus doesn't echo our own card, so we update local state here."""
        try:
            self.board.hands[seat].cards.remove(card)
        except ValueError:
            pass
        self.current_trick.append(card)
        self.send("card", seat.name.title(), format_card(card))
        if len(self.current_trick) == 4:
            winner_idx = self._trick_winner(self.current_trick)
            winner_seat = Seat((self.trick_leader.value + winner_idx) % 4)
            self.completed_tricks.append(Trick(
                cards=list(self.current_trick),
                leader=self.trick_leader, winner=winner_seat))
            self.log(f"  trick won by {winner_seat.name}")
            self.trick_leader = winner_seat
            self.current_trick = []
            if self._i_control(winner_seat):
                time.sleep(0.4)
                self._send_my_card(winner_seat)

    def _send_my_card(self, seat: Optional[Seat] = None) -> None:
        if seat is None:
            seat = self.my_seat
        # Pair-mode declarer/dummy coordination (keeps the line coherent
        # AND satisfies Q-Plus's per-connection card routing).
        if self.pair_mode and self.declarer is not None:
            dummy = self.declarer.partner()
            if self.declarer == self.my_seat and seat == dummy:
                # I'm declarer choosing the DUMMY's card: compute it (I see
                # both declaring hands) and hand it to the dummy's client.
                # The dummy's CONNECTION submits it; I'll get it back as a
                # broadcast, which advances my state.
                card = self._choose_card(seat)
                if card is not None:
                    self._write_dummy_ipc(seat, card)
                return
            if dummy == self.my_seat and seat == self.my_seat:
                # I'm the dummy: play the card the DECLARER chose for me.
                card = self._read_dummy_ipc()
                if card is None:                       # fallback: own engine
                    card = self._choose_card(seat)
                if card is not None:
                    self._play_card(seat, card)
                else:
                    self.log(f"no cards left in {seat.name}, cannot play")
                return
        card = self._choose_card(seat)
        if card is None:
            self.log(f"no cards left in {seat.name}, cannot play")
            return
        self._play_card(seat, card)

    def _on_report_score(self, args: List[str]) -> None:
        self.log(f"SCORE: {args[0] if args else ''}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="biq Q-NET client — joins a Q-Plus bridge "
                     "server and plays one seat with biq's engines")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True,
                   help="Q-Plus server port (or proxy port if "
                        "logging the session)")
    p.add_argument("--seat", choices=["N", "E", "S", "W"],
                   required=True)
    p.add_argument("--system", default="SAYC",
                   help="biq bidding system (default SAYC)")
    p.add_argument("--name", default="biq",
                   help="display name to send in join_game")
    p.add_argument("--num-samples", type=int, default=50,
                   help="MC samples per cardplay decision (50 balances finesse "
                        "accuracy vs the libdds crash rate; 120 crashed DDS "
                        "~45x/64-board run → weak fallback cards)")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--log", default=None,
                   help="append all session output (handshake, deals, "
                        "bids, cards, scores) to this file; stderr-only "
                        "if omitted")
    p.add_argument("--system-file", default=None,
                   help="path to a file holding a bidding-system name "
                        "(e.g. SAYC, StandardAcol, TwoOverOne); biq "
                        "re-reads it at the start of each deal, so "
                        "writing a new name switches biq's system for "
                        "the NEXT deal without restarting")
    p.add_argument("--auto-system", action="store_true",
                   help="sync biq's bidding system to whatever Q-Plus "
                        "reports for biq's side (conv.bidding.E/W or "
                        "N/S in set_config), re-polled each deal, so "
                        "biq and its Q-Plus bot partner agree")
    p.add_argument("--random-system", action="store_true",
                   help="pick a random bidding system for biq at each "
                        "deal (robustness test; mismatches the bot "
                        "partner — not a clean measurement)")
    p.add_argument("--pair", action="store_true",
                   help="two-biq partnership: a SEPARATE biq client holds "
                        "the partner seat, so this client plays ONLY its "
                        "own seat (incl. when dummy). Required when running "
                        "biq on both N and S — otherwise both fight over "
                        "both seats.")
    p.add_argument("--nopeek", action="store_true",
                   help="play CARDS with the no-peek technique engine "
                        "(backend.nopeek) instead of MC+DDS — never looks at "
                        "hidden cards. Bidding is unchanged. Use this to measure "
                        "the no-peek engine head-to-head vs Q-Plus cardplay.")
    args = p.parse_args(argv)
    # Seat-aware: only clears a stuck same-seat client, so a biq+biq
    # partnership (N and S clients) can coexist.
    _kill_prior_instances(args.seat)
    seat_map = {"N": Seat.NORTH, "E": Seat.EAST,
                 "S": Seat.SOUTH, "W": Seat.WEST}
    client = BiqClient(
        args.host, args.port, seat_map[args.seat],
        system=args.system, name=args.name,
        num_samples=args.num_samples,
        verbose=not args.quiet, log_path=args.log,
        system_file=args.system_file, auto_system=args.auto_system,
        random_system=args.random_system, pair_mode=args.pair,
        nopeek=args.nopeek)
    client.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
