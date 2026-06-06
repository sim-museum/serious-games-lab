/*
 * PokerIQ — Theory of Mind analytics engine. Faithful port of the logic in
 * TheoryOfMindPanel / HeroOutsTab / MetricDashboard (pokerIQ.py):
 *   - per-style preflop ranges + PokerStove-notation parser + board-connection
 *     narrowing  -> estimateRange()
 *   - Phil Gordon "Little Green Book" advisor: hand tiers, combo nicknames,
 *     the two-question script + four setup questions  -> gordonAdvice()
 *   - eval7-equivalent outs computation + scare cards
 *   - equity vs estimated ranges (no-peek Monte Carlo)
 *   - the nine decision metrics (MDF, bluff-catch, range advantage, reverse
 *     implied, realized, Nash push, tilt, risk-of-ruin, VPIP/PFR/AGF)
 *
 * This is the depth that makes it PokerIQ. Depends on engine.js + analytics.js.
 */
(function (root) {
  'use strict';
  const isNode = (typeof require !== 'undefined' && typeof module !== 'undefined' && module.exports);
  const E = isNode ? require('./engine.js') : root.PokerEngine;
  const A = isNode ? require('./analytics.js') : root.PokerAnalytics;

  const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
  const RANK_VAL = { 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, T: 10, J: 11, Q: 12, K: 13, A: 14 };
  const ORDER = 'AKQJT98765432';   // index 0 = A (highest)

  // ---- per-style ranges (TheoryOfMindPanel.STYLE_RANGES) ----
  const STYLE_RANGES = {
    tight: {
      preflop_open: { loose: 'AA, KK, QQ, JJ, TT, 99, 88, AKs, AQs, AJs, AKo, AQo', neutral: 'AA, KK, QQ, JJ, TT, 99, AKs, AQs, AKo', tight: 'AA, KK, QQ, JJ, AKs, AKo' },
      preflop_call: { loose: 'AA-66, AKs-A9s, KQs-KTs, AKo-ATo', neutral: 'AA-77, AKs-ATs, KQs, AKo-AJo', tight: 'AA-99, AKs-AQs, AKo' },
      flop_continue: 0.6,
    },
    loose: {
      preflop_open: { loose: 'AA-22, any suited, any broadway, any connector', neutral: 'AA-22, AKs-A2s, KQs-K2s, QJs-Q8s, JTs-J8s, T9s-T8s, 98s-97s, 87s, 76s, AKo-A2o, KQo-K9o', tight: 'AA-22, AKs-A5s, KQs-K9s, QJs-Q9s, JTs-J9s, AKo-A8o, KQo-KTo' },
      preflop_call: { loose: 'AA-22, any suited, any broadway, any connector', neutral: 'AA-22, any suited, any broadway', tight: 'AA-22, AKs-A2s, KQs-K5s, any broadway' },
      flop_continue: 0.8,
    },
    aggressive: {
      preflop_open: { loose: 'AA-22, AKs-A2s, KQs-K5s, suited connectors, AKo-A5o, KQo-K9o', neutral: 'AA-55, AKs-A7s, KQs-KTs, QJs-QTs, JTs, T9s, 98s, 87s, 76s, AKo-ATo, KQo-KJo', tight: 'AA-77, AKs-A9s, KQs-KJs, QJs, JTs, AKo-AJo, KQo' },
      preflop_call: { loose: 'AA-22, AKs-A2s, any suited connector, AKo-A5o', neutral: 'AA-22, AKs-A2s, suited connectors, AKo-ATo', tight: 'AA-44, AKs-A7s, KQs-KTs, suited connectors, AKo-AJo' },
      flop_continue: 0.75,
    },
    optimal: {
      preflop_open: { loose: 'AA-44, AKs-A7s, KQs-K9s, QJs-Q9s, JTs-J9s, T9s, 98s, 87s, AKo-A9o, KQo-KTo', neutral: 'AA-66, AKs-A9s, KQs-KTs, QJs-QTs, JTs, T9s, AKo-AJo, KQo', tight: 'AA-88, AKs-ATs, KQs-KJs, QJs, AKo-AQo, KQo' },
      preflop_call: { loose: 'AA-22, AKs-A5s, suited connectors, AKo-A9o', neutral: 'AA-44, AKs-A8s, suited connectors, AKo-ATo', tight: 'AA-66, AKs-ATs, KQs, AKo-AJo' },
      flop_continue: 0.65,
    },
  };
  const THREE_BET = {
    tight: { tight: 'AA, KK', neutral: 'AA, KK, QQ, AKs', loose: 'AA, KK, QQ, JJ, AKs, AKo' },
    optimal: { tight: 'AA, KK, QQ', neutral: 'AA, KK, QQ, AKs, AKo', loose: 'AA, KK, QQ, JJ, AKs, AKo, AQs' },
    loose: { tight: 'AA, KK, QQ, JJ', neutral: 'AA, KK, QQ, JJ, AKs, AKo, AQs', loose: 'AA, KK, QQ, JJ, TT, AKs, AKo, AQs, AQo' },
    aggressive: { tight: 'AA, KK, QQ, JJ, AKs', neutral: 'AA, KK, QQ, JJ, AKs, AKo, AQs, AQo', loose: 'AA, KK, QQ, JJ, TT, AKs, AKo, AQs, AQo, AJs, KQs' },
  };
  const FOUR_BET = { tight: 'AA, KK', optimal: 'AA, KK, AKs', loose: 'AA, KK, QQ, AKs', aggressive: 'AA, KK, QQ, AKs, AKo' };
  const styleKey = s => STYLE_RANGES[s] ? s : 'loose';   // shark/tom/etc → loose ranges

  // ---- PokerStove notation parser (parse_range_notation) ----
  function parseRangeNotation(notation) {
    const rd = {};
    const rv = {}; RANKS.forEach((r, i) => rv[r] = i);
    const add = (h, w) => { rd[h] = (w == null ? 1.0 : w); };
    const addPairRange = (hi, lo) => { const a = rv[hi], b = rv[lo]; if (a >= 0 && b >= 0) for (let i = a; i <= b; i++) add(RANKS[i] + RANKS[i]); };
    const parts = (notation || '').replace(/ /g, '').split(',');
    for (let part of parts) {
      part = part.trim(); if (!part) continue;
      const low = part.toLowerCase();
      if (low.includes('anysuited')) { for (let i = 0; i < 13; i++) for (let j = 0; j < 13; j++) if (i < j) add(RANKS[i] + RANKS[j] + 's', 0.7); continue; }
      if (low.includes('anybroadway')) { const bw = ['A', 'K', 'Q', 'J', 'T']; for (let i = 0; i < bw.length; i++) for (let j = 0; j < bw.length; j++) { if (i < j) { add(bw[i] + bw[j] + 's', 0.8); add(bw[i] + bw[j] + 'o', 0.6); } else if (i === j) add(bw[i] + bw[j], 0.9); } continue; }
      if (low.includes('suitedconnector')) { [['A', 'K'], ['K', 'Q'], ['Q', 'J'], ['J', 'T'], ['T', '9'], ['9', '8'], ['8', '7'], ['7', '6'], ['6', '5'], ['5', '4']].forEach(([a, b]) => add(a + b + 's', 0.8)); continue; }
      if (part.includes('-') && part.length >= 5 && part[0] === part[1]) { addPairRange(part[0], part[3]); continue; }
      if (part.length === 2 && part[0] === part[1] && rv[part[0]] != null) { add(part); continue; }
      if (part.includes('+')) {
        const base = part.replace('+', '');
        if (base.length === 3 && 'so'.includes(base[2])) { const r1 = base[0], suit = base[2]; const start = rv[base[1]], end = rv[r1]; if (start >= 0 && end >= 0) for (let i = end + 1; i <= start; i++) add(r1 + RANKS[i] + suit); }
        else if (base.length === 2 && base[0] === base[1]) addPairRange('A', base[0]);
        continue;
      }
      if (part.includes('-') && part.length >= 7) { const [h1, h2] = part.split('-'); if (h1.length === 3 && h2.length === 3 && h1[0] === h2[0]) { const r1 = h1[0], suit = h1[2]; const start = rv[h1[1]], end = rv[h2[1]]; if (start >= 0 && end >= 0) for (let i = start; i <= end; i++) add(r1 + RANKS[i] + suit); } continue; }
      if (part.length === 3 && 'so'.includes(part[2])) add(part);
      else if (part.length === 2 && rv[part[0]] != null && rv[part[1]] != null) {
        if (part[0] !== part[1]) { let r1 = part[0], r2 = part[1]; if (rv[r1] > rv[r2]) { const t = r1; r1 = r2; r2 = t; } add(r1 + r2 + 's', 0.8); add(r1 + r2 + 'o', 0.6); }
        else add(part);
      }
    }
    return rd;
  }

  function handRanks(h) {
    if (!h || h.length < 2) return null;
    let r1 = h[0], r2 = h[1]; const suited = h.length >= 3 && h[2] === 's';
    if (r1 === r2) return [r1, r2, false];
    if (RANK_VAL[r1] < RANK_VAL[r2]) { const t = r1; r1 = r2; r2 = t; }
    return [r1, r2, suited];
  }

  // ---- board connection score (_board_connection_score) ----
  function boardConnectionScore(handStr, board) {
    const parts = handRanks(handStr); if (!parts || !board || !board.length) return 0;
    const [r1, r2, suited] = parts; const v1 = RANK_VAL[r1], v2 = RANK_VAL[r2];
    const bRanks = [], bSuits = [];
    for (const c of board) { const cs = E.cardToStr(c); bRanks.push(RANK_VAL[cs[0]] || 0); bSuits.push(cs[1] || ''); }
    const br = bRanks.filter(b => b > 0); if (!br.length) return 0;
    const topBoard = Math.max(...br); const isPair = r1 === r2;
    if (isPair) {
      if (br.includes(v1)) return 1.0;
      if (v1 > topBoard) return 1.0;
      const overs = br.filter(b => b > v1).length; return overs <= 1 ? 0.55 : 0.35;
    }
    let score = 0.10;
    if (br.includes(v1) && br.includes(v2)) score = Math.max(score, 0.85);
    else if (v1 === topBoard) score = Math.max(score, v2 >= 10 ? 0.95 : 0.85);
    else if (br.includes(v1)) score = Math.max(score, 0.75);
    else if (br.includes(v2)) score = Math.max(score, 0.55);
    if (v1 > topBoard && v2 > topBoard) score = Math.max(score, 0.30);
    const all = new Set(br); all.add(v1); all.add(v2); if (all.has(14)) all.add(1);
    for (let lo = 1; lo <= 10; lo++) {
      const window = []; for (let k = lo; k < lo + 5; k++) window.push(k);
      const present = window.filter(w => all.has(w)); const need = window.filter(w => !all.has(w));
      const usesHole = window.includes(v1) || window.includes(v2) || ((v1 === 14 || v2 === 14) && window.includes(1));
      if (!usesHole) continue;
      if (present.length >= 5) { score = Math.max(score, 0.95); break; }
      if (present.length === 4) { const missing = need[0]; if (missing === lo || missing === lo + 4) score = Math.max(score, 0.75); else score = Math.max(score, 0.55); }
    }
    if (suited) { for (const s of new Set(bSuits)) if (s && bSuits.filter(x => x === s).length >= 2) { score = Math.max(score, 0.75); break; } }
    return Math.min(1, score);
  }

  // ---- estimate a player's range (estimate_range) ----
  // actions: Set of tags {raised, three_bet, four_bet, five_bet_plus,
  //          called_postflop, bet_postflop, raised_postflop}
  // mode: 'loose'|'neutral'|'tight'
  function estimateRange(style, mode, actions, board) {
    const sk = styleKey(style); const info = STYLE_RANGES[sk];
    let baseNotation, actionDesc;
    if (actions.has('five_bet_plus')) { baseNotation = 'AA, KK'; actionDesc = '5-bet+ preflop (premium-only)'; }
    else if (actions.has('four_bet')) { baseNotation = FOUR_BET[sk] || FOUR_BET.optimal; actionDesc = '4-bet preflop'; }
    else if (actions.has('three_bet')) { const tb = THREE_BET[sk] || THREE_BET.optimal; baseNotation = tb[mode] || tb.neutral; actionDesc = '3-bet preflop'; }
    else if (actions.has('raised')) { const rd = info.preflop_open; baseNotation = rd[mode] || rd.neutral; actionDesc = 'opened/raised preflop'; }
    else { const rd = info.preflop_call; baseNotation = rd[mode] || rd.neutral; actionDesc = 'called preflop'; }

    const modeDesc = { loose: '(assuming weak)', neutral: '', tight: '(assuming strong)' };
    const expl = [`Player Style: ${cap(style)}`, `Range Mode: ${cap(mode)} ${modeDesc[mode] || ''}`, `Action: ${actionDesc}`, '', 'Preflop Range Estimate:', `  ${baseNotation}`];

    let mult = 1.0;
    const postflop = board && board.length >= 3;
    if (postflop) {
      if (actions.has('bet_postflop') || actions.has('raised_postflop')) { mult *= 0.5; expl.push('', 'Postflop betting narrows range significantly.', 'Likely has: top pair+, draws, or bluffs'); }
      else if (actions.has('called_postflop')) { mult *= info.flop_continue; expl.push('', 'Called postflop - still wide but connected to board.'); }
    }
    const rd = parseRangeNotation(baseNotation);
    if (mult < 1) for (const h in rd) rd[h] *= mult;
    const boardHits = {};
    if (postflop) {
      const pureCall = actions.has('called_postflop') && !actions.has('raised_postflop') && !actions.has('bet_postflop');
      for (const h of Object.keys(rd)) {
        if (rd[h] <= 0) continue;
        const hit = boardConnectionScore(h, board); boardHits[h] = hit;
        if (pureCall) { const floor = 0.15, bump = 1.0 + Math.max(0, hit - 0.5); rd[h] = Math.min(1, Math.max(0, rd[h] * Math.max(floor, hit) * bump)); }
      }
      if (pureCall) {
        const strong = Object.keys(boardHits).filter(h => boardHits[h] >= 0.85 && rd[h] > 0.2);
        const draws = Object.keys(boardHits).filter(h => boardHits[h] >= 0.55 && boardHits[h] < 0.85 && rd[h] > 0.2);
        if (strong.length || draws.length) expl.push('', 'Range narrowed by board connection — combos that hit are highlighted (yellow).');
        if (strong.length) expl.push('Made hands likely: ' + strong.slice(0, 8).join(', ') + (strong.length > 8 ? '…' : ''));
        if (draws.length) expl.push('Draws / second pair: ' + draws.slice(0, 8).join(', ') + (draws.length > 8 ? '…' : ''));
      }
    }
    return { range: rd, notation: baseNotation, explanation: expl.join('\n'), boardHits };
  }

  // ---- hero hand → 169 key ----
  function handToKey(hand) {
    if (!hand || hand.length < 2) return null;
    const c1 = E.cardToStr(hand[0]), c2 = E.cardToStr(hand[1]);
    let r1 = c1[0], r2 = c2[0], s1 = c1[1], s2 = c2[1];
    if (ORDER.indexOf(r1) > ORDER.indexOf(r2)) { [r1, r2] = [r2, r1]; [s1, s2] = [s2, s1]; }
    if (r1 === r2) return r1 + r2;
    return s1 === s2 ? r1 + r2 + 's' : r1 + r2 + 'o';
  }

  // ---- Gordon tiers + nicknames + combo description ----
  const GORDON_TIER = {};
  ['AA', 'KK', 'QQ', 'JJ', 'AKs', 'AKo', 'AQs'].forEach(k => GORDON_TIER[k] = 1);
  ['TT', '99', 'AQo', 'AJs', 'KQs', 'AJo', 'KQo'].forEach(k => GORDON_TIER[k] = 2);
  ['88', '77', '66', 'ATs', 'KJs', 'QJs', 'JTs', 'KTs', 'QTs', 'T9s', '98s', '87s', '76s', 'ATo', 'KJo', 'QJo', 'JTo'].forEach(k => GORDON_TIER[k] = 3);
  ['55', '44', '33', '22', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s', 'K9s', 'Q9s', 'J9s', 'T8s', '97s', '86s', '75s', '65s', '54s', 'KTo', 'QTo', 'T9o', '98o'].forEach(k => GORDON_TIER[k] = 4);
  const gordonTier = k => GORDON_TIER[k] != null ? GORDON_TIER[k] : 6;
  const NICK = { AA: 'American Airlines / Pocket Rockets', KK: 'Cowboys / King Kong', QQ: 'Ladies / Hilton Sisters', JJ: 'Fishhooks / Jacks', TT: 'Dimes / TNT', 99: 'German Virgin', 88: 'Snowmen', 77: 'Hockey Sticks', 66: 'Route 66', 55: 'Speed Limit / Presto', 44: 'Sailboats', 33: 'Crabs', 22: 'Ducks / Deuces', AKs: 'Big Slick (suited)', AKo: 'Big Slick (offsuit)', AQs: 'Big Chick (suited)', AQo: 'Big Chick (offsuit)', AJs: 'Ajax (suited)', AJo: 'Ajax (offsuit)', KQs: 'Royal Couple (suited)', KQo: 'Royal Couple (offsuit)', KJs: 'Kojak (suited)', KJo: 'Kojak (offsuit)', QJs: 'Queen-Jack (suited)', JTs: 'Justin Timberlake (suited)', T9s: 'T-Niner (suited)', '98s': 'Oldsmobile (suited)', '76s': 'Trombones (suited)', '65s': 'Mike Sexton', '54s': 'Colt 45 (suited)', '72o': 'The Hammer — worst hand in poker', K9o: 'Canine', J5o: 'Jackson Five / Motown' };

  function gordonComboDescription(key) {
    if (!key || key === '??') return '';
    const r1 = key[0]; let r2, suited, isPair;
    if (key.length === 2) { r2 = r1; suited = false; isPair = true; } else { r2 = key[1]; suited = key[key.length - 1].toLowerCase() === 's'; isPair = false; }
    const i1 = ORDER.indexOf(r1), i2 = ORDER.indexOf(r2), gap = Math.abs(i1 - i2), high = Math.min(i1, i2);
    const nick = NICK[key] || ''; let hint;
    if (isPair) {
      if (high <= 1) hint = "premium — raise / 3-bet always. Don't go broke pre vs the 4th raise (AA only).";
      else if (high <= 3) hint = "premium pair — open / 3-bet always; fold to a tight player's 4-bet shove.";
      else if (high <= 5) hint = 'strong pair — open / 3-bet; set-mine if 4-bet. Need 8:1 implied.';
      else if (high <= 8) hint = 'medium pair — raise if folded to, otherwise set-mine. Loses unimproved multi-way.';
      else hint = 'small pair — call cheap for set value. Need 15:1 implied; fold to raises.';
    } else if (r1 === 'A' || r2 === 'A') {
      const other = r1 === 'A' ? r2 : r1, oi = ORDER.indexOf(other);
      if (other === 'K') hint = 'Big Slick — best unpaired. Raise / 3-bet any seat. Ace-high until it connects.';
      else if ('QJ'.includes(other)) hint = suited ? 'strong broadway (suited) — open / call 3-bets in position.' : 'broadway offsuit — open, fold to 3-bets from tight players. Watch AK domination.';
      else if (other === 'T') hint = suited ? 'suited Broadway — open / call in position.' : 'marginal ace — open late position only. Dominated by AJ/AQ/AK.';
      else if (suited && oi >= 9) hint = 'wheel ace suited — nut-flush + A-5 straight potential. Great 3-bet bluff hand.';
      else if (suited) hint = 'suited ace — flush-only equity; call in position with implied odds.';
      else hint = oi <= 6 ? 'trouble ace offsuit — open button only, fold to aggression.' : 'ace-rag offsuit — dominated by every better ace; fold.';
    } else if (r1 === 'K' || r2 === 'K') {
      const other = r1 === 'K' ? r2 : r1, oi = ORDER.indexOf(other);
      if (other === 'Q') hint = suited ? 'Royal draw (suited).' : 'KQ offsuit — trap hand; often dominated by AK/AQ. Looks better than it plays.';
      else if ('JT'.includes(other)) hint = suited ? 'suited broadway — raise in position; strong multi-way.' : 'broadway offsuit — raise in position only.';
      else if (suited && oi <= 9) hint = 'suited king — button / BB only. Flush potential, vulnerable kicker.';
      else hint = 'king-rag — not profitable long-term. Fold.';
    } else if ('QJ'.includes(r1) && 'QJT9'.includes(r2)) {
      hint = suited ? 'Broadway connector (suited) — open in position; flops well into straights / flushes.' : 'broadway offsuit — open in position. Often makes second-best top pair.';
    } else if (suited && gap === 1 && high >= 4) hint = 'suited connector — best multi-way speculator. Need 15-20x implied; deep stacks only.';
    else if (suited && gap === 2 && high >= 4) hint = 'suited one-gapper — speculative; late position with depth, otherwise fold.';
    else if (suited && gap === 3) hint = 'suited two-gapper — button / BB only. Marginal.';
    else if (suited) hint = 'weak suited — defend BB cheaply, rarely open. Flush potential is the only redemption.';
    else if (gap === 1 && high <= 4) hint = 'connected offsuit — speculative; rarely open.';
    else hint = 'trash — fold.';
    return (nick ? nick : key) + ' — ' + hint;
  }

  function gordonOpenSize(position, bb) { const m = { UTG: 2.5, EP: 2.5, MP: 3.0, CO: 3.5, BTN: 3.5, SB: 3.0, BB: 3.0 }[position] || 3.0; return `RAISE to ${m}× BB ($${Math.round(m * Math.max(bb, 1))})`; }

  // ---- pot-odds header (_build_pot_odds_header) ----
  function potOddsHeader(ctx) {
    const pot = ctx.pot || 0, toCall = ctx.toCall || 0, potOdds = ctx.potOdds || 0;
    const noPeek = ctx.noPeekEquity, numOpps = ctx.numOpponents || 0, street = ctx.street || 'Preflop';
    const bb = ctx.bb || 2, curBet = ctx.currentBet || 0;
    const unraised = street === 'Preflop' && toCall > 0 && curBet <= bb;
    const lines = ['═══ POT ODDS & EQUITY ═══'];
    if (toCall > 0) {
      const ratio = pot / toCall;
      if (unraised) lines.push(`Pot $${pot}  |  To call $${toCall} (BB to enter)  |  no real raise — pot odds don't drive the decision`);
      else lines.push(`Pot $${pot}  |  To call $${toCall}  |  Pot odds ${ratio.toFixed(1)}:1 (need ${(potOdds * 100).toFixed(1)}% equity)`);
    } else if (pot > 0) lines.push(`Pot $${pot}  |  No bet to call right now`);
    else lines.push('No pot yet');
    if (noPeek != null) {
      let line = `Hand equity (vs ${numOpps} opp range${numOpps !== 1 ? 's' : ''}, ${street}): ${(noPeek * 100).toFixed(1)}%`;
      if (unraised) line += '   →   decide by HAND TIER + POSITION (no raise to fold to)';
      else if (toCall > 0) { const margin = (noPeek - potOdds) * 100; line += margin >= 0 ? `   →   +${margin.toFixed(1)}% over pot odds (+EV call)` : `   →   ${margin.toFixed(1)}% under pot odds (-EV call)`; }
      lines.push(line); lines.push('(No-peek: computed vs estimated ranges, never actual cards.)');
    }
    return lines.join('\n');
  }

  // ---- Gordon advice (_build_gordon_advice) ----
  function gordonAdvice(ctx, key, setup) {
    const position = (ctx.heroPosition || 'MP').toUpperCase();
    const street = ctx.street || 'Preflop', toCall = ctx.toCall || 0, pot = ctx.pot || 0;
    const equity = ctx.equity || 0, potOdds = ctx.potOdds || 0, curBet = ctx.currentBet || 0, numOpps = ctx.numOpponents || 0;
    const bb = ctx.bb || 2, heroStack = ctx.heroStack || 200, stackBb = bb ? heroStack / bb : 50;
    const tier = gordonTier(key);
    const unraised = street === 'Preflop' && curBet > 0 && curBet <= bb;
    let betRaise = false, checkFold = false, action = '', why = '';
    if (street === 'Preflop') {
      const nRaises = Math.max(0, Math.floor(curBet / Math.max(bb, 1)) - 1);
      const firstIn = toCall <= bb && curBet <= bb;
      const facingRaise = curBet > bb;
      if (stackBb <= 15) {
        const pct = A.handStrengthPercentile(ctx.heroHand || []); const band = A.nashPushPct(stackBb);
        if (pct >= (1 - band)) { betRaise = true; action = `PUSH ALL-IN (Nash @ ${stackBb.toFixed(0)}bb: top ${(band * 100).toFixed(0)}%)`; why = 'Folding equity + ICM beats blinding out.'; }
        else { checkFold = true; action = 'FOLD (outside Nash push range)'; why = 'Conserve chips for a better spot.'; }
      } else if (facingRaise && nRaises >= 3) {
        if (tier === 1 && key === 'AA') { betRaise = true; action = 'SHOVE — call any all-in (AA)'; why = 'Only AA beats AA; get it all in.'; }
        else { checkFold = true; action = 'FOLD (4th raise ≈ AA)'; why = "Gordon's rule: the 4th raise means aces. Save chips for a clean spot."; }
      } else if (facingRaise) {
        const isPair = key.length === 2, implied = toCall > 0 ? heroStack / Math.max(1, toCall) : 1e9;
        if (tier <= 2) { betRaise = true; action = `3-BET (tier ${tier} hand vs raise)`; why = 'Re-raise to isolate / take the lead. Gordon: 3× the previous bet.'; }
        else if (isPair && implied >= 15) { action = `CALL — set mine (${implied.toFixed(0)}:1)`; why = 'Small pair + deep stacks: 12% to flop a set, big implied odds.'; }
        else if (tier === 3 && (position === 'CO' || position === 'BTN')) { action = 'CALL in position'; why = 'Set/draw equity + positional advantage.'; }
        else { checkFold = true; action = `FOLD (tier ${tier} vs raise)${isPair ? ` (implied ${implied.toFixed(0)}:1 < 15:1)` : ''}`; why = 'Out of position / dominated; wait.'; }
      } else if (firstIn) {
        const steal = position === 'CO' || position === 'BTN';
        if (tier <= 3) { betRaise = true; action = gordonOpenSize(position, bb); why = "First in → always raise (thin field, take lead, define ranges, conceal strength, win blinds)."; }
        else if (tier === 4) { if (steal) { betRaise = true; action = gordonOpenSize(position, bb); why = 'Tier 4 from LP — open for steal value; positional advantage post-flop.'; } else { checkFold = true; action = 'FOLD (tier 4 — open only LP)'; why = 'Avoid weak hands out of position.'; } }
        else if (tier === 5) { if (steal) { betRaise = true; action = gordonOpenSize(position, bb) + ' — steal'; why = "Gordon: BTN / CO are 'kind of money' steal seats."; } else { checkFold = true; action = 'FOLD'; why = 'No reason to play.'; } }
        else { if (position === 'BTN') { betRaise = true; action = gordonOpenSize(position, bb) + ' — BTN steal'; why = 'BTN, folded around — even trash is +EV vs two blinds.'; } else if (position === 'CO') { action = 'CALL — light CO limp'; why = 'Trash from CO: limp for cheap speculation.'; } else { checkFold = true; action = 'FOLD (trash from this seat)'; why = 'Wait for a real spot.'; } }
      } else {
        if (tier <= 3) { betRaise = true; action = 'RAISE limpers'; why = 'Punish weak limps with a pot-sized squeeze in position.'; }
        else { action = 'CHECK'; why = 'Take the free flop with this trash.'; }
      }
    } else {
      const eqP = equity * 100, poP = potOdds * 100;
      if (toCall <= 0) {
        if (eqP >= 60 || (numOpps === 1 && eqP >= 50)) { betRaise = true; action = 'BET 2/3 pot (value)'; why = 'Big hand → big pot. Charge draws, extract value.'; }
        else if (eqP >= 35 && numOpps === 1) { betRaise = true; action = 'C-BET ½ pot'; why = 'Continuation bet wins ~65% HU when villain misses.'; }
        else { action = 'CHECK'; why = 'Pot control with a weak/marginal hand.'; }
      } else {
        if (eqP >= 75 && pot >= bb * 8) { betRaise = true; action = 'RAISE — get it in'; why = 'Top of the range; build the pot.'; }
        else if (eqP >= poP) { if (eqP >= 60) { betRaise = true; action = 'RAISE for value / protection'; why = "Big hand → big pot. Don't slow-play on draws."; } else { action = 'CALL'; why = `Equity ${eqP.toFixed(0)}% beats pot odds ${poP.toFixed(0)}%.`; } }
        else { checkFold = true; action = 'FOLD'; why = `Equity ${eqP.toFixed(0)}% < pot odds ${poP.toFixed(0)}%; no implied path.`; }
      }
    }
    let watch = '';
    if (street === 'Preflop' && curBet > 3 * bb && tier >= 3) watch = 'WATCH: big preflop pot ≈ they\'re not folding.';
    else if (street === 'Flop' && ctx.board && ctx.board.length >= 3) { const r = ctx.board.slice(0, 3).map(c => E.cardToStr(c)[0]); if (new Set(r).size < r.length) watch = 'WATCH: paired board — first to bet usually wins.'; else if (new Set(ctx.board.slice(0, 3).map(c => E.cardToStr(c)[1])).size === 1) watch = 'WATCH: monotone flop — flush draws everywhere.'; }
    else if (stackBb <= 20 && stackBb > 15 && street === 'Preflop') watch = 'WATCH: ~20 BB — push/fold soon.';
    return { key, tier, position, stackBb, street, combo: gordonComboDescription(key), setup, betRaise, checkFold, action, why, watch, unraised };
  }

  // ---- outs (HeroOutsTab/_count_outs) + scare cards ----
  const CAT = E.CAT;
  const PAIR_FAMILY = new Set([CAT.ONE_PAIR, CAT.TWO_PAIR, CAT.TRIPS, CAT.FULL_HOUSE, CAT.QUADS]);
  function computeOuts(hand, board) {
    if (!hand || hand.length < 2 || !board || board.length < 3 || board.length > 4) return { count: 0, outs: [], made: board && board.length ? '' : 'Preflop — outs depend on flop' };
    const cur = E.evaluate(hand.concat(board)); const curCat = E.categoryOf(cur);
    const used = new Set([...hand, ...board].map(c => E.cardToStr(c)));
    const heroRanks = new Set(hand.map(c => E.cardToStr(c)[0]));
    const boardRankSet = new Set(board.map(c => E.cardToStr(c)[0]));
    const boardHighIdx = boardRankSet.size ? Math.min(...[...boardRankSet].map(r => ORDER.indexOf(r))) : 0;
    const outs = [];
    for (const r of ORDER) for (const s of ['s', 'h', 'd', 'c']) {
      const key = r + s; if (used.has(key)) continue;
      const card = E.cardFromStr(key); const ns = E.evaluate(hand.concat(board, [card])); const nc = E.categoryOf(ns);
      if (boardRankSet.has(r) && !heroRanks.has(r) && PAIR_FAMILY.has(nc)) continue;
      if (nc > curCat && nc >= CAT.TWO_PAIR) { outs.push(key); continue; }
      if (curCat === CAT.HIGH_CARD && nc === CAT.ONE_PAIR && heroRanks.has(r) && ORDER.indexOf(r) <= boardHighIdx) { outs.push(key); continue; }
      if (heroRanks.has(r) && nc === curCat && ns > cur && nc >= CAT.ONE_PAIR) outs.push(key);
    }
    return { count: outs.length, outs, made: 'Best now: ' + E.describe(cur), curCat };
  }
  function scareCards(hand, board) {
    if (!board || board.length < 3) return [];
    const bRanks = board.map(c => E.cardToStr(c)[0]), bSuits = board.map(c => E.cardToStr(c)[1]);
    const heroRanks = new Set((hand || []).map(c => E.cardToStr(c)[0]));
    const out = []; const sc = {}; bSuits.forEach(s => sc[s] = (sc[s] || 0) + 1);
    for (const s in sc) if (sc[s] >= 3) { out.push(`Any ${{ h: '♥', s: '♠', d: '♦', c: '♣' }[s]} (flush)`); break; }
    const bv = bRanks.map(r => ORDER.indexOf(r)).sort((a, b) => a - b);
    for (let i = 0; i < 13; i++) { const tv = bv.concat([i]).sort((a, b) => a - b); for (let j = 0; j <= tv.length - 5; j++) { if (tv[j + 4] - tv[j] === 4) { const cr = ORDER[i]; if (!bRanks.includes(cr) && !heroRanks.has(cr)) out.push(`${cr} (straight)`); break; } } }
    for (const r of bRanks) if (bRanks.filter(x => x === r).length === 1 && !heroRanks.has(r)) out.push(`${r} (pairs board)`);
    for (const r of 'AKQ') if (!bRanks.includes(r) && !heroRanks.has(r)) out.push(`${r} (hits broadways)`);
    return out.slice(0, 8);
  }

  // ---- equity vs estimated ranges (no-peek MC) ----
  function equityVsRanges(hand, board, oppRanges, opts) {
    opts = opts || {}; const iters = opts.iterations || 350; const rng = opts.rng || Math.random;
    // expand each opponent's range to concrete combos (cards) above threshold
    const used0 = new Set([...hand, ...board].map(c => E.codeOf(c)));
    const oppCombos = oppRanges.map(rd => expandCombos(rd, used0, 0.3)).filter(c => c.length);
    if (!oppCombos.length) return null;
    let wins = 0, ties = 0, done = 0;
    for (let it = 0; it < iters; it++) {
      const used = new Set(used0); const opp = []; let ok = true;
      for (const combos of oppCombos) {
        let pick = null;
        for (let tries = 0; tries < 8; tries++) { const c = combos[Math.floor(rng() * combos.length)]; if (!used.has(E.codeOf(c[0])) && !used.has(E.codeOf(c[1]))) { pick = c; break; } }
        if (!pick) { ok = false; break; }
        used.add(E.codeOf(pick[0])); used.add(E.codeOf(pick[1])); opp.push(pick);
      }
      if (!ok) continue;
      // complete board
      const deck = E.fullDeck().filter(c => !used.has(E.codeOf(c)));
      for (let i = deck.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); const t = deck[i]; deck[i] = deck[j]; deck[j] = t; }
      const need = 5 - board.length; const full = board.concat(deck.slice(0, need));
      const hs = E.evaluate(hand.concat(full)); let best = -1;
      for (const o of opp) { const s = E.evaluate(o.concat(full)); if (s > best) best = s; }
      if (hs > best) wins++; else if (hs === best) ties++; done++;
    }
    return done ? (wins + ties / 2) / done : null;
  }
  function expandCombos(rd, used, threshold) {
    const combos = [];
    for (const h in rd) {
      if (rd[h] < threshold) continue;
      const r1 = h[0], r2 = h[1], suited = h[2] === 's', pair = r1 === r2;
      const suits = ['s', 'h', 'd', 'c'];
      if (pair) { for (let i = 0; i < 4; i++) for (let j = i + 1; j < 4; j++) pushCombo(combos, r1 + suits[i], r2 + suits[j], used); }
      else if (suited) { for (const s of suits) pushCombo(combos, r1 + s, r2 + s, used); }
      else { for (const a of suits) for (const b of suits) if (a !== b) pushCombo(combos, r1 + a, r2 + b, used); }
    }
    return combos;
  }
  function pushCombo(arr, c1s, c2s, used) { const c1 = E.cardFromStr(c1s), c2 = E.cardFromStr(c2s); if (used.has(E.codeOf(c1)) || used.has(E.codeOf(c2))) return; arr.push([c1, c2]); }

  // ---- the nine dashboard metrics ----
  function metrics(ctx) {
    const pot = ctx.pot || 0, toCall = ctx.toCall || 0, bb = ctx.bb || 2;
    const facing = toCall > 0;
    const bet = toCall;  // bet faced
    const mdf = facing ? 100 * pot / (pot + bet) : null;
    const bluffCatch = facing ? 100 * bet / (pot + bet) : null;
    // range advantage: heuristic from initiative + board high-card fit (Acevedo)
    let rangeAdv = null;
    if (ctx.board && ctx.board.length >= 3) {
      const tex = A.classifyBoard(ctx.board);
      let adv = ctx.hasInitiative ? 8 : -4;
      if (tex.label === 'dry') adv += 6; else if (tex.label.includes('wet')) adv -= 6;
      rangeAdv = Math.max(-30, Math.min(30, adv));
    }
    // reverse implied: stack-at-risk heuristic — higher with dominated-prone hands
    let reverseImplied = null;
    if (ctx.heroHand && ctx.heroHand.length === 2 && ctx.board && ctx.board.length >= 3) {
      const made = computeOuts(ctx.heroHand, ctx.board);
      // one-pair-ish with weak kicker on coordinated boards = high RI
      const tex = A.classifyBoard(ctx.board);
      let ri = 6; if (made.curCat === CAT.ONE_PAIR) ri = 12; if (made.curCat === CAT.TWO_PAIR) ri = 9;
      if (tex.label.includes('wet') || tex.label.includes('dynamic')) ri += 6;
      reverseImplied = Math.min(30, ri);
    }
    const stackBb = ctx.heroStack != null && bb ? ctx.heroStack / bb : null;
    const nashPush = (stackBb != null && stackBb <= 15) ? A.nashPushPct(stackBb) * 100 : null;
    return { mdf, bluffCatch, rangeAdv, reverseImplied, nashPush, stackBb };
  }

  function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }

  // ---- hand descriptions (ports of categorize_preflop_hand / describe_made_hand
  //      / get_hand_name) for the Hand Summary ----
  const RANK_NAME = { A: 'Ace', K: 'King', Q: 'Queen', J: 'Jack', T: 'Ten', 9: 'Nine', 8: 'Eight', 7: 'Seven', 6: 'Six', 5: 'Five', 4: 'Four', 3: 'Three', 2: 'Two' };
  function categorizePreflop(hand) {
    if (!hand || hand.length < 2) return 'unknown';
    const c1 = E.cardToStr(hand[0]), c2 = E.cardToStr(hand[1]);
    const r1 = c1[0], r2 = c2[0], s1 = c1[1], s2 = c2[1];
    const v1 = ORDER.indexOf(r1), v2 = ORDER.indexOf(r2);
    const pair = r1 === r2, suited = s1 === s2;
    if (pair) { if ('AK'.includes(r1)) return 'premium pair'; if ('QJT'.includes(r1)) return 'high pair'; if ('987'.includes(r1)) return 'medium pair'; return 'small pair'; }
    const high = Math.min(v1, v2), gap = Math.abs(v1 - v2);
    if (high <= 1 && gap <= 1) return suited ? 'big slick' : 'big slick offsuit';
    if (high <= 3 && gap <= 2) return suited ? 'suited broadway' : 'broadway';
    if (suited && gap === 1) return 'suited connector';
    if (suited && gap <= 2) return 'suited one-gapper';
    if (r1 === 'A' || r2 === 'A') return suited ? 'suited ace' : 'ace-rag';
    if (suited) return 'suited cards';
    return 'offsuit junk';
  }
  function handName(hand) {
    if (!hand || hand.length < 2) return 'unknown';
    let c1 = E.cardToStr(hand[0]), c2 = E.cardToStr(hand[1]);
    let r1 = c1[0], r2 = c2[0], s1 = c1[1], s2 = c2[1];
    if (ORDER.indexOf(r1) > ORDER.indexOf(r2)) { [r1, r2] = [r2, r1]; [s1, s2] = [s2, s1]; }
    if (r1 === r2) return `pocket ${RANK_NAME[r1]}s`;
    return `${RANK_NAME[r1]}-${RANK_NAME[r2]}${s1 === s2 ? ' suited' : ''}`;
  }
  function describeMadeHand(hand, board) {
    if (!hand || !board || hand.length < 2 || (hand.length + board.length) < 5) return board && board.length ? 'no hand' : categorizePreflop(hand);
    const cat = E.categoryOf(E.evaluate(hand.concat(board)));
    const holeRanks = hand.map(c => E.cardToStr(c)[0]);
    const boardRanks = board.map(c => E.cardToStr(c)[0]);
    const allRanks = holeRanks.concat(boardRanks);
    const cnt = {}; allRanks.forEach(r => cnt[r] = (cnt[r] || 0) + 1);
    const bcnt = {}; boardRanks.forEach(r => bcnt[r] = (bcnt[r] || 0) + 1);
    const pos = r => ORDER.indexOf(r);
    const firstWith = n => Object.keys(cnt).find(r => cnt[r] >= n);
    if (cat === CAT.STRAIGHT_FLUSH) return 'straight flush';
    if (cat === CAT.QUADS) { const q = firstWith(4); return q ? `quads (${q}s)` : 'four of a kind'; }
    if (cat === CAT.FULL_HOUSE) { const t = firstWith(3); const p = Object.keys(cnt).find(r => cnt[r] >= 2 && r !== t); return t && p ? `full house (${t}s full of ${p}s)` : 'full house'; }
    if (cat === CAT.FLUSH) return 'flush';
    if (cat === CAT.STRAIGHT) return 'straight';
    if (cat === CAT.TRIPS) { const t = firstWith(3); if (t && holeRanks[0] === holeRanks[1] && holeRanks[0] === t) return `set of ${t}s`; if (t && bcnt[t] >= 2) return `trips (${t}s)`; return 'three of a kind'; }
    if (cat === CAT.TWO_PAIR) { const pairs = Object.keys(cnt).filter(r => cnt[r] >= 2); return holeRanks.some(r => pairs.includes(r)) ? 'two pair' : 'two pair (board)'; }
    if (cat === CAT.ONE_PAIR) {
      const pr = firstWith(2); if (!pr) return 'pair';
      if (holeRanks[0] === holeRanks[1] && holeRanks[0] === pr) return boardRanks.every(br => pos(pr) < pos(br)) ? `overpair (${pr}${pr})` : `pocket pair (${pr}${pr})`;
      if (holeRanks.includes(pr) && boardRanks.includes(pr)) { const sb = [...new Set(boardRanks)].sort((a, b) => pos(a) - pos(b)); if (pr === sb[0]) return `top pair (${pr}s)`; if (sb.length > 1 && pr === sb[1]) return `second pair (${pr}s)`; return `bottom pair (${pr}s)`; }
      return 'pair on board';
    }
    // high card — surface draws pre-river
    if (board.length < 5) {
      const holeSuits = hand.map(c => E.cardToStr(c)[1]);
      const allSuits = holeSuits.concat(board.map(c => E.cardToStr(c)[1]));
      const scnt = {}; allSuits.forEach(s => scnt[s] = (scnt[s] || 0) + 1);
      if (holeSuits.some(s => scnt[s] === 4)) return 'flush draw';
      const vals = [...new Set(allRanks.map(pos))].sort((a, b) => a - b);
      for (let i = 0; i <= vals.length - 4; i++) if (vals[i + 3] - vals[i] <= 4) return 'straight draw';
    }
    const hi = holeRanks.slice().sort((a, b) => pos(a) - pos(b))[0];
    return `${hi}-high`;
  }

  const API = {
    STYLE_RANGES, estimateRange, parseRangeNotation, boardConnectionScore,
    handToKey, gordonTier, gordonComboDescription, gordonAdvice, potOddsHeader,
    computeOuts, scareCards, equityVsRanges, expandCombos, metrics, RANKS, ORDER,
    categorizePreflop, handName, describeMadeHand,
  };
  if (isNode) module.exports = API;
  else root.PokerToMLogic = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
