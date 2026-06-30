/*
 * PokerIQ — Preferences. Ports the desktop Preferences dialog (Equity / Display
 * / AI Opponents tabs) and persists to localStorage (was QSettings):
 *   - Equity:  use only publicly revealed cards for Hero's equity (default on)
 *   - Display: legacy 2-colour deck (red hearts+diamonds, black clubs+spades)
 *   - AI Opponents: per-seat bot type, randomise-after-win, beat-the-defaults
 *                   unlock gate (matches BOT_PREFS + randomize_bots_enabled).
 *
 * The store is a thin typed wrapper over the shared safe localStorage (exported
 * by analytics.js as root.__piqStore) so it degrades gracefully on file://.
 */
(function (root) {
  'use strict';

  const store = (root && root.__piqStore) || (function () {
    const m = {}; return { getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: k => { delete m[k]; } };
  })();
  const getBool = (k, d) => { try { const v = store.getItem(k); return v == null ? d : v === 'true' || v === '1'; } catch (e) { return d; } };
  const getStr = (k, d) => { try { const v = store.getItem(k); return v == null ? d : v; } catch (e) { return d; } };
  const setVal = (k, v) => { try { store.setItem(k, String(v)); } catch (e) {} };

  const KEYS = {
    visibleOnly: 'piq.pref.visibleOnly',
    legacyColors: 'piq.pref.legacyColors',
    randomizeBots: 'piq.pref.randomizeBots',
    beatDefaults: 'piq.pref.beatDefaults',
  };

  const Prefs = {
    visibleOnly: () => getBool(KEYS.visibleOnly, true),
    legacyColors: () => getBool(KEYS.legacyColors, false),
    randomizeBots: () => getBool(KEYS.randomizeBots, false),
    beatDefaults: () => getBool(KEYS.beatDefaults, false),
    botFor: (seat) => getStr('piq.bot.' + seat, 'default'),
    set: (k, v) => setVal(KEYS[k] || k, v),
    setBot: (seat, v) => setVal('piq.bot.' + seat, v),
  };

  // Bot options (id → label) — mirror BOT_TYPE_OPTIONS / cute names.
  const BOT_OPTS = [
    ['default', 'Default (lineup)'],
    ['tight', 'Tight Tim'], ['loose', 'Loose Bruce'], ['aggressive', 'Aggro Angela'],
    ['shark', 'Sharkey Steve'], ['tom', 'Fluid Fiona'], ['optimal', 'Optimal Olivia'],
    ['exploit', 'Exploit Eli'], ['icm', 'ICM Ian'], ['station', 'Station Stan'],
    ['piq_basic_equity', 'Equity Eddie'], ['piq_improved_equity', 'Savvy Sarah'],
  ];

  // Apply persisted prefs to a controller + the document (called at boot and on save).
  function apply(ctrl) {
    ctrl.visibleCardsOnly = Prefs.visibleOnly();
    const rootEl = (typeof document !== 'undefined') ? (document.getElementById('app') || document.body) : null;
    if (rootEl) rootEl.classList.toggle('legacy-colors', Prefs.legacyColors());
    ctrl.randomizeBotsEnabled = Prefs.randomizeBots();
  }

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function openDialog(ctx) {
    const { ctrl, view } = ctx;
    const card = document.createElement('div'); card.className = 'modal-card';
    let tab = 'equity';
    const beat = Prefs.beatDefaults();
    // edits live in an in-memory draft and are committed to localStorage only on
    // Save — so Cancel (and tab switching) never mutate the persisted prefs.
    const draft = {
      visibleOnly: Prefs.visibleOnly(), legacyColors: Prefs.legacyColors(),
      randomizeBots: Prefs.randomizeBots(), bots: {},
    };
    ctrl.game.players.forEach((p, i) => { draft.bots[i] = Prefs.botFor(i); });
    // pull whatever the user toggled on the mounted tab into the draft
    const stash = () => {
      const vis = card.querySelector('#pf-vis'); if (vis) draft.visibleOnly = vis.checked;
      const leg = card.querySelector('#pf-legacy'); if (leg) draft.legacyColors = leg.checked;
      const rnd = card.querySelector('#pf-rand'); if (rnd) draft.randomizeBots = rnd.checked;
      card.querySelectorAll('select[data-seat]').forEach(s => { draft.bots[s.getAttribute('data-seat')] = s.value; });
    };
    const render = () => {
      card.innerHTML = `<h2>Preferences</h2>
        <div class="pf-tabs">
          <button class="pf-tab ${tab === 'equity' ? 'on' : ''}" data-t="equity">Equity</button>
          <button class="pf-tab ${tab === 'display' ? 'on' : ''}" data-t="display">Display</button>
          <button class="pf-tab ${tab === 'ai' ? 'on' : ''}" data-t="ai">AI Opponents</button>
        </div>
        <div class="pf-body" id="pf-body"></div>
        <div class="modal-actions"></div>`;
      const body = card.querySelector('#pf-body');
      if (tab === 'equity') {
        body.innerHTML = `
          <label class="pf-check"><input type="checkbox" id="pf-vis" ${draft.visibleOnly ? 'checked' : ''}>
            <span>Use only publicly revealed cards for Hero's equity</span></label>
          <div class="pf-desc">On (realistic Theory-of-Mind): equity is Monte-Carlo'd treating opponents as random ranges — only the board and your own cards are known. Off (God-style): equity is computed against opponents' <i>actual</i> hands (only meaningful with God Mode on).</div>`;
      } else if (tab === 'display') {
        body.innerHTML = `
          <label class="pf-check"><input type="checkbox" id="pf-legacy" ${draft.legacyColors ? 'checked' : ''}>
            <span>Legacy colours (red diamonds, black clubs)</span></label>
          <div class="pf-desc">Off (default): modern 4-colour deck — red hearts, blue diamonds, green clubs, black spades. On: traditional 2-colour deck — red hearts &amp; diamonds, black clubs &amp; spades.</div>
          <div class="pf-row"><span class="muted">Preview:</span>
            <span class="card heart"><b>A</b><i>♥</i></span><span class="card diamond"><b>K</b><i>♦</i></span>
            <span class="card club"><b>Q</b><i>♣</i></span><span class="card spade"><b>J</b><i>♠</i></span></div>`;
        setTimeout(() => {
          const cb = card.querySelector('#pf-legacy'); const prevRow = card.querySelector('.pf-row');
          if (cb && prevRow) { prevRow.classList.toggle('legacy-colors', cb.checked); cb.onchange = () => prevRow.classList.toggle('legacy-colors', cb.checked); }
        }, 0);
      } else {
        const seats = ctrl.game.players.map((p, i) => {
          if (i === 0 && p.isHuman) return '';      // seat 0 is the local hero
          const cur = draft.bots[i];
          return `<div class="pf-seat"><label>${esc(p.name)}</label>
            <select data-seat="${i}">${BOT_OPTS.map(([v, l]) => `<option value="${v}" ${cur === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>`;
        }).join('');
        body.innerHTML = `
          <div class="sub" style="margin-bottom:10px;">Pick the bot style for each opponent seat (applies on the next table / New hand).</div>
          ${seats}
          <label class="pf-check"><input type="checkbox" id="pf-rand" ${draft.randomizeBots ? 'checked' : ''} ${beat ? '' : 'disabled'}>
            <span>Randomise bots from the combined pool after winning a game</span></label>
          <div class="pf-status ${beat ? 'pos' : 'muted'}">${beat ? '✓ You have beaten the default bots — random pool unlocked.' : 'Beat the default bots once to unlock the advanced random pool.'}</div>`;
      }
      const actions = card.querySelector('.modal-actions');
      const save = document.createElement('button'); save.className = 'btn check'; save.textContent = 'Save';
      save.onclick = () => {
        stash();
        // commit the draft to the persistent store, now
        Prefs.set('visibleOnly', draft.visibleOnly);
        Prefs.set('legacyColors', draft.legacyColors);
        Prefs.set('randomizeBots', draft.randomizeBots);
        Object.keys(draft.bots).forEach(i => Prefs.setBot(i, draft.bots[i]));
        apply(ctrl);
        ctrl.applyBotPrefs && ctrl.applyBotPrefs();
        ctrl.refreshHeroEquity && ctrl.refreshHeroEquity();
        ctrl.render();
        view.closeModal();
      };
      const cancel = document.createElement('button'); cancel.className = 'ghost'; cancel.textContent = 'Cancel';
      cancel.onclick = () => view.closeModal();
      actions.append(save, cancel);
    };
    card.addEventListener('click', e => {
      const t = e.target.closest('.pf-tab'); if (!t) return;
      stash(); tab = t.getAttribute('data-t'); render();
    });
    render();
    view.showModal(card);
  }

  const API = { Prefs, apply, openDialog, BOT_OPTS, KEYS };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerPrefs = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
