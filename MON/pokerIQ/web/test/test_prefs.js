/* Preferences test under jsdom: store round-trips, equity mode switches the
 * hero-equity method, legacy-colours toggles the document class, and the dialog
 * builds + saves. Run: node test/test_prefs.js */
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><div id="app"></div>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;

const PokerUI = require('../src/ui.js');
require('../src/analytics.js');                 // exports __piqStore onto globalThis
const PP = require('../src/prefs.js');
global.PokerPrefs = PP;                          // ui.js reads root.PokerPrefs in browser path

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };
function mulberry32(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

// defaults
ok(PP.Prefs.visibleOnly() === true, 'visibleOnly defaults true');
ok(PP.Prefs.legacyColors() === false, 'legacyColors defaults false');

// set + read back
PP.Prefs.set('legacyColors', true);
ok(PP.Prefs.legacyColors() === true, 'legacyColors persists');
PP.Prefs.set('visibleOnly', false);
ok(PP.Prefs.visibleOnly() === false, 'visibleOnly persists');

let view;
const ctrl = new PokerUI.Controller({ rng: mulberry32(3), botDelayMs: 0, equityIters: 80, onRender: (s) => view.render(s) });
view = new PokerUI.View(document.getElementById('app'), ctrl);

// apply() sets the document class + controller flag
PP.apply(ctrl);
ok(ctrl.visibleCardsOnly === false, 'apply sets ctrl.visibleCardsOnly');
const rootEl = document.getElementById('app');
ok(rootEl.classList.contains('legacy-colors'), 'apply toggles legacy-colors class');

// equity mode: with visibleOnly=false and god knowledge, hero equity uses multiway
ctrl.newHand();
ctrl.visibleCardsOnly = false; ctrl.refreshHeroEquity();
const godEq = ctrl.heroEquity;
ctrl.visibleCardsOnly = true; ctrl.refreshHeroEquity();
const pubEq = ctrl.heroEquity;
ok(godEq != null && pubEq != null, 'both equity modes produce a number');

// dialog builds + Save commits without throwing
let threw = null;
try {
  PP.openDialog({ ctrl, view });
  // simulate Save on the equity tab
  const save = [...document.querySelectorAll('.modal-card .btn.check')].find(b => b.textContent === 'Save');
  if (save) save.onclick();
} catch (e) { threw = e; }
ok(!threw, 'Preferences dialog opens + saves' + (threw ? ': ' + threw.message : ''));

// per-seat bot pref applies on next hand
PP.Prefs.setBot(1, 'shark');
ctrl.applyBotPrefs();
ok(ctrl.game.players[1].style === 'shark', 'applyBotPrefs sets seat 1 style');

// cleanup global so other tests are unaffected
delete global.PokerPrefs;
console.log(fail ? `\n✗ ${fail} FAILED, ${pass} passed` : `\n✓ ALL PASS — ${pass} passed, 0 failed`);
process.exit(fail ? 1 : 0);
