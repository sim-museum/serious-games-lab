/*
 * PokerIQ — File menu: Save / Load a game, Buy more chips, Hand-history replay
 * browser, and the per-hand-class P&L table. Ports pokerIQ.py's File menu
 * (_menu_save_game / _menu_load_game / Buy More Chips), the desktop
 * HandClassPnLTable, and the hand-history replay that was a known web gap.
 *
 * Each builder takes { ctrl, view } and drives the shared modal host on the
 * View. Browser-only (uses Blob/FileReader); the build inlines it as a global.
 */
(function (root) {
  'use strict';

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function downloadText(name, text, mime) {
    try {
      const blob = new Blob([text], { type: mime || 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = name;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return true;
    } catch (e) { return false; }
  }

  // ---- Save game (download JSON) ----
  function saveGame(ctx) {
    const { ctrl, view } = ctx;
    const state = ctrl.saveState();
    const text = JSON.stringify(state, null, 2);
    const d = ctrl.now();
    const p2 = n => String(n).padStart(2, '0');
    const name = `pokerIQ_save_${d.getFullYear()}${p2(d.getMonth() + 1)}${p2(d.getDate())}_${p2(d.getHours())}${p2(d.getMinutes())}${p2(d.getSeconds())}.json`;
    const ok = downloadText(name, text, 'application/json');
    const card = document.createElement('div'); card.className = 'modal-card';
    card.innerHTML = `<h2>Save game</h2>
      <div class="sub">${ok ? 'Saved as <code>' + esc(name) + '</code>.' : 'Download was blocked — copy the text below into a <code>.json</code> file.'} Load it later from <b>File ▸ Load game</b> to resume — mid-hand state and all.</div>
      <textarea class="log-preview" readonly></textarea>
      <div class="modal-actions"></div>`;
    card.querySelector('.log-preview').value = text;
    const copy = document.createElement('button'); copy.className = 'btn check'; copy.textContent = 'Copy';
    copy.onclick = () => { const ta = card.querySelector('.log-preview'); ta.select(); try { navigator.clipboard.writeText(text); } catch (e) { try { document.execCommand('copy'); } catch (e2) {} } copy.textContent = 'Copied ✓'; };
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').append(copy, close);
    view.showModal(card);
  }

  // ---- Load game (upload JSON or paste) ----
  function loadGame(ctx) {
    const { ctrl, view } = ctx;
    const card = document.createElement('div'); card.className = 'modal-card';
    card.innerHTML = `<h2>Load game</h2>
      <div class="sub">Choose a <code>pokerIQ_save_*.json</code> file, or paste its contents. Resumes exactly where you saved.</div>
      <input type="file" accept="application/json,.json" id="lg-file" class="lg-file">
      <textarea class="log-preview" id="lg-text" placeholder="…or paste the save JSON here"></textarea>
      <div class="lg-err" id="lg-err" style="color:#ff7777;min-height:18px;"></div>
      <div class="modal-actions"></div>`;
    const err = card.querySelector('#lg-err');
    const apply = (text) => {
      try {
        const obj = JSON.parse(text);
        ctrl.loadState(obj);
        view.closeModal();
      } catch (e) { err.textContent = 'Could not load: ' + (e && e.message ? e.message : 'invalid file'); }
    };
    card.querySelector('#lg-file').onchange = (e) => {
      const f = e.target.files && e.target.files[0]; if (!f) return;
      const r = new FileReader();
      r.onload = () => apply(String(r.result));
      r.onerror = () => { err.textContent = 'Could not read the file.'; };
      r.readAsText(f);
    };
    const load = document.createElement('button'); load.className = 'btn check'; load.textContent = 'Load pasted text';
    load.onclick = () => { const t = card.querySelector('#lg-text').value.trim(); if (t) apply(t); else err.textContent = 'Pick a file or paste the JSON.'; };
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Cancel';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').append(load, close);
    view.showModal(card);
  }

  // ---- Buy more chips (between hands, single-player top-up) ----
  function buyChips(ctx) {
    const { ctrl, view } = ctx;
    const card = document.createElement('div'); card.className = 'modal-card';
    const hero = ctrl.game.players[0];
    card.innerHTML = `<h2>Buy more chips</h2>
      <div class="sub">Top up <b>${esc(hero.name)}</b>'s stack between hands. Current stack: <b>$${hero.stack}</b>.</div>
      <div class="buy-row"><label>Add chips $</label><input type="number" id="bc-amt" value="200" min="1" step="50"></div>
      <div class="modal-actions"></div>`;
    const add = document.createElement('button'); add.className = 'btn check'; add.textContent = 'Add chips';
    add.onclick = () => { const v = parseInt(card.querySelector('#bc-amt').value, 10) || 0; if (v > 0) ctrl.buyChips(v, 0); view.closeModal(); };
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Cancel';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').append(add, close);
    view.showModal(card);
  }

  // ---- Hand-history replay browser ----
  // Lists every completed hand this session; open any one's full Hand Summary,
  // step prev/next. Closes the desktop's --replay gap for in-session review.
  function handHistory(ctx) {
    const { ctrl, view } = ctx;
    const hist = ctrl.handHistories.slice();
    const card = document.createElement('div'); card.className = 'modal-card hh-modal';
    if (!hist.length) {
      card.innerHTML = `<h2>Hand history</h2><div class="notice">No completed hands yet this session — play a hand, then come back to replay it.</div><div class="modal-actions"></div>`;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      view.showModal(card); return;
    }
    const rows = hist.map((h, i) => {
      const heroSeat = (ctrl.humanSeats && ctrl.humanSeats.size) ? Math.min(...ctrl.humanSeats) : 0;
      const net = ((h.result && h.result.net) || []).find(n => n.seat === heroSeat);
      const v = net ? net.net : 0;
      const cls = v > 0 ? 'pos' : v < 0 ? 'neg' : 'muted';
      const hero = (h.holeCards || []).find(x => x.seat === heroSeat);
      const cards = hero ? hero.cards.map(c => root.PokerEngine.cardToStr(c)).join(' ') : '';
      return `<tr data-i="${i}"><td>#${h.handNumber}</td><td class="hh-cards">${esc(cards)}</td><td class="${cls}">${v >= 0 ? '+' : '-'}$${Math.abs(v)}</td><td><button class="ghost hh-open" data-i="${i}">Replay ▸</button></td></tr>`;
    }).join('');
    card.innerHTML = `<h2>Hand history — ${hist.length} hand${hist.length > 1 ? 's' : ''}</h2>
      <div class="sub">Replay any hand's full Theory-of-Mind summary (per-street equity, made hands, hindsight, results).</div>
      <div class="hh-scroll"><table class="hh-table"><tr><th>Hand</th><th>Your cards</th><th>Net</th><th></th></tr>${rows}</table></div>
      <div class="modal-actions"></div>`;
    card.querySelector('.hh-scroll').addEventListener('click', e => {
      const b = e.target.closest('.hh-open'); if (!b) return;
      const i = parseInt(b.getAttribute('data-i'), 10);
      replayHand(ctx, hist, i);
    });
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').appendChild(close);
    view.showModal(card);
  }

  // open one hand's summary with prev/next stepping through the session
  function replayHand(ctx, hist, i) {
    const { ctrl, view } = ctx;
    i = Math.max(0, Math.min(hist.length - 1, i));
    view.showHandSummary(hist[i]);
    // graft prev/next controls onto the summary's action row
    const act = view.el.modal.querySelector('.hs-actions');
    if (act) {
      const nav = document.createElement('span'); nav.className = 'hh-nav';
      const prev = document.createElement('button'); prev.className = 'ghost'; prev.textContent = '◄ Prev hand'; prev.disabled = i <= 0;
      prev.onclick = () => replayHand(ctx, hist, i - 1);
      const idx = document.createElement('span'); idx.className = 'muted'; idx.textContent = ` Hand #${hist[i].handNumber} (${i + 1}/${hist.length}) `;
      const next = document.createElement('button'); next.className = 'ghost'; next.textContent = 'Next hand ►'; next.disabled = i >= hist.length - 1;
      next.onclick = () => replayHand(ctx, hist, i + 1);
      nav.append(prev, idx, next);
      act.insertBefore(nav, act.firstChild);
    }
  }

  // ---- Hand-class P&L table (desktop HandClassPnLTable) ----
  function handClassPnL(ctx) {
    const { ctrl, view } = ctx;
    const bb = ctrl.game.bb() || 2;
    const rows = Object.values(ctrl.holeStats)
      .sort((a, b) => b.net - a.net || a.cls.localeCompare(b.cls))
      .slice(0, 50)
      .map(h => {
        const played = h.played || 0;
        const bb100 = played > 0 ? (h.net / bb / played) * 100 : 0;
        const cls = h.net > 0 ? 'pos' : h.net < 0 ? 'neg' : 'muted';
        return `<tr><td>${esc(h.cls)}</td><td>${h.seen}</td><td>${h.won}</td><td>${h.lost}</td><td class="${cls}">${h.net >= 0 ? '+' : '-'}$${Math.abs(h.net)}</td><td class="${cls}">${bb100 >= 0 ? '+' : ''}${bb100.toFixed(1)}</td></tr>`;
      }).join('');
    const card = document.createElement('div'); card.className = 'modal-card hh-modal';
    card.innerHTML = `<h2>bb/100 by starting hand</h2>
      <div class="sub">Per-hand-class P&amp;L for this session — find the hand groups that leak (sorted by net).</div>
      ${rows ? `<div class="hh-scroll"><table class="hh-table"><tr><th>Hand</th><th>Seen</th><th>Won</th><th>Lost</th><th>Net</th><th>bb/100</th></tr>${rows}</table></div>`
        : '<div class="notice">No hands recorded yet — play some hands to populate this table.</div>'}
      <div class="modal-actions"></div>`;
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').appendChild(close);
    view.showModal(card);
  }

  const API = { saveGame, loadGame, buyChips, handHistory, handClassPnL };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerFiles = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
