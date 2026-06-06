/*
 * PokerIQ — bot AI. Faithful port of Player.get_bot_action (pokerIQ.py) for the
 * 9 built-in styles, plus the poker_iq basic/improved equity bots.
 *
 * Exposes a single decide(game, player) -> [action, amount] that the Game
 * engine calls via its botDecide hook. All equity gates use the JS Monte-Carlo
 * engine (engine.js) — multiway `equity` for fold decisions, heads-up `hu` for
 * raise decisions, matching the Python rationale documented inline there.
 */
(function (root) {
  'use strict';
  const E = (typeof require !== 'undefined') ? require('./engine.js') : root.PokerEngine;

  // equity iterations kept modest for snappy bot turns (Python used 200-400)
  const HIDDEN_ITERS = 280;
  const HU_ITERS = 200;

  function stats(game, player) {
    const board = game.board;
    const opps = game.activePlayers().filter(p => p !== player);
    const numOpp = Math.max(1, opps.length);
    const toCall = Math.max(0, game.currentBet - player.betInRound);
    const pot = game.pot;
    const potOdds = (pot + toCall) > 0 ? toCall / (pot + toCall) : 0;
    const rng = game.rng;
    const equity = player.hand.length
      ? E.equityVsRandom(player.hand, board, { iterations: HIDDEN_ITERS, opponents: numOpp, rng })
      : 0;
    const hu = player.hand.length
      ? E.equityVsRandom(player.hand, board, { iterations: HU_ITERS, opponents: 1, rng })
      : equity;
    return { toCall, pot, potOdds, equity, hu, numOpp, opps };
  }

  // bet sizing helpers — mirror the integer-pot math in the Python
  function potBet(game, frac) { return Math.floor(Math.max(1, game.pot) * frac); }
  function raiseTo(game, player, target, minExtra) {
    // python returned an absolute "raise to" amount; clamp to legal here
    const bb = game.bb();
    const toCall = Math.max(0, game.currentBet - player.betInRound);
    return Math.max(target, toCall + (minExtra || 2 * bb) + player.betInRound);
  }

  function decide(game, player) {
    // poker_iq equity bots take priority if assigned
    if (player.botType === 'piq_basic_equity') return piqBasic(game, player);
    if (player.botType === 'piq_improved_equity') return piqImproved(game, player);

    const s = stats(game, player);
    const rng = game.rng;
    const { toCall, pot, potOdds, equity, hu } = s;
    player.actionsThisRound = player.actionsThisRound; // (no-op, parity marker)

    // huge-bet discipline (all styles): facing a bet > 25% stack, fold < 60%
    if (toCall > player.stack * 0.25 && equity < 0.60) return ['f', 0];

    switch (player.style) {
      case 'tight': {
        if (equity < potOdds + 0.15) return ['f', 0];
        if (hu > 0.75) return ['r', potBet(game, 0.75)];
        return ['c', 0];
      }
      case 'loose': {
        if (equity < potOdds - 0.05) return ['f', 0];
        return ['c', 0];
      }
      case 'station': {
        if (equity < 0.08 && toCall > 0) return ['f', 0];
        return ['c', 0];
      }
      case 'aggressive': {
        if (player.actionsThisRound > 4) return ['c', 0];
        const r = rng();
        if (hu > 0.80) return ['r', raiseTo(game, player, potBet(game, 0.9 + rng() * 0.2))];
        if (hu > 0.50) {
          if (r < 0.85) return ['r', raiseTo(game, player, potBet(game, 0.6 + rng() * 0.35))];
          return ['c', 0];
        }
        if (hu > 0.25) {
          if (r < 0.35) return ['r', raiseTo(game, player, potBet(game, 0.5 + rng() * 0.25))];
          if (equity >= potOdds + 0.02) return ['c', 0];
          return ['f', 0];
        }
        if (equity < potOdds) return ['f', 0];
        return ['c', 0];
      }
      case 'optimal': {
        if (player.actionsThisRound > 3) return ['c', 0];
        if (hu > 0.80) return ['r', potBet(game, 0.8)];
        if (hu > 0.60) return ['r', potBet(game, 0.5)];
        if (equity >= potOdds) return ['c', 0];
        return ['f', 0];
      }
      case 'shark': {
        if (player.actionsThisRound > 4) return ['c', 0];
        const bb = game.bb();
        const spr = pot > 0 ? player.stack / pot : 10;
        if (hu > 0.85) {
          if (rng() < 0.25) return ['c', 0];
          return ['r', raiseTo(game, player, potBet(game, spr > 2 ? 1.0 : 0.7))];
        }
        if (hu > 0.70) {
          if (rng() < 0.66) return ['r', raiseTo(game, player, potBet(game, 0.75))];
          return ['c', 0];
        }
        if (hu > 0.55) {
          if (rng() < 0.5 && toCall < pot * 0.4)
            return ['r', raiseTo(game, player, potBet(game, 0.5), bb)];
          return ['c', 0];
        }
        if (equity >= potOdds + 0.04) return ['c', 0];
        if (toCall < pot * 0.4 && equity > 0.20 && rng() < 0.12)
          return ['r', raiseTo(game, player, potBet(game, 0.55), bb)];
        if (toCall === 0) return ['c', 0];
        return ['f', 0];
      }
      case 'exploit': {
        if (player.actionsThisRound > 4) return ['c', 0];
        const bb = game.bb();
        const opps = s.opps;
        const tightN = opps.filter(p => p.style === 'tight').length;
        const looseN = opps.filter(p => p.style === 'loose' || p.style === 'station').length;
        const aggroN = opps.filter(p => p.style === 'aggressive').length;
        const stealFreq = tightN > looseN ? 0.28 : 0.10;
        const valueSize = looseN > 0 ? 0.85 : 0.65;
        const slowVsAggro = aggroN > 0;
        if (hu > 0.80) {
          if (slowVsAggro && rng() < 0.5) return ['c', 0];
          return ['r', raiseTo(game, player, potBet(game, valueSize))];
        }
        if (hu > 0.60) {
          if (slowVsAggro && toCall > 0) return ['c', 0];
          return ['r', raiseTo(game, player, potBet(game, valueSize * 0.7), bb)];
        }
        if (equity >= potOdds + 0.03) return ['c', 0];
        if (toCall === 0 && rng() < stealFreq)
          return ['r', raiseTo(game, player, potBet(game, 0.5), 2 * bb)];
        if (toCall === 0) return ['c', 0];
        return ['f', 0];
      }
      case 'icm': {
        const bb = game.bb();
        const spr = pot > 0 ? player.stack / pot : 99;
        if (spr < 3 && player.stack <= 25 * bb) {
          if (hu >= 0.55) return ['r', player.stack + player.betInRound]; // shove
          if (toCall > 0) return ['f', 0];
          return ['c', 0];
        }
        if (hu > 0.80) return ['r', potBet(game, 0.8)];
        if (hu > 0.60) return ['r', potBet(game, 0.5)];
        if (equity >= potOdds + 0.03) return ['c', 0];
        return ['f', 0];
      }
      case 'tom': {
        if (player.actionsThisRound > 3) return ['c', 0];
        const opps = s.opps;
        const tightN = opps.filter(p => p.style === 'tight').length;
        const looseN = opps.filter(p => p.style === 'loose').length;
        const aggroN = opps.filter(p => p.style === 'aggressive').length;
        let adjHu = hu;
        if (tightN > 0 && toCall > pot * 0.5) adjHu *= 0.8;
        if (looseN > 0 && hu > 0.6) adjHu *= 1.1;
        let adjCall = equity;
        if (aggroN > 0 && toCall > 0 && equity > 0.35) adjCall = Math.max(equity, potOdds + 0.05);
        if (adjHu > 0.75) return ['r', potBet(game, 0.75)];
        if (adjHu > 0.55) {
          if (rng() < 0.3) return ['r', potBet(game, 0.5)];
          return ['c', 0];
        }
        if (adjCall >= potOdds) return ['c', 0];
        if (rng() < 0.15 && toCall < pot * 0.3 && hu > 0.35) return ['r', potBet(game, 0.6)];
        return ['f', 0];
      }
      default:
        return ['c', 0];
    }
  }

  // ---- poker_iq equity bots (ported from basic_equity_bot / improved) ----
  function piqBasic(game, player) {
    const s = stats(game, player);
    const { toCall, potOdds, equity } = s;
    if (toCall === 0) {
      if (equity > 0.65) return ['r', potBet(game, 0.6)];
      return ['c', 0];
    }
    if (equity < potOdds) return ['f', 0];
    if (equity > 0.75) return ['r', potBet(game, 0.7)];
    return ['c', 0];
  }
  function piqImproved(game, player) {
    const s = stats(game, player);
    const rng = game.rng;
    const { toCall, pot, potOdds, equity, hu } = s;
    const preflop = game.board.length === 0;
    // position-aware: tighten OOP, widen on/near button
    const pos = game.positionOf(player.seat);
    const late = pos === 'BT' || pos === 'CO';
    const callFloor = potOdds + (late ? -0.02 : 0.03);
    if (preflop) {
      if (hu > 0.66) return ['r', raiseTo(game, player, potBet(game, 0.8))];
      if (hu > 0.5 || (late && hu > 0.45)) return ['c', 0];
      if (toCall === 0) return ['c', 0];
      return equity >= callFloor ? ['c', 0] : ['f', 0];
    }
    // postflop: c-bet as aggressor proxy, value-raise strong, semibluff draws
    if (hu > 0.78) return ['r', raiseTo(game, player, potBet(game, 0.7))];
    if (hu > 0.6) {
      if (toCall === 0 && rng() < 0.7) return ['r', potBet(game, 0.6)];
      return ['c', 0];
    }
    if (equity >= callFloor) return ['c', 0];
    if (toCall === 0 && rng() < 0.25) return ['r', potBet(game, 0.5)]; // light stab
    return toCall === 0 ? ['c', 0] : ['f', 0];
  }

  const API = { decide };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerBots = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
