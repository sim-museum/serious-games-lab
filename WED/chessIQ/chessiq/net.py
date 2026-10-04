"""chessIQ two-player network games over TCP (Qt sockets, one JSON object per line).

The host listens, picks the colours and starts each game; the guest connects. Both screens run the same rules
engine, and every move travels as SAN with its ply number, so each side checks the other's move is legal at that
point in the game -- a mismatch ends the connection instead of letting two boards silently diverge.

  guest -> host   {"t":"hello", "name":..., "version":...}
  host  -> guest  {"t":"start", "name":..., "you":"w"|"b"}            (also each later "new game")
  either way      {"t":"move", "ply":n, "san":"Nf3"}
                  {"t":"draw_offer"} {"t":"draw_accept"} {"t":"draw_decline"} {"t":"resign"}
                  {"t":"chat", "text":...}  {"t":"bye"}
"""
import json

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

DEFAULT_PORT = 47810
PROTOCOL = 1


class Link(QObject):
    """One side of a network game. Signals carry the peer's messages to the UI."""
    connected = pyqtSignal(str)             # peer's name (host: a guest arrived; guest: the host answered)
    started = pyqtSignal(str)               # a game starts; our colour
    moved = pyqtSignal(int, str)            # ply, SAN
    draw_offered = pyqtSignal()
    draw_answered = pyqtSignal(bool)
    resigned = pyqtSignal()
    chat = pyqtSignal(str)
    closed = pyqtSignal(str)                # why

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.peer_name = ""
        self.server = None
        self.sock = None
        self.buf = b""
        self.is_host = False
        self.port = 0

    # ---- host ----
    def host(self, port=DEFAULT_PORT):
        self.is_host = True
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.SpecialAddress.Any, port):
            return False
        self.port = self.server.serverPort()
        self.server.newConnection.connect(self._accept)
        return True

    def _accept(self):
        s = self.server.nextPendingConnection()
        if self.sock is not None:            # a two-player game: one guest at a time
            s.write(b'{"t":"bye","why":"this table is full"}\n')
            s.disconnectFromHost()
            return
        self._attach(s)

    # ---- guest ----
    def join(self, host, port=DEFAULT_PORT):
        self._attach(QTcpSocket(self))
        self.sock.connected.connect(lambda: self.send(t="hello", name=self.name, version=PROTOCOL))
        self.sock.connectToHost(host, port)

    # ---- both ----
    def _attach(self, s):
        self.sock, self.buf = s, b""
        s.readyRead.connect(self._read)
        s.disconnected.connect(self._gone)
        s.errorOccurred.connect(lambda _e: self._gone(s.errorString()))

    def _gone(self, why="the other player left"):
        if self.sock is None:
            return
        self.sock.deleteLater()
        self.sock = None
        self.closed.emit(why)

    def send(self, **msg):
        if self.sock is not None:
            self.sock.write((json.dumps(msg) + "\n").encode())

    def start_game(self, guest_colour):
        """Host only: a new game; the guest plays guest_colour."""
        self.send(t="start", name=self.name, you=guest_colour)

    def close(self):
        self.send(t="bye")
        if self.sock is not None:
            self.sock.flush()
            self.sock.disconnectFromHost()
        if self.server is not None:
            self.server.close()

    def _read(self):
        self.buf += bytes(self.sock.readAll())
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self._dispatch(msg)
            if self.sock is None:
                return

    def _dispatch(self, msg):
        t = msg.get("t")
        if t == "hello" and self.is_host:
            self.peer_name = str(msg.get("name", "Guest"))[:24]
            self.connected.emit(self.peer_name)
        elif t == "start" and not self.is_host:
            self.peer_name = str(msg.get("name", "Host"))[:24]
            self.connected.emit(self.peer_name)
            self.started.emit("b" if msg.get("you") == "b" else "w")
        elif t == "move":
            self.moved.emit(int(msg.get("ply", -1)), str(msg.get("san", "")))
        elif t == "draw_offer":
            self.draw_offered.emit()
        elif t in ("draw_accept", "draw_decline"):
            self.draw_answered.emit(t == "draw_accept")
        elif t == "resign":
            self.resigned.emit()
        elif t == "chat":
            self.chat.emit(str(msg.get("text", ""))[:300])
        elif t == "bye":
            self._gone(msg.get("why") or "%s left" % (self.peer_name or "the other player"))
