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

Validate without a robot (scripted clients, see bluechip_test_client.py):
  python3 tools/biq_bluechip_tm.py --remote E,W --boards 4 --port 2001 &
  python3 tools/bluechip_test_client.py --seat East --port 2001 &
  python3 tools/bluechip_test_client.py --seat West --port 2001
"""
from __future__ import annotations

import argparse
import datetime as _dt
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


# ------------------------------------------------------------ connections
class Remote:
    def __init__(self, sock, addr, log):
        self.sock, self.addr, self.log = sock, addr, log
        self.buf = b""
        self.pending: List[str] = []
        self.seat: Optional[Seat] = None
        self.team = ""

    def send(self, line: str):
        self.log(f"-> {NAME[self.seat] if self.seat else self.addr}: {line}")
        self.sock.sendall((line + "\r\n").encode("latin-1"))

    def _readline(self, timeout: float) -> str:
        deadline = time.time() + timeout
        while b"\n" not in self.buf:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError(f"{NAME.get(self.seat, self.addr)}: no message in {timeout:.0f} s")
            r, _, _ = select.select([self.sock], [], [], left)
            if r:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ConnectionError(f"{NAME.get(self.seat, self.addr)} disconnected")
                self.buf += chunk
        i = self.buf.index(b"\n")
        line = self.buf[:i].decode("latin-1").replace("\r", "").strip()
        self.buf = self.buf[i + 1:]
        return line

    def expect(self, rx: str, timeout: float = 900.0) -> re.Match:
        """Next message matching `rx` (case-insensitive). Out-of-order
        messages are kept for later expects."""
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
            self.log(f"<- {NAME[self.seat] if self.seat else self.addr}: {line}")
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
        from backend import bid_sim
        bid_sim.set_play_system(a.system)    # card-play sampler reads our system
        self.out = Path(a.out or (_HERE / "runs" / "bluechip" /
                                  _dt.datetime.now().strftime("%y%m%d_%H%M%S")))
        self.out.mkdir(parents=True, exist_ok=True)
        self.logf = open(self.out / "tm.log", "a")
        self.conns: Dict[Seat, Remote] = {}
        self.results = []

    def log(self, msg: str):
        line = f"{_dt.datetime.now():%H:%M:%S} {msg}"
        self.logf.write(line + "\n")
        self.logf.flush()
        if not self.a.quiet:
            print(line, flush=True)

    # --- session
    def connect_all(self):
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.a.host, self.a.port))
        ls.listen(8)
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
            if seat not in self.remote_seats or seat in self.conns:
                rc.send(f"Seat {NAME[seat]} is not available")
                sock.close()
                continue
            if int(m.group(3)) != PROTOCOL_VERSION:
                self.log(f"note: {NAME[seat]} uses protocol version {m.group(3)}")
            rc.seat = seat
            rc.send(f'{NAME[seat]} ("{rc.team}") seated')
            rc.expect(rf"{NAME[seat]}\s+ready\s+for\s+teams")
            self.conns[seat] = rc
        ls.close()
        ns = self._team(True)
        ew = self._team(False)
        for rc in self.conns.values():
            rc.send(f'Teams : N/S : "{ns}" E/W : "{ew}"')
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+to\s+start")

    def _team(self, ns: bool) -> str:
        for s, rc in self.conns.items():
            if s.is_ns() == ns:
                return rc.team
        return self.a.team

    def end_session(self):
        for rc in self.conns.values():
            try:
                rc.send("End of session")
            except OSError:
                pass
        time.sleep(1)
        for rc in self.conns.values():
            try:
                rc.sock.close()
            except OSError:
                pass

    # --- one board
    def play_board(self, label: str, number: int, dealer: Seat, vul: Vulnerability, hands):
        t0 = time.time()
        for rc in self.conns.values():
            rc.send("Start of board")
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+for\s+deal")
        for rc in self.conns.values():
            rc.send(f"Board number {number}. Dealer {NAME[dealer]}. {VUL_TEXT[vul]} vulnerable.")
        for s, rc in self.conns.items():
            rc.expect(rf"{NAME[s]}\s+ready\s+for\s+cards")
        for s, rc in self.conns.items():
            rc.send(f"{NAME[s]}'s cards : {fmt_hand(hands[s])}")
        self.log(f"=== {label}: board {number}, dealer {NAME[dealer]}, {VUL_TEXT[vul]} vulnerable")

        auction, alerts = self._auction(dealer, vul, hands)
        contract = derive_contract(auction, dealer)
        rec = {"label": label, "board": number, "dealer": NAME[dealer][0],
               "vul": VUL_TEXT[vul], "deal": "N:" + " ".join(hands[s].to_pbn() for s in SEATS),
               "auction": " ".join(_call_str(b) for b in auction), "alerts": alerts}
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
                line_opp = fmt_call(seat, b) + (f" {alert}" if alert else "")
                line_partner = fmt_call(seat, b)
                if alert:
                    alerts[len(auction)] = alert
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
                line_opp = line_partner = fmt_call(seat, b)
            for s, rc in self.conns.items():
                if s == seat:
                    continue
                rc.expect(rf"{NAME[s]}\s+ready\s+for\s+{NAME[seat]}'s\s+bid")
                rc.send(line_partner if s.is_ns() == seat.is_ns() else line_opp)
            auction.append(b)
            seat = seat.next()
        self.log("auction: " + " ".join(_call_str(b) for b in auction))
        return auction, alerts

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
                        m = self.conns[actor].expect(rf"^{NAME[p]}\s+plays\s+(\S+)")
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
                    rc.expect(rf"{NAME[s]}\s+ready\s+for\s+\w+'s\s+card\s+to\s+trick\s+{t}\b")
                    rc.send(f"{NAME[p]} plays {fmt_card(c)}")
                live[p].cards.remove(c)
                cur.append(c)
                play.append(fmt_card(c))
                if t == 1 and k == 0:               # dummy goes down after the lead
                    for s, rc in self.conns.items():
                        if s == dummy:
                            continue
                        rc.expect(rf"{NAME[s]}\s+ready\s+for\s+dummy\b(?!')")
                        rc.send(f"Dummy's cards : {fmt_hand(live[dummy])}")
            w = trick_winner(cur, leader, trump)
            board.tricks.append(Trick(cards=list(cur), leader=leader, winner=w))
            if w.is_ns() == decl.is_ns():
                decl_tricks += 1
            leader = w
            time.sleep(self.a.trick_pause)
        return decl_tricks, play

    # --- the match
    def run(self):
        if self.a.pbn:
            deck = read_pbn(self.a.pbn)[self.a.start - 1: self.a.start - 1 + self.a.boards]
        else:
            deck = [(n, *seeded_board(self.a.seed, n))
                    for n in range(self.a.start, self.a.start + self.a.boards)]
        self.connect_all()
        rooms = ["open", "closed"][: self.a.rooms]
        # Rooms alternate board by board (open 1, closed 1, open 2, ...) so a
        # crash in a long unattended run loses at most one board's pair.
        with open(self.out / "results.jsonl", "a") as fh:
            for n, dealer0, vul0, hands0 in deck:
                for room in rooms:
                    dealer, vul, hands = dealer0, vul0, hands0
                    if room == "closed":
                        dealer, vul, hands = rotate(dealer, vul, hands)
                    rec = self.play_board(f"{room}-{n}", n, dealer, vul, hands)
                    rec["room"] = room
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
        biq_ns_open = all(s not in self.conns for s in (Seat.NORTH, Seat.SOUTH))
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
        biq_ns_open = all(s not in self.conns for s in (Seat.NORTH, Seat.SOUTH))
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
    ap.add_argument("--quiet", action="store_true")
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
