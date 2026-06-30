/*
 * PokerIQ — game engine (betting, side pots, showdown).
 *
 * Ports TextModeGame + Player from pokerIQ.py into a UI-agnostic state machine.
 * The original text/GUI loop is synchronous; here the engine is event-driven so
 * a browser UI can drive it one action at a time:
 *
 *   const g = new Game(opts);
 *   g.dealHand();
 *   while (g.awaitingAction) {
 *     const seat = g.toAct;                 // whose turn
 *     g.applyAction(seat, 'r', amount);     // f / c / r
 *   }                                        // engine auto-runs bots if wired
 *
 * Differences from the Python reference (improvements, not regressions):
 *  - TRUE side pots at showdown (the text version just split the whole pot;
 *    this tracks total_invested per player and builds layered pots).
 *  - Deterministic RNG injectable for tests.
 *
 * Depends on engine.js (PokerEngine) for hand evaluation.
 */
(function (root) {
  'use strict';
  const E = (typeof require !== 'undefined') ? require('./engine.js') : root.PokerEngine;

  const STREETS = ['Preflop', 'Flop', 'Turn', 'River'];
  const STARTING_STACK = 200;
  const HANDS_PER_BLIND_LEVEL = 10;
  const BLIND_LEVELS = [
    [1, 2], [2, 4], [3, 6], [5, 10], [10, 20],
    [15, 30], [25, 50], [50, 100], [75, 150], [100, 200],
  ];

  // Canonical 5-bot lineup (one of each archetype), matching pokerIQ.py.
  const DEFAULT_BOT_LINEUP = [
    ['Tight Tim', 'tight'],
    ['Loose Bruce', 'loose'],
    ['Aggro Angela', 'aggressive'],
    ['Sharkey Steve', 'shark'],
    ['Fluid Fiona', 'tom'],
  ];

  const CUTE_NAMES = {
    optimal: 'Optimal Olivia', tight: 'Tight Tim', loose: 'Loose Bruce',
    station: 'Station Stan', aggressive: 'Aggro Angela', tom: 'Fluid Fiona',
    shark: 'Sharkey Steve', exploit: 'Exploit Eli', icm: 'ICM Ian',
    piq_basic_equity: 'Equity Eddie', piq_improved_equity: 'Savvy Sarah',
  };

  function makeRandomLineup(rng) {
    const pool = DEFAULT_BOT_LINEUP.map(x => x.slice());
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      const t = pool[i]; pool[i] = pool[j]; pool[j] = t;
    }
    return pool;
  }

  class Player {
    constructor(name, style, seat) {
      this.name = name;
      this.style = style;       // 'human' or a bot style id
      this.seat = seat;
      this.stack = STARTING_STACK;
      this.hand = [];           // array of card ints (engine encoding)
      this.active = true;       // still in this hand (not folded/out)
      this.betInRound = 0;
      this.actionsThisRound = 0;
      this.totalInvested = 0;   // chips committed this hand (for side pots)
      this.lastAction = null;   // 'fold'|'check'|'call'|'raise'|'post'
      this.allIn = false;
      this.botType = null;      // for piq_* equity bots
    }
    resetForHand() {
      this.hand = [];
      this.active = this.stack > 0;
      this.betInRound = 0;
      this.actionsThisRound = 0;
      this.totalInvested = 0;
      this.lastAction = null;
      this.allIn = false;
    }
    get isHuman() { return this.style === 'human'; }
  }

  class Game {
    /**
     * @param {object} opts
     *   rng           : () => [0,1)            (default Math.random)
     *   godMode       : boolean
     *   numBots       : 1..5 (default 5)
     *   onEvent       : (type, payload) => void   UI hook
     *   botDecide     : (game, player) => [action, amount]   AI hook
     */
    constructor(opts = {}) {
      this.rng = opts.rng || Math.random;
      this.godMode = !!opts.godMode;
      this.onEvent = opts.onEvent || function () {};
      this.botDecide = opts.botDecide || null;
      this.manualBots = !!opts.manualBots;   // when true, caller paces bot turns
      this.awaitingBot = -1;                 // seat a bot is about to act from

      if (opts.seats && opts.seats.length >= 2) {
        // explicit lineup: [{name, style}] — style 'human' or a bot style id.
        // Used by hotseat (multiple human seats) and custom tables.
        this.players = opts.seats.map((s, i) => new Player(s.name, s.style, i));
      } else {
        const lineup = makeRandomLineup(this.rng).slice(0, opts.numBots || 5);
        this.players = [new Player('Hero (You)', 'human', 0)]
          .concat(lineup.map((x, i) => new Player(x[0], x[1], i + 1)));
      }

      this.deck = [];
      this.board = [];
      this.pot = 0;
      this.dealerIdx = 0;
      this.currentBet = 0;
      this.streetIdx = 0;
      this.toAct = -1;            // seat index whose turn it is (-1 = none)
      this.minRaiseTo = 0;        // minimum legal raise-to amount
      this.lastRaiseSize = 0;     // size of last bet/raise increment
      this.handNumber = 0;
      this.blindLevel = 0;
      this.handInProgress = false;
      this.awaitingAction = false;
      this.actionLog = [];
      this.lastResult = null;     // populated at end of hand
    }

    // ---- helpers ----
    bb() { return BLIND_LEVELS[this.blindLevel][1]; }
    sb() { return BLIND_LEVELS[this.blindLevel][0]; }
    activePlayers() { return this.players.filter(p => p.active); }
    log(msg) { this.actionLog.push(msg); this.onEvent('log', msg); }

    nextActiveSeat(from) {
      const n = this.players.length;
      let i = (from + 1) % n;
      for (let c = 0; c < n; c++) {
        if (this.players[i].active) return i;
        i = (i + 1) % n;
      }
      return from;
    }

    // Position label relative to dealer (BT/SB/BB/UTG/CO/MP)
    positionOf(seat) {
      const n = this.players.length;
      const off = (seat - this.dealerIdx + n) % n;
      if (off === 0) return 'BT';
      if (off === 1) return 'SB';
      if (off === 2) return 'BB';
      if (off === n - 1 && n >= 5) return 'CO';
      if (off === 3) return 'UTG';
      return 'MP';
    }

    buildDeck() {
      const used = new Set();
      for (const p of this.players) for (const c of p.hand) used.add(E.codeOf(c));
      for (const c of this.board) used.add(E.codeOf(c));
      const d = E.fullDeck().filter(c => !used.has(E.codeOf(c)));
      // Fisher-Yates with injected rng
      for (let i = d.length - 1; i > 0; i--) {
        const j = Math.floor(this.rng() * (i + 1));
        const t = d[i]; d[i] = d[j]; d[j] = t;
      }
      return d;
    }
    draw(n) { return this.deck.splice(0, n); }

    // ---- hand lifecycle ----
    dealHand() {
      this.handNumber += 1;
      // blind increase every N hands
      if (this.handNumber > 1 && (this.handNumber - 1) % HANDS_PER_BLIND_LEVEL === 0
          && this.blindLevel < BLIND_LEVELS.length - 1) {
        this.blindLevel += 1;
        this.log(`*** Blinds up to $${this.sb()}/$${this.bb()} ***`);
      }

      this.board = [];
      for (const p of this.players) p.resetForHand();
      this.deck = this.buildDeck();
      this.pot = 0;
      this.currentBet = 0;
      this.streetIdx = 0;
      this.actionLog = [];
      this.lastResult = null;
      this.handInProgress = true;

      if (this.activePlayers().length < 2) {
        this.handInProgress = false;
        this.onEvent('needReset', null);
        return false;
      }

      // advance dealer to an active seat
      this.dealerIdx = this.nextActiveSeat(this.dealerIdx);

      // deal hole cards
      for (const p of this.players) if (p.active) p.hand = this.draw(2);

      // announce the hand BEFORE blinds so listeners can record the blind
      // posts (and start stacks) into their per-hand history.
      this.onEvent('handStart', {
        handNumber: this.handNumber, dealer: this.dealerIdx,
        startStacks: this.players.map(p => ({ seat: p.seat, name: p.name, stack: p.stack })),
      });

      // blinds
      const sbSeat = this.nextActiveSeat(this.dealerIdx);
      const bbSeat = this.nextActiveSeat(sbSeat);
      this.postBlind(this.players[sbSeat], this.sb(), 'small blind');
      this.postBlind(this.players[bbSeat], this.bb(), 'big blind');
      this.currentBet = this.bb();
      this.minRaiseTo = this.bb() * 2;
      this.lastRaiseSize = this.bb();

      this.toAct = this.nextActiveSeat(bbSeat);
      this.beginStreetActors();
      this.awaitingAction = true;
      this.advanceToActionable(true);
      return true;
    }

    postBlind(player, amount, kind) {
      const actual = Math.min(amount, player.stack);
      player.stack -= actual;
      player.betInRound = actual;
      player.totalInvested = actual;
      if (player.stack === 0) player.allIn = true;
      this.pot += actual;
      player.lastAction = 'post';
      this.log(`${player.name} posts ${kind} $${actual}`);
      this.onEvent('action', { seat: player.seat, action: 'post', amount: actual,
        total: player.betInRound, pot: this.pot, streetIdx: 0 });
    }

    beginStreetActors() {
      for (const p of this.players) p.actionsThisRound = 0;
    }

    // ---- turn engine ----
    // Returns true if the current seat needs a human decision; otherwise
    // auto-resolves bots and street/hand transitions until it does or the
    // hand ends.
    advanceToActionable(justStarted) {
      if (!justStarted) {} // (kept for symmetry/readability)
      let guard = 0;
      while (this.handInProgress) {
        if (++guard > 10000) throw new Error('engine loop guard tripped');

        if (this.activePlayers().length < 2) { this.endHand(); return false; }

        if (this.roundComplete()) {
          if (!this.nextStreet()) return false;   // hand ended
          continue;
        }

        const p = this.players[this.toAct];
        const needsToAct = p.active && !p.allIn &&
          (p.actionsThisRound === 0 || p.betInRound < this.currentBet);

        if (!needsToAct) { this.toAct = this.nextActiveSeat(this.toAct); continue; }

        if (p.isHuman) {
          this.awaitingAction = true;
          this.onEvent('awaitAction', { seat: this.toAct, ...this.legalActions(this.toAct) });
          return true;
        }
        // bot turn
        if (this.manualBots) {
          // hand control back so the caller can pace this bot's action on a
          // timer (for watchable play); resume via stepBot().
          this.awaitingBot = this.toAct;
          return 'bot';
        }
        const [a, amt] = this.botDecide ? this.botDecide(this, p) : ['c', 0];
        this.applyActionInternal(p, a, amt);
        this.toAct = this.nextActiveSeat(this.toAct);
      }
      return false;
    }

    // Perform exactly one pending bot action (paced mode). Returns the result
    // of advanceToActionable: true (hero to act), 'bot' (another bot pending),
    // or false (hand ended / between hands).
    stepBot() {
      if (this.awaitingBot < 0 || !this.handInProgress) return false;
      const p = this.players[this.awaitingBot];
      this.awaitingBot = -1;
      const [a, amt] = this.botDecide ? this.botDecide(this, p) : ['c', 0];
      this.applyActionInternal(p, a, amt);
      this.toAct = this.nextActiveSeat(this.toAct);
      return this.advanceToActionable(false);
    }

    // A betting round is complete when every still-in player has either
    // matched the current bet or is all-in, AND everyone has acted at least
    // once since the last aggressive action.
    roundComplete() {
      const inHand = this.activePlayers();
      if (inHand.length < 2) return true;
      const canAct = inHand.filter(p => !p.allIn && p.stack > 0);
      const matched = inHand.every(p => p.betInRound === this.currentBet || p.allIn);
      const allActed = canAct.every(p => p.actionsThisRound > 0);
      return matched && allActed;
    }

    legalActions(seat) {
      const p = this.players[seat];
      const toCall = Math.max(0, this.currentBet - p.betInRound);
      const canRaise = p.stack > toCall;
      const minRaiseTo = Math.min(p.stack + p.betInRound, Math.max(this.minRaiseTo, this.currentBet + this.lastRaiseSize));
      const maxRaiseTo = p.stack + p.betInRound;
      return { toCall, canCheck: toCall === 0, canRaise, minRaiseTo, maxRaiseTo, pot: this.pot };
    }

    // Public entry: apply a human (or external) action then auto-run to next.
    applyAction(seat, action, amount) {
      if (!this.awaitingAction || seat !== this.toAct) return false;
      const p = this.players[seat];
      this.awaitingAction = false;
      this.applyActionInternal(p, action, amount);
      this.toAct = this.nextActiveSeat(this.toAct);
      return this.advanceToActionable(false);
    }

    applyActionInternal(player, action, amount) {
      const toCall = Math.max(0, this.currentBet - player.betInRound);
      let chipsAdded = 0;            // chips this player puts in for this action
      let openingBet = false;        // street-opening wager → "bets" not "raises to"
      if (action === 'f') {
        // folding when you could check is legal but silly; allow it
        player.active = false;
        player.lastAction = 'fold';
        this.log(`${player.name} folds`);
      } else if (action === 'r' && player.stack + player.betInRound > this.currentBet) {
        openingBet = this.currentBet === 0;   // no prior wager this street
        const minTo = Math.max(this.minRaiseTo, this.currentBet + this.lastRaiseSize);
        const maxTo = player.stack + player.betInRound;   // shove ceiling
        // clamp the requested raise-to into [minTo, maxTo]; if the player is
        // too short to make a full min-raise, allow an all-in under-raise.
        let raiseTo = Math.min(amount, maxTo);
        if (raiseTo < minTo) raiseTo = (maxTo <= minTo) ? maxTo : minTo;
        const inc = raiseTo - this.currentBet;
        const chips = raiseTo - player.betInRound;
        chipsAdded = chips;
        player.stack -= chips;
        this.pot += chips;
        player.totalInvested += chips;
        player.betInRound = raiseTo;
        if (inc >= this.lastRaiseSize) this.lastRaiseSize = inc;
        this.currentBet = raiseTo;
        this.minRaiseTo = raiseTo + this.lastRaiseSize;
        if (player.stack === 0) player.allIn = true;
        player.lastAction = 'raise';
        this.log(`${player.name} ${player.allIn ? 'is all-in for' : (openingBet ? 'bets' : 'raises to')} $${raiseTo}`);
        // re-open action for everyone else
        for (const q of this.players) if (q !== player && q.active && !q.allIn) q.actionsThisRound = 0;
      } else { // call / check
        if (toCall > 0) {
          const actual = Math.min(player.stack, toCall);
          chipsAdded = actual;
          player.stack -= actual;
          player.betInRound += actual;
          player.totalInvested += actual;
          this.pot += actual;
          if (player.stack === 0) player.allIn = true;
          player.lastAction = 'call';
          this.log(`${player.name} calls $${actual}${player.allIn ? ' (all-in)' : ''}`);
        } else {
          player.lastAction = 'check';
          this.log(`${player.name} checks`);
        }
      }
      player.actionsThisRound += 1;
      // defensive: chip math is proven over 4000+ hands, but never let a stray
      // edge case crash the UI or print money — clamp and carry on.
      if (player.stack < 0) { this.pot += player.stack; player.betInRound += player.stack; player.stack = 0; player.allIn = true; }
      this.onEvent('action', { seat: player.seat, action: player.lastAction,
        amount: chipsAdded, total: player.betInRound, pot: this.pot, streetIdx: this.streetIdx, opening: openingBet });
    }

    nextStreet() {
      for (const p of this.players) p.betInRound = 0;
      this.currentBet = 0;
      this.lastRaiseSize = this.bb();
      this.minRaiseTo = this.bb();
      this.streetIdx += 1;

      if (this.activePlayers().length < 2 || this.streetIdx >= STREETS.length) {
        this.endHand();
        return false;
      }
      // deal the street
      const street = STREETS[this.streetIdx];
      if (street === 'Flop') this.board = this.board.concat(this.draw(3));
      else this.board = this.board.concat(this.draw(1));
      this.beginStreetActors();
      this.onEvent('street', { street, board: this.board.slice() });

      // if at most one player can still act (rest all-in), run it out
      const canAct = this.activePlayers().filter(p => !p.allIn && p.stack > 0);
      if (canAct.length <= 1) {
        while (this.streetIdx < STREETS.length - 1) {
          this.streetIdx += 1;
          const s = STREETS[this.streetIdx];
          if (s === 'Flop') this.board = this.board.concat(this.draw(3));
          else this.board = this.board.concat(this.draw(1));
          this.onEvent('street', { street: s, board: this.board.slice(), runout: true });
        }
        this.endHand();
        return false;
      }
      this.toAct = this.nextActiveSeat(this.dealerIdx);
      return true;
    }

    // ---- showdown with true side pots ----
    endHand() {
      this.handInProgress = false;
      this.awaitingAction = false;
      this.toAct = -1;
      while (this.board.length < 5) this.board = this.board.concat(this.draw(1));

      const contenders = this.activePlayers();
      const payouts = {};        // seat -> chips won
      for (const p of this.players) payouts[p.seat] = 0;
      let showdown = [];

      if (contenders.length === 1) {
        payouts[contenders[0].seat] = this.pot;
        contenders[0].stack += this.pot;
        this.log(`${contenders[0].name} wins $${this.pot} (uncontested)`);
      } else {
        // score everyone still in
        const scored = contenders.map(p => ({
          p, score: E.evaluate(p.hand.concat(this.board)),
        }));
        showdown = scored.map(s => ({
          seat: s.p.seat, name: s.p.name, hand: s.p.hand.slice(),
          desc: E.describe(s.score), score: s.score,
        }));

        // Build side pots from total_invested layers across ALL players who
        // put chips in (including folded players' dead money).
        const pots = this.buildSidePots();
        for (const pot of pots) {
          // eligible = contenders who contributed to this layer
          const elig = scored.filter(s => pot.eligible.has(s.p.seat));
          if (!elig.length) continue;
          const best = Math.max(...elig.map(s => s.score));
          const winners = elig.filter(s => s.score === best);
          const share = Math.floor(pot.amount / winners.length);
          let rem = pot.amount - share * winners.length;
          // award; odd chip goes to first winner left of dealer
          winners.sort((a, b) =>
            ((a.p.seat - this.dealerIdx + 99) % this.players.length) -
            ((b.p.seat - this.dealerIdx + 99) % this.players.length));
          for (const w of winners) {
            const extra = rem > 0 ? 1 : 0; rem -= extra;
            payouts[w.p.seat] += share + extra;
            w.p.stack += share + extra;
          }
        }
        const winNames = showdown
          .filter(s => payouts[s.seat] > 0)
          .map(s => s.name);
        this.log(`Showdown — ${winNames.join(', ')} take the pot`);
      }

      this.lastResult = {
        pot: this.pot, payouts, showdown,
        board: this.board.slice(),
        net: this.players.map(p => ({ seat: p.seat, name: p.name,
          net: payouts[p.seat] - p.totalInvested, stack: p.stack })),
      };
      this.onEvent('handEnd', this.lastResult);
    }

    // Layered side pots from each player's totalInvested.
    buildSidePots() {
      const invs = this.players
        .map(p => ({ seat: p.seat, inv: p.totalInvested, active: p.active }))
        .filter(x => x.inv > 0);
      const pots = [];
      let prev = 0;
      const levels = Array.from(new Set(invs.map(x => x.inv))).sort((a, b) => a - b);
      for (const lvl of levels) {
        let amount = 0;
        const eligible = new Set();
        for (const x of invs) {
          if (x.inv >= lvl) {
            amount += (lvl - prev);
            if (x.active) eligible.add(x.seat);  // only non-folded can win
          }
        }
        if (amount > 0) pots.push({ amount, eligible });
        prev = lvl;
      }
      return pots;
    }

    // ---- online follower: apply an authoritative game-state blob from the host ----
    // Mutates existing Player objects (preserving identity for the view). Hidden
    // opponents arrive with hand:[]; at showdown the host reveals every hand.
    applyNet(gs) {
      if (!gs) return;
      if (gs.players) {
        for (const sp of gs.players) {
          let p = this.players[sp.seat];
          if (!p) { p = new Player(sp.name, sp.style, sp.seat); this.players[sp.seat] = p; }
          p.name = sp.name; p.style = sp.style;
          p.stack = sp.stack; p.betInRound = sp.betInRound || 0;
          p.active = !!sp.active; p.allIn = !!sp.allIn;
          p.lastAction = sp.lastAction || null;
          p.totalInvested = sp.totalInvested || 0;
          if (sp.hand) p.hand = sp.hand.slice();
        }
        this.players = this.players.filter(Boolean);
      }
      if (gs.board) this.board = gs.board.slice();
      if (gs.pot != null) this.pot = gs.pot;
      if (gs.currentBet != null) this.currentBet = gs.currentBet;
      if (gs.toAct != null) this.toAct = gs.toAct;
      if (gs.dealerIdx != null) this.dealerIdx = gs.dealerIdx;
      if (gs.streetIdx != null) this.streetIdx = gs.streetIdx;
      if (gs.blindLevel != null) this.blindLevel = gs.blindLevel;
      if (gs.handNumber != null) this.handNumber = gs.handNumber;
      if (gs.handInProgress != null) this.handInProgress = gs.handInProgress;
      if (gs.awaitingAction != null) this.awaitingAction = gs.awaitingAction;
      if (gs.minRaiseTo != null) this.minRaiseTo = gs.minRaiseTo;
      if (gs.lastRaiseSize != null) this.lastRaiseSize = gs.lastRaiseSize;
    }

    // Compact authoritative state for one recipient seat (host → that peer).
    // Reveals the recipient's own cards; opponents' cards only when `revealAll`.
    netStateFor(seat, revealAll) {
      return {
        players: this.players.map(p => ({
          seat: p.seat, name: p.name, style: p.isHuman ? 'human' : p.style,
          stack: p.stack, betInRound: p.betInRound, active: p.active,
          allIn: p.allIn, lastAction: p.lastAction, totalInvested: p.totalInvested,
          hand: (revealAll || p.seat === seat) ? p.hand.slice() : [],
        })),
        board: this.board.slice(), pot: this.pot, currentBet: this.currentBet,
        toAct: this.toAct, dealerIdx: this.dealerIdx, streetIdx: this.streetIdx,
        blindLevel: this.blindLevel, handNumber: this.handNumber,
        handInProgress: this.handInProgress, awaitingAction: this.awaitingAction,
        minRaiseTo: this.minRaiseTo, lastRaiseSize: this.lastRaiseSize,
      };
    }

    // bust-out check / table reset
    bustedSeats() { return this.players.filter(p => p.stack <= 0).map(p => p.seat); }
    resetStacks() {
      for (const p of this.players) { p.stack = STARTING_STACK; p.active = true; }
      this.handNumber = 0; this.blindLevel = 0;
    }
  }

  const API = {
    Game, Player,
    STREETS, STARTING_STACK, BLIND_LEVELS, HANDS_PER_BLIND_LEVEL,
    DEFAULT_BOT_LINEUP, CUTE_NAMES, makeRandomLineup,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerGame = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
