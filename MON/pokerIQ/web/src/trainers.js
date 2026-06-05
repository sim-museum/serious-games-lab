/*
 * PokerIQ — trainer/drill modals. Faithful ports of the standalone QDialogs in
 * pokerIQ.py: AKQ toy game (Chen Ch13), Jam-or-Fold (Nash), Indifference
 * visualiser (Chen Ch17), MTT bubble/ICM, Variance·Edge·Bankroll dashboard,
 * Calibration (Brier), Mindset coach (Hilger's seven attitudes), Range
 * narrowing (Bayes). Each returns an element to drop into the modal host.
 *
 * Depends on PokerEngine, PokerAnalytics. A small rng is injected for tests.
 */
(function (root) {
  'use strict';
  const isNode = (typeof require !== 'undefined' && typeof module !== 'undefined' && module.exports);
  const E = isNode ? require('./engine.js') : root.PokerEngine;
  const A = isNode ? require('./analytics.js') : root.PokerAnalytics;

  function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function shuffle(a, rng) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; } return a; }

  // ---- AKQ toy game (Chen Ch 13) ----
  function akqGame(ctx) {
    const rng = ctx.rng || Math.random;
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'AKQ Game'));
    wrap.appendChild(el('div', 'sub', 'Chen Ch 13 — three-card deck {A,K,Q}. Pot=2, bet=1. GTO: bettor value-bets A, checks K, bluffs Q ⅓ of the time; caller calls K ½ the time.'));
    const state = el('div', 'notice'); wrap.appendChild(state);
    const score = el('div', null); score.style.margin = '10px 0'; wrap.appendChild(score);
    const log = el('div', 'piq-feed'); log.style.height = '160px'; wrap.appendChild(log);
    const row = el('div', 'modal-actions'); wrap.appendChild(row);
    const dealBtn = el('button', 'btn check', 'Deal');
    const aBtn = el('button', 'btn raise', 'Bet'); aBtn.disabled = true;
    const bBtn = el('button', 'btn fold', 'Check'); bBtn.disabled = true;
    row.append(dealBtn, aBtn, bBtn, closeBtn(ctx));

    let net = 0, hands = 0, role = 'bettor', hero = null, bot = null;
    const idx = c => 'AKQ'.indexOf(c);
    const logLine = m => { log.insertBefore(el('div', null, m), log.firstChild); };
    const sync = () => { score.textContent = `Hands: ${hands}  |  Your net: ${net >= 0 ? '+' : ''}$${net.toFixed(2)}`; };
    sync();

    function deal() {
      const d = shuffle(['A', 'K', 'Q'], rng); hero = d[0]; bot = d[1];
      role = (hands % 2 === 0) ? 'bettor' : 'caller';
      dealBtn.disabled = true;
      if (role === 'bettor') {
        state.textContent = `You're the BETTOR. Your card: ${hero}. Bet (+1) or Check (showdown)?`;
        aBtn.textContent = 'Bet 1'; bBtn.textContent = 'Check'; aBtn.disabled = false; bBtn.disabled = false;
      } else {
        const ba = botBettor();
        if (ba === 'check') { state.textContent = `Bot (caller scenario) checked — free showdown.`; resolveCallerShowdown(); return; }
        state.textContent = `You're the CALLER. Your card: ${hero}. Bot BETS. Call or Fold?`;
        aBtn.textContent = 'Call'; bBtn.textContent = 'Fold'; aBtn.disabled = false; bBtn.disabled = false;
      }
    }
    const botBettor = () => bot === 'A' ? 'bet' : (bot === 'Q' ? (rng() < 1 / 3 ? 'bet' : 'check') : 'check');
    const botCaller = () => bot === 'A' ? 'call' : (bot === 'K' ? (rng() < 0.5 ? 'call' : 'fold') : 'fold');

    function act(which) {
      aBtn.disabled = bBtn.disabled = true; dealBtn.disabled = false;
      if (role === 'bettor') {
        if (which === 'a') { const bc = botCaller(); if (bc === 'fold') { net += 1; logLine(`You bet ${hero}, bot folds. +1`); } else if (idx(hero) < idx(bot)) { net += 2; logLine(`You bet ${hero}, bot calls ${bot}. +2`); } else { net -= 1; logLine(`You bet ${hero}, bot calls ${bot}. −1`); } }
        else { if (idx(hero) < idx(bot)) { net += 1; logLine(`Check SD: ${hero} beats ${bot}. +1`); } else { net -= 1; logLine(`Check SD: ${hero} loses to ${bot}. −1`); } }
      } else {
        if (which === 'a') { if (idx(hero) < idx(bot)) { net += 2; logLine(`You call ${hero}, bot ${bot}. +2`); } else { net -= 1; logLine(`You call ${hero}, bot ${bot}. −1`); } }
        else { net -= 1; logLine(`You fold ${hero} to bot's bet. −1`); }
      }
      hands++; sync();
    }
    function resolveCallerShowdown() { if (idx(hero) < idx(bot)) { net += 1; logLine(`Bot checked. ${hero} beats ${bot}. +1`); } else { net -= 1; logLine(`Bot checked. ${hero} loses to ${bot}. −1`); } hands++; sync(); dealBtn.disabled = false; }

    dealBtn.onclick = deal; aBtn.onclick = () => act('a'); bBtn.onclick = () => act('b');
    return wrap;
  }

  // ---- Jam-or-Fold (Nash push chart) ----
  function jamOrFold(ctx) {
    const rng = ctx.rng || Math.random;
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Jam-or-Fold Trainer'));
    wrap.appendChild(el('div', 'sub', 'Small blind, heads-up, effective stack shown. Push or fold? Compared to the Nash chart.'));
    const scn = el('div', 'notice'); wrap.appendChild(scn);
    const sc = el('div', null); sc.style.margin = '10px 0'; wrap.appendChild(sc);
    const fb = el('div', 'piq-feed'); fb.style.height = '160px'; wrap.appendChild(fb);
    const row = el('div', 'modal-actions'); wrap.appendChild(row);
    const push = el('button', 'btn raise', 'PUSH ALL-IN'); const fold = el('button', 'btn fold', 'FOLD');
    row.append(push, fold, closeBtn(ctx));
    let correct = 0, total = 0, cur = null;
    function next() {
      const stack = [5, 7, 10, 12, 15, 20][Math.floor(rng() * 6)];
      const deck = shuffle(E.fullDeck().slice(), rng);
      const hole = [deck[0], deck[1]];
      const pctile = A.handStrengthPercentile(hole);
      const band = A.nashPushPct(stack);
      cur = { stack, hole, pctile, band, truth: pctile >= (1 - band) ? 'push' : 'fold' };
      scn.textContent = `Stack: ${stack} bb     Hand: ${E.cardToStr(hole[0])} ${E.cardToStr(hole[1])}`;
    }
    function answer(choice) {
      if (!cur) return; total++;
      const ok = choice === cur.truth; if (ok) correct++;
      const line = `#${total} [${cur.stack}bb ${E.cardToStr(cur.hole[0])}${E.cardToStr(cur.hole[1])}, you ${choice.toUpperCase()}] — ${ok ? '✓ correct' : '✗ Nash says ' + cur.truth.toUpperCase()} (top ${Math.round(cur.band * 100)}%, strength ${cur.pctile.toFixed(2)})`;
      fb.insertBefore(el('div', ok ? 'pos' : 'neg', line), fb.firstChild);
      sc.textContent = `Score: ${correct} / ${total}`;
      next();
    }
    push.onclick = () => answer('push'); fold.onclick = () => answer('fold');
    next(); sc.textContent = 'Score: 0 / 0';
    return wrap;
  }

  // ---- Indifference / bluff-frequency visualiser ----
  function indifference(ctx) {
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Indifference Visualiser'));
    wrap.appendChild(el('div', 'sub', 'Pot = $100, villain bets $X, hero holds a bluff-catcher. Find the bluff% where EV(call)=EV(fold) = Pot/(Pot+Bet).'));
    const mkSlider = (label, min, max, val) => {
      const r = el('div'); r.style.cssText = 'display:flex;gap:10px;align-items:center;margin:8px 0;';
      const cap = el('span', 'muted', label); cap.style.width = '120px';
      const s = el('input'); s.type = 'range'; s.min = min; s.max = max; s.value = val; s.style.flex = '1'; s.style.accentColor = '#d9b25b';
      const out = el('span'); out.style.cssText = 'width:60px;color:#d9b25b;font-weight:700;';
      r.append(cap, s, out); return { r, s, out };
    };
    const bet = mkSlider('Bet size $', 10, 300, 75);
    const bluff = mkSlider('Villain bluff %', 0, 100, 33);
    wrap.append(bet.r, bluff.r);
    const res = el('div', 'notice'); res.style.lineHeight = '1.6'; wrap.appendChild(res);
    wrap.appendChild(el('div', 'modal-actions').appendChild(closeBtn(ctx)).parentNode);
    function refresh() {
      const pot = 100, b = +bet.s.value, bl = +bluff.s.value / 100;
      bet.out.textContent = '$' + b; bluff.out.textContent = Math.round(bl * 100) + '%';
      const evCall = bl * (pot + b) + (1 - bl) * (-b);
      const indiff = pot / (pot + b);
      const verdict = Math.abs(bl - indiff) < 0.02 ? 'Indifferent — pure Nash.'
        : (bl > indiff ? 'Hero PROFITS by calling (villain over-bluffs).' : 'Hero LOSES by calling (villain under-bluffs).');
      res.innerHTML = `Pot $100, bet $${b}<br>EV(call) = ${bl.toFixed(2)}·${pot + b} + ${(1 - bl).toFixed(2)}·(${-b}) = <b>$${evCall.toFixed(2)}</b><br>EV(fold) = $0.00<br>Nash bluff% = pot/(pot+bet) = <b>${(indiff * 100).toFixed(1)}%</b><br><br><b>${verdict}</b>`;
    }
    bet.s.oninput = refresh; bluff.s.oninput = refresh; refresh();
    return wrap;
  }

  // ---- MTT bubble / ICM drill ----
  function mttBubble(ctx) {
    const rng = ctx.rng || Math.random;
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'MTT Bubble Drill (ICM)'));
    wrap.appendChild(el('div', 'sub', '4 left, 3 cash ($500/$300/$200). You are 3rd in chips; a big stack shoves. Calls that are +ChipEV can be −$EV on the bubble.'));
    const scn = el('div', 'notice'); wrap.appendChild(scn);
    const fb = el('div', 'piq-feed'); fb.style.height = '170px'; wrap.appendChild(fb);
    const row = el('div', 'modal-actions'); wrap.appendChild(row);
    const call = el('button', 'btn call', 'CALL'); const fold = el('button', 'btn fold', 'FOLD');
    row.append(call, fold, closeBtn(ctx));
    let round = 0, eq = 0;
    function next() { eq = 0.30 + rng() * 0.25; scn.textContent = `Hero equity if called: ${Math.round(eq * 100)}%  (chip pot-odds say call > 30%).`; }
    function answer(choice) {
      round++;
      const chipEv = eq - (1 - eq);
      const icmEv = eq * 0.5 - (1 - eq);
      const truth = icmEv > 0 ? 'call' : 'fold'; const ok = choice === truth;
      fb.insertBefore(el('div', ok ? 'pos' : 'neg',
        `Round ${round} [eq ${Math.round(eq * 100)}%, you ${choice.toUpperCase()}] — ${ok ? '✓ correct (ICM)' : '✗ chip-EV ≠ $-EV'} · ChipEV ${chipEv >= 0 ? '+' : ''}${chipEv.toFixed(2)} / $-EV ${icmEv >= 0 ? '+' : ''}${icmEv.toFixed(2)}`), fb.firstChild);
      next();
    }
    call.onclick = () => answer('call'); fold.onclick = () => answer('fold'); next();
    return wrap;
  }

  // ---- Variance · Edge · Bankroll dashboard ----
  function variance(ctx) {
    const s = ctx.stats; const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Variance · Edge · Bankroll'));
    wrap.appendChild(el('div', 'sub', 'Session + lifetime stats. Risk-of-ruin and Kelly per Chen Ch22/24. Lifetime numbers persist via localStorage.'));
    const brRow = el('div'); brRow.style.cssText = 'display:flex;gap:10px;align-items:center;margin-bottom:12px;';
    brRow.appendChild(el('span', 'muted', 'Bankroll $'));
    const safeStore = root.__piqStore || { getItem: () => null, setItem: () => {} };
    const br = el('input'); br.type = 'number'; br.value = parseInt(safeStore.getItem('piq.bankroll') || '2000', 10);
    br.style.cssText = 'width:120px;padding:6px;background:#0d141c;color:#eef3f7;border:1px solid #243;border-radius:6px;';
    brRow.appendChild(br); wrap.appendChild(brRow);
    const body = el('div', 'kv'); wrap.appendChild(body);
    function refresh() {
      const b = +br.value || 0;
      safeStore.setItem('piq.bankroll', b);
      const [lo, hi] = s.edgeConfidenceInterval();
      const ror = s.riskOfRuin(b), kelly = s.kellyFraction();
      const rows = [
        ['Session hands', s.sessionHands],
        ['Session bb/100', fmt(s.sessionBbPer100, 1, true)],
        ['Session σ ($/hand)', s.sessionStd.toFixed(2)],
        ['Lifetime hands', s.lifetimeHands],
        ['Lifetime profit', '$' + s.lifetimeProfit.toFixed(0)],
        ['Lifetime bb/100', fmt(s.lifetimeBbPer100, 1, true)],
        ['Edge 95% CI', `[${fmt(lo, 1, true)}, ${fmt(hi, 1, true)}] bb/100`],
        ['Risk of ruin', (ror * 100).toFixed(1) + '%'],
        ['Kelly fraction', kelly.toFixed(3)],
        ['½-Kelly buy-in', '$' + Math.max(20, kelly * b * 0.5).toFixed(0)],
      ];
      body.innerHTML = rows.map(([k, v]) => `<div class="k">${k}</div><div>${v}</div>`).join('');
    }
    br.oninput = refresh; refresh();
    wrap.appendChild(el('div', 'modal-actions').appendChild(closeBtn(ctx)).parentNode);
    return wrap;
  }

  // ---- Calibration (Brier) ----
  function calibration(ctx) {
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Calibration — Brier score'));
    const preds = ctx.predictions || [];
    const body = el('div', 'notice');
    if (!preds.length) body.innerHTML = 'No equity predictions logged this session. As you act, predicted-vs-actual outcomes feed a Brier score (0 = perfect, 0.25 = chance).';
    else {
      const brier = preds.reduce((a, [p, o]) => a + (p - o) * (p - o), 0) / preds.length;
      body.innerHTML = `Predictions: <b>${preds.length}</b><br>Brier score: <b>${brier.toFixed(4)}</b><br>Calibration: <b>${((1 - 4 * brier) * 100).toFixed(1)}%</b> (higher better; same rule weather forecasters use).`;
    }
    wrap.appendChild(body);
    wrap.appendChild(el('div', 'modal-actions').appendChild(closeBtn(ctx)).parentNode);
    return wrap;
  }

  // ---- Mindset coach (Hilger seven attitudes) ----
  const SEVEN = ['Accept variance', 'Play the long term', 'Process over outcomes', 'Desensitise to money', 'Leave ego at the door', 'Remove emotion from decisions', 'Continuous analysis'];
  function mindset(ctx) {
    const s = ctx.stats; const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Mindset Coach'));
    wrap.appendChild(el('div', 'sub', "Hilger's seven attitudes, scored from this session's play + your check-ins."));
    const decSigma = (s.decisionTimes.length > 1) ? std(s.decisionTimes) : 0;
    const statuses = [
      `${s.sessionHands} hands — variance is real`,
      `Lifetime n = ${s.lifetimeHands}`,
      `process tracked via EV verdicts`,
      `buy-in fixed each hand`,
      `bb/100 ${fmt(s.sessionBbPer100, 1, true)} — detach from swings`,
      `decision-time σ: ${decSigma.toFixed(2)}s`,
      `keep journaling & reviewing`,
    ];
    const tbl = el('table', 'drill');
    tbl.innerHTML = '<tr><th>Attitude</th><th>Session status</th></tr>' +
      SEVEN.map((a, i) => `<tr><td style="text-align:left"><b>${a}</b></td><td style="text-align:left">${statuses[i]}</td></tr>`).join('');
    wrap.appendChild(tbl);
    wrap.appendChild(el('div', 'modal-actions').appendChild(closeBtn(ctx)).parentNode);
    return wrap;
  }

  // ---- Range narrowing (Bayes walkthrough) ----
  function rangeNarrowing(ctx) {
    const wrap = el('div', 'modal-card');
    wrap.appendChild(el('h2', null, 'Range Narrowing (Bayes)'));
    wrap.appendChild(el('div', 'sub', 'Each villain action this hand trims the prior range: P(hand|action) ∝ P(action|hand)·P(hand).'));
    const text = el('div', 'piq-feed'); text.style.height = '220px';
    let pct = 100; const lines = [];
    for (const act of (ctx.actionHistory || []).slice(0, 30)) {
      const a = String(act).toLowerCase();
      if (a.includes('fold')) continue;
      if (a.includes('rais') || a.includes('bet') || a.includes('all-in')) { pct *= 0.25; lines.push(`${act} → ~${pct.toFixed(1)}% (raise narrows hard)`); }
      else if (a.includes('call')) { pct *= 0.55; lines.push(`${act} → ~${pct.toFixed(1)}% (call narrows)`); }
      else if (a.includes('check')) { pct *= 0.95; lines.push(`${act} → ~${pct.toFixed(1)}% (check barely narrows)`); }
    }
    if (!lines.length) lines.push('(no actions in the last hand to narrow)');
    text.innerHTML = lines.map(l => `<div>${l}</div>`).join('');
    wrap.appendChild(text);
    wrap.appendChild(el('div', 'modal-actions').appendChild(closeBtn(ctx)).parentNode);
    return wrap;
  }

  // helpers
  function closeBtn(ctx) { const b = el('button', 'ghost', 'Close'); b.onclick = () => ctx.close && ctx.close(); return b; }
  function fmt(v, d, sign) { const s = v.toFixed(d); return (sign && v >= 0 ? '+' : '') + s; }
  function std(arr) { const n = arr.length; const m = arr.reduce((a, b) => a + b, 0) / n; return Math.sqrt(arr.reduce((a, x) => a + (x - m) * (x - m), 0) / n); }

  const REGISTRY = {
    akq: { label: 'AKQ Toy Game (Chen Ch13)', build: akqGame },
    jam: { label: 'Jam-or-Fold (Nash)', build: jamOrFold },
    indiff: { label: 'Indifference Visualiser', build: indifference },
    mtt: { label: 'MTT Bubble / ICM', build: mttBubble },
    variance: { label: 'Variance · Edge · Bankroll', build: variance },
    calibration: { label: 'Calibration (Brier)', build: calibration },
    mindset: { label: 'Mindset Coach', build: mindset },
    range: { label: 'Range Narrowing (Bayes)', build: rangeNarrowing },
  };

  const FINANCE_TOOLTIPS = {
    SPR: 'Stack-to-Pot Ratio — below 1 you are effectively all-in.',
    MDF: 'Minimum Defense Frequency — defend enough that bluffs break even.',
    Kelly: 'Bet sizing from edge/variance: f* = μ/σ². Half-Kelly is the practical ceiling.',
    'Pot Odds': 'Price laid / total pot. Compare to equity to call or fold.',
    Equity: 'Long-run win probability via Monte-Carlo sampling.',
    Brier: 'Mean-squared error of probability forecasts (0 perfect, 0.25 chance).',
  };

  const API = { REGISTRY, FINANCE_TOOLTIPS };
  if (isNode) module.exports = API;
  else root.PokerTrainers = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
