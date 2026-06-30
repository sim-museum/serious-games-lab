/* Load the FINAL built pokerIQ.html in jsdom exactly as a browser would —
 * executing the inlined <script> — and verify it boots, renders the table, and
 * plays hands end to end through the real UI (clicking action buttons).
 * Run: node test/test_built.js */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const htmlPath = path.join(__dirname, '..', '..', 'pokerIQ.html');
const html = fs.readFileSync(htmlPath, 'utf8');

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom;
const { document } = window;

// engine globals should now exist (script executed on load)
ok(typeof window.PokerEngine === 'object', 'PokerEngine global present');
ok(typeof window.PokerGame === 'object', 'PokerGame global present');
ok(typeof window.PokerBots === 'object', 'PokerBots global present');
ok(typeof window.PokerUI === 'object', 'PokerUI global present');
ok(typeof window.PokerTrainers === 'object', 'PokerTrainers global present');
ok(window.PIQ && window.PIQ.ctrl, 'app auto-booted (window.PIQ.ctrl)');

// table rendered
const app = document.getElementById('app');
ok(app.querySelector('.piq-felt') != null, 'felt rendered');
ok(app.querySelectorAll('.seat').length === 6, '6 seats present');
ok(app.querySelector('#piq-board') != null, 'board present');

// click through a hand: fold/check/call whichever buttons appear, up to N steps
const ctrl = window.PIQ.ctrl;
ctrl.botDelayMs = 0;   // resolve bot turns synchronously for the headless drive
ctrl.pump();           // flush the first hand's pending (timer-paced) bot turns
function clickFirstAction() {
  const btns = app.querySelectorAll('.piq-actions .btn');
  if (!btns.length) return false;
  // prefer check/call over fold to make hands last; fall back to fold
  let target = null;
  btns.forEach(b => { const t = b.textContent.toLowerCase(); if (/check|call/.test(t)) target = b; });
  (target || btns[0]).click();
  return true;
}

let steps = 0, handsSeen = 0;
let lastHand = ctrl.game.handNumber;
for (let i = 0; i < 400 && handsSeen < 6; i++) {
  if (ctrl.game.handInProgress && ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
    clickFirstAction(); steps++;
  } else if (!ctrl.game.handInProgress) {
    // result overlay should be showing a Next button
    const next = document.getElementById('piq-next');
    if (next) { next.click(); handsSeen++; }
    else break;
  } else {
    // bots resolving synchronously; nudge by re-rendering isn't needed — break if stuck
    break;
  }
}
ok(steps > 0, `hero clicked actions (${steps} steps)`);
ok(handsSeen >= 3, `played through multiple hands via UI (${handsSeen})`);
ok(ctrl.stats.sessionHands >= 3, `session stats recorded (${ctrl.stats.sessionHands})`);

// open a trainer modal and verify it builds
window.PIQ.openTrainer('jam');
ok(document.querySelector('.piq-modal').style.display === 'flex', 'trainer modal opened');
ok(document.querySelector('.modal-card h2').textContent.includes('Jam'), 'Jam-or-Fold trainer rendered');
// click an answer to make sure handlers are wired
const pushBtn = [...document.querySelectorAll('.modal-card .btn')].find(b => /push/i.test(b.textContent));
if (pushBtn) { pushBtn.click(); ok(document.querySelector('.modal-card .piq-feed').children.length > 0, 'jam trainer records an answer'); }
else ok(false, 'jam push button found');

// each trainer builds without throwing
let built = 0;
for (const key of Object.keys(window.PokerTrainers.REGISTRY)) {
  try { window.PIQ.openTrainer(key); built++; } catch (e) { console.log('  trainer build failed:', key, e.message); }
}
ok(built === Object.keys(window.PokerTrainers.REGISTRY).length, `all ${built} trainers build`);

// stats panel
window.PIQ.openStats();
ok(document.querySelector('.modal-card h2').textContent.includes('statistics'), 'stats panel opens');

// ---- new desktop-parity features wired through the real menu ----
const view = window.PIQ.view;
ok(typeof window.PokerNet === 'object' && typeof window.PokerClaude === 'object' &&
   typeof window.PokerFiles === 'object' && typeof window.PokerPrefs === 'object', 'new modules present in build');

// menu buttons exist
['net', 'file', 'prefs'].forEach(a => ok(app.querySelector(`[data-act="${a}"]`) != null, `menu button "${a}" present`));

// Preferences opens with all three tabs
view.onMenu('prefs');
ok(/Preferences/.test(document.querySelector('.modal-card h2').textContent), 'Preferences dialog opens');
ok(document.querySelectorAll('.pf-tab').length === 3, 'Preferences has Equity/Display/AI tabs');
view.closeModal();

// File ▾ popup → Save game modal
view.onMenu('file');
const filepop = document.querySelector('.menu-pop');
ok(filepop && [...filepop.querySelectorAll('button')].some(b => /Save game/.test(b.textContent)), 'File menu lists Save game');
const saveItem = [...filepop.querySelectorAll('button')].find(b => /Save game/.test(b.textContent));
saveItem.click();
ok(/Save game/.test(document.querySelector('.modal-card h2').textContent), 'Save game dialog opens');
// the save payload round-trips through loadState
const saveText = document.querySelector('.log-preview').value;
ok(saveText.length > 50 && JSON.parse(saveText).game, 'save JSON is valid + has game state');
view.closeModal();

// Online (WebRTC) dialog opens (jsdom has no RTCPeerConnection → graceful path still builds the menu)
view.onMenu('net');
ok(/online/i.test(document.querySelector('.modal-card h2').textContent), 'Online play dialog opens');
view.closeModal();

// Hand Summary → Analyze (Claude) with no key shows the key prompt (no network)
view.showHandSummary(ctrl.lastHistory);
const analyzeBtn = [...document.querySelectorAll('.modal-card .btn')].find(b => /Analyze \(Claude\)/.test(b.textContent));
ok(analyzeBtn != null, 'Hand Summary has an Analyze (Claude) button');
analyzeBtn.click();
ok(/Claude/.test(document.querySelector('.modal-card h2').textContent), 'Claude analysis dialog opens');
ok(/API key/.test(document.querySelector('#cl-body').textContent), 'prompts for an API key when none set (no silent network)');
view.closeModal();

// legacy-colours preference toggles the 4-colour deck class
window.PokerPrefs.Prefs.set('legacyColors', true); window.PokerPrefs.apply(ctrl);
ok(app.classList.contains('legacy-colors') || document.body.classList.contains('legacy-colors'), 'legacy-colours pref applies a class');
window.PokerPrefs.Prefs.set('legacyColors', false); window.PokerPrefs.apply(ctrl);

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
