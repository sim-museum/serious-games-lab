/* Hand Summary test — everyone's hole cards + best hand per street, basic/stats/
 * log views. Builds a seeded instance in the built page. Run: node test/test_summary.js */
const fs = require('fs'), path = require('path');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'pokerIQ.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/' });
const { window } = dom, d = window.document;
function mb(a){return function(){a|=0;a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};}

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

// description helpers are pure — test them directly
const T = window.PokerToMLogic, E = window.PokerEngine;
const h = s => E.handFromStr(s);
ok(T.categorizePreflop(h('7c Kd')) === 'offsuit junk', 'categorize 7cKd = offsuit junk');
ok(T.categorizePreflop(h('Ah Ks')) === 'big slick offsuit', 'categorize AKo = big slick offsuit');
ok(T.categorizePreflop(h('As Ks')) === 'big slick', 'categorize AKs = big slick');
ok(T.categorizePreflop(h('Th Ts') ) === 'high pair', 'categorize TT = high pair');
ok(T.categorizePreflop(h('8d 7d')) === 'suited connector', 'categorize 87s = suited connector');
ok(T.categorizePreflop(h('5d Ac')) === 'ace-rag', 'categorize A5o = ace-rag');
ok(T.handName(h('7c Kd')) === 'King-Seven', 'handName 7cKd = King-Seven');
ok(T.handName(h('Kh Kd')) === 'pocket Kings', 'handName KK = pocket Kings');
ok(T.handName(h('As Ks')) === 'Ace-King suited', 'handName AKs = Ace-King suited');
// made-hand descriptions per street
ok(T.describeMadeHand(h('As Ks'), h('Ks 2s 9d')) === 'top pair (Ks)', 'AKs on Ks29 = top pair (Ks)');
ok(T.describeMadeHand(h('Tc Td'), h('Ks 2s 9d')) === 'pocket pair (TT)', 'TT on Ks29 = pocket pair (TT)');
ok(T.describeMadeHand(h('6h 9d'), h('6s Jc 7d')) === 'bottom pair (6s)', '69 on 6J7 = bottom pair (6s)');
ok(/^set of 9s/.test(T.describeMadeHand(h('9c 9h'), h('9s 2s Kd'))), '99 on 9s2K = set of 9s');
ok(T.describeMadeHand(h('Ac Kc'), h('Kh Kd 7d')) === 'trips (Ks)', 'AcKc on KhKd7 = trips (Ks)');

// full summary data over a played hand
const app = d.createElement('div'); d.body.appendChild(app);
const C = new window.PokerUI.Controller({ rng: mb(3), botDelayMs: 0, onRender: () => {} });
const V = new window.PokerUI.View(app, C); C.onRender = s => V.render(s);
C.newHand();
let g = 0; while (C.game.handInProgress && g++ < 300) { if (C.humanToAct()) C.act('c', 0); else C.pump(); }
const data = C.buildSummaryData(C.lastHistory);

// every dealt player has hole cards + a category in the basic view
ok(data.holeCards.length === 6, `all 6 players' hole cards captured (${data.holeCards.length})`);
ok(data.holeCards.every(x => x.cards.length === 2 && x.category), 'each has cards + a category label');
ok(data.heldLines.length >= 1 && /^[A-Z]/.test(data.heldLines[0].held), 'hero "held" line present');

// per-street panels carry a made-hand for every player + equity for contesting
ok(data.panels.length >= 1, 'panels built');
const flop = data.panels.find(p => p.name === 'Flop');
if (flop) {
  ok(flop.rows.length === 6, 'flop panel lists all 6 players (incl. folded)');
  ok(flop.rows.every(r => typeof r.made === 'string' && r.made.length), 'every row has a best-hand description');
  const contesting = flop.rows.filter(r => !r.folded);
  ok(contesting.every(r => typeof r.real === 'number' && typeof r.thinking === 'number'), 'contesting rows have True + vs-Range equity');
  ok(contesting.some(r => r.ahead) , 'at least one player marked AHEAD');
  // true equities of contesting players sum to ~1
  const sum = contesting.reduce((a, r) => a + r.real, 0);
  ok(Math.abs(sum - 1) < 0.02, `true equities sum to ~100% (${(sum*100).toFixed(0)}%)`);
}

// results cover every player with start→end
ok(data.results.length === 6 && data.results.every(r => 'start' in r && 'end' in r && 'net' in r), 'results have net + start→end for all players');

// DOM: the three views render distinct content
const basic = V.summaryBasicHTML(data, ''); const stats = V.summaryStatsHTML(data, '');
ok(/Hand #\d+ Analysis/.test(basic) && /HOLE CARDS:/.test(basic), 'basic view text');
ok(/True Equity/.test(stats) && /Hand Results/.test(stats), 'stats view structure');
const tmp = d.createElement('div'); tmp.innerHTML = stats;
ok(tmp.querySelectorAll('.hs-panel').length >= 2, 'stats has multiple street panels');
ok(tmp.querySelectorAll('.hs-eqtable tr').length >= 7, 'equity table has rows');

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
