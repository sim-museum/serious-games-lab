/* Session-log format test — drives the built HTML in jsdom, plays a few hands,
 * saves the log, and asserts it matches the PyQt pokerIQ format. Run: node test/test_log.js */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const ctrl = window.PIQ.ctrl;
// deterministic clock so the dump is stable
let t = new Date(2026, 5, 5, 21, 57, 12);
ctrl.now = () => t;
const Bots = window.PokerBots;
ctrl.botDelayMs = 0; ctrl.pump();

// play 3 hands, hero acts like a bot
for (let h = 0; h < 3; h++) {
  let guard = 0;
  while (ctrl.game.handInProgress && guard++ < 300) {
    if (ctrl.game.awaitingAction && ctrl.game.toAct === 0) {
      const [a, amt] = Bots.decide(ctrl.game, ctrl.game.players[0]);
      ctrl.act(a, amt);
    } else ctrl.pump();
  }
  if (h < 2) ctrl.newHand();
}

const log = ctrl.buildLogText();

// ---- format assertions vs pokerIQ.py ----
ok(log.startsWith('='.repeat(60) + '\nPOKER LEARNING GAME - SESSION LOG\n'), 'session header exact');
ok(/Started: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\n/.test(log), 'Started line format');
ok(/=== NEW HAND ===/.test(log), 'NEW HAND marker');
ok(/={60}\nHAND #1 - \d{2}:\d{2}:\d{2}\n={60}/.test(log), 'hand header block');
ok(/=== GAME STATUS ===/.test(log) && /  Game Type: Texas Hold 'em/.test(log) && /  Limit Type: No Limit/.test(log), 'GAME STATUS block');
ok(/  Starting Chips: \$200/.test(log), 'starting chips line');
ok(/  Blinds \(Original\/Current\): \$1\/\$2 → \$1\/\$2/.test(log), 'blinds line with arrow');
ok(/Dealer: .+\nHole Cards Dealt:\n  .+: [2-9TJQKA][cdhs] [2-9TJQKA][cdhs]/.test(log), 'Dealer + Hole Cards Dealt');
ok(/ posts \$\d+/.test(log), 'blind post line');
ok(/: (Folds|Checks|Calls \$\d+|Raises to \$\d+)/.test(log), 'action lines (Folds/Checks/Calls/Raises to)');
ok(/--- (Flop|Turn|River) ---\n  \[STATS\]\n    .{15} Cards: .+  Equity: \d+\.\d%  PotOdds: \d+\.\d%/.test(log), '--- Street --- + [STATS] block');
ok(/\nBoard: ([2-9TJQKA][cdhs] ?){3,5}/.test(log), 'Board line');
ok(/(Final Stacks:\n( {2}.+: \$-?\d+\n)+)/.test(log), 'Final Stacks block');
ok(/Hand Results \(Gain\/Loss\):\n( {2}.+: (\+\$\d+|-\$\d+|\$0 \(broke even\))\n)+/.test(log), 'Gain/Loss block');
// winner line: either uncontested or showdown
ok(/(Winner: .+ - \$\d+ \(others folded\))|(WINNER: .+ \(\$-?\d+\)!)/.test(log), 'winner line');
// showdown hand types use eval7 short names
ok(/: (High Card|Pair|Two Pair|Trips|Straight|Flush|Full House|Quads|Straight Flush)\n/.test(log) || /others folded/.test(log), 'showdown hand-type or uncontested');
// session summary
ok(/#{60}\nSESSION SUMMARY\n#{60}/.test(log), 'SESSION SUMMARY block');
ok(/=== TABLE STATS ===/.test(log) && /Showdowns W\/Total/.test(log), 'TABLE STATS header');
ok(/--- CHIP COUNT ---/.test(log), 'CHIP COUNT block');
ok(/Ended: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\n$/.test(log), 'Ended line at EOF');

// filename format
ok(/^poker_log_\d{8}_\d{6}\.txt$/.test(ctrl.logFilename()), 'filename poker_log_YYYYMMDD_HHMMSS.txt');

// Save Log button works (preview modal opens with the text)
const btn = [...d.querySelectorAll('.piq-menu button')].find(b => /Log/.test(b.textContent));
ok(btn != null, 'Save Log button present');
btn.click();
ok(d.querySelector('.log-preview') != null, 'log preview modal opens');
ok(d.querySelector('.log-preview').value.length > 200, 'preview contains the log text');

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
if (process.argv[2] === '--dump') { console.log('\n========= SAMPLE LOG =========\n'); console.log(log); }
process.exit(fail ? 1 : 0);
