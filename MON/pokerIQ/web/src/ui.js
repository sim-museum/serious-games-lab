/*
 * PokerIQ — table UI + controller. Renders the poker table (DOM/CSS, no canvas
 * dependency) and drives the Game engine one human action at a time, auto-
 * stepping bot turns with a small delay so play is watchable.
 *
 * Split into:
 *   Controller — UI-agnostic glue between Game/Bots/Analytics and the view.
 *                Fully unit-testable under jsdom (test/test_ui.js).
 *   View       — DOM construction + render(state). Pure function of state.
 *
 * Depends on PokerEngine, PokerGame, PokerBots, PokerAnalytics globals.
 */
(function (root) {
  'use strict';
  const isNode = (typeof require !== 'undefined' && typeof module !== 'undefined' && module.exports);
  const E = isNode ? require('./engine.js') : root.PokerEngine;
  const PG = isNode ? require('./game.js') : root.PokerGame;
  const PB = isNode ? require('./bots.js') : root.PokerBots;
  const PA = isNode ? require('./analytics.js') : root.PokerAnalytics;
  // resolved lazily so this loads under Node tests (require) and in the browser (globals)
  const getLog = () => isNode ? require('./logfile.js') : root.PokerLog;
  const getToMLogic = () => isNode ? require('./tomlogic.js') : root.PokerToMLogic;
  const getToM = () => isNode ? require('./tom.js') : root.PokerToM;

  // ---------------- Controller ----------------
  class Controller {
    constructor(opts = {}) {
      this.opts = opts;
      this.botDelayMs = opts.botDelayMs != null ? opts.botDelayMs : 650;
      this.godMode = !!opts.godMode;
      this.showTells = !!opts.showTells;
      this.onRender = opts.onRender || function () {};
      this.onHandEnd = opts.onHandEnd || function () {};
      this.timer = opts.timer || ((fn, ms) => setTimeout(fn, ms));

      this.stats = new PA.SessionStats(2);
      this.oppModel = new PA.OpponentModel();
      this.tilt = new PA.TiltDetector();

      this.events = [];           // recent log lines for the feed
      this.handResult = null;
      this.heroEquity = null;     // cached live equity for hero readout
      this.lastStreet = 'Preflop';
      this.history = null;        // structured per-hand history (building)
      this.lastHistory = null;    // last completed hand's history (for summary)
      this.training = !!opts.training;   // ToM training screen on/off
      this.tomTab = 'advisor';    // active ToM tab
      this.rangeMode = 'neutral'; // 'loose'(opps weak) | 'neutral' | 'tight'(opps strong)
      // exact-format session log (PyQt-compatible) for AI post-game analysis
      this.logbook = new (getLog()).LogBook();
      this.logStarted = false;
      this.tableStats = {};       // per-player cumulative counters
      this.holeStats = {};        // hero per-starting-hand class
      this.prevBlindLevel = 0;    // game.blindLevel starts at 0
      this.origPlayerCount = null;
      this.origBlinds = null;
      this.now = opts.now || (() => new Date());
      // Analytics (equity/advisor/[STATS]) must NOT consume the game's deck RNG
      // — otherwise computing them would perturb the actual deal/bot decisions.
      this.auxRng = opts.auxRng || Math.random;
      // hotseat (pass-and-play): >1 human seat on one device. `armed` gates the
      // reveal so the next player must tap "show my cards" before they see them.
      this.hotseat = false;
      this.humanSeats = new Set([0]);
      this.armed = true;
      // fold→spectator (God view) + assist flagging
      this.spectating = false;       // viewer folded, watching the rest
      this.specSnaps = [];           // per-street spectator snapshots
      this.specIdx = -1;             // -1 = live; else index into specSnaps
      this.handAssists = {};         // {playerName: Set(assist)} used while still in hand

      this.game = new PG.Game({
        rng: opts.rng || Math.random,
        godMode: this.godMode,
        manualBots: true,                  // controller paces bot turns
        botDecide: (g, p) => PB.decide(g, p),
        onEvent: (t, payload) => this.onGameEvent(t, payload),
      });
    }

    streetName() { return PG.STREETS[this.game.streetIdx] || 'Showdown'; }

    // is a human seat currently to act?
    humanToAct() { return this.game.awaitingAction && this.humanSeats.has(this.game.toAct); }
    // the seat to render as "the viewer/hero" — the acting human in hotseat,
    // else seat 0. All hero-perspective analysis keys off this.
    heroSeat() { return this.humanToAct() ? this.game.toAct : 0; }
    // hotseat privacy gate: a human must arm before their cards are shown.
    // Suppressed while a just-folded player is mid-review (they pass first).
    get passGate() { return this.hotseat && this.humanToAct() && !this.armed && !this.spectating; }
    arm() { this.armed = true; this.stats.actionStarted(); this.render(); }

    // ---- assists: God/Tells/Training used while still in the hand get flagged ----
    flagAssist(name) {
      const p = this.game.players[this.heroSeat()];
      // only flag when the viewer is still IN the hand (folding first is legit)
      if (this.game.handInProgress && p && p.active && !this.spectating) {
        (this.handAssists[p.name] || (this.handAssists[p.name] = new Set())).add(name);
      }
    }
    // Manual God peek pre-fold is only allowed when there are no other human
    // players (you can't peek at other humans' cards mid-hand). After you fold,
    // the spectator God-view is always available regardless.
    canUseGod() { return this.humanSeats.size <= 1; }
    toggleGod() {
      if (!this.godMode && !this.canUseGod()) return;   // blocked: humans at the table
      this.godMode = !this.godMode;
      if (this.godMode) this.flagAssist('God Mode');
      this.render();
    }
    toggleTells() { this.showTells = !this.showTells; if (this.showTells) this.flagAssist('Show Tells'); this.render(); }
    toggleTraining() { this.training = !this.training; if (this.training) this.flagAssist('Theory of Mind'); this.render(); }
    assistFlags() {
      return Object.keys(this.handAssists).map(n => ({ name: n, assists: [...this.handAssists[n]] }));
    }

    // ---- fold → God-view spectator mode ----
    // EVERY human fold gets a God-view review. Single-player / bots-only: watch
    // the run-out live to showdown. Hotseat with another human still to act:
    // review the current state, then "Pass device →" to continue.
    maybeEnterSpectator(foldedSeat) {
      if (this.spectating) return;
      if (!this.humanSeats.has(foldedSeat)) return;          // a bot folded
      if (!this.game.handInProgress) return;
      if (this.game.activePlayers().length < 2) return;       // hand's over anyway
      this.spectating = true; this.specIdx = -1; this.specSnaps = [];
      this.captureSpecSnapshot();
    }
    captureSpecSnapshot() {
      if (!this.spectating) return;
      this.specSnaps.push({ street: this.streetName(), board: this.game.board.slice(), table: this.specTable() });
    }
    // leave the review. `pass` (hotseat) resumes the hand → next player's gate;
    // otherwise (single-player live watch) the in-flight run-out just continues.
    exitSpectator(pass) { this.spectating = false; this.specIdx = -1; if (pass) this.pump(); else this.render(); }
    specPrev() { const n = this.specSnaps.length; if (!n) return; this.specIdx = this.specIdx < 0 ? n - 2 : this.specIdx - 1; if (this.specIdx < 0) this.specIdx = 0; this.render(); }
    specNext() { const n = this.specSnaps.length; if (!n) return; if (this.specIdx < 0) return; this.specIdx += 1; if (this.specIdx >= n - 1) this.specIdx = -1; this.render(); }

    // spectator panel payload — live state, or a navigated past-street snapshot
    spectatorData() {
      const live = this.specIdx < 0 || this.specIdx >= this.specSnaps.length;
      const snap = live ? { street: this.streetName(), board: this.game.board.slice(), table: this.specTable() }
        : this.specSnaps[this.specIdx];
      // in hotseat, if another human still has to act, the folder reviews then
      // hands off ("Pass device →"); otherwise it's a live watch ("Close View").
      const humanLeft = this.game.activePlayers().some(p => this.humanSeats.has(p.seat));
      return {
        street: snap.street, board: snap.board, table: snap.table,
        pot: this.game.pot, live, passMode: this.hotseat && humanLeft,
        canPrev: this.specSnaps.length > 1 && (live || this.specIdx > 0),
        canNext: !live,
        idx: live ? this.specSnaps.length - 1 : this.specIdx,
        count: this.specSnaps.length,
      };
    }

    // per-player equity table for the spectator panel:
    //  Real    = true (god) multiway equity over actual hands
    //  Thinking= each active player's equity vs the OTHERS' estimated ranges
    //  PotOdds = price each player faces right now
    specTable() {
      const T = getToMLogic(), g = this.game, board = g.board;
      const active = g.activePlayers();
      let real = [];
      if (active.length >= 2) real = E.equityMultiway(active.map(p => p.hand), board, { iterations: 400, rng: this.auxRng });
      const realBy = {}; active.forEach((p, i) => realBy[p.seat] = real[i] != null ? real[i] : 0);
      return g.players.map(p => {
        if (!p.active) return { name: p.name, seat: p.seat, folded: true };
        const others = active.filter(q => q !== p);
        const ranges = others.map(q => T.estimateRange(q.style, this.rangeMode, this.actionTagsFor(q.seat), board).range);
        const thinking = ranges.length ? T.equityVsRanges(p.hand, board, ranges, { iterations: 250, rng: this.auxRng }) : null;
        const toCall = Math.max(0, g.currentBet - p.betInRound);
        const potOdds = (g.pot + toCall) > 0 && toCall > 0 ? toCall / (g.pot + toCall) : 0;
        const realEq = realBy[p.seat];
        const evPos = toCall > 0 ? (realEq >= potOdds) : (realEq >= 0.5);
        return { name: p.name, seat: p.seat, folded: false, real: realEq, thinking: thinking != null ? thinking : realEq, potOdds, facing: toCall > 0, evPos };
      });
    }

    newHand() {
      this.handResult = null;
      this.events = [];
      this.heroEquity = null;
      if (this.hotseat) this.armed = false;   // first player must arm
      // bust-out → offer reset
      if (this.game.players.filter(p => p.stack > 0).length < 2) this.game.resetStacks();
      this.stats.bbAmount = this.game.bb();
      const ok = this.game.dealHand();
      if (!ok) { this.game.resetStacks(); this.game.dealHand(); }
      for (const p of this.game.players) if (p.style !== 'human') this.oppModel.recordHand(p.name);
      this.refreshHeroEquity();
      this.render();
      this.pump();
    }

    // (re)configure the table: specs = [{name, style}] (style 'human' or bot id).
    // Enables hotseat when more than one seat is human.
    setupPlayers(specs) {
      this.humanSeats = new Set(specs.map((s, i) => s.style === 'human' ? i : -1).filter(i => i >= 0));
      this.hotseat = this.humanSeats.size > 1;
      this.game = new PG.Game({
        rng: this.opts.rng || Math.random, godMode: this.godMode, manualBots: true,
        seats: specs, botDecide: (g, p) => PB.decide(g, p),
        onEvent: (t, payload) => this.onGameEvent(t, payload),
      });
      this.prevBlindLevel = 0;
      this.armed = !this.hotseat;
      this.newHand();
    }

    onGameEvent(type, payload) {
      if (type === 'handStart') {
        this.history = {
          handNumber: payload.handNumber,
          startStacks: payload.startStacks,
          // all hole cards (god view) for the hand summary
          holeCards: this.game.players.filter(p => p.hand.length).map(p => ({ seat: p.seat, name: p.name, cards: p.hand.slice() })),
          streets: [{ name: 'Preflop', board: [], actions: [] }],
        };
        this.spectating = false; this.specSnaps = []; this.specIdx = -1; this.handAssists = {};
        this.logHandStart(payload);
      } else if (type === 'log') {
        this.pushEvent(payload);
      } else if (type === 'street') {
        this.lastStreet = payload.street; this.heroEquity = null; this.refreshHeroEquity();
        if (this.history) this.history.streets.push({ name: payload.street, board: payload.board.slice(), actions: [] });
        this.logStreet(payload);
        if (this.spectating) this.captureSpecSnapshot();
      } else if (type === 'action') {
        this.recordHistoryAction(payload);
        this.trackOppAction(payload);
        this.logAction(payload);
      } else if (type === 'handEnd') {
        if (this.history) { this.history.result = payload; this.history.assists = this.assistFlags(); this.lastHistory = this.history; }
        this.spectating = false;
        this.logHandEnd(payload);
        this.onHandComplete(payload);
      }
    }

    // ---- exact-format log writers (mirror pokerIQ.py) ----
    fmtCards(cards) { return cards.map(c => E.cardToStr(c)).join(' '); }   // format_cards
    pad2(n) { return String(n).padStart(2, '0'); }
    timeStr() { const d = this.now(); return `${this.pad2(d.getHours())}:${this.pad2(d.getMinutes())}:${this.pad2(d.getSeconds())}`; }
    dateStr() { const d = this.now(); return `${d.getFullYear()}-${this.pad2(d.getMonth() + 1)}-${this.pad2(d.getDate())} ${this.timeStr()}`; }

    logHandStart(payload) {
      const g = this.game, lb = this.logbook;
      if (!this.logStarted) { lb.sessionHeader(this.dateStr()); this.logStarted = true; }
      lb.newHand(payload.handNumber, this.timeStr());
      // blind increase line (when the level just advanced)
      if (g.blindLevel > this.prevBlindLevel) lb.blindIncrease(g.sb(), g.bb());
      this.prevBlindLevel = g.blindLevel;
      // GAME STATUS, first hand only
      if (!lb.gameStatusLogged) {
        const alive = g.players.filter(p => p.stack > 0).length;
        if (this.origPlayerCount == null) { this.origPlayerCount = alive; this.origBlinds = [g.sb(), g.bb()]; }
        const inc = PG.HANDS_PER_BLIND_LEVEL - (g.handNumber % PG.HANDS_PER_BLIND_LEVEL);
        const nextIn = inc === PG.HANDS_PER_BLIND_LEVEL ? 0 : inc;
        const nextMarker = g.blindLevel < PG.BLIND_LEVELS.length - 1 ? `Hand #${g.handNumber + nextIn}` : 'Max blinds reached';
        lb.gameStatus({
          mode: 'PokerIQ Local', startingChips: PG.STARTING_STACK, handsDealt: g.handNumber,
          nextBlind: nextMarker, origPlayers: this.origPlayerCount, curPlayers: alive,
          origSb: this.origBlinds[0], origBb: this.origBlinds[1], curSb: g.sb(), curBb: g.bb(),
        });
        lb.gameStatusLogged = true;
      }
      // Dealer + all active hole cards (the log is a private god-view record)
      const dealerName = g.players[g.dealerIdx].name;
      const hole = g.activePlayers().map(p => ({ name: p.name, cards: this.fmtCards(p.hand) }));
      lb.dealerAndHole(dealerName, hole);
    }

    logAction(payload) {
      const lb = this.logbook, name = this.game.players[payload.seat].name;
      switch (payload.action) {
        case 'post': lb.post(name, payload.amount); break;
        case 'fold': lb.fold(name); break;
        case 'check': lb.check(name); break;
        case 'call': lb.call(name, payload.amount); break;
        case 'raise': lb.raise(name, payload.total); break;
      }
    }

    logStreet(payload) {
      const g = this.game;
      // [STATS] — true (god-view) equity of every active player vs the field,
      // computed over actual hands at the freshly-dealt board.
      const active = g.activePlayers();
      let eq = [];
      if (active.length >= 2) eq = E.equityMultiway(active.map(p => p.hand), payload.board, { iterations: 300, rng: this.auxRng });
      const rows = active.map((p, i) => {
        const toCall = Math.max(0, g.currentBet - p.betInRound);
        const potOdds = (g.pot + toCall) > 0 ? toCall / (g.pot + toCall) : 0;
        return { name: p.name, cards: this.fmtCards(p.hand), equity: eq[i] != null ? eq[i] : 0, potOdds };
      });
      this.logbook.street(payload.street, rows, this.fmtCards(payload.board));
    }

    logHandEnd(result) {
      const g = this.game, lb = this.logbook;
      const winners = result.net.filter(n => result.payouts[n.seat] > 0);
      if (result.showdown.length > 1) {
        const ordered = result.showdown.slice().sort((a, b) => b.score - a.score);
        lb.showdownResults(ordered.map(s => ({ name: s.name, cat: E.categoryOf(s.score) })));
        lb.winnerShowdown(winners.map(w => ({ name: w.name, net: w.net })));
      } else if (winners.length) {
        lb.winnerUncontested(winners[0].name, winners[0].net);
      }
      lb.finalStacks(g.players.map(p => ({ name: p.name, stack: p.stack })));
      lb.gainLoss(result.net.map(n => ({ name: n.name, change: n.net })));
      this.updateLogStats(result);
    }

    // cumulative table + hero hole-card stats for the session summary
    updateLogStats(result) {
      const g = this.game;
      const showdownSeats = new Set(result.showdown.map(s => s.seat));
      for (const p of g.players) {
        const t = this.tableStats[p.name] || (this.tableStats[p.name] = { name: p.name, handsPlayed: 0, handsWon: 0, showdownsSeen: 0, showdownsWon: 0, allIns: 0, stack: p.stack });
        t.handsPlayed += 1;
        t.stack = p.stack;
        if (p.allIn) t.allIns += 1;
        const won = result.payouts[p.seat] > 0;
        if (won) t.handsWon += 1;
        if (showdownSeats.has(p.seat)) { t.showdownsSeen += 1; if (won) t.showdownsWon += 1; }
      }
      // hero hole-card class
      const hero = g.players[0];
      if (hero.hand.length) {
        const cls = getToMLogic().handToKey(hero.hand) || '??';
        const h = this.holeStats[cls] || (this.holeStats[cls] = { cls, seen: 0, played: 0, won: 0, lost: 0, cashGained: 0, cashLost: 0, net: 0 });
        h.seen += 1;
        const net = (result.net.find(n => n.seat === 0) || { net: 0 }).net;
        if (hero.totalInvested > 0) h.played += 1;
        if (net > 0) { h.won += 1; h.cashGained += net; }
        else if (net < 0) { h.lost += 1; h.cashLost += Math.abs(net); }
        h.net += net;
      }
    }

    // assemble the full log text (live buffer + session summary) for download
    buildLogText() {
      const lb = new (getLog()).LogBook();
      lb.msgs = this.logbook.msgs.slice();   // copy the live buffer
      const holeStats = Object.values(this.holeStats).sort((a, b) => b.net - a.net || a.cls.localeCompare(b.cls));
      lb.sessionSummary({
        tableStats: this.game.players.map(p => this.tableStats[p.name] || { name: p.name, stack: p.stack, handsPlayed: 0, handsWon: 0, showdownsSeen: 0, showdownsWon: 0, allIns: 0 }),
        holeStats, endedStr: this.dateStr(),
      });
      return lb.text();
    }

    logFilename() { const d = this.now(); return `poker_log_${d.getFullYear()}${this.pad2(d.getMonth() + 1)}${this.pad2(d.getDate())}_${this.timeStr().replace(/:/g, '')}.txt`; }

    // ---- rich hand-summary data (computed lazily when the summary opens) ----
    // Per-street: every player's cards + best-hand description + true (god)
    // equity + vs-range equity + ahead/behind, plus that street's actions.
    buildSummaryData(h) {
      if (!h) return null;
      const T = getToMLogic();
      const hole = h.holeCards || [];
      const styleOf = seat => (this.game.players[seat] ? this.game.players[seat].style : 'loose');
      // which street each seat folded on (else they reached showdown)
      const foldStreet = {};
      h.streets.forEach((st, i) => st.actions.forEach(a => { if (a.action === 'fold' && foldStreet[a.seat] === undefined) foldStreet[a.seat] = i; }));
      const inAfter = (seat, S) => foldStreet[seat] === undefined || foldStreet[seat] > S;
      const actVerb = a => a.action === 'raise' ? (a.opening ? `Bets $${a.total}` : `Raises to $${a.total}`)
        : a.action === 'call' ? `Calls $${a.amount}` : a.action === 'check' ? 'Checks' : a.action === 'fold' ? 'Folds' : a.action;

      const panels = h.streets.map((st, S) => {
        const board = st.board || [];
        const contesting = hole.filter(x => inAfter(x.seat, S));
        const real = {};
        if (contesting.length >= 2) {
          const eq = E.equityMultiway(contesting.map(x => x.cards), board, { iterations: 600, rng: this.auxRng });
          contesting.forEach((x, i) => real[x.seat] = eq[i] != null ? eq[i] : 0);
        } else if (contesting.length === 1) real[contesting[0].seat] = 1;
        const maxReal = Math.max(0, ...Object.values(real));
        const rows = hole.map(x => {
          const folded = !inAfter(x.seat, S);
          const made = board.length >= 3 ? T.describeMadeHand(x.cards, board) : T.categorizePreflop(x.cards);
          if (folded) return { seat: x.seat, name: x.name, cards: x.cards, made, folded: true };
          const r = real[x.seat] != null ? real[x.seat] : 0;
          const others = contesting.filter(y => y.seat !== x.seat);
          const ranges = others.map(y => T.estimateRange(styleOf(y.seat), 'neutral', this.actionTagsFor(y.seat), board).range);
          let think = ranges.length ? T.equityVsRanges(x.cards, board, ranges, { iterations: 300, rng: this.auxRng }) : r;
          if (think == null) think = r;
          return { seat: x.seat, name: x.name, cards: x.cards, made, folded: false, real: r, thinking: think, ahead: r >= maxReal - 1e-9 };
        });
        const potAfter = st.actions.length ? st.actions[st.actions.length - 1].pot : 0;
        const actions = st.actions.filter(a => a.action !== 'post').map(a => ({ name: a.name, verb: actVerb(a) }));
        return { name: st.name, board, pot: potAfter, rows, actions };
      });

      const res = h.result || { net: [], showdown: [], payouts: {} };
      const startBy = {}; (h.startStacks || []).forEach(x => startBy[x.seat] = x.stack);
      const results = (res.net || []).map(n => ({ name: n.name, seat: n.seat, net: n.net, start: startBy[n.seat] != null ? startBy[n.seat] : n.stack, end: n.stack }));
      const humanSet = this.humanSeats;
      return {
        handNumber: h.handNumber,
        holeCards: hole.map(x => ({ name: x.name, cards: x.cards, category: T.categorizePreflop(x.cards) })),
        heldLines: hole.filter(x => humanSet.has(x.seat)).map(x => ({ name: x.name, held: T.handName(x.cards), cards: x.cards })),
        panels, results,
        finalBoard: res.board || (panels.length ? panels[panels.length - 1].board : []),
        humanSeats: [...humanSet],
      };
    }

    recordHistoryAction(payload) {
      if (!this.history) return;
      const cur = this.history.streets[this.history.streets.length - 1];
      const p = this.game.players[payload.seat];
      cur.actions.push({
        seat: payload.seat, name: p ? p.name : ('Seat ' + payload.seat),
        action: payload.action, amount: payload.amount || 0,
        total: payload.total || 0, pot: payload.pot, opening: !!payload.opening,
      });
    }

    pushEvent(msg) { this.events.push(msg); if (this.events.length > 8) this.events.shift(); }

    trackOppAction(payload) {
      const p = this.game.players[payload.seat];
      if (!p || p.isHuman) return;
      const street = this.streetName();
      const faced3bet = this.game.currentBet > 2 * this.game.bb();
      this.oppModel.recordAction(p.name, payload.action, street, faced3bet, street === 'River');
    }

    // hero's live equity vs the active field (used for readouts/EV)
    refreshHeroEquity() {
      const hero = this.game.players[this.heroSeat()];
      if (!hero.active || !hero.hand.length) { this.heroEquity = null; return; }
      const opps = this.game.activePlayers().filter(p => p !== hero).length || 1;
      this.heroEquity = E.equityVsRandom(hero.hand, this.game.board,
        { iterations: this.opts.equityIters || 600, opponents: opps, rng: this.auxRng });
    }

    // advisor readout for the hero panel
    advisor() {
      const hero = this.game.players[this.heroSeat()];
      if (!hero.active || !hero.hand.length) return null;
      const g = this.game;
      const toCall = Math.max(0, g.currentBet - hero.betInRound);
      const potOdds = (g.pot + toCall) > 0 ? toCall / (g.pot + toCall) : 0;
      const eq = this.heroEquity != null ? this.heroEquity : 0;
      const ctx = {
        pot: g.pot, currentBet: g.currentBet, betInRound: hero.betInRound,
        board: g.board.length, bb: g.bb(), playerStack: hero.stack,
        oppStacks: g.activePlayers().filter(p => p !== hero).map(p => p.stack),
      };
      const evCall = PA.heroActionEV(ctx, 'c', eq, 0);
      const evRaise = PA.heroActionEV(ctx, 'r', eq, Math.floor(g.pot * 0.66));
      const board = PA.classifyBoard(g.board);
      return {
        equity: eq, potOdds, toCall,
        evFold: 0, evCall, evRaise,
        board, posLabel: g.positionOf(this.heroSeat()),
        verdict: this.verdict(eq, potOdds, evCall, evRaise, toCall),
      };
    }

    verdict(eq, potOdds, evCall, evRaise, toCall) {
      if (toCall === 0) return evRaise > 0 ? 'Lead/bet — +EV with initiative' : 'Check — pot control';
      if (eq < potOdds && evCall < 0) return 'Fold — equity below price';
      if (evRaise > evCall && evRaise > 0) return 'Raise — most +EV line';
      if (evCall > 0) return 'Call — getting the right price';
      return 'Fold — no profitable continue';
    }

    // the acting human seat plays
    act(action, amount) {
      if (!this.humanToAct()) return;
      const seat = this.game.toAct;
      this.stats.actionFinished();
      this.game.applyAction(seat, action, amount);
      if (action === 'f') this.maybeEnterSpectator(seat);   // fold → watch (God view)
      if (this.hotseat) this.armed = false;   // re-gate for the next player
      this.heroEquity = null;
      if (this.game.handInProgress) this.refreshHeroEquity();
      this.render();
      this.pump();
    }

    // Drive the table forward. When it's the hero's turn, stop and wait for
    // input. When a bot is pending, either resolve it instantly (botDelayMs<=0,
    // used by the headless tests) or step it on a timer so play is watchable.
    pump() {
      const g = this.game;
      // A folded human is reviewing (God view). If another human still has to
      // act, freeze the hand until they tap "Pass device →" (so the device can
      // hand off privately). If only bots remain, let the run-out play live so
      // the folder watches through to showdown.
      if (this.spectating && g.handInProgress) {
        const humanLeft = g.activePlayers().some(p => this.humanSeats.has(p.seat));
        if (humanLeft) { this.render(); return; }
        if (g.awaitingBot >= 0) {
          if (this.botDelayMs <= 0) {
            let gd = 0;
            while (g.handInProgress && g.awaitingBot >= 0) { if (++gd > 500) break; g.stepBot(); }
            this.render(); return;
          }
          this.render();
          this.timer(() => { g.stepBot(); this.pump(); }, this.botDelayMs);
          return;
        }
        this.render(); return;
      }
      if (this.humanToAct()) {
        // hotseat: wait on the privacy gate until the player arms; otherwise
        // it's this human's turn to act.
        if (!this.passGate) this.stats.actionStarted();
        this.render();
        return;
      }
      if (g.handInProgress && g.awaitingBot >= 0) {
        if (this.botDelayMs <= 0) {
          let guard = 0;
          while (g.handInProgress && g.awaitingBot >= 0 && !this.humanToAct()) {
            if (++guard > 500) break;
            g.stepBot();
          }
          if (this.humanToAct() && !this.passGate) this.stats.actionStarted();
          this.render();
          return;
        }
        this.render();
        this.timer(() => { g.stepBot(); this.pump(); }, this.botDelayMs);
        return;
      }
      this.render();
    }

    onHandComplete(result) {
      this.handResult = result;
      const heroNet = (result.net.find(n => n.seat === 0) || { net: 0 }).net;
      this.stats.recordHandResult(heroNet);
      this.render();
      this.onHandEnd(result);
    }

    // derive a player's action-tag set this hand from the history
    actionTagsFor(seat) {
      const tags = new Set();
      if (!this.history) return tags;
      let preflopRaises = 0;
      this.history.streets.forEach((st, sIdx) => {
        for (const a of st.actions) {
          if (a.seat !== seat) continue;
          if (sIdx === 0) {
            if (a.action === 'raise') { preflopRaises++; }
          } else {
            if (a.action === 'raise') tags.add(a.opening ? 'bet_postflop' : 'raised_postflop');
            else if (a.action === 'call') tags.add('called_postflop');
          }
        }
      });
      if (preflopRaises >= 4) tags.add('five_bet_plus');
      else if (preflopRaises === 3) tags.add('four_bet');
      else if (preflopRaises === 2) tags.add('three_bet');
      else if (preflopRaises === 1) tags.add('raised');
      return tags;
    }

    // Gordon's four setup-question answers, from the opponent model
    gordonSetup() {
      const T = getToMLogic();
      // field aggregate VPIP/PFR
      let v = 0, p = 0, n = 0;
      for (const pl of this.game.players) {
        if (pl.isHuman) continue;
        const s = this.oppModel.stats[pl.name];
        if (!s || s.hands < 3) continue;
        const seen = s.hands; v += (s.vpip || 0); p += (s.pfr || 0); n += seen;
      }
      let style = 'n/a yet (need a few hands of sample)';
      if (n >= 6) { const vp = 100 * v / n, pf = 100 * p / n; const tag = vp < 20 ? 'TIGHT' : vp < 35 ? 'NORMAL' : 'LOOSE'; style = `<b>${tag}</b> · field VPIP ${vp.toFixed(0)}%, PFR ${pf.toFixed(0)}% · n=${n}`; }
      // acting player's image (their own session VPIP/PFR)
      let image = 'no sample yet';
      const heroName = this.game.players[this.heroSeat()].name;
      const hi = this.oppModel.stats[heroName];
      if (hi && hi.hands >= 3) { const vp = 100 * (hi.vpip || 0) / hi.hands, pf = 100 * (hi.pfr || 0) / hi.hands; const tag = vp < 20 ? 'TIGHT image' : vp < 35 ? 'balanced image' : 'LOOSE image'; const tail = vp < 20 ? 'they fold to your bets, fold-equity is high' : vp < 35 ? 'standard respect' : 'they call you down — value-bet thin, bluff less'; image = `<b>${tag}</b> · your VPIP ${vp.toFixed(0)}% / PFR ${pf.toFixed(0)}% · ${tail}`; }
      const posMap = { UTG: '<b style="color:#ff7777">EARLY</b> — act first; play tight.', MP: '<b style="color:#ffd966">MIDDLE</b> — neutral.', CO: '<b style="color:#88ff88">LATE</b> — second-best seat; wide opens profitable.', BTN: '<b style="color:#88ff88">LATE</b> — best seat; widest open range.', SB: '<b style="color:#ff7777">BLIND</b> — out of position post-flop; -EV seat.', BB: '<b style="color:#ff7777">BLIND</b> — out of position post-flop; -EV seat.' };
      return { style, ranges: 'see per-bot tabs — each opponent\'s estimated range narrows as the betting progresses', image, position: posMap[this.game.positionOf(this.heroSeat())] || 'n/a' };
    }

    // Full Theory-of-Mind snapshot for the training screen.
    tomData() {
      const T = getToMLogic(), g = this.game, hs = this.heroSeat(), hero = g.players[hs];
      const street = this.streetName();
      const toCall = Math.max(0, g.currentBet - hero.betInRound);
      const potOdds = (g.pot + toCall) > 0 ? toCall / (g.pot + toCall) : 0;
      const oppsActive = g.activePlayers().filter(pp => pp !== hero);
      const mode = this.rangeMode;

      // per-opponent estimated ranges
      const opponents = g.players.filter(pp => pp.seat !== hs).map(pp => {
        const tags = this.actionTagsFor(pp.seat);
        const er = T.estimateRange(pp.style, mode, tags, g.board);
        return { name: pp.name, active: pp.active, range: er.range, notation: er.notation, explanation: er.explanation, boardHits: er.boardHits };
      });

      // no-peek equity vs active opponents' ranges
      let equity = null;
      if (hero.hand.length && hero.active) {
        const ranges = oppsActive.map(pp => {
          const tags = this.actionTagsFor(pp.seat);
          return T.estimateRange(pp.style, mode, tags, g.board).range;
        });
        equity = ranges.length ? T.equityVsRanges(hero.hand, g.board, ranges, { iterations: this.opts.equityIters || 350, rng: this.auxRng }) : null;
        if (equity == null) equity = this.heroEquity;   // fall back to vs-random
      }
      const equityPct = equity != null ? equity * 100 : null;

      // outs + scare + commitment
      const outs = T.computeOuts(hero.hand, g.board);
      const scare = T.scareCards(hero.hand, g.board);
      const commit = { pot: g.pot, toCall, stack: hero.stack };

      // implied label
      const avgOpp = oppsActive.length ? oppsActive.reduce((a, pp) => a + pp.stack, 0) / oppsActive.length : 0;
      const eff = Math.min(hero.stack, avgOpp);
      const impliedPct = (toCall > 0) ? 100 * toCall / (g.pot + toCall + 0.5 * eff) : null;
      const unraised = street === 'Preflop' && toCall > 0 && g.currentBet <= g.bb();
      const potOddsLabel = toCall > 0
        ? `${(potOdds * 100).toFixed(1)}%${unraised ? ' (unraised — not a fold signal)' : ''}`
        : 'no bet';
      const impliedLabel = impliedPct != null ? `${impliedPct.toFixed(1)}% ($${hero.stack - toCall} behind)` : '--';

      // advisor (Gordon)
      const lastAggr = this.lastAggressorSeat();
      const ctx = {
        pot: g.pot, toCall, potOdds, currentBet: g.currentBet, numOpponents: oppsActive.length || 1,
        bb: g.bb(), heroStack: hero.stack, heroPosition: g.positionOf(hs), street,
        heroHand: hero.hand, equity: equity || 0, board: g.board,
        noPeekEquity: equity, hasInitiative: lastAggr === 0,
      };
      const key = T.handToKey(hero.hand);
      const advice = (hero.hand.length && key) ? T.gordonAdvice(ctx, key, this.gordonSetup()) : null;
      const potOddsHeader = T.potOddsHeader(ctx);

      // metrics
      const m = T.metrics(ctx);
      m.tilt = (() => { const t = this.tilt.update(this.stats.decisionTimes); return t.tilted ? 45 : Math.min(20, this.stats.decisionTimes.length); })();
      m.ror = this.stats.lifetimeHands >= 100 ? this.stats.riskOfRuin(2000) * 100 : 100;
      m.vpip = (hs => hs && hs.hands ? 100 * (hs.vpip || 0) / hs.hands : null)(this.oppModel.stats['Hero (You)']);
      m.realized = this.stats.sessionHands >= 3 ? 100 : null;

      // EV per action (for the action bar)
      const evCtx = { pot: g.pot, currentBet: g.currentBet, betInRound: hero.betInRound, board: g.board.length, bb: g.bb(), playerStack: hero.stack, oppStacks: oppsActive.map(pp => pp.stack) };
      const eqForEv = equity != null ? equity : 0;
      const evCall = PA.heroActionEV(evCtx, 'c', eqForEv, 0);
      const evRaise = PA.heroActionEV(evCtx, 'r', eqForEv, Math.floor(g.pot * 0.66));

      const posLongMap = { BT: 'Button', SB: 'Small Blind', BB: 'Big Blind', UTG: 'UTG', CO: 'Cutoff', MP: 'Middle' };
      return {
        board: g.board.slice(), heroHand: hero.hand.slice(), street,
        pot: g.pot, equityPct, potOddsLabel, impliedLabel,
        posLong: posLongMap[g.positionOf(hs)] || g.positionOf(hs),
        outs, scare, commit, rangeMode: this.rangeMode, tab: this.tomTab,
        opponents, advice, potOddsHeader, metrics: m,
        evCheck: toCall === 0 ? 0 : evCall, evCall, evRaise,
      };
    }

    lastAggressorSeat() {
      if (!this.history) return -1;
      let seat = -1;
      for (const st of this.history.streets) for (const a of st.actions) if (a.action === 'raise') seat = a.seat;
      return seat;
    }

    // which seats' hole cards are face-up right now
    seatReveal(seat, active) {
      if (this.handResult) return true;                    // showdown: reveal ALL (incl. folded) for review
      if (this.godMode || this.spectating) return true;
      if (this.hotseat) return this.armed && seat === this.game.toAct && this.humanSeats.has(seat);
      // single-player: hero (seat 0) always; villains after hero folds
      const heroFolded = !this.game.players[0].active && this.game.handInProgress;
      return this.humanSeats.has(seat) || heroFolded;
    }

    // full game-state snapshot for the view
    snapshot() {
      const g = this.game, hs = this.heroSeat();
      // Once the (single-player) hero folds (or god mode), reveal villains + tells.
      const heroFolded = !this.hotseat && !g.players[0].active && g.handInProgress;
      const revealVillains = this.godMode || heroFolded;
      const showTellsEff = this.showTells || heroFolded;
      const armedHuman = this.humanToAct() && (!this.hotseat || this.armed);
      return {
        players: g.players.map(p => ({
          seat: p.seat, name: p.name, style: p.style, stack: p.stack,
          bet: p.betInRound, active: p.active, allIn: p.allIn,
          isHuman: p.isHuman, hand: p.hand.slice(), lastAction: p.lastAction,
          reveal: this.seatReveal(p.seat, p.active),
          isActiveSeat: this.hotseat ? (g.toAct === p.seat && this.humanSeats.has(p.seat)) : p.isHuman,
          pos: g.positionOf(p.seat),
          isDealer: p.seat === g.dealerIdx, isTurn: g.toAct === p.seat,
          leak: (showTellsEff && !p.isHuman) ? this.oppModel.biggestLeak(p.name) : null,
          level: (showTellsEff && !p.isHuman) ? this.oppModel.levelOf(p.name) : null,
          range: (showTellsEff && !p.isHuman && p.active)
            ? PA.rangeFor(p.style, this.streetName()) : null,
        })),
        board: g.board.slice(),
        pot: g.pot, street: this.streetName(),
        handNumber: g.handNumber, sb: g.sb(), bb: g.bb(),
        hotseat: this.hotseat, passGate: this.passGate,
        activeName: g.players[g.toAct] ? g.players[g.toAct].name : '',
        spectating: this.spectating,
        spectator: this.spectating ? this.spectatorData() : null,
        assists: this.assistFlags(),
        canUseGod: this.canUseGod(),
        awaitingHero: armedHuman,
        legal: armedHuman ? g.legalActions(g.toAct) : null,
        advisor: armedHuman ? this.advisor() : null,
        events: this.events.slice(),
        handResult: this.handResult,
        revealVillains, heroFolded,
        training: this.training,
        tom: this.training ? this.tomData() : null,
        godMode: this.godMode, showTells: this.showTells,
        session: {
          hands: this.stats.sessionHands, bb100: this.stats.sessionBbPer100,
          std: this.stats.sessionStd, lifeHands: this.stats.lifetimeHands,
          lifeBb100: this.stats.lifetimeBbPer100,
        },
      };
    }

    render() { this.onRender(this.snapshot()); }
  }

  // ---------------- View (DOM) ----------------
  const SUIT_GLYPH = { c: '♣', d: '♦', h: '♥', s: '♠' };
  const SUIT_CLASS = { c: 'club', d: 'diamond', h: 'heart', s: 'spade' };

  function cardHTML(cardInt, hidden) {
    if (hidden) return '<span class="card back"></span>';
    const str = E.cardToStr(cardInt);
    const r = str[0], s = str[1];
    return `<span class="card ${SUIT_CLASS[s]}"><b>${r === 'T' ? '10' : r}</b><i>${SUIT_GLYPH[s]}</i></span>`;
  }

  class View {
    constructor(rootEl, controller) {
      this.root = rootEl;
      this.ctrl = controller;
      this.build();
    }
    build() {
      this.root.innerHTML = `
        <div class="piq-top">
          <div class="piq-brand">Poker<b>IQ</b></div>
          <div class="piq-hud">
            <span id="piq-hand">Hand —</span>
            <span id="piq-blinds">Blinds —</span>
            <span id="piq-session" class="muted"></span>
          </div>
          <div class="piq-menu">
            <label class="train-toggle" id="piq-train"><span class="tt-knob"></span><span class="tt-lab">Training</span></label>
            <button data-act="players" class="ghost">Players</button>
            <button data-act="tells" class="ghost">Tells</button>
            <button data-act="god" class="ghost">God</button>
            <button data-act="trainers" class="ghost">Trainers ▾</button>
            <button data-act="stats" class="ghost">Stats</button>
            <button data-act="savelog" class="ghost" title="Download the full session log (PyQt-format) for AI analysis">⤓ Log</button>
            <button data-act="help" class="ghost">?</button>
          </div>
        </div>
        <div class="table-view" id="piq-tableview">
          <div class="piq-felt">
            <div class="piq-board" id="piq-board"></div>
            <div class="piq-pot" id="piq-pot"></div>
            <div class="piq-seats" id="piq-seats"></div>
            <div class="piq-result" id="piq-result" style="display:none"></div>
          </div>
          <div class="piq-bottom">
            <div class="piq-feed" id="piq-feed"></div>
            <div class="piq-advisor" id="piq-advisor"></div>
          </div>
        </div>
        <div class="tom-view" id="piq-tomview" style="display:none"></div>
        <div class="piq-spectator" id="piq-spectator" style="display:none"></div>
        <div class="piq-gate" id="piq-gate" style="display:none"></div>
        <div class="piq-footer"><div class="piq-actions" id="piq-actions"></div></div>
        <div class="piq-modal" id="piq-modal" style="display:none"></div>`;
      this.el = {
        hand: this.root.querySelector('#piq-hand'),
        blinds: this.root.querySelector('#piq-blinds'),
        session: this.root.querySelector('#piq-session'),
        board: this.root.querySelector('#piq-board'),
        pot: this.root.querySelector('#piq-pot'),
        seats: this.root.querySelector('#piq-seats'),
        result: this.root.querySelector('#piq-result'),
        feed: this.root.querySelector('#piq-feed'),
        advisor: this.root.querySelector('#piq-advisor'),
        actions: this.root.querySelector('#piq-actions'),
        modal: this.root.querySelector('#piq-modal'),
        tableView: this.root.querySelector('#piq-tableview'),
        tomView: this.root.querySelector('#piq-tomview'),
        gate: this.root.querySelector('#piq-gate'),
        spectator: this.root.querySelector('#piq-spectator'),
        train: this.root.querySelector('#piq-train'),
      };
      this.root.querySelector('.piq-menu').addEventListener('click', e => {
        const act = e.target.getAttribute('data-act'); if (!act) return;
        if (act === 'god') { this.ctrl.toggleGod(); }
        else if (act === 'tells') { this.ctrl.toggleTells(); }
        else if (this.onMenu) this.onMenu(act);
      });
      this.el.train.addEventListener('click', () => { this.ctrl.toggleTraining(); });
      // delegated clicks inside the ToM view (tabs + range-mode radio)
      this.el.tomView.addEventListener('click', e => {
        const tab = e.target.closest('[data-tab]'); if (tab) { this.ctrl.tomTab = tab.getAttribute('data-tab'); this.ctrl.render(); return; }
        const rm = e.target.closest('[data-mode]'); if (rm) { this.ctrl.rangeMode = rm.getAttribute('data-mode'); this.ctrl.render(); return; }
      });
    }

    render(s) {
      this.el.hand.textContent = `Hand #${s.handNumber} · ${s.street}`;
      this.el.blinds.textContent = `Blinds $${s.sb}/$${s.bb}`;
      this.el.session.textContent = `Session ${s.session.hands}h · ${s.session.bb100 >= 0 ? '+' : ''}${s.session.bb100.toFixed(1)} bb/100`;
      this.el.train.classList.toggle('on', s.training);

      // hotseat privacy gate covers everything until the next player arms
      if (s.passGate) {
        this.el.gate.style.display = 'flex';
        this.el.gate.innerHTML = `<div class="gate-card">
          <div class="gate-icon">🂠</div>
          <div class="gate-pass">Pass the device to</div>
          <div class="gate-name">${escapeHTML(s.activeName)}</div>
          <div class="gate-sub">Everyone else: look away.</div>
          <button class="btn check gate-go" id="piq-arm">I'm ${escapeHTML(s.activeName)} — show my cards</button>
        </div>`;
        const arm = this.root.querySelector('#piq-arm');
        if (arm) arm.onclick = () => this.ctrl.arm();
      } else {
        this.el.gate.style.display = 'none';
      }

      // spectator (you folded) panel — overlays the bottom with the equity table
      if (s.spectating && s.spectator) {
        this.el.spectator.style.display = 'block';
        this.renderSpectator(s);
      } else {
        this.el.spectator.style.display = 'none';
      }

      if (s.training) {
        this.el.tableView.style.display = 'none';
        this.el.tomView.style.display = s.passGate ? 'none' : 'block';
        if (!s.passGate) this.el.tomView.innerHTML = getToM().render(s.tom);
      } else {
        this.el.tomView.style.display = 'none';
        this.el.tableView.style.display = 'flex';
        // board
        this.el.board.innerHTML = s.board.map(c => cardHTML(c, false)).join('') ||
          '<span class="muted">— preflop —</span>';
        this.el.pot.innerHTML = `<span class="chip"></span> Pot $${s.pot}`;
        this.el.seats.innerHTML = s.players.map(p => this.seatHTML(p, s)).join('');
        this.el.feed.innerHTML = s.events.map(e => `<div>${escapeHTML(e)}</div>`).join('');
        this.el.advisor.innerHTML = s.advisor ? this.advisorHTML(s.advisor) : '';
      }

      // shared action footer (with EV labels in training mode)
      this.el.actions.innerHTML = '';
      if (s.handResult) this.buildEndActions(s);
      else if (s.spectating) this.el.actions.innerHTML = '<span class="muted">👁 You folded — watching with God view. Use the panel to review streets.</span>';
      else if (s.passGate) this.el.actions.innerHTML = `<span class="muted">🂠 waiting for ${escapeHTML(s.activeName)} to take the device…</span>`;
      else if (s.awaitingHero && s.legal) this.buildActions(s.legal, s.training ? s.tom : null);
      else this.el.actions.innerHTML = '<span class="muted">…bots acting</span>';

      // result overlay only in table mode
      if (s.handResult && !s.training) this.showResult(s.handResult, s);
      else this.el.result.style.display = 'none';

      const godBtn = this.root.querySelector('[data-act="god"]');
      godBtn.classList.toggle('on', s.godMode);
      // God peek is disabled while other humans are at the table (hotseat) —
      // you only get the God view after you fold.
      godBtn.disabled = !s.canUseGod;
      godBtn.title = s.canUseGod ? '' : 'God peek is off in multiplayer — you get the God view after you fold';
      this.root.querySelector('[data-act="tells"]').classList.toggle('on', s.showTells);
    }

    // spectator equity panel (you folded → God view), mirrors the desktop layout
    renderSpectator(s) {
      const sp = s.spectator;
      const bar = (frac, cls) => `<div class="sb-track"><div class="sb-fill ${cls}" style="width:${Math.max(0, Math.min(1, frac || 0)) * 100}%"></div></div>`;
      const rows = sp.table.map(p => {
        if (p.folded) return `<tr class="folded"><td>${escapeHTML(p.name)}</td><td colspan="4" class="muted">(Folded)</td></tr>`;
        const ev = p.facing ? (p.evPos ? '<span class="pos">+EV</span>' : '<span class="neg">-EV</span>') : '';
        return `<tr>
          <td class="${p.seat === 0 ? 'me' : ''}">${escapeHTML(p.name)}</td>
          <td>${bar(p.real, 'real')}<span class="sb-pct">${(p.real * 100).toFixed(0)}%</span></td>
          <td>${bar(p.thinking, 'think')}<span class="sb-pct">${(p.thinking * 100).toFixed(0)}%</span></td>
          <td>${bar(p.potOdds, 'odds')}<span class="sb-pct">${(p.potOdds * 100).toFixed(0)}%</span></td>
          <td class="sb-ev">${ev}</td>
        </tr>`;
      }).join('');
      const board = sp.board.length ? sp.board.map(c => cardHTML(c, false)).join('') : '<span class="muted">preflop</span>';
      this.el.spectator.innerHTML = `
        <div class="sp-head">
          <span class="sp-title">👁 Spectating — ${escapeHTML(sp.street)}${sp.live ? '' : ' (review)'}</span>
          <span class="sp-board">${board}</span>
          <span class="sp-pot">Pot $${sp.pot}</span>
          <span class="sp-nav">
            <button class="ghost" id="sp-prev" ${sp.canPrev ? '' : 'disabled'}>◄ Previous Street</button>
            <button class="ghost" id="sp-next" ${sp.canNext ? '' : 'disabled'}>Next Street ►</button>
            <button class="btn ${sp.passMode ? 'check' : 'fold'}" id="sp-close">${sp.passMode ? 'Pass device →' : 'Close View'}</button>
          </span>
        </div>
        <table class="sp-table">
          <tr><th>Player</th><th>Real</th><th>Thinking</th><th>Pot Odds</th><th></th></tr>
          ${rows}
        </table>`;
      const prev = this.root.querySelector('#sp-prev'); if (prev) prev.onclick = () => this.ctrl.specPrev();
      const next = this.root.querySelector('#sp-next'); if (next) next.onclick = () => this.ctrl.specNext();
      const close = this.root.querySelector('#sp-close'); if (close) close.onclick = () => this.ctrl.exitSpectator(sp.passMode);
    }

    buildEndActions(s) {
      const wrap = this.el.actions;
      const lbl = document.createElement('span');
      if (s.hotseat) {
        const winners = s.handResult.net.filter(n => s.handResult.payouts[n.seat] > 0);
        lbl.className = 'end-net pos';
        lbl.textContent = `Hand #${s.handNumber}: ${winners.map(w => `${w.name} +$${w.net}`).join(', ') || 'split'}`;
      } else {
        const heroNet = (s.handResult.net.find(n => n.seat === 0) || { net: 0 }).net;
        lbl.className = 'end-net ' + (heroNet >= 0 ? 'pos' : 'neg');
        lbl.textContent = `Hand #${s.handNumber}: you ${heroNet >= 0 ? 'win' : 'lose'} $${Math.abs(heroNet)}`;
      }
      const sum = document.createElement('button'); sum.className = 'btn summary'; sum.textContent = 'Hand summary';
      sum.onclick = () => this.showHandSummary(this.ctrl.lastHistory);
      const next = document.createElement('button'); next.className = 'btn next'; next.textContent = 'Next hand →';
      next.onclick = () => this.ctrl.newHand();
      wrap.append(lbl, sum, next);
    }

    seatHTML(p, s) {
      const reveal = p.reveal;
      const cards = p.hand.length
        ? p.hand.map(c => cardHTML(c, !reveal)).join('')
        : '<span class="card empty"></span><span class="card empty"></span>';
      const tags = [];
      if (p.isDealer) tags.push('<span class="dealer">D</span>');
      if (p.pos) tags.push(`<span class="pos">${p.pos}</span>`);
      const tells = p.leak ? `<div class="leak">⚑ ${escapeHTML(p.leak)}</div>` : '';
      const range = p.range ? `<div class="range">range: ${escapeHTML(p.range)}</div>` : '';
      const lvl = (p.level != null) ? `<span class="lvl" title="levels of thinking">L${p.level}</span>` : '';
      return `<div class="seat ${p.active ? '' : 'folded'} ${p.isTurn ? 'turn' : ''} ${p.isActiveSeat ? 'hero' : ''}">
        <div class="seat-head"><span class="seat-name">${escapeHTML(p.name)}</span> ${tags.join(' ')} ${lvl}</div>
        <div class="seat-cards">${cards}</div>
        <div class="seat-foot"><span class="stack">$${p.stack}</span>${p.bet > 0 ? `<span class="bet">bet $${p.bet}</span>` : ''}${p.allIn ? '<span class="allin">ALL-IN</span>' : ''}</div>
        ${p.lastAction ? `<div class="last">${p.lastAction}</div>` : ''}
        ${tells}${range}
      </div>`;
    }

    advisorHTML(a) {
      const money = v => (v >= 0 ? '+' : '') + '$' + v.toFixed(1);
      const evColor = v => v > 0.5 ? 'pos' : (v < -0.5 ? 'neg' : 'neu');
      return `
        <div class="adv-row">
          <span class="adv-k">Equity</span><span class="adv-v">${(a.equity * 100).toFixed(1)}%</span>
          <span class="adv-k">Pot odds</span><span class="adv-v">${(a.potOdds * 100).toFixed(1)}%</span>
          <span class="adv-k">Pos</span><span class="adv-v">${a.posLabel}</span>
        </div>
        <div class="adv-row">
          <span class="adv-k">EV fold</span><span class="adv-v ${evColor(0)}">$0.0</span>
          <span class="adv-k">EV call</span><span class="adv-v ${evColor(a.evCall)}">${money(a.evCall)}</span>
          <span class="adv-k">EV raise</span><span class="adv-v ${evColor(a.evRaise)}">${money(a.evRaise)}</span>
        </div>
        <div class="adv-board">Board: <b>${a.board.label}</b>${a.board.cbet ? ' — ' + a.board.cbet : ''}</div>
        <div class="adv-verdict">▸ ${a.verdict}</div>`;
    }

    buildActions(legal, tom) {
      const wrap = this.el.actions;
      // EV sub-label (training mode shows EV under each action, as in the panel)
      const ev = v => tom ? `<small class="ev ${v > 0.5 ? 'pos' : v < -0.5 ? 'neg' : 'neu'}">EV ${v >= 0 ? '+' : ''}$${v.toFixed(1)}</small>` : '';
      const mk = (label, cls, fn) => { const b = document.createElement('button'); b.className = cls; b.innerHTML = label; b.onclick = fn; wrap.appendChild(b); return b; };
      mk(`Fold${ev(0)}`, 'btn fold', () => this.ctrl.act('f', 0));
      if (legal.canCheck) mk(`Check${ev(tom ? tom.evCheck : 0)}`, 'btn check', () => this.ctrl.act('c', 0));
      else mk(`Call $${legal.toCall}${ev(tom ? tom.evCall : 0)}`, 'btn call', () => this.ctrl.act('c', 0));
      if (legal.canRaise) {
        const slider = document.createElement('input');
        slider.type = 'range'; slider.min = legal.minRaiseTo; slider.max = legal.maxRaiseTo;
        slider.value = Math.min(legal.maxRaiseTo, Math.max(legal.minRaiseTo, Math.floor(legal.pot * 0.66) + legal.toCall));
        const out = document.createElement('span'); out.className = 'raise-amt';
        const sync = () => { out.textContent = '$' + slider.value; };
        slider.oninput = sync; sync();
        const raiseBtn = mk(`Raise${ev(tom ? tom.evRaise : 0)}`, 'btn raise', () => this.ctrl.act('r', parseInt(slider.value, 10)));
        // pot-fraction quick buttons
        const quick = document.createElement('div'); quick.className = 'quick';
        [['½', 0.5], ['¾', 0.75], ['Pot', 1.0], ['All-in', null]].forEach(([lbl, frac]) => {
          const q = document.createElement('button'); q.className = 'qbtn'; q.textContent = lbl;
          q.onclick = () => { slider.value = frac == null ? legal.maxRaiseTo : Math.min(legal.maxRaiseTo, Math.max(legal.minRaiseTo, Math.floor(legal.pot * frac) + legal.toCall)); sync(); };
          quick.appendChild(q);
        });
        const sliderWrap = document.createElement('div'); sliderWrap.className = 'slider-wrap';
        sliderWrap.appendChild(slider); sliderWrap.appendChild(out);
        wrap.appendChild(sliderWrap); wrap.appendChild(quick);
        raiseBtn.parentNode.insertBefore(raiseBtn, sliderWrap); // keep order tidy
      }
    }

    showResult(res, s) {
      const heroNet = (res.net.find(n => n.seat === 0) || { net: 0 }).net;
      const winners = res.showdown.filter(sd => res.payouts[sd.seat] > 0);
      const lines = res.showdown.length
        ? res.showdown.map(sd => `<div class="${res.payouts[sd.seat] > 0 ? 'won' : ''}">${escapeHTML(sd.name)} — ${sd.desc} ${res.payouts[sd.seat] > 0 ? `(+$${res.payouts[sd.seat]})` : ''}</div>`).join('')
        : `<div>Pot won uncontested</div>`;
      this.el.result.innerHTML = `
        <div class="result-card">
          <h3>Hand #${s.handNumber} complete</h3>
          <div class="result-net ${heroNet >= 0 ? 'pos' : 'neg'}">You ${heroNet >= 0 ? 'win' : 'lose'} $${Math.abs(heroNet)}</div>
          <div class="result-show">${lines}</div>
          <div class="result-btns">
            <button class="btn summary" id="piq-summary">Hand summary</button>
            <button class="btn next" id="piq-next">Next hand →</button>
          </div>
        </div>`;
      this.el.result.style.display = 'flex';
      const nb = this.root.querySelector('#piq-next');
      if (nb) nb.onclick = () => this.ctrl.newHand();
      const sb = this.root.querySelector('#piq-summary');
      if (sb) sb.onclick = () => this.showHandSummary(this.ctrl.lastHistory);
    }

    showHandSummary(history) {
      if (!history) return;
      this._summary = { history, data: this.ctrl.buildSummaryData(history), view: 'basic' };
      this.renderSummary();
    }
    switchSummary(view) { if (this._summary) { this._summary.view = view; this.renderSummary(); } }
    renderSummary() {
      const { history, data, view } = this._summary;
      this.showModal(this.handSummaryNode(history, data, view));
    }

    handSummaryNode(h, data, view) {
      const card = document.createElement('div'); card.className = 'modal-card hs-modal';
      const flags = (h.assists && h.assists.length)
        ? `<div class="hs-flags">⚑ Assists used while still in the hand: ` +
          h.assists.map(a => `<b>${escapeHTML(a.name)}</b> — ${a.assists.map(escapeHTML).join(', ')}`).join(' · ') + `</div>` : '';
      let body;
      if (view === 'stats') body = this.summaryStatsHTML(data, flags);
      else if (view === 'log') body = this.summaryLogHTML(h);
      else body = this.summaryBasicHTML(data, flags);
      card.innerHTML = `<h2>Hand Summary</h2><div class="hs-body">${body}</div><div class="modal-actions hs-actions"></div>`;
      const mk = (label, cls, fn) => { const b = document.createElement('button'); b.className = cls; b.textContent = label; b.onclick = fn; return b; };
      const act = card.querySelector('.hs-actions');
      if (view !== 'basic') act.appendChild(mk('Analysis', 'ghost', () => this.switchSummary('basic')));
      if (view !== 'stats') act.appendChild(mk('Stats', 'btn check', () => this.switchSummary('stats')));
      if (view !== 'log') act.appendChild(mk('Hand Log', 'btn raise', () => this.switchSummary('log')));
      act.appendChild(mk('Close', 'ghost', () => this.closeModal()));
      return card;
    }

    // basic analysis text (matches the desktop "Hand #N Analysis" view)
    summaryBasicHTML(d, flags) {
      const cs = cards => cards.map(c => E.cardToStr(c)).join(' ');
      const heroSeat = (d.humanSeats && d.humanSeats.length) ? Math.min(...d.humanSeats) : 0;
      const L = [];
      L.push(`Hand #${d.handNumber} Analysis`);
      L.push('-'.repeat(40));
      L.push('HOLE CARDS:');
      d.holeCards.forEach(x => L.push(`  ${x.name}: ${cs(x.cards)} (${x.category})`));
      L.push('');
      d.heldLines.forEach(x => L.push(`${x.name} held: ${x.held} (${cs(x.cards)})`));
      // per-street boards + hero equity + opponents' made hands
      d.panels.forEach((p, i) => {
        if (p.name === 'Preflop') return;
        const newCards = p.name === 'Flop' ? p.board.slice(0, 3) : p.board.slice(-1);
        L.push('');
        L.push(`${p.name}: ${cs(newCards)}`);
        const heroRow = p.rows.find(r => r.seat === heroSeat);
        if (heroRow && !heroRow.folded) L.push(`  ${heroRow.name} equity: ${Math.round(heroRow.real * 100)}%`);
        p.rows.filter(r => !r.folded && !d.humanSeats.includes(r.seat)).forEach(r => L.push(`  ${r.name}: ${r.made}`));
      });
      return `${flags}<pre class="hs-basic">${escapeHTML(L.join('\n'))}</pre>`;
    }

    // rich per-street stats panels (Player | Cards | Hand | True Equity | vs Range | A/B + actions)
    summaryStatsHTML(d, flags) {
      const bar = (f, cls) => `<span class="sb-track" style="width:90px"><span class="sb-fill ${cls}" style="width:${Math.max(0, Math.min(1, f || 0)) * 100}%"></span></span>`;
      const panelHTML = p => {
        const board = p.board.length ? p.board.map(c => cardHTML(c, false)).join('') : '<span class="muted">preflop</span>';
        const rows = p.rows.map(r => {
          const cards = r.cards.map(c => cardHTML(c, false)).join('');
          if (r.folded) return `<tr class="folded"><td>${escapeHTML(r.name)}</td><td>${cards}</td><td>${escapeHTML(r.made)}</td><td colspan="3" class="muted">(Folded)</td></tr>`;
          return `<tr>
            <td>${escapeHTML(r.name)}</td><td>${cards}</td><td>${escapeHTML(r.made)}</td>
            <td>${bar(r.real, r.ahead ? 'real' : 'bad')}<span class="sb-pct">${Math.round(r.real * 100)}%</span></td>
            <td>${bar(r.thinking, 'think')}<span class="sb-pct">${Math.round(r.thinking * 100)}%</span></td>
            <td class="${r.ahead ? 'pos' : 'neg'}">${r.ahead ? 'AHEAD' : 'BEHIND'}</td></tr>`;
        }).join('');
        const acts = p.actions.length ? p.actions.map(a => `<div><b>${escapeHTML(a.name)}</b>: ${escapeHTML(a.verb)}</div>`).join('') : '<div class="muted">—</div>';
        return `<div class="hs-panel">
          <div class="hs-panel-top"><span class="hs-st-name">${p.name}</span> <span class="hs-pb">${board}</span> <span class="sp-pot">Pot $${p.pot}</span></div>
          <div class="hs-panel-grid">
            <table class="hs-eqtable"><tr><th>Player</th><th>Cards</th><th>Hand</th><th>True Equity</th><th>vs Range</th><th></th></tr>${rows}</table>
            <div class="hs-actcol"><div class="hs-actcol-h">Actions</div>${acts}</div>
          </div></div>`;
      };
      const panels = d.panels.filter(p => p.name === 'Preflop' || p.board.length).map(panelHTML).join('');
      // hand results
      const results = `<div class="hs-results"><h3>Hand Results</h3><div class="hs-res-grid">` +
        d.results.map(r => `<div class="hs-res"><div class="hs-res-name">${escapeHTML(r.name)}</div><div class="hs-res-net ${r.net > 0 ? 'pos' : r.net < 0 ? 'neg' : 'muted'}">${r.net >= 0 ? '+' : '-'}$${Math.abs(r.net)}</div><div class="muted">$${r.start} → $${r.end}</div></div>`).join('') +
        `</div></div>`;
      return `${flags}<div class="hs-panels">${panels}</div>${results}`;
    }

    // raw per-hand action log
    summaryLogHTML(h) {
      const L = [`Hand #${h.handNumber}`];
      const verb = a => a.action === 'post' ? `posts $${a.amount}`
        : a.action === 'raise' ? (a.opening ? `bets $${a.total}` : `raises to $${a.total}`)
        : a.action === 'call' ? `calls $${a.amount}` : a.action === 'check' ? 'checks' : a.action === 'fold' ? 'folds' : a.action;
      (h.streets || []).forEach(st => {
        if (!st.actions.length && st.name === 'Preflop') return;
        const board = st.board && st.board.length ? ' [' + st.board.map(c => E.cardToStr(c)).join(' ') + ']' : '';
        L.push('');
        L.push(`--- ${st.name} ---${board}`);
        st.actions.forEach(a => L.push(`  ${a.name}: ${verb(a)}`));
      });
      if (h.result) {
        L.push('');
        (h.result.net || []).forEach(n => L.push(`  ${n.name}: ${n.net >= 0 ? '+' : '-'}$${Math.abs(n.net)} (→ $${n.stack})`));
      }
      return `<pre class="hs-basic">${escapeHTML(L.join('\n'))}</pre>`;
    }
  }

  // modal host + menu popup live on the View prototype
  View.prototype.showModal = function (node) {
    this.el.modal.innerHTML = '';
    this.el.modal.appendChild(node);
    this.el.modal.style.display = 'flex';
    this.el.modal.onclick = (e) => { if (e.target === this.el.modal) this.closeModal(); };
  };
  View.prototype.closeModal = function () { this.el.modal.style.display = 'none'; this.el.modal.innerHTML = ''; };
  View.prototype.popupMenu = function (anchorAct, items) {
    const existing = this.root.querySelector('.menu-pop'); if (existing) { existing.remove(); return; }
    const btn = this.root.querySelector(`[data-act="${anchorAct}"]`);
    const pop = document.createElement('div'); pop.className = 'menu-pop';
    const r = btn.getBoundingClientRect();
    pop.style.left = r.left + 'px'; pop.style.top = (r.bottom + 4) + 'px';
    items.forEach(([label, fn]) => { const b = document.createElement('button'); b.textContent = label; b.onclick = () => { pop.remove(); fn(); }; pop.appendChild(b); });
    document.body.appendChild(pop);
    setTimeout(() => { const off = (e) => { if (!pop.contains(e.target)) { pop.remove(); document.removeEventListener('click', off); } }; document.addEventListener('click', off); }, 0);
  };

  function escapeHTML(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  const API = { Controller, View, cardHTML };
  if (isNode) module.exports = API;
  else root.PokerUI = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
