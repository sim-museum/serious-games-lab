#!/usr/bin/env python3
"""Headless integration test for pokerIQ multi-client networking.

Spins up a real PokerServer plus several PokerClients inside one Qt event
loop over 127.0.0.1 and asserts:

  1. Host accepts unique, short names.
  2. Duplicate name is rejected with code 'name_taken'.
  3. Overlong name (>MAX_NAME_LEN chars) is rejected with 'name_too_long'.
  4. Empty name is rejected with 'name_empty'.
  5. Seat pick succeeds; same seat is rejected for the next client.
  6. Table-full check rejects when no seats remain.
  7. Host-broadcast TOM_ADVICE reaches the correct client and no others.

Run with:  python3 test_multi_client.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QTimer, QEventLoop
from PyQt6.QtWidgets import QApplication

from network.protocol import MAX_NAME_LEN
from network.server import PokerServer
from network.client import PokerClient


class Collector:
    def __init__(self, name):
        self.name = name
        self.connected = False
        self.server_name = None
        self.reject = None          # (reason, code)
        self.seat = None
        self.seat_reject = None
        self.tom = []               # (advice, notation, for_seat)
        self.analyses = None        # list of dicts from HAND_ANALYSIS
        self.analysis_hand = None   # hand_number for last HAND_ANALYSIS

    def attach(self, client):
        client.connected.connect(
            lambda sn, _c=self: setattr(_c, 'connected', True) or setattr(_c, 'server_name', sn))

        def on_fail(reason, _c=self, _cl=client):
            # Pull the code out of the last CONNECT_REJECT payload if we can.
            code = getattr(_cl, '_last_reject_code', "")
            _c.reject = (reason, code)
        client.connection_failed.connect(on_fail)

        client.seat_confirmed.connect(lambda s, _c=self: setattr(_c, 'seat', s))
        client.seat_rejected.connect(lambda r, _c=self: setattr(_c, 'seat_reject', r))
        client.tom_advice_received.connect(
            lambda a, n, fs, _c=self: _c.tom.append((a, n, fs)))

        def on_analysis(analyses, hand_num, _c=self):
            _c.analyses = list(analyses)
            _c.analysis_hand = hand_num
        client.hand_analysis_received.connect(on_analysis)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def patch_reject_code_capture():
    """Monkey-patch PokerClient._handle_message to remember the last reject code.

    The public connection_failed signal carries only the reason string. For
    the test we want to see the 'code' field too, so we sniff it from the
    raw message before the existing handler runs.
    """
    from network.client import PokerClient
    from network.protocol import MessageType
    original = PokerClient._handle_message

    def patched(self, msg):
        if msg.type == MessageType.CONNECT_REJECT:
            self._last_reject_code = msg.payload.get('code', '')
        return original(self, msg)

    PokerClient._handle_message = patched


def attempt(name, host, port, results, results_key, seat=None):
    """Spawn one client, connect with `name`, optionally request a seat,
    wait for handshake to complete."""
    client = PokerClient(player_name=name)
    col = Collector(name)
    col.attach(client)
    results[results_key] = (client, col)

    client.connect_to_server(host, port)
    # Give the handshake ~400ms to complete (accept or reject)
    wait(400)

    if seat is not None and col.connected and col.reject is None:
        client.request_seat(seat)
        wait(250)

    return client, col


def main():
    # QApplication (not QCoreApplication) so we can also unit-test
    # RaiseDialog, which is a QWidget.
    app = QApplication.instance() or QApplication(sys.argv)
    patch_reject_code_capture()

    port = 47778  # off the default pokerIQ port
    print(f"Starting host on 127.0.0.1:{port}")
    server = PokerServer(server_name="TestTable", num_seats=4,
                         host_seat=0, host_name="Host")
    assert server.start(port), "server failed to listen"
    wait(150)

    results = {}

    # 1) Two legitimate guests — Alice and Bob — each in a distinct seat
    print("\n[1] Alice joins, takes seat 1")
    attempt("Alice", "127.0.0.1", port, results, "alice", seat=1)
    _, alice = results["alice"]
    assert alice.connected, f"Alice not connected: {alice.reject}"
    assert alice.seat == 1, f"Alice seat not confirmed: {alice.seat}"

    print("[2] Bob joins, takes seat 2")
    attempt("Bob", "127.0.0.1", port, results, "bob", seat=2)
    _, bob = results["bob"]
    assert bob.connected, f"Bob not connected: {bob.reject}"
    assert bob.seat == 2

    # 2) Duplicate name — "Alice" again — must be rejected
    print("[3] 'Alice' attempts to join again — should be rejected (name_taken)")
    attempt("Alice", "127.0.0.1", port, results, "alice_dup")
    _, alice_dup = results["alice_dup"]
    assert not alice_dup.connected, "Duplicate name should not be accepted"
    assert alice_dup.reject is not None, "Expected reject message"
    assert alice_dup.reject[1] == "name_taken", \
        f"Expected code name_taken, got {alice_dup.reject!r}"

    # 3) Host's own name collision — trying "Host" (the host_name) should also fail
    print("[4] 'Host' (same as host name) — rejected (name_taken)")
    attempt("Host", "127.0.0.1", port, results, "host_dup")
    _, host_dup = results["host_dup"]
    assert not host_dup.connected
    assert host_dup.reject[1] == "name_taken", host_dup.reject

    # 4) Overlong name
    long_name = "x" * (MAX_NAME_LEN + 3)
    print(f"[5] '{long_name}' — rejected (name_too_long)")
    attempt(long_name, "127.0.0.1", port, results, "longname")
    _, longc = results["longname"]
    assert not longc.connected
    assert longc.reject[1] == "name_too_long", longc.reject

    # 5) Empty name
    print("[6] '' (empty) — rejected (name_empty)")
    attempt("", "127.0.0.1", port, results, "empty")
    _, emptyc = results["empty"]
    assert not emptyc.connected
    assert emptyc.reject[1] == "name_empty", emptyc.reject

    # 6) Seat collision — Carol joins then tries seat 1 (Alice's seat)
    print("[7] Carol joins, tries seat 1 (taken) then seat 3")
    attempt("Carol", "127.0.0.1", port, results, "carol")
    _, carol = results["carol"]
    carol_client, _ = results["carol"]
    assert carol.connected, f"Carol not connected: {carol.reject}"
    carol_client.request_seat(1)
    wait(250)
    assert carol.seat is None, "Carol should NOT be confirmed at taken seat 1"
    assert carol.seat_reject is not None
    # Now take seat 3
    carol_client.request_seat(3)
    wait(250)
    assert carol.seat == 3, f"Carol should have seat 3, got {carol.seat}"

    # 7) Table is now full (host seat 0, Alice 1, Bob 2, Carol 3). Dan can
    # connect (server has 4 seats, 3 clients already connected but host seat
    # reserved too, so free seat count = 0 -> 'full' reject).
    print("[8] Dan tries to join — table full")
    attempt("Dan", "127.0.0.1", port, results, "dan")
    _, dan = results["dan"]
    # Depending on timing, Dan may still handshake but hit the 'full' check
    # before seat assignment. Either way the server must reject with 'full'.
    if dan.connected:
        # Edge case: host sent accept before the seat count logic ran. In
        # that event the seat requests all fail. Our impl rejects before
        # accept, so we expect no accept here.
        raise AssertionError("Dan should have been rejected for full table")
    assert dan.reject[1] == "full", dan.reject

    # 8) TOM advice routing — host sends personalized advice to each client
    print("[9] TOM advice routed per seated client")
    advice_map = {
        1: {'advice': 'Alice: think about pot odds.', 'notation': ''},
        2: {'advice': 'Bob: consider folding weak aces.', 'notation': 'AKs-AQs'},
        3: {'advice': 'Carol: BTN is premium — widen your opens.', 'notation': ''},
    }
    server.broadcast_tom_advice_per_client(advice_map)
    wait(250)

    assert len(alice.tom) == 1 and "pot odds" in alice.tom[0][0], alice.tom
    assert alice.tom[0][2] == 1, "for_seat must equal Alice's seat"
    assert len(bob.tom) == 1 and "folding weak aces" in bob.tom[0][0], bob.tom
    assert bob.tom[0][1] == "AKs-AQs", "Bob's notation must route through"
    assert len(carol.tom) == 1 and "BTN" in carol.tom[0][0], carol.tom

    # 9) HAND_ANALYSIS — host broadcasts a bundle of per-player critiques;
    # every connected client receives the same bundle intact.
    print("[10] HAND_ANALYSIS broadcast reaches every client")
    bundle = [
        {'player': 'Host',  'seat': 0, 'text': 'Host: your 3-bet was thin.'},
        {'player': 'Alice', 'seat': 1, 'text': 'Alice: good pot-control line.'},
        {'player': 'Bob',   'seat': 2, 'text': 'Bob: consider folding OOP next time.'},
        {'player': 'Carol', 'seat': 3, 'text': 'Carol: nailed the river bet size.'},
    ]
    server.broadcast_hand_analysis(bundle, hand_number=42)
    wait(250)

    for who in (alice, bob, carol):
        assert who.analyses is not None, f"{who.name} got no HAND_ANALYSIS"
        assert who.analysis_hand == 42, who.analysis_hand
        assert len(who.analyses) == 4
        names = [a['player'] for a in who.analyses]
        assert names == ['Host', 'Alice', 'Bob', 'Carol'], names
        # Spot-check the actual text is routed intact
        assert 'thin' in who.analyses[0]['text']
        assert 'pot-control' in who.analyses[1]['text']

    # Clean shutdown
    for key, (client, _) in results.items():
        try:
            client.disconnect_from_server()
        except Exception:
            pass
    wait(200)
    server.stop()
    wait(100)

    # 10) Raise semantics: check the RaiseDialog returns call+raise. We do
    # this with a real QWidget parent-less instance (no show, no exec).
    from pokerIQ import RaiseDialog
    # to_call=$2, user picks raise of $6 → total commitment should be $8
    rd = RaiseDialog(to_call=2, min_raise_above=2, max_raise_above=20,
                     pot=10, parent=None, bb_amount=2)
    rd.set_value(6)  # raise $6 above the call
    assert rd.get_raise_above() == 6, rd.get_raise_above()
    assert rd.get_value() == 8, rd.get_value()

    print("[11] RaiseDialog: to_call=2, raise=6 → get_value()=8 ✓")

    print("\n=== All pokerIQ multi-client assertions passed ===")


if __name__ == "__main__":
    main()
