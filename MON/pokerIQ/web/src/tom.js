/*
 * PokerIQ — Theory of Mind training screen (renderer). Builds the rich
 * analysis view shown when Training is ON: board/hand strip, the
 * Pot/Equity/PotOdds/Implied metric strip, Outs/Scare row, range-mode radio,
 * tabs (Advisor / Hero / per-opponent), the 13×13 range grids, the 4×13 outs
 * board, and the 3×3 decision-metric dashboard.
 *
 * Pure function of a tomData snapshot produced by the Controller (ui.js).
 * Depends on PokerEngine, PokerToMLogic. cardHTML reused from PokerUI.
 */
(function (root) {
  'use strict';
  const isNode = (typeof require !== 'undefined' && typeof module !== 'undefined' && module.exports);
  const E = isNode ? require('./engine.js') : root.PokerEngine;
  const T = isNode ? require('./tomlogic.js') : root.PokerToMLogic;

  const SUIT_GLYPH = { c: '♣', d: '♦', h: '♥', s: '♠' };
  const SUIT_CLASS = { c: 'club', d: 'diamond', h: 'heart', s: 'spade' };
  function cardHTML(card, hidden) {
    if (hidden) return '<span class="card back"></span>';
    const s = E.cardToStr(card), r = s[0], su = s[1];
    return `<span class="card ${SUIT_CLASS[su]}"><b>${r === 'T' ? '10' : r}</b><i>${SUIT_GLYPH[su]}</i></span>`;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  // 13×13 range grid (HandRangeGrid) as a CSS grid
  function rangeGridHTML(range, boardHits) {
    const R = T.RANKS; let cells = '';
    for (let i = 0; i < 13; i++) for (let j = 0; j < 13; j++) {
      let hand, fam;
      if (i < j) { hand = R[i] + R[j] + 's'; fam = 'suited'; }
      else if (i > j) { hand = R[j] + R[i] + 'o'; fam = 'offsuit'; }
      else { hand = R[i] + R[j]; fam = 'pair'; }
      const w = Math.max(0, Math.min(1, range[hand] || 0));
      const hit = (boardHits && boardHits[hand]) || 0;
      const ring = (hit >= 0.6 && w > 0) ? (hit >= 0.85 ? ' hit2' : ' hit1') : '';
      const lit = w > 0.5 ? ' lit' : '';
      cells += `<div class="rg-cell ${fam}${ring}${lit}" style="--w:${w.toFixed(2)}">${hand}</div>`;
    }
    return `<div class="range-grid">${cells}</div>`;
  }

  // 4×13 outs board (HeroOutsTab deck grid)
  function outsBoardHTML(hand, board, outsSet) {
    const suits = ['s', 'h', 'd', 'c'], R = T.RANKS;
    const used = {}; (hand || []).forEach(c => used[E.cardToStr(c)] = 'hole');
    (board || []).forEach(c => used[E.cardToStr(c)] = 'board');
    let rows = '';
    for (const s of suits) {
      let row = `<div class="ob-head">${SUIT_GLYPH[s]}</div>`;
      for (const r of R) {
        const key = r + s; const role = used[key] || (outsSet && outsSet.has(key) ? 'out' : 'dim');
        row += `<div class="ob-cell ${role}">${r}</div>`;
      }
      rows += `<div class="ob-row">${row}</div>`;
    }
    return `<div class="outs-board">${rows}</div>`;
  }

  // a single dashboard metric tile (MetricPie card style)
  function tile(label, value, frac, color, dim) {
    const pct = Math.max(0, Math.min(1, frac || 0)) * 100;
    return `<div class="mtile ${dim ? 'dim' : ''}">
      <div class="mt-bar"><div class="mt-fill" style="width:${pct}%;background:${color}"></div></div>
      <div class="mt-val">${value}</div>
      <div class="mt-cap">${label}</div>
    </div>`;
  }
  // color helpers matching MetricDashboard verdicts
  const C = { good: '#88ff88', warn: '#ffd966', bad: '#ff7777', neu: '#58a6ff', purple: '#a87fff', dim: '#5a6470' };

  function dashboardHTML(m, hero) {
    const T9 = [];
    // Row 0
    T9.push(m.mdf == null ? tile('MDF — min defense freq', '--', 0, C.dim, true)
      : tile('MDF — min defense freq', m.mdf.toFixed(0) + '%', m.mdf / 100, m.mdf < 50 ? C.good : m.mdf < 70 ? C.warn : C.bad));
    T9.push(m.bluffCatch == null ? tile('Bluff-catch threshold', '--', 0, C.dim, true)
      : tile('Bluff-catch threshold', m.bluffCatch.toFixed(0) + '%', m.bluffCatch / 100, C.purple));
    T9.push(m.rangeAdv == null ? tile('Range advantage', '--', 0, C.dim, true)
      : tile('Range advantage', (m.rangeAdv >= 0 ? '+' : '−') + Math.abs(m.rangeAdv).toFixed(0) + '%', Math.abs(m.rangeAdv) / 30, m.rangeAdv >= 3 ? C.good : m.rangeAdv <= -3 ? C.bad : C.dim));
    // Row 1
    T9.push(m.reverseImplied == null ? tile('Reverse implied (domination)', '--', 0, C.dim, true)
      : tile('Reverse implied (domination)', m.reverseImplied.toFixed(0) + '%', m.reverseImplied / 30, m.reverseImplied >= 20 ? C.bad : m.reverseImplied >= 10 ? C.warn : C.good));
    if (m.nashPush == null) T9.push(tile('Nash push (≤ 15 BB)', 'n/a', 0, C.dim, true));
    else { const pct = m.nashPush; T9.push(tile('Nash push (≤ 15 BB)', pct.toFixed(0) + '%', pct / 100, m.stackBb <= 6 ? C.bad : C.warn)); }
    T9.push(m.realized == null ? tile('Realized vs raw equity', '--', 0, C.dim, true)
      : tile('Realized vs raw equity', m.realized.toFixed(0) + '%', Math.min(130, m.realized) / 130, m.realized >= 95 ? C.good : m.realized >= 75 ? C.warn : C.bad));
    // Row 2
    T9.push(m.vpip == null ? tile('Hero session VPIP / PFR / AGF', '--', 0, C.dim, true)
      : tile('Hero session VPIP / PFR / AGF', m.vpip.toFixed(0) + '%', m.vpip / 100, (m.vpip >= 16 && m.vpip <= 30) ? C.good : (m.vpip >= 12 && m.vpip <= 40) ? C.warn : C.bad));
    T9.push(tile('Tilt score (Hilger)', String(m.tilt == null ? 0 : m.tilt), (m.tilt || 0) / 100, (m.tilt || 0) < 25 ? C.good : (m.tilt || 0) < 40 ? C.warn : C.bad));
    T9.push(m.ror == null ? tile('Risk of Ruin (Chen)', '--', 0, C.dim, true)
      : tile('Risk of Ruin (Chen)', m.ror.toFixed(1) + '%', Math.min(10, m.ror) / 10, m.ror < 1 ? C.good : m.ror < 5 ? C.warn : C.bad));
    return `<div class="tom-dash">${T9.join('')}</div>`;
  }

  // advisor tab content (Gordon)
  function advisorHTML(d) {
    const a = d.advice; if (!a) return '<div class="muted">Deal a hand to see the advisor.</div>';
    const tag = (on, yes) => on ? `<b style="color:${yes ? C.good : C.bad}">YES</b>` : '<span class="muted">no</span>';
    const Q = s => `<span style="color:#9cd6ff">${s}</span>`;
    return `<div class="adv-text">
      <div class="adv-head">${esc(d.potOddsHeader).replace(/\n/g, '<br>')}</div>
      <div class="adv-line"><b>Hand</b> [${a.key}] tier ${a.tier} · pos ${a.position} · ${a.stackBb.toFixed(0)}bb · ${a.street}</div>
      <div class="adv-line" style="color:#9cd6ff">${esc(a.combo)}</div>
      <div class="adv-line"><b>Gordon's script</b> — run through every turn:</div>
      <div class="adv-line">${Q('Q. How are my opponents playing?')} ${a.setup.style}</div>
      <div class="adv-line">${Q('Q. What hands are they likely to hold?')} ${a.setup.ranges}</div>
      <div class="adv-line">${Q('Q. What do they think I have?')} ${a.setup.image}</div>
      <div class="adv-line">${Q('Q. Am I in good position?')} ${a.setup.position}</div>
      <div class="adv-line"><b>Q. Should I bet / raise?</b> → ${tag(a.betRaise, true)}   <b>Q. Should I check / fold?</b> → ${tag(a.checkFold, false)}</div>
      <div class="adv-line"><b style="color:${a.betRaise ? C.good : a.checkFold ? C.bad : C.warn}">ACTION:</b> ${esc(a.action)}</div>
      <div class="adv-line"><b>WHY:</b> ${esc(a.why)}</div>
      ${a.watch ? `<div class="adv-line" style="color:${C.warn}">⚠ ${esc(a.watch)}</div>` : ''}
      ${a.unraised ? `<div class="adv-line muted"><i>Unraised pot — decision is hand-tier × position, not pot odds.</i></div>` : ''}
    </div>`;
  }

  // hero tab content (pot commitment + outs board)
  function heroTabHTML(d) {
    const c = d.commit;
    let commit;
    if (!c || c.toCall <= 0) {
      const sprNow = c && c.pot > 0 ? (c.stack / c.pot) : null;
      commit = `<div class="commit"><h3>Pot Commitment</h3>
        ${sprNow != null
          ? `<div class="cm muted">No bet to face — pot odds don't apply yet.</div>
             <div class="cm"><b>SPR</b> (stack ÷ pot): <b>${sprNow.toFixed(2)}</b> → ${sprZone(sprNow)}</div>
             <div class="cm muted">Pot $${c.pot} · behind $${c.stack}</div>`
          : `<div class="cm muted">(no live bet to call — commitment math appears here when there's a bet to face)</div>`}
      </div>`;
    } else {
      const stackAfter = Math.max(0, c.stack - c.toCall), potAfter = c.pot + c.toCall;
      const spr = potAfter > 0 ? stackAfter / potAfter : 0;
      const potOddsPct = potAfter > 0 ? 100 * c.toCall / potAfter : 0;
      const ratioPct = c.stack > 0 ? 100 * c.toCall / c.stack : 100;
      const ratioTag = ratioPct >= 33 ? `<b style="color:${C.bad}">EFFECTIVELY COMMITTED</b>` : ratioPct >= 15 ? `<span style="color:${C.warn}">Meaningful</span>` : `<span style="color:${C.good}">Light</span>`;
      const eqVerdict = d.equityPct != null ? (d.equityPct < potOddsPct ? `<b style="color:${C.bad}">Unprofitable call</b>` : `<b style="color:${C.good}">Profitable call</b>`) : '';
      commit = `<div class="commit"><h3>Pot Commitment</h3>
        <div class="cm"><b>Pot Commitment Ratio</b>: <b>${ratioPct.toFixed(1)}%</b> of your stack → ${ratioTag}</div>
        <div class="cm"><b>SPR after call</b>: <b>${spr.toFixed(2)}</b> → ${sprZone(spr)}</div>
        ${d.equityPct != null ? `<div class="cm">Pot odds <b>${potOddsPct.toFixed(1)}%</b> vs Equity <b>${d.equityPct.toFixed(1)}%</b> → ${eqVerdict}</div>` : ''}
        <div class="cm muted">Putting in $${c.toCall} of $${c.stack} stack — $${stackAfter} behind into a $${potAfter} pot.</div>
      </div>`;
    }
    const outs = d.outs;
    const madeLine = `<div class="outs-head"><span class="made">${esc(outs.made || '(deal a hand)')}</span><span class="ocount">Outs: ${outs.count}</span></div>`;
    const outsSet = new Set(outs.outs || []);
    const list = (outs.outs && outs.outs.length)
      ? `<div class="outs-list">${groupOuts(outs.outs)}</div>` : '';
    return `${commit}${madeLine}<div class="muted" style="margin:6px 0">Cards in the deck (yellow = your outs)</div>${outsBoardHTML(d.heroHand, d.board, outsSet)}${list}`;
  }
  function sprZone(spr) { return spr < 1 ? `<b style="color:${C.bad}">POT-COMMITTED</b> (SPR < 1)` : spr < 3 ? `<span style="color:${C.warn}">Borderline</span> (SPR 1–3)` : `<span style="color:${C.good}">Not committed</span> (SPR ≥ 3)`; }
  function groupOuts(outs) {
    const g = { s: [], h: [], d: [], c: [] }; outs.forEach(k => { if (g[k[1]]) g[k[1]].push(k[0]); });
    const sym = { s: '♠', h: '♥', d: '♦', c: '♣' }; const parts = [];
    for (const s of ['s', 'h', 'd', 'c']) if (g[s].length) { g[s].sort((a, b) => T.ORDER.indexOf(a) - T.ORDER.indexOf(b)); parts.push(`${sym[s]} ${g[s].join(' ')}`); }
    return parts.join('   ');
  }

  // opponent tab content (range grid + betting history)
  function oppTabHTML(d, opp) {
    return `<div class="opp-tab">
      <div class="opp-left">
        <div class="opp-title">Estimated Range for ${esc(opp.name)}</div>
        ${rangeGridHTML(opp.range, opp.boardHits)}
        <div class="opp-notation">${esc(opp.notation)}</div>
      </div>
      <div class="opp-right">
        <div class="opp-hist-head">Betting history — ${esc(opp.name)}</div>
        <div class="opp-hist">${esc(opp.explanation).replace(/\n/g, '<br>')}</div>
      </div>
    </div>`;
  }

  // top strip + metric strip + outs/scare + range mode
  function topHTML(d) {
    const boardCells = [];
    for (let i = 0; i < 5; i++) boardCells.push(d.board[i] != null ? cardHTML(d.board[i], false) : '<span class="card back"></span>');
    const heroCards = d.heroHand && d.heroHand.length ? d.heroHand.map(c => cardHTML(c, false)).join('') : '<span class="card back"></span><span class="card back"></span>';
    const eq = d.equityPct != null ? d.equityPct.toFixed(1) + '%' : '--';
    const potOdds = d.potOddsLabel;
    const implied = d.impliedLabel;
    return `<div class="tom-strip">
      <span class="ts-lab">Board:</span> <span class="ts-board">${boardCells.join('')}</span>
      <span class="ts-lab" style="margin-left:18px">Your Hand (${d.posLong}):</span> <span class="ts-board">${heroCards}</span>
      <span class="ts-boardlabel">Board: ${d.street}</span>
    </div>
    <div class="tom-metrics">
      <div class="tm yellow">Pot: $${d.pot}</div>
      <div class="tm blue">Equity (vs Ranges): ${eq}</div>
      <div class="tm orange">Pot Odds: ${potOdds}</div>
      <div class="tm purple">Implied: ${implied}</div>
    </div>
    <div class="tom-outs">
      <div class="to-box">Outs: ${d.outs.count != null && (d.board.length >= 3) ? d.outs.count : '--'}</div>
      <div class="to-box">Scare Cards: ${d.scare && d.scare.length ? esc(d.scare.join(', ')) : '--'}</div>
      <div class="to-mode">Range Estimate:
        ${['loose', 'neutral', 'tight'].map(mode => {
          const lbl = mode === 'loose' ? 'Opps weak' : mode === 'tight' ? 'Opps strong' : 'Neutral';
          const cls = mode === 'loose' ? 'weak' : mode === 'tight' ? 'strong' : 'neu';
          return `<label class="rm ${cls} ${d.rangeMode === mode ? 'on' : ''}" data-mode="${mode}"><span class="dot"></span>${lbl}</label>`;
        }).join('')}
      </div>
    </div>`;
  }

  function tabsHTML(d) {
    const tabs = [{ id: 'advisor', label: 'Advisor', dot: null }, { id: 'hero', label: 'Hero', dot: null }]
      .concat(d.opponents.map(o => ({ id: o.name, label: o.name, dot: o.active ? 'on' : 'off' })));
    const bar = tabs.map(t => `<button class="tom-tab ${d.tab === t.id ? 'active' : ''}" data-tab="${esc(t.id)}">${t.dot ? `<span class="tdot ${t.dot}"></span>` : ''}${esc(t.label)}</button>`).join('');
    let content;
    if (d.tab === 'advisor') content = advisorHTML(d);
    else if (d.tab === 'hero') content = heroTabHTML(d);
    else { const opp = d.opponents.find(o => o.name === d.tab); content = opp ? oppTabHTML(d, opp) : advisorHTML(d); }
    return `<div class="tom-tabbar">${bar}</div><div class="tom-tabcontent">${content}</div>`;
  }

  // assemble the whole ToM screen body (everything between top bar and action bar)
  function render(d) {
    return `${topHTML(d)}
      <div class="tom-main">
        <div class="tom-left">${tabsHTML(d)}</div>
        <div class="tom-right">${dashboardHTML(d.metrics, d)}</div>
      </div>`;
  }

  const API = { render, cardHTML, rangeGridHTML, outsBoardHTML };
  if (isNode) module.exports = API;
  else root.PokerToM = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
