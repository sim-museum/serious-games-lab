/* Save/Load + Files (hand history, hand-class P&L, buy chips) test under jsdom.
 * Verifies a game round-trips through saveState/loadState mid-hand and between
 * hands, and that the File dialogs build without error. Run: node test/test_files.js */
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><div id="app"></div>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
global.Blob = dom.window.Blob;
global.URL = dom.window.URL || { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };
global.FileReader = dom.window.FileReader;

const PokerUI = require('../src/ui.js');
const PG = require('../src/game.js');
require('../src/engine.js');
// files.js uses root.PokerEngine / root.PokerFiles globals
global.PokerEngine = require('../src/engine.js');
const PF = require('../src/files.js');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };
function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

let view;
const ctrl = new PokerUI.Controller({ rng: mulberry32(7), botDelayMs: 0, equityIters: 120, onRender: (s) => view.render(s) });
view = new PokerUI.View(document.getElementById('app'), ctrl);
const Bots = require('../src/bots.js');

// --- play 2 hands so we have history + holeStats ---
function autoplay() {
  let guard = 0;
  while (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
    if (++guard > 300) break;
    const [a, amt] = Bots.decide(ctrl.game, ctrl.game.players[0]);
    ctrl.act(a, amt);
  }
}
ctrl.newHand(); autoplay();
ctrl.newHand(); autoplay();
ok(ctrl.handHistories.length >= 1, 'hand histories accumulate (' + ctrl.handHistories.length + ')');

// decision journal records hero predictions + resolves them for Brier calibration
ok(ctrl.journal && ctrl.journal.entries.length >= 1, 'journal recorded hero decisions (' + ctrl.journal.entries.length + ')');
const preds = ctrl.journal.sessionPredictions();
ok(preds.every(p => p[0] >= 0 && p[0] <= 1 && (p[1] === 0 || p[1] === 1)), 'predictions are (equity 0..1, outcome 0/1) pairs');

// --- buy chips ---
const before = ctrl.game.players[0].stack;
ctrl.buyChips(150, 0);
ok(ctrl.game.players[0].stack === before + 150, 'buyChips adds to hero stack');

// --- save / load round-trip (deal a fresh hand, save mid-hand, load, compare) ---
ctrl.newHand();
// step a couple of bot actions so we're mid-hand
let g = ctrl.game;
const snapBefore = JSON.stringify({
  pot: g.pot, board: g.board.map(c => c), hand: g.players[0].hand.slice(),
  stacks: g.players.map(p => p.stack), toAct: g.toAct, street: g.streetIdx,
  hn: g.handNumber, bl: g.blindLevel, hip: g.handInProgress,
});
const saved = ctrl.saveState();
const json = JSON.stringify(saved);                  // ensure serializable
ok(json.length > 50, 'saveState serializes to JSON');

// mutate state, then load to prove restore replaces it
ctrl.game.pot = 99999; ctrl.game.players[0].stack = -1;
ctrl.loadState(JSON.parse(json));
g = ctrl.game;
const snapAfter = JSON.stringify({
  pot: g.pot, board: g.board.map(c => c), hand: g.players[0].hand.slice(),
  stacks: g.players.map(p => p.stack), toAct: g.toAct, street: g.streetIdx,
  hn: g.handNumber, bl: g.blindLevel, hip: g.handInProgress,
});
ok(snapBefore === snapAfter, 'loadState restores exact game state');

// after load, play continues to completion without throwing
let threw = false;
try { autoplay(); let guard = 0; while (ctrl.game.handInProgress && guard++ < 500) { if (ctrl.game.awaitingBot >= 0) ctrl.game.stepBot(); else if (ctrl.game.toAct === 0 && ctrl.game.awaitingAction) ctrl.act('f', 0); else break; } }
catch (e) { threw = true; console.log('  loadState continue threw:', e.message); }
ok(!threw, 'play continues after loadState');

// --- File dialogs build without error ---
const fctx = { ctrl, view };
for (const fn of ['saveGame', 'loadGame', 'buyChips', 'handHistory', 'handClassPnL']) {
  let e2 = null;
  try { PF[fn](fctx); view.closeModal(); } catch (e) { e2 = e; }
  ok(!e2, 'File.' + fn + ' opens without error' + (e2 ? ': ' + e2.message : ''));
}

console.log(fail ? `\n✗ ${fail} FAILED, ${pass} passed` : `\n✓ ALL PASS — ${pass} passed, 0 failed`);
process.exit(fail ? 1 : 0);
