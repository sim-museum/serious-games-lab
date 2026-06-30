/*
 * PokerIQ — Claude hand analysis, in the browser. Restores the desktop
 * ClaudeAnalysisThread feature without the `claude` CLI: it calls the Anthropic
 * Messages API directly from the page (the user supplies their own API key,
 * stored in localStorage) using the dangerous-direct-browser-access header.
 *
 *   - critique mode: a ≤3-sentence per-player review (Hand Summary ▸ Analyze)
 *   - annotate  mode: chess-engine !/!?/?!/? per-action marks + a RETROSPECTIVE
 *     section with per-street hindsight paragraphs
 *
 * Model: claude-opus-4-8 with adaptive thinking (budget_tokens is rejected on
 * 4.8). Network is opt-in and only fires when the user clicks Analyze.
 */
(function (root) {
  'use strict';

  const store = (root && root.__piqStore) || (function () {
    const m = {}; return { getItem: k => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: k => { delete m[k]; } };
  })();
  const KEY = 'piq.claude.key';
  const MODEL = 'claude-opus-4-8';
  const ENDPOINT = 'https://api.anthropic.com/v1/messages';

  function getKey() { try { return store.getItem(KEY) || ''; } catch (e) { return ''; } }
  function setKey(k) { try { if (k) store.setItem(KEY, k); else store.removeItem(KEY); } catch (e) {} }
  function hasKey() { return !!getKey(); }

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function critiquePrompt(name, handText) {
    return `Critique this poker hand from ${name}'s perspective (3 sentences max). ` +
      `Was ${name}'s play correct? What was ${name}'s key decision? ` +
      `Plain text only, no markdown.\n\n${handText}`;
  }
  function annotatePrompt(name, handText, lineCount, wordLimit) {
    return `You are annotating a poker hand for ${name} like a chess engine annotates a game.\n` +
      `The action lines are numbered 1..${lineCount}. For each meaningful action by ${name}, output one line:\n` +
      `"N. <one-sentence comment, optionally ending with a marker !, !?, ?!, or ?>" where ` +
      `! = strong play, !? = interesting, ?! = dubious, ? = mistake. Skip routine actions.\n` +
      `Then a line "RETROSPECTIVE:" followed, for each street that was reached, by a line ` +
      `"STREET[<Preflop|Flop|Turn|River>]:" and a short hindsight paragraph. Keep the whole ` +
      `retrospective under ${wordLimit || 80} words. Plain text only, no markdown.\n\n${handText}`;
  }

  // One API call for one POV. Returns { player, seat, text, model } (text is an
  // error string on failure so the UI can show it inline, like the desktop).
  async function analyzeOne(pov, handText, opts) {
    const fetchFn = (opts && opts.fetchFn) || (typeof fetch !== 'undefined' ? fetch : null);
    const key = (opts && opts.key) || getKey();
    const mode = (opts && opts.mode) || 'critique';
    const model = (opts && opts.model) || MODEL;
    if (!fetchFn) return { player: pov.name, seat: pov.seat, text: '(no fetch available in this environment)', model };
    if (!key) return { player: pov.name, seat: pov.seat, text: '(no API key set — open ⚙ to add one)', model };
    const prompt = mode === 'annotate'
      ? annotatePrompt(pov.name, handText, opts.lineCount || 0, opts.wordLimit)
      : critiquePrompt(pov.name, handText);
    const body = {
      model, max_tokens: mode === 'annotate' ? 1200 : 400,
      thinking: { type: 'adaptive' },
      output_config: { effort: 'high' },
      messages: [{ role: 'user', content: prompt }],
    };
    try {
      const resp = await fetchFn(ENDPOINT, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': key,
          'anthropic-version': '2023-06-01',
          'anthropic-dangerous-direct-browser-access': 'true',
        },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        let detail = '';
        try { const j = await resp.json(); detail = (j && j.error && j.error.message) || ''; } catch (e) {}
        return { player: pov.name, seat: pov.seat, text: `(API error ${resp.status}${detail ? ': ' + detail : ''})`, model };
      }
      const data = await resp.json();
      const text = (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('\n').trim()
        || (data.stop_reason === 'refusal' ? '(model declined to analyze this hand)' : '(empty response)');
      return { player: pov.name, seat: pov.seat, text, model };
    } catch (e) {
      // network/CORS failures land here
      return { player: pov.name, seat: pov.seat, text: `(request failed: ${e && e.message ? e.message : 'network error'})`, model };
    }
  }

  // Analyze a hand from each POV. Returns an array of result objects.
  async function analyze(opts) {
    const povs = (opts && opts.povs) || [];
    const handText = (opts && opts.handText) || '';
    const out = [];
    for (const pov of povs) {                       // sequential keeps key rate-limit-friendly
      const r = await analyzeOne(pov, handText, opts);
      out.push(r);
      if (opts && opts.onProgress) opts.onProgress(out.length, povs.length, pov.name);
    }
    return out;
  }

  // ---- UI ----
  function keyRow(card, view) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<div class="pf-row"><label class="lead">Anthropic API key</label>
      <input type="password" class="cl-key" id="cl-key" placeholder="sk-ant-..." value="${esc(getKey())}"></div>
      <div class="pf-desc">Stored only in this browser's localStorage and sent directly to api.anthropic.com when you click Analyze. Get a key at console.anthropic.com. Leave blank and Save to remove it.</div>`;
    return wrap;
  }

  function openSettings(ctx) {
    const { view } = ctx;
    const card = document.createElement('div'); card.className = 'modal-card';
    card.innerHTML = `<h2>Claude analysis — settings</h2>
      <div class="sub">PokerIQ can critique your hands with Claude (Opus 4.8). This calls the Anthropic API directly from your browser with your own key.</div>
      <div id="cl-keyrow"></div>
      <div class="modal-actions"></div>`;
    card.querySelector('#cl-keyrow').appendChild(keyRow(card, view));
    const save = document.createElement('button'); save.className = 'btn check'; save.textContent = 'Save';
    save.onclick = () => { setKey(card.querySelector('#cl-key').value.trim()); view.closeModal(); };
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Cancel';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').append(save, close);
    view.showModal(card);
  }

  // Render the per-POV analysis blocks, marking !/!?/?!/? glyphs.
  function blocksHTML(results) {
    // highlight annotation marks; lookahead for the trailing boundary so the
    // shared space isn't consumed (adjacent marks + end-of-line marks both match)
    const mark = t => esc(t)
      .replace(/(\s|^)(!\?|\?!|!|\?)(?=\s|$|<)/g, (m, a, g) => a + `<span class="cl-mark ${g === '!' ? 'good' : g === '?' ? 'bad' : 'dub'}">${g}</span>`);
    return results.map(r => `<div class="cl-block"><span class="who">${esc(r.player)} — ${esc(r.model)}</span>${mark(r.text).replace(/\n/g, '<br>')}</div>`).join('');
  }

  // The Hand Summary "Analyze with Claude" flow.
  function analyzeHand(ctx, history, mode) {
    const { ctrl, view } = ctx;
    mode = mode || 'critique';
    const h = history || ctrl.lastHistory;
    const built = ctrl.handTextForClaude(h);
    if (!built) return;
    const povs = ctrl.claudePovs();
    const card = document.createElement('div'); card.className = 'modal-card';
    card.innerHTML = `<h2>Claude — hand analysis</h2>
      <div class="sub">${mode === 'annotate' ? 'Per-action marks + retrospective' : 'Per-player critique (≤3 sentences each)'} from Claude Opus 4.8.</div>
      <div id="cl-body"><div class="cl-busy">Running Claude (Opus 4.8, adaptive thinking)… 0/${povs.length}</div></div>
      <div class="modal-actions"></div>`;
    const body = card.querySelector('#cl-body');
    const settings = document.createElement('button'); settings.className = 'ghost'; settings.textContent = '⚙ Key';
    settings.onclick = () => openSettings(ctx);
    const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
    close.onclick = () => view.closeModal();
    card.querySelector('.modal-actions').append(settings, close);
    view.showModal(card);

    if (!hasKey()) {
      body.innerHTML = `<div class="notice">No Anthropic API key set. Click <b>⚙ Key</b> below to add one — it stays in this browser and is sent only to api.anthropic.com.</div>`;
      return;
    }
    // word-limit scales with hero loss severity (mirrors desktop retro_word_limit)
    let wordLimit = 80;
    const heroSeat = povs.length ? povs[0].seat : 0;
    const net = ((h && h.result && h.result.net) || []).find(n => n.seat === heroSeat);
    if (net && net.net < 0) wordLimit = Math.min(320, 80 + Math.floor(Math.abs(net.net) / Math.max(1, ctrl.game.bb())) * 8);

    analyze({
      povs, handText: built.text, mode, lineCount: built.lineCount, wordLimit,
      onProgress: (done, total, name) => { body.innerHTML = `<div class="cl-busy">Running Claude (Opus 4.8)… ${done}/${total} — last: ${esc(name)}</div>`; },
    }).then(results => {
      body.innerHTML = blocksHTML(results);
      // stash on the history so the Hand Summary can show it too
      if (h) h.claudeAnalysis = results;
    }).catch(e => { body.innerHTML = `<div class="notice">Analysis failed: ${esc(e && e.message ? e.message : 'error')}</div>`; });
  }

  const API = { getKey, setKey, hasKey, analyze, analyzeOne, openSettings, analyzeHand, blocksHTML, MODEL, ENDPOINT };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerClaude = API;
})(typeof globalThis !== 'undefined' ? globalThis : this);
