#!/usr/bin/env python3
"""Blue Chip table manager: biq plays other bridge programs over TCP.

Implements the Table Manager side of the Blue Chip Bridge protocol
(version 18, the World Computer Bridge Championship protocol; spec archived
at web.archive.org/web/2021/http://www.bluechipbridge.co.uk/protocol.htm).
WBridge5 (Connection menu), Ben and other robots connect to it as clients,
one TCP connection per seat. The seats nobody connects for are played by
biq in-process with the same engine as the live Q-Plus runs: hybrid bidding
(rules + simulation, BIQ_BID_SIM=0 for rules only) and the no-peek card
search.

Teams match without re-seating anyone: with --rooms 2 every deck board is
played twice, open and closed room alternating board by board. The closed room deals the same cards rotated one seat
clockwise (N's hand to E, dealer and vulnerability rotated with it), so the
robot that sat East/West in the open room now holds the open room's N/S
cards and biq holds the E/W cards. IMPs compare the two scores for the
side holding the original N/S cards.

Usage:
  python3 tools/biq_bluechip_tm.py --remote E,W [--port 2000] [--boards 16]
         [--seed 1 | --pbn FILE] [--rooms 2] [--system SAYC] [--out DIR]

Then in WBridge5 (one instance per remote seat): Connection, server
localhost (or this machine's address), the port above, seat East (West),
any team name, Auto checked.

Live settings: a file control.json in the output folder, e.g.
  {"system": "Precision90M", "signalling": false}
is re-read before every board (both rooms of a board always use the same
settings), so biq's bidding system and defensive signalling can be changed
during a run without dropping the robots' connections. Missing keys keep the
current value; every change is logged, and each results.jsonl record carries
the system and signalling it was played with.

Continuous mode (--continuous): the deck is open-ended. Before each board the
TM takes the next unplayed entry of <out>/queue.jsonl ({"qid", "deal": "N:...",
"dealer", "vul", "tags"}, or {"qid", "random": true} for the seeded random
board of that number), written by tools/biq_planner.py while the match runs;
with the queue empty it deals the seeded random board.
Each results record carries its source (random / qid), tags, the code
fingerprint and biq's reason for every call it made.

Spare windows: a second window that joins a seat already taken becomes its
spare (windows may join at any time; the listening socket stays open). When
a window is silent for --failover-secs (180) or disconnects, its spare takes
the seat and the board is replayed from the start; failovers.jsonl logs it.
Q-Plus windows freeze after ~370 hands, so one spare per seat doubles an
unattended run.

Segments (two runs in one night): <out>/segments.json
  {"handover_after_boards": 175,
   "segments": [{"label": "2/1", "biq": {"system": "TwoOverOne", "signalling": true}},
                {"label": "Precision", "biq": {"system": "Precision90M", "signalling": true}}]}
The first set of windows plays segment 1; the next set (joined as spares,
launched with segment 2's Q-Plus settings) takes ALL seats at once after
handover_after_boards boards, or early when a window of segment 1 fails, and
biq switches to segment 2's system / signalling at the same board. Records
carry "segment"; handovers.jsonl logs each switch.

Hot code swap: control.json {"reexec": "<token>", "code": "<code dir>"} makes
the TM, at the next board boundary, exec itself from <code dir>/tools/
biq_bluechip_tm.py (a snapshot made by tools/biq_deploy.py) with the robots'
sockets inherited, so new biq code goes live without anyone re-joining.

Validate without a robot (scripted clients, see bluechip_test_client.py):
  python3 tools/biq_bluechip_tm.py --remote E,W --boards 4 --port 2001 &
  python3 tools/bluechip_test_client.py --seat East --port 2001 &
  python3 tools/bluechip_test_client.py --seat West --port 2001
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import json
import os
import re
import select
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.models import (Bid, Seat, Suit, Rank, Card, Hand, BoardState,   # noqa: E402
                            Contract, Trick, Vulnerability)
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid    # noqa: E402
from backend.bidding_systems import get_system                                # noqa: E402
from backend.scoring import calculate_contract_score, diff_to_imps            # noqa: E402

PROTOCOL_VERSION = 18
SEATS = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
NAME = {s: s.name.title() for s in SEATS}
BY_NAME = {s.name.lower(): s for s in SEATS}
SUIT_CH = {Suit.SPADES: "S", Suit.HEARTS: "H", Suit.DIAMONDS: "D",
           Suit.CLUBS: "C", Suit.NOTRUMP: "NT"}
CH_SUIT = {"S": Suit.SPADES, "H": Suit.HEARTS, "D": Suit.DIAMONDS,
           "C": Suit.CLUBS, "NT": Suit.NOTRUMP, "N": Suit.NOTRUMP}
RANK_CH = "AKQJT98765432"            # index = Rank value
STRAIN_RANK = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3,
               Suit.NOTRUMP: 4}
VUL_TEXT = {Vulnerability.NONE: "Neither", Vulnerability.NS: "N/S",
            Vulnerability.EW: "E/W", Vulnerability.BOTH: "Both"}


# ------------------------------------------------------------- formatting
def fmt_hand(hand: Hand) -> str:
    """'S A K 3. H -. D Q J T. C 9 8 7 6 5 4 3.' (protocol hand format)."""
    out = []
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        rs = sorted((c.rank.value for c in hand.cards if c.suit == s))
        out.append(f"{SUIT_CH[s]} " + (" ".join(RANK_CH[r] for r in rs) if rs else "-") + ".")
    return " ".join(out)


def fmt_call(seat: Seat, b: Bid) -> str:
    if b.is_pass:
        return f"{NAME[seat]} passes"
    if b.is_double:
        return f"{NAME[seat]} doubles"
    if b.is_redouble:
        return f"{NAME[seat]} redoubles"
    return f"{NAME[seat]} bids {b.level}{SUIT_CH[b.suit]}"


def fmt_card(c: Card) -> str:
    return RANK_CH[c.rank.value] + SUIT_CH[c.suit]


def parse_card(tok: str) -> Card:
    t = tok.strip().upper().rstrip(".")
    if len(t) == 3 and t.startswith("10"):
        t = "T" + t[2]
    if t[0] in "SHDC" and t[1] in RANK_CH:          # tolerate suit-first
        t = t[1] + t[0]
    return Card(CH_SUIT[t[1]], Rank(RANK_CH.index(t[0])))


_CALL_RX = re.compile(r"^(north|east|south|west)\s+(passes|pass|doubles|redoubles|"
                      r"bids\s+([1-7])\s*(nt|n|s|h|d|c))\b(.*)$", re.I)


def parse_call(line: str):
    """-> (seat, Bid, alert_text or None) or None."""
    m = _CALL_RX.match(line.strip())
    if not m:
        return None
    seat = BY_NAME[m.group(1).lower()]
    w = m.group(2).lower()
    if w.startswith("pass"):
        b = Bid.make_pass()
    elif w == "doubles":
        b = Bid.make_double()
    elif w == "redoubles":
        b = Bid.make_redouble()
    else:
        b = Bid(level=int(m.group(3)), suit=CH_SUIT[m.group(4).upper()])
    rest = m.group(5).strip().lstrip(".").strip()
    alert = rest if rest.lower().startswith("alert") or rest.lower().startswith("infos") else None
    return seat, b, alert


def trick_winner(cards: List[Card], leader: Seat, trump: Optional[Suit]) -> Seat:
    best = 0
    for i, c in enumerate(cards[1:], 1):
        b = cards[best]
        if trump is not None and c.suit == trump and b.suit != trump:
            best = i
        elif c.suit == b.suit and c.rank.value < b.rank.value:   # lower value = higher card
            best = i
    return Seat((leader.value + best) % 4)


def auction_over(a: List[Bid]) -> bool:
    if len(a) >= 4 and all(b.is_pass for b in a[-3:]) and any(not b.is_pass for b in a[:-3]):
        return True
    return len(a) == 4 and all(b.is_pass for b in a)


def legal_call(auction: List[Bid], dealer: Seat, seat: Seat, b: Bid) -> bool:
    last, last_seat, dbl = None, None, 0
    s = dealer
    for x in auction:
        if x.is_double:
            dbl = 1
        elif x.is_redouble:
            dbl = 2
        elif not x.is_pass:
            last, last_seat, dbl = x, s, 0
        s = s.next()
    if b.is_pass:
        return True
    if b.is_double:
        return last is not None and dbl == 0 and last_seat.is_ns() != seat.is_ns()
    if b.is_redouble:
        return last is not None and dbl == 1 and last_seat.is_ns() == seat.is_ns()
    if last is None:
        return True
    return (b.level, STRAIN_RANK[b.suit]) > (last.level, STRAIN_RANK[last.suit])


def derive_contract(auction: List[Bid], dealer: Seat) -> Optional[Contract]:
    s, last, last_seat, dbl, first = dealer, None, None, 0, {}
    for b in auction:
        if b.is_double:
            dbl = 1
        elif b.is_redouble:
            dbl = 2
        elif not b.is_pass:
            last, last_seat, dbl = b, s, 0
            first.setdefault((s.is_ns(), b.suit), s)
        s = s.next()
    if last is None:
        return None
    return Contract(level=last.level, suit=last.suit, doubled=dbl == 1,
                    redoubled=dbl == 2, declarer=first[(last_seat.is_ns(), last.suit)])


# ------------------------------------------------------------------ decks
def seeded_board(seed: int, n: int):
    from tools.biq_qnet_server import _deal, _VMAP
    dealer, vul, hands = _deal(seed, n)
    return dealer, _VMAP[vul], hands


def read_pbn(path: str):
    """[(board, dealer, vul, hands)] from a PBN file (Board/Dealer/
    Vulnerable/Deal tags)."""
    out, tags = [], {}
    vmap = {"none": Vulnerability.NONE, "love": Vulnerability.NONE, "-": Vulnerability.NONE,
            "ns": Vulnerability.NS, "ew": Vulnerability.EW, "all": Vulnerability.BOTH,
            "both": Vulnerability.BOTH}

    def flush():
        if "Deal" in tags:
            first, rest = tags["Deal"].split(":", 1)
            seat = BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[first.strip().upper()]]
            hands = {}
            for h in rest.split():
                hands[seat] = Hand.from_pbn(h)
                seat = seat.next()
            d = tags.get("Dealer", "N").strip().upper()[:1]
            out.append((int(tags.get("Board", len(out) + 1)),
                        BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[d]],
                        vmap.get(tags.get("Vulnerable", "None").strip().lower(), Vulnerability.NONE),
                        hands))
        tags.clear()

    for line in open(path, encoding="latin-1"):
        m = re.match(r'\s*\[(\w+)\s+"([^"]*)"\]', line)
        if m:
            if m.group(1) == "Board" and "Deal" in tags:
                flush()
            tags[m.group(1)] = m.group(2)
    flush()
    return out


def rotate(dealer: Seat, vul: Vulnerability, hands):
    """Same cards one seat clockwise (closed room)."""
    swap = {Vulnerability.NS: Vulnerability.EW, Vulnerability.EW: Vulnerability.NS}
    return dealer.next(), swap.get(vul, vul), {s.next(): Hand(cards=list(h.cards))
                                               for s, h in hands.items()}


def code_fingerprint(root: Path = _HERE.parent) -> str:
    """Short hash of the biq code this TM runs (backend/*.py + this file)."""
    h = hashlib.sha1()
    for f in sorted((root / "backend").glob("*.py")) + [root / "tools" / "biq_bluechip_tm.py"]:
        try:
            h.update(f.name.encode() + f.read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:10]


_VUL_IN = {"none": Vulnerability.NONE, "ns": Vulnerability.NS, "n/s": Vulnerability.NS,
           "ew": Vulnerability.EW, "e/w": Vulnerability.EW, "both": Vulnerability.BOTH,
           "all": Vulnerability.BOTH, "neither": Vulnerability.NONE}


def board_from_entry(e: dict):
    """(dealer, vul, hands) of a queue entry."""
    first, rest = e["deal"].split(":", 1)
    seat = BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[first.strip().upper()]]
    hands = {}
    for h in rest.split():
        hands[seat] = Hand.from_pbn(h)
        seat = seat.next()
    dealer = BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[e.get("dealer", "N")[0].upper()]]
    return dealer, _VUL_IN[str(e.get("vul", "None")).lower()], hands


# ------------------------------------------------------------ connections
class BoardRedo(RuntimeError):
    """A robot went silent mid-board: start the board again."""
    def __init__(self, msg, seat=None):
        super().__init__(msg)
        self.seat = seat


class SeatTimeout(TimeoutError):
    def __init__(self, msg, seat=None):
        super().__init__(msg)
        self.seat = seat


class SeatGone(ConnectionError):
    def __init__(self, msg, seat=None):
        super().__init__(msg)
        self.seat = seat


class Remote:
    def __init__(self, sock, addr, log):
        self.sock, self.addr, self.log = sock, addr, log
        self.buf = b""
        self.pending: List[str] = []
        self.seat: Optional[Seat] = None
        self.team = ""
        self.last = ""
        self.timeout = 900.0                 # silence that ends (or fails over) the seat
        self.stage = 0                       # spare handshake: 0 new, 1 seated, 2 teams sent

    def send(self, line: str):
        self.last = line
        self.log(f"-> {NAME[self.seat] if self.seat is not None else self.addr}: {line}")
        self.sock.sendall((line + "\r\n").encode("latin-1"))

    def _readline(self, timeout: float) -> str:
        deadline = time.time() + timeout
        while b"\n" not in self.buf:
            left = deadline - time.time()
            if left <= 0:
                raise SeatTimeout(f"{NAME.get(self.seat, self.addr)}: no message in {timeout:.0f} s",
                                  self.seat)
            r, _, _ = select.select([self.sock], [], [], left)
            if r:
                try:
                    chunk = self.sock.recv(4096)
                except OSError:
                    chunk = b""
                if not chunk:
                    raise SeatGone(f"{NAME.get(self.seat, self.addr)} disconnected", self.seat)
                self.buf += chunk
        i = self.buf.index(b"\n")
        line = self.buf[:i].decode("latin-1").replace("\r", "").strip()
        self.buf = self.buf[i + 1:]
        return line

    def poll_lines(self) -> List[str]:
        """Complete lines already available, without blocking."""
        while True:
            r, _, _ = select.select([self.sock], [], [], 0)
            if not r:
                break
            chunk = self.sock.recv(4096)
            if not chunk:
                raise SeatGone(f"{NAME.get(self.seat, self.addr)} disconnected", self.seat)
            self.buf += chunk
        out = []
        while b"\n" in self.buf:
            i = self.buf.index(b"\n")
            line = self.buf[:i].decode("latin-1").replace("\r", "").strip()
            self.buf = self.buf[i + 1:]
            if line:
                out.append(line)
        return out

    def expect(self, rx: str, timeout: Optional[float] = None) -> re.Match:
        """Next message matching `rx` (case-insensitive). Out-of-order
        messages are kept for later expects."""
        if timeout is None:
            timeout = self.timeout
        pat = re.compile(rx, re.I)
        for k, line in enumerate(self.pending):
            m = pat.search(line)
            if m:
                del self.pending[k]
                return m
        while True:
            line = self._readline(timeout)
            if not line:
                continue
            self.log(f"<- {NAME[self.seat] if self.seat is not None else self.addr}: {line}")
            m = pat.search(line)
            if m:
                return m
            self.pending.append(line)


# ------------------------------------------------------------ biq seats
def biq_card(board: BoardState, seat: Seat, cur: List[Card], timeout: float = 90.0) -> Optional[Card]:
    """No-peek card search in a forked child (libdds can segfault; a crash
    costs one card, never the match). Same isolation as the Q-NET client."""
    from backend import nopeek

    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(r)
            c = nopeek.decide(board, seat, current_trick_cards=list(cur))
            if c is not None:
                os.write(w, fmt_card(c).encode())
        except Exception:
            pass
        finally:
            os._exit(0)
    os.close(w)
    data, deadline = b"", time.time() + timeout
    while time.time() < deadline:
        rl, _, _ = select.select([r], [], [], deadline - time.time())
        if not rl:
            break
        chunk = os.read(r, 16)
        if not chunk:
            break
        data += chunk
    os.close(r)
    try:
        if os.waitpid(pid, os.WNOHANG)[0] == 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    return parse_card(data.decode()) if data.strip() else None


def legal_cards(hand: Hand, cur: List[Card]) -> List[Card]:
    if cur:
        follow = [c for c in hand.cards if c.suit == cur[0].suit]
        if follow:
            return follow
    return list(hand.cards)


# ------------------------------------------------------------ the manager
class TableManager:
    def __init__(self, a):
        self.a = a
        self.remote_seats = [BY_NAME[{"N": "north", "E": "east", "S": "south", "W": "west"}[x.strip().upper()[0]]]
                             for x in a.remote.split(",") if x.strip()]
        self.system = get_system(a.system)
        self.sys_name = a.system
        self.script = {}                     # probe mode: this board's script
        from backend import bid_sim
        from backend import signals as _signals
        bid_sim.set_play_system(a.system)    # card-play sampler reads our system
        self.signalling = _signals.is_enabled()
        self._control_mtime = None
        self.out = Path(a.out or (_HERE / "runs" / "bluechip" /
                                  _dt.datetime.now().strftime("%y%m%d_%H%M%S")))
        self.out.mkdir(parents=True, exist_ok=True)
        self.logf = open(self.out / "tm.log", "a")
        self.conns: Dict[Seat, Remote] = {}
        self.results = []
        self.code = code_fingerprint()
        self.explain = {}                    # this board: call index -> biq's reason
        self.token = os.environ.get("BIQ_TM_TOKEN", "")
        self.reexec_to = None                # (token, code dir) requested by control.json
        self.listener = None                 # stays open: spare windows may join any time
        self.lobby: List[Remote] = []        # connections still in the join handshake
        self.spares: Dict[Seat, List[Remote]] = {}
        try:
            self.segcfg = json.loads((self.out / "segments.json").read_text())
        except (OSError, ValueError):
            self.segcfg = None
        self.seg = int(os.environ.get("BIQ_TM_SEGMENT", "0"))
        self._board_now = a.start
        self.seg_start = int(os.environ.get("BIQ_TM_SEG_START", str(a.start)))
        self.argv = list(sys.argv[1:])

    def log(self, msg: str):
        line = f"{_dt.datetime.now():%H:%M:%S} {msg}"
        self.logf.write(line + "\n")
        self.logf.flush()
        if not self.a.quiet:
            print(line, flush=True)

    # --- session
    def connect_all(self):
        state = os.environ.pop("BIQ_TM_RESUME", None)
        if state:
            # Re-exec'd for a code swap: the robots' sockets were inherited.
            st = json.loads(state)
            for kind, items in (("conn", st.get("conns", st)), ("spare", st.get("spares", {}))):
                for name, xs in items.items():
                    for x in (xs if isinstance(xs, list) else [xs]):
                        seat = BY_NAME[name]
                        rc = Remote(socket.socket(fileno=int(x["fd"])), "resumed", self.log)
                        rc.seat, rc.team = seat, x["team"]
                        rc.buf = base64.b64decode(x["buf"])
                        rc.pending = list(x["pending"])
                        if kind == "conn":
                            self.conns[seat] = rc
                        else:
                            rc.stage = 3
                            self.spares.setdefault(seat, []).append(rc)
            self._listen()
            self.log(f"resumed after code swap: {', '.join(NAME[s] for s in self.conns)} kept, "
                     f"spares {self._spare_txt()}; code {self.code}")
            return
        ls = self._listen(blocking=True)
        self.log(f"table manager on {self.a.host}:{self.a.port}, waiting for "
                 f"{', '.join(NAME[s] for s in self.remote_seats)}; biq plays "
                 f"{', '.join(NAME[s] for s in SEATS if s not in self.remote_seats)}")
        while len(self.conns) < len(self.remote_seats):
            sock, addr = ls.accept()
            rc = Remote(sock, f"{addr[0]}:{addr[1]}", self.log)
            # Q-Plus connects first and sends its seat only when the user
            # clicks "Join game": wait, and a dropped or silent connection
            # must not end the session.
            try:
                m = rc.expect(r'connecting\s+"?([^"]*?)"?\s+as\s+(north|east|south|west)\s+'
                              r'using\s+protocol\s+version\s+(\d+)', timeout=900)
            except (TimeoutError, ConnectionError, OSError) as ex:
                self.log(f"dropped {rc.addr}: {ex}")
                sock.close()
                continue
            seat = BY_NAME[m.group(2).lower()]
            rc.team = m.group(1).strip() or "robot"
            if seat in self.remote_seats and seat in self.conns:
                # A second window for a seat already taken: a spare. It
                # finishes its handshake between boards (poll_lobby).
                rc.seat = seat
                rc.send(f'{NAME[seat]} ("{rc.team}") seated')
                rc.stage = 1
                self.lobby.append(rc)
                self.log(f"{NAME[seat]}: second window joins as a spare")
                continue
            if seat not in self.remote_seats:
                rc.send(f"Seat {NAME[seat]} is not available")
                sock.close()
                continue
            if int(m.group(3)) != PROTOCOL_VERSION:
                self.log(f"note: {NAME[seat]} uses protocol version {m.group(3)}")
            rc.seat = seat
            rc.send(f'{NAME[seat]} ("{rc.team}") seated')
            rc.expect(rf"{NAME[seat]}\s+ready\s+for\s+teams")
            self.conns[seat] = rc
        ls.setblocking(False)
        ns = self._team(True)
        ew = self._team(False)
        for rc in self.conns.values():
            rc.send(f'Teams : N/S : "{ns}" E/W : "{ew}"')
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+to\s+start")

    def _team(self, ns: bool) -> str:
        if any(s.is_ns() == ns for s in SEATS if s not in self.remote_seats):
            return self.a.team                  # biq sits on this side
        for s, rc in self.conns.items():
            if s.is_ns() == ns:
                return rc.team
        return self.a.team

    # --- spare windows
    def _listen(self, blocking: bool = False):
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.a.host, self.a.port))
        ls.listen(8)
        ls.setblocking(blocking)
        self.listener = ls
        return ls

    def _spare_txt(self) -> str:
        return ", ".join(f"{NAME[s]} {len(v)}" for s, v in self.spares.items() if v) or "none"

    def _prune_spares(self):
        """Drop spare windows whose connection is gone. A spare only waits for
        "Start of board", so anything readable is a close ('') or a Q-Plus
        "abort_connection" (261020: a window joined East, left and rejoined as
        West; the stale East spare aborted at the handover and the TM stopped)."""
        for seat, lst in self.spares.items():
            for rc in list(lst):
                dead = False
                try:
                    data = rc.sock.recv(4096, socket.MSG_PEEK | socket.MSG_DONTWAIT)
                    dead = (data == b"" or b"abort" in data.lower())
                except (BlockingIOError, InterruptedError):
                    dead = False
                except OSError:
                    dead = True
                if dead:
                    lst.remove(rc)
                    try:
                        rc.sock.close()
                    except OSError:
                        pass
                    self.log(f"spare window for {NAME[seat]} gone (spares: {self._spare_txt()})")

    def poll_lobby(self):
        """Accept new windows and move their join handshake on, without
        blocking. A window that joins a remote seat becomes that seat's spare
        once it says "ready to start"; it then waits for "Start of board"."""
        if self.spares:
            self._prune_spares()
        if self.listener is not None:
            while True:
                try:
                    sock, addr = self.listener.accept()
                except (BlockingIOError, InterruptedError):
                    break
                except OSError:
                    break
                sock.setblocking(True)
                self.lobby.append(Remote(sock, f"{addr[0]}:{addr[1]}", self.log))
        for rc in list(self.lobby):
            try:
                lines = rc.poll_lines()
            except (ConnectionError, OSError):
                self.lobby.remove(rc)
                continue
            for line in lines:
                self.log(f"<- {NAME[rc.seat] if rc.seat is not None else rc.addr} (joining): {line}")
                if rc.stage == 0:
                    m = re.search(r'connecting\s+"?([^"]*?)"?\s+as\s+(north|east|south|west)', line, re.I)
                    if not m:
                        continue
                    seat = BY_NAME[m.group(2).lower()]
                    if seat not in self.remote_seats:
                        rc.send(f"Seat {NAME[seat]} is not available")
                        rc.sock.close()
                        self.lobby.remove(rc)
                        break
                    rc.seat, rc.team = seat, m.group(1).strip() or "robot"
                    rc.send(f'{NAME[seat]} ("{rc.team}") seated')
                    rc.stage = 1
                elif rc.stage == 1 and re.search(r"ready\s+for\s+teams", line, re.I):
                    rc.send(f'Teams : N/S : "{self._team(True)}" E/W : "{self._team(False)}"')
                    rc.stage = 2
                elif rc.stage == 2 and re.search(r"ready\s+to\s+start", line, re.I):
                    rc.stage = 3
                    self.lobby.remove(rc)
                    if rc.seat in self.conns:
                        self.spares.setdefault(rc.seat, []).append(rc)
                        self.log(f"spare window ready for {NAME[rc.seat]} (spares: {self._spare_txt()})")
                    else:
                        self.conns[rc.seat] = rc     # a seat with no window: take it at once
                        self.log(f"{NAME[rc.seat]} seated from the lobby")
                    break
        for s, rc in self.conns.items():           # quick failover only when a spare can take over
            spare = self.spares.get(s) or any(x.seat == s for x in self.lobby)
            rc.timeout = self.a.failover_secs if spare else 900.0

    def failover(self, seat, why: str) -> bool:
        """Replace a silent or vanished window by its seat's spare."""
        self.poll_lobby()
        if self._segments() and self.seg + 1 < len(self._segments()):
            # The spares carry the next segment's settings: switch the whole
            # table rather than mix settings within a partnership.
            return self.handover(self._board_now, f"{NAME.get(seat, '?')} failed: {why}")
        if seat is None or not self.spares.get(seat):
            return False
        old = self.conns.get(seat)
        new = self.spares[seat].pop(0)
        if old is not None:
            try:
                old.sock.close()
            except OSError:
                pass
        self.conns[seat] = new
        for rc in self.conns.values():
            rc.pending = []
        self.log(f"FAILOVER {NAME[seat]}: {why}; spare window takes the seat "
                 f"(spares left: {self._spare_txt()})")
        try:
            with open(self.out / "failovers.jsonl", "a") as fh:
                fh.write(json.dumps({"time": _dt.datetime.now().isoformat(timespec="seconds"),
                                     "seat": NAME[seat], "why": why}) + "\n")
        except OSError:
            pass
        self.poll_lobby()                          # refresh timeouts
        return True

    def play_with_failover(self, label, n, dealer, vul, hands, reset=None):
        """play_board; a silent / vanished window is replaced by its spare and
        the board replayed from the start (the other robots accept "Start of
        board" mid-board). Without a spare: one plain replay after a missing
        card, else the error ends the session as before."""
        replayed = False
        for attempt in range(4):
            if attempt and reset is not None:
                reset()
            try:
                return self.play_board(label, n, dealer, vul, hands)
            except (BoardRedo, SeatTimeout, SeatGone) as ex:
                if self.failover(getattr(ex, "seat", None), repr(ex)):
                    self.log(f"replaying {label} from the start")
                    continue
                if isinstance(ex, BoardRedo) and not replayed:
                    replayed = True
                    self.log(f"{ex}; replaying {label} from the start")
                    for rc in self.conns.values():
                        rc.pending = []
                    continue
                raise
        raise RuntimeError(f"{label}: no window could finish the board")

    def end_session(self):
        for rc in list(self.conns.values()) + [x for v in self.spares.values() for x in v]:
            try:
                rc.send("End of session")
            except OSError:
                pass
        time.sleep(1)
        for rc in list(self.conns.values()) + [x for v in self.spares.values() for x in v]:
            try:
                rc.sock.close()
            except OSError:
                pass

    # --- one board
    def play_board(self, label: str, number: int, dealer: Seat, vul: Vulnerability, hands):
        t0 = time.time()
        for rc in self.conns.values():      # late "ready" lines from a skipped wait
            rc.pending = [x for x in rc.pending if not re.search(r"ready\s+for", x, re.I)]
            rc.send("Start of board")
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+for\s+deal")
            # Anything a robot sent before "ready for deal" belongs to the
            # board before (a replay after a failover cut it off mid-play: a
            # stale "North plays 3H" was taken as North's card).
            rc.pending = []
        for rc in self.conns.values():
            rc.send(f"Board number {number}. Dealer {NAME[dealer]}. {VUL_TEXT[vul]} vulnerable.")
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+for\s+cards")
        for s, rc in self.conns.items():
            rc.send(f"{NAME[s]}'s cards : {fmt_hand(hands[s])}")
        self.log(f"=== {label}: board {number}, dealer {NAME[dealer]}, {VUL_TEXT[vul]} vulnerable")

        self.explain = {}
        auction, alerts = self._auction(dealer, vul, hands)
        contract = derive_contract(auction, dealer)
        rec = {"label": label, "board": number, "dealer": NAME[dealer][0],
               "vul": VUL_TEXT[vul], "deal": "N:" + " ".join(hands[s].to_pbn() for s in SEATS),
               "auction": " ".join(_call_str(b) for b in auction), "alerts": alerts,
               "explain": dict(self.explain), "code": self.code}
        if contract is None:
            rec.update(contract="PASS", tricks=0, ns_score=0, play=[])
            self.log(f"{label}: passed out")
        else:
            tricks, play = self._play(dealer, vul, hands, auction, contract)
            sc = calculate_contract_score(contract, tricks, vul.is_vulnerable(contract.declarer))
            rec.update(contract=f"{contract.to_str()} {NAME[contract.declarer][0]}",
                       tricks=tricks, ns_score=sc if contract.declarer.is_ns() else -sc,
                       play=play)
            self.log(f"{label}: {rec['contract']} {tricks} tricks, N/S {rec['ns_score']:+d}")
        secs = int(time.time() - t0)
        for rc in self.conns.values():
            rc.send(f"Timing - N/S : this board {secs // 60}:{secs % 60:02d}, total 0:00:00. "
                    f"E/W : this board {secs // 60}:{secs % 60:02d}, total 0:00:00")
        return rec

    def _auction(self, dealer, vul, hands):
        auction: List[Bid] = []
        alerts = {}
        seat = dealer
        while not auction_over(auction):
            if seat in self.conns:
                for _ in range(3):
                    m = self.conns[seat].expect(rf"^{NAME[seat]}\s+(passes|pass|doubles|redoubles|bids)\b")
                    p = parse_call(m.string)
                    if p and legal_call(auction, dealer, seat, p[1]):
                        break
                    self.conns[seat].send("Illegal bid")
                else:
                    raise RuntimeError(f"{NAME[seat]} made three illegal calls")
                _, b, alert = p
                # Q-Plus froze on the first alerted call relayed to it ("North
                # bids 2NT Alert.", 2026-10-05): opponents get alerts only
                # with --relay-alerts.
                line_opp = fmt_call(seat, b) + (f" {alert}" if alert and self.a.relay_alerts else "")
                line_partner = fmt_call(seat, b)
                if alert:
                    alerts[len(auction)] = alert
            elif self.script.get("calls", {}).get(NAME[seat][0]):
                # Probe mode: biq's seat makes the scripted call.
                b = Bid.from_str(self.script["calls"][NAME[seat][0]].pop(0))
                if not legal_call(auction, dealer, seat, b):
                    self.log(f"scripted {_call_str(b)} illegal; passing")
                    b = Bid.make_pass()
                line_opp = line_partner = fmt_call(seat, b)
            else:
                st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
                e = evaluate_hand(hands[seat])
                try:
                    b = decide_bid(st, e, self.system, hand=hands[seat])
                except Exception as ex:                      # never wedge the table
                    self.log(f"biq bidder error {ex!r}; passing")
                    b = Bid.make_pass()
                if not legal_call(auction, dealer, seat, b):
                    self.log(f"biq produced an illegal {_call_str(b)}; passing")
                    b = Bid.make_pass()
                if "Simulation:" in (b.explanation or ""):
                    self.log(f"  {b.explanation}")
                if b.explanation:
                    self.explain[str(len(auction))] = b.explanation[:240]
                line_opp = line_partner = fmt_call(seat, b)
            for s, rc in self.conns.items():
                if s == seat:
                    continue
                self._await_ready(rc, rf"{NAME[s]}\s+ready\s+for\s+{NAME[seat]}'s\s+bid")
                rc.send(line_partner if s.is_ns() == seat.is_ns() else line_opp)
            auction.append(b)
            seat = seat.next()
        self.log("auction: " + " ".join(_call_str(b) for b in auction))
        return auction, alerts

    def _await_card(self, rc, rx):
        """A robot's card. Q-Plus sometimes shows its card in its window but
        never sends it (East leading to trick 4, 2026-10-05). Resend the last
        message after 120 s; after another 180 s replay the board."""
        t1, t2 = min(120.0, rc.timeout), min(180.0, rc.timeout)
        try:
            return rc.expect(rx, timeout=t1)
        except TimeoutError:
            self.log(f"no card from {NAME[rc.seat]} in {t1:.0f} s; resending {rc.last!r}")
            rc.send(rc.last)
        try:
            return rc.expect(rx, timeout=t2)
        except TimeoutError:
            raise BoardRedo(f"no card from {NAME[rc.seat]}", rc.seat) from None

    def _await_ready(self, rc, rx):
        """Wait for a robot's "ready for ..." before relaying a card. Q-Plus
        once never sent "West ready for South's card to trick 3" although its
        window sat waiting for that card (2026-10-04, after 6 boards), and the
        900 s timeout ended the session. Send the card anyway after 120 s."""
        t = min(120.0, rc.timeout)
        try:
            rc.expect(rx, timeout=t)
        except TimeoutError:
            self.poll_lobby()
            if self.spares.get(rc.seat):
                raise SeatTimeout(f"{NAME[rc.seat]}: no 'ready' in {t:.0f} s", rc.seat) from None
            self.log(f"no 'ready' from {NAME[rc.seat]} in {t:.0f} s; sending anyway")

    def _play(self, dealer, vul, hands, auction, contract):
        decl = contract.declarer
        dummy = decl.partner()
        trump = None if contract.suit == Suit.NOTRUMP else contract.suit
        live = {s: Hand(cards=list(hands[s].cards)) for s in SEATS}
        board = BoardState(board_number=1, dealer=dealer, vulnerability=vul,
                           hands=live, auction=list(auction), contract=contract, tricks=[])
        leader = decl.next()
        decl_tricks, play = 0, []
        for t in range(1, 14):
            cur: List[Card] = []
            for k in range(4):
                p = Seat((leader.value + k) % 4)
                actor = decl if p == dummy else p
                if k == 0 and actor in self.conns:
                    self.conns[actor].send("Dummy to lead" if p == dummy else f"{NAME[p]} to lead")
                if actor in self.conns:
                    for _ in range(3):
                        m = self._await_card(self.conns[actor], rf"^{NAME[p]}\s+plays\s+(\S+)")
                        try:
                            c = parse_card(m.group(1))
                        except (KeyError, ValueError, IndexError):
                            c = None
                        if c is not None and c in legal_cards(live[p], cur):
                            break
                        self.conns[actor].send("Illegal card")
                    else:
                        raise RuntimeError(f"{NAME[p]} played three illegal cards")
                else:
                    board.tricks = list(board.tricks)
                    c = self._scripted_card(t, p, live[p], cur)
                    if c is None:
                        c = biq_card(board, p, cur)
                    if c is None or c not in legal_cards(live[p], cur):
                        self.log(f"biq card search failed for {NAME[p]}; legal fallback")
                        c = sorted(legal_cards(live[p], cur), key=lambda x: -x.rank.value)[0]
                # Every other robot asks for the card first: "ready for East's
                # card to trick 3", "ready for dummy's card ..." (the spec has
                # dummy itself always say "dummy's", so accept any name).
                for s, rc in self.conns.items():
                    if s == actor:
                        continue
                    self._await_ready(rc, rf"{NAME[s]}\s+ready\s+for\s+\w+'s\s+card\s+to\s+trick\s+{t}\b")
                    rc.send(f"{NAME[p]} plays {fmt_card(c)}")
                live[p].cards.remove(c)
                cur.append(c)
                play.append(fmt_card(c))
                if t == 1 and k == 0:               # dummy goes down after the lead
                    for s, rc in self.conns.items():
                        if s == dummy:
                            continue
                        self._await_ready(rc, rf"{NAME[s]}\s+ready\s+for\s+dummy\b(?!')")
                        rc.send(f"Dummy's cards : {fmt_hand(live[dummy])}")
            w = trick_winner(cur, leader, trump)
            board.tricks.append(Trick(cards=list(cur), leader=leader, winner=w))
            if w.is_ns() == decl.is_ns():
                decl_tricks += 1
            leader = w
            time.sleep(self.a.trick_pause)
        return decl_tricks, play

    def _scripted_card(self, t, p, hand, cur):
        """Probe mode: a scripted card for biq's seat `p` if the script has
        one: "follows" {"<trick><seat>": card}; "low": suit letter = follow
        that suit with the lowest card; else, on lead, the first card of
        "leads" that `p` holds."""
        sc = self.script
        if not sc:
            return None
        legal = legal_cards(hand, cur)
        f = sc.get("follows", {}).get(f"{t}{NAME[p][0]}")
        if f:
            c = parse_card(f)
            return c if c in legal else None
        low = sc.get("low")                  # "C": follow with the lowest club
        if low and cur and cur[0].suit == parse_card("2" + low).suit \
                and legal and legal[0].suit == cur[0].suit:
            return max(legal, key=lambda c: c.rank.value)
        if not cur:
            for i, tok in enumerate(sc.get("leads", [])):
                c = parse_card(tok)
                if c in legal:
                    sc["leads"].pop(i)
                    return c
        return None

    # --- live settings
    def apply_control(self):
        """Re-read <out>/control.json when it has changed (see the module
        docstring). An unreadable file is logged and changes nothing; an
        unknown system name is logged and keeps the current system, while the
        file's other settings still apply."""
        p = self.out / "control.json"
        try:
            mt = p.stat().st_mtime
        except FileNotFoundError:
            return
        if mt == self._control_mtime:
            return
        self._control_mtime = mt
        try:
            c = json.loads(p.read_text())
            if not isinstance(c, dict):
                raise ValueError("not a JSON object")
        except (OSError, ValueError) as ex:
            self.log(f"control.json unreadable ({ex}); settings unchanged")
            return
        from backend import bid_sim
        from backend import signals as _signals
        name = c.get("system", self.sys_name)
        if self._segments():
            name = self.sys_name                 # segments.json sets biq's system
        if name != self.sys_name:
            new = get_system(name)
            if name != "SAYC" and getattr(new, "name", "SAYC") == "SAYC":
                self.log(f"control.json: unknown system {name!r}; keeping {self.sys_name}")
            else:
                self.system, self.sys_name = new, name
                bid_sim.set_play_system(name)
                self.log(f"control.json: biq's system is now {name}")
        tok = str(c.get("reexec", "") or "")
        if tok and tok != self.token:
            self.reexec_to = (tok, c.get("code") or str(_HERE.parent))
            self.log(f"control.json: code swap {tok} requested ({self.reexec_to[1]})")
        sig = bool(c.get("signalling", self.signalling))
        if self._segments():
            sig = self.signalling
        if sig != self.signalling:
            _signals.set_enabled(sig)
            self.signalling = sig
            self.log(f"control.json: biq's signalling is now {'on' if sig else 'off'}")

    def set_biq(self, system: Optional[str] = None, signalling: Optional[bool] = None, why=""):
        from backend import bid_sim
        from backend import signals as _signals
        if system and system != self.sys_name:
            new = get_system(system)
            if system != "SAYC" and getattr(new, "name", "SAYC") == "SAYC":
                self.log(f"{why}unknown system {system!r}; keeping {self.sys_name}")
            else:
                self.system, self.sys_name = new, system
                bid_sim.set_play_system(system)
                self.log(f"{why}biq's system is now {system}")
        if signalling is not None and bool(signalling) != self.signalling:
            _signals.set_enabled(bool(signalling))
            self.signalling = bool(signalling)
            self.log(f"{why}biq's signalling is now {'on' if signalling else 'off'}")

    # --- segments
    def _segments(self):
        return (self.segcfg or {}).get("segments") or []

    def segment_label(self) -> Optional[str]:
        segs = self._segments()
        return segs[self.seg].get("label", str(self.seg + 1)) if segs and self.seg < len(segs) else None

    def apply_segment(self):
        segs = self._segments()
        if segs and self.seg < len(segs):
            b = segs[self.seg].get("biq", {})
            self.set_biq(b.get("system"), b.get("signalling"), why=f"segment {self.segment_label()}: ")

    def handover(self, n: int, why: str) -> bool:
        """All remote seats switch to their next spare window (the next
        segment's Q-Plus settings) and biq to the next segment's settings."""
        segs = self._segments()
        if not segs or self.seg + 1 >= len(segs):
            return False
        self.poll_lobby()
        self._prune_spares()
        if not all(self.spares.get(s) for s in self.remote_seats):
            self.log(f"handover to segment {self.seg + 2} not possible ({why}): "
                     f"spares {self._spare_txt()}")
            return False
        old_label = self.segment_label()
        for s in self.remote_seats:
            old = self.conns.get(s)
            if old is not None:
                try:
                    old.send("End of session")
                    old.sock.close()
                except OSError:
                    pass
            self.conns[s] = self.spares[s].pop(0)
        for rc in self.conns.values():
            rc.pending = []
        self.seg += 1
        self.seg_start = n
        self.log(f"HANDOVER at board {n} ({why}): segment {old_label} -> {self.segment_label()}; "
                 f"new windows for {', '.join(NAME[s] for s in self.remote_seats)}")
        self.apply_segment()
        try:
            with open(self.out / "handovers.jsonl", "a") as fh:
                fh.write(json.dumps({"time": _dt.datetime.now().isoformat(timespec="seconds"),
                                     "board": n, "why": why, "from": old_label,
                                     "to": self.segment_label()}) + "\n")
        except OSError:
            pass
        self.poll_lobby()
        return True

    # --- continuous deck
    def _consumed(self) -> set:
        done = set()
        try:
            for line in open(self.out / "results.jsonl"):
                q = json.loads(line).get("qid")
                if q:
                    done.add(q)
        except (OSError, ValueError):
            pass
        return done

    def next_board(self, n: int, consumed: set):
        """(dealer, vul, hands, source, qid, tags) for board number n."""
        try:
            for line in open(self.out / "queue.jsonl"):
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("qid") and e["qid"] not in consumed:
                    if e.get("random"):               # planner's slot for a random board
                        dealer, vul, hands = seeded_board(self.a.seed, n)
                        return dealer, vul, hands, "random", e["qid"], {}
                    dealer, vul, hands = board_from_entry(e)
                    return dealer, vul, hands, "queue", e["qid"], e.get("tags", {})
        except (OSError, ValueError, KeyError) as ex:
            if not isinstance(ex, FileNotFoundError):
                self.log(f"queue.jsonl unreadable ({ex!r}); dealing a random board")
        dealer, vul, hands = seeded_board(self.a.seed, n)
        return dealer, vul, hands, "random", None, {}

    def reexec(self, n: int, boards_left: int):
        """Exec the TM from the requested code dir, keeping the robots."""
        tok, code = self.reexec_to
        script = Path(code) / "tools" / "biq_bluechip_tm.py"
        if not script.is_file():
            self.log(f"code swap {tok}: {script} missing; staying on {self.code}")
            self.token = tok
            self.reexec_to = None
            return
        def _st(rc):
            fd = rc.sock.fileno()
            os.set_inheritable(fd, True)
            return {"fd": fd, "team": rc.team, "pending": rc.pending,
                    "buf": base64.b64encode(rc.buf).decode()}
        state = {"conns": {NAME[s].lower(): _st(rc) for s, rc in self.conns.items()},
                 "spares": {NAME[s].lower(): [_st(rc) for rc in v] for s, v in self.spares.items() if v}}
        if self.listener is not None:
            self.listener.close()
        argv, skip = [], False
        for i, x in enumerate(self.argv):
            if skip:
                skip = False
                continue
            if x in ("--start", "--boards"):
                skip = True
                continue
            if x.startswith("--start=") or x.startswith("--boards="):
                continue
            argv.append(x)
        argv += ["--start", str(n), "--boards", str(boards_left)]
        env = dict(os.environ, BIQ_TM_RESUME=json.dumps(state), BIQ_TM_TOKEN=tok,
                   BIQ_TM_SEGMENT=str(self.seg), BIQ_TM_SEG_START=str(self.seg_start))
        self.log(f"code swap {tok}: exec {script} at board {n}")
        self.logf.flush()
        os.execve(sys.executable, [sys.executable, str(script)] + argv, env)

    def run_continuous(self):
        self.connect_all()
        rooms = ["open", "closed"][: self.a.rooms]
        consumed = self._consumed()
        try:                                  # running totals span code swaps
            self.results = [json.loads(x) for x in open(self.out / "results.jsonl") if x.strip()]
        except (OSError, ValueError):
            self.results = []
        self.apply_segment()
        with open(self.out / "results.jsonl", "a") as fh:
            for n in range(self.a.start, self.a.start + self.a.boards):
                self._board_now = n
                self.apply_control()
                if self.reexec_to is not None:
                    fh.flush()
                    self.reexec(n, self.a.start + self.a.boards - n)
                hab = (self.segcfg or {}).get("handover_after_boards")
                if hab and self.seg + 1 < len(self._segments()) and n - self.seg_start >= int(hab):
                    self.handover(n, f"scheduled after {n - self.seg_start} boards")
                dealer0, vul0, hands0, source, qid, tags = self.next_board(n, consumed)
                if qid:
                    consumed.add(qid)
                for room in rooms:
                    dealer, vul, hands = dealer0, vul0, hands0
                    self.script = {}
                    if room == "closed":
                        dealer, vul, hands = rotate(dealer, vul, hands)
                    self.poll_lobby()
                    rec = self.play_with_failover(f"{room}-{n}", n, dealer, vul, hands)
                    rec.update(room=room, system=self.sys_name, signalling=self.signalling,
                               source=source, qid=qid, tags=tags, segment=self.segment_label())
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    self.results.append(rec)
                if len(rooms) == 2:
                    self.log(f"after board {n} ({source}{' ' + qid if qid else ''}): {self.running()}")
        self.end_session()
        self.report()

    # --- the match
    def run(self):
        if self.a.continuous:
            return self.run_continuous()
        if self.a.pbn:
            deck = read_pbn(self.a.pbn)[self.a.start - 1: self.a.start - 1 + self.a.boards]
        else:
            deck = [(n, *seeded_board(self.a.seed, n))
                    for n in range(self.a.start, self.a.start + self.a.boards)]
        self.connect_all()
        rooms = ["open", "closed"][: self.a.rooms]
        scripts = {}
        if self.a.script:
            for line in open(self.a.script):
                if line.strip():
                    x = json.loads(line)
                    scripts[int(x["board"])] = x
        # Rooms alternate board by board (open 1, closed 1, open 2, ...) so a
        # crash in a long unattended run loses at most one board's pair.
        with open(self.out / "results.jsonl", "a") as fh:
            for n, dealer0, vul0, hands0 in deck:
                self.apply_control()
                for room in rooms:
                    dealer, vul, hands = dealer0, vul0, hands0
                    self.script = json.loads(json.dumps(scripts.get(n, {})))
                    if room == "closed":
                        dealer, vul, hands = rotate(dealer, vul, hands)
                    self.poll_lobby()
                    rec = self.play_with_failover(
                        f"{room}-{n}", n, dealer, vul, hands,
                        reset=lambda n=n: setattr(self, "script", json.loads(json.dumps(scripts.get(n, {})))))
                    rec["room"] = room
                    rec["system"] = self.sys_name
                    rec["signalling"] = self.signalling
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    self.results.append(rec)
                if len(rooms) == 2:
                    self.log(f"after board {n}: {self.running()}")
        self.end_session()
        self.report()

    def running(self) -> str:
        """Running teams total over the boards played in both rooms."""
        by = {}
        for r in self.results:
            by.setdefault(r["board"], {})[r["room"]] = r
        biq_ns_open = any(s not in self.conns for s in (Seat.NORTH, Seat.SOUTH))  # biq sits N/S
        tot = n = 0
        for b in by.values():
            if "open" in b and "closed" in b:
                d = diff_to_imps(b["open"]["ns_score"] + b["closed"]["ns_score"])
                tot += d if biq_ns_open else -d
                n += 1
        return f"biq {tot:+d} IMP over {n} boards"

    def report(self):
        by = {}
        for r in self.results:
            by.setdefault(r["board"], {})[r["room"]] = r
        lines, total = [], 0
        biq_ns_open = any(s not in self.conns for s in (Seat.NORTH, Seat.SOUTH))  # biq sits N/S
        for n in sorted(by):
            o, c = by[n].get("open"), by[n].get("closed")
            if not o or not c:
                continue
            # closed room is rotated: the original N/S cards sit E/W there
            closed_orig_ns = -c["ns_score"]
            diff = o["ns_score"] - closed_orig_ns
            imp_biq = diff_to_imps(diff) if biq_ns_open else -diff_to_imps(diff)
            total += imp_biq
            lines.append(f"board {n:3d}: open {o['contract']:>9s} {o['ns_score']:+6d} | "
                         f"closed {c['contract']:>9s} orig-N/S {closed_orig_ns:+6d} | biq {imp_biq:+3d}")
        if lines:
            lines.append(f"biq vs {self._team(False) if biq_ns_open else self._team(True)}: "
                         f"{total:+d} IMP over {len(lines)} boards")
        txt = "\n".join(lines)
        (self.out / "summary.txt").write_text(txt + "\n")
        self.log("\n" + txt)


def _call_str(b: Bid) -> str:
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{SUIT_CH[b.suit]}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--remote", default="E,W", help="seats played by connecting robots")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pbn", default=None, help="deal the boards of this PBN file")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--boards", type=int, default=16)
    ap.add_argument("--rooms", type=int, default=2, choices=[1, 2])
    ap.add_argument("--system", default="SAYC", help="biq's system")
    ap.add_argument("--team", default="biq")
    ap.add_argument("--trick-pause", type=float, default=1.0,
                    help="seconds between tricks (the protocol asks for 1)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--relay-alerts", action="store_true",
                    help="pass robots' alerts on to their opponents")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--script", default=None,
                    help="probe mode: JSON lines {board, calls: {N: [..], S: [..]}, "
                         "leads: [cards], follows: {'<trick><seat>': card}, low: suit} "
                         "for biq's seats")
    ap.add_argument("--continuous", action="store_true",
                    help="open-ended deck: <out>/queue.jsonl entries first, else seeded "
                         "random boards; honours control.json code swaps")
    ap.add_argument("--failover-secs", type=float, default=180.0,
                    help="silence after which a window with a spare is replaced (else 900 s)")
    a = ap.parse_args(argv)
    tm = TableManager(a)
    try:
        tm.run()
    except (ConnectionError, TimeoutError, KeyboardInterrupt, RuntimeError) as ex:
        tm.log(f"stopped: {ex!r}")
        tm.end_session()
        tm.report()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
