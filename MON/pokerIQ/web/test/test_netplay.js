/* Online multiplayer protocol test (no real WebRTC — in-memory LoopbackHub).
 * A host runs the authoritative engine; a guest joins, is seated, and plays a
 * full hand over the wire. Verifies seating, hole-card privacy, state mirroring,
 * remote actions, chip conservation, showdown reveal, and chat. Run: node test/test_netplay.js */
const PokerUI = require('../src/ui.js');
const PG = require('../src/game.js');
const Net = require('../src/netplay.js');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };
function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

// ---- host ----
const hostCtrl = new PokerUI.Controller({ rng: mulberry32(99), botDelayMs: 0, equityIters: 60, onRender: () => {} });
const hub = new Net.LoopbackHub();
const netHost = new Net.NetHost(hostCtrl, hub.hostTransport(), { hostName: 'Alice' });

// ---- guest ----
const guestCtrl = new PokerUI.Controller({ rng: mulberry32(1), botDelayMs: 0, follower: true, equityIters: 60, onRender: () => {} });
const guestT = hub.guestTransport();
const netGuest = new Net.NetGuest(guestCtrl, guestT, { name: 'Bob' });

// join happens in the NetGuest constructor; host seats between hands (no hand yet)
ok(guestCtrl.netGuest === netGuest && guestCtrl.follower, 'guest controller is a follower');
ok(netGuest.seated, 'guest got welcomed + seated');
const seat = guestCtrl.mySeat;
ok(seat >= 1, 'guest assigned a non-host seat (' + seat + ')');
ok(hostCtrl.remoteSeats.has(seat), 'host marks the seat remote');
ok(netHost.seats()[seat] === 'Bob', 'lobby shows the guest name');

// ---- play a full hand, guest checks/calls to showdown ----
function guestToAct() { const g = hostCtrl.game; return g.awaitingAction && g.toAct === seat && hostCtrl.remoteSeats.has(seat); }
hostCtrl.newHand();
let guard = 0, guestActed = 0;
while (hostCtrl.game.handInProgress && guard++ < 400) {
  if (guestToAct()) {
    // guest sees the request: its mirror knows its own 2 cards, board matches host
    ok(guestCtrl.game.players[seat].hand.length === 2, 'guest sees its own hole cards');
    const oppHidden = guestCtrl.game.players.every((p, i) => i === seat || hostCtrl.game.handInProgress === false || p.hand.length === 0);
    if (guestActed === 0) ok(oppHidden, 'opponents\' cards hidden from guest mid-hand');
    if (guestCtrl.game.board.length === hostCtrl.game.board.length) pass++; else { fail++; console.log('  FAIL: board mirrors host'); }
    // act via the follower path (View → ctrl.act → host)
    const L = hostCtrl.game.legalActions(seat);
    guestCtrl.act('c', 0);   // check or call
    guestActed++;
  } else {
    // not guest's turn — host should be driving bots; if it's the LOCAL host's
    // turn, act for them so the hand progresses
    const g = hostCtrl.game;
    if (g.awaitingAction && g.toAct === 0) { hostCtrl.act('c', 0); }
    else if (!g.awaitingAction && g.awaitingBot < 0) break;   // wedged (shouldn't happen)
    else break;
  }
}
ok(guestActed >= 1, 'guest acted at least once over the wire (' + guestActed + ')');
ok(!hostCtrl.game.handInProgress, 'hand completed');

// chip conservation on the host
const total = hostCtrl.game.players.reduce((a, p) => a + p.stack, 0);
ok(total === PG.STARTING_STACK * hostCtrl.game.players.length, 'chips conserved on host (' + total + ')');

// guest mirror stacks match host after the hand
const match = hostCtrl.game.players.every(p => guestCtrl.game.players[p.seat] && guestCtrl.game.players[p.seat].stack === p.stack);
ok(match, 'guest mirror stacks match host at hand end');

// showdown revealed all hands to the guest (it reached showdown by calling)
const reveal = guestCtrl.game.players.filter(p => p.active).every(p => p.hand.length === 2);
ok(reveal, 'guest sees all active hands at showdown');

// guest built a summary-able history
ok(guestCtrl.lastHistory && guestCtrl.lastHistory.holeCards.length >= 2, 'guest has a completed hand history');
const sd = guestCtrl.buildSummaryData(guestCtrl.lastHistory);
ok(sd && sd.panels.length >= 1, 'guest can build the hand summary');

// chat both ways
netHost.chat('Alice', 'hi Bob');
ok(netGuest.chatLog.some(m => m.text === 'hi Bob'), 'guest receives host chat');
netGuest.sendChat('hi Alice');
ok(netHost.chatLog.some(m => m.text === 'hi Alice'), 'host receives guest chat');

// disconnect turns the seat back into a bot
hub.dropGuest(guestT.id);
ok(!hostCtrl.remoteSeats.has(seat), 'seat reverts to a bot on disconnect');
ok(hostCtrl.game.players[seat].style !== 'human', 'disconnected seat is a bot');

console.log(fail ? `\n✗ ${fail} FAILED, ${pass} passed` : `\n✓ ALL PASS — ${pass} passed, 0 failed`);
process.exit(fail ? 1 : 0);
