#!/usr/bin/env python3
"""Scripted Blue Chip protocol client, for testing biq_bluechip_tm.py
without a real robot. It follows the robot's side of protocol version 18
strictly (connect, seat, deal, ready-for messages, dummy, "to lead") with a
trivial strategy: open one of its longest suit with 12+ HCP (or 1NT when
balanced), raise partner's suit with 3+ cards and 8+ HCP once, otherwise
pass; play the lowest legal card. Each run plays as one seat.

  python3 tools/bluechip_test_client.py --seat East [--host 127.0.0.1] [--port 2000]
"""
from __future__ import annotations

import argparse
import re
import socket
import sys
import time

SEATS = ["North", "East", "South", "West"]
RANKS = "AKQJT98765432"
STRAIN = ["C", "D", "H", "S", "NT"]


class Client:
    def __init__(self, a):
        self.me = a.seat.title()
        self.mi = SEATS.index(self.me)
        self.sock = socket.create_connection((a.host, a.port))
        self.buf = b""
        self.verbose = not a.quiet
        self.freeze_after = a.freeze_after   # stop answering after N messages (a frozen robot)
        self.die_after = a.die_after         # disconnect after N messages
        self.n_recv = 0
        self.in_board = False

    def send(self, s):
        if self.verbose:
            print(f"{self.me} -> {s}", flush=True)
        self.sock.sendall((s + "\r\n").encode())

    def recv(self):
        while b"\n" not in self.buf:
            d = self.sock.recv(4096)
            if not d:
                raise SystemExit(f"{self.me}: server closed")
            self.buf += d
        i = self.buf.index(b"\n")
        line = self.buf[:i].decode().strip()
        self.buf = self.buf[i + 1:]
        if self.verbose:
            print(f"{self.me} <- {line}", flush=True)
        self.n_recv += 1
        if self.freeze_after and self.n_recv >= self.freeze_after:
            print(f"{self.me}: freezing after {self.n_recv} messages", flush=True)
            time.sleep(10 ** 6)
        if self.die_after and self.n_recv >= self.die_after:
            print(f"{self.me}: disconnecting after {self.n_recv} messages", flush=True)
            self.sock.close()
            raise SystemExit(0)
        if self.in_board and line.lower() == "start of board":
            raise Restart()                  # the TM replays the board (a robot failed over)
        return line

    @staticmethod
    def parse_hand(line):
        """'... : S A K 3. H -. D ... C ...' -> set of cards like 'AS'."""
        body = line.split(":", 1)[1]
        cards = set()
        for part in body.split("."):
            toks = part.split()
            if not toks:
                continue
            suit = toks[0]
            for r in toks[1:]:
                if r != "-":
                    cards.add(r + suit)
        return cards

    # ------------------------------------------------------------ strategy
    @staticmethod
    def hcp(cards):
        return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(c[0], 0) for c in cards)

    def choose_call(self, auction, dealer_i):
        bids = [(i, b) for i, b in enumerate(auction) if b not in ("P", "X", "XX")]
        lens = {s: sum(1 for c in self.hand if c[1] == s) for s in "SHDC"}
        p = self.hcp(self.hand)
        if not bids:
            if p >= 12:
                if sorted(lens.values()) in ([3, 3, 3, 4], [2, 3, 4, 4], [2, 3, 3, 5]) and 15 <= p <= 17:
                    return "1NT"
                s = max("SHDC", key=lambda x: (lens[x], "CDHS".index(x)))
                return "1" + s
            return "P"
        last_i, last = bids[-1]
        bidder = (dealer_i + last_i) % 4
        if bidder == (self.mi + 2) % 4 and last[-1] in "SHDC" and int(last[0]) < 3:
            mine = [b for i, b in enumerate(auction) if (dealer_i + i) % 4 == self.mi and b != "P"]
            if not mine and lens[last[-1]] >= 3 and p >= 8:
                return f"{int(last[0]) + 1}{last[-1]}"
        return "P"

    def lowest_legal(self, hand, trick):
        if trick:
            follow = [c for c in hand if c[1] == trick[0][1]]
            if follow:
                hand = follow
        return max(hand, key=lambda c: RANKS.index(c[0]))

    # --------------------------------------------------------------- flow
    def run(self):
        self.send(f'Connecting "tester" as {self.me} using protocol version 18')
        self.recv()                                  # seated
        self.send(f"{self.me} ready for teams")
        self.recv()                                  # Teams : ...
        self.send(f"{self.me} ready to start")
        restart = False
        while True:
            if not restart:
                line = self.recv()
                if line.lower().startswith("end of session"):
                    return
                if line.lower() != "start of board":
                    continue                             # Timing etc.
            restart = False
            try:
                self.in_board = True
                self.send(f"{self.me} ready for deal")
                info = self.recv()
                m = re.search(r"Dealer (\w+)\.", info)
                dealer_i = SEATS.index(m.group(1).title())
                self.send(f"{self.me} ready for cards")
                self.hand = self.parse_hand(self.recv())
                self.board(dealer_i)
            except Restart:
                restart = True
            finally:
                self.in_board = False

    def board(self, dealer_i):
        auction = []
        turn = dealer_i
        while not self.over(auction):
            if turn == self.mi:
                c = self.choose_call(auction, dealer_i)
                self.send(f"{self.me} passes" if c == "P" else f"{self.me} bids {c}")
            else:
                self.send(f"{self.me} ready for {SEATS[turn]}'s bid")
                line = self.recv()
                c = self.call_of(line)
            auction.append(c)
            turn = (turn + 1) % 4
        bids = [(i, b) for i, b in enumerate(auction) if b not in ("P", "X", "XX")]
        if not bids:
            return
        last_i, last = bids[-1]
        side = (dealer_i + last_i) % 2
        strain = last[1:]
        decl = next((dealer_i + i) % 4 for i, b in bids
                    if (dealer_i + i) % 2 == side and b[1:] == strain)
        dummy = (decl + 2) % 4
        trump = None if strain == "NT" else strain
        dummy_hand = set(self.hand) if dummy == self.mi else None
        leader = (decl + 1) % 4
        for t in range(1, 14):
            trick = []
            for k in range(4):
                p = (leader + k) % 4
                actor = decl if p == dummy else p
                if actor == self.mi:
                    if k == 0:
                        self.recv()                  # "East to lead" / "Dummy to lead"
                    hand = dummy_hand if p == dummy else self.hand
                    card = self.lowest_legal(hand, trick)
                    self.send(f"{SEATS[p]} plays {card}")
                else:
                    who = "dummy" if p == dummy else SEATS[p]
                    self.send(f"{self.me} ready for {who}'s card to trick {t}")
                    card = self.recv().split()[-1].upper()
                (dummy_hand if p == dummy and dummy_hand is not None else
                 self.hand if p == self.mi else set()).discard(card)
                trick.append(card)
                if t == 1 and k == 0 and self.mi != dummy:
                    self.send(f"{self.me} ready for dummy")
                    dummy_hand = self.parse_hand(self.recv())
            leader = (leader + self.winner(trick, trump)) % 4

    @staticmethod
    def winner(trick, trump):
        best = 0
        for i, c in enumerate(trick[1:], 1):
            b = trick[best]
            if trump and c[1] == trump and b[1] != trump:
                best = i
            elif c[1] == b[1] and RANKS.index(c[0]) < RANKS.index(b[0]):
                best = i
        return best

    @staticmethod
    def call_of(line):
        w = line.split()
        if w[1].lower() == "passes":
            return "P"
        if w[1].lower() == "doubles":
            return "X"
        if w[1].lower() == "redoubles":
            return "XX"
        return w[2].rstrip(".").upper()

    @staticmethod
    def over(a):
        return (len(a) >= 4 and all(b == "P" for b in a[-3:]) and any(b != "P" for b in a[:-3])) \
            or (len(a) == 4 and all(b == "P" for b in a))


class Restart(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat", required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--freeze-after", type=int, default=0)
    ap.add_argument("--die-after", type=int, default=0)
    Client(ap.parse_args()).run()


if __name__ == "__main__":
    sys.exit(main())
