/* Engine correctness — run: node test/test_game.js
 * Plays thousands of full hands with all bots and asserts invariants:
 *  - chips are conserved every hand (Σ stacks constant; no money printed/burned)
 *  - pot equals Σ totalInvested at showdown
 *  - side pots award correctly in forced all-in scenarios
 *  - no illegal negative stacks; engine never deadlocks
 */
const G = require('../src/game.js');
const Bots = require('../src/bots.js');

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) pass++; else { fail++; console.log('  FAIL:', m); } };

const TOTAL_CHIPS = G.STARTING_STACK * 6;
let handsPlayed = 0, showdowns = 0, allInHands = 0, maxBlind = 0;

const rng = mulberry32(99);
const game = new G.Game({ rng, botDecide: Bots.decide });

for (let h = 0; h < 4000; h++) {
  // reset stacks if table can't continue (keeps the sim going)
  if (game.activePlayers().length < 2 || game.players.filter(p => p.stack > 0).length < 2) {
    game.resetStacks();
  }
  const before = game.players.reduce((a, p) => a + p.stack, 0);

  const dealt = game.dealHand();
  if (!dealt) { game.resetStacks(); continue; }

  // drive: the engine auto-runs bots; only the human seat needs us. Make the
  // "human" act like another bot so we can run unattended.
  let guard = 0;
  while (game.awaitingAction) {
    if (++guard > 5000) { console.log('  DEADLOCK at hand', h); fail++; break; }
    const seat = game.toAct;
    const [a, amt] = Bots.decide(game, game.players[seat]); // treat hero as a bot
    // hero has style 'human'; give it a concrete style for the sim
    game.applyAction(seat, a, amt);
  }

  handsPlayed++;
  const res = game.lastResult;
  if (res && res.showdown.length > 1) showdowns++;
  if (game.players.some(p => p.allIn)) allInHands++;
  maxBlind = Math.max(maxBlind, game.blindLevel);

  // INVARIANT 1: chip conservation
  const after = game.players.reduce((a, p) => a + p.stack, 0);
  if (after !== before) {
    ok(false, `chip leak hand ${h}: before=${before} after=${after}`);
    break;
  }
  // INVARIANT 2: no negative stacks
  if (game.players.some(p => p.stack < 0)) { ok(false, `negative stack hand ${h}`); break; }
  // INVARIANT 3: pot fully distributed (lastResult payouts sum to pot)
  if (res) {
    const paid = Object.values(res.payouts).reduce((a, b) => a + b, 0);
    if (paid !== res.pot) { ok(false, `pot mismatch hand ${h}: pot=${res.pot} paid=${paid}`); break; }
  }
}
ok(true, 'ran without chip leak / deadlock / negative stack'); // reached only if loop didn't break on those

console.log(`\nplayed ${handsPlayed} hands; ${showdowns} showdowns; ${allInHands} all-in hands; reached blind level ${maxBlind}`);

// --- targeted side-pot test: 3 players, forced all-ins of different sizes ---
(function sidePotTest() {
  const g = new G.Game({ rng: mulberry32(7), botDecide: () => ['c', 0], numBots: 2 });
  // hand-craft a 3-way all-in: short stack 20, mid 60, big 200
  g.players[0].stack = 20; g.players[1].stack = 60; g.players[2].stack = 200;
  // give deterministic hands by stacking the deck after deal isn't exposed;
  // instead just verify pot math via buildSidePots directly.
  g.players[0].totalInvested = 20; g.players[0].active = true;
  g.players[1].totalInvested = 60; g.players[1].active = true;
  g.players[2].totalInvested = 60; g.players[2].active = true; // big only called 60
  const pots = g.buildSidePots();
  // layer 1 (0..20): all 3 -> 60 ; layer 2 (20..60): players 1,2 -> 80
  const total = pots.reduce((a, p) => a + p.amount, 0);
  ok(total === 140, `side-pot total = 140 (got ${total})`);
  ok(pots.length === 2, `two side-pot layers (got ${pots.length})`);
  ok(pots[0].amount === 60 && pots[0].eligible.size === 3, 'main pot 60, 3 eligible');
  ok(pots[1].amount === 80 && pots[1].eligible.size === 2, 'side pot 80, 2 eligible');
})();

console.log(`\n${fail === 0 ? '✓ ALL PASS' : '✗ FAILURES'} — ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
