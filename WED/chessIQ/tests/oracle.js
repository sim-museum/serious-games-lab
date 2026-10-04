// Parity oracle: runs the ORIGINAL engine from WED/kramnik_chess.html (extracted at run time, never copied) on the
// cases in stdin and prints the results as JSON. Used by test_parity.py.
const fs = require('fs'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', '..', 'kramnik_chess.html'), 'utf8');
const src = html.match(/<script type="text\/plain" id="engine-src">([\s\S]*?)<\/script>/)[1];
(0, eval)(src + '\nglobalThis.__nodes = () => NODES;');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const toBoard = arr => arr.map(p => p ? {c: p[0], t: p[1]} : null);
function perft(b, color, ep, d) {
  if (d === 0) return 1;
  let n = 0;
  for (const m of legalMoves(b, color, ep)) n += perft(applyMove(b, m), opp(color), epAfter(m), d - 1);
  return n;
}
const out = cases.map(c => {
  const b = toBoard(c.board), r = {};
  if (c.perft) r.perft = perft(b, c.turn, c.ep, c.perft);
  if (c.depth) {
    const m = bestMove(b, c.turn, c.ep, {t: 1e12, d: c.depth, banned: c.banned || []});
    r.best = m ? [m.from, m.to, m.promo || null, m.kind, m._v === undefined ? null : m._v] : null;
    r.nodes = __nodes();
  }
  r.sans = legalMoves(b, c.turn, c.ep).map(m => sanOf(b, m, c.ep));
  r.eval = evaluate(b);
  return r;
});
process.stdout.write(JSON.stringify(out));
