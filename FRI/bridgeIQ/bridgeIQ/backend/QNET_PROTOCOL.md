# Q-NET TCP Protocol — Reverse-Engineering Notes

Q-Plus Bridge 17.1 ships `Q-NET.EXE` for networked play. This
document collects everything learned so far about the wire
protocol; goal is to eventually let biq speak it directly and play
live against Q-Plus over the network.

## Architecture from binary inspection

```
QBRIDGE.EXE  ←DDE→  Q-NET.EXE  ←TCP→  Q-NET.EXE  ←DDE→  QBRIDGE.EXE
   (game)         (net bridge)      (net bridge)         (remote game)
```

- `QBRIDGE.EXE`: the bridge game (2.8 MB, Borland C++ 1995-built).
- `Q-NET.EXE`: networking module (84 KB), opened via DDE by the
  main game.

`Q-NET.EXE` depends on:
- `WSOCK32.dll`: Windows Sockets 1.1 (Berkeley sockets, TCP).
- `USER32.dll` `DdeNameService`: Dynamic Data Exchange — local IPC
  between Q-NET.EXE and QBRIDGE.EXE.
- `TAPI32.DLL`: Telephony API (legacy modem support; ignore).

## Commands seen in Q-NET.EXE strings

```
DDE_CMD_CONNECT [%s]
DDE_CMD_DIRECT_MESSAGE [%s]
DDE_CMD_DISCONNECT [%s]
DDE_CMD_NET_COMMAND [%s]
DDE_CMD_RESEND_MESSAGE [%s]
DDE_CMD_START_SERVER [%s]
DDE_CMD_STOP_SERVER [%s]
DDE_REQ_EXIT [%s]
DDE_REQ_STATE [%s]
GET_STATE
```

These are likely **DDE message names** used between Q-NET ↔
QBRIDGE locally. The TCP wire format between two Q-NET instances
is a separate layer — needs capture to identify.

## Error / status strings

```
"Q-plus Bridge networking module"
"cannot create comm socket"
"requested TCP/IP port not available"
"Local TCP/IP port %u"        ← runtime-logged after bind()
"SOCK : bind() error : %d"
"SOCKET : closesocket() failed (%x)"
"SOCK : net_socket_send_to_server() - not connected"
"client recv buffer overflow"
"server recv buffer overflow"
"network down" / "network reset" / "network unreachable"
"remote party disconnected"
"DDE invalid message format"
```

`net_socket_send_to_server` suggests a client→server send wrapper.
The "buffer overflow" string pair (client + server) hints the
protocol is framed (each side has a recv buffer to assemble frames).

## Operational notes from the manual (`2-PLAYERS-B.DOC`)

- Server PC: menu **Network → Start bridge server on this PC** → click **Start**.
- Client PC: menu **Network → Connect to local bridge server** → enter
  TCP/IP address (or hostname) → **Connect** → **Join game**.
- Windows Defender Firewall must allow inbound `Q-plus Net` on first run.
- The port is asked at runtime (no compile-time default visible
  in binary strings); both ends must agree.

## RE plan (the work to do)

1. **Capture a session.** Run two Q-Plus instances under Wine,
   plumb one through `tools/qnet_proxy.py`, play a deal end-to-end.
   See proxy header for the exact command. Output is a timestamped
   hex+ASCII dump of every TCP byte in both directions.

2. **Decode frames.** Most likely structure: a 2- or 4-byte length
   header followed by a payload. Look for repeating byte patterns
   at the start of bursts (probably the command type code, mirrors
   of the DDE_CMD_* enum).

3. **Identify message types.** Cross-reference observed frames
   against game events:
   - Server start, client connect → handshake messages.
   - Bid made by Computer / Human / Extern → an "auction bid" msg.
   - Card played → a "play card" msg.
   - Trick won → maybe explicit, or derivable from card+state.
   - Disconnect / end → DDE_REQ_EXIT-style.

4. **Build a biq client.** Once frames are decoded, biq implements
   a client that connects to a Q-Plus server, joins as one seat,
   reads bid/play messages from Q-Plus, and sends biq's bids/plays
   back. ~500 lines of pure-Python sockets+protocol code, no Wine.

## Files

- `tools/qnet_proxy.py`: TCP proxy/sniffer (ready).
- `backend/QNET_PROTOCOL.md`: this doc.

## Effort estimate

- Session capture + initial frame decode: ~half a day.
- Full command-set decode (auction + play + state queries): ~1-2 days.
- biq client implementation: ~1-2 days.

Total ≈ 3-5 days of focused RE work, much of it interactive (running
Q-Plus and watching what happens). Best done with the user driving
Q-Plus and biq engineering parsing the captures.

## Why this is worth it

Live biq-vs-Q-Plus play is a clean external benchmark — none of
the biq-vs-biq cancellation that makes our current cardplay-mode
metric useless for declarer improvements. Items 1, 2, 3, 5 from
`CARDPLAY_PLAN.md` can finally be measured honestly against an
external commercial engine.
