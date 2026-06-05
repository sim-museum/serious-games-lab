"""Plan 3 — Q-NET TCP proxy/sniffer for protocol RE.

Sits between two Q-Plus instances (server + client) and logs every
byte sent in either direction with timestamps. The captured traffic
is the raw input for decoding Q-Plus's proprietary bridge-server
wire protocol.

Setup (manual):
  1. Start Q-Plus instance A as server. In its Network dialog,
     pick a port (call it SERVER_PORT, e.g. 5555).
  2. Run this proxy:
       python3 tools/qnet_proxy.py \\
           --listen-port 5556 \\
           --forward-host 127.0.0.1 \\
           --forward-port 5555 \\
           --log tools/runs/qnet_session.log
  3. Start Q-Plus instance B as client. Connect to host=127.0.0.1
     port=5556 (the proxy's listen port).
  4. Both instances play a deal; the proxy logs all traffic.

Output format: one line per packet with direction (C2S / S2C),
millisecond timestamp, byte length, and a hex+ASCII dump. Easy
to feed into a downstream analyzer that recognises commands
(DDE_CMD_* etc. observed in the Q-NET.EXE strings).
"""

import argparse
import socket
import sys
import threading
import time
from pathlib import Path

LOG_LOCK = threading.Lock()


def _hex_ascii(data: bytes, width: int = 16) -> str:
    """Hex+ASCII dump for binary protocol bytes."""
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {off:04x}  {hexs:<{width*3}}  {asci}")
    return "\n".join(lines)


def _log(fh, direction: str, data: bytes, t0: float) -> None:
    with LOG_LOCK:
        ms = int((time.time() - t0) * 1000)
        fh.write(f"[{ms:>8} ms] {direction}  len={len(data)}\n")
        fh.write(_hex_ascii(data) + "\n\n")
        fh.flush()


def _pipe(name: str, src: socket.socket, dst: socket.socket,
          direction: str, fh, t0: float) -> None:
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            _log(fh, direction, data, t0)
            dst.sendall(data)
    except (OSError, BrokenPipeError):
        pass
    finally:
        try:
            src.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            dst.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _serve(listen_port: int, forward_host: str, forward_port: int,
            log_path: Path) -> int:
    t0 = time.time()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(log_path, "w")
    fh.write(f"# Q-NET proxy started\n")
    fh.write(f"# listen=:{listen_port}  "
              f"forward={forward_host}:{forward_port}\n")
    fh.write(f"# format: [ms_elapsed] DIR  len=N\\n hex+ascii dump\n\n")
    fh.flush()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", listen_port))
    srv.listen(1)
    print(f"[qnet_proxy] listening on :{listen_port} "
          f"→ {forward_host}:{forward_port}  "
          f"(accepting reconnects until Ctrl-C)", file=sys.stderr)
    print(f"[qnet_proxy] log → {log_path}", file=sys.stderr)
    try:
        session = 0
        while True:
            try:
                client_sock, addr = srv.accept()
            except KeyboardInterrupt:
                break
            session += 1
            fh.write(f"\n# --- session {session} from {addr} at "
                      f"{int((time.time()-t0)*1000)} ms ---\n\n")
            fh.flush()
            print(f"[qnet_proxy] session {session}: "
                  f"client connected from {addr}",
                  file=sys.stderr)
            try:
                upstream = socket.socket(socket.AF_INET,
                                           socket.SOCK_STREAM)
                upstream.connect((forward_host, forward_port))
            except OSError as e:
                print(f"[qnet_proxy] upstream connect failed: {e} "
                      f"(is the server running on "
                      f"{forward_host}:{forward_port}?)",
                      file=sys.stderr)
                fh.write(f"# upstream connect failed: {e}\n")
                fh.flush()
                client_sock.close()
                continue
            print(f"[qnet_proxy] upstream connected", file=sys.stderr)
            t_c2s = threading.Thread(target=_pipe, args=(
                "c2s", client_sock, upstream, "C2S", fh, t0))
            t_s2c = threading.Thread(target=_pipe, args=(
                "s2c", upstream, client_sock, "S2C", fh, t0))
            t_c2s.start()
            t_s2c.start()
            t_c2s.join()
            t_s2c.join()
            print(f"[qnet_proxy] session {session} ended; "
                  f"listening for reconnect", file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        fh.write(f"\n# proxy stopped at "
                  f"{int((time.time()-t0)*1000)} ms\n")
        fh.close()
        srv.close()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Q-NET TCP proxy/sniffer for protocol RE")
    p.add_argument("--listen-port", type=int, required=True,
                   help="port we accept the Q-Plus client on")
    p.add_argument("--forward-host", default="127.0.0.1",
                   help="Q-Plus server host (default 127.0.0.1)")
    p.add_argument("--forward-port", type=int, required=True,
                   help="port the Q-Plus server is listening on")
    p.add_argument("--log", type=Path, required=True,
                   help="path to write the capture log")
    args = p.parse_args(argv)
    return _serve(args.listen_port, args.forward_host,
                   args.forward_port, args.log)


if __name__ == "__main__":
    sys.exit(main())
