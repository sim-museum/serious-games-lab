/*
 * PokerIQ — boot + wiring. Creates the Controller + View, hooks the top-menu
 * to the trainer registry / stats panel, and provides honest in-browser
 * notices for the two features that cannot run in a sandboxed single file:
 * LAN multiplayer (raw TCP sockets) and Claude hand-analysis (CLI subprocess).
 */
(function (root) {
  'use strict';
  const PokerUI = root.PokerUI, PT = root.PokerTrainers, PA = root.PokerAnalytics;

  function boot(mountId) {
    const mount = document.getElementById(mountId || 'app');
    const ctrl = new PokerUI.Controller({
      botDelayMs: 600,
      onRender: (snap) => view.render(snap),
    });
    const view = new PokerUI.View(mount, ctrl);

    // trainer modal launcher
    function openTrainer(key) {
      const entry = PT.REGISTRY[key]; if (!entry) return;
      const ctx = {
        rng: Math.random,
        stats: ctrl.stats,
        predictions: [],                      // calibration: none logged yet
        actionHistory: ctrl.events.slice(),   // range narrowing uses last hand's log
        close: () => view.closeModal(),
      };
      view.showModal(entry.build(ctx));
    }

    // stats panel (session + lifetime snapshot)
    function openStats() {
      const s = ctrl.stats;
      const card = document.createElement('div'); card.className = 'modal-card';
      const [lo, hi] = s.edgeConfidenceInterval();
      card.innerHTML = `
        <h2>Session statistics</h2>
        <div class="sub">Live session + persistent lifetime numbers (localStorage).</div>
        <div class="kv">
          <div class="k">Session hands</div><div>${s.sessionHands}</div>
          <div class="k">Session bb/100</div><div>${s.sessionBbPer100 >= 0 ? '+' : ''}${s.sessionBbPer100.toFixed(1)}</div>
          <div class="k">Session σ ($/hand)</div><div>${s.sessionStd.toFixed(2)}</div>
          <div class="k">Lifetime hands</div><div>${s.lifetimeHands}</div>
          <div class="k">Lifetime profit</div><div>$${s.lifetimeProfit.toFixed(0)}</div>
          <div class="k">Lifetime bb/100</div><div>${s.lifetimeBbPer100 >= 0 ? '+' : ''}${s.lifetimeBbPer100.toFixed(1)}</div>
          <div class="k">Edge 95% CI</div><div>[${lo.toFixed(1)}, ${hi.toFixed(1)}] bb/100</div>
        </div>
        <div class="modal-actions"></div>`;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      view.showModal(card);
    }

    // honest notice for dropped features
    function droppedNotice(title, body) {
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `<h2>${title}</h2><div class="notice">${body}</div><div class="modal-actions"></div>`;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'OK';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      view.showModal(card);
    }

    function openHelp() {
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `
        <h2>PokerIQ — about this build</h2>
        <div class="sub">Single self-contained HTML port of the PyQt6 PokerIQ trainer.</div>
        <p>Play 6-max No-Limit Hold'em vs nine AI styles (tight, loose, station, aggressive, optimal,
        shark, exploit, ICM, theory-of-mind) with live Monte-Carlo equity, pot-odds and EV advice,
        board-texture reads, opponent tells, and eight study trainers.</p>
        <h3 style="margin:14px 0 6px;color:#9aa7b4;font-size:13px;text-transform:uppercase;">Controls</h3>
        <div class="kv">
          <div class="k">God mode</div><div>reveal all hole cards (top bar)</div>
          <div class="k">Tells</div><div>show opponent ranges, leaks & thinking level</div>
          <div class="k">Raise</div><div>slider + ½ / ¾ / Pot / All-in quick buttons</div>
        </div>
        <h3 style="margin:14px 0 6px;color:#9aa7b4;font-size:13px;text-transform:uppercase;">Not in the browser build</h3>
        <div class="notice">
          <b>LAN multiplayer</b> and <b>Claude hand-analysis</b> from the desktop app are intentionally
          omitted: a single sandboxed HTML file cannot open raw TCP sockets or shell out to the
          <code>claude</code> CLI. Everything else — engine, equity, bots, analytics, trainers, and
          lifetime stats — runs fully offline in this one file.
        </div>
        <div class="modal-actions"></div>`;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      view.showModal(card);
    }

    function saveLog() {
      const text = ctrl.buildLogText();
      const name = ctrl.logFilename();
      try {
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = name;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (e) { /* fall through to preview */ }
      // also show a copyable preview (works even where download is blocked)
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `<h2>Session log</h2>
        <div class="sub">Saved as <code>${name}</code> — exact PyQt PokerIQ format. Paste into an AI for play analysis &amp; commentary.</div>
        <textarea class="log-preview" readonly></textarea>
        <div class="modal-actions"></div>`;
      card.querySelector('.log-preview').value = text;
      const copy = document.createElement('button'); copy.className = 'btn check'; copy.textContent = 'Copy to clipboard';
      copy.onclick = () => { const ta = card.querySelector('.log-preview'); ta.select(); try { navigator.clipboard.writeText(text); } catch (e) { document.execCommand('copy'); } copy.textContent = 'Copied ✓'; };
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').append(copy, close);
      view.showModal(card);
    }

    view.onMenu = (act) => {
      if (act === 'trainers') {
        view.popupMenu('trainers', Object.keys(PT.REGISTRY).map(k => [PT.REGISTRY[k].label, () => openTrainer(k)]));
      } else if (act === 'stats') {
        openStats();
      } else if (act === 'savelog') {
        saveLog();
      } else if (act === 'help') {
        openHelp();
      }
    };

    // expose dropped-feature notices via keyboard shortcut help / future menu
    ctrl.openDroppedNotice = droppedNotice;
    root.PIQ = { ctrl, view, openTrainer, openStats, droppedNotice, saveLog };

    ctrl.newHand();
    return root.PIQ;
  }

  root.PokerIQBoot = boot;
  // auto-boot. This script is inlined at the end of <body>, so #app is already
  // parsed and present even while readyState === 'loading' — boot immediately
  // when we can see it, otherwise wait for the DOM to finish.
  if (typeof document !== 'undefined' && document.getElementById) {
    if (document.getElementById('app')) boot('app');
    else document.addEventListener('DOMContentLoaded', () => boot('app'));
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
