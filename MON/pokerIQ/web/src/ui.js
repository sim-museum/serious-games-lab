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
            <button data-act="tells" class="ghost">Tells</button>
            <button data-act="god" class="ghost">God</button>
            <button data-act="trainers" class="ghost">Trainers ▾</button>
            <button data-act="stats" class="ghost">Stats</button>
            <button data-act="help" class="ghost">?</button>
          </div>
        </div>
        <div class="piq-felt">
          <div class="piq-board" id="piq-board"></div>
          <div class="piq-pot" id="piq-pot"></div>
          <div class="piq-seats" id="piq-seats"></div>
          <div class="piq-result" id="piq-result" style="display:none"></div>
        </div>
        <div class="piq-bottom">
          <div class="piq-feed" id="piq-feed"></div>
          <div class="piq-advisor" id="piq-advisor"></div>
          <div class="piq-actions" id="piq-actions"></div>
        </div>
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
      };
      this.root.querySelector('.piq-menu').addEventListener('click', e => {
        const act = e.target.getAttribute('data-act'); if (!act) return;
        if (act === 'god') { this.ctrl.godMode = !this.ctrl.godMode; this.ctrl.render(); }
        else if (act === 'tells') { this.ctrl.showTells = !this.ctrl.showTells; this.ctrl.render(); }
        else if (this.onMenu) this.onMenu(act);
      });
    }

    render(s) {
      this.el.hand.textContent = `Hand #${s.handNumber} · ${s.street}`;
      this.el.blinds.textContent = `Blinds $${s.sb}/$${s.bb}`;
      this.el.session.textContent = `Session ${s.session.hands}h · ${s.session.bb100 >= 0 ? '+' : ''}${s.session.bb100.toFixed(1)} bb/100`;

      // board
      this.el.board.innerHTML = s.board.map(c => cardHTML(c, false)).join('') ||
        '<span class="muted">— preflop —</span>';
      this.el.pot.innerHTML = `<span class="chip"></span> Pot $${s.pot}`;

      // seats
      this.el.seats.innerHTML = s.players.map(p => this.seatHTML(p, s)).join('');

      // feed
      this.el.feed.innerHTML = s.events.map(e => `<div>${escapeHTML(e)}</div>`).join('');

      // advisor
      this.el.advisor.innerHTML = s.advisor ? this.advisorHTML(s.advisor) : '';

      // actions
      this.el.actions.innerHTML = '';
      if (s.awaitingHero && s.legal) this.buildActions(s.legal);
      else if (!s.handResult) this.el.actions.innerHTML = '<span class="muted">…bots acting</span>';

      // result overlay
      if (s.handResult) this.showResult(s.handResult, s); else this.el.result.style.display = 'none';

      // toggle button states
      this.root.querySelector('[data-act="god"]').classList.toggle('on', s.godMode);
      this.root.querySelector('[data-act="tells"]').classList.toggle('on', s.showTells);
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

    buildActions(legal) {
      const wrap = this.el.actions;
      const mk = (label, cls, fn) => { const b = document.createElement('button'); b.className = cls; b.innerHTML = label; b.onclick = fn; wrap.appendChild(b); return b; };
      mk('Fold', 'btn fold', () => this.ctrl.act('f', 0));
      if (legal.canCheck) mk('Check', 'btn check', () => this.ctrl.act('c', 0));
      else mk(`Call $${legal.toCall}`, 'btn call', () => this.ctrl.act('c', 0));
      if (legal.canRaise) {
        const slider = document.createElement('input');
        slider.type = 'range'; slider.min = legal.minRaiseTo; slider.max = legal.maxRaiseTo;
        slider.value = Math.min(legal.maxRaiseTo, Math.max(legal.minRaiseTo, Math.floor(legal.pot * 0.66) + legal.toCall));
        const out = document.createElement('span'); out.className = 'raise-amt';
        const sync = () => { out.textContent = '$' + slider.value; };
        slider.oninput = sync; sync();
        const raiseBtn = mk('Raise to', 'btn raise', () => this.ctrl.act('r', parseInt(slider.value, 10)));
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
