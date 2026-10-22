"""Backlog 55: the table password (blank host = open table), as in the other Serious Games Week games.

    QT_QPA_PLATFORM=offscreen python3 test_password.py      (from MON/pokerIQ)

Host password / client password -> joined?  ""/"x" yes, "abc"/"abc" yes, "abc"/"x" no ("Wrong password ..."),
"abc"/"" no ("... needs a password").
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication  # noqa: E402
from network.server import PokerServer  # noqa: E402
from network.client import PokerClient  # noqa: E402
from test_multi_client import Collector, wait  # noqa: E402


def trial(port, host_pw, client_pw):
    server = PokerServer(server_name="PwTable", num_seats=4, host_seat=0, host_name="Host", password=host_pw)
    assert server.start(port), "server failed to listen"
    wait(150)
    client = PokerClient(player_name="Alice", password=client_pw)
    col = Collector("Alice")
    col.attach(client)
    client.connect_to_server("127.0.0.1", port)
    wait(400)
    joined, why = col.connected and col.reject is None, (col.reject or ("", ""))[0]
    client.disconnect_from_server() if hasattr(client, "disconnect_from_server") else None
    server.stop()
    wait(100)
    return joined, why


def main():
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    fails = 0
    for port, hp, cp, want, text in ((47791, "", "x", True, ""), (47792, "abc", "abc", True, ""),
                                     (47793, "abc", "x", False, "Wrong password"),
                                     (47794, "abc", "", False, "needs a password")):
        joined, why = trial(port, hp, cp)
        ok = joined == want and (text in why if text else True)
        fails += not ok
        print(f"  host {hp!r:6} client {cp!r:6} -> {'joined' if joined else 'refused'} {why!r:40} {'PASS' if ok else 'FAIL'}")
    print("ALL PASS" if fails == 0 else f"{fails} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
