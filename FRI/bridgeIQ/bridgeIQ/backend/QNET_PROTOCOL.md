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

## Practical workflow for capturing on this machine

A helper script `tools/qplus_dual_instance.sh` (local-only,
gitignored) sets up two Q-Plus instances + the byte-logging proxy.
Run in three terminals:

```bash
# Terminal 1
tools/qplus_dual_instance.sh setup   # one-time: clone Wine prefix to WP_client/
tools/qplus_dual_instance.sh proxy   # byte sniffer on :5556 → :5555

# Terminal 2: Q-Plus instance A (server)
tools/qplus_dual_instance.sh server
#   in UI: Configuration → Players → one seat to Extern
#          Network → Start bridge server on this PC → port 5555 → Start

# Terminal 3: Q-Plus instance B (client)
tools/qplus_dual_instance.sh client
#   in UI: Network → Connect to local bridge server
#          Address 127.0.0.1, Port 5556 (the PROXY, not the server)
#          Connect → Join game
```

Play one complete deal. Every byte gets timestamped + hex+ASCII
dumped into `tools/runs/qnet_session.log`.

The `proxy` subcommand is idempotent — if port 5556 is already
held by a previous proxy instance, it kills the holder (SIGTERM,
then SIGKILL after 1s if needed) and archives the existing log
to `tools/runs/qnet_session_<timestamp>.log` before opening a
fresh log. Lets you re-run `tools/qplus_dual_instance.sh proxy`
without manual port cleanup or log loss.

`tools/biq_qnet_client.py` is also idempotent: at startup it
greps for any other `biq_qnet_client.py` Python processes and
kills them (SIGTERM, then SIGKILL after 0.7s). Prevents a
stuck previous biq run from holding the seat at Q-Plus (which
would cause `player_refused` or duplicate-client confusion on
the next run).

If the in-line proxy's latency upsets Q-Plus's handshake timing,
fall back to passive packet capture:
```bash
tools/qplus_dual_instance.sh capture-with-tcpdump
```
Then have Q-Plus B connect DIRECTLY to port 5555 (not the proxy).
Resulting `tools/runs/qnet.pcap` is readable by Wireshark.

Wine prefix layout:
- Server: `$FRI_ROOT/WP/` (existing, original)
- Client: `$FRI_ROOT/WP_client/` (clone, made by `setup`)

Each Q-Plus instance has its own prefix because they share config
files in the install dir.

**Important**: Q-Plus needs a specific Wine runner — default Ubuntu
wine (9.x) lacks the glyphs for the bridge suit characters, so
cards render with empty boxes. The helper picks
`$HOME/.local/share/lutris/runners/wine/lutris-6.21-6-x86_64/bin/wine`
by default (wine-TkG Staging 6.21 from Lutris), matching what
`bridgeIQ/config/wine_runners.csv` configures for the corpus
tools. Override via the `WINE_BIN` env var if your runner lives
elsewhere.

## Decoded protocol (from one captured deal, 2026-05-30)

**Format**: plain text, `\n`-terminated lines. No length headers,
no binary framing. Each line:
```
"<command>" [arg1] [arg2] [arg3] ...
```
where `<command>` is quoted and each arg is in square brackets.
Arg contents are free text (may include spaces).

### Handshake (one-time at connect)

| Cmd | Dir | Args | Notes |
|---|---|---|---|
| `request_player_info` | C→S | `[seat]` | client probes each of 4 seats (north/east/south/west, lowercase) |
| `set_player_info` | S→C | `[Display] [Internal] [Type] [Status]` | one per seat. Type ∈ {Human, Computer, Extern}; Status ∈ {local, not_connected, connected} |
| `join_game` | C→S | `[Display] [Internal]` | client claims a seat; Internal is the client's chosen name |
| `player_accepted` | S→C | — | server ack of the join |
| `request_config` | C→S | — | client asks for game settings |
| `set_config` | S→C | `[k=v;k=v;...]` | semicolon-delimited k=v: conventions, lead/signal codes, etc. |

### Per-deal vocabulary

| Cmd | Dir | Args | Notes |
|---|---|---|---|
| `new_deal_pbn` | S→C | `[tag1] [scoring] [tag2] [<dealer> <vul> <starter>:<hand> <hand> <hand> <hand>]` | PBN deal; **dealer is in arg[3]**, NOT arg[0]; hands listed S/H/D/C order within each, in seat order from `<starter>` |
| `start_bidding` | S→C | `[-]` | auction begins |
| `bid` | both | `[Seat] [bid]` | bid format: `1nt`, `2c ` (trailing space for suit bids), ` p ` for pass, ` x ` for double, `xx ` for redouble |
| `begin_play` | both | — | each seat acks ready to play (we observed 3 from server, 1 from client) |
| `card` | both | `[Seat] [card]` | card = lowercase suit + uppercase rank, e.g. `sA`, `hQ`, `d4` |
| `report_score` | S→C | `[scoreline]` | scoreline contains DI/DD/... fields |
| `server_stopped` | S→C | — | clean disconnect |

### Direction rules

- **Server is authoritative.** Every bid/card is broadcast by the
  server to all clients including the one that sent it.
- **Client only SENDS bids/cards for its claimed seat.** The
  client must echo the server's `begin_play` once.
- **Client must wait for `start_bidding` before sending bids**, and
  for `begin_play` before sending cards.

### Vulnerability tokens

`None`, `NS`, `EW`, `All` (or `Both`). `None` is the default.

### Bid format quirks

- Pass = `[ p ]` with spaces. Acceptable to send `[p]` too based on
  parser leniency; safer to match server's whitespace.
- Suit bids: lowercase suit letter (`s`/`h`/`d`/`c`/`nt`) preceded
  by level digit. Trailing space for non-NT bids (e.g. `[2c ]`).

## biq client implementation

`tools/biq_qnet_client.py` (local-only per the tools/-gitignore
policy) implements the full protocol:

```bash
# Connect biq to an existing Q-Plus server as East:
python3 tools/biq_qnet_client.py \\
    --host 127.0.0.1 --port 5555 \\
    --seat E --system SAYC

# Connect via the proxy to capture biq-vs-Q-Plus traffic in parallel:
python3 tools/biq_qnet_client.py --port 5556 --seat E --system SAYC
```

### What the client does

1. TCP connects to host:port.
2. Sends the 4-step handshake (request_player_info ×4, join_game,
   request_config). Waits for each ack.
3. On `new_deal_pbn`: parses dealer + vul + 4 hands, builds a
   `BoardState`, prints biq's hand for the claimed seat.
4. On `start_bidding`: if biq is the dealer, calls
   `backend.native_bidder.decide_bid()` and sends the result.
5. On `bid`: appends to auction; if next bidder is biq, sends
   biq's bid. Detects auction end and derives the contract.
6. On `begin_play`: sends one `begin_play` ack. If biq is the
   opening leader (LHO of declarer), sends the first card.
7. On `card`: removes the card from the played seat's hand,
   accumulates the trick. On 4 cards, computes the winner. If
   biq is next to play, calls `BridgeEngine.get_mc_card_play()`
   and sends the result.
8. On `report_score`: logs the result.
9. On `server_stopped`: exits cleanly.

### Fallbacks

- Bidder exception → biq sends pass.
- Cardplay exception or MC failure → biq plays the lowest legal
  card in the led suit (or any legal card if void).
- Q-Plus's recorded card not in hand on replay → falls back to
  lowest legal card (same logic).

## Clean-measurement workflow (Q-Plus bots vs biq, no human)

After the Plan 3 milestone, the right way to gather statistics is
to take the user out of the loop entirely: Q-Plus's Computer
plays N/S/W, biq plays its claimed seat (E), and a small clicker
script keeps hitting "Next deal" on the server window.

Three terminals + one click-loop:

```bash
# Terminal 1 — Q-Plus server (configure N/S/W=Computer, E=Extern)
tools/qplus_dual_instance.sh server
# Then in Q-Plus: Configuration → Players → S=Computer, E=Extern,
# N=Computer, W=Computer → OK
# Then: Network → Start bridge server → port 5555 → Start

# Terminal 2 — proxy for protocol logging (optional)
tools/qplus_dual_instance.sh proxy

# Terminal 3 — biq client
python3 tools/biq_qnet_client.py --port 5556 --seat E --system SAYC

# Terminal 4 — auto-Next-Deal loop (after playing deal 1 manually)
python3 tools/qplus_network_autoplay.py --deals 50
# (calibrates Next-deal button position once, then loops)
```

`tools/qplus_network_autoplay.py` is the stripped-down companion
to `qplus_autoplay.py` — only one button to click in network
mode because the Computer seats and biq autonomously play through
each deal once started.

After the session, aggregate IMP totals from the proxy log:

```bash
python3 tools/qnet_score_aggregate.py --our-seat E
# default --log = tools/runs/qnet_session.log
```

Output:
- Total IMPs for biq + opp + net
- Per-deal table: deal id, dealer/vul, NS raw score, biq IMP, opp IMP
- Win/tie/loss counts

The aggregator parses `report_score` lines from the proxy hex
dump. The relevant payload fields per deal are:
- `DI "<label>"` — deal ID
- `RE <ns_actual> <ew_par>` — actual NS score + EW par reference
- `IM <ns_imp> <ew_imp>` — IMPs (one of the two is 0; the other
  is the absolute swing for whichever side benefited from
  comparing actual to par)

`our-seat ∈ {N,E,S,W}` tells the aggregator which side biq
plays (so it knows whether biq's IMP is the NS or EW column).

Open question still pending: does Q-Plus's networked mode actually
accept S=Computer at the server while biq holds E=Extern? Reports
from interactive testing on 2026-05-30 suggest YES — biq has played
multiple deals against three Q-Plus bots — but document confirmation
needed if/when found in Q-Plus help docs.

## First live biq vs Q-Plus deal (2026-05-30)

Plan 3 end-to-end smoke test successful. Setup:
- Server (`WP/`): N=Computer, E=Extern, S=Human (user), W=Computer
- biq client (`tools/biq_qnet_client.py`): joined East as `biq2`
  via the proxy on :5556

biq's protocol handling:
- Handshake (request_player_info ×4 / join_game / request_config /
  set_config) succeeded.
- A bug in the first run had biq's auction tracker out of sync
  because Q-Plus does NOT echo the client's own bid back —
  fixed by manually appending the sent bid + advancing the
  bidder pointer in `_send_my_bid` and `_send_my_card`.
- Stale-Extern issue if biq disconnects mid-session — workaround
  is to restart Q-Plus's bridge-server (Stop → Start).

Deal #42 (dealer N, vul E/W):
- Full 14-bid auction tracked: 1H-P-1S-P-1NT-P-2C-P-2S-P-3S-P-4S-P-P-P
- Contract: 4S by South.
- biq played all 13 East cards via the MC+DDS engine.
- Result: NS set 1 (NS made 9, needed 10). NS −50.
- Q-Plus's DD analysis: NS makes 10 (par +620 for NS).
- The deal "beat" Q-Plus's declarer-side DD prediction by 11 IMP
  to E/W.

CAVEAT — not yet a clean biq vs Q-Plus measurement:
- The user was playing South in this deal, so the contract was
  defeated by `biq + W-bot + user`, not by `biq + 3 Q-Plus bots`.
- For an honest measurement, Q-Plus must be configured to run
  ALL three non-biq seats as Computer (S=Computer, not Human),
  and the deal must be started without human input at the table.
- Open question: does Q-Plus's networked-play mode allow
  S=Computer at server while a client (biq) holds E=Extern? The
  standard 2-PLAYERS-B documentation describes two-humans-vs-each-
  other; the all-Computer-except-Extern configuration hasn't
  been verified end-to-end yet. Try it next.

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
