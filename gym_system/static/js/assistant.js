/* Salo, el asistente flotante (Body-Fit) */
(function () {
  'use strict';
  var history = [];
  var busy = false;

  // Imagen propia del coach: si existe static/img/coach.png se usa; si no, el muñeco SVG.
  var CUSTOM_IMG = '/static/img/coach.png';
  var FACE = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="bgG" cx="50%" cy="38%" r="70%"><stop offset="0" stop-color="#1f2a24"/><stop offset="1" stop-color="#070907"/></radialGradient><radialGradient id="skG" cx="38%" cy="32%" r="80%"><stop offset="0" stop-color="#f8e0ba"/><stop offset=".6" stop-color="#ebc597"/><stop offset="1" stop-color="#cf9c68"/></radialGradient><linearGradient id="capG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5cf08c"/><stop offset=".55" stop-color="#22c55e"/><stop offset="1" stop-color="#128a3e"/></linearGradient><linearGradient id="brimG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22c55e"/><stop offset="1" stop-color="#0f6b30"/></linearGradient><linearGradient id="hrG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a5530"/><stop offset="1" stop-color="#55301a"/></linearGradient><linearGradient id="frG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cfd5dc"/></linearGradient><linearGradient id="lnG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b3340"/><stop offset=".5" stop-color="#05070a"/><stop offset="1" stop-color="#000"/></linearGradient><radialGradient id="spG"><stop offset="0" stop-color="#fff"/><stop offset=".4" stop-color="#fff" stop-opacity=".6"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient><clipPath id="bfc"><circle cx="50" cy="50" r="50"/></clipPath></defs><circle cx="50" cy="50" r="50" fill="url(#bgG)"/><g clip-path="url(#bfc)"><ellipse cx="54" cy="90" rx="30" ry="5" fill="#000" opacity=".55"/><g transform="rotate(-8 50 56)"><path d="M30 84q-6-2-8-9 8 3 14-2 6 4 14 4 8 0 14-5 4 6 0 12z" fill="#16a34a" stroke="#0b3d16" stroke-width="1.8" stroke-linejoin="round"/><path d="M17 86q3-9 6 0t6 0t6 0" stroke="#4ade80" stroke-width="2.6" fill="none" stroke-linecap="round"/><ellipse cx="27.5" cy="65" rx="5" ry="7.5" fill="#dcae80" stroke="#1a0f0a" stroke-width="1.8"/><path d="M27 62q3 2 1 7" stroke="#b98456" stroke-width="1.4" fill="none" stroke-linecap="round"/><ellipse cx="55" cy="64" rx="31" ry="27" fill="url(#skG)" stroke="#1a0f0a" stroke-width="2.2"/><path d="M32 74c6 17 36 24 52 2-6 14-20 20-32 20-14 0-24-10-20-22z" fill="#b8814f" opacity=".35"/><ellipse cx="74" cy="74" rx="5" ry="3" fill="#f08a6a" opacity=".35"/><path d="M27 47C25 57 27 63 30 68L34 59Q38 52 43 57Q48 50 53 56Q59 50 64 56Q70 51 75 56Q79 52 83 58Q86 51 81 44Z" fill="url(#hrG)" stroke="#1a0f0a" stroke-width="1.8" stroke-linejoin="round"/><path d="M40 55q2-3 4 0M55 54q2-3 5 0M68 54q2-3 4 0" stroke="#b07a4a" stroke-width="1.2" fill="none" stroke-linecap="round"/><g transform="translate(0 -5)"><path d="M24 52c-2-24 14-38 36-36 18 2 28 14 28 28-10-8-26-10-42-8-10 2-18 8-22 16z" fill="url(#capG)" stroke="#0b3d16" stroke-width="2.2" stroke-linejoin="round"/><path d="M44 18c-8 6-12 18-12 30M58 17c-3 9-3 20-1 28M72 22c-1 6 0 13 4 19" stroke="#0f6b30" stroke-width="1.2" fill="none" opacity=".7" stroke-linecap="round"/><path d="M34 30c4-9 14-13 24-12" stroke="#fff" stroke-width="3" fill="none" opacity=".4" stroke-linecap="round"/><path d="M45 30a6 6 0 0 1 12 0z" fill="#16a34a" stroke="#0b3d16" stroke-width="1.6"/><path d="M24 52c-9 2-15 8-17 17 9-2 18-6 25-13z" fill="url(#brimG)" stroke="#0b3d16" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 64c4-4 9-6 14-7" stroke="#4ade80" stroke-width="1.6" fill="none" opacity=".7" stroke-linecap="round"/></g><path d="M22 65l12-7" stroke="#1a0f0a" stroke-width="5.6" stroke-linecap="round"/><path d="M22 65l12-7" stroke="url(#frG)" stroke-width="3.4" stroke-linecap="round"/><rect x="33" y="56" width="51" height="14" rx="5.5" fill="url(#lnG)" stroke="#1a0f0a" stroke-width="5.4"/><rect x="33" y="56" width="51" height="14" rx="5.5" fill="none" stroke="url(#frG)" stroke-width="3.2"/><path d="M39 59.5l9 0M44 62.5l6 0" stroke="#fff" stroke-width="1.8" opacity=".45" stroke-linecap="round"/><path d="M63 59l9 0" stroke="#fff" stroke-width="1.4" opacity=".25" stroke-linecap="round"/><path d="M58 56.5v-0.5" stroke="#fff"/><path d="M51 75q6-3.4 12 0q-6 4.6-12 0z" fill="#1a0f0a"/><path d="M54 74.4q3-1.2 6 0" stroke="#5a3a28" stroke-width=".9" fill="none" stroke-linecap="round"/><path d="M54.5 80q3 1.6 6 0" stroke="#8a5a3a" stroke-width="1.3" fill="none" stroke-linecap="round"/><circle cx="27" cy="76" r="8" fill="url(#spG)"/><path d="M27 70l1.4 4 4 1.4-4 1.4L27 81l-1.4-4.2-4-1.4 4-1.4z" fill="#fff"/><g fill="#a77846" opacity=".5"><circle cx="40" cy="49" r=".7"/><circle cx="71" cy="51" r=".7"/><circle cx="62" cy="84" r=".7"/><circle cx="46" cy="81" r=".7"/><circle cx="79" cy="68" r=".7"/><circle cx="37" cy="76" r=".7"/><circle cx="68" cy="80" r=".7"/><circle cx="50" cy="86" r=".7"/></g></g></g></svg>';

  function setMascot(box) {
    box.innerHTML = FACE;
    if (!CUSTOM_IMG) return;
    var img = new Image();
    img.alt = 'Salo';
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;display:block';
    img.onload = function () { box.innerHTML = ''; box.appendChild(img); };
    img.src = CUSTOM_IMG;
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  // ── DOM ──────────────────────────────────────────────
  var fab = el('button'); fab.id = 'bf-ai-fab'; fab.title = 'Salo'; fab.setAttribute('aria-label', 'Abrir chat con Salo');
  var fabImg = el('span', 'bf-face'); setMascot(fabImg); var badge = el('span', 'bf-badge', 'IA'); fab.appendChild(fabImg); fab.appendChild(badge);

  var panel = el('div'); panel.id = 'bf-ai-panel';
  var head = el('div', 'bf-head');
  var av = el('div', 'bf-av'); setMascot(av);
  var ht = el('div'); ht.appendChild(el('b', '', 'Salo')); ht.appendChild(el('small', '', 'Clientes, pagos, asistencia y música 🎵'));
  var musicBtn = el('button', 'bf-mbtn', '🎵'); musicBtn.type = 'button'; musicBtn.title = 'Música'; musicBtn.setAttribute('aria-label', 'Música');
  var closeBtn = el('button', 'bf-x', '×'); closeBtn.setAttribute('aria-label', 'Cerrar');
  head.appendChild(av); head.appendChild(ht); head.appendChild(musicBtn); head.appendChild(closeBtn);

  // Reproductor: barra "sonando ahora" + lista de canciones (se abre con 🎵)
  var np = el('div', 'bf-np');
  var npTitle = el('span', 'bf-np-t', '');
  function mbtn(txt, label) { var b = el('button', '', txt); b.type = 'button'; b.title = label; b.setAttribute('aria-label', label); return b; }
  var bPrev = mbtn('⏮', 'Anterior'), bPlay = mbtn('▶', 'Reproducir / pausar'), bNext = mbtn('⏭', 'Siguiente'), bStop = mbtn('⏹', 'Detener');
  np.appendChild(npTitle); [bPrev, bPlay, bNext, bStop].forEach(function (b) { np.appendChild(b); });
  var mlist = el('div', 'bf-mlist');

  var msgs = el('div', 'bf-msgs');
  var chips = el('div', 'bf-chips');
  ['Registra un cliente', 'Registrar asistencia', '¿Qué planes hay?', '🎵 Pon música'].forEach(function (t) {
    var c = el('span', '', t); c.onclick = function () { input.value = t; send(); }; chips.appendChild(c);
  });
  var form = el('form', 'bf-form');
  var input = el('input'); input.placeholder = 'Ej: registra a Juan Pérez, cc 123456…'; input.maxLength = 500; input.autocomplete = 'off';
  var sendBtn = el('button', '', '➤'); sendBtn.type = 'submit';
  form.appendChild(input); form.appendChild(sendBtn);
  panel.appendChild(head); panel.appendChild(np); panel.appendChild(mlist); panel.appendChild(msgs); panel.appendChild(chips); panel.appendChild(form);
  document.body.appendChild(fab); document.body.appendChild(panel);

  function scroll() { msgs.scrollTop = msgs.scrollHeight; }
  function bubble(text, cls) { var m = el('div', 'bf-m ' + cls, text); msgs.appendChild(m); scroll(); return m; }

  bubble('¡Qué más pues, parce! Soy Salo, el Ferxxo del gym 💚🔥 Dime qué necesitas. Ejemplo: "registra a María López, cédula 1002003004" o "María pagó el plan mensual en Nequi". También puedo poner música: "pon Brickell" o "pon música aleatoria" 🎵', 'bot');

  function toggle(open) {
    var o = open === undefined ? !panel.classList.contains('open') : open;
    panel.classList.toggle('open', o);
    if (o) setTimeout(function () { input.focus(); }, 50);
  }
  fab.onclick = function () { toggle(); };
  closeBtn.onclick = function () { toggle(false); };


  // ── Reproductor de música ────────────────────────────
  var SILENT = 'data:audio/wav;base64,UklGRkQDAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YSADAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgA==';
  var STORE = 'bf_music';
  var audio = new Audio(); audio.preload = 'none';
  var songs = [], byId = {}, queue = [], pos = -1, unlocked = false, lastSave = 0;
  audio.volume = 0.8;

  function store(obj) { try { localStorage.setItem(STORE, JSON.stringify(obj)); } catch (e) {} }
  function readStore() { try { return JSON.parse(localStorage.getItem(STORE) || 'null'); } catch (e) { return null; } }
  function saveState() {
    store({ queue: queue, pos: pos, time: audio.currentTime || 0, playing: !audio.paused, volume: audio.volume });
  }
  function isSilent() { return audio.src.indexOf('data:') === 0; }

  function loadSongs(cb) {
    if (songs.length) { if (cb) cb(); return; }
    fetch('/assistant/music', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      songs = d.songs || []; byId = {};
      songs.forEach(function (s) { byId[s.id] = s; });
      renderList();
      if (cb) cb();
    }).catch(function () { if (cb) cb(); });
  }

  function renderList() {
    mlist.innerHTML = '';
    if (!songs.length) { mlist.appendChild(el('div', 'bf-mempty', 'No hay canciones cargadas.')); return; }
    var cur = queue[pos];
    songs.forEach(function (s) {
      var row = el('div', 'bf-mrow' + (s.id === cur ? ' on' : ''), (s.id === cur ? '♪ ' : '') + s.title);
      row.onclick = function () { playQueue(songs.map(function (x) { return x.id; }), false, s.id); };
      mlist.appendChild(row);
    });
  }

  function refreshUi() {
    var id = queue[pos], playing = !audio.paused && !audio.ended;
    np.classList.toggle('on', !!id);
    npTitle.textContent = id && byId[id] ? byId[id].title : '';
    bPlay.textContent = playing ? '⏸' : '▶';
    fab.classList.toggle('bf-playing', playing);
    badge.textContent = playing ? '♪' : 'IA';
    renderList();
  }

  function playCurrent() {
    var id = queue[pos];
    if (!id) return;
    audio.src = '/assistant/music/' + encodeURIComponent(id);
    var pr = audio.play();
    if (pr && pr.catch) pr.catch(function () { refreshUi(); });   // el navegador bloqueó el autoplay: queda listo para ▶
    refreshUi();
  }

  function playQueue(ids, shuffle, startId) {
    ids = ids.filter(function (i) { return byId[i]; });
    if (!ids.length) return;
    if (shuffle) {
      for (var i = ids.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = ids[i]; ids[i] = ids[j]; ids[j] = t; }
    }
    queue = ids; pos = startId ? Math.max(0, ids.indexOf(startId)) : 0;
    playCurrent();
  }

  function nextTrack() {
    if (!queue.length) return;
    if (pos + 1 < queue.length) pos++;
    else if (queue.length > 1) pos = 0;
    else { audio.pause(); audio.currentTime = 0; refreshUi(); return; }
    playCurrent();
  }
  function prevTrack() {
    if (!queue.length) return;
    if (audio.currentTime > 3) { audio.currentTime = 0; return; }
    pos = pos > 0 ? pos - 1 : queue.length - 1;
    playCurrent();
  }
  function togglePlay() {
    if (!queue.length) { loadSongs(function () { playQueue(songs.map(function (s) { return s.id; }), true); }); return; }
    if (audio.paused) { if (!audio.src || isSilent()) playCurrent(); else audio.play().catch(function () {}); }
    else audio.pause();
  }
  function stopMusic() { audio.pause(); audio.removeAttribute('src'); audio.load(); queue = []; pos = -1; store(null); refreshUi(); }
  function setVolume(delta) { audio.volume = Math.max(0, Math.min(1, audio.volume + delta)); saveState(); }

  // Desbloquea el audio con un gesto del usuario (Safari/Chrome móvil bloquean play() tras una espera de red)
  function unlock() {
    if (unlocked || !audio.paused) { unlocked = true; return; }
    unlocked = true;
    audio.src = SILENT;
    var pr = audio.play();
    if (pr && pr.catch) pr.catch(function () {});
  }

  function runMusic(cmds) {
    loadSongs(function () {
      (cmds || []).forEach(function (c) {
        switch (c.type) {
          case 'play': playQueue((c.queue || []).slice(), !!c.shuffle); break;
          case 'pausar': audio.pause(); break;
          case 'reanudar': togglePlayIfPaused(); break;
          case 'siguiente': nextTrack(); break;
          case 'anterior': prevTrack(); break;
          case 'detener': stopMusic(); break;
          case 'subir_volumen': setVolume(0.15); break;
          case 'bajar_volumen': setVolume(-0.15); break;
        }
      });
    });
  }
  function togglePlayIfPaused() { if (audio.paused) togglePlay(); }

  audio.addEventListener('ended', function () { if (!isSilent()) nextTrack(); });
  audio.addEventListener('play', function () { if (!isSilent()) { refreshUi(); saveState(); } });
  audio.addEventListener('pause', function () { if (!isSilent()) { refreshUi(); saveState(); } });
  audio.addEventListener('error', function () {
    if (isSilent() || !audio.src) return;
    bubble('⚠️ No pude reproducir esa canción.', 'bot err');
    if (queue.length > 1) nextTrack();
  });
  audio.addEventListener('timeupdate', function () {
    var now = Date.now();
    if (!isSilent() && now - lastSave > 2000) { lastSave = now; saveState(); }
  });

  bPrev.onclick = prevTrack; bNext.onclick = nextTrack; bStop.onclick = stopMusic; bPlay.onclick = togglePlay;
  musicBtn.onclick = function () {
    unlock();
    var open = !mlist.classList.contains('open');
    mlist.classList.toggle('open', open);
    if (open) loadSongs();
  };

  // La app recarga la página al navegar: retomamos donde se quedó la música (si el navegador lo permite)
  (function restore() {
    var st = readStore();
    if (!st || !st.queue || !st.queue.length) return;
    loadSongs(function () {
      var ids = st.queue.filter(function (i) { return byId[i]; });
      if (!ids.length || !byId[st.queue[st.pos]]) return;
      queue = st.queue; pos = st.pos;
      if (typeof st.volume === 'number') audio.volume = st.volume;
      audio.src = '/assistant/music/' + encodeURIComponent(queue[pos]);
      audio.addEventListener('loadedmetadata', function once() {
        audio.removeEventListener('loadedmetadata', once);
        try { audio.currentTime = st.time || 0; } catch (e) {}
      });
      refreshUi();
      if (st.playing) { var pr = audio.play(); if (pr && pr.catch) pr.catch(function () { refreshUi(); }); }
    });
  })();

  // ── Red ──────────────────────────────────────────────
  function post(url, body) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    }).then(function (r) {
      if (r.redirected || r.status === 401 || r.status === 403) throw new Error('Tu sesión expiró. Recarga la página e inicia sesión.');
      return r.json();
    });
  }

  function setBusy(b) { busy = b; sendBtn.disabled = b; input.disabled = b; }

  function renderCard(a) {
    var card = el('div', 'bf-card');
    card.appendChild(el('h6', '', '📝 ' + a.title + ' — confirma para guardar'));
    a.lines.forEach(function (l) { card.appendChild(el('div', 'l', l)); });
    var btns = el('div', 'bf-btns');
    var ok = el('button', 'ok', '✔ Confirmar'), no = el('button', 'no', 'Cancelar');
    function resolve(approve) {
      ok.disabled = no.disabled = true;
      post('/assistant/confirm', { token: a.token, approve: approve }).then(function (r) {
        card.classList.add('done');
        bubble(r.message, r.ok ? 'bot' : 'bot err');
        history.push({ role: 'assistant', content: r.message });
      }).catch(function (e) { ok.disabled = no.disabled = false; bubble(e.message, 'bot err'); });
    }
    ok.onclick = function () { resolve(true); }; no.onclick = function () { resolve(false); };
    btns.appendChild(ok); btns.appendChild(no); card.appendChild(btns);
    msgs.appendChild(card); scroll();
  }

  function send() {
    var text = input.value.trim();
    if (!text || busy) return;
    unlock();
    input.value = ''; chips.style.display = 'none';
    bubble(text, 'me');
    history.push({ role: 'user', content: text });
    var typing = el('div', 'bf-typing', 'Salo está en lo suyo…'); msgs.appendChild(typing); scroll();
    setBusy(true);
    post('/assistant/chat', { messages: history }).then(function (r) {
      typing.remove();
      bubble(r.reply, r.reply.indexOf('⚠️') === 0 ? 'bot err' : 'bot');
      history.push({ role: 'assistant', content: r.reply });
      (r.actions || []).forEach(renderCard);
      if (r.music && r.music.length) runMusic(r.music);
    }).catch(function (e) {
      typing.remove(); bubble(e.message || 'Error de conexión.', 'bot err');
    }).then(function () { setBusy(false); input.focus(); });
  }
  form.onsubmit = function (e) { e.preventDefault(); send(); };
})();
