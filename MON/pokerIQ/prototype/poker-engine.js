/*
 * PokerIQ — JS hand-evaluator + Monte-Carlo equity engine (prototype).
 *
 * Self-contained, zero-dependency. Designed to replace the eval7 C-extension
 * (calc_equity_* in pokerIQ.py) and the pure-Python poker_iq/evaluator.py.
 *
 * Card model mirrors poker_iq/models.py:
 *   rank: 2..14 (14 = Ace), suit: 0..3 = c,d,h,s
 *   string form: "Ah", "Ks", "2c"   |   code 0..51 = (rank-2)*4 + suit
 *
 * evaluate7() returns ONE comparable integer: higher = better hand.
 * Encoding: category(4b) << 20 | t1<<16 | t2<<12 | t3<<8 | t4<<4 | t5
 * The absolute number is meaningless across engines; only the ordering matters,
 * and that ordering matches eval7 / poker_iq exactly (proven by validate.js).
 */

(function (root) {
  'use strict';

  const RANKS = '23456789TJQKA';      // index 0 -> rank 2
  const SUITS = 'cdhs';                // index 0 -> clubs

  // ---- category constants (match poker_iq HandRank ordering) ----
  const CAT = {
    HIGH_CARD: 0, ONE_PAIR: 1, TWO_PAIR: 2, TRIPS: 3, STRAIGHT: 4,
    FLUSH: 5, FULL_HOUSE: 6, QUADS: 7, STRAIGHT_FLUSH: 8,
  };
  const CAT_NAMES = [
    'High Card', 'One Pair', 'Two Pair', 'Three of a Kind', 'Straight',
    'Flush', 'Full House', 'Four of a Kind', 'Straight Flush',
  ];

  function rankToChar(r) { return RANKS[r - 2]; }
  function charToRank(c) {
    const i = RANKS.indexOf(c.toUpperCase());
    if (i < 0) throw new Error('bad rank: ' + c);
    return i + 2;
  }
  function charToSuit(c) {
    const i = SUITS.indexOf(c.toLowerCase());
    if (i < 0) throw new Error('bad suit: ' + c);
    return i;
  }

  // A card is encoded as the small integer (rank << 2) | suit for speed.
  // rank 2..14, suit 0..3.  (This is NOT the 0..51 deck code; see codeOf.)
  function cardFromStr(s) {
    s = s.trim();
    return (charToRank(s[0]) << 2) | charToSuit(s[1]);
  }
  function cardToStr(card) {
    return rankToChar(card >> 2) + SUITS[card & 3];
  }
  function rankOf(card) { return card >> 2; }
  function suitOf(card) { return card & 3; }
  // 0..51 deck code, matching poker_iq Card.to_code(): (rank-2)*4 + suit
  function codeOf(card) { return (rankOf(card) - 2) * 4 + suitOf(card); }
  function cardFromCode(code) { return (((code >> 2) + 2) << 2) | (code & 3); }

  function fullDeck() {
    const d = new Array(52);
    for (let c = 0; c < 52; c++) d[c] = cardFromCode(c);
    return d;
  }

  // Highest 5-in-a-row in a rank bitmask (bits 2..14). Returns high rank or 0.
  // Handles the wheel (A-2-3-4-5) by mirroring the ace to bit 1.
  function straightHigh(mask) {
    let m = mask;
    if (m & (1 << 14)) m |= (1 << 1);     // ace plays low
    // window of 5 consecutive bits, from ace-high down to 5-high (wheel)
    for (let hi = 14; hi >= 5; hi--) {
      const need = 0b11111 << (hi - 4);    // bits hi..hi-4
      if ((m & need) === need) return hi;
    }
    return 0;
  }

  /**
   * Evaluate the best 5-card poker hand from 5, 6, or 7 cards.
   * @param {number[]} cards  array of card ints (rank<<2|suit)
   * @returns {number} comparable score (higher = better)
   */
  function evaluate(cards) {
    const rankCount = new Int8Array(15);          // index = rank 2..14
    const suitMask = [0, 0, 0, 0];                // per-suit rank bitmask
    const suitCnt = [0, 0, 0, 0];
    let rankMask = 0;

    for (let i = 0; i < cards.length; i++) {
      const c = cards[i];
      const r = c >> 2, s = c & 3;
      rankCount[r]++;
      suitMask[s] |= (1 << r);
      suitCnt[s]++;
      rankMask |= (1 << r);
    }

    // --- flush / straight-flush ---
    let flushSuit = -1;
    for (let s = 0; s < 4; s++) if (suitCnt[s] >= 5) { flushSuit = s; break; }
    if (flushSuit >= 0) {
      const sfHigh = straightHigh(suitMask[flushSuit]);
      if (sfHigh) return enc(CAT.STRAIGHT_FLUSH, sfHigh);
    }

    // --- count-based categories: build ranks-by-count descending ---
    // quads / trips / pairs lists, each sorted high->low by virtue of scan.
    let quad = 0, tripsHi = 0, tripsLo = 0, pairHi = 0, pairMid = 0;
    for (let r = 14; r >= 2; r--) {
      const n = rankCount[r];
      if (n === 4) quad = r;
      else if (n === 3) { if (!tripsHi) tripsHi = r; else if (!tripsLo) tripsLo = r; }
      else if (n === 2) { if (!pairHi) pairHi = r; else if (!pairMid) pairMid = r; }
    }

    if (quad) {
      const k = topRanks(rankCount, 1, [quad]);
      return enc(CAT.QUADS, quad, k[0]);
    }

    // full house: best trips + best pair (a 2nd trips counts as the pair)
    if (tripsHi) {
      let pair = pairHi;
      if (tripsLo && tripsLo > pair) pair = tripsLo;     // 2nd trips as pair
      if (pair) return enc(CAT.FULL_HOUSE, tripsHi, pair);
    }

    if (flushSuit >= 0) {
      const fr = topBits(suitMask[flushSuit], 5);
      return enc(CAT.FLUSH, fr[0], fr[1], fr[2], fr[3], fr[4]);
    }

    const sHigh = straightHigh(rankMask);
    if (sHigh) return enc(CAT.STRAIGHT, sHigh);

    if (tripsHi) {
      const k = topRanks(rankCount, 2, [tripsHi]);
      return enc(CAT.TRIPS, tripsHi, k[0], k[1]);
    }

    if (pairHi && pairMid) {
      const k = topRanks(rankCount, 1, [pairHi, pairMid]);
      return enc(CAT.TWO_PAIR, pairHi, pairMid, k[0]);
    }

    if (pairHi) {
      const k = topRanks(rankCount, 3, [pairHi]);
      return enc(CAT.ONE_PAIR, pairHi, k[0], k[1], k[2]);
    }

    const k = topRanks(rankCount, 5, []);
    return enc(CAT.HIGH_CARD, k[0], k[1], k[2], k[3], k[4]);
  }

  // pack category + up to 5 tiebreak ranks into one int
  function enc(cat, t1 = 0, t2 = 0, t3 = 0, t4 = 0, t5 = 0) {
    return (cat << 20) | (t1 << 16) | (t2 << 12) | (t3 << 8) | (t4 << 4) | t5;
  }

  // top `n` ranks present (by count, high->low), excluding `exclude` ranks
  function topRanks(rankCount, n, exclude) {
    const out = [];
    for (let r = 14; r >= 2 && out.length < n; r--) {
      if (exclude.indexOf(r) >= 0) continue;
      let c = rankCount[r];
      while (c-- > 0 && out.length < n) out.push(r);
    }
    return out;
  }
  // top `n` set bits of a rank bitmask, high->low
  function topBits(mask, n) {
    const out = [];
    for (let r = 14; r >= 2 && out.length < n; r--) if (mask & (1 << r)) out.push(r);
    return out;
  }

  function categoryOf(score) { return score >> 20; }
  function describe(score) {
    const cat = categoryOf(score);
    const t1 = (score >> 16) & 0xf, t2 = (score >> 12) & 0xf;
    const rc = rankToChar;
    switch (cat) {
      case CAT.STRAIGHT_FLUSH: return t1 === 14 ? 'Royal Flush' : `Straight Flush, ${rc(t1)}-high`;
      case CAT.QUADS: return `Four of a Kind, ${rc(t1)}s`;
      case CAT.FULL_HOUSE: return `Full House, ${rc(t1)}s full of ${rc(t2)}s`;
      case CAT.FLUSH: return `Flush, ${rc(t1)}-high`;
      case CAT.STRAIGHT: return `Straight, ${rc(t1)}-high`;
      case CAT.TRIPS: return `Three of a Kind, ${rc(t1)}s`;
      case CAT.TWO_PAIR: return `Two Pair, ${rc(t1)}s and ${rc(t2)}s`;
      case CAT.ONE_PAIR: return `Pair of ${rc(t1)}s`;
      default: return `High Card, ${rc(t1)}`;
    }
  }

  // ---------- Monte-Carlo equity ----------
  // Fisher-Yates partial shuffle on the live deck (in place, first k slots).
  function dealShuffle(deck, n, k, rng) {
    for (let i = 0; i < k; i++) {
      const j = i + Math.floor(rng() * (n - i));
      const t = deck[i]; deck[i] = deck[j]; deck[j] = t;
    }
  }

  /**
   * Equity of hero vs N random opponents (mirrors calc_equity_hidden).
   * @param {number[]} hero    2 hero cards
   * @param {number[]} board   0..5 board cards
   * @param {object} opts {iterations=2000, opponents=1, rng=Math.random}
   * @returns {number} win probability incl. tie split, 0..1
   */
  function equityVsRandom(hero, board, opts = {}) {
    const iterations = opts.iterations || 2000;
    const opponents = opts.opponents || 1;
    const rng = opts.rng || Math.random;

    const used = new Set([...hero, ...board].map(codeOf));
    const liveBase = fullDeck().filter(c => !used.has(codeOf(c)));
    const need = 5 - board.length;
    const draw = opponents * 2 + need;

    let wins = 0, ties = 0, done = 0;
    const hand = new Array(7);
    for (let it = 0; it < iterations; it++) {
      const n = liveBase.length;
      if (n < draw) break;
      dealShuffle(liveBase, n, draw, rng);

      // complete board
      let bi = 0;
      const full = board.slice();
      for (let i = 0; i < need; i++) full.push(liveBase[bi++]);

      // hero score
      hand.length = 0;
      for (const c of hero) hand.push(c);
      for (const c of full) hand.push(c);
      const heroScore = evaluate(hand);

      let bestOpp = -1;
      for (let o = 0; o < opponents; o++) {
        hand.length = 0;
        hand.push(liveBase[bi++], liveBase[bi++]);
        for (const c of full) hand.push(c);
        const s = evaluate(hand);
        if (s > bestOpp) bestOpp = s;
      }
      if (heroScore > bestOpp) wins++;
      else if (heroScore === bestOpp) ties++;
      done++;
    }
    return done ? (wins + ties / 2) / done : 0;
  }

  /**
   * Multiway equity — each known hand's share of the pot (mirrors
   * calc_multiway_equity). Returns array of equities aligned to `hands`.
   * @param {number[][]} hands  array of 2-card hands
   * @param {number[]} board    0..5 board cards
   */
  function equityMultiway(hands, board, opts = {}) {
    const iterations = opts.iterations || 2000;
    const rng = opts.rng || Math.random;
    const used = new Set();
    for (const h of hands) for (const c of h) used.add(codeOf(c));
    for (const c of board) used.add(codeOf(c));
    const liveBase = fullDeck().filter(c => !used.has(codeOf(c)));
    const need = 5 - board.length;

    const eq = new Array(hands.length).fill(0);
    const hand = new Array(7);
    let done = 0;
    for (let it = 0; it < iterations; it++) {
      const n = liveBase.length;
      if (n < need) break;
      dealShuffle(liveBase, n, need, rng);
      const full = board.slice();
      for (let i = 0; i < need; i++) full.push(liveBase[i]);

      let best = -1; const scores = new Array(hands.length);
      for (let p = 0; p < hands.length; p++) {
        hand.length = 0;
        hand.push(hands[p][0], hands[p][1]);
        for (const c of full) hand.push(c);
        const s = evaluate(hand);
        scores[p] = s;
        if (s > best) best = s;
      }
      let winners = 0;
      for (let p = 0; p < hands.length; p++) if (scores[p] === best) winners++;
      for (let p = 0; p < hands.length; p++) if (scores[p] === best) eq[p] += 1 / winners;
      done++;
    }
    if (done) for (let p = 0; p < eq.length; p++) eq[p] /= done;
    return eq;
  }

  const API = {
    CAT, CAT_NAMES,
    cardFromStr, cardToStr, cardFromCode, codeOf, rankOf, suitOf, fullDeck,
    evaluate, categoryOf, describe, straightHigh,
    equityVsRandom, equityMultiway,
    // helpers for tests
    handFromStr: s => s.trim().split(/\s+/).map(cardFromStr),
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerEngine = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
