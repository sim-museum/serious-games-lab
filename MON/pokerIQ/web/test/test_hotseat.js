/* Hotseat (pass-and-play) test — drives the built HTML in jsdom, configures
 * multiple human seats, and verifies the privacy gate + per-seat reveal +
 * turn handoff. Run: node test/test_hotseat.js */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const ctrl = window.PIQ.ctrl, Bots = window.PokerBots;
ctrl.botDelayMs = 0; ctrl.pump();

// default = single-player, no gate
ok(ctrl.hotseat === false, 'default is single-player (no hotseat)');
ok(ctrl.passGate === false, 'no privacy gate in single-player');

// configure 3 humans + 3 bots
ctrl.setupPlayers([
  { name: 'Alice', style: 'human' },
  { name: 'Bob', style: 'human' },
  { name: 'Cara', style: 'human' },
  { name: 'Tight Tim', style: 'tight' },
  { name: 'Loose Bruce', style: 'loose' },
  { name: 'Aggro Angela', style: 'aggressive' },
]);
ctrl.botDelayMs = 0;
ok(ctrl.hotseat === true, 'hotseat enabled with >1 human');
ok(ctrl.humanSeats.size === 3, `3 human seats (${ctrl.humanSeats.size})`);
ok(ctrl.game.players[0].name === 'Alice' && ctrl.game.players[3].name === 'Tight Tim', 'lineup applied (humans + bots)');

// drive a few hands; assert the gate + reveal invariants the whole way
let armCount = 0, actCount = 0, handsDone = 0, guard = 0;
let everGated = false, revealLeakSeen = false;
while (handsDone < 3 && guard++ < 2000) {
  const s = ctrl.snapshot();
  if (s.handResult) { // hand over → next
    // at showdown all active hole cards revealed (shared)
    handsDone++;
    if (handsDone < 3) ctrl.newHand();
    continue;
  }
  if (s.passGate) {
    everGated = true;
    // INVARIANT: while gated, NO hole cards are revealed
    if (s.players.some(p => p.reveal && p.hand.length)) revealLeakSeen = true;
    ctrl.arm(); armCount++;
    // after arming, exactly the active human seat is revealed; others hidden
    const s2 = ctrl.snapshot();
    const revealed = s2.players.filter(p => p.reveal && p.hand.length);
    ok(revealed.length === 1 && revealed[0].seat === ctrl.game.toAct, 'only the armed seat is revealed');
    // and that seat is a human seat
    if (!ctrl.humanSeats.has(revealed[0].seat)) ok(false, 'revealed seat is human');
    continue;
  }
  if (s.awaitingHero && s.legal) {
    const seat = ctrl.game.toAct;
    const [a, amt] = Bots.decide(ctrl.game, ctrl.game.players[seat]);
    ctrl.act(a, amt); actCount++;
    continue;
  }
  // bots acting (no gate, no human) — pump
  ctrl.pump();
}

ok(everGated, 'privacy gate appeared before human turns');
ok(!revealLeakSeen, 'no hole cards leaked while gated');
ok(armCount > 0 && actCount > 0, `players armed (${armCount}) and acted (${actCount})`);
ok(handsDone === 3, `played ${handsDone} hotseat hands to completion`);

// the gate DOM renders with the active player's name + arm button
ctrl.newHand();
const sg = ctrl.snapshot();
if (sg.passGate) {
  ctrl.render();
  ok(d.getElementById('piq-gate').style.display === 'flex', 'gate overlay shown in DOM');
  ok(/Pass the device to/.test(d.getElementById('piq-gate').textContent), 'gate prompt text');
  ok(d.getElementById('piq-arm') != null, 'arm button present');
  // clicking arm reveals (gate hides)
  d.getElementById('piq-arm').click();
  ok(ctrl.armed === true, 'arm button armed the player');
}

// back to single-player removes the gate
ctrl.setupPlayers([
  { name: 'Hero (You)', style: 'human' }, { name: 'Tight Tim', style: 'tight' },
  { name: 'Loose Bruce', style: 'loose' }, { name: 'Aggro Angela', style: 'aggressive' },
  { name: 'Sharkey Steve', style: 'shark' }, { name: 'Fluid Fiona', style: 'tom' },
]);
ok(ctrl.hotseat === false, 'single human → hotseat off');
ok(ctrl.passGate === false, 'no gate back in single-player');

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
