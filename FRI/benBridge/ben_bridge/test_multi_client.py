#!/usr/bin/env python3
"""Integration test: one host + multiple guests, each picking a seat.

Drives BridgeServer and BridgeClient directly (no GUI) inside a single
Qt event loop so we can assert accept/reject behavior deterministically.

Run with:  python3 test_multi_client.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QCoreApplication, QTimer, QEventLoop

from ben_backend.models import Seat
from network.server import BridgeServer
from network.client import BridgeClient


class Results:
    def __init__(self):
        self.accepted = []          # list of (name, my_seat, partner_seat, role)
        self.rejected = []          # list of (name, reason)
        self.clients = []           # keep client refs alive


def wait(ms: int):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def attempt_connect(name: str, seat_char: str, port: int, results: Results):
    """Start a guest and wait briefly for acceptance/rejection."""
    client = BridgeClient()
    results.clients.append(client)

    def on_connected(server_name, my_seat, partner_seat, role):
        results.accepted.append((name, my_seat, partner_seat, role))
        print(f"  [{name}] CONNECTED seat={my_seat} partner={partner_seat} role={role}")

    def on_failed(reason):
        results.rejected.append((name, reason))
        print(f"  [{name}] REJECTED: {reason}")

    client.connected.connect(on_connected)
    client.connection_failed.connect(on_failed)
    client.connect_to_server("127.0.0.1", port, name, requested_seat=seat_char)

    # Wait for the handshake to complete (accept or reject).
    wait(800)
    return client


def main():
    app = QCoreApplication(sys.argv)
    port = 47777

    print(f"Starting host server on port {port}, seat=S")
    server = BridgeServer()

    def on_client_connected(name, role):
        print(f"  (server) guest '{name}' joined as {role}")

    def on_client_disconnected():
        print(f"  (server) a guest disconnected")

    server.client_connected.connect(on_client_connected)
    server.client_disconnected.connect(on_client_disconnected)

    assert server.start(port=port, name="Host", seat=Seat.SOUTH), "server failed to start"
    wait(150)  # let server enter listening state

    results = Results()

    # 1) Guest A asks for N — free, expected to succeed
    print("\nGuest A wants N")
    attempt_connect("A", "N", port, results)
    assert len(results.accepted) == 1, "A should be accepted"
    assert results.accepted[0][1] == "N"
    # Host (S) + guest (N) occupied; E, W free
    free = sorted(s.to_char() for s in server.free_seats())
    assert free == ["E", "W"], f"free seats after A: {free}"
    assert server.num_clients == 1

    # 2) Guest B asks for N again — should be rejected with free=[E,W]
    print("\nGuest B wants N (already taken)")
    attempt_connect("B", "N", port, results)
    assert len(results.rejected) == 1, "B should be rejected"
    b_reason = results.rejected[0][1]
    assert "taken" in b_reason.lower(), f"expected 'taken' in: {b_reason}"
    assert "E" in b_reason and "W" in b_reason, f"free seats missing from reject: {b_reason}"
    assert server.num_clients == 1, "B's rejected socket must not count"

    # 3) Guest C asks for E — free
    print("\nGuest C wants E")
    attempt_connect("C", "E", port, results)
    assert len(results.accepted) == 2, "C should be accepted"
    assert results.accepted[1][1] == "E"
    assert server.num_clients == 2

    # 4) Guest D asks for W — free, table now has host + 3 guests
    print("\nGuest D wants W")
    attempt_connect("D", "W", port, results)
    assert len(results.accepted) == 3, "D should be accepted"
    assert results.accepted[2][1] == "W"
    assert server.num_clients == 3

    # 5) Guest E asks for any seat — table is full (host + 3 guests)
    print("\nGuest E wants N (table full)")
    attempt_connect("E", "N", port, results)
    assert len(results.rejected) == 2, "E should be rejected"
    e_reason = results.rejected[1][1]
    assert "full" in e_reason.lower(), f"expected 'full' in: {e_reason}"

    print("\nOccupied seats on server:",
          sorted(s.to_char() for s in server.occupied_seats()))
    print("Free seats on server:    ",
          sorted(s.to_char() for s in server.free_seats()))

    # Tear down
    for c in results.clients:
        c.disconnect_from_server()
    wait(200)
    server.stop()
    wait(100)

    print("\n=== All multi-client assertions passed ===")


if __name__ == "__main__":
    main()
