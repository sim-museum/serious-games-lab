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

      this.game = new PG.Game({
        rng: opts.rng || Math.random,
        godMode: this.godMode,
        manualBots: true,                  // controller paces bot turns
        botDecide: (g, p) => PB.decide(g, p),
        onEvent: (t, payload) => this.onGameEvent(t, payload),
      });
    }

    streetName() { return PG.STREETS[this.game.streetIdx] || 'Showdown'; }

    newHand() {
      this.handResult = null;
      this.events = [];
      this.heroEquity = null;
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

    onGameEvent(type, payload) {
      if (type === 'handStart') {
        this.history = {
          handNumber: payload.handNumber,
          startStacks: payload.startStacks,
          streets: [{ name: 'Preflop', board: [], actions: [] }],
        };
      } else if (type === 'log') {
        this.pushEvent(payload);
      } else if (type === 'street') {
        this.lastStreet = payload.street; this.heroEquity = null; this.refreshHeroEquity();
        if (this.history) this.history.streets.push({ name: payload.street, board: payload.board.slice(), actions: [] });
      } else if (type === 'action') {
        this.recordHistoryAction(payload);
        this.trackOppAction(payload);
      } else if (type === 'handEnd') {
        if (this.history) { this.history.result = payload; this.lastHistory = this.history; }
        this.onHandComplete(payload);
      }
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
      const hero = this.game.players[0];
      if (!hero.active || !hero.hand.length) { this.heroEquity = null; return; }
      const opps = this.game.activePlayers().filter(p => p !== hero).length || 1;
      this.heroEquity = E.equityVsRandom(hero.hand, this.game.board,
        { iterations: this.opts.equityIters || 600, opponents: opps, rng: this.game.rng });
    }

    // advisor readout for the hero panel
    advisor() {
      const hero = this.game.players[0];
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
        board, posLabel: g.positionOf(0),
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

    // hero acts
    act(action, amount) {
      if (!this.game.awaitingAction || this.game.toAct !== 0) return;
      this.stats.actionFinished();
      // record hero into opponent-agnostic feed already handled by engine log
      this.game.applyAction(0, action, amount);
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
      if (g.awaitingAction && g.toAct === 0) { this.stats.actionStarted(); this.render(); return; }
      if (g.handInProgress && g.awaitingBot >= 0) {
        if (this.botDelayMs <= 0) {
          let guard = 0;
          while (g.handInProgress && g.awaitingBot >= 0 && !(g.awaitingAction && g.toAct === 0)) {
            if (++guard > 500) break;
            g.stepBot();
          }
          if (g.awaitingAction && g.toAct === 0) this.stats.actionStarted();
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
      const T = root.PokerToMLogic;
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
      // hero image
      let image = 'no sample yet';
      const hs = this.oppModel.stats['Hero (You)'];
      if (hs && hs.hands >= 3) { const vp = 100 * (hs.vpip || 0) / hs.hands, pf = 100 * (hs.pfr || 0) / hs.hands; const tag = vp < 20 ? 'TIGHT image' : vp < 35 ? 'balanced image' : 'LOOSE image'; const tail = vp < 20 ? 'they fold to your bets, fold-equity is high' : vp < 35 ? 'standard respect' : 'they call you down — value-bet thin, bluff less'; image = `<b>${tag}</b> · your VPIP ${vp.toFixed(0)}% / PFR ${pf.toFixed(0)}% · ${tail}`; }
      const posMap = { UTG: '<b style="color:#ff7777">EARLY</b> — act first; play tight.', MP: '<b style="color:#ffd966">MIDDLE</b> — neutral.', CO: '<b style="color:#88ff88">LATE</b> — second-best seat; wide opens profitable.', BTN: '<b style="color:#88ff88">LATE</b> — best seat; widest open range.', SB: '<b style="color:#ff7777">BLIND</b> — out of position post-flop; -EV seat.', BB: '<b style="color:#ff7777">BLIND</b> — out of position post-flop; -EV seat.' };
      return { style, ranges: 'see per-bot tabs — each opponent\'s estimated range narrows as the betting progresses', image, position: posMap[this.game.positionOf(0)] || 'n/a' };
    }

    // Full Theory-of-Mind snapshot for the training screen.
    tomData() {
      const T = root.PokerToMLogic, g = this.game, hero = g.players[0];
      const street = this.streetName();
      const toCall = Math.max(0, g.currentBet - hero.betInRound);
      const potOdds = (g.pot + toCall) > 0 ? toCall / (g.pot + toCall) : 0;
      const oppsActive = g.activePlayers().filter(pp => pp !== hero);
      const mode = this.rangeMode;

      // per-opponent estimated ranges
      const opponents = g.players.filter(pp => !pp.isHuman).map(pp => {
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
        equity = ranges.length ? T.equityVsRanges(hero.hand, g.board, ranges, { iterations: this.opts.equityIters || 350, rng: g.rng }) : null;
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
        bb: g.bb(), heroStack: hero.stack, heroPosition: g.positionOf(0), street,
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
        posLong: posLongMap[g.positionOf(0)] || g.positionOf(0),
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

    // full game-state snapshot for the view
    snapshot() {
      const g = this.game;
      // Once the hero folds (or in god mode), reveal villain cards + tells for
      // the rest of the hand so you can study how it plays out.
      const heroFolded = !g.players[0].active && g.handInProgress;
      const revealVillains = this.godMode || heroFolded;
      const showTellsEff = this.showTells || heroFolded;
      return {
        players: g.players.map(p => ({
          seat: p.seat, name: p.name, style: p.style, stack: p.stack,
          bet: p.betInRound, active: p.active, allIn: p.allIn,
          isHuman: p.isHuman, hand: p.hand.slice(), lastAction: p.lastAction,
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
        awaitingHero: g.awaitingAction && g.toAct === 0,
        legal: (g.awaitingAction && g.toAct === 0) ? g.legalActions(0) : null,
        advisor: (g.awaitingAction && g.toAct === 0) ? this.advisor() : null,
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
            <button data-act="tells" class="ghost">Tells</button>
            <button data-act="god" class="ghost">God</button>
            <button data-act="trainers" class="ghost">Trainers ▾</button>
            <button data-act="stats" class="ghost">Stats</button>
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
        train: this.root.querySelector('#piq-train'),
      };
      this.root.querySelector('.piq-menu').addEventListener('click', e => {
        const act = e.target.getAttribute('data-act'); if (!act) return;
        if (act === 'god') { this.ctrl.godMode = !this.ctrl.godMode; this.ctrl.render(); }
        else if (act === 'tells') { this.ctrl.showTells = !this.ctrl.showTells; this.ctrl.render(); }
        else if (this.onMenu) this.onMenu(act);
      });
      this.el.train.addEventListener('click', () => { this.ctrl.training = !this.ctrl.training; this.ctrl.render(); });
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

      if (s.training) {
        this.el.tableView.style.display = 'none';
        this.el.tomView.style.display = 'block';
        this.el.tomView.innerHTML = root.PokerToM.render(s.tom);
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
      else if (s.awaitingHero && s.legal) this.buildActions(s.legal, s.training ? s.tom : null);
      else this.el.actions.innerHTML = '<span class="muted">…bots acting</span>';

      // result overlay only in table mode
      if (s.handResult && !s.training) this.showResult(s.handResult, s);
      else this.el.result.style.display = 'none';

      this.root.querySelector('[data-act="god"]').classList.toggle('on', s.godMode);
      this.root.querySelector('[data-act="tells"]').classList.toggle('on', s.showTells);
    }

    buildEndActions(s) {
      const wrap = this.el.actions;
      const heroNet = (s.handResult.net.find(n => n.seat === 0) || { net: 0 }).net;
      const lbl = document.createElement('span'); lbl.className = 'end-net ' + (heroNet >= 0 ? 'pos' : 'neg');
      lbl.textContent = `Hand #${s.handNumber}: you ${heroNet >= 0 ? 'win' : 'lose'} $${Math.abs(heroNet)}`;
      const sum = document.createElement('button'); sum.className = 'btn summary'; sum.textContent = 'Hand summary';
      sum.onclick = () => this.showHandSummary(this.ctrl.lastHistory);
      const next = document.createElement('button'); next.className = 'btn next'; next.textContent = 'Next hand →';
      next.onclick = () => this.ctrl.newHand();
      wrap.append(lbl, sum, next);
    }

    seatHTML(p, s) {
      const reveal = p.isHuman || s.revealVillains || (s.handResult && p.active);
      const cards = p.hand.length
        ? p.hand.map(c => cardHTML(c, !reveal)).join('')
        : '<span class="card empty"></span><span class="card empty"></span>';
      const tags = [];
      if (p.isDealer) tags.push('<span class="dealer">D</span>');
      if (p.pos) tags.push(`<span class="pos">${p.pos}</span>`);
      const tells = p.leak ? `<div class="leak">⚑ ${escapeHTML(p.leak)}</div>` : '';
      const range = p.range ? `<div class="range">range: ${escapeHTML(p.range)}</div>` : '';
      const lvl = (p.level != null) ? `<span class="lvl" title="levels of thinking">L${p.level}</span>` : '';
      return `<div class="seat ${p.active ? '' : 'folded'} ${p.isTurn ? 'turn' : ''} ${p.isHuman ? 'hero' : ''}">
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
      this.showModal(this.handSummaryNode(history));
    }

    // Build the hand-summary modal: per-street betting + board, and a
    // start→end stack table with each player's win/loss.
    handSummaryNode(h) {
      const res = h.result || { net: [], showdown: [], payouts: {} };
      const startBySeat = {}; (h.startStacks || []).forEach(x => startBySeat[x.seat] = x.stack);
      const netBySeat = {}; (res.net || []).forEach(x => netBySeat[x.seat] = x);
      const handBySeat = {}; (res.showdown || []).forEach(sd => handBySeat[sd.seat] = sd);

      const card = document.createElement('div'); card.className = 'modal-card';
      const board = h.result ? h.result.board : [];
      let html = `<h2>Hand #${h.handNumber} summary</h2>
        <div class="sub">Final board: ${board && board.length ? board.map(c => cardHTML(c, false)).join('') : '—'} · pot $${res.pot || 0}</div>`;

      // streets
      html += '<div class="hs-streets">';
      for (const st of h.streets) {
        if (!st.actions.length) continue;
        const boardStr = st.board && st.board.length ? st.board.map(c => cardHTML(c, false)).join('') : '<span class="muted">(no cards)</span>';
        const acts = st.actions.map(a => {
          const verb = a.action === 'post' ? `posts $${a.amount}`
            : a.action === 'raise' ? (a.opening ? `bets $${a.total}` : `raises to $${a.total}`)
            : a.action === 'call' ? `calls $${a.amount}`
            : a.action === 'check' ? 'checks'
            : a.action === 'fold' ? 'folds' : a.action;
          return `<span class="hs-act"><b>${escapeHTML(a.name)}</b> ${verb}</span>`;
        }).join('');
        const potAfter = st.actions.length ? st.actions[st.actions.length - 1].pot : 0;
        html += `<div class="hs-street"><div class="hs-st-head"><span class="hs-st-name">${st.name}</span> ${boardStr} <span class="muted">pot $${potAfter}</span></div><div class="hs-acts">${acts}</div></div>`;
      }
      html += '</div>';

      // results table
      html += `<table class="drill hs-table"><tr><th>Player</th><th>Hand</th><th>Start</th><th>End</th><th>Net</th></tr>`;
      for (const p of this.ctrl.game.players) {
        const start = startBySeat[p.seat] != null ? startBySeat[p.seat] : p.stack;
        const n = netBySeat[p.seat];
        const end = n ? n.stack : p.stack;
        const net = n ? n.net : 0;
        const sd = handBySeat[p.seat];
        const handCell = sd ? `${sd.hand.map(c => cardHTML(c, false)).join('')} <span class="muted">${sd.desc}</span>`
          : (p.seat === 0 && p.hand.length ? p.hand.map(c => cardHTML(c, false)).join('') : '<span class="muted">mucked</span>');
        const cls = net > 0 ? 'pos' : (net < 0 ? 'neg' : '');
        html += `<tr><td style="text-align:left">${escapeHTML(p.name)}</td><td style="text-align:left">${handCell}</td><td>$${start}</td><td>$${end}</td><td class="${cls}">${net >= 0 ? '+' : ''}$${net}</td></tr>`;
      }
      html += '</table><div class="modal-actions"></div>';
      card.innerHTML = html;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => this.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      return card;
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
