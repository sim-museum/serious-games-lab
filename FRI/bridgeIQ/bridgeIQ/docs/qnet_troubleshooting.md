# Why biq E/W won't attach to the Q-Plus Q-NET server

biq E/W connects to Q-Plus over Q-NET as two TCP clients (one per seat,
`tools/biq_qnet_client.py --seat E/W`) to `127.0.0.1:5555`. The handshake is:

```
C→S  "request_player_info" [north] / [east] / [south] / [west]
S→C  "set_player_info" [...]            (×4, one per seat)
C→S  "join_game" [East] [biq]
S→C  "player_accepted"
C→S  "request_config"
S→C  "set_config" [k=v;...]
```

If the client connects (TCP succeeds, "Connected to server") but the seat never
becomes live, it is almost always **one of these three** — in order of how often
it's the culprit:

## 1. The Q-Plus server is running under the wrong wine (the usual cause)

The Q-NET server **must** run under **system wine‑9.0 (`/usr/bin/wine`)**, *not*
the TkG 6.21 runner biq uses elsewhere for suit glyphs.

Under TkG 6.21 on kernel 6.17+, `Q-NET.EXE` **accepts** the TCP connection but
**never reads it** (broken async socket-event delivery — the Win32 message loop
is never woken for `FD_READ`). The client's `request_player_info` bytes pile up
unread; no `set_player_info` ever comes back; the handshake stalls forever. This
is silent — the client looks "connected" but the seat stays unfilled.
`WINEESYNC/WINEFSYNC` do **not** fix it; only the wine version does.

**Fix:** launch the Q-Plus server with `WINE_BIN_SERVER=/usr/bin/wine`. The
control panel already does this (`tools/qplus_dual_instance.sh server`); if you
start Q-Plus by hand, use `/usr/bin/wine QBRIDGE.EXE`. (Suit glyphs won't render
under wine‑9.0 — irrelevant for the headless biq client.)
See `backend/QNET_PROTOCOL.md` and the project memory `qplus_qnet_wine_runner`.

## 2. The E/W seats aren't set to "Extern" in Q-Plus

A biq client can only take a seat Q-Plus has opened to the network. In Q-Plus's
player configuration each of **East and West must be `Extern`** (not `Local`
human and not `Computer`). If they're `Computer`, Q-Plus plays them itself and
rejects the join.

## 3. A stale "Extern" seat from a previous session

If biq disconnected mid-session, Q-Plus holds the seat as a *stale Extern* and a
new client can't re-take it. Restart Q-Plus's bridge server (**Stop → Start**),
or clear everything with **Extras → Kill all wine processes** (added to biq) /
the control panel's *Kill wine* button — both run `wineserver -k` + `pkill` to
free the `:5555` socket. Then relaunch the server (under `/usr/bin/wine`) and
reconnect.

## Quick checklist
1. `pgrep QBRIDGE` and `ss -tln | grep 5555` — is the server up and listening?
2. Server launched with `/usr/bin/wine` (wine‑9.0), not TkG? ← most common fix
3. East and West both `Extern` in Q-Plus?
4. No stale client/socket? If unsure: **Extras → Kill all wine processes**, then
   restart the server and reconnect.
5. Read the biq client log (`--log`) for the exact step it stalls on
   (no `set_player_info` → cause #1; no `player_accepted` → cause #2/#3).
