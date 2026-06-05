/*
 * PokerIQ — analytics layer. Ports the poker-math + tracking classes from
 * pokerIQ.py: classify_board, sklansky_distance, nash_push_pct,
 * hand_strength_percentile, hero_action_ev, SessionStats, DecisionJournal,
 * OpponentModel, TiltDetector. Persistence uses localStorage (was QSettings).
 *
 * Book references preserved in the original are kept in comments.
 */
(function (root) {
  'use strict';
  const E = (typeof require !== 'undefined') ? require('./engine.js') : root.PokerEngine;

  // Safe storage: real localStorage when usable, in-memory fallback otherwise.
  // Note `typeof localStorage` can be 'object' yet *throw* on access (opaque
  // origins, private mode, file:// in some browsers) — so we probe with a real
  // read/write inside try/catch, not just a typeof check.
  const store = (function () {
    try {
      const t = '__piq_probe__';
      localStorage.setItem(t, '1'); localStorage.removeItem(t);
      return localStorage;
    } catch (e) {
      const m = {};
      return { getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: k => { delete m[k]; } };
    }
  })();
  const LS = {
    getNum: (k, d) => { try { const v = store.getItem(k); return v == null ? d : parseFloat(v); } catch (e) { return d; } },
    getStr: (k, d) => { try { const v = store.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set: (k, v) => { try { store.setItem(k, v); } catch (e) {} },
  };
  // export the safe store so other modules (trainers/main) reuse it
  if (typeof root !== 'undefined') root.__piqStore = store;

  const RANK_ORDER = 'AKQJT98765432';
  const cardStr = c => E.cardToStr(c);          // 'Ah'
  const rankChar = c => cardStr(c)[0];
  const suitChar = c => cardStr(c)[1];

  // ---- board texture (Acevedo Ch 11) ----
  function classifyBoard(board) {
    if (!board || board.length < 3) return { label: 'preflop', cbet: '' };
    const cards = board.slice(0, 3);
    const ranks = cards.map(rankChar);
    const suits = cards.map(suitChar);
    const paired = new Set(ranks).size < 3;
    const suitCounts = {}; suits.forEach(s => suitCounts[s] = (suitCounts[s] || 0) + 1);
    const maxSuit = Math.max(...Object.values(suitCounts));
    const flushy = maxSuit >= 2;
    const monotone = maxSuit === 3;
    const idxs = ranks.map(r => RANK_ORDER.indexOf(r)).sort((a, b) => a - b);
    const spread = idxs[idxs.length - 1] - idxs[0];
    const connected = spread <= 4 && new Set(ranks).size === 3;

    let label;
    if (paired) label = 'paired';
    else if (monotone) label = 'wet (monotone)';
    else if (flushy && connected) label = 'wet & dynamic';
    else if (flushy || connected) label = 'dynamic';
    else label = 'dry';

    let cbet;
    if (label === 'dry') cbet = 'small (33% pot) — range bet, you have range advantage';
    else if (label === 'paired') cbet = 'small (33% pot) — paired boards favour the pre-flop raiser';
    else if (label.includes('dynamic') || label.includes('wet')) cbet = 'big (66-75% pot) — polarised; charge draws';
    else cbet = 'mixed (~50% pot)';
    return { label, cbet, paired, flushy, connected };
  }

  // ---- Sklansky distance (Theory of Poker Ch 3) ----
  function sklanskyDistance(aAct, aAmt, pAct, pAmt, pot) {
    if (!aAct || !pAct) return 0;
    const aa = aAct[0].toLowerCase(), pa = pAct[0].toLowerCase();
    if (aa === pa) {
      if (aa === 'r') { const denom = Math.max(1, pot || pAmt || 1); return Math.min(10, Math.abs(aAmt - pAmt) / denom * 5); }
      return 0;
    }
    const pairs = { 'f,c': 6, 'c,f': 6, 'f,r': 9, 'r,f': 9, 'c,r': 4, 'r,c': 4 };
    return pairs[`${aa},${pa}`] != null ? pairs[`${aa},${pa}`] : 8;
  }

  // ---- Nash push chart (SnapShove-style top-percent by stack bb) ----
  const NASH = { 5: 0.45, 6: 0.40, 7: 0.35, 8: 0.30, 9: 0.27, 10: 0.25, 12: 0.22, 15: 0.18, 18: 0.15, 20: 0.13, 25: 0.10 };
  function nashPushPct(stackBb) {
    const keys = Object.keys(NASH).map(Number).sort((a, b) => a - b);
    if (stackBb <= keys[0]) return NASH[keys[0]];
    if (stackBb >= keys[keys.length - 1]) return NASH[keys[keys.length - 1]];
    for (const k of keys) if (k >= stackBb) return NASH[k];
    return 0.10;
  }

  // ---- preflop strength percentile (1.0 = AA, 0 = 72o) ----
  const RV = { A: 12, K: 11, Q: 10, J: 9, T: 8, 9: 7, 8: 6, 7: 5, 6: 4, 5: 3, 4: 2, 3: 1, 2: 0 };
  function handStrengthPercentile(hole) {
    if (!hole || hole.length < 2) return 0;
    const c1 = cardStr(hole[0]), c2 = cardStr(hole[1]);
    const r1 = RV[c1[0]] || 0, r2 = RV[c2[0]] || 0;
    const suited = c1[1] === c2[1], pair = r1 === r2;
    let score;
    if (pair) score = 0.55 + (r1 / 12) * 0.45;
    else {
      const hi = Math.max(r1, r2), lo = Math.min(r1, r2);
      const gap = hi > lo ? (hi - lo - 1) : 0;
      score = (hi / 12) * 0.55 + (lo / 12) * 0.25 - gap * 0.03 + (suited ? 0.08 : 0);
    }
    return Math.max(0, Math.min(1, score));
  }

  // ---- EV of each hero action ($), ported from hero_action_ev ----
  // ctx: { pot, currentBet, betInRound, board(len), playerStack, oppStacks[] }
  function heroActionEV(ctx, actionCode, equity, raiseAmount) {
    const pot = ctx.pot, toCall = Math.max(0, ctx.currentBet - ctx.betInRound);
    const bb = ctx.bb || 2;
    const boardN = ctx.board || 0;
    let implCall, implRaise;
    if (boardN === 0) { implCall = 0.30; implRaise = 0.15; }
    else if (boardN === 3) { implCall = 0.40; implRaise = 0.20; }
    else if (boardN === 4) { implCall = 0.25; implRaise = 0.12; }
    else { implCall = 0.0; implRaise = 0.0; }
    const oppStacks = (ctx.oppStacks || []).filter(s => s > 0);
    const avgOpp = oppStacks.length ? oppStacks.reduce((a, b) => a + b, 0) / oppStacks.length : 0;
    const eff = avgOpp > 0 ? Math.min(ctx.playerStack, avgOpp) : 0;
    const impliedCallPot = eff * implCall, impliedRaisePot = eff * implRaise;

    if (actionCode === 'f') return 0;
    if (actionCode === 'c') return toCall <= 0 ? 0 : equity * (pot + toCall + impliedCallPot) - toCall;
    if (actionCode === 'r') {
      const left = Math.max(1, oppStacks.length);
      const perFold = ctx.currentBet > 2 * bb ? 0.25 : 0.40;
      const allFold = Math.pow(perFold, left);
      const discEq = equity * 0.70;
      const raiseAbove = Math.max(raiseAmount || 0, toCall + bb * 2);
      const cost = toCall + raiseAbove;
      const calledPot = pot + cost + raiseAbove;
      return allFold * pot + (1 - allFold) * (discEq * (calledPot + impliedRaisePot) - cost);
    }
    return 0;
  }

  // ---- SessionStats ----
  class SessionStats {
    constructor(bbAmount) {
      this.handResults = [];
      this.bbAmount = bbAmount || 2;
      this.decisionTimes = [];
      this._actionStart = null;
      this.lifetimeHands = LS.getNum('piq.life.hands', 0);
      this.lifetimeProfit = LS.getNum('piq.life.profit', 0);
      this.lifetimeSumsq = LS.getNum('piq.life.sumsq', 0);
    }
    _save() {
      LS.set('piq.life.hands', this.lifetimeHands);
      LS.set('piq.life.profit', this.lifetimeProfit);
      LS.set('piq.life.sumsq', this.lifetimeSumsq);
    }
    recordHandResult(profit) {
      this.handResults.push(profit);
      this.lifetimeHands += 1; this.lifetimeProfit += profit; this.lifetimeSumsq += profit * profit;
      this._save();
    }
    recordDecisionTime(s) { this.decisionTimes.push(s); if (this.decisionTimes.length > 200) this.decisionTimes.shift(); }
    actionStarted() { this._actionStart = (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000; }
    actionFinished() { if (this._actionStart != null) { const now = (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000; this.recordDecisionTime(now - this._actionStart); this._actionStart = null; } }
    get sessionHands() { return this.handResults.length; }
    get sessionBbPer100() {
      if (!this.handResults.length || this.bbAmount <= 0) return 0;
      const bbSum = this.handResults.reduce((a, b) => a + b, 0) / this.bbAmount;
      return bbSum / Math.max(1, this.sessionHands) * 100;
    }
    get sessionStd() {
      const n = this.handResults.length; if (n < 2) return 0;
      const m = this.handResults.reduce((a, b) => a + b, 0) / n;
      const v = this.handResults.reduce((a, x) => a + (x - m) * (x - m), 0) / (n - 1);
      return Math.sqrt(v);
    }
    get lifetimeBbPer100() {
      if (this.lifetimeHands === 0 || this.bbAmount <= 0) return 0;
      return this.lifetimeProfit / this.bbAmount / Math.max(1, this.lifetimeHands) * 100;
    }
    get lifetimeStd() {
      const n = this.lifetimeHands; if (n < 2) return 0;
      const mean = this.lifetimeProfit / n;
      const v = Math.max(0, this.lifetimeSumsq / n - mean * mean);
      return Math.sqrt(v);
    }
    edgeConfidenceInterval() {
      const n = this.lifetimeHands; if (n < 30) return [0, 0];
      const sigma = this.lifetimeStd / Math.max(1, this.bbAmount);
      const se = sigma / Math.sqrt(n);
      const edge = this.lifetimeBbPer100 / 100;
      return [(edge - 1.96 * se) * 100, (edge + 1.96 * se) * 100];
    }
    riskOfRuin(bankroll) {
      if (this.lifetimeHands < 100) return 1;
      const mean = this.lifetimeProfit / this.lifetimeHands; if (mean <= 0) return 1;
      const v = this.lifetimeStd ** 2; if (v <= 0) return 1;
      return Math.exp(-2 * mean * bankroll / v);
    }
    kellyFraction() {
      if (this.lifetimeHands < 100 || this.lifetimeStd <= 0) return 0;
      const mean = this.lifetimeProfit / this.lifetimeHands;
      return Math.max(0, mean / (this.lifetimeStd ** 2));
    }
  }

  // ---- OpponentModel (localStorage-backed) ----
  class OpponentModel {
    constructor() {
      this.stats = {};
      try { const raw = LS.getStr('piq.oppStats', ''); if (raw) this.stats = JSON.parse(raw); } catch (e) { this.stats = {}; }
    }
    _save() { try { LS.set('piq.oppStats', JSON.stringify(this.stats)); } catch (e) {} }
    _slot(name) {
      if (!this.stats[name]) this.stats[name] = { hands: 0, vpip: 0, pfr: 0, fold_to_3bet: 0, faced_3bet: 0, raises: 0, calls: 0, checks: 0, folds: 0, river_calls: 0, river_faced_bet: 0 };
      return this.stats[name];
    }
    recordAction(name, action, street, faced3bet, facedRiverBet) {
      const s = this._slot(name), a = (action || '').toLowerCase();
      if (a.startsWith('rais') || a.startsWith('bet')) { s.raises++; if (street === 'Preflop') { s.pfr++; s.vpip++; } }
      else if (a.startsWith('call')) { s.calls++; if (street === 'Preflop') s.vpip++; if (street === 'River' && facedRiverBet) s.river_calls++; }
      else if (a.startsWith('check')) s.checks++;
      else if (a.startsWith('fold')) { s.folds++; if (faced3bet) s.fold_to_3bet++; }
      if (faced3bet) s.faced_3bet++;
      if (street === 'River' && facedRiverBet) s.river_faced_bet++;
      this._save();
    }
    recordHand(name) { this._slot(name).hands++; this._save(); }
    levelOf(name) {
      const s = this.stats[name]; if (!s || s.hands < 10) return 1;
      const agg = s.raises / Math.max(1, s.raises + s.calls + s.checks + s.folds);
      if (agg < 0.05) return 0; if (agg < 0.20) return 1; if (agg < 0.35) return 2; return 3;
    }
    biggestLeak(name) {
      const s = this.stats[name]; if (!s || s.hands < 5) return null;
      const total = s.raises + s.calls + s.checks + s.folds; if (total === 0) return null;
      const foldPct = s.folds / total;
      if (s.faced_3bet >= 3) { const f = s.fold_to_3bet / Math.max(1, s.faced_3bet); if (f > 0.75) return `folds to 3-bet ${pct(f)} — widen 3-bet bluffs`; }
      if (foldPct > 0.6) return `folds ${pct(foldPct)} — c-bet a lot, value-bet thinner`;
      if (s.river_faced_bet >= 3) { const rc = s.river_calls / Math.max(1, s.river_faced_bet); if (rc > 0.65) return `calls river ${pct(rc)} — never bluff, value-bet wider`; if (rc < 0.20) return `folds river ${pct(rc)} — increase river bluffs`; }
      if (s.raises / Math.max(1, total) > 0.3) return 'raises heavily — slow-play monsters, induce bluffs';
      return null;
    }
  }
  const pct = f => Math.round(f * 100) + '%';

  // ---- TiltDetector (decision-time spike heuristic) ----
  class TiltDetector {
    constructor() { this.baseline = null; }
    update(times) {
      if (!times || times.length < 5) return { tilted: false, note: 'gathering baseline' };
      const recent = times.slice(-5);
      const mean = times.reduce((a, b) => a + b, 0) / times.length;
      const rMean = recent.reduce((a, b) => a + b, 0) / recent.length;
      if (rMean < mean * 0.45) return { tilted: true, note: 'snap-decisions — possible tilt/autopilot' };
      if (rMean > mean * 2.0) return { tilted: true, note: 'long tank times — frustration/uncertainty' };
      return { tilted: false, note: 'decision pace steady' };
    }
  }

  // ---- ToM range estimates (from TextModeGame.STYLE_RANGES) ----
  const STYLE_RANGES = {
    tight: { open: 'TT+, AQs+, AKo', call: '77+, ATs+, KQs, AJo+', bet: 'Top pair+, strong draws' },
    loose: { open: '22+, Axs, Kxs, QTs+, JTs..98s, A2o+, K9o+, QTo+', call: 'Any pair/suited/connector/broadway', bet: 'Any pair, any draw, sometimes air' },
    station: { open: 'Any pair, any ace, suited kings', call: 'Anything with a piece or draw', bet: 'Only strong made hands' },
    aggressive: { open: '55+, A2s+, K9s+, QTs+, JTs, T9s, A9o+, KTo+, QJo', call: '22+, suited connectors, broadways', bet: 'Wide — pairs, draws, air' },
    optimal: { open: '77+, A2s+, KTs+, QJs, ATo+, KQo', call: '55+, suited connectors, suited aces', bet: 'Balanced — value and bluffs' },
    shark: { open: 'Balanced ~17% — pairs, suited broadways, SCs', call: 'Polarised, position-aware', bet: 'Polarised value+bluff, mixed sizings' },
    exploit: { open: 'Table-dependent (wider vs nits)', call: 'Targets the weakest range at the table', bet: 'Sizes up vs stations, bluffs more vs nits' },
    icm: { open: 'Push/fold by stack — Nash jam range', call: 'Tight; survival-weighted', bet: 'Shove or check, little in between' },
    tom: { open: 'Adapts to table', call: 'Adapts to opponent', bet: 'Exploitative' },
  };
  function rangeFor(style, street) {
    const r = STYLE_RANGES[style] || STYLE_RANGES.optimal;
    return street === 'Preflop' ? r.open : r.bet;
  }

  const API = {
    classifyBoard, sklanskyDistance, nashPushPct, handStrengthPercentile, heroActionEV,
    SessionStats, OpponentModel, TiltDetector, STYLE_RANGES, rangeFor,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerAnalytics = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
