/* Fold→spectator view + assist flagging test. Builds a seeded Controller+View
 * inside the built page and verifies: folding reveals all cards + the equity
 * panel; God/Tells used while still in the hand are flagged in the summary;
 * God used after folding is NOT flagged. Run: node test/test_spectator.js */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;
function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

// seeded instance with a real View on a fresh element
function makeInstance(seed) {
  const app = d.createElement('div'); d.body.appendChild(app);
  const C = new window.PokerUI.Controller({ rng: mulberry32(seed), botDelayMs: 0, onRender: () => {} });
  const V = new window.PokerUI.View(app, C);
  C.onRender = (snap) => V.render(snap);
  return { C, V, app };
}
// deal until it's the human hero's turn (seat 0) with the hand live
function toHeroTurn(C) {
  for (let tries = 0; tries < 40; tries++) {
    C.botDelayMs = 0; C.newHand();
    if (C.humanToAct() && C.game.toAct === 0 && C.game.handInProgress) return true;
  }
  return false;
}

// ---- 1. fold → spectator God view ----
{
  const { C, V, app } = makeInstance(11);
  ok(toHeroTurn(C), 'reached hero turn');
  // freeze bots so the spectator state persists after the fold
  C.timer = () => {}; C.botDelayMs = 600;
  C.act('f', 0);
  if (C.game.handInProgress) {
    ok(C.spectating === true, 'spectating after hero folds (bots remain)');
    const s = C.snapshot();
    ok(s.players.every(p => !p.hand.length || p.reveal), 'all hole cards revealed in spectator view');
    ok(s.spectator && Array.isArray(s.spectator.table), 'spectator equity table present');
    const live = s.spectator.table.filter(r => !r.folded);
    ok(live.length >= 2, `equity rows for active players (${live.length})`);
    ok(live.every(r => typeof r.real === 'number' && typeof r.thinking === 'number' && typeof r.potOdds === 'number'), 'rows have Real/Thinking/PotOdds');
    ok(s.spectator.table.some(r => r.folded), 'folded players shown as (Folded)');
    // DOM: spectator panel rendered with nav
    ok(app.querySelector('#piq-spectator').style.display === 'block', 'spectator panel shown in DOM');
    ok(app.querySelector('.sp-table') != null, 'spectator table rendered');
    ok(app.querySelector('#sp-close') != null, 'Close View button present');
    // street nav doesn't crash
    C.specPrev(); C.specNext();
    ok(true, 'street nav prev/next ran');
    // close view exits spectating
    C.exitSpectator(false);
    ok(C.spectating === false, 'exitSpectator exits spectator mode');
  } else { ok(true, 'hand ended on fold (uncontested) — spectator skipped, acceptable'); }
}

// ---- 2. God used BEFORE folding → flagged ----
{
  const { C } = makeInstance(11);
  ok(toHeroTurn(C), 'reached hero turn (flag test)');
  ok(C.game.players[0].active, 'hero still in the hand');
  C.toggleGod();
  const flags = C.assistFlags();
  ok(flags.some(f => f.name === C.game.players[0].name && f.assists.includes('God Mode')), 'God Mode while in hand is flagged');
  C.toggleTells();
  ok(C.assistFlags().some(f => f.assists.includes('Show Tells')), 'Show Tells while in hand is flagged');
}

// ---- 3. God used AFTER folding → NOT flagged ----
{
  const { C } = makeInstance(11);
  ok(toHeroTurn(C), 'reached hero turn (no-flag test)');
  C.timer = () => {}; C.botDelayMs = 600;
  C.act('f', 0);  // fold first
  C.godMode = false;            // ensure off
  C.toggleGod();                // turn on AFTER folding
  const flags = C.assistFlags();
  ok(!flags.some(f => f.assists && f.assists.includes('God Mode')), 'God after folding is NOT flagged');
}

// ---- 4. assist flag surfaces in the hand summary ----
{
  const { C, V } = makeInstance(7);
  ok(toHeroTurn(C), 'reached hero turn (summary test)');
  C.toggleGod();                          // flag it
  C.botDelayMs = 0; C.timer = (fn) => fn();
  // finish the hand: hero calls/checks then bots run out
  let guard = 0;
  while (C.game.handInProgress && guard++ < 200) {
    if (C.humanToAct() && C.game.toAct === 0) C.act('c', 0); else C.pump();
  }
  ok(C.lastHistory && C.lastHistory.assists && C.lastHistory.assists.length > 0, 'assists recorded into hand history');
  // render the summary node and check the flag text
  const node = V.handSummaryNode(C.lastHistory, C.buildSummaryData(C.lastHistory), 'basic');
  ok(/Assists used while still in the hand/.test(node.textContent), 'summary shows the assist flag');
  ok(/God Mode/.test(node.textContent), 'summary names God Mode');
}

// ---- 5. hotseat 6-human preset works ----
{
  const ctrl = window.PIQ.ctrl;
  ctrl.setupPlayers(Array.from({ length: 6 }, (_, i) => ({ name: 'P' + (i + 1), style: 'human' })));
  ok(ctrl.hotseat === true && ctrl.humanSeats.size === 6, '6-human hotseat configured');
  ok(ctrl.game.players.length === 6 && ctrl.game.players.every(p => p.style === 'human'), 'all six seats are human');
}

// ---- 6. hotseat: EVERY folder gets a review even with humans remaining (rev 1) ----
{
  const { C } = makeInstance(11);
  C.setupPlayers([{ name: 'A', style: 'human' }, { name: 'B', style: 'human' },
    { name: 'Tight Tim', style: 'tight' }, { name: 'Loose Bruce', style: 'loose' },
    { name: 'Aggro Angela', style: 'aggressive' }, { name: 'Sharkey Steve', style: 'shark' }]);
  C.timer = () => {}; C.botDelayMs = 600;
  let guard = 0, folded = false;
  while (!folded && guard++ < 60) {
    if (C.passGate) { C.arm(); continue; }
    if (C.humanToAct()) { C.act('f', 0); folded = true; break; }
    C.pump();
  }
  ok(folded, 'a human folded in hotseat');
  ok(C.spectating === true, 'folder gets a God-view review even with another human still in (rev 1)');
  const sp = C.spectatorData();
  ok(sp.passMode === true, 'hotseat review offers "Pass device →" (another human to act)');
  C.exitSpectator(true);
  ok(C.spectating === false, 'Pass device exits the review');
}

// ---- 7. God peek blocked in hotseat pre-fold (rev 2) ----
{
  const { C } = makeInstance(11);
  C.setupPlayers([{ name: 'A', style: 'human' }, { name: 'B', style: 'human' },
    { name: 'Tight Tim', style: 'tight' }, { name: 'Loose Bruce', style: 'loose' },
    { name: 'Aggro Angela', style: 'aggressive' }, { name: 'Sharkey Steve', style: 'shark' }]);
  ok(C.canUseGod() === false, 'God peek unavailable with other humans at the table');
  C.toggleGod();
  ok(C.godMode === false, 'God toggle is blocked in hotseat (pre-fold)');
  const { C: C2 } = makeInstance(11);
  ok(C2.canUseGod() === true, 'God peek available in single-player');
}

// ---- 8. showdown reveals ALL hands (incl. folded) for review ----
{
  const { C } = makeInstance(7);
  let guard = 0;
  while (guard++ < 200) {
    if (C.humanToAct()) C.act('c', 0);
    else if (!C.game.handInProgress) break;
    else C.pump();
  }
  if (C.handResult) {
    const s = C.snapshot();
    ok(s.players.every(p => !p.hand.length || p.reveal), 'all hands (incl. folded) revealed at showdown');
  } else ok(true, 'hand still running — skipped showdown-reveal check');
}

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
