/* Emit JS equity for a fixed set of scenarios + a speed benchmark.
 * node equity_js.js  -> writes equity_js.json */
const E = require('./poker-engine.js');
const fs = require('fs');

const H = E.handFromStr;
const ITER = 50000;

const scenarios = [
  { name: 'AA vs 1 random, preflop', hero: 'As Ah', board: '', opp: 1 },
  { name: 'AA vs 3 random, preflop', hero: 'As Ah', board: '', opp: 3 },
  { name: '72o vs 1 random, preflop', hero: '7d 2c', board: '', opp: 1 },
  { name: 'AKs vs 2 random, preflop', hero: 'As Ks', board: '', opp: 2 },
  { name: 'flush draw vs 1, flop', hero: 'As Ks', board: 'Qs 7s 2d', opp: 1 },
  { name: 'set vs 2, flop', hero: '7c 7d', board: '7h Kd 2c', opp: 2 },
  { name: 'OESD vs 1, turn', hero: '9c 8c', board: 'Th 7d 2s Kc', opp: 1 },
  { name: 'top pair vs 1, river', hero: 'Ad Kc', board: 'Kh 9s 4d 2c 7h', opp: 1 },
];

const out = scenarios.map(s => {
  const eq = E.equityVsRandom(H(s.hero), s.board ? H(s.board) : [],
    { iterations: ITER, opponents: s.opp });
  return { name: s.name, hero: s.hero, board: s.board, opp: s.opp, eq };
});
fs.writeFileSync(__dirname + '/equity_js.json', JSON.stringify(out, null, 0));
out.forEach(r => console.log(`  ${r.eq.toFixed(4)}  ${r.name}`));

// ---- benchmark: hits/sec of evaluate() and equityVsRandom ----
const t0 = Date.now();
let acc = 0;
const sample = H('As Ks Qh 7d 2c 9s 4h');
for (let i = 0; i < 2000000; i++) acc ^= E.evaluate(sample);
const t1 = Date.now();
const evalsPerSec = Math.round(2000000 / ((t1 - t0) / 1000));
console.log(`\n  evaluate(): ${(evalsPerSec / 1e6).toFixed(1)}M hands/sec  (acc=${acc & 1})`);

const t2 = Date.now();
E.equityVsRandom(H('As Ah'), [], { iterations: 10000, opponents: 1 });
const t3 = Date.now();
console.log(`  equityVsRandom 10k iters, 1 opp: ${t3 - t2}ms`);
