#!/usr/bin/env python3
"""biq as the Q-NET SERVER — Q-Plus (or biq's own client) connects as a client.

The mirror image of tools/biq_qnet_client.py. biq binds/listens, accepts ONE
client, runs the Q-NET handshake, then drives a fully-automated match: it deals
reproducible boards, runs the auction and cardplay (biq's engine for its seats,
the client for the client's seat), scores each board double-dummy, and loops —
with NO mouse clicks anywhere (biq, as server, IS the game flow).

Roles: the client plays ONE seat (--client-seat, default South = Extern); biq
plays the other three (Computer). Dummy is played by the DECLARING side's
controller (standard Q-NET), so when the client declares it also plays the
dummy, and when biq declares it plays the client's seat as dummy.

Protocol is plain-text bracketed-token lines (see backend/QNET_PROTOCOL.md);
helpers are reused verbatim from biq_qnet_client. Validate without Q-Plus:
  term1:  python3 tools/biq_qnet_server.py --boards 4
  term2:  python3 tools/biq_qnet_client.py --host 127.0.0.1 --port 5555 \
              --seat South --quiet
A full 4-board match completing on the loopback proves the protocol; Q-Plus,
using the same wire format, then connects the same way.

Usage:
  python3 tools/biq_qnet_server.py [--port 5555] [--client-seat South]
      [--seed 1] [--start-board 1] [--boards 64]
      [--ns-system SAYC] [--ew-system SAYC] [--score-log FILE]
"""
from __future__ import annotations

import argparse
import random
import socket
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from backend.models import (Bid, Seat, Suit, Rank, Card, Hand, BoardState,   # noqa: E402
                            Contract, Trick, Vulnerability)
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid    # noqa: E402
from backend.bidding_systems import get_system                                # noqa: E402
from backend.engine import BridgeEngine                                       # noqa: E402
from backend.dds import DDSolver                                              # noqa: E402
from backend.scoring import calculate_contract_score, diff_to_imps            # noqa: E402
from tools.biq_qnet_client import (format_message, parse_message,             # noqa: E402
                                   format_bid, parse_bid_token,
                                   format_card, parse_card_token)

_SEATS = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
_VUL_BY_BOARD = {  # standard 16-board vulnerability rotation
    1: "None", 2: "NS", 3: "EW", 4: "Both", 5: "NS", 6: "EW", 7: "Both",
    8: "None", 9: "EW", 10: "Both", 11: "None", 12: "NS", 13: "Both",
    14: "None", 15: "NS", 16: "EW"}
_VMAP = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
         "EW": Vulnerability.EW, "Both": Vulnerability.BOTH}
_STRAIN = {Suit.SPADES: "S", Suit.HEARTS: "H", Suit.DIAMONDS: "D",
           Suit.CLUBS: "C", Suit.NOTRUMP: "NT"}
_RANKS = "AKQJT98765432"


def _deal(seed: int, board: int):
    """Reproducible board → (dealer, vul, {seat: Hand}). Pure seeded shuffle;
    biq deals its own boards, so they need only be reproducible for an A/B."""
    rng = random.Random(f"{seed}:{board}")
    deck = [Card(s, r) for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS,
                                 Suit.CLUBS) for r in Rank]
    rng.shuffle(deck)
    hands = {_SEATS[i]: Hand(cards=sorted(deck[i * 13:(i + 1) * 13],
                                          key=lambda c: (c.suit.value,
                                                         c.rank.value)))
             for i in range(4)}
    dealer = _SEATS[(board - 1) % 4]
    vul = _VUL_BY_BOARD[((board - 1) % 16) + 1]
    return dealer, vul, hands


def _pbn(hands) -> str:
    """S.H.D.C hands, space-separated N E S W (suit ranks high→low)."""
    def hand_str(h):
        bys = {s: [] for s in (Suit.SPADES, Suit.HEARTS,
                               Suit.DIAMONDS, Suit.CLUBS)}
        for c in h.cards:
            bys[c.suit].append(c.rank.value)   # 0=A (high) .. 12=2 (low)
        return ".".join("".join(_RANKS[v] for v in sorted(bys[s]))
                        for s in (Suit.SPADES, Suit.HEARTS,
                                  Suit.DIAMONDS, Suit.CLUBS))
    return " ".join(hand_str(hands[s]) for s in _SEATS)


class BiqServer:
    def __init__(self, port, client_seat, seed, start_board, boards,
                 ns_system, ew_system, score_log, host="127.0.0.1",
                 samples=40, verbose=True):
        self.port = port
        self.client_seat = client_seat
        self.seed = seed
        self.start_board = start_board
        self.boards = boards
        self.ns = get_system(ns_system)
        self.ew = get_system(ew_system)
        self.ns_name = ns_system
        self.ew_name = ew_system
        self.score_log = score_log
        self.host = host
        self.samples = samples
        self.verbose = verbose
        self.sock = None
        self.conn = None
        self.buf = b""
        self.engine = BridgeEngine()
        self.dds = DDSolver()
        self.results = []

    # ---- wire ----
    def log(self, m):
        if self.verbose:
            print(f"[biq-server] {m}", flush=True)

    def send(self, cmd, *args):
        self.conn.sendall(format_message(cmd, *args))

    def recv_msg(self):
        while b"\n" not in self.buf:
            chunk = self.conn.recv(4096)
            if not chunk:
                return None
            self.buf += chunk
        nl = self.buf.index(b"\n")
        line = self.buf[:nl].decode("latin-1")
        self.buf = self.buf[nl + 1:]
        return parse_message(line)

    def recv_expect(self, cmd):
        """Block until a message of type `cmd` arrives; return its args.
        Auto-answers the client's interspersed per-deal request_config."""
        while True:
            m = self.recv_msg()
            if m is None:
                raise ConnectionError("client disconnected")
            if m[0] == cmd:
                return m[1]
            if m[0] == "request_config":
                self._send_config()
            # else tolerate stray acks

    # ---- handshake ----
    def accept(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        self.log(f"listening on {self.host}:{self.port} — "
                 f"client plays {self.client_seat.name.title()}")
        self.conn, addr = self.sock.accept()
        self.log(f"client connected from {addr}")

    def handshake(self):
        # The client probes seats then joins. Respond to each request and the
        # join. We answer request_player_info for all 4 seats up front when the
        # first probe arrives, which the line reader tolerates.
        # The client's sequence: request_player_info ×4 → join_game →
        # request_config. Complete through set_config (the client BLOCKS for
        # set_config before the match starts).
        config_sent = False
        while not config_sent:
            m = self.recv_msg()
            if m is None:
                raise ConnectionError("client gone during handshake")
            cmd, args = m
            if cmd == "request_player_info":
                for s in _SEATS:
                    typ = "Extern" if s == self.client_seat else "Computer"
                    status = ("connected" if s == self.client_seat
                              else "local")
                    self.send("set_player_info", s.name.title(),
                              s.name.title(), typ, status)
            elif cmd == "join_game":
                self.send("player_accepted")
                self.send("set_player_info", self.client_seat.name.title(),
                          args[1] if len(args) > 1 else "client",
                          "Extern", "connected")
            elif cmd == "request_config":
                self._send_config()
                config_sent = True
        self.log("handshake complete")

    def _send_config(self):
        self.send("set_config",
                  f"conv.bidding.N/S = {self._code(self.ns_name)};"
                  f"conv.bidding.E/W = {self._code(self.ew_name)};")

    @staticmethod
    def _code(name):
        return {"SAYC": "A-SAYC-I", "TwoOverOne": "A-2-1-A",
                "StandardAcol": "B-ACL-S", "StandardFrench": "F-FRA-M",
                "Precision90M": "P-P90M-A"}.get(name, "A-SAYC-I")

    # ---- match loop ----
    def run_match(self):
        for b in range(self.start_board, self.start_board + self.boards):
            self._play_board(b)
        self.send("server_stopped")
        self.log(f"match done — {len(self.results)} boards. "
                 f"net teams IMP (biq table − client table): "
                 f"{sum(r['imp'] for r in self.results):+d}")
        if self.score_log:
            Path(self.score_log).write_text(
                "\n".join(f"{r['label']} contract={r['contract']} "
                          f"open_ns={r['open_ns']} closed_ns={r['closed_ns']} "
                          f"imp={r['imp']:+d}" for r in self.results) + "\n")

    def _play_board(self, board):
        dealer, vul_s, hands = _deal(self.seed, board)
        vul = _VMAP[vul_s]
        label = f"{self.seed}-{board:02d}"
        # The client may re-request config each deal (--auto-system); answer it.
        self.send("new_deal_pbn", f"{dealer.name[0]} {board} {self.seed}",
                  "IMP", label,
                  f"{dealer.name[0]} {vul_s} N:{_pbn(hands)}")
        self.send("start_bidding", "-")
        auction = self._run_auction(dealer, vul, hands)
        contract = self._derive_contract(auction, dealer)
        if contract is None:
            self.log(f"board {board}: passed out")
            self._report(label, hands, vul, None, 0)
            return
        self.send("begin_play")
        # client acks begin_play (one ack)
        self.recv_expect("begin_play")
        decl_tricks = self._run_play(hands, contract, vul)
        self._report(label, hands, vul, contract, decl_tricks)

    def _sys_for(self, seat):
        return self.ns if seat.is_ns() else self.ew

    def _run_auction(self, dealer, vul, hands):
        auction = []
        seat = dealer
        for _ in range(60):
            if seat == self.client_seat:
                tok = self.recv_expect("bid")
                bid = parse_bid_token(tok[1])
            else:
                st = parse_auction(seat, dealer, list(auction),
                                   vulnerability=vul)
                bid = decide_bid(st, evaluate_hand(hands[seat]),
                                 self._sys_for(seat))
                self.send("bid", seat.name.title(), format_bid(bid))
            auction.append(bid)
            if self._auction_over(auction):
                break
            seat = seat.next()
        return auction

    @staticmethod
    def _auction_over(a):
        if len(a) >= 4 and all(b.is_pass for b in a[-3:]) and \
                any(not b.is_pass for b in a[:-3]):
            return True
        return len(a) >= 4 and all(b.is_pass for b in a)

    def _derive_contract(self, auction, dealer):
        seat = dealer
        last = None
        last_seat = None
        decl_by_strain = {}
        for b in auction:
            if not b.is_pass and not b.is_double and not b.is_redouble:
                last = b
                last_seat = seat
                key = (seat.is_ns(), b.suit)
                decl_by_strain.setdefault(key, seat)
            seat = seat.next()
        if last is None:
            return None
        declarer = decl_by_strain[(last_seat.is_ns(), last.suit)]
        doubled = sum(1 for b in auction if b.is_double)
        redoubled = any(b.is_redouble for b in auction)
        return Contract(level=last.level, suit=last.suit,
                        doubled=bool(doubled and not redoubled),
                        redoubled=redoubled, declarer=declarer)

    def _plays_seat(self, seat, declarer):
        """Who plays a card for `seat` — MUST match the client's _i_control:
        a single Extern client controls BOTH its-side seats when its side
        declares (it plays declarer + dummy), and only its own seat when
        defending. Returns 'client' or 'biq'."""
        cs = self.client_seat.is_ns()
        if declarer.is_ns() == cs:           # client's side declares
            return "client" if seat.is_ns() == cs else "biq"
        return "client" if seat == self.client_seat else "biq"

    def _run_play(self, hands, contract, vul):
        trump = None if contract.suit == Suit.NOTRUMP else contract.suit
        board = BoardState(board_number=1, dealer=contract.declarer,
                           vulnerability=vul,
                           hands={s: Hand(cards=list(hands[s].cards))
                                  for s in hands},
                           auction=[], contract=contract)
        decl_tricks = 0
        leader = contract.declarer.next()
        for _ in range(13):
            trick = Trick(leader=leader)
            board.current_trick = trick
            cur = leader
            for _ in range(4):
                if self._plays_seat(cur, contract.declarer) == "client":
                    tok = self.recv_expect("card")
                    card = parse_card_token(tok[1])
                else:
                    if len(board.tricks) == 0 and len(trick.cards) == 0:
                        resp = self.engine.get_opening_lead(board)
                    else:
                        resp = self.engine.get_mc_card_play(
                            board, cur, list(trick.cards),
                            num_samples=self.samples)
                    card = resp.action
                    self.send("card", cur.name.title(), format_card(card))
                board.hands[cur].remove_card(card)
                trick.add_card(card, trump)
                cur = cur.next()
            board.current_trick = None
            board.tricks.append(trick)
            w = trick.winner
            if w.is_ns() == contract.declarer.is_ns():
                decl_tricks += 1
            leader = w
        return decl_tricks

    # ---- scoring + report ----
    def _report(self, label, hands, vul, contract, decl_tricks):
        pbn = f"N:{_pbn(hands)}"
        t = self.dds.solve_dd_table(pbn)
        if contract is None:
            open_ns = 0
        else:
            decl_vul = vul.is_vulnerable(contract.declarer)
            sc = calculate_contract_score(contract, decl_tricks, decl_vul)
            open_ns = sc if contract.declarer.is_ns() else -sc
        # Closed room = biq self-play (both pairs biq) on the same board → the
        # teams comparison "client's table vs an all-biq table".
        closed_ns = self._closed_room(hands, vul)
        imp = diff_to_imps(open_ns - closed_ns)
        self.results.append({"label": label,
                             "contract": self._cstr(contract),
                             "open_ns": open_ns, "closed_ns": closed_ns,
                             "imp": imp})
        # Mirror Q-Plus's report_score shape closely enough for the existing
        # parsers (DI / DD / RE / IM).
        self.send("report_score", "2",
                  f'DI "{label}";DD "{vul_str(vul)} {pbn}";'
                  f'RE {open_ns} {closed_ns};IM {max(imp,0)} {max(-imp,0)};')
        self.log(f"{label}: {self._cstr(contract)} open_ns={open_ns} "
                 f"closed_ns={closed_ns} IMP={imp:+d}")

    def _closed_room(self, hands, vul):
        """biq bids+DD-scores the same board (all four seats biq)."""
        dealer = Seat.NORTH  # dealer doesn't affect the DD score we use
        auction = []
        seat = dealer
        for _ in range(60):
            st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
            bid = decide_bid(st, evaluate_hand(hands[seat]),
                             self._sys_for(seat))
            auction.append(bid)
            if self._auction_over(auction):
                break
            seat = seat.next()
        c = self._derive_contract(auction, dealer)
        if c is None:
            return 0
        pbn = f"N:{_pbn(hands)}"
        t = self.dds.solve_dd_table(pbn)
        strain = _STRAIN[c.suit]
        tricks = t["NESW"[c.declarer.value]][strain]
        sc = calculate_contract_score(c, tricks, vul.is_vulnerable(c.declarer))
        return sc if c.declarer.is_ns() else -sc

    @staticmethod
    def _cstr(c):
        if c is None:
            return "PASS"
        return (f"{c.level}{_STRAIN[c.suit]}"
                f"{'XX' if c.redoubled else 'X' if c.doubled else ''} "
                f"{c.declarer.name[0]}")

    def close(self):
        try:
            if self.conn:
                self.conn.close()
            if self.sock:
                self.sock.close()
        except OSError:
            pass


def vul_str(v):
    return {Vulnerability.NONE: "None", Vulnerability.NS: "NS",
            Vulnerability.EW: "EW", Vulnerability.BOTH: "All"}[v]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=5555)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--client-seat", default="South",
                   choices=["North", "East", "South", "West"])
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--start-board", type=int, default=1)
    p.add_argument("--boards", type=int, default=64)
    p.add_argument("--ns-system", default="SAYC")
    p.add_argument("--ew-system", default="SAYC")
    p.add_argument("--samples", type=int, default=40)
    p.add_argument("--score-log", default=None)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    srv = BiqServer(a.port, Seat[a.client_seat.upper()], a.seed,
                    a.start_board, a.boards, a.ns_system, a.ew_system,
                    a.score_log, host=a.host, samples=a.samples,
                    verbose=not a.quiet)
    try:
        srv.accept()
        srv.handshake()
        srv.run_match()
    except (ConnectionError, KeyboardInterrupt) as e:
        srv.log(f"stopped: {e}")
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
