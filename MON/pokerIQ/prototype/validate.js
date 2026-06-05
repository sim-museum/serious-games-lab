/* Validation for poker-engine.js — run with: node validate.js
 *
 * Part A: hard-coded ordering sanity (royal > sf > quads > ... > high card),
 *         wheel, steel wheel, kicker tiebreaks, full-house edge cases.
 * Part B: emit JSON for `pairs` random 7-card matchups so a Python script can
 *         confirm eval7 agrees on every winner/loser/tie.  Writes pairs.json.
 */
const E = require('./poker-engine.js');
const fs = require('fs');

let pass = 0, fail = 0;
function ok(cond, msg) { if (cond) pass++; else { fail++; console.log('  FAIL:', msg); } }
const ev = s => E.evaluate(E.handFromStr(s));

console.log('== Part A: ordering & category sanity ==');

// category ladder, each strictly beats the next
const ladder = [
  ['As Ks Qs Js Ts', 'Royal/SF'],
  ['9s 8s 7s 6s 5s', 'Straight flush'],
  ['Ac Ad Ah As Kd', 'Quads'],
  ['Ac Ad Ah Kd Kc', 'Full house'],
  ['As Qs 9s 6s 3s', 'Flush'],
  ['Ah Kd Qc Js Td', 'Straight'],
  ['Ac Ad Ah Kc Qd', 'Trips'],
  ['Ac Ad Kc Kd Qh', 'Two pair'],
  ['Ac Ad Kc Qd Jh', 'One pair'],
  ['Ac Kd Qc Js 9h', 'High card'],
];
for (let i = 0; i < ladder.length - 1; i++) {
  ok(ev(ladder[i][0]) > ev(ladder[i + 1][0]),
    `${ladder[i][1]} > ${ladder[i + 1][1]}`);
}
// categories land where expected
ok(E.categoryOf(ev(ladder[0][0])) === E.CAT.STRAIGHT_FLUSH, 'royal is SF cat');
ok(E.describe(ev(ladder[0][0])) === 'Royal Flush', 'royal described');

// wheel straight (A2345) recognized, ranks as 5-high, below 6-high
ok(E.categoryOf(ev('Ah 2c 3d 4s 5h')) === E.CAT.STRAIGHT, 'wheel is straight');
ok(ev('6h 2c 3d 4s 5h') > ev('Ah 2c 3d 4s 5h'), '6-high straight > wheel');
ok(E.describe(ev('Ah 2c 3d 4s 5h')).includes('5-high'), 'wheel is 5-high');
// steel wheel (A2345 suited) is a straight flush, 5-high
ok(E.categoryOf(ev('Ah 2h 3h 4h 5h')) === E.CAT.STRAIGHT_FLUSH, 'steel wheel SF');
ok(ev('6h 2h 3h 4h 5h') > ev('Ah 2h 3h 4h 5h'), '6-high SF > steel wheel');

// kicker tiebreaks
ok(ev('Ac Ad Kc Qd Jh') > ev('Ac Ad Kc Qd Th'), 'pair, better kicker wins');
ok(ev('Ac Ad Kc Kd Ah') === ev('As Ah Ks Kh Ad'), 'identical ranks tie (suits ignored)');
ok(ev('Ks Kd Qc Qh Ad') > ev('Ks Kd Jc Jh Ad'), 'two pair, higher 2nd pair');
ok(ev('Ks Kd Qc Qh Ad') > ev('Ks Kd Qc Qh 2d'), 'two pair, kicker');

// 7-card best-five selection
ok(E.categoryOf(ev('As Ks Qs Js Ts 2c 3d')) === E.CAT.STRAIGHT_FLUSH, '7card royal');
ok(E.categoryOf(ev('Ac Ad Ah As Kd Qc 2c')) === E.CAT.QUADS, '7card quads');
// two trips -> full house using higher trips, lower as pair
ok(E.describe(ev('Ac Ad Ah Kc Kd Kh 2c')).startsWith('Full House, As'), 'two trips -> AAA full of KKK');
// trips + two pairs on board -> full house picks best pair
ok(E.categoryOf(ev('Ac Ad Ah Kc Kd Qc Qd')) === E.CAT.FULL_HOUSE, 'trips+2pair -> boat');
// flush of 6 -> takes top 5
ok(E.describe(ev('As Ks Qs Js 9s 2s 3c')) === 'Flush, A-high', '6-card flush top5');

console.log(`  Part A: ${pass} passed, ${fail} failed`);

// ---- Part B: emit random matchups for eval7 cross-check ----
// deterministic PRNG (mulberry32) so the run is reproducible
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(12345);
const NPAIRS = parseInt(process.argv[2] || '20000', 10);
const deck = E.fullDeck();
function shuffle(d) {
  for (let i = d.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    const t = d[i]; d[i] = d[j]; d[j] = t;
  }
}
const rows = [];
for (let i = 0; i < NPAIRS; i++) {
  shuffle(deck);
  // two distinct 7-card hands sharing a 5-card board, like a real showdown
  const board = deck.slice(0, 5);
  const a = [deck[5], deck[6], ...board];
  const b = [deck[7], deck[8], ...board];
  const sa = E.evaluate(a), sb = E.evaluate(b);
  const sign = sa > sb ? 1 : (sa < sb ? -1 : 0);
  rows.push({
    a: a.map(E.cardToStr), b: b.map(E.cardToStr), sign,
  });
}
fs.writeFileSync(__dirname + '/pairs.json', JSON.stringify(rows));
console.log(`\n== Part B: wrote ${rows.length} matchups to pairs.json (for eval7 cross-check) ==`);

process.exit(fail ? 1 : 0);
