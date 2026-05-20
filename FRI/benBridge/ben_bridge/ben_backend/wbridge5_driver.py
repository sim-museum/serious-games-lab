"""Bridge Table Manager (TM) protocol driver for wbridge5.

The BBO Table Manager Protocol is a text-over-TCP, line-oriented
protocol that bridge engines (wbridge5, GIB, JACK, etc.) speak to
talk to an external "table manager" — a process that orchestrates
the auction and play. We implement the SERVER side (the TM) and
launch wbridge5 as a CLIENT connected to it, then drive deals
through the auction phase to capture wbridge5's bids per seat.

This file provides three pieces:

  * `TMConnection` — wraps a socket. Sends and receives one TM
    line at a time. Handles `\\r\\n` framing, debug logging.

  * `TMServer` — listens on a port, accepts a client connection,
    runs the protocol's deal handshake. Hands out one auction
    per call to `play_one_deal`.

  * `Wbridge5Driver` — convenience wrapper. Launches wbridge5
    under Wine, points it at our TMServer, and exposes
    `auction_for(board)` that returns the list of bids
    wbridge5's engine made for that deal.

The protocol message templates we use are drawn from inspection of
wbridge5's own binary strings (`grep -i "using protocol version"`)
and BBO's TM protocol spec. Specifically the message classes we
handle:

  Server → client:
    "<seat> ("<name>") seated"
    "Teams: N/S : "ben_bridge". E/W : "ben_bridge"."
    "Start of board"
    "Board number <N>. Dealer <S>. <V> vulnerable."
    "<seat>'s cards : S K Q J. H A K 2. D Q J. C T 9 8 7 6 5."
    "<seat> ready for bid"
    "<seat> bids <bid>"      # forwarded from another seat
    "Timing - ..."
    "End of board"

  Client → server:
    "Connecting "<name>" as <seat> using protocol version 18"
    "<seat> ready for teams"
    "<seat> ready to start"
    "<seat> ready for deal"
    "<seat> ready for cards"
    "<seat> ready for <other>'s bid"
    "<seat> bids <bid>"

Lines are framed by `\\r\\n`. Bid format: "Pass" / "X" / "XX" / a
level + suit letter like "1H" or "3NT". Card format: rank-suit
like "KH" or "TC".

Card play is NOT yet plumbed through here — for the SAYC-wbridge5
tuning use case we only need the auction. Card play can be added
in a follow-up by extending `play_one_deal` past the auction-end
condition.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import Bid, Card, Hand, Rank, Seat, Suit, Vulnerability


# Protocol version we identify as.  wbridge5 5.12 speaks version 18.
TM_PROTOCOL_VERSION = 18

# CRLF framing per the TM spec.
_EOL = b"\r\n"


# Map ben_bridge enum identities to TM-protocol string tokens.
_SEAT_TM = {Seat.NORTH: "North", Seat.EAST: "East",
            Seat.SOUTH: "South", Seat.WEST: "West"}
_TM_SEAT = {v: k for k, v in _SEAT_TM.items()}

_VUL_TM = {
    Vulnerability.NONE: "Neither",
    Vulnerability.NS:   "N/S",
    Vulnerability.EW:   "E/W",
    Vulnerability.BOTH: "Both",
}

_RANK_TM = {Rank.ACE: "A", Rank.KING: "K", Rank.QUEEN: "Q",
            Rank.JACK: "J", Rank.TEN: "T", Rank.NINE: "9",
            Rank.EIGHT: "8", Rank.SEVEN: "7", Rank.SIX: "6",
            Rank.FIVE: "5", Rank.FOUR: "4", Rank.THREE: "3",
            Rank.TWO: "2"}
_TM_RANK = {v: k for k, v in _RANK_TM.items()}

_SUIT_TM = {Suit.SPADES: "S", Suit.HEARTS: "H",
            Suit.DIAMONDS: "D", Suit.CLUBS: "C"}
_TM_SUIT = {v: k for k, v in _SUIT_TM.items()}


def _format_hand_for_tm(hand: Hand) -> str:
    """Render a hand as 'S K Q J. H A K 2. D Q J. C T 9 8 7 6 5'."""
    by_suit = {s: [] for s in (Suit.SPADES, Suit.HEARTS,
                                Suit.DIAMONDS, Suit.CLUBS)}
    for c in hand.cards:
        by_suit[c.suit].append(c.rank)
    parts = []
    for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS):
        # Sort A→2 by rank.value (ACE=0 is high in this codebase).
        ranks = sorted(by_suit[s], key=lambda r: r.value)
        body = " ".join(_RANK_TM[r] for r in ranks) if ranks else "-"
        parts.append(f"{_SUIT_TM[s]} {body}")
    return ". ".join(parts) + "."


def _format_bid_for_tm(bid: Bid) -> str:
    """Render a Bid as 'Pass' / 'X' / 'XX' / '1H' / '3NT'."""
    if bid.is_pass:
        return "Pass"
    if bid.is_double:
        return "X"
    if bid.is_redouble:
        return "XX"
    if bid.suit is None:
        return "?"
    if bid.suit == Suit.NOTRUMP:
        return f"{bid.level}NT"
    return f"{bid.level}{_SUIT_TM[bid.suit]}"


def _parse_bid_from_tm(token: str) -> Bid:
    """Reverse of _format_bid_for_tm. Tolerant of case + whitespace."""
    t = token.strip().upper()
    if t in ("PASS", "P"):
        return Bid.make_pass()
    if t in ("DOUBLE", "X", "DBL"):
        return Bid.make_double()
    if t in ("REDOUBLE", "XX", "RDBL"):
        return Bid.make_redouble()
    if len(t) < 2:
        raise ValueError(f"Bad TM bid token: {token!r}")
    level = int(t[0])
    rest = t[1:]
    if rest in ("NT", "N"):
        return Bid(level=level, suit=Suit.NOTRUMP)
    if rest in _TM_SUIT:
        return Bid(level=level, suit=_TM_SUIT[rest])
    raise ValueError(f"Bad TM bid token: {token!r}")


# ---------------------------------------------------------------------------
# Connection layer
# ---------------------------------------------------------------------------


class TMConnection:
    """Line-framed socket wrapper for the TM protocol.

    Reads CRLF-framed text from the socket and writes CRLF-framed
    text to it. Maintains a small read buffer so partial lines
    don't get lost between recv() calls. Optionally logs every
    line through `log_fn(direction, line)` — useful when bringing
    up wbridge5 and verifying we speak the right dialect.
    """

    def __init__(self, sock: socket.socket, log_fn=None):
        self._sock = sock
        self._buf = b""
        self._log_fn = log_fn
        self._sock.settimeout(60.0)

    def send_line(self, line: str) -> None:
        if self._log_fn:
            self._log_fn("→", line)
        self._sock.sendall(line.encode("ascii") + _EOL)

    def recv_line(self) -> str:
        while _EOL not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("TM peer closed the connection")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(_EOL)
        text = line.decode("ascii", errors="replace").strip()
        if self._log_fn:
            self._log_fn("←", text)
        return text

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Per-deal interaction
# ---------------------------------------------------------------------------


@dataclass
class TMDeal:
    """One auction-only deal exchanged through the TM protocol.

    `hands` covers all four seats — the TM hands out each player
    their own cards (per protocol) but the server (us) needs all
    four for record-keeping.
    """
    board_number: int
    dealer: Seat
    vulnerability: Vulnerability
    hands: Dict[Seat, Hand]
    auction: List[Bid] = field(default_factory=list)


class TMServer:
    """A minimal Table Manager server.

    Single-engine flavour: we expect ONE client (e.g. wbridge5)
    that's been told to play all four seats. The protocol-version
    handshake happens once per connection; afterwards we hand out
    deals via `play_one_deal`. The auction proceeds until three
    consecutive passes after a non-pass bid (or four straight
    passes at start of auction).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 *, name: str = "ben_bridge_tm",
                 log_fn=None):
        self._name = name
        self._log_fn = log_fn
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, port))
        self._listener.listen(1)
        self._listener.settimeout(120.0)
        self.host, self.port = self._listener.getsockname()
        self._conns: Dict[Seat, TMConnection] = {}
        # The connect-handshake state: each seat sends
        # "<seat> ready for teams" once it's seated.
        self._seated: Dict[Seat, str] = {}

    # ---- Connection-time handshake ------------------------------------

    def accept_one_client(self, *, timeout: float = 30.0) -> TMConnection:
        """Block until a single TM client connects, then return the
        wrapped TMConnection. Used when the engine handles all 4
        seats over one socket — wbridge5's typical configuration.
        """
        self._listener.settimeout(timeout)
        conn_sock, _peer = self._listener.accept()
        return TMConnection(conn_sock, log_fn=self._log_fn)

    def accept_four_seats(self, *, timeout: float = 60.0
                          ) -> Dict[Seat, TMConnection]:
        """Accept four sequential connections, one per seat.

        Some engines (notably JACK) prefer a separate socket per
        seat. wbridge5 can run either way; this helper supports
        the per-seat variant. Returns a dict keyed by Seat after
        each client has identified itself via the connect line.
        """
        out: Dict[Seat, TMConnection] = {}
        deadline = time.time() + timeout
        while len(out) < 4:
            remaining = max(1.0, deadline - time.time())
            self._listener.settimeout(remaining)
            conn_sock, _peer = self._listener.accept()
            conn = TMConnection(conn_sock, log_fn=self._log_fn)
            seat, name = self._read_connect(conn)
            out[seat] = conn
            self._seated[seat] = name
        return out

    def _read_connect(self, conn: TMConnection) -> Tuple[Seat, str]:
        """Parse the client's opening
            `Connecting "<name>" as <seat> using protocol version <n>`
        and reply with `<seat> ("<name>") seated`.
        """
        line = conn.recv_line()
        # Robust to extra whitespace and quote-style variations.
        import re
        m = re.match(
            r'\s*Connecting\s+"([^"]+)"\s+as\s+(\w+)\s+using\s+protocol\s+version\s+(\d+)',
            line,
        )
        if not m:
            raise ValueError(f"unexpected TM connect line: {line!r}")
        name, seat_word, _ver = m.group(1), m.group(2), m.group(3)
        seat = _TM_SEAT.get(seat_word.capitalize())
        if seat is None:
            raise ValueError(f"bad seat in TM connect: {seat_word}")
        conn.send_line(f'{seat_word} ("{name}") seated')
        return seat, name

    # ---- Per-deal auction loop ----------------------------------------

    def _seats_send(self, conns, line):
        """Send a line to every seat — used for global broadcasts."""
        for c in conns.values():
            c.send_line(line)

    def play_auction(self, conns: Dict[Seat, TMConnection],
                     deal: TMDeal) -> List[Bid]:
        """Run one TM auction with the given client(s).

        Supports both single-socket-for-all-seats (`len(conns)==1`,
        keyed by any Seat) and per-seat-socket configurations.

        Returns the auction as a list of Bid objects.
        """
        single_socket = len(conns) == 1
        any_conn = next(iter(conns.values()))

        # 1) Teams + start-of-board boilerplate.
        for c in conns.values():
            c.send_line(f'Teams: N/S : "{self._name}". E/W : "{self._name}".')
        # Each seat acknowledges teams.
        for seat, conn in conns.items():
            line = conn.recv_line()
            if "ready for" not in line.lower():
                raise ValueError(f"expected ready-for-start, got {line!r}")

        for c in conns.values():
            c.send_line("Start of board")
        vul_word = _VUL_TM.get(deal.vulnerability, "Neither")
        board_line = (f"Board number {deal.board_number}. "
                      f"Dealer {_SEAT_TM[deal.dealer]}. "
                      f"{vul_word} vulnerable.")
        for c in conns.values():
            c.send_line(board_line)

        # Each seat reads its own cards.
        for seat, conn in conns.items():
            # The client asks; we send only when asked. Loop until
            # we see the matching ready-for-cards.
            line = conn.recv_line()
            if "ready for cards" not in line.lower() and "ready for deal" not in line.lower():
                raise ValueError(f"expected ready-for-cards, got {line!r}")
            # In the single-socket case the engine asks per-seat; we
            # deal out every seat's hand on the same socket.
            if single_socket:
                for s in (Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST):
                    conn.send_line(
                        f"{_SEAT_TM[s]}'s cards : {_format_hand_for_tm(deal.hands[s])}"
                    )
            else:
                conn.send_line(
                    f"{_SEAT_TM[seat]}'s cards : {_format_hand_for_tm(deal.hands[seat])}"
                )

        # 2) Auction loop. Bidder = dealer + len(bids) clockwise.
        bidder = deal.dealer
        auction: List[Bid] = []
        consecutive_passes = 0
        while True:
            bidder_word = _SEAT_TM[bidder]
            conn_for_bidder = conns.get(bidder, any_conn)
            # Other seats announce "ready for bidder's bid".
            for s, c in conns.items():
                if s == bidder:
                    continue
                # We're playing TM server — clients send us
                # ready-for-bid lines; we read them.
                line = c.recv_line()
                # We just discard the announcement; client is in sync.
            # Bidder's seat sends its bid.
            line = conn_for_bidder.recv_line()
            # Format: "<seat> bids <bid>" or "<seat> doubles" /
            # "<seat> redoubles".
            import re
            m = re.match(
                r'\s*(\w+)\s+(bids|doubles|redoubles|passes)\b\s*(\S*)',
                line, re.I,
            )
            if not m:
                raise ValueError(f"bad bid line: {line!r}")
            verb, payload = m.group(2).lower(), m.group(3)
            if verb == "passes":
                bid = Bid.make_pass()
            elif verb == "doubles":
                bid = Bid.make_double()
            elif verb == "redoubles":
                bid = Bid.make_redouble()
            else:
                bid = _parse_bid_from_tm(payload)
            auction.append(bid)
            # Broadcast back to every seat (so each engine knows
            # the auction state in lockstep).
            broadcast_line = f"{bidder_word} bids {_format_bid_for_tm(bid)}"
            for s, c in conns.items():
                if s == bidder:
                    continue
                c.send_line(broadcast_line)

            # Termination check.
            if bid.is_pass:
                consecutive_passes += 1
            else:
                consecutive_passes = 0
            if len(auction) >= 4 and consecutive_passes >= 3:
                break
            if len(auction) >= 4 and consecutive_passes == 4 \
                    and not any(not b.is_pass for b in auction):
                # Four-pass start-of-auction = passed out.
                break
            bidder = bidder.next()

        deal.auction = auction
        return auction


# ---------------------------------------------------------------------------
# wbridge5 launcher
# ---------------------------------------------------------------------------


def _wbridge5_install_dir() -> Optional[str]:
    """Best-effort guess at the wbridge5 install path."""
    here = os.path.dirname(os.path.abspath(__file__))
    fri_root = os.path.normpath(os.path.join(here, "..", "..", ".."))
    cand = os.path.join(fri_root, "WP", "drive_c", "wbridge5")
    if os.path.isdir(cand):
        return cand
    return None


class Wbridge5Driver:
    """Spawn wbridge5 under Wine and route it through TMServer.

    Usage:

        srv = TMServer(port=0)
        drv = Wbridge5Driver(server=srv)
        drv.start()                   # launches wbridge5
        conns = srv.accept_four_seats()
        for deal in deals:
            srv.play_auction(conns, deal)
            print(deal.auction)
        drv.stop()

    NOTE: as of wbridge5 5.12, putting it into TM-client mode is
    a GUI operation (File → Bridge Table Manager → connect). The
    INI exposes Port / Adresse, but those are persisted state,
    not auto-connect flags. Until we find a CLI flag for it, the
    user has to click "Connect to TM" once per wbridge5 launch.
    The driver writes the host/port into the INI so the user just
    has to hit OK in the dialog.
    """

    def __init__(self, server: 'TMServer',
                 install_dir: Optional[str] = None,
                 wine_bin: Optional[str] = None):
        self.server = server
        self.install_dir = install_dir or _wbridge5_install_dir()
        if self.install_dir is None:
            raise FileNotFoundError(
                "Could not locate wbridge5 install — pass install_dir=...")
        self.wine_bin = wine_bin or os.environ.get("WINE") or "wine"
        self._proc: Optional[subprocess.Popen] = None

    def _patch_ini(self) -> None:
        """Pre-populate the WBRIDGE5.INI with our TM host/port so
        the user only has to click OK when wbridge5 prompts.
        """
        ini = os.path.join(self.install_dir, "WBRIDGE5.INI")
        if not os.path.isfile(ini):
            return
        host = self.server.host
        port = self.server.port
        lines = []
        seen_addr = seen_port = False
        for ln in open(ini, "r", encoding="latin-1", errors="replace"):
            if ln.startswith("Port="):
                lines.append(f"Port={port}\n")
                seen_port = True
            elif ln.startswith("Adresse="):
                lines.append(f"Adresse={host}\n")
                seen_addr = True
            else:
                lines.append(ln)
        if not seen_port:
            lines.append(f"Port={port}\n")
        if not seen_addr:
            lines.append(f"Adresse={host}\n")
        with open(ini, "w", encoding="latin-1") as f:
            f.writelines(lines)

    def start(self, env: Optional[Dict[str, str]] = None) -> None:
        """Launch wbridge5 under Wine. Returns immediately; the
        caller is responsible for calling
        `server.accept_four_seats()` once the user (or future
        automation) has put wbridge5 into TM-client mode.
        """
        self._patch_ini()
        env_full = os.environ.copy()
        if env:
            env_full.update(env)
        wineprefix = env_full.get("WINEPREFIX")
        if wineprefix is None:
            here = os.path.dirname(os.path.abspath(__file__))
            fri_root = os.path.normpath(os.path.join(here, "..", "..", ".."))
            wineprefix = os.path.join(fri_root, "WP")
        env_full["WINEPREFIX"] = wineprefix
        env_full.setdefault("WINEARCH", "win32")
        exe = os.path.join(self.install_dir, "Wbridge5.exe")
        self._proc = subprocess.Popen(
            [self.wine_bin, exe],
            cwd=self.install_dir,
            env=env_full,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
