/*
 * PokerIQ — online multiplayer, serverless. Restores the desktop LAN/network
 * play (network/{server,client,protocol}.py) without any server: peers connect
 * directly over WebRTC DataChannels using copy/paste signalling (offer/answer
 * SDP blobs), so it still runs from one self-contained HTML file in any browser.
 *
 * Topology: the host runs the authoritative engine (its existing Controller);
 * each guest is a remote seat. The host forwards every engine event plus a
 * tailored authoritative game-state blob (own hole cards only; all at showdown)
 * to each peer, and asks a peer for an action when it is that seat's turn. A
 * guest mirrors the state and renders with the full PokerIQ UI (advisor, ToM,
 * summary) computed locally from its own cards + the public board.
 *
 * NetHost / NetGuest take an abstract transport so the protocol is unit-tested
 * with an in-memory loopback; RTCTransport is the real WebRTC implementation.
 */
(function (root) {
  'use strict';

  const PG = (typeof require !== 'undefined') ? require('./game.js') : root.PokerGame;

  // ---------------- protocol helpers ----------------
  const legalWire = (g, seat) => {
    const L = g.legalActions(seat);
    return { toCall: L.toCall, canCheck: L.canCheck, canRaise: L.canRaise, minRaiseTo: L.minRaiseTo, maxRaiseTo: L.maxRaiseTo, pot: L.pot };
  };

  // ---------------- Host ----------------
  class NetHost {
    constructor(ctrl, transport, opts = {}) {
      this.ctrl = ctrl;
      this.t = transport;
      this.hostName = opts.hostName || 'Host';
      this.seatByPeer = {};      // peerId -> seat
      this.peerBySeat = {};      // seat -> peerId
      this.nameByPeer = {};      // peerId -> display name
      this.pending = [];         // peers awaiting a seat (joined mid-hand)
      this.chatLog = [];
      this.onUpdate = opts.onUpdate || function () {};
      ctrl.netHost = this;
      this.t.onMessage((peer, msg) => this.onPeerMessage(peer, msg));
      if (this.t.onClose) this.t.onClose(peer => this.onPeerClose(peer));
    }

    seats() {
      // {seatIndex: name|null} for the lobby view
      const out = {};
      this.ctrl.game.players.forEach(p => { out[p.seat] = this.ctrl.remoteSeats.has(p.seat) ? p.name : (p.seat === 0 ? this.hostName + ' (you)' : null); });
      return out;
    }
    connectedPlayers() {
      return Object.keys(this.seatByPeer).map(peer => ({ peer, seat: this.seatByPeer[peer], name: this.nameByPeer[peer] }));
    }

    onPeerMessage(peer, msg) {
      if (!msg || !msg.t) return;
      if (msg.t === 'join') this.join(peer, msg.name);
      else if (msg.t === 'action') this.remoteAction(peer, msg);
      else if (msg.t === 'chat') this.chat(this.nameByPeer[peer] || 'Guest', msg.text);
    }

    // open seats = bot seats with chips, not already remote
    openSeat() {
      const g = this.ctrl.game;
      for (let i = 1; i < g.players.length; i++) {
        const p = g.players[i];
        if (p && p.stack > 0 && !this.ctrl.remoteSeats.has(i)) return i;
      }
      return -1;
    }

    join(peer, name) {
      name = (name || 'Guest').slice(0, 12);
      this.nameByPeer[peer] = name;
      // seat now if between hands; otherwise queue for the next deal
      if (!this.ctrl.game.handInProgress) this.seatPeer(peer);
      else { if (!this.pending.includes(peer)) this.pending.push(peer); this.t.send(peer, { t: 'sys', text: 'Seated at the next hand…' }); }
      this.onUpdate();
    }

    seatPeer(peer) {
      const seat = this.openSeat();
      if (seat < 0) { this.t.send(peer, { t: 'full' }); return false; }
      const g = this.ctrl.game, name = this.nameByPeer[peer] || 'Guest';
      g.players[seat].style = 'human';     // engine now waits for this seat
      g.players[seat].name = name;
      this.ctrl.remoteSeats.add(seat);
      this.seatByPeer[peer] = seat; this.peerBySeat[seat] = peer;
      this.t.send(peer, { t: 'welcome', seat, sb: g.sb(), bb: g.bb(), hostName: this.hostName });
      this.t.send(peer, { t: 'state', gs: g.netStateFor(seat, !g.handInProgress) });
      this.broadcast({ t: 'sys', text: `${name} joined (seat ${seat + 1})` });
      this.chatLog.push({ from: '—', text: `${name} joined`, sys: true });
      return true;
    }

    applyPendingSeats() {
      // called from Controller.newHand (host) before dealing
      const still = [];
      for (const peer of this.pending) { if (!this.seatPeer(peer)) still.push(peer); }
      this.pending = still;
      this.ctrl.requestedRemote = -1;
    }

    onPeerClose(peer) {
      const seat = this.seatByPeer[peer];
      if (seat != null) {
        // turn the seat back into a bot so the table keeps playing
        this.ctrl.remoteSeats.delete(seat);
        const g = this.ctrl.game, names = PG.CUTE_NAMES;
        g.players[seat].style = 'tight'; g.players[seat].name = names.tight;
        delete this.peerBySeat[seat];
        this.broadcast({ t: 'sys', text: `${this.nameByPeer[peer] || 'A player'} left — seat ${seat + 1} is a bot now` });
      }
      delete this.seatByPeer[peer]; delete this.nameByPeer[peer];
      this.onUpdate();
      // if it was their turn, let the (now-bot) seat act
      if (this.ctrl.game.awaitingAction && this.ctrl.game.toAct === seat) {
        this.ctrl.game.awaitingAction = false; this.ctrl.game.awaitingBot = seat;
        this.ctrl.pump();
      }
    }

    requestAction(seat, legal) {
      const peer = this.peerBySeat[seat]; if (!peer) return;
      this.t.send(peer, { t: 'act', legal: legalWire(this.ctrl.game, seat), gs: this.ctrl.game.netStateFor(seat, false) });
    }

    remoteAction(peer, msg) {
      const seat = this.seatByPeer[peer]; const g = this.ctrl.game;
      if (seat == null || !g.awaitingAction || g.toAct !== seat) return;   // not your turn
      g.applyAction(seat, msg.action, msg.amount || 0);   // emits events → broadcast
      this.ctrl.render();
      this.ctrl.pump();
    }

    // every engine event → forward to peers with their tailored authoritative state
    onEngineEvent(type, payload) {
      const g = this.ctrl.game;
      const revealAll = !g.handInProgress;   // showdown: reveal all hole cards
      for (const peer of Object.keys(this.seatByPeer)) {
        const seat = this.seatByPeer[peer];
        this.t.send(peer, { t: 'ev', type, payload, gs: g.netStateFor(seat, revealAll) });
      }
    }

    chat(from, text) {
      text = String(text || '').slice(0, 200);
      this.chatLog.push({ from, text });
      this.broadcast({ t: 'chat', from, text });
      this.onUpdate();
    }
    broadcast(msg) { for (const peer of Object.keys(this.seatByPeer)) this.t.send(peer, msg); }
  }

  // ---------------- Guest ----------------
  class NetGuest {
    constructor(ctrl, transport, opts = {}) {
      this.ctrl = ctrl;          // a follower Controller
      this.t = transport;
      this.name = opts.name || 'Guest';
      this.chatLog = [];
      this.onUpdate = opts.onUpdate || function () {};
      this.seated = false;
      ctrl.netGuest = this;
      this.t.onMessage(msg => this.onMsg(msg));
      this.t.send({ t: 'join', name: this.name });
    }

    onMsg(msg) {
      if (!msg || !msg.t) return;
      const ctrl = this.ctrl, g = ctrl.game;
      switch (msg.t) {
        case 'welcome':
          ctrl.mySeat = msg.seat; this.seated = true;
          this.hostName = msg.hostName;
          this.onUpdate(); ctrl.render();
          break;
        case 'state':
          g.applyNet(msg.gs); ctrl.render();
          break;
        case 'act':
          g.applyNet(msg.gs); this.legal = msg.legal; ctrl.render();
          break;
        case 'ev':
          g.applyNet(msg.gs);
          // at showdown the host revealed every hand — make sure the building
          // history carries them so the summary can show all hole cards.
          if (msg.type === 'handEnd' && ctrl.history) {
            ctrl.history.holeCards = g.players.filter(p => p.hand.length).map(p => ({ seat: p.seat, name: p.name, cards: p.hand.slice() }));
          }
          ctrl.onGameEvent(msg.type, msg.payload);
          ctrl.render();
          break;
        case 'chat':
          this.chatLog.push({ from: msg.from, text: msg.text }); this.onUpdate(); break;
        case 'sys':
          this.chatLog.push({ from: '—', text: msg.text, sys: true }); this.onUpdate(); break;
        case 'full':
          this.chatLog.push({ from: '—', text: 'Table is full — no open seat.', sys: true }); this.onUpdate(); break;
      }
    }

    sendAction(action, amount) { this.t.send({ t: 'action', action, amount: amount || 0 }); }
    sendChat(text) { text = String(text || '').slice(0, 200); this.t.send({ t: 'chat', text }); this.chatLog.push({ from: this.name, text, me: true }); this.onUpdate(); }
  }

  // ---------------- in-memory loopback transport (tests) ----------------
  // A hub wiring one host transport to N guest transports with no network.
  class LoopbackHub {
    constructor() { this.hostRecv = null; this.guests = {}; this.closeCb = null; this._n = 0; }
    hostTransport() {
      const hub = this;
      return {
        onMessage(fn) { hub.hostRecv = fn; },
        onClose(fn) { hub.closeCb = fn; },
        send(peer, msg) { const gt = hub.guests[peer]; if (gt && gt._recv) gt._recv(clone(msg)); },
        broadcast(msg) { for (const p of Object.keys(hub.guests)) this.send(p, msg); },
      };
    }
    guestTransport() {
      const hub = this; const id = 'peer' + (++hub._n);
      const gt = {
        id, _recv: null,
        onMessage(fn) { gt._recv = fn; },
        send(msg) { if (hub.hostRecv) hub.hostRecv(id, clone(msg)); },
      };
      hub.guests[id] = gt;
      return gt;
    }
    dropGuest(id) { if (this.closeCb) this.closeCb(id); delete this.guests[id]; }
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  // ---------------- WebRTC transport (browser) ----------------
  // Manual copy/paste signalling: no server. One RTCPeerConnection per guest on
  // the host; one on the guest. SDP+ICE bundled into a single base64 blob so the
  // handshake is two copy/pastes. STUN is optional (LAN works without it).
  const ICE = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }, { urls: 'stun:stun1.l.google.com:19302' }] };
  const enc = o => { try { return btoa(JSON.stringify(o)); } catch (e) { return ''; } };
  const dec = s => { try { return JSON.parse(atob(s.trim())); } catch (e) { return null; } };
  const haveRTC = () => typeof RTCPeerConnection !== 'undefined';

  function gatherComplete(pc) {
    return new Promise(res => {
      if (pc.iceGatheringState === 'complete') return res();
      const check = () => { if (pc.iceGatheringState === 'complete') { pc.removeEventListener('icegatheringstatechange', check); res(); } };
      pc.addEventListener('icegatheringstatechange', check);
      setTimeout(res, 4000);   // fall back after a moment (LAN candidates arrive fast)
    });
  }

  // Host-side multi-peer transport over WebRTC.
  class RTCHostTransport {
    constructor() { this.peers = {}; this._msg = null; this._close = null; this._n = 0; }
    onMessage(fn) { this._msg = fn; }
    onClose(fn) { this._close = fn; }
    send(peer, msg) { const p = this.peers[peer]; if (p && p.ch && p.ch.readyState === 'open') { try { p.ch.send(JSON.stringify(msg)); } catch (e) {} } }
    broadcast(msg) { for (const id of Object.keys(this.peers)) this.send(id, msg); }
    // create an offer blob for a new guest; returns {id, offer}
    async createOffer() {
      const id = 'peer' + (++this._n);
      const pc = new RTCPeerConnection(ICE);
      const ch = pc.createDataChannel('piq');
      const rec = { pc, ch };
      this.peers[id] = rec;
      ch.onmessage = e => { if (this._msg) { const m = safe(e.data); if (m) this._msg(id, m); } };
      ch.onclose = () => { if (this._close) this._close(id); delete this.peers[id]; };
      pc.onconnectionstatechange = () => { if ((pc.connectionState === 'failed' || pc.connectionState === 'disconnected') && this._close) { this._close(id); } };
      const offer = await pc.createOffer(); await pc.setLocalDescription(offer); await gatherComplete(pc);
      return { id, offer: enc(pc.localDescription) };
    }
    async acceptAnswer(id, blob) {
      const rec = this.peers[id]; if (!rec) return false;
      const ans = dec(blob); if (!ans) return false;
      await rec.pc.setRemoteDescription(ans); return true;
    }
  }

  // Guest-side single-peer transport over WebRTC.
  class RTCGuestTransport {
    constructor() { this.pc = null; this.ch = null; this._msg = null; this._open = null; }
    onMessage(fn) { this._msg = fn; }
    onOpen(fn) { this._open = fn; }
    send(msg) { if (this.ch && this.ch.readyState === 'open') { try { this.ch.send(JSON.stringify(msg)); } catch (e) {} } }
    // accept the host's offer blob, return our answer blob
    async accept(offerBlob) {
      const offer = dec(offerBlob); if (!offer) throw new Error('bad offer blob');
      const pc = new RTCPeerConnection(ICE); this.pc = pc;
      pc.ondatachannel = e => {
        this.ch = e.channel;
        this.ch.onopen = () => { if (this._open) this._open(); };
        this.ch.onmessage = ev => { if (this._msg) { const m = safe(ev.data); if (m) this._msg(m); } };
      };
      await pc.setRemoteDescription(offer);
      const ans = await pc.createAnswer(); await pc.setLocalDescription(ans); await gatherComplete(pc);
      return enc(pc.localDescription);
    }
  }
  function safe(d) { try { return JSON.parse(d); } catch (e) { return null; } }

  const API = { NetHost, NetGuest, LoopbackHub, RTCHostTransport, RTCGuestTransport, haveRTC, enc, dec };
  // attach the UI (browser only) lazily so Node tests don't need the DOM
  if (typeof document !== 'undefined') { try { attachUI(API); } catch (e) {} }
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.PokerNet = API;

  // ---------------- UI ----------------
  function attachUI(API) {
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    API.openMenu = function (ctx) {
      const { view } = ctx;
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `<h2>Play online</h2>
        <div class="sub">Serverless peer-to-peer poker over WebRTC — no install, no server. Host a table and send each friend an invite code, or join with one. Works across the internet (or just your LAN).</div>
        <div class="modal-actions"></div>`;
      const host = document.createElement('button'); host.className = 'btn check'; host.textContent = '🖥 Host a table';
      host.onclick = () => { if (!API.haveRTC()) return noRTC(view); openHost(ctx); };
      const join = document.createElement('button'); join.className = 'btn raise'; join.textContent = '🔗 Join a table';
      join.onclick = () => { if (!API.haveRTC()) return noRTC(view); openJoin(ctx); };
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Cancel';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').append(host, join, close);
      view.showModal(card);
    };

    function noRTC(view) {
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `<h2>WebRTC unavailable</h2><div class="notice">This browser doesn't expose WebRTC, so peer-to-peer online play isn't available here. Hotseat (Players ▸ pass-and-play) still works for same-device multiplayer.</div><div class="modal-actions"></div>`;
      const b = document.createElement('button'); b.className = 'ghost'; b.textContent = 'OK'; b.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(b); view.showModal(card);
    }

    function chatPanelHTML() {
      return `<div class="net-step"><h3>Table chat</h3><div class="net-chat" id="net-chat"></div>
        <div class="pf-row"><input id="net-chat-in" placeholder="message…" style="flex:1"><button class="ghost" id="net-chat-send">Send</button></div></div>`;
    }
    function renderChat(card, log, send) {
      const box = card.querySelector('#net-chat'); if (!box) return;
      box.innerHTML = log.map(m => m.sys ? `<div class="sys">${esc(m.text)}</div>` : `<div class="${m.me ? 'me' : ''}"><b>${esc(m.from)}:</b> ${esc(m.text)}</div>`).join('');
      box.scrollTop = box.scrollHeight;
      const inp = card.querySelector('#net-chat-in'), btn = card.querySelector('#net-chat-send');
      if (btn) btn.onclick = () => { const v = inp.value.trim(); if (v) { send(v); inp.value = ''; } };
      if (inp) inp.onkeydown = e => { if (e.key === 'Enter') { const v = inp.value.trim(); if (v) { send(v); inp.value = ''; } } };
    }

    function openHost(ctx) {
      const { ctrl, view } = ctx;
      const name = (prompt('Your display name?', 'Host') || 'Host').slice(0, 12);
      const transport = new API.RTCHostTransport();
      const netHost = new API.NetHost(ctrl, transport, { hostName: name });
      const card = document.createElement('div'); card.className = 'modal-card net-host';
      const draw = () => {
        const seats = netHost.seats();
        const seatRows = Object.keys(seats).map(s => `<tr><td>Seat ${+s + 1}</td><td>${seats[s] ? esc(seats[s]) : '<span class="muted">bot / open</span>'}</td></tr>`).join('');
        card.innerHTML = `<h2>Hosting — ${esc(name)}'s table</h2>
          <div class="sub">Add a player to generate an invite code. Send it to your friend; paste their reply code below to connect them. Deal hands from the table as usual — guests play their own seats.</div>
          <table class="net-table"><tr><th>Seat</th><th>Player</th></tr>${seatRows}</table>
          <div class="net-step"><h3>1 — Invite a player</h3>
            <button class="ghost" id="net-newoffer">➕ Generate invite code</button>
            <textarea class="net-blob" id="net-offer" readonly placeholder="invite code appears here — copy &amp; send it"></textarea>
            <button class="ghost" id="net-copyoffer">Copy invite</button></div>
          <div class="net-step"><h3>2 — Connect them</h3>
            <textarea class="net-blob" id="net-answer" placeholder="paste your friend's reply code here"></textarea>
            <button class="ghost" id="net-accept">Connect player</button>
            <span id="net-acc-msg" class="muted"></span></div>
          ${chatPanelHTML()}
          <div class="modal-actions"></div>`;
        const done = document.createElement('button'); done.className = 'ghost'; done.textContent = 'Close';
        done.onclick = () => view.closeModal();
        card.querySelector('.modal-actions').appendChild(done);
        let curOffer = null;
        card.querySelector('#net-newoffer').onclick = async () => {
          card.querySelector('#net-offer').value = 'generating…';
          const { id, offer } = await transport.createOffer();
          curOffer = id; card.querySelector('#net-offer').value = offer;
        };
        card.querySelector('#net-copyoffer').onclick = () => { const ta = card.querySelector('#net-offer'); ta.select(); try { navigator.clipboard.writeText(ta.value); } catch (e) {} };
        card.querySelector('#net-accept').onclick = async () => {
          const blob = card.querySelector('#net-answer').value.trim(); const msg = card.querySelector('#net-acc-msg');
          if (!curOffer) { msg.textContent = 'generate an invite first'; return; }
          msg.textContent = 'connecting…';
          const okc = await transport.acceptAnswer(curOffer, blob);
          msg.textContent = okc ? 'connected — they will be seated next hand' : 'could not read that code';
          card.querySelector('#net-answer').value = '';
        };
        renderChat(card, netHost.chatLog, t => netHost.chat(name, t));
      };
      netHost.onUpdate = () => { draw(); };
      draw();
      view.showModal(card);
    }

    function openJoin(ctx) {
      const { ctrl, view } = ctx;
      const name = (prompt('Your display name?', 'Player') || 'Player').slice(0, 12);
      const card = document.createElement('div'); card.className = 'modal-card';
      card.innerHTML = `<h2>Join a table</h2>
        <div class="sub">Paste the host's invite code, copy your reply code back to them, and you're in. Your seat, cards, advisor and Theory-of-Mind all run locally.</div>
        <div class="net-step"><h3>1 — Paste the invite code</h3>
          <textarea class="net-blob" id="net-offer" placeholder="paste the host's invite code"></textarea>
          <button class="ghost" id="net-make">Generate my reply code</button></div>
        <div class="net-step"><h3>2 — Send this back to the host</h3>
          <textarea class="net-blob" id="net-answer" readonly placeholder="your reply code appears here"></textarea>
          <button class="ghost" id="net-copyans">Copy reply</button>
          <div id="net-status" class="muted"></div></div>
        <div class="modal-actions"></div>`;
      const close = document.createElement('button'); close.className = 'ghost'; close.textContent = 'Close';
      close.onclick = () => view.closeModal();
      card.querySelector('.modal-actions').appendChild(close);
      const transport = new API.RTCGuestTransport();
      let guest = null;
      transport.onOpen(() => {
        card.querySelector('#net-status').textContent = 'connected! waiting for the host to deal…';
        // hand the table over to the live game view; close the dialog shortly
        setTimeout(() => view.closeModal(), 900);
      });
      card.querySelector('#net-make').onclick = async () => {
        const offer = card.querySelector('#net-offer').value.trim();
        const status = card.querySelector('#net-status');
        if (!offer) { status.textContent = 'paste the invite code first'; return; }
        try {
          status.textContent = 'building reply…';
          const ans = await transport.accept(offer);
          card.querySelector('#net-answer').value = ans;
          status.textContent = 'copy your reply code to the host →';
          // become a follower: swap the controller into guest/mirror mode
          ctrl.follower = true; ctrl.netGuest = null; ctrl.handResult = null; ctrl.history = null;
          ctrl.humanSeats = new Set([ctrl.mySeat]); ctrl.hotseat = false;
          guest = new API.NetGuest(ctrl, transport, { name });
          guest.onUpdate = () => {};
        } catch (e) { status.textContent = 'could not read that invite code'; }
      };
      card.querySelector('#net-copyans').onclick = () => { const ta = card.querySelector('#net-answer'); ta.select(); try { navigator.clipboard.writeText(ta.value); } catch (e) {} };
      view.showModal(card);
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
