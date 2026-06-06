/* UI controller + view smoke test under jsdom — run: node test/test_ui.js
 * Builds the table, plays a full hand (hero auto-folds/checks/calls), and
 * asserts the DOM reflects state and a hand result is produced. */
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><div id="app"></div>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
// keep Node's own global.performance (jsdom's recurses); ui.js uses performance.now

// expose engine modules as browser-style globals for ui.js (which prefers require under node)
const PokerUI = require('../src/ui.js');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

let renders = 0;
const ctrl = new PokerUI.Controller({
  rng: mulberry32(2024),
  botDelayMs: 0,
  equityIters: 200,
  onRender: (snap) => { renders++; view.render(snap); },
});
const view = new PokerUI.View(document.getElementById('app'), ctrl);

// play 5 full hands, hero acts like a simple bot (call/check, fold to big bets)
const Bots = require('../src/bots.js');
let handsCompleted = 0;
ctrl.onHandEnd = () => { handsCompleted++; };

for (let h = 0; h < 5; h++) {
  ctrl.newHand();
  let guard = 0;
  while (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
    if (++guard > 200) { ok(false, 'hero turn loop guard'); break; }
    // decide hero action via bot logic for unattended play
    const [a, amt] = Bots.decide(ctrl.game, ctrl.game.players[0]);
    ctrl.act(a, amt);
  }
}

// assertions
ok(renders > 5, `view rendered multiple times (${renders})`);
ok(handsCompleted === 5, `5 hands completed (${handsCompleted})`);

// DOM structure present
const appEl = document.getElementById('app');
ok(appEl.querySelector('.piq-felt') != null, 'felt rendered');
ok(appEl.querySelectorAll('.seat').length === 6, '6 seats rendered');
ok(appEl.querySelector('#piq-board') != null, 'board element present');

// a card renders with rank+suit
const sampleCard = PokerUI.cardHTML(require('../src/engine.js').cardFromStr('Ah'), false);
ok(sampleCard.includes('♥') && sampleCard.includes('A'), 'card HTML has rank + suit glyph');
ok(PokerUI.cardHTML(0, true).includes('back'), 'hidden card renders as back');

// session stats accumulated
ok(ctrl.stats.sessionHands === 5, `session recorded 5 hands (${ctrl.stats.sessionHands})`);

// advisor produces EV numbers when it's hero's turn (start a fresh hand and check)
ctrl.newHand();
if (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
  const adv = ctrl.advisor();
  ok(adv && typeof adv.equity === 'number' && adv.equity >= 0 && adv.equity <= 1, 'advisor equity in [0,1]');
  ok(adv && typeof adv.evCall === 'number', 'advisor has EV call');
  ok(appEl.querySelector('.adv-verdict') != null, 'advisor verdict rendered');
  const actionBtns = appEl.querySelectorAll('.piq-actions .btn');
  ok(actionBtns.length >= 2, `hero action buttons rendered (${actionBtns.length})`);
} else {
  ok(true, 'hero folded preflop in fresh hand (no advisor) — acceptable');
}

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
