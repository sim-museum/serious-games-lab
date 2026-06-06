/* Theory of Mind screen test — drives the built HTML in jsdom, turns Training
 * on, and verifies the ToM view renders with all panels + tabs. */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const ctrl = window.PIQ.ctrl;
ctrl.botDelayMs = 0; ctrl.pump();

// turn Training on via the toggle
const toggle = d.getElementById('piq-train');
ok(toggle != null, 'Training toggle present');
toggle.click();
ok(ctrl.training === true, 'training enabled after toggle');

const tom = d.getElementById('piq-tomview');
ok(tom.style.display === 'block', 'ToM view shown');
ok(d.getElementById('piq-tableview').style.display === 'none', 'table view hidden');

// strip + metrics
ok(/Your Hand/.test(tom.textContent), 'hand strip rendered');
ok(/Equity \(vs Ranges\)/.test(tom.textContent), 'equity-vs-ranges metric present');
ok(/Pot Odds/.test(tom.textContent), 'pot odds metric present');
ok(/Implied/.test(tom.textContent), 'implied metric present');

// range-mode radio
ok(tom.querySelectorAll('.rm').length === 3, 'three range-mode options');
ok(tom.querySelector('.rm.neu.on') != null, 'neutral selected by default');

// tabs: Advisor, Hero, + one per bot (5)
const tabs = tom.querySelectorAll('.tom-tab');
ok(tabs.length === 7, `7 tabs (Advisor+Hero+5 bots): got ${tabs.length}`);
ok(/Gordon's script/.test(tom.textContent), 'Advisor tab shows Gordon script by default');
ok(/POT ODDS & EQUITY/.test(tom.textContent), 'pot-odds header present');

// dashboard: 9 tiles, MDF/bluff-catch present
const tiles = tom.querySelectorAll('.mtile');
ok(tiles.length === 9, `9 dashboard tiles: got ${tiles.length}`);
ok(/MDF/.test(tom.textContent) && /Bluff-catch/.test(tom.textContent) && /Risk of Ruin/.test(tom.textContent), 'key metric captions present');

// switch to Hero tab → pot commitment + outs board
const heroTab = [...tabs].find(t => t.getAttribute('data-tab') === 'hero');
heroTab.click();
const tom2 = d.getElementById('piq-tomview');
ok(/Pot Commitment/.test(tom2.textContent), 'Hero tab shows Pot Commitment');
ok(tom2.querySelector('.outs-board') != null, 'Hero tab shows outs board');

// switch to an opponent tab → range grid (169 cells) + betting history
const botTab = [...d.querySelectorAll('.tom-tab')].find(t => /Fiona|Tim|Bruce|Steve|Angela/.test(t.textContent));
ok(botTab != null, 'an opponent tab exists');
botTab.click();
const tom3 = d.getElementById('piq-tomview');
ok(tom3.querySelector('.range-grid') != null, 'opponent tab shows range grid');
ok(tom3.querySelectorAll('.rg-cell').length === 169, `range grid has 169 cells: got ${tom3.querySelectorAll('.rg-cell').length}`);
ok(/Estimated Range for/.test(tom3.textContent), 'range title present');
ok(/Player Style:/.test(tom3.textContent), 'betting history shows player style');

// range mode switch updates state
const weak = d.querySelector('.rm.weak'); weak.click();
ok(ctrl.rangeMode === 'loose', 'range mode → loose (opps weak)');

// EV labels on action buttons (training mode), if hero to act
if (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
  ok(d.querySelector('.piq-actions .btn small.ev') != null, 'action buttons show EV labels in training mode');
}

// toggle back to table view
d.getElementById('piq-train').click();
ok(ctrl.training === false, 'training disabled');
ok(d.getElementById('piq-tableview').style.display === 'flex', 'table view restored');

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
