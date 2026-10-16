/* Asistente IA flotante (Body-Fit) */
(function () {
  'use strict';
  var history = [];
  var busy = false;

  var FACE =
    '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">' +
    '<rect x="6" y="40" width="9" height="20" rx="3" fill="#1f2937"/><rect x="85" y="40" width="9" height="20" rx="3" fill="#1f2937"/>' +
    '<rect x="14" y="46" width="72" height="8" rx="2" fill="#374151"/>' +
    '<circle cx="50" cy="52" r="27" fill="#ffd9b3"/>' +
    '<path d="M23 46c2-20 52-20 54 0-8-8-46-8-54 0z" fill="#1f2937"/>' +
    '<rect x="22" y="40" width="56" height="7" rx="3" fill="#ef4444"/>' +
    '<circle cx="41" cy="54" r="4" fill="#111"/><circle cx="59" cy="54" r="4" fill="#111"/>' +
    '<circle cx="42.3" cy="52.7" r="1.3" fill="#fff"/><circle cx="60.3" cy="52.7" r="1.3" fill="#fff"/>' +
    '<path d="M39 66q11 10 22 0" stroke="#111" stroke-width="3" fill="none" stroke-linecap="round"/>' +
    '</svg>';

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  // ── DOM ──────────────────────────────────────────────
  var fab = el('button'); fab.id = 'bf-ai-fab'; fab.title = 'Asistente IA'; fab.setAttribute('aria-label', 'Abrir asistente');
  fab.innerHTML = FACE; fab.appendChild(el('span', 'bf-badge', 'IA'));

  var panel = el('div'); panel.id = 'bf-ai-panel';
  var head = el('div', 'bf-head');
  var av = el('div', 'bf-av'); av.innerHTML = FACE;
  var ht = el('div'); ht.appendChild(el('b', '', 'Coach IA')); ht.appendChild(el('small', '', 'Pídeme registrar clientes, pagos o asistencia'));
  var closeBtn = el('button', '', '×'); closeBtn.setAttribute('aria-label', 'Cerrar');
  head.appendChild(av); head.appendChild(ht); head.appendChild(closeBtn);

  var msgs = el('div', 'bf-msgs');
  var chips = el('div', 'bf-chips');
  ['Registra un cliente', 'Registrar asistencia', '¿Qué planes hay?'].forEach(function (t) {
    var c = el('span', '', t); c.onclick = function () { input.value = t; send(); }; chips.appendChild(c);
  });
  var form = el('form', 'bf-form');
  var input = el('input'); input.placeholder = 'Ej: registra a Juan Pérez, cc 123456…'; input.maxLength = 500; input.autocomplete = 'off';
  var sendBtn = el('button', '', '➤'); sendBtn.type = 'submit';
  form.appendChild(input); form.appendChild(sendBtn);
  panel.appendChild(head); panel.appendChild(msgs); panel.appendChild(chips); panel.appendChild(form);
  document.body.appendChild(fab); document.body.appendChild(panel);

  function scroll() { msgs.scrollTop = msgs.scrollHeight; }
  function bubble(text, cls) { var m = el('div', 'bf-m ' + cls, text); msgs.appendChild(m); scroll(); return m; }

  bubble('¡Hola! Soy tu coach IA 💪 Dime qué necesitas. Ejemplo: "registra a María López, cédula 1002003004" o "María pagó el plan mensual en Nequi".', 'bot');

  function toggle(open) {
    var o = open === undefined ? !panel.classList.contains('open') : open;
    panel.classList.toggle('open', o);
    if (o) setTimeout(function () { input.focus(); }, 50);
  }
  fab.onclick = function () { toggle(); };
  closeBtn.onclick = function () { toggle(false); };

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
    input.value = ''; chips.style.display = 'none';
    bubble(text, 'me');
    history.push({ role: 'user', content: text });
    var typing = el('div', 'bf-typing', 'Escribiendo…'); msgs.appendChild(typing); scroll();
    setBusy(true);
    post('/assistant/chat', { messages: history }).then(function (r) {
      typing.remove();
      bubble(r.reply, r.reply.indexOf('⚠️') === 0 ? 'bot err' : 'bot');
      history.push({ role: 'assistant', content: r.reply });
      (r.actions || []).forEach(renderCard);
    }).catch(function (e) {
      typing.remove(); bubble(e.message || 'Error de conexión.', 'bot err');
    }).then(function () { setBusy(false); input.focus(); });
  }
  form.onsubmit = function (e) { e.preventDefault(); send(); };
})();
