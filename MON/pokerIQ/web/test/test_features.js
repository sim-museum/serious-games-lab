/* Tests for the new features: per-hand history, reveal-after-fold, hand
 * summary modal. Drives the real built HTML in jsdom. Run: node test/test_features.js */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const ctrl = window.PIQ.ctrl, view = window.PIQ.view;
ctrl.botDelayMs = 0; ctrl.pump();

// 1) history is captured during a hand
ok(ctrl.history != null, 'history initialised on hand start');
ok(ctrl.history.streets[0].name === 'Preflop', 'first street is Preflop');
const blindActs = ctrl.history.streets[0].actions.filter(a => a.action === 'post');
ok(blindActs.length === 2, `two blind posts recorded (${blindActs.length})`);
ok(blindActs[0].amount > 0, 'blind post has amount');

// 2) reveal-after-fold: fold the hero, villains should reveal
// drive to hero turn then fold
let guard = 0;
while (ctrl.game.handInProgress && !(ctrl.game.awaitingAction && ctrl.game.toAct === 0) && guard++ < 50) ctrl.pump();
if (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
  ctrl.act('f', 0);
  const snap = ctrl.snapshot();
  if (ctrl.game.handInProgress) {
    ok(snap.heroFolded === true, 'heroFolded flag set after fold');
    ok(snap.revealVillains === true, 'villains revealed after fold');
    // a non-hero active seat should now show face-up cards (no .back)
    const villainSeat = [...d.querySelectorAll('.seat')].find(s => !s.classList.contains('hero') && !s.classList.contains('folded'));
    ok(villainSeat && villainSeat.querySelectorAll('.card.back').length === 0, 'villain cards face-up after hero fold');
  } else {
    ok(true, 'hand ended immediately after fold (everyone else folded too) — acceptable');
  }
} else {
  ok(true, 'hero had no decision this hand — skipping fold-reveal check');
}

// 3) play a hand to completion, then the summary modal builds with streets + table
ctrl.specPaused = false;   // if block 2 left a paused spectator, let it run out
guard = 0;
while (guard++ < 300) {
  if (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
    // call/check to reach showdown when possible
    const legal = ctrl.game.legalActions(0);
    ctrl.act('c', 0);
  } else if (!ctrl.game.handInProgress) break;
  else ctrl.pump();
}
ok(ctrl.lastHistory != null, 'lastHistory recorded at hand end');
ok(ctrl.lastHistory.result != null, 'history has result attached');

// open the summary via the result overlay button
const sumBtn = d.getElementById('piq-summary');
ok(sumBtn != null, 'result overlay has Hand summary button');
if (sumBtn) {
  sumBtn.click();
  const modal = d.querySelector('.piq-modal');
  ok(modal.style.display === 'flex', 'summary modal opened');
  // default = basic analysis text with hole cards
  ok(/Hand #\d+ Analysis/.test(modal.textContent), 'basic summary shows "Hand #N Analysis"');
  ok(/HOLE CARDS:/.test(modal.textContent), 'basic summary lists HOLE CARDS');
  ok(modal.querySelector('.hs-basic') != null, 'basic analysis text block present');
  // switch to Stats view
  const statsBtn = [...modal.querySelectorAll('.hs-actions button')].find(b => b.textContent === 'Stats');
  ok(statsBtn != null, 'Stats button present');
  statsBtn.click();
  const modal2 = d.querySelector('.piq-modal');
  ok(modal2.querySelector('.hs-panel') != null, 'stats view has per-street panels');
  ok(modal2.querySelector('.hs-eqtable') != null, 'stats view has equity table');
  ok(/Hand Results/.test(modal2.textContent), 'stats view shows Hand Results');
  ok(/AHEAD|BEHIND|\(Folded\)/.test(modal2.textContent), 'equity column shows AHEAD/BEHIND/(Folded)');
  // Hand Log view
  const logBtn = [...modal2.querySelectorAll('.hs-actions button')].find(b => b.textContent === 'Hand Log');
  logBtn.click();
  ok(/--- (Flop|Turn|River|Preflop) ---/.test(d.querySelector('.piq-modal').textContent), 'hand log view shows street markers');
}

// 4) font scale sanity: base body font is 20px now (was 14)
const styleText = [...d.querySelectorAll('style')].map(s => s.textContent).join('');
ok(/font:20px/.test(styleText), 'base font bumped to 20px');
ok(/width:60px;height:84px/.test(styleText), 'cards enlarged to 60x84');

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
