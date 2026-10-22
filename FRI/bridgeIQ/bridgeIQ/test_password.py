"""Backlog 55: the table password (blank host = open table), as in the other Serious Games Week games.

    python3 test_password.py      (from FRI/bridgeIQ/bridgeIQ)

Host password / guest password -> joined?  ""/"x" yes, "abc"/"abc" yes, "abc"/"x" no ("Wrong password ..."),
"abc"/"" no ("... needs a password").
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtCore import QCoreApplication  # noqa: E402
from backend.models import Seat  # noqa: E402
from network.server import BridgeServer  # noqa: E402
from network.client import BridgeClient  # noqa: E402
from test_multi_client import wait  # noqa: E402


def trial(port, host_pw, guest_pw):
    server = BridgeServer(password=host_pw)
    assert server.start(port=port, name="Host", seat=Seat.SOUTH), "server failed to start"
    wait(150)
    got = {}
    client = BridgeClient(password=guest_pw)
    client.connected.connect(lambda *a: got.setdefault("ok", True))
    client.connection_failed.connect(lambda r: got.setdefault("why", r))
    client.connect_to_server("127.0.0.1", port, "Alice", requested_seat="N")
    wait(500)
    try:
        client.disconnect_from_server()
    except Exception:
        pass
    server.stop()
    wait(100)
    return bool(got.get("ok")) and "why" not in got, got.get("why", "")


def main():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)  # noqa: F841
    fails = 0
    for port, hp, gp, want, text in ((47781, "", "x", True, ""), (47782, "abc", "abc", True, ""),
                                     (47783, "abc", "x", False, "Wrong password"),
                                     (47784, "abc", "", False, "needs a password")):
        joined, why = trial(port, hp, gp)
        ok = joined == want and (text in why if text else True)
        fails += not ok
        print(f"  host {hp!r:6} guest {gp!r:6} -> {'joined' if joined else 'refused'} {why!r:40} {'PASS' if ok else 'FAIL'}")
    print("ALL PASS" if fails == 0 else f"{fails} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
