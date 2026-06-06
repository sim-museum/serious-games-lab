/*
 * PokerIQ — session log writer. Reproduces the PyQt pokerIQ log file format
 * EXACTLY (byte-for-byte where it matters) so a saved web-app log can be fed to
 * an AI for the same post-game analysis/commentary the desktop app supports.
 *
 * The PyQt app writes the file via a stream of write_log(msg) calls (log_action
 * funnels through the same path). We model that precisely: LogBook records each
 * msg in order; text() === msgs.join("\n") + "\n", which is exactly what
 * f.write(msg + "\n") per call produces.
 *
 * Reference: pokerIQ.py init_logfile / _log_game_status / deal_hand /
 * post_blind / process_action / deal_community / showdown / _log_session_summary.
 */
(function (root) {
  'use strict';
  const HANDTYPE = ['High Card', 'Pair', 'Two Pair', 'Trips', 'Straight', 'Flush', 'Full House', 'Quads', 'Straight Flush'];

  // python-style padding helpers
  const padR = (s, n) => { s = String(s); return s.length >= n ? s : s + ' '.repeat(n - s.length); };  // {:<n}
  const padL = (s, n) => { s = String(s); return s.length >= n ? s : ' '.repeat(n - s.length) + s; };  // {:>n}
  const pct1 = f => (f * 100).toFixed(1) + '%';   // python {:.1%}

  class LogBook {
    constructor() { this.msgs = []; this.gameStatusLogged = false; }
    w(msg) { this.msgs.push(msg); }
    text() { return this.msgs.join('\n') + '\n'; }

    // ---- session header (init_logfile) ----
    sessionHeader(startedStr) {
      const bar = '='.repeat(60);
      this.w(bar);
      this.w('POKER LEARNING GAME - SESSION LOG');
      this.w(`Started: ${startedStr}`);
      this.w(bar);
      this.w('');                       // init_logfile's trailing blank line
    }

    // ---- GAME STATUS (first hand only) ----
    gameStatus(g) {
      this.w('\n=== GAME STATUS ===');
      this.w(`  Game Name: ${g.mode}`);
      this.w("  Game Type: Texas Hold 'em");
      this.w('  Limit Type: No Limit');
      this.w(`  Starting Chips: $${g.startingChips}`);
      this.w(`  Hands Dealt: ${g.handsDealt}`);
      this.w(`  Next Blind Increase: ${g.nextBlind}`);
      this.w(`  # Players (Original/Current): ${g.origPlayers}/${g.curPlayers}`);
      this.w(`  Blinds (Original/Current): $${g.origSb}/$${g.origBb} → $${g.curSb}/$${g.curBb}`);
      this.w('  Ante: None');
      this.w('  Limits: N/A');
      this.w('===================\n');
    }

    // ---- per-hand ----
    newHand(n, timeStr) {
      const bar = '='.repeat(60);
      this.w('=== NEW HAND ===');     // log_action
      this.w('\n' + bar);             // write_log(f"\n{'='*60}")
      this.w(`HAND #${n} - ${timeStr}`);
      this.w(bar);
    }
    blindIncrease(sb, bb) { this.w(`*** BLINDS INCREASE: $${sb}/$${bb} ***`); }
    dealerAndHole(dealerName, hole) {
      this.w(`Dealer: ${dealerName}`);
      this.w('Hole Cards Dealt:');
      for (const h of hole) this.w(`  ${h.name}: ${h.cards}`);
    }
    post(name, amt) { this.w(`${name} posts $${amt}`); }
    fold(name) { this.w(`${name}: Folds`); }
    check(name) { this.w(`${name}: Checks`); }
    call(name, amt) { this.w(`${name}: Calls $${amt}`); }
    raise(name, total) { this.w(`${name}: Raises to $${total}`); }

    // street: "--- Street ---" then [STATS] block then "Board: ..."
    street(streetName, statsRows, boardStr) {
      this.w(`--- ${streetName} ---`);
      this.w('  [STATS]');
      for (const r of statsRows) {
        this.w(`    ${padR(r.name, 15)} Cards: ${r.cards}  Equity: ${pct1(r.equity)}  PotOdds: ${pct1(r.potOdds)}`);
      }
      this.w(`Board: ${boardStr}`);
    }

    showdownResults(rows) { for (const r of rows) this.w(`${r.name}: ${HANDTYPE[r.cat]}`); }
    winnerUncontested(name, net) { this.w(`${name} wins $${net}!`); this.w(`Winner: ${name} - $${net} (others folded)`); }
    winnerShowdown(winners) { this.w(`WINNER: ${winners.map(w => `${w.name} ($${w.net})`).join(', ')}!`); }
    finalStacks(rows) { this.w('Final Stacks:'); for (const r of rows) this.w(`  ${r.name}: $${r.stack}`); }
    gainLoss(rows) {
      this.w('Hand Results (Gain/Loss):');
      for (const r of rows) {
        if (r.change > 0) this.w(`  ${r.name}: +$${r.change}`);
        else if (r.change < 0) this.w(`  ${r.name}: -$${Math.abs(r.change)}`);
        else this.w(`  ${r.name}: $0 (broke even)`);
      }
    }

    // ---- session summary (_log_session_summary) ----
    sessionSummary(s) {
      this.w('\n' + '#'.repeat(60));
      this.w('SESSION SUMMARY');
      this.w('#'.repeat(60));
      // TABLE STATS
      this.w('\n=== TABLE STATS ===');
      this.w('  ' + padR('Name', 16) + ' ' + padL('Status', 10) + ' ' + padL('Hands Played', 14) + ' ' + padL('Hands Won', 11) + ' ' + padL('Showdowns W/Total', 20) + ' ' + padL('All Ins', 9));
      for (const p of s.tableStats) {
        this.w('  ' + padR(p.name.slice(0, 16), 16) + ' ' + padL('$' + p.stack, 10) + ' ' + padL(p.handsPlayed, 14) + ' ' + padL(p.handsWon, 11) + ' ' + padL(`${p.showdownsWon}/${p.showdownsSeen}`, 20) + ' ' + padL(p.allIns, 9));
      }
      this.w('===================\n');
      // HOLE CARD STATS (hero)
      if (s.holeStats && s.holeStats.length) {
        this.w('\n=== HOLE CARD STATS (Hero) ===');
        this.w('  ' + padR('Hand', 5) + ' ' + padL('Seen', 5) + ' ' + padL('Played', 7) + ' ' + padL('Won', 5) + ' ' + padL('Lost', 5) + ' ' + padL('Cash Gained', 13) + ' ' + padL('Cash Lost', 11) + ' ' + padL('Net', 9));
        for (const h of s.holeStats) {
          this.w('  ' + padR(h.cls, 5) + ' ' + padL(h.seen, 5) + ' ' + padL(h.played, 7) + ' ' + padL(h.won, 5) + ' ' + padL(h.lost, 5) + ' ' + padL('$' + h.cashGained, 13) + ' ' + padL('$' + h.cashLost, 11) + ' ' + padL('$' + (h.net >= 0 ? '+' : '') + h.net, 9));
        }
        this.w('============================\n');
      }
      // CHIP COUNT
      this.w('--- CHIP COUNT ---');
      for (const p of s.tableStats) this.w(`  ${p.name}: $${p.stack}`);
      this.w(`Ended: ${s.endedStr}`);
    }
  }

  const API = { LogBook, HANDTYPE };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerLog = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
